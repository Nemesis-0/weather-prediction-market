# V3 Study 2 — Model-ready historical data contract

## Purpose

Transform the accepted 2024-01-01 through 2026-10-06 historical source census
into a leakage-auditable intraday state table **before any M0 fit**.

This stage contains no probability estimates, no model performance, no market
prices, no economic screening, and no order logic.

## Source roles are intentionally different

IEM KMDW ASOS/METAR observations are the point-in-time weather input source.

Weather Underground KMDW Daily Observations provide the final daily target
`M_D^WU`.

Row-count parity between IEM and WU is not required. WU observation count is QC
metadata only and must not be a model feature.

Observed nonzero `WU max - IEM max` values are preserved rather than reconciled
or forced to zero.

## Historical timestamp convention

Historical IEM retrieval does not reconstruct original HTTP receive time.

For each numeric-temperature METAR, the `DDHHMMZ` issue timestamp is parsed to
an unambiguous UTC instant and checked against the IEM Chicago-local
`valid_local` value.

That METAR issue timestamp is the historical point-in-time availability proxy.
This convention, and the lack of reconstructed original receive latency, must
be reviewed at Sol Max Gate #2.

Naive local time is never used as a unique key. This preserves both 01:53
observations on fall-DST days.

Rows with null `tmpf` remain source/audit evidence but do not enter the
temperature state. If two numeric rows at the same UTC instant disagree on
temperature, construction fails closed.

## Intraday grid

States are constructed on a 30-minute UTC-stepped grid spanning each Chicago
local calendar day.

This naturally produces:
- 46 grid states on a 23-hour spring-DST day,
- 48 on a normal day,
- 50 on a 25-hour fall-DST day.

At each decision timestamp, only METAR observations issued at or before that
timestamp are eligible.

The table records:
- current/latest temperature,
- running observed maximum,
- current temperature minus running maximum,
- latest-observation age,
- a deterministic 60-minute backward temperature reference/change,
- final WU daily maximum as target,
- `M_D^WU - m_D,t^ASOS` as target residual.

Unavailable early-day states are retained with `state_available=false`.

## Frozen chronological split

Frozen before any model fit or performance inspection:

- Train: 2024-01-01 through 2024-12-31
- Calibration: 2025-01-01 through 2025-12-31
- Historical validation: 2026-01-01 through 2026-10-06

Dates never cross split boundaries.

If Gate #2 finds that support is scientifically insufficient, backward
historical extension may be considered as a data-support remedy **before M0
evaluation**. The split or census must not be changed in response to model
performance or economic results.

## WU historical-vintage limitation

Historical WU pages were retrieved after their event dates. The dataset does
not claim to reconstruct the exact WU page vintage seen at original ForecastEx
settlement time.

This remains an explicit Gate #2 issue.

## Gate boundary

After this table and its QC artifacts are reviewed internally, stop.

The next high-capacity review is:

**SOL MAX GATE #2 — HISTORICAL / MODEL-READY DATA GATE**

No M0 scientific inference is authorized before Gate #2 GO.
