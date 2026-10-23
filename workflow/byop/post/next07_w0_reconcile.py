#!/usr/bin/env python3
"""NEXT-07 W0 (read-only, NO solver): corrected reconciliation of the original S0 existing-customer shed, with every share stated
as numerator / denominator / unit. Reads only the frozen S0 outputs (S0_shed_by_snapshot_frozen.csv.gz, S0_RESULT.json,
shed_by_bus_S0.csv) and the A2 SOC segment map of the same code; recomputes everything independently of the NEXT-06 W1 tables
and then cross-checks those tables. Run from workflow/ (local or L2):
    python byop/post/next07_w0_reconcile.py
Writes current_work_pckg/BYOP_NEXT_07/W0_SHED_RECONCILIATION_CORRECTED.csv and W0_RECONCILIATION_VERDICT.json.
"""
from __future__ import annotations

import hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
SRC = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
SEG = WF / 'results/BYOP/post_v16_a2_static/_structural_merged/A2_SOC_SEGMENT_MAP_S0.csv'
N06 = WF / 'results/BYOP/next06_s0_diagnostic'
OUT = ROOT / 'current_work_pckg/BYOP_NEXT_07'
REPORTED_TOTAL, REPORTED_2026_NATIVE = 54205.7791, 51049.2775
FAR_WEST = ['p610 4', 'p620 6', 'p620 7']           # NEXT-06 W1 pocket
TOL = 0.05                                          # MWh, package W0.1
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def segment_of(index):
    sm = pd.read_csv(SEG, parse_dates=['start', 'end'])
    w = pd.Series(np.nan, index=index); kind = pd.Series('', index=index, dtype=object)
    per = index.get_level_values(0); ts = pd.DatetimeIndex(index.get_level_values(1))
    for r in sm.itertuples():
        msk = (per == r.period) & (ts >= r.start) & (ts <= r.end)
        w[msk] = r.w_generators_h; kind[msk] = r.kind
    return w, kind, sm


def ratio(num, den, num_def, den_def):
    return dict(value=num / den if den else None, numerator_MWh=num, denominator_MWh=den, numerator=num_def, denominator=den_def, unit='MWh / MWh')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    f = SRC / 'S0_shed_by_snapshot_frozen.csv.gz'
    raw = pd.read_csv(f, index_col=[0, 1], parse_dates=[1])
    w, kind, sm = segment_of(raw.index)
    assert not w.isna().any(), 'snapshot without a segment weight'
    shed = raw.clip(lower=0.0)                       # solver noise of order 1e-10 MW
    noise = float((raw.clip(upper=0.0)).abs().to_numpy().sum())
    res = json.loads((SRC / 'S0_RESULT.json').read_text(encoding='utf-8'))
    rep_total = float(res.get('acceptance', {}).get('values', {}).get('existing_shed_MWh', REPORTED_TOTAL))
    long = shed.stack().rename('MW').reset_index()
    long.columns = ['period', 'timestep', 'unit', 'MW']
    long['category'] = np.where(long.unit.str.endswith(' inherited_ramp_unserved'), 'inherited_ramp', 'native')
    long['bus'] = long.unit.str.replace(' inherited_ramp_unserved$', '', regex=True).str.replace(' load_shed$', '', regex=True)
    key = pd.MultiIndex.from_arrays([long.period, long.timestep])
    long['weight_h'] = w.reindex(key).values; long['segment_kind'] = kind.reindex(key).values
    long['raw_3h_MWh'] = long.MW * 3.0; long['weighted_MWh'] = long.MW * long.weight_h
    long['night_00_09'] = pd.DatetimeIndex(long.timestep).hour <= 9
    long['shed_snapshot'] = long.MW > 1e-6
    # bus x year x segment_kind x category (all buses with any shed, every kind listed even if 0)
    g = long.groupby(['bus', 'period', 'segment_kind', 'category'])
    tab = g.agg(raw_3h_MWh=('raw_3h_MWh', 'sum'), weighted_MWh=('weighted_MWh', 'sum'), peak_MW=('MW', 'max'),
                shed_snapshots=('shed_snapshot', 'sum')).reset_index()
    tab['night_shed_snapshots'] = long[long.shed_snapshot & long.night_00_09].groupby(['bus', 'period', 'segment_kind', 'category']).size() \
        .reindex(pd.MultiIndex.from_frame(tab[['bus', 'period', 'segment_kind', 'category']])).fillna(0).astype(int).values
    tab = tab[tab.weighted_MWh > 1e-6].copy()
    tab['weight_h'] = tab.segment_kind.map({'SAMPLED_WEEK': float(sm[sm.kind == 'SAMPLED_WEEK'].w_generators_h.iloc[0]), 'B7_STRESS_ONLY': 3.0})
    tab['weight_ratio_to_3h'] = tab.weight_h / 3.0
    tot = float(tab.weighted_MWh.sum())
    y26 = tab[tab.period == 2026]
    tab['share_of_all_year_total'] = tab.weighted_MWh / tot
    tab['share_of_2026_total'] = np.where(tab.period == 2026, tab.weighted_MWh / float(y26.weighted_MWh.sum()), np.nan)
    tab['far_west_pocket'] = tab.bus.isin(FAR_WEST)
    tab['denominator_note'] = ('share_of_all_year_total = row weighted MWh / sum of 2026-2031 weighted MWh (' + f'{tot:.3f}'
                               + '); share_of_2026_total = row / 2026 weighted MWh (native + inherited); weighted_MWh = MW x weight_h; raw_3h_MWh = MW x 3 h')
    tab = tab.sort_values(['period', 'weighted_MWh'], ascending=[True, False])
    tab.to_csv(OUT / 'W0_SHED_RECONCILIATION_CORRECTED.csv', index=False)

    by = lambda d, k: {str(a): float(b) for a, b in d.groupby(k).weighted_MWh.sum().items()}
    w26 = float(y26.weighted_MWh.sum()); w26n = float(y26[y26.category == 'native'].weighted_MWh.sum())
    sw_all = float(tab[tab.segment_kind == 'SAMPLED_WEEK'].weighted_MWh.sum()); b7_all = float(tab[tab.segment_kind == 'B7_STRESS_ONLY'].weighted_MWh.sum())
    fw26 = y26[y26.bus.isin(FAR_WEST)]
    fw26_sw = float(fw26[fw26.segment_kind == 'SAMPLED_WEEK'].weighted_MWh.sum()); fw26_b7 = float(fw26[fw26.segment_kind == 'B7_STRESS_ONLY'].weighted_MWh.sum())
    per_bus = {}
    for b in ['p620 6', 'p620 7', 'p610 4', 'p620 3', 'p630 2']:
        d = y26[y26.bus == b]
        per_bus[b] = {k: dict(weighted_MWh=float(d[d.segment_kind == k].weighted_MWh.sum()), raw_3h_MWh=float(d[d.segment_kind == k].raw_3h_MWh.sum()),
                              shed_snapshots=int(d[d.segment_kind == k].shed_snapshots.sum()), night_shed_snapshots=int(d[d.segment_kind == k].night_shed_snapshots.sum()))
                      for k in ('SAMPLED_WEEK', 'B7_STRESS_ONLY')}
        tw = sum(v['weighted_MWh'] for v in per_bus[b].values())
        per_bus[b]['stress_day_share_of_bus_2026_weighted'] = per_bus[b]['B7_STRESS_ONLY']['weighted_MWh'] / tw if tw else None
    raw26 = float(y26.raw_3h_MWh.sum()); raw26_sw = float(y26[y26.segment_kind == 'SAMPLED_WEEK'].raw_3h_MWh.sum())
    raw26_b7 = float(y26[y26.segment_kind == 'B7_STRESS_ONLY'].raw_3h_MWh.sum())
    swr = float(sm[sm.kind == 'SAMPLED_WEEK'].w_generators_h.iloc[0])
    # cross-check against the NEXT-06 W1 table (read only) and the run's own per-bus report
    n06 = pd.read_csv(N06 / 'W1_S0_SHED_SNAPSHOT_WEIGHTS.csv')
    rep_bus = pd.read_csv(SRC / 'shed_by_bus_S0.csv')
    checks = dict(
        total_vs_S0_RESULT_abs_MWh=abs(tot - rep_total),
        total_vs_reported_54205_7791_abs_MWh=abs(tot - REPORTED_TOTAL),
        native_2026_vs_reported_51049_2775_abs_MWh=abs(w26n - REPORTED_2026_NATIVE),
        sampled_plus_b7_minus_total_abs_MWh=abs(sw_all + b7_all - tot),
        native_plus_inherited_minus_total_abs_MWh=abs(float(tab.groupby('category').weighted_MWh.sum().sum()) - tot),
        n06_w1_table_total_abs_MWh=abs(float(n06.weighted_MWh.sum()) - tot),
        weights_sum_h_by_period={str(int(p)): float(v) for p, v in w.groupby(level=0).sum().items()},
        negative_noise_clipped_MW_sum=noise)
    ok = (checks['total_vs_S0_RESULT_abs_MWh'] < TOL and checks['total_vs_reported_54205_7791_abs_MWh'] < TOL
          and checks['native_2026_vs_reported_51049_2775_abs_MWh'] < TOL and checks['sampled_plus_b7_minus_total_abs_MWh'] < 1e-6
          and checks['native_plus_inherited_minus_total_abs_MWh'] < 1e-6 and checks['n06_w1_table_total_abs_MWh'] < TOL
          and all(abs(v - 8760.0) < 1e-6 for v in checks['weights_sum_h_by_period'].values()))
    ver = dict(
        work_package='BYOP_NEXT_07', step='W0', solver_calls=0,
        inputs=dict(shed_file=str(f.relative_to(ROOT)), shed_file_sha256=sha(f), s0_result=str((SRC / 'S0_RESULT.json').relative_to(ROOT)),
                    s0_result_sha256=sha(SRC / 'S0_RESULT.json'), segment_map=str(SEG.relative_to(ROOT)), segment_map_sha256=sha(SEG),
                    shed_by_bus_S0=str((SRC / 'shed_by_bus_S0.csv').relative_to(ROOT)), shed_by_bus_S0_sha256=sha(SRC / 'shed_by_bus_S0.csv'),
                    n06_w1_table_sha256=sha(N06 / 'W1_S0_SHED_SNAPSHOT_WEIGHTS.csv')),
        snapshots=dict(rows=int(len(raw)), per_period=int(len(raw) // raw.index.get_level_values(0).nunique()), units=int(raw.shape[1]),
                       sampled_week_weight_h=swr, sampled_week_weight_ratio_to_3h=swr / 3.0, b7_weight_h=3.0),
        totals_MWh=dict(all_years_weighted=tot, by_year_weighted=by(tab, 'period'), by_category_all_years=by(tab, 'category'),
                        by_segment_kind_all_years=by(tab, 'segment_kind'), y2026_weighted_all=w26, y2026_weighted_native=w26n,
                        y2026_weighted_inherited_ramp=w26 - w26n, y2026_raw_3h_all=raw26, y2026_raw_3h_sampled_week=raw26_sw, y2026_raw_3h_b7=raw26_b7,
                        y2026_far_west_weighted=float(fw26.weighted_MWh.sum()), y2026_far_west_sampled_week_weighted=fw26_sw,
                        y2026_far_west_b7_weighted=fw26_b7),
        shares=dict(
            y2026_native_of_all_years=ratio(w26n, tot, '2026 native weighted', '2026-2031 weighted sum (all categories)'),
            sampled_week_of_all_years=ratio(sw_all, tot, 'SAMPLED_WEEK weighted, all years', '2026-2031 weighted sum'),
            b7_of_all_years=ratio(b7_all, tot, 'B7_STRESS_ONLY weighted, all years', '2026-2031 weighted sum'),
            far_west_2026_of_all_years=ratio(float(fw26.weighted_MWh.sum()), tot, 'Far West pocket 2026 weighted (both kinds)', '2026-2031 weighted sum'),
            far_west_2026_sampled_week_of_all_years=ratio(fw26_sw, tot, 'Far West pocket 2026 SAMPLED_WEEK weighted', '2026-2031 weighted sum'),
            far_west_2026_of_2026=ratio(float(fw26.weighted_MWh.sum()), w26, 'Far West pocket 2026 weighted', '2026 weighted (native + inherited)'),
            y2026_sampled_week_of_2026=ratio(float(y26[y26.segment_kind == 'SAMPLED_WEEK'].weighted_MWh.sum()), w26, '2026 SAMPLED_WEEK weighted', '2026 weighted')),
        far_west_and_key_buses_2026=per_bus,
        corrections_to_next06=[
            dict(statement='"94 % of all S0 shed is the Far West pocket" (W1 section (a))',
                 correct=f"94.2 % is ALL 2026 native shed / 2026-2031 sum. The Far West pocket {FAR_WEST} in 2026 is "
                         f"{float(fw26.weighted_MWh.sum()) / tot:.1%} of the 2026-2031 sum (its SAMPLED_WEEK part {fw26_sw / tot:.1%}); "
                         f"SAMPLED_WEEK snapshots of all buses and years are {sw_all / tot:.1%}."),
            dict(statement='"94 % of the total is two sampled weeks nightly shed x25.86" (W1 root-cause table, row T)',
                 correct=f"The SAMPLED_WEEK share of the 2026-2031 total is {sw_all / tot:.1%} (not 94 %); the x25.857 ratio applies only to "
                         'SAMPLED_WEEK snapshots (weight 77.571 h vs 3 h); B7 stress-day snapshots carry weight 3 h (ratio 1).'),
            dict(statement='"5,991 MWh raw x 25.86 = 51 GWh"',
                 correct=f"2026 raw 3 h shed {raw26:.1f} MWh = SAMPLED_WEEK {raw26_sw:.1f} + B7 {raw26_b7:.1f}; only the SAMPLED_WEEK part is "
                         f"multiplied by {swr / 3.0:.4f} ({raw26_sw * swr / 3.0:.1f} MWh); the B7 part keeps weight 3 h."),
            dict(statement='54,205.78 MWh read as an annual EENS',
                 correct='It is the sum of six model-year weighted values (2026-2031), not a single-year EENS.')],
        w0_2_pins=dict(
            original_s0_s1_code_sha='cdfdea06146a6fe73df89cb410d6a88cb5fda306',
            baseline_sha256_pinned='a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16',
            files={str(p.relative_to(ROOT)): sha(p) for p in [SRC / 'S0_RESULT.json', SRC / 'S1_EARLIEST_RESULT.json', SRC / 'A2_SOLVE_LOG.csv',
                                                            SRC / 'A2_OPTIMIZER_CALL_LOG.csv', SRC / 'S0_NO_HARM_REFERENCE.csv', f]},
            weight_classes_h=dict(SAMPLED_WEEK=swr, B7_STRESS_ONLY=3.0),
            lp2_2025_vs_s0_2026_known_differences=[
                'background load growth factor 1.009327 (AEO 2026 vs 2025)', '3 GW non-locational operating reserve with online-capacity / min-load rows (S0 only)',
                'segment-neutral SOC (A2F08) on two sampled weeks + B7 days vs full-year chronology in LP2',
                'committed-asset COD (DWB uniform 0.51 derate in 2026, PBRP) and paid COD-lagged public expansion', 'multi-year 2026-2031 joint investment',
                'time sampling: 2 weeks (77.571 h) + 3 B7 days (3 h) vs 2,920 x 3 h'],
            attribution_note='No single added constraint is credited with the LP2 (no shed) vs S0 (shed) difference here; weights follow the method and are not an error by themselves.'),
        checks=checks, W0_DATA_QA='PASS' if ok else 'FAIL',
        note='NEXT-06 signed reports are not rewritten; this verdict and NEXT_07 reports carry the erratum.')
    (OUT / 'W0_RECONCILIATION_VERDICT.json').write_text(json.dumps(ver, indent=1, default=float), encoding='utf-8')
    print(json.dumps(dict(W0_DATA_QA=ver['W0_DATA_QA'], totals=ver['totals_MWh'], checks=checks,
                          shares={k: round(v['value'], 4) for k, v in ver['shares'].items()}, per_bus=per_bus), indent=1, default=float))


if __name__ == '__main__':
    main()
