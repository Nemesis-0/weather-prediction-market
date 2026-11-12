# Historical Holdout Freeze

Freeze date: 2026-09-30

This freeze was created after completion of development rolling-origin
model selection and before any Weather-only or Market+Weather evaluation
on the historical holdout.

## Development results used for selection

Development dates:

    2026-08-14 through 2026-09-13

Rolling validation:

    17 calendar dates
    51 city-days

Selected regularization:

    M0 Market-only:       lambda = 0.01
    M1 Weather-only:      lambda = 1.0
    M2 Market + Weather:  lambda = 0.001

These values are frozen.

The M2 value lies at the lowest boundary of the pre-specified lambda
grid. The grid will NOT be expanded after observing development results.

## Historical holdout

Dates:

    2026-09-14 through 2026-09-28

Size:

    15 calendar dates
    45 city-days

All three cities remain grouped by calendar date.

No model family, feature transformation, regularization value, station,
decision time, city set, or scoring rule may be changed based on
historical-holdout performance.

## Primary comparison

    M2 Market + Weather
    versus
    fitted M0 Market-only

Primary metric:

    paired calendar-date multiclass log-loss difference

    delta = M2 log loss - M0 log loss

Negative delta favors M2.

Secondary metric:

    paired multiclass Brier-score difference

M1 Weather-only and raw normalized market probabilities are descriptive
scientific baselines.

## Interpretation

This historical holdout is not the final prospective test.

A favorable result may justify further prospective evaluation but does
not establish stable predictive or economic alpha.
