from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.modeling.build_model_features import bucket_mass


ALIGNMENT_PATH = Path(
    "results/v2_feasibility/"
    "v2_market_alignment_events.csv"
)

PAIRS_PATH = Path(
    "results/v2_feasibility/"
    "v2_full_revision_pairs.csv"
)

MARKET_PATH = Path(
    "data/processed/"
    "market_panel_preclose.csv"
)

PROTOCOL_PATH = Path(
    "docs/v2_market_reaction_protocol.md"
)

OUTDIR = Path(
    "results/v2_market_reaction"
)

OUTDIR.mkdir(
    parents=True,
    exist_ok=True,
)

BOOTSTRAP_REPS = 10_000
RANDOM_SEED = 20260930

EXPECTED_PRIMARY_EVENTS = 196


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def parse_bucket_label(
    label: str,
):
    """
    Convert Kalshi temperature bucket labels into the
    integer endpoints expected by frozen bucket_mass().

    Examples:
      "75° or below" -> (None, 75)
      "76° to 77°"   -> (76, 77)
      "84° or above" -> (84, None)
    """

    label = str(label).strip()

    m = re.fullmatch(
        r"\s*(-?\d+)°?\s+or\s+below\s*",
        label,
        flags=re.IGNORECASE,
    )

    if m:
        return (
            None,
            float(
                m.group(1)
            ),
        )

    m = re.fullmatch(
        r"\s*(-?\d+)°?\s+to\s+(-?\d+)°?\s*",
        label,
        flags=re.IGNORECASE,
    )

    if m:
        return (
            float(
                m.group(1)
            ),
            float(
                m.group(2)
            ),
        )

    m = re.fullmatch(
        r"\s*(-?\d+)°?\s+or\s+above\s*",
        label,
        flags=re.IGNORECASE,
    )

    if m:
        return (
            float(
                m.group(1)
            ),
            None,
        )

    raise ValueError(
        f"Unrecognized bucket label: {label!r}"
    )


def weather_proxy_vector(
    bucket_rows: pd.DataFrame,
    mu: float,
    sigma: float,
):
    masses = []

    for row in bucket_rows.itertuples(
        index=False
    ):
        lower, upper = (
            parse_bucket_label(
                row.bucket_label
            )
        )

        masses.append(
            bucket_mass(
                mu=float(mu),
                sigma=float(sigma),
                lower_integer=lower,
                upper_integer=upper,
            )
        )

    q = np.asarray(
        masses,
        dtype=float,
    )

    total = q.sum()

    if (
        not np.isfinite(total)
        or total <= 0
    ):
        raise RuntimeError(
            "Invalid weather-proxy probability sum."
        )

    q = q / total

    return q


def market_probability_vector(
    bucket_rows: pd.DataFrame,
):
    p = (
        bucket_rows[
            "midpoint_close"
        ]
        .to_numpy(
            dtype=float
        )
    )

    if (
        len(p) != 6
        or not np.isfinite(p).all()
        or (p < 0).any()
    ):
        raise RuntimeError(
            "Invalid market midpoint vector."
        )

    total = p.sum()

    if total <= 0:
        raise RuntimeError(
            "Nonpositive market midpoint sum."
        )

    return p / total


def beta_from_events(
    df: pd.DataFrame,
):
    numerator = float(
        df[
            "projection_numerator"
        ].sum()
    )

    denominator = float(
        df[
            "projection_denominator"
        ].sum()
    )

    if denominator <= 0:
        return np.nan

    return (
        numerator
        / denominator
    )


def date_contributions(
    df: pd.DataFrame,
):
    return (
        df.groupby(
            "event_date_local",
            as_index=False,
        )
        .agg(
            numerator=(
                "projection_numerator",
                "sum",
            ),
            denominator=(
                "projection_denominator",
                "sum",
            ),
            events=(
                "projection_numerator",
                "size",
            ),
        )
        .sort_values(
            "event_date_local"
        )
        .reset_index(
            drop=True
        )
    )


def moving_block_bootstrap_beta(
    date_df: pd.DataFrame,
    block_length: int,
    reps: int,
    rng: np.random.Generator,
):
    nums = (
        date_df[
            "numerator"
        ]
        .to_numpy(
            dtype=float
        )
    )

    dens = (
        date_df[
            "denominator"
        ]
        .to_numpy(
            dtype=float
        )
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
                    s,
                    s + block_length,
                )
                for s in chosen
            ]
        )[:n]

        numerator = (
            nums[
                indices
            ].sum()
        )

        denominator = (
            dens[
                indices
            ].sum()
        )

        out[b] = (
            numerator
            / denominator
            if denominator > 0
            else np.nan
        )

    return out[
        np.isfinite(out)
    ]


def evaluate_population(
    events: pd.DataFrame,
    post_col: str,
    market: pd.DataFrame,
):
    rows = []

    for event in events.itertuples(
        index=False
    ):
        pre_time = pd.Timestamp(
            event.pre_snapshot_utc
        )

        post_time = pd.Timestamp(
            getattr(
                event,
                post_col,
            )
        )

        if pre_time.tzinfo is None:
            pre_time = (
                pre_time.tz_localize(
                    "UTC"
                )
            )
        else:
            pre_time = (
                pre_time.tz_convert(
                    "UTC"
                )
            )

        if post_time.tzinfo is None:
            post_time = (
                post_time.tz_localize(
                    "UTC"
                )
            )
        else:
            post_time = (
                post_time.tz_convert(
                    "UTC"
                )
            )

        event_market = market[
            (
                market["city"]
                == event.city
            )
            & (
                market[
                    "event_date_local"
                ]
                == event.event_date_local
            )
            & (
                market[
                    "event_ticker"
                ]
                == event.event_ticker
            )
        ].copy()

        pre = event_market[
            event_market[
                "timestamp_utc"
            ]
            == pre_time
        ].copy()

        post = event_market[
            event_market[
                "timestamp_utc"
            ]
            == post_time
        ].copy()

        if (
            len(pre) != 6
            or len(post) != 6
        ):
            raise RuntimeError(
                f"Expected six buckets for "
                f"{event.city} "
                f"{event.event_date_local}"
            )

        if (
            pre[
                "market_ticker"
            ].nunique()
            != 6
            or post[
                "market_ticker"
            ].nunique()
            != 6
        ):
            raise RuntimeError(
                "Duplicate/missing market tickers."
            )

        pre = pre.sort_values(
            "market_ticker"
        ).reset_index(
            drop=True
        )

        post = post.sort_values(
            "market_ticker"
        ).reset_index(
            drop=True
        )

        if not (
            pre[
                "market_ticker"
            ].tolist()
            ==
            post[
                "market_ticker"
            ].tolist()
        ):
            raise RuntimeError(
                "PRE/POST bucket sets differ."
            )

        if not (
            pre[
                "bucket_label"
            ].tolist()
            ==
            post[
                "bucket_label"
            ].tolist()
        ):
            raise RuntimeError(
                "PRE/POST bucket labels differ."
            )

        q_old = weather_proxy_vector(
            pre,
            mu=event.old_txn,
            sigma=event.old_xnd,
        )

        q_new = weather_proxy_vector(
            pre,
            mu=event.new_txn,
            sigma=event.new_xnd,
        )

        p_pre = (
            market_probability_vector(
                pre
            )
        )

        p_post = (
            market_probability_vector(
                post
            )
        )

        delta_q = (
            q_new - q_old
        )

        delta_p = (
            p_post - p_pre
        )

        numerator = float(
            np.dot(
                delta_q,
                delta_p,
            )
        )

        denominator = float(
            np.dot(
                delta_q,
                delta_q,
            )
        )

        dq_l1 = float(
            np.abs(
                delta_q
            ).sum()
        )

        dp_l1 = float(
            np.abs(
                delta_p
            ).sum()
        )

        rows.append(
            {
                "event_date_local":
                    event.event_date_local,
                "city":
                    event.city,
                "event_ticker":
                    event.event_ticker,

                "revision_sequence":
                    event.revision_sequence,
                "transition":
                    event.transition,

                "old_txn":
                    event.old_txn,
                "old_xnd":
                    event.old_xnd,
                "new_txn":
                    event.new_txn,
                "new_xnd":
                    event.new_xnd,

                "delta_txn":
                    event.delta_txn,
                "delta_xnd":
                    event.delta_xnd,

                "pre_snapshot_utc":
                    pre_time.isoformat(),
                "post_snapshot_utc":
                    post_time.isoformat(),

                "weather_revision_l1":
                    dq_l1,
                "market_move_l1":
                    dp_l1,

                "projection_numerator":
                    numerator,
                "projection_denominator":
                    denominator,

                "directional_dot_positive":
                    numerator > 0,
                "directional_dot_zero":
                    np.isclose(
                        numerator,
                        0.0,
                        atol=1e-15,
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def main():
    alignment = pd.read_csv(
        ALIGNMENT_PATH
    )

    pairs = pd.read_csv(
        PAIRS_PATH
    )

    market = pd.read_csv(
        MARKET_PATH
    )

    market[
        "timestamp_utc"
    ] = pd.to_datetime(
        market[
            "timestamp_utc"
        ],
        utc=True,
    )

    key = [
        "event_date_local",
        "city",
        "revision_sequence",
    ]

    pair_cols = [
        *key,
        "old_txn",
        "old_xnd",
        "new_txn",
        "new_xnd",
    ]

    data = alignment.merge(
        pairs[
            pair_cols
        ],
        on=key,
        how="left",
        validate="one_to_one",
    )

    # Verify required weather revision fields exist
    required_revision_cols = [
        "old_txn",
        "old_xnd",
        "new_txn",
        "new_xnd",
        "delta_txn",
        "delta_xnd",
    ]

    missing = [
        c for c in required_revision_cols
        if c not in data.columns
    ]

    if missing:
        raise RuntimeError(
            f"Missing revision columns after merge: {missing}"
        )

    if data[
        [
            "old_txn",
            "old_xnd",
            "new_txn",
            "new_xnd",
        ]
    ].isna().any().any():
        raise RuntimeError(
            "Weather-state merge failure."
        )

    primary = data[
        data[
            "any_weather_change"
        ].astype(bool)
        & data[
            "clean_pre_post1h"
        ].astype(bool)
    ].copy()

    secondary_2h = data[
        data[
            "any_weather_change"
        ].astype(bool)
        & data[
            "clean_pre_post2h"
        ].astype(bool)
    ].copy()

    if len(primary) != EXPECTED_PRIMARY_EVENTS:
        raise RuntimeError(
            f"Expected "
            f"{EXPECTED_PRIMARY_EVENTS} "
            f"primary events; "
            f"found {len(primary)}"
        )

    if (
        primary[
            "event_date_local"
        ].nunique()
        != 45
    ):
        raise RuntimeError(
            "Expected 45 primary calendar dates."
        )

    primary_metrics = (
        evaluate_population(
            primary,
            post_col=
                "post1_snapshot_utc",
            market=market,
        )
    )

    secondary_2h_metrics = (
        evaluate_population(
            secondary_2h,
            post_col=
                "post2_snapshot_utc",
            market=market,
        )
    )

    primary_metrics.to_csv(
        OUTDIR
        / "v2_market_reaction_event_metrics_1h.csv",
        index=False,
    )

    secondary_2h_metrics.to_csv(
        OUTDIR
        / "v2_market_reaction_event_metrics_2h.csv",
        index=False,
    )

    primary_beta = (
        beta_from_events(
            primary_metrics
        )
    )

    secondary_2h_beta = (
        beta_from_events(
            secondary_2h_metrics
        )
    )

    dates = date_contributions(
        primary_metrics
    )

    dates.to_csv(
        OUTDIR
        / "v2_market_reaction_date_contributions.csv",
        index=False,
    )

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    cis = {}

    for block in (
        1,
        3,
        7,
    ):
        boot = (
            moving_block_bootstrap_beta(
                dates,
                block_length=block,
                reps=BOOTSTRAP_REPS,
                rng=rng,
            )
        )

        cis[block] = (
            float(
                np.quantile(
                    boot,
                    0.025,
                )
            ),
            float(
                np.quantile(
                    boot,
                    0.975,
                )
            ),
        )

    directional_positive = float(
        primary_metrics[
            "directional_dot_positive"
        ].mean()
    )

    directional_zero = int(
        primary_metrics[
            "directional_dot_zero"
        ].sum()
    )

    by_city = []

    for city, g in (
        primary_metrics.groupby(
            "city"
        )
    ):
        by_city.append(
            {
                "city":
                    city,
                "events":
                    len(g),
                "beta":
                    beta_from_events(
                        g
                    ),
                "positive_dot_fraction":
                    float(
                        g[
                            "directional_dot_positive"
                        ].mean()
                    ),
            }
        )

    by_city = pd.DataFrame(
        by_city
    )

    by_transition = []

    transition_order = [
        "prev18Z->00Z",
        "00Z->06Z",
        "06Z->12Z",
    ]

    for transition in (
        transition_order
    ):
        g = primary_metrics[
            primary_metrics[
                "transition"
            ]
            == transition
        ]

        by_transition.append(
            {
                "transition":
                    transition,
                "events":
                    len(g),
                "beta":
                    beta_from_events(
                        g
                    ),
                "positive_dot_fraction":
                    float(
                        g[
                            "directional_dot_positive"
                        ].mean()
                    ),
            }
        )

    by_transition = pd.DataFrame(
        by_transition
    )

    by_city.to_csv(
        OUTDIR
        / "v2_market_reaction_by_city.csv",
        index=False,
    )

    by_transition.to_csv(
        OUTDIR
        / "v2_market_reaction_by_transition.csv",
        index=False,
    )

    summary = [
        "V2 H2.1 MARKET-REACTION EVENT STUDY",
        "=" * 88,
        "",
        (
            "Interpretation: positive beta means "
            "market probabilities moved, on average, "
            "in the direction of the newly published "
            "weather-proxy revision."
        ),
        "",
        "PRIMARY +1H POPULATION",
        (
            f"  events:                 "
            f"{len(primary_metrics)}"
        ),
        (
            f"  calendar dates:         "
            f"{primary_metrics['event_date_local'].nunique()}"
        ),
        (
            f"  beta:                   "
            f"{primary_beta:+.6f}"
        ),
        (
            f"  positive-dot fraction:  "
            f"{directional_positive:.3f}"
        ),
        (
            f"  zero-dot events:        "
            f"{directional_zero}"
        ),
        "",
        "Primary 3-day moving-block bootstrap:",
        (
            f"  95% CI: "
            f"[{cis[3][0]:+.6f}, "
            f"{cis[3][1]:+.6f}]"
        ),
        "",
        "Sensitivity:",
        (
            f"  1-day CI: "
            f"[{cis[1][0]:+.6f}, "
            f"{cis[1][1]:+.6f}]"
        ),
        (
            f"  7-day CI: "
            f"[{cis[7][0]:+.6f}, "
            f"{cis[7][1]:+.6f}]"
        ),
        "",
        "SECONDARY +2H",
        (
            f"  events:                 "
            f"{len(secondary_2h_metrics)}"
        ),
        (
            f"  beta:                   "
            f"{secondary_2h_beta:+.6f}"
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
        "RESTRICTION:",
        (
            "No settlement outcomes, prediction "
            "accuracy, executable trade prices, fees, "
            "or PnL were used."
        ),
        (
            "This result cannot establish incomplete "
            "assimilation, tradeability, or alpha."
        ),
    ]

    summary_text = (
        "\n".join(summary)
        + "\n"
    )

    summary_path = (
        OUTDIR
        / "v2_market_reaction_summary.txt"
    )

    summary_path.write_text(
        summary_text,
        encoding="utf-8",
    )

    manifest = [
        "V2 H2.1 PRE-RESULT / RESULT MANIFEST",
        "=" * 88,
        (
            "Created UTC: "
            + datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "",
        (
            "No settlement or PnL inputs are used "
            "by this evaluator."
        ),
        "",
    ]

    manifest_files = [
        PROTOCOL_PATH,
        ALIGNMENT_PATH,
        PAIRS_PATH,
        MARKET_PATH,
        Path(__file__),
    ]

    for path in manifest_files:
        manifest.append(
            f"{sha256(path)}  {path}"
        )

    (
        OUTDIR
        / "v2_market_reaction_manifest.txt"
    ).write_text(
        "\n".join(
            manifest
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(summary_text)

    print(
        "Saved:"
    )
    print(
        "  results/v2_market_reaction/"
        "v2_market_reaction_event_metrics_1h.csv"
    )
    print(
        "  results/v2_market_reaction/"
        "v2_market_reaction_event_metrics_2h.csv"
    )
    print(
        "  results/v2_market_reaction/"
        "v2_market_reaction_by_city.csv"
    )
    print(
        "  results/v2_market_reaction/"
        "v2_market_reaction_by_transition.csv"
    )
    print(
        "  results/v2_market_reaction/"
        "v2_market_reaction_summary.txt"
    )


if __name__ == "__main__":
    main()
