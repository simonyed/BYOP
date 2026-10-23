# OVERNIGHT_EXECUTION_REPORT: BYOP NEXT-05 v2 (2026-10-22 23:57 → 2026-10-23 ~04:45 EDT)

```text
WORK_PACKAGE: BYOP_NEXT_05_OVERNIGHT_v2
AUTHORIZATION_MODE: USER_ADVANCE_AUTHORIZATION_WITH_INDEPENDENT_GATES (researcher chat approval, see OVERNIGHT_AUTHORIZATION_RECORD.md)
A1_FIX_APPROVED_CODE_SHA: 07c881a4c643a800dfc55257716671e2791a48ab
A1_HISTORICAL_LP_R_1: SOLVER_OPTIMAL_OUTPUT_FAILED (consumed 1)
A1_HISTORICAL_CALLS: 1
A1_RERUN_LP_R: PASS
A1_RERUN_LP_N: INFEASIBLE (baseline_pressure_infeasible_network_side)
A1_RERUN_CALLS_ACTUAL: 2
A1_RERUN_AUTH_CONFIG_COMMIT: e4bfbe7fb11e05d691b60c49e9e717d50d4b5617 (closed again in cdfdea06)
A1_H_RESOURCE_MW: 2587.77 (facility; IT ~2253.37)
A1_H_NETWORK_MW: NOT_AVAILABLE
A1_G2: A1_FIXED_NETWORK_EXCEPTION
A2_MERGE: PASS (merge 8e4ad312; revalidation 248/0, structural 75/75, manifest 149+110 / 0 mismatches)
UNIFIED_MAIN_SHA: cdfdea06146a6fe73df89cb410d6a88cb5fda306 (approved A2 code; mainline-v13-stageA, later commits reports / post-processing only)
A2_AUTH_CONFIG_COMMIT: see git log "A2 approval (config-only)" on mainline-v13-stageA (approved_git_sha cdfdea06)
A2_SCENARIO_ATTEMPTS: 2
A2_TOP_LEVEL_CALLS: 3 (S0_COST, S1_SPEED_HIERARCHY [12 objectives], S1_COST)
S0: PASS
S1_EARLIEST: PASS
S0_S1_COMPARISON: DELIVERED (S0_S1_MAINLINE_COMPARISON.csv, S0_S1_MAINLINE_FINDINGS.md); exploratory with method flags (S0 existing-customer shed 54,206 MWh)
A3_TOP_LEVEL_CALLS: 0
S2_S3_PILOT: BLOCKED (no independent A3 gate / call plan; S0 reliability flag pending review)
NEXT_SAFE_ACTION: STOP - researcher review of the S0 reliability flag and S1-S0 findings; A3 gate + instrumentation is a separate development step before any S2 / S3 solve
```

## Milestones (EDT)

| Time | Step | Evidence |
|---|---|---|
| 23:57 | H0: state verified (HEAD `5380f0f5`, 0 gated drift, pins OK, no running jobs) | `OVERNIGHT_START_SNAPSHOT.json` |
| ~00:02 | First attempt to record the approval from the package text only was **refused by the permission system**. After the researcher's chat approval: A1 config-only commit `e4bfbe7f`. | `OVERNIGHT_AUTHORIZATION_RECORD.md` |
| 00:04–00:06 | A1 rerun1 LP-R: optimal, **PASS**, H_resource = 2,587.77 MW | `A1_RERUN_EXECUTION_REPORT.md` |
| 00:06–00:26 | A1 rerun1 LP-N: **infeasible** (network side) → G2 `A1_FIXED_NETWORK_EXCEPTION` | same; solver-free corridor diagnostic |
| 00:26–00:47 | H2: A2 merged (no conflicts, A1 fix kept, `.gz` binary OK). Regression 244/4: the 4 assumed the A1 config was unapproved; A1 approval closed; then **248/0**. Structural 75/75. A2 manifest rebuilt. | `A2_MERGE_AND_REVALIDATION_REPORT.md` |
| 00:49 | A2 config-only approval (`approved_git_sha cdfdea06`); A2 gate approved S0 | git log |
| 00:50–01:29 | **S0_COST optimal (2,281 s), S0 PASS**; SHA-pinned no-harm reference written | `S0_RESULT.json`, ledgers |
| 01:29–03:35 | **S1_SPEED_HIERARCHY optimal** (12 objectives, 7,433 s) | child ledger |
| 03:35–04:24 | **S1_COST optimal (2,859 s), S1 PASS**: no-harm, speed levels held, calls complete | `S1_EARLIEST_RESULT.json` |
| 04:31 | Final collector step crashed on newline-only `s0cal_line_flows.csv` (post-v1.6 has no S0CAL). Fixed (skip empty), re-run **post-process only**: TECHNICAL_GATE PASS. | `A2_COLLECT_POSTPROCESS.log`, `MAINLINE_GATE_CHECKS.csv` |
| ~04:45 | S1−S0 comparison, findings, SOC-audit gap record; **STOP before A3** | this report |

## Why A3 (S2/S3) was not started

Package §7 / §8 and the truncated A3 clause of the approval require:
- S0 and S1 PASS (met);
- an **independent A3 gate / manifest / parent-child ledger** that refuses extra calls and survives crashes;
- a common conservative firm rule for S2/S3.

None of these A3 mechanisms exists yet:
- the S2 developer LPs call linopy/Gurobi directly and are refused as unplanned by the A2 lock;
- there is no A3 call plan or budget enforcement.

Building them is a development task, not a solve. The S0 reliability flag (§3 of the findings) should also be reviewed first, because S2/S3 inherit the same public world. **0 A3 calls; nothing in the A3 budget was used.**

## Other notes

- **SOC audit gap:** `A2_SOC_SEGMENT_POSTSOLVE_AUDIT.csv` has status `NOT_DERIVABLE_FROM_PERSISTED_OUTPUTS`. The run did not export storage SOC; the fix for the next run is noted there. No re-solve was done for it.
- **Tooling fixes made overnight** (post-processing only, after the solves): `collect_mainline.py` empty-file guard. The model code in the solved runs is exactly the approved `cdfdea06`.
- **Git:**
  - `main` (GitHub `be2c6904`) is an ancestor of the unified mainline and is fast-forwarded to it.
  - The temporary branches `work/a2-postv16-static` and `integrate/next05` (local) are kept.
  - No force push.
