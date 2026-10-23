# A1_RERUN_APPROVAL_REQUEST (NEXT-04 G2 Option 1) — 2026-10-22, 23:35 EDT

**This is a request, not an approval.** A1 config: `run_authorization: NOT_APPROVED`, `approved_git_sha: null`, `approved_by: null`. Since your Option 1 instruction there have been 0 solver calls.

## 1. What changed (output path only; the LP is unchanged)

| File | Change | SHA-256 (A1 manifest) |
|---|---|---|
| `workflow/byop/run/post_v16_a1.py` | `solution_view` reads each PV16 variable's **own** solution (`m['PV16-res_su'].solution` etc.), not the merged `m.solution` Dataset that padded the reserve frames to 485 names. `save_solution` writes the solved network (netCDF, L2) and every PV16-* variable (CSV) **before** writers and acceptance. Ledger and outputs go to `POST_V16_A1_HEADROOM/<run_dir>/`. | `ff0c71812885…` (was `1d6dcccc…`) |
| `workflow/byop/model/post_v16_gate.py` | New check 7: every `prior_ledgers` file exists with its pinned SHA and is not reused as the current ledger | `4e8ec5d7a4e8…` (was `cd2ce9f0…`) |
| `workflow/config/config.byop_post_v16_a1.yaml` | Approval fields reset to NOT_APPROVED. `run_dir: rerun1`. `prior_ledgers` pins the first attempt's `HEADROOM_SOLVE_LOG.csv` (`05bd03c2…`) and `LP_R_H_RESOURCE_RESULT.json` (`d80d6f9e…`). | normalised `adffc9c7…` |
| **Unchanged** | `post_v16_headroom.py` (the LP builder, `f45940f7…`), `byop_paths.py`, `run_post_v16.sh`, all 10 inputs, the v1.6 baseline `a623fb6d…747d16`, windows, reserve, zero-shed, objective and solver options | — |

**Proof the LP is unchanged:** `a1_dry` builds LP-R and LP-N at 373,249 variables / 967,980 constraints / 0 integers / 432 snapshots each, identical to before.

## 2. Verification (L2, 0 solver calls)

| Check | Result |
|---|---|
| New `test_post_v16_a1_writer.py` (3 tests) | **PASS.** On the real LP-R model with an injected solution: the reserve frame has exactly the 43 storage units, while the old merged read is still padded. The full `lp()` post-solve path (save → writers → acceptance → RESULT.json → ledger) completes, with every acceptance input numeric. Zero dispatch ends as `acceptance_failed`, not `output_failed`. The gate refuses a missing or tampered prior ledger, or reuse of it. |
| Full A1-line suite (`byop/tests`, mainline checkout) | **214 passed / 0 failed** at `7865fc5d` |
| A1 manifest | Rebuilt: 5 code + 10 input files. File SHA `d3c8b668…`. |
| `a1_gate` | Refuses only on `run_authorization` / `approved_by` / `approved_git_sha` (LP-N additionally needs LP-R PASS). No other reason: manifest, baseline, prior evidence and clean tree are all OK. |
| First attempt's evidence | Unchanged on L2: `HEADROOM_SOLVE_LOG.csv` `05bd03c2…`, `LP_R_H_RESOURCE_RESULT.json` `d80d6f9e…`. Never cleared or edited. |

## 3. Proposed approval and budget

```yaml
# workflow/config/config.byop_post_v16_a1.yaml (config-only commit, after your explicit approval)
post_v16:
  run_authorization: APPROVED
  approved_git_sha: <the commit that contains this request; given in the executor's message>
  approved_by: <your identifier>
```

- **Budget (rerun 1): at most 2 solver calls, 0 retries.** One LP-R, then one LP-N, only if LP-R passes. They are logged in `POST_V16_A1_HEADROOM/rerun1/HEADROOM_SOLVE_LOG.csv`.
- The first attempt's call (`LP_R_H_RESOURCE#1`, `output_failed`) stays recorded and counted, so A1 would total **3 actual solver calls**.
- **Commands** (L2 A1 main checkout `workflow/`):
  - `THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_r`
  - then `a1_lp_n`
- **Threads:** L2 load was ~9–10 of 24 at 23:33 EDT, so T ≈ 12, re-measured at launch. Each LP took ~77 s last time.
- **Stop rules:** unchanged. If LP-R fails, no LP-N. If B0 is infeasible, the result is classified resource-side or network-side and is never reported as 0 headroom. After A1 the executor STOPS for your review (G2).
