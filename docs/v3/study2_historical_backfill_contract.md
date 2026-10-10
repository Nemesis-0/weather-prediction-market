# V3 Study 2 — Historical Backfill Construction Contract

## Status and boundary

This document governs the bulk historical source-construction stage after
Sol Max Gate #1 GO and after the bounded 8-date historical source-feasibility
probe passed.

This stage is **pre-model**. It does not authorize probability inference,
economic conclusions, candidate selection, order-lifecycle work, or live
trading.

## Sources

Each historical Chicago-local date is reconstructed from the same source
families accepted at H0:

1. IEM `IL_ASOS` station `MDW`, preserving KMDW routine + special ASOS/METAR
   observations and raw METAR text.
2. Weather Underground KMDW **Daily Observations**, parsed only through the
   station/date/timezone/table/unit identity checks already accepted at H0.

No alternate settlement label or convenient summary-high proxy may silently
replace the WU Daily Observations-derived target.

## Retrieval-vintage limitation

Historical WU pages are retrieved at current HTTP retrieval time. The backfill
does **not** claim that the retrieved page bytes equal the page state that
ForecastEx observed at original settlement time.

Every date-level record must preserve:

- current retrieval provenance,
- raw bytes and SHA256,
- the explicit historical-vintage limitation,
- `original_settlement_time_vintage_reconstructed = false`.

This limitation is an explicit Gate #2 review item.

## Date census

A bulk dataset is created from an explicit inclusive `start_date` / `end_date`
census before model fitting. A backfill root cannot later be reused with a
different census.

The census is contiguous; dates are not selected using outcomes, market prices,
or model results.

## Immutable-attempt and resume semantics

Each date attempt is written to a new immutable attempt directory.

- Existing verified `PASS` dates are skipped on resume.
- Failed or incomplete dates receive a new attempt directory.
- Previous failed raw responses are never overwritten.
- A date is `PASS` only if both IEM and WU parse/identity checks pass and the
  archived raw-payload SHA256 values verify.

## DST and time identity

Naive local clock labels are not unique on the fall DST transition. Duplicate
local labels must be preserved. A later model-ready transformation must create
unambiguous UTC/offset-aware observation timestamps before using time as a
model key.

## Target and observation semantics

Primary daily target:

`M_D^WU = max temperature in the exact parsed WU Daily Observations table`

Observation source:

KMDW ASOS/METAR observations retrieved through IEM.

The historical source layer records the IEM daily observed maximum only as QC.
It must **not** substitute that maximum for `M_D^WU`.

The quantity `M_D^WU - max(IEM temperature)` may be negative, zero, or positive.
No lower-bound assumption is imposed.

## Gate #2 boundary

Bulk backfill and later model-ready construction may proceed until the dataset
is complete enough to fit M0.

Before treating any M0 performance or probability as scientific evidence, stop
and submit the historical/model-ready dataset to Sol Max Gate #2.
