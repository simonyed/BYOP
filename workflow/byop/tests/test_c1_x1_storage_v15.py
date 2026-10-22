"""WP v1.5 (C1-X1 + storage two-stage) checks - no solve here. Run from pypsa-usa/workflow after the run and
    python byop/post/c1_x1_collect.py ;  python -m pytest -q byop/tests/test_c1_x1_storage_v15.py"""
from __future__ import annotations

import ast, json, sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
BY = WF / 'byop'
sys.path.insert(0, str(BY / 'model'))
import byop_paths as BP  # noqa: E402

OUT = BP.RESULTS / 'C1_X1_STORAGE_V15'
need = pytest.mark.skipif(not (OUT / 'C1_X1_QA.json').exists(), reason='v1.5 not collected on this machine')
QA = lambda: json.loads((OUT / 'C1_X1_QA.json').read_text())


def test_config_and_formal_gates():
    c = yaml.safe_load((WF / 'config/config.byop_c1_x1_storage_v15.yaml').read_text())['c1x1']
    assert c['authorization'] == 'AUTHORIZED_BY_RESEARCHER_WP_V1_5'
    assert c['effective_stages'] == ['C1_X1_RAW_IMPEDANCE', 'C1_X1_MIN_STORAGE_THROUGHPUT']
    assert c['epsilon_F'] == {'abs_USD': 1.0, 'rel': 1.0e-8} and c['epsilon_E'] == {'abs_MWh': 0.001, 'rel': 1.0e-8}
    for p in (WF / 'config').glob('config.byop_ercot_mainline*.yaml'):
        assert yaml.safe_load(p.read_text())['mainline']['run_authorization'] == 'NOT_APPROVED'


def test_runner_structure():
    s = ast.unparse(ast.parse((BY / 'run/c1_x1_storage_v15.py').read_text(encoding='utf-8')))
    assert 'reindex(led.index)' in s                                           # impedance restored by line ID
    assert "assert (a.s_nom_X1 == a.s_nom_calibrated).all()" in s
    assert 'add_objective(T, overwrite=True)' in s and "name='X1S2-economic_cost_bound'" in s
    assert "name='X1S2-shed_upper'" in s and "name='X1S2-shed_lower'" in s
    assert 'binary' not in s.lower() and 'integer' not in s.lower()             # no MILP
    assert 'stage2_nodal_balance_duals_NOT_economic_prices' in s                 # stage-2 duals never labelled as prices


def test_line_audit_exact():
    a = pd.read_csv(OUT / 'C1_X1_LINE_INPUT_AUDIT.csv', index_col=0)
    assert (a.s_nom_X1 == a.s_nom_calibrated).all()
    assert a.uplift_line.sum() == 18 and set(a.index[a.impedance_restored]) == set(a.index[a.uplift_line])
    up = a[a.uplift_line]
    assert (up.x_X1 == up.x_raw).all() and (up.r_X1 == up.r_raw).all()
    assert (a[~a.uplift_line].x_X1 == a[~a.uplift_line].x_calibrated).all()


@need
def test_stages_optimal_and_bounds():
    q = QA()
    assert q['solver_termination']['stage1'] is True and q['solver_termination']['stage2'] is True
    assert q['effective_stages'] == 2
    b = q['stage2_bounds']
    assert b['F_bound_ok'] is True and b['E_bound_ok'] is True
    assert abs(b['F_recomputed_stage1'] - b['F_star']) <= max(1.0, 1e-7 * abs(b['F_star']))      # F(x) recomputation = solver objective
    assert q['x1_input_identity'] is True and q['balance_residual_max_abs_MW'] < 1e-3
    assert q['storage_state_equation_max_abs_residual_MWh'] < 1e-3


@need
def test_outputs_complete_and_prices_separated():
    q = QA()
    assert q['output_complete'] is True, q['output_completeness']
    assert q['prices']['stage1_economic'] is True and q['prices']['stage2_duals_separate'] is True
    assert q['inputs_or_old_results_changed_since_cf5df4f0'] == []
    assert all(v == 'NOT_APPROVED' for v in q['formal_gates'].values())
    cmp_ = pd.read_csv(OUT / 'C1_X1_STAGE_COMPARISON.csv').set_index('metric')
    for k in ('shed_MWh', 'storage_simultaneous_MWh', 'storage_throughput_MWh', 'economic_cost_USD'):
        assert cmp_.loc[k, ['v14_CALIBRATED', 'X1_stage1', 'X1_stage2']].notna().all(), k
