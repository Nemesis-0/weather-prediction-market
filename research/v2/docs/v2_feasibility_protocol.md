# V2 Historical Feasibility Protocol

Freeze date: 2026-09-30

V1 is permanently closed.

V2 studies forecast revision / information arrival and must remain
scientifically separate from V1.

No V2 settlement-prediction performance, trading performance, or PnL may
be inspected during this feasibility stage.

---

## 1. Primary feasibility question

Can historical NBM/NBS forecast revisions for the same daily Tmax target
be reconstructed with sufficiently precise source-backed publication
timing to support a Kalshi information-arrival event study?

---

## 2. Weather source

Primary forecast values:

    NOAA National Blend of Models
    NBS short-term text bulletin

Parsed IEM data may be used for convenience and cross-checking.

However, NOAA archived NBS objects are the primary provenance source for:

- existence of the cycle,
- historical object publication timestamp,
- direct raw bulletin verification.

For every candidate cycle preserve:

- nominal cycle time UTC,
- NOAA object path,
- NOAA Last-Modified timestamp,
- station,
- event date,
- target valid time,
- TXN,
- XND,
- whether the required target value is present.

---

## 3. Do not assume forecast cadence

Do not assume that every operational NBS hourly cycle supplies the
required TXN/XND value for the target daily Tmax.

Feasibility must mechanically determine which historical cycles actually
contain the relevant target.

A cycle counts as a usable forecast state only if:

1. the NOAA NBS object exists;
2. a source-backed publication timestamp exists;
3. the bulletin contains the required station;
4. the bulletin contains TXN/XND for the intended daily Tmax target;
5. publication occurred before the market state claimed to follow it.

---

## 4. Initial cycle census

For a small prespecified sample of historical dates, inspect all nominal:

    00Z through 23Z

NBS cycles.

Initial dates should include:

- one ordinary August date,
- one ordinary September date,
- 2026-09-24, the known delayed-publication date.

Use all three V1 stations:

- KNYC
- KMDW
- KDEN

This stage examines data availability only.

Do not inspect settlement correctness or model performance.

---

## 5. Revision pair definition

A valid revision pair consists of two sequential usable forecast states
for the same:

- city,
- event date,
- Tmax target.

For states old and new:

    q_old
    q_new

the revision is based on the difference between those forecast states.

The exact V2 feature transformation is NOT frozen yet.

The feasibility audit should first establish the empirical distribution
of time gaps between usable forecast states.

Do not force a 06Z -> 12Z definition if the source data show a different
usable update structure.

---

## 6. Publication timing

For every usable state compute:

    publication_lag =
        NOAA_Last_Modified - nominal_cycle_time

and for sequential states:

    inter_publication_gap =
        publication_time_new - publication_time_old

Historical market-reaction analysis may only use the source-backed
publication timestamp.

Nominal cycle time is insufficient for event-time alignment.

---

## 7. Kalshi feasibility

For each usable new-information event, later feasibility work must test
whether complete synchronized six-bucket market states can be recovered:

PRE:
    latest complete synchronized six-bucket snapshot ending at or before
    the information publication time

POST:
    prespecified later synchronized market state(s)

No future candle may enter PRE.

Do not choose reaction windows using settlement outcomes or PnL.

---

## 8. Feasibility outputs

Before any V2 modeling, report:

- dates examined,
- cities examined,
- nominal cycles examined,
- NOAA objects found,
- usable TXN/XND forecast states,
- usable states by nominal cycle hour,
- publication-lag distribution,
- sequential revision pairs per city-day,
- inter-publication-gap distribution,
- city-days with no revision pair,
- source/parser disagreements,
- missingness reasons.

---

## 9. Feasibility gates

### Gate A — Forecast reconstruction

PASS only if multiple point-in-time forecast states for the same daily
target can be reconstructed on a useful fraction of city-days.

### Gate B — Publication provenance

PASS only if usable states have sufficiently precise source-backed
publication timestamps.

### Gate C — Revision frequency

PASS only if the resulting revision pairs occur often enough to support
a bounded historical event study.

### Gate D — Market alignment

Evaluated after weather feasibility passes.

Must show synchronized market states around enough information events.

---

## 10. Failure interpretation

If hourly or sub-daily TXN/XND revisions cannot be reconstructed reliably,
do not manufacture them.

Possible later redesigns may include other point-in-time forecast
elements or observed-weather innovations, but only as explicitly new V2
hypotheses.

Failure of the TXN/XND revision feasibility gate is not evidence that
weather-market assimilation does not exist.

---

## 11. Data-use restriction

The entire existing 46-date V1 sample is development data for V2.

It may be used for:

- feasibility,
- data engineering,
- event-window design,
- feature design,
- historical development.

It may not be described as an untouched V2 holdout.

Definitive V2 evaluation requires future observations collected after a
V2 Final Freeze.

---

## 12. Current status

V1:

    CLOSED AND ARCHIVED

V2:

    FEASIBILITY ONLY

No V2 predictive or economic result has been inspected.
