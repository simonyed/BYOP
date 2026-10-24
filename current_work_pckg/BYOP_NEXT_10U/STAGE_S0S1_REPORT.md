# NEXT-10U stage report: S0 / S1_EARLIEST (model version `engineering_cost_v1`)

| Item | Value |
|---|---|
| Status | **PASS**: technical acceptance for both stages + S0 scientific gate |
| Config | `workflow/config/config.byop_next10u_s0s1.yaml`, approved_git_sha `34a27ee6`, approved_by `sw2434@cornell.edu` (researcher chat authorization 2026-10-24) |
| Baseline | ADOPTED v1.7L lossy 2025 (`f9aa87ae…`), unchanged |
| Run (L2, THREADS=12) | 2026-10-24 02:20 → 06:55 EDT; out_dir `workflow/results/BYOP/next10u_engineering_cost_v1/S0S1` |
| Manifest | `NEXT10U_S0S1_PRE_RUN_MANIFEST.json` (SHA `b1c329cc…`, recorded in `A2_SOLVE_LOG.csv`) |
| Optimizer calls | **3 of 3** planned (S0_COST, S1_SPEED_HIERARCHY, S1_COST). 0 retries. Program total 3 / 40. |

## Ledgers

| Call | Started (UTC) | Seconds | Termination | Vars / cons |
|---|---|---|---|---|
| S0#1 / S0_COST | 06:21:36 | 2,339 | optimal | 2.66 M / 7.11 M |
| S1_EARLIEST#1 / S1_SPEED_HIERARCHY (12 Gurobi hierarchy objectives) | 07:03:25 | 6,781 | optimal | 2.71 M / 7.30 M |
| S1_EARLIEST#1 / S1_COST | 08:56:30 | 6,799 | optimal | 2.71 M / 7.30 M |

## S0 (No New AIDC)

All three S0 checks pass: technical acceptance, the scientific gate (fixed before the solve) and the Far West pocket.

| Year | EENS (MWh) | EENS / native load (≤ 1e-5) | Max shed / peak (≤ 1e-3) |
|---|---|---|---|
| 2026 | 44.2 | 8.9e-8 | 9.0e-5 |
| 2027 | 84.6 | 1.7e-7 | 1.7e-4 |
| 2028 | 144.1 | 2.8e-7 | 3.0e-4 |
| 2029 | 133.1 | 2.6e-7 | 3.1e-4 |
| 2030 | 0.0004 | 8.5e-13 | 1.2e-11 |
| 2031 | 0.0004 | 8.6e-13 | 1.3e-11 |

- **Total EENS:** 406 MWh. The residual sits at `p600 1` (2026–2029) and `p620 1` (2028–2029), in 2 sampled snapshots per year.
- **Far West pocket (`p610 4`, `p620 6`, `p620 7`):** ≈ 0. The v1.6 S0 had 54.2 GWh there, so the NEXT-07 loss-basis diagnosis is confirmed on the formal baseline.
- **Public expansion in S0 by 2031:** AC_exp 36.1 GW, onwind 24.6 GW, solar 10.1 GW, CCGT 0.4 GW.
- **Real resource cost (PV):** 49.886 B USD.

## S1_EARLIEST (Grid-Only, earliest physically feasible service)

- **Acceptance:** all 18 checks are true.
- **No-harm:** max excess 0.0010 MW (limit 0.002); existing-customer shed is 405.07 MWh, ≤ S0.
- **Balance residual:** 4.3e-4 MW.
- **Reserve slack:** ≥ 0.
- **Speed levels:** all six year levels of the lexicographic speed stage hold in the cost stage.

| Year | Requested IT (MW) | Served IT (MW) | Served share |
|---|---|---|---|
| 2026 | 105 | 31 | 29 % |
| 2027 | 808 | 331 | 41 % |
| 2028 | 1,597 | 457 | 29 % |
| 2029 | 2,366 | 457 | 19 % |
| 2030 | 3,018 | 2,428 | 80 % |
| 2031 | 3,532 | 3,074 | 87 % |

### How the engineering POI model shapes grid-only service

1. **2026–2029: only known equipment serves load.**
   - Helios 200 MW (2026.5) + 391 MW (2027.5); p630 6; p630 9; p650 0.
   - No new POI equipment committed in 2026 can be energized before 2029.16 (NEMA 165-week lead), so firm credit starts in 2030 at the earliest.
   - Grid-only service is therefore flat at 457 MW in 2028–2029.
2. **2030: new equipment arrives.** The model commits 2,883.6 MW of new POI equipment at 15 sites (all of it committed in 2026 / 2027), and service jumps to 2,428 MW.
3. **Remaining delay in 2030–2031 comes from the disclosure caps.**
   - The ENG-vis caps bind in 2026 and 2027 at 12 sites; their duals are about 2.1 M USD/MW.
   - Equipment committed in 2028 or later reaches COD after 2031, beyond the horizon.
   - This applies the package's research assumption (announcement = max(2026, request year − 3)). It is not an observed utility decision.
4. **Abilene (`p610 2`).** Delay is 54 / 308 / 603 / 796 MW in 2026–2029.
   - The approved 955.6 MW right is modelled with RIGHTED equipment committed from 2026, so COD is 2029.16.
   - If the real equipment was ordered earlier, the real delay is smaller; see `RETURN/14_METHOD_LIMITATIONS.md` §2.

**Delay over the horizon:** 4,647.6 MW-IT-year of 11,426 requested; 6,778.4 served.

### S1 − S0 (grid-only AIDC cost to the system)

| Book item | S1 − S0 (PV, USD) |
|---|---|
| Public resource capex (generation, storage, AC_exp, POI) | +927.2 M |
|   of which POI equipment (in-horizon annuities) | +43.0 M |
| System operating | +82.3 M |
| **Real resource cost** | **+1,009.5 M** |
| Social delay loss (V = 2.8 M USD per MW-IT-yr) | +12,308 M |

The public expansion difference by 2031 is +1.9 GW solar, +1.8 GW onwind, +1.1 GW CCGT and +5.6 MW 4 h BESS. AC_exp is −0.8 GW in 2031, after +0.7 GW in 2030 (the expansion is re-routed).

## Accounting note

Capital costs enter as annuities for the model years within the horizon (2026–2031); the same rule applies in every scenario. The 2,883.6 MW of new POI equipment (160 USD/kW research proxy, about 461 M USD overnight) therefore shows only 43 M USD of in-horizon resource cost. The cost books report both the in-horizon PV and the overnight / CIAC amounts.

## Flags kept

- **`SCIENTIFIC_USE = BLOCKED: no_load_shed`** in `MAINLINE_GATE_CHECKS.csv`. This is the legacy B0 rule: any existing-customer shed blocks it.
  - It is reported, not overridden.
  - The NEXT-10U S0 scientific gate (thresholds fixed before the solve) is the reliability standard for this package. It passes.
- **`S0_RELIABILITY_REVIEW_REQUIRED=ON`** (a method flag): 406 MWh in total, 22.8 MW at the worst bus snapshot.

## Reference SHAs (pinned in `config.byop_next10u_a3.yaml`)

| File | SHA-256 |
|---|---|
| S0_RESULT.json | `8bc50378509337de90d9110813d869f0211cb14e60c4af9a0f461ad1747b63f2` |
| S1_EARLIEST_RESULT.json | `44270331a07f5737578698ccbf49ea50a631af2e1eea9f8e8cdf641bc915bef4` |
| S0_NO_HARM_REFERENCE.csv | `b9290ec3cd5f71014c25b0c5f9d7e04245449e99cda43ac248bdb269a6e43626` |
