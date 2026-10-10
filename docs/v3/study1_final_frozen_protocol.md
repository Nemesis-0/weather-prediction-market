# V3 Study 1 — Final Frozen Confirmatory Protocol

Status: **FINAL FROZEN ON COMMIT; confirmatory collection has not started at the moment of this freeze document.**

Freeze parent: `b698f85`.

The strategy-blind live acceptance run `20261006T151123Z` passed with 160/160
planned adjacent-pair checks completed and zero structural failures. The final
Sol Max gate then identified three implementation defects. Those defects are
resolved before this freeze; see `study1_sol_max_final_gate_resolution_2026-10-06.md`.
No basket cost, opportunity count, alpha, hypothetical fill, or PnL was
inspected before this freeze.

## Scientific question

For nested ForecastEx daily-high temperature thresholds with settlement
semantics identical except threshold, does a conservative two-leg basket
repeatedly appear at displayed executable asks below the ordinary-settlement
payout floor after frozen fees, one-tick-per-leg reserve, funding reserve, and
one-poll revalidation?

For adjacent thresholds `a < b`, the basket is lower-threshold YES plus
higher-threshold NO. Under ordinary settlement and verified common semantics,
the nested-event construction has a $1 payout floor.

## Frozen universe and dates

Universe: NYC/KLGA (`UHLGA`), Chicago/KMDW (`UHMDW`), Denver/KBKF (`UHBKF`).

Primary planned dates are the 30 consecutive calendar dates **2026-10-07 through
2026-11-05 inclusive**. They are not replaced. An aborted, missing, or
integrity-failed planned date stays in the primary denominator with primary
value zero. More than three such dates closes the study for operational
reliability.

D0 = 2026-10-07 is valid only if the freeze is committed/tagged and the first
collector is ready before 09:00 America/New_York. A partial first session is not
allowed.

## Event-date and semantic eligibility

Scientific event date is parsed strictly from every listed contract question;
broker expiration is never a substitute. Every listed contract must be
explicitly classified as the target date or another date. An unparseable listed
contract is a study blocker and may not be silently dropped before adjacency is
constructed.

Every target-date threshold must have a mutually referenced YES/NO pair,
expected product/station, Fahrenheit daily-high exceed semantics, details payout
$1.00, rules payout $1.00, rules minimum price increment $0.01, Weather
Underground source, matching parsed threshold, and last-trade time at 23:59
local on the scientific event date. All normalized cross-threshold rule
fingerprints must be identical after removing threshold itself. Only adjacent
thresholds in that complete verified target-date ladder are evaluated.

The audited ForecastEx Daily Temperature Terms PDF is frozen in-repo at
`docs/v3/legal/DailyTemperatureTermsandConditions_2026-10-06.pdf`, SHA256
`226826cb5d64cddc52c86b99a2e908f25ba48aa431f6c9ffe2c30e55731db511`.
Each daily run must retrieve the contract terms URL and obtain the same hash.
A verified semantic or terms-version mismatch closes the study; it is not an
ordinary aborted date and cannot be treated as a zero opportunity.

## Frozen observation window

Session: **09:00:00–17:00:00 America/New_York**, end exclusive. Cadence:
**30 seconds**, 960 nominal slots per planned date. Each adjacent
lower-YES/higher-NO pair is requested together in one two-conid HTTP snapshot.
Both the pair request start and an eligible response must occur inside the
frozen session.

Hard structural checks are evaluated for both legs before ordinary quote
availability: exact response shape/conids, real-time delivery, valid broker
`_updated` millisecond epoch, future-time bound, and request latency. A missing
ask on one leg therefore cannot hide a delayed/frozen or timestamp-invalid other
leg.

A quote is buyable only for an ask in **$0.01–$0.99 inclusive** on a whole-cent
tick with integer ask size at least 1. Missing/non-numeric ask/size, zero/one-
dollar ask, or zero size is ordinary quote-unavailability and cannot create a
basket. Off-range, off-tick, malformed response, wrong conid, delayed/frozen
delivery, invalid epoch, over-latency, or session-boundary violation is a
structural failure. `_updated` age and cross-leg skew are diagnostics only.
No forward fill is allowed.

Each slot records the full expected pair count and observed pair-record count.
A `NORMAL` slot requires complete pair coverage and zero structural failures.
Any structural-invalid slot is globally excluded from revalidation even if
some pairs in that slot were individually quote-eligible.

## Two-poll confirmation

The same adjacent pair must be quote-eligible in two consecutive globally
NORMAL nominal slots with request-start separation 25–35 seconds. Any
intervening unavailable/invalid observation or invalid slot breaks pending
confirmation. This is quote re-observation, not proof of simultaneous fills.

## Frozen cost model

For each leg, use the higher displayed ask across the two qualifying
observations. Add two exchange fees at $0.01/contract, broker fee $0.00/contract
under the frozen direct-client schedule attestation, one $0.01 tick reserve per
leg, and a fixed 5% annual conservative funding stress through scheduled payout.
Round total cost upward to the next cent. Qualification requires frozen total
cost **<= $0.99**. These buffers are pre-result assumptions, not claimed upper
bounds on real execution loss or actual capital cost.

The user attested before freeze that the account was opened directly through
IBKR's website and is not known to be under an introducing broker/advisor.
Actual account fees are still re-verified before any later micro-live phase.

## Daily health and denominator

A date is `VALID` only with at least 951/960 NORMAL slots, no more than 9 total
structural-invalid slots, and no run of 3 structural-invalid slots. Quote-
unavailable pairs alone do not make a slot structurally invalid.

The daily collector is result-blind. It writes sealed pair observations, a
960-slot health ledger, semantic ladder archive, schedules, runtime terms hash,
run identity and hashes. It does not compute cost, opportunity, candidate
count, alpha, hypothetical fills, or PnL.

At endpoint, the evaluator must verify the frozen core-file manifest, per-day
run identity, sealed-input SHA256, complete slot ledger, pair coverage and
session timing before any opportunity evaluation. A corrupted/missing date is
labelled explicitly as an operational/integrity failure, retained in the
primary denominator as zero, and counted toward the operational kill rule.
A semantic/terms study blocker closes the study before the opportunity endpoint
is evaluated.

## Endpoint and inference

Primary estimand: proportion of **all 30 planned dates** with at least one
qualifying revalidated basket in any frozen city. City/pair/tick observations do
not increase the primary sample size.

A practical recurrence gate requires at least 5 qualifying planned dates.
Inference reports the date-level proportion and non-circular moving-block
bootstrap intervals with 3-day primary blocks and 7-day sensitivity blocks,
10,000 replicates, seed 20261006. These intervals are approximate small-sample,
short-range-dependence descriptions, not long-run profitability guarantees.
Degenerate all-zero/all-one samples do not manufacture a bootstrap confidence
interval.

The endpoint evaluator is locked until **2026-11-05 22:00 UTC = 17:00 ET**.

## Result firewall and no rescue

Before the endpoint unlock, do not inspect sealed pair observations, prices,
basket costs, margins, opportunity/candidate counts, daily primary values,
hypothetical fills, settlement-linked PnL, or subgroup strategy outcomes.
Operational health, authentication, missingness, schema/semantic errors,
latency, clock offset, ledger completeness, terms hashes and frozen file hashes
may be inspected.

No post-result change to city, threshold policy, cadence, window, cost buffer,
denominator, block length, endpoint, or date replacement is allowed to rescue
Study 1. A result that survives the recurrence gate only advances to a separate
shadow-execution validation; it does not establish executable or profitable
alpha.
