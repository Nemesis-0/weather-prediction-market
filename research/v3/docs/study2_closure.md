# V3 Study 2 — Closure Memo

Status: **CLOSED — CURRENT M0 ECONOMIC ROUTE KILLED**

Closure date: 2026-10-07 (America/Chicago)

Canonical pre-closure HEAD:

`88d4f9d12917e9ae358e9761921d613ec4e48cb8`

## Scope

This closure applies to **V3 Study 2: KMDW settlement-aware intraday nowcasting,
current observation-only M0 economic route**.

It does **not** claim that:
- weather prediction markets are globally unprofitable;
- all future settlement-aware models are invalid;
- V3 as an umbrella project is closed;
- V1/V2 or V3 Study 1 should be reopened.

## Gate #3 outcome

The first admissible post-fix ready-window economic screen produced:
- 440 total quote rows;
- 143 valid supported economic rows;
- 78 apparent positive conservative-margin rows;
- 65 supported nonpositive rows;
- 77 model-data-insufficient rows;
- 220 invalid executable-quote rows.

The largest apparent candidate was:
- threshold: 78°F;
- side: NO;
- executable ask: $0.02;
- displayed ask size: 7,250;
- q_hat(YES): 0.17565383665709344;
- q_U(YES): 0.30017895003004147;
- conservative NO probability: 0.6998210499699585;
- reported margin: $0.6598210499699585 per contract.

Sol Max Gate #3 returned **NO-GO**.

The decisive blocker was not quote mapping, arithmetic, or the frozen cost formula.
The blocker was an omitted point-in-time settlement-source state:
before the largest candidate quote, the same-day KMDW WU Daily Observations page
had already displayed 79°F observations. For a contract whose YES event is
final daily maximum > 78°F, the current M0 still assigned a low YES probability
because it did not condition on the already-observed WU settlement-source state.

Therefore the large apparent NO edge was not credible executable alpha.

## Diagnostic settlement-state overlay

A diagnostic-only overlay was applied to the already-screened Gate #3 session.

Rule:
if the already-known WU daily maximum was greater than a contract threshold,
the current M0 candidate was treated as settlement-state contaminated and blocked
from interpretation as usable economic evidence.

Results:
- original positive rows: 78;
- blocked known-crossed-threshold rows: 76;
- remaining positive rows: 2.

Breakdown of blocked rows:
- NO 75°F: 19 rows; max reported margin 0.031601696673230234;
- NO 76°F: 19 rows; max reported margin 0.2157636266633805;
- NO 77°F: 19 rows; max reported margin 0.45883466818685525;
- NO 78°F: 19 rows; max reported margin 0.6598210499699585.

Remaining rows:
- YES 79°F: 2 rows;
- largest remaining reported margin:
  $0.001623866150736085 per contract.

This overlay is diagnostic only. It does not retroactively create a new valid
economic protocol or validate the remaining two rows.

## Closure decision

The current M0 route is closed because:
1. Gate #3 returned NO-GO on the first apparent positive executable candidate;
2. 76/78 apparent positive rows (97.4%) were explained by one settlement-state
   misspecification;
3. the maximum surviving diagnostic margin was only about $0.001624/contract and
   lacked independent prospective confirmation;
4. repairing, revalidating, and modeling settlement-source revision risk is not
   justified by the remaining economic signal under the project's current
   alpha-search objective.

No further M0 retuning, calibration repair, support widening, settlement-guard v2
development, or fresh Study 2 economic screening is authorized under this closed route.

## Scientific interpretation

The failure is specific and informative:

An ASOS-only residual model can be predictively reasonable while still being
insufficient for settlement-aware trading if it omits point-in-time information
from the settlement source itself.

Future alpha work should test deterministic settlement-state and contract-semantic
constraints before investing in probabilistic modeling.

## Preserved reusable infrastructure

The following remain reusable for future V3 work:
- ForecastEx / IBKR read-only market-data collection;
- direct YES/NO executable quote mapping;
- KMDW point-in-time weather collection;
- WU snapshot / settlement-source archival;
- provenance and raw-evidence handling;
- fee / reserve accounting;
- support / calibration infrastructure;
- Gate-based adversarial audit workflow.

## Frozen outcome

**FINAL STUDY 2 CURRENT-ROUTE STATUS: CLOSED / ECONOMIC KILL**

No real orders were authorized or submitted by this study.
