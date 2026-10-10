from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


WEATHER_PATH = Path(
    "data/processed/weather_panel_primary.csv"
)

CENSUS_PATH = Path(
    "results/audit/v1_noaa_publication_timing_census.csv"
)

FALLBACK_PATH = Path(
    "results/audit/v1_weather_violation_fallback_probe.csv"
)

RAW_DIR = Path(
    "data/raw/weather/nbm_nbs"
)

ARCHIVE = Path(
    "archive/v1_pre_source_timing_correction"
)

CORRECTION_OUT = Path(
    "results/audit/v1_weather_timing_correction_rows.csv"
)

MANIFEST_OUT = Path(
    "results/audit/v1_weather_timing_correction_manifest.txt"
)

IEM_URL = (
    "https://mesonet.agron.iastate.edu/api/1/mos.json"
)


EXPECTED_CORRECTIONS = {
    ("NYC", "2026-08-31"): {
        "cycle": "2026-08-31T06:00:00+00:00",
        "published": "2026-08-31T06:49:06+00:00",
        "txn": 79.0,
        "xnd": 3.0,
    },
    ("NYC", "2026-09-24"): {
        "cycle": "2026-09-23T18:00:00+00:00",
        "published": "2026-09-23T18:55:41+00:00",
        "txn": 68.0,
        "xnd": 3.0,
    },
    ("Chicago", "2026-09-24"): {
        "cycle": "2026-09-24T00:00:00+00:00",
        "published": "2026-09-24T14:17:12+00:00",
        "txn": 69.0,
        "xnd": 2.0,
    },
    ("Denver", "2026-09-24"): {
        "cycle": "2026-09-24T06:00:00+00:00",
        "published": "2026-09-24T15:31:56+00:00",
        "txn": 72.0,
        "xnd": 4.0,
    },
}


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def to_utc(x):
    ts = pd.Timestamp(x)

    if ts.tzinfo is None:
        return ts.tz_localize("UTC")

    return ts.tz_convert("UTC")


def fetch_iem_raw(
    station: str,
    cycle: pd.Timestamp,
):
    runtime = cycle.strftime(
        "%Y-%m-%d %H:%MZ"
    )

    r = requests.get(
        IEM_URL,
        params={
            "station": station,
            "model": "NBS",
            "runtime": runtime,
        },
        timeout=30,
    )

    r.raise_for_status()

    return r.json()


def archive_original_state():
    if ARCHIVE.exists():
        raise RuntimeError(
            f"Archive already exists: {ARCHIVE}\n"
            "Refusing to overwrite the pre-correction snapshot."
        )

    ARCHIVE.mkdir(
        parents=True
    )

    files = [
        "data/processed/weather_panel_primary.csv",
        "data/processed/modeling_master_event.csv",
        "data/processed/modeling_master_long.csv",
        "data/processed/model_features_event.csv",

        "docs/v1_point_in_time_implementation_audit.md",

        "results/development/development_model_summary.txt",
        "results/development/development_lambda_selection.csv",
        "results/development/development_full_fit.json",
        "results/historical_holdout/historical_holdout_summary.txt",
        "results/historical_holdout/historical_holdout_model_summary.csv",
        "results/historical_holdout/historical_holdout_fit.json",
        "results/historical_economics/historical_economic_summary.csv",
        "results/historical_economics/historical_execution_stress_summary.csv",
        "results/historical_economics/historical_execution_stress_m2_vs_m0.csv",
    ]

    manifest = []

    for name in files:
        src = Path(name)

        if not src.exists():
            continue

        dst = ARCHIVE / name

        dst.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            src,
            dst,
        )

        manifest.append(
            (
                sha256(src),
                name,
            )
        )

    text = [
        "V1 pre-source-timing-correction snapshot",
        "=" * 80,
        (
            "Created UTC: "
            + datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "",
        (
            "This snapshot preserves the V1 results produced "
            "under the original +60-minute assumed availability rule."
        ),
        "",
        (
            "Those results were subsequently found to contain "
            "four source-publication timing violations and are "
            "superseded for final V1 interpretation."
        ),
        "",
    ]

    for digest, name in manifest:
        text.append(
            f"{digest}  {name}"
        )

    (
        ARCHIVE
        / "MANIFEST.txt"
    ).write_text(
        "\n".join(text) + "\n",
        encoding="utf-8",
    )


def main():
    if not WEATHER_PATH.exists():
        raise FileNotFoundError(
            WEATHER_PATH
        )

    if not CENSUS_PATH.exists():
        raise FileNotFoundError(
            CENSUS_PATH
        )

    if not FALLBACK_PATH.exists():
        raise FileNotFoundError(
            FALLBACK_PATH
        )

    # --------------------------------------------------
    # Preserve contaminated/original state first.
    # --------------------------------------------------

    archive_original_state()

    weather = pd.read_csv(
        WEATHER_PATH
    )

    census = pd.read_csv(
        CENSUS_PATH
    )

    fallback = pd.read_csv(
        FALLBACK_PATH
    )

    if len(weather) != 138:
        raise RuntimeError(
            f"Expected 138 weather rows; "
            f"found {len(weather)}"
        )

    # --------------------------------------------------
    # Add source-backed availability metadata to all rows.
    # For normal rows this comes from the 12Z census.
    # --------------------------------------------------

    census_small = (
        census[
            [
                "city",
                "event_date_local",
                "noaa_last_modified_utc",
                "actual_release_lag_minutes",
                "actual_margin_minutes",
                "actual_available_before_decision",
            ]
        ]
        .rename(
            columns={
                "noaa_last_modified_utc":
                    "source_available_at_utc",
                "actual_release_lag_minutes":
                    "source_release_lag_minutes",
                "actual_margin_minutes":
                    "source_availability_margin_minutes",
                "actual_available_before_decision":
                    "source_available_before_decision",
            }
        )
    )

    weather = weather.merge(
        census_small,
        on=[
            "city",
            "event_date_local",
        ],
        how="left",
        validate="one_to_one",
    )

    weather[
        "availability_provenance"
    ] = (
        "NOAA NBM S3 object Last-Modified"
    )

    weather[
        "v1_timing_corrected"
    ] = False

    weather[
        "original_cycle_time_utc"
    ] = weather[
        "cycle_time_utc"
    ]

    weather[
        "original_txn"
    ] = weather[
        "txn"
    ]

    weather[
        "original_xnd"
    ] = weather[
        "xnd"
    ]

    correction_records = []

    # --------------------------------------------------
    # Apply only the four mechanically identified rows.
    # --------------------------------------------------

    for (
        city,
        event_date,
    ), expected in (
        EXPECTED_CORRECTIONS.items()
    ):
        mask = (
            (weather["city"] == city)
            & (
                weather[
                    "event_date_local"
                ]
                == event_date
            )
        )

        if mask.sum() != 1:
            raise RuntimeError(
                f"Expected one weather row for "
                f"{city} {event_date}; "
                f"found {mask.sum()}"
            )

        station = weather.loc[
            mask,
            "station",
        ].iloc[0]

        decision = to_utc(
            weather.loc[
                mask,
                "decision_time_utc",
            ].iloc[0]
        )

        cycle = to_utc(
            expected["cycle"]
        )

        published = to_utc(
            expected["published"]
        )

        if published > decision:
            raise RuntimeError(
                f"Correction itself is not point-in-time eligible: "
                f"{city} {event_date}"
            )

        # Verify this exact fallback exists in the probe file.
        fb = fallback[
            (fallback["city"] == city)
            & (
                fallback[
                    "event_date_local"
                ]
                == event_date
            )
            & (
                pd.to_datetime(
                    fallback[
                        "cycle_time_utc"
                    ],
                    utc=True,
                )
                == cycle
            )
        ]

        if len(fb) != 1:
            raise RuntimeError(
                f"Fallback probe row not unique for "
                f"{city} {event_date}"
            )

        fbrow = fb.iloc[0]

        if not bool(
            fbrow["eligible"]
        ):
            raise RuntimeError(
                f"Frozen fallback row is not eligible: "
                f"{city} {event_date}"
            )

        if (
            float(fbrow["txn"])
            != expected["txn"]
            or float(fbrow["xnd"])
            != expected["xnd"]
        ):
            raise RuntimeError(
                f"Fallback values differ from expected "
                f"for {city} {event_date}"
            )

        # Independently fetch the exact parsed IEM runtime again.
        payload = fetch_iem_raw(
            station,
            cycle,
        )

        target_valid = (
            pd.Timestamp(event_date)
            + pd.Timedelta(
                days=1
            )
        ).tz_localize("UTC")

        matches = []

        for r in payload.get(
            "data",
            [],
        ):
            if (
                r.get("ftime_utc")
                is None
            ):
                continue

            try:
                ftime = to_utc(
                    r["ftime_utc"]
                )
            except Exception:
                continue

            if (
                ftime == target_valid
                and r.get("txn")
                is not None
                and r.get("xnd")
                is not None
            ):
                matches.append(r)

        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one target TXN/XND row from IEM for "
                f"{city} {event_date}; found {len(matches)}"
            )

        source = matches[0]

        if (
            float(source["txn"])
            != expected["txn"]
            or float(source["xnd"])
            != expected["xnd"]
        ):
            raise RuntimeError(
                f"Fresh IEM verification differs for "
                f"{city} {event_date}"
            )

        # Preserve fallback raw API response.
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
                f"{cycle:%Y%m%dT%H%MZ}.json"
            )
        )

        wrapper = {
            "retrieved_at_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "correction":
                "V1 source-publication timing correction",
            "city":
                city,
            "station":
                station,
            "event_date_local":
                event_date,
            "decision_time_utc":
                decision.isoformat(),
            "cycle_time_utc":
                cycle.isoformat(),
            "source_available_at_utc":
                published.isoformat(),
            "availability_provenance":
                "NOAA NBM S3 object Last-Modified",
            "model":
                "NBM",
            "product":
                "NBS",
            "archive_provider":
                "IEM",
            "api_response":
                payload,
        }

        raw_path.write_text(
            json.dumps(
                wrapper,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        old_cycle = weather.loc[
            mask,
            "cycle_time_utc",
        ].iloc[0]

        old_txn = float(
            weather.loc[
                mask,
                "txn",
            ].iloc[0]
        )

        old_xnd = float(
            weather.loc[
                mask,
                "xnd",
            ].iloc[0]
        )

        margin = (
            (
                decision
                - published
            ).total_seconds()
            / 60.0
        )

        release_lag = (
            (
                published
                - cycle
            ).total_seconds()
            / 60.0
        )

        weather.loc[
            mask,
            "cycle_time_utc",
        ] = cycle.isoformat()

        # Keep the old assumed +60m field for historical traceability.
        # Model code does not use this field as a predictor.
        #
        # Source-backed timing goes in the new source_* fields.
        weather.loc[
            mask,
            "source_available_at_utc",
        ] = published.isoformat()

        weather.loc[
            mask,
            "source_release_lag_minutes",
        ] = release_lag

        weather.loc[
            mask,
            "source_availability_margin_minutes",
        ] = margin

        weather.loc[
            mask,
            "source_available_before_decision",
        ] = True

        weather.loc[
            mask,
            "txn",
        ] = expected["txn"]

        weather.loc[
            mask,
            "xnd",
        ] = expected["xnd"]

        weather.loc[
            mask,
            "v1_timing_corrected",
        ] = True

        correction_records.append(
            {
                "city":
                    city,
                "event_date_local":
                    event_date,
                "station":
                    station,
                "decision_time_utc":
                    decision.isoformat(),

                "old_cycle_time_utc":
                    old_cycle,
                "old_txn":
                    old_txn,
                "old_xnd":
                    old_xnd,

                "corrected_cycle_time_utc":
                    cycle.isoformat(),
                "corrected_source_available_at_utc":
                    published.isoformat(),
                "corrected_margin_minutes":
                    margin,
                "corrected_txn":
                    expected["txn"],
                "corrected_xnd":
                    expected["xnd"],

                "raw_fallback_file":
                    str(raw_path),
            }
        )

    # --------------------------------------------------
    # Mechanical final integrity checks.
    # --------------------------------------------------

    corrected = weather[
        weather[
            "v1_timing_corrected"
        ]
    ]

    if len(corrected) != 4:
        raise RuntimeError(
            f"Expected exactly 4 corrected rows; "
            f"found {len(corrected)}"
        )

    source_available = pd.to_datetime(
        weather[
            "source_available_at_utc"
        ],
        utc=True,
    )

    decisions = pd.to_datetime(
        weather[
            "decision_time_utc"
        ],
        utc=True,
    )

    violations_after = int(
        (
            source_available
            > decisions
        ).sum()
    )

    if violations_after != 0:
        raise RuntimeError(
            f"Still have {violations_after} "
            "source-timing violations after correction."
        )

    if (
        weather["txn"].isna().any()
        or weather["xnd"].isna().any()
    ):
        raise RuntimeError(
            "TXN/XND missing after correction."
        )

    # Save corrected canonical weather panel.
    weather.to_csv(
        WEATHER_PATH,
        index=False,
    )

    corrections = pd.DataFrame(
        correction_records
    )

    corrections.to_csv(
        CORRECTION_OUT,
        index=False,
    )

    manifest = [
        "V1 source-publication timing correction",
        "=" * 80,
        (
            "Applied UTC: "
            + datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "",
        "Correction count: 4",
        "",
        "No feature, model, lambda grid, scoring rule, market snapshot,",
        "trading rule, or economic rule was changed.",
        "",
        "The only correction was replacement of weather information that",
        "was not yet source-verified as publicly available at the frozen",
        "10AM local decision time.",
        "",
        "Corrected rows:",
        corrections.to_string(
            index=False
        ),
        "",
        (
            "Post-correction source-timing violations: "
            f"{violations_after}"
        ),
        "",
        (
            "Corrected canonical weather panel SHA256: "
            f"{sha256(WEATHER_PATH)}"
        ),
        "",
        (
            "Original contaminated state preserved at: "
            f"{ARCHIVE}"
        ),
    ]

    MANIFEST_OUT.write_text(
        "\n".join(manifest) + "\n",
        encoding="utf-8",
    )

    print(
        "\nV1 WEATHER TIMING CORRECTION"
    )
    print("=" * 80)

    print(
        corrections[
            [
                "city",
                "event_date_local",
                "old_cycle_time_utc",
                "old_txn",
                "old_xnd",
                "corrected_cycle_time_utc",
                "corrected_txn",
                "corrected_xnd",
                "corrected_margin_minutes",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        "Corrected rows:                 ",
        len(corrections),
    )
    print(
        "Post-correction timing violations:",
        violations_after,
    )
    print(
        "Missing TXN:",
        int(
            weather["txn"].isna().sum()
        ),
    )
    print(
        "Missing XND:",
        int(
            weather["xnd"].isna().sum()
        ),
    )

    print(
        "\nORIGINAL STATE ARCHIVED:"
    )
    print(
        f"  {ARCHIVE}"
    )

    print(
        "\nCORRECTION MANIFEST:"
    )
    print(
        f"  {MANIFEST_OUT}"
    )

    print(
        "\nSTATUS: "
        "CORRECTION APPLIED — "
        "DOWNSTREAM V1 RESULTS MUST NOW BE RECOMPUTED"
    )


if __name__ == "__main__":
    main()
