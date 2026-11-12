from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


FEATURES = Path(
    "data/processed/model_features_event.csv"
)

DEV_PREDS = Path(
    "results/development/development_selected_predictions.csv"
)

HOLDOUT_PREDS = Path(
    "results/corrected_historical/corrected_historical_predictions.csv"
)

OUTDIR = Path(
    "results/corrected_historical_economics"
)

MODELS = ("M0", "M2")

BOOTSTRAP_REPS = 10_000
RANDOM_SEED = 20260930


def taker_fee_one_contract(price: float) -> float:
    """
    General Kalshi event-contract taker fee:
        0.07 * C * P * (1-P)

    Historical V1:
        C = 1
        multiplier = 1

    Round upward to the next cent.
    """

    raw = 0.07 * price * (1.0 - price)

    return math.ceil(
        raw * 100.0 - 1e-12
    ) / 100.0


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
        np.ceil(n / block_length)
    )

    out = np.empty(reps)

    for b in range(reps):
        chosen = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )

        sample = np.concatenate(
            [
                values[s:s + block_length]
                for s in chosen
            ]
        )[:n]

        out[b] = sample.mean()

    return out


def prepare_predictions():
    dev = pd.read_csv(
        DEV_PREDS
    )

    dev = dev[
        dev["model"].isin(MODELS)
    ].copy()

    dev[
        "economic_segment"
    ] = "rolling_development"

    hold = pd.read_csv(
        HOLDOUT_PREDS
    )

    hold = hold[
        hold["model"].isin(MODELS)
    ].copy()

    hold[
        "economic_segment"
    ] = "historical_holdout"

    preds = pd.concat(
        [dev, hold],
        ignore_index=True,
    )

    return preds


def main():
    features = pd.read_csv(
        FEATURES
    )

    preds = prepare_predictions()

    feature_cols = [
        "city",
        "event_date_local",
        "event_ticker",
    ]

    for k in range(1, 7):
        feature_cols.extend(
            [
                f"bucket_{k}_bid",
                f"bucket_{k}_ask",
                f"bucket_{k}_outcome",
            ]
        )

    merged = preds.merge(
        features[feature_cols],
        on=[
            "city",
            "event_date_local",
            "event_ticker",
        ],
        how="left",
        validate="many_to_one",
    )

    expected = {
        "rolling_development":
            51 * len(MODELS),
        "historical_holdout":
            45 * len(MODELS),
    }

    for segment, count in expected.items():
        actual = len(
            merged[
                merged[
                    "economic_segment"
                ] == segment
            ]
        )

        if actual != count:
            raise RuntimeError(
                f"{segment}: expected "
                f"{count}, got {actual}"
            )

    records = []

    for row in merged.itertuples(
        index=False
    ):
        candidates = []

        for k in range(1, 7):
            p = float(
                getattr(
                    row,
                    f"pred_{k}",
                )
            )

            bid = float(
                getattr(
                    row,
                    f"bucket_{k}_bid",
                )
            )

            ask = float(
                getattr(
                    row,
                    f"bucket_{k}_ask",
                )
            )

            outcome = int(
                getattr(
                    row,
                    f"bucket_{k}_outcome",
                )
            )

            # ------------------------------
            # YES
            # ------------------------------

            yes_price = ask
            yes_fee = (
                taker_fee_one_contract(
                    yes_price
                )
            )

            yes_ev = (
                p
                - yes_price
                - yes_fee
            )

            candidates.append(
                {
                    "bucket": k,
                    "side": "YES",
                    "model_probability":
                        p,
                    "action_probability":
                        p,
                    "entry_price":
                        yes_price,
                    "fee":
                        yes_fee,
                    "estimated_net_ev":
                        yes_ev,
                    "action_true":
                        outcome,
                }
            )

            # ------------------------------
            # NO
            # ------------------------------

            no_price = (
                1.0 - bid
            )

            no_prob = (
                1.0 - p
            )

            no_fee = (
                taker_fee_one_contract(
                    no_price
                )
            )

            no_ev = (
                no_prob
                - no_price
                - no_fee
            )

            candidates.append(
                {
                    "bucket": k,
                    "side": "NO",
                    "model_probability":
                        p,
                    "action_probability":
                        no_prob,
                    "entry_price":
                        no_price,
                    "fee":
                        no_fee,
                    "estimated_net_ev":
                        no_ev,
                    "action_true":
                        1 - outcome,
                }
            )

        best = max(
            candidates,
            key=lambda x:
                x["estimated_net_ev"],
        )

        trade = (
            best["estimated_net_ev"]
            > 0
        )

        if trade:
            realized_pnl = (
                best["action_true"]
                - best["entry_price"]
                - best["fee"]
            )
        else:
            realized_pnl = 0.0

        records.append(
            {
                "economic_segment":
                    row.economic_segment,
                "model":
                    row.model,
                "city":
                    row.city,
                "event_date_local":
                    row.event_date_local,
                "event_ticker":
                    row.event_ticker,
                "trade":
                    int(trade),
                "bucket":
                    (
                        best["bucket"]
                        if trade
                        else np.nan
                    ),
                "side":
                    (
                        best["side"]
                        if trade
                        else "NO_TRADE"
                    ),
                "entry_price":
                    (
                        best["entry_price"]
                        if trade
                        else 0.0
                    ),
                "fee":
                    (
                        best["fee"]
                        if trade
                        else 0.0
                    ),
                "estimated_net_ev":
                    (
                        best[
                            "estimated_net_ev"
                        ]
                        if trade
                        else 0.0
                    ),
                "action_true":
                    (
                        best["action_true"]
                        if trade
                        else np.nan
                    ),
                "realized_pnl":
                    realized_pnl,
            }
        )

    trades = pd.DataFrame(
        records
    )

    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    trades.to_csv(
        OUTDIR
        / "historical_trade_decisions.csv",
        index=False,
    )

    # --------------------------------------------------
    # Summary by segment/model
    # --------------------------------------------------

    summary_rows = []

    for (
        segment,
        model,
    ), g in trades.groupby(
        [
            "economic_segment",
            "model",
        ]
    ):
        executed = g[
            g["trade"] == 1
        ]

        positive_trade_pnl = (
            executed[
                executed[
                    "realized_pnl"
                ] > 0
            ][
                "realized_pnl"
            ].sum()
        )

        total_positive = max(
            positive_trade_pnl,
            0.0,
        )

        largest_positive = (
            executed[
                "realized_pnl"
            ].max()
            if len(executed)
            else np.nan
        )

        concentration = (
            largest_positive
            / total_positive
            if total_positive > 0
            else np.nan
        )

        summary_rows.append(
            {
                "segment":
                    segment,
                "model":
                    model,
                "city_days":
                    len(g),
                "trades":
                    int(
                        g["trade"].sum()
                    ),
                "no_trades":
                    int(
                        (g["trade"] == 0)
                        .sum()
                    ),
                "total_pnl":
                    g[
                        "realized_pnl"
                    ].sum(),
                "mean_pnl_per_city_day":
                    g[
                        "realized_pnl"
                    ].mean(),
                "mean_pnl_per_trade":
                    (
                        executed[
                            "realized_pnl"
                        ].mean()
                        if len(executed)
                        else np.nan
                    ),
                "win_rate":
                    (
                        (
                            executed[
                                "realized_pnl"
                            ] > 0
                        ).mean()
                        if len(executed)
                        else np.nan
                    ),
                "mean_estimated_edge":
                    (
                        executed[
                            "estimated_net_ev"
                        ].mean()
                        if len(executed)
                        else np.nan
                    ),
                "max_gain":
                    (
                        executed[
                            "realized_pnl"
                        ].max()
                        if len(executed)
                        else np.nan
                    ),
                "max_loss":
                    (
                        executed[
                            "realized_pnl"
                        ].min()
                        if len(executed)
                        else np.nan
                    ),
                "largest_win_share_of_positive_pnl":
                    concentration,
            }
        )

    summary = pd.DataFrame(
        summary_rows
    )

    summary.to_csv(
        OUTDIR
        / "historical_economic_summary.csv",
        index=False,
    )

    # --------------------------------------------------
    # Primary M2 - M0 holdout comparison
    # --------------------------------------------------

    hold = trades[
        trades["economic_segment"]
        == "historical_holdout"
    ]

    m0 = hold[
        hold["model"] == "M0"
    ][
        [
            "city",
            "event_date_local",
            "realized_pnl",
        ]
    ].rename(
        columns={
            "realized_pnl":
                "m0_pnl"
        }
    )

    m2 = hold[
        hold["model"] == "M2"
    ][
        [
            "city",
            "event_date_local",
            "realized_pnl",
        ]
    ].rename(
        columns={
            "realized_pnl":
                "m2_pnl"
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

    paired["delta_pnl"] = (
        paired["m2_pnl"]
        - paired["m0_pnl"]
    )

    daily = (
        paired
        .groupby(
            "event_date_local"
        )
        .agg(
            m0_pnl=(
                "m0_pnl",
                "sum",
            ),
            m2_pnl=(
                "m2_pnl",
                "sum",
            ),
            delta_pnl=(
                "delta_pnl",
                "mean",
            ),
        )
        .sort_index()
    )

    paired.to_csv(
        OUTDIR
        / "historical_holdout_paired_pnl.csv",
        index=False,
    )

    daily.to_csv(
        OUTDIR
        / "historical_holdout_daily_pnl.csv"
    )

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    cis = {}

    for block in (1, 3, 7):
        boot = (
            moving_block_bootstrap_mean(
                daily[
                    "delta_pnl"
                ].to_numpy(),
                block,
                BOOTSTRAP_REPS,
                rng,
            )
        )

        cis[block] = (
            np.quantile(
                boot,
                .025,
            ),
            np.quantile(
                boot,
                .975,
            ),
        )

    # --------------------------------------------------
    # City-level holdout PnL
    # --------------------------------------------------

    city = (
        hold.groupby(
            [
                "model",
                "city",
            ]
        )
        .agg(
            trades=(
                "trade",
                "sum",
            ),
            total_pnl=(
                "realized_pnl",
                "sum",
            ),
            mean_pnl=(
                "realized_pnl",
                "mean",
            ),
        )
    )

    # --------------------------------------------------
    # Print
    # --------------------------------------------------

    print(
        "\nCORRECTED HISTORICAL ECONOMIC EVALUATION"
    )

    print("=" * 76)

    for segment in [
        "rolling_development",
        "historical_holdout",
    ]:
        print(
            f"\n{segment}:"
        )

        s = summary[
            summary["segment"]
            == segment
        ]

        for _, r in (
            s.sort_values("model")
            .iterrows()
        ):
            print(
                f"  {r['model']}: "
                f"trades={int(r['trades'])}/{int(r['city_days'])} | "
                f"total PnL=${r['total_pnl']:+.2f} | "
                f"PnL/city-day=${r['mean_pnl_per_city_day']:+.4f} | "
                f"PnL/trade=${r['mean_pnl_per_trade']:+.4f} | "
                f"win={r['win_rate']:.3f} | "
                f"estimated edge={r['mean_estimated_edge']:.4f}"
            )

    print(
        "\nPRIMARY HISTORICAL-HOLDOUT "
        "M2 - M0 PnL"
    )

    print(
        "  Mean city-day delta: "
        f"${paired['delta_pnl'].mean():+.4f}"
    )

    print(
        "  Total M0 PnL:       "
        f"${paired['m0_pnl'].sum():+.2f}"
    )

    print(
        "  Total M2 PnL:       "
        f"${paired['m2_pnl'].sum():+.2f}"
    )

    print(
        "  Total delta:        "
        f"${paired['delta_pnl'].sum():+.2f}"
    )

    print(
        "\n3-day block-bootstrap "
        "95% CI for mean city-day delta:"
    )

    print(
        f"  [{cis[3][0]:+.4f}, "
        f"{cis[3][1]:+.4f}]"
    )

    print(
        "\nSensitivity:"
    )

    print(
        f"  1-day: [{cis[1][0]:+.4f}, "
        f"{cis[1][1]:+.4f}]"
    )

    print(
        f"  7-day: [{cis[7][0]:+.4f}, "
        f"{cis[7][1]:+.4f}]"
    )

    print(
        "\nHoldout PnL by city:"
    )

    print(
        city.round(4).to_string()
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "This is one-contract quote-based "
        "historical tradeability, not proof "
        "of fill or scalable live alpha."
    )


if __name__ == "__main__":
    main()
