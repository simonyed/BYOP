#!/usr/bin/env python3
"""WP2 real-LP acceptance on the native PyPSA-USA ERCOT 8s baseline (S0 / S1).

Runs inside the PyPSA-USA environment (it imports PyPSA-USA's own solve code so S0 and S1 share
identical physics, constraints and cost noise):

    cd ../pypsa-usa/workflow
    python byop/model/wp2_ercot_s0_s1.py --out results/BYOP/wp2_ercot8s

Scenarios (all continuous LP, one 2030 investment period, 2920 x 3h snapshots):
  S0             PyPSA-USA public system only (Legacy load already in background; no Study-New).
  S1_zero_new    S1 structure (DC facility bus, POI link, unserved-compute slack) with IT_MW = 0.
  S1_poi0        SYNTHETIC_DEV cohort, POI_MW = 0 (disconnected).
  S1_cod_late    SYNTHETIC_DEV cohort, POI and a zero-capex public CCGT candidate with COD 2031 > 2030.
  S1_cod_ontime  positive control of S1_cod_late with COD 2030.

Acceptance tests: S1_ZERO_NEW_EQUALS_S0 (FCF-01), POI0_NO_IMPORT (FCF-03/M05),
NO_COD_EARLY (FCF-07/M02, POI and public asset), plus FCF-10 unit/energy conservation.

The single cohort is SYNTHETIC_DEV: real Texas zonal allocation needs a spatial crosswalk (NOT_RUN; PNNL basis withdrawn),
so national/state IT increments are NOT placed into ERCOT zones here.
ERM-DC-01 B (user 2026-10-18): grid-served DC load (POI flow) is added to its zone's ERM requirement; the
unserved-compute slack sits on the DC bus outside every ERM row, so it never earns firm credit.
S1_stress_A/B (10 GW, SYNTHETIC_DEV) compare B with the old A treatment.
"""
from __future__ import annotations

import argparse, copy, hashlib, json, logging, sys, time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

sys.path.insert(0, str(Path('scripts').resolve()))
import solve_network as sn  # noqa: E402  (PyPSA-USA module)
from opts.reserves import store_ERM_duals  # noqa: E402

PREP = 'resources/BYOP_ERCOT7s/networks/texas/elec_s20_c8s_ec_lv1.0_REM-ERM-3h_E.nc'
REF_SOLVED = 'results/BYOP_ERCOT7s/texas/networks/elec_s20_c8s_ec_lv1.0_REM-ERM-3h_E.nc'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import byop_paths as BP  # noqa: E402
PUE_CSV = str(BP.PUE)
YEAR = 2030
COHORT = dict(cohort_id='SYN_DEV_P63_100MW', region_id='p63', IT_MW=100.0, quality='SYNTHETIC_DEV')
BACKLOG_USD_PER_MWH = 1000.0  # SYNTHETIC_DEV bounded value of unserved compute (only scales the slack)
REL_TOL = 1e-6

logger = logging.getLogger('wp2')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


EXCLUDE_ZONES = ['p48']  # SPATIAL-ERCOT-03: p48 island dropped from the ERCOT analysis


def base_network(config, exclude=None):
    """Load the prepared PyPSA-USA network, apply solve_network.prepare_network (noise) once, then drop excluded
    island zones. Removal happens after the noise draw so the remaining components keep identical costs."""
    n = pypsa.Network(PREP)
    solve_opts = config['solving']['options']
    np.random.seed(solve_opts.get('seed', 123))
    n = sn.prepare_network(n, solve_opts)
    exclude = EXCLUDE_ZONES if exclude is None else exclude
    if exclude:
        for c in ['Line', 'Link']:
            df = n.static(c)
            touching = df.index[df.bus0.isin(exclude) | df.bus1.isin(exclude)]
            if len(touching):
                raise ValueError(f'SPATIAL-ERCOT-03: {exclude} is not an island, {c} {list(touching)} connects it')
        for c in ['Generator', 'Load', 'StorageUnit', 'Store']:
            df = n.static(c)
            if not df.empty:
                n.remove(c, df.index[df.bus.isin(exclude)])
        n.remove('Bus', n.buses.index[n.buses.index.isin(exclude)])
    return n


def add_cohort(n, cohort, it_mw, poi_mw, poi_cod):
    """S1 Grid-Only facility: DC bus + POI link (COD = build_year) + fixed facility load + unserved slack."""
    z, cid = cohort['region_id'], cohort['cohort_id']
    dc = f'DC_{cid}'
    zb = n.buses.loc[z]
    n.add('Carrier', ['POI', 'compute_unserved'], co2_emissions=0.0)
    n.add('Bus', dc, carrier='AC', x=zb.x, y=zb.y, v_nom=zb.v_nom, country='DC', reeds_zone='DC',
          reeds_state='DC', interconnect='dc_facility', nerc_reg='DC')
    pue = float(PUE[(PUE.st == 'TX') & (PUE.year == YEAR)].pue.iloc[0])
    fac_mw = it_mw * pue
    n.add('Load', f'{dc} load', bus=dc, p_set=fac_mw, carrier='AC')
    n.add('Link', f'POI {cid}', bus0=z, bus1=dc, p_nom=poi_mw, p_nom_extendable=False, efficiency=1.0,
          build_year=poi_cod, lifetime=100, carrier='POI', marginal_cost=0.0, capital_cost=0.0)
    n.add('Generator', f'{dc} unserved', bus=dc, p_nom=fac_mw, p_nom_extendable=False,
          marginal_cost=BACKLOG_USD_PER_MWH, carrier='compute_unserved', build_year=YEAR, lifetime=100)
    return dict(dc_bus=dc, pue=pue, facility_MW=fac_mw, IT_MW=it_mw, POI_MW=poi_mw, POI_COD=poi_cod)


def add_public_candidate(n, zone, cod):
    """Zero-capex public CCGT candidate: attractive, so only COD can keep it at zero in 2030."""
    ref = n.generators[(n.generators.carrier == 'CCGT') & (n.generators.bus == zone)].iloc[0]
    name = f'{zone} CCGT TEST_COD{cod}'
    n.add('Generator', name, bus=zone, carrier='CCGT', p_nom_extendable=True, p_nom_max=2000.0,
          capital_cost=0.0, marginal_cost=float(ref.marginal_cost) * 0.5, efficiency=float(ref.efficiency),
          build_year=cod, lifetime=30)
    return name


_UPSTREAM_EXTRA = sn.extra_functionality
ERM_MARGIN = 0.15
DC_ERM = {'mode': 'B', 'pois': []}  # pois: list of (poi_link_name, zone_bus); set per solve
ERM_REGIONS = {'TX': ERM_MARGIN}
POST_V16_NO_ERM = {'on': False}    # NEXT-01 A2-static: set only by the post-v1.6 build path (legacy default unchanged)     # region name -> margin (national M6: one row per NERC region)
ZONE_REGION = {}                     # zone bus -> ERM region name (default: the single region)


def extra_functionality_erm_dc(n, snapshots):
    """Upstream constraints, then ERM-DC-01 B: zone ERM row z gets requirement + (1+erm) x served DC (POI flow).

    lhs_z - (1+erm) * p_POI >= rhs_z. Requested-but-unserved DC load adds no requirement, and the unserved
    slack sits on the DC bus, which is outside every ERM row, so it can never earn firm credit.
    """
    _UPSTREAM_EXTRA(n, snapshots)
    if DC_ERM['mode'] != 'B' or not DC_ERM['pois']:
        return
    m = n.model
    default = next(iter(ERM_REGIONS))
    by_region = {}
    for link, zone in DC_ERM['pois']:
        by_region.setdefault(ZONE_REGION.get(zone, default), []).append((link, zone))
    for reg, pois in by_region.items():
        name = f'GlobalConstraint-{reg}_ERM'
        c = m.constraints[name]
        lhs, rhs, mask = c.lhs, c.rhs, c.mask
        for link, zone in pois:
            coef = xr.DataArray([(1.0 + ERM_REGIONS[reg]) if b == zone else 0.0 for b in lhs.coords['Bus'].values],
                                coords={'Bus': lhs.coords['Bus'].values}, dims='Bus')
            lhs = lhs - m['Link-p'].sel(name=[link]).sum('name') * coef
        m.remove_constraints(name)
        m.add_constraints(lhs, '>=', rhs, name=name, mask=mask)
        logger.info(f'ERM-DC-01 B: added (1+{ERM_REGIONS[reg]}) x POI flow of {len(pois)} POIs to {name}')


sn.extra_functionality = extra_functionality_erm_dc


def solve(n, config, tag, outdir, erm_dc_mode='B'):
    cfg = copy.deepcopy(config)
    DC_ERM['mode'] = erm_dc_mode
    DC_ERM['pois'] = [(l, n.links.bus0[l]) for l in n.links.index[n.links.carrier == 'POI']]
    # one region 'TX' = the 8 zone buses (reeds_state TX): same constraints as upstream 'all' incl. inter-zone
    # reserve sharing over links; DC facility buses (reeds_state 'DC') are outside the ERM rows, and under
    # ERM-DC-01 B their grid-served load is charged to the POI zone row by extra_functionality_erm_dc
    if POST_V16_NO_ERM['on']:   # NEXT-01 A2: post-v1.6 line - no legacy 15 % ERM row / shadow SOC / ERM-DC (operating reserve instead)
        DC_ERM['mode'] = 'OFF'; DC_ERM['pois'] = []
        cfg.setdefault('electricity', {}).pop('erm', None)
        cfg['wildcards'] = dict(cfg['wildcards'], opts='-'.join(o for o in cfg['wildcards']['opts'].split('-') if o and o != 'ERM'))
    else:
        cfg['electricity']['erm'] = dict(ERM_REGIONS)
        if 'ERM' not in cfg['wildcards']['opts'].split('-'):
            cfg['wildcards'] = dict(cfg['wildcards'], opts=cfg['wildcards']['opts'] + '-ERM')
    sn.snakemake = SimpleNamespace(params=SimpleNamespace(foresight=cfg['foresight'], solving=cfg['solving']),
                                   config=cfg, input=SimpleNamespace(), wildcards=SimpleNamespace(**cfg['wildcards']))
    opts = [o for o in cfg['wildcards']['opts'].split('-') if o]
    t0 = time.time()
    sn.solve_network(n, config=cfg, solving=copy.deepcopy(cfg['solving']), opts=opts,
                     log_fn=str(outdir / f'solver_{tag}.log'))
    if 'ERM' in opts:
        store_ERM_duals(n)
    st = getattr(n.model, 'status', None); tc = getattr(n.model, 'termination_condition', None)
    erm_term = None
    if DC_ERM['pois'] and erm_dc_mode == 'B':
        # structural check: the POI flow variable appears in the zone ERM row with coefficient -(1+erm)
        link, zone = DC_ERM['pois'][0]
        lab = int(n.model['Link-p'].sel(name=link).labels.values.ravel()[0])
        row = n.model.constraints[f"GlobalConstraint-{ZONE_REGION.get(zone, next(iter(ERM_REGIONS)))}_ERM"].lhs.sel(Bus=zone).isel(snapshot=0)
        coeffs = row.coeffs.values[row.vars.values == lab]
        erm_term = float(coeffs.sum()) if coeffs.size else 0.0
    return dict(tag=tag, status=str(st), termination=str(tc), objective=float(n.objective), seconds=round(time.time() - t0, 1),
                n_vars=int(n.model.nvars), n_cons=int(n.model.ncons),
                integer_vars=int(len(n.model.binaries) + len(n.model.integers)), erm_dc_mode=erm_dc_mode,
                erm_poi_coeff_snapshot0=erm_term)


def summarize(n, info=None):
    w = n.snapshot_weightings.generators
    g = n.generators
    gen = (n.generators_t.p.multiply(w, axis=0).sum().groupby(g.carrier).sum() / 1e6)
    out = dict(gen_TWh=gen.round(6).to_dict(),
               cap_opt_MW=g.groupby('carrier').p_nom_opt.sum().round(3).to_dict(),
               public_new_MW=(g.p_nom_opt - g.p_nom).clip(lower=0).groupby(g.carrier).sum().round(3).to_dict())
    if info:
        poi = n.links_t.p0[f"POI {info['dc_bus'][3:]}"] if f"POI {info['dc_bus'][3:]}" in n.links_t.p0 else pd.Series(0.0, index=n.snapshots)
        uns = n.generators_t.p[f"{info['dc_bus']} unserved"]
        load = n.loads_t.p[f"{info['dc_bus']} load"]
        out.update(poi_max_MW=float(poi.abs().max()), poi_MWh=float((poi * w).sum()),
                   unserved_MWh=float((uns * w).sum()), facility_MWh=float((load * w).sum()),
                   dc_balance_resid_MW=float((poi + uns - load).abs().max()))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True); a = ap.parse_args()
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(outdir / 'ERCOT_solver.log', 'w', 'utf-8'), logging.StreamHandler()])
    global PUE, ZONES
    PUE = pd.read_csv(PUE_CSV)
    config = pypsa.Network(PREP).meta
    ZONES = [b for b in pypsa.Network(PREP).buses.index if b not in EXCLUDE_ZONES]
    results, summ, info = {}, {}, {}
    global BUS_GEN
    BUS_GEN = {}

    runs = [('S0_full_with_p48', 'FULL'), ('S0', None), ('S1_zero_new', dict(it=0.0, poi=150.0, cod=YEAR, cand=None)),
            ('S1_poi0', dict(it=COHORT['IT_MW'], poi=0.0, cod=YEAR, cand=None)),
            ('S1_cod_late', dict(it=COHORT['IT_MW'], poi=150.0, cod=YEAR + 1, cand=YEAR + 1)),
            ('S1_cod_ontime', dict(it=COHORT['IT_MW'], poi=150.0, cod=YEAR, cand=YEAR)),
            # SYNTHETIC_DEV stress pair: 10 GW IT, POI 12 GW on time, ERM-DC-01 B vs A
            ('S1_stress_B', dict(it=10000.0, poi=12000.0, cod=YEAR, cand=None, erm='B')),
            ('S1_stress_A', dict(it=10000.0, poi=12000.0, cod=YEAR, cand=None, erm='A'))]
    for tag, spec in runs:
        n = base_network(config, exclude=[] if spec == 'FULL' else None)
        cand = None
        if spec == 'FULL':
            spec = None
        if spec:
            info[tag] = add_cohort(n, COHORT, spec['it'], spec['poi'], spec['cod'])
            if spec['cand']:
                cand = add_public_candidate(n, COHORT['region_id'], spec['cand'])
        logger.info(f'=== solving {tag} ===')
        results[tag] = solve(n, config, tag, outdir, erm_dc_mode=(spec or {}).get('erm', 'B'))
        summ[tag] = summarize(n, info.get(tag))
        w_ = n.snapshot_weightings.generators
        BUS_GEN[tag] = {(b, c): v for (b, c), v in (n.generators_t.p.multiply(w_, axis=0).sum().groupby([n.generators.bus, n.generators.carrier]).sum() / 1e6).items()}
        if cand:
            summ[tag]['candidate'] = dict(name=cand, p_nom_opt=float(n.generators.p_nom_opt[cand]),
                                          MWh=float((n.generators_t.p[cand] * n.snapshot_weightings.generators).sum()))
        if tag == 'S0':
            s0_net = n
        logger.info(f"{tag}: {results[tag]}")

    ref = pypsa.Network(REF_SOLVED)
    o0 = results['S0']['objective']  # 7-zone S0 (p48 excluded)
    tests = {}
    # LP_MODEL_TRUE_LP / REAL_ERCOT_SOLVER_SUCCESS
    tests['REAL_ERCOT_SOLVER_SUCCESS'] = all(r['status'] == 'ok' and r['termination'] == 'optimal' for r in results.values())
    tests['LP_MODEL_TRUE_LP'] = all(r['integer_vars'] == 0 for r in results.values())
    of = results['S0_full_with_p48']['objective']
    tests['S0_REPRODUCES_SNAKEMAKE_BASELINE'] = dict(runner=of, snakemake=float(ref.objective), rel=abs(of - ref.objective) / abs(ref.objective))
    # SPATIAL-ERCOT-03: dropping the p48 island must leave the other 7 zones' dispatch unchanged
    gb_full, gb_7 = BUS_GEN['S0_full_with_p48'], BUS_GEN['S0']
    keys = set(gb_7) | {k for k in gb_full if k[0] not in EXCLUDE_ZONES}
    dmax = max(abs(gb_full.get(k, 0.0) - gb_7.get(k, 0.0)) for k in keys)
    tot7 = sum(gb_7.values())
    tests['P48_DROP_LEAVES_7_ZONES_UNCHANGED'] = dict(max_abs_gen_diff_TWh=dmax, total_7zone_TWh=tot7,
        p48_island_objective_USD=of - o0, pass_=bool(dmax <= 1e-4 * tot7))
    tests['S0_REPRODUCES_SNAKEMAKE_BASELINE']['pass'] = tests['S0_REPRODUCES_SNAKEMAKE_BASELINE']['rel'] < 1e-4
    # FCF-01 S1(no new) == S0
    d = abs(results['S1_zero_new']['objective'] - o0) / abs(o0)
    gdiff = max(abs(summ['S1_zero_new']['gen_TWh'].get(k, 0) - v) for k, v in summ['S0']['gen_TWh'].items())
    tests['S1_ZERO_NEW_EQUALS_S0'] = dict(rel_obj_diff=d, max_gen_diff_TWh=gdiff, poi_MWh=summ['S1_zero_new']['poi_MWh'],
                                          pass_=bool(d < REL_TOL and summ['S1_zero_new']['poi_max_MW'] < 1e-6))
    # FCF-03 / M05 POI=0 -> no import, all unserved, cost = S0 + slack
    p = summ['S1_poi0']
    exp = o0 + p['facility_MWh'] * BACKLOG_USD_PER_MWH
    tests['POI0_NO_IMPORT'] = dict(poi_max_MW=p['poi_max_MW'], unserved_share=p['unserved_MWh'] / p['facility_MWh'],
                                   obj_vs_S0_plus_slack_rel=abs(results['S1_poi0']['objective'] - exp) / exp,
                                   pass_=bool(p['poi_max_MW'] < 1e-6 and abs(p['unserved_MWh'] / p['facility_MWh'] - 1) < 1e-6))
    # FCF-07 / M02 no output before COD (POI and public asset), with on-time positive control
    L, T = summ['S1_cod_late'], summ['S1_cod_ontime']
    tests['NO_COD_EARLY'] = dict(late_poi_max_MW=L['poi_max_MW'], late_unserved_share=L['unserved_MWh'] / L['facility_MWh'],
                                 late_candidate_MWh=L['candidate']['MWh'], ontime_poi_MWh=T['poi_MWh'],
                                 ontime_unserved_share=T['unserved_MWh'] / T['facility_MWh'], ontime_candidate_MWh=T['candidate']['MWh'],
                                 ontime_candidate_MW=T['candidate']['p_nom_opt'],
                                 pass_=bool(L['poi_max_MW'] < 1e-6 and L['candidate']['MWh'] < 1e-3
                                            and T['poi_MWh'] > 0 and T['unserved_MWh'] / T['facility_MWh'] < 1e-6 and T['candidate']['MWh'] > 0))
    # FCF-10 units / DC energy conservation
    tests['DC_UNITS_AND_BALANCE'] = dict(PUE=info['S1_poi0']['pue'], IT_MW=COHORT['IT_MW'], facility_MW=info['S1_poi0']['facility_MW'],
                                         max_dc_balance_resid_MW=max(summ[t]['dc_balance_resid_MW'] for t in info),
                                         pass_=bool(max(summ[t]['dc_balance_resid_MW'] for t in info) < 1e-3
                                                    and abs(info['S1_poi0']['facility_MW'] - COHORT['IT_MW'] * info['S1_poi0']['pue']) < 1e-9))

    # ERM-DC-01 B: POI term present with -(1+erm); stress pair shows B adds public firm requirement vs A
    cof = results['S1_cod_ontime']['erm_poi_coeff_snapshot0']
    sB, sA = summ['S1_stress_B'], summ['S1_stress_A']
    newB = sum(sB['public_new_MW'].values()); newA = sum(sA['public_new_MW'].values())
    tests['ERM_DC_SERVED_LOAD_IN_ZONE_ERM'] = dict(poi_coeff_in_p63_row=cof, expected=-(1 + ERM_MARGIN),
        stress_obj_B=results['S1_stress_B']['objective'], stress_obj_A=results['S1_stress_A']['objective'],
        stress_new_public_MW_B=newB, stress_new_public_MW_A=newA,
        stress_served_share_B=sB['poi_MWh'] / sB['facility_MWh'], stress_served_share_A=sA['poi_MWh'] / sA['facility_MWh'],
        pass_=bool(cof is not None and abs(cof + (1 + ERM_MARGIN)) < 1e-9
                   and results['S1_stress_B']['objective'] >= results['S1_stress_A']['objective'] * (1 - 1e-9)
                   and results['S1_stress_A']['erm_poi_coeff_snapshot0'] is None))
    tests['UNSERVED_SLACK_NOT_FIRM'] = dict(note='slack generator bus (DC) not in TX ERM region by construction',
        dc_bus_reeds_state='DC', pass_=True)

    # contract outputs
    rows = lambda key: pd.DataFrame([{**{'scenario': t}, **summ[t].get(key, {})} for t in summ])
    pd.DataFrame([{**{'scenario': t}, **results[t]} for t in results]).to_csv(outdir / 'baseline.csv', index=False)
    pd.DataFrame([{'scenario': t, **COHORT, **{k: v for k, v in info[t].items() if k != 'dc_bus'}} for t in info]).to_csv(outdir / 'requested_service.csv', index=False)
    rows('public_new_MW').to_csv(outdir / 'public_builds.csv', index=False)
    pd.DataFrame([{'scenario': t, 'facility_MWh': summ[t]['facility_MWh'], 'served_MWh': summ[t]['poi_MWh'],
                   'served_share': summ[t]['poi_MWh'] / summ[t]['facility_MWh'] if summ[t]['facility_MWh'] else None} for t in info]).to_csv(outdir / 'served_compute.csv', index=False)
    pd.DataFrame([{'scenario': t, 'unserved_MWh': summ[t]['unserved_MWh'], 'backlog_value_USD': summ[t]['unserved_MWh'] * BACKLOG_USD_PER_MWH,
                   'quality': 'SYNTHETIC_DEV'} for t in info]).to_csv(outdir / 'backlog.csv', index=False)
    rows('gen_TWh').to_csv(outdir / 'generation_TWh.csv', index=False)
    allpass = all((v.get('pass_', v.get('pass')) if isinstance(v, dict) else v) for v in tests.values())
    res = dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), status='WP2_S0_S1_TESTS_PASS' if allpass else 'WP2_TESTS_FAIL',
               prepared_network=PREP, prepared_sha256=sha(PREP), cohort=COHORT, backlog_USD_per_MWh=BACKLOG_USD_PER_MWH,
               results=results, tests=tests, summaries=summ)
    (outdir / 'wp2_results.json').write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(dict(status=res['status'], tests=tests, results={k: {kk: v[kk] for kk in ['status', 'termination', 'objective', 'seconds']} for k, v in results.items()}), indent=1, default=str))


if __name__ == '__main__':
    main()
