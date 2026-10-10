# Results

This directory separates canonical scientific outputs from intermediate working
results.

## Final closures

- [V1 final closure](final_v1/V1_FINAL_CLOSURE.md)
- [V1 final manifest](final_v1/V1_FINAL_MANIFEST.txt)
- [V2 final closure](final_v2/V2_FINAL_CLOSURE.md)
- [V3 / weather-domain final allocation closure](../docs/v3/weather_alpha_domain_closure_20261008.md)

## V2 H2.1 - first recorded post-publication response

- [H2.1 summary](v2_market_reaction/v2_market_reaction_summary.txt)
- [By-city descriptive results](v2_market_reaction/v2_market_reaction_by_city.csv)
- [By-transition descriptive results](v2_market_reaction/v2_market_reaction_by_transition.csv)

The original H2.1 machine-specific manifest is preserved locally but excluded
from the public repository because it contains an absolute local filesystem
path.

## V2 H2.2 - later-window post-publication association

- [Final H2.2 summary](v2_residual_assimilation/final_h22/V2_H2_2_FINAL_SUMMARY.txt)
- [Final H2.2 statistics](v2_residual_assimilation/final_h22/v2_h22_final_statistics.csv)
- [Denominator concentration](v2_residual_assimilation/final_h22/v2_h22_denominator_concentration.csv)
- [Market-structure diagnostics](v2_residual_assimilation/final_h22/v2_h22_market_structure_diagnostics.csv)
- [Post-result freeze manifest](v2_residual_assimilation/H2_2_POST_RESULT_FREEZE_SHA256.txt)

The H2.2 directory also retains the pre-result and execution-freeze manifests
that document the specification history.

## V1 point-in-time audit outputs

Canonical timing and implementation audits remain under:

- [`audit/`](audit/)

## Excluded working outputs

The following directories are local/regenerable working outputs and are
intentionally excluded from public Git history:

- `development/`
- `historical_holdout/`
- `historical_economics/`
- `corrected_historical/`
- `corrected_historical_economics/`

Their exclusion does not change the frozen final V1 or V2 conclusions.

## V3 result policy and final status

V3 produced **no canonical positive executable-alpha result**.

Its final weather-domain status is:

`FOREGROUND_RETIRED / PASSIVE_WATCH_ONLY`

The V3 repository still preserves protocols, code, tests, and closure records
because they document the prospective research process and the reasons routes
were killed or deallocated.

Infrastructure checks, paper orders, and exploratory shadow outputs must not be
promoted into evidence of executable alpha merely because they look profitable.
In particular:

- paper fills are engineering evidence, not live-fill evidence;
- midpoint PnL is not executable PnL;
- exploratory shadow PnL before a freeze is not a confirmatory result;
- post-hoc threshold, timing-window, city, contract, or strategy-family
  selection cannot be presented as frozen prospective evidence;
- a live-profitability claim requires actual fee, spread, slippage, latency,
  liquidity, and fill behavior to be represented.

See the [final weather-domain closure](../docs/v3/weather_alpha_domain_closure_20261008.md)
for the current interpretation.
