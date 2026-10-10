from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


FEATURES_PATH = Path(
    "data/processed/model_features_event.csv"
)

WEATHER_PATH = Path(
    "data/processed/weather_panel_primary.csv"
)

RAW_WEATHER_DIR = Path(
    "data/raw/weather/nbm_nbs"
)

MARKET_PATH = Path(
    "data/processed/market_panel_preclose.csv"
)

MASTER_EVENT_PATH = Path(
    "data/processed/modeling_master_event.csv"
)

MASTER_LONG_PATH = Path(
    "data/processed/modeling_master_long.csv"
)

OUTDIR = Path("results/audit")
DOC_PATH = Path(
    "docs/v1_point_in_time_implementation_audit.md"
)

PRIMARY_DECISION_HOUR = 10
AVAILABILITY_LAG_MINUTES = 60
MAX_MARKET_STALENESS_MINUTES = 60
CYCLES_UTC = (0, 6, 12, 18)

CITY_CONFIG = {
    "NYC": {
        "station": "KNYC",
        "timezone": "America/New_York",
    },
    "Chicago": {
        "station": "KMDW",
        "timezone": "America/Chicago",
    },
    "Denver": {
        "station": "KDEN",
        "timezone": "America/Denver",
    },
}


def to_utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    return ts


def expected_decision_time(
    event_date: str,
    timezone_name: str,
) -> pd.Timestamp:
    date = datetime.strptime(
        event_date,
        "%Y-%m-%d",
    ).date()

    dt = datetime(
        date.year,
        date.month,
        date.day,
        PRIMARY_DECISION_HOUR,
        0,
        tzinfo=ZoneInfo(timezone_name),
    )

    return pd.Timestamp(
        dt
    ).tz_convert("UTC")


def latest_eligible_cycle(
    decision_utc: pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    candidates = []

    # Search several prior UTC dates independently
    # of the original implementation.
    for offset in (-2, -1, 0):
        d = (
            decision_utc.date()
            + timedelta(days=offset)
        )

        for hour in CYCLES_UTC:
            cycle = pd.Timestamp(
                datetime(
                    d.year,
                    d.month,
                    d.day,
                    hour,
                    0,
                    tzinfo=timezone.utc,
                )
            )

            available = (
                cycle
                + pd.Timedelta(
                    minutes=AVAILABILITY_LAG_MINUTES
                )
            )

            if available <= decision_utc:
                candidates.append(
                    (cycle, available)
                )

    if not candidates:
        raise RuntimeError(
            f"No eligible cycle for "
            f"{decision_utc}"
        )

    return max(
        candidates,
        key=lambda x: x[0],
    )


def expected_valid_time(
    event_date: str,
) -> pd.Timestamp:
    d = (
        pd.Timestamp(event_date)
        + pd.Timedelta(days=1)
    )

    return pd.Timestamp(
        d.strftime("%Y-%m-%d")
        + "T00:00:00Z"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def weather_audit(
    features: pd.DataFrame,
    weather: pd.DataFrame,
):
    weather_idx = (
        weather
        .set_index(
            [
                "city",
                "event_date_local",
            ]
        )
    )

    records = []

    for row in features.itertuples(
        index=False
    ):
        city = row.city
        event_date = row.event_date_local

        cfg = CITY_CONFIG[city]

        expected_station = (
            cfg["station"]
        )

        decision_expected = (
            expected_decision_time(
                event_date,
                cfg["timezone"],
            )
        )

        cycle_expected, available_expected = (
            latest_eligible_cycle(
                decision_expected
            )
        )

        decision_actual = to_utc(
            row.decision_time_utc
        )

        cycle_actual = to_utc(
            row.cycle_time_utc
        )

        available_actual = to_utc(
            row.assumed_available_at_utc
        )

        margin_minutes = (
            (
                decision_actual
                - available_actual
            ).total_seconds()
            / 60.0
        )

        key = (
            city,
            event_date,
        )

        weather_row_missing = (
            key not in weather_idx.index
        )

        weather_value_match = False
        exclusion_reason = None
        missing_reason = None

        if not weather_row_missing:
            w = weather_idx.loc[key]

            if isinstance(
                w,
                pd.DataFrame,
            ):
                raise RuntimeError(
                    f"Duplicate weather rows: "
                    f"{key}"
                )

            weather_value_match = (
                str(w["station"])
                == str(row.station)
                and np.isclose(
                    float(w["txn"]),
                    float(row.txn),
                )
                and np.isclose(
                    float(w["xnd"]),
                    float(row.xnd),
                )
                and to_utc(
                    w["cycle_time_utc"]
                )
                == cycle_actual
                and to_utc(
                    w[
                        "assumed_available_at_utc"
                    ]
                )
                == available_actual
            )

            exclusion_reason = (
                None
                if pd.isna(
                    w.get(
                        "exclusion_reason",
                        np.nan,
                    )
                )
                else str(
                    w.get(
                        "exclusion_reason"
                    )
                )
            )

            missing_reason = (
                None
                if pd.isna(
                    w.get(
                        "missing_reason",
                        np.nan,
                    )
                )
                else str(
                    w.get(
                        "missing_reason"
                    )
                )
            )

        raw_path = (
            RAW_WEATHER_DIR
            / expected_station
            / (
                f"{event_date}_"
                f"{cycle_actual:%Y%m%dT%H%MZ}.json"
            )
        )

        raw_exists = raw_path.exists()

        raw_wrapper_match = False
        raw_target_match_count = 0
        raw_value_match = False
        raw_runtime_match = True
        raw_runtime_available = False

        if raw_exists:
            raw = json.loads(
                raw_path.read_text(
                    encoding="utf-8"
                )
            )

            if "api_response" in raw:
                payload = raw[
                    "api_response"
                ]

                raw_wrapper_match = (
                    str(raw.get("city"))
                    == city
                    and str(
                        raw.get("station")
                    )
                    == expected_station
                    and str(
                        raw.get(
                            "event_date_local"
                        )
                    )
                    == event_date
                    and to_utc(
                        raw[
                            "cycle_time_utc"
                        ]
                    )
                    == cycle_actual
                    and to_utc(
                        raw[
                            "assumed_available_at_utc"
                        ]
                    )
                    == available_actual
                    and to_utc(
                        raw[
                            "decision_time_utc"
                        ]
                    )
                    == decision_actual
                )
            else:
                payload = raw

            target_valid = (
                expected_valid_time(
                    event_date
                )
            )

            target_matches = []

            api_runtimes = []

            for api_row in payload.get(
                "data",
                [],
            ):
                runtime_value = (
                    api_row.get("runtime")
                )

                if runtime_value:
                    try:
                        api_runtimes.append(
                            to_utc(
                                runtime_value
                            )
                        )
                    except Exception:
                        pass

                ftime = (
                    api_row.get(
                        "ftime_utc"
                    )
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
                    ftime_ts
                    == target_valid
                    and api_row.get(
                        "txn"
                    ) is not None
                    and api_row.get(
                        "xnd"
                    ) is not None
                ):
                    target_matches.append(
                        api_row
                    )

            raw_target_match_count = len(
                target_matches
            )

            if (
                raw_target_match_count
                == 1
            ):
                api_row = target_matches[0]

                raw_value_match = (
                    np.isclose(
                        float(
                            api_row["txn"]
                        ),
                        float(row.txn),
                    )
                    and np.isclose(
                        float(
                            api_row["xnd"]
                        ),
                        float(row.xnd),
                    )
                )

            if api_runtimes:
                raw_runtime_available = True

                unique_runtime = set(
                    api_runtimes
                )

                raw_runtime_match = (
                    len(unique_runtime) == 1
                    and next(
                        iter(unique_runtime)
                    )
                    == cycle_actual
                )

        future_cycle_violation = (
            cycle_actual
            > decision_actual
        )

        unavailable_violation = (
            available_actual
            > decision_actual
        )

        latest_cycle_mismatch = (
            cycle_actual
            != cycle_expected
        )

        # Any use of a cycle later than the exact
        # recomputed latest-eligible cycle.
        future_substitution = (
            cycle_actual
            > cycle_expected
        )

        # Conservative definition:
        # any alternate cycle selection is treated
        # as a nearest/other-cycle substitution.
        nearest_cycle_substitution = (
            cycle_actual
            != cycle_expected
        )

        later_missing_replacement = (
            cycle_actual
            > cycle_expected
        )

        records.append(
            {
                "city": city,
                "event_date_local":
                    event_date,
                "station_used":
                    row.station,
                "expected_station":
                    expected_station,

                "model_cycle_time_utc":
                    cycle_actual.isoformat(),
                "expected_latest_cycle_utc":
                    cycle_expected.isoformat(),

                "assumed_available_at_utc":
                    available_actual.isoformat(),
                "expected_available_at_utc":
                    available_expected.isoformat(),

                "decision_time_utc":
                    decision_actual.isoformat(),
                "expected_decision_time_utc":
                    decision_expected.isoformat(),

                "availability_margin_minutes":
                    margin_minutes,

                "available_at_decision":
                    not unavailable_violation,

                "latest_eligible_cycle":
                    not latest_cycle_mismatch,

                "future_cycle_violation":
                    future_cycle_violation,

                "unavailable_at_decision_violation":
                    unavailable_violation,

                "future_substitution":
                    future_substitution,

                "nearest_cycle_substitution":
                    nearest_cycle_substitution,

                "missing_replaced_with_later_forecast":
                    later_missing_replacement,

                "decision_time_match":
                    decision_actual
                    == decision_expected,

                "station_match":
                    str(row.station)
                    == expected_station,

                "txn_available":
                    not pd.isna(row.txn),

                "xnd_available":
                    not pd.isna(row.xnd),

                "weather_processed_row_exists":
                    not weather_row_missing,

                "weather_processed_value_match":
                    weather_value_match,

                "raw_file_exists":
                    raw_exists,

                "raw_wrapper_match":
                    raw_wrapper_match,

                "raw_target_match_count":
                    raw_target_match_count,

                "raw_txn_xnd_match":
                    raw_value_match,

                "raw_api_runtime_available":
                    raw_runtime_available,

                "raw_api_runtime_match":
                    raw_runtime_match,

                "missing_reason":
                    missing_reason,

                "exclusion_reason":
                    exclusion_reason,
            }
        )

    return pd.DataFrame(
        records
    )


def market_audit(
    features: pd.DataFrame,
    market: pd.DataFrame,
):
    market = market.copy()

    market[
        "timestamp_utc"
    ] = pd.to_datetime(
        market[
            "timestamp_utc"
        ],
        utc=True,
    )

    records = []

    quote_cols = [
        "yes_bid_close",
        "yes_ask_close",
        "midpoint_close",
        "spread_close",
    ]

    for row in features.itertuples(
        index=False
    ):
        city = row.city
        event_date = (
            row.event_date_local
        )

        decision = (
            expected_decision_time(
                event_date,
                CITY_CONFIG[
                    city
                ]["timezone"],
            )
        )

        snapshot_actual = to_utc(
            row.market_snapshot_utc
        )

        event_market = market[
            (
                market["city"]
                == city
            )
            & (
                market[
                    "event_date_local"
                ]
                == event_date
            )
            & (
                market[
                    "event_ticker"
                ]
                == row.event_ticker
            )
        ].copy()

        eligible = event_market[
            event_market[
                "timestamp_utc"
            ]
            <= decision
        ].dropna(
            subset=quote_cols
        )

        sync = (
            eligible
            .groupby(
                "timestamp_utc"
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
            )
        )

        complete = sync[
            (
                sync["row_count"]
                == 6
            )
            & (
                sync[
                    "bucket_count"
                ]
                == 6
            )
        ]

        if len(complete):
            expected_snapshot = (
                complete.index.max()
            )
        else:
            expected_snapshot = (
                pd.NaT
            )

        latest_complete_match = (
            pd.notna(
                expected_snapshot
            )
            and snapshot_actual
            == expected_snapshot
        )

        snapshot_rows = (
            event_market[
                event_market[
                    "timestamp_utc"
                ]
                == snapshot_actual
            ]
        )

        synchronized_six = (
            len(snapshot_rows) == 6
            and snapshot_rows[
                "market_ticker"
            ].nunique()
            == 6
            and not snapshot_rows[
                quote_cols
            ].isna().any().any()
        )

        age_minutes = (
            (
                decision
                - snapshot_actual
            ).total_seconds()
            / 60.0
        )

        future_violation = (
            snapshot_actual
            > decision
        )

        stale_violation = (
            age_minutes < 0
            or age_minutes
            > MAX_MARKET_STALENESS_MINUTES
        )

        records.append(
            {
                "city":
                    city,
                "event_date_local":
                    event_date,
                "event_ticker":
                    row.event_ticker,

                "decision_time_utc":
                    decision.isoformat(),

                "market_snapshot_utc":
                    snapshot_actual.isoformat(),

                "recomputed_latest_complete_snapshot_utc":
                    (
                        expected_snapshot.isoformat()
                        if pd.notna(
                            expected_snapshot
                        )
                        else None
                    ),

                "snapshot_age_minutes":
                    age_minutes,

                "future_market_candle_violation":
                    future_violation,

                "staleness_violation":
                    stale_violation,

                "complete_synchronized_six":
                    synchronized_six,

                "latest_complete_snapshot_match":
                    latest_complete_match,
            }
        )

    return pd.DataFrame(
        records
    )


def quote_alignment_audit(
    long_df: pd.DataFrame,
    market: pd.DataFrame,
):
    left = long_df[
        [
            "city",
            "event_date_local",
            "event_ticker",
            "market_ticker",
            "market_snapshot_utc",
            "yes_bid_close",
            "yes_ask_close",
            "midpoint_close",
            "spread_close",
        ]
    ].copy()

    left[
        "market_snapshot_utc"
    ] = pd.to_datetime(
        left[
            "market_snapshot_utc"
        ],
        utc=True,
    )

    right = market[
        [
            "city",
            "event_date_local",
            "event_ticker",
            "market_ticker",
            "timestamp_utc",
            "yes_bid_close",
            "yes_ask_close",
            "midpoint_close",
            "spread_close",
        ]
    ].copy()

    right[
        "timestamp_utc"
    ] = pd.to_datetime(
        right[
            "timestamp_utc"
        ],
        utc=True,
    )

    right = right.rename(
        columns={
            "yes_bid_close":
                "source_yes_bid_close",
            "yes_ask_close":
                "source_yes_ask_close",
            "midpoint_close":
                "source_midpoint_close",
            "spread_close":
                "source_spread_close",
        }
    )

    merged = left.merge(
        right,
        left_on=[
            "city",
            "event_date_local",
            "event_ticker",
            "market_ticker",
            "market_snapshot_utc",
        ],
        right_on=[
            "city",
            "event_date_local",
            "event_ticker",
            "market_ticker",
            "timestamp_utc",
        ],
        how="left",
        validate="one_to_one",
    )

    missing_source = (
        merged[
            "timestamp_utc"
        ].isna()
    )

    mismatch = np.zeros(
        len(merged),
        dtype=bool,
    )

    comparisons = [
        (
            "yes_bid_close",
            "source_yes_bid_close",
        ),
        (
            "yes_ask_close",
            "source_yes_ask_close",
        ),
        (
            "midpoint_close",
            "source_midpoint_close",
        ),
        (
            "spread_close",
            "source_spread_close",
        ),
    ]

    for a, b in comparisons:
        mismatch |= (
            ~np.isclose(
                merged[a],
                merged[b],
                equal_nan=False,
            )
        )

    merged[
        "source_row_missing"
    ] = missing_source

    merged[
        "quote_value_mismatch"
    ] = mismatch

    return merged


def main():
    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    features = pd.read_csv(
        FEATURES_PATH
    )

    weather = pd.read_csv(
        WEATHER_PATH
    )

    market = pd.read_csv(
        MARKET_PATH
    )

    event_master = pd.read_csv(
        MASTER_EVENT_PATH
    )

    long_master = pd.read_csv(
        MASTER_LONG_PATH
    )

    # --------------------------------------------------
    # Structural checks
    # --------------------------------------------------

    if len(features) != 138:
        raise RuntimeError(
            f"Expected 138 model feature rows, "
            f"found {len(features)}"
        )

    if (
        features[
            [
                "city",
                "event_date_local",
            ]
        ]
        .duplicated()
        .any()
    ):
        raise RuntimeError(
            "Duplicate city-days in model features."
        )

    # --------------------------------------------------
    # Weather audit
    # --------------------------------------------------

    w = weather_audit(
        features,
        weather,
    )

    w.to_csv(
        OUTDIR
        / "v1_weather_point_in_time_rows.csv",
        index=False,
    )

    # --------------------------------------------------
    # Market audit
    # --------------------------------------------------

    m = market_audit(
        features,
        market,
    )

    m.to_csv(
        OUTDIR
        / "v1_market_point_in_time_rows.csv",
        index=False,
    )

    q = quote_alignment_audit(
        long_master,
        market,
    )

    q.to_csv(
        OUTDIR
        / "v1_market_quote_alignment_rows.csv",
        index=False,
    )

    # --------------------------------------------------
    # Weather aggregate diagnostics
    # --------------------------------------------------

    future_cycle = int(
        w[
            "future_cycle_violation"
        ].sum()
    )

    unavailable = int(
        w[
            "unavailable_at_decision_violation"
        ].sum()
    )

    future_sub = int(
        w[
            "future_substitution"
        ].sum()
    )

    nearest_sub = int(
        w[
            "nearest_cycle_substitution"
        ].sum()
    )

    later_replacement = int(
        w[
            "missing_replaced_with_later_forecast"
        ].sum()
    )

    latest_cycle_mismatch = int(
        (
            ~w[
                "latest_eligible_cycle"
            ]
        ).sum()
    )

    decision_mismatch = int(
        (
            ~w[
                "decision_time_match"
            ]
        ).sum()
    )

    station_mismatch = int(
        (
            ~w[
                "station_match"
            ]
        ).sum()
    )

    missing_txn = int(
        (
            ~w["txn_available"]
        ).sum()
    )

    missing_xnd = int(
        (
            ~w["xnd_available"]
        ).sum()
    )

    processed_mismatch = int(
        (
            ~w[
                "weather_processed_value_match"
            ]
        ).sum()
    )

    raw_missing = int(
        (
            ~w[
                "raw_file_exists"
            ]
        ).sum()
    )

    raw_wrapper_mismatch = int(
        (
            ~w[
                "raw_wrapper_match"
            ]
        ).sum()
    )

    raw_target_failures = int(
        (
            w[
                "raw_target_match_count"
            ]
            != 1
        ).sum()
    )

    raw_value_mismatch = int(
        (
            ~w[
                "raw_txn_xnd_match"
            ]
        ).sum()
    )

    runtime_checked = w[
        "raw_api_runtime_available"
    ]

    runtime_mismatch = int(
        (
            runtime_checked
            & (
                ~w[
                    "raw_api_runtime_match"
                ]
            )
        ).sum()
    )

    # --------------------------------------------------
    # Market aggregate diagnostics
    # --------------------------------------------------

    market_future = int(
        m[
            "future_market_candle_violation"
        ].sum()
    )

    market_stale = int(
        m[
            "staleness_violation"
        ].sum()
    )

    market_incomplete = int(
        (
            ~m[
                "complete_synchronized_six"
            ]
        ).sum()
    )

    market_latest_mismatch = int(
        (
            ~m[
                "latest_complete_snapshot_match"
            ]
        ).sum()
    )

    quote_missing = int(
        q[
            "source_row_missing"
        ].sum()
    )

    quote_mismatch = int(
        q[
            "quote_value_mismatch"
        ].sum()
    )

    # --------------------------------------------------
    # Cycle distribution
    # --------------------------------------------------

    cycle_dist = (
        w.assign(
            cycle_hour=pd.to_datetime(
                w[
                    "model_cycle_time_utc"
                ],
                utc=True,
            ).dt.strftime(
                "%HZ"
            )
        )
        .groupby(
            [
                "city",
                "cycle_hour",
            ]
        )
        .size()
        .unstack(
            fill_value=0
        )
    )

    # --------------------------------------------------
    # Missing/exclusion reasons
    # --------------------------------------------------

    reasons = []

    for col in (
        "missing_reason",
        "exclusion_reason",
    ):
        counts = (
            w[col]
            .dropna()
            .value_counts()
        )

        for reason, count in (
            counts.items()
        ):
            reasons.append(
                (
                    col,
                    reason,
                    int(count),
                )
            )

    # --------------------------------------------------
    # Relevant implementation source hashes
    # --------------------------------------------------

    source_files = [
        Path(
            "src/weather/backfill_nbm.py"
        ),
        Path(
            "src/market/build_modeling_master.py"
        ),
        Path(
            "src/modeling/build_model_features.py"
        ),
    ]

    hashes = []

    for path in source_files:
        hashes.append(
            (
                str(path),
                sha256(path),
            )
        )

    # --------------------------------------------------
    # Hard validity status
    # --------------------------------------------------

    hard_failures = {
        "future_cycle_violations":
            future_cycle,
        "unavailable_at_decision_violations":
            unavailable,
        "future_substitutions":
            future_sub,
        "nearest_cycle_substitutions":
            nearest_sub,
        "later_missing_replacements":
            later_replacement,
        "latest_cycle_mismatches":
            latest_cycle_mismatch,
        "decision_time_mismatches":
            decision_mismatch,
        "station_mismatches":
            station_mismatch,
        "missing_txn":
            missing_txn,
        "missing_xnd":
            missing_xnd,
        "processed_weather_mismatches":
            processed_mismatch,
        "raw_weather_files_missing":
            raw_missing,
        "raw_wrapper_mismatches":
            raw_wrapper_mismatch,
        "raw_target_row_failures":
            raw_target_failures,
        "raw_txn_xnd_mismatches":
            raw_value_mismatch,
        "raw_runtime_mismatches":
            runtime_mismatch,
        "future_market_candle_violations":
            market_future,
        "market_staleness_violations":
            market_stale,
        "incomplete_market_snapshots":
            market_incomplete,
        "latest_market_snapshot_mismatches":
            market_latest_mismatch,
        "market_quote_source_rows_missing":
            quote_missing,
        "market_quote_value_mismatches":
            quote_mismatch,
    }

    passed = all(
        value == 0
        for value in hard_failures.values()
    )

    # --------------------------------------------------
    # Report
    # --------------------------------------------------

    margin = w[
        "availability_margin_minutes"
    ]

    snapshot_age = m[
        "snapshot_age_minutes"
    ]

    exact_market = int(
        (
            snapshot_age == 0
        ).sum()
    )

    stale_market = int(
        (
            snapshot_age > 0
        ).sum()
    )

    lines = [
        "# V1 Point-in-Time Implementation Audit",
        "",
        "Audit date: 2026-09-30",
        "",
        "## 1. Methodology",
        "",
        (
            "The audit independently recomputed the frozen "
            "10:00 AM local decision time, the latest eligible "
            "00/06/12/18Z NBS cycle under the +60 minute "
            "availability rule, raw TXN/XND provenance, and the "
            "latest complete synchronized six-bucket Kalshi "
            "snapshot at or before the decision time."
        ),
        "",
        (
            "The audit used the exact city-days contained in "
            "`model_features_event.csv`, i.e. the observations "
            "actually supplied to the V1 predictive models."
        ),
        "",
        "## 2. Weather point-in-time diagnostics",
        "",
        f"- Total V1 city-days examined: {len(features)}",
        f"- Total weather rows used: {len(w)}",
        f"- Future-cycle violations: {future_cycle}",
        (
            "- Unavailable-at-decision violations: "
            f"{unavailable}"
        ),
        f"- Future substitutions: {future_sub}",
        (
            "- Nearest/alternate-cycle substitutions: "
            f"{nearest_sub}"
        ),
        (
            "- Missing eligible forecasts replaced with "
            f"later forecasts: {later_replacement}"
        ),
        f"- Latest-cycle mismatches: {latest_cycle_mismatch}",
        f"- Decision-time mismatches: {decision_mismatch}",
        f"- Station mismatches: {station_mismatch}",
        f"- Missing TXN: {missing_txn}",
        f"- Missing XND: {missing_xnd}",
        (
            "- Processed-weather/model-feature mismatches: "
            f"{processed_mismatch}"
        ),
        f"- Raw weather files missing: {raw_missing}",
        f"- Raw wrapper mismatches: {raw_wrapper_mismatch}",
        (
            "- Raw target-valid-time row failures: "
            f"{raw_target_failures}"
        ),
        f"- Raw TXN/XND mismatches: {raw_value_mismatch}",
        (
            "- Raw API runtime mismatches "
            f"(where runtime field available): {runtime_mismatch}"
        ),
        "",
        "Availability margin "
        "`decision_time - assumed_available_at`:",
        "",
        (
            f"- Minimum: {margin.min():.1f} minutes "
            f"({margin.min()/60:.2f} h)"
        ),
        (
            f"- Median: {margin.median():.1f} minutes "
            f"({margin.median()/60:.2f} h)"
        ),
        (
            f"- Maximum: {margin.max():.1f} minutes "
            f"({margin.max()/60:.2f} h)"
        ),
        "",
        "Cycle-frequency distribution by city:",
        "",
        "```",
        cycle_dist.to_string(),
        "```",
        "",
        "Exclusion / missingness reasons:",
        "",
    ]

    if reasons:
        for kind, reason, count in reasons:
            lines.append(
                f"- {kind}: {reason} = {count}"
            )
    else:
        lines.append(
            "- None."
        )

    lines.extend(
        [
            "",
            "## 3. Market point-in-time diagnostics",
            "",
            (
                f"- Market city-days examined: "
                f"{len(m)}"
            ),
            (
                "- Future market-candle violations: "
                f"{market_future}"
            ),
            (
                "- Snapshot staleness >60 minute violations: "
                f"{market_stale}"
            ),
            (
                "- Incomplete/non-synchronized selected "
                f"snapshots: {market_incomplete}"
            ),
            (
                "- Selected snapshot not equal to independently "
                "recomputed latest complete snapshot: "
                f"{market_latest_mismatch}"
            ),
            (
                "- Selected quote source rows missing: "
                f"{quote_missing}"
            ),
            (
                "- Selected quote value mismatches: "
                f"{quote_mismatch}"
            ),
            f"- Exact 10:00 snapshots: {exact_market}",
            f"- Non-exact but eligible snapshots: {stale_market}",
            (
                f"- Snapshot age minimum: "
                f"{snapshot_age.min():.1f} minutes"
            ),
            (
                f"- Snapshot age median: "
                f"{snapshot_age.median():.1f} minutes"
            ),
            (
                f"- Snapshot age maximum: "
                f"{snapshot_age.max():.1f} minutes"
            ),
            "",
            "## 4. Responsible implementation",
            "",
            (
                "- NBS cycle eligibility: "
                "`src/weather/backfill_nbm.py` — "
                "`primary_decision_time()`, "
                "`latest_eligible_cycle()`, "
                "`expected_tmax_valid_time()`, and `main()`."
            ),
            (
                "- Weather/market timestamp alignment: "
                "`src/market/build_modeling_master.py` — "
                "`main()`; specifically the at-or-before-decision "
                "filter, synchronized six-bucket grouping, and "
                "latest eligible snapshot selection."
            ),
            (
                "- Predictive feature dataset construction: "
                "`src/modeling/build_model_features.py` — "
                "`bucket_mass()` and `main()`."
            ),
            "",
            "Source SHA256:",
            "",
            "```",
        ]
    )

    for path, digest in hashes:
        lines.append(
            f"{digest}  {path}"
        )

    lines.extend(
        [
            "```",
            "",
            "## 5. Violations and interpretation",
            "",
        ]
    )

    if passed:
        lines.extend(
            [
                (
                    "No point-in-time implementation violation "
                    "was detected in the weather or market data "
                    "actually used by V1."
                ),
                "",
                (
                    "No detected implementation issue changes "
                    "the interpretation of the frozen V1 results."
                ),
                "",
                "## 6. V1 closure",
                "",
                (
                    "**Under the frozen V1 specification, static "
                    "NBM TXN/XND proxy information did not show "
                    "reliable incremental predictive or economic "
                    "value beyond the 10AM Kalshi market in this "
                    "46-date sample.**"
                ),
                "",
                (
                    "The small positive Market-only historical "
                    "PnL is not evidence of alpha. It is fully "
                    "eliminated by +1¢ adverse execution and "
                    "becomes negative at +2¢."
                ),
                "",
                (
                    "V1 does not establish scalable or realized "
                    "tradeable profitability."
                ),
                "",
                "**FINAL AUDIT STATUS: PASS — V1 CLOSED**",
            ]
        )
    else:
        lines.append(
            "**FINAL AUDIT STATUS: FAIL — V1 NOT YET CLOSED**"
        )

        lines.append("")
        lines.append(
            "Detected non-zero validity diagnostics:"
        )

        for name, value in (
            hard_failures.items()
        ):
            if value:
                lines.append(
                    f"- {name}: {value}"
                )

        lines.append("")
        lines.append(
            "Do not modify V1 until the detected "
            "implementation issue is understood."
        )

    report = "\n".join(lines) + "\n"

    DOC_PATH.write_text(
        report,
        encoding="utf-8",
    )

    (
        OUTDIR
        / "v1_point_in_time_implementation_audit.txt"
    ).write_text(
        report,
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print(
        "V1 POINT-IN-TIME IMPLEMENTATION AUDIT"
    )
    print("=" * 80)

    print(
        f"V1 city-days examined:                 {len(features)}"
    )
    print(
        f"Weather rows used:                     {len(w)}"
    )
    print(
        f"Future-cycle violations:               {future_cycle}"
    )
    print(
        f"Unavailable-at-decision violations:     {unavailable}"
    )
    print(
        f"Future substitutions:                  {future_sub}"
    )
    print(
        f"Nearest/alternate-cycle substitutions: {nearest_sub}"
    )
    print(
        f"Later missing replacements:             {later_replacement}"
    )
    print(
        f"Missing TXN/XND:                        {missing_txn + missing_xnd}"
    )

    print()
    print(
        "Availability margin (minutes): "
        f"min={margin.min():.1f} | "
        f"median={margin.median():.1f} | "
        f"max={margin.max():.1f}"
    )

    print()
    print("Cycle distribution:")
    print(cycle_dist.to_string())

    print()
    print(
        f"Future market-candle violations:        {market_future}"
    )
    print(
        f"Market staleness violations:            {market_stale}"
    )
    print(
        f"Incomplete synchronized snapshots:      {market_incomplete}"
    )
    print(
        f"Latest-snapshot mismatches:              {market_latest_mismatch}"
    )
    print(
        f"Quote source/value mismatches:           {quote_missing + quote_mismatch}"
    )
    print(
        f"Exact 10:00 snapshots:                   {exact_market}"
    )
    print(
        f"Eligible non-exact snapshots:            {stale_market}"
    )

    print()
    print(
        "FINAL AUDIT STATUS:",
        "PASS — V1 CLOSED"
        if passed
        else "FAIL — INVESTIGATE",
    )
    print("=" * 80)

    print(
        "\nFull report:"
    )
    print(
        "  docs/v1_point_in_time_implementation_audit.md"
    )

    print(
        "\nRow-level evidence:"
    )
    print(
        "  results/audit/v1_weather_point_in_time_rows.csv"
    )
    print(
        "  results/audit/v1_market_point_in_time_rows.csv"
    )
    print(
        "  results/audit/v1_market_quote_alignment_rows.csv"
    )


if __name__ == "__main__":
    main()
