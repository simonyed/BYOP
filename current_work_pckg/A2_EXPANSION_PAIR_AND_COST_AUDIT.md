# A2_EXPANSION_PAIR_AND_COST_AUDIT (NEXT-02 A2-FIX-01 / A2-FIX-02)

**A2_EXPANSION_PAIR_INTEGRITY: PASS**

Evidence is static: the full post-v1.6 S0 / S1_EARLIEST / S3 models were built on L2 and **0 solver executions** ran (3 calls were intercepted).
- Branch `work/a2-postv16-static`, code `ce64fea2`.
- Structural run: `workflow/results/BYOP/post_v16_a2_static/_structural_next02/` (66 / 66 checks PASS).

## 1. A2-FIX-01: is reverse-direction expansion free? **No.** Two existing rows tie each pair; nothing needed rewriting.

`rearch_mech.add_line_expansion_tamu` creates `L<line>_exp<p>_fwd` (`capital_cost` > 0) and `_rev` (`capital_cost` = 0). Tying the pair does **not** rest on the ledger's naming. On every built model the pair is bound by:

| Row | Code location | Form | Count in S0 / S1 |
|---|---|---|---|
| `M2-line_sym_<fwd>` | `workflow/byop/model/v240_mech.py` (`extra`, corridor block at the `STATE['corridors']` loop). It is called through `v250_mech.extra_gce` → `rearch_mech.extra_rearch`. `M.STATE` is `rearch_mech.STATE` (`STATE = M.STATE`), so the corridors set by `add_line_expansion_tamu` are the ones read. | `p_nom_fwd − p_nom_rev = 0` | 324 / 324 |
| `M2-line_cap_<corridor>` | same block | `Σ_p p_nom_fwd(p) ≤ corridor cap` (100 % of the existing rating) | 162 corridors |
| Upstream PyPSA-USA `opts.bidirectional_link` (`workflow/scripts/opts/bidirectional_link.py`) | added by `solve_network` for every extendable `_fwd/_rev` pair | `fwd.p_nom − rev.p_nom` equality (redundant with M2-line_sym) | log: "Added 324 bidirectional link constraints" |

Per-pair audit (`post_v16_mainline.expansion_pair_audit`; 648 rows in `PUBLIC_EXPANSION_CAPACITY_RIGHTS_QA.csv`, record `AC_exp_PAIR`), all **PASS**:
- **Equality row form:** exactly two variables, coefficients +1 / −1, sign `=`, rhs 0.
- **One-sided builds rejected:** a 100 MW reverse-only build violates the row, and so does a forward-only build. Equal 100 MW builds satisfy it.
- **Investment paid once:**
  - the fwd objective coefficient on `p_nom` is > 0, ranging from 1,055 to 90,671 (capital cost × period weights);
  - the rev objective coefficient is exactly 0;
  - so each MW of two-way capacity triggers one positive investment.
- **Shared attributes:** fwd and rev have the same build year, lifetime and `p_nom_max`.
- **Cumulative cap:** the corridor row contains the fwd variable (coefficient 1) and not the rev variable, and its rhs equals the corridor cap.
- **Timing:** approval year < build year. Corridors are offered for 2030 / 2031, approved 2026 / 2027 (line lead 4 y).

Committed fixed links (record `COMMITTED_FIXED_LINK`):
- `DWB_Stage_2`, `PBRP-765-A` and `PBRP-765-B` (fwd/rev) are non-extendable, cost-free in the LP, and appear in no `M2-line_sym` / `M2-line_cap` row.
- They therefore neither cancel nor double-count the endogenous expansion.

The ledger was hardened (`public_expansion_ledger(..., m=model)`):
- A `_rev` link is now `ENDOGENOUS_PRICED_VIA_FWD_EQUALITY` only if the equality row is verified on the model.
- Without a model it is `PAIR_UNVERIFIED`; without the row it is `FREE_FORBIDDEN`.
- Unit test: a pair without the row is flagged `FREE_FORBIDDEN`, and the reverse-only build is not rejected.
- S0 / S1 / S3 ledgers: 1,494 `ENDOGENOUS_PRICED` + 324 `ENDOGENOUS_PRICED_VIA_FWD_EQUALITY` + 6 committed. **0 free, 0 unverified, 0 S0CAL.**

## 2. A2-FIX-02: cost, build time, COD

`PUBLIC_EXPANSION_COST_COD_AUDIT.csv` covers 1,818 candidates × {S0, S1_EARLIEST}: 540 generators, 630 storage units and 648 `AC_exp` links. All **PASS**:
- approval year ≤ build year, with leads of 1–5 y (730 at 4 y, 630 at 1 y, 248 at 2 y, 180 at 3 y, 30 at 5 y);
- PyPSA activity mask is false in every period before the build year;
- **the dispatch variable is masked (label −1) for every snapshot before the build year in all 1,818 cases**;
- first active period = build year;
- positive capital cost and positive objective coefficient (a reverse link is priced through its fwd twin).

**Counterexample (approval 2027, positive lead, COD 2029):** 62 candidates, e.g. `p600 0 solar pub2029`. They are inactive and capacity-free in 2027 and 2028 in S0 and S1, under the same rule. The unit test `test_counter_example_2027_order_2029_cod_unavailable_before` covers the same case.

How cost enters the objective:
- PyPSA multi-period: capital cost per MW-year × period weighting, counted only in active periods.
- The annuity method applies, so the implicit residual value equals the remaining annuities beyond 2031 (`v240_mech.tv_factor`, θ = 1).
- Committed assets enter at `capital_cost` = 0 and are identical in every scenario.

Committed DWB / PBRP costs (new `inputs/grid/COMMITTED_PUBLIC_ASSET_COSTS.csv` → `COMMITTED_PUBLIC_ASSET_COST_LEDGER.csv`):
- These are **outside the LP objective** and cancel in every S-difference.
- They are reported separately for absolute social cost and funding flows:

| Asset | Total (base) | Sunk by end-2025 (assumed) | Unpaid commitment after 2025 | Source / class |
|---|---:|---:|---:|---|
| DWB Stage 2 | 371 M$ (2019) | 278 M$ | 93 M$ | ERCOT RPG Dec-2019 roadmap, Stage 2 TSP preliminary. Cost SOURCED; remaining share = EXECUTOR_ASSUMPTION. |
| PBRP-765-A | 3,020 M$ (2024) | 151 M$ | 2,869 M$ | ERCOT Jul-2024 PBRP report: 765-kV import paths 9.06 B$ for 3 paths, divided by 3. PROXY: no public per-path split found. |
| PBRP-765-B | 3,020 M$ (2024) | 151 M$ | 2,869 M$ | Same as PBRP-765-A |

- Low/high ranges are in the input file. High for PBRP is scaled to ERCOT's later ~15 B$ whole-plan update.
- These figures are **pending your review** (decision D5). None of them enters the optimisation.

Legacy items:
- ERM-02, the 15 % legacy ERM, shadow SOC and S0CAL are off on the post-v1.6 path. Checked by `QA-NOERM` in each scenario and by the ledger's 0 S0CAL.
- The 2025 v1.6 `.nc` is SHA-pinned and was not regenerated.
- The S0–S3 committed asset list is identical (`S0_S1_IDENTICAL_PUBLIC_INPUTS.json`).
