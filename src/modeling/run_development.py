from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.modeling.conditional_softmax import (
    MODELS,
    coefficient_dict,
    fit_model,
    predict_model,
)


DATA_PATH = Path(
    "data/processed/model_features_event.csv"
)

RESULTS_DIR = Path(
    "results/development"
)

LAMBDAS = (
    0.001,
    0.01,
    0.1,
    1.0,
    10.0,
)

INITIAL_TRAIN_DATES = 14

SCORE_EPSILON = 1e-6

TIE_TOLERANCE = 1e-8


def get_matrix(
    df: pd.DataFrame,
    prefix: str,
) -> np.ndarray:
    cols = [
        f"bucket_{k}_{prefix}"
        for k in range(1, 7)
    ]

    return df[
        cols
    ].to_numpy(
        dtype=float,
    )


def score_probs(
    probs: np.ndarray,
    y_idx: np.ndarray,
):
    p = np.clip(
        probs,
        SCORE_EPSILON,
        1 - SCORE_EPSILON,
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

    log_loss = -np.log(
        p[
            np.arange(len(y_idx)),
            y_idx,
        ]
    )

    brier = np.sum(
        (p - y) ** 2,
        axis=1,
    )

    return log_loss, brier


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
            "Outcomes are not one-hot."
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


def main():
    df = pd.read_csv(DATA_PATH)

    dev = (
        df[
            df["historical_split"]
            == "development"
        ]
        .copy()
        .sort_values(
            [
                "event_date_local",
                "city",
            ]
        )
        .reset_index(drop=True)
    )

    holdout_count = int(
        (
            df["historical_split"]
            == "historical_holdout"
        ).sum()
    )

    dates = sorted(
        dev["event_date_local"]
        .unique()
        .tolist()
    )

    if len(dev) != 93:
        raise RuntimeError(
            f"Expected 93 development "
            f"city-days, found {len(dev)}."
        )

    if len(dates) != 31:
        raise RuntimeError(
            f"Expected 31 development "
            f"dates, found {len(dates)}."
        )

    per_date = (
        dev.groupby(
            "event_date_local"
        )
        .size()
    )

    if not (
        per_date == 3
    ).all():
        raise RuntimeError(
            "Every development date "
            "must contain all three cities."
        )

    (
        log_market,
        log_weather,
        raw_market_prob,
        y_idx,
    ) = arrays(dev)

    all_predictions = []

    # -------------------------------------------------
    # Rolling-origin predictions for every model/lambda
    # -------------------------------------------------

    for model in MODELS:
        print(
            f"\nRunning {model}..."
        )

        for lam in LAMBDAS:
            print(
                f"  lambda={lam}"
            )

            for test_pos in range(
                INITIAL_TRAIN_DATES,
                len(dates),
            ):
                test_date = dates[
                    test_pos
                ]

                train_dates = set(
                    dates[:test_pos]
                )

                train_mask = (
                    dev[
                        "event_date_local"
                    ]
                    .isin(train_dates)
                    .to_numpy()
                )

                test_mask = (
                    dev[
                        "event_date_local"
                    ]
                    .eq(test_date)
                    .to_numpy()
                )

                theta, _ = fit_model(
                    log_market[
                        train_mask
                    ],
                    log_weather[
                        train_mask
                    ],
                    y_idx[
                        train_mask
                    ],
                    model=model,
                    lam=lam,
                )

                pred = predict_model(
                    theta,
                    log_market[
                        test_mask
                    ],
                    log_weather[
                        test_mask
                    ],
                    model=model,
                )

                test_y = y_idx[
                    test_mask
                ]

                ll, br = score_probs(
                    pred,
                    test_y,
                )

                test_rows = dev.loc[
                    test_mask,
                    [
                        "city",
                        "event_date_local",
                        "event_ticker",
                    ],
                ].reset_index(
                    drop=True
                )

                for i in range(
                    len(test_rows)
                ):
                    record = {
                        "model": model,
                        "lambda": lam,
                        "train_dates":
                            test_pos,
                        "train_city_days":
                            int(
                                train_mask.sum()
                            ),
                        "city":
                            test_rows.loc[
                                i,
                                "city",
                            ],
                        "event_date_local":
                            test_date,
                        "event_ticker":
                            test_rows.loc[
                                i,
                                "event_ticker",
                            ],
                        "outcome_bucket_index":
                            int(
                                test_y[i]
                                + 1
                            ),
                        "log_loss":
                            float(ll[i]),
                        "brier":
                            float(br[i]),
                    }

                    for k in range(6):
                        record[
                            f"pred_{k + 1}"
                        ] = float(
                            pred[i, k]
                        )

                    all_predictions.append(
                        record
                    )

    pred_df = pd.DataFrame(
        all_predictions
    )

    # -------------------------------------------------
    # Lambda-selection summaries
    # -------------------------------------------------

    lambda_rows = []

    for (
        model,
        lam,
    ), g in pred_df.groupby(
        [
            "model",
            "lambda",
        ]
    ):
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
            )
        )

        lambda_rows.append(
            {
                "model": model,
                "lambda": lam,
                "n_validation_dates":
                    len(daily),
                "n_validation_city_days":
                    len(g),
                "mean_date_log_loss":
                    daily[
                        "log_loss"
                    ].mean(),
                "mean_date_brier":
                    daily[
                        "brier"
                    ].mean(),
            }
        )

    lambda_summary = (
        pd.DataFrame(
            lambda_rows
        )
        .sort_values(
            [
                "model",
                "lambda",
            ]
        )
        .reset_index(drop=True)
    )

    selected = {}

    for model in MODELS:
        s = lambda_summary[
            lambda_summary["model"]
            == model
        ].copy()

        min_loss = (
            s["mean_date_log_loss"]
            .min()
        )

        tied = s[
            s["mean_date_log_loss"]
            <= (
                min_loss
                + TIE_TOLERANCE
            )
        ]

        # Pre-frozen deterministic tie-break:
        # choose larger lambda.
        chosen = tied.sort_values(
            "lambda",
            ascending=False,
        ).iloc[0]

        selected[
            model
        ] = float(
            chosen["lambda"]
        )

    # -------------------------------------------------
    # Selected rolling predictions
    # -------------------------------------------------

    selected_parts = []

    for model in MODELS:
        part = pred_df[
            (pred_df["model"] == model)
            & (
                pred_df["lambda"]
                == selected[model]
            )
        ].copy()

        selected_parts.append(
            part
        )

    selected_pred = pd.concat(
        selected_parts,
        ignore_index=True,
    )

    selected_summary_rows = []

    for model, g in selected_pred.groupby(
        "model"
    ):
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
            )
        )

        selected_summary_rows.append(
            {
                "model": model,
                "selected_lambda":
                    selected[model],
                "validation_dates":
                    len(daily),
                "validation_city_days":
                    len(g),
                "mean_log_loss":
                    daily[
                        "log_loss"
                    ].mean(),
                "mean_brier":
                    daily[
                        "brier"
                    ].mean(),
            }
        )

    selected_summary = (
        pd.DataFrame(
            selected_summary_rows
        )
        .sort_values("model")
    )

    # -------------------------------------------------
    # Raw M0 baseline over exactly same rolling dates
    # -------------------------------------------------

    eval_dates = set(
        dates[
            INITIAL_TRAIN_DATES:
        ]
    )

    raw_mask = (
        dev["event_date_local"]
        .isin(eval_dates)
        .to_numpy()
    )

    raw_ll, raw_br = score_probs(
        raw_market_prob[
            raw_mask
        ],
        y_idx[
            raw_mask
        ],
    )

    raw_eval = dev.loc[
        raw_mask,
        [
            "city",
            "event_date_local",
            "event_ticker",
        ],
    ].copy()

    raw_eval[
        "log_loss"
    ] = raw_ll

    raw_eval[
        "brier"
    ] = raw_br

    raw_daily = (
        raw_eval
        .groupby(
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

    raw_summary = {
        "mean_log_loss":
            raw_daily[
                "log_loss"
            ].mean(),
        "mean_brier":
            raw_daily[
                "brier"
            ].mean(),
    }

    # -------------------------------------------------
    # M2 - M0 paired development difference
    # descriptive only
    # -------------------------------------------------

    m0 = selected_pred[
        selected_pred["model"]
        == "M0"
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

    m2 = selected_pred[
        selected_pred["model"]
        == "M2"
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
        "delta_log_loss_m2_minus_m0"
    ] = (
        paired["m2_log_loss"]
        - paired["m0_log_loss"]
    )

    paired[
        "delta_brier_m2_minus_m0"
    ] = (
        paired["m2_brier"]
        - paired["m0_brier"]
    )

    paired_daily = (
        paired.groupby(
            "event_date_local"
        )
        .agg(
            delta_log_loss=(
                "delta_log_loss_m2_minus_m0",
                "mean",
            ),
            delta_brier=(
                "delta_brier_m2_minus_m0",
                "mean",
            ),
        )
    )

    # -------------------------------------------------
    # Final all-development fits using selected lambda
    # Still no holdout evaluation.
    # -------------------------------------------------

    full_fit = {}

    for model in MODELS:
        theta, opt = fit_model(
            log_market,
            log_weather,
            y_idx,
            model=model,
            lam=selected[model],
        )

        full_fit[model] = {
            "selected_lambda":
                selected[model],
            "n_development_dates":
                len(dates),
            "n_development_city_days":
                len(dev),
            "optimizer_success":
                bool(opt.success),
            "objective":
                float(opt.fun),
            "coefficients":
                coefficient_dict(
                    theta,
                    model,
                ),
        }

    # -------------------------------------------------
    # Save
    # -------------------------------------------------

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    pred_df.to_csv(
        RESULTS_DIR
        / "development_all_lambda_predictions.csv",
        index=False,
    )

    lambda_summary.to_csv(
        RESULTS_DIR
        / "development_lambda_selection.csv",
        index=False,
    )

    selected_pred.to_csv(
        RESULTS_DIR
        / "development_selected_predictions.csv",
        index=False,
    )

    selected_summary.to_csv(
        RESULTS_DIR
        / "development_selected_summary.csv",
        index=False,
    )

    paired.to_csv(
        RESULTS_DIR
        / "development_m2_vs_m0_paired.csv",
        index=False,
    )

    paired_daily.to_csv(
        RESULTS_DIR
        / "development_m2_vs_m0_daily.csv"
    )

    (
        RESULTS_DIR
        / "development_full_fit.json"
    ).write_text(
        json.dumps(
            full_fit,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------
    # Console report
    # -------------------------------------------------

    lines = [
        "Rolling-origin development results",
        "=" * 72,
        f"Development dates:                 {len(dates)}",
        f"Development city-days:             {len(dev)}",
        f"Initial training dates:            {INITIAL_TRAIN_DATES}",
        f"Rolling validation dates:          {len(dates) - INITIAL_TRAIN_DATES}",
        f"Rolling validation city-days:      {len(raw_eval)}",
        f"Historical holdout city-days:      {holdout_count}",
        "Historical holdout evaluated:      NO",
        "",
        "Lambda selection:",
    ]

    for model in MODELS:
        row = selected_summary[
            selected_summary[
                "model"
            ] == model
        ].iloc[0]

        lines.append(
            f"  {model}: "
            f"lambda={row['selected_lambda']:g} | "
            f"logloss={row['mean_log_loss']:.4f} | "
            f"brier={row['mean_brier']:.4f}"
        )

    lines.extend(
        [
            "",
            "Raw normalized-market reference",
            "over the same 17 rolling validation dates:",
            (
                "  logloss="
                f"{raw_summary['mean_log_loss']:.4f}"
                " | "
                "brier="
                f"{raw_summary['mean_brier']:.4f}"
            ),
            "",
            "Development paired M2 - fitted M0",
            "(negative favors M2; descriptive only):",
            (
                "  mean date log-loss delta: "
                f"{paired_daily['delta_log_loss'].mean():+.4f}"
            ),
            (
                "  mean date Brier delta:   "
                f"{paired_daily['delta_brier'].mean():+.4f}"
            ),
            "",
            "Full-development coefficients:",
        ]
    )

    for model in MODELS:
        lines.append(
            f"  {model}:"
        )

        for name, value in (
            full_fit[
                model
            ][
                "coefficients"
            ].items()
        ):
            lines.append(
                f"    {name}: {value:+.4f}"
            )

    lines.extend(
        [
            "",
            "IMPORTANT:",
            "These are development results used for lambda selection.",
            "They are not historical-holdout evidence and carry no",
            "formal claim of incremental predictive value.",
        ]
    )

    summary_path = (
        RESULTS_DIR
        / "development_model_summary.txt"
    )

    summary_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        "\n" + "\n".join(lines)
    )


if __name__ == "__main__":
    main()
