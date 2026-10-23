# A2_SOLVER_ACCOUNTING_AUDIT (NEXT-03 A2-FIX-09)

**A2_SUBCALL_ACCOUNTING_QA: PASS (static, 0 solver calls).**
- Branch `work/a2-postv16-static`.
- Tests: `byop/tests/test_next03_a2_static.py`. The plan is in `A2_OPTIMIZER_CALL_PLAN.json`; the forced-failure results are in `A2_GATE_FAILURE_INJECTION_QA.json`.

## 1. What "two calls" meant, and what it means now

NEXT-02 carried `max_lp_calls: 2`. That counted **scenario attempts** (the S0 and S1_EARLIEST parent rows), not optimizer calls. The actual call chain is:

```
rearch_mech.go(tag) -> post_v16_solve_wrapper   [parent row STARTED in A2_SOLVE_LOG.csv]
  -> v240.solve -> wp2.solve -> PyPSA solve_network -> n.optimize -> create_model
       -> extra_rearch -> lex_presolve -> gurobipy Model.optimize()      [S1 only: child S1_SPEED_HIERARCHY]
  -> linopy.Model.solve                                                   [child S0_COST / S1_COST]
```

`lex_presolve` therefore runs **inside** the S1 parent attempt; it does not bypass the gate. The budget is now stated in two separate parts in `config.byop_post_v16_a2.yaml`:

| Budget | Value | Ledger |
|---|---|---|
| `max_scenario_attempts` | 2 (S0, S1_EARLIEST) | `A2_SOLVE_LOG.csv` (parent) |
| `max_top_level_optimizer_calls` | 3 (S0_COST, S1_SPEED_HIERARCHY, S1_COST) | `A2_OPTIMIZER_CALL_LOG.csv` (child, with `parent_attempt_id`) |
| Gurobi hierarchical passes | Metadata only (`n_objectives` per call); not authorisable calls | Child row of S1_SPEED_HIERARCHY |

## 2. Interception: by explicit instrumentation, not by claims

- **linopy (PyPSA's cost stage).** `linopy.Model.solve` is a plain Python method. `_arm_post_v16_optimizer_lock` replaces it with a controlled entry that:
  - refuses outside the wrapper;
  - writes a STARTED child row (S0_COST / S1_COST, `n_vars`, `n_cons`) **before** calling the solver;
  - fills the same row with DONE / ERROR, status, termination and seconds.
  Any other linopy solve inside a parent (for example a second cost solve) gets the kind `UNPLANNED_LINOPY_SOLVE` and is refused.
- **gurobipy.** `gurobipy.Model` is a C extension type, so its `optimize` cannot be reliably patched. NEXT-02 had a try/except patch that silently failed. That claim is withdrawn: `PV16_LOCK['gurobipy_locked']` is now explicitly `False`. Instead, the one direct gurobipy call on the A2 path, `lex_presolve`'s `gm.optimize()`, is **instrumented in its own code**: `A2G.child_start('S1_SPEED_HIERARCHY', n_vars, n_cons, n_objectives)` runs before it and `child_finish` after. Outside an armed parent, `child_start` refuses.
- **Static scan of every optimizer call site in the model code:**
  - `rearch_mech` 1194 (`lex_presolve`, instrumented);
  - 1418/1423 and 1536/1542 (S2 developer LPs, not reachable from `--scenarios S0 S1_EARLIEST`; through linopy they would be refused as unplanned);
  - `v240_mech` 768 and `v250_mech` 313/318 (legacy / S2 paths, same);
  - `wp2.solve_network` (the cost stage).
  PyPSA-USA's iterative line re-solve is skipped because the model has no extendable Lines (log: "No expandable lines found"). If it ever re-solved, the second linopy call would be refused as an unplanned kind and the run would stop, so it fails closed.

## 3. Failure rules

| Situation | Result | Test |
|---|---|---|
| Hierarchical pre-solve raises or is not optimal | Child ERROR, parent ERROR, exception re-raised; nothing is deleted | `test_injection_hierarchy_failure_marks_child_and_parent_error` |
| Hierarchy DONE, then the cost stage crashes | Hierarchy DONE, S1_COST ERROR, parent ERROR | `test_injection_cost_failure_after_hierarchy_success` |
| Solve returns "optimal" without any logged optimizer call | Acceptance FAIL (`optimizer_calls_complete` = False), parent DONE with pass = False, STOP | `test_injection_missing_child_call_fails_acceptance` |
| Crash right after the parent STARTED row; second command | Gate refuses: the stage already has a logged call (zero retries); the row is kept | `test_injection_crash_second_run_corrupt_ledger_and_skipping_s0` |
| Corrupt parent or child ledger | Gate refuses (unreadable / malformed); files are kept | same |
| S1 requested without a PASSED S0 | Gate refuses | same |
| Child outside a parent, kind not in the plan, repeated kind | SystemExit before any call | `test_child_calls_need_a_started_parent_and_the_plan` |
| Third top-level call already used | Gate refuses | `test_top_level_budget` |
| linopy solve outside the wrapper | SystemExit; `gurobipy_locked` reported False | `test_linopy_lock_refuses_outside_wrapper` |

## 4. Lexicographic order kept and verified

S1_EARLIEST keeps the fixed order:
1. per year, maximise total online IT (A1_y);
2. maximise the fair share z_y (A2_y);
3. fix those levels (1e-6 relative / 1e-3 MW);
4. minimise real social cost (PyPSA cost stage).

There is no large-weight penalty. **New:** acceptance re-checks every A1_y level against the **cost-stage** solution (`speed_levels_hold`; Σ IT `p_nom_opt` per year ≥ level × (1 − 1e-6) − 2e-3 MW). If a level is lost, S1 fails.

## 5. Related strictness (A2 W2.3 item 4)

The S1 no-harm comparison no longer fills missing data:
- S0 writes `S0_NO_HARM_REFERENCE.csv` (each `load_shed` unit × snapshot) after its acceptance PASS, and its SHA goes into `S0_RESULT.json`.
- The gate refuses S1 if the file is missing or its SHA differs.
- S1 acceptance FAILs if units or snapshots differ or are duplicated. It also checks that the D24 row's rhs equals the reference + 0.001 MW (to 1e-6), so the row was built from exactly that reference.

Unit test: `test_no_harm_reference_is_strict`, which also covers a tampered reference.
