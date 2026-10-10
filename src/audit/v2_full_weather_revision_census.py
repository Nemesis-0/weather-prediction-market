from __future__ import annotations

import time
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests


WEATHER_V1_PATH = Path(
    "data/processed/weather_panel_primary.csv"
)

OUTDIR = Path(
    "results/v2_feasibility"
)

OUTDIR.mkdir(
    parents=True,
    exist_ok=True,
)

CITY = {
    "NYC": "KNYC",
    "Chicago": "KMDW",
    "Denver": "KDEN",
}

# Same-target forecast states identified in the pilot.
STATE_SPECS = [
    (-1, 18, "prev18Z", 0),
    (0, 0, "00Z", 1),
    (0, 6, "06Z", 2),
    (0, 12, "12Z", 3),
]

IEM_URL = (
    "https://mesonet.agron.iastate.edu/"
    "api/1/mos.json"
)

NOAA_TEMPLATE = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.{date}/{hour:02d}/text/"
    "blend_nbstx.t{hour:02d}z"
)

MAX_RETRIES = 7


def to_utc(x):
    ts = pd.Timestamp(x)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


def target_valid_time(event_date):
    d = (
        pd.Timestamp(event_date)
        + pd.Timedelta(days=1)
    )

    return pd.Timestamp(
        d.strftime("%Y-%m-%d")
        + "T00:00:00Z"
    )


def fetch_head(
    session,
    cycle,
):
    url = NOAA_TEMPLATE.format(
        date=cycle.strftime("%Y%m%d"),
        hour=cycle.hour,
    )

    for attempt in range(MAX_RETRIES):
        try:
            r = session.head(
                url,
                timeout=30,
                allow_redirects=True,
            )
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise

            time.sleep(
                min(
                    2 ** attempt,
                    30,
                )
            )
            continue

        if r.status_code == 429:
            time.sleep(
                min(
                    2 ** attempt,
                    45,
                )
            )
            continue

        published = None

        if (
            r.status_code == 200
            and r.headers.get(
                "Last-Modified"
            )
        ):
            published = to_utc(
                parsedate_to_datetime(
                    r.headers[
                        "Last-Modified"
                    ]
                )
            )

        return {
            "noaa_url":
                url,
            "noaa_http_status":
                r.status_code,
            "publication_time_utc":
                published,
            "etag":
                r.headers.get(
                    "ETag"
                ),
            "content_length":
                r.headers.get(
                    "Content-Length"
                ),
        }

    raise RuntimeError(
        f"NOAA HEAD retries exhausted: {url}"
    )


def fetch_iem(
    session,
    station,
    cycle,
    event_date,
):
    runtime = cycle.strftime(
        "%Y-%m-%d %H:%MZ"
    )

    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(
                IEM_URL,
                params={
                    "station": station,
                    "model": "NBS",
                    "runtime": runtime,
                },
                timeout=30,
            )
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise

            time.sleep(
                min(
                    2 ** attempt,
                    30,
                )
            )
            continue

        if r.status_code == 429:
            time.sleep(
                min(
                    2 ** attempt,
                    45,
                )
            )
            continue

        if r.status_code != 200:
            return {
                "iem_http_status":
                    r.status_code,
                "target_rows":
                    0,
                "txn":
                    None,
                "xnd":
                    None,
                "iem_runtime_values":
                    None,
            }

        payload = r.json()

        target = target_valid_time(
            event_date
        )

        matches = []

        runtime_values = []

        for row in payload.get(
            "data",
            [],
        ):
            rv = row.get(
                "runtime"
            )

            if rv is not None:
                runtime_values.append(
                    str(rv)
                )

            ftime = row.get(
                "ftime_utc"
            )

            if not ftime:
                continue

            try:
                ftime_ts = to_utc(
                    ftime
                )
            except Exception:
                continue

            if (
                ftime_ts == target
                and row.get("txn")
                is not None
                and row.get("xnd")
                is not None
            ):
                matches.append(row)

        if len(matches) == 1:
            return {
                "iem_http_status": 200,
                "target_rows": 1,
                "txn":
                    float(
                        matches[0]["txn"]
                    ),
                "xnd":
                    float(
                        matches[0]["xnd"]
                    ),
                "iem_runtime_values":
                    "|".join(
                        sorted(
                            set(
                                runtime_values
                            )
                        )
                    ),
            }

        return {
            "iem_http_status": 200,
            "target_rows":
                len(matches),
            "txn": None,
            "xnd": None,
            "iem_runtime_values":
                "|".join(
                    sorted(
                        set(
                            runtime_values
                        )
                    )
                ),
        }

    raise RuntimeError(
        "IEM retries exhausted."
    )


def main():
    base = pd.read_csv(
        WEATHER_V1_PATH
    )

    dates = sorted(
        base[
            "event_date_local"
        ].unique()
    )

    if len(dates) != 46:
        raise RuntimeError(
            f"Expected 46 V1 dates, "
            f"found {len(dates)}"
        )

    session = requests.Session()

    # --------------------------------------------------
    # Build unique NOAA cycle metadata once.
    # Same NOAA bulletin object covers all stations.
    # --------------------------------------------------

    cycle_meta = {}

    unique_cycles = []

    for event_date in dates:
        base_date = pd.Timestamp(
            event_date
        ).date()

        for (
            day_offset,
            hour,
            label,
            nominal_order,
        ) in STATE_SPECS:

            cycle_date = (
                base_date
                + timedelta(
                    days=day_offset
                )
            )

            cycle = pd.Timestamp(
                year=cycle_date.year,
                month=cycle_date.month,
                day=cycle_date.day,
                hour=hour,
                tz="UTC",
            )

            key = (
                event_date,
                label,
            )

            unique_cycles.append(
                (
                    key,
                    cycle,
                    nominal_order,
                )
            )

    print()
    print(
        "V2 FULL WEATHER REVISION CENSUS"
    )
    print("=" * 92)

    print(
        f"Event dates:          {len(dates)}"
    )
    print(
        f"Unique NOAA objects:  {len(unique_cycles)}"
    )

    print()
    print(
        "Fetching NOAA publication metadata..."
    )

    for i, (
        key,
        cycle,
        nominal_order,
    ) in enumerate(
        unique_cycles,
        start=1,
    ):
        meta = fetch_head(
            session,
            cycle,
        )

        publication = (
            meta[
                "publication_time_utc"
            ]
        )

        lag = (
            (
                publication
                - cycle
            ).total_seconds()
            / 60.0
            if publication
            is not None
            else np.nan
        )

        cycle_meta[key] = {
            **meta,
            "cycle_time_utc":
                cycle,
            "nominal_order":
                nominal_order,
            "publication_lag_minutes":
                lag,
        }

        if (
            i == 1
            or i % 20 == 0
            or i == len(
                unique_cycles
            )
        ):
            print(
                f"  NOAA {i:3d}/"
                f"{len(unique_cycles)}"
            )

        time.sleep(0.05)

    # --------------------------------------------------
    # IEM values for each city/state.
    # --------------------------------------------------

    rows = []

    total_requests = (
        len(dates)
        * len(CITY)
        * len(STATE_SPECS)
    )

    request_no = 0

    print()
    print(
        "Fetching IEM parsed TXN/XND states..."
    )

    for event_date in dates:
        base_date = pd.Timestamp(
            event_date
        ).date()

        for city, station in (
            CITY.items()
        ):

            for (
                day_offset,
                hour,
                label,
                nominal_order,
            ) in STATE_SPECS:

                request_no += 1

                cycle_date = (
                    base_date
                    + timedelta(
                        days=day_offset
                    )
                )

                cycle = pd.Timestamp(
                    year=cycle_date.year,
                    month=cycle_date.month,
                    day=cycle_date.day,
                    hour=hour,
                    tz="UTC",
                )

                meta = cycle_meta[
                    (
                        event_date,
                        label,
                    )
                ]

                iem = fetch_iem(
                    session,
                    station,
                    cycle,
                    event_date,
                )

                published = (
                    meta[
                        "publication_time_utc"
                    ]
                )

                usable = (
                    meta[
                        "noaa_http_status"
                    ]
                    == 200
                    and published
                    is not None
                    and iem[
                        "target_rows"
                    ]
                    == 1
                )

                missing_reason = None

                if (
                    meta[
                        "noaa_http_status"
                    ]
                    != 200
                ):
                    missing_reason = (
                        "noaa_object_missing"
                    )

                elif published is None:
                    missing_reason = (
                        "no_publication_timestamp"
                    )

                elif (
                    iem[
                        "iem_http_status"
                    ]
                    != 200
                ):
                    missing_reason = (
                        "iem_request_failure"
                    )

                elif (
                    iem[
                        "target_rows"
                    ]
                    == 0
                ):
                    missing_reason = (
                        "target_txn_xnd_missing"
                    )

                elif (
                    iem[
                        "target_rows"
                    ]
                    > 1
                ):
                    missing_reason = (
                        "duplicate_target_rows"
                    )

                rows.append(
                    {
                        "event_date_local":
                            event_date,
                        "city":
                            city,
                        "station":
                            station,

                        "state_label":
                            label,
                        "nominal_order":
                            nominal_order,

                        "cycle_time_utc":
                            cycle,
                        "target_valid_time_utc":
                            target_valid_time(
                                event_date
                            ),

                        "noaa_http_status":
                            meta[
                                "noaa_http_status"
                            ],
                        "noaa_url":
                            meta[
                                "noaa_url"
                            ],
                        "publication_time_utc":
                            published,
                        "publication_lag_minutes":
                            meta[
                                "publication_lag_minutes"
                            ],
                        "etag":
                            meta[
                                "etag"
                            ],
                        "content_length":
                            meta[
                                "content_length"
                            ],

                        "iem_http_status":
                            iem[
                                "iem_http_status"
                            ],
                        "target_rows":
                            iem[
                                "target_rows"
                            ],
                        "iem_runtime_values":
                            iem[
                                "iem_runtime_values"
                            ],

                        "txn":
                            iem[
                                "txn"
                            ],
                        "xnd":
                            iem[
                                "xnd"
                            ],

                        "usable_state":
                            usable,
                        "missing_reason":
                            missing_reason,
                    }
                )

                if (
                    request_no == 1
                    or request_no % 50 == 0
                    or request_no
                    == total_requests
                ):
                    print(
                        f"  IEM {request_no:3d}/"
                        f"{total_requests}"
                    )

                time.sleep(0.08)

    states = pd.DataFrame(
        rows
    )

    states[
        "publication_time_utc"
    ] = pd.to_datetime(
        states[
            "publication_time_utc"
        ],
        utc=True,
    )

    states[
        "cycle_time_utc"
    ] = pd.to_datetime(
        states[
            "cycle_time_utc"
        ],
        utc=True,
    )

    states_path = (
        OUTDIR
        / "v2_full_forecast_states.csv"
    )

    states.to_csv(
        states_path,
        index=False,
    )

    # --------------------------------------------------
    # Structural audit by city-day.
    # --------------------------------------------------

    usable = states[
        states[
            "usable_state"
        ]
    ].copy()

    cityday_counts = (
        usable.groupby(
            [
                "event_date_local",
                "city",
            ]
        )
        .size()
        .rename(
            "usable_states"
        )
        .reset_index()
    )

    all_citydays = (
        states[
            [
                "event_date_local",
                "city",
            ]
        ]
        .drop_duplicates()
    )

    cityday_counts = (
        all_citydays.merge(
            cityday_counts,
            on=[
                "event_date_local",
                "city",
            ],
            how="left",
        )
        .fillna(
            {
                "usable_states": 0
            }
        )
    )

    cityday_counts[
        "usable_states"
    ] = cityday_counts[
        "usable_states"
    ].astype(int)

    # --------------------------------------------------
    # Check publication-order consistency.
    # --------------------------------------------------

    order_audit_rows = []

    for (
        event_date,
        city,
    ), g in usable.groupby(
        [
            "event_date_local",
            "city",
        ]
    ):
        nominal = (
            g.sort_values(
                "nominal_order"
            )
        )

        publication = (
            g.sort_values(
                "publication_time_utc"
            )
        )

        nominal_labels = list(
            nominal[
                "state_label"
            ]
        )

        publication_labels = list(
            publication[
                "state_label"
            ]
        )

        order_audit_rows.append(
            {
                "event_date_local":
                    event_date,
                "city":
                    city,
                "nominal_chain":
                    "->".join(
                        nominal_labels
                    ),
                "publication_chain":
                    "->".join(
                        publication_labels
                    ),
                "publication_order_matches_nominal":
                    nominal_labels
                    == publication_labels,
            }
        )

    order_audit = pd.DataFrame(
        order_audit_rows
    )

    order_audit.to_csv(
        OUTDIR
        / "v2_publication_order_audit.csv",
        index=False,
    )

    # --------------------------------------------------
    # Build sequential revision pairs by ACTUAL
    # publication order, not nominal cycle order.
    # --------------------------------------------------

    pair_rows = []

    for (
        event_date,
        city,
    ), g in usable.groupby(
        [
            "event_date_local",
            "city",
        ]
    ):
        g = g.sort_values(
            [
                "publication_time_utc",
                "cycle_time_utc",
            ]
        )

        recs = list(
            g.itertuples(
                index=False
            )
        )

        for seq_no, (
            old,
            new,
        ) in enumerate(
            zip(
                recs[:-1],
                recs[1:],
            ),
            start=1,
        ):
            gap = (
                new.publication_time_utc
                - old.publication_time_utc
            ).total_seconds() / 60.0

            pair_rows.append(
                {
                    "event_date_local":
                        event_date,
                    "city":
                        city,
                    "station":
                        old.station,

                    "revision_sequence":
                        seq_no,

                    "old_state_label":
                        old.state_label,
                    "new_state_label":
                        new.state_label,

                    "transition":
                        (
                            f"{old.state_label}"
                            f"->{new.state_label}"
                        ),

                    "old_nominal_order":
                        old.nominal_order,
                    "new_nominal_order":
                        new.nominal_order,

                    "old_cycle_time_utc":
                        old.cycle_time_utc,
                    "new_cycle_time_utc":
                        new.cycle_time_utc,

                    "old_publication_time_utc":
                        old.publication_time_utc,
                    "new_publication_time_utc":
                        new.publication_time_utc,

                    "inter_publication_gap_minutes":
                        gap,

                    "old_txn":
                        old.txn,
                    "new_txn":
                        new.txn,
                    "delta_txn":
                        (
                            new.txn
                            - old.txn
                        ),

                    "old_xnd":
                        old.xnd,
                    "new_xnd":
                        new.xnd,
                    "delta_xnd":
                        (
                            new.xnd
                            - old.xnd
                        ),

                    "txn_changed":
                        (
                            new.txn
                            != old.txn
                        ),

                    "xnd_changed":
                        (
                            new.xnd
                            != old.xnd
                        ),

                    "any_weather_change":
                        (
                            new.txn
                            != old.txn
                            or new.xnd
                            != old.xnd
                        ),

                    "publication_order_reversal":
                        (
                            new.nominal_order
                            <= old.nominal_order
                        ),
                }
            )

    pairs = pd.DataFrame(
        pair_rows
    )

    pairs_path = (
        OUTDIR
        / "v2_full_revision_pairs.csv"
    )

    pairs.to_csv(
        pairs_path,
        index=False,
    )

    # --------------------------------------------------
    # Aggregate diagnostics.
    # --------------------------------------------------

    total_states = len(states)

    usable_states = int(
        states[
            "usable_state"
        ].sum()
    )

    expected_states = (
        len(dates)
        * len(CITY)
        * len(STATE_SPECS)
    )

    missing_states = (
        expected_states
        - usable_states
    )

    full_four = int(
        (
            cityday_counts[
                "usable_states"
            ]
            == 4
        ).sum()
    )

    at_least_three = int(
        (
            cityday_counts[
                "usable_states"
            ]
            >= 3
        ).sum()
    )

    zero_pairs = int(
        (
            cityday_counts[
                "usable_states"
            ]
            < 2
        ).sum()
    )

    publication_reversals = int(
        (
            ~order_audit[
                "publication_order_matches_nominal"
            ]
        ).sum()
    )

    pair_reversals = int(
        pairs[
            "publication_order_reversal"
        ].sum()
    )

    any_change = int(
        pairs[
            "any_weather_change"
        ].sum()
    )

    txn_change = int(
        pairs[
            "txn_changed"
        ].sum()
    )

    xnd_change = int(
        pairs[
            "xnd_changed"
        ].sum()
    )

    # Transition distribution.
    transition_summary = (
        pairs.groupby(
            "transition"
        )
        .agg(
            revision_pairs=(
                "transition",
                "size",
            ),
            txn_change_rate=(
                "txn_changed",
                "mean",
            ),
            xnd_change_rate=(
                "xnd_changed",
                "mean",
            ),
            any_change_rate=(
                "any_weather_change",
                "mean",
            ),
            median_abs_delta_txn=(
                "delta_txn",
                lambda x:
                    float(
                        np.median(
                            np.abs(x)
                        )
                    ),
            ),
            median_gap_minutes=(
                "inter_publication_gap_minutes",
                "median",
            ),
        )
        .reset_index()
    )

    transition_summary.to_csv(
        OUTDIR
        / "v2_revision_transition_summary.csv",
        index=False,
    )

    missing_summary = (
        states.loc[
            ~states[
                "usable_state"
            ],
            "missing_reason",
        ]
        .value_counts(
            dropna=False
        )
    )

    publication_lag = (
        usable[
            "publication_lag_minutes"
        ]
        .dropna()
    )

    pair_gap = (
        pairs[
            "inter_publication_gap_minutes"
        ]
        .dropna()
    )

    abs_delta_txn = (
        pairs[
            "delta_txn"
        ]
        .abs()
    )

    abs_delta_xnd = (
        pairs[
            "delta_xnd"
        ]
        .abs()
    )

    # --------------------------------------------------
    # Report.
    # --------------------------------------------------

    lines = [
        "V2 FULL WEATHER REVISION FEASIBILITY CENSUS",
        "=" * 92,
        "",
        f"Calendar dates examined:              {len(dates)}",
        f"City-days examined:                  {len(cityday_counts)}",
        f"Expected forecast states:            {expected_states}",
        f"Observed state records:              {total_states}",
        f"Usable forecast states:              {usable_states}",
        f"Missing/unusable forecast states:    {missing_states}",
        "",
        f"City-days with all 4 states:         {full_four}",
        f"City-days with >=3 states:           {at_least_three}",
        f"City-days with <2 states:            {zero_pairs}",
        "",
        f"Sequential revision pairs:           {len(pairs)}",
        f"Pairs with TXN change:               {txn_change}",
        f"Pairs with XND change:               {xnd_change}",
        f"Pairs with any TXN/XND change:       {any_change}",
        "",
        (
            "City-days where actual publication order "
            f"differs from nominal order:          {publication_reversals}"
        ),
        f"Pair-level nominal-order reversals:   {pair_reversals}",
        "",
    ]

    if len(publication_lag):
        lines.extend(
            [
                "Publication lag among usable states:",
                (
                    f"  min:    "
                    f"{publication_lag.min():.1f} min"
                ),
                (
                    f"  median: "
                    f"{publication_lag.median():.1f} min"
                ),
                (
                    f"  p95:    "
                    f"{publication_lag.quantile(.95):.1f} min"
                ),
                (
                    f"  max:    "
                    f"{publication_lag.max():.1f} min"
                ),
                "",
            ]
        )

    if len(pair_gap):
        lines.extend(
            [
                "Sequential inter-publication gaps:",
                (
                    f"  min:    "
                    f"{pair_gap.min():.1f} min"
                ),
                (
                    f"  median: "
                    f"{pair_gap.median():.1f} min"
                ),
                (
                    f"  p05:    "
                    f"{pair_gap.quantile(.05):.1f} min"
                ),
                (
                    f"  p95:    "
                    f"{pair_gap.quantile(.95):.1f} min"
                ),
                (
                    f"  max:    "
                    f"{pair_gap.max():.1f} min"
                ),
                "",
            ]
        )

    if len(abs_delta_txn):
        lines.extend(
            [
                "Absolute TXN revision size:",
                (
                    f"  zero-rate: "
                    f"{(abs_delta_txn == 0).mean():.3f}"
                ),
                (
                    f"  median:    "
                    f"{abs_delta_txn.median():.2f} F"
                ),
                (
                    f"  p90:       "
                    f"{abs_delta_txn.quantile(.90):.2f} F"
                ),
                (
                    f"  max:       "
                    f"{abs_delta_txn.max():.2f} F"
                ),
                "",
                "Absolute XND revision size:",
                (
                    f"  zero-rate: "
                    f"{(abs_delta_xnd == 0).mean():.3f}"
                ),
                (
                    f"  median:    "
                    f"{abs_delta_xnd.median():.2f}"
                ),
                (
                    f"  p90:       "
                    f"{abs_delta_xnd.quantile(.90):.2f}"
                ),
                (
                    f"  max:       "
                    f"{abs_delta_xnd.max():.2f}"
                ),
                "",
            ]
        )

    lines.append(
        "Transition summary:"
    )
    lines.append("")

    lines.append(
        transition_summary.to_string(
            index=False
        )
    )

    lines.append("")
    lines.append(
        "Missingness reasons:"
    )

    if len(missing_summary):
        lines.append(
            missing_summary.to_string()
        )
    else:
        lines.append(
            "  None."
        )

    lines.extend(
        [
            "",
            "Interpretation restriction:",
            (
                "This census evaluates weather-state reconstruction "
                "and publication timing only."
            ),
            (
                "No settlement performance, market-response "
                "performance, or PnL was evaluated."
            ),
        ]
    )

    report = "\n".join(
        lines
    ) + "\n"

    report_path = (
        OUTDIR
        / "v2_full_weather_revision_census.txt"
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
        f"  {states_path}"
    )
    print(
        f"  {pairs_path}"
    )
    print(
        "  results/v2_feasibility/"
        "v2_publication_order_audit.csv"
    )
    print(
        "  results/v2_feasibility/"
        "v2_revision_transition_summary.csv"
    )
    print(
        f"  {report_path}"
    )


if __name__ == "__main__":
    main()
