# NEXT_03_EXECUTION_REPORT: BYOP-POST-V16-NEXT-03 (2026-10-22, New York time)

## Stage conclusions

| Stage | Outcome |
|---|---|
| **H1: A1** | No researcher approval was received, so **NOT_RUN** and 0 solver calls. The W1.1 read-only recheck on L2 HEAD `303eb35b` is **PASS_READY_FOR_A1_APPROVAL** (`A1_FINAL_RECHECK_NEXT03.json`, `NEXT03_A1_{DRY,GATE}.log`). `A1_FINAL_APPROVAL_REQUEST.md` is updated. |
| **H3: A2 static** | **PASS.** FIX-08: SOC segment neutrality; PyPSA cross-gap linking confirmed on the real model and cut. FIX-09: separate attempt / top-level-call budgets, child-call ledger, failure injection 11/11, strict no-harm reference, speed levels re-checked. FIX-01..07 retained. Tests: structural 75/75, A2 worktree 245/0, fresh LF clone 243/0/2, new unit tests 15/15. The A2 gate stays LOCKED; the request is in `A2_PRE_SOLVE_RESEARCHER_DECISION.md`. |
| **W3: S0/S1** | **NOT_RUN** (no A2 approval): `S0_S1_EXECUTION_REPORT.md` |
| **W4: A3** | Handoff only: `A3_NEXT_GATE_HANDOFF.md` |

## Decisions recorded from the researcher this round

None. No approval or decision was given. D2, D4, D5, D6, D7 and A1-APPROVAL remain open.

## Git state

- **Mainline `mainline-v13-stageA`:**
  - started at `303eb35be204a37a9f3d11d5f8037235dba38410`;
  - ends at the sync commit that contains this report. It changes reports and results only, with 0 changes under the A1-gated paths since `802c9d94`; the A1 gate was re-run after sync.
- **A2 `work/a2-postv16-static`:**
  - started at `fa93d257eaa11d207324afb5f97e210a364e3708`;
  - code `81bd57438c7b002d6cfe455ec2b3f973f33ed12c`;
  - head `39a74ff5f96acafc356d40978e33048768fce6a7` (manifest / verdict); pushed to GitHub and fast-forwarded on L2.
- **No new remote branch, no force push, no tag.** The A1 tag is created only after A1 PASS.

## New or updated deliverables (`current_work_pckg/`)

- **A1:**
  - `A1_FINAL_APPROVAL_REQUEST.md` (updated);
  - `A1_FINAL_RECHECK_NEXT03.json`;
  - `A1_EXECUTION_REPORT.md` (NOT_RUN).
- **A2 FIX-08 (SOC segments):**
  - `A2_REPRESENTATIVE_PERIOD_SOC_BOUNDARY_AUDIT.md`;
  - `A2_SOC_SEGMENT_MAP.csv`;
  - `A2_SOC_BOUNDARY_TESTS.json`.
- **A2 FIX-09 (call accounting):**
  - `A2_SOLVER_ACCOUNTING_AUDIT.md`;
  - `A2_OPTIMIZER_CALL_PLAN.json`;
  - `A2_GATE_FAILURE_INJECTION_QA.json`.
- **A2 request:**
  - `A2_PRE_SOLVE_RESEARCHER_DECISION.md` (updated);
  - `A2_GATE_VERDICT.json`;
  - `A2_PRE_RUN_MANIFEST.json`;
  - `A2_REGRESSION_SUMMARY.json`.
- **S0/S1 and A3:** `S0_S1_EXECUTION_REPORT.md` (NOT_RUN), `A3_NEXT_GATE_HANDOFF.md`.
- **Package:** `NEXT_03_RETURN_PACKAGE.zip`.
- **Evidence logs:**
  - `workflow/results/BYOP/post_v16_a2_static/NEXT03_*.log`;
  - `_structural_next03/`;
  - L2 `POST_V16_A1_HEADROOM/NEXT03_A1_*.log`.

## Notes

- The A2 authorisation source pinned by the A2 gate is now the NEXT-03 package text. The NEXT-02 text stays in place.
- **Archiving:** the A0.2 / NEXT-01 / NEXT-02 files stay in `current_work_pckg/` until A1 is frozen, because pinned paths refer to them.
- **One technical correction to NEXT-02:** its claim that gurobipy was locked by a monkey-patch is withdrawn. gurobipy cannot be patched; the hierarchical Gurobi call is now instrumented explicitly instead.

```text
WORK_PACKAGE: BYOP-POST-V16-NEXT-03
A1_MAINLINE_START_SHA: 303eb35be204a37a9f3d11d5f8037235dba38410
A1_MAINLINE_FINAL_SHA: the NEXT-03 sync commit on mainline-v13-stageA that contains this file (reports / results only)
A2_BRANCH_START_SHA: fa93d257eaa11d207324afb5f97e210a364e3708
A2_BRANCH_FINAL_SHA: 39a74ff5f96acafc356d40978e33048768fce6a7 (code 81bd57438c7b002d6cfe455ec2b3f973f33ed12c)
BASELINE_SHA256: a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16
A1_RESEARCHER_APPROVAL: NOT_APPROVED
A1_GATE_STATUS: REFUSED only on run_authorization / approved_by / approved_git_sha (LP-N also needs LP-R PASS); recheck PASS_READY_FOR_A1_APPROVAL at 303eb35b
A1_SOLVER_CALLS_ACTUAL: 0
A1_LP_R_STATUS: NOT_RUN
A1_LP_N_STATUS: NOT_RUN
H_RESOURCE_FACILITY_MW: NOT_AVAILABLE
H_NETWORK_FACILITY_MW: NOT_AVAILABLE
A2_SOC_SEGMENT_QA: PASS (static; 24/24 within-period gaps linked by PyPSA and cut; 11,305 rows S0/S1, 12,985 S3; LP only)
A2_SUBCALL_ACCOUNTING_QA: PASS (static; failure injection 11/11; budgets 2 attempts / 3 top-level calls)
A2_REGRESSION_PASS_FAIL_SKIP: worktree 245/0/0; fresh LF clone 243/0/2 (v1.6 baseline only on L2)
A2_STRUCTURAL_PASS_FAIL: 75/0
A2_RESEARCHER_APPROVAL: NOT_APPROVED
A2_SCENARIO_ATTEMPTS: 0
A2_TOP_LEVEL_OPTIMIZER_CALLS_ACTUAL: 0
A2_GUROBI_HIERARCHY_OBJECTIVE_COUNT: NOT_RUN
A2_S0_STATUS: NOT_RUN
A2_S1_EARLIEST_STATUS: NOT_RUN
A3_SOLVER_CALLS: 0
S0_S1_COMPARISON_STATUS: NOT_RUN
PROXY_LIMITS: single weather year; gas L2 3y; 8 sites UNKNOWN_CONSERVATIVE; sampled 3h (2 weeks + 3 stress days per period, energy-neutral segments); reserve aggregate LP proxy
OPEN_RESEARCHER_DECISIONS: A1-APPROVAL; D2 (p650 0 = L2); D4 (stores 3 h + start/end SOC + segment neutrality); D5 (DWB 2019 USD / PBRP 2024 USD proxy, unpaid shares assumed); D6 (no-harm +0.001 MW, strict reference); D7 (A2: 2 attempts / 3 top-level calls at 81bd5743, after A1 review)
DELIVERABLES_AND_SHA256: NEXT_03_RETURN_PACKAGE.zip / FILE_LIST_SHA256.txt
```
