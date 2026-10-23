# W5P_LOSSLESS_VERDICT (NEXT-07): the lossless S0 confirming probe

**Class (pre-registered): `LOSS_BASIS_CONFIRMED_MAIN_CAUSE`.** Solving the formal S0 without transmission losses removes the 2026 Far West nightly shed entirely: **47,297.9 → 0.0 MWh (−100 %)**. It also removes **all** other 2026 shed.

The probe is a diagnostic only (`DIAGNOSTIC_LOSSLESS_NOT_THE_FORMAL_LOSS_BASIS`). It is not a formal S0, not a reliability baseline, and does not choose the study's loss basis.

## Run record

| Item | Value |
|---|---|
| Authorisation | Researcher in chat, 2026-10-23. Config-only commit `9dce6b5d` on approved SHA `bf61d873b1e2e1d0df9befd70d3b41896df967d6`; approved_by `sw2434@cornell.edu`. Approval closed after use. |
| Pre-run recheck (L2) | Manifest 0 mismatches; normalised config SHA equal; gate approved with no reasons; no prior probe ledger; original A2 ledgers byte-identical |
| Call | 1 × `S0_COST`, 0 retries. 13:27–13:51 EDT. Barrier 116 iterations, 1,405 s; 16 threads. 2,527,882 variables / 6,446,750 constraints. |
| Status | ok / optimal |
| Acceptance | **PASS** on all ten checks. The formal 3,000 MW reserve is met in all 816 snapshots (mean held 3,940 MW at the former shed hours). |
| Outputs | `workflow/results/BYOP/next07_s0_lossless_probe/`: `solution/S0/` (14 files), `W5P_*`. No no-harm reference written. Seal: `W5P_SEAL.json`. |
| Untouched | Original `POST_V16_A2_S0S1` and the reserve-probe ledgers (SHA-checked) |

## 1. Existing-customer shed (2026–2031 weighted)

| | Formal S0 (losses 2) | Lossless probe | Δ |
|---|---:|---:|---:|
| 2026–2031 sum | 54,205.8 MWh | **646.8 MWh** | −98.8 % |
| 2026 (all) | 51,049.9 | 0.0 | −100 % |
| 2026 Far West nights (pre-registered) | 47,297.9 | 0.0 | −100 % |
| 2026 p630 2 / p620 3 stress-day spikes | 845.2 / 1,028.5 | 0 / 0 | −100 % |
| 2027–2031 | 3,155.9 | 646.8 | −79.5 % |

The remaining 646.8 MWh is entirely **B7 stress-day** shed in 2027–2029: p630 2 in 2028, 477.9 MWh; p600 1, 128.9 MWh; p620 1, 40.0 MWh. That is the size of the v1.6 lossless calibration checks (LP1 102 MWh, LP2 112 MWh).

## 2. Immediate dispatch effect (2026)

Neither run has a new public asset active in 2026 (0 MW in both). The 2026 change is therefore purely operational: the same fleet and the same lines, without loss terms.

| 2026, at the former pocket shed hours | Formal S0 | Lossless |
|---|---:|---:|
| Pocket import | 504.7 MW (TL35 delivering 387.6 after a 49.5 MW loss) | 519.0 MW, all load served |
| TL43 / TL35 max loading | 0.98 / 0.84 (loss-limited) | **1.00 / 0.95** |
| LMP p620 6 / p620 7 / p610 4 | $35,685 / $34,016 / $31,222 | $428 / $304 / $211 |
| LMP p620 0 / p620 4 | $397 / $381 | $48 / $34 |
| Mean LMP, all grid buses, 2026 | $868.6 | **$46.5** |

The network constraint still binds without losses: TL43 is at its rating. The difference is that the full line capacity is usable.

## 3. Investment feedback (2027–2031)

| Public new MW (all build years) | Formal S0 | Lossless | Δ |
|---|---:|---:|---:|
| AC expansion | 36,370.7 | 30,438.3 | **−5,932.3** |
| 4 h BESS | 642.5 | 0.0 | −642.5 |
| 8 h BESS | 180.2 | 12.2 | −168.0 |
| Onshore wind | 25,348.5 | 24,162.0 | −1,186.6 |
| Solar | 9,560.7 | 9,060.0 | −500.7 |
| CCGT | 191.6 | 802.8 | +611.2 |

**By build year:**
- 2027: −722 MW (Far West −308 MW)
- 2028: −989 MW (Far West −999 MW)
- 2029: −2,017 MW
- 2030: −5,944 MW
- 2031: +1,853 MW (Far West +1,500 MW)

The early Far West BESS and transmission that the formal S0 builds against the loss-limited pocket are **not** built.

| PV 2026–2031 | Δ (lossless − formal) |
|---|---:|
| Public capex | −$1,285.6 M (−17 %) |
| System operating | −$743.8 M |
| Existing-customer unserved loss | −$1,909.1 M (−98.9 %) |
| Physical spending proxy | −$2,029.4 M |
| Social welfare cost / LP objective | **−$3,938.5 M (−7.5 %)** |

## 4. Reading

1. **The S0 2026 reliability problem is a loss-basis artefact relative to the v1.6 calibration.**
   - The v1.6 network was calibrated (thermal uplift, LP1/LP2 residual shed) without losses.
   - The mainline runs it with `transmission_losses: 2` (inherited from `config.default.yaml`).
   - Without losses, the same S0 shows essentially the calibrated reliability.
2. **Losses are a first-order model setting, not a detail.** They change the 2026–2031 public build-out by about 10 GW and the social cost by about $3.9 B PV. **They therefore also affect every S1/S2/S3 comparison built on S0.**
3. **Lossless is not "correct" either.** Losses are physical; at these 230 kV resistances they are about 12 % on TL35 at 412 MW. The defensible fix is **one basis throughout**:
   - **(a) Keep losses:** re-check, and if needed recalibrate, the v1.6 baseline with losses on (LP1 uplift / LP2 check with `transmission_losses: 2`). Then rerun S0/S1 as a pair.
   - **(b) Lossless study:** set `transmission_losses: 0` in the mainline config for every scenario, consistent with the v1.6 calibration, and report losses as a limitation or sensitivity. Then rerun S0/S1 as a pair.
4. **S0 verdict proposal:** `METHOD_BUG_CONFIRMED_REPAIR_REQUIRED` (calibration and scenario loss-basis mismatch). The formal S0/S1 (`POST_V16_A2_S0S1`) keep their record but should not be used for reliability or for S1−S0 cost claims until the repaired pair exists. This needs your confirmation; the A3-gated status file is unchanged.

**Tables:**
- `W5P_LOSSLESS_CAUSAL_COMPARISON.csv` (63 rows)
- `W5P_LOSSLESS_CAUSAL_SUMMARY.json`
- `W5P_PUBLIC_INVESTMENT_BY_CARRIER_YEAR.csv`
- `workflow/results/BYOP/next07_s0_lossless_probe/W5P_SHED_BY_BUS_YEAR_KIND.csv`
- `workflow/results/BYOP/next07_s0_lossless_probe/W5P_FAR_WEST_2026_SNAPSHOTS.csv`
