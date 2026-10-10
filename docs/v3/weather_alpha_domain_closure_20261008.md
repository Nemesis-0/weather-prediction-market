# Weather Prediction-Market Alpha Domain Closure

Closure date: **2026-10-08**

Final foreground status: **RETIRED / PASSIVE-WATCH ONLY**

Positive executable-alpha claim: **NONE**

## 1. Scope of this closure

This memo closes the current **foreground weather prediction-market alpha-search
program** after V1, V2, V3 Study 1/2, and the V3 structural alpha funnel.

The closure is an allocation decision, not a universal market-efficiency claim.
It does **not** assert that:

- weather prediction markets can never contain alpha;
- every future settlement, lifecycle, microstructure, or cross-venue mechanism
  is impossible;
- the observed negative results generalize to every venue, city, data source,
  latency regime, or future product design.

The narrower conclusion is:

> **No currently surviving weather mechanism has enough positive executable
> evidence to justify further foreground research allocation under this
> project's profitability-first objective.**

Residual mechanisms may remain passive watchers, but they no longer receive
fixed-window research time without new trigger evidence.

## 2. Research progression

### V1 - static public weather information

Question:

> Does public NOAA/NBM TXN/XND information add predictive or economic value
> beyond the 10:00 AM local Kalshi weather-market state?

Final status: **CLOSED**.

After a source-backed point-in-time audit corrected four weather observations
that were not actually public by the frozen decision time, the corrected frozen
V1 design did not establish reliable incremental predictive or economic value.

Primary corrected predictive comparison:

- M2 minus M0 mean calendar-date log-loss delta: `+0.0144`;
- 3-day moving-block bootstrap 95% CI: `[-0.0376, +0.0863]`.

The corrected historical economic difference was economically tiny and
uncertain.

Canonical record:
[`../../results/final_v1/V1_FINAL_CLOSURE.md`](../../results/final_v1/V1_FINAL_CLOSURE.md).

### V2 - forecast revision / information assimilation

Question:

> Are public NBM forecast revisions followed by a reliable directional market
> reaction under the frozen historical event-study design?

Final status: **CLOSED**.

H2.1:

- `beta = +0.02957`;
- primary 3-day moving-block bootstrap 95% CI:
  `[-0.01225, +0.08462]`.

H2.2:

- `beta = -0.02814`;
- primary 3-day moving-block bootstrap 95% CI:
  `[-0.07276, +0.03360]`.

Neither stage established a reliable positive directional assimilation effect.
The negative H2.2 point estimate was not interpreted as a reversal effect.

Canonical record:
[`../../results/final_v2/V2_FINAL_CLOSURE.md`](../../results/final_v2/V2_FINAL_CLOSURE.md).

### V3 Study 1 - structural cross-threshold consistency

Study 1 developed a prospective protocol for executable consistency across
nested ForecastEx daily-high-temperature thresholds.

Strategy-blind shakedown, remediation, acceptance, and final pre-D0 freezing
were completed. Confirmatory collection **never started**. The frozen state is
preserved by tag:

`v3-study1-final-pre-d0-2026-10-06`

Final status: **DEFERRED PRE-D0 / NOT A CONFIRMATORY RESULT**.

Later high-throughput structural quick screens did not produce a promoted
static guaranteed-payoff candidate, but those screens are not retroactively
relabelled as the unrun Study 1 confirmatory experiment.

Canonical protocol:
[`study1_final_frozen_protocol.md`](study1_final_frozen_protocol.md).

### V3 Study 2 - settlement-aware intraday nowcasting

Study 2 tested whether point-in-time intraday weather state could support a
conservative probability edge over real executable ForecastEx asks.

Final status: **CLOSED / CURRENT M0 ECONOMIC ROUTE KILLED**.

The first admissible ready-window economic screen contained 78 apparent
positive rows. An adversarial settlement-state review found that 76 of those 78
rows were inconsistent with already-observed Weather Underground settlement-
source state. Only two diagnostic positive rows remained, both YES 79°F, with a
maximum reported remaining margin of approximately `$0.001624` per contract.

The model route was closed rather than retuned.

Canonical record:
[`study2_closure.md`](study2_closure.md).

### V3 alpha funnel - structural / timing triage

The final alpha funnel used synchronized executable quotes and explicit
semantic checks to kill weak mechanisms quickly.

Phase 1 produced **zero PROMOTE survivors** among completed deterministic /
guaranteed-payoff candidates. Tested candidates were either:

- KILL;
- SEMANTIC_KILL;
- SEMANTIC_INSUFFICIENT; or
- trigger-dependent passive watchers.

The direct ForecastEx YES/NO probe also established that paired top-of-book
quotes are mirrored rather than independent:

`Ask_Y + Bid_N = 1.00`

`Ask_N + Bid_Y = 1.00`

with corresponding observed size mirroring in the valid paired sample.

An overnight census found 67/67 valid realtime pairs mirror-consistent, while
all 67 were static over the 15-second diagnostic interval. That result was not
used to kill daytime microstructure; it was used only to avoid over-interpreting
an inactive overnight regime.

Canonical checkpoint:
[`alpha_funnel_phase2_checkpoint_20261008.md`](alpha_funnel_phase2_checkpoint_20261008.md).

## 3. Final alpha-family status

| Alpha family | Final status | Interpretation |
|---|---|---|
| Static weather forecasting | **CLOSED** | No reliable incremental predictive/economic value in the frozen V1 design. |
| Forecast-revision assimilation | **CLOSED** | No reliable directional assimilation effect in V2. |
| Settlement-aware observation-only model | **CLOSED / ECONOMIC KILL** | Apparent edge was dominated by omitted point-in-time settlement-source state. |
| Full Study 1 cross-threshold confirmatory program | **DEFERRED / NOT RUN** | Protocol preserved; no confirmatory result claimed. |
| Simple deterministic structural relations | **EXHAUSTED FOR FOREGROUND SEARCH** | No PROMOTE survivor from completed quick screens. |
| Persistent settlement-state lag | **NO POSITIVE EXECUTABLE EVIDENCE / RETIRED** | No basis for continued fixed-window research allocation. |
| Exact-crossing transient lag | **UNRESOLVED / PASSIVE WATCH** | Would require a clean trigger and ordinary-retail execution window; no foreground allocation. |
| Lifecycle / reopen behavior | **UNRESOLVED / PASSIVE WATCH** | Reopen only on a true lifecycle trigger. |
| Cross-venue weather structure | **UNRESOLVED / PASSIVE WATCH** | Requires payout-equivalent contracts and executable after-cost two-leg evidence. |

## 4. Methodological lessons retained from the project

### 4.1 Settlement-source state is part of the information set

A weather model can look statistically reasonable and still be economically
invalid if it assigns probability to an event that the contract's own
settlement source has already mechanically constrained.

Future weather-market work must condition on the point-in-time settlement-source
state before interpreting any model-derived probability edge.

### 4.2 Point-in-time availability must be demonstrated, not assumed

The V1 timing correction showed that nominal model-cycle timing is not enough.
The project must retain source-backed publication / receive timing whenever a
claim depends on what was knowable at a decision time.

### 4.3 Executability dominates cosmetic mispricing

A price discrepancy is not alpha unless the relevant side is actually buyable
or sellable under the venue's rules, with sufficient displayed size, realistic
fees, and a valid time ordering.

Midpoints, stale states, closed contracts, and non-buyable winners are not
substitutes for executable evidence.

### 4.4 YES/NO pairs are not independent order books

Observed ForecastEx YES/NO top-of-book prices and sizes map as complements.
Analyses must use the independent economic queues rather than double-counting
mirrored fields as separate liquidity.

### 4.5 Semantic auditing should precede complex modeling

Settlement source, station, comparator, threshold, trading cutoff, payout,
refund/cancellation rules, and contract relationships can invalidate an
apparent opportunity before statistical modeling begins.

### 4.6 Negative results should close routes

V1, V2, and Study 2 were not reopened to search for favorable thresholds,
cities, windows, or model changes after their primary evidence failed to clear
the relevant gate.

This discipline is treated as a research result, not as a failure to be hidden.

## 5. Foreground allocation decision

No additional fixed-window weather research is authorized under the current
program.

Weather becomes **PASSIVE-WATCH ONLY**. A future mechanism may be reconsidered
only if new prospective evidence materially changes the allocation case - for
example, a clean independently observed trigger with a conservative executable
after-cost margin that survives semantic and timing checks.

No such trigger is claimed by this closure.

## 6. Reusable infrastructure

The following components remain useful outside the closed weather foreground:

- public-source timing and archival tools;
- point-in-time market/weather state reconstruction;
- IBKR / ForecastEx read-only contract discovery and quote collection;
- executable YES/NO quote mapping;
- settlement-rule normalization and semantic guardrails;
- frozen cost / execution screens;
- integrity tests and fail-closed record validation;
- KILL / NO_TRIGGER / PROMOTE research-allocation logic.

These components can be reused in a future event-market domain without
reopening closed weather hypotheses.

## 7. Canonical final status

`WEATHER_FOREGROUND_RETIRED / PASSIVE_WATCH_ONLY`

No positive executable-alpha claim is made.

The final research contribution is the documented progression from predictive
signal testing to point-in-time assimilation, executable economics, settlement-
source auditing, structural constraints, and disciplined domain retirement.
