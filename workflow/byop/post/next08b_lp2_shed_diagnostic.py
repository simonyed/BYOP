#!/usr/bin/env python3
"""NEXT-08b read-only diagnostic of the residual LP2 shed on the v2 lossy candidate (0 solver calls).

Reads the sealed outputs of the approved v2 chain (results/BYOP/next08b_lp1_tangent_fix) and the NEXT-08 v1 chain and reports:
  * v1 vs v2: LP1 / LP2 losses, uplift, EENS, largest gap, shed by bus;
  * the LP2 shed events and, at each of their snapshots, every line whose rating row is binding: |s| + loss >= 0.995 x s_max_pu s_nom
    with s = p0 - loss / 2 (the row PyPSA builds with transmission_losses; the C1 metric |p0| / limit >= 0.999 used in the QA JSON
    can never fire with losses, hence 'binding_lines: 0' there);
  * the lines incident to the shed buses with LP2 flow / loss and LP1-IT2 loss at the same snapshot;
  * per-line LP1-IT2 vs LP2 annual loss, and the remaining S_ref (IT1) vs final (IT2) capacity difference;
  * the LP1 / LP2 shed-penalty values (LP1 SHED_COST vs v1.6 voll).
Run on L2 from workflow/:  python byop/post/next08b_lp2_shed_diagnostic.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/run'))
V2 = WF / 'results/BYOP/next08b_lp1_tangent_fix'
V1 = WF / 'results/BYOP/next08_lossy_lp1'
STAGES = ('LP1_LOSSY_IT1', 'LP1_LOSSY_IT2', 'LP2_LOSSY_CANDIDATE')
BIND = 0.995


def chain_summary(d):
    q1, q2 = (json.loads((d / s / 'LOSSY_LP1_QA.json').read_text()) for s in STAGES[:2])
    q3 = json.loads((d / STAGES[2] / 'LOSS_BASIS_LP2_QA.json').read_text())
    a = q3['acceptance']
    return dict(lp1_it1_loss_TWh=q1['total_loss_MWh'] / 1e6, lp1_it2_loss_TWh=q2['total_loss_MWh'] / 1e6, lp2_loss_TWh=q3['losses']['total_loss_MWh'] / 1e6,
                lp1_it1_max_rel_r_gap=q1['convergence']['max_rel_r_gap'], lp1_it2_max_rel_r_gap=q2['convergence']['max_rel_r_gap'],
                uplift_it2_MVA=q2['guards']['total_uplift_MVA'], lp1_it2_eens_MWh=q2['residual_shed']['eens_MWh'],
                lp2_eens_MWh=a['eens_MWh'], lp2_max_gap_MW=a['max_gap_MW'], lp2_max_gap_step=a['max_gap_step'], lp2_shed_hours=a['shed_hours'],
                lp2_events=a['events'], lp2_shed_buses=len(a['shed_buses']), lp2_objective_USD=q3['metrics']['objective_USD'],
                eens_pass=a['eens_pass'], max_gap_pass=a['max_gap_pass'], lp2_shed_by_bus_MWh={k: round(v, 1) for k, v in q3['shed_by_bus_MWh'].items()},
                uplift_by_line_MVA={k: round(v, 1) for k, v in q2['uplift_by_line_MVA'].items()})


def main():
    import baseline_v16_calibration as V16
    import loss_basis_lp1 as L
    v, _ = V16.load_cfg()
    lp2 = V2 / STAGES[2]
    lines = pd.read_csv(lp2 / 'lines.csv', index_col='line')
    s1 = pd.read_csv(V2 / STAGES[1] / 'LP1_LINE_SOLUTION.csv', index_col=0)
    ll1 = pd.read_csv(V2 / STAGES[1] / 'line_loss.csv.gz', index_col=[0, 1])
    ll2 = pd.read_csv(lp2 / 'line_loss.csv.gz', index_col=[0, 1])
    p0 = pd.read_csv(lp2 / 'line_flow_p0.csv.gz', index_col=[0, 1])
    ev = pd.read_csv(lp2 / 'shedding_events.csv').sort_values('energy_MWh', ascending=False)
    use = ((p0 - ll2 / 2).abs() + ll2) / lines.limit_MW.reindex(p0.columns)
    w = 3.0

    rep = dict(step='NEXT-08b read-only LP2 shed diagnostic on the v2 lossy candidate', solver_calls=0,
               v1=chain_summary(V1), v2=chain_summary(V2),
               shed_penalty_USD_MWh=dict(lp1_SHED_COST=float(L.SHED_COST), lp2_voll=float(v['voll_USD_MWh'])),
               binding_rule=f'|p0 - loss/2| + loss >= {BIND} x s_max_pu x s_nom')
    rep['lines_binding_any_step'] = int(((use >= BIND).sum() > 0).sum())
    rep['binding_hours_top'] = ((use >= BIND).sum() * w).sort_values(ascending=False).head(20).to_dict()
    snaps = {}
    for _, e in ev.head(8).iterrows():
        k = (2030, e.start)
        if k not in use.index or e.start in snaps:
            continue
        u = use.loc[k]
        b = u[u >= BIND].sort_values(ascending=False)
        snaps[e.start] = dict(shed_bus=e.bus, energy_MWh=round(e.energy_MWh, 1), peak_MW=round(e.peak_MW, 1),
                              binding={ln: dict(bus0=lines.bus0[ln], bus1=lines.bus1[ln], use=round(float(u[ln]), 4),
                                                limit_MW=round(float(lines.limit_MW[ln]), 1), s_nom=round(float(lines.s_nom_MVA[ln]), 1),
                                                s_v16=round(float(s1.s_v16_prepared[ln]), 1)) for ln in b.index})
    rep['shed_event_snapshots'] = snaps
    inc = {}
    for bus in ('p610 1', 'p630 14'):
        ls = lines.index[(lines.bus0 == bus) | (lines.bus1 == bus)]
        k = (2030, '2030-08-28 09:00:00')
        inc[bus] = {ln: dict(other=lines.bus1[ln] if lines.bus0[ln] == bus else lines.bus0[ln], s_v16=round(float(s1.s_v16_prepared[ln]), 1),
                             s_cand=round(float(lines.s_nom_MVA[ln]), 1), use_lp2=round(float(use.loc[k, ln]), 4), p0_lp2=round(float(p0.loc[k, ln]), 1),
                             loss_lp2=round(float(ll2.loc[k, ln]), 2), loss_lp1_it2=round(float(ll1.loc[k, ln]), 2)) for ln in ls}
    rep['incident_lines_at_max_gap_step'] = inc
    tot = pd.DataFrame(dict(lp1_it2_MWh=ll1.sum() * w, lp2_MWh=ll2.sum() * w))
    tot['ratio'] = tot.lp1_it2_MWh / tot.lp2_MWh
    big = tot[tot.lp2_MWh > 1000]
    rep['loss_lp1_it2_over_lp2'] = dict(total=float(tot.lp1_it2_MWh.sum() / tot.lp2_MWh.sum()),
                                        lines_over_1p2=big[big.ratio > 1.2].round(2).sort_values('lp2_MWh', ascending=False).to_dict('index'),
                                        lines_under_0p8=big[big.ratio < 0.8].round(2).sort_values('lp2_MWh', ascending=False).to_dict('index'))
    rep['s_ref_vs_final_max_rel'] = ((s1.s_nom_opt - s1.s_ref) / s1.s_ref).abs().sort_values(ascending=False).head(8).round(4).to_dict()
    out = V2 / 'W8B_LP2_SHED_DIAGNOSTIC.json'
    out.write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: rep[k] for k in ('v1', 'v2', 'shed_penalty_USD_MWh', 'lines_binding_any_step')}, indent=1, default=str))


if __name__ == '__main__':
    main()
