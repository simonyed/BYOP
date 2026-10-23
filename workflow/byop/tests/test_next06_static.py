"""NEXT-06 W2 / W3 static tests (zero solver: injected solutions only)."""
from __future__ import annotations

import sys
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


def test_diag_config_is_locked_and_pins_its_run():
    import post_v16_a2_gate as A2G
    c = A2G.load(WF / 'config/config.byop_post_v16_n06_diag.yaml')
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_by'] is None and c['approved_git_sha'] is None
    assert A2G.budgets(c) == (1, 1) and c['optimizer_call_plan'] == {'S0': ['S0_COST']} and c['stages'] == ['S0']
    assert c['run_args'] == {'start': 2026, 'end': 2026, 'sample_weeks': 0, 'scenarios': ['S0']}
    assert c['out_dir'] != A2G.load()['out_dir'] and c['manifest'] != A2G.load()['manifest']    # never the consumed A2 ledger
    g = A2G.check('S0', None, cfg_path=WF / 'config/config.byop_post_v16_n06_diag.yaml')
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons']


def test_guard_refuses_run_args_drift(monkeypatch, capsys):
    import rearch_mech as R
    a = SimpleNamespace(a2_config=str(WF / 'config/config.byop_post_v16_n06_diag.yaml'), base=None, mainline=True,
                        config='config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml', out=str(WF / 'results/BYOP/next06_s0_diag_fullyear_2026'),
                        no_harm='on', attribution=False, relax=[], scenarios=['S0'], start=2026, end=2031, sample_weeks=26,
                        calibrate=False, erm_cal=None, s0_calibrate=False, s0_cal_file=None)
    with pytest.raises(SystemExit):
        R.post_v16_guard(a)
    out = capsys.readouterr().out
    assert '--end 2031 differs' in out and '--sample-weeks 26 differs' in out


def two_segment_network():
    pypsa = pytest.importorskip('pypsa')
    rows = [(2026, t) for start in ('2030-01-01', '2030-02-20') for t in pd.date_range(start, periods=4, freq='3h')]
    n = pypsa.Network(); n.set_snapshots(pd.MultiIndex.from_tuples(rows, names=['period', 'timestep'])); n.investment_periods = [2026]
    n.snapshot_weightings = n.snapshot_weightings * 0.0 + 3.0
    n.add('Bus', 'a'); n.add('Carrier', ['gas', 'battery'])
    n.add('Generator', 'g', bus='a', carrier='gas', p_nom=1000, marginal_cost=30, build_year=2025, lifetime=50)
    n.add('StorageUnit', 'bat', bus='a', carrier='battery', p_nom=100, max_hours=4, efficiency_store=1.0, efficiency_dispatch=1.0,
          cyclic_state_of_charge=True, cyclic_state_of_charge_per_period=True, build_year=2025, lifetime=30)
    n.add('Load', 'l', bus='a', p_set=500.0)
    return n


def test_persist_solution_and_soc_audit(tmp_path):
    import post_v16_mainline as PM
    n = two_segment_network()
    ps = np.array([100 / 3, 100 / 3, 100 / 3, 100 / 3, 0, 0, 0, 0.0]); pdp = np.array([0, 0, 0, 0, 100 / 3, 100 / 3, 100 / 3, 100 / 3])
    soc = np.cumsum(3 * (ps - pdp))                                 # 0 -> 400 in segment 1, back to 0 in segment 2 (a cross-gap transfer)
    n.storage_units_t.state_of_charge = pd.DataFrame({'bat': soc}, index=n.snapshots)
    n.storage_units_t.p_store = pd.DataFrame({'bat': ps}, index=n.snapshots)
    n.storage_units_t.p_dispatch = pd.DataFrame({'bat': pdp}, index=n.snapshots)
    n.storage_units['p_nom_opt'] = 100.0
    a = PM.soc_segment_postsolve_audit(n)
    assert len(a) == 2 and list(a.SOC_start_MWh.round(6)) == [0.0, 400.0] and list(a.SOC_end_MWh.round(6)) == [400.0, 0.0]
    assert list(a.SOC_end_minus_start_MWh.round(6)) == [400.0, -400.0]
    assert list(a['neutral_within_1e-3_MWh']) == [False, False] and list(a.end_ge_start) == [True, False]   # the audit exposes it
    rec = PM.persist_solution(n, tmp_path / 'solution' / 'S0')
    assert 'storage_soc.csv.gz' in rec and 'SOC_SEGMENT_POSTSOLVE_AUDIT.csv' in rec and len(rec['storage_soc.csv.gz']) == 64
