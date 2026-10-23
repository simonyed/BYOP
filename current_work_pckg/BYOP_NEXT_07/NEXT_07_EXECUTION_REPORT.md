# NEXT_07_EXECUTION_REPORT (2026-10-23, New York time)

```text
WORK_PACKAGE: BYOP_NEXT_07
SOURCE_MAIN_SHA: bcd9844d2cda985d9c369e89aca2020a25e5def3 (rechecked: main = mainline-v13-stageA = L2 at start)
START_HEAD: bcd9844d2cda985d9c369e89aca2020a25e5def3
END_HEAD: see NEXT_07_RESULTS_INDEX.json (report commit on mainline-v13-stageA); W2 approvable code SHA 5df4dda75efc4efb1796393c1131f93a8d801599; W4 branch work/next07-a3-static 79134c9fc3499e923240e1ed537ef2d8b87dc5da (not merged)
ORIGINAL_S0_S1_CODE_SHA: cdfdea06146a6fe73df89cb410d6a88cb5fda306
W0_DATA_QA: PASS
W1_RESERVE_RHS_ONLY_STATIC: PASS
W2_NEW_SOLVER_CALLS: 0
W2_AUTHORIZATION: NOT_APPROVED
W2_SOLVER_AND_ACCEPTANCE: NOT_RUN
W2_RHS_CHANGED_ONLY: YES
W3_S0_RELIABILITY_VERDICT: BASELINE_RELIABILITY_UNRESOLVED
W3_FULL_YEAR_DIAGNOSTIC: NOT_AUTHORIZED
W4_A3_RUNTIME_STATIC: PARTIAL
A3_SOLVER_CALLS: 0
ORIGINAL_A2_LEDGERS_UNCHANGED: YES
NEXT_DECISION_REQUIRED: approve or decline the single W2 reserve-probe LP at 5df4dda75efc4efb1796393c1131f93a8d801599 (S0, 2026-2031, 26 weeks, reserve RHS 0, 1 S0_COST call, 0 retries)
```

**Optimizer calls in this package: 0.** Every model was built with `linopy.Model.solve` and `gurobipy.Model.optimize` intercepted.

## W0: corrected shed reconciliation (`W0_*`)

The reconstruction matches every reported total (residual < 0.0003 MWh). The weights sum to 8,760 h in every year. All shares below are weighted MWh ÷ weighted MWh.

| Quantity | Value | Share and denominator |
|---|---:|---|
| 2026–2031 sum of model-year weighted shed | 54,205.78 MWh | Sum of six model years, **not** a single-year EENS |
| 2026 native | 51,049.28 MWh | 94.2 % of the 2026–2031 sum |
| SAMPLED_WEEK snapshots, all years | 46,871.78 MWh | **86.5 %** of the sum, all of it in 2026 |
| B7_STRESS_ONLY, all years | 7,334.00 MWh | 13.5 % (weight 3 h) |
| Far West pocket, 2026 (both kinds) | 47,449.95 MWh | 87.5 % of the sum (sampled-week part 85.2 %); 92.9 % of 2026 |
| 2026 raw 3 h shed | 5,990.80 MWh | **= SAMPLED_WEEK 1,812.72 + B7 4,178.08.** Only the first part is multiplied by 25.857 (giving 46,871.8). The B7 part keeps weight 3 h. |

**Errata to the NEXT-06 report wording.** The signed NEXT-06 reports are not rewritten; this table is the correction.
- "94 % Far West" should read 87.5 %. The 94 % figure is all 2026 shed as a share of the 2026–2031 sum.
- "94 % = two weeks × 25.86" should read 86.5 %.
- "5,991 MWh × 25.86" is wrong: only 1,812.7 MWh of it is from the sampled weeks.

**By bus, 2026:**
- p620 6: 96.3 % sampled-week (30,046 MWh); 3.7 % stress-day (1,154 MWh).
- p620 7: 99.3 % sampled-week.
- p620 3: 61 % stress-day.
- p630 2: 100 % stress-day.
- p610 4: about 0. It is in the pocket by topology, not by shed.

## W1: reserve-RHS-only probe (`W1_*`, L2, 160 s)

**How the probe is built:**
- `add_operating_reserve(..., reserve_MW=None|0.0)` is passed per build; `POST_V16` is never mutated.
- The value is accepted only from the exact `config.byop_post_v16_n07_reserve_probe.yaml`. That config pins S0, its own out_dir, run_args 2026–2031 / 26 weeks / [S0], and a budget of 1 / 1.
- Every other config carrying a `diagnostic` block is refused by the guard, the A2 gate and the A3 gate.

**Solver-free proof.** REF (formal), PROBE and REF2 (formal again) were built in one process.
- **REF vs PROBE: exactly one difference.** `PV16M-reserve_req` RHS goes 3000 → 0 on all 816 rows.
- Everything else is equal: variables, bounds, all 1,015 constraint groups (coefficients, signs, RHS), objective, network inputs, weights.
- All reserve-side rows are present in both: online capacity, min-load, headroom, ramp, BESS energy at the end and start of each snapshot, and 35 segment-SOC groups.
- **REF2 == REF** (0 differences), so the probe leaves no state behind.
- **Size:** 2,660,074 variables / 7,107,710 constraints / 35,171,029 nonzeros, identical to the formal S0.

**Persisted state.** `persist_solution` now also writes, before acceptance and straight from the linopy solution:
- `reserve_by_snapshot` (total, RHS, dual, thermal / BESS reserve, online capacity, dispatch, available capacity, shortfall versus the formal 3 GW);
- per-unit online capacity, thermal reserve, BESS reserve and available thermal capacity.

**Tests.** L2 full suite at the frozen code: **272 passed / 0 failed** (256 + 16 new).

## W2: approval request (`W2_APPROVAL_REQUEST.md`)

- Approvable SHA: **`5df4dda75efc4efb1796393c1131f93a8d801599`**, equal to L2 and GitHub `mainline-v13-stageA`.
- The manifest was built on L2 (150 code + 110 input files, 0 mismatches).
- The gate refuses **only** on the three approval fields.
- Budget: 1 S0_COST call, 0 retries.
- Expected cost: about 40 min and about 15 GB.
- Not run.

## W3: S0 decision (`W3_*`)

- **M** stays open until W2 runs.
- **T, partly answered without an LP:**
  - the sampled weeks are typical for the pocket (night load at the 48th percentile);
  - S0 delivered 458–537 MW (median 499 MW) into the pocket at the shed snapshots;
  - a constant 499 MW night supply reproduces the actual sampled-week shed (1,832 vs 1,786 MWh) and implies about 61 GWh over all 2026 nights;
  - so there is no evidence that the weights over-extrapolate under the A2 rules, but the supply level is endogenous.
- **The prepared NEXT-06 full-year LP is not runnable.** The zero-solver build fails with `KeyError: 'Generator-p_nom'` because a single-period 2026 model has no extendable generator. Its SHA `e2daf9d3` is also stale. → `NOT_AUTHORIZED`; it would need a fix, a measured size and its own approval.
- The proposed verdict stays `BASELINE_RELIABILITY_UNRESOLVED`. The A3-gated status file is unchanged.
- A paired S0/S1 rerun is not justified: there is no bug evidence.

## W4: A3 static (`W4_A3_STATIC_READINESS.md`; branch `work/next07-a3-static`)

**Built:**
- A3 runtime accounting covering every planned call kind (S0, S1 with its hierarchy, S3, S2 developer lex ≤ 6, developer cost and public LPs, S3_mS2).
- A fail-closed `a3_guard` and `a3_solve_wrapper`.
- A2-reproduction checks with SHA-pinned references.
- S2 convergence handling: no S3_mS2 and no efficiency claim when S2 has not converged.
- The matched-service audit.
- The conservative RE+BESS firm rule (F ≤ 0) in S2 and S3 alike.

**Results:**
- W4 branch full suite: **289 passed / 0 failed**.
- The real CLI refuses A3 with exit 3 before building.
- **Not merged:** it merges after W2 is sealed or declined, followed by an A3 manifest rebuild.
- Remaining gaps: an end-to-end A3 build dry run (injected gate, zero solve) and the runtime check of the supply-pool rows.

## Files

- `current_work_pckg/BYOP_NEXT_07/`:
  - `W0_SHED_RECONCILIATION_CORRECTED.csv`, `W0_RECONCILIATION_VERDICT.json`;
  - `W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json`, `W1_CONSTRAINT_DIFF.csv`;
  - `N07_RESERVE_PROBE_PRE_RUN_MANIFEST.json`, `W2_APPROVAL_REQUEST.md`;
  - `W2_RESERVE_CAUSAL_COMPARISON.csv` (NOT_RUN), `W2_RESERVE_CAUSAL_VERDICT.md` (NOT_RUN);
  - `W3_S0_SCIENTIFIC_DECISION.md`, `W3_S0_RELIABILITY_VERDICT_PROPOSAL.json`, `W3_FULLYEAR_DECISION_TABLE.csv`;
  - `W4_A3_STATIC_READINESS.md`;
  - `NEXT_07_RESULTS_INDEX.json`, `NEXT_07_RETURN_PACKAGE.zip`.
- `workflow/results/BYOP/next07_s0_reserve_probe/`:
  - `_static_w1/`;
  - `W3_REPRESENTATIVENESS*`, `W3_POCKET_LOAD_FULL_YEAR_3H.csv.gz`;
  - `_fullyear_size/SIZE_BUILD_FAILURE.excerpt.log`;
  - `_w4_static/`;
  - `N07_TESTS.log`.
- Code on `main`-line:
  - `byop/post/next07_w0_reconcile.py`;
  - `byop/tests/structural_n07_reserve_probe.py`, `byop/tests/test_next07_reserve_probe.py`;
  - edits to `post_v16_mainline.py`, `rearch_mech.py`, `post_v16_a2_gate.py`, `post_v16_a3_gate.py`;
  - `run_post_v16_a2.sh` (`n07_*` commands).
- Code on the W4 branch: `post_v16_a3_runtime.py`, `next07_w3_representativeness.py`, `structural_n07_fullyear_size.py`, `test_next07_a3_runtime.py`.

**Originals unchanged:** `POST_V16_A2_S0S1/*` (SHA-checked: results, both ledgers, no-harm reference, frozen shed), `next06_s0_diagnostic/`, `BYOP_NEXT_06/`, `POST_V16_A1_HEADROOM/`.
