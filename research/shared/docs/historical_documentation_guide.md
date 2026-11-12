# Documentation Guide

This repository contains two closed historical studies (V1/V2), a prospective
V3 program with preserved protocol history, and a final 2026-10-08 domain-level
allocation decision.

## Canonical project states

| Version / layer | Final status | Canonical entry point |
|---|---|---|
| V1 - Static Weather Information | **CLOSED** | [`../results/final_v1/V1_FINAL_CLOSURE.md`](../../v1/results/final/V1_FINAL_CLOSURE.md) |
| V2 - Forecast Revision / Assimilation | **CLOSED** | [`../results/final_v2/V2_FINAL_CLOSURE.md`](../../v2/results/final/V2_FINAL_CLOSURE.md) |
| V3 Study 1 - Structural Consistency | **DEFERRED PRE-D0 / confirmatory study not run** | [`v3/study1_final_frozen_protocol.md`](../../v3/docs/study1_final_frozen_protocol.md) |
| V3 Study 2 - Settlement-Aware Nowcasting | **CLOSED / ECONOMIC KILL** | [`v3/study2_closure.md`](../../v3/docs/study2_closure.md) |
| Weather alpha domain | **FOREGROUND RETIRED / PASSIVE-WATCH ONLY** | [`v3/weather_alpha_domain_closure_20261008.md`](../../v3/docs/weather_alpha_domain_closure_20261008.md) |

The Git tag `v1-v2-closed-2026-10-02` identifies the pre-V3 historical closure
state. V1/V2 remain closed to timing-window search, subgroup rescue, post-hoc
trading thresholds, and other specification search.

## Recommended reading order

For a short review of the research program:

1. [`v3/weather_alpha_domain_closure_20261008.md`](../../v3/docs/weather_alpha_domain_closure_20261008.md)
2. [`../results/final_v1/V1_FINAL_CLOSURE.md`](../../v1/results/final/V1_FINAL_CLOSURE.md)
3. [`../results/final_v2/V2_FINAL_CLOSURE.md`](../../v2/results/final/V2_FINAL_CLOSURE.md)
4. [`v3/study2_closure.md`](../../v3/docs/study2_closure.md)
5. [`v3/study1_final_frozen_protocol.md`](../../v3/docs/study1_final_frozen_protocol.md)
6. [`research_protocol.md`](research_protocol.md)

## Historical V1/V2 documentation

Historical protocols and audits retain their underlying evidence and immutable
freeze history; their repository paths were mechanically relocated in 2026-11-12.
Consult the migration ledger for old-to-new paths. Important records
include:

- [`research_protocol.md`](research_protocol.md)
- [`pre_weather_freeze.md`](../../v1/docs/pre_weather_freeze.md)
- [`model_specification_pre_weather_results.md`](../../v1/docs/model_specification_pre_weather_results.md)
- [`v1_point_in_time_implementation_audit.md`](../../v1/docs/v1_point_in_time_implementation_audit.md)
- [`v1_source_timing_correction_protocol.md`](../../v1/docs/v1_source_timing_correction_protocol.md)
- [`v2_hypothesis_design.md`](../../v2/docs/v2_hypothesis_design.md)
- [`v2_market_reaction_protocol.md`](../../v2/docs/v2_market_reaction_protocol.md)
- [`v2_h2_2_residual_assimilation_protocol.md`](../../v2/docs/v2_h2_2_residual_assimilation_protocol.md)

These files are historical scientific records. They should not be rewritten
merely to make old status language look current.

Some frozen V1 records retain references to a local pre-correction archive used
during timing correction. That archive is not distributed in the final public
repository; the tracked post-correction audits and final V1 closure are the
canonical public record.

## V3 documentation

Canonical V3 records now include:

- [`v3/weather_alpha_domain_closure_20261008.md`](../../v3/docs/weather_alpha_domain_closure_20261008.md) - final domain-level allocation decision.
- [`v3/study2_closure.md`](../../v3/docs/study2_closure.md) - current M0 settlement-aware route closure.
- Static structural/timing screening is summarized in the final domain closure; detailed alpha-funnel working checkpoints remain in the local/private research workspace and are not part of the public repository.
- [`v3/study1_final_frozen_protocol.md`](../../v3/docs/study1_final_frozen_protocol.md) - final pre-D0 Study 1 protocol; confirmatory collection never started.
- [`v3/research_charter.md`](../../v3/docs/research_charter.md) - historical V3 governance charter; superseded for current status by the final domain closure.
- [`v3/api_capability_audit.md`](../../v3/docs/api_capability_audit.md) - infrastructure audit retained for reproducibility.

Pre-freeze, remediation, acceptance, and adversarial-review documents are kept as
provenance but are not recommended as first-entry reading for the project. Some frozen
Study 1 records preserve the historical internal label `Sol Max`; in this public closeout,
that label should be read simply as an independent adversarial review checkpoint. Original freeze manifests are not rewritten. Some document hyperlinks were mechanically
retargeted; the migration ledger records which bytes changed.

## Result and data guides

- [`../results/README.md`](historical_results_guide.md) - canonical result policy.
- [`../data/README.md`](../../../DATA_POLICY.md) - historical reconstruction and prospective-data policy.

## Provenance rule

Historical code, protocols, manifests, and closure artifacts are preserved when
they are necessary to understand the specification history. Current-status
navigation lives in the root README and the final domain closure rather than by
rewriting every historical document.
