# V2 H2.2 Residual Assimilation Protocol

## Status

REVISED PRE-RESULT FROZEN SPECIFICATION.

This revision was made before inspection of any valid directional H2.2
result, following an independent adversarial methodological review.

The previous specification is archived as superseded.

V1 remains CLOSED.

All 46 historical dates are V2 historical-development data, not an
untouched holdout.

Definitive V2 confirmation, if pursued, requires future observations
collected after a later V2 Final Freeze.

---

## Research question

After a public NBM/NBS TXN/XND forecast revision becomes available, is
second-hour Kalshi repricing directionally associated with the original
weather revision?

H2.2 is an information-assimilation event study.

It is NOT:

- a settlement-accuracy test
- a trading test
- a PnL test
- proof of executable alpha
- proof of causal market inefficiency

Because H2.1 did not establish a reliable first-hour response, a positive
H2.2 result must be described as evidence of:

    second-hour directional association

or, cautiously:

    delayed assimilation

It must NOT be described as continued assimilation after a demonstrated
initial response.

---

## Event population

The H2.2 historical-development population consists of isolated weather
revisions with complete clean PRE / POST1H / POST2H market observations.

An event must satisfy all of the following:

1. `any_weather_change == True`
2. `clean_pre_post1h == True`
3. `clean_pre_post2h == True`
4. valid sequential old/new public forecast states
5. exact six-bucket synchronized Kalshi market vectors at PRE, POST1H,
   and POST2H
6. no later public weather revision contaminating the applicable POST
   windows under the frozen alignment rules

Structural feasibility work identifies:

    179 events

This is a structural data-availability population and must not be changed
based on H2.2 performance.

No settlement result, realized winner, outcome variable, executable trade
price, fee, realized trade result, or PnL field may enter H2.2 construction
or estimation.

---

## Weather revision vector

For event i, construct old and new weather-implied six-bucket
probability vectors:

    q_old_i
    q_new_i

using exactly the frozen V1 weather-proxy transformation:

    Normal(TXN, XND^2)

with the same half-degree latent bucket cutpoints and `bucket_mass`
semantics used in V1.

Define:

    delta_q_i = q_new_i - q_old_i

No market information may enter construction of `delta_q_i`.

---

## Market probability vectors

At each aligned market snapshot, obtain the synchronized six-bucket
midpoint vector:

    m_pre_i
    m_post1_i
    m_post2_i

Because six raw bucket midpoints need not sum to one, normalize each
snapshot independently:

    p_t_i = m_t_i / sum(m_t_i)

for:

    t in {PRE, POST1, POST2}

The same six market tickers, bucket definitions, and ordering must be used
at all three snapshots.

Define:

    delta_p_initial_i
        = p_post1_i - p_pre_i

    delta_p_residual_i
        = p_post2_i - p_post1_i

---

## PRIMARY estimand

The confirmatory H2.2 estimand is the unadjusted residual projection:

    beta_residual
        =
        sum_i [ delta_q_i' delta_p_residual_i ]
        /
        sum_i [ ||delta_q_i||^2 ]

Interpretation:

A positive `beta_residual` means that second-hour market repricing is, on
average, directionally associated with the original public weather-proxy
revision.

This is an associational historical-development statistic.

It is not a causal effect.

---

## PRIMARY inference

Primary uncertainty uses a date-preserving moving-block bootstrap.

Primary block length:

    3 calendar dates

Sensitivity block lengths:

    1 calendar date
    7 calendar dates

All cities, transitions, revision events, and six bucket coordinates
belonging to a sampled calendar date move together.

For each bootstrap replicate, recompute the complete primary
`beta_residual` statistic.

Use:

    10,000 bootstrap replicates
    random seed = 20260930

Report percentile 95% confidence intervals.

---

## PRIMARY success criterion

Reliable historical-development evidence of second-hour directional
association requires BOTH:

1. `beta_residual > 0`
2. the primary 3-day bootstrap 95% confidence interval excludes zero on
   the positive side

If the primary 3-day interval includes zero, H2.2 does not establish
reliable residual directional association.

The 1-day and 7-day block results are sensitivity analyses and cannot
override the primary 3-day conclusion.

No subgroup, transition, city, or alternative timing window may replace
the primary analysis based on observed performance.

---

## SECONDARY diagnostic: adjusted regression

The previously proposed conditional regression is retained only as a
secondary diagnostic:

    delta_p_residual_ij
        =
        beta_weather_adjusted * delta_q_ij
        +
        gamma_initial * delta_p_initial_ij
        +
        error_ij

with no intercept.

Important limitation:

`delta_p_initial` is a post-weather-revision market-response variable.

It also shares the POST1 endpoint with `delta_p_residual`:

    delta_p_initial = POST1 - PRE

    delta_p_residual = POST2 - POST1

Therefore POST1 quote, midpoint, and microstructure measurement error can
mechanically induce covariance between the control and outcome.

For this reason:

- `beta_weather_adjusted` is diagnostic only
- it cannot replace the primary H2.2 estimand
- it cannot override the primary H2.2 conclusion
- disagreement between the primary and adjusted result must be disclosed,
  not resolved by choosing the more favorable result

---

## Descriptive initial-response comparison

For scale comparison only, report:

    beta_initial_same_population
        =
        sum_i [ delta_q_i' delta_p_initial_i ]
        /
        sum_i [ ||delta_q_i||^2 ]

This uses the same 179-event H2.2 population.

It is descriptive only.

Do NOT infer assimilation decay merely because
`beta_initial_same_population` and `beta_residual` differ.

No direct statistical comparison between them is confirmatory unless
separately pre-specified before result inspection.

---

## Descriptive subgroup analysis

By-city and by-transition estimates may be reported descriptively only.

They are not independent confirmatory tests.

They cannot redefine the primary claim.

---

## Market-snapshot implementation requirements

Before computing the valid directional H2.2 result, mechanically verify
the market-event alignment implementation.

The audit must confirm:

1. PRE contains no market information after the relevant weather
   publication boundary.

2. POST1 and POST2 use the intended frozen event-time endpoints and
   tolerance rules.

3. All six bucket values inside each market vector are constructed under
   the same synchronized timestamp rule.

4. No later public weather revision contaminates the relevant POST1 or
   POST2 window.

5. The same event, six markets, and bucket ordering are used consistently
   across PRE, POST1, and POST2.

This implementation audit must inspect only market-event alignment and
snapshot-selection mechanics.

It must not reopen or retune the broader V2 hypothesis design.

---

## Interpretation restrictions

H2.2 alone cannot establish:

- profitable trading
- executable alpha
- settlement forecasting superiority
- realized fill quality
- scalable capacity
- causal market inefficiency

A positive H2.2 result would remain historical-development evidence.

Economic analysis, if ever pursued, is a later and separately frozen
stage.

---

## Integrity rule

No valid directional H2.2 result may be computed or inspected until:

1. this revised specification is frozen and hashed;
2. the frozen market-event alignment implementation has passed the
   mechanical timing/synchronization audit.

No further confirmatory specification change may be made in response to
the eventual sign, magnitude, or significance of H2.2.


---

# Astra-required final pre-result additions

## Actual event-time offsets

For the frozen 179-event H2.2 population, actual market snapshot offsets
relative to the verified weather publication time are:

PRE:
- mean: -32.90 minutes
- median: -35.03 minutes
- range: -56.32 to -3.78 minutes

POST1:
- mean: +87.10 minutes
- median: +84.97 minutes
- range: +63.68 to +116.22 minutes

POST2:
- mean: +147.10 minutes
- median: +144.97 minutes
- range: +123.68 to +176.22 minutes

Therefore the primary H2.2 outcome must NOT be described literally as
"minutes 60-120 after publication."

The confirmatory historical claim is limited to:

    later-window post-publication directional association

between the frozen NBM proxy revision and the recorded Kalshi market
movement.

The design does not identify the exact intra-hour timing of repricing.

---

## Claim boundary

The primary hypothesis concerns association between:

    delta_q

the frozen NBM TXN/XND proxy-implied six-bucket revision,

and:

    delta_p_later = p_POST2 - p_POST1

the later recorded normalized Kalshi market-vector change.

A positive result does NOT by itself establish:

- publication-caused repricing
- delayed causal assimilation
- incomplete market efficiency
- incremental information beyond everything traders already knew
- executable alpha
- profitable trading

The strongest allowed historical interpretation is:

    evidence of post-publication later-window directional association

under the frozen event-selection and measurement rules.

---

## Falsification diagnostic 1:
## exact pre-publication placebo

For each H2.2 event, define:

    PLACEBO_START = PRE - 60 minutes

The placebo market change is:

    delta_p_placebo
        =
        p_PRE
        -
        p_PLACEBO_START

using the same independent six-bucket midpoint normalization rule as the
primary market vectors.

Eligibility requires an exact complete synchronized six-bucket market
snapshot at PRE - 60 minutes.

Availability audit conducted before any directional H2.2 result found:

    174 / 179 events available

The remaining five events are structurally unavailable for this placebo.

Frozen placebo rules:

- placebo population = exactly those 174 structurally available events
- no interpolation
- no nearest-snapshot replacement
- no alternative placebo window
- no dropping additional events based on performance

The placebo directional statistic is:

    beta_placebo
        =
        sum_i [ delta_q_i' delta_p_placebo_i ]
        /
        sum_i [ ||delta_q_i||^2 ]

computed only over the frozen 174-event placebo population.

Inference uses the same date-preserving moving-block bootstrap framework:

- 3-calendar-day blocks primary
- 1-day and 7-day sensitivities
- 10,000 replicates
- seed = 20260930

The placebo is a falsification diagnostic only.

It does not replace or redefine the primary 179-event H2.2 result.

A strong positive placebo association would weaken an interpretation that
the later association is specific to the post-publication period.

---

## Falsification diagnostic 2:
## unnormalized midpoint sensitivity

On the full frozen 179-event primary population, construct raw six-bucket
midpoint vectors:

    m_POST1
    m_POST2

without normalization.

Define:

    delta_m_later
        =
        m_POST2
        -
        m_POST1

and report:

    beta_raw_midpoint
        =
        sum_i [ delta_q_i' delta_m_later_i ]
        /
        sum_i [ ||delta_q_i||^2 ]

This is a diagnostic only.

It cannot replace the normalized primary statistic.

Use the same 3-day primary moving-block bootstrap and 1-day / 7-day
sensitivities.

Also report, descriptively:

    midpoint_sum_POST1 = sum_j m_POST1_j
    midpoint_sum_POST2 = sum_j m_POST2_j
    delta_midpoint_sum = midpoint_sum_POST2 - midpoint_sum_POST1

and the six-bucket total quoted spread at POST1 and POST2 when available.

These quantities are reported to assess whether normalization-denominator
or liquidity/spread changes could materially contribute to the observed
directional result.

No significance-based rule will be used to choose between normalized and
unnormalized representations.

Both must be reported regardless of outcome.

---

## Final confirmatory hierarchy

PRIMARY:
- 179-event normalized later-window beta
- 3-day date-preserving moving-block bootstrap 95% CI

SENSITIVITY:
- 1-day and 7-day block bootstrap CIs

FALSIFICATION / DIAGNOSTIC:
- 174-event exact PRE-60min placebo
- 179-event raw-midpoint directional statistic
- midpoint normalization-sum diagnostics
- spread/liquidity diagnostics
- adjusted shared-POST1 regression, if reported, remains secondary only

No diagnostic may replace the primary result.

No further confirmatory specification changes may be made after the first
valid H2.2 directional result is computed.


---

## Final bootstrap implementation clarification

The moving-block bootstrap operates on the COMPLETE fixed 46-calendar-day
historical study calendar, not only on dates containing eligible events.

For any calendar date with no eligible events for the statistic being
bootstrapped, that date contributes:

    numerator = 0
    denominator = 0
    event_count = 0

before block resampling.

Therefore a 3-day block always represents three genuinely consecutive
calendar dates and cannot bridge across a zero-event date.

Within every bootstrap replicate:

    beta*
        =
        sum(sampled date numerators)
        /
        sum(sampled date denominators)

whenever the sampled denominator is positive.

This clarification does not change:
- the 179-event primary population,
- the 174-event placebo population,
- the primary statistic,
- any weather or market vector,
- block lengths,
- bootstrap replicate count,
- random seed,
- success criterion.

It is an implementation clarification made before inspection of any valid
directional H2.2 result.
