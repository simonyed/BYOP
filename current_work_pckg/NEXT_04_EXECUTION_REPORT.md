# NEXT_04_EXECUTION_REPORT: BYOP-POST-V16-NEXT-04 (2026-10-22, New York time)

```text
WORK_PACKAGE: BYOP-POST-V16-NEXT-04
A1_APPROVAL: APPROVED (researcher 2026-10-22, approved_by sw2434@cornell.edu, config-only commit f6dc3151fe9228f0d162829ee3df4224d1eeced1)
A1_LP_R: FAILED (solver ok / optimal; post-solve output reader KeyError -> acceptance not evaluable -> failure_class output_failed, pass=False)
A1_LP_N: NOT_RUN (requires a PASSED LP-R)
A1_OPTIMIZER_CALLS_ACTUAL: 1
H_RESOURCE_MW: NOT_AVAILABLE (unaccepted objective 2587.77 MW facility recorded for information only)
H_NETWORK_MW: NOT_AVAILABLE
A1_RESEARCHER_REVIEW: PENDING (G2 decision requested: Option 1 fix reader + re-authorise / Option 2 written exception / Option 3 stop)
A2_MERGE: NOT_STARTED
UNIFIED_MAIN_SHA: NOT_AVAILABLE
A2_STATIC_REVALIDATION: NOT_RUN
A2_APPROVAL: NOT_APPROVED
A2_SCENARIO_ATTEMPTS_ACTUAL: 0
A2_TOP_LEVEL_OPTIMIZER_CALLS_ACTUAL: 0
S0: NOT_RUN
S1_EARLIEST: NOT_RUN
S0_S1_COMPARISON: NOT_AVAILABLE
A3_SOLVER_CALLS_ACTUAL: 0
RESEARCHER_DECISIONS_REMAINING: G2 (A1 blocked disposition), D2, D4, D5, D6, G3/D7 (A2 approval on a future merged SHA)
```

## Sequence

| Phase | Outcome |
|---|---|
| **P0** | **PASS** (read-only; `NEXT_04_APPROVAL_STATUS.md`) |
| **G1** | Your words: "I approve A1 (LP-R then LP-N, max 2 calls, 0 retries) at approved_git_sha 802c9d9414514641fd2b088b45ec7ea945be18a4". `approved_by` = `sw2434@cornell.edu`, given explicitly in reply to my question. Config-only commit `f6dc3151`, synced to L2 and GitHub; the gate then approved LP-R. |
| **P1, LP-R** | 22:54 EDT, THREADS = 10. Gurobi optimal in 77 s (objective −2,587.772). The output reader crashed (merged `m.solution` coordinates), so acceptance could not be evaluated. Ledger: DONE / ok / optimal / output_failed / pass = False. **Cause reproduced without a solver; the LP formulation itself is sound** (`A1_EXECUTION_REPORT.md` §2). |
| **P1, LP-N** | Not run (rule: LP-R must PASS). |
| **G2** | **STOP: decision requested** (`A1_EXECUTION_REPORT.md` §5). |
| P2–P4 | Not started. The A1 checkout is untouched since the run; no A2 merge. |

## Evidence

On L2 in `workflow/results/BYOP/POST_V16_A1_HEADROOM/`, pulled to GitHub by the sync tool (small files):

| File | SHA-256 |
|---|---|
| `HEADROOM_SOLVE_LOG.csv` | `05bd03c2fa629f7af0f1f767d9d9758bd5b156856c00f5d75ce06a5e7142e28d` |
| `LP_R_H_RESOURCE_RESULT.json` | `d80d6f9e11b3765699ddc052021c06742f26e0a2d288daeafc81ad8d0162bd27` |
| `HEADROOM_BY_BUS_LP_R_H_RESOURCE.csv` | `551f57dad0ed4eb67d2f4452c6ec9e6e7bb7438e3af1b92270844467489083f5` |
| `A1_LP_R_CONSOLE.log` | `13ab4ab141fe54dc4caae54b3c359be2fcc5a8abc79cb6ed92a2c606b85e89b7` (contains the full Gurobi log) |
