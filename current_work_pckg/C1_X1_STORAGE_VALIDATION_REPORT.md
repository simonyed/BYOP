# C1_X1_STORAGE_VALIDATION_REPORT: C1-X1 network comparison and storage-degeneracy check (work package v1.5)

- Date: 2026-10-22 (New York time)
- Branch: `mainline-v13-stageA`
  - Start SHA: `90192db8` (report) / `7c3f3599` (code).
  - Archive commit: `cf5df4f0` (moves v1.4 + v1.4.1 into `_completed/BYOP_C0_Repair_C1_Diagnostics_v1.4/`).
  - Runner commit: `0c23f85f` (code and config committed before solving; dry check passed).
  - **Code and results commit: `7d699edfda7ee03df2345b3dd1ba821d55151efd`**.
  - Report commit: the commit that contains this file.
- **Solves this round**: 2 effective LP stages, 0 retries, 2 actual solver calls.
  - Stage 1: 236.6 s.
  - Stage 2: 4,035.6 s (crossover and simplex clean-up on a highly degenerate objective).
  - Both terminated with `status == ok` and `termination == optimal` exactly.
- Unchanged:
  - formal run gates (both `NOT_APPROVED`);
  - historical assets, future AIDC, the inherited load, POI, gas, technology costs, ERM and VOLL;
  - the baseline `prepared.nc`, the raw network and the v1.4 C1 results (git diff since `cf5df4f0` is empty);
  - no S0–S3, B3 or capacity-expansion run.
- Interpretation boundary: this is a model comparison that varies only the impedance representation, plus a check of storage degeneracy. **It is not a reliability certification of the real ERCOT system and not a full replay of 2025.**

## 1. Stage 1: C1-X1, calibrated capacity with original impedance

### 1.1 Input differences (`C1_X1_LINE_INPUT_AUDIT.csv`)

- X1 starts from the v1.4 C1_NETWORK_CALIBRATED diagnostic network:
  - the same fleet, load, availability, storage (annual cyclic), 2,920 × 3 h snapshots with weight 3, costs, VOLL 35,685 USD/MWh, global-constraint handling and shed variables;
  - solver settings are the v1.4 settings that already gave optimal results (Method 2, Crossover 1, NumericFocus 2, BarHomogeneous 1).
- **The only change**: x and r on the 18 uplift lines are reset to the raw network values, **matched by line ID**.
- Asserted:
  - X1 s_nom equals CALIBRATED **exactly** on all 162 lines;
  - x and r change on exactly those 18 lines;
  - all other lines keep CALIBRATED x and r;
  - topology, length and s_max_pu are unchanged;
  - there is no `*_nom` build variable and no S0CAL link.

### 1.2 Results (`C1_X1_STAGE_COMPARISON.csv`)

| Metric | v1.4 CALIBRATED | **X1 stage 1** | Change |
|---|---:|---:|---:|
| Annual shed (MWh) | 72,905.1 | **112.58** | **−99.85 %** |
| Max shed (MW) | 797.8 | 27.2 | |
| Shed hours / buses | 1,047 h / 13 | 12 h / 5 | |
| Longest continuous gap | 60 h | 3 h | |
| Binding lines / total binding hours | 43 / 66,867 | 46 / 60,636 | |
| Economic cost F (USD) | 1.02863e10 | **7.47623e9 = F\*** | −2.81e9 (mostly shed cost: about 72,792 MWh × 35,685 = 2.60e9) |
| Wind / solar curtailment (GWh) | 14,281 / 6,216 | 10,254 / 5,068 | |

**X1 shed by bus and event** (`C1_X1_SHED_BY_BUS_MONTH.csv`, `C1_X1_SHED_EVENTS_LABELLED.csv`):

| Bus | MWh | Event |
|---|---:|---|
| p620 1 | 81.3 | 07/14/2025 HE 11:00, 3 h, peak 27.1 MW |
| p620 7 | 24.6 | 08/28 HE 11:00, 21.5 MWh; 07/31 HE 14:00, 3.2 MWh |
| p620 2 | 6.3 | 08/28 HE 11:00 |
| p620 5 | 0.3 | – |
| p630 2 | 0.1 | 07/31 HE 14:00 |

- **p630 2 (Red Oak)** falls from 4,070 MWh to 0.08 MWh.
- The far-west p620 group falls from about 64.2 GWh to 112.5 MWh.
- Events are reported in model coordinates (2030); `source_HE` gives the 2025 Native Load source row and HE label. This is not a UTC conversion, and DST / 24:00 labels are kept.

**How line flows redistribute** (`C1_X1_LINE_COMPARISON.csv`): 20 lines bind more and 28 bind less. The effect is not one-directional.

| Line | Uplift line? | Binding hours, v1.4 CAL → X1 |
|---|---|---|
| TL12 (p600 1–p620 2) | yes | 8,514 → 2,802 |
| TL69 | yes | 5,730 → 1,281 |
| TL63 (p630 12–p630 2) | yes | 3,387 → 255 |
| TL26 | yes | 4,233 → 1,158 |
| TL42 | yes | 759 → 21 |
| TL40 | yes | 4,302 → 4,218 (about unchanged) |
| **TL43** | yes | **3,630 → 4,470** |
| **TL3** | yes | **714 → 5,769** |
| **TL68** | yes | **0 → 2,538** |
| **TL15** | yes | **0 → 1,806** |
| TL84 | no | 1,635 → 2,646 |
| TL46 | no | 1,827 → 2,640 |

A lower impedance does not make a line carry more flow in every period, so this is reported only as the result of this run, not as a general rule.

### 1.3 What it shows

| Comparison | Conclusion |
|---|---|
| v1.4 CALIBRATED vs X1 | **Under the current fixed capacities, costs and operating limits, the x / r scaling applied when the network was saved has a substantial effect on shed (72.9 GWh → 112.6 MWh) and on the congestion pattern.** This confirms the hypothesis left open in v1.4.1, within this model comparison. |
| X1 (112.6 MWh) vs the original calibration residual (102.2 MWh) | Still mixed with differences in objective (the calibration could buy line capacity), shed price (1e6 vs 35,685 USD/MWh) and the dropped sub-0.5 MVA uplifts, so it **cannot be attributed to a single cause**. "Close to 102 MWh" is not used as a pass criterion, and the original calibration was **not** re-run. |

## 2. Stage 2: minimizing storage throughput on X1

### 2.1 Setup

- Stage 2 reuses the **in-memory** stage-1 linopy model (stage 1 is not re-solved). All physical constraints and capacities are kept.
- Two bounds are added:
  - economic cost: `F(x) ≤ F* + ε_F`, where F is the stage-1 objective expression;
  - total shed: `E* − ε_E ≤ E(x) ≤ E* + ε_E`, using the same weights and the same shed variables.
- Objective: `min Σ_t w_t Σ_s (p_store + p_dispatch)` over all 43 batteries, physical charge and discharge, no efficiency correction.
- No cost change, no binary variables.

| Quantity | Value |
|---|---|
| F\* | 7,476,225,965.01 USD (recomputed from the solution: 7,476,225,965.01; agrees) |
| ε_F | max(1, 1e-8·F\*) = 74.76 USD |
| ε_E | 0.001 MWh |
| E\* | 112.57849 MWh |
| **Stage-2 recomputed F** | 7,476,226,039.77 USD = F\* + 74.7637. This sits on the bound; it exceeds the nominal bound by 0.0015 USD (2e-13 relative), within the solver's feasibility tolerance. |
| **Stage-2 E** | 112.57849 MWh (differs from E\* by 1.3e-6 MWh, inside ε_E) |

### 2.2 Stages 1 and 2 compared

| Metric | Stage 1 | **Stage 2** | Change |
|---|---:|---:|---:|
| Simultaneous charge/discharge overlap (GWh) | 3,787.0 | **106.0** | **−97.2 %** |
| Steps with overlap | 2,658 | 530 | |
| Storage throughput (GWh) | 13,938.8 | 5,892.2 | −57.7 % |
| Charge / discharge (GWh) | 7,549 / 6,390 | 3,191 / 2,701 | |
| Conversion loss (GWh) | 1,159.6 | 490.2 | −669 |
| Wind / solar curtailment (GWh) | 10,254 / 5,068 | 10,640 / 5,350 | +387 / +282 |
| Thermal generation | – | – | Nearly unchanged: CCGT −656, coal −1,823, OCGT +1,120, gas_steam +383 MWh |
| Shed | 112.58 | 112.58 | Identical by bus and by event |
| Binding hours | 60,636 | 60,627 | Small changes, e.g. TL15 1,806 → 1,809, TL68 2,538 → 2,526 |
| Line flows | – | – | **Not identical**: the largest single-step change is 832 MW (TL55); TL130 663, TL49 629, TL99 579 MW |

**Judgment**:
- With the economic cost and total shed held within the stated tolerances, most of the simultaneous charge/discharge (97 %) disappears. This **supports the explanation that the original solution contains removable degenerate cycling**: wind/solar marginal cost is 0 and curtailment is free, so "losing" surplus energy through storage losses costs the same as curtailing it.
- When the overlap goes, curtailment rises by about the same amount as the reduction in conversion losses.
- Shed totals and their locations are unchanged.
- **Line flows and some saturation hours do change.** We do not claim that "all operating results are unaffected".

### 2.3 Remaining overlap (`C1_X1_STORAGE_BY_UNIT.csv`)

- 8 of the 43 units still have overlap > 1 MWh.
- **The battery at p630 14 accounts for 98.1 GWh, about 93 % of the remainder, and its overlap is unchanged between stage 1 and stage 2.**
  - Bus p630 14 has no generators.
  - It connects to the network only through TL23 and TL67.
  - The storage conversion losses there act as an extra local load.
- Candidate explanation: **under the DC power-flow / KVL constraints this local energy sink has value for keeping the economic cost at F\***, so it is not a removable degeneracy. **This is not proven** (the bus prices and the dual of the cost bound in stage 2 would need checking). It is not treated as an error, and no MILP was added.
- The other units are small, e.g. p640 5 at 4.3 GWh and p620 4 at 1.7 GWh.

## 3. Output completeness and price separation (`C1_X1_QA.json`)

Each stage has its own folder, `stage1_X1/` and `stage2_min_throughput/`. All 17 required files are present and non-empty:

| Category | Contents |
|---|---|
| Storage | `p_store`, `p_dispatch` and SOC per unit; efficiency, initial/final and bus mapping |
| Generation | output, available output and static parameters per unit |
| Lines | `p0` / `p1`, capacity / effective limit / x / r, saturation |
| Shed | per bus per period |
| Events | event table |
| Summaries | metrics, generation by carrier, objective |

Prices and duals:
- **Stage-1 economic prices** are in `economic_marginal_price.csv.gz`.
- **Stage-2 duals** are in `stage2_nodal_balance_duals_NOT_economic_prices.csv.gz`. They belong to the throughput objective and are not economic dispatch prices.

The four `lines_p0/p1` files are over 5 MB and stay on L2 under `workflow/results/BYOP/C1_X1_STORAGE_V15/stage*/`. Their SHA-256 is in `C1_X1_QA.json`; for example, stage-1 `lines_p0` is `409f0dad…`.

Checks:
- Max power-balance residual 0, and max storage state-equation residual 0 (checked against the state-transition equation with the cyclic SOC; first and last SOC are not required to be equal).
- Environment: pypsa 1.3.0, linopy 0.9.1, gurobipy 11.0.3, Python 3.11.17, host lambda-2. Config, script and authorization-source SHAs are recorded in each stage's `metrics.json`.

## 4. Tests (L2, no new solves)

| Test | Result |
|---|---|
| `test_c1_x1_storage_v15.py` (config / gates, runner structure including impedance restored by line ID / bounds / no MILP / duals separated, exact line audit, both stages optimal and within bounds, F recomputation matches, completeness and price separation, inputs unchanged) | **5/5** |
| `test_c1_fixed_asset.py` / `test_c0_repair_v14.py` / `test_c0_anchor.py` / `test_mainline_v13.py` / `test_dynamic_siting.py` | 12/12, 10/10, 13/13, 50/50, 32/32 |

Logs: `workflow/results/BYOP/C1_X1_STORAGE_V15/_l2_run/`. No test thresholds were changed.

## 5. C0 asset evidence requests (prepared in parallel; not used in this round's LPs)

`C0_PRIORITY_ASSET_EVIDENCE_REQUESTS.csv`, 32 rows. Each row lists both sides' IDs (CDR UNIT CODE and source row; ReEDS Unique ID and EIA plant ID), status, dates, capacity with its basis, the specific conflict and the evidence needed:

| Priority | Item |
|---|---|
| **HIGH** | Kiamichi (1,400 physical / −885 unavailable / 515 net vs model 1,224 summer) |
| **HIGH** | Tenaska Gateway (937 / −937 / 0 vs 826) |
| **HIGH** | 7 status conflicts (1,638 MW): Sequoia, Fagus SLF, Buzios, Big Star, La Casa, Gaia, Long Point |
| MEDIUM | 3 reclassification candidates (567.5 MW): Pyron, Danish Fields Storage, Myrtle Storage |
| ONGOING | ERCOT–EIA ID mapping for the 20 high-impact unmatched groups |

Until there is a ruling, every row keeps the existing model values. Kiamichi is **not** changed to 515 MW, and Gateway is **not** removed. Both stages use the same fleet.

## 6. Corrections to earlier reports

- **Storage degeneracy**: in v1.4.1 this was only a candidate explanation. It is now **largely supported** by this check (97 % of the overlap can be removed at the same cost and shed). The remaining 106 GWh, concentrated at p630 14, is a local energy sink whose cause is unproven.
- **Low model solar output**: the earlier link to "commissioning late in 2025" was **not verified** and should not be used as an explanation on its own.
- **Impedance**: v1.4.1 described this as "consistent with the hypothesis". Within this model comparison the effect is now confirmed by X1. Its effect on the whole network follows the comparison outputs: flows redistribute in both directions.

## 7. Recommended network representation (proposal only; not implemented)

1. **Thermal-limit uplift proxy at the original impedance (the X1 approach).**
   - The calibration LP and the final fixed network use the same x, so they agree with each other (in X1, shed is 112.6 MWh).
   - Note: keeping the raw x **does not mean that real parallel circuits were added**. It is a thermal-limit proxy that is consistent with the calibration LP. Before it is used for the formal common baseline, the researcher must accept this definition.
2. **Iterative calibration with capacity and impedance updated together.**
   - Outer loop:
     1. with x fixed, solve the minimum-uplift LP;
     2. update x and r by 1/(new s_nom / old s_nom);
     3. repeat the uplift LP with the new x.
   - Stopping rule: total uplift changes by < 1 % between iterations **and** the fixed-network shed changes by < 1 MWh, or at most 5 rounds.
   - Every round stays an LP, with no non-convex impedance–capacity coupling.
   - At the end, **re-check the final fixed network with the fixed-asset LP**, and report the iteration path and whether it converged.

**Suggested next stage**: once the network representation and the key asset rulings are settled, build a separate version of the common baseline and check it as a fixed network. Then restore S0/S1, followed by S2/S3. **This round's diagnostics are not a reliability certification of the real ERCOT system.**

## 8. Deliverables

In `current_work_pckg/`:
- this report;
- `C1_X1_LINE_INPUT_AUDIT.csv`, `C1_X1_STAGE_COMPARISON.csv`, `C1_X1_STORAGE_BY_UNIT.csv`, `C1_X1_SHED_BY_BUS_MONTH.csv`, `C1_X1_LINE_COMPARISON.csv`, `C1_X1_SHED_EVENTS_LABELLED.csv`;
- `C1_X1_QA.json`, `C1_X1_SOLVE_LOG.csv`;
- `C0_PRIORITY_ASSET_EVIDENCE_REQUESTS.csv`.

Code:
- `byop/run/c1_x1_storage_v15.py`, `config/config.byop_c1_x1_storage_v15.yaml`;
- `byop/post/c1_x1_collect.py`, `byop/post/c0_evidence_requests.py`;
- `byop/tests/test_c1_x1_storage_v15.py`.

## Return

```text
START_SHA: 90192db8111fea3168b422c4acae92f824d38f48 (code 7c3f3599)
CODE_SHA_AND_REPORT_SHA: code + results 7d699edfda7ee03df2345b3dd1ba821d55151efd (runner first committed in 0c23f85f before solving); report = the commit holding this file
NEW_DISTINCT_LP_STAGES: 2
ACTUAL_SOLVER_CALLS_AND_RETRIES: 2 calls, 0 retries (stage 1 236.6 s optimal; stage 2 4,035.6 s optimal)
X1_INPUT_DIFF_AND_CAPACITY_IDENTITY: x, r of exactly the 18 uplift lines set to raw values by line ID; s_nom identical to CALIBRATED on all 162 lines (asserted); all else identical
X1_SHED_VS_EXISTING_CALIBRATED: 112.58 MWh vs 72,905.1 MWh (-99.85 %); max 27.2 vs 797.8 MW; 12 vs 1,047 h; 5 vs 13 buses
X1_SPATIAL_AND_LINE_FLOW_CHANGES: p620 group 64.2 GWh -> 112.5 MWh, p630 2 4,070 -> 0.08 MWh; 20 lines bind more / 28 less (TL12 8,514->2,802, TL69 5,730->1,281, TL63 3,387->255, TL26 4,233->1,158; TL3 714->5,769, TL68 0->2,538, TL15 0->1,806, TL43 3,630->4,470)
PRIMARY_F_STAR_E_STAR_AND_TOLERANCES: F* 7,476,225,965.01 USD (recomputed equal), E* 112.57849 MWh; eps_F 74.76 USD, eps_E 0.001 MWh
SECONDARY_ORIGINAL_COST_AND_SHED_BOUND_CHECK: F = F* + 74.7637 USD (at bound, 0.0015 USD above nominal = solver feasibility tolerance); E = E* + 1.3e-6 MWh - both pass
STORAGE_OVERLAP_THROUGHPUT_AND_LOSSES_BEFORE_AFTER: overlap 3,787.0 -> 106.0 GWh (-97.2 %), steps 2,658 -> 530; throughput 13,938.8 -> 5,892.2 GWh; conversion loss 1,159.6 -> 490.2 GWh; curtailment +387 (wind) / +282 (solar) GWh; remainder 98.1 GWh at p630 14 (bus without generators: local sink, unproven)
SHEDDING_OR_CONGESTION_DISTRIBUTION_CHANGED: shed identical by bus and event; binding hours nearly identical (60,636 -> 60,627); individual line flows change up to 832 MW per step (TL55)
OUTPUT_COMPLETENESS_AND_DUAL_SEPARATION: 17/17 files per stage; stage-1 economic prices and stage-2 duals in separate, labelled files; lines_p0/p1 on L2 with SHA in QA
QA_TESTS_AND_FAILURES: v1.5 5/5; C1 12/12; C0 repair 10/10; C0 13/13; legacy 50/50; dynamic 32/32; no failures
C0_ASSET_EVIDENCE_REQUESTS: 32 rows (HIGH 9: Kiamichi, Gateway, 7 status conflicts 1,638 MW; MEDIUM 3: 567.5 MW candidates; ONGOING 20: ERCOT-EIA mapping); all keep existing model values
HISTORICAL_OR_FUTURE_NUMERIC_INPUTS_CHANGED: NO
FORMAL_RUN_GATES_CHANGED: NO
CAUSAL_FINDINGS_AND_UNRESOLVED_ITEMS: impedance scaling drives the v1.4 CALIBRATED shed in this model comparison (confirmed by X1); most storage overlap is removable degeneracy (supported); unresolved: X1 vs 102.2 MWh residual difference (objective / price / threshold mix), p630 14 local sink, solar gap vs official
NEXT_RECOMMENDATION: researcher decides the network representation (raw-x thermal-limit proxy vs iterative capacity-impedance calibration) and the HIGH asset rulings; then build a separate common baseline + fixed-network check; then S0/S1, S2/S3 - STOP_FOR_RESEARCHER_REVIEW
```
