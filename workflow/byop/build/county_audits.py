#!/usr/bin/env python3
"""v2.5.0 doc sec.10.6 audit deliverables (no optimisation):
  COUNTY_BUS_INTERFACE_AUDIT.csv  corridor, fwd/rev MW (NARIS) after D250-16 calibration, cost, length, TPIT eligibility
  COUNTY_BASELINE_DIFF.csv        7-zone baseline vs county baseline aggregated to the parent reeds_zone (fleet by carrier, load)
  GRID_PIPELINE_BY_YEAR.csv       TPIT records by projected year x asset type x activation status (data/derived register)
Run on L2 from pypsa-usa/workflow with the venv: python byop/build/county_audits.py
"""
import sys
from pathlib import Path

import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
import byop_paths as BP  # noqa: E402
OUT = BP.BASE_COUNTY.parent


def main():
    nc = pypsa.Network(str(OUT / 'baseline_2025_county_prepared.nc'))
    z7 = pypsa.Network(str(BP.BASE_7ZONE))
    import v250_mech as V
    pairs = V.tpit_corridors()
    cal = pd.read_csv(OUT / 'ITL_2025_CALIBRATION_UPLIFT.csv')
    calc = cal.groupby('corridor').added_MW.sum()
    l = nc.links[nc.links.carrier == 'AC']
    rows = []
    for f, r in l[l.index.str.endswith('_fwd')].iterrows():
        base = f[:-4]; rv = nc.links.loc[base + '_rev'] if base + '_rev' in nc.links.index else None
        key = tuple(sorted([r.bus0, r.bus1]))
        rows.append(dict(corridor=base, bus0=r.bus0, bus1=r.bus1, fwd_MW=float(r.p_nom), rev_MW=float(rv.p_nom) if rv is not None else None,
                         calibration_uplift_MW=float(calc.get(base, 0.0)), capital_cost_USD_per_MW_yr=float(r.capital_cost),
                         length_km=float(r.length), tpit_eligible_G_R=key in pairs, tpit_projects='|'.join(pairs.get(key, [])),
                         source='ReEDS transmission_capacity_init_AC_county_NARIS2024 (+ D250-16 calibration)'))
    pd.DataFrame(rows).to_csv(OUT / 'COUNTY_BUS_INTERFACE_AUDIT.csv', index=False)
    zone = nc.buses.reeds_zone
    def fleet(n, zmap):
        g = n.generators[~n.generators.p_nom_extendable & (n.generators.build_year <= 2025)]
        s = n.storage_units[~n.storage_units.p_nom_extendable & (n.storage_units.build_year <= 2025)]
        a = pd.concat([g[['bus', 'carrier', 'p_nom']], s[['bus', 'carrier', 'p_nom']]])
        a = a[a.carrier.ne('load_shed')]
        a['zone'] = a.bus.map(zmap)
        return a.groupby(['zone', 'carrier']).p_nom.sum()
    f_c = fleet(nc, zone); f_7 = fleet(z7, lambda b: b)
    ld_c = nc.loads_t.p_set.T.groupby(nc.loads.bus.map(zone)).sum().T.mul(nc.snapshot_weightings.generators, axis=0).sum() / 1e6
    ld_7 = z7.loads_t.p_set.T.groupby(z7.loads.bus).sum().T.mul(z7.snapshot_weightings.generators, axis=0).sum() / 1e6
    d = pd.DataFrame({'zone7_MW': f_7, 'county_agg_MW': f_c}).fillna(0.0)
    d['diff_MW'] = d.county_agg_MW - d.zone7_MW
    d = d.reset_index()
    ld = pd.DataFrame({'zone': ld_7.index.union(ld_c.index)})
    ld['carrier'] = 'LOAD_TWh'; ld['zone7_MW'] = ld.zone.map(ld_7).fillna(0); ld['county_agg_MW'] = ld.zone.map(ld_c).fillna(0)
    ld['diff_MW'] = ld.county_agg_MW - ld.zone7_MW
    pd.concat([d, ld]).to_csv(OUT / 'COUNTY_BASELINE_DIFF.csv', index=False)
    reg = pd.read_csv(BP.INPUTS / 'grid/TPIT_2026-07-13_project_register_v250.csv')
    g = reg.groupby(['projected_in_service_year', 'source_category', 'asset_type', 'activation_status']).size().rename('records').reset_index()
    g.to_csv(OUT / 'GRID_PIPELINE_BY_YEAR.csv', index=False)
    print('fleet total diff MW', round(float(d.diff_MW.sum()), 1), '| load TWh', round(float(ld_c.sum()), 2), round(float(ld_7.sum()), 2))
    print(d[d.diff_MW.abs() > 1].groupby('zone').diff_MW.sum().round(1).to_dict())


if __name__ == '__main__':
    main()
