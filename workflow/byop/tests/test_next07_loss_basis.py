"""NEXT-07 W6 static tests: lossy 2025 LP2 re-validation runner and gate (zero solver)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/run')); sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/build'))
CFG = WF / 'config/config.byop_loss_basis_lp2.yaml'


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def test_config_locked_and_separate_from_v16():
    import loss_basis_lp2 as L
    import baseline_v16_calibration as V16
    import post_v16_a2_gate as A2G
    c = L.load()
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_by'] is None and c['approved_git_sha'] is None
    assert c['stages'] == L.STAGES and int(c['max_lp_calls']) == 2 and int(c['max_retries']) == 0 and int(c['transmission_losses']) == 2
    v, _ = V16.load_cfg()
    assert c['out_dir'] != v['out_dir'] and set(L.STAGES).isdisjoint(V16.STAGES)       # never the consumed v1.6 ledger
    src = WF.parent / c['authorization_source']
    assert A2G.file_shas(src)['lf'] == c['authorization_source_sha256']
    g = L.check('LP2_LOSSY_ASIS')
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons']


def tmp_cfg(tmp_path):
    raw = yaml.safe_load(CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str(tmp_path / 'lb')
    p = tmp_path / 'config.byop_loss_basis_lp2.yaml'
    p.write_text(yaml.safe_dump(raw), encoding='utf-8')
    return p


@pytest.mark.parametrize('rows, refused', [
    ([], True),                                                                                     # no ASIS yet
    ([dict(stage='LP2_LOSSY_ASIS', state='DONE', termination='optimal', acceptance_pass='True')], True),    # ASIS passed: no repair
    ([dict(stage='LP2_LOSSY_ASIS', state='ERROR', termination='', acceptance_pass='')], True),      # ASIS failed to solve
    ([dict(stage='LP2_LOSSY_ASIS', state='DONE', termination='optimal', acceptance_pass='False')], False),  # ASIS failed acceptance
])
def test_r_parallel_only_after_failed_asis(tmp_path, rows, refused):
    import loss_basis_lp2 as L
    p = tmp_cfg(tmp_path)
    c = L.load(p)
    if rows:
        lp, _ = L.ledger(c); lp.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([{**{k: '' for k in L.LOG_COLS}, 'attempt_id': 'LP2_LOSSY_ASIS#1', **r} for r in rows])[L.LOG_COLS].to_csv(lp, index=False)
    reasons = L.check('LP2_LOSSY_R_PARALLEL', cfg_path=p)['reasons']
    assert any('only after an optimal LP2_LOSSY_ASIS that FAILED' in r for r in reasons) is refused


def test_zero_retries_and_budget(tmp_path):
    import loss_basis_lp2 as L
    p = tmp_cfg(tmp_path)
    c = L.load(p)
    lp, _ = L.ledger(c); lp.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{**{k: '' for k in L.LOG_COLS}, 'attempt_id': 'LP2_LOSSY_ASIS#1', 'stage': 'LP2_LOSSY_ASIS', 'state': 'ERROR'}])[L.LOG_COLS].to_csv(lp, index=False)
    assert any('zero retries' in r for r in L.check('LP2_LOSSY_ASIS', cfg_path=p)['reasons'])


def test_r_parallel_changes_only_resistance_of_uplifted_lines():
    pypsa = pytest.importorskip('pypsa')
    import loss_basis_lp2 as L

    def net(s):
        n = pypsa.Network(); n.add('Bus', ['a', 'b', 'c'], v_nom=230.0)
        n.add('Line', 'L1', bus0='a', bus1='b', s_nom=s[0], x=50.0, r=10.0)
        n.add('Line', 'L2', bus0='b', bus1='c', s_nom=s[1], x=40.0, r=8.0)
        return n
    raw, n = net([100.0, 200.0]), net([400.0, 200.0])           # L1 uplifted x4, L2 untouched
    t = L.r_parallel(n, raw)
    assert list(t.index) == ['L1'] and n.lines.r['L1'] == pytest.approx(2.5) and n.lines.r['L2'] == 8.0
    assert n.lines.x.tolist() == [50.0, 40.0] and n.lines.s_nom.tolist() == [400.0, 200.0]     # x and capacity unchanged


def test_runner_uses_lossy_basis_and_never_touches_v16_outputs():
    src = (WF / 'byop/run/loss_basis_lp2.py').read_text(encoding='utf-8')
    assert "n.optimize.create_model(transmission_losses=int(c['transmission_losses']))" in src
    assert 'BASELINE_V16_SOLVE_LOG' not in src and "V16.log_call" not in src and "V16.lp2(" not in src
    assert "d16 / 'baseline_2025_tamu_prepared.nc'" in src and '.to_netcdf' not in src and '.export_to_netcdf' not in src


# ------------------------------------------------------------------------------------------------ zero-solver post-processing
def tiny_build(stage, c):
    """small lossy fixed-asset network shaped like the LP2 one (MultiIndex snapshots, V16 shed units, storage)"""
    pypsa = pytest.importorskip('pypsa')
    import baseline_v16_calibration as V16
    v, _ = V16.load_cfg()
    mi = pd.MultiIndex.from_product([[2030], pd.date_range('2030-01-01', periods=8, freq='3h')], names=['period', 'timestep'])
    n = pypsa.Network(); n.set_snapshots(mi); n.investment_periods = [2030]
    n.snapshot_weightings = n.snapshot_weightings * 0.0 + 3.0
    n.add('Bus', ['a', 'b'], v_nom=230.0); n.add('Carrier', ['gas', 'battery', 'load_shed', 'AC'])
    n.add('Generator', 'a gas', bus='a', carrier='gas', p_nom=500, marginal_cost=30)
    n.add('Generator', ['a V16 shed', 'b V16 shed'], bus=['a', 'b'], carrier='load_shed', p_nom=1e5, marginal_cost=35685)
    n.add('StorageUnit', 'b bat', bus='b', carrier='battery', p_nom=50, max_hours=4, cyclic_state_of_charge=True)
    n.add('Line', ['TL35', 'TL43'], bus0='a', bus1='b', s_nom=[300, 100], s_max_pu=0.7, x=[50, 40], r=[10, 8], carrier='AC')
    n.add('Load', 'l', bus='b', p_set=200.0)
    rtab = None
    if stage == 'LP2_LOSSY_R_PARALLEL':
        import loss_basis_lp2 as L
        raw = n.copy(); raw.lines['s_nom'] = [100.0, 100.0]
        rtab = L.r_parallel(n, raw)
    n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
    return n, dict(generators=3), rtab, v


@pytest.mark.parametrize('stage', ['LP2_LOSSY_ASIS', 'LP2_LOSSY_R_PARALLEL'])
def test_full_post_solve_path_with_injected_solution(tmp_path, monkeypatch, stage):
    """A1 lesson: the complete output path (PyPSA assign_solution / duals / post_processing, Line-loss read from the linopy
    solution, metrics, acceptance, every file, ledger STARTED -> DONE) runs on an injected solution before any real solve"""
    import linopy
    import fake_solve as F
    import loss_basis_lp2 as L
    monkeypatch.setattr(linopy.Model, 'solve', F.fake_solve)
    p = tmp_cfg(tmp_path)
    qa = L.run(stage, 2, cfg_path=p, gate_fn=lambda s: dict(approved=True, reasons=['TEST_INJECTED']), build_fn=tiny_build)
    od = tmp_path / 'lb' / stage
    for f in ('LOSS_BASIS_LP2_QA.json', 'shedding_events.csv', 'lines.csv', 'generation_by_carrier.csv', 'shed_by_bus.csv.gz',
              'line_flow_p0.csv.gz', 'line_loss.csv.gz'):
        assert (od / f).exists(), f
    assert (od / 'R_PARALLEL_CHANGES.csv').exists() == (stage == 'LP2_LOSSY_R_PARALLEL')
    assert qa['losses']['total_loss_MWh'] == pytest.approx(2 * 8 * 3.0)               # 2 lines x 8 snapshots x 1 MW x 3 h (injected)
    assert qa['acceptance']['eens_MWh'] == pytest.approx(2 * 8 * 3.0) and qa['acceptance_pass'] is True   # 48 MWh < 4,882
    assert set(qa['key_lines']) == {'TL35', 'TL43'} and qa['key_lines']['TL35']['loss_MWh'] == pytest.approx(24.0)
    lp = pd.read_csv(tmp_path / 'lb' / 'LOSS_BASIS_LP2_SOLVE_LOG.csv', dtype=str, keep_default_na=False)
    assert list(lp.state) == ['DONE'] and list(lp.termination) == ['optimal'] and list(lp.acceptance_pass) == ['True']


def test_line_loss_frame_refuses_partial_solution():
    pypsa = pytest.importorskip('pypsa')
    import loss_basis_lp2 as L
    n, *_ = tiny_build('LP2_LOSSY_ASIS', dict(transmission_losses=2))
    m = n.model
    v = m.variables['Line-loss']
    v.solution = (v.labels * 0.0 + 1.0).where(v.labels >= 0)
    m.status = 'ok'
    assert L.line_loss_frame(n).shape == (8, 2)
    sol = v.solution.copy(); sol[0, 0] = np.nan; v.solution = sol
    with pytest.raises(ValueError, match='does not cover'):
        L.line_loss_frame(n)
