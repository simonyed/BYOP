#!/usr/bin/env python3
"""NEXT-07 follow-up (read-only, NO solver): why does the Far West pocket shed in S0 2026 but not in the v1.6 LP2 2025 check?
Compares, at the same weather hours (2030 calendar; S0 2026 shed snapshots), the LP2 solution (LP2_line_flow_p0, LP2_lines limits,
LP2_shed_by_bus) with the NEXT-07 reserve probe (identical 2026 Far West shed to the formal S0; flows, dispatch, links persisted):
  1  binding lines (loading >= 0.999 of each run's own limit) around the Far West at those hours
  2  the import cut of the shedding sub-pocket {p620 6, p620 7} = TL43 (p620 4 -> p620 6) + TL36 (p610 4 -> p620 7), and its load
  3  angle differences across the pocket loop from flow x reactance (DC power flow, x in ohm on a common 230 kV base)
  4  native load (baseline p_set; S0 x 1.009327 for 2026), LP2 vs S0 shed per bus
Run on L2 from workflow/ (or with BYOP_WF):  python byop/post/next07_w5_lp2_vs_s0_flows.py
Writes results/BYOP/next07_s0_reserve_probe/W5_*.csv / .json."""
from __future__ import annotations

import json, os
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(os.environ.get('BYOP_WF') or Path(__file__).resolve().parents[2])
B16 = WF / 'results/BYOP/baseline_2025_tamu_v16'
PROBE = WF / 'results/BYOP/next07_s0_reserve_probe'
ORIG = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
SUB = ['p620 6', 'p620 7']
POCKET = ['p610 4', 'p620 6', 'p620 7']
GROWTH = 1.009327


def by_ts(df):
    """(period, timestep) frame -> timestep-indexed (one weather year)"""
    df = df.copy()
    df.index = pd.DatetimeIndex(df.index.get_level_values(1))
    return df


def main():
    import pypsa
    n = pypsa.Network(str(B16 / 'baseline_2025_tamu_prepared.nc'))
    L = n.lines.copy()
    vn = n.buses.v_nom
    L['x_pu'] = L.x / (vn.reindex(L.bus0).values ** 2)
    lim_b = L.s_nom * L.s_max_pu
    l2 = pd.read_csv(B16 / 'LP2_lines.csv').set_index('line')
    lim_2 = l2.limit_MW.reindex(L.index)
    f2 = by_ts(pd.read_csv(B16 / 'LP2_line_flow_p0.csv.gz', index_col=[0, 1], parse_dates=[1]))
    fp = pd.read_csv(PROBE / 'solution/S0/line_p0.csv.gz', index_col=[0, 1], parse_dates=[1])
    f0 = by_ts(fp.loc[[2026]])
    sh0 = pd.read_csv(ORIG / 'S0_shed_by_snapshot_frozen.csv.gz', index_col=[0, 1], parse_dates=[1]).clip(lower=0.0)
    s26 = by_ts(sh0.loc[[2026]])
    sub_cols = [c for c in s26.columns if any(c.startswith(b + ' ') for b in SUB)]
    hours = s26.index[s26[sub_cols].sum(axis=1) > 1e-3]
    load = n.loads_t.p_set
    load = load.droplevel(0) if isinstance(load.index, pd.MultiIndex) else load
    busload = load.T.groupby(n.loads.bus).sum().T
    step = pd.Series(busload.index).diff().dropna().median()
    load3 = busload.resample('3h').mean() if step < pd.Timedelta(hours=3) else busload
    lp2_shed = pd.read_csv(B16 / 'LP2_shed_by_bus.csv.gz', index_col=0)
    # 1 binding lines in the West at the shed hours
    west = L.index[L.bus0.astype(str).str.startswith(('p610', 'p620', 'p630')) | L.bus1.astype(str).str.startswith(('p610', 'p620', 'p630'))]
    rows = []
    for ln in west:
        if ln not in f2.columns or ln not in f0.columns:
            continue
        a2 = f2.loc[hours, ln].abs() / lim_2[ln]; a0 = f0.loc[hours, ln].abs() / lim_b[ln]
        rows.append(dict(line=ln, bus0=L.bus0[ln], bus1=L.bus1[ln], limit_LP2_MW=float(lim_2[ln]), limit_S0_MW=float(lim_b[ln]),
                         limit_differs=abs(float(lim_2[ln]) - float(lim_b[ln])) > 1e-3, x_ohm=float(L.x[ln]),
                         LP2_binding_hours_of_42=int((a2 >= 0.999).sum()), S0_binding_hours_of_42=int((a0 >= 0.999).sum()),
                         LP2_mean_flow_MW=float(f2.loc[hours, ln].mean()), S0_mean_flow_MW=float(f0.loc[hours, ln].mean()),
                         LP2_mean_loading=float(a2.mean()), S0_mean_loading=float(a0.mean())))
    BL = pd.DataFrame(rows).sort_values(['S0_binding_hours_of_42', 'LP2_binding_hours_of_42'], ascending=False)
    BL.to_csv(PROBE / 'W5_WEST_LINE_BINDING_AT_S0_SHED_HOURS.csv', index=False)
    # 2 sub-pocket import and load, per hour
    sgn = lambda ln, into: 1.0 if L.bus1[ln] == into else -1.0           # p0 flows bus0 -> bus1
    H = []
    for t in hours:
        r = dict(timestep=t)
        for tag, f, lim in (('LP2', f2, lim_2), ('S0', f0, lim_b)):
            imp43 = sgn('TL43', 'p620 6') * f.at[t, 'TL43']; imp36 = sgn('TL36', 'p620 7') * f.at[t, 'TL36']
            imp35 = sgn('TL35', 'p610 4') * f.at[t, 'TL35']
            r.update({f'{tag}_TL43_into_p620_6': imp43, f'{tag}_TL36_into_p620_7': imp36, f'{tag}_TL35_into_p610_4': imp35,
                      f'{tag}_TL44_p620_6_to_7': sgn('TL44', 'p620 7') * f.at[t, 'TL44'], f'{tag}_sub_pocket_import': imp43 + imp36,
                      f'{tag}_TL43_loading': abs(f.at[t, 'TL43']) / lim['TL43'], f'{tag}_TL36_loading': abs(f.at[t, 'TL36']) / lim['TL36'],
                      f'{tag}_TL44_loading': abs(f.at[t, 'TL44']) / lim['TL44'], f'{tag}_TL35_loading': abs(f.at[t, 'TL35']) / lim['TL35']})
        ld = load3.reindex([t])[SUB].sum(axis=1).iloc[0]
        r['LP2_sub_pocket_load'] = float(ld); r['S0_sub_pocket_load'] = float(ld * GROWTH)
        r['S0_sub_pocket_shed'] = float(s26.loc[t, sub_cols].sum())
        r['LP2_sub_pocket_shed'] = float(sum(lp2_shed.loc[str(t), c] if str(t) in lp2_shed.index and c in lp2_shed.columns else 0.0 for c in SUB)) if len(lp2_shed) else 0.0
        r['p610_4_load_S0'] = float(load3.at[t, 'p610 4'] * GROWTH)
        # 3 angle across the loop p620 0 -> p610 4 -> p620 7 -> p620 6 <- p620 4 (DC power flow: theta_a - theta_b = x_pu f_ab)
        for tag, f in (('LP2', f2), ('S0', f0)):
            d = lambda ln: float(L.x_pu[ln] * f.at[t, ln])                    # theta(bus0) - theta(bus1)
            th = {'p620 0': 0.0}
            th['p610 4'] = th['p620 0'] + (d('TL35') if L.bus0['TL35'] == 'p620 0' else -d('TL35'))
            th['p620 7'] = th['p610 4'] - (d('TL36') if L.bus0['TL36'] == 'p610 4' else -d('TL36'))
            th['p620 6'] = th['p620 7'] + (d('TL44') if L.bus0['TL44'] == 'p620 6' else -d('TL44'))
            th['p620 4'] = th['p620 6'] + (d('TL43') if L.bus0['TL43'] == 'p620 4' else -d('TL43'))
            r[f'{tag}_theta_p620_0_minus_p620_4_mrad'] = 1e3 * (th['p620 0'] - th['p620 4'])
        H.append(r)
    HH = pd.DataFrame(H)
    HH.to_csv(PROBE / 'W5_SUB_POCKET_HOURLY.csv', index=False)
    # full-year LP2 view of the sub-pocket: how often is it at its cut, and how close is load to the cut
    full = pd.DataFrame(index=f2.index)
    full['import'] = sgn('TL43', 'p620 6') * f2['TL43'] + sgn('TL36', 'p620 7') * f2['TL36']
    full['cut'] = float(lim_2['TL43'] + lim_2['TL36'])
    full['load_2025'] = load3.reindex(f2.index)[SUB].sum(axis=1).values
    full['load_2026'] = full.load_2025 * GROWTH
    full['TL43_at_limit'] = f2['TL43'].abs() / lim_2['TL43'] >= 0.999
    full['TL36_at_limit'] = f2['TL36'].abs() / lim_2['TL36'] >= 0.999
    summ = dict(
        work_package='BYOP_NEXT_07', step='W5 LP2 vs S0 mesh flows', optimizer_calls=0, hours=int(len(hours)),
        sub_pocket=SUB, sub_pocket_cut=dict(TL43=float(lim_2['TL43']), TL36=float(lim_2['TL36']), sum=float(lim_2['TL43'] + lim_2['TL36']),
                                            same_in_S0=bool(abs(lim_2['TL43'] - lim_b['TL43']) < 1e-3 and abs(lim_2['TL36'] - lim_b['TL36']) < 1e-3)),
        lines_with_different_limits_in_west=BL[BL.limit_differs].line.tolist(),
        at_s0_shed_hours={k: float(v) for k, v in HH.drop(columns=['timestep']).mean().items()},
        lp2_full_year=dict(snapshots=int(len(full)), TL43_at_limit=int(full.TL43_at_limit.sum()), TL36_at_limit=int(full.TL36_at_limit.sum()),
                           both_at_limit=int((full.TL43_at_limit & full.TL36_at_limit).sum()),
                           import_max=float(full['import'].max()), load_2025_max=float(full.load_2025.max()), load_2026_max=float(full.load_2026.max()),
                           snapshots_load_2025_above_cut=int((full.load_2025 > full.cut + 1e-3).sum()),
                           snapshots_load_2026_above_cut=int((full.load_2026 > full.cut + 1e-3).sum())),
        binding_lines_S0=BL[BL.S0_binding_hours_of_42 > 0][['line', 'S0_binding_hours_of_42', 'LP2_binding_hours_of_42']].to_dict('records'))
    (PROBE / 'W5_LP2_VS_S0_SUMMARY.json').write_text(json.dumps(summ, indent=1, default=float), encoding='utf-8')
    print(json.dumps(summ, indent=1, default=float))
    pd.set_option('display.width', 250)
    print(BL.head(15).to_string())
    print(HH.round(2).head(12).T.to_string())


if __name__ == '__main__':
    main()
