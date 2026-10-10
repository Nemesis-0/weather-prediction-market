"""Read-only public weather and settlement-source capture for V3 Study 2 H0.

This module deliberately records source state and provenance only.  It does not
turn temperatures into probabilities, candidate flags, PnL, or trading actions.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

SOURCES_VERSION = "v3_s2_h0_sources_2"
IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
IEM_NETWORK = "IL_ASOS"
IEM_STATION_ID = "MDW"
EXPECTED_ICAO = "KMDW"
WU_DAILY_URL = "https://www.wunderground.com/history/daily/us/il/chicago/KMDW/date/{date_path}"
PUBLIC_USER_AGENT = (
    "weather-prediction-market-research/Study2-H0 "
    "(+read-only research provenance capture)"
)


class Study2SourceError(RuntimeError):
    """Raised when a public source request or semantic parse is unusable."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_sha256(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(raw)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text in {"", "M", "NA", "N/A", "None", "null", "--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_iem_asos_params(event_date: date) -> list[tuple[str, str]]:
    """Build an event-local-day request using IEM routine + special METARs.

    IEM identifies Chicago Midway as station ``MDW`` in ``IL_ASOS`` even though
    the raw METAR ICAO token is ``KMDW``.  The end date is exclusive.
    """
    end = event_date + timedelta(days=1)
    return [
        ("station", IEM_STATION_ID),
        ("network", IEM_NETWORK),
        ("data", "tmpf"),
        ("data", "dwpf"),
        ("data", "relh"),
        ("data", "metar"),
        ("year1", str(event_date.year)),
        ("month1", str(event_date.month)),
        ("day1", str(event_date.day)),
        ("year2", str(end.year)),
        ("month2", str(end.month)),
        ("day2", str(end.day)),
        ("tz", "America/Chicago"),
        ("format", "onlycomma"),
        ("latlon", "no"),
        ("elev", "no"),
        ("missing", "M"),
        ("trace", "T"),
        ("direct", "no"),
        ("report_type", "3"),
        ("report_type", "4"),
    ]


def parse_iem_asos_csv(text: str, *, event_date: date) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(StringIO(text))
    fieldnames = [str(x).strip() for x in (reader.fieldnames or []) if x is not None]
    required = {"station", "valid", "tmpf", "metar"}
    if not required.issubset(set(fieldnames)):
        raise Study2SourceError(
            f"IEM ASOS CSV missing required columns: {sorted(required - set(fieldnames))}"
        )

    bad_station: list[str] = []
    bad_icao: list[str] = []
    bad_dates: list[str] = []

    for raw in reader:
        station = str(raw.get("station") or "").strip()
        valid = str(raw.get("valid") or "").strip()
        metar = str(raw.get("metar") or "").strip()
        if not station or not valid:
            continue

        if station not in {IEM_STATION_ID, EXPECTED_ICAO}:
            bad_station.append(station)

        metar_icao_ok = (not metar) or metar.startswith(f"{EXPECTED_ICAO} ")
        if not metar_icao_ok:
            bad_icao.append(metar.split(" ", 1)[0] if metar else "<missing>")

        try:
            valid_date = date.fromisoformat(valid[:10])
        except ValueError:
            bad_dates.append(valid)
            valid_date = None
        valid_local_date_ok = valid_date == event_date
        if not valid_local_date_ok and valid not in bad_dates:
            bad_dates.append(valid)

        rows.append({
            "station": station,
            "valid_local": valid,
            "valid_local_date_ok": valid_local_date_ok,
            "tmpf": _float_or_none(raw.get("tmpf")),
            "dwpf": _float_or_none(raw.get("dwpf")),
            "relh": _float_or_none(raw.get("relh")),
            "metar": metar or None,
            "metar_icao_ok": metar_icao_ok,
            "source_row_sha256": canonical_json_sha256(raw),
        })

    if bad_station:
        raise Study2SourceError(
            f"IEM station identity mismatch: expected MDW/KMDW, observed {sorted(set(bad_station))}"
        )
    if bad_icao:
        raise Study2SourceError(
            f"IEM METAR ICAO mismatch: expected {EXPECTED_ICAO}, observed {sorted(set(bad_icao))}"
        )
    if bad_dates:
        raise Study2SourceError(
            f"IEM valid-local date mismatch: expected {event_date.isoformat()}, observed {bad_dates[:5]}"
        )

    temps = [r["tmpf"] for r in rows if isinstance(r.get("tmpf"), float)]
    return {
        "source": "IEM_ASOS_ROUTINE_SPECIAL",
        "network": IEM_NETWORK,
        "station_requested": IEM_STATION_ID,
        "icao_expected": EXPECTED_ICAO,
        "event_date": event_date.isoformat(),
        "fieldnames": fieldnames,
        "rows": rows,
        "row_count": len(rows),
        "temperature_row_count": len(temps),
        "running_max_tmpf": max(temps) if temps else None,
        "station_check_ok": True,
        "date_check_ok": True,
        "guardrail": "observation_input_only_not_settlement_label",
    }


def wu_daily_url(event_date: date) -> str:
    return WU_DAILY_URL.format(date_path=f"{event_date.year}-{event_date.month}-{event_date.day}")


class _WUDailyObservationsCollector(HTMLParser):
    """Collect WU page identity and only the Daily Observations table.

    The target table must live inside ``div.airport-results[data-results=observations]``,
    follow the ``Daily Observations`` section heading, and carry the
    ``observations-table`` class. This rejects generic tables with superficially
    similar Time/Temperature columns.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.page_identities: list[dict[str, str]] = []
        self.daily_tables: list[list[list[str]]] = []
        self._observations_container_depth: int | None = None
        self._daily_heading_seen = False
        self._heading_depth: int | None = None
        self._heading_parts: list[str] | None = None
        self._table_depth: int | None = None
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    @staticmethod
    def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {str(k).lower(): str(v or "") for k, v in attrs}

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.depth += 1
        amap = self._attrs(attrs)

        if tag == "airport-body":
            self.page_identities.append({
                "data-icao-code": amap.get("data-icao-code", ""),
                "data-time-zone": amap.get("data-time-zone", ""),
                "data-mode": amap.get("data-mode", ""),
                "data-date": amap.get("data-date", ""),
            })

        classes = set(amap.get("class", "").split())
        if (
            tag == "div"
            and self._observations_container_depth is None
            and "airport-results" in classes
            and amap.get("data-results", "").strip().lower() == "observations"
        ):
            self._observations_container_depth = self.depth
            self._daily_heading_seen = False

        if self._observations_container_depth is not None:
            if tag == "h2" and "section-title" in classes:
                self._heading_depth = self.depth
                self._heading_parts = []
            elif (
                tag == "table"
                and self._daily_heading_seen
                and "observations-table" in classes
                and self._table is None
            ):
                self._table_depth = self.depth
                self._table = []
            elif self._table is not None and tag == "tr":
                self._row = []
            elif self._table is not None and tag in {"td", "th"} and self._row is not None:
                self._cell_parts = []

        if tag in self._VOID_TAGS:
            self.depth = max(0, self.depth - 1)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in self._VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)
        if self._heading_parts is not None:
            self._heading_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._table is not None:
            if tag in {"td", "th"} and self._cell_parts is not None:
                text = " ".join("".join(self._cell_parts).split())
                assert self._row is not None
                self._row.append(html.unescape(text))
                self._cell_parts = None
            elif tag == "tr" and self._row is not None:
                if any(cell for cell in self._row):
                    self._table.append(self._row)
                self._row = None
                self._cell_parts = None
            elif tag == "table" and self._table_depth == self.depth:
                self.daily_tables.append(self._table)
                self._table = None
                self._table_depth = None
                self._row = None
                self._cell_parts = None

        if tag == "h2" and self._heading_depth == self.depth and self._heading_parts is not None:
            heading = _norm_header(" ".join(self._heading_parts))
            if heading == "daily observations":
                self._daily_heading_seen = True
            self._heading_depth = None
            self._heading_parts = None

        if (
            tag == "div"
            and self._observations_container_depth is not None
            and self._observations_container_depth == self.depth
        ):
            self._observations_container_depth = None
            self._daily_heading_seen = False

        self.depth = max(0, self.depth - 1)


def _norm_header(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _parse_number(cell: str) -> float | None:
    m = re.search(r"[-+]?\d+(?:\.\d+)?", cell.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _loose_ymd(value: str) -> date | None:
    m = re.fullmatch(r"\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*", value or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _temperature_units(cell: str) -> set[str]:
    text = html.unescape(cell).replace("º", "°")
    units: set[str] = set()
    if re.search(r"(?:°\s*F|\bFahrenheit\b)", text, flags=re.I):
        units.add("F")
    if re.search(r"(?:°\s*C|\bCelsius\b)", text, flags=re.I):
        units.add("C")
    return units


def _temperature_unit(cell: str) -> str | None:
    units = _temperature_units(cell)
    if len(units) == 1:
        return next(iter(units))
    return None


def _validate_wu_page_identity(
    identities: list[dict[str, str]], *, event_date: date
) -> dict[str, str]:
    if not identities:
        raise Study2SourceError("WU airport-body identity metadata missing")

    tuples = {
        (
            x.get("data-icao-code", "").strip(),
            x.get("data-time-zone", "").strip(),
            x.get("data-mode", "").strip(),
            x.get("data-date", "").strip(),
        )
        for x in identities
    }
    if len(tuples) != 1:
        raise Study2SourceError(f"WU page identity metadata is ambiguous: {sorted(tuples)}")

    icao, timezone_name, mode, date_text = next(iter(tuples))
    actual_date = _loose_ymd(date_text)
    if icao.upper() != EXPECTED_ICAO:
        raise Study2SourceError(
            f"WU station identity mismatch: expected {EXPECTED_ICAO}, observed {icao or '<missing>'}"
        )
    if timezone_name != "America/Chicago":
        raise Study2SourceError(
            f"WU timezone mismatch: expected America/Chicago, observed {timezone_name or '<missing>'}"
        )
    if mode.lower() != "daily":
        raise Study2SourceError(f"WU mode mismatch: expected daily, observed {mode or '<missing>'}")
    if actual_date != event_date:
        raise Study2SourceError(
            f"WU page date mismatch: expected {event_date.isoformat()}, observed {date_text or '<missing>'}"
        )

    return {
        "icao_code": icao.upper(),
        "time_zone": timezone_name,
        "mode": mode.lower(),
        "page_date": actual_date.isoformat(),
    }


def validate_wu_final_url(final_url: str, *, event_date: date) -> dict[str, str]:
    path = urlparse(final_url).path
    m = re.search(r"/([^/]+)/date/(\d{4}-\d{1,2}-\d{1,2})(?:/|$)", path, flags=re.I)
    if not m:
        raise Study2SourceError(f"WU final URL lacks station/date identity: {final_url}")
    station = m.group(1).upper()
    actual_date = _loose_ymd(m.group(2))
    if station != EXPECTED_ICAO:
        raise Study2SourceError(
            f"WU final URL station mismatch: expected {EXPECTED_ICAO}, observed {station}"
        )
    if actual_date != event_date:
        raise Study2SourceError(
            f"WU final URL date mismatch: expected {event_date.isoformat()}, observed {m.group(2)}"
        )
    return {"station_code": station, "event_date": actual_date.isoformat()}


def parse_wu_daily_observations_html(raw_html: str, *, event_date: date) -> dict[str, Any]:
    """Parse the station/date-bound WU Daily Observations table only.

    Success requires the WU page identity metadata, the dedicated Daily
    Observations container/table, and an explicit uniform Fahrenheit unit.
    Anything else fails closed; callers retain the raw response for audit.
    """
    collector = _WUDailyObservationsCollector()
    collector.feed(raw_html)

    page_identity = _validate_wu_page_identity(collector.page_identities, event_date=event_date)

    if len(collector.daily_tables) != 1:
        raise Study2SourceError(
            f"WU Daily Observations table identity unresolved: expected 1, found {len(collector.daily_tables)}"
        )
    table = collector.daily_tables[0]

    header_index = None
    temp_index = None
    time_index = None
    header_temp_unit = None
    for i, row in enumerate(table[:8]):
        normalized = [_norm_header(x) for x in row]
        t_candidates = [j for j, x in enumerate(normalized) if x == "temperature" or x.startswith("temperature ")]
        time_candidates = [j for j, x in enumerate(normalized) if x == "time" or x.startswith("time ")]
        if t_candidates and time_candidates:
            header_index = i
            temp_index = t_candidates[0]
            time_index = time_candidates[0]
            header_units = _temperature_units(row[temp_index])
            if len(header_units) > 1:
                raise Study2SourceError(
                    "WU Daily Observations temperature header contains mixed/ambiguous units"
                )
            header_temp_unit = next(iter(header_units), None)
            break
    if header_index is None or temp_index is None or time_index is None:
        raise Study2SourceError("WU Daily Observations header could not be resolved")

    observations: list[dict[str, Any]] = []
    observed_units: set[str] = set()
    unknown_unit_rows: list[str] = []
    for row in table[header_index + 1:]:
        if max(temp_index, time_index) >= len(row):
            continue
        time_label = row[time_index].strip()
        temp_cell = row[temp_index].strip()
        temperature = _parse_number(temp_cell)
        if temperature is None or not time_label:
            continue
        if _norm_header(time_label) in {"max", "avg", "min", "date"}:
            continue

        cell_units = _temperature_units(temp_cell)
        if len(cell_units) > 1:
            raise Study2SourceError(
                f"WU Daily Observations temperature cell has mixed/ambiguous units "
                f"at {time_label}: {temp_cell!r}"
            )

        unit = next(iter(cell_units), None)

        if unit is not None:
            observed_units.add(unit)

            if header_temp_unit is not None and unit != header_temp_unit:
                raise Study2SourceError(
                    "WU Daily Observations temperature header/row unit conflict: "
                    f"header={header_temp_unit}, row={unit}, time={time_label}"
                )

        elif header_temp_unit is None:
            unknown_unit_rows.append(time_label)

        observations.append({
            "time_label": time_label,
            "temperature_f": temperature,
            "temperature_source_text": temp_cell,
            "cells": row,
        })

    if not observations:
        raise Study2SourceError("WU Daily Observations table contained no temperature rows")
    if header_temp_unit == "C" or "C" in observed_units:
        raise Study2SourceError(
            "WU Daily Observations temperature unit is Celsius, not Fahrenheit"
        )
    if any(unit != "F" for unit in observed_units):
        raise Study2SourceError(f"WU Daily Observations unsupported temperature units: {sorted(observed_units)}")
    if unknown_unit_rows and header_temp_unit != "F":
        raise Study2SourceError(
            f"WU Daily Observations temperature unit is unknown for rows {unknown_unit_rows[:5]}"
        )
    if not observed_units and header_temp_unit != "F":
        raise Study2SourceError("WU Daily Observations Fahrenheit unit could not be verified")

    temperatures = [x["temperature_f"] for x in observations]
    return {
        "source": "WEATHER_UNDERGROUND_DAILY_OBSERVATIONS",
        "event_date": event_date.isoformat(),
        "station_code": EXPECTED_ICAO,
        "page_identity": page_identity,
        "table_identity": "airport-results[data-results=observations] > Daily Observations > table.observations-table",
        "temperature_unit": "F",
        "observation_count": len(observations),
        "observations": observations,
        "max_temperature_f": max(temperatures),
        "observations_sha256": canonical_json_sha256(observations),
        "finality_status": "UNRESOLVED_DEVELOPMENT",
        "guardrail": "daily_observations_only_summary_high_low_not_used",
    }


@dataclass
class PublicSourceResponse:
    requested_url: str
    final_url: str
    status_code: int
    received_utc: str
    content_type: str | None
    etag: str | None
    last_modified: str | None
    body: bytes


def _request_public(
    session: requests.Session,
    url: str,
    *,
    timeout_seconds: float,
    params: list[tuple[str, str]] | None = None,
) -> PublicSourceResponse:
    from datetime import datetime, timezone

    try:
        response = session.get(
            url,
            params=params,
            headers={"User-Agent": PUBLIC_USER_AGENT, "Accept": "text/html,text/csv,*/*;q=0.8"},
            timeout=float(timeout_seconds),
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise Study2SourceError(f"public source request failed: {type(exc).__name__}: {exc}") from exc
    received = datetime.now(timezone.utc).isoformat()
    return PublicSourceResponse(
        requested_url=url,
        final_url=str(response.url),
        status_code=int(response.status_code),
        received_utc=received,
        content_type=response.headers.get("Content-Type"),
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        body=bytes(response.content),
    )


def _require_http_200(response: PublicSourceResponse) -> None:
    if response.status_code != 200:
        raise Study2SourceError(
            f"public source returned HTTP {response.status_code}: {response.final_url or response.requested_url}"
        )


def fetch_iem_asos_day(
    session: requests.Session,
    *,
    event_date: date,
    timeout_seconds: float,
) -> tuple[PublicSourceResponse, dict[str, Any]]:
    response = _request_public(
        session,
        IEM_ASOS_URL,
        timeout_seconds=timeout_seconds,
        params=build_iem_asos_params(event_date),
    )
    _require_http_200(response)
    text = response.body.decode("utf-8", errors="replace")
    parsed = parse_iem_asos_csv(text, event_date=event_date)
    return response, parsed


def fetch_wu_daily(
    session: requests.Session,
    *,
    event_date: date,
    timeout_seconds: float,
) -> tuple[PublicSourceResponse, dict[str, Any]]:
    response = _request_public(
        session,
        wu_daily_url(event_date),
        timeout_seconds=timeout_seconds,
    )
    _require_http_200(response)
    validate_wu_final_url(response.final_url, event_date=event_date)
    text = response.body.decode("utf-8", errors="replace")
    parsed = parse_wu_daily_observations_html(text, event_date=event_date)
    return response, parsed


class Study2PublicSourceRecorder:
    """Archive raw public-source responses before any semantic parsing."""

    def __init__(self, *, output_dir: Path, event_date: date, session_id: str) -> None:
        self.output_dir = output_dir
        self.event_date = event_date
        self.session_id = session_id
        self.sources_dir = output_dir / "sources"
        self.iem_raw_dir = self.sources_dir / "iem_raw"
        self.wu_raw_dir = self.sources_dir / "wu_raw"
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.iem_raw_dir.mkdir(parents=True, exist_ok=True)
        self.wu_raw_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.seen_observation_keys = self._load_seen_observations()
        self.last_wu_semantic_hash = self._last_jsonl_value(
            self.sources_dir / "wu_snapshots.jsonl", "observations_sha256"
        )

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
            f.flush()

    @staticmethod
    def _last_jsonl_value(path: Path, key: str) -> str | None:
        if not path.exists():
            return None
        value = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get(key):
                value = str(obj[key])
        return value

    def _load_seen_observations(self) -> set[str]:
        path = self.sources_dir / "weather_observations.jsonl"
        out: set[str] = set()
        if not path.exists():
            return out
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("observation_key"):
                out.add(str(obj["observation_key"]))
        return out

    def _archive_raw_response(
        self,
        *,
        response: PublicSourceResponse,
        source_kind: str,
        raw_dir: Path,
        prefix: str,
        suffix: str,
    ) -> tuple[str, Path, dict[str, Any]]:
        payload_sha = sha256_bytes(response.body)
        raw_path = raw_dir / f"{prefix}_{payload_sha[:16]}.{suffix}"
        if not raw_path.exists():
            raw_path.write_bytes(response.body)

        raw_record = {
            "record_type": "study2_public_source_raw_fetch",
            "sources_version": SOURCES_VERSION,
            "session_id": self.session_id,
            "event_date": self.event_date.isoformat(),
            "source_kind": source_kind,
            "received_utc": response.received_utc,
            "requested_url": response.requested_url,
            "final_url": response.final_url,
            "status_code": response.status_code,
            "content_type": response.content_type,
            "etag": response.etag,
            "last_modified": response.last_modified,
            "payload_sha256": payload_sha,
            "raw_file": str(raw_path.relative_to(self.output_dir)),
        }
        self._append_jsonl(self.sources_dir / "raw_fetches.jsonl", raw_record)
        return payload_sha, raw_path, raw_record

    def capture_iem(self, *, timeout_seconds: float) -> dict[str, Any]:
        response = _request_public(
            self.session,
            IEM_ASOS_URL,
            timeout_seconds=timeout_seconds,
            params=build_iem_asos_params(self.event_date),
        )
        payload_sha, raw_path, raw_record = self._archive_raw_response(
            response=response,
            source_kind="IEM_ASOS_ROUTINE_SPECIAL",
            raw_dir=self.iem_raw_dir,
            prefix="iem_asos",
            suffix="csv",
        )

        try:
            _require_http_200(response)
            text = response.body.decode("utf-8", errors="replace")
            parsed = parse_iem_asos_csv(text, event_date=self.event_date)
        except Study2SourceError as exc:
            failure = {
                **raw_record,
                "record_type": "study2_iem_asos_fetch",
                "parse_ok": False,
                "semantic_error": str(exc),
            }
            self._append_jsonl(self.sources_dir / "iem_asos_fetches.jsonl", failure)
            raise

        new_rows = 0
        obs_path = self.sources_dir / "weather_observations.jsonl"
        for row in parsed["rows"]:
            key = canonical_json_sha256({
                "valid_local": row.get("valid_local"),
                "metar": row.get("metar"),
                "tmpf": row.get("tmpf"),
            })
            if key in self.seen_observation_keys:
                continue
            rec = {
                "record_type": "study2_kmdw_weather_observation",
                "sources_version": SOURCES_VERSION,
                "session_id": self.session_id,
                "event_date": self.event_date.isoformat(),
                "source": parsed["source"],
                "observation_key": key,
                "source_payload_sha256": payload_sha,
                "source_received_utc": response.received_utc,
                **row,
            }
            self._append_jsonl(obs_path, rec)
            self.seen_observation_keys.add(key)
            new_rows += 1

        fetch_record = {
            **raw_record,
            "record_type": "study2_iem_asos_fetch",
            "parse_ok": True,
            "row_count": parsed["row_count"],
            "temperature_row_count": parsed["temperature_row_count"],
            "running_max_tmpf": parsed["running_max_tmpf"],
            "station_check_ok": parsed["station_check_ok"],
            "date_check_ok": parsed["date_check_ok"],
            "new_observations": new_rows,
            "guardrail": parsed["guardrail"],
        }
        self._append_jsonl(self.sources_dir / "iem_asos_fetches.jsonl", fetch_record)
        return fetch_record

    def capture_wu(self, *, timeout_seconds: float) -> dict[str, Any]:
        response = _request_public(
            self.session,
            wu_daily_url(self.event_date),
            timeout_seconds=timeout_seconds,
        )
        payload_sha, raw_path, raw_record = self._archive_raw_response(
            response=response,
            source_kind="WEATHER_UNDERGROUND_DAILY_OBSERVATIONS",
            raw_dir=self.wu_raw_dir,
            prefix="wu_daily",
            suffix="html",
        )

        try:
            _require_http_200(response)
            final_url_identity = validate_wu_final_url(response.final_url, event_date=self.event_date)
            text = response.body.decode("utf-8", errors="replace")
            parsed = parse_wu_daily_observations_html(text, event_date=self.event_date)
        except Study2SourceError as exc:
            failure = {
                **raw_record,
                "record_type": "study2_wu_daily_snapshot",
                "parse_ok": False,
                "semantic_error": str(exc),
                "finality_status": "UNRESOLVED_DEVELOPMENT",
            }
            self._append_jsonl(self.sources_dir / "wu_snapshots.jsonl", failure)
            raise

        previous = self.last_wu_semantic_hash
        current = parsed["observations_sha256"]
        semantic_changed = previous is not None and current != previous
        snapshot = {
            **raw_record,
            "record_type": "study2_wu_daily_snapshot",
            "parse_ok": True,
            "final_url_identity": final_url_identity,
            "semantic_changed_from_previous": semantic_changed,
            **parsed,
        }
        self._append_jsonl(self.sources_dir / "wu_snapshots.jsonl", snapshot)
        self.last_wu_semantic_hash = current
        return snapshot
