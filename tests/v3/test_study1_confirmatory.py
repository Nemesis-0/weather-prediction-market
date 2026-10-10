from __future__ import annotations

import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.v3.study1 import confirmatory as c


class TestConfirmatorySemantics(unittest.TestCase):
    def setUp(self):
        self.spec = c.PRODUCT_BY_CODE["UHLGA"]
        self.event_date = date(2026, 10, 5)
        last_trade = int(datetime(2026, 10, 5, 23, 59, tzinfo=ZoneInfo("America/New_York")).timestamp())
        base_rules = {
            "source_agency": "Weather Underground", "data_and_resolution_link": "https://x/KLGA",
            "description": "Daily high at KLGA", "market_rules_link": "https://x/terms.pdf", "payout": "$1.00",
            "price_increment": "$0.01", "product_code": "UHLGA", "last_trade_time": last_trade,
            "release_time": last_trade + 3600, "payout_time": last_trade + 7200,
            "exchange_timezone": "US/Central", "threshold": "70.0",
        }
        q = "Will the highest temperature in New York City (NYC)(LGA)(KLGA) exceed 70 F on October 5, 2026? (maximum)?"
        yd = {"conid_yes": 1, "conid_no": 2, "question": q, "side": "Y", "strike": 70.0,
              "symbol": "UHLGA", "market_name": self.spec.market_name, "payout": 1.0}
        nd = dict(yd, side="N")
        self.y = {"conid": 1, "details": yd, "rules": dict(base_rules)}
        self.n = {"conid": 2, "details": nd, "rules": dict(base_rules)}

    def test_question_date_is_canonical_not_expiration(self):
        parsed = c.parse_event_question(self.y["details"]["question"], self.spec)
        self.assertEqual(parsed["event_date"], "2026-10-05")

    def test_mutual_complement_and_fingerprint(self):
        row = c.validate_threshold_pair_records(self.y, self.n, spec=self.spec, event_date=self.event_date)
        self.assertEqual(row["yes_conid"], 1); self.assertEqual(row["no_conid"], 2)
        self.assertEqual(row["event_date"], "2026-10-05")

    def test_wrong_complement_fails(self):
        bad = {**self.n, "details": {**self.n["details"], "conid_yes": 999}}
        with self.assertRaises(c.ConfirmatoryEligibilityError):
            c.validate_threshold_pair_records(self.y, bad, spec=self.spec, event_date=self.event_date)

    def test_cross_threshold_mismatch_fails(self):
        a = c.validate_threshold_pair_records(self.y, self.n, spec=self.spec, event_date=self.event_date)
        b = dict(a, threshold="71", yes_conid=3, no_conid=4, source_agency="DIFFERENT")
        with self.assertRaises(c.ConfirmatoryEligibilityError): c.validate_cross_threshold_ladder([a, b])


class TestQuoteAndCostGuards(unittest.TestCase):
    def test_same_request_quote_validation(self):
        now = 1_800_000_000.0
        ms = int((now - 2) * 1000)
        payload = [
            {"conid": 1, "86": "0.42", "85": "2", "6509": "R", "_updated": ms},
            {"conid": 2, "86": "0.51", "85": "1", "6509": "R", "_updated": ms + 1000},
        ]
        out = c.validate_pair_snapshot(payload, expected_conids=(1,2), request_elapsed_seconds=.4, response_received_epoch=now)
        self.assertEqual(len(out["rows"]), 2)

    def test_duplicate_or_delayed_fails(self):
        now = 1_800_000_000.0; ms = int((now - 2) * 1000)
        dup = [{"conid":1,"86":"0.42","85":"1","6509":"R","_updated":ms},
               {"conid":1,"86":"0.42","85":"1","6509":"R","_updated":ms}]
        with self.assertRaises(c.ConfirmatoryEligibilityError): c.validate_pair_snapshot(dup, expected_conids=(1,2), request_elapsed_seconds=.1, response_received_epoch=now)
        delayed = [{"conid":1,"86":"0.42","85":"1","6509":"D","_updated":ms},
                   {"conid":2,"86":"0.42","85":"1","6509":"R","_updated":ms}]
        with self.assertRaises(c.ConfirmatoryEligibilityError): c.validate_pair_snapshot(delayed, expected_conids=(1,2), request_elapsed_seconds=.1, response_received_epoch=now)

    def test_cost_rounds_up_and_counts_two_fees_two_ticks(self):
        out = c.conservative_cost(lower_ask_t1="0.40", lower_ask_t2="0.41", higher_no_ask_t1="0.50", higher_no_ask_t2="0.49",
                                  broker_fee_per_contract="0.00", exchange_fee_per_contract="0.01", tick_reserve_per_leg="0.01",
                                  annual_funding_rate="0.04", seconds_to_payout=86400)
        self.assertEqual(str(out["fees"]), "0.02")
        self.assertEqual(str(out["tick_reserve"]), "0.02")
        self.assertGreaterEqual(out["total_rounded"], out["total_raw"])

    def test_date_health_policy(self):
        self.assertEqual(c.classify_date_health(normal_slots=960), "VALID")
        self.assertTrue(c.classify_date_health(normal_slots=950).startswith("ABORTED"))
        self.assertTrue(c.classify_date_health(normal_slots=958, max_consecutive_invalid=3).startswith("ABORTED"))


class TestAcceptanceFirewall(unittest.TestCase):
    def test_acceptance_source_does_not_call_cost_or_opportunity(self):
        root = Path(__file__).resolve().parents[2]
        src = (root / "scripts/v3/run_study1_confirmatory_acceptance.py").read_text()
        for token in ["conservative_cost(", "opportunity_flag", "qualifying_basket", "compute_pnl"]:
            self.assertNotIn(token, src)

    def test_acceptance_help(self):
        root = Path(__file__).resolve().parents[2]
        p = subprocess.run([sys.executable, str(root / "scripts/v3/run_study1_confirmatory_acceptance.py"), "--help"], cwd=root, text=True, capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("strategy-blind", p.stdout.lower())

    def test_acceptance_source_emits_status_and_failure_classes(self):
        root = Path(__file__).resolve().parents[2]
        src = (root / "scripts/v3/run_study1_confirmatory_acceptance.py").read_text()
        for token in ["acceptance_status", "quote_unavailable_checks", "structural_failure_checks", "diagnostic_only"]:
            self.assertIn(token, src)


if __name__ == "__main__": unittest.main()

class TestScheduleAndRevalidation(unittest.TestCase):
    def test_schedule_open_and_closed(self):
        import calendar
        from datetime import datetime, timezone
        sched = {"timezone":"America/Chicago","trading_schedules":[
            {"day_of_week":"Monday","trading_times":[{"open":"12:00 AM","close":"4:15 PM"},{"open":"4:16 PM","close":"11:59 PM"}]}
        ]}
        open_epoch = datetime(2026,10,5,15,0,tzinfo=timezone.utc).timestamp()  # 10 AM CT
        self.assertTrue(c.validate_schedule_open(sched, now_epoch=open_epoch)["open"])
        gap_epoch = datetime(2026,10,5,21,15,30,tzinfo=timezone.utc).timestamp()  # 4:15:30 PM CT maintenance minute
        with self.assertRaises(c.ConfirmatoryEligibilityError): c.validate_schedule_open(sched, now_epoch=gap_epoch)

    def test_empty_schedule_fails(self):
        with self.assertRaises(c.ConfirmatoryEligibilityError): c.validate_schedule_open({}, now_epoch=0)

    def test_revalidation_requires_next_slot_and_25_to_35_seconds(self):
        t=c.RevalidationTracker()
        self.assertEqual(t.observe("p",slot_index=1,request_start_epoch=100,valid=True,payload="a")[0],"PENDING_FIRST")
        status,payload=t.observe("p",slot_index=2,request_start_epoch=130,valid=True,payload="b")
        self.assertEqual(status,"CONFIRMED_TWO_POLL"); self.assertEqual(payload,("a","b"))

    def test_revalidation_invalid_intervening_resets(self):
        t=c.RevalidationTracker(); t.observe("p",slot_index=1,request_start_epoch=100,valid=True,payload="a")
        self.assertEqual(t.observe("p",slot_index=2,request_start_epoch=130,valid=False,payload=None)[0],"INVALID_RESET")
        self.assertEqual(t.observe("p",slot_index=3,request_start_epoch=160,valid=True,payload="c")[0],"PENDING_FIRST")

    def test_revalidation_wrong_gap_resets(self):
        t=c.RevalidationTracker(); t.observe("p",slot_index=1,request_start_epoch=100,valid=True,payload="a")
        self.assertEqual(t.observe("p",slot_index=2,request_start_epoch=140,valid=True,payload="b")[0],"RESET_NEW_FIRST")

    def test_date_ledger_keeps_all_dates_in_denominator(self):
        ledger=c.build_date_ledger(date(2026,10,6),3)
        self.assertEqual([x["date"] for x in ledger],["2026-10-06","2026-10-07","2026-10-08"])
        self.assertTrue(all(x["in_primary_denominator"] for x in ledger))

    def test_nan_price_fails(self):
        now=1_800_000_000.0; ms=int((now-1)*1000)
        payload=[{"conid":1,"86":"NaN","85":"1","6509":"R","_updated":ms},{"conid":2,"86":"0.5","85":"1","6509":"R","_updated":ms}]
        with self.assertRaises(c.ConfirmatoryEligibilityError): c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)

    def test_old_broker_timestamp_is_diagnostic_not_failure(self):
        now=1_800_000_000.0; ms=int((now-61)*1000)
        payload=[{"conid":1,"86":"0.4","85":"1","6509":"R","_updated":ms},{"conid":2,"86":"0.5","85":"1","6509":"R","_updated":ms}]
        out=c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)
        self.assertTrue(all(r["broker_age_diagnostic_exceeds_reference"] for r in out["rows"]))

    def test_pair_broker_skew_is_diagnostic_not_failure(self):
        now=1_800_000_000.0
        payload=[{"conid":1,"86":"0.4","85":"1","6509":"R","_updated":int((now-10)*1000)},
                 {"conid":2,"86":"0.5","85":"1","6509":"R","_updated":int((now-1)*1000)}]
        out=c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)
        self.assertTrue(out["pair_broker_skew_diagnostic_exceeds_reference"])

    def test_future_broker_timestamp_still_fails(self):
        now=1_800_000_000.0; ms=int((now+2)*1000)
        payload=[{"conid":1,"86":"0.4","85":"1","6509":"R","_updated":ms},{"conid":2,"86":"0.5","85":"1","6509":"R","_updated":ms}]
        with self.assertRaises(c.ConfirmatoryEligibilityError):
            c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)

    def test_snapshot_failure_class_separates_quote_unavailable(self):
        self.assertEqual(c.snapshot_failure_class(c.QuoteUnavailableError("ask unavailable")), "quote_unavailable")
        self.assertEqual(c.snapshot_failure_class(c.ConfirmatoryEligibilityError("duplicate conid in pair response")), "structural_failure")

class TestFrozenProtocol(unittest.TestCase):
    def test_frozen_schedule_is_exact_30_dates(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        ds=frozen.planned_dates(cfg)
        self.assertEqual(len(ds),30)
        self.assertEqual(ds[0],"2026-10-07")
        self.assertEqual(ds[-1],"2026-11-05")
        self.assertEqual(cfg["status"],"FINAL_FROZEN_CONFIRMATORY_NOT_STARTED")

    def test_daily_collector_source_is_result_blind(self):
        root=Path(__file__).resolve().parents[2]
        src=(root/"scripts/v3/run_study1_confirmatory_day.py").read_text()
        self.assertNotIn("conservative_cost(",src)
        self.assertNotIn("evaluate_city_date(",src)
        self.assertIn("sealed_pair_observations.jsonl", (root/"configs/v3/study1_confirmatory_frozen.json").read_text())

    def test_endpoint_unlock_after_last_session(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        unlock=frozen.endpoint_unlock_time(cfg)
        self.assertEqual(unlock.isoformat(),"2026-11-05T22:00:00+00:00")

    def test_mbb_degenerate_is_none(self):
        from src.v3.study1 import frozen
        self.assertIsNone(frozen.mbb_interval([0]*30,block_days=3,replicates=100,seed=1))

    def test_first_qualifying_pair_is_deterministic(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        payout=86_530.0
        ladder={
            "thresholds":[
                {"threshold":"70","payout_time":payout},
                {"threshold":"71","payout_time":payout},
                {"threshold":"72","payout_time":payout},
            ],
            "adjacent_pairs":[
                {"city_id":"NYC","event_date":"2026-10-07","lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2},
                {"city_id":"NYC","event_date":"2026-10-07","lower_threshold":"71","higher_threshold":"72","lower_yes_conid":3,"higher_no_conid":4},
            ]
        }
        def rec(slot,pid,lo,hi,a,b,t):
            return {"slot_index":slot,"city_id":"NYC","pair_id":pid,"quote_status":"QUOTE_ELIGIBLE","request_start_epoch":t,
                    "snapshot":{"rows":[{"conid":lo,"ask":a},{"conid":hi,"ask":b}]}}
        p1=frozen.pair_id("NYC","70",1,2); p2=frozen.pair_id("NYC","71",3,4)
        records=[rec(0,p1,1,2,"0.40","0.50",100),rec(1,p1,1,2,"0.41","0.49",130),
                 rec(0,p2,3,4,"0.39","0.50",100),rec(1,p2,3,4,"0.40","0.49",130)]
        out=frozen.evaluate_city_date(records,city_id="NYC",ladder=ladder,cfg=cfg,valid_slot_indices={0,1})
        self.assertIsNotNone(out)
        self.assertEqual(out["lower_threshold"],"70")


class TestSolFinalGateRegression(unittest.TestCase):
    def setUp(self):
        self.spec = c.PRODUCT_BY_CODE["UHLGA"]
        self.event_date = date(2026, 10, 7)
        self.last_trade = int(datetime(2026, 10, 7, 23, 59, tzinfo=ZoneInfo("America/New_York")).timestamp())

    def _question(self, threshold: int) -> str:
        return f"Will the highest temperature in New York City (NYC)(LGA)(KLGA) exceed {threshold} F on October 7, 2026? (maximum)?"

    def _details(self, yid: int, nid: int, threshold: int, side: str, question: str | None = None) -> dict:
        return {
            "conid_yes": yid, "conid_no": nid, "question": question or self._question(threshold),
            "side": side, "strike": float(threshold), "symbol": "UHLGA",
            "market_name": self.spec.market_name, "payout": 1.0,
        }

    def _rules(self, threshold: int, *, payout: str = "$1.00", tick: str = "$0.01") -> dict:
        return {
            "source_agency": "Weather Underground", "data_and_resolution_link": "https://x/KLGA",
            "description": "Daily high at KLGA", "market_rules_link": "https://x/terms.pdf",
            "payout": payout, "price_increment": tick, "product_code": "UHLGA",
            "last_trade_time": self.last_trade, "release_time": self.last_trade + 3600,
            "payout_time": self.last_trade + 7200, "exchange_timezone": "US/Central",
            "threshold": str(float(threshold)),
        }

    def test_rules_details_payout_mismatch_is_study_blocker(self):
        y={"conid":1,"details":self._details(1,2,70,"Y"),"rules":self._rules(70,payout="$0.50")}
        n={"conid":2,"details":self._details(1,2,70,"N"),"rules":self._rules(70,payout="$0.50")}
        with self.assertRaises(c.StudyBlockerError):
            c.validate_threshold_pair_records(y,n,spec=self.spec,event_date=self.event_date)

    def test_wrong_tick_is_study_blocker(self):
        y={"conid":1,"details":self._details(1,2,70,"Y"),"rules":self._rules(70,tick="$0.02")}
        n={"conid":2,"details":self._details(1,2,70,"N"),"rules":self._rules(70,tick="$0.02")}
        with self.assertRaises(c.StudyBlockerError):
            c.validate_threshold_pair_records(y,n,spec=self.spec,event_date=self.event_date)

    def test_unparseable_listed_contract_cannot_be_silently_dropped(self):
        details={
            1:self._details(1,2,70,"Y"), 2:self._details(1,2,70,"N"),
            3:self._details(3,4,71,"Y",question="UNPARSEABLE QUESTION"),
            4:self._details(3,4,71,"N"),
        }
        rules={1:self._rules(70),2:self._rules(70),3:self._rules(71),4:self._rules(71)}
        class Fake:
            def contract_details(self, conid): return details[conid]
            def contract_rules(self, conid): return rules[conid]
        market={"contracts":[{"conid":1},{"conid":2},{"conid":3},{"conid":4}]}
        with self.assertRaises(c.StudyBlockerError):
            c.acquire_event_ladder(Fake(),self.spec,market,self.event_date)

    def test_missing_first_ask_cannot_hide_delayed_second_leg(self):
        now=1_800_000_000.0; ms=int((now-1)*1000)
        payload=[
            {"conid":1,"86":None,"85":"1","6509":"R","_updated":ms},
            {"conid":2,"86":"0.50","85":"1","6509":"D","_updated":ms},
        ]
        with self.assertRaises(c.ConfirmatoryEligibilityError) as ctx:
            c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)
        self.assertNotIsInstance(ctx.exception,c.QuoteUnavailableError)
        self.assertEqual(c.snapshot_failure_class(ctx.exception),"structural_failure")

    def test_zero_or_one_ask_is_quote_unavailable(self):
        now=1_800_000_000.0; ms=int((now-1)*1000)
        for bad in ("0.00","1.00"):
            payload=[{"conid":1,"86":bad,"85":"1","6509":"R","_updated":ms},
                     {"conid":2,"86":"0.50","85":"1","6509":"R","_updated":ms}]
            with self.assertRaises(c.QuoteUnavailableError):
                c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)

    def test_zero_broker_epoch_is_structural_failure(self):
        now=1_800_000_000.0
        payload=[{"conid":1,"86":"0.40","85":"1","6509":"R","_updated":0},
                 {"conid":2,"86":"0.50","85":"1","6509":"R","_updated":int((now-1)*1000)}]
        with self.assertRaises(c.ConfirmatoryEligibilityError) as ctx:
            c.validate_pair_snapshot(payload,expected_conids=(1,2),request_elapsed_seconds=.1,response_received_epoch=now)
        self.assertEqual(c.snapshot_failure_class(ctx.exception),"structural_failure")

    def test_terms_hash_mismatch_is_study_blocker(self):
        with self.assertRaises(c.StudyBlockerError):
            c.verify_terms_archive({"url":"https://x/terms.pdf","sha256":"bad"},expected_url="https://x/terms.pdf",expected_sha256="good")

    def test_structural_invalid_slot_cannot_complete_revalidation(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        ladder={"thresholds":[{"threshold":"70","payout_time":86530.0},{"threshold":"71","payout_time":86530.0}],
                "adjacent_pairs":[{"city_id":"NYC","event_date":"2026-10-07","lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2}]}
        pid=frozen.pair_id("NYC","70",1,2)
        records=[
            {"slot_index":0,"city_id":"NYC","pair_id":pid,"quote_status":"QUOTE_ELIGIBLE","request_start_epoch":100,"snapshot":{"rows":[{"conid":1,"ask":"0.40"},{"conid":2,"ask":"0.50"}]}},
            {"slot_index":1,"city_id":"NYC","pair_id":pid,"quote_status":"QUOTE_ELIGIBLE","request_start_epoch":130,"snapshot":{"rows":[{"conid":1,"ask":"0.40"},{"conid":2,"ask":"0.50"}]}}]
        self.assertIsNone(frozen.evaluate_city_date(records,city_id="NYC",ladder=ladder,cfg=cfg,valid_slot_indices={0}))

    def test_daily_collector_contains_terms_session_and_coverage_guards(self):
        root=Path(__file__).resolve().parents[2]
        src=(root/"scripts/v3/run_study1_confirmatory_day.py").read_text()
        for token in ["verify_terms_archive", "received >= end_epoch", "expected_pair_records", "STUDY_BLOCKER", "verify_freeze_manifest"]:
            self.assertIn(token,src)

    def test_endpoint_requires_integrity_audit(self):
        root=Path(__file__).resolve().parents[2]
        src=(root/"scripts/v3/evaluate_study1_after_endpoint.py").read_text()
        for token in ["audit_valid_day_inputs", "read_day_health_summary", "health_errors", "INTEGRITY_FAILURE_RETAIN_IN_DENOMINATOR", "CLOSE_SEMANTIC_OR_TERMS_BLOCKER"]:
            self.assertIn(token,src)

    def test_frozen_terms_artifact_hash(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        p=root/cfg["terms"]["frozen_pdf_path"]
        self.assertEqual(frozen.sha256_file(p),cfg["terms"]["sha256"])
        self.assertEqual(cfg["terms"]["sha256"],"226826cb5d64cddc52c86b99a2e908f25ba48aa431f6c9ffe2c30e55731db511")

    def test_freeze_manifest_matches_actual_core_files_and_config(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        state=frozen.verify_freeze_manifest(root)
        self.assertEqual(state["manifest"]["protocol_id"],cfg["protocol_id"])
        self.assertEqual(state["manifest"]["freeze_parent_commit"],cfg["freeze_parent_commit"])
        self.assertIn(cfg["terms"]["frozen_pdf_path"],{r["path"] for r in state["manifest"]["core_files"]})

class TestEndpointInputIntegrity(unittest.TestCase):
    def _fixture(self, tmp: Path, *, outside_session: bool = False):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=json.loads(json.dumps(frozen.load_frozen_config(root)))
        cfg["nominal_slots_per_date"]=2
        cfg["date_health"]["minimum_normal_slots"]=2
        cfg["date_health"]["maximum_total_invalid_slots"]=0
        cfg["date_health"]["maximum_consecutive_invalid_slots"]=0
        d="2026-10-07"
        ladder={"NYC":{"thresholds":[{"threshold":"70","payout_time":9999999999},{"threshold":"71","payout_time":9999999999}],
                       "adjacent_pairs":[{"city_id":"NYC","event_date":d,"lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2}]}}
        pid=frozen.pair_id("NYC","70",1,2)
        start,end=frozen.session_bounds(date.fromisoformat(d),cfg)
        t0=start.timestamp()+10
        t1=end.timestamp() if outside_session else start.timestamp()+40
        identity={"city_id":"NYC","pair_id":pid,"lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2}
        records=[
            {"slot_index":0,**identity,"quote_status":"QUOTE_ELIGIBLE","request_start_epoch":t0,"response_received_epoch":t0+.2,"snapshot":{"rows":[{"conid":1,"ask":"0.40"},{"conid":2,"ask":"0.50"}]}},
            {"slot_index":1,**identity,"quote_status":"QUOTE_ELIGIBLE","request_start_epoch":t1,"response_received_epoch":t1+.2,"snapshot":{"rows":[{"conid":1,"ask":"0.40"},{"conid":2,"ask":"0.50"}]}}
        ]
        sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
        sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
        (tmp/"run_identity.json").write_text(json.dumps({"protocol_id":cfg["protocol_id"],"event_date":d,"freeze_manifest_sha256":"manifest"}))
        (tmp/"terms_manifest.json").write_text("[]")
        (tmp/"trading_schedules.json").write_text("{}")
        slot_rows=[{"slot_index":0,"status":"NORMAL","expected_pair_records":1,"observed_pair_records":1},
                   {"slot_index":1,"status":"NORMAL","expected_pair_records":1,"observed_pair_records":1}]
        (tmp/"slot_health.jsonl").write_text("".join(json.dumps(x)+"\n" for x in slot_rows))
        health={
            "protocol_id":cfg["protocol_id"],"event_date":d,"date_status":"VALID",
            "nominal_slots":2,"observed_or_accounted_slots":2,
            "normal_slots":2,"structural_invalid_slots":0,"max_consecutive_structural_invalid_slots":0,
            "terminal_failure":None,"study_blocker":None,
            "sealed_input_sha256":frozen.sha256_file(sealed),
        }
        return frozen,cfg,d,ladder,records,health

    def test_valid_day_audit_verifies_complete_ledgers_and_hash(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            self.assertEqual(frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest"),{0,1})
            health["sealed_input_sha256"]="bad"
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_eligible_response_outside_session_is_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp,outside_session=True)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_missing_quote_status_is_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0].pop("quote_status")
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_unknown_quote_status_is_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0]["quote_status"]="UNKNOWN_STATUS"
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_eligible_missing_required_snapshot_is_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0].pop("snapshot")
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_quote_unavailable_is_allowed_only_with_explicit_failure_fields(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0]={k:v for k,v in records[0].items() if k not in {"response_received_epoch","snapshot"}}
            records[0]["quote_status"]="QUOTE_UNAVAILABLE"
            records[0]["failure_class"]="quote_unavailable"
            records[0]["reason"]="ask unavailable"
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            self.assertEqual(frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest"),{0,1})

    def test_missing_city_id_is_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0].pop("city_id")
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_city_id_must_match_frozen_pair_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0]["city_id"]="CHI"
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_pair_identity_fields_must_match_frozen_ladder(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0]["lower_yes_conid"]=999
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_eligible_failure_fields_conflict_is_integrity_failure(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0]["failure_class"]="structural_failure"
            records[0]["reason"]="synthetic conflict"
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_eligible_snapshot_conids_must_match_frozen_pair(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frozen,cfg,d,ladder,records,health=self._fixture(tmp)
            records[0]["snapshot"]["rows"][1]["conid"]=999
            sealed=tmp/cfg["result_firewall"]["sealed_input_file"]
            sealed.write_text("".join(json.dumps(x)+"\n" for x in records))
            health["sealed_input_sha256"]=frozen.sha256_file(sealed)
            with self.assertRaises(RuntimeError):
                frozen.audit_valid_day_inputs(tmp,event_date=d,cfg=cfg,health=health,ladders=ladder,records=records,manifest_sha256="manifest")

    def test_claimed_valid_day_recomputes_minimum_normal_slots(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=json.loads(json.dumps(frozen.load_frozen_config(root)))
        health={
            "protocol_id":cfg["protocol_id"],"event_date":"2026-10-07","date_status":"VALID",
            "nominal_slots":960,"observed_or_accounted_slots":960,
            "normal_slots":950,"structural_invalid_slots":10,
            "max_consecutive_structural_invalid_slots":1,"terminal_failure":None,"study_blocker":None,
        }
        with self.assertRaises(RuntimeError):
            frozen.validate_valid_date_health(health,cfg=cfg,event_date="2026-10-07",slots=960,normal_count=950,total_invalid=10,max_consecutive_invalid=1)

    def test_claimed_valid_day_recomputes_consecutive_invalid_limit(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=json.loads(json.dumps(frozen.load_frozen_config(root)))
        health={
            "protocol_id":cfg["protocol_id"],"event_date":"2026-10-07","date_status":"VALID",
            "nominal_slots":960,"observed_or_accounted_slots":960,
            "normal_slots":957,"structural_invalid_slots":3,
            "max_consecutive_structural_invalid_slots":3,"terminal_failure":None,"study_blocker":None,
        }
        with self.assertRaises(RuntimeError):
            frozen.validate_valid_date_health(health,cfg=cfg,event_date="2026-10-07",slots=960,normal_count=957,total_invalid=3,max_consecutive_invalid=3)

    def test_claimed_valid_day_rejects_terminal_failure(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=json.loads(json.dumps(frozen.load_frozen_config(root)))
        health={
            "protocol_id":cfg["protocol_id"],"event_date":"2026-10-07","date_status":"VALID",
            "nominal_slots":960,"observed_or_accounted_slots":960,
            "normal_slots":960,"structural_invalid_slots":0,
            "max_consecutive_structural_invalid_slots":0,"terminal_failure":"synthetic failure","study_blocker":None,
        }
        with self.assertRaises(RuntimeError):
            frozen.validate_valid_date_health(health,cfg=cfg,event_date="2026-10-07",slots=960,normal_count=960,total_invalid=0,max_consecutive_invalid=0)

    def test_corrupt_health_json_is_date_level_integrity_failure_input(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        with tempfile.TemporaryDirectory() as td:
            hp=Path(td)/"day_health_summary.json"
            hp.write_text("{not valid json",encoding="utf-8")
            health,err=frozen.read_day_health_summary(hp,event_date="2026-10-07",cfg=cfg)
            self.assertIsNone(health)
            self.assertIn("JSONDecodeError",err)

    def test_health_reader_preserves_readable_semantic_blocker(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        with tempfile.TemporaryDirectory() as td:
            hp=Path(td)/"day_health_summary.json"
            hp.write_text(json.dumps({"protocol_id":cfg["protocol_id"],"event_date":"2026-10-07","date_status":"STUDY_BLOCKER","study_blocker":"synthetic"}),encoding="utf-8")
            health,err=frozen.read_day_health_summary(hp,event_date="2026-10-07",cfg=cfg)
            self.assertIsNone(err)
            self.assertEqual(health["date_status"],"STUDY_BLOCKER")

    def test_health_reader_wrong_type_status_is_integrity_failure_not_crash(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        for bad_status in (["VALID"], {"status":"VALID"}):
            with self.subTest(bad_status=bad_status), tempfile.TemporaryDirectory() as td:
                hp=Path(td)/"day_health_summary.json"
                hp.write_text(json.dumps({
                    "protocol_id":cfg["protocol_id"],
                    "event_date":"2026-10-07",
                    "date_status":bad_status,
                    "study_blocker":None,
                }),encoding="utf-8")
                health,err=frozen.read_day_health_summary(hp,event_date="2026-10-07",cfg=cfg)
                self.assertIsNone(health)
                self.assertIn("date_status must be a string",err)

    def test_health_reader_semantic_blocker_has_priority_over_unknown_status(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        with tempfile.TemporaryDirectory() as td:
            hp=Path(td)/"day_health_summary.json"
            hp.write_text(json.dumps({
                "protocol_id":cfg["protocol_id"],
                "event_date":"2026-10-07",
                "date_status":"UNKNOWN_STATUS",
                "study_blocker":"synthetic semantic mismatch",
            }),encoding="utf-8")
            health,err=frozen.read_day_health_summary(hp,event_date="2026-10-07",cfg=cfg)
            self.assertIsNone(err)
            self.assertEqual(health["study_blocker"],"synthetic semantic mismatch")

    def test_health_reader_semantic_blocker_has_priority_over_wrong_type_status(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        with tempfile.TemporaryDirectory() as td:
            hp=Path(td)/"day_health_summary.json"
            hp.write_text(json.dumps({
                "protocol_id":cfg["protocol_id"],
                "event_date":"2026-10-07",
                "date_status":["VALID"],
                "study_blocker":"synthetic semantic mismatch",
            }),encoding="utf-8")
            health,err=frozen.read_day_health_summary(hp,event_date="2026-10-07",cfg=cfg)
            self.assertIsNone(err)
            self.assertEqual(health["study_blocker"],"synthetic semantic mismatch")

    def test_endpoint_wrong_type_status_becomes_integrity_failure(self):
        from src.v3.study1 import frozen
        import scripts.v3.evaluate_study1_after_endpoint as endpoint
        repo_root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(repo_root)
        d=frozen.planned_dates(cfg)[0]
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            day=base/d
            day.mkdir(parents=True)
            (day/"day_health_summary.json").write_text(json.dumps({
                "protocol_id":cfg["protocol_id"],
                "event_date":d,
                "date_status":["VALID"],
                "study_blocker":None,
            }),encoding="utf-8")
            out=base/"endpoint.json"
            argv=["evaluate_study1_after_endpoint.py","--input-root",str(base),"--output",str(out)]
            with mock.patch.object(endpoint,"endpoint_unlock_time",return_value=datetime(2000,1,1,tzinfo=ZoneInfo("UTC"))), \
                 mock.patch.object(sys,"argv",argv):
                rc=endpoint.main()
            self.assertEqual(rc,0)
            result=json.loads(out.read_text(encoding="utf-8"))
            first=result["date_results"][0]
            self.assertEqual(first["status"],"INTEGRITY_FAILURE_RETAIN_IN_DENOMINATOR")
            self.assertIn("date_status must be a string",first["integrity_failure"])
            self.assertEqual(result["decision"],"CLOSE_OPERATIONAL_RELIABILITY")

    def test_endpoint_readable_semantic_blocker_beats_status_schema_error(self):
        from src.v3.study1 import frozen
        import scripts.v3.evaluate_study1_after_endpoint as endpoint
        repo_root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(repo_root)
        d=frozen.planned_dates(cfg)[0]
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            day=base/d
            day.mkdir(parents=True)
            (day/"day_health_summary.json").write_text(json.dumps({
                "protocol_id":cfg["protocol_id"],
                "event_date":d,
                "date_status":"UNKNOWN_STATUS",
                "study_blocker":"synthetic semantic mismatch",
            }),encoding="utf-8")
            out=base/"endpoint.json"
            argv=["evaluate_study1_after_endpoint.py","--input-root",str(base),"--output",str(out)]
            with mock.patch.object(endpoint,"endpoint_unlock_time",return_value=datetime(2000,1,1,tzinfo=ZoneInfo("UTC"))), \
                 mock.patch.object(sys,"argv",argv):
                rc=endpoint.main()
            self.assertEqual(rc,3)
            result=json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(result["decision"],"CLOSE_SEMANTIC_OR_TERMS_BLOCKER")
            self.assertEqual(result["blocking_date"],d)
            self.assertEqual(result["study_blocker"],"synthetic semantic mismatch")
            self.assertFalse(result["primary_endpoint_evaluated"])

    def test_evaluator_rejects_current_pair_with_missing_city_id(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        ladder={"thresholds":[{"threshold":"70","payout_time":9999999999},{"threshold":"71","payout_time":9999999999}],
                "adjacent_pairs":[{"city_id":"NYC","event_date":"2026-10-07","lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2}]}
        pid=frozen.pair_id("NYC","70",1,2)
        rec={"slot_index":0,"pair_id":pid,"quote_status":"QUOTE_ELIGIBLE","request_start_epoch":1,"snapshot":{"rows":[{"conid":1,"ask":"0.40"},{"conid":2,"ask":"0.50"}]}}
        with self.assertRaises(RuntimeError):
            frozen.evaluate_city_date([rec],city_id="NYC",ladder=ladder,cfg=cfg,valid_slot_indices={0})

    def test_evaluator_rejects_eligible_failure_field_conflict(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        ladder={"thresholds":[{"threshold":"70","payout_time":9999999999},{"threshold":"71","payout_time":9999999999}],
                "adjacent_pairs":[{"city_id":"NYC","event_date":"2026-10-07","lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2}]}
        pid=frozen.pair_id("NYC","70",1,2)
        rec={"slot_index":0,"city_id":"NYC","pair_id":pid,"quote_status":"QUOTE_ELIGIBLE","failure_class":"structural_failure","request_start_epoch":1,"snapshot":{"rows":[{"conid":1,"ask":"0.40"},{"conid":2,"ask":"0.50"}]}}
        with self.assertRaises(RuntimeError):
            frozen.evaluate_city_date([rec],city_id="NYC",ladder=ladder,cfg=cfg,valid_slot_indices={0})

    def test_evaluator_rejects_unknown_status_in_valid_slot(self):
        from src.v3.study1 import frozen
        root=Path(__file__).resolve().parents[2]
        cfg=frozen.load_frozen_config(root)
        ladder={"thresholds":[{"threshold":"70","payout_time":9999999999},{"threshold":"71","payout_time":9999999999}],
                "adjacent_pairs":[{"city_id":"NYC","event_date":"2026-10-07","lower_threshold":"70","higher_threshold":"71","lower_yes_conid":1,"higher_no_conid":2}]}
        pid=frozen.pair_id("NYC","70",1,2)
        rec={"slot_index":0,"city_id":"NYC","pair_id":pid,"quote_status":"UNKNOWN_STATUS","request_start_epoch":1}
        with self.assertRaises(RuntimeError):
            frozen.evaluate_city_date([rec],city_id="NYC",ladder=ladder,cfg=cfg,valid_slot_indices={0})
