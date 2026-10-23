# W4_A3_STATIC_READINESS (NEXT-07), 0 optimizer calls for A3

**W4_A3_RUNTIME_STATIC: PASS (static scope).** A3 is **`NOT_APPROVED / STATIC_READY_BUT_BLOCKED`**: the S0 verdict is still `BASELINE_RELIABILITY_UNRESOLVED`, and you have not authorised an A3 solve.

**Where the work is:**
- Branch `work/next07-a3-static` was **merged into `main` after the W2 probe was solved and sealed** (merge `1d05a03e`), as you authorised.
- The A3 manifest was rebuilt on L2 on the merged code (`4edf7bac`): **151 code + 110 input files, 0 mismatches**.
- The A3 gate now refuses only on:
  - the three approval fields;
  - the S0 verdict prerequisite;
  - stage order (S3 needs a passed S0 / S1).

**Tests on the merged code:**
- L2 full suite: **290 passed / 0 failed**.
- **Zero-solver A3 end-to-end dry run: 13 / 13 PASS**, 0 solver executions. Report: `workflow/results/BYOP/next07_s0_reserve_probe/_a3_e2e/E2E_A3_REPORT.json`; ledgers: `E2E_A3_*_LOG.csv`.
  - **What it ran:** the real models of S0, S1_EARLIEST, S3, the S2 developer LP, the S2 public LP and S3_mS2, built through the real A3 wrapper, linopy lock and lex instrumentation. The gate was injected as approved, with scratch ledgers. The real A3 ledgers are untouched.
  - **What it showed:**
    - one child row of the planned kind per stage, in plan order: `S0_COST`, `S1_SPEED_HIERARCHY`, `S3_COST`, `S2_DEV_LEX`, `S2_PUBLIC`, `S3_MS2_COST`;
    - each row STARTED before the call and ERROR after the intercepted call;
    - every parent closed ERROR, with no retry;
    - the conservative firm rule (A2-F_cert ≤ 0) in S3, the S2 developer LP, the S2 public LP and S3_mS2;
    - the 3,000 MW reserve row kept in the S2 public LP.
  - **Model sizes:**

    | Stage | Variables | Constraints |
    |---|---:|---:|
    | S0 | 2.66 M | 7.11 M |
    | S1 | 2.71 M | 7.30 M |
    | S3 / S3_mS2 | 2.99 M | 7.92 M |
    | S2 public | 2.99 M | 7.93 M |
    | S2 developer | 0.32 M | 0.72 M |

**Bug found and fixed by the dry run (needs your review).** With the post-v1.6 rules on, the **S2 developer LP could not be built**:
- `extra_rearch` added the 3 GW system reserve row to the developer's private network of DC buses. That network has no grid unit, so the row read `0 >= 3000` and linopy raised. A3 would have failed at its first S2 stage.
- **Fix (commit `caa428ab`):** the system reserve row is skipped only for the developer network, through an explicit flag set inside `developer_joint_build` and reset in `finally`. The 3 GW requirement stays on the grid in the S2 public LP and in S3 (verified in the dry run). Segment-SOC and firm-certificate rows still apply to the developer LP.
- This is a modelling rule: the developer is not the system operator. Please confirm it before any A3 approval request.

## What was built (package W4.1 / W4.2)

| Requirement | Implementation | Test (`test_next07_a3_runtime.py`) |
|---|---|---|
| Every A3 top-level call: `child_start` → call → `child_finish` | New `byop/model/post_v16_a3_runtime.py`: `begin(stage)` = A3 gate, then a persisted parent STARTED row. One linopy lock routes every `linopy.Model.solve` in an A3 run to a child row of the open stage. The developer LPs announce their kinds (`S2_DEV_LEX` ×≤6, `S2_DEV_COST`) via `_a3_expect`. `lex_presolve`'s direct `gurobipy` call is instrumented explicitly (`S1_SPEED_HIERARCHY`), not monkey-patched. | call plan per kind (7th dev-lex and 2nd public refused); routing through the lock (STARTED before, ERROR kept); call outside a stage refused |
| Gate before build, fail-closed | `a3_guard` (via `--post-v16 --a3-config`) runs before anything is built. It refuses:<br>• a scenario list other than exactly S0, S1_EARLIEST, S3, S2, S3_mS2;<br>• `--s2-iter` outside 1–3;<br>• a diagnostic block, or `--a2-config` together with `--a3-config`;<br>• a firm rule other than the conservative one;<br>• unpinned or changed A2 reference files;<br>• everything the A3 gate checks (approval, SHA, manifest, S0 verdict, order, budgets). | guard refusal; real CLI on L2 clone: exit 3, nothing built (`_w4_static/A3_CLI_REFUSAL.log`) |
| Exceptions keep evidence | `end('ERROR')` closes still-open children as ERROR; rows are never deleted | failed stage keeps parent + child rows |
| S0 / S1 re-solve = accepted A2 result | `a2_reproduction` checks:<br>• objective (relative 1e-6) and weighted shed (0.05 MWh) against the SHA-pinned `S0_RESULT.json` / `S1_EARLIEST_RESULT.json`;<br>• for S0, the per unit × snapshot difference against `S0_NO_HARM_REFERENCE.csv` (reported).<br>All later no-harm rows use the **formal A2 reference**, not the re-solve. A recalibrated S0 would need a new approved S0/S1 base (new pins). | pass / fail cases |
| S2 convergence, no budget filling | The S2_IT*k* stage spans developer + public LPs. `a3_s2_end` passes on acceptance plus a complete call set. An inconsistent iteration triggers the next one; a consistent one stops (`s2_loop` semantics). After IT3 still inconsistent: `S2_NOT_CONVERGED`, **S3_mS2 is not run**, efficiency claim `BLOCKED_S2_NOT_CONVERGED`. | iterations skipped after convergence; 1–3 limit; gap rule |
| S3_mS2 matched service | `matched_service_audit`: per bus × year IT MW, total MW-year and per-year distribution against the S2_final delivered service. It is part of S3_mS2 acceptance. `efficiency_claim` is `ALLOWED` only for a converged and matched pair. | same total but shifted timing: rejected |
| Conservative RE+BESS firm (W4.2) | `add_re_bess_firm_certificate(..., firm_rule='CONSERVATIVE_FIRM_SCREENING')`:<br>• certificate rows still built (audit), certificate F has upper bound 0, so dedicated BYOP RE+BESS earns no full-year firm IT credit;<br>• wind / PV / BESS still dispatch;<br>• qualified firm terms (RICE etc.) in `M2-serve_cap` unchanged.<br>The rule is set once per A3 run (`STATE['pv16_firm_rule']`) and reaches the S2 developer LP, S2 public, S3 and S3_mS2 through the single `extra_rearch` path. Unknown rules raise. BYOP units at DC buses were already excluded from the public 3 GW reserve, so there is no double reservation. | F bound per rule; RICE term unchanged; unknown rule refused; single code path for S2 and S3 |
| Old A2 budget never re-consumed | the A2 gate still refuses S0 (`already has a logged call`) | test |

**Tests:** W4 branch, full suite on a clean L2 clone: **289 passed / 0 failed / 0 skipped** (272 on `main` + 17 W4). Excerpt in `workflow/results/BYOP/next07_s0_reserve_probe/_w4_static/W4_TESTS.excerpt.log`.

## Remaining gaps (in order)

1. **S0 scientific verdict.** It must be `CALIBRATED_PASS` or `PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS`, decided by you. W2 has ruled out the reserve rule; the residual question is why the LP2 2025 check had no shed (`W3_S0_SCIENTIFIC_DECISION.md` §5). Until then A3 stays locked.
2. **Your confirmation of the developer-LP reserve rule** described above.
3. **Runtime check of the S2 developer supply-pool rows.** This is the NEXT-06 parity gap. It is visible only on a solved developer LP.
4. **48/72 h contiguous RE+BESS certificate.** Not implemented, by design. A sampling change is a separate package; until then the conservative rule gives zero firm credit.
5. **A3 approval request.** Only after 1–2: the approvable SHA, up to 29 calls, 0 retries. **Not authorised now.**
