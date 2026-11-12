from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PANEL_PATH = Path("data/processed/weather_panel_primary.csv")
RAW_DIR = Path("data/raw/weather/nbm_nbs")
RESULTS_DIR = Path("results/development")


def main():
    df = pd.read_csv(PANEL_PATH)

    for col in [
        "decision_time_local",
        "decision_time_utc",
        "cycle_time_utc",
        "assumed_available_at_utc",
        "forecast_valid_time_utc",
        "forecast_window_start_utc",
        "forecast_window_end_utc",
    ]:
        df[col] = pd.to_datetime(
            df[col],
            utc=True,
            errors="coerce",
        )

    problems = []

    # --------------------------------------------------
    # Basic structure
    # --------------------------------------------------

    if len(df) != 138:
        problems.append(
            f"Expected 138 rows, found {len(df)}."
        )

    duplicate_count = int(
        df.duplicated(
            ["city", "event_date_local"]
        ).sum()
    )

    if duplicate_count:
        problems.append(
            f"Duplicate city-days: {duplicate_count}"
        )

    city_counts = (
        df.groupby("city")["event_date_local"]
        .nunique()
        .sort_index()
    )

    # --------------------------------------------------
    # Frozen decision-time / cycle checks
    # --------------------------------------------------

    decision_local_hour_bad = 0

    # Parse original ISO strings again without forcing UTC,
    # so the local offset/hour is preserved.
    raw_df = pd.read_csv(PANEL_PATH)

    for value in raw_df["decision_time_local"]:
        ts = pd.Timestamp(value)

        if ts.hour != 10 or ts.minute != 0:
            decision_local_hour_bad += 1

    if decision_local_hour_bad:
        problems.append(
            f"Non-10:00 local decisions: "
            f"{decision_local_hour_bad}"
        )

    bad_cycle_hour = int(
        (df["cycle_time_utc"].dt.hour != 12).sum()
    )

    if bad_cycle_hour:
        problems.append(
            f"Non-12Z selected cycles: {bad_cycle_hour}"
        )

    lag_minutes = (
        (
            df["assumed_available_at_utc"]
            - df["cycle_time_utc"]
        )
        .dt.total_seconds()
        / 60.0
    )

    bad_lag = int(
        (~lag_minutes.eq(60)).sum()
    )

    if bad_lag:
        problems.append(
            f"Rows not using exactly +60m lag: "
            f"{bad_lag}"
        )

    availability_violations = int(
        (
            df["assumed_available_at_utc"]
            > df["decision_time_utc"]
        ).sum()
    )

    if availability_violations:
        problems.append(
            f"Availability violations: "
            f"{availability_violations}"
        )

    # --------------------------------------------------
    # Forecast-valid-time checks
    # --------------------------------------------------

    event_dates = pd.to_datetime(
        df["event_date_local"]
    )

    expected_valid = (
        event_dates
        + pd.Timedelta(days=1)
    ).dt.tz_localize("UTC")

    valid_mismatch = int(
        (
            df["forecast_valid_time_utc"]
            != expected_valid
        ).sum()
    )

    if valid_mismatch:
        problems.append(
            f"00Z-next-day valid-time mismatches: "
            f"{valid_mismatch}"
        )

    window_hours = (
        (
            df["forecast_window_end_utc"]
            - df["forecast_window_start_utc"]
        )
        .dt.total_seconds()
        / 3600.0
    )

    bad_window = int(
        (~window_hours.eq(18)).sum()
    )

    if bad_window:
        problems.append(
            f"Non-18h forecast windows: "
            f"{bad_window}"
        )

    # --------------------------------------------------
    # Weather-value integrity
    # --------------------------------------------------

    missing_txn = int(df["txn"].isna().sum())
    missing_xnd = int(df["xnd"].isna().sum())

    nonpositive_xnd = int(
        (df["xnd"] <= 0).sum()
    )

    if missing_txn:
        problems.append(
            f"Missing TXN rows: {missing_txn}"
        )

    if missing_xnd:
        problems.append(
            f"Missing XND rows: {missing_xnd}"
        )

    if nonpositive_xnd:
        problems.append(
            f"Non-positive XND rows: "
            f"{nonpositive_xnd}"
        )

    # --------------------------------------------------
    # Raw -> processed audit, all 138 rows
    # --------------------------------------------------

    raw_match_failures = []

    for row in raw_df.itertuples(index=False):
        cycle = pd.Timestamp(
            row.cycle_time_utc
        )

        filename = (
            f"{row.event_date_local}_"
            f"{cycle:%Y%m%dT%H%MZ}.json"
        )

        raw_path = (
            RAW_DIR
            / row.station
            / filename
        )

        if not raw_path.exists():
            raw_match_failures.append(
                (
                    row.city,
                    row.event_date_local,
                    "raw_file_missing",
                )
            )
            continue

        raw = json.loads(
            raw_path.read_text(
                encoding="utf-8"
            )
        )

        payload = raw.get(
            "api_response",
            raw,
        )

        target_valid = pd.Timestamp(
            row.forecast_valid_time_utc
        ).tz_convert(None)

        matches = []

        for api_row in payload.get("data", []):
            if not api_row.get("ftime_utc"):
                continue

            api_valid = pd.Timestamp(
                api_row["ftime_utc"]
            )

            if api_valid == target_valid:
                if (
                    api_row.get("txn") is not None
                    and api_row.get("xnd") is not None
                ):
                    matches.append(api_row)

        if len(matches) != 1:
            raw_match_failures.append(
                (
                    row.city,
                    row.event_date_local,
                    f"match_count={len(matches)}",
                )
            )
            continue

        api_row = matches[0]

        if (
            float(api_row["txn"])
            != float(row.txn)
            or float(api_row["xnd"])
            != float(row.xnd)
        ):
            raw_match_failures.append(
                (
                    row.city,
                    row.event_date_local,
                    "value_mismatch",
                )
            )

    if raw_match_failures:
        problems.append(
            f"Raw->processed match failures: "
            f"{len(raw_match_failures)}"
        )

    # --------------------------------------------------
    # Descriptive summaries
    # --------------------------------------------------

    by_city = (
        df.groupby("city")
        .agg(
            n=("event_date_local", "size"),
            txn_min=("txn", "min"),
            txn_median=("txn", "median"),
            txn_mean=("txn", "mean"),
            txn_max=("txn", "max"),
            xnd_min=("xnd", "min"),
            xnd_median=("xnd", "median"),
            xnd_mean=("xnd", "mean"),
            xnd_max=("xnd", "max"),
        )
        .round(3)
    )

    xnd_counts = (
        df.groupby(
            ["city", "xnd"]
        )
        .size()
        .unstack(fill_value=0)
    )

    decision_buffer_hours = (
        (
            df["decision_time_utc"]
            - df["assumed_available_at_utc"]
        )
        .dt.total_seconds()
        / 3600.0
    )

    summary = []

    summary.append(
        "Primary weather panel QC"
    )
    summary.append("=" * 64)

    summary.append(
        f"Rows:                         {len(df)}"
    )

    summary.append(
        f"Unique city-days:             "
        f"{df[['city','event_date_local']].drop_duplicates().shape[0]}"
    )

    summary.append(
        f"Duplicate city-days:          {duplicate_count}"
    )

    summary.append(
        f"Missing TXN:                  {missing_txn}"
    )

    summary.append(
        f"Missing XND:                  {missing_xnd}"
    )

    summary.append(
        f"Non-positive XND:             {nonpositive_xnd}"
    )

    summary.append(
        f"Non-10:00 local decisions:    "
        f"{decision_local_hour_bad}"
    )

    summary.append(
        f"Non-12Z selected cycles:      {bad_cycle_hour}"
    )

    summary.append(
        f"Non-60m availability lags:    {bad_lag}"
    )

    summary.append(
        f"Availability violations:      "
        f"{availability_violations}"
    )

    summary.append(
        f"Valid-time mismatches:        {valid_mismatch}"
    )

    summary.append(
        f"Non-18h forecast windows:     {bad_window}"
    )

    summary.append(
        f"Raw->processed failures:      "
        f"{len(raw_match_failures)}"
    )

    summary.append("")
    summary.append(
        "City-day counts:"
    )

    for city, count in city_counts.items():
        summary.append(
            f"  {city:<8} {count}"
        )

    summary.append("")
    summary.append(
        "Decision buffer after assumed availability:"
    )

    summary.append(
        f"  min:    {decision_buffer_hours.min():.2f} h"
    )

    summary.append(
        f"  median: {decision_buffer_hours.median():.2f} h"
    )

    summary.append(
        f"  max:    {decision_buffer_hours.max():.2f} h"
    )

    summary.append("")
    summary.append(
        "TXN / XND summary by city:"
    )

    summary.append(
        by_city.to_string()
    )

    summary.append("")
    summary.append(
        "XND frequency table:"
    )

    summary.append(
        xnd_counts.to_string()
    )

    summary.append("")
    summary.append(
        "FINAL QC STATUS: "
        + (
            "PASS"
            if not problems
            else "FAIL"
        )
    )

    if problems:
        summary.append("")
        summary.append(
            "Problems:"
        )

        for p in problems:
            summary.append(
                f"- {p}"
            )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit_path = (
        RESULTS_DIR
        / "weather_panel_qc.txt"
    )

    audit_path.write_text(
        "\n".join(summary) + "\n",
        encoding="utf-8",
    )

    if raw_match_failures:
        pd.DataFrame(
            raw_match_failures,
            columns=[
                "city",
                "event_date_local",
                "problem",
            ],
        ).to_csv(
            RESULTS_DIR
            / "weather_raw_match_failures.csv",
            index=False,
        )

    print(
        "\n" + "\n".join(summary)
    )


if __name__ == "__main__":
    main()
