"""Read-only capability audit helpers for V3 IBKR / ForecastEx infrastructure."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from src.v3.ibkr.client import IBKRAPIError, IBKRClient
from src.v3.ibkr.websocket_probe import probe_market_stream


MARKET_DATA_FIELDS = {
    "31": "last",
    "84": "bid",
    "85": "ask_size",
    "86": "ask",
    "87": "volume",
    "88": "bid_size",
    "201": "right",
    "6004": "exchange",
    "6008": "conid_field",
    "6070": "sec_type",
    "6509": "market_data_availability",
    "7059": "last_size",
}


@dataclass(frozen=True)
class MarketDataAvailability:
    raw: str | None
    delivery: str | None
    snapshot_or_consolidated: str | None
    top_of_book: bool


def decode_market_data_availability(value: str | None) -> MarketDataAvailability:
    if not value:
        return MarketDataAvailability(None, None, None, False)
    first = value[0] if len(value) >= 1 else None
    second = value[1] if len(value) >= 2 else None
    third = value[2] if len(value) >= 3 else None
    delivery_map = {
        "R": "real_time",
        "D": "delayed",
        "Z": "frozen",
        "Y": "frozen_delayed",
        "N": "not_subscribed",
        "i": "incomplete",
        "v": "vdr_exempt",
    }
    second_map = {"P": "snapshot", "p": "consolidated"}
    return MarketDataAvailability(
        raw=value,
        delivery=delivery_map.get(first, f"unknown:{first}" if first else None),
        snapshot_or_consolidated=second_map.get(second, f"unknown:{second}" if second else None),
        top_of_book=(third == "B"),
    )


def _unwrap_auth_status(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("success"), dict):
        value = payload["success"].get("value")
        if isinstance(value, dict):
            return value
    return payload


def _safe_auth_summary(payload: Any) -> dict[str, Any]:
    status = _unwrap_auth_status(payload)
    return {
        "authenticated": bool(status.get("authenticated", False)),
        "connected": bool(status.get("connected", False)),
        "established": bool(status.get("established", False)),
        "competing": bool(status.get("competing", False)),
    }


def _safe_contract_search(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    out: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        sections = item.get("sections")
        safe_sections = []
        if isinstance(sections, list):
            for section in sections:
                if isinstance(section, dict):
                    safe_sections.append(
                        {
                            k: section.get(k)
                            for k in ("secType", "exchange", "months")
                            if k in section
                        }
                    )
        out.append(
            {
                k: item.get(k)
                for k in ("conid", "symbol", "companyName", "description", "opt")
                if k in item
            }
            | {"sections": safe_sections}
        )
    return out


def _safe_contract_metadata(payload: Any) -> Any:
    allowed = {
        "conid", "conid_yes", "conid_no", "question", "side", "strike_label",
        "strike", "exchange", "expiration", "symbol", "measured_period",
        "market_name", "underlying_conid", "payout", "asset_class", "description",
        "threshold", "source_agency", "data_and_resolution_link", "last_trade_time",
        "product_code", "market_rules_link", "release_time", "payout_time",
        "price_increment", "exchange_timezone", "right", "secType", "maturityDate",
        "tradingClass", "validExchanges", "expiry_label", "time_specifier",
    }
    if isinstance(payload, list):
        return [_safe_contract_metadata(x) for x in payload]
    if isinstance(payload, dict):
        return {k: v for k, v in payload.items() if k in allowed}
    return payload


def _safe_market_snapshot(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    out: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        record: dict[str, Any] = {
            "conid": item.get("conid"),
            "broker_updated_ms": item.get("_updated"),
        }
        for field_id, name in MARKET_DATA_FIELDS.items():
            if field_id in item:
                record[name] = item[field_id]
        record["market_data_availability_decoded"] = asdict(
            decode_market_data_availability(item.get("6509"))
        )
        out.append(record)
    return out


def _flatten_category_tree(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    categories = payload.get("categories")
    if not isinstance(categories, dict):
        return []
    out: list[dict[str, Any]] = []
    for category_id, category in categories.items():
        if not isinstance(category, dict):
            continue
        markets = category.get("markets")
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict):
                continue
            out.append(
                {
                    "category_id": str(category_id),
                    "category_name": category.get("name"),
                    "category_parent_id": category.get("parent_id"),
                    "name": market.get("name"),
                    "symbol": market.get("symbol"),
                    "exchange": market.get("exchange"),
                    "conid": market.get("conid"),
                    "product_conid": market.get("product_conid"),
                }
            )
    return out


def find_markets(payload: Any, pattern: str) -> tuple[int, list[dict[str, Any]]]:
    all_markets = _flatten_category_tree(payload)
    rx = re.compile(pattern, re.IGNORECASE)
    matches = []
    for market in all_markets:
        haystack = " | ".join(
            str(x or "") for x in (market.get("name"), market.get("symbol"), market.get("category_name"))
        )
        if rx.search(haystack):
            matches.append(market)
    matches.sort(key=lambda x: (str(x.get("name")), str(x.get("symbol"))))
    return len(all_markets), matches


def _safe_market_contracts(payload: Any, max_pairs: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"market": {}, "pairs": [], "contract_count": 0}
    contracts = payload.get("contracts")
    if not isinstance(contracts, list):
        contracts = []
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for c in contracts:
        if not isinstance(c, dict):
            continue
        expiration = str(c.get("expiration") or "")
        strike_key = str(c.get("strike_label") if c.get("strike_label") is not None else c.get("strike"))
        key = (expiration, strike_key)
        rec = groups.setdefault(
            key,
            {
                "expiration": c.get("expiration"),
                "strike": c.get("strike"),
                "strike_label": c.get("strike_label"),
                "underlying_conid": c.get("underlying_conid"),
                "yes_conid": None,
                "no_conid": None,
            },
        )
        side = str(c.get("side") or "").upper()
        if side == "Y":
            rec["yes_conid"] = c.get("conid")
        elif side == "N":
            rec["no_conid"] = c.get("conid")
    pairs = sorted(groups.values(), key=lambda x: (str(x.get("expiration")), str(x.get("strike"))))[:max_pairs]
    return {
        "market": {
            k: payload.get(k)
            for k in ("market_name", "exchange", "symbol", "payout", "exclude_historical_data")
            if k in payload
        },
        "contract_count": len(contracts),
        "pairs": pairs,
    }


def _history_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "bar_count": 0}
    data = payload.get("data")
    if not isinstance(data, list):
        data = []
    times = [row.get("t") for row in data if isinstance(row, dict) and isinstance(row.get("t"), int)]
    return {
        "ok": True,
        "bar_count": len(data),
        "first_bar_time_ms": times[0] if times else None,
        "last_bar_time_ms": times[-1] if times else None,
        "top_level_keys": sorted(str(k) for k in payload.keys()),
        "row_keys": sorted({str(k) for row in data[:10] if isinstance(row, dict) for k in row.keys()}),
    }


def run_http_capability_audit(
    client: IBKRClient,
    *,
    symbol: str | None = None,
    contract_conid: int | None = None,
    market_conids: list[int] | None = None,
    auto_weather: bool = False,
    market_name_pattern: str = r"temperature|weather",
    max_markets: int = 6,
    max_contract_pairs_per_market: int = 2,
    probe_history: bool = False,
    websocket_seconds: float = 0.0,
) -> dict[str, Any]:
    """Run the read-only V3 capability audit.

    No order endpoint is implemented or called. Auto-weather mode uses the
    ForecastEx category tree, market-contract endpoint, contract details/rules,
    HTTP BBO snapshots, optional 1-minute historical bars, and an optional short
    websocket top-of-book probe.
    """

    report: dict[str, Any] = {
        "audit_version": "v3_ibkr_capability_2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": client.base_url,
        "verify_tls": client.verify_tls,
        "read_only": True,
        "orders_submitted": False,
        "gateway_reachable": False,
        "auth": None,
        "tickle_ok": False,
        "accounts_endpoint_ok": False,
        "account_count": None,
        "symbol_probe": None,
        "contract_details": None,
        "contract_rules": None,
        "market_snapshot": None,
        "auto_weather_discovery": None,
        "historical_probe": None,
        "websocket_probe": None,
        "errors": [],
        "remaining_audit_work": [
            "long-duration stream stability and reconnect/gap behavior",
            "measured rate-limit / throttling behavior beyond documented limits",
            "paper-versus-live capability comparison",
            "price-ladder / depth capability if required for the final strategy",
            "full-day local-clock / receive-timestamp discipline",
        ],
    }

    try:
        auth_raw = client.auth_status()
        report["gateway_reachable"] = True
        report["auth"] = _safe_auth_summary(auth_raw)
    except IBKRAPIError as exc:
        report["errors"].append(str(exc))
        return report

    try:
        client.tickle()
        report["tickle_ok"] = True
    except IBKRAPIError as exc:
        report["errors"].append(str(exc))

    try:
        accounts = client.accounts()
        report["accounts_endpoint_ok"] = True
        if isinstance(accounts, dict) and isinstance(accounts.get("accounts"), list):
            report["account_count"] = len(accounts["accounts"])
        elif isinstance(accounts, list):
            report["account_count"] = len(accounts)
    except IBKRAPIError as exc:
        report["errors"].append(str(exc))

    if symbol:
        try:
            report["symbol_probe"] = _safe_contract_search(client.search_symbol(symbol))
        except IBKRAPIError as exc:
            report["errors"].append(str(exc))

    if contract_conid is not None:
        try:
            report["contract_details"] = _safe_contract_metadata(client.contract_details(contract_conid))
        except IBKRAPIError as exc:
            report["errors"].append(str(exc))
        try:
            report["contract_rules"] = _safe_contract_metadata(client.contract_rules(contract_conid))
        except IBKRAPIError as exc:
            report["errors"].append(str(exc))

    discovered_conids: list[int] = []
    if auto_weather:
        discovery: dict[str, Any] = {
            "pattern": market_name_pattern,
            "category_tree_ok": False,
            "total_markets_in_tree": None,
            "matching_market_count": 0,
            "matching_markets": [],
            "probed_markets": [],
        }
        try:
            tree = client.category_tree()
            discovery["category_tree_ok"] = True
            total, matches = find_markets(tree, market_name_pattern)
            discovery["total_markets_in_tree"] = total
            discovery["matching_market_count"] = len(matches)
            discovery["matching_markets"] = matches[:50]
            for market in matches[:max_markets]:
                conid = market.get("conid")
                if not isinstance(conid, int):
                    continue
                try:
                    safe_market = _safe_market_contracts(
                        client.forecast_market(conid, exchange=str(market.get("exchange") or "FORECASTX")),
                        max_contract_pairs_per_market,
                    )
                    safe_market["discovery"] = market
                    discovery["probed_markets"].append(safe_market)
                    for pair in safe_market["pairs"]:
                        for key in ("yes_conid", "no_conid"):
                            value = pair.get(key)
                            if isinstance(value, int) and value not in discovered_conids:
                                discovered_conids.append(value)
                except IBKRAPIError as exc:
                    report["errors"].append(str(exc))
            report["auto_weather_discovery"] = discovery
        except (IBKRAPIError, re.error) as exc:
            report["errors"].append(str(exc))
            report["auto_weather_discovery"] = discovery

        if discovered_conids and contract_conid is None:
            first = discovered_conids[0]
            try:
                report["contract_details"] = _safe_contract_metadata(client.contract_details(first))
            except IBKRAPIError as exc:
                report["errors"].append(str(exc))
            try:
                report["contract_rules"] = _safe_contract_metadata(client.contract_rules(first))
            except IBKRAPIError as exc:
                report["errors"].append(str(exc))

    snapshot_conids = list(dict.fromkeys((market_conids or []) + discovered_conids[:8]))
    if snapshot_conids:
        fields = list(MARKET_DATA_FIELDS)
        try:
            client.marketdata_snapshot(snapshot_conids, fields=fields)
            second = client.marketdata_snapshot(snapshot_conids, fields=fields)
            report["market_snapshot"] = _safe_market_snapshot(second)
        except IBKRAPIError as exc:
            report["errors"].append(str(exc))

    probe_conid = snapshot_conids[0] if snapshot_conids else contract_conid
    if probe_history and isinstance(probe_conid, int):
        try:
            report["historical_probe"] = _history_summary(
                client.historical_marketdata(probe_conid, period="1d", bar="1min")
            )
        except IBKRAPIError as exc:
            report["historical_probe"] = {"ok": False, "bar_count": 0}
            report["errors"].append(str(exc))

    if websocket_seconds > 0 and isinstance(probe_conid, int):
        try:
            report["websocket_probe"] = probe_market_stream(
                client,
                probe_conid,
                fields=list(MARKET_DATA_FIELDS),
                duration_seconds=websocket_seconds,
            )
        except IBKRAPIError as exc:
            report["errors"].append(str(exc))

    return report
