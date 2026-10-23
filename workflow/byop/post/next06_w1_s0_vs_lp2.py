#!/usr/bin/env python3
"""NEXT-06 W1.3 (read-only, NO solver; network build only): build the S0 network exactly as the A2 run did (rearch_mech build path of the
merged code, post-v1.6 switches on) and compare, for the Far West shed buses and their neighbours at the 2026 S0 shed snapshots, the
inputs S0 sees with the v1.6 baseline / LP2 fixed-asset 2025 check at the same weather hours. Nothing is optimised: linopy.Model.solve
and n.optimize are refused. Run on L2 from workflow/:
    python -W ignore byop/post/next06_w1_s0_vs_lp2.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, 'byop/model')
import linopy  # noqa: E402
linopy.Model.solve = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver refused (W1 read-only)'))
import pypsa  # noqa: E402
import rearch_mech as R  # noqa: E402
import post_v16_mainline as PM  # noqa: E402
import byop_paths as BP  # noqa: E402

M, w2, V, STATE = R.M, R.w2, R.V, R.STATE
WF = Path.cwd()
OUT = WF / 'results/BYOP/next06_s0_diagnostic'
B16 = BP.BASE_TAMU_V16_DIR
CFG_PATH = 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml'
FOCUS = ['p620 6', 'p620 7']


def build_s0():
    """the structural-harness configuration (= the --post-v16 run configuration), S0 network only"""
    R.BASE_TAMU = BP.BASE_TAMU_V16
    R.ml_select_siting(CFG_PATH)
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['W1 read-only']))
    R.GCFG.update(setting='G-REAL', competing=0.0, regional_dc='off', case='base', gas_case='base', relax=[], s2_modes=R.MODES,
                  interrupt_cap=0.005, no_harm=True, base_assets='main', s0_calibrate=False, s0_cal_file=None)
    M.CFG.update(periods='annual', start=2026, end=2031, cost_basis='repaired', public_subsidy='without', tariff='energy', reuse='on',
                 reuse_case='base', frac_cod=True, flex=False, poi_lead=0, byop_case='base', public_case='base', byop_techs=list(R.ML_TECHS),
                 sample_weeks=26, bg_growth=0.0, line_exp=True, erm15=False, threads=4, v=2.8e6, v_private=None, smoke=False, dem_scale=1.0)
    M.CFG['tech_version'] = R.ml_tech_version(CFG_PATH)
    PM.POST_V16['on'] = True
    w2.POST_V16_NO_ERM['on'] = True
    R.configure_mainline(OUT / '_build_only')
    M.build = R.build_rearch; M.extra = R.extra_rearch
    w2.store_ERM_duals = V.store_erm_duals_tx; V.GCFG.update(erm_scope='tx')
    w2.PREP = str(R.BASE_TAMU); w2.PUE = pd.read_csv(w2.PUE_CSV)
    config = pypsa.Network(str(R.BASE_TAMU)).meta
    STATE['erm_cal'] = None
    n, _ = M.build(config, 'S0', 2.8e6)
    return n


def main():
    (OUT / '_build_only').mkdir(parents=True, exist_ok=True)
    n = build_s0()
    b = pypsa.Network(str(BP.BASE_TAMU_V16))
    sh = pd.read_csv(OUT / 'W1_S0_SHED_SNAPSHOT_WEIGHTS.csv', parse_dates=['timestep'])
    ts = sorted(set(sh[(sh.period == 2026) & sh.bus.isin(FOCUS)].timestep))
    sns26 = [s for s in n.snapshots if s[0] == 2026 and pd.Timestamp(s[1]) in set(ts)]
    adj = n.lines[n.lines.bus0.isin(FOCUS) | n.lines.bus1.isin(FOCUS)]
    ring = sorted(set(FOCUS) | set(adj.bus0) | set(adj.bus1))
    rows = []
    # --- loads by bus (S0 2026 vs baseline at the same timesteps)
    ls0 = n.loads_t.p_set.loc[sns26]
    lb = b.loads_t.p_set; lb = lb.droplevel(0) if isinstance(lb.index, pd.MultiIndex) else lb
    lb = lb.loc[[pd.Timestamp(s[1]) for s in sns26]]
    for bus in ring:
        c0 = [x for x in n.loads.index[n.loads.bus == bus] if x in ls0.columns]
        cb = [x for x in b.loads.index[b.loads.bus == bus] if x in lb.columns]
        rows.append(dict(item='load_MW_mean_at_shed', bus=bus, S0_2026=float(ls0[c0].sum(axis=1).mean()) if c0 else 0.0,
                         v16_baseline_2025=float(lb[cb].sum(axis=1).mean()) if cb else 0.0, S0_components=';'.join(c0)[:200]))
    # --- generator / storage availability at the ring (active in 2026, p_nom x p_max_pu)
    act = n.components['Generator'].get_activity_mask(n.snapshots)
    pm0 = n.get_switchable_as_dense('Generator', 'p_max_pu', n.snapshots)
    pmb = b.get_switchable_as_dense('Generator', 'p_max_pu', b.snapshots)
    pmb = pmb.droplevel(0) if isinstance(pmb.index, pd.MultiIndex) else pmb
    for bus in ring:
        g0 = n.generators[(n.generators.bus == bus) & (n.generators.carrier != 'load_shed')]
        fixed = g0[~g0.p_nom_extendable]
        av0 = float((pm0.loc[sns26, fixed.index] * act.loc[sns26, fixed.index] * fixed.p_nom).sum(axis=1).mean()) if len(fixed) else 0.0
        gb = b.generators[(b.generators.bus == bus) & ~b.generators.p_nom_extendable & (b.generators.carrier != 'load_shed')]
        avb = float((pmb.loc[[pd.Timestamp(s[1]) for s in sns26], gb.index] * gb.p_nom).sum(axis=1).mean()) if len(gb) else 0.0
        ext26 = g0[g0.p_nom_extendable & (g0.build_year <= 2026)]
        rows.append(dict(item='fixed_generation_available_MW_mean_at_shed', bus=bus, S0_2026=av0, v16_baseline_2025=avb,
                         S0_components=';'.join(f'{x}:{fixed.carrier[x]}:{fixed.p_nom[x]:.0f}' for x in fixed.index)[:300],
                         note=f'extendable candidates active in 2026 at this bus: {len(ext26)}'))
        s0 = n.storage_units[n.storage_units.bus == bus]; sb = b.storage_units[b.storage_units.bus == bus]
        rows.append(dict(item='storage_MW', bus=bus, S0_2026=float(s0[~s0.p_nom_extendable].p_nom.sum()), v16_baseline_2025=float(sb.p_nom.sum()),
                         S0_components=';'.join(s0.index)[:200]))
    # --- lines and links touching the ring
    for x, r in n.lines[n.lines.bus0.isin(ring) | n.lines.bus1.isin(ring)].iterrows():
        smp = n.get_switchable_as_dense('Line', 's_max_pu', n.snapshots)[x].loc[sns26].mean() if x in n.lines.index else np.nan
        rows.append(dict(item='line_rating_MW', bus=f'{r.bus0}-{r.bus1}', name=x, S0_2026=float(r.s_nom * smp),
                         v16_baseline_2025=float(b.lines.s_nom[x] * b.lines.s_max_pu[x]), x_S0=float(r.x), x_v16=float(b.lines.x[x])))
    for x, r in n.links[n.links.bus0.isin(ring) | n.links.bus1.isin(ring)].iterrows():
        pmax = n.get_switchable_as_dense('Link', 'p_max_pu', n.snapshots)[x].loc[sns26].mean()
        actl = n.components['Link'].get_activity_mask(n.snapshots)[x].loc[sns26].mean()
        rows.append(dict(item='link', bus=f'{r.bus0}->{r.bus1}', name=x, S0_2026=float(r.p_nom * pmax * actl), carrier=r.carrier,
                         extendable=bool(r.p_nom_extendable), build_year=int(r.build_year)))
    d = pd.DataFrame(rows)
    d.to_csv(OUT / 'W1_S0_VS_V16_LP2_INPUTS_FAR_WEST.csv', index=False)
    # --- how did the v1.6 LP2 (2025 fixed assets, full year) serve the same hours? (saved line flows / shed / SOC)
    f = pd.read_csv(B16 / 'LP2_line_flow_p0.csv.gz', index_col=[0, 1], parse_dates=[1]).droplevel(0)
    tsel = [pd.Timestamp(s[1]) for s in sns26]
    lines_r = [x for x in n.lines.index[n.lines.bus0.isin(ring) | n.lines.bus1.isin(ring)] if x in f.columns]
    flows = f.reindex(tsel)[lines_r]
    lp2 = pd.read_csv(B16 / 'LP2_shed_by_bus.csv.gz', index_col=[0, 1], parse_dates=[1]).droplevel(0)
    lp2_at = lp2.reindex(tsel)
    summ = dict(solver_calls=0, shed_snapshots_2026_focus=len(sns26), ring=ring,
                lp2_flows_at_same_hours_mean_MW=flows.mean().round(1).to_dict() if len(flows) else {},
                lp2_flow_rows_matched=int(flows.notna().any(axis=1).sum()),
                lp2_shed_at_same_hours_MW={c: float(lp2_at[c].sum()) for c in lp2_at.columns if c in ring},
                lp2_line_ratings_MW={x: float(b.lines.s_nom[x] * b.lines.s_max_pu[x]) for x in lines_r},
                lp2_max_abs_flow_at_same_hours_MW=flows.abs().max().round(1).to_dict() if len(flows) else {})
    (OUT / 'W1_S0_VS_V16_LP2_SUMMARY.json').write_text(json.dumps(summ, indent=1, default=str))
    pd.set_option('display.width', 250)
    print(d.to_string(max_colwidth=60))
    print(json.dumps(summ, indent=1, default=str))


if __name__ == '__main__':
    main()
