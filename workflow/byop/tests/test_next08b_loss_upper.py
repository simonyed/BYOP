"""NEXT-08b loss-upper fix (LP1 v3) static tests: affine capacity-dependent loss bound + trust floor (zero solver)."""
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
CFG2 = WF / 'config/config.byop_lossy_lp1_v2.yaml'
CFG3 = WF / 'config/config.byop_lossy_lp1_v3.yaml'
from test_next08_lossy_lp1 import tiny_raw  # noqa: E402

S_PREP = pd.Series([400.0, 150.0, 80.0], ['TL35', 'TL43', 'TL44'])
S_REF = pd.Series([450.0, 120.0, 80.0], ['TL35', 'TL43', 'TL44'])     # above, below and equal to s_prep; TL35 floor 337.5 > raw 100


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def env(a, r, Rr, K=2):
    return np.maximum.reduce([np.zeros_like(a)] + [2 * r * (k / K * Rr) * a - r * (k / K * Rr) ** 2 for k in range(1, K + 1)])


def test_v3_config_differs_from_v2_only_in_loss_upper_and_bookkeeping():
    import loss_basis_lp1 as L
    import post_v16_a2_gate as A2G
    c2, c3 = L.load(CFG2), L.load(CFG3)
    diff = {k for k in set(c2) | set(c3) if c2.get(k) != c3.get(k)}
    assert diff <= {'authorization_source', 'authorization_source_sha256', 'manifest', 'out_dir', 'loss_upper', 'static_reference',
                    'run_authorization', 'approved_git_sha', 'approved_by'}
    assert {'loss_upper', 'out_dir', 'manifest', 'authorization_source'} <= diff
    assert c3['loss_upper'] == 'affine_s_ref' and c3['loss_tangent_reference'] == 's_ref'
    assert c3['run_authorization'] == 'NOT_APPROVED' and c3['approved_by'] is None and c3['approved_git_sha'] is None
    for k in ('guards', 'cap_factor', 'acceptance', 'r_tol', 's_tol_MVA', 'transmission_losses', 'max_lp_calls', 'max_retries', 'stages', 'baseline', 'raw_baseline'):
        assert c3[k] == c2[k], k                                       # G1-G3, r rule, LP2 acceptance, budget unchanged
    assert c3['out_dir'] not in (c2['out_dir'], L.load(L.CFG)['out_dir'])
    assert A2G.file_shas(WF.parent / c3['authorization_source'])['lf'] == c3['authorization_source_sha256']
    assert not L.check('LP1_LOSSY_IT1', CFG3)['approved']


def test_affine_bound_analytics():
    """the design proof, numerically: U(R) = r (2 R_ref R - R_ref^2) is exact at R_ref, never above r R^2, dominates the tangent
    envelope at |s| = R for every R >= 0.75 R_ref (no hidden flow cap) and fails below; the naive constant bound r R_ref^2 caps
    |s| at R_ref whatever the capacity"""
    import loss_basis_lp1 as L
    rng = np.random.default_rng(7)
    assert L.trust_floor_factor(2) == 0.75 and L.trust_floor_factor(3) == pytest.approx(5 / 6)
    for _ in range(200):
        r, Rr = rng.uniform(1e-6, 1e-3), rng.uniform(20, 2000)
        R = np.linspace(0.75 * Rr, 3 * Rr, 500)
        U = r * (2 * Rr * R - Rr ** 2)
        assert np.all(U - env(R, r, Rr) >= -1e-12 * r * Rr ** 2)          # no hidden cap on [0.75, 3] x R_ref
        assert np.all(U <= r * R ** 2 + 1e-12 * r * Rr ** 2)                # never more room than LP2 at that capacity
        assert r * (2 * Rr * Rr - Rr ** 2) == pytest.approx(r * Rr ** 2)    # fixed point
        Rlo = np.linspace(0.3 * Rr, 0.74 * Rr, 50)
        assert np.all(r * (2 * Rr * Rlo - Rr ** 2) < env(Rlo, r, Rr))      # below the floor the affine bound WOULD cap flows
        assert r * (2 * Rr * 0.5 * Rr - Rr ** 2) == pytest.approx(0.0, abs=1e-12)   # and force R >= R_ref / 2 through loss >= 0
        # naive fix (the researcher's caution): constant r R_ref^2 with the top tangent -> |s| <= R_ref for any capacity
        smax_naive = (r * Rr ** 2 + r * Rr ** 2) / (2 * r * Rr)
        assert smax_naive == pytest.approx(Rr)


def build(tmp_path, cfg, s_ref=S_REF):
    import loss_basis_lp1 as L
    raw = tiny_raw(tmp_path / 'raw.nc')
    n, info = L.build_lp1_from(raw, S_PREP, s_ref, L.load(cfg))
    return raw, n, info


def test_v3_rows_on_small_network(tmp_path):
    import loss_basis_lp1 as L
    raw, n3, i3 = build(tmp_path, CFG3)
    (tmp_path / 'v2').mkdir()
    _, n2, _ = build(tmp_path / 'v2', CFG2)
    assert (int(n3.model.nvars), int(n3.model.ncons)) == (int(n2.model.nvars), int(n2.model.ncons)) and len(n3.model.integers) == 0
    floor = np.maximum(i3['s_raw'], 0.75 * S_REF.reindex(i3['s_raw'].index))
    assert np.allclose(i3['s_floor'], floor) and np.allclose(n3.lines.s_nom_min, floor) and i3['s_floor']['TL35'] == 337.5
    rows, D = L.loss_rows_report(n3, S_REF, n3.lines.s_nom_max, i3['s_floor'])
    lu = rows['loss_upper']
    assert lu['slope_max_abs_dev'] < 1e-15 and lu['offset_max_abs_dev'] < 1e-12 and lu['sign'] == ['<='] and lu['other_terms'] == 0
    assert all(d['offset_max_abs_dev'] < 1e-12 and d['slope_max_abs_dev'] < 1e-12 for d in rows['loss_tangents'].values())
    assert rows['s_nom_upper']['rhs_max_abs_dev'] < 1e-12 and rows['s_nom_lower']['rhs_max_abs_dev'] < 1e-12
    assert rows['rating_rows']['upper']['loss_coef'] == [1.0] and rows['rating_rows']['lower']['loss_coef'] == [-1.0]
    d = rows['domain']
    assert d['min_margin_rel'] >= -1e-12 and d['max_U_minus_rR2_rel'] <= 1e-12 and d['min_U_rel'] >= 0.5 - 1e-12 and d['fixed_point_max_dev_rel'] < 1e-12
    # tangents of v3 = tangents of v2 (unchanged NEXT-08b fix)
    for k in (1, 2):
        for sg in (-1, 1):
            cn = f'Line-loss_tangents-{k}-{sg}'
            assert np.allclose(n3.model.constraints[cn].rhs.values, n2.model.constraints[cn].rhs.values, rtol=0, atol=1e-14)


def test_v3_fixed_point_equals_lp2_rows(tmp_path):
    import loss_basis_lp1 as L
    import baseline_v16_calibration as V16
    raw, n3, i3 = build(tmp_path, CFG3)
    v, _ = V16.load_cfg()
    fx = tmp_path / 'fixed.nc'
    L.candidate_network(raw, S_REF).export_to_netcdf(str(fx))
    fp = L.fixed_point_vs_lp2(n3, S_REF, fx, v)
    assert fp['s_nom_dev'] < 1e-12 and fp['r_dev'] < 1e-12 and fp['loss_upper_rel_dev'] < 1e-12
    assert all(fp[k] < 1e-12 for k in fp if k.startswith(('tangent_', 'rating_')))


def test_representative_points_pass_v3_and_detect_naive_fix_and_missing_floor(tmp_path):
    import loss_basis_lp1 as L
    import xarray as xr
    raw, n3, i3 = build(tmp_path, CFG3)
    pc, bad = L.representative_point_checks(n3, S_REF, n3.lines.s_nom_max, i3['s_floor'])
    assert pc['failures'] == dict(A=0, B=0, C=0, D=0)
    # negative control 1: the naive fix (constant loss_upper r (0.7 S_ref)^2) makes the loss bound the flow limit above S_ref
    (tmp_path / 'v2').mkdir()
    _, n2, i2 = build(tmp_path / 'v2', CFG2)
    lu = n2.model.constraints['Line-loss_upper']
    names = list(lu.rhs.coords['name'].values)
    scale = ((S_REF.reindex(names) / n2.lines.s_nom_max.reindex(names)) ** 2).values
    lu.update(rhs=lu.rhs * xr.DataArray(scale, coords={'name': names}, dims='name'))
    pcn, badn = L.representative_point_checks(n2, S_REF, n2.lines.s_nom_max, i2['s_raw'])
    assert pcn['failures']['A'] > 0 and any(b[0] in ('mid', 'cap') and 'Line-loss_upper' in str(b) for b in badn['A'])
    # negative control 2: the affine bound WITHOUT the floor (capacity allowed down to raw) caps flows / forces a hidden floor
    lo = n3.model.constraints['Line-ext-s_nom-lower']
    lo.update(rhs=lo.rhs.copy(data=np.asarray(i3['s_raw'].reindex(list(lo.rhs.coords['name'].values)).values, dtype=float)))
    pcf, badf = L.representative_point_checks(n3, S_REF, n3.lines.s_nom_max, i3['s_raw'])
    assert pcf['failures']['A'] + pcf['failures']['D'] > 0 and 'TL35' in str(badf['A'] + badf['D'])


def test_dissipation_room_v3_vs_v2(tmp_path):
    import loss_basis_lp1 as L
    _, n3, i3 = build(tmp_path, CFG3)
    dr = L.dissipation_room(n3, S_REF, n3.lines.s_nom_max, i3['s_floor'])
    r_pu = n3.lines.r / 230.0 ** 2
    rate = 2 * r_pu * 0.7 * S_REF.reindex(n3.lines.index) * 0.7
    assert dr['rate_MW_per_MVA_max'] == pytest.approx(float(rate.max())) and dr['v3_room_at_s_ref_total_MW'] == 0.0
    old = (r_pu * ((0.7 * n3.lines.s_nom_max) ** 2 - (0.7 * S_REF.reindex(n3.lines.index)) ** 2)).sum()
    assert dr['v2_room_at_s_ref_total_MW'] == pytest.approx(float(old)) and old > 0


def test_convergence_trust_floor_rule():
    import loss_basis_lp1 as L
    raw = pd.Series([100.0, 100.0], ['a', 'b']); ref = pd.Series([400.0, 100.0], ['a', 'b']); floor = pd.Series([300.0, 100.0], ['a', 'b'])
    ok, info = L.convergence(pd.Series([400.0, 100.0], ['a', 'b']), ref, raw, 0.05, 10.0, s_floor=floor)
    assert ok and info['lines_at_trust_floor'] == [] and info['trust_floor_lines'] == 1
    ok, info = L.convergence(pd.Series([300.0, 100.0], ['a', 'b']), pd.Series([300.0, 100.0], ['a', 'b']), raw, 0.05, 10.0, s_floor=floor)
    assert not ok and info['lines_at_trust_floor'] == ['a']                 # r-converged but on a floor above raw -> not converged
    ok0, info0 = L.convergence(pd.Series([300.0, 100.0], ['a', 'b']), pd.Series([300.0, 100.0], ['a', 'b']), raw, 0.05, 10.0)
    assert ok0 and 'lines_at_trust_floor' not in info0                      # v1 / v2 rule unchanged


def fake_at(values):
    """fake solve that puts every line capacity at given values (e.g. S_ref: the fixed point)"""
    import fake_solve as F
    import xarray as xr

    def f(self, *a, **k):
        r = F.fake_solve(self, *a, **k)
        if 'Line-s_nom' in self.variables:
            v = self.variables['Line-s_nom']
            nm = list(v.labels.coords['name'].values)
            v.solution = xr.DataArray(values.reindex(nm).values.astype(float), coords={'name': nm}, dims='name')
        return r
    return f


def test_v3_full_chain_zero_solver(tmp_path, monkeypatch):
    """the v3 chain on the small network through the real build code and stage rules: (a) capacities at the fixed point -> IT1
    converged -> candidate -> LP2, IT2 refused; (b) capacities at their lower row (the trust floor) -> not converged -> IT2 -> STOP"""
    import linopy
    import fake_solve as F
    import loss_basis_lp1 as L
    import baseline_v16_calibration as V16
    raw = tiny_raw(tmp_path / 'raw.nc')
    v, _ = V16.load_cfg()

    def setup(tag):
        rc = yaml.safe_load(CFG3.read_text(encoding='utf-8')); rc['post_v16']['out_dir'] = str(tmp_path / tag)
        p = tmp_path / f'config.{tag}.yaml'; p.write_text(yaml.safe_dump(rc), encoding='utf-8')
        return p, L.load(p)

    def lp1_build(stage, c_):
        s_ref = S_PREP if stage == 'LP1_LOSSY_IT1' else pd.read_csv(L.out_dir(c_) / 'LP1_LOSSY_IT1' / 'LP1_LINE_SOLUTION.csv', index_col=0).s_nom_opt
        n, info = L.build_lp1_from(raw, S_PREP, s_ref, c_)
        return n, dict(info, raw_nc=raw), v

    def gate_for(p):
        def gate(stage):
            g = L.check(stage, cfg_path=p)
            keep = [x for x in g['reasons'] if x.startswith((stage, 'LP2_LOSSY_CANDIDATE only', 'LP1_LOSSY_IT2 only', 'candidate', 'LP budget')) or 'already has' in x]
            return dict(g, approved=not keep, reasons=keep)
        return gate
    # (a) fixed point
    pa, ca = setup('a')
    monkeypatch.setattr(linopy.Model, 'solve', fake_at(S_PREP))
    q1 = L.run('LP1_LOSSY_IT1', 1, cfg_path=pa, gate_fn=gate_for(pa), lp1_build=lp1_build)
    assert q1['r_converged'] is True and q1['candidate_written'] is True and q1['convergence']['lines_at_trust_floor'] == []
    with pytest.raises(SystemExit):
        L.run('LP1_LOSSY_IT2', 1, cfg_path=pa, gate_fn=gate_for(pa), lp1_build=lp1_build)       # IT1 converged -> IT2 refused
    monkeypatch.setattr(linopy.Model, 'solve', F.fake_solve)
    q3 = L.run('LP2_LOSSY_CANDIDATE', 1, cfg_path=pa, gate_fn=gate_for(pa))
    assert q3['transmission_losses'] == 2
    sol = pd.read_csv(L.out_dir(ca) / 'LP1_LOSSY_IT1' / 'LP1_LINE_SOLUTION.csv', index_col=0)
    assert 's_floor' in sol and np.allclose(sol.s_floor, np.maximum(sol.s_nom_input, 0.75 * sol.s_ref))
    # (b) on the trust floor
    pb, cb = setup('b')
    q1 = L.run('LP1_LOSSY_IT1', 1, cfg_path=pb, gate_fn=gate_for(pb), lp1_build=lp1_build)
    assert q1['r_converged'] is False and 'TL35' in q1['convergence']['lines_at_trust_floor']
    q2 = L.run('LP1_LOSSY_IT2', 1, cfg_path=pb, gate_fn=gate_for(pb), lp1_build=lp1_build)
    assert q2['r_converged'] is False and q2['candidate_written'] is False
    with pytest.raises(SystemExit):
        L.run('LP2_LOSSY_CANDIDATE', 1, cfg_path=pb, gate_fn=gate_for(pb))                       # STOP: no LP2
    lg = pd.read_csv(L.ledger(cb)[0], dtype=str, keep_default_na=False)
    assert list(lg.stage) == ['LP1_LOSSY_IT1', 'LP1_LOSSY_IT2'] and set(lg.state) == {'DONE'}


def test_v1_v2_builds_unchanged_by_v3_code(tmp_path):
    """v1 / v2 configs: no loss_upper key -> 'cap' (constant bound at the cap, floor = raw) exactly as solved in NEXT-08 / NEXT-08b"""
    import loss_basis_lp1 as L
    _, n2, i2 = build(tmp_path, CFG2)
    assert i2['loss_upper'] == 'cap' and i2['s_floor'] is None and np.allclose(n2.lines.s_nom_min, i2['s_raw'])
    r_pu = n2.lines.r / 230.0 ** 2
    lu = n2.model.constraints['Line-loss_upper'].rhs.transpose(..., 'name').values
    assert np.allclose(lu, np.broadcast_to((r_pu * (0.7 * n2.lines.s_nom_max) ** 2).values, lu.shape))
    with pytest.raises(ValueError, match='loss_upper'):
        L.build_lp1_from(tiny_raw(tmp_path / 'raw2.nc'), S_PREP, S_REF, dict(L.load(CFG2), loss_upper='affine_s_ref', loss_tangent_reference='cap'))
