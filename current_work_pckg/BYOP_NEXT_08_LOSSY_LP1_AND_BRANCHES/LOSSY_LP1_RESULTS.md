# LOSSY_LP1_RESULTS (NEXT-08): three approved calls

**Result: the calibration converged and passed its guards, but the fixed-asset LP2 on the candidate FAILS the v1.6 largest-gap criterion.**

| Criterion | Limit | LP2 result | Verdict |
|---|---:|---:|---|
| EENS | 4,882 MWh | 1,657 MWh | pass |
| Largest gap | 83.7 MW | **132.4 MW** | fail |

Per the pre-registered rules the chain **stops**: no further call, and no capacity added. The candidate is **not adopted** (your instruction). The cause is identified (§4), and it has a method-consistent fix that needs no extra capacity rule.

## Run record

| Item | Value |
|---|---|
| Authorisation | Researcher in chat, 2026-10-23. Config-only commit `1adf3116` on approved SHA `219bf3e9b7f08c9bc65f69276a2635a37fe8c47c`; approved_by `sw2434@cornell.edu`. Approval closed after use. |
| Pre-run | Gate approved IT1 with no reasons (IT2 / LP2 held back by their stage rules); manifest 0 mismatches; no prior ledger. L2 load 1.8, so 1 process × **21 threads** (B = 22). |
| Calls | **3 of 3**, 0 retries. IT1 15:55–16:25 EDT (1,775 s); IT2 16:25–16:56 (1,853 s); LP2 16:56–17:09 (737 s). Each later stage was allowed by its own gate. |
| Frozen files | v1.6 `prepared.nc` `a623fb6d…` and `raw_uncalibrated.nc` `eb659f9b…` unchanged. All earlier ledgers / results untouched. |
| Candidate | `results/BYOP/next08_lossy_lp1/baseline_2025_tamu_lossy_candidate.nc` (SHA `4720185461d3204a…`, L2 only). **Not adopted.** |
| Seal | `LOSSY_LP1_SEAL.json` (18 output files SHA-pinned) |

## 1. LP1 iterations

| | IT1 (r from v1.6 capacities) | IT2 (r from the IT1 solution) |
|---|---:|---:|
| Status | optimal | optimal |
| r-converged | **no** (13 lines; max gap 18 % on TL69) | **yes** (max 2.1 %) |
| Residual EENS / largest gap inside LP1 | 112.8 MWh / 27.1 MW (p620 1) | 110.9 MWh / 27.1 MW |
| Total uplift over raw | 5,883.9 MVA (20 lines) | **5,816.6 MVA (20 lines)** |
| G1 ≤ 7,727.8 MVA · G2 no line at cap · G3 new lines ≤ 1,000 MVA | pass · pass · pass (new: TL67 7.5, TL154 3.0) | **pass · pass · pass** (new: TL67 7.0, TL154 2.9) |
| Losses (LP1's own approximation) | 4.00 TWh | 3.90 TWh |
| Objective (uplift penalty + operation + shed) | 19.44 B | 19.30 B |

**Uplift vs v1.6** (`results/BYOP/next08_lossy_lp1/LP1_VS_V16_UPLIFT.csv`): **+664.8 MVA in total (+12.9 %).**
- Largest increases: TL13 +122.8, TL73 +103.7, TL38 +102.3, TL37 +60.2, TL39 +45.6, TL12 +39.6, TL42 +34.7, TL69 +30.8, TL35 +30.5.
- TL26 is −22.6 MVA below v1.6.
- Every v1.6 line stays the same order of magnitude; no line approaches its cap.

**Resulting resistances** (raw → proxy, Ω): TL35 15.6 → 2.6; TL12 70.7 → 19.0; TL13 12.4 → 7.2; TL38 3.0 → 1.2. These are synthetic-network calibration proxies, not physical line data.

## 2. LP2 on the candidate (fixed assets, losses 2, unchanged v1.6 acceptance)

| | v1.6 lossless LP2 | W6 lossy, raw r | W6 lossy, r-scaled v1.6 | **NEXT-08 candidate** |
|---|---:|---:|---:|---:|
| EENS (limit 4,882 MWh) | 111.8 | 153,266 | 13,690 | **1,657.1 ✅** |
| Largest gap (limit 83.7 MW) | pass | 745.9 | 438.4 | **132.4 ❌** |
| Shed snapshots / hours / events | — | 994 / 2,982 / 906 | 94 / 282 / 145 | **20 / 60 / 28** |
| Total losses | 0 | 6.64 TWh (1.36 %) | 5.29 TWh (1.08 %) | **5.32 TWh (1.09 %)**, peak 1,397 MW |

**Largest gap:** 2030-08-28 09:00 (late-summer morning); p610 1 117.2 MW, p620 6 8.2, p620 2 5.8, p620 7 1.1.

**Main shed buses (MWh):** p610 1 869.3 · p630 14 320.4 · p620 2 122.9 · p630 2 101.2 · p620 1 82.0 · p620 7 67.7 · p630 13 45.3 · p620 6 24.7.

**Largest line losses (GWh):** TL133 467 · TL13 321 · TL84 311 · TL99 224 · TL38 185 · TL8 172 · TL21 162 · TL12 160.

**Key lines** (r Ω / rating MW / max |p0| MW / loss GWh):

| Line | r | Rating | Max \|p0\| | Loss |
|---|---:|---:|---:|---:|
| TL35 | 2.65 | 483.3 | 466.5 | 38.4 |
| TL43 | 8.62 | 122.9 | 121.7 | 13.6 |
| TL36 | 4.12 | 145.3 | 144.5 | 7.2 |
| TL44 | 12.54 | 68.6 | 67.0 | 2.6 |
| TL12 | 19.3 | 278.8 | 267.0 | 159.7 |
| TL13 | 7.33 | 722.8 | 632.4 | 320.8 |
| TL15 | 1.76 | 306.9 | 305.4 | 13.5 |
| TL21 | 1.24 | 1,376.8 | 1,356.0 | 162.2 |

**The Far West pocket that drove the S0 problem is now served:** p620 6 / 7 shed 25 / 68 MWh in the whole year, against 52,721 / 17,887 MWh with raw r. The remaining gap moves to **p610 1** and **p630 14**.

## 3. Why LP1 says "served" but LP2 does not

The two LPs approximate losses differently:
- **LP1:** total losses 3.90 TWh. Its extendable lines have `s_nom_max` = 2 × v1.6, and PyPSA places the two loss tangents at ½ and 1 × `s_max_pu·s_nom_max`, i.e. at **1× and 2× the v1.6 rating**. Below the v1.6 rating, the lower envelope underestimates the quadratic loss heavily: at a quarter of the cap the first tangent gives zero.
- **LP2 / S0–S3:** total losses 5.32 TWh (+37 %). Lines are fixed (`s_nom_max = s_nom`), so the tangents sit at **½ and 1× the actual rating**.

LP1 therefore saw **less loss than the test network**, and bought slightly too little capacity where flows are moderate (p610 1, p630 14). This is a **design error in my cap choice**, not a data finding. The capacity–resistance logic itself worked: the iteration converged and the guards held.

## 4. Recommendation

1. **No formal baseline adoption and no S0–S3** (your instruction, and the candidate fails anyway).
2. **The method-consistent fix** (a new static preparation, then a new approval).
   - Make LP1's loss approximation at least as tight as LP2's, so that LP1 can never "see" less loss than the S0–S3 basis: **`transmission_losses: {mode: tangents, segments: 4}` in LP1 only**.
   - With the cap at 2 × v1.6, the 4 tangents sit at ¼, ½, ¾ and 1 × the cap, i.e. at ½ and 1 × the v1.6 rating among others. **They contain LP2's own tangent points**, so LP1 losses ≥ LP2 losses on every line whose rating stays near v1.6, and LP1 is tighter everywhere else.
   - S0–S3 and the LP2 check keep the chosen basis (`transmission_losses: 2`).
   - **Expected effect:** a modest further uplift where flows are moderate, judged by the same unchanged G1–G3 guards. No other change, and no capacity rule changed.
   - **Cost:** about +1.9 M loss rows in LP1 (~8.8 M constraints); budget again ≤ 2 LP1 + 1 LP2, 0 retries.
3. **Alternatives (not recommended now):**
   - secant losses in LP1 (`transmission_losses: True`). This always overestimates, so it may over-expand;
   - accepting a documented 2025 residual gap with the reliability verdict carrying limits. This only makes sense if you judge 132 MW at one late-summer morning acceptable for the research question.
4. **After an LP2 PASS:** candidate adoption (your decision, new baseline SHA), then the paired S0/S1 rerun, then the S0 verdict, then S2/S3. Each is approved separately.
