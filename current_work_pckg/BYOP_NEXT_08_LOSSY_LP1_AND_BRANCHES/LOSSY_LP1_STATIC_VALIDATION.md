# LOSSY_LP1_STATIC_VALIDATION (NEXT-08 C4): 0 optimizer calls

## 1. Real-model static build (`results/BYOP/next08_lossy_lp1/LOSSY_LP1_BUILD.json`, L2)

| Check | Result |
|---|---|
| LP1 (IT1) model size | **2,093,803 variables / 6,902,966 constraints** (v1.6 LP1: 1.62 M / 4.54 M) |
| Loss rows | `Line-loss_upper` + 4 `Line-loss_tangents-*`; `Line-loss` variable present |
| Capacity variables | `Line-s_nom` on all 162 lines; `s_nom_min` = raw; `s_nom_max` = 2.0 × v1.6 prepared (finite on every line) |
| Objective prices | uplift `capital_cost` = 2e6 on every line (unchanged v1.6 price); shed units at 1e6 USD/MWh (63 buses) |
| Fleet | 264 generators (incl. 63 shed), 43 storage units, 2,920 snapshots, 0 committable |
| r / x | r scaled on exactly the 18 v1.6-uplifted lines (Σr 1,836 → 1,680 Ω at s_ref = v1.6); **x identical to the raw network** |
| Candidate built from the v1.6 capacities (no file) | x = raw; Σr = 1,680 Ω, equal to the W6 R_PARALLEL network |
| Solver | not called (`linopy.Model.solve` intercepted) |

## 2. Zero-solver end-to-end chain on the real networks

`results/BYOP/next08_lossy_lp1/_zero_solver_chain/NEXT08_ZERO_SOLVER_CHAIN.json`: **ZERO_SOLVER_CHAIN_PASS**.

All three stages run through `loss_basis_lp1.run` with the **real stage-order rules**. Only the approval, SHA and manifest reasons are dropped, and the ledger and candidate are scratch. A fake solve writes capacities at `s_nom_min` (no uplift); gurobipy optimize raises.

| Stage | Outcome (synthetic numbers) | Checked |
|---|---|---|
| LP1_LOSSY_IT1 | optimal; **not r-converged** (r from v1.6 capacities vs raw "solution": 18 lines off, max 0.82 on TL35); no candidate | `LP1_LINE_SOLUTION.csv`, QA, shed, events, `line_loss` |
| LP1_LOSSY_IT2 | allowed by the gate (IT1 not converged); r from the IT1 solution; **converged** (gap 2e-16); guards G1–G3 pass; **candidate NetCDF written** (scratch) | same + candidate |
| LP2_LOSSY_CANDIDATE | allowed only now (converged, guards pass, candidate present); LP2 C1 rules on the candidate, losses on | QA, `line_loss`, shed, flows |

**Also checked:**
- 3 fake calls in total.
- Ledger: three DONE rows.
- A retry is refused ("already has a logged call").
- Frozen v1.6 `prepared` / `raw_uncalibrated` SHAs unchanged.
- The real ledger was never written.

## 3. Unit tests (`byop/tests/test_next08_lossy_lp1.py`, 11 tests) and regression

| Test | What it proves |
|---|---|
| config locked / budget / rules | NOT_APPROVED; 3 stages; ≤ 3 calls; 0 retries; losses 2; cap 2.0; G1 1.5×; G3 1,000 MVA; pinned authorisation SHA; own out_dir |
| stage order (6 cases) | IT2 only after an optimal, non-converged IT1. LP2 only after an optimal, converged, guard-passing LP1 with a candidate on disk. ERROR / unconverged-IT2 / guard-fail all refuse. |
| r proxy / convergence / guards | r never above raw; convergence by r gap or 10 MVA; G1 / G2 (cap) / G3 (new lines) each trigger |
| **setup equals v1.6 LP1** | The **original** `build_2025_baseline_tamu.calibrate_2025` was run with the fake solve. The new LP1, lossless and uncapped, has the **identical** model size and variables. The cap adds exactly one row per line. Losses add the 5 loss groups. |
| full chain (small network) | IT1 → IT2 → candidate → LP2, with every gate decision, ledger row and file checked; zero retries; input network untouched |
| **invalid capacity solution fails closed** | A −∞ / below-raw `s_nom_opt` raises before guards, r or a candidate are derived. The ERROR row is kept and no candidate is written. (Found by the zero-solver chain: PyPSA imposes `s_nom_min` as a row, not a bound, so a careless reader could take −∞.) |

**W6 runner refactor:** `common_checks` were factored out, and the ledger is injectable in `run()`. The W6 tests (11) still pass.

**L2 full suite at the frozen code: 319 passed / 0 failed** (log: `results/BYOP/next08_lossy_lp1/N08_TESTS.log`).

## 4. Files (code)

| File | Content |
|---|---|
| `workflow/byop/run/loss_basis_lp1.py` | new: gate, `prepare_lp1`, `r_proxy`, `convergence`, `guards`, `candidate_network`, run / postprocess, `--build` |
| `workflow/byop/run/loss_basis_lp2.py` | `common_checks`; `run(..., ledger_fn, log_cols)`; default behaviour unchanged |
| `workflow/config/config.byop_lossy_lp1.yaml` | new, locked |
| `workflow/byop/run/run_post_v16_a2.sh` | `lp1l_build` / `_manifest` / `_gate` / `_it1` / `_it2` / `_lp2` / `_chain` |
| `workflow/byop/tests/fake_solve.py` | capacities from the `-ext-…-lower` rows |
| `workflow/byop/tests/test_next08_lossy_lp1.py` | new |
| `workflow/byop/tests/structural_n08_lossy_lp1_chain.py` | new |
| `workflow/byop/post/next08_transmission_evidence.py` | new (A3) |
