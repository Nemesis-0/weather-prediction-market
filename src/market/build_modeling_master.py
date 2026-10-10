from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


MARKET_PATH = Path(
    "data/processed/market_panel_preclose.csv"
)

WEATHER_PATH = Path(
    "data/processed/weather_panel_primary.csv"
)

OUTPUT_DIR = Path("data/processed")
RESULTS_DIR = Path("results/development")

MAX_STALENESS_MINUTES = 60


def parse_bucket(label: str):
    """
    Returns:
      lower_f
      upper_f
      sort_key

    Unbounded side is represented as NaN.
    """

    label = str(label).strip()

    m = re.match(
        r"^(-?\d+)\s*°?\s*or below$",
        label,
        flags=re.I,
    )

    if m:
        upper = float(m.group(1))
        return np.nan, upper, -1e9

    m = re.match(
        r"^(-?\d+)\s*°?\s*to\s*(-?\d+)\s*°?$",
        label,
        flags=re.I,
    )

    if m:
        lower = float(m.group(1))
        upper = float(m.group(2))
        return lower, upper, lower

    m = re.match(
        r"^(-?\d+)\s*°?\s*or above$",
        label,
        flags=re.I,
    )

    if m:
        lower = float(m.group(1))
        return lower, np.nan, lower

    return np.nan, np.nan, np.nan


def main():
    market = pd.read_csv(MARKET_PATH)
    weather = pd.read_csv(WEATHER_PATH)

    # ---------------------------------------------------------
    # Parse UTC times
    # ---------------------------------------------------------

    market["timestamp_utc"] = pd.to_datetime(
        market["timestamp_utc"],
        utc=True,
    )

    weather["decision_time_utc"] = pd.to_datetime(
        weather["decision_time_utc"],
        utc=True,
    )

    weather["cycle_time_utc"] = pd.to_datetime(
        weather["cycle_time_utc"],
        utc=True,
    )

    weather["assumed_available_at_utc"] = pd.to_datetime(
        weather["assumed_available_at_utc"],
        utc=True,
    )

    weather["forecast_valid_time_utc"] = pd.to_datetime(
        weather["forecast_valid_time_utc"],
        utc=True,
    )

    # ---------------------------------------------------------
    # Attach frozen decision time to every market row
    # ---------------------------------------------------------

    decision_lookup = weather[
        [
            "city",
            "event_date_local",
            "decision_time_utc",
        ]
    ].copy()

    m = market.merge(
        decision_lookup,
        on=[
            "city",
            "event_date_local",
        ],
        how="left",
        validate="many_to_one",
    )

    # Never use future market information.
    eligible = m[
        m["timestamp_utc"]
        <= m["decision_time_utc"]
    ].copy()

    # Need valid bid/ask-derived quote information.
    eligible = eligible.dropna(
        subset=[
            "yes_bid_close",
            "yes_ask_close",
            "midpoint_close",
            "spread_close",
        ]
    )

    # ---------------------------------------------------------
    # Find synchronized six-bucket timestamps
    # ---------------------------------------------------------

    sync = (
        eligible
        .groupby(
            [
                "city",
                "event_date_local",
                "event_ticker",
                "timestamp_utc",
            ],
            as_index=False,
        )
        .agg(
            row_count=("market_ticker", "size"),
            bucket_count=(
                "market_ticker",
                "nunique",
            ),
        )
    )

    sync = sync[
        (sync["row_count"] == 6)
        & (sync["bucket_count"] == 6)
    ].copy()

    # Latest synchronized snapshot at/before decision time.
    chosen = (
        sync
        .sort_values("timestamp_utc")
        .groupby(
            [
                "city",
                "event_date_local",
                "event_ticker",
            ],
            as_index=False,
        )
        .tail(1)
        [
            [
                "city",
                "event_date_local",
                "event_ticker",
                "timestamp_utc",
            ]
        ]
        .rename(
            columns={
                "timestamp_utc":
                    "market_snapshot_utc"
            }
        )
    )

    selected = eligible.merge(
        chosen,
        left_on=[
            "city",
            "event_date_local",
            "event_ticker",
            "timestamp_utc",
        ],
        right_on=[
            "city",
            "event_date_local",
            "event_ticker",
            "market_snapshot_utc",
        ],
        how="inner",
        validate="many_to_one",
    )

    # ---------------------------------------------------------
    # Merge weather
    # ---------------------------------------------------------

    weather_cols = [
        "city",
        "event_date_local",
        "station",
        "timezone",
        "decision_time_local",
        "decision_time_utc",
        "cycle_time_utc",
        "assumed_available_at_utc",
        "forecast_valid_time_utc",
        "txn",
        "xnd",
        "tmp_at_valid_time",
        "tsd_at_valid_time",
        "archive_provider",
        "target_role",
    ]

    master = selected.merge(
        weather[weather_cols],
        on=[
            "city",
            "event_date_local",
        ],
        how="left",
        suffixes=(
            "_market",
            "_weather",
        ),
        validate="many_to_one",
    )

    # There are two copies after merge.
    decision_col = (
        "decision_time_utc_weather"
        if "decision_time_utc_weather"
        in master.columns
        else "decision_time_utc"
    )

    master["snapshot_age_minutes"] = (
        (
            master[decision_col]
            - master["market_snapshot_utc"]
        )
        .dt.total_seconds()
        / 60.0
    )

    master[
        "primary_market_snapshot_eligible"
    ] = (
        master["snapshot_age_minutes"]
        .between(
            0,
            MAX_STALENESS_MINUTES,
            inclusive="both",
        )
    )

    # ---------------------------------------------------------
    # Parse and order bucket definitions
    # ---------------------------------------------------------

    parsed = master["bucket_label"].apply(
        parse_bucket
    )

    master["bucket_lower_f"] = [
        x[0] for x in parsed
    ]

    master["bucket_upper_f"] = [
        x[1] for x in parsed
    ]

    master["_bucket_sort"] = [
        x[2] for x in parsed
    ]

    master = master.sort_values(
        [
            "city",
            "event_date_local",
            "_bucket_sort",
        ]
    ).reset_index(drop=True)

    master["bucket_index"] = (
        master
        .groupby(
            [
                "city",
                "event_date_local",
            ]
        )
        .cumcount()
        + 1
    )

    # ---------------------------------------------------------
    # Normalized Market-only probability
    # ---------------------------------------------------------

    master[
        "midpoint_sum"
    ] = master.groupby(
        [
            "city",
            "event_date_local",
        ]
    )["midpoint_close"].transform(
        "sum"
    )

    master[
        "market_prob_raw"
    ] = (
        master["midpoint_close"]
        / master["midpoint_sum"]
    )

    master[
        "total_spread"
    ] = master.groupby(
        [
            "city",
            "event_date_local",
        ]
    )["spread_close"].transform(
        "sum"
    )

    # ---------------------------------------------------------
    # Event-level QC
    # ---------------------------------------------------------

    event_qc = (
        master
        .groupby(
            [
                "city",
                "event_date_local",
                "event_ticker",
            ]
        )
        .agg(
            rows=(
                "market_ticker",
                "size",
            ),
            buckets=(
                "market_ticker",
                "nunique",
            ),
            winners=(
                "outcome_yes",
                "sum",
            ),
            prob_sum=(
                "market_prob_raw",
                "sum",
            ),
            midpoint_sum=(
                "midpoint_close",
                "sum",
            ),
            total_spread=(
                "spread_close",
                "sum",
            ),
            snapshot_age_minutes=(
                "snapshot_age_minutes",
                "first",
            ),
            eligible=(
                "primary_market_snapshot_eligible",
                "first",
            ),
            txn=("txn", "first"),
            xnd=("xnd", "first"),
        )
        .reset_index()
    )

    # Check bucket labels form a contiguous integer partition.
    partition_failures = []

    for keys, group in master.groupby(
        [
            "city",
            "event_date_local",
            "event_ticker",
        ]
    ):
        g = group.sort_values(
            "bucket_index"
        )

        if len(g) != 6:
            partition_failures.append(
                (*keys, "not_six_buckets")
            )
            continue

        if g[
            [
                "bucket_lower_f",
                "bucket_upper_f",
            ]
        ].isna().all(axis=1).any():
            partition_failures.append(
                (*keys, "unparsed_bucket")
            )
            continue

        ok = True

        for i in range(5):
            left = g.iloc[i]
            right = g.iloc[i + 1]

            left_upper = left[
                "bucket_upper_f"
            ]

            right_lower = right[
                "bucket_lower_f"
            ]

            if (
                pd.isna(left_upper)
                or pd.isna(right_lower)
                or left_upper + 1
                != right_lower
            ):
                ok = False
                break

        if not ok:
            partition_failures.append(
                (*keys, "noncontiguous_partition")
            )

    # ---------------------------------------------------------
    # Missing expected city-days
    # ---------------------------------------------------------

    expected = weather[
        [
            "city",
            "event_date_local",
        ]
    ].drop_duplicates()

    observed = event_qc[
        [
            "city",
            "event_date_local",
        ]
    ].drop_duplicates()

    missing_events = (
        expected.merge(
            observed,
            on=[
                "city",
                "event_date_local",
            ],
            how="left",
            indicator=True,
        )
        .query("_merge == 'left_only'")
        .drop(columns="_merge")
    )

    # ---------------------------------------------------------
    # Wide event-level modeling table
    # ---------------------------------------------------------

    event_rows = []

    for (
        city,
        event_date,
        event_ticker,
    ), group in master.groupby(
        [
            "city",
            "event_date_local",
            "event_ticker",
        ]
    ):
        g = group.sort_values(
            "bucket_index"
        )

        first = g.iloc[0]

        row = {
            "city": city,
            "event_date_local": event_date,
            "event_ticker": event_ticker,
            "decision_time_local":
                first["decision_time_local"],
            "decision_time_utc":
                first[decision_col],
            "market_snapshot_utc":
                first["market_snapshot_utc"],
            "snapshot_age_minutes":
                first["snapshot_age_minutes"],
            "station": first["station"],
            "cycle_time_utc":
                first["cycle_time_utc"],
            "assumed_available_at_utc":
                first[
                    "assumed_available_at_utc"
                ],
            "forecast_valid_time_utc":
                first[
                    "forecast_valid_time_utc"
                ],
            "txn": first["txn"],
            "xnd": first["xnd"],
            "midpoint_sum":
                first["midpoint_sum"],
            "total_spread":
                first["total_spread"],
        }

        winner = g.loc[
            g["outcome_yes"] == 1,
            "bucket_index",
        ]

        row["outcome_bucket_index"] = (
            int(winner.iloc[0])
            if len(winner) == 1
            else np.nan
        )

        for _, r in g.iterrows():
            k = int(r["bucket_index"])

            row[f"bucket_{k}_label"] = (
                r["bucket_label"]
            )
            row[f"bucket_{k}_lower_f"] = (
                r["bucket_lower_f"]
            )
            row[f"bucket_{k}_upper_f"] = (
                r["bucket_upper_f"]
            )
            row[f"bucket_{k}_bid"] = (
                r["yes_bid_close"]
            )
            row[f"bucket_{k}_ask"] = (
                r["yes_ask_close"]
            )
            row[f"bucket_{k}_midpoint"] = (
                r["midpoint_close"]
            )
            row[f"bucket_{k}_spread"] = (
                r["spread_close"]
            )
            row[f"bucket_{k}_market_prob"] = (
                r["market_prob_raw"]
            )
            row[f"bucket_{k}_outcome"] = (
                r["outcome_yes"]
            )

        event_rows.append(row)

    event_level = pd.DataFrame(
        event_rows
    ).sort_values(
        [
            "event_date_local",
            "city",
        ]
    )

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    long_path = (
        OUTPUT_DIR
        / "modeling_master_long.csv"
    )

    event_path = (
        OUTPUT_DIR
        / "modeling_master_event.csv"
    )

    master.drop(
        columns=["_bucket_sort"],
    ).to_csv(
        long_path,
        index=False,
    )

    event_level.to_csv(
        event_path,
        index=False,
    )

    event_qc.to_csv(
        RESULTS_DIR
        / "modeling_master_event_qc.csv",
        index=False,
    )

    missing_events.to_csv(
        RESULTS_DIR
        / "modeling_master_missing_events.csv",
        index=False,
    )

    if partition_failures:
        pd.DataFrame(
            partition_failures,
            columns=[
                "city",
                "event_date_local",
                "event_ticker",
                "problem",
            ],
        ).to_csv(
            RESULTS_DIR
            / "modeling_master_partition_failures.csv",
            index=False,
        )

    # ---------------------------------------------------------
    # Final audit
    # ---------------------------------------------------------

    exact_decision_snapshots = int(
        (
            event_qc[
                "snapshot_age_minutes"
            ] == 0
        ).sum()
    )

    eligible_events = int(
        event_qc["eligible"].sum()
    )

    bad_prob_sums = int(
        (
            ~np.isclose(
                event_qc["prob_sum"],
                1.0,
                atol=1e-10,
            )
        ).sum()
    )

    bad_winners = int(
        (
            event_qc["winners"] != 1
        ).sum()
    )

    bad_six = int(
        (
            (event_qc["rows"] != 6)
            | (event_qc["buckets"] != 6)
        ).sum()
    )

    missing_weather = int(
        (
            event_qc["txn"].isna()
            | event_qc["xnd"].isna()
        ).sum()
    )

    summary = [
        "Primary modeling master-table audit",
        "=" * 64,
        f"Expected city-days:               {len(expected)}",
        f"Observed city-days:               {len(event_qc)}",
        f"Long-table rows:                  {len(master)}",
        f"Missing city-days:                {len(missing_events)}",
        f"Events with six buckets:          {len(event_qc) - bad_six}",
        f"Events with one winner:           {len(event_qc) - bad_winners}",
        f"Events with weather:              {len(event_qc) - missing_weather}",
        f"Normalized-probability failures:  {bad_prob_sums}",
        f"Bucket-partition failures:        {len(partition_failures)}",
        "",
        f"Eligible <=60m snapshots:         {eligible_events}",
        f"Exact 10:00 snapshots:            {exact_decision_snapshots}",
        f"Snapshot age min:                 {event_qc['snapshot_age_minutes'].min():.1f} min",
        f"Snapshot age median:              {event_qc['snapshot_age_minutes'].median():.1f} min",
        f"Snapshot age max:                 {event_qc['snapshot_age_minutes'].max():.1f} min",
        "",
        "Selected-time market midpoint-sum:",
        f"  q05: {event_qc['midpoint_sum'].quantile(.05):.4f}",
        f"  q50: {event_qc['midpoint_sum'].quantile(.50):.4f}",
        f"  q95: {event_qc['midpoint_sum'].quantile(.95):.4f}",
        "",
        "Selected-time total spread:",
        f"  q05: {event_qc['total_spread'].quantile(.05):.4f}",
        f"  q50: {event_qc['total_spread'].quantile(.50):.4f}",
        f"  q95: {event_qc['total_spread'].quantile(.95):.4f}",
    ]

    critical_fail = any(
        [
            len(event_qc) != 138,
            len(missing_events) != 0,
            bad_six != 0,
            bad_winners != 0,
            missing_weather != 0,
            bad_prob_sums != 0,
            len(partition_failures) != 0,
            eligible_events != len(event_qc),
        ]
    )

    summary.extend(
        [
            "",
            "FINAL MASTER STATUS: "
            + (
                "PASS"
                if not critical_fail
                else "FAIL"
            ),
            "",
            f"Long table:  {long_path}",
            f"Event table: {event_path}",
        ]
    )

    audit_path = (
        RESULTS_DIR
        / "modeling_master_audit.txt"
    )

    audit_path.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print(
        "\n" + "\n".join(summary)
    )


if __name__ == "__main__":
    main()
