# V3 Study 2 — Support / calibration freeze before economics

Protocol:
`v3_study2_support_calibration_frozen_2026-10-07_r1`

This stage follows the frozen one-shot 2026 M0 historical validation.

It does **not** retune M0. Its sole purpose is to define, before examining
economic margins, where future probabilities are supported and how a
conservative interval `[q_L, q_U]` is constructed.

## Probability semantics

For ForecastEx threshold `theta`:

`q_hat = P(M_D^WU > theta | weather information at t)`.

The strict `>` inequality is frozen.

Given `[q_L, q_U]`:
- YES conservative probability = `q_L`;
- NO conservative probability = `1 - q_U`.

`1 - q_L` is forbidden for NO.

## Conservative calibration envelope

The frozen 2026 validation is converted into a threshold-agnostic calibration
diagnostic using fixed pseudo-contract residual cutoffs:

`delta = theta - running_max_f`

on the integer grid `-10°F, -9°F, ..., +20°F`.

For each available validation state and delta:
- compute frozen M0 `q_hat = P(R > delta)`;
- observe `Y = 1[R_actual > delta]`.

Only `q_hat` between 0.05 and 0.95 is considered supportable.

Cells are fixed as:
- Chicago-local six-hour time block;
- 0.05-wide q_hat bin.

Within each cell, each date receives equal total weight. The observed-minus-
predicted calibration gap is bootstrapped at the event-date cluster level
(2,000 reps; seed family based on 20261007).

A cell is supportable only with at least 100 independent validation dates.

For a supported future candidate:
`slack = max(abs(CI_low), abs(CI_high))`

where the CI is the frozen 95% cluster-bootstrap interval for the calibration
gap in its cell.

Then:
- `q_L = max(0, q_hat - slack)`
- `q_U = min(1, q_hat + slack)`.

This is a conservative post-validation risk envelope. It is not a claim that
the envelope itself has been independently validated; that question is
prospective.

## Weather-state support

State support is frozen from **2024+2025 only**, not from market prices.

A future candidate must:
- have a valid weather state;
- have latest-observation age <= 90 minutes;
- fall in a month x six-hour local-time support cell containing at least
  45 independent 2024+2025 dates;
- have running max, temperature-vs-running-max, observation age, and nonmissing
  ~60-minute temperature change inside the frozen 1st-99th percentile ranges
  of that month x time-block cell;
- if the trend is missing, that exact month x block must have at least
  45 independent historical dates with trend missing;
- have `delta = theta - running_max_f` in [-10°F, +20°F];
- have frozen M0 q_hat in [0.05, 0.95];
- map to a calibration cell passing the >=100 independent-date rule.

Otherwise:
`MODEL_DATA_INSUFFICIENT`.

No tail extrapolation is allowed merely because an executable ask looks cheap.

## Market-selection risk

Historical weather data identify weather-only probability, not necessarily

`P(Y | weather, selected because ask looked cheap)`.

Therefore market-selection risk remains:

`UNRESOLVED_PROSPECTIVE_ONLY`.

Consequences:
- an economic screen may immediately produce `ECONOMIC_KILL`;
- a positive conservative weather-only margin does **not yet** authorize an
  `EXECUTABLE_CANDIDATE`;
- a positive state remains `MODEL_DATA_INSUFFICIENT` with respect to
  market-selection conditioning until independent prospective shadow evidence
  exists.

This prevents "cheap ask" selection from silently changing the conditioning
regime.

## Next stage

After this policy is reviewed and frozen, implement the fast executable-price
economic kill test using:
- fresh executable ask;
- verified fee;
- pre-frozen execution reserve;
- funding/carry reserve if justified.

Do not use midpoint.

No orders are authorized.
