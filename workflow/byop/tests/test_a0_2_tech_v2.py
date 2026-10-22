"""A0.2 static tests (zero solver): T-VERSION, T-COST, T-COD, T-ENV-COD (ENV-01..10), T-SUPPLY, T-RE_FIRM, T-BASELINE, S2/S3
same physical set, dynamic keys. Any real optimizer call fails (autouse fixture)."""
from __future__ import annotations

import hashlib, json, math, re, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
for p in ('model', 'build', 'post'):
    sys.path.insert(0, str(WF / 'byop' / p))
import byop_paths as BP  # noqa: E402
import byop_tech_parameters_v2 as T2  # noqa: E402
import byop_delivery_and_permit as D  # noqa: E402
import byop_emissions as EM  # noqa: E402
import byop_supply_pools as SP  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
J, T = T2.load()
PKG = WF.parent / 'current_work_pckg/BYOP_A0_2_PreSolve_Integration_v1.1/source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22'


@pytest.fixture(autouse=True)
def no_solver(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('solver called in an A0.2 test')
    try:
        import linopy
        monkeypatch.setattr(linopy.Model, 'solve', boom)
    except ImportError:
        pass
    yield


# ------------------------------------------------------------------------------------------------ T-VERSION
def test_sources_byte_identical_to_package_and_pinned():
    for f, h in T2.SOURCE_SHA256.items():
        assert sha(T2.SRC / f) == h == sha(PKG / f)
    assert sha(PKG.parent / 'ORIGINAL_SOURCE_ZIP.zip') == '527ff8ab95dbaaaab5c0d6c160d405b05eae7a941d7b73d1850f92e5601b241d'


def test_version_isolation_legacy_default_unchanged():
    import importlib
    v240 = pytest.importorskip('v240_mech')
    assert v240.CFG['tech_version'] == 'legacy-v13'
    import subprocess
    old_blob = subprocess.run(['git', '-C', str(WF.parent), 'show', '946406d1:workflow/byop/inputs/tech/MAINLINE_V13_TECH_DEFAULTS.csv'],
                              capture_output=True).stdout.replace(bytes([13, 10]), bytes([10]))
    now = (BP.INPUTS / 'tech/MAINLINE_V13_TECH_DEFAULTS.csv').read_bytes().replace(bytes([13, 10]), bytes([10]))
    assert old_blob and old_blob == now                                                       # legacy v1.3 table unchanged since A0
    cfg = dict(v240.CFG, tech_v13=str(BP.INPUTS / 'tech/MAINLINE_V13_TECH_DEFAULTS.csv'))
    old = dict(v240.CFG)
    try:
        v240.CFG.update(cfg)
        a = v240.byop_params('RICE', 'private')
        assert a['case'] == 'v13' and a['overnight_per_MW'] == 2450 * 1000          # legacy v1.3 RICE_50DF value
        v240.CFG['tech_version'] = 'TECH_COMP_2'
        b = v240.byop_params('RICE', 'private')
        assert b['case'] == 'TECH_COMP_2' and b['overnight_per_MW'] == 2200 * 1000 and b['r'] == 1.25
        c = v240.byop_params('RICE', 'private', path='CONTROLLED_ENV')
        assert c['overnight_per_MW'] == 2350 * 1000 and c['nox_kg_per_MWh'] == 0.0675
    finally:
        v240.CFG.clear(); v240.CFG.update(old)


def test_no_hardcoded_8_or_17_bus_count_in_new_code():
    for f in ['byop_tech_parameters_v2.py', 'byop_delivery_and_permit.py', 'byop_supply_pools.py', 'byop_emissions.py', 'byop_renewable_firm.py']:
        s = (WF / 'byop/model' / f).read_text(encoding='utf-8')
        assert not re.search(r'len\(SITES\)\s*==\s*(8|17)', s)
    st = pd.read_csv(T2.SRC / 'RESEARCH_SITE_COUNTY_FIPS_V2.csv', keep_default_na=False)
    assert len(st) == 16


def test_missing_parameter_is_an_error_not_zero(tmp_path):
    import shutil
    for f in T2.SOURCE_SHA256:
        shutil.copy(T2.SRC / f, tmp_path / f)
    (tmp_path / 'BYOP_TECH_PARAMETERS_V2.csv').write_text((tmp_path / 'BYOP_TECH_PARAMETERS_V2.csv').read_text().replace('2200', '2201', 1))
    with pytest.raises(ValueError, match='SHA mismatch'):
        T2.load(tmp_path)


# ------------------------------------------------------------------------------------------------ T-COST
def test_cost_reference_values():
    ref = {'RICE': 231.78, 'OCGT_aero': 225.50, 'SOFC_NG': 553.2}
    for t, v in ref.items():
        assert abs(T2.fixed_costs(t, T=T)['private_annual_USD_per_kWyr'] - v) < 0.01
    u = json.loads((T2.SRC / 'PARAMETER_UNIT_CHECKS.json').read_text())
    for r in u['records']:
        assert abs(T2.fixed_costs(r['tech'], T=T)['private_annual_USD_per_kWyr'] - r['private_annual_fixed_USD_kWyr']) < 0.01
    s = T2.fixed_costs('SOFC_NG', T=T)
    assert s['fom_USD_per_kWyr'] == 125                                                       # stack reserve inside FOM, once


def test_fuel_hhv_2028_and_gas_series():
    assert [T2.gas_price(y) for y in range(2026, 2032)] == [3.738, 3.513, 3.576, 3.768, 4.443, 4.857]
    for r in json.loads((T2.SRC / 'PARAMETER_UNIT_CHECKS.json').read_text())['records']:
        assert abs(T2.fuel(r['tech'], 2028, T)['fuel_cost_USD_per_MWh'] - r['gas_2028_marginal_cost_USD_per_MWh']) < 1e-3
    f = T2.fuel('RICE', 2028, T)
    assert f['MMBtu_per_MWh'] == 8.381 and abs(f['efficiency'] - 3412.14 / 8381) < 1e-12
    with pytest.raises(ValueError):
        T2.gas_price(2032)


def test_control_cost_only_on_controlled_path():
    assert T2.fixed_costs('RICE', 'DEFAULT_ENV', T)['capex_USD_per_kW'] == 2200
    d = EM.control_cost_delta('RICE', T)
    assert d['extra_capex_USD_per_kW'] == 150 and d['extra_fom_USD_per_kWyr'] == 5
    assert EM.control_cost_delta('SOFC_NG', T)['extra_capex_USD_per_kW'] == 0


# ------------------------------------------------------------------------------------------------ T-COD
def test_cod_cases():
    a = D.cod('SOFC_NG', 2026, '48441', gas_lead_years=0.5)
    assert a['COD_real'] == 2027.0 and a['first_full_firm_year'] == 2027                      # equipment 0.75 + install 0.25
    b = D.cod('SOFC_NG', 2026, '48441', gas_evidence='L2')
    assert b['COD_real'] >= 2029.0                                                            # L2 gas 3 y
    assert not D.firm_full_year(2027.25, 2027) and D.firm_full_year(2027.25, 2028)
    assert D.cod('RICE', 2026, '48121', gas_lead_years=0.5)['COD_real'] >= D.cod('RICE', 2026, '48441', gas_lead_years=0.5)['COD_real']
    assert J['schedule']['confirmed_fast_reserved_2026_MW']['SOFC_NG'] == 0                  # SOFC fast path: 0 MW
    with pytest.raises(ValueError):
        D.cod('RICE', 2026, '48441')                                                         # no gas evidence -> refused, not 0
    with pytest.raises(ValueError):
        D.cod('RICE', 2026, '48441', gas_lead_years=0.5, preconstruction_lead_years=0.0)    # earlier start needs evidence


# ------------------------------------------------------------------------------------------------ T-ENV-COD
def test_env_01_ozone_table():
    t = D.ozone_table()
    assert len(t) == 19 and (t.classification_FOR_MODEL == 'OZONE_NONATTAINMENT_2008_ONLY').sum() == 3
    assert ((t.nonattainment_2015_ozone == 1) == (t.classification_FOR_MODEL == 'OZONE_NONATTAINMENT_2015')).all()
    assert D.county_class(None)[0] == 'UNKNOWN_CONSERVATIVE'
    c, f = D.county_class('48441')
    assert c == 'ATTAINMENT_OR_UNCLASSIFIED' and 'NOT_IN_LIST_NOT_FULL_LEGAL_VERIFICATION' in f
    assert D.county_class('48121')[0] == 'OZONE_NONATTAINMENT_2015' and D.county_class('48291')[0] == 'OZONE_NONATTAINMENT_2008_ONLY'


def test_env_02_ng_egu_route():
    assert 'NOT_ESTABLISHED' in D.route_eligibility('RICE', None) and 'POSSIBLE' in D.route_eligibility('RICE', 'SI_PIPELINE_NG_VERIFIED')
    assert 'NOT_APPLICABLE_TURBINE' in D.route_eligibility('OCGT_aero', 'SI_PIPELINE_NG_VERIFIED')
    a = D.cod('RICE', 2026, '48441', gas_lead_years=0.5, equipment_type='SI_PIPELINE_NG_VERIFIED')
    assert a['permit_lead_years_proxy'] == 0.75                                               # eligibility never shortens the proxy


def test_env_03_sofc_permit_not_critical():
    a = D.cod('SOFC_NG', 2026, '48441', gas_lead_years=0.5)
    assert a['COD_real'] == 2027.0 and a['permit_attributable_COD_delay_years'] == 0


def test_env_04_preconstruction_default_blocks_parallel_build():
    a = D.cod('RICE', 2026, '48121', gas_lead_years=0.5)
    assert a['preconstruction_release'] == 2027.25 and a['COD_real'] == 2027.75               # 1.25 y permit, then 0.5 y install
    assert a['COD_without_permit_constraints'] == 2027.5 and a['permit_attributable_COD_delay_years'] == 0.25
    assert 'construction_release(permit)' in a['COD_binding_milestone']


def test_env_05_sofc_gas_l2_no_speed_gain():
    a = D.cod('SOFC_NG', 2026, '48121', gas_lead_years=3.0)
    assert a['COD_real'] == 2029.0 and a['permit_attributable_COD_delay_years'] == 0 and a['COD_binding_milestone'] == 'gas_ready'


def test_env_06_controlled_no_speedup():
    d = D.cod('RICE', 2026, '48441', 'DEFAULT_ENV', gas_lead_years=0.5)
    c = D.cod('RICE', 2026, '48441', 'CONTROLLED_ENV', gas_lead_years=0.5)
    assert c['COD_real'] == d['COD_real'] and c['permit_lead_years_proxy'] == d['permit_lead_years_proxy']
    assert EM.pte_short_tpy(100, c['NOx_kg_per_MWh']) < EM.pte_short_tpy(100, d['NOx_kg_per_MWh'])
    assert abs(EM.pte_short_tpy(100, 0.7) - 675.9373) < 1e-3                                  # /907.18474 kg per short ton


def test_env_07_site_pte_aggregated():
    s = EM.site_pte([dict(site_id='S', tech='RICE', path='DEFAULT_ENV', capacity_MW=60), dict(site_id='S', tech='RICE', path='CONTROLLED_ENV', capacity_MW=40)])
    assert len(s) == 1 and abs(s.NOx_PTE_screen_short_tpy[0] - (EM.pte_short_tpy(60, 0.7) + EM.pte_short_tpy(40, 0.0675))) < 1e-9


def test_env_08_permit_bottleneck_changes_cod():
    a = D.cod('RICE', 2026, '48441', gas_lead_years=0.5)
    b = D.cod('RICE', 2026, '48121', gas_lead_years=0.5)
    assert b['COD_real'] - a['COD_real'] == 0.25 and b['permit_attributable_COD_delay_years'] > 0 == a['permit_attributable_COD_delay_years']


def test_env_09_renewables_keep_positive_permit():
    for t in ('WIND', 'PV', 'BESS'):
        a = D.cod(t, 2026, '48121')
        assert a['permit_lead_years_proxy'] > 0 and a['COD_real'] > 2026 and a['NOx_kg_per_MWh'] == 0


def test_env_10_cross_tech_difference_not_all_environment():
    s = D.cod('SOFC_NG', 2026, '48121', gas_lead_years=1.0)
    a = D.cod('OCGT_aero', 2026, '48121', gas_lead_years=1.0)
    total = a['COD_real'] - s['COD_real']
    assert total == 1.25 and a['permit_attributable_COD_delay_years'] - s['permit_attributable_COD_delay_years'] == 0.25 < total


def test_no_monetised_environment_term():
    for f in ['byop_tech_parameters_v2.py', 'byop_delivery_and_permit.py', 'byop_emissions.py']:
        s = (WF / 'byop/model' / f).read_text(encoding='utf-8').lower()
        assert 'carbon_price' not in s and 'damage_cost' not in s and 'add_constraints' not in s


# ------------------------------------------------------------------------------------------------ T-SUPPLY
def test_supply_pool():
    t = SP.pool_table()
    assert len(t) == 18 and t[('RICE', 2026)] == 250 and t[('OCGT_aero', 2031)] == 400 and t[('SOFC_NG', 2028)] == 225
    with pytest.raises(ValueError):
        SP.pool('SOFC_NG', 2032)
    assert SP.pool('WIND', 2027) is None
    u = SP.usage_check([dict(site_id='a', tech='RICE', order_year=2026, path='DEFAULT_ENV', MW=200, delivery_year=2027, asset_id='x'),
                        dict(site_id='b', tech='RICE', order_year=2026, path='CONTROLLED_ENV', MW=150, delivery_year=2027, asset_id='y'),
                        dict(site_id='b', tech='RICE', order_year=2026, path='CONTROLLED_ENV', MW=150, delivery_year=2027, asset_id='y')])
    assert u.used_MW[0] == 350 and bool(u.within_pool[0]) is False                              # 350 > 300 across buses / paths
    ra = SP.rights_audit([dict(asset_id='c', owner='o', site='s', kind='C', physical_MW=50, firm_right_MW=50, contracted_right_MW=10, rights_source='x')])
    assert ra.status[0] == 'FAIL'


def test_pool_rows_on_a_model():
    pypsa = pytest.importorskip('pypsa')
    n = pypsa.Network(); n.set_snapshots(range(2)); n.add('Bus', 'b')
    n.add('Generator', ['g1', 'g2', 'g3'], bus='b', p_nom_extendable=True, capital_cost=1.0, marginal_cost=1.0)
    n.add('Load', 'l', bus='b', p_set=1.0)
    n.optimize.create_model()
    made = SP.add_pool_constraints(n, n.model, {'g1': ('RICE', 2027), 'g2': ('RICE', 2027), 'g3': ('SOFC_NG', 2026)})
    c = n.model.constraints['V2-supply_pool_RICE_2027']
    assert float(c.rhs) == 300 and set(c.lhs.vars.values.ravel()) - {-1} and len(made) == 2


# ------------------------------------------------------------------------------------------------ T-RE_FIRM
def test_re_firm_model():
    pytest.importorskip('linopy')
    import byop_renewable_firm as RF
    win = {'w24': 24, 'w48': 48}
    cw = {k: np.full(v, 0.3) for k, v in win.items()}; cp = {k: np.zeros(v) for k, v in win.items()}
    m, lab = RF.build_firm_model(cw, cp, win, mode='ISLANDED')
    names = list(m.variables)
    assert not any('grid_import' in v for v in names) and not any('RESERVE' in v for v in names)
    assert lab['soc'] == ['RF-E_w24', 'RF-E_w48']
    c = m.constraints['RF-soc_w24'].lhs
    co = set(np.round(np.abs(c.coeffs.values.ravel()), 6)) - {0}
    assert {1.0, round(math.sqrt(0.85), 6), round(1 / math.sqrt(0.85), 6)} <= co
    e0 = m.constraints['RF-E_initial_cap_w24'].lhs
    assert np.isclose(sorted(np.abs(e0.coeffs.values.ravel()))[-1], 2.0)                   # 0.5 x 4 h
    assert 'RF-E_final_ge_initial_w48' in m.constraints and m.constraints['RF-firm_w48'].lhs.sizes['t'] == 48
    g, _ = RF.build_firm_model(cw, cp, win, mode='GRID_FLEX', grid_import_cap=10)
    assert any('grid_import' in v for v in g.variables)
    zero = {k: np.zeros(v) for k, v in win.items()}
    assert RF.firm_energy_upper_bound(zero, zero, win, dict(wind=100, pv=100, bess=50)) == 0.0   # weak wind / sun -> 0 Firm
    w = RF.firm_windows(list(range(100, 172)))
    assert len(w[24]) == 24 and len(w[48]) == 48 and w[72][0] == 100


# ------------------------------------------------------------------------------------------------ S2 / S3 same physical set
def cohort_harness(actor):
    pypsa = pytest.importorskip('pypsa')
    import rearch_mech as R
    M = R.M
    saved = dict(M.CFG)
    M.CFG.update(periods='annual', start=2026, end=2031, decision_year=2026, frac_cod=True, firm_full_year=True, tech_version='TECH_COMP_2',
                 cost_basis='repaired', tv_share_byop=1.0)
    try:
        P = M.periods()
        mi = pd.MultiIndex.from_product([P, pd.date_range('2030-01-01', periods=2, freq='3h')], names=['period', 'timestep'])
        n = pypsa.Network(); n.set_snapshots(mi); n.investment_periods = P
        n.add('Bus', ['p630 9', 'DC_p630 9'])
        R.STATE['re_profile'] = {}
        R.STATE['stress_ts'] = set()
        R.STATE.pop('v2_pool_candidates', None)
        site = dict(site='p630 9', bus='p630 9', lat_lead=3.0, lat_cost=100e3, onsite_re=100.0, county_fips='48121')
        R.add_byop_cohorts(n, 'p630 9', site, 100.0, ['RICE', 'SOFC_NG', 'OCGT_aero', 'BESS'], None, actor)
        g = n.generators.copy(); su = n.storage_units.copy()
        pm = n.generators_t.p_max_pu.copy()
        audit = {k: v for k, v in R.STATE['byop_cod'].items()}
        return g, su, pm, audit, dict(R.STATE.get('v2_pool_candidates', {}))
    finally:
        M.CFG.clear(); M.CFG.update(saved)


def test_s2_s3_same_physical_set_and_cod_from_permit_function():
    gp, sp, pmp, ap, poolp = cohort_harness('private')
    gs, ss, pms, as_, pools = cohort_harness('social')
    assert list(gp.index) == list(gs.index) and list(sp.index) == list(ss.index)
    for col in ('bus', 'carrier', 'build_year', 'lifetime', 'p_nom_max', 'efficiency', 'marginal_cost'):
        assert (gp[col].values == gs[col].values).all(), col
    assert np.allclose(pmp.values, pms.values) and poolp == pools                         # same availability, same pool candidates
    assert (gp.capital_cost.values != gs.capital_cost.values).any()                       # only the cost basis differs
    assert any(' CTRL ' in x for x in gp.index) and not any('SOFC_NG CTRL' in x for x in gp.index)
    rice = [k for k, v in ap.items() if v['carrier'] == 'RICE' and 'CTRL' not in k]
    a = ap[rice[0]]
    assert a['permit_audit']['COD_real'] == a['cod'] and a['cod'] >= 2029.0                # L2-like 3 y lateral binds
    assert a['permit_audit']['ozone_class'] == 'OZONE_NONATTAINMENT_2015'


def test_dynamic_s3_ms2_keys_not_hardcoded():
    s = (WF / 'byop/model/rearch_mech.py').read_text(encoding='utf-8')
    assert not re.search(r'len\((SITES|keys|served)\)\s*==\s*48', s) and 'range(48)' not in s


# ------------------------------------------------------------------------------------------------ T-BASELINE
def test_baseline_pins_and_legacy_disabled_on_new_line():
    import post_v16_gate as G
    c = G.load(WF / 'config/config.byop_post_v16_a1.yaml')
    assert c['baseline']['sha256'] == 'a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16'
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_git_sha'] is None
    for p in (WF / 'config').glob('config.byop_ercot_mainline*.yaml'):
        import yaml
        assert yaml.safe_load(p.read_text())['mainline']['run_authorization'] == 'NOT_APPROVED'
    if BP.BASE_TAMU_V16.exists():
        assert sha(BP.BASE_TAMU_V16) == BP.BASE_TAMU_V16_SHA256
