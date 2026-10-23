# NEXT_08B_APPROVAL_REQUEST: lossy 2025 LP1 v2 (reference-capacity loss tangents)

**Status: NOT_APPROVED. No optimizer call has been made in NEXT-08b.**

| Item | Value |
|---|---|
| **Approvable code SHA** | **`5cb7889e7144e488ea346d7bd36e050c17d0d1b2`** (GitHub `main` = L2 `byop` at freeze) |
| Config | `workflow/config/config.byop_lossy_lp1_v2.yaml` (`NOT_APPROVED / null / null`; `loss_tangent_reference: s_ref`) |
| Manifest | `current_work_pckg/BYOP_NEXT_08B_LP1_TANGENT_FIX/LOSSY_LP1_V2_PRE_RUN_MANIFEST.json` (L2-built at `80fc503e`; 153 code + 110 input files, 0 mismatches) |
| Gate now | `LP1_LOSSY_IT1` refused **only** on the three approval fields. IT2 and LP2 additionally on their stage rules. |
| Output / ledger | `workflow/results/BYOP/next08b_lp1_tangent_fix/` (new). The NEXT-08 ledger, candidate and results are never touched. |
| Pinned inputs | v1.6 `prepared.nc` `a623fb6d…`; `raw_uncalibrated.nc` `eb659f9b…` (read only) |

## Calls, budget and stop rules

Unchanged from NEXT-08 except the tangent reference.

| # | Stage | Runs when | Calls |
|---|---|---|---:|
| 1 | `LP1_LOSSY_IT1` (S_ref = v1.6 capacity) | after approval | 1 |
| 2 | `LP1_LOSSY_IT2` (S_ref = IT1 solution) | only if IT1 is optimal and not r-converged | ≤ 1 |
| 3 | `LP2_LOSSY_CANDIDATE` | only after an optimal, r-converged LP1 passing G1 (≤ 7,727.8 MVA), G2 (no line at the 2 × v1.6 cap) and G3 (≤ 1,000 MVA on lines not uplifted in v1.6), with the candidate written | ≤ 1 |
| | **Total** | | **≤ 3, 0 retries** |

- **LP2 acceptance:** the unchanged v1.6 criteria (EENS ≤ 4,882 MWh, largest gap ≤ 83.7 MW).
- **STOP:** any non-optimal or invalid solution, IT2 not converged, a guard fail, or the budget used.
- **Command (L2, `workflow/`):** `THREADS=<B> bash byop/run/run_post_v16_a2.sh lp1r_chain`, with B measured at launch (about 21 at load 2). Expected run time is like NEXT-08: about 30 + 31 + 12 min.

**Not covered by an approval:**
- adopting any candidate as the formal 2025 baseline (your separate decision);
- any change to the frozen v1.6 or NEXT-08 files;
- S0–S3 runs.

## Proposed approval sentence

> I approve the NEXT-08b lossy LP1 v2 (reference-capacity loss tangents) at approved_git_sha 5cb7889e7144e488ea346d7bd36e050c17d0d1b2: IT1; IT2 only if IT1 is optimal and not r-converged; LP2 only after a converged LP1 passing G1–G3; transmission_losses 2; at most 3 optimizer calls; 0 retries; no baseline adoption or S0–S3 runs; approved_by: <your identifier>.
