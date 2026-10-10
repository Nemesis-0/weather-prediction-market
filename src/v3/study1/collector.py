"""Strategy-blind shakedown collector for V3 Study 1.

This module intentionally does NOT compute structural basket costs, opportunity
flags, alpha, or PnL. It collects only the operational evidence needed to freeze
an eventual prospective protocol.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.v3.audit.ibkr_capability import MARKET_DATA_FIELDS, decode_market_data_availability, find_markets
from src.v3.ibkr.client import IBKRAPIError, IBKRClient

COLLECTOR_VERSION = "v3_s1_shakedown_3"
SENSITIVE_KEY_RX = re.compile(r"(?i)(account|acct|username|user_name|password|passwd|token|session|cookie|secret|tax|passport)")


@dataclass(frozen=True)
class ShakedownConfig:
    base_url: str = "https://localhost:5001/v1/api"
    market_name_pattern: str = r"(?i)(temperature.*high|high.*temperature)"
    provisional_cadence_seconds: float = 30.0
    tickle_interval_seconds: float = 60.0
    auth_check_interval_seconds: float = 300.0
    batch_size: int = 8
    max_markets_per_session: int = 24
    contracts_per_market: int = 8
    rotation_modulus: int = 3
    snapshot_prime_delay_seconds: float = 0.75
    gap_multiplier: float = 1.75
    rule_audit_contract_limit: int = 0  # 0 = auto: one complete YES/NO pair per selected market


@dataclass
class SessionStats:
    started_utc: str
    session_id: str
    expected_cycles: int = 0
    completed_cycles: int = 0
    quote_records: int = 0
    complete_bbo_records: int = 0
    full_bbo_size_records: int = 0
    missing_contract_responses: int = 0
    http_errors: int = 0
    tickle_failures: int = 0
    auth_failures: int = 0
    gaps: int = 0
    max_cycle_elapsed_ms: float = 0.0
    max_batch_elapsed_ms: float = 0.0
    availability_values: Counter = field(default_factory=Counter)
    delivery_modes: Counter = field(default_factory=Counter)
    market_quote_records: Counter = field(default_factory=Counter)
    market_complete_bbo_records: Counter = field(default_factory=Counter)
    market_full_bbo_size_records: Counter = field(default_factory=Counter)
    market_broker_update_changes: Counter = field(default_factory=Counter)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sanitize_public_payload(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            key = str(k)
            if SENSITIVE_KEY_RX.search(key):
                continue
            out[key] = sanitize_public_payload(v)
        return out
    if isinstance(obj, list):
        return [sanitize_public_payload(x) for x in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def safe_market_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"market": {}, "contracts": []}
    market = {k: payload.get(k) for k in (
        "market_name", "exchange", "symbol", "payout", "exclude_historical_data",
        "underlying_conid", "description", "measured_period", "expiration"
    ) if k in payload}
    contracts = []
    for c in payload.get("contracts") or []:
        if not isinstance(c, dict):
            continue
        contracts.append({k: c.get(k) for k in (
            "conid", "side", "strike", "strike_label", "expiration", "underlying_conid",
            "right", "exchange", "symbol"
        ) if k in c})
    contracts.sort(key=lambda x: (
        str(x.get("expiration")),
        str(x.get("strike_label") if x.get("strike_label") is not None else x.get("strike")),
        str(x.get("side")), str(x.get("conid"))
    ))
    return {"market": market, "contracts": contracts}


def discover_candidate_universe(client: IBKRClient, *, pattern: str) -> dict[str, Any]:
    tree = client.category_tree()
    total, matches = find_markets(tree, pattern)
    markets: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for item in matches:
        conid = item.get("conid")
        if not isinstance(conid, int):
            continue
        try:
            payload = client.forecast_market(conid, exchange=str(item.get("exchange") or "FORECASTX"))
            safe = safe_market_payload(payload)
            safe["discovery"] = {k: item.get(k) for k in ("name", "symbol", "exchange", "conid", "category_name") if k in item}
            markets.append(safe)
        except IBKRAPIError as exc:
            errors.append({"underlying_conid": conid, "error": str(exc)})
    markets.sort(key=lambda x: (
        str((x.get("market") or {}).get("market_name") or (x.get("discovery") or {}).get("name")),
        str((x.get("market") or {}).get("symbol"))
    ))
    return {
        "collector_version": COLLECTOR_VERSION,
        "created_utc": utc_now(),
        "pattern": pattern,
        "total_forecastex_markets": total,
        "matching_market_count": len(matches),
        "markets": markets,
        "errors": errors,
    }


def rotate_markets(markets: list[dict[str, Any]], *, rotation_index: int, rotation_modulus: int, max_markets: int) -> list[dict[str, Any]]:
    modulus = max(1, int(rotation_modulus))
    idx = int(rotation_index) % modulus
    selected = [m for i, m in enumerate(markets) if i % modulus == idx]
    return selected[:max(1, int(max_markets))]


def _pair_key(contract: dict[str, Any]) -> tuple[str, str]:
    expiration = str(contract.get("expiration") or "")
    strike = contract.get("strike")
    strike_label = contract.get("strike_label")
    return expiration, str(strike if strike is not None else strike_label)


def _threshold_sort_key(pair: dict[str, Any]) -> tuple[int, float | str]:
    strike = pair.get("strike")
    if isinstance(strike, (int, float)):
        return (0, float(strike))
    try:
        return (0, float(str(strike)))
    except (TypeError, ValueError):
        return (1, str(pair.get("strike_label") or strike or ""))


def _evenly_spaced_indices(n: int, k: int) -> list[int]:
    if n <= 0 or k <= 0:
        return []
    if k >= n:
        return list(range(n))
    if k == 1:
        return [n // 2]
    return [round(i * (n - 1) / (k - 1)) for i in range(k)]


def resolve_active_expiration(client: IBKRClient, contracts: list[dict[str, Any]], *, now_epoch: float) -> tuple[str | None, list[dict[str, Any]]]:
    """Choose the nearest still-tradable expiration using public rule metadata only."""
    reps: dict[str, int] = {}
    for c in contracts:
        expiration = str(c.get("expiration") or "")
        conid = c.get("conid")
        if expiration and isinstance(conid, int):
            reps.setdefault(expiration, conid)
    evidence: list[dict[str, Any]] = []
    active: list[tuple[int, str]] = []
    for expiration in sorted(reps):
        conid = reps[expiration]
        rec: dict[str, Any] = {"expiration": expiration, "representative_conid": conid}
        try:
            rules = sanitize_public_payload(client.contract_rules(conid))
            last_trade = rules.get("last_trade_time") if isinstance(rules, dict) else None
            rec["last_trade_time"] = last_trade
            rec["rules_sha256"] = canonical_hash(rules)
            if isinstance(last_trade, (int, float)) and float(last_trade) > now_epoch:
                active.append((int(last_trade), expiration))
        except IBKRAPIError as exc:
            rec["rules_error"] = str(exc)
        evidence.append(rec)
    if not active:
        return None, evidence
    active.sort()
    return active[0][1], evidence


def select_strategy_blind_contracts(contracts: list[dict[str, Any]], *, expiration: str, contracts_per_market: int) -> list[dict[str, Any]]:
    """Select complete YES/NO pairs across an already-verified active expiration.

    The selection is price-blind and spreads thresholds across the ladder so
    shakedown feed coverage is not concentrated at one end of the chain.
    """
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for c in contracts:
        if not isinstance(c, dict) or str(c.get("expiration") or "") != str(expiration):
            continue
        key = _pair_key(c)
        rec = grouped.setdefault(key, {
            "expiration": c.get("expiration"), "strike": c.get("strike"),
            "strike_label": c.get("strike_label"), "Y": None, "N": None,
        })
        side = str(c.get("side") or "").upper()
        if side in {"Y", "N"}:
            rec[side] = c
    pairs = [x for x in grouped.values() if isinstance(x.get("Y"), dict) and isinstance(x.get("N"), dict)]
    pairs.sort(key=_threshold_sort_key)
    pair_budget = max(1, int(contracts_per_market) // 2)
    selected: list[dict[str, Any]] = []
    for i in _evenly_spaced_indices(len(pairs), min(pair_budget, len(pairs))):
        pair = pairs[i]
        selected.extend([pair["Y"], pair["N"]])
    return selected


def build_contract_index(selected_markets: list[dict[str, Any]], *, active_expirations: dict[str, str], contracts_per_market: int) -> tuple[dict[int, dict[str, Any]], list[int]]:
    index: dict[int, dict[str, Any]] = {}
    ordered: list[int] = []
    for m in selected_markets:
        market_meta = m.get("market") or {}
        discovery = m.get("discovery") or {}
        market_name = market_meta.get("market_name") or discovery.get("name")
        expiration = active_expirations.get(str(market_name))
        if not expiration:
            continue
        chosen = select_strategy_blind_contracts(m.get("contracts") or [], expiration=expiration, contracts_per_market=contracts_per_market)
        for c in chosen:
            conid = c.get("conid")
            if not isinstance(conid, int) or conid in index:
                continue
            index[conid] = {
                "market_name": market_name,
                "market_symbol": market_meta.get("symbol") or discovery.get("symbol"),
                "market_exchange": market_meta.get("exchange") or discovery.get("exchange") or "FORECASTX",
                "underlying_conid": c.get("underlying_conid") or discovery.get("conid"),
                "side": c.get("side"), "strike": c.get("strike"), "strike_label": c.get("strike_label"),
                "expiration": c.get("expiration"),
                "shakedown_contract_selection": "nearest_still_tradable_expiration_evenly_spaced_complete_yes_no_pairs",
            }
            ordered.append(conid)
    return index, ordered


def select_rule_audit_conids(selected_conids: list[int], contract_index: dict[int, dict[str, Any]], *, limit: int) -> list[int]:
    """Cover every selected market with one complete YES/NO threshold pair when possible."""
    by_market: dict[str, dict[tuple[str, str], dict[str, int]]] = {}
    for conid in selected_conids:
        meta = contract_index.get(conid, {})
        market = str(meta.get("market_name") or "")
        key = (str(meta.get("expiration") or ""), str(meta.get("strike") if meta.get("strike") is not None else meta.get("strike_label") or ""))
        side = str(meta.get("side") or "").upper()
        if side in {"Y", "N"}:
            by_market.setdefault(market, {}).setdefault(key, {})[side] = conid
    out: list[int] = []
    cap = max(0, int(limit))
    if cap == 0:
        return out
    for market in sorted(by_market):
        complete = [(k, v) for k, v in by_market[market].items() if "Y" in v and "N" in v]
        if not complete:
            continue
        complete.sort(key=lambda kv: kv[0])
        _, pair = complete[len(complete) // 2]
        for side in ("Y", "N"):
            if len(out) >= cap:
                return out
            out.append(pair[side])
    return out

def iter_batches(items: list[int], batch_size: int) -> Iterable[list[int]]:
    size = max(1, int(batch_size))
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _present(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip() not in {"", "-", "--", "None", "null"}


def quote_record(item: dict[str, Any], *, contract_meta: dict[str, Any], session_id: str, cycle_id: int, batch_id: int,
                 request_sent_utc: str, response_received_utc: str, request_monotonic_ns: int, response_monotonic_ns: int) -> dict[str, Any]:
    availability = decode_market_data_availability(item.get("6509"))
    fields = {
        "last": item.get("31"), "bid": item.get("84"), "ask_size": item.get("85"), "ask": item.get("86"),
        "volume": item.get("87"), "bid_size": item.get("88"), "exchange": item.get("6004"),
        "conid_field": item.get("6008"), "sec_type": item.get("6070"),
        "market_data_availability": item.get("6509"), "last_size": item.get("7059"),
    }
    field_presence = {k: _present(v) for k, v in fields.items()}
    return {
        "record_type": "quote", "collector_version": COLLECTOR_VERSION, "session_id": session_id,
        "cycle_id": cycle_id, "batch_id": batch_id, "request_sent_utc": request_sent_utc,
        "response_received_utc": response_received_utc, "request_monotonic_ns": request_monotonic_ns,
        "response_monotonic_ns": response_monotonic_ns,
        "request_elapsed_ms": (response_monotonic_ns - request_monotonic_ns) / 1_000_000.0,
        "conid": item.get("conid"), **contract_meta, **fields, "broker_updated_ms": item.get("_updated"),
        "availability_decoded": {
            "raw": availability.raw, "delivery": availability.delivery,
            "snapshot_or_consolidated": availability.snapshot_or_consolidated, "top_of_book": availability.top_of_book,
        },
        "field_presence": field_presence,
    }


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        f.flush()


def archive_rules(client: IBKRClient, selected_conids: list[int], contract_index: dict[int, dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    out = []
    for conid in selected_conids[:max(0, int(limit))]:
        rec: dict[str, Any] = {"conid": conid, **contract_index.get(conid, {})}
        try:
            details = sanitize_public_payload(client.contract_details(conid))
            rec["details"] = details
            rec["details_sha256"] = canonical_hash(details)
        except IBKRAPIError as exc:
            rec["details_error"] = str(exc)
        try:
            rules = sanitize_public_payload(client.contract_rules(conid))
            rec["rules"] = rules
            rec["rules_sha256"] = canonical_hash(rules)
        except IBKRAPIError as exc:
            rec["rules_error"] = str(exc)
        out.append(rec)
    return out


def archive_schedules(client: IBKRClient, selected_conids: list[int], contract_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Archive one public trading schedule per selected market."""
    representative: dict[str, int] = {}
    for conid in selected_conids:
        market = str(contract_index.get(conid, {}).get("market_name") or "")
        representative.setdefault(market, conid)
    out: list[dict[str, Any]] = []
    for market in sorted(representative):
        conid = representative[market]
        rec: dict[str, Any] = {"market_name": market, "representative_conid": conid}
        try:
            schedule = sanitize_public_payload(client.contract_schedules(conid))
            rec["schedule"] = schedule
            rec["schedule_sha256"] = canonical_hash(schedule)
        except IBKRAPIError as exc:
            rec["schedule_error"] = str(exc)
        out.append(rec)
    return out


def preflight_subscriptions(client: IBKRClient, conids: list[int], *, batch_size: int, prime_delay_seconds: float) -> None:
    fields = list(MARKET_DATA_FIELDS)
    for batch in iter_batches(conids, batch_size):
        client.marketdata_snapshot(batch, fields=fields)
        time.sleep(max(0.0, float(prime_delay_seconds)))


def run_session(*, client: IBKRClient, config: ShakedownConfig, output_dir: Path, duration_seconds: float, rotation_index: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    stats = SessionStats(started_utc=utc_now(), session_id=session_id)

    auth = client.auth_status()
    auth_value = auth.get("success", {}).get("value", {}) if isinstance(auth, dict) else {}
    if not auth_value and isinstance(auth, dict):
        auth_value = auth
    if not bool((auth_value or {}).get("authenticated")):
        raise RuntimeError("Gateway reachable but brokerage session is not authenticated")
    client.accounts()
    client.tickle()

    universe = discover_candidate_universe(client, pattern=config.market_name_pattern)
    (output_dir / "universe_snapshot.json").write_text(json.dumps(universe, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    rotation_selected = rotate_markets(universe.get("markets") or [], rotation_index=rotation_index,
                                       rotation_modulus=config.rotation_modulus, max_markets=config.max_markets_per_session)
    expiration_audit: list[dict[str, Any]] = []
    active_expirations: dict[str, str] = {}
    selected: list[dict[str, Any]] = []
    selection_epoch = time.time()
    for market in rotation_selected:
        market_meta = market.get("market") or {}
        discovery = market.get("discovery") or {}
        market_name = str(market_meta.get("market_name") or discovery.get("name") or "")
        expiration, evidence = resolve_active_expiration(client, market.get("contracts") or [], now_epoch=selection_epoch)
        expiration_audit.append({"market_name": market_name, "selected_expiration": expiration, "expiration_evidence": evidence})
        if expiration is not None:
            active_expirations[market_name] = expiration
            selected.append(market)

    contract_index, conids = build_contract_index(selected, active_expirations=active_expirations,
                                                   contracts_per_market=config.contracts_per_market)
    if not conids:
        raise RuntimeError("No still-tradable paired candidate contracts selected for shakedown")

    selection_manifest = {
        "collector_version": COLLECTOR_VERSION, "created_utc": utc_now(), "session_id": session_id,
        "rotation_index": rotation_index, "rotation_modulus": config.rotation_modulus,
        "rotation_market_count_before_active_filter": len(rotation_selected),
        "selected_market_count": len(selected), "selected_contract_count": len(conids),
        "active_expiration_resolution": expiration_audit,
        "selected_markets": selected, "contract_index": {str(k): v for k, v in contract_index.items()},
        "guardrail": "selection uses public trading metadata and threshold geometry only; no prices, basket cost or PnL are used",
    }
    (output_dir / "selection_manifest.json").write_text(json.dumps(selection_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    required_rule_contracts = 2 * len(selected)
    configured_rule_limit = int(config.rule_audit_contract_limit)
    effective_rule_limit = required_rule_contracts if configured_rule_limit <= 0 else configured_rule_limit
    if effective_rule_limit < required_rule_contracts:
        raise RuntimeError(
            f"Rule-audit contract limit {effective_rule_limit} cannot cover "
            f"{len(selected)} selected markets; need at least {required_rule_contracts}."
        )

    rule_audit_conids = select_rule_audit_conids(conids, contract_index, limit=effective_rule_limit)
    rules = archive_rules(client, rule_audit_conids, contract_index, limit=len(rule_audit_conids))
    (output_dir / "contract_rule_audit.json").write_text(json.dumps(rules, indent=2, sort_keys=True, ensure_ascii=False) + "\n")

    selected_market_names = {
        str((m.get("market") or {}).get("market_name") or (m.get("discovery") or {}).get("name") or "")
        for m in selected
    }
    rule_groups: dict[str, list[dict[str, Any]]] = {}
    for rec in rules:
        rule_groups.setdefault(str(rec.get("market_name") or ""), []).append(rec)

    bad_rule_markets: list[str] = []
    for market in sorted(selected_market_names):
        rows = rule_groups.get(market, [])
        sides = {str(r.get("side") or "").upper() for r in rows}
        strikes = {str(r.get("strike")) for r in rows}
        expirations = {str(r.get("expiration") or "") for r in rows}
        hashes = {str(r.get("rules_sha256") or "") for r in rows if r.get("rules_sha256")}
        has_errors = any("details_error" in r or "rules_error" in r for r in rows)
        if len(rows) != 2 or sides != {"Y", "N"} or len(strikes) != 1 or len(expirations) != 1 or len(hashes) != 1 or has_errors:
            bad_rule_markets.append(market)

    if bad_rule_markets:
        raise RuntimeError(
            "Rule audit failed complete YES/NO semantic coverage for: " + ", ".join(bad_rule_markets)
        )

    schedules = archive_schedules(client, conids, contract_index)
    (output_dir / "contract_schedule_audit.json").write_text(json.dumps(schedules, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    schedule_markets = {str(x.get("market_name") or "") for x in schedules}
    schedule_errors = [str(x.get("market_name") or "") for x in schedules if "schedule_error" in x]
    if schedule_markets != selected_market_names or schedule_errors:
        missing_schedule = sorted(selected_market_names - schedule_markets)
        parts = []
        if missing_schedule:
            parts.append("missing=" + ",".join(missing_schedule))
        if schedule_errors:
            parts.append("errors=" + ",".join(sorted(schedule_errors)))
        raise RuntimeError("Trading-schedule audit incomplete before collection: " + "; ".join(parts))

    preflight_subscriptions(client, conids, batch_size=config.batch_size, prime_delay_seconds=config.snapshot_prime_delay_seconds)

    quotes_path = output_dir / "quotes.jsonl"
    health_path = output_dir / "health.jsonl"
    start_mono = time.monotonic()
    next_due = start_mono
    end_mono = start_mono + max(1.0, float(duration_seconds))
    last_tickle = start_mono
    last_auth_check = start_mono
    last_cycle_start: float | None = None
    last_broker_updated_by_conid: dict[int, Any] = {}
    cycle_id = 0

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
            if observed_gap > config.provisional_cadence_seconds * config.gap_multiplier:
                stats.gaps += 1
                write_jsonl(health_path, {
                    "record_type": "gap", "collector_version": COLLECTOR_VERSION, "session_id": session_id,
                    "cycle_id": cycle_id, "detected_utc": utc_now(), "observed_interval_seconds": observed_gap,
                    "provisional_cadence_seconds": config.provisional_cadence_seconds,
                    "reason": "cycle_start_interval_exceeded",
                })
        last_cycle_start = cycle_start

        if cycle_start - last_tickle >= config.tickle_interval_seconds:
            try:
                client.tickle()
                write_jsonl(health_path, {"record_type": "tickle", "collector_version": COLLECTOR_VERSION,
                                          "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(), "ok": True})
            except IBKRAPIError as exc:
                stats.tickle_failures += 1
                write_jsonl(health_path, {"record_type": "tickle", "collector_version": COLLECTOR_VERSION,
                                          "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                                          "ok": False, "error": str(exc)})
            last_tickle = cycle_start

        if cycle_start - last_auth_check >= config.auth_check_interval_seconds:
            try:
                auth_now = client.auth_status()
                auth_now_value = auth_now.get("success", {}).get("value", {}) if isinstance(auth_now, dict) else {}
                if not auth_now_value and isinstance(auth_now, dict):
                    auth_now_value = auth_now
                authenticated_now = bool((auth_now_value or {}).get("authenticated"))
                if not authenticated_now:
                    stats.auth_failures += 1
                write_jsonl(health_path, {"record_type": "auth_status", "collector_version": COLLECTOR_VERSION,
                                          "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                                          "authenticated": authenticated_now})
            except IBKRAPIError as exc:
                stats.auth_failures += 1
                write_jsonl(health_path, {"record_type": "auth_status", "collector_version": COLLECTOR_VERSION,
                                          "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                                          "authenticated": False, "error": str(exc)})
            last_auth_check = cycle_start

        seen_this_cycle: set[int] = set()
        for batch_id, batch in enumerate(iter_batches(conids, config.batch_size), start=1):
            sent_utc = utc_now()
            sent_ns = time.monotonic_ns()
            try:
                payload = client.marketdata_snapshot(batch, fields=list(MARKET_DATA_FIELDS))
                recv_ns = time.monotonic_ns()
                recv_utc = utc_now()
                elapsed_ms = (recv_ns - sent_ns) / 1_000_000.0
                stats.max_batch_elapsed_ms = max(stats.max_batch_elapsed_ms, elapsed_ms)
                rows = payload if isinstance(payload, list) else []
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    conid = item.get("conid")
                    if not isinstance(conid, int) or conid not in contract_index:
                        continue
                    seen_this_cycle.add(conid)
                    rec = quote_record(item, contract_meta=contract_index[conid], session_id=session_id,
                                       cycle_id=cycle_id, batch_id=batch_id, request_sent_utc=sent_utc,
                                       response_received_utc=recv_utc, request_monotonic_ns=sent_ns,
                                       response_monotonic_ns=recv_ns)
                    write_jsonl(quotes_path, rec)
                    stats.quote_records += 1
                    market_name = str(rec.get("market_name") or "UNKNOWN")
                    stats.market_quote_records[market_name] += 1
                    fp = rec["field_presence"]
                    if fp.get("bid") and fp.get("ask"):
                        stats.complete_bbo_records += 1
                        stats.market_complete_bbo_records[market_name] += 1
                    if fp.get("bid") and fp.get("ask") and fp.get("bid_size") and fp.get("ask_size"):
                        stats.full_bbo_size_records += 1
                        stats.market_full_bbo_size_records[market_name] += 1
                    updated = rec.get("broker_updated_ms")
                    if conid in last_broker_updated_by_conid and updated is not None and updated != last_broker_updated_by_conid[conid]:
                        stats.market_broker_update_changes[market_name] += 1
                    if updated is not None:
                        last_broker_updated_by_conid[conid] = updated
                    raw6509 = rec.get("market_data_availability")
                    if raw6509 is not None:
                        stats.availability_values[str(raw6509)] += 1
                    delivery = (rec.get("availability_decoded") or {}).get("delivery")
                    if delivery:
                        stats.delivery_modes[str(delivery)] += 1
            except IBKRAPIError as exc:
                stats.http_errors += 1
                write_jsonl(health_path, {"record_type": "http_error", "collector_version": COLLECTOR_VERSION,
                                          "session_id": session_id, "cycle_id": cycle_id, "batch_id": batch_id,
                                          "utc": utc_now(), "conid_count": len(batch), "error": str(exc)})

        missing = [c for c in conids if c not in seen_this_cycle]
        if missing:
            stats.missing_contract_responses += len(missing)
            write_jsonl(health_path, {"record_type": "missing_contracts", "collector_version": COLLECTOR_VERSION,
                                      "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                                      "missing_count": len(missing), "missing_conids": missing})

        cycle_elapsed_ms = (time.monotonic() - cycle_start) * 1000.0
        stats.max_cycle_elapsed_ms = max(stats.max_cycle_elapsed_ms, cycle_elapsed_ms)
        stats.completed_cycles += 1
        write_jsonl(health_path, {"record_type": "cycle_complete", "collector_version": COLLECTOR_VERSION,
                                  "session_id": session_id, "cycle_id": cycle_id, "utc": utc_now(),
                                  "cycle_elapsed_ms": cycle_elapsed_ms, "expected_contract_count": len(conids),
                                  "seen_contract_count": len(seen_this_cycle)})

        next_due = start_mono + cycle_id * config.provisional_cadence_seconds
        if next_due < time.monotonic():
            next_due = time.monotonic() + config.provisional_cadence_seconds

    summary = {
        "collector_version": COLLECTOR_VERSION, "study_status": "SHAKEDOWN_ONLY_NOT_CONFIRMATORY",
        "started_utc": stats.started_utc, "finished_utc": utc_now(), "session_id": session_id,
        "duration_requested_seconds": duration_seconds, "provisional_cadence_seconds": config.provisional_cadence_seconds,
        "rotation_index": rotation_index, "rotation_market_count_before_active_filter": len(rotation_selected),
        "selected_market_count": len(selected), "selected_contract_count": len(conids),
        "nominal_scheduled_cycles": int((max(1.0, float(duration_seconds)) + config.provisional_cadence_seconds - 1e-12) // config.provisional_cadence_seconds),
        "expected_cycles": stats.expected_cycles, "completed_cycles": stats.completed_cycles,
        "quote_records": stats.quote_records, "complete_bbo_records": stats.complete_bbo_records,
        "full_bbo_size_records": stats.full_bbo_size_records,
        "missing_contract_responses": stats.missing_contract_responses, "http_errors": stats.http_errors,
        "tickle_failures": stats.tickle_failures, "auth_failures": stats.auth_failures, "gaps": stats.gaps,
        "max_cycle_elapsed_ms": stats.max_cycle_elapsed_ms, "max_batch_elapsed_ms": stats.max_batch_elapsed_ms,
        "availability_values": dict(stats.availability_values), "delivery_modes": dict(stats.delivery_modes),
        "rule_audit_contract_limit_effective": effective_rule_limit,
        "rule_audit_contract_count": len(rules),
        "rule_audit_market_count": len({str(x.get("market_name") or "") for x in rules}),
        "schedule_audit_market_count": len(schedules),
        "schedule_audit_errors": sum(1 for x in schedules if "schedule_error" in x),
        "market_health": {
            market: {
                "quote_records": int(stats.market_quote_records[market]),
                "complete_bbo_records": int(stats.market_complete_bbo_records[market]),
                "full_bbo_size_records": int(stats.market_full_bbo_size_records[market]),
                "broker_updated_change_count": int(stats.market_broker_update_changes[market]),
            }
            for market in sorted(stats.market_quote_records)
        },
        "guardrail": "No basket-cost, opportunity, alpha or PnL calculation was performed.",
    }
    (output_dir / "session_health_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
