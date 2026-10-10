from __future__ import annotations

from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd


INPUT = Path(
    "data/processed/modeling_master_event.csv"
)

OUTPUT = Path(
    "data/processed/model_features_event.csv"
)

AUDIT = Path(
    "results/development/model_feature_audit.txt"
)

PROB_FLOOR = 1e-6

NORM = NormalDist()


def normal_cdf(x: float) -> float:
    if x == np.inf:
        return 1.0

    if x == -np.inf:
        return 0.0

    return NORM.cdf(x)


def bucket_mass(
    mu: float,
    sigma: float,
    lower_integer: float | None,
    upper_integer: float | None,
) -> float:
    """
    Weather proxy only.

    Integer settlement bucket:
      <= U       -> (-inf, U + 0.5)
      L ... U    -> [L - 0.5, U + 0.5)
      >= L       -> [L - 0.5, +inf)
    """

    if sigma <= 0:
        raise ValueError(
            f"XND must be positive, got {sigma}"
        )

    if (
        lower_integer is None
        or pd.isna(lower_integer)
    ):
        lower_cut = -np.inf
    else:
        lower_cut = (
            float(lower_integer) - 0.5
        )

    if (
        upper_integer is None
        or pd.isna(upper_integer)
    ):
        upper_cut = np.inf
    else:
        upper_cut = (
            float(upper_integer) + 0.5
        )

    lower_z = (
        -np.inf
        if lower_cut == -np.inf
        else (lower_cut - mu) / sigma
    )

    upper_z = (
        np.inf
        if upper_cut == np.inf
        else (upper_cut - mu) / sigma
    )

    mass = (
        normal_cdf(upper_z)
        - normal_cdf(lower_z)
    )

    return max(
        float(mass),
        0.0,
    )


def main():
    df = pd.read_csv(INPUT)

    weather_matrix = np.zeros(
        (len(df), 6),
        dtype=float,
    )

    market_matrix = np.zeros(
        (len(df), 6),
        dtype=float,
    )

    for row_i, row in df.iterrows():
        mu = float(row["txn"])
        sigma = float(row["xnd"])

        q = []

        for k in range(1, 7):
            lower = row[
                f"bucket_{k}_lower_f"
            ]

            upper = row[
                f"bucket_{k}_upper_f"
            ]

            mass = bucket_mass(
                mu=mu,
                sigma=sigma,
                lower_integer=lower,
                upper_integer=upper,
            )

            q.append(mass)

            market_matrix[
                row_i,
                k - 1,
            ] = float(
                row[
                    f"bucket_{k}_market_prob"
                ]
            )

        q = np.asarray(
            q,
            dtype=float,
        )

        if q.sum() <= 0:
            raise RuntimeError(
                "Weather proxy probabilities "
                f"sum to zero for row {row_i}"
            )

        q = q / q.sum()

        weather_matrix[
            row_i,
            :
        ] = q

    # --------------------------------------------------
    # Log-transform floors
    # --------------------------------------------------

    weather_for_log = np.clip(
        weather_matrix,
        PROB_FLOOR,
        None,
    )

    weather_for_log = (
        weather_for_log
        / weather_for_log.sum(
            axis=1,
            keepdims=True,
        )
    )

    market_for_log = np.clip(
        market_matrix,
        PROB_FLOOR,
        None,
    )

    market_for_log = (
        market_for_log
        / market_for_log.sum(
            axis=1,
            keepdims=True,
        )
    )

    # --------------------------------------------------
    # Attach features
    # --------------------------------------------------

    for k in range(1, 7):
        df[
            f"bucket_{k}_weather_proxy_prob"
        ] = weather_matrix[
            :,
            k - 1,
        ]

        df[
            f"bucket_{k}_log_weather_proxy"
        ] = np.log(
            weather_for_log[
                :,
                k - 1,
            ]
        )

        df[
            f"bucket_{k}_log_market_prob"
        ] = np.log(
            market_for_log[
                :,
                k - 1,
            ]
        )

    # --------------------------------------------------
    # QC
    # --------------------------------------------------

    weather_sum = (
        weather_matrix.sum(axis=1)
    )

    market_sum = (
        market_matrix.sum(axis=1)
    )

    finite_weather_logs = np.isfinite(
        np.log(weather_for_log)
    ).all()

    finite_market_logs = np.isfinite(
        np.log(market_for_log)
    ).all()

    dev = df[
        df["historical_split"]
        == "development"
    ]

    holdout = df[
        df["historical_split"]
        == "historical_holdout"
    ]

    problems = []

    if len(df) != 138:
        problems.append(
            f"Expected 138 rows; found {len(df)}"
        )

    if len(dev) != 93:
        problems.append(
            f"Expected 93 development rows; "
            f"found {len(dev)}"
        )

    if len(holdout) != 45:
        problems.append(
            f"Expected 45 holdout rows; "
            f"found {len(holdout)}"
        )

    if not np.allclose(
        weather_sum,
        1.0,
        atol=1e-12,
    ):
        problems.append(
            "Weather proxy does not sum to one."
        )

    if not np.allclose(
        market_sum,
        1.0,
        atol=1e-10,
    ):
        problems.append(
            "Market probabilities do not sum "
            "to one."
        )

    if not finite_weather_logs:
        problems.append(
            "Non-finite weather log features."
        )

    if not finite_market_logs:
        problems.append(
            "Non-finite market log features."
        )

    if np.any(
        weather_matrix < 0
    ):
        problems.append(
            "Negative weather proxy probability."
        )

    # Do NOT evaluate against outcomes here.
    # This script is feature construction only.

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    AUDIT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT,
        index=False,
    )

    weather_max = (
        weather_matrix.max(axis=1)
    )

    lines = [
        "Model feature construction QC",
        "=" * 64,
        f"Rows:                             {len(df)}",
        f"Development city-days:            {len(dev)}",
        f"Historical holdout city-days:     {len(holdout)}",
        f"Weather-proxy sum failures:       "
        f"{int((~np.isclose(weather_sum, 1)).sum())}",
        f"Market-probability sum failures:  "
        f"{int((~np.isclose(market_sum, 1)).sum())}",
        f"Finite weather log features:      {finite_weather_logs}",
        f"Finite market log features:       {finite_market_logs}",
        "",
        "Weather proxy concentration (descriptive only):",
        f"  max-bucket probability q05:     "
        f"{np.quantile(weather_max, .05):.4f}",
        f"  max-bucket probability median:  "
        f"{np.quantile(weather_max, .50):.4f}",
        f"  max-bucket probability q95:     "
        f"{np.quantile(weather_max, .95):.4f}",
        "",
        "No outcome-based weather performance was computed.",
        "",
        "FINAL FEATURE STATUS: "
        + (
            "PASS"
            if not problems
            else "FAIL"
        ),
    ]

    if problems:
        lines.append("")
        lines.append("Problems:")

        for p in problems:
            lines.append(
                f"- {p}"
            )

    AUDIT.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        "\n" + "\n".join(lines)
    )


if __name__ == "__main__":
    main()
