"""Mainline v1.3 Stage A static tests (E2) - no LP solver is called anywhere in this file.
Run on L2 from pypsa-usa/workflow:  python -m pytest -q byop/tests/test_mainline_v13.py
(the pure input tests also run locally without pypsa; model tests are skipped when pypsa is missing)."""
from __future__ import annotations

import hashlib, inspect, json, math, re, sys
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
    # audit P0-3: existing (observed energized) / verified approval / planned-unverified are separate rows; only the first
    # two are preapproved; a planned row waits for the procedural earliest grid COD in eq_terms()
    e0 = rd('poi/GREAL_POI_E0_SCHEDULE.csv')
    assert (e0.MW > 0).all()
    cls = e0.evidence_class.str.split(' ').str[0].str.split('/').str[0]
    assert set(cls) == {'VERIFIED_APPROVAL', 'EXISTING_ENERGIZED', 'PLANNED_UNVERIFIED'}
    assert (e0.preapproved == cls.isin(['VERIFIED_APPROVAL', 'EXISTING_ENERGIZED'])).all()
    tl = rd('dc/EPOCH_TX_TIMELINE_EVIDENCE.csv')
    st = rd('dc/EPOCH_TX_SITES_TAMU64.csv').set_index('site')
    for r in e0[cls == 'EXISTING_ENERGIZED'].itertuples():       # existing <= observed operational IT - end-2025 stock
        obs = tl[(tl.site == r.site) & tl.observed_by_as_of].IT_MW.max()
        assert r.MW <= (obs - st.IT_MW_2025[r.site]) * 1.1567 + 0.1, r.site
    assert not e0.site.isin(['OpenAI Stargate Shackelford', 'Crusoe Abilene Expansion']).any()   # ML13-02: upgrade path only
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


# ------------------------------------------------------------------------------------------------ audit P0 fixes (2026-10-21)
def test_p0_1_inherited_ramp_shed_is_booked(R):
    """synthetic ledger (no network, no solver): inherited-ramp shed enters load_shed / social books once"""
    from types import SimpleNamespace
    M = R.M
    idx = pd.MultiIndex.from_product([M.periods(), pd.date_range('2030-01-01', periods=2, freq='3h')], names=['period', 'timestep'])
    g = pd.DataFrame(dict(carrier=['load_shed', 'load_shed', 'OCGT']), index=['p610 2 load_shed', 'p610 2 inherited_ramp_unserved', 'gas'])
    p = pd.DataFrame(0.0, index=idx, columns=g.index)
    p.loc[(2027, slice(None)), 'p610 2 inherited_ramp_unserved'] = 10.0          # 10 MW in both 2027 snapshots
    n = SimpleNamespace(generators=g, generators_t=SimpleNamespace(p=p), snapshots=idx,
                        snapshot_weightings=pd.DataFrame(dict(generators=1.5), index=idx))
    summ = dict(load_shed_MWh=7.0, load_shed_PV_USD=70.0, social_real_resource_cost_USD=1000.0, social_total_USD=2000.0)
    R.ml_shed_accounting(n, summ)
    pv = 30.0 * M.SHED_COST * M.df(2027, M.CFG['social_r'])
    assert summ['inherited_ramp_unserved_MWh'] == 30.0 and summ['native_background_unserved_MWh'] == 7.0
    assert summ['load_shed_MWh'] == 37.0 and abs(summ['load_shed_PV_USD'] - (70.0 + pv)) < 1e-6
    assert abs(summ['social_real_resource_cost_USD'] - (1000.0 + pv)) < 1e-6 and abs(summ['social_total_USD'] - (2000.0 + pv)) < 1e-6
    assert 'ml_shed_accounting(n, summ)' in inspect.getsource(R.main)


def test_p0_2_matched_service_in_formal_run(R):
    sc = R.ml_config_scenarios(WF / 'config/config.byop_ercot_mainline.yaml')
    assert set(R.ML_REQUIRED_SCENARIOS) <= set(sc) and 'S3_mS2' in sc
    run = (BY / 'run/run_mainline.sh').read_text(encoding='utf-8')
    line = [l for l in run.splitlines() if l.strip().startswith('run)')][0]
    assert '--scenarios' not in line                                         # formal run uses the config list
    c = (BY / 'post/collect_mainline.py').read_text(encoding='utf-8')
    assert 'matched_service_valid' in c and 'SCIENTIFIC_USE' in c          # Stage B B0: strict 48-key S2_final vs S3_mS2 check


def test_p0_4_stress_certified_offer(R):
    src = inspect.getsource(R.s1_offer)
    assert 'firm_stress' in src and 'stress_mask' in src
    d = inspect.getsource(R.add_dc_poi)
    assert "off.get('firm_stress', firm_mw) / firm_mw" in d                  # dev purchase at stress <= certified
    assert "o_['firm_stress']" in inspect.getsource(R.main)                   # re-offer also updates the certified part
    c = (BY / 'post/collect_mainline.py').read_text(encoding='utf-8')
    assert 's2_public_delivers_developer_plan' in c


def test_p0_5_inherited_ramp_before_s0_calibration(R):
    b = inspect.getsource(R.build_rearch)
    assert b.index('add_inherited_ramp(n)') < b.index('add_s0_calibration(n, scen)')
    assert "n.generators.carrier == 'load_shed', 'marginal_cost'] = S0CAL_SHED" in inspect.getsource(R.add_s0_calibration)


def test_p1_reporting_fields(R):
    src = inspect.getsource(R.poi_ledger)
    for f in ('pclr_trigger_hours_weighted', 'pclr_curtailed_hours_weighted', 'pclr_max_consecutive_sampled_h'):
        assert f in src
    assert "STATE.setdefault('approval_year', {})[f'{base}_exp{p}_fwd']" in inspect.getsource(R.add_line_expansion_tamu)
    assert 'ay[r.name] = int(r.build_year - l_)' in inspect.getsource(R.ml_public_candidates)


# ------------------------------------------------------------------------------------------------ Stage B B0 (2026-10-21)
B0_SITES = ['p600 0', 'p610 2', 'p630 2', 'p630 4', 'p630 5', 'p630 6', 'p630 9', 'p650 0']
B0_YEARS = list(range(2026, 2032))


def _cm():
    import importlib.util
    spec = importlib.util.spec_from_file_location('collect_mainline_b0', BY / 'post/collect_mainline.py')
    cm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cm)
    return cm


def _synthetic_case(tmp, R, n_iter=2, converged=True, drop_key=False, dup_key=False, gap=0.0):
    """synthetic solved case written through the REAL selection code (no network, no solver): iteration k has
    served = 10 k MW IT, cost = 1e9 k USD, public MW = 100 k; S3_mS2 fixes the LAST iteration's service"""
    import json as _j
    SUM, LED, SVC, POIL, UPL, DUA = [], [], [], [], [], []
    base = ['S0', 'S1_EARLIEST', 'S3']
    tags = ['S2'] + [f'S2_it{k}' for k in range(2, n_iter + 1)]
    def add(tag, k):
        SUM.append(dict(scenario=tag, social_real_resource_cost_USD=1e9 * k, load_shed_MWh=0.0))
        POIL.append(pd.DataFrame([dict(scenario=tag, site=s, year=y, requested_IT_MW=100.0, served_IT_MW=10.0 * k, unserved_IT_MW=100 - 10.0 * k,
                                       equipment_total_MW=500.0, total_import_peak_MW=1.0) for s in B0_SITES for y in B0_YEARS]))
        LED.append(pd.DataFrame([dict(scenario=tag, asset_id=f'pub_{tag}', component='Generator', carrier='solar', asset_boundary='UTILITY',
                                      resource_path='public', zone='p610 2', commit_year=2027, build_period=2029, year=2030,
                                      capacity_MW=100.0 * k, social_annuity_USD_per_MW_yr=1.0, private_annuity_USD_per_MW_yr=1.0,
                                      resource_capex_PV_USD=1.0, private_capex_PV_USD=1.0, dispatch_MWh_per_yr=0.0)]))
        for L in (SVC, UPL, DUA):
            L.append(pd.DataFrame([dict(scenario=tag, x=k)]))
    for t in base:
        add(t, 1)
    for k, t in enumerate(tags, start=1):
        add(t, k)
    sel = R.select_s2_final(n_iter, converged, SUM, LED, SVC, POIL, UPL, DUA, tmp)
    m3 = POIL[-1][POIL[-1].scenario == 'S2_final'].assign(scenario='S3_mS2')     # S3_mS2 = last iteration's delivery
    if gap:
        m3.loc[m3.index[0], 'served_IT_MW'] += gap
    if drop_key:
        m3 = m3.iloc[1:]
    if dup_key:
        m3 = pd.concat([m3, m3.iloc[:1]])
    POIL.append(m3)
    SUM.append(dict(scenario='S3_mS2', social_real_resource_cost_USD=0.5e9 * n_iter, load_shed_MWh=0.0))
    pd.DataFrame(SUM).to_csv(tmp / 'scenario_summary.csv', index=False)
    pd.concat(POIL).to_csv(tmp / 'poi_ledger.csv', index=False)
    pd.concat(LED).to_csv(tmp / 'ledger.csv', index=False)
    pd.DataFrame([dict(iteration=k, site=s, year=y, mode='GF', BYOP_capacity_MW=float(k)) for k in range(1, n_iter + 1)
                  for s in B0_SITES for y in B0_YEARS]).to_csv(tmp / 'S2_developer_modes.csv', index=False)
    pd.DataFrame([dict(iteration=k, site=s, year=y, planned_IT_MW=10.0 * k, gap_IT_MW=0.0 if (converged or k < n_iter) else 5.0)
                  for k in range(1, n_iter + 1) for s in B0_SITES for y in B0_YEARS]).to_csv(tmp / 'S2_consistency.csv', index=False)
    chk = dict(true_LP=True, all_optimal=True, no_harm_existing_customers=True, served_le_requested=True, online_IT_monotone=True,
               dc_energy_balance=True)
    (tmp / 'case_manifest.json').write_text(_j.dumps(dict(checks=chk, s2_selection=sel)))
    return sel


def _gate(tmp):
    g = pd.read_csv(tmp / 'MAINLINE_GATE_CHECKS.csv').set_index('check').result
    return g


def test_b0_two_iterations_select_last(R, tmp_path):
    sel = _synthetic_case(tmp_path, R, n_iter=2)
    assert sel == dict(selected_iteration=2, selected_tag='S2_it2', formal_label='S2_final', converged=True)
    _cm().collect(tmp_path)
    sm = pd.read_csv(tmp_path / 'MAINLINE_SCENARIO_SUMMARY.csv')
    assert set(sm.scenario) == {'S0', 'S1_EARLIEST', 'S3', 'S2_final', 'S3_mS2'}                # raw S2 / S2_it2 not formal
    assert float(sm[sm.scenario == 'S2_final'].social_real_resource_cost_USD.iloc[0]) == 2e9           # cost from iteration 2
    dl = pd.read_csv(tmp_path / 'MAINLINE_BUS_DELIVERY_AND_DELAY.csv')
    assert set(dl.scenario) == {'S0', 'S1_EARLIEST', 'S3', 'S2_final', 'S3_mS2'} and (dl[dl.scenario == 'S2_final'].served_IT_MW == 20.0).all()
    inv = pd.read_csv(tmp_path / 'MAINLINE_PUBLIC_INVESTMENT_DELTA.csv')
    assert float(inv.S2_final.sum()) == 200.0 and 'S2' not in inv and 'S2_it2' not in inv                # not summed with iteration 1
    md = pd.read_csv(tmp_path / 'MAINLINE_S2_MODES_TECH.csv')
    assert (md.iteration == 2).all() and len(md) == 48                                                    # developer table of iteration 2
    diag = pd.read_csv(tmp_path / 'MAINLINE_DIAGNOSTIC_S2_ITERATIONS.csv')
    assert set(diag.scenario) == {'S2', 'S2_it2'}
    ms = pd.read_csv(tmp_path / 'MAINLINE_MATCHED_SERVICE_COST.csv').iloc[0]
    assert ms.gap_status == 'VALID' and ms.S2_final_social_real_USD == 2e9 and ms.matched_service_max_abs_gap_IT_MW == 0.0
    g = _gate(tmp_path)
    assert g['SCIENTIFIC_USE'] == 'ALLOWED' and str(g['selected_S2_iteration']) == '2' and str(g['matched_service_48_keys_present']) == 'True'


def test_b0_single_iteration_unchanged(R, tmp_path):
    sel = _synthetic_case(tmp_path, R, n_iter=1)
    assert sel['selected_tag'] == 'S2' and sel['selected_iteration'] == 1
    _cm().collect(tmp_path)
    sm = pd.read_csv(tmp_path / 'MAINLINE_SCENARIO_SUMMARY.csv').set_index('scenario')
    raw = pd.read_csv(tmp_path / 'scenario_summary.csv').set_index('scenario')
    assert sm.social_real_resource_cost_USD['S2_final'] == raw.social_real_resource_cost_USD['S2']      # identical to the one round
    assert _gate(tmp_path)['SCIENTIFIC_USE'] == 'ALLOWED'


@pytest.mark.parametrize('kw, why', [(dict(drop_key=True), 'matched_service_48_keys_present'),
                                     (dict(dup_key=True), 'matched_service_keys_unique'),
                                     (dict(gap=0.6), 'matched_service_valid'),
                                     (dict(converged=False), 's2_converged')])
def test_b0_blocked_cases(R, tmp_path, kw, why):
    _synthetic_case(tmp_path, R, n_iter=3 if 'converged' in kw else 2, **kw)
    _cm().collect(tmp_path)
    g = _gate(tmp_path)
    assert g['SCIENTIFIC_USE'].startswith('BLOCKED') and why in g['SCIENTIFIC_USE']
    if 'converged' not in kw:
        assert pd.read_csv(tmp_path / 'MAINLINE_MATCHED_SERVICE_COST.csv').gap_status.iloc[0] == 'INVALID_DIAGNOSTIC_ONLY'


def test_b0_missing_check_is_not_a_pass(R, tmp_path):
    import json as _j
    _synthetic_case(tmp_path, R, n_iter=1)
    m = _j.loads((tmp_path / 'case_manifest.json').read_text())
    m['checks']['no_harm_existing_customers'] = None                                       # missing -> not a pass
    (tmp_path / 'case_manifest.json').write_text(_j.dumps(m))
    _cm().collect(tmp_path)
    assert 'no_harm_existing_customers' in _gate(tmp_path)['SCIENTIFIC_USE']


def test_b0_pilot_s01_is_partial(R, tmp_path):
    import json as _j
    pd.DataFrame([dict(scenario=s, social_real_resource_cost_USD=1.0) for s in ('S0', 'S1_EARLIEST')]).to_csv(tmp_path / 'scenario_summary.csv', index=False)
    (tmp_path / 'case_manifest.json').write_text(_j.dumps(dict(checks=dict(true_LP=True, all_optimal=True, no_harm_existing_customers=True,
                                                                          served_le_requested=True, online_IT_monotone=True))))
    _cm().collect(tmp_path)
    g = _gate(tmp_path)
    assert g['phase'] == 'PARTIAL_PILOT' and g['SCIENTIFIC_USE'].startswith('PARTIAL_PILOT')


def test_b0_run_entry_command_assembly():
    """DRY=1: commands only; pilot entries carry no --attribution; pilot_s01 = S0 S1_EARLIEST; pilot_core = config list"""
    import shutil, subprocess
    bash = shutil.which('bash')
    if bash is None:
        pytest.skip('bash not available')
    def cmd(stage):
        r = subprocess.run([bash, str(BY / 'run/run_mainline.sh'), stage], capture_output=True, text=True, env={**__import__('os').environ, 'DRY': '1'})
        return [l for l in r.stdout.splitlines() if l.startswith('CMD ')]
    s01, core, attr, full = cmd('pilot_s01'), cmd('pilot_core'), cmd('attribution'), cmd('run')
    assert len(s01) == len(core) == len(attr) == len(full) == 1
    assert '--attribution' not in s01[0] and '--scenarios S0 S1_EARLIEST' in s01[0] and '_PILOT_S01' in s01[0]
    assert '--attribution' not in core[0] and '--scenarios' not in core[0] and '_PILOT_CORE' in core[0]
    assert '--attribution' in attr[0] and '--attribution' in full[0]
    outs = {c.split('--out ')[1].split()[0] for c in s01 + core + attr + full}
    assert len(outs) == 4                                                                   # separate case directories
    for c in s01 + core + attr + full:
        assert '--mainline' in c and '--erm-cal' in c and '--s0-cal-file' in c


# ------------------------------------------------------------------------------------------------ Stage B2 F1 / F2-b (2026-10-21)
class _FakeGM:
    """records setParam; getParamInfo returns (name, type, current, ...) like gurobipy; optimize is never called"""
    def __init__(self):
        self.p = {}
    def setParam(self, k, v):
        self.p[k] = v
    def getParamInfo(self, k):
        return (k, type(self.p[k]), self.p[k], None, None, None)
    def optimize(self):
        raise AssertionError('solver must not be called in tests')


def test_f1_lex_options_consistent(R):
    gm = _FakeGM()
    got = R.gurobi_apply_options(gm, 20)
    want = dict(Method=2, Crossover=0, BarConvTol=1e-5, FeasibilityTol=1e-3, OptimalityTol=1e-4, BarHomogeneous=1)
    assert R.MAINLINE_GUROBI_LP_OPTIONS == want
    assert got == dict(want, Threads=20) and gm.p == dict(want, Threads=20)
    src = inspect.getsource(R.lex_presolve)
    assert src.index('gurobi_apply_options(gm') < src.index('gm.optimize()')       # options set BEFORE the optimize call
    assert "gm.setParam('Threads', M.CFG['threads'])" not in src                   # no Threads-only path left


def test_f1_developer_options_consistent(R):
    o = R.ml_dev_solver_options(8)
    assert {k: o[k] for k in R.MAINLINE_GUROBI_LP_OPTIONS} == R.MAINLINE_GUROBI_LP_OPTIONS and o['Threads'] == 8
    src = inspect.getsource(R.developer_joint)
    assert 'ml_dev_solver_options(' in src and 'BarConvTol=1e-7' not in src


def test_f1_lex_failure_is_logged_before_raise(R):
    src = inspect.getsource(R.lex_presolve)
    assert src.index("Path(STATE['out_dir']") < src.index('raise RuntimeError')
    for f in ('solver_params', 'objective_values', 'ConstrVio', 'status_name', 'n_int'):
        assert f in src


def test_f1_lex_audit_levels(R):
    levels = [dict(stage='A1', year=2028, value=100.0), dict(stage='A2', year=2028, value=0.5),
              dict(stage='A1', year=2029, value=50.0), dict(stage='A2', year=2029, value=0.0, flag='LEXIMIN_ZERO_LOCK')]
    elig = [dict(year=2028, R={'a': 80.0, 'b': 40.0}), dict(year=2029, R={'a': 30.0, 'b': 20.0})]
    ok = R.lex_audit(levels, {('a', 2028): 60.0, ('b', 2028): 40.0, ('a', 2029): 30.0, ('b', 2029): 20.0}, elig)
    assert all(r['satisfied'] for r in ok) and len(ok) == 6
    bad = R.lex_audit(levels, {('a', 2028): 39.0, ('b', 2028): 60.9, ('a', 2029): 30.0, ('b', 2029): 20.0}, elig)
    f = {(r['stage'], r['year'], r['site']): r['satisfied'] for r in bad}
    assert f[('A1', 2028, 'ALL')] is False and f[('A2', 2028, 'a')] is False and f[('A2', 2029, 'a')] is True   # zero lock not imposed


def test_f2_mainline_voll_only(R):
    assert R.ML_VOLL['F2_mainline_VOLL_USD_MWh'] == 35685.0 and R.ML_VOLL['VOLL_source_year'] == 2024
    assert R.M.SHED_COST == 1e4                                     # non-mainline default untouched until configure_mainline
    src = inspect.getsource(R.configure_mainline)
    assert "M.SHED_COST = ML_VOLL['F2_mainline_VOLL_USD_MWh']" in src
    assert src.index('M.SHED_COST =') < src.index('SITES[r.site_id]')      # before any DC / load_shed object is built
    assert R.S0CAL_SHED == 1e8 and R.S0CAL_COST == 1e7               # B1 calibration constants kept


def test_f2_shed_books_once(R):
    from types import SimpleNamespace
    M = R.M
    old = M.SHED_COST
    try:
        M.SHED_COST = 35685.0
        idx = pd.MultiIndex.from_product([M.periods(), pd.date_range('2030-01-01', periods=2, freq='3h')], names=['period', 'timestep'])
        g = pd.DataFrame(dict(carrier=['load_shed', 'load_shed']), index=['p630 2 load_shed', 'p630 2 inherited_ramp_unserved'])
        p = pd.DataFrame(0.0, index=idx, columns=g.index)
        p.loc[(2028, slice(None)), 'p630 2 inherited_ramp_unserved'] = 4.0
        n = SimpleNamespace(generators=g, generators_t=SimpleNamespace(p=p), snapshots=idx,
                            snapshot_weightings=pd.DataFrame(dict(generators=3.0), index=idx))
        nat_pv = 5.0 * 35685.0 * M.df(2027, M.CFG['social_r'])         # v240 native book at the same price
        summ = dict(load_shed_MWh=5.0, load_shed_PV_USD=nat_pv, social_real_resource_cost_USD=1e6 + nat_pv, social_total_USD=2e6 + nat_pv)
        R.ml_shed_accounting(n, summ)
        inh_pv = 24.0 * 35685.0 * M.df(2028, M.CFG['social_r'])
        assert summ['inherited_ramp_unserved_MWh'] == 24.0 and abs(summ['inherited_ramp_unserved_PV_USD'] - inh_pv) < 1e-6
        assert abs(summ['load_shed_PV_USD'] - (nat_pv + inh_pv)) < 1e-6
        assert abs(summ['social_total_USD'] - (2e6 + nat_pv + inh_pv)) < 1e-6
        assert abs(summ['load_shed_PV_USD'] / M.SHED_COST * 35685.0 - summ['load_shed_PV_USD']) < 1e-6   # VOLL report column = book
    finally:
        M.SHED_COST = old
    main_src = inspect.getsource(R.main)
    assert not re.search(r"social_\w+\s*\+=\s*summ\['existing_customer_shed_loss_VOLL", main_src)   # report-only column


def test_f2_pilot_fix_command():
    import os, shutil, subprocess
    bash = shutil.which('bash')
    if bash is None:
        pytest.skip('bash not available')
    r = subprocess.run([bash, str(BY / 'run/run_mainline.sh'), 'pilot_s01_fix'], capture_output=True, text=True, env={**os.environ, 'DRY': '1'})
    c = [l for l in r.stdout.splitlines() if l.startswith('CMD ')]
    assert len(c) == 1 and '--scenarios S0 S1_EARLIEST' in c[0] and '--attribution' not in c[0]
    assert '--out ' in c[0] and c[0].split('--out ')[1].split()[0].endswith('MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1')
    assert 'MAINLINE_V13_GREAL_MID_ERMCAL/erm02_calibration.json' in c[0] and 'MAINLINE_V13_GREAL_MID_S0CAL/S0_CALIBRATION.csv' in c[0]


def test_f2_gate_refuses_after_reset(R):
    g = R.mainline_gate(WF / 'config/config.byop_ercot_mainline.yaml')
    assert g['approved'] is False and 'run_authorization=NOT_APPROVED' in g['reasons']


def test_f2_b1_inputs_unchanged():
    b1 = WF / 'results/BYOP/mainline'
    for rel, h in (('MAINLINE_V13_GREAL_MID_ERMCAL/erm02_calibration.json', '7d0c02f1245ebba31d26cb303cd154600e0a6626853d7d2c2910a1a268807a19'),
                   ('MAINLINE_V13_GREAL_MID_S0CAL/S0_CALIBRATION.csv', '30bf497ef009f3e120d43f7d6c2995fe0b7d82ffce9d1df2b5629131397454d5')):
        f = b1 / rel
        if not f.exists():
            pytest.skip(f'{rel} not present')
        assert sha(f) == h, rel


# ------------------------------------------------------------------------------------------------ Stage B2.5 (2026-10-21)
def test_b25_cost_book_identity_and_voll_split():
    cm = _cm()
    s = pd.DataFrame([dict(scenario='S2_final', public_resource_capex_PV_USD=10.0, byop_resource_capex_PV_USD=5.0, system_operating_PV_USD=20.0,
                           byop_fuel_PV_USD=3.0, load_shed_PV_USD=7.0, social_real_resource_cost_USD=42.0, social_delay_loss_PV_USD=1.0,
                           curtailment_loss_PV_USD=0.5, interruption_loss_PV_USD=0.5, social_total_USD=44.0, transfer_energy_PV_social_USD=99.0)]).set_index('scenario')
    cb = cm.cost_book_decomposition(s).iloc[0]
    assert cb.physical_resource_spending_proxy_PV_USD == 35.0 and cb.existing_customer_unserved_loss_PV_USD == 7.0
    assert cb.identity_check == 'PASS' and cb.transfer_energy_payment_PV_USD_not_added == 99.0      # transfer listed, not added
    bad = s.copy(); bad.loc['S2_final', 'social_real_resource_cost_USD'] = 50.0                       # broken identity -> FAIL
    assert cm.cost_book_decomposition(bad).iloc[0].identity_check == 'FAIL'


@pytest.mark.parametrize('chk_mod, phase, tech_pass', [
    ({}, 'PARTIAL_PILOT', True),                                            # S0 shed + no-harm PASS -> exploratory with flags
    ({'all_optimal': False}, 'PARTIAL_PILOT', False),                       # any LP not optimal -> BLOCKED
    ({'no_harm_existing_customers': False}, 'PARTIAL_PILOT', False),        # no-harm FAIL -> BLOCKED
    ({'dc_energy_balance': None}, 'PARTIAL_PILOT', False),                  # missing field is not a pass
    ({'s2_converged': True, 's2_public_delivers_developer_plan': True, 'matched_service_valid': False}, 'CORE', False),   # 48 keys broken
    ({'s2_converged': False, 's2_public_delivers_developer_plan': True, 'matched_service_valid': True}, 'CORE', False),   # S2 not converged
    ({'s2_converged': True, 's2_public_delivers_developer_plan': True, 'matched_service_valid': True}, 'CORE', True)])
def test_b25_science_layers(chk_mod, phase, tech_pass):
    cm = _cm()
    chk = dict(true_LP=True, all_optimal=True, no_harm_existing_customers=True, served_le_requested=True, online_IT_monotone=True,
               dc_energy_balance=True, poi_flow_le_equipment=True, no_service_before_grid_or_byop=True, lex_presolve_optimal=True,
               no_load_shed=False)
    chk.update(chk_mod)
    flags = dict(ERM_FIRST_YEAR_METHOD_FLAG='ON (105.22 MW_IT 2026 short, ERM binding)', S0_RELIABILITY_REVIEW_REQUIRED='ON (total 11874.5 MWh)',
                 S0CAL_LINE_FLOWS='PENDING_DIAGNOSTIC_EXPORT')
    L = cm.science_layers(chk, phase, flags)
    if tech_pass:
        assert L['TECHNICAL_GATE'] == 'PASS' and L['EXPLORATORY_USE'] == 'PERMITTED_WITH_METHOD_FLAGS'
        assert L['FINAL_SCIENTIFIC_USE'] == 'PENDING_METHOD_VALIDATION'                  # never ALLOWED automatically
    else:
        assert L['TECHNICAL_GATE'].startswith('FAIL') and L['EXPLORATORY_USE'] == 'BLOCKED' and L['FINAL_SCIENTIFIC_USE'] == 'BLOCKED'
    assert 'no_load_shed' not in cm.TECH_REQUIRED and chk['no_load_shed'] is False       # raw FAIL kept, not a technical gate item
    if phase == 'PARTIAL_PILOT':
        assert not any(k in L['TECHNICAL_GATE'] for k in cm.TECH_REQUIRED_CORE)          # CORE-only items not required in B2


def test_b25_collect_keeps_legacy_and_adds_layers(R, tmp_path):
    _synthetic_case(tmp_path, R, n_iter=2)
    m = json.loads((tmp_path / 'case_manifest.json').read_text())
    m['checks'].update(poi_flow_le_equipment=True, no_service_before_grid_or_byop=True, lex_presolve_optimal=True, no_load_shed=False)
    (tmp_path / 'case_manifest.json').write_text(json.dumps(m))
    _cm().collect(tmp_path)
    g = _gate(tmp_path)
    assert g['SCIENTIFIC_USE'].startswith('BLOCKED') and 'no_load_shed' in g['SCIENTIFIC_USE']     # legacy column unchanged
    assert g['TECHNICAL_GATE'] == 'PASS' and g['EXPLORATORY_USE'].startswith('PERMITTED') and g['FINAL_SCIENTIFIC_USE'] != 'ALLOWED'
    assert (tmp_path / 'MAINLINE_COST_BOOK_DECOMPOSITION.csv').exists()


def test_b25_s0cal_flow_summary(R):
    idx = pd.MultiIndex.from_product([[2028], pd.date_range('2030-01-01', periods=4, freq='3h')], names=['period', 'timestep'])
    links = pd.DataFrame(dict(carrier=['AC_s0cal'] * 2 + ['AC'], p_nom=[100.0, 100.0, 50.0], bus0=['p630 2', 'p630 5', 'x'], bus1=['p630 5', 'p630 2', 'y']),
                         index=['S0CAL_TL73_fwd', 'S0CAL_TL73_rev', 'other'])
    p0 = pd.DataFrame(dict(S0CAL_TL73_fwd=[100.0, 50.0, 0.0, 0.0], S0CAL_TL73_rev=[0.0, 0.0, 80.0, 0.0]), index=idx)
    t = R.s0cal_flow_summary(links, p0, pd.Series(2.0, index=idx), ['p630 2'], 'S1_EARLIEST')
    r = t.iloc[0]
    assert len(t) == 1 and r.line == 'TL73' and r.max_fwd_MW == 100.0 and r.max_rev_MW == 80.0 and r.max_utilisation == 1.0
    assert r.full_load_hours_weighted == 2.0 and r.aidc_adjacent                       # directions not summed into a net capacity
    src = inspect.getsource(R.ml_export_flows)
    assert 'add_constraints' not in src and 'n.model' not in src                       # output-only
    assert 'ml_export_flows(n, tag, out)' in inspect.getsource(R.main)


def test_b25_b3e_entry_and_dir_guard():
    import os, shutil, subprocess
    run = (BY / 'run/run_mainline.sh').read_text(encoding='utf-8')
    assert 'ls -A $OUT/$name' in run and 'return 5' in run                               # partial data -> refuse
    bash = shutil.which('bash')
    if bash is None:
        pytest.skip('bash not available')
    r = subprocess.run([bash, str(BY / 'run/run_mainline.sh'), 'pilot_core_b3e'], capture_output=True, text=True, env={**os.environ, 'DRY': '1'})
    c = [l for l in r.stdout.splitlines() if l.startswith('CMD ')]
    assert len(c) == 1 and '--scenarios S0 S1_EARLIEST S3 S2 S3_mS2' in c[0] and '--attribution' not in c[0]
    assert c[0].split('--out ')[1].split()[0].endswith('MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1')
    assert 'MAINLINE_V13_GREAL_MID_ERMCAL/erm02_calibration.json' in c[0] and 'MAINLINE_V13_GREAL_MID_S0CAL/S0_CALIBRATION.csv' in c[0]
