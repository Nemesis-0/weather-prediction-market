"""Read-only KMDW target discovery and semantic provenance for V3 Study 2 H0."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import time
from typing import Any
from zoneinfo import ZoneInfo

from src.v3.audit.ibkr_capability import find_markets
from src.v3.ibkr.client import IBKRAPIError, IBKRClient
from src.v3.study1.collector import canonical_hash, sanitize_public_payload
from src.v3.study1.confirmatory import (
    ConfirmatoryEligibilityError,
    PRODUCT_BY_CODE,
    acquire_event_ladder,
    archive_terms,
    validate_schedule_open,
)

TARGETS_VERSION = "v3_s2_h0_targets_1"
KMDW_PRODUCT_CODE = "UHMDW"
KMDW_STATION_CODE = "KMDW"
KMDW_MARKET_NAME = "Chicago Daily Temperature High"
KMDW_TIMEZONE = "America/Chicago"
KMDW_SPEC = PRODUCT_BY_CODE[KMDW_PRODUCT_CODE]


class Study2TargetError(RuntimeError):
    """Raised when the current KMDW target cannot be identified unambiguously."""


def chicago_local_date(now: datetime | None = None) -> date:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(ZoneInfo(KMDW_TIMEZONE)).date()


def discover_kmdw_market(client: IBKRClient) -> dict[str, Any]:
    tree = client.category_tree()
    total, matches = find_markets(tree, r"(?i)(temperature.*high|high.*temperature)")
    candidates = [m for m in matches if str(m.get("symbol") or "") == KMDW_PRODUCT_CODE]
    if len(candidates) != 1:
        raise Study2TargetError(
            f"expected exactly one {KMDW_PRODUCT_CODE} market, found {len(candidates)}"
        )
    discovery = candidates[0]
    conid = discovery.get("conid")
    if not isinstance(conid, int):
        raise Study2TargetError("KMDW market discovery did not contain an integer conid")
    try:
        raw_market = client.forecast_market(
            conid,
            exchange=str(discovery.get("exchange") or "FORECASTX"),
        )
    except IBKRAPIError as exc:
        raise Study2TargetError(f"KMDW market retrieval failed: {exc}") from exc
    if not isinstance(raw_market, dict):
        raise Study2TargetError("KMDW market payload is not an object")
    market_name = str(raw_market.get("market_name") or discovery.get("name") or "")
    if market_name != KMDW_MARKET_NAME:
        raise Study2TargetError(
            f"unexpected KMDW market name: {market_name!r}; expected {KMDW_MARKET_NAME!r}"
        )
    return {
        "targets_version": TARGETS_VERSION,
        "total_forecastex_markets": total,
        "discovery": sanitize_public_payload(discovery),
        "market": sanitize_public_payload(raw_market),
        "_raw_market": raw_market,
    }


def _quote_conids(ladder: dict[str, Any]) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for row in ladder.get("thresholds") or []:
        if not isinstance(row, dict):
            continue
        for key in ("yes_conid", "no_conid"):
            value = row.get(key)
            if isinstance(value, int) and value not in seen:
                seen.add(value)
                out.append(value)
    return out


def collect_kmdw_target_snapshot(
    client: IBKRClient,
    *,
    event_date: date,
    now_epoch: float | None = None,
    terms_dir: Path | None = None,
    terms_timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Resolve one KMDW event-date ladder and archive public semantic context.

    This function is deliberately read-only.  Terms-download failure is recorded
    rather than converted into an order/trading decision; the H0 acceptance audit
    decides whether the provenance is sufficient.
    """
    discovered = discover_kmdw_market(client)
    raw_market = discovered.pop("_raw_market")
    try:
        ladder = acquire_event_ladder(client, KMDW_SPEC, raw_market, event_date)
    except ConfirmatoryEligibilityError as exc:
        raise Study2TargetError(f"KMDW event ladder failed semantic validation: {exc}") from exc

    conids = _quote_conids(ladder)
    if len(conids) < 2:
        raise Study2TargetError("KMDW event ladder produced fewer than two quote conids")

    representative = conids[len(conids) // 2]
    try:
        schedule = sanitize_public_payload(client.contract_schedules(representative))
    except IBKRAPIError as exc:
        raise Study2TargetError(f"KMDW schedule retrieval failed: {exc}") from exc
    if not isinstance(schedule, dict):
        raise Study2TargetError("KMDW schedule payload is not an object")

    epoch = float(time.time() if now_epoch is None else now_epoch)
    try:
        schedule_status = validate_schedule_open(schedule, now_epoch=epoch)
    except ConfirmatoryEligibilityError as exc:
        schedule_status = {
            "open": False,
            "checked_epoch": epoch,
            "reason": str(exc),
        }

    thresholds = ladder.get("thresholds") or []
    first = thresholds[0] if thresholds and isinstance(thresholds[0], dict) else {}
    terms_url = first.get("market_rules_link")
    terms_record: dict[str, Any] = {
        "attempted": terms_dir is not None,
        "url": terms_url,
    }
    if terms_dir is not None:
        if not terms_url:
            terms_record.update({"ok": False, "error": "missing market_rules_link"})
        else:
            try:
                archived = archive_terms(
                    str(terms_url),
                    terms_dir,
                    timeout_seconds=float(terms_timeout_seconds),
                )
                terms_record.update({"ok": True, **archived})
            except Exception as exc:  # recorded provenance failure; no trading action follows
                terms_record.update({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    return {
        "record_type": "study2_target_snapshot",
        "targets_version": TARGETS_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "event_date": event_date.isoformat(),
        "station_code": KMDW_STATION_CODE,
        "station_timezone": KMDW_TIMEZONE,
        "product_code": KMDW_PRODUCT_CODE,
        "market_name": KMDW_MARKET_NAME,
        "discovery": discovered,
        "ladder": ladder,
        "quote_conids": conids,
        "schedule": schedule,
        "schedule_sha256": canonical_hash(schedule),
        "schedule_status": schedule_status,
        "terms_archive": terms_record,
        "guardrail": "read_only_target_provenance_no_order_submission",
    }
