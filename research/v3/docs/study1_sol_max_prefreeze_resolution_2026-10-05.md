# V3 Study 1 — Sol Max Pre-Freeze Resolution

Status: **remediation candidate; untouched evaluation has not started**.

The adversarial review returned **NOT FREEZE-READY**, while explicitly accepting
(1) the scientific family, (2) the two-session shakedown amendment, and (3) no
need for a third long shakedown.  The remaining blockers are implementation and
pre-registration closure items, not a request for more strategy-result data.

## Accepted blockers

1. Same-strike YES/NO rule equality is insufficient for cross-threshold semantic
   equivalence.  The confirmatory path must fetch and archive metadata for every
   listed threshold in the fixed three-city universe; verify mutual YES/NO IDs;
   parse the scientific event date from `details.question`; normalize semantic
   fields across thresholds; and fail closed on missing/ambiguous metadata.
2. Broker `expiration` is not the scientific event date.  No expiration+1,
   nearest-expiration, or post-result repair is permitted in confirmatory mode.
3. Confirmatory acquisition must not use shakedown rotation, market downsampling,
   nearest-expiration selection, or evenly-spaced threshold sampling.  It uses
   NYC/UHLGA/KLGA, Chicago/UHMDW/KMDW, and Denver/UHBKF/KBKF and the full ladder
   mapped to the target event date.
4. Each adjacent structural pair is validated from a dedicated same-request
   two-conid snapshot.  Missing, duplicate, unexpected, delayed/frozen, malformed,
   off-tick, zero-size, over-latency or stale records fail that observation.
5. A fixed date ledger, nominal 30-second grid, abort policy and denominator are
   required before D0 is signed.
6. Cost arithmetic must use `Decimal`, verified fees, an explicit one-tick-per-leg
   reserve, a frozen funding proxy, and deterministic cent rounding.
7. Behavioral tests and a strategy-blind five-cycle live acceptance check must pass
   before the final freeze commit.

## Caution retained from the audit

IBKR `_updated` is not documented as an exchange-synchronous timestamp for every
BBO field.  The candidate `60s` age and `5s` pair-skew bounds are therefore
conservative broker-freshness screens, **not** proof of simultaneous exchange
quotes or fills.  The five-cycle acceptance check is allowed to test whether
those pre-result bounds are operationally coherent.  It must not output prices,
basket costs, margins, opportunity flags, or candidate counts.

## Current remediation stage

This commit may add reusable semantic/date/quote/cost/ledger primitives and the
strategy-blind acceptance runner.  It must **not** set D0, enable the 30-date
runner, or inspect strategy outputs.  A final freeze commit follows only after
acceptance evidence is reviewed and all GO/NO-GO boxes are mechanically signed.

## Public terms / fee facts checked on 2026-10-05

The current ForecastEx Daily Temperature terms state that the scientific date is
the **date listed in the Contract**, the source is Weather Underground, the
minimum tick is $0.01, and last trading is 11:59 PM local time on that listed
date.  The current published IBKR direct-client schedule lists ForecastEx broker
commission $0.00/contract and third-party exchange fee $0.01/contract.  These
facts are still re-verified at final freeze; account applicability is signed
explicitly rather than inferred from shakedown data.

## 2026-10-06 strategy-blind acceptance follow-up

The first five-cycle live acceptance run showed that the provisional `_updated`
age/skew screens were not operationally coherent as hard eligibility rules.
Without inspecting any strategy-result quantity, the project therefore moved
old `_updated` age and cross-leg `_updated` skew to diagnostics-only status;
implausibly future timestamps remain hard failures. See
`study1_acceptance_resolution_2026-10-06.md` for the frozen rationale and the
required second short acceptance gate.
