from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd


TRADES_PATH = Path(
    "results/historical_economics/"
    "historical_trade_decisions.csv"
)

MASTER_LONG_PATH = Path(
    "data/processed/modeling_master_long.csv"
)

MARKET_PATH = Path(
    "data/processed/market_panel_preclose.csv"
)

OUTDIR = Path(
    "results/historical_economics"
)

MODELS = ("M0", "M2")

CITY_TZ = {
    "NYC": "America/New_York",
    "Chicago": "America/Chicago",
    "Denver": "America/Denver",
}

BOOTSTRAP_REPS = 10_000
RANDOM_SEED = 20260930


def taker_fee(price: float) -> float:
    raw = (
        0.07
        * price
        * (1.0 - price)
    )

    return (
        math.ceil(
            raw * 100.0 - 1e-12
        )
        / 100.0
    )


def stressed_pnl(
    action_true: float,
    baseline_price: float,
    adverse: float,
) -> tuple[float, float, float]:
    price = min(
        1.0,
        baseline_price + adverse,
    )

    fee = taker_fee(price)

    pnl = (
        action_true
        - price
        - fee
    )

    return price, fee, pnl


def target_11am_utc(
    event_date: str,
    city: str,
) -> pd.Timestamp:
    date = datetime.strptime(
        event_date,
        "%Y-%m-%d",
    ).date()

    local = datetime(
        date.year,
        date.month,
        date.day,
        11,
        0,
        tzinfo=ZoneInfo(
            CITY_TZ[city]
        ),
    )

    return pd.Timestamp(
        local
    ).tz_convert("UTC")


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
        chosen = rng.choice(
            starts,
            size=blocks_needed,
            replace=True,
        )

        sample = np.concatenate(
            [
                values[
                    s:s + block_length
                ]
                for s in chosen
            ]
        )[:n]

        out[b] = sample.mean()

    return out


def concentration_summary(
    g: pd.DataFrame,
    pnl_col: str,
):
    pnl = g[pnl_col].dropna()

    positive = (
        pnl[pnl > 0]
        .sort_values(
            ascending=False
        )
    )

    positive_total = (
        positive.sum()
    )

    top1_share = (
        positive.iloc[:1].sum()
        / positive_total
        if positive_total > 0
        else np.nan
    )

    top3_share = (
        positive.iloc[:3].sum()
        / positive_total
        if positive_total > 0
        else np.nan
    )

    daily = (
        g.dropna(
            subset=[pnl_col]
        )
        .groupby(
            "event_date_local"
        )[pnl_col]
        .sum()
    )

    return {
        "positive_pnl":
            positive_total,
        "top1_positive_share":
            top1_share,
        "top3_positive_share":
            top3_share,
        "best_date_pnl":
            (
                daily.max()
                if len(daily)
                else np.nan
            ),
        "worst_date_pnl":
            (
                daily.min()
                if len(daily)
                else np.nan
            ),
    }


def main():
    trades = pd.read_csv(
        TRADES_PATH
    )

    trades = trades[
        trades["model"].isin(
            MODELS
        )
    ].copy()

    master = pd.read_csv(
        MASTER_LONG_PATH
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

    # --------------------------------------------------
    # Map frozen bucket index to exact market ticker
    # --------------------------------------------------

    ticker_map = (
        master[
            [
                "city",
                "event_date_local",
                "event_ticker",
                "bucket_index",
                "market_ticker",
            ]
        ]
        .drop_duplicates()
    )

    trades = trades.merge(
        ticker_map,
        left_on=[
            "city",
            "event_date_local",
            "event_ticker",
            "bucket",
        ],
        right_on=[
            "city",
            "event_date_local",
            "event_ticker",
            "bucket_index",
        ],
        how="left",
        validate="many_to_one",
    )

    # No-trade rows naturally have no bucket/ticker.
    bad_trade_mapping = trades[
        (trades["trade"] == 1)
        & (
            trades[
                "market_ticker"
            ].isna()
        )
    ]

    if len(bad_trade_mapping):
        raise RuntimeError(
            "Selected trades failed "
            "market-ticker mapping."
        )

    # --------------------------------------------------
    # +1c / +2c decision-preserving execution
    # --------------------------------------------------

    for adverse_cents in (
        1,
        2,
    ):
        adverse = (
            adverse_cents
            / 100.0
        )

        prices = []
        fees = []
        pnls = []

        for row in trades.itertuples(
            index=False
        ):
            if int(row.trade) == 0:
                prices.append(0.0)
                fees.append(0.0)
                pnls.append(0.0)
                continue

            price, fee, pnl = (
                stressed_pnl(
                    action_true=float(
                        row.action_true
                    ),
                    baseline_price=float(
                        row.entry_price
                    ),
                    adverse=adverse,
                )
            )

            prices.append(price)
            fees.append(fee)
            pnls.append(pnl)

        trades[
            f"adverse_{adverse_cents}c_price"
        ] = prices

        trades[
            f"adverse_{adverse_cents}c_fee"
        ] = fees

        trades[
            f"pnl_adverse_{adverse_cents}c"
        ] = pnls

    # --------------------------------------------------
    # Exact 11AM local quote lookup
    # --------------------------------------------------

    delay_prices = []
    delay_fees = []
    delay_pnls = []
    delay_available = []

    market_lookup = (
        market[
            [
                "market_ticker",
                "timestamp_utc",
                "yes_bid_close",
                "yes_ask_close",
            ]
        ]
        .drop_duplicates(
            [
                "market_ticker",
                "timestamp_utc",
            ]
        )
    )

    for row in trades.itertuples(
        index=False
    ):
        # No trade remains no trade;
        # no later quote is required.
        if int(row.trade) == 0:
            delay_prices.append(0.0)
            delay_fees.append(0.0)
            delay_pnls.append(0.0)
            delay_available.append(True)
            continue

        target = target_11am_utc(
            row.event_date_local,
            row.city,
        )

        q = market_lookup[
            (
                market_lookup[
                    "market_ticker"
                ]
                == row.market_ticker
            )
            & (
                market_lookup[
                    "timestamp_utc"
                ]
                == target
            )
        ]

        if len(q) != 1:
            delay_prices.append(
                np.nan
            )
            delay_fees.append(
                np.nan
            )
            delay_pnls.append(
                np.nan
            )
            delay_available.append(
                False
            )
            continue

        quote = q.iloc[0]

        if row.side == "YES":
            price = float(
                quote[
                    "yes_ask_close"
                ]
            )

        elif row.side == "NO":
            price = (
                1.0
                - float(
                    quote[
                        "yes_bid_close"
                    ]
                )
            )

        else:
            raise RuntimeError(
                f"Unexpected side: "
                f"{row.side}"
            )

        fee = taker_fee(
            price
        )

        pnl = (
            float(
                row.action_true
            )
            - price
            - fee
        )

        delay_prices.append(
            price
        )

        delay_fees.append(
            fee
        )

        delay_pnls.append(
            pnl
        )

        delay_available.append(
            True
        )

    trades[
        "delay_1h_available"
    ] = delay_available

    trades[
        "delay_1h_price"
    ] = delay_prices

    trades[
        "delay_1h_fee"
    ] = delay_fees

    trades[
        "pnl_delay_1h"
    ] = delay_pnls

    trades.to_csv(
        OUTDIR
        / "historical_execution_stress.csv",
        index=False,
    )

    # --------------------------------------------------
    # Scenario summaries
    # --------------------------------------------------

    scenarios = {
        "baseline":
            "realized_pnl",
        "adverse_1c":
            "pnl_adverse_1c",
        "adverse_2c":
            "pnl_adverse_2c",
        "delay_1h":
            "pnl_delay_1h",
    }

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
        for scenario, pnl_col in (
            scenarios.items()
        ):
            available = g[
                pnl_col
            ].notna()

            ga = g[
                available
            ]

            executed = ga[
                ga["trade"] == 1
            ]

            conc = (
                concentration_summary(
                    ga,
                    pnl_col,
                )
            )

            summary_rows.append(
                {
                    "segment":
                        segment,
                    "model":
                        model,
                    "scenario":
                        scenario,
                    "city_days_available":
                        len(ga),
                    "trades":
                        int(
                            executed[
                                "trade"
                            ].sum()
                        ),
                    "total_pnl":
                        ga[
                            pnl_col
                        ].sum(),
                    "mean_pnl_per_city_day":
                        ga[
                            pnl_col
                        ].mean(),
                    "mean_pnl_per_trade":
                        (
                            executed[
                                pnl_col
                            ].mean()
                            if len(executed)
                            else np.nan
                        ),
                    **conc,
                }
            )

    summary = pd.DataFrame(
        summary_rows
    )

    summary.to_csv(
        OUTDIR
        / "historical_execution_stress_summary.csv",
        index=False,
    )

    # --------------------------------------------------
    # Holdout M2 - M0 comparisons
    # --------------------------------------------------

    hold = trades[
        trades[
            "economic_segment"
        ]
        == "historical_holdout"
    ].copy()

    comparison_rows = []

    rng = np.random.default_rng(
        RANDOM_SEED
    )

    for scenario, pnl_col in (
        scenarios.items()
    ):
        m0 = hold[
            hold["model"]
            == "M0"
        ][
            [
                "city",
                "event_date_local",
                pnl_col,
            ]
        ].rename(
            columns={
                pnl_col:
                    "m0_pnl"
            }
        )

        m2 = hold[
            hold["model"]
            == "M2"
        ][
            [
                "city",
                "event_date_local",
                pnl_col,
            ]
        ].rename(
            columns={
                pnl_col:
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

        paired = paired.dropna(
            subset=[
                "m0_pnl",
                "m2_pnl",
            ]
        )

        paired[
            "delta_pnl"
        ] = (
            paired["m2_pnl"]
            - paired["m0_pnl"]
        )

        daily = (
            paired
            .groupby(
                "event_date_local"
            )
            .agg(
                delta_pnl=(
                    "delta_pnl",
                    "mean",
                )
            )
            .sort_index()
        )

        cis = {}

        for block in (
            1,
            3,
            7,
        ):
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
                float(
                    np.quantile(
                        boot,
                        .025,
                    )
                ),
                float(
                    np.quantile(
                        boot,
                        .975,
                    )
                ),
            )

        comparison_rows.append(
            {
                "scenario":
                    scenario,
                "paired_city_days":
                    len(paired),
                "paired_dates":
                    len(daily),
                "m0_total_pnl":
                    paired[
                        "m0_pnl"
                    ].sum(),
                "m2_total_pnl":
                    paired[
                        "m2_pnl"
                    ].sum(),
                "total_delta":
                    paired[
                        "delta_pnl"
                    ].sum(),
                "mean_city_day_delta":
                    paired[
                        "delta_pnl"
                    ].mean(),
                "ci3_low":
                    cis[3][0],
                "ci3_high":
                    cis[3][1],
                "ci1_low":
                    cis[1][0],
                "ci1_high":
                    cis[1][1],
                "ci7_low":
                    cis[7][0],
                "ci7_high":
                    cis[7][1],
            }
        )

    comparisons = pd.DataFrame(
        comparison_rows
    )

    comparisons.to_csv(
        OUTDIR
        / "historical_execution_stress_m2_vs_m0.csv",
        index=False,
    )

    # --------------------------------------------------
    # Console report
    # --------------------------------------------------

    print(
        "\nHISTORICAL EXECUTION STRESS TEST"
    )
    print("=" * 80)

    for segment in (
        "rolling_development",
        "historical_holdout",
    ):
        print(
            f"\n{segment}:"
        )

        ss = summary[
            summary["segment"]
            == segment
        ]

        for scenario in scenarios:
            print(
                f"\n  {scenario}:"
            )

            for model in MODELS:
                r = ss[
                    (
                        ss["scenario"]
                        == scenario
                    )
                    & (
                        ss["model"]
                        == model
                    )
                ].iloc[0]

                print(
                    f"    {model}: "
                    f"available={int(r['city_days_available'])} | "
                    f"trades={int(r['trades'])} | "
                    f"PnL=${r['total_pnl']:+.2f} | "
                    f"PnL/trade=${r['mean_pnl_per_trade']:+.4f}"
                )

    print(
        "\nPRIMARY HOLDOUT ROBUSTNESS:"
    )

    for _, r in (
        comparisons.iterrows()
    ):
        print(
            f"  {r['scenario']}: "
            f"M0=${r['m0_total_pnl']:+.2f} | "
            f"M2=${r['m2_total_pnl']:+.2f} | "
            f"delta=${r['total_delta']:+.2f} | "
            f"mean delta=${r['mean_city_day_delta']:+.4f} | "
            f"3d CI=[{r['ci3_low']:+.4f}, {r['ci3_high']:+.4f}] | "
            f"n={int(r['paired_city_days'])}"
        )

    print(
        "\nHOLDOUT PROFIT CONCENTRATION:"
    )

    hs = summary[
        summary["segment"]
        == "historical_holdout"
    ]

    for model in MODELS:
        r = hs[
            (
                hs["model"]
                == model
            )
            & (
                hs["scenario"]
                == "baseline"
            )
        ].iloc[0]

        print(
            f"  {model}: "
            f"positive PnL=${r['positive_pnl']:.2f} | "
            f"top1 share={r['top1_positive_share']:.3f} | "
            f"top3 share={r['top3_positive_share']:.3f} | "
            f"best date=${r['best_date_pnl']:+.2f} | "
            f"worst date=${r['worst_date_pnl']:+.2f}"
        )

    delay_missing = int(
        (
            (trades["trade"] == 1)
            & (
                ~trades[
                    "delay_1h_available"
                ]
            )
        ).sum()
    )

    print(
        "\n1-hour delay selected-trade "
        f"quote failures: {delay_missing}"
    )

    print(
        "\nNo model or trade rule was "
        "retuned for these stress tests."
    )


if __name__ == "__main__":
    main()
