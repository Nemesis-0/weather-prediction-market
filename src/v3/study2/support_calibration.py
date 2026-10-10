"""Post-validation support/calibration freeze for V3 Study 2.

This layer DOES NOT retune M0. It uses the frozen one-shot 2026 validation only
to construct a conservative probability envelope and explicit support rules for
future prospective economic screening.

No market prices, fees, PnL, candidate selection, or orders are read here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from src.v3.study2.m0 import weighted_quantile

SUPPORT_PROTOCOL_ID = "v3_study2_support_calibration_frozen_2026-10-07_r1"
SUPPORT_VERSION = "v3_s2_support_calibration_1"

BOOTSTRAP_SEED = 20261007
BOOTSTRAP_REPS = 2000
PSEUDO_THRESHOLD_DELTA_MIN_F = -10
PSEUDO_THRESHOLD_DELTA_MAX_F = 20
PSEUDO_THRESHOLD_DELTA_STEP_F = 1
Q_MIN = 0.05
Q_MAX = 0.95
Q_BIN_WIDTH = 0.05
MIN_CALIBRATION_CELL_DATES = 100
MIN_STATE_SUPPORT_CELL_DATES = 45
MAX_OBSERVATION_AGE_MINUTES = 90.0
STATE_QUANTILE_LOW = 0.01
STATE_QUANTILE_HIGH = 0.99

STATE_SUPPORT_FEATURES = [
    "running_max_f",
    "temp_minus_running_max_f",
    "observation_age_minutes",
    "temp_change_60m_f",
]


class SupportCalibrationError(RuntimeError):
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
        raise SupportCalibrationError(f"expected JSON object: {path}")
    return obj


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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
    raise SupportCalibrationError(f"bad local minute {local_minute}")


def _q_bin_label(q: float) -> str | None:
    if q < Q_MIN or q > Q_MAX:
        return None
    # Put exact 0.95 in the final supported bin [0.90,0.95].
    if math.isclose(q, Q_MAX, abs_tol=1e-12):
        lo = Q_MAX - Q_BIN_WIDTH
    else:
        lo = math.floor((q - Q_MIN) / Q_BIN_WIDTH) * Q_BIN_WIDTH + Q_MIN
    lo = round(lo, 10)
    hi = round(lo + Q_BIN_WIDTH, 10)
    return f"{lo:.2f}-{hi:.2f}"


def _load_ecdf(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows = _read_csv(path)
    z = np.asarray([float(r["standardized_residual_z"]) for r in rows], dtype=float)
    w = np.asarray([float(r["date_balanced_probability_weight"]) for r in rows], dtype=float)
    if len(z) == 0:
        raise SupportCalibrationError("empty calibration ECDF")
    order = np.argsort(z, kind="mergesort")
    z = z[order]
    w = w[order]
    w = w / w.sum()
    return z, w


def _survival_probability(z: np.ndarray, w: np.ndarray, cutoff: float) -> float:
    # Strict event M_D^WU > theta, equivalently R > delta.
    # Calibration ECDF is discrete empirical probability mass.
    idx = int(np.searchsorted(z, cutoff, side="right"))
    return float(w[idx:].sum())


def _date_level_cell_means(
    rows: list[tuple[str, float, float]],
) -> dict[str, tuple[float, float, float]]:
    # input: (date, q_hat, y)
    by_date: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for d, q, y in rows:
        by_date[d].append((q, y))
    out: dict[str, tuple[float, float, float]] = {}
    for d, vals in by_date.items():
        q = float(np.mean([x[0] for x in vals]))
        y = float(np.mean([x[1] for x in vals]))
        out[d] = (q, y, y - q)
    return out


def _bootstrap_gap_ci(
    per_date: dict[str, tuple[float, float, float]],
    *,
    seed_offset: int,
) -> tuple[float, float]:
    dates = sorted(per_date)
    gaps = np.asarray([per_date[d][2] for d in dates], dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    n = len(gaps)
    boot = np.empty(BOOTSTRAP_REPS, dtype=float)
    for i in range(BOOTSTRAP_REPS):
        idx = rng.integers(0, n, size=n)
        boot[i] = gaps[idx].mean()
    return float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def build_state_support(
    *,
    model_ready_csv: Path,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], dict[str, Any]] = defaultdict(
        lambda: {"dates": set(), "rows": []}
    )

    with model_ready_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["split"] not in {"train", "calibration"}:
                continue
            if row["state_available"] != "True":
                continue

            d = date.fromisoformat(row["event_date"])
            block = _block_name(int(row["local_minute_of_day"]))
            key = (d.month, block)
            grouped[key]["dates"].add(row["event_date"])
            grouped[key]["rows"].append(row)

    out: list[dict[str, Any]] = []
    for (month, block), item in sorted(grouped.items()):
        rows = item["rows"]
        rec: dict[str, Any] = {
            "month": month,
            "local_time_block": block,
            "independent_date_count": len(item["dates"]),
            "state_count": len(rows),
            "support_cell_pass": len(item["dates"]) >= MIN_STATE_SUPPORT_CELL_DATES,
        }

        for feat in STATE_SUPPORT_FEATURES:
            vals = np.asarray(
                [
                    float(r[feat])
                    for r in rows
                    if r.get(feat) not in ("", None)
                ],
                dtype=float,
            )
            rec[f"{feat}_nonmissing_count"] = int(len(vals))
            if len(vals) == 0:
                rec[f"{feat}_q01"] = None
                rec[f"{feat}_q99"] = None
            else:
                rec[f"{feat}_q01"] = float(np.quantile(vals, STATE_QUANTILE_LOW))
                rec[f"{feat}_q99"] = float(np.quantile(vals, STATE_QUANTILE_HIGH))

        trend_missing_dates = {
            r["event_date"] for r in rows if r.get("temp_change_60m_f") in ("", None)
        }
        rec["temp_change_missing_independent_date_count"] = len(trend_missing_dates)
        out.append(rec)

    expected_cells = 12 * 4
    if len(out) != expected_cells:
        raise SupportCalibrationError(
            f"expected {expected_cells} month x block support cells, got {len(out)}"
        )
    return out


def build_calibration_cells(
    *,
    validation_predictions_csv: Path,
    calibration_ecdf_csv: Path,
) -> list[dict[str, Any]]:
    pred = _read_csv(validation_predictions_csv)
    if len(pred) != 12864:
        raise SupportCalibrationError(f"expected 12864 validation predictions, got {len(pred)}")

    z, zw = _load_ecdf(calibration_ecdf_csv)
    deltas = list(
        range(
            PSEUDO_THRESHOLD_DELTA_MIN_F,
            PSEUDO_THRESHOLD_DELTA_MAX_F + 1,
            PSEUDO_THRESHOLD_DELTA_STEP_F,
        )
    )

    cells: dict[tuple[str, str], list[tuple[str, float, float]]] = defaultdict(list)

    for r in pred:
        d = r["event_date"]
        block = r["local_time_block"]
        mu = float(r["mu_f"])
        scale = float(r["scale_f"])
        target_residual = float(r["target_residual_f"])
        if scale <= 0:
            raise SupportCalibrationError("nonpositive frozen predictive scale")

        for delta in deltas:
            cutoff_z = (float(delta) - mu) / scale
            q_hat = _survival_probability(z, zw, cutoff_z)
            qbin = _q_bin_label(q_hat)
            if qbin is None:
                continue
            y = 1.0 if target_residual > float(delta) else 0.0
            cells[(block, qbin)].append((d, q_hat, y))

    out: list[dict[str, Any]] = []
    for idx, ((block, qbin), rows) in enumerate(sorted(cells.items())):
        per_date = _date_level_cell_means(rows)
        dates = sorted(per_date)
        qbar = float(np.mean([per_date[d][0] for d in dates]))
        ybar = float(np.mean([per_date[d][1] for d in dates]))
        gap = ybar - qbar
        ci_lo, ci_hi = _bootstrap_gap_ci(per_date, seed_offset=idx + 1)
        slack = max(abs(ci_lo), abs(ci_hi))
        support = len(dates) >= MIN_CALIBRATION_CELL_DATES

        out.append({
            "local_time_block": block,
            "q_bin": qbin,
            "independent_date_count": len(dates),
            "pseudo_contract_row_count": len(rows),
            "date_balanced_mean_q_hat": qbar,
            "date_balanced_observed_rate": ybar,
            "calibration_gap_observed_minus_q": gap,
            "gap_ci95_date_cluster_bootstrap": [ci_lo, ci_hi],
            "conservative_probability_slack": slack,
            "calibration_cell_pass": support,
        })

    return out


def write_outputs(
    *,
    output_dir: Path,
    model_ready_csv: Path,
    validation_predictions_csv: Path,
    validation_summary_json: Path,
    calibration_ecdf_csv: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise SupportCalibrationError(f"output_dir already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    validation_summary = _read_json(validation_summary_json)
    if validation_summary.get("validation_date_count") != 279:
        raise SupportCalibrationError("unexpected frozen validation date count")
    if validation_summary.get("validation_available_states_evaluated") != 12864:
        raise SupportCalibrationError("unexpected frozen validation state count")

    state_cells = build_state_support(model_ready_csv=model_ready_csv)
    cal_cells = build_calibration_cells(
        validation_predictions_csv=validation_predictions_csv,
        calibration_ecdf_csv=calibration_ecdf_csv,
    )

    state_path = output_dir / "state_support_cells.csv"
    with state_path.open("w", newline="", encoding="utf-8") as f:
        fields = list(state_cells[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(state_cells)

    cal_path = output_dir / "calibration_support_cells.csv"
    with cal_path.open("w", newline="", encoding="utf-8") as f:
        fields = list(cal_cells[0].keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in cal_cells:
            rr = dict(r)
            rr["gap_ci95_date_cluster_bootstrap"] = json.dumps(
                rr["gap_ci95_date_cluster_bootstrap"]
            )
            w.writerow(rr)

    pass_cal = [r for r in cal_cells if r["calibration_cell_pass"]]
    fail_cal = [r for r in cal_cells if not r["calibration_cell_pass"]]
    max_slack = max(r["conservative_probability_slack"] for r in pass_cal)
    min_slack = min(r["conservative_probability_slack"] for r in pass_cal)

    policy = {
        "support_protocol_id": SUPPORT_PROTOCOL_ID,
        "support_version": SUPPORT_VERSION,
        "source_sha256": {
            "model_ready_states.csv": sha256_file(model_ready_csv),
            "validation_predictions.csv": sha256_file(validation_predictions_csv),
            "validation_summary.json": sha256_file(validation_summary_json),
            "calibration_standardized_residuals.csv": sha256_file(calibration_ecdf_csv),
        },
        "strict_threshold_semantics": "q_hat = P(M_D^WU > theta | weather state)",
        "conservative_probability_rule": {
            "point_probability": "frozen M0 q_hat",
            "cell": "Chicago local 6-hour block x frozen q_hat 0.05-width bin",
            "q_L": "max(0, q_hat - calibration_cell_slack)",
            "q_U": "min(1, q_hat + calibration_cell_slack)",
            "slack_definition": (
                "max absolute endpoint of 95% event-date-cluster-bootstrap CI "
                "for observed-minus-predicted calibration gap in frozen 2026 validation"
            ),
            "YES_conservative_probability": "q_L",
            "NO_conservative_probability": "1 - q_U",
            "forbidden_NO_formula": "1 - q_L",
        },
        "calibration_pseudo_contract_grid": {
            "threshold_delta_definition": "delta = theta - running_max_f",
            "delta_min_f": PSEUDO_THRESHOLD_DELTA_MIN_F,
            "delta_max_f": PSEUDO_THRESHOLD_DELTA_MAX_F,
            "delta_step_f": PSEUDO_THRESHOLD_DELTA_STEP_F,
            "q_min": Q_MIN,
            "q_max": Q_MAX,
            "q_bin_width": Q_BIN_WIDTH,
            "minimum_independent_dates_per_cell": MIN_CALIBRATION_CELL_DATES,
            "bootstrap_reps": BOOTSTRAP_REPS,
            "bootstrap_seed_base": BOOTSTRAP_SEED,
        },
        "future_candidate_support_rule": {
            "state_available_required": True,
            "max_observation_age_minutes": MAX_OBSERVATION_AGE_MINUTES,
            "month_x_local_time_block_cell_min_independent_dates": MIN_STATE_SUPPORT_CELL_DATES,
            "state_feature_range": (
                "candidate running_max_f, temp_minus_running_max_f, "
                "observation_age_minutes, and nonmissing temp_change_60m_f "
                "must lie inside frozen 1st-99th percentile range of the "
                "2024+2025 month x local-time-block support cell"
            ),
            "temp_change_missing_rule": (
                "if candidate temp_change_60m_f is missing, the same 2024+2025 "
                "month x block cell must have >=45 independent dates with trend missing"
            ),
            "threshold_delta_range_f": [
                PSEUDO_THRESHOLD_DELTA_MIN_F,
                PSEUDO_THRESHOLD_DELTA_MAX_F,
            ],
            "q_hat_range": [Q_MIN, Q_MAX],
            "calibration_cell_pass_required": True,
            "no_extrapolation": True,
        },
        "market_selection_risk": {
            "status": "UNRESOLVED_PROSPECTIVE_ONLY",
            "reason": (
                "historical weather data do not identify P(Y|weather, selected "
                "because executable ask looked cheap)"
            ),
            "consequence": (
                "economic screen may produce ECONOMIC_KILL immediately; a positive "
                "weather-only conservative margin is not yet sufficient for "
                "EXECUTABLE_CANDIDATE and remains MODEL_DATA_INSUFFICIENT with "
                "respect to market-selection conditioning until prospective shadow evidence"
            ),
        },
        "no_retuning_statement": (
            "This layer does not change M0 coefficients, features, ridge penalties, "
            "2025 calibration ECDF, historical split, or 2026 validation result."
        ),
        "economics_not_yet_run": True,
        "orders_authorized": False,
        "guardrail": "SUPPORT_CALIBRATION_ONLY_NO_MARKET_PRICE_NO_ECONOMICS_NO_ORDERS",
    }
    (output_dir / "support_policy.json").write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "support_protocol_id": SUPPORT_PROTOCOL_ID,
        "state_support_cell_count": len(state_cells),
        "state_support_pass_count": sum(bool(r["support_cell_pass"]) for r in state_cells),
        "calibration_cell_count": len(cal_cells),
        "calibration_cell_pass_count": len(pass_cal),
        "calibration_cell_fail_count": len(fail_cal),
        "supported_calibration_slack_min": min_slack,
        "supported_calibration_slack_max": max_slack,
        "supported_calibration_cells": [
            {
                "local_time_block": r["local_time_block"],
                "q_bin": r["q_bin"],
                "independent_date_count": r["independent_date_count"],
                "slack": r["conservative_probability_slack"],
            }
            for r in pass_cal
        ],
        "unsupported_calibration_cells": [
            {
                "local_time_block": r["local_time_block"],
                "q_bin": r["q_bin"],
                "independent_date_count": r["independent_date_count"],
            }
            for r in fail_cal
        ],
        "market_selection_risk": "UNRESOLVED_PROSPECTIVE_ONLY",
        "guardrail": "PASS:SUPPORT_CALIBRATION_ONLY_NO_MARKET_PRICE_NO_ECONOMICS_NO_ORDERS",
        "next_boundary": (
            "review/freeze support policy, then implement executable-price economic "
            "kill test without changing M0/support rules"
        ),
    }
    (output_dir / "support_calibration_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
