# Predictive Model Specification — Frozen Before Weather Results

Freeze date: 2026-09-30

No Weather-only or Market+Weather predictive performance had been
examined before this specification was frozen.

## 1. Modeling Unit

One observation is one city-day six-category temperature event.

The six mutually exclusive ordered buckets are modeled jointly.

No bucket row is treated as an independent observation.

---

## 2. Models

### M0 — fitted Market-only

For event i and bucket j:

    eta_ij =
        bucket_rank_intercept_j
        + beta_market * log(market_probability_ij)

Probabilities are obtained by softmax across the six buckets.

### M1 — Weather-only

    eta_ij =
        bucket_rank_intercept_j
        + beta_weather * log(weather_proxy_probability_ij)

### M2 — Market + Weather

    eta_ij =
        bucket_rank_intercept_j
        + beta_market * log(market_probability_ij)
        + beta_weather * log(weather_proxy_probability_ij)

M0 and M2 therefore differ only by the addition of the weather signal.

---

## 3. Bucket-Rank Intercepts

Five free ordered-bucket intercepts are used.

Bucket 1 is the reference intercept and is fixed at zero.

The same intercept structure is available to M0, M1, and M2.

No city-specific or date-specific intercepts are used in V1.

---

## 4. Market Predictor

The market predictor is the previously frozen normalized midpoint
probability from the synchronized primary market snapshot.

For the log transform only:

    probability floor = 1e-6

No executable price is clipped for later economic analysis.

---

## 5. Weather Proxy Predictor

NBM/NBS TXN and XND remain predictors only.

They are NOT interpreted as the true TWC settlement distribution.

For construction of a compact weather-location predictor only, define a
latent Gaussian proxy:

    latent_temperature ~ Normal(TXN, XND^2)

Kalshi integer settlement buckets are mapped to half-degree latent
cutpoints.

Examples:

    63 or below -> (-inf, 63.5)
    64 to 65    -> [63.5, 65.5)
    66 to 67    -> [65.5, 67.5)
    72 or above -> [71.5, +inf)

The Normal CDF mass within each bucket defines:

    weather_proxy_probability_j

The six proxy probabilities are normalized to sum to one.

For the log transform only:

    probability floor = 1e-6

This construction is a feature transformation only. It does not assert
that TWC settlement temperature is normally distributed around TXN with
standard deviation XND.

---

## 6. Regularization

All fitted models use the same L2-regularized conditional-softmax
framework.

Candidate regularization strengths:

    lambda in {0.001, 0.01, 0.1, 1.0, 10.0}

The same candidate grid and optimization procedure are used for M0, M1,
and M2.

Each model selects its lambda using development-period rolling-origin
mean calendar-date multiclass log loss.

No holdout performance may influence lambda selection.

---

## 7. Development Selection

Development dates:

    2026-08-14 through 2026-09-13

Minimum initial fitting window:

    14 calendar dates

Beginning with development date 15:

- fit using all earlier development dates;
- predict all three cities on the next date;
- keep the three cities together;
- repeat sequentially through the end of the development period.

Primary tuning score:

    mean calendar-date multiclass log loss

Secondary descriptive score:

    multiclass Brier score

---

## 8. Historical Holdout

After lambda selection and model specification are complete, each model
is refit using all 31 development dates.

The historical holdout:

    2026-09-14 through 2026-09-28

is then evaluated once.

The primary incremental comparison is:

    M2 versus fitted M0

M1 is a scientific baseline and is not the primary evidence for
market-relative incremental value.

---

## 9. Restrictions

V1 does not add:

- HRRR
- ECMWF
- radar
- neighboring-station shopping
- neural networks
- tree ensembles
- city-specific tuning
- decision-time tuning
- post-hoc feature expansion

Any later expansion must be explicitly labeled as a new exploratory
study and cannot replace this frozen V1 result.

---

## 10. Optimization Details

The fitted objective is:

    mean multiclass negative log likelihood
    + (lambda / 2) * sum(beta^2)

L2 regularization is applied to generic predictor coefficients only:

- beta_market
- beta_weather

Bucket-rank intercepts are not penalized.

This avoids reference-category-dependent shrinkage of the alternative
intercepts.

Optimization is deterministic using L-BFGS-B with:

- zero initialization
- no coefficient bounds
- analytic gradient
- maximum 2000 iterations

If two lambda values have development mean calendar-date log loss within
1e-8, the larger lambda is selected as the deterministic tie-breaker.

No historical-holdout outcomes are used in optimization or lambda
selection.
