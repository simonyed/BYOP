# current_work_pckg: the current work package and its reports

Storage rules (set by the researcher on 2026-10-20):

| Content | Location | Uploaded to GitHub / L2? |
|---|---|---|
| The work package currently being executed (placed here by the researcher) | `pypsa-usa/current_work_pckg/` | Yes |
| Reports based on that package: decision log, execution report, sync report, etc. | `pypsa-usa/current_work_pckg/` | Yes |
| Raw data the package needs, plus preprocessing scripts and their logs | `D:\BYOP_impact\work_pkgs\<folder for the package>\` | **No** (local only) |
| Preprocessed data that the model actually reads | The designated place inside pypsa-usa, e.g. `workflow/byop/inputs/<category>/`, with a source note | Yes |
| Executed programs and run configuration | `workflow/byop/{model,build,post,run,tests}/`, `workflow/config/config.byop_*.yaml` | Yes |
| Run results and logs (small files only) | `workflow/results/BYOP/`, `workflow/logs/byop/` | Yes (`.nc` and other large files are excluded) |

Project-level documents that span work packages are in `workflow/byop/docs/`.

## Current work package: BYOP-POST-V16-NEXT-03 v1.0 (2026-10-22): A1 recheck, A2-FIX-08 / FIX-09, S0/S1 request

- **Original:** `BYOP_POST_V16_NEXT_03_v1.0/BYOP_POST_V16_NEXT_03_A1_A2_Formal_S0_S1_Execution_2026-10-22.md` (byte-identical; LF SHA `f1b1a249…`, pinned by the A2 gate). Local copy: `work_pkgs/BYOP_POST_V16_NEXT_03_v1.0/`.
- **Outcome:** 0 solver calls. A1 recheck PASS; A1 NOT_APPROVED. A2 static PASS: SOC segment neutrality, child-call ledger, structural 75/75, regression 245/0. A2 gate LOCKED. S0/S1 NOT_RUN. A3 handoff only.
- **Archiving deferred** (as for NEXT-02): the NEXT-02 text stays in place, and the earlier packages stay until A1 is frozen.

| File | Status |
|---|---|
| `NEXT_03_EXECUTION_REPORT.md` | Stage summary and fixed return block |
| `A1_FINAL_APPROVAL_REQUEST.md` (updated), `A1_FINAL_RECHECK_NEXT03.json`, `A1_EXECUTION_REPORT.md` | PASS_READY_FOR_A1_APPROVAL; NOT_RUN |
| `A2_REPRESENTATIVE_PERIOD_SOC_BOUNDARY_AUDIT.md`, `A2_SOC_SEGMENT_MAP.csv`, `A2_SOC_BOUNDARY_TESTS.json` | FIX-08 PASS (static) |
| `A2_SOLVER_ACCOUNTING_AUDIT.md`, `A2_OPTIMIZER_CALL_PLAN.json`, `A2_GATE_FAILURE_INJECTION_QA.json` | FIX-09 PASS (static) |
| `A2_PRE_SOLVE_RESEARCHER_DECISION.md` (updated), `A2_GATE_VERDICT.json`, `A2_PRE_RUN_MANIFEST.json`, `A2_REGRESSION_SUMMARY.json` | STOP: A2 approval requested (code `81bd5743`) |
| `S0_S1_EXECUTION_REPORT.md` | NOT_RUN |
| `A3_NEXT_GATE_HANDOFF.md` | Handoff only; A3 NOT_APPROVED |
| `NEXT_03_RETURN_PACKAGE.zip` | Return package |

## Previous: BYOP-POST-V16-NEXT-02 v1.0 (2026-10-22): A1 approval request, A2 static repairs and gate, S0/S1 request

- **Original:** `BYOP_POST_V16_NEXT_02_v1.0/BYOP_POST_V16_NEXT_02_A1_to_Formal_S0_S1_2026-10-22.md` (byte-identical; SHA-256 `a6baf464…`, pinned by the A2 gate). Local copy: `work_pkgs/BYOP_POST_V16_NEXT_02_v1.0/`.
- **Scope this round:** A1 read-only recheck and approval request; A2-FIX-01..07 static work on branch `work/a2-postv16-static`; A3 handoff. **0 solver calls** (A1, A2 and A3 all NOT_APPROVED).
- **Archiving of A0.2 / NEXT-01 deferred.** These stay in place until A1 is frozen:
  - `POST_V16_A1_PRE_RUN_MANIFEST.json`, which the A1 config pins;
  - `BYOP_A0_2_PreSolve_Integration_v1.1/`, which `test_a0_2_tech_v2.py` reads;
  - the A1 pre-approval files.
  Moving them would change what the pending A1 approval refers to.

| File | Status |
|---|---|
| `NEXT_02_EXECUTION_REPORT.md` | Status block and summary |
| `A1_FINAL_APPROVAL_REQUEST.md`, `A1_FINAL_RECHECK.json`, `a1_final_recheck_next02.py` | Recheck PASS_READY_FOR_A1_APPROVAL; A1 NOT_APPROVED, NOT_RUN |
| `A1_EXECUTION_REPORT.md` | NOT_RUN (NEXT-01 file, unchanged) |
| `A2_EXPANSION_PAIR_AND_COST_AUDIT.md`, `PUBLIC_EXPANSION_CAPACITY_RIGHTS_QA.csv`, `PUBLIC_EXPANSION_COST_COD_AUDIT.csv`, `COMMITTED_PUBLIC_ASSET_COST_LEDGER.csv` | PASS (static) |
| `A2_RESERVE_SOC_TIME_QA.md` | PASS (static), plus a stores-weighting fix needing your confirmation |
| `NATIVE_LOAD_NO_HARM_QA.csv`, `S0_S1_IDENTICAL_PUBLIC_INPUTS.json` | PASS (static) |
| `A2_EOL_SHA_PORTABILITY_REPORT.md`, `A2_REGRESSION_SUMMARY.json` | See report |
| `A2_PRE_RUN_MANIFEST.json`, `A2_GATE_VERDICT.json` | Gate LOCKED (NOT_APPROVED) |
| `A2_PRE_SOLVE_RESEARCHER_DECISION.md` | STOP: A2 approval requested |
| `A3_READINESS_HANDOFF.md` | Static only; A3 NOT_APPROVED |
| `NEXT_02_RETURN_PACKAGE.zip` | Reports, SHA list, branch diff, static logs |

## Previous package (archive deferred): BYOP A0.2 v1.1 + NEXT-01

**BYOP A0.2 v1.1: pre-solve model integration (A0.1 repair + TECH_COMP_2 + environment -> permit -> COD), 2026-10-22. Authorised scope: code / inputs / static tests only (zero solver calls).**

- Original package: `BYOP_A0_2_PreSolve_Integration_v1.1/` (EXECUTION_WORK_PACKAGE.md, ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md, original v2.0 ZIP + 9 files, tools, static examples; byte-identical); full local copy `work_pkgs/BYOP_A0_2_PreSolve_Integration_v1.1/`
- Technology inputs (byte-identical, SHA-pinned): `workflow/byop/inputs/tech_calibrated_v2/`
- Archived on 2026-10-22: post-v1.6 A0 and its reports -> `_completed/BYOP_Post_v1.6_Execution_v1.1_A0/`

| File | Content | Status |
|---|---|---|
| `A0_2_INTEGRATION_REPORT.md` | Decision + acceptance, fixed return block | READY_FOR_RESEARCHER_APPROVAL; 0 solver calls |
| `A0_1_REPAIR_REPORT.md` | FIX-01..04 evidence | PASS_STATIC |
| `TECH_V2_IMPLEMENTATION_AUDIT.md` | TECH_COMP_2 landing, v1.3 -> v2 differences | Done |
| `SOURCE_TO_PARAMETER_CROSSWALK.csv` | source -> loader -> state -> build / constraint -> ledger -> test | 147 rows |
| `TECH_COST_AND_COD_AUDIT.csv`, `PERMIT_TO_COD_CAUSAL_AUDIT.csv` | costs, COD milestones, permit attribution (ENV-01..10 + 16 buses) | DRY_NOT_SOLVED |
| `TECH_PERMIT_STATUS.csv` | 16 research buses: site FIPS / ozone class / flags | 8 known, 8 UNKNOWN_CONSERVATIVE |
| `TECH_SUPPLY_USAGE_STATIC_QA.csv`, `TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv`, `TECH_EMISSIONS_PROXY_STATIC_QA.csv`, `TECH_RE_BESS_FIRM_STATIC_QA.csv` | pools / rights, environment evidence, PTE / ledger, RE+BESS firm builder | DRY_NOT_SOLVED |
| `A2_TECH_READINESS_MATRIX.csv` | READY_STATIC / NOT_IMPLEMENTED / BLOCKED per module | Done |
| `A0_2_TEST_SUMMARY.json`, `A1_GATE_VERDICT.json`, `POST_V16_A1_PRE_RUN_MANIFEST.json` | L2 tests 196 passed; gate NOT_APPROVED; manifest (locked) | Done |
| `A0_2_RETURN_PACKAGE.zip` | Small files for local / L2 / GitHub reconciliation | Done |

### BYOP-POST-V16-NEXT-01 (2026-10-22): A0.2 acceptance, A1 pre-approval, A2 / A3 static (0 solver calls)

| File | Status |
|---|---|
| `NEXT_STAGE_EXECUTION_REPORT.md` | Fixed header; A1 NOT_RUN (not approved) |
| `A1_PREAPPROVAL_CHECK.md`, `A1_PREAPPROVAL_GATE.json`, `a1_preapproval_check.py` | P0 PASS; approvable commit 802c9d94 |
| `A1_EXECUTION_REPORT.md` | NOT_RUN |
| `A2_STATIC_INTEGRATION_REPORT.md`, `A2_READINESS_MATRIX.csv` | PASS_STATIC on branch `work/a2-postv16-static` @ ba73e600 (not merged) |
| `PERMIT_GAS_EVIDENCE_PRIORITY.csv`, `PERMIT_TO_COD_CAUSAL_AUDIT_VNEXT.csv`, `PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv`, `ENVIRONMENT_MECHANISM_LIMITATIONS.md` | A3 PASS_STATIC |
| `NEXT_STAGE_RETURN_PACKAGE.zip` | Return package |
