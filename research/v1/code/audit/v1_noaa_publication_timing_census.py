from __future__ import annotations

import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd
import requests


WEATHER_PATH = Path(
    "data/processed/weather_panel_primary.csv"
)

OUTDIR = Path("results/audit")

S3_TEMPLATE = (
    "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
    "blend.{date}/12/text/blend_nbstx.t12z"
)

MAX_RETRIES = 6


def to_utc(value):
    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


def head_object(
    session: requests.Session,
    url: str,
):
    for attempt in range(MAX_RETRIES):
        try:
            r = session.head(
                url,
                timeout=30,
                allow_redirects=True,
            )
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
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
        f"HEAD retries exhausted: {url}"
    )


def main():
    OUTDIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    weather = pd.read_csv(
        WEATHER_PATH
    )

    if len(weather) != 138:
        raise RuntimeError(
            f"Expected 138 weather rows, "
            f"found {len(weather)}"
        )

    weather[
        "decision_time_utc"
    ] = pd.to_datetime(
        weather[
            "decision_time_utc"
        ],
        utc=True,
    )

    weather[
        "cycle_time_utc"
    ] = pd.to_datetime(
        weather[
            "cycle_time_utc"
        ],
        utc=True,
    )

    weather[
        "assumed_available_at_utc"
    ] = pd.to_datetime(
        weather[
            "assumed_available_at_utc"
        ],
        utc=True,
    )

    dates = sorted(
        weather[
            "event_date_local"
        ].unique()
    )

    if len(dates) != 46:
        raise RuntimeError(
            f"Expected 46 event dates, "
            f"found {len(dates)}"
        )

    session = requests.Session()

    publication = {}

    print(
        "\nNOAA 12Z NBS PUBLICATION-TIMING CENSUS"
    )
    print("=" * 84)

    # --------------------------------------------------
    # One NOAA HEAD request per event date.
    # --------------------------------------------------

    for i, event_date in enumerate(
        dates,
        start=1,
    ):
        ymd = event_date.replace(
            "-",
            "",
        )

        url = S3_TEMPLATE.format(
            date=ymd
        )

        r = head_object(
            session,
            url,
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

        cycle = pd.Timestamp(
            f"{event_date}T12:00:00Z"
        )

        release_lag_min = (
            (
                last_modified
                - cycle
            ).total_seconds()
            / 60.0
            if last_modified
            is not None
            else None
        )

        publication[
            event_date
        ] = {
            "url": url,
            "http_status":
                r.status_code,
            "last_modified_utc":
                last_modified,
            "release_lag_minutes":
                release_lag_min,
            "etag":
                r.headers.get(
                    "ETag"
                ),
            "content_length":
                r.headers.get(
                    "Content-Length"
                ),
        }

        print(
            f"[{i:02d}/46] "
            f"{event_date} | "
            f"HTTP={r.status_code} | "
            f"published={last_modified} | "
            f"lag="
            + (
                f"{release_lag_min:.1f} min"
                if release_lag_min
                is not None
                else "NA"
            )
        )

        time.sleep(0.10)

    # --------------------------------------------------
    # Expand to the 138 model observations.
    # --------------------------------------------------

    rows = []

    for row in weather.itertuples(
        index=False
    ):
        info = publication[
            row.event_date_local
        ]

        actual_publication = (
            info[
                "last_modified_utc"
            ]
        )

        decision = to_utc(
            row.decision_time_utc
        )

        selected_cycle = to_utc(
            row.cycle_time_utc
        )

        assumed_available = to_utc(
            row.assumed_available_at_utc
        )

        selected_is_12z = (
            selected_cycle.hour == 12
            and selected_cycle.minute == 0
        )

        actual_available = (
            actual_publication
            is not None
            and actual_publication
            <= decision
        )

        actual_margin_min = (
            (
                decision
                - actual_publication
            ).total_seconds()
            / 60.0
            if actual_publication
            is not None
            else None
        )

        assumed_margin_min = (
            (
                decision
                - assumed_available
            ).total_seconds()
            / 60.0
        )

        rows.append(
            {
                "city":
                    row.city,
                "event_date_local":
                    row.event_date_local,
                "station":
                    row.station,

                "selected_cycle_utc":
                    selected_cycle.isoformat(),
                "selected_cycle_is_12z":
                    selected_is_12z,

                "decision_time_utc":
                    decision.isoformat(),

                "assumed_available_at_utc":
                    assumed_available.isoformat(),
                "assumed_margin_minutes":
                    assumed_margin_min,

                "noaa_http_status":
                    info[
                        "http_status"
                    ],
                "noaa_last_modified_utc":
                    (
                        actual_publication.isoformat()
                        if actual_publication
                        is not None
                        else None
                    ),
                "actual_release_lag_minutes":
                    info[
                        "release_lag_minutes"
                    ],
                "actual_margin_minutes":
                    actual_margin_min,

                "actual_available_before_decision":
                    actual_available,

                "actual_availability_violation":
                    not actual_available,

                "txn":
                    row.txn,
                "xnd":
                    row.xnd,

                "etag":
                    info["etag"],
                "content_length":
                    info[
                        "content_length"
                    ],
            }
        )

    audit = pd.DataFrame(
        rows
    )

    csv_path = (
        OUTDIR
        / "v1_noaa_publication_timing_census.csv"
    )

    audit.to_csv(
        csv_path,
        index=False,
    )

    # --------------------------------------------------
    # Diagnostics
    # --------------------------------------------------

    object_failures = int(
        (
            audit[
                "noaa_http_status"
            ]
            != 200
        ).sum()
    )

    missing_publication = int(
        audit[
            "noaa_last_modified_utc"
        ].isna().sum()
    )

    non_12z = int(
        (
            ~audit[
                "selected_cycle_is_12z"
            ]
        ).sum()
    )

    violations = int(
        audit[
            "actual_availability_violation"
        ].sum()
    )

    unique_violation_dates = (
        audit.loc[
            audit[
                "actual_availability_violation"
            ],
            "event_date_local",
        ]
        .nunique()
    )

    release_by_date = (
        audit[
            [
                "event_date_local",
                "actual_release_lag_minutes",
            ]
        ]
        .drop_duplicates()
    )

    city_summary = (
        audit.groupby("city")
        .agg(
            n=(
                "event_date_local",
                "size",
            ),
            violations=(
                "actual_availability_violation",
                "sum",
            ),
            margin_min=(
                "actual_margin_minutes",
                "min",
            ),
            margin_median=(
                "actual_margin_minutes",
                "median",
            ),
            margin_max=(
                "actual_margin_minutes",
                "max",
            ),
        )
        .round(2)
    )

    violation_rows = audit[
        audit[
            "actual_availability_violation"
        ]
    ].copy()

    violation_path = (
        OUTDIR
        / "v1_noaa_publication_timing_violations.csv"
    )

    violation_rows.to_csv(
        violation_path,
        index=False,
    )

    passed = all(
        [
            object_failures == 0,
            missing_publication == 0,
            non_12z == 0,
            violations == 0,
        ]
    )

    lines = [
        "V1 NOAA ACTUAL PUBLICATION-TIMING CENSUS",
        "=" * 84,
        f"Event dates examined:                 {len(dates)}",
        f"City-days examined:                   {len(audit)}",
        f"NOAA object HTTP failures:            {object_failures}",
        f"Missing Last-Modified timestamps:     {missing_publication}",
        f"Non-12Z selected V1 cycles:           {non_12z}",
        f"Actual availability violations:       {violations}",
        f"Dates with availability violations:   {unique_violation_dates}",
        "",
        "12Z NOAA publication lag from nominal cycle:",
        (
            f"  minimum: "
            f"{release_by_date['actual_release_lag_minutes'].min():.1f} min"
        ),
        (
            f"  median:  "
            f"{release_by_date['actual_release_lag_minutes'].median():.1f} min"
        ),
        (
            f"  maximum: "
            f"{release_by_date['actual_release_lag_minutes'].max():.1f} min"
        ),
        "",
        "Actual publication margin before 10AM decision by city:",
        city_summary.to_string(),
        "",
        "Important:",
        (
            "The original +60 minute availability rule was an "
            "assumed conservative eligibility rule, not the observed "
            "NOAA publication timestamp. This census replaces that "
            "assumption for the mechanical V1 provenance check."
        ),
        "",
        "FINAL NOAA TIMING STATUS: "
        + (
            "PASS"
            if passed
            else "FAIL — INVESTIGATE"
        ),
    ]

    if violations:
        lines.extend(
            [
                "",
                "VIOLATING CITY-DAYS:",
                violation_rows[
                    [
                        "city",
                        "event_date_local",
                        "decision_time_utc",
                        "noaa_last_modified_utc",
                        "actual_margin_minutes",
                    ]
                ].to_string(
                    index=False
                ),
            ]
        )

    report_path = (
        OUTDIR
        / "v1_noaa_publication_timing_census.txt"
    )

    report_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print(
        "\n"
        + "\n".join(lines)
    )

    print(
        f"\nSaved:\n  {csv_path}\n"
        f"  {violation_path}\n"
        f"  {report_path}"
    )


if __name__ == "__main__":
    main()
