from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PAIRS_PATH = Path(
    "results/v2_feasibility/"
    "v2_full_revision_pairs.csv"
)

MARKET_PATH = Path(
    "data/processed/"
    "market_panel_preclose.csv"
)

OUTDIR = Path(
    "results/v2_feasibility"
)

OUTDIR.mkdir(
    parents=True,
    exist_ok=True,
)

QUOTE_COLS = [
    "yes_bid_close",
    "yes_ask_close",
    "midpoint_close",
    "spread_close",
]

PRE_MAX_STALENESS_MIN = 60
POST_MAX_LATENESS_MIN = 60

GATE_MIN_EVENTS = 90
GATE_MIN_DATES = 30
GATE_MIN_PER_CITY = 20
GATE_MIN_PER_TRANSITION = 15


def select_pre(
    times: pd.DatetimeIndex,
    event_time: pd.Timestamp,
):
    candidates = times[
        times < event_time
    ]

    if len(candidates) == 0:
        return pd.NaT

    return candidates.max()


def select_post(
    times: pd.DatetimeIndex,
    target_time: pd.Timestamp,
):
    candidates = times[
        times >= target_time
    ]

    if len(candidates) == 0:
        return pd.NaT

    return candidates.min()


def iso(x):
    if pd.isna(x):
        return None

    return x.isoformat()


def main():
    pairs = pd.read_csv(
        PAIRS_PATH
    )

    market = pd.read_csv(
        MARKET_PATH
    )

    if len(pairs) != 414:
        raise RuntimeError(
            f"Expected 414 revision pairs; "
            f"found {len(pairs)}"
        )

    for col in [
        "old_publication_time_utc",
        "new_publication_time_utc",
    ]:
        pairs[col] = pd.to_datetime(
            pairs[col],
            utc=True,
        )

    market[
        "timestamp_utc"
    ] = pd.to_datetime(
        market[
            "timestamp_utc"
        ],
        utc=True,
    )

    # --------------------------------------------------
    # Determine the next same-target publication event.
    # --------------------------------------------------

    pairs = pairs.sort_values(
        [
            "event_date_local",
            "city",
            "revision_sequence",
        ]
    ).copy()

    pairs[
        "next_same_target_publication_utc"
    ] = (
        pairs.groupby(
            [
                "event_date_local",
                "city",
            ]
        )[
            "new_publication_time_utc"
        ]
        .shift(-1)
    )

    # --------------------------------------------------
    # Build complete synchronized six-bucket market states.
    # --------------------------------------------------

    market[
        "row_quotes_complete"
    ] = (
        market[
            QUOTE_COLS
        ]
        .notna()
        .all(
            axis=1
        )
    )

    snapshots = (
        market.groupby(
            [
                "city",
                "event_date_local",
                "event_ticker",
                "timestamp_utc",
            ],
            as_index=False,
        )
        .agg(
            row_count=(
                "market_ticker",
                "size",
            ),
            bucket_count=(
                "market_ticker",
                "nunique",
            ),
            all_quotes_complete=(
                "row_quotes_complete",
                "all",
            ),
        )
    )

    snapshots[
        "complete_six"
    ] = (
        (
            snapshots[
                "row_count"
            ]
            == 6
        )
        & (
            snapshots[
                "bucket_count"
            ]
            == 6
        )
        & snapshots[
            "all_quotes_complete"
        ]
    )

    complete = snapshots[
        snapshots[
            "complete_six"
        ]
    ].copy()

    # One event ticker per city-day is expected.
    ticker_map = (
        market[
            [
                "city",
                "event_date_local",
                "event_ticker",
            ]
        ]
        .drop_duplicates()
    )

    ticker_counts = (
        ticker_map.groupby(
            [
                "city",
                "event_date_local",
            ]
        )[
            "event_ticker"
        ]
        .nunique()
    )

    if (
        ticker_counts
        != 1
    ).any():
        raise RuntimeError(
            "Expected exactly one event ticker "
            "per city-day."
        )

    ticker_map = (
        ticker_map.drop_duplicates(
            [
                "city",
                "event_date_local",
            ]
        )
    )

    pairs = pairs.merge(
        ticker_map,
        on=[
            "city",
            "event_date_local",
        ],
        how="left",
        validate="many_to_one",
    )

    if pairs[
        "event_ticker"
    ].isna().any():
        raise RuntimeError(
            "Some revision pairs could not be "
            "mapped to a Kalshi event."
        )

    # Fast lookup of complete timestamps.
    time_lookup = {}

    for (
        city,
        event_date,
        event_ticker,
    ), g in complete.groupby(
        [
            "city",
            "event_date_local",
            "event_ticker",
        ]
    ):
        times = pd.DatetimeIndex(
            g[
                "timestamp_utc"
            ]
            .sort_values()
            .unique()
        )

        time_lookup[
            (
                city,
                event_date,
                event_ticker,
            )
        ] = times

    # --------------------------------------------------
    # Align every information event.
    # --------------------------------------------------

    records = []

    for row in pairs.itertuples(
        index=False
    ):
        key = (
            row.city,
            row.event_date_local,
            row.event_ticker,
        )

        times = time_lookup.get(
            key,
            pd.DatetimeIndex(
                [],
                tz="UTC",
            ),
        )

        old_pub = (
            row.old_publication_time_utc
        )

        event_time = (
            row.new_publication_time_utc
        )

        next_pub = (
            row.next_same_target_publication_utc
        )

        pre = select_pre(
            times,
            event_time,
        )

        if pd.notna(pre):
            pre_staleness = (
                (
                    event_time
                    - pre
                ).total_seconds()
                / 60.0
            )

            pre_within_60 = (
                0
                < pre_staleness
                <= PRE_MAX_STALENESS_MIN
            )

            pre_after_old = (
                pre
                >= old_pub
            )
        else:
            pre_staleness = np.nan
            pre_within_60 = False
            pre_after_old = False

        pre_clean = (
            pd.notna(pre)
            and pre_within_60
            and pre_after_old
        )

        post1_target = (
            event_time
            + pd.Timedelta(
                minutes=60
            )
        )

        post1 = select_post(
            times,
            post1_target,
        )

        if pd.notna(post1):
            post1_lateness = (
                (
                    post1
                    - post1_target
                ).total_seconds()
                / 60.0
            )

            post1_within_tolerance = (
                0
                <= post1_lateness
                <= POST_MAX_LATENESS_MIN
            )

            post1_before_next = (
                pd.isna(next_pub)
                or post1
                < next_pub
            )
        else:
            post1_lateness = np.nan
            post1_within_tolerance = False
            post1_before_next = False

        post1_clean = (
            pd.notna(post1)
            and post1_within_tolerance
            and post1_before_next
        )

        clean_1h = (
            pre_clean
            and post1_clean
        )

        post2_target = (
            event_time
            + pd.Timedelta(
                minutes=120
            )
        )

        post2 = select_post(
            times,
            post2_target,
        )

        if pd.notna(post2):
            post2_lateness = (
                (
                    post2
                    - post2_target
                ).total_seconds()
                / 60.0
            )

            post2_within_tolerance = (
                0
                <= post2_lateness
                <= POST_MAX_LATENESS_MIN
            )

            post2_before_next = (
                pd.isna(next_pub)
                or post2
                < next_pub
            )
        else:
            post2_lateness = np.nan
            post2_within_tolerance = False
            post2_before_next = False

        post2_clean = (
            pd.notna(post2)
            and post2_within_tolerance
            and post2_before_next
        )

        clean_2h = (
            pre_clean
            and post2_clean
        )

        records.append(
            {
                "event_date_local":
                    row.event_date_local,
                "city":
                    row.city,
                "station":
                    row.station,
                "event_ticker":
                    row.event_ticker,

                "revision_sequence":
                    row.revision_sequence,
                "transition":
                    row.transition,

                "old_state_label":
                    row.old_state_label,
                "new_state_label":
                    row.new_state_label,

                "old_publication_time_utc":
                    iso(old_pub),
                "new_publication_time_utc":
                    iso(event_time),
                "next_same_target_publication_utc":
                    iso(next_pub),

                "delta_txn":
                    row.delta_txn,
                "delta_xnd":
                    row.delta_xnd,
                "txn_changed":
                    bool(
                        row.txn_changed
                    ),
                "xnd_changed":
                    bool(
                        row.xnd_changed
                    ),
                "any_weather_change":
                    bool(
                        row.any_weather_change
                    ),

                "pre_snapshot_utc":
                    iso(pre),
                "pre_staleness_minutes":
                    pre_staleness,
                "pre_within_60":
                    pre_within_60,
                "pre_after_old_publication":
                    pre_after_old,
                "pre_clean":
                    pre_clean,

                "post1_target_utc":
                    iso(post1_target),
                "post1_snapshot_utc":
                    iso(post1),
                "post1_lateness_minutes":
                    post1_lateness,
                "post1_within_tolerance":
                    post1_within_tolerance,
                "post1_before_next_publication":
                    post1_before_next,
                "post1_clean":
                    post1_clean,

                "clean_pre_post1h":
                    clean_1h,

                "post2_target_utc":
                    iso(post2_target),
                "post2_snapshot_utc":
                    iso(post2),
                "post2_lateness_minutes":
                    post2_lateness,
                "post2_within_tolerance":
                    post2_within_tolerance,
                "post2_before_next_publication":
                    post2_before_next,
                "post2_clean":
                    post2_clean,

                "clean_pre_post2h":
                    clean_2h,
            }
        )

    alignment = pd.DataFrame(
        records
    )

    out_path = (
        OUTDIR
        / "v2_market_alignment_events.csv"
    )

    alignment.to_csv(
        out_path,
        index=False,
    )

    # --------------------------------------------------
    # Aggregate feasibility.
    # --------------------------------------------------

    changed = alignment[
        alignment[
            "any_weather_change"
        ]
    ].copy()

    clean_changed_1h = changed[
        changed[
            "clean_pre_post1h"
        ]
    ].copy()

    clean_changed_2h = changed[
        changed[
            "clean_pre_post2h"
        ]
    ].copy()

    n_clean = len(
        clean_changed_1h
    )

    n_dates = (
        clean_changed_1h[
            "event_date_local"
        ]
        .nunique()
    )

    by_city = (
        clean_changed_1h
        .groupby(
            "city"
        )
        .size()
        .reindex(
            [
                "NYC",
                "Chicago",
                "Denver",
            ],
            fill_value=0,
        )
    )

    transition_order = [
        "prev18Z->00Z",
        "00Z->06Z",
        "06Z->12Z",
    ]

    by_transition = (
        clean_changed_1h
        .groupby(
            "transition"
        )
        .size()
        .reindex(
            transition_order,
            fill_value=0,
        )
    )

    gate_events = (
        n_clean
        >= GATE_MIN_EVENTS
    )

    gate_dates = (
        n_dates
        >= GATE_MIN_DATES
    )

    gate_cities = bool(
        (
            by_city
            >= GATE_MIN_PER_CITY
        ).all()
    )

    gate_transitions = bool(
        (
            by_transition
            >= GATE_MIN_PER_TRANSITION
        ).all()
    )

    gate_pass = all(
        [
            gate_events,
            gate_dates,
            gate_cities,
            gate_transitions,
        ]
    )

    # --------------------------------------------------
    # Reasons events fail clean +1h.
    # --------------------------------------------------

    fail = changed[
        ~changed[
            "clean_pre_post1h"
        ]
    ].copy()

    reason_counts = {
        "no_clean_pre":
            int(
                (
                    ~fail[
                        "pre_clean"
                    ]
                ).sum()
            ),

        "pre_not_after_old_publication":
            int(
                (
                    ~fail[
                        "pre_after_old_publication"
                    ]
                ).sum()
            ),

        "pre_stale_or_missing":
            int(
                (
                    ~fail[
                        "pre_within_60"
                    ]
                ).sum()
            ),

        "post1_missing_or_outside_tolerance":
            int(
                (
                    ~fail[
                        "post1_within_tolerance"
                    ]
                ).sum()
            ),

        "post1_overlaps_next_weather_update":
            int(
                (
                    fail[
                        "post1_within_tolerance"
                    ]
                    & (
                        ~fail[
                            "post1_before_next_publication"
                        ]
                    )
                ).sum()
            ),
    }

    # --------------------------------------------------
    # Coverage tables.
    # --------------------------------------------------

    transition_summary = (
        alignment.groupby(
            "transition"
        )
        .agg(
            all_events=(
                "transition",
                "size",
            ),
            changed_events=(
                "any_weather_change",
                "sum",
            ),
            clean_all_1h=(
                "clean_pre_post1h",
                "sum",
            ),
        )
        .reset_index()
    )

    clean_changed_counts = (
        clean_changed_1h
        .groupby(
            "transition"
        )
        .size()
        .rename(
            "clean_changed_1h"
        )
        .reset_index()
    )

    transition_summary = (
        transition_summary.merge(
            clean_changed_counts,
            on="transition",
            how="left",
        )
        .fillna(
            {
                "clean_changed_1h":
                    0
            }
        )
    )

    transition_summary[
        "clean_changed_1h"
    ] = (
        transition_summary[
            "clean_changed_1h"
        ]
        .astype(int)
    )

    transition_summary.to_csv(
        OUTDIR
        / "v2_market_alignment_transition_summary.csv",
        index=False,
    )

    city_summary = (
        changed.groupby(
            "city"
        )
        .agg(
            changed_events=(
                "any_weather_change",
                "size",
            ),
            clean_changed_1h=(
                "clean_pre_post1h",
                "sum",
            ),
            clean_changed_2h=(
                "clean_pre_post2h",
                "sum",
            ),
        )
        .reset_index()
    )

    city_summary.to_csv(
        OUTDIR
        / "v2_market_alignment_city_summary.csv",
        index=False,
    )

    # --------------------------------------------------
    # Report.
    # --------------------------------------------------

    lines = [
        "V2 MARKET-ALIGNMENT FEASIBILITY AUDIT",
        "=" * 92,
        "",
        f"All revision events:                         {len(alignment)}",
        f"Weather-changing revision events:            {len(changed)}",
        "",
        f"All events with clean PRE + POST1H:          {int(alignment['clean_pre_post1h'].sum())}",
        f"Changed events with clean PRE + POST1H:      {len(clean_changed_1h)}",
        f"Distinct dates represented at clean +1H:     {n_dates}",
        "",
        f"Changed events with clean PRE + POST2H:      {len(clean_changed_2h)}",
        "",
        "Clean changed +1H events by city:",
        by_city.to_string(),
        "",
        "Clean changed +1H events by transition:",
        by_transition.to_string(),
        "",
        "Changed-event +1H failure diagnostics:",
    ]

    for name, value in (
        reason_counts.items()
    ):
        lines.append(
            f"  {name}: {value}"
        )

    lines.extend(
        [
            "",
            "Transition coverage:",
            transition_summary.to_string(
                index=False
            ),
            "",
            "Gate D frozen thresholds:",
            (
                f"  >= {GATE_MIN_EVENTS} clean changed events: "
                f"{n_clean} -> "
                f"{'PASS' if gate_events else 'FAIL'}"
            ),
            (
                f"  >= {GATE_MIN_DATES} distinct dates: "
                f"{n_dates} -> "
                f"{'PASS' if gate_dates else 'FAIL'}"
            ),
            (
                f"  >= {GATE_MIN_PER_CITY} per city: "
                f"{'PASS' if gate_cities else 'FAIL'}"
            ),
            (
                f"  >= {GATE_MIN_PER_TRANSITION} per transition: "
                f"{'PASS' if gate_transitions else 'FAIL'}"
            ),
            "",
            (
                "FINAL GATE D STATUS: "
                + (
                    "PASS"
                    if gate_pass
                    else "FAIL / REDESIGN REQUIRED"
                )
            ),
            "",
            "Interpretation restriction:",
            (
                "This audit evaluates market-state availability and "
                "event isolation only."
            ),
            (
                "No market-reaction direction, settlement outcome, "
                "forecast performance, or PnL was evaluated."
            ),
        ]
    )

    report = "\n".join(
        lines
    ) + "\n"

    report_path = (
        OUTDIR
        / "v2_market_alignment_feasibility.txt"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print()
    print(report)

    print(
        "Saved:"
    )
    print(
        f"  {out_path}"
    )
    print(
        "  results/v2_feasibility/"
        "v2_market_alignment_transition_summary.csv"
    )
    print(
        "  results/v2_feasibility/"
        "v2_market_alignment_city_summary.csv"
    )
    print(
        f"  {report_path}"
    )


if __name__ == "__main__":
    main()
