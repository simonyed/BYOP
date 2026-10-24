#!/usr/bin/env python3
"""NEXT-10U A3 end-to-end dry run of model version engineering_cost_v1 with ZERO optimizer executions (pattern of
structural_n07_a3_e2e.py): the real models of every A3 stage (S0, S1_EARLIEST, S3, S2 developer, S2 public, S3_mS2) are built through
the real A3 solve wrapper and linopy lock on the ADOPTED v1.7L baseline with the engineering POI model; the gate is injected as approved
and the ledgers live in a scratch directory, so nothing touches the formal A3 ledgers or budget. linopy.Model.solve and
gurobipy.Model.optimize raise before any solver is reached.
The S1 network is never solved, so the S2 inputs are synthetic: zero prices, POI_upgrade p_nom_opt = 50 MW on every engineering
candidate (so the CIAC / security price path is non-trivial), empty dispatch. Checks: the S2 private import-right price
(ml_eng_ciac) is built and positive where new equipment exists; the developer LP prices the right (grid_purchase extendable at
the CIAC rate) and carries no POI / ENG rows; the public S2 / S3_mS2 LPs carry the ENG rows and no CIAC; 0 solver runs.
Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n10u_a3_e2e.py --out results/BYOP/next10u_engineering_cost_v1/_a3_e2e
"""
from __future__ import annotations

import argparse, json, shutil, time
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import yaml

import structural_n07_reserve_probe as S       # solver interception (linopy / gurobipy patched) + rearch_mech imports

R, M, STATE, PM = S.R, S.M, S.STATE, S.PM
w2, V = R.w2, R.V
import baseline_registry as BR  # noqa: E402
import post_v16_a3_runtime as RT  # noqa: E402
import post_v16_a3_gate as A3G  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402

CFG_PATH = 'config/config.byop_ercot_mainline_engineering_cost_v1.yaml'
A3CFG = Path('config/config.byop_next10u_a3.yaml')
CHK = []


def check(name, ok, detail=''):
    CHK.append(dict(check=name, result='PASS' if ok else 'FAIL', detail=str(detail)[:400]))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {'' if ok else detail}", flush=True)


def staged(fn, *a, **k):
    try:
        fn(*a, **k)
        return 'NO_EXCEPTION'
    except S.StopBeforeSolve:
        return 'StopBeforeSolve'


def setup(out):
    """the NEXT-10U mainline setup of structural_n10u_engineering.py (v1.7L baseline, engineering POI model)"""
    R.BASE_TAMU = BR.BASE_TAMU_V17L
    siting = R.ml_select_siting(CFG_PATH)
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['NEXT10U_A3_E2E']))
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


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    t0 = time.time()
    import gurobipy, linopy
    if gurobipy.Model.optimize is not S._no_solve or linopy.Model.solve is not S._no_solve:
        raise SystemExit('E2E: solver interception not in place - refused')
    config, siting = setup(out)
    check('engineering_cost_v1 POI model on the v1.7L baseline', R.ML['poi_model'] == 'engineering_cost_v1' and M.sha(R.BASE_TAMU) == BR.BASE_TAMU_V17L_SHA256)
    raw = yaml.safe_load(A3CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str((out / 'ledgers').resolve())
    cfgp = out / 'config.byop_next10u_a3.E2E.yaml'
    cfgp.write_text(yaml.safe_dump(raw), encoding='utf-8')
    c = A3G.load(cfgp)
    STATE['pv16_firm_rule'] = c['firm_rule']
    R.ML['gate'] = dict(approved=True, reasons=['E2E_INJECTED_GATE'])
    RT.arm(cfgp, None, gate_fn=lambda st: dict(approved=True, reasons=['E2E_INJECTED_GATE']))
    R.PV16_LOCK['armed'] = False
    R._arm_post_v16_optimizer_lock()
    gate = dict(approved=True, a3=True, firm_rule=c['firm_rule'], reference_dir=c['reference']['dir'])
    M.solve = R.a3_solve_wrapper(M.solve, None, out, gate)
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
    ref = A2G.read_no_harm_reference(A2G.WF / c['reference']['dir'])
    check('formal NEXT-10U S0 no-harm reference readable (pinned dir)', ref is not None and len(ref) > 0, c['reference']['dir'])
    STATE['shed_S0'] = ref
    STATE['firm_strict'] = True; STATE['lex'] = dict(tag='S1_EARLIEST')
    exc['S1_EARLIEST'] = staged(build_and_solve, 'S1_EARLIEST', 'S')
    STATE['firm_strict'] = False; STATE['lex'] = None
    STATE['pv16m_re_firm'] = None
    STATE['cond_public'] = {s: True for s in R.SITES}
    exc['S3'] = staged(build_and_solve, 'S3', 'S', byop=byop, reuse_dedicated=True)
    m3 = nets['S3'][0].model
    check('S3: ENG cumulative / disclosure rows present', any(k.startswith('ENG-') for k in m3.constraints))
    # ---------------------------------------------------------------- synthetic S1 "solution" -> S2 inputs (s1_offer, ml_eng_ciac)
    n1, mult1 = nets['S1_EARLIEST']
    up = n1.links.index[n1.links.carrier == 'POI_upgrade']
    n1.links['p_nom_opt'] = n1.links.p_nom.astype(float)
    n1.links.loc[up, 'p_nom_opt'] = 50.0
    n1.generators['p_nom_opt'] = n1.generators.p_nom.astype(float)
    n1.buses_t.marginal_price = pd.DataFrame(0.0, index=n1.snapshots, columns=n1.buses.index)
    STATE['triggers'] = {}
    STATE['reuse_s1'] = []
    STATE['offer'], off = R.s1_offer(n1)
    STATE['offer'] = {k: dict(v, firm=max(v['firm'], 50.0), firm_stress=max(v['firm_stress'], 50.0)) for k, v in STATE['offer'].items()}  # synthetic
    ciac = R.ml_eng_ciac(n1)
    ciac.to_csv(out / 'E2E_S2_PRIVATE_GRID_RIGHT_CHARGES.csv', index=False)
    check('S1 offer table built for every DC site-year', len(off) == len(STATE['dc']), (len(off), len(STATE['dc'])))
    check('ml_eng_ciac: one row per engineering site-year, positive right price where new POI equipment exists',
          len(ciac) > 0 and bool((ciac.loc[ciac.new_poi_equipment_MW > 1e-3, 'right_price_USD_per_MW_yr'] > 0).all())
          and bool((ciac.loc[ciac.new_poi_equipment_MW <= 1e-3, 'right_price_USD_per_MW_yr'] == 0).all()),
          ciac[['site', 'year', 'new_share', 'right_price_USD_per_MW_yr']].head(8).to_dict('records'))
    check('ml_eng_ciac: security hold = (COD - q) + 2 y on the built candidates', bool((ciac.loc[ciac.new_poi_equipment_MW > 1e-3, 'security_hold_y'] > 2.0).all()))
    # ---------------------------------------------------------------- S2 iteration 1: developer LP through the A3 wrapper
    RT.begin('S2_IT1')
    try:
        exc['S2_DEV'] = staged(R.developer_joint, config, n1, 2.8e6, mult1, True, 1)
    except Exception as e:
        exc['S2_DEV'] = f'{e.__class__.__name__}: {e}'[:300]
    dn, dm, (sv_r, sv_c) = R.developer_joint_build(n1, 2.8e6, mult1)
    STATE['reuse'] = sv_r; STATE['corridors'] = sv_c; M.STATE['erm'] = True
    check('S2 developer LP reaches the (intercepted) solve', exc['S2_DEV'] == 'StopBeforeSolve', exc['S2_DEV'])
    gp = dn.generators[dn.generators.carrier == 'grid_purchase'] if 'carrier' in dn.generators else pd.DataFrame()
    ext = gp[gp.p_nom_extendable]
    check('S2 developer LP: grid_purchase import right extendable and priced (CIAC + security) exactly where ml_eng_ciac is positive',
          len(ext) > 0 and bool((ext.capital_cost > 0).all()) and len(ext) == int((ciac.right_price_USD_per_MW_yr > 0).sum())
          and bool((ext.p_nom_max <= 50.0 + 1e-9).all()), (len(gp), len(ext), int((ciac.right_price_USD_per_MW_yr > 0).sum())))
    check('S2 developer LP: no POI / POI_upgrade links and no ENG rows (the developer receives an offer)',
          not dn.links.carrier.isin(['POI', 'POI_upgrade']).any() and not [k for k in dm.constraints if k.startswith('ENG-')])
    s_dev = {(d['zone'], d['period']): 0.0 for d in STATE['dc']}
    STATE['rights'] = {k: dict(firm=0.0, cond=0.0, S=0.0, mode='GO_F') for k in s_dev}
    STATE['s_upper_only'] = True
    M.extra = R.extra_rights
    exc['S2_PUBLIC'] = staged(build_and_solve, 'S2', 'S', byop=byop, byop_fixed={}, rfixed=None, s_fixed=s_dev)
    M.extra = R.extra_rearch
    STATE['s_upper_only'] = False; STATE['rights'] = None
    n2 = nets['S2'][0]
    check('S2 public LP: ENG rows present, no grid_purchase (no CIAC in a public objective)',
          any(k.startswith('ENG-') for k in n2.model.constraints) and not (n2.generators.carrier == 'grid_purchase').any())
    if RT.ACCT['parent']:
        RT.end('ERROR', note='E2E: intercepted', **{'pass': False})
    STATE['a3_s2_target'] = dict(s_dev)
    exc['S3_mS2'] = staged(build_and_solve, 'S3_mS2', 'S', byop=byop, reuse_dedicated=True, s_fixed=s_dev)
    n4 = nets['S3_mS2'][0]
    check('S3_mS2: ENG rows present, no grid_purchase', any(k.startswith('ENG-') for k in n4.model.constraints)
          and not (n4.generators.carrier == 'grid_purchase').any())
    _, _, log, child = A3G.paths(cfgp)
    lg = pd.read_csv(log, dtype=str, keep_default_na=False); cl = pd.read_csv(child, dtype=str, keep_default_na=False)
    lg.to_csv(out / 'E2E_A3_SOLVE_LOG.csv', index=False); cl.to_csv(out / 'E2E_A3_OPTIMIZER_CALL_LOG.csv', index=False)
    want = ['S0_COST', 'S1_SPEED_HIERARCHY', 'S3_COST', 'S2_DEV_LEX', 'S2_PUBLIC', 'S3_MS2_COST']
    check('every A3 stage routed through the A3 parent ledger in plan order', list(lg.stage) == ['S0', 'S1_EARLIEST', 'S3', 'S2_IT1', 'S3_mS2'], list(lg.stage))
    check('child rows: one per stage, of the planned kind, ERROR after the intercepted call', list(cl.kind) == want and set(cl.state) == {'ERROR'},
          list(zip(cl.kind, cl.state)))
    check('0 solver executions (every call intercepted)', all(x == 'refused' for x in S.SOLVER_CALLS), S.SOLVER_CALLS)
    rep = dict(work_package='BYOP_NEXT_10U', step='A3 end-to-end dry run (engineering_cost_v1)', solver_executions=0,
               solver_calls_intercepted=len(S.SOLVER_CALLS), exceptions=exc, n_checks=len(CHK),
               n_pass=sum(x['result'] == 'PASS' for x in CHK), n_fail=sum(x['result'] == 'FAIL' for x in CHK),
               model_size={k: dict(nvars=int(v[0].model.nvars), ncons=int(v[0].model.ncons)) for k, v in nets.items() if getattr(v[0], 'model', None) is not None},
               gate='INJECTED (approved) in a scratch ledger', seconds=round(time.time() - t0, 1))
    pd.DataFrame(CHK).to_csv(out / 'E2E_A3_CHECKS.csv', index=False)
    (out / 'E2E_A3_REPORT.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    RT.disarm()
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
