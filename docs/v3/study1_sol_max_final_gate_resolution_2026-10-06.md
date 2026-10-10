# V3 Study 1 — Sol Max Final GO/NO-GO Resolution

Status: **required pre-freeze implementation repairs completed in this freeze candidate; confirmatory collection has not started**.

The final adversarial gate returned **GO WITH REQUIRED PRE-FREEZE CHANGES** and
accepted the scientific family, fixed three-city universe, 30 consecutive
calendar dates, 09:00–17:00 America/New_York window, 30-second cadence,
two-poll revalidation, date-level endpoint, current conservative cost model,
health thresholds, and D0 = 2026-10-07 provided the implementation defects
below were corrected before the first session.

No strategy-result quantity was inspected while making these repairs.

## Fatal blocker 1 — semantic validation was not fully fail closed

Repair:

- every listed contract is now fetched and its question must be strictly
  parseable before it can be classified as TARGET_EVENT_DATE or OTHER_EVENT_DATE;
- an unparseable listed contract is a `STUDY_BLOCKER`; it can no longer disappear
  before adjacency is constructed;
- target-date YES/NO details and rules must agree on complement IDs, strike,
  product, question semantics and event date;
- both details and rules payout must be exactly $1.00;
- rules source must be Weather Underground and rules price increment must be
  exactly $0.01;
- cross-threshold semantic fingerprints must remain identical except threshold;
- the audited ForecastEx Daily Temperature Terms PDF is committed at
  `docs/v3/legal/DailyTemperatureTermsandConditions_2026-10-06.pdf` with SHA256
  `226826cb5d64cddc52c86b99a2e908f25ba48aa431f6c9ffe2c30e55731db511`;
- each daily run re-downloads the contract terms URL and requires the same frozen
  hash. A verified terms-version or semantic mismatch is `STUDY_BLOCKER`, not an
  ordinary market zero.

## Fatal blocker 2 — ordinary quote missingness could hide hard integrity errors

Repair:

- response shape/conids, both-leg real-time delivery, both-leg broker timestamp
  schema and future-time bounds are validated before ask/size availability;
- an ordinary missing ask/size therefore cannot mask delayed/frozen delivery or
  an invalid timestamp on the other leg;
- buyable asks are restricted to $0.01–$0.99 on whole-cent ticks;
- zero/one-dollar asks and zero size are quote-unavailable, not qualifying asks;
- malformed/off-range/off-tick values remain structural failures;
- `_updated` must be a valid millisecond epoch at or after 2000-01-01 and may not
  be implausibly in the future; old age and cross-leg skew remain diagnostics only.

## Fatal blocker 3 — session/input completeness was insufficiently enforced

Repair:

- each pair request and eligible response must occur before the frozen 17:00 ET
  end-exclusive boundary;
- each nominal slot records expected and observed pair-record counts;
- NORMAL slots require full coverage of every frozen adjacent pair;
- structural-invalid slots are globally ineligible for two-poll revalidation,
  even if some pair quotes inside that slot were individually usable;
- each day records a sealed-input SHA256 plus the freeze-manifest SHA256;
- the endpoint evaluator re-verifies the core freeze manifest, run identity,
  sealed-input hash, 960-slot ledger, per-slot pair coverage, session timing and
  structural-slot status before using any strategy input;
- missing/corrupt days are explicitly labelled operational/integrity failures,
  retained in the frozen denominator as zero, and count toward the >3-date
  operational kill rule;
- a recorded semantic/terms study blocker closes the study without evaluating
  the primary opportunity endpoint.

## Regression evidence

The corrected complete repository test suite contains dedicated regression tests
for the three blocker classes, including the exact silent-threshold-drop,
payout/tick mismatch, missing-ask masking delayed second leg, zero/one ask,
zero broker epoch, terms hash mismatch, structural-slot revalidation and sealed
input/session-integrity failure paths.

The installer must run the complete V3 test suite from the actual `b698f85`
parent before the freeze is committed.

## D0 rule

The first planned date remains **2026-10-07** only if this corrected freeze is
committed/tagged and operational authentication/metadata preparation is complete
before 09:00 America/New_York on that date. No partial first session is allowed.
If that condition is missed, do not run a shortened 2026-10-07 session; the
planned 30-date ledger must be re-frozen before any confirmatory collection.
