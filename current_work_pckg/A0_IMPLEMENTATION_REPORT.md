# A0_IMPLEMENTATION_REPORT: post-v1.6 execution package v1.1, stage A0 (zero solver calls)

- Date: 2026-10-22 (New York time). Branch `mainline-v13-stageA`.
- Commits:
  - Start HEAD: `0b417903c7704c00de609581646fed29723397cf`, identical locally, on GitHub and on L2.
  - **Code: `453e846f440c592dcffe7eca9319584d883d6eb0`** (A0 implementation), then **`80e1835f6626ebb61e3f454ca63e852b7bad80a0`** (gate approval rule: an approval commit that touches only the A1 config is accepted; manifest rebuilt).
  - Report: the commit that contains this file.
- **Solver calls in A0: 0.** No Gurobi, PyPSA `optimize`, `solve_model` or mock solver was called. An autouse test fixture fails any test that attempts a solve. `run_authorization` remains `NOT_APPROVED` everywhere.
- Not run: legacy `step0`, `pilot_s01`, `pilot_core`, attribution, S0–S3, national runs, 2050.

## 1. What A0 did

1. **Verification:**
   - HEAD and branch match the package.
   - The v1.6 `prepared.nc` SHA matches on L2.
   - The v1.6 baseline checks hold: 63 buses, 162 lines, 155,446.9 MW, 2 switchable plant groups with monthly caps, and x/r and s_nom as in the v1.6 identity QA.
   - The old manifests have SHA drift but remain NOT_APPROVED (`OLD_MANIFEST_SHA_DIFF.json`).
   - Details: `POST_V16_A0_RECONCILIATION.md`.
2. **Package placement and data:**
   - The package documents are in `current_work_pckg/BYOP_Post_v1.6_Execution_v1.1/`.
   - `raw/` went to a new, separate staging directory, `workflow/data/byop/post_v16_execution_v11/raw/` (local + L2, not git); `derived/` went to `workflow/byop/inputs/post_v16/derived/`.
   - SHA QA: 53/53 files and 20/20 raw registry entries match. The package's `build_research_data.py`, re-run on a scratch copy, reproduces all 19 derived files (text-identical after line-ending normalisation).
   - Official files are unchanged.
   - v1.6 was archived to `_completed/BYOP_Calibration_Closeout_v1.6/`.
3. **Constraint audit:** `BASELINE_AND_RESERVE_CONSTRAINT_INVENTORY.csv`, 21 old and 2 new items, each with exact file:function:line and constraint names, when it is enabled, its double-count risk and the keep/replace/remove decision. Key findings:
   - **The old 15 % snapshot ERM uses its own shadow storage system.** `reserves.py:35` has a separate `state_of_charge_RESERVES` that is not linked to the dispatch SOC, so the same battery energy can serve dispatch and the full ERM credit (REL-04). It is injected into every legacy solve (`wp2_ercot_s0_s1.py:156-158`), summed into one TX row (`v250_mech.py:204`), and lowered per period by ERM-02 B (`v240_mech.py:567-588`).
   - **S0CAL** (`rearch_mech.py:565`) turns S0 deficits into cost-free fixed links in every scenario from 2026 (REL-02).
   - **E1 gate:** applies `--base` only after the gate and never hashes it (`rearch_mech.py:1748`, CODE-02). `run_mainline.sh` never passes `--base`, so the pre-v1.6 baseline is the default (CODE-01).
   - **Committed TPIT (DWB Stage 2, 1,000 MW at ISD 2026.49) and PBRP (2 × 2,400 MW, 2031):** exogenous pre-commitments with sources, treated as sunk in all scenarios. They are not model-generated, and they are not in the 2025 A1 slice.
4. **Isolated post-v1.6 entry and gate:**
   - **New files:** `run_post_v16.sh`, `byop/run/post_v16_a1.py`, `byop/model/post_v16_gate.py`, `config.byop_post_v16_a1.yaml` and `current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json`. The manifest pins 5 code files, 10 inputs, the normalised config and the v1.6 base SHA.
   - **Gate checks:**
     - approval fields;
     - approved SHA == HEAD, or an ancestor with only the A1 config changed since;
     - clean code / config / inputs (CR-at-EOL ignored, because the L2 checkout shows CRLF-only differences as modified; no untracked files);
     - package SHA;
     - manifest SHAs;
     - **the SHA of the actual `--base` file** (no fallback);
     - stage list and order (LP-R before LP-N);
     - zero retries and the 2-call budget.
   - **Legacy protection:**
     - `run_mainline.sh` refuses `step0`, `pilot*`, `attribution` and `run` for any post-v1.6 config (exit 6), while still reproducing legacy runs unchanged.
     - `rearch_mech.py --post-v16` refuses `--calibrate`, `--erm-cal`, `--s0-calibrate`, `--s0-cal-file` and any base other than the SHA-pinned v1.6 file. It then always exits 3 with `POST_V16_MAINLINE_NOT_READY`, because the new reserve rule is not yet in the multi-period mainline (A2 item).
5. **New A1 model (built, not solved):** `byop/model/post_v16_headroom.py`, formulation in `POST_V16_A1_FORMULATION.md`.
   - 1 h continuous windows from source rows; 6 blocks (λ = 0 and λ × 3 pre-registered windows).
   - 3,000 MW / τ = 1 h system reserve:
     - thermal reserve through an LP online-capacity relaxation (no binaries) with min stable load and 10-min ramp;
     - storage reserve tied to the **dispatch SOC**;
     - no reserve credit for wind, solar, nuclear, shed or AIDC.
   - The same λ applies at the 16 dynamic_pnnl_v1 buses with fixed facility weights.
   - LP-R uses the same lines and KVL with limits lifted (connected); LP-N uses the v1.6 limits.
   - The POI book (H_POI) is a separate ledger, not an LP.

## 2. Fixed return

```text
EXECUTION_STATUS: READY_FOR_A1_APPROVAL
BRANCH_AND_START_HEAD: mainline-v13-stageA @ 0b417903c7704c00de609581646fed29723397cf (local = GitHub = L2, no drift)
CODE_COMMIT_SHA: 80e1835f6626ebb61e3f454ca63e852b7bad80a0 (A0 code 453e846f + gate approval-rule fix); report commit = the commit containing this file
V16_NC_PATH_AND_SHA_VERIFIED_ON_L2: workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc = a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16 (verified on L2; raw eb659f9b…); 63 buses / 162 lines / 155,446.9 MW / 2 switchable cap groups
SOURCE_AND_DERIVED_DATA_SHA_QA: PASS - 53/53 vs ORIGINAL_RESEARCH_FILES_SHA256.json, 20/20 raw vs SOURCE_REGISTRY.csv; rebuild of 19 derived files text-identical (CRLF only); official files unchanged (STAGING_SHA_QA.json)
BASELINE_2025_FROZEN_AND_LIMITATIONS: v1.6 file only (gate + guard, no fallback); limitations carried: 4,000.1 MW thermal PRM-basis gap unexplained, DR/PUN/RMR/DC ties not modelled, West Texas Export not reproduced, v1.6 3 h LP2 shed 111.8 MWh (not comparable with 1 h), year-end stock x 2025 load (not a replay), MORA outages not applied
ERM02_AND_S0CAL_LEGACY_DISABLE_AUDIT: old 15 % ERM (shadow SOC double-credit risk), ERM-02 B and free S0CAL are absent from the A1 model (asserted: no *_RESERVES / ERM rows) and refused by rearch_mech --post-v16; run_post_v16.sh DRY passes none of --calibrate/--erm-cal/--s0-calibrate/--s0-cal-file; legacy step0 refuses post-v1.6 configs (exit 6) and still reproduces legacy configs
NEW_RESERVE_MODEL: 3000 MW, tau=1h, fixed exogenous; eligible = CCGT/OCGT/gas_steam/coal/biomass (online-capacity LP relaxation: p<=c<=p_nom*avail, p>=pmin*c, r<=c-p, r<=rho*c, rho=min(1-pmin, ramp*10min)) + hydro + storage (r<=p_nom-p_d+p_s, tau*r/eff_d<=dispatch SOC); not eligible: nuclear, wind, solar, load shed, AIDC; claim = "load deliverable on the network while the system aggregate reserve holds" (NOT deliverable reserve, NOT N-1); pmin / ramp values = executor assumptions with sources, PENDING APPROVAL
STRESS_VINTAGE_AND_DST_QA: 3 pre-registered 72 h windows (08-17..19 incl. load peak HE18 + net peak HE21 as ONE window; 02-19..21; 07-29..31 hold-out), contiguous source HE rows, 0 DST hours, no resampling; load = Native Load 1 h (= v1.6 3 h load to 1.8e-12 MW on 70 complete steps); renewables = v1.6 model p_max_pu held 3 h (not observed output, not the same weather year); STRESS_SOURCE_VINTAGE_QA.json
H_RESOURCE_VS_H_NETWORK_STATIC_FORMULATION: two LPs with identical variables / constraints (373,249 vars, 940,764 cons, 0 integers each; asserted equal sizes); same lambda x w_b at 16 buses (sum w = 1, facility MW; IT = facility / PUE 2031); B0 block certifies lambda = 0 feasibility inside the same LP; LP-R = same lines + KVL, limits 1e6 MVA, one connected component; acceptance 0 <= H_network <= H_resource + 1e-3 MW, zero existing shed, exact optimal
POI_ELIGIBILITY_SCOPE: separate H_POI book (no LP): pre-approved E0 / all E0 rows / + POI upgrade (earliest COD 2029) / conditional PCLR (never firm); lambda_POI = min cap_b / w_b (valid only for independent fixed rights, unchanged network); A0 preview: 0 in 2026-2028 (11 of 16 buses without qualified equipment), 11,446.6 MW from 2029 with the upgrade (binding p630 4)
SOLVER_CALLS: 0
TESTS_PASS_FAIL_SKIP: L2 (pypsa 1.3.0, at 80e1835f): 161 passed / 0 failed / 0 skipped (test_post_v16_a0 29 + v1.6 + C0 + C0 repair + C1 + v1.5 + dynamic siting + mainline), 11 warnings (pandas str-dtype FutureWarning in pypsa io, linopy include_objective_constant FutureWarning, numpy ABI RuntimeWarning); local (no pypsa): 114 passed / 0 failed / 47 skipped
DRY_COMMANDS_AND_EXPECTED_A1_SOLVE_BUDGET: see section 3; A1 = at most 2 LPs (LP-R then LP-N), 0 retries, each ~0.37 M vars / 0.94 M cons, estimated 1-10 min and < 10 GB on 20 threads (estimate from the v1.6 LP2: 1.62 M vars / 4.54 M cons in 257 s; NOT measured)
GATES_AND_UNRESOLVED_BLOCKERS: A1 gate verdict at 80e1835f on L2 = refused only for run_authorization / approved_by / approved_git_sha (all SHA, manifest, base and clean-tree checks pass). No blocker for A1. Open for approval: reserve parameter values (pmin / ramp, response window), thermal availability without MORA outages, inherited-ramp treatment as existing load. Open for A2: the 3 GW reserve rule is not yet in the multi-period mainline (rearch_mech --post-v16 exits 3); committed-project ledger; DWB / PBRP cost treatment
DELIVERABLES_AND_SHAS: section 4 and A0_RETURN_PACKAGE.zip (FILE_LIST_SHA256.txt inside)
NEXT_RESEARCHER_DECISION: approve or reject A1 after reading the artifacts (approve = set run_authorization APPROVED, approved_by, approved_git_sha = the report commit or 80e1835f, in an approval commit that changes only config.byop_post_v16_a1.yaml; optionally change the pending reserve parameters first, which needs a new A0 manifest)
```

## 3. Exact DRY commands (`DRY=1 bash byop/run/run_post_v16.sh <stage>` on L2)

```text
a1_dry   CMD python -W ignore /datasets/prgm/BYOP_impact/pypsa-usa/workflow/byop/run/post_v16_a1.py --base /datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc --threads 16 --dry
a1_lp_r  CMD python -W ignore /datasets/prgm/BYOP_impact/pypsa-usa/workflow/byop/run/post_v16_a1.py --base /datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc --threads 16 --lp R
a1_lp_n  CMD python -W ignore /datasets/prgm/BYOP_impact/pypsa-usa/workflow/byop/run/post_v16_a1.py --base /datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc --threads 16 --lp N
a2_s0s1  CMD python -W ignore /datasets/prgm/BYOP_impact/pypsa-usa/workflow/byop/model/rearch_mech.py --mainline --post-v16 --config config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml --base /datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc --case-id POST_V16_A2_S0S1 --out /datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1 --start 2026 --end 2031 --sample-weeks 26 --threads 16 --scenarios S0 S1_EARLIEST    (shape only; refused: exit 3)
```

- **A1 after approval:** `THREADS=20 bash byop/run/run_post_v16.sh a1_lp_r`, then `a1_lp_n` only if LP-R is exact optimal with zero existing shed.
- **L2 thread budget:** run them sequentially, because LP-N needs the LP-R result. Use B ≈ 20 threads after checking `uptime`.
- **Outputs:** `results/BYOP/POST_V16_A1_HEADROOM/`:
  - `HEADROOM_SOLVE_LOG.csv`, `LP_*_RESULT.json`;
  - `HEADROOM_BY_BUS_*.csv`, `STRESS_DISPATCH_RESERVE_QA_*.csv`, `NETWORK_PRESSURE_DIAGNOSTICS_*.csv`;
  - `JOINT_HEADROOM_RESOURCE_NETWORK.csv`;
  - the POI ledger.
  - The A1 report and manifest are written after the runs.

## 4. Deliverables

| File | Content |
|---|---|
| `current_work_pckg/A0_IMPLEMENTATION_REPORT.md` | This report |
| `current_work_pckg/POST_V16_A0_RECONCILIATION.md` | v1.6 items closed / carried; verification; committed-project table |
| `current_work_pckg/BASELINE_AND_RESERVE_CONSTRAINT_INVENTORY.csv` | Constraint audit with decisions |
| `current_work_pckg/POST_V16_A1_FORMULATION.md` | Static A1 formulation |
| `current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json` | A1 pins (not an approval) |
| `workflow/config/config.byop_post_v16_a1.yaml` | A1 request, `NOT_APPROVED` |
| `workflow/byop/inputs/post_v16/POST_V16_RESERVE_PARAMETERS.csv` | Reserve parameters with sources (pending approval) |
| `workflow/byop/inputs/post_v16/STAGING_SHA_QA.json` | Data SHA QA |
| `workflow/results/BYOP/POST_V16_A1_HEADROOM/A1_DRY_CHECK.json`, `STRESS_SOURCE_VINTAGE_QA.json`, `POI_*_A0_PREVIEW.csv`, `OLD_MANIFEST_SHA_DIFF.json`, `A1_GATE_VERDICT.json`, `A0_TESTS_L2.log`, `A1_DRY_CONSOLE.log` | A0 outputs (no solver) |
| `current_work_pckg/A0_RETURN_PACKAGE.zip` | The above, plus `git diff` 0b417903..80e1835f (code / config / docs) and FILE_LIST_SHA256.txt |

## 5. Reserve parameter sources (all executor assumptions pending approval; no value was tuned)

- **Reserve amount:** 3,000 MW and τ = 1 h, from the package (`PARAMETER_CANDIDATES.csv`; ERCOT 2024 ELCC Study Appendix B). 4,000 MW is not run.
- **Response window:** 10 min, from the ERCOT ECRS response rule. NPRR 1282 sets the ECRS duration to one hour, which matches τ = 1 h.
- **CCGT:** 4 %/min ramp, 50 % min load ("usual" values in the VGB PowerTech table, ADB Asia Clean Energy Forum 2018).
- **Coal and other steam (gas steam, biomass):** 2 %/min ramp, 40 % min load (VGB "usual").
- **OCGT:** 10 %/min ramp, 40 % min load. Wärtsilä gives about 50 %/min for aeroderivative units and a 40–50 % emissions floor for most gas turbines. No public figure was found for the frame-unit fleet, so the base ramp is conservative.
- **Hydro:** eligible within its availability.

**Interpretation boundary:**
- A1 will measure the joint connection capability of the given AIDC distribution under the stated stress and reserve proxy on a 64-bus synthetic network.
- It is **not** real ERCOT headroom, an interconnection-capacity figure, an N-1 result or a LOLE/LOLH result.
- A0 has produced no headroom number.
