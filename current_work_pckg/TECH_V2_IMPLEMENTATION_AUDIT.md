# TECH_V2_IMPLEMENTATION_AUDIT: TECH_COMP_2 in the repository (A0.2 P2–P4, zero solver calls)

## 1. Source and versioning

- **Source:** the researcher's original v2.0 ZIP is at `BYOP_A0_2_PreSolve_Integration_v1.1/source_tech_v2/ORIGINAL_SOURCE_ZIP.zip`, SHA `527ff8ab…241d`.
  - Its 9 files are unpacked unchanged.
  - The package tool `validate_original_sources.py` reports PASS, and the original `VALIDATE_STATIC_PARAMETERS.py` reports PASS.
- **Copied** byte-identical to `workflow/byop/inputs/tech_calibrated_v2/`:

  | File | SHA-256 (prefix) |
  |---|---|
  | `BYOP_TECH_PARAMETER_BASELINE_V2.json` | `10bd868b` |
  | `BYOP_TECH_PARAMETERS_V2.csv` | `3956cdd2` |
  | `BYOP_SUPPLY_POOL_PROXY_V2.csv` | `181af58f` |
  | `BYOP_COUNTY_OZONE_RULES_2026.csv` | `8bfc4de5` |
  | `SOURCE_REGISTER.json`, `PARAMETER_UNIT_CHECKS.json` | evidence only |

  `byop_tech_parameters_v2.verify_sources()` checks these SHAs on every load. Any change refuses to load; there is no silent default.
- **Versioning:**
  - The **legacy v1.3 table `MAINLINE_V13_TECH_DEFAULTS.csv` is unchanged** (byte-compared with A0 commit `946406d1` in `test_version_isolation_legacy_default_unchanged`).
  - `v240_mech.CFG['tech_version']` defaults to `legacy-v13`.
  - `TECH_COMP_2` is used only when a config sets `mainline.tech_version: TECH_COMP_2`, i.e. the prepared post-v1.6 S0/S1 config. Every legacy config therefore keeps v1.3 / TECH-01.
- **Not affected:** the A1 2025 model (fixed fleet) is untouched by v2. The public generation cost inputs are not changed.

## 2. Value changes v1.3 → v2.0 (BYOP behind-the-meter candidates only)

| Tech | CAPEX $/kW v1.3 → v2 | FOM $/kW·y v1.3 → v2 | v1.3 lead | v2 equipment + install (+ civil) | Private annual fixed $/kW·y (v2) |
|---|---|---|---|---|---:|
| RICE (`RICE_50DF` → RICE) | 2,450 → **2,200** | 43 → 43 | 2 y | 1.00 + 0.50 (civil 0.5) | **231.78** |
| OCGT_aero | 2,275 → **2,550** | 9.99 → **20** | 2 y | 1.50 + 0.50 (civil 0.75) | **225.50** |
| SOFC_NG | 7,953 → **3,900** | 37.77 → **125** (incl. stack reserve) | 3 y | 0.75 + 0.25 (civil 0.5) | **553.20** |
| WIND | 1,562 = | 34.57 = | 3 y | 1.75 + 0.75 (civil 1.25) | 160.45 |
| PV | 1,342 = | 23.60 = | 2 y | 0.75 + 0.50 (civil 0.5) | 131.75 |
| BESS 4 h | 1,500 = | 41.84 = | 1 y | 0.50 + 0.25 (civil 0.5) | 206.53 |

- **Heat rates (HHV):** unchanged. RICE 8,381, aero 9,447, SOFC 6,469 Btu/kWh, so `GAS-mdq` fuel rows and the efficiency 3,412.14/HR are as before.
- **Fuel:** HR/1000 × the WSC gas price for the year (3.738–4.857 $/MMBtu, 2026–2031) + VOM.
  - 2028: RICE 36.97, aero 39.752, SOFC 23.853 $/MWh, which equals the source `PARAMETER_UNIT_CHECKS.json`.
  - The flat 3.19 is used only as the reference price that `ml_gas_delta` re-prices to the year value, exactly as in v1.3.
- **Firm r:** RICE 1.25, aero 1.25, SOFC 1.10. Wind, PV and BESS have no stand-alone Firm credit; theirs comes only from the window certification (P4).
- **NOx control (CONTROLLED_ENV):**
  - RICE: +150 $/kW, +5 $/kW·y, NOx 0.700 → 0.0675 kg/MWh.
  - Aero: +200 $/kW, +4 $/kW·y, NOx 0.424 → 0.085 kg/MWh.
  - SOFC: no control path (0.001 kg/MWh).
  - The permit lead is identical on both paths.

## 3. Where each attribute is read (full table: `SOURCE_TO_PARAMETER_CROSSWALK.csv`, 147 rows)

| Step | Where |
|---|---|
| Source → loader | `byop_tech_parameters_v2.load / fixed_costs / fuel / nox_rate / byop_params_v2` |
| Loader → state | `v240_mech.byop_params(carrier, actor, path)` dispatches on `CFG['tech_version']`; `rearch_mech.add_byop_cohorts → v2_cohorts(site, car, actor)` |
| State → build | Generator `DC_<s> BYOP <tech> [CTRL] q<q>` with `capital_cost` (annual private for S2, social for S3), `marginal_cost`, `efficiency`, `build_year = first_period(COD_real)`, `avail_frac` / `firm_frac` from COD_real, and `STATE['byop_cod'][name]['permit_audit']` holding the full milestone row |
| Build → constraint | `V2-supply_pool_<tech>_<year>` (`extra_rearch` → `byop_supply_pools.add_pool_constraints`); existing `GAS-mdq_<S>`, `M2-serve_cap`, `ML-onsite_*` / `ML-potential_*` |
| Ledger | `byop_emissions` (PTE screen, CO₂ / NOx); `PERMIT_TO_COD_CAUSAL_AUDIT.csv` |
| Tests | `test_a0_2_tech_v2.py` (25 tests) |

## 4. S2 / S3 same physical set

- `cohort_harness('private')` and `cohort_harness('social')` build the RICE / SOFC / aero / BESS candidates of one site through the real `add_byop_cohorts`, without a solver.
- They produce identical names, buses, build years, lifetimes, `p_nom_max`, efficiencies, marginal costs, availability series and supply-pool candidates. Only `capital_cost` differs, because the private and social annuities differ (`test_s2_s3_same_physical_set_and_cod_from_permit_function`).
- The harness site is p630 9 (Denton, 2015 nonattainment) with a 3-year L2 gas lateral, so the RICE COD is set by gas (≥ 2029), not by the permit.

## 5. Limits (stated, not hidden)

- **Permit leads** are the v2.0 research proxies (`RELATIVE_RISK_RESEARCH_PROXY_NOT_LEGAL_DETERMINATION`), not TCEQ approval times.
- **Preconstruction:** the release equals the permit lead by default; earlier construction requires evidence.
- **Electrical readiness** uses the package's static-example proxy of 0.5 years after order.
- **Supply pools** are `RESEARCH_PROXY_NOT_VERIFIED_SPARE_OEM_CAPACITY`. 2032+ is refused (no value), and verified pre-orders are 0.
- **Site FIPS:** 8 of 16 research buses have a real Epoch site FIPS. 8 PNNL candidate buses are `UNKNOWN_CONSERVATIVE`; the bus geometry is not used.
- **Modules / MILP:** continuous capacity only. Module sizes (RICE 10 MW, aero 50 MW, SOFC 0.325 MW) are reported, not modelled; there is no MILP.
- **RE + BESS Firm:** the certificate model is built but not yet linked to `serve_cap` (an A2 item). Weather data: `REEDS_MULTIWX_PENDING_LOCAL_H5`, a single weather year.
- **Mainline status:** the multi-period mainline is still `POST_V16_MAINLINE_NOT_READY` (`rearch_mech --post-v16` exits 3). TECH_COMP_2 is `TECH_INTEGRATED_STATIC_ONLY`.
