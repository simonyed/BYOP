"""NEXT-03 A2-FIX-08 (SOC segments) / A2-FIX-09 (optimizer-call accounting) static tests. Zero solver: models are built and
solutions injected by hand; every 'solve' in the failure-injection tests is a fake function, and linopy.Model.solve is
replaced by a refusal for the whole module."""
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


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


# ------------------------------------------------------------------------------------------------ A2-FIX-08
def snaps(P=(2026, 2027), blocks=(('2030-01-01', 4), ('2030-02-20', 4))):
    rows = [(p, t) for p in P for start, k in blocks for t in pd.date_range(start, periods=k, freq='3h')]
    return pd.MultiIndex.from_tuples(rows, names=['period', 'timestep'])


def test_segments_contiguous_gap_stress_and_period():
    import post_v16_mainline as PM
    one = PM.soc_segments(snaps(P=(2026,), blocks=(('2030-01-01', 8),)))
    assert one.segment.nunique() == 1                                                  # continuous 3 h -> one segment
    two = PM.soc_segments(snaps(P=(2026,), blocks=(('2030-01-01', 4), ('2030-07-01', 4))))
    assert two.segment.nunique() == 2 and two.gap_h_before.max() > 3                    # weeks apart -> separate
    three = PM.soc_segments(snaps(P=(2026,), blocks=(('2030-01-01', 4), ('2030-02-20', 8), ('2030-07-01', 4))))
    assert three.segment.nunique() == 3 and (three.groupby('segment').size().tolist() == [4, 8, 4])  # 2-day stress event stays one
    yrs = PM.soc_segments(snaps(P=(2026, 2027), blocks=(('2030-01-01', 4),)))
    assert yrs.segment.nunique() == 2 and yrs.groupby('segment').period.nunique().max() == 1     # never across periods


def two_segment_network(per_period=True):
    pypsa = pytest.importorskip('pypsa')
    n = pypsa.Network(); n.set_snapshots(snaps()); n.investment_periods = [2026, 2027]
    n.snapshot_weightings = n.snapshot_weightings * 0.0 + 3.0
    n.add('Bus', 'a'); n.add('Carrier', ['gas', 'battery'])
    n.add('Generator', 'g', bus='a', carrier='gas', p_nom=1000, marginal_cost=30, build_year=2025, lifetime=50)
    n.add('StorageUnit', 'bat', bus='a', carrier='battery', p_nom=100, max_hours=4, efficiency_store=1.0, efficiency_dispatch=1.0,
          cyclic_state_of_charge=True, cyclic_state_of_charge_per_period=per_period, build_year=2025, lifetime=30)
    n.add('Load', 'l', bus='a', p_set=500.0)
    n.optimize.create_model(multi_investment_periods=True)
    return n


def _row(m, name):
    c = m.constraints[name]
    v, co = np.asarray(c.lhs.vars.values).ravel(), np.asarray(c.lhs.coeffs.values).ravel()
    return pd.Series(co[v != -1]).groupby(v[v != -1]).sum(), str(np.asarray(c.sign.values).ravel()[0]), float(np.asarray(c.rhs.values).ravel()[0])


def test_pypsa_chains_soc_across_the_gap_and_segment_rows_cut_it():
    import post_v16_mainline as PM
    n = two_segment_network()
    m = n.model
    sns = n.snapshots
    lab = lambda i: int(m['StorageUnit-state_of_charge'].sel(name='bat', snapshot=sns[i]).labels.values)
    eb = m.constraints['StorageUnit-energy_balance'].lhs.sel(name='bat', snapshot=sns[4])     # first snapshot of segment 2 (Feb 20)
    assert lab(3) in set(np.asarray(eb.vars.values).ravel())                               # PyPSA links it to Jan 1 21:00 (the gap)
    info = PM.add_segment_soc_neutrality(n, sns)
    assert info['segments'] == 4 and info['rows'] == 4 and int(len(m.binaries) + len(m.integers)) == 0
    rows = [c for c in m.constraints if c.startswith('A2F08-seg_soc_')]
    pairs = {}
    for c in rows:
        d, sign, rhs = _row(m, c)
        assert sign == '>=' and rhs == 0 and sorted(d.values) == [-1.0, 1.0]
        pairs[int(d.index[d == 1.0][0])] = int(d.index[d == -1.0][0])
    # per-period cyclic: segment 1 ends >= its predecessor (end of segment 2 of the same period), segment 2 ends >= end of segment 1
    assert pairs[lab(3)] == lab(7) and pairs[lab(7)] == lab(3) and pairs[lab(11)] == lab(15) and pairs[lab(15)] == lab(11)


def test_horizon_cyclic_unit_links_across_periods_and_is_cut_too():
    import post_v16_mainline as PM
    n = two_segment_network(per_period=False)
    m, sns = n.model, n.snapshots
    lab = lambda i: int(m['StorageUnit-state_of_charge'].sel(name='bat', snapshot=sns[i]).labels.values)
    info = PM.add_segment_soc_neutrality(n, sns)
    pairs = {}
    for c in [c for c in m.constraints if c.startswith('A2F08-seg_soc_')]:
        d, _, _ = _row(m, c)
        pairs[int(d.index[d == 1.0][0])] = int(d.index[d == -1.0][0])
    assert pairs[lab(11)] == lab(7)                    # 2027 segment 1 starts from the end of 2026 (PyPSA chain) -> now neutral
    assert pairs[lab(3)] == lab(15)                    # horizon cycle closes 2031->2026 equivalent (here 2027 -> 2026)
    assert info['rows'] == 4


def test_four_hour_battery_cannot_carry_energy_across_a_gap():
    """counter-example: charge 400 MWh in segment 1, discharge it during the low-resource segment 2. PyPSA's balance accepts the
    path (chain across the gap); the segment rows reject it"""
    import post_v16_mainline as PM
    n = two_segment_network()
    m, sns = n.model, n.snapshots
    PM.add_segment_soc_neutrality(n, sns)
    for name in m.variables:
        m.variables[name].solution = m[name].labels.copy(data=np.zeros(m[name].labels.shape))
    soc = np.zeros(len(sns)); ps = np.zeros(len(sns)); pdis = np.zeros(len(sns))
    for per0 in (0, 8):
        ps[per0:per0 + 4] = 100 / 3                                      # charge 400 MWh over 4 x 3 h in segment 1
        pdis[per0 + 4:per0 + 8] = 100 / 3                                # 4 x 3 h x 33.3 MW = 400 MWh out in segment 2
        prev = 0.0
        for i in range(per0, per0 + 8):
            soc[i] = prev + 3 * (ps[i] - pdis[i]); prev = soc[i]
    assert abs(soc[3] - 400) < 1e-6 and abs(soc[7]) < 1e-6                 # a 4 h battery, full, then empty: cyclic per period
    for name, vals in (('StorageUnit-state_of_charge', soc), ('StorageUnit-p_store', ps), ('StorageUnit-p_dispatch', pdis)):
        lab = m[name].labels
        m.variables[name].solution = lab.copy(data=vals.reshape(lab.shape) if lab.dims[0] == 'snapshot' else vals.reshape(lab.shape[::-1]).T)
    m.status, m.termination_condition = 'ok', 'optimal'
    eb = m.constraints['StorageUnit-energy_balance']
    assert np.allclose(np.asarray((eb.lhs.solution - eb.rhs).values, dtype=float), 0.0)     # PyPSA's own balance is satisfied
    viol = [c for c in m.constraints if c.startswith('A2F08-seg_soc_')
            and float(np.asarray(m.constraints[c].lhs.solution.values).min()) < -1e-6]
    assert viol                                                            # ... the segment rows are not: the transfer is cut


def test_segment_map_kinds():
    import post_v16_mainline as PM
    pypsa = pytest.importorskip('pypsa')
    n = pypsa.Network(); n.set_snapshots(snaps(P=(2026,), blocks=(('2030-01-01', 4), ('2030-02-20', 8))))
    n.investment_periods = [2026]
    sm = PM.segment_map(n, stress_ts=list(pd.date_range('2030-02-20', periods=8, freq='3h')))
    assert sm.kind.tolist() == ['SAMPLED_WEEK', 'B7_STRESS_ONLY'] and sm.snapshots.tolist() == [4, 8]


# ------------------------------------------------------------------------------------------------ A2-FIX-09
def _cfg(tmp_path, **over):
    c = yaml.safe_load((WF / 'config/config.byop_post_v16_a2.yaml').read_text(encoding='utf-8'))
    c['post_v16'].update(out_dir=str(tmp_path / 'out'), manifest=str(tmp_path / 'MANIFEST.json'), **over)
    p = tmp_path / 'cfg.yaml'
    p.write_text(yaml.safe_dump(c), encoding='utf-8')
    return p


@pytest.fixture
def acct(tmp_path):
    import post_v16_a2_gate as A2G
    cfg = _cfg(tmp_path)
    A2G.arm_accounting(cfg)
    yield A2G, cfg
    A2G.ACCT.update(armed=False, parent=None, stage=None)


def test_budgets_are_separate(acct):
    A2G, cfg = acct
    c = A2G.load(cfg)
    assert A2G.budgets(c) == (2, 3) and 'max_lp_calls' not in c
    assert A2G.CALL_PLAN == {'S0': ['S0_COST'], 'S1_EARLIEST': ['S1_SPEED_HIERARCHY', 'S1_COST']} == c['optimizer_call_plan']


def test_child_calls_need_a_started_parent_and_the_plan(acct):
    A2G, cfg = acct
    _, out, log = A2G.paths(cfg)
    with pytest.raises(SystemExit):                                         # no parent attempt
        A2G.child_start('S0_COST')
    aid = A2G.start_attempt(log, 'S0', 'm', 'b')
    A2G.ACCT.update(parent=aid, stage='S0')
    with pytest.raises(SystemExit):                                         # not in the S0 plan
        A2G.child_start('S1_SPEED_HIERARCHY')
    cid = A2G.child_start('S0_COST', n_vars=10, n_cons=5)
    cl = pd.read_csv(out / 'A2_OPTIMIZER_CALL_LOG.csv', dtype=str)
    assert cl.state.tolist() == ['STARTED'] and cl.parent_attempt_id.tolist() == [aid]   # STARTED written before the call
    with pytest.raises(SystemExit):                                         # same kind twice for one parent (zero retries)
        A2G.child_start('S0_COST')
    A2G.child_finish(cid, state='DONE', status='ok', termination='optimal')
    assert A2G.children_complete(aid, 'S0')[0]


def _wrapped(A2G, cfg, solve0):
    import rearch_mech as R
    return R.post_v16_solve_wrapper(solve0, SimpleNamespace(base='x'), None, cfg_path=cfg, gate_fn=lambda tag: dict(approved=True, reasons=[]),
                                    state={})


def test_injection_hierarchy_failure_marks_child_and_parent_error(acct, tmp_path):
    A2G, cfg = acct
    _, out, log = A2G.paths(cfg)
    out.mkdir(parents=True, exist_ok=True)

    def solve0(config, tag, out_, n):
        A2G.child_start('S1_SPEED_HIERARCHY', n_objectives=12)
        raise RuntimeError('P0-2 lexicographic pre-solve not optimal')
    with pytest.raises(RuntimeError):
        _wrapped(A2G, cfg, solve0)(None, 'S1_EARLIEST', None, None)
    lg, cl = A2G.read_ledger(log), A2G.read_child_log(out / 'A2_OPTIMIZER_CALL_LOG.csv')[0]
    assert lg.state.tolist() == ['ERROR'] and cl.state.tolist() == ['ERROR'] and cl.kind.tolist() == ['S1_SPEED_HIERARCHY']


def test_injection_cost_failure_after_hierarchy_success(acct):
    A2G, cfg = acct
    _, out, log = A2G.paths(cfg)
    out.mkdir(parents=True, exist_ok=True)

    def solve0(config, tag, out_, n):
        cid = A2G.child_start('S1_SPEED_HIERARCHY', n_objectives=12)
        A2G.child_finish(cid, state='DONE', status='ok', termination='optimal')
        A2G.child_start('S1_COST')
        raise RuntimeError('cost stage crashed')
    with pytest.raises(RuntimeError):
        _wrapped(A2G, cfg, solve0)(None, 'S1_EARLIEST', None, None)
    cl = A2G.read_child_log(out / 'A2_OPTIMIZER_CALL_LOG.csv')[0]
    assert cl.set_index('kind').state.to_dict() == {'S1_SPEED_HIERARCHY': 'DONE', 'S1_COST': 'ERROR'}
    assert A2G.read_ledger(log).state.tolist() == ['ERROR']


def test_injection_missing_child_call_fails_acceptance(acct):
    """a 'solve' that returns optimal without any logged optimizer call cannot pass (no unlogged solves)"""
    A2G, cfg = acct
    _, out, log = A2G.paths(cfg)
    out.mkdir(parents=True, exist_ok=True)
    fake_n = SimpleNamespace(model=SimpleNamespace(constraints={}), generators=pd.DataFrame(columns=['carrier']), storage_units=pd.DataFrame(),
                             links=pd.DataFrame(columns=['carrier']))
    with pytest.raises(SystemExit):
        _wrapped(A2G, cfg, lambda *a: dict(status='ok', termination='optimal', integer_vars=0))(None, 'S0', None, fake_n)
    r = json.loads((out / 'S0_RESULT.json').read_text())
    assert r['acceptance']['PASS'] is False and A2G.read_ledger(log).iloc[0]['pass'] == 'False'


def test_injection_crash_second_run_corrupt_ledger_and_skipping_s0(acct, tmp_path):
    A2G, cfg = acct
    _, out, log = A2G.paths(cfg)
    A2G.start_attempt(log, 'S0', 'm', 'b')                                  # crash right after the parent STARTED row
    g = A2G.check('S0', None, cfg_path=cfg)
    assert any('already has a logged call' in r for r in g['reasons'])        # second run refused, the row is kept
    assert any('needs a PASSED S0' in r for r in A2G.check('S1_EARLIEST', None, cfg_path=cfg)['reasons'])
    (out / 'A2_OPTIMIZER_CALL_LOG.csv').write_text('garbage without the columns\n1,2\n')
    assert any('optimizer-call ledger malformed' in r for r in A2G.check('S0', None, cfg_path=cfg)['reasons'])
    log.write_text('\x00\x01 not a csv')
    assert any('ledger' in r for r in A2G.check('S0', None, cfg_path=cfg)['reasons'])
    assert log.exists() and (out / 'A2_OPTIMIZER_CALL_LOG.csv').exists()   # nothing deleted


def test_top_level_budget(acct):
    A2G, cfg = acct
    _, out, log = A2G.paths(cfg)
    for st, kinds in (('S0', ['S0_COST']), ('S1_EARLIEST', ['S1_SPEED_HIERARCHY', 'S1_COST'])):
        aid = A2G.start_attempt(log, st, 'm', 'b'); A2G.ACCT.update(parent=aid, stage=st)
        for k in kinds:
            A2G.child_finish(A2G.child_start(k), state='DONE', status='ok', termination='optimal')
    assert any('top-level optimizer-call budget used' in r for r in A2G.check('S0', None, cfg_path=cfg)['reasons'])


def test_linopy_lock_refuses_outside_wrapper(monkeypatch):
    import linopy
    import rearch_mech as R
    monkeypatch.setattr(R, 'PV16_LOCK', dict(inside=False, armed=False))
    orig = linopy.Model.solve
    try:
        R._arm_post_v16_optimizer_lock()
        with pytest.raises(SystemExit):
            linopy.Model().solve()
        assert R.PV16_LOCK['gurobipy_locked'] is False                     # stated, not claimed
    finally:
        linopy.Model.solve = orig


def test_speed_levels_hold():
    import post_v16_a2_gate as A2G
    lv = [dict(stage='A1', year=2027, value=500.0), dict(stage='A2', year=2027, value=0.4), dict(stage='A1', year=2028, value=800.0)]
    assert A2G.speed_levels_hold(lv, {2027: 500.0, 2028: 800.0})[0]
    ok, rows = A2G.speed_levels_hold(lv, {2027: 499.0, 2028: 800.0})
    assert not ok and [r['ok'] for r in rows] == [False, True]
    assert not A2G.speed_levels_hold([], {})[0]


def test_no_harm_reference_is_strict(tmp_path):
    import post_v16_a2_gate as A2G
    pypsa = pytest.importorskip('pypsa')
    n = pypsa.Network(); n.set_snapshots(snaps(P=(2026,), blocks=(('2030-01-01', 2),))); n.investment_periods = [2026]
    n.add('Bus', 'a'); n.add('Carrier', ['load_shed'])
    n.add('Generator', ['a load_shed', 'b inherited_ramp_unserved'], bus='a', carrier='load_shed', p_nom=1e3, marginal_cost=1e4)
    n.generators_t.p = pd.DataFrame({'a load_shed': [0.0, 1.0], 'b inherited_ramp_unserved': [0.0, 0.0]}, index=n.snapshots)
    rec = A2G.write_no_harm_reference(n, tmp_path)
    (tmp_path / 'S0_RESULT.json').write_text(json.dumps(dict(no_harm_reference=rec)))
    n_model = SimpleNamespace(constraints={})
    n2 = SimpleNamespace(generators=n.generators, generators_t=n.generators_t, snapshots=n.snapshots, model=n_model)
    chk, val = A2G.no_harm_check(n2, tmp_path)
    assert chk['no_harm_reference_sha_ok'] and chk['no_harm_units_match'] and chk['no_harm_snapshots_match'] and chk['no_harm_ok']
    assert chk['no_harm_row_built_from_reference'] is False                 # the D24 row must be in the model
    p = tmp_path / A2G.NO_HARM_REF
    p.write_text(p.read_text() + '#')                                       # tampered reference
    assert not A2G.no_harm_check(n2, tmp_path)[0]['no_harm_reference_sha_ok']
