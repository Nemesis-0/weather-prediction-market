# Historical Development and Holdout Protocol

Freeze date: 2026-09-30

## Purpose

This document freezes the chronological historical development structure
before inspecting Weather-only or Market+Weather predictive performance.

The historical holdout is not the final prospective test.

Its purpose is to reduce historical model-selection bias before the later
fully frozen prospective evaluation.

---

## 1. Calendar-Date Split

Development period:

    2026-08-14 through 2026-09-13 inclusive

- 31 calendar dates
- 93 city-days
- all three cities remain together on each date

Historical holdout:

    2026-09-14 through 2026-09-28 inclusive

- 15 calendar dates
- 45 city-days
- all three cities remain together on each date

No city-day may move between development and holdout based on model
performance, weather regime, liquidity, or PnL.

---

## 2. Scope of the Historical Holdout

The historical holdout must not be used to select:

- weather feature transformations
- model family
- regularization strength
- target-calibration method
- city inclusion
- decision time
- station choice
- trading threshold
- no-trade rule

Those choices must be made using development data only.

After the historical model specification is frozen, the holdout is
evaluated once.

---

## 3. Important Blinding Limitation

Before this split was frozen, aggregate Market-only descriptive
performance had already been computed across all 46 calendar dates.

Therefore the historical holdout is NOT fully blind with respect to
aggregate raw Market-only performance.

However, no Weather-only or Market+Weather predictive results had been
examined before this split was frozen.

The holdout is therefore treated as an untouched historical test for
weather-model development and incremental Market+Weather evaluation,
subject to this documented limitation.

---

## 4. Development-Period Model Selection

Within the development period, chronological rolling-origin evaluation
must be used.

Minimum initial training window:

    first 14 calendar dates

After the initial window, models are evaluated sequentially on the next
calendar date using only earlier dates for fitting.

All three cities belonging to a calendar date remain together.

Primary development selection metric:

    mean calendar-date multiclass log loss

Secondary development metric:

    multiclass Brier score

No random row-level cross-validation is permitted.

---

## 5. Model-Comparison Principle

Primary historical comparison:

    M2 = Market + Weather

versus

    fitted M0 = Market-only

M0 and M2 must use matched:

- training dates
- fitting procedure
- regularization framework
- scoring convention
- evaluation dates

The defining difference must be the addition of weather information.

M1 = Weather-only is retained as a scientific baseline but is not the
primary market-relative hypothesis test.

---

## 6. Historical Holdout Interpretation

The historical holdout can provide evidence that an effect survives
chronological model development.

It cannot establish stable profitability.

Any promising historical result must still survive a later fully frozen
prospective test before claims of persistent tradeable alpha are made.
