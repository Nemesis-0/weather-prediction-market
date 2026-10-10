# V2 Final Closure — Weather Forecast Revision / Market Assimilation Study

## Status

**CLOSED**

V2 is closed as a completed historical-development study.

No additional historical analysis is required for scientific closure.

The frozen historical sample must not be reopened, retuned, subset-searched,
or extended in order to obtain statistical significance or trading
profitability.

---

# 1. Research question

V2 studied whether public NOAA/NBM forecast revisions were followed by
directional repricing in Kalshi daily maximum-temperature markets.

The central question was not whether weather forecasts are useful in general,
nor whether Kalshi markets are globally efficient.

The frozen historical question was narrower:

> Do publicly released NBM TXN/XND forecast revisions show a reliable
> directional association with subsequent Kalshi six-bucket market movement
> under the pre-specified historical event-study design?

Markets:

- NYC
- Chicago
- Denver

Market structure:

- six mutually exclusive daily maximum-temperature buckets
- historical 60-minute Kalshi candles

Weather signal:

- NOAA/NBM NBS TXN/XND
- source-backed publication timestamps
- frozen V1 Normal(TXN, XND^2) six-bucket probability proxy

---

# 2. Historical data reconstruction

The historical V2 reconstruction produced:

- 46 consecutive calendar dates
- 552 usable forecast states
- 414 sequential forecast-revision pairs
- 220 revisions where TXN and/or XND changed

The V2 analysis used source-backed NOAA publication timing rather than nominal
model-cycle assumptions.

---

# 3. H2.1 — first recorded post-publication directional response

Primary H2.1 population:

- 196 clean weather-changing revision events

Estimator:

    beta_1h
      =
      sum_i(delta_q_i' delta_p_i)
      /
      sum_i(||delta_q_i||^2)

where:

    delta_q_i

is the frozen weather-proxy probability revision and:

    delta_p_i

is the first recorded post-publication normalized Kalshi probability-vector
change.

Final H2.1 result:

    beta_1h = +0.029570

Primary 3-day moving-block bootstrap 95% CI:

    [-0.012251, +0.084617]

Sensitivity:

    1-day CI = [-0.019013, +0.088790]

    7-day CI = [-0.000426, +0.074220]

Positive-dot fraction:

    0.520

Interpretation:

H2.1 did not establish a reliable first-window directional market response to
the frozen NBM proxy revision.

The positive point estimate is insufficient to establish assimilation,
market inefficiency, tradeability, or alpha.

---

# 4. H2.2 — later-window post-publication directional association

## 4.1 Frozen population

The final H2.2 primary population contained:

- 179 events
- 45 dates with at least one eligible event
- complete fixed 46-calendar-day bootstrap calendar

By city:

- Chicago: 63
- Denver: 60
- NYC: 56

By transition:

- prev18Z->00Z: 50
- 00Z->06Z: 51
- 06Z->12Z: 78

All PRE, POST1, and POST2 six-bucket snapshots passed the frozen mechanical
timing and synchronization audit.

---

## 4.2 Frozen H2.2 signal

The weather revision vector was constructed strictly as:

    delta_q
      =
      q_new - q_old

where q_old and q_new were generated only from:

- old TXN
- old XND
- new TXN
- new XND

using the V1-frozen weather-proxy bucket transform.

Market PRE/POST movement was not used to define the weather direction.

---

## 4.3 Frozen H2.2 primary estimand

The primary market outcome was:

    delta_p_later
      =
      p_POST2 - p_POST1

The primary estimator was:

    beta_later
      =
      sum_i(delta_q_i' delta_p_later_i)
      /
      sum_i(||delta_q_i||^2)

The prior adjusted shared-POST1 regression was demoted before valid result
inspection because POST1 appears in both the initial and later market changes.

The unadjusted projection above became the confirmatory primary statistic.

---

# 5. H2.2 final result

Primary normalized later-window result:

    beta_later = -0.02813775

Positive-dot fraction:

    0.464

Zero-dot events:

    0

Primary 3-day moving-block bootstrap 95% CI:

    [-0.07276015, +0.03359751]

Sensitivity:

    1-day CI = [-0.07969537, +0.02178450]

    7-day CI = [-0.07177623, +0.03309736]

Interpretation:

The frozen historical H2.2 design did not establish a reliable positive
later-window directional association.

The negative point estimate must not be interpreted as evidence of a reliable
negative or reversal effect because all pre-specified confidence intervals
include zero and positive effects.

---

# 6. Mandatory falsification and diagnostic analyses

## 6.1 Exact pre-publication placebo

An exact one-hour pre-PRE placebo interval was frozen before valid H2.2 result
inspection.

Exact synchronized placebo-start snapshots were structurally available for:

    174 / 179 events

No interpolation, nearest-snapshot replacement, or alternative window was
permitted.

Result:

    beta_placebo = -0.01851410

Primary 3-day 95% CI:

    [-0.06127073, +0.01472115]

Sensitivity:

    1-day CI = [-0.05872353, +0.01967436]

    7-day CI = [-0.05585465, +0.01123688]

Interpretation:

The placebo did not establish a reliable pre-publication directional
association and does not alter the primary H2.2 null interpretation.

---

## 6.2 Raw-midpoint diagnostic

The primary analysis normalized each six-bucket midpoint vector independently
to sum to one.

A mandatory frozen diagnostic repeated the directional projection using raw,
unnormalized midpoint changes:

    delta_m_later
      =
      m_POST2 - m_POST1

Result:

    beta_raw_midpoint = -0.02898768

Primary 3-day 95% CI:

    [-0.07426099, +0.03362353]

Sensitivity:

    1-day CI = [-0.08295631, +0.02146754]

    7-day CI = [-0.07616479, +0.03271995]

The raw-midpoint estimate is extremely close to the normalized primary
estimate.

Therefore the primary null / weak-negative point estimate is not plausibly
explained by the probability-normalization step.

---

## 6.3 Market-structure diagnostics

Mean change in total six-bucket midpoint sum:

    +0.001369

Median:

    0.000000

Mean change in total quoted spread:

    +0.002961

Median:

    0.000000

These diagnostics do not indicate an obvious normalization-denominator or
aggregate spread artifact capable of explaining the H2.2 result.

---

# 7. Denominator concentration

Frozen H2.2 denominator-contribution diagnostics:

    maximum single-date share = 0.0714

    top-5 date share = 0.2585

    denominator HHI = 0.0315

    effective denominator dates = 31.76

No single date dominates the result sufficiently to require additional
analysis before closure.

---

# 8. Timing limitation

Because the historical market source consists of 60-minute candles, POST1 and
POST2 are not literal +60 and +120 minute observations.

Observed offsets relative to source-backed weather publication times were:

PRE:

    mean   = -32.90 minutes
    median = -35.03 minutes
    range  = -56.32 to -3.78 minutes

POST1:

    mean   = +87.10 minutes
    median = +84.97 minutes
    range  = +63.68 to +116.22 minutes

POST2:

    mean   = +147.10 minutes
    median = +144.97 minutes
    range  = +123.68 to +176.22 minutes

Therefore the correct estimand description is:

> later-window post-publication directional association

and not:

> exact 60–120 minute delayed assimilation.

The historical candle data cannot identify exact intra-hour repricing timing.

---

# 9. Combined V2 conclusion

H2.1 did not establish a reliable first-window directional response.

H2.2 did not establish a reliable later-window directional association.

Therefore the final V2 conclusion is:

> **The historical V2 results do not provide reliable evidence of a stable
> delayed directional assimilation pattern for this frozen NBM proxy and
> hourly-market-data design.**

This is a null / unsupported result.

It is not evidence of a reliable negative or reversal effect.

---

# 10. Claim boundary

V2 does NOT establish that:

- Kalshi weather markets are generally efficient
- public weather information never matters
- NBM forecast revisions have negative economic value
- no richer meteorological signal can outperform market prices
- no faster information-processing strategy can work
- no profitable prediction-market strategy exists
- exact publication timing has no market impact

V2 tests only the frozen historical design described above.

---

# 11. Descriptive subgroup results

By-city and by-transition estimates remain descriptive only.

No subgroup may redefine the primary V2 conclusion.

In particular, the positive prev18Z->00Z point estimate is not a new
confirmatory result.

No additional historical city, transition, timing-window, or event-subset
search will be conducted to rescue significance.

---

# 12. Economic / trading analysis

A historical H3 trading analysis is not required for closure of V2.

Because the frozen historical information-assimilation hypothesis was not
reliably supported, V2 will not be extended with post-hoc:

- trading thresholds
- holding-period selection
- executable-side optimization
- city selection
- transition selection
- timing-window selection

solely to search for historical profitability.

Any future executable-alpha study must be treated as a new, separately frozen
research design.

Preferably it should use prospective and higher-resolution market data.

---

# 13. Independent adversarial review

After the H2.2 result and all mandatory diagnostics were frozen, an independent
post-result adversarial methodological review was conducted.

Final verdict:

    A — scientifically close H2.2 / V2 as currently interpreted.

The review found:

- the revised primary estimand scientifically acceptable
- the moving-block bootstrap structure acceptable for the limited claim
- the null interpretation appropriate
- no mandatory additional analysis before closure
- subgroup rescue analysis inappropriate
- historical H3 economics unnecessary for V2 closure

---

# 14. Research-integrity rule

V2 is permanently closed.

The frozen historical sample will not be reopened or retuned based on the
observed results.

The workflow followed was:

    plausible hypothesis
        ->
    pre-result specification
        ->
    point-in-time reconstruction
        ->
    implementation audit
        ->
    adversarial review
        ->
    frozen test
        ->
    mandatory falsification diagnostics
        ->
    independent post-result review
        ->
    scientific closure

The null result is retained as the valid research result.

---

# FINAL STATUS

**V2 CLOSED**

Final scientific statement:

> Under the frozen historical V2 specification, public NBM TXN/XND forecast
> revisions did not show reliable evidence of a stable delayed directional
> assimilation pattern in NYC, Chicago, and Denver Kalshi daily
> maximum-temperature markets using hourly market data.

Future work, if undertaken, must begin as a new study rather than as a rescue
analysis of V2.
