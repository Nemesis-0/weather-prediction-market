# Contract Rules Audit

## V1 Scope

Primary target:
- Daily maximum temperature prediction markets

Initial cities:
- New York City
- Chicago
- Denver

Purpose:
- Define the exact settlement target before any weather modeling.
- Contract-specific rules override generic weather help pages.
- Unknown details remain explicitly unverified rather than inferred.

## Contract Audit Table

| Field | NYC | Chicago | Denver |
|---|---|---|---|
| Series ID | KXHIGHNY | KXHIGHCHI | KXHIGHDEN |
| Example event | KXHIGHNY-26SEP28 | KXHIGHCHI-26SEP28 | KXHIGHDEN-26SEP28 |
| Settlement provider | The Weather Company | The Weather Company | The Weather Company |
| Settlement location code | CLINYC | CLIMDW | CLIDEN |
| Human-readable location | New York City | Chicago | Denver |
| Physical station mapping | Not independently verified | Not independently verified | Not independently verified |
| Local timezone | America/New_York | America/Chicago | America/Denver |
| Target variable | Daily maximum temperature | Daily maximum temperature | Daily maximum temperature |
| Target date | Local calendar date specified by event | Local calendar date specified by event | Local calendar date specified by event |
| Bucket structure | Mutually exclusive temperature buckets; thresholds vary by event/date | Mutually exclusive temperature buckets; thresholds vary by event/date | Mutually exclusive temperature buckets; thresholds vary by event/date |
| Endpoint rule | Read exact inequality from each contract; do not infer solely from display label | Read exact inequality from each contract; do not infer solely from display label | Read exact inequality from each contract; do not infer solely from display label |
| Preliminary data | May differ from final TWC value because of rounding/conversion | May differ from final TWC value because of rounding/conversion | May differ from final TWC value because of rounding/conversion |
| Exact rounding algorithm | Not independently verified | Not independently verified | Not independently verified |
| Material-error revision | Kalshi may delay resolution pending corrected data | Kalshi may delay resolution pending corrected data | Kalshi may delay resolution pending corrected data |
| Missing-data fallback | Last fair price determined by Kalshi if valid data remains unavailable through permitted resolution period | Last fair price determined by Kalshi if valid data remains unavailable through permitted resolution period | Last fair price determined by Kalshi if valid data remains unavailable through permitted resolution period |
| Last trading boundary | 11:59 PM local time on event date | 11:59 PM local time on event date | 11:59 PM local time on event date |
| Fee handling | Must use contemporaneous executable fee schedule in economic evaluation | Must use contemporaneous executable fee schedule in economic evaluation | Must use contemporaneous executable fee schedule in economic evaluation |
| Audit status | Sufficient for V1 data engineering; station mapping unresolved | Sufficient for V1 data engineering; station mapping unresolved | Sufficient for V1 data engineering; station mapping unresolved |

## Modeling Rules

1. Never assume generic NWS observations equal the settlement target.
2. Preserve settlement-provider/source regime by date.
3. Store the exact event ticker and bucket inequality with every observation.
4. Use point-in-time weather data only: issue time, availability time, and valid time must all be retained.
5. Never use preliminary observations as final settlement labels unless explicitly marked.
6. Economic evaluation must use executable bid/ask prices and contemporaneous fees, not midpoint prices.

## Open Questions

These do not block V1 data collection:

- Exact physical station mapping behind CLINYC / CLIMDW / CLIDEN.
- Exact internal TWC aggregation and rounding implementation.
- Historical dates on which settlement-provider regimes changed.
- Series-specific maker-fee treatment.

These should be resolved only when they become necessary for feature engineering,
historical labeling, or execution analysis.

## Audit Note — 2026-09-29

Current specific KXHIGHNY, KXHIGHCHI, and KXHIGHDEN contract pages identify
The Weather Company as the settlement source and use CLINYC, CLIMDW, and CLIDEN
respectively. Specific contract rules are treated as authoritative for V1.

The objective of this document is not to reverse-engineer every Weather Company
internal process before modeling. Its purpose is to prevent target-definition
and settlement-source mistakes.
