"""NEXT-10U static tests (no solver): engineering POI inputs, the engineering_cost_v1 model branch, the S0 scientific gate, the private
CIAC / security price of the S2 import right, the three cost books and the gates / budgets of the NEXT-10U configs.
Run on L2 from workflow/:  python -m pytest -q byop/tests/test_next10u_engineering.py
"""
from __future__ import annotations

import hashlib, inspect, json, math, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
for p in ('byop/model', 'byop/build', 'byop/post'):
    sys.path.insert(0, str(WF / p))
import build_engineering_poi_v1 as B  # noqa: E402
import next10u_s0_science as SC  # noqa: E402
import next10u_cost_books as CB  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402
import post_v16_a3_gate as A3G  # noqa: E402
import baseline_registry as BR  # noqa: E402

ENG = WF / 'byop/inputs/poi_eng'
ML_CFG = WF / 'config/config.byop_ercot_mainline_engineering_cost_v1.yaml'
S01 = WF / 'config/config.byop_next10u_s0s1.yaml'
A3 = WF / 'config/config.byop_next10u_a3.yaml'
DATA_OK = all((B.DATA / k).is_file() for k in B.SOURCES)


# ------------------------------------------------------------------------------------------------ H1 inputs
@pytest.mark.skipif(not DATA_OK, reason='engineering data package not on this machine')
def test_sources_pinned_and_rebuild_identical():
    assert B.verify_sources() == []
    res = B.build()
    for f, k in (('ENG_POI_SITES.csv', 'sites'), ('ENG_POI_EQUIPMENT_KNOWN.csv', 'known'), ('ENG_POI_CANDIDATES.csv', 'candidates'),
                 ('ENG_POI_VISIBILITY.csv', 'visibility'), ('ENG_POI_LEAD_COMPONENTS.csv', 'lead')):
        assert res[k].to_csv(index=False, lineterminator='\n') == (ENG / f).read_text(encoding='utf-8'), f


def test_fail_closed_on_changed_source(tmp_path):
    for rel in B.SOURCES:
        p = tmp_path / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'x')
    with pytest.raises(SystemExit):
        B.build(tmp_path)


def test_site_table_has_no_poi_proxy_columns():
    s = pd.read_csv(ENG / 'ENG_POI_SITES.csv')
    assert not set(B.FORBIDDEN) & set(s.columns)
    assert len(s) == 16 and s.site_id.is_unique


def test_equipment_is_not_rights_and_helios_within_approval():
    k = pd.read_csv(ENG / 'ENG_POI_EQUIPMENT_KNOWN.csv')
    s = pd.read_csv(ENG / 'ENG_POI_SITES.csv').set_index('site_id')
    assert 'p610 2' not in set(k.site_id) and s.loc['p610 2', 'approved_capacity_right_MW'] > 900       # Abilene: right, no equipment
    h = k[k.site_id == 'p600 0']
    assert abs(h.MW.sum() - 591.0) < 1e-6 and h.MW.sum() <= 800.0 and sorted(h.COD) == [2026.5, 2027.5]
    assert set(k.evidence_level) <= {'E0', 'E1'}
    # known equipment is never re-bought: new cap = site cap - known
    assert np.allclose(s.new_equipment_cap_MW, (s.site_cumulative_cap_MW - s.known_equipment_MW).clip(lower=0))
    assert np.allclose(s.cap_RIGHTED_MW + s.cap_NEW_REQUEST_MW, s.new_equipment_cap_MW)


def test_cod_is_max_of_parallel_components_never_sum():
    c = pd.read_csv(ENG / 'ENG_POI_CANDIDATES.csv')
    lead = B.TX_WEEKS['base'] / B.WEEKS_PER_YEAR
    g = c[c.engineering_class != 'LOCAL']
    floor = np.where(g.engineering_class == 'NEW_REQUEST', B.BATCH_ZERO_FLOOR, -np.inf)
    assert np.allclose(g.equipment_COD, np.maximum(g.commitment_year + round(lead, 4), floor), atol=1e-4)
    sw = B.SWGR_WEEKS['base'] / B.WEEKS_PER_YEAR
    assert np.all(g.equipment_COD < g.commitment_year + lead + sw - 1e-6)                      # not lead + switchgear
    assert (g.firm_first_full_year == np.ceil(g.equipment_COD - 1e-9)).all()
    assert not (c.lead_component_y == 3.0).any() and not (c.class_cumulative_cap_MW == 2000.0).any()


def test_local_route_disabled_and_rights_class_only_where_approved():
    c = pd.read_csv(ENG / 'ENG_POI_CANDIDATES.csv')
    assert (c[c.engineering_class == 'LOCAL'].enabled == 0).all()
    r = c[(c.engineering_class == 'RIGHTED') & (c.enabled == 1)]
    assert set(r.site_id) == {'p610 2', 'p600 0'} or set(r.site_id) <= {'p610 2', 'p600 0'}


def test_visibility_cap_formula():
    v = pd.read_csv(ENG / 'ENG_POI_VISIBILITY.csv')
    assert np.allclose(v.visible_new_order_cap_MW, (v.announced_facility_MW_cum - v.known_equipment_MW).clip(lower=0), atol=1e-4)
    for s, g in v.groupby('site_id'):
        assert (g.sort_values('commitment_year').announced_facility_MW_cum.diff().dropna() >= -1e-9).all()


# ------------------------------------------------------------------------------------------------ model branch
def test_engineering_config_selects_engineering_inputs_only():
    import rearch_mech as R
    s = R.ml_select_siting(ML_CFG)
    names = [Path(p).name for p in R.ML_INPUTS]
    assert s['poi_model'] == 'engineering_cost_v1' and R.ML['poi_model'] == 'engineering_cost_v1'
    assert 'GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv' not in names and 'GREAL_POI_E0_SCHEDULE.csv' not in names
    assert {'ENG_POI_SITES.csv', 'ENG_POI_EQUIPMENT_KNOWN.csv', 'ENG_POI_CANDIDATES.csv', 'ENG_POI_VISIBILITY.csv'} <= set(names)
    legacy = R.ml_select_siting(WF / 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v17l.yaml')    # legacy branch unchanged
    assert legacy['poi_model'] == 'legacy_proxy' and 'GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv' in [Path(p).name for p in R.ML_INPUTS]
    R.ml_select_siting(ML_CFG)


def test_mixed_config_refused(tmp_path):
    import rearch_mech as R
    d = yaml.safe_load(ML_CFG.read_text(encoding='utf-8'))
    d['inputs']['poi'] = 'byop/inputs/poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv'
    p = tmp_path / 'c.yaml'; p.write_text(yaml.safe_dump(d), encoding='utf-8')
    with pytest.raises(SystemExit):
        R.ml_select_siting(p)
    R.ml_select_siting(ML_CFG)


def test_configure_branch_never_reads_proxy_columns():
    import rearch_mech as R
    src = inspect.getsource(R.ml_eng_sites)
    assert 'poi_upgrade' not in src and 'earliest_grid_COD' not in src and 'E0_total' not in src


def _toy(sites_caps, links):
    import linopy
    import rearch_mech as R
    m = linopy.Model()
    names = [nm for nm, _ in links]
    lnom = m.add_variables(lower=0, coords=[pd.Index(names, name='name')], name='Link-p_nom')
    n = SimpleNamespace(links=pd.DataFrame(dict(p_nom_extendable=[True] * len(names)), index=names))
    R.SITES.clear(); R.STATE['poi_eng'] = {}
    for s, (caps, vis) in sites_caps.items():
        R.SITES[s] = dict(eng_caps=caps, eng_vis=vis)
    for nm, e in links:
        R.STATE['poi_eng'][nm] = e
    rows = R.ml_eng_constraints(n, m, lnom)
    return m, rows


def test_cumulative_and_disclosure_rows_structure():
    links = [(f'POIup s1 NEW_REQUEST q{q}', dict(site='s1', cls='NEW_REQUEST', q=q, cod=q + 3.16, cap=100.0)) for q in (2026, 2027, 2028)] + \
            [('POIup s1 RIGHTED q2026', dict(site='s1', cls='RIGHTED', q=2026, cod=2029.16, cap=50.0))]
    vis = {2026: 30.0, 2027: 60.0, 2028: 90.0}
    m, rows = _toy({'s1': (dict(RIGHTED=50.0, NEW_REQUEST=100.0, total=120.0), vis)}, links)
    cons = set(m.constraints)
    assert {'ENG-cum_RIGHTED_s1', 'ENG-cum_NEW_REQUEST_s1', 'ENG-cum_site_s1', 'ENG-vis_s1_2026', 'ENG-vis_s1_2027', 'ENG-vis_s1_2028'} <= cons
    lab = {nm: int(m['Link-p_nom'].sel(name=nm).labels) for nm, _ in links}
    v26 = set(np.asarray(m.constraints['ENG-vis_s1_2026'].vars).ravel()) - {-1}
    assert v26 == {lab['POIup s1 NEW_REQUEST q2026'], lab['POIup s1 RIGHTED q2026']}      # an undisclosed later order is not in Q=2026
    v28 = set(np.asarray(m.constraints['ENG-vis_s1_2028'].vars).ravel()) - {-1}
    assert v28 == set(lab.values())                                                           # orders are cumulative over q (no re-buy)
    assert float(np.asarray(m.constraints['ENG-vis_s1_2026'].rhs).ravel()[0]) == 30.0
    assert float(np.asarray(m.constraints['ENG-cum_site_s1'].rhs).ravel()[0]) == 120.0


def test_firm_needs_full_year_after_cod():
    import v240_mech as M
    M.CFG.update(periods='annual', start=2026, end=2031, frac_cod=True, firm_full_year=True)
    bp = M.first_period(2029.1622)
    assert bp == 2029 and M.firm_frac(bp, 2029.1622, 2029) == 0.0 and M.firm_frac(bp, 2029.1622, 2030) == 1.0
    assert M.firm_frac(M.first_period(2026.5), 2026.5, 2026) == 0.0 and M.firm_frac(M.first_period(2026.5), 2026.5, 2027) == 1.0


def test_ciac_right_price():
    import rearch_mech as R
    import v240_mech as M
    M.CFG.update(private_wacc=0.07)
    R.SITES.clear()
    R.SITES['s1'] = dict(eng=[1], U_cost=160000.0, E0rows=[dict(MW=100.0, cod=2026.0, pre=True)], proc=2028.0)
    R.STATE['poi_up'] = {'s1': [('POIup s1 NEW_REQUEST q2026', 2029, 2029.1622)]}
    R.STATE['poi_eng'] = {'POIup s1 NEW_REQUEST q2026': dict(site='s1', cls='NEW_REQUEST', q=2026, cod=2029.1622, cap=500.0)}
    R.STATE['dc'] = [dict(zone='s1', period=2030)]
    M.CFG.update(periods='annual', start=2026, end=2031, frac_cod=True, firm_full_year=True)
    n1 = SimpleNamespace(links=pd.DataFrame(dict(p_nom_opt=[300.0]), index=['POIup s1 NEW_REQUEST q2026']))
    df = R.ml_eng_ciac(n1)
    a = M.crf(0.07, R.UPGRADE_LIFE)
    want = 300.0 / 400.0 * (160000.0 * a + R.SECURITY_USD_PER_MW * 0.07 * (2029.1622 - 2026) * a)
    assert abs(R.STATE['ciac_rate'][('s1', 2030)] - want) < 1e-6 and abs(df.new_share.iloc[0] - 0.75) < 1e-12
    assert R.SECURITY_USD_PER_MW == 50000.0        # USD per MW, not per kW


def test_developer_right_priced_only_in_developer_lp():
    import rearch_mech as R
    src = inspect.getsource(R.add_dc_poi)
    assert "STATE.get('ciac_rate'" in src and "carrier='grid_purchase', p_nom_extendable=True" in src
    assert 'ciac' not in inspect.getsource(R.extra_rearch)                 # never in a public / social objective


# ------------------------------------------------------------------------------------------------ S0 scientific gate
def _net(shed_mw, load_mw=1000.0):
    import pypsa
    n = pypsa.Network()
    idx = pd.MultiIndex.from_product([[2026, 2027], pd.date_range('2026-01-01', periods=4, freq='3h')], names=['period', 'timestep'])
    n.set_snapshots(idx); n.investment_periods = [2026, 2027]
    n.snapshot_weightings.loc[:, 'generators'] = 365 * 8 / 4.0 * 3 / 3
    n.add('Bus', 'b'); n.add('Bus', 'DC_x')
    n.add('Load', 'l', bus='b', p_set=load_mw); n.add('Load', 'dc', bus='DC_x', p_set=5000.0)
    n.add('Generator', 'b load_shed', bus='b', carrier='load_shed', p_nom=1e5)
    n.generators_t.p = pd.DataFrame({'b load_shed': shed_mw}, index=n.snapshots)
    return n


def test_s0_science_gate_thresholds():
    ok = SC.evaluate(_net([0.0] * 8))
    assert ok['PASS'] and ok['verdict'] == 'S0_SCIENCE_PASS'
    bad = SC.evaluate(_net([0.0, 0.0, 2.0, 0.0] + [0.0] * 4))           # 2 MW of 1,000 MW peak -> 2e-3 > 1e-3
    assert not bad['PASS'] and not bad['by_year'][0]['peak_ok']
    assert all(r['native_load_MWh'] > 0 for r in ok['by_year'])
    assert ok['by_year'][0]['native_peak_MW'] == 1000.0                    # the DC bus load is not existing-customer load


def test_acceptance_has_science_check():
    src = inspect.getsource(A2G.acceptance)
    assert "chk['s0_science_pass']" in src and "tag == 'S0' and science is not None" in src


# ------------------------------------------------------------------------------------------------ cost books
def test_books_reconcile_on_a_solved_case():
    d = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
    if not (d / 'scenarios/S0/scenario_summary.csv').exists():
        pytest.skip('no solved reference case on this machine')
    r = CB.build(d)
    assert r['checks']['resource_reconciles_with_solver_summary'] and r['checks']['every_asset_in_one_class']
    inc = r['inc']
    a = inc[(inc.scenario == 'S1_EARLIEST') & (inc.asset_class == 'A_DC_DIRECT_INTERCONNECTION')]
    assert float(a.developer_cash_PV_USD.iloc[0]) == float(a.resource_PV_USD.iloc[0])            # CIAC = transfer of the class A resource
    b = r['pay'][r['pay'].asset_id.str.endswith('_ALL')]
    assert (b.payer == 'UNRESOLVED_LEGAL_ALLOCATOR').all()


def test_payment_shares_do_not_change_resource():
    d = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
    if not (d / 'scenarios/S0/scenario_summary.csv').exists():
        pytest.skip('no solved reference case on this machine')
    r = CB.build(d)
    before = r['res'].real_resource_PV_USD.sum()
    old = CB.SECURITY_USD_PER_MW
    try:
        CB.SECURITY_USD_PER_MW = 1e9
        r2 = CB.build(d)
    finally:
        CB.SECURITY_USD_PER_MW = old
    assert r2['res'].real_resource_PV_USD.sum() == before


# ------------------------------------------------------------------------------------------------ configs, gates, budget
def test_configs_and_budget():
    c1, c3 = A2G.load(S01), A3G.load(A3)
    assert c1['stage'] == 'A2' and c3['stage'] == 'A3'
    assert int(c1['max_top_level_optimizer_calls']) + int(c3['max_top_level_optimizer_calls']) <= 40
    assert int(c1['max_retries']) == 0 and int(c3['max_retries']) == 0
    for c in (c1, c3):
        assert c['mainline_config'] == 'config/config.byop_ercot_mainline_engineering_cost_v1.yaml'
        assert c['baseline']['sha256'] == BR.BASE_TAMU_V17L_SHA256
        src = WF.parent / c['authorization_source']
        assert hashlib.sha256(src.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == c['authorization_source_sha256']
    g = c1['s0_science_gate']
    assert g['eens_share_max'] == 1e-5 and g['max_shed_to_peak_max'] == 1e-3
    assert c3['prerequisites'][0]['file'].endswith('next10u_engineering_cost_v1/S0S1/S0_SCIENCE_VERDICT.json')
    assert c3['reference']['dir'] == c1['out_dir'] and c3['out_dir'] != c1['out_dir']


def test_next09_config_untouched_and_held():
    c = A2G.load(WF / 'config/config.byop_post_v17l_s0s1.yaml')
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_git_sha'] is None and c['approved_by'] is None


def test_s0s1_gate_refuses_while_not_approved():
    c = A2G.load(S01)
    if c['run_authorization'] == 'APPROVED':
        pytest.skip('approved')
    g = A2G.check('S0', str(BR.BASE_TAMU_V17L), cfg_path=S01)
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons']
