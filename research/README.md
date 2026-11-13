# Research studies and scientific record

This repository contains three sequential research versions. Each version addresses a **different scientific question** and has its own protocol, code, results and claim boundary. For a narrative overview of the experiments and key findings, begin with the [project README](../README.md).

| Study | Data and evaluation | Main outcome | Detailed entry |
|:--|:--|:--|:--|
| **V1 — Static forecasts** | Historical Kalshi, 46 dates, 138 city-days; market-only vs. weather-augmented multiclass probabilities | No reliable incremental predictive or economic value after point-in-time correction | [V1 methods and findings](v1/README.md) |
| **V2 — Forecast revisions** | Historical Kalshi / NOAA publication-aligned event study; 196 first-window and 179 later-window events | Neither window established reliable positive directional repricing | [V2 methods and findings](v2/README.md) |
| **V3 — Executable mechanisms** | Prospective IBKR / ForecastEx market observations and contract/settlement integrity controls | Study 1 frozen but unrun; Study 2 model route closed; no executable-alpha claim established | [V3 methods and findings](v3/README.md) |

## Reading paths

**For research questions and findings:** [V1](v1/README.md) → [V2](v2/README.md) → [V3](v3/README.md).

**For original specifications and evidence:**

- V1: [predictive model specification](v1/docs/model_specification_pre_weather_results.md), [corrected scientific closure](v1/results/final/V1_FINAL_CLOSURE.md).
- V2: [market-reaction protocol](v2/docs/v2_market_reaction_protocol.md), [later-window protocol](v2/docs/v2_h2_2_residual_assimilation_protocol.md), [final closure](v2/results/final/V2_FINAL_CLOSURE.md).
- V3: [structural pre-D0 protocol](v3/docs/study1_final_frozen_protocol.md), [settlement-aware Study 2 closure](v3/docs/study2_closure.md), [domain closure](v3/docs/weather_alpha_domain_closure_20261008.md).

**For implementation:** [V1 code](v1/code/), [V2 code](v2/code/), [V3 code and tests](v3/code/), and [cross-study historical components](shared/README.md).

## Interpretation boundaries

- A better probability forecast does not by itself establish an executable trade.
- A directional association does not establish causation or a replicable economic edge.
- The V3 Study 1 protocol was frozen before D0, but confirmatory collection **did not start**.
- V1/V2 raw data are not fully distributed; public tables, frozen records and code are available under their respective study directories.
- No real-money profitability is claimed by the closed V1–V3 research program.

For data-source provenance and reproducibility limits, see the [Data Policy](../DATA_POLICY.md). Historical repository-path migration and freeze-compatibility evidence remain available in the [technical migration record](REORGANIZATION.md), separate from the scientific overview.
