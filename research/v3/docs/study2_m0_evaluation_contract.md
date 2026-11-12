# V3 Study 2 — Frozen one-shot M0 historical validation contract

Evaluation protocol:
`v3_study2_m0_historical_validation_frozen_2026-10-07_r1`

This contract is fixed before opening 2026 historical-validation feature/target
values with the frozen M0.

## Preconditions

- Gate #2 = GO.
- M0 implementation/protocol is committed and pushed.
- 2024 fit and 2025 calibration artifacts exist from the pre-evaluation run.
- Pre-evaluation summary records zero 2026 feature values used and zero 2026
  target values used.
- Evaluator code must itself be committed and pushed before execution.
- Tracked worktree must be clean and `HEAD == origin/main`.

## Evaluation lock

Before any numeric 2026 feature or target is parsed, the evaluator writes
`evaluation_lock.json` containing:
- canonical HEAD;
- SHA256 of the frozen model JSON;
- SHA256 of the 2025 calibration ECDF;
- SHA256 of the pre-evaluation summary;
- SHA256 of the model-ready state CSV;
- frozen metric family;
- frozen date-cluster bootstrap seed and repetition count.

The evaluation output directory is fail-closed and cannot pre-exist.

## Population

Historical validation:
2026-01-01 through 2026-10-06.

Expected:
- 279 dates;
- 13,390 total 30-minute grid states;
- 526 unavailable states excluded by the already-frozen state-availability
  rule;
- 12,864 available states evaluated.

No additional support filter is introduced at this stage.

## Frozen predictive distribution

The evaluator loads the already-frozen M0:
`R|x = mu(x) + sigma(x) * Z`.

There is no fit, recalibration, hyperparameter search, feature selection, or
model comparison during validation.

## Primary metric

**Date-balanced mean CRPS** of the complete predictive residual distribution.

For each date, intraday states receive equal within-date weight; every date
receives equal total weight.

A 95% percentile interval is computed using a 2,000-replicate event-date
cluster bootstrap with fixed seed `20261007`.

## Frozen secondary metrics

Overall:
- date-balanced absolute error of predictive median;
- 50%, 80%, 90% central interval empirical coverage;
- average width of those intervals;
- weighted PIT mean and variance;
- weighted PIT KS distance from Uniform(0,1);
- date-balanced PIT probability mass in ten decile bins.

The same descriptive metric family is computed separately for four
pre-specified Chicago-local time blocks:
- 00:00–05:59;
- 06:00–11:59;
- 12:00–17:59;
- 18:00–23:59.

Date-cluster bootstrap intervals are produced for CRPS, median MAE, interval
coverage, and interval width.

## Interpretation boundary

This is a one-shot frozen historical validation.

Whatever the result:
- do not retune M0 in response to 2026;
- do not change features, ridge penalties, calibration construction, split, or
  grid based on validation performance;
- do not substitute a more complex model to rescue a weak result.

The next step is interpretation plus support/calibration review. Economic value
is a separate question and remains unauthorized until that review is complete.

## Carried limitations

The Gate #2 caveats remain:
- historical METAR issue time is only an availability proxy;
- COR publication timing is not proven point-in-time;
- historical WU settlement-time page vintage is not reconstructed;
- `temp_change_60m_f` is an as-of difference, not an exact one-hour rate;
- repeated states within a date are dependent;
- validation ends 2026-10-06.
