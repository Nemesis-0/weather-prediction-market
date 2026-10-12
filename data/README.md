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

V3 was designed as a prospective program: when a research claim depended on
timing or executability, market and weather information was to be captured as
observed rather than reconstructed later.

Prospective V3 runtime data are intentionally excluded from Git. The tracked
repository contains schemas, collection code, integrity rules, frozen research
configuration, and selected non-sensitive canonical outputs — not the full raw
stream.

The prospective collection policy required these rules:

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

V3 schema freezing was gated on the
[`API capability audit`](../docs/v3/api_capability_audit.md), which documented
what fields and timestamp semantics were available before prospective protocol
freezes were treated as operational.
