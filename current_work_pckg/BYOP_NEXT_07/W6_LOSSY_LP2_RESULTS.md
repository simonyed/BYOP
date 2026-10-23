# W6_LOSSY_LP2_RESULTS: 2025 fixed-asset LP2 on the lossy basis (two approved calls)

**Result: both stages solved optimal and both FAIL the v1.6 reliability criteria.** The v1.6 baseline as calibrated (lossless) does not reproduce 2025 service once losses are on. The r-only correction removes about 91 % of the gap, but not enough.

**Not ready for the formal S0/S1 rerun or S2/S3.** See §4.

## Run record

| Item | Value |
|---|---|
| Authorisation | Researcher in chat, 2026-10-23. Config-only commit `1601c57c` on approved SHA `c93cca5de7d799b290711012347e97e9e5c75f0a`; approved_by `sw2434@cornell.edu`. Approval closed after use. |
| Pre-run safeguard | Zero-solver injected-solution tests (pytest on a small network, plus the real 2.09 M-variable models): `ZERO_SOLVER_POST_PASS`. Suite 308 / 0. All outputs were then written on the real runs. |
| Calls | **2 of 2**, 0 retries. `LP2_LOSSY_ASIS` 14:43–14:55 EDT (701 s); `LP2_LOSSY_R_PARALLEL` 14:55–15:07 EDT (723 s). The second was allowed by the gate because the first was optimal **and** failed acceptance. |
| Threads | 16. The L2 run rule asks for THREADS = B (about 21–22 at the measured load). This is a recorded deviation, with little effect above the 12 physical cores. |
| Untouched | v1.6 runner / ledger / lossless LP1 / LP2 outputs; the NEXT-07 reserve and lossless probes (SHA in `W6_LOSSY_LP2_SEAL.json`) |
| Outputs | `workflow/results/BYOP/next07_loss_basis/LP2_LOSSY_*/`: QA json, shed by bus, events, lines, generation, line flows, **line losses**, r changes |

## 1. Reliability

v1.6 criteria (fixed before the solves): EENS ≤ 4,882 MWh (1e-5 × 2025 energy), largest gap ≤ 83.7 MW.

| | LP2 lossless (v1.6) | **LP2_LOSSY_ASIS** | **LP2_LOSSY_R_PARALLEL** |
|---|---:|---:|---:|
| EENS | 111.8 MWh | **153,266 MWh** (3.1e-4 of energy; 31× the limit) | **13,690 MWh** (2.8e-5; 2.8× the limit) |
| Largest gap | — (pass) | **745.9 MW** (8.9× the limit) | **438.4 MW** (5.2× the limit) |
| When / where is the largest gap | — | 2030-07-31 12:00 (summer midday): p630 2 600 MW, p620 2 106 MW, p620 7 23 MW | same snapshot: p630 2 394 MW, p620 7 34 MW |
| Shed snapshots / hours / events | — | 994 / 2,982 h / 906 | 94 / 282 h / 145 |
| Acceptance | PASS | **FAIL** | **FAIL** |

**Main shed buses (MWh):**

| Run | Shed by bus |
|---|---|
| ASIS (Far West dominates) | p620 6 52,721 · p620 2 38,105 · p620 3 21,554 · p620 7 17,887 · p610 4 7,854 · p620 1 7,696 · p620 4 4,564 · p630 2 1,799 |
| R_PARALLEL | p620 2 5,805 · p620 6 2,034 · p620 3 1,998 · p630 2 1,182 · p620 1 749 · p600 1 450 · p600 2 424 · p620 7 404 |

## 2. Transmission losses

| | ASIS | R_PARALLEL |
|---|---:|---:|
| Total annual losses | **6.64 TWh** (1.36 % of 2025 energy) | **5.29 TWh** (1.08 %) |
| Peak loss | 1,419 MW | 1,228 MW |
| Largest line losses (GWh) | TL38 521, TL13 519, TL133 468, TL12 415, TL84 293, **TL35 246**, TL99 219, TL37 217 | TL133 469, TL13 354, TL84 300, TL99 222, TL38 200, TL12 158, TL21 142, TL93 135 |

These are bulk inter-cluster losses of the 64-cluster network only; losses inside clusters are not represented.

## 3. Key lines (2025, full year)

Each cell is r (Ω) / maximum |p0| (MW) / annual loss (GWh).

| Line (rating MW) | ASIS | R_PARALLEL |
|---|---|---|
| TL35 (461.9) | 15.63 / 387.6 / **246.2** | 2.78 / 445.9 / 41.7 |
| TL43 (119.0) | 15.45 / 117.0 / 22.5 | 8.91 / 117.8 / 13.5 (at ≥ 0.99 of rating 4,560 h) |
| TL36 (137.5) | 9.50 / 135.9 / 14.9 | 4.36 / 136.7 / 7.5 (≥ 0.99 1,593 h) |
| TL44 (68.6) | 12.54 / 68.1 / 2.6 | 12.54 / 67.0 / 2.5 (not uplifted, unchanged) |
| TL12 (251.1) | 70.68 / 225.9 / **415.4** | 21.43 / 240.5 / 158.1 |
| TL13 (636.9) | 12.39 / 527.1 / **519.3** | 8.31 / 557.2 / 353.5 |
| TL15 (306.5) | 7.08 / 300.7 / 55.7 | 1.76 / 305.0 / 14.0 (≥ 0.99 2,070 h) |
| TL21 (1,376.8, not uplifted) | 1.24 / 1,356.0 / 124.1 | 1.24 / 1,356.0 / 142.2 |

**Reading:**
- In ASIS, losses on the uplifted Far West feeders cut their deliverable capacity (TL35 delivers at most 387.6 of 461.9 MW).
- With the r correction, those feeders run at their ratings (TL43, TL36, TL15 near rating for thousands of hours). The remaining shortfall is then **thermal capacity** under lossy flows: Far West p620 2 / 6 / 3 / 1, and a summer-midday spike at p630 2.
- The v1.6 uplift was sized for lossless flows. With losses, the same capacity serves less.

## 4. Assessment and recommendation

1. **The lossy basis is not yet calibrated.** Neither the as-is v1.6 network nor the r-only candidate meets the v1.6 criteria for 2025, a year that ERCOT actually served. A lossy S0/S1 on either network would start from a baseline that fails its own calibration standard.
   - **Recommendation: do not start the formal S0/S1 rerun or S2/S3 yet.**
2. **The r-only correction (R_PARALLEL) stays a candidate synthetic-network calibration assumption.** It is not established as a physical parameter, as you required. It has an engineering rationale: the builder's own parallel-circuit convention, and a 91 % EENS reduction. But it is not validated by passing, and it changes no file. **No baseline file was modified.**
3. **What a consistent next step would be (a researcher decision; nothing prepared to run yet).** v1.6's own calibration method was LP1, a minimum thermal uplift at a fixed cost, so that 2025 is servable. It was solved lossless. The method-consistent repair is to **repeat LP1 on the lossy basis**: same objective, costs and fleet; only `transmission_losses: 2` changes. Then an LP2 lossy check.
   - **Not arbitrary:** this is the approved calibration rule re-applied on the chosen basis, not capacity added to remove scenario shed.
   - **It does change capacities, and so the baseline.** It therefore needs your explicit decision.
   - **Design choices to settle first:**
     - **(a) r rule inside LP1.** Keep pre-calibration r (conservative), or iterate r ∝ 1/capacity. Iterating is not linear inside one LP and needs a fixed-point loop (≥ 2 LP1 calls).
     - **(b) Engineering evidence for the Far West uplift.** For example, the committed and energised ERCOT Far West projects of 2024–25 (DWB stages, the 345 kV rebuilds) that the synthetic network lacks.
     - **(c) Budget.** About 1–2 LP1 calls (the lossless LP1 took 26 min) plus 1 LP2 check, 0 retries.
   - Alternatives you could choose instead: reconsider the loss basis, or accept an explicit, documented 2025 residual with a reliability verdict that carries limits. **I do not recommend these** without the LP1 check.
4. **After a lossy-consistent baseline passes LP2:**
   - write the new baseline file (new SHA; old files kept);
   - paired S0/S1 rerun (2 attempts / ≤ 3 calls);
   - S0 verdict;
   - A3 manifest rebuild and confirmation of the developer-LP reserve rule;
   - S2/S3 (≤ 29 calls).

   Each step needs its own approval.
