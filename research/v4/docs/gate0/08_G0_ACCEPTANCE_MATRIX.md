# Gate 0 bounded recheck — Required adversarial acceptance matrix

**Status:** test **specification**, not evidence that runtime V4 passed. Solmax should judge whether acceptance logic closes the six design findings. Do not run Gateway or place orders as part of G0. Later code must implement these cases at G1/G2/G3/G4 according to gate allocation.

| ID | Finding | Minimal scenario | Required result | Gate to execute production implementation |
|---|---|---|---|---|
| I01 | A1 | Duplicate scans and both YES/NO sides for same strike | One canonical YES target, one event score weight; mirror side diagnostic only | G2 |
| I02 | A1 | Same source measurement period relisted; release time postponed; rule version updated | Stable outcome ID, dependence block, train/eval assignment and concentration balance; substantive payout change yields new *linked* target | G2 |
| I03 | A1 | Two YES conids with conflicting rule/strike metadata reversed in response order | Deterministic `HOLD_PAIR_CONFLICT`, never input-order selection | G1/G2 |
| I04 | A1 | One event has 100 eligible thresholds, another has 1; same outcomes/scores as Solmax fixture | Equal **outcome-event** contribution. No raw-row mean; distinguish +0.116436 from event-weighted −0.060000 in audit fixture | G2/G4 |
| I05 | A1 | Correlated releases from different families, same measurement window | Same connected dependence block for inference; precommitted family assignment avoids identical-outcome double count | G2/G4 |
| I06 | A1 | No quote at predefined as-of, later quote available | `NO_CUTOFF_SNAPSHOT`; do not select nearest later quote; coverage denominator retains event | G2 |
| I07 | A1 | M0 unavailable, M2 missing, **on-time** fallback, delayed final, void | Distinct reasons; only actually issued `<=D_g` fallback => score difference 0; other missing counterparts never retrospectively imputed; preserve enrollment coverage | G2/G4 |
| I08 | A1 | Snapshot 11:54:50; `T_g=11:55:00`; actual M0/M2 issuance 11:55:30; registered `D_g=11:56:00` versus `D_g=T_g` | Admissible for 11:56 deadline only when all inputs received+ready `<=T_g` and outcome undetermined at issuance; fail 11:55 deadline; log issuance separately for each model/fallback | G2/G4 |
| I09 | A1 | One eligible matured threshold with paired Brier difference +.12, another enrolled threshold missing M2 | `J_enrolled=2`, `J_pair=1`, event score +.12; **not** +.06; if none paired, no score; coverage exposes both | G2/G4 |
| I10 | A1 | Qualified two-sided book and on-time paired forecasts; account fee unknown or daily budget exhausted | Still score legal matured forecasts, but trade decision is `HOLD_TRADE_ONLY`; no unverified fee/budget selection of primary cohort | G2/G4 |
| S01 | A2 | Proven irreversible partial source crosses `>` strike while venue open | Determined side withheld **before** official final release, with receipt/time evidence | G2 |
| S02 | A2 | Source equals threshold under `>` and `>=` | Different correct YES states from precise comparator; time availability pinned | G2 |
| S03 | A2 | Provisional/source-revisable crossing, conflicting copies, venue-under-review | Conservative provisional/HOLD state; no false binding label or actionable suggestion | G2 |
| S04 | A2 | Venue-binding vintage effective 12:00, first received+ingest-ready 12:08; **scoring-only** cutoff `S_g=12:06`; scheduled training updates `U=12:05` and `U=12:10` | Primary score is `LATE_LABEL` (exclude from `J_pair`/keep in enrollment), never backfilled after `S_g`; 12:05 training rejects, 12:10 training may admit after binding+receipt+ready and distinct-block/embargo/update-policy/forecast guards; **training is not bound by `S_g`** | G2/G4 |
| S05 | A2 | Upstream late revision after venue-final binary, no venue correction | No silent relabel; append diagnostic revision and preserve frozen forecast/fit; official venue correction is separately versioned | G2/G4 |
| Q01 | A3 | YES bid/ask .41/.45, NO bid/ask .55/.59 with synchronized $1 complementary rules | One M0_YES=.43; NO only mirror check; no second outcome or alpha position | G1/G2 |
| Q02 | A3 | Real-time `6509=R`, but one leg stale after reconnect | `HOLD_STALE_OR_ASYNC`; mode alone not freshness proof | G1/G2 |
| Q03 | A3 | YES support [.52,.68], NO all-in cost .40 | NO lower = .32, no positive conservative net edge; NEVER use 1−.52=.48 | G2/G3 |
| Q04 | A3 | Model has point estimate but no independently justified support interval | `NO_TRADE_UNSUPPORTED`, even if apparent positive expected value | G2/G3 |
| Q05 | A3 | YES lower .60, ask .40, fee .01, reserve .02, required margin .05. At manual ceiling .58, edge −.01 despite ask edge +.17; at ceiling .52, edge **exactly +.05** | Both ceilings reject as `NO_TRADE_EDGE_AT_LIMIT` (the latter **on equality**); accept on edge only when `edge_at_ceiling > .05`, and only if the separate $1 cap and all other gates pass. Price must be the one embedded in the reserved intent | G2/G3 |
| C01 | A3 | Opposite-leg ForecastEx offset, purchases .40+.35, total fees .02, one validated net credit 1.00 | Net cash .23 before coupons/adjustments; both premiums+fees charged, credit posted once | G2/G4 |
| C02 | A3 | Canceled unfilled order; partial/mismatched quantity; exceptional payout; later fee adjustment | Separate pending/exception workflow and versioned cash events; no fictitious PnL or double booking | G2/G4 |
| U01 | A4 | Update includes future label or label from event/block currently forecast | Reject update; preserve old champion and input snapshot | G2/G4 |
| U02 | A4 | Candidate or calibration fit contains protected comparison cohort | Reject protected promotion; training approval not promotion approval | G2/G4/G5 |
| U03 | A4 | User inspects daily Brier plots and changes hyperparameter after poor score | New update-policy ID and **new forward cohort**, not retrospective improvement of previous primary claim | G4/G5 |
| U04 | A4 | Added unregistered formal look at event 40 after formal single-look set for event 100 | Inference fails verification; daily descriptive dashboards allowed | G4/G5 |
| U05 | A4 | Event block A was scored, then venue-binding label for A is observed+ready before scheduled update; new forecast is for distinct, non-overlapping block B | A may enter B's later *registered* training/tuning/calibration if embargo satisfied; A's earlier score immutable; A must NOT enter a new A or overlapping-block forecast | G2/G4 |
| U06 | A4 | Intraday shadow challenger refit between registered daily primary checkpoints | Shadow result may be logged descriptively, but cannot change primary `update_policy_id`, its cadence, issued scoring stream or terminal look | G4 |
| U07 | A4/G4 | First authoritative binding label observed+ready, legal checkpoint, **zero human fills** | First G4 label/update review proceeds; cash/fill subreview remains pending, not a blocker to observation-driven training validation | G4 |
| R01 | A5 | Two simultaneous $0.60 reservations, shared $1 concentration cap | One succeeds and one rejects atomically under DB transaction | G2 |
| R02 | A5 | Human order may have been submitted before process crashed; no import | Outstanding reservation persists; next suggestion that would exceed cap blocked until trusted reconciliation | G2/G3 |
| R03 | A5 | Cancel requested, partial fill during cancel, calendar midnight, UI expiry, account handoff | No premature exposure release; filled/outstanding amounts reconciled separately | G2/G3 |
| R04 | A5 | Restore DB only but evidence object/manifest absent; then full DB+evidence restore | Partial restore fails closed; full restore proves pending intent, referential integrity, correct hash and exposure | G2 |
| R05 | A5 | Human placed order outside recorded suggestion or broker session cannot be reconciled | `HOLD_RECONCILIATION` suppresses new actionable suggestions | G2/G3 |
| X01 | A6 | `NO_RULE` with scan item+reason+error evidence but no event/rule/quote/fee/forecast; no-quote item; scored `ELIGIBLE_NO_TRADE` with forecast | Enforce both common envelope (`record_scope=scan_item`, `scope_ref`, event nullable) AND branch-specific body: preforecast holds have no invented FKs, scored no-trade has actual `forecast_id` | G2 |
| X06 | A6 | Complete successful scan no single event; `NO_RULE` unresolved item; multi-event `model_update`; global health outage; baseline-only M0 issuance with M2 absent | Require scan/item/model/health scope-appropriate refs, null event permitted except confirmed event scope; `MISSING_M2` cites genuine M0 ID but not fabricated paired forecast, while issued scored candidate requires actual forecast | G2 |
| X02 | A6 | Page truncation, rate-limit outage, category failure | Coverage gaps/pagination status recorded; cannot claim verified zero markets | G1/G2 |
| X03 | A6 | Private marker nested in nominally allowed `metadata`, or top-level arbitrary scalar | Recursive schema rejects entire export; no pass-through | G2 |
| X04 | A6 | Allowed public M0/derived feature could reconstruct restricted raw quotes under actual terms | Projection denies by field-level license/channel policy until permission is shown | G1/G2 |
| X05 | A6 | Public replay using paired licensed probabilities/labels vs private full replay with backed-up source objects | Public score replay only; authorized private replay reconstructs cutoff, skips, and transformations; missing archive fails restore | G2/G4 |
| E01 | Pre-G1 | `https://localhost:5001` with untrusted TLS, redirect to external host, unexpected method or order path | V4 fails closed, suppresses raw URL/exception/token in output; no order endpoints reachable | Before any G1 API probe |
| E02 | G1 | Snapshot API warm-up, mixed timestamps, duplicate YES conid, one platform displaces Gateway brokerage session | Complete gap evidence; no claim of live actionable book or safe human handoff until tested | G1 |
| E03 | G2 | Synthetic token in log, test bundle and public JSON; historical V1–V3 diff | Passing explicit secrets scan and no unrelated changes; no raw private leak | G2 |
| E04 | G3 | Actual account fee upper bound unknown or proposed $1 all-in exceeded | `NO_TRADE` regardless of apparent edge; manual pilot only after signed gate decision | G3 |

## Audit checklist and evidence level

- **G0 reviewer:** inspect five open A1/A2/A3/A4/A6 acceptance-rule corrections in 01/02/03/07, retain A5 as closed-at-design, and independently recheck I08/I09/I10, S04, Q05, U05/U06/U07, and X01/X06; exercise nearest neighboring original cases I02/I04, Q01/Q03 and X03 for regressions. Reproduce synthetic math if helpful; no network or account access needed.
- **G1:** validate actual event/data license/session/clock/quote structure, supported families and outcome-blind sampling parameter values; test transport allowlist before touching Gateway.
- **G2:** implement and independently run deterministic tests including power-loss/restart, private archive backup/restore, secret scanner, and unchanged frozen V1–V3 path/hash diff.
- **G3:** owner-approved actual budgets, provider fees, handoff and unambiguous account/order reconciliation; permit only manual small pilot after GO.
- **G4/G5:** legal label checkpoints and protected forward promotion; no peeking at held-out outcomes.

**Never convert these test-specification rows into claims of executed production verification.**
