"""Mainline v1.3 Stage A static tests (E2) - no LP solver is called anywhere in this file.
Run on L2 from pypsa-usa/workflow:  python -m pytest -q byop/tests/test_mainline_v13.py
(the pure input tests also run locally without pypsa; model tests are skipped when pypsa is missing)."""
from __future__ import annotations

import hashlib, inspect, math, re, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
BY = WF / 'byop'
INP = BY / 'inputs'
WP = WF.parent / 'current_work_pckg'
sys.path.insert(0, str(BY / 'model'))
EPOCH_BUSES = {'p600 0', 'p610 2', 'p630 2', 'p630 4', 'p630 5', 'p630 6', 'p630 9', 'p650 0'}
NEW_SRC = [BY / 'model/rearch_mech.py', BY / 'model/v240_mech.py', BY / 'post/collect_mainline.py',
           BY / 'build/build_mainline_inputs.py', BY / 'build/build_reeds2_potential.py']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rd = lambda rel: pd.read_csv(INP / rel)


@pytest.fixture(scope='module')
def R():
    pytest.importorskip('pypsa')
    import rearch_mech as R_
    R_.M.CFG.update(periods='annual', start=2026, end=2031, frac_cod=True, firm_full_year=True, decision_year=2026,
                    tech_v13=str(R_.ML_TECH), byop_case='base', cost_basis='repaired')
    gp = pd.read_csv(R_.ML_GASP)
    R_.M.CFG['gas_by_year'] = {int(r.year): float(r.gas_price_2025USD_per_MMBtu_HHV) for r in gp.itertuples()}
    return R_


# ------------------------------------------------------------------------------------------------ QA-DC
def test_qa_dc_reconciliation():
    rec = rd('dc/MAINLINE_AIDC_RECONCILIATION.csv')
    assert (rec.check == 'PASS').all()
    tot = rd('dc/ERCOT_DC_TOTALS_2026_2035.csv')
    rc = rd('dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv')
    ramp = rd('dc/MAINLINE_INHERITED_RAMP_2025.csv')
    for (sc, y), g in rc.groupby(['scenario', 'request_year']):
        t = float(tot[(tot.scenario == sc) & (tot.year == y)].new_IT_MW.iloc[0])
        inh = float(ramp.inherited_ramp_IT_MW.sum()) if y == 2026 else 0.0
        assert abs(g.IT_MW.sum() + inh - t) < 1e-3, (sc, y)          # approved total unchanged, no extra 461 MW
    assert abs(ramp.inherited_ramp_IT_MW.sum() - 460.73) < 0.01
    assert set(rc.region_id) == EPOCH_BUSES and set(ramp.bus) <= EPOCH_BUSES
    assert not set(rc.region_id) & {'DFW_KAU', 'ABI_TAY', 'PEC_REE'}     # old three test POIs carry no demand
    assert np.allclose(ramp.facility_MW_2026, ramp.inherited_ramp_IT_MW * 1.1567, rtol=1e-3)   # IT x PUE once


def test_qa_dc_s0_and_entry_points(R):
    assert "if scen != 'S0':" in inspect.getsource(R.M.build)             # S0: no research AIDC
    src = inspect.getsource(R.configure_mainline)
    assert 'POI_REQ' not in src and 'ML_COH' in src
    assert "a.setting, a.competing, a.regional_dc = 'G-REAL', 0.0, 'off'" in inspect.getsource(R.main)
    assert 'add_inherited_ramp(n)' in inspect.getsource(R.build_rearch)   # inherited ramp in every scenario incl. S0


# ------------------------------------------------------------------------------------------------ QA-COD
def test_qa_cod_approval_cohorts(R):
    M = R.M
    c = {q: (cod, bp) for q, cod, bp in M.approval_cohorts(2.0)}
    assert c[2029] == (2031.0, 2031) and 2030 not in c                    # 2029 decision + 2 y -> 2031; 2030 -> outside
    for y in (2029, 2030):
        assert M.avail_frac(2031, 2031.0, y) == 0.0
    assert M.avail_frac(2031, 2031.0, 2031) == 1.0
    assert M.firm_frac(2027, 2027.5, 2027) == 0.0 and M.avail_frac(2027, 2027.5, 2027) == 0.5   # half year: energy, no firm
    up = M.approval_cohorts(3.0, floor=2028.0)
    assert up[0] == (2026, 2029.0, 2029)                                  # POI upgrade after procedure + lead
    sofc = M.byop_params('SOFC_NG', 'private')
    assert sofc['lead'] == 3.0 and M.approval_cohorts(sofc['lead'])[0][1] == 2029.0


def test_qa_cod_existing_vs_new():
    e0 = rd('poi/GREAL_POI_E0_SCHEDULE.csv')
    assert e0.preapproved.all() and (e0.MW > 0).all()                     # existing / approved equipment rows
    pool = rd('poi/GREAL_R_ASSET_POOL.csv')
    assert len(pool) == 0                                                 # D14: no verified reusable unit -> empty


# ------------------------------------------------------------------------------------------------ QA-BESS
def test_qa_bess_soc_bound(R):
    b = R.M.byop_params('BESS', 'social')
    assert b['max_hours'] == 4.0 and abs(b['eta_rt'] - 0.85) < 1e-12
    eta = math.sqrt(b['eta_rt'])
    e_max = 1.0 * b['max_hours']                                          # 1 MW / 4 MWh
    soc, ok = e_max, True                                                 # start full, discharge 1 MW for 5 h, no charging
    for _ in range(5):
        soc -= 1.0 / eta
        ok = ok and soc >= -1e-9
    assert not ok                                                         # infeasible: 5 h at 1 MW > 4 MWh x eta
    assert abs(eta * eta - 0.85) < 1e-12                                  # store x dispatch efficiency = round trip
    src = inspect.getsource(R.add_byop_cohorts)
    assert "'StorageUnit'" in src and 'cyclic_state_of_charge=True' in src and 'efficiency_store=eta' in src


# ------------------------------------------------------------------------------------------------ QA-FIRM
def test_qa_firm_separation(R):
    M = R.M
    assert M.NONFIRM_BYOP == {'WIND', 'PV', 'BESS'} and M.SOFC_FAST_ELIGIBLE_MW == 0.0
    t = pd.read_csv(R.ML_TECH)
    assert not t.technology.str.contains('FAST').any()
    ex = inspect.getsource(M.extra)
    assert 'firm_frac(' in ex and 'NONFIRM_BYOP' in ex                   # firm credit: full years, no wind / PV
    src = inspect.getsource(R.add_byop_cohorts)
    assert "np.where(smask, fm / bp['r'], av)" in src                     # normal dispatch av, failure-case 1/r only at stress
    assert 'reuse_pool_poi' in inspect.getsource(R.add_reuse_poi) and 'ML_RPOOL' in inspect.getsource(R.reuse_pool_poi)
    assert 'S1_EARLIEST' in inspect.getsource(R.main) and "STATE['offer'], off = s1_offer(n1)" in inspect.getsource(R.main)


# ------------------------------------------------------------------------------------------------ QA-SPACE
def test_qa_space_inputs():
    poi = rd('poi/GREAL_POI_ASSUMPTIONS.csv')
    assert set(poi.bus) == EPOCH_BUSES and (poi.poi_upgrade_max_MW > 0).all() and (poi.onsite_renewable_cap_MW > 0).all()
    pot = rd('grid/ERCOT_WIND_SOLAR_POTENTIAL.csv')
    assert EPOCH_BUSES <= set(pot.bus) and (pot.remaining_new_MW_AC >= 0).all()


def test_qa_space_constraints(R):
    src = inspect.getsource(R.ml_space)
    assert 'ML-onsite_' in src and 'ML-potential_' in src and 'cap - fixed' in src
    assert "dc = f'DC_{s}'" in inspect.getsource(R.add_byop_cohorts)       # on-site units only at their own DC bus


# ------------------------------------------------------------------------------------------------ QA-COST
def test_qa_cost_gas_and_heat_rate(R):
    M = R.M
    assert [M.gas_price(y) for y in range(2026, 2032)] == [3.738, 3.513, 3.576, 3.768, 4.443, 4.857]
    r = M.byop_params('RICE', 'social')
    assert abs(r['mc'] - (8381 / 1000 * M.GAS + 7.0)) < 1e-9             # base mc at GAS; yearly delta added by ml_gas_delta
    assert abs((r['mc'] + 8381 / 1000 * (M.gas_price(2030) - M.GAS)) - (8381 / 1000 * 4.443 + 7.0)) < 1e-9
    assert 'HR x (gas_y - GAS)' in inspect.getsource(R.ml_gas_delta)
    c = (BY / 'post/collect_mainline.py').read_text(encoding='utf-8')
    assert 'private payments to the grid are transfers' in c


# ------------------------------------------------------------------------------------------------ QA-LP
def test_qa_lp_no_integer_and_no_maxmin():
    for f in NEW_SRC:
        s = f.read_text(encoding='utf-8')
        assert not re.search(r'binary\s*=\s*True|integer\s*=\s*True|vtype|GRB\.BINARY|GRB\.INTEGER', s), f
    dj = (BY / 'model/rearch_mech.py').read_text(encoding='utf-8')
    body = dj[dj.index('def developer_joint('):dj.index('def developer_joint_build(')]
    assert 'lexz' not in body and 'max-min' not in body.replace('No max-min', '') and 'itertools.product' not in body


# ------------------------------------------------------------------------------------------------ QA-DELAY-CAUSE
def test_qa_delay_cause(R):
    poi = rd('poi/GREAL_POI_ASSUMPTIONS.csv')
    assert poi.earliest_grid_COD_base.nunique() == 1                     # same rule at every bus, no forced bus delay
    src = inspect.getsource(R.poi_ledger)
    for f in ('equipment_total_MW', 'poi_eq_dual_abs', 'procedure_ready_year', 'earliest_grid_COD', 'certified_import_MW'):
        assert f in src
    c = (BY / 'post/collect_mainline.py').read_text()
    for f in ('poi_limit_MW', 'upstream_limit_or_binding', 'resource_adequacy_binding', 'S1E_xUP', 'S1E_xPROC'):
        assert f in c


# ------------------------------------------------------------------------------------------------ QA-STRESS-FIRM
def test_qa_stress_in_lp(R):
    b = inspect.getsource(R.ml_base_build)
    assert 'ml_stress_days' in b and 'weights still sum to 8760' in b
    assert "R.M.base_build" not in b and 'M.base_build = ml_base_build' in inspect.getsource(R.build_rearch)


# ------------------------------------------------------------------------------------------------ QA-GEOGRAPHY
def test_qa_geography():
    mp = rd('dc/MAINLINE_BUS_SITE_POI_MAP.csv')
    assert set(mp.bus) == EPOCH_BUSES
    assert mp.bus_boundary_tie.sum() == 1 and 'Shackelford' in mp[mp.bus_boundary_tie].site.iloc[0]
    ca = rd('grid/COMMITTED_BASE_ASSETS.csv')
    far_west = set(ca.bus0) | set(ca.bus1)
    assert not far_west & EPOCH_BUSES                                     # Far West project buses are not AIDC buses
    poi = rd('poi/GREAL_POI_ASSUMPTIONS.csv')
    assert not poi.site_name.str.contains('Reeves|Pecos|Kaufman').any()


# ------------------------------------------------------------------------------------------------ QA-BRIDGE
def test_qa_bridge_fields(R):
    for f in ('IT_energized_MW', 'grid_import_MWh', 'BYOP_gen_MWh', 'BYOP_capacity_MW', 'certified_import_MW'):
        assert f in inspect.getsource(R.poi_ledger)
        assert f in inspect.getsource(R.developer_joint) or f == 'IT_energized_MW' or f == 'certified_import_MW'
    assert R.label_mode(10, 0, 0, 5) == 'IS' and R.label_mode(10, 5, 0, 5) == 'GF' and R.label_mode(10, 5, 1, 0) == 'GO_C'
    assert R.label_mode(10, 5, 0, 0) == 'GO_F' and R.label_mode(0, 0, 0, 0) == 'NOT_SERVED'


# ------------------------------------------------------------------------------------------------ QA-PARAM
EXPECT = {'RICE_50DF': (2450, 43.00, 7.00, 8381, 2), 'SOFC_NG_STANDARD': (7953, 37.77, 0.72, 6469, 3),
          'OCGT_AERO': (2275, 9.99, 5.97, 9447, 2), 'WIND_ONSHORE': (1562, 34.57, 0, None, 3),
          'PV_TRACKING': (1342, 23.60, 0, None, 2), 'BESS_4H': (1500, 41.84, 0, None, 1)}


def test_qa_param_tables():
    for nm in ('MAINLINE_V13_TECH_DEFAULTS.csv', 'MAINLINE_V13_GAS_PRICES_2026_2031.csv'):
        assert sha(INP / 'tech' / nm) == sha(WP / nm)                     # machine input = package attachment, byte-identical
    t = rd('tech/MAINLINE_V13_TECH_DEFAULTS.csv').set_index('technology')
    assert set(t.index) == set(EXPECT)
    for k, (cap, fom, vom, hr, lead) in EXPECT.items():
        r = t.loc[k]
        assert (r.capex_2025USD_per_kW_netAC, r.fom_2025USD_per_kW_year, r.vom_2025USD_per_MWh_e, r.reference_lead_years) == (cap, fom, vom, lead)
        assert (hr is None and r.heat_rate_BtuHHV_per_kWh_e != r.heat_rate_BtuHHV_per_kWh_e) or r.heat_rate_BtuHHV_per_kWh_e == hr
    g = rd('tech/MAINLINE_V13_GAS_PRICES_2026_2031.csv')
    assert list(g.year) == list(range(2026, 2032)) and list(g.gas_price_2025USD_per_MMBtu_HHV) == [3.738, 3.513, 3.576, 3.768, 4.443, 4.857]


def test_qa_param_code_uses_v13(R):
    M = R.M
    for c, k in M.V13_ID.items():
        p = M.byop_params(c, 'social')
        cap, fom, vom, hr, lead = EXPECT[k]
        assert p['overnight_per_MW'] == cap * 1000 and abs(p['fom'] - fom * 1000) < 1e-6 and p['lead'] == lead
        assert p['case'] == 'v13'
    assert M.byop_params('RICE', 'social')['r'] == 1.25 and M.byop_params('SOFC_NG', 'social')['r'] == 1.10   # TECH-01 base firm proxy
    assert set(R.ML_TECHS) == set(M.V13_ID)
