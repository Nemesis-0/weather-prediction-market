#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.support_calibration import write_outputs


def _git(args):
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-ready-csv", required=True, type=Path)
    p.add_argument("--validation-predictions", required=True, type=Path)
    p.add_argument("--validation-summary", required=True, type=Path)
    p.add_argument("--calibration-ecdf", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()

    head = _git(["rev-parse", "HEAD"])
    origin = _git(["rev-parse", "origin/main"])
    if head != origin:
        raise SystemExit("STOP: require HEAD == origin/main")
    dirty = _git(["status", "--porcelain", "--untracked-files=no"])
    if dirty:
        raise SystemExit("STOP: tracked worktree must be clean")

    def r(pth: Path) -> Path:
        return pth if pth.is_absolute() else REPO_ROOT / pth

    summary = write_outputs(
        output_dir=r(a.output_dir),
        model_ready_csv=r(a.model_ready_csv),
        validation_predictions_csv=r(a.validation_predictions),
        validation_summary_json=r(a.validation_summary),
        calibration_ecdf_csv=r(a.calibration_ecdf),
    )

    print("===== STUDY 2 SUPPORT + CALIBRATION FREEZE =====")
    print("canonical_head:", head)
    print("state_support_cell_count:", summary["state_support_cell_count"])
    print("state_support_pass_count:", summary["state_support_pass_count"])
    print("calibration_cell_count:", summary["calibration_cell_count"])
    print("calibration_cell_pass_count:", summary["calibration_cell_pass_count"])
    print("calibration_cell_fail_count:", summary["calibration_cell_fail_count"])
    print(
        "supported_calibration_slack_min/max:",
        summary["supported_calibration_slack_min"],
        summary["supported_calibration_slack_max"],
    )
    print("market_selection_risk:", summary["market_selection_risk"])
    print("unsupported_calibration_cells:")
    for x in summary["unsupported_calibration_cells"]:
        print(" ", x)
    print("guardrail=" + summary["guardrail"])
    print("NEXT=REVIEW_AND_FREEZE_BEFORE_EXECUTABLE_ECONOMIC_KILL_TEST")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
