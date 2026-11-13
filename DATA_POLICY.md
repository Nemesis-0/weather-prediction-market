# Data sources, provenance and reproducibility

This repository publishes **research code, protocols, frozen study records, selected final tables and integrity checks**, but not the full historical raw-market/weather archives or private brokerage runtime data.

## Sources by study

| Study | Market data | Non-market information | Reproducibility boundary |
|:--|:--|:--|:--|
| V1 | Historical Kalshi daily-maximum-temperature six-bucket contracts | NOAA/NBM NBS `TXN` / `XND`; source-verified publication timing | The 46-date public results and protocols are retained; full raw archives are not included |
| V2 | Historical Kalshi hourly market candles | Sequential NOAA/NBM revisions with source-backed release times | Published event metrics, summary tables and frozen protocols are retained; full source archives are not included |
| V3 | Prospective IBKR / ForecastEx contract metadata and observed quotes | Settlement specifications and available settlement-relevant weather state | Read-only source code, audit documents, schemas and deterministic tests are public; broker sessions and raw runtime streams are not |

## Point-in-time information integrity

A scientific statement about a market decision depends on what was knowable **at that moment**. In this project that requires attention to:

- The difference between nominal weather-model cycle time and **demonstrated public publication time**.
- The difference between market candle timestamps, broker update timestamps, local receive timestamps and verified exchange time.
- The precise contract identity, settlement site/source, threshold, comparator, event date, and payout/cancellation rules.
- Missing data, stale/delayed quotes, order-book availability and mismatched observation windows.
- Explicitly preserving original observations; not silently replacing historical inputs with information learned later.

In V1, a publication-timing audit resulted in the documented mechanical correction of four weather inputs. The final corrected evaluation is **not described as an untouched holdout**. [Read the final V1 closure](research/v1/results/final/V1_FINAL_CLOSURE.md).

In V3, settlement information already observable at the decision time invalidated most of one model's apparent positive candidates. [Read the V3 Study 2 closure](research/v3/docs/study2_closure.md).

## Reconstruction code and public outputs

- [Kalshi market-data collection and panel code](research/shared/code/market/)
- [NBM weather-data processing](research/shared/code/weather/)
- [Shared historical feature assembly](research/shared/code/modeling/)
- [V1 point-in-time auditing](research/v1/code/audit/) and [final tables](research/v1/results/final/)
- [V2 revision-event code](research/v2/code/) and [final closure](research/v2/results/final/V2_FINAL_CLOSURE.md)
- [V3 IBKR/ForecastEx modules](research/v3/code/), [schemas](research/v3/schemas/) and [tests](research/v3/tests/)

The original source datasets are not fully redistributed, and some archived freeze manifests refer to local artifacts that are not present in the public Git tree. Thus **a successful deterministic test run is not proof that the full historical V1/V2 analysis has been reproduced from its raw inputs**.

## Sensitive information and local data

Local `.venv/`, `data/`, `runtime/`, `local_artifacts/` and similar working directories may exist on the research machine without being tracked by Git. Raw broker responses, session state and personal account information are intentionally excluded from the public repository.

The project does not publish credentials, tokens, account or financial identifiers, tax or identity records, or residential addresses. The public code and schemas support auditability without disclosing these private runtime materials.

The [original scientific research protocols](research/shared/docs/research_protocol.md) and [version-specific conclusions](research/README.md) remain the authority for each historical experiment's scope. Subsequent versions must label new hypotheses and data as new work rather than retroactively changing a closed result.
