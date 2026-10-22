# Post-v1.6 calibration research basis

Start with `CALIBRATION_RESEARCH_MEMO_v0.1.md`.

This is a research/data handoff, **not an execution work package**. It does not
change v1.6, authorize model solves, or open formal scenario gates.

`build_research_data.py` rebuilds all derived data from the supplied official
XLSX files using pandas/openpyxl. No PyPSA or solver is needed.

Key files:

- `derived/ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv`: 8,760 Native Load and
  settlement-generation hour keys, explicitly preserving DST source labels.
- `derived/ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_3H.csv`: 2,920 weighted-compatible rows.
- `derived/PRE_REGISTERED_STRESS_EVENTS.csv` and `WINDOW_*`: event selection and
  complete windows; gross and net summer peaks are on the same calendar day.
- `derived/ERCOT_OPERATIONAL_WIND_SOLAR_2023_2025.csv.gz`: 26,304 supplemental
  operational hours with installed capacity. Do not replace Native Load with
  its different load series without resolving scope and vintage differences.
- `derived/MORA_2025_HOURLY_PERCENTILE_MARGINALS.csv`: 9,647 forecast marginal
  rows. They are neither realized data nor joint probability scenarios.
- `derived/MORA_2025_UNPLANNED_THERMAL_OUTAGE_QUANTILES.csv`: 143 rows; December
  has an extra weather-increment component.
- `derived/CDR_FUTURE_ELCC_2026_2031_REFERENCE.csv`: 720 published coefficients;
  they are not physical hourly availability factors.
- `SOURCE_REGISTRY.csv`, `DATA_GAPS_AND_OWNERSHIP.csv`, `PARAMETER_CANDIDATES.csv`:
  provenance, remaining research-side collection, and provisional policy choices.

All model recommendations remain conditional on the actual v1.6 return.
The archive includes the XLSX files required for reproducibility. Supporting
PDF reports are referenced by their public source URLs and short structured
evidence notes; full reference reports are not reproduced in the archive.
