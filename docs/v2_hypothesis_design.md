# V2 Hypothesis Design — Forecast Revision and Information Arrival

Design date: 2026-09-30

V1 is closed.

V2 is a new study and must not be interpreted as a post-hoc rescue of the
V1 static TXN/XND specification.

All 46 historical TWC-regime dates already examined in V1 are considered
DEVELOPMENT data for V2.

No date from the V1 sample may be described as an untouched V2 holdout.

The definitive V2 evaluation must use observations collected after the
V2 Final Freeze.

---

## 1. Scientific Question

Does NEW public meteorological information contained in an updated NBM
forecast contain information that is not immediately and completely
incorporated into Kalshi weather-market prices?

V2 studies information arrival and market assimilation rather than the
static level of a weather forecast.

---

## 2. Primary Information Event

Primary historical event:

    transition from the previous eligible NBS cycle
    to the new 12Z NBS cycle

Primary comparison:

    06Z NBS -> 12Z NBS

for the same target city-day.

The relevant signal is the forecast REVISION, not the level of the 12Z
forecast alone.

---

## 3. Weather Revision Representation

For both the old and new NBS cycles, construct the same prespecified
six-bucket weather proxy distribution used only as a feature
transformation:

    q_old
    q_new

from TXN and XND.

Define bucket-level revision information using quantities such as:

    delta_q_j = q_new_j - q_old_j

and/or

    delta_log_odds_j =
        logit(q_new_j) - logit(q_old_j)

The exact final representation will be selected using V2 development data
only and frozen before prospective evaluation.

No V1 model coefficient or V1 weather performance is reused as evidence
for V2.

---

## 4. Information Availability

Because V2 studies market reaction to information arrival, forecast-cycle
time alone is NOT sufficient.

Historical V2 must attempt to recover a source-backed publication or
availability timestamp for each NBS cycle.

Preferred provenance:

    NOAA/NBM archive object publication metadata

IEM may be used for parsed forecast values, but not by itself as proof of
the exact public-release timestamp.

For each forecast cycle record, preserve:

- nominal model cycle time
- source publication/availability timestamp
- retrieval source
- target valid time
- station
- TXN
- XND

No post-release market-reaction claim may be made if historical release
timing cannot be established with adequate precision.

---

## 5. Market Event-Time Alignment

For every information event, define market states relative to the verified
forecast availability timestamp.

Candidate event-study states:

    PRE:
        latest complete synchronized six-bucket market snapshot
        ending at or before forecast availability

    POST +1H:
        first complete synchronized snapshot approximately one hour after
        availability

    POST +2H:
        analogous two-hour state

Exact alignment tolerances must be determined from the hourly candle
structure before outcome analysis and then frozen.

No future quote may be used in a PRE state.

All six bucket quotes within a state must be synchronized.

---

## 6. V2 Hypotheses

### H2.1 — Market Reaction

Larger NBM forecast revisions are associated with subsequent Kalshi
probability changes in the corresponding direction after the forecast
becomes publicly available.

This establishes whether the market measurably responds to the public
information event.

### H2.2 — Assimilation Lag

The market response is not always instantaneous or complete.

After an initial reaction window, the residual component of the forecast
revision may predict subsequent repricing.

This is the principal candidate mechanism for V2 market-relative edge.

### H2.3 — Settlement Relevance

Forecast-revision information may improve final settlement prediction
beyond the market state available at the relevant V2 decision time.

This must be evaluated separately from short-horizon repricing.

---

## 7. Required Distinction

Three different claims must remain separate:

1. INFORMATION CONTENT
   NBM revisions contain meteorologically meaningful new information.

2. MARKET ASSIMILATION
   Kalshi prices react to that information with a measurable dynamic.

3. TRADEABLE RESIDUAL
   Some information remains after realistic observation and execution
   delay, large enough to exceed bid/ask and fees.

Evidence for (1) or (2) does not establish (3).

---

## 8. Historical Development

The existing 46 TWC-regime dates may be used for:

- data engineering
- revision-feature design
- event-window design
- model selection
- descriptive event studies
- chronological rolling-origin development

They are not a clean V2 holdout because V1 outcomes have already been
examined.

Any historical V2 performance is development evidence only.

---

## 9. Prospective Evaluation

Before prospective V2 begins, freeze:

- exact information-event definition
- release-time source
- revision feature
- market reaction windows
- model family
- regularization
- trade/no-trade rule
- fee treatment
- execution delay
- pass/fail criteria

Only future observations after that freeze may support the primary V2
out-of-sample claim.

---

## 10. V2 Feasibility Gates

Do not proceed to V2 modeling unless the historical data support all of
the following:

A. Previous and new NBS cycles can be reconstructed for the same target.

B. TXN/XND revision can be obtained point-in-time without future-cycle
   contamination.

C. Historical release/availability timing can be established well enough
   to order PRE and POST market states.

D. Complete synchronized Kalshi market states exist around the event.

E. The number of usable information events is sufficient for a bounded
   statistical study.

If release timing cannot be established adequately, V2 must be redesigned
as a fixed-decision-time revision-prediction study and must NOT claim
short-horizon market-assimilation lag.

---

## 11. Prohibited V2 Behavior

Do not:

- change V1 conclusions;
- tune V1 again;
- call a V2 result an independent historical holdout;
- choose cities based on V1 profitability;
- search release windows based on realized PnL;
- add many forecast systems before the NBM revision hypothesis is tested;
- interpret a historical backtest as proof of live fill or scalable alpha.

---

## 12. Current Status

V2 hypothesis designed.

No V2 predictive, repricing, or economic result has yet been inspected.

Next step:

    V2 historical data-feasibility audit.
