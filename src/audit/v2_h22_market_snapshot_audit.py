from pathlib import Path
import re
import numpy as np
import pandas as pd


ALIGN_PATH = Path(
    "results/v2_feasibility/v2_market_alignment_events.csv"
)

MARKET_PATH = Path(
    "data/processed/market_panel_all.csv"
)

SOURCE_PATH = Path(
    "src/audit/v2_market_alignment_feasibility.py"
)


def bool_col(s):
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False)
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "false": False,
            "1": True,
            "0": False,
        })
        .fillna(False)
        .astype(bool)
    )


def utc(s):
    return pd.to_datetime(
        s,
        utc=True,
        errors="coerce",
    )


def minutes(a, b):
    return (
        (a - b)
        .dt.total_seconds()
        / 60.0
    )


def check(name, condition):
    condition = bool(condition)
    print(
        f"{'PASS' if condition else 'FAIL'} | {name}"
    )
    return condition


def main():

    print("=" * 96)
    print("V2 H2.2 MARKET SNAPSHOT IMPLEMENTATION AUDIT")
    print("=" * 96)

    align = pd.read_csv(
        ALIGN_PATH
    )

    for c in [
        "any_weather_change",
        "clean_pre_post1h",
        "clean_pre_post2h",
        "pre_clean",
        "post1_clean",
        "post2_clean",
        "pre_after_old_publication",
        "pre_within_60",
        "post1_within_tolerance",
        "post2_within_tolerance",
        "post1_before_next_publication",
        "post2_before_next_publication",
    ]:
        if c in align.columns:
            align[c] = bool_col(
                align[c]
            )

    h22 = align[
        align["any_weather_change"]
        & align["clean_pre_post1h"]
        & align["clean_pre_post2h"]
    ].copy()

    print("\nPOPULATION")
    print("H2.2 rows:", len(h22))
    print(
        "dates:",
        h22["event_date_local"].nunique()
    )
    print(
        "cities:",
        h22["city"].value_counts().to_dict()
    )
    print(
        "transitions:",
        h22["transition"].value_counts().to_dict()
    )

    all_ok = True

    all_ok &= check(
        "exactly 179 frozen H2.2 events",
        len(h22) == 179,
    )

    time_cols = [
        "old_publication_time_utc",
        "new_publication_time_utc",
        "next_same_target_publication_utc",
        "pre_snapshot_utc",
        "post1_target_utc",
        "post1_snapshot_utc",
        "post2_target_utc",
        "post2_snapshot_utc",
    ]

    for c in time_cols:
        if c in h22.columns:
            h22[c] = utc(
                h22[c]
            )

    print("\nTIMING INVARIANTS")

    no_future_pre = (
        h22["pre_snapshot_utc"]
        <=
        h22["new_publication_time_utc"]
    )

    all_ok &= check(
        "PRE snapshot never after new weather publication",
        no_future_pre.all(),
    )

    pre_after_old = (
        h22["pre_snapshot_utc"]
        >=
        h22["old_publication_time_utc"]
    )

    all_ok &= check(
        "PRE snapshot never before old weather state became public",
        pre_after_old.all(),
    )

    ordered = (
        (
            h22["pre_snapshot_utc"]
            <
            h22["post1_snapshot_utc"]
        )
        &
        (
            h22["post1_snapshot_utc"]
            <
            h22["post2_snapshot_utc"]
        )
    )

    all_ok &= check(
        "PRE < POST1 < POST2 for every event",
        ordered.all(),
    )

    post1_after_new = (
        h22["post1_snapshot_utc"]
        >
        h22["new_publication_time_utc"]
    )

    post2_after_new = (
        h22["post2_snapshot_utc"]
        >
        h22["new_publication_time_utc"]
    )

    all_ok &= check(
        "POST1 occurs after new weather publication",
        post1_after_new.all(),
    )

    all_ok &= check(
        "POST2 occurs after new weather publication",
        post2_after_new.all(),
    )

    if (
        "next_same_target_publication_utc"
        in h22.columns
    ):
        has_next = (
            h22[
                "next_same_target_publication_utc"
            ].notna()
        )

        safe1 = (
            ~has_next
            |
            (
                h22["post1_snapshot_utc"]
                <
                h22[
                    "next_same_target_publication_utc"
                ]
            )
        )

        safe2 = (
            ~has_next
            |
            (
                h22["post2_snapshot_utc"]
                <
                h22[
                    "next_same_target_publication_utc"
                ]
            )
        )

        all_ok &= check(
            "POST1 strictly before next weather publication",
            safe1.all(),
        )

        all_ok &= check(
            "POST2 strictly before next weather publication",
            safe2.all(),
        )

    for c in [
        "pre_clean",
        "post1_clean",
        "post2_clean",
        "pre_after_old_publication",
        "pre_within_60",
        "post1_within_tolerance",
        "post2_within_tolerance",
        "post1_before_next_publication",
        "post2_before_next_publication",
    ]:
        if c in h22.columns:
            all_ok &= check(
                f"{c} true for all H2.2 events",
                h22[c].all(),
            )

    print("\nSTORED TIMING-METRIC CONSISTENCY")

    if "pre_staleness_minutes" in h22.columns:
        actual = minutes(
            h22["new_publication_time_utc"],
            h22["pre_snapshot_utc"],
        )

        stored = pd.to_numeric(
            h22["pre_staleness_minutes"],
            errors="coerce",
        )

        diff = (
            actual - stored
        ).abs()

        print(
            "max |computed-stored| PRE staleness minutes:",
            float(diff.max())
        )

        all_ok &= check(
            "PRE staleness field matches timestamps",
            np.allclose(
                actual,
                stored,
                atol=1e-6,
                equal_nan=True,
            ),
        )

    if "post1_lateness_minutes" in h22.columns:
        actual = minutes(
            h22["post1_snapshot_utc"],
            h22["post1_target_utc"],
        )

        stored = pd.to_numeric(
            h22["post1_lateness_minutes"],
            errors="coerce",
        )

        diff = (
            actual - stored
        ).abs()

        print(
            "max |computed-stored| POST1 lateness minutes:",
            float(diff.max())
        )

        all_ok &= check(
            "POST1 lateness field matches timestamps",
            np.allclose(
                actual,
                stored,
                atol=1e-6,
                equal_nan=True,
            ),
        )

    if "post2_lateness_minutes" in h22.columns:
        actual = minutes(
            h22["post2_snapshot_utc"],
            h22["post2_target_utc"],
        )

        stored = pd.to_numeric(
            h22["post2_lateness_minutes"],
            errors="coerce",
        )

        diff = (
            actual - stored
        ).abs()

        print(
            "max |computed-stored| POST2 lateness minutes:",
            float(diff.max())
        )

        all_ok &= check(
            "POST2 lateness field matches timestamps",
            np.allclose(
                actual,
                stored,
                atol=1e-6,
                equal_nan=True,
            ),
        )

    print("\nSIX-BUCKET SNAPSHOT AUDIT")

    market = pd.read_csv(
        MARKET_PATH,
        usecols=[
            "city",
            "event_ticker",
            "market_ticker",
            "bucket_label",
            "timestamp_utc",
            "midpoint_close",
            "is_pre_close",
        ],
    )

    market["timestamp_utc"] = utc(
        market["timestamp_utc"]
    )

    if "is_pre_close" in market.columns:
        market["is_pre_close"] = bool_col(
            market["is_pre_close"]
        )

    bad_snapshot_count = 0
    bad_ticker_set_count = 0
    bad_bucket_mapping_count = 0
    non_preclose_count = 0

    checked_snapshots = 0

    sample_bad = []

    for _, r in h22.iterrows():

        snapshot_sets = {}
        bucket_maps = {}

        for label, col in [
            ("PRE", "pre_snapshot_utc"),
            ("POST1", "post1_snapshot_utc"),
            ("POST2", "post2_snapshot_utc"),
        ]:

            sub = market[
                (market["city"] == r["city"])
                &
                (
                    market["event_ticker"]
                    == r["event_ticker"]
                )
                &
                (
                    market["timestamp_utc"]
                    == r[col]
                )
            ].copy()

            checked_snapshots += 1

            valid_six = (
                len(sub) == 6
                and
                sub["market_ticker"].nunique() == 6
                and
                sub["timestamp_utc"].nunique() == 1
                and
                sub["midpoint_close"].notna().all()
            )

            if not valid_six:
                bad_snapshot_count += 1

                if len(sample_bad) < 10:
                    sample_bad.append(
                        (
                            r["event_date_local"],
                            r["city"],
                            r["transition"],
                            label,
                            len(sub),
                            sub[
                                "market_ticker"
                            ].nunique(),
                        )
                    )

            if (
                len(sub)
                and
                not sub["is_pre_close"].all()
            ):
                non_preclose_count += 1

            snapshot_sets[label] = set(
                sub["market_ticker"].tolist()
            )

            bucket_maps[label] = dict(
                zip(
                    sub["market_ticker"],
                    sub["bucket_label"],
                )
            )

        if not (
            snapshot_sets["PRE"]
            ==
            snapshot_sets["POST1"]
            ==
            snapshot_sets["POST2"]
        ):
            bad_ticker_set_count += 1

        if not (
            bucket_maps["PRE"]
            ==
            bucket_maps["POST1"]
            ==
            bucket_maps["POST2"]
        ):
            bad_bucket_mapping_count += 1

    print(
        "snapshots checked:",
        checked_snapshots,
    )

    print(
        "invalid six-bucket snapshots:",
        bad_snapshot_count,
    )

    print(
        "events with inconsistent market-ticker sets:",
        bad_ticker_set_count,
    )

    print(
        "events with inconsistent ticker->bucket mappings:",
        bad_bucket_mapping_count,
    )

    print(
        "snapshots containing non-pre-close rows:",
        non_preclose_count,
    )

    all_ok &= check(
        "all 179 x 3 snapshots contain exactly six synchronized buckets",
        bad_snapshot_count == 0
        and checked_snapshots == 179 * 3,
    )

    all_ok &= check(
        "same six market tickers across PRE/POST1/POST2",
        bad_ticker_set_count == 0,
    )

    all_ok &= check(
        "same ticker-to-bucket mapping across PRE/POST1/POST2",
        bad_bucket_mapping_count == 0,
    )

    all_ok &= check(
        "all selected snapshots remain pre-close",
        non_preclose_count == 0,
    )

    if sample_bad:
        print("\nSAMPLE BAD SNAPSHOTS")
        for x in sample_bad:
            print(x)

    print("\nSOURCE-CODE INSPECTION EXCERPTS")
    print(
        "File:",
        SOURCE_PATH,
    )

    lines = (
        SOURCE_PATH
        .read_text()
        .splitlines()
    )

    pattern = re.compile(
        r"pre_snapshot|post1|post2|"
        r"next_same_target|publication|"
        r"tolerance|snapshot",
        re.IGNORECASE,
    )

    hits = [
        i
        for i, line in enumerate(lines)
        if pattern.search(line)
    ]

    ranges = []

    for i in hits:
        start = max(0, i - 3)
        end = min(len(lines), i + 4)

        if (
            not ranges
            or
            start > ranges[-1][1]
        ):
            ranges.append(
                [start, end]
            )
        else:
            ranges[-1][1] = max(
                ranges[-1][1],
                end,
            )

    shown = 0

    for start, end in ranges:
        for i in range(start, end):
            print(
                f"{i+1:04d}: {lines[i]}"
            )
            shown += 1

        print("----")

        if shown >= 220:
            print(
                "[source excerpt truncated after ~220 lines]"
            )
            break

    print("\n" + "=" * 96)

    if all_ok:
        print(
            "MECHANICAL DATA AUDIT STATUS: PASS"
        )
    else:
        print(
            "MECHANICAL DATA AUDIT STATUS: FAIL"
        )

    print(
        "NOTE: candle-end synchronization can be verified;"
    )
    print(
        "historical 60-minute candles cannot prove that all six underlying"
    )
    print(
        "order-book quotes updated at the exact same intra-hour instant."
    )

    print("=" * 96)


if __name__ == "__main__":
    main()
