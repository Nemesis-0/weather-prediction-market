# Weather Prediction-Market Research

**Independent empirical research on point-in-time information, market pricing, settlement semantics, and executable market structure.**

The historical weather-alpha research did **not** establish repeatable, executable advantage. Negative results and frozen evidence remain preserved; V4 is **not included** in this release.

## Study index

| Study | Status | Canonical result |
|---|---|---|
| [V1 — Static weather information](research/v1/README.md) | CLOSED | [Corrected V1 closure](research/v1/results/final/V1_FINAL_CLOSURE.md) |
| [V2 — Forecast revision / assimilation](research/v2/README.md) | CLOSED | [V2 closure](research/v2/results/final/V2_FINAL_CLOSURE.md) |
| [V3 — ForecastEx mechanism studies](research/v3/README.md) | Study 1 frozen/unlaunched; Study 2 CLOSED | [Final weather-domain closure](research/v3/docs/weather_alpha_domain_closure_20261008.md) |

V1/V2 used historical Kalshi weather-market data; V3 used prospective ForecastEx/IBKR observation and settlement checks. Do not combine these contexts as one confirmed live trading sample.

## Repository layout

```text
weather-prediction-market-research/
├── README.md
├── DATA_POLICY.md
├── research/
│   ├── README.md
│   ├── REORGANIZATION.md
│   ├── v1/{README.md,code/,docs/,results/}
│   ├── v2/{README.md,code/,docs/,results/}
│   ├── v3/{README.md,code/,docs/,configs/,schemas/,tests/}
│   └── shared/{README.md,code/,docs/}
├── requirements.txt
└── requirements-dev.txt
```

**The root `data/` workspace is deliberately untracked, not deleted by the installer.** See [data policy](DATA_POLICY.md). This archive contains no paper-trading or V4 implementation.

## Reproducibility

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q research/v3/tests
python research/v3/code/cli/run_ibkr_capability_audit.py --help
```

The last CLI is read-only and `--help` makes no broker call. Actual IBKR probing requires a separately authenticated local Gateway and appropriate entitlements.

The prior frozen historical protocols and evidence are retained; old recorded SHA256 values and old repository-relative paths are **not rewritten**. The [reorganization ledger](research/REORGANIZATION.md) explains path changes, exact-byte preservation, and the limits of runtime validation. Full V1/V2 reproduction requires external archived data, not included here.

## Research integrity

This is a scientific research archive, not a live profitability claim or trading recommendation. Previously closed studies were not reopened and V4 is a future, separately reviewed program.
