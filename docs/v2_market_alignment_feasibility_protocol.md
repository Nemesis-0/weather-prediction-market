# V2 Market-Alignment Feasibility Protocol

Freeze date: 2026-09-30

This stage evaluates only whether historical Kalshi market states can be
aligned to source-verified NBM/NBS information-arrival events.

No settlement outcome, predictive performance, market-response direction,
or PnL may be inspected.

## 1. Information event

For every sequential V2 weather revision pair, the information-event time
is:

    new NOAA publication timestamp

Nominal NBM cycle time is not used as event time.

## 2. PRE market state

PRE is the latest complete synchronized six-bucket hourly market snapshot:

    strictly before the new forecast publication time

Requirements:

- all six bucket contracts present;
- synchronized timestamp;
- bid/ask/midpoint/spread available;
- no future candle;
- PRE staleness <= 60 minutes;
- PRE timestamp must be at or after publication of the old forecast state.

The final requirement ensures the PRE state can reasonably represent a
market that had access to the old forecast before the new information
arrived.

## 3. POST +1H market state

Define target:

    new forecast publication + 60 minutes

POST +1H is the first complete synchronized six-bucket snapshot ending at
or after this target.

Maximum lateness relative to the target:

    60 minutes

To isolate the current weather revision, POST +1H must occur strictly
before publication of the next same-target NBS forecast state, if one
exists.

If another same-target forecast arrives before the selected POST snapshot,
the event is marked overlapping and is not a clean +1H event.

## 4. POST +2H market state

Defined analogously using:

    new forecast publication + 120 minutes

with maximum 60-minute snapshot lateness.

POST +2H is secondary feasibility only.

It must also precede the next same-target forecast publication when such a
forecast exists.

## 5. Weather-change status

All 414 revision events are aligned mechanically.

For the eventual weather-reaction hypothesis, the primary informative
subset consists of events where:

    TXN changed OR XND changed

Unchanged revisions remain available as possible controls and are not
deleted from the feasibility dataset.

## 6. Primary Gate D

Gate D is evaluated using clean changed-information events with both PRE
and POST +1H available.

PASS requires all of:

- at least 90 clean changed events;
- at least 30 distinct calendar dates;
- all three cities represented with at least 20 clean changed events each;
- each of the three revision-transition classes represented by at least
  15 clean changed events.

These thresholds are frozen before alignment results are inspected.

They are structural feasibility thresholds, not statistical-significance
or profitability thresholds.

## 7. Restrictions

Do not:

- inspect settlement outcomes;
- calculate forecast accuracy;
- calculate direction of market response;
- calculate PnL;
- select reaction windows based on observed market behavior;
- discard dates based on whether the market later moved favorably.

