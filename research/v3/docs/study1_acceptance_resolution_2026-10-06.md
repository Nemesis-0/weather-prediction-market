# V3 Study 1 — Strategy-Blind Acceptance Resolution

Status: **pre-freeze operational amendment; untouched evaluation has not started**.

## Evidence reviewed

The first live five-cycle acceptance run on 2026-10-06 completed the fixed
NYC/Chicago/Denver event-date ladders and all 160 planned same-request adjacent-
pair checks without exposing basket costs, opportunity flags, candidate counts,
alpha, fills or PnL.

Observed strategy-blind health facts were:

- 5/5 cycles completed;
- 32 adjacent pairs per cycle, 160 pair checks total;
- host clock offset about 0.071 seconds;
- maximum request elapsed about 0.44 seconds;
- no strategy-result output was computed or emitted;
- 74 observations were quote-unavailable because an ask/size field was not a
  usable numeric value at that poll;
- 54 observations exceeded the provisional 60-second broker `_updated` age
  screen;
- 3 observations exceeded the provisional 5-second cross-leg `_updated` skew
  screen.

No prices, basket margins or opportunity frequencies were inspected in making
this amendment.

## Pre-freeze decision

The 60-second `_updated` age and 5-second cross-leg `_updated` skew screens are
removed as **hard quote-eligibility gates** before final freeze. They remain
recorded diagnostics.

Rationale: `_updated` is useful broker-side update metadata, but the project does
not have a documented guarantee that it is an exchange-synchronous timestamp for
each BBO field. Treating old age or cross-leg skew as a hard eligibility rule
would therefore encode an unsupported semantic interpretation. The live
strategy-blind check also showed that these provisional screens reject many
otherwise structurally valid same-request real-time snapshots.

The following protections remain hard fail-closed requirements:

- `6509` must decode as real-time;
- each adjacent pair is requested together in one two-conid HTTP request;
- response shape and conids must be exact, with no duplicates or substitutions;
- request latency stays within the frozen bound;
- ask and ask size must be usable and satisfy the quote schema for an observation
  to be quote-eligible;
- no forward fill is permitted;
- missing/invalid `_updated` remains a schema failure;
- an implausibly future `_updated` timestamp remains a hard failure;
- event-date, semantic-ladder, schedule and clock checks remain fail closed.

The acceptance summary must now distinguish ordinary `quote_unavailable`
observations from `structural_failure` observations. Final pre-freeze acceptance
passes only if every planned pair request is attempted and there are zero
structural failures. Quote-unavailable observations are retained as observed
missingness and cannot create a qualifying basket.

## Next gate

Run one more five-cycle strategy-blind live acceptance under this amended
interpretation. Do not compute or inspect basket costs, margins, opportunity
counts, alpha or PnL. If coverage is complete and structural failures are zero,
the project may proceed to final protocol freeze rather than another long
shakedown.
