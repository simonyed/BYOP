# A2_PRE_SOLVE_RESEARCHER_DECISION (NEXT-03 update, H3 stop point): request for the S0 + S1_EARLIEST solve

**A2 is `NOT_APPROVED`. 0 A2 scenario attempts, 0 optimizer calls. This document requests a separate approval; it does not grant one.**
- A1 approval never carries over to A2.
- S2/S3 stay `NOT_APPROVED` (A3).
- NEXT-03 W3.1 prerequisite: A2 should be approved **after** you have reviewed the A1 result, or have explicitly decided how to read an A1 that has not run or is blocked.

## 1. Code and evidence to approve

| Item | Value |
|---|---|
| Branch / code commit | `work/a2-postv16-static`, code **`81bd57438c7b002d6cfe455ec2b3f973f33ed12c`**. Branch head `39a74ff5` adds only `current_work_pckg/` (manifest, verdict, summary). |
| Manifest | `current_work_pckg/A2_PRE_RUN_MANIFEST.json`, built on L2 at `81bd5743`: 149 code + 110 input files, three SHA layers, 0 mismatches. Normalised config `31f1c3fc…`. Baseline `a623fb6d…747d16`. |
| Authorisation source pinned by the gate | `current_work_pckg/BYOP_POST_V16_NEXT_03_v1.0/BYOP_POST_V16_NEXT_03_A1_A2_Formal_S0_S1_Execution_2026-10-22.md`, LF SHA `f1b1a249…`. The NEXT-02 text stays in place. |
| Gate now | `A2_GATE_VERDICT.json` = LOCKED. Refused only on the three approval fields; S1 additionally needs a PASSED S0 and its SHA-pinned no-harm reference. |
| Static evidence | Structural 75/75; A2 worktree 245/0; fresh LF clone 243/0/2 (L2-only baseline); NEXT-03 unit tests 15/15. 0 solver calls. |

## 2. What NEXT-03 added (and what it kept)

| Fix | Result |
|---|---|
| **A2-FIX-08 SOC segments** | **Real risk confirmed:** PyPSA chained the SOC across all 24 within-period gaps (sampled weeks ↔ B7 stress days). 63 units also chained across investment years. Fixed with one linear row per unit × segment (end ≥ the SOC PyPSA carries in), which makes every segment energy-neutral. No binaries. → `A2_REPRESENTATIVE_PERIOD_SOC_BOUNDARY_AUDIT.md` |
| **A2-FIX-09 call accounting** | Separate budgets: **2 scenario attempts** and **3 top-level optimizer calls** (S0_COST; S1_SPEED_HIERARCHY + S1_COST). Every call gets a child row, STARTED before it, tied to its parent. linopy is a controlled entry; the Gurobi hierarchical call is instrumented in `lex_presolve`. gurobipy is **not** claimed to be patched. Failure injection: 11 / 11. Speed levels are re-checked in the cost stage. The no-harm reference is strict and SHA-pinned, with no fill. → `A2_SOLVER_ACCOUNTING_AUDIT.md`, `A2_OPTIMIZER_CALL_PLAN.json`, `A2_GATE_FAILURE_INJECTION_QA.json` |
| Kept from NEXT-02 (re-verified in the 75 checks) | FIX-01 pairs (324, `M2-line_sym`); FIX-02 COD / cost (1,818); FIX-03 `stores` = 3 h + start/end reserve SOC; FIX-04 no-harm / S0 ≡ S1; FIX-05 no BYOP firm rows in S0/S1; FIX-06 EOL / gzip; FIX-07 independent gate |

## 3. The request

| Field | Value |
|---|---|
| Config-only commit | `workflow/config/config.byop_post_v16_a2.yaml`: `run_authorization: APPROVED`, `approved_git_sha: 81bd57438c7b002d6cfe455ec2b3f973f33ed12c`, `approved_by: <your identifier>` |
| Commands (L2 A2 worktree `/datasets/prgm/BYOP_impact/pypsa-usa/.worktrees/a2/workflow`) | `bash byop/run/run_post_v16_a2.sh gate`, then `THREADS=<T> bash byop/run/run_post_v16_a2.sh s0s1` (S0 → S1_EARLIEST; S1 only after S0 PASS) |
| Budget | **max_scenario_attempts = 2; max_top_level_optimizer_calls = 3** (S0_COST, S1_SPEED_HIERARCHY, S1_COST). Gurobi hierarchy passes are logged as `n_objectives`, not counted as calls. 0 retries. |
| Threads | Dependent steps, so a single process each. T = 24 − (other users' load at launch), at least 4 (L2 load ~18.5 tonight, so about 6). Memory per LP ~10–20 GB (not measured). |
| Run time | Not measured. Each LP has ~2.7 M variables / 7.1–7.3 M constraints; no promise is made. |
| STOP | Gate refusal; any exception; non-optimal status; a missing or extra child call; acceptance failure. Acceptance covers: balance ≤ 1e-3 MW, reserve and both SOC rows, segment rows present, fwd = rev, no free link, children complete; for S1 also strict no-harm against the reference plus the D24 row built from it, lexicographic hierarchy optimal, and speed levels held. No retry, no log deletion, no parameter change, no S2/S3. |

## 4. Decisions you need to make

| # | Recommendation | Meaning |
|---|---|---|
| D4 | Accept `stores` = 3 h, start/end reserve SOC, **and the FIX-08 segment neutrality** | Storage is a representative-day/week approximation; no cross-segment or cross-year energy. Do not fall back to the ~77 h step. |
| D5 | DWB/PBRP are common exogenous committed assets, outside the objective | DWB 371 M$ is in **2019 USD** (TSP preliminary, SOURCED). PBRP 3,020 M$ per path is in **2024 USD** (9.06 B$ / 3, PROXY). The sunk/unpaid shares are executor assumptions. Not one common 2025 USD figure. |
| D6 | S1 shed ≤ S0 shed per unit × snapshot + 0.001 MW (acceptance limit 0.002) | Strict file-based reference: a mismatch fails the run, with no fill. |
| D7 | Approve 2 attempts / 3 top-level calls at `81bd5743`, after the A1 review | Requires an explicit approval separate from A1 |
| A1 link | If A1 is BLOCKED, explain whether that undermines the S0/S1 physical baseline before releasing A2 | — |
| D2 | Bexar `p650 0` stays at L2 | No firm MDQ or contract evidence |

## 5. Remaining proxies

- Single weather year.
- Sampled 3 h segments (2 weeks + 3 stress days per period, energy-neutral).
- LP online-capacity relaxation.
- Aggregate reserve proxy (not N-1).
- Gas lead L2 at 3 y.
- 8 of 16 sites UNKNOWN_CONSERVATIVE.
- POI, permit and supply-pool inputs are research proxies.
- The inherited 460.73 MW ramp may overlap Native Load 2025.
