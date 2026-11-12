# V1 Final Closure Record

Final closure date: 2026-09-30

## Final status

**CLOSED — completed negative study**

Independent adversarial Checkpoint 1b judgment:

**A — V1 can now be closed.**

V1 must not be retuned, rescued, extended, or reopened in response to its
results.

---

## Study question

V1 tested whether static public NBM/NBS TXN/XND information provided
incremental predictive and economic value beyond the 10:00 AM local
Kalshi daily-high-temperature market state.

Cities:

- NYC
- Chicago
- Denver

TWC-regime historical sample:

- 46 calendar dates
- 138 city-days
- 828 bucket contracts

Primary decision time:

- 10:00 AM local

---

## Point-in-time correction

A source-backed NOAA publication-timing census discovered four genuine
weather-data availability violations in the original V1 implementation.

The affected observations were corrected mechanically using the latest
source-verified NBM/NBS forecast actually public before the originally
frozen 10:00 AM local decision time:

- NYC 2026-08-31:
  12Z -> 06Z

- NYC 2026-09-24:
  12Z -> previous-day 18Z

- Chicago 2026-09-24:
  12Z -> 00Z

- Denver 2026-09-24:
  12Z -> 06Z

No research specification was changed.

The following remained frozen:

- cities
- stations
- 10AM decision time
- market snapshots
- weather-proxy construction
- model family
- lambda grid
- rolling-origin selection algorithm
- scoring
- trade-selection rule
- fee treatment
- execution-stress rules

The original pre-correction state is preserved at:

    archive/v1_pre_source_timing_correction

Those pre-correction downstream results are superseded.

---

## Final point-in-time integrity

After correction:

- city-days checked: 138
- corrected weather rows: 4
- remaining weather availability violations: 0
- future market-snapshot violations: 0
- market snapshots older than frozen 60-minute limit: 0
- six-bucket structural failures: 0

---

## Corrected development result

The original pre-specified lambda-selection procedure was rerun because
one corrected observation belonged to the development period.

Selected lambdas remained:

- M0: 0.01
- M1: 1
- M2: 0.001

Rolling-development economic results:

- M0 PnL: +$2.26
- M2 PnL: -$2.63

No post-correction model retuning was performed.

---

## Corrected historical predictive evaluation

The 15-date period is called:

**corrected historical evaluation**

It is NOT an untouched holdout.

Results:

- M0 log loss: 1.0115
- M1 log loss: 1.5413
- M2 log loss: 1.0259
- raw normalized-market log loss: 0.9752

Primary M2 minus M0 mean calendar-date log-loss delta:

    +0.0144

Negative would favor M2.

Primary 3-day moving-block bootstrap 95% CI:

    [-0.0376, +0.0863]

M2 therefore did not show reliable incremental predictive value over M0.

The corrected M2 Brier result was slightly favorable relative to M0, but
its uncertainty also crossed zero and did not overturn the primary
log-loss result.

---

## Corrected historical economic evaluation

Baseline:

- M0 total PnL: +$0.42
- M2 total PnL: +$0.48
- M2 minus M0: +$0.06 total
- M2 minus M0 mean city-day PnL: +$0.0013

Primary 3-day moving-block bootstrap 95% CI:

    [-$0.0487, +$0.0280]

The point estimate is economically tiny and statistically uncertain.

---

## Execution robustness

Corrected historical evaluation:

### Baseline

- M0: +$0.42
- M2: +$0.48

### +1 cent adverse execution

- M0: approximately $0.00
- M2: +$0.05

### +2 cents adverse execution

- M0: -$0.42
- M2: -$0.37

### One-hour delayed execution

- M0: +$0.62
- M2: +$0.84

All M2-minus-M0 execution-scenario confidence intervals included zero.

Neither the positive M0 nor M2 baseline historical PnL constitutes
evidence of reliable tradeable alpha.

---

## Final V1 interpretation

**Under the corrected point-in-time-valid frozen V1 specification, static
NBM TXN/XND proxy information did not show reliable incremental predictive
or economic value beyond the 10AM Kalshi market in this 46-date sample.**

This conclusion is deliberately narrow.

V1 does NOT establish that weather information is generally useless.

V1 does NOT establish that NBM revisions cannot contain useful
information.

V1 does NOT establish realized fills.

V1 does NOT establish scalable alpha.

V1 does NOT establish live profitability.

The small positive Market-only historical PnL is friction-sensitive and
is not evidence of alpha.

The corrected positive M2 historical PnL is likewise too small and
uncertain to establish economic edge.

---

## Historical terminology

The original 15-date period must not be called an untouched holdout.

Correct terminology:

    corrected historical evaluation

Any legacy `historical_holdout` labels remaining in computational source
artifacts are implementation-era identifiers only.

Canonical final-report copies use corrected terminology.

---

## V1 research status

V1 is permanently closed.

Any subsequent work must be explicitly labeled as a new hypothesis and
new study version rather than an extension or rescue of V1.
