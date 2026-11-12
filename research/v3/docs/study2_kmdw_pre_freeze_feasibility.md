# V3 Study 2 — KMDW Settlement-Aware Intraday Nowcasting: Pre-Freeze Feasibility

> **Historical-status note (2026-10-08):** This document is the preserved
> pre-freeze feasibility record. The current observation-only M0 route later
> reached Gate #3 and was **CLOSED / ECONOMIC KILL**. See
> [`study2_closure.md`](study2_closure.md). The status block below is retained
> as the state that existed when this document governed the study.

## Status

- **V3:** ACTIVE umbrella for prospective executable-alpha research.
- **Study 1:** DEFERRED PRE-D0; confirmatory collection never started.
- **Study 2:** PRE-FREEZE FEASIBILITY / NOT LIVE-READY.
- **Current evidence state:** `MODEL_DATA_INSUFFICIENT`.
- **Live-money status:** NOT AUTHORIZED / NOT LIVE-READY.

`MODEL_DATA_INSUFFICIENT` is the evidence state before Study 2 probability and
economic validation. It is not the result of an already-run 48–72 hour sprint
and is not evidence that KMDW nowcasting is unprofitable.

## Provenance boundary

The exact Study 1 repository state immediately before strategic deferral is
tagged:

`v3-study1-final-pre-d0-2026-10-06`

Study 1 frozen protocol, configuration, implementation, and accepted provenance
remain unchanged. The former confirmatory schedule must not be launched under
the current status.

V1 and V2 remain closed and must not be reopened for specification search.

## Study 2 question

For a ForecastEx KMDW daily-maximum-temperature threshold contract, can the
weather information actually available by intraday time `t` support a
settlement-event probability that remains favorable relative to a real
executable ask after fees, material execution/funding costs, and model
uncertainty?

For threshold `theta`:

- YES: `M_D > theta`
- NO: `M_D <= theta`

where `M_D` is the final temperature derived from the contract-specified
settlement source and local settlement date.

## Development boundaries

The settlement target is the exact legal source, not a convenient proxy maximum.
ASOS/METAR may be model inputs but are not automatically settlement labels or
hard lower bounds.

Continuous capture is allowed during pre-freeze feasibility. Development data
inspected now cannot later be relabeled as untouched confirmation.

The independent outcome unit is the KMDW local settlement date. Repeated
intraday states, thresholds, sides, quote requests, and fills do not create
additional independent outcome dates.

## Six allowed sprint end states

1. `DATA_TARGET_KILL`
2. `ECONOMIC_KILL`
3. `MODEL_DATA_INSUFFICIENT`
4. `EXECUTABLE_CANDIDATE`
5. `READY_TO_BUILD_ORDER_LIFECYCLE`
6. `READY_FOR_TINY_LIVE_DIAGNOSTIC`

Seventy-two hours is an upper bound, not a required wait and not a trading
deadline.

## Fastest current path

`exact settlement labels + consistently decoded historical KMDW observations`
`→ observation-only M0`
`→ date-level support and conservative probability interval`
`→ continuous full-ladder executable-ask screening`
`→ fresh requote`
`→ economic kill / candidate decision`

Historical forecast reconstruction is a separate lower-priority lane and must
not block the first observation-only model if point-in-time semantics are not
validated.

## Economic screen

For a current buyable side:

`g = q_conservative - ask - fee_cap - execution_reserve - funding_cost`

A candidate requires a valid fresh ask and strictly positive `g`, with the
probability supported in the actual candidate domain.

Model uncertainty belongs in the probability interval. The same risk must not
be subtracted again through an arbitrary reserve.

## First implementation tranche

The first Study 2 implementation is read-only.

Planned minimum components:

- `src/v3/study2/targets.py`
- `src/v3/study2/capture.py`
- `scripts/v3/run_study2_development.py`

Parallel historical work may add:

- `src/v3/study2/historical.py`
- `scripts/v3/backfill_study2.py`

No order-submission endpoint belongs in this first tranche.

## Live-money boundary

Current live-money status is:

**NOT AUTHORIZED / NOT LIVE-READY**

A live alpha order requires exact target and causal inputs, a supported
conservative probability for the actually buyable tail, verified/capped real
costs, fresh positive economic margin, a separately validated one-contract
order-to-cash lifecycle, current account/risk checks, and explicit user
authorization.

A profitable engineering diagnostic would not establish repeatable alpha.

## What this phase cannot prove

A 48–72 hour sprint cannot establish repeatable net alpha across independent
future settlement dates, stable fill/adverse-selection behavior, or capacity.

Its purpose is to kill weak paths quickly, identify a defensible executable
candidate if one exists, and state any irreducible evidence bottleneck exactly.
