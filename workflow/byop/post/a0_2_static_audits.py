#!/usr/bin/env python3
"""A0.2 static audit tables (no solver; every row DRY_NOT_SOLVED). Run from workflow/ (L2 for the RE/BESS part, needs linopy):
    python byop/post/a0_2_static_audits.py
Writes into current_work_pckg/: SOURCE_TO_PARAMETER_CROSSWALK.csv, TECH_COST_AND_COD_AUDIT.csv, PERMIT_TO_COD_CAUSAL_AUDIT.csv,
TECH_SUPPLY_USAGE_STATIC_QA.csv, TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv, TECH_EMISSIONS_PROXY_STATIC_QA.csv,
TECH_RE_BESS_FIRM_STATIC_QA.csv, A2_TECH_READINESS_MATRIX.csv (TECH_PERMIT_STATUS.csv: byop/build/build_tech_v2_site_permit.py)
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402
import byop_tech_parameters_v2 as T2  # noqa: E402
import byop_delivery_and_permit as D  # noqa: E402
import byop_emissions as EM  # noqa: E402
import byop_supply_pools as SP  # noqa: E402

OUT = WF.parent / 'current_work_pckg'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
S = 'DRY_NOT_SOLVED'


def crosswalk(J, T):
    src = 'BYOP_TECH_PARAMETER_BASELINE_V2.json (+ CSV cross-check)'
    use = {
        'capex_2025USD_per_kW': ('fixed_costs / byop_params_v2', "capital_cost of 'DC_<s> BYOP <tech> [CTRL] q<q>'", 'annual private / social annuity', 'test_cost_reference_values'),
        'fom_USD_per_kWyr': ('fixed_costs / byop_params_v2', 'capital_cost (FOM once per year)', 'annual cost', 'test_cost_reference_values'),
        'vom_USD_per_MWh': ('fuel / byop_params_v2', 'marginal_cost', 'fuel_cost = HR/1000 x gas + VOM', 'test_fuel_hhv_2028'),
        'heat_rate_HHV_Btu_per_kWh': ('fuel / byop_params_v2', 'efficiency = 3412.14 / HR; GAS-mdq fuel rows', 'MMBtu/MWh = HR/1000', 'test_fuel_hhv_2028'),
        'equipment_order_to_arrival_years': ('byop_delivery_and_permit.cod', 'build_year = first_period(COD_real); supply pool delivery year', 'equipment_ready', 'test_cod_cases'),
        'site_install_commission_years': ('byop_delivery_and_permit.cod', 'build_year / avail_frac / firm_frac', 'installation_done', 'test_cod_cases'),
        'civil_ready_from_order_years': ('byop_delivery_and_permit.cod', 'build_year', 'civil_ready', 'test_cod_cases'),
        'lifetime_years': ('byop_params_v2', 'lifetime + annuity', 'CRF', 'test_cost_reference_values'),
        'firm_redundancy_factor': ('byop_params_v2', 'failure-case firm credit 1/r at stress snapshots', 'serve_cap coefficient', 'test_version_isolation'),
        'NOx_kg_per_MWh_uncontrolled_proxy': ('nox_rate / byop_emissions', 'NOx PTE screen + operating ledger (no objective term)', 'permit route screen', 'test_env_06_controlled_no_speedup'),
        'NOx_kg_per_MWh_controlled_proxy': ('nox_rate / byop_emissions', 'CONTROLLED_ENV candidates', 'PTE screen', 'test_env_06_controlled_no_speedup'),
        'NOx_control_extra_CAPEX_USD_per_kW': ('fixed_costs(CONTROLLED_ENV)', 'capital_cost of CTRL candidates only', 'resource cost of the control path', 'test_env_06_controlled_no_speedup'),
        'NOx_control_extra_FOM_USD_per_kWyr': ('fixed_costs(CONTROLLED_ENV)', 'capital_cost of CTRL candidates only', 'annual cost', 'test_env_06_controlled_no_speedup'),
        'CO2_t_per_MWh': ('byop_emissions.operating_ledger', 'post-processing ledger only (carrier co2 = 0 placeholder)', 'CO2 t', 'test_emission_ledger'),
        'storage_duration_hours': ('byop_params_v2 / byop_renewable_firm', 'max_hours; E <= h x K', 'SOC', 'test_re_firm_model'),
        'storage_round_trip_efficiency': ('byop_params_v2 / byop_renewable_firm', 'sqrt(eta) store / dispatch', 'SOC chain', 'test_re_firm_model'),
    }
    rows = []
    for t, x in T.items():
        for k, (loader, var, ledger, test) in use.items():
            if k not in x:
                continue
            rows.append(dict(source_file=src, tech=t, key=k, value=x[k], unit=k.split('_', 1)[-1] if '_' in k else '', loader=loader,
                             state=f"M.CFG['tech_version']='TECH_COMP_2'", build_or_constraint=var, ledger=ledger, test=test,
                             evidence=x.get('evidence'), sources=';'.join(x.get('sources', []))))
    for cls, v in J['permit']['values_years_from_order'].items():
        for t, y in v.items():
            rows.append(dict(source_file='BYOP_TECH_PARAMETER_BASELINE_V2.json permit.values_years_from_order', tech=t, key=f'permit_lead[{cls}]', value=y,
                             unit='years from order', loader='byop_delivery_and_permit.permit_lead', state='site county class (19-FIPS table)',
                             build_or_constraint='final_permit_ready + construction_release -> COD_real -> build_year', ledger='PERMIT_TO_COD_CAUSAL_AUDIT',
                             test='test_env_cases', evidence=J['permit']['source_status'], sources=';'.join(J['permit']['sources'])))
    for r in pd.read_csv(T2.SRC / 'BYOP_SUPPLY_POOL_PROXY_V2.csv').itertuples():
        rows.append(dict(source_file='BYOP_SUPPLY_POOL_PROXY_V2.csv', tech=r.technology, key=f'pool[{r.delivery_year}]', value=r.ercot_available_MW_base_PROXY,
                         unit='MW net AC', loader='byop_supply_pools.pool', state="STATE['v2_pool_candidates']", build_or_constraint=f'V2-supply_pool_{r.technology}_{r.delivery_year}',
                         ledger='TECH_SUPPLY_USAGE_STATIC_QA', test='test_supply_pool', evidence=r.evidence_class, sources=r.source_refs))
    for r in pd.read_csv(T2.SRC / 'BYOP_COUNTY_OZONE_RULES_2026.csv', dtype={'county_fips': str}).itertuples():
        rows.append(dict(source_file='BYOP_COUNTY_OZONE_RULES_2026.csv', tech='ALL', key=f'county_class[{r.county_fips}]', value=r.classification_FOR_MODEL,
                         unit='class', loader='byop_delivery_and_permit.county_class', state="SITES[s]['county_fips']", build_or_constraint='permit lead class',
                         ledger='TECH_PERMIT_STATUS', test='test_env_01_ozone_table', evidence=r.evidence_class, sources=r.source_refs))
    return pd.DataFrame(rows)


def cost_cod(J, T):
    rows = []
    for t in T2.TECHS:
        for path in (T2.PATHS if t in ('RICE', 'OCGT_aero') else ('DEFAULT_ENV',)):
            fc = T2.fixed_costs(t, path, T)
            f28 = T2.fuel(t, 2028, T)
            for cls_fips, cls in (('48441', 'ATTAINMENT_OR_UNCLASSIFIED'), ('48121', 'OZONE_NONATTAINMENT_2015'), (None, 'UNKNOWN_CONSERVATIVE')):
                a = D.cod(t, 2026, cls_fips, path, gas_lead_years=1.0 if t in T2.GAS_TECHS else None, J=J, T=T)
                rows.append(dict(tech=t, path=path, county_class=cls, capex_USD_per_kW=fc['capex_USD_per_kW'], fom_USD_per_kWyr=fc['fom_USD_per_kWyr'],
                                 private_annual_USD_per_kWyr=round(fc['private_annual_USD_per_kWyr'], 3), social_annual_USD_per_kWyr=round(fc['social_annual_USD_per_kWyr'], 3),
                                 fuel_cost_2028_USD_per_MWh=round(f28['fuel_cost_USD_per_MWh'], 3), MMBtu_per_MWh_HHV=f28['MMBtu_per_MWh'],
                                 order_year=2026, gas_lead_assumed_y=1.0 if t in T2.GAS_TECHS else None, COD_real=a['COD_real'],
                                 COD_binding=a['COD_binding_milestone'], first_full_firm_year=a['first_full_firm_year'], status=S))
    return pd.DataFrame(rows)


def causal(J, T, sites):
    rows = []
    for s in sites.itertuples():
        for t in T2.GAS_TECHS + ['WIND', 'PV', 'BESS']:
            for path in (T2.PATHS if t in ('RICE', 'OCGT_aero') else ('DEFAULT_ENV',)):
                a = D.cod(t, 2026, s.county_fips or None, path, gas_lead_years=float(s.gas_lateral_lead_y_base) if t in T2.GAS_TECHS else None, J=J, T=T)
                pte = EM.pte_short_tpy(100.0, a['NOx_kg_per_MWh'])
                rows.append(dict(case='SITE_' + s.bus.replace(' ', '_'), site_id=s.site_id, site_fips=s.county_fips, gas_evidence=s.gas_evidence_level,
                                 **{k: a[k] for k in ('tech', 'permit_path', 'NOx_kg_per_MWh', 'CO2_t_per_MWh')},
                                 NOx_PTE_screen_short_tpy_100MW=round(pte, 5), ozone_class=a['ozone_class'],
                                 **{k: a[k] for k in ('permit_route_eligibility_status', 'permit_lead_years_proxy', 'equipment_ready', 'civil_ready', 'gas_ready',
                                                      'preconstruction_release', 'final_permit_ready', 'electrical_ready', 'COD_without_permit_constraints',
                                                      'COD_real', 'permit_attributable_COD_delay_years', 'COD_binding_milestone', 'first_full_firm_year',
                                                      'proxy_evidence_class')}, status=S))
    env = env_cases(J, T)
    return pd.concat([pd.DataFrame(rows), env], ignore_index=True), env


def env_cases(J, T):
    """ENV-01..10 pre-registered pure-function cases (ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md E)"""
    c = []
    def add(case, t, fips, path='DEFAULT_ENV', gas=0.5, **kw):
        a = D.cod(t, 2026, fips, path, gas_lead_years=gas if t in T2.GAS_TECHS else None, J=J, T=T, **kw)
        c.append(dict(case=case, site_id='STATIC_EXAMPLE', site_fips=fips, gas_evidence='EXAMPLE', NOx_PTE_screen_short_tpy_100MW=round(EM.pte_short_tpy(100.0, a['NOx_kg_per_MWh']), 5),
                      **{k: a[k] for k in ('tech', 'permit_path', 'NOx_kg_per_MWh', 'CO2_t_per_MWh', 'ozone_class', 'permit_route_eligibility_status',
                                           'permit_lead_years_proxy', 'equipment_ready', 'civil_ready', 'gas_ready', 'preconstruction_release', 'final_permit_ready',
                                           'electrical_ready', 'COD_without_permit_constraints', 'COD_real', 'permit_attributable_COD_delay_years',
                                           'COD_binding_milestone', 'first_full_firm_year', 'proxy_evidence_class')}, status=S))
        return a
    add('ENV-01_unknown_fips', 'SOFC_NG', None)
    add('ENV-02_RICE_50DF_no_SI_evidence', 'RICE', '48441')
    add('ENV-02_aero_never_NG_EGU', 'OCGT_aero', '48441')
    add('ENV-03_SOFC_ordinary', 'SOFC_NG', '48441')
    add('ENV-04_RICE_nonattainment_preconstruction', 'RICE', '48121')
    add('ENV-05_SOFC_gas_L2_3y', 'SOFC_NG', '48121', gas=3.0)
    add('ENV-06_RICE_default', 'RICE', '48441', 'DEFAULT_ENV')
    add('ENV-06_RICE_controlled', 'RICE', '48441', 'CONTROLLED_ENV')
    add('ENV-08_RICE_attainment_proxy', 'RICE', '48441')
    add('ENV-08_RICE_ozone_proxy', 'RICE', '48121')
    for t in ('WIND', 'PV', 'BESS'):
        add(f'ENV-09_{t}_nonzero_permit', t, '48121')
    add('ENV-10_SOFC_default', 'SOFC_NG', '48121', gas=1.0)
    add('ENV-10_aero_default', 'OCGT_aero', '48121', gas=1.0)
    return pd.DataFrame(c)


def supply():
    t = SP.pool_table()
    rows = [dict(kind='POOL', tech=k[0], delivery_year=k[1], pool_MW=v, used_MW=None, within_pool=None, note='RESEARCH_PROXY_NOT_VERIFIED_SPARE_OEM_CAPACITY',
                 status=S) for k, v in t.items()]
    ex = [dict(site_id='p630 9', tech='RICE', order_year=2026, path='DEFAULT_ENV', MW=200, delivery_year=2027, asset_id='A1'),
          dict(site_id='p650 0', tech='RICE', order_year=2026, path='CONTROLLED_ENV', MW=150, delivery_year=2027, asset_id='A2'),
          dict(site_id='p650 0', tech='RICE', order_year=2026, path='CONTROLLED_ENV', MW=150, delivery_year=2027, asset_id='A2'),   # duplicate asset
          dict(site_id='p610 2', tech='SOFC_NG', order_year=2026, path='DEFAULT_ENV', MW=60, delivery_year=2026, asset_id='A3')]
    u = SP.usage_check(ex)
    for r in u.itertuples():
        rows.append(dict(kind='EXAMPLE_USAGE', tech=r.tech, delivery_year=r.delivery_year, pool_MW=r.pool_MW, used_MW=r.used_MW, within_pool=r.within_pool,
                         note=f'example orders across buses / paths; duplicate asset rows ignored: {r.duplicate_assets_ignored}', status=S))
    try:
        SP.pool('RICE', 2032)
        rows.append(dict(kind='YEAR_2032', tech='RICE', delivery_year=2032, note='ERROR: value returned', status='FAIL'))
    except ValueError as e:
        rows.append(dict(kind='YEAR_2032', tech='RICE', delivery_year=2032, pool_MW=None, note=f'refused: {e}', status=S))
    ra = SP.rights_audit([dict(asset_id='N1', owner='DC', site='p630 9', kind='N', physical_MW=100, firm_right_MW=80, contracted_right_MW=20, rights_source='S2 build'),
                          dict(asset_id='C1', owner='DC', site='p650 0', kind='C', physical_MW=50, firm_right_MW=50, contracted_right_MW=10, rights_source='contract')])
    for r in ra.itertuples():
        rows.append(dict(kind='RIGHTS_AUDIT', tech=r.kind, note=f'{r.asset_id}: firm {r.firm_right_MW} + contract {r.contracted_right_MW} vs physical {r.physical_MW} -> {r.status}', status=S))
    rows.append(dict(kind='R_POOL', tech='REUSE', note=f"GREAL_R_ASSET_POOL.csv rows = {len(pd.read_csv(BP.INPUTS / 'poi/GREAL_R_ASSET_POOL.csv'))} (empty = no qualified reuse candidate; never generated)", status=S))
    return pd.DataFrame(rows)


def env_ledger(T):
    rows = []
    for t in T2.TECHS:
        x = T[t]
        rows += [dict(tech=t, attribute='CO2_t_per_MWh', value=x['CO2_t_per_MWh'], evidence=x['evidence'], affects_COD=False, use='operating ledger only'),
                 dict(tech=t, attribute='NOx_kg_per_MWh_default', value=x['NOx_kg_per_MWh_uncontrolled_proxy'], evidence=x['evidence'], affects_COD='via permit class / route only (no continuous NOx -> lead function)', use='PTE screen + ledger'),
                 dict(tech=t, attribute='NOx_kg_per_MWh_controlled', value=x['NOx_kg_per_MWh_controlled_proxy'], evidence=x['evidence'], affects_COD=False, use='CONTROLLED_ENV ledger; same permit lead'),
                 dict(tech=t, attribute='water', value=None, evidence='SOFC low conventional water use: qualitative (Bloom datasheet) - no like-for-like cross-technology data' if t == 'SOFC_NG' else 'NOT_QUANTIFIED', affects_COD=False, use='explanation only (no price, no lead change)'),
                 dict(tech=t, attribute='noise', value=None, evidence='SOFC low noise: qualitative - no like-for-like facility data' if t == 'SOFC_NG' else 'NOT_QUANTIFIED', affects_COD=False, use='explanation only'),
                 dict(tech=t, attribute='permit_lead_proxy_by_class', value=json.dumps({k: v[t] for k, v in T2.load()[0]['permit']['values_years_from_order'].items()}),
                      evidence='RELATIVE_RISK_RESEARCH_PROXY_NOT_LEGAL_DETERMINATION', affects_COD=True, use='final permit + construction release milestones')]
    return pd.DataFrame(rows)


def emissions_qa(T):
    rows = []
    for t in T2.GAS_TECHS:
        for p in (T2.PATHS if t != 'SOFC_NG' else ('DEFAULT_ENV',)):
            r = T2.nox_rate(t, p, T)
            rows.append(dict(check='PTE_100MW', tech=t, path=p, NOx_kg_per_MWh=r, value=EM.pte_short_tpy(100, r), unit='short ton / yr',
                             formula='100 MW x 8760 h x rate / 907.18474'))
    site = EM.site_pte([dict(site_id='S1', tech='RICE', path='DEFAULT_ENV', capacity_MW=60), dict(site_id='S1', tech='RICE', path='CONTROLLED_ENV', capacity_MW=40),
                        dict(site_id='S1', tech='SOFC_NG', path='DEFAULT_ENV', capacity_MW=50)])
    rows.append(dict(check='SITE_AGGREGATION', tech='RICE+SOFC', path=site.paths[0], value=float(site.NOx_PTE_screen_short_tpy[0]), unit='short ton / yr',
                     formula='sum over all units / paths of the site (never split)'))
    led = EM.operating_ledger([dict(tech='RICE', path='DEFAULT_ENV', MWh=1000), dict(tech='SOFC_NG', path='DEFAULT_ENV', MWh=1000)])
    for r in led.itertuples():
        rows.append(dict(check='OPERATING_LEDGER_1000MWh', tech=r.tech, path=r.path, value=r.CO2_t, unit='t CO2', formula=f'NOx {r.NOx_kg} kg; {r.note}'))
    for t in ('RICE', 'OCGT_aero'):
        d = EM.control_cost_delta(t, T)
        rows.append(dict(check='CONTROL_COST_DELTA', tech=t, path='CONTROLLED_ENV', value=d['extra_private_annual_USD_per_kWyr'], unit='USD / kW-yr private',
                         formula=f"extra CAPEX {d['extra_capex_USD_per_kW']} USD/kW, extra FOM {d['extra_fom_USD_per_kWyr']} USD/kW-yr"))
    rows = pd.DataFrame(rows); rows['status'] = S
    return rows


def re_firm_qa():
    import byop_renewable_firm as RF
    rows = []
    win = {'w24': 24, 'w48': 48, 'w72': 72}
    rng = np.random.default_rng(0)
    strong = {k: np.clip(0.4 + 0.2 * rng.standard_normal(v), 0, 1) for k, v in win.items()}
    sun = {k: np.tile(np.r_[np.zeros(7), np.sin(np.linspace(0, np.pi, 11)), np.zeros(6)], v // 24) for k, v in win.items()}
    zero = {k: np.zeros(v) for k, v in win.items()}
    for label, cw, cp in (('typical_profile', strong, sun), ('weak_wind_no_sun', zero, zero)):
        for mode in RF.MODES:
            m, lab = RF.build_firm_model(cw, cp, win, mode=mode)
            names = list(m.variables)
            ub = RF.firm_energy_upper_bound(cw, cp, win, dict(wind=100, pv=100, bess=50), mode=mode, grid_import_cap=0.0)
            rows.append(dict(case=label, mode=mode, windows='24/48/72 h', n_vars=int(m.nvars), n_cons=int(m.ncons), soc_variables=';'.join(lab['soc']),
                             shadow_soc=any('RESERVE' in v or 'shadow' in v.lower() for v in names), grid_import_vars=any('grid_import' in v for v in names),
                             F_upper_bound_no_solve_MW_at_K100_100_50=round(ub, 6), status='DRY_NOT_SOLVED (built, never solved)'))
    return pd.DataFrame(rows)


def readiness():
    R = [('A1 LP-R / LP-N build (1 h stress, 3 GW reserve, max lambda, zero shed)', 'READY_STATIC', 'gate NOT_APPROVED; never solved'),
         ('A1 gate (FIX-02 / FIX-03 / FIX-04)', 'READY_STATIC', 'fault-injection tests only'),
         ('TECH_COMP_2 parameter adapter (6 tech, cost, HHV fuel, annuities)', 'READY_STATIC', 'byop_params dispatch on CFG tech_version'),
         ('Permit -> COD pure function (19 FIPS, route screen, critical path)', 'READY_STATIC', 'research proxy leads; no legal determination'),
         ('Site FIPS for the 16 buses', 'READY_STATIC', '8 known Epoch site FIPS, 8 UNKNOWN_CONSERVATIVE (PNNL candidate buses)'),
         ('add_byop_cohorts TECH_COMP_2 branch (site COD, DEFAULT / CONTROLLED paths)', 'READY_STATIC', 'static harness only; mainline itself refused (exit 3)'),
         ('Supply pool rows V2-supply_pool_<tech>_<year>', 'READY_STATIC', 'added in extra_rearch for TECH_COMP_2; 2032+ refused'),
         ('NOx PTE / operating CO2 / NOx ledger', 'READY_STATIC', 'post-processing; no emission price / cap'),
         ('RE + BESS Firm certification (24 / 48 / 72 h)', 'READY_STATIC', 'model builder only; not linked to serve_cap (A2 item); REEDS_MULTIWX_PENDING_LOCAL_H5'),
         ('Gas MDQ with TECH_COMP_2 heat rates', 'READY_STATIC', 'existing GAS-mdq rows use efficiency = 3412.14 / HR (same HR as v1.3)'),
         ('N / R / C rights ledger', 'READY_STATIC', 'audit function; R pool empty = no reuse candidate'),
         ('Post-v1.6 operating reserve in the multi-period mainline (replace 15 % ERM / shadow SOC)', 'NOT_IMPLEMENTED', 'A2 item; rearch_mech --post-v16 exits 3 (POST_V16_MAINLINE_NOT_READY)'),
         ('Priced, lagged public expansion without S0CAL / ERM-02', 'NOT_IMPLEMENTED', 'A2 item (S0CAL / ERM-02 refused on the new line)'),
         ('RE / BESS Firm certificate in the serve_cap / FLEX rows', 'NOT_IMPLEMENTED', 'A2 / A3 item'),
         ('S2 / S3 same physical candidate set', 'READY_STATIC', 'same builder, actor changes cost only (test_s2_s3_same_physical_set)'),
         ('S3_mS2 dynamic (site, year) keys', 'READY_STATIC', 'keys built from STATE dc (16 buses x periods); no hard-coded 48 / 8 (test)'),
         ('A2 S0 / S1 run', 'BLOCKED', 'NOT_APPROVED + mainline not ready'),
         ('A3 S2 / S3 / S3_mS2 run', 'BLOCKED', 'NOT_APPROVED + A2 first')]
    return pd.DataFrame([dict(module=a, status=b, note=c) for a, b, c in R])


def main():
    J, T = T2.load()
    sites = pd.read_csv(T2.SRC / 'RESEARCH_SITE_COUNTY_FIPS_V2.csv', dtype={'county_fips': str}, keep_default_na=False)
    crosswalk(J, T).to_csv(OUT / 'SOURCE_TO_PARAMETER_CROSSWALK.csv', index=False, lineterminator='\n')
    cost_cod(J, T).to_csv(OUT / 'TECH_COST_AND_COD_AUDIT.csv', index=False, lineterminator='\n')
    ca, env = causal(J, T, sites)
    ca.to_csv(OUT / 'PERMIT_TO_COD_CAUSAL_AUDIT.csv', index=False, lineterminator='\n')
    supply().to_csv(OUT / 'TECH_SUPPLY_USAGE_STATIC_QA.csv', index=False, lineterminator='\n')
    env_ledger(T).to_csv(OUT / 'TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv', index=False, lineterminator='\n')
    emissions_qa(T).to_csv(OUT / 'TECH_EMISSIONS_PROXY_STATIC_QA.csv', index=False, lineterminator='\n')
    try:
        re_firm_qa().to_csv(OUT / 'TECH_RE_BESS_FIRM_STATIC_QA.csv', index=False, lineterminator='\n')
    except ImportError as e:
        print('RE/BESS firm QA skipped here (needs linopy, run on L2):', e)
    readiness().to_csv(OUT / 'A2_TECH_READINESS_MATRIX.csv', index=False, lineterminator='\n')
    print(env[['case', 'tech', 'permit_path', 'ozone_class', 'COD_real', 'COD_without_permit_constraints', 'permit_attributable_COD_delay_years', 'COD_binding_milestone']].to_string())


if __name__ == '__main__':
    main()
