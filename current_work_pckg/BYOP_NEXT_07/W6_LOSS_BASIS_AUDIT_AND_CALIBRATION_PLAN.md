# W6: lossy basis, line-loss audit, lossy 2025 LP2 re-validation and calibration plan

**Decision (researcher, 2026-10-23, `W6_LOSS_BASIS_DECISION_RECORD.md`):** S0–S3 use lossy transmission, with the mainline `transmission_losses: 2`.

**This step:** static audit, model builds and calibration design only. **0 optimizer calls.** No existing lossless or lossy result was changed.

## 1. Static audit (`results/BYOP/next07_loss_basis/W6_LINE_LOSS_AUDIT.csv/.json`)

| Check | Result |
|---|---|
| Unit conversion | PyPSA `r_pu_eff` = r [Ω] / v_nom² [kV²] exactly, for all 162 lines (max relative error 0). Loss in MW = r_pu_eff · S², matching 3-phase physics: P = R·S²/V². All buses are 230 kV in the clustered network. |
| Loss approximation | Two tangents at ½ and 1 × rating; lower envelope; `loss ≤ r_pu_eff · rating²`. Maximum underestimate 1.2 % at 0.9 × rating. Adequate. |
| Rating row with losses | `|s| + loss ≤ s_max_pu · s_nom` (PyPSA, Neumann & Brown 2022), with half of the loss at each end. **Conservative:** the sending end is limited to rating − loss/2; about 25 MW on TL35. This is PyPSA's documented formulation; left unchanged and recorded. |
| Linearised unit commitment | No committable generator in the baseline, so it has no effect on LP2. |
| Resistance, generally | Median 0.037 Ω/km, p90 0.32 Ω/km. Several very high per-km values (TL94, TL40, TL26 ~0.6 Ω/km; TL25 472 km) come from the TAMU synthetic cluster equivalents (length = cluster-centroid distance). **No engineering basis to change them.** |
| Interface-rule lines | The builder scales x and r by 1/capacity (parallel-circuit convention, `build_2025_baseline_tamu.py:324–326`), so r is consistent with capacity there. |
| **The 18 calibration-uplifted lines (X1)** | `apply_uplift(v16=True)` raised **only s_nom** (+5,151.8 MVA in total); x and r stayed pre-calibration. The approved X1 rule deliberately kept x (the flow split). Keeping r had **no effect in the lossless calibration**. Under losses, each uplifted line carries up to ×1.08–×5.63 its pre-calibration capacity through a resistance sized for that pre-calibration capacity. |

Loss share at full rating on the uplifted lines, with the formal r and with r scaled by raw / prepared s_nom (the builder's own convention, applied to r only):

| Line | Capacity ratio | Formal | r scaled |
|---|---:|---:|---:|
| TL35 | 5.63 | 13.6 % | 2.4 % |
| TL12 | 3.30 | 33.6 % | 10.2 % |
| TL13 | 1.49 | 14.9 % | 10.0 % |
| TL69 | 1.45 | 12.4 % | 8.6 % |
| TL42 | 2.38 | 12.1 % | 5.1 % |
| TL40 | 2.64 | 10.3 % | 3.9 % |
| TL43 | 1.73 | 3.5 % | 2.0 % |
| TL15 | 4.03 | 4.1 % | 1.0 % |

## 2. Prepared lossy 2025 LP2 re-validation (gated, NOT run)

**Runner:** `byop/run/loss_basis_lp2.py`. It has its own config `config.byop_loss_basis_lp2.yaml`, ledger `results/BYOP/next07_loss_basis/LOSS_BASIS_LP2_SOLVE_LOG.csv` and manifest. The consumed v1.6 runner, ledger and outputs are untouched.

**Kept identical to v1.6 LP2:** the C1 fixed-asset rules (2025 fleet, every capacity fixed, cyclic storage, shed at VOLL), solver options and **acceptance tolerances**:
- EENS ≤ 1e-5 × 2025 energy = 4,882 MWh;
- largest gap ≤ 83.7 MW.

| Stage | What | When |
|---|---|---|
| `LP2_LOSSY_ASIS` | the v1.6 prepared baseline as is, `transmission_losses: 2` | first |
| `LP2_LOSSY_R_PARALLEL` | as above, with r of the 18 uplifted lines × raw / prepared s_nom. **x and every capacity unchanged; nothing added.** | only if ASIS solves optimal **and fails** the acceptance (enforced by the gate) |

**Static build (`W6_LOSSY_LP2_BUILD.json`, no solver):**
- Both models: 2,093,640 variables / 6,902,642 constraints, with the loss rows present.
- Same size, same total line capacity (198,015 MW) and same total x. Only the 18 r values differ (Σr 1,836 → 1,680 Ω).
- Lossless LP2 solved in 257 s; lossy LP2 is expected to take about 5–20 min each.

**Tests and gate:**
- L2 full suite: **305 passed / 0 failed**.
- Manifest: L2-built at `4ab5b88d`, 152 code + 110 input files, 0 mismatches.
- Gate: `LP2_LOSSY_ASIS` refuses only on the approval fields; `LP2_LOSSY_R_PARALLEL` additionally on its stage rule.

## 3. Calibration decision tree (fixed before any solve)

| LP2 outcome | Reading | Next |
|---|---|---|
| ASIS **PASS** | v1.6 holds on the lossy basis for 2025. No calibration change. | The formal S0/S1 (already lossy) stand. The 2026 S0 shortfall is then a feature of 2026 conditions under losses; the researcher decides the S0 verdict (e.g. `PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS`). No S0/S1 rerun is needed for the basis. |
| ASIS fails, R_PARALLEL **PASS** | The X1 resistance on uplifted lines is the inconsistency. The fix is engineering-based (the builder's own convention) and adds no capacity. | Researcher approves a **v1.6.1 amendment (r only, 18 lines)**. A zero-solver script writes the amended baseline (new SHA, old file kept). Then a **paired S0/S1 rerun** on it, then the A3 manifest rebuild and S2/S3. |
| ASIS fails, R_PARALLEL **fails** | The lossy basis needs more than the r correction | Read-only residual analysis (which buses / hours / lines). **No capacity uplift** without separate engineering evidence and a separate researcher decision. |
| Infeasible / error | `BLOCKED` | Evidence kept, no retry |

## 4. Optimizer-call budget (each line needs its own explicit approval)

| Step | Calls | Status |
|---|---:|---|
| W6 `LP2_LOSSY_ASIS` (+ conditional `LP2_LOSSY_R_PARALLEL`) | **≤ 2**, 0 retries | **Requested now** (one approval covers both; the gate enforces the condition) |
| v1.6.1 amended baseline file | 0 (no solver) | only if R_PARALLEL passes and you approve the amendment |
| Paired S0/S1 rerun on the chosen baseline | 2 attempts / ≤ 3 calls, 0 retries | separate request (new SHA, A2-type gate) |
| A3 pilot (S0 → S1 → S3 → S2 1–3 iterations → S3_mS2) | ≤ 29, 0 retries | separate request after the S0 verdict (manifest rebuild, developer-LP reserve rule confirmation) |

## 5. Approval request

| Item | Value |
|---|---|
| Approvable SHA | **`3a9f68a82d158e9033566674e31664147a31c3f4`** (`mainline-v13-stageA` = L2 = GitHub) |
| Config | `workflow/config/config.byop_loss_basis_lp2.yaml` (now `NOT_APPROVED / null / null`) |
| Commands (L2, `workflow/`) | `bash byop/run/run_post_v16_a2.sh lb_gate`, then `THREADS=<T> … lb_lp2_asis`, and only if the gate allows it, `… lb_lp2_r_parallel` |

Proposed sentence:

> I approve the NEXT-07 W6 lossy 2025 LP2 re-validation at approved_git_sha 3a9f68a82d158e9033566674e31664147a31c3f4: LP2_LOSSY_ASIS, then LP2_LOSSY_R_PARALLEL only if ASIS is optimal and fails the v1.6 acceptance; transmission_losses 2; at most 2 optimizer calls; 0 retries; approved_by: <your identifier>.
