from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from src.market.kalshi_client import KalshiPublicClient


SERIES = {
    "NYC": "KXHIGHNY",
    "Chicago": "KXHIGHCHI",
    "Denver": "KXHIGHDEN",
}

OUTPUT_DIR = Path("data/raw/market")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def best_price(levels: list[list[str]]) -> str | None:
    if not levels:
        return None
    return max(levels, key=lambda x: float(x[0]))[0]


def main() -> None:
    client = KalshiPublicClient()

    started_at = datetime.now(timezone.utc)
    timer_start = time.perf_counter()

    print("\nKalshi synchronized weather-market snapshot")
    print("=" * 78)

    series_data = {}
    all_tickers: list[str] = []

    # Step 1: collect series metadata and current market records.
    for city, series_ticker in SERIES.items():
        series_payload = client.get_series(series_ticker)
        markets = client.get_markets(
            series_ticker,
            status="open",
        )

        series = series_payload["series"]

        series_data[series_ticker] = {
            "city": city,
            "series_metadata": series,
            "markets": markets,
        }

        all_tickers.extend(
            market["ticker"]
            for market in markets
        )

    # Step 2: get all order books as close to one instant as possible.
    orderbook_request_started_at = utc_now()

    orderbooks = client.get_orderbooks(all_tickers)

    orderbook_request_finished_at = utc_now()

    # Step 3: combine metadata + order books.
    snapshot_series = {}

    for series_ticker, record in series_data.items():
        city = record["city"]
        series = record["series_metadata"]
        markets = record["markets"]

        print(f"\n{city} — {series_ticker}")
        print(
            "  settlement source(s):",
            [
                x.get("name")
                for x in series.get("settlement_sources", [])
            ],
        )
        print(f"  fee type: {series.get('fee_type')}")
        print(f"  fee multiplier: {series.get('fee_multiplier')}")
        print(f"  markets returned: {len(markets)}")

        combined_markets = []

        for market in markets:
            ticker = market["ticker"]
            orderbook = orderbooks.get(ticker)

            if orderbook is None:
                print(f"    WARNING: no batch orderbook returned for {ticker}")
                combined_markets.append(
                    {
                        "market": market,
                        "orderbook": None,
                    }
                )
                continue

            yes_levels = orderbook.get("yes_dollars", [])
            no_levels = orderbook.get("no_dollars", [])

            print(
                f"    {ticker}"
                f" | {market.get('yes_sub_title') or market.get('title')}"
                f" | YES levels={len(yes_levels)}"
                f" | NO levels={len(no_levels)}"
                f" | best YES bid={best_price(yes_levels)}"
                f" | best NO bid={best_price(no_levels)}"
            )

            combined_markets.append(
                {
                    "market": market,
                    "orderbook": orderbook,
                }
            )

        snapshot_series[series_ticker] = {
            "city": city,
            "series_metadata": series,
            "markets": combined_markets,
        }

    finished_at = datetime.now(timezone.utc)
    duration = time.perf_counter() - timer_start

    snapshot = {
        "schema_version": 3,
        "collection_started_at_utc": started_at.isoformat(),
        "orderbook_batch_started_at_utc": orderbook_request_started_at,
        "orderbook_batch_finished_at_utc": orderbook_request_finished_at,
        "collection_finished_at_utc": finished_at.isoformat(),
        "collection_duration_seconds": round(duration, 3),
        "source": "Kalshi public Trade API",
        "series": snapshot_series,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    output_path = (
        OUTPUT_DIR
        / f"kalshi_snapshot_{timestamp}.json"
    )

    output_path.write_text(
        json.dumps(
            snapshot,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 78)
    print(f"Market tickers requested: {len(all_tickers)}")
    print(f"Order books returned:    {len(orderbooks)}")
    print(f"Collection duration:     {duration:.3f} seconds")
    print(f"Saved raw snapshot:      {output_path}")


if __name__ == "__main__":
    main()
