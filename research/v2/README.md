# V2 — Do public forecast revisions predict market repricing?

**Study status:** CLOSED · **Setting:** historical Kalshi weather-market reactions to NOAA/NBM revisions · **Canonical record:** [V2 Final Closure](results/final/V2_FINAL_CLOSURE.md)

## Question and contribution

V1 did not establish reliable incremental value for a static morning weather proxy. V2 asks a **different** question: **are newly published forecast revisions followed by systematic market-price movements in the direction of the revision?**

The object of inference is a **directional association** between *a predefined weather-proxy revision vector* and *a later observed market-probability change*. It is not a causal measurement of market efficiency or proof of an executable strategy.

## Historical reconstruction

| Component | Description |
|:--|:--|
| Venues and geography | Kalshi six-bucket daily-high-temperature contracts, NYC / Chicago / Denver |
| Weather data | NOAA/NBM NBS `TXN` and `XND`, with source-supported publication times |
| Market data | Historical 60-minute candle snapshots mapped to six normalized probability buckets |
| Calendar | 46 consecutive dates |
| Reconstructed weather states | **552** |
| Sequential revision pairs | **414** |
| Pairs changing `TXN` and/or `XND` | **220** |

Forecast cycles were **not** assumed to become public at nominal initialization time. The event study used source-backed availability and synchronized market snapshots.

## Hypothesis and estimator

For event $i$, the weather revision is $\Delta q_i=q_{\mathrm{new},i}-q_{\mathrm{old},i}$, where each $q$ is a six-bucket weather-proxy vector computed using the *V1-frozen* transformation. A later normalized Kalshi midpoint movement $\Delta p_i$ is projected onto this direction:

$$
\widehat\beta=\frac{\sum_i \Delta q_i^\top\Delta p_i}{\sum_i\|\Delta q_i\|^2}.
$$

A positive estimate indicates price movement aligned with the weather revision in the chosen observation window. It is not itself a trading return.

## Two separately specified tests

### H2.1 — First recorded post-publication response

- **Population:** 196 clean weather-changing revision events.
- **Outcome:** normalized six-bucket probability-vector change between the frozen pre-publication state and the first recorded eligible post-publication state.
- **Estimate:** `β = +0.029570`.
- **Primary 3-day moving-block bootstrap 95% CI:** `[-0.012251, +0.084617]`.
- **Result:** no reliable positive first-window response established.

[Market-reaction study protocol](docs/v2_market_reaction_protocol.md) · [Published metrics](results/market_reaction/)

### H2.2 — Later-window directional association

- **Population:** 179 events across 45 dates containing eligible events, analyzed within a fixed 46-calendar-day bootstrap calendar.
- **Weather signal:** revision vector $\Delta q$ constructed without looking at market outcomes.
- **Primary outcome:** `p_POST2 − p_POST1`—the later observed market movement, *not* the immediate pre-to-post change.
- **Estimate:** `β = −0.02813775`.
- **Primary 3-day moving-block bootstrap 95% CI:** `[-0.07276015, +0.03359751]`.
- **Result:** no reliable positive later-window association; the negative estimate does not establish a reversal.

The first- and later-window tests are not interchangeable, and H2.2's endpoint was fixed before valid result inspection.

[H2.2 frozen protocol](docs/v2_h2_2_residual_assimilation_protocol.md) · [Final H2.2 numerical summary](results/residual_assimilation/final_h22/V2_H2_2_FINAL_SUMMARY.txt)

## Falsification and sensitivity checks

| Diagnostic | Estimate | 3-day 95% CI | Why it matters |
|:--|--:|:--|:--|
| Exact pre-publication placebo | `−0.01851410` | `[-0.06127073, +0.01472115]` | Tests whether directional movement is already present before the eligible study window |
| Unnormalized raw-midpoint later-window projection | `−0.02898768` | `[-0.07426099, +0.03362353]` | Checks that the result is not driven by per-snapshot probability normalization |

Further diagnostics examined spread/price-mass changes, time offsets, date concentration, and 1-/7-day alternative bootstrap blocks. These were interpretation checks, **not alternate primary estimands**.

### Important timing limitation

Because the historical market source uses **60-minute candles**, POST1 and POST2 cannot be read as exact +60 and +120 minute quotes. H2.2's recorded POST1 median offset was approximately **+85 minutes**, and POST2's approximately **+145 minutes** from source-backed publication times.

The scientifically accurate phrase is **later-window post-publication directional association**—not a claim of identified minute-by-minute delay or causal information assimilation.

## Final conclusion

The historical sample did not support a reliable first-window or later-window directional association from the frozen forecast-revision proxy. The hypothesis was **closed rather than re-specified to search favorable cities, cycles, windows or trading thresholds**. V2 did not proceed to a post-hoc historical trading strategy.

## Research artifacts

| Resource | Location |
|:--|:--|
| Final scientific interpretation | [Canonical V2 closure](results/final/V2_FINAL_CLOSURE.md) |
| Conceptual hypothesis | [Hypothesis design](docs/v2_hypothesis_design.md) |
| Data/timing feasibility | [Feasibility protocol](docs/v2_feasibility_protocol.md) · [Feasibility results](results/feasibility/) |
| H2.1 test | [Market reaction protocol](docs/v2_market_reaction_protocol.md) · [Results](results/market_reaction/) |
| H2.2 test | [Residual-assimilation protocol](docs/v2_h2_2_residual_assimilation_protocol.md) · [Results and freeze records](results/residual_assimilation/) |
| Code | [Study scripts](code/) |

**Reproduction boundary:** historical market/weather raw data are not distributed; all public result tables and frozen historical protocols are retained. See [Data Policy](../../DATA_POLICY.md).

[← Project overview](../../README.md) · [Research index](../README.md)
