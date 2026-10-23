"""NEXT-08 static tests: lossy 2025 LP1 calibration chain (zero solver: fake_solve writes synthetic solutions)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
for d in ('byop/run', 'byop/model', 'byop/build', 'byop/tests'):
    sys.path.insert(0, str(WF / d))
CFG = WF / 'config/config.byop_lossy_lp1.yaml'


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def test_config_locked_budget_and_rules():
    import loss_basis_lp1 as L
    import post_v16_a2_gate as A2G
    c = L.load()
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_by'] is None and c['approved_git_sha'] is None
    assert c['stages'] == L.STAGES and int(c['max_lp_calls']) == 3 and int(c['max_retries']) == 0 and int(c['transmission_losses']) == 2
    assert float(c['cap_factor']) == 2.0 and c['guards'] == {'G1_factor': 1.5, 'G3_max_MVA': 1000.0}
    assert A2G.file_shas(WF.parent / c['authorization_source'])['lf'] == c['authorization_source_sha256']
    assert c['out_dir'] not in ('results/BYOP/baseline_2025_tamu_v16', 'results/BYOP/next07_loss_basis')       # never an old ledger
    g = L.check('LP1_LOSSY_IT1')
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons']


def tmp_cfg(tmp_path):
    raw = yaml.safe_load(CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str(tmp_path / 'lp1')
    p = tmp_path / 'config.byop_lossy_lp1.yaml'
    p.write_text(yaml.safe_dump(raw), encoding='utf-8')
    return p


def write_ledger(L, c, rows):
    p, _ = L.ledger(c); p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{**{k: '' for k in L.LOG_COLS}, **r} for r in rows], columns=L.LOG_COLS).to_csv(p, index=False)


@pytest.mark.parametrize('rows, it2_refused, lp2_refused', [
    ([], True, True),
    ([dict(attempt_id='LP1_LOSSY_IT1#1', stage='LP1_LOSSY_IT1', state='DONE', termination='optimal', r_converged='False', guards_pass='True')], False, True),
    ([dict(attempt_id='LP1_LOSSY_IT1#1', stage='LP1_LOSSY_IT1', state='DONE', termination='optimal', r_converged='True', guards_pass='True')], True, False),
    ([dict(attempt_id='LP1_LOSSY_IT1#1', stage='LP1_LOSSY_IT1', state='DONE', termination='optimal', r_converged='True', guards_pass='False')], True, True),
    ([dict(attempt_id='LP1_LOSSY_IT1#1', stage='LP1_LOSSY_IT1', state='DONE', termination='optimal', r_converged='False', guards_pass='True'),
      dict(attempt_id='LP1_LOSSY_IT2#1', stage='LP1_LOSSY_IT2', state='DONE', termination='optimal', r_converged='False', guards_pass='True')], True, True),
    ([dict(attempt_id='LP1_LOSSY_IT1#1', stage='LP1_LOSSY_IT1', state='ERROR', termination='')], True, True),
])
def test_stage_order(tmp_path, rows, it2_refused, lp2_refused):
    import loss_basis_lp1 as L
    p = tmp_cfg(tmp_path); c = L.load(p)
    write_ledger(L, c, rows)
    (L.out_dir(c) / L.CANDIDATE_NC).parent.mkdir(parents=True, exist_ok=True)
    (L.out_dir(c) / L.CANDIDATE_NC).write_bytes(b'placeholder')
    r2 = L.check('LP1_LOSSY_IT2', cfg_path=p)['reasons']; r3 = L.check('LP2_LOSSY_CANDIDATE', cfg_path=p)['reasons']
    assert any('only after an optimal LP1_LOSSY_IT1 that is NOT r-converged' in x or 'already has a logged call' in x for x in r2) is it2_refused
    assert any('only after an optimal, r-converged LP1' in x for x in r3) is lp2_refused


def test_r_proxy_convergence_and_guards():
    import loss_basis_lp1 as L
    idx = ['A', 'B', 'C']
    s_raw = pd.Series([100.0, 100.0, 100.0], idx); r_raw = pd.Series([10.0, 10.0, 10.0], idx)
    assert L.r_proxy(r_raw, s_raw, pd.Series([400.0, 100.0, 50.0], idx)).tolist() == [2.5, 10.0, 10.0]   # never above raw
    ok, info = L.convergence(pd.Series([400.0, 100.0, 100.0], idx), pd.Series([400.0, 100.0, 100.0], idx), s_raw, 0.05, 10.0)
    assert ok and info['lines_not_converged'] == 0
    ok, info = L.convergence(pd.Series([600.0, 100.0, 100.0], idx), pd.Series([400.0, 100.0, 100.0], idx), s_raw, 0.05, 10.0)
    assert not ok and list(info['worst']) == ['A']
    prep = pd.Series([400.0, 100.0, 100.0], idx); smax = 2 * prep
    g = L.guards(pd.Series([450.0, 100.0, 120.0], idx), s_raw, prep, smax, {'G1_factor': 1.5, 'G3_max_MVA': 1000.0})
    assert g['all_pass'] and g['new_lines'] == {'C': 20.0}
    g = L.guards(pd.Series([800.0, 100.0, 100.0], idx), s_raw, prep, smax, {'G1_factor': 1.5, 'G3_max_MVA': 1000.0})
    assert not g['G1'] and not g['G2'] and g['lines_at_cap'] == ['A']                                      # 700 > 450, at cap
    g = L.guards(pd.Series([400.0, 100.0, 180.0], idx), s_raw, prep, smax, {'G1_factor': 3.0, 'G3_max_MVA': 50.0})
    assert not g['G3'] and g['new_lines_over_50MVA'] == ['C']


def tiny_raw(path):
    pypsa = pytest.importorskip('pypsa')
    mi = pd.MultiIndex.from_product([[2030], pd.date_range('2030-01-01', periods=8, freq='3h')], names=['period', 'timestep'])
    n = pypsa.Network(); n.set_snapshots(mi); n.investment_periods = [2030]
    n.snapshot_weightings = n.snapshot_weightings * 0.0 + 3.0
    n.add('Bus', ['a', 'b', 'c'], v_nom=230.0); n.add('Carrier', ['gas', 'battery', 'AC', 'load_shed'])
    n.add('Generator', 'a gas', bus='a', carrier='gas', p_nom=900, marginal_cost=30, build_year=2020)
    n.add('Generator', 'a new', bus='a', carrier='gas', p_nom_extendable=True, capital_cost=1e5, build_year=2027)
    n.add('StorageUnit', 'c bat', bus='c', carrier='battery', p_nom=50, max_hours=4, build_year=2020)
    n.add('Line', ['TL35', 'TL43', 'TL44'], bus0=['a', 'a', 'b'], bus1=['b', 'c', 'c'], s_nom=[100.0, 100.0, 80.0], s_max_pu=0.7,
          x=[50.0, 40.0, 30.0], r=[10.0, 8.0, 6.0], carrier='AC')
    n.add('Load', ['lb', 'lc'], bus=['b', 'c'], p_set=[150.0, 120.0])
    n.export_to_netcdf(str(path))
    return path


def test_prepare_lp1_matches_v16_calibrate_2025(tmp_path, monkeypatch):
    """the lossless part of the new LP1 equals the v1.6 LP1 model statement by statement: run the ORIGINAL calibrate_2025 with the
    fake solve and compare its model size with prepare_lp1 (lossless, cap infinite-equivalent); then check the three changes"""
    import linopy
    import fake_solve as F
    import build_2025_baseline_tamu as B
    import loss_basis_lp1 as L
    monkeypatch.setattr(linopy.Model, 'solve', F.fake_solve)
    raw = tiny_raw(tmp_path / 'raw.nc')
    det = {}
    B.calibrate_2025(str(raw), 1, detail=det)
    pypsa = pytest.importorskip('pypsa')
    s_prep = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
    n0, _ = L.prepare_lp1(raw, s_prep, 2.0, s_prep)
    n0.lines['s_nom_max'] = np.inf
    n0.optimize.create_model()                                       # lossless, uncapped: must equal the v1.6 LP1 model exactly
    assert (int(n0.model.nvars), int(n0.model.ncons)) == (det['n_vars'], det['n_cons'])
    assert sorted(n0.model.variables) == sorted(det['linopy_variables'])
    n, info = L.prepare_lp1(raw, s_prep, 2.0, s_prep)
    n.optimize.create_model()                                        # + finite cap: exactly one upper-bound row per line more
    assert int(n.model.nvars) == det['n_vars'] and int(n.model.ncons) == det['n_cons'] + len(n.lines)
    assert 'a new' not in n.generators.index and n.generators.carrier.eq('load_shed').sum() == 2
    assert n.lines.s_nom_min.tolist() == [100.0, 100.0, 80.0] and set(n.lines.capital_cost) == {L.UPLIFT_COST} and n.lines.s_nom_extendable.all()
    assert n.lines.s_nom_max.tolist() == [800.0, 300.0, 160.0]                            # change 2: 2 x v1.6 capacity
    assert n.lines.r.tolist() == [2.5, pytest.approx(8.0 * 100 / 150), 6.0] and n.lines.x.tolist() == [50.0, 40.0, 30.0]   # change 3; x raw
    n2, _ = L.prepare_lp1(raw, s_prep, 2.0, s_prep)
    n2.optimize.create_model(transmission_losses=2)                                      # change 1
    assert 'Line-loss' in n2.model.variables and sum(k.startswith('Line-loss') for k in n2.model.constraints) == 5


def test_full_chain_zero_solver(tmp_path, monkeypatch):
    """IT1 (r from v1.6 capacities; the fake 'solution' keeps raw capacities -> not r-converged) -> IT2 (r from the IT1 solution ->
    converged, guards pass) -> candidate NetCDF written -> LP2 on the candidate; every ledger row, file and gate decision checked"""
    import linopy
    import fake_solve as F
    import loss_basis_lp1 as L
    pypsa = pytest.importorskip('pypsa')
    monkeypatch.setattr(linopy.Model, 'solve', F.fake_solve)
    raw = tiny_raw(tmp_path / 'raw.nc')
    s_prep = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
    p = tmp_cfg(tmp_path); c = L.load(p)
    import baseline_v16_calibration as V16
    v, _ = V16.load_cfg()

    def lp1_build(stage, c_):
        s_ref = s_prep if stage == 'LP1_LOSSY_IT1' else pd.read_csv(L.out_dir(c_) / 'LP1_LOSSY_IT1' / 'LP1_LINE_SOLUTION.csv', index_col=0).s_nom_opt
        n, info = L.prepare_lp1(raw, s_ref, 2.0, s_prep)
        n.optimize.create_model(transmission_losses=2)
        return n, dict(info, s_ref=s_ref, s_prep=s_prep, raw_nc=raw), v

    def gate(stage):                                   # the REAL stage-order rules; approval / SHA / manifest reasons dropped (test)
        g = L.check(stage, cfg_path=p)
        keep = [x for x in g['reasons'] if x.startswith((stage, 'LP2_LOSSY_CANDIDATE only', 'LP1_LOSSY_IT2 only', 'candidate', 'LP budget')) or 'already has' in x]
        return dict(g, approved=not keep, reasons=keep)
    q1 = L.run('LP1_LOSSY_IT1', 1, cfg_path=p, gate_fn=gate, lp1_build=lp1_build)
    assert q1['r_converged'] is False and q1['candidate_written'] is False and q1['guards']['all_pass']
    q2 = L.run('LP1_LOSSY_IT2', 1, cfg_path=p, gate_fn=gate, lp1_build=lp1_build)
    assert q2['r_converged'] is True and q2['candidate_written'] is True
    cand = pypsa.Network(str(L.out_dir(c) / L.CANDIDATE_NC))
    assert cand.lines.s_nom.tolist() == [100.0, 100.0, 80.0] and cand.lines.r.tolist() == [10.0, 8.0, 6.0] and cand.lines.x.tolist() == [50.0, 40.0, 30.0]
    q3 = L.run('LP2_LOSSY_CANDIDATE', 1, cfg_path=p, gate_fn=gate)
    assert q3['transmission_losses'] == 2 and (L.out_dir(c) / 'LP2_LOSSY_CANDIDATE' / 'line_loss.csv.gz').exists()
    lg = pd.read_csv(L.ledger(c)[0], dtype=str, keep_default_na=False)
    assert list(lg.stage) == L.STAGES and set(lg.state) == {'DONE'} and list(lg.r_converged) == ['False', 'True', '']
    with pytest.raises(SystemExit):                    # zero retries: every stage refused now
        L.run('LP1_LOSSY_IT1', 1, cfg_path=p, gate_fn=gate, lp1_build=lp1_build)
    assert raw.exists() and pypsa.Network(str(raw)).lines.s_nom.tolist() == [100.0, 100.0, 80.0]          # input network untouched


def test_invalid_capacity_solution_fails_closed(tmp_path, monkeypatch):
    """a -inf / below-raw s_nom_opt must stop the stage (ERROR row), never feed guards, r or a candidate"""
    import linopy
    import loss_basis_lp1 as L
    import baseline_v16_calibration as V16

    def bad_solve(self, *a, **k):
        for nm in self.variables:
            v = self.variables[nm]
            v.solution = (v.labels * 0.0 + (-np.inf if nm == 'Line-s_nom' else 0.0)).where(v.labels >= 0)
        for nm in self.constraints:
            self.constraints[nm].dual = (self.constraints[nm].labels * 0.0).where(self.constraints[nm].labels >= 0)
        self.status, self.termination_condition = 'ok', 'optimal'
        self.objective._value = 0.0
        return 'ok', 'optimal'
    monkeypatch.setattr(linopy.Model, 'solve', bad_solve)
    raw = tiny_raw(tmp_path / 'raw.nc')
    s_prep = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
    p = tmp_cfg(tmp_path); c = L.load(p)
    v, _ = V16.load_cfg()

    def lp1_build(stage, c_):
        n, info = L.prepare_lp1(raw, s_prep, 2.0, s_prep)
        n.optimize.create_model(transmission_losses=2)
        return n, dict(info, s_ref=s_prep, s_prep=s_prep, raw_nc=raw), v
    with pytest.raises(ValueError, match='capacity solution invalid'):
        L.run('LP1_LOSSY_IT1', 1, cfg_path=p, gate_fn=lambda s: dict(approved=True, reasons=[]), lp1_build=lp1_build)
    lg = pd.read_csv(L.ledger(c)[0], dtype=str, keep_default_na=False)
    assert list(lg.state) == ['ERROR'] and not (L.out_dir(c) / L.CANDIDATE_NC).exists()
