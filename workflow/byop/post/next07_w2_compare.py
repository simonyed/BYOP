#!/usr/bin/env python3
"""NEXT-07 W2.3 (read-only, NO solver): original formal S0 (3,000 MW reserve) vs the reserve-RHS probe (0 MW), same snapshot index.
Like-for-like where both runs saved it (existing-customer shed per unit x snapshot, bus LMPs, public investment ledger, cost book);
probe-only where the original run did not persist the state (line flows, dispatch, SOC, reserve; persistence exists since NEXT-06).
Separates the immediate dispatch effect from the investment feedback: public assets active in 2026 are compared first - if the
2026-active public fleet is identical, every 2026 difference is operational (dispatch / reserve), and the investment feedback is
the 2027-2031 build difference plus what follows from it. Pre-registered class on the 2026 Far West nightly weighted shed.
Run on L2: BYOP_WF=<.../pypsa-usa/workflow> python next07_w2_compare.py
Writes <WF>/results/BYOP/next07_s0_reserve_probe/W2_*.csv / .json."""
from __future__ import annotations

import json, os
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(os.environ.get('BYOP_WF') or Path(__file__).resolve().parents[2])
ORIG = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
PROBE = WF / os.environ.get('BYOP_PROBE_DIR', 'results/BYOP/next07_s0_reserve_probe')     # W5: the lossless probe reuses this script
SEG = WF / 'results/BYOP/post_v16_a2_static/_structural_merged/A2_SOC_SEGMENT_MAP_S0.csv'
BASE = WF / 'results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc'
POCKET = ['p610 4', 'p620 6', 'p620 7']
KEY_BUSES = ['p620 6', 'p620 7', 'p620 3', 'p610 4', 'p630 2']
NIGHT_H = set(range(0, 10))
PFX = os.environ.get('BYOP_OUT_PREFIX', 'W2')
CLASSES = {'reserve': [(0.8, 'RESERVE_REQUIREMENT_LARGE_CONTRIBUTOR'), (0.2, 'MIXED_CAUSES'), (-np.inf, 'RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL')],
           'lossless': [(0.8, 'LOSS_BASIS_CONFIRMED_MAIN_CAUSE'), (0.2, 'LOSSES_MAJOR_NOT_ONLY_CAUSE'), (-np.inf, 'LOSSES_NOT_MAIN_CAUSE')]
           }[os.environ.get('BYOP_PROBE_KIND', 'reserve')]


def rd(p, **kw):
    return pd.read_csv(p, **kw)


def weights(index):
    sm = rd(SEG, parse_dates=['start', 'end'])
    w = pd.Series(np.nan, index=index); kind = pd.Series('', index=index, dtype=object)
    per = index.get_level_values(0); ts = pd.DatetimeIndex(index.get_level_values(1))
    for r in sm.itertuples():
        msk = (per == r.period) & (ts >= r.start) & (ts <= r.end)
        w[msk] = r.w_generators_h; kind[msk] = r.kind
    return w, kind


def long_shed(f, w, kind, tag):
    s = rd(f, index_col=[0, 1], parse_dates=[1]).clip(lower=0.0)
    L = s.stack().rename('MW').reset_index(); L.columns = ['period', 'timestep', 'unit', 'MW']
    L['bus'] = L.unit.str.replace(' inherited_ramp_unserved$', '', regex=True).str.replace(' load_shed$', '', regex=True)
    L['category'] = np.where(L.unit.str.endswith('inherited_ramp_unserved'), 'inherited_ramp', 'native')
    k = pd.MultiIndex.from_arrays([L.period, L.timestep])
    L['weight_h'] = w.reindex(k).values; L['segment_kind'] = kind.reindex(k).values
    L['weighted_MWh'] = L.MW * L.weight_h; L['raw_3h_MWh'] = L.MW * 3.0
    L['night'] = pd.DatetimeIndex(L.timestep).hour.isin(NIGHT_H)
    L['run'] = tag
    return s, L


def main():
    import pypsa
    res = json.loads((PROBE / 'S0_RESULT.json').read_text(encoding='utf-8'))
    acc = res['acceptance']
    sol = PROBE / 'solution' / 'S0'
    o_s = rd(ORIG / 'S0_shed_by_snapshot_frozen.csv.gz', index_col=[0, 1], parse_dates=[1])
    w, kind = weights(o_s.index)
    o_s, LO = long_shed(ORIG / 'S0_shed_by_snapshot_frozen.csv.gz', w, kind, 'original')
    p_s, LP = long_shed(PROBE / 'S0_shed_by_snapshot_frozen.csv.gz', w, kind, 'probe')
    same_index = o_s.index.equals(p_s.index) and list(o_s.columns) == list(p_s.columns)
    L = pd.concat([LO, LP])
    rows = []

    def add(section, metric, scope, o, p, unit, note=''):
        d = None if o is None or p is None else p - o
        pct = (d / o) if (d is not None and o not in (0, None) and abs(o) > 1e-9) else None
        rows.append(dict(section=section, metric=metric, scope=scope, original=o, probe=p, delta=d, rel_change=pct, unit=unit, note=note))

    g = lambda q: L.query(q).groupby('run').weighted_MWh.sum().reindex(['original', 'probe']).fillna(0.0)
    for q, scope in [('period >= 2026', '2026-2031 sum (six model-year values)'), ('period == 2026', '2026 all'),
                     ("period == 2026 and category == 'native'", '2026 native'), ("period == 2026 and category == 'inherited_ramp'", '2026 inherited ramp'),
                     ('period > 2026', '2027-2031 sum')]:
        v = g(q); add('A_shed', 'existing-customer shed, weighted', scope, float(v.original), float(v.probe), 'MWh')
    fw = f'period == 2026 and bus in {POCKET}'
    v_fw_night = g(fw + ' and night'); v_fw = g(fw)
    add('A_shed', 'Far West pocket shed, weighted (PRE-REGISTERED METRIC: 2026, night 00-09 start)', '2026 Far West night', float(v_fw_night.original), float(v_fw_night.probe), 'MWh')
    add('A_shed', 'Far West pocket shed, weighted', '2026 Far West all hours', float(v_fw.original), float(v_fw.probe), 'MWh')
    raw = L.query(fw).groupby('run').raw_3h_MWh.sum().reindex(['original', 'probe']).fillna(0.0)
    add('A_shed', 'Far West pocket shed, raw 3 h (no weight)', '2026 Far West all hours', float(raw.original), float(raw.probe), 'MWh')
    for k in ('SAMPLED_WEEK', 'B7_STRESS_ONLY'):
        v = g(f"period == 2026 and segment_kind == '{k}'"); add('A_shed', f'shed weighted, {k}', '2026', float(v.original), float(v.probe), 'MWh')
    for b in KEY_BUSES:
        q = L[(L.period == 2026) & (L.bus == b)]
        mx = q.groupby('run').MW.max().reindex(['original', 'probe']).fillna(0.0)
        wm = q.groupby('run').weighted_MWh.sum().reindex(['original', 'probe']).fillna(0.0)
        ns = q[(q.MW > 1e-3) & q.night].groupby('run').size().reindex(['original', 'probe']).fillna(0)
        add('A_shed_bus', 'peak shed', f'2026 {b}', float(mx.original), float(mx.probe), 'MW')
        add('A_shed_bus', 'weighted shed', f'2026 {b}', float(wm.original), float(wm.probe), 'MWh')
        add('A_shed_bus', 'night shed snapshots', f'2026 {b}', float(ns.original), float(ns.probe), 'count')
    bys = L.groupby(['run', 'period', 'bus', 'segment_kind', 'category'])[['weighted_MWh', 'raw_3h_MWh']].sum().reset_index()
    bys = bys[bys.weighted_MWh > 1e-6]
    bys.to_csv(PROBE / f'{PFX}_SHED_BY_BUS_YEAR_KIND.csv', index=False)
    # B prices
    po = rd(ORIG / 'prices_S0.csv.gz', index_col=[0, 1], parse_dates=[1])
    pp = rd(sol / 'bus_marginal_price.csv.gz', index_col=[0, 1], parse_dates=[1])
    o26 = o_s.loc[2026]
    pocket_cols = [c for c in o26.columns if any(c.startswith(b + ' ') for b in POCKET)]
    shed_ts = o26.index[o26[pocket_cols].sum(axis=1) > 1e-3]
    sel = pd.MultiIndex.from_product([[2026], shed_ts])
    for b in POCKET + ['p620 0', 'p620 4']:
        if b in po.columns and b in pp.columns:
            add('B_price', 'mean LMP at the original 2026 pocket shed snapshots', b, float(po.loc[sel, b].mean()), float(pp.loc[sel, b].mean()), 'USD/MWh')
    allb = [c for c in po.columns if c in pp.columns and not str(c).startswith('DC_')]
    add('B_price', 'mean LMP, all grid buses, 2026', 'system', float(po.loc[2026, allb].mean().mean()), float(pp.loc[2026, allb].mean().mean()), 'USD/MWh')
    # C lines / D dispatch / E storage / reserve: probe only (original not persisted)
    n = pypsa.Network(str(BASE))
    lin = n.lines
    cut = lin[lin.bus0.isin(POCKET) ^ lin.bus1.isin(POCKET)]
    lp = rd(sol / 'line_p0.csv.gz', index_col=[0, 1], parse_dates=[1])
    snaps = []
    for t in o26.index:
        k = (2026, t)
        r = dict(timestep=t, segment_kind=kind.get(k, ''), night=t.hour in NIGHT_H,
                 pocket_shed_original_MW=float(o26.loc[t, pocket_cols].sum()), pocket_shed_probe_MW=float(p_s.loc[k, pocket_cols].sum()))
        imp = 0.0
        for ln, row in cut.iterrows():
            if ln in lp.columns:
                f = float(lp.loc[k, ln])
                imp += f if row.bus1 in POCKET else -f        # p0 flows bus0 -> bus1
                r[f'{ln}_loading_probe'] = abs(f) / float(row.s_nom * row.s_max_pu) if row.s_nom else np.nan
        r['pocket_net_import_probe_MW'] = imp
        for b in POCKET:
            r[f'LMP_{b}_original'] = float(po.loc[k, b]) if b in po.columns else np.nan
            r[f'LMP_{b}_probe'] = float(pp.loc[k, b]) if b in pp.columns else np.nan
        snaps.append(r)
    SN = pd.DataFrame(snaps)
    rv = rd(sol / 'reserve_by_snapshot.csv.gz', index_col=[0, 1], parse_dates=[1]) if (sol / 'reserve_by_snapshot.csv.gz').exists() else None
    if rv is not None:
        r26 = rv.loc[2026]
        for c in ('reserve_total_MW', 'thermal_reserve_MW', 'bess_reserve_MW', 'thermal_online_cap_MW', 'thermal_p_MW', 'shortfall_vs_formal_MW'):
            SN[c + '_probe'] = r26.reindex(SN.timestep)[c].values
        add('D_reserve', 'snapshots with total reserve < 3,000 MW (formal requirement) - probe', '2026-2031', None, float((rv.shortfall_vs_formal_MW > 1e-3).sum()), 'count',
            'original: >= 3,000 MW in every snapshot by construction')
        add('D_reserve', 'mean total reserve held - probe', '2026 original pocket shed snapshots', 3000.0, float(r26.loc[shed_ts, 'reserve_total_MW'].mean()), 'MW',
            'original value is the binding floor (>= 3,000), exact original level not persisted')
        add('D_reserve', 'mean thermal online capacity - probe', '2026 original pocket shed snapshots', None, float(r26.loc[shed_ts, 'thermal_online_cap_MW'].mean()), 'MW', 'original not persisted')
        add('D_reserve', 'mean thermal dispatch - probe', '2026 original pocket shed snapshots', None, float(r26.loc[shed_ts, 'thermal_p_MW'].mean()), 'MW', 'original not persisted')
    sh = SN.night & (SN.pocket_shed_original_MW > 1e-3)
    add('C_lines', 'pocket net import - probe (original not persisted)', '2026 original pocket shed snapshots', None, float(SN.loc[sh, 'pocket_net_import_probe_MW'].mean()), 'MW',
        f'cut lines {list(cut.index)}; static cut {float((cut.s_nom * cut.s_max_pu).sum()):.1f} MW')
    for ln in cut.index:
        c = f'{ln}_loading_probe'
        if c in SN:
            add('C_lines', f'{ln} max loading - probe', '2026 original pocket shed snapshots', None, float(SN.loc[sh, c].max()), 'share of rating')
    gp = rd(sol / 'generator_p.csv.gz', index_col=[0, 1], parse_dates=[1])
    g = n.generators
    fwg = [x for x in gp.columns if x in g.index and str(g.bus[x]).startswith(('p610', 'p620')) and g.carrier[x] not in ('load_shed',)]
    add('D_dispatch', 'Far West (p610*/p620*) generation - probe (original not persisted)', '2026 original pocket shed snapshots', None,
        float(gp.loc[sel, fwg].sum(axis=1).mean()) if fwg else None, 'MW')
    soc = rd(sol / 'storage_soc.csv.gz', index_col=[0, 1], parse_dates=[1]) if (sol / 'storage_soc.csv.gz').exists() else None
    if soc is not None:
        add('E_storage', 'total grid storage SOC - probe (original not persisted)', '2026 original pocket shed snapshots', None, float(soc.loc[sel].sum(axis=1).mean()), 'MWh')
    SN.to_csv(PROBE / f'{PFX}_FAR_WEST_2026_SNAPSHOTS.csv', index=False)
    # F investment, 2026-active fleet first (immediate vs feedback)
    lo = rd(ORIG / 'MAINLINE_ASSET_COMMITMENT_LEDGER.csv'); lo = lo[lo.scenario == 'S0']
    lpp = rd(PROBE / 'MAINLINE_ASSET_COMMITMENT_LEDGER.csv'); lpp = lpp[lpp.scenario == 'S0']
    inv = []
    for tag, d in (('original', lo), ('probe', lpp)):
        first = d.sort_values('year').groupby('asset_id').first().reset_index()
        first = first[first.resource_path == 'public']
        for (c, b), x in first.groupby(['carrier', 'build_period']):
            inv.append(dict(run=tag, carrier=c, build_period=int(b), new_MW=float(x.capacity_MW.sum()), capex_PV_USD=float(x.resource_capex_PV_USD.sum()),
                            far_west_MW=float(x[x.zone.astype(str).str.startswith(('p610', 'p620'))].capacity_MW.sum())))
    IV = pd.DataFrame(inv)
    piv = IV.pivot_table(index=['carrier', 'build_period'], columns='run', values=['new_MW', 'far_west_MW', 'capex_PV_USD'], aggfunc='sum', fill_value=0.0)
    piv.columns = [f'{a}_{b}' for a, b in piv.columns]
    piv = piv.reset_index()
    for c in ('new_MW', 'far_west_MW', 'capex_PV_USD'):
        for r in ('original', 'probe'):
            if f'{c}_{r}' not in piv:
                piv[f'{c}_{r}'] = 0.0
        piv[f'{c}_delta'] = piv[f'{c}_probe'] - piv[f'{c}_original']
    piv.to_csv(PROBE / f'{PFX}_PUBLIC_INVESTMENT_BY_CARRIER_YEAR.csv', index=False)
    a26 = piv[piv.build_period <= 2026]
    active26_same = bool(a26.empty or (a26.new_MW_delta.abs() < 1e-3).all())
    add('F_investment', 'public new MW active in 2026 (build <= 2026)', 'system', float(a26.new_MW_original.sum()), float(a26.new_MW_probe.sum()), 'MW',
        'identical -> every 2026 difference is an immediate dispatch effect' if active26_same else '2026 fleet differs -> 2026 effect mixes dispatch and investment')
    for y in sorted(piv.build_period.unique()):
        x = piv[piv.build_period == y]
        add('F_investment', 'public new MW by build year', str(int(y)), float(x.new_MW_original.sum()), float(x.new_MW_probe.sum()), 'MW')
        add('F_investment', 'public new MW in Far West zones by build year', str(int(y)), float(x.far_west_MW_original.sum()), float(x.far_west_MW_probe.sum()), 'MW')
    for c in sorted(piv.carrier.unique()):
        x = piv[piv.carrier == c]
        add('F_investment', f'public new MW {c} (all build years)', 'system', float(x.new_MW_original.sum()), float(x.new_MW_probe.sum()), 'MW')
    so = rd(ORIG / 'MAINLINE_COST_BOOK_DECOMPOSITION.csv').iloc[0]
    sp = rd(PROBE / 'MAINLINE_COST_BOOK_DECOMPOSITION.csv').iloc[0] if (PROBE / 'MAINLINE_COST_BOOK_DECOMPOSITION.csv').exists() else None
    for c in ('public_resource_capex_PV_USD', 'system_operating_PV_USD', 'existing_customer_unserved_loss_PV_USD', 'physical_resource_spending_proxy_PV_USD',
              'social_welfare_cost_before_dc_delay_PV_USD'):
        add('G_cost', c, 'PV 2026-2031', float(so[c]), float(sp[c]) if sp is not None and c in sp else None, 'USD')
    add('G_cost', 'LP objective', 'PV', float(json.loads((ORIG / 'S0_RESULT.json').read_text())['result']['objective']), float(res['result']['objective']), 'USD')
    C = pd.DataFrame(rows)
    C.to_csv(PROBE / f'{PFX}_RESERVE_CAUSAL_COMPARISON.csv', index=False)
    o_m, p_m = float(v_fw_night.original), float(v_fw_night.probe)
    red = (o_m - p_m) / o_m if o_m > 0 else None
    cls = 'DIAGNOSTIC_BLOCKED' if not acc.get('PASS') else next(c for th, c in CLASSES if red is not None and red >= th)
    summ = dict(work_package='BYOP_NEXT_07', step='W2.3', optimizer_calls_this_step=0, acceptance_PASS=acc.get('PASS'), acceptance_checks=acc.get('checks'),
                diagnostic_label=(acc.get('diagnostic') or {}).get('label'), same_snapshot_index=same_index,
                preregistered_metric='2026 Far West pocket {p610 4, p620 6, p620 7} weighted shed, snapshots starting 00-09',
                original_MWh=o_m, probe_MWh=p_m, reduction=red, reduction_abs_MWh=o_m - p_m, CLASS=cls,
                pocket_raw_3h_MWh=dict(original=float(raw.original), probe=float(raw.probe)),
                fleet_2026_identical=active26_same, solve=dict(status=res['result'].get('status'), termination=res['result'].get('termination'),
                                                             seconds=res['result'].get('seconds'), objective=res['result'].get('objective')))
    (PROBE / f'{PFX}_RESERVE_CAUSAL_SUMMARY.json').write_text(json.dumps(summ, indent=1, default=str), encoding='utf-8')
    print(json.dumps(summ, indent=1, default=str))
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 70)
    print(C.to_string())


if __name__ == '__main__':
    main()
