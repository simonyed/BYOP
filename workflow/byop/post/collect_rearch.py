#!/usr/bin/env python3
"""Collect rearchitecture case outputs (results/BYOP/rearch/<case>/) into the work-package deliverable tables.

    python byop/post/collect_rearch.py results/BYOP/rearch [--out results/BYOP/rearch/_collected]

Writes POI_DELIVERABILITY_LEDGER.csv (site x year x scenario incl. S1 delay attribution), DELAY_ATTRIBUTION.csv,
ASSET_COMMITMENT_LEDGER.csv (public / BYOP / POI upgrade / committed grid projects, N/R paths, COD, life, value),
SCENARIO_COMPARISON.csv (service, earliest full-service year, BYOP, public builds, costs, matched-service gaps),
GATE_CHECKS.csv (every manifest check per case) and figures (served trajectories, attribution).
"""
import argparse, json
from pathlib import Path

import numpy as np
import pandas as pd

ATTR_V1 = {'S1_xPOI': 'POI equipment', 'S1_xUP': 'upstream transmission', 'S1_xRA': 'system resource adequacy',
           'S1_xPROC': 'procedural/study'}
ATTR_V2 = {'S1E_xPOI': 'POI equipment', 'S1E_xUP': 'upstream transmission', 'S1E_xRA': 'system resource adequacy',
           'S1E_xPROC': 'procedural/study'}     # P0-2: attribution on the strict earliest base S1_EARLIEST
ATTR = dict(ATTR_V1)


def first_full(df):
    """first year in which the site's request of that year is fully served (>= 99 %), per scenario x site"""
    out = {}
    for (sc, s), g in df.groupby(['scenario', 'site']):
        g = g.sort_values('year')
        ok = g[(g.requested_IT_MW > 0) & (g.served_IT_MW >= 0.99 * g.requested_IT_MW)]
        gap = g[(g.requested_IT_MW > 0) & (g.served_IT_MW < 0.99 * g.requested_IT_MW)]
        last_gap = int(gap.year.max()) if len(gap) else None
        out[(sc, s)] = dict(first_full_service_year=int(ok.year.min()) if len(ok) else None,
                            full_service_from=(last_gap + 1) if last_gap is not None and last_gap < int(g.year.max()) else
                            (None if last_gap is not None else int(g[g.requested_IT_MW > 0].year.min())),
                            unserved_MW_IT_yr=float(g.unserved_IT_MW.sum()))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('--out', default=None)
    a = ap.parse_args()
    root = Path(a.root); out = Path(a.out) if a.out else root / '_collected'
    out.mkdir(parents=True, exist_ok=True)
    POI, ATT, ASSET, CMP, GATE = [], [], [], [], []
    for case in sorted(p for p in root.iterdir() if p.is_dir() and (p / 'case_manifest.json').exists()):
        man = json.loads((case / 'case_manifest.json').read_text())
        cid = man['case_id']
        for k, v in man['checks'].items():
            GATE.append(dict(case=cid, check=k, value=v, status=man['status']))
        for tag, r in man['solves'].items():
            GATE.append(dict(case=cid, check=f'solve_{tag}', value=r.get('termination'), seconds=r.get('seconds'),
                             n_vars=r.get('n_vars'), integer_vars=r.get('integer_vars')))
        summ = pd.read_csv(case / 'scenario_summary.csv')
        pl = pd.read_csv(case / 'poi_ledger.csv') if (case / 'poi_ledger.csv').stat().st_size > 2 else pd.DataFrame()
        led = pd.read_csv(case / 'ledger.csv') if (case / 'ledger.csv').stat().st_size > 2 else pd.DataFrame()
        grp = man.get('case_group', cid)
        if len(pl):
            pl.insert(0, 'case', cid); pl.insert(1, 'case_group', grp); pl.insert(2, 'setting', man['gcfg']['setting'])
            POI.append(pl)
        ff = first_full(pl) if len(pl) else {}
        # assets
        if len(led):
            g = led.groupby(['scenario', 'asset_id', 'component', 'carrier', 'asset_boundary', 'resource_path', 'zone', 'build_period'])
            agg = g.agg(capacity_MW=('capacity_MW', 'max'), first_year=('year', 'min'), last_year_in_window=('year', 'max'),
                        social_annuity_USD_per_MW_yr=('social_annuity_USD_per_MW_yr', 'first'),
                        private_annuity_USD_per_MW_yr=('private_annuity_USD_per_MW_yr', 'first'),
                        resource_capex_PV_USD=('resource_capex_PV_USD', 'sum'), private_capex_PV_USD=('private_capex_PV_USD', 'sum'),
                        mean_cf=('cf', 'mean')).reset_index()
            agg.insert(0, 'case', cid)
            cod = pd.read_csv(case / 'byop_cod.csv').set_index('byop_name') if (case / 'byop_cod.csv').stat().st_size > 2 else pd.DataFrame()
            agg['COD'] = [float(cod.cod[x]) if len(cod) and x in cod.index else (b if not str(c).startswith('byop_') else np.nan)
                          for x, b, c in zip(agg.asset_id, agg.build_period, agg.carrier)]
            agg['owner'] = np.where(agg.asset_boundary.str.startswith('DC_BTM'), 'data_center', 'public')
            agg['commit_year'] = man['cfg']['decision_year']
            agg['asset_status'] = 'model_decision (static multi-period LP; approve-and-commit controller not run)'
            agg['remaining_life_after_window_y'] = np.nan
            ASSET.append(agg)
        up = pd.read_csv(case / 'poi_upgrade_ledger.csv') if (case / 'poi_upgrade_ledger.csv').stat().st_size > 2 else pd.DataFrame()
        if len(up):
            u = up.groupby(['scenario', 'asset_id', 'zone', 'build_period', 'COD']).agg(capacity_MW=('capacity_MW', 'max'),
                                                                                       resource_capex_PV_USD=('resource_capex_PV_USD', 'sum'),
                                                                                       first_year=('year', 'min')).reset_index()
            u.insert(0, 'case', cid); u['component'] = 'Link'; u['carrier'] = 'POI_upgrade'; u['asset_boundary'] = 'UTILITY_POI'
            u['resource_path'] = 'public'; u['owner'] = 'public (TSP)'
            ASSET.append(u)
        gp = pd.read_csv(case / 'grid_projects.csv') if (case / 'grid_projects.csv').stat().st_size > 2 else pd.DataFrame()
        if len(gp):
            gp = gp.rename(columns={'project': 'asset_id', 'MW': 'capacity_MW', 'ISD': 'COD'})
            gp.insert(0, 'case', cid); gp['scenario'] = 'ALL'; gp['carrier'] = 'AC_committed'; gp['owner'] = 'public (TSP)'
            gp['resource_path'] = 'committed'
            ASSET.append(gp)
        for r in summ.itertuples():
            row = dict(case=cid, case_group=man.get('case_group', cid), setting=man['gcfg']['setting'], scenario=r.scenario, relax=getattr(r, 'relax', 'none'),
                       served_MW_IT_yr=r.served_MW_IT_year, unserved_MW_IT_yr=r.delay_MW_IT_year,
                       social_real_resource_cost_USD=r.social_real_resource_cost_USD,
                       public_resource_capex_PV_USD=r.public_resource_capex_PV_USD, byop_resource_capex_PV_USD=r.byop_resource_capex_PV_USD,
                       poi_upgrade_resource_capex_PV_USD=getattr(r, 'poi_upgrade_resource_capex_PV_USD', 0.0),
                       system_operating_PV_USD=r.system_operating_PV_USD, load_shed_MWh=r.load_shed_MWh,
                       private_total_USD=r.private_total_USD, public_new_MW=r.public_new_MW, byop_MW=r.byop_MW,
                       poi_upgrade_MW=getattr(r, 'poi_upgrade_MW', 0.0), curtailed_MWh=getattr(r, 'curtailed_MWh', 0.0),
                       termination=r.termination, solve_seconds=r.solve_seconds)
            for s in sorted({k[1] for k in ff}):
                f = ff.get((r.scenario, s), {})
                row[f'{s}_full_service_from'] = f.get('full_service_from')
                row[f'{s}_unserved_MW_IT_yr'] = f.get('unserved_MW_IT_yr')
            if len(led):
                L = led[(led.scenario == r.scenario) & (led.year == led.year.max())]
                row['line_expansion_MW_2031'] = float(L[L.carrier == 'AC_exp'].capacity_MW.sum())
                b = led[(led.scenario == r.scenario) & led.asset_boundary.isin(['DC_BTM', 'DC_BTM_R'])]
                row['byop_mean_cf'] = float((b.dispatch_MWh_per_yr.sum() / (b.capacity_MW * 8760).sum())) if len(b) and b.capacity_MW.sum() > 0 else None
            CMP.append(row)
        dm = case / 'S2_developer_modes.csv'
        if dm.exists() and dm.stat().st_size > 2:
            x = pd.read_csv(dm); x.insert(0, 'case', cid)
            x.to_csv(out / f'S2_MODES_{cid}.csv', index=False)
    poi = pd.concat(POI, ignore_index=True) if POI else pd.DataFrame()
    for grp, pg in (poi.groupby('case_group') if len(poi) else []):
        v2 = (pg.scenario == 'S1_EARLIEST').any()
        btag, ATTRg, xall_tag = ('S1_EARLIEST', ATTR_V2, 'S1E_xALL') if v2 else ('S1', ATTR_V1, 'S1_xALL')
        base = pg[pg.scenario == btag].drop_duplicates(['site', 'year']).set_index(['site', 'year'])
        if not len(base):
            continue
        for sc in ATTRg:
            x = pg[pg.scenario == sc].drop_duplicates(['site', 'year']).set_index(['site', 'year'])
            if len(x):
                m_ = (poi.case_group == grp) & (poi.scenario == btag)
                poi.loc[m_, f'gain_{sc}_MW_IT'] = (x.served_IT_MW - base.served_IT_MW).reindex(
                    pd.MultiIndex.from_frame(poi.loc[m_, ['site', 'year']])).values
        if not (pg.scenario == xall_tag).any():
            continue
        xall = pg[pg.scenario == xall_tag].drop_duplicates(['site', 'year']).set_index(['site', 'year'])
        for (s, y), r in base.iterrows():
            gains = {lab: float(pg[(pg.scenario == sc) & (pg.site == s) & (pg.year == y)].served_IT_MW.iloc[0] - r.served_IT_MW)
                     if ((pg.scenario == sc) & (pg.site == s) & (pg.year == y)).any() else np.nan for sc, lab in ATTRg.items()}
            tot = float(xall.served_IT_MW.get((s, y), np.nan) - r.served_IT_MW)
            row = dict(case_group=grp, base=btag, setting=r.setting, site=s, year=y, requested_IT_MW=r.requested_IT_MW,
                       S1_served_IT_MW=r.served_IT_MW, S1_unserved_IT_MW=r.unserved_IT_MW, gain_all_relaxed_MW_IT=tot, **gains)
            vals = [v for v in gains.values() if v == v]
            row['combined/uncertain'] = tot - sum(vals)
            row['unexplained_after_all_relaxed'] = float(r.requested_IT_MW - xall.served_IT_MW.get((s, y), np.nan))
            row['dominant_cause'] = (max(gains, key=lambda k: gains[k] if gains[k] == gains[k] else -1)
                                     if r.unserved_IT_MW > 0.5 and vals and max(vals) > 0.5 else
                                     ('combined/uncertain' if r.unserved_IT_MW > 0.5 else 'none (served)'))
            ATT.append(row)
    poi.to_csv(out / 'POI_DELIVERABILITY_LEDGER.csv', index=False)
    att = pd.DataFrame(ATT); att.to_csv(out / 'DELAY_ATTRIBUTION.csv', index=False)
    (pd.concat(ASSET, ignore_index=True) if ASSET else pd.DataFrame()).to_csv(out / 'ASSET_COMMITMENT_LEDGER.csv', index=False)
    cmp_ = pd.DataFrame(CMP)
    # matched-service and headline differences per case (social real resource cost)
    rows = []
    for cid, g in cmp_.groupby('case_group'):
        c = g.drop_duplicates('scenario').set_index('scenario')
        get = lambda s, k: float(c[k][s]) if s in c.index else np.nan
        s1 = 'S1_ECON' if 'S1_ECON' in c.index else 'S1'
        for a_, b_, lab in [(s1, 'S0', 'S1-S0 (AIDC impact)'), ('S2', s1, 'S2-S1 (BYOP impact)'), ('S2', 'S3', 'S2-S3 (actual service)'),
                            ('S2', 'S3_mS2', 'S2-S3 matched to S2 service'), (s1, 'S3_mS1', 'S1-S3 matched to S1 service'),
                            ('S1_EARLIEST', s1, 'S1_EARLIEST - S1_ECON (economic under-service)')]:
            rows.append(dict(case=cid, setting=g.setting.iloc[0], comparison=lab,
                             d_social_real_resource_cost_USD=get(a_, 'social_real_resource_cost_USD') - get(b_, 'social_real_resource_cost_USD'),
                             d_served_MW_IT_yr=get(a_, 'served_MW_IT_yr') - get(b_, 'served_MW_IT_yr'),
                             d_public_capex_PV_USD=get(a_, 'public_resource_capex_PV_USD') - get(b_, 'public_resource_capex_PV_USD'),
                             d_byop_capex_PV_USD=get(a_, 'byop_resource_capex_PV_USD') - get(b_, 'byop_resource_capex_PV_USD'),
                             d_line_expansion_MW=get(a_, 'line_expansion_MW_2031') - get(b_, 'line_expansion_MW_2031') if 'line_expansion_MW_2031' in c else np.nan))
    cmp_.to_csv(out / 'SCENARIO_COMPARISON.csv', index=False)
    pd.DataFrame(rows).to_csv(out / 'SCENARIO_DIFFERENCES.csv', index=False)
    pd.DataFrame(GATE).to_csv(out / 'GATE_CHECKS.csv', index=False)
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        if len(poi):
            cases = sorted(poi.case.unique()); sites = sorted(poi.site.unique())
            fig, axs = plt.subplots(len(cases), len(sites), figsize=(4 * len(sites), 2.8 * len(cases)), squeeze=False, sharey=True)
            for i, cid in enumerate(cases):
                for j, s in enumerate(sites):
                    ax = axs[i][j]
                    x = poi[(poi.case == cid) & (poi.site == s)]
                    for sc, st in [('S1', 'o-'), ('S2', 's-'), ('S3', '^--'), ('S1_xALL', ':')]:
                        y = x[x.scenario == sc].sort_values('year')
                        if len(y):
                            ax.plot(y.year, y.served_IT_MW, st, label=sc, ms=3)
                    r = x[x.scenario == 'S1'].sort_values('year')
                    ax.step(r.year, r.requested_IT_MW, 'k-', where='mid', lw=0.6, label='request')
                    ax.set_title(f'{cid} | {s}', fontsize=8)
            axs[0][0].legend(fontsize=6); fig.supylabel('served IT MW'); fig.tight_layout()
            fig.savefig(out / 'served_trajectories.png', dpi=150)
        if len(att):
            cols = list(ATTR.values()) + ['combined/uncertain']
            t = att.groupby(['case_group', 'site'])[cols].sum().clip(lower=0)
            ax = t.plot.bar(stacked=True, figsize=(10, 4)); ax.set_ylabel('S1 served gain when relaxed (MW_IT-yr)')
            plt.tight_layout(); plt.savefig(out / 'delay_attribution.png', dpi=150)
    except Exception as e:
        print('figures failed', e)
    print(cmp_.to_string(max_cols=20)[:6000])
    print(pd.DataFrame(rows).to_string())
    if len(att):
        print(att.groupby(['case_group', 'site'])[[*ATTR_V1.values(), 'combined/uncertain', 'S1_unserved_IT_MW']].sum().round(1).to_string())


if __name__ == '__main__':
    main()
