"""Pre-freeze confirmatory infrastructure for V3 Study 1.

This module is intentionally split from the shakedown collector.  It provides
machine-checkable metadata/date/quote/cost/ledger primitives and a
strategy-blind live acceptance check.  It does not start the 30-date untouched
evaluation by itself.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import socket
import struct
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

from src.v3.audit.ibkr_capability import MARKET_DATA_FIELDS, decode_market_data_availability, find_markets
from src.v3.ibkr.client import IBKRAPIError, IBKRClient
from src.v3.study1.collector import canonical_hash, sanitize_public_payload

CONFIRMATORY_VERSION = "v3_s1_final_freeze_1"


@dataclass(frozen=True)
class ProductSpec:
    city_id: str
    market_name: str
    product_code: str
    station_code: str
    station_timezone: str


PRODUCTS: tuple[ProductSpec, ...] = (
    ProductSpec("NYC", "New York City Daily Temperature High", "UHLGA", "KLGA", "America/New_York"),
    ProductSpec("CHI", "Chicago Daily Temperature High", "UHMDW", "KMDW", "America/Chicago"),
    ProductSpec("DEN", "Denver Daily Temperature High", "UHBKF", "KBKF", "America/Denver"),
)

PRODUCT_BY_CODE = {p.product_code: p for p in PRODUCTS}

QUESTION_DATE_RX = re.compile(r"\bon\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\?", re.IGNORECASE)
QUESTION_THRESHOLD_RX = re.compile(r"\bexceed\s+(-?\d+(?:\.\d+)?)\s*F\b", re.IGNORECASE)


class ConfirmatoryEligibilityError(RuntimeError):
    """Raised when a confirmatory semantic/readiness requirement fails closed."""


class StudyBlockerError(ConfirmatoryEligibilityError):
    """Raised for verified semantic/terms inconsistencies that close the study."""


class QuoteUnavailableError(ConfirmatoryEligibilityError):
    """Raised only after structural quote integrity passes for both legs."""


def _dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or value is None:
        raise ConfirmatoryEligibilityError(f"not a numeric value: {value!r}")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ConfirmatoryEligibilityError(f"invalid numeric value: {value!r}") from exc


def _money_dec(value: Any, *, label: str) -> Decimal:
    if isinstance(value, str):
        value = value.strip().replace("$", "").replace(",", "")
    try:
        out = _dec(value)
    except ConfirmatoryEligibilityError as exc:
        raise StudyBlockerError(f"{label} is not a valid monetary value: {value!r}") from exc
    if not out.is_finite():
        raise StudyBlockerError(f"{label} is not finite: {value!r}")
    return out


def parse_event_question(question: str, spec: ProductSpec) -> dict[str, Any]:
    q = str(question or "").strip()
    if not q:
        raise ConfirmatoryEligibilityError("missing contract question")
    lower = q.lower()
    if "highest temperature" not in lower or "exceed" not in lower:
        raise ConfirmatoryEligibilityError(f"unexpected question predicate for {spec.product_code}")
    if spec.station_code.lower() not in lower:
        raise ConfirmatoryEligibilityError(f"question does not identify expected station {spec.station_code}")
    dm = QUESTION_DATE_RX.search(q)
    tm = QUESTION_THRESHOLD_RX.search(q)
    if not dm or not tm:
        raise ConfirmatoryEligibilityError("question date/threshold could not be parsed")
    event_date = datetime.strptime(dm.group(1), "%B %d, %Y").date()
    threshold = _dec(tm.group(1))
    return {
        "event_date": event_date.isoformat(),
        "threshold": str(threshold.normalize()),
        "station_code": spec.station_code,
        "predicate": "daily_high_exceed",
    }


def verify_last_trade_matches_event_date(last_trade_time: Any, event_date: date, spec: ProductSpec) -> str:
    try:
        epoch = float(last_trade_time)
    except (TypeError, ValueError) as exc:
        raise ConfirmatoryEligibilityError("missing/invalid last_trade_time") from exc
    local_dt = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(ZoneInfo(spec.station_timezone))
    if local_dt.date() != event_date or (local_dt.hour, local_dt.minute) != (23, 59):
        raise ConfirmatoryEligibilityError(
            f"last_trade_time does not map to {event_date.isoformat()} 23:59 in {spec.station_timezone}: {local_dt.isoformat()}"
        )
    return local_dt.isoformat()


def _required(d: dict[str, Any], fields: Iterable[str], *, label: str) -> None:
    missing = [f for f in fields if f not in d or d.get(f) in (None, "")]
    if missing:
        raise ConfirmatoryEligibilityError(f"{label} missing required fields: {missing}")


def _normalized_rules_fingerprint(rules: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    _required(
        rules,
        (
            "source_agency", "data_and_resolution_link", "description", "market_rules_link",
            "payout", "price_increment", "product_code", "last_trade_time", "release_time",
            "payout_time", "exchange_timezone", "threshold",
        ),
        label="rules",
    )
    normalized = {k: rules.get(k) for k in sorted(rules) if k != "threshold"}
    return canonical_hash(normalized), normalized


def validate_threshold_pair_records(
    yes_record: dict[str, Any],
    no_record: dict[str, Any],
    *,
    spec: ProductSpec,
    event_date: date,
) -> dict[str, Any]:
    """Validate same-threshold YES/NO complement structure and semantic metadata."""
    for label, rec in (("YES", yes_record), ("NO", no_record)):
        if not isinstance(rec, dict):
            raise ConfirmatoryEligibilityError(f"{label} record is not an object")
        if "details_error" in rec or "rules_error" in rec:
            raise ConfirmatoryEligibilityError(f"{label} metadata retrieval failed")
        _required(rec, ("conid", "details", "rules"), label=label)

    yd, nd = yes_record["details"], no_record["details"]
    yr, nr = yes_record["rules"], no_record["rules"]
    if not all(isinstance(x, dict) for x in (yd, nd, yr, nr)):
        raise ConfirmatoryEligibilityError("details/rules must be objects")

    _required(yd, ("conid_yes", "conid_no", "question", "side", "strike", "symbol", "market_name", "payout"), label="YES details")
    _required(nd, ("conid_yes", "conid_no", "question", "side", "strike", "symbol", "market_name", "payout"), label="NO details")

    yid, nid = int(yes_record["conid"]), int(no_record["conid"])
    if str(yd.get("side")).upper() != "Y" or str(nd.get("side")).upper() != "N":
        raise ConfirmatoryEligibilityError("YES/NO sides are not complementary")
    if int(yd["conid_yes"]) != yid or int(yd["conid_no"]) != nid:
        raise ConfirmatoryEligibilityError("YES details do not mutually reference the pair")
    if int(nd["conid_yes"]) != yid or int(nd["conid_no"]) != nid:
        raise ConfirmatoryEligibilityError("NO details do not mutually reference the pair")
    if _dec(yd["strike"]) != _dec(nd["strike"]):
        raise ConfirmatoryEligibilityError("YES/NO strike mismatch")
    if str(yd["symbol"]) != spec.product_code or str(nd["symbol"]) != spec.product_code:
        raise ConfirmatoryEligibilityError("product code mismatch")
    if str(yd["market_name"]) != spec.market_name or str(nd["market_name"]) != spec.market_name:
        raise ConfirmatoryEligibilityError("market name mismatch")
    details_yes_payout = _money_dec(yd["payout"], label="YES details payout")
    details_no_payout = _money_dec(nd["payout"], label="NO details payout")
    if details_yes_payout != Decimal("1") or details_no_payout != Decimal("1"):
        raise StudyBlockerError("details payout is not the expected $1.00")

    yq = parse_event_question(str(yd["question"]), spec)
    nq = parse_event_question(str(nd["question"]), spec)
    if yq != nq:
        raise ConfirmatoryEligibilityError("YES/NO question semantics differ")
    if yq["event_date"] != event_date.isoformat():
        raise ConfirmatoryEligibilityError("question event date does not equal requested event date")
    if _dec(yq["threshold"]) != _dec(yd["strike"]):
        raise ConfirmatoryEligibilityError("question threshold does not equal strike")

    yfp, ynorm = _normalized_rules_fingerprint(yr)
    nfp, nnorm = _normalized_rules_fingerprint(nr)
    if yfp != nfp or ynorm != nnorm:
        raise ConfirmatoryEligibilityError("YES/NO rules differ beyond threshold")
    if str(yr.get("product_code")) != spec.product_code or str(nr.get("product_code")) != spec.product_code:
        raise StudyBlockerError("rules product code mismatch")
    if str(yr.get("source_agency")) != "Weather Underground" or str(nr.get("source_agency")) != "Weather Underground":
        raise StudyBlockerError("rules source agency is not Weather Underground")
    if _money_dec(yr.get("payout"), label="YES rules payout") != Decimal("1") or _money_dec(nr.get("payout"), label="NO rules payout") != Decimal("1"):
        raise StudyBlockerError("rules payout is not the expected $1.00")
    if _money_dec(yr.get("price_increment"), label="YES rules price increment") != Decimal("0.01") or _money_dec(nr.get("price_increment"), label="NO rules price increment") != Decimal("0.01"):
        raise StudyBlockerError("rules price increment is not the expected $0.01")
    if _dec(yr.get("threshold")) != _dec(yd["strike"]) or _dec(nr.get("threshold")) != _dec(nd["strike"]):
        raise StudyBlockerError("rules threshold does not equal strike")
    local_last_trade = verify_last_trade_matches_event_date(yr.get("last_trade_time"), event_date, spec)

    return {
        "city_id": spec.city_id,
        "product_code": spec.product_code,
        "event_date": event_date.isoformat(),
        "threshold": str(_dec(yd["strike"]).normalize()),
        "yes_conid": yid,
        "no_conid": nid,
        "semantic_fingerprint_sha256": yfp,
        "last_trade_local": local_last_trade,
        "market_rules_link": yr.get("market_rules_link"),
        "data_and_resolution_link": yr.get("data_and_resolution_link"),
        "source_agency": yr.get("source_agency"),
        "payout": str(details_yes_payout),
        "price_increment": str(_money_dec(yr.get("price_increment"), label="rules price increment")),
        "release_time": yr.get("release_time"),
        "payout_time": yr.get("payout_time"),
    }


def validate_cross_threshold_ladder(thresholds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(thresholds) < 2:
        raise ConfirmatoryEligibilityError("fewer than two eligible thresholds")
    ordered = sorted(thresholds, key=lambda x: _dec(x["threshold"]))
    vals = [_dec(x["threshold"]) for x in ordered]
    if len(set(vals)) != len(vals):
        raise ConfirmatoryEligibilityError("duplicate threshold in ladder")
    base = ordered[0]
    compare_fields = (
        "city_id", "product_code", "event_date", "semantic_fingerprint_sha256",
        "market_rules_link", "data_and_resolution_link", "source_agency", "payout",
        "price_increment", "release_time", "payout_time",
    )
    for row in ordered[1:]:
        for field in compare_fields:
            if row.get(field) != base.get(field):
                raise ConfirmatoryEligibilityError(f"cross-threshold semantic mismatch: {field}")
    pairs = []
    for low, high in zip(ordered[:-1], ordered[1:]):
        pairs.append({
            "city_id": low["city_id"],
            "event_date": low["event_date"],
            "lower_threshold": low["threshold"],
            "higher_threshold": high["threshold"],
            "lower_yes_conid": low["yes_conid"],
            "higher_no_conid": high["no_conid"],
        })
    return pairs


def discover_fixed_markets(client: IBKRClient) -> dict[str, dict[str, Any]]:
    tree = client.category_tree()
    _, matches = find_markets(tree, r"(?i)(temperature.*high|high.*temperature)")
    by_symbol = {str(x.get("symbol")): x for x in matches if x.get("symbol")}
    out: dict[str, dict[str, Any]] = {}
    for spec in PRODUCTS:
        item = by_symbol.get(spec.product_code)
        if not item or not isinstance(item.get("conid"), int):
            raise ConfirmatoryEligibilityError(f"fixed product not found: {spec.product_code}")
        payload = client.forecast_market(int(item["conid"]), exchange=str(item.get("exchange") or "FORECASTX"))
        if not isinstance(payload, dict):
            raise ConfirmatoryEligibilityError(f"invalid market payload: {spec.product_code}")
        out[spec.city_id] = {"discovery": sanitize_public_payload(item), "market": sanitize_public_payload(payload)}
    return out


def acquire_event_ladder(client: IBKRClient, spec: ProductSpec, market_payload: dict[str, Any], event_date: date) -> dict[str, Any]:
    contracts = market_payload.get("contracts") or []
    if not isinstance(contracts, list) or not contracts:
        raise ConfirmatoryEligibilityError("contracts payload is not a non-empty list")

    # Every listed contract must be explicitly classified by strict question
    # semantics.  A contract that cannot be classified is a study blocker: it
    # must never be silently dropped before adjacency is reconstructed.
    grouped: dict[Decimal, dict[str, dict[str, Any]]] = {}
    archived: list[dict[str, Any]] = []
    for c in contracts:
        if not isinstance(c, dict) or not isinstance(c.get("conid"), int):
            raise StudyBlockerError("listed contract is missing an integer conid")
        conid = int(c["conid"])
        try:
            details = sanitize_public_payload(client.contract_details(conid))
        except IBKRAPIError as exc:
            raise ConfirmatoryEligibilityError(f"details retrieval failed for listed contract {conid}: {exc}") from exc
        if not isinstance(details, dict):
            raise ConfirmatoryEligibilityError(f"details payload is not an object for listed contract {conid}")
        try:
            parsed = parse_event_question(str(details.get("question") or ""), spec)
        except ConfirmatoryEligibilityError as exc:
            raise StudyBlockerError(f"listed contract {conid} cannot be classified by question semantics: {exc}") from exc

        rec: dict[str, Any] = {
            "conid": conid,
            "details": details,
            "details_sha256": canonical_hash(details),
            "parsed_question": parsed,
            "disposition": "TARGET_EVENT_DATE" if parsed["event_date"] == event_date.isoformat() else "OTHER_EVENT_DATE",
        }
        archived.append(rec)
        if rec["disposition"] != "TARGET_EVENT_DATE":
            continue

        try:
            rules = sanitize_public_payload(client.contract_rules(conid))
        except IBKRAPIError as exc:
            raise ConfirmatoryEligibilityError(f"rules retrieval failed for event-date contract {conid}: {exc}") from exc
        if not isinstance(rules, dict):
            raise ConfirmatoryEligibilityError(f"rules payload is not an object for event-date contract {conid}")
        rec["rules"] = rules
        rec["rules_sha256"] = canonical_hash(rules)

        strike = _dec(details.get("strike"))
        side = str(details.get("side") or "").upper()
        if side not in {"Y", "N"}:
            raise StudyBlockerError(f"unexpected side for event-date contract {conid}: {side}")
        if side in grouped.setdefault(strike, {}):
            raise StudyBlockerError(f"duplicate {side} contract at threshold {strike}")
        grouped[strike][side] = rec

    if not grouped:
        raise ConfirmatoryEligibilityError(f"no contracts mapped to event date {event_date.isoformat()} for {spec.product_code}")

    thresholds: list[dict[str, Any]] = []
    for strike in sorted(grouped):
        sides = grouped[strike]
        if set(sides) != {"Y", "N"}:
            raise StudyBlockerError(f"incomplete YES/NO threshold {strike} for {spec.product_code}")
        try:
            thresholds.append(validate_threshold_pair_records(sides["Y"], sides["N"], spec=spec, event_date=event_date))
        except StudyBlockerError:
            raise
        except ConfirmatoryEligibilityError as exc:
            raise StudyBlockerError(f"semantic validation failed at threshold {strike}: {exc}") from exc

    try:
        adjacent_pairs = validate_cross_threshold_ladder(thresholds)
    except ConfirmatoryEligibilityError as exc:
        raise StudyBlockerError(f"cross-threshold semantic validation failed: {exc}") from exc
    return {
        "spec": spec.__dict__,
        "event_date": event_date.isoformat(),
        "listed_contract_count": len(contracts),
        "classified_contract_count": len(archived),
        "target_event_contract_count": sum(1 for r in archived if r["disposition"] == "TARGET_EVENT_DATE"),
        "excluded_other_date_contract_count": sum(1 for r in archived if r["disposition"] == "OTHER_EVENT_DATE"),
        "thresholds": thresholds,
        "adjacent_pairs": adjacent_pairs,
        "archived_contract_metadata": archived,
    }



def validate_schedule_open(schedule: Any, *, now_epoch: float) -> dict[str, Any]:
    if not isinstance(schedule, dict):
        raise ConfirmatoryEligibilityError("missing trading schedule")
    tz_name = str(schedule.get("timezone") or "")
    entries = schedule.get("trading_schedules")
    if not tz_name or not isinstance(entries, list):
        raise ConfirmatoryEligibilityError("schedule missing timezone/trading_schedules")
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise ConfirmatoryEligibilityError(f"invalid schedule timezone: {tz_name}") from exc
    now_local = datetime.fromtimestamp(now_epoch, tz=timezone.utc).astimezone(tz)
    day_name = now_local.strftime("%A")
    day_rows = [x for x in entries if isinstance(x, dict) and str(x.get("day_of_week")) == day_name]
    if len(day_rows) != 1:
        raise ConfirmatoryEligibilityError(f"schedule missing/ambiguous weekday row: {day_name}")
    times = day_rows[0].get("trading_times")
    if not isinstance(times, list) or not times:
        raise ConfirmatoryEligibilityError(f"no trading intervals for {day_name}")
    intervals = []
    is_open = False
    for rec in times:
        if not isinstance(rec, dict) or not rec.get("open") or not rec.get("close"):
            raise ConfirmatoryEligibilityError("malformed trading interval")
        try:
            ot = datetime.strptime(str(rec["open"]), "%I:%M %p").time()
            ct = datetime.strptime(str(rec["close"]), "%I:%M %p").time()
        except ValueError as exc:
            raise ConfirmatoryEligibilityError("unparseable trading interval") from exc
        start = datetime.combine(now_local.date(), ot, tzinfo=tz)
        end = datetime.combine(now_local.date(), ct, tzinfo=tz)
        if end < start:
            end += timedelta(days=1)
        # Treat published close as the start of a closed interval; this fails
        # conservatively across one-minute maintenance breaks such as 4:15-4:16.
        end_exclusive = end
        intervals.append({"open": start.isoformat(), "close_exclusive": end_exclusive.isoformat()})
        if start <= now_local < end_exclusive:
            is_open = True
    if not is_open:
        raise ConfirmatoryEligibilityError(f"market schedule closed at {now_local.isoformat()}")
    return {"timezone": tz_name, "now_local": now_local.isoformat(), "intervals": intervals, "open": True}


@dataclass
class RevalidationTracker:
    """State machine for two consecutive nominal-slot observations.

    The tracker contains no cost or profitability logic. Any invalid/intervening
    observation clears the pending first observation.
    """
    pending: dict[str, tuple[int, float, Any]]

    def __init__(self) -> None:
        self.pending = {}

    def observe(self, pair_id: str, *, slot_index: int, request_start_epoch: float, valid: bool, payload: Any) -> tuple[str, Any | None]:
        if not valid:
            self.pending.pop(pair_id, None)
            return "INVALID_RESET", None
        old = self.pending.get(pair_id)
        if old is None:
            self.pending[pair_id] = (slot_index, request_start_epoch, payload)
            return "PENDING_FIRST", None
        old_slot, old_time, old_payload = old
        delta = request_start_epoch - old_time
        if slot_index != old_slot + 1 or delta < 25.0 or delta > 35.0:
            self.pending[pair_id] = (slot_index, request_start_epoch, payload)
            return "RESET_NEW_FIRST", None
        self.pending.pop(pair_id, None)
        return "CONFIRMED_TWO_POLL", (old_payload, payload)


def build_date_ledger(start_date: date, count: int = 30) -> list[dict[str, Any]]:
    return [{"date": d, "planned": True, "status": "PENDING", "in_primary_denominator": True}
            for d in planned_dates(start_date, count)]

def archive_terms(url: str, output_dir: Path, *, timeout_seconds: float = 15.0) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, timeout=timeout_seconds)
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF"):
        raise ConfirmatoryEligibilityError("terms resource is not a PDF")
    sha = hashlib.sha256(content).hexdigest()
    path = output_dir / f"forecast_terms_{sha[:12]}.pdf"
    path.write_bytes(content)
    return {"url": url, "sha256": sha, "bytes": len(content), "file": path.name}


def verify_terms_archive(record: dict[str, Any], *, expected_url: str, expected_sha256: str) -> None:
    if str(record.get("url")) != str(expected_url):
        raise StudyBlockerError("contract terms URL differs from frozen terms URL")
    if str(record.get("sha256")) != str(expected_sha256):
        raise StudyBlockerError("contract terms content hash differs from frozen audited terms")


def _quote_decimal(value: Any, *, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise QuoteUnavailableError(f"{label} unavailable: {value!r}")
    try:
        x = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise QuoteUnavailableError(f"{label} unavailable: {value!r}") from exc
    if not x.is_finite():
        raise QuoteUnavailableError(f"{label} unavailable: {value!r}")
    return x


def _numeric_ask(value: Any) -> Decimal:
    x = _quote_decimal(value, label="ask")
    if x == 0 or x == 1:
        raise QuoteUnavailableError(f"ask is not buyable in $0.01-$0.99 range: {x}")
    if x < 0 or x > 1:
        raise ConfirmatoryEligibilityError(f"ask outside [0,1]: {x}")
    cents = x * Decimal("100")
    if cents != cents.to_integral_value():
        raise ConfirmatoryEligibilityError(f"ask not on $0.01 tick: {x}")
    return x


def _positive_integer_size(value: Any) -> int:
    x = _quote_decimal(value, label="ask size")
    if x < 0 or x != x.to_integral_value():
        raise ConfirmatoryEligibilityError(f"ask size is malformed: {value!r}")
    if x < 1:
        raise QuoteUnavailableError(f"ask size unavailable: {value!r}")
    return int(x)


def validate_pair_snapshot(
    payload: Any,
    *,
    expected_conids: tuple[int, int],
    request_elapsed_seconds: float,
    response_received_epoch: float,
    max_request_elapsed_seconds: float = 5.0,
    broker_age_diagnostic_seconds: float = 60.0,
    max_broker_future_seconds: float = 1.0,
    pair_broker_skew_diagnostic_seconds: float = 5.0,
    minimum_valid_broker_epoch_ms: int = 946684800000,
) -> dict[str, Any]:
    """Validate one same-request pair snapshot with structural errors prioritized.

    Response shape, both-leg delivery, both-leg broker timestamp schema, future
    bounds and conid integrity are checked *before* ordinary quote availability.
    Missing/non-buyable asks or sizes therefore cannot mask a hard error on the
    other leg.  Old ``_updated`` age and cross-leg skew remain diagnostics only.
    """
    try:
        elapsed = float(request_elapsed_seconds)
        received = float(response_received_epoch)
    except (TypeError, ValueError) as exc:
        raise ConfirmatoryEligibilityError("invalid request/response timing") from exc
    if not math.isfinite(elapsed) or elapsed < 0 or elapsed > max_request_elapsed_seconds:
        raise ConfirmatoryEligibilityError("request elapsed outside frozen bound")
    if not math.isfinite(received) or received <= 0:
        raise ConfirmatoryEligibilityError("invalid response received epoch")
    if not isinstance(payload, list) or len(payload) != 2:
        raise ConfirmatoryEligibilityError("pair response must contain exactly two rows")

    by_conid: dict[int, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("conid"), int):
            raise ConfirmatoryEligibilityError("invalid quote row/conid")
        conid = int(item["conid"])
        if conid in by_conid:
            raise ConfirmatoryEligibilityError("duplicate conid in pair response")
        if conid not in expected_conids:
            raise ConfirmatoryEligibilityError("unexpected conid in pair response")
        by_conid[conid] = item
    if set(by_conid) != set(expected_conids):
        raise ConfirmatoryEligibilityError("missing expected conid in pair response")

    # Phase 1: hard structural integrity for both legs.
    structural: dict[int, dict[str, Any]] = {}
    broker_times: list[float] = []
    for conid in expected_conids:
        item = by_conid[conid]
        delivery = decode_market_data_availability(item.get("6509")).delivery
        if delivery != "real_time":
            raise ConfirmatoryEligibilityError(f"non-real-time delivery for {conid}: {delivery}")
        try:
            updated_ms = int(item.get("_updated"))
        except (TypeError, ValueError) as exc:
            raise ConfirmatoryEligibilityError(f"missing/invalid broker _updated for {conid}") from exc
        if updated_ms < int(minimum_valid_broker_epoch_ms):
            raise ConfirmatoryEligibilityError(f"broker _updated epoch is invalid for {conid}: {updated_ms}")
        updated_s = updated_ms / 1000.0
        age = received - updated_s
        if age < -max_broker_future_seconds:
            raise ConfirmatoryEligibilityError(f"broker _updated timestamp is implausibly future for {conid}: {age:.3f}s")
        structural[conid] = {
            "delivery": delivery,
            "availability": str(item.get("6509")),
            "broker_updated_ms": updated_ms,
            "broker_age_seconds": age,
            "broker_age_diagnostic_exceeds_reference": age > broker_age_diagnostic_seconds,
        }
        broker_times.append(updated_s)

    # Phase 2: quote availability/schema.  Quote-unavailable errors are collected
    # only after both legs have passed structural integrity.
    rows: list[dict[str, Any]] = []
    quote_errors: list[str] = []
    for conid in expected_conids:
        item = by_conid[conid]
        try:
            ask = _numeric_ask(item.get("86"))
            ask_size = _positive_integer_size(item.get("85"))
        except QuoteUnavailableError as exc:
            quote_errors.append(f"{conid}:{exc}")
            continue
        row = {"conid": conid, "ask": str(ask), "ask_size": ask_size, **structural[conid]}
        rows.append(row)
    if quote_errors:
        raise QuoteUnavailableError("; ".join(quote_errors))

    pair_skew = max(broker_times) - min(broker_times)
    return {
        "rows": rows,
        "request_elapsed_seconds": elapsed,
        "pair_broker_skew_seconds": pair_skew,
        "pair_broker_skew_diagnostic_exceeds_reference": pair_skew > pair_broker_skew_diagnostic_seconds,
    }


def snapshot_failure_class(exc: Exception) -> str:
    """Classify quote unavailability only after hard integrity has passed."""
    return "quote_unavailable" if isinstance(exc, QuoteUnavailableError) else "structural_failure"


def ntp_offset_seconds(host: str, *, timeout_seconds: float = 3.0) -> float:
    """Small RFC-5905 style offset estimate using one unauthenticated NTP query."""
    packet = bytearray(48)
    packet[0] = 0x1B
    addr = (host, 123)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout_seconds)
        t1 = time.time()
        s.sendto(packet, addr)
        data, _ = s.recvfrom(512)
        t4 = time.time()
    if len(data) < 48:
        raise ConfirmatoryEligibilityError("short NTP response")
    sec, frac = struct.unpack("!II", data[40:48])
    t3 = sec - 2208988800 + frac / 2**32
    # With only server transmit time available, midpoint is a conservative
    # approximation for operational clock-health screening.
    return t3 - ((t1 + t4) / 2.0)


def best_ntp_offset(hosts: Iterable[str] = ("time.google.com", "time.cloudflare.com", "time.apple.com")) -> dict[str, Any]:
    errors = []
    for host in hosts:
        try:
            offset = ntp_offset_seconds(host)
            return {"host": host, "offset_seconds": offset, "ok": abs(offset) <= 1.0}
        except Exception as exc:  # strategy-blind operational fallback only
            errors.append(f"{host}:{type(exc).__name__}")
    return {"host": None, "offset_seconds": None, "ok": False, "errors": errors}


def conservative_cost(
    *,
    lower_ask_t1: Any,
    lower_ask_t2: Any,
    higher_no_ask_t1: Any,
    higher_no_ask_t2: Any,
    broker_fee_per_contract: Any,
    exchange_fee_per_contract: Any,
    tick_reserve_per_leg: Any,
    annual_funding_rate: Any,
    seconds_to_payout: float,
) -> dict[str, Decimal]:
    lower = max(_dec(lower_ask_t1), _dec(lower_ask_t2))
    higher = max(_dec(higher_no_ask_t1), _dec(higher_no_ask_t2))
    broker = _dec(broker_fee_per_contract) * 2
    exchange = _dec(exchange_fee_per_contract) * 2
    ticks = _dec(tick_reserve_per_leg) * 2
    c0 = lower + higher + broker + exchange + ticks
    rate = _dec(annual_funding_rate)
    funding = c0 * rate * Decimal(str(max(0.0, seconds_to_payout))) / Decimal(str(365 * 86400))
    total_raw = c0 + funding
    total_cents = (total_raw * Decimal("100")).to_integral_value(rounding=ROUND_CEILING) / Decimal("100")
    return {"lower_leg": lower, "higher_no_leg": higher, "fees": broker + exchange,
            "tick_reserve": ticks, "funding": funding, "total_raw": total_raw, "total_rounded": total_cents}


def planned_dates(start_date: date, count: int = 30) -> list[str]:
    if count <= 0:
        raise ValueError("count must be positive")
    return [(start_date + timedelta(days=i)).isoformat() for i in range(count)]


def classify_date_health(*, normal_slots: int, total_slots: int = 960, max_consecutive_invalid: int = 2,
                         total_invalid: int | None = None, terminal_failure: bool = False) -> str:
    invalid = (total_slots - normal_slots) if total_invalid is None else total_invalid
    if terminal_failure or normal_slots < 951 or invalid > 9 or max_consecutive_invalid >= 3:
        return "ABORTED_RETAIN_IN_DENOMINATOR"
    return "VALID"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
