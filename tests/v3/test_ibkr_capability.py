import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.v3.audit.ibkr_capability import (
    _safe_auth_summary,
    _safe_market_snapshot,
    decode_market_data_availability,
    find_markets,
    run_http_capability_audit,
)
from src.v3.ibkr.client import IBKRAPIError, IBKRClient
from src.v3.ibkr.websocket_probe import websocket_url_from_base


class TestMarketDataAvailability(unittest.TestCase):
    def test_realtime_book(self):
        got = decode_market_data_availability("RpB")
        self.assertEqual(got.delivery, "real_time")
        self.assertEqual(got.snapshot_or_consolidated, "consolidated")
        self.assertTrue(got.top_of_book)

    def test_delayed(self):
        got = decode_market_data_availability("DPB")
        self.assertEqual(got.delivery, "delayed")
        self.assertEqual(got.snapshot_or_consolidated, "snapshot")
        self.assertTrue(got.top_of_book)


class TestDiscovery(unittest.TestCase):
    def test_weather_market_filter(self):
        payload = {
            "categories": {
                "g1": {
                    "name": "Weather",
                    "markets": [
                        {"name": "New York City Daily Temperature High", "symbol": "NYH", "exchange": "FORECASTX", "conid": 11},
                        {"name": "Rainfall", "symbol": "RAIN", "exchange": "FORECASTX", "conid": 12},
                    ],
                },
                "g2": {
                    "name": "Economics",
                    "markets": [{"name": "Fed Funds", "symbol": "FF", "exchange": "FORECASTX", "conid": 13}],
                },
            }
        }
        total, matches = find_markets(payload, r"temperature|weather")
        self.assertEqual(total, 3)
        # Weather category metadata is intentionally part of the filter haystack.
        self.assertEqual([m["conid"] for m in matches], [11, 12])

    def test_websocket_url(self):
        self.assertEqual(
            websocket_url_from_base("https://localhost:5000/v1/api"),
            "wss://localhost:5000/v1/api/ws",
        )


class TestSafeSummaries(unittest.TestCase):
    def test_auth_redacts_identity_fields(self):
        raw = {"success": {"value": {"authenticated": True, "connected": True, "established": True, "MAC": "do-not-store", "session": "secret"}}}
        safe = _safe_auth_summary(raw)
        self.assertTrue(safe["authenticated"])
        self.assertNotIn("MAC", safe)
        self.assertNotIn("session", safe)

    def test_market_snapshot_keeps_bbo_without_raw_payload(self):
        raw = [{"conid": 123, "_updated": 1712596911593, "84": "0.42", "86": "0.44", "88": "7", "85": "9", "6509": "RpB", "server_id": "q1"}]
        safe = _safe_market_snapshot(raw)
        self.assertEqual(safe[0]["bid"], "0.42")
        self.assertEqual(safe[0]["ask"], "0.44")
        self.assertNotIn("server_id", safe[0])


class TestRedactionAndDeterminism(unittest.TestCase):
    def test_http_error_does_not_persist_response_body(self):
        client = IBKRClient(base_url="https://localhost:5000/v1/api")
        response = Mock(ok=False, status_code=401, text="account=SECRET token=SECRET", content=b"x")
        client.session.request = Mock(return_value=response)
        with self.assertRaises(IBKRAPIError) as ctx:
            client.auth_status()
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_auto_weather_populates_contracts_and_bbo(self):
        class FakeClient:
            base_url = "https://localhost:5000/v1/api"
            verify_tls = False
            def auth_status(self): return {"authenticated": True, "connected": True, "established": True}
            def tickle(self): return {"success": {"value": {"session": "secret"}}}
            def accounts(self): return {"accounts": []}
            def category_tree(self):
                return {"categories": {"g": {"name": "Temperature", "markets": [{"name": "NYC Daily Temperature High", "symbol": "NYH", "exchange": "FORECASTX", "conid": 100}]}}}
            def forecast_market(self, underlying_conid, *, exchange="FORECASTX"):
                return {"market_name": "NYC Daily Temperature High", "exchange": "FORECASTX", "symbol": "NYH", "contracts": [
                    {"conid": 201, "side": "Y", "expiration": "20261003", "strike": 80, "strike_label": "Above 80", "underlying_conid": 100},
                    {"conid": 202, "side": "N", "expiration": "20261003", "strike": 80, "strike_label": "Above 80", "underlying_conid": 100},
                ]}
            def contract_details(self, conid): return {"conid_yes": 201, "conid_no": 202, "market_name": "NYC Daily Temperature High"}
            def contract_rules(self, conid): return {"source_agency": "NWS", "market_name": "NYC Daily Temperature High"}
            def marketdata_snapshot(self, conids, *, fields=None): return [{"conid": c, "84": "0.40", "86": "0.42", "6509": "RpB"} for c in conids]
        report = run_http_capability_audit(FakeClient(), auto_weather=True)
        self.assertEqual(report["auto_weather_discovery"]["matching_market_count"], 1)
        self.assertEqual(len(report["market_snapshot"]), 2)
        self.assertEqual(report["contract_rules"]["source_agency"], "NWS")


class TestOperationalCLI(unittest.TestCase):
    def test_direct_help_runs_from_repo_root(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "scripts" / "v3" / "run_ibkr_capability_audit.py"
        proc = subprocess.run([sys.executable, str(script), "--help"], cwd=repo_root, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Read-only V3 IBKR / ForecastEx capability audit", proc.stdout)


if __name__ == "__main__":
    unittest.main()
