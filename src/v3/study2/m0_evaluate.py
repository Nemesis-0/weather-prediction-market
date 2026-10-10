"""One-shot historical validation for frozen V3 Study 2 M0.

The evaluator loads the already-fitted 2024/2025 frozen M0 artifacts and opens
2026 historical-validation outcomes only after it has written an evaluation
lock containing the hashes of those frozen artifacts.

No model fitting, calibration update, model selection, economics, or orders are
performed here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from src.v3.study2.m0 import (
    BASE_FEATURES,
    M0_PROTOCOL_ID,
    M0_VERSION,
    MIN_SCALE_F,
    feature_vector,
    weighted_quantile,
)

EVAL_PROTOCOL_ID = "v3_study2_m0_historical_validation_frozen_2026-10-07_r1"
BOOTSTRAP_SEED = 20261007
BOOTSTRAP_REPS = 2000
INTERVAL_LEVELS = (0.50, 0.80, 0.90)


class M0EvaluationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise M0EvaluationError(f"expected JSON object: {path}")
    return obj


def _normalize_weights(w: np.ndarray) -> np.ndarray:
    total = float(w.sum())
    if total <= 0:
        raise M0EvaluationError("nonpositive weights")
    return w / total


def _load_calibration_ecdf(path: Path) -> tuple[np.ndarray, np.ndarray]:
    z: list[float] = []
    w: list[float] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if set(reader.fieldnames or []) != {
            "standardized_residual_z",
            "date_balanced_probability_weight",
        }:
            raise M0EvaluationError("unexpected calibration ECDF schema")
        for row in reader:
            z.append(float(row["standardized_residual_z"]))
            w.append(float(row["date_balanced_probability_weight"]))
    if not z:
        raise M0EvaluationError("empty calibration ECDF")
    za = np.asarray(z, dtype=float)
    wa = _normalize_weights(np.asarray(w, dtype=float))
    order = np.argsort(za, kind="mergesort")
    za = za[order]
    wa = wa[order]
    if np.any(~np.isfinite(za)) or np.any(~np.isfinite(wa)):
        raise M0EvaluationError("nonfinite calibration ECDF")
    return za, wa


def _ecdf_precompute(z: np.ndarray, w: np.ndarray) -> dict[str, Any]:
    cw = np.cumsum(w)
    cwz = np.cumsum(w * z)

    # E|Z-Z'| = 2 * sum_j w_j * (z_j*W_prev - S_prev)
    prev_w = np.concatenate(([0.0], cw[:-1]))
    prev_wz = np.concatenate(([0.0], cwz[:-1]))
    pair_abs = 2.0 * float(np.sum(w * (z * prev_w - prev_wz)))

    return {
        "z": z,
        "w": w,
        "cw": cw,
        "cwz": cwz,
        "pair_abs": pair_abs,
        "weighted_mean": float(np.sum(w * z)),
        "weighted_var": float(np.sum(w * (z - np.sum(w * z)) ** 2)),
    }


def _expected_abs_to_a(pre: dict[str, Any], a: float) -> float:
    z = pre["z"]
    cw = pre["cw"]
    cwz = pre["cwz"]

    idx = int(np.searchsorted(z, a, side="right"))
    if idx == 0:
        left_w = 0.0
        left_s = 0.0
    else:
        left_w = float(cw[idx - 1])
        left_s = float(cwz[idx - 1])

    total_w = float(cw[-1])
    total_s = float(cwz[-1])
    right_w = total_w - left_w
    right_s = total_s - left_s

    return a * left_w - left_s + right_s - a * right_w


def _cdf_at(pre: dict[str, Any], a: float) -> float:
    z = pre["z"]
    cw = pre["cw"]
    idx = int(np.searchsorted(z, a, side="right"))
    if idx == 0:
        return 0.0
    return float(cw[idx - 1])


def _crps_location_scale(
    *,
    y: float,
    mu: float,
    scale: float,
    pre: dict[str, Any],
) -> float:
    a = (y - mu) / scale
    first = _expected_abs_to_a(pre, a)
    crps = scale * (first - 0.5 * pre["pair_abs"])
    if crps < -1e-9:
        raise M0EvaluationError(f"negative CRPS {crps}")
    return max(0.0, float(crps))


def _date_balanced_row_weights(dates: list[str]) -> np.ndarray:
    counts: dict[str, int] = {}
    for d in dates:
        counts[d] = counts.get(d, 0) + 1
    if not counts:
        raise M0EvaluationError("empty evaluation subset")
    return np.asarray([1.0 / counts[d] for d in dates], dtype=float)


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.average(values, weights=weights))


def _weighted_quantile_general(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    return weighted_quantile(values, _normalize_weights(weights), q)


def _block_name(local_minute: int) -> str:
    hour = local_minute // 60
    if 0 <= hour < 6:
        return "00-06"
    if 6 <= hour < 12:
        return "06-12"
    if 12 <= hour < 18:
        return "12-18"
    if 18 <= hour < 24:
        return "18-24"
    raise M0EvaluationError(f"bad local minute {local_minute}")


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise M0EvaluationError("empty metric subset")
    dates = [r["event_date"] for r in rows]
    w = _date_balanced_row_weights(dates)

    crps = np.asarray([r["crps"] for r in rows], dtype=float)
    ae = np.asarray([r["median_abs_error"] for r in rows], dtype=float)
    pit = np.asarray([r["pit"] for r in rows], dtype=float)

    out: dict[str, Any] = {
        "date_count": len(set(dates)),
        "state_count": len(rows),
        "date_balanced_mean_crps": _weighted_mean(crps, w),
        "date_balanced_median_prediction_mae": _weighted_mean(ae, w),
        "pit_weighted_mean": _weighted_mean(pit, w),
        "pit_weighted_variance": _weighted_mean(
            (pit - _weighted_mean(pit, w)) ** 2, w
        ),
    }

    # Weighted KS distance of PIT from Uniform(0,1).
    order = np.argsort(pit, kind="mergesort")
    ps = pit[order]
    ws = _normalize_weights(w[order])
    cw = np.cumsum(ws)
    ks_upper = np.max(np.abs(cw - ps))
    cw_prev = np.concatenate(([0.0], cw[:-1]))
    ks_lower = np.max(np.abs(cw_prev - ps))
    out["pit_weighted_ks_distance_from_uniform"] = float(max(ks_upper, ks_lower))

    bins = []
    for i in range(10):
        lo, hi = i / 10.0, (i + 1) / 10.0
        if i < 9:
            mask = (pit >= lo) & (pit < hi)
        else:
            mask = (pit >= lo) & (pit <= hi)
        bins.append(float(w[mask].sum() / w.sum()))
    out["pit_decile_weight_mass"] = bins

    for level in INTERVAL_LEVELS:
        key = str(int(level * 100))
        covered = np.asarray([r[f"covered_{key}"] for r in rows], dtype=float)
        width = np.asarray([r[f"width_{key}"] for r in rows], dtype=float)
        out[f"coverage_{key}"] = _weighted_mean(covered, w)
        out[f"mean_width_{key}_f"] = _weighted_mean(width, w)

    return out


def _per_date_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[r["event_date"]].append(r)

    out: dict[str, dict[str, float]] = {}
    for d, rr in grouped.items():
        vals: dict[str, float] = {
            "crps": float(np.mean([x["crps"] for x in rr])),
            "mae": float(np.mean([x["median_abs_error"] for x in rr])),
        }
        for level in INTERVAL_LEVELS:
            key = str(int(level * 100))
            vals[f"coverage_{key}"] = float(np.mean([x[f"covered_{key}"] for x in rr]))
            vals[f"width_{key}"] = float(np.mean([x[f"width_{key}"] for x in rr]))
        out[d] = vals
    return out


def _bootstrap_date_means(
    per_date: dict[str, dict[str, float]],
    *,
    reps: int = BOOTSTRAP_REPS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    dates = sorted(per_date)
    if len(dates) != 279:
        raise M0EvaluationError(f"expected 279 validation dates, got {len(dates)}")
    metric_names = sorted(next(iter(per_date.values())))
    matrix = np.asarray(
        [[per_date[d][m] for m in metric_names] for d in dates],
        dtype=float,
    )
    rng = np.random.default_rng(seed)
    boot = np.empty((reps, len(metric_names)), dtype=float)
    n = len(dates)
    for i in range(reps):
        idx = rng.integers(0, n, size=n)
        boot[i] = matrix[idx].mean(axis=0)

    result: dict[str, Any] = {
        "bootstrap_reps": reps,
        "bootstrap_seed": seed,
        "cluster_unit": "event_date",
        "date_count": n,
        "metrics": {},
    }
    for j, m in enumerate(metric_names):
        result["metrics"][m] = {
            "point_estimate_date_mean": float(matrix[:, j].mean()),
            "ci95_percentile": [
                float(np.quantile(boot[:, j], 0.025)),
                float(np.quantile(boot[:, j], 0.975)),
            ],
        }
    return result


def _validate_model_artifacts(model: dict[str, Any], pre: dict[str, Any]) -> None:
    if model.get("protocol_id") != M0_PROTOCOL_ID:
        raise M0EvaluationError("unexpected M0 protocol")
    if model.get("m0_version") != M0_VERSION:
        raise M0EvaluationError("unexpected M0 version")
    if model.get("validation_used") is not False:
        raise M0EvaluationError("pre-eval artifact says validation was used")
    if model.get("hyperparameter_tuning_performed") is not False:
        raise M0EvaluationError("unexpected hyperparameter tuning flag")
    if pre.get("historical_validation_target_values_used") != 0:
        raise M0EvaluationError("validation targets already used")
    if pre.get("historical_validation_feature_values_used") != 0:
        raise M0EvaluationError("validation features already used")
    if pre.get("train_dates") != 366 or pre.get("calibration_dates") != 365:
        raise M0EvaluationError("unexpected train/calibration date counts")


def _model_arrays(model: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = np.asarray([model["feature_mean"][x] for x in BASE_FEATURES], dtype=float)
    std = np.asarray([model["feature_std"][x] for x in BASE_FEATURES], dtype=float)
    beta_mu = np.asarray(
        [model["location_intercept"]]
        + [model["location_coefficients_standardized"][x] for x in BASE_FEATURES],
        dtype=float,
    )
    beta_ls = np.asarray(
        [model["log_scale_intercept"]]
        + [model["log_scale_coefficients_standardized"][x] for x in BASE_FEATURES],
        dtype=float,
    )
    return mean, std, beta_mu, beta_ls


def evaluate_once(
    *,
    source_csv: Path,
    pre_eval_dir: Path,
    output_dir: Path,
    canonical_head: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise M0EvaluationError(f"output_dir already exists; refusing overwrite: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    model_path = pre_eval_dir / "m0_model.json"
    z_path = pre_eval_dir / "calibration_standardized_residuals.csv"
    pre_path = pre_eval_dir / "pre_eval_summary.json"
    for p in (model_path, z_path, pre_path, source_csv):
        if not p.is_file():
            raise M0EvaluationError(f"missing required artifact: {p}")

    model = _read_json(model_path)
    pre_summary = _read_json(pre_path)
    _validate_model_artifacts(model, pre_summary)

    source_sha = sha256_file(source_csv)
    if source_sha != pre_summary.get("source_model_ready_csv_sha256"):
        raise M0EvaluationError("model-ready CSV hash differs from pre-eval fit source")

    frozen_hashes = {
        "m0_model.json": sha256_file(model_path),
        "calibration_standardized_residuals.csv": sha256_file(z_path),
        "pre_eval_summary.json": sha256_file(pre_path),
        "model_ready_states.csv": source_sha,
    }

    # This lock is written BEFORE any historical-validation numeric feature/target
    # value is parsed below.
    lock = {
        "evaluation_protocol_id": EVAL_PROTOCOL_ID,
        "canonical_head": canonical_head,
        "frozen_m0_protocol_id": M0_PROTOCOL_ID,
        "frozen_m0_version": M0_VERSION,
        "frozen_input_sha256": frozen_hashes,
        "primary_metric": "date_balanced_mean_CRPS",
        "secondary_metrics": [
            "date_balanced predictive-median MAE",
            "50/80/90 central interval coverage and width",
            "weighted PIT mean/variance/KS/decile mass",
            "same descriptive metrics by local 6-hour block",
        ],
        "bootstrap": {
            "cluster_unit": "event_date",
            "reps": BOOTSTRAP_REPS,
            "seed": BOOTSTRAP_SEED,
            "ci": "percentile_95",
        },
        "guardrail": "MODEL_FROZEN_BEFORE_2026_NUMERIC_PARSE_NO_ECONOMICS_NO_ORDERS",
    }
    (output_dir / "evaluation_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    z, zw = _load_calibration_ecdf(z_path)
    ecdf = _ecdf_precompute(z, zw)

    quantile_probs = {0.50}
    for level in INTERVAL_LEVELS:
        alpha = (1.0 - level) / 2.0
        quantile_probs.add(alpha)
        quantile_probs.add(1.0 - alpha)
    zq = {q: weighted_quantile(z, zw, q) for q in sorted(quantile_probs)}

    mean, std, beta_mu, beta_ls = _model_arrays(model)

    predictions: list[dict[str, Any]] = []
    raw_validation_rows = 0
    unavailable_validation_rows = 0

    with source_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["split"] != "historical_validation":
                continue
            raw_validation_rows += 1

            if row["state_available"] != "True":
                unavailable_validation_rows += 1
                continue

            x = np.asarray(feature_vector(row), dtype=float)
            xs = (x - mean) / std
            mu = float(beta_mu[0] + xs @ beta_mu[1:])
            log_scale = float(beta_ls[0] + xs @ beta_ls[1:])
            scale = max(MIN_SCALE_F, math.exp(log_scale))
            y = float(row["target_residual_f"])
            zy = (y - mu) / scale

            median = mu + scale * zq[0.50]
            rec: dict[str, Any] = {
                "event_date": row["event_date"],
                "decision_utc": row["decision_utc"],
                "decision_local": row["decision_local"],
                "local_minute_of_day": int(row["local_minute_of_day"]),
                "local_time_block": _block_name(int(row["local_minute_of_day"])),
                "target_residual_f": y,
                "mu_f": mu,
                "scale_f": scale,
                "predictive_median_f": median,
                "median_abs_error": abs(y - median),
                "pit": _cdf_at(ecdf, zy),
                "crps": _crps_location_scale(y=y, mu=mu, scale=scale, pre=ecdf),
            }

            for level in INTERVAL_LEVELS:
                key = str(int(level * 100))
                alpha = (1.0 - level) / 2.0
                lo = mu + scale * zq[alpha]
                hi = mu + scale * zq[1.0 - alpha]
                rec[f"lower_{key}_f"] = lo
                rec[f"upper_{key}_f"] = hi
                rec[f"covered_{key}"] = 1.0 if lo <= y <= hi else 0.0
                rec[f"width_{key}"] = hi - lo

            predictions.append(rec)

    if raw_validation_rows != 13390:
        raise M0EvaluationError(
            f"expected 13390 total historical-validation states, got {raw_validation_rows}"
        )
    if unavailable_validation_rows != 526:
        raise M0EvaluationError(
            f"expected 526 unavailable historical-validation states, got {unavailable_validation_rows}"
        )
    if len(predictions) != 12864:
        raise M0EvaluationError(
            f"expected 12864 available validation states, got {len(predictions)}"
        )
    if len({r["event_date"] for r in predictions}) != 279:
        raise M0EvaluationError("expected 279 validation dates")

    overall = _metric_summary(predictions)
    by_block: dict[str, Any] = {}
    for block in ("00-06", "06-12", "12-18", "18-24"):
        by_block[block] = _metric_summary(
            [r for r in predictions if r["local_time_block"] == block]
        )

    per_date = _per_date_metrics(predictions)
    bootstrap = _bootstrap_date_means(per_date)

    pred_path = output_dir / "validation_predictions.csv"
    pred_fields = list(predictions[0].keys())
    with pred_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=pred_fields)
        writer.writeheader()
        writer.writerows(predictions)

    date_path = output_dir / "validation_date_metrics.csv"
    metric_names = sorted(next(iter(per_date.values())))
    with date_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_date"] + metric_names)
        for d in sorted(per_date):
            writer.writerow([d] + [per_date[d][m] for m in metric_names])

    summary = {
        "evaluation_protocol_id": EVAL_PROTOCOL_ID,
        "canonical_head": canonical_head,
        "frozen_m0_protocol_id": M0_PROTOCOL_ID,
        "frozen_m0_version": M0_VERSION,
        "frozen_input_sha256": frozen_hashes,
        "validation_period": ["2026-01-01", "2026-10-06"],
        "validation_date_count": 279,
        "validation_total_grid_states": raw_validation_rows,
        "validation_unavailable_states_excluded": unavailable_validation_rows,
        "validation_available_states_evaluated": len(predictions),
        "primary_metric": {
            "name": "date_balanced_mean_CRPS",
            "value": overall["date_balanced_mean_crps"],
            "ci95_date_cluster_bootstrap": bootstrap["metrics"]["crps"]["ci95_percentile"],
        },
        "secondary_overall": overall,
        "by_local_time_block": by_block,
        "date_cluster_bootstrap": bootstrap,
        "calibration_ecdf": {
            "row_count": int(len(z)),
            "weighted_z_mean": ecdf["weighted_mean"],
            "weighted_z_variance": ecdf["weighted_var"],
            "weighted_pairwise_abs_difference": ecdf["pair_abs"],
            "frozen_z_quantiles": {str(q): zq[q] for q in sorted(zq)},
        },
        "accepted_historical_limitations": [
            "METAR DDHHMMZ is a historical availability proxy; original publication/receive latency is not reconstructed and COR availability is not proven PIT",
            "historical WU page retrieval does not reconstruct original ForecastEx settlement-time page vintage",
            "temp_change_60m_f is an as-of-state difference, not an exact 60-minute temperature rate",
            "independent unit is event_date; repeated intraday states are dependent",
            "historical validation ends 2026-10-06",
        ],
        "guardrail": "ONE_SHOT_HISTORICAL_VALIDATION_ONLY_NO_RETUNING_NO_ECONOMICS_NO_ORDERS",
        "next_boundary": "interpret frozen M0 validation without retuning; then perform support/calibration review before economic kill test",
    }
    (output_dir / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
