#!/usr/bin/env python3
"""v2.5.0 D250-20: minimum ITL calibration that lets the 2025 fleet serve observed 2025 ERCOT load in every 3 h step.

Single-period dispatch LP on the county baseline (full year, 2,920 snapshots): only 2025-active non-extendable
generators/storage, 2025 load (no growth, no DC), existing county ITLs, plus one extendable uplift Link per existing
corridor direction priced at UPLIFT_COST (USD/MW) and load shedding at SHED_COST (USD/MWh). With
UPLIFT_COST / SHED_COST = 2 MWh per MW, uplift is chosen only where it avoids > ~2 MWh of shedding per MW, and since the
largest possible dispatch saving (< 1e6 USD/MW-yr) is below UPLIFT_COST it is never bought for economics.
Output: ITL_2025_CALIBRATION_LP.csv (corridor direction, added MW) -> read by build_2025_baseline_county.py.
    python calibrate_itl_lp.py <baseline nc> <out csv> [threads]
"""
import sys

import numpy as np
import pandas as pd
import pypsa

UPLIFT_COST = 2e6
SHED_COST = 1e6


def main(nc, out, threads='4'):
    n = pypsa.Network(nc)
    g = n.generators
    n.remove('Generator', g.index[g.p_nom_extendable | (g.build_year > 2025)])
    s = n.storage_units
    n.remove('StorageUnit', s.index[s.p_nom_extendable | (s.build_year > 2025)])
    n.remove('Link', n.links.index[n.links.carrier != 'AC'])
    n.generators['lifetime'] = np.inf; n.storage_units['lifetime'] = np.inf; n.links['lifetime'] = np.inf
    n.generators['build_year'] = 0; n.storage_units['build_year'] = 0; n.links['build_year'] = 0
    if 'GlobalConstraint' in n.components.keys() and len(n.global_constraints):
        n.remove('GlobalConstraint', n.global_constraints.index)
    for c in ['load_shed', 'AC_uplift']:
        if c not in n.carriers.index:
            n.add('Carrier', c)
    buses = sorted(set(n.loads.bus))
    n.add('Generator', [f'{b} shed' for b in buses], bus=buses, carrier='load_shed', p_nom=1e5, marginal_cost=SHED_COST)
    ac = n.links[n.links.carrier == 'AC']
    n.add('Link', [f'{l} uplift' for l in ac.index], bus0=ac.bus0.values, bus1=ac.bus1.values, carrier='AC_uplift',
          p_nom_extendable=True, capital_cost=UPLIFT_COST, efficiency=ac.efficiency.values)
    n.optimize(solver_name='gurobi', solver_options=dict(Method=2, Crossover=0, Threads=int(threads), BarConvTol=1e-7, NumericFocus=1))
    up = n.links.p_nom_opt[n.links.carrier == 'AC_uplift']
    shed = n.generators_t.p[[f'{b} shed' for b in buses]].mul(n.snapshot_weightings.generators, axis=0).sum()
    r = pd.DataFrame({'link': [x[:-7] for x in up.index], 'added_MW': up.values})
    r = r[r.added_MW > 0.5]
    r['corridor'] = r.link.str.replace(r'_(fwd|rev)$', '', regex=True)
    r['direction'] = r.link.str[-3:]
    r['bus0'] = r.link.map(n.links.bus0); r['bus1'] = r.link.map(n.links.bus1)
    r['existing_MW'] = r.link.map(n.links.p_nom)
    r['evidence_level'] = 'B'; r['derivation'] = 'B2025_CALIBRATION_LP (min uplift, full-year 2025 dispatch)'
    r.to_csv(out, index=False)
    print(f'termination {n.model.termination_condition}; uplift rows {len(r)}, total {r.added_MW.sum():.1f} MW; '
          f'remaining shed {shed.sum():.1f} MWh')
    print(r.sort_values('added_MW', ascending=False).head(25).to_string())


if __name__ == '__main__':
    main(*sys.argv[1:])
