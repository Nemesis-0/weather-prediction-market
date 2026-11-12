# V3 Study 1 — Structural Consistency Pre-Freeze Charter

Status: **long-run strategy-blind shakedown complete under documented amendment; operational freeze candidate not yet final**.

This document governs the shakedown period for the first prospective V3 study. It is deliberately strategy-blind during shakedown: operational data quality may be inspected, but opportunity frequency, hypothetical PnL, and parameter choices that improve apparent edge may not be used to tune the study.

## 1. Frozen scientific architecture

The first V3 study is **structural consistency across nested daily-high temperature thresholds**.

For two contracts with verified identical settlement definitions except threshold, where the higher-threshold event is a subset of the lower-threshold event, the eventual confirmatory study will test whether a conservative two-leg basket can repeatedly appear below its ordinary-settlement payout floor after frozen costs and execution assumptions.

The shakedown collector **does not calculate this basket, detect opportunities, or compute PnL**.

The first study does not test NOAA/NBM predictive value. V1/V2 remain closed and are not reused to tune V3 rules.

## 2. Frozen guardrails

During shakedown, it is permitted to inspect only:

- authentication/session health;
- market and contract discovery coverage;
- contract metadata and settlement-rule completeness;
- quote field completeness;
- bid/ask and displayed-size delivery mechanics;
- field `6509` values and update behavior;
- request/response timing, batch skew, cadence stability and gaps;
- HTTP errors, throttling symptoms, reconnect/restart behavior;
- machine clock/monotonic-timer consistency;
- unattended operation and daily reauthentication practicality.

During shakedown, it is prohibited to use:

- structural basket cost;
- apparent arbitrage/opportunity frequency;
- hypothetical or realized PnL;
- favorable cities, thresholds, dates or time windows;
- favorable polling cadences;
- post-hoc cost buffers;

as a reason to choose the final universe, session window, cadence, threshold policy, or evaluation rule.

## 3. Operational parameters intentionally left unresolved

Exactly three operational choices remain open until shakedown evidence is complete:

1. **Eligible universe rule** — a deterministic rule based on contract semantics and feed reliability, not apparent opportunity frequency.
2. **Collection/evaluation session window** — based on documented/open trading availability and stable feed coverage, not favorable prices.
3. **HTTP polling cadence** — based on measured field completeness, update behavior, batch skew, error/throttling behavior and unattended stability, not favorable signal counts.

A provisional cadence may be used for shakedown only. It is not a confirmatory parameter.

## 4. Shakedown budget and amendment

The original target was **three full unattended sessions on distinct dates**,
with daily Gateway authentication exercised at least once per session.

Before confirmatory evaluation began, this pre-freeze target was amended to
**two clean four-hour unattended sessions on distinct dates, including one
weekend and one weekday session**. The amendment was based only on operational
evidence: complete scheduled-cycle coverage, zero feed/auth/tickle/gap failures,
real-time delivery status throughout, complete rule/schedule guardrail coverage,
and bounded cycle latency. No basket cost, opportunity frequency, alpha, or PnL
was inspected.

The rationale and exact evidence are recorded in
[`study1_shakedown_amendment_2026-10-05.md`](study1_shakedown_amendment_2026-10-05.md).

Up to two additional dates remain available only for a specific plumbing defect
identified before final freeze. They are not to be run merely to increase
sample size or search for favorable market behavior.

## 5. Data policy

Mandatory shakedown artifacts:

- a universe/contract metadata snapshot;
- sanitized settlement-rule payloads or rule hashes where available;
- point-in-time quote records with request-send and response-receive times;
- raw field-presence information;
- `6509` raw/decoded values;
- explicit missing-field and gap records;
- session-health/keepalive records;
- final session health summary.

Never persist credentials, usernames, account identifiers, cookies or session tokens.

Do not forward-fill quotes across missing responses. Missing data remain missing.

Broker `_updated` is preserved as a broker-provided timestamp field only; it is not relabeled as a synchronized exchange timestamp.

## 6. Settlement semantics

No pair may enter the later confirmatory study unless settlement definitions are independently verified to be identical except for the nested threshold relation. Required items include, where applicable:

- event date;
- station/source/site;
- observation window and time zone;
- temperature units and rounding;
- comparator and threshold;
- YES/NO complement structure;
- payout, tick/multiplier and trading cutoff;
- cancellation/refund/fallback provisions;
- rule version/source and archival hash.

The collector may archive candidate metadata; it must not automatically declare two contracts semantically equivalent.

### Shakedown implementation discipline

During shakedown, contract sampling within a market must remain price-blind. The implementation may use public `last_trade_time` metadata to choose the nearest still-tradable expiration, and may sample complete YES/NO pairs across that active threshold ladder to test feed coverage. It may not prefer an expiration or threshold because observed prices look favorable.

The shakedown must archive at least one YES/NO rule pair and one trading schedule for every selected market. Trading schedules are operational evidence only: they help distinguish planned closures from feed gaps and help choose the final session window, but they do not by themselves establish quote executability or semantic equivalence.

## 7. What ends long-run shakedown

Under the documented amendment, long-run shakedown is complete because the
project demonstrated:

- two clean four-hour unattended sessions on distinct dates;
- one weekend and one weekday session;
- stable authentication/keepalive behavior with zero recorded failures;
- deterministic market/contract discovery;
- reliable distinction between complete and incomplete BBO observations;
- real-time `6509` delivery status throughout both sessions;
- bounded cycle/batch timing with zero detected cadence gaps;
- zero missing contract responses and zero HTTP errors;
- no silent quote forward-fill;
- full selected-market rule-pair and trading-schedule guardrail coverage.

Long-run shakedown completion does **not** by itself authorize confirmatory
evaluation. Before final freeze the project still requires:

- a reviewed cross-threshold settlement-semantics rule, not merely a same-strike
  YES/NO rule-pair check;
- an explicit event-date mapping that does not treat broker expiration labels as
  the scientific event date;
- frozen universe/session/cadence/cost/gap/selection rules;
- one narrow adversarial pre-registration review.

The current candidate is documented in
[`study1_operational_freeze_candidate.md`](study1_operational_freeze_candidate.md).


### Day-1 metadata fail-fast guardrail

Before quote collection starts, the shakedown runner must obtain one complete
YES/NO rule pair for every selected market and one trading-schedule record for
every selected market. The rule-audit budget is auto-sized to at least two
contracts per selected market. Missing rule coverage, rule-endpoint errors,
YES/NO semantic mismatch, or missing schedule coverage aborts the session before
strategy-blind quote collection. This is an operational-validity guardrail, not
a strategy filter.
