"""Read-only ForecastEx quote capture for V3 Study 2 H0 development."""

from __future__ import annotations

import json
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.v3.audit.ibkr_capability import MARKET_DATA_FIELDS, decode_market_data_availability
from src.v3.ibkr.client import IBKRAPIError, IBKRClient
from src.v3.study1.collector import canonical_hash, sanitize_public_payload
from src.v3.study2.targets import collect_kmdw_target_snapshot
from src.v3.study2.sources import Study2PublicSourceRecorder, Study2SourceError

CAPTURE_VERSION = "v3_s2_h0_capture_3"


@dataclass(frozen=True)
class Study2CaptureConfig:
    cadence_seconds: float = 30.0
    batch_size: int = 8
    tickle_interval_seconds: float = 60.0
    auth_check_interval_seconds: float = 300.0
    snapshot_prime_delay_seconds: float = 0.75
    gap_multiplier: float = 1.75
    terms_timeout_seconds: float = 15.0
    weather_cadence_seconds: float = 60.0
    wu_cadence_seconds: float = 300.0
    public_source_timeout_seconds: float = 15.0
    enable_public_sources: bool = True


@dataclass
class CaptureStats:
    session_id: str
    started_utc: str
    expected_cycles: int = 0
    completed_cycles: int = 0
    quote_records: int = 0
    missing_contract_responses: int = 0
    http_errors: int = 0
    tickle_failures: int = 0
    auth_failures: int = 0
    gaps: int = 0
    max_batch_elapsed_ms: float = 0.0
    delivery_modes: Counter = field(default_factory=Counter)
    iem_fetch_attempts: int = 0
    iem_fetch_successes: int = 0
    iem_fetch_failures: int = 0
    iem_new_observations: int = 0
    wu_fetch_attempts: int = 0
    wu_fetch_successes: int = 0
    wu_fetch_failures: int = 0
    wu_semantic_revisions: int = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        f.flush()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def iter_batches(items: list[int], batch_size: int) -> Iterable[list[int]]:
    size = max(1, int(batch_size))
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _present(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip() not in {"", "-", "--", "None", "null"}


def normalize_quote_item(
    item: dict[str, Any],
    *,
    contract_meta: dict[str, Any],
    session_id: str,
    cycle_id: int,
    batch_id: int,
    request_sent_utc: str,
    response_received_utc: str,
    request_monotonic_ns: int,
    response_monotonic_ns: int,
    batch_payload_sha256: str | None = None,
) -> dict[str, Any]:
    availability = decode_market_data_availability(item.get("6509"))
    fields = {
        "last": item.get("31"),
        "bid": item.get("84"),
        "ask_size": item.get("85"),
        "ask": item.get("86"),
        "volume": item.get("87"),
        "bid_size": item.get("88"),
        "exchange": item.get("6004"),
        "conid_field": item.get("6008"),
        "sec_type": item.get("6070"),
        "market_data_availability": item.get("6509"),
        "last_size": item.get("7059"),
    }
    return {
        "record_type": "study2_kmdw_quote",
        "capture_version": CAPTURE_VERSION,
        "session_id": session_id,
        "cycle_id": cycle_id,
        "batch_id": batch_id,
        "request_sent_utc": request_sent_utc,
        "response_received_utc": response_received_utc,
        "request_monotonic_ns": request_monotonic_ns,
        "response_monotonic_ns": response_monotonic_ns,
        "request_elapsed_ms": (response_monotonic_ns - request_monotonic_ns) / 1_000_000.0,
        "batch_payload_sha256": batch_payload_sha256,
        "conid": item.get("conid"),
        **contract_meta,
        **fields,
        "broker_updated_ms": item.get("_updated"),
        "availability_decoded": asdict(availability),
        "field_presence": {k: _present(v) for k, v in fields.items()},
    }


def _auth_value(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    success = payload.get("success")
    if isinstance(success, dict) and isinstance(success.get("value"), dict):
        return success["value"]
    return payload


def _contract_index(target: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for row in (target.get("ladder") or {}).get("thresholds") or []:
        if not isinstance(row, dict):
            continue
        base = {
            "event_date": target.get("event_date"),
            "station_code": target.get("station_code"),
            "product_code": target.get("product_code"),
            "threshold": row.get("threshold"),
            "payout": row.get("payout"),
            "price_increment": row.get("price_increment"),
        }
        y = row.get("yes_conid")
        n = row.get("no_conid")
        if isinstance(y, int):
            out[y] = {**base, "side": "Y"}
        if isinstance(n, int):
            out[n] = {**base, "side": "N"}
    return out


def run_development_session(
    *,
    client: IBKRClient,
    event_date: date,
    output_dir: Path,
    duration_seconds: float,
    config: Study2CaptureConfig,
) -> dict[str, Any]:
    """Capture KMDW target provenance and the full event-date YES/NO ladder."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if output_dir.exists():
        if not output_dir.is_dir():
            raise RuntimeError(f"session output path exists and is not a directory: {output_dir}")
        if any(output_dir.iterdir()):
            raise RuntimeError(
                f"refusing to reuse non-empty Study 2 session directory: {output_dir}"
            )
    else:
        output_dir.mkdir(parents=True, exist_ok=False)
    session_id = str(uuid.uuid4())
    stats = CaptureStats(session_id=session_id, started_utc=utc_now())

    auth = _auth_value(client.auth_status())
    if not bool(auth.get("authenticated")):
        raise RuntimeError("Gateway reachable but brokerage session is not authenticated")
    client.accounts()
    client.tickle()

    target = collect_kmdw_target_snapshot(
        client,
        event_date=event_date,
        now_epoch=time.time(),
        terms_dir=output_dir / "terms",
        terms_timeout_seconds=config.terms_timeout_seconds,
    )
    target["session_id"] = session_id
    write_json(output_dir / "target_snapshot.json", target)

    contract_index = _contract_index(target)
    conids = [int(x) for x in target.get("quote_conids") or [] if isinstance(x, int)]
    if not conids or set(conids) != set(contract_index):
        raise RuntimeError("target quote conids do not match normalized contract index")
    write_json(output_dir / "contract_index.json", {str(k): v for k, v in contract_index.items()})

    fields = list(MARKET_DATA_FIELDS)
    for batch in iter_batches(conids, config.batch_size):
        client.marketdata_snapshot(batch, fields=fields)
        time.sleep(max(0.0, float(config.snapshot_prime_delay_seconds)))

    quotes_path = output_dir / "quotes.jsonl"
    raw_path = output_dir / "raw_marketdata.jsonl"
    health_path = output_dir / "health.jsonl"
    start_mono = time.monotonic()
    next_due = start_mono
    end_mono = start_mono + float(duration_seconds)
    last_tickle = start_mono
    last_auth = start_mono
    last_cycle_start: float | None = None
    cycle_id = 0
    source_recorder = (
        Study2PublicSourceRecorder(
            output_dir=output_dir,
            event_date=event_date,
            session_id=session_id,
        )
        if config.enable_public_sources
        else None
    )
    next_iem_due = start_mono
    next_wu_due = start_mono

    while time.monotonic() < end_mono:
        now = time.monotonic()
        if now < next_due:
            time.sleep(min(0.5, next_due - now))
            continue
        cycle_start = time.monotonic()
        cycle_id += 1
        stats.expected_cycles += 1

        if last_cycle_start is not None:
            observed_gap = cycle_start - last_cycle_start
            if observed_gap > float(config.cadence_seconds) * float(config.gap_multiplier):
                stats.gaps += 1
                write_jsonl(health_path, {
                    "record_type": "gap",
                    "capture_version": CAPTURE_VERSION,
                    "session_id": session_id,
                    "cycle_id": cycle_id,
                    "detected_utc": utc_now(),
                    "observed_interval_seconds": observed_gap,
                })
        last_cycle_start = cycle_start

        if cycle_start - last_tickle >= config.tickle_interval_seconds:
            try:
                client.tickle()
                write_jsonl(health_path, {
                    "record_type": "tickle", "capture_version": CAPTURE_VERSION,
                    "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(), "ok": True,
                })
            except IBKRAPIError as exc:
                stats.tickle_failures += 1
                write_jsonl(health_path, {
                    "record_type": "tickle", "capture_version": CAPTURE_VERSION,
                    "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                    "ok": False, "error": str(exc),
                })
            last_tickle = cycle_start

        if cycle_start - last_auth >= config.auth_check_interval_seconds:
            try:
                auth_now = _auth_value(client.auth_status())
                authenticated = bool(auth_now.get("authenticated"))
                if not authenticated:
                    stats.auth_failures += 1
                write_jsonl(health_path, {
                    "record_type": "auth_status", "capture_version": CAPTURE_VERSION,
                    "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                    "authenticated": authenticated,
                })
            except IBKRAPIError as exc:
                stats.auth_failures += 1
                write_jsonl(health_path, {
                    "record_type": "auth_status", "capture_version": CAPTURE_VERSION,
                    "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                    "authenticated": False, "error": str(exc),
                })
            last_auth = cycle_start

        seen: set[int] = set()
        for batch_id, batch in enumerate(iter_batches(conids, config.batch_size), start=1):
            sent_utc = utc_now()
            sent_ns = time.monotonic_ns()
            try:
                payload = client.marketdata_snapshot(batch, fields=fields)
                recv_ns = time.monotonic_ns()
                recv_utc = utc_now()
                stats.max_batch_elapsed_ms = max(
                    stats.max_batch_elapsed_ms,
                    (recv_ns - sent_ns) / 1_000_000.0,
                )
                safe_payload = sanitize_public_payload(payload)
                batch_sha = canonical_hash(safe_payload)
                write_jsonl(raw_path, {
                    "record_type": "study2_raw_marketdata_batch",
                    "capture_version": CAPTURE_VERSION,
                    "session_id": session_id,
                    "cycle_id": cycle_id,
                    "batch_id": batch_id,
                    "request_sent_utc": sent_utc,
                    "response_received_utc": recv_utc,
                    "request_monotonic_ns": sent_ns,
                    "response_monotonic_ns": recv_ns,
                    "requested_conids": batch,
                    "payload_sha256": batch_sha,
                    "payload": safe_payload,
                })
                rows = payload if isinstance(payload, list) else []
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    conid = item.get("conid")
                    if not isinstance(conid, int) or conid not in contract_index:
                        continue
                    seen.add(conid)
                    rec = normalize_quote_item(
                        item,
                        contract_meta=contract_index[conid],
                        session_id=session_id,
                        cycle_id=cycle_id,
                        batch_id=batch_id,
                        request_sent_utc=sent_utc,
                        response_received_utc=recv_utc,
                        request_monotonic_ns=sent_ns,
                        response_monotonic_ns=recv_ns,
                        batch_payload_sha256=batch_sha,
                    )
                    write_jsonl(quotes_path, rec)
                    stats.quote_records += 1
                    delivery = (rec.get("availability_decoded") or {}).get("delivery")
                    if delivery:
                        stats.delivery_modes[str(delivery)] += 1
            except IBKRAPIError as exc:
                stats.http_errors += 1
                write_jsonl(health_path, {
                    "record_type": "http_error", "capture_version": CAPTURE_VERSION,
                    "session_id": session_id, "cycle_id": cycle_id, "batch_id": batch_id,
                    "utc": utc_now(), "conid_count": len(batch), "error": str(exc),
                })

        missing = [c for c in conids if c not in seen]
        if missing:
            stats.missing_contract_responses += len(missing)
            write_jsonl(health_path, {
                "record_type": "missing_contracts", "capture_version": CAPTURE_VERSION,
                "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                "missing_count": len(missing), "missing_conids": missing,
            })

        stats.completed_cycles += 1

        source_now = time.monotonic()
        if source_recorder is not None and source_now >= next_iem_due:
            stats.iem_fetch_attempts += 1
            try:
                iem_record = source_recorder.capture_iem(
                    timeout_seconds=float(config.public_source_timeout_seconds)
                )
                stats.iem_fetch_successes += 1
                stats.iem_new_observations += int(iem_record.get("new_observations") or 0)
            except Study2SourceError as exc:
                stats.iem_fetch_failures += 1
                write_jsonl(health_path, {
                    "record_type": "iem_source_error",
                    "capture_version": CAPTURE_VERSION,
                    "session_id": session_id,
                    "cycle_id": cycle_id,
                    "utc": utc_now(),
                    "error": str(exc),
                })
            next_iem_due = source_now + max(5.0, float(config.weather_cadence_seconds))

        source_now = time.monotonic()
        if source_recorder is not None and source_now >= next_wu_due:
            stats.wu_fetch_attempts += 1
            try:
                wu_record = source_recorder.capture_wu(
                    timeout_seconds=float(config.public_source_timeout_seconds)
                )
                stats.wu_fetch_successes += 1
                if bool(wu_record.get("semantic_changed_from_previous")):
                    stats.wu_semantic_revisions += 1
            except Study2SourceError as exc:
                stats.wu_fetch_failures += 1
                write_jsonl(health_path, {
                    "record_type": "wu_source_error",
                    "capture_version": CAPTURE_VERSION,
                    "session_id": session_id,
                    "cycle_id": cycle_id,
                    "utc": utc_now(),
                    "error": str(exc),
                })
            next_wu_due = source_now + max(30.0, float(config.wu_cadence_seconds))

        next_due += float(config.cadence_seconds)
        if next_due <= cycle_start:
            next_due = cycle_start + float(config.cadence_seconds)

    summary = {
        **asdict(stats),
        "delivery_modes": dict(stats.delivery_modes),
        "capture_version": CAPTURE_VERSION,
        "event_date": event_date.isoformat(),
        "selected_contract_count": len(conids),
        "ended_utc": utc_now(),
        "guardrail": "PASS:read_only_no_order_submission_no_alpha_or_pnl_computation",
    }
    write_json(output_dir / "session_summary.json", summary)
    return summary
