#!/usr/bin/env python3
"""NEXT-10U H3 static gate: builds S0, S1_EARLIEST and S3 of model version engineering_cost_v1 on the ADOPTED v1.7L lossy baseline
(16 research buses, 2026-2031, 26 sample weeks + B7 stress days, TECH_COMP_2, post-v1.6 rules) and inspects the engineering POI layer.
NO SOLVER IS CALLED: linopy.Model.solve and gurobipy.Model.optimize raise before anything reaches a solver.
Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n10u_engineering.py --out results/BYOP/next10u_engineering_cost_v1/_static
Writes N10U_STATIC_CHECKS.csv / N10U_STATIC_REPORT.json there and into current_work_pckg/BYOP_NEXT_10U/H3/.
"""
from __future__ import annotations

import argparse, json, shutil, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, 'byop/model')
import linopy  # noqa: E402
import pypsa  # noqa: E402
import rearch_mech as R  # noqa: E402
import post_v16_mainline as PM  # noqa: E402
import baseline_registry as BR  # noqa: E402

M, w2, V, STATE = R.M, R.w2, R.V, R.STATE
SOLVER_CALLS, CHK = [], []
CFG_PATH = 'config/config.byop_ercot_mainline_engineering_cost_v1.yaml'
PKG = Path('../current_work_pckg/BYOP_NEXT_10U/H3')
LEGACY = ('GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv', 'GREAL_POI_ASSUMPTIONS.csv', 'GREAL_POI_E0_SCHEDULE.csv')


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


def check(qa, name, ok, detail=''):
    CHK.append(dict(qa=qa, check=name, result='PASS' if ok else 'FAIL', detail=str(detail)[:400]))
    print(f"[{'PASS' if ok else 'FAIL'}] {qa} {name} {detail if not ok else ''}")


def build_model(config, out, tag, scen, **kw):
    n, mult = M.build(config, scen, 2.8e6, **kw)
    try:
        M.solve(config, tag, out, n)
    except StopBeforeSolve:
        pass
    return n, n.model


def rhs_of(m, name):
    return float(np.asarray(m.constraints[name].rhs.values).ravel()[0])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    R.BASE_TAMU = BR.BASE_TAMU_V17L
    siting = R.ml_select_siting(CFG_PATH)
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['NEXT10U_STATIC']))
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
    config = pypsa.Network(str(R.BASE_TAMU)).meta
    STATE['erm_cal'] = None
    sites = sorted(R.SITES)
    cand = pd.read_csv(R.POI_MODELS['engineering_cost_v1']['candidates'])
    known = pd.read_csv(R.POI_MODELS['engineering_cost_v1']['poi_equipment'])
    sitet = pd.read_csv(R.POI_MODELS['engineering_cost_v1']['poi'])
    # ------------------------------------------------------------------ G0 / G1 input and version checks
    check('QA-BASE', 'v1.7L ADOPTED formal baseline file and SHA', M.sha(R.BASE_TAMU) == BR.BASE_TAMU_V17L_SHA256 and BR.summary()['formal'] == 'v17l')
    check('QA-BASE', 'baseline meta transmission_losses = registry (2)', BR.meta_loss_problems(config) == [], BR.meta_loss_problems(config))
    check('QA-VERSION', 'poi_model engineering_cost_v1 selected by the config', R.ML['poi_model'] == 'engineering_cost_v1' and siting['poi_model'] == 'engineering_cost_v1')
    names = [Path(p).name for p in R.ML_INPUTS]
    check('QA-NEG', 'legacy POI proxy table and E0 schedule NOT among the model inputs', not set(LEGACY) & set(names), names)
    check('QA-NEG', 'engineering site table has no poi_upgrade_* / earliest_grid_COD_* / E0_total column',
          not [c for c in sitet.columns if c.startswith(('poi_upgrade_', 'earliest_grid_COD')) or c == 'E0_total_MW'])
    check('QA-NEG', 'no SITES entry carries a 2,000 MW per-cohort cap or a 3 y lead',
          all(abs(R.SITES[s]['U_max'] - 2000.0) > 1e-6 and abs(R.SITES[s]['U_lead'] - 3.0) > 1e-6 for s in sites))
    check('QA-SPACE', '16 research buses', len(sites) == 16, len(sites))
    e0 = {s: R.SITES[s]['E0rows'] for s in sites}
    check('QA-E0', 'known equipment rows only (E0 / E1 from ENG_POI_EQUIPMENT_KNOWN), every row pre-energized evidence with its own COD',
          sum(len(v) for v in e0.values()) == len(known) and all(x['pre'] for v in e0.values() for x in v), {s: len(v) for s, v in e0.items() if v})
    check('QA-E0', 'approved rights are not equipment: Abilene (p610 2) has an approved right but no known equipment',
          R.SITES['p610 2']['approved_right_MW'] > 900 and R.SITES['p610 2']['E0'] == 0.0)
    check('QA-E0', 'Helios known equipment = 200 MW (2026.5) + Phase II 391 MW (2027.5) <= Helios I 800 MW approval',
          abs(R.SITES['p600 0']['E0'] - 591.0) < 1e-6 and sorted(x['cod'] for x in e0['p600 0']) == [2026.5, 2027.5])
    res = {}
    for tag, scen, kw in (('S0', 'S0', {}), ('S1_EARLIEST', 'S', {}), ('S3', 'S', dict(byop=list(R.ML_TECHS), reuse_dedicated=True))):
        STATE['firm_strict'] = True; STATE['lex'] = None
        for k in ('v2_pool_candidates', 'byop_cod', 'pv16m_re_firm'):
            STATE.pop(k, None)
        if tag == 'S1_EARLIEST':      # SYNTHETIC zero S0 shed reference, only so the D24 no-harm row is built and inspected
            n0_ = res['S0']['n']
            STATE['shed_S0'] = pd.DataFrame(0.0, index=n0_.snapshots, columns=n0_.generators.index[n0_.generators.carrier == 'load_shed'])
        n, m = build_model(config, out, tag, scen, **kw)
        if tag == 'S1_EARLIEST':
            STATE['shed_S0'] = None
        res[tag] = dict(n=n, m=m, eng_rows=list(STATE.get('eng_rows') or []))
        check('QA-LP', f'{tag}: continuous LP (no integer / binary)', int(len(m.binaries) + len(m.integers)) == 0)
    n0, m0 = res['S0']['n'], res['S0']['m']
    n1, m1 = res['S1_EARLIEST']['n'], res['S1_EARLIEST']['m']
    n3, m3 = res['S3']['n'], res['S3']['m']
    # ------------------------------------------------------------------ S0 not contaminated by AIDC POI inputs
    check('QA-S0', 'S0: no DC bus, no POI / POI_upgrade link, no compute_IT unit, no ENG row',
          not n0.buses.index.str.startswith('DC_').any() and not n0.links.carrier.isin(['POI', 'POI_upgrade', 'POI_cond']).any()
          and not (n0.generators.carrier == 'compute_IT').any() and not [c for c in m0.constraints if c.startswith('ENG-')])
    # ------------------------------------------------------------------ S1 engineering POI layer
    up1 = n1.links[n1.links.carrier == 'POI_upgrade']
    want = cand[cand.enabled == 1]
    want = want[[M.first_period(c) is not None for c in want.equipment_COD]]
    exp_names = {f"POIup {r.site_id} {r.engineering_class} q{r.commitment_year}" for r in want.itertuples()}
    check('QA-POI', 'S1: one POI_upgrade link per enabled site / class / commitment year (exactly the candidate table)',
          set(up1.index) == exp_names, dict(n_links=len(up1), n_expected=len(exp_names), extra=sorted(set(up1.index) - exp_names)[:3],
                                            missing=sorted(exp_names - set(up1.index))[:3]))
    ok_cap = all(abs(float(up1.p_nom_max[f"POIup {r.site_id} {r.engineering_class} q{r.commitment_year}"]) - float(r.class_cumulative_cap_MW)) < 1e-6
                 and int(up1.build_year[f"POIup {r.site_id} {r.engineering_class} q{r.commitment_year}"]) == M.first_period(r.equipment_COD) for r in want.itertuples())
    check('QA-POI', 'S1: link p_nom_max = class cumulative cap, build year = first period of the equipment COD', ok_cap)
    check('QA-POI', 'S1: no legacy approval-cohort link (POIup <site> q<year> without class) and no 2,000 MW cap',
          not [x for x in up1.index if len(x.split()) == 4] and not (up1.p_nom_max >= 2000 - 1e-6).any())
    check('QA-POI', 'S1: no LOCAL_POI_UPGRADE link (policy upper bound 0)', not [x for x in up1.index if ' LOCAL ' in x])
    check('QA-POI', 'S1: every POI_upgrade link is priced (capital_cost > 0) and carries no flow (p_max_pu = 0)',
          bool((up1.capital_cost > 0).all()) and bool((up1.p_max_pu == 0).all()))
    cons1 = set(m1.constraints)
    exp_rows = set()
    for s in sites:
        L = [x for x in up1.index if x.split()[0:3] == ['POIup', *s.split()]]
        if not L:
            continue
        exp_rows.add(f'ENG-cum_site_{s}')
        for cls in ('RIGHTED', 'NEW_REQUEST'):
            if any(f' {cls} ' in x for x in L):
                exp_rows.add(f'ENG-cum_{cls}_{s}')
        for Q in range(2026, 2032):
            if any(int(x.rsplit('q', 1)[1]) <= Q for x in L):
                exp_rows.add(f'ENG-vis_{s}_{Q}')
    check('QA-ENG', 'S1: cumulative (per class, per site) and disclosure rows present for every site with candidates',
          exp_rows <= cons1, sorted(exp_rows - cons1)[:5])
    vis = pd.read_csv(R.POI_MODELS['engineering_cost_v1']['visibility'])
    ok_vis = all(abs(rhs_of(m1, f'ENG-vis_{r.site_id}_{r.commitment_year}') - float(r.visible_new_order_cap_MW)) < 1e-6
                 for r in vis.itertuples() if f'ENG-vis_{r.site_id}_{r.commitment_year}' in cons1)
    check('QA-ENG', 'S1: disclosure-row RHS = announced facility envelope by Q - known equipment (ENG_POI_VISIBILITY)', ok_vis)
    ok_cum = all(abs(rhs_of(m1, f'ENG-cum_site_{s}') - R.SITES[s]['eng_caps']['total']) < 1e-6 for s in sites if f'ENG-cum_site_{s}' in cons1)
    check('QA-ENG', 'S1: site cumulative-row RHS = site cap - known equipment (never re-buy known equipment)', ok_cum)
    # equipment in POI-eq rows, year by year (full-year firm rule)
    fixed = {(d['zone'], d['period']): R.eq_terms(d['zone'], d['period'])[0] for d in STATE['dc']}
    check('QA-COD', 'Helios: 0 MW firm equipment in 2026 (COD 2026.5), 200 in 2027, 591 from 2028',
          fixed[('p600 0', 2026)] == 0.0 and fixed[('p600 0', 2027)] == 200.0 and abs(fixed[('p600 0', 2028)] - 591.0) < 1e-6,
          {y: fixed[('p600 0', y)] for y in range(2026, 2032)})
    check('QA-COD', 'E4 sites: no fixed equipment and no upgrade term before 2030 (COD 2029.16 -> first full firm year 2030)',
          all(fixed[('p630 4', y)] == 0.0 and not R.eq_terms('p630 4', y)[1] for y in range(2026, 2030)) and bool(R.eq_terms('p630 4', 2030)[1]))
    poi_eq = [c for c in m1.constraints if c.startswith('POI-eq_')]
    check('QA-COD', 'S1: POI-eq rows for every site-year', len(poi_eq) == len(STATE['dc']), (len(poi_eq), len(STATE['dc'])))
    # ------------------------------------------------------------------ S2 / S3 physical identity of the engineering layer
    up3 = n3.links[n3.links.carrier == 'POI_upgrade']
    same = set(up3.index) == set(up1.index) and np.allclose(up3.loc[up1.index, 'p_nom_max'].values, up1.p_nom_max.values) \
        and np.allclose(up3.loc[up1.index, 'capital_cost'].values, up1.capital_cost.values)
    check('QA-S2S3', 'S3: identical POI candidate set, caps and costs as S1 (one build path for S1 / S2-public / S3 / S3_mS2)', same)
    check('QA-S2S3', 'S3: identical ENG cumulative / disclosure rows as S1',
          {c for c in m3.constraints if c.startswith('ENG-')} == {c for c in m1.constraints if c.startswith('ENG-')})
    check('QA-S2S3', 'S3: no CIAC / security term in the social objective (grid_purchase only exists in the developer LP)',
          not (n3.generators.carrier == 'grid_purchase').any())
    check('QA-LP', 'no solver was called (only intercepted model calls)', all(c == 'refused' for c in SOLVER_CALLS), SOLVER_CALLS)
    eng_rows = pd.DataFrame(res['S1_EARLIEST']['eng_rows'])
    eng_rows.to_csv(out / 'N10U_ENG_ROWS_S1.csv', index=False)
    pd.DataFrame([dict(link=x, site=' '.join(x.split()[1:3]), cls=x.split()[3], q=int(x.rsplit('q', 1)[1]), p_nom_max=float(up1.p_nom_max[x]),
                       build_year=int(up1.build_year[x]), capital_cost=float(up1.capital_cost[x])) for x in up1.index]).to_csv(out / 'N10U_POI_LINKS_S1.csv', index=False)
    rep = dict(stage='NEXT10U_H3_STATIC', solver_executions=0, solver_calls_intercepted=len(SOLVER_CALLS), poi_model=R.ML['poi_model'],
               siting=siting, n_checks=len(CHK), n_pass=sum(c['result'] == 'PASS' for c in CHK), n_fail=sum(c['result'] == 'FAIL' for c in CHK),
               n_vars={k: int(v['m'].nvars) for k, v in res.items()}, n_cons={k: int(v['m'].ncons) for k, v in res.items()},
               poi_links_S1=len(up1), eng_rows_S1=len(eng_rows), seconds=round(time.time() - t0, 1), base_sha256=M.sha(R.BASE_TAMU),
               tech_version=M.CFG['tech_version'], verdict='STATIC_PASS' if all(c['result'] == 'PASS' for c in CHK) else 'STATIC_FAIL')
    pd.DataFrame(CHK).to_csv(out / 'N10U_STATIC_CHECKS.csv', index=False)
    (out / 'N10U_STATIC_REPORT.json').write_text(json.dumps(rep, indent=1, default=str))
    PKG.mkdir(parents=True, exist_ok=True)
    for f in ('N10U_STATIC_CHECKS.csv', 'N10U_STATIC_REPORT.json', 'N10U_ENG_ROWS_S1.csv', 'N10U_POI_LINKS_S1.csv'):
        shutil.copy2(out / f, PKG / f)
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
