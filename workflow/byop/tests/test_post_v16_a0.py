"""Post-v1.6 execution package v1.1, A0 static tests: NO solver is ever called (an autouse fixture makes any solve fail).
    python -m pytest -q byop/tests/test_post_v16_a0.py        (from pypsa-usa/workflow; pypsa tests skip without pypsa,
                                                               v1.6-network tests skip without the L2 baseline)"""
from __future__ import annotations

import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
BY = WF / 'byop'
for p in ('model', 'build', 'run', 'post'):
    sys.path.insert(0, str(BY / p))
import byop_paths as BP  # noqa: E402
import post_v16_gate as G  # noqa: E402

CFG = WF / 'config/config.byop_post_v16_a1.yaml'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def eol_layers(p):
    """NEXT-02 A2-FIX-06: raw / LF / CRLF SHA-256 of a text file. The pinned value must equal one of them (same content, any checkout
    EOL); a lone CR or mixed endings make the LF and CRLF layers differ from any clean pin, so a content change is never accepted"""
    b = Path(p).read_bytes()
    lf = b.replace(b'\r\n', b'\n')
    return dict(raw=hashlib.sha256(b).hexdigest(), lf=hashlib.sha256(lf).hexdigest(), crlf=hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest(),
                lone_cr=b'\r' in lf)


def pinned_text_ok(p, pinned):
    e = eol_layers(p)
    return not e['lone_cr'] and pinned in (e['raw'], e['lf'], e['crlf'])
need_base = pytest.mark.skipif(not BP.BASE_TAMU_V16.exists(), reason='v1.6 baseline .nc only on L2')
FORBIDDEN = ('--calibrate', '--erm-cal', '--s0-calibrate', '--s0-cal-file')


@pytest.fixture(autouse=True)
def no_solver(monkeypatch):
    """A0 = zero solver calls: any linopy / PyPSA solve inside a test fails it"""
    def boom(*a, **k):
        raise AssertionError('solver called in an A0 test')
    try:
        import linopy
        monkeypatch.setattr(linopy.Model, 'solve', boom)
    except ImportError:
        pass
    try:
        import pypsa.optimization.optimize as po
        monkeypatch.setattr(po.OptimizationAccessor, 'solve_model', boom, raising=False)
        monkeypatch.setattr(po.OptimizationAccessor, '__call__', boom, raising=False)
    except Exception:
        pass
    yield


# ------------------------------------------------------------------------------------------------ staging, baseline pins
def test_staging_sha_qa_pass():
    q = json.loads((BP.POST_V16_INPUTS / 'STAGING_SHA_QA.json').read_text())
    assert q['status'] == 'PASS' and q['files_ok'] == q['files'] == 53 and q['raw_registry_ok'] == 20 and q['solver_calls'] == 0
    for r in q['rows']:
        if r['path'].startswith('derived/'):
            assert pinned_text_ok(ROOT / r['staged'], r['expected']), r['staged']      # A2-FIX-06: content-strict, EOL-portable


def test_v16_base_pins_agree():
    c = G.load(CFG)
    assert c['baseline']['sha256'] == BP.BASE_TAMU_V16_SHA256 == 'a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16'
    assert (ROOT / c['baseline']['path']).resolve() == BP.BASE_TAMU_V16.resolve()
    assert 'baseline_2025_tamu_v16' in c['baseline']['path']
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_git_sha'] is None and c['approved_by'] is None
    assert c['stages'] == ['LP_R_H_RESOURCE', 'LP_N_H_NETWORK'] and c['max_lp_calls'] == 2 and c['max_retries'] == 0


@need_base
def test_v16_base_file_sha_on_this_machine():
    assert sha(BP.BASE_TAMU_V16) == BP.BASE_TAMU_V16_SHA256


def test_manifest_is_current():
    import build_post_v16_manifest as BM
    m = json.loads((ROOT / 'current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json').read_text())
    now = BM.build()
    for k in ('config_sha256_normalised', 'baseline', 'stages'):
        assert m[k] == now[k], k
    for k in ('code_sha256', 'inputs_sha256'):           # A2-FIX-06: the A1 pins are CRLF bytes of the main checkouts
        assert set(m[k]) == set(now[k]), k
        for rel, h in m[k].items():
            assert h == now[k][rel] or pinned_text_ok(ROOT / rel, h), rel


# ------------------------------------------------------------------------------------------------ windows, weights, load
def test_windows_preregistered_disjoint_and_vintage():
    import post_v16_headroom as H
    c = H.load_cfg(CFG)
    wins = H.windows(c)
    assert [w['id'] for w in wins] == ['W_SUMMER_PEAK_20250818', 'W_WINTER_PEAK_20250220', 'W_SUMMER_DISJOINT_20250730']
    assert all(len(w['rows']) == 72 for w in wins)
    assert wins[0]['events'] == ['SUMMER_LOAD_PEAK', 'SUMMER_OBSERVED_NET_PEAK']          # same 72 h, counted once
    q = H.stress_vintage_qa(c, wins)
    for w in q['windows']:
        assert w['hours'] == 72 and w['dst_extra_hours'] == 0 and w['hour_ending_contiguous']
    assert q['renewables']['same_weather_year'] is False and 'ACTUAL OUTPUT' in q['renewables']['observed_output']
    assert q['solver_calls'] == 0
    mi, meta = H.snapshot_index(wins)
    assert len(mi) == 432 and sorted(set(meta.period)) == list(range(1, 7))
    assert (meta.step3h == meta.source_row // 3).all()
    assert set(meta[meta.block == 'B0'].source_row) == set(meta[meta.block == 'BL'].source_row)


def test_weights_16_buses_facility_vs_it():
    import post_v16_headroom as H
    w = H.weights()
    assert len(w) == 16 and abs(w.w.sum() - 1) < 1e-12 and (w.w > 0).all()
    assert np.allclose(w.facility_MW_2031 / w.IT_MW_2026_2031, w.PUE_TX_2031)           # MW facility = MW IT x PUE
    poi = pd.read_csv(BP.INPUTS / 'poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv')
    assert abs(w.facility_MW_2031.sum() - poi.research_facility_MW_2031_mid.sum()) < 1e-3 and 'p610 2' in w.index


def test_hourly_load_rule_matches_native_load():
    import post_v16_headroom as H
    rows = list(range(5471, 5543))
    L, d = H.hourly_bus_load(rows, BP.BASE_TAMU_V16_DIR / 'COUNTY_TO_BUS_SHARES.csv')
    assert np.allclose(L.sum(axis=1).values, d.native_load_MW.values) and L.shape[1] == 63
    assert abs(d.native_load_MW.max() - 83679.001697) < 1e-6                                # 2025-08-18 HE18 inside the window


def test_inherited_ramp_is_existing_load():
    import post_v16_headroom as H
    r, p25, it = H.inherited_ramp()
    assert abs(it - 460.73) < 1e-6 and abs(r.sum() - 460.73 * p25) < 1e-6 and len(r) == 5


def test_reserve_parameters_and_eligibility():
    import post_v16_headroom as H
    rp = H.reserve_params(H.load_cfg(CFG))
    assert set(rp) == {'CCGT', 'OCGT', 'gas_steam', 'coal', 'biomass', 'hydro'}               # no nuclear / wind / solar / shed
    assert np.isclose(rp['CCGT']['rho'], 0.4) and np.isclose(rp['CCGT']['pmin'], 0.5)
    assert np.isclose(rp['OCGT']['rho'], 0.6) and np.isclose(rp['coal']['rho'], 0.2)
    t = pd.read_csv(BP.POST_V16_INPUTS / 'POST_V16_RESERVE_PARAMETERS.csv')
    assert (t[t.parameter.isin(['ramp_rate', 'min_stable_load'])].status == 'EXECUTOR_ASSUMPTION_PENDING_APPROVAL').all()
    c = H.load_cfg(CFG)
    assert c['reserve']['requirement_MW'] == 3000 and c['reserve']['tau_h'] == 1


# ------------------------------------------------------------------------------------------------ synthetic model (pypsa, no solver)
def synthetic(mode='N'):
    pypsa = pytest.importorskip('pypsa')
    import post_v16_headroom as H
    ts = pd.date_range('2025-08-18 01:00', periods=3, freq='h')
    mi = pd.MultiIndex.from_arrays([[1, 1, 1, 2, 2, 2], list(ts) * 2], names=['period', 'timestep'])
    meta = pd.DataFrame(dict(period=[1, 1, 1, 2, 2, 2], block=['B0'] * 3 + ['BL'] * 3, source_row=[0, 1, 2] * 2, step3h=[0] * 6), index=mi)
    n = pypsa.Network()
    n.set_snapshots(mi); n.investment_periods = [1, 2]
    for b in ('a', 'b', 'c'):
        n.add('Bus', b, carrier='AC', reeds_zone='p60')
    n.add('Carrier', ['AC', 'CCGT', 'OCGT', 'nuclear', 'onwind', 'battery'])
    n.add('Line', ['L1', 'L2'], bus0=['a', 'b'], bus1=['b', 'c'], s_nom=[100.0, 100.0], x=[0.1, 0.1], r=[0.01, 0.01], s_max_pu=0.7)
    n.add('Generator', 'a CCGT', bus='a', carrier='CCGT', p_nom=500.0, marginal_cost=30.0)
    n.add('Generator', 'b OCGT', bus='b', carrier='OCGT', p_nom=200.0, marginal_cost=60.0)
    n.add('Generator', 'c nuc', bus='c', carrier='nuclear', p_nom=300.0, marginal_cost=10.0)
    n.add('Generator', 'c wind', bus='c', carrier='onwind', p_nom=200.0, marginal_cost=0.0, p_max_pu=pd.Series([0.5] * 6, index=mi))
    n.add('StorageUnit', 'b bat', bus='b', carrier='battery', p_nom=100.0, max_hours=2.0, efficiency_store=0.92, efficiency_dispatch=0.92)
    for df in (n.generators, n.storage_units, n.lines):
        df['build_year'] = 0; df['lifetime'] = np.inf
    H.apply_costs_and_storage(n)
    Lt = pd.DataFrame({'a': 300.0, 'b': 200.0, 'c': 100.0}, index=mi)
    w = pd.DataFrame(dict(w=[0.25, 0.75], PUE_TX_2031=1.1484), index=pd.Index(['a', 'c'], name='bus'))
    H.add_loads(n, meta, Lt, pd.Series({'b': 10.0}), w, 1000.0)
    H.apply_mode(n, mode)
    cfg = H.load_cfg(CFG)
    info = dict(mode=mode, meta=meta, weights=w.reset_index().to_dict(orient='records'), reserve=H.reserve_params(cfg))
    n.optimize.create_model()
    hr = H.add_headroom(n, cfg, info)
    return n, info, cfg, hr, H


def labels(v):
    return set(np.asarray(v.labels.values).ravel()) - {-1}


def test_headroom_model_has_no_build_variables_no_old_erm_no_shadow_soc():
    n, info, cfg, hr, H = synthetic('N')
    s = H.structural_checks(n, info)
    assert not [v for v in s['variables'] if v.endswith(('-p_nom', '-s_nom', '-e_nom', '_RESERVES'))]
    assert not [c for c in s['constraints'] if 'ERM' in c] and s['integer_vars'] == 0
    assert 'StorageUnit-state_of_charge_RESERVES' not in s['variables']


def test_reserve_requirement_eligible_set_and_thermal_rows():
    n, info, cfg, hr, H = synthetic('N')
    m = n.model
    assert set(m['PV16-res_thermal'].coords['name'].values) == {'a CCGT', 'b OCGT'}         # nuclear / wind not eligible
    req = m.constraints['PV16-reserve_req']
    assert np.allclose(req.rhs.values, 3000.0) and req.rhs.size == 6
    used = set(req.lhs.vars.values.ravel()) - {-1}
    assert used <= labels(m['PV16-res_thermal']) | labels(m['PV16-res_su'])
    om = m.constraints['PV16-online_min'].lhs
    ccgt = om.sel(name='a CCGT')
    assert np.isclose(sorted(set(np.round(ccgt.coeffs.values.ravel(), 9)))[0], -0.5)       # p - pmin x c >= 0
    rr = m.constraints['PV16-res_ramp'].lhs.sel(name='b OCGT')
    assert np.isclose(sorted(set(np.round(rr.coeffs.values.ravel(), 9)))[0], -0.6)         # r - rho x c <= 0
    ub = m['PV16-online_cap'].upper.sel(name='a CCGT').values
    assert np.allclose(ub, 500.0)                                                          # c <= p_nom x avail


def test_storage_reserve_uses_dispatch_soc():
    n, info, cfg, hr, H = synthetic('N')
    m = n.model
    e = m.constraints['PV16-res_su_energy'].lhs
    soc = labels(m['StorageUnit-state_of_charge'])
    vars_ = set(e.vars.values.ravel()) - {-1}
    assert vars_ & soc and vars_ <= soc | labels(m['PV16-res_su'])                            # the SAME dispatch SOC variable
    cr = e.coeffs.values[np.isin(e.vars.values, list(labels(m['PV16-res_su'])))]
    assert np.allclose(cr, 1.0 / 0.92)                                                     # tau / eff_dispatch
    pw = m.constraints['PV16-res_su_power']
    assert np.allclose(pw.rhs.values, 100.0)                                               # r + p_dispatch - p_store <= p_nom


def test_lambda_block_weights_and_objective():
    n, info, cfg, hr, H = synthetic('N')
    m = n.model
    c = m.constraints['PV16-newload']
    lam = int(m['PV16-lambda'].labels.values)
    co = c.lhs.coeffs.values[c.lhs.vars.values == lam]
    assert sorted(set(np.round(co, 12))) == [0.25, 0.75] and c.lhs.sizes['snapshot'] == 3  # BL only
    pmin = n.get_switchable_as_dense('Generator', 'p_min_pu', inds=['a PV16 new AIDC load'])
    assert (pmin.values[:3] == 0).all() and (pmin.values[3:] == -1).all()                  # B0: new load fixed to 0
    obj = m.objective.expression if hasattr(m.objective, 'expression') else m.objective
    ov, oc = obj.vars.values.ravel(), obj.coeffs.values.ravel()
    assert set(ov[ov != -1]) == {lam} and np.allclose(oc[ov != -1], -1.0)                  # A0.1 FIX-01: objective = -lambda only
    shed = [x for x in n.generators.index if n.generators.carrier[x] == 'load_shed']
    z = m.constraints['PV16-existing_shed_zero']                                            # hard zero, B0 and BL
    assert np.allclose(z.rhs.values, 0.0) and set(np.unique(np.asarray(z.sign.values).astype(str))) == {'='}
    assert z.lhs.sizes['snapshot'] == 6 and set(z.lhs.coords['name'].values) == set(shed)


def test_copperplate_keeps_lines_and_connectivity():
    nR, infoR, *_ = synthetic('R')
    nN, infoN, *_ = synthetic('N')
    import post_v16_headroom as H
    assert (nR.lines.s_nom == H.COPPER_MVA).all() and (nN.lines.s_nom == 100.0).all()
    assert len(nR.lines) == len(nN.lines) == 2 and list(nR.lines.x) == list(nN.lines.x)    # KVL kept, no isolated bus
    sR, sN = H.structural_checks(nR, infoR), H.structural_checks(nN, infoN)
    assert sR['components'] == sN['components'] == 1
    assert sR['n_vars'] == sN['n_vars'] and sR['n_cons'] == sN['n_cons']                   # same feasible-set structure


def test_writer_with_synthetic_solution(tmp_path):
    import post_v16_a1 as A
    mi = pd.MultiIndex.from_arrays([[1, 1, 2, 2], pd.to_datetime(['2025-08-18 01:00', '2025-08-18 02:00'] * 2)], names=['period', 'timestep'])
    meta = pd.DataFrame(dict(period=[1, 1, 2, 2], block=['B0', 'B0', 'BL', 'BL'], source_row=[0, 1, 0, 1], step3h=[0, 0, 0, 0]), index=mi)
    p = pd.DataFrame({'g': [100.0] * 4, 'sh': [0.0, 0.0, 0.0, 1.0]}, index=mi)
    v = dict(lam=500.0, weights=pd.DataFrame(dict(w=[0.4, 0.6], PUE_TX_2031=1.1484), index=pd.Index(['a', 'b'], name='bus')), meta=meta,
             p=p, carrier=pd.Series({'g': 'CCGT', 'sh': 'load_shed'}), bus=None, p_nom=None,
             r_thermal=pd.DataFrame({'g': [2500.0] * 4}, index=mi), online=None, r_su=pd.DataFrame({'s': [600.0] * 4}, index=mi),
             su_dispatch=pd.DataFrame({'s': [0.0, 10.0, 0.0, 0.0]}, index=mi), su_store=pd.DataFrame({'s': [0.0, 5.0, 0.0, 0.0]}, index=mi),
             soc=pd.DataFrame({'s': [800.0] * 4}, index=mi), su_pnom=None, su_effd=pd.Series({'s': 0.92}),
             p0=pd.DataFrame({'L1': [50.0, 70.0, 69.5, 10.0]}, index=mi), limit=pd.Series({'L1': 70.0}),
             line_bus0=pd.Series({'L1': 'a'}), line_bus1=pd.Series({'L1': 'b'}), zone=pd.Series({'a': 'p60', 'b': 'p63'}),
             load=pd.DataFrame({'a': [100.0] * 4}, index=mi), R=3000.0, tau=1.0, mode='N')
    s = A.write_outputs(v, tmp_path, 'LP_N_H_NETWORK')
    assert s['lambda_facility_MW'] == 500.0 and np.isclose(s['lambda_IT_MW'], 500 / 1.1484)
    assert s['existing_shed_MWh_B0'] == 0.0 and s['existing_shed_MWh_BL'] == 1.0 and s['reserve_min_slack_MW'] == 100.0
    assert s['reserve_storage_simultaneous_MW_max'] == 600.0 and s['lines_near_limit_BL'] == 1
    q = pd.read_csv(tmp_path / 'STRESS_DISPATCH_RESERVE_QA_LP_N_H_NETWORK.csv')
    assert np.isclose(q.storage_energy_backing_min_margin_MWh.min(), 800 - 600 / 0.92)
    hb = pd.read_csv(tmp_path / 'HEADROOM_BY_BUS_LP_N_H_NETWORK.csv')
    assert np.isclose(hb.h_facility_MW.sum(), 500.0) and np.isclose(hb.h_IT_MW.sum() * 1.1484, 500.0)


# ------------------------------------------------------------------------------------------------ POI ledger
def test_poi_ledger_firm_conditional_separate():
    import post_v16_headroom as H
    L, lam = H.poi_ledger()
    assert set(L.bus) == set(H.weights().index) and set(L.year) == set(range(2026, 2032))
    assert (L.E0_firm_preapproved_MW <= L.E0_firm_all_rows_MW + 1e-9).all() and (L.firm_with_upgrade_MW >= L.E0_firm_all_rows_MW).all()
    assert 'conditional_PCLR_MW' in L and not (lam.book == 'conditional_PCLR_MW').any()     # conditional never a firm book
    assert (L.upgrade_earliest_COD == 2029.0).all()                                        # max(2026 + 3 y lead, procedural 2028)
    x = L[L.year == 2026]
    r = (x.E0_firm_preapproved_MW / x.w_b).min()
    assert np.isclose(lam[(lam.year == 2026) & (lam.book == 'E0_firm_preapproved_MW')].lambda_POI_facility_MW.iloc[0], r)
    assert lam[(lam.year == 2026) & (lam.book == 'E0_firm_preapproved_MW')].lambda_POI_facility_MW.iloc[0] == 0.0   # buses without POI


# ------------------------------------------------------------------------------------------------ gate (negative + positive)
class FakeGit:
    def __init__(self, head='a' * 40, dirty='', ancestor=True, since=''):
        self.head, self.dirty, self.ancestor, self.since = head, dirty, ancestor, since

    def __call__(self, *args):
        if args[0] == 'rev-parse':
            return SimpleNamespace(stdout=self.head + '\n')
        if args[0] == 'merge-base':
            return SimpleNamespace(returncode=0 if self.ancestor else 1, stdout='')
        if args[0] == 'diff' and args[1] == '--name-only':     # diff --name-only <approved> HEAD -- paths
            return SimpleNamespace(stdout=self.since)
        if args[0] == 'diff':
            return SimpleNamespace(stdout=self.dirty)
        if args[0] == 'ls-files':
            return SimpleNamespace(stdout='')
        raise AssertionError(args)


def gate_env(tmp_path, approve=True, base_bytes=b'v16', pin=None):
    root = tmp_path / 'root'
    (root / 'workflow/config').mkdir(parents=True)
    src = root / 'wp.md'; src.write_text('package')
    base = root / 'workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc'
    base.parent.mkdir(parents=True); base.write_bytes(base_bytes)
    code = root / 'code.py'; code.write_text('x = 1')
    c = yaml.safe_load(CFG.read_text(encoding='utf-8'))
    p = c['post_v16']
    p.update(authorization_source='wp.md', authorization_source_sha256=sha(src), manifest='man.json')
    p['baseline']['sha256'] = pin or hashlib.sha256(b'v16').hexdigest()
    if approve:
        p.update(run_authorization='APPROVED', approved_git_sha='a' * 12, approved_by='researcher')
    cfg = root / 'workflow/config/config.byop_post_v16_a1.yaml'
    cfg.write_text(yaml.safe_dump(c))
    man = dict(code_sha256={'code.py': sha(code)}, inputs_sha256={}, config_sha256_normalised=G.config_sha(cfg),
               baseline=dict(sha256=p['baseline']['sha256']))
    (root / 'man.json').write_text(json.dumps(man))
    return root, cfg, base


def test_gate_refuses_not_approved_and_never_solves(tmp_path):
    root, cfg, base = gate_env(tmp_path, approve=False)
    g = G.check(cfg, 'LP_R_H_RESOURCE', base, tmp_path / 'log.csv', root=root, git_fn=FakeGit())
    assert not g['approved'] and any('run_authorization=NOT_APPROVED' in r for r in g['reasons'])
    with pytest.raises(SystemExit):
        G.deny(g)


def test_gate_passes_only_when_everything_matches(tmp_path):
    root, cfg, base = gate_env(tmp_path)
    g = G.check(cfg, 'LP_R_H_RESOURCE', base, tmp_path / 'log.csv', root=root, git_fn=FakeGit())
    assert g['approved'], g['reasons']


def test_gate_refuses_wrong_head_dirty_tree_and_changed_code(tmp_path):
    root, cfg, base = gate_env(tmp_path)
    chk = lambda gf: G.check(cfg, 'LP_R_H_RESOURCE', base, tmp_path / 'l.csv', root=root, git_fn=gf)['reasons']
    assert any('not HEAD' in r for r in chk(FakeGit(head='b' * 40, ancestor=False)))
    assert chk(FakeGit(head='b' * 40, since='workflow/config/config.byop_post_v16_a1.yaml')) == []     # approval commit of the config only
    assert any('changed since the approved commit' in r for r in chk(FakeGit(head='b' * 40, since='workflow/byop/model/post_v16_headroom.py')))
    assert any('not clean' in r for r in G.check(cfg, 'LP_R_H_RESOURCE', base, tmp_path / 'l.csv', root=root, git_fn=FakeGit(dirty='workflow/byop/model/x.py'))['reasons'])
    (root / 'code.py').write_text('x = 2')
    assert any('sha256 mismatch: code.py' in r for r in G.check(cfg, 'LP_R_H_RESOURCE', base, tmp_path / 'l.csv', root=root, git_fn=FakeGit())['reasons'])


def test_base_sha_pin_and_wrong_base_refused(tmp_path):
    root, cfg, base = gate_env(tmp_path, base_bytes=b'not v16')
    assert any('baseline SHA' in r for r in G.check(cfg, 'LP_R_H_RESOURCE', base, tmp_path / 'l.csv', root=root, git_fn=FakeGit())['reasons'])
    old = root / 'workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc'
    old.parent.mkdir(parents=True); old.write_bytes(b'v16')
    assert any('is not the v1.6 baseline' in r for r in G.check(cfg, 'LP_R_H_RESOURCE', old, tmp_path / 'l.csv', root=root, git_fn=FakeGit())['reasons'])
    assert any('no --base' in r for r in G.check(cfg, 'LP_R_H_RESOURCE', None, tmp_path / 'l.csv', root=root, git_fn=FakeGit())['reasons'])
    base.unlink()
    root2, cfg2, base2 = gate_env(tmp_path / 'x'); base2.unlink()
    assert any('BLOCKED_ON_L2_BASELINE' in r for r in G.check(cfg2, 'LP_R_H_RESOURCE', base2, tmp_path / 'l.csv', root=root2, git_fn=FakeGit())['reasons'])


def ledger_row(stage, state='DONE', status='ok', term='optimal', ok='True', k=1):
    return dict(attempt_id=f'{stage}#{k}', stage=stage, attempt=k, state=state, status=status, termination=term, **{'pass': ok})


def result_json(d, stage, PASS=True, checks=None):
    checks = checks if checks is not None else dict(status_ok=True, termination_optimal=True, existing_shed_zero_B0=True, existing_shed_zero_BL=True)
    (d / f'{stage}_RESULT.json').write_text(json.dumps(dict(stage=stage, acceptance=dict(PASS=PASS, checks=checks))))


def test_gate_stage_order_retry_budget(tmp_path):
    root, cfg, base = gate_env(tmp_path)
    log = tmp_path / 'log.csv'
    chk = lambda st: G.check(cfg, st, base, log, root=root, git_fn=FakeGit())['reasons']
    assert any('needs a PASSED LP_R' in r for r in chk('LP_N_H_NETWORK'))
    assert any('not authorised' in r for r in chk('S0'))
    pd.DataFrame([ledger_row('LP_R_H_RESOURCE', 'STARTED', '', '', '')]).to_csv(log, index=False)          # crashed mid-solve
    assert any('zero retries' in r and 'STARTED' in r for r in chk('LP_R_H_RESOURCE'))
    assert any('needs a PASSED' in r for r in chk('LP_N_H_NETWORK'))
    pd.DataFrame([ledger_row('LP_R_H_RESOURCE'), ledger_row('LP_N_H_NETWORK')]).to_csv(log, index=False)
    assert any('budget' in r for r in chk('LP_N_H_NETWORK'))


def test_gate_lp_n_needs_lp_r_result_pass_not_only_log(tmp_path):
    """FIX-02 counter-examples: optimal + positive shed, optimal + missing result, optimal + no PASS, non-optimal"""
    root, cfg, base = gate_env(tmp_path)
    log = tmp_path / 'log.csv'
    chk = lambda: G.check(cfg, 'LP_N_H_NETWORK', base, log, root=root, git_fn=FakeGit())['reasons']
    pd.DataFrame([ledger_row('LP_R_H_RESOURCE')]).to_csv(log, index=False)
    assert any('RESULT.json missing' in r for r in chk())                                         # optimal + missing result
    result_json(tmp_path, 'LP_R_H_RESOURCE', PASS=False, checks=dict(status_ok=True, existing_shed_zero_BL=False))
    assert any('acceptance is not PASS' in r for r in chk())                                      # optimal + positive shed
    result_json(tmp_path, 'LP_R_H_RESOURCE', PASS=True, checks=dict(status_ok=True, existing_shed_zero_BL=False))
    assert any('acceptance is not PASS' in r for r in chk())                                      # PASS flag inconsistent with checks
    pd.DataFrame([ledger_row('LP_R_H_RESOURCE', ok='False')]).to_csv(log, index=False); result_json(tmp_path, 'LP_R_H_RESOURCE')
    assert any('not DONE / ok / optimal / pass' in r for r in chk())                              # optimal + no PASS
    pd.DataFrame([ledger_row('LP_R_H_RESOURCE', status='warning', term='suboptimal')]).to_csv(log, index=False)
    assert any('not DONE / ok / optimal / pass' in r for r in chk())                              # non-optimal
    pd.DataFrame([ledger_row('LP_R_H_RESOURCE')]).to_csv(log, index=False); result_json(tmp_path, 'LP_R_H_RESOURCE')
    assert chk() == []                                                                            # only a real PASS opens LP-N


def test_gate_refuses_corrupted_ledger(tmp_path):
    root, cfg, base = gate_env(tmp_path)
    log = tmp_path / 'log.csv'
    log.write_text('stage,status\nLP_R_H_RESOURCE,ok\n')
    assert any('malformed' in r for r in G.check(cfg, 'LP_R_H_RESOURCE', base, log, root=root, git_fn=FakeGit())['reasons'])
    log.write_bytes(b'\x00\xff\xfe"unterminated')
    r = G.check(cfg, 'LP_R_H_RESOURCE', base, log, root=root, git_fn=FakeGit())['reasons']
    assert any('ledger' in x for x in r)


def test_gate_config_approval_fields_do_not_change_pinned_sha(tmp_path):
    root, cfg, base = gate_env(tmp_path, approve=False)
    a = G.config_sha(cfg)
    c = yaml.safe_load(cfg.read_text()); c['post_v16'].update(run_authorization='APPROVED', approved_git_sha='x', approved_by='y')
    cfg.write_text(yaml.safe_dump(c))
    assert G.config_sha(cfg) == a
    c['post_v16']['reserve']['requirement_MW'] = 2000; cfg.write_text(yaml.safe_dump(c))
    assert G.config_sha(cfg) != a


def test_unapproved_lp_refused_before_any_build(monkeypatch):
    import post_v16_a1 as A
    monkeypatch.setattr(A, 'build', lambda *a, **k: (_ for _ in ()).throw(AssertionError('built before the gate')))
    with pytest.raises(SystemExit) as e:
        A.lp('R', str(BP.BASE_TAMU_V16), 1)
    assert 'POST_V16_RUN_GATE REFUSED' in str(e.value) and 'NOT_APPROVED' in str(e.value)


# ------------------------------------------------------------------------------------------------ entries / legacy refusal
def bash(cmd, env=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run(['bash', '-c', cmd], cwd=str(WF), capture_output=True, text=True, env=e)


@pytest.mark.skipif(shutil.which('bash') is None, reason='bash missing')
def test_dry_commands_show_base_and_no_legacy_calibration_args():
    for st in ('a1_dry', 'a1_lp_r', 'a1_lp_n', 'a2_s0s1'):
        r = bash(f'bash byop/run/run_post_v16.sh {st}', dict(DRY='1'))
        assert r.returncode == 0 and r.stdout.startswith('CMD '), (st, r.stdout, r.stderr)
        for line in r.stdout.splitlines():
            assert '--base /datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc' in line
            assert not any(f in line.split() for f in FORBIDDEN), line
    r = bash('bash byop/run/run_post_v16.sh a2_s0s1')
    assert r.returncode == 3


@pytest.mark.skipif(shutil.which('bash') is None, reason='bash missing')
def test_legacy_step0_refuses_post_v16_configs_but_legacy_still_reproduces():
    for cfg in ('config/config.byop_post_v16_a1.yaml', 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml'):
        for st in ('step0', 'pilot_s01', 'pilot_core', 'run'):
            r = bash(f'bash byop/run/run_mainline.sh {st}', dict(DRY='1', CFG=cfg))
            assert r.returncode == 6 and 'refusing' in r.stdout, (cfg, st)
    r = bash('bash byop/run/run_mainline.sh step0', dict(DRY='1'))
    assert r.returncode == 0 and '--calibrate' in r.stdout and '--s0-calibrate' in r.stdout          # legacy reproduction unchanged


def test_rearch_post_v16_refuses_legacy_flags(tmp_path):
    pytest.importorskip('pypsa')
    base = str(BP.BASE_TAMU_V16)
    for extra in (['--calibrate'], ['--erm-cal', 'x.json'], ['--s0-calibrate'], ['--s0-cal-file', 'x.csv'], []):
        r = subprocess.run([sys.executable, '-W', 'ignore', str(BY / 'model/rearch_mech.py'), '--post-v16', '--case-id', 't', '--out', str(tmp_path),
                            '--base', base, *extra], cwd=str(WF), capture_output=True, text=True)
        assert r.returncode == 3, r.stderr[-500:]
        assert 'POST_V16_GUARD' in r.stdout and 'POST_V16_MAINLINE_NOT_READY' in r.stdout
        if extra:
            assert f'legacy flag {extra[0]}' in r.stdout
    r = subprocess.run([sys.executable, '-W', 'ignore', str(BY / 'model/rearch_mech.py'), '--post-v16', '--case-id', 't', '--out', str(tmp_path),
                        '--base', str(BP.BASE_TAMU_DIR / 'baseline_2025_tamu_prepared.nc')], cwd=str(WF), capture_output=True, text=True)
    assert r.returncode == 3 and 'is not the v1.6 baseline' in r.stdout


# ------------------------------------------------------------------------------------------------ v1.6 network (L2 only)
@need_base
def test_real_v16_models_build_without_solver():
    import post_v16_a1 as A
    for mode in ('R', 'N'):
        n, info, cfg = A.build(mode, BP.BASE_TAMU_V16)
        s = info['structure']
        assert s['buses'] == 63 and s['lines'] == 162 and s['snapshots'] == 432 and s['components'] == 1 and s['integer_vars'] == 0
        caps = [x for x in n.generators.index if 'Kiamichi' in x or 'Tenaska Gateway' in x]
        assert len(caps) == 2 and (n.generators_t.p_max_pu[caps].min() < 1).any()                  # switchable caps held
        assert abs(n.generators.p_nom[~n.generators.carrier.isin(['load_shed', 'aidc_new'])].sum() + n.storage_units.p_nom.sum() - 155446.9) < 0.1


def test_balance_residual_on_hand_built_flows():
    pypsa = pytest.importorskip('pypsa')
    import post_v16_a1 as A
    n = pypsa.Network(); n.set_snapshots(range(2))
    n.add('Bus', ['a', 'b']); n.add('Line', 'L', bus0='a', bus1='b', s_nom=10, x=0.1)
    n.add('Generator', 'g', bus='a', p_nom=10); n.add('Load', 'l', bus='b', p_set=5.0)
    n.generators_t.p = pd.DataFrame({'g': [5.0, 5.0]}, index=n.snapshots); n.loads_t.p = pd.DataFrame({'l': [5.0, 5.0]}, index=n.snapshots)
    n.lines_t.p0 = pd.DataFrame({'L': [5.0, 4.0]}, index=n.snapshots); n.lines_t.p1 = pd.DataFrame({'L': [-5.0, -4.0]}, index=n.snapshots)
    assert np.isclose(A.balance_residual(n), 1.0)
