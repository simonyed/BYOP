#!/usr/bin/env python3
"""v2.5.0 P1 collector: case outputs -> doc sec.7.3 fields.

    python collect_p1.py <outputs/p1 dir>
Writes into <dir>/_collected/:
  P1_scenario_summary.csv      all cases x scenarios (social total, real resource cost, delay, served, load shed, status)
  P1_service_by_county.csv     served / requested IT by case, scenario, county, year (+ first_partial / full grid year)
  P1_delivery_years.csv        earliest_full_grid_year, first_partial_grid_year, first_byop_online_year per county
  P1_bottlenecks.csv           binding_bottleneck_class per case/scenario/county/year (serve-cap dual, ERM, corridor)
  P1_line_builds.csv           county-ITL reinforcement built (MW) by corridor / build year, with TPIT project ids
  P1_capex_split.csv           additional public vs BYOP capex (PV) per case/scenario, vs S0 / S1 of the same case
  P1_matched_service.csv       S3 vs S3_mS2 / S2 social-cost gaps at matched service
  P1_gas_use.csv               peak-day fuel of dedicated gas units (what a firm MDQ would have to cover)
  P1_checks.csv                case_manifest checks + gas-gate matrix status
"""
import json, sys
from pathlib import Path

import pandas as pd

NAMES = {'p48029': 'Bexar', 'p48113': 'Dallas', 'p48121': 'Denton', 'p48453': 'Travis'}


def first_year(df, col_ok):
    y = df.loc[col_ok, 'year']
    return int(y.min()) if len(y) else None


def main(root):
    root = Path(root); out = root / '_collected'; out.mkdir(exist_ok=True)
    S, V, B, L, C, G, K = [], [], [], [], [], [], []
    for case in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('_')):
        man_p = case / 'case_manifest.json'
        gce_p = case / 'gce_manifest.json'
        gce = json.loads(gce_p.read_text()) if gce_p.exists() else {}
        tag = dict(case=case.name, grid=gce.get('gce', {}).get('grid'), gas_gate=gce.get('gce', {}).get('gas_gate'),
                   s2_rule=gce.get('gce', {}).get('s2_rule'))
        if man_p.exists():
            man = json.loads(man_p.read_text())
            K.append(dict(**tag, status=man.get('status'), **{f'check_{k}': v for k, v in (man.get('checks') or {}).items()}))
        if (case / 'scenario_summary.csv').exists():
            s = pd.read_csv(case / 'scenario_summary.csv')
            for k, v in tag.items():
                s.insert(0, k, v)
            S.append(s)
        if (case / 'service.csv').exists():
            v = pd.read_csv(case / 'service.csv')
            for k, x in tag.items():
                v.insert(0, k, x)
            V.append(v)
        if (case / 'duals.csv').exists():
            d = pd.read_csv(case / 'duals.csv')
            for k, x in tag.items():
                d.insert(0, k, x)
            B.append(d)
        if (case / 'ledger.csv').exists():
            led = pd.read_csv(case / 'ledger.csv', low_memory=False)
            ln = led[led.carrier == 'AC_exp']
            if len(ln):
                cor = pd.read_csv(case / 'gce_corridors.csv') if (case / 'gce_corridors.csv').exists() else pd.DataFrame()
                g = ln.groupby(['scenario', 'asset_id', 'build_period']).capacity_MW.first().reset_index()
                g['corridor'] = g.asset_id.str.replace(r'_exp\d{4}_fwd$', '', regex=True)
                if len(cor):
                    g = g.merge(cor[['corridor', 'existing_MW', 'cap_MW', 'tpit_projects']], on='corridor', how='left')
                for k, x in tag.items():
                    g.insert(0, k, x)
                L.append(g)
            cap = led.groupby(['scenario', 'resource_path']).resource_capex_PV_USD.sum().unstack(fill_value=0.0)
            for scen, r in cap.iterrows():
                C.append(dict(**tag, scenario=scen, public_capex_PV=float(r.get('public', 0.0)),
                              byop_N_capex_PV=float(r.get('N', 0.0)), reuse_R_capex_PV=float(r.get('R', 0.0))))
        if (case / 'byop_gas_use.csv').exists():
            gu = pd.read_csv(case / 'byop_gas_use.csv')
            for k, x in tag.items():
                gu.insert(0, k, x)
            G.append(gu)
    cat = lambda xs: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame()
    S, V, B, L, G = cat(S), cat(V), cat(B), cat(L), cat(G)
    S.to_csv(out / 'P1_scenario_summary.csv', index=False)
    if len(V):
        V['county_name'] = V.zone.map(NAMES)
        V.to_csv(out / 'P1_service_by_county.csv', index=False)
        rows = []
        for (case, scen, z), d in V.groupby(['case', 'scenario', 'zone']):
            d = d.sort_values('year')
            full = d.served_MW_IT >= d.requested_MW_IT - 1e-3
            # "grid" years: served without dedicated energy; BYOP years: dedicated energy > 0
            rows.append(dict(case=case, scenario=scen, county=z, county_name=NAMES.get(z),
                             earliest_full_service_year=first_year(d, full & (d.requested_MW_IT > 0)),
                             first_partial_service_year=first_year(d, d.served_MW_IT > 1e-3),
                             earliest_full_grid_year=first_year(d, full & (d.byop_MWh_per_yr < 1.0) & (d.requested_MW_IT > 0)),
                             first_byop_online_year=first_year(d, d.byop_MWh_per_yr > 1.0),
                             served_MW_IT_year=float(d.served_MW_IT_year.sum()), delay_MW_IT_year=float(d.delay_MW_IT_year.sum()),
                             served_last_year_MW=float(d.served_MW_IT.iloc[-1]), requested_last_year_MW=float(d.requested_MW_IT.iloc[-1])))
        pd.DataFrame(rows).to_csv(out / 'P1_delivery_years.csv', index=False)
    if len(B):
        cls = []
        for (case, scen, y), d in B.groupby(['case', 'scenario', 'year']):
            erm = d[(d.constraint.str.startswith('ERM')) & (d.binding == True)]
            cong = d[(d.constraint == 'corridor_congestion') & (d.binding == True)]
            for r in d[d.constraint.str.startswith('serve_cap')].itertuples():
                c = []
                if r.binding:
                    c.append('POI_SERVICE_CAP(grid+BYOP)')
                    if len(erm):
                        c.append('ERM_RELIABILITY')
                    dc_cong = cong[cong.zone.str.contains(r.zone)] if len(cong) else cong
                    if len(dc_cong):
                        c.append(f'COUNTY_ITL({len(dc_cong)} corridors at DC county)')
                cls.append(dict(case=case, scenario=scen, year=y, county=r.zone, county_name=NAMES.get(r.zone),
                                serve_cap_dual_USD_per_MW_IT_yr=r.dual_USD_per_MW_IT_yr, binding=r.binding,
                                binding_bottleneck_class='|'.join(c) if c else 'NONE',
                                n_congested_corridors_system=len(cong), erm_binding_buses=len(erm)))
        pd.DataFrame(cls).to_csv(out / 'P1_bottlenecks.csv', index=False)
        B.to_csv(out / 'P1_duals_all.csv', index=False)
    if len(L):
        L.to_csv(out / 'P1_line_builds.csv', index=False)
    Cdf = pd.DataFrame(C)
    if len(Cdf) and len(S):
        Cdf = Cdf.merge(S[['case', 'scenario', 'social_total_USD', 'social_real_resource_cost_USD', 'served_MW_IT_year']],
                        on=['case', 'scenario'], how='left')
        for ref in ['S0', 'S1']:
            r = Cdf[Cdf.scenario == ref].set_index('case').public_capex_PV
            Cdf[f'additional_public_capex_vs_{ref}'] = Cdf.public_capex_PV - Cdf.case.map(r)
        Cdf.to_csv(out / 'P1_capex_split.csv', index=False)
    if len(S):
        ms = []
        for case, d in S.groupby('case'):
            d = d.set_index('scenario')
            for a, b in [('S2', 'S3_mS2'), ('S1', 'S3_mS1'), ('S2', 'S3')]:
                if a in d.index and b in d.index:
                    ms.append(dict(case=case, pair=f'{a} vs {b}', served_a=d.served_MW_IT_year[a], served_b=d.served_MW_IT_year[b],
                                   matched=abs(d.served_MW_IT_year[a] - d.served_MW_IT_year[b]) < 1e-3 * max(1, d.served_MW_IT_year[a]),
                                   real_resource_gap_USD=d.social_real_resource_cost_USD[a] - d.social_real_resource_cost_USD[b],
                                   social_total_gap_USD=d.social_total_USD[a] - d.social_total_USD[b]))
        pd.DataFrame(ms).to_csv(out / 'P1_matched_service.csv', index=False)
    if len(G):
        G = G[G.peak_day_MMBtu >= 1.0]   # drop solver-noise dispatch (< 1 MMBtu/day)
        G.to_csv(out / 'P1_gas_use.csv', index=False)
    shed = []   # buses whose marginal price hits the load-shed cost (1e4 USD/MWh) -> where load is shed (D250-20 label)
    for case in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('_')):
        for f in sorted(case.glob('prices_*.csv.gz')):
            pr = pd.read_csv(f, index_col=[0, 1])
            hit = (pr >= 9999).groupby(level=0).sum()
            for bus in hit.columns[hit.sum() > 0]:
                if bus.startswith('erm_'):
                    continue
                for yr, k in hit[bus].items():
                    if k:
                        shed.append(dict(case=case.name, scenario=f.name[7:-7], bus=bus, year=int(yr), shed_snapshots=int(k),
                                         snapshots_in_year=int((pr.index.get_level_values(0) == yr).sum())))
    pd.DataFrame(shed).to_csv(out / 'P1_shed_buses.csv', index=False)
    pd.DataFrame(K).to_csv(out / 'P1_checks.csv', index=False)
    print(f'collected {len(S)} scenario rows from {len(K)} cases -> {out}')
    if len(S):
        print(S[['case', 'scenario', 'social_total_USD', 'served_MW_IT_year', 'delay_MW_IT_year', 'load_shed_MWh',
                 'public_new_MW', 'byop_MW', 'termination']].to_string())


if __name__ == '__main__':
    main(sys.argv[1])
