#!/usr/bin/env python3
"""NEXT-08b (read-only, NO solver): LP1 vs LP2 loss-approximation comparison on the saved NEXT-08 candidate. For every line the PyPSA
tangent lower envelope env(s) = max(0, max_k 2 r P_k |s| - r P_k^2) is evaluated at the SAME flows (the LP2 candidate solution,
s = p0 - loss/2, 2,920 x 3 h) for:
  LP2   2 tangents at 1/2, 1 x s_max_pu x S_cand (candidate capacity; r_final)   = the S0-S3 basis (fixed lines)
  A     2 tangents at 1/2, 1 x s_max_pu x S_max, S_max = 2 x v1.6 (the NEXT-08 LP1 as run; r_used of IT2)
  B     4 tangents at 1/4..1 x s_max_pu x S_max (the requested four-tangent LP1; r_used)
  C     2 tangents at 1/2, 1 x s_max_pu x S_ref (reference-capacity tangents, S_ref = the iteration's reference capacity = the
        IT1 solution used by IT2; r_used) - PyPSA's own two tangents, placed where LP2 will place them once capacities converge
Each option also with r_final (tangent effect only) and the r effect separately (r_used vs r_final at LP2 tangents).
Pointwise: worst relative underestimate vs LP2 over |s| in [0.3, 1] x candidate rating. Validation: the LP2 envelope at its own flows
must reproduce the LP2 loss solution. Run on L2 from workflow/: python byop/post/next08b_loss_envelope.py
Writes results/BYOP/next08b_lp1_tangent_fix/W8B_LOSS_ENVELOPE_*.csv / .json"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
SRC = WF / 'results/BYOP/next08_lossy_lp1'
OUT = WF / 'results/BYOP/next08b_lp1_tangent_fix'
FOCUS_BUSES = ['p610 1', 'p630 14', 'p620 2', 'p630 2']


def env(s_abs, r_pu, points):
    """PyPSA tangent lower envelope at |s| (arrays broadcast: s (T,), points (K,))"""
    s = np.asarray(s_abs, dtype=float)[:, None]
    p = np.asarray(points, dtype=float)[None, :]
    return np.maximum(0.0, (2 * r_pu * p * s - r_pu * p ** 2).max(axis=1))


def main():
    import pypsa
    OUT.mkdir(parents=True, exist_ok=True)
    cand = pypsa.Network(str(SRC / 'baseline_2025_tamu_lossy_candidate.nc'))
    vn = cand.buses.v_nom.reindex(cand.lines.bus0).values
    L = cand.lines.assign(v_nom=vn)
    sol2 = pd.read_csv(SRC / 'LP1_LOSSY_IT2' / 'LP1_LINE_SOLUTION.csv', index_col=0)
    p0 = pd.read_csv(SRC / 'LP2_LOSSY_CANDIDATE' / 'line_flow_p0.csv.gz', index_col=[0, 1])
    ls = pd.read_csv(SRC / 'LP2_LOSSY_CANDIDATE' / 'line_loss.csv.gz', index_col=[0, 1])
    s = (p0 - ls / 2.0)                                     # PyPSA: p0 = s + loss/2
    w = 3.0
    rows, worst_rows = [], []
    tot = dict(LP2_solution=float(ls.sum().sum() * w))
    acc = {k: 0.0 for k in ('LP2', 'A', 'B', 'C', 'A_rfinal', 'B_rfinal', 'C_rfinal', 'LP2_rused')}
    for ln in L.index:
        smax_pu = float(L.s_max_pu[ln]); vn2 = float(L.v_nom[ln]) ** 2
        S_c = float(L.s_nom[ln]); rating = smax_pu * S_c
        r_fin = float(L.r[ln]) / vn2; r_use = float(sol2.r_used[ln]) / vn2
        S_max = float(sol2.s_nom_max[ln]); S_ref = float(sol2.s_ref[ln])
        pts = dict(LP2=[0.5 * rating, rating], A=[0.5 * smax_pu * S_max, smax_pu * S_max],
                   B=[k / 4 * smax_pu * S_max for k in (1, 2, 3, 4)], C=[0.5 * smax_pu * S_ref, smax_pu * S_ref])
        f = s[ln].abs().values
        e = {'LP2': env(f, r_fin, pts['LP2']), 'LP2_rused': env(f, r_use, pts['LP2'])}
        for k in ('A', 'B', 'C'):
            e[k] = env(f, r_use, pts[k]); e[f'{k}_rfinal'] = env(f, r_fin, pts[k])
        E = {k: float(v.sum() * w) for k, v in e.items()}
        for k in acc:
            acc[k] += E[k]
        grid = np.linspace(0.3, 1.0, 141) * rating
        g2 = env(grid, r_fin, pts['LP2'])
        under = {k: float(np.max(1 - env(grid, r_fin, pts[k]) / np.where(g2 > 0, g2, np.nan))) for k in ('A', 'B', 'C')}
        q = np.quantile(f / rating, [0.5, 0.9, 1.0]) if rating > 0 else [np.nan] * 3
        rows.append(dict(line=ln, bus0=L.bus0[ln], bus1=L.bus1[ln], focus=bool({L.bus0[ln], L.bus1[ln]} & set(FOCUS_BUSES)),
                         S_v16=float(sol2.s_v16_prepared[ln]), S_ref_IT2=S_ref, S_cand=S_c, S_max=S_max, rating_MW=rating,
                         r_used_ohm=float(sol2.r_used[ln]), r_final_ohm=float(L.r[ln]), r_used_over_final=float(sol2.r_used[ln] / L.r[ln]) if L.r[ln] else np.nan,
                         flow_share_p50=q[0], flow_share_p90=q[1], flow_share_max=q[2],
                         loss_LP2_MWh=E['LP2'], loss_A_MWh=E['A'], loss_B_MWh=E['B'], loss_C_MWh=E['C'],
                         A_over_LP2=E['A'] / E['LP2'] if E['LP2'] else np.nan, B_over_LP2=E['B'] / E['LP2'] if E['LP2'] else np.nan,
                         C_over_LP2=E['C'] / E['LP2'] if E['LP2'] else np.nan,
                         A_rfinal_over_LP2=E['A_rfinal'] / E['LP2'] if E['LP2'] else np.nan, B_rfinal_over_LP2=E['B_rfinal'] / E['LP2'] if E['LP2'] else np.nan,
                         C_rfinal_over_LP2=E['C_rfinal'] / E['LP2'] if E['LP2'] else np.nan,
                         r_effect_LP2rused_over_LP2=E['LP2_rused'] / E['LP2'] if E['LP2'] else np.nan,
                         worst_pointwise_under_A_0p3_1=under['A'], worst_pointwise_under_B_0p3_1=under['B'], worst_pointwise_under_C_0p3_1=under['C'],
                         loss_solution_LP2_MWh=float(ls[ln].sum() * w)))
    T = pd.DataFrame(rows).sort_values('loss_LP2_MWh', ascending=False)
    T.to_csv(OUT / 'W8B_LOSS_ENVELOPE_BY_LINE.csv', index=False)
    tot.update({f'{k}_MWh': v for k, v in acc.items()})
    big = T[T.loss_LP2_MWh > 1000]
    def summ(col):
        return dict(lines_under_5pct=int((big[col] < 0.95).sum()), worst=big.nsmallest(5, col)[['line', col, 'loss_LP2_MWh']].round(4).to_dict('records'),
                    loss_weighted=float((big[col] * big.loss_LP2_MWh).sum() / big.loss_LP2_MWh.sum()))
    rep = dict(step='NEXT-08b loss-envelope comparison (read-only)', optimizer_calls=0, flows='LP2 candidate solution, s = p0 - loss/2, 2,920 x 3 h',
               validation=dict(LP2_envelope_at_own_flows_MWh=acc['LP2'], LP2_loss_solution_MWh=tot['LP2_solution'],
                               rel_diff=abs(acc['LP2'] - tot['LP2_solution']) / tot['LP2_solution']),
               totals_MWh=tot,
               ratios_to_LP2=dict(A=acc['A'] / acc['LP2'], B=acc['B'] / acc['LP2'], C=acc['C'] / acc['LP2'], A_rfinal=acc['A_rfinal'] / acc['LP2'],
                                  B_rfinal=acc['B_rfinal'] / acc['LP2'], C_rfinal=acc['C_rfinal'] / acc['LP2'], r_effect=acc['LP2_rused'] / acc['LP2']),
               lines_with_LP2_loss_over_1GWh=int(len(big)),
               A=summ('A_over_LP2'), B=summ('B_over_LP2'), C=summ('C_over_LP2'),
               pointwise_worst_0p3_1=dict(A=float(T.worst_pointwise_under_A_0p3_1.max()), B=float(T.worst_pointwise_under_B_0p3_1.max()),
                                         C=float(T.worst_pointwise_under_C_0p3_1.max())),
               r_used_over_final=dict(min=float(T.r_used_over_final.min()), max=float(T.r_used_over_final.max())),
               focus_lines=T[T.focus][['line', 'bus0', 'bus1', 'rating_MW', 'flow_share_p50', 'flow_share_p90', 'flow_share_max', 'loss_LP2_MWh',
                                       'A_over_LP2', 'B_over_LP2', 'C_over_LP2', 'r_used_over_final', 'worst_pointwise_under_B_0p3_1']].round(3).to_dict('records'))
    (OUT / 'W8B_LOSS_ENVELOPE_SUMMARY.json').write_text(json.dumps(rep, indent=1, default=float), encoding='utf-8')
    print(json.dumps({k: v for k, v in rep.items() if k != 'focus_lines'}, indent=1, default=float))
    pd.set_option('display.width', 250)
    print(pd.DataFrame(rep['focus_lines']).to_string())


if __name__ == '__main__':
    main()
