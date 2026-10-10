from __future__ import annotations

import time
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests


DATES = [
    "2026-08-20",
    "2026-09-15",
    "2026-09-24",
]

CITY = {
    "NYC": "KNYC",
    "Chicago": "KMDW",
    "Denver": "KDEN",
}

# Candidate states for one event-day Tmax target.
# Previous-day 18Z is included because V1 source-timing repair
# already demonstrated that it can contain the same target.
STATE_SPECS = [
    (-1, 18, "prev18Z"),
    (0, 0, "00Z"),
    (0, 6, "06Z"),
    (0, 12, "12Z"),
]

IEM_URL = (
    "https://mesonet.agron.iastate.edu/"
    "api/1/mos.json"
)

NOAA_TEMPLATE = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.{date}/{hour:02d}/text/"
    "blend_nbstx.t{hour:02d}z"
)

OUTDIR = Path(
    "results/v2_feasibility"
)

OUTDIR.mkdir(
    parents=True,
    exist_ok=True,
)


def to_utc(x):
    ts = pd.Timestamp(x)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


def target_valid_time(
    event_date,
):
    d = (
        pd.Timestamp(event_date)
        + pd.Timedelta(days=1)
    )

    return pd.Timestamp(
        d.strftime("%Y-%m-%d")
        + "T00:00:00Z"
    )


def fetch_head(
    session,
    cycle,
):
    url = NOAA_TEMPLATE.format(
        date=cycle.strftime(
            "%Y%m%d"
        ),
        hour=cycle.hour,
    )

    for attempt in range(6):
        r = session.head(
            url,
            timeout=30,
            allow_redirects=True,
        )

        if r.status_code == 429:
            time.sleep(
                min(
                    2 ** attempt,
                    30,
                )
            )
            continue

        published = None

        if (
            r.status_code == 200
            and r.headers.get(
                "Last-Modified"
            )
        ):
            published = to_utc(
                parsedate_to_datetime(
                    r.headers[
                        "Last-Modified"
                    ]
                )
            )

        return (
            r.status_code,
            published,
            url,
        )

    raise RuntimeError(
        "NOAA HEAD retries exhausted."
    )


def fetch_iem(
    session,
    station,
    cycle,
    event_date,
):
    for attempt in range(6):
        r = session.get(
            IEM_URL,
            params={
                "station": station,
                "model": "NBS",
                "runtime":
                    cycle.strftime(
                        "%Y-%m-%d %H:%MZ"
                    ),
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
            return (
                r.status_code,
                0,
                None,
                None,
            )

        target = (
            target_valid_time(
                event_date
            )
        )

        matches = []

        for row in (
            r.json()
            .get(
                "data",
                [],
            )
        ):
            if not row.get(
                "ftime_utc"
            ):
                continue

            try:
                ftime = to_utc(
                    row[
                        "ftime_utc"
                    ]
                )
            except Exception:
                continue

            if (
                ftime == target
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
            return (
                200,
                1,
                float(
                    matches[0][
                        "txn"
                    ]
                ),
                float(
                    matches[0][
                        "xnd"
                    ]
                ),
            )

        return (
            200,
            len(matches),
            None,
            None,
        )

    raise RuntimeError(
        "IEM retries exhausted."
    )


def main():
    session = requests.Session()

    rows = []

    print()
    print(
        "V2 EXTENDED REVISION-CHAIN PROBE"
    )
    print("=" * 94)

    for event_date in DATES:
        base = pd.Timestamp(
            event_date
        ).date()

        print()
        print(
            "-" * 94
        )
        print(
            "EVENT DATE:",
            event_date,
        )

        for city, station in (
            CITY.items()
        ):
            city_rows = []

            for (
                day_offset,
                hour,
                label,
            ) in STATE_SPECS:

                cycle_date = (
                    base
                    + timedelta(
                        days=day_offset
                    )
                )

                cycle = pd.Timestamp(
                    year=cycle_date.year,
                    month=cycle_date.month,
                    day=cycle_date.day,
                    hour=hour,
                    tz="UTC",
                )

                (
                    noaa_status,
                    published,
                    url,
                ) = fetch_head(
                    session,
                    cycle,
                )

                (
                    iem_status,
                    target_rows,
                    txn,
                    xnd,
                ) = fetch_iem(
                    session,
                    station,
                    cycle,
                    event_date,
                )

                usable = (
                    noaa_status == 200
                    and published
                    is not None
                    and target_rows == 1
                )

                rec = {
                    "event_date_local":
                        event_date,
                    "city":
                        city,
                    "station":
                        station,
                    "state_label":
                        label,
                    "cycle_time_utc":
                        cycle,
                    "publication_time_utc":
                        published,
                    "noaa_http_status":
                        noaa_status,
                    "iem_http_status":
                        iem_status,
                    "target_rows":
                        target_rows,
                    "txn":
                        txn,
                    "xnd":
                        xnd,
                    "usable_state":
                        usable,
                    "noaa_url":
                        url,
                }

                rows.append(rec)
                city_rows.append(rec)

                time.sleep(0.08)

            print(
                f"\n{city} | {station}"
            )

            for r in city_rows:
                print(
                    f"  {r['state_label']:<7} | "
                    f"cycle={r['cycle_time_utc']} | "
                    f"published={r['publication_time_utc']} | "
                    f"TXN={r['txn']} | "
                    f"XND={r['xnd']} | "
                    f"usable={r['usable_state']}"
                )

            usable = [
                r
                for r in city_rows
                if r[
                    "usable_state"
                ]
            ]

            usable = sorted(
                usable,
                key=lambda r:
                    r[
                        "publication_time_utc"
                    ],
            )

            if len(usable) >= 2:
                print(
                    "  PUBLICATION-ORDER CHAIN:"
                )

                for i, r in enumerate(
                    usable
                ):
                    if i == 0:
                        gap = None
                    else:
                        gap = (
                            r[
                                "publication_time_utc"
                            ]
                            - usable[
                                i - 1
                            ][
                                "publication_time_utc"
                            ]
                        ).total_seconds() / 60

                    print(
                        f"    {i+1}. "
                        f"{r['state_label']} "
                        f"@ {r['publication_time_utc']}"
                        + (
                            ""
                            if gap is None
                            else
                            f" | gap={gap:.1f}m"
                        )
                    )

    df = pd.DataFrame(
        rows
    )

    out = (
        OUTDIR
        / "v2_extended_revision_chain_probe.csv"
    )

    df.to_csv(
        out,
        index=False,
    )

    usable = df[
        df["usable_state"]
    ].copy()

    counts = (
        usable.groupby(
            [
                "event_date_local",
                "city",
            ]
        )
        .size()
    )

    print()
    print("=" * 94)
    print(
        "EXTENDED-CHAIN SUMMARY"
    )
    print("=" * 94)

    print(
        "City-days:",
        len(counts),
    )

    print(
        "City-days with 4 usable states:",
        int(
            (counts == 4).sum()
        ),
    )

    print(
        "City-days with >=3 usable states:",
        int(
            (counts >= 3).sum()
        ),
    )

    print(
        "Minimum usable states/city-day:",
        int(
            counts.min()
        ),
    )

    print(
        "Median usable states/city-day:",
        float(
            counts.median()
        ),
    )

    print(
        "Maximum usable states/city-day:",
        int(
            counts.max()
        ),
    )

    print(
        "\nSaved:",
        out,
    )


if __name__ == "__main__":
    main()
