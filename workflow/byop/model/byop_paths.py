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
import os
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
REEDS_GENDB = REEDS / 'capacity_exogenous/ReEDS_generator_database_final_EIA-NEMS.csv'

# C0 ERCOT 2025 official anchor (work package v1.3, 2026-10-22): official raw files (data/byop, local + L2, not git),
# extracted small tables (inputs, tracked) and the C0 audit outputs
ANCHOR2025 = DATA / 'ercot_official_anchor_2025'
ANCHOR2025_RAW = ANCHOR2025 / 'raw'
ANCHOR2025_MANIFEST = ANCHOR2025 / 'SOURCE_MANIFEST.json'
ANCHOR2025_DERIVED = INPUTS / 'anchor2025'
BASE_TAMU_DIR = RESULTS / 'baseline_2025_tamu'
C0_RESULTS = RESULTS / 'C0_ANCHOR_2025'                 # C0 v1.3 snapshot (kept unchanged)
C0_REPAIR_RESULTS = RESULTS / 'C0_REPAIR_V14'           # C0 repair (prompt v1.4)
C1_RESULTS = RESULTS / 'C1_FIXED_ASSET_DIAG'            # C1 fixed-asset dispatch diagnostics (prompt v1.4)

# calibration close-out v1.6 (2026-10-22): asset decisions + evidence (tracked), official raw files (data/byop), new baseline
CALIB_V16_INPUTS = INPUTS / 'calibration_v16'
CALIB_V16_EVIDENCE = CALIB_V16_INPUTS / 'evidence'
CALIB_V16_RAW = DATA / 'calibration_closeout_v16/raw'
BASE_TAMU_V16_DIR = RESULTS / 'baseline_2025_tamu_v16'
BASE_TAMU_V16 = BASE_TAMU_V16_DIR / 'baseline_2025_tamu_prepared.nc'
BASE_TAMU_V16_SHA256 = 'a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16'   # v1.6 report 0b417903

# NEXT-09 (2026-10-23): v1.7L lossy 2025 baseline = byte copy of the NEXT-08b LP1 v3 candidate (byop/build/freeze_baseline_v17l.py);
# formal only once config/config.byop_baseline_registry.yaml says ADOPTED (byop/model/baseline_registry.py)
BASE_TAMU_V17L_DIR = RESULTS / 'baseline_2025_tamu_v17_lossy'
BASE_TAMU_V17L = BASE_TAMU_V17L_DIR / 'baseline_2025_tamu_v17_lossy_prepared.nc'
BASE_TAMU_V17L_SHA256 = 'f9aa87aea496f7c07ea4aca0439a703e7eaa90d08cb66c5bc6f149ea60eeefb6'   # NEXT-08b v3 seal (LOSSY_LP1_V3_SEAL.json)

# post-v1.6 execution package v1.1 (2026-10-22): staged research data (raw local + L2 only; derived tracked) and A0/A1 outputs
POST_V16_PACKAGE = WORKFLOW.parent / 'current_work_pckg/_completed/BYOP_Post_v1.6_Execution_v1.1_A0/BYOP_Post_v1.6_Execution_v1.1'
POST_V16_RAW = DATA / 'post_v16_execution_v11/raw'
POST_V16_INPUTS = INPUTS / 'post_v16'
POST_V16_DERIVED = POST_V16_INPUTS / 'derived'
POST_V16_RESULTS = RESULTS / 'POST_V16_A1_HEADROOM'

# optional raw sources outside the repository: set by environment variable, never a personal drive letter in code
_env = lambda k: Path(os.environ[k]) if os.environ.get(k) else None
EPOCH_TIMELINE_RAW = _env('BYOP_EPOCH_TIMELINE_RAW')     # Epoch AI data_center_timelines.csv (refreshes the tracked extract)
REEDS2_ROOT = _env('BYOP_REEDS2_ROOT')                   # local ReEDS2 checkout (build_reeds2_potential.py)
