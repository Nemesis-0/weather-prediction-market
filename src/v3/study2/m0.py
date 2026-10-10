"""Frozen simple M0 for V3 Study 2.

M0 is a single observation-only conditional residual distribution:

    R_D,t = M_D^WU - m_D,t^ASOS
    R | x = mu(x) + sigma(x) * Z

mu(x) is a weighted ridge location regression fitted on 2024 only.
sigma(x) is a weighted ridge log-absolute-residual regression fitted on 2024 only.
Z is a date-balanced weighted empirical standardized-residual distribution
constructed from 2025 calibration only.

No 2026 target or feature value is parsed for fitting, calibration, model
selection, or diagnostics in the pre-evaluation fit path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

M0_PROTOCOL_ID = "v3_study2_m0_frozen_2026-10-07_r1"
M0_VERSION = "v3_s2_m0_location_scale_ridge_ecdf_1"
RIDGE_ALPHA_LOCATION = 10.0
RIDGE_ALPHA_LOG_SCALE = 10.0
LOG_SCALE_OFFSET_F = 0.5
MIN_SCALE_F = 0.25

BASE_FEATURES = [
    "sin_local_time",
    "cos_local_time",
    "sin_day_of_year",
    "cos_day_of_year",
    "running_max_f",
    "temp_minus_running_max_f",
    "observation_age_minutes",
    "temp_change_60m_f_filled",
    "temp_change_60m_missing",
]


class M0Error(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _weighted_mean_std(x: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    wsum = float(w.sum())
    if wsum <= 0:
        raise M0Error("nonpositive total weight")
    mean = (x * w[:, None]).sum(axis=0) / wsum
    var = (((x - mean) ** 2) * w[:, None]).sum(axis=0) / wsum
    std = np.sqrt(np.maximum(var, 0.0))
    if np.any(std <= 1e-12):
        bad = [BASE_FEATURES[i] for i, s in enumerate(std) if s <= 1e-12]
        raise M0Error(f"zero/near-zero feature std: {bad}")
    return mean, std


def _fit_weighted_ridge(
    x_std: np.ndarray,
    y: np.ndarray,
    w: np.ndarray,
    alpha: float,
) -> np.ndarray:
    n = x_std.shape[0]
    design = np.column_stack([np.ones(n), x_std])
    sw = np.sqrt(w)
    xw = design * sw[:, None]
    yw = y * sw
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    lhs = xw.T @ xw + penalty
    rhs = xw.T @ yw
    try:
        beta = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError as exc:
        raise M0Error("ridge solve failed") from exc
    return beta


def _predict(beta: np.ndarray, x_std: np.ndarray) -> np.ndarray:
    return beta[0] + x_std @ beta[1:]


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    if not 0.0 <= q <= 1.0:
        raise ValueError(q)
    order = np.argsort(values, kind="mergesort")
    v = values[order]
    w = weights[order]
    c = np.cumsum(w)
    cutoff = q * float(w.sum())
    idx = int(np.searchsorted(c, cutoff, side="left"))
    return float(v[min(idx, len(v) - 1)])


def _day_of_year_fraction(d: date) -> float:
    year_len = 366 if date(d.year, 12, 31).timetuple().tm_yday == 366 else 365
    return (d.timetuple().tm_yday - 1) / year_len


def feature_vector(row: dict[str, str]) -> list[float]:
    minute = float(row["local_minute_of_day"])
    theta_t = 2.0 * math.pi * minute / 1440.0

    d = date.fromisoformat(row["event_date"])
    theta_d = 2.0 * math.pi * _day_of_year_fraction(d)

    temp_change_raw = row.get("temp_change_60m_f", "")
    temp_change_missing = 1.0 if temp_change_raw in ("", None) else 0.0
    temp_change = 0.0 if temp_change_missing else float(temp_change_raw)

    return [
        math.sin(theta_t),
        math.cos(theta_t),
        math.sin(theta_d),
        math.cos(theta_d),
        float(row["running_max_f"]),
        float(row["temp_minus_running_max_f"]),
        float(row["observation_age_minutes"]),
        temp_change,
        temp_change_missing,
    ]


@dataclass
class PreEvalData:
    train_x: np.ndarray
    train_y: np.ndarray
    train_dates: list[str]
    cal_x: np.ndarray
    cal_y: np.ndarray
    cal_dates: list[str]
    skipped_validation_rows: int
    unavailable_rows_skipped: dict[str, int]
    split_available_rows: dict[str, int]


def load_pre_eval_data(path: Path) -> PreEvalData:
    train_x: list[list[float]] = []
    train_y: list[float] = []
    train_dates: list[str] = []
    cal_x: list[list[float]] = []
    cal_y: list[float] = []
    cal_dates: list[str] = []
    skipped_validation_rows = 0
    unavailable = {"train": 0, "calibration": 0, "historical_validation": 0}
    available = {"train": 0, "calibration": 0, "historical_validation": 0}

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {
            "event_date", "split", "state_available", "local_minute_of_day",
            "running_max_f", "temp_minus_running_max_f",
            "observation_age_minutes", "temp_change_60m_f",
            "target_residual_f",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise M0Error(f"missing columns: {sorted(missing)}")

        for row in reader:
            split = row["split"]
            if split not in available:
                raise M0Error(f"unexpected split {split!r}")

            if row["state_available"] != "True":
                unavailable[split] += 1
                continue

            available[split] += 1

            # Hard pre-evaluation boundary: do not parse validation features or target.
            if split == "historical_validation":
                skipped_validation_rows += 1
                continue

            x = feature_vector(row)
            y = float(row["target_residual_f"])
            d = row["event_date"]

            if split == "train":
                train_x.append(x)
                train_y.append(y)
                train_dates.append(d)
            elif split == "calibration":
                cal_x.append(x)
                cal_y.append(y)
                cal_dates.append(d)

    return PreEvalData(
        train_x=np.asarray(train_x, dtype=float),
        train_y=np.asarray(train_y, dtype=float),
        train_dates=train_dates,
        cal_x=np.asarray(cal_x, dtype=float),
        cal_y=np.asarray(cal_y, dtype=float),
        cal_dates=cal_dates,
        skipped_validation_rows=skipped_validation_rows,
        unavailable_rows_skipped=unavailable,
        split_available_rows=available,
    )


def date_balanced_weights(dates: list[str]) -> np.ndarray:
    counts: dict[str, int] = {}
    for d in dates:
        counts[d] = counts.get(d, 0) + 1
    if not counts:
        raise M0Error("no dates")
    w = np.asarray([1.0 / counts[d] for d in dates], dtype=float)
    return w


def fit_pre_eval(data: PreEvalData) -> dict[str, Any]:
    if data.train_x.shape[0] != 16870:
        raise M0Error(f"unexpected train available row count: {data.train_x.shape[0]}")
    if data.cal_x.shape[0] != 16809:
        raise M0Error(f"unexpected calibration available row count: {data.cal_x.shape[0]}")
    if data.skipped_validation_rows != 12864:
        raise M0Error(
            f"unexpected validation available row count: {data.skipped_validation_rows}"
        )
    if len(set(data.train_dates)) != 366:
        raise M0Error("expected 366 independent train dates")
    if len(set(data.cal_dates)) != 365:
        raise M0Error("expected 365 independent calibration dates")

    train_w = date_balanced_weights(data.train_dates)
    cal_w = date_balanced_weights(data.cal_dates)

    mean, std = _weighted_mean_std(data.train_x, train_w)
    train_xs = (data.train_x - mean) / std
    cal_xs = (data.cal_x - mean) / std

    beta_mu = _fit_weighted_ridge(
        train_xs, data.train_y, train_w, RIDGE_ALPHA_LOCATION
    )
    mu_train = _predict(beta_mu, train_xs)
    train_abs = np.abs(data.train_y - mu_train)
    log_scale_target = np.log(train_abs + LOG_SCALE_OFFSET_F)

    beta_log_scale = _fit_weighted_ridge(
        train_xs, log_scale_target, train_w, RIDGE_ALPHA_LOG_SCALE
    )
    log_scale_train = _predict(beta_log_scale, train_xs)
    scale_train = np.maximum(MIN_SCALE_F, np.exp(log_scale_train))

    mu_cal = _predict(beta_mu, cal_xs)
    log_scale_cal = _predict(beta_log_scale, cal_xs)
    scale_cal = np.maximum(MIN_SCALE_F, np.exp(log_scale_cal))
    z_cal = (data.cal_y - mu_cal) / scale_cal

    # Each calibration date has total weight 1. Normalize to an ECDF probability mass.
    z_weights = cal_w / float(cal_w.sum())

    # Diagnostics are train/calibration only; no validation values are parsed.
    q = {
        str(p): weighted_quantile(z_cal, z_weights, p)
        for p in (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
    }

    return {
        "feature_mean": mean,
        "feature_std": std,
        "beta_location": beta_mu,
        "beta_log_scale": beta_log_scale,
        "calibration_z": z_cal,
        "calibration_weight": z_weights,
        "train_scale": scale_train,
        "calibration_scale": scale_cal,
        "train_location_residual": data.train_y - mu_train,
        "calibration_location_residual": data.cal_y - mu_cal,
        "calibration_z_quantiles": q,
    }


def write_pre_eval_artifacts(
    *,
    output_dir: Path,
    source_csv: Path,
    data: PreEvalData,
    fit: dict[str, Any],
) -> dict[str, Any]:
    if output_dir.exists():
        raise M0Error(f"output_dir already exists; refusing overwrite: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    model = {
        "protocol_id": M0_PROTOCOL_ID,
        "m0_version": M0_VERSION,
        "target": "target_residual_f = M_D^WU - running_max_f",
        "distribution": "R|x = mu(x) + sigma(x) * Z",
        "feature_names": BASE_FEATURES,
        "feature_mean": dict(zip(BASE_FEATURES, map(float, fit["feature_mean"]))),
        "feature_std": dict(zip(BASE_FEATURES, map(float, fit["feature_std"]))),
        "location_intercept": float(fit["beta_location"][0]),
        "location_coefficients_standardized": dict(
            zip(BASE_FEATURES, map(float, fit["beta_location"][1:]))
        ),
        "log_scale_intercept": float(fit["beta_log_scale"][0]),
        "log_scale_coefficients_standardized": dict(
            zip(BASE_FEATURES, map(float, fit["beta_log_scale"][1:]))
        ),
        "ridge_alpha_location": RIDGE_ALPHA_LOCATION,
        "ridge_alpha_log_scale": RIDGE_ALPHA_LOG_SCALE,
        "log_scale_target": f"log(abs(location_residual)+{LOG_SCALE_OFFSET_F})",
        "min_scale_f": MIN_SCALE_F,
        "calibration_distribution": "date-balanced weighted empirical ECDF of 2025 standardized residuals",
        "train_period": ["2024-01-01", "2024-12-31"],
        "calibration_period": ["2025-01-01", "2025-12-31"],
        "historical_validation_period": ["2026-01-01", "2026-10-06"],
        "validation_used": False,
        "market_data_used": False,
        "hyperparameter_tuning_performed": False,
    }
    (output_dir / "m0_model.json").write_text(
        json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    z_path = output_dir / "calibration_standardized_residuals.csv"
    with z_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["standardized_residual_z", "date_balanced_probability_weight"])
        order = np.argsort(fit["calibration_z"], kind="mergesort")
        for i in order:
            w.writerow([
                repr(float(fit["calibration_z"][i])),
                repr(float(fit["calibration_weight"][i])),
            ])

    summary = {
        "protocol_id": M0_PROTOCOL_ID,
        "m0_version": M0_VERSION,
        "source_model_ready_csv": str(source_csv),
        "source_model_ready_csv_sha256": sha256_file(source_csv),
        "train_dates": len(set(data.train_dates)),
        "train_available_states": int(data.train_x.shape[0]),
        "calibration_dates": len(set(data.cal_dates)),
        "calibration_available_states": int(data.cal_x.shape[0]),
        "historical_validation_available_rows_skipped_before_numeric_parse": int(
            data.skipped_validation_rows
        ),
        "historical_validation_target_values_used": 0,
        "historical_validation_feature_values_used": 0,
        "unavailable_rows_skipped": data.unavailable_rows_skipped,
        "split_available_rows_seen": data.split_available_rows,
        "calibration_z_quantiles": fit["calibration_z_quantiles"],
        "train_location_residual_date_balanced_mean": float(
            np.average(
                fit["train_location_residual"],
                weights=date_balanced_weights(data.train_dates),
            )
        ),
        "calibration_location_residual_date_balanced_mean": float(
            np.average(
                fit["calibration_location_residual"],
                weights=date_balanced_weights(data.cal_dates),
            )
        ),
        "train_scale_min": float(np.min(fit["train_scale"])),
        "train_scale_median": float(np.median(fit["train_scale"])),
        "train_scale_max": float(np.max(fit["train_scale"])),
        "calibration_scale_min": float(np.min(fit["calibration_scale"])),
        "calibration_scale_median": float(np.median(fit["calibration_scale"])),
        "calibration_scale_max": float(np.max(fit["calibration_scale"])),
        "guardrail": "PRE_EVAL_ONLY_NO_2026_TARGET_USE_NO_MARKET_NO_ECONOMICS_NO_ORDERS",
        "next_boundary": "freeze/commit M0 implementation and artifacts before one-shot 2026 historical validation",
    }
    (output_dir / "pre_eval_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary
