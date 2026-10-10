from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.modeling.conditional_softmax import (
    fit_model,
    predict_model,
    coefficient_dict,
)


DATA = Path(
    "data/processed/model_features_event.csv"
)

RESULTS = Path(
    "results/corrected_historical"
)

LAMBDAS = {
    "M0": 0.01,
    "M1": 1.0,
    "M2": 0.001,
}

MODELS = ("M0", "M1", "M2")

EPSILON = 1e-6

BOOTSTRAP_REPS = 10000
RANDOM_SEED = 20260930


def get_matrix(
    df: pd.DataFrame,
    prefix: str,
):
    return df[
        [
            f"bucket_{k}_{prefix}"
            for k in range(1, 7)
        ]
    ].to_numpy(
        dtype=float
    )


def arrays(df: pd.DataFrame):
    log_market = get_matrix(
        df,
        "log_market_prob",
    )

    log_weather = get_matrix(
        df,
        "log_weather_proxy",
    )

    market_prob = get_matrix(
        df,
        "market_prob",
    )

    outcome = get_matrix(
        df,
        "outcome",
    )

    if not np.all(
        outcome.sum(axis=1) == 1
    ):
        raise RuntimeError(
            "Outcome matrix is not one-hot."
        )

    y_idx = np.argmax(
        outcome,
        axis=1,
    )

    return (
        log_market,
        log_weather,
        market_prob,
        y_idx,
    )


def score_probs(
    probs: np.ndarray,
    y_idx: np.ndarray,
):
    p = np.clip(
        probs,
        EPSILON,
        1 - EPSILON,
    )

    p = (
        p
        / p.sum(
            axis=1,
            keepdims=True,
        )
    )

    y = np.zeros_like(p)

    y[
        np.arange(len(y_idx)),
        y_idx,
    ] = 1.0

    ll = -np.log(
        p[
            np.arange(len(y_idx)),
            y_idx,
        ]
    )

    br = np.sum(
        (p - y) ** 2,
        axis=1,
    )

    top1 = (
        np.argmax(p, axis=1)
        == y_idx
    ).astype(int)

    return ll, br, top1


def moving_block_bootstrap_mean(
    values: np.ndarray,
    block_length: int,
    reps: int,
    rng: np.random.Generator,
):
    n = len(values)

    starts = np.arange(
        0,
        n - block_length + 1,
    )

    blocks_needed = int(
        np.ceil(
            n / block_length
        )
    )

    out = np.empty(reps)

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


def main():
    df = pd.read_csv(DATA)

    dev = (
        df[
            df["historical_split"]
            == "development"
        ]
        .sort_values(
            [
                "event_date_local",
                "city",
            ]
        )
        .reset_index(drop=True)
    )

    holdout = (
        df[
            df["historical_split"]
            == "historical_holdout"
        ]
        .sort_values(
            [
                "event_date_local",
                "city",
            ]
        )
        .reset_index(drop=True)
    )

    if len(dev) != 93:
        raise RuntimeError(
            f"Expected 93 development rows, "
            f"found {len(dev)}."
        )

    if len(holdout) != 45:
        raise RuntimeError(
            f"Expected 45 holdout rows, "
            f"found {len(holdout)}."
        )

    if (
        holdout[
            "event_date_local"
        ].nunique()
        != 15
    ):
        raise RuntimeError(
            "Expected exactly 15 holdout dates."
        )

    (
        dev_lm,
        dev_lw,
        _,
        dev_y,
    ) = arrays(dev)

    (
        test_lm,
        test_lw,
        raw_market,
        test_y,
    ) = arrays(holdout)

    predictions = []
    fitted_models = {}

    # --------------------------------------------------
    # Frozen model fits
    # --------------------------------------------------

    for model in MODELS:
        lam = LAMBDAS[model]

        theta, opt = fit_model(
            dev_lm,
            dev_lw,
            dev_y,
            model=model,
            lam=lam,
        )

        probs = predict_model(
            theta,
            test_lm,
            test_lw,
            model=model,
        )

        ll, br, top1 = score_probs(
            probs,
            test_y,
        )

        fitted_models[model] = {
            "lambda": lam,
            "objective":
                float(opt.fun),
            "coefficients":
                coefficient_dict(
                    theta,
                    model,
                ),
        }

        for i in range(
            len(holdout)
        ):
            row = {
                "model": model,
                "lambda": lam,
                "city":
                    holdout.loc[
                        i,
                        "city",
                    ],
                "event_date_local":
                    holdout.loc[
                        i,
                        "event_date_local",
                    ],
                "event_ticker":
                    holdout.loc[
                        i,
                        "event_ticker",
                    ],
                "outcome_bucket_index":
                    int(
                        test_y[i] + 1
                    ),
                "log_loss":
                    float(ll[i]),
                "brier":
                    float(br[i]),
                "top1_correct":
                    int(top1[i]),
            }

            for k in range(6):
                row[
                    f"pred_{k + 1}"
                ] = float(
                    probs[i, k]
                )

            predictions.append(row)

    pred = pd.DataFrame(
        predictions
    )

    # --------------------------------------------------
    # Raw market reference
    # --------------------------------------------------

    raw_ll, raw_br, raw_top1 = (
        score_probs(
            raw_market,
            test_y,
        )
    )

    raw = holdout[
        [
            "city",
            "event_date_local",
            "event_ticker",
        ]
    ].copy()

    raw[
        "log_loss"
    ] = raw_ll

    raw[
        "brier"
    ] = raw_br

    raw[
        "top1_correct"
    ] = raw_top1

    # --------------------------------------------------
    # Model summaries
    # --------------------------------------------------

    summary_rows = []

    for model in MODELS:
        g = pred[
            pred["model"] == model
        ]

        daily = (
            g.groupby(
                "event_date_local"
            )
            .agg(
                log_loss=(
                    "log_loss",
                    "mean",
                ),
                brier=(
                    "brier",
                    "mean",
                ),
                top1=(
                    "top1_correct",
                    "mean",
                ),
            )
        )

        summary_rows.append(
            {
                "model": model,
                "lambda":
                    LAMBDAS[model],
                "n_city_days":
                    len(g),
                "n_dates":
                    len(daily),
                "mean_log_loss":
                    daily[
                        "log_loss"
                    ].mean(),
                "mean_brier":
                    daily[
                        "brier"
                    ].mean(),
                "top1_accuracy":
                    g[
                        "top1_correct"
                    ].mean(),
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    raw_daily = (
        raw.groupby(
            "event_date_local"
        )
        .agg(
            log_loss=(
                "log_loss",
                "mean",
            ),
            brier=(
                "brier",
                "mean",
            ),
        )
    )

    # --------------------------------------------------
    # Primary paired M2 - M0 comparison
    # --------------------------------------------------

    m0 = pred[
        pred["model"] == "M0"
    ][
        [
            "city",
            "event_date_local",
            "log_loss",
            "brier",
        ]
    ].rename(
        columns={
            "log_loss":
                "m0_log_loss",
            "brier":
                "m0_brier",
        }
    )

    m2 = pred[
        pred["model"] == "M2"
    ][
        [
            "city",
            "event_date_local",
            "log_loss",
            "brier",
        ]
    ].rename(
        columns={
            "log_loss":
                "m2_log_loss",
            "brier":
                "m2_brier",
        }
    )

    paired = m0.merge(
        m2,
        on=[
            "city",
            "event_date_local",
        ],
        validate="one_to_one",
    )

    paired[
        "delta_log_loss"
    ] = (
        paired["m2_log_loss"]
        - paired["m0_log_loss"]
    )

    paired[
        "delta_brier"
    ] = (
        paired["m2_brier"]
        - paired["m0_brier"]
    )

    daily_delta = (
        paired.groupby(
            "event_date_local"
        )
        .agg(
            delta_log_loss=(
                "delta_log_loss",
                "mean",
            ),
            delta_brier=(
                "delta_brier",
                "mean",
            ),
        )
        .sort_index()
    )

    # --------------------------------------------------
    # Pre-specified moving-block uncertainty
    # --------------------------------------------------

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    ci_results = {}

    for block_length in (
        1,
        3,
        7,
    ):
        boot_ll = (
            moving_block_bootstrap_mean(
                daily_delta[
                    "delta_log_loss"
                ].to_numpy(),
                block_length,
                BOOTSTRAP_REPS,
                rng,
            )
        )

        boot_br = (
            moving_block_bootstrap_mean(
                daily_delta[
                    "delta_brier"
                ].to_numpy(),
                block_length,
                BOOTSTRAP_REPS,
                rng,
            )
        )

        ci_results[
            block_length
        ] = {
            "log_loss":
                [
                    float(
                        np.quantile(
                            boot_ll,
                            .025,
                        )
                    ),
                    float(
                        np.quantile(
                            boot_ll,
                            .975,
                        )
                    ),
                ],
            "brier":
                [
                    float(
                        np.quantile(
                            boot_br,
                            .025,
                        )
                    ),
                    float(
                        np.quantile(
                            boot_br,
                            .975,
                        )
                    ),
                ],
        }

    # --------------------------------------------------
    # By-city paired diagnostics
    # --------------------------------------------------

    by_city = (
        paired.groupby("city")
        .agg(
            n=(
                "delta_log_loss",
                "size",
            ),
            mean_delta_log_loss=(
                "delta_log_loss",
                "mean",
            ),
            median_delta_log_loss=(
                "delta_log_loss",
                "median",
            ),
            mean_delta_brier=(
                "delta_brier",
                "mean",
            ),
        )
    )

    # --------------------------------------------------
    # Save everything
    # --------------------------------------------------

    RESULTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    pred.to_csv(
        RESULTS
        / "corrected_historical_predictions.csv",
        index=False,
    )

    raw.to_csv(
        RESULTS
        / "corrected_historical_raw_market.csv",
        index=False,
    )

    summary.to_csv(
        RESULTS
        / "corrected_historical_model_summary.csv",
        index=False,
    )

    paired.to_csv(
        RESULTS
        / "corrected_historical_m2_vs_m0.csv",
        index=False,
    )

    daily_delta.to_csv(
        RESULTS
        / "corrected_historical_daily_delta.csv"
    )

    (
        RESULTS
        / "corrected_historical_fit.json"
    ).write_text(
        json.dumps(
            {
                "models":
                    fitted_models,
                "bootstrap_ci":
                    ci_results,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    # --------------------------------------------------
    # Human-readable report
    # --------------------------------------------------

    lines = [
        "CORRECTED HISTORICAL EVALUATION RESULTS",
        "=" * 76,
        "Development city-days:          93",
        "Corrected historical dates:      15",
        "Corrected historical city-days:  45",
        "",
        "Frozen fitted models:",
    ]

    for model in MODELS:
        row = summary[
            summary["model"]
            == model
        ].iloc[0]

        lines.append(
            f"  {model}: "
            f"lambda={row['lambda']:g} | "
            f"logloss={row['mean_log_loss']:.4f} | "
            f"brier={row['mean_brier']:.4f} | "
            f"top1={row['top1_accuracy']:.4f}"
        )

    lines.extend(
        [
            "",
            "Raw normalized market reference:",
            (
                "  logloss="
                f"{raw_daily['log_loss'].mean():.4f}"
                " | "
                "brier="
                f"{raw_daily['brier'].mean():.4f}"
                " | "
                "top1="
                f"{raw['top1_correct'].mean():.4f}"
            ),
            "",
            "PRIMARY: paired M2 - fitted M0",
            "(negative favors weather-augmented M2)",
            (
                "  Mean date log-loss delta: "
                f"{daily_delta['delta_log_loss'].mean():+.4f}"
            ),
            (
                "  Median date log-loss delta: "
                f"{daily_delta['delta_log_loss'].median():+.4f}"
            ),
            (
                "  Mean date Brier delta:   "
                f"{daily_delta['delta_brier'].mean():+.4f}"
            ),
            (
                "  Dates M2 beats M0:       "
                f"{int((daily_delta['delta_log_loss'] < 0).sum())}"
                f" / {len(daily_delta)}"
            ),
            "",
            "Primary 3-day moving-block bootstrap:",
            (
                "  Log-loss delta 95% CI: "
                f"[{ci_results[3]['log_loss'][0]:+.4f}, "
                f"{ci_results[3]['log_loss'][1]:+.4f}]"
            ),
            (
                "  Brier delta 95% CI:    "
                f"[{ci_results[3]['brier'][0]:+.4f}, "
                f"{ci_results[3]['brier'][1]:+.4f}]"
            ),
            "",
            "Sensitivity:",
            (
                "  1-day log-loss CI: "
                f"[{ci_results[1]['log_loss'][0]:+.4f}, "
                f"{ci_results[1]['log_loss'][1]:+.4f}]"
            ),
            (
                "  7-day log-loss CI: "
                f"[{ci_results[7]['log_loss'][0]:+.4f}, "
                f"{ci_results[7]['log_loss'][1]:+.4f}]"
            ),
            "",
            "By-city paired M2 - M0:",
            by_city.round(4).to_string(),
            "",
            "Historical evaluation recomputed after source-timing correction.",
            "Do not retune V1 based on these results.",
        ]
    )

    report = (
        RESULTS
        / "corrected_historical_summary.txt"
    )

    report.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        "\n" + "\n".join(lines)
    )


if __name__ == "__main__":
    main()
