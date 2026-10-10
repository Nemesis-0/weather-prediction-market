# Data

The complete working datasets are intentionally not committed to this
repository.

The historical analysis used two primary external data sources:

- Kalshi historical market data for daily maximum-temperature contracts.
- NOAA/NBM NBS forecast data with source-backed publication timing.

The local research workspace contains raw source files and processed panels
that are substantially larger than the final research outputs. Public Git
history therefore contains the analysis code, protocols, audits, and final
result tables rather than the full working data directory.

## Reconstruction code

Relevant market-data code is under:

- [`../src/market/`](../src/market/)
- [`../src/market/backfill_twc_candles.py`](../src/market/backfill_twc_candles.py)
- [`../src/market/build_panel.py`](../src/market/build_panel.py)

Relevant weather-data code is under:

- [`../src/weather/`](../src/weather/)
- [`../src/weather/backfill_nbm.py`](../src/weather/backfill_nbm.py)

Point-in-time and timing audits are under:

- [`../src/audit/`](../src/audit/)

The final scientific results are retained under:

- [`../results/final_v1/`](../results/final_v1/)
- [`../results/final_v2/`](../results/final_v2/)
- [`../results/v2_market_reaction/`](../results/v2_market_reaction/)
- [`../results/v2_residual_assimilation/`](../results/v2_residual_assimilation/)

Some freeze manifests reference local data artifacts that are not redistributed
in this repository. Those manifests are preserved as historical provenance
records and should not be edited.

## V3 prospective-data policy

V3 begins prospectively. Raw market and weather information should be captured
as it is observed rather than reconstructed later whenever the research claim
depends on timing or executability.

Prospective V3 runtime data are intentionally excluded from Git. The tracked
repository should contain schemas, collection code, integrity rules, frozen
research configuration, and selected non-sensitive canonical outputs — not the
full raw stream.

The future collector must follow these rules:

- preserve the raw provider payload or a lossless raw-event representation;
- record a local wall-clock receive timestamp;
- record a local monotonic receive timestamp for ordering / latency diagnostics;
- retain provider timestamps with their exact documented semantics;
- never call a broker update timestamp an exchange timestamp without support;
- record contract / settlement metadata needed to interpret each quote;
- retain collector-health, reconnect, and feed-gap events;
- keep raw events append-only / immutable after capture;
- version derived transformations rather than overwriting raw information;
- never backfill information that was not actually available at the historical
  decision time into a prospective record;
- never store brokerage credentials, account identifiers, bank information,
  tax identifiers, identity-document information, or exact residential
  addresses in research data.

The first V3 schemas should be frozen only after the active
[`API capability audit`](../docs/v3/api_capability_audit.md) establishes what
fields and timestamp semantics are actually available.
