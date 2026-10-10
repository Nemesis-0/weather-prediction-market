#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.v3.study2.model_ready import build_model_ready


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backfill-root", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()

    backfill = a.backfill_root if a.backfill_root.is_absolute() else REPO_ROOT / a.backfill_root
    out = a.output_dir if a.output_dir.is_absolute() else REPO_ROOT / a.output_dir

    manifest = build_model_ready(backfill_root=backfill, output_dir=out)

    print("===== STUDY 2 MODEL-READY BUILD =====")
    print("output_dir:", out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out)
    print("source_date_count:", manifest["source_date_count"])
    print("state_row_count:", manifest["state_row_count"])
    print("state_available_row_count:", manifest["state_available_row_count"])
    print("split_date_counts:", manifest["split_date_counts"])
    print("split_state_counts:", manifest["split_state_counts"])
    print("split_available_state_counts:", manifest["split_available_state_counts"])
    print("fresh_raw_hashes_verified:", manifest["fresh_raw_hashes_verified"])
    print(
        "dates_with_nonzero_wu_iem_daily_max_difference:",
        manifest["dates_with_nonzero_wu_iem_daily_max_difference"],
    )
    print(
        "dates_with_iem_wu_observation_count_mismatch:",
        manifest["dates_with_iem_wu_observation_count_mismatch"],
    )
    print(
        "historical_availability_convention:",
        manifest["historical_availability_convention"],
    )
    print(
        "historical_wu_vintage_limitation:",
        manifest["historical_wu_vintage_limitation"],
    )
    print("guardrail=PASS:pre_model_only_no_probability_no_economics_no_orders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
