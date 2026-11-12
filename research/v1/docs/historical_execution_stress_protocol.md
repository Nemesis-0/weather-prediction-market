# Historical Execution Stress Protocol

Freeze date: 2026-09-30

This protocol is frozen after the primary quote-based historical economic
evaluation and before inspecting any adverse-execution or delayed-execution
results.

The predictive models, trade-selection rule, and selected actions are not
retuned for these stress tests.

## 1. Baseline

Baseline is the previously frozen historical economic evaluation:

- decision time: 10:00 AM local
- executable YES price: YES ask
- executable NO price: 1 - YES bid
- one contract maximum per city-day
- one selected action maximum per city-day
- general Kalshi taker fee
- hold to settlement

## 2. Decision-Preserving Adverse Execution

For every trade selected under the baseline rule, keep the selected:

- city-day
- bucket
- YES/NO side

unchanged.

Stress the executable purchase price by:

    +$0.01

and separately:

    +$0.02

capped at $1.00.

Recalculate the taker fee using the stressed entry price.

Do NOT re-optimize the action or convert a stressed trade into a no-trade.

This tests robustness of the originally selected strategy to modest
execution deterioration.

## 3. One-Hour Execution Delay

Keep the action selected using information and prices available at the
10:00 AM local decision time.

For an originally selected trade, simulate execution at:

    11:00 AM local

using the same contract and same YES/NO side.

YES execution price:

    11:00 AM YES ask

NO execution price:

    1 - 11:00 AM YES bid

The fee is recalculated using the delayed executable price.

The model probability is NOT updated.

The action is NOT re-selected using the later quote.

If the required 11:00 quote is unavailable, the observation is marked
missing for the delay analysis rather than imputed.

## 4. Profit Concentration

For each model and segment, report:

- total PnL
- positive PnL
- largest winning trade share of positive PnL
- top-three winning trades share of positive PnL
- best calendar-date PnL
- worst calendar-date PnL

A strategy whose historical profitability depends strongly on a small
number of observations must be treated as fragile.

## 5. Primary Comparison

For every execution scenario, compare:

    M2 PnL - M0 PnL

at the city-day level.

Primary uncertainty:

    3-day moving-block bootstrap

Sensitivity:

    1-day blocks
    7-day blocks

The three cities from a calendar date remain together.

## 6. Interpretation

These are historical robustness tests.

They do not prove that displayed historical quotes were fillable and do
not establish live trading capacity.

No result from this analysis may be used to retune V1.
