#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.m0 import load_pre_eval_data, fit_pre_eval, write_pre_eval_artifacts


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-ready-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()

    source = a.model_ready_csv if a.model_ready_csv.is_absolute() else REPO_ROOT / a.model_ready_csv
    out = a.output_dir if a.output_dir.is_absolute() else REPO_ROOT / a.output_dir

    data = load_pre_eval_data(source)
    fit = fit_pre_eval(data)
    summary = write_pre_eval_artifacts(
        output_dir=out,
        source_csv=source,
        data=data,
        fit=fit,
    )

    print("===== STUDY 2 M0 PRE-EVALUATION FIT =====")
    print("output_dir:", out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out)
    print("train_dates:", summary["train_dates"])
    print("train_available_states:", summary["train_available_states"])
    print("calibration_dates:", summary["calibration_dates"])
    print("calibration_available_states:", summary["calibration_available_states"])
    print(
        "validation_available_rows_skipped_before_numeric_parse:",
        summary["historical_validation_available_rows_skipped_before_numeric_parse"],
    )
    print("validation_target_values_used:", summary["historical_validation_target_values_used"])
    print("validation_feature_values_used:", summary["historical_validation_feature_values_used"])
    print("calibration_z_quantiles:", summary["calibration_z_quantiles"])
    print(
        "train_scale_min/median/max:",
        summary["train_scale_min"],
        summary["train_scale_median"],
        summary["train_scale_max"],
    )
    print(
        "calibration_scale_min/median/max:",
        summary["calibration_scale_min"],
        summary["calibration_scale_median"],
        summary["calibration_scale_max"],
    )
    print("guardrail=PASS:" + summary["guardrail"])
    print("NEXT=REVIEW_PRE_EVAL_ONLY_DO_NOT_RUN_2026_EVALUATION_YET")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
