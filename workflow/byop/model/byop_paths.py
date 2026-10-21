"""Single source of file locations for the BYOP project code inside pypsa-usa (restructure 2026-10-20).

    pypsa-usa/workflow/
      byop/model/    executed model code (v250_mech, v240_mech, v240_path, wp2_ercot_s0_s1, wp2_ercot_s1_real)
      byop/build/    executed builders (county 2025 baseline, ITL calibration LP, audits)
      byop/post/     executed collectors
      byop/run/      L2 run scripts
      byop/inputs/   runtime inputs = key parameters (tracked in git)
      data/byop/     raw public data read by the builders (not tracked)
      results/BYOP/  all BYOP outputs: baselines, calibrations, case results (not tracked; small files synced)

All scripts are run with the working directory pypsa-usa/workflow (PyPSA-USA modules are imported from ./scripts).
"""
from pathlib import Path

MODEL = Path(__file__).resolve().parent
BYOP = MODEL.parent
WORKFLOW = BYOP.parent
INPUTS = BYOP / 'inputs'
DATA = WORKFLOW / 'data' / 'byop'
RESULTS = WORKFLOW / 'results' / 'BYOP'

# runtime inputs (provenance: inputs/README.md)
TECH = INPUTS / 'tech/TECH-01_technologies_DRAFT.csv'
PUE = INPUTS / 'dc/state_pue_2022_2050.csv'
TASK = INPUTS / 'dc/yearly_task_parameters_2022_2050.csv'
TRACE = INPUTS / 'dc/hourly_inference_trace.csv'
DC_TOTALS = INPUTS / 'dc/ERCOT_DC_TOTALS_2026_2035.csv'               # approved Texas DC IT trajectory, low/mid/high (DATA-01, DATA-03A)
DC_COHORTS_TAMU64 = INPUTS / 'dc/ercot_cohorts_2026_2035_tamu64.csv'  # totals on TAMU64 buses, Epoch AI geography (RA-DC-SPATIAL-03)
# PNNL-based 7-zone and county cohorts were deleted (RA-DC-SPATIAL-04, 2026-10-21); the v240 / v250 / WP2 runs that read
# them need a new spatial basis before they can run again
COHORTS_7ZONE = None
COHORTS_COUNTY = None
BG_LOAD_GROWTH = INPUTS / 'load/background_load_growth_states_AEO2023_reference.csv'
TPIT_MAP = INPUTS / 'grid/TPIT_TO_COUNTY_ASSET_MAP.csv'

# generated baselines (results)
BASE_7ZONE = RESULTS / 'baseline_2025_7zone/baseline_2025_prepared.nc'
BASE_COUNTY = RESULTS / 'baseline_2025_county/baseline_2025_county_prepared.nc'

# raw data for the builders
REEDS = DATA / 'reeds_inputs'
NATIVE_LOAD = DATA / 'ercot_native_load/Native_Load_2025.xlsx'
