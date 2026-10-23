#!/usr/bin/env python3
"""NEXT-07 W1.3 solver-free proof that the reserve probe differs from the formal S0 ONLY in the RHS of PV16M-reserve_req.
Builds, in ONE process and in this order, three post-v1.6 S0 models (v1.6 baseline, 2026-2031, 26 sample weeks + B7 stress days):
    REF    the formal path (no diagnostic: 3,000 MW)
    PROBE  identical inputs, reserve RHS from the validated NEXT-07 probe config (0 MW)
    REF2   the formal path again (the probe must leave no state behind: REF2 == REF exactly)
and compares every variable (labels, bounds), every constraint (coordinates, variable labels, coefficients, sign, RHS), the objective
(variables, coefficients, constant) and the network inputs. NO SOLVER IS CALLED (linopy.Model.solve and gurobipy.Model.optimize raise).
Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n07_reserve_probe.py --out results/BYOP/next07_s0_reserve_probe/_static_w1
Writes W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json and W1_CONSTRAINT_DIFF.csv there and into current_work_pckg/BYOP_NEXT_07/.
"""
from __future__ import annotations

import argparse, gc, hashlib, json, resource, shutil, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, 'byop/model')
import linopy  # noqa: E402
import pypsa  # noqa: E402
import rearch_mech as R  # noqa: E402
import post_v16_mainline as PM  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402
import byop_paths as BP  # noqa: E402

M, w2, V, STATE = R.M, R.w2, R.V, R.STATE
SOLVER_CALLS = []
CFG_PATH = 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml'
PROBE_CFG = Path('config/config.byop_post_v16_n07_reserve_probe.yaml')
N06_CFG = Path('config/config.byop_post_v16_n06_diag.yaml')
PKG = Path('../current_work_pckg/BYOP_NEXT_07')
TOL = 1e-10
REQUIRED_ROWS = ['PV16M-online_cap_fixed', 'PV16M-online_cap_ext', 'PV16M-online_max_p', 'PV16M-online_min', 'PV16M-res_thermal_head',
                 'PV16M-res_ramp', 'PV16M-res_su_energy', 'PV16M-res_su_energy_start', 'PV16M-reserve_req']


class StopBeforeSolve(Exception):
    pass


def _no_solve(self, *a, **k):
    SOLVER_CALLS.append('refused')
    raise StopBeforeSolve()


linopy.Model.solve = _no_solve
try:
    import gurobipy
    gurobipy.Model.optimize = _no_solve
except Exception:
    pass


def setup(out):
    R.BASE_TAMU = BP.BASE_TAMU_V16
    siting = R.ml_select_siting(CFG_PATH)
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['NEXT07_W1_STATIC']))
    R.GCFG.update(setting='G-REAL', competing=0.0, regional_dc='off', case='base', gas_case='base', relax=[], s2_modes=R.MODES,
                  interrupt_cap=0.005, no_harm=True, base_assets='main', s0_calibrate=False, s0_cal_file=None)
    M.CFG.update(periods='annual', start=2026, end=2031, cost_basis='repaired', public_subsidy='without', tariff='energy', reuse='on',
                 reuse_case='base', frac_cod=True, flex=False, poi_lead=0, byop_case='base', public_case='base', byop_techs=list(R.ML_TECHS),
                 sample_weeks=26, bg_growth=0.0, line_exp=True, erm15=False, threads=4, v=2.8e6, v_private=None, smoke=False, dem_scale=1.0)
    M.CFG['tech_version'] = R.ml_tech_version(CFG_PATH)
    PM.POST_V16['on'] = True
    w2.POST_V16_NO_ERM['on'] = True
    R.configure_mainline(out)
    M.build = R.build_rearch; M.extra = R.extra_rearch
    w2.store_ERM_duals = V.store_erm_duals_tx; V.GCFG.update(erm_scope='tx')
    w2.PREP = str(R.BASE_TAMU); w2.PUE = pd.read_csv(w2.PUE_CSV)
    STATE['erm_cal'] = None
    return pypsa.Network(str(R.BASE_TAMU)).meta, siting


def build_s0(config, out, rhs):
    """one S0 build; rhs None = formal path. The value lives in STATE only for this build and is removed afterwards (finally)."""
    STATE['firm_strict'] = True; STATE['lex'] = None
    for k in ('v2_pool_candidates', 'byop_cod', 'pv16m_re_firm', 'pv16_reserve_rhs_MW', 'shed_S0'):
        STATE.pop(k, None)
    if rhs is not None:
        STATE['pv16_reserve_rhs_MW'] = rhs
    try:
        n, _ = M.build(config, 'S0', 2.8e6)
        try:
            M.solve(config, 'S0', out, n)
        except StopBeforeSolve:
            pass
        info = dict(STATE.get('pv16m_reserve') or {})
    finally:
        STATE.pop('pv16_reserve_rhs_MW', None)
    return n, info


def arr(x):
    return np.asarray(x.values if hasattr(x, 'values') else x)


def h(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()[:16]


def hc(coord):
    """hash of a coordinate's values (MultiIndex snapshot tuples included)"""
    return hashlib.sha256('|'.join(map(str, coord.to_index())).encode()).hexdigest()[:16]


def snapshot_model(n):
    """compact, comparable fingerprint of the linopy model (arrays per variable / constraint) + network inputs"""
    m = n.model
    V_, C_ = {}, {}
    for k in m.variables:
        v = m.variables[k]
        V_[k] = dict(dims=tuple(v.labels.dims), shape=tuple(v.labels.shape), labels=arr(v.labels), lower=arr(v.lower).astype(float), upper=arr(v.upper).astype(float),
                     coords={d: hc(v.labels.coords[d]) for d in v.labels.dims})
    for k in m.constraints:
        c = m.constraints[k]
        C_[k] = dict(dims=tuple(c.labels.dims), shape=tuple(c.labels.shape), labels=arr(c.labels), vars=arr(c.vars), coeffs=arr(c.coeffs).astype(float),
                     sign=arr(c.sign).astype(str), rhs=arr(c.rhs).astype(float),
                     coords={d: hc(c.labels.coords[d]) for d in c.labels.dims})
    o = m.objective
    e = getattr(o, 'expression', o)
    obj = dict(vars=arr(o.vars), coeffs=arr(o.coeffs).astype(float), const=float(np.asarray(getattr(e, 'const', 0.0)).sum()))
    nnz = int(sum(int((C_[k]['vars'] != -1).sum()) for k in C_))
    net = PM.public_inputs_fingerprint(n)
    net['snapshot_weightings'] = dict(sha256=hashlib.sha256(n.snapshot_weightings.to_csv().encode()).hexdigest())
    net['snapshots'] = dict(sha256=hashlib.sha256(pd.Series(range(len(n.snapshots)), index=n.snapshots).to_csv().encode()).hexdigest())
    wsum = {int(p): float(v) for p, v in n.snapshot_weightings.generators.groupby(level=0).sum().items()}
    return dict(V=V_, C=C_, obj=obj, nvars=int(m.nvars), ncons=int(m.ncons), nnz=nnz, net=net, wsum=wsum,
                stores_w=sorted(set(np.round(n.snapshot_weightings.stores.values, 6))))


def diff(a, b, la, lb):
    """every difference between two model fingerprints, one row each"""
    rows = []
    add = lambda kind, name, field, detail: rows.append(dict(pair=f'{la}_vs_{lb}', kind=kind, name=name, field=field, detail=str(detail)[:300]))
    for k in sorted(set(a['V']) ^ set(b['V'])):
        add('variable', k, 'presence', f"{la}={k in a['V']} {lb}={k in b['V']}")
    for k in sorted(set(a['V']) & set(b['V'])):
        x, y = a['V'][k], b['V'][k]
        if x['dims'] != y['dims'] or x['shape'] != y['shape'] or x['coords'] != y['coords']:
            add('variable', k, 'coords', (x['shape'], y['shape'])); continue
        if not np.array_equal(x['labels'], y['labels']):
            add('variable', k, 'labels', 'label arrays differ')
        for f in ('lower', 'upper'):
            if not np.allclose(x[f], y[f], rtol=0, atol=TOL, equal_nan=True):
                add('variable', k, f, float(np.nanmax(np.abs(x[f] - y[f]))))
    for k in sorted(set(a['C']) ^ set(b['C'])):
        add('constraint', k, 'presence', f"{la}={k in a['C']} {lb}={k in b['C']}")
    for k in sorted(set(a['C']) & set(b['C'])):
        x, y = a['C'][k], b['C'][k]
        if x['dims'] != y['dims'] or x['shape'] != y['shape'] or x['coords'] != y['coords']:
            add('constraint', k, 'coords', (x['shape'], y['shape'])); continue
        if not np.array_equal(x['labels'], y['labels']):
            add('constraint', k, 'labels', 'row label arrays differ')
        if x['vars'].shape != y['vars'].shape or not np.array_equal(x['vars'], y['vars']):
            add('constraint', k, 'vars', 'variable labels differ')
        elif not np.allclose(x['coeffs'], y['coeffs'], rtol=0, atol=TOL, equal_nan=True):
            add('constraint', k, 'coeffs', float(np.nanmax(np.abs(x['coeffs'] - y['coeffs']))))
        if not np.array_equal(x['sign'], y['sign']):
            add('constraint', k, 'sign', 'sign differs')
        if not np.allclose(x['rhs'], y['rhs'], rtol=0, atol=TOL, equal_nan=True):
            d = x['rhs'] - y['rhs']
            add('constraint', k, 'rhs', dict(rows=int(x['rhs'].size), rows_changed=int((np.abs(d) > TOL).sum()),
                                              a_values=sorted(set(np.round(x['rhs'].ravel(), 6)))[:4], b_values=sorted(set(np.round(y['rhs'].ravel(), 6)))[:4]))
    if a['obj']['vars'].shape != b['obj']['vars'].shape or not np.array_equal(a['obj']['vars'], b['obj']['vars']):
        add('objective', 'objective', 'vars', 'objective variables differ')
    elif not np.allclose(a['obj']['coeffs'], b['obj']['coeffs'], rtol=0, atol=TOL):
        add('objective', 'objective', 'coeffs', float(np.abs(a['obj']['coeffs'] - b['obj']['coeffs']).max()))
    if abs(a['obj']['const'] - b['obj']['const']) > TOL:
        add('objective', 'objective', 'const', (a['obj']['const'], b['obj']['const']))
    for k in sorted(set(a['net']) | set(b['net'])):
        if a['net'].get(k, {}).get('sha256') != b['net'].get(k, {}).get('sha256'):
            add('network_input', k, 'sha256', (a['net'].get(k, {}).get('sha256'), b['net'].get(k, {}).get('sha256')))
    for f in ('nvars', 'ncons', 'nnz', 'wsum', 'stores_w'):
        if a[f] != b[f]:
            add('model_size', f, 'value', (a[f], b[f]))
    return rows


def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 ** 2


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    config, siting = setup(out)
    pc = A2G.load(PROBE_CFG)
    rhs_probe = PM.diagnostic_reserve_rhs(pc, PROBE_CFG)
    pre = dict(probe_config_rhs=rhs_probe, n06_fullyear_config_rhs=PM.diagnostic_reserve_rhs(A2G.load(N06_CFG), N06_CFG),
               formal_a2_config_rhs=PM.diagnostic_reserve_rhs(A2G.load(), A2G.CFG), POST_V16_reserve_MW_before=PM.POST_V16['reserve_MW'])
    fp, infos, times, mem = {}, {}, {}, {}
    for lab, rhs in (('REF', None), ('PROBE', rhs_probe), ('REF2', None)):
        t = time.time()
        n, infos[lab] = build_s0(config, out, rhs)
        fp[lab] = snapshot_model(n)
        times[lab] = round(time.time() - t, 1); mem[lab] = round(rss_gb(), 2)
        req = n.model.constraints['PV16M-reserve_req']
        print(f"{lab}: built in {times[lab]} s, nvars {fp[lab]['nvars']}, ncons {fp[lab]['ncons']}, nnz {fp[lab]['nnz']}, "
              f"reserve_req RHS {sorted(set(np.round(arr(req.rhs).ravel(), 6)))}, peak RSS {mem[lab]} GB", flush=True)
        del n; gc.collect()
    d_rp = diff(fp['REF'], fp['PROBE'], 'REF', 'PROBE')
    d_rr = diff(fp['REF'], fp['REF2'], 'REF', 'REF2')
    rows = d_rp + d_rr
    exp = [r for r in d_rp if r['kind'] == 'constraint' and r['name'] == 'PV16M-reserve_req' and r['field'] == 'rhs']
    other = [r for r in d_rp if r not in exp]
    rq = {lab: sorted(set(np.round(fp[lab]['C']['PV16M-reserve_req']['rhs'].ravel(), 6))) for lab in fp}
    present = {lab: {k: k in fp[lab]['C'] for k in REQUIRED_ROWS} | {'A2F08-seg_soc_*': sum(k.startswith('A2F08-seg_soc_') for k in fp[lab]['C'])} for lab in fp}
    nsnap = fp['REF']['C']['PV16M-reserve_req']['rhs'].size
    checks = dict(
        exactly_one_constraint_rhs_changed=len(exp) == 1 and not other,
        reserve_req_rows_all_changed_3000_to_0=bool(exp) and rq['REF'] == [3000.0] and rq['PROBE'] == [0.0] and
        int(np.sum(np.abs(fp['REF']['C']['PV16M-reserve_req']['rhs'] - fp['PROBE']['C']['PV16M-reserve_req']['rhs']) > TOL)) == nsnap,
        reserve_req_coeffs_sign_coords_identical=not [r for r in d_rp if r['name'] == 'PV16M-reserve_req' and r['field'] != 'rhs'],
        required_reserve_rows_present_in_both=all(all(v for k, v in present[l].items() if k != 'A2F08-seg_soc_*') and present[l]['A2F08-seg_soc_*'] > 0
                                                  for l in ('REF', 'PROBE')) and present['REF'] == present['PROBE'],
        ref2_identical_to_ref=not d_rr, default_rhs_restored_ref2=rq['REF2'] == [3000.0],
        post_v16_reserve_MW_unchanged=PM.POST_V16['reserve_MW'] == 3000.0,
        n06_fullyear_and_formal_a2_configs_have_no_diagnostic=pre['n06_fullyear_config_rhs'] is None and pre['formal_a2_config_rhs'] is None,
        probe_config_rhs_is_0=rhs_probe == 0.0, no_solver_called=all(c == 'refused' for c in SOLVER_CALLS) and len(SOLVER_CALLS) == 3)
    verdict = 'W1_STATIC_PASS' if all(checks.values()) else 'BUILD_COMPARABILITY_FAIL'
    rep = dict(work_package='BYOP_NEXT_07', step='W1.3', verdict=verdict, W2_RHS_CHANGED_ONLY='YES' if checks['exactly_one_constraint_rhs_changed'] else 'NO',
               solver_executions=0, solver_calls_intercepted=len(SOLVER_CALLS), checks=checks, pre=pre, reserve_req_rhs_values=rq,
               reserve_req_rows=nsnap, required_rows_present=present, reserve_info={k: {x: y for x, y in v.items() if x != 'soc_interval_start'} for k, v in infos.items()},
               model_size={lab: dict(nvars=fp[lab]['nvars'], ncons=fp[lab]['ncons'], nnz=fp[lab]['nnz'], variables=len(fp[lab]['V']), constraints=len(fp[lab]['C']))
                           for lab in fp},
               snapshot_weight_sum_h=fp['REF']['wsum'], stores_weight_h=fp['REF']['stores_w'], differences_REF_vs_PROBE=len(d_rp), differences_REF_vs_REF2=len(d_rr),
               unexpected_differences=other[:20], build_seconds=times, peak_rss_GB_after_build=mem, siting=siting['variant'], tech_version=M.CFG['tech_version'],
               base_sha256=M.sha(R.BASE_TAMU), tolerance=TOL, seconds=round(time.time() - t0, 1),
               method='labels / bounds / coefficients / RHS compared array-wise per variable and constraint name (label arrays identical => canonical alignment); '
                      'network inputs by per-component SHA (public_inputs_fingerprint) + snapshot index / weightings')
    pd.DataFrame(rows, columns=['pair', 'kind', 'name', 'field', 'detail']).to_csv(out / 'W1_CONSTRAINT_DIFF.csv', index=False)
    (out / 'W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    PKG.mkdir(parents=True, exist_ok=True)
    for f in ('W1_CONSTRAINT_DIFF.csv', 'W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json'):
        shutil.copyfile(out / f, PKG / f)
    print(json.dumps({k: v for k, v in rep.items() if k not in ('required_rows_present',)}, indent=1, default=str))


if __name__ == '__main__':
    main()
