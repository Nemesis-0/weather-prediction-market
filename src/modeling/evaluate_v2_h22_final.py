from pathlib import Path
import argparse
import ast
import json
import math
import hashlib

import numpy as np
import pandas as pd


WEATHER_PATH = Path(
    "results/v2_residual_assimilation/"
    "v2_h22_weather_revision_vectors.csv"
)

PLACEBO_PATH = Path(
    "results/v2_residual_assimilation/"
    "v2_h22_placebo_availability.csv"
)

PAIRS_PATH = Path(
    "results/v2_feasibility/"
    "v2_full_revision_pairs.csv"
)

MARKET_PATH = Path(
    "data/processed/"
    "market_panel_all.csv"
)

OUTDIR = Path(
    "results/v2_residual_assimilation/final_h22"
)

EXPECTED_PRIMARY_EVENTS = 179
EXPECTED_PLACEBO_EVENTS = 174
EXPECTED_STUDY_DATES = 46

BOOTSTRAP_REPS = 10_000
RANDOM_SEED = 20260930


def parse_bool(s):
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


def parse_vec(x):
    if isinstance(x, str):
        return np.asarray(
            ast.literal_eval(x),
            dtype=float,
        )

    return np.asarray(
        x,
        dtype=float,
    )


def parse_json_list(x):
    if isinstance(x, str):
        return json.loads(x)

    return list(x)


def normalize(v):
    v = np.asarray(v, dtype=float)

    total = float(v.sum())

    if not np.isfinite(total) or total <= 0:
        raise RuntimeError(
            f"Invalid midpoint sum: {total}"
        )

    return v / total


def market_vector(
    market,
    city,
    event_ticker,
    timestamp,
    ticker_order,
):
    sub = market[
        (market["city"] == city)
        &
        (
            market["event_ticker"]
            == event_ticker
        )
        &
        (
            market["timestamp_utc"]
            == timestamp
        )
    ].copy()

    if len(sub) != 6:
        raise RuntimeError(
            f"Expected 6 market rows, found {len(sub)} "
            f"for {city} {event_ticker} {timestamp}"
        )

    if sub["market_ticker"].nunique() != 6:
        raise RuntimeError(
            "Market snapshot does not contain six "
            "unique market tickers."
        )

    if not sub["midpoint_close"].notna().all():
        raise RuntimeError(
            "Missing midpoint_close in selected snapshot."
        )

    if not sub["spread_close"].notna().all():
        raise RuntimeError(
            "Missing spread_close in selected snapshot."
        )

    if not sub["is_pre_close"].all():
        raise RuntimeError(
            "Selected snapshot contains non-pre-close rows."
        )

    indexed = (
        sub.set_index("market_ticker")
    )

    observed = set(
        indexed.index.tolist()
    )

    expected = set(
        ticker_order
    )

    if observed != expected:
        raise RuntimeError(
            "Market ticker set differs from frozen "
            "weather-vector ticker set."
        )

    indexed = indexed.loc[
        ticker_order
    ]

    midpoint = (
        indexed["midpoint_close"]
        .astype(float)
        .to_numpy()
    )

    spread = (
        indexed["spread_close"]
        .astype(float)
        .to_numpy()
    )

    labels = (
        indexed["bucket_label"]
        .astype(str)
        .tolist()
    )

    return midpoint, spread, labels


def build_validated_inputs():
    weather = pd.read_csv(
        WEATHER_PATH
    )

    placebo = pd.read_csv(
        PLACEBO_PATH
    )

    pairs = pd.read_csv(
        PAIRS_PATH
    )

    market = pd.read_csv(
        MARKET_PATH,
        usecols=[
            "city",
            "event_ticker",
            "market_ticker",
            "bucket_label",
            "timestamp_utc",
            "midpoint_close",
            "spread_close",
            "is_pre_close",
        ],
    )

    market["timestamp_utc"] = pd.to_datetime(
        market["timestamp_utc"],
        utc=True,
    )

    market["is_pre_close"] = parse_bool(
        market["is_pre_close"]
    )

    for c in [
        "pre_snapshot_utc",
        "post1_snapshot_utc",
        "post2_snapshot_utc",
    ]:
        weather[c] = pd.to_datetime(
            weather[c],
            utc=True,
        )

    placebo[
        "placebo_start_utc"
    ] = pd.to_datetime(
        placebo["placebo_start_utc"],
        utc=True,
    )

    placebo[
        "pre_snapshot_utc"
    ] = pd.to_datetime(
        placebo["pre_snapshot_utc"],
        utc=True,
    )

    placebo[
        "placebo_complete_six"
    ] = parse_bool(
        placebo["placebo_complete_six"]
    )

    # --------------------------------------------------
    # Frozen population checks
    # --------------------------------------------------

    if len(weather) != EXPECTED_PRIMARY_EVENTS:
        raise RuntimeError(
            f"Expected {EXPECTED_PRIMARY_EVENTS} "
            f"primary events, found {len(weather)}"
        )

    if (
        placebo["placebo_complete_six"].sum()
        != EXPECTED_PLACEBO_EVENTS
    ):
        raise RuntimeError(
            "Frozen placebo population is not 174."
        )

    primary_key = [
        "event_date_local",
        "city",
        "event_ticker",
        "revision_sequence",
        "transition",
    ]

    if weather.duplicated(
        primary_key
    ).any():
        raise RuntimeError(
            "Duplicate primary H2.2 event key."
        )

    if placebo.duplicated(
        primary_key
    ).any():
        raise RuntimeError(
            "Duplicate placebo event key."
        )

    # --------------------------------------------------
    # Complete 46-calendar-day study calendar
    # --------------------------------------------------

    study_dates = (
        pd.to_datetime(
            pairs["event_date_local"]
        )
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
        .reset_index(drop=True)
    )

    if len(study_dates) != EXPECTED_STUDY_DATES:
        raise RuntimeError(
            f"Expected 46 study dates, "
            f"found {len(study_dates)}"
        )

    expected_calendar = pd.Series(
        pd.date_range(
            study_dates.iloc[0],
            study_dates.iloc[-1],
            freq="D",
        )
    )

    if len(expected_calendar) != EXPECTED_STUDY_DATES:
        raise RuntimeError(
            "Study period does not span exactly "
            "46 consecutive calendar dates."
        )

    if not np.array_equal(
        study_dates.to_numpy(),
        expected_calendar.to_numpy(),
    ):
        raise RuntimeError(
            "Study dates are not the complete "
            "46-day calendar."
        )

    study_date_strings = (
        study_dates
        .dt.strftime("%Y-%m-%d")
        .tolist()
    )

    # --------------------------------------------------
    # Build market inputs WITHOUT directional statistics
    # --------------------------------------------------

    primary_rows = []

    max_delta_q_sum_error = 0.0

    for _, r in weather.iterrows():

        dq = parse_vec(
            r["delta_q"]
        )

        if dq.shape != (6,):
            raise RuntimeError(
                "delta_q is not six-dimensional."
            )

        if not np.isfinite(dq).all():
            raise RuntimeError(
                "Non-finite delta_q."
            )

        dq_sum_error = abs(
            float(dq.sum())
        )

        max_delta_q_sum_error = max(
            max_delta_q_sum_error,
            dq_sum_error,
        )

        if dq_sum_error > 1e-10:
            raise RuntimeError(
                "delta_q does not sum to zero."
            )

        stored_norm_sq = float(
            r["delta_q_norm_sq"]
        )

        recomputed_norm_sq = float(
            np.dot(dq, dq)
        )

        if not np.isclose(
            stored_norm_sq,
            recomputed_norm_sq,
            atol=1e-12,
            rtol=1e-12,
        ):
            raise RuntimeError(
                "delta_q norm-squared mismatch."
            )

        if recomputed_norm_sq <= 0:
            raise RuntimeError(
                "Nonpositive delta_q denominator."
            )

        ticker_order = parse_json_list(
            r["market_tickers"]
        )

        frozen_labels = parse_json_list(
            r["bucket_labels"]
        )

        if len(ticker_order) != 6:
            raise RuntimeError(
                "Frozen ticker order is not length 6."
            )

        if len(set(ticker_order)) != 6:
            raise RuntimeError(
                "Frozen ticker order contains duplicates."
            )

        market_vectors = {}

        for name, timestamp in [
            (
                "pre",
                r["pre_snapshot_utc"],
            ),
            (
                "post1",
                r["post1_snapshot_utc"],
            ),
            (
                "post2",
                r["post2_snapshot_utc"],
            ),
        ]:
            midpoint, spread, labels = market_vector(
                market=market,
                city=r["city"],
                event_ticker=r["event_ticker"],
                timestamp=timestamp,
                ticker_order=ticker_order,
            )

            if labels != frozen_labels:
                raise RuntimeError(
                    "Bucket-label ordering mismatch."
                )

            market_vectors[name] = {
                "midpoint": midpoint,
                "spread": spread,
                "normalized": normalize(
                    midpoint
                ),
            }

        primary_rows.append({
            "event_date_local":
                r["event_date_local"],

            "city":
                r["city"],

            "event_ticker":
                r["event_ticker"],

            "revision_sequence":
                int(r["revision_sequence"]),

            "transition":
                r["transition"],

            "delta_q":
                json.dumps(
                    dq.tolist()
                ),

            "delta_q_norm_sq":
                recomputed_norm_sq,

            "pre_midpoints":
                json.dumps(
                    market_vectors[
                        "pre"
                    ]["midpoint"].tolist()
                ),

            "post1_midpoints":
                json.dumps(
                    market_vectors[
                        "post1"
                    ]["midpoint"].tolist()
                ),

            "post2_midpoints":
                json.dumps(
                    market_vectors[
                        "post2"
                    ]["midpoint"].tolist()
                ),

            "pre_prob":
                json.dumps(
                    market_vectors[
                        "pre"
                    ]["normalized"].tolist()
                ),

            "post1_prob":
                json.dumps(
                    market_vectors[
                        "post1"
                    ]["normalized"].tolist()
                ),

            "post2_prob":
                json.dumps(
                    market_vectors[
                        "post2"
                    ]["normalized"].tolist()
                ),

            "pre_midpoint_sum":
                float(
                    market_vectors[
                        "pre"
                    ]["midpoint"].sum()
                ),

            "post1_midpoint_sum":
                float(
                    market_vectors[
                        "post1"
                    ]["midpoint"].sum()
                ),

            "post2_midpoint_sum":
                float(
                    market_vectors[
                        "post2"
                    ]["midpoint"].sum()
                ),

            "pre_total_spread":
                float(
                    market_vectors[
                        "pre"
                    ]["spread"].sum()
                ),

            "post1_total_spread":
                float(
                    market_vectors[
                        "post1"
                    ]["spread"].sum()
                ),

            "post2_total_spread":
                float(
                    market_vectors[
                        "post2"
                    ]["spread"].sum()
                ),
        })

    primary = pd.DataFrame(
        primary_rows
    )

    if len(primary) != EXPECTED_PRIMARY_EVENTS:
        raise RuntimeError(
            "Primary validated input row count changed."
        )

    # --------------------------------------------------
    # Build frozen 174-event exact placebo inputs
    # --------------------------------------------------

    placebo_eligible = placebo[
        placebo["placebo_complete_six"]
    ].copy()

    placebo_eligible = placebo_eligible.merge(
        weather[
            primary_key
            +
            [
                "market_tickers",
                "bucket_labels",
                "delta_q",
                "delta_q_norm_sq",
            ]
        ],
        on=primary_key,
        how="left",
        validate="one_to_one",
    )

    if len(placebo_eligible) != EXPECTED_PLACEBO_EVENTS:
        raise RuntimeError(
            "Placebo merge did not preserve 174 events."
        )

    if placebo_eligible[
        "delta_q"
    ].isna().any():
        raise RuntimeError(
            "Placebo event missing frozen delta_q."
        )

    placebo_rows = []

    for _, r in placebo_eligible.iterrows():

        ticker_order = parse_json_list(
            r["market_tickers"]
        )

        frozen_labels = parse_json_list(
            r["bucket_labels"]
        )

        dq = parse_vec(
            r["delta_q"]
        )

        start_mid, start_spread, start_labels = (
            market_vector(
                market=market,
                city=r["city"],
                event_ticker=r["event_ticker"],
                timestamp=r[
                    "placebo_start_utc"
                ],
                ticker_order=ticker_order,
            )
        )

        pre_mid, pre_spread, pre_labels = (
            market_vector(
                market=market,
                city=r["city"],
                event_ticker=r["event_ticker"],
                timestamp=r[
                    "pre_snapshot_utc"
                ],
                ticker_order=ticker_order,
            )
        )

        if start_labels != frozen_labels:
            raise RuntimeError(
                "Placebo-start bucket ordering mismatch."
            )

        if pre_labels != frozen_labels:
            raise RuntimeError(
                "Placebo PRE bucket ordering mismatch."
            )

        placebo_rows.append({
            "event_date_local":
                r["event_date_local"],

            "city":
                r["city"],

            "event_ticker":
                r["event_ticker"],

            "revision_sequence":
                int(r["revision_sequence"]),

            "transition":
                r["transition"],

            "delta_q":
                json.dumps(
                    dq.tolist()
                ),

            "delta_q_norm_sq":
                float(
                    r["delta_q_norm_sq"]
                ),

            "placebo_start_midpoints":
                json.dumps(
                    start_mid.tolist()
                ),

            "pre_midpoints":
                json.dumps(
                    pre_mid.tolist()
                ),

            "placebo_start_prob":
                json.dumps(
                    normalize(
                        start_mid
                    ).tolist()
                ),

            "pre_prob":
                json.dumps(
                    normalize(
                        pre_mid
                    ).tolist()
                ),

            "placebo_start_midpoint_sum":
                float(start_mid.sum()),

            "pre_midpoint_sum":
                float(pre_mid.sum()),

            "placebo_start_total_spread":
                float(start_spread.sum()),

            "pre_total_spread":
                float(pre_spread.sum()),
        })

    placebo_validated = pd.DataFrame(
        placebo_rows
    )

    if len(
        placebo_validated
    ) != EXPECTED_PLACEBO_EVENTS:
        raise RuntimeError(
            "Validated placebo population changed."
        )

    return (
        primary,
        placebo_validated,
        study_date_strings,
        max_delta_q_sum_error,
    )


def validate_only():
    (
        primary,
        placebo,
        study_dates,
        max_delta_q_sum_error,
    ) = build_validated_inputs()

    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    primary.to_csv(
        OUTDIR
        / "validated_primary_inputs.csv",
        index=False,
    )

    placebo.to_csv(
        OUTDIR
        / "validated_placebo_inputs.csv",
        index=False,
    )

    pd.DataFrame({
        "event_date_local":
            study_dates
    }).to_csv(
        OUTDIR
        / "study_calendar_46_dates.csv",
        index=False,
    )

    print("=" * 96)
    print(
        "V2 H2.2 FINAL EVALUATOR — VALIDATE ONLY"
    )
    print("=" * 96)

    print(
        "Primary events:",
        len(primary)
    )

    print(
        "Primary dates with >=1 event:",
        primary[
            "event_date_local"
        ].nunique()
    )

    print(
        "Placebo events:",
        len(placebo)
    )

    print(
        "Placebo dates with >=1 event:",
        placebo[
            "event_date_local"
        ].nunique()
    )

    print(
        "Complete study calendar dates:",
        len(study_dates)
    )

    print()

    print(
        "Primary by city:"
    )
    print(
        primary[
            "city"
        ].value_counts()
        .to_string()
    )

    print()

    print(
        "Primary by transition:"
    )
    print(
        primary[
            "transition"
        ].value_counts()
        .to_string()
    )

    print()

    print(
        "Placebo by city:"
    )
    print(
        placebo[
            "city"
        ].value_counts()
        .to_string()
    )

    print()

    print(
        "Placebo by transition:"
    )
    print(
        placebo[
            "transition"
        ].value_counts()
        .to_string()
    )

    print()

    print(
        "max |sum(delta_q)|:",
        f"{max_delta_q_sum_error:.3e}"
    )

    print()

    print(
        "Primary midpoint-sum ranges:"
    )

    for c in [
        "pre_midpoint_sum",
        "post1_midpoint_sum",
        "post2_midpoint_sum",
    ]:
        print(
            f"  {c}: "
            f"[{primary[c].min():.6f}, "
            f"{primary[c].max():.6f}]"
        )

    print()

    print(
        "Primary total-spread ranges:"
    )

    for c in [
        "pre_total_spread",
        "post1_total_spread",
        "post2_total_spread",
    ]:
        print(
            f"  {c}: "
            f"[{primary[c].min():.6f}, "
            f"{primary[c].max():.6f}]"
        )

    print()

    print(
        "Saved structural inputs to:",
        OUTDIR
    )

    print()

    print("=" * 96)
    print(
        "VALIDATION STATUS: PASS"
    )
    print(
        "NO directional dot product, beta, bootstrap CI, "
        "or H2.2 result was computed."
    )
    print("=" * 96)



EXECUTION_FREEZE_PATH = Path(
    "results/v2_residual_assimilation/"
    "H2_2_EXECUTION_FREEZE_SHA256.txt"
)


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def verify_execution_freeze():
    if not EXECUTION_FREEZE_PATH.exists():
        raise RuntimeError(
            "Execution-freeze manifest does not exist."
        )

    checked = 0

    for line in EXECUTION_FREEZE_PATH.read_text().splitlines():
        line = line.strip()

        if not line:
            continue

        expected, relpath = line.split(
            "  ",
            1,
        )

        path = Path(relpath)

        if not path.exists():
            raise RuntimeError(
                f"Frozen execution input missing: {path}"
            )

        actual = sha256_file(path)

        if actual != expected:
            raise RuntimeError(
                "EXECUTION FREEZE HASH MISMATCH:\n"
                f"  file:     {path}\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}"
            )

        checked += 1

    if checked == 0:
        raise RuntimeError(
            "Execution-freeze manifest contained no files."
        )

    return checked


def beta_from_events(
    df,
    numerator_col,
    denominator_col="projection_denominator",
):
    numerator = float(
        df[numerator_col].sum()
    )

    denominator = float(
        df[denominator_col].sum()
    )

    if denominator <= 0:
        return np.nan

    return numerator / denominator


def full_calendar_date_contributions(
    df,
    numerator_col,
    denominator_col,
    study_dates,
):
    grouped = (
        df.groupby(
            "event_date_local",
            as_index=False,
        )
        .agg(
            numerator=(
                numerator_col,
                "sum",
            ),
            denominator=(
                denominator_col,
                "sum",
            ),
            events=(
                denominator_col,
                "size",
            ),
        )
    )

    calendar = pd.DataFrame(
        {
            "event_date_local":
                study_dates
        }
    )

    out = calendar.merge(
        grouped,
        on="event_date_local",
        how="left",
        validate="one_to_one",
    )

    out[
        [
            "numerator",
            "denominator",
            "events",
        ]
    ] = (
        out[
            [
                "numerator",
                "denominator",
                "events",
            ]
        ]
        .fillna(0)
    )

    out["events"] = (
        out["events"]
        .astype(int)
    )

    if len(out) != EXPECTED_STUDY_DATES:
        raise RuntimeError(
            "Date-contribution table is not 46 rows."
        )

    return out


def moving_block_bootstrap_beta(
    date_df,
    block_length,
    reps,
    rng,
):
    nums = (
        date_df["numerator"]
        .to_numpy(dtype=float)
    )

    dens = (
        date_df["denominator"]
        .to_numpy(dtype=float)
    )

    n = len(date_df)

    if block_length > n:
        raise ValueError(
            "Block length exceeds number of dates."
        )

    starts = np.arange(
        0,
        n - block_length + 1,
    )

    blocks_needed = int(
        math.ceil(
            n / block_length
        )
    )

    out = np.empty(
        reps,
        dtype=float,
    )

    for b in range(reps):
        chosen = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )

        indices = np.concatenate(
            [
                np.arange(
                    start,
                    start + block_length,
                )
                for start in chosen
            ]
        )[:n]

        numerator = float(
            nums[indices].sum()
        )

        denominator = float(
            dens[indices].sum()
        )

        out[b] = (
            numerator / denominator
            if denominator > 0
            else np.nan
        )

    return out[
        np.isfinite(out)
    ]


def bootstrap_cis(
    date_df,
):
    # Resetting to the same frozen seed for each statistic
    # gives the same calendar-block draws wherever possible.
    rng = np.random.default_rng(
        RANDOM_SEED
    )

    out = {}

    for block_length in (
        1,
        3,
        7,
    ):
        boot = moving_block_bootstrap_beta(
            date_df=date_df,
            block_length=block_length,
            reps=BOOTSTRAP_REPS,
            rng=rng,
        )

        if len(boot) == 0:
            raise RuntimeError(
                "Bootstrap returned no finite replicates."
            )

        out[block_length] = {
            "lower":
                float(
                    np.quantile(
                        boot,
                        0.025,
                    )
                ),

            "upper":
                float(
                    np.quantile(
                        boot,
                        0.975,
                    )
                ),

            "finite_reps":
                int(len(boot)),
        }

    return out


def denominator_concentration(
    date_df,
):
    total = float(
        date_df[
            "denominator"
        ].sum()
    )

    if total <= 0:
        raise RuntimeError(
            "Nonpositive total denominator."
        )

    out = date_df.copy()

    out[
        "denominator_share"
    ] = (
        out["denominator"]
        / total
    )

    shares = (
        out[
            "denominator_share"
        ]
        .to_numpy(dtype=float)
    )

    hhi = float(
        np.sum(
            shares ** 2
        )
    )

    effective_dates = (
        float(1.0 / hhi)
        if hhi > 0
        else np.nan
    )

    sorted_shares = np.sort(
        shares
    )[::-1]

    stats = {
        "max_date_share":
            float(
                sorted_shares[0]
            ),

        "top5_date_share":
            float(
                sorted_shares[
                    :5
                ].sum()
            ),

        "denominator_hhi":
            hhi,

        "effective_denominator_dates":
            effective_dates,
    }

    return out, stats


def grouped_descriptive(
    df,
    group_col,
):
    rows = []

    for name, g in df.groupby(
        group_col,
        sort=True,
    ):
        rows.append(
            {
                group_col:
                    name,

                "events":
                    len(g),

                "beta":
                    beta_from_events(
                        g,
                        "projection_numerator",
                    ),

                "positive_dot_fraction":
                    float(
                        g[
                            "directional_dot_positive"
                        ].mean()
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def descriptive_summary(
    series,
):
    x = pd.Series(
        series,
        dtype=float,
    )

    return {
        "n":
            int(x.notna().sum()),

        "mean":
            float(x.mean()),

        "median":
            float(x.median()),

        "std":
            float(x.std(ddof=1)),

        "min":
            float(x.min()),

        "p05":
            float(x.quantile(0.05)),

        "p95":
            float(x.quantile(0.95)),

        "max":
            float(x.max()),
    }


def load_frozen_structural_inputs():
    primary_path = (
        OUTDIR
        / "validated_primary_inputs.csv"
    )

    placebo_path = (
        OUTDIR
        / "validated_placebo_inputs.csv"
    )

    calendar_path = (
        OUTDIR
        / "study_calendar_46_dates.csv"
    )

    for path in [
        primary_path,
        placebo_path,
        calendar_path,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    primary = pd.read_csv(
        primary_path
    )

    placebo = pd.read_csv(
        placebo_path
    )

    calendar = pd.read_csv(
        calendar_path
    )

    if len(primary) != EXPECTED_PRIMARY_EVENTS:
        raise RuntimeError(
            "Frozen primary input is not 179 events."
        )

    if len(placebo) != EXPECTED_PLACEBO_EVENTS:
        raise RuntimeError(
            "Frozen placebo input is not 174 events."
        )

    if len(calendar) != EXPECTED_STUDY_DATES:
        raise RuntimeError(
            "Frozen study calendar is not 46 dates."
        )

    dates = (
        calendar[
            "event_date_local"
        ]
        .astype(str)
        .tolist()
    )

    parsed_dates = pd.to_datetime(
        dates
    )

    expected = pd.date_range(
        parsed_dates.min(),
        parsed_dates.max(),
        freq="D",
    )

    if len(expected) != EXPECTED_STUDY_DATES:
        raise RuntimeError(
            "Frozen study calendar does not span 46 days."
        )

    if not np.array_equal(
        parsed_dates.to_numpy(),
        expected.to_numpy(),
    ):
        raise RuntimeError(
            "Frozen study calendar is not consecutive."
        )

    return (
        primary,
        placebo,
        dates,
    )


def build_primary_metrics(
    primary,
):
    rows = []

    for _, r in primary.iterrows():
        dq = parse_vec(
            r["delta_q"]
        )

        p1 = parse_vec(
            r["post1_prob"]
        )

        p2 = parse_vec(
            r["post2_prob"]
        )

        m1 = parse_vec(
            r["post1_midpoints"]
        )

        m2 = parse_vec(
            r["post2_midpoints"]
        )

        if not all(
            x.shape == (6,)
            for x in [
                dq,
                p1,
                p2,
                m1,
                m2,
            ]
        ):
            raise RuntimeError(
                "Primary vector dimensionality failure."
            )

        delta_p_later = (
            p2 - p1
        )

        delta_m_later = (
            m2 - m1
        )

        numerator = float(
            np.dot(
                dq,
                delta_p_later,
            )
        )

        raw_numerator = float(
            np.dot(
                dq,
                delta_m_later,
            )
        )

        denominator = float(
            r[
                "delta_q_norm_sq"
            ]
        )

        rows.append(
            {
                "event_date_local":
                    r[
                        "event_date_local"
                    ],

                "city":
                    r["city"],

                "event_ticker":
                    r[
                        "event_ticker"
                    ],

                "revision_sequence":
                    int(
                        r[
                            "revision_sequence"
                        ]
                    ),

                "transition":
                    r["transition"],

                "delta_q":
                    json.dumps(
                        dq.tolist()
                    ),

                "delta_p_later":
                    json.dumps(
                        delta_p_later.tolist()
                    ),

                "delta_m_later":
                    json.dumps(
                        delta_m_later.tolist()
                    ),

                "projection_numerator":
                    numerator,

                "raw_projection_numerator":
                    raw_numerator,

                "projection_denominator":
                    denominator,

                "directional_dot_positive":
                    bool(
                        numerator > 0
                    ),

                "directional_dot_zero":
                    bool(
                        np.isclose(
                            numerator,
                            0.0,
                            atol=1e-15,
                        )
                    ),

                "post1_midpoint_sum":
                    float(
                        r[
                            "post1_midpoint_sum"
                        ]
                    ),

                "post2_midpoint_sum":
                    float(
                        r[
                            "post2_midpoint_sum"
                        ]
                    ),

                "delta_midpoint_sum":
                    float(
                        r[
                            "post2_midpoint_sum"
                        ]
                        -
                        r[
                            "post1_midpoint_sum"
                        ]
                    ),

                "post1_total_spread":
                    float(
                        r[
                            "post1_total_spread"
                        ]
                    ),

                "post2_total_spread":
                    float(
                        r[
                            "post2_total_spread"
                        ]
                    ),

                "delta_total_spread":
                    float(
                        r[
                            "post2_total_spread"
                        ]
                        -
                        r[
                            "post1_total_spread"
                        ]
                    ),
            }
        )

    out = pd.DataFrame(
        rows
    )

    if len(out) != EXPECTED_PRIMARY_EVENTS:
        raise RuntimeError(
            "Primary metric count changed."
        )

    return out


def build_placebo_metrics(
    placebo,
):
    rows = []

    for _, r in placebo.iterrows():
        dq = parse_vec(
            r["delta_q"]
        )

        p0 = parse_vec(
            r[
                "placebo_start_prob"
            ]
        )

        p1 = parse_vec(
            r["pre_prob"]
        )

        if not all(
            x.shape == (6,)
            for x in [
                dq,
                p0,
                p1,
            ]
        ):
            raise RuntimeError(
                "Placebo vector dimensionality failure."
            )

        delta_p_placebo = (
            p1 - p0
        )

        numerator = float(
            np.dot(
                dq,
                delta_p_placebo,
            )
        )

        denominator = float(
            r[
                "delta_q_norm_sq"
            ]
        )

        rows.append(
            {
                "event_date_local":
                    r[
                        "event_date_local"
                    ],

                "city":
                    r["city"],

                "event_ticker":
                    r[
                        "event_ticker"
                    ],

                "revision_sequence":
                    int(
                        r[
                            "revision_sequence"
                        ]
                    ),

                "transition":
                    r["transition"],

                "projection_numerator":
                    numerator,

                "projection_denominator":
                    denominator,

                "directional_dot_positive":
                    bool(
                        numerator > 0
                    ),

                "directional_dot_zero":
                    bool(
                        np.isclose(
                            numerator,
                            0.0,
                            atol=1e-15,
                        )
                    ),
            }
        )

    out = pd.DataFrame(
        rows
    )

    if len(out) != EXPECTED_PLACEBO_EVENTS:
        raise RuntimeError(
            "Placebo metric count changed."
        )

    return out


def run_results():
    checked = verify_execution_freeze()

    (
        primary,
        placebo,
        study_dates,
    ) = load_frozen_structural_inputs()

    primary_metrics = (
        build_primary_metrics(
            primary
        )
    )

    placebo_metrics = (
        build_placebo_metrics(
            placebo
        )
    )

    # --------------------------------------------------
    # PRIMARY NORMALIZED LATER-WINDOW STATISTIC
    # --------------------------------------------------

    primary_beta = beta_from_events(
        primary_metrics,
        "projection_numerator",
    )

    primary_dates = (
        full_calendar_date_contributions(
            df=primary_metrics,
            numerator_col=
                "projection_numerator",
            denominator_col=
                "projection_denominator",
            study_dates=study_dates,
        )
    )

    primary_dates, concentration = (
        denominator_concentration(
            primary_dates
        )
    )

    primary_cis = bootstrap_cis(
        primary_dates
    )

    # --------------------------------------------------
    # RAW-MIDPOINT DIAGNOSTIC
    # --------------------------------------------------

    raw_beta = beta_from_events(
        primary_metrics,
        "raw_projection_numerator",
    )

    raw_dates = (
        full_calendar_date_contributions(
            df=primary_metrics,
            numerator_col=
                "raw_projection_numerator",
            denominator_col=
                "projection_denominator",
            study_dates=study_dates,
        )
    )

    raw_cis = bootstrap_cis(
        raw_dates
    )

    # --------------------------------------------------
    # PRE-PUBLICATION PLACEBO
    # --------------------------------------------------

    placebo_beta = beta_from_events(
        placebo_metrics,
        "projection_numerator",
    )

    placebo_dates = (
        full_calendar_date_contributions(
            df=placebo_metrics,
            numerator_col=
                "projection_numerator",
            denominator_col=
                "projection_denominator",
            study_dates=study_dates,
        )
    )

    placebo_cis = bootstrap_cis(
        placebo_dates
    )

    # --------------------------------------------------
    # DESCRIPTIVE ONLY
    # --------------------------------------------------

    positive_fraction = float(
        primary_metrics[
            "directional_dot_positive"
        ].mean()
    )

    zero_events = int(
        primary_metrics[
            "directional_dot_zero"
        ].sum()
    )

    placebo_positive_fraction = float(
        placebo_metrics[
            "directional_dot_positive"
        ].mean()
    )

    by_city = grouped_descriptive(
        primary_metrics,
        "city",
    )

    by_transition = grouped_descriptive(
        primary_metrics,
        "transition",
    )

    diagnostic_rows = []

    for col in [
        "post1_midpoint_sum",
        "post2_midpoint_sum",
        "delta_midpoint_sum",
        "post1_total_spread",
        "post2_total_spread",
        "delta_total_spread",
    ]:
        stats = descriptive_summary(
            primary_metrics[col]
        )

        diagnostic_rows.append(
            {
                "quantity":
                    col,
                **stats,
            }
        )

    diagnostics = pd.DataFrame(
        diagnostic_rows
    )

    # --------------------------------------------------
    # SAVE EVENT- AND DATE-LEVEL AUDIT OUTPUTS
    # --------------------------------------------------

    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    primary_metrics.to_csv(
        OUTDIR
        / "v2_h22_primary_event_metrics.csv",
        index=False,
    )

    placebo_metrics.to_csv(
        OUTDIR
        / "v2_h22_placebo_event_metrics.csv",
        index=False,
    )

    primary_dates.to_csv(
        OUTDIR
        / "v2_h22_primary_date_contributions.csv",
        index=False,
    )

    raw_dates.to_csv(
        OUTDIR
        / "v2_h22_raw_midpoint_date_contributions.csv",
        index=False,
    )

    placebo_dates.to_csv(
        OUTDIR
        / "v2_h22_placebo_date_contributions.csv",
        index=False,
    )

    by_city.to_csv(
        OUTDIR
        / "v2_h22_by_city.csv",
        index=False,
    )

    by_transition.to_csv(
        OUTDIR
        / "v2_h22_by_transition.csv",
        index=False,
    )

    diagnostics.to_csv(
        OUTDIR
        / "v2_h22_market_structure_diagnostics.csv",
        index=False,
    )

    ci_rows = []

    for statistic, beta, cis in [
        (
            "primary_normalized_later_window",
            primary_beta,
            primary_cis,
        ),
        (
            "raw_midpoint_later_window",
            raw_beta,
            raw_cis,
        ),
        (
            "pre_publication_placebo",
            placebo_beta,
            placebo_cis,
        ),
    ]:
        for block in [
            1,
            3,
            7,
        ]:
            ci_rows.append(
                {
                    "statistic":
                        statistic,

                    "beta":
                        beta,

                    "block_days":
                        block,

                    "ci_lower":
                        cis[
                            block
                        ]["lower"],

                    "ci_upper":
                        cis[
                            block
                        ]["upper"],

                    "bootstrap_reps":
                        cis[
                            block
                        ]["finite_reps"],
                }
            )

    ci_table = pd.DataFrame(
        ci_rows
    )

    ci_table.to_csv(
        OUTDIR
        / "v2_h22_final_statistics.csv",
        index=False,
    )

    concentration_table = pd.DataFrame(
        [
            concentration
        ]
    )

    concentration_table.to_csv(
        OUTDIR
        / "v2_h22_denominator_concentration.csv",
        index=False,
    )

    # --------------------------------------------------
    # HUMAN-READABLE SUMMARY
    # --------------------------------------------------

    diag_lookup = (
        diagnostics
        .set_index("quantity")
    )

    summary = [
        "V2 H2.2 FINAL HISTORICAL DIRECTIONAL ANALYSIS",
        "=" * 96,
        "",
        (
            f"Execution-freeze files verified: "
            f"{checked}"
        ),
        "",
        "PRIMARY — normalized later-window association",
        (
            f"  events:                 "
            f"{len(primary_metrics)}"
        ),
        (
            f"  calendar dates:         "
            f"{len(study_dates)}"
        ),
        (
            f"  beta:                   "
            f"{primary_beta:+.8f}"
        ),
        (
            f"  positive-dot fraction:  "
            f"{positive_fraction:.3f}"
        ),
        (
            f"  zero-dot events:        "
            f"{zero_events}"
        ),
        "",
        "  Primary 3-day moving-block bootstrap:",
        (
            f"    95% CI: "
            f"[{primary_cis[3]['lower']:+.8f}, "
            f"{primary_cis[3]['upper']:+.8f}]"
        ),
        "",
        "  Sensitivity:",
        (
            f"    1-day CI: "
            f"[{primary_cis[1]['lower']:+.8f}, "
            f"{primary_cis[1]['upper']:+.8f}]"
        ),
        (
            f"    7-day CI: "
            f"[{primary_cis[7]['lower']:+.8f}, "
            f"{primary_cis[7]['upper']:+.8f}]"
        ),
        "",
        "FALSIFICATION — exact PRE-60min placebo",
        (
            f"  events:                 "
            f"{len(placebo_metrics)}"
        ),
        (
            f"  beta:                   "
            f"{placebo_beta:+.8f}"
        ),
        (
            f"  positive-dot fraction:  "
            f"{placebo_positive_fraction:.3f}"
        ),
        (
            f"  3-day 95% CI:           "
            f"[{placebo_cis[3]['lower']:+.8f}, "
            f"{placebo_cis[3]['upper']:+.8f}]"
        ),
        (
            f"  1-day CI:               "
            f"[{placebo_cis[1]['lower']:+.8f}, "
            f"{placebo_cis[1]['upper']:+.8f}]"
        ),
        (
            f"  7-day CI:               "
            f"[{placebo_cis[7]['lower']:+.8f}, "
            f"{placebo_cis[7]['upper']:+.8f}]"
        ),
        "",
        "DIAGNOSTIC — unnormalized midpoint later-window projection",
        (
            f"  beta:                   "
            f"{raw_beta:+.8f}"
        ),
        (
            f"  3-day 95% CI:           "
            f"[{raw_cis[3]['lower']:+.8f}, "
            f"{raw_cis[3]['upper']:+.8f}]"
        ),
        (
            f"  1-day CI:               "
            f"[{raw_cis[1]['lower']:+.8f}, "
            f"{raw_cis[1]['upper']:+.8f}]"
        ),
        (
            f"  7-day CI:               "
            f"[{raw_cis[7]['lower']:+.8f}, "
            f"{raw_cis[7]['upper']:+.8f}]"
        ),
        "",
        "DENOMINATOR CONCENTRATION",
        (
            f"  max single-date share:  "
            f"{concentration['max_date_share']:.4f}"
        ),
        (
            f"  top-5 date share:       "
            f"{concentration['top5_date_share']:.4f}"
        ),
        (
            f"  denominator HHI:        "
            f"{concentration['denominator_hhi']:.4f}"
        ),
        (
            f"  effective dates:        "
            f"{concentration['effective_denominator_dates']:.2f}"
        ),
        "",
        "NORMALIZATION / LIQUIDITY DESCRIPTIVES",
        (
            f"  mean delta midpoint sum: "
            f"{diag_lookup.loc['delta_midpoint_sum', 'mean']:+.6f}"
        ),
        (
            f"  median delta midpoint sum: "
            f"{diag_lookup.loc['delta_midpoint_sum', 'median']:+.6f}"
        ),
        (
            f"  mean delta total spread: "
            f"{diag_lookup.loc['delta_total_spread', 'mean']:+.6f}"
        ),
        (
            f"  median delta total spread: "
            f"{diag_lookup.loc['delta_total_spread', 'median']:+.6f}"
        ),
        "",
        "BY CITY — DESCRIPTIVE ONLY",
        by_city.to_string(
            index=False
        ),
        "",
        "BY TRANSITION — DESCRIPTIVE ONLY",
        by_transition.to_string(
            index=False
        ),
        "",
        "CLAIM RESTRICTION",
        (
            "A positive primary result would establish only a "
            "later-window post-publication directional association "
            "under the frozen historical design."
        ),
        (
            "It would not by itself establish publication-caused "
            "repricing, delayed causal assimilation, market "
            "inefficiency, executable alpha, or profitability."
        ),
        (
            "The placebo and raw-midpoint analyses are mandatory "
            "falsification/diagnostic results and cannot replace "
            "the primary statistic."
        ),
    ]

    summary_text = (
        "\n".join(summary)
        + "\n"
    )

    summary_path = (
        OUTDIR
        / "V2_H2_2_FINAL_SUMMARY.txt"
    )

    summary_path.write_text(
        summary_text
    )

    print(
        summary_text
    )

    print(
        "Saved final outputs to:",
        OUTDIR
    )


def main():
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--validate-only",
        action="store_true",
    )

    mode.add_argument(
        "--run-results",
        action="store_true",
    )

    args = parser.parse_args()

    if args.validate_only:
        validate_only()
        return

    if args.run_results:
        run_results()
        return


if __name__ == "__main__":
    main()
