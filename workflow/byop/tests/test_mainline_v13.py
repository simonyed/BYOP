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
