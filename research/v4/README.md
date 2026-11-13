# V4 — Live Market Research & Online Learning

**Status:** Gate 0 (scientific design) **GO / CLOSED** as reported in the owner's 2026-11-12 Solmax final-review screenshot. **Gateway access, live predictions and manual-trade readiness are not approved.** This directory contains the approved *design baseline* and offline verification only.

V4 studies how information beyond contemporaneously available market prices affects the accuracy and economic executability of real-world event forecasts. It is an independent new study; V1–V3 research and conclusions remain closed.

## Research design

- **Market unit:** stable underlying outcome event with linked contracts, resolution versions and correlated dependence blocks; YES/NO complements are not separate Brier samples.
- **Primary comparison:** pre-registered, forward-issued paired event-weighted Brier difference for a fixed adaptive update policy versus the canonical market baseline M0.
- **Time legality:** inputs available before the predeclared as-of cutoff; issuance timestamp separately recorded; binding settlement labels enter only when received and ingest-ready before the *appropriate* scoring or training cutoff.
- **Updates:** frequent predictions and daily candidate refits are permitted. Champion promotion requires separately protected prospective evidence under the registered look policy.
- **Execution boundary:** no paper-trading phase, no programmatic order submission; human-only decisions after G2 and G3, initially <= USD 1.00 all-in per purchased contract. A suggested manual order requires a crash-durable exposure reservation before display.
- **Audit:** preserve every scan disposition and issued prediction, including no-trade and missing-data cases. Publish only permission-approved records; retain protected source/broker evidence in a backed-up private archive.

The detailed normative design is stored **verbatim** under [`docs/gate0/`](docs/gate0/). Those reviewed files retain their original candidate-era titles and headers for byte-exact provenance; the later GO status is recorded separately in [`docs/G0_CLOSURE.md`](docs/G0_CLOSURE.md). **Do not interpret G0 closure as authorization for live trading.**

## Reading order

1. [Research protocol](docs/gate0/01_V4_RESEARCH_PROTOCOL_REVISED.md)
2. [Normative amendments A1–A6](docs/gate0/07_G0_NORMATIVE_AMENDMENTS.md)
3. [Engineering and data contract](docs/gate0/02_V4_ENGINEERING_DATA_CONTRACT_REVISED.md)
4. [Acceptance matrix](docs/gate0/08_G0_ACCEPTANCE_MATRIX.md)
5. [Review gates](docs/gate0/03_SOLMAX_REVIEW_GATES_REVISED.md)
6. [Closure record and remaining gate prerequisites](docs/G0_CLOSURE.md)

## Offline verification (works without ZIP, Internet or IBKR login)

```bash
python3 research/v4/verify_g0.py
python3 -m pytest -q -p no:cacheprovider
python3 research/reorganization_verify.py
```

**No live Gateway entrypoint is shipped at this stage.** The next deliverable is a separately reviewed, strictly allowlisted read-only G1 probe. No order-routing code is included in this design package.
