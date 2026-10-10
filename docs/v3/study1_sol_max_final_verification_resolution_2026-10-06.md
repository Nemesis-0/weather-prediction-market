# V3 Study 1 — Sol Max final implementation verification resolution (2026-10-06)

The exact candidate commit `58bf64c5ebe3eeb9de7ff9f06841d5bb1a95f39d` received `FINAL GO: NO` for one remaining endpoint-input integrity defect. No scientific design choice was reopened.

## Remaining blocker

`audit_valid_day_inputs()` verified sealed SHA, slot health, session bounds, and complete pair coverage, but a record in a `NORMAL` slot could omit `quote_status` or use an unknown value. `evaluate_city_date()` would silently ignore such a record because it only selected `QUOTE_ELIGIBLE` rows. That could misclassify malformed input as a valid zero-opportunity outcome.

## Frozen implementation correction

For every expected pair record in a `NORMAL` slot:

- `quote_status` is mandatory and must be exactly `QUOTE_ELIGIBLE` or `QUOTE_UNAVAILABLE`.
- `QUOTE_ELIGIBLE` requires a finite in-session request timestamp, a finite in-session response timestamp, and a two-row snapshot with required `conid` and finite `ask` fields.
- `QUOTE_UNAVAILABLE` requires an in-session request timestamp, `failure_class=quote_unavailable`, and a non-empty reason.
- Missing/unknown status or incomplete status-specific fields raises an input-integrity failure before any opportunity calculation.
- `evaluate_city_date()` also rejects missing/unknown statuses in any slot already declared valid, so direct helper invocation cannot silently convert malformed input into zero opportunity.

This is an implementation-only fail-closed correction. Research question, cities, dates, session, cadence, revalidation, cost model, date-health thresholds, denominator rules, recurrence gate, and endpoint timing are unchanged. D0 remains 2026-10-07 provided the corrected exact commit is frozen before the full 09:00 ET session.

## Narrow re-verification follow-up

A second narrow re-verification of exact commit `94d7a1d4062d3406a1ce3af973ee993b4158c685` found that the status enum itself was fail-closed, but redundant record identity fields were not yet fully bound to the frozen pair registry. In particular, a valid `pair_id` could coexist with a missing or contradictory `city_id`, and a `QUOTE_ELIGIBLE` record could carry contradictory failure fields. Because city filtering occurred inside the evaluator, such malformed records could be skipped or misinterpreted rather than classified as integrity failures.

The implementation is therefore closed one level further before D0:

- every sealed record must bind `city_id`, lower/higher thresholds, and lower-YES/higher-NO conids to the exact frozen `pair_id` mapping;
- `QUOTE_ELIGIBLE` may not carry a non-empty `failure_class` or `reason`;
- the two eligible snapshot rows must use the frozen lower-YES and higher-NO conids in that order;
- `evaluate_city_date()` defensively rejects a current-city frozen pair whose `city_id` is missing or contradictory, even if the global day audit were bypassed;
- targeted regressions cover missing/mismatched city identity, pair-field drift, eligible/failure-field conflict, and snapshot conid drift.

No scientific parameter or accepted protocol choice changed. This remains an implementation-only fail-closed correction to prevent malformed sealed input from becoming a valid zero-opportunity date.

## Holistic final-gate follow-up

The subsequent holistic pre-D0 audit of exact commit `8d364a566f9d7c11e9e1aae2a2b459fdd3cda414` found two remaining endpoint-integrity gaps, both implementation-only:

1. a day labelled `VALID` was checked for consistency between the slot ledger and stored health counts, but the endpoint did not independently re-apply the frozen eligibility thresholds (minimum 951 NORMAL slots, no more than 9 total structural-invalid slots, no run of 3 structural-invalid slots, and no terminal failure);
2. malformed `day_health_summary.json` could raise during JSON parsing outside the date-level integrity-failure path and terminate the endpoint instead of being retained as an integrity-failed zero in the denominator.

The correction now makes the endpoint re-derive date-health eligibility from the verified 960-slot ledger before any opportunity evaluation. A claimed `VALID` date must account for all frozen nominal slots, match the re-derived normal/invalid/consecutive-invalid counts, contain no terminal failure or study blocker, and satisfy every frozen date-health threshold. Missing, malformed, wrong-date, wrong-protocol, or unknown-status health summaries are converted to explicit `INTEGRITY_FAILURE_RETAIN_IN_DENOMINATOR` rows and counted toward the operational kill rule. All planned dates are health-pre-scanned before opportunity calculation so any readable semantic/terms blocker still closes the study with priority.

No scientific parameter or accepted protocol choice changed.


## Final holistic health-reader follow-up

The next holistic audit of exact commit `02b1f2e742e920c6ff161832f945f55f9ad3b533` confirmed that frozen date-health thresholds are now independently re-derived correctly, but found two remaining fail-closed edge cases in the health-summary reader:

1. a non-string `date_status` such as a JSON array or object could reach set-membership logic and raise `TypeError` instead of becoming a date-level integrity failure;
2. for the exact frozen protocol/date, a readable non-empty `study_blocker` could be discarded by an ordinary `date_status` schema error before the endpoint's global semantic-blocker pre-scan.

The reader now validates `date_status` type before enum membership whenever no readable semantic blocker is present. Non-string status values are returned as explicit health-summary integrity errors rather than raising. For the exact frozen protocol/date, a non-empty string `study_blocker` is preserved before ordinary status-schema validation so semantic/terms closure retains priority over ordinary integrity/date failure. Regression tests cover list/object `date_status`, unknown status plus a readable blocker, and wrong-type status plus a readable blocker.

No scientific parameter or accepted protocol choice changed.
