# V3 - Prospective Executable Weather Alpha

**Current status:** the weather foreground program is retired as of 2026-10-08;
this package is retained for reproducibility and reuse of research
infrastructure. See
[`../../docs/v3/weather_alpha_domain_closure_20261008.md`](../../docs/v3/weather_alpha_domain_closure_20261008.md).

Historical V1/V2 code and canonical results remain frozen and must not be
retuned using the closed historical sample.

## Package structure

- `ibkr/`
  IBKR session handling, instrument discovery, and market-data interfaces.

- `contracts/`
  Contract registry, YES/NO pairing, threshold geometry,
  and settlement-rule normalization.

- `collector/`
  Prospective market-data collection, connection health,
  reconnect handling, and feed-gap logging.

- `weather/`
  Point-in-time weather publications, station observations,
  running daily maximum, and later nowcasting inputs.

- `signals/`
  Prospective alpha-family and signal namespaces.

- `execution/`
  Fees, slippage, latency assumptions, shadow execution,
  and execution-validation support.

- `audit/`
  Timing, synchronization, data gaps, settlement mapping,
  and research-integrity checks.

- `study1/`, `study2/`, `alpha_funnel/`
  Preserved implementations for the V3 research stages and their closure
  evidence. Their presence does not imply that the corresponding strategy is
  active or profitable.
