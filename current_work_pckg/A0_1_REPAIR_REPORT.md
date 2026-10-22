# A0_1_REPAIR_REPORT: A1 objective, gate and call-ledger repair (A0.2 P1, zero solver calls)

- Commits:
  - P1 code: **`ed72b20865eb152178068f7e51e8b8cc98024cd4`**, on top of A0 report `946406d1`.
  - Later A0.2 commits change the A1 code only by rebuilding the manifest.
- **Solver calls: 0.** Every test that touches a solve path uses a fake `solve_fn` or a monkeypatched function. The autouse fixture fails any test that reaches a real `linopy.Model.solve`.
- **Status:** `PRE_RUN_STATUS = READY_FOR_RESEARCHER_APPROVAL`. A1 remains `NOT_APPROVED`, with `approved_git_sha: null` and `approved_by: null`.

## FIX-01: strict max λ and hard zero existing shed (`byop/model/post_v16_headroom.py`)

- **Objective:** `m.objective = -λ` is the only term. The old `EPS_COST × dispatch cost + 1000 × shed − λ` is gone.
  - PyPSA needs cost terms to create the model, so the marginal costs stay in the network but are discarded when the objective is replaced.
  - `structural_checks` asserts that the objective contains only the λ variable, with coefficient −1.
- **Existing shed:** the `<bus> PV16 existing shed` generators are kept, with `p_max_pu = 0`, plus a hard row `PV16-existing_shed_zero`: `p == 0` for every shed unit, every snapshot, B0 and BL, LP-R and LP-N.
  - The check verifies sign `=`, rhs 0, the complete name set and all 432 snapshots.
  - If this makes the model infeasible, the result is `baseline_pressure_infeasible_resource_side` (LP-R) or `…_network_side` (LP-N), never "AIDC".
- **λ:** one global variable with the 16 fixed weights (unchanged). Acceptance requires λ < 200,000 × (1 − 1e-6), so a solution at the artificial cap fails.
- **Dispatch:** with no secondary cost term, the dispatch of a solution is a non-unique **optimal witness**. It must not be used for congestion or price attribution; the config says so.
- **Dry sizes on L2 (no solver):** LP-R and LP-N each have 373,249 variables and **967,980 constraints**, 0 integers. The 27,216 constraints added since A0 are the zero-shed rows (63 buses × 432 h).

## FIX-02: LP-R → LP-N strict gate and result acceptance (`post_v16_gate.py`, `post_v16_a1.py`)

- **Per-LP acceptance (`acceptance()`):**
  - `status == ok`, `termination == optimal`;
  - outputs written;
  - λ finite, ≥ 0 and below the artificial cap;
  - existing shed = 0 in B0 and in BL;
  - reserve met (slack ≥ −1e-3 MW);
  - bus balance residual ≤ 1e-3 MW.

  PASS means every check is true. The result is written to `<stage>_RESULT.json`.
- **LP-N gate (`prior_stage_pass`):** LP-N may start only if both hold:
  - the LP-R ledger row is DONE / ok / optimal / pass = True;
  - `LP_R_H_RESOURCE_RESULT.json` exists, is readable and has `acceptance.PASS is True` with every check true.

  An optimal entry in the log alone is not enough.
- **A1 combination (`combine()`):** `A1_PASS` only if both LPs PASS and 0 ≤ H_network ≤ H_resource + 1e-3 MW. Otherwise the result is **`A1_BLOCKED`**, and `A1_RESULT.json` / `JOINT_HEADROOM_RESOURCE_NETWORK.csv` are written. LP-N then exits with code 4; it no longer just prints False.
- **Counter-examples tested** (`test_gate_lp_n_needs_lp_r_result_pass_not_only_log`, `test_a1_pass_only_with_both_pass_and_order`, `test_optimal_with_positive_shed_or_residual_or_cap_fails_acceptance`), each refused or BLOCKED as expected:
  - optimal + missing result;
  - optimal + positive shed;
  - a PASS flag that contradicts its checks;
  - optimal with pass = False;
  - non-optimal;
  - H_network > H_resource;
  - LP-N not PASS;
  - missing LP-R result;
  - λ at the cap;
  - NaN λ;
  - balance residual 0.5 MW.

## FIX-03: call ledger written before the solver (`post_v16_a1.py`)

- **Before each solve:** `start_attempt()` appends a `STARTED` row (attempt_id, UTC, stage, attempt, manifest SHA, base SHA) by write + fsync + atomic rename. Only then is the solver called.
- **After:** `finish_attempt()` fills the same row (DONE / ERROR, status, termination, failure class, pass). It never adds or deletes a row.
- **Gate:** any ledger row of the stage, in any state, consumes it (zero retries). The budget counts every row, maximum 2. An unreadable or malformed ledger is refused, never treated as empty.
- **Tested:**
  - the ledger already holds STARTED when the fake solver is entered;
  - a crash (KeyboardInterrupt) leaves an ERROR row and refuses a rerun;
  - a leftover STARTED row blocks the stage;
  - finishing fills the same row;
  - a corrupted or malformed ledger is refused.

## FIX-04: failure evidence

- **Failure classes:**
  - `solver_failed`: exception, or a non-optimal return that is not infeasible;
  - `baseline_pressure_infeasible_resource_side` / `_network_side`;
  - `output_failed`: post-processing exception (never PASS);
  - `acceptance_failed`.
- **Recording:** each class is written to the RESULT JSON and the ledger, with no automatic retry. The RESULT JSON keeps the status, termination, summary and error text.

## Researcher A0.1 decisions recorded (config `reserve.researcher_decision`, `headroom.inherited_ramp`)

- **Reserve proxy:** R = 3,000 MW, τ = 1 h, 10 min; CCGT 0.50 / 4 %/min; OCGT 0.40 / 10 %/min; coal / gas steam / biomass 0.40 / 2 %/min. These are **permitted as the A1 physical proxy**; the evidence class stays PENDING, and this is not a solve authorisation.
- **Inherited ramp:** 460.73 MW IT remains protected existing load. Native Load 2025 may already contain part of it; there is no overlap estimate and no reduction of Native Load. A1 is not a historical replay.

## Gate verdict and tests

- **Gate:** see `A1_GATE_VERDICT.json` (at the final code commit on L2). It is refused only on the approval fields, and for LP-N additionally "needs a PASSED LP_R".
- **Tests on L2:** `test_a0_1_repair.py` 9 passed; `test_post_v16_a0.py` 30 passed (A0 tests updated to FIX-01 / 02 / 03); full suite in `A0_2_TEST_SUMMARY.json`.
