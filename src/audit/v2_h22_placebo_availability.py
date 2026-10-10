from pathlib import Path
import pandas as pd


EVENTS = Path(
    "results/v2_residual_assimilation/"
    "v2_h22_weather_revision_vectors.csv"
)

MARKET = Path(
    "data/processed/market_panel_all.csv"
)


def main():

    events = pd.read_csv(EVENTS)

    market = pd.read_csv(
        MARKET,
        usecols=[
            "city",
            "event_ticker",
            "market_ticker",
            "timestamp_utc",
            "midpoint_close",
            "is_pre_close",
        ],
    )

    events["pre_snapshot_utc"] = pd.to_datetime(
        events["pre_snapshot_utc"],
        utc=True,
    )

    market["timestamp_utc"] = pd.to_datetime(
        market["timestamp_utc"],
        utc=True,
    )

    rows = []

    for _, r in events.iterrows():

        placebo_start = (
            r["pre_snapshot_utc"]
            - pd.Timedelta(minutes=60)
        )

        sub = market[
            (market["city"] == r["city"])
            &
            (market["event_ticker"] == r["event_ticker"])
            &
            (market["timestamp_utc"] == placebo_start)
        ].copy()

        complete = (
            len(sub) == 6
            and sub["market_ticker"].nunique() == 6
            and sub["midpoint_close"].notna().all()
        )

        rows.append(
            {
                "event_date_local":
                    r["event_date_local"],

                "city":
                    r["city"],

                "event_ticker":
                    r["event_ticker"],

                "revision_sequence":
                    r["revision_sequence"],

                "transition":
                    r["transition"],

                "placebo_start_utc":
                    placebo_start.isoformat(),

                "pre_snapshot_utc":
                    r["pre_snapshot_utc"].isoformat(),

                "placebo_complete_six":
                    complete,

                "placebo_row_count":
                    len(sub),

                "placebo_market_count":
                    sub["market_ticker"].nunique(),
            }
        )

    out = pd.DataFrame(rows)

    path = Path(
        "results/v2_residual_assimilation/"
        "v2_h22_placebo_availability.csv"
    )

    out.to_csv(
        path,
        index=False,
    )

    print("=" * 88)
    print("H2.2 PRE-PUBLICATION PLACEBO AVAILABILITY AUDIT")
    print("=" * 88)

    print("Frozen H2.2 events:", len(out))
    print(
        "Complete exact PRE-60min snapshots:",
        int(out["placebo_complete_six"].sum())
    )
    print(
        "Unavailable/incomplete:",
        int((~out["placebo_complete_six"]).sum())
    )

    print()
    print("By city:")
    print(
        out.groupby("city")[
            "placebo_complete_six"
        ]
        .agg(["count", "sum"])
        .to_string()
    )

    print()
    print("By transition:")
    print(
        out.groupby("transition")[
            "placebo_complete_six"
        ]
        .agg(["count", "sum"])
        .to_string()
    )

    print()
    print("Saved:", path)

    print()
    print(
        "NO directional H2.2 or placebo statistic was computed."
    )


if __name__ == "__main__":
    main()
