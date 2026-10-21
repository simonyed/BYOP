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

## PNNL data-center geography on the TAMU 64s backbone (added 2026-10-21)

Producer: `work_pkgs/BYOP_ERCOT_Rearchitecture_Work_Package/pnnl_spatial/build_pnnl_tamu_weights.py` (raw PNNL data local only under `pnnl_spatial/raw/`).
Sources: IM3 Open Source Data Center Atlas v2026.02.09 (existing facilities, OSM-derived, ODbL 1.0, DOI 10.57931/3017294; CSV sha256 `53d200d8111c…`, GPKG `1c0d8c206eb2…`) and IM3 Projected US Data Center Locations v1.1 (20 growth x market-gravity scenarios, CC-BY-4.0, DOI 10.57931/3020186). Mapping: site point -> county -> nearest ERCOT TAMU substation -> 64s cluster bus (`results/BYOP/baseline_2025_tamu/NETWORK_MAPPING_AUDIT.csv`). Full hashes in `dc/PNNL_TAMU64_PROVENANCE.json`.

| File | Content | SHA-256 |
|---|---|---|
| `dc/PNNL_SITES_TAMU64.csv` | every de-duplicated existing facility / projected site with county, ERCOT flag, bus, zone, distance, weight | `312d6686dcdc76b9…` |
| `dc/PNNL_BUS_WEIGHTS_TAMU64.csv` | bus weights per source x scenario (share of ERCOT, share within reeds_zone) | `9e6776c01ed0c21f…` |
| `dc/PNNL_CONCENTRATION_TAMU64.csv` | concentration per source x scenario (counties, buses, top-1/top-3 bus share, HHI) | `c74ca0ddcff0e17c…` |
| `dc/ercot_cohorts_2026_2035_tamu64.csv` | `ercot_cohorts_2026_2035.csv` on TAMU buses: `spatial_basis=projected_moderate50` MAIN (approved zone totals, within-zone split by projected moderate/50 sites, DATA-03B); `existing_atlas` SENSITIVITY (ERCOT total per year split by existing footprint; changes the zone split, needs approval) | `3efb8bf6b88771ad…` |
| `dc/PNNL_TAMU64_PROVENANCE.json` | versions, DOIs, licences, raw-file hashes, de-duplication counts | `3991da50dbc2ae8c…` |

Rules: the existing atlas has no MW field. Its footprint (sqft) is used only as a relative spatial weight and is never converted to IT MW. Campus/building overlap and county-straddling duplicate rows are removed. The 4 bare points use the median Texas building footprint as a labelled proxy. Model use is opt-in: `rearch_mech.py --regional-dc {off|projected_moderate50|existing_atlas} --regional-dc-scenario {low|mid|high}`, default `off`. The cohorts are added as background facility load (cumulative IT x PUE), with their own load_shed generator protected by no-harm. They are not study requests. Two points still need researcher decisions: the aggregate-POI equipment assumption, and the overlap with the 3 representative POIs (currently added on top).
