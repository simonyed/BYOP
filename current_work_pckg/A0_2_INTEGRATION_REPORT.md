# A0_2_INTEGRATION_REPORT: pre-solve model integration (A0.1 repair + TECH_COMP_2 + environment → permit → COD), zero solver calls

- Date: 2026-10-22 (New York time). Branch `mainline-v13-stageA`.
- Commits:
  - Start: `946406d15f016bf6eb7dd37ae11d4ce99ead673d` (A0 report). Local, GitHub and L2 were identical; no drift.
  - P1 (A0.1 repair) code: `ed72b20865eb152178068f7e51e8b8cc98024cd4`.
  - P2–P5 code: **`@@CODE_SHA@@`**.
  - Report: the commit that contains this file.
- **REAL_SOLVER_EXECUTIONS = 0.** No real or mock optimizer call happened. All A1 / A2 / A3 gates remain `NOT_APPROVED`.
- **Frozen v1.6 baseline:** `a623fb6d…747d16`, verified on L2 and unchanged. No 2025 unit, line, x/r, s_nom, load, POI right, weather window or technology capacity was changed.

## 1. P0: what was checked

| Check | Result |
|---|---|
| HEAD / branch / tree | `946406d1`, clean, identical locally / on GitHub / on L2 |
| v1.6 `.nc` SHA (L2) | `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`, matches |
| A0 artefacts | A0 report, formulation, gate, manifest read and archived to `_completed/BYOP_Post_v1.6_Execution_v1.1_A0/`. Paths updated; the staging SHA QA was re-run: 53/53, 20/20, rebuild 19/19 text-identical. |
| v2.0 sources | Package `tools/validate_original_sources.py` → `ORIGINAL_TECH_V2_SOURCE_QA_PASS`; original `VALIDATE_STATIC_PARAMETERS.py` → PASS. ZIP SHA `527ff8ab…`; 9 files; 6 technologies, 18 supply rows, 19 ozone FIPS (16 classed 2015, 3 classed 2008-only). |
| Old tech chain | `MAINLINE_V13_TECH_DEFAULTS.csv` → `v240_mech.byop_params_v13` → `rearch_mech.add_byop_cohorts` / `ml_space` / `GAS-mdq` (inventory in `TECH_V2_IMPLEMENTATION_AUDIT.md` §3) |

## 2. P1: A0.1 repair, committed separately (`ed72b208`)

Full evidence: `A0_1_REPAIR_REPORT.md`.

- **FIX-01:** the objective is exactly −λ. Existing shed is a hard zero (`PV16-existing_shed_zero`) in B0 and BL and in both LPs. A λ at the artificial cap fails acceptance. The dispatch is an optimal witness only.
- **FIX-02:**
  - LP-N needs an LP-R ledger row DONE / ok / optimal / pass **and** `LP_R_H_RESOURCE_RESULT.json` with acceptance PASS on every check.
  - A1 is PASS only if both LPs PASS and 0 ≤ H_network ≤ H_resource + 1e-3. Otherwise `A1_BLOCKED` (exit 4).
- **FIX-03:** a STARTED row is persisted (fsync + atomic rename) before the solver. Any row of a stage consumes it, the budget is 2, there are no retries, and a corrupted ledger is refused.
- **FIX-04:** failure classes `solver_failed` / `output_failed` / `acceptance_failed` / `baseline_pressure_infeasible_{resource,network}_side`.
- **Dry (L2):** LP-R and LP-N each have 373,249 variables, 967,980 constraints, 0 integers, with the objective asserted to be −λ.

## 3. P2: TECH_COMP_2 (details: `TECH_V2_IMPLEMENTATION_AUDIT.md`, `SOURCE_TO_PARAMETER_CROSSWALK.csv`)

- **Inputs:** the four original files are copied byte-identical to `workflow/byop/inputs/tech_calibrated_v2/` and SHA-checked on every load. The legacy v1.3 table is unchanged and remains the default (`tech_version: legacy-v13`).
- **Selection:** `TECH_COMP_2` applies only through `mainline.tech_version` in the prepared post-v1.6 S0/S1 config.
- **Costs:** private annual fixed cost RICE **231.78**, aero **225.50**, SOFC **553.20** $/kW·y (7 % annuity + FOM once).
- **Fuel:** HHV, `HR/1000 × gas(year) + VOM` using the WSC 2026–2031 prices; efficiency = 3412.14/HR.
- **S2 / S3:** identical candidates and bounds; only the capital cost basis differs (tested through the real `add_byop_cohorts`).

## 4. P3: environment → permit → COD (main mechanism of this package)

### 4.1 Implemented chain

`byop_delivery_and_permit.cod()` computes, for every candidate:

```text
county class (original 19-FIPS table; no site FIPS -> UNKNOWN_CONSERVATIVE)
  -> permit lead (v2.0 JSON proxy)
  -> construction release (= permit lead unless evidence) and final permit
  -> installation = max(equipment, civil, release) + install
  -> COD_real = max(installation, final permit, gas lateral (site POI evidence), electrical)
  -> first full Firm year = ceil(COD_real)
```

- **Counterfactual:** `COD_without_permit_constraints` removes only the permit milestones. It is a non-compliant attribution device, not an option.
- **Delay:** `permit_attributable_COD_delay_years = max(0, COD_real − COD_without_permit)`.
- **Route screen:** the NG-EGU standard permit is possible only for verified spark-ignition pipeline-gas RICE. It never applies to turbines, and the `RICE_50DF` name is not proof. The screen reports eligibility and does not shorten the proxy lead.
- **Site FIPS (`TECH_PERMIT_STATUS.csv`):**
  - 8 buses have real Epoch-site FIPS:
    - 2015 nonattainment: Ellis 48139 (p630 2, p630 6), Denton 48121 (p630 9), Bexar 48029 (p650 0);
    - not in the list (research class attainment / unclassified, not a legal verification): Dickens, Taylor, Shackelford, Bell.
  - 8 PNNL candidate buses have no real site → `UNKNOWN_CONSERVATIVE`; the bus geometry is not used.

### 4.2 Pre-registered cases (`PERMIT_TO_COD_CAUSAL_AUDIT.csv`, rows `ENV-*`; order 2026)

| Case | Inputs | COD_real | COD without permit | Permit-attributable delay | Binding |
|---|---|---:|---:|---:|---|
| **ENV-03** | SOFC, ordinary county (lead 0.40), equipment 0.75 + install 0.25, gas 0.5 y | **2027.00** | 2027.00 | **0.00** | installation (permit not critical) |
| **ENV-05** | SOFC, ozone county (0.60), gas lateral 3 y | **2029.00** | 2029.00 | **0.00** | gas_ready: SOFC's low NOx gives **no** earlier COD |
| **ENV-06** | RICE ordinary county, DEFAULT (0.700 kg/MWh) vs CONTROLLED (0.0675) | **2027.50 / 2027.50** | 2027.50 | **0.00 / 0.00** | Installation. PTE (100 MW) 675.94 → 65.18 short t/yr; +150 $/kW, +5 $/kW·y; permit lead and COD **unchanged** |
| **ENV-08** | RICE, same inputs, attainment lead 0.75 vs ozone 1.25 | **2027.50 vs 2027.75** | 2027.50 | **0.00 vs 0.25** | Ozone case: construction release (permit) + installation, so the permit is on the critical path |
| ENV-04 | RICE ozone; construction not allowed before the 1.25 y permit | 2027.75 | 2027.50 | 0.25 | release 2027.25 + 0.5 install |
| ENV-10 | SOFC vs aero, ozone county, gas 1 y | 2027.00 vs 2028.25 | 2027.00 vs 2028.00 | 0.00 vs 0.25 | The 1.25 y gap is mostly equipment; only 0.25 y is permit, so the gap is **not** all environment |
| ENV-09 | Wind / PV / BESS, ozone county | 2028.50 / 2027.25 / 2026.75 | same | 0 | Positive site permit leads (0.75 / 0.40 / 0.35 y), never COD = 0 |

### 4.3 When the permit is and is not the bottleneck at the 16 research buses

- **Result:** across the 128 site × technology × path rows (order 2026), the permit-attributable COD delay is **0 everywhere**.
- **Why:**
  - 14 buses have gas evidence L2, so a 3-year lateral gives every gas technology COD = 2029.0.
  - The 2 L1 buses (p610 2 Taylor, p630 4 Shackelford, 1-year lateral, attainment counties) bind on gas or on equipment / installation.
- **Interpretation:** under the present gas evidence, the lower-emission technology's potential permit advantage (SOFC 0.40 / 0.60 y vs RICE 0.75 / 1.25 y and aero 1.00 / 1.75 y) **does not translate into an earlier actual COD** at any research bus.
  - It would matter only where firm gas is quick (L0 / L1) **and** the site is in an ozone-nonattainment county; ENV-08 / ENV-04 show the 0.25 y effect for RICE / aero.
  - This is a static research-proxy statement, not an optimisation result and not a legal permit timeline.

### 4.4 Emissions

- **NOx PTE screen:** per site over all units and paths, K × 8760 × rate / 907.18474 (`TECH_EMISSIONS_PROXY_STATIC_QA.csv`).
- **CO₂ / NOx:** an operating ledger only.
- **Not added:** emission price, carbon tax, cap or damage cost.
- **Water / noise:** qualitative only (`TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv`), with no COD effect.

## 5. P3c / P4: supply pools, rights, RE + BESS Firm

- **Supply pools (`TECH_SUPPLY_USAGE_STATIC_QA.csv`):**
  - 18 pool values (RICE 250–600, aero 200–400, SOFC 75–450 MW for 2026–2031).
  - `V2-supply_pool_<tech>_<year>` rows are shared across the 16 buses and both paths; the delivery year is that of equipment arrival.
  - Duplicate asset ids are counted once. 2032+ is refused. Verified pre-orders are 0.
- **Rights audit:** the N / R / C ledger fails on oversold firm + contract rights. The R pool is empty, meaning no reuse candidate; none is generated.
- **RE + BESS Firm (`byop_renewable_firm.py`, `TECH_RE_BESS_FIRM_STATIC_QA.csv`):**
  - 24 / 48 / 72 h windows; one SOC chain per window with √0.85 charge / discharge; E_initial ≤ 0.5 × 4 h × K; E_final ≥ E_initial.
  - ISLANDED has no grid-import variable. GRID_FLEX has a booked import variable.
  - No shadow SOC. The solver-free bound gives F = 0 for weak wind and no sun.
  - Built only (727 / 871 variables, 1,014 constraints); never solved; not yet linked to `serve_cap` (A2).

## 6. P5: integration, regressions, readiness

- **Readiness (`A2_TECH_READINESS_MATRIX.csv`):**
  - READY_STATIC: the A1 build and gate, the TECH_COMP_2 adapter, permit → COD, site FIPS, the cohort-builder branch, pool rows, ledgers, Firm builder, S2 / S3 same set, dynamic keys.
  - **NOT_IMPLEMENTED:** the post-v1.6 reserve rule in the multi-period mainline, priced public expansion without S0CAL / ERM-02, and the RE / BESS certificate in `serve_cap`.
  - **BLOCKED:** A2 and A3 runs. `rearch_mech --post-v16` still exits 3 (`POST_V16_MAINLINE_NOT_READY`); this was not removed.
- **Tests on L2 (pypsa 1.3.0):** @@L2_TESTS@@
- **Legacy mainline structural dry build** (`structural_mainline_v13.py`, legacy configs, no solver): @@LEGACY_STRUCT@@

## 7. Fixed return

```text
BRANCH / START_SHA / FINAL_CODE_SHA / FINAL_REPORT_SHA: mainline-v13-stageA / 946406d15f016bf6eb7dd37ae11d4ce99ead673d / @@CODE_SHA@@ (P1 ed72b20865eb152178068f7e51e8b8cc98024cd4) / the commit containing this report
PRE_RUN_STATUS: READY_FOR_RESEARCHER_APPROVAL
SOURCE_V2_PACKAGE_PRESENT: TRUE ; NUMERIC_CROSSWALK_RESULT: PASS - 4 source files byte-identical (SHA pinned, checked on load), JSON = CSV for 15 numeric fields x 6 techs, cost / fuel reference values reproduced (231.78 / 225.50 / 553.2; 2028 fuel 36.97 / 39.752 / 23.853), 147-row crosswalk source -> loader -> state -> build / constraint -> ledger -> test
V16_BASELINE_SHA_VERIFIED: a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16 on L2 (unchanged)
A0_1_FIXES: FIX01=PASS_STATIC (objective -lambda only, hard zero shed B0/BL LP-R/LP-N, cap check), FIX02=PASS_STATIC (LP-R RESULT PASS gate, A1_PASS/A1_BLOCKED), FIX03=PASS_STATIC (STARTED before solve, any row consumes, budget 2, corrupted ledger refused); FIX04 failure classes
TECH_VERSION: TECH_COMP_2 ; LEGACY_V13_UNCHANGED: TRUE (MAINLINE_V13_TECH_DEFAULTS.csv byte-equal to 946406d1; CFG default legacy-v13; legacy configs build unchanged)
TECH_V2_SIX_CARRIER_QA: PASS - RICE / OCGT_aero / SOFC_NG / WIND / PV / BESS loaded with units, sources, 2025 USD; no missing value silently 0; CONTROLLED_ENV only for RICE / aero
PERMIT_FIPS_COVERAGE_AND_UNKNOWN_CONSERVATIVE: 19/19 original FIPS used; research buses 8/16 with real Epoch-site FIPS (4 OZONE_NONATTAINMENT_2015, 4 not listed -> ATTAINMENT_OR_UNCLASSIFIED + NOT_IN_LIST_NOT_FULL_LEGAL_VERIFICATION), 8/16 UNKNOWN_CONSERVATIVE (PNNL candidate buses, no real site; bus geometry not used)
COD_AND_GAS_EVIDENCE_QA: PASS - SOFC 2026 standard -> COD 2027.0 (2027 full Firm); L2 gas 3 y -> >= 2029.0; 2027.25 COD -> no 2027 Firm; SOFC fast slots 0 MW; ozone class never faster; missing gas evidence refused (no 0 / infinite); 14/16 buses L2 (3 y), 2/16 L1 (1 y)
SUPPLY_POOL_2026_2031_QA: PASS - 18 values exact, shared across 16 buses / both paths / order years by delivery year, duplicate assets once, 2032+ refused, verified pre-orders 0
DIRECT_EMISSIONS_NOX_AND_NONQUANTIFIED_ENV_QA: PASS - NOx PTE screen /907.18474 per site over all paths (RICE 100 MW 675.94 -> 65.18 short t/yr controlled), CO2 / NOx operating ledger, carrier co2 = 0 flagged as placeholder, water / noise qualitative only, no monetised environment term
PERMIT_TO_COD_CAUSAL_QA: PASS - ENV-03 COD 2027.0 delay 0; ENV-05 COD 2029.0 delay 0 (gas binds, no speed gain); ENV-06 COD 2027.5 both paths, PTE down, cost up, lead unchanged; ENV-08 COD 2027.5 -> 2027.75, delay 0.25 (permit critical); at the 16 research buses delay = 0 in all 128 rows (gas / equipment bind): potential permit advantage of low-emission tech does NOT become an earlier actual COD under the current gas evidence
RE_BESS_FIRM_STATIC_ONLY: model builder only (24/48/72 h, one SOC, islanded / grid-flex), never solved, not linked to serve_cap (A2), weak resource -> F bound 0; REEDS_MULTIWX_PENDING_LOCAL_H5
S2_S3_SAME_PHYSICAL_FEASIBLE_SET_STATIC_QA: PASS - same candidates / bounds / availability / pool candidates through the real add_byop_cohorts; only capital_cost basis differs
A1_GATE_LOCKED / A2_GATE_LOCKED / A3_GATE_LOCKED: LOCKED (NOT_APPROVED) / LOCKED (NOT_APPROVED + rearch_mech --post-v16 exit 3) / LOCKED (NOT_APPROVED)
PYTEST_TOTAL_PASS_FAIL_SKIP_AND_L2_ENV: @@L2_TESTS@@
REAL_SOLVER_EXECUTIONS: 0
LEGACY_ERM02_S0CAL_IN_POST_V16: DISABLED
DELIVERABLE_FILES_AND_SHA256: A0_2_RETURN_PACKAGE.zip / FILE_LIST_SHA256.txt (inside the zip)
UNRESOLVED_BLOCKERS_FOR_A1: none technical; researcher approval required (config-only approval commit; LP-R then LP-N, 2 calls, 0 retries)
UNRESOLVED_BLOCKERS_FOR_A2_A3: post-v1.6 reserve rule not in the multi-period mainline; priced public expansion without S0CAL / ERM-02; RE+BESS certificate not in serve_cap; 8/16 research sites without real FIPS (UNKNOWN_CONSERVATIVE); permit leads / supply pools / electrical readiness are research proxies; single weather year; separate approvals for A2 and A3
NEXT_RESEARCHER_DECISION: REVIEW_A0_2_THEN_SEPARATELY_APPROVE_A1
```
