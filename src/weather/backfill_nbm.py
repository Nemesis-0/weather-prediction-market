from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests


API_URL = "https://mesonet.agron.iastate.edu/api/1/mos.json"

MARKET_PANEL = Path("data/processed/market_panel_preclose.csv")
RAW_DIR = Path("data/raw/weather/nbm_nbs")
PROCESSED_DIR = Path("data/processed")
RESULTS_DIR = Path("results/development")

PRIMARY_DECISION_HOUR = 10
ASSUMED_DISSEMINATION_LAG_MINUTES = 60

CYCLES_UTC = (0, 6, 12, 18)

CITY_CONFIG = {
    "NYC": {
        "station": "KNYC",
        "timezone": "America/New_York",
    },
    "Chicago": {
        "station": "KMDW",
        "timezone": "America/Chicago",
    },
    "Denver": {
        "station": "KDEN",
        "timezone": "America/Denver",
    },
}


def get_json(
    session: requests.Session,
    params: dict,
) -> dict:
    max_retries = 8

    for attempt in range(max_retries):
        r = session.get(
            API_URL,
            params=params,
            timeout=30,
        )

        if r.status_code == 429:
            wait = min(2 ** attempt, 60)
            print(
                f"    429 rate limit — waiting {wait}s"
            )
            time.sleep(wait)
            continue

        r.raise_for_status()
        return r.json()

    raise RuntimeError(
        "Exceeded IEM retry limit."
    )


def primary_decision_time(
    event_date: str,
    timezone_name: str,
) -> datetime:
    date = datetime.strptime(
        event_date,
        "%Y-%m-%d",
    ).date()

    tz = ZoneInfo(timezone_name)

    local_dt = datetime(
        date.year,
        date.month,
        date.day,
        PRIMARY_DECISION_HOUR,
        0,
        tzinfo=tz,
    )

    return local_dt


def latest_eligible_cycle(
    decision_local: datetime,
) -> tuple[datetime, datetime]:
    """
    Returns:
      cycle_time_utc
      assumed_available_at_utc

    Rule frozen before weather backfill:

      assumed_available_at
          = cycle_time + 60 minutes

      assumed_available_at
          <= decision_time
    """

    decision_utc = decision_local.astimezone(
        timezone.utc
    )

    candidates = []

    # Search current UTC date and previous UTC date.
    for day_offset in (-1, 0):
        candidate_date = (
            decision_utc.date()
            + timedelta(days=day_offset)
        )

        for hour in CYCLES_UTC:
            cycle = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                hour,
                0,
                tzinfo=timezone.utc,
            )

            available = cycle + timedelta(
                minutes=(
                    ASSUMED_DISSEMINATION_LAG_MINUTES
                )
            )

            if available <= decision_utc:
                candidates.append(
                    (cycle, available)
                )

    if not candidates:
        raise RuntimeError(
            f"No eligible cycle before "
            f"{decision_utc.isoformat()}"
        )

    return max(
        candidates,
        key=lambda x: x[0],
    )


def expected_tmax_valid_time(
    event_date: str,
) -> datetime:
    """
    For CONUS NBS:
      Tmax is reported at 00Z following day.
    """

    date = datetime.strptime(
        event_date,
        "%Y-%m-%d",
    ).date()

    next_day = date + timedelta(days=1)

    return datetime(
        next_day.year,
        next_day.month,
        next_day.day,
        0,
        0,
        tzinfo=timezone.utc,
    )


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None

    text = (
        value
        .replace("Z", "+00:00")
        .replace(".000", "")
    )

    dt = datetime.fromisoformat(text)

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(timezone.utc)


def main():
    market = pd.read_csv(MARKET_PANEL)

    city_days = (
        market[
            [
                "city",
                "event_date_local",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            [
                "event_date_local",
                "city",
            ]
        )
        .reset_index(drop=True)
    )

    print("\nHistorical NBM/NBS backfill")
    print("=" * 80)
    print(
        f"Unique city-days: {len(city_days)}"
    )

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    session = requests.Session()

    processed_rows = []

    downloaded = 0
    skipped = 0
    missing = 0

    retrieval_time = datetime.now(
        timezone.utc
    )

    for record in city_days.itertuples(
        index=False
    ):
        city = record.city
        event_date = record.event_date_local

        cfg = CITY_CONFIG[city]

        station = cfg["station"]
        timezone_name = cfg["timezone"]

        decision_local = primary_decision_time(
            event_date,
            timezone_name,
        )

        decision_utc = (
            decision_local
            .astimezone(timezone.utc)
        )

        (
            cycle_utc,
            assumed_available_utc,
        ) = latest_eligible_cycle(
            decision_local
        )

        target_valid_utc = (
            expected_tmax_valid_time(
                event_date
            )
        )

        runtime_param = (
            cycle_utc.strftime(
                "%Y-%m-%d %H:%MZ"
            )
        )

        raw_city_dir = (
            RAW_DIR / station
        )

        raw_city_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        raw_path = (
            raw_city_dir
            / (
                f"{event_date}_"
                f"{cycle_utc:%Y%m%dT%H%MZ}.json"
            )
        )

        if raw_path.exists():
            payload = json.loads(
                raw_path.read_text(
                    encoding="utf-8"
                )
            )
            skipped += 1
        else:
            payload = get_json(
                session,
                {
                    "station": station,
                    "model": "NBS",
                    "runtime": runtime_param,
                },
            )

            raw_record = {
                "retrieved_at_utc":
                    retrieval_time.isoformat(),
                "city": city,
                "station": station,
                "event_date_local":
                    event_date,
                "decision_time_local":
                    decision_local.isoformat(),
                "decision_time_utc":
                    decision_utc.isoformat(),
                "cycle_time_utc":
                    cycle_utc.isoformat(),
                "assumed_available_at_utc":
                    assumed_available_utc.isoformat(),
                "availability_lag_minutes":
                    ASSUMED_DISSEMINATION_LAG_MINUTES,
                "model": "NBM",
                "product": "NBS",
                "archive_provider": "IEM",
                "api_response": payload,
            }

            raw_path.write_text(
                json.dumps(
                    raw_record,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            downloaded += 1

            time.sleep(0.25)

        # If we loaded our own raw wrapper,
        # extract the original API response.
        if "api_response" in payload:
            api_payload = payload[
                "api_response"
            ]
        else:
            api_payload = payload

        rows = api_payload.get(
            "data",
            []
        )

        matches = []

        for row in rows:
            ftime = parse_utc(
                row.get("ftime_utc")
            )

            if ftime != target_valid_utc:
                continue

            if row.get("txn") is None:
                continue

            if row.get("xnd") is None:
                continue

            matches.append(row)

        if len(matches) == 1:
            row = matches[0]

            processed_rows.append(
                {
                    "city": city,
                    "station": station,
                    "event_date_local":
                        event_date,
                    "timezone":
                        timezone_name,

                    "decision_time_local":
                        decision_local.isoformat(),
                    "decision_time_utc":
                        decision_utc.isoformat(),

                    "model": "NBM",
                    "product": "NBS",

                    "cycle_time_utc":
                        cycle_utc.isoformat(),
                    "assumed_available_at_utc":
                        assumed_available_utc.isoformat(),
                    "availability_lag_minutes":
                        ASSUMED_DISSEMINATION_LAG_MINUTES,

                    "forecast_valid_time_utc":
                        target_valid_utc.isoformat(),

                    "forecast_window_start_utc":
                        datetime.strptime(
                            event_date,
                            "%Y-%m-%d",
                        )
                        .replace(
                            hour=12,
                            tzinfo=timezone.utc,
                        )
                        .isoformat(),

                    "forecast_window_end_utc":
                        (
                            datetime.strptime(
                                event_date,
                                "%Y-%m-%d",
                            )
                            .replace(
                                hour=6,
                                tzinfo=timezone.utc,
                            )
                            + timedelta(days=1)
                        )
                        .isoformat(),

                    "txn":
                        float(row["txn"]),
                    "xnd":
                        float(row["xnd"]),

                    "tmp_at_valid_time":
                        row.get("tmp"),
                    "tsd_at_valid_time":
                        row.get("tsd"),

                    "archive_provider":
                        "IEM",
                    "retrieved_at_utc":
                        retrieval_time.isoformat(),

                    "eligible_at_decision_time":
                        True,

                    "target_role":
                        "predictor_only",

                    "missing_reason":
                        None,
                    "exclusion_reason":
                        None,
                }
            )

            print(
                f"{event_date} | "
                f"{city:<7} | "
                f"{station} | "
                f"cycle={cycle_utc:%HZ} | "
                f"TXN={row['txn']} | "
                f"XND={row['xnd']}"
            )

        else:
            missing += 1

            reason = (
                "no_unique_00Z_next_day_"
                "TXN_XND_row"
            )

            processed_rows.append(
                {
                    "city": city,
                    "station": station,
                    "event_date_local":
                        event_date,
                    "timezone":
                        timezone_name,

                    "decision_time_local":
                        decision_local.isoformat(),
                    "decision_time_utc":
                        decision_utc.isoformat(),

                    "model": "NBM",
                    "product": "NBS",

                    "cycle_time_utc":
                        cycle_utc.isoformat(),
                    "assumed_available_at_utc":
                        assumed_available_utc.isoformat(),
                    "availability_lag_minutes":
                        ASSUMED_DISSEMINATION_LAG_MINUTES,

                    "forecast_valid_time_utc":
                        target_valid_utc.isoformat(),

                    "txn": None,
                    "xnd": None,

                    "archive_provider":
                        "IEM",
                    "retrieved_at_utc":
                        retrieval_time.isoformat(),

                    "eligible_at_decision_time":
                        True,

                    "target_role":
                        "predictor_only",

                    "missing_reason":
                        reason,
                    "exclusion_reason":
                        None,
                }
            )

            print(
                f"{event_date} | "
                f"{city:<7} | "
                f"{station} | "
                f"MISSING "
                f"(matches={len(matches)})"
            )

    weather = pd.DataFrame(
        processed_rows
    )

    weather_path = (
        PROCESSED_DIR
        / "weather_panel_primary.csv"
    )

    weather.to_csv(
        weather_path,
        index=False,
    )

    # -----------------------------------------------------
    # QC audit
    # -----------------------------------------------------

    complete = weather[
        weather["txn"].notna()
        & weather["xnd"].notna()
    ].copy()

    cycle_counts = (
        weather["cycle_time_utc"]
        .str.slice(11, 13)
        .value_counts()
        .sort_index()
    )

    duplicate_count = int(
        weather.duplicated(
            [
                "city",
                "event_date_local",
            ]
        ).sum()
    )

    availability_violations = 0

    for r in weather.itertuples():
        decision = parse_utc(
            r.decision_time_utc
        )
        available = parse_utc(
            r.assumed_available_at_utc
        )

        if (
            decision is not None
            and available is not None
            and available > decision
        ):
            availability_violations += 1

    summary = [
        "Historical NBM/NBS backfill audit",
        "=" * 60,
        f"Expected city-days:            {len(city_days)}",
        f"Processed rows:                {len(weather)}",
        f"Complete TXN/XND rows:         {len(complete)}",
        f"Missing TXN/XND rows:          {missing}",
        f"Duplicate city-day rows:       {duplicate_count}",
        f"Availability violations:       {availability_violations}",
        "",
        "Selected cycle-hour counts:",
    ]

    for hour, count in cycle_counts.items():
        summary.append(
            f"  {hour}Z: {count}"
        )

    summary.extend(
        [
            "",
            f"Raw downloads this run:        {downloaded}",
            f"Raw files reused/skipped:      {skipped}",
            f"Processed panel:               {weather_path}",
        ]
    )

    audit_path = (
        RESULTS_DIR
        / "weather_backfill_audit.txt"
    )

    audit_path.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    print("\n" + "\n".join(summary))


if __name__ == "__main__":
    main()
