#!/usr/bin/env python3
"""Frozen result-blind daily collector for V3 Study 1.

This script never computes basket cost, opportunity flags, candidate counts,
alpha, hypothetical fills, or PnL. It writes the frozen inputs required by the
endpoint evaluator after the 30-date window closes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.v3.audit.ibkr_capability import MARKET_DATA_FIELDS
from src.v3.ibkr.client import IBKRAPIError, IBKRClient
from src.v3.study1.confirmatory import (
    PRODUCTS,
    ConfirmatoryEligibilityError,
    StudyBlockerError,
    acquire_event_ladder,
    archive_terms,
    best_ntp_offset,
    discover_fixed_markets,
    snapshot_failure_class,
    validate_pair_snapshot,
    validate_schedule_open,
    verify_terms_archive,
    write_json,
)
from src.v3.study1.frozen import (
    load_frozen_config,
    maximum_consecutive_true,
    pair_id,
    planned_dates,
    session_bounds,
    sha256_file,
    verify_freeze_manifest,
)


def auth_ready(client: IBKRClient) -> bool:
    auth = client.auth_status()
    status = auth.get("success", {}).get("value", {}) if isinstance(auth, dict) else {}
    if not status and isinstance(auth, dict):
        status = auth
    return bool(status.get("authenticated") and status.get("established") and status.get("connected") and not status.get("competing"))


def append_jsonl(path: Path, rec: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
        f.flush()


def main() -> int:
    p = argparse.ArgumentParser(description="Frozen result-blind V3 Study 1 daily collector.")
    p.add_argument("--event-date", required=True)
    p.add_argument("--base-url", default="https://localhost:5001/v1/api")
    p.add_argument("--output-root", default="local_artifacts/v3_study1_confirmatory")
    args = p.parse_args()

    cfg = load_frozen_config(ROOT)
    freeze_state = verify_freeze_manifest(ROOT)
    target = date.fromisoformat(args.event_date)
    if target.isoformat() not in planned_dates(cfg):
        raise SystemExit("STOP: event date is not in the frozen 30-date schedule")

    frozen_terms = ROOT / cfg["terms"]["frozen_pdf_path"]
    if not frozen_terms.is_file() or sha256_file(frozen_terms) != cfg["terms"]["sha256"]:
        raise SystemExit("STOP: local frozen terms artifact missing or hash mismatch")

    out = Path(args.output_root) / target.isoformat()
    if out.exists():
        raise SystemExit(f"STOP: frozen date directory already exists; no retry/overwrite: {out}")
    out.mkdir(parents=True)
    write_json(out / "run_identity.json", {
        "protocol_id": cfg["protocol_id"],
        "event_date": target.isoformat(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "freeze_manifest_sha256": freeze_state["manifest_sha256"],
        "frozen_config_sha256": sha256_file(ROOT / "configs/v3/study1_confirmatory_frozen.json"),
        "frozen_terms_sha256": cfg["terms"]["sha256"],
    })

    obs_path = out / cfg["result_firewall"]["sealed_input_file"]
    slot_path = out / "slot_health.jsonl"
    terminal_failure: str | None = None
    study_blocker: str | None = None
    structural_slots: list[bool] = []
    normal_slots = 0
    total_quote_unavailable = 0
    expected_pair_count = 0

    try:
        client = IBKRClient(base_url=args.base_url)
        if not auth_ready(client):
            raise ConfirmatoryEligibilityError("gateway authentication/readiness failed")
        client.accounts(); client.tickle()

        clock = best_ntp_offset()
        write_json(out / "clock_health.json", clock)
        if not clock.get("ok") or abs(float(clock.get("offset_seconds"))) > float(cfg["quote_readiness"]["max_clock_offset_seconds"]):
            raise ConfirmatoryEligibilityError("host clock failed frozen offset bound")

        fixed = discover_fixed_markets(client)
        ladders: dict[str, dict] = {}
        schedules: dict[str, dict] = {}
        terms_urls: set[str] = set()
        for spec in PRODUCTS:
            payload = fixed[spec.city_id].get("market") or {}
            ladder = acquire_event_ladder(client, spec, payload, target)
            ladders[spec.city_id] = ladder
            for row in ladder["thresholds"]:
                url = str(row.get("market_rules_link") or "")
                if not url:
                    raise StudyBlockerError("event-date threshold missing market_rules_link")
                terms_urls.add(url)
            rep = int(ladder["thresholds"][0]["yes_conid"])
            schedules[spec.city_id] = client.contract_schedules(rep)

        if terms_urls != {cfg["terms"]["source_url"]}:
            raise StudyBlockerError(f"runtime terms URLs differ from frozen source: {sorted(terms_urls)}")

        write_json(out / "semantic_ladder_audit.json", ladders)
        write_json(out / "trading_schedules.json", schedules)
        terms_record = archive_terms(cfg["terms"]["source_url"], out / "terms")
        verify_terms_archive(terms_record, expected_url=cfg["terms"]["source_url"], expected_sha256=cfg["terms"]["sha256"])
        write_json(out / "terms_manifest.json", [terms_record])

        pair_plan: list[tuple[str, dict]] = []
        all_conids: set[int] = set()
        for spec in PRODUCTS:
            for pair in ladders[spec.city_id]["adjacent_pairs"]:
                pair_plan.append((spec.city_id, pair))
                all_conids.update((int(pair["lower_yes_conid"]), int(pair["higher_no_conid"])))
        expected_pair_count = len(pair_plan)
        if expected_pair_count <= 0:
            raise StudyBlockerError("frozen universe produced no adjacent pairs")

        for i in range(0, len(all_conids), 8):
            client.marketdata_snapshot(sorted(all_conids)[i:i+8], fields=list(MARKET_DATA_FIELDS))
        time.sleep(0.75)

        start_dt, end_dt = session_bounds(target, cfg)
        start_epoch, end_epoch = start_dt.timestamp(), end_dt.timestamp()
        cadence = float(cfg["cadence_seconds"])
        tolerance = float(cfg["slot_start_lateness_tolerance_seconds"])
        slots = int(cfg["nominal_slots_per_date"])
        last_tickle = time.monotonic()
        last_auth = time.monotonic()

        while time.time() < start_epoch:
            if time.monotonic() - last_tickle >= 60:
                client.tickle(); last_tickle = time.monotonic()
            if time.monotonic() - last_auth >= 300:
                if not auth_ready(client):
                    raise ConfirmatoryEligibilityError("authentication lost before session start")
                last_auth = time.monotonic()
            time.sleep(min(1.0, max(0.05, start_epoch - time.time())))

        for slot in range(slots):
            due = start_epoch + slot * cadence
            while time.time() < due:
                time.sleep(min(0.25, due - time.time()))
            actual_start = time.time()
            if actual_start >= end_epoch:
                structural_slots.append(True)
                append_jsonl(slot_path, {
                    "slot_index": slot, "nominal_epoch": due, "status": "MISSED_AFTER_SESSION_END",
                    "expected_pair_records": expected_pair_count, "observed_pair_records": 0,
                })
                continue
            if actual_start - due > tolerance:
                structural_slots.append(True)
                append_jsonl(slot_path, {
                    "slot_index": slot, "nominal_epoch": due, "status": "MISSED_LATE_START",
                    "lateness_seconds": actual_start - due,
                    "expected_pair_records": expected_pair_count, "observed_pair_records": 0,
                })
                continue

            if time.monotonic() - last_tickle >= 60:
                try: client.tickle()
                except IBKRAPIError: pass
                last_tickle = time.monotonic()
            if time.monotonic() - last_auth >= 300:
                if not auth_ready(client):
                    raise ConfirmatoryEligibilityError("authentication lost during frozen session")
                last_auth = time.monotonic()

            slot_structural = False
            slot_unavailable = 0
            observed_pair_records = 0

            city_schedule_error: dict[str, str] = {}
            for city_id, schedule in schedules.items():
                try:
                    validate_schedule_open(schedule, now_epoch=actual_start)
                except ConfirmatoryEligibilityError as exc:
                    city_schedule_error[city_id] = str(exc)
                    slot_structural = True

            for city_id, pair in pair_plan:
                expected = (int(pair["lower_yes_conid"]), int(pair["higher_no_conid"]))
                pid = pair_id(city_id, pair["lower_threshold"], expected[0], expected[1])
                base = {
                    "slot_index": slot, "nominal_epoch": due, "city_id": city_id, "pair_id": pid,
                    "lower_threshold": pair["lower_threshold"], "higher_threshold": pair["higher_threshold"],
                    "lower_yes_conid": expected[0], "higher_no_conid": expected[1],
                }
                if city_id in city_schedule_error:
                    append_jsonl(obs_path, {**base, "request_start_epoch": time.time(), "quote_status": "STRUCTURAL_FAILURE",
                                            "failure_class": "structural_failure", "reason": city_schedule_error[city_id]})
                    observed_pair_records += 1
                    continue

                request_start_epoch = time.time()
                if request_start_epoch >= end_epoch:
                    append_jsonl(obs_path, {**base, "request_start_epoch": request_start_epoch, "quote_status": "STRUCTURAL_FAILURE",
                                            "failure_class": "structural_failure", "reason": "pair request started outside frozen session"})
                    slot_structural = True; observed_pair_records += 1
                    continue
                try:
                    validate_schedule_open(schedules[city_id], now_epoch=request_start_epoch)
                    t0 = time.monotonic()
                    payload = client.marketdata_snapshot(expected, fields=list(MARKET_DATA_FIELDS))
                    elapsed = time.monotonic() - t0
                    received = time.time()
                    if received >= end_epoch:
                        raise ConfirmatoryEligibilityError("pair response received outside frozen session")
                    checked = validate_pair_snapshot(
                        payload,
                        expected_conids=expected,
                        request_elapsed_seconds=elapsed,
                        response_received_epoch=received,
                        max_request_elapsed_seconds=float(cfg["quote_readiness"]["max_request_elapsed_seconds"]),
                        max_broker_future_seconds=float(cfg["quote_readiness"]["max_broker_future_seconds"]),
                        minimum_valid_broker_epoch_ms=int(cfg["quote_readiness"]["minimum_valid_broker_epoch_ms"]),
                    )
                    append_jsonl(obs_path, {**base, "request_start_epoch": request_start_epoch,
                                            "response_received_epoch": received, "quote_status": "QUOTE_ELIGIBLE",
                                            "snapshot": checked})
                except (ConfirmatoryEligibilityError, IBKRAPIError) as exc:
                    cls = snapshot_failure_class(exc) if isinstance(exc, ConfirmatoryEligibilityError) else "structural_failure"
                    status = "QUOTE_UNAVAILABLE" if cls == "quote_unavailable" else "STRUCTURAL_FAILURE"
                    if cls == "quote_unavailable":
                        slot_unavailable += 1; total_quote_unavailable += 1
                    else:
                        slot_structural = True
                    append_jsonl(obs_path, {**base, "request_start_epoch": request_start_epoch,
                                            "quote_status": status, "failure_class": cls, "reason": str(exc)})
                observed_pair_records += 1

            if observed_pair_records != expected_pair_count:
                slot_structural = True
            structural_slots.append(slot_structural)
            if not slot_structural:
                normal_slots += 1
            append_jsonl(slot_path, {
                "slot_index": slot, "nominal_epoch": due,
                "status": "STRUCTURAL_INVALID" if slot_structural else "NORMAL",
                "quote_unavailable_pairs": slot_unavailable,
                "expected_pair_records": expected_pair_count,
                "observed_pair_records": observed_pair_records,
            })

    except StudyBlockerError as exc:
        study_blocker = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        terminal_failure = f"{type(exc).__name__}: {exc}"

    total_invalid = len(structural_slots) - normal_slots
    max_consecutive = maximum_consecutive_true(structural_slots)
    if study_blocker:
        date_status = "STUDY_BLOCKER"
    elif terminal_failure or len(structural_slots) != int(cfg["nominal_slots_per_date"]) or normal_slots < int(cfg["date_health"]["minimum_normal_slots"]) or total_invalid > int(cfg["date_health"]["maximum_total_invalid_slots"]) or max_consecutive > int(cfg["date_health"]["maximum_consecutive_invalid_slots"]):
        date_status = "ABORTED_RETAIN_IN_DENOMINATOR"
    else:
        date_status = "VALID"

    summary = {
        "protocol_id": cfg["protocol_id"], "event_date": target.isoformat(), "date_status": date_status,
        "nominal_slots": int(cfg["nominal_slots_per_date"]), "observed_or_accounted_slots": len(structural_slots),
        "normal_slots": normal_slots, "structural_invalid_slots": total_invalid,
        "max_consecutive_structural_invalid_slots": max_consecutive,
        "quote_unavailable_pair_observations": total_quote_unavailable,
        "expected_pair_records_per_complete_slot": expected_pair_count,
        "terminal_failure": terminal_failure, "study_blocker": study_blocker,
        "sealed_input_sha256": sha256_file(obs_path) if obs_path.exists() else None,
        "freeze_manifest_sha256": freeze_state["manifest_sha256"],
        "guardrail": "Daily collector did not compute basket cost opportunity candidate count alpha hypothetical fills or PnL.",
    }
    write_json(out / "day_health_summary.json", summary)
    print(f"event_date={target.isoformat()}")
    print(f"date_status={date_status}")
    print(f"normal_slots={normal_slots}/{cfg['nominal_slots_per_date']}")
    print(f"structural_invalid_slots={total_invalid}")
    print(f"study_blocker={study_blocker}")
    print(f"terminal_failure={terminal_failure}")
    print(f"output_dir={out}")
    print("result_firewall=PASS:no_cost_or_opportunity_computation")
    if study_blocker:
        return 3
    return 0 if terminal_failure is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
