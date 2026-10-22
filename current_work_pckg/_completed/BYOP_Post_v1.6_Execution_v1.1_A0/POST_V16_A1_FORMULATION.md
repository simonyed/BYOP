# POST_V16_A1_FORMULATION: 1 h stress LP, 3,000 MW / 1 h reserve, joint headroom λ (static, A0)

Status: these models are built and checked without a solver (A0). Nothing has been solved.

- Code:
  - `workflow/byop/model/post_v16_headroom.py` builds the models.
  - `workflow/byop/run/post_v16_a1.py` is the entry point.
  - `workflow/byop/model/post_v16_gate.py` is the gate.
- Config: `workflow/config/config.byop_post_v16_a1.yaml` (`NOT_APPROVED`).
- Tests: `workflow/byop/tests/test_post_v16_a0.py`.

## 1. Fixed inputs (identical in LP-R and LP-N)

| Item | Definition | Source / check |
|---|---|---|
| Network | v1.6 `baseline_2025_tamu_prepared.nc`, SHA `a623fb6d…747d16`, 63 buses / 162 lines; only the 2025 fleet is used (extendable units and units with build_year > 2025 removed). Every `*_nom` is fixed, and links and global constraints are removed. | Gate check 5. `test_real_v16_models_build_without_solver`: 155,446.9 MW, 2 switchable plant groups. |
| Windows | Three pre-registered 72 h windows, 1 h source rows: <br>• 2025-08-17..19 (rows 5471–5542), which contains both the summer load peak (HE18) and the summer observed net peak (HE21); it counts as **one** window. <br>• 2025-02-19..21 (rows 1176–1247), winter peak. <br>• 2025-07-29..31 (rows 5015–5086), the disjoint hold-out. | `PRE_REGISTERED_STRESS_EVENTS.csv`. No DST hour in any window. `STRESS_SOURCE_VINTAGE_QA.json` |
| Blocks | Six investment-period blocks: B0 (λ = 0) and BL (λ) × 3 windows, 432 hourly snapshots of weight 1. Storage SOC is cyclic inside each block; there is no coupling across windows or blocks. | `snapshot_index` |
| Existing load | Native Load 2025 1 h by weather zone → bus, using the v1.6 builder rule (COUNTY_TO_BUS_SHARES, lpf × substation share). | Equals native load to 1e-9. The 3 h means equal the v1.6 network on the 70 complete 3 h steps (max \|Δ\| 1.8e-12 MW). |
| Inherited ramp | 460.73 MW IT × PUE TX 2025 (1.1583) = 533.7 MW facility at its 5 buses, flat, in both blocks. It is protected existing load and is never part of λ. | INV-17 |
| Wind / solar availability | v1.6 network `p_max_pu` of the 3 h step that contains the source row, held for 3 h. These are model-weather profiles, **not** observed 2025 output, and not the same weather year as the load. | Vintage QA `same_weather_year: false` |
| Thermal availability | v1.6 `p_max_pu`. The Kiamichi and Tenaska Gateway monthly caps are used once, in both dispatch and reserve. MORA outage quantiles are **not** applied. | Unknown-data flag |
| Weights | w_b = cumulative mid IT 2026–2031 × PUE TX 2031, normalised over the 16 dynamic_pnnl_v1 buses. This equals `research_facility_MW_2031_mid` (POI table). | `test_weights_16_buses_facility_vs_it` |

## 2. Constraints added to the PyPSA dispatch LP (DC power flow, storage energy balance and bounds unchanged)

For every hour t and block, where E is the eligible thermal + hydro set and S is storage:

```text
new load       p_newload_b(t) = -λ · w_b                          (BL)    p_newload_b(t) = 0 (B0, by bounds)   [PV16-newload]
online cap     p_g(t) <= c_g(t) <= p_nom_g · avail_g(t)                                                   [PV16-online_max_p, bound]
min stable     p_g(t) >= pmin_g · c_g(t)                          (LP relaxation of commitment, no binaries) [PV16-online_min]
thermal res.   r_g(t) <= c_g(t) - p_g(t)  and  r_g(t) <= rho_g · c_g(t),  rho_g = min(1 - pmin_g, ramp_g · 10 min)   [PV16-res_thermal_head, PV16-res_ramp]
storage res.   r_s(t) <= p_nom_s - p_dispatch_s(t) + p_store_s(t)                                          [PV16-res_su_power]
               tau · r_s(t) / eff_dispatch_s <= SOC_s(t)          (the dispatch SOC variable itself)        [PV16-res_su_energy]
requirement    sum_E r_g(t) + sum_S r_s(t) >= 3000 MW                                                     [PV16-reserve_req]
objective      min  1e-5 · dispatch cost + 1e3 · sum existing shed (MWh) - λ                               (lexicographic weights)
```

- **Not eligible for reserve:** nuclear, wind, solar, load shed and the new AIDC load. Hydro is eligible with pmin 0 and rho 1.
- **Parameters:** `byop/inputs/post_v16/POST_V16_RESERVE_PARAMETERS.csv`, base column.

  | Carrier | pmin | rho |
  |---|---:|---:|
  | CCGT | 0.5 | 0.4 |
  | OCGT | 0.4 | 0.6 |
  | gas steam | 0.4 | 0.2 |
  | coal | 0.4 | 0.2 |
  | biomass | 0.4 | 0.2 |

  - Sources: VGB PowerTech usual values and Wärtsilä's aeroderivative data.
  - The 10-minute response window follows the ERCOT ECRS rule.
  - **All of these are executor assumptions pending your approval.**
- **Weight dominance** (asserted in the tests):
  - one MW of λ is worth 1;
  - serving it for 216 h at 200 USD/MWh costs ≤ 0.43 in the objective;
  - one MWh of existing shed costs 1,000, so shed is never traded for λ.
- **λ = 0 certificate:** B0 is the same physics with λ = 0 inside the same LP. If B0 has zero shed, the existing load plus the 3 GW reserve is feasible on its own.
- **Acceptance:** zero existing shed in both blocks. Otherwise the result is `BASELINE_PRESSURE_INFEASIBLE`, and it is never attributed to AIDC.
- **Claim:** "load deliverable on the network while the system aggregate reserve condition holds". This is **not** deliverable reserve, **not** N-1 and **not** a reliability certificate. Reserve deployment is not checked against the network.

## 3. The two LPs

| | LP-R (`LP_R_H_RESOURCE`) | LP-N (`LP_N_H_NETWORK`) |
|---|---|---|
| Lines | Same 162 lines and reactances (KVL kept, one connected component); s_nom = 1e6 MVA, s_max_pu = 1, so no transfer limit can bind and no bus is isolated | v1.6 s_nom × s_max_pu (0.7) |
| Everything else | Identical: same variables / constraints / bounds; asserted equal n_vars and n_cons | Identical |
| Size (dry on L2) | 373,249 variables, 940,764 constraints, 0 integers | Same |
| Acceptance | `status ok`, `termination optimal`, zero existing shed | Same, plus 0 ≤ H_network ≤ H_resource + 1e-3 MW |

- **Order:** LP-R first; LP-N only after an optimal LP-R. Zero retries.
- **Expected time:** each LP is about 1/4 of the v1.6 LP2 size (1.62 M variables / 4.54 M constraints, 257 s on 20 threads), so the estimate is roughly 1–10 min each and under 10 GB RAM. **This is an estimate, not a measurement.**
- **Not done:** summing per-bus maxima, re-siting the weights, or using PRM-based allocation.

## 4. POI book (`H_POI`, no LP)

- `poi_ledger()` reports, per bus and year 2026–2031:
  - pre-approved E0 equipment;
  - all E0 rows, at max(COD, procedural 2028) for rows that are not pre-approved;
  - the POI upgrade (2,000 MW, earliest COD max(2026 + 3 y, 2028) = 2029);
  - the conditional PCLR capacity, which is never firm.
- λ_POI = min over w_b > 0 of cap_b / w_b. This is valid only when the POI rights are independent fixed caps and the network is unchanged.
- **A0 preview:**
  - λ_POI is **0 in 2026–2028 for every book**: 11 of the 16 buses (9 when counting all E0 rows from 2028) have no qualified POI equipment.
  - From 2029, with the upgrade: 11,446.6 MW facility, binding at p630 4.
  - A zero comes from POI qualification and procedure. It does not mean zero physical resource.
