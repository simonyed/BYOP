"""AIDC geospatial distribution v1 (work package 2026-10-22) static tests - no LP solver is called anywhere in this file.
Run from pypsa-usa/workflow:  python -m pytest -q byop/tests/test_dynamic_siting.py
GEO-xx in the test names = the QA ids of the work package (§7.2); legacy eight-bus regression next to the dynamic variant.
Model tests (gate, siting switch) are skipped when pypsa is missing."""
from __future__ import annotations

import copy, hashlib, importlib.util, json, re, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
BY = WF / 'byop'
DC, POI = BY / 'inputs/dc', BY / 'inputs/poi'
ROOT = WF.parent
CFG_LEGACY = WF / 'config/config.byop_ercot_mainline.yaml'
CFG_DYN = WF / 'config/config.byop_ercot_mainline_geo_dynamic_v1.yaml'
LEGACY8 = ['p600 0', 'p610 2', 'p630 2', 'p630 4', 'p630 5', 'p630 6', 'p630 9', 'p650 0']
YEARS = list(range(2026, 2036))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, BY / rel)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def B():
    return _load('build_dynamic_siting_inputs', 'build/build_dynamic_siting_inputs.py')


@pytest.fixture(scope='module')
def CFG(B):
    return B.load_cfg(DC / 'MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml')


@pytest.fixture(scope='module')
def RES(B, CFG):
    return B.build(CFG, write=False)


@pytest.fixture(scope='module')
def CM():
    return _load('collect_mainline_geo', 'post/collect_mainline.py')


@pytest.fixture(scope='module')
def R():
    pytest.importorskip('pypsa')
    sys.path.insert(0, str(BY / 'model'))
    import rearch_mech as R_
    return R_


coh = lambda: pd.read_csv(DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv')
legacy = lambda: pd.read_csv(DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv')


# ------------------------------------------------------------------------------------------------ GEO-01 history unchanged
def test_geo01_2025_stock_and_d11_unchanged():
    ramp = pd.read_csv(DC / 'MAINLINE_INHERITED_RAMP_2025.csv')
    assert abs(ramp.inherited_ramp_IT_MW.sum() - 460.73) < 1e-6 and len(ramp) == 5
    st = pd.read_csv(DC / 'EPOCH_TX_SITES_TAMU64.csv')
    assert abs(st[st.ercot].IT_MW_2025_avg.sum() - 140.27) < 0.01               # stays inside the 2025 native load
    c = coh()
    assert (c.IT_MW >= 0).all()
    c26 = c[c.request_year == 2026]
    r26 = c26.groupby(['scenario', 'region_id']).inherited_end2025_ramp_IT_MW_background.sum()
    for sc in ('low', 'mid', 'high'):                                             # D11 never inside the research IT_MW column
        assert abs(r26[sc].sum() - 460.73) < 1e-6
    assert (c[c.request_year > 2026].inherited_end2025_ramp_IT_MW_background == 0).all()


def test_geo01_frozen_files_match_the_b3_case():
    man = json.loads((WF / 'results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1/case_manifest.json').read_text())
    for p in [DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv', DC / 'MAINLINE_INHERITED_RAMP_2025.csv', POI / 'GREAL_POI_E0_SCHEDULE.csv',
              POI / 'GREAL_POI_ASSUMPTIONS.csv']:
        assert man['inputs_sha256'][p.name] == sha(p), p.name                      # legacy inputs = the B3-E run inputs


# ------------------------------------------------------------------------------------------------ GEO-02 annual reconciliation
def test_geo02_reconciliation_30_of_30():
    c = coh()
    tot = pd.read_csv(DC / 'ERCOT_DC_TOTALS_2026_2035.csv').set_index(['scenario', 'year']).new_IT_MW
    rec = pd.read_csv(DC / 'MAINLINE_AIDC_RECONCILIATION_GEO_DYNAMIC_V1.csv')
    assert len(rec) == 30 and (rec.check == 'PASS').all()
    n = 0
    for (sc, y), g in c.groupby(['scenario', 'request_year']):
        H = 460.73 if y == 2026 else 0.0
        assert abs(g.IT_MW.sum() + H - tot[(sc, y)]) < 1e-4, (sc, y)
        assert abs(g.verified_2026plus_increment_IT_MW.sum() + g.forecast_reallocated_increment_IT_MW.sum() - g.IT_MW.sum()) < 1e-6
        n += 1
    assert n == 30
    assert abs(c[c.scenario == 'mid'].IT_MW.sum() - 4567.903) < 1e-3


# ------------------------------------------------------------------------------------------------ GEO-03 2026 = Epoch
def test_geo03_2026_keeps_epoch_layout():
    c, o = coh(), legacy()
    m = c[c.request_year == 2026].merge(o[o.request_year == 2026][['scenario', 'region_id', 'IT_MW']], on=['scenario', 'region_id'], how='left',
                                        suffixes=('', '_old'))
    assert (m.IT_MW - m.IT_MW_old.fillna(0.0)).abs().max() < 2e-4                 # only the logged 4-decimal legacy rounding
    assert (m[~m.region_id.isin(LEGACY8)].IT_MW == 0).all()                         # no new bus in 2026
    assert (m[m.region_id == 'p630 4'].IT_MW == 0).all()                            # Shackelford research growth 2026 stays 0
    rr = pd.read_csv(DC / 'ROUNDING_RECONCILIATION_GEO_DYNAMIC_V1.csv')
    assert set(rr.year) <= {2026} and (rr.gap_before_MW.abs() < 1e-3).all()


# ------------------------------------------------------------------------------------------------ GEO-04 locked vs forecast
def test_geo04_only_reviewed_items_are_locked(CFG):
    q = pd.read_csv(DC / 'MAINLINE_SITE_CLASSIFICATION_GEO_DYNAMIC_V1.csv')
    lk = q[q.classification != 'FORECAST_REALLOCATABLE']
    assert set(zip(lk.site, lk.epoch_year)) == {(r['site'], r['epoch_year']) for r in CFG['locked_verified']}
    assert abs(lk.locked_IT_MW.sum() - 387.0) < 1e-9
    assert set(q[q.epoch_year >= 2027].classification) == {'FORECAST_REALLOCATABLE'}  # no future Epoch date locked
    assert not any('E0' in str(r['evidence']) for r in CFG['locked_verified'])        # E0 equipment never locks demand


def test_geo04_locked_amounts_stay_on_bus_and_year(RES):
    svc = pd.read_csv(DC / 'EPOCH_SITE_SERVICE_TAMU64.csv')
    q = RES['classification'].set_index(['site', 'epoch_year']).lock_share
    svc['lk'] = svc.served_IT_MW * [q.get((s, e), 0.0) for s, e in zip(svc.site, svc.epoch_year)]
    exp = svc[svc.year > 2026].groupby(['scenario', 'year', 'bus']).lk.sum()
    w = RES['weights'].set_index(['scenario', 'year', 'bus']).verified_2026plus_increment_IT_MW
    for k, v in exp.items():
        assert abs(w[k] - v) < 1e-9, k
        assert RES['weights'].set_index(['scenario', 'year', 'bus']).new_research_IT_MW[k] >= v - 1e-9


# ------------------------------------------------------------------------------------------------ GEO-05 weights
def test_geo05_weights_normalised(RES, CFG):
    W = RES['weights']
    assert not W.isna().any().any() and (W[['w', 'E_share', 'A_share', 'P_share', 'new_research_IT_MW']] >= -1e-12).all().all()
    s = W.groupby(['scenario', 'year']).agg(w=('w', 'sum'), a=('A_share', 'sum'), p=('P_share', 'sum'))
    assert np.allclose(s.w, 1.0) and np.allclose(s.a, 1.0) and np.allclose(s.p, 1.0)
    assert set(W.scenario) == {'low', 'mid', 'high'} and set(W.year) == set(YEARS)
    assert set(W.bus) == set(RES['buses'])
    for y in YEARS:
        mx = W[W.year == y].iloc[0]
        cfgm = [r for r in CFG['mix_weights'] if r['from'] <= y <= r['to']][0]
        assert (mx.alpha_cfg, mx.beta_cfg, mx.gamma_cfg) == (cfgm['epoch'], cfgm['atlas'], cfgm['projected'])
    el = RES['eligibility']
    for c in ('P_g0_only', 'P_g50_only', 'P_main_g0_25_g50_75'):
        assert abs(el[c].sum() - 1.0) < 1e-9                                       # g0 / g50 normalised separately
    assert np.allclose(el.P_main_g0_25_g50_75, (0.25 * el.P_g0_only + 0.75 * el.P_g50_only) / (0.25 * el.P_g0_only + 0.75 * el.P_g50_only).sum())


def test_geo05_candidate_set(RES):
    el = RES['eligibility']
    assert set(LEGACY8) <= set(RES['buses'])                                        # all Epoch buses protected
    ne = el[~el.src_epoch]
    assert (((ne.q_x_mid_research_total_IT_MW >= 36.0) & ~ne.crypto_only) == ne.eligible).all()
    assert not el[el.crypto_only].eligible.any()
    assert len(el) == 37 and RES['n_buses'] == 16


# ------------------------------------------------------------------------------------------------ edge cases (§7.3.3 / 4)
def test_edge_zero_source_drops_out(B):
    E = pd.Series({'a': 1.0, 'b': 0.0}); A = pd.Series({'a': 0.0, 'b': 0.0}); P = pd.Series({'a': 0.0, 'b': 3.0})
    w, used = B.mixed_weights(E, A, P, dict(epoch=0.5, atlas=0.25, projected=0.25), ['a', 'b'])
    assert used['atlas'] == 0.0 and abs(sum(used.values()) - 1) < 1e-12 and abs(w.sum() - 1) < 1e-12
    w2, _ = B.mixed_weights(E, A, P * 0, dict(epoch=0.3, atlas=0.2, projected=0.5), ['a', 'b'])   # PNNL all zero
    assert w2['a'] == 1.0


def test_edge_candidate_without_atlas_and_zero_years(RES):
    W = RES['weights']
    b = [x for x in RES['buses'] if not RES['eligibility'].src_atlas_noncrypto[x]]
    assert b and (W[W.bus.isin(b)].A_share == 0).all()
    assert (W[W.year == 2026].groupby('bus').new_research_IT_MW.sum() == 0).sum() >= 8       # many buses at 0 in 2026


def test_edge_locked_conflict_and_bad_inputs(B):
    w = pd.Series({'a': 0.5, 'b': 0.5})
    lk, fc, R = B.allocate(100.0, 0.0, {'a': 99.0}, w)
    assert abs(lk.sum() + fc.sum() - 100.0) < 1e-12 and R == pytest.approx(1.0)     # locked takes most of the year
    with pytest.raises(B.DataConflict):
        B.allocate(100.0, 10.0, {'a': 95.0}, w)                                      # locked + D11 > total -> stop
    with pytest.raises(ValueError):
        B.normalise(pd.Series({'a': -1.0, 'b': 2.0}))
    with pytest.raises(ValueError):
        B.normalise(pd.Series({'a': np.nan, 'b': 2.0}))                              # missing coordinate -> NaN share
    net = pd.DataFrame(dict(reeds_zone=['p63', 'p40']), index=['p630 3', 'X 1'])
    with pytest.raises(B.DataConflict):
        B.check_ercot_buses(['p630 3', 'X 1'], net)                                  # outside ERCOT
    with pytest.raises(B.DataConflict):
        B.check_ercot_buses(['p999 9'], net)


def test_edge_heavy_locks_follow_scenario_service(B, CFG):
    """locked capacity keeps the bus and the year in which the approved scenario serves it (EPOCH_SITE_SERVICE), so a lock
    can take a whole year's research growth but never more; a lock larger than its Epoch bucket is refused"""
    c = copy.deepcopy(CFG)
    c['locked_verified'] = list(c['locked_verified']) + [dict(site='OpenAI Stargate Shackelford', epoch_year=2027, IT_MW=420.0, evidence='test'),
                                                          dict(site='OpenAI Stargate Shackelford', epoch_year=2028, IT_MW=980.0, evidence='test'),
                                                          dict(site='Crusoe Abilene Expansion', epoch_year=2027, IT_MW=672.0, evidence='test')]
    r = B.build(c, write=False)
    assert (r['rec'].check == 'PASS').all() and (r['rec'].forecast_residual_IT_MW >= -1e-9).all()
    assert (r['rec'].locked_verified_IT_MW <= r['rec'].ERCOT_approved_new_IT_MW - r['rec'].D11_inherited_IT_MW + 1e-6).all()
    c['locked_verified'] = [dict(site='Vantage TX1', epoch_year=2026, IT_MW=40.0, evidence='test')]      # bucket is 32 MW IT
    with pytest.raises(B.DataConflict):
        B.build(c, write=False)
    c['locked_verified'] = [dict(site='Vantage TX1', epoch_year=2031, IT_MW=1.0, evidence='test')]       # no such bucket
    with pytest.raises(B.DataConflict):
        B.build(c, write=False)


def test_edge_source_switch_changes_allocation_not_base_files(B, CFG, RES):
    before = {p.name: sha(p) for p in DC.glob('*GEO_DYNAMIC_V1*')}
    c = copy.deepcopy(CFG)
    for r in c['mix_weights']:
        if r['from'] > 2026:
            r['projected'] += r['atlas']; r['atlas'] = 0.0
    alt = B.build(c, write=False)
    assert not np.allclose(alt['weights'].new_research_IT_MW, RES['weights'].new_research_IT_MW)
    assert (alt['rec'].check == 'PASS').all()
    assert before == {p.name: sha(p) for p in DC.glob('*GEO_DYNAMIC_V1*')}


# ------------------------------------------------------------------------------------------------ GEO-06 provenance / filters
def test_geo06_provenance_and_filters():
    prov = json.loads((DC / 'PNNL_PROVENANCE.json').read_text())
    assert prov['atlas']['licence'].startswith('ODbL') and prov['projected']['licence'] == 'CC BY 4.0'
    assert '10.57931/3017294' in prov['atlas']['doi'] and '10.57931/3020186' in prov['projected']['doi']
    for o, h in prov['outputs'].items():
        assert sha(DC / o) == h, o
    at = pd.read_csv(DC / 'PNNL_ATLAS_TX_SITES_TAMU64.csv', dtype={'id': str})
    ex = at[at.crypto_flag == 'CRYPTO_CHECKED_EXCLUDED']
    assert set(ex.name) == {'Riot Corsiana', 'Riot Rockdale', 'MARA Data Center', 'IONIC Digital Cedarvale'}
    assert set(ex.id) == {'01450422488', '01450418654', '01301559332', '01455361421'}
    assert (at.crypto_flag == 'CRYPTO_SCREEN_REVIEW').sum() == 0
    assert set(at.dup_class) <= {'UNIQUE', 'EXPLICIT_DUP_CONTAINED', 'SUSPECT_SAME_CAMPUS'}
    assert len(at) == 127 and at.site_cluster.nunique() == prov['counts']['atlas_site_clusters']
    rv = pd.read_csv(DC / 'PNNL_SPATIAL_MAPPING_REVIEW.csv')
    assert rv.note.str.contains('no POI contract|nearest kept').all()


def test_geo06_no_growth_rate_or_score_reweighting(B):
    import inspect
    src = inspect.getsource(B)
    assert 'weighted_siting_score' not in src and 'growth_rate' not in src                 # P = IT MW shares only, no 15 %/yr
    assert 'IT_MW.sum()' in inspect.getsource(B.projected_shares)
    pr = pd.read_csv(DC / 'PNNL_PROJECTED_HIGHER_TX_TAMU64.csv')
    assert set(pr.market_gravity_weight) == {0, 25, 50, 75, 100}


# ------------------------------------------------------------------------------------------------ GEO-07 / 08 POI
def test_geo07_new_bus_poi_rows():
    p = pd.read_csv(POI / 'GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv')
    e0 = pd.read_csv(POI / 'GREAL_POI_E0_SCHEDULE.csv')
    new = p[p.bus_class == 'PNNL_NEW_SITE']
    assert len(new) == 8 and (new.E0_total_MW == 0).all() and not set(new.bus) & set(e0.bus)
    assert (new.gas_evidence_level == 'L2').all() and new.ev_E0.str.contains('NOT a statement that the real POI capacity is zero').all()
    assert (new.earliest_grid_COD_base == 2028.0).all() and (new.poi_upgrade_max_MW == 2000.0).all()
    assert set(p.bus) == set(coh().region_id)
    rk = pd.read_csv(DC / 'MAINLINE_NEW_BUS_POI_RISK_GEO_DYNAMIC_V1.csv')
    nr = rk[rk.bus_class == 'PNNL_NEW_SITE']
    assert nr[nr.year_first_forecast_MW_mid < 2028].risk_flags.str.contains('POI_PROXY_MAY_DRIVE_DELAY').all()


def test_geo08_epoch_poi_evidence_unchanged():
    old = pd.read_csv(POI / 'GREAL_POI_ASSUMPTIONS.csv').set_index('bus')
    new = pd.read_csv(POI / 'GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv').set_index('bus')
    derived = {'research_IT_MW_2026_2031_mid', 'research_facility_MW_2031_mid', 'pclr_conditional_MW', 'onsite_renewable_cap_MW'}
    for c in old.columns:
        if c in derived:
            continue
        a, b = old[c], new.loc[old.index, c]
        if pd.api.types.is_numeric_dtype(a):
            assert np.allclose(a.astype(float), b.astype(float), atol=1e-6, equal_nan=True), c     # CSV written at 9 decimals
        else:
            assert ((a == b) | (a.isna() & b.isna())).all(), c
    d = pd.read_csv(POI / 'MAINLINE_POI_DERIVED_DELTA_GEO_DYNAMIC_V1.csv')
    assert len(d) == 32 and set(d.field) == derived and set(d.bus) == set(LEGACY8)


# ------------------------------------------------------------------------------------------------ GEO-09 expected keys
def _poil(keys2, keys3, v3=None):
    a = pd.DataFrame([dict(scenario='S2_final', site=s, year=y, served_IT_MW=5.0) for s, y in keys2])
    b = pd.DataFrame([dict(scenario='S3_mS2', site=s, year=y, served_IT_MW=5.0 if v3 is None else v3) for s, y in keys3])
    return pd.concat([a, b], ignore_index=True)


@pytest.fixture(scope='module')
def EXP(RES):
    return {(b, y) for b in RES['buses'] for y in range(2026, 2032)}


def test_geo09_dynamic_expected_keys(CM, EXP, RES):
    man = dict(mainline=dict(research_buses=RES['buses'], model_years=list(range(2026, 2032))))
    exp, basis = CM.expected_service_keys(man)
    assert exp == EXP and len(exp) == 96 and basis == 'mainline.research_buses'
    k = sorted(EXP)
    ok = CM.matched_service_check(_poil(k, k), exp)
    assert ok['matched_service_valid'] and ok['matched_service_expected_key_count'] == 96 and ok['matched_service_48_keys_present'] is None


@pytest.mark.parametrize('case', ['drop_one', 'dup_one', 'extra_key', 'bad_value', 'both_missing', 'gap'])
def test_geo09_broken_key_sets_never_pass(CM, EXP, case):
    k = sorted(EXP)
    k2, k3, v3 = list(k), list(k), None
    if case == 'drop_one':
        k3 = k3[1:]
    elif case == 'dup_one':
        k3 = k3 + k3[:1]
    elif case == 'extra_key':
        k2, k3 = k2 + [('p999 9', 2026)], k3 + [('p999 9', 2026)]
    elif case == 'bad_value':
        v3 = 'x'
    elif case == 'both_missing':
        k2, k3 = k2[1:], k3[1:]                                                     # both sides lose the same bus-year
    elif case == 'gap':
        v3 = 6.0
    r = CM.matched_service_check(_poil(k2, k3, v3), EXP)
    assert r['matched_service_valid'] is False, case


def test_geo09_legacy_48_regression(CM):
    exp, basis = CM.expected_service_keys({})
    assert len(exp) == 48 and basis == 'legacy eight Epoch buses'
    man = json.loads((WF / 'results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1/case_manifest.json').read_text())
    exp_b3, _ = CM.expected_service_keys(man)
    assert exp_b3 == exp                                                           # B3-E case = 8 x 2026-2031
    poil = pd.read_csv(WF / 'results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1/poi_ledger.csv')
    r = CM.matched_service_check(poil, exp_b3)
    assert r['matched_service_valid'] and r['matched_service_48_keys_present'] is True    # frozen B3-E still valid


# ------------------------------------------------------------------------------------------------ GEO-11 / 12 / 13 switch, gate, manifest
def test_geo11_switch_and_legacy_paths(R):
    s = R.ml_select_siting(CFG_LEGACY)
    assert s['variant'] == 'epoch8_legacy' and R.ML_COH.name == 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv'
    s = R.ml_select_siting(CFG_DYN)
    assert s['variant'] == 'dynamic_pnnl_v1' and R.ML_COH.name.endswith('_GEO_DYNAMIC_V1.csv') and R.ML_POI in R.ML_INPUTS
    R.ml_select_siting(CFG_LEGACY)


def test_geo11_switch_refuses_mixed_paths(R, tmp_path):
    t = CFG_DYN.read_text(encoding='utf-8').replace('MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv', 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv')
    p = tmp_path / 'c.yaml'; p.write_text(t, encoding='utf-8')
    with pytest.raises(SystemExit):
        R.ml_select_siting(p)
    R.ml_select_siting(CFG_LEGACY)


def test_geo10_missing_re_profile_only_skips_in_dynamic_variant(R):
    import inspect
    src = inspect.getsource(R.add_byop_cohorts)
    assert "STATE.setdefault('byop_re_profile_missing', [])" in src and "!= 'epoch8_legacy'" in src     # option absent + flagged
    assert "assert prof is not None" in src                                                             # legacy hard check kept
    assert 'byop_re_profile_missing' in inspect.getsource(R.main)                                        # recorded in the case manifest


def test_geo12_gate_refuses_both_configs(R):
    for c in (CFG_LEGACY, CFG_DYN):
        t = c.read_text(encoding='utf-8')
        assert re.search(r'^  run_authorization: NOT_APPROVED', t, re.M) and re.search(r'^  approved_git_sha: null', t, re.M)
        R.ml_select_siting(c)
        g = R.mainline_gate(c)
        assert g['approved'] is False and 'run_authorization=NOT_APPROVED' in g['reasons']
    R.ml_select_siting(CFG_LEGACY)


def test_geo12_no_new_formal_results():
    d = WF / 'results/BYOP/mainline'
    assert not [p for p in d.glob('MAINLINE_V13_GEO_DYNAMIC*') if (p / 'case_manifest.json').exists()]


def test_geo13_manifest_lists_variant_and_hashes():
    p = ROOT / 'current_work_pckg/AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json'
    if not p.exists():
        pytest.skip('pending manifest not built yet')
    m = json.loads(p.read_text())
    assert m['siting_variant'] == 'dynamic_pnnl_v1' and m['RUN_AUTHORIZATION'] == 'NOT_APPROVED' and m['SOLVER_EXECUTIONS'] == 0
    for rel in ('workflow/byop/inputs/dc/MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv', 'workflow/byop/inputs/poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv',
                'workflow/byop/inputs/dc/MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml'):
        assert m['inputs_sha256'][rel] == sha(ROOT / rel)
    assert m['code_sha256']['workflow/byop/build/build_dynamic_siting_inputs.py'] == sha(ROOT / 'workflow/byop/build/build_dynamic_siting_inputs.py')


# ------------------------------------------------------------------------------------------------ GEO-14 determinism
def test_geo14_rebuild_is_identical(B, CFG):
    a = B.build(CFG, write=False)
    b = B.build(CFG, write=False)
    pd.testing.assert_frame_equal(a['cohorts'], b['cohorts'])
    on_disk = coh()
    assert np.allclose(on_disk.IT_MW.values, a['cohorts'].IT_MW.values, atol=1e-9)
    bm = json.loads((DC / 'MAINLINE_SITING_BUILD_MANIFEST_GEO_DYNAMIC_V1.json').read_text())
    for rel, h in bm['outputs_sha256'].items():
        assert sha(WF / rel) == h, rel
