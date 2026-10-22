# A2_STATIC_INTEGRATION_REPORT: post-v1.6 multi-period S0/S1 preparation (NEXT-01 W2), zero solver calls

- **Branch:** `work/a2-postv16-static` @ **`ba73e600aa260b8f09ee9bd0d0084a98431c98d1`**, cut from `802c9d94`, pushed to GitHub as a separate branch.
  - It is **not merged** into `mainline-v13-stageA` and is not in the checkout A1 would run from.
  - Locally and on L2 it lives in `pypsa-usa/.worktrees/a2` (git-ignored). On L2 that worktree symlinks the untracked data and the baseline `.nc`.
- **Status:**
  - `A2_STATIC_STATUS = PASS_STATIC`.
  - `rearch_mech.py --post-v16` **still exits 3**, so no formal A2 solve is possible.
  - A2 / A3 remain `NOT_APPROVED`. **A2 solver calls: 0.**

## 1. What was implemented (`byop/model/post_v16_mainline.py` + hooks)

### A2-P1: operating reserve replaces the legacy ERM on the post-v1.6 path

- **Switch:** `wp2_ercot_s0_s1.POST_V16_NO_ERM` (default off, so legacy is unchanged). When on, `solve()` drops the `ERM` opt and `electricity.erm`, and disables ERM-DC-01.
  - Result: no `GlobalConstraint-*_ERM` row, no `*_RESERVES` shadow storage, no ERM-02 `M2-erm_margin`.
- **Hook:** `extra_rearch` adds `add_operating_reserve` when `post_v16_mainline.POST_V16['on']` is set:
  - **Requirement:** `PV16M-reserve_req`, Σ r ≥ 3,000 MW in **every snapshot of every period**.
  - **Thermal:** existing grid thermal and **extendable public thermal candidates**:
    - `p ≤ c`; `c ≤ p_nom × p_max_pu × active`, with `p_nom` a variable for candidates;
    - `p ≥ pmin × c`; `r ≤ c − p`; `r ≤ ρ × c`.
    - Parameters from `POST_V16_RESERVE_PARAMETERS.csv`, the same base values as A1.
  - **Grid storage:** `r ≤ p_nom − p_dispatch + p_store` (p_nom a variable if extendable), and `τ × r / η_d ≤ state_of_charge`, using **the dispatch SOC**.
  - **Excluded:** BYOP units at DC buses and load_shed are never reserve.
- **3 h mapping:** the reserve MW is held through the whole 3 h snapshot (each of its 3 hours is a 1 h requirement with the same dispatch), with 1 h energy backing from the end-of-snapshot SOC. The 3 h weight applies to dispatch energy only.
- **Scope:** a **system aggregate reserve**, not a deliverable ancillary-service product, not N-1 / LOLE.

### A2-P2: public expansion and initial assets

- **Ledger:** `public_expansion_ledger()` classifies every extendable public component. On S0, S1 and S3 alike:
  - **1,818 ENDOGENOUS_PRICED:** positive capital cost; the reverse link of a symmetric pair carries the cost on its forward link;
  - **0 FREE_FORBIDDEN**, **0 S0CAL**;
  - **6 COMMITTED_SUNK_COMMON_ASSET:** the same in S0–S3, as below.

  | Asset | Carrier | Buses | First period | MW | Source / treatment |
  |---|---|---|---|---:|---|
  | DWB Stage 2 (TPIT 69709 / 102815) | AC_base_committed | p620 4 ↔ p620 0 | 2026 (ISD 2026.49, partial first year) | 1,000 | ERCOT Far West report 2026-02-04; sunk common asset |
  | PBRP 765 kV A | AC_committed | p630 5 ↔ p620 1 | 2031 (ISD 2031.0) | 2,400 (SIL proxy) | PUCT-approved import path; sunk / committed |
  | PBRP 765 kV B | AC_committed | p650 7 ↔ p610 4 | 2031 (ISD 2031.5) | 2,400 (SIL proxy) | PUCT-approved; sunk / committed |

- **S0 vs S1:** identical public generators, candidates and costs, the same lines and the same committed links. Only the AIDC rows differ.
- **S1 POI:** equipment is phased per site and year (in 2026 some sites have pre-approved E0 > 0, others 0). There is no joint λ = 0 hard-coding.
- **Unchanged:** the v1.6 2025 file (SHA `a623fb6d…`); S0CAL and ERM-02 stay legacy-only.

### A2-P3: RE + BESS firm certificate and S2 / S3 same set

- **Certificate:** `add_re_bess_firm_certificate()` creates one `A2-F_cert_<site>_<period>` per (site, period); **96 = 16 × 6** in S3.
  - Rows: F ≤ Σ p(BYOP WIND, PV) + Σ (p_dispatch − p_store)(BYOP BESS) at every B7 stress snapshot.
  - Dispatch-SOC boundary per stress day: start ≤ 0.5 × h × p_nom, end ≥ start.
  - F / PUE enters `M2-serve_cap_<S>` of the same (site, period) as dedicated firm IT.
- **Normal operation:** wind / PV / BESS still dispatch normally; nameplate is never Firm.
- **Islanded only:** the certificate has no grid-import term.
- **S3 build (static):**
  - TECH_COMP_2 candidates carry the permit / COD audit, and every build year equals `first_period(COD_real)`.
  - CONTROLLED_ENV exists only for RICE / aero; all capital costs are positive.
  - Common pool rows `V2-supply_pool_<tech>_<year>` cover 2026–2031 only.
  - The A0.2 harness already showed that the S2 and S3 candidate sets are identical except for the cost basis.

## 2. Structural evidence (`results/BYOP/post_v16_a2_static/_structural/`)

- **Script:** `byop/tests/structural_post_v16_a2.py`. `linopy.Model.solve` and `gurobipy.Model.optimize` are replaced by a refusal; 3 calls were intercepted and **0 executed**.
- **Inputs:** the real post-v1.6 config (`tech_version: TECH_COMP_2`, `dynamic_pnnl_v1`, 16 buses) on the v1.6 baseline.
- **Checks:** **40 / 40 PASS** (`A2_STRUCTURAL_CHECKS.csv`, `A2_STRUCTURAL_REPORT.json`).
- **Model sizes:**

  | Scenario | Variables | Constraints | Integers |
  |---|---:|---:|---:|
  | S0 | 2,660,074 | 6,530,917 | 0 |
  | S1_EARLIEST | 2,712,538 | 6,663,765 | 0 |
  | S3 | 2,978,054 | 7,245,550 | 0 |

- **Unit tests:** `byop/tests/test_a2_a3_static.py`, 8 passed.
- **Branch regressions on L2:** 202 passed / 2 failed.
  - Both failures are **line-ending artefacts of the fresh worktree checkout**. Git stores LF; the A1 manifest and staging QA pin the CRLF bytes of the main checkouts.
  - The content is identical: the branch `post_v16_headroom.py` re-encoded to CRLF gives exactly the pinned hash.
  - A1 is unaffected because it runs from the main L2 checkout (P0 verified all hashes).
  - The A1 code was not changed. Making the A1 hashes EOL-portable is a decision for you, because it changes gated code.

## 3. Proposed A2 solve request (for a later approval; not requested to run now)

- **Order:** S0 first, then S1_EARLIEST. Each is one LP of about 2.7 M variables / 6.6 M constraints (estimate 30–90 min each on L2; not measured).
- **Budget:** 2 calls (S0, S1_EARLIEST), 0 retries, with the same STARTED-before-solve ledger and acceptance pattern as A1.
- **Required beforehand:**
  1. An A2 manifest and gate. The A1 gate pattern extends to the mainline; this is not implemented yet.
  2. Removal of the `--post-v16` exit 3, only after your approval.
  3. Your decisions on: the 3 h → 1 h reserve mapping; the sunk treatment of DWB Stage 2 / PBRP; whether to keep the no-harm reference (S0 shed per snapshot) or adopt the A1 hard zero for existing customers.
  4. The p650 0 gas evidence decision.
- **STOP conditions:**
  - not optimal;
  - existing-customer shed above the agreed reference;
  - reserve row infeasibility, reported as `BASELINE_PRESSURE_INFEASIBLE` and never fixed with free lines;
  - balance residual > 1e-3 MW;
  - any legacy ERM / S0CAL row present.

## 4. Open limits

- The certificate uses only the 24 h B7 stress days of the 3 h sample. The 48 / 72 h windows exist only in the stand-alone `byop_renewable_firm.py`.
- GRID_FLEX import certification is not in the main LP.
- Single weather year (`REEDS_MULTIWX_PENDING_LOCAL_H5`).
- Reserve parameters are still evidence class PENDING (permitted as a proxy for A1 by your A0.1 decision; A2 use needs confirmation).
- 8 of 16 sites are `UNKNOWN_CONSERVATIVE` for the permit class.
