# Weather Prediction-Market Research

**Independent empirical research on point-in-time information, prediction-market pricing, settlement semantics, and executable market structure.**

This project studies a simple question that becomes difficult under real-world constraints:

> **Can public weather information produce a repeatable, executable edge in prediction markets once timing, contract semantics, liquidity, fees, and settlement state are handled correctly?**

Across historical and prospective studies, the answer was **not established**. The main contribution is therefore methodological: a reproducible record of how apparently promising signals disappeared under stricter point-in-time, semantic, and executable-market checks.

## Research progression

| Study | Question | Design | Final conclusion |
|---|---|---|---|
| [**V1 — Static weather information**](results/final_v1/V1_FINAL_CLOSURE.md) | Does public NOAA/NBM weather information add value beyond the 10 AM market state? | Frozen historical comparison with point-in-time source audit and block-bootstrap inference | No reliable incremental predictive or economic value after timing correction |
| [**V2 — Forecast revision / assimilation**](results/final_v2/V2_FINAL_CLOSURE.md) | Do public forecast revisions predict subsequent market movement? | Frozen event studies of first-window and later-window reactions | No reliable positive directional assimilation effect |
| [**V3 Study 1 — Structural consistency**](docs/v3/study1_final_frozen_protocol.md) | Do nested ForecastEx weather contracts exhibit persistent executable inconsistencies? | Prospective protocol engineering and semantic validation | Protocol frozen; confirmatory collection not launched |
| [**V3 Study 2 — Settlement-aware nowcasting**](docs/v3/study2_closure.md) | Can intraday weather state support a conservative edge over executable asks? | Prospective executable screen with settlement-source auditing | Apparent edge largely vanished after conditioning on already-observed settlement state |
| [**V3 mechanism screening**](docs/v3/weather_alpha_domain_closure_20261008.md) | Do simple structural, timing, or liquidity mechanisms survive executable screening? | Bounded semantic and market-structure triage | No candidate promoted to a positive executable-alpha claim |

V1/V2 use historical Kalshi weather-market data. V3 moves to prospective ForecastEx observation through IBKR, so the phases are treated as distinct empirical settings rather than pooled as one market sample.

**Project status: Closed.** The pre-specified evidence did not support further active investigation of the weather-market hypothesis.

## Recommended reading order

For a short technical review:

1. [Weather-domain closure](docs/v3/weather_alpha_domain_closure_20261008.md) — final allocation decision and cross-study synthesis.
2. [V1 final closure](results/final_v1/V1_FINAL_CLOSURE.md) — corrected point-in-time historical result.
3. [V2 final closure](results/final_v2/V2_FINAL_CLOSURE.md) — forecast-revision / assimilation result.
4. [V3 Study 2 closure](docs/v3/study2_closure.md) — settlement-aware executable screen and closure.

The frozen-but-unlaunched Study 1 protocol and the full historical protocol trail are available through the [documentation index](docs/README.md).

## Selected findings

### 1. Point-in-time source validity changed the V1 conclusion

A source-timing audit found four weather observations that were not actually public by the frozen decision time. After mechanical correction, the primary V1 comparison was:

- M2 − M0 mean calendar-date log-loss delta: **+0.0144**
- 3-day moving-block bootstrap 95% CI: **[-0.0376, +0.0863]**

Negative values would favor the augmented weather model; the corrected result did not establish reliable incremental value.

### 2. Forecast revisions did not show a reliable assimilation effect

V2 evaluated two frozen event-study questions.

**H2.1 — first recorded post-publication response**

- $\beta = 0.02957$
- 3-day moving-block bootstrap 95% CI: $[-0.01225,\ 0.08462]$

**H2.2 — later-window association**

- $\beta = -0.02814$
- 3-day moving-block bootstrap 95% CI: $[-0.07276,\ 0.03360]$

Neither stage established a reliable positive directional effect.

### 3. Settlement-source state invalidated most apparent V3 Study 2 edges

The first admissible ready-window screen contained 78 apparent positive rows. After adding already-observed Weather Underground settlement-source state:

- 76 of 78 apparent positives were blocked;
- 2 diagnostic positives remained;
- the largest remaining margin was about **$0.001624** per contract.

The route was closed rather than retuned.

## Research methods

The project separates three questions that are often conflated:

1. **Predictive value** — does an information source improve probability forecasts?
2. **Information assimilation** — does new public information predict later market movement?
3. **Executable economic value** — does a discrepancy survive real asks, fees, latency, liquidity, settlement semantics, and uncertainty?

Core safeguards include:

- point-in-time source and market-state reconstruction;
- source-backed publication timing;
- frozen research protocols and SHA-256 manifests;
- moving-block bootstrap inference;
- executable ask/size requirements;
- fee and latency treatment;
- semantic validation of contract geometry and settlement rules;
- fail-closed integrity checks;
- explicit negative-result closure rather than post-hoc rescue.

## Repository map

```text
weather-prediction-market-research/
├── README.md
├── configs/          # frozen non-secret research configuration
├── data/README.md    # data reconstruction and availability policy
├── docs/             # protocols, audits, and closure records
│   └── v3/
├── results/          # selected canonical outputs
├── schemas/          # prospective record schemas
├── scripts/          # reproducible command-line entry points
├── src/              # market, weather, modeling, and audit code
├── tests/v3/         # deterministic integrity tests
└── requirements.txt
```

Raw datasets, broker-session state, runtime market streams, logs, and exploratory local artifacts are intentionally excluded from public Git history.

## Reproducibility

Create an isolated environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Run the deterministic test suite:

```bash
python -m pytest -q
```

Full historical reruns require reconstruction of external source data described in [`data/README.md`](data/README.md).

## Limitations

- Historical V1/V2 evidence covers a limited date range and three cities.
- Historical market data are lower frequency than full tick-level order-book data.
- V3 prospective evidence is mechanism-specific and short-horizon.
- V3 Study 1 confirmatory collection was never launched.
- No live-profitability or scalable-alpha claim is made.

## Research integrity

The repository intentionally preserves negative findings. Closed studies were not reopened to search cities, timing windows, thresholds, or models for a favorable result after the primary evidence failed its frozen gate.

The project is presented as a reproducible empirical research record, **not as a trading recommendation**.
