# V3 Study 1 — Operational Freeze Candidate

Status: **historical pre-freeze candidate; superseded by `study1_final_frozen_protocol.md` on 2026-10-06**.

Confirmatory evaluation has **not started**.

## 1. Scientific question

For nested daily-high temperature thresholds with identical settlement
definitions except threshold, does a conservative two-leg basket ever appear
repeatedly at executable displayed asks below its ordinary-settlement payout
floor after frozen costs and revalidation?

For lower threshold event `E_a` and higher threshold event `E_b` with
`E_b ⊂ E_a`, the candidate basket is:

- buy lower-threshold **YES**;
- buy higher-threshold **NO**.

Under ordinary settlement, this basket has a payout floor of $1 if the nesting,
YES/NO complement structure, and settlement definitions are all correct.

This study tests structural consistency. It does not use NOAA/NBM as a signal.

## 2. Pre-result provenance

The scientific family was selected before prospective V3 strategy-result
inspection.

The long-run shakedown used strategy-blind operational metrics only. No basket
cost, opportunity frequency, alpha, or PnL was inspected or used to tune this
candidate.

V1/V2 remain closed and are not used to optimize this protocol.

## 3. Candidate scientific universe

The candidate confirmatory universe is the **current-day daily-high**
ForecastEx market for:

- New York City;
- Chicago;
- Denver.

This three-city universe comes from the prior architecture decision, not from
which shakedown markets displayed more favorable BBO availability.

A broker `expiration` label must **not** be treated as the scientific event
date. The event date must be established from settlement/question metadata and
must correspond to the daily-high event being evaluated.

## 4. Mandatory semantic eligibility

No threshold pair is eligible unless, for that event date and market, the
project verifies and archives:

- identical settlement source/station/site;
- identical observation window and time-zone treatment;
- identical temperature units and rounding;
- identical payout and price increment;
- identical trading cutoff / release / payout timing where applicable;
- identical cancellation/refund/fallback provisions;
- valid YES/NO complement structure at each threshold;
- strict threshold ordering and the intended nested-event relation;
- a rule/source version or archival hash sufficient to reproduce the check.

The current shakedown fail-fast guardrail proves one complete same-strike
YES/NO rule pair per selected market. That is useful operational evidence but
is **not sufficient by itself** to prove cross-threshold equivalence.

The final evaluation implementation must therefore perform an explicit
cross-threshold semantic check before any pair can qualify.

## 5. Market-data eligibility

A candidate observation must use only point-in-time records received by the
collector.

Required for each leg at each qualifying observation:

- displayed ask present;
- displayed ask size present and at least one contract;
- delivery status recorded as real-time;
- request-send and response-receive timestamps present;
- no forward-fill from a prior poll;
- no unresolved session/feed gap covering the observation.

Displayed asks are evidence of quoted availability, not proof of simultaneous
two-leg fills.

## 6. Polling cadence

**Candidate cadence: 30 seconds.**

Operational basis:

- 960 scheduled cycles across two four-hour sessions;
- 960/960 cycles completed;
- zero detected cadence gaps;
- zero HTTP/tickle/auth failures;
- zero missing contract responses;
- maximum observed cycle elapsed 13.314 seconds, below the 30-second cadence.

The cadence may be changed only before final freeze for a documented
operational reason, not because it changes opportunity counts.

## 7. Session window

The prior architecture review proposed **09:00–17:00 America/New_York**.

This remains the candidate scientific window because it was proposed before
strategy-result inspection. However, the shakedown directly validated two
four-hour windows rather than one uninterrupted eight-hour window.

The pre-registration adversarial review must explicitly decide whether:

1. the existing operational evidence is sufficient to retain 09:00–17:00 ET; or
2. a narrower fixed window is required on operational grounds.

No choice may be based on observed or hypothetical opportunity frequency.

## 8. Candidate signal and revalidation rule

Consider adjacent listed thresholds only.

At poll `t`, a candidate pair requires:

- lower-threshold YES ask and size >= 1;
- higher-threshold NO ask and size >= 1;
- complete semantic eligibility under Section 4.

Revisit the **same pair** one polling interval later.

Both observations must independently satisfy quote completeness and size
requirements. Revalidation establishes survival at two observed polls; it does
not prove continuous availability between them.

## 9. Candidate conservative acquisition cost

For each leg, use the **higher displayed ask across the two qualifying
observations**.

Candidate basket cost includes:

- those two conservative leg asks;
- verified account/venue fees;
- one minimum tick per leg as a slippage reserve;
- any funding-through-settlement treatment required by the venue/account.

The candidate qualification rule is:

`conservative acquisition cost <= $0.99`

against the ordinary-settlement $1 payout floor.

Fees must be verified immediately before final freeze and must not be counted
twice. Displayed quotes are not labeled executed fills.

## 10. Candidate selection rule

- maximum one qualifying basket per city-date;
- use the first qualifying revalidated basket;
- simultaneous ties: lower threshold first, then deterministic contract ID;
- no hindsight selection of a later or more favorable basket.

## 11. Primary endpoint

Primary estimand:

**the proportion of planned untouched evaluation dates on which the frozen
collector detects at least one qualifying, revalidated structural basket.**

The unit of primary evidence is the **date**, not the quote tick and not the
number of overlapping threshold pairs.

Candidate evaluation budget: **30 new scheduled dates after final freeze**.

All scheduled dates, aborted dates, feed failures, and missing observations must
remain visible in the audit trail.

## 12. Gap and failure treatment

- Never forward-fill an incomplete quote.
- A missed/invalid observation cannot create a qualifying basket.
- A gap does not prove that no underlying opportunity existed during the gap.
- A scheduled date with material feed/session failure must remain disclosed.
- Abort/retry rules must be frozen before confirmatory collection begins.

The pre-registration review must finalize the exact threshold for a
"material" session failure and whether such a date remains in the primary
denominator.

## 13. Inference and dependence

Aggregate evidence at the date level.

Repeated 30-second quotes and overlapping threshold pairs are not treated as
independent observations.

Candidate inference plan:

- primary date-level summary;
- three-day moving-block bootstrap;
- seven-day block-length sensitivity.

If zero qualifying dates occur, do not report a mechanically degenerate
bootstrap interval as if it were informative.

## 14. Kill criteria

Close Study 1 rather than rescue it if:

- cross-threshold settlement semantics cannot be verified;
- live/stale/incomplete feed status cannot be handled reliably;
- fewer than five distinct qualifying opportunity dates occur in the 30-date
  evaluation;
- apparent edge disappears under the frozen cost treatment;
- later micro-live validation cannot control rejects/cancellations/single-leg
  exposure or does not support positive net expected value.

No post-result city, threshold, cadence, session-window, or cost-buffer rescue.

## 15. Required adversarial pre-registration decisions

Before final freeze, the reviewer must specifically attack and resolve:

1. whether the two-session shakedown amendment is methodologically acceptable;
2. whether 30-second polling is adequately justified;
3. whether 09:00–17:00 ET is operationally supportable or must be narrowed;
4. the exact cross-threshold semantic-normalization rule;
5. event-date mapping versus broker expiration labels;
6. the exact fee/slippage/funding treatment;
7. stale/asynchronous-leg risk under two-poll revalidation;
8. gap/abort/denominator handling;
9. date-level dependence and bootstrap choices;
10. any remaining degree of freedom that could enable post-result rescue.

Only after those items are resolved, encoded in code/tests, and frozen may the
30-date untouched evaluation begin.
