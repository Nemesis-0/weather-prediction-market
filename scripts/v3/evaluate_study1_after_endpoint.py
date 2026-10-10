#!/usr/bin/env python3
"""Frozen endpoint evaluator for V3 Study 1. Refuses to run before endpoint."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.study1.frozen import (
    audit_valid_day_inputs,
    endpoint_unlock_time,
    evaluate_city_date,
    load_frozen_config,
    mbb_interval,
    planned_dates,
    read_day_health_summary,
    read_jsonl,
    verify_freeze_manifest,
)


def write_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Frozen V3 Study 1 endpoint evaluator; unavailable before final session ends.")
    p.add_argument("--input-root", default="local_artifacts/v3_study1_confirmatory")
    p.add_argument("--output", default="results/v3/study1_confirmatory_endpoint.json")
    args = p.parse_args()

    cfg = load_frozen_config(ROOT)
    freeze_state = verify_freeze_manifest(ROOT)
    unlock = endpoint_unlock_time(cfg)
    if datetime.now(timezone.utc) < unlock:
        raise SystemExit(f"STOP: endpoint firewall locked until {unlock.isoformat()}")

    input_root = Path(args.input_root)
    out = Path(args.output)

    # Pre-scan every planned date before any opportunity computation. A readable
    # semantic/terms blocker closes the study globally. Missing/corrupt health
    # files are cached as date-level integrity failures rather than crashing the
    # evaluator or being mistaken for market zeros.
    health_cache: dict[str, dict | None] = {}
    health_errors: dict[str, str] = {}
    for d in planned_dates(cfg):
        hp = input_root / d / "day_health_summary.json"
        health, health_error = read_day_health_summary(hp, event_date=d, cfg=cfg)
        health_cache[d] = health
        if health_error is not None:
            health_errors[d] = health_error
            continue
        assert health is not None
        if health.get("date_status") == "STUDY_BLOCKER" or health.get("study_blocker"):
            result = {
                "protocol_id": cfg["protocol_id"],
                "decision": "CLOSE_SEMANTIC_OR_TERMS_BLOCKER",
                "blocking_date": d,
                "study_blocker": health.get("study_blocker"),
                "execution_claim": False,
                "primary_endpoint_evaluated": False,
            }
            write_result(out, result)
            print(json.dumps(result, indent=2))
            return 3

    date_rows: list[dict] = []
    endpoint_values: list[int] = []
    aborted = 0
    for d in planned_dates(cfg):
        day = input_root / d
        health = health_cache[d]
        if d in health_errors:
            aborted += 1; endpoint_values.append(0)
            date_rows.append({
                "date": d,
                "status": "INTEGRITY_FAILURE_RETAIN_IN_DENOMINATOR",
                "primary_value": 0,
                "city_candidates": {},
                "integrity_failure": health_errors[d],
            })
            continue

        assert health is not None
        if health.get("date_status") != "VALID":
            aborted += 1; endpoint_values.append(0)
            date_rows.append({"date": d, "status": health.get("date_status"), "primary_value": 0, "city_candidates": {}, "terminal_failure": health.get("terminal_failure")})
            continue

        try:
            ladder_path = day / "semantic_ladder_audit.json"
            if not ladder_path.is_file():
                raise RuntimeError("missing semantic_ladder_audit.json")
            ladders = json.loads(ladder_path.read_text(encoding="utf-8"))
            records = read_jsonl(day / cfg["result_firewall"]["sealed_input_file"])
            normal_slots = audit_valid_day_inputs(
                day,
                event_date=d,
                cfg=cfg,
                health=health,
                ladders=ladders,
                records=records,
                manifest_sha256=freeze_state["manifest_sha256"],
            )
        except Exception as exc:
            aborted += 1; endpoint_values.append(0)
            date_rows.append({"date": d, "status": "INTEGRITY_FAILURE_RETAIN_IN_DENOMINATOR", "primary_value": 0, "city_candidates": {}, "integrity_failure": f"{type(exc).__name__}: {exc}"})
            continue

        city_candidates = {
            cid: evaluate_city_date(records, city_id=cid, ladder=lad, cfg=cfg, valid_slot_indices=normal_slots)
            for cid, lad in ladders.items()
        }
        value = int(any(v is not None for v in city_candidates.values()))
        endpoint_values.append(value)
        date_rows.append({"date": d, "status": "VALID", "primary_value": value, "city_candidates": city_candidates})

    n = len(endpoint_values)
    k = sum(endpoint_values)
    rate = k / n
    inf = cfg["evaluation"]["inference"]
    ci3 = mbb_interval(endpoint_values, block_days=inf["moving_block_bootstrap_block_days"], replicates=inf["moving_block_bootstrap_replicates"], seed=inf["bootstrap_seed"])
    ci7 = mbb_interval(endpoint_values, block_days=inf["sensitivity_block_days"], replicates=inf["moving_block_bootstrap_replicates"], seed=inf["bootstrap_seed"])
    if aborted > int(cfg["date_health"]["maximum_aborted_or_missing_dates_before_operational_kill"]):
        decision = "CLOSE_OPERATIONAL_RELIABILITY"
    elif k < int(cfg["evaluation"]["recurrence_gate_minimum_qualifying_dates"]):
        decision = "CLOSE_NO_RECURRENT_EDGE"
    else:
        decision = "SURVIVES_RECURRENCE_GATE_PENDING_SHADOW_EXECUTION_VALIDATION"

    result = {
        "protocol_id": cfg["protocol_id"],
        "planned_dates": n,
        "qualifying_dates": k,
        "primary_proportion": rate,
        "aborted_missing_or_integrity_failed_dates": aborted,
        "mbb_3day_95pct": ci3,
        "mbb_7day_95pct_sensitivity": ci7,
        "decision": decision,
        "date_results": date_rows,
        "execution_claim": False,
    }
    write_result(out, result)
    print(json.dumps({k: result[k] for k in ("planned_dates", "qualifying_dates", "primary_proportion", "aborted_missing_or_integrity_failed_dates", "decision")}, indent=2))
    print(f"result={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
