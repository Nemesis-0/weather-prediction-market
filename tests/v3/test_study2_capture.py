from __future__ import annotations

import inspect
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.v3.study2 import capture


class TestStudy2Capture(unittest.TestCase):
    def test_normalize_quote_preserves_missingness_and_delivery(self):
        item = {"conid": 1, "84": "0.20", "85": "12", "6509": "RPB", "_updated": 123}
        out = capture.normalize_quote_item(
            item,
            contract_meta={"threshold": "68", "side": "Y"},
            session_id="s",
            cycle_id=1,
            batch_id=1,
            request_sent_utc="a",
            response_received_utc="b",
            request_monotonic_ns=100,
            response_monotonic_ns=200,
            batch_payload_sha256="abc",
        )
        self.assertTrue(out["field_presence"]["bid"])
        self.assertFalse(out["field_presence"]["ask"])
        self.assertEqual(out["availability_decoded"]["delivery"], "real_time")
        self.assertEqual(out["side"], "Y")
        self.assertEqual(out["batch_payload_sha256"], "abc")

    def test_contract_index_contains_both_sides(self):
        target = {
            "event_date": "2026-10-06",
            "station_code": "KMDW",
            "product_code": "UHMDW",
            "ladder": {"thresholds": [
                {"threshold": "68", "yes_conid": 1, "no_conid": 2, "payout": "1", "price_increment": "0.01"}
            ]},
        }
        out = capture._contract_index(target)
        self.assertEqual(out[1]["side"], "Y")
        self.assertEqual(out[2]["side"], "N")

    def test_nonempty_session_directory_fails_closed_before_client_access(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "session"
            out.mkdir()
            sentinel = out / "sentinel.txt"
            sentinel.write_text("preserve", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "refusing to reuse non-empty"):
                capture.run_development_session(
                    client=object(),
                    event_date=date(2026, 10, 7),
                    output_dir=out,
                    duration_seconds=1,
                    config=capture.Study2CaptureConfig(enable_public_sources=False),
                )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")

    def test_source_is_read_only_and_has_no_alpha_logic(self):
        src = inspect.getsource(capture)
        for token in ["conservative_cost", "compute_pnl", "opportunity_flag", "place_order", "submit_order", "cancel_order"]:
            self.assertNotIn(token, src)

    def test_runner_help_is_read_only(self):
        root = Path(__file__).resolve().parents[2]
        p = subprocess.run(
            [sys.executable, str(root / "scripts/v3/run_study2_development.py"), "--help"],
            cwd=root,
            text=True,
            capture_output=True,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("read-only", p.stdout.lower())


if __name__ == "__main__":
    unittest.main()
