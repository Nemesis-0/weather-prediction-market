# V3 Study 1 — Shakedown Amendment (2026-10-05)

Status: **pre-freeze amendment; confirmatory evaluation had not started**.

## 1. Original plan

The original Study 1 pre-freeze charter targeted three full unattended
strategy-blind shakedown sessions on distinct dates.

That number was a design budget for collector feasibility, not a statistical
endpoint and not a scientific hypothesis test.

## 2. Amendment

The long-run shakedown is ended after **two clean four-hour unattended sessions
on distinct dates**, one weekend and one weekday.

No third full session is required unless a specific plumbing defect is later
identified before final freeze.

This amendment was made before confirmatory evaluation and before any
prospective basket-cost, opportunity-frequency, alpha, or PnL inspection.

## 3. Permitted evidence used for the amendment

Only strategy-blind operational evidence was used:

| Metric | Day 1 — 2026-10-04 | Day 2 — 2026-10-05 |
|---|---:|---:|
| Rotation | 0 | 1 |
| Requested duration | 14,400 s | 14,400 s |
| Completed / expected cycles | 480 / 480 | 480 / 480 |
| Selected markets | 11 | 11 |
| Selected contracts | 88 | 88 |
| Quote records | 42,240 | 42,240 |
| Missing contract responses | 0 | 0 |
| HTTP errors | 0 | 0 |
| Tickle failures | 0 | 0 |
| Auth failures | 0 | 0 |
| Detected cadence gaps | 0 | 0 |
| Real-time delivery records | 42,240 | 42,240 |
| Rule-audit market coverage | 11 / 11 | 11 / 11 |
| Schedule-audit market coverage | 11 / 11 | 11 / 11 |
| Schedule-audit errors | 0 | 0 |
| Max cycle elapsed | 3.976 s | 13.314 s |
| Provisional cadence | 30 s | 30 s |

Complete BBO+size availability differed between the two sessions
(5,924 versus 12,870 records). That difference is retained only as an
operational data-availability observation. It was **not** used to select
favorable cities, thresholds, dates, windows, or strategy rules.

## 4. Why stopping is defensible

The two sessions answer the shakedown's main engineering question: the current
collector can run unattended for four hours while preserving scheduled cycles,
real-time delivery status, authentication health, complete contract responses,
explicit missingness, rule/schedule metadata, and gap detection.

A third four-hour run would add another operational observation but is not
required to establish the already-demonstrated long-run collector behavior.

The project therefore advances to protocol reconciliation and pre-registration
freeze review rather than extending shakedown by default.

## 5. What this amendment does not establish

This amendment does **not** establish:

- cross-threshold settlement equivalence;
- executable structural opportunity frequency;
- fillability of two legs;
- after-cost alpha;
- profitability;
- adequacy of any final session window;
- validity of any final fee/slippage model.

Those items remain governed by the operational-freeze candidate and the
subsequent adversarial pre-registration review.
