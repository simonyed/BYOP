# A3_READINESS_HANDOFF (NEXT-02 W4) — static preparation only, `A3 = NOT_APPROVED`, 0 solver calls

S2 and S3 have **not** been solved, and no S2/S3 solve is requested in this round. This note lists what must exist before an A3 request can be written. Per the work package, that request comes after S0/S1 have real, accepted results.

## 1. Prerequisites from A2

- **S0 and S1_EARLIEST must be PASS** (A2 gate ledger DONE / ok / optimal / pass, plus `S*_RESULT.json` acceptance) **and reviewed by you.**
- **The S2/S3 runs reuse the A2 public world:**
  - the same public world as S0/S1, with its identity hashed in `S0_S1_IDENTICAL_PUBLIC_INPUTS.json`;
  - the same `AC_exp` pair rules (`M2-line_sym`, one-sided price, `M2-line_cap`);
  - the same COD masks;
  - the same committed DWB / PBRP assets and committed-cost ledger;
  - the same 3 GW reserve, including the start-and-end SOC energy rows;
  - the same elapsed-3 h storage weighting;
  - the same no-harm reference rule: the S0 shed per unit × snapshot.

## 2. Open items before any A3 solve

| # | Item | Current state | Needed |
|---|---|---|---|
| A3-1 | **S2 Speed-First.** Lexicographic order: maximise deliverable qualified DC service / earliest COD first, then minimise private cost at that speed. | The existing developer LP (`private_mode` / `developer_joint_build`) uses a Gurobi hierarchical pre-solve. Not re-audited on the post-v1.6 line. | Audit that no large-weight delay penalty replaces the hierarchy. Grid offers and POI rights must come from the S1 rules, not unconstrained S1 outputs. Keep N/R/C sourcing separate from the GRID_ONLY / GRID_FLEX / ISLANDED supply modes. The R pool stays empty where it is empty. |
| A3-2 | **S3 coordinated.** | S3 builds (structural, 0 solves) with TECH_COMP_2 candidates, the permit → COD audit and supply-pool rows. | Align technology, lead, gas, permit, manufacturing pool, POI, public assets and no-harm with S2. Book social resource cost separately from private cash flows. Matched-service (S3_mS2) is mandatory if service differs. |
| A3-3 | **RE + BESS firm (A2-FIX-05).** | 96 `A2-F_cert` rows enter `serve_cap` in S3, but only on the 24 h B7 stress days. S0/S1 have none (checked: `QA-F5`). | Add 48 / 72 h continuous low-wind/low-solar certification on the **same** dispatch SOC, boundary SOC, and a same-resource double-reservation check. Keep GRID_FLEX and ISLANDED import eligibility separate (no free grid energy for an islanded certificate). Nameplate ≠ firm; one BESS cannot back two exclusive full services. A conservative public substitute needs your approval. |
| A3-4 | Weather | Single frozen weather year. `REEDS_MULTIWX_PENDING_LOCAL_H5` stays open. | No synthetic multi-year extremes. |
| A3-5 | **Environment → COD chain.** | All 16 buses: the permit-attributable COD delay is 0, because the L2 gas lead dominates. Bexar `p650 0` stays at L2 (D2). | A permit counts as a speed benefit only when it is on the critical path and changes delivered service. SOFC low-NOx is not automatically permit-free. A NOx control earns no time benefit without evidence. The hypothetical ozone-county block stays a mechanism check only, outside the base inputs. |
| A3-6 | Long horizon | Not built. | 2032–2035 new load, then 2036–2050 zero-increment operation (asset use, lock-in, duplicated expansion). Only after the four-scenario ERCOT case stands. No 2050 claims from the 2026–2031 case. |
| A3-7 | Comparisons | — | S2−S1 (speed and public-investment feedback) and S2−S3 (private vs social efficiency), with matched-service where service differs. Results may show no BYOP advantage. |

## 3. Budget for a future A3 request

To be set after S0/S1:
- one call per scenario (S3, S2 developer + public, S3_mS2);
- 0 retries;
- the same independent-gate pattern (own config, manifest and ledger), with no inheritance from A1 or A2 approval fields.
