# V3 — Prospective Executable Weather Alpha: Research Charter

> **Current-status note (2026-10-08):** This charter records the governance
> of V3 while the program was active. Weather foreground research is now
> **RETIRED / PASSIVE-WATCH ONLY**. Present-tense statements below about the
> "current" Study 2 route are preserved as historical provenance. See
> [`weather_alpha_domain_closure_20261008.md`](weather_alpha_domain_closure_20261008.md)
> for canonical current status.

## 1. Objective

V3 is a **new prospective study**. Its final objective is not merely to predict
weather accurately or to show that a prediction market is inefficient.

The target is to identify a **repeatable positive edge at real executable
prices** after accounting for:

- exchange / platform fees;
- bid-ask spread;
- slippage and fill uncertainty;
- latency;
- liquidity and available size;
- model uncertainty;
- operational / data-integrity risk.

A profitable outcome is allowed to be the final goal, but the research process
must prioritize distinguishing **real alpha from fake alpha**. Specifications
must not be repeatedly changed after observing results merely to make PnL or
statistical evidence look positive.

## 2. Relationship to V1 and V2

V1 and V2 remain frozen historical studies.

### V1 baseline

Question: did simple static public NBM TXN/XND information show reliable
incremental predictive or economic value beyond the 10 AM Kalshi market?

Answer under the corrected frozen historical design: **no reliable evidence**.

### V2 baseline

Question: did NBM TXN/XND forecast revisions show a reliable first-window or
later-window directional market-assimilation pattern in hourly Kalshi data?

Answer under the frozen historical design: **no reliable evidence**.

V1/V2 therefore serve as baselines / negative controls. They are not abandoned,
but their closed 46-date historical sample must not be reused to optimize V3
entry thresholds, timing windows, cities, cycles, or trading rules.

V3 is worthwhile only if it adds genuinely new information or execution
structure, such as:

- finer timing;
- richer weather-state information;
- station nowcasting;
- executable prices and size;
- market microstructure;
- structural contract inconsistencies;
- carefully normalized cross-venue relationships.

## 3. Current infrastructure state

The brokerage / regulatory / funding layer is operational:

- IBKR Individual / Pro account approved;
- Prediction Markets permission approved;
- No Borrow Margin;
- paper-trading environment available;
- ForecastEx weather contracts visible;
- small live balance available for later execution validation.

No account identifiers, bank information, tax identifiers, identity-document
information, authentication material, or exact residential addresses belong in
this repository.

The V3 API/data capability audit established a viable read-only prospective path:

- authenticated Client Portal Gateway access;
- programmatic ForecastEx contract discovery;
- contract details, rules, schedules, and YES/NO geometry;
- real-time HTTP top-of-book snapshots with bid/ask and displayed size when
  present;
- delivery-mode field `6509` retained and decoded;
- sanitized point-in-time request/response timing;
- unattended keepalive/auth-health monitoring.

WebSocket delivery and broker historical bars remain unproven or unreliable for
this use case, but neither is required for the first prospective study. HTTP
polling is therefore the current collection path.

## 4. Current phase: Study 2 pre-freeze feasibility

Study 1 selected **structural consistency across nested daily-high temperature
thresholds** and completed strategy-blind shakedown, remediation, acceptance,
and final pre-D0 freezing. Confirmatory collection never started.

Following the 2026-10-06 strategic review, Study 1 is **DEFERRED PRE-D0**.
Its frozen protocol, configuration, implementation, accepted provenance, and
former 2026-10-07 through 2026-11-05 schedule remain preserved as historical
records. They are not the current operating schedule. The exact pre-deferral
repository state is tagged `v3-study1-final-pre-d0-2026-10-06`.

The current primary route is **Study 2 — KMDW Settlement-Aware Intraday
Nowcasting**. Its status is **PRE-FREEZE FEASIBILITY / NOT LIVE-READY**.

Study 2 asks whether point-in-time KMDW weather state can support a sufficiently
credible probability for the exact ForecastEx settlement event that remains
above a real executable ask after fees and material execution/funding costs.

The current evidence state is `MODEL_DATA_INSUFFICIENT`: exact target/data
paths have promising feasibility evidence, but no Study 2 probability model,
conservative economic margin, or live-order justification has yet been
established. This state precedes implementation of the planned 48–72 hour
development sprint; it is not a negative sprint result.

No Study 2 confirmatory protocol, decision window, model, probability bound,
execution reserve, or trading rule is frozen at this stage.

## 5. Prospective collector principle

Once the API audit establishes a viable path, the next priority is the
**prospective collector**, not a complex trading model.

### Market side

At minimum, the future collector should be capable of recording fields such as:

- local receive timestamp;
- broker / venue timestamp when actually available, with exact semantics;
- venue;
- contract identifier / conid;
- product / event identifiers;
- event date;
- threshold / contract geometry;
- YES bid / ask and available size;
- NO bid / ask and available size when separately represented;
- last price where useful;
- volume / open interest where available;
- market-data availability status;
- market status;
- collector-health / reconnect / gap information.

A broker timestamp must not be relabeled as an exchange timestamp unless its
semantics actually support that claim.

### Weather side

**Study 1 does not use a weather forecast or nowcast as a signal.** Its first
scientific question is purely structural. For Study 1, the required non-market
information is settlement metadata and the final official settlement outcome,
not NOAA/NBM predictive features.

Future V3 families may add point-in-time weather information only under a new
frozen design. Any such collector should preserve source, publication /
availability time, local receive time, settlement station/site, event date, and
the exact information state available at decision time.

The governing principle remains:

> Save the true information state prospectively from now on rather than spending
> the project mining a closed historical sample.

## 6. Alpha-family status

V3 does not assume that the V1/V2 NBM-revision-lag mechanism is the source of
profit.

Study 1 developed family 6.1 through a frozen pre-D0 implementation state but
did not begin confirmatory collection. Family 6.1 is now deferred.

Family 6.2 is the current **Study 2 pre-freeze feasibility** route. This is a
strategic reprioritization made before Study 1 D0, not a post-null rescue
specification. Families 6.3 and 6.4 remain deferred.

Study 2 development may use broad continuous capture to characterize data,
support, and executable-price feasibility. Any later confirmatory design must
be frozen before its prospective outcomes are used as confirmation.

### 6.1 Structural / cross-threshold consistency

For ordered threshold contracts, the implied probabilities should satisfy the
contract geometry. Examples include monotonicity across thresholds and other
payoff identities implied by mutually related YES/NO contracts.

The scanner should distinguish:

- descriptive probability inconsistency;
- executable inconsistency;
- executable after-cost arbitrage / near-arbitrage.

Settlement definitions, threshold semantics, fees, synchronization, and
available size must all be correct before any arbitrage claim is made.

### 6.2 Late-day nowcasting / stale quotes

As the day progresses, settlement-consistent station observations and the
running daily maximum can sharply reduce uncertainty about the final Tmax.

The question is whether market uncertainty ever contracts more slowly than the
weather-information state, leaving an executable after-cost discrepancy.

This is conceptually distinct from simply following an NBM revision.

### 6.3 Sub-hour information assimilation

V2 did not establish a reliable hourly delayed-revision effect. V3 may later
test whether genuinely new public information is incorporated over seconds or
minutes rather than hours.

This family is not interpretable until timestamp semantics, receive latency,
stream reliability, and synchronization are audited.

### 6.4 Cross-venue consistency

ForecastEx / Kalshi / CME or other venues may be studied only after settlement
station, threshold definition, timing, payout, and rule differences are fully
normalized. Otherwise apparent arbitrage can be entirely fake.

## 7. Shadow execution engine

IBKR paper fills are useful for plumbing but are **not scientific evidence of
real executable alpha**.

The primary prospective execution test should use recorded real market data and
a transparent shadow engine. Each signal should eventually retain enough
information to reconstruct the decision, including:

- signal time;
- information available at signal time;
- model / fair probability if applicable;
- executable bid / ask;
- available size;
- exact fee treatment;
- slippage assumption;
- latency buffer;
- uncertainty buffer;
- TRADE / NO TRADE decision;
- position size;
- final settlement;
- realized hypothetical PnL.

A conceptual edge for a YES purchase is:

`expected_edge = fair_probability - executable_cost - execution_losses - uncertainty_buffer`

where executable cost and execution losses must be defined with the actual
contract / venue mechanics.

**NO TRADE is the default state.** A signal is not generated merely because the
model and market differ.

## 8. Paper, shadow, and live roles

### IBKR Paper

Use for:

- UI familiarization;
- order-entry testing;
- API and instrument-discovery testing;
- pipeline plumbing.

Do not use simulated fill quality as evidence of live executable alpha.

### Shadow engine

Use as the main scientific prospective execution test once the relevant rules
are frozen. It must use real recorded BBO / size / timestamps rather than
optimistic midpoint assumptions.

### Micro-live

Use only after the model / signal definition, cost assumptions, latency rules,
risk limits, and evaluation design are frozen and prospective evidence warrants
execution validation.

The initial purpose is to compare expected execution with real fills, fees,
latency, slippage, and PnL — not to maximize profit.

No leverage / borrowed funds should be used for V3 validation.

## 9. Adversarial review checkpoints

### Review A — architecture review before prospective strategy inspection

Completed after the API/data capability audit and before any V3 prospective
basket-cost, opportunity, alpha, or PnL inspection.

This review selected structural cross-threshold consistency as Study 1 and
required executable asks/sizes, conservative costs, explicit settlement
semantics, strategy-blind shakedown, and untouched prospective evaluation.

### Review B — narrow pre-registration audit before untouched evaluation

After shakedown and after the operational-freeze candidate is written, conduct
one narrow adversarial review before confirmatory evaluation begins.

Its purpose is to attack:

- settlement/event-date mapping;
- cross-threshold semantic equivalence;
- YES/NO complement structure;
- universe and session definitions;
- polling cadence and revalidation logic;
- stale/asynchronous-leg risk;
- fee/slippage/funding treatment;
- gap/abort/missed-date handling;
- date-level dependence and inference;
- degrees of freedom that could permit post-result rescue;
- fake execution claims.

This review may correct protocol defects **before** the final freeze. It may not
use prospective strategy results to optimize the protocol.

### Review C — kill audit only after apparent positive executable evidence

If the frozen prospective study later appears positive and real-money expansion
is being considered, conduct a separate audit designed to kill the result via:

- timestamp leakage;
- look-ahead bias;
- selection bias;
- fake fills;
- stale-quote artifacts;
- settlement mismatch;
- hidden fees;
- underestimated slippage;
- queue assumptions;
- event dependence;
- concentration;
- capacity;
- regime dependence;
- multiple testing;
- accidental cherry-picking.

## 10. Things V3 may defer

V3 does not need to begin with:

- large-scale historical ForecastEx backfills;
- months of historical tick downloads;
- many weather-model benchmarks;
- deep learning;
- large ML ensembles;
- a large robustness appendix;
- reconstruction of already-closed V1/V2 results;
- significant live capital;
- paid market data without a demonstrated need.

## 11. Things V3 cannot avoid if the goal is executable alpha

Eventually the project must have:

1. real executable bid / ask;
2. available size;
3. timestamps with documented semantics;
4. point-in-time weather information;
5. exact settlement rules;
6. an exact / venue-correct fee model;
7. explicit slippage / latency treatment;
8. prospective signal logging;
9. a NO-TRADE rule;
10. small real-money execution validation before any scaling claim.

## 12. Success criterion

Success is **not**:

- accurate weather prediction alone;
- positive paper PnL;
- a few large winning trades;
- statistical significance without execution realism.

The target is a positive edge that is:

**prospective + point-in-time valid + executable + after-cost + repeatable + controlled-risk**.

The intended progression is:

`API/Data Audit → Architecture Review → Strategy-Blind Collector/Shakedown → Pre-Registration Freeze Audit → Untouched Prospective Evaluation + Shadow Decisions → Micro-Live Validation if Warranted → Positive-Result Kill Audit → Only Then Consider Scaling`

Canonical principle:

> Profit can be the final objective, but the first priority is to distinguish
> real alpha from fake alpha as quickly and defensibly as possible.
