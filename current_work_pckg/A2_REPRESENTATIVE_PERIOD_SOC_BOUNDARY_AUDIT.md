# A2_REPRESENTATIVE_PERIOD_SOC_BOUNDARY_AUDIT (NEXT-03 A2-FIX-08)

**A2_SOC_SEGMENT_QA: PASS (static, 0 solver calls).**
- Code `81bd5743` on `work/a2-postv16-static`.
- Evidence:
  - `A2_SOC_SEGMENT_MAP.csv` (S0 and S1_EARLIEST, 30 segments each);
  - `A2_SOC_BOUNDARY_TESTS.json`;
  - structural run `results/BYOP/post_v16_a2_static/_structural_next03/` (75/75 checks, `QA-SOCSEG`).

## 1. What the retained snapshots are

Per investment period (6 periods, 2026–2031) the model keeps 136 snapshots (3 h each) in 5 contiguous segments. The calendar is the model weather year.

| Segment | Content | Snapshots | Gap before (h) | Weight (`generators` / `objective`) | `stores` |
|---|---|---:|---:|---:|---:|
| 1 | Sampled week 0 (Jan 1–7) | 56 | — | 77.57 h | 3 h |
| 2 | B7 stress day (Feb 19) | 8 | 1,011 | 3 h | 3 h |
| 3 | Sampled week 26 (Jul 2–8) | 56 | 3,171 | 77.57 h | 3 h |
| 4 | B7 stress day (Jul 31) | 8 | 531 | 3 h | 3 h |
| 5 | B7 stress day (Sep 15) | 8 | 1,083 | 3 h | 3 h |

The weights still sum to 8,760 h per period: 112 × 77.57 + 24 × 3.

## 2. Is the risk real? Yes, PyPSA links the segments

PyPSA's `StorageUnit-energy_balance` uses the previous **retained** snapshot as the SOC predecessor, whatever the real time gap.
- On the real S0, S1_EARLIEST and S3 models, the balance row at the first snapshot after each of the **24 within-period gaps** contains the SOC of the last snapshot before the gap: **24 / 24 linked**.
- Unit settings in the v1.6 base:
  - all 189 existing batteries are cyclic;
  - 126 are cyclic **per period**;
  - **63 (`battery`) are cyclic over the whole 2026–2031 horizon**, so their SOC also chains from one investment year into the next;
  - no hydro or other storage with inflow; standing loss 0.
  Public candidate and DC-bus BESS units follow their templates.
- Without a fix, a battery could charge in the January week and discharge on the July stress day, or carry energy from 2026 into 2027.
  - With NEXT-02's `stores` = 3 h, this is a 3 h-equivalent, nearly lossless transfer across weeks or months.
  - With the old ~77 h step it was distorted in another way.

## 3. Fix: segment energy neutrality (minimal, linear, no new variables)

`post_v16_mainline.add_segment_soc_neutrality` is called in `extra_rearch` when `POST_V16['soc_segments']` is set. For every StorageUnit u and every contiguous segment k:

    SOC_u(last snapshot of k)  ≥  SOC_u,prev(k)

- **The predecessor is read from PyPSA's own balance row:** `SOC_u,prev(k)` is the other SOC variable in the `energy_balance` row of k's first snapshot. If there is none (non-cyclic start), the initial-SOC constant is used. The code therefore does not re-implement PyPSA's per-period or horizon cyclic rules.
- **Why this makes every segment neutral:** around a cyclic chain, the segment increments are each ≥ 0 and sum to 0, so each is 0. **No net energy crosses a time gap or a period boundary.**
- **What is kept:** inside a segment, the 3 h dynamics stay exact. A multi-day contiguous stress event stays one segment; the SOC is not reset per snapshot.
- **Size:** rows = active units × segments. S0 / S1_EARLIEST: 11,305 rows. S3: 12,985 (DC-bus BESS added). Structural check: rows = expected; no binaries or integers.
- **Model size:**
  - S0: 2,660,074 variables (unchanged), 7,107,710 constraints;
  - S1_EARLIEST: 2,712,538 / 7,296,046;
  - S3: 2,978,054 / 7,824,023.
- **Relation to the NEXT-02 rows:**
  - The start/end reserve energy rows (`PV16M-res_su_energy[_start]`) still apply within each snapshot.
  - The S3 RE+BESS certificate rows (stress-day start ≤ 0.5·h·p_nom, end ≥ start) are consistent with segment neutrality.

## 4. Tests (no solver)

| Case | Result |
|---|---|
| Continuous 3 h → 1 segment; weeks apart → 2; inserted 2-day stress event stays 1 segment; never across periods | PASS |
| PyPSA links the SOC across a gap (balance row) and the new rows carry the true predecessor (per-period cyclic) | PASS |
| Horizon-cyclic unit: a period start's predecessor is the previous period's end; also neutral | PASS |
| **Counterexample:** a 4 h battery charges 400 MWh in segment 1 and discharges it on a low-resource day in segment 2. PyPSA's own balance is satisfied; the segment rows are violated. | PASS |
| Real models: 24/24 gaps linked by PyPSA; rows = expected; segments never span a gap or a period | PASS (S0, S1_EARLIEST, S3) |

## 5. Interpretation boundary (to be stated with any result)

Storage dispatch remains a **representative** approximation:
- Each segment is a self-contained, energy-neutral day or week, weighted to the year.
- Segment SOC paths are not an hourly annual storage trajectory.
- Seasonal or multi-week storage value cannot be represented. That matters little for 1–8 h batteries, and the ERCOT base has no hydro storage.

Annual energy and cost keep the sample weights. Reserve energy uses the same dispatch SOC at both snapshot ends.
