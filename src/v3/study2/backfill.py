"""Resumable historical IEM/WU backfill orchestration for V3 Study 2.

This is a pre-model data-construction layer.  It reuses the exact H0-accepted
public-source parsers/recorders, preserves every source attempt, and exposes
date-level QC/provenance without fitting a model or computing economics.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Iterable

from src.v3.study2.historical import summarize_iem_date, summarize_wu_date
from src.v3.study2.sources import Study2PublicSourceRecorder, Study2SourceError

BACKFILL_VERSION = "v3_s2_historical_backfill_1"
RETRIEVAL_VINTAGE = "current_http_retrieval_of_historical_source"
VINTAGE_LIMITATION = (
    "historical Weather Underground pages are retrieved now; equality to the "
    "page state at original ForecastEx settlement time is not established"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inclusive_dates(start_date: date, end_date: date, *, today: date) -> list[date]:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    if end_date >= today:
        raise ValueError(
            f"historical backfill end_date must be before current Chicago date "
            f"{today.isoformat()}: {end_date.isoformat()}"
        )
    out: list[date] = []
    cur = start_date
    from datetime import timedelta
    while cur <= end_date:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
        f.flush()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _attempt_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def build_census(start_date: date, end_date: date, *, today: date) -> dict[str, Any]:
    dates = inclusive_dates(start_date, end_date, today=today)
    date_strings = [d.isoformat() for d in dates]
    return {
        "record_type": "study2_historical_backfill_date_census",
        "backfill_version": BACKFILL_VERSION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "date_count": len(date_strings),
        "dates": date_strings,
        "date_selection_basis": (
            "fixed_contiguous_recent_historical_window_selected_before_model_fitting"
        ),
        "census_sha256": canonical_json_sha256(date_strings),
    }


def initialize_or_validate_root(
    *,
    output_dir: Path,
    start_date: date,
    end_date: date,
    today: date,
) -> dict[str, Any]:
    census = build_census(start_date, end_date, today=today)
    contract_path = output_dir / "backfill_contract.json"
    census_path = output_dir / "date_census.json"

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=False)
        contract = {
            "record_type": "study2_historical_backfill_contract",
            "backfill_version": BACKFILL_VERSION,
            "created_utc": utc_now(),
            "start_date": census["start_date"],
            "end_date": census["end_date"],
            "date_count": census["date_count"],
            "census_sha256": census["census_sha256"],
            "sources": [
                "IEM_MDW_KMDW_routine_plus_special_ASOS_METAR",
                "WEATHER_UNDERGROUND_KMDW_DAILY_OBSERVATIONS",
            ],
            "primary_target": "M_D^WU = maximum temperature in parsed WU Daily Observations",
            "observation_source": "IEM MDW/KMDW ASOS/METAR routine + special",
            "retrieval_vintage": RETRIEVAL_VINTAGE,
            "historical_wu_vintage_limitation": VINTAGE_LIMITATION,
            "original_settlement_time_vintage_reconstructed": False,
            "source_substitution_allowed": False,
            "guardrail": (
                "read_only_historical_sources_only_no_model_no_probability_no_economics_no_orders"
            ),
        }
        _write_json_atomic(contract_path, contract)
        _write_json_atomic(census_path, census)
        (output_dir / "dates").mkdir(parents=True, exist_ok=True)
        (output_dir / "runs").mkdir(parents=True, exist_ok=True)
        return contract

    contract = _read_json(contract_path)
    prior_census = _read_json(census_path)
    if contract is None or prior_census is None:
        raise RuntimeError("existing backfill root is missing contract/date_census; refusing reuse")
    expected = {
        "start_date": census["start_date"],
        "end_date": census["end_date"],
        "date_count": census["date_count"],
        "census_sha256": census["census_sha256"],
        "backfill_version": BACKFILL_VERSION,
    }
    actual = {k: contract.get(k) for k in expected}
    if actual != expected:
        raise RuntimeError(
            f"existing backfill contract mismatch; refusing mixed census: expected={expected} actual={actual}"
        )
    if prior_census.get("census_sha256") != census["census_sha256"]:
        raise RuntimeError("existing date_census hash mismatch; refusing reuse")
    return contract


def _verify_raw_fetches(attempt_dir: Path) -> dict[str, Any]:
    rows = _read_jsonl(attempt_dir / "sources" / "raw_fetches.jsonl")
    checks: list[dict[str, Any]] = []
    all_ok = bool(rows)
    kinds = []
    for row in rows:
        raw_rel = row.get("raw_file")
        expected_sha = row.get("payload_sha256")
        path = attempt_dir / str(raw_rel) if raw_rel else None
        actual_sha = sha256_file(path) if path and path.is_file() else None
        ok = bool(expected_sha) and actual_sha == expected_sha
        all_ok = all_ok and ok
        kind = str(row.get("source_kind") or "")
        kinds.append(kind)
        checks.append({
            "source_kind": kind,
            "raw_file": raw_rel,
            "expected_sha256": expected_sha,
            "actual_sha256": actual_sha,
            "sha256_ok": ok,
        })
    required = {
        "IEM_ASOS_ROUTINE_SPECIAL",
        "WEATHER_UNDERGROUND_DAILY_OBSERVATIONS",
    }
    required_kinds_present = required.issubset(set(kinds))
    return {
        "raw_fetch_record_count": len(rows),
        "required_source_kinds_present": required_kinds_present,
        "all_raw_hashes_match": bool(all_ok and required_kinds_present),
        "checks": checks,
    }


def backfill_one_date(
    *,
    event_date: date,
    date_dir: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    attempts_dir = date_dir / "attempts"
    attempts_dir.mkdir(parents=True, exist_ok=True)
    attempt_id = _attempt_id()
    attempt_dir = attempts_dir / attempt_id
    attempt_dir.mkdir(parents=True, exist_ok=False)

    session_id = f"historical-backfill-{event_date.isoformat()}-{attempt_id}"
    recorder = Study2PublicSourceRecorder(
        output_dir=attempt_dir,
        event_date=event_date,
        session_id=session_id,
    )

    result: dict[str, Any] = {
        "record_type": "study2_historical_backfill_attempt",
        "backfill_version": BACKFILL_VERSION,
        "event_date": event_date.isoformat(),
        "attempt_id": attempt_id,
        "session_id": session_id,
        "started_utc": utc_now(),
        "attempt_dir": str(attempt_dir.relative_to(date_dir)),
        "retrieval_vintage": RETRIEVAL_VINTAGE,
        "historical_wu_vintage_limitation": VINTAGE_LIMITATION,
        "original_settlement_time_vintage_reconstructed": False,
        "guardrail": "sources_only_no_model_no_probability_no_economics_no_orders",
    }

    try:
        iem_fetch = recorder.capture_iem(timeout_seconds=timeout_seconds)
        result["iem"] = summarize_iem_date(attempt_dir, iem_fetch)
    except Study2SourceError as exc:
        result["iem"] = {"parse_ok": False, "error": str(exc)}

    try:
        wu_snapshot = recorder.capture_wu(timeout_seconds=timeout_seconds)
        result["wu"] = summarize_wu_date(wu_snapshot)
    except Study2SourceError as exc:
        result["wu"] = {"parse_ok": False, "error": str(exc)}

    raw_audit = _verify_raw_fetches(attempt_dir)
    result["raw_audit"] = raw_audit

    iem_ok = bool(result["iem"].get("parse_ok"))
    wu_ok = bool(result["wu"].get("parse_ok"))
    iem_identity_ok = bool(
        result["iem"].get("station_check_ok") and result["iem"].get("date_check_ok")
    )
    iem_nonempty = int(result["iem"].get("temperature_row_count") or 0) > 0
    wu_identity = result["wu"].get("page_identity") or {}
    wu_nonempty = int(result["wu"].get("observation_count") or 0) > 0
    wu_identity_ok = (
        result["wu"].get("station_code") == "KMDW"
        and wu_identity.get("icao_code") == "KMDW"
        and wu_identity.get("page_date") == event_date.isoformat()
        and wu_identity.get("time_zone") == "America/Chicago"
        and result["wu"].get("temperature_unit") == "F"
    )

    pass_ok = bool(
        iem_ok
        and wu_ok
        and iem_identity_ok
        and iem_nonempty
        and wu_identity_ok
        and wu_nonempty
        and raw_audit["all_raw_hashes_match"]
    )

    iem_max = result["iem"].get("running_max_tmpf")
    wu_max = result["wu"].get("max_temperature_f")
    result["daily_max_difference_wu_minus_iem_f"] = (
        None
        if iem_max is None or wu_max is None
        else float(wu_max) - float(iem_max)
    )
    result["status"] = "PASS" if pass_ok else "FAIL"
    result["completed_utc"] = utc_now()

    _write_json_atomic(attempt_dir / "attempt_summary.json", result)
    date_status = {
        "record_type": "study2_historical_backfill_date_status",
        "backfill_version": BACKFILL_VERSION,
        "event_date": event_date.isoformat(),
        "status": result["status"],
        "latest_attempt_id": attempt_id,
        "latest_attempt_summary": str(
            (attempt_dir / "attempt_summary.json").relative_to(date_dir)
        ),
        "updated_utc": result["completed_utc"],
        "iem": result["iem"],
        "wu": result["wu"],
        "raw_audit": result["raw_audit"],
        "daily_max_difference_wu_minus_iem_f": result["daily_max_difference_wu_minus_iem_f"],
        "retrieval_vintage": RETRIEVAL_VINTAGE,
        "historical_wu_vintage_limitation": VINTAGE_LIMITATION,
        "original_settlement_time_vintage_reconstructed": False,
    }
    _write_json_atomic(date_dir / "date_status.json", date_status)
    return date_status


def _pass_status_is_reusable(date_dir: Path, status: dict[str, Any]) -> bool:
    if status.get("status") != "PASS":
        return False
    rel = status.get("latest_attempt_summary")
    if not rel:
        return False
    attempt_summary_path = date_dir / str(rel)
    if not attempt_summary_path.is_file():
        return False
    attempt_summary = _read_json(attempt_summary_path)
    if attempt_summary is None or attempt_summary.get("status") != "PASS":
        return False
    attempt_dir = attempt_summary_path.parent
    fresh_raw_audit = _verify_raw_fetches(attempt_dir)
    return bool(fresh_raw_audit.get("all_raw_hashes_match"))


def collect_statuses(output_dir: Path, dates: Iterable[date]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in dates:
        date_dir = output_dir / "dates" / d.isoformat()
        status = _read_json(date_dir / "date_status.json")
        if status is None:
            out.append({"event_date": d.isoformat(), "status": "PENDING"})
        else:
            out.append(status)
    return out


def write_index_and_summary(
    *,
    output_dir: Path,
    dates: list[date],
    run_id: str,
    attempted_this_run: int,
    skipped_pass_this_run: int,
) -> dict[str, Any]:
    statuses = collect_statuses(output_dir, dates)
    index_path = output_dir / "date_index.jsonl"
    with index_path.open("w", encoding="utf-8") as f:
        for s in statuses:
            compact = {
                "event_date": s.get("event_date"),
                "status": s.get("status"),
                "latest_attempt_id": s.get("latest_attempt_id"),
                "iem_row_count": (s.get("iem") or {}).get("row_count"),
                "iem_temperature_row_count": (s.get("iem") or {}).get("temperature_row_count"),
                "iem_running_max_tmpf": (s.get("iem") or {}).get("running_max_tmpf"),
                "iem_duplicate_valid_local_count": (s.get("iem") or {}).get("duplicate_valid_local_count"),
                "wu_observation_count": (s.get("wu") or {}).get("observation_count"),
                "wu_max_temperature_f": (s.get("wu") or {}).get("max_temperature_f"),
                "wu_duplicate_time_label_count": (s.get("wu") or {}).get("duplicate_time_label_count"),
                "daily_max_difference_wu_minus_iem_f": s.get("daily_max_difference_wu_minus_iem_f"),
                "all_raw_hashes_match": (s.get("raw_audit") or {}).get("all_raw_hashes_match"),
                "retrieval_vintage": s.get("retrieval_vintage"),
                "original_settlement_time_vintage_reconstructed": s.get(
                    "original_settlement_time_vintage_reconstructed"
                ),
            }
            f.write(json.dumps(compact, sort_keys=True) + "\n")

    counts: dict[str, int] = {}
    for s in statuses:
        key = str(s.get("status") or "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1

    pass_rows = [s for s in statuses if s.get("status") == "PASS"]
    diffs = [
        float(s["daily_max_difference_wu_minus_iem_f"])
        for s in pass_rows
        if isinstance(s.get("daily_max_difference_wu_minus_iem_f"), (int, float))
    ]
    summary = {
        "record_type": "study2_historical_backfill_summary",
        "backfill_version": BACKFILL_VERSION,
        "updated_utc": utc_now(),
        "latest_run_id": run_id,
        "requested_date_count": len(dates),
        "status_counts": counts,
        "all_dates_pass": counts.get("PASS", 0) == len(dates),
        "attempted_this_run": attempted_this_run,
        "skipped_existing_pass_this_run": skipped_pass_this_run,
        "pass_date_count_with_daily_max_difference": len(diffs),
        "daily_max_difference_wu_minus_iem_f_min": min(diffs) if diffs else None,
        "daily_max_difference_wu_minus_iem_f_max": max(diffs) if diffs else None,
        "daily_max_difference_wu_minus_iem_f_negative_date_count": sum(x < 0 for x in diffs),
        "daily_max_difference_wu_minus_iem_f_positive_date_count": sum(x > 0 for x in diffs),
        "daily_max_difference_wu_minus_iem_f_zero_date_count": sum(x == 0 for x in diffs),
        "historical_wu_vintage_limitation": VINTAGE_LIMITATION,
        "original_settlement_time_vintage_reconstructed": False,
        "next_boundary": (
            "data construction only; no M0 inference or economic interpretation is authorized"
        ),
        "guardrail": "no_model_no_probability_no_economics_no_orders",
    }
    _write_json_atomic(output_dir / "backfill_summary.json", summary)
    return summary


def run_backfill(
    *,
    start_date: date,
    end_date: date,
    output_dir: Path,
    chicago_today: date,
    timeout_seconds: float = 20.0,
    inter_date_sleep_seconds: float = 3.0,
) -> dict[str, Any]:
    dates = inclusive_dates(start_date, end_date, today=chicago_today)
    initialize_or_validate_root(
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
        today=chicago_today,
    )

    run_id = _attempt_id()
    run_record = {
        "record_type": "study2_historical_backfill_run",
        "backfill_version": BACKFILL_VERSION,
        "run_id": run_id,
        "started_utc": utc_now(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "date_count": len(dates),
        "timeout_seconds": float(timeout_seconds),
        "inter_date_sleep_seconds": float(inter_date_sleep_seconds),
        "resume_semantics": (
            "existing PASS dates with intact attempt summary and raw-hash audit are skipped; "
            "failed/pending dates receive a new immutable attempt directory"
        ),
    }
    _write_json_atomic(output_dir / "runs" / f"{run_id}.json", run_record)

    attempted = 0
    skipped = 0
    manifest_path = output_dir / "backfill_manifest.jsonl"

    for idx, event_date in enumerate(dates):
        date_dir = output_dir / "dates" / event_date.isoformat()
        existing = _read_json(date_dir / "date_status.json")
        if existing is not None and _pass_status_is_reusable(date_dir, existing):
            skipped += 1
            _append_jsonl(manifest_path, {
                "record_type": "study2_historical_backfill_manifest",
                "run_id": run_id,
                "event_date": event_date.isoformat(),
                "action": "SKIP_EXISTING_PASS",
                "recorded_utc": utc_now(),
            })
            continue

        attempted += 1
        status = backfill_one_date(
            event_date=event_date,
            date_dir=date_dir,
            timeout_seconds=float(timeout_seconds),
        )
        _append_jsonl(manifest_path, {
            "record_type": "study2_historical_backfill_manifest",
            "run_id": run_id,
            "event_date": event_date.isoformat(),
            "action": "ATTEMPT",
            "status": status.get("status"),
            "latest_attempt_id": status.get("latest_attempt_id"),
            "recorded_utc": utc_now(),
        })

        if idx + 1 < len(dates) and inter_date_sleep_seconds > 0:
            time.sleep(float(inter_date_sleep_seconds))

    summary = write_index_and_summary(
        output_dir=output_dir,
        dates=dates,
        run_id=run_id,
        attempted_this_run=attempted,
        skipped_pass_this_run=skipped,
    )
    run_record["completed_utc"] = utc_now()
    run_record["attempted"] = attempted
    run_record["skipped_existing_pass"] = skipped
    run_record["final_status_counts"] = summary["status_counts"]
    _write_json_atomic(output_dir / "runs" / f"{run_id}.json", run_record)
    return summary
