from __future__ import annotations

from datetime import datetime, timezone
import unittest

from src.v3.study2.economic_kill import (
    _quote_quality,
    build_weather_state,
)


class TestStudy2EconomicKill(unittest.TestCase):
    def test_realtime_one_sided_ask_is_eligible_and_comma_size_parses(self):
        q = {
            "availability_decoded": {"delivery": "real_time", "top_of_book": False},
            "field_presence": {"ask": True, "ask_size": True, "bid": False, "bid_size": False},
            "ask": "0.02",
            "ask_size": "7,520",
        }
        ok, reasons, ask, size = _quote_quality(q)
        self.assertTrue(ok)
        self.assertEqual(reasons, [])
        self.assertEqual(ask, 0.02)
        self.assertEqual(size, 7520.0)

    def test_field_presence_is_required(self):
        q = {
            "availability_decoded": {"delivery": "real_time", "top_of_book": False},
            "field_presence": {"ask": False, "ask_size": False},
            "ask": "0.02",
            "ask_size": "7,520",
        }
        ok, reasons, _, _ = _quote_quality(q)
        self.assertFalse(ok)
        self.assertIn("ask_field_not_present", reasons)
        self.assertIn("ask_size_field_not_present", reasons)

    def test_non_realtime_is_rejected(self):
        q = {
            "availability_decoded": {"delivery": None, "top_of_book": False},
            "field_presence": {"ask": True, "ask_size": True},
            "ask": "0.02",
            "ask_size": "7,520",
        }
        ok, reasons, _, _ = _quote_quality(q)
        self.assertFalse(ok)
        self.assertIn("not_real_time", reasons)

    def test_weather_state_respects_receive_time_and_corrections(self):
        obs = [
            {
                "source_received_utc": "2026-10-07T15:00:00+00:00",
                "tmpf": 60.0,
                "metar": "KMDW 071453Z AUTO ...",
            },
            {
                "source_received_utc": "2026-10-07T16:00:00+00:00",
                "tmpf": 61.0,
                "metar": "KMDW 071553Z AUTO ...",
            },
            {
                "source_received_utc": "2026-10-07T17:00:00+00:00",
                "tmpf": 62.0,
                "metar": "KMDW 071453Z COR ...",
            },
        ]
        q = datetime(2026, 10, 7, 16, 30, tzinfo=timezone.utc)
        s = build_weather_state(obs, quote_utc=q, event_date="2026-10-07")
        self.assertIsNotNone(s)
        self.assertAlmostEqual(s["current_temp_f"], 61.0)
        self.assertAlmostEqual(s["running_max_f"], 61.0)
        self.assertAlmostEqual(s["temp_change_60m_f"], 1.0)


if __name__ == "__main__":
    unittest.main()
