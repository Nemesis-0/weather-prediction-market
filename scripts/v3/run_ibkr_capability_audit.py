#!/usr/bin/env python3
"""Run the read-only V3 IBKR / ForecastEx capability audit.

No order endpoint is implemented or called by this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import urllib3

from src.v3.audit.ibkr_capability import run_http_capability_audit
from src.v3.ibkr.client import DEFAULT_BASE_URL, IBKRClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only V3 IBKR / ForecastEx capability audit."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--verify-tls", action="store_true")
    parser.add_argument("--symbol")
    parser.add_argument("--contract-conid", type=int)
    parser.add_argument("--market-conid", type=int, action="append", default=[])
    parser.add_argument(
        "--auto-weather",
        action="store_true",
        help="Discover ForecastEx weather/temperature markets from the category tree.",
    )
    parser.add_argument(
        "--market-name-pattern",
        default=r"temperature|weather",
        help="Case-insensitive regex used by --auto-weather.",
    )
    parser.add_argument("--max-markets", type=int, default=6)
    parser.add_argument("--max-contract-pairs-per-market", type=int, default=2)
    parser.add_argument("--probe-history", action="store_true")
    parser.add_argument(
        "--websocket-seconds",
        type=float,
        default=0.0,
        help="Short read-only top-of-book websocket probe duration; 0 disables.",
    )
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def write_summary(report: dict, path: Path) -> None:
    auth = report.get("auth") or {}
    discovery = report.get("auto_weather_discovery") or {}
    snapshot = report.get("market_snapshot") or []
    ws = report.get("websocket_probe") or {}
    history = report.get("historical_probe") or {}
    deliveries = sorted(
        {
            (x.get("market_data_availability_decoded") or {}).get("delivery")
            for x in snapshot
            if isinstance(x, dict)
        }
        - {None}
    )
    lines = [
        "V3 IBKR / ForecastEx Capability Audit",
        "======================================",
        f"Created UTC: {report.get('created_at_utc')}",
        f"Base URL: {report.get('base_url')}",
        f"Gateway reachable: {report.get('gateway_reachable')}",
        f"Authenticated: {auth.get('authenticated')}",
        f"Connected: {auth.get('connected')}",
        f"Established: {auth.get('established')}",
        f"Tickle OK: {report.get('tickle_ok')}",
        f"Accounts endpoint OK: {report.get('accounts_endpoint_ok')}",
        f"Account count (IDs not stored): {report.get('account_count')}",
        f"ForecastEx markets in category tree: {discovery.get('total_markets_in_tree')}",
        f"Weather/temperature market matches: {discovery.get('matching_market_count')}",
        f"Markets contract-probed: {len(discovery.get('probed_markets') or [])}",
        f"BBO contracts returned: {len(snapshot)}",
        f"Observed market-data delivery modes: {', '.join(deliveries) if deliveries else 'none'}",
        f"Historical 1-min probe OK: {history.get('ok')}",
        f"Historical bars returned: {history.get('bar_count')}",
        f"Websocket matching messages: {ws.get('matching_market_messages')}",
        f"Websocket availability codes: {ws.get('market_data_availability_values')}",
        f"Errors: {len(report.get('errors', []))}",
        "",
        "Interpretation boundary:",
        "- Read-only infrastructure evidence only; not an alpha result.",
        "- No order endpoint is implemented or called.",
        "- Broker `_updated` is not labeled as an exchange timestamp.",
        "- Session tokens/account identifiers are not persisted.",
    ]
    if report.get("errors"):
        lines += ["", "Errors:"] + [f"- {x}" for x in report["errors"]]
    if report.get("remaining_audit_work"):
        lines += ["", "Remaining audit work:"] + [f"- {x}" for x in report["remaining_audit_work"]]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    args = parse_args()
    if not args.verify_tls and args.base_url.startswith("https://localhost"):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if args.output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_dir = Path("local_artifacts") / "v3_api_capability_audit" / stamp
    else:
        output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    client = IBKRClient(base_url=args.base_url, verify_tls=args.verify_tls)
    report = run_http_capability_audit(
        client,
        symbol=args.symbol,
        contract_conid=args.contract_conid,
        market_conids=args.market_conid,
        auto_weather=args.auto_weather,
        market_name_pattern=args.market_name_pattern,
        max_markets=max(1, args.max_markets),
        max_contract_pairs_per_market=max(1, args.max_contract_pairs_per_market),
        probe_history=args.probe_history,
        websocket_seconds=max(0.0, args.websocket_seconds),
    )

    json_path = output_dir / "capability_report.json"
    summary_path = output_dir / "capability_summary.txt"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_summary(report, summary_path)

    print(f"report:  {json_path}")
    print(f"summary: {summary_path}")
    print(f"gateway_reachable={report['gateway_reachable']}")
    if report.get("auth"):
        print(f"authenticated={report['auth'].get('authenticated')}")
    discovery = report.get("auto_weather_discovery") or {}
    print(f"weather_market_matches={discovery.get('matching_market_count')}")
    print(f"bbo_contracts={len(report.get('market_snapshot') or [])}")
    print(f"websocket_messages={(report.get('websocket_probe') or {}).get('matching_market_messages')}")
    print(f"errors={len(report.get('errors', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
