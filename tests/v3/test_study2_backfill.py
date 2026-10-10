from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from src.v3.study2.backfill import (
    build_census,
    inclusive_dates,
    initialize_or_validate_root,
    write_index_and_summary,
)


class TestStudy2Backfill(unittest.TestCase):
    def test_inclusive_dates(self):
        rows = inclusive_dates(
            date(2026, 1, 1), date(2026, 1, 3), today=date(2026, 10, 7)
        )
        self.assertEqual(
            rows, [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
        )

    def test_rejects_today_or_future(self):
        with self.assertRaises(ValueError):
            inclusive_dates(
                date(2026, 10, 6), date(2026, 10, 7), today=date(2026, 10, 7)
            )

    def test_rejects_reverse_range(self):
        with self.assertRaises(ValueError):
            inclusive_dates(
                date(2026, 2, 2), date(2026, 2, 1), today=date(2026, 10, 7)
            )

    def test_census_is_deterministic(self):
        a = build_census(date(2026, 1, 1), date(2026, 1, 3), today=date(2026, 10, 7))
        b = build_census(date(2026, 1, 1), date(2026, 1, 3), today=date(2026, 10, 7))
        self.assertEqual(a["dates"], b["dates"])
        self.assertEqual(a["census_sha256"], b["census_sha256"])
        self.assertEqual(a["date_count"], 3)

    def test_existing_root_with_different_census_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "backfill"
            initialize_or_validate_root(
                output_dir=root,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 3),
                today=date(2026, 10, 7),
            )
            with self.assertRaises(RuntimeError):
                initialize_or_validate_root(
                    output_dir=root,
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 1, 4),
                    today=date(2026, 10, 7),
                )

    def test_summary_counts_negative_zero_positive_without_assumption(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dates = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
            diffs = [-1.0, 0.0, 2.0]
            for d, diff in zip(dates, diffs):
                ddir = root / "dates" / d.isoformat()
                ddir.mkdir(parents=True)
                (ddir / "date_status.json").write_text(
                    json.dumps(
                        {
                            "event_date": d.isoformat(),
                            "status": "PASS",
                            "latest_attempt_id": "x",
                            "iem": {
                                "row_count": 2,
                                "temperature_row_count": 2,
                                "running_max_tmpf": 50.0,
                            },
                            "wu": {"observation_count": 2, "max_temperature_f": 50.0 + diff},
                            "raw_audit": {"all_raw_hashes_match": True},
                            "daily_max_difference_wu_minus_iem_f": diff,
                            "retrieval_vintage": "current_http_retrieval_of_historical_source",
                            "original_settlement_time_vintage_reconstructed": False,
                        }
                    )
                    + "\n"
                )
            s = write_index_and_summary(
                output_dir=root,
                dates=dates,
                run_id="r",
                attempted_this_run=3,
                skipped_pass_this_run=0,
            )
            self.assertEqual(s["daily_max_difference_wu_minus_iem_f_negative_date_count"], 1)
            self.assertEqual(s["daily_max_difference_wu_minus_iem_f_zero_date_count"], 1)
            self.assertEqual(s["daily_max_difference_wu_minus_iem_f_positive_date_count"], 1)
            self.assertTrue(s["all_dates_pass"])


if __name__ == "__main__":
    unittest.main()
