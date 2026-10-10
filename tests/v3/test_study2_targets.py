from __future__ import annotations

import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from src.v3.study2 import targets


class FakeClient:
    def __init__(self):
        self.event_date = date(2026, 10, 6)
        self.yes = {68: 1001, 72: 1003}
        self.no = {68: 1002, 72: 1004}

    def category_tree(self):
        return {
            "categories": {
                "1": {
                    "name": "Weather",
                    "markets": [
                        {"name": "Chicago Daily Temperature High", "symbol": "UHMDW", "exchange": "FORECASTX", "conid": 900},
                        {"name": "New York City Daily Temperature High", "symbol": "UHLGA", "exchange": "FORECASTX", "conid": 901},
                    ],
                }
            }
        }

    def forecast_market(self, conid, exchange="FORECASTX"):
        self.assert_equal(conid, 900)
        contracts = []
        for strike in (68, 72):
            contracts += [
                {"conid": self.yes[strike]},
                {"conid": self.no[strike]},
            ]
        return {"market_name": "Chicago Daily Temperature High", "symbol": "UHMDW", "contracts": contracts}

    @staticmethod
    def assert_equal(a, b):
        if a != b:
            raise AssertionError((a, b))

    def _question(self, strike):
        return f"Will the highest temperature at KMDW exceed {strike} F on October 6, 2026?"

    def contract_details(self, conid):
        for strike in (68, 72):
            if conid in (self.yes[strike], self.no[strike]):
                side = "Y" if conid == self.yes[strike] else "N"
                return {
                    "conid_yes": self.yes[strike],
                    "conid_no": self.no[strike],
                    "question": self._question(strike),
                    "side": side,
                    "strike": float(strike),
                    "symbol": "UHMDW",
                    "market_name": "Chicago Daily Temperature High",
                    "payout": 1.0,
                }
        raise KeyError(conid)

    def contract_rules(self, conid):
        details = self.contract_details(conid)
        strike = int(details["strike"])
        last_trade = int(
            datetime(2026, 10, 6, 23, 59, tzinfo=ZoneInfo("America/Chicago")).timestamp()
        )
        return {
            "source_agency": "Weather Underground",
            "data_and_resolution_link": "https://example.invalid/history/KMDW",
            "description": "Daily high at KMDW",
            "market_rules_link": "https://example.invalid/terms.pdf",
            "payout": "$1.00",
            "price_increment": "$0.01",
            "product_code": "UHMDW",
            "last_trade_time": last_trade,
            "release_time": last_trade + 3600,
            "payout_time": last_trade + 7200,
            "exchange_timezone": "US/Central",
            "threshold": str(float(strike)),
        }

    def contract_schedules(self, conid):
        return {
            "timezone": "America/Chicago",
            "trading_schedules": [
                {
                    "day_of_week": "Tuesday",
                    "trading_times": [{"open": "12:00 AM", "close": "11:59 PM"}],
                }
            ],
        }


class TestStudy2Targets(unittest.TestCase):
    def test_chicago_local_date_is_timezone_aware(self):
        dt = datetime(2026, 10, 7, 3, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(targets.chicago_local_date(dt), date(2026, 10, 6))

    def test_discovers_only_uhmdw(self):
        out = targets.discover_kmdw_market(FakeClient())
        self.assertEqual(out["discovery"]["symbol"], "UHMDW")
        self.assertEqual(out["market"]["market_name"], "Chicago Daily Temperature High")

    def test_target_snapshot_has_full_yes_no_ladder(self):
        client = FakeClient()
        now_epoch = datetime(2026, 10, 6, 10, 0, tzinfo=ZoneInfo("America/Chicago")).timestamp()
        out = targets.collect_kmdw_target_snapshot(
            client,
            event_date=date(2026, 10, 6),
            now_epoch=now_epoch,
            terms_dir=None,
        )
        self.assertEqual(out["event_date"], "2026-10-06")
        self.assertEqual(out["quote_conids"], [1001, 1002, 1003, 1004])
        self.assertTrue(out["schedule_status"]["open"])
        self.assertFalse(out["terms_archive"]["attempted"])
        self.assertEqual([x["threshold"] for x in out["ladder"]["thresholds"]], ["68", "72"])

    def test_no_study1_frozen_or_cost_dependency(self):
        from pathlib import Path
        src = Path(targets.__file__).read_text(encoding="utf-8")
        self.assertNotIn("study1.frozen", src)
        self.assertNotIn("conservative_cost", src)


if __name__ == "__main__":
    unittest.main()
