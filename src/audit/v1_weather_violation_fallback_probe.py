from __future__ import annotations

import time
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests


IEM_URL = (
    "https://mesonet.agron.iastate.edu/"
    "api/1/mos.json"
)

S3_TEMPLATE = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.{date}/{hour:02d}/text/"
    "blend_nbstx.t{hour:02d}z"
)

VIOLATIONS = [
    ("NYC", "KNYC", "America/New_York", "2026-08-31"),
    ("NYC", "KNYC", "America/New_York", "2026-09-24"),
    ("Chicago", "KMDW", "America/Chicago", "2026-09-24"),
    ("Denver", "KDEN", "America/Denver", "2026-09-24"),
]

# Candidate cycles in chronological order.
# Include previous-day 18Z in case 00/06Z is missing.
CANDIDATE_SPECS = [
    (-1, 18),
    (0, 0),
    (0, 6),
    (0, 12),
]


def to_utc(x):
    ts = pd.Timestamp(x)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


def decision_time(
    event_date: str,
    timezone_name: str,
):
    d = pd.Timestamp(
        event_date
    ).date()

    local = datetime(
        d.year,
        d.month,
        d.day,
        10,
        0,
        tzinfo=ZoneInfo(
            timezone_name
        ),
    )

    return pd.Timestamp(
        local
    ).tz_convert("UTC")


def target_valid_time(
    event_date: str,
):
    d = (
        pd.Timestamp(
            event_date
        )
        + pd.Timedelta(days=1)
    )

    return pd.Timestamp(
        d.strftime("%Y-%m-%d")
        + "T00:00:00Z"
    )


def fetch_iem(
    session,
    station,
    cycle,
    event_date,
):
    runtime = (
        cycle.strftime(
            "%Y-%m-%d %H:%MZ"
        )
    )

    for attempt in range(6):
        r = session.get(
            IEM_URL,
            params={
                "station": station,
                "model": "NBS",
                "runtime": runtime,
            },
            timeout=30,
        )

        if r.status_code == 429:
            time.sleep(
                min(
                    2 ** attempt,
                    30,
                )
            )
            continue

        if r.status_code != 200:
            return {
                "http_status":
                    r.status_code,
                "target_rows": 0,
                "txn": None,
                "xnd": None,
            }

        rows = (
            r.json()
            .get(
                "data",
                [],
            )
        )

        target = (
            target_valid_time(
                event_date
            )
        )

        matches = []

        for row in rows:
            ftime = row.get(
                "ftime_utc"
            )

            if not ftime:
                continue

            try:
                ts = to_utc(
                    ftime
                )
            except Exception:
                continue

            if (
                ts == target
                and row.get(
                    "txn"
                ) is not None
                and row.get(
                    "xnd"
                ) is not None
            ):
                matches.append(
                    row
                )

        if len(matches) == 1:
            return {
                "http_status": 200,
                "target_rows": 1,
                "txn":
                    float(
                        matches[0]["txn"]
                    ),
                "xnd":
                    float(
                        matches[0]["xnd"]
                    ),
            }

        return {
            "http_status": 200,
            "target_rows":
                len(matches),
            "txn": None,
            "xnd": None,
        }

    raise RuntimeError(
        "IEM retries exhausted."
    )


def fetch_noaa_metadata(
    session,
    cycle,
):
    ymd = cycle.strftime(
        "%Y%m%d"
    )

    hour = cycle.hour

    url = S3_TEMPLATE.format(
        date=ymd,
        hour=hour,
    )

    r = session.head(
        url,
        timeout=30,
        allow_redirects=True,
    )

    last_modified = None

    if (
        r.status_code == 200
        and r.headers.get(
            "Last-Modified"
        )
    ):
        last_modified = to_utc(
            parsedate_to_datetime(
                r.headers[
                    "Last-Modified"
                ]
            )
        )

    return {
        "url": url,
        "status":
            r.status_code,
        "last_modified":
            last_modified,
    }


def main():
    session = requests.Session()

    records = []

    print(
        "\nV1 WEATHER VIOLATION "
        "FALLBACK PROBE"
    )
    print("=" * 96)

    for (
        city,
        station,
        timezone_name,
        event_date,
    ) in VIOLATIONS:

        decision = decision_time(
            event_date,
            timezone_name,
        )

        print()
        print(
            "-" * 96
        )
        print(
            f"{city} | {event_date} | "
            f"decision={decision}"
        )

        base_date = pd.Timestamp(
            event_date
        ).date()

        local_candidates = []

        for (
            day_offset,
            hour,
        ) in CANDIDATE_SPECS:

            candidate_date = (
                base_date
                + timedelta(
                    days=day_offset
                )
            )

            cycle = pd.Timestamp(
                datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour,
                    0,
                ),
                tz="UTC",
            )

            noaa = (
                fetch_noaa_metadata(
                    session,
                    cycle,
                )
            )

            iem = fetch_iem(
                session,
                station,
                cycle,
                event_date,
            )

            published = (
                noaa[
                    "last_modified"
                ]
            )

            public_before_decision = (
                published
                is not None
                and published
                <= decision
            )

            has_target = (
                iem[
                    "target_rows"
                ]
                == 1
            )

            eligible = (
                noaa["status"] == 200
                and public_before_decision
                and has_target
            )

            margin_min = (
                (
                    decision
                    - published
                ).total_seconds()
                / 60.0
                if published
                is not None
                else None
            )

            rec = {
                "city": city,
                "event_date_local":
                    event_date,
                "station":
                    station,
                "decision_time_utc":
                    decision,
                "cycle_time_utc":
                    cycle,
                "noaa_http_status":
                    noaa["status"],
                "noaa_last_modified_utc":
                    published,
                "publication_margin_minutes":
                    margin_min,
                "iem_http_status":
                    iem[
                        "http_status"
                    ],
                "target_rows":
                    iem[
                        "target_rows"
                    ],
                "txn":
                    iem["txn"],
                "xnd":
                    iem["xnd"],
                "eligible":
                    eligible,
            }

            records.append(rec)

            local_candidates.append(
                rec
            )

            print(
                f"  {cycle:%Y-%m-%d %HZ} | "
                f"published={published} | "
                f"margin="
                + (
                    f"{margin_min:+.1f}m"
                    if margin_min
                    is not None
                    else "NA"
                )
                + f" | TXN={iem['txn']} "
                + f"XND={iem['xnd']} "
                + f"| eligible={eligible}"
            )

            time.sleep(0.10)

        eligible_rows = [
            r
            for r in local_candidates
            if r["eligible"]
        ]

        if eligible_rows:
            latest = max(
                eligible_rows,
                key=lambda r:
                    r[
                        "cycle_time_utc"
                    ],
            )

            print(
                "\n  CORRECT LATEST "
                "ELIGIBLE FALLBACK:"
            )
            print(
                f"    cycle="
                f"{latest['cycle_time_utc']} | "
                f"TXN={latest['txn']} | "
                f"XND={latest['xnd']} | "
                f"published="
                f"{latest['noaa_last_modified_utc']}"
            )
        else:
            print(
                "\n  NO ELIGIBLE "
                "FORECAST FOUND"
            )

    df = pd.DataFrame(
        records
    )

    out = (
        "results/audit/"
        "v1_weather_violation_"
        "fallback_probe.csv"
    )

    df.to_csv(
        out,
        index=False,
    )

    print(
        "\n"
        + "=" * 96
    )
    print(
        f"Saved: {out}"
    )


if __name__ == "__main__":
    main()
