#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.m0_evaluate import evaluate_once


def _git(args):
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model-ready-csv", required=True, type=Path)
    p.add_argument("--pre-eval-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()

    head = _git(["rev-parse", "HEAD"])
    origin = _git(["rev-parse", "origin/main"])
    if head != origin:
        raise SystemExit("STOP: require HEAD == origin/main before opening validation")
    dirty = _git(["status", "--porcelain", "--untracked-files=no"])
    if dirty:
        raise SystemExit("STOP: tracked worktree must be clean before opening validation")

    source = a.model_ready_csv if a.model_ready_csv.is_absolute() else REPO_ROOT / a.model_ready_csv
    pre = a.pre_eval_dir if a.pre_eval_dir.is_absolute() else REPO_ROOT / a.pre_eval_dir
    out = a.output_dir if a.output_dir.is_absolute() else REPO_ROOT / a.output_dir

    summary = evaluate_once(
        source_csv=source,
        pre_eval_dir=pre,
        output_dir=out,
        canonical_head=head,
    )

    print("===== STUDY 2 M0 ONE-SHOT HISTORICAL VALIDATION =====")
    print("canonical_head:", summary["canonical_head"])
    print("validation_date_count:", summary["validation_date_count"])
    print("validation_total_grid_states:", summary["validation_total_grid_states"])
    print("validation_unavailable_states_excluded:", summary["validation_unavailable_states_excluded"])
    print("validation_available_states_evaluated:", summary["validation_available_states_evaluated"])
    print("primary:", summary["primary_metric"])
    print("secondary_overall:")
    for k, v in summary["secondary_overall"].items():
        print(f"  {k}: {v}")
    print("by_local_time_block:")
    for b, vals in summary["by_local_time_block"].items():
        print(f"  [{b}]")
        for k, v in vals.items():
            print(f"    {k}: {v}")
    print("guardrail=PASS:" + summary["guardrail"])
    print("NEXT=INTERPRET_FROZEN_RESULT_NO_RETUNING")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
