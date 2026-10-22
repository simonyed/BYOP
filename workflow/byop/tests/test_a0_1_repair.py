"""A0.1 repair (A0.2 package P1) static tests: FIX-01 strict max lambda + hard zero shed, FIX-02 LP-R PASS gate / A1 acceptance,
FIX-03 STARTED-before-solve ledger, FIX-04 failure classes. Fault injection uses fake solve functions and a fake network;
NO optimizer is called (the autouse fixture makes any real solve fail the test)."""
from __future__ import annotations

import json, sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
for p in ('model', 'run'):
    sys.path.insert(0, str(WF / 'byop' / p))
import post_v16_a1 as A  # noqa: E402


@pytest.fixture(autouse=True)
def no_solver(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('real solver called in an A0.1 test')
    try:
        import linopy
        monkeypatch.setattr(linopy.Model, 'solve', boom)
    except ImportError:
        pass
    yield


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """runner writes into tmp; gate approved; build() returns a fake network (no pypsa, no model)"""
    monkeypatch.setattr(A, 'OUT', tmp_path)
    monkeypatch.setattr(A, 'LOG', tmp_path / 'HEADROOM_SOLVE_LOG.csv')
    monkeypatch.setattr(A.G, 'check', lambda *a, **k: dict(approved=True, reasons=[]))
    base = tmp_path / 'base.nc'; base.write_bytes(b'v16')
    man = tmp_path / 'man.json'; man.write_text('{}')
    monkeypatch.setattr(A.G, 'load', lambda *a, **k: dict(manifest=str(man)))
    cfg = dict(solver='gurobi', solver_options={}, reserve=dict(requirement_MW=3000, tau_h=1), headroom=dict(lambda_upper_MW=200000.0),
               acceptance=dict(h_network_le_h_resource_tol_MW=1e-3))
    fake_n = SimpleNamespace(optimize=SimpleNamespace(solve_model=lambda **k: (_ for _ in ()).throw(AssertionError('default solver path used'))))
    info = dict(structure={}, headroom={})
    monkeypatch.setattr(A, 'build', lambda mode, b: (fake_n, info, cfg))
    return tmp_path, base


def good_outputs(monkeypatch, lam=500.0, shed_bl=0.0, resid=1e-9):
    monkeypatch.setattr(A, 'solution_view', lambda n, info: None)
    monkeypatch.setattr(A, 'write_outputs', lambda v, out, tag: dict(lambda_facility_MW=lam, lambda_IT_MW=lam / 1.1484, existing_shed_MWh_B0=0.0,
                                                                   existing_shed_MWh_BL=shed_bl, reserve_min_slack_MW=0.0))
    monkeypatch.setattr(A, 'balance_residual', lambda n: resid)


# ------------------------------------------------------------------------------------------------ FIX-03 / FIX-04
def test_started_row_is_persisted_before_the_solver_and_consumes_the_call(sandbox, monkeypatch):
    out, base = sandbox
    seen = {}

    def crash(**k):                                  # the ledger must already hold STARTED when the solver is entered
        lg = A.read_ledger()
        seen['rows'] = lg.to_dict(orient='records')
        raise KeyboardInterrupt('killed')
    with pytest.raises(SystemExit, match='solver_failed'):
        A.lp('R', str(base), 1, solve_fn=crash)
    assert seen['rows'][0]['state'] == 'STARTED' and seen['rows'][0]['stage'] == 'LP_R_H_RESOURCE'
    lg = A.read_ledger()
    assert len(lg) == 1 and lg.state[0] == 'ERROR' and lg.failure_class[0] == 'solver_failed' and lg['pass'][0] == 'False'
    assert lg.base_sha256[0] and lg.manifest_sha256[0]                          # base / code SHA recorded
    r = json.loads((out / 'LP_R_H_RESOURCE_RESULT.json').read_text())
    assert r['acceptance']['PASS'] is False


def test_leftover_started_row_blocks_rerun_and_budget(tmp_path):
    import post_v16_gate as G
    log = tmp_path / 'HEADROOM_SOLVE_LOG.csv'
    A.start_attempt('LP_R_H_RESOURCE', 'm', 'b', path=log)                      # process died after STARTED
    lg, prob = G.solve_log_rows(log)
    assert prob is None and lg.state.tolist() == ['STARTED']
    assert (lg.stage == 'LP_R_H_RESOURCE').any()                                # gate rule: any row consumes the stage
    A.start_attempt('LP_N_H_NETWORK', 'm', 'b', path=log)
    assert len(G.solve_log_rows(log)[0]) == 2                                   # budget of 2 used, deleting rows is the only bypass
    A.finish_attempt('LP_R_H_RESOURCE#1', path=log, state='ERROR')
    lg2 = G.solve_log_rows(log)[0]
    assert len(lg2) == 2 and lg2.state.tolist() == ['ERROR', 'STARTED']         # finish fills the same row, adds none


@pytest.mark.parametrize('term,cls', [('infeasible', 'baseline_pressure_infeasible_resource_side'), ('suboptimal', 'solver_failed')])
def test_nonoptimal_classified_and_blocked(sandbox, monkeypatch, term, cls):
    out, base = sandbox
    with pytest.raises(SystemExit, match=cls):
        A.lp('R', str(base), 1, solve_fn=lambda **k: ('warning', term))
    lg = A.read_ledger()
    assert lg.state[0] == 'DONE' and lg.failure_class[0] == cls and lg['pass'][0] == 'False'


def test_output_failure_is_not_pass(sandbox, monkeypatch):
    out, base = sandbox
    monkeypatch.setattr(A, 'solution_view', lambda n, info: (_ for _ in ()).throw(RuntimeError('post-processing broke')))
    with pytest.raises(SystemExit, match='output_failed'):
        A.lp('R', str(base), 1, solve_fn=lambda **k: ('ok', 'optimal'))
    r = json.loads((out / 'LP_R_H_RESOURCE_RESULT.json').read_text())
    assert r['failure_class'] == 'output_failed' and r['acceptance']['PASS'] is False


def test_optimal_with_positive_shed_or_residual_or_cap_fails_acceptance(sandbox, monkeypatch):
    out, base = sandbox
    good_outputs(monkeypatch, shed_bl=5.0)
    with pytest.raises(SystemExit, match='acceptance_failed'):
        A.lp('R', str(base), 1, solve_fn=lambda **k: ('ok', 'optimal'))
    acc = json.loads((out / 'LP_R_H_RESOURCE_RESULT.json').read_text())['acceptance']
    assert acc['checks']['existing_shed_zero_BL'] is False and acc['PASS'] is False
    s = dict(status='ok', termination='optimal', outputs_written=True, lambda_facility_MW=200000.0, existing_shed_MWh_B0=0.0,
             existing_shed_MWh_BL=0.0, reserve_min_slack_MW=0.0, balance_residual_max_abs_MW=0.0)
    assert A.acceptance(s, 200000.0)['checks']['lambda_below_artificial_upper'] is False             # artificial cap hit
    assert A.acceptance(dict(s, lambda_facility_MW=float('nan')), 200000.0)['PASS'] is False          # NaN
    assert A.acceptance(dict(s, lambda_facility_MW=10.0, balance_residual_max_abs_MW=0.5), 200000.0)['PASS'] is False


def test_lp_r_pass_writes_result_and_ledger(sandbox, monkeypatch):
    out, base = sandbox
    good_outputs(monkeypatch)
    A.lp('R', str(base), 1, solve_fn=lambda **k: ('ok', 'optimal'))
    r = json.loads((out / 'LP_R_H_RESOURCE_RESULT.json').read_text())
    assert r['acceptance']['PASS'] is True and all(r['acceptance']['checks'].values())
    lg = A.read_ledger()
    assert lg.state[0] == 'DONE' and lg['pass'][0] == 'True' and lg.status[0] == 'ok'


# ------------------------------------------------------------------------------------------------ FIX-02: A1 combination
def write_res(d, stage, lam, PASS=True):
    (d / f'{stage}_RESULT.json').write_text(json.dumps(dict(stage=stage, status='ok', termination='optimal', lambda_facility_MW=lam,
                                                            acceptance=dict(PASS=PASS, checks=dict(x=PASS)))))


def test_a1_pass_only_with_both_pass_and_order(tmp_path):
    write_res(tmp_path, 'LP_R_H_RESOURCE', 900.0); write_res(tmp_path, 'LP_N_H_NETWORK', 600.0)
    assert A.combine(tmp_path, 1e-3) == 'A1_PASS'
    write_res(tmp_path, 'LP_N_H_NETWORK', 950.0)
    assert A.combine(tmp_path, 1e-3) == 'A1_BLOCKED'                                                  # H_network > H_resource
    assert 'not in' in json.loads((tmp_path / 'A1_RESULT.json').read_text())['reasons'][0]
    write_res(tmp_path, 'LP_N_H_NETWORK', 600.0, PASS=False)
    assert A.combine(tmp_path, 1e-3) == 'A1_BLOCKED'                                                  # LP-N not PASS
    (tmp_path / 'LP_R_H_RESOURCE_RESULT.json').unlink()
    assert A.combine(tmp_path, 1e-3) == 'A1_BLOCKED'                                                  # missing result
    t = pd.read_csv(tmp_path / 'JOINT_HEADROOM_RESOURCE_NETWORK.csv')
    assert (t.A1_status == 'A1_BLOCKED').all() and 'NOT real ERCOT' in t.label[0]


def test_lp_n_blocked_exit_when_h_network_exceeds_h_resource(sandbox, monkeypatch):
    out, base = sandbox
    write_res(out, 'LP_R_H_RESOURCE', 400.0)
    good_outputs(monkeypatch, lam=500.0)
    with pytest.raises(SystemExit) as e:
        A.lp('N', str(base), 1, solve_fn=lambda **k: ('ok', 'optimal'))
    assert e.value.code == 4
    assert json.loads((out / 'A1_RESULT.json').read_text())['A1_status'] == 'A1_BLOCKED'
