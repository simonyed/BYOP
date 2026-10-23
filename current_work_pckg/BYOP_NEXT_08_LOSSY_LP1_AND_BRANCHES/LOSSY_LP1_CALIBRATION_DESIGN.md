# LOSSY_LP1_CALIBRATION_DESIGN (NEXT-08 A): 2025 lossy LP1 calibration → candidate baseline → LP2 check

**Status: design, code and zero-solver tests only. No optimizer call is authorised or made in this stage.**

## 1. Goal and starting point

S0–S3 use `transmission_losses: 2` (researcher decision, `W6_LOSS_BASIS_DECISION_RECORD.md`). The v1.6 baseline was calibrated lossless, and on the lossy basis it fails the v1.6 reliability criteria for 2025 (EENS ≤ 4,882 MWh, largest gap ≤ 83.7 MW):

| | EENS | Largest gap |
|---|---:|---:|
| v1.6 lossless LP2 | 111.8 MWh | pass |
| Lossy LP2, raw r | 153,266 MWh | 745.9 MW |
| Lossy LP2, r of 18 lines scaled | 13,690 MWh | 438.4 MW |

**Goal:** within a fixed, small number of LPs, produce a **candidate 2025 lossy baseline** that passes the unchanged v1.6 criteria. It is a **new file**; the frozen v1.6 NetCDFs are never written. The paired S0/S1 rerun can then start from it, after separate approval.

## 2. Capacity–resistance treatment: the two options

| | Option 1: X1 as is (raw r, x) | **Option 2: parallel-circuit r proxy, fixed per LP (recommended)** |
|---|---|---|
| Rule | LP1 with losses; every line keeps its pre-calibration r and x whatever capacity it gets | r = r_raw × s_raw / s_ref, **fixed inside each LP**; x = raw (X1) |
| Physical reading | Added capacity carries the resistance of the original small line: a 127 MVA line pushed to 412 MW loses 12 % (TL35) | Added capacity behaves like additional parallel circuits: the equivalent resistance falls in proportion. This is the builder's own convention for every other capacity change (`build_2025_baseline_tamu.py:324–326`). |
| Effect on uplift | Losses on uplifted lines are overstated, so LP1 must buy even more capacity to cover artificial losses. This is the over-expansion the package forbids. | Losses consistent with the represented capacity, so the minimum uplift reflects deliverability, not a resistance artefact |
| x (flow split) | raw | raw. **Assumption:** keeping x means the uplifted corridor does **not** attract more flow, as real parallel circuits would (lower x). This is the researcher-approved X1 decision; it makes the flow split conservative for the uplifted corridors. Recorded, not changed. |
| LP character | Linear | Linear. **There is never an r × s_nom product in one LP**; r is a parameter set from the previous capacity. |
| Calls | 1 LP1 | 1–2 LP1 (fixed-point iteration, see §4) |
| Code | Same runner, `r_proxy` off | `loss_basis_lp1.py`: `r_proxy` / `convergence` / `candidate_network` (about 30 lines of logic) |

**Recommendation: Option 2.**
- **Physics:** it is the only option where the loss model and the capacity mean the same thing.
- **Evidence:** the completed TPIT work behind 87 % of the v1.6 uplift is mostly second circuits, double circuits and rebuilds (§5), i.e. parallel capacity.
- **Cost:** it adds one LP at most.

Option 1 is not recommended. It would buy capacity to offset losses that come from mixing a small line's resistance with a large line's rating.

**Calibration proxy vs real parameters.** The resulting r and s_nom are **equivalent-impedance calibration proxies of a 64-cluster synthetic network**, not physical parameters of any ERCOT circuit. They may not be cited as engineering line data.

## 3. New LP1 vs v1.6 LP1 (`build_2025_baseline_tamu.calibrate_2025`)

| Item | v1.6 LP1 | NEXT-08 lossy LP1 |
|---|---|---|
| Network | `baseline_2025_tamu_raw_uncalibrated.nc` (SHA `eb659f9b…`) | **same file** (SHA-pinned in the config; never written) |
| Load | 2025 ERCOT native load, 3 h, 2,920 snapshots | same |
| Generation / storage | 2025 fleet only (extendable and post-2025 units removed), global constraints dropped | **identical statements** (verified: the lossless, uncapped part of the new model equals the v1.6 model exactly) |
| Objective / prices | uplift 2e6 USD per MVA of s_nom, shed 1e6 USD/MWh; uplift is a calibration penalty, not an investment cost | **same** |
| Line variables | every line extendable, s_nom_min = raw, s_nom_max = ∞ | every line extendable, s_nom_min = raw, **s_nom_max = 2 × v1.6 capacity** (finite: required by PyPSA's loss formulation; tangents then sit exactly at the v1.6 rating; also the per-line expansion guard) |
| Losses | none | **`transmission_losses: 2`**: two tangents, `|s| + loss ≤ s_max_pu·s_nom`, half the loss at each end (same as S0–S3) |
| r | raw | parallel proxy r_raw·s_raw/s_ref (§2) |
| x | raw | raw |
| Solver options | v1.6 exact-optimal (Barrier, crossover on, BarConvTol 1e-8, NumericFocus 2) | same |
| Size | 1.62 M variables / 4.54 M constraints; 1,566 s (20 threads) | **2.09 M variables / 6.90 M constraints** (built, not solved); expected about 30–60 min |

**Scope of capacity changes.** As in v1.6, every line may be uplifted; the minimum-cost objective decides where. The design does not restrict the LP to the original 18 lines, because the W6 results show bottlenecks beyond them (p630 2 summer-midday spike; p620 2). Instead, pre-registered guards (§4) bound and flag any expansion.

## 4. Calls, iteration rule, guards and stop conditions (fixed before any solve)

1. **`LP1_LOSSY_IT1`**: r from the v1.6 capacities (s_ref = v1.6 prepared s_nom), i.e. exactly the W6 R_PARALLEL network as the starting point.
2. **Convergence after an LP1:** a line is converged if |r_used / r_implied(s_opt) − 1| ≤ 5 % **or** |s_opt − s_ref| ≤ 10 MVA. All lines must be converged.
3. **`LP1_LOSSY_IT2`** runs only if IT1 is optimal and **not** converged. It takes r from the IT1 solution. If IT2 is still not converged: **STOP**, no LP2, report.
4. **Expansion guards, on the converged LP1, before any LP2** (all must pass, else STOP):
   - **G1:** total uplift over raw ≤ 1.5 × the v1.6 total (≤ 7,727.8 MVA).
   - **G2:** no line at its cap (2 × v1.6 capacity).
   - **G3:** uplift on lines **not** uplifted in v1.6 ≤ 1,000 MVA in total; each such line above 50 MVA is listed for evidence review.
5. **Candidate:** written only after a converged, guard-passing, optimal LP1, as a **new** NetCDF `results/BYOP/next08_lossy_lp1/baseline_2025_tamu_lossy_candidate.nc`. It is the raw network with s_nom = s_opt and r = proxy; x and everything else unchanged.
6. **`LP2_LOSSY_CANDIDATE`:** the v1.6 C1 fixed-asset rules on the candidate, `transmission_losses: 2`, the **unchanged v1.6 acceptance**.
7. **Budget:** at most 3 calls (IT1, conditional IT2, LP2), 0 retries. Every gate rule is enforced in code (`loss_basis_lp1.check`) and tested.
8. **Any non-optimal solve, or an invalid capacity solution** (non-finite or below raw): ERROR row, outputs kept, no retry, no candidate.

**After a PASS (separate approvals):**
- your decision to adopt the candidate as the lossy 2025 baseline (new SHA; v1.6 kept);
- paired S0/S1 rerun on it (2 attempts / ≤ 3 calls);
- S0 verdict;
- A3 manifest rebuild;
- S2/S3.

**After a FAIL:** read-only analysis. No further capacity without new evidence and your decision.

## 5. Engineering evidence (A3; `A3_TRANSMISSION_EVIDENCE*.csv/.json`)

ERCOT TPIT 2026-07-13 workbook, mapped to TAMU-64 buses via the v1.6 county-to-bus shares:

| Class | v1.6-uplifted lines | Uplift MVA |
|---|---:|---:|
| **E2**: completed 2024–25 ≥ 138 kV line work at the line's end-bus areas | 14 (TL3, TL13, TL15, **TL35**, **TL36**, TL37, TL38, TL39, TL40, TL41, **TL43**, TL68, TL69, TL73) | **4,472.5 (87 %)** |
| **E0**: none, a **research calibration proxy** | 4 (TL12 250.0, TL26 47.4, TL42 225.9, TL63 156.1) | **679.4 (13 %)** |
| E1: exact bus-pair completed project | 0 (expected: synthetic inter-cluster lines aggregate many real circuits) | — |

**Examples of completed 2025 projects:**

| Line(s) | Projects |
|---|---|
| TL35 / TL36 (Far West pocket) | Ollin–LCRA Crane partial build / rebuild / conversion; Ollin 138 kV station; Hartring–Upland 138 kV double circuit |
| TL37 / TL38 | Riverton–Border–Quarry Field 138 kV second circuit; Salt Flat Road–Barr Ranch–Reiter second circuit; Grey Well Draw–Buffalo second circuit |

The committed DWB Stage 2 (in service mid-2026) and the PBRP 765 kV paths are 2026+ assets. They are already in S0–S3 as committed links and are **not** used as 2025 evidence.

**Reading:**
- The evidence supports that real capacity was added in these corridors through 2025.
- It does not fix the MVA.
- Lines rated E0, and any new line LP1 uplifts, are reported as research calibration proxies with their size and the uplift price (2e6 USD per MVA of s_nom, a calibration penalty, not a cost estimate).
