#!/usr/bin/env python3
"""v2.5.0 CNY-03 diagnostic: per county, 2025 peak load vs local dispatchable capacity + county-ITL import capability
(NARIS directional MW into the county). Screening only (no optimisation, no N-1 beyond what NARIS already embeds):
explains why the upstream nodal ERM cannot be met county by county and where DC counties stand.

    python county_deliverability_diag.py <baseline_2025_county_prepared.nc> <out.csv>
"""
import sys

import pandas as pd
import pypsa

FIRM = ['CCGT', 'OCGT', 'gas_steam', 'coal', 'nuclear', 'biomass', 'hydro']
DC = {'p48029': 'Bexar', 'p48113': 'Dallas', 'p48121': 'Denton', 'p48453': 'Travis'}


def main(nc, out):
    n = pypsa.Network(nc)
    g = n.generators[~n.generators.p_nom_extendable]
    s = n.storage_units[~n.storage_units.p_nom_extendable]
    peak = n.loads_t.p_set.T.groupby(n.loads.bus).sum().T.max()
    firm = g[g.carrier.isin(FIRM) & (g.build_year <= 2025)].groupby('bus').p_nom.sum()
    batt = s[s.build_year <= 2025].groupby('bus').p_nom.sum()
    ac = n.links[n.links.carrier == 'AC']
    imp = ac.groupby('bus1').p_nom.sum()          # directional capability into bus1
    exp_ = ac.groupby('bus0').p_nom.sum()
    df = pd.DataFrame({'peak_load_MW_3h': peak}).fillna(0.0)
    df['firm_thermal_MW_2025'] = firm.reindex(df.index).fillna(0.0)
    df['battery_MW_2025'] = batt.reindex(df.index).fillna(0.0)
    df['itl_import_MW'] = imp.reindex(df.index).fillna(0.0)
    df['itl_export_MW'] = exp_.reindex(df.index).fillna(0.0)
    df['n_corridors'] = ac.groupby('bus1').size().reindex(df.index).fillna(0).astype(int)
    df['local_plus_import_MW'] = df.firm_thermal_MW_2025 + df.battery_MW_2025 + df.itl_import_MW
    df['cover_ratio'] = df.local_plus_import_MW / df.peak_load_MW_3h.where(df.peak_load_MW_3h > 0)
    df['dc_county'] = df.index.map(DC)
    df = df.sort_values('cover_ratio')
    df.to_csv(out)
    print('counties with cover_ratio < 1.15:', int((df.cover_ratio < 1.15).sum()), 'of', int(df.cover_ratio.notna().sum()))
    print(df.head(12).round(2).to_string())
    print(df[df.dc_county.notna()].round(2).to_string())


if __name__ == '__main__':
    main(*sys.argv[1:])
