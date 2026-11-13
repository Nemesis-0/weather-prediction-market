# V3 — Prospective settlement-aware and executable market mechanisms

**Research state:** weather-focused foreground program CLOSED/RETIRED · Study 1 **deferred before confirmatory collection** · Study 2 observation-only M0 route **closed** · **No demonstrated executable alpha**.

**Canonical interpretation:** [Weather Prediction-Market Alpha Domain Closure (2026-10-08)](docs/weather_alpha_domain_closure_20261008.md)

## Why V3 was different

V1 tested incremental probability prediction; V2 tested historical direction of information assimilation. Neither established a reliable positive effect. V3 therefore asked a more stringent question:

> Can a contract-level signal derived from **prospectively observed market and settlement information** survive exact rule interpretation, simultaneous executable-quote checks, timing uncertainty, fees, and conservative economic screening?

The study used **IBKR / ForecastEx** instrument discovery, quote and settlement-rule auditing, and read-only market observation. This is a different venue/context from the earlier historical Kalshi dataset and **not a record of real executed trades**.

## Data and contract-integrity infrastructure

V3's research pipeline addressed:

1. **Contract identity:** exchange/conid, underlying event, threshold, comparator, trading window, payout and the precise settlement-source definition.
2. **Market state:** broker-observed YES/NO bid/ask, available displayed size, delivery mode and observation time.
3. **Clock semantics:** local wall and monotonic receive times, documented broker timestamps, request latency, stale or delayed feeds, and independent quote alignment.
4. **Economic interpretation:** actual buyable asks and sizes rather than midpoints, explicit fees/reserves, and the distinction between a quote and a realized fill.
5. **Scientific provenance:** frozen configurations, sealed observations, checksums, date-level denominators, and adversarial evidence review.

[IBKR capability audit](docs/api_capability_audit.md) · [Read-only API code](code/ibkr/) · [Public schemas](schemas/)

## Study 1 — Structural consistency across adjacent thresholds

### Hypothesis

For nested daily-high-temperature thresholds, an appropriately selected lower-threshold YES plus higher-threshold NO can have a guaranteed logical payoff **only if** the contract definitions and settlement treatments are truly compatible. Apparent mispricing is irrelevant unless both legs are actually buyable with adequate size and the conservative total cost is below the guaranteed payout.

### Final frozen design

| Dimension | Design |
|:--|:--|
| Universe | Eligible adjacent ForecastEx threshold pairs satisfying semantic constraints |
| Observation protocol | **30-second nominal cadence**, simultaneous two-conid requests within specified sessions |
| Revalidation | Two consecutive globally valid observations of the same pair, 25–35 seconds apart |
| Quote eligibility | Whole-cent executable asks (`$0.01`–`$0.99`) and integer ask size at least 1; structurally invalid feeds excluded |
| Economics | Higher ask across confirmation polls, exchange fees, tick/slippage reserves and conservative funding stress |
| Proposed qualification | Rounded total conservative two-leg cost at most `$0.99` |
| Intended primary endpoint | Fraction of **30 planned dates** with at least one qualifying revalidated basket; date is the unit, not each pair/tick |
| Controls | Pre-D0 protocol freeze, sealed collection, health denominators, result firewall, no post-result rescue |

**Crucial status:** strategy-blind shakedown, remediation, acceptance and final pre-D0 freeze were completed, but **the 30-date confirmatory collection did not begin**. The design above is a preserved *protocol*, **not a set of realized findings**.

[Frozen confirmatory protocol](docs/study1_final_frozen_protocol.md) · [Pre-D0 acceptance](docs/study1_acceptance_pass_2026-10-06.md) · [Implementation](code/study1/)

## Study 2 — Settlement-aware intraday weather nowcasting

### Hypothesis

A point-in-time weather-observation model for **KMDW** might identify a probability difference from executable ForecastEx asks that remains positive after uncertainty and costs.

The first admissible economic screen contained:

| Gate #3 classification | Rows |
|:--|--:|
| Total quote rows | 440 |
| Supported economic rows | 143 |
| Apparent positive conservative-margin rows | 78 |
| Supported nonpositive rows | 65 |
| Model-data-insufficient rows | 77 |
| Invalid executable-quote rows | 220 |

**The decisive finding was a missing variable in the information set.** The current M0 did not condition on the same-day maximum already visible at the weather source relevant to contract settlement. Once this already-known state was included as a *diagnostic blocker*, **76 of 78** apparent positives were invalid as usable edge evidence. The remaining **two diagnostic YES 79°F rows** had a maximum reported margin of only **about $0.001624 per contract**.

The study's original model route was **closed rather than retuned after this result**. The diagnostic overlay was not a new confirmatory strategy and the apparent margins are not realized PnL.

[Study 2 closure](docs/study2_closure.md) · [M0 and evaluation code](code/study2/) · [Historical-data limitations](docs/study2_historical_backfill_contract.md)

## Separate structural and market-mechanics evidence

A subsequent fast structural/timing screen did not produce any **PROMOTE** candidate among the completed deterministic guaranteed-payoff mechanisms. An observed ForecastEx paired-book property also showed that YES and NO top-of-book fields are **mirrored**, rather than freely independent liquidity:

- `Ask_Y + Bid_N = $1.00`
- `Ask_N + Bid_Y = $1.00`

The overnight diagnostic sample recorded **67/67** valid paired observations as mirror-consistent; it was static over a short inactive-window diagnostic. This does not establish that active daytime order books lack opportunities. It does establish why naive YES/NO double-counting is unsafe.

[Detailed public domain closure](docs/weather_alpha_domain_closure_20261008.md)

## Scientific interpretation

V3 found several ways **apparent** opportunity can fail before or after modeling:

- An event outcome can already be constrained by the **official settlement-source state** even if a model based on fewer observations still assigns uncertainty.
- A mirrored YES/NO quote is not a second independent bid/ask queue.
- A mathematically consistent static basket is not a feasible arbitrage if the legs cannot be bought under synchronized, after-cost conditions.
- A protocol completed before D0 is **not** evidence that the confirmatory experiment was run.
- An archived model's past feature support is not automatically a valid point-in-time feature set for a new venue or product.

The weather-focused foreground search was retired on **2026-10-08**, with narrower passive-watch possibilities retained as contingencies. No positive executable-alpha or real-money profitability claim is made.

## Code and reading guide

| Resource | Content |
|:--|:--|
| [Canonical closure](docs/weather_alpha_domain_closure_20261008.md) | Final conclusion across V1/V2/V3 weather mechanisms |
| [Study 1 frozen protocol](docs/study1_final_frozen_protocol.md) | Exact planned structural consistency design, including endpoint and health rules |
| [Study 2 closure](docs/study2_closure.md) | Detailed settlement-state discovery and economic kill |
| [IBKR API audit](docs/api_capability_audit.md) | What the broker interface could and could not establish |
| [V3 read-only CLI](code/cli/) | Capability checks, study collectors and historical research utilities |
| [Research code](code/) · [configurations](configs/) · [schemas](schemas/) · [tests](tests/) | Public implementation and deterministic test coverage |

To run the deterministic suite from the repository root:

```bash
python -m pytest -q research/v3/tests
```

Original private broker sessions, raw streams, source archives, and account material are **not included**. The historical freeze files are preserved, and [Data Policy](../../DATA_POLICY.md) documents the public/private boundary.

[← Project overview](../../README.md) · [Research index](../README.md)
