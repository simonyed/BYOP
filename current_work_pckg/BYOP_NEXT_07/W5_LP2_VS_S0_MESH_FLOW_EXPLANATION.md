# W5: why the Far West pocket sheds in S0 2026 but not in the v1.6 LP2 2025 check (read-only, 0 optimizer calls)

**Answer: transmission losses.**
- The mainline S0 is solved **with linearised transmission losses** (`transmission_losses: 2`, inherited from the PyPSA-USA default config layer through `scripts/solve_network.py`).
- The v1.6 calibration LPs, including LP2 (`byop/run/baseline_v16_calibration.py`: `n.optimize.create_model()`), were solved **without losses**.

On the two 230 kV lines that feed the pocket, the losses use up about 80 MW of deliverable capacity. That is more than the whole shortfall (sub-pocket shed: 24 MW mean, 98 MW peak).

Ratings, reactances, topology and pocket loads are the same in both runs (apart from the documented +0.93 % growth). **This is not a data or network error.** It is a **modelling-basis mismatch**: the v1.6 baseline (including its 18-line thermal uplift) was calibrated lossless, and S0 runs it with losses.

Inputs:
- the LP2 saved solution (`LP2_line_flow_p0`, `LP2_lines`, `LP2_shed_by_bus`);
- the NEXT-07 probe's persisted S0 solution. Its 2026 Far West shed is identical per snapshot to the formal S0.
- the 42 S0 shed hours (2030 weather calendar in both runs).

Scripts:
- `byop/post/next07_w5_lp2_vs_s0_flows.py`
- inline checks recorded in `W5_*.csv`

## Evidence

**1. The shortfall is in the sub-pocket {p620 6, p620 7}.** p610 4 is fully served.

| Item | Value |
|---|---|
| Sub-pocket feeders | TL43 (p620 4 → p620 6, rating 118.98 MW) and TL36 (p610 4 → p620 7, 137.49 MW); static cut 256.5 MW |
| Sub-pocket load | 210–224 MW at the shed hours (LP2 2025: 217.7 MW mean; S0 2026: 219.7 MW) |
| Power to the sub-pocket | Reaches it either over TL43 or through p610 4 (TL35 → TL36) |

The static cut is never exceeded, in either year. **The limit is deliverability, not cut capacity.**

**2. The line limits in the S0 model include losses.** In the solver-free S0 build, each line's rating row is `s + loss ≤ s_nom × s_max_pu` (same ratings as LP2), with a two-segment tangent approximation of the quadratic loss. Bus balances take p0 = s + loss/2.

| At the S0 shed hours | TL35 (into p610 4) | TL43 (into p620 6) |
|---|---:|---:|
| Rating | 461.90 MW | 118.98 MW |
| r / x | 15.6 / 93.8 Ω | 15.4 / 88.2 Ω |
| Hours at their loss-limited maximum | **33 / 42** | **42 / 42** |
| Loss on the line when saturated | **49.5 MW (12 %)** (quadratic r·S²/V² check: 44 MW) | 3.9 MW (check: 4.0 MW) |
| Delivered to the pocket side | **387.6 MW** | **113.2 MW** |
| LP2 (lossless) at the same hours | up to 461.9 delivered (mean 402.1; 0 hours at rating) | 118.98 (at rating 29 / 42 hours) |

- Usable capacity of the pocket feeders lost to losses: TL35 74.3 MW + TL43 5.8 MW ≈ **80 MW**.
- The pocket's (p610 4 + sub-pocket) night load is 500–558 MW. Lossless, the two feeders could deliver up to about 581 MW and serve it, as LP2 does. With losses they deliver about 500 MW.
- **The shortfall falls on the sub-pocket**, because its own feeders are TL43 (saturated) and TL36. TL36 runs below rating, but its supply comes from p610 4, which receives only what saturated TL35 delivers.

**3. The same effect runs through the whole West mesh.** At the 42 hours:
- **In S0**, 38 West lines saturate in at least one hour (7.7 saturated lines per hour), each 0.5–17 % below its rating. The largest reductions are on long high-r/x lines: TL35 0.84, TL13 0.83, TL42 0.85, TL12 0.90 (`W5_SATURATION_COMPARISON.csv`).
- **In LP2**, 27 lines are at rating in at least one hour (6.8 per hour).
- In S0, less power arrives at p620 0 (TL21 412 vs 549 MW). The pocket-loop angle θ(p620 0) − θ(p620 4) is 24 mrad more negative (−812 vs −788 mrad).

**4. What does not explain it:**

| Factor | Why it is ruled out |
|---|---|
| Line ratings or reactances | Identical in LP2 and S0; no West line has a different limit (`lines_with_different_limits_in_west: []`) |
| The 3 GW reserve | W2 probe: −0.0009 % |
| DWB Stage 2 | Moves ~244 MW net p620 4 → p620 0 at these hours, which helps the pocket. Its fwd/rev links also circulate flow at the same time (a degenerate zero-cost loop; recorded, harmless to the balance). |
| Load growth | +0.93 % (+2 MW in the sub-pocket) is small next to the 80 MW loss effect |

## What it means

| Question | Finding |
|---|---|
| Is the S0 2026 pocket shortage a calibration artefact? | **Largely yes, with respect to the v1.6 calibration.** The v1.6 thermal uplift and the LP1/LP2 residual-shed checks (102 / 112 MWh) were all done lossless. Running the same network with losses removes about 12 % of TL35's usable capacity, and similar amounts on other long West lines. This produces deficits the calibration never saw. |
| Are losses wrong? | No. Losses are physical, and the 230 kV r values give losses of the right size (TL35 ~12 % at 412 MW). The issue is **consistency**: calibration and scenario must share one loss basis. |
| Is it a code bug? | Not in the sense of a wrong formula. It is an unregistered setting inherited from `config.default.yaml`. It has a large effect (54 GWh weighted S0 shed) and was never part of the A2 / NEXT decision registers. |

## Erratum to `W2_RESERVE_CAUSAL_VERDICT.md`

W2 described TL35 as "carrying its KVL share, 387.63 MW, below its own rating" and TL43 as "pinned at its effective limit 117.05 MW (98.4 % of rating)". **Correct reading:**
- Both lines are at their **loss-limited** maximum: |s| + loss = rating.
- TL35's 387.63 MW is what it delivers after a 49.5 MW loss.
- TL43's 117.05 MW is p0 at the sending end; 113.2 MW is delivered.

The W2 class (`RESERVE_REQUIREMENT_NOT_PRIMARY`) is unaffected.

## Proposed next steps (researcher decisions; nothing run)

1. **Choose the loss basis for the whole study** (S0–S3 and the calibration):
   - **(a)** keep losses: re-check, and if needed recalibrate, the v1.6 baseline under losses (LP1/LP2 with `transmission_losses: 2`); or
   - **(b)** run the mainline lossless, consistent with the v1.6 calibration (`transmission_losses: 0` in the mainline config), and register losses as a limitation or sensitivity.

   Either is a model change. The formal S0/S1 would then need a paired rerun (2 attempts / 3 calls, separately approved).
2. **Optional single confirming diagnostic** before that decision: the same S0, 2026–2031, 26 weeks, formal 3 GW reserve, `transmission_losses: 0`. One `S0_COST` call, 0 retries, built and gated like the W2 probe.
   - **Expected:** the 2026 Far West shed largely disappears.
   - **If it does not:** the remaining mesh-injection difference (TL21 / p620 0 supply) is the next suspect.
3. **S0 verdict proposal → `METHOD_BUG_CONFIRMED_REPAIR_REQUIRED`** (loss-basis mismatch between calibration and scenarios). This is pending your confirmation; the A3-gated status file is unchanged.

**Files:**
- `workflow/results/BYOP/next07_s0_reserve_probe/`:
  - `W5_LP2_VS_S0_SUMMARY.json`
  - `W5_SUB_POCKET_HOURLY.csv`
  - `W5_WEST_LINE_BINDING_AT_S0_SHED_HOURS.csv`
  - `W5_SATURATION_COMPARISON.csv`
  - `W5_POCKET_FEEDER_LOSSES.csv`
  - `W5_INJECTION_DIFF.csv`
  - `_w5_limits/LINE_LIMITS_IN_S0_MODEL.json` (the loss and rating rows read from a solver-free S0 build)
