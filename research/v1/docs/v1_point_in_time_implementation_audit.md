# V1 Point-in-Time Implementation Audit

Audit date: 2026-09-30

## 1. Methodology

The audit independently recomputed the frozen 10:00 AM local decision time, the latest eligible 00/06/12/18Z NBS cycle under the +60 minute availability rule, raw TXN/XND provenance, and the latest complete synchronized six-bucket Kalshi snapshot at or before the decision time.

The audit used the exact city-days contained in `model_features_event.csv`, i.e. the observations actually supplied to the V1 predictive models.

## 2. Weather point-in-time diagnostics

- Total V1 city-days examined: 138
- Total weather rows used: 138
- Future-cycle violations: 0
- Unavailable-at-decision violations: 0
- Future substitutions: 0
- Nearest/alternate-cycle substitutions: 0
- Missing eligible forecasts replaced with later forecasts: 0
- Latest-cycle mismatches: 0
- Decision-time mismatches: 0
- Station mismatches: 0
- Missing TXN: 0
- Missing XND: 0
- Processed-weather/model-feature mismatches: 0
- Raw weather files missing: 0
- Raw wrapper mismatches: 0
- Raw target-valid-time row failures: 0
- Raw TXN/XND mismatches: 0
- Raw API runtime mismatches (where runtime field available): 0

Availability margin `decision_time - assumed_available_at`:

- Minimum: 60.0 minutes (1.00 h)
- Median: 120.0 minutes (2.00 h)
- Maximum: 180.0 minutes (3.00 h)

Cycle-frequency distribution by city:

```
cycle_hour  12Z
city           
Chicago      46
Denver       46
NYC          46
```

Exclusion / missingness reasons:

- None.

## 3. Market point-in-time diagnostics

- Market city-days examined: 138
- Future market-candle violations: 0
- Snapshot staleness >60 minute violations: 0
- Incomplete/non-synchronized selected snapshots: 0
- Selected snapshot not equal to independently recomputed latest complete snapshot: 0
- Selected quote source rows missing: 0
- Selected quote value mismatches: 0
- Exact 10:00 snapshots: 132
- Non-exact but eligible snapshots: 6
- Snapshot age minimum: 0.0 minutes
- Snapshot age median: 0.0 minutes
- Snapshot age maximum: 60.0 minutes

## 4. Responsible implementation

- NBS cycle eligibility: `src/weather/backfill_nbm.py` — `primary_decision_time()`, `latest_eligible_cycle()`, `expected_tmax_valid_time()`, and `main()`.
- Weather/market timestamp alignment: `src/market/build_modeling_master.py` — `main()`; specifically the at-or-before-decision filter, synchronized six-bucket grouping, and latest eligible snapshot selection.
- Predictive feature dataset construction: `src/modeling/build_model_features.py` — `bucket_mass()` and `main()`.

Source SHA256:

```
64820d65d56612ff6782a05daaf0e1769ec286426013a2f9fae0a38c302a8c90  src/weather/backfill_nbm.py
6294d928e2c4ccbcdbfcbdf1f3ddb9c8dd11eb2e360b4329cd25b6d7ede41244  src/market/build_modeling_master.py
ed8ee7c909afeb89c2135167729a1a96870af18b98a7140774cb64c4735353f5  src/modeling/build_model_features.py
```

## 5. Violations and interpretation

No point-in-time implementation violation was detected in the weather or market data actually used by V1.

No detected implementation issue changes the interpretation of the frozen V1 results.

## 6. V1 closure

**Under the frozen V1 specification, static NBM TXN/XND proxy information did not show reliable incremental predictive or economic value beyond the 10AM Kalshi market in this 46-date sample.**

The small positive Market-only historical PnL is not evidence of alpha. It is fully eliminated by +1¢ adverse execution and becomes negative at +2¢.

V1 does not establish scalable or realized tradeable profitability.

**FINAL AUDIT STATUS: PASS — V1 CLOSED**
