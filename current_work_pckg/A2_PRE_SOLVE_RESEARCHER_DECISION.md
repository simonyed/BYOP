# A2_PRE_SOLVE_RESEARCHER_DECISION (NEXT-02 W2 stop point): request for the S0 + S1_EARLIEST solve

**A2 is `NOT_APPROVED`. 0 A2 solver calls. This document requests a separate approval; it does not grant one.** A1 approval never carries over to A2. S2/S3 stay `NOT_APPROVED` (A3).

## 1. What was changed or verified (branch `work/a2-postv16-static`, code on top of `ba73e600`)

| Item | Result | Evidence |
|---|---|---|
| A2-FIX-01: fwd/rev expansion pairs | **PASS.** Pre-existing `M2-line_sym` + `M2-line_cap` rows (`v240_mech.extra`), plus the redundant upstream `bidirectional_link` row. 324 pairs × S0/S1/S3; rev-only and fwd-only builds rejected; fwd priced once. The ledger now needs the verified row. | `A2_EXPANSION_PAIR_AND_COST_AUDIT.md`, `PUBLIC_EXPANSION_CAPACITY_RIGHTS_QA.csv` |
| A2-FIX-02: cost / COD | **PASS.** 1,818 candidates: inactive and dispatch-masked before the build year, priced. 2027→2029 counterexample (62 cases). Committed DWB/PBRP cost ledger outside the objective. | `PUBLIC_EXPANSION_COST_COD_AUDIT.csv`, `COMMITTED_PUBLIC_ASSET_COST_LEDGER.csv` |
| A2-FIX-03: SOC / reserve time | **PASS (static)**, with **one model-behaviour fix:** stores weighting = elapsed 3 h (it was ~77 h), plus a start-of-interval reserve energy row. | `A2_RESERVE_SOC_TIME_QA.md` |
| A2-FIX-04: no-harm / S0≡S1 | **PASS.** All 68 existing-customer shed units (63 native + 5 inherited ramp) are in the S1 D24 row (S0 shed + 0.001 MW per unit × snapshot); no AIDC unit is in it. Public input hashes S0 = S1. | `NATIVE_LOAD_NO_HARM_QA.csv`, `S0_S1_IDENTICAL_PUBLIC_INPUTS.json` |
| A2-FIX-05: RE+BESS firm scope | S0/S1 have no `A2-F_cert` rows (`QA-F5`). The 48/72 h certification stays an S2/S3 prerequisite. | `A3_READINESS_HANDOFF.md` |
| A2-FIX-06: EOL / SHA | Tests are content-strict and EOL-portable; the A2 manifest has three layers; the A1 gate is untouched. | `A2_EOL_SHA_PORTABILITY_REPORT.md`, `A2_REGRESSION_SUMMARY.json` |
| A2-FIX-07: independent gate | `config.byop_post_v16_a2.yaml` (NOT_APPROVED), `post_v16_a2_gate.py`, own ledger `results/BYOP/post_v16_a2/POST_V16_A2_S0S1/A2_SOLVE_LOG.csv`, `A2_PRE_RUN_MANIFEST.json`. `rearch_mech --post-v16` is fail-closed (exit 3). | `A2_GATE_VERDICT.json` |

Structural run: 66/66 checks, 0 solver executions. Model sizes (variables / constraints / integers):
- S0: 2,660,074 / 7,096,405 / 0
- S1_EARLIEST: 2,712,538 / 7,284,741 / 0
- S3: 2,978,054 / 7,811,038 / 0

## 2. Forced-failure behaviour (each covered by a test or by the gate)

- The gate refuses:
  - when NOT_APPROVED;
  - when the config `stage` is not A2 (no A1 inheritance);
  - when the manifest is missing or mismatched;
  - for a wrong `--base`, `--config` or `--out`;
  - for any legacy flag;
  - for `--attribution` / `--relax`;
  - for scenarios other than [S0], [S0, S1_EARLIEST] or [S1_EARLIEST];
  - for a second call of the same stage (a STARTED row counts);
  - when the budget of 2 is used up;
  - for S1 without a DONE/ok/optimal/pass S0 plus an `S0_RESULT.json` acceptance PASS plus the frozen `S0_shed_by_snapshot_frozen.csv.gz`.
- Any optimizer call outside the ledgered wrapper is refused (`linopy.Model.solve` lock).
- **Acceptance per scenario** (all must hold, otherwise STOP):
  - `status=ok` and `termination=optimal`;
  - 0 integers;
  - nodal balance residual ≤ 1e-3 MW;
  - reserve slack ≥ −1e-3 MW;
  - both SOC reserve rows with slack ≥ −1e-3;
  - fwd/rev built capacity equal within 1e-3 MW;
  - no zero-cost public link built;
  - S1 only: no-harm excess ≤ 0.002 MW, the D24 row present, and the lexicographic pre-solve OPTIMAL.

## 3. The request

| Field | Value |
|---|---|
| Approve | `work/a2-postv16-static` at the code commit named in `A2_GATE_VERDICT.json` (`approved_git_sha`); config-only commit of `workflow/config/config.byop_post_v16_a2.yaml` |
| Fields you set | `run_authorization: APPROVED`, `approved_git_sha: <sha>`, `approved_by: <your identifier>` |
| Command (L2, A2 worktree `/datasets/prgm/BYOP_impact/pypsa-usa/.worktrees/a2/workflow`) | `THREADS=<T> bash byop/run/run_post_v16_a2.sh s0s1` (S0, then S1_EARLIEST in the same process; S1 starts only after S0 PASS) |
| Budget | **2 ledgered calls**, 0 retries. Disclosure: S1_EARLIEST = one Gurobi hierarchical speed-first pre-solve (`lex_presolve`) + the cost-stage LP inside the **same** ledgered call. |
| Threads | The two steps are dependent, so each runs as a single process. T = 24 − (other users' load at launch), capped at 22 and at least 4. About 6–8 at today's load of ~16 of 24. Memory ~10–20 GB each (not measured). |
| Run time | Not measured. NEXT-01 estimated 30–90 min per LP; that is **not** a guarantee. |
| Stop | Any gate refusal, exception, non-optimal status or acceptance failure. No retry, no log deletion, no parameter change, no S2/S3. |

## 4. Decisions you need to make before approving

- **D4: 3 h dispatch / 1 h reserve.** Confirm the research screening approximation **and** the stores-weighting fix (about 77 h → 3 h). This changes storage behaviour compared with all earlier mainline builds.
- **D5: DWB/PBRP.** Common exogenous committed assets; the absolute cost ledger is outside the objective. Review the cost figures and the sunk/unpaid shares (DWB 371 M$ SOURCED; PBRP per-path PROXY 3.02 B$; remaining shares are executor assumptions).
- **D6: no-harm.** S1 existing-customer shed ≤ S0 shed per unit × snapshot + 0.001 MW (recommended), rather than a hard zero.
- **D7: A2 two LPs.** S0 once and S1_EARLIEST once, 0 retries, at the SHA in `A2_GATE_VERDICT.json`.
- **A1 relation.** If A1 ends `A1_BLOCKED`, explain whether that undermines a credible S0/S1 physical baseline before A2 is released.
- **D2: Bexar p650 0.** Stays L2 (no firm MDQ or contract evidence).

## 5. Remaining proxies (not hidden)

- Single weather year.
- 26-week + B7 stress sampling.
- LP online-capacity relaxation.
- Reserve is a system-aggregate proxy.
- 8 of 16 sites have UNKNOWN_CONSERVATIVE county/permit status.
- POI, permit, supply-pool and electrical-readiness inputs are research proxies.
- The 460.73 MW inherited ramp may overlap Native Load 2025.
