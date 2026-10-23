"""NEXT-07 W4 static tests: A3 runtime accounting, conservative RE+BESS firm rule, S2 convergence / matched-service audits
(zero solver: every linopy solve raises; ledgers live in tmp_path)."""
from __future__ import annotations

import json, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
A3CFG = WF / 'config/config.byop_post_v16_a3.yaml'


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


@pytest.fixture
def rt(tmp_path, monkeypatch):
    """armed A3 runtime on a tmp copy of the A3 config (own ledgers in tmp_path), gate injected as approved"""
    import post_v16_a3_runtime as RT
    raw = yaml.safe_load(A3CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str(tmp_path / 'a3')
    p = tmp_path / 'config.byop_post_v16_a3.yaml'
    p.write_text(yaml.safe_dump(raw), encoding='utf-8')
    RT.arm(p, None, gate_fn=lambda st: dict(approved=True, reasons=[]))
    yield RT, p
    RT.disarm()


def ledgers(p):
    import post_v16_a3_gate as A3G
    c, out, log, child = A3G.paths(p)
    lg = pd.read_csv(log, dtype=str, keep_default_na=False) if log.exists() else pd.DataFrame()
    cl = pd.read_csv(child, dtype=str, keep_default_na=False) if child.exists() else pd.DataFrame()
    return lg, cl


# ------------------------------------------------------------------------------------------------ W4.2 conservative firm rule
def firm_network():
    pypsa = pytest.importorskip('pypsa')
    mi = pd.MultiIndex.from_product([[2026], pd.date_range('2030-02-19', periods=4, freq='3h')], names=['period', 'timestep'])
    n = pypsa.Network(); n.set_snapshots(mi); n.investment_periods = [2026]
    n.add('Bus', ['a', 'DC_x']); n.add('Carrier', ['CCGT', 'byop_WIND', 'byop_BESS', 'byop_RICE', 'compute_IT'])
    n.add('Generator', 'a CCGT', bus='a', carrier='CCGT', p_nom=1000, marginal_cost=30, build_year=2025, lifetime=50)
    n.add('Generator', 'DC_x BYOP WIND', bus='DC_x', carrier='byop_WIND', p_nom_extendable=True, capital_cost=1e5, build_year=2026, lifetime=25)
    n.add('Generator', 'DC_x BYOP RICE', bus='DC_x', carrier='byop_RICE', p_nom_extendable=True, capital_cost=2e5, build_year=2026, lifetime=25)
    n.add('Generator', 'DC_x S', bus='DC_x', carrier='compute_IT', p_nom_extendable=True, build_year=2026, lifetime=25)
    n.add('StorageUnit', 'DC_x BYOP BESS', bus='DC_x', carrier='byop_BESS', p_nom_extendable=True, max_hours=4, capital_cost=5e4, build_year=2026, lifetime=15)
    n.add('Load', 'l', bus='a', p_set=500.0)
    m = n.optimize.create_model()
    pn = m['Generator-p_nom']
    m.add_constraints(pn.sel(name='DC_x S') - pn.sel(name='DC_x BYOP RICE') <= 0, name='M2-serve_cap_DC_x S')     # RICE = qualified firm
    return n


def serve_cap_terms(m):
    c = m.constraints['M2-serve_cap_DC_x S']
    v, k = np.asarray(c.vars.values).ravel(), np.asarray(c.coeffs.values).ravel()
    return {int(a): float(b) for a, b in zip(v, k) if a != -1}


@pytest.mark.parametrize('rule, ub', [(None, np.inf), ('CONSERVATIVE_FIRM_SCREENING', 0.0)])
def test_firm_rule_bounds_re_bess_credit(rule, ub):
    import post_v16_mainline as PM
    n = firm_network()
    rows = PM.add_re_bess_firm_certificate(n, n.snapshots, [dict(zone='x', period=2026, S='DC_x S', pue=1.25)], lambda s: np.ones(len(s), bool), firm_rule=rule)
    m = n.model
    F = m.variables['A2-F_cert_x_2026']
    assert float(np.asarray(F.upper.values)) == ub
    assert rows[0]['firm_credit_allowed'] is (rule is None)
    t = serve_cap_terms(m)
    fl = int(np.asarray(F.labels.values))
    assert abs(t[fl] + 0.8) < 1e-12                       # the certificate term is still in the row (audit) ...
    rice = int(m['Generator-p_nom'].sel(name='DC_x BYOP RICE').labels.values)
    assert t[rice] == -1.0                               # ... and the qualified firm (RICE) term is unchanged
    assert any(k.startswith('A2-F_soc_start_') for k in m.constraints)


def test_firm_rule_unknown_value_refused():
    import post_v16_mainline as PM
    n = firm_network()
    with pytest.raises(ValueError, match='not implemented'):
        PM.add_re_bess_firm_certificate(n, n.snapshots, [], lambda s: np.ones(len(s), bool), firm_rule='CERT_48H')


def test_firm_rule_reaches_s2_developer_and_s3_alike():
    """one code path: developer_joint_build and every public / S3 build use extra_rearch, which passes the run's firm rule"""
    import rearch_mech as R
    src = Path(R.__file__).read_text(encoding='utf-8')
    assert "add_re_bess_firm_certificate(n, snapshots, STATE['dc'], stress_mask, firm_rule=STATE.get('pv16_firm_rule'))" in src
    dj = src[src.index('def developer_joint_build'):src.index('def _require_gate')]
    assert 'extra_rearch(n, n.snapshots)' in dj
    assert "STATE['pv16_firm_rule'] = pv16_gate['firm_rule']" in src
    assert yaml.safe_load(A3CFG.read_text(encoding='utf-8'))['post_v16']['firm_rule'] == 'CONSERVATIVE_FIRM_SCREENING'


# ------------------------------------------------------------------------------------------------ W4.1 runtime accounting
def test_stage_refused_without_gate(tmp_path):
    import post_v16_a3_runtime as RT
    raw = yaml.safe_load(A3CFG.read_text(encoding='utf-8')); raw['post_v16']['out_dir'] = str(tmp_path / 'a3')
    p = tmp_path / 'c.yaml'; p.write_text(yaml.safe_dump(raw), encoding='utf-8')
    RT.arm(p, None, gate_fn=lambda st: dict(approved=False, reasons=['run_authorization=NOT_APPROVED']))
    try:
        with pytest.raises(SystemExit, match='A3_GATE REFUSED'):
            RT.begin('S0')
        assert ledgers(p)[0].empty                        # nothing consumed by a refused stage
    finally:
        RT.disarm()
    with pytest.raises(SystemExit, match='outside an armed A3 run'):
        RT.begin('S0')


def test_child_outside_stage_refused(rt):
    RT, p = rt
    with pytest.raises(SystemExit, match='outside a ledgered A3 stage'):
        RT.child_start()


def test_s2_iteration_call_plan(rt):
    RT, p = rt
    aid, _ = RT.begin('S2_IT1')
    cids = []
    for _ in range(6):
        RT.expect('S2_DEV_LEX'); cids.append(RT.child_start())
    with pytest.raises(SystemExit, match='S2_DEV_LEX already used 6 / 6'):
        RT.expect('S2_DEV_LEX'); RT.child_start()
    RT.expect('S2_DEV_COST'); cids.append(RT.child_start())
    cids.append(RT.child_start())                        # default kind of an S2 stage = the public LP
    with pytest.raises(SystemExit, match='S2_PUBLIC already used'):
        RT.child_start()
    ok, rows = RT.children_complete(aid, 'S2_IT1')
    assert not ok                                         # still STARTED
    for c in cids:
        RT.child_finish(c, state='DONE', status='ok', termination='optimal')
    ok, rows = RT.children_complete(aid, 'S2_IT1')
    assert ok and sorted({r['kind'] for r in rows}) == ['S2_DEV_COST', 'S2_DEV_LEX', 'S2_PUBLIC']
    RT.end('DONE', **{'pass': True})
    lg, cl = ledgers(p)
    assert list(lg.state) == ['DONE'] and len(cl) == 8 and set(cl.parent_attempt_id) == {aid}


def test_failed_stage_keeps_evidence(rt):
    RT, p = rt
    RT.begin('S0')
    cid = RT.child_start()
    RT.end('ERROR', status='exception', note='boom', **{'pass': False})
    lg, cl = ledgers(p)
    assert list(lg.state) == ['ERROR'] and list(cl.state) == ['ERROR'] and cl.call_id.iloc[0] == cid      # rows kept, never deleted


def test_linopy_lock_routes_a3_calls(rt, monkeypatch):
    import rearch_mech as R
    import linopy
    RT, p = rt
    monkeypatch.setitem(R.PV16_LOCK, 'armed', False)
    R._arm_post_v16_optimizer_lock()
    m = linopy.Model(); x = m.add_variables(lower=0, name='x'); m.add_objective(1 * x)
    with pytest.raises(SystemExit, match='outside a ledgered A3 stage'):
        m.solve()
    RT.begin('S3')
    with pytest.raises(RuntimeError, match='solver call in a static test'):
        m.solve()
    lg, cl = ledgers(p)
    assert list(cl.kind) == ['S3_COST'] and list(cl.state) == ['ERROR']   # STARTED before the call, ERROR after it


def test_wrapper_refuses_unplanned_scenario(rt):
    import rearch_mech as R
    RT, p = rt
    w = R.a3_solve_wrapper(lambda *a, **k: dict(status='ok'), SimpleNamespace(base=None), p.parent / 'a3',
                           dict(reference_dir='results/BYOP/post_v16_a2/POST_V16_A2_S0S1'))
    for tag in ('S2_off', 'S1_ECON', 'S3_mS1'):
        with pytest.raises(SystemExit, match='not part of the A3 plan'):
            w(None, tag, None, None)
    with pytest.raises(SystemExit, match='outside its open S2 stage'):
        w(None, 'S2', None, None)
    assert ledgers(p)[0].empty


# ------------------------------------------------------------------------------------------------ audits
def test_s2_loop_skips_optional_iterations_after_convergence():
    import post_v16_a3_runtime as RT
    calls = []
    it, conv = RT.s2_loop(lambda i: calls.append(i) or [], 3)
    assert (it, conv, calls) == (1, True, [1])
    calls.clear()
    it, conv = RT.s2_loop(lambda i: calls.append(i) or (['gap'] if i < 2 else []), 3)
    assert (it, conv, calls) == (2, True, [1, 2])
    calls.clear()
    it, conv = RT.s2_loop(lambda i: calls.append(i) or ['gap'], 3)
    assert (it, conv, calls) == (3, False, [1, 2, 3])
    with pytest.raises(ValueError):
        RT.s2_loop(lambda i: [], 4)


def test_s2_gaps_rule():
    import post_v16_a3_runtime as RT
    dc = [dict(zone='a', period=2027), dict(zone='b', period=2027)]
    rows, bad = RT.s2_gaps(dc, {('a', 2027): 100.0, ('b', 2027): 1000.0}, {('a', 2027): 99.6, ('b', 2027): 998.0})
    assert [d['zone'] for d in bad] == ['b'] and rows[0]['gap_IT_MW'] == pytest.approx(0.4)


def test_matched_service_and_efficiency_claim():
    import post_v16_a3_runtime as RT
    tgt = {('a', 2027): 100.0, ('a', 2028): 200.0, ('b', 2028): 50.0}
    ok, df = RT.matched_service_audit(tgt, dict(tgt))
    assert ok['PASS'] and RT.efficiency_claim(True, ok) == 'ALLOWED'
    shifted = {('a', 2027): 200.0, ('a', 2028): 100.0, ('b', 2028): 50.0}      # same total MW-year, wrong timing
    bad, df = RT.matched_service_audit(tgt, shifted)
    assert not bad['PASS'] and bad['total_ok'] and not bad['bus_year_ok']
    assert RT.efficiency_claim(True, bad) == 'BLOCKED_S3_MS2_NOT_MATCHED'
    assert RT.efficiency_claim(False, ok) == 'BLOCKED_S2_NOT_CONVERGED'


def test_a2_reproduction(tmp_path):
    import post_v16_a3_runtime as RT
    (tmp_path / 'S1_EARLIEST_RESULT.json').write_text(json.dumps(dict(result=dict(objective=5.0e10), acceptance=dict(values=dict(existing_shed_MWh=54205.78)))))
    ok = RT.a2_reproduction('S1_EARLIEST', 5.0e10 * (1 + 1e-7), 54205.79, ref_dir=tmp_path)
    assert ok['PASS']
    assert not RT.a2_reproduction('S1_EARLIEST', 5.0e10 * (1 + 1e-5), 54205.78, ref_dir=tmp_path)['PASS']
    assert not RT.a2_reproduction('S1_EARLIEST', 5.0e10, 54300.0, ref_dir=tmp_path)['PASS']


# ------------------------------------------------------------------------------------------------ fail-closed gates
def a3_args(**kw):
    import rearch_mech as R
    a = dict(a3_config=str(A3CFG), a2_config=None, base=str(R.BP.BASE_TAMU_V16), mainline=True,
             config='config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml', out=str(WF / 'results/BYOP/post_v16_a3/POST_V16_A3_PILOT'),
             no_harm='on', attribution=False, relax=[], scenarios=['S0', 'S1_EARLIEST', 'S3', 'S2', 'S3_mS2'], s2_iter=3,
             calibrate=False, erm_cal=None, s0_calibrate=False, s0_cal_file=None)
    a.update(kw)
    return SimpleNamespace(**a)


def test_a3_guard_fail_closed(capsys):
    import rearch_mech as R
    with pytest.raises(SystemExit):
        R.post_v16_guard(a3_args(scenarios=['S0', 'S1_EARLIEST', 'S3', 'S2', 'S2_off', 'S3_mS2'], s2_iter=4, a2_config='x.yaml'))
    o = capsys.readouterr().out
    assert 'must be exactly' in o and '--s2-iter must be 1-3' in o and 'exclusive' in o
    with pytest.raises(SystemExit) as e:
        R.post_v16_guard(a3_args())
    o = capsys.readouterr().out
    assert e.value.code == 3 and 'run_authorization=NOT_APPROVED' in o and 'S0_RELIABILITY_VERDICT' in o     # S0 verdict blocks A3


def test_consumed_a2_budget_never_reused():
    import post_v16_a2_gate as A2G
    r = A2G.check('S0', None)['reasons']
    assert any('already has a logged call' in x for x in r) or any('budget used' in x for x in r)


def test_a3_reference_pins():
    import post_v16_a3_gate as A3G
    c = A3G.load()
    assert set(c['reference']['sha256']) == {'S0_RESULT.json', 'S1_EARLIEST_RESULT.json', 'S0_NO_HARM_REFERENCE.csv'}
    assert A3G.reference_problems(dict(c, reference=dict(dir=c['reference']['dir'], sha256={'S0_RESULT.json': '0' * 64})))
