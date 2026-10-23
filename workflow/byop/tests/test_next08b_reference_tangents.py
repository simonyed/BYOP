"""NEXT-08b static tests: lossy LP1 v2 with reference-capacity loss tangents (zero solver)."""
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
CFG2 = WF / 'config/config.byop_lossy_lp1_v2.yaml'
from test_next08_lossy_lp1 import tiny_raw  # noqa: E402


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def test_v2_config_differs_from_v1_only_in_tangent_reference_and_bookkeeping():
    import loss_basis_lp1 as L
    import post_v16_a2_gate as A2G
    c1, c2 = L.load(CFG), L.load(CFG2)
    diff = {k for k in set(c1) | set(c2) if c1.get(k) != c2.get(k)}
    assert diff <= {'authorization_source', 'authorization_source_sha256', 'manifest', 'out_dir', 'loss_tangent_reference', 'run_authorization'}
    assert {'loss_tangent_reference', 'out_dir', 'manifest'} <= diff
    assert c2['loss_tangent_reference'] == 's_ref' and c2['run_authorization'] == 'NOT_APPROVED' and c2['approved_by'] is None and c2['approved_git_sha'] is None
    assert c2['guards'] == c1['guards'] and c2['cap_factor'] == c1['cap_factor'] and c2['acceptance'] == c1['acceptance'] and int(c2['max_lp_calls']) == 3
    assert A2G.file_shas(WF.parent / c2['authorization_source'])['lf'] == c2['authorization_source_sha256']
    assert not L.check('LP1_LOSSY_IT1', CFG2)['approved']


def fixed_reference_model(raw, s_ref):
    """the fixed-capacity model of capacity s_ref as LP2 / S0-S3 build it: non-extendable lines, s_nom = s_ref, same r"""
    pypsa = pytest.importorskip('pypsa')
    import loss_basis_lp1 as L
    n = pypsa.Network(str(raw))
    s_raw, r_raw = n.lines.s_nom.copy(), n.lines.r.copy()
    n.lines['s_nom'] = s_ref.reindex(n.lines.index)
    n.lines['r'] = L.r_proxy(r_raw, s_raw, s_ref.reindex(n.lines.index))
    n.optimize.create_model(transmission_losses=2)
    return n


def tangent_offsets(m):
    return {(k, sg): np.asarray(m.constraints[f'Line-loss_tangents-{k}-{sg}'].rhs.transpose(..., 'name').values, dtype=float)
            for k in (1, 2) for sg in (-1, 1)}


def test_v2_tangent_rows_equal_the_fixed_capacity_rows(tmp_path):
    import loss_basis_lp1 as L
    raw = tiny_raw(tmp_path / 'raw.nc')
    s_prep = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
    s_ref = pd.Series([450.0, 120.0, 80.0], ['TL35', 'TL43', 'TL44'])
    n2, i2 = L.build_lp1_from(raw, s_prep, s_ref, L.load(CFG2))
    n1, _ = L.build_lp1_from(raw, s_prep, s_ref, L.load(CFG))
    fx = fixed_reference_model(raw, s_ref)
    assert i2['tangent_reference'] == 's_ref'
    a2, af = tangent_offsets(n2.model), tangent_offsets(fx.model)
    assert all(np.allclose(a2[k], af[k], rtol=0, atol=1e-12) for k in a2)                       # identical offsets as the fixed model
    dev = L.tangent_rows_vs_reference(n2, s_ref.reindex(n2.lines.index))
    assert all(d['offset_max_abs_dev'] < 1e-12 and d['slope_max_abs_dev'] < 1e-12 for d in dev.values())   # and slopes
    dev1 = L.tangent_rows_vs_reference(n1, n1.lines.s_nom_max)
    assert all(d['offset_max_abs_dev'] < 1e-12 and d['slope_max_abs_dev'] < 1e-12 for d in dev1.values())  # v1 unchanged: at the cap
    cap = 2.0 * s_prep
    assert np.allclose(n2.model.constraints['Line-ext-s_nom-upper'].rhs.values, cap.reindex(n2.lines.index).values)
    assert n2.lines.s_nom_max.tolist() == cap.tolist()
    r_pu = n2.lines.r / 230.0 ** 2
    lu = n2.model.constraints['Line-loss_upper'].rhs.transpose(..., 'name').values
    assert np.allclose(lu, np.broadcast_to((r_pu * (0.7 * cap) ** 2).values, lu.shape))
    assert (int(n2.model.nvars), int(n2.model.ncons)) == (int(n1.model.nvars), int(n1.model.ncons)) and len(n2.model.integers) == 0


def test_tangent_reference_mode_validated(tmp_path):
    import loss_basis_lp1 as L
    raw = tiny_raw(tmp_path / 'raw.nc')
    s = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
    with pytest.raises(ValueError, match='loss_tangent_reference'):
        L.build_lp1_from(raw, s, s, dict(L.load(CFG2), loss_tangent_reference='four'))


def test_v2_full_chain_zero_solver(tmp_path, monkeypatch):
    """the whole v2 chain on the small network through the real build code (build_lp1_from) and the real stage rules"""
    import linopy
    import fake_solve as F
    import loss_basis_lp1 as L
    import baseline_v16_calibration as V16
    monkeypatch.setattr(linopy.Model, 'solve', F.fake_solve)
    raw = tiny_raw(tmp_path / 'raw.nc')
    s_prep = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
    raw_cfg = yaml.safe_load(CFG2.read_text(encoding='utf-8')); raw_cfg['post_v16']['out_dir'] = str(tmp_path / 'v2')
    p = tmp_path / 'config.byop_lossy_lp1_v2.yaml'; p.write_text(yaml.safe_dump(raw_cfg), encoding='utf-8')
    c = L.load(p); v, _ = V16.load_cfg()

    def lp1_build(stage, c_):
        s_ref = s_prep if stage == 'LP1_LOSSY_IT1' else pd.read_csv(L.out_dir(c_) / 'LP1_LOSSY_IT1' / 'LP1_LINE_SOLUTION.csv', index_col=0).s_nom_opt
        n, info = L.build_lp1_from(raw, s_prep, s_ref, c_)
        return n, dict(info, raw_nc=raw), v

    def gate(stage):
        g = L.check(stage, cfg_path=p)
        keep = [x for x in g['reasons'] if x.startswith((stage, 'LP2_LOSSY_CANDIDATE only', 'LP1_LOSSY_IT2 only', 'candidate', 'LP budget')) or 'already has' in x]
        return dict(g, approved=not keep, reasons=keep)
    q1 = L.run('LP1_LOSSY_IT1', 1, cfg_path=p, gate_fn=gate, lp1_build=lp1_build)
    q2 = L.run('LP1_LOSSY_IT2', 1, cfg_path=p, gate_fn=gate, lp1_build=lp1_build)
    q3 = L.run('LP2_LOSSY_CANDIDATE', 1, cfg_path=p, gate_fn=gate)
    assert q1['r_converged'] is False and q2['r_converged'] is True and q2['candidate_written'] is True and q3['transmission_losses'] == 2
    lg = pd.read_csv(L.ledger(c)[0], dtype=str, keep_default_na=False)
    assert list(lg.stage) == L.STAGES and set(lg.state) == {'DONE'}
