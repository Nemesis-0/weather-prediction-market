#!/usr/bin/env python3
"""Strategy-blind short acceptance check for V3 Study 1 pre-freeze remediation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.audit.ibkr_capability import MARKET_DATA_FIELDS
from src.v3.ibkr.client import IBKRClient
from src.v3.study1.confirmatory import (
    CONFIRMATORY_VERSION, PRODUCTS, ConfirmatoryEligibilityError, acquire_event_ladder,
    archive_terms, best_ntp_offset, discover_fixed_markets, write_json,
    snapshot_failure_class, validate_pair_snapshot, validate_schedule_open,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Strategy-blind 5-cycle acceptance check; never computes basket costs or opportunity flags.")
    p.add_argument("--base-url", default="https://localhost:5001/v1/api")
    p.add_argument("--event-date", required=True, help="Scientific event date YYYY-MM-DD parsed from contract questions.")
    p.add_argument("--cycles", type=int, default=5)
    p.add_argument("--cadence-seconds", type=float, default=30.0)
    p.add_argument("--output-root", default="local_artifacts/v3_study1_prefreeze_acceptance")
    args = p.parse_args()
    if args.cycles < 5:
        raise SystemExit("STOP: acceptance requires at least 5 cycles")
    target = date.fromisoformat(args.event_date)
    out = Path(args.output_root) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)

    client = IBKRClient(base_url=args.base_url)
    auth = client.auth_status()
    status = auth.get("success", {}).get("value", {}) if isinstance(auth, dict) else {}
    if not status and isinstance(auth, dict): status = auth
    safe_auth = {k: bool((status or {}).get(k, False)) for k in ("authenticated", "established", "connected", "competing")}
    if not safe_auth["authenticated"] or not safe_auth["established"] or not safe_auth["connected"] or safe_auth["competing"]:
        raise SystemExit(f"STOP: gateway not ready: {safe_auth}")
    client.accounts(); client.tickle()

    clock = best_ntp_offset()
    write_json(out / "clock_health.json", clock)
    if not clock.get("ok"):
        raise SystemExit(f"STOP: clock offset could not be verified within 1s: {clock}")

    fixed = discover_fixed_markets(client)
    ladders = {}
    schedules = {}
    terms_urls = set()
    for spec in PRODUCTS:
        payload = (fixed[spec.city_id].get("market") or {})
        ladder = acquire_event_ladder(client, spec, payload, target)
        # Do not persist raw contract quotes or any strategy-derived values.
        ladders[spec.city_id] = ladder
        for row in ladder["thresholds"]:
            if row.get("market_rules_link"): terms_urls.add(str(row["market_rules_link"]))
        rep = int(ladder["thresholds"][0]["yes_conid"])
        schedule = client.contract_schedules(rep)
        schedules[spec.city_id] = {"schedule": schedule, "readiness": validate_schedule_open(schedule, now_epoch=time.time())}
    write_json(out / "semantic_ladder_audit.json", ladders)
    write_json(out / "schedule_readiness.json", schedules)

    terms = []
    for url in sorted(terms_urls):
        terms.append(archive_terms(url, out / "terms"))
    write_json(out / "terms_manifest.json", terms)

    # Prime all unique conids in coarse batches. Pair validation below is always a
    # dedicated same-request two-conid snapshot.
    all_conids = sorted({c for lad in ladders.values() for pair in lad["adjacent_pairs"]
                         for c in (pair["lower_yes_conid"], pair["higher_no_conid"])})
    for i in range(0, len(all_conids), 8):
        client.marketdata_snapshot(all_conids[i:i+8], fields=list(MARKET_DATA_FIELDS))
    time.sleep(0.75)

    cycle_summaries = []
    total_pair_checks = 0
    quote_unavailable_checks = 0
    structural_failure_checks = 0
    old_age_diagnostic_checks = 0
    skew_diagnostic_checks = 0
    start = time.monotonic()
    for cycle in range(1, args.cycles + 1):
        due = start + (cycle - 1) * args.cadence_seconds
        while time.monotonic() < due:
            time.sleep(min(0.25, due - time.monotonic()))
        cycle_start = time.monotonic()
        valid_pairs = 0; invalid_pairs = 0; max_request = 0.0; max_skew = 0.0; max_age = 0.0
        failures = {}; failure_classes = {"quote_unavailable": 0, "structural_failure": 0}
        age_diagnostic = 0; skew_diagnostic = 0
        for city_id, lad in ladders.items():
            for pair in lad["adjacent_pairs"]:
                expected = (int(pair["lower_yes_conid"]), int(pair["higher_no_conid"]))
                t0 = time.monotonic(); payload = client.marketdata_snapshot(expected, fields=list(MARKET_DATA_FIELDS)); t1 = time.monotonic()
                elapsed = t1 - t0; received_epoch = time.time(); max_request = max(max_request, elapsed)
                total_pair_checks += 1
                try:
                    checked = validate_pair_snapshot(payload, expected_conids=expected, request_elapsed_seconds=elapsed,
                                                     response_received_epoch=received_epoch)
                    valid_pairs += 1
                    pair_skew = float(checked["pair_broker_skew_seconds"])
                    max_skew = max(max_skew, pair_skew)
                    row_ages = [float(r["broker_age_seconds"]) for r in checked["rows"]]
                    if row_ages:
                        max_age = max(max_age, max(row_ages))
                    if any(bool(r.get("broker_age_diagnostic_exceeds_reference")) for r in checked["rows"]):
                        age_diagnostic += 1; old_age_diagnostic_checks += 1
                    if bool(checked.get("pair_broker_skew_diagnostic_exceeds_reference")):
                        skew_diagnostic += 1; skew_diagnostic_checks += 1
                except ConfirmatoryEligibilityError as exc:
                    invalid_pairs += 1
                    key = str(exc).split(":", 1)[0]
                    failures[key] = failures.get(key, 0) + 1
                    cls = snapshot_failure_class(exc)
                    failure_classes[cls] += 1
                    if cls == "quote_unavailable":
                        quote_unavailable_checks += 1
                    else:
                        structural_failure_checks += 1
        cycle_elapsed = time.monotonic() - cycle_start
        cycle_summaries.append({"cycle": cycle, "valid_pair_snapshots": valid_pairs, "invalid_pair_snapshots": invalid_pairs,
                                "max_request_elapsed_seconds": max_request, "max_pair_broker_skew_seconds": max_skew,
                                "max_broker_age_seconds_observed": max_age,
                                "broker_age_diagnostic_checks": age_diagnostic,
                                "pair_skew_diagnostic_checks": skew_diagnostic,
                                "cycle_elapsed_seconds": cycle_elapsed, "failure_counts": failures,
                                "failure_classes": failure_classes})

    expected_pair_checks = args.cycles * sum(len(lad["adjacent_pairs"]) for lad in ladders.values())
    acceptance_status = "PASS" if total_pair_checks == expected_pair_checks and structural_failure_checks == 0 else "FAIL"
    result = {
        "version": CONFIRMATORY_VERSION,
        "study_status": "PREFREEZE_STRATEGY_BLIND_ACCEPTANCE_ONLY",
        "acceptance_status": acceptance_status,
        "event_date": target.isoformat(), "cycles": args.cycles, "cadence_seconds": args.cadence_seconds,
        "clock_health": clock,
        "cities": {cid: {"threshold_count": len(lad["thresholds"]), "adjacent_pair_count": len(lad["adjacent_pairs"])} for cid, lad in ladders.items()},
        "coverage": {
            "expected_pair_checks": expected_pair_checks,
            "completed_pair_checks": total_pair_checks,
            "quote_eligible_checks": total_pair_checks - quote_unavailable_checks - structural_failure_checks,
            "quote_unavailable_checks": quote_unavailable_checks,
            "structural_failure_checks": structural_failure_checks,
        },
        "broker_timestamp_diagnostics": {
            "age_reference_seconds": 60.0,
            "pair_skew_reference_seconds": 5.0,
            "checks_exceeding_age_reference": old_age_diagnostic_checks,
            "checks_exceeding_pair_skew_reference": skew_diagnostic_checks,
            "eligibility_role": "diagnostic_only; implausibly future _updated remains a hard failure",
        },
        "cycle_summaries": cycle_summaries,
        "guardrail": "No basket cost, margin, opportunity flag, candidate selection, alpha, hypothetical fill, or PnL was computed or emitted.",
    }
    write_json(out / "acceptance_summary.json", result)
    print(f"output_dir: {out}")
    print(f"event_date={target.isoformat()}")
    print(f"cycles={args.cycles}")
    print("cities=" + json.dumps(result["cities"], sort_keys=True))
    print(f"clock_offset_seconds={clock.get('offset_seconds')}")
    print(f"acceptance_status={acceptance_status}")
    print("coverage=" + json.dumps(result["coverage"], sort_keys=True))
    print("strategy_guardrail=PASS:no_cost_or_opportunity_computation")
    print("acceptance_summary=" + str(out / "acceptance_summary.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
