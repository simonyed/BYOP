# AIDC_GEO_DYNAMIC_V1_IMPLEMENTATION_REPORT: multi-bus siting of 2026–2035 data-center load (implementation, no solver)

- Date: 2026-10-22 (New York time)
- Branch: `mainline-v13-stageA`; main was not changed. The SHAs are listed in `AIDC_GEO_DYNAMIC_V1_RETURN_MANIFEST.md`.
- Parent commit:
  - `d0a9bf85`: this package was archived and the work package added on top of `b3cb9c32`, which the work package cites.
  - That commit only moved `current_work_pckg` into `_completed/BYOP_ERCOT_Mainline_v1.3/` and pointed the two code paths to the archive. It did not change the model or any input.
- **Solver runs: 0.** Neither config was modified to `APPROVED`. B3-E results and all legacy input files are unchanged (SHA checked).
- Status: `IMPLEMENTED_NO_SOLVER`. Waiting for researcher review.

## 1. What was done

| Step (§10) | Implementation | Files |
|---|---|---|
| Data sources and source QA | The PNNL preprocessing script was moved into the repository. It adds:<br>• Atlas deduplication (explicit containment, suspected same campus)<br>• exclusion of the 4 crypto-mining records, matched on both id and name<br>• a mapping-review table: boundary ties, distance > 15 km, county/busmap mismatches<br>• a verify mode used when raw data is not available | `byop/build/build_pnnl_tamu_candidates.py`<br>`inputs/dc/PNNL_*` (4 regenerated + 1 new `PNNL_SPATIAL_MAPPING_REVIEW.csv`) |
| Legacy 8-bus baseline frozen | The new builder writes only `*_GEO_DYNAMIC_V1*` files. Before and after writing it compares the SHA of 11 legacy inputs.<br>Tests compare the 4 key legacy files with `inputs_sha256` in the B3-E `case_manifest.json`. | `byop/build/build_dynamic_siting_inputs.py` |
| verified / forecast ledger | Each 2026+ increment of the 15 Epoch queue items is classified; see §2. | `MAINLINE_SITE_CLASSIFICATION_GEO_DYNAMIC_V1.csv` |
| 36 MW candidate set | q_b = (E_decade + A + P)/3, mid 2026–2035. All 8 Epoch buses are kept. A bus backed only by crypto-mining records is removed. → **16 buses** | `MAINLINE_CANDIDATE_BUS_ELIGIBILITY_GEO_DYNAMIC_V1.csv` |
| Dynamic weights and annual conservation | Yearly α/β/γ; each source is normalized first, then mixed; the result is renormalized after filtering. `NEW = LOCKED + R·w`. | `MAINLINE_SITING_WEIGHTS_GEO_DYNAMIC_V1.csv`<br>`MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv`<br>`MAINLINE_AIDC_RECONCILIATION_GEO_DYNAMIC_V1.csv`<br>`ROUNDING_RECONCILIATION_GEO_DYNAMIC_V1.csv` |
| POI / gas / RE for new buses | 8 Epoch buses: evidence fields unchanged, 4 derived quantities recomputed (OLD/NEW delta).<br>8 new buses: uniform PROXY values, see §4. | `inputs/poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv`<br>`MAINLINE_POI_DERIVED_DELTA_GEO_DYNAMIC_V1.csv`<br>`MAINLINE_NEW_BUS_POI_RISK_GEO_DYNAMIC_V1.csv`<br>`MAINLINE_NEW_RESEARCH_BUS_POI_MAP_GEO_DYNAMIC_V1.csv` |
| Model input switch | `mainline.siting_variant` (default `epoch8_legacy`). `ml_select_siting()` sets `ML_COH` / `ML_POI` / `ML_INPUTS` **before the run gate hashes them**. A config path that does not match the variant is refused. | `byop/model/rearch_mech.py`<br>`config/config.byop_ercot_mainline.yaml` (adds `siting_variant: epoch8_legacy`)<br>new `config/config.byop_ercot_mainline_geo_dynamic_v1.yaml` |
| Fixed 8-bus / 48-key assumption removed | The expected M4 key set comes from `mainline.research_buses × model_years` recorded in the case manifest, never from S2 output.<br>New fields: `matched_service_expected_keys_present` / `_expected_key_count` / `_observed_key_count`.<br>The legacy `matched_service_48_keys_present` field is still filled for 48 keys and is `None` for any other geography.<br>Structural tests count `N_B × N_Y`.<br>`stage_b3_tables` takes bus names from the bus map. | `post/collect_mainline.py`<br>`tests/structural_mainline_v13.py`<br>`post/stage_b3_tables.py` |
| Runner and manifest | `run_mainline.sh` accepts `CFG=…`; the case ID is read from the config.<br>The B1 calibration (S0 has no research load) is shared through `CALCASE`.<br>New `tests_geo` entry.<br>`build_mainline_manifest.py --variant dynamic_pnnl_v1` writes a separate pending manifest. | `byop/run/run_mainline.sh`<br>`byop/build/build_mainline_manifest.py`<br>`current_work_pckg/AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json` |
| Versioned method parameters | α/β/γ, the g0/g50 mix, the 36 MW threshold, the reviewed `locked_verified` items and the new-bus PROXY values all live in the YAML. None are hard-coded. | `inputs/dc/MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml` |

The mathematical model (network, technologies, build times, ERM, TPIT, S0CAL, VOLL, Gurobi options, lexicographic objectives, no-harm) is **not changed**. The one model-code addition:
- If a PNNL new bus has no PyPSA-USA wind or PV **candidate profile** for some technology, BYOP onsite RE of that technology is not offered there, and the case is recorded in `byop_re_profile_missing` in the case manifest.
- No profile is borrowed or invented.
- Legacy buses keep the original hard check.
- The structural test shows the only such case is **p650 7 WIND**: p650 7 has no public onwind candidate in the TAMU network, although ReEDS2 lists 588 MW of remaining potential there.
- This needs researcher review: should that bus be allowed to borrow the wind profile of a neighbouring bus, or does it stay as now with no onsite wind?

## 2. Verified / forecast ledger (§3.2)

Locking rule:
- An increment is `LOCKED_VERIFIED` only if a manually reviewed Epoch timeline row:
  - is dated on or before 2026-10-21;
  - does not use estimate wording;
  - and its status text says the capacity is operational, citing a source (earnings call, TDLR, company statement) or satellite imagery.
- E0 equipment and project names never lock demand.
- Every decision is recorded in the YAML.

| Site / Epoch year | Increment (MW IT) | Classification | Basis |
|---|---:|---|---|
| CoreWeave Denton TX / 2026 | 195 | **LOCKED_VERIFIED** | 2026-07-03: buildings 1–7 operational (satellite + Core Scientific Q2 2026 earnings call) |
| Coreweave Helios / 2026 | 132 | **LOCKED_VERIFIED** | 2026-08-30: building 1 fully operational (Phase I) |
| Microsoft SAT14 / 2026 | 28 | **LOCKED_VERIFIED** | 2026-03-31: building 2 fully operational, construction complete |
| Vantage TX1 / 2026 | 32 | **LOCKED_VERIFIED** | 2026-02-15: building 1 operational |
| OpenAI Stargate Abilene / 2026 | 632 | FORECAST | Buildings 5–8 structurally complete but not confirmed operational; 843 MW is an estimate |
| Google Midlothian / Red Oak / Meta Temple / 2026 | 103 / 77 / 26 | FORECAST | "probably operational" or estimated dates |
| Crusoe Abilene expansion / 2027 | 672 | FORECAST | TDLR completion date only |
| Stargate Shackelford / 2027, 2028 | 420, 980 | FORECAST | Under construction; operation date = TDLR + 6 months (estimate) |
| Helios / 2028, 2029; Denton / 2027; Vantage / 2027 | 264, 132, 20, 96 | FORECAST | Company guidance or TDLR estimates |

How the locks enter the allocation:
- A locked increment keeps **the bus and the year in which it was served under the original approved scenario** (`EPOCH_SITE_SERVICE_TAMU64.csv`). In mid this is 33.24 MW in 2026, 222.07 MW in 2027 and 131.69 MW in 2028, 387 MW in total.
- Because of this, a lock can never exceed that year's total. A lock larger than its Epoch bucket, or with no matching bucket, causes a `BLOCKED_DATA_CONFLICT` stop (tested).
- 2026 always keeps the original Epoch layout (α = 1), whatever is locked.
- The researcher can move any FORECAST item to `locked_verified`; rerunning the builder applies it.

## 3. Results (mid; low/high in the CSVs)

| Item | Value |
|---|---|
| Research-demand buses | **16**: the 8 Epoch buses + p630 3, p630 8, p630 10 (DFW), p640 1 (Austin), p650 7 (San Antonio), p670 0, p670 1, p670 4 (Coast) |
| Annual conservation | **30/30 PASS**: low/mid/high × 2026–2035, absolute error < 1e-4 MW |
| Research addition, mid 2026–2035 | 4,567.903 MW IT, same as legacy |
| Top-3 share, mid 2026–2035 | **48.3 %** (legacy 84.0 %) |
| 2026 | Same as legacy Epoch; all 8 new buses are 0 |
| Expected M4 keys, 2026–2031 | **96 = 16 × 6** (the work package's reference ~17 × 6 = 102; see the data report §4: 17 buses with the raw Atlas basis) |

The bus-by-bus comparison is in `AIDC_GEO_DYNAMIC_V1_LEGACY_VS_DYNAMIC_AUDIT.md`.

## 4. New-bus POI / gas / RE (§5): PROXY only, never presented as rights

All 8 new buses are marked `PROXY_PNNL_NEW_SITE`:
- **E0 = 0**: this only means there is no evidence that new research demand has spare approved equipment. It does not mean the bus's real POI capacity is zero.
- No `preapproved` E0 row was added.
- Upgrade path:
  - lead time 3 y (low 2 / high 5);
  - cost 160 USD/kW (80 / 300);
  - cap 2,000 MW;
  - earliest procedural COD 2028 (2027.5 / 2029).
- PCLR = 0.3 × the bus's mid 2031 research facility MW. This is a research upper bound, not an existing entitlement.
- Gas: L2 (lead 3 y, 100 USD/kW, MDQ 100,000 MMBtu/d).
- Onsite RE = 1.0 × 2031 facility MW, still subject to the ReEDS2 bus cap shared with the public grid.

**Risks that need the researcher's attention**:
1. **`POI_PROXY_MAY_DRIVE_DELAY`**: all 8 new buses first receive forecast demand in 2027, but under the proxy they cannot connect to the grid before 2028. If a later LP delays them, that delay comes from the proxy rule. It is not evidence that ERCOT would refuse connection.
2. **The upgrade cap is very loose**: 8 × 2,000 = **16,000 MW** of proxy upgrade cap, against only 961.5 MW IT of mid 2031 research demand on those buses. The cap was not tuned; it is left for the next calibration or sensitivity step.
3. Flags: `ATLAS_WITHOUT_E0_EVIDENCE` on 7 buses; `PROJECTED_ONLY_NO_ATLAS` on p670 1; `BOUNDARY_TIE_RECORDS` on 9 (6 new buses + Epoch p630 2/4 and p650 0); `CRYPTO_RECORDS_EXCLUDED` on p630 5 (the Riot record only).
4. p650 7 has no wind candidate profile (see §1).

Full list: `AIDC_GEO_DYNAMIC_V1_POI_GAS_RISK_REGISTER.csv`. Its columns follow §5.3.

## 5. Testing (all without a solver)

| Item | Result |
|---|---|
| Legacy static tests `test_mainline_v13.py` (L2) | **50 / 50 PASS** |
| Dynamic static tests `test_dynamic_siting.py` (L2) | **32 / 32 PASS** (0 skipped), covering GEO-01 to GEO-14 and the edge cases of §7.3 |
| Structural test, legacy (8 buses, 48 keys) | **46 / 46 PASS**; solver_executions 0 (3 calls intercepted) |
| Structural test, dynamic (16 buses, 96 keys) | **45 / 45 PASS**; solver_executions 0 (3 calls intercepted)<br>Model size, legacy → dynamic:<br>• S3: 4.39 M → 4.71 M variables, 7.56 M → 8.00 M constraints<br>• S2 joint developer: 0.13 M → 0.25 M variables, 0.28 M → 0.56 M constraints<br>• S0 has no research load and is unchanged |
| Gate | Both configs: `approved: false` (`run_authorization=NOT_APPROVED`, `approved_git_sha missing`)<br>Dynamic config: **no hash mismatch** (the pending manifest matches the current files)<br>Legacy config: additionally lists 5 code-hash mismatches against the archived v1.3 manifest. These are the code changes of this package; any rerun of legacy B3-E needs its manifest rebuilt and a new approval. |
| DRY `pilot_core_b3e` | legacy and dynamic commands assembled; nothing executed (new case directory `MAINLINE_V13_GEO_DYNAMIC_V1_MID_B3_EXPLORATORY_V1`) |
| Rebuild determinism (GEO-14) | the L2 rebuild of all `*_GEO_DYNAMIC_V1*` files is byte-identical to the local build |

Logs: `workflow/results/BYOP/mainline/_geo_dynamic_v1_qa/`, `_structural_geo_dynamic_v1/`, `_structural_legacy_geo_v1/`.

## 6. Data dependencies for the follow-up official calibration (C0–C5)

- **C0 (2025 official anchors)** uses only 2025 facts (2025 stock, D11, historical fleet, load) and **does not read** any dynamic-geography file. This package changed none of those facts.
- The future spatial distribution is chosen with `siting_variant`:
  - `epoch8_legacy` reproduces B3-E;
  - `dynamic_pnnl_v1` is the new version from this package.
- Any solve of the dynamic geography needs **a new researcher approval of a SHA**. The gate checks `current_work_pckg/AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json`.
- Recommended comparison order (§9.4), changing one thing at a time:
  1. old8 + old baseline (B3-E, existing results);
  2. newgeo + old baseline;
  3. newgeo + new calibration.
