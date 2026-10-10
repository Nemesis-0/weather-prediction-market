from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DATA_PATH = Path("data/processed/modeling_master_event.csv")
RESULTS_DIR = Path("results/development")

EPSILON = 1e-6
BOOTSTRAP_REPS = 10_000
RANDOM_SEED = 20260930


def moving_block_bootstrap_mean(
    values: np.ndarray,
    block_length: int,
    reps: int,
    rng: np.random.Generator,
) -> np.ndarray:
    n = len(values)

    if block_length < 1 or block_length > n:
        raise ValueError("Invalid block length.")

    starts = np.arange(
        0,
        n - block_length + 1,
    )

    out = np.empty(reps)

    blocks_needed = int(
        np.ceil(n / block_length)
    )

    for b in range(reps):
        sampled_starts = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )

        sample = np.concatenate(
            [
                values[
                    s:s + block_length
                ]
                for s in sampled_starts
            ]
        )[:n]

        out[b] = sample.mean()

    return out


def ci(x: np.ndarray):
    return (
        np.quantile(x, 0.025),
        np.quantile(x, 0.975),
    )


def main():
    df = pd.read_csv(DATA_PATH)

    prob_cols = [
        f"bucket_{k}_market_prob"
        for k in range(1, 7)
    ]

    outcome_cols = [
        f"bucket_{k}_outcome"
        for k in range(1, 7)
    ]

    probs = df[prob_cols].to_numpy(
        dtype=float
    )

    y = df[outcome_cols].to_numpy(
        dtype=float
    )

    # ---------------------------------------------
    # Integrity
    # ---------------------------------------------

    if not np.allclose(
        probs.sum(axis=1),
        1.0,
        atol=1e-10,
    ):
        raise RuntimeError(
            "Market probabilities do not sum to 1."
        )

    if not np.all(
        y.sum(axis=1) == 1
    ):
        raise RuntimeError(
            "Outcomes are not one-hot."
        )

    winner_idx = np.argmax(
        y,
        axis=1,
    )

    winner_prob_raw = probs[
        np.arange(len(df)),
        winner_idx,
    ]

    exact_zero_winner = (
        winner_prob_raw == 0
    )

    # ---------------------------------------------
    # Fixed numerical clipping for log loss
    # ---------------------------------------------

    scored_probs = np.clip(
        probs,
        EPSILON,
        1 - EPSILON,
    )

    scored_probs = (
        scored_probs
        / scored_probs.sum(
            axis=1,
            keepdims=True,
        )
    )

    winner_prob_scored = (
        scored_probs[
            np.arange(len(df)),
            winner_idx,
        ]
    )

    log_loss = -np.log(
        winner_prob_scored
    )

    brier = np.sum(
        (scored_probs - y) ** 2,
        axis=1,
    )

    top_pick = np.argmax(
        probs,
        axis=1,
    )

    top1_correct = (
        top_pick == winner_idx
    ).astype(int)

    entropy = -np.sum(
        scored_probs
        * np.log(scored_probs),
        axis=1,
    )

    # ---------------------------------------------
    # Event-level result table
    # ---------------------------------------------

    result = df[
        [
            "city",
            "event_date_local",
            "event_ticker",
            "market_snapshot_utc",
            "snapshot_age_minutes",
            "midpoint_sum",
            "total_spread",
            "outcome_bucket_index",
        ]
    ].copy()

    result["winner_market_prob"] = (
        winner_prob_raw
    )

    result["m0_raw_log_loss"] = (
        log_loss
    )

    result["m0_raw_brier"] = (
        brier
    )

    result["m0_raw_top1_correct"] = (
        top1_correct
    )

    result["market_entropy"] = (
        entropy
    )

    result["winner_exact_zero_prob"] = (
        exact_zero_winner
    )

    # ---------------------------------------------
    # Descriptive summaries
    # ---------------------------------------------

    overall = {
        "n_city_days": len(result),
        "mean_log_loss":
            result["m0_raw_log_loss"].mean(),
        "mean_brier":
            result["m0_raw_brier"].mean(),
        "top1_accuracy":
            result["m0_raw_top1_correct"].mean(),
        "mean_winner_probability":
            result["winner_market_prob"].mean(),
        "median_winner_probability":
            result["winner_market_prob"].median(),
        "zero_prob_winners":
            int(
                result[
                    "winner_exact_zero_prob"
                ].sum()
            ),
    }

    by_city = (
        result
        .groupby("city")
        .agg(
            n=("event_ticker", "size"),
            log_loss=(
                "m0_raw_log_loss",
                "mean",
            ),
            brier=(
                "m0_raw_brier",
                "mean",
            ),
            top1_accuracy=(
                "m0_raw_top1_correct",
                "mean",
            ),
            mean_winner_prob=(
                "winner_market_prob",
                "mean",
            ),
        )
        .round(4)
    )

    # ---------------------------------------------
    # Primary date-level uncertainty
    #
    # All three cities for each date remain together.
    # ---------------------------------------------

    daily = (
        result
        .groupby("event_date_local")
        .agg(
            log_loss=(
                "m0_raw_log_loss",
                "mean",
            ),
            brier=(
                "m0_raw_brier",
                "mean",
            ),
            top1_accuracy=(
                "m0_raw_top1_correct",
                "mean",
            ),
        )
        .sort_index()
    )

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    bootstrap_results = {}

    for block_length in (1, 3, 7):
        boot_log = (
            moving_block_bootstrap_mean(
                daily["log_loss"].to_numpy(),
                block_length,
                BOOTSTRAP_REPS,
                rng,
            )
        )

        boot_brier = (
            moving_block_bootstrap_mean(
                daily["brier"].to_numpy(),
                block_length,
                BOOTSTRAP_REPS,
                rng,
            )
        )

        log_ci = ci(boot_log)
        brier_ci = ci(boot_brier)

        bootstrap_results[
            block_length
        ] = {
            "log_loss_low":
                log_ci[0],
            "log_loss_high":
                log_ci[1],
            "brier_low":
                brier_ci[0],
            "brier_high":
                brier_ci[1],
        }

    # ---------------------------------------------
    # Stale snapshot audit
    # ---------------------------------------------

    stale = result[
        result["snapshot_age_minutes"] > 0
    ].copy()

    # ---------------------------------------------
    # Save
    # ---------------------------------------------

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        RESULTS_DIR
        / "m0_raw_event_scores.csv",
        index=False,
    )

    daily.to_csv(
        RESULTS_DIR
        / "m0_raw_daily_scores.csv"
    )

    stale.to_csv(
        RESULTS_DIR
        / "m0_raw_stale_snapshots.csv",
        index=False,
    )

    # ---------------------------------------------
    # Console summary
    # ---------------------------------------------

    lines = [
        "M0-raw Market-only baseline",
        "=" * 64,
        f"City-days:                    {overall['n_city_days']}",
        f"Mean multiclass log loss:     {overall['mean_log_loss']:.4f}",
        f"Mean multiclass Brier score:  {overall['mean_brier']:.4f}",
        f"Top-1 market accuracy:        {overall['top1_accuracy']:.4f}",
        f"Mean winner probability:      {overall['mean_winner_probability']:.4f}",
        f"Median winner probability:    {overall['median_winner_probability']:.4f}",
        f"Exact-zero winning probs:     {overall['zero_prob_winners']}",
        "",
        "By city:",
        by_city.to_string(),
        "",
        "Primary uncertainty: 3-day moving-block bootstrap",
        (
            "  Log loss 95% CI: "
            f"[{bootstrap_results[3]['log_loss_low']:.4f}, "
            f"{bootstrap_results[3]['log_loss_high']:.4f}]"
        ),
        (
            "  Brier 95% CI:    "
            f"[{bootstrap_results[3]['brier_low']:.4f}, "
            f"{bootstrap_results[3]['brier_high']:.4f}]"
        ),
        "",
        "Pre-specified sensitivity:",
        (
            "  1-day log-loss CI: "
            f"[{bootstrap_results[1]['log_loss_low']:.4f}, "
            f"{bootstrap_results[1]['log_loss_high']:.4f}]"
        ),
        (
            "  7-day log-loss CI: "
            f"[{bootstrap_results[7]['log_loss_low']:.4f}, "
            f"{bootstrap_results[7]['log_loss_high']:.4f}]"
        ),
        "",
        f"Non-exact 10:00 snapshots:   {len(stale)}",
    ]

    audit_path = (
        RESULTS_DIR
        / "m0_raw_summary.txt"
    )

    audit_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        "\n" + "\n".join(lines)
    )


if __name__ == "__main__":
    main()
