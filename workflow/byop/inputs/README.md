# BYOP runtime inputs (key parameters, tracked)

Copied 2026-10-20 from the work packages (now in D:\BYOP_impact\work_pkgs, local only). The producing scripts are preprocessing and stay in work_pkgs; re-generate there and copy here.

| File | Source (work_pkgs/...) | Producer | SHA-256 |
|---|---|---|---|
| `tech/TECH-01_technologies_DRAFT.csv` | `work_package_v2/decisions/TECH-01_technologies_DRAFT.csv` | TECH-01 decision table (researcher-approved draft) | `127e5a97b5177eb4…` |
| `dc/state_pue_2022_2050.csv` | `work_package_v2/outputs/input_audit/pue/state_pue_2022_2050.csv` | build_post2035_state_pue.py (DATA-05) | `28c4da9100277205…` |
| `dc/yearly_task_parameters_2022_2050.csv` | `work_package_v2/outputs/input_audit/workload/yearly_task_parameters_2022_2050.csv` | build_yearly_task_parameters.py + build_post2035_task_mix.py (TASK-01/02) | `1206faa69dd9f468…` |
| `dc/hourly_inference_trace.csv` | `work_package_v2/data/researcher/hourly_inference_trace.csv` | researcher input (TASK-01) | `b282e1a142899f5a…` |
| `dc/ercot_cohorts_2026_2035.csv` | `work_package_v2/outputs/spatial/ercot_8s/ercot_cohorts_2026_2035.csv` | build_ercot_cohorts.py (DATA-01/03, 7-zone) | `b038ecfb48fbb05c…` |
| `dc/ercot_cohorts_2026_2035_county.csv` | `BYOP_ERCOT_County_v2.5.0/data/derived/ercot_cohorts_2026_2035_county.csv` | build_county_cohorts.py (D250-05) | `248ebb2055c69ac8…` |
| `load/background_load_growth_states_AEO2023_reference.csv` | `BYOP_ERCOT_Mechanism_Repair_v2.4.0/data/background_load_growth_states_AEO2023_reference.csv` | build_bg_load_growth.py (LOAD-GROWTH-03) | `8fc098183b479520…` |
| `grid/TPIT_TO_COUNTY_ASSET_MAP.csv` | `BYOP_ERCOT_County_v2.5.0/data/derived/TPIT_TO_COUNTY_ASSET_MAP.csv` | build_tpit_register.py (RUN-2, D250-09/12) | `3fd0a742d241479a…` |
| `grid/TPIT_2026-07-13_project_register_v250.csv` | `BYOP_ERCOT_County_v2.5.0/data/derived/TPIT_2026-07-13_project_register_v250.csv` | build_tpit_register.py (RUN-2) | `b7697cc9d57ed153…` |

## ERCOT data-center growth on the TAMU 64s backbone

- **2026-10-21: the PNNL-based allocation was withdrawn by the researcher (RA-DC-SPATIAL-02).** All PNNL-derived files were removed: `PNNL_*_TAMU64.*`, `ercot_cohorts_2026_2035_tamu64.csv`, `ERCOT_DC_CAPACITY_ALLOCATION_TAMU64.csv` and the `results/BYOP/dc_allocation` map. The raw PNNL data was also removed from `work_pkgs`.
- The new spatial basis will be Epoch AI "AI data centers" (CC-BY-4.0, retrieved 2026-10-21; raw data local only, under `work_pkgs/BYOP_ERCOT_Rearchitecture_Work_Package/epoch_ai/raw/`). The allocation option is pending the researcher's choice.
- `rearch_mech.py --regional-dc` stays off until the new allocation file exists.
