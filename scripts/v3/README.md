# V3 Operational Scripts

These scripts are retained as reproducible research tooling. **The weather
foreground program is retired as of 2026-10-08; none of these entry points
should be interpreted as an active trading strategy or a positive-alpha claim.**

Current status:
[`docs/v3/weather_alpha_domain_closure_20261008.md`](../../docs/v3/weather_alpha_domain_closure_20261008.md).

## `run_ibkr_capability_audit.py`

Read-only IBKR / ForecastEx capability audit. It does not implement or call any
order endpoint.

The audit can measure:

- Client Portal Gateway reachability and brokerage-session status;
- keep-alive (`tickle`) capability without persisting the session token;
- accounts-endpoint readiness without storing account identifiers;
- ForecastEx category-tree discovery;
- automatic weather / temperature market discovery;
- market contract geometry and YES/NO conid pairing;
- contract details and settlement rules;
- HTTP top-of-book bid/ask/size plus market-data availability code `6509`;
- a one-day / one-minute historical-data capability probe;
- a short read-only websocket top-of-book stream probe with local receive timing.

Default Client Portal Gateway base URL in the retained implementation:

```text
https://localhost:5000/v1/api
```

Outputs are written under ignored `local_artifacts/` paths. Credentials,
session tokens, and account identifiers must not be persisted.

Important boundaries:

- no order endpoint is implemented or called by the capability-audit client;
- paper/live fills are not alpha evidence;
- broker `_updated` is recorded only as a broker timestamp, not an exchange timestamp;
- session tokens and account identifiers are not persisted;
- the short websocket probe establishes capability, not full-day stream reliability.

## Historical Kalshi collector

Historical Kalshi snapshot collection remains separate from V3 at:

`../collect_kalshi_snapshot.sh`

## Study 1 tooling

`run_study1_shakedown.py`, the acceptance tools, the confirmatory-day runner,
and endpoint evaluator are retained for provenance and reproducibility.

Study 1 reached a final frozen pre-D0 state, but **confirmatory collection never
started**. The former schedule is historical only. Do not launch the old
confirmatory runner as if it were a current study without a new documented
research decision that preserves the existing frozen provenance.

Canonical protocol:

`docs/v3/study1_final_frozen_protocol.md`

## Study 2 tooling

Study 2 is **CLOSED / ECONOMIC KILL** for the current observation-only M0 route.

The source-capture, historical backfill, model-ready construction, frozen M0,
support/calibration, and economic-screen scripts remain in the repository so
the research sequence can be inspected and reproduced. They must not be used to
retune or rescue the closed route.

Canonical closure:

`docs/v3/study2_closure.md`

## Alpha Funnel tooling

The Alpha Funnel scripts are retained as a quick-screen / triage harness.
Completed static structural screening produced no PROMOTE survivor. Trigger-
dependent residual mechanisms are passive-watch only under the final weather
domain decision.

Canonical checkpoint:

`docs/v3/alpha_funnel_phase2_checkpoint_20261008.md`
