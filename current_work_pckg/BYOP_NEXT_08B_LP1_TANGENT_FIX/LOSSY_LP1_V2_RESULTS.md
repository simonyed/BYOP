# LOSSY_LP1_V2_RESULTS: NEXT-08b lossy 2025 LP1 v2 (reference-capacity loss tangents)

> **Update (2026-10-23, `NEXT_08B_PTDF_DIAGNOSTIC.md`): §3 below is superseded.**
> - **Missed difference:** the "excluded" list overlooked one row. LP1's loss ceiling sits at the 2× cap, while LP2's sits at the actual rating.
> - **What LP1 does with it:** LP1 uses up to 1.46 GW of non-physical dissipation at the shed steps, about 0.4 TWh a year, which LP2 forbids. This is proven with a zero-solver objective-consistency test, PTDF-located on the lines around p610 1.
> - **Hypothesis rejected as main cause:** the resistance and tangent residual adds only 2–3 MW of loss.
> - **Recommendation:** A.

**Verdict.** The approved chain ran completely: 3 optimizer calls, 0 retries, all optimal. LP1 converged and passed G1–G3.
- **LP2 on the v2 candidate:** EENS **817.4 MWh** (PASS, limit 4,882). Largest gap **107.4 MW** (**FAIL**, limit 83.7 MW).
- **Against NEXT-08 v1:** EENS halved and the gap fell by 25 MW, but the gap criterion is still not met.
- **Candidate status:** written but **NOT ADOPTED**, per your approval (no baseline adoption, no S0–S3). The approval is closed.

**Run record:**
- Approval `d5f40f79` (code `5cb7889e`, sw2434@cornell.edu); results commit `812cd2ef`; seal `LOSSY_LP1_V2_SEAL.json`.
- L2, 11 threads (load 13 from another user's jobs at launch); 2026-10-23 18:05–19:39 EDT.
- Frozen v1.6 NetCDFs and the NEXT-08 v1 candidate were re-hashed after the run: unchanged.

## 1. Stages

| Stage | Result | Time |
|---|---|---:|
| `LP1_LOSSY_IT1` (S_ref = v1.6 capacity) | optimal; **not** r-converged (max r gap 22.1 %, 14 lines); uplift 5,930.2 MVA; guards pass | 39 min |
| `LP1_LOSSY_IT2` (S_ref = IT1 solution) | optimal; **r-converged** (max r gap 2.4 %, 0 lines out); **G1** 5,856.4 ≤ 7,727.8 MVA; **G2** no line at cap; **G3** 11.7 MVA on new lines (TL67 8.7, TL154 3.0) ≤ 1,000 | 38 min |
| `LP2_LOSSY_CANDIDATE` (fixed assets, losses 2) | optimal; acceptance **FAIL** on the gap | 16 min |

The candidate (`baseline_2025_tamu_lossy_candidate.nc`, SHA `71726880…`) has capacities identical to the LP1-IT2 solution (maximum difference 0.0 MVA).

## 2. v1.6, NEXT-08 v1 and v2 side by side

| | v1.6 (lossless) | NEXT-08 v1 (tangents at the cap) | **NEXT-08b v2 (tangents at S_ref)** |
|---|---:|---:|---:|
| Total uplift over raw (MVA) | 5,151.8 | 5,816.6 | **5,856.4** |
| LP1 losses, final iteration (TWh) | 0 | 3.90 | **5.67** |
| LP2 losses (TWh) | 0 | 5.32 | **5.32** |
| LP1 / LP2 losses | — | 0.73 | **1.07** |
| LP1 residual EENS (MWh) | 102.2 | 110.9 | **109.7** |
| LP2 EENS (MWh) | 111.8 | 1,657 | **817** |
| LP2 largest gap (MW) | 27.2 | 132.4 | **107.4** |
| LP2 shed hours / events / buses | 12 / 7 / 5 | 60 / 28 / 14 | **48 / 24 / 14** |
| Largest-gap step | 07-14 09:00 (p620 1) | 08-28 09:00 (p610 1 117.2) | **08-28 09:00 (p610 1 95.1 MW)** |

Snapshot dates carry the model's period label 2030, as in v1.6.

**Uplift changes from v1 to v2** (same 20 lines):
- TL73 +21.0, TL69 +5.9, TL68 +5.6, TL26 +3.5, TL63 −3.4 MVA; all others within ±1.5 MVA.
- TL26 (p610 1–p610 2) is still below its v1.6 capacity: 126.3 vs 145.4 MVA.

**LP2 shed by bus (MWh):**
- p610 1: 414.7
- p630 14: 191.4
- p620 1: 82.4
- p620 2: 70.1
- p620 6: 26.8
- the other nine buses: under 9 each.

## 3. What the tangent fix did, and what it did not

- **Fixed: the loss bias.** LP1 now carries at least LP2's losses: 1.07 × in total, against 0.73 × in v1. The lines near p610 1 are no longer invisible to LP1, so the gap fell from 132.4 to 107.4 MW and EENS halved.
  - LP1 sits **above** LP2 mainly on TL28 (2.5 ×), TL27 (3.0 ×), TL22 and TL148. LP1 dissipates loss above its lower envelope there, which an LP may do when energy is in surplus. This is not an under-estimate.
- **Not fixed: LP2 still sheds where LP1 does not.** At the largest-gap step, LP1-IT2 sheds 9.5 MW (p620 6 / p620 2) and LP2 sheds 107.4 MW, 95.1 MW of it at p610 1. In the lossless v1.6 pair, LP1 and LP2 shed almost the same: 102.2 and 111.8 MWh, both with a largest gap of 27.1–27.2 MW at p620 1.

### Read-only diagnosis (0 solver calls; `byop/post/next08b_lp2_shed_diagnostic.py` → `W8B_LP2_SHED_DIAGNOSTIC.json`)

**Excluded as causes:**
- **Capacities:** candidate = LP1-IT2 to 0.0 MVA.
- **Line resistance:** LP2 r is at most 2.5 % above LP1 r_used (TL69 +2.5 %, TL13 +1.9 %, TL68 +1.8 %, TL12 +1.5 %, TL67 +0.6 %, TL26 +0.1 %; TL63 and TL129 0 %).
- **Constraint form:** PyPSA 1.3 builds the same rating row (|s| + loss ≤ s_max_pu · s_nom) and the same tangent rows for extendable (LP1) and fixed (LP2) lines. The v2 tangents equal the fixed-capacity rows at S_ref (static proof, NEXT_08B_REPORT §4).
- **Shed penalty:** LP1's $1,000,000/MWh vs LP2's VOLL $35,685/MWh cannot create shed while LP1's dispatch is feasible in LP2. Every alternative costs far less than VOLL.

**What the LP2 solution shows at the shed steps:**
- 6–13 lines bind at the same time (rule: |p0 − loss/2| + loss ≥ 0.995 × rating). The recurring set is:
  - TL26 (p610 1–p610 2);
  - TL67 (p630 13–p630 14);
  - TL68 and TL69 (p630 13 to p640 1 / p640 2);
  - TL63 (p630 12–p630 2);
  - TL129 (p650 4–p650 6).
- The other lines at p610 1 are lightly loaded at 08-28 09:00:
  - TL28: 389 of 864 MW;
  - TL6: 296 of 684 MW;
  - TL17: 71 of 289 MW;
  - TL27: 54 of 341 MW.
- So the p610 1 shed is set by loop flows through a mesh of binding lines, not by a radial import limit. Across the year, 46 lines bind at least once.

**Remaining explanation (hypothesis, not verified):**
- LP1-IT2 ends at a vertex where many lines bind at once.
- LP2 differs from LP1 only by the convergence residual on exactly those binding lines. That residual is S_ref vs final capacity ≤ 2.45 % (TL69, TL68 1.74 %, TL12 1.48 %), with the matching r difference.
- From IT1 to IT2 the capacities of these lines fell slightly (TL69 234.9 → 229.2, TL68 189.3 → 186.0, TL12 403.9 → 397.9, TL13 1,052.1 → 1,032.1, TL67 107.4 → 106.7 MVA). The candidate's r on them is therefore higher than the r LP1-IT2 used, and its tangent points sit at slightly lower flows, which raises the estimated loss at a given flow below the rating. LP1-IT2's dispatch may then no longer be feasible in LP2.
- If the only control left at p610 1 is shed with a low network sensitivity, a few MW of extra loss on binding loop lines can take tens of MW of shed to relieve.
- Testing this needs a PTDF / sensitivity calculation on the candidate. That needs no solver and is not done yet.

**Reporting note:** the QA field `binding_lines: 0` in `LOSS_BASIS_LP2_QA.json` is an artefact.
- The inherited C1 metric tests |p0| / rating ≥ 0.999, which cannot fire when losses are modelled, because p0 = s + loss/2 and |s| + loss ≤ rating.
- The diagnostic above uses the correct row. The frozen metric code is unchanged.

## 4. Status and decisions for you

- **Unchanged:** the NEXT-08 v1 ledger, candidate and seal; the v1.6 NetCDFs; G1–G3; the LP2 criteria; the S0 / S1 configs.
- `config.byop_lossy_lp1_v2.yaml` approval **CLOSED** (`NOT_APPROVED / null / null`; history in `d5f40f79` and the ledger).
- **No candidate is adopted.** Neither lossy candidate meets the v1.6 gap criterion.

**Possible next steps (none prepared or run):**
1. **Zero-solver sensitivity check** on the v2 candidate: PTDF of the binding set, and the shed at p610 1 per MW of extra loss on TL26 / TL67–TL69 / TL12 / TL13. It confirms or rejects the hypothesis in §3 before any further calls.
2. **If confirmed:** an LP1 consistency step that removes the residual. Either one more iteration with S_ref and r taken from IT2, or a tighter s_tol / r_tol on the binding lines, then one LP2. This needs a code change, a new manifest and your approval. Whether it brings the gap under 83.7 MW cannot be predicted.
3. **Stop the lossy LP1 route** and choose another calibration basis for S0–S3. This is your decision.
