#!/usr/bin/env python3
"""AIDC geospatial v1 audit tables (input side only, no solver):
    python byop/post/geo_dynamic_v1_tables.py [--out results/BYOP/mainline/AIDC_GEO_DYNAMIC_V1_AUDIT]

LEGACY_VS_DYNAMIC_BY_BUS.csv     scenario x bus: new research IT in 2026 / 2028 / 2031 / 2035 and cumulative 2026-2035, legacy vs dynamic
LEGACY_VS_DYNAMIC_SUMMARY.csv    scenario: buses with growth, top-3 share, research total, both variants
ATLAS_BASIS_SENSITIVITY.csv      eligible bus count / top-3 share for atlas count basis raw / explicit-dedup / clusters (input-side only)
P_VARIANT_SENSITIVITY.csv        the same for P = main (g0 25 % / g50 75 %), g0 only, g50 only, five-scenario mean
"""
from __future__ import annotations

import argparse, copy, importlib.util
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
WF = HERE.parents[1]
DC = WF / 'byop/inputs/dc'
spec = importlib.util.spec_from_file_location('bdsi', WF / 'byop/build/build_dynamic_siting_inputs.py')
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
YRS = [2026, 2028, 2031, 2035]


def summary(c, label):
    rows = []
    for sc, g in c.groupby('scenario'):
        t = g.groupby('region_id').IT_MW.sum().sort_values(ascending=False)
        rows.append(dict(variant=label, scenario=sc, buses_with_growth=int((t > 1e-6).sum()), research_total_IT_MW=float(t.sum()),
                         top3_share=float(t.head(3).sum() / t.sum()), top3_buses='; '.join(t.head(3).index)))
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(WF / 'results/BYOP/mainline/AIDC_GEO_DYNAMIC_V1_AUDIT'))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    old = pd.read_csv(DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv')
    new = pd.read_csv(DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv')
    rows = []
    for sc in ('low', 'mid', 'high'):
        o = old[old.scenario == sc].pivot_table(index='region_id', columns='request_year', values='IT_MW', aggfunc='sum')
        n = new[new.scenario == sc].pivot_table(index='region_id', columns='request_year', values='IT_MW', aggfunc='sum')
        for b in sorted(set(o.index) | set(n.index)):
            r = dict(scenario=sc, bus=b)
            for y in YRS:
                r[f'legacy_{y}'] = float(o.loc[b, y]) if b in o.index else 0.0
                r[f'dynamic_{y}'] = float(n.loc[b, y]) if b in n.index else 0.0
            r['legacy_cum_2026_2035'] = float(o.loc[b].sum()) if b in o.index else 0.0
            r['dynamic_cum_2026_2035'] = float(n.loc[b].sum()) if b in n.index else 0.0
            r['delta_cum'] = r['dynamic_cum_2026_2035'] - r['legacy_cum_2026_2035']
            r['legacy_cum_2026_2031'] = float(o.loc[b, [y for y in o.columns if y <= 2031]].sum()) if b in o.index else 0.0
            r['dynamic_cum_2026_2031'] = float(n.loc[b, [y for y in n.columns if y <= 2031]].sum()) if b in n.index else 0.0
            rows.append(r)
    pd.DataFrame(rows).to_csv(out / 'LEGACY_VS_DYNAMIC_BY_BUS.csv', index=False, lineterminator='\n', float_format='%.6f')
    pd.DataFrame(summary(old, 'epoch8_legacy') + summary(new, 'dynamic_pnnl_v1')).to_csv(out / 'LEGACY_VS_DYNAMIC_SUMMARY.csv', index=False,
                                                                                         lineterminator='\n', float_format='%.6f')
    cfg = B.load_cfg(DC / 'MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml')
    sens = []
    for basis in ('raw', 'explicit_dedup', 'noncrypto_clusters'):
        c = copy.deepcopy(cfg); c['atlas']['count_basis'] = basis
        r = B.build(c, write=False)
        m = r['cohorts'][r['cohorts'].scenario == 'mid'].groupby('region_id').IT_MW.sum().sort_values(ascending=False)
        sens.append(dict(atlas_count_basis=basis, eligible_buses=r['n_buses'], buses='; '.join(r['buses']), top3_share_mid=float(m.head(3).sum() / m.sum()),
                         main=basis == cfg['atlas']['count_basis']))
    pd.DataFrame(sens).to_csv(out / 'ATLAS_BASIS_SENSITIVITY.csv', index=False, lineterminator='\n', float_format='%.6f')
    pv = []
    for nm, mix in (('main_g0_25_g50_75', {0: 0.25, 50: 0.75}), ('g0_only', {0: 1.0}), ('g50_only', {50: 1.0}),
                    ('g5_equal', {0: 0.2, 25: 0.2, 50: 0.2, 75: 0.2, 100: 0.2})):
        c = copy.deepcopy(cfg); c['projected']['gravity_mix'] = mix
        r = B.build(c, write=False)
        m = r['cohorts'][r['cohorts'].scenario == 'mid'].groupby('region_id').IT_MW.sum().sort_values(ascending=False)
        pv.append(dict(P_variant=nm, eligible_buses=r['n_buses'], buses='; '.join(r['buses']), top3_share_mid=float(m.head(3).sum() / m.sum()),
                       main=nm == 'main_g0_25_g50_75'))
    pd.DataFrame(pv).to_csv(out / 'P_VARIANT_SENSITIVITY.csv', index=False, lineterminator='\n', float_format='%.6f')
    print(pd.DataFrame(sens).drop(columns='buses').to_string()); print(pd.DataFrame(pv).drop(columns='buses').to_string())


if __name__ == '__main__':
    main()
