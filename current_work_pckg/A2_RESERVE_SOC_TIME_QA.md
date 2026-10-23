# A2_RESERVE_SOC_TIME_QA (NEXT-02 A2-FIX-03)

**A2_SOC_RESERVE_QA: PASS (static)**

Evidence:
- structural checks `QA-SOC` / `QA-RES` in S0, S1_EARLIEST and S3;
- unit tests in `test_next02_a2_static.py`;
- 0 solver calls.

Status label: research screening approximation. This is not a validation of every transition inside an hour.

## 1. Finding 1: SOC time base was wrong (fixed on the post-v1.6 path only)

- `rearch_mech.ml_base_build` gave **every** weighting column, `stores` included, the sampled-week weight. In the A2 configuration (26-week sampling plus B7 stress days) that weight is about 77 h per base snapshot.
- PyPSA advances the SOC by `stores` hours × power. So in the multi-period mainline a battery's state of charge moved as if each 3 h snapshot lasted about 77 h. A 4 h battery could not sustain even one full-power snapshot.
- This was not a "3 h dispatch" for storage, and it understated grid storage (energy and reserve) in every earlier mainline build.
- **Fix:** with `POST_V16['stores_elapsed_h']` (on the post-v1.6 path only), `stores` = the elapsed 3 h. The objective and generator weightings keep the sample weight, so annual energy and cost sums are unchanged.
  - Structural check: stores weighting = 3.0 h everywhere; generator weights sum to 52,560 h = 6 × 8,760.
- Legacy (v1.3–v1.6) runs are unchanged; their results should be read with this caveat.
- **This changes model behaviour, so you need to confirm it under D4.**

## 2. Finding 2: reserve energy was checked at the end of the snapshot only

The NEXT-01 row `τ·r/η_d ≤ SOC(t)` uses the **end-of-snapshot** SOC. When storage charges during the snapshot, the start-of-interval SOC is lower, so the row overstated reserve energy at the start of the interval.

**Added:** `PV16M-res_su_energy_start`: `τ·r/η_d ≤ SOC_start(t)`, with

`(1−l)^w · SOC_prev = SOC(t) − w·η_s·p_store(t) + w·p_dispatch(t)/η_d − w·inflow(t) + w·spill(t)` (w = stores weighting)

- This is PyPSA's own storage balance solved for the decayed start SOC: an affine expression of the **same dispatch variables**.
  - It needs no shadow storage state and no assumption about the previous snapshot or cyclic rule.
  - Inflow is a constant and is subtracted exactly.
  - The spill term (≥ 0) is left out, which only tightens the bound.
  - The decayed start SOC is ≤ SOC_prev, so the row is conservative.
- Dispatch is constant inside a snapshot, so the SOC path between the two endpoints is monotone. The start and end rows together bound the energy throughout the interval.
- Built for 693 grid storage units (0 with inflow) in S0, S1_EARLIEST and S3. The variables in the row are the SOC, `p_store`, `p_dispatch` and `PV16M-res_su` (structural check).
- **Unit tests:**
  - row coefficients: SOC −1, p_store +w·η_s, p_dispatch −w/η_d, reserve +τ/η_d;
  - a hand-made SOC path that satisfies the balance reproduces SOC(t−1) exactly from the expression.

## 3. Thermal reserve consistency (unchanged rows, verified present)

For eligible grid thermal units (existing plus public candidates; 239 in S0, 112 extendable), on the same online-capacity variable c:

| Row | Constraint |
|---|---|
| `PV16M-online_max_p` | p ≤ c |
| `PV16M-online_cap_*` | c ≤ p_nom × availability × activity |
| `PV16M-online_min` | p ≥ p_min·c |
| `PV16M-res_thermal_head` | r ≤ c − p |
| `PV16M-res_ramp` | r ≤ ρ·c (ρ = min(1 − p_min, ramp × 10 min)) |

- DC-bus BYOP units and `load_shed` are never reserve (`QA-RES`).
- Storage: `PV16M-res_su_power_*` gives r ≤ p_nom − p_dispatch + p_store.
- The requirement is 3,000 MW in every snapshot of every period (`PV16M-reserve_req`).

## 4. Remaining approximation (stated, not hidden)

- The 3 h snapshot holds one dispatch. Each of its three hours carries the same 1 h reserve requirement, so intra-snapshot ramps and 1 h transitions are not represented.
- LP online capacity is a relaxation (no binaries, no minimum up/down times).
- The reserve is a system-aggregate adequacy proxy. It is not a deliverable ancillary-service product, and not N-1 or LOLE.
- A later 1 h verification on selected stress windows (A1-style) stays on the task list. It does not enlarge this round.
