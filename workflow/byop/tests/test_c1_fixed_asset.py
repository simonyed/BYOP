"""C1 fixed-asset diagnostics (prompt v1.4, stage B) - checks on the produced outputs and on the runner code; no solve here.
Run from pypsa-usa/workflow after the C1 runs and  python byop/run/c1_fixed_asset_diagnostics.py --collect :
    python -m pytest -q byop/tests/test_c1_fixed_asset.py"""
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

OUT = BP.C1_RESULTS
need = pytest.mark.skipif(not (OUT / 'C1_QA.json').exists(), reason='C1 not collected on this machine')
QA = lambda: json.loads((OUT / 'C1_QA.json').read_text())


def test_config_own_gate_and_formal_gates_untouched():
    c = yaml.safe_load((WF / 'config/config.byop_c1_fixed_asset_diag.yaml').read_text(encoding='utf-8'))['c1']
    assert c['authorization'] == 'AUTHORIZED_BY_RESEARCHER_PROMPT_V1_4' and c['max_diagnostic_solves'] == 6
    assert set(c['cases']) == {'C1_NETWORK_BASE', 'C1_NETWORK_CALIBRATED'} and c['windows']['max_net_load']['status'] == 'MISSING_INPUT'
    for p in (WF / 'config').glob('config.byop_ercot_mainline*.yaml'):
        t = yaml.safe_load(p.read_text(encoding='utf-8'))['mainline']
        assert t['run_authorization'] == 'NOT_APPROVED' and t['approved_git_sha'] is None, p.name
    src = (BY / 'run/c1_fixed_asset_diagnostics.py').read_text(encoding='utf-8')
    assert 'mainline_gate' not in src and 'run_authorization' not in src           # the formal gate is neither read nor changed


def test_runner_has_no_expansion_or_relaxation():
    tree = ast.parse((BY / 'run/c1_fixed_asset_diagnostics.py').read_text(encoding='utf-8'))
    s = ast.unparse(tree)
    assert "s_nom_extendable'] = True" not in s and "p_nom_extendable'] = True" not in s and 's_nom_max' not in s
    assert "endswith('-p_nom')" in s and "endswith('-s_nom')" in s                  # build variables asserted absent
    assert "build_year > 2025" in s and 'remove' in s


@need
def test_solves_within_budget_and_all_optimal():
    q = QA()
    assert q['diagnostic_solves'] <= q['solve_budget'] == 6
    assert q['all_optimal'] is True and q['no_build_variables'] is True
    log = pd.read_csv(OUT / 'C1_SOLVE_LOG.csv')
    ok = log[(log.counted_as == 'diagnostic') & (log.status == 'ok')]
    assert not ok.duplicated(['case', 'kind']).any()                                 # no silent re-run of a solved case


@need
def test_only_uplift_differs_and_loaded_once():
    q = QA()
    nd = q['network_difference']
    assert nd['lines_changed'] == 18 and abs(nd['uplift_MVA'] - 4993.9) < 0.1 and nd['equals_ledger'] is True
    assert all(nd['all_else_identical'].values()), nd['all_else_identical']
    assert q['ac_s0cal_links'] == 0
    man = pd.read_csv(OUT / 'C1_CASE_MANIFEST.csv')
    assert set(man.network) == {'results/BYOP/baseline_2025_tamu/baseline_2025_tamu_raw_uncalibrated.nc',
                                'results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc'}
    assert man.label.str.contains('NOT a historical replay').all()


@need
def test_power_balance_and_storage_reported():
    q = QA()
    assert q['balance_residual_max_abs_MW'] < 1.0                                    # barrier without crossover: small residual reported
    met = pd.read_csv(OUT / 'C1_METRICS.csv')
    for col in ('shed_MWh', 'shed_max_MW', 'storage_simultaneous_MWh', 'soc_total_first_MWh', 'soc_total_last_MWh', 'curtailment_wind_MWh'):
        assert col in met and met[col].notna().all()
    a = met[met.kind == 'ANNUAL_3H']
    assert len(a) == 2 and (a.weight_h == 3.0).all() and (a.snapshots == 2920).all()
    w = met[met.kind == 'PEAK_WINDOW_1H']
    assert len(w) == 2 and (w.weight_h == 1.0).all() and (w.evaluated_snapshots == 48).all()
    for f in ('C1_LINE_COMPARISON.csv', 'C1_GENERATION_BY_FUEL.csv', 'C1_BINDING_LINES.csv'):
        d = pd.read_csv(OUT / f)
        assert set(d.kind) == {'ANNUAL_3H', 'PEAK_WINDOW_1H'}, f                     # one label vocabulary, no empty joins


@need
def test_missing_inputs_declared_and_history_unchanged():
    q = QA()
    assert q['max_net_load_window'] == 'MISSING_INPUT'
    assert any('1 h wind / solar' in m for m in q['missing_inputs'])
    assert q['historical_or_future_inputs_changed_since_d2cf7d1c'] == []
    assert all(q['formal_gates_NOT_APPROVED'].values())
