# V3 Study 2 — Frozen M0 protocol

Protocol ID: `v3_study2_m0_frozen_2026-10-07_r1`

Gate #2 authorized M0 inference under the frozen pre-model data contract.
This document freezes M0 **before any 2026 historical-validation target is
used**.

## Scientific object

The target at date `D` and intraday state `t` is

`R_D,t = M_D^WU - m_D,t^ASOS`.

Negative residuals are valid and are not truncated.

A single conditional residual distribution serves every eventual temperature
threshold. There are no threshold-specific models.

## M0 distribution

M0 is deliberately simple:

`R | x = mu(x) + sigma(x) * Z`.

- `mu(x)`: weighted linear ridge location model.
- `sigma(x)`: weighted linear ridge model for
  `log(abs(location residual) + 0.5°F)`, exponentiated with a 0.25°F floor.
- `Z`: date-balanced weighted empirical distribution of standardized 2025
  calibration residuals.

This is a single semi-parametric location-scale distribution, not an ensemble.

Both ridge penalties are fixed at `alpha = 10.0`; there is no tuning or model
selection.

## Inputs

Only accepted observation-state information is used:

- sine/cosine of Chicago local time;
- sine/cosine annual seasonal position;
- running observed maximum;
- current temperature relative to running maximum;
- age of latest observation;
- the frozen `temp_change_60m_f` as-of-state difference;
- a missing indicator for that change.

Missing `temp_change_60m_f` is filled with zero only in conjunction with its
missingness indicator.

No market price, contract threshold, ForecastEx quote, WU observation count,
future observation, or post-state weather value enters M0.

## Dependence and weighting

The independent unit is the calendar date, not the 30-minute state.

Every date receives equal total weight in:
- 2024 location/scale fitting;
- 2025 calibration ECDF;
- later validation summaries.

Within-date repeated states do not create additional independent-day weight.

## Frozen chronology

- Fit: 2024-01-01 through 2024-12-31 only.
- Calibration: 2025-01-01 through 2025-12-31 only.
- Historical validation: 2026-01-01 through 2026-10-06, untouched until the
  implementation and pre-evaluation artifacts are reviewed and frozen.

No hyperparameter or feature choice may be changed in response to 2026
performance.

## Pre-evaluation boundary

The pre-evaluation fit path skips `historical_validation` rows before numeric
feature/target parsing and records zero validation feature/target values used.

The only permissible outputs before the one-shot validation are:
- frozen coefficients and standardization constants;
- 2025 calibration standardized residual distribution;
- train/calibration-only numerical sanity diagnostics.

## Later one-shot validation metrics

Before opening 2026 outcomes, the following evaluation family is frozen:

Primary:
- date-balanced mean CRPS of the full conditional distribution.

Secondary:
- date-balanced absolute error of predictive median;
- 50%, 80%, and 90% central interval coverage and average width;
- weighted PIT/calibration summaries;
- the same descriptive metrics by pre-specified six-hour local-time blocks.

Inference/uncertainty must respect date clustering.

These metrics diagnose predictive adequacy. They do not establish executable
economic value.

## Accepted Gate #2 limitations carried forward

1. Historical IEM availability uses METAR `DDHHMMZ` issue time as a proxy.
   Original publication/receive latency is not reconstructed. COR reports do
   not prove corrected values were available at the original issue time.
2. Historical WU pages are current retrievals of past Daily Observations pages;
   equality to the original ForecastEx settlement-time page vintage is not
   established.
3. `temp_change_60m_f` is an as-of-state difference, not a strict exactly
   60-minute temperature-rate measurement.
4. Training has 366 independent date clusters despite many intraday states.
5. Historical validation ends on 2026-10-06.

These are limitations, not silently repaired data.

## Prohibited at this stage

- no LightGBM / neural network / ensemble;
- no threshold-specific model;
- no 2026 model tuning;
- no economic screening;
- no order lifecycle or live trading logic.

After the pre-evaluation fit is reviewed, freeze/commit the M0 implementation.
Only then run the single 2026 historical validation.
