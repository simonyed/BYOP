# EXECUTION_REPORT (NEXT-08): lossy LP1 calibration preparation + GitHub branch cleanup, 2026-10-23 (New York)

```text
WORK_PACKAGE: BYOP_NEXT_08 (prompt: NEXT_08_PROMPT.md)
START_HEAD: 327b46eaa0095dc80e0c0893f538f6396c259c6a (main = mainline-v13-stageA)
APPROVABLE_SHA: 219bf3e9b7f08c9bc65f69276a2635a37fe8c47c (lossy LP1 chain, NOT_APPROVED)
OPTIMIZER_CALLS: 3 (approved later the same day at 219bf3e9 via 1adf3116: IT1 not converged, IT2 converged + G1-G3 PASS, LP2 candidate EENS 1,657 MWh PASS / max gap 132.4 MW FAIL; see LOSSY_LP1_RESULTS.md)
TASK_A_STATIC: PASS (design, runner, real-model build, zero-solver chain PASS, 11 new unit tests, suite 319/0)
TASK_B_BRANCHES: GitHub = main only; 11 tags; 3 local/L2 worktree-bound branches kept (worktree removal refused by the permission classifier - needs your OK)
FROZEN_FILES_CHANGED: none (v1.6 NetCDFs, ledgers, approvals, results, inputs untouched)
NEXT_DECISION_REQUIRED: candidate not adopted (LP2 gap 132.4 MW > 83.7); decide on the LP1 loss-approximation fix (4 tangent segments in LP1 only, <= 3 calls) and allow the 3 worktree removals
```

## Work done

**C1 (state).**
- GitHub branches: `main` = `mainline-v13-stageA` (`327b46ea`), plus `work/a2-postv16-static` and `work/next07-a3-static`. All are ancestors of `main` with 0 unique commits.
- No running L2 job, no open PR, no protected branch; default branch `main`.

**C2/C3 (branches)**, see `BRANCH_CLEANUP_REPORT.md`:
- 11 annotated tags (`byop/*` solved-code SHAs, `archive/branch-*` heads).
- The 3 retired GitHub branches deleted.
- Local working branch moved to `byop` (same commit). The sync tool's branch detection was fixed: it would have pushed to `heads/byop`.
- Branch policy rewritten in `pypsa-usa/CLAUDE.md`: `origin/main` is the only baseline, `work/<task>` branches come from it. The local `CLAUDE.md` was updated too.
- L2 worktree-only marker files migrated.

**A1–A3 (design, evidence)**, see `LOSSY_LP1_CALIBRATION_DESIGN.md`, `A3_TRANSMISSION_EVIDENCE*`:
- **Option 2 chosen:** a parallel-circuit r proxy, fixed inside each LP, with x raw. It needs at most 2 LP1 calls and 1 LP2, has explicit convergence and guards, and adds no bilinear term.
- **Differences from the v1.6 LP1** are tabulated: losses, finite cap, r proxy; everything else identical, verified against the original function.
- **TPIT evidence:**
  - 14 of 18 uplifted lines (4,472.5 MVA, 87 %) have completed 2024–25 ≥ 138 kV work (mostly second circuits, double circuits, rebuilds) at their end buses;
  - 4 lines (679.4 MVA: TL12, TL26, TL42, TL63) are research calibration proxies.

**A4/C4 (code, tests)**, see `LOSSY_LP1_STATIC_VALIDATION.md`:
- `loss_basis_lp1.py` with config, run commands and gate.
- Real LP1 model built: 2.09 M variables / 6.90 M constraints.
- Zero-solver chain on the real networks passed.
- One defect found and closed: an invalid (−∞) capacity solution would have been read silently. The runner now fails closed, with a test.
- Suite 319 / 0.

**C5:** manifest built on L2, SHA frozen (`NEXT_STAGE_APPROVAL_REQUEST.md`). Everything is synced: GitHub `main` = L2 `byop` = local `byop`.

## Code changes

| File | Change |
|---|---|
| `workflow/byop/run/loss_basis_lp1.py` | new runner |
| `workflow/config/config.byop_lossy_lp1.yaml` | new, locked |
| `workflow/byop/run/loss_basis_lp2.py` | `common_checks`; injectable ledger in `run()` (default unchanged) |
| `workflow/byop/run/run_post_v16_a2.sh` | `lp1l_*` commands |
| `workflow/byop/tests/fake_solve.py` | capacities read from their `-ext-…-lower` rows |
| `workflow/byop/tests/test_next08_lossy_lp1.py`, `workflow/byop/tests/structural_n08_lossy_lp1_chain.py` | new |
| `workflow/byop/post/next08_transmission_evidence.py` | new |
| `pypsa-usa/CLAUDE.md` | BYOP branch policy |

Outside the repository (local tooling):
- `work_pkgs/_tools/sync_pypsa_usa.sh`: branch detection fixed;
- `D:\BYOP_impact\CLAUDE.md` §2: branch policy.

## Open items

1. **The worktree removals were refused by the permission classifier.** Three branch references remain: local `work/a2-postv16-static` and `integrate/next05`, and L2 `work/a2-postv16-static`. All their commits are in `main` and tagged. Safe commands are in `BRANCH_CLEANUP_REPORT.md` §5.
2. **Lossy LP1 chain:** waiting for approval (≤ 3 calls).
3. **Earlier items carried forward:**
   - the A3 manifest (`4edf7bac`) is stale and must be rebuilt for any A3 request;
   - the S2 developer-LP reserve rule still needs your confirmation;
   - the S0 verdict waits on a valid lossy baseline.

## Recommended next step

Approve the lossy LP1 chain at `219bf3e9`. If LP2 passes:
1. decide on adopting the candidate (new baseline SHA; v1.6 kept);
2. paired S0/S1 rerun (≤ 3 calls);
3. S0 verdict;
4. A3 manifest rebuild;
5. S2/S3, for the BYOP speed-to-power, public-investment-feedback and social-efficiency results.

No new sensitivity batches are proposed.

## Update: the approved lossy LP1 chain (see `LOSSY_LP1_RESULTS.md`)

**Calls:** 3 of 3, 0 retries, 21 threads.

| Stage | Result |
|---|---|
| IT1 | optimal, not r-converged |
| IT2 | optimal, converged; uplift 5,816.6 MVA = v1.6 + 664.8 MVA on 20 lines; G1–G3 pass; candidate written as a new file |
| LP2 on the candidate | EENS 1,657 MWh (pass); **largest gap 132.4 MW (fail)** at p610 1, 28 Aug 09:00 |

- **Far West pocket:** now served.
- **Candidate:** not adopted; the frozen files are unchanged.

**Cause.** LP1's loss tangents sit at 1× and 2× the v1.6 rating because of the 2× cap, while LP2 and S0–S3 place them at ½ and 1× the actual rating. LP1 therefore under-counts losses (3.90 vs 5.32 TWh).

**Proposed fix (needs your approval).** Use 4 tangent segments in LP1 only. These contain LP2's tangent points, so LP1 losses are at least LP2's. Budget: ≤ 3 calls.
