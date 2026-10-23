# W3_A3_EXECUTION_READINESS (NEXT-06), 0 optimizer calls

**W3_A3_GATE: STATIC_PASS (gate + plan + tests). A3 EXECUTION: NOT READY.** The A3 runtime wiring and the conservative firm rule are still to do, and the S0 verdict is unresolved. A3 solver calls in this package: **0**. The NEXT-05 A3 budget of 30 is untouched and **not** unlocked.

## Built (static)

| Item | Where | Status |
|---|---|---|
| Independent A3 gate | `workflow/byop/model/post_v16_a3_gate.py` | Approval fields (stage A3 only), SHA / ancestor / clean tree, LF-pinned authorisation text, manifest, baseline, **prerequisite: S0 scientific verdict**, stage order with optional S2 iterations, zero retries, scenario-attempt budget, child ledger with **per-kind counts** and total budget |
| A3 config | `workflow/config/config.byop_post_v16_a3.yaml` | NOT_APPROVED. Stages S0 → S1_EARLIEST → S3 → S2_IT1 (→ IT2 → IT3 optional) → S3_mS2. Plan max **29** ≤ 30. `firm_rule: CONSERVATIVE_FIRM_SCREENING`. |
| A3 manifest | `current_work_pckg/BYOP_NEXT_06/A3_PRE_RUN_MANIFEST.json` | 150 code + 110 inputs, 0 mismatches (L2) |
| Call plan from the real code | `W3_A3_SOLVER_CALL_PLAN.csv` | Per S2 iteration: 6 developer lex LPs + 1 private cost + 1 public = 8. S3: 1. S3_mS2: 1. Re-solve S0 + S1 (3), because S2 needs the S1 network in memory. |
| S2 / S3 physical parity | `W3_S2_S3_PHYSICAL_PARITY.csv` | Shared by code: technology / COD / permit / gas / POI / public assets / reserve / SOC / no-harm. **GAP:** the RE+BESS firm certificate (24 h only, S3), and supply-pool rows in the developer LP to verify at runtime. |
| Tests | `test_next06_a3_gate.py` (5), `test_next06_static.py` (3) | PASS (L2 full suite 256 / 0). Failure injection: see `W3_A3_STATIC_TEST_SUMMARY.json`. |
| Gate verdict now | `W3_A3_GATE_VERDICT.json` | LOCKED: NOT_APPROVED + **S0 verdict UNRESOLVED** + order |

## Still required before an A3 approval request (in this order)

1. **S0 scientific verdict** = `CALIBRATED_PASS` or `PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS`, decided by you after the W2 diagnostic. Until then the gate refuses by design.
2. **Runtime wiring:** route every A3 optimizer call through `post_v16_a3_gate.child_start` with the planned kinds:
   - `developer_joint`'s per-year `m.solve` (S2_DEV_LEX) and `solve_model` (S2_DEV_COST);
   - `go('S2')` (S2_PUBLIC), `go('S3')`, `go('S3_mS2')`;
   - the S0/S1 re-solves, which must reproduce the accepted A2 results (no-harm reference SHA identical).

   The A2 linopy lock currently refuses these as UNPLANNED, which is correct until the wiring exists.
3. **Conservative firm rule** in S2 and S3 alike: dedicated RE+BESS full-year firm credit = 0 until a 48/72 h contiguous same-SOC certificate exists. A sampling change for 48/72 h stress segments is a separate researcher decision.
4. **Runtime S2 checks:**
   - `S2_final` convergence check (public delivery ≥ developer plan, otherwise `S2_NOT_CONVERGED`);
   - the matched-service S3_mS2 must exist before any S2−S3 efficiency claim;
   - a solver-free test of both.
5. Rebuild the A3 manifest on the wired code, then make a separate A3 approval request: up to 29 calls, 0 retries.
