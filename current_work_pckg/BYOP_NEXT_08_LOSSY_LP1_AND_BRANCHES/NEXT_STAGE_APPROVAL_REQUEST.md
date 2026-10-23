# NEXT_STAGE_APPROVAL_REQUEST (NEXT-08): lossy 2025 LP1 calibration + candidate LP2

**Status: NOT_APPROVED. No optimizer call has been made in NEXT-08.**

| Item | Value |
|---|---|
| **Approvable code SHA** | **`219bf3e9b7f08c9bc65f69276a2635a37fe8c47c`** (GitHub `main` = L2 `byop` at freeze) |
| Config | `workflow/config/config.byop_lossy_lp1.yaml` (fields now `NOT_APPROVED / null / null`) |
| Manifest | `current_work_pckg/BYOP_NEXT_08_LOSSY_LP1_AND_BRANCHES/LOSSY_LP1_PRE_RUN_MANIFEST.json` (L2-built at `8029cefc`; 153 code + 110 input files, 0 mismatches; no gated file changed since) |
| Gate now | `LP1_LOSSY_IT1` refused **only** on the three approval fields. IT2 and LP2 are additionally refused by their stage rules, as designed. |
| Pinned inputs | v1.6 `prepared.nc` `a623fb6d…747d16`; `raw_uncalibrated.nc` `eb659f9b…077a97f` (both read only) |
| Ledger / outputs | `workflow/results/BYOP/next08_lossy_lp1/` (`LOSSY_LP1_SOLVE_LOG.csv`), new; no older ledger touched |

## Optimizer-call order, budget and stop conditions (enforced by `loss_basis_lp1.check`)

| # | Stage | Runs when | Calls | Expected time (est.) |
|---|---|---|---:|---|
| 1 | `LP1_LOSSY_IT1` | after approval | 1 | 30–60 min (v1.6 lossless LP1: 26 min) |
| 2 | `LP1_LOSSY_IT2` | **only if** IT1 is optimal **and not** r-converged | ≤ 1 | 30–60 min |
| 3 | `LP2_LOSSY_CANDIDATE` | **only if** the last LP1 is optimal, r-converged, passes G1–G3 **and** the candidate NetCDF exists | ≤ 1 | about 12 min (W6 lossy LP2: 12 min) |
| | **Total** | | **≤ 3**, 0 retries | |

**STOP (no further call; evidence kept):**
- any non-optimal solve or invalid capacity solution;
- IT2 still not converged;
- a guard fails: G1 total uplift > 7,727.8 MVA; G2 any line at 2 × its v1.6 capacity; G3 more than 1,000 MVA on lines not uplifted in v1.6;
- the budget is used.

**LP2 acceptance:** the unchanged v1.6 criteria (EENS ≤ 4,882 MWh, largest gap ≤ 83.7 MW).

**Command (L2, `workflow/`):** `THREADS=<B> bash byop/run/run_post_v16_a2.sh lp1l_chain`. Each stage's own gate decides, so a stage that is not allowed is refused without a solve. Following the L2 run rule, B = 24 minus other users' busy cores, capped at about 22, measured at launch; at today's load (about 2) that is **21**.

## What an approval does NOT cover

- Adopting the candidate as the formal lossy 2025 baseline. **A PASS still needs your separate decision**: the r proxy and any added capacity are synthetic-network calibration assumptions, not physical parameters.
- Any change to the frozen v1.6 NetCDFs (never written).
- The paired S0/S1 rerun, A3 or S2/S3. Each needs its own request.

## Proposed approval sentence

> I approve the NEXT-08 lossy LP1 calibration at approved_git_sha 219bf3e9b7f08c9bc65f69276a2635a37fe8c47c: LP1_LOSSY_IT1; LP1_LOSSY_IT2 only if IT1 is optimal and not r-converged; LP2_LOSSY_CANDIDATE only after an optimal, r-converged LP1 that passes G1–G3; transmission_losses 2; at most 3 optimizer calls; 0 retries; approved_by: <your identifier>.
