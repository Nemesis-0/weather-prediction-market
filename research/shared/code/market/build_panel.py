from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


RAW_DIR = Path("data/raw/market/candlesticks/60m")
PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results/development")

SERIES_TIMEZONES = {
    "KXHIGHNY": "America/New_York",
    "KXHIGHCHI": "America/Chicago",
    "KXHIGHDEN": "America/Denver",
}

MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def as_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def nested_float(obj, parent, child):
    value = obj.get(parent, {}).get(child)
    return as_float(value)


def parse_iso(value):
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
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def event_date_from_ticker(event_ticker: str) -> str:
    match = re.search(
        r"-(\d{2})([A-Z]{3})(\d{2})$",
        event_ticker,
    )

    if not match:
        raise ValueError(
            f"Could not parse event date: {event_ticker}"
        )

    yy, mon, dd = match.groups()

    year = 2000 + int(yy)
    month = MONTHS[mon]
    day = int(dd)

    return (
        datetime(year, month, day)
        .date()
        .isoformat()
    )


def main():
    files = sorted(
        RAW_DIR.glob("*/*.json")
    )

    if not files:
        raise RuntimeError(
            "No raw candlestick files found."
        )

    rows = []

    print("\nBuilding clean market panel")
    print("=" * 80)
    print(f"Raw event files: {len(files)}")

    for file_path in files:
        data = json.loads(
            file_path.read_text(
                encoding="utf-8"
            )
        )

        series_ticker = data["series_ticker"]
        city = data["city"]
        event_ticker = data["event_ticker"]

        timezone_name = SERIES_TIMEZONES[
            series_ticker
        ]

        local_tz = ZoneInfo(timezone_name)

        event_date_local = (
            event_date_from_ticker(
                event_ticker
            )
        )

        metadata_by_ticker = {
            market["ticker"]: market
            for market in data["market_metadata"]
        }

        for market_record in (
            data["candlestick_response"]["markets"]
        ):
            market_ticker = (
                market_record["market_ticker"]
            )

            metadata = metadata_by_ticker.get(
                market_ticker
            )

            if metadata is None:
                raise RuntimeError(
                    f"Missing metadata for "
                    f"{market_ticker}"
                )

            close_dt = parse_iso(
                metadata.get("close_time")
            )

            expiration_dt = parse_iso(
                metadata.get("expiration_time")
            )

            result = (
                str(metadata.get("result") or "")
                .strip()
                .lower()
            )

            if result == "yes":
                outcome_yes = 1
            elif result == "no":
                outcome_yes = 0
            else:
                outcome_yes = None

            for candle in market_record.get(
                "candlesticks",
                [],
            ):
                end_ts = int(
                    candle["end_period_ts"]
                )

                end_utc = datetime.fromtimestamp(
                    end_ts,
                    tz=timezone.utc,
                )

                end_local = end_utc.astimezone(
                    local_tz
                )

                if close_dt is not None:
                    hours_to_close = (
                        close_dt - end_utc
                    ).total_seconds() / 3600.0

                    is_pre_close = (
                        end_utc <= close_dt
                    )
                else:
                    hours_to_close = None
                    is_pre_close = None

                yes_bid_close = nested_float(
                    candle,
                    "yes_bid",
                    "close_dollars",
                )

                yes_ask_close = nested_float(
                    candle,
                    "yes_ask",
                    "close_dollars",
                )

                if (
                    yes_bid_close is not None
                    and yes_ask_close is not None
                ):
                    midpoint_close = (
                        yes_bid_close
                        + yes_ask_close
                    ) / 2.0

                    spread_close = (
                        yes_ask_close
                        - yes_bid_close
                    )
                else:
                    midpoint_close = None
                    spread_close = None

                rows.append(
                    {
                        "city": city,
                        "series_ticker":
                            series_ticker,
                        "event_ticker":
                            event_ticker,
                        "event_date_local":
                            event_date_local,
                        "timezone":
                            timezone_name,

                        "market_ticker":
                            market_ticker,
                        "bucket_label":
                            metadata.get(
                                "yes_sub_title"
                            ),
                        "strike_type":
                            metadata.get(
                                "strike_type"
                            ),
                        "floor_strike":
                            metadata.get(
                                "floor_strike"
                            ),

                        "candle_end_ts":
                            end_ts,
                        "timestamp_utc":
                            end_utc.isoformat(),
                        "timestamp_local":
                            end_local.isoformat(),

                        "market_close_utc":
                            (
                                close_dt.isoformat()
                                if close_dt
                                else None
                            ),
                        "expiration_utc":
                            (
                                expiration_dt.isoformat()
                                if expiration_dt
                                else None
                            ),
                        "hours_to_close":
                            hours_to_close,
                        "is_pre_close":
                            is_pre_close,

                        "result":
                            result or None,
                        "outcome_yes":
                            outcome_yes,

                        "yes_bid_open":
                            nested_float(
                                candle,
                                "yes_bid",
                                "open_dollars",
                            ),
                        "yes_bid_high":
                            nested_float(
                                candle,
                                "yes_bid",
                                "high_dollars",
                            ),
                        "yes_bid_low":
                            nested_float(
                                candle,
                                "yes_bid",
                                "low_dollars",
                            ),
                        "yes_bid_close":
                            yes_bid_close,

                        "yes_ask_open":
                            nested_float(
                                candle,
                                "yes_ask",
                                "open_dollars",
                            ),
                        "yes_ask_high":
                            nested_float(
                                candle,
                                "yes_ask",
                                "high_dollars",
                            ),
                        "yes_ask_low":
                            nested_float(
                                candle,
                                "yes_ask",
                                "low_dollars",
                            ),
                        "yes_ask_close":
                            yes_ask_close,

                        "midpoint_close":
                            midpoint_close,
                        "spread_close":
                            spread_close,

                        "trade_price_open":
                            nested_float(
                                candle,
                                "price",
                                "open_dollars",
                            ),
                        "trade_price_high":
                            nested_float(
                                candle,
                                "price",
                                "high_dollars",
                            ),
                        "trade_price_low":
                            nested_float(
                                candle,
                                "price",
                                "low_dollars",
                            ),
                        "trade_price_mean":
                            nested_float(
                                candle,
                                "price",
                                "mean_dollars",
                            ),
                        "trade_price_close":
                            nested_float(
                                candle,
                                "price",
                                "close_dollars",
                            ),
                        "trade_price_previous":
                            nested_float(
                                candle,
                                "price",
                                "previous_dollars",
                            ),

                        "volume":
                            as_float(
                                candle.get(
                                    "volume_fp"
                                )
                            ),
                        "open_interest":
                            as_float(
                                candle.get(
                                    "open_interest_fp"
                                )
                            ),
                    }
                )

    df = pd.DataFrame(rows)

    df = df.sort_values(
        [
            "series_ticker",
            "event_date_local",
            "market_ticker",
            "candle_end_ts",
        ]
    ).reset_index(drop=True)

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_path = (
        PROCESSED_DIR
        / "market_panel_all.csv"
    )

    preclose_path = (
        PROCESSED_DIR
        / "market_panel_preclose.csv"
    )

    df.to_csv(
        all_path,
        index=False,
    )

    preclose = df[
        df["is_pre_close"] == True
    ].copy()

    preclose.to_csv(
        preclose_path,
        index=False,
    )

    # ---------------------------------------------------------
    # Settlement-label audit
    # ---------------------------------------------------------

    labels = (
        df[
            [
                "city",
                "event_ticker",
                "market_ticker",
                "outcome_yes",
            ]
        ]
        .drop_duplicates()
    )

    label_audit = (
        labels
        .groupby(
            [
                "city",
                "event_ticker",
            ]
        )
        .agg(
            markets=(
                "market_ticker",
                "nunique",
            ),
            known_results=(
                "outcome_yes",
                "count",
            ),
            yes_winners=(
                "outcome_yes",
                "sum",
            ),
        )
        .reset_index()
    )

    valid_labels = (
        (label_audit["markets"] == 6)
        & (
            label_audit["known_results"]
            == 6
        )
        & (
            label_audit["yes_winners"]
            == 1
        )
    )

    invalid_label_events = label_audit[
        ~valid_labels
    ]

    # ---------------------------------------------------------
    # Six-bucket distribution audit
    # ---------------------------------------------------------

    quote_rows = preclose.dropna(
        subset=[
            "midpoint_close",
            "spread_close",
        ]
    )

    distribution_audit = (
        quote_rows
        .groupby(
            [
                "city",
                "event_ticker",
                "timestamp_utc",
            ]
        )
        .agg(
            bucket_count=(
                "market_ticker",
                "nunique",
            ),
            midpoint_sum=(
                "midpoint_close",
                "sum",
            ),
            total_spread=(
                "spread_close",
                "sum",
            ),
        )
        .reset_index()
    )

    complete = distribution_audit[
        distribution_audit[
            "bucket_count"
        ] == 6
    ].copy()

    negative_spreads = int(
        (
            df["spread_close"].dropna()
            < 0
        ).sum()
    )

    summary_lines = []

    summary_lines.append(
        "Market panel audit"
    )
    summary_lines.append(
        "=" * 60
    )
    summary_lines.append(
        f"Raw event files: {len(files)}"
    )
    summary_lines.append(
        f"All candle rows: {len(df)}"
    )
    summary_lines.append(
        f"Pre-close candle rows: {len(preclose)}"
    )
    summary_lines.append(
        f"Unique city-days: "
        f"{df[['city', 'event_ticker']].drop_duplicates().shape[0]}"
    )
    summary_lines.append(
        f"Unique markets: "
        f"{df['market_ticker'].nunique()}"
    )
    summary_lines.append("")
    summary_lines.append(
        "Settlement label audit"
    )
    summary_lines.append(
        f"Events with exactly six markets "
        f"and exactly one YES winner: "
        f"{int(valid_labels.sum())}"
        f"/{len(label_audit)}"
    )
    summary_lines.append(
        f"Invalid label events: "
        f"{len(invalid_label_events)}"
    )
    summary_lines.append("")
    summary_lines.append(
        "Quote/distribution audit"
    )
    summary_lines.append(
        f"Negative bid-ask spreads: "
        f"{negative_spreads}"
    )
    summary_lines.append(
        f"Complete synchronized "
        f"6-bucket quote snapshots: "
        f"{len(complete)}"
    )

    if len(complete):
        quantiles = (
            complete["midpoint_sum"]
            .quantile(
                [
                    0.05,
                    0.25,
                    0.50,
                    0.75,
                    0.95,
                ]
            )
        )

        summary_lines.append(
            "Sum of six bucket midpoints:"
        )

        for q, value in quantiles.items():
            summary_lines.append(
                f"  q{int(q * 100):02d}: "
                f"{value:.4f}"
            )

        summary_lines.append(
            f"  mean: "
            f"{complete['midpoint_sum'].mean():.4f}"
        )

        summary_lines.append(
            f"Median total spread "
            f"across six buckets: "
            f"{complete['total_spread'].median():.4f}"
        )

    audit_path = (
        RESULTS_DIR
        / "market_panel_audit.txt"
    )

    audit_path.write_text(
        "\n".join(summary_lines)
        + "\n",
        encoding="utf-8",
    )

    distribution_audit.to_csv(
        RESULTS_DIR
        / "market_distribution_audit.csv",
        index=False,
    )

    invalid_label_events.to_csv(
        RESULTS_DIR
        / "market_label_anomalies.csv",
        index=False,
    )

    print("\n" + "\n".join(summary_lines))

    print("\nOutputs")
    print("-" * 60)
    print(all_path)
    print(preclose_path)
    print(audit_path)
    print(
        RESULTS_DIR
        / "market_distribution_audit.csv"
    )
    print(
        RESULTS_DIR
        / "market_label_anomalies.csv"
    )


if __name__ == "__main__":
    main()
