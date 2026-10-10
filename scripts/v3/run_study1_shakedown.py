#!/usr/bin/env python3
"""Run one V3 Study 1 strategy-blind shakedown session."""

from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import urllib3
from src.v3.ibkr.client import IBKRClient
from src.v3.study1.collector import ShakedownConfig, run_session


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="V3 Study 1 strategy-blind operational shakedown collector")
    p.add_argument("--base-url", default="https://localhost:5001/v1/api")
    p.add_argument("--verify-tls", action="store_true")
    p.add_argument("--duration-seconds", type=float)
    p.add_argument("--duration-hours", type=float)
    p.add_argument("--rotation-index", type=int, default=0)
    p.add_argument("--cadence-seconds", type=float, default=30.0, help="PROVISIONAL shakedown cadence only")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--max-markets", type=int, default=24)
    p.add_argument("--contracts-per-market", type=int, default=8)
    p.add_argument("--rotation-modulus", type=int, default=3)
    p.add_argument("--rule-audit-contract-limit", type=int, default=0, help="0=auto: one complete YES/NO pair per selected market")
    p.add_argument("--market-name-pattern", default=r"(?i)(temperature.*high|high.*temperature)")
    p.add_argument("--output-dir", type=Path)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    if a.duration_seconds is None and a.duration_hours is None:
        raise SystemExit("Specify --duration-seconds or --duration-hours")
    if a.duration_seconds is not None and a.duration_hours is not None:
        raise SystemExit("Specify only one of --duration-seconds or --duration-hours")
    duration = float(a.duration_seconds if a.duration_seconds is not None else a.duration_hours * 3600.0)
    if duration <= 0:
        raise SystemExit("Duration must be positive")
    if not a.verify_tls and a.base_url.startswith("https://localhost"):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if a.output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = REPO_ROOT / "local_artifacts" / "v3_study1_shakedown" / stamp
    else:
        out = a.output_dir
    cfg = ShakedownConfig(
        base_url=a.base_url, market_name_pattern=a.market_name_pattern,
        provisional_cadence_seconds=max(5.0, float(a.cadence_seconds)), batch_size=max(1, int(a.batch_size)),
        max_markets_per_session=max(1, int(a.max_markets)), contracts_per_market=max(1, int(a.contracts_per_market)),
        rotation_modulus=max(1, int(a.rotation_modulus)), rule_audit_contract_limit=max(0, int(a.rule_audit_contract_limit)),
    )
    client = IBKRClient(base_url=a.base_url, verify_tls=a.verify_tls)
    summary = run_session(client=client, config=cfg, output_dir=out, duration_seconds=duration, rotation_index=a.rotation_index)
    try:
        shown = out.relative_to(REPO_ROOT)
    except ValueError:
        shown = out
    print(f"output_dir: {shown}")
    print(f"selected_markets={summary['selected_market_count']}")
    print(f"selected_contracts={summary['selected_contract_count']}")
    print(f"completed_cycles={summary['completed_cycles']}")
    print(f"quote_records={summary['quote_records']}")
    print(f"full_bbo_size_records={summary['full_bbo_size_records']}")
    print(f"http_errors={summary['http_errors']}")
    print(f"tickle_failures={summary['tickle_failures']}")
    print(f"gaps={summary['gaps']}")
    print(f"delivery_modes={json.dumps(summary['delivery_modes'], sort_keys=True)}")
    print(f"rule_audit_contract_limit_effective={summary['rule_audit_contract_limit_effective']}")
    print(f"rule_audit_markets={summary['rule_audit_market_count']}")
    print(f"schedule_audit_markets={summary['schedule_audit_market_count']}")
    print(f"schedule_audit_errors={summary['schedule_audit_errors']}")
    print("strategy_guardrail=PASS:no_opportunity_or_pnl_computation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
