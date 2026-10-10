#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.economic_kill import screen_session


def _git(args):
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--session-dir", required=True, type=Path)
    p.add_argument("--pre-eval-dir", required=True, type=Path)
    p.add_argument("--validation-dir", required=True, type=Path)
    p.add_argument("--support-dir", required=True, type=Path)
    p.add_argument(
        "--economic-config",
        type=Path,
        default=Path("configs/v3/study2_economic_kill_frozen.json"),
    )
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()

    head = _git(["rev-parse", "HEAD"])
    origin = _git(["rev-parse", "origin/main"])
    if head != origin:
        raise SystemExit("STOP: require HEAD == origin/main")
    dirty = _git(["status", "--porcelain", "--untracked-files=no"])
    if dirty:
        raise SystemExit("STOP: tracked worktree must be clean")

    commit_utc = datetime.fromisoformat(_git(["show", "-s", "--format=%cI", "HEAD"]))

    def r(pth: Path) -> Path:
        return pth if pth.is_absolute() else REPO_ROOT / pth

    summary = screen_session(
        session_dir=r(a.session_dir),
        pre_eval_dir=r(a.pre_eval_dir),
        validation_dir=r(a.validation_dir),
        support_dir=r(a.support_dir),
        economic_config_path=r(a.economic_config),
        output_dir=r(a.output_dir),
        protocol_commit_utc=commit_utc,
    )

    print("===== STUDY 2 FRESH EXECUTABLE ECONOMIC KILL SCREEN =====")
    print("canonical_head:", head)
    print("event_date:", summary["event_date"])
    print("quote_rows_total:", summary["quote_rows_total"])
    print("valid_supported_economic_rows:", summary["valid_supported_economic_rows"])
    print("nonpositive_supported_rows:", summary["nonpositive_supported_rows"])
    print("positive_supported_rows:", summary["positive_supported_rows"])
    print("model_data_insufficient_rows:", summary["model_data_insufficient_rows"])
    print("invalid_executable_quote_rows:", summary["invalid_executable_quote_rows"])
    print("by_side:", summary["by_side"])
    print("min_supported_margin:", summary["min_supported_margin"])
    print("max_supported_margin:", summary["max_supported_margin"])
    print("market_selection_risk:", summary["market_selection_risk"])
    print("session_decision:", summary["session_decision"])
    if summary["top_positive_candidates"]:
        print("top_positive_candidates:")
        for x in summary["top_positive_candidates"]:
            print(" ", x)
    print("global_economic_kill_claim:", summary["global_economic_kill_claim"])
    print("orders_authorized:", summary["orders_authorized"])
    print("guardrail=" + summary["guardrail"])
    print("NEXT=" + summary["next_boundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
