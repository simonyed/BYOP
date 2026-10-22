#!/usr/bin/env python3
"""WP v1.5 collector (no solve): compare the existing v1.4 C1 CALIBRATED annual result, X1 stage 1 and X1 stage 2.
    python byop/post/c1_x1_collect.py
Outputs (results/BYOP/C1_X1_STORAGE_V15/): C1_X1_STAGE_COMPARISON.csv, C1_X1_SHED_BY_BUS_MONTH.csv, C1_X1_STORAGE_BY_UNIT.csv,
C1_X1_LINE_COMPARISON.csv, C1_X1_SHED_EVENTS_LABELLED.csv, C1_X1_QA.json
"""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

OUT = BP.RESULTS / 'C1_X1_STORAGE_V15'
C1 = BP.C1_RESULTS
S1D, S2D = OUT / 'stage1_X1', OUT / 'stage2_min_throughput'
KEY_LINES = ['TL12', 'TL69', 'TL40', 'TL26', 'TL43', 'TL63']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
REQUIRED = ['storage_p_store.csv.gz', 'storage_p_dispatch.csv.gz', 'storage_soc.csv.gz', 'storage_static.csv', 'generators_p.csv.gz',
            'generators_available.csv.gz', 'generators_static.csv', 'lines_p0.csv.gz', 'lines_p1.csv.gz', 'lines_static.csv',
            'lines_saturated.csv.gz', 'shed_by_bus.csv.gz', 'storage_by_unit.csv', 'shedding_events.csv', 'lines.csv',
            'generation_by_carrier.csv', 'metrics.json']


def is_optimal(s, t):
    return str(s) == 'ok' and str(t) == 'optimal'


def shed_by_month(d, label):
    s = pd.read_csv(d / 'shed_by_bus.csv.gz', index_col=[0, 1])
    s = s.T.groupby(level=0).sum().T * 3.0                               # weight 3 h; columns are bus names (one shed unit per bus)
    mon = pd.to_datetime(s.index.get_level_values(1)).month
    t = s.groupby(mon).sum().T
    t['total_MWh'] = t.sum(axis=1)
    return t.assign(case=label).reset_index().rename(columns={'index': 'bus'})


def collect():
    c = yaml.safe_load((WF / 'config/config.byop_c1_x1_storage_v15.yaml').read_text())['c1x1']
    m_cal = json.loads((C1 / 'C1_NETWORK_CALIBRATED__ANNUAL_3H/metrics.json').read_text())
    m1 = json.loads((S1D / 'metrics.json').read_text())
    m2 = json.loads((S2D / 'metrics.json').read_text()) if (S2D / 'metrics.json').exists() else None
    eta = pd.read_csv(S1D / 'storage_static.csv', index_col=0)
    es, ed = float(eta.efficiency_store.iloc[0]), float(eta.efficiency_dispatch.iloc[0])
    assert np.allclose(eta.efficiency_store, es) and np.allclose(eta.efficiency_dispatch, ed)
    cal_loss = m_cal['storage_charge_MWh'] * (1 - es) + m_cal['storage_dispatch_MWh'] * (1 / ed - 1)
    keys = ['shed_MWh', 'shed_max_MW', 'shed_hours', 'shed_buses', 'longest_shed_event_h', 'binding_lines', 'line_binding_hours_total',
            'curtailment_wind_MWh', 'curtailment_solar_MWh', 'storage_charge_MWh', 'storage_dispatch_MWh', 'storage_simultaneous_MWh',
            'storage_simultaneous_steps', 'balance_residual_max_abs_MW', 'load_MWh']
    rows = []
    for k in keys:
        rows.append(dict(metric=k, v14_CALIBRATED=m_cal.get(k), X1_stage1=m1.get(k), X1_stage2=m2.get(k) if m2 else None))
    rows += [dict(metric='storage_throughput_MWh', v14_CALIBRATED=m_cal['storage_charge_MWh'] + m_cal['storage_dispatch_MWh'], X1_stage1=m1['storage_throughput_MWh'],
                  X1_stage2=m2['storage_throughput_MWh'] if m2 else None),
             dict(metric='storage_conversion_loss_MWh', v14_CALIBRATED=cal_loss, X1_stage1=m1['storage_conversion_loss_MWh'], X1_stage2=m2['storage_conversion_loss_MWh'] if m2 else None),
             dict(metric='economic_cost_USD', v14_CALIBRATED=m_cal['objective_USD'], X1_stage1=m1['F_recomputed_USD'], X1_stage2=m2['F_stage2_recomputed_USD'] if m2 else None),
             dict(metric='solver_objective_USD_or_MWh', v14_CALIBRATED=m_cal['objective_USD'], X1_stage1=m1['F_star_USD'], X1_stage2=m2['stage2_objective_value'] if m2 else None),
             dict(metric='storage_state_equation_max_abs_residual_MWh', v14_CALIBRATED=None, X1_stage1=m1['storage_state_equation_max_abs_residual_MWh'],
                  X1_stage2=m2['storage_state_equation_max_abs_residual_MWh'] if m2 else None)]
    cmp_ = pd.DataFrame(rows)
    cmp_['X1_stage1_minus_v14'] = pd.to_numeric(cmp_.X1_stage1, errors='coerce') - pd.to_numeric(cmp_.v14_CALIBRATED, errors='coerce')
    cmp_['X1_stage2_minus_stage1'] = pd.to_numeric(cmp_.X1_stage2, errors='coerce') - pd.to_numeric(cmp_.X1_stage1, errors='coerce')
    cmp_.to_csv(OUT / 'C1_X1_STAGE_COMPARISON.csv', index=False, lineterminator='\n', float_format='%.6f')
    # shed by bus x month
    cal = pd.read_csv(C1 / 'explain/C1_SHED_BY_BUS_MONTH.csv')
    cal = cal[cal.case == 'C1_NETWORK_CALIBRATED'].rename(columns=lambda x: int(x) if str(x).isdigit() else x).assign(case='v14_CALIBRATED')
    parts = [cal, shed_by_month(S1D, 'X1_stage1')] + ([shed_by_month(S2D, 'X1_stage2')] if m2 else [])
    sb = pd.concat(parts, ignore_index=True).fillna(0.0)
    sb = sb[sb.total_MWh > 1e-6] if len(sb) else sb
    sb.to_csv(OUT / 'C1_X1_SHED_BY_BUS_MONTH.csv', index=False, lineterminator='\n', float_format='%.3f')
    # storage by unit
    u1 = pd.read_csv(S1D / 'storage_by_unit.csv', index_col=0).add_suffix('_stage1')
    u = u1.join(pd.read_csv(S2D / 'storage_by_unit.csv', index_col=0).add_suffix('_stage2')) if m2 else u1
    u.to_csv(OUT / 'C1_X1_STORAGE_BY_UNIT.csv', lineterminator='\n', float_format='%.6f')
    # lines
    lc = pd.read_csv(C1 / 'C1_NETWORK_CALIBRATED__ANNUAL_3H/lines.csv').set_index('line')
    l1 = pd.read_csv(S1D / 'lines.csv').set_index('line')
    st = pd.read_csv(S1D / 'lines_static.csv', index_col=0)
    au = pd.read_csv(OUT / 'C1_X1_LINE_INPUT_AUDIT.csv', index_col=0)
    p01 = pd.read_csv(S1D / 'lines_p0.csv.gz', index_col=[0, 1])
    ln = pd.DataFrame(dict(bus0=st.bus0, bus1=st.bus1, uplift_line=au.uplift_line, limit_MW=st.limit_MW, x_X1=st.x, x_calibrated=au.x_calibrated,
                           binding_h_v14_CAL=lc.binding_hours, binding_h_X1_s1=l1.binding_hours, max_loading_v14_CAL=lc.max_loading, max_loading_X1_s1=l1.max_loading,
                           mean_abs_flow_MW_X1_s1=p01.abs().mean()))
    if m2:
        l2 = pd.read_csv(S2D / 'lines.csv').set_index('line')
        p02 = pd.read_csv(S2D / 'lines_p0.csv.gz', index_col=[0, 1])
        ln['binding_h_X1_s2'] = l2.binding_hours; ln['mean_abs_flow_MW_X1_s2'] = p02.abs().mean()
        ln['max_abs_flow_change_s2_vs_s1_MW'] = (p02 - p01).abs().max()
    ln['binding_h_change_X1s1_vs_v14'] = ln.binding_h_X1_s1 - ln.binding_h_v14_CAL
    ln['key_line'] = ln.index.isin(KEY_LINES)
    ln.to_csv(OUT / 'C1_X1_LINE_COMPARISON.csv', lineterminator='\n', float_format='%.6f')
    # events with source labels
    h1 = pd.read_csv(BP.ANCHOR2025_DERIVED / 'ERCOT_NATIVE_LOAD_2025_1H.csv', usecols=['source_row_1based', 'Hour Ending'])
    t0 = pd.Timestamp('2030-01-01')
    evs = []
    for lab, d in (('X1_stage1', S1D), ('X1_stage2', S2D)):
        if not (d / 'shedding_events.csv').exists():
            continue
        e = pd.read_csv(d / 'shedding_events.csv')
        if not len(e):
            continue
        hs = ((pd.to_datetime(e.start) - t0) / pd.Timedelta(hours=1)).astype(int)
        he = ((pd.to_datetime(e.end) - t0) / pd.Timedelta(hours=1)).astype(int) + 2
        e = e.assign(stage=lab, source_row_start=h1.source_row_1based.values[hs], source_HE_start=h1['Hour Ending'].values[hs],
                     source_row_end=h1.source_row_1based.values[he], source_HE_end=h1['Hour Ending'].values[he],
                     time_note='model coordinate kept; source = 2025 Native Load row order (HE, DST / 24:00 kept), not UTC')
        evs.append(e)
    ev = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame()
    ev.to_csv(OUT / 'C1_X1_SHED_EVENTS_LABELLED.csv', index=False, lineterminator='\n', float_format='%.6f')
    # QA
    log = pd.read_csv(OUT / 'C1_X1_SOLVE_LOG.csv')
    au_ok = bool((au.s_nom_X1 == au.s_nom_calibrated).all() and set(au.index[au.impedance_restored]) == set(au.index[au.uplift_line]) and au.uplift_line.sum() == 18)
    comp = {nm: {f: bool((d / f).exists() and (d / f).stat().st_size > 0) for f in REQUIRED} for nm, d in (('stage1', S1D), ('stage2', S2D))}
    prices = dict(stage1_economic=(S1D / 'economic_marginal_price.csv.gz').exists(),
                  stage2_duals_separate=(S2D / 'stage2_nodal_balance_duals_NOT_economic_prices.csv.gz').exists() and not (S2D / 'economic_marginal_price.csv.gz').exists())
    ch = subprocess.run(['git', '-C', str(WF.parent), 'diff', '--name-only', 'cf5df4f0', 'HEAD', '--', 'workflow/byop/inputs', 'workflow/results/BYOP/baseline_2025_tamu',
                         'workflow/results/BYOP/C1_FIXED_ASSET_DIAG'], capture_output=True, text=True).stdout.split()
    gates = {p.name: yaml.safe_load(p.read_text())['mainline']['run_authorization'] for p in (WF / 'config').glob('config.byop_ercot_mainline*.yaml')}
    s1ok = is_optimal(m1['status'], m1['termination'])
    s2ok = bool(m2 and is_optimal(m2['status'], m2['termination']))
    qa = dict(stage='C1-X1 / storage validation (WP v1.5)',
              solver_termination=dict(stage1=s1ok, stage2=s2ok),
              effective_stages=int((log.counted_as == 'effective').sum()), retries=int((log.counted_as == 'retry').sum()), solver_calls=int(len(log)),
              x1_input_identity=au_ok, no_build_variables=True,
              stage2_bounds=dict(F_bound_ok=m2.get('F_bound_ok') if m2 else None, E_bound_ok=m2.get('E_bound_ok') if m2 else None,
                                 F_star=m1['F_star_USD'], F_recomputed_stage1=m1['F_recomputed_USD'], F_stage2=m2.get('F_stage2_recomputed_USD') if m2 else None,
                                 epsilon_F=m2.get('epsilon_F_USD') if m2 else None, E_star=m1['E_star_MWh'], E_stage2=m2.get('E_stage2_MWh') if m2 else None,
                                 epsilon_E=m2.get('epsilon_E_MWh') if m2 else None),
              balance_residual_max_abs_MW=max(m1['balance_residual_max_abs_MW'], m2['balance_residual_max_abs_MW'] if m2 else 0.0),
              storage_state_equation_max_abs_residual_MWh=max(m1['storage_state_equation_max_abs_residual_MWh'], m2['storage_state_equation_max_abs_residual_MWh'] if m2 else 0.0),
              output_completeness=comp, output_complete=all(all(v.values()) for v in comp.values()), prices=prices,
              inputs_or_old_results_changed_since_cf5df4f0=ch, formal_gates=gates,
              big_files_sha256={f'{nm}/{f}': sha(d / f) for nm, d in (('stage1_X1', S1D), ('stage2_min_throughput', S2D)) for f in REQUIRED if (d / f).exists() and f.endswith('.gz')})
    (OUT / 'C1_X1_QA.json').write_text(json.dumps(qa, indent=1, default=str))
    print(json.dumps({k: v for k, v in qa.items() if k != 'big_files_sha256'}, indent=1, default=str))
    print(cmp_.round(3).to_string())


if __name__ == '__main__':
    collect()
