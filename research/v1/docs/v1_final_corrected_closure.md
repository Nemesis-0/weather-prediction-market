# V1 Final Corrected Closure

Closure date: 2026-09-30

## Status

V1 is complete subject to final independent post-correction review.

A source-backed NOAA publication-timing audit discovered four city-days
where the originally selected 12Z NBS forecast had not yet been publicly
available at the frozen 10:00 AM local decision time.

The affected weather inputs were mechanically replaced with the latest
source-verified eligible forecast available at the original decision time.

No city, station, market snapshot, decision time, model family,
regularization grid, scoring rule, trade-selection rule, fee rule, or
execution-stress rule was changed.

## Corrected weather observations

- NYC 2026-08-31: 12Z -> 06Z
- NYC 2026-09-24: 12Z -> previous-day 18Z
- Chicago 2026-09-24: 12Z -> 00Z
- Denver 2026-09-24: 12Z -> 06Z

The original contaminated state remains archived under:

    archive/v1_pre_source_timing_correction

## Final point-in-time integrity

- City-days: 138
- Corrected weather city-days: 4
- Weather available-after-decision violations after correction: 0
- Future market-snapshot violations: 0
- Market staleness > 60 minutes: 0
- Six-bucket structural failures: 0

## Corrected predictive evidence

Rolling-development lambda selection remained:

- M0: lambda = 0.01
- M1: lambda = 1
- M2: lambda = 0.001

Corrected 15-date historical evaluation:

- M0 log loss: 1.0115
- M1 log loss: 1.5413
- M2 log loss: 1.0259
- Raw normalized-market log loss: 0.9752

Primary M2 minus M0 mean calendar-date log-loss delta:

    +0.0144

Negative would favor M2.

Primary 3-day moving-block bootstrap 95% CI:

    [-0.0376, +0.0863]

Corrected M2 Brier score was slightly better than M0, but the primary
log-loss comparison did not show reliable incremental predictive value.

## Corrected historical economics

Rolling development:

- M0 total PnL: +$2.26
- M2 total PnL: -$2.63

Corrected 15-date historical evaluation:

- M0 total PnL: +$0.42
- M2 total PnL: +$0.48
- M2 minus M0 total difference: +$0.06
- mean city-day difference: +$0.0013

Primary 3-day moving-block bootstrap 95% CI for mean city-day PnL
difference:

    [-$0.0487, +$0.0280]

## Execution robustness

Corrected historical evaluation:

Baseline:
- M0: +$0.42
- M2: +$0.48

+1 cent adverse execution:
- M0: approximately $0.00
- M2: +$0.05

+2 cents adverse execution:
- M0: -$0.42
- M2: -$0.37

One-hour delayed execution:
- M0: +$0.62
- M2: +$0.84

All M2-minus-M0 execution-scenario confidence intervals included zero.

The small corrected M2 historical profit therefore does not establish a
reliable or robust incremental economic edge.

## Interpretation

The original pre-correction historical evaluation is superseded.

Because the previously opened 15-date historical period was subsequently
corrected, it is no longer described as an untouched holdout.

The final V1 interpretation is:

**Under the corrected point-in-time-valid frozen V1 specification, static
NBM TXN/XND proxy information did not show reliable incremental predictive
or economic value beyond the 10AM Kalshi market in this 46-date sample.**

The small positive historical Market-only PnL is not evidence of alpha:
it is eliminated by +1 cent adverse execution and becomes negative at
+2 cents.

The corrected M2 historical baseline PnL is also too small and uncertain
to establish tradeable alpha and becomes negative under +2 cents adverse
execution.

V1 does not establish realized fill, scalability, or live profitability.

No V2 result has been inspected.
