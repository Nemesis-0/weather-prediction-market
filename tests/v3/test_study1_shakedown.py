from __future__ import annotations
import inspect, subprocess, sys, unittest
from pathlib import Path
from src.v3.study1 import collector


class TestStudy1Guardrails(unittest.TestCase):
    def test_rotation_is_deterministic(self):
        markets = [{"market": {"market_name": f"M{i}"}} for i in range(9)]
        a = collector.rotate_markets(markets, rotation_index=1, rotation_modulus=3, max_markets=20)
        b = collector.rotate_markets(markets, rotation_index=1, rotation_modulus=3, max_markets=20)
        self.assertEqual(a, b)
        self.assertEqual([x["market"]["market_name"] for x in a], ["M1", "M4", "M7"])

    def test_sensitive_keys_are_redacted(self):
        payload = {"question": "Public contract text", "accountId": "DO_NOT_KEEP", "nested": {"session": "SECRET", "rule": "keep me"}}
        safe = collector.sanitize_public_payload(payload)
        self.assertEqual(safe["question"], "Public contract text")
        self.assertNotIn("accountId", safe)
        self.assertNotIn("session", safe["nested"])
        self.assertEqual(safe["nested"]["rule"], "keep me")

    def test_quote_record_preserves_missingness(self):
        item = {"conid": 123, "84": "0.42", "6509": "RPB", "_updated": 999}
        rec = collector.quote_record(item, contract_meta={"market_name": "X"}, session_id="s", cycle_id=1, batch_id=1,
                                     request_sent_utc="a", response_received_utc="b", request_monotonic_ns=100, response_monotonic_ns=200)
        self.assertTrue(rec["field_presence"]["bid"])
        self.assertFalse(rec["field_presence"]["ask"])
        self.assertIsNone(rec["ask"])

    def test_collector_source_contains_no_strategy_evaluation_function(self):
        src = inspect.getsource(collector)
        for token in ["compute_pnl", "opportunity_flag", "arbitrage_signal"]:
            self.assertNotIn(token, src)


    def test_active_expiration_uses_nearest_future_last_trade(self):
        class FakeClient:
            def contract_rules(self, conid):
                return {1: {"last_trade_time": 900}, 2: {"last_trade_time": 1200}, 3: {"last_trade_time": 1800}}[conid]
        contracts = [
            {"conid": 1, "expiration": "20261003"},
            {"conid": 2, "expiration": "20261004"},
            {"conid": 3, "expiration": "20261005"},
        ]
        exp, evidence = collector.resolve_active_expiration(FakeClient(), contracts, now_epoch=1000)
        self.assertEqual(exp, "20261004")
        self.assertEqual(len(evidence), 3)

    def test_contract_sampling_preserves_pairs_and_spreads_thresholds(self):
        contracts = []
        for strike in range(70, 80):
            contracts.append({"conid": 1000 + strike * 2, "side": "Y", "strike": float(strike), "strike_label": f"Above {strike}", "expiration": "20261004"})
            contracts.append({"conid": 1001 + strike * 2, "side": "N", "strike": float(strike), "strike_label": f"Above {strike}", "expiration": "20261004"})
        selected = collector.select_strategy_blind_contracts(contracts, expiration="20261004", contracts_per_market=8)
        self.assertEqual(len(selected), 8)
        strikes = sorted({x["strike"] for x in selected})
        self.assertEqual(len(strikes), 4)
        self.assertEqual(strikes[0], 70.0)
        self.assertEqual(strikes[-1], 79.0)
        for strike in strikes:
            self.assertEqual({x["side"] for x in selected if x["strike"] == strike}, {"Y", "N"})

    def test_rule_audit_covers_each_market_before_extra_thresholds(self):
        index = {}
        conids = []
        c = 1
        for market in ["A", "B", "C"]:
            for strike in [1.0, 2.0]:
                for side in ["Y", "N"]:
                    index[c] = {"market_name": market, "expiration": "20261004", "strike": strike, "side": side}
                    conids.append(c)
                    c += 1
        chosen = collector.select_rule_audit_conids(conids, index, limit=6)
        self.assertEqual(len(chosen), 6)
        self.assertEqual({index[x]["market_name"] for x in chosen}, {"A", "B", "C"})
        for market in ["A", "B", "C"]:
            self.assertEqual({index[x]["side"] for x in chosen if index[x]["market_name"] == market}, {"Y", "N"})

    def test_schedule_archive_is_one_per_market(self):
        class FakeClient:
            def contract_schedules(self, conid):
                return {"timezone": "US/Central", "trading_schedules": [{"day_of_week": "Friday", "trading_times": []}]}
        index = {1: {"market_name": "A"}, 2: {"market_name": "A"}, 3: {"market_name": "B"}}
        out = collector.archive_schedules(FakeClient(), [1, 2, 3], index)
        self.assertEqual([x["market_name"] for x in out], ["A", "B"])
        self.assertTrue(all("schedule_sha256" in x for x in out))


    def test_rule_audit_limit_fail_fast_present(self):
        src = inspect.getsource(collector.run_session)
        self.assertIn("required_rule_contracts = 2 * len(selected)", src)
        self.assertIn("need at least", src)

    def test_rule_audit_semantic_fail_fast_present(self):
        src = inspect.getsource(collector.run_session)
        self.assertIn('sides != {"Y", "N"}', src)
        self.assertIn("Rule audit failed complete YES/NO semantic coverage", src)

    def test_schedule_fail_fast_present(self):
        src = inspect.getsource(collector.run_session)
        self.assertIn("Trading-schedule audit incomplete before collection", src)

    def test_daily_runner_no_partial_rule_limit(self):
        root = Path(__file__).resolve().parents[2]
        daily = (root / "scripts/v3/run_study1_daily.sh").read_text()
        self.assertNotIn("--rule-audit-contract-limit 24", daily)

    def test_runner_help(self):
        root = Path(__file__).resolve().parents[2]
        proc = subprocess.run([sys.executable, str(root / "scripts/v3/run_study1_shakedown.py"), "--help"], cwd=root, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("strategy-blind", proc.stdout.lower())


if __name__ == "__main__":
    unittest.main()
