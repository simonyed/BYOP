"""NEXT-04 Option 1: the A1 post-solve path (solution reader, saver, writers, acceptance, RESULT.json, ledger) on the REAL LP-R
model with an INJECTED solution. No solver is ever called (linopy.Model.solve refused; the 'solve' is a fake function); every
file goes to a pytest tmp directory, never to POST_V16_A1_HEADROOM/. Needs the v1.6 baseline (L2)."""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
for p_ in ('model', 'run'):
    sys.path.insert(0, str(WF / 'byop' / p_))
import byop_paths as BP  # noqa: E402

need_base = pytest.mark.skipif(not BP.BASE_TAMU_V16.exists(), reason='v1.6 baseline .nc only on L2')


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def inject(n, lam=123.0):
    """a hand-made 'solution': zeros everywhere, lambda = lam; then PyPSA's own assign_solution (as after a real solve)"""
    m = n.model
    for k in m.variables:
        lab = m[k].labels
        vals = np.zeros(lab.shape) if lab.ndim else np.array(0.0)
        m.variables[k].solution = lab.copy(data=vals)
    m.variables['PV16-lambda'].solution = m['PV16-lambda'].labels.copy(data=np.array(lam))
    m.status, m.termination_condition = 'ok', 'optimal'
    n.optimize.assign_solution()


@need_base
def test_solution_view_frames_have_only_their_own_names():
    import post_v16_a1 as A
    n, info, cfg = A.build('R', BP.BASE_TAMU_V16)
    inject(n)
    v = A.solution_view(n, dict(info, reserve_MW=3000, tau_h=1))
    assert set(v['r_su'].columns) == set(n.storage_units.index) and v['r_su'].shape == (432, len(n.storage_units))
    assert set(v['r_thermal'].columns) == set(n.model['PV16-res_thermal'].labels.coords['name'].values)
    assert set(v['r_thermal'].columns) <= set(n.generators.index) and not v['r_thermal'].isna().any().any()
    assert v['lam'] == 123.0
    # the defect it replaces: the merged Dataset pads every variable with all component names
    merged = n.model.solution['PV16-res_su'].to_pandas()
    assert merged.shape[1] > len(n.storage_units)


@need_base
def test_full_post_solve_path_with_injected_solution(tmp_path, monkeypatch):
    import post_v16_a1 as A
    built = {}
    b0 = A.build

    def build(mode, base):
        n, info, cfg = b0(mode, base)
        built['n'] = n
        return n, info, cfg

    def fake_solve(**kw):                                           # stands in for n.optimize.solve_model; no solver
        inject(built['n'], lam=500.0)
        return 'ok', 'optimal'
    monkeypatch.setattr(A, 'build', build)
    monkeypatch.setattr(A, 'OUT', tmp_path)
    monkeypatch.setattr(A, 'LOG', tmp_path / 'HEADROOM_SOLVE_LOG.csv')
    monkeypatch.setattr(A.G, 'check', lambda *a, **k: dict(approved=True, reasons=[], stage='LP_R_H_RESOURCE'))
    with pytest.raises(SystemExit) as ex:                            # zero dispatch cannot meet load / reserve -> acceptance fails
        A.lp('R', BP.BASE_TAMU_V16, 1, solve_fn=fake_solve)
    assert 'acceptance_failed' in str(ex.value)                      # NOT output_failed: the post-solve path itself works
    r = json.loads((tmp_path / 'LP_R_H_RESOURCE_RESULT.json').read_text())
    assert r['outputs_written'] is True and 'output_error' not in r and r['failure_class'] == 'acceptance_failed'
    assert r['lambda_facility_MW'] == 500.0
    for k in ('existing_shed_MWh_B0', 'existing_shed_MWh_BL', 'reserve_min_slack_MW', 'balance_residual_max_abs_MW'):
        assert isinstance(r[k], float) and np.isfinite(r[k])           # every acceptance input was computed
    assert r['acceptance']['checks']['reserve_met'] is False and r['acceptance']['checks']['lambda_finite_nonneg'] is True
    sv = r['saved_solution']                                          # saved BEFORE the writers ran
    assert 'network_sha256' in sv and Path(sv['network']).exists() and 'pv16_variables_error' not in sv
    assert (tmp_path / 'LP_R_H_RESOURCE_SOLUTION' / 'PV16-res_su.csv').exists()
    for f in ('HEADROOM_BY_BUS', 'STRESS_DISPATCH_RESERVE_QA', 'NETWORK_PRESSURE_DIAGNOSTICS'):
        assert (tmp_path / f'{f}_LP_R_H_RESOURCE.csv').exists()
    lg = pd.read_csv(tmp_path / 'HEADROOM_SOLVE_LOG.csv', dtype=str)
    assert lg.state.tolist() == ['DONE'] and lg['pass'].tolist() == ['False'] and lg.failure_class.tolist() == ['acceptance_failed']


def test_gate_pins_prior_ledgers(tmp_path):
    """the rerun is refused if the first attempt's ledger is missing / changed, or if it is reused as the current ledger"""
    import yaml
    import post_v16_gate as G
    c = yaml.safe_load((WF / 'config/config.byop_post_v16_a1.yaml').read_text(encoding='utf-8'))
    prior = c['post_v16']['prior_ledgers']
    assert c['post_v16']['run_dir'] == 'rerun1' and len(prior) == 2
    old = tmp_path / 'old.csv'
    old.write_text('attempt_id,stage,attempt,state,status,termination,pass\nLP_R_H_RESOURCE#1,LP_R_H_RESOURCE,1,DONE,ok,optimal,False\n')
    c['post_v16']['prior_ledgers'] = [dict(path=str(old), sha256=G.sha(old))]
    cfg = tmp_path / 'cfg.yaml'
    cfg.write_text(yaml.safe_dump(c), encoding='utf-8')
    ok = G.check(cfg, 'LP_R_H_RESOURCE', None, tmp_path / 'rerun1' / 'HEADROOM_SOLVE_LOG.csv', root=Path('/'))
    assert not any('prior ledger' in r for r in ok['reasons'])
    same = G.check(cfg, 'LP_R_H_RESOURCE', None, old, root=Path('/'))
    assert any('closed prior ledger' in r for r in same['reasons'])
    old.write_text(old.read_text().replace('False', 'True'))           # tampered evidence
    bad = G.check(cfg, 'LP_R_H_RESOURCE', None, tmp_path / 'rerun1' / 'HEADROOM_SOLVE_LOG.csv', root=Path('/'))
    assert any('missing or changed' in r for r in bad['reasons'])
