"""NEXT-07 W1 static tests for the reserve-RHS probe (zero solver: models are built, solutions injected)."""
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
sys.path.insert(0, str(WF / 'byop/tests'))
PROBE = WF / 'config/config.byop_post_v16_n07_reserve_probe.yaml'
N06 = WF / 'config/config.byop_post_v16_n06_diag.yaml'
A3 = WF / 'config/config.byop_post_v16_a3.yaml'


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def tampered(tmp_path, src=PROBE, name=None, **change):
    raw = yaml.safe_load(src.read_text(encoding='utf-8'))
    for k, v in change.items():
        if v is None:
            raw['post_v16'].pop(k, None)
        else:
            raw['post_v16'][k] = v
    p = tmp_path / (name or src.name)
    p.write_text(yaml.safe_dump(raw), encoding='utf-8')
    return p


def test_probe_config_is_locked_and_pinned():
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    c = A2G.load(PROBE)
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_by'] is None and c['approved_git_sha'] is None
    assert A2G.budgets(c) == (1, 1) and c['optimizer_call_plan'] == {'S0': ['S0_COST']} and c['stages'] == ['S0'] and c['max_retries'] == 0
    assert c['run_args'] == {'start': 2026, 'end': 2031, 'sample_weeks': 26, 'scenarios': ['S0']}
    assert c['diagnostic'] == {'kind': 'S0_RESERVE_REQ_RHS_ONLY', 'reserve_requirement_MW': 0.0}
    others = [A2G.load(), A2G.load(N06)]
    assert all(c['out_dir'] != o['out_dir'] and c['manifest'] != o['manifest'] for o in others)    # never a consumed / other ledger
    assert PM.diagnostic_reserve_rhs(c, PROBE) == 0.0
    g = A2G.check('S0', None, cfg_path=PROBE)
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons'] and not [r for r in g['reasons'] if 'diagnostic' in r]


def test_formal_configs_never_carry_the_probe():
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    assert PM.diagnostic_reserve_rhs(A2G.load(), A2G.CFG) is None
    assert PM.diagnostic_reserve_rhs(A2G.load(N06), N06) is None
    assert 'diagnostic' not in yaml.safe_load(A3.read_text(encoding='utf-8'))['post_v16']
    assert PM.POST_V16['reserve_MW'] == 3000.0


@pytest.mark.parametrize('change, msg', [
    (dict(diagnostic={'kind': 'S0_RESERVE_REQ_RHS_ONLY', 'reserve_requirement_MW': 500.0}), 'reserve_requirement_MW 500'),
    (dict(diagnostic={'kind': 'DROP_ONLINE_MIN', 'reserve_requirement_MW': 0.0}), 'exactly kind'),
    (dict(diagnostic={'kind': 'S0_RESERVE_REQ_RHS_ONLY', 'reserve_requirement_MW': 0.0, 'online_min': False}), 'exactly kind'),
    (dict(stages=['S0', 'S1_EARLIEST']), 'stages [S0]'),
    (dict(run_args={'start': 2026, 'end': 2026, 'sample_weeks': 0, 'scenarios': ['S0']}), 'run_args'),
    (dict(out_dir='results/BYOP/post_v16_a2/POST_V16_A2_S0S1'), 'own out_dir'),
    (dict(max_top_level_optimizer_calls=2), 'budget'),
])
def test_tampered_probe_is_refused(tmp_path, change, msg):
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    p = tampered(tmp_path, **change)
    with pytest.raises(ValueError, match=msg.replace('[', r'\[').replace(']', r'\]')):
        PM.diagnostic_reserve_rhs(A2G.load(p), p)
    g = A2G.check('S0', None, cfg_path=p)
    assert not g['approved'] and any(r.startswith('diagnostic config refused') for r in g['reasons'])


def test_diagnostic_block_only_in_the_probe_file(tmp_path):
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    p = tampered(tmp_path, src=N06, diagnostic={'kind': 'S0_RESERVE_REQ_RHS_ONLY', 'reserve_requirement_MW': 0.0})
    with pytest.raises(ValueError, match='only allowed in'):
        PM.diagnostic_reserve_rhs(A2G.load(p), p)
    assert any(r.startswith('diagnostic config refused') for r in A2G.check('S0', None, cfg_path=p)['reasons'])


def test_a3_gate_refuses_a_diagnostic_block(tmp_path):
    import post_v16_a3_gate as A3G
    p = tampered(tmp_path, src=A3, diagnostic={'kind': 'S0_RESERVE_REQ_RHS_ONLY', 'reserve_requirement_MW': 0.0})
    g = A3G.check('S0', None, cfg_path=p)
    assert not g['approved'] and any('diagnostic block' in r for r in g['reasons'])


def guard_args(**kw):
    a = dict(a2_config=str(PROBE), base=None, mainline=True, config='config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml',
             out=str(WF / 'results/BYOP/next07_s0_reserve_probe'), no_harm='on', attribution=False, relax=[], scenarios=['S0'],
             start=2026, end=2031, sample_weeks=26, calibrate=False, erm_cal=None, s0_calibrate=False, s0_cal_file=None)
    a.update(kw)
    return SimpleNamespace(**a)


def test_guard_pins_probe_run_args(capsys):
    import rearch_mech as R
    with pytest.raises(SystemExit):
        R.post_v16_guard(guard_args(end=2026, sample_weeks=0, scenarios=['S0', 'S1_EARLIEST']))
    out = capsys.readouterr().out
    assert '--end 2026 differs' in out and '--sample-weeks 0 differs' in out and 'differs from the config run_args' in out


def test_guard_refuses_unapproved_probe_without_building(capsys, monkeypatch):
    import rearch_mech as R
    import post_v16_a2_gate as A2G
    calls = []
    monkeypatch.setattr(A2G, 'check', lambda *a, **k: calls.append(1) or dict(approved=False, reasons=['run_authorization=NOT_APPROVED']))
    with pytest.raises(SystemExit) as e:
        R.post_v16_guard(guard_args(base=str(R.BP.BASE_TAMU_V16)))
    assert e.value.code == 3


def small():
    import test_a2_a3_static as T
    return T.small_multiperiod()


def fingerprint(m):
    rows = {}
    for k in m.constraints:
        c = m.constraints[k]
        rows[k] = (np.asarray(c.vars.values).copy(), np.asarray(c.coeffs.values).copy(), np.asarray(c.sign.values).astype(str), np.asarray(c.rhs.values, dtype=float).copy())
    return rows


def test_probe_changes_only_the_reserve_rhs_and_leaves_no_state():
    import post_v16_mainline as PM
    before = dict(PM.POST_V16)
    builds = []
    for rhs in (None, 0.0, None):                       # formal -> probe -> formal, in one process
        n = small()
        info = PM.add_operating_reserve(n, n.snapshots, reserve_MW=rhs)
        builds.append((fingerprint(n.model), info))
    (ref, i0), (probe, i1), (ref2, i2) = builds
    assert PM.POST_V16 == before and i0['reserve_req_rhs_MW'] == 3000.0 and i1['reserve_req_rhs_MW'] == 0.0 and i2['reserve_req_rhs_MW'] == 3000.0
    assert set(ref) == set(probe) == set(ref2)
    for k in ('PV16M-online_min', 'PV16M-res_thermal_head', 'PV16M-res_ramp', 'PV16M-res_su_energy', 'PV16M-res_su_energy_start', 'PV16M-online_cap_ext'):
        assert k in probe
    changed = []
    for k in ref:
        for j, f in enumerate(('vars', 'coeffs', 'sign', 'rhs')):
            same = np.array_equal(ref[k][j], probe[k][j]) if j != 1 and j != 3 else np.allclose(ref[k][j], probe[k][j], atol=1e-10, equal_nan=True)
            if not same:
                changed.append((k, f))
            assert np.array_equal(ref[k][j], ref2[k][j]) if j in (0, 2) else np.allclose(ref[k][j], ref2[k][j], atol=1e-10, equal_nan=True)
    assert changed == [('PV16M-reserve_req', 'rhs')]
    assert np.allclose(ref['PV16M-reserve_req'][3], 3000.0) and np.allclose(probe['PV16M-reserve_req'][3], 0.0)


def test_extra_rearch_reads_the_probe_rhs_per_build_only(monkeypatch):
    """the build entry passes STATE['pv16_reserve_rhs_MW'] explicitly; without it the formal 3,000 MW applies"""
    import rearch_mech as R
    import post_v16_mainline as PM
    seen = []
    monkeypatch.setattr(PM, 'add_operating_reserve', lambda n, s, reserve_MW=None: seen.append(reserve_MW) or {})
    src = Path(R.__file__).read_text(encoding='utf-8')
    assert "PM.add_operating_reserve(n, snapshots, reserve_MW=STATE.get('pv16_reserve_rhs_MW'))" in src
    assert "POST_V16['reserve_MW'] =" not in src and "POST_V16['reserve_MW']=" not in src           # never mutated globally
    assert "STATE['pv16_reserve_rhs_MW'] = (pv16_gate or {}).get('diagnostic_reserve_MW')" in src


def test_reserve_solution_frames_from_injected_solution():
    import post_v16_mainline as PM
    n = small()
    PM.add_operating_reserve(n, n.snapshots, reserve_MW=0.0)
    m = n.model
    m.status, m.termination_condition = 'ok', 'optimal'
    for k in m.variables:
        v = m.variables[k]
        v.solution = v.labels * 0.0 + (100.0 if k in ('PV16M-res_thermal', 'PV16M-online_cap') else 0.0)
    n.generators['p_nom_opt'] = n.generators.p_nom
    n.generators_t.p = pd.DataFrame(0.0, index=n.snapshots, columns=n.generators.index)
    f = PM.reserve_solution_frames(n)
    r = f['reserve_by_snapshot']
    assert not isinstance(r, str), r
    assert np.allclose(r.reserve_total_MW, 200.0) and np.allclose(r.reserve_req_rhs_MW, 0.0)          # 2 thermal units x 100
    assert np.allclose(r.shortfall_vs_formal_MW, 2800.0) and (r.formal_requirement_MW == 3000.0).all()
    assert set(f) >= {'thermal_online_cap', 'thermal_reserve', 'thermal_available_cap', 'bess_reserve'}


# ------------------------------------------------------------------------------------------------ NEXT-07 W5: lossless probe
LOSSLESS = WF / 'config/config.byop_post_v16_n07_lossless_probe.yaml'


def test_lossless_config_is_locked_and_pinned():
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    c = A2G.load(LOSSLESS)
    assert c['run_authorization'] == 'NOT_APPROVED' and c['approved_by'] is None and c['approved_git_sha'] is None
    assert A2G.budgets(c) == (1, 1) and c['optimizer_call_plan'] == {'S0': ['S0_COST']} and c['stages'] == ['S0'] and c['max_retries'] == 0
    assert c['run_args'] == {'start': 2026, 'end': 2031, 'sample_weeks': 26, 'scenarios': ['S0']}
    assert PM.diagnostic_spec(c, LOSSLESS)['kind'] == 'S0_TRANSMISSION_LOSSLESS'
    assert PM.diagnostic_transmission_losses(c, LOSSLESS) == 0 and PM.diagnostic_reserve_rhs(c, LOSSLESS) is None   # reserve stays 3 GW
    assert PM.diagnostic_transmission_losses(A2G.load(PROBE), PROBE) is None
    others = [A2G.load(), A2G.load(N06), A2G.load(PROBE)]
    assert all(c['out_dir'] != o['out_dir'] and c['manifest'] != o['manifest'] for o in others)
    g = A2G.check('S0', None, cfg_path=LOSSLESS)
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons'] and not [r for r in g['reasons'] if 'diagnostic' in r]


@pytest.mark.parametrize('change, msg', [
    (dict(diagnostic={'kind': 'S0_TRANSMISSION_LOSSLESS', 'transmission_losses': 1}), 'transmission_losses 1'),
    (dict(diagnostic={'kind': 'S0_TRANSMISSION_LOSSLESS', 'transmission_losses': 0, 'reserve_requirement_MW': 0.0}), 'exactly kind'),
    (dict(out_dir='results/BYOP/next07_s0_reserve_probe'), 'own out_dir'),
    (dict(run_args={'start': 2026, 'end': 2026, 'sample_weeks': 0, 'scenarios': ['S0']}), 'run_args'),
])
def test_tampered_lossless_is_refused(tmp_path, change, msg):
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    p = tampered(tmp_path, src=LOSSLESS, **change)
    with pytest.raises(ValueError, match=msg):
        PM.diagnostic_spec(A2G.load(p), p)
    assert any(r.startswith('diagnostic config refused') for r in A2G.check('S0', None, cfg_path=p)['reasons'])


def test_lossless_kind_only_in_its_own_file(tmp_path):
    import post_v16_a2_gate as A2G
    import post_v16_mainline as PM
    for src in (PROBE, N06):
        p = tampered(tmp_path, src=src, diagnostic={'kind': 'S0_TRANSMISSION_LOSSLESS', 'transmission_losses': 0})
        with pytest.raises(ValueError, match='only allowed in'):
            PM.diagnostic_spec(A2G.load(p), p)


def test_solve_config_override_is_per_solve_copy():
    import rearch_mech as R
    cfg = {'solving': {'options': {'transmission_losses': 2, 'linearized_unit_commitment': True}}}
    assert R.pv16_solve_config(cfg, {}) is cfg                                       # formal: untouched, same object
    c0 = R.pv16_solve_config(cfg, {'pv16_transmission_losses': 0})
    assert c0 is not cfg and c0['solving']['options']['transmission_losses'] == 0
    assert c0['solving']['options']['linearized_unit_commitment'] is True            # everything else formal
    assert cfg['solving']['options']['transmission_losses'] == 2                      # the baseline meta copy is never modified
    src = Path(R.__file__).read_text(encoding='utf-8')
    assert 'res = solve0(pv16_solve_config(config, state), tag, out_, n, *args_, **kw_)' in src
    assert "STATE['pv16_transmission_losses'] = int(spec_['value']) if spec_ and spec_['key'] == 'transmission_losses' else None" in src
