from __future__ import annotations

import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests


EVENT_DATE = "2026-09-28"

HOURS = range(8, 17)  # 08Z through 16Z

IEM_URL = (
    "https://mesonet.agron.iastate.edu/"
    "api/1/mos.json"
)

S3_TEMPLATE = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.{date}/{hour:02d}/text/"
    "blend_nbstx.t{hour:02d}z"
)

CITY = {
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


def utc_ts(x):
    ts = pd.Timestamp(x)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


def decision_time(event_date, tz_name):
    d = pd.Timestamp(event_date).date()

    local = datetime(
        d.year,
        d.month,
        d.day,
        10,
        0,
        tzinfo=ZoneInfo(tz_name),
    )

    return pd.Timestamp(local).tz_convert("UTC")


def target_valid_time(event_date):
    return (
        pd.Timestamp(event_date)
        + pd.Timedelta(days=1)
    ).tz_localize("UTC")


def fetch_iem(session, station, hour):
    runtime = (
        f"{EVENT_DATE} "
        f"{hour:02d}:00Z"
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
                min(2 ** attempt, 30)
            )
            continue

        if r.status_code != 200:
            return {
                "iem_status":
                    r.status_code,
                "txn":
                    None,
                "xnd":
                    None,
                "target_rows":
                    0,
            }

        payload = r.json()
        rows = payload.get(
            "data",
            []
        )

        target = (
            target_valid_time(
                EVENT_DATE
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
                ts = utc_ts(
                    ftime
                )
            except Exception:
                continue

            if (
                ts == target
                and row.get("txn")
                is not None
                and row.get("xnd")
                is not None
            ):
                matches.append(row)

        if len(matches) == 1:
            return {
                "iem_status": 200,
                "txn":
                    float(
                        matches[0]["txn"]
                    ),
                "xnd":
                    float(
                        matches[0]["xnd"]
                    ),
                "target_rows": 1,
            }

        return {
            "iem_status": 200,
            "txn": None,
            "xnd": None,
            "target_rows":
                len(matches),
        }

    raise RuntimeError(
        "IEM retries exhausted."
    )


def main():
    session = requests.Session()

    s3 = {}

    print(
        "\nNOAA NBS HOURLY CADENCE PROBE"
    )
    print("=" * 84)
    print(
        f"Event date: {EVENT_DATE}"
    )

    # -------------------------------------------------
    # NOAA object existence + Last-Modified
    # -------------------------------------------------

    print(
        "\nNOAA S3 objects:"
    )

    for hour in HOURS:
        url = S3_TEMPLATE.format(
            date=EVENT_DATE.replace(
                "-", ""
            ),
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
            last_modified = utc_ts(
                parsedate_to_datetime(
                    r.headers[
                        "Last-Modified"
                    ]
                )
            )

        cycle = pd.Timestamp(
            f"{EVENT_DATE} "
            f"{hour:02d}:00:00",
            tz="UTC",
        )

        lag_min = (
            (
                last_modified
                - cycle
            ).total_seconds()
            / 60.0
            if last_modified
            is not None
            else None
        )

        s3[hour] = {
            "status":
                r.status_code,
            "last_modified":
                last_modified,
            "lag_min":
                lag_min,
        }

        print(
            f"  {hour:02d}Z | "
            f"HTTP {r.status_code} | "
            f"Last-Modified="
            f"{last_modified} | "
            f"lag="
            f"{lag_min:.1f} min"
            if lag_min is not None
            else
            f"  {hour:02d}Z | "
            f"HTTP {r.status_code} | "
            f"Last-Modified=None"
        )

    # -------------------------------------------------
    # IEM parsed forecast availability
    # -------------------------------------------------

    results = []

    for city, cfg in CITY.items():
        decision = decision_time(
            EVENT_DATE,
            cfg["timezone"],
        )

        print(
            "\n"
            + "-" * 84
        )
        print(
            f"{city} | "
            f"{cfg['station']} | "
            f"10AM decision={decision}"
        )

        for hour in HOURS:
            iem = fetch_iem(
                session,
                cfg["station"],
                hour,
            )

            info = s3[hour]

            public_before_decision = (
                info["last_modified"]
                is not None
                and info[
                    "last_modified"
                ] <= decision
            )

            usable = (
                info["status"] == 200
                and public_before_decision
                and iem[
                    "target_rows"
                ] == 1
            )

            results.append(
                {
                    "city": city,
                    "station":
                        cfg["station"],
                    "cycle_hour":
                        hour,
                    "decision_utc":
                        decision,
                    "s3_status":
                        info["status"],
                    "last_modified_utc":
                        info[
                            "last_modified"
                        ],
                    "release_lag_min":
                        info["lag_min"],
                    "public_before_decision":
                        public_before_decision,
                    "iem_status":
                        iem[
                            "iem_status"
                        ],
                    "target_rows":
                        iem[
                            "target_rows"
                        ],
                    "txn":
                        iem["txn"],
                    "xnd":
                        iem["xnd"],
                    "usable":
                        usable,
                }
            )

            print(
                f"  {hour:02d}Z | "
                f"TXN={iem['txn']} | "
                f"XND={iem['xnd']} | "
                f"LastMod="
                f"{info['last_modified']} | "
                f"usable_before_10AM="
                f"{usable}"
            )

            time.sleep(0.15)

    df = pd.DataFrame(
        results
    )

    print(
        "\n"
        + "=" * 84
    )
    print(
        "LATEST VERIFIED USABLE CYCLE "
        "BEFORE 10AM LOCAL"
    )
    print("=" * 84)

    for city in CITY:
        g = df[
            (df["city"] == city)
            & df["usable"]
        ]

        if len(g) == 0:
            print(
                f"{city}: NONE"
            )
            continue

        latest = g.sort_values(
            "cycle_hour"
        ).iloc[-1]

        print(
            f"{city}: "
            f"{int(latest['cycle_hour']):02d}Z | "
            f"TXN={latest['txn']} | "
            f"XND={latest['xnd']} | "
            f"published="
            f"{latest['last_modified_utc']}"
        )

    # -------------------------------------------------
    # Compare against actual V1 row
    # -------------------------------------------------

    v1 = pd.read_csv(
        "data/processed/"
        "weather_panel_primary.csv"
    )

    v1 = v1[
        v1[
            "event_date_local"
        ] == EVENT_DATE
    ]

    print(
        "\nV1 ACTUAL SELECTED CYCLES:"
    )

    for row in v1.itertuples(
        index=False
    ):
        print(
            f"{row.city}: "
            f"{row.cycle_time_utc} | "
            f"TXN={row.txn} | "
            f"XND={row.xnd}"
        )

    out = (
        "results/audit/"
        "nbm_hourly_cadence_probe.csv"
    )

    df.to_csv(
        out,
        index=False,
    )

    print(
        f"\nSaved: {out}"
    )


if __name__ == "__main__":
    main()
