# NEXT_08B_LOSS_UPPER_APPROVAL_REQUEST: lossy 2025 LP1 v3 (loss-upper fix)

**Status: NOT_APPROVED. No optimizer call has been made for v3.**

| Item | Value |
|---|---|
| **Approvable code SHA** | **`d4fd5340945e50c86859024e2ecec86597b630dd`** (GitHub `main` = L2 `byop` at freeze) |
| Config | `workflow/config/config.byop_lossy_lp1_v3.yaml` (`NOT_APPROVED / null / null`; `loss_upper: affine_s_ref`) |
| Design and proof | `LOSS_UPPER_FIX_DESIGN.md` (lemma, construction, proofs P1–P5, static validation) |
| Manifest | `LOSSY_LP1_V3_PRE_RUN_MANIFEST.json` (L2-built at `b2f93b5d`; 153 code + 110 inputs, 0 mismatches) |
| Gate now | `LP1_LOSSY_IT1` refused **only** on the three approval fields. IT2 and LP2 also refused on their stage rules. |
| Output / ledger | `workflow/results/BYOP/next08b_lp1_loss_upper_fix/`, a new ledger. The NEXT-08 and NEXT-08b ledgers, candidates and results are never touched. |
| Pinned inputs | v1.6 `prepared.nc` `a623fb6d…`; `raw_uncalibrated.nc` `eb659f9b…` (read only) |

## What changes against v2 (one row family and one bound)

- **The loss upper bound.** `Line-loss_upper` changes from r·(0.7·cap)² (v2, the source of the non-physical dissipation) to r·(2·R_ref·R − R_ref²), where R = 0.7·s_nom is the LP variable.
  - Exact LP2 row at s_nom = S_ref.
  - Never above LP2's r·R² at any capacity.
  - Never a flow limit for s_nom ≥ 0.75·S_ref.
- **An explicit trust floor.** s_nom ≥ max(raw, 0.75·S_ref).
  - It is mathematically necessary: no LP bound that is exact at S_ref can avoid a hidden cap below 0.75·S_ref (design §2).
  - A line on a floor above raw counts as not converged.
  - In the sealed v2 chain the lowest solution / S_ref ratio was 0.87, so the floor would not have bound.

**Unchanged:**
- tangents at S_ref;
- cap 2 × v1.6;
- r proxy and the r / capacity thresholds (5 % / 10 MVA);
- G1 (≤ 7,727.8 MVA), G2, G3 (≤ 1,000 MVA);
- LP2 build and its acceptance (EENS ≤ 4,882 MWh, **largest gap ≤ 83.7 MW, not relaxed**);
- S0–S3.

## Calls, budget and stop rules

| # | Stage | Runs when | Calls |
|---|---|---|---:|
| 1 | `LP1_LOSSY_IT1` (S_ref = v1.6 capacity) | after approval | 1 |
| 2 | `LP1_LOSSY_IT2` (S_ref = IT1 solution) | only if IT1 is optimal and not converged (r rule or a line on a floor above raw) | ≤ 1 |
| 3 | `LP2_LOSSY_CANDIDATE` | only after an optimal, converged LP1 passing G1–G3, with the candidate written | ≤ 1 |
| | **Total** | | **≤ 3, 0 retries** |

- **STOP:** any non-optimal or invalid solution, IT2 not converged, a guard failure, or the budget used. No automatic rerun.
- **Command (L2, `workflow/`):** `THREADS=<B> bash byop/run/run_post_v16_a2.sh lp1u_chain`, with B measured at launch (about 21 when L2 is quiet). Expected run time is like NEXT-08b: about 40 + 38 + 16 min.

**Not covered by an approval:**
- adopting any candidate as the formal 2025 baseline (your separate decision after LP2);
- any change to frozen v1.6, NEXT-08 or NEXT-08b files;
- S0–S3 runs.

## Proposed approval sentence

> I approve the NEXT-08b lossy LP1 v3 (loss-upper fix) at approved_git_sha d4fd5340945e50c86859024e2ecec86597b630dd: IT1; IT2 only if IT1 is optimal and not converged; LP2 only after a converged LP1 passing G1–G3; transmission_losses 2; at most 3 optimizer calls; 0 retries; no baseline adoption or S0–S3 runs; approved_by: <your identifier>.
