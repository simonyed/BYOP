#!/usr/bin/env python3
"""Mainline v1.3 Stage A structural test (E2): builds the real G-REAL S0 / S1_EARLIEST / S3 public networks and the
S2 joint developer network, creates their linopy models with every extra constraint, and inspects variables,
constraints and time series. NO SOLVER IS CALLED: linopy.Model.solve and gurobipy.Model.optimize are replaced by a
function that raises before anything is handed to a solver (the S1 lexicographic pre-solve is not built).
Run on L2 from pypsa-usa/workflow:  python -W ignore byop/tests/structural_mainline_v13.py --out results/BYOP/mainline/_structural
AIDC geospatial v1: --config selects the siting variant (default legacy eight Epoch buses); every count check uses the actual
research-bus number N_B x model years (legacy 8 x 6 = 48), e.g.
    python -W ignore byop/tests/structural_mainline_v13.py --config config/config.byop_ercot_mainline_geo_dynamic_v1.yaml --out results/BYOP/mainline/_structural_geo_dynamic_v1
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, 'byop/model')
import linopy  # noqa: E402
import pypsa  # noqa: E402
import rearch_mech as R  # noqa: E402

M, w2, V, STATE = R.M, R.w2, R.V, R.STATE
SOLVER_CALLS = []


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

CHK = []


def check(qa, name, ok, detail=''):
    CHK.append(dict(qa=qa, check=name, result='PASS' if ok else 'FAIL', detail=str(detail)[:400]))
    print(f"[{'PASS' if ok else 'FAIL'}] {qa} {name} {detail if not ok else ''}")


def build_model(tag, scen, **kw):
    n, mult = M.build(CONFIG, scen, 2.8e6, **kw)
    try:
        M.solve(CONFIG, tag, OUT, n)
    except StopBeforeSolve:
        pass
    return n, mult, n.model


def ints(m):
    return int(len(m.binaries) + len(m.integers))


def main():
    global CONFIG, OUT
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    ap.add_argument('--config', default='config/config.byop_ercot_mainline.yaml', help='mainline config (selects the siting variant)')
    a = ap.parse_args()
    siting = R.ml_select_siting(a.config)
    OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['STAGE_A_STRUCTURAL_TEST']))
    R.GCFG.update(setting='G-REAL', competing=0.0, regional_dc='off', case='base', gas_case='base', relax=[], s2_modes=R.MODES,
                  interrupt_cap=0.005, no_harm=True, base_assets='main')
    M.CFG.update(periods='annual', start=2026, end=2031, cost_basis='repaired', public_subsidy='without', tariff='energy', reuse='on',
                 reuse_case='base', frac_cod=True, flex=False, poi_lead=0, byop_case='base', public_case='base', byop_techs=list(R.ML_TECHS),
                 sample_weeks=26, bg_growth=0.0, line_exp=True, erm15=False, threads=4, v=2.8e6, v_private=None, smoke=False, dem_scale=1.0)
    R.configure_mainline(OUT)
    M.build = R.build_rearch; M.extra = R.extra_rearch
    w2.store_ERM_duals = V.store_erm_duals_tx; V.GCFG.update(erm_scope='tx')
    w2.PREP = str(R.BASE_TAMU); w2.PUE = pd.read_csv(w2.PUE_CSV)
    CONFIG = pypsa.Network(str(R.BASE_TAMU)).meta
    STATE['erm_cal'] = None
    sites = sorted(R.SITES)
    NB, NY = len(sites), len(M.periods())
    NK = NB * NY
    coh = pd.read_csv(R.ML_COH)
    coh = coh[coh.scenario == 'mid']
    check('QA-SPACE', f"{NB} aggregated POIs on TAMU64 AC buses ({siting['variant']})", NB > 0 and all(s in M.ZONES for s in sites)
          and set(sites) == set(coh.region_id), sites)
    if siting['variant'] == 'epoch8_legacy':
        check('QA-SPACE', 'legacy regression: the 8 Epoch buses', sites == ['p600 0', 'p610 2', 'p630 2', 'p630 4', 'p630 5', 'p630 6', 'p630 9', 'p650 0'], sites)
    # ------------------------------------------------------------------ S0
    n0, _, m0 = build_model('S0', 'S0')
    per = n0.snapshots.get_level_values(0)
    check('QA-DC', 'S0 has no research DC bus', not any(str(b).startswith('DC_') for b in n0.buses.index))
    ir = n0.loads.index[n0.loads.index.str.endswith(' inherited_ramp')]
    check('QA-DC', 'inherited ramp loads in S0 (5 buses, 460.73 MW IT)', len(ir) == 5 and abs(STATE['inherited_ramp']['IT_MW'] - 460.73) < 0.01, list(ir))
    check('QA-LP', 'S0 model continuous', ints(m0) == 0)
    ls0 = n0.generators[n0.generators.carrier == 'load_shed']
    check('QA-F2', 'mainline S0: every existing-customer load_shed (native + inherited ramp) at VOLL 35685',
          len(ls0) > 5 and (ls0.marginal_cost == 35685.0).all() and int(ls0.index.str.endswith(' inherited_ramp_unserved').sum()) == 5,
          ls0.marginal_cost.value_counts().to_dict())
    so = {k.lower(): v for k, v in CONFIG['solving']['solver_options'][CONFIG['solving']['solver']['options']].items()}   # Gurobi names are case-insensitive
    check('QA-F1', 'MAINLINE_GUROBI_LP_OPTIONS equal the main-solve config options', all(so.get(k.lower()) == v for k, v in R.MAINLINE_GUROBI_LP_OPTIONS.items()),
          {k: so.get(k.lower()) for k in R.MAINLINE_GUROBI_LP_OPTIONS})
    sm = R.stress_mask(n0.snapshots)
    nst = {p: int(sm[per == p].sum()) for p in M.periods()}
    check('QA-STRESS-FIRM', 'stress snapshots in every period', all(v_ >= 8 for v_ in nst.values()), nst)
    check('QA-STRESS-FIRM', 'snapshot weights sum to 8760 h per period',
          all(abs(float(n0.snapshot_weightings.generators[per == p].sum()) - 8760.0) < 1e-6 for p in M.periods()))
    g = n0.generators
    gas = g.index[g.carrier.isin(['CCGT', 'OCGT']) & ~g.p_nom_extendable][0]
    mc = n0.get_switchable_as_dense('Generator', 'marginal_cost')[gas]
    hr = 3412.14 / float(g.efficiency[gas]) / 1000
    d = {p: float(mc[per == p].iloc[0]) for p in M.periods()}
    check('QA-COST', 'existing gas mc follows the yearly WSC price', abs((d[2030] - d[2026]) - hr * (4.443 - 3.738)) < 1e-6, d)
    # audit P0-5: S0 calibration build -> every load_shed unit (native + inherited ramp) carries the calibration penalty
    R.GCFG['s0_calibrate'] = True
    n0c, _ = M.build(CONFIG, 'S0', 2.8e6)
    R.GCFG['s0_calibrate'] = False
    sh = n0c.generators[n0c.generators.carrier == 'load_shed']
    check('QA-P0-5', 'S0 calibration: all load_shed units incl. inherited ramp at S0CAL_SHED',
          len(sh) > 5 and (sh.marginal_cost == R.S0CAL_SHED).all() and int(sh.index.str.endswith(' inherited_ramp_unserved').sum()) == 5,
          sh.marginal_cost.value_counts().to_dict())
    del n0c
    # ------------------------------------------------------------------ S1_EARLIEST (strict, lexicographic pre-solve not built)
    STATE['firm_strict'] = True; STATE['lex'] = None
    n1, mult, m1 = build_model('S1_EARLIEST', 'S')
    STATE['firm_strict'] = False
    eqc = [c for c in m1.constraints if c.startswith('POI-eq_')]
    check('QA-SPACE', f'one POI equipment row per bus-year ({NK} = {NB} x {NY})', len(eqc) == NK, len(eqc))
    up = n1.links[n1.links.carrier == 'POI_upgrade']
    first = up.groupby(up.bus1).build_year.min()
    check('QA-COD', 'POI upgrade first build = max(2026 + 3, 2028) = 2029', (first == 2029).all(), first.to_dict())
    check('QA-DELAY-CAUSE', 'POI upgrades are approval cohorts (q in name)', up.index.str.contains(' q20').all())
    check('QA-LP', 'S1 model continuous', ints(m1) == 0)
    erm = [c for c in m1.constraints if c.endswith('_ERM')]
    check('QA-DELAY-CAUSE', 'resource-adequacy (ERM) row present', len(erm) >= 1, erm)
    kvl = [c for c in m1.constraints if 'Kirchhoff' in c or 'kvl' in c.lower()]
    check('QA-DELAY-CAUSE', 'upstream KVL network constraints present', len(kvl) >= 1, kvl[:3])
    dcl = n1.generators.index[n1.generators.carrier == 'compute_IT']
    pmin = n1.generators_t.p_min_pu[dcl]
    sm1 = R.stress_mask(n1.snapshots)
    check('QA-STRESS-FIRM', 'research load is present in the stress snapshots (firm import must serve it)',
          bool((pmin[sm1].max(axis=0) > 0).sum() >= 40), int((pmin[sm1].max(axis=0) > 0).sum()))
    # ------------------------------------------------------------------ S3 (coordinated, same physical options as S2)
    STATE['cond_public'] = {s: True for s in R.SITES}
    n3, _, m3 = build_model('S3', 'S', byop=list(R.ML_TECHS), reuse_dedicated=True)
    gb = n3.generators
    by = gb[gb.carrier.str.startswith('byop_')]
    su = n3.storage_units[n3.storage_units.carrier == 'byop_BESS']
    nore = {(d_['site'], d_['technology']) for d_ in STATE.get('byop_re_profile_missing', [])}     # dynamic variant only, flagged
    check('QA-SPACE', 'every bus has BYOP candidates of all 6 techs (except flagged missing wind / PV profiles)', all(
        {c for c in by[by.bus == f'DC_{s}'].carrier} | ({'byop_BESS'} if (su.bus == f'DC_{s}').any() else set())
        == {f'byop_{c}' for c in R.ML_TECHS if (s, c) not in nore} for s in R.SITES), sorted(nore))
    check('QA-SPACE', 'no BYOP unit outside its own DC bus', set(by.bus) | set(su.bus) <= {f'DC_{s}' for s in R.SITES})
    l1 = [s for s, d_ in R.SITES.items() if d_['gas_level'] == 'L1'][0]
    l2 = [s for s, d_ in R.SITES.items() if d_['gas_level'] == 'L2'][0]
    r1 = by[(by.bus == f'DC_{l1}') & (by.carrier == 'byop_RICE')].build_year.min()
    r2 = by[(by.bus == f'DC_{l2}') & (by.carrier == 'byop_RICE')].build_year.min()
    check('QA-COD', 'RICE earliest COD 2028 at L1 gas, 2029 at L2 (lateral lead in parallel)', (r1, r2) == (2028, 2029), (r1, r2))
    q29 = [x for x in by.index if x.endswith('BYOP RICE q2029') and x.startswith(f'DC_{l1}')]
    check('QA-COD', 'RICE approved 2029 cannot dispatch in 2029 / 2030', len(q29) == 1 and
          float(n3.generators_t.p_max_pu[q29[0]][(n3.snapshots.get_level_values(0) <= 2030)].max()) == 0.0, q29)
    sofc = by[by.carrier == 'byop_SOFC_NG'].build_year.min()
    check('QA-PARAM', 'SOFC standard earliest COD 2029 (3 y), no fast slot', sofc == 2029 and not any('FAST' in x for x in by.index), sofc)
    rice = by.index[(by.carrier == 'byop_RICE') & (by.build_year == 2028)][0]
    pp = n3.generators_t.p_max_pu[rice]; s3m = R.stress_mask(n3.snapshots); p3 = n3.snapshots.get_level_values(0)
    check('QA-FIRM', 'RICE normal dispatch 1.0, failure-case firm 1/1.25 only at stress', abs(float(pp[(p3 == 2029) & ~s3m].max()) - 1.0) < 1e-9
          and abs(float(pp[(p3 == 2029) & s3m].max()) - 0.8) < 1e-9)
    pv = by.index[by.carrier == 'byop_PV'][0]
    hrs = pd.DatetimeIndex(n3.snapshots.get_level_values(-1)).hour
    night = float(n3.generators_t.p_max_pu[pv][(hrs == 6) | (hrs == 9)].max())     # snapshots are UTC: 06 / 09 UTC = 00-04 h Texas time
    check('QA-COD', 'on-site PV produces nothing at night (06 and 09 UTC = local night)', night < 1e-6, night)
    wnd = by.index[by.carrier == 'byop_WIND'][0]
    check('QA-COD', 'on-site wind follows the bus profile (< 1 at the low-wind stress day)', float(n3.generators_t.p_max_pu[wnd][s3m].mean()) < 0.6)
    check('QA-BESS', 'BESS: 4 h, eta 0.85 round trip, cyclic SOC per period', len(su) > 0 and (su.max_hours == 4).all()
          and np.allclose(su.efficiency_store * su.efficiency_dispatch, 0.85) and su.cyclic_state_of_charge.all())
    check('QA-BESS', 'BESS SOC variables in the model', 'StorageUnit-state_of_charge' in m3.variables)
    for pre in ('ML-onsite_WIND_', 'ML-onsite_PV_', 'ML-potential_onwind_', 'ML-potential_solar_', 'GAS-mdq_', 'M2-serve_cap_', 'POI-eq_'):
        check('QA-SPACE', f'constraint family {pre}* present', any(c.startswith(pre) for c in m3.constraints))
    sc = m3.constraints[[c for c in m3.constraints if c.startswith('M2-serve_cap_DC_p610 2 S2031')][0]]
    pv_ = m3.variables['Generator-p_nom']
    lab2name = dict(zip(pv_.labels.values.ravel().tolist(), pv_.coords['name'].values.tolist()))
    names = {lab2name[int(x)] for x in np.asarray(sc.lhs.vars.values).ravel() if int(x) in lab2name}
    check('QA-FIRM', 'serve_cap (firm) credits gas BYOP, never wind / PV', any('RICE' in x for x in names) and not any(('WIND' in x or ' PV ' in x) for x in names), sorted(names)[:6])
    check('QA-LP', 'S3 model continuous', ints(m3) == 0)
    pub_wind = gb.index[(gb.carrier == 'onwind') & gb.p_nom_extendable & (gb.bus == 'p630 4')]
    cap = R.STATE['re_potential'][('p630 4', 'onwind')]
    check('QA-SPACE', 'public wind candidate capped by remaining ReEDS2 potential', (gb.p_nom_max[pub_wind] <= cap + 1e-6).all(), cap)
    # B10 / B8 fields on the (unsolved) ledger: p_nom_opt := p_nom, no dispatch
    for df_ in (n3.generators, n3.links, n3.storage_units):
        df_['p_nom_opt'] = df_['p_nom']
    STATE['offer'] = {}
    pl = R.poi_ledger(n3, 'S3', 'STRUCTURAL')
    need = ['IT_energized_MW', 'grid_import_MWh', 'BYOP_gen_MWh', 'BYOP_capacity_MW', 'certified_import_MW', 'equipment_total_MW',
            'poi_eq_dual_abs', 'procedure_ready_year', 'earliest_grid_COD', 'mode_label', 'pclr_trigger_hours_weighted',
            'pclr_curtailed_hours_weighted', 'pclr_max_consecutive_sampled_h']
    check('QA-BRIDGE', 'bus-year ledger carries the B10 / B8 fields', all(c in pl for c in need) and len(pl) == NK, [c for c in need if c not in pl])
    pl.to_csv(OUT / 'structural_poi_ledger_S3_unsolved.csv', index=False)
    # ------------------------------------------------------------------ S2 joint developer (built, not solved)
    n1.buses_t.marginal_price = pd.DataFrame(30.0, index=n1.snapshots, columns=list(M.ZONES))
    STATE['offer'] = {(d_['zone'], d_['period']): dict(firm=R.eq_terms(d_['zone'], d_['period'])[0], cond=R.pclr_cap(d_['zone'], d_['period']),
                                                       firm_stress=0.5 * R.eq_terms(d_['zone'], d_['period'])[0]) for d_ in STATE['dc']}
    STATE['triggers'] = R.select_triggers(n1)
    trig = next(iter(STATE['triggers'].values()))
    check('QA-STRESS-FIRM', 'PCLR triggers start at the stress snapshots', bool(R.stress_mask(pd.MultiIndex.from_tuples(trig[:1])).all()) if trig else False)
    nd, md, _ = R.developer_joint_build(n1, 2.8e6, mult)
    dcb = [b for b in nd.buses.index if str(b).startswith('DC_')]
    check('QA-LP', f'ONE developer network for all {NB} research buses', len(dcb) == NB, dcb)
    check('QA-LP', 'developer model continuous', ints(md) == 0)
    gpur = nd.generators[nd.generators.carrier == 'grid_purchase']
    check('QA-FIRM', 'developer grid purchase capped by the S1 joint offer per bus-year', len(gpur) == NK and (gpur.p_nom_extendable == False).all())
    gx = gpur.index[gpur.p_nom > 1.0][0]
    ppx = nd.generators_t.p_max_pu[gx]; smd = R.stress_mask(nd.snapshots); pdx = nd.snapshots.get_level_values(0) == int(gpur.build_year[gx])
    check('QA-P0-4', 'developer firm purchase at stress snapshots <= stress-certified offer (0.5 here), 1.0 elsewhere',
          abs(float(ppx[pdx & smd].max()) - 0.5) < 1e-9 and abs(float(ppx[pdx & ~smd].max()) - 1.0) < 1e-9, gx)
    check('QA-SPACE', 'developer constraints: on-site / potential / gas MDQ / serve_cap', all(any(c.startswith(p_) for c in md.constraints)
          for p_ in ('ML-onsite_', 'ML-potential_', 'GAS-mdq_', 'M2-serve_cap_')))
    check('QA-LP', 'no solver was called', SOLVER_CALLS.count('refused') == 3 and not any(c != 'refused' for c in SOLVER_CALLS), SOLVER_CALLS)
    res = pd.DataFrame(CHK)
    res.to_csv(OUT / 'STRUCTURAL_CHECKS.csv', index=False)
    miss = sorted({(d_['bus'], d_['technology']) for d_ in STATE.get('byop_re_profile_missing', [])})
    check('QA-RE', 'BYOP wind / PV only where the bus has a PyPSA-USA candidate profile (missing -> option absent, flagged)',
          siting['variant'] != 'epoch8_legacy' or not miss, miss)
    rep = dict(siting=siting, research_buses=sites, expected_bus_year_keys=NK, byop_re_profile_missing=miss, n_checks=len(res), n_pass=int((res.result == "PASS").sum()), n_fail=int((res.result == "FAIL").sum()), solver_executions=0,
               solver_calls_intercepted=len(SOLVER_CALLS), seconds=round(time.time() - t0, 1), stress=STATE.get('stress_sample'),
               gas=STATE.get('gas_repriced'), n_vars=dict(S0=int(m0.nvars), S1=int(m1.nvars), S3=int(m3.nvars), S2_dev=int(md.nvars)),
               n_cons=dict(S0=int(m0.ncons), S1=int(m1.ncons), S3=int(m3.ncons), S2_dev=int(md.ncons)))
    (OUT / 'STRUCTURAL_REPORT.json').write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))
    sys.exit(0 if rep['n_fail'] == 0 else 1)


if __name__ == '__main__':
    main()
