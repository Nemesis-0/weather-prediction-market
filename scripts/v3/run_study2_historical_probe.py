#!/usr/bin/env python3
"""Run a bounded read-only historical source feasibility probe for V3 Study 2."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.historical import DEFAULT_PROBE_DATES, run_historical_probe


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="V3 Study 2 KMDW historical IEM/WU source feasibility probe")
    p.add_argument(
        "--date",
        dest="dates",
        action="append",
        help="historical Chicago-local date YYYY-MM-DD; may repeat; defaults to fixed 8-date DST/ordinary probe",
    )
    p.add_argument("--timeout-seconds", type=float, default=20.0)
    p.add_argument("--inter-date-sleep-seconds", type=float, default=3.0)
    p.add_argument("--output-dir", type=Path)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    dates = [date.fromisoformat(x) for x in a.dates] if a.dates else list(DEFAULT_PROBE_DATES)
    if a.output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = REPO_ROOT / "local_artifacts" / "v3_study2_historical_probe" / stamp
    else:
        out = a.output_dir

    summary = run_historical_probe(
        dates=dates,
        output_dir=out,
        timeout_seconds=max(1.0, float(a.timeout_seconds)),
        inter_date_sleep_seconds=max(0.0, float(a.inter_date_sleep_seconds)),
    )

    try:
        shown = out.relative_to(REPO_ROOT)
    except ValueError:
        shown = out
    print(f"output_dir: {shown}")
    print(f"requested_date_count={summary['requested_date_count']}")
    print(f"source_pair_pass_count={summary['source_pair_pass_count']}")
    print(f"source_pair_fail_count={summary['source_pair_fail_count']}")
    print(f"all_source_pairs_ok={summary['all_source_pairs_ok']}")
    for row in summary["dates"]:
        print(
            f"date={row['event_date']} pair_ok={row['source_pair_ok']} "
            f"iem_ok={row['iem'].get('parse_ok')} wu_ok={row['wu'].get('parse_ok')} "
            f"iem_dup_local={row['iem'].get('duplicate_valid_local_count')} "
            f"wu_dup_time={row['wu'].get('duplicate_time_label_count')}"
        )
    print("study2_historical_probe_guardrail=PASS:read_only_sources_only_no_model_no_economics_no_orders")
    return 0 if summary["all_source_pairs_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
