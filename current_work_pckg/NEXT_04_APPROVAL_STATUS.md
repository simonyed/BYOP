# NEXT_04_APPROVAL_STATUS — 2026-10-22, 22:10 EDT (P0 read-only, 0 solver calls)

**State A: no run authorisation received. A1, A2, S0 and S1 are NOT_RUN. Stopped at G1.**

## P0 result (L2, one read-only pass: `POST_V16_A1_HEADROOM/NEXT04_P0_READONLY.log`)

- **A1 main checkout:**
  - HEAD `1e637e6d94f03404419c41fde91213186808ac50` descends from `802c9d94`;
  - 0 gated changes since then, 0 dirty, 0 untracked;
  - the gate also re-verified the manifest, config and baseline SHAs;
  - `HEADROOM_SOLVE_LOG.csv` does not exist (0 of 2 calls used);
  - the gate refuses only on the three fields below (LP-N also needs LP-R PASS).
- **The NEXT-03 model recheck is reused** (`A1_FINAL_RECHECK_NEXT03.json`), because nothing gated has changed since. No model was rebuilt.
- **A2 worktree:**
  - HEAD `39a74ff5`, which contains code `81bd5743` (FIX-01..09; structural 75/75; regression 245/0);
  - no A2 ledger directory exists;
  - the A2 gate is LOCKED, refusing only on the approval fields.

## What is missing to proceed (only you can provide it)

**G1 / A1.** A config-only commit to `workflow/config/config.byop_post_v16_a1.yaml`:

```yaml
run_authorization: APPROVED
approved_git_sha: 802c9d9414514641fd2b088b45ec7ea945be18a4
approved_by: <your identifier>
```

Then `THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_r`, and `a1_lp_n` only if LP-R passes. At most 2 calls, 0 retries. L2 load at check time was 13 of 24, so T ≈ 8–10, measured again at launch.

**G2.** After A1: your review of the result (or a written disposition if A1 is blocked).

**G3 / A2.** Only after the A1 review **and** after the A2 branch is merged and revalidated on a unified `main`:
- a separate approval of the **new merged commit SHA**, not `81bd5743`;
- budget: 2 scenario attempts / 3 top-level optimizer calls, 0 retries.

Recommendations for D2/D4/D5/D6: `NEXT_04_RESEARCHER_DECISIONS.md`.
