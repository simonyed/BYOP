# C0_INPUT_RECONCILIATION: offline reconciliation of the 2025 official anchors (C0)

- Date: 2026-10-22 (New York time)
- Work package: `ERCOT_2025_Official_Anchor_v1.3/README_AND_EXECUTION_PROMPT_v1.3.md`
- Branch: `mainline-v13-stageA`
  - checkout SHA = the package's SHA, `7a7eb2683a1d91840060616ecb31b76623223ed7`;
  - archive commit `093e3247` (moves the AIDC geospatial package and adds this package);
  - code commit: see the return section at the end.
- **solver executions = 0.** Both run gates are still `NOT_APPROVED`, no B3 or other formal run was requested, and the model inputs are unchanged. This round **only did offline reconciliation and code integration. It does not claim that "the real ERCOT calibration is complete."**
- No changes were made to ERM, VOLL, technology costs, POI years, gas conditions, siting weights, annual increments, the dynamic 16-bus layout or the low/mid/high totals.

## 1. Task A: package integration and recomputation

| Item | Result |
|---|---|
| Official source files | 10 files, 27 MB, in `workflow/data/byop/ercot_official_anchor_2025/raw/` (local and L2, not uploaded to GitHub). SHA-256 checked one by one against `SOURCE_MANIFEST.json`, all match. |
| Package attachments | The original text, `SOURCE_MANIFEST.json`, `CHECKSUMS.sha256`, the annual-report page image and the two researcher scripts are in `current_work_pckg/ERCOT_2025_Official_Anchor_v1.3/` (byte-identical). The full copy including `repo_snapshot/` is local only, in `work_pkgs/ERCOT_2025_Official_Anchor_v1.3/`. |
| Repo-side recomputation | `byop/build/c0_anchor_evidence.py` (a port of `rebuild_evidence.py`, using paths from `byop_paths`) writes to `byop/inputs/anchor2025/`.<br>**All 9 tables and 17 metrics match the researcher's derived/ by value** (`EVIDENCE_REBUILD_CHECK.json: all_equal=true`).<br>The L2 and local rebuilds are byte-identical. |
| `repo_snapshot` vs the real repository | `rearch_mech.py`, `build_2025_baseline_tamu.py`, the fleet table, the calibration LP table and the 3 Epoch input files are byte-identical.<br>`baseline_2025_tamu_audit.json` has identical JSON content and differs only in formatting.<br>`build_mainline_inputs.py` was changed in this round (see the path item below). |
| Path configuration | `byop_paths.py` now has entries for `ANCHOR2025*`, `REEDS_GENDB`, `C0_RESULTS` and `BASE_TAMU_DIR`.<br>Personal `D:/` paths in the code are replaced by environment variables `BYOP_EPOCH_TIMELINE_RAW` and `BYOP_REEDS2_ROOT`. When unset, the behavior is unchanged: the tracked extract is used, and `build_reeds2_potential.py` requires `--reeds`. A test confirms no `D:/` path remains in `byop/build` or `byop/model`. |

Key metrics (`VERIFIED_METRICS.json`):
- **Native load**: 8,760 rows, **488.233578542299 TWh**.
- **Peaks**:
  - 1 h peak **83,679.001697 MW** (08/18/2025 18:00);
  - 3 h peak (consecutive 3-row mean) **83,403.652115 MW**;
  - the annual report's 83,707 MW is 27.998 MW higher than the Native Load 1 h peak. The cause of that 28 MW is not determined, and no scaling factor was applied.
- **Fuel Mix**: 488,072.550688 GWh, which is −161.03 GWh (−0.033 %) below Native Load. Reported only; neither side was adjusted.
- **Nuclear**: CDR installed capacity 5,268 MW against the model's 4,980 MW summer rating; the CDR summer 2026 column (4,973.2 MW) is used only to show the difference between the two definitions.

## 2. Task B: unit ledger bridge (`C0_GENERATOR_MATCH.csv`, `C0_CAPACITY_BRIDGE.csv`)

### 2.1 Matching method

The two sides are:
- the model fleet: ReEDS generator DB (ERCO, `TECH_MAP` identical to the baseline builder, with a test), 1,697 units active in 2025 (OP/SB, Start ≤ 2025 < Retire), **155,050.6 MW summer**, equal to `fleet_2025_MW_total` in the baseline audit;
- the CDR December 2025 Unit Details, 1,772 rows.

Matching rules:
- **Normalize the name first**: upper-case; drop technology words, legal suffixes and unit/phase designators (any token containing a digit, Roman numerals). Then group by plant: county + fuel family + name key.
- Match tiers, in order:
  1. exact key match;
  2. name similarity ≥ 0.5 within the same county and family, with a unique best candidate;
  3. name similarity ≥ 0.75 in a different county, unique;
  4. **capacity-assisted candidate** (`CANDIDATE_COUNTY_FUEL_CAPACITY`): only when a unique pairing exists within the same county and family and the MW ratio is 0.8–1.25. **This is not counted as a confirmed identity.**
- Never identified by nearest distance alone.
- Each model group pairs with at most one CDR group, and each ReEDS unit belongs to exactly one group (tested; **no one-to-many double counting of capacity**).
- No field of this table enters the model's numeric matrices; the model keeps its current values.

CDR "2025 core" units:
- statuses OPER / RMR / OPER-SYN / OPER-UNFC / OPER-UNR;
- attribute CONV or CONV-TGR;
- in service ≤ 2025-12-31 or with no date.

Excluded from the 2025 core:
- PLAN*, MOTH-IND;
- private networks (*-SLF / CONV-SLF), DGR / SODG distributed generation;
- DC-TIE, switchable (SWGR), EXT-OUT / MOTH-SEA.
- Tests confirm that no PLAN unit enters the 2025 history.

### 2.2 Coverage

| Measure | Units | MW |
|---|---:|---:|
| CDR 2025 core | 1,187 | 160,494.6 |
| Confirmed match (EXACT / FUZZY / OTHER_COUNTY) | 903 (76.1 %) | 130,047.9 (**81.0 %**) |
| + capacity-assisted candidates | | +12,337.7 → **88.7 %** |
| Ambiguous (multiple candidates) | | 1,759.6 |
| Unmatched | | **16,349.4** |
| Model active 2025, confirmed matched | 862 / 1,697 | 126,777.8 / 155,050.6 (**81.8 %**; 89.9 % with candidates) |

Confirmed + candidate share of CDR core MW by family: nuclear 100 %, biomass 100 %, hydro 100 %, coal 100 %, gas 89.6 %, wind 92.4 %, solar 78.3 %, storage 82.9 %.

### 2.3 Capacity bridge (MW; exact decomposition, all identity checks = 0)

`AR − model = [AR − CDR core] (unexplained publication residual) + [CDR core − model]`

The second term splits further into:

`rating difference (matched) + cross-ledger pipeline + matched but no model unit + candidate pairs + CDR unmatched − model unmatched − model matched to non-core`

| Category | Annual report | Model | Apparent gap | CDR core − model | **Unexplained AR − CDR core** |
|---|---:|---:|---:|---:|---:|
| Thermal | 89,507 | 72,455.3 | 17,051.7 | 1,767 | **15,285** |
| Wind | 40,719 | 40,028.8 | 690.2 | −42 | 732 |
| Solar | 37,443 | 29,262.7 | 8,180.3 | 3,080 | **5,100** |
| Storage | 16,656 | 12,768.4 | 3,887.6 | 607 | 3,281 |
| Hydro | 579 | 535.4 | 43.6 | 32 | 11 |
| Total | 184,904 | 155,050.6 | 29,853.4 | 5,445 | **24,409** |

Family-level decomposition (MW):

| Family | Rating difference (matched) | Cross-ledger pipeline | CDR unmatched | Model unmatched | Model matched to non-core | Candidates |
|---|---:|---:|---:|---:|---:|---:|
| gas | +2,748 | 0 | +5,752 | −5,691 | −3,893 | −363 |
| coal | +2,887 | 0 | 0 | 0 | 0 | +44 |
| nuclear | **+288** | 0 | 0 | 0 | 0 | 0 |
| solar | −456 | **+1,993** | +7,034 | −5,074 | −1,394 | +157 (and +820 matched but no model unit) |
| storage | −88 | +255 | +2,287 | −1,661 | −632 | +40 (+406) |
| wind | +201 | +265 | +3,036 | −3,170 | −450 | −189 (+263) |

How to read this:
1. **Most of the 29.85 GW apparent gap falls between the annual report and the CDR core**: 24.4 GW, of which 15.3 GW is Thermal. It is a difference in publication scope, rating and snapshot.
   - Candidate explanations, from the CDR "scope_info" rows, not allocated: OPER-SYN and other qualified statuses (gas 2,756, coal 2,137, solar 12,479 MW), switchable available (gas 4,066), outage/seasonal (coal 1,008), private networks (974), distribution DG (1,430).
   - The Dec 2025 trend operational exceeds the CDR core by 13.5 GW for gas, 5.1 GW for solar and 3.3 GW for storage. This is a definitional difference between two ERCOT publications from the same month. **Without evidence it is not assigned to any item**, and the model is not scaled up by 184.904 / 155.05.
2. **CDR core − model is only +5.4 GW**:
   - the matched rating difference is concentrated in thermal (gas +2.7 GW, coal +2.9 GW, nuclear +288 MW, i.e. installed rating vs summer rating);
   - the "CDR unmatched" and "model unmatched" amounts roughly offset each other (gas +5.8 / −5.7 GW, wind +3.0 / −3.2 GW). Most of this is an **ERCOT resource name vs EIA plant name** identification problem. It is not decided whether it means a missing unit.
3. **No unit was added or scaled up.**

### 2.4 Cross-ledger pipeline (Task B4, `C0_PIPELINE_RECLASS_SUGGESTIONS.csv`; suggestions only, not applied)

- **The CDR shows these operating by end-2025, but the model holds them only in the 2026 committed pipeline**:

  | Family | Plants | MW | Plants (MW) |
  |---|---:|---:|---|
  | Solar | 5 | **1,993.4** | Danish Fields 602.8, Roseland 508, Cottonwood Bayou 351.4, Myrtle 321.2, Blue Jay 210 |
  | Storage | 5 | 712.9 | Tidwell Prairie, Callisto, Headcamp, Stoneridge, Padua Grid |
  | Wind | 1 | 265.4 | Big Sampson |

  Most in-service dates are October–December 2025. This affects the 2025-end state of the 2026 starting fleet. It does not affect the 2025 operating replay. Whether to move them into the 2025 fleet needs a researcher decision.
- **The reverse**: 95 model groups are active in 2025 but their CDR match is not in the 2025 core. That is 6,368 MW: gas 3,893, solar 1,394, storage 632, wind 450.
  - The largest is **Kiamichi**: the model has 1,224 MW in Pittsburg County, Oklahoma; ERCOT CDR lists it as "TENASKA KIAMICHI STATION", a **switchable resource** connected at Fannin County with **some units marked SWGR-UNA (unavailable to ERCOT)**. The model counts the full amount as ERCOT capacity.
  - Researcher review is needed; nothing was changed.

### 2.5 Returned to the researcher (unresolvable without new evidence)

- **68 CDR core groups are unmatched (16.3 GW).**
  - Largest ones: Wise Tractebel 848, Sandhill 753, CVC Channelview 726, Brazos Valley 673, Pasadena Cogen 626, Plainview Ramsey 540, Rabbs 484, Parliament 483, Photon 452, H Braunig RMR 420 MW.
  - Many of these have an EIA plant in the same county under a different name, for example Channelview Cogeneration Plant 761 MW and Sand Hill 596 MW.
  - The full list is in `C0_GENERATOR_MATCH.csv` with `match_status=UNMATCHED`.
- **An ERCOT UNIT CODE ↔ EIA plant/unit ID crosswalk is needed** to replace the name and capacity candidate tiers.
- **20 ambiguous core units (1.8 GW)**: the candidates are listed in `match_note`.

## 3. Task B5: historical AIDC evidence classes (`C0_HISTORICAL_AIDC_EVIDENCE.csv`)

Values, buses, 2025 averages, end-2025 values and the 460.73 MW IT inherited ramp are unchanged (tested).

| Site | 2025 avg / year-end / inherited (MW IT) | Evidence class |
|---|---|---|
| Stargate Abilene | 30.23 / 211 / 180.77 | `OPERATION_CONFIRMED_FIRST_HAND__IT_MW_ESTIMATED` (Crusoe 2025-09-30) |
| CoreWeave Denton | 4.87 / 67 / 62.13 | `COMPANY_BILLABLE_MW__NOT_ENERGIZED_IT`: billable, energized, IT and actual load are recorded separately |
| Meta Temple | 9.58 / 152 / 142.42 | `ESTIMATE__2025_OPERATION_NOT_CONFIRMED` (Meta announced serving traffic on 2026-07-22) |
| Google Red Oak | 27.21 / 77 / 49.79 | `ESTIMATE__IMAGERY` |
| Microsoft SAT40 | 49.38 / 75 / 25.62 | `ESTIMATE__IMAGERY_DOWNGRADED` |
| Microsoft SAT14 | 19.00 / 19 / 0 | `ESTIMATE__IMAGERY_DOWNGRADED` |
| The other 5 sites | 0 | `NO_2025_CAPACITY` |

- No site is labelled VERIFIED.
- `estimate_wording=False` is not treated as sufficient grounds for VERIFIED.
- The algebra end = avg + inherited holds at every site, and the per-bus sums equal `MAINLINE_INHERITED_RAMP_2025`.
- The inherited ramp is labelled **`LOAD_PROXY_FROM_HISTORICAL_CAPACITY_ESTIMATE`**.

## 4. Task C: time axis and load ledger (`C0_LOAD_ACCOUNTING.csv`, all 17 checks PASS)

- **Rows and labels**:
  - 8,760 rows;
  - 1 `02:00 DST` row kept;
  - 365 `HE 24:00` rows kept and not double-counted;
  - source row numbers are consecutive.
- **3 h aggregation**: 2,920 steps × weight 3; annual energy is conserved (< 1e-3 MWh).
- **Baseline bus load**: on each of the 2,920 steps, the bus sum equals the ERCOT 3 h native load (max error < 1e-3 MW).
- **2025 demand components**:
  - native load only;
  - **no extra 2025 AIDC stock is added**: the 140.27 MW IT 2025 average is already inside the native load;
  - the background growth factor is 1.0 in 2025;
  - the 460.73 MW IT inherited ramp is added only from 2026, via `rearch_mech.add_inherited_ramp` × PUE;
  - storage charging is a StorageUnit variable, not part of load;
  - research AIDC starts in 2026, and the regional / competing queue is off in the mainline.
- **Not done this round**: an audit of future delivery conflicts, and any change to future scenarios. The spatial split of historical load across buses is a model rule, not a meter reading.

## 5. Task D: transmission uplift ledger (`C0_UPLIFT_LEDGER.csv`)

The ledger has three layers, recorded separately and never added together:

| Layer | Unit | Size | Form |
|---|---|---|---|
| 1. Synthetic original / interface rule | MVA | 162 lines (reeds_sum) | line `s_nom` |
| 2. 2025 calibration uplift (B2025_CALIBRATION_LP) | MVA | **18 lines, 4,993.9 MVA**, residual shed 102.2 MWh | added inside line `s_nom` |
| 3. S0CAL common baseline (B1, from 2026) | MW | **9 lines, 1,095.6 MW** | fixed `AC_s0cal` Link pairs, fwd/rev. Line `s_nom` is unchanged. |

Checks:
- `final_s_nom = interface rule + 2025 uplift` on every line, max error 2.7e-5 MVA.
- `existing_MVA` in S0CAL equals the final 2025 `s_nom`, so layer 3 is stacked on layer 2 only once.
- **The L2 baseline `.nc` was read** (`sha 19034285…`, read only, no solve):
  - line `s_nom` equals the ledger to within 1.8e-12 MVA;
  - the 2025 baseline has 0 `AC_s0cal` Links.
- Evidence class: synthetic calibration uplift (B). **It is not a TPIT project in service, and not a verified thermal limit.**
- **C1 preparation**: `build_2025_baseline_tamu.py` calls `calibrate_2025` (an LP) by default. This round never calls that builder. The C0 code entry points (`c0_anchor_evidence.py` / `c0_anchor_audit.py`) are checked by an AST test: they do not import linopy / gurobipy / the baseline builder and contain no `optimize` / `solve` call. When C1 runs, it must use `--no-calibration` explicitly or go through a separate gate, and it must keep the 2025 in-year replay apart from the year-end asset state.

## 6. Tests (L2, no solver)

| Test | Result |
|---|---|
| `test_c0_anchor.py` (source SHA, load energy and peak, DST/24:00, 3 h conservation, no double-counted historical load, TECH_MAP consistency, no one-to-many units, PLAN not in history, bridge identity and no scaling, name normalization, AIDC labels, no double-counted uplift, no solver call, no personal path) | **13 / 13 PASS** |
| `test_mainline_v13.py` (legacy regression) | **50 / 50 PASS** |
| `test_dynamic_siting.py` (dynamic-geography regression) | **32 / 32 PASS** |
| L2 rebuild of the evidence files and C0 output CSVs vs local | byte-identical |
| Run gates (legacy and dynamic) | both `approved: false` |
| Solver processes before / after | none |

Logs: `workflow/results/BYOP/C0_ANCHOR_2025/_l2_run/`.

## 7. Still open (no claim that these are solved)

- One-to-one mapping between ReEDS units and the official records: the confirmed share is 81 % of MW; it needs an ERCOT↔EIA ID crosswalk.
- How the historical load is really distributed across the 63 buses.
- Correspondence between synthetic lines and real lines and their thermal limits.
- 2025 hourly metered load of the six AIDC sites.
- The cause of the 24.4 GW gap between the annual report and the CDR core.
- The 28 MW peak difference.
