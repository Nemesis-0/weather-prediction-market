# V3 Study 2 — Frozen fast economic kill protocol

Protocol ID:
`v3_study2_economic_kill_frozen_2026-10-07_r1`

This protocol is frozen **before the fresh market session used for economic
screening is captured**.

## Scientific purpose

Test whether the already-frozen weather probability survives:
- an actual fresh displayed executable ask;
- verified transaction fees;
- a pre-frozen execution reserve;
- the frozen probability-calibration envelope.

This stage does not authorize trading.

## Frozen accounting

ForecastEx correct payout: `$1.00`.

Verified IBKR/ForecastEx fee schedule on 2026-10-07:
- IBKR commission: `$0.00 / contract`;
- ForecastEx exchange fee passed through by IBKR: `$0.01 / contract`.

Official fee source:
`https://www.interactivebrokers.com/en/pricing/commissions-events.php`

Execution reserve:
`$0.01 / contract` (one price tick).

Funding/carry reserve:
`$0.00 / contract` for this short-horizon fast screen.

Important: zero funding/carry reserve is a **convention**, not a claim that zero
is intrinsically conservative. Positive incentive/coupon economics are entirely
excluded from the screen.

Frozen total cost:
`$0.02 / contract`.

For the frozen weather probability interval `[q_L, q_U]`:

YES:
`g_yes = q_L - ask_yes - 0.02`

NO:
`g_no = (1 - q_U) - ask_no - 0.02`

`1 - q_L` is forbidden for NO.

The NO ask must be the actual displayed NO ask. It must not be synthesized as
`1 - ask_yes`.

## Fresh executable quote requirements

A screened quote row must:
- come from a capture session that started after the economic protocol code was
  committed;
- have `delivery = real_time`;
- have top-of-book availability;
- have a numeric ask strictly inside `(0,1)`;
- have positive displayed ask size.

No midpoint is used.

## Prospective weather-state timing

For a quote at time `t`, only weather observations whose source response had
actually been received by `t` may enter the state.

For corrected reports sharing an original METAR issue time, the latest version
received by `t` is used. A correction first received after `t` cannot leak
backward.

The state reproduces the frozen M0 semantics:
- current/latest temperature;
- running observed maximum;
- current minus running maximum;
- latest observation age;
- latest as-of observation at or before `t-60m` for the ~60-minute change.

## Frozen support/calibration rules

The already-committed support policy is applied without change:
- month x local-time weather-state support;
- 1st-99th percentile state support ranges;
- observation age limit;
- threshold-delta range;
- q_hat range;
- 6-hour-block x q-bin calibration slack.

Unsupported rows remain `MODEL_DATA_INSUFFICIENT`.

## Decision interpretation

For every supported executable row, compute the conservative margin.

If `g <= 0`:
`NONPOSITIVE_CONSERVATIVE_MARGIN`.

If `g > 0`:
`APPARENT_POSITIVE_CONSERVATIVE_MARGIN_GATE3_REQUIRED`.

A positive row is **not** an authorization to trade and is not yet a claim of
executable alpha. The protocol must stop for Sol Max Gate #3.

If a fresh session has no positive rows:
`NO_POSITIVE_MARGIN_IN_THIS_FRESH_SESSION`.

A single negative session does not by itself establish a universal
`ECONOMIC_KILL` over all future dates/times. Continue bounded prospective
read-only screening under the same frozen protocol unless an independently
pre-specified stopping rule is reached.

## Market-selection risk

The frozen support policy's market-selection warning remains active.

A weather-only probability does not automatically identify
`P(Y | weather, selected because ask looked cheap)`.

Therefore:
- positive margin triggers Gate #3, not trading;
- no post-hoc support/model retuning is allowed;
- all screened quote rows are retained, not only favorable rows.

## Guardrails

No:
- M0 retuning;
- support-policy retuning;
- midpoint substitution;
- candidate sizing;
- order submission;
- live-money authorization.


## Quote-eligibility correction — 2026-10-07

Correction ID:
`v3_study2_quote_eligibility_fix_2026-10-07_r1`

The first post-freeze fresh session was used only to discover an engineering
eligibility blocker. It produced zero economic-margin rows because the
evaluator incorrectly required `availability_decoded.top_of_book = true` and
attempted to parse IBKR ask sizes such as `"7,520"` directly as Python floats.

The schema-only diagnostic established:
- all 440 quote rows had real-time delivery;
- exactly 220 rows carried displayed ask + ask_size fields;
- ask-side rows were one-sided in the normalized contract record, so the
  decoder's `top_of_book` flag remained false;
- ask sizes use grouping commas.

No economic margin was computed before this correction.

Corrected buy-ask eligibility is therefore:
- real-time delivery;
- broker `field_presence.ask = true`;
- broker `field_presence.ask_size = true`;
- numeric displayed ask in `(0,1)`;
- positive ask size after removing grouping commas.

The `top_of_book` decoder flag remains archived as diagnostic metadata but is
not an eligibility requirement for a one-sided displayed buy ask.

No accounting, M0, support, calibration, fee, reserve, or decision formula is
changed.

To avoid using prices already observed during blocker discovery as confirmatory
economic evidence, the 2026-10-07 `20261008T002914Z_postfreeze` session is
classified as **engineering/blocker-discovery only**. The first admissible
economic screen after this correction must use a new capture session beginning
after the correction commit.
