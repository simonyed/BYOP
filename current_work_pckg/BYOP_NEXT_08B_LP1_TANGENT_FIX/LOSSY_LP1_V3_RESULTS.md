# LOSSY_LP1_V3_RESULTS: NEXT-08b lossy 2025 LP1 v3 (loss-upper fix)

> **Update (2026-10-23, NEXT-09):** the candidate is frozen byte for byte as baseline version **v1.7L** (`baseline_2025_tamu_v17_lossy/`, same SHA). Adoption and the paired S0 / S1 rerun are prepared but not approved: see `../BYOP_NEXT_09_V17L_BASELINE_ADOPTION/NEXT_09_ADOPTION_AND_S0S1_REQUEST.md`.

**Verdict: PASS.** The approved chain ran completely: 3 optimizer calls, 0 retries, all optimal. LP1 converged in IT2 with no line on a trust floor and passed G1–G3.
- **LP2 on the v3 candidate:** EENS **140.2 MWh** (limit 4,882) and largest gap **27.76 MW** (limit 83.7 MW, not relaxed). Both criteria pass.
- **Against v1.6 (lossless):** the lossy pair now reproduces v1.6's shed pattern. The largest gap is at the same step and bus (07-14 09:00, p620 1) and is within 0.6 MW of v1.6.
- **Candidate status:** written but **NOT ADOPTED**, per your approval (no baseline adoption, no S0–S3). Adoption needs a separate decision. The v3 approval is closed.

**Run record:**
- Approval `2c2c64a2` (code `d4fd5340`, sw2434@cornell.edu); seal `LOSSY_LP1_V3_SEAL.json`.
- L2, 20 threads (load about 4.8, about 1 core used by others at launch); 2026-10-23 21:04–22:43 EDT.
- After the run I re-hashed the frozen v1.6 NetCDFs, the NEXT-08 v1 and NEXT-08b v2 candidates, and both earlier ledgers. All are unchanged.

## 1. Stages

| Stage | Result | Time |
|---|---|---:|
| `LP1_LOSSY_IT1` (S_ref = v1.6 capacity) | optimal; **not** r-converged (max r gap 21.2 %, 12 lines); 0 of 15 floor lines on their floor; uplift 5,950.1 MVA; guards pass | 34 min |
| `LP1_LOSSY_IT2` (S_ref = IT1 solution) | optimal; **r-converged** (max r gap 2.2 %, 0 lines out); 0 of 17 floor lines on their floor (lowest s_opt / S_ref 0.978); **G1** 5,875.1 ≤ 7,727.8 MVA; **G2** no line at cap; **G3** 7.8 MVA on new lines (TL67 4.3, TL154 3.5) ≤ 1,000 | 48 min |
| `LP2_LOSSY_CANDIDATE` (fixed assets, losses 2) | optimal; acceptance **PASS** | 15 min |

The candidate (`baseline_2025_tamu_lossy_candidate.nc`, SHA `f9aa87ae…`) has the LP1-IT2 capacities (maximum difference 1.8e-12 MVA).

## 2. v1.6, v1, v2 and v3 side by side

| | v1.6 (lossless) | NEXT-08 v1 (tangents at the cap) | NEXT-08b v2 (tangents at S_ref) | **NEXT-08b v3 (+ affine loss upper)** |
|---|---:|---:|---:|---:|
| Total uplift over raw (MVA) | 5,151.8 | 5,816.6 | 5,856.4 | **5,875.1** |
| LP1 losses, final iteration (TWh) | 0 | 3.90 | 5.67 | **5.22** |
| LP2 losses (TWh) | 0 | 5.32 | 5.32 | **5.29** (1.08 % of load) |
| LP1 / LP2 losses | — | 0.73 | 1.07 | **0.99** |
| LP1 residual EENS (MWh) | 102.2 | 110.9 | 109.7 | **108.7** |
| LP2 EENS (MWh) | 111.8 | 1,657 | 817 | **140.2** |
| LP2 largest gap (MW) | 27.2 | 132.4 | 107.4 | **27.76** |
| LP2 shed hours / events / buses | 12 / 7 / 5 | 60 / 28 / 14 | 48 / 24 / 14 | **21 / 14 / 11** |
| Largest-gap step | 07-14 09:00 (p620 1) | 08-28 09:00 (p610 1 117.2) | 08-28 09:00 (p610 1 95.1) | **07-14 09:00 (p620 1 27.3)** |

Snapshot dates carry the model's period label 2030, as in v1.6.

## 3. What the fix did

- **The non-physical dissipation is gone.**
  - No line carries more loss in LP1 than in LP2: the largest per-line LP1 / LP2 ratio is 1.00, on lines with more than 20 GWh in LP2.
  - In v2, TL28 was at 2.5 × and TL27 at 3.0 ×.
  - LP1 is now slightly *below* LP2 on a few lines: TL24 0.81, TL27 0.87, TL13 0.90. This is the expected two-tangent under-estimate of r·s² between the tangent points. It totals 1.2 % of losses.
- **p610 1 no longer sheds in LP2.**
  - LP1 now buys **TL26 (p610 1–p610 2) at 153.9 MVA**, against 126.3 in v2 and 145.4 in v1.6.
  - Without the fake loss sink, LP1 had to pay for the capacity that LP2 actually needs.
  - Other uplift changes from v2 to v3: TL73 +15.3, TL43 +1.5, TL12 −5.9, TL67 −4.4, TL3 −4.1, TL68 −3.9, TL63 −2.7, TL69 −1.1 MVA. All other lines are within ±1 MVA.
- **The trust floor never bound.** No line ended on a floor above raw in either iteration, so no capacity was imposed by the floor.

## 4. The remaining LP2 shed (below the thresholds, not zero)

| Bus | MWh | Main step |
|---|---:|---|
| p620 1 | 82.4 | 07-14 09:00 (27.3 MW), the same event as v1.6 |
| p620 6 | 24.7 | 08-28 09:00 |
| p620 2 | 10.1 | 08-28 09:00 |
| p600 2 | 8.3 | 07-31 09:00 |
| 7 others | 14.8 | each 4.6 MWh or less |

- LP1-IT2 itself sheds 108.7 MWh at p620 1 and p620 6 (gap 27.1 MW). So almost all of the LP2 shed is the residual that the calibration already accepts, as in v1.6.
- The extra 31.5 MWh is spread thin. No event outside p620 1 and p620 6 peaks above 3.4 MW. It is the residual of the two-tangent loss approximation.

## 5. Scope and next decision

- **Not done:** baseline adoption, any S0–S3 run, any change to frozen v1.6 / NEXT-08 / NEXT-08b files.
- **Closed:** the v3 approval (`config.byop_lossy_lp1_v3.yaml` back to `NOT_APPROVED / null / null`).
- **Your decision:** whether to adopt `baseline_2025_tamu_lossy_candidate.nc` (`f9aa87ae…`) as the formal lossy 2025 baseline. The next steps on the existing plan need separate approvals:
  - the paired S0/S1 rerun on this basis;
  - the A3 manifest rebuild;
  - S2 / S3.
