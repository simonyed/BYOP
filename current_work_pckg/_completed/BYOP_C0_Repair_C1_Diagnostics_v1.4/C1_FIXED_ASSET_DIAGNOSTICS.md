# C1_FIXED_ASSET_DIAGNOSTICS: fixed-asset operating diagnostic of the 2025 fleet in the existing model (prompt v1.4 + continuation v1.4.1)

- Date: 2026-10-22 (New York time)
- Branch: `mainline-v13-stageA`
  - v1.4 start: `53aa883c`
  - this continuation's start (review base): `03536646`
  - **code commit `7c3f35999461f12522acdc817a5b630935f407bb`**
  - report commit: the commit containing this file, which cites the code SHA above
- **New solves in this continuation: 0.** The solve log `C1_SOLVE_LOG.csv` is byte-identical before and after re-collection.
- Solve history: 4 distinct cases, 4 logged retries, 8 solver calls in total. The remaining v1.4 budget was not used.
- This is a **fixed-asset diagnostic of the existing model's static year-end 2025 fleet**. It is **not** a historical replay of 2025, and it does not certify firm rights, POI eligibility, N-1 security or probabilistic resource adequacy. **It does not mean the historical baseline is fully calibrated.**

## 1. What was done: 4 valid cases and 8 solver calls

| Case | Network | Time | Final termination | Calls |
|---|---|---|---|---|
| C1_NETWORK_BASE × ANNUAL_3H | `baseline_2025_tamu_raw_uncalibrated.nc`: interface-rule capacity, **without** the 2025 uplift | 2,920 × 3 h, weight 3 | optimal | 1st sub-optimal (barrier, no crossover) → retry with crossover |
| C1_NETWORK_CALIBRATED × ANNUAL_3H | `baseline_2025_tamu_prepared.nc`: 18 lines +4,993.9 MVA **and** x, r on those lines scaled by the capacity ratio | same | optimal | 1st sub-optimal → retry |
| C1_NETWORK_BASE × PEAK_WINDOW_1H | same as BASE | 72 h (24 h buffer + 48 h evaluated) | optimal | 1st optimal; re-solved because the SOC boundary was re-taken from the optimal CALIBRATED annual run |
| C1_NETWORK_CALIBRATED × PEAK_WINDOW_1H | same as CALIBRATED | same | optimal | same |

- The superseded attempts are kept in `*__attempt1/` and `C1_SUPERSEDED_ATTEMPTS.csv`. They are not used in the final comparison.
- The sub-optimal and optimal CALIBRATED annual results give almost the same shed: 72,905.12 vs 72,905.11 MWh.

Settings common to both networks:
- the same 2025 fleet: extendable components and units with build year > 2025 removed;
- the same load and renewable time series;
- the same storage rule and the same VOLL of 35,685 USD/MWh;
- the `lv_limit` global constraint removed;
- no linopy model contains any `*_nom` build variable (asserted);
- no `AC_s0cal` links.

## 2. Acceptance fixes (v1.4.1 A)

- **Unified labels.** `c1_collect.py` previously built `met` first and only then normalized `kind`, so `C1_METRICS.csv` kept `annual`/`window` while the tests filtered for `ANNUAL_3H`/`PEAK_WINDOW_1H` and got empty sets. Labels are now normalized when each case's file is read. The manifest, metrics, events, line, line-comparison, fuel and QA tables all use one vocabulary, and the per-case folder name is asserted to match.
- **Exact optimal check.** `is_optimal(status, termination)` requires `status == 'ok'` and `termination == 'optimal'` exactly. Previously, `str.contains('optimal')` let `suboptimal` through.
- **Layered acceptance** (`validate()`, a pure function):

  | Layer | Content |
  |---|---|
  | `solver_termination_pass` | termination check |
  | `data_integrity_pass` | the manifest and metrics keys equal exactly the 4 expected keys (no missing, duplicate or extra entries); the fuel and line-comparison tables are non-empty and cover every key/kind; shed events agree with the metric (a case may have no events only if its metric is 0); the binding-line count agrees with the metric |
  | `physical_interpretation_limits` | a list of interpretation limits, kept separate from the pass/fail fields |

- **Tests**: `test_c1_fixed_asset.py` passes **12/12** on L2. It includes counterexamples that must all fail validation: `suboptimal`, a missing case, an empty fuel table, and a fabricated event.
- **Affected regressions on L2**:

  | Test | Result |
  |---|---|
  | C0 repair | 10/10 |
  | C0 v1.3 | 13/13 |
  | legacy geography | 50/50 |
  | dynamic geography | 32/32 |

  Logs: `workflow/results/BYOP/C1_FIXED_ASSET_DIAG/_l2_run/*_v141.log`.
- Current QA: `solver_termination_pass = true`, `data_integrity_pass = true`, `problems = []`.

## 3. Results

| Metric | BASE annual | CALIBRATED annual | BASE peak window | CALIBRATED peak window |
|---|---:|---:|---:|---:|
| Shed (MWh, evaluation period) | **10,264,061** | **72,905** | 58,618 | 17.3 |
| Max shed (MW) | 2,720 | 798 | 1,923 | 4.8 |
| Hours with shed | 8,760 | 1,047 | 48 | 6 |
| Buses with shed | 10 | 13 | 9 | 2 |
| Longest continuous gap (h) | 8,760 (p620 3) | 60 | 48 | 3 |
| Lines with binding hours | 44 | 43 | 34 | 28 |
| Curtailed wind / solar (GWh) | 22,344 / 10,024 | 14,281 / 6,216 | 147 / 57 | 73 / 27 |
| Max power-balance residual (MW) | ≤ 3.1e-10 (all cases) | | | |

Where and when the CALIBRATED annual shed occurs (`explain/C1_SHED_BY_BUS_MONTH.csv`):
- **By bus**: p620 2 (22,290 MWh), p620 7 (21,062), p620 6 (10,444), p620 1 (10,425), p630 2 (4,070), p610 1 (3,182), others < 600. About 88 % is in the far-west p620 group.
- **By month**: September 27,710 MWh; August 13,259; July 13,045; November–December about 10,500; January–February about 5,500.
- **Largest events**, with source labels:
  - p620 2 from 09/14/2025 HE 08:00, 57 h, 5,415 MWh, peak 207 MW;
  - p620 6 from 09/14 HE 05:00, 60 h, 2,337 MWh;
  - **p630 2 (Red Oak)**: two 6 h events, on 02/19 HE 10:00 (2,065 MWh, 461 MW) and 07/31 HE 14:00 (2,005 MWh, 638 MW).
- BASE has structural shortfall all year at p620 3 and other far-west buses, i.e. the 2025 fleet cannot serve load there without the uplift.
- **Peak window**:
  - BASE sheds 58.6 GWh in 48 h across 9 far-west buses;
  - CALIBRATED only 17 MWh: p620 7 at 08/18 HE 05:00 (5.9 MWh) and p670 8 at 08/18 HE 15:00 (11.4 MWh).

## 4. The 72.9 GWh vs the original 102.2 MWh (from existing outputs; not isolated)

Evidence: `explain/C1_CALIBRATION_VS_C1_SETUP.csv` and `C1_UPLIFT_LINE_CHECK.csv`, produced by `byop/post/c1_explain.py`, which reads saved outputs only.

**1. Confirmed input and code differences.** These are two different experiments.

| Item | Original calibration (`build_2025_baseline_tamu.calibrate_2025`) | C1 CALIBRATED |
|---|---|---|
| Lines | Reads `raw_uncalibrated.nc`; lines `s_nom_extendable`, `s_nom_min = s_nom`; **x and r held at their raw values while capacity is a variable** | Reads `prepared.nc`; on the 18 lines `s_nom` = raw + uplift **and** x, r divided by `s_nom_cal / s_nom_raw` (ratio 1.06–5.64; `main()` loops over `TAMU_2025_CALIBRATION_LP` and writes `s_nom, x/ratio, r/ratio`) |
| What is written back | The optimum `s_nom_opt − s_nom` on every line | Only uplifts > 0.5 MVA (`cal[cal.added_MVA > 0.5]`) |
| Objective | Operating cost + 1e6 USD/MWh × shed + 2e6 USD/MW × line uplift: capacity is bought wherever it is cheaper than shedding | Operating cost + 35,685 × shed; lines fixed |

The following are **the same** in both: fleet rule, removal of global constraints, storage (all 43 units are batteries and were already cyclic in the source network), 2,920 × 3 h snapshots with weight 3, and the MWh accounting (Σ p × weight).

The solver is not the cause: the sub-optimal and optimal C1 attempts give the same shed.

**2. Mechanism supported by outputs but not isolated.**
- In the CALIBRATED annual run, **12 of the 18 uplifted lines are still binding**: TL12 8,514 h, TL69 5,730 h, TL40 4,302 h, TL26 4,233 h, TL43 3,630 h, TL63 3,387 h, TL36 2,244 h.
- 19 of the 39 lines connected to shed buses are binding.
- The calibration LP sized these uplifts with the raw x. In the saved network their x is lower, so under DC power flow these lines take more flow than they did in the LP that sized them. That could saturate them again and push the bottleneck elsewhere.
- **This is consistent with the hypothesis that impedance scaling causes the extra shed, but it is not proven.** The two C1 networks differ in both capacity and impedance on the uplifted lines, so the effects cannot be separated.

**3. Hypotheses that still need an independent comparison.**
- Impedance scaling explains most of the 72.9 GWh.
- The 0.5 MVA threshold, or the difference in shed price (1e6 vs 35,685 USD/MWh), has a material effect. Both prices are far above every generator cost, so this is expected to be small.

**Minimal comparison design** (not run this round; needs approval):

| Run | Setup | Purpose | Solves |
|---|---|---|---|
| C1-X1 | `prepared.nc` capacity + **raw x, r** (no scaling), same as C1 otherwise | Isolates the impedance effect | 1 annual 3 h LP |
| C1-X2 (optional) | Re-run the original calibration LP exactly | Reproduces 102.2 MWh and confirms the base is consistent | 1 LP |

- Variables to save: per-line flows `p0`, bus prices, shed time series.
- If X1 sheds close to 102 MWh, the impedance hypothesis is confirmed. If not, look at the threshold or the objective next.

## 5. Simultaneous storage charging and discharging

**How it is computed.** `metrics()` takes, for each unit and each step, `min(p_dispatch, p_store)` where both are > 1e-3 MW, multiplies by the step weight and sums over units and steps. Unit and weight are correct.

| Case | Overlap | Steps with overlap |
|---|---:|---:|
| BASE annual | 9,043 GWh | 2,910 / 2,920 |
| CALIBRATED annual | 4,784 GWh | 2,860 / 2,920 |
| BASE window | 49.2 GWh | – |
| CALIBRATED window | 19.4 GWh | – |

Evidence from the inputs (`explain/C1_STORAGE_CHECK.csv`):
- All 43 storage units are batteries.
- Round-trip loss = 1 − η_store × η_dispatch = **15.36 %**; standing loss 0; storage marginal cost 0.
- **In the fixed 2025 fleet, input marginal costs are 0 USD/MWh for wind, solar and hydro, and none is negative.** The −7.79 seen earlier was the mean over extendable candidate units, which C1 removes. So the claim that "negative wind prices cause the anomaly" does not hold at the input level.
- Curtailment is also free (the generator only has an upper limit p_max_pu × p_nom, no minimum output). In hours with surplus energy, curtailing and losing energy by cycling storage cost exactly the same (0). This is **a multiple-optimum / degeneracy mechanism**: within the energy-balance constraint, the LP may "waste" surplus through storage losses. That matches the very large curtailment volumes (BASE 22.3 TWh wind).
- **Unproven**: there is no evidence that the overlap affects shed or prices.

Missing outputs (only aggregate quantities and SOC per unit were saved):
- per-unit `p_store` / `p_dispatch` time series;
- bus marginal prices and duals;
- per-unit curtailment.

So it cannot be shown which units, buses or hours contribute most, or whether solved prices are zero or negative in the overlap hours.

**Cyclic SOC.**
- The annual model applies the state-transition equation with SOC(t0−1) = SOC(T).
- The SOC of the first step is an end-of-step value; it is not required to equal the last step's SOC.
- The windows fix initial and final SOC from the end values of the CALIBRATED annual result at the 3 h steps that bound the window. The same values are used for both networks.

**Minimal check** (not run): fix the operating objective of the original optimum within tolerance (e.g. ≤ optimum × (1 + 1e-7)), then add a second-stage continuous LP that minimizes Σ(p_store + p_dispatch). If shed and line metrics are unchanged and the overlap disappears, the overlap is degeneracy. No MILP and no cost change are needed.

## 6. Generation by fuel (reference only, not fitted)

`C1_GENERATION_BY_FUEL.csv`, annual, GWh.

| Category | BASE | CALIBRATED | Official 2025 Fuel Mix |
|---|---:|---:|---:|
| Gas-CC | 170,959 | 172,422 | 161,819 |
| Gas (other) | 18,346 | 12,268 | 38,796 |
| Coal | 87,932 | 89,973 | 63,040 |
| Nuclear | 43,621 | 43,617 | 41,912 |
| Wind | 105,171 | 113,234 | 114,921 |
| Solar | 53,219 | 57,026 | 67,814 |
| Hydro | 1,019 | 1,019 | 550 |
| Biomass | 9 | 13 | 363 |

The scopes differ, so the gaps are not adjusted:
- The official figures are settlement data for the real 2025 system: units that came online during the year, outages, Other / WSL, and actual fuel prices.
- The model is a 3 h economic dispatch of the static year-end fleet with model costs. There is no unit commitment, no outage and no in-year commissioning, and hydro uses p_max_pu = 1 with no inflow series.

Directionally:
- coal is about 26.9 TWh above and other gas about 26.5 TWh below the official figures, consistent with coal's low marginal cost (23.1 USD/MWh) and the absence of outages and minimum-output constraints;
- solar is 10.8 TWh lower, which fits the late-2025 solar commissioning and the OPER-SYN status found in C0, but this was not verified.

## 7. Time labels and the limits of the 1 h evidence

- **Event timestamps** use the model coordinate (2030), which is kept. `explain/C1_SHED_EVENTS_LABELLED.csv` additionally gives each event's 2025 Native Load source row number and HE label, mapped by source row order. No conversion to UTC was done, and the DST and 24:00 labels are preserved.
- **The peak window** is "hourly load + wind and solar held at their 3 h values" (start row 5,475, peak 08/18/2025 HE 18:00, 24 h buffer + 48 h evaluated). It is **not** a full 1 h stress test.
- **The max-net-load window** is `MISSING_INPUT`: no hourly wind and solar data are time-aligned with the model's profiles. The PyPSA-USA hourly profiles do not reproduce the model's 3 h profiles at any shift (max |diff| 0.47 p.u.).

## 8. Data gaps and next steps

Gaps:
- time-aligned 1 h wind and solar;
- 2025 in-service, outage and retirement dates per unit (needed for an in-year commissioning replay);
- hydro inflow series;
- the solution variables listed in §5;
- the per-line flows needed for §4.

Next steps, by priority. **None of them has been executed**, and no historical asset values were changed.

1. **C1-X1 (1 LP)**: isolate the effect of impedance scaling on the 72.9 GWh. If it is confirmed, decide whether the calibrated network should keep raw x (with capacity added as parallel circuits whose impedance was not part of the calibration) or whether the uplift should be re-calibrated with scaled x.
2. **Two-stage storage LP (1 LP)**: confirm the degeneracy explanation.
3. **C0 asset items for the researcher's ruling**: the 567.5 MW reclassification candidates, the 1,638 MW status conflicts, Kiamichi and Tenaska Gateway availability, and the ERCOT↔EIA ID crosswalk.
4. A max-net-load window only after time-aligned 1 h wind and solar data become available.

## 9. Output files (`workflow/results/BYOP/C1_FIXED_ASSET_DIAG/`; copies in this folder)

| Group | Files |
|---|---|
| Collected tables | `C1_CASE_MANIFEST.csv`, `C1_METRICS.csv`, `C1_SHEDDING_EVENTS.csv`, `C1_BINDING_LINES.csv`, `C1_LINE_COMPARISON.csv`, `C1_GENERATION_BY_FUEL.csv` |
| QA, log and figure | `C1_QA.json`, `C1_SOLVE_LOG.csv`, `C1_SUPERSEDED_ATTEMPTS.csv`, `C1_DRY_CHECK.json`, `C1_MAIN_RESULTS.png` |
| Read-only analysis (`explain/`) | `C1_CALIBRATION_VS_C1_SETUP.csv`, `C1_UPLIFT_LINE_CHECK.csv`, `C1_SHED_BY_BUS_MONTH.csv`, `C1_SHED_EVENTS_LABELLED.csv`, `C1_SHED_BUS_NEIGHBOURHOOD.csv`, `C1_STORAGE_CHECK.csv`, `C1_EXPLAIN_SUMMARY.json` |
| Per-case folders | `metrics.json`, `shedding_events.csv`, `lines.csv`, `generation_by_carrier.csv`, `storage_soc.csv.gz` |
| Config and code | `config/config.byop_c1_fixed_asset_diag.yaml`, `byop/run/c1_fixed_asset_diagnostics.py`, `byop/post/c1_collect.py`, `byop/post/c1_explain.py`, `byop/tests/test_c1_fixed_asset.py` |

## Return

```text
START_SHA: 03536646721c59c255ac284a614af503c155cd53 (v1.4 start 53aa883c)
CODE_SHA: 7c3f35999461f12522acdc817a5b630935f407bb
REPORT_SHA: the commit containing this file (parent = CODE_SHA or its report-only successors)
COLLECTOR_LABEL_FIX: kind normalised at load (annual/window -> ANNUAL_3H/PEAK_WINDOW_1H) for manifest, metrics, events, lines, comparison, fuel, QA; folder-name assert
EXACT_OPTIMAL_AND_NONEMPTY_TESTS: is_optimal exact; validate() exact 4-key sets, non-empty fuel / line comparison, events and binding counts consistent with metrics; counterexamples suboptimal / missing case / empty fuel / fake event fail
C1_TESTS_AND_LOG_PATHS: test_c1_fixed_asset 12/12; c0_repair 10/10; c0_anchor 13/13; mainline 50/50; dynamic 32/32 (L2) - workflow/results/BYOP/C1_FIXED_ASSET_DIAG/_l2_run/*_v141.log
NEW_SOLVER_CALLS_THIS_CONTINUATION: 0
EXISTING_SOLVER_HISTORY: 4 distinct cases; 4 retries; 8 calls total
72_9_GWH_VS_102_MWH_CONFIRMED_DIFFERENCES: calibration LP used raw x / r with extendable s_nom and bought uplift at 2e6 USD/MW vs shed 1e6; the saved network scales x, r on the 18 lines by the capacity ratio (1.06-5.64) and drops uplifts <= 0.5 MVA; C1 fixes all lines, VOLL 35,685. Fleet, global constraints, storage cyclic, snapshots and MWh accounting identical; solver status not the cause
CAUSES_STILL_UNPROVEN: impedance scaling as the main cause (12/18 uplift lines bind again in C1; supporting, not isolated); threshold / objective differences (expected small)
STORAGE_FINDINGS_AND_MISSING_OUTPUTS: overlap metric per unit per step, weighted, correct; 43 batteries, 15.36 % round-trip loss, 0 standing loss; no negative input marginal cost in the fixed fleet (RE = 0, curtailment free) -> degenerate energy-sink optimum likely, unproven; missing: per-unit p_store / p_dispatch series, bus prices / duals, per-unit curtailment
TIME_LABELS_AND_1H_LIMITATIONS: events keep the 2030 model coordinate + 2025 source row / HE label (no UTC claim; DST / 24:00 kept); peak window = hourly load + 3 h-held RE, not a full 1 h test; max-net-load window MISSING_INPUT
DELIVERABLES_AND_README_UPDATED: yes (current_work_pckg C1_* + this report; README status)
HISTORICAL_OR_FUTURE_NUMERIC_INPUTS_CHANGED: NO
FORMAL_RUN_GATES_CHANGED: NO
RESEARCHER_EVIDENCE_REQUESTS: ERCOT UNIT CODE <-> EIA ID crosswalk; rulings on 567.5 MW candidates, 1,638 MW status conflicts, Kiamichi / Tenaska Gateway availability; time-aligned 1 h wind / solar; unit in-service / outage dates
MINIMUM_NEXT_DIAGNOSTIC_PROPOSAL: C1-X1 prepared s_nom with raw x / r (1 annual LP) [+ optional exact re-run of the calibration LP, 1 LP]; two-stage throughput-minimising storage LP (1 LP); save line flows, prices, per-unit storage series
NEXT_STEP: STOP_FOR_RESEARCHER_REVIEW
```
