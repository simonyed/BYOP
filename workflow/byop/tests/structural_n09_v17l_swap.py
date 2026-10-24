#!/usr/bin/env python3
"""NEXT-09 solver-free proof that moving the post-v1.6 S0 from the v1.6 baseline to the frozen v1.7L lossy baseline changes the
model ONLY through the 2025 network lines whose s_nom / r differ (BASELINE_V17L_RECORD.json, LINE_DIFF_VS_V16.csv).
Builds, in ONE process and in this order, three formal S0 models (2026-2031, 26 sample weeks + B7 stress days, transmission_losses 2
from the baseline meta):
    V16    on results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc
    V17L   on results/BYOP/baseline_2025_tamu_v17_lossy/baseline_2025_tamu_v17_lossy_prepared.nc
    V16B   on v1.6 again (the swap leaves no state behind: V16B == V16 exactly)
and compares every variable, constraint (coordinates, labels, coefficients, sign, RHS), the objective and the public network inputs
(structural_n07_reserve_probe.snapshot_model / diff). Admissible V16 -> V17L differences: Line-* rows (rating, loss tangents, loss
upper) on the changed lines only; the `lines` network-input fingerprint; and the LINE-01 corridor-expansion bound derived from the
base rating (rearch_mech.add_line_expansion_tamu: cap = s_nom x s_max_pu of the 2025 line) - M2-line_cap_L<line> RHS, the
p_nom_max of the L<line>_exp* links (Link-ext-p_nom-upper) and the `links` fingerprint - each on the changed lines only and equal
to the v1.7L rating exactly. Anything else is listed as UNEXPECTED (verdict REVIEW).
NO SOLVER IS CALLED (linopy.Model.solve and gurobipy.Model.optimize raise). Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n09_v17l_swap.py --out results/BYOP/post_v17l_s0s1/_static_swap
Writes V17L_SWAP_MODEL_DIFF.json and V17L_SWAP_CONSTRAINT_DIFF.csv there and into current_work_pckg/BYOP_NEXT_09_V17L_BASELINE_ADOPTION/.
"""
from __future__ import annotations

import argparse, gc, json, shutil, time
from pathlib import Path

import numpy as np
import pandas as pd

import structural_n07_reserve_probe as S      # solver interception + post-v1.6 snapshot / diff helpers

R, M, STATE, PM, w2, BP = S.R, S.M, S.STATE, S.PM, S.w2, S.BP
import baseline_registry as BR  # noqa: E402
CFG16 = 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml'
CFG17 = 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v17l.yaml'
PKG = Path('../current_work_pckg/BYOP_NEXT_09_V17L_BASELINE_ADOPTION')
TOL = 1e-10


def setup(base, cfg, out):
    """S.setup with the baseline and the mainline config of one variant (configure_mainline re-reads BASE_TAMU)"""
    S.CFG_PATH = cfg
    R.BASE_TAMU = Path(base)
    siting = R.ml_select_siting(cfg)
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['NEXT09_STATIC']))
    R.GCFG.update(setting='G-REAL', competing=0.0, regional_dc='off', case='base', gas_case='base', relax=[], s2_modes=R.MODES,
                  interrupt_cap=0.005, no_harm=True, base_assets='main', s0_calibrate=False, s0_cal_file=None)
    M.CFG.update(periods='annual', start=2026, end=2031, cost_basis='repaired', public_subsidy='without', tariff='energy', reuse='on',
                 reuse_case='base', frac_cod=True, flex=False, poi_lead=0, byop_case='base', public_case='base', byop_techs=list(R.ML_TECHS),
                 sample_weeks=26, bg_growth=0.0, line_exp=True, erm15=False, threads=4, v=2.8e6, v_private=None, smoke=False, dem_scale=1.0)
    M.CFG['tech_version'] = R.ml_tech_version(cfg)
    PM.POST_V16['on'] = True
    w2.POST_V16_NO_ERM['on'] = True
    R.configure_mainline(out)
    M.build = R.build_rearch; M.extra = R.extra_rearch
    w2.store_ERM_duals = S.V.store_erm_duals_tx; S.V.GCFG.update(erm_scope='tx')
    w2.PREP = str(R.BASE_TAMU); w2.PUE = pd.read_csv(w2.PUE_CSV)
    STATE['erm_cal'] = None
    import pypsa
    return pypsa.Network(str(R.BASE_TAMU)).meta, siting


def line_detail(n):
    """per-line view of every Line-* constraint: {row family: {line: (rhs bytes, coeff bytes)}}"""
    out = {}
    for k in n.model.constraints:
        if not k.startswith('Line-'):
            continue
        c = n.model.constraints[k]
        if 'name' not in c.labels.dims:
            continue
        nm = list(c.labels.coords['name'].values)
        rhs = np.asarray(c.rhs.transpose('name', ...).values, dtype=float).reshape(len(nm), -1)
        co = np.asarray(c.coeffs.transpose('name', ...).values, dtype=float).reshape(len(nm), -1)
        out[k] = {x: (rhs[i], co[i]) for i, x in enumerate(nm)}
    return out


def corridor_detail(n):
    """LINE-01 derived bounds: {corridor: cap rhs} and {expansion link: p_nom upper}, plus the base line ratings"""
    m = n.model
    caps = {k[len('M2-line_cap_'):]: float(np.asarray(m.constraints[k].rhs.values).ravel()[0]) for k in m.constraints if k.startswith('M2-line_cap_')}
    up = {}
    if 'Link-ext-p_nom-upper' in m.constraints:
        c = m.constraints['Link-ext-p_nom-upper']
        nm = [str(x) for x in c.labels.coords[c.labels.dims[0]].values]
        up = dict(zip(nm, np.asarray(c.rhs.values, dtype=float).ravel()))
    rating = (n.lines.s_nom * n.lines.s_max_pu).to_dict()
    return dict(caps=caps, up=up, rating=rating)


def corridor_changes(a, b, changed):
    """(rows, ok): every derived bound that moved; ok = only on changed lines and equal to the v1.7L rating"""
    rows, ok = [], True
    for k in sorted(set(a['caps']) | set(b['caps'])):
        u, v = a['caps'].get(k), b['caps'].get(k)
        if u is None or v is None or abs(u - v) > TOL:
            line = k[1:]
            good = line in changed and v is not None and abs(v - b['rating'][line]) <= 1e-6
            ok &= good
            rows.append(dict(family='M2-line_cap', line=line, field='rhs', v16=u, v17l=v, v17l_rating=b['rating'].get(line), ok=good))
    for k in sorted(set(a['up']) | set(b['up'])):
        u, v = a['up'].get(k), b['up'].get(k)
        if u is None or v is None or abs(u - v) > TOL:
            line = k[1:].split('_exp')[0]
            good = line in changed and v is not None and abs(v - b['rating'][line]) <= 1e-6
            ok &= good
            rows.append(dict(family='Link-ext-p_nom-upper', line=line, field=k, v16=u, v17l=v, v17l_rating=b['rating'].get(line), ok=good))
    return rows, ok


def line_changes(a, b):
    rows = []
    for k in sorted(set(a) | set(b)):
        if k not in a or k not in b:
            rows.append(dict(family=k, line='*', field='presence')); continue
        for x in sorted(set(a[k]) | set(b[k])):
            if x not in a[k] or x not in b[k]:
                rows.append(dict(family=k, line=x, field='presence')); continue
            for f, i in (('rhs', 0), ('coeffs', 1)):
                u, v = a[k][x][i], b[k][x][i]
                if u.shape != v.shape or not np.allclose(u, v, rtol=0, atol=TOL, equal_nan=True):
                    rows.append(dict(family=k, line=x, field=f, max_abs=float(np.nanmax(np.abs(u - v))) if u.shape == v.shape else None))
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rec = json.loads((BR.BASE_TAMU_V17L_DIR / 'BASELINE_V17L_RECORD.json').read_text(encoding='utf-8'))
    changed = set(pd.read_csv(BR.BASE_TAMU_V17L_DIR / 'LINE_DIFF_VS_V16.csv', index_col=0).index)
    fp, det, cor, metas, times = {}, {}, {}, {}, {}
    for lab, base, cfg in (('V16', BP.BASE_TAMU_V16, CFG16), ('V17L', BR.BASE_TAMU_V17L, CFG17), ('V16B', BP.BASE_TAMU_V16, CFG16)):
        t = time.time()
        config, _ = setup(base, cfg, out)
        metas[lab] = config.get('solving', {}).get('options', {}).get('transmission_losses')
        n, _ = S.build_s0(config, out, None)
        fp[lab] = S.snapshot_model(n)
        det[lab] = line_detail(n)
        cor[lab] = corridor_detail(n)
        times[lab] = round(time.time() - t, 1)
        del n; gc.collect()
    d_swap = S.diff(fp['V16'], fp['V17L'], 'V16', 'V17L')
    d_back = S.diff(fp['V16'], fp['V16B'], 'V16', 'V16B')
    lc = line_changes(det['V16'], det['V17L'])
    admissible = lambda r: (r['kind'] == 'constraint' and r['name'].startswith('Line-') and r['field'] in ('rhs', 'coeffs')) or \
        (r['kind'] == 'network_input' and r['name'] == 'lines')
    unexpected = [r for r in d_swap if not admissible(r)]
    lines_hit = sorted({r['line'] for r in lc})
    checks = dict(
        no_solver_called=len(S.SOLVER_CALLS) >= 3 and set(S.SOLVER_CALLS) == {'refused'},
        loss_basis_2_in_both=metas['V16'] == 2 and metas['V17L'] == 2,
        swap_leaves_no_state=not d_back,
        only_line_rows_and_line_inputs_differ=not unexpected,
        changed_rows_only_on_changed_lines=set(lines_hit) <= changed,
        corridor_bounds_only_on_changed_lines_and_equal_new_rating=cor_ok and bool(cc),
        every_changed_line_reaches_the_model=changed <= set(lines_hit),
        same_model_size=all(fp['V16'][k] == fp['V17L'][k] for k in ('nvars', 'ncons', 'nnz')),
        objective_identical=not any(r['kind'] == 'objective' for r in d_swap))
    res = dict(step='NEXT-09 v1.6 -> v1.7L baseline swap, S0 build (no solver)', baseline_v17l_sha256=rec['sha256'],
               models={k: dict(nvars=v['nvars'], ncons=v['ncons'], nnz=v['nnz']) for k, v in fp.items()}, seconds=times,
               transmission_losses_from_meta=metas, swap_diff=d_swap, rebuild_diff=d_back, unexpected=unexpected,
               line_rows_changed=len(lc), corridor_bounds_changed=cc, lines_hit=lines_hit, lines_changed_in_record=sorted(changed),
               families_hit=sorted({r['family'] for r in lc}), checks=checks, solver_calls=S.SOLVER_CALLS, wall_s=round(time.time() - t0, 1))
    res['verdict'] = 'SWAP_PASS' if all(checks.values()) else 'SWAP_REVIEW'
    (out / 'V17L_SWAP_MODEL_DIFF.json').write_text(json.dumps(res, indent=1, default=str), encoding='utf-8')
    pd.DataFrame(lc).to_csv(out / 'V17L_SWAP_CONSTRAINT_DIFF.csv', index=False)
    if PKG.exists():
        for f in ('V17L_SWAP_MODEL_DIFF.json', 'V17L_SWAP_CONSTRAINT_DIFF.csv'):
            shutil.copyfile(out / f, PKG / f)
    print(json.dumps(dict(verdict=res['verdict'], checks=checks, unexpected=unexpected[:20], families=res['families_hit'],
                          lines_hit=len(lines_hit), models=res['models']), indent=1, default=str))


if __name__ == '__main__':
    main()
