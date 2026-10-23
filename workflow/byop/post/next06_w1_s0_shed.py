#!/usr/bin/env python3
"""NEXT-06 W1.1 (read-only, NO solver): reconstruct the original S0 existing-customer shed by model year x bus x 3 h snapshot from the
frozen S0 outputs, attach the snapshot weights (rearch_mech.ml_base_build rule, read from the structural segment map of the same
code), native load (v1.6 baseline p_set) and the solved bus LMP, and reconcile with the reported totals. Run on L2 from workflow/:
    python byop/post/next06_w1_s0_shed.py
Writes workflow/results/BYOP/next06_s0_diagnostic/W1_*.csv / .json. The original S0 directory is only read.
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
SRC = WF / 'results/BYOP/post_v16_a2/POST_V16_A2_S0S1'
SEG = WF / 'results/BYOP/post_v16_a2_static/_structural_merged/A2_SOC_SEGMENT_MAP_S0.csv'
BASE = WF / 'results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc'
OUT = WF / 'results/BYOP/next06_s0_diagnostic'
REPORTED_TOTAL, REPORTED_2026 = 54205.7791, 51049.2775
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def weights(index):
    """per-snapshot weight (h) from the segment map of the same merged code: every segment has a constant weight"""
    sm = pd.read_csv(SEG, parse_dates=['start', 'end'])
    w = pd.Series(np.nan, index=index)
    kind = pd.Series('', index=index, dtype=object)
    per = index.get_level_values(0); ts = pd.DatetimeIndex(index.get_level_values(1))
    for r in sm.itertuples():
        msk = (per == r.period) & (ts >= r.start) & (ts <= r.end)
        w[msk] = r.w_generators_h; kind[msk] = r.kind
    return w, kind


def main():
    import pypsa
    OUT.mkdir(parents=True, exist_ok=True)
    f = SRC / 'S0_shed_by_snapshot_frozen.csv.gz'
    shed = pd.read_csv(f, index_col=[0, 1], parse_dates=[1])
    res = json.loads((SRC / 'S0_RESULT.json').read_text())
    w, kind = weights(shed.index)
    shed = shed.clip(lower=0.0)                     # solver noise ~1e-10 MW
    w_sum = w.groupby(level=0).sum()
    n = pypsa.Network(str(BASE))
    load = n.loads_t.p_set.T.groupby(n.loads.bus).sum().T          # native load by bus (baseline p_set; 2030-calendar weather year)
    if isinstance(load.index, pd.MultiIndex):
        load = load.droplevel(0)
    pr = pd.read_csv(SRC / 'prices_S0.csv.gz', index_col=[0, 1], parse_dates=[1])
    rows = []
    for col in shed.columns:
        bus, cat = (col[:-len(' inherited_ramp_unserved')], 'inherited_ramp') if col.endswith(' inherited_ramp_unserved') else (col[:-len(' load_shed')], 'native')
        s = shed[col]
        nz = s[s > 1e-6]
        for (p, t), mw in nz.items():
            rows.append(dict(period=int(p), timestep=t, bus=bus, category=cat, shed_MW=float(mw), physical_hours=3.0, weight_h=float(w[(p, t)]),
                             segment_kind=kind[(p, t)], raw_MWh=float(mw) * 3.0, weighted_MWh=float(mw) * float(w[(p, t)]),
                             native_load_MW=float(load.at[t, bus]) if bus in load.columns and t in load.index else np.nan,
                             lmp_USD_MWh=float(pr.at[(p, t), bus]) if bus in pr.columns else np.nan))
    ev = pd.DataFrame(rows).sort_values('weighted_MWh', ascending=False)
    ev['share_of_total'] = ev.weighted_MWh / ev.weighted_MWh.sum()
    ev.to_csv(OUT / 'W1_S0_SHED_SNAPSHOT_WEIGHTS.csv', index=False)
    by = ev.groupby(['period', 'bus', 'category']).agg(snapshots=('shed_MW', 'size'), raw_MWh=('raw_MWh', 'sum'), weighted_MWh=('weighted_MWh', 'sum'),
                                                       peak_MW=('shed_MW', 'max'), max_weight_h=('weight_h', 'max')).reset_index()
    by.sort_values(['period', 'weighted_MWh'], ascending=[True, False]).to_csv(OUT / 'W1_S0_SHED_BY_BUS_YEAR.csv', index=False)
    # contiguous events per bus: consecutive retained snapshots 3 h apart within a period
    evs = []
    for (p, bus, cat), g in ev.sort_values('timestep').groupby(['period', 'bus', 'category']):
        recs = g.sort_values('timestep').to_dict('records')
        runs, cur = [], [recs[0]]
        for r in recs[1:]:
            if pd.Timestamp(r['timestep']) - pd.Timestamp(cur[-1]['timestep']) == pd.Timedelta(hours=3):
                cur.append(r)
            else:
                runs.append(cur); cur = [r]
        runs.append(cur)
        for run in runs:
            d = pd.DataFrame(run)
            i = d.shed_MW.idxmax()
            evs.append(dict(period=p, bus=bus, category=cat, start=d.timestep.min(), end=d.timestep.max(), snapshots=len(d), duration_h=3 * len(d),
                            peak_MW=d.shed_MW.max(), raw_MWh=d.raw_MWh.sum(), weighted_MWh=d.weighted_MWh.sum(), weight_h=d.weight_h.max(),
                            weight_amplification=d.weight_h.max() / 3.0, segment_kind=d.segment_kind.iloc[0],
                            native_load_MW_at_peak=float(d.native_load_MW[i]), lmp_USD_MWh_max=d.lmp_USD_MWh.max()))
    E = pd.DataFrame(evs).sort_values('weighted_MWh', ascending=False)
    E.head(40).to_csv(OUT / 'W1_S0_TOP_SHED_EVENTS.csv', index=False)
    tot = float(ev.weighted_MWh.sum()); t26 = float(ev[ev.period == 2026].weighted_MWh.sum())
    top10 = float(ev.head(10).weighted_MWh.sum())
    rec = dict(solver_calls=0, source_dir=str(SRC.relative_to(WF.parent)), shed_file=f.name, shed_file_sha256=sha(f), shed_shape=list(shed.shape),
               s0_result_sha256=sha(SRC / 'S0_RESULT.json'), s0_result_existing_shed_MWh=res['acceptance']['values'].get('existing_shed_MWh'),
               segment_map=str(SEG.relative_to(WF.parent)), segment_map_sha256=sha(SEG), baseline_sha256=sha(BASE),
               weights_sum_h_by_period={int(k): float(v) for k, v in w_sum.items()}, weight_values_h=sorted(set(np.round(w.values, 4))),
               reconstructed_total_MWh=tot, reported_total_MWh=REPORTED_TOTAL, reconstructed_2026_MWh=t26, reported_2026_MWh=REPORTED_2026,
               by_year_weighted_MWh={int(k): float(v) for k, v in ev.groupby('period').weighted_MWh.sum().items()},
               by_year_raw_3h_MWh={int(k): float(v) for k, v in ev.groupby('period').raw_MWh.sum().items()},
               by_category_weighted_MWh={k: float(v) for k, v in ev.groupby('category').weighted_MWh.sum().items()},
               top10_snapshot_share=top10 / tot if tot else None,
               weighted_by_segment_kind_MWh={k: float(v) for k, v in ev.groupby('segment_kind').weighted_MWh.sum().items()},
               snapshots_with_shed=int(ev[['period', 'timestep']].drop_duplicates().shape[0]),
               max_shed_MW_2026=float(ev[ev.period == 2026].groupby(['timestep']).shed_MW.sum().max()) if t26 else 0.0)
    t26_native = float(ev[(ev.period == 2026) & (ev.category == 'native')].weighted_MWh.sum())
    rec['reconstructed_2026_native_only_MWh'] = t26_native
    rec['note_2026'] = ('the reported 2026 figure (shed_by_bus_S0.csv) counts only "<bus> load_shed" units (native) and drops columns <= 1e-3 MWh; '
                        'the reconstruction includes the inherited-ramp unit as well')
    rec['RECONCILIATION'] = 'PASS' if abs(tot - REPORTED_TOTAL) < 0.05 and abs(t26_native - REPORTED_2026) < 0.05 and all(abs(v - 8760) < 1e-6 for v in w_sum) else 'DATA_QA_FAIL'
    (OUT / 'W1_S0_RECONCILIATION.json').write_text(json.dumps(rec, indent=1, default=str))
    print(json.dumps(rec, indent=1, default=str))
    print(E.head(15).to_string())


if __name__ == '__main__':
    main()
