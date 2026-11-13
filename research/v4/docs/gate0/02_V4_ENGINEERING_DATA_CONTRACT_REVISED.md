> **Design revision for G0 bounded recheck:** Six audit amendments are integrated into this data contract and specified in full in `07_G0_NORMATIVE_AMENDMENTS.md`. It remains a proposal, not a tested operational ledger or verified API implementation.

# V4 — Engineering Architecture & Data Contract (DRAFT, Gate 0)

**Status:** G0 BOUNDED RECHECK CANDIDATE, not code; API semantics and numeric risk limits require later gates. Initial implementation changes are scoped to `research/v4/` **plus** a prospective root `DATA_POLICY.md` amendment and narrowly required `.gitignore` entries; all root exceptions must be enumerated in the G2 diff. This review pack does not modify the published repo.

## A. Proposed repository layout

```text
research/
  v1/ v2/ v3/              # frozen; no scientific edits
  shared/                 # existing shared historical utilities
  v4/
    README.md
    docs/
      RESEARCH_PROTOCOL.md
      API_CAPABILITY_REPORT.md
      DATA_DICTIONARY.md
      OPERATIONAL_RUNBOOK.md
      REVIEW_GATES.md
    code/
      adapters/            # IBKR ForecastEx readonly; future venues separate
      discovery/           # broad inventory, lifecycle and normalized event identity
      semantics/           # rules, status, payout and source-state guards
      acquisition/         # authenticated read-only quotes, external availability
      features/            # family-specific point-in-time features
      models/              # market baseline; family models; calibration
      decision/            # candidate ranking, net value, risk + NO_TRADE
      journal/             # durable writes, typed record schema, redaction
      reconciliation/      # manually submitted order/fill/outcome / final labels
      learning/            # resolution-only updater and model registry
      reports/             # daily and weekly evidence report
      cli/                 # observe, suggest, record-fill, reconcile, update, report
    configs/
      observation_policy.yaml
      family_registry.yaml
      model_policy.yaml
      risk_limits.yaml
      source_requirements.yaml
    schemas/
      scan.schema.json
      observation.schema.json
      forecast.schema.json
      decision.schema.json
      execution.schema.json
      settlement.schema.json
      model_release.schema.json
    records/               # Git TRACKED, non-sensitive daily append-only exports
      scans/YYYY-MM-DD.jsonl
      forecasts/YYYY-MM-DD.jsonl
      decisions/YYYY-MM-DD.jsonl
      executions/YYYY-MM-DD.jsonl
      settlements/YYYY-MM-DD.jsonl
      model_registry.jsonl
      manifests/YYYY-MM-DD.json
    tests/
      fixtures/            # synthetic, redacted contract snapshots
      test_point_in_time.py
      test_settlement.py
      test_quotes.py
      test_yes_no_geometry.py
      test_event_grouping.py
      test_pretrade_persistence.py
      test_no_order_submission.py
      test_reconcile.py
      test_online_update.py
      test_privacy.py
      test_replay.py
local_artifacts/v4/         # NOT TRACKED; SQLite WAL, raw source payloads, snapshots
```

The root `DATA_POLICY.md` must be amended *once, prospectively* for new V4 records. Preserve V1–V3 frozen history. `records/` is a small audit/evidence export; it is not an invitation to commit complete account/order statements or a multi-million-row quote store. For V4, new code must not directly edit V3 closed research implementation; adapt its read-only `IBKRClient` behind an interface or copy tested V4-compatible helpers with provenance.

## B. Runtime separation and data flow

1. **Gateway readonly adapter:** authenticated IBKR session; `/forecast/category/tree`, `/forecast/contract/market`, `/forecast/contract/details`, `/forecast/contract/rules`, `/forecast/contract/schedules`, `/iserver/marketdata/snapshot`, plus authorized health calls. Verify endpoint availability in actual current Gateway. A multi-venue discovery abstraction must not promise ForecastEx endpoints will discover CME/Kalshi.
2. **Inventory & candidate selector:** caches long-lived product identity, obtains fresh contract chain and schedules, filters by *actual* last trade and known-state status. Discovery must not simply take first five markets sorted alphabetically (V3 test helper does this).
3. **Quoted-state capture:** fetch two sides together where supported, local UTC wall-clock and monotonic timestamps, broker update timestamp `_updated` retaining broker meaning, field `6509` parsed into delivery mode; live quote status and age are explicit. A stale/delayed/frozen/non-subscribed quote is not live executable evidence. Preserve request start/end times and timeout/gap state.
4. **Contract semantics normalization:** parse rule source, exact outcome geometry, unit, final source, release/payout/trade-stop, event group; cache source URL and content digest with history of revisions. Unknown -> HOLD.
5. **Feature builder:** per-family adapters return values, sources, *first observed/available* and valid timestamps, quality flags, schema version; no timeless joined table that can leak future values.
6. **Forecaster:** versioned market baseline and family model(s) run on exactly the same captured eligibility state. A pair of YES/NO contracts is modeled as one event target plus side mapping when mathematically valid.
7. **Decision engine:** separate predictive eligibility (unaffected by account fee/budget) from trade-readiness; record actual ask, authorized limit ceiling, worst-case fees and reserves, supported conservative probability, per-contract/event risk budgets, and reason-coded outcomes: `ELIGIBLE_NO_TRADE`, `HOLD_*`, `RECOMMENDED`, never silently discards rejected cases.
8. **Protected journal and manual intent:** before **actionable** suggestion, durably commit `forecast`, `decision`, unique manual intent and atomically reserved worst-case cash exposure within the same risk-check transaction; if evidence durability or DB commit fails, suppress suggestion. This is a research and UI workflow; **no order endpoints**.
9. **Manual execution reconciliation:** user inputs fill or cancel from IBKR; future read-only position/trade report import allowed only after explicit privacy boundary and API capability audit. Store order IDs/account mapping in a local private vault, not tracked Git; public sanitized refs can link corresponding decisions.
10. **Settlement and learning:** official outcome source and broker cash result (if actual trade) are reconciled separately. Only newly finalized outcomes enter training after temporal checks. Challenger version is immutable; promotion gate does not rewrite old predictions.

## C. Entity identity / relational keys

- `venue_id`: exchange name and rule context.
- `market_family_id`: stable family-specific forecasting mechanism, **not** a category display string; category tree labels may change.
- `outcome_event_id`: stable reference entity/series + measured variable + measurement period + canonical release instance, excluding venue/conid, strike, rule version, relisting and schedule changes. Aliases require verified mapping; ambiguous => HOLD. Never use resolution value in identity.
- `contract_target_id`: proposition/rule-version/strike/operator/rounding/payout identity, linked to the stable outcome; each substantive payoff revision is a different target. YES/NO conids belong to verified side instruments, not separate labels.
- `dependence_block_id`: cross-venue/cross-family connected release/window dependence used for split/bootstrap and embargo.
- `concentration_group_id`: economic co-exposure cluster stable across relists and threshold revisions; linked order/positions sum across aliases.
- `contract_key`: venue plus YES or NO conid and event geometry; no implicit assumption that conids are immutable across relisting.
- `scan_id`: ULID/UUID; captures search policy/version and total visible/eligible/skipped counts.
- `snapshot_id`: immutable market-data and feature evidence identity, actual receive time and quality; registered input anchor `T_g`, separately pinned issuance deadline `D_g`, and per-model actual issuance timestamps are stored for scoreable cases.
- `forecast_id`: unique append-only forecast; pinned model/version before result.
- `scan_item_disposition_id`: one typed row per discovered item, including skipped, not-forecastable, only-M0 and missing quote cases. A **paired scored** `ELIGIBLE_NO_TRADE` or `SUGGESTION_RESERVED` requires its on-time issued `forecast_id`; preforecast holds and M0-only/unissued-M2 states must not fabricate M2 or full forecast IDs. Whole-scan success, outages, model checkpoints and coverage gaps need a scope reference but may lack one event key.
- `decision_id`: reason-coded trade decision following a legally issued forecast where available, or preforecast disposition where unavailable. `forecast_id` is required for scored `ELIGIBLE_NO_TRADE`, `NO_TRADE_UNSUPPORTED` with issued prediction, `SUGGESTION_RESERVED` and any other decision whose justification uses a particular issued forecast; `NO_RULE`, `NO_CUTOFF_SNAPSHOT`, `MISSING_M0`, `MISSING_M2` (without fallback) or other preforecast/partial states can have no paired `forecast_id` and instead preserve their observed references and reasons. Missing fee/budget => trade-only hold with issued prediction retained in the scoring cohort.
- `manual_intent_id`: one-use idempotent human order handoff plus durable worst-case all-in reserved outlay, explicitly tied to outcome/target/side/quote/source/expiry; no local expiration auto-releases risk.
- `execution_ref`: random pseudonymous local ID, with private broker-order mapping separately stored.
- `resolution_id`: official outcome/version/correction state for one underlying event.
- `model_release_id`: source code Git commit, checkpoint digest, feature schema, training cutoff, allowed sample IDs, evaluation gate, status.

## D. Minimum durable record contract

Common envelope on **every record**:

```json
{
  "schema_version": "v4.draft.1",
  "record_id": "<uuid>",
  "record_type": "scan|scan_item_disposition|forecast|decision|model_update|...",
  "record_scope": "scan|scan_item|event|model|global_health",
  "scope_ref": "<typed nonempty scan_id/item_ref/event_id/model_release_id/health_id>",
  "created_at_utc": "<ISO8601 UTC>",
  "outcome_event_id": "<stable event ID when positively resolved; otherwise null>",
  "actor": "collector|model|human|reconciler",
  "previous_record_digest": "<optional chained SHA256>",
  "payload_digest": "<SHA256>",
  "source_trace_refs": ["<digest:local_archive_object>"],
  "privacy_class": "publishable|local_only"
}
```

**Record-scope schema rule (must be enforced now at design level; exact enumerations/types frozen at G1/G2):** `record_scope=event` requires a resolved `outcome_event_id` and `scope_ref=outcome_event_id`; `scan` requires `scan_id` and has no event requirement; `scan_item` requires `scan_id + item_ref + disposition` and permits null event ID while identity is unresolved; `model` requires `model_release_id` or update ID and may span many events; `global_health` requires a health/incident ID and may have no scan or event. All scopes retain mandatory generic record ID, type, created/receipt clock as applicable, actor, payload digest, privacy class and an observed source/evidence or explicit `evidence_unavailable` reason. No fake event key or quote data is permitted.

**Schema sketches (all exact types frozen at Gate 1/2):**

| Record | Mandatory body |
|---|---|
| Scan | scan id, source/tree observed time, collector version, pagination/completeness, discovered inventory and per-item disposition IDs; keep outage and truncated coverage distinct from zero markets |
| Scan item disposition | scan id, item ref, reason code/version, captured and ready times, **evidence_ref or explicit error/evidence-unavailable reason**; event/target/rule digest/quote/forecast are required *only if actually observed and relevant*. `NO_RULE` may have none of them. `MISSING_M2` stores M0-issued reference if available but no invented paired `forecast_id`. Scored `ELIGIBLE_NO_TRADE` always has actual paired `forecast_id`. |
| Contract/rules | stable outcome ID, immutable versioned target ID, alias history, dependency/concentration groups, venue/conids checked for duplicate collisions, exact strike/operator/rounding/measurement, schedules, source, payout/exceptional conditions, fee/rule digests and receipt evidence |
| Quote/feature snapshot | request begin/end and receipt/ingest UTC + monotonic, broker `_updated` with documented meaning, 6509 raw/decoded, *per-leg* bid/ask/size/update and sync evidence, reconnect gaps, source issuance/availability/valid times, feature provenance, evidence hash and permission flags |
| Forecast | stable outcome ID, target/threshold and canonical YES view, selected input anchor `T_g`, source/snapshot received+ready <= `T_g`, **registered issuance deadline `D_g` and each actual issuance clock `I_M0`, `I_M2` or `I_fallback` <= `D_g`**, pinned model/policy/checkpoint and feature hashes, M0 midpoint, genuinely issued M2 or genuinely issued fallback, family support/[L,U] if applicable; source-state guard must still be valid at issuance, without reading post-anchor values into predictions. |
| Decision | **Conditional by disposition:** preforecast `NO_RULE`/`NO_CUTOFF_SNAPSHOT`/`HOLD_PAIR_CONFLICT` requires scan item/ref, reason, observed error/evidence; no fabricated target/rule/forecast/quote/fee/edge. `MISSING_M2` stores actually issued M0 and absent-M2 reason if available, but no full paired forecast. Scored `ELIGIBLE_NO_TRADE`, fee/budget `HOLD_TRADE_ONLY` and model-bound `NO_TRADE_UNSUPPORTED` require actual `forecast_id` plus input/source references; pricing/fee/edge only when used for that decision. `SUGGESTION_RESERVED` additionally requires supported side-bound interval, current ask and time/size quality, **screened authorized limit ceiling**, strict `edge_at_ceiling > margin` inequality *at that ceiling*, one-use manual intent/expiry and atomically reserved all-in under daily/open/concentration budgets. |
| Execution | private matching to one manual intent, human attempt and IBKR evidence, state `SUBMISSION_UNKNOWN`/`SUBMITTED`/`CANCEL_REQUESTED`/`CANCEL_CONFIRMED`/`PARTIAL_FILLED`/`UNRECONCILED` etc., actual fills and fees per leg/quantity, settlement cash and adjustment lineage, reservations released **only** by trusted reconciliation |
| Settlement | per-target as-of source-state transitions and evidence vintages, venue-binding binary final state+receipt/ingest times, rule version, void/exceptional status and corrections, separate broker cash-posting and offset/reconciliation proof |
| Model update | locked update-policy ID, scheduled training and source cutoff, *actually observed+ready venue-binding labels*, per-forecast protected dependence block/embargo, training/tuning/calibration cohorts **relative to that forecast checkpoint** (previously scored+matured blocks may roll into a later scheduled update), code/schema/checkpoint hashes, intraday shadow vs primary stream flag, `TRAINING_CHECKPOINT_APPROVED` independently from prospective `PROMOTION_APPROVED` and protected single-look evidence |

**Primary scoring clocks and denominator:** every enrolled event stores `T_g`, `D_g`, actual per-model issuance clocks, registered scoring-only maturity cutoff `S_g`, enrolled threshold refs `J_enrolled`, paired score refs `J_pair` with binding+received+ready by `S_g`, and reason-coded censored refs including `LATE_LABEL`; late-scored labels may nonetheless be admitted to future scheduled training by separate cutoff `U` and its protected-block guards. Both M0 and M2/fallback must be actually issued by `D_g` on information no later than `T_g`; later issuance is admissible only before disqualifying source state as of issuance. Per-event Brier difference divides by `|J_pair|`, not `|J_enrolled|`. No paired thresholds => no event score. Account fees and budgets only change trade dispositions, not forecast scoring membership.

**Exactly-once logical emission:** local write idempotency uses (`record_type`, canonical_id`, payload version`) to prevent retry duplicates. Outages are distinct `health` records. Immutability is logical/event-sourced; corrections append superseding records, never rewrite a historical forecast. Model training reads only verified finalized labels with explicitly versioned corrected source policy.

## E. Durable local storage and Git export design

- Operational store: SQLite in WAL mode in `local_artifacts/v4/` with **verified** `PRAGMA synchronous=FULL` on a tested durable volume, atomic transactions and unique idempotency keys; private market/source objects use content-addressed storage. Durably write and fsync evidence object, atomic rename and directory sync where supported **before** database commits references. Backup/restore SQLite+WAL, evidence objects, manifests and private mapping keys as a consistent set. Prove restore and pending reservation persistence at G2.
- Actionable pretrade barrier: `durable source evidence -> BEGIN IMMEDIATE -> check same-concentration group + daily + open/old intent budgets -> insert snapshot/forecast/decision/manual_intent/maximum-cost RESERVATION -> COMMIT (FULL) -> display one-use human suggestion`. No actionable display before commit. Expired UI suggestions, crash before import, broker session change, midnight, cancellation request and open orders all **retain** risk until trusted broker-side reconciliation. Unknown activity => `HOLD_RECONCILIATION`; never infer no order from missing local entry. Recompute availability inside transaction for race safety.
- Every UTC/local-date export contains signed-off manifest (row counts, schema hashes, per-file SHA256, per-record hash/sequence bounds, per-item skips, missing event IDs and coverage/pagination gaps) with reproducible generator version. Keep date-boundary rules fixed. For prior days, append corrections under the *current* date, do not edit closed partitions.
- Git `records/` publishes **only** recursively type-checked, source-licensed, default-deny allowlisted fields; reject private markers even nested in permitted metadata and deny reconstructable quotes where not licensed. Allowed paired probabilities and labels support only declared **score replay**. Input/feature/source temporal replay requires the authorized, backed-up private archive. Do not claim that hashes alone reproduce data. A lossless raw archive is needed for full end-to-end point-in-time reconstruction; public Git cannot be asserted to cover that if restricted source payloads are missing.
- `git add`/`commit`/`push` is a **separate, human-controlled** release flow with privacy/license scan. Frequent local data writes must never auto-push private changes to public GitHub.
- Local backup + restore test is a mandatory Gate 2/3 precondition. Daily review checks byte integrity and ledger linkage.

## F. Point-in-time contract (bitemporal)

For each source `s`: `valid_at`, `issued_at`, `observed_at`, `available_at` where known, broker updated timestamp if present, API request start/end, stored wall/monotonic receive times; use source-specific timing contract. If `available_at` is not demonstrable <= forecast cutoff, feature is missing/unsupported and cannot be imputed from a later source value. Label `final_at` and `observed_final_at` are tracked independently; a late revision is a new settlement record, not an invisible overwrite.

**Label eligibility uses two independent deadlines.** The same factual barrier applies to both uses: an authoritative venue-binding binary result (or rule-verified binding source vintage) must be effective, actually received/observed and ingest-ready **by the relevant cutoff**; a finality stamp alone never suffices. **Primary scoring** uses the registered **scoring-only** maturity/censoring cutoff `S_g`; if binding evidence is first ready after `S_g`, the enrolled threshold remains `LATE_LABEL`, is absent from `J_pair` and is never retrospectively added to the primary score. **Subsequent training** uses the scheduled **actual update cutoff `U`**, *not* `S_g`, with the exact target/rule/source guard, dependence-block, embargo, primary-update-schedule and original forecast input `T_g`/issuance `D_g` guards independently enforced. Thus for S04: final effective at 12:00, first received+ready 12:08, scoring `S_g=12:06` => `LATE_LABEL`; training `U=12:05` => reject, training `U=12:10` => consider if all other guards pass. The label can train a future distinct block without changing its earlier score. Separate venue-final, provisional partial source, under-review, void/exceptional and broker cash states. Include valid observed events regardless of trades; deduplicate stable outcome IDs and protect dependence blocks. Corrections append new venue-proven evidence and explicit score restatement lineage, never retroactively enter older fits. Fixed snapshot selection and itemized censoring/missingness apply before outcomes.

## G. Risk / execution ledger

`reserved_all_in = quantity * limit_price_ceiling + worst_case_fee_upper_bound + other_maximum_costs`; require atomic held reservation before actionable suggestion. The **same `limit_price_ceiling`** is used in the frozen conservative-edge inequality `supported_p_lower * verified_payout - quantity-adjusted limit ceiling - max_fee - execution_reserve > margin` (strict inequality; equality means `NO_TRADE_EDGE_AT_LIMIT`), applying consistent units/quantity; a lower current ask cannot excuse a failing limit-ceiling edge. If the actual permitted limit changes, recompute and re-approve a new durable intent before suggestion, without erasing the old reservation until reconciliation. `all_in_outlay = actual_filled_premium + actual_fees + other_paid_costs` for broker-matched fills; for initial pilot `quantity = 1` and `all_in_outlay <= 1.00`, with strict stop on unknown fees/costs. Use different formulas where payout not 1.00. Pre-trade use a conservative fee upper bound, post-trade replace *in execution record only* with actual fees; preserve original predicted costs. Outstanding limit orders count toward exposure until reliably canceled, even though the system itself never submits them.

`realized_net_pnl = total_authorized_final_broker_cash_credits - premium_paid_all_legs - fees_all_legs - other_paid_costs` with coupons/refunds/adjustments explicit; for an eligible ForecastEx opposite-leg offset, count both purchased premiums and fees then netting credit **once**, quantity matched; if closed early, the settlement cash for the offset position may be zero and exceptional outcomes require a separate disposition. Partial fills are explicit. Reconcile broker transaction in private vault with sanitized execution record.

## H. Explicit testing and kill switches

**Design acceptance vectors are enumerated in `08_G0_ACCEPTANCE_MATRIX.md`. Before G1 calls, create and independently verify a dedicated **read-only** transport entrypoint with exact HTTPS loopback host/port/method/path allowlist, rejected redirects, trusted cert handling (do not inherit V3 `verify_tls=False`), no raw URL/exception/account/token health fields, and no order endpoint. Permission and provider terms are G1 inputs.

**Synthetic/property tests:** rules inclusive/exclusive, timezones and DST, crossing known outcome before quote, official-source delayed revisions, YES/NO complementary mapping and mirror quotes, monotone strike curve, impossible probabilities, delayed status 6509, stale quote, negative/zero size, unmatched conid, fee > budget, duplicate scan/partial fill, after-hours cutoff, crash during pre-trade record write, duplicate final label, label correction, candidate upgrade never mutates original champion output, lookahead via forecast publication/actual observed times, records privacy/secret scanner and declared source licenses, every closed historical hash preserved.

**No-order invariant:** strict method+host+endpoint allowlist permits only verified capability/market-data/approved auth-health operations. No order submission, modify or cancel endpoints; no trading API client/module. If a permitted auth keepalive uses POST, list that **exact route** and document side effects, not a wildcard POST. V3 client’s `verify_tls=False`, dynamic base URL and raw exception reporting are **not** acceptable defaults for V4. Synthetic fixtures and mocked responses test failure modes without paper-trading fills or invented economic returns.

**Operational HOLD:** no auth, untrusted TLS/endpoint or forbidden redirect, missing real-time mode or bid/ask size age, reconnect/session handoff gap, identity/rule/source conflict, already determined result, venue review, partial bound uncertainty, clock drift, unreconciled or unmatched positions/intents, unknown cost upper bound, missing durable journal, violated budget, nonapproved production model, or failed permission-aware export.

## I. Provisional first implementation contract

**Single later major-upgrade ZIP** (per owner workflow) is acceptable for initial V4 code, but build it on a branch and stop at explicit review gates before first human real trade. It should contain complete modules, deterministic synthetic tests, local installation/backup, and a read-only CLI for API capability; no automatic orders; GitHub publication separate from validation. `V4.0` should contain the **full vertical slice** (discover/forecast/decision/manual fill/settlement/update/report) even if some families initially return `NO_TRADE` until capability / support checks pass. Do not postpone essential logging and settlement defenses.

## J. Existing implementation vs assumptions

**Actually verified from uploaded repo source:** V3 read-only `IBKRClient` implements ForecastEx category/market/details/rules/schedules and `/iserver/marketdata/snapshot`; `ibkr_capability.py` decodes quote field 6509, matches pairs, and sanitizes selected fields. The V3 `run_ibkr_capability_audit.py` accepts `--auto-weather` with a regex, but probes the alphabetically first `max_markets` matches and only a few pairs. Its output is **not** evidence of currently tradable nearest-expiry coverage or working live trading.

**Unverified, require Gate 1 real API output:** authentication now, broad category/family coverage, clock/update semantics, real quote sizes, fees actually applied to owner account, last trade/release/finality, settlement link coverage, source licensing, live order reconciliation capabilities, network stability and rate limits. Do not put these in the frozen protocol as already accomplished.
