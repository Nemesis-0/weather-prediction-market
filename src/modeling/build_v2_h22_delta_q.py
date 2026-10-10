from pathlib import Path
import ast
import json
import re

import numpy as np
import pandas as pd

from src.modeling.build_model_features import bucket_mass


RESIDUAL_PATH = Path(
    "results/v2_residual_assimilation/"
    "v2_residual_events.csv"
)

ALIGN_PATH = Path(
    "results/v2_feasibility/"
    "v2_market_alignment_events.csv"
)

PAIRS_PATH = Path(
    "results/v2_feasibility/"
    "v2_full_revision_pairs.csv"
)

MARKET_PATH = Path(
    "data/processed/"
    "market_panel_all.csv"
)

OUTPUT_PATH = Path(
    "results/v2_residual_assimilation/"
    "v2_h22_weather_revision_vectors.csv"
)


def bool_col(s):
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False)

    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .map(
            {
                "true": True,
                "false": False,
                "1": True,
                "0": False,
            }
        )
        .fillna(False)
        .astype(bool)
    )


def parse_vector(x):
    if isinstance(x, str):
        return np.asarray(
            ast.literal_eval(x),
            dtype=float,
        )

    return np.asarray(
        x,
        dtype=float,
    )


def parse_bucket_bounds(
    label,
    strike_type,
):
    """
    Convert the six frozen Kalshi bucket labels to the integer
    bounds expected by the already-frozen V1 bucket_mass function.

    Examples:
        "75° or below" -> (None, 75)
        "76° to 77°"   -> (76, 77)
        "84° or above" -> (84, None)
    """

    text = str(label)
    st = str(strike_type).strip().lower()

    nums = [
        int(x)
        for x in re.findall(
            r"-?\d+",
            text,
        )
    ]

    low_words = (
        "below" in text.lower()
        or st in {
            "less",
            "less_than",
            "lte",
        }
    )

    high_words = (
        "above" in text.lower()
        or st in {
            "greater",
            "greater_than",
            "gte",
        }
    )

    if low_words:
        if len(nums) != 1:
            raise ValueError(
                f"Could not parse lower-tail bucket: "
                f"{label!r}, strike_type={strike_type!r}"
            )

        return None, nums[0]

    if high_words:
        if len(nums) != 1:
            raise ValueError(
                f"Could not parse upper-tail bucket: "
                f"{label!r}, strike_type={strike_type!r}"
            )

        return nums[0], None

    if len(nums) != 2:
        raise ValueError(
            f"Could not parse interior bucket: "
            f"{label!r}, strike_type={strike_type!r}"
        )

    lo, hi = nums

    if lo > hi:
        raise ValueError(
            f"Invalid bucket bounds: {label!r}"
        )

    return lo, hi


def main():

    residual = pd.read_csv(
        RESIDUAL_PATH
    )

    align = pd.read_csv(
        ALIGN_PATH
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
            "strike_type",
            "floor_strike",
            "timestamp_utc",
            "midpoint_close",
        ],
    )


    print("=" * 96)
    print(
        "V2 H2.2 TRUE WEATHER REVISION VECTOR BUILDER"
    )
    print("=" * 96)


    if len(residual) != 179:
        raise RuntimeError(
            f"Expected frozen 179-event residual dataset; "
            f"found {len(residual)}"
        )


    for c in [
        "any_weather_change",
        "clean_pre_post1h",
        "clean_pre_post2h",
    ]:
        align[c] = bool_col(
            align[c]
        )


    h22_align = align[
        align["any_weather_change"]
        & align["clean_pre_post1h"]
        & align["clean_pre_post2h"]
    ].copy()


    if len(h22_align) != 179:
        raise RuntimeError(
            f"Expected 179 eligible alignment rows; "
            f"found {len(h22_align)}"
        )


    timestamp_cols = [
        "pre_snapshot_utc",
        "post1_snapshot_utc",
        "post2_snapshot_utc",
    ]

    for df in [
        residual,
        h22_align,
    ]:
        for c in timestamp_cols:
            df[c] = pd.to_datetime(
                df[c],
                utc=True,
            )


    market[
        "timestamp_utc"
    ] = pd.to_datetime(
        market["timestamp_utc"],
        utc=True,
    )


    residual_key = [
        "event_date_local",
        "city",
        "transition",
        "pre_snapshot_utc",
        "post1_snapshot_utc",
        "post2_snapshot_utc",
    ]


    if residual.duplicated(
        residual_key
    ).any():
        raise RuntimeError(
            "Residual dataset is not unique on frozen event key."
        )


    if h22_align.duplicated(
        residual_key
    ).any():
        raise RuntimeError(
            "Alignment dataset is not unique on frozen event key."
        )


    events = residual.merge(
        h22_align[
            residual_key
            +
            [
                "revision_sequence",
                "event_ticker",
                "old_state_label",
                "new_state_label",
                "new_publication_time_utc",
            ]
        ],
        on=residual_key,
        how="left",
        validate="one_to_one",
    )


    if events[
        "revision_sequence"
    ].isna().any():
        raise RuntimeError(
            "Failed to recover alignment metadata "
            "for one or more H2.2 events."
        )


    pair_key = [
        "event_date_local",
        "city",
        "revision_sequence",
    ]


    if pairs.duplicated(
        pair_key
    ).any():
        raise RuntimeError(
            "Revision-pair dataset is not unique "
            "on event_date/city/revision_sequence."
        )


    events = events.merge(
        pairs[
            pair_key
            +
            [
                "transition",
                "old_txn",
                "new_txn",
                "old_xnd",
                "new_xnd",
                "delta_txn",
                "delta_xnd",
                "any_weather_change",
            ]
        ].rename(
            columns={
                "transition":
                    "pair_transition",
                "delta_txn":
                    "pair_delta_txn",
                "delta_xnd":
                    "pair_delta_xnd",
                "any_weather_change":
                    "pair_any_weather_change",
            }
        ),
        on=pair_key,
        how="left",
        validate="one_to_one",
    )


    required_weather = [
        "old_txn",
        "new_txn",
        "old_xnd",
        "new_xnd",
    ]

    if events[
        required_weather
    ].isna().any().any():
        raise RuntimeError(
            "Missing old/new TXN/XND after revision-pair merge."
        )


    if not (
        events["transition"]
        ==
        events["pair_transition"]
    ).all():
        raise RuntimeError(
            "Transition mismatch between alignment "
            "and revision-pair datasets."
        )


    pair_changed = bool_col(
        events[
            "pair_any_weather_change"
        ]
    )

    if not pair_changed.all():
        raise RuntimeError(
            "H2.2 dataset unexpectedly contains "
            "a non-changing weather pair."
        )


    if not np.allclose(
        events["new_txn"]
        -
        events["old_txn"],
        events["pair_delta_txn"],
        atol=1e-12,
    ):
        raise RuntimeError(
            "TXN delta consistency check failed."
        )


    if not np.allclose(
        events["new_xnd"]
        -
        events["old_xnd"],
        events["pair_delta_xnd"],
        atol=1e-12,
    ):
        raise RuntimeError(
            "XND delta consistency check failed."
        )


    rows = []

    max_old_sum_error = 0.0
    max_new_sum_error = 0.0
    max_pre_distribution_error = 0.0


    for _, r in events.iterrows():

        pre_rows = market[
            (
                market["city"]
                ==
                r["city"]
            )
            &
            (
                market["event_ticker"]
                ==
                r["event_ticker"]
            )
            &
            (
                market["timestamp_utc"]
                ==
                r["pre_snapshot_utc"]
            )
        ].copy()


        pre_rows = pre_rows.sort_values(
            "market_ticker"
        ).reset_index(
            drop=True
        )


        if len(pre_rows) != 6:
            raise RuntimeError(
                f"Expected six PRE buckets for "
                f"{r['event_date_local']} "
                f"{r['city']} "
                f"{r['transition']}; "
                f"found {len(pre_rows)}"
            )


        if (
            pre_rows[
                "market_ticker"
            ].nunique()
            != 6
        ):
            raise RuntimeError(
                "Duplicate market tickers in PRE bucket schema."
            )


        stored_pre = parse_vector(
            r["pre_distribution"]
        )


        actual_pre = (
            pre_rows[
                "midpoint_close"
            ]
            .astype(float)
            .to_numpy()
        )


        if len(stored_pre) != 6:
            raise RuntimeError(
                "Stored PRE distribution is not six-dimensional."
            )


        pre_error = float(
            np.max(
                np.abs(
                    stored_pre
                    -
                    actual_pre
                )
            )
        )

        max_pre_distribution_error = max(
            max_pre_distribution_error,
            pre_error,
        )


        if pre_error > 1e-10:
            raise RuntimeError(
                "Stored market-vector ordering does not match "
                "market_ticker-sorted PRE bucket ordering."
            )


        bounds = []

        for _, b in pre_rows.iterrows():

            lo, hi = parse_bucket_bounds(
                b["bucket_label"],
                b["strike_type"],
            )

            bounds.append(
                (
                    lo,
                    hi,
                )
            )


        old_txn = float(
            r["old_txn"]
        )

        new_txn = float(
            r["new_txn"]
        )

        old_xnd = float(
            r["old_xnd"]
        )

        new_xnd = float(
            r["new_xnd"]
        )


        if old_xnd <= 0 or new_xnd <= 0:
            raise RuntimeError(
                "XND must be strictly positive "
                "for the frozen Normal proxy."
            )


        q_old = np.asarray(
            [
                bucket_mass(
                    old_txn,
                    old_xnd,
                    lo,
                    hi,
                )
                for lo, hi in bounds
            ],
            dtype=float,
        )


        q_new = np.asarray(
            [
                bucket_mass(
                    new_txn,
                    new_xnd,
                    lo,
                    hi,
                )
                for lo, hi in bounds
            ],
            dtype=float,
        )


        old_sum_error = abs(
            float(
                q_old.sum()
            )
            -
            1.0
        )

        new_sum_error = abs(
            float(
                q_new.sum()
            )
            -
            1.0
        )


        max_old_sum_error = max(
            max_old_sum_error,
            old_sum_error,
        )

        max_new_sum_error = max(
            max_new_sum_error,
            new_sum_error,
        )


        if old_sum_error > 1e-8:
            raise RuntimeError(
                f"q_old does not sum to one: "
                f"{q_old.sum()}"
            )


        if new_sum_error > 1e-8:
            raise RuntimeError(
                f"q_new does not sum to one: "
                f"{q_new.sum()}"
            )


        delta_q = (
            q_new
            -
            q_old
        )


        delta_q_norm_sq = float(
            np.dot(
                delta_q,
                delta_q,
            )
        )


        if delta_q_norm_sq <= 1e-16:
            raise RuntimeError(
                "Weather-changing revision produced "
                "numerically zero delta_q."
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
                    int(
                        r["revision_sequence"]
                    ),

                "transition":
                    r["transition"],

                "old_state_label":
                    r["old_state_label"],

                "new_state_label":
                    r["new_state_label"],

                "old_txn":
                    old_txn,

                "new_txn":
                    new_txn,

                "old_xnd":
                    old_xnd,

                "new_xnd":
                    new_xnd,

                "delta_txn":
                    float(
                        new_txn - old_txn
                    ),

                "delta_xnd":
                    float(
                        new_xnd - old_xnd
                    ),

                "pre_snapshot_utc":
                    r[
                        "pre_snapshot_utc"
                    ].isoformat(),

                "post1_snapshot_utc":
                    r[
                        "post1_snapshot_utc"
                    ].isoformat(),

                "post2_snapshot_utc":
                    r[
                        "post2_snapshot_utc"
                    ].isoformat(),

                "market_tickers":
                    json.dumps(
                        pre_rows[
                            "market_ticker"
                        ].tolist()
                    ),

                "bucket_labels":
                    json.dumps(
                        pre_rows[
                            "bucket_label"
                        ].tolist()
                    ),

                "bucket_bounds":
                    json.dumps(
                        bounds
                    ),

                "q_old":
                    json.dumps(
                        q_old.tolist()
                    ),

                "q_new":
                    json.dumps(
                        q_new.tolist()
                    ),

                "delta_q":
                    json.dumps(
                        delta_q.tolist()
                    ),

                "delta_q_norm_sq":
                    delta_q_norm_sq,
            }
        )


    out = pd.DataFrame(
        rows
    )


    if len(out) != 179:
        raise RuntimeError(
            f"Expected 179 final weather vectors; "
            f"found {len(out)}"
        )


    if out[
        [
            "q_old",
            "q_new",
            "delta_q",
        ]
    ].isna().any().any():
        raise RuntimeError(
            "Missing weather-vector output."
        )


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    out.to_csv(
        OUTPUT_PATH,
        index=False,
    )


    print()
    print(
        "Events:",
        len(out)
    )

    print(
        "Dates:",
        out[
            "event_date_local"
        ].nunique()
    )

    print()
    print(
        "By city:"
    )
    print(
        out[
            "city"
        ].value_counts()
        .to_string()
    )

    print()
    print(
        "By transition:"
    )
    print(
        out[
            "transition"
        ].value_counts()
        .to_string()
    )

    print()
    print(
        "delta_q ||.||^2 summary:"
    )
    print(
        out[
            "delta_q_norm_sq"
        ].describe()
    )

    print()
    print(
        "max |sum(q_old)-1|:",
        f"{max_old_sum_error:.3e}",
    )

    print(
        "max |sum(q_new)-1|:",
        f"{max_new_sum_error:.3e}",
    )

    print(
        "max PRE ordering consistency error:",
        f"{max_pre_distribution_error:.3e}",
    )

    print()
    print(
        "FIRST EVENT WEATHER VECTOR"
    )

    first = out.iloc[0]

    print(
        "event:",
        first[
            "event_date_local"
        ],
        first["city"],
        first["transition"],
    )

    print(
        "old TXN/XND:",
        first["old_txn"],
        first["old_xnd"],
    )

    print(
        "new TXN/XND:",
        first["new_txn"],
        first["new_xnd"],
    )

    print(
        "bucket labels:",
        first[
            "bucket_labels"
        ],
    )

    print(
        "q_old:",
        first[
            "q_old"
        ],
    )

    print(
        "q_new:",
        first[
            "q_new"
        ],
    )

    print(
        "delta_q:",
        first[
            "delta_q"
        ],
    )

    print()
    print(
        "Saved:",
        OUTPUT_PATH,
    )

    print()
    print("=" * 96)
    print(
        "PASS: delta_q was constructed ONLY from "
        "old/new TXN/XND through the frozen V1 bucket_mass transform."
    )
    print(
        "NO H2.2 MARKET-DIRECTION RESULT WAS COMPUTED."
    )
    print("=" * 96)


if __name__ == "__main__":
    main()
