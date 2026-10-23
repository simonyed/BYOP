#!/usr/bin/env python3
"""NEXT-07 W4 end-to-end A3 dry run with ZERO optimizer executions: the real models of every A3 stage are built through the real
A3 solve wrapper, linopy lock and lex_presolve instrumentation; the gate is injected as approved and the ledgers live in a scratch
directory, so nothing touches the A3 pilot ledgers or budget. linopy.Model.solve and gurobipy.Model.optimize raise before any
solver is reached, so every stage ends ERROR with a STARTED -> ERROR child row of the planned kind (evidence kept, no retry).
Checks: kinds S0_COST, S1_SPEED_HIERARCHY, S3_COST, S2_DEV_LEX, S2_PUBLIC, S3_MS2_COST in that order; the conservative firm rule
(A2-F_cert upper bound 0) in the S3, S2 developer, S2 public and S3_mS2 models; no RE+BESS firm rows in S0 / S1; 0 solver runs.
Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n07_a3_e2e.py --out results/BYOP/next07_s0_reserve_probe/_a3_e2e
"""
from __future__ import annotations

import argparse, json, shutil, time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import structural_n07_reserve_probe as S       # solver interception + post-v1.6 setup (imports rearch_mech, linopy patched)

R, M, STATE, PM = S.R, S.M, S.STATE, S.PM
import post_v16_a3_runtime as RT  # noqa: E402
import post_v16_a3_gate as A3G  # noqa: E402

CHK = []


def check(name, ok, detail=''):
    CHK.append(dict(check=name, result='PASS' if ok else 'FAIL', detail=str(detail)[:400]))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {'' if ok else detail}", flush=True)


def firm_rows_ok(n):
    m = n.model
    fv = [v for v in m.variables if v.startswith('A2-F_cert_')]
    ub = [float(np.asarray(m.variables[v].upper.values)) for v in fv]
    return fv, all(u == 0.0 for u in ub)


def staged(fn, *a, **k):
    """run fn; the intercepted solve raises StopBeforeSolve (or a SystemExit from the ledger) - return the exception name"""
    try:
        fn(*a, **k)
        return 'NO_EXCEPTION'
    except S.StopBeforeSolve:
        return 'StopBeforeSolve'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    t0 = time.time()
    import gurobipy, linopy
    if gurobipy.Model.optimize is not S._no_solve or linopy.Model.solve is not S._no_solve:      # never reach a solver
        raise SystemExit('E2E: solver interception not in place - refused')
    config, siting = S.setup(out)
    raw = yaml.safe_load(A3G.CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str((out / 'ledgers').resolve())
    cfgp = out / 'config.byop_post_v16_a3.E2E.yaml'
    cfgp.write_text(yaml.safe_dump(raw), encoding='utf-8')
    c = A3G.load(cfgp)
    STATE['pv16_firm_rule'] = c['firm_rule']
    RT.arm(cfgp, None, gate_fn=lambda st: dict(approved=True, reasons=['E2E_INJECTED_GATE']))
    R.PV16_LOCK['armed'] = False
    R._arm_post_v16_optimizer_lock()                    # wraps the intercepting solve: a call outside a stage is refused
    gate = dict(approved=True, a3=True, firm_rule=c['firm_rule'], reference_dir=c['reference']['dir'])
    solve0 = M.solve
    M.solve = R.a3_solve_wrapper(solve0, None, out, gate)
    byop = list(R.ML_TECHS)
    nets, exc = {}, {}

    def build_and_solve(tag, scen, **kw):
        n, mult = M.build(config, scen, 2.8e6, **kw)
        nets[tag] = (n, mult)
        return M.solve(config, tag, out, n)

    for k in ('v2_pool_candidates', 'byop_cod', 'pv16m_re_firm', 'pv16_reserve_rhs_MW', 'shed_S0'):
        STATE.pop(k, None)
    STATE['firm_strict'] = False; STATE['lex'] = None
    exc['S0'] = staged(build_and_solve, 'S0', 'S0')
    check('S0: no RE+BESS firm rows', not firm_rows_ok(nets['S0'][0])[0])
    import post_v16_a2_gate as A2G
    STATE['shed_S0'] = A2G.read_no_harm_reference(A2G.WF / c['reference']['dir'])     # the formal A2 reference, as in the A3 run
    STATE['firm_strict'] = True; STATE['lex'] = dict(tag='S1_EARLIEST')
    exc['S1_EARLIEST'] = staged(build_and_solve, 'S1_EARLIEST', 'S')
    STATE['firm_strict'] = False; STATE['lex'] = None
    check('S1_EARLIEST: no RE+BESS firm rows', not firm_rows_ok(nets['S1_EARLIEST'][0])[0])
    STATE['pv16m_re_firm'] = None
    exc['S3'] = staged(build_and_solve, 'S3', 'S', byop=byop, reuse_dedicated=True)
    fv, ok = firm_rows_ok(nets['S3'][0])
    check('S3: RE+BESS firm certificate rows built with upper bound 0 (conservative rule)', bool(fv) and ok, (len(fv), ok))
    check('S3: certificate records say firm_credit_allowed False', all(not r['firm_credit_allowed'] for r in STATE.get('pv16m_re_firm') or [{}]))
    # S2 iteration 1: developer LP (needs S1 prices / offers; the S1 model was never solved -> zero prices, offers from the build)
    n1, mult1 = nets['S1_EARLIEST']
    n1.buses_t.marginal_price = pd.DataFrame(0.0, index=n1.snapshots, columns=n1.buses.index)
    STATE['offer'] = {(d['zone'], d['period']): dict(firm=0.0, cond=0.0, firm_stress=0.0) for d in STATE['dc']}
    STATE['triggers'] = {}
    STATE['reuse_s1'] = []
    RT.begin('S2_IT1')
    try:
        exc['S2_DEV'] = staged(R.developer_joint, config, n1, 2.8e6, mult1, True, 1)
    except Exception as e:
        exc['S2_DEV'] = f'{e.__class__.__name__}: {e}'[:300]
    # the developer network object of the failed call is not returned; rebuild it once (no solve) to inspect the firm rows
    STATE['offer'] = {(d['zone'], d['period']): dict(firm=0.0, cond=0.0, firm_stress=0.0) for d in STATE['dc']}
    dn, _, (sv_r, sv_c) = R.developer_joint_build(n1, 2.8e6, mult1)
    STATE['reuse'] = sv_r; STATE['corridors'] = sv_c; M.STATE['erm'] = True
    fv, ok = firm_rows_ok(dn)
    check('S2 developer LP: RE+BESS firm rows with upper bound 0 (same rule as S3)', bool(fv) and ok, (len(fv), ok))
    s_dev = {(d['zone'], d['period']): 0.0 for d in STATE['dc']}
    STATE['rights'] = {k: dict(firm=0.0, cond=0.0, S=0.0, mode='GO_F') for k in s_dev}
    STATE['s_upper_only'] = True
    M.extra = R.extra_rights
    exc['S2_PUBLIC'] = staged(build_and_solve, 'S2', 'S', byop=byop, byop_fixed={}, rfixed=None, s_fixed=s_dev)
    M.extra = R.extra_rearch
    STATE['s_upper_only'] = False; STATE['rights'] = None
    fv, ok = firm_rows_ok(nets['S2'][0])
    check('S2 public LP: RE+BESS firm rows with upper bound 0', (not fv) or ok, (len(fv), ok))
    if RT.ACCT['parent']:
        RT.end('ERROR', note='E2E: intercepted', **{'pass': False})
    STATE['a3_s2_target'] = dict(s_dev)
    exc['S3_mS2'] = staged(build_and_solve, 'S3_mS2', 'S', byop=byop, reuse_dedicated=True, s_fixed=s_dev)
    fv, ok = firm_rows_ok(nets['S3_mS2'][0])
    check('S3_mS2: RE+BESS firm rows with upper bound 0', bool(fv) and ok, (len(fv), ok))
    # ledgers
    _, _, log, child = A3G.paths(cfgp)
    lg = pd.read_csv(log, dtype=str, keep_default_na=False); cl = pd.read_csv(child, dtype=str, keep_default_na=False)
    lg.to_csv(out / 'E2E_A3_SOLVE_LOG.csv', index=False); cl.to_csv(out / 'E2E_A3_OPTIMIZER_CALL_LOG.csv', index=False)
    want = ['S0_COST', 'S1_SPEED_HIERARCHY', 'S3_COST', 'S2_DEV_LEX', 'S2_PUBLIC', 'S3_MS2_COST']
    check('every A3 stage routed through the A3 parent ledger in plan order', list(lg.stage) == ['S0', 'S1_EARLIEST', 'S3', 'S2_IT1', 'S3_mS2'], list(lg.stage))
    check('child rows: one per stage, of the planned kind, STARTED before the call and ERROR after the intercepted call',
          list(cl.kind) == want and set(cl.state) == {'ERROR'}, list(zip(cl.kind, cl.state)))
    check('every parent closed ERROR (no silent pass, no retry)', set(lg.state) == {'ERROR'} and set(lg['pass']) == {'False'}, list(lg.state))
    check('0 solver executions (every call intercepted)', all(x == 'refused' for x in S.SOLVER_CALLS), S.SOLVER_CALLS)
    rep = dict(work_package='BYOP_NEXT_07', step='W4 A3 end-to-end dry run', solver_executions=0, solver_calls_intercepted=len(S.SOLVER_CALLS),
               exceptions=exc, n_checks=len(CHK), n_pass=sum(x['result'] == 'PASS' for x in CHK), n_fail=sum(x['result'] == 'FAIL' for x in CHK),
               model_size={k: dict(nvars=int(v[0].model.nvars), ncons=int(v[0].model.ncons)) for k, v in nets.items() if getattr(v[0], 'model', None) is not None},
               gate='INJECTED (approved) - real gate refuses: NOT_APPROVED + S0 verdict', ledgers=str(out / 'ledgers'), seconds=round(time.time() - t0, 1))
    pd.DataFrame(CHK).to_csv(out / 'E2E_A3_CHECKS.csv', index=False)
    (out / 'E2E_A3_REPORT.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    RT.disarm()
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
