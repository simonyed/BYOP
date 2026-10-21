# BYOP runtime inputs (key parameters, tracked)

Copied 2026-10-20 from the work packages (now in D:\BYOP_impact\work_pkgs, local only). The producing scripts are preprocessing and stay in work_pkgs; re-generate there and copy here.

| File | Source (work_pkgs/...) | Producer | SHA-256 |
|---|---|---|---|
| `tech/TECH-01_technologies_DRAFT.csv` | `work_package_v2/decisions/TECH-01_technologies_DRAFT.csv` | TECH-01 decision table (researcher-approved draft) | `127e5a97b5177eb4…` |
| `dc/state_pue_2022_2050.csv` | `work_package_v2/outputs/input_audit/pue/state_pue_2022_2050.csv` | build_post2035_state_pue.py (DATA-05) | `28c4da9100277205…` |
| `dc/yearly_task_parameters_2022_2050.csv` | `work_package_v2/outputs/input_audit/workload/yearly_task_parameters_2022_2050.csv` | build_yearly_task_parameters.py + build_post2035_task_mix.py (TASK-01/02) | `1206faa69dd9f468…` |
| `dc/hourly_inference_trace.csv` | `work_package_v2/data/researcher/hourly_inference_trace.csv` | researcher input (TASK-01) | `b282e1a142899f5a…` |
| `load/background_load_growth_states_AEO2023_reference.csv` | `BYOP_ERCOT_Mechanism_Repair_v2.4.0/data/background_load_growth_states_AEO2023_reference.csv` | build_bg_load_growth.py (LOAD-GROWTH-03) | `8fc098183b479520…` |
| `grid/TPIT_TO_COUNTY_ASSET_MAP.csv` | `BYOP_ERCOT_County_v2.5.0/data/derived/TPIT_TO_COUNTY_ASSET_MAP.csv` | build_tpit_register.py (RUN-2, D250-09/12) | `3fd0a742d241479a…` |
| `grid/TPIT_2026-07-13_project_register_v250.csv` | `BYOP_ERCOT_County_v2.5.0/data/derived/TPIT_2026-07-13_project_register_v250.csv` | build_tpit_register.py (RUN-2) | `b7697cc9d57ed153…` |

## ERCOT data-center growth on the TAMU 64s backbone (RA-DC-SPATIAL-03, 2026-10-21)

**Rule (researcher decision, option C with exact totals).**
- Total new IT MW per scenario and year = the approved Texas trajectory (`dc/ERCOT_DC_TOTALS_2026_2035.csv`, low/mid/high; 2035 cumulative 3,347 / 5,029 / 6,747 MW). This is exactly equal every year.
- Geography and order come from Epoch AI:
  - Each ERCOT Epoch site's IT power added after 2025 forms a queue by Epoch year. IT online by 2025-12-31 is stock, already in the 2025 native load.
  - Each year's new total first serves the queue (oldest Epoch year first, pro rata within a year, never earlier than the Epoch date). The remainder is residual growth, split over the Epoch buses by their share of the total Epoch post-2025 increment.
  - Every bus is non-decreasing.
- Result: 8 buses (p630 4 Shackelford, p610 2 Abilene, p600 0 Dickens, p630 9 Denton, p650 0 San Antonio, p630 6 Midlothian, p630 2 Red Oak, p630 5 Temple).
- Goodnight (Armstrong County) is outside ERCOT and excluded.
- The 3 representative test POIs are not included.

**Source.** Epoch AI, "AI data centers", https://epoch.ai/data/ai-data-centers, CC-BY-4.0, retrieved 2026-10-21. The raw zip and CSVs are local only, under `work_pkgs/BYOP_ERCOT_Rearchitecture_Work_Package/epoch_ai/raw/`. The producer is `epoch_ai/build_epoch_tamu_allocation.py` (work_pkgs).

**Geocoding.** Epoch gives only street addresses, so each was geocoded in turn:
1. US Census onelineaddress (address level, 4 sites);
2. OSM Nominatim (road level, 5 sites);
3. ZIP or county-centroid fallback (3 sites: Microsoft SAT40 by ZIP, Stargate Shackelford and Goodnight by county).

Each site's precision is in `geocode_precision`. A site maps to the nearest ERCOT TAMU substation and then to its 64s cluster bus.

| File | Content | SHA-256 |
|---|---|---|
| `dc/ERCOT_DC_TOTALS_2026_2035.csv` | approved Texas DC IT trajectory (new and cumulative IT MW per scenario and year = national IT x researcher Texas share; DATA-01, DATA-03A; no spatial split). Extracted 2026-10-21 from the former 7-zone cohort file, whose PNNL zone split was deleted (RA-DC-SPATIAL-04) | `ad9264672f9300f2…` |
| `dc/ERCOT_DC_CAPACITY_ALLOCATION_TAMU64.csv` | **bus x year allocation** (8 buses, 2026-2035, low/mid/high): new IT MW split into Epoch-queue and residual parts, cumulative IT MW, TX PUE, cumulative facility MW, bus coordinates, Epoch sites, counties, increment share | `fa145e17423095ee…` |
| `dc/ercot_cohorts_2026_2035_tamu64.csv` | the same allocation in cohort format, read by `rearch_mech.py --regional-dc epoch_hybrid` | `47de6d5e675839b0…` |
| `dc/EPOCH_TX_SITES_TAMU64.csv` | 12 Texas Epoch sites: address, geocode and precision, county, ERCOT flag, bus, year-end IT MW 2025-2035 from the Epoch timeline | `8c6dc5fb690eed91…` |
| `dc/EPOCH_SITE_SERVICE_TAMU64.csv` | audit trail: per scenario, year and site, how much of the Epoch queue was served, and the delay versus the Epoch date | `d93d5e34f2352b2a…` |
| `dc/EPOCH_TAMU64_PROVENANCE.json` | source, licence, raw-file hashes, geocoders, excluded sites | `f36c266f311139b5…` |

Model use is opt-in: `--regional-dc epoch_hybrid --regional-dc-scenario {low|mid|high}`, default `off`. All PNNL data was withdrawn and deleted on 2026-10-21 (RA-DC-SPATIAL-02/04). The legacy v240 / v250 / WP2 models that read the deleted 7-zone and county cohorts now stop with a message.
