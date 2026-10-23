# W2_RESERVE_CAUSAL_VERDICT (NEXT-07): the reserve-RHS probe

**Class (pre-registered): `RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL`.** Removing the 3,000 MW system reserve requirement does not change the 2026 Far West nightly shed:

| | Original S0 | Probe | Change |
|---|---:|---:|---:|
| 2026 Far West pocket weighted shed, nights | 47,297.9 MWh | 47,297.4 MWh | **−0.4 MWh (−0.0009 %)** |

This rejects NEXT-06's "most likely" driver. The probe is a diagnostic only: `DIAGNOSTIC_NONCOMPLIANT_WITH_FORMAL_3GW_REQUIREMENT`. It does **not** replace the formal S0, and is not a reliability baseline.

## Run record

| Item | Value |
|---|---|
| Authorisation | Researcher, in chat, 2026-10-23. Config-only commit `6181ff5f` on approved SHA `5df4dda75efc4efb1796393c1131f93a8d801599`; approved_by `sw2434@cornell.edu` |
| Pre-run recheck (L2) | Manifest 0 mismatches; normalised config SHA equal; gate `approved: true`; no prior probe ledger; original A2 ledgers byte-identical |
| Call | 1 × `S0_COST`, 0 retries. STARTED 15:42:46Z, DONE 15:56:49Z (11:42–11:56 EDT). Barrier, 88 iterations, 786 s; 877 s total; 16 threads |
| Status | ok / optimal |
| Acceptance | **PASS**: balance residual 2.0e-5 MW, reserve slack ≥ 0 against the 0 MW RHS, reserve-SOC, segment SOC rows, expansion pairs, no free public expansion, optimizer calls complete |
| Outputs | `workflow/results/BYOP/next07_s0_reserve_probe/`. Persisted state in `solution/S0/`: flows, dispatch, SOC, prices, reserve frames. No no-harm reference was written. |
| Untouched | Original `POST_V16_A2_S0S1` results and ledgers. A2 / A3 approvals not used. |

## 1. Immediate dispatch effect (2026)

**Clean separation.** Neither run has any public new asset active in 2026: 0 MW in both (`W2_PUBLIC_INVESTMENT_BY_CARRIER_YEAR.csv`). Every 2026 difference is therefore operational.

| 2026 | Original | Probe | Δ |
|---|---:|---:|---:|
| Existing-customer shed, weighted | 51,049.9 MWh | 51,049.7 MWh | −0.2 MWh |
| Far West pocket, nights (pre-registered metric) | 47,297.9 | 47,297.4 | −0.4 MWh |
| Far West pocket, raw 3 h | 3,049.3 | 3,049.3 | −0.05 MWh |
| p620 6 / p620 7 weighted | 31,199.9 / 16,250.0 | 31,191.4 / 16,258.3 | −8.5 / +8.3 MWh (shifted between the two buses) |
| p620 6 / p620 7 night shed snapshots | 40 / 16 | 40 / 16 | 0 |
| p620 3 / p630 2 (stress days) | 1,028.5 / 845.2 | 1,028.5 / 845.2 | ≈ 0 (p630 2 peak 281.5 → 281.4 MW) |
| Mean LMP, pocket buses, at the shed snapshots | $31.2k / $35.7k / $34.0k | same | < $0.1 |
| Mean LMP, all grid buses | $868.6 | $868.7 | +$0.02 |

**Why the reserve doesn't matter here: a network limit.** The probe's persisted flows (`W2_FAR_WEST_2026_SNAPSHOTS.csv`) show the following at every one of the 42 pocket shed snapshots:
- **TL43** (p620 4 → p620 6) is pinned at **117.05 MW**, its effective limit in the model (98.4 % of the baseline s_nom × s_max_pu of 118.98 MW). This holds in every period 2026–2031 and in both runs.
- **TL35** (p620 0 → p610 4) carries its KVL share, **387.63 MW**, well below its own 461.9 MW rating.
- The pocket's net import is therefore capped at **504.68 MW**, below the 500–558 MW pocket load at those hours.
- The pocket has no local generation or storage at night. Whatever the import cannot cover is shed.
- **This cap does not depend on the reserve.** With RHS 0 the system holds 0 MW of reserve, and thermal online capacity equals dispatch (31,648 MW mean, 63,278 MW available), yet the import into the pocket is the same.

The original run did not persist flows or dispatch (persistence began in NEXT-06), so the original side of the flow comparison is inferred, not observed. Its shed is identical per snapshot, so the same network limit binds.

## 2. Investment feedback (2027–2031)

Without the reserve requirement, the multi-year LP builds a different public portfolio. These are total equilibrium responses; investment and the dispatch that follows it are not separable after 2026.

| Public new MW (all build years) | Original | Probe | Δ |
|---|---:|---:|---:|
| Solar | 9,560.7 | 8,584.8 | **−975.9** |
| CCGT | 191.6 | 68.1 | **−123.5** |
| 8 h BESS | 180.2 | 116.9 | −63.3 |
| 4 h BESS | 642.5 | 719.3 | +76.8 |
| Onshore wind | 25,348.5 | 25,572.9 | +224.3 |
| AC expansion | 36,370.7 | 36,621.4 | +250.8 |

**Timing:**
- Builds are shifted out of 2029 (−2,154 MW, of which −617 MW in Far West zones) into 2030 (+1,053 MW) and 2031 (+495 MW).
- 2027: +27.8 MW. 2028: −32.5 MW.

**Consequences:**
- **2027–2031 shed rises:** 3,155.9 → 3,921.4 MWh (+765 MWh, +24 %). The 3 GW requirement had been bringing forward firm and flexible capacity that also reduced later shed.
- **2026–2031 weighted total:** 54,205.8 → 54,971.0 MWh (+765 MWh).

**Costs (PV 2026–2031):**

| | Δ |
|---|---:|
| Public capex | −$311.8 M |
| System operating cost | +$267.7 M |
| Existing-customer unserved loss | +$25.9 M |
| Physical spending proxy | −$44.0 M |
| Social welfare cost / LP objective | −$18.1 M / −$18.4 M (−0.03 %) |

So the whole 3 GW requirement costs about $18 M in PV over 2026–2031 in this sampled world. It shapes the build-out (less solar and CCGT, later builds) but not the 2026 pocket shortage.

## 3. What this does and does not show

- **Shows:** in the original model, forcing 3 GW of aggregate reserve does **not** cause the 2026 Far West nightly shortage. The shortage is set by a **deliverability limit into the pocket** (TL43 at its limit, TL35 at its KVL share), the same with or without reserve.
- **Does not show:**
  - that the 3 GW rule is right or wrong (the formal rule is unchanged);
  - that the min-load / online-capacity rows are irrelevant elsewhere (they stayed in the probe);
  - why the v1.6 LP2 2025 check served these hours with the same lines (NEXT-06 W1). With reserve ruled out, the remaining explanation is the night-time flow pattern across the wider West mesh, which sets the TL35/TL43 split. Candidates: the 2026 fleet and committed DWB/PBRP representation, load growth elsewhere, and the sampled-week chronology. These are listed in `W3_S0_SCIENTIFIC_DECISION.md`; none is tested by this probe.
- **Not a formal S0.** The probe holds 0 MW reserve in all 816 snapshots, a 3,000 MW shortfall against the formal rule. It must never be used as the reliability baseline.

Tables:
- `W2_RESERVE_CAUSAL_COMPARISON.csv`: 63 rows; original / probe / delta / unit / note.
- `W2_RESERVE_CAUSAL_SUMMARY.json`
- `W2_PUBLIC_INVESTMENT_BY_CARRIER_YEAR.csv`
- `workflow/results/BYOP/next07_s0_reserve_probe/W2_SHED_BY_BUS_YEAR_KIND.csv`
- `workflow/results/BYOP/next07_s0_reserve_probe/W2_FAR_WEST_2026_SNAPSHOTS.csv`
