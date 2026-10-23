# A1_EXECUTION_REPORT: A1_BLOCKED (LP-R post-solve output defect), 2026-10-22 New York time

```text
A1_APPROVAL: APPROVED (researcher, 2026-10-22; approved_by sw2434@cornell.edu; config-only commit f6dc3151fe9228f0d162829ee3df4224d1eeced1)
A1_LP_R: FAILED - failure_class output_failed (solver ok / optimal; acceptance could not be evaluated -> pass=False)
A1_LP_N: NOT_RUN (needs a PASSED LP-R; gate refuses)
A1_OPTIMIZER_CALLS_ACTUAL: 1 of 2 (0 retries)
H_RESOURCE_MW: NOT_AVAILABLE (unaccepted solver value below; not a result)
H_NETWORK_MW: NOT_AVAILABLE
A1_STATUS: A1_BLOCKED (cause: executor-side output code defect, not a physical infeasibility)
```

## 1. What ran

| Item | Value |
|---|---|
| Checkout | L2 A1 main checkout. HEAD `f6dc3151` = approval commit on top of `67deda8e`; `802c9d94` is an ancestor with 0 gated changes. The gate re-verified manifest, config and baseline SHAs: `approved=true`, `reasons=[]`. |
| Command | `THREADS=10 bash byop/run/run_post_v16.sh a1_lp_r`. L2 load was ~14 of 24 at launch (another user's jobs on ~12 cores); 244 GB memory free. |
| Ledger `HEADROOM_SOLVE_LOG.csv` | `LP_R_H_RESOURCE#1`: STARTED 02:54:01Z (22:54 EDT, written before the solver) → DONE 02:55:18Z; status `ok`, termination `optimal`, `failure_class=output_failed`, `pass=False`, 77.4 s. SHA-256 `05bd03c2…`. |
| Gurobi | 967,980 rows × 373,249 columns, presolved to 296,810 × 283,021. Barrier converged in 27 iterations (42.3 s); crossover 112,757 iterations; solved in 68.0 s total. **Optimal objective −2,587.772185.** |

## 2. Why it is BLOCKED (exact cause, reproduced without a solver)

- **Where it fails:** `run/post_v16_a1.py::solution_view` reads the reserve variables from linopy's **merged** `m.solution` Dataset. That Dataset's `name` coordinate is the union of every component's names. `PV16-res_su` therefore comes back with 485 columns (162 lines + 280 generators + 43 storage) instead of 43.
- **The crash:** `write_outputs` then indexes `su_effd[r_su.columns]` → `KeyError` (the line names `TL…` and generator names are not in the storage index).
- **The reproduction:** on L2 I built the same LP-R model (create_model only), injected a zero solution and called the same writer. It raises the identical `KeyError` at `post_v16_a1.py:130`. No solver was called and nothing was written to the A1 folder.
- **The model is not at fault:** a probe of the built LP shows `PV16-res_su` has exactly 43 storage units × 432 snapshots (18,576 variables). None is attached to a line or generator, and every reserve row covers exactly those variables.
- **Consequences:**
  - only `HEADROOM_BY_BUS_LP_R_H_RESOURCE.csv` was written (the writer's first step);
  - the reserve, shed, balance and network diagnostics were never produced;
  - the acceptance checks (zero existing shed in B0/BL, reserve met, balance residual ≤ 1e-3, λ finite and below the upper bound) were all recorded `False` because their inputs were missing;
  - the solved network was not saved, so acceptance cannot be evaluated after the fact.
- **The NEXT-02/03 dry and static checks missed it:** they built the models but never ran the writer on a solution.

## 3. Unaccepted solver value (for your information only, NOT a result)

`HEADROOM_BY_BUS_LP_R_H_RESOURCE.csv` (SHA-256 `551f57da…`):
- λ = 2,587.77 MW facility (IT 2,253.37 MW);
- distributed over the 16 buses by the fixed weights (sum w = 1), e.g. p610 2: 595.6 MW facility; p630 4: 452.1; p650 0: 305.8.

It is only the objective of an `ok/optimal` solve whose zero-shed / reserve / balance acceptance was **never checked**. It must not be reported as H_resource.

## 4. What was NOT done (your rules)

- No retry of LP-R and no LP-N. The gate now refuses both: LP-R "already has a logged call", LP-N "needs a PASSED LP-R".
- No ledger edit, no code fix in the A1 checkout, no change to the baseline or constraints.
- No A2 merge (G2 not passed).

## 5. Decision needed (G2): see `NEXT_04_RESEARCHER_DECISIONS.md`

**Option 1 (recommended): fix the reader, then re-authorise A1 as a fresh, explicitly budgeted run.**
- **The fix (output path only):** in `solution_view`, take every reserve/online variable from the variable itself (`m['PV16-res_su'].solution`, `m['PV16-res_thermal'].solution`, `m['PV16-online_cap'].solution`), not from the merged Dataset. Also save the solved network (or a compact solution file) **before** acceptance, so a writer failure never loses the solve again.
- **New static test:** a fake-solution writer test, the same pattern as the repro, so the defect cannot recur unnoticed.
- **No change to the LP:** the formulation, constraints, inputs and objective stay unchanged; the five A1 manifest code files would change (`post_v16_a1.py` only).
- **This needs from you:**
  - a new approvable commit (new manifest);
  - an explicit new budget. The ledger keeps `LP_R_H_RESOURCE#1` and is never cleared, so the gate needs either a new ledger file for "A1 rerun 1" or a config field you approve, e.g. `stage_budget: {LP_R_H_RESOURCE: 2}`;
  - a new config-only approval.
- **Cost:** about 1–2 min of solver time per LP.

**Option 2: written disposition.** Keep A1 = BLOCKED (tooling defect), record λ = 2,587.77 MW only as an unaccepted diagnostic, and let P2 (A2 merge) proceed. The package allows this only with your explicit written exception, because A1 was not "physically" interpreted.

**Option 3: stop here** pending further review.
