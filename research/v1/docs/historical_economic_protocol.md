# Historical Economic Evaluation Protocol

Freeze date: 2026-09-30

This protocol is frozen after predictive historical-holdout results were
summarized, but before any trade-level or PnL evaluation was performed.

Therefore the economic historical holdout is not fully blind with respect
to aggregate predictive results. Trade selection and realized PnL had not
been inspected before this protocol was frozen.

## 1. Models

Primary economic comparison:

    M2 = Market + Weather
    versus
    fitted M0 = Market-only

Only out-of-sample probabilities are eligible:

- rolling-origin development predictions for the 17 validation dates;
- frozen-model predictions for the 15 historical-holdout dates.

The first 14 development dates are excluded from economic evaluation
because they do not have rolling out-of-sample predictions.

## 2. Execution Price

Primary historical execution proxy:

    synchronized primary 10:00 AM market snapshot

Buy YES price:

    yes_ask

Buy NO price:

    1 - yes_bid

No midpoint is treated as executable.

Historical displayed quotes do not prove actual fill or quoted size.
This evaluation is therefore a one-contract quote-based tradeability
test, not proof of realized execution capacity.

## 3. Position and Action Set

For each city-day and each model, evaluate twelve possible actions:

- buy YES on each of six buckets;
- buy NO on each of six buckets.

At most ONE contract may be purchased per city-day.

The action with the highest model-implied after-fee expected value is
selected.

If the highest after-fee expected value is <= 0:

    NO TRADE

No position sizing, leverage, scaling, martingale, or simultaneous
multi-bucket portfolio is permitted.

## 4. Fee Treatment

Primary historical analysis uses the general Kalshi taker-fee schedule
effective during the sample:

    fee = round_up_to_cent(
        0.07 * C * P * (1 - P)
    )

with:

    C = 1 contract

and default multiplier:

    M = 1

No settlement fee is applied.

## 5. Model-Implied Net Expected Value

For a YES action:

    q = model probability of the bucket
    P = executable YES ask

For a NO action:

    q = 1 - model probability of the bucket
    P = executable NO ask

For one contract held to settlement:

    estimated_net_EV = q - P - fee

Trade only when:

    estimated_net_EV > 0

No additional edge threshold is tuned in historical V1.

## 6. Realized PnL

The selected contract is held to settlement.

If the selected action resolves true:

    realized_PnL = 1 - P - fee

otherwise:

    realized_PnL = -P - fee

No early exit is simulated.

## 7. Primary Economic Comparison

For every city-day, define:

    delta_PnL = PnL_M2 - PnL_M0

No-trade has PnL = 0.

Primary uncertainty uses calendar-date-preserving 3-day moving-block
bootstrap.

All three cities on a date remain together.

Pre-specified block sensitivities:

    1 day
    7 days

## 8. Required Diagnostics

Report separately for M0 and M2:

- trade count
- no-trade count
- total PnL
- mean PnL per city-day
- mean PnL per executed trade
- win rate
- mean model-estimated edge
- maximum gain
- maximum loss
- city-level PnL
- concentration of profits

Report M2 - M0 paired PnL uncertainty.

## 9. Interpretation

Positive historical PnL is not sufficient evidence of stable alpha.

Historical quote data do not prove fills or scalable capacity.

Before prospective testing, later analyses must test:

- execution delay;
- adverse price/slippage;
- PnL concentration;
- liquidity/capacity;
- model uncertainty.

No economic result may be used to retune the frozen predictive V1 model.
