#!/usr/bin/env python3
"""NEXT-07 W3.2 (read-only, NO optimizer): is the 2026 nightly Far West shortage of the two sampled weeks representative of the
whole 2026 weather year? Evidence without a solve:
  1  pocket native load {p610 4, p620 6, p620 7} (v1.6 baseline p_set x the documented 2026 growth 1.009327) at 3 h resolution
     over the full weather year: where the sampled weeks and the B7 stress days sit in its distribution (all hours / night)
  2  the deliverable pocket supply implied by the original S0 solution at its shed snapshots (served = load - shed; the pocket
     has no local generation or storage at night in 2026, NEXT-06 W1), and the full-year shed it would imply if that supply were
     the year-round limit (a RULE-BASED BOUND for three supply levels, not an LP; daytime local solar is not credited)
  3  ERCOT-wide native load percentile of the sampled weeks (weather representativeness of the sample itself)
Run on L2 (outside the gated checkout is fine): BYOP_WF=<.../pypsa-usa/workflow> python next07_w3_representativeness.py
Writes <WF>/results/BYOP/next07_s0_reserve_probe/W3_REPRESENTATIVENESS_*.csv / .json."""
from __future__ import annotations

import json, os
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(os.environ.get('BYOP_WF') or Path(__file__).resolve().parents[2])
SRC = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
BASE = WF / 'results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc'
SEG = WF / 'results/BYOP/post_v16_a2_static/_structural_merged/A2_SOC_SEGMENT_MAP_S0.csv'
OUT = WF / 'results/BYOP/next07_s0_reserve_probe'
POCKET = ['p610 4', 'p620 6', 'p620 7']
GROWTH_2026 = 1.009327
NIGHT = range(0, 10)            # snapshot start hours 00, 03, 06, 09 (the W1 shed window)


def main():
    import pypsa
    OUT.mkdir(parents=True, exist_ok=True)
    n = pypsa.Network(str(BASE))
    p = n.loads_t.p_set
    if isinstance(p.index, pd.MultiIndex):
        p = p.droplevel(0)
    bus = p.T.groupby(n.loads.bus).sum().T
    step = pd.Series(p.index).diff().dropna().median()
    load3 = bus.resample('3h').mean() if step < pd.Timedelta(hours=3) else bus
    pocket = load3[POCKET].sum(axis=1) * GROWTH_2026
    system = load3.sum(axis=1) * GROWTH_2026
    sm = pd.read_csv(SEG, parse_dates=['start', 'end'])
    sm26 = sm[sm.period == 2026]
    kind = pd.Series('NOT_SAMPLED', index=pocket.index)
    for r in sm26.itertuples():
        kind[(pocket.index >= r.start) & (pocket.index <= r.end)] = r.kind
    night = pd.Series(pocket.index.hour.isin(NIGHT), index=pocket.index)
    # 2 S0 served pocket load at the shed snapshots of 2026
    shed = pd.read_csv(SRC / 'S0_shed_by_snapshot_frozen.csv.gz', index_col=[0, 1], parse_dates=[1]).clip(lower=0.0)
    s26 = shed.loc[2026]
    cols = [c for c in s26.columns if any(c == f'{b} load_shed' or c == f'{b} inherited_ramp_unserved' for b in POCKET)]
    psh = s26[cols].sum(axis=1)
    ev = pd.DataFrame(dict(pocket_load_MW=pocket.reindex(psh.index), shed_MW=psh, kind=kind.reindex(psh.index), night=night.reindex(psh.index)))
    ev['served_MW'] = ev.pocket_load_MW - ev.shed_MW
    at = ev[ev.shed_MW > 1e-3]
    sw_night = ev[(ev.kind == 'SAMPLED_WEEK') & ev.night]
    levels = dict(served_min=float(at.served_MW.min()), served_median=float(at.served_MW.median()), served_max=float(at.served_MW.max()))
    bound_rows = []
    for lab, cap in levels.items():
        for scope, msk in (('night_only', night), ('all_snapshots', pd.Series(True, index=pocket.index))):
            d = (pocket[msk] - cap).clip(lower=0.0)
            bound_rows.append(dict(supply_level=lab, supply_MW=cap, scope=scope, snapshots_above=int((d > 1e-6).sum()),
                                   hours_above=3 * int((d > 1e-6).sum()), implied_shed_MWh_3h=float(d.sum() * 3.0),
                                   implied_shed_MWh_in_sampled_weeks_3h=float(d[kind[msk] == 'SAMPLED_WEEK'].sum() * 3.0)))
    bounds = pd.DataFrame(bound_rows)
    # 1 / 3 distribution and percentiles
    pct = lambda s, v: float((s < v).mean())
    pn = pocket[night]
    dist = []
    for k in ('SAMPLED_WEEK', 'B7_STRESS_ONLY', 'NOT_SAMPLED'):
        for scope, s in (('all', pocket), ('night', pn)):
            x = s[kind.reindex(s.index) == k]
            if len(x):
                dist.append(dict(segment_kind=k, scope=scope, snapshots=len(x), pocket_mean_MW=float(x.mean()), pocket_max_MW=float(x.max()),
                                 pocket_mean_percentile_in_year=pct(s, float(x.mean())), system_mean_MW=float(system.reindex(x.index).mean()),
                                 system_mean_percentile_in_year=pct(system, float(system.reindex(x.index).mean()))))
    dist = pd.DataFrame(dist)
    sampled_raw_MWh = float((ev[ev.kind == 'SAMPLED_WEEK'].shed_MW * 3.0).sum())
    ver = dict(work_package='BYOP_NEXT_07', step='W3.2', optimizer_calls=0, pocket=POCKET, growth_2026=GROWTH_2026, weather_year_index=str(pocket.index[0].year),
               full_year_snapshots=int(len(pocket)), pocket_load_2026_MW=dict(mean=float(pocket.mean()), max=float(pocket.max()), night_mean=float(pn.mean())),
               s0_shed_snapshots_pocket=int(len(at)), s0_served_at_shed_MW=levels, s0_pocket_load_at_shed_MW=[float(at.pocket_load_MW.min()), float(at.pocket_load_MW.max())],
               s0_sampled_week_pocket_raw_3h_shed_MWh=sampled_raw_MWh,
               s0_sampled_week_pocket_weighted_MWh=sampled_raw_MWh * 77.5714285714 / 3.0,
               sampled_week_night_snapshots=int(len(sw_night)), sampled_week_night_shed_share=float((sw_night.shed_MW > 1e-3).mean()) if len(sw_night) else None,
               bounds=bounds.to_dict('records'),
               reading=('If the night-time deliverable pocket supply seen at the S0 shed snapshots held all year, the implied 2026 shed is the '
                        'night_only rows (rule-based, no LP; local daytime solar not credited, so all_snapshots is an upper bound). The supply '
                        'level itself is endogenous to the S0 dispatch (reserve coupling, mesh flows) and varies by season - this bounds T, it does '
                        'not replace the full-year LP.'))
    bounds.to_csv(OUT / 'W3_REPRESENTATIVENESS_BOUNDS.csv', index=False)
    dist.to_csv(OUT / 'W3_REPRESENTATIVENESS_DISTRIBUTION.csv', index=False)
    ev.reset_index().to_csv(OUT / 'W3_REPRESENTATIVENESS_S0_POCKET_SNAPSHOTS.csv', index=False)
    pd.DataFrame(dict(pocket_load_2026_MW=pocket, system_load_2026_MW=system, segment_kind=kind, night=night)).to_csv(OUT / 'W3_POCKET_LOAD_FULL_YEAR_3H.csv.gz')
    (OUT / 'W3_REPRESENTATIVENESS.json').write_text(json.dumps(ver, indent=1, default=float), encoding='utf-8')
    print(json.dumps({k: v for k, v in ver.items() if k != 'reading'}, indent=1, default=float))
    print(dist.to_string())


if __name__ == '__main__':
    main()
