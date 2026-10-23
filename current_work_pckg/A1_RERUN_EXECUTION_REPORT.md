# A1_RERUN_EXECUTION_REPORT (NEXT-05 v2 H1), 2026-10-23 00:04–00:26 EDT

**G2 = `A1_FIXED_NETWORK_EXCEPTION`.** LP-R PASS: H_resource = **2,587.77 MW facility**. LP-N is physically INFEASIBLE with the frozen 2025 line limits. H_network is NOT_AVAILABLE (never 0).

## Call accounting (A1 total: 3 real optimizer calls)

| Call | Ledger | Code | Result |
|---|---|---|---|
| Historical `LP_R_H_RESOURCE#1` (NEXT-04) | `POST_V16_A1_HEADROOM/HEADROOM_SOLVE_LOG.csv` (SHA `05bd03c2…`, unchanged) | `802c9d94` | solver ok / optimal, **output_failed, pass=False** (reader defect). Not a result. |
| rerun1 `LP_R_H_RESOURCE#1` | `POST_V16_A1_HEADROOM/rerun1/HEADROOM_SOLVE_LOG.csv` | `07c881a4` (approval commit `e4bfbe7f`) | 04:04:26Z → 04:06:00Z, 93 s, THREADS = 10: **DONE / ok / optimal / pass=True** |
| rerun1 `LP_N_H_NETWORK#1` | same | same | 04:06:21Z → 04:25:37Z, 1,155 s: **DONE / warning / infeasible / `baseline_pressure_infeasible_network_side`, pass=False** |

Retries: 0. The rerun1 budget (1 + 1) is fully used.

## LP-R acceptance (all PASS)

| Check | Value |
|---|---|
| status / termination / integers | ok / optimal / 0 |
| λ | **2,587.772185 MW facility** (finite, below the 200,000 MW upper bound). IT ≈ 2,253.37 MW. Identical to the first attempt's unaccepted objective. |
| Existing shed | B0 0.0 MWh; BL 0.0 MWh |
| 3 GW reserve | Minimum slack −9e-13 MW (met; binding) |
| Nodal balance residual | 1.18e-11 MW |
| Saved before the writers | `LP_R_H_RESOURCE_SOLVED_NETWORK.nc` (L2), `LP_R_H_RESOURCE_SOLUTION/` (PV16 variables) |

Per-bus split: `HEADROOM_BY_BUS_LP_R_H_RESOURCE.csv`. Examples: p610 2 595.6 MW; p630 4 452.1; p650 0 305.8; p630 3 264.4 MW facility.

The reserve is binding and is met mostly by storage in the stress hours. That is a property of the stress windows, not a defect.

## LP-N: network-side infeasibility (physical, attributed by construction)

- **The two LPs differ only in line limits.** LP-N and LP-R have identical variables, rows, data, objective, windows, reserve and hard-zero shed; LP-R lifts every line limit, LP-N keeps the v1.6 `s_nom × s_max_pu`.
- **LP-R is feasible and optimal, so the infeasibility comes from the frozen line limits.** Because λ ≥ 0 includes λ = 0 (the B0 block), no dispatch serves even the **existing** 2025 load with zero shed plus the 3 GW reserve in the pre-registered stress windows.
- **Consistent with earlier evidence:** the v1.6 annual 3 h calibration also needed residual existing-customer shed (111.8 MWh/yr).
- **Indicative corridor diagnostic** (solver-free; `A1_LPN_INFEASIBILITY_DIAGNOSTIC*.{json,csv}` in `rerun1/`):
  - LP-R's copperplate witness dispatch exceeds the frozen ratings in every stress window.
  - The tightest corridors are in West Texas: TL129 p650 4–p650 6 (693 MW, up to 2.73×), TL120 p650 1–2 (483 MW, 2.65×), TL117 p650 0–4 (1,414 MW, 1.72×), TL104 p640 1–4 (908 MW, 1.84×) and TL133 p650 5–p670 4 (3,244 MW, 1.36×).
  - The LP-R dispatch is non-unique, so this ranks pressure points; it is not an IIS. An IIS would need another optimizer call, which is outside the budget.
- **No retry.** No relaxation of the zero-shed rule or the 3 GW reserve, and no free line added.

## Meaning

- **H_resource = 2,587.77 MW facility** is the joint resource-side deliverable capacity of the given 16-bus AIDC distribution, under the stress / reserve conditions, on the synthetic network with a copperplate network.
- **H_network: NOT_AVAILABLE.** The frozen 2025 network cannot carry the existing stress-window load with a 3 GW reserve and zero shed. A1's fixed-network screen is therefore not a valid headroom measure on this network.
- This is a screening result, not an ERCOT POI allocation. The max-λ dispatch is not a price signal.
- **Package §4.5:** H2 (A2 merge) proceeds and S0 is tested independently. S0 is a multi-year LP with paid public expansion, a different feasible set. A1 is **not** reported as PASS.
