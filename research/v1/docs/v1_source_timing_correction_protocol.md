# V1 Source-Timing Correction Protocol

Correction date: 2026-09-30

A source-backed NOAA NBM publication-timing census found four V1
city-days for which the originally selected 12Z NBS forecast had not yet
been publicly available at the frozen 10:00 AM local decision time.

Affected observations:

- NYC, 2026-08-31:
  replace 12Z with latest eligible 06Z
- NYC, 2026-09-24:
  replace 12Z with latest eligible previous-day 18Z
- Chicago, 2026-09-24:
  replace 12Z with latest eligible 00Z
- Denver, 2026-09-24:
  replace 12Z with latest eligible 06Z

The correction changes only the point-in-time weather inputs.

The following remain frozen and unchanged:

- cities
- stations
- 10:00 AM local primary decision time
- market snapshots
- bucket definitions
- weather-proxy transformation
- model family
- lambda candidate grid
- rolling-origin selection algorithm
- scoring rules
- economic trade-selection rule
- fee treatment
- execution-stress rules

Because NYC 2026-08-31 is in the development period, the original lambda
selection may have been affected. Therefore lambda selection must be
rerun using the identical pre-specified grid and rolling-origin procedure.

This is correction of contaminated input data, not post-hoc retuning.

Because 2026-09-24 belongs to the previously opened historical holdout,
the corrected historical evaluation must no longer be described as an
untouched holdout. It is a corrected historical evaluation.

The original pre-correction state is preserved at:

    archive/v1_pre_source_timing_correction

All pre-correction downstream V1 results are superseded for final V1
interpretation.
