from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

SERIES = {
    "NYC": "KXHIGHNY",
    "Chicago": "KXHIGHCHI",
    "Denver": "KXHIGHDEN",
}

OUTPUT_DIR = Path("data/raw/market/history")


def get_json(
    session: requests.Session,
    path: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    max_retries = 8

    for attempt in range(max_retries):
        r = session.get(
            f"{BASE_URL}{path}",
            params=params,
            timeout=30,
        )

        if r.status_code != 429:
            r.raise_for_status()
            return r.json()

        retry_after = r.headers.get("Retry-After")

        if retry_after:
            try:
                wait_seconds = float(retry_after)
            except ValueError:
                wait_seconds = min(2 ** attempt, 60)
        else:
            wait_seconds = min(2 ** attempt, 60)

        print(
            f"  Rate limited (429). "
            f"Waiting {wait_seconds:.1f}s before retry..."
        )
        time.sleep(wait_seconds)

    raise RuntimeError(
        f"Exceeded {max_retries} retries for {path}"
    )


def paginate_markets(
    session: requests.Session,
    path: str,
    params: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Returns:
      parsed markets
      raw page payloads
    """
    markets: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []

    cursor = None

    while True:
        q = dict(params)
        q["limit"] = 1000

        if cursor:
            q["cursor"] = cursor

        payload = get_json(session, path, q)
        pages.append(payload)

        # Be polite to the public API during large historical backfills.
        time.sleep(0.35)

        batch = payload.get("markets", [])
        markets.extend(batch)

        cursor = payload.get("cursor")
        if not cursor:
            break

    return markets, pages


def rule_source_hint(market: dict[str, Any]) -> str:
    """
    Heuristic only.

    We do NOT treat this as final authoritative settlement metadata.
    It is used to identify possible historical regime changes for audit.
    """
    text = " ".join(
        str(market.get(field) or "")
        for field in (
            "rules_primary",
            "rules_secondary",
            "subtitle",
            "title",
        )
    ).lower()

    if (
        "the weather company" in text
        or "weather.com/kalshi" in text
    ):
        return "TWC"

    if (
        "national weather service" in text
        or "nws " in text
        or "nws/" in text
    ):
        return "NWS"

    return "UNKNOWN"


def time_key(market: dict[str, Any]) -> str:
    for field in (
        "settlement_ts",
        "close_time",
        "expiration_time",
        "open_time",
        "created_time",
    ):
        value = market.get(field)
        if value:
            return str(value)

    return ""


def main() -> None:
    session = requests.Session()

    run_at = datetime.now(timezone.utc)

    print("\nKalshi historical weather-market census")
    print("=" * 80)

    cutoff = get_json(session, "/historical/cutoff")

    print(
        "market historical cutoff:",
        cutoff.get("market_settled_ts"),
    )

    output: dict[str, Any] = {
        "schema_version": 1,
        "collected_at_utc": run_at.isoformat(),
        "historical_cutoff": cutoff,
        "series": {},
    }

    for city, series_ticker in SERIES.items():
        print(f"\n{city} — {series_ticker}")

        # Recent settled markets still in live storage.
        live_markets, live_pages = paginate_markets(
            session,
            "/markets",
            {
                "series_ticker": series_ticker,
                "status": "settled",
            },
        )

        # Older settled markets moved to historical storage.
        historical_markets, historical_pages = paginate_markets(
            session,
            "/historical/markets",
            {
                "series_ticker": series_ticker,
            },
        )

        combined_by_ticker: dict[str, dict[str, Any]] = {}

        for market in historical_markets:
            market = dict(market)
            market["_storage_tier"] = "historical"
            combined_by_ticker[market["ticker"]] = market

        for market in live_markets:
            market = dict(market)
            market["_storage_tier"] = "live"
            combined_by_ticker[market["ticker"]] = market

        combined = list(combined_by_ticker.values())

        # One representative record per event/day.
        events: dict[str, dict[str, Any]] = {}

        for market in combined:
            event_ticker = market.get("event_ticker")

            if not event_ticker:
                continue

            if event_ticker not in events:
                events[event_ticker] = market

        source_counts = Counter(
            rule_source_hint(m)
            for m in events.values()
        )

        print(f"  live settled markets:       {len(live_markets)}")
        print(f"  archived markets:           {len(historical_markets)}")
        print(f"  combined unique markets:    {len(combined)}")
        print(f"  unique event-days:          {len(events)}")
        print(f"  rule-source hints:          {dict(source_counts)}")

        # Print approximate date range by source hint.
        for source in ("TWC", "NWS", "UNKNOWN"):
            subset = [
                m
                for m in events.values()
                if rule_source_hint(m) == source
            ]

            if not subset:
                continue

            dates = sorted(
                x
                for x in (time_key(m) for m in subset)
                if x
            )

            if dates:
                print(
                    f"    {source:<7}"
                    f" events={len(subset):<5}"
                    f" range={dates[0]}  ->  {dates[-1]}"
                )
            else:
                print(
                    f"    {source:<7}"
                    f" events={len(subset):<5}"
                    f" range=unavailable"
                )

        output["series"][series_ticker] = {
            "city": city,
            "live_pages": live_pages,
            "historical_pages": historical_pages,
            "combined_markets": combined,
            "summary": {
                "live_market_count": len(live_markets),
                "historical_market_count": len(historical_markets),
                "combined_unique_market_count": len(combined),
                "unique_event_count": len(events),
                "rule_source_hint_counts": dict(source_counts),
            },
        }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = run_at.strftime("%Y%m%dT%H%M%SZ")

    output_path = (
        OUTPUT_DIR
        / f"market_history_census_{timestamp}.json"
    )

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 80)
    print(f"Saved census: {output_path}")


if __name__ == "__main__":
    main()
