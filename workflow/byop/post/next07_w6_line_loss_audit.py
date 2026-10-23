#!/usr/bin/env python3
"""NEXT-07 W6 (read-only, NO solver): engineering audit of line resistance, units and the loss approximation in the v1.6 baseline,
before any lossy re-validation. Per line (v1.6 network + v1.6 LINE_LEDGER):
  units      PyPSA r_pu_eff (calculate_dependent_values) vs r / v_nom^2 (ohm on a 1 MVA base); MW loss = r_pu_eff * S^2
  geometry   ledger length (km), r and x per km, x / r
  capacity   TAMU raw s_nom (member line) vs final v1.6 s_nom (ReEDS sum + calibration uplift): capacity ratio
  losses     share of a full-rating flow lost: r_pu_eff * s_max_pu * s_nom (formal); the same for the raw member line at its own rating;
             and with r scaled by raw / final s_nom (capacity represented as parallel conductor) - the engineering-consistent
             candidate for uplifted lines (x unchanged: researcher-approved X1 rule for the flow split)
  tangents   2-segment tangent error at 0.9 x rating (PyPSA tangents at 1/2 and 1 x rating) vs the exact quadratic
Run on L2 from workflow/: python byop/post/next07_w6_line_loss_audit.py   -> results/BYOP/next07_loss_basis/W6_LINE_LOSS_AUDIT.csv / .json"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
B16 = WF / 'results/BYOP/baseline_2025_tamu_v16'
OUT = WF / 'results/BYOP/next07_loss_basis'


def main():
    import pypsa
    OUT.mkdir(parents=True, exist_ok=True)
    n = pypsa.Network(str(B16 / 'baseline_2025_tamu_prepared.nc'))
    n.calculate_dependent_values()
    L = n.lines.copy()
    led = pd.read_csv(B16 / 'LINE_LEDGER.csv').set_index('name')
    vn = n.buses.v_nom.reindex(L.bus0).values
    d = pd.DataFrame(index=L.index)
    d['bus0'], d['bus1'], d['v_nom_kV'] = L.bus0, L.bus1, vn
    d['r_ohm'], d['x_ohm'] = L.r, L.x
    d['r_pu_eff'] = L.r_pu_eff
    d['r_over_vnom2'] = L.r / vn ** 2
    d['unit_check_rel_err'] = (d.r_pu_eff - d.r_over_vnom2).abs() / d.r_over_vnom2.replace(0, np.nan)
    d['length_km'] = led.length.reindex(L.index)
    d['r_ohm_per_km'] = d.r_ohm / d.length_km
    d['x_ohm_per_km'] = d.x_ohm / d.length_km
    d['x_over_r'] = d.x_ohm / d.r_ohm
    d['s_nom_final'], d['s_max_pu'] = L.s_nom, L.s_max_pu
    d['rating_MW'] = L.s_nom * L.s_max_pu
    d['tamu_raw_s_nom'] = led.tamu_raw_s_nom.reindex(L.index)
    d['n_member_lines'] = led.n_member_lines.reindex(L.index)
    d['calibration_uplift_MVA'] = led.calibration_uplift_MVA.reindex(L.index).fillna(0.0)
    d['capacity_ratio_final_over_raw'] = d.s_nom_final / d.tamu_raw_s_nom
    d['uplifted_in_v16'] = d.calibration_uplift_MVA > 0.5
    d['loss_share_at_rating_formal'] = d.r_pu_eff * d.rating_MW
    d['loss_share_at_raw_rating'] = d.r_pu_eff * d.tamu_raw_s_nom * d.s_max_pu
    d['r_parallel_equiv_ohm'] = d.r_ohm * (d.tamu_raw_s_nom / d.s_nom_final).clip(upper=1.0)
    d['loss_share_at_rating_parallel_equiv'] = d.r_parallel_equiv_ohm / vn ** 2 * d.rating_MW
    p = 0.9 * d.rating_MW
    exact = d.r_pu_eff * p ** 2
    t1 = 2 * d.r_pu_eff * (d.rating_MW / 2) * p - d.r_pu_eff * (d.rating_MW / 2) ** 2
    t2 = 2 * d.r_pu_eff * d.rating_MW * p - d.r_pu_eff * d.rating_MW ** 2
    d['tangent_underestimate_at_0p9_rating'] = 1 - np.maximum(t1, t2) / exact
    # PyPSA rating row |s| + loss <= rating: sending end limited to rating - loss/2 (conservative by loss/2 vs a sending-end limit)
    d['sending_end_conservatism_at_rating_MW'] = 0.5 * d.r_pu_eff * d.rating_MW ** 2 / (1 + d.loss_share_at_rating_formal)
    d = d.sort_values('loss_share_at_rating_formal', ascending=False)
    d.to_csv(OUT / 'W6_LINE_LOSS_AUDIT.csv')
    up = d[d.uplifted_in_v16]
    summ = dict(
        work_package='BYOP_NEXT_07', step='W6 static line-loss audit', optimizer_calls=0, lines=int(len(d)),
        unit_check_max_rel_err=float(d.unit_check_rel_err.max()),
        loss_formula='PyPSA tangents: loss >= 2 r_pu_eff p_k s - r_pu_eff p_k^2 at p_k = 1/2, 1 x rating; loss <= r_pu_eff rating^2; '
                     'rating row |s| + loss <= s_max_pu s_nom (Neumann & Brown 2022); bus balance -loss/2 at each end',
        tangent_underestimate_at_0p9_rating_max=float(d.tangent_underestimate_at_0p9_rating.max()),
        uplifted_lines=int(len(up)), uplifted_total_MVA=float(up.calibration_uplift_MVA.sum()),
        loss_share_at_rating=dict(all_median=float(d.loss_share_at_rating_formal.median()), all_p90=float(d.loss_share_at_rating_formal.quantile(0.9)),
                                  uplifted_median=float(up.loss_share_at_rating_formal.median()), non_uplifted_median=float(d[~d.uplifted_in_v16].loss_share_at_rating_formal.median()),
                                  lines_above_5pct=int((d.loss_share_at_rating_formal > 0.05).sum()),
                                  uplifted_above_5pct=int((up.loss_share_at_rating_formal > 0.05).sum())),
        uplifted_with_parallel_equiv_r=dict(median=float(up.loss_share_at_rating_parallel_equiv.median()), max=float(up.loss_share_at_rating_parallel_equiv.max())),
        r_ohm_per_km=dict(median=float(d.r_ohm_per_km.median()), p10=float(d.r_ohm_per_km.quantile(0.1)), p90=float(d.r_ohm_per_km.quantile(0.9))),
        top_lines=d.head(12)[['bus0', 'bus1', 'v_nom_kV', 'length_km', 'r_ohm', 'r_ohm_per_km', 'tamu_raw_s_nom', 's_nom_final', 'capacity_ratio_final_over_raw',
                              'uplifted_in_v16', 'loss_share_at_rating_formal', 'loss_share_at_raw_rating', 'loss_share_at_rating_parallel_equiv']].round(4).reset_index().to_dict('records'))
    (OUT / 'W6_LINE_LOSS_AUDIT.json').write_text(json.dumps(summ, indent=1, default=float), encoding='utf-8')
    print(json.dumps({k: v for k, v in summ.items() if k != 'top_lines'}, indent=1, default=float))
    pd.set_option('display.width', 250)
    print(pd.DataFrame(summ['top_lines']).to_string())
    print(up[['length_km', 'r_ohm_per_km', 'tamu_raw_s_nom', 's_nom_final', 'capacity_ratio_final_over_raw', 'loss_share_at_rating_formal',
              'loss_share_at_rating_parallel_equiv']].round(3).to_string())


if __name__ == '__main__':
    main()
