# Weather Prediction Market V1 — Research & Trading Framework

## 1. Core Objective

The project is not “build a weather bot.” The research question is:

> **Do public meteorological signals add incremental predictive and economic value beyond weather-market prices?**

The project must pass two separate tests:

### Predictive hypothesis

$$
H_1:\quad M_{\text{market+weather}} > M_{\text{market-only}}
$$

where improvement is measured with proper probabilistic scoring rules such as Brier score, log loss, and calibration diagnostics.

### Economic hypothesis

$$
H_2:\quad E[\text{net PnL}] > 0
$$

where net PnL is evaluated using executable bid/ask prices, fees, execution assumptions, and any additional realistic trading frictions.

A better forecast is **not** automatically a profitable strategy.

---

## 2. V1 Scope

### Primary market
- **Daily maximum temperature contracts**
- Initial candidate cities:
  - New York City
  - Chicago
  - Denver

### Why this is the V1
- High recurrence: new events almost every day.
- Enough repeated observations for chronological testing.
- Clear binary / bucket-style payoffs.
- Better observed liquidity and tighter spreads than daily minimum temperature markets in the initial market audit.
- Strong fit with existing background in weather/climate modeling, probability, calibration, held-out validation, and spatiotemporal modeling.

### Not part of V1
- Daily minimum temperature
- Hourly temperature
- Snowfall
- Hurricane / disaster contracts
- Complex market making
- Fully automated live trading
- Deep learning for its own sake

Daily rainfall remains the main second-stage candidate after temperature V1.

---

## 3. Contract Definition Comes Before Modeling

For every contract, save and audit:

- market / series ID
- city / station / location definition
- settlement provider
- time zone
- settlement date and time window
- threshold or bucket boundaries
- inclusion/exclusion of endpoints
- rounding rules
- missing-value rules
- trace-precipitation rules if relevant
- revision / correction policy
- contract rule version

This is mandatory because current weather-contract documentation can differ between specific contract rules and general help / rule pages.

The prediction target must match the **actual settlement variable**, not a convenient substitute such as a generic NWS station reading.

---

## 4. Point-in-Time Data Architecture

The project must preserve only information genuinely available at the decision time.

### Market data
At each predetermined decision timestamp, save:

- YES bid / ask
- NO bid / ask
- visible size / depth
- volume
- open interest if available
- liquidity fields
- timestamp
- contract status
- fee schedule / fee version

### Meteorological data
Potential sources include:

- NBM
- LAMP
- HRRR
- GFS / GEFS
- ECMWF IFS / ENS / AIFS where available
- METAR / station observations

For every forecast input, preserve:

- model issue time
- actual availability / receipt time
- valid time
- forecast value / quantile / probability
- source version where possible

### Important restriction
Reanalysis products such as ERA5 / ERA5T may be useful for historical scientific analysis, but must not be treated as real-time trading features if they were not available at the historical decision time.

---

## 5. Baseline Models

V1 should deliberately stay simple.

### Model 0 — Market-only

$$
M_0 = f(p_{\text{market}})
$$

This is the main benchmark.

### Model 1 — Weather-only

$$
M_1 = f(X_{\text{weather}})
$$

Possible inputs:

- calibrated NBM probability information
- station-specific forecast residuals
- ensemble dispersion
- cloud / wind / frontal conditions
- observed temperature trajectory
- lead time
- season / month

### Model 2 — Market + Weather

$$
M_2 = f(p_{\text{market}}, X_{\text{weather}})
$$

The main scientific question is:

$$
P(Y=1\mid p_{\text{market}}, X_{\text{weather}})
$$

versus:

$$
P(Y=1\mid p_{\text{market}})
$$

The purpose is to test whether weather information contains **incremental information beyond the market**.

V1 should prefer simple, regularized / shrinkage models over large ML systems.

---

## 6. Main Statistical Evaluation

Use proper probabilistic evaluation, including:

- Brier score
- log loss
- calibration plots
- calibration intercept / slope where useful
- comparison of Market-only vs Market+Weather
- evaluation across lead times
- evaluation across cities
- evaluation across pre-specified weather regimes if justified

Do not rely only on:
- accuracy
- AUROC
- RMSE of a temperature point forecast

The target is a **probability distribution over contract outcomes**, not merely a temperature estimate.

---

## 7. Chronological Development and Frozen Validation

### Development phase
Use historical / early-period data to choose:

- feature set
- model family
- station-calibration method
- primary decision time
- trading threshold
- no-trade conditions
- execution assumptions

### Freeze
Before final evaluation, freeze:

- features
- model
- parameters
- decision time
- threshold
- fee treatment
- execution logic
- position-sizing rule
- stop conditions

### Prospective evaluation
After freeze, collect future data without changing the strategy.

Initial prospective period:
- at least 6–8 weeks as a **screening period**
- not sufficient by itself to claim stable profitability

Same city-day contracts, multiple buckets, and repeated timestamps must not be treated as independent events.

---

## 8. Trading Rule

Let:

$$
\hat p
$$

be the model’s estimated true probability.

For a YES contract:

$$
EV_{\text{YES}}
=
\hat p
-
\text{ask}
-
\text{fee}
-
\text{other execution cost}
$$

A simple frozen rule can be:

$$
\hat p - \text{ask} - \text{fee} > \delta
$$

then buy YES.

Otherwise:

$$
\text{NO TRADE}
$$

The same logic applies to NO contracts.

### Important
- Use the **actual ask** for simulated buys.
- Do not use mid-price to compute trading PnL.
- Do not deduct the full spread again if ask has already been used.
- Maker / passive strategies require separate fill modeling and should not be part of the first V1 result.

---

## 9. Economic Evaluation

Report at least:

- gross PnL
- net PnL after fees
- profit per trade
- ROI
- number of trades
- no-trade count
- opportunity frequency
- capital usage
- visible depth
- holding time
- drawdown
- city / date concentration
- sensitivity to execution delay
- block-bootstrap uncertainty by date / weather system where appropriate

The project must distinguish:

$$
\text{forecasting alpha}
$$

from:

$$
\text{tradeable alpha}
$$

and from:

$$
\text{scalable alpha}
$$

---

## 10. Kill Criteria

Write these before final testing.

### Stop the trading hypothesis if:
1. Contract labels / publication times cannot be audited reliably.
2. Weather information improves weak baselines but does not beat Market-only.
3. Improvement appears only after repeatedly changing cities, thresholds, or weather regimes.
4. Net PnL becomes negative after realistic fees / execution assumptions.
5. Positive PnL comes primarily from one isolated event.
6. Profit disappears under reasonable execution-delay assumptions.
7. The strategy produces positive point estimates but uncertainty remains too wide to establish meaningful evidence.
8. Predictive improvement exists, but economic edge is consistently consumed by trading costs.

A negative result is still a valid research result.

---

## 11. Possible Outcomes

### Outcome A — No market-relative predictive edge

$$
M_{\text{market+weather}} \not> M_{\text{market-only}}
$$

Interpretation:
- public weather information appears already incorporated into prices
- stop trading hypothesis
- preserve as a market-efficiency research result

### Outcome B — Predictive edge, no economic edge

$$
M_{\text{market+weather}} > M_{\text{market-only}}
$$

but:

$$
E[\text{net PnL}] \le 0
$$

Interpretation:
- statistically useful information exists
- spread / fees / execution remove monetization
- strong research result, but do not trade for profit

### Outcome C — Positive after-cost point estimate, high uncertainty

Interpretation:
- continue prospective collection
- do not scale capital
- do not claim stable alpha

### Outcome D — Persistent frozen prospective after-cost edge

Requirements:
- market-relative predictive improvement
- positive after-cost PnL
- survives frozen prospective testing
- survives reasonable execution assumptions
- not concentrated in one event / city / regime
- sufficient visible liquidity / capacity

Only then consider tiny-capital live validation.

---

## 12. Development Roadmap

### Stage 1 — V1 Daily Maximum Temperature
Focus:
- contract-rule audit
- point-in-time market data
- station-calibrated weather probabilities
- Market-only vs Market+Weather
- fixed decision time
- taker-style execution assumptions
- frozen prospective testing

### Stage 2 — Intraday Updating
Add:

$$
P(T_{\max} \mid \text{forecast + live observed trajectory})
$$

Possible information:
- observed temperature path
- cloud development
- wind
- dew point
- model-vs-observation residual
- frontal timing

Goal:
- test whether live observations produce incremental information before the market fully reprices

### Stage 3 — Forecast Revision / Information Timing
Study:

$$
\Delta p_{\text{weather forecast}}
\rightarrow
\Delta p_{\text{market}}
$$

Goal:
- measure how quickly market prices incorporate new public forecasts

### Stage 4 — Daily Rainfall
Possible focus:
- station-specific measurable precipitation
- radar movement and decay
- short-term PoP updating
- MRMS / station mismatch
- remaining settlement-window probability

### Stage 5 — Passive Execution / Market Making
Only after predictive edge is established.

Research:
- limit-order fills
- adverse selection
- queue position
- spread capture
- inventory risk

---

## 13. Application Value

The project should not be framed as “I built a trading bot.”

The research contribution is:

$$
\text{meteorological information}
\rightarrow
\text{probabilistic forecast}
\rightarrow
\text{market price}
\rightarrow
\text{cost-adjusted decision}
$$

The incremental skills relative to the existing portfolio are:

- market microstructure
- point-in-time data engineering
- economic evaluation
- execution-aware modeling
- decision under uncertainty
- prospective / frozen trading validation

Potential research title:

> **Incremental Predictive and Economic Value of Public Meteorological Signals in Weather Prediction Markets**

or:

> **From Weather Forecasts to Market Prices: Out-of-Sample Evaluation of Probabilistic and Economic Value**

---

## 14. Money-Making Interpretation

At project start, profitability is **unknown**.

The correct goal is not:

> “Build a profitable weather strategy.”

The correct goal is:

> **Build an experiment rigorous enough to determine whether a real, repeatable, after-cost trading edge exists.**

The research has asymmetric value:

$$
\text{No alpha}
\Rightarrow
\text{useful research project}
$$

$$
\text{Predictive edge but no PnL}
\Rightarrow
\text{strong market-efficiency result}
$$

$$
\text{Persistent after-cost prospective alpha}
\Rightarrow
\text{research project + potential own-capital deployment}
$$

Whether the project can actually make money must be decided by the final frozen prospective evidence, not by the attractiveness of the idea.

---

## 15. Before Any Real-Money Deployment

Before live trading:

- verify current platform eligibility
- verify current state / jurisdiction rules
- verify F-1 / own-account activity implications as needed
- begin with very small capital
- compare simulated and realized execution
- verify actual fills, latency, fees, and settlement behavior
- never scale based on historical backtest alone

The first live-money objective should be:

$$
\text{modeled PnL} \approx \text{realized PnL}
$$

not maximizing dollar profit.
