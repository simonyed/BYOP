#!/usr/bin/env python3
"""WP2 S1 with REAL 2026-2035 Texas cohorts on the native ERCOT 8s baseline (2030 investment period).

Run from pypsa-usa/workflow with the PyPSA-USA env:
    python byop/model/wp2_ercot_s1_real.py --out results/BYOP/wp2_ercot8s_real

Cohorts: the PNNL-based 7-zone cohort file was deleted (RA-DC-SPATIAL-04, 2026-10-21); this WP2 run needs a new spatial basis.
POI timing: LEAD-01 is PENDING_USER, so this run is the explicit ZERO-LEAD BOUND (POI COD = request year): every
request <= 2030 is grid-connectable in 2030, requests 2031-2035 are added with POI build_year > 2030 and must stay off.
Workload (configs/aidc_workload.yaml, TASK-01, 2030 row of yearly_task_parameters_2022_2050.csv):
  P_inf[t]   = K * infer_share * infer_util * m(daytype, 3h block)           fixed
  P_train[t] >= 0, sum_{t in day} 3h * P_train = 24 * K * train_share * train_util   (no inter-day shifting)
  P_inf + P_train <= K
  facility   = PUE_TX_2030 * (0.20 * K + 0.80 * (P_inf + P_train))           PUE applied once
Training is a sign=-1 generator on the DC bus (flexible load); ERM-DC-01 B charges POI flow to the zone ERM row.
"""
from __future__ import annotations

import argparse, copy, json, logging, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wp2_ercot_s0_s1 as w2  # noqa: E402

import byop_paths as BP  # noqa: E402
COHORTS = BP.COHORTS_7ZONE
TASK = BP.TASK
TRACE = BP.TRACE
IDLE = 0.20
YEAR = w2.YEAR
logger = logging.getLogger('wp2_real')
TRAIN = {}  # training generator name -> daily facility-side MWh target


def three_hour_multipliers(n):
    tr = pd.read_csv(TRACE)
    prof = {(r.type, int(r.h)): float(r.multiplier) for r in tr.itertuples()}
    ts = n.snapshots.get_level_values(1)
    out = []
    for t in ts:
        dt = 'we' if t.weekday() >= 5 else 'wd'
        out.append(np.mean([prof[(dt, h)] for h in range(t.hour, t.hour + 3)]))
    return pd.Series(out, index=n.snapshots)


def add_real_zone(n, zone, K_online, K_late, pue, par, mult):
    """One DC facility bus per zone: online cohorts (POI COD <= 2030) and late cohorts (POI COD 2031+)."""
    dc = f'DC_{zone}'
    zb = n.buses.loc[zone]
    for c in ['POI', 'compute_unserved', 'AIDC_training']:
        if c not in n.carriers.index:
            n.add('Carrier', c, co2_emissions=0.0)
    n.add('Bus', dc, carrier='AC', x=zb.x, y=zb.y, v_nom=zb.v_nom, country='DC', reeds_zone='DC',
          reeds_state='DC', interconnect='dc_facility', nerc_reg='DC')
    p_inf = K_online * par['infer_share'] * par['infer_util'] * mult
    fixed = pue * (IDLE * K_online + (1 - IDLE) * p_inf)
    n.add('Load', f'{dc} inference_idle', bus=dc, p_set=fixed, carrier='AC')
    tname = f'{dc} training'
    head = ((K_online - p_inf) / K_online).clip(lower=0) if K_online > 0 else 0 * mult
    n.add('Generator', tname, bus=dc, carrier='AIDC_training', sign=-1, p_nom=pue * (1 - IDLE) * K_online,
          p_nom_extendable=False, p_max_pu=head, marginal_cost=0.0, build_year=YEAR, lifetime=100)
    TRAIN[tname] = pue * (1 - IDLE) * 24 * K_online * par['train_share'] * par['train_util']
    peak = pue * K_online
    n.add('Link', f'POI {zone} online', bus0=zone, bus1=dc, p_nom=peak, efficiency=1.0, build_year=YEAR,
          lifetime=100, carrier='POI', marginal_cost=0.0, capital_cost=0.0, p_nom_extendable=False)
    if K_late > 0:  # COD-gated requests 2031-2035: POI exists but is inactive in the 2030 period
        n.add('Link', f'POI {zone} late', bus0=zone, bus1=dc, p_nom=pue * K_late, efficiency=1.0,
              build_year=YEAR + 1, lifetime=100, carrier='POI', marginal_cost=0.0, capital_cost=0.0,
              p_nom_extendable=False)
    n.add('Generator', f'{dc} unserved', bus=dc, p_nom=peak, p_nom_extendable=False,
          marginal_cost=w2.BACKLOG_USD_PER_MWH, carrier='compute_unserved', build_year=YEAR, lifetime=100)
    return dict(dc=dc, K_online=K_online, K_late=K_late, p_inf=p_inf, fixed=fixed, train=tname, peak=peak)


def extra_with_training(n, snapshots):
    w2.extra_functionality_erm_dc(n, snapshots)
    if not TRAIN:
        return
    m = n.model
    w = n.snapshot_weightings.generators
    days = pd.Index(snapshots.get_level_values(1).normalize(), name='day')
    for g, target in TRAIN.items():
        p = m['Generator-p'].sel(name=g)
        wt = xr_da(w.loc[snapshots].values, snapshots)
        expr = (p * wt).groupby(xr_da(days.values, snapshots, 'day')).sum()
        m.add_constraints(expr == target, name=f'AIDC_train_daily_{g}')
    logger.info(f'training daily-energy constraints added for {list(TRAIN)}')


def xr_da(values, snapshots, name=None):
    import xarray as xr
    return xr.DataArray(values, coords={'snapshot': snapshots}, dims='snapshot', name=name)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    ap.add_argument('--scenarios', nargs='*', default=['low', 'mid', 'high'])
    ap.add_argument('--leads', nargs='*', type=int, default=[0], help='LEAD-01 years from requested_year to POI COD (approved 2/3/5; 0 = bound)')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(out / 'ERCOT_solver.log', 'w', 'utf-8'), logging.StreamHandler()])
    w2.PUE = pd.read_csv(w2.PUE_CSV)
    w2.ZONES = [b for b in pypsa.Network(w2.PREP).buses.index if b not in w2.EXCLUDE_ZONES]  # SPATIAL-ERCOT-03
    w2.sn.extra_functionality = extra_with_training
    pue = float(w2.PUE[(w2.PUE.st == 'TX') & (w2.PUE.year == YEAR)].pue.iloc[0])
    par = pd.read_csv(TASK).set_index('year').loc[YEAR].to_dict()
    if COHORTS is None:
        raise SystemExit('PNNL-based 7-zone cohorts were deleted (RA-DC-SPATIAL-04); WP2 S1 needs a new spatial basis')
    coh = pd.read_csv(COHORTS)
    config = pypsa.Network(w2.PREP).meta

    results, summ, wl = {}, {}, {}
    for s, L in [(s, L) for s in a.scenarios for L in a.leads]:
        TRAIN.clear()
        n = w2.base_network(config)
        mult = three_hour_multipliers(n)
        c = coh[coh.scenario == s]
        cod = c.request_year + L  # LEAD-01: POI COD = requested_year + L
        on = c[cod <= YEAR].groupby('region_id').IT_MW.sum()
        late = c[cod > YEAR].groupby('region_id').IT_MW.sum()
        zones = {}
        for z in sorted(set(on.index) | set(late.index)):
            zones[z] = add_real_zone(n, z, float(on.get(z, 0.0)), float(late.get(z, 0.0)), pue, par, mult)
        tag = f'S1_real_{s}_L{L}'
        logger.info(f'=== solving {tag}: online IT {on.round(1).to_dict()} late IT {late.round(1).to_dict()} ===')
        results[tag] = w2.solve(n, config, tag, out, erm_dc_mode='B')
        sw = n.snapshot_weightings.generators
        zrep = {}
        for z, d in zones.items():
            poi_on = n.links_t.p0[f'POI {z} online']
            poi_late = n.links_t.p0[f'POI {z} late'] if f'POI {z} late' in n.links_t.p0 else poi_on * 0
            ptr_fac = n.generators_t.p[d['train']]
            uns = n.generators_t.p[f"{d['dc']} unserved"]
            K = d['K_online']
            p_train_IT = ptr_fac / (pue * (1 - IDLE)) if K > 0 else ptr_fac * 0
            fac = d['fixed'] + ptr_fac
            day = n.snapshots.get_level_values(1).normalize()
            daily = (ptr_fac * sw).groupby(day).sum()
            zrep[z] = dict(K_online_IT_MW=K, K_late_IT_MW=d['K_late'],
                           facility_TWh=float((fac * sw).sum() / 1e6), served_TWh=float((poi_on * sw).sum() / 1e6),
                           unserved_TWh=float((uns * sw).sum() / 1e6), late_poi_max_MW=float(poi_late.abs().max()),
                           peak_facility_MW=float(fac.max()), poi_peak_MW=float(poi_on.max()),
                           train_daily_resid_MWh=float((daily - TRAIN[d['train']]).abs().max()) if K > 0 else 0.0,
                           train_daily_target_MWh=float(TRAIN[d['train']]),
                           IT_headroom_resid_MW=float((d['p_inf'] + p_train_IT - K).clip(lower=0).max()),
                           dc_balance_resid_MW=float((poi_on + poi_late + uns - fac).abs().max()),
                           implied_facility_CF=float((fac * sw).sum() / (pue * K * 8760)) if K > 0 else None)
        summ[tag] = dict(zones=zrep, **w2.summarize(n))
        summ[tag]['lmp_mean'] = n.buses_t.marginal_price[w2.ZONES].mean().round(2).to_dict()
        ep = n.buses_t.get('erm_price')
        summ[tag]['erm_price_sum_by_zone'] = ep.astype(float).sum().round(2).reindex(w2.ZONES).to_dict() if ep is not None else None
        wl[tag] = dict(lead_years=L, requested_IT_by_2030=float(c[c.request_year <= YEAR].IT_MW.sum()), online_IT_2030=float(on.sum()), backlog_IT_2030=float(c[(c.request_year <= YEAR) & (cod > YEAR)].IT_MW.sum()), it_online=on.to_dict(), it_late=late.to_dict(), conserved_vs_cohorts=float(abs(on.sum() + late.sum() - c.IT_MW.sum())))
        logger.info(f'{tag}: {results[tag]}')

    s0 = json.loads((WP / 'outputs/wp2_ercot8s/wp2_results.json').read_text())
    o0 = s0['results']['S0']['objective']; g0 = s0['summaries']['S0']
    tests = {}
    for tag in results:
        Z = summ[tag]['zones']
        tests[tag] = dict(
            solver_ok=results[tag]['termination'] == 'optimal', true_LP=results[tag]['integer_vars'] == 0,
            cohort_mass_conserved=wl[tag]['conserved_vs_cohorts'] < 1e-6,
            late_cohorts_no_service=max(z['late_poi_max_MW'] for z in Z.values()) < 1e-6,
            # tolerance matches Gurobi FeasibilityTol 1e-3 on the 8-term daily row (barrier, no crossover)
            training_daily_energy_conserved=all(z['train_daily_resid_MWh'] <= 1e-4 * z['train_daily_target_MWh'] + 1e-2 for z in Z.values()),
            IT_headroom_respected=max(z['IT_headroom_resid_MW'] for z in Z.values()) < 1e-6,
            dc_balance=max(z['dc_balance_resid_MW'] for z in Z.values()) < 1e-3,
            erm_poi_coeff=results[tag]['erm_poi_coeff_snapshot0'])
        tests[tag]['pass_'] = all(v for k, v in tests[tag].items() if k != 'erm_poi_coeff') and abs(tests[tag]['erm_poi_coeff'] + 1.15) < 1e-9
        summ[tag]['delta_vs_S0'] = dict(objective_USD=results[tag]['objective'] - o0,
                                        public_new_MW={k: round(v - g0['public_new_MW'].get(k, 0), 2) for k, v in summ[tag]['public_new_MW'].items() if abs(v - g0['public_new_MW'].get(k, 0)) > 1e-3},
                                        gen_TWh={k: round(v - g0['gen_TWh'].get(k, 0), 3) for k, v in summ[tag]['gen_TWh'].items() if abs(v - g0['gen_TWh'].get(k, 0)) > 1e-3})
    allpass = all(t['pass_'] for t in tests.values())
    res = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), status='S1_REAL_COHORTS_PASS' if allpass else 'S1_REAL_FAIL',
               timing_assumption=f'LEAD-01 approved: POI COD = requested_year + L, L in {a.leads}', pue_TX_2030=pue, task_params_2030=par,
               idle_fraction=IDLE, cohorts_sha256=w2.sha(COHORTS), prepared_sha256=w2.sha(w2.PREP), results=results, tests=tests,
               summaries=summ, workload=wl, backlog_USD_per_MWh=w2.BACKLOG_USD_PER_MWH)
    (out / 's1_real_results.json').write_text(json.dumps(res, indent=2, default=str))
    rows = []
    for tag, sm in summ.items():
        for z, d in sm['zones'].items():
            rows.append(dict(scenario=tag, region_id=z, **d))
    pd.DataFrame(rows).to_csv(out / 'served_compute_by_zone.csv', index=False)
    pd.DataFrame([dict(scenario=t, **summ[t]['delta_vs_S0']['public_new_MW']) for t in summ]).to_csv(out / 'public_builds_delta_vs_S0.csv', index=False)
    print(json.dumps(dict(status=res['status'], tests=tests,
                          summary={t: dict(objective=results[t]['objective'], delta_obj=summ[t]['delta_vs_S0']['objective_USD'],
                                           new_MW=summ[t]['delta_vs_S0']['public_new_MW'],
                                           zones={z: {k: round(v, 4) if isinstance(v, float) else v for k, v in d.items() if k in ('K_online_IT_MW', 'facility_TWh', 'served_TWh', 'unserved_TWh', 'implied_facility_CF')} for z, d in summ[t]['zones'].items()})
                                   for t in summ}), indent=1, default=str))


if __name__ == '__main__':
    main()
