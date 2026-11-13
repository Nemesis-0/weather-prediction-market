# V1 — Does static weather information improve market probabilities?

**Study status:** CLOSED · **Setting:** historical Kalshi daily-high-temperature markets · **Final scientific record:** [V1 Final Closure](results/final/V1_FINAL_CLOSURE.md)

## Question and contribution

At **10:00 AM local time**, does publicly available NOAA/NBM `TXN`/`XND` forecast information provide **incremental predictive or economic value** beyond the probability distribution already implied by the Kalshi market?

This is an incremental-information experiment, not a general test of the value of numerical weather prediction. The central comparison is **M2 (Market + Weather) vs. M0 (Market-only)**, evaluated at a fixed information time with a fixed model family.

## Research design

| Element | Frozen specification |
|:--|:--|
| Markets | Daily maximum-temperature, six mutually exclusive ordered buckets |
| Cities | New York City, Chicago, Denver |
| Historical coverage | 46 dates; 138 city-day events; 828 bucket contracts |
| Decision time | 10:00 AM **local** per market |
| Statistical unit | One six-outcome city-day; all six buckets modeled jointly |
| Primary metric | Multiclass log loss, summarized by calendar date |
| Secondary metric | Multiclass Brier score |
| Model-selection procedure | Rolling-origin development, common L2 grid, no evaluation-data tuning |
| Economic checks | Frozen historical trade-selection/cost rules and adverse-execution scenarios |
| Uncertainty | Date-aware moving-block bootstrap; primary 3-day blocks |

### Features and models

Let $m_{ij}$ be the normalized market midpoint probability for bucket $j$ of city-day $i$, and let $w_{ij}$ be a weather-derived proxy probability.

The proxy transforms NBM `TXN` and `XND` into six bucket masses using a latent Gaussian CDF. This is a **feature-engineering proxy**, not a claim about the true settlement distribution.

The fitted logits share ordered-bucket intercepts and an L2-regularized conditional-softmax architecture:

- **M0 — Market-only:** bucket intercept + coefficient on `log(market probability)`.
- **M1 — Weather-only:** bucket intercept + coefficient on `log(weather proxy probability)`.
- **M2 — Market + Weather:** both terms, with the same model family.

The common regularization grid was `0.001, 0.01, 0.1, 1, 10`. Development used rolling-origin fitting on earlier dates and next-date prediction; the final evaluation was not used for model selection.

**Frozen specification:** [Predictive Model Specification](docs/model_specification_pre_weather_results.md) · [Development Protocol](docs/historical_development_protocol.md) · [Historical Evaluation Protocol](docs/historical_holdout_freeze.md)

### Publication-time validity

A source-backed NOAA publication-timing census identified **four observations** for which the initially selected forecast was not publicly available before the frozen 10:00 AM decision time. Each was replaced mechanically with the latest source-verified available forecast; cities, dates, model family, selection grid, scoring and execution rules remained unchanged.

The final record reports **zero remaining weather-availability violations** and **zero future market-snapshot violations** across 138 city-days. The corrected 15-date period is termed **corrected historical evaluation**, **not an untouched holdout**, because the original outcomes had previously been inspected.

[Timing correction protocol](docs/v1_source_timing_correction_protocol.md) · [Point-in-time implementation audit](docs/v1_point_in_time_implementation_audit.md)

## Results

### Corrected historical predictive comparison

| Model | Multiclass log loss | Role |
|:--|--:|:--|
| M0 | `1.0115` | Fitted market baseline |
| M1 | `1.5413` | Weather proxy only |
| M2 | `1.0259` | Market and weather proxy |
| Raw normalized market | `0.9752` | Descriptive market-price comparator |

Primary contrast: **M2 − M0 calendar-date mean log-loss difference = `+0.0144`**; 3-day moving-block bootstrap **95% CI `[-0.0376, +0.0863]`**. Negative would favor M2. The interval crosses zero, so the experiment did not establish incremental predictive value from the static weather proxy.

### Corrected historical economic comparison

| Scenario | M0 total PnL | M2 total PnL |
|:--|--:|--:|
| Frozen baseline historical evaluation | `+$0.42` | `+$0.48` |
| One-cent adverse execution | About `$0.00` | `+$0.05` |
| Two-cent adverse execution | `−$0.42` | `−$0.37` |

The baseline **M2 − M0 PnL difference was only `+$0.06` total**, and the date-block uncertainty around the economic difference included zero. These simulated historical execution scenarios are **not evidence of actual fills or live profitability**.

## Interpretation

**The corrected, frozen V1 specification did not establish reliable incremental predictive or economic value from static NBM `TXN`/`XND` information beyond the 10:00 AM market state in this sample.**

This is a limited negative result; it does not show that all public weather information is useless, that other models cannot work, or that all prediction markets are efficient. No post-result tuning was used to rescue the study.

## Research artifacts

| Resource | Location |
|:--|:--|
| Final conclusion and manifest | [V1 closure](results/final/V1_FINAL_CLOSURE.md) · [freeze manifest](results/final/V1_FINAL_MANIFEST.txt) |
| Model specification | [Frozen conditional-softmax specification](docs/model_specification_pre_weather_results.md) |
| Timing and information validity | [Source timing correction](docs/v1_source_timing_correction_protocol.md) · [timing audit](results/audits/) |
| Predictive and economic code | [Modeling and evaluation code](code/modeling/) |
| Additional original methods | [V1 protocols](docs/) |
| Published final tables | [Final results](results/final/) |

**Reproduction boundary:** original raw market and NOAA archives are not publicly redistributed. The tracked repository provides scientific protocols, code and final audit/result outputs; see the [Data Policy](../../DATA_POLICY.md).

[← Project overview](../../README.md) · [Research index](../README.md)
