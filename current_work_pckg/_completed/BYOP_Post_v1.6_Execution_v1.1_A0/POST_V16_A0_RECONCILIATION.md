# POST_V16_A0_RECONCILIATION: v1.6 items closed / carried, A0 verification (2026-10-22, New York time)

**Sources read:**
- `_completed/BYOP_Calibration_Closeout_v1.6/CALIBRATION_CLOSEOUT_REPORT.md`
- `BASELINE_V16_FIXED_ASSET_QA.json`
- `RELIABILITY_ANCHOR_BRIDGE.csv`
- `TRANSMISSION_EXTERNAL_VALIDATION.csv`
- the decision register `BYOP_Post_v1.6_Execution_v1.1/POST_V16_DECISION_REGISTER.csv`

## 1. Verification at A0 start (no solver)

| Check | Result |
|---|---|
| Branch / HEAD (local = GitHub = L2) | `mainline-v13-stageA` @ `0b417903c7704c00de609581646fed29723397cf`; no drift relative to the package |
| v1.6 network on L2 | `workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`, SHA `a623fb6d…747d16` (**verified on L2**); raw uncalibrated `eb659f9b…`. The dry check on L2 found 63 buses and 162 lines, the active fleet incl. storage is 155,446.9 MW, and the 2 switchable plant groups keep their monthly caps. |
| Staged package data | 53 / 53 files match `ORIGINAL_RESEARCH_FILES_SHA256.json`, and 20 / 20 raw files match `SOURCE_REGISTRY.csv`. <br>The package's `build_research_data.py` was re-run on a scratch copy; all 19 derived files are text-identical after line-ending normalisation (`STAGING_SHA_QA.json`). <br>Official files are unchanged. |
| Old manifests (`OLD_MANIFEST_SHA_DIFF.json`) | **Geo-dynamic v1 manifest (NOT_APPROVED):** 55 / 62 match on L2. The 7 changed files are rearch_mech.py, byop_paths.py, run_mainline.sh (A0 guards); GREAL_NETWORK_EVIDENCE.csv (v1.6 metadata); and build_mainline_inputs.py, build_reeds2_potential.py, test_dynamic_siting.py (earlier packages). <br>**v1.6 prepared S0/S1 manifest:** 9 / 9 match. <br>Both stay NOT_APPROVED; drift only makes the old gate stricter. |

## 2. v1.6 items (decision register)

| ID | v1.6 status | Closed in A0? | How |
|---|---|---|---|
| V16-01 freeze 2025 thermal baseline | CLOSED_ACCEPTED_WITH_LIMITATIONS | **closed** | The SHA-pinned v1.6 file is the only base. The gate and the `--post-v16` guard refuse any other file and there is no fallback. There is no further s_nom fitting. |
| V16-02 year-end fleet + annual 2025 load | CLOSED_WITH_SCOPE_LIMITATION | **carried (stated)** | A1 is a year-end-stock × 2025-load stress test, not a historical dispatch replay (vintage QA). |
| V16-03 switchable caps | CLOSED | **closed** | The caps are held on the 1 h snapshots through the 3 h step that contains each row, and the same availability bounds dispatch and reserve (one use). Test: `test_real_v16_models_build_without_solver`. |
| V16-04 official PRM | BRIDGED_NOT_FULLY_EXPLAINED | **carried** | 4,000.1 MW thermal basis is unexplained, and DR / PUN / RMR / DC ties are not modelled. The PRM is not used as a constraint; it must be disclosed in A1. |
| V16-05 West Texas Export | LIMITATION_OPEN | **carried** | A1 must report per-bus binding lines and zones (`NETWORK_PRESSURE_DIAGNOSTICS`). A West-dependent conclusion is flagged; there is no TL fitting. |
| CODE-01 baseline wiring | MUST_FIX_A0 | **closed** | `run_post_v16.sh` always passes `--base <v1.6>`, and DRY shows the full path. <br>`post_v16_a1.py` and `rearch_mech.py --post-v16` check the SHA. <br>The legacy `run_mainline.sh` refuses any post-v1.6 config (exit 6). |
| CODE-02 pre-run manifest | MUST_FIX_A0 | **closed** | New `POST_V16_A1_PRE_RUN_MANIFEST.json` pins 5 code files, 10 inputs, the normalised config and the baseline. <br>The new gate checks: approval, approved SHA == HEAD, clean tree (CR-at-EOL ignored, no untracked files), the package SHA, manifest SHAs, the SHA of the actual `--base`, stage list / order / zero retries / budget. <br>8 negative and 1 positive gate tests. |
| REL-01 ERM-02 B self-calibration | RECOMMENDED_REPLACE_A0 | **closed for the new line** | Not used by the new entries; `--calibrate` and `--erm-cal` are refused with `--post-v16`. Legacy is kept for reproduction. |
| REL-02 free S0CAL | RECOMMENDED_DISABLE_A0 | **closed for the new line** | `--s0-calibrate` and `--s0-cal-file` are refused with `--post-v16` and never passed by `run_post_v16.sh`. The 2025 X1 repair is unaffected. |
| REL-03 reserve amount | CANDIDATE_NOT_OFFICIAL | **implemented, pending approval** | Fixed exogenous 3,000 MW, τ = 1 h; 4,000 MW is not run. |
| REL-04 reserve double credit | MUST_VERIFY_A0 | **closed in the A1 model** | The old ERM's shadow SOC is confirmed as a double-credit risk (INV-01) and is not in the A1 model. <br>The new storage reserve is tied to the dispatch SOC (test). <br>Thermal reserve and dispatch share one online capacity. <br>Reserve held during steps with simultaneous charge and discharge is reported. |
| TIME-01 1 h windows | DATA_READY_A0 | **closed** | 3 × 72 h of contiguous source rows, no DST hour, no resampling (vintage QA). |
| LOAD-01 existing customer protection | MUST_VERIFY_A0 | **closed in formulation** | Shed carries a dominant penalty and acceptance requires zero in B0 and BL. The v1.6 3 h tolerance (111.8 MWh) is not transferred. |
| HEAD-01 joint headroom | PENDING_A1_AUTH | **static formulation done** | Two LPs with the same λ and fixed 16-bus weights; built and checked without a solver. |
| HEAD-02 POI book | A0_LEDGER_ONLY | **done (preview)** | `POI_ELIGIBILITY_LEDGER_A0_PREVIEW.csv`: λ_POI = 0 in 2026–2028 for every book; 11,446.6 MW from 2029 with the upgrade. |
| SCEN-01 / SCEN-02 | DEFER | **not touched** | S0–S3 are not run. `rearch_mech.py --post-v16` exits 3 (POST_V16_MAINLINE_NOT_READY). |

## 3. Committed future public projects (record only; not in the 2025 A1 slice)

| Asset | Source | Committed status | MW | First availability | Cost treatment | In A1? |
|---|---|---|---|---|---|---|
| DWB Stage 2 (TPIT 69709 / 102815) | ERCOT Far West load-growth report 2026-02-04; COMMITTED_BASE_ASSETS.csv | MAIN committed | 1,000 (500–1,500) | ISD 2026.49, partial first year | Sunk / common baseline in all S0–S3, not a model-generated rescue line | no (ISD > 2025) |
| DWB Stage 5 (TPIT 92734) | TPIT 2026-07-13 workbook | SENSITIVITY only (planned, not committed) | 1,000 proxy | 2028.42 | Not in the main case | no |
| PBRP 765 kV A / B | SRC-01 / SRC-02 (PUCT approval Apr 2025; CCN in progress) | Committed in G-U / G-REAL | 2,400 each (SIL proxy) | ISD 2031.0 / 2031.5 | Sunk / committed in every scenario | no |

A2 must carry this table as its committed-public-project ledger. It must also keep any model-built expansion (priced corridors, public candidates) apart from it.
