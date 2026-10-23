# A1_FINAL_APPROVAL_REQUEST (NEXT-02 W1 §2.2) — 2026-10-22, 20:10 EDT

**This is a request. It is not an approval.** A1 is `NOT_APPROVED`, the solver ledger is empty, and **0 solver calls** have been made. Two LPs run only after you explicitly approve. A1 approval does not carry over to A2, S2 or S3.

## 1. What is being approved

| Item | Value (re-verified by this request's read-only check) |
|---|---|
| Code commit to approve | `802c9d9414514641fd2b088b45ec7ea945be18a4` |
| Current A1 mainline HEAD (L2 main checkout) | `b2b2e48e5c3c782e13ccfe5511e652018a92673d`, branch `mainline-v13-stageA` |
| HEAD relative to `802c9d94` | Descendant (`merge-base --is-ancestor` = true) |
| Commits since `802c9d94` | `ac4eeeb8` and `b2b2e48e`: reports only. Changed paths are `current_work_pckg/*`, `.gitignore` and `results/BYOP/post_v16_a2_static/*`. **0 changes under the gated paths** (`workflow/byop/{model,build,run,post,inputs}`, `workflow/config`, `workflow/scripts`). |
| Worktree (gated paths) | Clean: no content diff (CR at EOL ignored) and no untracked file |
| v1.6 baseline (L2) | `workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`, SHA-256 `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16` (matches config and manifest) |
| Manifest | `current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json`, SHA-256 `d0f0b7f90568d2ec4b5b275a03cf242dfebf826769ac80eb6d96f9b425f4f5d1`; 5 code + 10 input files; **0 mismatches** |
| Normalised config SHA | `202c34d3d67f1e7303679fea12965d11359a941b64d9eea88f3a2e9998db9359` (equals the manifest) |
| Authorisation source text | `_completed/BYOP_Post_v1.6_Execution_v1.1_A0/.../CURRENT_EXECUTION_WORK_PACKAGE_v1.1.md`; pinned SHA `c3c1a0a5…` matches |
| Ledger | `workflow/results/BYOP/POST_V16_A1_HEADROOM/HEADROOM_SOLVE_LOG.csv` **does not exist**: 0 of 2 calls used, no STARTED / DONE / ERROR row |
| Dry build (create_model only) | LP-R and LP-N each have 373,249 variables, 967,980 constraints and 0 integers. 63 buses, 162 lines, 432 snapshots (1 h). Objective = −λ only. 27,216 hard-zero existing-shed rows. 16 weights summing to 1. Reserve 3,000 MW. Line limits: LP-R relaxed (1.62e8 MVA total) > LP-N frozen (198,015 MVA). |
| Gate verdict now | LP-R refused only for `run_authorization=NOT_APPROVED`, `approved_by missing` and `approved_git_sha missing`. LP-N also refused for `needs a PASSED LP_R_H_RESOURCE first`. |

Unchanged frozen design:
- B0 + BL blocks.
- Three pre-registered windows: W_SUMMER_PEAK_20250818, W_WINTER_PEAK_20250220 and W_SUMMER_DISJOINT_20250730.
- Reserve: 3 GW, 1 h, 10 min.
- Hard-zero existing shed.
- Objective: max λ, upper bound 200,000 MW.
- LP-R copperplate (KVL kept); LP-N frozen line limits.
- No change to the 2025 network, Native Load 2025, the 460.73 MW inherited IT ramp, weather or the reliability proxy.

Evidence: `current_work_pckg/A1_FINAL_RECHECK.json`, produced by `current_work_pckg/a1_final_recheck_next02.py` on L2, plus the L2 logs `POST_V16_A1_HEADROOM/NEXT02_A1_FINAL_RECHECK.log` and `NEXT02_A1_GATE.log`.

## 2. The only edit you would authorise (config-only commit)

`workflow/config/config.byop_post_v16_a1.yaml`:

```yaml
post_v16:
  run_authorization: APPROVED
  approved_git_sha: 802c9d9414514641fd2b088b45ec7ea945be18a4
  approved_by: <your own explicit approval identifier>
```

The executor will **not** fill in `approved_by`. If HEAD, a gated file, the manifest or the ledger changes before launch, the gate refuses and the request comes back to you.

## 3. Commands (L2 A1 main checkout, from `/datasets/prgm/BYOP_impact/pypsa-usa/workflow`)

```bash
THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_r
# only if LP_R_H_RESOURCE_RESULT.json acceptance is PASS and the ledger row is DONE / ok / optimal / pass:
THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_n
```

- **Threads.** L2 load was 16.5–19.8 of 24 logical cores at check time; other users hold about 13–17. The two steps are dependent, so each is a single process.
  - Proposal: T = 24 − (other users' load at launch), capped at 22 and at least 4. At today's load that is about 6–8.
  - The LP is small (0.37 M variables), so thread count affects wall time only.
- **Budget:** at most 2 solver calls, 0 retries. A STARTED row is written to disk before each call.

## 4. Stop and error rules (no retry, no log deletion, no parameter change)

- **Stop conditions.** Stop if any of these fails:
  - `status=ok` and `termination=optimal`;
  - zero existing shed;
  - reserve met;
  - nodal-balance residual ≤ 1e-3 MW;
  - λ finite and below the upper bound;
  - for the joint result, 0 ≤ H_network ≤ H_resource + 1e-3 MW.
- **If LP-R fails,** LP-N is not run.
- **If LP-N fails,** the run stops and `H_network` is not reported as 0.
- **If B0 is infeasible,** the result is classified as `BASELINE_PRESSURE_INFEASIBLE_RESOURCE_SIDE` or `BASELINE_PRESSURE_INFEASIBLE_NETWORK_SIDE`. It is never read as zero AIDC headroom.
- **After A1 the executor stops** and reports to you. A2 is not started from A1.

## 5. Interpretation boundary

A1 is a joint deliverable-capacity proxy: the fixed 2025 network, with growth held in the 16-bus proportions. It is not an ERCOT per-station interconnection approval. The max-λ dispatch is a non-unique witness, so its LMPs and duals are not proven prices.
