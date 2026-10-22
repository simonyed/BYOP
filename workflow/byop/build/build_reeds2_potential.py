#!/usr/bin/env python3
"""Mainline v1.3 WP-C: ERCOT onshore-wind / utility-PV new-build potential per TAMU 64s bus from the local ReEDS2 reV
supply curves (read only; the local ReEDS2 checkout is never copied or committed).

  supply curve   inputs/supply_curve/supplycurve_{wind-ons,upv}-reference.csv  (reV, reference siting; wind MW_AC,
                 UPV MW_DC -> MW_AC with ReEDS scalar ilr_utility = 1.34)
  site map       inputs/supply_curve/interconnection_land.h5 (sc_point_gid -> latitude, longitude, county FIPS)
  ERCOT filter   county in results/BYOP/baseline_2025_tamu/COUNTY_TO_BUS_SHARES.csv (the ERCOT county -> bus map of
                 the 2025 TAMU baseline); the site goes to the nearest TAMU 64s bus among that county's buses
  existing       BUS_LEDGER.csv (2025 fleet) + ercot_committed_pipeline_tamu.csv (committed 2026+) are subtracted:
                 remaining = max(0, ReEDS potential - existing - committed)  (no unlimited on-site wind / PV)
  profiles       NOT re-derived: the model keeps the PyPSA-USA hourly onwind / solar availability of each bus (the
                 2025 baseline weather year); ReEDS reV cf is reported per bus only as a cross-check
Outputs (small derived tables, tracked): inputs/grid/REEDS2_SOURCE_INVENTORY.csv, REEDS2_TO_TAMU64.csv,
ERCOT_WIND_SOLAR_POTENTIAL.csv. Run locally from pypsa-usa/workflow:
    python byop/build/build_reeds2_potential.py --reeds <ReEDS2 root>   (or env BYOP_REEDS2_ROOT)
"""
from __future__ import annotations

import argparse, hashlib, subprocess
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
import sys  # noqa: E402
sys.path.insert(0, str(HERE.parent / 'model'))
import byop_paths as BP  # noqa: E402
WF = HERE.parents[1]
OUT = HERE.parent / 'inputs/grid'
BASE = WF / 'results/BYOP/baseline_2025_tamu'
TECHS = {'wind-ons': 'onwind', 'upv': 'solar'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sitemap(path):
    with h5py.File(path, 'r') as f:
        g = f['data']
        df = pd.DataFrame({c: np.asarray(g[c]) for c in ['sc_point_gid', 'latitude', 'longitude', 'FIPS']})
    df['FIPS'] = df.FIPS.str.decode('utf-8').str.zfill(5)
    return df.set_index('sc_point_gid')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reeds', default=str(BP.REEDS2_ROOT) if BP.REEDS2_ROOT else None, required=BP.REEDS2_ROOT is None)
    a = ap.parse_args()
    R = Path(a.reeds)
    sc_dir = R / 'inputs/supply_curve'
    sm_path = sc_dir / 'interconnection_land.h5'
    scal = pd.read_csv(R / 'inputs/scalars.csv', header=None, index_col=0)
    ilr = float(scal.loc['ilr_utility', 1])
    try:
        ver = subprocess.run(['git', '-C', str(R), 'log', '-1', '--format=%H %cd'], capture_output=True, text=True).stdout.strip()
    except OSError:
        ver = 'UNKNOWN'
    sm = sitemap(sm_path)
    cty = pd.read_csv(BASE / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
    bl = pd.read_csv(BASE / 'BUS_LEDGER.csv', index_col=0)
    com = pd.read_csv(BASE / 'ercot_committed_pipeline_tamu.csv')
    inv, maps, rows = [], [], []
    for tech, car in TECHS.items():
        f = sc_dir / f'supplycurve_{tech}-reference.csv'
        inv.append(dict(file=str(f.relative_to(R)).replace('\\', '/'), reeds_commit=ver, sha256=sha(f), bytes=f.stat().st_size,
                        unit='MW_AC' if tech == 'wind-ons' else 'MW_DC (converted to MW_AC / ilr_utility)',
                        dollar_year='2022' if tech == 'wind-ons' else '2023', role=f'{car} new-build potential (reV reference siting)'))
        sc = pd.read_csv(f)
        sc = sc.join(sm, on='sc_point_gid')
        sc = sc[sc.FIPS.isin(set(cty.GEOID))].copy()
        sc['MW_AC'] = sc.capacity if tech == 'wind-ons' else sc.capacity / ilr
        bx = bl[['x', 'y']]
        cand = cty.groupby('GEOID').cluster_bus.apply(list).to_dict()
        def nearest(r):
            bs = cand[r.FIPS]
            d = ((bx.loc[bs, 'x'] - r.longitude) ** 2 + (bx.loc[bs, 'y'] - r.latitude) ** 2)
            return d.idxmin()
        sc['bus'] = sc.apply(nearest, axis=1)
        maps.append(sc.groupby(['bus', 'FIPS']).agg(n_sc_points=('sc_point_gid', 'size'), MW_AC=('MW_AC', 'sum'))
                    .reset_index().assign(technology=car, rule='county in ERCOT TAMU county map -> nearest TAMU bus of that county'))
        g = sc.groupby('bus').apply(lambda x: pd.Series(dict(
            reeds_potential_MW_AC=x.MW_AC.sum(), reeds_cf_capweighted=np.average(x.cf, weights=x.MW_AC),
            reeds_capital_adder_USD_per_MW=np.average(x.capital_adder_per_mw, weights=x.MW_AC), n_sc_points=len(x))), include_groups=False)
        ex = bl[f'MW_{car}'].reindex(g.index).fillna(0.0)
        cm = com[com.carrier == car].groupby('zone').MW.sum().reindex(g.index).fillna(0.0)
        g['existing_2025_MW'] = ex
        g['committed_2026plus_MW'] = cm
        g['remaining_new_MW_AC'] = (g.reeds_potential_MW_AC - ex - cm).clip(lower=0.0)
        g['technology'] = car
        rows.append(g.reset_index())
    pot = pd.concat(rows, ignore_index=True)
    pot['evidence_class'] = 'DERIVED'
    pot['source'] = f'ReEDS2 {ver} reV reference supply curve; existing/committed from 2025 TAMU baseline'
    pot['use_in_model'] = 'p_nom_max of public new-build + on-site BYOP at the bus share this cap (QA-SPACE)'
    inv.append(dict(file=str(sm_path.relative_to(R)).replace('\\', '/'), reeds_commit=ver, sha256=sha(sm_path), bytes=sm_path.stat().st_size,
                    unit='lat/lon/FIPS', dollar_year='', role='sc_point_gid site map'))
    inv.append(dict(file='inputs/scalars.csv', reeds_commit=ver, sha256=sha(R / 'inputs/scalars.csv'), bytes=(R / 'inputs/scalars.csv').stat().st_size,
                    unit=f'ilr_utility={ilr}', dollar_year='', role='UPV DC->AC'))
    for nm in ['cf_wind-ons_reference.h5', 'cf_upv_reference.h5']:
        inv.append(dict(file=f'inputs/profiles_cf/{nm}', reeds_commit=ver, sha256='NOT_HASHED_LARGE (md5 in remote_files.csv)', bytes=None,
                        unit='hourly cf 2007-2023', dollar_year='', role='NOT USED: PyPSA-USA bus profiles kept (weather-year consistency with the 2025 baseline load)'))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(inv).to_csv(OUT / 'REEDS2_SOURCE_INVENTORY.csv', index=False)
    pd.concat(maps, ignore_index=True).to_csv(OUT / 'REEDS2_TO_TAMU64.csv', index=False)
    pot.to_csv(OUT / 'ERCOT_WIND_SOLAR_POTENTIAL.csv', index=False)
    print(pot.pivot_table(index='bus', columns='technology', values='remaining_new_MW_AC').round(0).to_string())
    print(pot.groupby('technology')[['reeds_potential_MW_AC', 'existing_2025_MW', 'committed_2026plus_MW', 'remaining_new_MW_AC']].sum().round(0))


if __name__ == '__main__':
    main()
