#!/usr/bin/env python3
"""v2.4.0 annual approve-and-commit controller 2026-2035 + state advance 2036-2039 + milestones 2040/2045/2050 (E02/E06).

Derived from work_package_v2/tools/m3_annual_controller.py (v2.3.0) on top of v240_mech (repaired cost basis,
fractional first-year COD). Run from pypsa-usa/workflow:
    python byop/model/v240_path.py --scenario S3 --window 5 --out <dir>

Decision year t: window t..t+W-1 (annual, 13 sampled weeks), immutable ledger of earlier commitments enters as fixed
assets (sunk capex not in the marginal objective), only year-t decisions are committed:
  public generator/storage with COD == t + lead, line pairs with COD == t + line_lead, BYOP with COD == t + lead
  (fractional lead allowed: SOFC 0.5 y -> COD t+0.5, partial first year). Committed assets whose COD lies beyond
  the window are carried in the ledger and come online at COD in later windows / the replay.
W=5 has no candidate with COD > t+4 (CCGT utility lead 5 is never offered: the v2.3.0 truncation); W=7 offers it.
After 2035: replay 2036-2039 (ledger fixed, no new commitments, no new Study-New requests) and milestone LP
2040/2045/2050 (5 years each, ledger fixed, public re-expansion allowed with COD rules, no new BYOP).
Outputs: ledger.json/csv, service.csv, path_costs.csv, asset_status.csv, milestone_*.csv, events.jsonl
"""
from __future__ import annotations

import argparse, json, logging, math, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v240_mech as m  # noqa: E402

FIRST, LAST = 2026, 2035
logger = logging.getLogger('v240_path')


def set_window(t, length):
    m.CFG.update(period_list=list(range(t, t + length)), period_years={}, decision_year=t, periods='annual')


def add_ledger(n, ledger):
    for a in ledger:
        if a['type'] == 'Generator':
            if a['bus'] not in n.buses.index:
                continue
            n.add('Generator', a['name'], bus=a['bus'], carrier=a['carrier'], p_nom=a['MW'], p_nom_extendable=False,
                  capital_cost=a['capital_cost'], marginal_cost=a['marginal_cost'], efficiency=a.get('efficiency', 1.0),
                  build_year=a['build_period'], lifetime=a['lifetime'])
            if a['carrier'].startswith('byop_'):
                ppu = pd.Series(0.0, index=n.snapshots)
                for q in m.periods():
                    ppu.loc[q] = m.avail_frac(a['build_period'], a['COD'], q) / a['r'] if q >= a['build_period'] else 0.0
                n.generators_t.p_max_pu[a['name']] = ppu.values
                m.STATE.setdefault('byop_cod', {})[a['name']] = dict(cod=a['COD'], build=a['build_period'], r=a['r'],
                                                                     carrier=a['carrier'][5:], zone=a['bus'][3:])
            else:
                src = a.get('profile_from')
                cand = [c for c in n.generators_t.p_max_pu.columns if src and c.startswith(src)]
                if cand:
                    n.generators_t.p_max_pu[a['name']] = n.generators_t.p_max_pu[cand[0]].values
                else:
                    n.generators.loc[a['name'], 'p_max_pu'] = a.get('p_max_pu_const', 1.0)
        elif a['type'] == 'StorageUnit':
            n.add('StorageUnit', a['name'], bus=a['bus'], carrier=a['carrier'], p_nom=a['MW'], p_nom_extendable=False,
                  capital_cost=a['capital_cost'], max_hours=a['max_hours'], efficiency_store=a['eff_store'],
                  efficiency_dispatch=a['eff_dispatch'], cyclic_state_of_charge=True, build_year=a['build_period'],
                  lifetime=a['lifetime'], marginal_cost=a['marginal_cost'])
        elif a['type'] == 'LinkPair':
            for suf, b0, b1 in [('fwd', a['bus0'], a['bus1']), ('rev', a['bus1'], a['bus0'])]:
                n.add('Link', f"{a['name']}_{suf}", bus0=b0, bus1=b1, carrier='AC_committed', p_nom=a['MW'],
                      p_nom_extendable=False, capital_cost=a['capital_cost'] if suf == 'fwd' else 0.0,
                      efficiency=a['efficiency'], build_year=a['build_period'], lifetime=a['lifetime'])
    if 'AC_committed' not in n.carriers.index:
        n.add('Carrier', 'AC_committed', co2_emissions=0.0)
    used = {}
    for a in ledger:
        if a['type'] == 'LinkPair':
            used[a['corridor']] = used.get(a['corridor'], 0.0) + a['MW']
    for c in (m.STATE.get('corridors', []) if len(n.links) else []):
        left = max(c['cap_MW'] - used.get(c['corridor'], 0.0), 0.0)
        c['cap_MW'] = left
        for name in n.links.index[n.links.index.str.startswith(c['corridor'] + '_exp')]:
            n.links.loc[name, 'p_nom_max'] = left


def commits_from(n, t, scen, scope):
    tech = m.tech().set_index(['carrier', 'boundary'])
    out = []
    g, su, l = n.generators, n.storage_units, n.links
    pct = m.STATE.get('public_cost_table')
    pct = pct.set_index('name') if pct is not None and len(pct) else None
    if 'public' in scope:
        for car, (tc, comp) in m.PUBLIC.items():
            row = tech.loc[(tc, 'UTILITY' if comp == 'Generator' else 'UTILITY_AND_DC_BTM')]
            cod = t + float(row[f"lead_years_{m.CFG['public_case']}"])
            bp = m.first_period(cod)
            d = g if comp == 'Generator' else su
            sel = d[(d.carrier == car) & d.p_nom_extendable & (d.build_year == bp) & d.index.str.contains(' pub')] if bp else d.iloc[:0]
            for name, r in sel.iterrows():
                if r.p_nom_opt <= 0.5:
                    continue
                a = dict(scenario=scen, decision_year=t, type=comp, name=f'{name} c{t}', bus=r.bus, carrier=car,
                         MW=float(r.p_nom_opt), COD=cod, build_period=int(bp), lifetime=float(r.lifetime),
                         capital_cost=float(r.capital_cost), marginal_cost=float(r.marginal_cost), path='public',
                         cc_social=float(pct.cc_social[name]) if pct is not None and name in pct.index else float(r.capital_cost),
                         cc_private=float(pct.cc_market_sub[name]) if pct is not None and name in pct.index else float(r.capital_cost),
                         overnight=float(pct.overnight_per_MW[name]) if pct is not None and name in pct.index else None)
                if comp == 'Generator':
                    a.update(efficiency=float(r.efficiency))
                    if name in n.generators_t.p_max_pu:
                        a['profile_from'] = f"{r.bus} {car} pub"
                else:
                    a.update(max_hours=float(r.max_hours), eff_store=float(r.efficiency_store), eff_dispatch=float(r.efficiency_dispatch))
                out.append(a)
        lead_l = m.LINE_LEADS[m.CFG['public_case']]
        for name, r in l[(l.carrier == 'AC_exp') & (l.build_year == t + lead_l) & l.index.str.endswith('_fwd')].iterrows():
            if r.p_nom_opt <= 0.5:
                continue
            corridor = name.split('_exp')[0]
            out.append(dict(scenario=scen, decision_year=t, type='LinkPair', name=f'{corridor}_c{t}', corridor=corridor,
                            bus0=r.bus0, bus1=r.bus1, carrier='AC_exp', MW=float(r.p_nom_opt), COD=t + lead_l, build_period=t + lead_l,
                            lifetime=60.0, capital_cost=float(r.capital_cost), efficiency=float(r.efficiency), marginal_cost=0.0,
                            path='public', cc_social=float(r.capital_cost), cc_private=float(r.capital_cost), overnight=None))
    if 'byop' in scope:
        for name, r in g[g.carrier.str.startswith('byop_') & g.p_nom_extendable].iterrows():
            car = r.carrier[5:]
            bp_ = m.byop_params(car, 'social')
            cod = t + bp_['lead']
            if int(r.build_year) != m.first_period(cod) or r.p_nom_opt <= 0.5:
                continue
            out.append(dict(scenario=scen, decision_year=t, type='Generator', name=f'{name} c{t}', bus=r.bus,
                            carrier=r.carrier, MW=float(r.p_nom_opt), COD=cod, build_period=int(r.build_year),
                            lifetime=float(r.lifetime), capital_cost=float(r.capital_cost), marginal_cost=float(r.marginal_cost),
                            r=bp_['r'], path='N', cc_social=bp_['annual_social'], cc_private=bp_['annual_private'],
                            overnight=bp_['overnight_per_MW']))
    return out


def private_byop(config, s1_net, v, mult, ledger, t):
    """S2 developer stage inside the controller (same rules as v240_mech.private_stage) with ledger BYOP fixed."""
    dem = m.study_new_demand()
    sw = s1_net.snapshot_weightings.generators
    ow = pd.Series([float(s1_net.investment_period_weightings.objective[p]) for p in s1_net.snapshots.get_level_values(0)], index=s1_net.snapshots)
    erm_p = s1_net.buses_t.get('erm_price')
    nets = []
    for z in sorted(dem.zone.unique()):
        n = pypsa.Network()
        n.set_snapshots(s1_net.snapshots)
        n.investment_periods = m.periods()
        n.snapshot_weightings = s1_net.snapshot_weightings.copy()
        n.investment_period_weightings = s1_net.investment_period_weightings.copy()
        n.investment_period_weightings.loc[:, 'objective'] = [m.w_private(p) for p in m.periods()]
        lmp = s1_net.buses_t.marginal_price[z].astype(float)
        adder = pd.Series(0.0, index=s1_net.snapshots)
        if m.CFG['tariff'] == 'energy_erm' and erm_p is not None and z in erm_p:
            adder = (1 + m.w2.ERM_MARGIN) * erm_p[z].astype(float).fillna(0.0).abs() / (sw * ow)
        m.STATE['lmp_energy'] = {z: lmp}
        m.add_dc(n, dem[dem.zone == z], v, mult, byop=m.CFG['byop_techs'], price={z: lmp + adder}, actor='private')
        add_ledger(n, [a for a in ledger if a['type'] == 'Generator' and a['bus'] == f'DC_{z}' and a['carrier'].startswith('byop_')])
        m.STATE['erm'] = False
        sv = m.STATE.get('corridors'); m.STATE['corridors'] = []
        n.optimize(solver_name='gurobi', solver_options=dict(Method=2, Crossover=0, BarConvTol=1e-6, OutputFlag=0, Threads=m.CFG['threads']),
                   extra_functionality=m.extra, multi_investment_periods=True)
        m.STATE['corridors'] = sv; m.STATE['erm'] = True
        nets.append(n)
    return nets


def realised(n, t, scen, v, ledger):
    w = n.snapshot_weightings.generators
    sl = n.snapshots.get_level_values(0) == t
    g = n.generators
    svc = []
    for d in m.STATE.get('dc', []):
        if d['period'] != t:
            continue
        S = float(g.p_nom_opt[d['S']])
        byop_e = sum(float((n.generators_t.p[b][sl] * w[sl]).sum()) for b in g.index if g.carrier[b].startswith('byop_') and g.bus[b] == f"DC_{d['zone']}")
        poi = f"POI {d['zone']} {t}"; poinf = f"POInf {d['zone']} {t}"
        poi_e = sum(float((n.links_t.p0[x][sl] * w[sl]).sum()) for x in (poi, poinf) if x in n.links_t.p0)
        lmp = sum(float((n.links_t.p0[x][sl] * n.buses_t.marginal_price[d['zone']][sl] * w[sl]).sum()) for x in (poi, poinf) if x in n.links_t.p0)
        svc.append(dict(scenario=scen, year=t, zone=d['zone'], requested_MW_IT=d['D'], grid_ready_MW_IT=d['G'], served_MW_IT=S,
                        unserved_MW_IT=d['D'] - S, delay_loss_USD=v * (d['D'] - S) * m.years_p(t), poi_MWh=poi_e, byop_MWh=byop_e,
                        grid_payment_USD=lmp * m.years_p(t)))
    mc = n.get_switchable_as_dense('Generator', 'marginal_cost')
    ex = ~g.carrier.isin(['compute_IT', 'AIDC_training', 'load_shed'])
    ops = float((n.generators_t.p.loc[sl, g.index[ex]] * mc.loc[sl, g.index[ex]]).mul(w[sl], axis=0).sum().sum())
    shed = float(n.generators_t.p.loc[sl, [f'{z} load_shed' for z in m.ZONES]].multiply(w[sl], axis=0).sum().sum())
    act = [a for a in ledger if a['build_period'] <= t < a['build_period'] + a['lifetime']]
    status = []
    for a in ledger:
        st = 'operating' if (a['build_period'] <= t < a['build_period'] + a['lifetime']) else ('under_construction' if t < a['build_period'] else 'retired')
        nm = a['name'] if a['type'] != 'LinkPair' else f"{a['name']}_fwd"
        e = None
        if st == 'operating':
            if nm in n.generators_t.p:
                e = float((n.generators_t.p[nm][sl] * w[sl]).sum())
            elif nm in n.storage_units_t.p:
                e = float((n.storage_units_t.p[nm][sl].clip(lower=0) * w[sl]).sum())
            elif nm in n.links_t.p0:
                e = float((n.links_t.p0[nm][sl].abs() * w[sl]).sum())
        lmpv = None
        if e is not None and nm in n.generators_t.p and a['carrier'].startswith('byop_'):
            z = a['bus'][3:]
            lmpv = float((n.generators_t.p[nm][sl] * (n.buses_t.marginal_price[z][sl] - a['marginal_cost']) * w[sl]).sum())
        status.append(dict(scenario=scen, year=t, asset=a['name'], type=a['type'], carrier=a['carrier'], path=a.get('path'),
                           MW=a['MW'], decision_year=a['decision_year'], COD=a['COD'], status=st, energy_MWh=e,
                           cf=(e / (a['MW'] * 8760) if e is not None and a['MW'] > 0 else None),
                           energy_value_vs_LMP_USD=lmpv, years_represented=m.years_p(t)))
    cost = dict(scenario=scen, year=t, years_represented=m.years_p(t), operating_cost_USD=ops * m.years_p(t), load_shed_MWh=shed,
                ledger_capex_social_USD=sum(a['cc_social'] * a['MW'] for a in act) * m.years_p(t),
                ledger_capex_private_USD=sum(a['cc_private'] * a['MW'] for a in act) * m.years_p(t),
                byop_capex_social_USD=sum(a['cc_social'] * a['MW'] for a in act if a['carrier'].startswith('byop_')) * m.years_p(t),
                byop_capex_private_USD=sum(a['cc_private'] * a['MW'] for a in act if a['carrier'].startswith('byop_')) * m.years_p(t),
                delay_loss_USD=sum(s['delay_loss_USD'] for s in svc), served_MW_IT=sum(s['served_MW_IT'] for s in svc),
                requested_MW_IT=sum(s['requested_MW_IT'] for s in svc), grid_payment_USD=sum(s['grid_payment_USD'] for s in svc))
    cost['real_resource_cost_USD'] = cost['operating_cost_USD'] + cost['ledger_capex_social_USD'] + m.SHED_COST * shed * m.years_p(t)
    cost['social_total_USD'] = cost['real_resource_cost_USD'] + cost['delay_loss_USD']
    return svc, status, cost


def milestone_public_commits(n, scen, ledger):
    """public re-expansion chosen at the milestone LP (recorded, decision_year = 2036 bucket)"""
    out = []
    g, su = n.generators, n.storage_units
    for comp, d in [('Generator', g), ('StorageUnit', su)]:
        sel = d[d.p_nom_extendable & d.index.str.contains(' pub') & (d.p_nom_opt > 0.5)]
        for name, r in sel.iterrows():
            out.append(dict(scenario=scen, decision_year='milestone', type=comp, name=f'{name} ms', carrier=r.carrier,
                            MW=float(r.p_nom_opt), COD=int(r.build_year), build_period=int(r.build_year), lifetime=float(r.lifetime),
                            path='public_milestone', bus=r.bus))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario', required=True, choices=['S1', 'S2', 'S3'])
    ap.add_argument('--out', required=True); ap.add_argument('--window', type=int, default=5)
    ap.add_argument('--v', type=float, default=2.8e6); ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--last', type=int, default=LAST)
    ap.add_argument('--cost-basis', default='repaired', choices=['legacy', 'repaired'])
    ap.add_argument('--tariff', default='energy', choices=['energy', 'energy_erm'])
    ap.add_argument('--no-frac-cod', action='store_true')
    ap.add_argument('--erm-cal', required=True, help='annual ERM-02 B calibration (m3/erm02_calibration_annual.json)')
    ap.add_argument('--milestones', action='store_true', help='run replay 2036-2039 and milestones 2040/2045/2050')
    ap.add_argument('--cancel-share', type=float, default=0.0, help='ex-post cancellation share of cohorts requested >= 2031, from 2036')
    ap.add_argument('--milestones-only', action='store_true', help='reuse an existing ledger; only post-2035 stages')
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--tv-share-byop', type=float, default=1.0, help='E02 explicit residual-value share of out-of-window annuities for BYOP (1 = annuity-implied)')
    ap.add_argument('--tv-share-public', type=float, default=1.0, help='same for public candidates')
    ap.add_argument('--bg-traj', default=str(m.BG_TRAJ_DEFAULT), help="background annual load factor CSV; 'none' = hold 2025")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(out / 'controller.log', 'a', 'utf-8'), logging.StreamHandler()])
    run_id = f'v240path_{a.scenario}_W{a.window}_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    m.CFG.update(bg_traj=a.bg_traj, tv_share_byop=a.tv_share_byop, tv_share_public=a.tv_share_public, cost_basis=a.cost_basis, tariff=a.tariff, frac_cod=not a.no_frac_cod, threads=a.threads, v=a.v,
                 sample_weeks=None if a.smoke else 4, smoke=a.smoke, reuse='off')
    m.w2.PREP = str(m.BASE)
    m.w2.PUE = pd.read_csv(m.w2.PUE_CSV)
    config = pypsa.Network(m.BASE).meta
    cal = {int(k): float(x) for k, x in json.loads(Path(a.erm_cal).read_text())['margin_by_period'].items()}
    for y in range(max(cal) + 1, 2051):   # calibration covers 2026-2042; frozen background -> hold the last margin
        cal[y] = cal[max(k for k in cal if k <= 2042)]
    m.STATE['erm_cal'] = cal
    v = a.v
    lp = out / 'ledger.json'
    ledger = json.loads(lp.read_text()) if lp.exists() else []
    state = json.loads((out / 'state.json').read_text()) if (out / 'state.json').exists() else dict(done=[], SV=[], ST=[], CO=[])
    byop = m.CFG['byop_techs'] if a.scenario in ('S2', 'S3') else None

    def ev(event, year, status, msg, **kw):
        with open(out / 'events.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), run_id=run_id, event=event,
                                    scenario=a.scenario, window=a.window, year=year, status=status, message=msg, **kw),
                               ensure_ascii=False, default=str) + '\n')

    def save():
        lp.write_text(json.dumps(ledger, indent=1, default=str))
        (out / 'state.json').write_text(json.dumps(state, indent=1, default=str))

    def solve(n, tag):
        r = m.solve(config, tag, out, n)
        return r

    if not a.milestones_only:
        for t in range(FIRST, a.last + 1):
            if t in state['done']:
                continue
            t0 = time.time()
            set_window(t, a.window)
            if a.scenario in ('S1', 'S3'):
                n, mult = m.build(config, 'S', v, byop=byop)
                add_ledger(n, ledger)
                res = solve(n, f'{a.scenario}_t{t}')
                new = commits_from(n, t, a.scenario, ['public'] + (['byop'] if a.scenario == 'S3' else []))
            else:
                n1, mult = m.build(config, 'S', v, byop=None)
                add_ledger(n1, ledger)
                r1 = solve(n1, f'S2pre_t{t}')
                priv = private_byop(config, n1, v, mult, ledger, t)
                new_b = []
                for pn in priv:
                    new_b += commits_from(pn, t, 'S2', ['byop'])
                for x in new_b:   # developer financed: private annuity is what the developer pays
                    x['capital_cost'] = x['cc_private']
                set_window(t, a.window)
                n, mult = m.build(config, 'S', v, byop=None)
                add_ledger(n, ledger + new_b)
                res = solve(n, f'S2_t{t}')
                new = new_b + commits_from(n, t, 'S2', ['public'])
            ledger += new
            svc, status, cost = realised(n, t, a.scenario, v, ledger)
            cost.update(termination=res['termination'], integer_vars=res['integer_vars'], objective=res['objective'],
                        n_vars=res['n_vars'], seconds=round(time.time() - t0, 1), n_commits=len(new), committed_MW=sum(x['MW'] for x in new),
                        stage='controller')
            state['SV'] += svc; state['ST'] += status; state['CO'].append(cost); state['done'].append(t)
            save()
            ev('year_committed', t, 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL',
               f"{len(new)} commitments ({cost['committed_MW']:.0f} MW); served {cost['served_MW_IT']:.0f}/{cost['requested_MW_IT']:.0f} MW_IT",
               integer_vars=res['integer_vars'])
            logger.info(f'{a.scenario} t={t}: {cost}')
    if a.milestones:
        canc = dict(from_request_year=2031, share=a.cancel_share, effective_year=2036) if a.cancel_share > 0 else None
        m.CFG['cancel'] = canc
        tag = f"ms{'_cancel%02d' % int(100 * a.cancel_share) if canc else ''}"
        sd = out / tag; sd.mkdir(exist_ok=True)
        if not (sd / 'done').exists():
            # replay 2036-2039: ledger fixed, no new commitments of any kind
            set_window(2036, 4)
            n, mult = m.build(config, 'S', v, byop=None)
            add_ledger(n, ledger)
            for c, d in [('Generator', n.generators), ('StorageUnit', n.storage_units), ('Link', n.links)]:
                ext = d.index[d.p_nom_extendable & ~d.carrier.isin(['compute_IT', 'AIDC_training'])]
                d.loc[ext, 'p_nom_max'] = 0.0
            res = m.solve(config, f'{a.scenario}_{tag}_replay', sd, n)
            SV, ST, CO = [], [], []
            for y in range(2036, 2040):
                s_, st_, c_ = realised(n, y, a.scenario, v, ledger)
                c_.update(termination=res['termination'], integer_vars=res['integer_vars'], stage='replay_2036_2039')
                SV += s_; ST += st_; CO.append(c_)
            ev('replay_2036_2039', 2039, 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL', 'ledger fixed')
            # milestones: 2040 (2040-44), 2045 (2045-49), 2050 (2050) -> 2026-2050 covered once: ledger fixed, public re-expansion allowed, no new BYOP
            m.CFG.update(period_list=[2040, 2045, 2050], period_years={2040: 5, 2045: 5, 2050: 1}, decision_year=2036)
            n, mult = m.build(config, 'S', v, byop=None)
            add_ledger(n, ledger)
            res = m.solve(config, f'{a.scenario}_{tag}_milestones', sd, n)
            for y in [2040, 2045, 2050]:
                s_, st_, c_ = realised(n, y, a.scenario, v, ledger)
                c_.update(termination=res['termination'], integer_vars=res['integer_vars'], stage='milestone_5y')
                SV += s_; ST += st_; CO.append(c_)
            mpub = milestone_public_commits(n, a.scenario, ledger)
            ep = n.buses_t.get('erm_price')
            erm = []
            if ep is not None:
                for y in [2040, 2045, 2050]:
                    sl = n.snapshots.get_level_values(0) == y
                    for z in m.DC_ZONES:
                        if z in ep:
                            erm.append(dict(scenario=a.scenario, year=y, zone=z,
                                            erm_dual_USD_per_MW_yr=float(ep[z][sl].astype(float).fillna(0).abs().sum()) / m.w_social(y) * 1.0))
            pd.DataFrame(SV).to_csv(sd / 'service.csv', index=False); pd.DataFrame(ST).to_csv(sd / 'asset_status.csv', index=False)
            pd.DataFrame(CO).to_csv(sd / 'path_costs.csv', index=False); pd.DataFrame(mpub).to_csv(sd / 'milestone_public_builds.csv', index=False)
            pd.DataFrame(erm).to_csv(sd / 'milestone_erm_duals.csv', index=False)
            (sd / 'done').write_text(json.dumps(dict(cancel=canc, termination=res['termination'])))
            ev('milestones_2040_2045_2050', 2050, 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL', json.dumps(canc))
    pd.DataFrame(ledger).to_csv(out / 'ledger.csv', index=False)
    pd.DataFrame(state['SV']).to_csv(out / 'service.csv', index=False)
    pd.DataFrame(state['ST']).to_csv(out / 'asset_status.csv', index=False)
    pd.DataFrame(state['CO']).to_csv(out / 'path_costs.csv', index=False)
    ok = all(c.get('termination') == 'optimal' and c.get('integer_vars', 0) == 0 for c in state['CO'])
    (out / 'path_manifest.json').write_text(json.dumps(dict(run_id=run_id, scenario=a.scenario, window=a.window, cfg={k: v_ for k, v_ in m.CFG.items() if k != 'period_list'},
                                                           all_optimal_LP=ok, n_commitments=len(ledger), argv=sys.argv,
                                                           code_sha256={p.name: m.sha(p) for p in [Path(__file__), Path(m.__file__)]}), indent=2, default=str))
    print(json.dumps(dict(scenario=a.scenario, ok=ok, commitments=len(ledger)), indent=1))


if __name__ == '__main__':
    main()
