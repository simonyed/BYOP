#!/usr/bin/env python3
"""NEXT-08b zero-solver PTDF sensitivity diagnostic of the residual LP2 shed at p610 1 (researcher approval 2026-10-23).

Question: at the largest-gap steps, are the LP1 -> LP2 differences large enough to cause the extra p610 1 shed through the meshed
flow constraints? Uses only the sealed v2 candidate NetCDF and the saved LP1 / LP2 outputs; no optimizer, no write to any baseline.

Conventions (PyPSA 1.3, transmission_losses = 2 tangents):
  * Line-s = s (bus0 -> bus1); bus balance withdraws loss/2 at each end, so p0 = s + loss/2 and s = p0 - loss/2.
  * Rating row |s| + loss <= s_max_pu s_nom; tangents loss >= 2 r_pu p_k |s| - r_pu p_k^2, p_k = k/2 s_max_pu s_ref;
    loss <= r_pu (s_max_pu s_ref)^2 (loss_upper); loss >= 0; r_pu = r / v_nom^2.
  * KVL: s = PTDF @ (K s), K = bus x line incidence (+1 bus0, -1 bus1), PTDF from x_pu_eff with the PyPSA slack bus;
    a balanced transfer (+1 at A, -1 spread over a sink pattern w) is reference-independent: PTDF @ (e_A - w).
  * Binding: |s| + loss >= 0.995 x rating. Relief on a binding line = reduction of |s| (sign taken from the LP2 flow).

Tests:
  T0  PTDF reproduces the LP2 flows from the LP2 injections (validates PTDF, slack and the loss-split convention).
  T1  Objective consistency: the LP1 dispatch priced with LP2 costs vs the LP2 optimum (capex and shed price removed).
      v1.6 (lossless, known consistent) is the control. A negative difference beyond solver tolerance proves the LP1 dispatch
      is infeasible in LP2 (LP2 is optimal), i.e. a feasible-set difference between the two models at identical capacities.
  T2  r / tangent residual (S_ref vs final capacity, r_used vs r_final) at the LP2 flows of the shed steps: extra loss per line,
      tightening of each binding rating row, and the linear p610 1 shed that would absorb it if shed at p610 1 were the only
      control (single-control linear estimate; other redispatch is NOT evaluated).
  T3  loss_upper residual: LP1 loss above LP2's loss_upper r_pu (s_max_pu s_nom)^2 (= the quadratic loss at full rating, i.e.
      non-physical dissipation), per line and step; its linear flow effect on the LP2 binding lines vs that of the 95 MW shed.
  T4  Above-envelope dissipation inside LP2 itself (the same relaxation exists in every lossy run, incl. S0-S3).
Run on L2 from workflow/:  python byop/post/next08b_ptdf_sensitivity.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/run'))
R = WF / 'results/BYOP'
V2, V1, V16 = R / 'next08b_lp1_tangent_fix', R / 'next08_lossy_lp1', R / 'baseline_2025_tamu_v16'
BIND, W, MARGIN = 0.995, 3.0, 1.05
SHED_BUS = 'p610 1'
STEPS = ['2030-08-28 06:00:00', '2030-08-28 09:00:00', '2030-09-12 06:00:00', '2030-09-13 09:00:00']
OBJ_TOL_USD = 1e5


def envelope(s, r_pu, rating, segments=2):
    """PyPSA tangent lower envelope max(0, max_k 2 r p_k |s| - r p_k^2), p_k = k/segments x rating"""
    a = np.abs(s)
    out = np.zeros_like(a, dtype=float)
    for k in range(1, segments + 1):
        p = k / segments * rating
        out = np.maximum(out, 2 * r_pu * p * a - r_pu * p ** 2)
    return out


def ptdf(n):
    """dense PTDF (lines x buses) from x_pu_eff, PyPSA slack bus with zero column; returns PTDF, K, slack"""
    n.determine_network_topology()
    n.calculate_dependent_values()
    subs = n.sub_networks
    assert len(subs) == 1, f'expected one AC sub-network, got {len(subs)}'
    sn = subs.obj.iloc[0]
    sn.find_slack_bus()
    slack = sn.slack_bus
    L, buses = n.lines, n.buses.index
    bi = pd.Series(np.arange(len(buses)), buses)
    K = np.zeros((len(buses), len(L)))
    K[bi[L.bus0].values, np.arange(len(L))] = 1.0
    K[bi[L.bus1].values, np.arange(len(L))] = -1.0
    b = 1.0 / L.x_pu_eff.values
    B = K @ np.diag(b) @ K.T
    keep = np.array([x != slack for x in buses])
    Binv = np.zeros_like(B)
    Binv[np.ix_(keep, keep)] = np.linalg.inv(B[np.ix_(keep, keep)])
    return np.diag(b) @ K.T @ Binv, K, slack, bi


def objective_test(L):
    import loss_basis_lp1 as LB
    import baseline_v16_calibration as V16C
    v, _ = V16C.load_cfg()
    voll, shed1 = float(v['voll_USD_MWh']), float(LB.SHED_COST)

    def pair(obj1, eens1, sol, obj2, eens2):
        up = float((sol.s_nom_opt - sol.s_nom_input).sum())
        g1 = obj1 - LB.UPLIFT_COST * up - eens1 * shed1
        c12 = g1 + eens1 * voll
        return dict(lp1_objective=obj1, lp1_uplift_MVA=up, lp1_capex=LB.UPLIFT_COST * up, lp1_eens_MWh=eens1, lp1_operating_ex_shed=g1,
                    lp2_objective=obj2, lp2_eens_MWh=eens2, lp2_operating_ex_shed=obj2 - eens2 * voll,
                    lp1_dispatch_at_lp2_prices=c12, diff_vs_lp2_optimum=c12 - obj2,
                    verdict='LP1 dispatch NOT feasible in LP2' if c12 - obj2 < -OBJ_TOL_USD else 'consistent (LP2 optimum <= LP1 dispatch)')
    m16 = json.loads((V16 / 'LP1_METRICS.json').read_text())
    q16 = json.loads((V16 / 'BASELINE_V16_FIXED_ASSET_QA.json').read_text())
    out = dict(v16_lossless_control=pair(m16['objective_USD'], m16['shed']['eens_MWh'], pd.read_csv(V16 / 'LP1_LINE_SOLUTION.csv', index_col=0),
                                         q16['metrics']['objective_USD'], q16['acceptance']['eens_MWh']))
    for k, d in (('next08_v1', V1), ('next08b_v2', V2)):
        q1 = json.loads((d / 'LP1_LOSSY_IT2/LOSSY_LP1_QA.json').read_text())
        q2 = json.loads((d / 'LP2_LOSSY_CANDIDATE/LOSS_BASIS_LP2_QA.json').read_text())
        out[k] = pair(q1['objective'], q1['residual_shed']['eens_MWh'], pd.read_csv(d / 'LP1_LOSSY_IT2/LP1_LINE_SOLUTION.csv', index_col=0),
                      q2['metrics']['objective_USD'], q2['acceptance']['eens_MWh'])
    out['prices'] = dict(uplift_USD_per_MVA=LB.UPLIFT_COST, lp1_shed_USD_MWh=shed1, lp2_voll_USD_MWh=voll, tolerance_USD=OBJ_TOL_USD,
                         period_objective_weight=float(L['period_weight']))
    return out


def loss_upper_excess(d, vn, smax):
    """LP1-IT2 loss above the LP2 loss_upper of that chain's candidate (r_final, s_final); MWh by line, raw and with MARGIN"""
    sol = pd.read_csv(d / 'LP1_LOSSY_IT2/LP1_LINE_SOLUTION.csv', index_col=0)
    r_fin = sol.r_raw * (sol.s_nom_input / sol.s_nom_opt).clip(upper=1.0)
    up2 = r_fin / vn.reindex(sol.index) ** 2 * (smax * sol.s_nom_opt) ** 2
    up1 = sol.r_used / vn.reindex(sol.index) ** 2 * (smax * sol.s_nom_max) ** 2
    ll1 = pd.read_csv(d / 'LP1_LOSSY_IT2/line_loss.csv.gz', index_col=[0, 1])[sol.index]
    ex0, ex5 = (ll1 - up2).clip(lower=0), (ll1 - MARGIN * up2).clip(lower=0)
    return dict(ll1=ll1, up2=up2, ex5=ex5, summary=dict(
        lp1_loss_TWh=float(ll1.sum().sum() * W / 1e6), cells_over_lp2_upper=int((ex0 > 1e-3).sum().sum()),
        MWh_over_lp2_upper=float(ex0.sum().sum() * W), MWh_over_1p05_lp2_upper=float(ex5.sum().sum() * W),
        max_step_MW_over_1p05=float(ex5.sum(axis=1).max()), lp1_within_own_upper=bool((ll1 <= up1 * (1 + 1e-6) + 1e-3).all().all()),
        top_lines_MWh_over_1p05={k: round(v, 1) for k, v in (ex5.sum() * W).sort_values(ascending=False).head(12).items() if v > 0}))


def main():
    import pypsa
    n = pypsa.Network(str(V2 / 'baseline_2025_tamu_lossy_candidate.nc'))
    L = n.lines
    P, K, slack, bi = ptdf(n)
    buses = n.buses.index
    vn = n.buses.v_nom.reindex(L.bus0).set_axis(L.index)
    smax = float(L.s_max_pu.unique()[0])
    assert n.lines_t.s_max_pu.empty and len(L.s_max_pu.unique()) == 1
    rating = smax * L.s_nom
    sol = pd.read_csv(V2 / 'LP1_LOSSY_IT2/LP1_LINE_SOLUTION.csv', index_col=0).reindex(L.index)
    r_fin_pu, r_use_pu = L.r / vn ** 2, sol.r_used / vn ** 2
    assert np.allclose(L.r, sol.r_raw * (sol.s_nom_input / sol.s_nom_opt).clip(upper=1.0)) and np.allclose(L.s_nom, sol.s_nom_opt)
    lp2 = V2 / 'LP2_LOSSY_CANDIDATE'
    p0 = pd.read_csv(lp2 / 'line_flow_p0.csv.gz', index_col=[0, 1])[L.index]
    ll2 = pd.read_csv(lp2 / 'line_loss.csv.gz', index_col=[0, 1])[L.index]
    s2 = p0 - ll2 / 2
    use = (s2.abs() + ll2) / rating

    rep = dict(step='NEXT-08b zero-solver PTDF sensitivity of the residual p610 1 shed', solver_calls=0, slack_bus=slack,
               conventions=__doc__.split('Conventions')[1].split('Tests:')[0].strip())
    # T0: PTDF validation on the LP2 flows (all steps)
    S = s2.values.T                                               # lines x steps
    err = np.abs(P @ (K @ S) - S)
    rep['T0_ptdf_reproduces_lp2_flows'] = dict(max_abs_err_MW=float(err.max()), pass_=bool(err.max() < 0.5))
    L_ = dict(period_weight=float(n.investment_period_weightings.objective.iloc[0]))
    rep['T1_objective_consistency'] = objective_test(L_)

    # sink / source patterns for balanced transfers (reference-independent)
    g = n.generators[n.generators.carrier != 'load_shed']
    thermal = g[g.carrier.isin(['CCGT', 'OCGT', 'gas_steam', 'coal', 'nuclear', 'biomass', 'CCGT-95CCS'])].groupby('bus').p_nom.sum()

    def pattern(weights):
        w = np.zeros(len(buses)); s = weights[weights > 0]
        w[bi[s.index].values] = (s / s.sum()).values
        return w

    def patterns(ts):
        k = (2030, pd.Timestamp(ts))
        wind = g[g.carrier == 'onwind']
        pmax = n.generators_t.p_max_pu.reindex(columns=wind.index).loc[k].fillna(1.0)
        load = n.loads_t.p_set.loc[k].groupby(n.loads.bus).sum()
        return {'slack': pattern(pd.Series({slack: 1.0})), 'thermal_capacity': pattern(thermal),
                'load_at_step': pattern(load), 'wind_available_at_step': pattern((wind.p_nom * pmax).groupby(wind.bus).sum())}

    e_shed = np.zeros(len(buses)); e_shed[bi[SHED_BUS]] = 1.0
    gen_buses = sorted(set(g.bus))
    steps = {}
    for ts in STEPS:
        k = (2030, ts)
        sl, ul, sg = s2.loc[k], use.loc[k], np.sign(s2.loc[k])
        bnd = ul.index[ul >= BIND]
        pats = patterns(ts)
        # T2: r / tangent residual at the LP2 flows
        e2 = envelope(sl.values, r_fin_pu.values, rating.values)
        e1 = envelope(sl.values, r_use_pu.values, (smax * sol.s_ref).values)
        dL = pd.Series(e2 - e1, L.index)
        t2 = {}
        for name, w in pats.items():
            rel = pd.Series(-(sg * (P @ (e_shed - w))).values, L.index)            # |s| reduction per MW shed at p610 1
            ds_loss = pd.Series(P @ (-(np.abs(K) @ dL.values) / 2 + w * dL.sum()), L.index)   # flow shift of the extra loss withdrawals
            tight = (dL + sg * ds_loss)[bnd]
            need = {l: (float(tight[l] / rel[l]) if rel[l] > 1e-6 else (0.0 if tight[l] <= 0 else float('inf'))) for l in bnd}
            t2[name] = dict(relief_per_MW_shed={l: round(float(rel[l]), 4) for l in bnd},
                            tightening_MW={l: round(float(tight[l]), 4) for l in bnd},
                            single_control_shed_MW=max([0.0] + list(need.values())),
                            lines_not_relievable_by_p610_1_shed=[l for l, v in need.items() if not np.isfinite(v)])
        # T3: LP1 loss above LP2 loss_upper at this step, flow effect on the binding lines
        ll1 = pd.read_csv(V2 / 'LP1_LOSSY_IT2/line_loss.csv.gz', index_col=[0, 1]).loc[k].reindex(L.index)
        up2 = r_fin_pu * rating ** 2
        E = (ll1 - MARGIN * up2).clip(lower=0)
        t3 = {}
        for name in ('wind_available_at_step', 'thermal_capacity', 'load_at_step'):
            w = pats[name]
            ds_E = pd.Series(P @ (-(np.abs(K) @ E.values) / 2 + w * E.sum()), L.index)
            rel_E = (-sg * ds_E)[bnd]
            rel_shed = pd.Series(-(sg * (P @ (e_shed - w))).values, L.index)[bnd] * 95.1
            t3[name] = dict(relief_from_lp1_excess_sinks_MW=rel_E.round(2).to_dict(), relief_from_95MW_shed_MW=rel_shed.round(2).to_dict())
        steps[ts] = dict(binding=list(bnd), shed_at_p610_1_MW=None,
                         T2_r_tangent=dict(extra_loss_total_MW=round(float(dL.sum()), 3), extra_loss_on_binding_MW={l: round(float(dL[l]), 4) for l in bnd},
                                           by_sink=t2),
                         T3_loss_upper=dict(lp1_excess_over_1p05_lp2_upper_MW=round(float(E.sum()), 1),
                                            by_line={l: dict(MW=round(float(E[l]), 1), bus0=L.bus0[l], bus1=L.bus1[l]) for l in E.index[E > 0.5]},
                                            flow_effect_on_binding=t3))
    shed = pd.read_csv(lp2 / 'shed_by_bus.csv.gz', index_col=[0, 1])
    for ts in STEPS:
        steps[ts]['shed_at_p610_1_MW'] = round(float(shed.loc[(2030, ts), SHED_BUS]), 2)
    rep['steps'] = steps
    rep['T3_year'] = {k: loss_upper_excess(d, vn, smax)['summary'] for k, d in (('next08_v1', V1), ('next08b_v2', V2))}
    # T4: above-envelope dissipation inside LP2
    env2 = pd.DataFrame(envelope(s2.values, r_fin_pu.values[None, :], rating.values[None, :]), s2.index, L.index)
    above = (ll2 - env2).clip(lower=0)
    at_up = ll2 >= (r_fin_pu * rating ** 2) * (1 - 1e-4) - 1e-6
    rep['T4_lp2_above_envelope'] = dict(lp2_loss_TWh=float(ll2.sum().sum() * W / 1e6), envelope_TWh=float(env2.sum().sum() * W / 1e6),
                                        above_envelope_TWh=float(above.sum().sum() * W / 1e6), cells_at_loss_upper=int(at_up.sum().sum()),
                                        top_lines_above_MWh=(above.sum() * W).sort_values(ascending=False).head(8).round(0).to_dict())
    (V2 / 'W8B_PTDF_SENSITIVITY.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    by = pd.DataFrame({'bus0': L.bus0, 'bus1': L.bus1, 's_nom': L.s_nom.round(1), 's_ref': sol.s_ref.round(1), 'r_final': L.r, 'r_used': sol.r_used,
                       'lp2_loss_upper_MW': (r_fin_pu * rating ** 2).round(3)})
    ex = loss_upper_excess(V2, vn, smax)
    by['lp1_MWh_over_1p05_lp2_upper'] = (ex['ex5'].sum() * W).reindex(L.index).round(1)
    by['lp2_above_envelope_MWh'] = (above.sum() * W).round(1)
    by.to_csv(V2 / 'W8B_PTDF_SENSITIVITY_BY_LINE.csv')
    print(json.dumps({k: rep[k] for k in ('T0_ptdf_reproduces_lp2_flows', 'T1_objective_consistency', 'T3_year', 'T4_lp2_above_envelope')}, indent=1, default=str))
    for ts, v in steps.items():
        print(ts, 'shed', v['shed_at_p610_1_MW'], 'binding', v['binding'])
        print('  T2 extra loss MW', v['T2_r_tangent']['extra_loss_total_MW'], {k: (round(x['single_control_shed_MW'], 3), x['lines_not_relievable_by_p610_1_shed']) for k, x in v['T2_r_tangent']['by_sink'].items()})
        print('  T3 excess MW', v['T3_loss_upper']['lp1_excess_over_1p05_lp2_upper_MW'], v['T3_loss_upper']['by_line'])
        for k, x in v['T3_loss_upper']['flow_effect_on_binding'].items():
            print('   ', k, 'sinks', x['relief_from_lp1_excess_sinks_MW'], '| shed', x['relief_from_95MW_shed_MW'])


if __name__ == '__main__':
    main()
