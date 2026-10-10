"""Frozen V3 Study 1 collection/evaluation helpers.

The daily collector is result-blind: it records only the frozen inputs required
for endpoint evaluation. The endpoint evaluator is frozen before collection and
must not run before the final planned session ends.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import date, datetime, time as dtime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from src.v3.study1.confirmatory import conservative_cost

FROZEN_CONFIG_REL = Path("configs/v3/study1_confirmatory_frozen.json")
FREEZE_MANIFEST_REL = Path("configs/v3/study1_freeze_manifest.json")
FROZEN_VERSION = "v3_s1_frozen_2026-10-06_r1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_frozen_config(root: Path) -> dict[str, Any]:
    cfg = json.loads((root / FROZEN_CONFIG_REL).read_text(encoding="utf-8"))
    if cfg.get("status") != "FINAL_FROZEN_CONFIRMATORY_NOT_STARTED":
        raise RuntimeError("frozen Study 1 config has unexpected status")
    dates = cfg.get("evaluation", {}).get("planned_dates") or []
    if len(dates) != 30 or len(set(dates)) != 30:
        raise RuntimeError("frozen Study 1 planned date list must contain 30 unique dates")
    return cfg


def verify_freeze_manifest(root: Path) -> dict[str, Any]:
    path = root / FREEZE_MANIFEST_REL
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cfg = json.loads((root / FROZEN_CONFIG_REL).read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("protocol_id") != cfg.get("protocol_id"):
        errors.append("protocol_id")
    if manifest.get("freeze_parent_commit") != cfg.get("freeze_parent_commit"):
        errors.append("freeze_parent_commit")
    seen: set[str] = set()
    rows = manifest.get("core_files", [])
    if not isinstance(rows, list) or not rows:
        errors.append("core_files")
        rows = []
    for row in rows:
        rel = str(row.get("path", ""))
        if not rel or rel in seen:
            errors.append(f"duplicate_or_empty:{rel}")
            continue
        seen.add(rel)
        p = root / rel
        if not p.is_file():
            errors.append(f"missing:{rel}")
            continue
        data = p.read_bytes()
        got = hashlib.sha256(data).hexdigest()
        if got != row.get("sha256"):
            errors.append(f"sha256:{rel}:{got}!={row.get('sha256')}")
        if len(data) != int(row.get("bytes", -1)):
            errors.append(f"bytes:{rel}:{len(data)}!={row.get('bytes')}")
    if errors:
        raise RuntimeError("freeze manifest verification failed: " + "; ".join(errors))
    return {"manifest": manifest, "manifest_sha256": sha256_file(path)}


def planned_dates(cfg: dict[str, Any]) -> list[str]:
    return list(cfg["evaluation"]["planned_dates"])


def session_bounds(event_date: date, cfg: dict[str, Any]) -> tuple[datetime, datetime]:
    tz = ZoneInfo(cfg["session_timezone"])
    start_t = dtime.fromisoformat(cfg["session_start"])
    end_t = dtime.fromisoformat(cfg["session_end_exclusive"])
    return datetime.combine(event_date, start_t, tzinfo=tz), datetime.combine(event_date, end_t, tzinfo=tz)


def pair_id(city_id: str, lower_threshold: Any, lower_yes_conid: int, higher_no_conid: int) -> str:
    return f"{city_id}|{Decimal(str(lower_threshold)).normalize()}|{int(lower_yes_conid)}|{int(higher_no_conid)}"


def expected_pair_specs(ladders: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the frozen identity schema for every adjacent pair.

    The sealed endpoint input is self-audited, so pair_id membership alone is not
    enough: redundant city/threshold/conid fields must agree with the frozen
    ladder before any record can be interpreted as market evidence.
    """
    out: dict[str, dict[str, Any]] = {}
    for city_id, ladder in ladders.items():
        for p in ladder["adjacent_pairs"]:
            pid = pair_id(city_id, p["lower_threshold"], p["lower_yes_conid"], p["higher_no_conid"])
            if pid in out:
                raise RuntimeError("semantic ladder contains duplicate pair_id")
            out[pid] = {
                "city_id": str(city_id),
                "lower_threshold": Decimal(str(p["lower_threshold"])).normalize(),
                "higher_threshold": Decimal(str(p["higher_threshold"])).normalize(),
                "lower_yes_conid": int(p["lower_yes_conid"]),
                "higher_no_conid": int(p["higher_no_conid"]),
            }
    return out


def expected_pair_ids(ladders: dict[str, Any]) -> set[str]:
    return set(expected_pair_specs(ladders))


def maximum_consecutive_true(values: Iterable[bool]) -> int:
    best = cur = 0
    for v in values:
        if v:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def mbb_interval(values: list[int], *, block_days: int, replicates: int, seed: int) -> list[float] | None:
    if not values or all(v == values[0] for v in values):
        return None
    n = len(values)
    b = max(1, min(int(block_days), n))
    starts = list(range(0, n - b + 1))
    rng = random.Random(seed + b)
    stats: list[float] = []
    for _ in range(int(replicates)):
        sample: list[int] = []
        while len(sample) < n:
            s = rng.choice(starts)
            sample.extend(values[s:s+b])
        sample = sample[:n]
        stats.append(sum(sample) / n)
    stats.sort()
    lo = stats[int(0.025 * (len(stats) - 1))]
    hi = stats[int(0.975 * (len(stats) - 1))]
    return [lo, hi]


def endpoint_unlock_time(cfg: dict[str, Any]) -> datetime:
    last = date.fromisoformat(planned_dates(cfg)[-1])
    _, end = session_bounds(last, cfg)
    return end.astimezone(timezone.utc)


def _row_asks(snapshot: dict[str, Any]) -> tuple[Decimal, Decimal]:
    rows = snapshot["rows"]
    return Decimal(rows[0]["ask"]), Decimal(rows[1]["ask"])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_day_health_summary(path: Path, *, event_date: str, cfg: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Read one day-health file without letting corruption crash endpoint classification.

    Returns ``(health, None)`` for a structurally readable summary, otherwise
    ``(None, reason)``. Missing/corrupt health is an integrity/operational
    failure retained in the denominator; a readable semantic blocker is still
    handled by the endpoint before any opportunity calculation.
    """
    if not path.is_file():
        return None, "missing day_health_summary.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, "day_health_summary.json must contain a JSON object"
    if payload.get("protocol_id") != cfg["protocol_id"]:
        return None, "day health protocol_id mismatch"
    if payload.get("event_date") != event_date:
        return None, "day health event_date mismatch"
    # A readable semantic/terms blocker for the exact frozen protocol/date has
    # priority over ordinary health-schema defects. Preserve it so the endpoint
    # can close the study before any opportunity calculation.
    blocker = payload.get("study_blocker")
    if blocker not in (None, ""):
        if not isinstance(blocker, str):
            return None, "day health study_blocker must be a string when present"
        return payload, None

    # Validate type before set membership: JSON arrays/objects are unhashable
    # and must become date-level integrity failures rather than crashing the
    # endpoint process.
    status = payload.get("date_status")
    if not isinstance(status, str):
        return None, f"day health date_status must be a string: {status!r}"
    if status not in {"VALID", "ABORTED_RETAIN_IN_DENOMINATOR", "STUDY_BLOCKER"}:
        return None, f"unknown day health date_status: {status!r}"
    return payload, None


def validate_valid_date_health(
    health: dict[str, Any],
    *,
    cfg: dict[str, Any],
    event_date: str,
    slots: int,
    normal_count: int,
    total_invalid: int,
    max_consecutive_invalid: int,
) -> None:
    """Independently enforce frozen date-health eligibility for a claimed VALID date."""
    if health.get("date_status") != "VALID":
        raise RuntimeError("valid-day audit requires date_status=VALID")
    if health.get("protocol_id") != cfg["protocol_id"] or health.get("event_date") != event_date:
        raise RuntimeError("day health identity does not match frozen protocol/date")
    if health.get("study_blocker") not in (None, ""):
        raise RuntimeError("VALID day cannot contain study_blocker")
    if int(health.get("nominal_slots", -1)) != slots:
        raise RuntimeError("health nominal slot count disagrees with frozen configuration")
    if int(health.get("observed_or_accounted_slots", -1)) != slots:
        raise RuntimeError("VALID day does not account for every frozen nominal slot")
    if normal_count != int(health.get("normal_slots", -1)):
        raise RuntimeError("health normal slot count disagrees with slot ledger")
    if total_invalid != int(health.get("structural_invalid_slots", -1)):
        raise RuntimeError("health invalid slot count disagrees with slot ledger")
    if max_consecutive_invalid != int(health.get("max_consecutive_structural_invalid_slots", -1)):
        raise RuntimeError("health consecutive-invalid count disagrees with slot ledger")
    if health.get("terminal_failure") not in (None, ""):
        raise RuntimeError("VALID day contains terminal_failure")

    dh = cfg["date_health"]
    if normal_count < int(dh["minimum_normal_slots"]):
        raise RuntimeError("VALID day violates minimum_normal_slots")
    if total_invalid > int(dh["maximum_total_invalid_slots"]):
        raise RuntimeError("VALID day violates maximum_total_invalid_slots")
    if max_consecutive_invalid > int(dh["maximum_consecutive_invalid_slots"]):
        raise RuntimeError("VALID day violates maximum_consecutive_invalid_slots")


def audit_valid_day_inputs(
    day: Path,
    *,
    event_date: str,
    cfg: dict[str, Any],
    health: dict[str, Any],
    ladders: dict[str, Any],
    records: list[dict[str, Any]],
    manifest_sha256: str,
) -> set[int]:
    """Verify sealed-input integrity and return globally NORMAL slot indices.

    A date already labelled VALID must have complete ledgers and pair coverage.
    Structural-invalid slots are never usable for confirmation even if some pair
    quotes were recorded before another pair made that slot invalid.
    """
    required = ["run_identity.json", "slot_health.jsonl", "terms_manifest.json", "trading_schedules.json"]
    for name in required:
        if not (day / name).is_file():
            raise RuntimeError(f"valid date missing required file: {name}")

    run_identity = json.loads((day / "run_identity.json").read_text(encoding="utf-8"))
    if run_identity.get("protocol_id") != cfg["protocol_id"] or run_identity.get("event_date") != event_date:
        raise RuntimeError("run identity does not match frozen protocol/date")
    if run_identity.get("freeze_manifest_sha256") != manifest_sha256:
        raise RuntimeError("run identity freeze manifest hash mismatch")

    sealed = day / cfg["result_firewall"]["sealed_input_file"]
    if not sealed.is_file() or health.get("sealed_input_sha256") != sha256_file(sealed):
        raise RuntimeError("sealed input missing or SHA256 mismatch")

    slot_rows = read_jsonl(day / "slot_health.jsonl")
    slots = int(cfg["nominal_slots_per_date"])
    if len(slot_rows) != slots:
        raise RuntimeError(f"slot ledger must contain exactly {slots} rows")
    by_slot: dict[int, dict[str, Any]] = {}
    for row in slot_rows:
        idx = int(row.get("slot_index", -1))
        if idx in by_slot or idx < 0 or idx >= slots:
            raise RuntimeError("slot ledger contains duplicate/out-of-range slot")
        by_slot[idx] = row
    if set(by_slot) != set(range(slots)):
        raise RuntimeError("slot ledger does not cover the frozen nominal grid")

    expected_specs = expected_pair_specs(ladders)
    expected = set(expected_specs)
    if not expected:
        raise RuntimeError("semantic ladder contains no adjacent pairs")
    rec_by_slot: dict[int, dict[str, dict[str, Any]]] = {i: {} for i in range(slots)}
    for rec in records:
        idx = int(rec.get("slot_index", -1))
        pid = str(rec.get("pair_id", ""))
        if idx < 0 or idx >= slots or pid not in expected:
            raise RuntimeError("sealed input contains unknown slot/pair")
        if pid in rec_by_slot[idx]:
            raise RuntimeError("sealed input contains duplicate slot/pair record")

        spec = expected_specs[pid]
        if rec.get("city_id") != spec["city_id"]:
            raise RuntimeError("sealed input city_id does not match frozen pair mapping")
        try:
            lower_threshold = Decimal(str(rec["lower_threshold"])).normalize()
            higher_threshold = Decimal(str(rec["higher_threshold"])).normalize()
            lower_yes_conid = int(rec["lower_yes_conid"])
            higher_no_conid = int(rec["higher_no_conid"])
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise RuntimeError("sealed input pair identity fields are missing/invalid") from exc
        if (
            lower_threshold != spec["lower_threshold"]
            or higher_threshold != spec["higher_threshold"]
            or lower_yes_conid != spec["lower_yes_conid"]
            or higher_no_conid != spec["higher_no_conid"]
        ):
            raise RuntimeError("sealed input pair identity fields disagree with frozen ladder")
        rec_by_slot[idx][pid] = rec

    d = date.fromisoformat(event_date)
    start_dt, end_dt = session_bounds(d, cfg)
    start_epoch, end_epoch = start_dt.timestamp(), end_dt.timestamp()
    normal_slots: set[int] = set()
    normal_count = 0
    invalid_flags: list[bool] = []
    for idx in range(slots):
        row = by_slot[idx]
        status = row.get("status")
        seen = rec_by_slot[idx]
        if int(row.get("expected_pair_records", -1)) != len(expected):
            raise RuntimeError("slot ledger expected pair count mismatch")
        if int(row.get("observed_pair_records", -1)) != len(seen):
            raise RuntimeError("slot ledger observed pair count mismatch")
        if status == "NORMAL":
            if set(seen) != expected:
                raise RuntimeError("NORMAL slot lacks complete frozen pair coverage")
            for rec in seen.values():
                quote_status = rec.get("quote_status")
                if quote_status not in {"QUOTE_ELIGIBLE", "QUOTE_UNAVAILABLE"}:
                    raise RuntimeError("NORMAL slot contains missing/unknown quote_status")

                try:
                    rs = float(rec["request_start_epoch"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise RuntimeError("NORMAL slot record lacks valid request_start_epoch") from exc
                if not math.isfinite(rs) or not (start_epoch <= rs < end_epoch):
                    raise RuntimeError("NORMAL slot record request lies outside frozen session bounds")

                if quote_status == "QUOTE_ELIGIBLE":
                    if rec.get("failure_class") not in (None, "") or rec.get("reason") not in (None, ""):
                        raise RuntimeError("QUOTE_ELIGIBLE record conflicts with failure fields")
                    try:
                        rr = float(rec["response_received_epoch"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise RuntimeError("eligible quote lacks valid response_received_epoch") from exc
                    if not math.isfinite(rr) or not (start_epoch <= rr < end_epoch and rr >= rs):
                        raise RuntimeError("eligible quote lies outside frozen session bounds")
                    snapshot = rec.get("snapshot")
                    if not isinstance(snapshot, dict):
                        raise RuntimeError("eligible quote lacks snapshot object")
                    rows = snapshot.get("rows")
                    if not isinstance(rows, list) or len(rows) != 2:
                        raise RuntimeError("eligible quote snapshot must contain exactly two rows")
                    spec = expected_specs[rec["pair_id"]]
                    expected_snapshot_conids = [spec["lower_yes_conid"], spec["higher_no_conid"]]
                    observed_snapshot_conids: list[int] = []
                    for snap_row in rows:
                        if not isinstance(snap_row, dict) or "conid" not in snap_row or "ask" not in snap_row:
                            raise RuntimeError("eligible quote snapshot row missing required conid/ask")
                        try:
                            observed_snapshot_conids.append(int(snap_row["conid"]))
                            ask = Decimal(str(snap_row["ask"]))
                        except Exception as exc:
                            raise RuntimeError("eligible quote snapshot contains invalid conid/ask") from exc
                        if not ask.is_finite():
                            raise RuntimeError("eligible quote snapshot contains non-finite ask")
                    if observed_snapshot_conids != expected_snapshot_conids:
                        raise RuntimeError("eligible quote snapshot conids/order disagree with frozen pair")
                else:
                    if rec.get("failure_class") != "quote_unavailable":
                        raise RuntimeError("QUOTE_UNAVAILABLE record lacks quote_unavailable failure_class")
                    if not isinstance(rec.get("reason"), str) or not rec.get("reason", "").strip():
                        raise RuntimeError("QUOTE_UNAVAILABLE record lacks failure reason")
            normal_slots.add(idx)
            normal_count += 1
            invalid_flags.append(False)
        elif status in {"STRUCTURAL_INVALID", "MISSED_LATE_START", "MISSED_AFTER_SESSION_END"}:
            invalid_flags.append(True)
        else:
            raise RuntimeError(f"unknown slot status: {status}")

    total_invalid = slots - normal_count
    max_consecutive_invalid = maximum_consecutive_true(invalid_flags)
    validate_valid_date_health(
        health,
        cfg=cfg,
        event_date=event_date,
        slots=slots,
        normal_count=normal_count,
        total_invalid=total_invalid,
        max_consecutive_invalid=max_consecutive_invalid,
    )
    return normal_slots


def evaluate_city_date(
    records: list[dict[str, Any]],
    *,
    city_id: str,
    ladder: dict[str, Any],
    cfg: dict[str, Any],
    valid_slot_indices: set[int],
) -> dict[str, Any] | None:
    """Return deterministic first qualifying basket using only globally valid slots."""
    pair_meta = {}
    threshold_by_value = {str(Decimal(str(x["threshold"])).normalize()): x for x in ladder["thresholds"]}
    for p in ladder["adjacent_pairs"]:
        pid = pair_id(city_id, p["lower_threshold"], p["lower_yes_conid"], p["higher_no_conid"])
        lower = threshold_by_value[str(Decimal(str(p["lower_threshold"])).normalize())]
        pair_meta[pid] = {**p, "payout_time": lower["payout_time"]}

    grouped: dict[str, dict[int, dict[str, Any]]] = {}
    for rec in records:
        idx = int(rec.get("slot_index", -1))
        if idx not in valid_slot_indices:
            continue
        pid = str(rec.get("pair_id", ""))
        rec_city = rec.get("city_id")
        # Defensive guard even if the global day audit was bypassed: a record
        # claiming this city's frozen pair may never be filtered away because
        # its city_id is missing or contradictory.
        if pid in pair_meta:
            if rec_city != city_id:
                raise RuntimeError("valid-slot record city_id conflicts with frozen pair mapping")
        elif rec_city == city_id:
            raise RuntimeError("valid-slot record claims city with non-frozen pair_id")
        else:
            continue
        quote_status = rec.get("quote_status")
        if quote_status not in {"QUOTE_ELIGIBLE", "QUOTE_UNAVAILABLE"}:
            raise RuntimeError("valid-slot record contains missing/unknown quote_status")
        if quote_status == "QUOTE_ELIGIBLE" and (rec.get("failure_class") not in (None, "") or rec.get("reason") not in (None, "")):
            raise RuntimeError("QUOTE_ELIGIBLE record conflicts with failure fields")
        if quote_status == "QUOTE_UNAVAILABLE":
            continue
        grouped.setdefault(pid, {})[idx] = rec

    cost_cfg = cfg["cost"]
    for slot in range(1, int(cfg["nominal_slots_per_date"])):
        if slot not in valid_slot_indices or slot - 1 not in valid_slot_indices:
            continue
        confirmed = []
        for pid, slots in grouped.items():
            if slot - 1 not in slots or slot not in slots or pid not in pair_meta:
                continue
            a, b = slots[slot - 1], slots[slot]
            delta = float(b["request_start_epoch"]) - float(a["request_start_epoch"])
            if delta < float(cfg["revalidation"]["minimum_elapsed_seconds"]) or delta > float(cfg["revalidation"]["maximum_elapsed_seconds"]):
                continue
            lower1, higher1 = _row_asks(a["snapshot"])
            lower2, higher2 = _row_asks(b["snapshot"])
            payout_epoch = float(pair_meta[pid]["payout_time"])
            seconds_to_payout = max(0.0, payout_epoch - float(b["request_start_epoch"]))
            cost = conservative_cost(
                lower_ask_t1=lower1, lower_ask_t2=lower2,
                higher_no_ask_t1=higher1, higher_no_ask_t2=higher2,
                broker_fee_per_contract=cost_cfg["broker_fee_per_contract_usd"],
                exchange_fee_per_contract=cost_cfg["exchange_fee_per_contract_usd"],
                tick_reserve_per_leg=cost_cfg["tick_reserve_per_leg_usd"],
                annual_funding_rate=cost_cfg["annual_funding_rate"],
                seconds_to_payout=seconds_to_payout,
            )
            if cost["total_rounded"] <= Decimal(cost_cfg["qualification_ceiling_usd"]):
                meta = pair_meta[pid]
                confirmed.append((Decimal(str(meta["lower_threshold"])), int(meta["lower_yes_conid"]), pid, a, b, cost))
        if confirmed:
            confirmed.sort(key=lambda x: (x[0], x[1]))
            _, _, pid, a, b, cost = confirmed[0]
            meta = pair_meta[pid]
            return {
                "city_id": city_id,
                "confirmation_slot": slot,
                "pair_id": pid,
                "lower_threshold": meta["lower_threshold"],
                "higher_threshold": meta["higher_threshold"],
                "lower_yes_conid": meta["lower_yes_conid"],
                "higher_no_conid": meta["higher_no_conid"],
                "total_cost_rounded": str(cost["total_rounded"]),
                "funding": str(cost["funding"]),
                "t1_request_start_epoch": a["request_start_epoch"],
                "t2_request_start_epoch": b["request_start_epoch"],
            }
    return None
