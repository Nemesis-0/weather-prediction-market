# V2 Market-Reaction Event-Study Protocol

Freeze date: 2026-09-30

V1 is permanently closed.

V2 weather and market-alignment feasibility gates have passed.

This stage tests whether Kalshi market probabilities react in the
direction implied by newly published NBM/NBS forecast information.

No settlement outcome, prediction accuracy, trading rule, or PnL may be
used in this stage.

---

## 1. Analysis population

Primary population:

    weather-changing revision events
    with clean PRE and POST +1H market states

as defined by the frozen V2 market-alignment feasibility protocol.

Current feasibility count:

    196 events
    across 45 calendar dates

No event may be included or excluded based on the direction or magnitude
of subsequent market movement.

---

## 2. Weather-information representation

For each revision event construct:

    q_old
    q_new

the six-bucket weather-proxy probability vectors using the same Gaussian
TXN/XND-to-bucket transformation previously specified in V1.

The Gaussian representation remains only a compact feature
transformation. It is not interpreted as the true TWC settlement
distribution.

Define:

    delta_q = q_new - q_old

No model fitting is involved in constructing delta_q.

For this event-study stage, no log transform or epsilon clipping is
required unless mechanically required by the existing frozen probability
construction.

---

## 3. Market representation

At both PRE and POST +1H use synchronized six-bucket quote midpoints.

For each market state:

    raw midpoint_j = (YES bid_j + YES ask_j) / 2

Normalize jointly across the six mutually exclusive buckets:

    p_j = midpoint_j / sum(midpoint)

Define:

    delta_p = p_post1h - p_pre

Midpoints are used only to study probability movement.

They are not treated as executable trade prices.

---

## 4. Primary market-reaction estimand

The primary estimand is the aggregate projection coefficient:

                 sum_i sum_j delta_q_ij * delta_p_ij
    beta = ------------------------------------------------
                 sum_i sum_j delta_q_ij^2

where:

- i indexes clean weather-changing information events;
- j indexes the six temperature buckets.

Interpretation:

    beta > 0

means that, on average, market probability moved in the same direction
as the newly published weather information.

beta = 0 corresponds to no average directional assimilation under this
representation.

The magnitude of beta is descriptive and must not be interpreted as a
structural percentage of forecast information incorporated.

---

## 5. Dependence and uncertainty

Calendar date is the primary dependence unit.

All:

- cities,
- revision transitions,
- bucket components

from the same calendar date remain together during resampling.

Primary uncertainty:

    3-day moving-block bootstrap over calendar dates

Sensitivity:

    1-day blocks
    7-day blocks

Report a two-sided 95% confidence interval.

No bucket-level naive standard errors are permitted.

---

## 6. Secondary descriptive analyses

Prespecified secondary outputs:

- fraction of events with
      dot(delta_q, delta_p) > 0;

- POST +2H reaction coefficient using the already frozen clean +2H
  population;

- descriptive coefficients by city;

- descriptive coefficients by revision transition:
      prev18Z -> 00Z
      00Z -> 06Z
      06Z -> 12Z

These subgroup results are descriptive only.

No city or transition may replace the primary pooled analysis based on
performance.

---

## 7. Unchanged-weather controls

Forecast-state transitions with:

    delta_TXN = 0
    and
    delta_XND = 0

are not part of the primary directional-reaction test because delta_q is
zero.

They may be retained as descriptive controls for background market
movement.

Their performance cannot be used to redefine the primary population.

---

## 8. Interpretation

A positive market-reaction result establishes only that Kalshi prices
respond directionally to public forecast updates.

It does NOT establish:

- incomplete assimilation;
- predictable residual movement;
- economic value;
- tradeability;
- alpha.

Only after H2.1 is evaluated may a separate frozen study test whether
information remains after the initial market response.

---

## 9. Prohibited behavior

Do not:

- inspect settlement outcomes;
- calculate PnL;
- choose a different reaction window after seeing results;
- choose cities based on reaction strength;
- choose transitions based on reaction strength;
- change the weather-proxy transformation based on reaction results;
- use POST market movement to redefine which revisions count as signals.

