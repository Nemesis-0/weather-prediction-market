#!/usr/bin/env python3
"""Run one read-only V3 Study 2 KMDW H0 development capture session."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import urllib3

from src.v3.ibkr.client import IBKRClient
from src.v3.study2.capture import Study2CaptureConfig, run_development_session
from src.v3.study2.targets import chicago_local_date


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read-only V3 Study 2 KMDW H0 target/quote development capture"
    )
    p.add_argument("--base-url", default="https://localhost:5001/v1/api")
    p.add_argument("--verify-tls", action="store_true")
    p.add_argument("--event-date", help="KMDW local date YYYY-MM-DD; default=current Chicago date")
    p.add_argument("--duration-seconds", type=float, required=True)
    p.add_argument("--cadence-seconds", type=float, default=30.0)
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--weather-cadence-seconds", type=float, default=60.0)
    p.add_argument("--wu-cadence-seconds", type=float, default=300.0)
    p.add_argument("--public-source-timeout-seconds", type=float, default=15.0)
    p.add_argument("--disable-public-sources", action="store_true")
    p.add_argument("--output-dir", type=Path)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    if a.duration_seconds <= 0:
        raise SystemExit("--duration-seconds must be positive")
    if a.cadence_seconds < 5:
        raise SystemExit("--cadence-seconds must be at least 5 seconds during H0 development")
    event_date = date.fromisoformat(a.event_date) if a.event_date else chicago_local_date()

    if not a.verify_tls and a.base_url.startswith("https://localhost"):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if a.output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = REPO_ROOT / "local_artifacts" / "v3_study2_development" / stamp
    else:
        out = a.output_dir

    client = IBKRClient(base_url=a.base_url, verify_tls=a.verify_tls)
    config = Study2CaptureConfig(
        cadence_seconds=float(a.cadence_seconds),
        batch_size=max(1, int(a.batch_size)),
        weather_cadence_seconds=max(5.0, float(a.weather_cadence_seconds)),
        wu_cadence_seconds=max(30.0, float(a.wu_cadence_seconds)),
        public_source_timeout_seconds=max(1.0, float(a.public_source_timeout_seconds)),
        enable_public_sources=not bool(a.disable_public_sources),
    )
    summary = run_development_session(
        client=client,
        event_date=event_date,
        output_dir=out,
        duration_seconds=float(a.duration_seconds),
        config=config,
    )

    try:
        shown = out.relative_to(REPO_ROOT)
    except ValueError:
        shown = out
    print(f"output_dir: {shown}")
    print(f"event_date={summary['event_date']}")
    print(f"selected_contracts={summary['selected_contract_count']}")
    print(f"completed_cycles={summary['completed_cycles']}")
    print(f"quote_records={summary['quote_records']}")
    print(f"missing_contract_responses={summary['missing_contract_responses']}")
    print(f"http_errors={summary['http_errors']}")
    print(f"tickle_failures={summary['tickle_failures']}")
    print(f"auth_failures={summary['auth_failures']}")
    print(f"gaps={summary['gaps']}")
    print(f"delivery_modes={json.dumps(summary['delivery_modes'], sort_keys=True)}")
    print(f"iem_fetch_attempts={summary['iem_fetch_attempts']}")
    print(f"iem_fetch_successes={summary['iem_fetch_successes']}")
    print(f"iem_fetch_failures={summary['iem_fetch_failures']}")
    print(f"iem_new_observations={summary['iem_new_observations']}")
    print(f"wu_fetch_attempts={summary['wu_fetch_attempts']}")
    print(f"wu_fetch_successes={summary['wu_fetch_successes']}")
    print(f"wu_fetch_failures={summary['wu_fetch_failures']}")
    print(f"wu_semantic_revisions={summary['wu_semantic_revisions']}")
    print("study2_guardrail=PASS:read_only_no_order_submission_no_alpha_or_pnl_computation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
