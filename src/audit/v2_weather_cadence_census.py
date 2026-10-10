from __future__ import annotations

import time
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

HOURS = list(range(24))

IEM_URL = (
    "https://mesonet.agron.iastate.edu/"
    "api/1/mos.json"
)

NOAA_TEMPLATE = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.{date}/{hour:02d}/text/"
    "blend_nbstx.t{hour:02d}z"
)

OUTDIR = Path("results/v2_feasibility")
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
    event_date: str,
):
    return pd.Timestamp(
        event_date
    ).tz_localize("UTC") + pd.Timedelta(
        days=1
    )


def fetch_head(
    session,
    url,
):
    for attempt in range(6):
        try:
            r = session.head(
                url,
                timeout=30,
                allow_redirects=True,
            )
        except requests.RequestException:
            if attempt == 5:
                raise

            time.sleep(
                min(2 ** attempt, 20)
            )
            continue

        if r.status_code == 429:
            time.sleep(
                min(2 ** attempt, 30)
            )
            continue

        return r

    raise RuntimeError(
        f"HEAD failed: {url}"
    )


def fetch_iem(
    session,
    station,
    runtime,
    event_date,
):
    for attempt in range(6):
        r = session.get(
            IEM_URL,
            params={
                "station": station,
                "model": "NBS",
                "runtime":
                    runtime.strftime(
                        "%Y-%m-%d %H:%MZ"
                    ),
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
                "iem_http_status":
                    r.status_code,
                "target_rows":
                    0,
                "txn":
                    None,
                "xnd":
                    None,
            }

        rows = r.json().get(
            "data",
            [],
        )

        target = target_valid_time(
            event_date
        )

        matches = []

        for row in rows:
            ftime = row.get(
                "ftime_utc"
            )

            if not ftime:
                continue

            try:
                ftime = to_utc(
                    ftime
                )
            except Exception:
                continue

            if (
                ftime == target
                and row.get("txn")
                is not None
                and row.get("xnd")
                is not None
            ):
                matches.append(
                    row
                )

        if len(matches) == 1:
            return {
                "iem_http_status": 200,
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
            "iem_http_status": 200,
            "target_rows":
                len(matches),
            "txn": None,
            "xnd": None,
        }

    raise RuntimeError(
        "IEM retries exhausted."
    )


def main():
    session = requests.Session()

    object_meta = {}

    print()
    print(
        "V2 NBM/NBS WEATHER CADENCE CENSUS"
    )
    print("=" * 88)

    for event_date in DATES:
        ymd = event_date.replace(
            "-",
            "",
        )

        print()
        print(
            f"NOAA objects | {event_date}"
        )

        for hour in HOURS:
            cycle = pd.Timestamp(
                f"{event_date} "
                f"{hour:02d}:00:00",
                tz="UTC",
            )

            url = NOAA_TEMPLATE.format(
                date=ymd,
                hour=hour,
            )

            r = fetch_head(
                session,
                url,
            )

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

            lag = (
                (
                    published
                    - cycle
                ).total_seconds()
                / 60.0
                if published
                is not None
                else None
            )

            object_meta[
                (
                    event_date,
                    hour,
                )
            ] = {
                "cycle_time_utc":
                    cycle,
                "noaa_url":
                    url,
                "noaa_http_status":
                    r.status_code,
                "publication_time_utc":
                    published,
                "publication_lag_minutes":
                    lag,
                "etag":
                    r.headers.get(
                        "ETag"
                    ),
            }

            print(
                f"  {hour:02d}Z | "
                f"HTTP={r.status_code} | "
                f"published={published} | "
                f"lag="
                + (
                    f"{lag:.1f}m"
                    if lag is not None
                    else "NA"
                )
            )

            time.sleep(0.05)

    rows = []

    for event_date in DATES:
        print()
        print(
            "-" * 88
        )
        print(
            f"IEM target-value census | "
            f"{event_date}"
        )

        for city, station in (
            CITY.items()
        ):
            usable_hours = []

            for hour in HOURS:
                meta = object_meta[
                    (
                        event_date,
                        hour,
                    )
                ]

                cycle = meta[
                    "cycle_time_utc"
                ]

                iem = fetch_iem(
                    session,
                    station,
                    cycle,
                    event_date,
                )

                usable = (
                    meta[
                        "noaa_http_status"
                    ]
                    == 200
                    and meta[
                        "publication_time_utc"
                    ]
                    is not None
                    and iem[
                        "target_rows"
                    ]
                    == 1
                )

                if usable:
                    usable_hours.append(
                        hour
                    )

                rows.append(
                    {
                        "event_date_local":
                            event_date,
                        "city":
                            city,
                        "station":
                            station,

                        "cycle_hour_utc":
                            hour,
                        "cycle_time_utc":
                            cycle,

                        "noaa_http_status":
                            meta[
                                "noaa_http_status"
                            ],
                        "noaa_url":
                            meta[
                                "noaa_url"
                            ],
                        "publication_time_utc":
                            meta[
                                "publication_time_utc"
                            ],
                        "publication_lag_minutes":
                            meta[
                                "publication_lag_minutes"
                            ],
                        "etag":
                            meta["etag"],

                        "iem_http_status":
                            iem[
                                "iem_http_status"
                            ],
                        "target_rows":
                            iem[
                                "target_rows"
                            ],
                        "txn":
                            iem["txn"],
                        "xnd":
                            iem["xnd"],

                        "usable_state":
                            usable,
                    }
                )

                time.sleep(0.08)

            print(
                f"  {city:<8} | "
                f"usable cycles: "
                + (
                    ", ".join(
                        f"{h:02d}Z"
                        for h in usable_hours
                    )
                    if usable_hours
                    else "NONE"
                )
            )

    df = pd.DataFrame(
        rows
    )

    df.to_csv(
        OUTDIR
        / "v2_weather_cadence_census_rows.csv",
        index=False,
    )

    usable = df[
        df["usable_state"]
    ].copy()

    cycle_dist = (
        usable.groupby(
            "cycle_hour_utc"
        )
        .size()
        .rename(
            "usable_states"
        )
        .reset_index()
    )

    cycle_dist.to_csv(
        OUTDIR
        / "v2_weather_cadence_cycle_distribution.csv",
        index=False,
    )

    pair_rows = []

    for (
        event_date,
        city,
    ), g in usable.groupby(
        [
            "event_date_local",
            "city",
        ]
    ):
        g = g.sort_values(
            "publication_time_utc"
        )

        records = list(
            g.itertuples(
                index=False
            )
        )

        for old, new in zip(
            records[:-1],
            records[1:],
        ):
            pub_old = to_utc(
                old.publication_time_utc
            )

            pub_new = to_utc(
                new.publication_time_utc
            )

            pair_rows.append(
                {
                    "event_date_local":
                        event_date,
                    "city":
                        city,

                    "old_cycle_hour_utc":
                        old.cycle_hour_utc,
                    "new_cycle_hour_utc":
                        new.cycle_hour_utc,

                    "old_publication_time_utc":
                        pub_old,
                    "new_publication_time_utc":
                        pub_new,

                    "inter_publication_gap_minutes":
                        (
                            pub_new
                            - pub_old
                        ).total_seconds()
                        / 60.0,

                    "old_txn":
                        old.txn,
                    "new_txn":
                        new.txn,
                    "delta_txn":
                        new.txn
                        - old.txn,

                    "old_xnd":
                        old.xnd,
                    "new_xnd":
                        new.xnd,
                    "delta_xnd":
                        new.xnd
                        - old.xnd,
                }
            )

    pairs = pd.DataFrame(
        pair_rows
    )

    pairs.to_csv(
        OUTDIR
        / "v2_weather_revision_pairs.csv",
        index=False,
    )

    total_nominal = len(df)

    usable_count = int(
        df["usable_state"].sum()
    )

    city_days = (
        df[
            [
                "event_date_local",
                "city",
            ]
        ]
        .drop_duplicates()
        .shape[0]
    )

    pair_counts = (
        pairs.groupby(
            [
                "event_date_local",
                "city",
            ]
        )
        .size()
        if len(pairs)
        else pd.Series(
            dtype=int
        )
    )

    city_days_with_pair = int(
        (
            pair_counts > 0
        ).sum()
    )

    city_days_without_pair = (
        city_days
        - city_days_with_pair
    )

    lag = usable[
        "publication_lag_minutes"
    ].dropna()

    gaps = (
        pairs[
            "inter_publication_gap_minutes"
        ]
        if len(pairs)
        else pd.Series(
            dtype=float
        )
    )

    print()
    print("=" * 88)
    print(
        "V2 WEATHER FEASIBILITY SUMMARY"
    )
    print("=" * 88)

    print(
        "Dates examined:                    ",
        len(DATES),
    )
    print(
        "City-days examined:                ",
        city_days,
    )
    print(
        "Nominal city-cycle records:        ",
        total_nominal,
    )
    print(
        "Usable TXN/XND forecast states:    ",
        usable_count,
    )

    print()
    print(
        "Usable-state distribution by cycle:"
    )

    if len(cycle_dist):
        for r in (
            cycle_dist.itertuples(
                index=False
            )
        ):
            print(
                f"  {int(r.cycle_hour_utc):02d}Z: "
                f"{int(r.usable_states)}"
            )
    else:
        print(
            "  NONE"
        )

    print()
    print(
        "Sequential revision pairs:         ",
        len(pairs),
    )
    print(
        "City-days with >=1 revision pair:  ",
        city_days_with_pair,
    )
    print(
        "City-days with no revision pair:   ",
        city_days_without_pair,
    )

    if len(lag):
        print()
        print(
            "Publication lag among usable states:"
        )
        print(
            f"  min:    {lag.min():.1f} min"
        )
        print(
            f"  median: {lag.median():.1f} min"
        )
        print(
            f"  max:    {lag.max():.1f} min"
        )

    if len(gaps):
        print()
        print(
            "Inter-publication gap between "
            "sequential usable states:"
        )
        print(
            f"  min:    {gaps.min():.1f} min"
        )
        print(
            f"  median: {gaps.median():.1f} min"
        )
        print(
            f"  max:    {gaps.max():.1f} min"
        )

    print()
    print(
        "Saved:"
    )
    print(
        "  results/v2_feasibility/"
        "v2_weather_cadence_census_rows.csv"
    )
    print(
        "  results/v2_feasibility/"
        "v2_weather_cadence_cycle_distribution.csv"
    )
    print(
        "  results/v2_feasibility/"
        "v2_weather_revision_pairs.csv"
    )

    print()
    print(
        "NOTE: This is a cadence/metadata feasibility census."
    )
    print(
        "Direct raw NOAA bulletin verification will be done "
        "only for the usable-cycle pattern identified here."
    )


if __name__ == "__main__":
    main()
