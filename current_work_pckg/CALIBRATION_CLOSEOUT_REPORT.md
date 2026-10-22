# CALIBRATION_CLOSEOUT_REPORT: calibration close-out of the common 2025 baseline (work package v1.6)

- Date: 2026-10-22 (New York time). Branch `mainline-v13-stageA`.
- Commits:
  - Start: `55766e31` (package source HEAD). Archive and placement: `027431c2`.
  - **Code: `85cd6ae5`**, committed and pushed before any LP.
  - Report: the commit that contains this file.
- **Solves**: 2 LP stages, 2 actual solver calls, 0 retries (`BASELINE_V16_SOLVE_LOG.csv`).
  - LP1 1,565.6 s; LP2 257.4 s. Both ended with `status == ok` and `termination == optimal` exactly.
  - Solver settings: Gurobi barrier, Crossover 1, BarConvTol 1e-8, NumericFocus 2, BarHomogeneous 1, 20 threads.
- **Network representation**: `fixed_precalibration_xr_thermal_limit_proxy` (X1).
  - x and r are the values in `baseline_2025_tamu_raw_uncalibrated.nc`.
  - The calibration raises only the thermal limit s_nom.
  - There is no capacity–impedance outer iteration.
- **Unchanged**:
  - dynamic_pnnl_v1 siting and future AIDC quantities;
  - the inherited 460.73 MW IT ramp;
  - POI, gas and technology costs;
  - ERM definition and VOLL;
  - the formal gates: every `config.byop_ercot_mainline*.yaml` stays `NOT_APPROVED`.
- **Not run**: S0–S3 and B3. There is no 102.2 MWh fitting, no p630 14 storage follow-up and no MILP.
- **Interpretation boundary**: this is a research calibration of a 64-bus synthetic network with 3 h snapshots.
  - It is not an ERCOT reliability certification, a LOLE/LOLH study, an N-1 study or a 2025 historical replay.
  - The proxy tolerances below are not ERCOT standards.

## 1. Code changes (commit `85cd6ae5`)

| File | Change |
|---|---|
| `workflow/byop/build/baseline_v16_assets.py` (new) | Pure functions: <br>• overrides keyed by ReEDS Unique ID, rejecting a wrong ID, summer MW or technology family; <br>• a check that nothing else changes model set; <br>• the fleet delta; <br>• the source month of each 3 h step (row order of the native-load table); <br>• monthly caps = min(physical, MORA net), asserted equal to the package's `recommended_aggregate_dispatch_cap_MW`. |
| `workflow/byop/build/build_2025_baseline_tamu.py` | v1.6 is the default. Overrides are applied before the active/committed split. Kiamichi and Tenaska Gateway are split into their own plant groups (`plant_group` aggregation key) with p_max_pu(t) = cap_month / p_nom. <br>**Save rule**: s_nom = full LP solution on every line with a positive uplift; x and r are not touched. The 0.5 MVA cut is only the column `shown_in_display_table_gt_0p5MVA`. <br>Output goes to `results/BYOP/baseline_2025_tamu_v16/`, and the builder refuses to write into the pre-v1.6 directory. <br>`--legacy-v15` reproduces the old builder and needs an explicit `--out-dir`. The LP objective and prices are unchanged (2e6 USD/MW uplift, 1e6 USD/MWh shed). |
| `workflow/byop/run/baseline_v16_calibration.py` + `config/config.byop_baseline_v16_calibration.yaml` | Own gate, tied to the SHA-256 of the v1.6 main text; LP1 then LP2, once each; any logged attempt blocks a rerun. <br>Before the LP2 solve, the file reloaded from disk is checked: x/r equal raw, s_nom equals the LP1 solution, caps present. <br>The C1 fixed-asset rules then apply, and the absence of any `*_nom` linopy variable is asserted. |
| `workflow/byop/post/v16_prm_bridge.py`, `v16_transmission_validation.py`, `v16_collect.py` | Anchor 2 and anchor 3 post-processing (no solver); collector. |
| `workflow/byop/tests/test_baseline_v16.py` | Tests: <br>• overrides, duplicate check and rejection cases; <br>• month mapping; <br>• caps; <br>• **ERM credit = p_nom × p_max_pu(t), counted once**, using `scripts/opts/reserves.py` on a test network; <br>• s_nom-only save → reload identity, with an uplift below 0.5 MVA kept; <br>• official PRM reproduction; BESS ELCC interpolation; <br>• gate, budget and formal gates; <br>• post-run QA. |

**Disclosed correction after the run (label only).**
- **What was wrong:** at `85cd6ae5` the 20 `unit` rows of `BASELINE_V16_INPUT_DIFF.csv` had the pandas repr of `Series.item` in their label column `key`, because the builder used `r.item` inside `iterrows`.
- **Fix:** the builder line is fixed in the report commit. `v16_collect.py` rebuilt the labels from `ASSET_OVERRIDE_AUDIT.csv`, checking row order and `cluster_bus`.
- **Record:** SHA-256 before and after are in `BASELINE_V16_INPUT_DIFF_REKEY.json`.
- **Unaffected:** no number, network or LP.

## 2. Anchor 1: actual load and actual installed capacity

**Load.**
- ERCOT Native Load 2025: 488.234 TWh. The model sums to the same value (difference < 1e-6).
- Peak: 1 h 83,679.0 MW (08/18/2025 HE 18); 3 h model peak 83,403.7 MW (2030-08-18 15:00 model label, August 2025 source).
- Load is unchanged by v1.6.

**Assets** (`ASSET_OVERRIDE_AUDIT.csv`, `BASELINE_V16_INPUT_DIFF.csv`). Every decided ReEDS ID was checked for presence, summer MW and technology; the ReEDS source table is not edited.

| Item (ReEDS Unique ID) | Before → after | MW | Bus |
|---|---|---:|---|
| Sequoia 1 (22526), Fagus (21476), Buzios/Roaring Springs (22719), Big Star (18152), La Casa (21249), Long Point (23206) | active 2025 → active 2025 (kept) | 401.4 / 331.6 / 250 / 200 / 150 / 120 | p610 2, p600 0, p600 0, p640 0, p630 4, p670 9 |
| Gaia solar (20535) | active 2025 → **2026 committed pipeline** | 152.7 | p630 0 |
| Pyron wind (10088, status OA) | not in model → **active 2025** | 249.0 | p600 3 |
| Danish Fields (21245) / Myrtle (21242) storage | not in model → **active 2025** (225 MWh each, 1.5 h; efficiency as fleet) | 150 / 150 | p650 5 / p670 4 |
| Kiamichi (7970–7975) / Tenaska Gateway (7234–7237) | active 2025 kept at physical MW; own plant group, monthly cap | 1,224 / 826 | p630 1 |

- **Danish Fields and Myrtle:** ReEDS lists them as OP with StartYear 2026. The model rule (active = OP/SB and StartYear ≤ 2025; committed = U/V/TS) therefore had them in **neither** the 2025 fleet nor the committed pipeline. Moving them adds 300 MW without duplication. The builder asserts that each Unique ID sits in at most one set and that the network sets equal the override result.
- **EIA vs ERCOT status:** kept as separate columns so the concepts are not mixed.
  - `eia860_2025_status_MW`, e.g. "TS:150" for the two storage plants and "V:229.5" for Gaia.
  - `ercot_mora_2025_months_listed`: 12 months for each storage plant.
  - The firm credit is only in the PRM bridge.

**Physical fleet change by carrier (MW; active 2025):**

| Carrier | Change |
|---|---:|
| wind | +249.0 |
| storage | +300.0 |
| solar | −152.7 |
| **Total** | **+396.3** (155,050.6 → **155,446.9**, record-by-record sum) |

- Committed pipeline solar: +152.7 (8,790.2 → 8,942.9).
- Committed total: 15,186.2 → 15,338.9. No other record changes set.

**Switchable caps** (`SWITCHABLE_CAP_QA.csv`, 12 source months):

| Plant | Cap range (MW) | p_max_pu range |
|---|---|---|
| Kiamichi | 609–1,215 | 0.4975–0.9926 |
| Gateway | 551–826 | 0.6671–1.0 |

- **Dispatch:** in LP2, dispatch never exceeds the cap (max(p − cap) = 0.000 MW). Kiamichi is at its cap in 540 steps, Gateway in 2,417; the August maxima are 609 and 556 MW.
- **ERM:** the credit uses the same p_nom × p_max_pu(t) (`reserves.py`, non-extendable right-hand side), with no second derating. This is shown by the unit test and by the identity check on the reloaded network (difference 0 MW).
- **Not applied:** the 2026–2031 seasonal CDR table is not applied, because it is a future-scenario input.

## 3. LP1: minimum thermal uplift (revised fleet, caps, fixed pre-calibration x/r)

- **Result:** optimal in 1,565.6 s; objective 1.7867e10 USD.
- **Uplift:** **18 lines, 5,151.8 MVA**, against 18 lines and 4,993.9 MVA in the pre-v1.6 baseline.
  - All 18 uplifts are > 0.5 MVA. Every uplift is in the network (`TAMU_2025_CALIBRATION_LP.csv`; 0 lines ≤ 0.5 MVA dropped).
  - The uplifts are concentrated in West/Far West (p600–p620), plus TL63/TL73 (p630) and TL68/TL69 (p630 13 – p640).
- **Residual shed:** 102.20 MWh (2 events, p620 1 and p620 7; largest gap 27.10 MW).
  - Matching the earlier 102.2 MWh is a coincidence, not a target: the fleet, the caps and the save rule all changed.
- **New baseline:** `workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`, SHA-256 `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`.
  - Raw uncalibrated network: SHA-256 `eb659f9b1ba06b5e37a162b7173c36d07a6a19a92ae016d3cf3568905077a97f`.
  - Both files are on L2 only (6.4 MB each, not in git).

## 4. LP2: reloaded fixed-asset check (`BASELINE_V16_FIXED_ASSET_QA.json`)

**Identity, checked on the files read from disk before the solve:**
- x and r are identical to raw (max |Δ| = 0);
- s_nom equals the LP1 solution (max |Δ| = 1.8e-12 MVA) on 18 uplifted lines;
- LP1 input s_nom equals raw;
- switchable p_max_pu series are present and equal the caps (0 MW difference).

**Model setup:**
- linopy variables: `Generator-p`, `Line-s`, `StorageUnit-p_dispatch/p_store/state_of_charge` only, so no expansion variable exists;
- `lv_limit` removed;
- annual cyclic storage;
- shed at VOLL 35,685 USD/MWh.

**Result:** optimal in 257.4 s.

| Metric | Value | Proxy limit | Pass |
|---|---:|---:|---|
| EENS | **111.79 MWh** = 2.29e-7 of 488.23 TWh | ≤ 1e-5 (4,882.3 MWh) | yes |
| Largest gap | **27.19 MW** = 3.25e-4 of 83,679 MW | ≤ 1e-3 (83.68 MW) | yes |

- **Events:** 7 events, 4 steps (12 h), on 5 buses.
  - p620 1, 07-14 09:00 model label: 81.3 MWh, 27.1 MW.
  - p620 7, 08-28 09:00: 21.4 MWh, 7.1 MW.
  - p620 2, 08-28: 5.5 MWh.
  - p620 7, 07-31: 3.2 MWh.
  - Three events below 0.3 MWh each (p620 5, p620 2, p630 2).
- **Location:** 111.70 of the 111.79 MWh is in Far West p620, so the remaining shortfall is local transmission inside Far West. It is not a system-wide resource shortfall. **This is small, but it is not zero shed.**
- **LP1 vs LP2 shed:** LP1 shows 102.2 MWh and LP2 111.8 MWh because LP2 prices shed at VOLL (35,685 USD/MWh) rather than LP1's 1e6 USD/MWh, over the same assets.
- **Storage:** throughput 6,406.5 GWh; simultaneous charge and discharge 3,749.5 GWh in 2,651 steps.
  - This matches v1.5 (X1 stage 1: 3,787 GWh), where it was shown to be mostly LP degeneracy. No storage objective was added this round.
- **Other:** 46 binding lines; 10.50 TWh wind and 4.94 TWh solar curtailment; bus balance residual 3.2e-10 MW.

## 5. Anchor 2: official PRM, same-scope bridge (`RELIABILITY_ANCHOR_BRIDGE.csv`, `PRM_BRIDGE_SUMMARY.json`)

**Official rows (December 2024 Revised CDR, published 2025-02, Summer Summary).**
- PRM recomputed from its parts:

  | Risk period | Firm load (MW) | Credited capacity (MW) | PRM |
  |---|---:|---:|---:|
  | Peak load | 86,716.912 | 103,105.481 | **18.8989 %** |
  | Peak net load | 82,963.969 | 91,651.798 | **10.4718 %** |

  Each matches the source cell to < 1e-9.
- **Numerator** by category: thermal, hydro, switchable, mothballed, PUN, wind and solar by region, storage, RMR, DC ties. Planned rows are kept as their own status.
- **Denominator:** normal-weather forecast load less rooftop PV, load resources, ERS, TDSP programs and voltage reduction.
- These are published 2025 **forecast** results including eligible planned resources. They are not observed 2025 adequacy.

**Model rows (same scope), on the v1.6 fleet.**
- **ELCC by risk period:** peak_load uses summer_afternoon; peak_net_load uses summer_evening.
- **Storage:** each unit at its own duration (BESS 1–12 h, interpolated).
- **Wind and solar by CDR region:**
  - Coastal and Panhandle by county list; Far West and West by the builder's weather-zone assignment of the county.
  - These region lists are proxies, written into the script.
- **Thermal:** summer MW without the switchable plants.
- **Switchable:** the v1.6 cap of the risk month, counted once (August 1,165 MW; July 1,318 MW).
- **Hydro:** network p_max_pu at the risk step.
- **Not modelled (0, no virtual capacity):** demand-side resources, PUN, RMR, DC ties, mothballed.

**Bridge, peak load:**

| Step | Δ (MW) | PRM after step |
|---|---:|---:|
| Official | | 18.90 % |
| Not modelled: DC ties −817.4, mothballed −135.5, PUN −3,265.0, RMR −412.0 | −4,629.9 | |
| Hydro (model profile 37.5 MW at the peak step vs CDR peak average 543.7) | −506.1 | |
| Switchable (model 2 plants at the August cap vs CDR all switchable net) | −1,035.0 | |
| Wind/solar/storage ELCC and installed-MW scope (year-end 2025 model fleet vs CDR operational + planned) | −1,300.2 | |
| **Thermal capacity basis (unexplained)** | **+4,000.1** | |
| Model credited total = 99,634.3 MW on the official firm load | | **14.90 %** |
| Load basis: official firm load → model native load at the peak step (83,403.7) | −3,313.3 | **19.46 %** |

- **Peak net load:**
  - official 10.47 %;
  - not modelled −4,719.0 MW; hydro −520.4; switchable −882.0; ELCC scope −449.5;
  - thermal +4,000.1;
  - model 89,081.0 MW gives **7.37 %** on the official firm load;
  - load basis −2,103.8 gives **10.17 %** on the model native load at the net-peak step (80,860.2 MW).
- **Bridge closure:** both bridges close exactly, with each category difference attributed.
- **Unexplained MW: 4,000.1** (thermal).
  - Model thermal is 70,405.3 MW against CDR 66,138 + planned 267.2. The capacity bases differ: ReEDS summer MW versus CDR summer-rated.
  - Private-use-network units may sit inside model thermal at gross MW while the CDR counts 3,265 MW net. This overlap with the PUN step is **unresolved**.
- **Load comparison:** native load (actual demand and weather) is not confirmed to equal the CDR firm-load concept. The load-basis step is a scope comparison, not an adequacy shortfall.
- **No fitting:** no capacity was added, and no load or ERM was changed, to reach 18.90 % or 10.47 %.

**ERM rows (model constraints, kept separate from the PRM):**
- The 15 % per-snapshot energy-backed ERM in S0–S3: storage and line reserve terms plus non-extendable p_nom × p_max_pu(t) must be ≥ 1.15 × demand(t).
- ERM-02 B: period margins ≤ 0.15, maximised on the existing + committed fleet. Future negative margins are proxy values, not an ERCOT planning standard.
- The official PRM is used only as an external validation anchor. **The per-snapshot ERM is not calibrated to an official standard; that is not implemented.**

## 6. Anchor 3: official transmission constraints (`TRANSMISSION_EXTERNAL_VALIDATION.csv`, `TRANSMISSION_MODEL_CONGESTION.csv`, `WEST_EXPORT_INTERFACE.json`)

- **Official source:** ERCOT 2025 Constraints and Needs report, p. 5; the observation window is 2024-10 to 2025-09.
- **Model:** LP2 flows, calendar-2025 load and profile year, 3 h steps, fixed v1.6 assets, no outages.

| Status | Official constraints |
|---|---|
| **DIRECTION_INCONSISTENT** | West Texas Export Interface (rank 4) |
| NETWORK_NOT_RESOLVED | Koch Tap–Vealmoor, Hargrove–Twin Buttes, Knapp–Scurry Chevron, Polecat Creek–Wrage Ranch Pod (West, 138 kV); Laredo VFT North–Las Cruces (South, 138 kV); Bell County–Salado (Central, 138 kV); Longshore–Consavvy (345 kV: clustered TL ids carry no substation names and the package gives no coordinates, so no TL is identified by name) |
| OUTAGE_SEQUENCE_NOT_MODELLED | Odessa EHV–Yarbrough, Haine Drive–La Palma |

**West Texas Export.**
- **Definition:** signed flow out of zones p60/p61/p62 on every line that crosses the boundary into p63–p67.
- **The model does export:** net export in 81.1 % of hours, mean 3,165 MW, maximum 9,971 MW.
- **But the boundary never binds in the export direction:** 0 export-binding hours, against 15 import-binding hours. Export never reaches 95 % of the summed limit of 20,274 MW on the crossing lines.
- **Congestion sits inside West:** for example TL3 p600 0–p600 1 (5,889 h), TL43 p620 4–p620 6 (4,479 h), TL40 p620 1–p620 5 (4,179 h) and TL12 p600 1–p620 2 (2,562 h); Far West shed totals 111.7 MWh. The Far West import and shortage phenomenon is **not** counted as a match.
- **Conclusion:** the official export-interface congestion is **not reproduced** at the 64-bus boundary. The ReEDS NARIS interface ratings on the West boundary appear loose relative to the operational West Texas Export limit.
- **Recorded as a model limitation; no lines were changed** to fit the historical congestion rents.

## 7. Regressions and tests

- **L2** (pypsa 1.3.0): `test_baseline_v16.py` + C0 + C0 repair v1.4 + C1 + v1.5 + dynamic siting + mainline v1.3 = **132 passed**, 0 failed.
  - This includes the post-run QA test (≤ 2 calls, attempt 1 each, optimal, identity).
- **Locally** (no pypsa): 93 passed, 39 skipped.
- **Earlier results:** historical results keep their own test standards. `baseline_2025_tamu/` and C0/C1/v1.5 results are untouched. v1.6 differences are tested with explicit v1.6 expectations (+396.3 MW, Gaia 2026, caps).
- **`GREAL_NETWORK_EVIDENCE.csv` metadata:**
  - The 8 Epoch 2025-stock buses are now separated from the 16 dynamic_pnnl_v1 research-cohort buses.
  - The POI-process row now says "every research AIDC bus (16 / legacy 8)".
  - The calibration row is 5,151.8 MVA / 18 lines on the v1.6 baseline, x/r unchanged.
  - The ERM row says it is not the official PRM.
  - Two v1.6 rows were added: asset decisions and switchable caps.
  - AIDC quantities, siting, inherited ramp, POI, gas and costs are unchanged.
  - Because the old geo-dynamic pre-run manifest pins this file by SHA, that manifest no longer matches. This only makes the NOT_APPROVED gate stricter; an approved run needs a rebuilt manifest anyway.

## 8. Prepared S0/S1 configuration (not run)

- **Config:** `workflow/config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml`. It is identical to the geo-dynamic v1 config except:
  - `case_id` `MAINLINE_V13_GEO_DYNAMIC_V1_BASEV16_MID`;
  - `inputs.baseline` → the v1.6 baseline;
  - the manifest pointer;
  - `run_authorization: NOT_APPROVED`.
- **Manifest:** `current_work_pckg/S0_S1_BASELINE_V16_PREPARED_MANIFEST.json` holds the baseline SHA, input SHAs, resume order and wiring items.
- **Resume order:** step0 (ERM-02 B + S0CAL on this baseline, new CALCASE) → S0/S1_EARLIEST → S2/S3/S3_mS2.
- **Wiring still needed before an approved run:** `rearch_mech.py` reads the old `BASE_TAMU` unless `--base` is passed, and `run_mainline.sh` does not pass it yet.

## 9. Fixed return (package §6)

```text
START_SHA / CODE_SHA / REPORT_SHA: 55766e31 (package source) -> 027431c2 (archive) / 85cd6ae5 / the commit containing this report
CALIBRATION_STATUS: COMPLETE_WITH_STATED_LIMITATIONS
NETWORK_REPRESENTATION: fixed_precalibration_xr_thermal_limit_proxy
SOURCE_AND_OVERRIDE_SHA: ASSET_DECISIONS.csv c10164c5a5a020b1…; SWITCHABLE_2025_MONTHLY_AVAILABILITY.csv cafe312e829b09c9…; SOURCE_MANIFEST.json da0b948ac91a22a5… (16/16 raw files SHA-verified); DECISION_POLICY.yaml a82ad526d30ba341…; ReEDS source table not edited (audited overrides by Unique ID)
PHYSICAL_FLEET_DELTA_BY_CARRIER_AND_PIPELINE_NO_DUPLICATION: active 2025 wind +249.0, storage +300.0, solar -152.7 = +396.3 MW (155,050.6 -> 155,446.9); committed solar +152.7 (Gaia, 2026); Danish Fields / Myrtle were in neither set before; each Unique ID in at most one set (asserted)
KIAMICHI_GATEWAY_DISPATCH_AND_ERM_CAP_CHECK: own plant groups at 1,224 / 826 MW physical; p_max_pu = monthly MORA cap / p_nom (Kiamichi 609-1,215, Gateway 551-826 MW); LP2 max(p - cap) = 0.000 MW; ERM credit = p_nom x p_max_pu(t) once (reserves.py unit test + reload identity 0 MW); 2026-2031 caps not applied
LOAD_TOTAL_AND_1H_3H_PEAK: 488.234 TWh (model equal); 1 h peak 83,679.0 MW (08/18/2025 HE 18); 3 h peak 83,403.7 MW
OFFICIAL_PRM_REPRODUCED_PEAK_AND_NET_PEAK: 18.8989 % (103,105.481 / 86,716.912) and 10.4718 % (91,651.798 / 82,963.969), reproduced to < 1e-9
MODEL_PRM_SCOPE_BRIDGE_AND_UNEXPLAINED_MW: peak 14.90 % on the official firm load (19.46 % on model native peak); net peak 7.37 % (10.17 %); not modelled 4,629.9 / 4,719.0 MW; unexplained 4,000.1 MW (thermal capacity basis / possible PUN overlap); bridges close exactly
ERM_VS_PRM_INTERPRETATION: 15 % per-snapshot ERM and ERM-02 B are model deliverability rows, not the CDR PRM; PRM used as external anchor only; snapshot ERM not calibrated to an official standard (not implemented)
OFFICIAL_TRANSMISSION_MATCH_MISMATCH_UNRESOLVED: 0 consistent / 1 direction inconsistent (West Texas Export: model exports 81 % of hours but the boundary never binds for export; congestion is inside West / Far West) / 7 network not resolved (138 kV local, Longshore-Consavvy unnamed) / 2 outage sequence not modelled
LP_STAGES / ACTUAL_CALLS / RETRIES: 2 / 2 / 0
FINAL_FIXED_ASSET_EENS_MAX_GAP_EVENTS_AND_LOCATION: EENS 111.79 MWh (2.29e-7 of annual energy); max gap 27.19 MW (3.25e-4 of 83,679 MW) at p620 1, 2030-07-14 09:00 (July 2025 source); 7 events / 4 steps / 5 buses (p620 1, 2, 5, 7; p630 2); 111.70 MWh in Far West p620 = local transmission; LP1 102.20 MWh
FINAL_RELOADED_NETWORK_XR_CAPACITY_IDENTITY: x / r identical to raw_uncalibrated.nc (max |delta| 0); s_nom = LP1 solution (max |delta| 1.8e-12 MVA) on 18 lines / 5,151.8 MVA, 0 uplifts dropped; caps present; no *_nom variable
TESTS_AND_MATERIAL_LIMITATIONS: 132 passed on L2 (v1.6 + C0 + C0 repair + C1 + v1.5 + dynamic + mainline). Limitations: West export boundary not reproduced; 4,000 MW thermal capacity basis unresolved; DR / PUN / RMR / DC ties not modelled; CDR region mapping by county proxy; monthly caps are planning envelopes, not hourly outages; storage simultaneity remains degenerate; 3 h, 64-bus synthetic network, no N-1, no outages; diff-table labels re-keyed after the run (numbers unchanged)
NEW_BASELINE_PATH_AND_SHA: workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc (L2) a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16; raw eb659f9b1ba06b5e37a162b7173c36d07a6a19a92ae016d3cf3568905077a97f
S0_S1_CONFIG_READY / FORMAL_GATES_UNCHANGED: yes (config + manifest; --base wiring still to add in the approved follow-up) / yes (all NOT_APPROVED; nothing run)
```

## 10. Deliverables (`current_work_pckg/`; full set in `workflow/results/BYOP/baseline_2025_tamu_v16/`)

- **Copied here:**
  - `BASELINE_V16_INPUT_DIFF.csv`, `ASSET_OVERRIDE_AUDIT.csv`, `SWITCHABLE_CAP_QA.csv`;
  - `RELIABILITY_ANCHOR_BRIDGE.csv`, `TRANSMISSION_EXTERNAL_VALIDATION.csv`;
  - `BASELINE_V16_FIXED_ASSET_QA.json`, `BASELINE_V16_SOLVE_LOG.csv`;
  - `S0_S1_BASELINE_V16_PREPARED_MANIFEST.json`, `V16_CLOSEOUT_SUMMARY.json`.
- **In the results directory:**
  - `LP1_METRICS.json`, `LP1_LINE_SOLUTION.csv`, `LP1_shedding_events.csv`;
  - `LP2_*` (lines, events, shed by bus, line flows, SOC, switchable dispatch);
  - `PRM_BRIDGE_SUMMARY.json`, `PRM_BRIDGE_UNIT_CATEGORIES.csv`;
  - `TRANSMISSION_MODEL_CONGESTION.csv`, `WEST_EXPORT_INTERFACE.json`;
  - builder ledgers and audit, the `_dry/` check, and console logs `LP1_console.log` / `LP2_console.log` (solve logs).
- **Stop for researcher review.** No further solve is authorised by this package.
