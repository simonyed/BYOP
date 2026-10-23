# W4_A3_STATIC_READINESS (NEXT-07), 0 optimizer calls

**W4_A3_RUNTIME_STATIC: PARTIAL.** The wiring, the conservative firm rule and the audits are built and tested. A3 is **`NOT_APPROVED / STATIC_READY_BUT_BLOCKED`**, blocked by the S0 verdict (`BASELINE_RELIABILITY_UNRESOLVED`). PARTIAL means two items remain: an end-to-end A3 build dry-run, and the post-W2 merge plus A3 manifest rebuild (see the gaps below).

**Where the work is:**
- Branch `work/next07-a3-static` at `79134c9fc3499e923240e1ed537ef2d8b87dc5da`, on GitHub as its own branch.
- **Not merged into `main` and not on the L2 checkout**, so the W2 approvable SHA `5df4dda7` does not drift. It merges only after W2 is run or declined. The A3 manifest is then rebuilt on the merged code, and the static regressions are re-run.

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

1. **Merge after W2.** Merge `work/next07-a3-static` into `main` only after the W2 run is sealed or declined. Then rebuild `current_work_pckg/BYOP_NEXT_07/A3_PRE_RUN_MANIFEST.json` on L2 and re-run the full suite. The A3 config now points to that manifest; it does not exist yet, so the gate refuses.
2. **End-to-end A3 build dry run.** Run S0, S1_EARLIEST, S3, the S2 developer and public LPs, and S3_mS2 through the real wrapper with every solve intercepted. Today the wrapper is tested with fakes and the CLI only up to the guard. This needs an injected-gate structural harness (zero solve) before any A3 approval request.
3. **Runtime check of the S2 developer supply-pool rows.** This is the NEXT-06 parity gap and still holds.
4. **48/72 h contiguous RE+BESS certificate.** Not implemented, by design. A sampling change is a separate package; until then the conservative rule gives zero firm credit.
5. **S0 scientific verdict.** It must be `CALIBRATED_PASS` or `PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS`, decided by the researcher. Until then A3 stays locked.
