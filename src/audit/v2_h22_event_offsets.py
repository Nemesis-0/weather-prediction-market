from pathlib import Path
import pandas as pd


INPUT = Path(
    "results/v2_residual_assimilation/"
    "v2_residual_events.csv"
)

OUTPUT = Path(
    "results/v2_residual_assimilation/"
    "v2_h22_event_offsets.csv"
)


def main():

    df = pd.read_csv(INPUT)

    time_cols = [
        "pre_snapshot_utc",
        "post1_snapshot_utc",
        "post2_snapshot_utc",
    ]

    for c in time_cols:
        df[c] = pd.to_datetime(df[c], utc=True)

    # weather publication time is reconstructed from revision timing
    # use transition-specific available timestamps
    pairs = pd.read_csv(
        "results/v2_feasibility/"
        "v2_market_alignment_events.csv"
    )

    pairs["new_publication_time_utc"] = pd.to_datetime(
        pairs["new_publication_time_utc"],
        utc=True,
    )

    key = [
        "event_date_local",
        "city",
        "transition",
    ]

    merged = df.merge(
        pairs[
            key
            +
            [
                "new_publication_time_utc",
            ]
        ],
        on=key,
        how="left",
        validate="one_to_one",
    )

    merged["pre_offset_minutes"] = (
        (
            merged["pre_snapshot_utc"]
            -
            merged["new_publication_time_utc"]
        )
        .dt.total_seconds()
        /
        60
    )

    merged["post1_offset_minutes"] = (
        (
            merged["post1_snapshot_utc"]
            -
            merged["new_publication_time_utc"]
        )
        .dt.total_seconds()
        /
        60
    )

    merged["post2_offset_minutes"] = (
        (
            merged["post2_snapshot_utc"]
            -
            merged["new_publication_time_utc"]
        )
        .dt.total_seconds()
        /
        60
    )


    cols = [
        "event_date_local",
        "city",
        "transition",
        "new_publication_time_utc",
        "pre_snapshot_utc",
        "post1_snapshot_utc",
        "post2_snapshot_utc",
        "pre_offset_minutes",
        "post1_offset_minutes",
        "post2_offset_minutes",
    ]

    out = merged[cols].copy()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.to_csv(
        OUTPUT,
        index=False,
    )


    print("="*88)
    print(
        "V2 H2.2 EVENT OFFSET AUDIT"
    )
    print("="*88)

    print(
        "Rows:",
        len(out)
    )

    print()
    print(
        "PRE offset summary"
    )
    print(
        out["pre_offset_minutes"]
        .describe()
    )

    print()
    print(
        "POST1 offset summary"
    )
    print(
        out["post1_offset_minutes"]
        .describe()
    )

    print()
    print(
        "POST2 offset summary"
    )
    print(
        out["post2_offset_minutes"]
        .describe()
    )


    print()
    print(
        "Saved:"
    )
    print(
        OUTPUT
    )


if __name__ == "__main__":
    main()
