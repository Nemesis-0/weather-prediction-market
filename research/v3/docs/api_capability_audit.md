# V3 IBKR Prediction-Market API / Data Capability Audit

> **Historical-status note (2026-10-08):** This document governed the
> infrastructure audit before strategy work. The required read-only
> ForecastEx / IBKR capability path was later established and reused by V3.
> Weather foreground research is now retired; see
> [`weather_alpha_domain_closure_20261008.md`](weather_alpha_domain_closure_20261008.md).

## Status

**ACTIVE — infrastructure-only, pre-strategy audit**

This audit must be completed before the first V3 strategy architecture is
frozen and before prospective strategy PnL is inspected.

## Purpose

Establish exactly what prediction-market data, contract metadata, timing
information, and execution plumbing are actually available through the chosen
IBKR interface(s).

The output is a capability map, not a trading result.

This phase must not:

- train a trading model;
- inspect prospective strategy PnL;
- optimize entry thresholds;
- search timing windows for profitability;
- infer alpha from paper fills;
- buy market-data subscriptions without a defined missing capability;
- store credentials or account identifiers in tracked artifacts.

## Audit metadata

Record without sensitive identifiers:

- audit date / software version;
- operating environment;
- Python version;
- IBKR interface under test (for example Client Portal Web API, TWS API, or
  another officially supported interface);
- paper or live environment;
- market-data subscription state;
- local timezone and clock-synchronization method;
- whether tests are snapshot, polling, or streaming.

Do not record account numbers, usernames, authentication tokens, cookies,
personal identity data, tax data, or bank information.

## A. Authentication / session capability

- [ ] Selected API interface is documented
- [ ] Authentication flow is documented
- [ ] Whether authentication can be automated is documented
- [ ] Session lifetime / timeout behavior is measured
- [ ] Keepalive / heartbeat requirements are documented
- [ ] Reauthentication requirements are documented
- [ ] Paper and live session behavior are compared where relevant
- [ ] Credentials / tokens remain outside Git

## B. Contract discovery

- [ ] ForecastEx weather contracts can be discovered programmatically
- [ ] Accessible venues and product families are recorded
- [ ] Underlying / event / contract identifiers are mapped
- [ ] YES/NO identifiers are mapped correctly
- [ ] Thresholds are parsed without manual transcription
- [ ] Threshold ordering is reconstructible
- [ ] Event date / expiry / last-trade metadata are captured
- [ ] Market status is captured
- [ ] Discovery can be rerun without silently duplicating contracts

For each capability, retain source evidence: endpoint / field name, observed
response example with sensitive fields removed, and test date.

## C. Contract rules / settlement metadata

- [ ] Contract rules can be retrieved or linked programmatically
- [ ] Settlement source agency is captured where exposed
- [ ] Settlement station / location is captured where applicable
- [ ] Threshold semantics (`>`, `>=`, range, rounding, units) are captured
- [ ] Timezone is captured
- [ ] Last trading time is captured
- [ ] Resolution / payout timing is captured
- [ ] Revision / fallback procedures are captured
- [ ] Rule URL / rule version or content hash is retained
- [ ] Rule changes can be detected over time

No cross-contract or cross-venue comparison is allowed until settlement
semantics are normalized.

## D. Top-of-book market data

For each field, record whether it is available, its exact API field name,
update behavior, units, missing-value behavior, and paper/live differences.

- [ ] Bid price
- [ ] Ask price
- [ ] Bid size
- [ ] Ask size
- [ ] Last price
- [ ] Last size if available
- [ ] Volume if available
- [ ] Open interest if available
- [ ] Market-data availability status
- [ ] Real-time vs delayed vs frozen vs not-subscribed state

A midpoint alone is insufficient for V3 executable-alpha research.

## E. Depth / order-book capability

Audit separately from top-of-book:

- [ ] Depth endpoint / stream exists
- [ ] Number of depth levels is documented
- [ ] Price and size are available at each level
- [ ] Update semantics are documented
- [ ] Snapshot vs incremental update behavior is documented
- [ ] Paper/live differences are documented
- [ ] Any subscription requirement is documented

If depth is unavailable, the limitation must be explicit in the future
execution model.

## F. Timestamp semantics

For every time field, document what the provider says it means and what is
actually observed.

- [ ] Broker/API update timestamp identified
- [ ] Exchange timestamp identified only if genuinely exposed
- [ ] Local wall-clock receive timestamp recorded
- [ ] Local monotonic receive timestamp recorded
- [ ] Timestamp unit / timezone / resolution documented
- [ ] Local clock synchronization method documented
- [ ] Duplicate timestamps characterized
- [ ] Out-of-order timestamps characterized
- [ ] Quote-update frequency measured
- [ ] Polling / batching delay measured where relevant

**Never relabel a broker/API update time as an exchange timestamp without source
support.**

## G. Streaming / polling reliability

Run a continuous observation test long enough to expose normal session behavior.

- [ ] Connection start / stop recorded
- [ ] Authentication state observable
- [ ] Heartbeat / keepalive behavior tested
- [ ] Reconnect behavior tested
- [ ] Reconnect count recorded
- [ ] Gap start / gap end detectable
- [ ] Last-message age measurable
- [ ] Duplicate events detectable
- [ ] Out-of-order events detectable
- [ ] Unexpected schema / field changes detectable
- [ ] Collector-health events can be logged separately from quote events

The future collector must not turn reconnects or feed gaps into apparent price
jumps without flagging the integrity break.

## H. Rate limits / throttling

- [ ] Documented request / subscription limits recorded
- [ ] Observed throttling behavior tested conservatively
- [ ] Error codes / retry behavior documented
- [ ] Backoff policy documented
- [ ] Maximum practical concurrent contract coverage estimated
- [ ] Discovery, rules, historical, and market-data limits separated

Do not intentionally stress or evade provider limits.

## I. Historical data capability

Historical data are for infrastructure understanding and later diagnostics, not
for optimizing V3 strategy specifications on the closed V1/V2 sample.

- [ ] Historical endpoint tested
- [ ] Supported bar / tick granularity documented
- [ ] Maximum lookback / points per request documented
- [ ] Bid/ask vs trade-only availability documented
- [ ] Size availability documented
- [ ] Timestamp semantics documented
- [ ] Request limits documented
- [ ] Historical data differences from live streaming documented

## J. Paper vs live capability

- [ ] Contract discovery compared
- [ ] Rule / metadata access compared
- [ ] Market-data availability compared
- [ ] Data-delay status compared
- [ ] Order-entry plumbing tested in paper
- [ ] Cancel / replace plumbing tested in paper if relevant
- [ ] Paper fill behavior explicitly excluded as evidence of live execution
- [ ] Any live-only field or permission requirement documented

## K. Market-data subscription audit

Start with current access.

For every missing capability, document:

1. what field / quality is missing;
2. whether the missing item blocks a defined V3 requirement;
3. the subscription that would resolve it, if known;
4. whether the subscription adds real-time data, depth, or another specific
   capability.

- [ ] Free/current capability exhausted first
- [ ] Missing fields documented before purchase
- [ ] No subscription purchased merely "just in case"

## L. Execution-plumbing capability

This remains an engineering audit, not a live strategy test.

- [ ] Order types supported for the relevant event contracts documented
- [ ] ForecastEx YES/NO mechanics documented correctly
- [ ] Opposing-position / netting behavior documented
- [ ] Quantity / price increment rules documented
- [ ] Fee schedule source captured
- [ ] Order acknowledgement fields documented
- [ ] Fill / partial-fill fields documented in paper
- [ ] Cancel / replace behavior documented in paper
- [ ] No live order is required for completion of the capability audit

## M. Required deliverables

The audit must produce four artifacts with all sensitive fields removed:

1. **Machine-readable capability report**
   - one row / object per capability;
   - status such as `SUPPORTED`, `UNSUPPORTED`, `REQUIRES_SUBSCRIPTION`,
     `PAPER_ONLY`, `UNKNOWN`;
   - API interface / endpoint / field;
   - paper/live environment;
   - timestamp semantics where relevant;
   - evidence note;
   - audit date.

2. **Human-readable audit summary**
   - what works;
   - what does not;
   - what remains unknown;
   - what is safe to build next.

3. **Unresolved limitation list**
   - especially timing, depth, settlement, subscription, and paper/live gaps.

4. **Collector viability verdict**
   - whether a prospective collector can defensibly capture the minimum V3
     information state.

## N. Minimum gate before collector-schema freeze

Do not freeze the first prospective collector schema until the audit has
resolved, at minimum:

- programmatic contract discovery;
- contract / settlement mapping;
- executable BBO availability;
- available size or an explicit documented size limitation;
- real-time / delayed status;
- timestamp semantics;
- local receive-time capture;
- session / reconnect behavior;
- feed-gap observability;
- paper/live differences relevant to data capture.

If one of these is unavailable, the limitation must be carried explicitly into
the V3 architecture rather than silently assumed away.
