from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from src.v3.study2 import historical


class TestStudy2Historical(unittest.TestCase):
    def test_default_probe_contains_dst_transition_and_adjacent_dates(self):
        values = set(historical.DEFAULT_PROBE_DATES)
        for d in [
            date(2026, 3, 7), date(2026, 3, 8), date(2026, 3, 9),
            date(2025, 11, 1), date(2025, 11, 2), date(2025, 11, 3),
        ]:
            self.assertIn(d, values)

    def test_normalize_rejects_current_or_future_date(self):
        with self.assertRaisesRegex(ValueError, "before current Chicago date"):
            historical.normalize_probe_dates([date(2026, 10, 7)], today=date(2026, 10, 7))

    def test_normalize_deduplicates_preserving_order(self):
        a, b = date(2026, 1, 1), date(2026, 1, 2)
        self.assertEqual(
            historical.normalize_probe_dates([b, a, b], today=date(2026, 10, 7)),
            [b, a],
        )

    def test_output_dir_reuse_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "existing"
            path.mkdir()
            with self.assertRaisesRegex(FileExistsError, "refusing reuse"):
                historical.ensure_new_output_dir(path)

    def test_summarize_iem_flags_duplicate_local_clock_labels(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "sources"
            src.mkdir(parents=True)
            rows = [
                {"valid_local": "2025-11-02 01:53", "metar": "KMDW A"},
                {"valid_local": "2025-11-02 01:53", "metar": "KMDW B"},
            ]
            (src / "weather_observations.jsonl").write_text(
                "\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8"
            )
            out = historical.summarize_iem_date(root, {
                "parse_ok": True,
                "row_count": 2,
                "temperature_row_count": 2,
                "running_max_tmpf": 60.0,
                "station_check_ok": True,
                "date_check_ok": True,
            })
            self.assertEqual(out["duplicate_valid_local_count"], 1)
            self.assertEqual(out["duplicate_valid_local_values"], ["2025-11-02 01:53"])
            self.assertTrue(out["all_archived_rows_have_metar"])

    def test_run_probe_writes_manifest_and_preserves_vintage_limit(self):
        fake_row = {
            "event_date": "2026-01-02",
            "source_pair_ok": True,
            "iem": {"parse_ok": True},
            "wu": {"parse_ok": True},
        }
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "probe"
            with patch("src.v3.study2.historical.probe_one_date", return_value=fake_row):
                summary = historical.run_historical_probe(
                    dates=[date(2026, 1, 2)],
                    output_dir=out,
                    timeout_seconds=1,
                    inter_date_sleep_seconds=0,
                )
            self.assertTrue(summary["all_source_pairs_ok"])
            config = json.loads((out / "probe_config.json").read_text())
            self.assertIn("unproven", config["retrieval_vintage_limitation"])
            self.assertEqual(config["date_selection_basis"], "fixed_source_feasibility_and_dst_clock_probe_not_modeling_sample")
            self.assertTrue((out / "historical_probe_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
