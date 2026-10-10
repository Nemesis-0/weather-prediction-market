"""Frozen prospective fast economic kill screen for V3 Study 2.

This module evaluates EVERY fresh displayed executable ask in a read-only
Study 2 capture session. It does not place orders, size positions, retune M0,
retune support rules, or select only favorable rows.

Positive conservative margin is only an *apparently positive candidate* and
requires Sol Max Gate #3 before any shadow/freeze progression. A session with
no positive rows is not by itself a universal ECONOMIC_KILL across all future
market states.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from src.v3.study2.m0 import BASE_FEATURES, MIN_SCALE_F
from src.v3.study2.support_calibration import _q_bin_label, _survival_probability

ECON_PROTOCOL_ID = "v3_study2_economic_kill_frozen_2026-10-07_r1"
ECON_VERSION = "v3_s2_fast_economic_kill_1"
CHICAGO = ZoneInfo("America/Chicago")


class EconomicKillError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise EconomicKillError(f"expected JSON object: {path}")
    return obj


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            out.append(obj)
    return out


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise EconomicKillError(f"timestamp lacks timezone: {value}")
    return dt.astimezone(timezone.utc)


def _month_candidates(ref_utc: datetime) -> list[tuple[int, int]]:
    # Robust across UTC/local month boundaries: search previous/current/next month.
    base = ref_utc.date().replace(day=15)
    out: list[tuple[int, int]] = []
    for delta in (-40, 0, 40):
        d = base + timedelta(days=delta)
        key = (d.year, d.month)
        if key not in out:
            out.append(key)
    return out


_METAR_TIME_RE = re.compile(r"\b(\d{2})(\d{2})(\d{2})Z\b")


def resolve_metar_issue_utc(metar: str, *, reference_utc: datetime) -> datetime:
    m = _METAR_TIME_RE.search(metar or "")
    if not m:
        raise EconomicKillError(f"METAR missing DDHHMMZ token: {metar!r}")
    dd, hh, mm = map(int, m.groups())
    candidates: list[datetime] = []
    for year, month in _month_candidates(reference_utc):
        try:
            candidates.append(datetime(year, month, dd, hh, mm, tzinfo=timezone.utc))
        except ValueError:
            continue
    if not candidates:
        raise EconomicKillError(f"cannot resolve METAR issue time: {metar!r}")
    best = min(candidates, key=lambda x: abs((x - reference_utc).total_seconds()))
    if abs((best - reference_utc).total_seconds()) > 45 * 86400:
        raise EconomicKillError(f"METAR issue time implausibly far from quote: {metar!r}")
    return best


def _latest_versions_asof(
    observations: list[dict[str, Any]],
    *,
    quote_utc: datetime,
) -> list[tuple[datetime, float]]:
    # Prospective point-in-time rule:
    # 1) record must actually have been received by quote time;
    # 2) for each original METAR issue timestamp, use the latest received numeric
    #    version available by quote time (so later COR versions cannot leak backward).
    by_issue: dict[datetime, list[tuple[datetime, float]]] = defaultdict(list)

    for r in observations:
        received_raw = r.get("source_received_utc")
        tmpf = r.get("tmpf")
        metar = str(r.get("metar") or "")
        if not received_raw or tmpf is None or not metar:
            continue
        received = parse_utc(str(received_raw))
        if received > quote_utc:
            continue
        issue = resolve_metar_issue_utc(metar, reference_utc=quote_utc)
        if issue > quote_utc:
            continue
        by_issue[issue].append((received, float(tmpf)))

    resolved: list[tuple[datetime, float]] = []
    for issue, versions in by_issue.items():
        versions.sort(key=lambda x: x[0])
        latest_received = versions[-1][0]
        latest_vals = {v for rec, v in versions if rec == latest_received}
        if len(latest_vals) != 1:
            raise EconomicKillError(
                f"conflicting numeric temperatures at same issue/receipt: {issue.isoformat()}"
            )
        resolved.append((issue, next(iter(latest_vals))))

    resolved.sort(key=lambda x: x[0])
    return resolved


def build_weather_state(
    observations: list[dict[str, Any]],
    *,
    quote_utc: datetime,
    event_date: str,
) -> dict[str, Any] | None:
    known = _latest_versions_asof(observations, quote_utc=quote_utc)
    if not known:
        return None

    local = quote_utc.astimezone(CHICAGO)
    if local.date().isoformat() != event_date:
        return None

    latest_issue, current_temp = known[-1]
    running_max = max(v for _, v in known)
    age_min = (quote_utc - latest_issue).total_seconds() / 60.0
    if age_min < -1e-9:
        raise EconomicKillError("negative observation age")

    cutoff = quote_utc - timedelta(minutes=60)
    refs = [(t, v) for t, v in known if t <= cutoff]
    if refs:
        ref_issue, ref_temp = refs[-1]
        temp_change = current_temp - ref_temp
        ref_age_min = (quote_utc - ref_issue).total_seconds() / 60.0
    else:
        temp_change = None
        ref_age_min = None

    return {
        "event_date": event_date,
        "quote_utc": quote_utc.isoformat(),
        "decision_local": local.isoformat(),
        "local_minute_of_day": local.hour * 60 + local.minute,
        "current_temp_f": current_temp,
        "running_max_f": running_max,
        "temp_minus_running_max_f": current_temp - running_max,
        "observation_age_minutes": age_min,
        "temp_change_60m_f": temp_change,
        "reference_age_minutes": ref_age_min,
        "latest_observation_issue_utc": latest_issue.isoformat(),
        "known_numeric_observation_count": len(known),
    }


def model_feature_vector(state: dict[str, Any]) -> np.ndarray:
    minute = float(state["local_minute_of_day"])
    theta_t = 2.0 * math.pi * minute / 1440.0

    d = datetime.fromisoformat(state["event_date"]).date()
    year_len = 366 if datetime(d.year, 12, 31).date().timetuple().tm_yday == 366 else 365
    season_frac = (d.timetuple().tm_yday - 1) / year_len
    theta_d = 2.0 * math.pi * season_frac

    temp_change = state.get("temp_change_60m_f")
    missing = 1.0 if temp_change is None else 0.0
    filled = 0.0 if temp_change is None else float(temp_change)

    return np.asarray([
        math.sin(theta_t),
        math.cos(theta_t),
        math.sin(theta_d),
        math.cos(theta_d),
        float(state["running_max_f"]),
        float(state["temp_minus_running_max_f"]),
        float(state["observation_age_minutes"]),
        filled,
        missing,
    ], dtype=float)


def load_model(model_path: Path) -> dict[str, Any]:
    model = read_json(model_path)
    if model.get("validation_used") is not False:
        raise EconomicKillError("unexpected M0 model validation flag")
    return model


def load_ecdf(path: Path) -> tuple[np.ndarray, np.ndarray]:
    z: list[float] = []
    w: list[float] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            z.append(float(r["standardized_residual_z"]))
            w.append(float(r["date_balanced_probability_weight"]))
    za = np.asarray(z, dtype=float)
    wa = np.asarray(w, dtype=float)
    if len(za) == 0 or float(wa.sum()) <= 0:
        raise EconomicKillError("invalid calibration ECDF")
    order = np.argsort(za, kind="mergesort")
    return za[order], (wa[order] / wa.sum())


def predict_q(
    *,
    model: dict[str, Any],
    z: np.ndarray,
    zw: np.ndarray,
    state: dict[str, Any],
    threshold_f: float,
) -> dict[str, float]:
    x = model_feature_vector(state)
    mean = np.asarray([model["feature_mean"][k] for k in BASE_FEATURES], dtype=float)
    std = np.asarray([model["feature_std"][k] for k in BASE_FEATURES], dtype=float)
    beta_mu = np.asarray(
        [model["location_intercept"]]
        + [model["location_coefficients_standardized"][k] for k in BASE_FEATURES],
        dtype=float,
    )
    beta_ls = np.asarray(
        [model["log_scale_intercept"]]
        + [model["log_scale_coefficients_standardized"][k] for k in BASE_FEATURES],
        dtype=float,
    )

    xs = (x - mean) / std
    mu = float(beta_mu[0] + xs @ beta_mu[1:])
    scale = max(MIN_SCALE_F, math.exp(float(beta_ls[0] + xs @ beta_ls[1:])))
    delta = float(threshold_f) - float(state["running_max_f"])
    q = _survival_probability(z, zw, (delta - mu) / scale)
    return {"q_hat": q, "mu_f": mu, "scale_f": scale, "delta_f": delta}


def _load_state_support(path: Path) -> dict[tuple[int, str], dict[str, str]]:
    out: dict[tuple[int, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(int(r["month"]), r["local_time_block"])] = r
    return out


def _load_calibration_support(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(r["local_time_block"], r["q_bin"])] = r
    return out


def _block_name(local_minute: int) -> str:
    hour = local_minute // 60
    return ("00-06" if hour < 6 else "06-12" if hour < 12 else "12-18" if hour < 18 else "18-24")


def check_support(
    *,
    state: dict[str, Any],
    q_hat: float,
    delta_f: float,
    state_cells: dict[tuple[int, str], dict[str, str]],
    cal_cells: dict[tuple[str, str], dict[str, str]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    event_month = datetime.fromisoformat(state["event_date"]).month
    block = _block_name(int(state["local_minute_of_day"]))
    cell = state_cells.get((event_month, block))
    if cell is None or cell.get("support_cell_pass") != "True":
        reasons.append("state_support_cell_missing_or_failed")

    max_age = float(policy["future_candidate_support_rule"]["max_observation_age_minutes"])
    if float(state["observation_age_minutes"]) > max_age:
        reasons.append("observation_age_exceeds_frozen_limit")

    if cell is not None:
        feature_map = {
            "running_max_f": state.get("running_max_f"),
            "temp_minus_running_max_f": state.get("temp_minus_running_max_f"),
            "observation_age_minutes": state.get("observation_age_minutes"),
        }
        if state.get("temp_change_60m_f") is None:
            missing_dates = int(cell["temp_change_missing_independent_date_count"])
            min_dates = int(policy["future_candidate_support_rule"]["month_x_local_time_block_cell_min_independent_dates"])
            if missing_dates < min_dates:
                reasons.append("temp_change_missing_without_frozen_support")
        else:
            feature_map["temp_change_60m_f"] = state["temp_change_60m_f"]

        for feat, value in feature_map.items():
            lo = float(cell[f"{feat}_q01"])
            hi = float(cell[f"{feat}_q99"])
            if float(value) < lo or float(value) > hi:
                reasons.append(f"{feat}_outside_frozen_q01_q99")

    dmin, dmax = map(float, policy["future_candidate_support_rule"]["threshold_delta_range_f"])
    if delta_f < dmin or delta_f > dmax:
        reasons.append("threshold_delta_outside_frozen_range")

    qmin, qmax = map(float, policy["future_candidate_support_rule"]["q_hat_range"])
    if q_hat < qmin or q_hat > qmax:
        reasons.append("q_hat_outside_frozen_range")

    qbin = _q_bin_label(q_hat)
    cal = cal_cells.get((block, qbin)) if qbin is not None else None
    if cal is None or cal.get("calibration_cell_pass") != "True":
        reasons.append("calibration_cell_missing_or_failed")
        slack = None
    else:
        slack = float(cal["conservative_probability_slack"])

    return {
        "supported": not reasons,
        "support_reasons": reasons,
        "local_time_block": block,
        "q_bin": qbin,
        "slack": slack,
    }


def _parse_numeric_field(value: Any, *, allow_grouping_commas: bool) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    text = str(value).strip()
    if allow_grouping_commas:
        text = text.replace(",", "")
    try:
        out = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _quote_quality(q: dict[str, Any]) -> tuple[bool, list[str], float | None, float | None]:
    """Validate a displayed executable buy ask.

    ForecastEx side-contract snapshots observed in the accepted collector can be
    one-sided: an ask/ask_size pair may be present while the same row has no bid.
    Therefore availability_decoded.top_of_book (which was false for those
    one-sided rows) is diagnostic metadata, not an eligibility gate.

    Eligibility instead requires:
      * real-time delivery,
      * broker field_presence for ask and ask_size,
      * numeric ask in (0,1),
      * positive numeric ask size.

    IBKR formats sizes with grouping commas (for example "7,520"), which are
    normalized before numeric parsing.
    """
    reasons: list[str] = []
    availability = q.get("availability_decoded") or {}
    if availability.get("delivery") != "real_time":
        reasons.append("not_real_time")

    field_presence = q.get("field_presence") or {}
    if field_presence.get("ask") is not True:
        reasons.append("ask_field_not_present")
    if field_presence.get("ask_size") is not True:
        reasons.append("ask_size_field_not_present")

    ask = _parse_numeric_field(q.get("ask"), allow_grouping_commas=False)
    size = _parse_numeric_field(q.get("ask_size"), allow_grouping_commas=True)

    if ask is None or not (0.0 < ask < 1.0):
        reasons.append("invalid_or_missing_ask")
    if size is None or size <= 0:
        reasons.append("invalid_or_missing_ask_size")

    return not reasons, reasons, ask, size


def screen_session(
    *,
    session_dir: Path,
    pre_eval_dir: Path,
    validation_dir: Path,
    support_dir: Path,
    economic_config_path: Path,
    output_dir: Path,
    protocol_commit_utc: datetime,
) -> dict[str, Any]:
    if output_dir.exists():
        raise EconomicKillError(f"output_dir already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=False)

    config = read_json(economic_config_path)
    if config.get("protocol_id") != ECON_PROTOCOL_ID:
        raise EconomicKillError("unexpected economic protocol config")
    if abs(float(config["total_cost_usd_per_contract"]) - 0.02) > 1e-12:
        raise EconomicKillError("unexpected frozen total cost")

    session_summary_path = session_dir / "session_summary.json"
    quotes_path = session_dir / "quotes.jsonl"
    obs_path = session_dir / "sources" / "weather_observations.jsonl"
    for p in (session_summary_path, quotes_path, obs_path):
        if not p.is_file():
            raise EconomicKillError(f"missing session input: {p}")

    session_summary = read_json(session_summary_path)
    session_start = parse_utc(str(session_summary["started_utc"]))
    if session_start <= protocol_commit_utc:
        raise EconomicKillError(
            "session is not fresh: it began before/equal to frozen economic protocol commit"
        )
    if session_summary.get("guardrail") != "PASS:read_only_no_order_submission_no_alpha_or_pnl_computation":
        raise EconomicKillError("unexpected source-session guardrail")
    if int(session_summary.get("http_errors") or 0) != 0:
        raise EconomicKillError("source session has HTTP errors")
    if int(session_summary.get("auth_failures") or 0) != 0:
        raise EconomicKillError("source session has auth failures")
    if int(session_summary.get("gaps") or 0) != 0:
        raise EconomicKillError("source session has capture gaps")

    model_path = pre_eval_dir / "m0_model.json"
    ecdf_path = pre_eval_dir / "calibration_standardized_residuals.csv"
    val_summary_path = validation_dir / "validation_summary.json"
    policy_path = support_dir / "support_policy.json"
    state_path = support_dir / "state_support_cells.csv"
    cal_path = support_dir / "calibration_support_cells.csv"

    for p in (model_path, ecdf_path, val_summary_path, policy_path, state_path, cal_path):
        if not p.is_file():
            raise EconomicKillError(f"missing frozen input: {p}")

    val_summary = read_json(val_summary_path)
    support_policy = read_json(policy_path)

    # Chain-of-custody checks from frozen validation/support artifacts.
    expected_model_sha = val_summary["frozen_input_sha256"]["m0_model.json"]
    expected_ecdf_sha = val_summary["frozen_input_sha256"]["calibration_standardized_residuals.csv"]
    if sha256_file(model_path) != expected_model_sha:
        raise EconomicKillError("M0 model hash differs from frozen validation input")
    if sha256_file(ecdf_path) != expected_ecdf_sha:
        raise EconomicKillError("calibration ECDF hash differs from frozen validation input")
    if sha256_file(ecdf_path) != support_policy["source_sha256"]["calibration_standardized_residuals.csv"]:
        raise EconomicKillError("calibration ECDF hash differs from frozen support input")
    if sha256_file(val_summary_path) != support_policy["source_sha256"]["validation_summary.json"]:
        raise EconomicKillError("validation summary hash differs from frozen support input")
    if support_policy.get("economics_not_yet_run") is not True:
        raise EconomicKillError("support policy economics boundary unexpected")

    lock = {
        "economic_protocol_id": ECON_PROTOCOL_ID,
        "economic_version": ECON_VERSION,
        "eligibility_correction_id": config.get("eligibility_correction_id"),
        "protocol_commit_utc": protocol_commit_utc.isoformat(),
        "fresh_session_started_utc": session_start.isoformat(),
        "input_sha256": {
            "economic_config": sha256_file(economic_config_path),
            "session_summary": sha256_file(session_summary_path),
            "quotes": sha256_file(quotes_path),
            "weather_observations": sha256_file(obs_path),
            "m0_model": sha256_file(model_path),
            "calibration_ecdf": sha256_file(ecdf_path),
            "validation_summary": sha256_file(val_summary_path),
            "support_policy": sha256_file(policy_path),
            "state_support_cells": sha256_file(state_path),
            "calibration_support_cells": sha256_file(cal_path),
        },
        "fee_usd": float(config["verified_pricing"]["exchange_fee_usd_per_contract"]),
        "ibkr_commission_usd": float(config["verified_pricing"]["ibkr_commission_usd_per_contract"]),
        "execution_reserve_usd": float(config["reserves"]["execution_reserve_usd_per_contract"]),
        "funding_carry_reserve_usd": float(config["reserves"]["funding_carry_reserve_usd_per_contract"]),
        "total_cost_usd": float(config["total_cost_usd_per_contract"]),
        "market_selection_risk": support_policy["market_selection_risk"]["status"],
        "guardrail": "FRESH_READ_ONLY_SESSION_FROZEN_MODEL_SUPPORT_AND_COSTS_NO_ORDERS",
    }
    (output_dir / "economic_screen_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    model = load_model(model_path)
    z, zw = load_ecdf(ecdf_path)
    state_cells = _load_state_support(state_path)
    cal_cells = _load_calibration_support(cal_path)
    quotes = read_jsonl(quotes_path)
    observations = read_jsonl(obs_path)

    event_date = str(session_summary["event_date"])
    total_cost = float(config["total_cost_usd_per_contract"])

    rows: list[dict[str, Any]] = []
    for q in quotes:
        quote_utc = parse_utc(str(q["response_received_utc"]))
        quality_ok, quality_reasons, ask, ask_size = _quote_quality(q)

        rec: dict[str, Any] = {
            "session_id": q.get("session_id"),
            "cycle_id": q.get("cycle_id"),
            "batch_id": q.get("batch_id"),
            "response_received_utc": q.get("response_received_utc"),
            "conid": q.get("conid"),
            "threshold_f": q.get("threshold"),
            "side": q.get("side"),
            "ask": ask,
            "ask_size": ask_size,
            "quote_quality_ok": quality_ok,
            "quote_quality_reasons": "|".join(quality_reasons),
        }

        if not quality_ok:
            rec.update({
                "screen_status": "NO_VALID_EXECUTABLE_ASK",
                "supported": False,
            })
            rows.append(rec)
            continue

        state = build_weather_state(
            observations,
            quote_utc=quote_utc,
            event_date=event_date,
        )
        if state is None:
            rec.update({
                "screen_status": "MODEL_DATA_INSUFFICIENT",
                "supported": False,
                "support_reasons": "no_point_in_time_weather_state_received_by_quote_time",
            })
            rows.append(rec)
            continue

        threshold = float(q["threshold"])
        pred = predict_q(
            model=model,
            z=z,
            zw=zw,
            state=state,
            threshold_f=threshold,
        )
        support = check_support(
            state=state,
            q_hat=pred["q_hat"],
            delta_f=pred["delta_f"],
            state_cells=state_cells,
            cal_cells=cal_cells,
            policy=support_policy,
        )

        rec.update({
            **state,
            **pred,
            "local_time_block": support["local_time_block"],
            "q_bin": support["q_bin"],
            "supported": support["supported"],
            "support_reasons": "|".join(support["support_reasons"]),
            "calibration_slack": support["slack"],
        })

        if not support["supported"]:
            rec["screen_status"] = "MODEL_DATA_INSUFFICIENT"
            rows.append(rec)
            continue

        slack = float(support["slack"])
        q_l = max(0.0, pred["q_hat"] - slack)
        q_u = min(1.0, pred["q_hat"] + slack)
        side = str(q["side"]).upper()
        if side == "Y":
            p_cons = q_l
        elif side == "N":
            p_cons = 1.0 - q_u
        else:
            raise EconomicKillError(f"unexpected contract side: {side!r}")

        margin = p_cons - float(ask) - total_cost
        payout_ceiling_margin = 1.0 - float(ask) - total_cost

        rec.update({
            "q_L": q_l,
            "q_U": q_u,
            "conservative_side_probability": p_cons,
            "verified_fee_and_reserve_cost": total_cost,
            "payout_ceiling_margin": payout_ceiling_margin,
            "economic_margin": margin,
            "screen_status": (
                "APPARENT_POSITIVE_CONSERVATIVE_MARGIN_GATE3_REQUIRED"
                if margin > 0.0
                else "NONPOSITIVE_CONSERVATIVE_MARGIN"
            ),
        })
        rows.append(rec)

    if not rows:
        raise EconomicKillError("no quote rows")

    all_fields: list[str] = []
    seen_fields: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen_fields:
                seen_fields.add(k)
                all_fields.append(k)

    out_csv = output_dir / "economic_screen_rows.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=all_fields)
        w.writeheader()
        w.writerows(rows)

    supported = [r for r in rows if r.get("supported") is True and "economic_margin" in r]
    positive = [r for r in supported if float(r["economic_margin"]) > 0.0]
    nonpositive = [r for r in supported if float(r["economic_margin"]) <= 0.0]
    unsupported = [r for r in rows if r.get("screen_status") == "MODEL_DATA_INSUFFICIENT"]
    invalid_quotes = [r for r in rows if r.get("screen_status") == "NO_VALID_EXECUTABLE_ASK"]

    by_side: dict[str, dict[str, Any]] = {}
    for side in ("Y", "N"):
        ss = [r for r in supported if str(r.get("side")).upper() == side]
        pp = [r for r in ss if float(r["economic_margin"]) > 0]
        by_side[side] = {
            "supported_rows": len(ss),
            "positive_rows": len(pp),
            "max_margin": max((float(r["economic_margin"]) for r in ss), default=None),
        }

    positive_sorted = sorted(
        positive,
        key=lambda r: float(r["economic_margin"]),
        reverse=True,
    )
    top_positive = [
        {
            "cycle_id": r["cycle_id"],
            "response_received_utc": r["response_received_utc"],
            "threshold_f": r["threshold_f"],
            "side": r["side"],
            "ask": r["ask"],
            "ask_size": r["ask_size"],
            "q_hat": r["q_hat"],
            "q_L": r["q_L"],
            "q_U": r["q_U"],
            "calibration_slack": r["calibration_slack"],
            "conservative_side_probability": r["conservative_side_probability"],
            "economic_margin": r["economic_margin"],
            "local_time_block": r["local_time_block"],
            "q_bin": r["q_bin"],
        }
        for r in positive_sorted[:20]
    ]

    if positive:
        session_decision = "APPARENT_POSITIVE_CONSERVATIVE_MARGIN_GATE3_REQUIRED"
        next_boundary = (
            "STOP. Do not shadow-retune, build order lifecycle, or trade. "
            "Package the first positive candidate(s) for Sol Max Gate #3."
        )
    else:
        session_decision = "NO_POSITIVE_MARGIN_IN_THIS_FRESH_SESSION"
        next_boundary = (
            "No Gate #3 trigger in this session. Continue bounded prospective "
            "read-only screening under the same frozen protocol; do not retune."
        )

    summary = {
        "economic_protocol_id": ECON_PROTOCOL_ID,
        "economic_version": ECON_VERSION,
        "eligibility_correction_id": config.get("eligibility_correction_id"),
        "event_date": event_date,
        "session_started_utc": session_summary["started_utc"],
        "session_ended_utc": session_summary["ended_utc"],
        "quote_rows_total": len(rows),
        "valid_supported_economic_rows": len(supported),
        "nonpositive_supported_rows": len(nonpositive),
        "positive_supported_rows": len(positive),
        "model_data_insufficient_rows": len(unsupported),
        "invalid_executable_quote_rows": len(invalid_quotes),
        "by_side": by_side,
        "max_supported_margin": max(
            (float(r["economic_margin"]) for r in supported),
            default=None,
        ),
        "min_supported_margin": min(
            (float(r["economic_margin"]) for r in supported),
            default=None,
        ),
        "top_positive_candidates": top_positive,
        "fee_and_reserve": {
            "ibkr_commission": config["verified_pricing"]["ibkr_commission_usd_per_contract"],
            "exchange_fee": config["verified_pricing"]["exchange_fee_usd_per_contract"],
            "execution_reserve": config["reserves"]["execution_reserve_usd_per_contract"],
            "funding_carry_reserve": config["reserves"]["funding_carry_reserve_usd_per_contract"],
            "total_cost": total_cost,
        },
        "market_selection_risk": support_policy["market_selection_risk"]["status"],
        "session_decision": session_decision,
        "global_economic_kill_claim": False,
        "orders_authorized": False,
        "guardrail": "PASS:FRESH_EXECUTABLE_ASK_SCREEN_ONLY_NO_ORDERS_NO_RETUNING",
        "next_boundary": next_boundary,
    }
    (output_dir / "economic_screen_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary
