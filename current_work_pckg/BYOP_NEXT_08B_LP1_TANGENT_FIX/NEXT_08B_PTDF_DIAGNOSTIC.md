# NEXT_08B_PTDF_DIAGNOSTIC: why LP2 sheds at p610 1 when LP1 does not (0 optimizer calls)

## Recommendation: **A**, a clear, verifiable residual model inconsistency that justifies one last targeted fix

**What the question assumed, and what the diagnostic found.** The difference between LP1 and LP2 that matters is **not** the resistance and tangent residual the question focused on. It is the **upper bound on line losses**.
- **The cause.** LP2, and every S0–S3 run, caps each line's loss at r·(0.7·s_nom)², the physical loss at full rating. LP1 caps it at r·(0.7·2×v1.6)².
- **What LP1 does with this.** LP1 uses the extra room to "dissipate" up to **1.46 GW** of non-physical loss in the shed hours. These sinks sit at p610 2 and p640 2, the far ends of the binding lines around the p610 1 pocket, and shift loop flow away from TL26.
- **What LP2 cannot do.** LP2 is not allowed to do this, so it sheds instead.

**The resistance and tangent residual is real but three orders of magnitude smaller**: 2–3 MW of extra loss in total at the shed steps.

**Run record:**
- Script `byop/post/next08b_ptdf_sensitivity.py`, run on L2 at `34f1b365`.
- Outputs (SHA-256):
  - `results/BYOP/next08b_lp1_tangent_fix/W8B_PTDF_SENSITIVITY.json` (`3f6bcc54…`)
  - `W8B_PTDF_SENSITIVITY_BY_LINE.csv` (`d1c73f00…`)
  - `.log`
- Inputs: the sealed v2 candidate (`71726880…`) and the sealed LP1 / LP2 outputs (`LOSSY_LP1_V2_SEAL.json`).
- No baseline, ledger, criterion or approval was changed.
- Instruction text: `NEXT_08B_PTDF_INSTRUCTION_RECORD.md`.

## 1. Conventions (as required)

- **Flow and loss split.** `Line-s` = s (bus0 → bus1). The bus balance withdraws loss/2 at each end, so s = p0 − loss/2.
- **Rating row.** |s| + loss ≤ 0.7·s_nom.
- **Tangents.** loss ≥ 2r·p_k·|s| − r·p_k², with p_k = ½ and 1 × 0.7·S_ref.
- **Upper bound.** loss ≤ r·(0.7·S_ref)²; also loss ≥ 0. Here r means r_pu = r/v_nom².
- **PTDF.**
  - Built from x_pu_eff, with PyPSA's slack bus (p600 0) as the zero column.
  - Every sensitivity is a **balanced transfer**: +1 MW at the source and −1 MW over a sink pattern. This makes it independent of the reference bus.
  - Four sink/source patterns are reported:
    - the slack bus;
    - thermal capacity;
    - load at the step;
    - wind available at the step.
- **T0 check.** PTDF·(K·s) reproduces all 2,920 × 162 LP2 flows to within **0.016 MW**. This confirms the PTDF, the slack handling and the loss-split convention.
- **Binding** means |s| + loss ≥ 0.995 × rating. **Relief** means a reduction of |s| in the direction of the LP2 flow.
- **Simultaneous congestion.** 9 to 13 lines bind at once at the shed steps. Every binding line is reported separately; no single line is taken as representative.

## 2. T1: LP1's dispatch is not feasible in LP2 (proven, no optimizer)

Method: price the LP1-IT2 dispatch with LP2's costs and compare it with the LP2 optimum.
- **Removed from LP1:** line capex (2 × 10⁶ USD/MVA × uplift) and shed at the LP1 price of 10⁶ USD/MWh.
- **Added back:** LP1's shed at LP2's VOLL of 35,685 USD/MWh.
- **Common to both:** cost data, capacities and investment weighting (1.0).
- **Accuracy:** Gurobi barrier with crossover, BarConvTol 1e-8. The tolerance used is $0.1M.

| Pair | LP1 dispatch at LP2 prices − LP2 optimum | Reading |
|---|---:|---|
| **v1.6 lossless (control)** | **+$0.57 M** | Consistent: the LP2 optimum is no more expensive than the LP1 dispatch |
| NEXT-08 v1 | **−$111.6 M** | LP1 dispatch **not feasible** in LP2 |
| **NEXT-08b v2** | **−$29.3 M** | LP1 dispatch **not feasible** in LP2 |

**Why this is a proof.** If LP1's dispatch were feasible in LP2, LP2's optimum could cost no more than that dispatch. So the two models have **different feasible sets at identical capacities**. The lossless control confirms the method.

**What it does not show.** It does not say which constraint differs. T2 and T3 test the candidates.

## 3. T2: resistance and tangent residual (the question as posed)

Method: at the LP2 flows of the shed steps, compute each line's LP2 envelope (r_final, tangents at the candidate capacity) minus its LP1-IT2 envelope (r_used, tangents at S_ref).

| | 08-28 06:00 (p610 1 shed 18.9 MW) | **08-28 09:00 (95.1 MW)** | 09-12 06:00 | 09-13 09:00 |
|---|---:|---:|---:|---:|
| Extra LP2 loss, all lines (MW) | 2.14 | 3.21 | 3.21 | 3.02 |

**Tightening of each binding rating row** (extra loss plus the flow shift of the extra loss withdrawals; range over the 4 sink patterns):
- **Largest:** TL38 ≤ 0.52, TL12 ≤ 0.52, TL69 0.39–0.45, TL41 / TL42 ≤ 0.32, TL39 0.23–0.28.
- **Next:** TL68 0.14–0.19, TL35 0.10–0.12.
- **TL26:** 0.02–0.06 MW.

**Linear relief per MW of p610 1 shed** (range over sink patterns):

| Line | Relief per MW of shed |
|---|---|
| TL26 | 0.134–0.138 |
| TL69 | 0.027–0.042 |
| TL68 | 0.022–0.034 |
| TL12, TL38, TL41, TL42 | ≤ 0.004 |
| TL67, TL63 | **negative** (p610 1 shed makes them worse) |

**Reading:**
- On TL26, the line through which p610 1 shed acts most strongly, the residual tightening equals only **0.2–0.4 MW** of p610 1 shed.
- **The single-control estimate is not meaningful here.** It asks how much p610 1 shed would absorb the tightening if shed at p610 1 were the only control.
  - It is undefined, because TL67 cannot be relieved by p610 1 shed.
  - Otherwise it is dominated by lines where p610 1 shed is an ineffective control: TL12 at 0.0036 per MW gives "135 MW".
  - An LP would relieve those lines with other generators. That **redispatch is not evaluated** here, and these numbers are not evidence that the residual causes 95 MW.
- **Conclusion for T2:** the residual exists, but with 2–3 MW of extra loss and sub-MW tightening it is not sufficient on linear evidence.

## 4. T3: LP1 uses non-physical loss that LP2 forbids (the cause)

**Measure.** LP1-IT2 line loss above **1.05 ×** LP2's loss ceiling r_final·(0.7·s_cand)².
- That ceiling is the physical quadratic loss at full rating.
- The 5 % margin covers the r and S_ref residual.
- Loss above it cannot occur at any flow allowed by the rating.

**Over the year:**

| | NEXT-08 v1 | **NEXT-08b v2** |
|---|---:|---:|
| Energy above the ceiling (GWh) | 411.8 | **397.9** |
| Line-steps above it | 2,738 | **2,615** |
| Largest single step (MW) | 1,270 | **1,459** |

- **v2 top lines (GWh):** TL28 98.5 and TL27 94.0 (both at p610 1), TL24 51.3, TL13 34.5, TL148 30.6, TL22 26.8, TL23 20.0 (at p630 14).
- **Own-limit check:** LP1 stays within its own limit r·(0.7·cap)², so this is allowed in LP1 by design.

**At the shed steps:**

| Step | p610 1 shed (MW) | LP1 excess dissipation (MW) | Where | TL26 relief from these sinks (MW, 3 source patterns) | TL26 relief from 95.1 MW of p610 1 shed (MW) |
|---|---:|---:|---|---|---:|
| 08-28 06:00 | 18.9 | **1,459** | p610 2: TL30 450.5, TL31 179.6, TL29 154.1, TL16 66.4, TL7 49.1, TL18 14.2. p640 1/2: TL102 165.9, TL107 59.0, TL106 47.5, TL104 40.9. TL32 157.6. TL11 44.1 | **17.9–20.3** | 13.0–13.1 |
| **08-28 09:00** | **95.1** | **1,236** | same lines; TL32 95.1 | **17.8–19.7** | 13.0–13.1 |
| 09-12 06:00 | 10.3 | 545 | p610 2 lines | 11.2–13.2 | 12.8–13.1 |
| 09-13 09:00 | 10.5 | 205 | TL29, TL31 | 4.4–4.7 | 13.0–13.1 |

**Mechanism.**
- PyPSA's tangent formulation bounds loss only from below. Loss above the envelope acts as a **controllable sink of loss/2 at each end of the line**, up to the loss ceiling.
- LP1's ceiling is set at the 2× cap. That is (2·v1.6 / s_nom)² ≈ 4 × LP2's ceiling on lines that were not uplifted.
- So LP1 can place GW-scale sinks at p610 2, the other end of TL26. This lowers the TL26 loading needed to supply p610 1, a phase-shifter-like effect that does not exist physically.
- With shed priced at $1M/MWh and capacity at $2M/MVA, LP1 prefers this free relief to uplift. TL26 stays at 126.3 MVA, against 145.4 MVA in lossless v1.6.
- LP2 has the physical ceiling, cannot do the same, and sheds at p610 1.
- The incentive also comes from wind's negative marginal cost (down to −12.6 USD/MWh, the PTC): dissipating wind energy that would otherwise be curtailed earns the LP money.

**Where it comes from in the code:**
- v1: PyPSA sets the ceiling from s_nom_max = cap.
- v2: `apply_reference_tangents` deliberately rescales `Line-loss_upper` back to the cap ("feasible range unchanged"). That was a design error. The NEXT-08b tangent fix made the tangents consistent with LP2, but not the ceiling.

**Proven (data and linear algebra, no optimizer):**
1. LP1's dispatch is infeasible in LP2 (T1).
2. LP1 uses 0.2–1.5 GW of dissipation that LP2 forbids at exactly the p610 1 shed steps. 0.4 TWh a year (T3).
3. At the max-gap step, these sinks relieve TL26 by more (17.8–19.7 MW) than the whole 95.1 MW of p610 1 shed does (13.0–13.1 MW), under every source pattern.

**Not proven (needs a solve):**
- That removing this ability alone makes LP1 uplift enough for the LP2 gap to fall below 83.7 MW.
- The effect on TL68 / TL69 depends on where the dissipated energy is generated: positive with wind sources, negative with thermal or load. This redispatch is not evaluated.

## 5. T4: the same relaxation inside LP2 (and S0–S3)

LP2 itself carries **0.25 TWh** above its envelope, 4.7 % of its 5.32 TWh losses.
- 3,086 line-steps sit at its ceiling.
- Top lines: TL24, TL28, TL27, TL13, TL23.

The ceiling here is the physical loss at full rating of the actual capacity, so the effect is bounded and much smaller than in LP1. It is a property of PyPSA's tangent formulation (losses are tight only without an incentive to dissipate), not a new error in LP2. The same small, bounded artefact will be present in S0–S3.

**Proposed follow-up (not done):** add this measure (above-envelope dissipation and line-steps at the ceiling) as a post-solve QA item for S0–S3, so it is reported and not silent. This does not block the mainline.

## 6. Why A, and not B or C

- **A:**
  - The inconsistency is specific and verifiable: T1 proves it, and T3 locates it on the lines around the shed.
  - It sits in one row of the LP1 calibration only.
  - It explains why the NEXT-08b fix improved v1 (the tangents became consistent) but did not close the gap (the ceiling stayed at the cap).
- **Not B:** LP2 and S0–S3 use PyPSA's standard ceiling. The error is confined to how the LP1 calibration sets that ceiling. No new error was found in the S0–S3 model; the bounded artefact in §5 is a QA item.
- **Not C:**
  - Accepting 107.4 MW would freeze a 2025 calibration whose capacities are known to depend on non-physical dissipation, 0.4 TWh a year and up to 1.46 GW in one step.
  - That is a defect in the baseline, not a "residual limitation".
  - The fix is small and does not change any criterion.

**The targeted fix (described only, not prepared, as instructed):**
- **The change:** in LP1, leave `Line-loss_upper` at r·(0.7·S_ref)², which PyPSA already builds when the model is created with s_nom_max = S_ref. Drop the rescale to the cap; this removes one statement in `apply_reference_tangents`.
- **Effect at the fixed point:** LP1's loss rows (tangents and ceiling) then equal LP2's / S0–S3's exactly.
- **Unchanged:** cap, guards G1–G3, LP2 criteria, r rule, convergence rule, ledger and budget pattern (≤ 2 LP1 + 1 LP2, 0 retries; about 1.5 h on L2).
- **Expected direction:** without free relief, LP1 must buy uplift on the p610 1 / p630 13 mesh (TL26, TL68, TL69) or shed at $1M/MWh. G1 has 1,871 MVA of headroom.
- **Whether the LP2 gap then meets 83.7 MW cannot be predicted.**
- **If it does not,** the remaining gap is a genuine network limit, and option C becomes the honest conclusion.

**Not done:** no new LP1 run or configuration was prepared; no code that runs a solver was changed; the frozen v1.6 files, the NEXT-08 and NEXT-08b candidates, the ledgers and the criteria are unchanged.
