"""Historical source-feasibility orchestration for V3 Study 2.

This module is intentionally pre-model. It retrieves the same exact IEM KMDW
and Weather Underground KMDW Daily Observations sources already accepted at H0,
archives each raw response before semantic parsing through Study2PublicSourceRecorder,
and records date-level source/QC facts needed before bulk backfill design.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from src.v3.study2.sources import Study2PublicSourceRecorder, Study2SourceError

HISTORICAL_PROBE_VERSION = "v3_s2_historical_probe_1"
CHICAGO_TZ = ZoneInfo("America/Chicago")

# Deliberately includes ordinary days plus both sides of DST transitions and the
# transition dates themselves. These are source/clock-feasibility checks only,
# not a modeling sample and not an outcome-selected subset.
DEFAULT_PROBE_DATES = (
    date(2026, 10, 5),
    date(2026, 7, 15),
    date(2026, 3, 7),
    date(2026, 3, 8),
    date(2026, 3, 9),
    date(2025, 11, 1),
    date(2025, 11, 2),
    date(2025, 11, 3),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def chicago_today() -> date:
    return datetime.now(CHICAGO_TZ).date()


def normalize_probe_dates(values: Iterable[date], *, today: date | None = None) -> list[date]:
    today = today or chicago_today()
    out: list[date] = []
    seen: set[date] = set()
    for value in values:
        if value >= today:
            raise ValueError(
                f"historical probe date must be before current Chicago date {today.isoformat()}: "
                f"{value.isoformat()}"
            )
        if value not in seen:
            seen.add(value)
            out.append(value)
    if not out:
        raise ValueError("historical probe requires at least one date")
    return out


def ensure_new_output_dir(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"historical probe output already exists; refusing reuse: {path}")
    path.mkdir(parents=True, exist_ok=False)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            out.append(value)
    return out


def _duplicate_values(values: Iterable[str]) -> list[str]:
    counts = Counter(v for v in values if v)
    return sorted(v for v, n in counts.items() if n > 1)


def summarize_iem_date(date_dir: Path, fetch_record: dict[str, Any]) -> dict[str, Any]:
    observations = _read_jsonl(date_dir / "sources" / "weather_observations.jsonl")
    valid_local = [str(x.get("valid_local") or "") for x in observations]
    duplicate_valid_local = _duplicate_values(valid_local)
    metar_present = [bool(x.get("metar")) for x in observations]
    return {
        "parse_ok": bool(fetch_record.get("parse_ok")),
        "row_count": int(fetch_record.get("row_count") or 0),
        "temperature_row_count": int(fetch_record.get("temperature_row_count") or 0),
        "running_max_tmpf": fetch_record.get("running_max_tmpf"),
        "station_check_ok": bool(fetch_record.get("station_check_ok")),
        "date_check_ok": bool(fetch_record.get("date_check_ok")),
        "archived_observation_count": len(observations),
        "duplicate_valid_local_count": len(duplicate_valid_local),
        "duplicate_valid_local_values": duplicate_valid_local,
        "all_archived_rows_have_metar": bool(observations) and all(metar_present),
        "payload_sha256": fetch_record.get("payload_sha256"),
        "raw_file": fetch_record.get("raw_file"),
    }


def summarize_wu_date(snapshot: dict[str, Any]) -> dict[str, Any]:
    observations = snapshot.get("observations") or []
    labels = [str(x.get("time_label") or "") for x in observations if isinstance(x, dict)]
    duplicate_labels = _duplicate_values(labels)
    return {
        "parse_ok": bool(snapshot.get("parse_ok")),
        "station_code": snapshot.get("station_code"),
        "page_identity": snapshot.get("page_identity"),
        "final_url_identity": snapshot.get("final_url_identity"),
        "table_identity": snapshot.get("table_identity"),
        "temperature_unit": snapshot.get("temperature_unit"),
        "observation_count": int(snapshot.get("observation_count") or 0),
        "max_temperature_f": snapshot.get("max_temperature_f"),
        "observations_sha256": snapshot.get("observations_sha256"),
        "duplicate_time_label_count": len(duplicate_labels),
        "duplicate_time_labels": duplicate_labels,
        "payload_sha256": snapshot.get("payload_sha256"),
        "raw_file": snapshot.get("raw_file"),
        "finality_status_from_live_parser": snapshot.get("finality_status"),
    }


def probe_one_date(*, event_date: date, date_dir: Path, timeout_seconds: float) -> dict[str, Any]:
    date_dir.mkdir(parents=True, exist_ok=False)
    session_id = f"historical-probe-{event_date.isoformat()}"
    recorder = Study2PublicSourceRecorder(
        output_dir=date_dir,
        event_date=event_date,
        session_id=session_id,
    )
    result: dict[str, Any] = {
        "event_date": event_date.isoformat(),
        "session_id": session_id,
        "started_utc": utc_now(),
        "retrieval_vintage": "current_http_retrieval_of_historical_source",
        "original_settlement_time_vintage_reconstructed": False,
        "settlement_finality_claim": "NOT_MADE_IN_HISTORICAL_PROBE",
        "guardrail": "source_feasibility_only_no_probability_no_economics_no_orders",
    }

    try:
        iem = recorder.capture_iem(timeout_seconds=timeout_seconds)
        result["iem"] = summarize_iem_date(date_dir, iem)
    except Study2SourceError as exc:
        result["iem"] = {"parse_ok": False, "error": str(exc)}

    try:
        wu = recorder.capture_wu(timeout_seconds=timeout_seconds)
        result["wu"] = summarize_wu_date(wu)
    except Study2SourceError as exc:
        result["wu"] = {"parse_ok": False, "error": str(exc)}

    result["source_pair_ok"] = bool(result["iem"].get("parse_ok")) and bool(result["wu"].get("parse_ok"))
    result["completed_utc"] = utc_now()
    return result


def run_historical_probe(
    *,
    dates: Iterable[date],
    output_dir: Path,
    timeout_seconds: float = 20.0,
    inter_date_sleep_seconds: float = 3.0,
) -> dict[str, Any]:
    probe_dates = normalize_probe_dates(dates)
    ensure_new_output_dir(output_dir)

    config = {
        "record_type": "study2_historical_probe_config",
        "historical_probe_version": HISTORICAL_PROBE_VERSION,
        "created_utc": utc_now(),
        "dates": [d.isoformat() for d in probe_dates],
        "timeout_seconds": float(timeout_seconds),
        "inter_date_sleep_seconds": float(inter_date_sleep_seconds),
        "date_selection_basis": "fixed_source_feasibility_and_dst_clock_probe_not_modeling_sample",
        "retrieval_vintage_limitation": (
            "historical pages are retrieved now; equality to the page state at original settlement time is unproven"
        ),
        "guardrail": "read_only_sources_only_no_model_no_economics_no_orders",
    }
    (output_dir / "probe_config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rows: list[dict[str, Any]] = []
    dates_dir = output_dir / "dates"
    dates_dir.mkdir(parents=True, exist_ok=True)
    for idx, event_date in enumerate(probe_dates):
        row = probe_one_date(
            event_date=event_date,
            date_dir=dates_dir / event_date.isoformat(),
            timeout_seconds=float(timeout_seconds),
        )
        rows.append(row)
        if idx + 1 < len(probe_dates) and inter_date_sleep_seconds > 0:
            time.sleep(float(inter_date_sleep_seconds))

    passed = sum(1 for x in rows if x.get("source_pair_ok"))
    summary = {
        "record_type": "study2_historical_probe_summary",
        "historical_probe_version": HISTORICAL_PROBE_VERSION,
        "completed_utc": utc_now(),
        "requested_date_count": len(rows),
        "source_pair_pass_count": passed,
        "source_pair_fail_count": len(rows) - passed,
        "all_source_pairs_ok": passed == len(rows),
        "dates": rows,
        "next_boundary": (
            "probe evidence only; do not treat current historical WU retrievals as proven original settlement-time vintages"
        ),
        "guardrail": "no_model_no_probability_no_economic_screen_no_order_path",
    }
    (output_dir / "historical_probe_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary
