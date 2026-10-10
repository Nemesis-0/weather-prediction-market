#!/usr/bin/env python3
"""Run/resume V3 Study 2 historical IEM/WU backfill. No modeling or economics."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.backfill import run_backfill


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="V3 Study 2 resumable historical IEM/WU backfill")
    p.add_argument("--start-date", required=True, help="inclusive Chicago-local YYYY-MM-DD")
    p.add_argument("--end-date", required=True, help="inclusive Chicago-local YYYY-MM-DD")
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--inter-date-sleep-seconds", type=float, default=3.0)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    start = date.fromisoformat(a.start_date)
    end = date.fromisoformat(a.end_date)
    today = datetime.now(ZoneInfo("America/Chicago")).date()

    out = a.output_dir
    if not out.is_absolute():
        out = REPO_ROOT / out

    summary = run_backfill(
        start_date=start,
        end_date=end,
        output_dir=out,
        chicago_today=today,
        timeout_seconds=max(1.0, float(a.timeout_seconds)),
        inter_date_sleep_seconds=max(0.0, float(a.inter_date_sleep_seconds)),
    )

    try:
        shown = out.relative_to(REPO_ROOT)
    except ValueError:
        shown = out

    print("===== STUDY 2 HISTORICAL BACKFILL =====")
    print("output_dir:", shown)
    print("requested_date_count:", summary["requested_date_count"])
    print("status_counts:", summary["status_counts"])
    print("attempted_this_run:", summary["attempted_this_run"])
    print("skipped_existing_pass_this_run:", summary["skipped_existing_pass_this_run"])
    print("all_dates_pass:", summary["all_dates_pass"])
    print(
        "daily_max_diff_counts:",
        {
            "negative": summary["daily_max_difference_wu_minus_iem_f_negative_date_count"],
            "zero": summary["daily_max_difference_wu_minus_iem_f_zero_date_count"],
            "positive": summary["daily_max_difference_wu_minus_iem_f_positive_date_count"],
        },
    )
    print(
        "historical_wu_vintage_limitation:",
        summary["historical_wu_vintage_limitation"],
    )
    print(
        "guardrail=PASS:read_only_historical_sources_only_no_model_no_probability_no_economics_no_orders"
    )
    return 0 if summary["all_dates_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
