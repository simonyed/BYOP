#!/usr/bin/env python3
"""C1 continuation v1.4.1 (2026-10-22): explain the existing C1 results from SAVED outputs and READ-ONLY networks.
No optimize / solve / calibration call (pypsa.Network is only read). Run on L2 from workflow/:
    python byop/post/c1_explain.py
Outputs (results/BYOP/C1_FIXED_ASSET_DIAG/explain/):
  C1_CALIBRATION_VS_C1_SETUP.csv   calibrate_2025 (102.2 MWh residual) vs C1 CALIBRATED annual, item by item with file / function evidence
  C1_UPLIFT_LINE_CHECK.csv         the 18 uplift lines: raw / calibrated s_nom, x, r, x ratio, binding hours BASE vs CALIBRATED
  C1_SHED_BY_BUS_MONTH.csv         CALIBRATED annual shed by bus x month (and BASE for reference)
  C1_SHED_EVENTS_LABELLED.csv      every shedding event with model coordinate AND source 2025 Native Load row / HE label
  C1_SHED_BUS_NEIGHBOURHOOD.csv    lines incident to shed buses: uplift flag, s_nom, x, binding hours in both cases
  C1_STORAGE_CHECK.csv             storage settings (efficiencies, losses, cyclic flags in the source networks), SOC transition check,
                                   generator marginal-cost signs - what the saved outputs can and cannot show
  C1_EXPLAIN_SUMMARY.json
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

C1 = BP.C1_RESULTS
OUT = C1 / 'explain'
BT = BP.BASE_TAMU_DIR


def main():
    import pypsa
    OUT.mkdir(parents=True, exist_ok=True)
    raw = pypsa.Network(str(BT / 'baseline_2025_tamu_raw_uncalibrated.nc'))
    cal = pypsa.Network(str(BT / 'baseline_2025_tamu_prepared.nc'))
    led = pd.read_csv(BT / 'TAMU_2025_CALIBRATION_LP.csv').set_index('line')
    audit = json.loads((BT / 'baseline_2025_tamu_audit.json').read_text())
    cfg = __import__('yaml').safe_load((WF / 'config/config.byop_c1_fixed_asset_diag.yaml').read_text())['c1']
    mets = {(d.name.split('__')[0], d.name.split('__')[1]): json.loads((d / 'metrics.json').read_text())
            for d in C1.glob('C1_NETWORK_*__*') if '__attempt' not in d.name and (d / 'metrics.json').exists()}
    ca = mets[('C1_NETWORK_CALIBRATED', 'ANNUAL_3H')]
    # ---------------- setup comparison (evidence = file / function / field)
    su_raw = raw.storage_units[~raw.storage_units.p_nom_extendable & (raw.storage_units.build_year <= 2025)]
    rows = [
        dict(item='network read by the LP', calibration='baseline_2025_tamu_raw_uncalibrated.nc (raw s_nom, raw x / r), lines s_nom_extendable, s_nom_min = s_nom',
             c1_calibrated='baseline_2025_tamu_prepared.nc: s_nom = raw + uplift on 18 lines AND x, r divided by (s_nom_cal / s_nom_raw) on those lines',
             evidence='build_2025_baseline_tamu.calibrate_2025 (c.lines s_nom_extendable / s_nom_min); main(): loop over TAMU_2025_CALIBRATION_LP rows sets s_nom, x / ratio, r / ratio',
             status='CONFIRMED_INPUT_DIFFERENCE'),
        dict(item='impedance during the calibration LP', calibration='x, r fixed at the raw values while s_nom is a variable (linear power flow keeps impedance constant)',
             c1_calibrated='x, r of the 18 uplift lines are 1.06-5.64 x lower than in the LP that sized them (see C1_UPLIFT_LINE_CHECK)',
             evidence='C1_UPLIFT_LINE_CHECK.csv x_raw / x_cal = s ratio', status='CONFIRMED_INPUT_DIFFERENCE (effect on shed NOT isolated)'),
        dict(item='uplift threshold', calibration='LP optimum s_nom_opt - s_nom on every line', c1_calibrated='only lines with added > 0.5 MVA written to the network (18 lines)',
             evidence='main(): cal = cal[cal.added_MVA > 0.5]', status='CONFIRMED (sub-0.5 MVA uplifts dropped; magnitude small)'),
        dict(item='shed price', calibration='SHED_COST = 1e6 USD/MWh; line uplift capital_cost 2e6 USD/MW', c1_calibrated=f"VOLL {cfg['voll_USD_MWh']} USD/MWh; no line variable",
             evidence='build_2025_baseline_tamu SHED_COST / UPLIFT_COST; config.byop_c1_fixed_asset_diag.yaml voll_USD_MWh', status='CONFIRMED_DIFFERENCE (both far above every generator cost)'),
        dict(item='objective', calibration='operating cost + 1e6 x shed + 2e6 x line uplift (line capacity bought where cheaper than shed)',
             c1_calibrated='operating cost + VOLL x shed (fixed lines)', evidence='calibrate_2025 vs c1_fixed_asset_diagnostics.prepare', status='CONFIRMED_DIFFERENT_EXPERIMENTS'),
        dict(item='fleet', calibration='remove p_nom_extendable or build_year > 2025 generators / storage', c1_calibrated='same rule', evidence='calibrate_2025 / prepare()', status='SAME'),
        dict(item='global constraints', calibration='all removed', c1_calibrated='all removed (lv_limit)', evidence='same', status='SAME'),
        dict(item='storage cyclic flag', calibration=f"as stored in the raw network: cyclic_state_of_charge True for {int(su_raw.cyclic_state_of_charge.sum())} of {len(su_raw)} 2025 units",
             c1_calibrated='forced True for every unit (annual cyclic)', evidence='calibrate_2025 leaves storage_units untouched; prepare() sets cyclic_state_of_charge = True',
             status='CONFIRMED_DIFFERENCE' if not su_raw.cyclic_state_of_charge.all() else 'SAME'),
        dict(item='storage initial SOC (non-cyclic units in calibration)', calibration=f"state_of_charge_initial sum {float(su_raw.state_of_charge_initial.sum()):.1f} MWh",
             c1_calibrated='cyclic: SOC(t0-1) = SOC(T)', evidence='raw network storage_units', status='INFO'),
        dict(item='snapshots / weights', calibration='2,920 x 3 h, weight 3 (same network snapshots)', c1_calibrated='2,920 x 3 h, weight 3', evidence='network snapshot_weightings', status='SAME'),
        dict(item='shed accounting', calibration=f"residual_shed_MWh = sum(shed p x weight) = {audit['calibration']['residual_shed_MWh']:.4f} (all buses, all steps)",
             c1_calibrated=f"shed_MWh = sum(shed p x weight) = {ca['shed_MWh']:.1f}; event threshold 1e-3 MW per bus", evidence='calibrate_2025 return; c1 metrics()', status='SAME_UNIT (MWh, weighted)'),
        dict(item='solver', calibration='Gurobi barrier, Crossover 0, BarConvTol 1e-8, NumericFocus 2 (termination optimal per audit json)',
             c1_calibrated='attempt 1: barrier Crossover 0 -> suboptimal; final: Crossover 1, NumericFocus 2, BarHomogeneous 1 -> optimal (shed 72,905.12 vs 72,905.11 MWh)',
             evidence='C1_SOLVE_LOG.csv, C1_SUPERSEDED_ATTEMPTS.csv', status='SOLVER STATUS NOT THE CAUSE (both attempts give the same shed)'),
    ]
    pd.DataFrame(rows).to_csv(OUT / 'C1_CALIBRATION_VS_C1_SETUP.csv', index=False, lineterminator='\n')
    # ---------------- uplift lines
    lb = pd.read_csv(C1 / 'C1_NETWORK_BASE__ANNUAL_3H/lines.csv').set_index('line')
    lc = pd.read_csv(C1 / 'C1_NETWORK_CALIBRATED__ANNUAL_3H/lines.csv').set_index('line')
    up = pd.DataFrame(dict(bus0=raw.lines.bus0, bus1=raw.lines.bus1, s_raw=raw.lines.s_nom, s_cal=cal.lines.s_nom, x_raw=raw.lines.x, x_cal=cal.lines.x,
                           r_raw=raw.lines.r, r_cal=cal.lines.r)).loc[led.index]
    up['s_ratio'] = up.s_cal / up.s_raw; up['x_ratio_raw_over_cal'] = up.x_raw / up.x_cal
    up['binding_h_BASE'] = lb.binding_hours.reindex(up.index); up['binding_h_CAL'] = lc.binding_hours.reindex(up.index)
    up['max_loading_BASE'] = lb.max_loading.reindex(up.index); up['max_loading_CAL'] = lc.max_loading.reindex(up.index)
    up.to_csv(OUT / 'C1_UPLIFT_LINE_CHECK.csv', lineterminator='\n', float_format='%.6f')
    # ---------------- shed location / time with source labels
    h1 = pd.read_csv(BP.ANCHOR2025_DERIVED / 'ERCOT_NATIVE_LOAD_2025_1H.csv', usecols=['source_row_1based', 'Hour Ending'])
    t0 = pd.Timestamp('2030-01-01 00:00:00')
    ev = pd.read_csv(C1 / 'C1_SHEDDING_EVENTS.csv')
    def src(ts, step_h, end=False):
        h = int((pd.Timestamp(ts) - t0) / pd.Timedelta(hours=1)) + (step_h - 1 if end else 0)
        return int(h1.source_row_1based.iloc[h]), str(h1['Hour Ending'].iloc[h])
    lab = []
    for r in ev.itertuples():
        step = 3 if r.kind == 'ANNUAL_3H' else 1
        (rs, hs), (re_, he) = src(r.start, step), src(r.end, step, end=True)
        lab.append(dict(r._asdict(), source_row_start=rs, source_HE_start=hs, source_row_end=re_, source_HE_end=he,
                        time_note='model coordinate (2030) kept; source = 2025 Native Load row order (HE labels incl. DST / 24:00), not UTC'))
    lab = pd.DataFrame(lab).drop(columns=['Index'])
    lab.to_csv(OUT / 'C1_SHED_EVENTS_LABELLED.csv', index=False, lineterminator='\n', float_format='%.6f')
    ann = lab[lab.kind == 'ANNUAL_3H'].copy()
    ann['month'] = pd.to_datetime(ann.start).dt.month
    sbm = ann.pivot_table(index=['case', 'bus'], columns='month', values='energy_MWh', aggfunc='sum', fill_value=0.0)
    sbm['total_MWh'] = sbm.sum(axis=1)
    sbm.reset_index().sort_values(['case', 'total_MWh'], ascending=[True, False]).to_csv(OUT / 'C1_SHED_BY_BUS_MONTH.csv', index=False, lineterminator='\n', float_format='%.3f')
    # neighbourhood of shed buses (CALIBRATED annual)
    sb = set(ann[ann.case == 'C1_NETWORK_CALIBRATED'].bus)
    L = cal.lines
    nb = L[L.bus0.isin(sb) | L.bus1.isin(sb)].copy()
    nb = pd.DataFrame(dict(line=nb.index, bus0=nb.bus0, bus1=nb.bus1, uplift_line=nb.index.isin(led.index), s_nom_raw=raw.lines.s_nom.reindex(nb.index).values,
                           s_nom_cal=nb.s_nom.values, x_raw=raw.lines.x.reindex(nb.index).values, x_cal=nb.x.values,
                           binding_h_BASE=lb.binding_hours.reindex(nb.index).values, binding_h_CAL=lc.binding_hours.reindex(nb.index).values,
                           max_loading_CAL=lc.max_loading.reindex(nb.index).values))
    nb.to_csv(OUT / 'C1_SHED_BUS_NEIGHBOURHOOD.csv', index=False, lineterminator='\n', float_format='%.4f')
    # ---------------- storage evidence
    s = cal.storage_units[~cal.storage_units.p_nom_extendable & (cal.storage_units.build_year <= 2025)]
    soc = pd.read_csv(C1 / 'C1_NETWORK_CALIBRATED__ANNUAL_3H/storage_soc.csv.gz', index_col=[0, 1])
    socb = pd.read_csv(C1 / 'C1_NETWORK_BASE__ANNUAL_3H/storage_soc.csv.gz', index_col=[0, 1])
    st = pd.DataFrame(dict(bus=s.bus, carrier=s.carrier, p_nom=s.p_nom, max_hours=s.max_hours, efficiency_store=s.efficiency_store,
                           efficiency_dispatch=s.efficiency_dispatch, standing_loss=s.standing_loss, marginal_cost=s.marginal_cost,
                           cyclic_in_source_network=s.cyclic_state_of_charge,
                           roundtrip_loss_share=1 - s.efficiency_store * s.efficiency_dispatch))
    st['soc_first_step_CAL'] = soc.iloc[0].reindex(st.index).values; st['soc_last_step_CAL'] = soc.iloc[-1].reindex(st.index).values
    st['soc_max_CAL'] = soc.max().reindex(st.index).values; st['soc_max_BASE'] = socb.max().reindex(st.index).values
    st['energy_cap_MWh'] = st.p_nom * st.max_hours
    st['note'] = ('cyclic LP: SOC(first step) = SOC(last step) x (1-standing_loss)^w + w (eta_s p_store - p_dispatch / eta_d) of the first step; '
                  'equality of first and last SOC is NOT required. Per-unit p_store / p_dispatch and bus prices were NOT saved')
    st.to_csv(OUT / 'C1_STORAGE_CHECK.csv', lineterminator='\n', float_format='%.6f')
    g = cal.generators
    mc = g[~g.p_nom_extendable & (g.build_year <= 2025)].groupby('carrier').marginal_cost.agg(['min', 'max', 'mean'])
    summ = dict(
        no_solver_call=True,
        calibration_residual_MWh=audit['calibration']['residual_shed_MWh'], c1_calibrated_annual_shed_MWh=ca['shed_MWh'],
        c1_base_annual_shed_MWh=mets[('C1_NETWORK_BASE', 'ANNUAL_3H')]['shed_MWh'],
        uplift_lines_binding_CAL=int((up.binding_h_CAL > 0).sum()), uplift_lines_binding_BASE=int((up.binding_h_BASE > 0).sum()),
        shed_buses_CAL=sorted(sb), shed_bus_incident_lines=len(nb), shed_bus_incident_uplift_lines=int(nb.uplift_line.sum()),
        shed_bus_incident_lines_binding_CAL=int((nb.binding_h_CAL > 0).sum()),
        cal_shed_by_month_MWh=ann[ann.case == 'C1_NETWORK_CALIBRATED'].groupby('month').energy_MWh.sum().round(1).to_dict(),
        largest_events_CAL=ann[ann.case == 'C1_NETWORK_CALIBRATED'].nlargest(5, 'energy_MWh')[['bus', 'start', 'source_HE_start', 'duration_h', 'energy_MWh', 'peak_MW']].to_dict('records'),
        storage=dict(units=len(st), carriers=st.carrier.value_counts().to_dict(), roundtrip_loss_share_range=[float(st.roundtrip_loss_share.min()), float(st.roundtrip_loss_share.max())],
                     standing_loss_max=float(st.standing_loss.max()), cyclic_in_source=int(st.cyclic_in_source_network.sum()),
                     marginal_cost_input_by_carrier=mc.round(3).to_dict('index'),
                     missing_outputs=['per-unit p_store / p_dispatch time series', 'bus marginal prices / duals', 'per-unit curtailment']),
    )
    (OUT / 'C1_EXPLAIN_SUMMARY.json').write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))
    print(up.round(3).to_string())
    print(nb.round(2).to_string())


if __name__ == '__main__':
    main()
