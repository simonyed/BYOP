#!/usr/bin/env python3
"""NEXT-07 W5 solver-free proof that the lossless probe differs from the formal S0 ONLY by the transmission-loss terms.
Builds, in ONE process and in this order, three post-v1.6 S0 models (v1.6 baseline, 2026-2031, 26 sample weeks + B7 stress days):
    REF    the formal path (baseline meta: transmission_losses = 2)
    PROBE  identical, solve config from rearch_mech.pv16_solve_config with the validated probe value (transmission_losses = 0)
    REF2   the formal path again (the probe leaves no state behind: REF2 == REF exactly)
Removing the Line-loss variable shifts every later variable label, so variables are compared by canonical key (name, flat position):
  * variables: PROBE = REF minus {Line-loss}; every other variable identical (coords, bounds)
  * constraints: PROBE = REF minus {Line-loss_upper, Line-loss_tangents-*}; every other row identical (coords, sign, RHS, and the
    canonical (variable, coefficient) terms once the Line-loss terms are dropped from REF); the rows that held loss terms are listed
  * objective identical (canonical); 3,000 MW reserve row identical; network inputs identical
NO SOLVER IS CALLED. Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n07_lossless_probe.py --out results/BYOP/next07_s0_lossless_probe/_static
Writes W5P_MODEL_EQUALS_EXCEPT_LOSSES.json and W5P_CONSTRAINT_DIFF.csv there and into current_work_pckg/BYOP_NEXT_07/."""
from __future__ import annotations

import argparse, gc, json, shutil, time
from pathlib import Path

import numpy as np
import pandas as pd

import structural_n07_reserve_probe as S      # solver interception + post-v1.6 setup

R, M, STATE, PM, A2G = S.R, S.M, S.STATE, S.PM, S.A2G
LOSSLESS_CFG = Path('config/config.byop_post_v16_n07_lossless_probe.yaml')
LOSS_VAR = 'Line-loss'
SENT = np.iinfo(np.int64).max
TOL = 1e-10


def build(config, out, losses):
    STATE['firm_strict'] = True; STATE['lex'] = None
    for k in ('v2_pool_candidates', 'byop_cod', 'pv16m_re_firm', 'pv16_reserve_rhs_MW', 'pv16_transmission_losses', 'shed_S0'):
        STATE.pop(k, None)
    st = {} if losses is None else {'pv16_transmission_losses': losses}
    n, _ = M.build(config, 'S0', 2.8e6)
    try:
        M.solve(R.pv16_solve_config(config, st), 'S0', out, n)
    except S.StopBeforeSolve:
        pass
    return n


def name_id(k):
    """stable id of a variable NAME (independent of which other variables exist in the model)"""
    return int.from_bytes(S.hashlib.sha256(k.encode()).digest()[:2], 'big')     # 16 bits; collisions checked in keymap


def keymap(m):
    """label -> canonical int64 key (name id << 40 | flat position); returns (key array, names)"""
    names = sorted(m.variables)
    ids = [name_id(k) for k in names]
    assert len(set(ids)) == len(ids), 'variable-name id collision'
    top = max(int(np.asarray(m.variables[k].labels.values).max()) for k in names) + 1
    key = np.full(top + 1, SENT, dtype=np.int64)
    for i, k in zip(ids, names):
        lab = np.asarray(m.variables[k].labels.values).ravel()
        ok = lab >= 0
        key[lab[ok]] = (np.int64(i) << 40) + np.arange(lab.size, dtype=np.int64)[ok]
    return key, names


def canon_terms(vars_, coeffs, key, drop_ids=()):
    """rows x terms -> sorted canonical keys and matching coefficients, with dropped variables removed"""
    v = np.asarray(vars_); c = np.asarray(coeffs, dtype=float)
    nt = v.shape[-1] if v.ndim else 1
    v = v.reshape(-1, nt); c = c.reshape(-1, nt)
    k = np.where(v >= 0, key[np.clip(v, 0, None)], SENT)
    for d in drop_ids:
        hit = (k != SENT) & ((k >> 40) == d)
        k = np.where(hit, SENT, k); c = np.where(hit, 0.0, c)
    c = np.where(k == SENT, 0.0, c)
    o = np.argsort(k, axis=1, kind='stable')
    k = np.take_along_axis(k, o, 1); c = np.take_along_axis(c, o, 1)
    w = int((k != SENT).sum(axis=1).max()) if k.size else 0
    return k[:, :w], c[:, :w]


def fingerprint(n):
    m = n.model
    key, names = keymap(m)
    V = {k: dict(shape=tuple(m.variables[k].labels.shape), coords={d: S.hc(m.variables[k].labels.coords[d]) for d in m.variables[k].labels.dims},
                 lower=np.asarray(m.variables[k].lower.values, dtype=float), upper=np.asarray(m.variables[k].upper.values, dtype=float)) for k in names}
    loss_id = name_id(LOSS_VAR) if LOSS_VAR in names else None
    C = {}
    for k in m.constraints:
        c = m.constraints[k]
        kk, cc = canon_terms(c.vars.values, c.coeffs.values, key, [loss_id] if loss_id is not None else [])
        had_loss = False
        if loss_id is not None:
            raw = np.asarray(c.vars.values); raw = raw[raw >= 0]
            had_loss = bool(((key[raw] >> 40) == loss_id).any()) if raw.size else False
        C[k] = dict(shape=tuple(c.labels.shape), coords={d: S.hc(c.labels.coords[d]) for d in c.labels.dims}, sign=np.asarray(c.sign.values).astype(str),
                    rhs=np.asarray(c.rhs.values, dtype=float), keys=kk, coeffs=cc, had_loss_terms=had_loss)
    o = m.objective
    ok, oc = canon_terms(np.asarray(o.vars.values)[None, :], np.asarray(o.coeffs.values)[None, :], key, [loss_id] if loss_id is not None else [])
    net = PM.public_inputs_fingerprint(n)
    net['snapshot_weightings'] = dict(sha256=S.hashlib.sha256(n.snapshot_weightings.to_csv().encode()).hexdigest())
    return dict(V=V, C=C, obj=(ok, oc), net=net, nvars=int(m.nvars), ncons=int(m.ncons), names=names,
                nnz=int(sum(int((np.asarray(m.constraints[k].vars.values) != -1).sum()) for k in m.constraints)))


def compare(a, b, la, lb, drop_vars=(), drop_cons_prefix=()):
    rows = []
    add = lambda kind, name, field, detail='': rows.append(dict(pair=f'{la}_vs_{lb}', kind=kind, name=name, field=field, detail=str(detail)[:300]))
    for k in sorted(set(a['V']) ^ set(b['V'])):
        add('variable', k, 'presence', f"{la}={k in a['V']} {lb}={k in b['V']}" + (' (expected)' if k in drop_vars else ''))
    for k in sorted(set(a['V']) & set(b['V'])):
        x, y = a['V'][k], b['V'][k]
        if x['shape'] != y['shape'] or x['coords'] != y['coords']:
            add('variable', k, 'coords'); continue
        for f in ('lower', 'upper'):
            if not np.allclose(x[f], y[f], rtol=0, atol=TOL, equal_nan=True):
                add('variable', k, f)
    for k in sorted(set(a['C']) ^ set(b['C'])):
        exp = any(k.startswith(p) for p in drop_cons_prefix)
        add('constraint', k, 'presence', f"{la}={k in a['C']} {lb}={k in b['C']}" + (' (expected)' if exp else ''))
    for k in sorted(set(a['C']) & set(b['C'])):
        x, y = a['C'][k], b['C'][k]
        if x['shape'] != y['shape'] or x['coords'] != y['coords']:
            add('constraint', k, 'coords'); continue
        if not np.array_equal(x['sign'], y['sign']):
            add('constraint', k, 'sign')
        if not np.allclose(x['rhs'], y['rhs'], rtol=0, atol=TOL, equal_nan=True):
            add('constraint', k, 'rhs')
        if x['keys'].shape != y['keys'].shape or not np.array_equal(x['keys'], y['keys']):
            add('constraint', k, 'terms', (x['keys'].shape, y['keys'].shape))
        elif not np.allclose(x['coeffs'], y['coeffs'], rtol=0, atol=TOL):
            add('constraint', k, 'coeffs', float(np.abs(x['coeffs'] - y['coeffs']).max()))
    (ka, ca), (kb, cb) = a['obj'], b['obj']
    if ka.shape != kb.shape or not np.array_equal(ka, kb) or not np.allclose(ca, cb, rtol=0, atol=TOL):
        add('objective', 'objective', 'terms')
    for k in sorted(set(a['net']) | set(b['net'])):
        if a['net'].get(k, {}).get('sha256') != b['net'].get(k, {}).get('sha256'):
            add('network_input', k, 'sha256')
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    config, siting = S.setup(out)
    lc = A2G.load(LOSSLESS_CFG)
    tl = PM.diagnostic_transmission_losses(lc, LOSSLESS_CFG)
    pre = dict(probe_transmission_losses=tl, probe_reserve_rhs=PM.diagnostic_reserve_rhs(lc, LOSSLESS_CFG),
               baseline_meta_transmission_losses=config['solving']['options'].get('transmission_losses'),
               baseline_meta_linearized_unit_commitment=config['solving']['options'].get('linearized_unit_commitment'),
               formal_a2=PM.diagnostic_spec(A2G.load(), A2G.CFG), n06=PM.diagnostic_spec(A2G.load(S.N06_CFG), S.N06_CFG))
    fp, sizes = {}, {}
    for lab, losses in (('REF', None), ('PROBE', tl), ('REF2', None)):
        t = time.time()
        n = build(config, out, losses)
        fp[lab] = fingerprint(n)
        req = n.model.constraints['PV16M-reserve_req']
        sizes[lab] = dict(nvars=fp[lab]['nvars'], ncons=fp[lab]['ncons'], nnz=fp[lab]['nnz'], has_line_loss=LOSS_VAR in fp[lab]['names'],
                          reserve_rhs=sorted(set(np.round(np.asarray(req.rhs.values).ravel(), 6))), seconds=round(time.time() - t, 1),
                          peak_rss_GB=round(S.rss_gb(), 2))
        print(lab, sizes[lab], flush=True)
        del n; gc.collect()
    cons_loss = ('Line-loss',)
    d_rp = compare(fp['REF'], fp['PROBE'], 'REF', 'PROBE', drop_vars=(LOSS_VAR,), drop_cons_prefix=cons_loss)
    d_rr = compare(fp['REF'], fp['REF2'], 'REF', 'REF2')
    unexpected = [r for r in d_rp if not r['detail'].endswith('(expected)')]
    had = sorted(k for k, v in fp['REF']['C'].items() if v['had_loss_terms'] and k in fp['PROBE']['C'])
    removed_c = sorted(set(fp['REF']['C']) - set(fp['PROBE']['C']))
    checks = dict(
        probe_value_is_0=tl == 0, formal_configs_have_no_diagnostic=pre['formal_a2'] is None and pre['n06'] is None,
        baseline_meta_losses_is_2=pre['baseline_meta_transmission_losses'] == 2,
        ref_has_line_loss=sizes['REF']['has_line_loss'], probe_has_no_line_loss=not sizes['PROBE']['has_line_loss'],
        only_line_loss_variable_removed=sorted(set(fp['REF']['V']) - set(fp['PROBE']['V'])) == [LOSS_VAR] and not (set(fp['PROBE']['V']) - set(fp['REF']['V'])),
        only_line_loss_constraints_removed=bool(removed_c) and all(k.startswith('Line-loss') for k in removed_c) and not (set(fp['PROBE']['C']) - set(fp['REF']['C'])),
        every_other_row_identical_after_dropping_loss_terms=not unexpected,
        reserve_row_3000_in_both=sizes['REF']['reserve_rhs'] == [3000.0] and sizes['PROBE']['reserve_rhs'] == [3000.0],
        ref2_identical_to_ref=not d_rr, no_solver_called=all(c == 'refused' for c in S.SOLVER_CALLS) and len(S.SOLVER_CALLS) == 3)
    verdict = 'W5P_STATIC_PASS' if all(checks.values()) else 'BUILD_COMPARABILITY_FAIL'
    rep = dict(work_package='BYOP_NEXT_07', step='W5 lossless probe static proof', verdict=verdict, solver_executions=0,
               solver_calls_intercepted=len(S.SOLVER_CALLS), checks=checks, pre=pre, sizes=sizes, removed_constraints=removed_c,
               rows_that_held_loss_terms_and_are_otherwise_identical=had, unexpected_differences=unexpected[:20],
               differences_REF_vs_REF2=len(d_rr), tolerance=TOL, seconds=round(time.time() - t0, 1),
               method='variables / rows compared by canonical key (variable name, flat position) because removing Line-loss shifts labels; '
                      'REF rows compared after dropping their Line-loss terms; network inputs by per-component SHA')
    pd.DataFrame(d_rp + d_rr, columns=['pair', 'kind', 'name', 'field', 'detail']).to_csv(out / 'W5P_CONSTRAINT_DIFF.csv', index=False)
    (out / 'W5P_MODEL_EQUALS_EXCEPT_LOSSES.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    S.PKG.mkdir(parents=True, exist_ok=True)
    for f in ('W5P_CONSTRAINT_DIFF.csv', 'W5P_MODEL_EQUALS_EXCEPT_LOSSES.json'):
        shutil.copyfile(out / f, S.PKG / f)
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
