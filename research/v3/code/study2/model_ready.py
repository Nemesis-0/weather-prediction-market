"""Canonical pre-model intraday state construction for V3 Study 2.

This module transforms the accepted historical backfill into a leakage-auditable
date x intraday-state table.  It does not fit a model or inspect market prices.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

CHICAGO = ZoneInfo("America/Chicago")
MODEL_READY_VERSION = "v3_s2_model_ready_1"
GRID_MINUTES = 30
METAR_TIME_RE = re.compile(r"^KMDW\s+(\d{2})(\d{2})(\d{2})Z\b")

HISTORICAL_AVAILABILITY_CONVENTION = (
    "METAR issue timestamp parsed from DDHHMMZ is used as the historical "
    "point-in-time availability proxy; original HTTP publication/receive latency "
    "is not reconstructed"
)
HISTORICAL_WU_VINTAGE_LIMITATION = (
    "historical Weather Underground pages were retrieved after the event date; "
    "equality to the page state at original ForecastEx settlement time is not established"
)


class ModelReadyError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ModelReadyError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def split_for_date(d: date) -> str:
    if date(2024, 1, 1) <= d <= date(2024, 12, 31):
        return "train"
    if date(2025, 1, 1) <= d <= date(2025, 12, 31):
        return "calibration"
    if date(2026, 1, 1) <= d <= date(2026, 10, 6):
        return "historical_validation"
    raise ModelReadyError(f"date outside frozen split census: {d.isoformat()}")


def _candidate_months(event_date: date) -> list[tuple[int, int]]:
    y, m = event_date.year, event_date.month
    out: list[tuple[int, int]] = []
    for delta in (-1, 0, 1):
        mm = m + delta
        yy = y
        if mm == 0:
            yy -= 1
            mm = 12
        elif mm == 13:
            yy += 1
            mm = 1
        out.append((yy, mm))
    return out


def parse_metar_issue_utc(
    *,
    metar: str,
    event_date: date,
    valid_local: str,
) -> datetime:
    m = METAR_TIME_RE.match(metar.strip())
    if not m:
        raise ModelReadyError(f"unparseable KMDW METAR issue time: {metar!r}")

    day, hour, minute = map(int, m.groups())
    try:
        expected_local = datetime.strptime(valid_local, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ModelReadyError(f"invalid valid_local {valid_local!r}") from exc

    candidates: list[datetime] = []
    for yy, mm in _candidate_months(event_date):
        try:
            utc_dt = datetime(yy, mm, day, hour, minute, tzinfo=timezone.utc)
        except ValueError:
            continue
        local = utc_dt.astimezone(CHICAGO)
        if (
            local.date() == event_date
            and local.replace(tzinfo=None, second=0, microsecond=0) == expected_local
        ):
            candidates.append(utc_dt)

    if len(candidates) != 1:
        raise ModelReadyError(
            f"METAR UTC resolution not unique for event_date={event_date}, "
            f"valid_local={valid_local!r}, metar={metar!r}, candidates={candidates}"
        )
    return candidates[0]


def canonical_numeric_observations(
    rows: list[dict[str, Any]],
    *,
    event_date: date,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    numeric: list[dict[str, Any]] = []
    null_temp_rows = 0

    for r in rows:
        tmpf = r.get("tmpf")
        if not isinstance(tmpf, (int, float)):
            null_temp_rows += 1
            continue
        metar = str(r.get("metar") or "")
        valid_local = str(r.get("valid_local") or "")
        obs_utc = parse_metar_issue_utc(
            metar=metar,
            event_date=event_date,
            valid_local=valid_local,
        )
        rec = dict(r)
        rec["tmpf"] = float(tmpf)
        rec["observation_utc"] = obs_utc
        rec["observation_local"] = obs_utc.astimezone(CHICAGO)
        numeric.append(rec)

    by_utc: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for r in numeric:
        by_utc[r["observation_utc"]].append(r)

    canonical: list[dict[str, Any]] = []
    same_utc_duplicate_rows = 0
    for obs_utc in sorted(by_utc):
        group = by_utc[obs_utc]
        temps = {round(float(r["tmpf"]), 10) for r in group}
        if len(temps) > 1:
            raise ModelReadyError(
                f"conflicting numeric temperatures at same UTC instant "
                f"{obs_utc.isoformat()}: {sorted(temps)}"
            )
        chosen = sorted(
            group,
            key=lambda r: (
                str(r.get("observation_key") or ""),
                str(r.get("metar") or ""),
            ),
        )[0]
        canonical.append(chosen)
        same_utc_duplicate_rows += max(0, len(group) - 1)

    return canonical, {
        "raw_weather_row_count": len(rows),
        "null_temperature_row_count": null_temp_rows,
        "numeric_temperature_row_count": len(numeric),
        "canonical_numeric_observation_count": len(canonical),
        "same_utc_numeric_duplicate_rows_collapsed": same_utc_duplicate_rows,
    }


def local_day_grid(event_date: date, *, grid_minutes: int = GRID_MINUTES) -> list[datetime]:
    start_local = datetime.combine(event_date, time(0, 0), tzinfo=CHICAGO)
    end_local = datetime.combine(event_date + timedelta(days=1), time(0, 0), tzinfo=CHICAGO)
    cur = start_local.astimezone(timezone.utc)
    end = end_local.astimezone(timezone.utc)
    step = timedelta(minutes=grid_minutes)
    out: list[datetime] = []
    while cur < end:
        out.append(cur)
        cur += step
    return out


def _latest_at_or_before(
    observations: list[dict[str, Any]],
    t_utc: datetime,
) -> dict[str, Any] | None:
    latest = None
    for r in observations:
        if r["observation_utc"] <= t_utc:
            latest = r
        else:
            break
    return latest


def build_state_rows(
    *,
    event_date: date,
    observations: list[dict[str, Any]],
    wu_max_f: float,
    grid_minutes: int = GRID_MINUTES,
) -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    running_max: float | None = None
    obs_idx = 0

    for decision_utc in local_day_grid(event_date, grid_minutes=grid_minutes):
        while (
            obs_idx < len(observations)
            and observations[obs_idx]["observation_utc"] <= decision_utc
        ):
            temp = float(observations[obs_idx]["tmpf"])
            running_max = temp if running_max is None else max(running_max, temp)
            obs_idx += 1

        latest = observations[obs_idx - 1] if obs_idx > 0 else None
        local = decision_utc.astimezone(CHICAGO)

        row: dict[str, Any] = {
            "event_date": event_date.isoformat(),
            "split": split_for_date(event_date),
            "decision_utc": decision_utc.isoformat(),
            "decision_local": local.isoformat(),
            "local_utc_offset_minutes": int(local.utcoffset().total_seconds() // 60),
            "local_minute_of_day": local.hour * 60 + local.minute,
            "grid_minutes": grid_minutes,
            "state_available": latest is not None,
            "target_wu_max_f": float(wu_max_f),
            "historical_availability_proxy": "METAR_issue_timestamp_DDHHMMZ",
        }

        if latest is None:
            row.update({
                "latest_observation_utc": None,
                "latest_observation_local": None,
                "current_temp_f": None,
                "running_max_f": None,
                "temp_minus_running_max_f": None,
                "observation_age_minutes": None,
                "temp_60m_reference_f": None,
                "temp_60m_reference_utc": None,
                "temp_change_60m_f": None,
                "target_residual_f": None,
            })
            states.append(row)
            continue

        current_temp = float(latest["tmpf"])
        age_min = (decision_utc - latest["observation_utc"]).total_seconds() / 60.0
        ref_cutoff = decision_utc - timedelta(minutes=60)
        ref = _latest_at_or_before(observations, ref_cutoff)

        row.update({
            "latest_observation_utc": latest["observation_utc"].isoformat(),
            "latest_observation_local": latest["observation_local"].isoformat(),
            "current_temp_f": current_temp,
            "running_max_f": float(running_max),
            "temp_minus_running_max_f": current_temp - float(running_max),
            "observation_age_minutes": age_min,
            "temp_60m_reference_f": None if ref is None else float(ref["tmpf"]),
            "temp_60m_reference_utc": None if ref is None else ref["observation_utc"].isoformat(),
            "temp_change_60m_f": None if ref is None else current_temp - float(ref["tmpf"]),
            "target_residual_f": float(wu_max_f) - float(running_max),
        })
        states.append(row)

    return states


def _attempt_dir_from_status(date_dir: Path, status: dict[str, Any]) -> Path:
    rel = status.get("latest_attempt_summary")
    if not rel:
        raise ModelReadyError(f"missing latest_attempt_summary for {date_dir.name}")
    summary = date_dir / str(rel)
    if not summary.is_file():
        raise ModelReadyError(f"missing attempt summary: {summary}")
    return summary.parent


def _fresh_verify_raw_hashes(attempt_dir: Path) -> int:
    raw_fetches = _read_jsonl(attempt_dir / "sources" / "raw_fetches.jsonl")
    if len(raw_fetches) < 2:
        raise ModelReadyError(f"expected IEM + WU raw fetches: {attempt_dir}")
    checked = 0
    for r in raw_fetches:
        rel = r.get("raw_file")
        expected = r.get("payload_sha256")
        p = attempt_dir / str(rel)
        if not p.is_file() or _sha256(p) != expected:
            raise ModelReadyError(f"raw hash verification failed: {p}")
        checked += 1
    return checked


STATE_FIELDS = [
    "event_date", "split", "decision_utc", "decision_local",
    "local_utc_offset_minutes", "local_minute_of_day", "grid_minutes",
    "state_available", "latest_observation_utc", "latest_observation_local",
    "current_temp_f", "running_max_f", "temp_minus_running_max_f",
    "observation_age_minutes", "temp_60m_reference_f",
    "temp_60m_reference_utc", "temp_change_60m_f",
    "target_wu_max_f", "target_residual_f", "historical_availability_proxy",
]


def build_model_ready(
    *,
    backfill_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise ModelReadyError(f"output_dir already exists; refusing overwrite: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    contract = _read_json(backfill_root / "backfill_contract.json")
    census = _read_json(backfill_root / "date_census.json")
    summary = _read_json(backfill_root / "backfill_summary.json")

    if contract.get("start_date") != "2024-01-01" or contract.get("end_date") != "2026-10-06":
        raise ModelReadyError("unexpected historical census boundaries")
    if contract.get("date_count") != 1010 or census.get("date_count") != 1010:
        raise ModelReadyError("expected frozen 1010-date census")
    if summary.get("status_counts") != {"PASS": 1010} or not summary.get("all_dates_pass"):
        raise ModelReadyError("historical backfill is not 1010/1010 PASS")

    state_path = output_dir / "model_ready_states.csv"
    date_qc_path = output_dir / "date_qc.jsonl"

    split_date_counts: dict[str, int] = defaultdict(int)
    split_state_counts: dict[str, int] = defaultdict(int)
    split_available_counts: dict[str, int] = defaultdict(int)
    total_raw_hashes = 0
    total_states = 0
    available_states = 0
    dates_with_nonzero_wu_iem_max_diff = 0
    dates_with_iem_local_duplicates = 0
    wu_count_mismatch_dates = 0
    date_qc_rows: list[dict[str, Any]] = []

    with state_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=STATE_FIELDS)
        writer.writeheader()

        for dtext in census["dates"]:
            event_date = date.fromisoformat(dtext)
            split = split_for_date(event_date)
            split_date_counts[split] += 1

            date_dir = backfill_root / "dates" / dtext
            status = _read_json(date_dir / "date_status.json")
            if status.get("status") != "PASS":
                raise ModelReadyError(f"non-PASS date encountered: {dtext}")

            attempt_dir = _attempt_dir_from_status(date_dir, status)
            total_raw_hashes += _fresh_verify_raw_hashes(attempt_dir)

            weather_rows = _read_jsonl(attempt_dir / "sources" / "weather_observations.jsonl")
            canonical_obs, obs_qc = canonical_numeric_observations(
                weather_rows, event_date=event_date
            )
            if not canonical_obs:
                raise ModelReadyError(f"no canonical numeric IEM observations: {dtext}")

            wu_max = status.get("wu", {}).get("max_temperature_f")
            if not isinstance(wu_max, (int, float)):
                raise ModelReadyError(f"missing WU max target: {dtext}")

            states = build_state_rows(
                event_date=event_date,
                observations=canonical_obs,
                wu_max_f=float(wu_max),
            )

            for row in states:
                writer.writerow(row)
                total_states += 1
                split_state_counts[split] += 1
                if row["state_available"]:
                    available_states += 1
                    split_available_counts[split] += 1

            daily_diff = status.get("daily_max_difference_wu_minus_iem_f")
            if isinstance(daily_diff, (int, float)) and daily_diff != 0:
                dates_with_nonzero_wu_iem_max_diff += 1
            if (status.get("iem", {}).get("duplicate_valid_local_count") or 0) > 0:
                dates_with_iem_local_duplicates += 1
            if status.get("iem", {}).get("temperature_row_count") != status.get("wu", {}).get("observation_count"):
                wu_count_mismatch_dates += 1

            q = {
                "event_date": dtext,
                "split": split,
                "target_wu_max_f": float(wu_max),
                "daily_max_difference_wu_minus_iem_f": daily_diff,
                "iem_temperature_row_count": status.get("iem", {}).get("temperature_row_count"),
                "wu_observation_count": status.get("wu", {}).get("observation_count"),
                "iem_duplicate_valid_local_count": status.get("iem", {}).get("duplicate_valid_local_count"),
                "wu_duplicate_time_label_count": status.get("wu", {}).get("duplicate_time_label_count"),
                "grid_state_count": len(states),
                "grid_available_state_count": sum(bool(x["state_available"]) for x in states),
                **obs_qc,
            }
            date_qc_rows.append(q)

    with date_qc_path.open("w", encoding="utf-8") as f:
        for q in date_qc_rows:
            f.write(json.dumps(q, sort_keys=True) + "\n")

    split_contract = {
        "record_type": "study2_model_ready_split_contract",
        "model_ready_version": MODEL_READY_VERSION,
        "frozen_before_model_fit": True,
        "train": {"start": "2024-01-01", "end": "2024-12-31"},
        "calibration": {"start": "2025-01-01", "end": "2025-12-31"},
        "historical_validation": {"start": "2026-01-01", "end": "2026-10-06"},
        "selection_basis": (
            "chronological calendar-year split fixed before any M0 fit or performance inspection"
        ),
        "no_date_overlap": True,
    }
    (output_dir / "split_contract.json").write_text(
        json.dumps(split_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "record_type": "study2_model_ready_manifest",
        "model_ready_version": MODEL_READY_VERSION,
        "source_backfill_version": contract.get("backfill_version"),
        "source_census_sha256": contract.get("census_sha256"),
        "source_date_count": 1010,
        "grid_minutes": GRID_MINUTES,
        "split_date_counts": dict(split_date_counts),
        "split_state_counts": dict(split_state_counts),
        "split_available_state_counts": dict(split_available_counts),
        "state_row_count": total_states,
        "state_available_row_count": available_states,
        "fresh_raw_hashes_verified": total_raw_hashes,
        "dates_with_nonzero_wu_iem_daily_max_difference": dates_with_nonzero_wu_iem_max_diff,
        "dates_with_iem_duplicate_local_labels": dates_with_iem_local_duplicates,
        "dates_with_iem_wu_observation_count_mismatch": wu_count_mismatch_dates,
        "historical_availability_convention": HISTORICAL_AVAILABILITY_CONVENTION,
        "historical_wu_vintage_limitation": HISTORICAL_WU_VINTAGE_LIMITATION,
        "original_http_receive_latency_reconstructed": False,
        "original_settlement_time_wu_vintage_reconstructed": False,
        "wu_observation_count_used_as_model_feature": False,
        "iem_wu_row_count_parity_required": False,
        "guardrail": "pre_model_data_construction_only_no_model_no_probability_no_economics_no_orders",
    }
    (output_dir / "model_ready_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest
