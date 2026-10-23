# W1_S0_RELIABILITY_ROOT_CAUSE: what the S0 shed of 54,205.8 MWh is (NEXT-06 W1, 0 optimizer calls)

**Sources:** original S0 run (code `cdfdea06`, read only); v1.6 frozen baseline `a623fb6d…`; v1.6 LP2 outputs; S0 network rebuilt with the build step only (no model, solver refused).

**Tables:** `workflow/results/BYOP/next06_s0_diagnostic/W1_*`. Scripts: `workflow/byop/post/next06_w1_*.py`.

## 1. Reconciliation (W1.1): PASS

| Item | Value |
|---|---|
| Frozen shed file | `S0_shed_by_snapshot_frozen.csv.gz`, 816 snapshots × 68 units (63 native + 5 inherited ramp) |
| Weights | Two classes per year: sampled-week snapshots **77.571 h**, B7 stress-day snapshots **3 h**. **Sum = 8,760 h in every year**; no overlap or double counting. |
| Reconstructed total | **54,205.777 MWh** (reported 54,205.7791; difference 0.002 from clipping ~1e-10 solver noise) |
| 2026 | **51,049.277 MWh** native only = reported 51,049.2775. Inherited-ramp shed is only **1.34 MWh** over all years. |
| By year (weighted) | 2026 51,049.9 · 2027 2,065.5 · 2028 1,022.9 · 2029 67.5 · 2030–31 0 |
| **2026 raw 3 h shed** | **5,990.8 MWh**, weighted to 51,049.9 (×8.5 overall) |

## 2. Where the 2026 number comes from

**(a) The Far West pocket (94 % of all S0 shed)**
- **Size:** p620 6 **31,199.9 MWh** and p620 7 **16,250.0 MWh** (weighted), plus 1,028.5 MWh at p620 3.
- **When:** every one of these snapshots lies in the two **sampled weeks** (Jan 1–7 and Jul 2–8 of the weather year), nightly 00:00–09:00 model time, with peaks of 72.2 MW (p620 6) and 36.0 MW (p620 7).
  - Each such 3 h snapshot carries **77.57 h**, so raw 2,315.7 + 733.7 MWh become 47,450 MWh.
  - The top 10 snapshots carry 39.6 % of the all-years total.
- **Network position:** the pocket {p610 4, p620 6, p620 7} is supplied only by two lines, TL35 (p620 0 → p610 4, 461.9 MW) and TL43 (p620 4 → p620 6, 119.0 MW).
  - TL44 (68.6 MW) and TL36 (137.5 MW) are internal to the pocket.
  - There is no generation inside the pocket at night (p610 4: 561 MW solar; p620 7: 108 MW solar) and no storage before the 2028 committed battery at p610 4.
- **No new capacity can be built there in 2026:** with the procurement leads, no public candidate in the pocket reaches COD in 2026. From 2027 S0 builds local BESS (90 MW 8 h at p620 6, 45 MW 4 h at p620 7, 11 MW at p610 4), and the sampled-week shed disappears.

**(b) Short stress-day spikes (≈ 2.5 GWh in 2026; 3 h weight, so raw = weighted)**
- p630 2 (Red Oak) 844.6 MWh with a **281.5 MW peak**; p600 1 700.8; p620 1 570.0; p630 13 159.6.
- They recur at a smaller scale in 2027–2029 (p630 2: 251.8 MW peak in 2028).
- These are B7 stress events, not extrapolated.

## 3. The decisive comparison: same network, same hours, no shed

The closest reference is the **v1.6 LP2 fixed-asset check**: the frozen `.nc`, the full 2025 year at 3 h, no per-snapshot reserve, 111.79 MWh shed (`W1_BASELINE_LINEAGE_AND_COMPARABILITY.csv`). I rebuilt the S0 network for 2026 without solving (`W1_S0_VS_V16_LP2_INPUTS_FAR_WEST.csv`) and compared it with LP2 at the same 42 shed hours:

- **Loads:** pocket load is identical except for the documented AEO2023 TX background factor **1.009327** for 2026 (LOAD-GROWTH-03): about +5 MW in the pocket.
- **Supply and network:** pocket generation, storage, line ratings and **reactances are identical**. The higher x/r on 18 lines relative to the pre-v1.6 file is the researcher-approved **X1** rule (raw impedance, thermal uplift only; the C1-X1 report and v1.6 closeout). It is **not** an error and **not** a change between LP2 and S0.
- **LP2 served the pocket with no shed at these hours,** with TL43, TL36 and TL15 at their ratings (LP2 max |flow| 119.0 / 137.5 / 306.5 MW). The pocket has no slack, but the 2025 dispatch was feasible.
- **The static cut capacity (580.9 MW) exceeds the pocket load (499–551 MW) at every shed hour.** The S0 shed is therefore not forced by the two feeding lines alone; it comes from **meshed (KVL) loop limits**.
- **The LMP pattern in S0 confirms a network-wide night-time limit.** At 2030-01-06 00:00 (period 2026):
  - p620 0 and p620 4 are at about 39 USD/MWh;
  - p600 2 6,490, p620 2 14,887, p610 4 16,555, p620 3 33,840, and p620 6 at VOLL.

  At 12:00 the same day every West price is normal (29–160 USD/MWh). So the limit is a night-time, multi-line deliverability limit across the West mesh, **which LP2 did not have**.

## 4. Root-cause decision (`W1_ROOT_CAUSE_DECISION_TABLE.csv`)

| Class | Verdict | Evidence |
|---|---|---|
| **D** data / topology | **Rejected.** Pocket inputs are identical to LP2; X1 x/r is approved; the load factor is documented. | MODEL_DIRECT |
| **T** time weighting | **Confirmed amplifier, not an error.** The weights follow the method (sum 8,760 h), but 94 % of the total is two sampled weeks' nightly shed ×25.86. Representativeness is **unproven**: on the same network the full-year 2025 dispatch had no such nightly deficits. | MODEL_DIRECT |
| **C** committed / COD | **Minor.** DWB Stage 2 is modelled as a uniform 0.51 derate all of 2026 (in reality ~0 in Jan, 1,000 MW in Jul) but is not on the pocket cut. No reachable candidate in 2026 is a true lead-time effect (COD audit 1,818 / 1,818). | MODEL_DIRECT / SOURCED |
| **P** physical tightness | **Confirmed pre-condition.** No slack in the pocket and no pocket resources until 2027. Not sufficient on its own. | MODEL_DIRECT |
| **M** method / formulation | **Most likely driver.** S0 adds what LP2 lacks: the 3 GW system reserve (not locational) with thermal online-capacity / min-load coupling, segment-neutral SOC, the 2026 fleet and the DWB link. These change night-time dispatch so less power can be delivered into the pocket (≈ 476–500 MW vs up to ≈ 572 MW in LP2 at the same hours). | DERIVED |
| **U** | **Unresolved:** which M component dominates. S0 persisted no line flows, SOC or unit dispatch, so this cannot be separated without a solve. | UNRESOLVED |

**W1_ROOT_CAUSE: METHOD (most likely) × TIME amplification, on a PHYSICALLY tight pocket. Component UNRESOLVED.** No data, topology or COD error was found that would justify editing S0 inputs.

## 5. Why 111.8 MWh is not the target

- **Different feasible sets:**
  - The 102.2 MWh (LP1) and 111.8 MWh (LP2) figures are 2025 full-year runs without the 3 GW per-snapshot reserve.
  - LP1 even had line uplift as a decision variable.
  - The 72.9 GWh (v1.4 C1) used scaled-down x/r on 18 lines: `NOT_COMPARABLE`.
- **Sampling:** S0 2026 is a 2026 run with the post-v1.6 rules and two sampled weeks.
- **Matching LP2 is not a success criterion.** The open question is whether the nightly shortage under the post-v1.6 rules is real across the 2026 year (T) and which rule causes it (M).

## 6. Consequences

- **S0 reliability verdict now: `BASELINE_RELIABILITY_UNRESOLVED`.** The shed is not an input error, but neither its annual magnitude (T) nor its cause (M) is established. The scientific-use flag stays.
- **S1 inherits the same 2026 pocket shed unchanged** (no-harm holds), so S1 − S0 differences are not driven by it. The S1 − S0 cost and expansion comparison is therefore usable **as a differential** with this caveat. Absolute S0 reliability is not.
- **W2 needs one diagnostic LP to separate T** (true 2026 annual EENS under the A2 rules) **and to persist flows, SOC and dispatch for M.** See `W2_S0_CALIBRATION_DECISION.md`.
