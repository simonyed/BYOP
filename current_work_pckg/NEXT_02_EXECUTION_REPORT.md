# NEXT_02_EXECUTION_REPORT: BYOP-POST-V16-NEXT-02 (2026-10-22, New York time)

```text
START_MAINLINE_SHA: b2b2e48e5c3c782e13ccfe5511e652018a92673d (mainline-v13-stageA; A1 approvable code 802c9d9414514641fd2b088b45ec7ea945be18a4)
START_A2_BRANCH_SHA: ba73e600aa260b8f09ee9bd0d0084a98431c98d1
FINAL_MAINLINE_SHA: the commit containing this report (reports / results only; 0 changes under the A1-gated paths since 802c9d94)
FINAL_A2_BRANCH_SHA: fa93d257 (work/a2-postv16-static; code a7f195b239a739101c2bb8cd53f495febbf0e789 + manifest / verdict commit)
V16_BASELINE_SHA256: a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16
A1_RESEARCHER_APPROVAL: NOT_APPROVED (A1_FINAL_APPROVAL_REQUEST.md submitted; no approval evidence)
A1_LP_R: NOT_RUN
A1_LP_N: NOT_RUN
A1_SOLVER_CALLS: 0
A1_RESULT: NOT_AVAILABLE
H_RESOURCE_FACILITY_MW: NOT_AVAILABLE
H_NETWORK_FACILITY_MW: NOT_AVAILABLE
A2_EXPANSION_PAIR_INTEGRITY: PASS (324 AC_exp pairs x S0 / S1 / S3 tied by the pre-existing M2-line_sym equality (+ redundant upstream bidirectional_link row); rev-only rejected; fwd priced once; corridor cap row)
A2_SOC_RESERVE_QA: PASS (static; start AND end-of-snapshot SOC reserve rows; stores weighting fixed from ~77 h to the elapsed 3 h on the post-v1.6 path - needs D4 confirmation)
A2_ALL_REGRESSIONS: PASSED (L2 A2 worktree 230 passed / 0 failed / 0 skipped; fresh LF clone 228 passed / 0 failed / 2 skipped (L2-only baseline); 66 / 66 structural; 0 solver)
A2_STATIC_READINESS: PASS_STATIC
A2_RESEARCHER_APPROVAL: NOT_APPROVED (A2_PRE_SOLVE_RESEARCHER_DECISION.md submitted)
A2_S0: NOT_RUN
A2_S1: NOT_RUN
A2_SOLVER_CALLS: 0
A3_SOLVER_CALLS: 0
NEXT_DECISION: A1_APPROVAL (then, separately, A2_APPROVAL)
```

## 1. W1: A1 (not authorised, not run)

The read-only recheck ran on the **L2 A1 main checkout**: `a1_final_recheck_next02.py` → `A1_FINAL_RECHECK.json`. Result: `PASS_READY_FOR_A1_APPROVAL`.

- **Commit:** HEAD `b2b2e48e` descends from `802c9d94` with no change under the gated paths; the worktree is clean.
- **Pins:** all 5 code and 10 input SHAs, the normalised config, the authorisation source and the v1.6 `.nc` match.
- **Ledger:** absent (0 of 2 calls used).
- **Dry builds (create_model only):** unchanged at 373,249 variables / 967,980 constraints / 0 integers. 432 × 1 h snapshots; objective −λ; 27,216 zero-shed rows; weights sum to 1; LP-R line limits > LP-N.
- **Gate:** refuses only on the three approval fields (LP-N also on the LP-R order).

Request: `A1_FINAL_APPROVAL_REQUEST.md`, a config-only commit with `approved_git_sha: 802c9d94…`. `approved_by` is left for you. `A1_EXECUTION_REPORT.md` stays NOT_RUN.

## 2. W2: A2 static repairs (branch `work/a2-postv16-static`, not merged; the A1 checkout is untouched)

| Item | Outcome |
|---|---|
| FIX-01 | **No free reverse build.** Every pair has `M2-line_sym_<fwd>` (`v240_mech.extra`, reached through `v250.extra_gce` → `rearch_mech.extra_rearch` with the shared `STATE`), plus `M2-line_cap_<corridor>`, plus the upstream `bidirectional_link` equality. The audit and ledger now *require* the verified row. Nothing was rewritten. |
| FIX-02 | 1,818 public candidates are all inactive, dispatch-masked and capacity-free before COD, and priced. The 2027→2029 counterexample (62 cases) is unavailable in 2027/28 in S0 and S1. DWB/PBRP absolute costs are in a new ledger outside the objective: 371 M$ SOURCED; 2 × 3,020 M$ PROXY; sunk/unpaid shares are assumptions → **D5**. |
| FIX-03 | **Finding:** in the multi-period mainline the SOC advanced by the ~77 h sampled-week weight, not 3 h. Fixed on the post-v1.6 path (`stores` = 3 h; objective and generator weights unchanged). Added a start-of-interval reserve energy row from PyPSA's own balance (exact, conservative). Thermal r ≤ c − p, ramp and min-load rows confirmed. |
| FIX-04 | S1 D24 no-harm row covers all 68 existing-customer shed units (63 native + 5 inherited ramp) and no AIDC unit. S0 ≡ S1 public inputs (per-table hashes equal). |
| FIX-05 | S0/S1 carry no RE+BESS firm rows. 48/72 h certification → A3 prerequisite. |
| FIX-06 | Content-strict, EOL-portable pin checks (tests and the A2 manifest). **Finding:** `derived/ERCOT_OPERATIONAL_WIND_SOLAR_2023_2025.csv.gz` has been a corrupt (LF-converted) blob in git since `453e846f` because `workflow/byop/** text eol=lf` forced text. Fixed on the A2 branch (binary exemption + correct bytes). It stays corrupt on the mainline/GitHub until A1 is frozen; A1 does not read it. |
| FIX-07 | Independent A2 gate, config, ledger and manifest (149 + 110 files). `rearch_mech --post-v16` is fail-closed and allows only [S0] → [S1_EARLIEST]. STARTED is written before each solve, and acceptance runs after it. No optimizer call outside the wrapper. `A2_GATE_VERDICT.json` = LOCKED. |

Structural run (L2, `results/BYOP/post_v16_a2_static/_structural_next02/`): **66/66 PASS**, 3 solver calls intercepted, 0 executed. Variables / constraints:
- S0: 2,660,074 / 7,096,405
- S1_EARLIEST: 2,712,538 / 7,284,741
- S3: 2,978,054 / 7,811,038

Request: `A2_PRE_SOLVE_RESEARCHER_DECISION.md`. **STOP:** A2 needs its own approval (D4, D5, D6, D7).

## 3. W3 / W4

- **W3 (S0/S1 formal runs): not executed** (no A2 approval), so there is no `S0/S1_EXECUTION_REPORT` and no `S0_S1_COMPARISON.csv`.
- **W4:** `A3_READINESS_HANDOFF.md` (static only; A3 NOT_APPROVED).

## 4. Process notes

- **Archiving.** The A0.2 / NEXT-01 files stay in `current_work_pckg/`, because the pending A1 approval and the A1 config pin some of them. They will be archived after A1 is frozen.
- **Solver calls this round:** A1 0, A2 0, A3 0.
- **L2 load:** 16–20 of 24 logical cores were in use by other users during this round. Proposed threads at launch: 24 minus the measured load, at least 4.
