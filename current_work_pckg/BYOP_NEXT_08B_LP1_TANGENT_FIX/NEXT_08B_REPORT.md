# NEXT_08B_REPORT: LP1–LP2 loss-approximation fix (0 optimizer calls)

**Result.** The four-tangent LP1 removes the bias on average, but not point-wise. The recommended and implemented minimal fix is **reference-capacity tangents (v2)**: LP1 builds exactly the two tangent rows that LP2 / S0–S3 build for a line of the reference capacity, and the existing outer iteration updates that reference together with r.
- **Formulation:** still an LP, same model size as v1, no new solve batch.
- **Static proof:** passed on the real model.
- **Status:** approved and run on 2026-10-23 (3 calls): LP2 EENS 817 MWh PASS, largest gap 107.4 MW FAIL; see `LOSSY_LP1_V2_RESULTS.md`.
- **Follow-up (v3, loss-upper fix):** approved and run on 2026-10-23 (3 calls): LP2 EENS 140.2 MWh PASS, largest gap 27.76 MW PASS; candidate `f9aa87ae…` NOT ADOPTED; see `LOSSY_LP1_V3_RESULTS.md`.

**Unchanged:** the NEXT-08 ledger, candidate NetCDF, approval SHA and results (18 sealed files and the candidate re-verified by SHA), G1–G3, and the LP2 reliability criteria. LP2 and S0–S3 keep `transmission_losses: 2`.

## 1. Loss-envelope comparison on the saved NEXT-08 candidate (items 2, 3)

Script: `byop/post/next08b_loss_envelope.py`.

**Outputs:**
- `results/BYOP/next08b_lp1_tangent_fix/W8B_LOSS_ENVELOPE_SUMMARY.json`
- `results/BYOP/next08b_lp1_tangent_fix/W8B_LOSS_ENVELOPE_BY_LINE.csv` (162 lines)

**Method.** Every line's PyPSA tangent lower envelope, max(0, max_k 2r·p_k·|s| − r·p_k²), is evaluated at **the same flows**: the LP2 candidate solution, s = p0 − loss/2, 2,920 × 3 h.

**Validation.** The LP2 envelope at its own flows gives 5.058 TWh against the LP2 loss solution of 5.321 TWh, 4.9 % less. The difference is loss the LP2 solution carries above its lower envelope, which is allowed in an LP. It is not an approximation error of this check.

| Option (LP1) | Tangent points | Losses vs LP2 envelope | Lines > 5 % low (of 117 with > 1 GWh) | Worst point-wise shortfall at 0.3–1 × rating |
|---|---|---:|---:|---:|
| **LP2 / S0–S3** (reference) | ½, 1 × rating of the candidate capacity | 1 | — | — |
| **A**: NEXT-08 as run | ½, 1 × s_max_pu·2×v1.6 | **0.637** | **109** | 100 % (zero below the first tangent) |
| **B**: four tangents (as asked) | ¼…1 × s_max_pu·2×v1.6 | 1.001 | 0 | **90.3 % (TL26)** |
| **C**: reference capacity | ½, 1 × s_max_pu·S_ref | **0.997** | **0** | **8.6 %** |

**Readings:**
- **A was a systemic under-estimate on all lines**, not only the uplifted ones, because the 2× cap moved every line's tangents. This explains the 3.90 vs 5.32 TWh gap in NEXT-08.
- **B is not guaranteed to be ≥ LP2, as you cautioned.** Its points come from the fixed cap, not the actual capacity. Where the candidate ends below v1.6 (TL26: 122.8 vs 145.4 MVA), only the lowest tangent is active over most of the operating range, giving a 90 % point-wise under-estimate. Its energy total looks right only because over- and under-estimates cancel.
- **C coincides with LP2 when the reference equals the final capacity.** The residual (worst lines TL69 0.976, TL13 0.980, TL68 0.982, TL12 0.983; point-wise ≤ 8.6 %) is entirely the S_ref vs final-capacity difference: in this replay S_ref is the IT1 solution, and the converged IT2 solution is the candidate. It shrinks with the existing convergence tolerance.

**Lines near the new bottlenecks (p610 1, p630 14, also p620 2, p630 2):**
- **Under A:** TL6 (p600 0–p610 1) 0.17, TL28 (p610 1–p640 5) 0.01, TL27 (p610 1–p630 13) 0.01, TL23 (p610 0–p630 14) 0.16, TL17 (p600 4–p610 1) 0.00 of their LP2 losses. LP1 was blind to these lines' losses, which is consistent with the remaining shed appearing exactly there.
- **Under C:** all at 1.000. TL67 (p630 13–p630 14) is at 0.994; TL26 (p610 1–p610 2) at 1.001.
- **Representative operating range:** median flow 0.16–0.85 and p90 0.27–0.97 of the rating (e.g. TL12 p50 0.85; TL26 p90 0.97; TL6 p50 0.36).

## 2. Resistance vs tangent effects (item 5)

- r_used (LP1 IT2) / r_final (candidate) = **0.979–1.003** on every line.
- At the LP2 tangents, swapping r_final for r_used changes the losses by **−0.2 %** (ratio 0.998).
- With r_final in every option, A = 0.639, B = 1.003, C = 1.000. **The NEXT-08 bias is the tangent placement, not the resistance iteration.**

## 3. Implemented fix: LP1 v2 (item 4)

**Code (`byop/run/loss_basis_lp1.py`, active only when `loss_tangent_reference: s_ref`):**
1. Create the LP1 model with `s_nom_max = S_ref`, so PyPSA writes its two tangents at ½ and 1 × s_max_pu·S_ref. These are exactly the rows of a fixed-capacity model of S_ref.
2. Reset the capacity row `Line-ext-s_nom-upper` to the unchanged guard cap (2 × v1.6) and scale `Line-loss_upper` to r·(s_max_pu·cap)², using linopy `Constraint.update(rhs=…)`.
3. Restore `n.lines.s_nom_max = cap`.

**Properties:**
- Parameter changes of existing rows only: **same variables and constraints as v1, still an LP, no bilinear term.**
- **Reference update:** S_ref is the v1.6 capacity in IT1 and the IT1 solution in IT2. It is the same quantity the r proxy already uses, so **no extra solve batch**.
- **Convergence:** the existing per-line rule (|r_used / r_implied − 1| ≤ 5 % or |Δs| ≤ 10 MVA) also bounds the tangent-reference error.
- **Budget:** unchanged, ≤ 2 LP1 + 1 LP2.
- **Not done (as instructed):** more tangents, more capacity, any change to the criteria.
- **Honest limit:** the fix makes LP1 and LP2 the same formulation at the fixed point. Away from it, the mismatch is the convergence tolerance (≤ 8.6 % point-wise, 0.3 % in total in the replay); it is not zero.

**Config:** `config/config.byop_lossy_lp1_v2.yaml`.
- Differs from v1 only in `loss_tangent_reference`, out_dir `results/BYOP/next08b_lp1_tangent_fix`, the manifest and the authorisation source (`NEXT_08B_INSTRUCTION_RECORD.md`, your instruction verbatim).
- Guards, cap, r rule, convergence, LP2 check and acceptance are identical (tested).

**Run commands:** `lp1r_build`, `lp1r_manifest`, `lp1r_gate`, `lp1r_chain`.

**Three-option code footprint:**

| Option | Footprint |
|---|---|
| A (v1) | unchanged |
| B | would need about +1.9 M rows and still under-estimates point-wise |
| C | about 25 lines, 0 new rows |

## 4. Static validation (item 7)

| Check | Result |
|---|---|
| Real-model build (`results/BYOP/next08b_lp1_tangent_fix/LOSSY_LP1_BUILD.json`) | 2,093,803 variables / 6,902,966 constraints (= v1). **Tangent rows equal the fixed-capacity rows at S_ref on all 162 lines × 2,920 snapshots** (offset deviation ≤ 3e-14, slope 0). Capacity row = guard cap; x raw; r on the 18 lines; losses 2; 0 committable; no solver. |
| Zero-solver chain on the real networks (`_zero_solver_chain/NEXT08_ZERO_SOLVER_CHAIN.json`) | **PASS**: IT1 not converged → IT2 converged → candidate written → LP2. All outputs present; retry refused; frozen v1.6 files unchanged; real v2 ledger never written. |
| Unit tests (`test_next08b_reference_tangents.py`, 4) | v2 config differs from v1 only as intended; v2 tangent rows identical to a fixed-capacity model (small network); v1 tangents still at the cap; loss upper bound and capacity row at the cap; same model size; invalid mode refused; full v2 chain. Deprecated `rhs` setter replaced; passes with DeprecationWarning as error. |
| L2 full regression | **323 passed / 0 failed** (`results/BYOP/next08b_lp1_tangent_fix/N08B_TESTS.log`) |
| NEXT-08 v1 seal | 18 sealed files and the candidate NetCDF re-hashed on L2: **unchanged** |
