# Weather Prediction-Market Research

**Can public information improve probabilistic forecasts beyond prediction-market prices—and can an apparent statistical edge survive real-world trading constraints?**

An independent empirical research project investigating **information timing, probabilistic modeling, forecast-revision assimilation, and executable prediction-market structure**. The research progresses from historical Kalshi daily-high-temperature markets to prospective Interactive Brokers / ForecastEx market-data and settlement-rule studies.

The project emphasizes *what was knowable at the decision time*, honest out-of-sample evaluation, and the distinction between **predictive value**, **market response**, and **tradeable value**. Its completed studies did **not** establish a reliable executable advantage. That negative finding is part of the research outcome—not a result edited away.

## Research at a glance

| Study | Research question | Main methodology | Finding |
|:--|:--|:--|:--|
| **[V1 · Static information](research/v1/README.md)** | Do public weather forecasts improve a probability model beyond the market state? | Six-outcome conditional softmax; rolling-origin model selection; point-in-time audit; date-block bootstrap and execution stress | No reliable incremental predictive or economic value in the corrected historical evaluation |
| **[V2 · Forecast revisions](research/v2/README.md)** | Do newly published forecast revisions predict subsequent directional market movements? | Publication-aligned event study; first- and later-window vector projections; exact pre-publication placebo; moving-block bootstrap | Neither observation window established a reliable directional association |
| **[V3 · Executable mechanisms](research/v3/README.md)** | Can prospectively observed quotes reveal executable structural or settlement-aware opportunities? | IBKR/ForecastEx contract discovery; timestamp and rule validation; cross-threshold protocol; point-in-time settlement-state and executable-cost audits | Apparent opportunities were not promoted to a credible executable-alpha claim; one confirmatory study was frozen but never launched |

**Scope:** V1/V2 analyze a 46-date historical weather-market sample; V3 is a distinct prospective mechanism and data-integrity program. Their observations, venues, and claims are not pooled into a single live-performance record. [Detailed status and claim boundaries](research/v3/docs/weather_alpha_domain_closure_20261008.md).

## 1. Research motivation

A market price is not automatically a calibrated probability, and a more accurate forecast is not automatically a profitable trade. For a purported information advantage to matter, several questions must be answered separately:

1. **Information availability:** Was the signal publicly observable *before* the decision, rather than only reconstructable afterward?
2. **Incremental prediction:** Does the signal improve proper probability scores beyond an explicitly defined market-only baseline?
3. **Information assimilation:** If a public forecast changes, is there measurable subsequent repricing in the corresponding direction?
4. **Economic executability:** Is the signal compatible with the contract's exact settlement rules, displayed executable quotes, fees, time ordering, and trading availability?
5. **Research validity:** Are model choices, timing windows, outcomes, and statistical uncertainty handled without post-result selection?

The three versions address these questions in sequence. Negative evidence in an earlier version motivates a **new, separately specified research question**, not retroactive tuning of a closed study.

## 2. V1 — Incremental value of static public forecasts

**Hypothesis.** At a fixed **10:00 AM local** decision time, NOAA/NBM NBS `TXN`/`XND` information might add useful predictive information beyond the Kalshi six-bucket daily-maximum-temperature market distribution.

**Data and unit of analysis.** New York City, Chicago, and Denver; **46 calendar dates**, **138 city-days**, and **828 temperature-bucket contracts**. The modeling observation is a *city-day six-category event*—not six independent contract outcomes. Historical market states are paired with public forecast states using publication-time constraints.

**Pre-specified models.** All three models share an L2-regularized conditional-softmax form over the six ordered outcomes:

- **M0 — Market-only:** normalized market midpoint probabilities.
- **M1 — Weather-only:** a six-bucket probability *proxy* derived from NBM `TXN`/`XND`.
- **M2 — Market + Weather:** market and weather proxy together, testing the incremental contribution of the latter.

The weather proxy uses a Gaussian feature transformation; it is **not** claimed to be the true distribution of the contract's settlement temperature. Regularization was selected by **rolling-origin development-period log loss**; multiclass log loss was primary, Brier score secondary. Economic and execution-stress comparisons were separate from predictive scoring.

**Point-in-time correction.** A later source-backed NOAA publication census identified **four city-days** whose originally selected forecasts had not yet been public by 10:00 AM. These inputs were mechanically replaced with the latest source-verified eligible forecasts without changing the frozen study specification. The corrected 15-date evaluation is explicitly **not an untouched holdout**.

**Key corrected results:**

| Measure | Result | Interpretation |
|:--|:--|:--|
| Market-only M0 multiclass log loss | `1.0115` | Fitted baseline |
| Market + Weather M2 multiclass log loss | `1.0259` | Higher (worse) than M0 |
| M2 − M0 mean calendar-date log-loss difference | `+0.0144` | 3-day moving-block bootstrap 95% CI: `[-0.0376, +0.0863]` |
| M2 − M0 total historical PnL | `+$0.06` | Tiny and uncertain; not evidence of an executable edge |

**Conclusion:** Static NBM-derived proxy information did **not** show reliable additional predictive or economic value under this corrected, frozen design. The observed historical PnL is not real fill evidence and is sensitive to execution assumptions.

[Detailed V1 methodology and evidence](research/v1/README.md) · [Canonical final closure](research/v1/results/final/V1_FINAL_CLOSURE.md)

## 3. V2 — How markets respond to forecast revisions

**Hypothesis.** Even if a static forecast feature fails to improve a 10:00 AM prediction, a *new public forecast revision* might lead to subsequent directional market repricing.

**Reconstruction.** The same 46-date historical setting yielded **552 usable forecast states**, **414 sequential revision pairs**, and **220 revisions changing `TXN` and/or `XND`**. NOAA publication timing was independently supported, rather than inferred from nominal model-cycle times. Kalshi market data were historical **60-minute candles**.

**Design.** A forecast revision changes the six-bucket weather-proxy vector by `Δq`. The project projected subsequent market-probability movement `Δp` onto that *predefined weather direction*:

$$
\widehat\beta = \frac{\sum_i \Delta q_i^\top \Delta p_i}{\sum_i \lVert \Delta q_i\rVert^2}.
$$

Two separately defined analyses tested different observed windows:

| Analysis | Eligible events | Point estimate | 3-day moving-block bootstrap 95% CI |
|:--|--:|--:|:--|
| **H2.1** — first recorded post-publication response | 196 | `+0.02957` | `[-0.01225, +0.08462]` |
| **H2.2** — later-window directional association | 179 | `−0.02814` | `[-0.07276, +0.03360]` |

H2.2 additionally included a **pre-publication placebo**, an unnormalized-midpoint diagnostic, date-concentration checks, and fixed timing/eligibility rules. The placebo did not alter the primary null interpretation. Because the source consists of hourly candles, these are **observed post-publication windows**, not exact minute-by-minute reaction times or a causal estimate of information incorporation.

**Conclusion:** Neither window showed a reliable positive directional association under its frozen design. The slightly negative later-window estimate does **not** establish a reversal effect.

[Detailed V2 design and results](research/v2/README.md) · [Canonical final closure](research/v2/results/final/V2_FINAL_CLOSURE.md)

## 4. V3 — From forecast signals to executable market mechanisms

V3 shifted from reconstructed historical market behavior to **prospectively observed ForecastEx contracts via IBKR**, asking whether an apparent probability or structural discrepancy remains meaningful after exact **contract semantics, order-book geometry, settlement-state knowledge, fees, and time ordering** are checked.

### Study 1 · Cross-threshold structural consistency

Nested daily-temperature thresholds impose mathematical consistency restrictions. The planned study tested whether an apparent two-leg inconsistency could recur at **executable displayed asks**, after costs and two-poll confirmation—not merely in midpoint prices. It specified contract eligibility, a 30-second observation cadence, dated observations, cost reserves, a date-level endpoint, integrity checks, and result-access controls.

**Status: deferred before confirmatory collection.** Shakedown and a final pre-D0 protocol freeze were completed, but the planned 30-date confirmatory study **was never run**. No confirmatory structural-arbitrage result is claimed.

### Study 2 · Settlement-aware intraday nowcasting

The hypothesis was that an intraday observation-based probability estimate could differ favorably from an executable ForecastEx ask. The initial screen returned **78 apparently positive rows**. Independent review identified omitted *already-observed settlement-source information*: **76 of those 78** rows were blocked by the known state of the official settlement-relevant weather source. Two small diagnostic positives remained, with a maximum stated margin of approximately **$0.001624 per contract**, insufficient to rehabilitate the route.

**Status: closed without model rescue.** This is an illustration of why a mathematically computed edge can disappear when the true point-in-time settlement information is enforced.

### Market-structure findings

A separate structural screen found **no promoted deterministic guaranteed-payoff candidate**. In valid paired ForecastEx observations, YES/NO top-of-book fields were **mirrored, not independent queues** (for example, `Ask_Y + Bid_N = 1.00`). This matters for liquidity accounting and avoiding false cross-side opportunities.

**Conclusion:** The completed weather-focused executable-alpha search did not yield a defensible positive live-profitability claim. Its lasting contribution is a reproducible framework for **semantic, timestamp, and execution-aware falsification**.

[Detailed V3 studies and status](research/v3/README.md) · [Canonical weather-domain closure](research/v3/docs/weather_alpha_domain_closure_20261008.md)

## 5. What the repository implements

Beyond the final numerical results, the codebase documents an end-to-end empirical research workflow:

- **Market and weather data engineering:** historical Kalshi contract/candle ingestion, NOAA/NBM forecast-state reconstruction, six-bucket event alignment, and publication-timing validation.
- **Statistical modeling and evaluation:** regularized multiclass probability models, rolling-origin selection, proper scoring rules, date-aware uncertainty, and explicit historical execution stress.
- **Event-study experimentation:** predefined weather-revision vectors, market-response estimands, placebo tests, raw-vs-normalized diagnostics, and dependence-aware interpretation.
- **Prospective market infrastructure:** read-only IBKR/ForecastEx discovery and quote analysis, contract semantics, settlement-state checks, and fail-closed feasibility screening.
- **Research auditability:** frozen scientific specifications, integrity checks, surviving negative-result records, and explicit boundaries between hypothesis testing and real-world executability.

These pieces are separable: the repository does **not** present simulated economics as actual filled trades, and the historical data are not advertised as a live trading performance record.

## 6. Research methodology and safeguards

Across the program, the key practices are:

- **Point-in-time information sets:** distinguish forecast generation, actual public release, quote observation, and contract settlement-source knowledge.
- **Event-level statistical units:** respect six mutually exclusive outcomes per city-day, dependence among revised forecasts, and date-clustered uncertainty.
- **Predefined models and endpoints:** separate development, evaluation, diagnostics, and post-result interpretation; preserve negative outcomes.
- **Probability vs. economic evaluation:** proper scoring rules cannot substitute for actual executable asks, costs, size, and fill evidence.
- **Falsification before complexity:** a violated information-time or settlement-rule condition can invalidate an apparent edge before another model is trained.
- **Research provenance:** archived protocols, closed-study results, frozen manifests, code, and clearly stated reproduction limits.

The project makes **no claim of realized live trading profitability**. These studies do not imply that all weather markets are efficient or that no future event-market mechanism can be profitable.

## 7. Explore the project

| Start here | What it contains |
|:--|:--|
| [V1 study](research/v1/README.md) | Data construction, M0/M1/M2 definitions, corrected probability and economic results |
| [V2 study](research/v2/README.md) | Publication-aligned revision event study, H2.1/H2.2 estimands, placebo and uncertainty |
| [V3 study](research/v3/README.md) | ForecastEx mechanisms, frozen-but-unrun structural protocol, settlement-state audit and closure |
| [Research index](research/README.md) | Study-oriented navigation through protocols, code, and canonical outputs |
| [Data and reproducibility](DATA_POLICY.md) | Data sources, point-in-time provenance, public/private boundary, limitations |

### Code and reproducibility

The repository contains the historical scripts, public protocols, selected audit tables, and V3 deterministic tests. The full original market/weather archives and local broker runtime data are **not distributed**; passing the tests does not amount to rerunning V1/V2 on private raw data.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q research/v3/tests
python research/v3/code/cli/run_ibkr_capability_audit.py --help
```

The last command displays help only; it does not log in to a broker or submit an order. The V3 IBKR research interfaces are read-only. For source provenance and archive limits, see [Data Policy](DATA_POLICY.md).


---

*Research status: V1/V2 closed; V3 Study 1 deferred before confirmatory collection, V3 Study 2 closed, and the weather-focused foreground alpha program retired. Any future research version is a separate project phase and not evidence of profitability in V1–V3.*
