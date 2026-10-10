from __future__ import annotations

import inspect
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.v3.study2 import sources


def wu_fixture(
    *,
    station: str = "KMDW",
    page_date: str = "2026-10-7",
    timezone_name: str = "America/Chicago",
    mode: str = "daily",
    heading: str = "Daily Observations",
    data_results: str = "observations",
    table_class: str = "observations-table",
    temp1: str = "64 °F",
    temp2: str = "68 °F",
) -> str:
    return f"""
    <html><body>
    <airport-body data-location-id="{station}:9:US" data-time-zone="{timezone_name}"
      data-icao-code="{station}" data-country-code="us" data-admin-district-code="il"
      data-city="chicago" data-mode="{mode}" data-date="{page_date}">
      <div class="airport-results" data-results="{data_results}">
        <h2 class="section-title">{heading}</h2>
        <div class="observations-section"><div class="table-scroll">
          <table class="{table_class}">
            <thead><tr><th>Time</th><th>Temperature</th><th>Dew Point</th><th>Humidity</th></tr></thead>
            <tbody>
              <tr><td>8:53 AM</td><td>{temp1}</td><td>48 °F</td><td>55 %</td></tr>
              <tr><td>9:53 AM</td><td>{temp2}</td><td>49 °F</td><td>50 %</td></tr>
            </tbody>
          </table>
        </div></div>
      </div>
    </airport-body>
    </body></html>
    """


class FakeResponse:
    def __init__(self, *, body: bytes, url: str, status_code: int = 200, content_type: str = "text/html") -> None:
        self.content = body
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


class TestStudy2Sources(unittest.TestCase):
    def test_iem_params_use_midway_network_and_routine_special(self):
        params = sources.build_iem_asos_params(date(2026, 10, 7))
        self.assertIn(("station", "MDW"), params)
        self.assertIn(("network", "IL_ASOS"), params)
        self.assertEqual([v for k, v in params if k == "report_type"], ["3", "4"])
        self.assertIn(("tz", "America/Chicago"), params)
        self.assertIn(("year2", "2026"), params)
        self.assertIn(("month2", "10"), params)
        self.assertIn(("day2", "8"), params)

    def test_iem_csv_parser_preserves_raw_metar_and_running_max(self):
        text = (
            "station,valid,tmpf,dwpf,relh,metar\n"
            "MDW,2026-10-07 08:53,61,49,64,KMDW 071353Z 01005KT 10SM CLR 16/09 A3000\n"
            "MDW,2026-10-07 09:15,63,50,62,KMDW 071415Z 02006KT 10SM CLR 17/10 A3001\n"
        )
        out = sources.parse_iem_asos_csv(text, event_date=date(2026, 10, 7))
        self.assertEqual(out["row_count"], 2)
        self.assertEqual(out["temperature_row_count"], 2)
        self.assertEqual(out["running_max_tmpf"], 63.0)
        self.assertTrue(out["station_check_ok"])
        self.assertTrue(out["date_check_ok"])
        self.assertTrue(out["rows"][0]["metar"].startswith("KMDW "))
        self.assertTrue(out["rows"][0]["valid_local_date_ok"])

    def test_iem_csv_station_mismatch_fails_closed(self):
        text = (
            "station,valid,tmpf,dwpf,relh,metar\n"
            "ORD,2026-10-07 08:53,61,49,64,KORD 071353Z 01005KT 10SM CLR 16/09 A3000\n"
        )
        with self.assertRaisesRegex(sources.Study2SourceError, "station identity mismatch"):
            sources.parse_iem_asos_csv(text, event_date=date(2026, 10, 7))

    def test_iem_csv_next_day_valid_local_fails_closed(self):
        text = (
            "station,valid,tmpf,dwpf,relh,metar\n"
            "MDW,2026-10-08 09:53,67,54,63,KMDW 081453Z 29010KT 10SM CLR 19/12 A2918\n"
        )
        with self.assertRaisesRegex(sources.Study2SourceError, "valid-local date mismatch"):
            sources.parse_iem_asos_csv(text, event_date=date(2026, 10, 7))

    def test_wu_parser_binds_daily_observations_container(self):
        fixture = wu_fixture()
        out = sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))
        self.assertEqual(out["max_temperature_f"], 68.0)
        self.assertEqual(out["observation_count"], 2)
        self.assertEqual(out["temperature_unit"], "F")
        self.assertEqual(out["page_identity"]["icao_code"], "KMDW")
        self.assertEqual(out["page_identity"]["page_date"], "2026-10-07")
        self.assertEqual(out["finality_status"], "UNRESOLVED_DEVELOPMENT")
        self.assertIn("daily_observations_only", out["guardrail"])

    def test_wu_hourly_forecast_table_cannot_masquerade_as_daily_observations(self):
        fixture = wu_fixture(heading="Hourly Forecast", data_results="forecast", table_class="observations-table")
        with self.assertRaisesRegex(sources.Study2SourceError, "table identity unresolved"):
            sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))

    def test_wu_celsius_temperature_fails_closed(self):
        fixture = wu_fixture(temp1="17.8 °C", temp2="20 °C")
        with self.assertRaisesRegex(sources.Study2SourceError, "Celsius"):
            sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))

    def test_wu_mixed_units_in_single_cell_fail_closed(self):
        fixture = wu_fixture(
            temp1="20 °C (68 °F)",
            temp2="72 °F",
        )
        with self.assertRaisesRegex(
            sources.Study2SourceError,
            "mixed/ambiguous units",
        ):
            sources.parse_wu_daily_observations_html(
                fixture,
                event_date=date(2026, 10, 7),
            )

    def test_wu_header_row_unit_conflict_fails_closed(self):
        fixture = wu_fixture(
            temp1="20",
            temp2="68 °F",
        ).replace(
            "<th>Temperature</th>",
            "<th>Temperature (°C)</th>",
        )

        with self.assertRaisesRegex(
            sources.Study2SourceError,
            "header/row unit conflict",
        ):
            sources.parse_wu_daily_observations_html(
                fixture,
                event_date=date(2026, 10, 7),
            )

    def test_wu_unknown_temperature_unit_fails_closed(self):
        fixture = wu_fixture(temp1="64", temp2="68")
        with self.assertRaisesRegex(sources.Study2SourceError, "unit"):
            sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))

    def test_wu_wrong_station_fails_closed(self):
        fixture = wu_fixture(station="KORD")
        with self.assertRaisesRegex(sources.Study2SourceError, "station identity mismatch"):
            sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))

    def test_wu_wrong_page_date_fails_closed(self):
        fixture = wu_fixture(page_date="2026-10-8")
        with self.assertRaisesRegex(sources.Study2SourceError, "page date mismatch"):
            sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))

    def test_wu_wrong_timezone_fails_closed(self):
        fixture = wu_fixture(timezone_name="America/New_York")
        with self.assertRaisesRegex(sources.Study2SourceError, "timezone mismatch"):
            sources.parse_wu_daily_observations_html(fixture, event_date=date(2026, 10, 7))

    def test_wu_final_url_station_and_date_are_validated(self):
        good = sources.validate_wu_final_url(
            "https://www.wunderground.com/history/daily/us/il/chicago/KMDW/date/2026-10-7",
            event_date=date(2026, 10, 7),
        )
        self.assertEqual(good["station_code"], "KMDW")
        with self.assertRaisesRegex(sources.Study2SourceError, "station mismatch"):
            sources.validate_wu_final_url(
                "https://www.wunderground.com/history/daily/us/il/chicago/KORD/date/2026-10-7",
                event_date=date(2026, 10, 7),
            )
        with self.assertRaisesRegex(sources.Study2SourceError, "date mismatch"):
            sources.validate_wu_final_url(
                "https://www.wunderground.com/history/daily/us/il/chicago/KMDW/date/2026-10-8",
                event_date=date(2026, 10, 7),
            )

    def test_wu_parse_failure_archives_raw_response_before_parse(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            recorder = sources.Study2PublicSourceRecorder(
                output_dir=out, event_date=date(2026, 10, 7), session_id="s"
            )
            malformed = wu_fixture(heading="Hourly Forecast", data_results="forecast").encode()
            recorder.session = FakeSession(FakeResponse(
                body=malformed,
                url="https://www.wunderground.com/history/daily/us/il/chicago/KMDW/date/2026-10-7",
            ))
            with self.assertRaises(sources.Study2SourceError):
                recorder.capture_wu(timeout_seconds=1)

            raw_files = list((out / "sources" / "wu_raw").glob("*.html"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].read_bytes(), malformed)
            raw_records = [json.loads(x) for x in (out / "sources" / "raw_fetches.jsonl").read_text().splitlines()]
            failure_records = [json.loads(x) for x in (out / "sources" / "wu_snapshots.jsonl").read_text().splitlines()]
            self.assertEqual(raw_records[0]["payload_sha256"], sources.sha256_bytes(malformed))
            self.assertFalse(failure_records[0]["parse_ok"])
            self.assertEqual(failure_records[0]["payload_sha256"], raw_records[0]["payload_sha256"])
            self.assertEqual(failure_records[0]["raw_file"], raw_records[0]["raw_file"])

    def test_iem_parse_failure_archives_raw_response_before_parse(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            recorder = sources.Study2PublicSourceRecorder(
                output_dir=out, event_date=date(2026, 10, 7), session_id="s"
            )
            bad = (
                "station,valid,tmpf,dwpf,relh,metar\n"
                "MDW,2026-10-08 09:53,67,54,63,KMDW 081453Z 29010KT 10SM CLR 19/12 A2918\n"
            ).encode()
            recorder.session = FakeSession(FakeResponse(
                body=bad,
                url=sources.IEM_ASOS_URL,
                content_type="text/csv",
            ))
            with self.assertRaises(sources.Study2SourceError):
                recorder.capture_iem(timeout_seconds=1)

            raw_files = list((out / "sources" / "iem_raw").glob("*.csv"))
            self.assertEqual(len(raw_files), 1)
            self.assertEqual(raw_files[0].read_bytes(), bad)
            self.assertFalse((out / "sources" / "weather_observations.jsonl").exists())
            failure_records = [json.loads(x) for x in (out / "sources" / "iem_asos_fetches.jsonl").read_text().splitlines()]
            self.assertFalse(failure_records[0]["parse_ok"])
            self.assertEqual(failure_records[0]["payload_sha256"], sources.sha256_bytes(bad))

    def test_wu_url_is_station_and_date_specific(self):
        url = sources.wu_daily_url(date(2026, 10, 7))
        self.assertIn("/KMDW/", url)
        self.assertTrue(url.endswith("/2026-10-7"))

    def test_source_module_contains_no_alpha_or_order_path(self):
        src = inspect.getsource(sources)
        for token in [
            "conservative_cost",
            "compute_pnl",
            "opportunity_flag",
            "place_order(",
            "submit_order(",
            "cancel_order(",
            "/orders",
        ]:
            self.assertNotIn(token, src)


if __name__ == "__main__":
    unittest.main()
