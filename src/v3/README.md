# V3 - Prospective Executable Weather Alpha

**Current status:** the weather foreground program is retired as of 2026-10-08;
this package is retained for reproducibility and reuse of research
infrastructure. See
[`../../docs/v3/weather_alpha_domain_closure_20261008.md`](../../docs/v3/weather_alpha_domain_closure_20261008.md).

Historical V1/V2 code and canonical results remain frozen and must not be
retuned using the closed historical sample.

## Public package structure

- `ibkr/`
  IBKR session handling and market-data interfaces used by the prospective V3
  infrastructure.

- `audit/`
  Public timing, synchronization, capability, and research-integrity support.

- `study1/`, `study2/`
  Preserved public implementations for the two documented V3 study stages and
  their closure evidence. Their presence does not imply that a strategy is
  active or profitable.

The final public closeout contains only implemented, documented V3 packages.
Internal alpha-funnel / discovery code remains in the local/private research
workspace and is intentionally not distributed here.
