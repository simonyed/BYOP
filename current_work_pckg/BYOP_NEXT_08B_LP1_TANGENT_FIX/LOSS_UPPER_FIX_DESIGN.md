# LOSS_UPPER_FIX_DESIGN: LP1 v3, a capacity-dependent loss upper bound (NEXT-08b, 0 optimizer calls)

**Scope:** the minimal fix of the LP1 feasible-set error found by `NEXT_08B_PTDF_DIAGNOSTIC.md` (recommendation A), designed under your instruction of 2026-10-23 (`NEXT_08B_LOSS_UPPER_INSTRUCTION_RECORD.md`).

**Code:**
- `byop/run/loss_basis_lp1.py`: `apply_affine_loss_upper`, `trust_floor_factor`, the `convergence(…, s_floor)` extension and the static read-back checks.
- Config: `config/config.byop_lossy_lp1_v3.yaml` (`loss_upper: affine_s_ref`).

**Unchanged:**
- tangents at S_ref (the NEXT-08b fix);
- cap 2 × v1.6;
- r proxy and the iteration's r / capacity thresholds;
- G1–G3;
- LP2 and its acceptance (EENS ≤ 4,882 MWh, gap ≤ 83.7 MW);
- S0–S3;
- every earlier ledger and result.

Notation, per line:
- **Variables:** s is the flow (`Line-s`) and loss is `Line-loss`.
- **Rating and resistance:** R = 0.7·s_nom is the rating (an LP variable in LP1), R_ref = 0.7·S_ref, and r = r_pu.
- **Tangents:** K = 2 tangents at p_k = k/K·R_ref.
- **Envelope:** E(a) = max(0, max_k 2r·p_k·a − r·p_k²) is the tangent lower envelope at |s| = a.

The rows common to LP1 and LP2 are loss ≥ E(|s|) (the tangents) and |s| + loss ≤ R (the rating).

## 1. Why the simple fix is wrong (your caution, confirmed)

**The simple fix.** Keeping LP1's loss bound at LP2's fixed-capacity value, loss ≤ r·R_ref², together with the top tangent loss ≥ 2r·R_ref·|s| − r·R_ref², gives:

  2r·R_ref·|s| − r·R_ref² ≤ r·R_ref²  ⇒  **|s| ≤ R_ref, for every s_nom.**

**Consequence.** Extra capacity could never carry more flow, so line expansion would be disabled.

**Test.** `test_representative_points…` builds exactly this "naive" model as a negative control. The largest flow the rating allows above S_ref is then infeasible, and `Line-loss_upper` is the violated row.

## 2. Requirements and an impossibility result

| # | Requirement |
|---|---|
| R1 | Still an LP. |
| R2 | At s_nom = S_ref, identical to LP2 / S0–S3: loss ≤ r·R_ref². |
| R3 | No hidden flow limit: for every capacity in the domain, the flows allowed are exactly those the rating row allows. |
| R4 | No implied capacity bound. The only capacity limits are explicit rows. |
| R5 | Never more dissipation room than LP2 at the same capacity. This is what rules out a return of the GW-scale artefact. |

**Lemma.**
- **Setting.** An LP upper bound loss ≤ U(R) has U concave, since it is a minimum of affine functions. R3 requires U(R) ≥ E(R) on the capacity domain [a, b], because the rating allows |s| up to just below R. R2 requires U(R_ref) = E(R_ref) = r·R_ref².
- **Step 1.** g = U − E is concave (concave minus convex), non-negative on [a, b], and zero at R_ref.
- **Step 2.** If a < R_ref < b, a concave function that reaches its minimum at an interior point is constant. So g ≡ 0 and U = E on [a, b].
- **Step 3.** That requires E to be affine on [a, b].
- **Step 4.** E is affine only where the top tangent alone forms the envelope, which is R ≥ f·R_ref with f = (2K − 1)/(2K) = **0.75**. That is where the tangents K − 1 and K intersect.

**Conclusion.** No LP bound can meet R1–R3 on a capacity domain that extends below 0.75·S_ref. A trust region is necessary, not optional.

## 3. Construction (v3)

  **loss ≤ r·(2·R_ref·R − R_ref²)**, with R = 0.7·s_nom. This is the affine tangent of LP2's r·R² at R_ref, and the top loss tangent evaluated at R.

  **s_nom ≥ max(s_raw, 0.75·S_ref)**: an explicit trust floor, the `Line-ext-s_nom-lower` row.

  **Convergence addition:** a line that ends on a floor above its raw s_nom counts as not converged.
- After IT1, this leads to IT2 with S_ref updated, so the floor moves down.
- After IT2, it leads to STOP, with no LP2.
- The r and capacity thresholds are unchanged.

**Proofs:**
- **P1 (R2).** U(R_ref) = r·R_ref² = LP2's r·(0.7·s_nom)² at s_nom = S_ref. The tangents (NEXT-08b) and the rating rows are already identical at that point, so every loss row equals the fixed-capacity LP2 row.
- **P2 (R3).** For R ≥ 0.75·R_ref, U(R) = E(R). Any |s| the rating allows has |s| < R, so E(|s|) ≤ E(R) = U(R), because E is non-decreasing. So loss = E(|s|) satisfies the bound, and the set of allowed flows is exactly the rating-only set. Raising s_nom raises R and the allowed flow exactly as the rating row does: **expansion keeps its full effect.**
- **P3 (R5).** r·R² − U(R) = r·(R − R_ref)² ≥ 0. The bound is never above LP2's bound at the same capacity, and equals it only at the fixed point.
- **P4 (R4).** U(0.75·R_ref) = 0.5·r·R_ref² > 0, so zero flow with zero loss is feasible at the floor. The affine bound's own implied floor (U ≥ 0 ⇔ R ≥ R_ref/2) lies below the explicit floor and can never bind.
- **P5 (R1).** One affine row per line and step replaces the constant row (coefficient −2·r_pu·R_ref·0.7 on `Line-s_nom`). The row count and the variables are unchanged.

**Cost of the floor.** It is an explicit restriction, reported and fail-closed, on lines whose S_ref exceeds 4/3 × raw. In IT1 that is the v1.6-uplifted lines.
- 15 lines have a floor above raw: TL12, TL13, TL15, TL26, TL35–TL43, TL63, TL69.
- In the sealed v2 chain, the lowest solution / S_ref ratio was **0.87** (TL26) in IT1 and 0.976 in IT2.
- So the floor would not have bound. Without non-physical relief, v3 is expected to need more capacity, not less.

## 4. GW check (R5 in numbers)

- **At the fixed point:** v3 allows exactly LP2's dissipation room. v2 allowed r·((0.7·cap)² − R_ref²) more on every line.
- **More room needs more capacity:** U(R) − U(R_ref) = 2r·R_ref·0.7 × (s_nom − S_ref) MW per line. That room must be bought at 2 × 10⁶ USD per MVA and counts against G1.
- **Real-network numbers** (max rate per MVA; v2 dissipation the v3 bound forbids) are in `results/BYOP/next08b_lp1_loss_upper_fix/LOSSY_LP1_BUILD.json`, reported in §5.

## 5. Static validation

Filled from the L2 run; see `NEXT_08B_LOSS_UPPER_APPROVAL_REQUEST.md`.
