> **Review boundaries:** G0 closure does not authorize broker access, real order suggestions, V4-informed manual orders, live fees or supported alpha. A **separate read-only transport entrypoint security check** is required before G1 probing (allowlisted host/verb/path, certificate verification, no redirects/raw secrets). G1 validates completeness, duplicates, quote sync and session handoff. One ZIP may support G2 and G3, but they are separate verdicts.

# V4 — Solmax Independent Review Gates (DRAFT)

**Guiding rule:** this is a **second G0 bounded recheck candidate**, not a GO. A5 is **closed at design level** by Solmax revision-1 review; review only the five still-open A1, A2, A3, A4 and A6 acceptance-rule conflicts and adjacent regressions. A5 production crash/reconcile evidence remains at G2/G3. Bounded, evidence-driven adversarial review happens at material decision points, not every daily trade. The owner can run daily observation and manual execution under an already approved protocol; material code/model/scope/risk changes trigger a new bounded review.

| Gate | When | Solmax's main question | Required evidence | GO means / NOT means |
|---|---|---|---|---|
| **G0 — Research Design** | **Now, before V4 feature implementation** | Are objectives, data/label boundaries, event independence, model training and prospective evaluation logically coherent and separated from frozen V1–V3? | This protocol + architecture + prior closures + existing read-only API source | GO after the five remaining G0 conflicts close permits **pre-G1 read-only entrypoint security validation**, then bounded G1 read-only observation; **not** a real order |
| **G1 — Actual Gateway / Market Feasibility** | After read-only V4 capability scan | Which near-term contract families actually have valid fresh bids/asks/sizes, rules, last trade, released/final outcomes, source timing and fees? | Sanitized immutable API responses, field mapping/timestamp contract, market coverage (not merely alphabetic first five), session/gap/rate evidence; no private credentials | GO permits freezing *family selection, operational contract and data schema*, not profitable trade claims |
| **G2 — End-to-End Software & Journal Integrity** | After V4 implementation ZIP in branch, before an actionable human suggestion | Are immutable pre-order decisions, eligibility, no-order invariant, manual-fill journal, label reconciliation, replay and privacy correct under failures? | Exact Git commit/tree and ZIP SHA256, full source/diff, synthetic/redacted fixtures, independent test commands+outputs, crash injection, restore test, passing secret scan | GO permits preparing live pilot, subject to G3 |
| **G3 — First Manual Live Pilot Readiness** | Before owner submits first V4-informed real order | Are payout, real cost, order quantity, market-data status, limits, kill switches, user manual workflow, and the current prediction evidence adequate and properly disclosed? | Frozen policy/config/fee/rules, actual representative **read-only** quote/schedule evidence, full one-cycle prediction → record → suggested trade test (NO fake fill), human ledger procedure, owner-approved total and group budgets | GO authorizes the **bounded manual pilot protocol** only, not automatic orders or expected profit |
| **G4 — Settlement & Online Update Integrity** | When first venue-binding binary labels are observed+ingest-ready and the first lawful model checkpoint is created, **even with zero fills**; fill/cash reconciliation subreview after real fills exist | Does training include only already-final labels, preserve timestamp legality, dedup by event group, and keep champion/challenger comparisons prospective? | Actual sanitized append-only observational records, venue-binding final-source evidence with receipt+ready clocks, journal/SQLite identity hashes, checkpoint and training sample hashes, independent replay, scoring/missingness and bias checks; broker fill/cash evidence required once fills exist | GO permits ongoing update pipeline under frozen promotion policy; no alpha claim |
| **G5 — Formal Model Promotion / Expansion** | Before an important champion switch, additional family/venue, higher spend, or public alpha assertion | Does event-group prospective improvement survive dependence-aware tests, optional stopping, and economic execution scrutiny? | Prespecified checkpoint, sample/event-group counts, paired forecasts, score uncertainty, real fills/costs and sensitivity, drift and privacy review | GO permits precisely scoped release/expansion, **not** unbounded deployment |

## Required verdict syntax

`GO | CONDITIONAL GO | BLOCKED`, with:
1. Exact gate and frozen candidate Git/ZIP identity.
2. Scope inspected / scope excluded.
3. Independent executed tests and evidence sampled.
4. Findings ranked `BLOCKER | MATERIAL | MINOR`, each with concrete path/field/test and reproduction.
5. Precise permission for next step; no re-opening previously closed studies unless a genuine regression is introduced.

## Bounded remediation

- Address only findings from that gate; do not retune scientific thresholds based on positive/negative PnL discovered in protected data.
- Re-review affected files plus neighboring regressions; keep prior GO gates closed if unchanged.
- A `CONDITIONAL GO` is not a green light for orders when its conditions involve semantics, safety, timing or ledger integrity.
- Archive review prompt, verdict and evidence hash under `research/v4/docs/reviews/` on a future committed release, with no credentials or restricted raw market data.
- Not every daily model checkpoint needs Solmax: automated invariants run at every update. Solmax reviews changes to the updater/promotion rule and major promotions; runtime safety stops on failure.

## Recommended delivery cadence

1. **Now:** Send this second bounded G0 recheck pack resolving A1/A2/A3/A4/A6 conflicts to Solmax. A5 remains closed at design level. G0 remains open until a new reviewer verdict accepts the targeted clauses.
2. **Next (only after G0 recheck and separate pre-entrypoint transport audit):** One **read-only** Gateway capability probe with real current markets, followed by G1. The earlier V3 `--market-name-pattern '.' --max-markets 5` probe is only broad category discovery; it does not rank nearest live markets.
3. **Then:** One complete V4 initial implementation ZIP and branch verification; G2 and G3 are separate review decisions on a single implementation candidate, not necessarily separate ZIP upgrades.
4. **Daily operation:** Automatic repeated observations, forecasts and settlement polling; owner manually enters bounded live trades; daily candidate training; never automatic order placement or unreviewed release promotion.
5. **Once authoritative binding labels are observed+ready:** G4 validates legal update/checkpoint integrity **even with zero fills**; reconcile fill/cash evidence when fills later exist. G5 governs protected formal promotion/scale.

## Critical open questions (G0 should classify rather than guess)

- The one-primary-as-of, per-threshold/group/family weighting method and single terminal-look principle are now **specified**. G1 must freeze its numeric anchor, prospectively admitted family roster and horizon based on outcome-blind capability evidence.
- M0 formula is specified for verified binary mirrored books, but G1 must empirically validate contemporaneous quote leg timing, quality/mirror tolerances, subscription and status.
- G0 mandates no actionable trade without a defensible family-specific calibrated probability bound; estimator/sample minimum and reserve values require G1 evidence and G3 approval.
- G0 specifies provisional/partial/binding/void states and observed-before-update rule; G1 must establish real source/venue mapping and temporal evidence.
- G0 mandates atomic persistent manual-intent reservations and conservative reconciliation; G3 requires owner-approved numeric daily/concurrent/group budgets and broker handoff evidence.
- G0 mandates type-safe recursively validated allowlisted public projection and explicit score-vs-private-temporal replay; G1 verifies source/channel permissions and G2 tests leak resistance.
- Current contract universe and exact data fees/field reliability: cannot be answered from code alone.

## Explicit non-goals

No new V1/V2/V3 experiments, no inferred backtested fills, no paper trading, no automated order submission, no assertion that all live API endpoints work, no claims of alpha based on a few successful trades.
