from __future__ import annotations

from datetime import date, datetime, timezone
import unittest

from src.v3.study2.model_ready import (
    build_state_rows,
    canonical_numeric_observations,
    local_day_grid,
    parse_metar_issue_utc,
    split_for_date,
)


class TestStudy2ModelReady(unittest.TestCase):
    def test_split_contract_boundaries(self):
        self.assertEqual(split_for_date(date(2024, 1, 1)), "train")
        self.assertEqual(split_for_date(date(2024, 12, 31)), "train")
        self.assertEqual(split_for_date(date(2025, 1, 1)), "calibration")
        self.assertEqual(split_for_date(date(2026, 10, 6)), "historical_validation")

    def test_dst_fallback_metars_resolve_to_distinct_utc(self):
        a = parse_metar_issue_utc(
            metar="KMDW 020653Z 27003KT 10SM 07/03 A3016",
            event_date=date(2025, 11, 2),
            valid_local="2025-11-02 01:53",
        )
        b = parse_metar_issue_utc(
            metar="KMDW 020753Z 31004KT 10SM 08/03 A3017",
            event_date=date(2025, 11, 2),
            valid_local="2025-11-02 01:53",
        )
        self.assertNotEqual(a, b)
        self.assertEqual(a, datetime(2025, 11, 2, 6, 53, tzinfo=timezone.utc))
        self.assertEqual(b, datetime(2025, 11, 2, 7, 53, tzinfo=timezone.utc))

    def test_null_auto_duplicate_does_not_create_numeric_conflict(self):
        rows = [
            {
                "valid_local": "2024-03-30 12:55",
                "tmpf": None,
                "metar": "KMDW 301755Z AUTO 33013KT 10SM",
                "observation_key": "a",
            },
            {
                "valid_local": "2024-03-30 12:55",
                "tmpf": 63.0,
                "metar": "KMDW 301755Z 33013KT 10SM",
                "observation_key": "b",
            },
        ]
        obs, qc = canonical_numeric_observations(rows, event_date=date(2024, 3, 30))
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["tmpf"], 63.0)
        self.assertEqual(qc["null_temperature_row_count"], 1)

    def test_local_day_grid_handles_dst(self):
        spring = local_day_grid(date(2026, 3, 8))
        fall = local_day_grid(date(2025, 11, 2))
        normal = local_day_grid(date(2026, 3, 9))
        self.assertEqual(len(spring), 46)
        self.assertEqual(len(fall), 50)
        self.assertEqual(len(normal), 48)

    def test_state_rows_never_use_future_observation(self):
        rows = [
            {
                "tmpf": 50.0,
                "observation_utc": datetime(2026, 7, 15, 6, 53, tzinfo=timezone.utc),
                "observation_local": datetime(2026, 7, 15, 1, 53, tzinfo=timezone.utc),
            },
            {
                "tmpf": 60.0,
                "observation_utc": datetime(2026, 7, 15, 7, 53, tzinfo=timezone.utc),
                "observation_local": datetime(2026, 7, 15, 2, 53, tzinfo=timezone.utc),
            },
        ]
        states = build_state_rows(
            event_date=date(2026, 7, 15),
            observations=rows,
            wu_max_f=80.0,
        )
        for s in states:
            if s["latest_observation_utc"] is not None:
                self.assertLessEqual(s["latest_observation_utc"], s["decision_utc"])


if __name__ == "__main__":
    unittest.main()
