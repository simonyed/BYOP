# S0_S1_MAINLINE_FINDINGS: first formal S1−S0 result (ERCOT, 16 research buses, 2026–2031, mid demand, LP)

**Status:** S0 PASS, S1_EARLIEST PASS (independent acceptance), with 3 top-level optimizer calls. The collector's TECHNICAL_GATE is PASS. Use is **exploratory, with method flags**: S0 has existing-customer shed that needs your reliability review (§3). Data: `S0_S1_MAINLINE_COMPARISON.csv`; outputs `workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1/`.

## 1. What new AIDC demand does to the public system (S1 − S0)

| Metric (PV, 2026–2031) | S0 | S1_EARLIEST | S1 − S0 |
|---|---:|---:|---:|
| Public resource capex | 7.54 B$ | 9.08 B$ | **+1.54 B$** |
| System operating cost | 43.27 B$ | 43.45 B$ | +0.18 B$ |
| POI upgrades | 0 | 2,204 MW / 0.026 B$ | +2,204 MW |
| Social real resource cost | 52.75 B$ | 54.46 B$ | **+1.71 B$** |
| Delay loss of unserved AIDC (social) | 0 | 1.61 B$ | +1.61 B$ |
| Existing-customer shed | 54,206 MWh | 54,008 MWh | −198 MWh (no-harm held) |

New public capacity by 2031 (cumulative MW), S0 → S1:

| Asset | S0 | S1 | Difference |
|---|---:|---:|---:|
| Solar | 9,561 | 12,878 | +3,317 (+3,773 in 2029–30) |
| Onshore wind | 25,349 | 27,254 | +1,906 |
| CCGT (2031) | 192 | 870 | +678 |
| 4 h BESS | 642 | 849 | +206 |
| 8 h BESS | 180 | 233 | +53 |
| AC corridor expansion (two-way MW, 2031) | 36,371 | 35,155 | **−1,216** (−156 in 2030) |

- **The AIDC load is met mainly by more renewables, BESS and some CCGT**, timed to their leads (solar from 2028, wind from 2029, CCGT in 2031).
- **Corridor expansion is slightly lower in S1.** Generation built near the DC buses substitutes for some transfer capacity. This is a mechanism result, not yet attributed.

## 2. Speed-to-power under Grid-Only (S1_EARLIEST)

| Year | Requested IT MW | Served | Not served |
|---|---:|---:|---:|
| 2026 | 105 | 8 | 97 |
| 2027 | 808 | 639 | 169 |
| 2028 | 1,597 | 1,273 | 324 |
| 2029–2031 | 2,366 / 3,018 / 3,532 | all | 0 |

- **Total:** 591 of 11,426 MW-IT-years are not delivered on time (5.2 %).
- **Where:** at the North-Central (p630, DFW-area) sites, and p610 2 / p600 0 in 2026.
- **Why:** the POI constraint binds until the earliest grid COD (2028 or 2029). Once the POI upgrades come online (2,204 MW cumulative by 2031), every request is served.
- **The waiting is real but short:** 2026–2028 only, and concentrated at a few POIs. Formal single-factor attribution (POI vs adequacy vs procedure) was not run; it is outside the approved scope.

## 3. Reliability flag (needs your review)

- **The shed:** S0 sheds 54,206 MWh of existing customer load, weighted to the year. **94 % of it is in 2026** (51,049 MWh); it falls to 2,065 MWh in 2027, about 1,000 in 2028, 67 in 2029 and 0 from 2030. Most is at the Far West buses **p620 6** (32,052 MWh) and **p620 7** (16,250 MWh).
- **Interpretation:** in 2026 the frozen 2025 network plus the committed DWB Stage 2 (mid-2026) cannot serve Far West stress load. No costed public expansion can be online yet, because of the lead times.
- **Consistent evidence:** this matches A1's network-side infeasibility (`A1_FIXED_NETWORK_EXCEPTION`), which binds in West Texas.
- **Effect on S1:** S1 inherits it exactly; no-harm holds.
- **Comparison with v1.6:** 54 GWh is far above v1.6's 111.8 MWh annual-calibration shed. The likely causes are the new 3 GW reserve rule, the corrected 3 h storage step and the segment-neutral SOC, all of which remove storage arbitrage the old model allowed. This has **not** been proven by an attribution run.

## 4. Limits

- Single weather year; sampled 3 h segments (2 weeks + 3 stress days per period, energy-neutral).
- Aggregate reserve proxy.
- Gas at L2; POI and permit inputs are research proxies; 8 sites UNKNOWN_CONSERVATIVE.
- Only 2026–2031, so no claim about 2036–2050 lock-in.
- The post-solve per-asset SOC segment audit **could not be built** (the run does not persist SOC; see `A2_SOC_SEGMENT_POSTSOLVE_AUDIT.csv`).
