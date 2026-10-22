#!/usr/bin/env python3
"""Stage B2.5 method audit of the solved B2-R case (pure post-processing, no solver; B2-R tables are only read):
    python byop/post/stage_b25_audit.py results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1 \
        --out results/BYOP/mainline/B25_METHOD_AUDIT

STAGE_B25_ERM_2026_METHOD_AUDIT.csv   per bus x year: request / service / delay, E0, ERM binding and shadow price at
                                      the bus row, POI and serve_cap duals, procedure year, method flag (descriptive)
STAGE_B25_S0_S1_SHED_EXPOSURE.csv     per bus x year x kind: S0 and S1 existing-customer shed (MWh, peak MW), S1 - S0;
                                      2028 snapshot overlap of Red Oak and p630 13 / 14 in S0 (S1 per-snapshot shed
                                      was not saved by B2-R -> DATA_NOT_SAVED)
STAGE_B25_RELIABILITY_FLAGS.csv       B2-R reliability screen items with their real values and PASS / FAIL
STAGE_B25_COST_BOOK_DECOMPOSITION.csv collect_mainline.cost_book_decomposition() on the B2-R S0 / S1 summary
"""
from __future__ import annotations

import argparse, importlib.util, json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collect_mainline', HERE / 'collect_mainline.py')
CM = importlib.util.module_from_spec(spec); spec.loader.exec_module(CM)
INP = HERE.parent / 'inputs'
NAMES = {'p600 0': 'Helios', 'p610 2': 'Abilene', 'p630 2': 'Red Oak', 'p630 4': 'Shackelford', 'p630 5': 'Temple',
         'p630 6': 'Midlothian', 'p630 9': 'Denton', 'p650 0': 'TX1/SAT14'}


def shed_table(f, stress, tag):
    w = CM._weights(f.index, stress)
    e = f.mul(w, axis=0).groupby(level=0).sum()
    rows = []
    for col in e.columns:
        kind = 'inherited_ramp' if col.endswith(' inherited_ramp_unserved') else ('native_background' if col.endswith(' load_shed') else 'other')
        bus = col.replace(' inherited_ramp_unserved', '').replace(' load_shed', '')
        for y in e.index:
            rows.append(dict(scenario=tag, bus=bus, year=int(y), kind=kind, shed_MWh=float(e.loc[y, col]),
                             peak_shed_MW=float(f[col][f.index.get_level_values(0) == y].max())))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('case'); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    C, O = Path(a.case), Path(a.out)
    O.mkdir(parents=True, exist_ok=True)
    man = json.loads((C / 'case_manifest.json').read_text())
    stress = man['mainline']['stress']['days']
    duals = pd.read_csv(C / 'duals.csv')
    t48 = pd.read_csv(C / 'STAGE_B2_48_BUS_YEAR_GRID_ONLY_F1F2.csv')
    e0 = pd.read_csv(INP / 'poi/GREAL_POI_E0_SCHEDULE.csv')
    poi_a = pd.read_csv(INP / 'poi/GREAL_POI_ASSUMPTIONS.csv').set_index('bus')
    # ------------------------------------------------------------------ A. ERM 2026 method audit
    erm = duals[duals.constraint.astype(str).str.startswith('ERM')]
    sc = duals[duals.constraint.astype(str).str.startswith('serve_cap')]
    erm_tot = erm.groupby(['scenario', 'year']).agg(erm_dual_total=('dual_raw', 'sum'), erm_binding_any=('binding', 'any'))
    rows = []
    for r in t48.itertuples():
        e_ = erm[(erm.scenario == 'S1_EARLIEST') & (erm.zone == r.site) & (erm.year == r.year)]
        s_ = sc[(sc.scenario == 'S1_EARLIEST') & (sc.zone == r.site) & (sc.year == r.year)]
        ee = e0[e0.bus == r.site]
        e0_pre = float(ee[ee.preapproved & (ee.COD <= r.year)].MW.sum())
        tot = erm_tot.loc[('S1_EARLIEST', r.year)] if ('S1_EARLIEST', r.year) in erm_tot.index else None
        poi_bind = bool(r.delay_IT_MW > 0.5 and r.total_import_peak_MW >= 0.999 * r.equipment_total_MW - 1e-2 and r.equipment_total_MW > 0)
        first = r.year == 2026
        rows.append(dict(
            year=r.year, site=r.site, name=NAMES[r.site], requested_IT_MW=r.requested_IT_MW, served_IT_MW=r.served_IT_MW, delay_IT_MW=r.delay_IT_MW,
            E0_preapproved_available_MW=e0_pre, equipment_total_MW=r.equipment_total_MW,
            ERM_binding_bus_row=bool(e_.binding.any()) if len(e_) else None, ERM_shadow_price_bus_row=float(e_.dual_raw.sum()) if len(e_) else None,
            ERM_binding_system=bool(tot['erm_binding_any']) if tot is not None else None, ERM_shadow_price_system_sum=float(tot['erm_dual_total']) if tot is not None else None,
            serve_cap_dual_USD_per_MW_IT_yr=float(s_.dual_USD_per_MW_IT_yr.sum()) if len(s_) else None, poi_eq_dual_abs=r.poi_eq_dual_abs,
            POI_binding=poi_bind, procedure_ready_year=float(poi_a.loc[r.site, 'earliest_grid_COD_base']),
            procedure_ready=bool(r.year >= float(poi_a.loc[r.site, 'earliest_grid_COD_base'])),
            method_flag='ERM_2026_METHOD_FLAG' if first and r.delay_IT_MW > 0.5 else '',
            interpretation=('ERM-02 B first-year zero headroom: POI equipment available and not binding, ERM row binding' if first and r.delay_IT_MW > 0.5 and e0_pre > r.requested_IT_MW * r.PUE
                            else ('multiple constraints possible (no pre-approved equipment in 2026); ERM row binding' if first and r.delay_IT_MW > 0.5
                                  else ('POI / procedure (serve_cap dual = service value)' if r.delay_IT_MW > 0.5 else ''))),
            source='STAGE_B2_48_BUS_YEAR_GRID_ONLY_F1F2.csv; duals.csv (S1_EARLIEST); GREAL_POI_E0_SCHEDULE.csv',
            interpretation_limit='descriptive by year; no ERM-relaxation counterfactual was solved -> not a causal share'))
    erm_a = pd.DataFrame(rows)
    tot_d = float(t48.delay_IT_MW.clip(lower=0).sum())
    d26 = float(t48[t48.year == 2026].delay_IT_MW.clip(lower=0).sum())
    summary = pd.DataFrame([dict(year='ALL', site='SUMMARY', name='total_delay_MW_IT_year', delay_IT_MW=tot_d),
                            dict(year='2026', site='SUMMARY', name='method_flagged_2026_delay_MW_IT_year', delay_IT_MW=d26),
                            dict(year='2027-2031', site='SUMMARY', name='post_2026_delay_MW_IT_year', delay_IT_MW=tot_d - d26)])
    pd.concat([erm_a, summary], ignore_index=True).to_csv(O / 'STAGE_B25_ERM_2026_METHOD_AUDIT.csv', index=False)
    # ------------------------------------------------------------------ B. S0 / S1 shed exposure
    s0 = shed_table(pd.read_csv(C / 'S0_shed_by_snapshot_frozen.csv.gz', index_col=[0, 1], parse_dates=[1]), stress, 'S0')
    s1b = pd.read_csv(C / 'shed_by_bus_S1_EARLIEST.csv') if (C / 'shed_by_bus_S1_EARLIEST.csv').exists() else pd.DataFrame()
    ex = s0.rename(columns={'shed_MWh': 'S0_shed_MWh', 'peak_shed_MW': 'S0_peak_shed_MW'}).drop(columns='scenario')
    if len(s1b):
        s1l = s1b.melt(id_vars='bus', var_name='year', value_name='S1_shed_MWh').assign(year=lambda d: d.year.astype(int), kind='native_background')
        ex = ex.merge(s1l, on=['bus', 'year', 'kind'], how='outer')
    ex['S1_shed_MWh'] = ex.get('S1_shed_MWh', np.nan)
    ex.loc[ex.kind == 'native_background', 'S1_shed_MWh'] = ex.loc[ex.kind == 'native_background', 'S1_shed_MWh'].fillna(0.0)
    ex['S1_peak_shed_MW'] = 'DATA_NOT_SAVED (B2-R saved S1 shed only as bus-year MWh)'
    ex['S1_minus_S0_MWh'] = ex.S1_shed_MWh - ex.S0_shed_MWh.fillna(0.0)
    ex.loc[ex.kind == 'inherited_ramp', 'S1_shed_MWh'] = np.nan
    ex['note'] = np.where(ex.kind == 'inherited_ramp', 'S1 inherited-ramp shed per bus not saved by B2-R (total 0.503 MWh in summary)', '')
    ex = ex[(ex.S0_shed_MWh.fillna(0) > 1e-6) | (ex.S1_shed_MWh.fillna(0) > 1e-6)]
    sm = pd.read_csv(C / 'scenario_summary.csv').set_index('scenario')
    ex = pd.concat([ex, pd.DataFrame([dict(bus='ALL_ERCOT', year='2026-2031', kind='all', S0_shed_MWh=float(sm.load_shed_MWh['S0']),
                                           S1_shed_MWh=float(sm.load_shed_MWh['S1_EARLIEST']),
                                           S1_minus_S0_MWh=float(sm.load_shed_MWh['S1_EARLIEST'] - sm.load_shed_MWh['S0']),
                                           note='result comparison only - not a BYOP improvement (no S2 in B2-R)')])], ignore_index=True)
    ex['source'] = 'S0_shed_by_snapshot_frozen.csv.gz x sample weights; shed_by_bus_S1_EARLIEST.csv; scenario_summary.csv'
    # 2028 overlap of S0 shed at Red Oak and p630 13 / 14 (S0 snapshots only)
    f = pd.read_csv(C / 'S0_shed_by_snapshot_frozen.csv.gz', index_col=[0, 1], parse_dates=[1])
    f28 = f[f.index.get_level_values(0) == 2028]
    cols = [c for c in f28.columns if c.split(' load_shed')[0] in ('p630 2', 'p630 13', 'p630 14') and c.endswith(' load_shed')]
    on = (f28[cols] > 1e-3)
    ov = pd.DataFrame(dict(snapshots_2028=len(f28), **{f'{c}_snapshots': int(on[c].sum()) for c in cols},
                           all_three_same_snapshot=int(on.all(axis=1).sum()), any_of_three=int(on.any(axis=1).sum()),
                           stress_snapshots_with_any=int(on.any(axis=1)[pd.DatetimeIndex(f28.index.get_level_values(1)).normalize().isin(
                               pd.DatetimeIndex([d['day'] for d in stress]))].sum())), index=[0])
    ov = ov.melt(var_name='metric', value_name='value').assign(bus='OVERLAP_2028_S0', kind='snapshot_count',
                                                               note='S0 only; S1 per-snapshot shed DATA_NOT_SAVED; line flows DATA_NOT_SAVED in B2-R')
    pd.concat([ex, ov], ignore_index=True).to_csv(O / 'STAGE_B25_S0_S1_SHED_EXPOSURE.csv', index=False)
    # ------------------------------------------------------------------ B. reliability flags
    s0y = s0.groupby(['year', 'kind']).shed_MWh.sum()
    tot = float(s0.shed_MWh.sum()); peak = float(s0.peak_shed_MW.max())
    inh = float(s0[s0.kind == 'inherited_ramp'].groupby('year').shed_MWh.sum().max())
    nh = float(sm.no_harm_max_violation_MW.get('S1_EARLIEST', np.nan))
    fl = pd.DataFrame([
        dict(flag='S0_total_shed_le_1000_MWh', value=tot, threshold=1000.0, result='PASS' if tot <= 1000 else 'FAIL'),
        dict(flag='S0_bus_peak_le_10_MW', value=peak, threshold=10.0, result='PASS' if peak <= 10 else 'FAIL',
             note=f"max at {s0.loc[s0.peak_shed_MW.idxmax(), 'bus']} {int(s0.loc[s0.peak_shed_MW.idxmax(), 'year'])}"),
        dict(flag='S0_inherited_ramp_le_1_MWh_per_year', value=inh, threshold=1.0, result='PASS' if inh <= 1 else 'FAIL'),
        dict(flag='S0_RELIABILITY_REVIEW_REQUIRED', value=None, threshold=None, result='ON' if (tot > 1000 or peak > 10 or inh > 1) else 'OFF'),
        dict(flag='no_harm_existing_customers (S1 <= S0 + 0.001 MW, per generator x snapshot)', value=nh, threshold=0.001,
             result='PASS' if man['checks'].get('no_harm_existing_customers') is True else 'FAIL',
             note='max violation equals the constraint slack 0.001 MW (edge of the allowed margin), from the model check'),
        dict(flag='ERM_2026_METHOD_FLAG', value=d26, threshold=None, result='ON', note='descriptive 2026 delay; ERM row binding in S0 and S1 2026 only'),
        dict(flag='S0CAL_LINE_FLOWS_PENDING_DIAGNOSTIC_EXPORT', value=None, threshold=None, result='ON',
             note='B2-R did not save link flows; B2.5-E adds the export for the next solve')])
    fl['source'] = 'B2-R case files (see STAGE_B25_METHOD_AUDIT_REPORT.md)'
    fl.to_csv(O / 'STAGE_B25_RELIABILITY_FLAGS.csv', index=False)
    # ------------------------------------------------------------------ C. cost books
    cb = CM.cost_book_decomposition(sm)
    cb.to_csv(O / 'STAGE_B25_COST_BOOK_DECOMPOSITION.csv', index=False)
    print(json.dumps(dict(written=sorted(p.name for p in O.glob('STAGE_B25_*.csv')), total_delay=tot_d, d2026=d26, s0_shed=tot,
                          cost_identity=list(cb.identity_check)), indent=1))


if __name__ == '__main__':
    main()
