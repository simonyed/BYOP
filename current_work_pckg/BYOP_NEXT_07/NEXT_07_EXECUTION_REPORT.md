# NEXT_07_EXECUTION_REPORT (2026-10-23, New York time)

```text
WORK_PACKAGE: BYOP_NEXT_07
SOURCE_MAIN_SHA: bcd9844d2cda985d9c369e89aca2020a25e5def3 (rechecked: main = mainline-v13-stageA = L2 at start)
START_HEAD: bcd9844d2cda985d9c369e89aca2020a25e5def3
END_HEAD: see NEXT_07_RESULTS_INDEX.json (final report commit on mainline-v13-stageA = GitHub main = L2)
SOLVED_CODE_SHA (W2): 5df4dda75efc4efb1796393c1131f93a8d801599 (approval: config-only commit 6181ff5f; approval closed after use in 4cc9dcc4)
ORIGINAL_S0_S1_CODE_SHA: cdfdea06146a6fe73df89cb410d6a88cb5fda306
W0_DATA_QA: PASS
W1_RESERVE_RHS_ONLY_STATIC: PASS
W2_NEW_SOLVER_CALLS: 1
W5P_LOSSLESS_PROBE_CALLS: 1 (approved bf61d873 via config commit 9dce6b5d; optimal, PASS; class LOSS_BASIS_CONFIRMED_MAIN_CAUSE)
W2_AUTHORIZATION: APPROVED (researcher in chat, 2026-10-23; approved_by sw2434@cornell.edu)
W2_SOLVER_AND_ACCEPTANCE: PASS (optimal, 877 s; diagnostic label DIAGNOSTIC_NONCOMPLIANT_WITH_FORMAL_3GW_REQUIREMENT)
W2_RHS_CHANGED_ONLY: YES
W2_CLASS: RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL (2026 Far West nightly shed 47,297.9 -> 47,297.4 MWh, -0.0009 %)
W3_S0_RELIABILITY_VERDICT: METHOD_BUG_CONFIRMED_REPAIR_REQUIRED (proposal after W5/W5P: calibration lossless vs scenarios with transmission_losses 2; gated status file unchanged)
W3_FULL_YEAR_DIAGNOSTIC: NOT_AUTHORIZED (and not runnable as prepared)
W4_A3_RUNTIME_STATIC: PASS (merged after the W2 seal; A3 manifest rebuilt; suite 290/0; zero-solver A3 E2E 13/13)
A3_SOLVER_CALLS: 0
ORIGINAL_A2_LEDGERS_UNCHANGED: YES (SHA-checked before and after the probe)
NEXT_DECISION_REQUIRED: choose ONE loss basis for calibration and S0-S3 ((a) losses on + re-check v1.6, or (b) lossless study), then a separately approved paired S0/S1 rerun; confirm the S2 developer-LP reserve rule
```

**Optimizer calls in this package: exactly 2** (W2 reserve probe; W5P lossless probe), each separately approved, 0 retries. Previously: It was the approved W2 probe: `S0#1/S0_COST`, 0 retries. A3 made 0 calls; every other model build had its solver intercepted.

## W0: corrected shed reconciliation (`W0_*`)

The reconstruction matches the reported totals within 0.0003 MWh, and the weights sum to 8,760 h in every year.
- **2026–2031 sum:** 54,205.78 MWh. This is a sum of six model-year values, not a single-year EENS.
- **2026 native:** 51,049.28 MWh, 94.2 % of the sum.
- **By sample class:** SAMPLED_WEEK 46,871.78 MWh (**86.5 %**, all in 2026); B7 7,334.00 MWh (13.5 %).
- **Far West pocket, 2026:** 87.5 % of the sum.
- **2026 raw 3 h shed:** 5,990.8 MWh = sampled-week 1,812.7 + stress-day 4,178.1. Only the sampled-week part carries the ×25.857 weight.

**Errata** to the NEXT-06 report wording (the signed report is not rewritten):
- "94 % Far West" should read 87.5 %.
- "94 % = two weeks × 25.86" should read 86.5 %.
- "5,991 MWh × 25.86" is wrong: only 1,812.7 MWh of it is from the sampled weeks.

## W1: reserve-RHS-only probe, static proof (`W1_*`)

The RHS is passed per build and is valid only from the exact probe config; every other config with a `diagnostic` block is refused.

**REF vs PROBE (built without a solver):**
- **Exactly one difference:** `PV16M-reserve_req` RHS goes 3000 → 0 on 816 rows.
- **Identical:** 2,660,074 variables, 7,107,710 constraints, 35,171,029 nonzeros; all other rows, the objective and the inputs.
- **REF2 == REF:** the probe leaves no state behind.

Suite at the solved code: 272 / 0.

## W2: the approved probe LP (`W2_*`, `workflow/results/BYOP/next07_s0_reserve_probe/`)

**Pre-run recheck on L2:** manifest 0 mismatches; gate approved; no prior probe ledger; original A2 ledgers byte-identical.

**Run:** STARTED 11:42 EDT. Barrier 88 iterations, 786 s, optimal; acceptance PASS. Solution state was persisted before acceptance (flows, dispatch, SOC, prices, reserve frames). No no-harm reference was written. The result carries the diagnostic label and **is not a reliability baseline**.

**Pre-registered metric:** 2026 Far West nightly weighted shed, **47,297.9 → 47,297.4 MWh (−0.0009 %)**. Class: **`RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL`**. This rejects the NEXT-06 leading hypothesis.

**Mechanism: a pocket deliverability limit, identical with or without the reserve.**
- At all 42 shed snapshots, TL43 is held at 117.05 MW (its effective model limit) and TL35 carries its KVL share of 387.63 MW, below its 461.9 MW rating.
- The pocket import is therefore capped at **504.68 MW**, against 500–558 MW of night load, with no local generation or storage.

**Immediate dispatch effect (2026):** cleanly separable, because neither run has any new public asset active in 2026.
- Shed, LMPs and the pocket are unchanged (2026 total −0.2 MWh).
- The probe holds 0 MW reserve; thermal online capacity equals dispatch.

**Investment feedback (2027–2031):**
- **Capacity:** solar −976 MW, CCGT −124 MW, 8 h BESS −63 MW; 4 h BESS +77 MW, wind +224 MW, AC +251 MW.
- **Timing:** 2029 builds −2,154 MW, shifted into 2030–31.
- **Shed:** 2027–2031 shed +765 MWh (+24 %), so 2026–2031 total goes 54,205.8 → 54,971.0 MWh.
- **Cost (PV):** public capex −$312 M, operating +$268 M, unserved +$26 M. Net −$18 M (−0.03 %), the full PV cost of the 3 GW rule in this sampled world.

**Sealed** (`W2_SEAL.json`): the consumed approval was closed (fields back to NOT_APPROVED; history in commit `6181ff5f` and the ledgers). The original S0/S1 files are untouched.

## W3: S0 decision (`W3_*`)

- **M** is answered: the reserve rule is not the cause.
- **T**, without an LP:
  - the sampled weeks are typical for the pocket;
  - a constant ~499 MW night supply reproduces the sampled-week shed and implies about 61 GWh over all 2026 nights;
  - so there is no evidence that the weights over-extrapolate.
- **NEXT-06 full-year LP:** not runnable as prepared (single-period build `KeyError: 'Generator-p_nom'`) → `NOT_AUTHORIZED`.
- **Verdict proposal:** `BASELINE_RELIABILITY_UNRESOLVED`. The residual question is why the v1.6 LP2 2025 check served these hours with the same lines. That is a West-mesh flow-pattern difference (fleet / DWB / load growth / chronology / TL43's effective limit), answerable read-only.
- **Paired S0/S1 rerun:** not justified; there is no bug evidence.

## W4: A3 static (`W4_A3_STATIC_READINESS.md`)

**Built and merged after the W2 seal** (as authorised):
- A3 runtime accounting covering every planned call kind;
- fail-closed `a3_guard` and `a3_solve_wrapper`;
- A2-reproduction checks;
- S2 convergence handling: no S3_mS2 and no efficiency claim when S2 has not converged;
- the matched-service audit;
- the conservative RE+BESS firm rule (F ≤ 0) in S2 and S3 alike.

**Verified:**
- A3 manifest rebuilt at `4edf7bac` (151 + 110 files, 0 mismatches).
- Suite **290 / 0**.
- Zero-solver A3 E2E **13 / 13**: all six A3 stages built through the real wrapper; planned child kinds in order; 0 solver executions.

**Bug found by the E2E and fixed:** the S2 developer LP received the 3 GW system reserve row (`0 >= 3000`, build failure). It is now skipped only on the private developer network; the requirement stays in S2 public and S3. **Your review is requested.**

**A3 remains locked.** Not approved, and the S0 verdict is unresolved. No A3 solve is authorised.

## Files

- **`current_work_pckg/BYOP_NEXT_07/`:**
  - W0: `W0_*`
  - W1: `W1_*`
  - W2: `N07_RESERVE_PROBE_PRE_RUN_MANIFEST.json`, `W2_APPROVAL_REQUEST.md`, `W2_RESERVE_CAUSAL_COMPARISON.csv`, `W2_RESERVE_CAUSAL_SUMMARY.json`, `W2_PUBLIC_INVESTMENT_BY_CARRIER_YEAR.csv`, `W2_RESERVE_CAUSAL_VERDICT.md`, `W2_SEAL.json`
  - W3: `W3_*`
  - W4: `A3_PRE_RUN_MANIFEST.json`, `W4_A3_STATIC_READINESS.md`
  - Package: `NEXT_07_RESULTS_INDEX.json`, `NEXT_07_RETURN_PACKAGE.zip`
- **`workflow/results/BYOP/next07_s0_reserve_probe/`:**
  - probe ledgers, `S0_RESULT.json`, `MAINLINE_*`;
  - `solution/S0/` (full solution on L2);
  - `W2_*`, `W3_*`;
  - `_static_w1/`, `_fullyear_size/`, `_w4_static/`, `_w4_merged/`, `_a3_e2e/`.

**Originals unchanged:** `POST_V16_A2_S0S1/*`, `next06_s0_diagnostic/`, `BYOP_NEXT_06/`, `POST_V16_A1_HEADROOM/`.

## W5 / W5P: why S0 sheds where LP2 did not (`W5_LP2_VS_S0_MESH_FLOW_EXPLANATION.md`, `W5P_LOSSLESS_VERDICT.md`)

**W5, read-only.** The mainline S0 is solved with `transmission_losses: 2` (inherited from `config.default.yaml` via the baseline meta). The v1.6 calibration LP1/LP2 were lossless.
- TL35 loses 49.5 MW (12 %) and delivers 387.6 of its 461.9 MW rating; TL43 delivers 113.2 of 118.98 MW.
- That is about 80 MW of pocket deliverability lost, more than the shortfall.
- Ratings, reactances and topology are identical to LP2.
- The W2 wording on TL35 was corrected (erratum in `W2_RESERVE_CAUSAL_VERDICT.md`).

**W5P, 1 approved call.** The formal S0 with `transmission_losses: 0`, everything else formal (static proof `W5P_STATIC_PASS`: only the loss terms differ).
- Optimal, acceptance PASS.
- 2026 shed: 51,049.9 → **0** MWh. 2026–2031: 54,205.8 → 646.8 MWh (the remainder is B7 stress days 2027–29, LP2-sized).
- Public builds about −10 GW; social cost −$3.94 B PV (−7.5 %).
- Class **`LOSS_BASIS_CONFIRMED_MAIN_CAUSE`**.

**Consequence.** The formal S0/S1 keep their record but should not be used for reliability or S1−S0 cost claims until the study runs on one loss basis. The researcher chooses that basis. The A3 manifest (`4edf7bac`) is stale after the W5P code changes; A3 remains locked.
