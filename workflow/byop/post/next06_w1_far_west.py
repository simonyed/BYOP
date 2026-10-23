#!/usr/bin/env python3
"""NEXT-06 W1.2 / W1.3 (read-only, NO solver): Far West (p620 6 / p620 7) deliverability, line lineage (v1.6 vs pre-v1.6 baseline),
committed-project COD representation and LMP evidence at the S0 shed snapshots. Run on L2 from workflow/:
    python byop/post/next06_w1_far_west.py
Writes workflow/results/BYOP/next06_s0_diagnostic/W1_*.csv / .json."""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

WF = Path(__file__).resolve().parents[2]
SRC = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
B16 = WF / 'results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc'
B15 = WF / 'results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc'
OUT = WF / 'results/BYOP/next06_s0_diagnostic'
FOCUS = ['p620 6', 'p620 7']
A1_LINES = ['TL129', 'TL120', 'TL117', 'TL104', 'TL133']


def main():
    n = pypsa.Network(str(B16))
    o = pypsa.Network(str(B15)) if B15.exists() else None
    L = n.lines
    near = set(FOCUS)
    adj = L[L.bus0.isin(near) | L.bus1.isin(near)]
    near2 = near | set(adj.bus0) | set(adj.bus1)
    ring = L[L.bus0.isin(near2) | L.bus1.isin(near2)]
    # ---------------- line lineage: v1.6 vs pre-v1.6 for the Far West ring, the A1 lines and every line whose s_nom / x / r changed
    rows = []
    cand = set(ring.index) | set(A1_LINES)
    if o is not None:
        com = L.index.intersection(o.lines.index)
        for x in com:
            ch = any(abs(float(L.at[x, c]) - float(o.lines.at[x, c])) > 1e-9 * max(1.0, abs(float(o.lines.at[x, c]))) for c in ('s_nom', 'x', 'r'))
            if ch:
                cand.add(x)
    for x in sorted(cand):
        r = dict(line=x, bus0=L.at[x, 'bus0'], bus1=L.at[x, 'bus1'], in_far_west_ring=x in ring.index, a1_indicated=x in A1_LINES,
                 v16_s_nom=float(L.at[x, 's_nom']), v16_s_max_pu=float(L.at[x, 's_max_pu']), v16_x=float(L.at[x, 'x']), v16_r=float(L.at[x, 'r']))
        if o is not None and x in o.lines.index:
            ol = o.lines.loc[x]
            r.update(pre_s_nom=float(ol.s_nom), pre_s_max_pu=float(ol.s_max_pu), pre_x=float(ol.x), pre_r=float(ol.r))
            r['s_nom_ratio'] = r['v16_s_nom'] / r['pre_s_nom'] if r['pre_s_nom'] else np.nan
            r['x_ratio'] = r['v16_x'] / r['pre_x'] if r['pre_x'] else np.nan
            r['r_ratio'] = r['v16_r'] / r['pre_r'] if r['pre_r'] else np.nan
            r['x_scaled_inverse_to_s_nom'] = bool(np.isfinite(r['s_nom_ratio']) and abs(r['s_nom_ratio'] - 1) > 1e-6
                                                  and abs(r['x_ratio'] * r['s_nom_ratio'] - 1) < 1e-3)
            r['flag'] = 'TOPOLOGY_OR_IMPEDANCE_REVIEW_REQUIRED' if r['x_scaled_inverse_to_s_nom'] else ('S_NOM_CHANGED' if abs(r['s_nom_ratio'] - 1) > 1e-6 else '')
        rows.append(r)
    lin = pd.DataFrame(rows)
    lin.to_csv(OUT / 'W1_LINE_LINEAGE_V16_VS_PRE.csv', index=False)
    # ---------------- Far West asset deliverability (baseline assets at / around the shed buses)
    g = n.generators; su = n.storage_units
    bytime = lambda df: df.droplevel(0) if isinstance(df.index, pd.MultiIndex) else df
    pm = bytime(n.generators_t.p_max_pu)
    shed = pd.read_csv(OUT / 'W1_S0_SHED_SNAPSHOT_WEIGHTS.csv', parse_dates=['timestep'])
    ts26 = sorted(set(shed[(shed.period == 2026) & shed.bus.isin(FOCUS)].timestep))
    load = bytime(n.loads_t.p_set)
    lb = n.loads.bus
    A = []
    for b in sorted(near2):
        gl = g[(g.bus == b)]
        for name, r in gl.iterrows():
            av = pm[name].reindex(ts26).mean() if name in pm and ts26 else (float(r.p_max_pu) if 'p_max_pu' in r else 1.0)
            A.append(dict(bus=b, component='Generator', name=name, carrier=r.carrier, p_nom_MW=float(r.p_nom), extendable=bool(r.p_nom_extendable),
                          mean_p_max_pu_at_2026_shed_snapshots=float(av) if av == av else None,
                          available_MW_at_shed=float(r.p_nom) * float(av) if av == av else None, build_year=int(r.build_year), lifetime=float(r.lifetime)))
        for name, r in su[su.bus == b].iterrows():
            A.append(dict(bus=b, component='StorageUnit', name=name, carrier=r.carrier, p_nom_MW=float(r.p_nom), extendable=bool(r.p_nom_extendable),
                          max_hours=float(r.max_hours), build_year=int(r.build_year)))
        lds = lb.index[lb == b]
        if len(lds):
            lv = load[[x for x in lds if x in load.columns]].sum(axis=1)
            at = lv.reindex(ts26)
            A.append(dict(bus=b, component='Load', name='native load (sum)', carrier='load', p_nom_MW=float(lv.max()),
                          mean_load_MW_at_2026_shed_snapshots=float(at.mean()) if len(at.dropna()) else None, peak_load_MW_year=float(lv.max())))
    for x, r in ring.iterrows():
        A.append(dict(bus=f'{r.bus0} - {r.bus1}', component='Line', name=x, carrier='AC', p_nom_MW=float(r.s_nom) * float(r.s_max_pu),
                      s_nom=float(r.s_nom), s_max_pu=float(r.s_max_pu), x=float(r.x), r=float(r.r)))
    fw = pd.DataFrame(A)
    fw.to_csv(OUT / 'W1_FAR_WEST_ASSET_DELIVERABILITY.csv', index=False)
    # ---------------- LMP evidence at the 2026 shed snapshots: focus buses vs the rest (network-limited vs system-wide scarcity)
    pr = pd.read_csv(SRC / 'prices_S0.csv.gz', index_col=[0, 1], parse_dates=[1])
    E = []
    for t in ts26:
        row = pr.loc[(2026, t)]
        voll_buses = sorted(row.index[row >= 35684.0])
        E.append(dict(period=2026, timestep=t, lmp_p620_6=float(row.get('p620 6', np.nan)), lmp_p620_7=float(row.get('p620 7', np.nan)),
                      buses_at_VOLL=';'.join(voll_buses), n_buses_at_VOLL=len(voll_buses), lmp_median_all=float(row.median()),
                      lmp_max_outside_far_west=float(row[[c for c in row.index if not c.startswith('p620')]].max()),
                      **{f'lmp_{b}': float(row[b]) for b in sorted(near2 - near) if b in row.index}))
    ev = pd.DataFrame(E)
    ev.to_csv(OUT / 'W1_FAR_WEST_BOTTLENECK_EVIDENCE.csv', index=False)
    # ---------------- native load mapping QA (focus + ring buses): baseline load per bus, inherited ramp file
    ramp = pd.read_csv(WF / 'byop/inputs/dc/MAINLINE_INHERITED_RAMP_2025.csv')
    q = []
    for b in sorted(near2):
        lds = list(lb.index[lb == b])
        lv = load[[x for x in lds if x in load.columns]].sum(axis=1) if lds else pd.Series(dtype=float)
        q.append(dict(bus=b, native_load_components=len(lds), native_load_names=';'.join(lds)[:200], annual_energy_TWh=float(lv.sum() * 3 / 1e6) if len(lv) else 0.0,
                      peak_MW=float(lv.max()) if len(lv) else 0.0, min_MW=float(lv.min()) if len(lv) else 0.0,
                      inherited_ramp_IT_MW=float(ramp[ramp.bus == b].inherited_ramp_IT_MW.sum()) if 'bus' in ramp else None,
                      note='baseline p_set (3 h, 2030 calendar = model weather year); S0 has no study AIDC'))
    pd.DataFrame(q).to_csv(OUT / 'W1_NATIVE_LOAD_MAPPING_QA.csv', index=False)
    # ---------------- S0 public builds at the Far West ring by year (from the solved ledger)
    led = pd.read_csv(SRC / 'scenarios/S0/ledger.csv')
    fwl = led[led.zone.isin(sorted(near2))]
    fwl.groupby(['zone', 'carrier', 'year']).capacity_MW.sum().reset_index().to_csv(OUT / 'W1_FAR_WEST_S0_PUBLIC_BUILDS.csv', index=False)
    s = dict(solver_calls=0, focus=FOCUS, ring_buses=sorted(near2), ring_lines=list(ring.index),
             lines_changed_vs_pre=int((lin.get('flag', pd.Series(dtype=str)) != '').sum()) if len(lin) else 0,
             lines_impedance_review=int((lin.get('flag', pd.Series(dtype=str)) == 'TOPOLOGY_OR_IMPEDANCE_REVIEW_REQUIRED').sum()) if len(lin) else 0,
             shed_snapshots_2026_focus=len(ts26), voll_bus_sets=ev.buses_at_VOLL.value_counts().head(5).to_dict() if len(ev) else {},
             lmp_max_outside_far_west_at_shed=float(ev.lmp_max_outside_far_west.max()) if len(ev) else None)
    (OUT / 'W1_FAR_WEST_SUMMARY.json').write_text(json.dumps(s, indent=1, default=str))
    print(json.dumps(s, indent=1, default=str))
    print(fw.to_string(max_colwidth=40)[:6000])
    print(lin.to_string()[:4000])


if __name__ == '__main__':
    main()
