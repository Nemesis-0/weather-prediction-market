from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://external-api.kalshi.com/trade-api/v2"

CENSUS_DIR = Path("data/raw/market/history")
OUTPUT_DIR = Path("data/raw/market/candlesticks/60m")


def rule_source_hint(market: dict[str, Any]) -> str:
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


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(
            value,
            tz=timezone.utc,
        )

    text = str(value).replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except ValueError:
        return None


def get_json(
    session: requests.Session,
    path: str,
    params: dict[str, Any],
) -> dict[str, Any]:

    max_retries = 8

    for attempt in range(max_retries):

        response = session.get(
            f"{BASE_URL}{path}",
            params=params,
            timeout=30,
        )

        if response.status_code == 429:

            retry_after = response.headers.get("Retry-After")

            if retry_after:
                try:
                    wait = float(retry_after)
                except ValueError:
                    wait = min(2 ** attempt, 60)
            else:
                wait = min(2 ** attempt, 60)

            print(
                f"    429 rate limit — waiting {wait:.1f}s"
            )

            time.sleep(wait)
            continue

        response.raise_for_status()

        return response.json()

    raise RuntimeError(
        f"Exceeded retry limit for {path}"
    )


def latest_census_file() -> Path:
    files = sorted(
        CENSUS_DIR.glob(
            "market_history_census_*.json"
        )
    )

    if not files:
        raise FileNotFoundError(
            "No history census JSON found."
        )

    return files[-1]


def event_window(
    markets: list[dict[str, Any]],
) -> tuple[int, int]:

    start_candidates: list[datetime] = []
    end_candidates: list[datetime] = []

    for market in markets:

        for field in (
            "open_time",
            "created_time",
        ):
            dt = parse_time(market.get(field))
            if dt:
                start_candidates.append(dt)

        for field in (
            "settlement_ts",
            "close_time",
            "expiration_time",
        ):
            dt = parse_time(market.get(field))
            if dt:
                end_candidates.append(dt)

    if not start_candidates:
        raise RuntimeError(
            "Could not determine market start time."
        )

    if not end_candidates:
        raise RuntimeError(
            "Could not determine market end time."
        )

    start = min(start_candidates)
    end = max(end_candidates)

    return (
        int(start.timestamp()),
        int(end.timestamp()),
    )


def main() -> None:

    census_path = latest_census_file()

    print("\nTWC-era hourly candlestick backfill")
    print("=" * 80)
    print(f"Census: {census_path}")

    census = json.loads(
        census_path.read_text(
            encoding="utf-8"
        )
    )

    session = requests.Session()

    total_events = 0
    fetched_events = 0
    skipped_events = 0
    total_candles = 0

    for series_ticker, series_record in census["series"].items():

        city = series_record["city"]

        grouped: dict[
            str,
            list[dict[str, Any]]
        ] = defaultdict(list)

        for market in series_record["combined_markets"]:

            if rule_source_hint(market) != "TWC":
                continue

            event_ticker = market.get("event_ticker")

            if event_ticker:
                grouped[event_ticker].append(market)

        print(
            f"\n{city} — {series_ticker}"
            f" — {len(grouped)} TWC events"
        )

        series_dir = (
            OUTPUT_DIR / series_ticker
        )

        series_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for event_ticker in sorted(grouped):

            markets = grouped[event_ticker]

            total_events += 1

            output_path = (
                series_dir
                / f"{event_ticker}.json"
            )

            # Resume support.
            if output_path.exists():
                skipped_events += 1
                print(
                    f"  SKIP {event_ticker}"
                    " — already downloaded"
                )
                continue

            tickers = sorted(
                market["ticker"]
                for market in markets
            )

            start_ts, end_ts = event_window(
                markets
            )

            payload = get_json(
                session,
                "/markets/candlesticks",
                {
                    "market_tickers": ",".join(
                        tickers
                    ),
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "period_interval": 60,
                    "include_latest_before_start":
                        "false",
                },
            )

            candle_count = sum(
                len(
                    market_record.get(
                        "candlesticks",
                        [],
                    )
                )
                for market_record
                in payload.get("markets", [])
            )

            total_candles += candle_count
            fetched_events += 1

            raw_record = {
                "schema_version": 1,
                "source":
                    "Kalshi public Trade API",
                "period_interval_minutes": 60,
                "series_ticker":
                    series_ticker,
                "city": city,
                "event_ticker":
                    event_ticker,
                "start_ts":
                    start_ts,
                "end_ts":
                    end_ts,
                "market_metadata":
                    markets,
                "candlestick_response":
                    payload,
            }

            output_path.write_text(
                json.dumps(
                    raw_record,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            print(
                f"  {event_ticker}"
                f" | markets={len(tickers)}"
                f" | candles={candle_count}"
            )

            # Gentle pacing for public API.
            time.sleep(0.35)

    print("\n" + "=" * 80)
    print(
        f"TWC event-days discovered: {total_events}"
    )
    print(
        f"Downloaded this run:       {fetched_events}"
    )
    print(
        f"Already present/skipped:   {skipped_events}"
    )
    print(
        f"Hourly candles downloaded: {total_candles}"
    )
    print(
        f"Output directory:          {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()
