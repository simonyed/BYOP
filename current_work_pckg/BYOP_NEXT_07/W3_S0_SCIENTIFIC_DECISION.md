# W3_S0_SCIENTIFIC_DECISION (NEXT-07), 2026-10-23 (updated after the approved W2 probe; W3 itself: 0 optimizer calls)

**Proposed verdict: `BASELINE_RELIABILITY_UNRESOLVED` (unchanged).** The A3 gate reads `current_work_pckg/BYOP_NEXT_06/S0_SCIENTIFIC_STATUS.json`, and that file is **not** modified. The proposal is in `W3_S0_RELIABILITY_VERDICT_PROPOSAL.json`.

## 1. Two questions, kept apart

| | Question | Status after NEXT-07 (no new solve) |
|---|---|---|
| **M** (mechanism) | Does the 3 GW reserve requirement cause the 2026 Far West nightly shortage in the same sampled world? | **Answered: no.** The W2 probe (RHS 0, 1 call, optimal, acceptance PASS) leaves the 2026 Far West nightly shed at 47,297.4 vs 47,297.9 MWh (−0.0009 %): `RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL`. The binding cause is a deliverability limit into the pocket: TL43 at 117.05 MW plus TL35 at its KVL share of 387.63 MW, so the import is capped at 504.68 MW. See `W2_RESERVE_CAUSAL_VERDICT.md`. |
| **T** (representativeness) | Do the two sampled weeks over-state the 2026 year? | **Partly answered without an LP: no evidence of over-extrapolation under the A2 rules** (section 2). Not proven, because the deliverable supply into the pocket is endogenous. |

Even if W2 shows a large reserve effect, T stays a separate question. A mechanism result does not upgrade the 51 GWh weighted figure into a credible annual EENS.

## 2. T: representativeness evidence without an optimizer

Script `byop/post/next07_w3_representativeness.py` (W4 branch, run read-only on L2). Outputs: `workflow/results/BYOP/next07_s0_reserve_probe/W3_REPRESENTATIVENESS*`, and `W3_POCKET_LOAD_FULL_YEAR_3H.csv.gz` on L2.

**Pocket load.** The pocket {p610 4, p620 6, p620 7} is 2026 native load (v1.6 p_set × 1.009327), 2,920 snapshots of 3 h, weather year 2030.
- Mean 507 MW, maximum 593 MW. The load is very flat.
- **The sampled weeks are typical, not extreme, for the pocket.** Their night-time mean is 504.7 MW, the 48th percentile of the year.
- The B7 stress days are extreme for ERCOT as a whole (system load at the 85th percentile) but not for the pocket (47th percentile).

**What S0 delivered.** At the 42 pocket shed snapshots, S0 served 458–537 MW (median 499 MW) against loads of 500–558 MW. This is below the 580.9 MW static cut, which is the meshed-network effect found in NEXT-06 W1.

**Rule-based bound.** If the night supply level seen at the shed snapshots held all year, the implied 2026 shed would be as follows. This is a rule, not an LP; local daytime solar is not credited.

| Assumed night supply | Night snapshots above it | Implied 2026 shed (3 h, MWh) | Same rule inside the sampled weeks |
|---|---:|---:|---:|
| 537 MW (max served) | 178 | 6,976 | 174 MWh |
| **499 MW (median served)** | 873 | **60,701** | **1,832 MWh** (actual S0 raw sampled-week shed in the pocket: **1,786 MWh**) |
| 458 MW (min served) | 1,414 | 208,832 | 7,835 MWh |

The median-supply rule reproduces the actual sampled-week shed almost exactly (1,832 vs 1,786 MWh). Extended over all nights of the year, it gives about 61 GWh, the same order as the model's weighted 2026 pocket figure (47.4 GWh).

**Reading.** The weights do not obviously over-state the year. If S0's night-time deliverability into the pocket persists, the shortage is roughly year-round under the A2 rules. The open point is whether that deliverability limit is right, which is M, not the weights.

**Limit.** The supply level is an outcome of the S0 dispatch (reserve coupling, mesh flows) and can vary by season. This bounds T; it is not a full-year solve.

## 3. The prepared NEXT-06 full-year LP: not runnable as prepared

A solver-free build of exactly the NEXT-06 diagnostic was run on L2 (2026 only, `sample_weeks 0`, formal 3 GW; script `byop/tests/structural_n07_fullyear_size.py`).

- **The build fails before any solver call:** `KeyError: 'Generator-p_nom'` in `v240_mech.extra`. A single-period 2026 model has no extendable generator, so the variable group does not exist.
- Evidence: `workflow/results/BYOP/next07_s0_reserve_probe/_fullyear_size/SIZE_BUILD_FAILURE.excerpt.log`.
- Had the NEXT-06 request been approved, the attempt would have been consumed with **0 optimizer calls and no result**.
- Its approvable SHA `e2daf9d3` is also stale: NEXT-07 changed gated code since then.
- Any future full-year request therefore needs:
  - a code fix (the single-period path of `v240_mech.extra`);
  - a new SHA and manifest;
  - a successful zero-solver build that reports the real `nvars / ncons / nnz` and memory;
  - its own approval (1 call, 0 retries, formal 3 GW reserve).
- Comparability limit, registered in advance: a full year (continuous SOC, one period) and the representative sample (segment SOC, 2026–2031 jointly) are different feasible sets. It is evidence on annual reliability under the same rules, not a pure re-weighting experiment.

## 4. Decision rules (fixed in advance, unchanged)

| W2 outcome (2026 Far West nightly shed, probe vs original) | Class | Next |
|---|---|---|
| reduction ≥ 80 % | `RESERVE_REQUIREMENT_LARGE_CONTRIBUTOR` | Analyse congestion, online-capacity and SOC evidence from the persisted state. The formal 3 GW rule stays. The researcher decides whether the reserve's representation (non-locational, min-load coupling) is a method question. Full-year LP only if T must be closed for publication. |
| 20–80 % | `MIXED_CAUSES` | Rank contributions from the persisted flows / SOC; no single-factor claim |
| < 20 % | `RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL` | Mechanism lies elsewhere (segment SOC, 2026 fleet, DWB, network); no new arbitrary sensitivity batch |
| infeasible / warning / acceptance failure | `DIAGNOSTIC_BLOCKED` | Keep evidence, no retry |

**Paired formal S0/S1 rerun:** not justified now. No implementation bug has been evidenced. W0 found only reporting-ratio errors, and W1 found no build difference.

## 5. After W2 (the probe ran: class NOT_PRIMARY)

**The reserve rule is cleared as the cause.** The shortage is a network deliverability limit into the pocket at night. The same lines served these hours in the v1.6 LP2 2025 check, so what differs is the night-time flow pattern across the West mesh, which sets the TL35/TL43 split. That pattern comes from inputs or rules other than the reserve:
- the 2026 fleet and committed-asset representation (DWB uniform 0.51 derate, PBRP);
- load growth elsewhere;
- the sampled-week chronology and segment SOC;
- TL43's effective model limit (117.05 MW, 98.4 % of its baseline s_nom × s_max_pu).

All of these can be examined **read-only** from the persisted probe state (bus angles via flows, upstream injections) against the LP2 2025 solution. That is the cheapest next step and needs no solve.

**Verdict proposal unchanged: `BASELINE_RELIABILITY_UNRESOLVED`.** Moving to `PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS` would need two things:
- an explanation of why the LP2 2025 check had no shed (evidence that the 2026 limit is physical, not an artefact);
- your explicit decision.

There is no evidence of an implementation bug, so `METHOD_BUG_CONFIRMED_REPAIR_REQUIRED` does not apply and no paired S0/S1 rerun is proposed. The full-year LP stays `NOT_AUTHORIZED` (and is not runnable as prepared). The decision the researcher needs to make next is whether to commission the read-only LP2-vs-S0 mesh-flow comparison, or to accept the pocket limit as physical scarcity with stated limits.
