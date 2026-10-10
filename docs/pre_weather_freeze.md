# Pre-Weather Analysis Freeze

Freeze date: 2026-09-30

## Purpose

This document freezes the main design choices that must be specified
before the full historical weather backfill and before observing
weather-vs-market predictive or PnL results.

This is not the final model freeze.

Its purpose is to reduce researcher degrees of freedom, prevent
decision-time / station / forecast-cycle cherry-picking, and protect
the validity of later Market-only vs Market+Weather comparisons.

---

## 1. Primary Research Question

Does public meteorological information contain incremental predictive
information beyond contemporaneous weather-market prices?

Primary predictive comparison:

M2 = Market + Weather

versus

M0 = Market-only

Economic profitability is a separate downstream question.

---

## 2. Outcome Definition

Each city-day is treated as one six-category outcome.

For each event:

Y ∈ {bucket 1, ..., bucket 6}

The six mutually exclusive Kalshi temperature contracts are not treated
as six independent Bernoulli observations.

Repeated timestamps within the same city-day are also not treated as
independent outcomes.

Current primary sample:

- New York City
- Chicago
- Denver
- current The Weather Company settlement regime
- 138 city-days total
- 46 calendar dates × 3 cities

Settlement labels come from the resolved Kalshi contracts.

NOAA observations or forecast stations are never used to reconstruct
or replace the settlement label.

---

## 3. Primary Decision Time

Primary decision time:

10:00 AM local time for each city.

Time zones:

- NYC: America/New_York
- Chicago: America/Chicago
- Denver: America/Denver

Other timestamps, including 13:00 and 16:00 local time, may be retained
for secondary / exploratory analysis but cannot replace 10:00 local as
the primary decision time based on observed performance.

---

## 4. Weather Stations

The primary predictor stations are frozen as:

- NYC: KNYC
- Chicago: KMDW
- Denver: KDEN

These are predictor locations only.

The study does not claim that KNYC, KMDW, or KDEN are necessarily
physically identical to the internal TWC settlement locations
CLINYC, CLIMDW, or CLIDEN.

Changing to nearby stations based on historical predictive or economic
performance is not permitted in the primary V1 analysis.

---

## 5. NBM / NBS Forecast Eligibility

Primary weather source:

- NOAA National Blend of Models (NBM)
- NBS text product
- historical access through the Iowa Environmental Mesonet archive/API

For each decision time, only forecasts satisfying the following rule
are eligible:

    assumed_available_at = cycle_time + 60 minutes

and

    assumed_available_at <= decision_time

The latest eligible cycle is used.

The 60-minute offset is a conservative point-in-time availability
assumption. It is deliberately more conservative than relying on the
nominal model cycle time.

No nearest-cycle matching is allowed.

No cycle with assumed availability after the decision time may be used.

Future information must never be substituted when an eligible forecast
is missing.

The historical sample is within the NBS 00/06/12/18Z operational-cycle
regime identified during source audit.

Forecast cycle, assumed availability time, decision time, and valid time
must all be retained in the processed data.

---

## 6. Role of TXN and XND

TXN and XND are weather predictors only.

They are not assumed to equal the mean and standard deviation of the
Kalshi/TWC calendar-day settlement temperature distribution.

In particular, NBS TXN represents an operational forecast-extreme
quantity whose forecast window does not exactly equal the TWC
calendar-day settlement target.

Therefore the primary analysis will NOT directly assume:

    T_settlement ~ Normal(TXN, XND^2)

and will not convert TXN/XND directly into six bucket probabilities
without target-specific calibration estimated using development data.

Any mapping from TXN/XND to settlement probabilities must be learned
under the chronological development protocol.

---

## 7. Market Probability Construction

For a synchronized six-bucket market snapshot, define each raw midpoint:

    m_i = (YES_bid_i + YES_ask_i) / 2

The transparent no-fit market probability vector is:

    p_i = m_i / sum_j(m_j)

This normalized six-dimensional vector is used as the raw Market-only
reference probability distribution.

Normalization is used only for probabilistic prediction/scoring.

Economic PnL must use actual executable bid/ask prices and must never
use normalized midpoint probabilities as executable prices.

---

## 8. Fair Market-only vs Market+Weather Comparison

The main incremental-information comparison must not give M2 a more
powerful calibration / fitting procedure than M0 solely because M2
contains weather information.

Primary fitted models must use matched:

- training periods
- chronological splits
- fitting procedure
- regularization framework
- calibration machinery
- evaluation timestamps

The defining difference is:

M0:
    market-derived predictors

M2:
    same market-derived predictors
    + weather predictors

A raw normalized-midpoint baseline will also be reported as a
transparent no-fit reference.

---

## 9. Primary Scoring Unit and Metrics

Primary unit:

    one city-day = one six-category outcome

Primary proper scoring rules:

### Multiclass log loss

    -log(p_true_bucket)

### Multiclass Brier score

    sum_k (p_k - y_k)^2

where y is a one-hot six-category outcome vector.

Binary bucket-level metrics may be reported only as secondary
diagnostics and must not be interpreted as independent sample sizes.

---

## 10. Dependence and Uncertainty

Dependence exists:

- across six buckets within the same city-day
- across repeated timestamps within the same city-day
- potentially across cities on the same calendar date
- across consecutive dates during persistent weather regimes

Primary uncertainty analysis will preserve calendar-date dependence.

Primary resampling method:

- moving-block bootstrap over consecutive calendar dates
- primary block length: 3 calendar days

Pre-specified sensitivity analyses:

- 1-day date-cluster bootstrap
- 7-day moving-block bootstrap

All three cities belonging to a sampled calendar date remain together
inside the resampling unit.

No inference will use 828 contracts or 4,738 snapshots as if they were
independent observations.

---

## 11. Required Weather Provenance

Each weather record must retain, where available:

- city
- station
- event date
- local timezone
- decision time local
- decision time UTC
- source
- model
- product
- model cycle time UTC
- assumed availability time UTC
- forecast valid time UTC
- TXN
- XND
- NBM/NBS regime or version metadata
- archive provider
- retrieval timestamp
- eligibility at decision time
- missing-data reason
- exclusion reason

Raw source records should be retained separately from processed features.

---

## 12. Missingness and Exclusions

Missing forecast data must not be replaced with a future cycle.

Missing market/weather observations must remain documented.

All exclusions must have an explicit reason.

Dates may not be removed because:

- the model performed poorly
- no apparent trading opportunity existed
- realized PnL was negative
- a weather regime was inconvenient

No-trade days and rejected candidate trades remain part of economic
evaluation.

---

## 13. Feature-Scope Rule for V1

The initial weather model should remain deliberately small.

NBM/NBS TXN/XND and simple pre-specified derivatives may be evaluated
before adding additional meteorological systems.

The primary V1 analysis will not initially add:

- large multi-model weather ensembles
- many nearby stations
- HRRR feature grids
- ECMWF features
- radar-derived features
- deep learning
- complex market-making features

Additional sources may be considered only after the initial V1 result
and must be labeled as later-stage development rather than silently
added to the primary historical specification.

---

## 14. What Is Not Yet Frozen

The following remain development-stage choices and will be frozen later,
before prospective evaluation:

- final weather feature transformation
- final model family
- regularization strength
- target-calibration procedure
- trading edge threshold
- no-trade threshold
- execution-delay assumptions
- position sizing
- capital limits
- final fee treatment
- final stop criteria

These choices must be finalized using development data only.

---

## 15. Interpretation Constraint

Historical evidence can establish whether a sufficiently large signal is
worth prospective testing.

Historical evidence alone cannot establish stable profitability.

A positive historical result must still survive:

1. matched Market-only comparison,
2. realistic bid/ask and fees,
3. frozen prospective testing,
4. reasonable execution-delay assumptions,
5. concentration and dependence checks,
6. liquidity/capacity analysis.


---

## 16. Primary Market-Snapshot Alignment

For the primary 10:00 AM local decision time, the market snapshot is
defined as:

- the latest complete synchronized six-bucket candlestick timestamp
  ending at or before the decision time;
- all six bucket quotes must come from exactly the same timestamp;
- future candlesticks are never permitted;
- asynchronous mixing of bucket quotes from different timestamps is
  not permitted;
- maximum permitted snapshot staleness is 60 minutes.

If no complete synchronized six-bucket snapshot exists within the
60 minutes preceding the primary decision time, that city-day is marked
as missing primary market data with an explicit exclusion reason.

This rule is frozen before inspecting weather-vs-market model results.

---

## 17. Numerical Scoring Convention

For probabilistic evaluation, multiclass log loss uses a fixed numerical
probability floor:

    epsilon = 1e-6

For scoring only:

    p_scored = clip(p, epsilon, 1 - epsilon)

followed by renormalization to sum to one.

The same convention must be applied to every probabilistic model.

The analysis must separately report whether the realized winning bucket
received an exact zero probability before clipping.

This clipping convention is for numerical scoring only and must never be
applied to executable market prices or economic PnL.
