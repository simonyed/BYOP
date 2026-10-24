#!/usr/bin/env python3
"""NEXT-08 A4: lossy 2025 LP1 calibration -> candidate baseline -> fixed-asset lossy LP2 check (transmission_losses = 2, the
S0-S3 basis). Separate from the consumed v1.6 runner / ledger and from the NEXT-07 W6 lossy LP2 runner; nothing frozen is
overwritten (the candidate is a NEW NetCDF in results/BYOP/next08_lossy_lp1/). Run on L2 from workflow/:
    python byop/run/loss_basis_lp1.py --build                          # LP1 (iteration 1) and LP2 models built + checked, NO solve
    python byop/run/loss_basis_lp1.py --stage LP1_LOSSY_IT1            # GATED (config.byop_lossy_lp1.yaml)
    python byop/run/loss_basis_lp1.py --stage LP1_LOSSY_IT2            # GATED; only if IT1 is optimal and NOT r-converged
    python byop/run/loss_basis_lp1.py --stage LP2_LOSSY_CANDIDATE      # GATED; only after an optimal, r-converged LP1 whose
                                                                        # pre-registered expansion guards all pass
LP1 = the v1.6 LP1 (build_2025_baseline_tamu.calibrate_2025) on the same raw network, fleet, load, objective and prices
(UPLIFT_COST 2e6 USD per MVA of s_nom, SHED_COST 1e6 USD/MWh, every line extendable from its raw s_nom), with ONLY these changes:
  1  transmission_losses = 2 (PyPSA tangents; rating row |s| + loss <= s_max_pu s_nom)
  2  s_nom_max = CAP_FACTOR x v1.6 prepared s_nom (finite: required by the PyPSA loss formulation, whose tangents sit at 1/2 and 1 x
     s_max_pu s_nom_max - i.e. exactly at the v1.6 rating - and the per-line over-expansion guard)
  3  r = r_raw x s_nom_raw / s_ref (equivalent parallel-circuit resistance proxy, fixed inside each LP): s_ref = v1.6 prepared s_nom in
     iteration 1, the iteration-1 solution in iteration 2. x stays raw (researcher-approved X1 flow split). Never r x s_nom in one LP.
Convergence after an LP1: max over lines |r_used / r_implied(s_opt) - 1| <= R_TOL (r_implied = r_raw s_raw / s_opt) or the line's
|s_opt - s_ref| <= S_TOL_MVA. Not converged after IT2 -> STOP (no LP2). Guards (on the converged LP1, before any LP2):
  G1 total uplift over raw <= G1_FACTOR x v1.6 total uplift; G2 no line at its s_nom_max; G3 uplift on lines NOT uplifted in v1.6 <=
  G3_MAX_MVA in total (each such line > 50 MVA is listed for evidence review). LP2 acceptance = the unchanged v1.6 tolerances."""
from __future__ import annotations

import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/build')); sys.path.insert(0, str(WF / 'byop/run'))
import baseline_v16_calibration as V16  # noqa: E402
import loss_basis_lp2 as LB  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402
import post_v16_gate as G  # noqa: E402

CFG = WF / 'config/config.byop_lossy_lp1.yaml'
STAGES = ['LP1_LOSSY_IT1', 'LP1_LOSSY_IT2', 'LP2_LOSSY_CANDIDATE']
LOG_COLS = ['attempt_id', 'stage', 'state', 'started_utc', 'finished_utc', 'status', 'termination', 'seconds', 'r_converged', 'guards_pass',
            'acceptance_pass', 'note']
UPLIFT_COST, SHED_COST = 2e6, 1e6          # build_2025_baseline_tamu.py (unchanged v1.6 calibration prices)
CANDIDATE_NC = 'baseline_2025_tamu_lossy_candidate.nc'


def load(cfg_path=CFG):
    return yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))['post_v16']


def out_dir(c):
    return WF / c['out_dir']


def ledger(c):
    p = out_dir(c) / 'LOSSY_LP1_SOLVE_LOG.csv'
    return p, (pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame(columns=LOG_COLS))


def v16_files():
    v, _ = V16.load_cfg()
    d = V16.out_dir(v)
    return v, d / 'baseline_2025_tamu_raw_uncalibrated.nc', d / 'baseline_2025_tamu_prepared.nc'


# ------------------------------------------------------------------------------------------------ gate
def check(stage, cfg_path=CFG, git_fn=LB.git):
    """fail-closed; never touches a solver. Reuses the W6 approval / SHA / manifest checks, then this chain's stage rules."""
    c = load(cfg_path)
    r, head, asha = LB.common_checks(c, cfg_path, git_fn)          # approval, SHA, clean tree, source, manifest, v1.6 baseline
    rb = ROOT / c['raw_baseline']['path']
    if not rb.exists() or A2G.file_shas(rb)['raw'] != c['raw_baseline']['sha256']:
        r.append('v1.6 raw (pre-calibration) baseline missing or SHA differs')
    if stage not in STAGES or stage not in c['stages']:
        r.append(f'stage {stage} not in {c["stages"]}')
    _, lg = ledger(c)
    if (lg.stage == stage).any():
        r.append(f'{stage} already has a logged call (zero retries)')
    if len(lg) >= int(c['max_lp_calls']):
        r.append('LP budget used')
    done = lambda s: lg[(lg.stage == s) & (lg.state == 'DONE') & (lg.termination == 'optimal')]
    if stage == 'LP1_LOSSY_IT2':
        if not (done('LP1_LOSSY_IT1').r_converged == 'False').any():
            r.append('LP1_LOSSY_IT2 only after an optimal LP1_LOSSY_IT1 that is NOT r-converged')
    if stage == 'LP2_LOSSY_CANDIDATE':
        last = pd.concat([done('LP1_LOSSY_IT1'), done('LP1_LOSSY_IT2')])
        ok = last[(last.r_converged == 'True') & (last.guards_pass == 'True')]
        if ok.empty:
            r.append('LP2_LOSSY_CANDIDATE only after an optimal, r-converged LP1 whose expansion guards all pass')
        if not (out_dir(c) / CANDIDATE_NC).exists():
            r.append(f'candidate network {CANDIDATE_NC} missing')
    return dict(approved=not r, reasons=r, head=head, approved_git_sha=asha or None, stage=stage)


# ------------------------------------------------------------------------------------------------ model pieces (pure)
def r_proxy(r_raw, s_raw, s_ref):
    """equivalent parallel-circuit resistance proxy: r scales with raw / reference capacity (never above raw)"""
    return r_raw * (s_raw / s_ref).clip(upper=1.0)


def prepare_lp1(raw_nc, s_ref, cap_factor, s_prep):
    """the v1.6 LP1 network (calibrate_2025 statement by statement) + the lossy-basis changes 2 and 3 of the module docstring"""
    import pypsa
    c = pypsa.Network(str(raw_nc))
    g = c.generators
    c.remove('Generator', g.index[g.p_nom_extendable | (g.build_year > 2025)])
    s = c.storage_units
    c.remove('StorageUnit', s.index[s.p_nom_extendable | (s.build_year > 2025)])
    for df in (c.generators, c.storage_units, c.lines):
        df['lifetime'] = np.inf; df['build_year'] = 0
    if len(c.global_constraints):
        c.remove('GlobalConstraint', c.global_constraints.index)
    if 'load_shed' not in c.carriers.index:
        c.add('Carrier', 'load_shed')
    buses = sorted(set(c.loads.bus))
    c.add('Generator', [f'{b} shed' for b in buses], bus=buses, carrier='load_shed', p_nom=1e5, marginal_cost=SHED_COST)
    s_raw = c.lines.s_nom.copy(); r_raw = c.lines.r.copy()
    c.lines['s_nom_min'] = c.lines.s_nom
    c.lines['s_nom_extendable'] = True
    c.lines['s_nom_max'] = cap_factor * s_prep.reindex(c.lines.index)
    c.lines['capital_cost'] = UPLIFT_COST
    c.lines['r'] = r_proxy(r_raw, s_raw, s_ref.reindex(c.lines.index))
    return c, dict(s_raw=s_raw, r_raw=r_raw, buses=buses)


def convergence(s_opt, s_ref, s_raw, r_tol, s_tol, s_floor=None):
    """the unchanged per-line r / capacity rule; v3 (s_floor given) additionally: no line may end on a trust floor above its raw
    s_nom (the affine loss bound is only exact-and-cap-free above the floor, so such a solution is not a fixed point)"""
    r_used = (s_raw / s_ref).clip(upper=1.0); r_impl = (s_raw / s_opt).clip(upper=1.0)
    rel = (r_used / r_impl - 1.0).abs()
    ok_line = (rel <= r_tol) | ((s_opt - s_ref).abs() <= s_tol)
    worst = rel[~ok_line].sort_values(ascending=False)
    info = dict(max_rel_r_gap=float(rel.max()), lines_not_converged=int((~ok_line).sum()), worst={k: round(float(v), 4) for k, v in worst.head(8).items()})
    ok = bool(ok_line.all())
    if s_floor is not None:
        fl = s_floor.reindex(s_opt.index)
        at_floor = s_opt.index[(fl > s_raw.reindex(s_opt.index) + 1e-6) & (s_opt <= fl + 1e-3 * fl)]
        info.update(lines_at_trust_floor=list(at_floor), trust_floor_lines=int((fl > s_raw.reindex(s_opt.index) + 1e-6).sum()))
        ok = ok and len(at_floor) == 0
    return ok, info


def guards(s_opt, s_raw, s_prep, s_max, g):
    up = (s_opt - s_raw).clip(lower=0.0); up16 = (s_prep - s_raw).clip(lower=0.0)
    v16_set = up16.index[up16 > 0.5]
    new = up[~up.index.isin(v16_set) & (up > 0.5)]
    at_cap = up.index[(s_max - s_opt) <= 1e-3 * s_max]
    res = dict(total_uplift_MVA=float(up.sum()), v16_total_uplift_MVA=float(up16.sum()), G1_limit_MVA=float(g['G1_factor'] * up16.sum()),
               G1=bool(up.sum() <= g['G1_factor'] * up16.sum() + 1e-6), lines_at_cap=list(at_cap), G2=len(at_cap) == 0,
               new_lines_uplift_MVA=float(new.sum()), new_lines=new.round(1).to_dict(), new_lines_over_50MVA=list(new.index[new > 50]),
               G3=bool(new.sum() <= g['G3_max_MVA'] + 1e-6), uplifted_lines=int((up > 0.5).sum()))
    res['all_pass'] = res['G1'] and res['G2'] and res['G3']
    return res


def candidate_network(raw_nc, s_final):
    """the candidate baseline: v1.6 raw network with s_nom = s_final and r = parallel proxy at s_final (x raw, nothing else changed)"""
    import pypsa
    n = pypsa.Network(str(raw_nc))
    s_raw, r_raw = n.lines.s_nom.copy(), n.lines.r.copy()
    sf = s_final.reindex(n.lines.index)
    n.lines['s_nom'] = np.maximum(sf, s_raw)
    n.lines['r'] = r_proxy(r_raw, s_raw, n.lines.s_nom)
    return n


def apply_reference_tangents(n, s_ref, cap):
    """NEXT-08b: PyPSA places the two loss tangents at 1/2 and 1 x s_max_pu x s_nom_max of each line. The model is created with
    s_nom_max = s_ref (the iteration's reference capacity), so the tangents are exactly the ones a fixed-capacity LP2 / S0-S3 model
    of that capacity uses; afterwards the capacity row (Line-ext-s_nom-upper) and the loss upper bound (Line-loss_upper) are reset
    to the guard cap, so the feasible capacity range is unchanged. Purely parameter changes of existing rows: the model stays an LP
    with the same size. Returns the per-line reference used."""
    m = n.model
    up = m.constraints['Line-ext-s_nom-upper']
    names = list(up.rhs.coords['name'].values)
    up.update(rhs=up.rhs.copy(data=np.asarray(cap.reindex(names).values, dtype=float)))
    import xarray as xr
    lu = m.constraints['Line-loss_upper']
    lnames = list(lu.rhs.coords['name'].values)
    scale = ((cap.reindex(lnames) / s_ref.reindex(lnames)) ** 2).values
    lu.update(rhs=lu.rhs * xr.DataArray(scale, coords={'name': lnames}, dims='name'))   # r (s_max_pu cap)^2 = r (s_max_pu s_ref)^2 x scale
    n.lines['s_nom_max'] = cap.reindex(n.lines.index)
    return s_ref.reindex(names)


def trust_floor_factor(segments):
    """the top tangent (k = K) alone is the tangent envelope for |s| >= (2K - 1) / (2K) x s_max_pu s_ref (the intersection of
    tangents K - 1 and K); 0.75 for K = 2"""
    return (2 * segments - 1) / (2 * segments)


def apply_affine_loss_upper(n, s_ref, s_raw, segments):
    """NEXT-08b v3: replace the constant loss upper bound by its affine tangent in the capacity variable at S_ref
        loss <= r_pu (2 R_ref R - R_ref^2),   R = s_max_pu s_nom (LP variable), R_ref = s_max_pu S_ref
    and raise the capacity floor of each line to max(s_raw, f S_ref), f = trust_floor_factor(K).
    Properties (proof in BYOP_NEXT_08B_LP1_TANGENT_FIX/LOSS_UPPER_FIX_DESIGN.md, tests in test_next08b_loss_upper.py):
      * s_nom = S_ref: the bound is r_pu R_ref^2, i.e. the LP2 / S0-S3 row of that capacity (with the S_ref tangents: identical rows);
      * U(R) <= r_pu R^2 (tangent below the parabola): never more dissipation room than LP2 at the same capacity;
      * R >= f R_ref: U(R) >= tangent envelope at |s| = R, so the bound never limits a flow the rating row allows (no hidden cap);
      * below f R_ref no affine bound exact at S_ref can avoid such a cap (it would also force s_nom >= S_ref / 2 through loss >= 0),
        hence the explicit, reported floor; a line ending on a floor above its raw s_nom counts as not converged.
    Same number of rows (Line-loss_upper replaced one for one), still an LP. Returns the floor."""
    import xarray as xr
    m = n.model
    L = n.lines
    old = m.constraints['Line-loss_upper']
    names = list(old.rhs.coords['name'].values)
    assert (np.asarray(old.labels.values) >= 0).all(), 'masked Line-loss_upper rows'
    r_pu = (L.r / n.buses.v_nom.reindex(L.bus0).values ** 2).reindex(names)
    r_ref = L.s_max_pu.reindex(names) * s_ref.reindex(names)
    da = lambda x: xr.DataArray(np.asarray(x, dtype=float), coords={'name': names}, dims='name')
    loss, snom = m.variables['Line-loss'].sel(name=names), m.variables['Line-s_nom'].sel(name=names)
    m.remove_constraints('Line-loss_upper')
    m.add_constraints(loss - da(2 * r_pu * r_ref * L.s_max_pu.reindex(names)) * snom <= da(-r_pu * r_ref ** 2), name='Line-loss_upper')
    lo = m.constraints['Line-ext-s_nom-lower']
    lnames = list(lo.rhs.coords['name'].values)
    floor = np.maximum(s_raw.reindex(lnames), trust_floor_factor(segments) * s_ref.reindex(lnames))
    lo.update(rhs=lo.rhs.copy(data=np.asarray(floor.values, dtype=float)))
    n.lines['s_nom_min'] = floor.reindex(n.lines.index)
    return floor


def row_coefficients(m, cname, var_names):
    """per row of constraint cname: the summed coefficient on each listed variable (by label membership), the rhs and the sign;
    arrays transposed to (..., name)"""
    c = m.constraints[cname]
    v = np.asarray(c.vars.transpose(..., 'name', '_term').values)
    co = np.asarray(c.coeffs.transpose(..., 'name', '_term').values, dtype=float)
    out = {}
    for vn in var_names:
        lab = np.asarray(m.variables[vn].labels.values).ravel()
        out[vn] = np.where(np.isin(v, lab[lab >= 0]), co, 0.0).sum(axis=-1)
    other = ~np.isin(v, np.concatenate([np.asarray(m.variables[x].labels.values).ravel() for x in var_names])) & (v >= 0)
    return dict(coef=out, rhs=np.asarray(c.rhs.transpose(..., 'name').values, dtype=float), sign=np.unique(np.asarray(c.sign.values).astype(str)),
                names=list(c.rhs.coords['name'].values), other_terms=int(other.sum()))


def loss_rows_report(n, s_ref, s_cap, s_floor, segments=2):
    """static proof on a BUILT LP1 model: read every Line-loss_upper, Line-loss_tangents-*, Line-ext-s_nom-upper/-lower and line rating
    row back from linopy and check them against the v3 design; then, per line, evaluate the extracted rows over the capacity domain
    [floor, cap] (incl. S_ref): margin of the upper bound over the tangent envelope at |s| = R (>= 0: no hidden flow cap), the bound vs
    r R^2 (<= : no more dissipation room than LP2 at that capacity), the fixed point (= r R_ref^2) and non-negativity"""
    m = n.model
    L = n.lines
    smax = L.s_max_pu
    r_pu = L.r / n.buses.v_nom.reindex(L.bus0).values ** 2
    R_ref = smax * s_ref.reindex(L.index)
    rep = {}
    up = row_coefficients(m, 'Line-loss_upper', ['Line-loss', 'Line-s_nom'])
    nm = up['names']
    a_s = -up['coef']['Line-s_nom'] / up['coef']['Line-loss']                 # U(s_nom) = a_s s_nom + b
    b = up['rhs'] / up['coef']['Line-loss']
    exp_a = (2 * r_pu * R_ref * smax).reindex(nm).values
    exp_b = (-r_pu * R_ref ** 2).reindex(nm).values
    rep['loss_upper'] = dict(rows=int(a_s.size), sign=list(up['sign']), other_terms=up['other_terms'],
                             slope_max_abs_dev=float(np.nanmax(np.abs(a_s - exp_a))), offset_max_abs_dev=float(np.nanmax(np.abs(b - exp_b))),
                             loss_coef_unique=sorted(set(np.round(up['coef']['Line-loss'].ravel(), 12))))
    tan = tangent_rows_vs_reference(n, s_ref.reindex(L.index), segments)
    rep['loss_tangents'] = tan
    capr = row_coefficients(m, 'Line-ext-s_nom-upper', ['Line-s_nom'])
    lor = row_coefficients(m, 'Line-ext-s_nom-lower', ['Line-s_nom'])
    rep['s_nom_upper'] = dict(sign=list(capr['sign']), rhs_max_abs_dev=float(np.max(np.abs(capr['rhs'] - s_cap.reindex(capr['names']).values))))
    rep['s_nom_lower'] = dict(sign=list(lor['sign']), rhs_max_abs_dev=float(np.max(np.abs(lor['rhs'] - s_floor.reindex(lor['names']).values))),
                              lines_floor_above_raw=None)
    rat = {}
    for side, sg in (('upper', 1.0), ('lower', -1.0)):
        rr = row_coefficients(m, f'Line-ext-s-{side}', ['Line-s', 'Line-s_nom', 'Line-loss'])
        smx = smax.reindex(rr['names']).values
        rat[side] = dict(sign=list(rr['sign']), other_terms=rr['other_terms'], s_coef=sorted(set(np.round(rr['coef']['Line-s'].ravel(), 12))),
                         loss_coef=sorted(set(np.round(rr['coef']['Line-loss'].ravel(), 12))),
                         s_nom_coef_max_abs_dev=float(np.max(np.abs(rr['coef']['Line-s_nom'] + sg * smx))), rhs_max_abs=float(np.max(np.abs(rr['rhs']))))
    rep['rating_rows'] = rat
    # domain evaluation from the extracted rows (first snapshot row per line; all snapshots identical: checked by the max-dev above)
    a1 = pd.Series(a_s.reshape(-1, len(nm))[0], nm); b1 = pd.Series(b.reshape(-1, len(nm))[0], nm)
    dom = {}
    worst = dict(margin=np.inf, line=None, R_over_Rref=None)
    for l in nm:
        grid = np.unique(np.r_[np.linspace(s_floor[l], s_cap[l], 401), s_ref[l]])
        R = smax[l] * grid
        U = a1[l] * grid + b1[l]
        Rr = R_ref[l]
        env = np.maximum.reduce([np.zeros_like(R)] + [2 * r_pu[l] * (k / segments * Rr) * R - r_pu[l] * (k / segments * Rr) ** 2 for k in range(1, segments + 1)])
        mg = U - env
        if mg.min() < worst['margin']:
            worst = dict(margin=float(mg.min()), line=l, R_over_Rref=float(R[mg.argmin()] / Rr))
        dom[l] = dict(min_margin_over_envelope=float(mg.min()), max_U_minus_rR2=float((U - r_pu[l] * R ** 2).max()), min_U=float(U.min()),
                      fixed_point_dev=float(abs(a1[l] * s_ref[l] + b1[l] - r_pu[l] * Rr ** 2)),
                      floor_over_ref=float(s_floor[l] / s_ref[l]), cap_over_ref=float(s_cap[l] / s_ref[l]))
    D = pd.DataFrame(dom).T
    scale = (r_pu * R_ref ** 2).reindex(nm)
    rep['domain'] = dict(lines=len(nm), worst_margin=worst, min_margin_rel=float((D.min_margin_over_envelope / scale).min()),
                         max_U_minus_rR2_rel=float((D.max_U_minus_rR2 / scale).max()), min_U_rel=float((D.min_U / scale).min()),
                         fixed_point_max_dev_rel=float((D.fixed_point_dev / scale).max()))
    return rep, D


def tangent_rows_vs_reference(n, s_ref, segments=2):
    """static proof: every Line-loss_tangents row of the built model has slope 2 r_pu p_k and offset -r_pu p_k^2 with
    p_k = k / segments x s_max_pu x s_ref (the fixed-capacity LP2 / S0-S3 rows of that capacity); returns max abs deviations"""
    m = n.model
    r_pu = n.lines.r / n.buses.v_nom.reindex(n.lines.bus0).values ** 2
    slabels = np.asarray(m.variables['Line-s'].labels.values).ravel()
    out = {}
    for k in range(1, segments + 1):
        for sign in (-1, 1):
            c = m.constraints[f'Line-loss_tangents-{k}-{sign}']
            names = list(c.rhs.coords['name'].values)
            pk = k / segments * n.lines.s_max_pu.reindex(names).values * s_ref.reindex(names).values
            rp = r_pu.reindex(names).values
            rhs = np.asarray(c.rhs.transpose(..., 'name').values, dtype=float)
            v = np.asarray(c.vars.transpose(..., 'name', '_term').values); co = np.asarray(c.coeffs.transpose(..., 'name', '_term').values, dtype=float)
            slope = np.where(np.isin(v, slabels), co, 0.0).sum(axis=-1)
            out[f'{k}{"+" if sign > 0 else "-"}'] = dict(offset_max_abs_dev=float(np.nanmax(np.abs(rhs - (-rp * pk ** 2)))),
                                                         slope_max_abs_dev=float(np.nanmax(np.abs(slope - sign * 2 * rp * pk))))
    return out


ROW_FAMILIES = ['Line-loss_upper', 'Line-loss_tangents-1--1', 'Line-loss_tangents-1-1', 'Line-loss_tangents-2--1', 'Line-loss_tangents-2-1',
                'Line-ext-s-upper', 'Line-ext-s-lower', 'Line-ext-s_nom-upper', 'Line-ext-s_nom-lower']


def line_rows(n, t=0):
    """the built rows of every line at snapshot t, read back from linopy: per family the coefficients on Line-loss / Line-s /
    Line-s_nom, the rhs and the sign (a pure LP row: lhs = c_loss loss + c_s s + c_snom s_nom  (<= | >=)  rhs)"""
    m = n.model
    out = {}
    for cn in ROW_FAMILIES:
        vs = [x for x in ('Line-loss', 'Line-s', 'Line-s_nom') if x in m.variables]
        rc = row_coefficients(m, cn, vs)
        k = len(rc['names'])
        assert rc['other_terms'] == 0 and len(rc['sign']) == 1, f'{cn}: unexpected terms or mixed signs'
        row = lambda a: pd.Series(np.asarray(a).reshape(-1, k)[t if np.asarray(a).size > k else 0], rc['names'])
        out[cn] = dict(sign=str(rc['sign'][0]), rhs=row(rc['rhs']), **{x: row(rc['coef'][x]) for x in vs})
    return out


def row_violations(rows, s_nom, s, loss):
    """positive = violated amount of each row family at the point (s_nom, s, loss) per line (Series inputs on the line index)"""
    v = {}
    for cn, r in rows.items():
        lhs = r.get('Line-loss', 0) * loss + r.get('Line-s', 0) * s + r.get('Line-s_nom', 0) * s_nom
        v[cn] = (lhs - r['rhs']) if r['sign'] == '<=' else (r['rhs'] - lhs)
    return pd.DataFrame(v)


def representative_point_checks(n, s_ref, s_cap, s_floor, segments=2):
    """item 4 on the BUILT rows, every line, capacities floor, 0.9 S_ref (if above the floor), S_ref, (S_ref + cap) / 2 and cap:
      A  the largest flow the rating row allows, |s| + env(|s|) = R, with loss = env, in both directions: every row satisfied
      B  a slightly larger flow (|s| + env(|s|) / 2, still < R): only the rating row is violated (no loss row is the flow limit)
      C  s = 0, loss = the v3 bound U(s_nom): no loss row violated; U + 0.1 % of r R_ref^2: Line-loss_upper violated
      D  s_nom 0.1 % below the floor (zero flow, zero loss): only Line-ext-s_nom-lower violated (no other implied capacity floor)"""
    L = n.lines
    rows = line_rows(n)
    nm = rows['Line-loss_upper']['rhs'].index
    smax = L.s_max_pu.reindex(nm)
    r_pu = (L.r / n.buses.v_nom.reindex(L.bus0).values ** 2).reindex(nm)
    Rr = smax * s_ref.reindex(nm)
    env = lambda a: pd.Series(np.maximum.reduce([np.asarray(a * 0.0, dtype=float)] + [np.asarray(2 * r_pu * (k / segments * Rr) * a - r_pu * (k / segments * Rr) ** 2, dtype=float)
                                                  for k in range(1, segments + 1)]), index=nm)
    up = rows['Line-loss_upper']
    U = lambda sn: (up['rhs'] - up['Line-s_nom'] * sn) / up['Line-loss']
    tol = 1e-7
    bad = {k: [] for k in 'ABCD'}
    levels = dict(floor=s_floor.reindex(nm), s_ref=s_ref.reindex(nm), mid=(s_ref.reindex(nm) + s_cap.reindex(nm)) / 2, cap=s_cap.reindex(nm))
    p9 = 0.9 * s_ref.reindex(nm)
    levels['0.9_s_ref'] = p9.where(p9 >= levels['floor'], levels['s_ref'])
    rating = {'Line-ext-s-upper', 'Line-ext-s-lower'}
    for lv, sn in levels.items():
        R = smax * sn
        lo, hi = pd.Series(0.0, nm), R.copy()
        for _ in range(80):                                               # |s| + env(|s|) = R (monotone): bisection
            mid = (lo + hi) / 2
            ok = mid + env(mid) <= R
            lo, hi = lo.where(~ok, mid), hi.where(ok, mid)
        smx = lo
        for sg in (1.0, -1.0):
            va = row_violations(rows, sn, sg * smx, env(smx))
            bad['A'] += [(lv, l, sg, c) for l in nm for c in va.columns if va.at[l, c] > tol * max(1.0, float(R[l]))]
            e0 = env(smx)
            s_b = smx + (e0 / 2).where(e0 > 0, 1e-3 * R)
            vb = row_violations(rows, sn, sg * s_b, env(s_b))
            for l in nm:
                viol = {c for c in vb.columns if vb.at[l, c] > tol * max(1.0, float(R[l]))}
                if not viol or not viol <= rating:
                    bad['B'].append((lv, l, sg, sorted(viol)))
        u = U(sn)
        vc = row_violations(rows, sn, 0.0 * sn, u)
        eps = 1e-3 * r_pu * Rr ** 2
        vc2 = row_violations(rows, sn, 0.0 * sn, u + eps)
        for l in nm:
            if (vc.loc[l, [c for c in vc.columns if c not in rating]] > tol * max(1.0, float(R[l]))).any():
                bad['C'].append((lv, l, 'U infeasible', vc.loc[l][vc.loc[l] > 0].round(6).to_dict()))
            if vc2.at[l, 'Line-loss_upper'] <= 0:
                bad['C'].append((lv, l, 'U + eps not cut'))
    fl = levels['floor'] * (1 - 1e-3)
    vd = row_violations(rows, fl, 0.0 * fl, 0.0 * fl)
    for l in nm:
        viol = {c for c in vd.columns if vd.at[l, c] > tol}
        if viol != {'Line-ext-s_nom-lower'}:
            bad['D'].append((l, sorted(viol)))
    return dict(lines=len(nm), levels=list(levels), failures={k: len(x) for k, x in bad.items()}, examples={k: x[:5] for k, x in bad.items() if x}), bad


def fixed_point_vs_lp2(n1, s_ref, fixed_nc, v, segments=2):
    """item 3: the LP1 v3 loss rows evaluated at s_nom = S_ref vs the rows of the fixed-capacity LP2 / S0-S3 model (V16.prepare_fixed,
    transmission_losses) of a network whose s_nom = S_ref and r = r proxy at S_ref; max abs deviations per row family"""
    F, _ = V16.prepare_fixed(v, fixed_nc)
    F.optimize.create_model(transmission_losses=segments)
    L1, LF = n1.lines, F.lines
    names = list(L1.index)
    out = dict(s_nom_dev=float((LF.s_nom.reindex(names) - s_ref.reindex(names)).abs().max()), r_dev=float((LF.r.reindex(names) - L1.r).abs().max()))
    m1, mF = n1.model, F.model

    def frame(m, cname, var=None):
        rc = row_coefficients(m, cname, [var] if var else ['Line-loss'])
        val = rc['rhs'] if var is None else rc['coef'][var]
        return pd.DataFrame(val.reshape(-1, len(rc['names'])), columns=rc['names'])[names]
    up1 = row_coefficients(m1, 'Line-loss_upper', ['Line-loss', 'Line-s_nom'])
    u1 = pd.DataFrame((up1['rhs'] / up1['coef']['Line-loss']).reshape(-1, len(up1['names'])), columns=up1['names'])
    a1 = pd.DataFrame((-up1['coef']['Line-s_nom'] / up1['coef']['Line-loss']).reshape(-1, len(up1['names'])), columns=up1['names'])
    U1 = (a1 * s_ref.reindex(up1['names']).values + u1)[names]               # LP1 bound at s_nom = S_ref
    UF = frame(mF, 'Line-loss_upper')
    out['loss_upper_max_abs_dev'] = float(np.abs(U1.values - UF.values).max())
    out['loss_upper_rel_dev'] = float(((U1 - UF).abs() / UF.abs().clip(lower=1e-12)).values.max())
    for k in range(1, segments + 1):
        for sg in (-1, 1):
            cn = f'Line-loss_tangents-{k}-{sg}'
            out[f'tangent_{k}{"+" if sg > 0 else "-"}_rhs_dev'] = float(np.abs(frame(m1, cn).values - frame(mF, cn).values).max())
            out[f'tangent_{k}{"+" if sg > 0 else "-"}_slope_dev'] = float(np.abs(frame(m1, cn, 'Line-s').values - frame(mF, cn, 'Line-s').values).max())
    for side in ('upper', 'lower'):
        r1 = row_coefficients(m1, f'Line-ext-s-{side}', ['Line-s', 'Line-loss', 'Line-s_nom'])
        rF = row_coefficients(mF, f'Line-fix-s-{side}', ['Line-s', 'Line-loss'])
        k1 = r1['names']
        eff1 = pd.DataFrame((r1['rhs'] - r1['coef']['Line-s_nom'] * s_ref.reindex(k1).values).reshape(-1, len(k1)), columns=k1)[names]   # rhs at S_ref
        effF = pd.DataFrame(rF['rhs'].reshape(-1, len(rF['names'])), columns=rF['names'])[names]
        out[f'rating_{side}_rhs_dev'] = float(np.abs(eff1.values - effF.values).max())
        out[f'rating_{side}_coef_dev'] = float(max(np.abs(r1['coef'][x].reshape(-1, len(k1)) - pd.DataFrame(rF['coef'][x].reshape(-1, len(rF['names'])), columns=rF['names'])[k1].values).max()
                                                   for x in ('Line-s', 'Line-loss')))
    del F
    return out


def dissipation_room(n, s_ref, s_cap, s_floor, s_prep=None, segments=2):
    """item 1 (GW check), analytic on the built rows: room of the v3 bound above the fixed-point bound if LP1 builds capacity,
    U(s) - U(S_ref) = 2 r_pu R_ref s_max_pu (s - S_ref) MW per line and step, vs the v1 / v2 cap-based bound r_pu (s_max_pu cap)^2"""
    L = n.lines
    r_pu = L.r / n.buses.v_nom.reindex(L.bus0).values ** 2
    smax = L.s_max_pu
    Rr = smax * s_ref.reindex(L.index)
    rate = 2 * r_pu * Rr * smax                                                       # MW of extra bound per MVA built
    old_room = r_pu * ((smax * s_cap.reindex(L.index)) ** 2 - Rr ** 2)                # v2: allowance above LP2 already at s_nom = S_ref
    new_room_cap = rate * (s_cap.reindex(L.index) - s_ref.reindex(L.index))
    return dict(rate_MW_per_MVA_max=float(rate.max()), rate_line=str(rate.idxmax()), rate_MW_per_MVA_p95=float(rate.quantile(0.95)),
                v2_room_at_s_ref_total_MW=float(old_room.sum()), v3_room_at_s_ref_total_MW=0.0,
                v3_room_if_every_line_at_cap_total_MW=float(new_room_cap.sum()),
                v3_room_per_1000_MVA_built_on_the_best_line_MW=float(1000 * rate.max()),
                top_rate_lines={k: round(float(x), 5) for k, x in rate.sort_values(ascending=False).head(6).items()})


def v3_model_checks(n, info, cap, v, fixed_nc=None):
    s_ref = info['s_ref'].reindex(n.lines.index); floor = info['s_floor'].reindex(n.lines.index); s_raw = info['s_raw'].reindex(n.lines.index)
    rows, D = loss_rows_report(n, s_ref, cap.reindex(n.lines.index), floor)
    out = dict(n_vars=int(n.model.nvars), n_cons=int(n.model.ncons), rows=rows,
               s_nom_min_equals_floor_and_floor_ge_raw=bool(np.allclose(n.lines.s_nom_min, floor) and (floor >= s_raw - 1e-9).all()
                                                              and np.allclose(floor, np.maximum(s_raw, trust_floor_factor(2) * s_ref))),
               lines_floor_above_raw={k: dict(raw=round(float(s_raw[k]), 1), floor=round(float(floor[k]), 1), s_ref=round(float(s_ref[k]), 1))
                                      for k in floor.index[floor > s_raw + 1e-6]},
               dissipation_room=dissipation_room(n, s_ref, cap, floor),
               representative_points=representative_point_checks(n, s_ref, cap.reindex(n.lines.index), floor)[0])
    rows['s_nom_lower']['lines_floor_above_raw'] = len(out['lines_floor_above_raw'])
    if fixed_nc is not None:
        out['fixed_point_vs_lp2'] = fixed_point_vs_lp2(n, s_ref, fixed_nc, v)
    return out, D


def static_v3_reference2(c, info, v):
    """a second, IT2-like reference: S_ref = the sealed NEXT-08b v2 LP1 solution (= the v2 candidate capacities, read only). Rows +
    fixed point vs the sealed v2 candidate NetCDF itself (an LP2 network of exactly that capacity and r), and the GW check: how much
    of the sealed v2 LP1 loss the v3 bound at those capacities would forbid"""
    sr = c['static_reference']
    cnd = ROOT / sr['candidate']
    assert A2G.file_shas(cnd)['raw'] == sr['candidate_sha256'], 'sealed v2 candidate SHA differs'
    sol = pd.read_csv(ROOT / sr['lp1_solution'], index_col=0)
    s_ref2 = sol.s_nom_opt
    n2, info2 = build_lp1_from(info['raw_nc'], info['s_prep'], s_ref2, c)
    res, _ = v3_model_checks(n2, info2, n2.lines.s_nom_max.copy(), v, fixed_nc=cnd)
    L = n2.lines
    r_pu = L.r / n2.buses.v_nom.reindex(L.bus0).values ** 2
    U = r_pu * (L.s_max_pu * s_ref2.reindex(L.index)) ** 2                 # v3 bound at s_nom = S_ref = the v2 solution
    ll = pd.read_csv(ROOT / sr['lp1_line_loss'], index_col=[0, 1])[L.index]
    w = float(n2.snapshot_weightings.generators.iloc[0])
    ex = (ll - U * (1 + 1e-6)).clip(lower=0)
    res['sealed_v2_lp1_loss_forbidden_by_v3'] = dict(MWh=float(ex.sum().sum() * w), cells=int((ex > 1e-3).sum().sum()),
                                                     max_step_MW=float(ex.sum(axis=1).max()),
                                                     top_lines_MWh={k: round(float(x), 1) for k, x in (ex.sum() * w).sort_values(ascending=False).head(8).items()})
    del n2
    return dict(reference2=res)


def v3_checks(s, v2_size):
    tol = 1e-9
    out = {}
    for key in ('it1', 'reference2'):
        r = s[key]['rows']
        fp = s[key]['fixed_point_vs_lp2']
        out[f'{key}_loss_upper_rows_affine_at_s_ref'] = r['loss_upper']['slope_max_abs_dev'] < 1e-12 and r['loss_upper']['offset_max_abs_dev'] < 1e-9 \
            and r['loss_upper']['sign'] == ['<='] and r['loss_upper']['other_terms'] == 0 and r['loss_upper']['loss_coef_unique'] == [1.0]
        out[f'{key}_tangent_rows_at_s_ref'] = all(d['offset_max_abs_dev'] < 1e-9 and d['slope_max_abs_dev'] < 1e-12 for d in r['loss_tangents'].values())
        out[f'{key}_s_nom_upper_is_cap'] = r['s_nom_upper']['rhs_max_abs_dev'] < 1e-9 and r['s_nom_upper']['sign'] == ['<=']
        out[f'{key}_s_nom_lower_is_floor'] = r['s_nom_lower']['rhs_max_abs_dev'] < 1e-9 and r['s_nom_lower']['sign'] == ['>='] \
            and s[key]['s_nom_min_equals_floor_and_floor_ge_raw']
        out[f'{key}_rating_rows_unchanged_form'] = all(x['other_terms'] == 0 and x['s_coef'] == [1.0] and x['s_nom_coef_max_abs_dev'] < 1e-12 and x['rhs_max_abs'] < 1e-12
                                                      for x in r['rating_rows'].values()) and r['rating_rows']['upper']['loss_coef'] == [1.0] \
            and r['rating_rows']['lower']['loss_coef'] == [-1.0]
        d = r['domain']
        out[f'{key}_no_hidden_flow_cap_on_floor_to_cap'] = d['min_margin_rel'] >= -tol
        out[f'{key}_bound_never_above_r_R2'] = d['max_U_minus_rR2_rel'] <= tol
        out[f'{key}_bound_nonnegative'] = d['min_U_rel'] >= -tol
        out[f'{key}_fixed_point_equals_r_Rref2'] = d['fixed_point_max_dev_rel'] <= tol
        out[f'{key}_fixed_point_equals_lp2_rows'] = fp['s_nom_dev'] < 1e-9 and fp['r_dev'] < 1e-12 and fp['loss_upper_rel_dev'] < 1e-9 \
            and all(fp[k] < 1e-9 for k in fp if k.startswith(('tangent_', 'rating_')))
        out[f'{key}_same_model_size_as_v2'] = (s[key]['n_vars'], s[key]['n_cons']) == tuple(v2_size)
        out[f'{key}_representative_points_ABCD'] = all(x == 0 for x in s[key]['representative_points']['failures'].values())
    out['v2_lp1_dissipation_forbidden_by_v3_GWh_ge_300'] = s['reference2']['sealed_v2_lp1_loss_forbidden_by_v3']['MWh'] >= 3e5
    return out


def build_lp1(stage, c):
    v, raw_nc, prep_nc = v16_files()
    import pypsa
    s_prep = pypsa.Network(str(prep_nc)).lines.s_nom
    if stage == 'LP1_LOSSY_IT1':
        s_ref = s_prep.copy()
    else:
        s_ref = pd.read_csv(out_dir(c) / 'LP1_LOSSY_IT1' / 'LP1_LINE_SOLUTION.csv', index_col=0).s_nom_opt
    n, info = build_lp1_from(raw_nc, s_prep, s_ref, c)
    return n, dict(info, raw_nc=raw_nc), v


def build_lp1_from(raw_nc, s_prep, s_ref, c):
    """the LP1 model from explicit inputs (used by build_lp1 and by the static tests on small networks)"""
    n, info = prepare_lp1(raw_nc, s_ref, float(c['cap_factor']), s_prep)
    tangent_ref = c.get('loss_tangent_reference', 'cap')          # v1 (NEXT-08): 'cap'; v2 (NEXT-08b): 's_ref'
    upper_mode = c.get('loss_upper', 'cap')                        # v1, v2: 'cap'; v3 (NEXT-08b loss-upper fix): 'affine_s_ref'
    if upper_mode not in ('cap', 'affine_s_ref') or (upper_mode == 'affine_s_ref' and tangent_ref != 's_ref'):
        raise ValueError(f'loss_upper {upper_mode!r} invalid (affine_s_ref requires loss_tangent_reference s_ref)')
    s_floor = None
    if tangent_ref == 's_ref':
        cap = n.lines.s_nom_max.copy()
        n.lines['s_nom_max'] = s_ref.reindex(n.lines.index)
        n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
        apply_reference_tangents(n, s_ref.reindex(n.lines.index), cap)
        if upper_mode == 'affine_s_ref':
            s_floor = apply_affine_loss_upper(n, s_ref.reindex(n.lines.index), info['s_raw'], int(c['transmission_losses']))
    elif tangent_ref == 'cap':
        n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
    else:
        raise ValueError(f'loss_tangent_reference {tangent_ref!r} not in (cap, s_ref)')
    return n, dict(info, s_ref=s_ref, s_prep=s_prep, tangent_reference=tangent_ref, loss_upper=upper_mode, s_floor=s_floor)


def build_lp2(stage, c):
    v, _, _ = v16_files()
    n, info = V16.prepare_fixed(v, out_dir(c) / CANDIDATE_NC)
    n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
    return n, info, None, v


# ------------------------------------------------------------------------------------------------ run
def run(stage, threads, cfg_path=CFG, gate_fn=None, lp1_build=None, lp2_build=None):
    c = load(cfg_path)
    g = (gate_fn or (lambda s_: check(s_, cfg_path)))(stage)
    if not g['approved']:
        print(json.dumps(dict(LOSSY_LP1_GATE='REFUSED', **g), indent=1)); raise SystemExit(3)
    if stage == 'LP2_LOSSY_CANDIDATE':
        # the W6 runner's run/postprocess with this chain's config, ledger and candidate network
        return LB.run(stage, threads, cfg_path=cfg_path, gate_fn=lambda s_: g, build_fn=lp2_build or build_lp2,
                      ledger_fn=lambda c_: ledger(c_), log_cols=LOG_COLS)
    n, info, v = (lp1_build or build_lp1)(stage, c)
    p, lg = ledger(c)
    aid = f'{stage}#1'
    row = {k: '' for k in LOG_COLS}; row.update(attempt_id=aid, stage=stage, state='STARTED', started_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    A2G._atomic_write(pd.concat([lg, pd.DataFrame([row])], ignore_index=True)[LOG_COLS], p)

    def finish(**kw):
        _, lg_ = ledger(c)
        i = lg_.index[lg_.attempt_id == aid][0]
        kw.setdefault('finished_utc', datetime.now(timezone.utc).isoformat(timespec='seconds'))
        for k, val in kw.items():
            lg_.loc[i, k] = str(val)
        A2G._atomic_write(lg_[LOG_COLS], p)
    opts = dict(v['solver_options'], Threads=int(threads))
    t = time.time()
    try:
        st, term = n.optimize.solve_model(solver_name=v['solver'], solver_options=opts)
    except BaseException as e:
        finish(state='ERROR', status='exception', seconds=round(time.time() - t, 1), note=f'{e.__class__.__name__}: {e}'[:300])
        raise
    sec = time.time() - t
    st, term = str(st), str(term)
    try:
        qa = postprocess_lp1(n, info, v, c, stage, st, term, sec, g, threads, out_dir(c) / stage)
        finish(state='DONE', status=st, termination=term, seconds=round(sec, 1), r_converged=qa['r_converged'], guards_pass=qa['guards']['all_pass'])
    except BaseException as e:
        finish(state='ERROR', status=st, termination=term, seconds=round(sec, 1), note=f'post-solve: {e.__class__.__name__}: {e}'[:300])
        raise
    if not (st == 'ok' and term == 'optimal'):
        raise SystemExit(f'{stage} {st} {term}: BLOCKED (outputs kept, no retry)')
    return qa


def postprocess_lp1(n, info, v, c, stage, st, term, sec, g, threads, od):
    ok = st == 'ok' and term == 'optimal'
    od.mkdir(parents=True, exist_ok=True)
    s_opt = n.lines.s_nom_opt.copy()
    bad = s_opt.index[~np.isfinite(s_opt) | (s_opt < info['s_raw'].reindex(s_opt.index) - 1e-6)] if ok else []
    if len(bad):                       # fail closed: never derive guards, r or a candidate from an invalid capacity solution
        raise ValueError(f'LP1 capacity solution invalid (non-finite or below raw s_nom) on {list(bad)[:5]}')
    sol = dict(s_nom_input=info['s_raw'], s_nom_opt=s_opt, s_ref=info['s_ref'], s_v16_prepared=info['s_prep'], s_nom_max=n.lines.s_nom_max,
               r_raw=info['r_raw'], r_used=n.lines.r)
    if info.get('s_floor') is not None:
        sol['s_floor'] = info['s_floor']
    pd.DataFrame(sol).to_csv(od / 'LP1_LINE_SOLUTION.csv')
    sh = n.generators_t.p[[f'{b} shed' for b in info['buses']]].copy(); sh.columns = info['buses']
    acc, ev = V16.shed_stats(sh, n.snapshot_weightings.generators, v, stage)
    loss = LB.line_loss_frame(n)
    w = n.snapshot_weightings.generators
    conv, cinfo = convergence(s_opt, info['s_ref'], info['s_raw'], float(c['r_tol']), float(c['s_tol_MVA']), s_floor=info.get('s_floor'))
    gd = guards(s_opt, info['s_raw'], info['s_prep'], n.lines.s_nom_max, c['guards'])
    up = (s_opt - info['s_raw']).clip(lower=0.0)
    qa = dict(stage=stage, status=st, termination=term, seconds=round(sec, 1), threads=int(threads), n_vars=int(n.model.nvars), n_cons=int(n.model.ncons),
              objective=float(n.objective) if ok else None, residual_shed=acc, r_converged=conv, convergence=cinfo, guards=gd,
              uplift_by_line_MVA={k: round(float(x), 2) for k, x in up[up > 0.5].sort_values(ascending=False).items()},
              total_loss_MWh=float(loss.mul(w.values, axis=0).sum().sum()) if loss is not None else None, gate=g,
              candidate_written=False, label='LOSSY LP1 CALIBRATION (2025 fixed fleet); not a scenario result')
    if ok and conv and gd['all_pass']:
        cand = candidate_network(info['raw_nc'], s_opt)
        cand.export_to_netcdf(str(out_dir(c) / CANDIDATE_NC))
        qa['candidate_written'] = True
        qa['candidate_sha256'] = A2G.file_shas(out_dir(c) / CANDIDATE_NC)['raw']
    (od / 'LOSSY_LP1_QA.json').write_text(json.dumps(qa, indent=1, default=str), encoding='utf-8')
    sh.to_csv(od / 'shed_by_bus.csv.gz'); ev.to_csv(od / 'shedding_events.csv', index=False)
    if loss is not None:
        loss.round(3).to_csv(od / 'line_loss.csv.gz')
    print(json.dumps({k: x for k, x in qa.items() if k != 'gate'}, indent=1, default=str))
    return qa


# ------------------------------------------------------------------------------------------------ static build
def build_only(threads, cfg_path=CFG):
    import linopy
    calls = []
    linopy.Model.solve = lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(RuntimeError('no solver in --build'))
    c = load(cfg_path)
    rep = dict(step='NEXT-08 lossy LP1 static build', config=str(cfg_path), tangent_reference=c.get('loss_tangent_reference', 'cap'),
               solver_calls=0, gate={s: check(s, cfg_path) for s in STAGES})
    n, info, v = build_lp1('LP1_LOSSY_IT1', c)
    m = n.model
    L = n.lines
    rep['LP1_LOSSY_IT1'] = dict(n_vars=int(m.nvars), n_cons=int(m.ncons), has_line_loss='Line-loss' in m.variables, has_line_s_nom='Line-s_nom' in m.variables,
                                loss_rows=sorted(k for k in m.constraints if k.startswith('Line-loss')), lines=int(len(L)),
                                all_lines_extendable=bool(L.s_nom_extendable.all()), s_nom_max_finite=bool(np.isfinite(L.s_nom_max).all()),
                                cap_over_v16_prepared=float((L.s_nom_max / info['s_prep'].reindex(L.index)).max()),
                                s_nom_min_equals_raw=bool(np.allclose(L.s_nom_min, info['s_raw'])), capital_cost_unique=sorted(set(L.capital_cost)),
                                x_equals_raw=None, r_scaled_lines=int((L.r < info['r_raw'] - 1e-12).sum()), r_sum_ohm=float(L.r.sum()),
                                generators=int(len(n.generators)), shed_units=int((n.generators.carrier == 'load_shed').sum()), storage_units=int(len(n.storage_units)),
                                snapshots=int(len(n.snapshots)), committable=int(n.generators.committable.sum()))
    import pypsa
    raw = pypsa.Network(str(info['raw_nc']))
    rep['LP1_LOSSY_IT1']['x_equals_raw'] = bool(np.array_equal(L.x.values, raw.lines.x.reindex(L.index).values))
    tref = info['s_ref'] if info.get('tangent_reference') == 's_ref' else L.s_nom_max
    dev = tangent_rows_vs_reference(n, tref.reindex(L.index))
    m_ = n.model
    cap_rhs = np.asarray(m_.constraints['Line-ext-s_nom-upper'].rhs.values, dtype=float)
    rep['LP1_LOSSY_IT1'].update(tangent_reference=info.get('tangent_reference'), tangent_rows_vs_reference=dev,
                                tangent_rows_match=all(d['offset_max_abs_dev'] < 1e-9 and d['slope_max_abs_dev'] < 1e-12 for d in dev.values()),
                                capacity_row_rhs_equals_cap=bool(np.allclose(cap_rhs, L.s_nom_max.reindex(list(m_.constraints['Line-ext-s_nom-upper'].rhs.coords['name'].values)).values)))
    v3 = info.get('loss_upper') == 'affine_s_ref'
    if v3:                                                             # IT1 rows + fixed point vs the fixed model of the v1.6 capacities
        sd = out_dir(c) / '_static'; sd.mkdir(parents=True, exist_ok=True)
        fx = sd / 'fixed_at_v16_capacities.nc'                         # scratch stand-in (r proxy at v1.6 s_nom), not a baseline
        candidate_network(info['raw_nc'], info['s_prep']).export_to_netcdf(str(fx))
        rep['v3_static'] = dict(it1=v3_model_checks(n, info, L.s_nom_max.copy(), v, fixed_nc=fx)[0])
    del n
    cand = candidate_network(info['raw_nc'], info['s_prep'])           # the v1.6 capacities as a stand-in LP1 solution (no file written)
    rep['candidate_from_v16_capacities'] = dict(r_sum_ohm=float(cand.lines.r.sum()), s_nom_sum=float(cand.lines.s_nom.sum()),
                                                x_equals_raw=bool(np.array_equal(cand.lines.x.values, raw.lines.x.values)))
    a = rep['LP1_LOSSY_IT1']
    if v3:
        rep['v3_static'].update(static_v3_reference2(c, info, v))
        v2b = json.loads((ROOT / c['static_reference']['v2_build_json']).read_text(encoding='utf-8'))['LP1_LOSSY_IT1']
        rep['v3_static']['checks'] = v3_checks(rep['v3_static'], (v2b['n_vars'], v2b['n_cons']))
        a['s_nom_min_equals_raw'] = rep['v3_static']['it1']['s_nom_min_equals_floor_and_floor_ge_raw']
    rep['checks'] = dict(loss_terms=a['has_line_loss'] and len(a['loss_rows']) == 5, capacity_variables=a['has_line_s_nom'],
                         finite_caps=a['s_nom_max_finite'], cap_factor_respected=abs(a['cap_over_v16_prepared'] - float(c['cap_factor'])) < 1e-9,
                         lp1_like_v16=a['all_lines_extendable'] and a['s_nom_min_equals_raw'] and a['capital_cost_unique'] == [UPLIFT_COST],
                         x_unchanged=a['x_equals_raw'], r_scaled_on_v16_uplifted_lines=a['r_scaled_lines'] == 18, no_committable=a['committable'] == 0,
                         tangent_rows_match_reference=a['tangent_rows_match'], capacity_row_is_guard_cap=a['capacity_row_rhs_equals_cap'],
                         no_solver_called=not calls)
    if v3:
        rep['checks'].update(rep['v3_static']['checks'])
    od = out_dir(c); od.mkdir(parents=True, exist_ok=True)
    (od / 'LOSSY_LP1_BUILD.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: x for k, x in rep.items() if k != 'gate'}, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true'); ap.add_argument('--stage', choices=STAGES)
    ap.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 20)))
    ap.add_argument('--config', default=str(CFG), help='gate config (default: the NEXT-08 v1 config; NEXT-08b: config.byop_lossy_lp1_v2.yaml)')
    a = ap.parse_args()
    cfgp = Path(a.config).resolve()
    if a.build:
        build_only(a.threads, cfgp)
    elif a.stage:
        run(a.stage, a.threads, cfg_path=cfgp)
    else:
        ap.error('--build or --stage')


if __name__ == '__main__':
    main()
