"""NEXT-10U G2 (2026-10-24): S0 scientific reliability gate (pure post-solve audit, no solver).

The researcher's earlier objection: a technically PASSED S0 (optimal, balanced, no-harm reference written) with an implausible
existing-customer shed (v1.6: 54.2 GWh, 94 % in the Far West pocket) must not become the no-harm reference of S1. With a config block
`s0_science_gate`, the S0 acceptance PASSes only if, in every model year y:
    EENS_y / native_load_y                <= eens_share_max      (default 1e-5)
    max_snapshot_native_shed_y / peak_y   <= max_shed_to_peak_max (default 1e-3)
EENS_y = weighted existing-customer shed (every load_shed unit: native background + inherited ramp); native_load_y = weighted
existing-customer load (no DC bus); peak_y = max snapshot native load of the sampled + stress snapshots. Thresholds are research
proxies fixed before the solve (config, SHA-pinned in the manifest), not ERCOT rules, and are never relaxed after a result.
Also reported: the Far West pocket per year and raw (unweighted) vs weighted snapshot counts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULTS = dict(eens_share_max=1e-5, max_shed_to_peak_max=1e-3, far_west_buses=['p610 4', 'p620 6', 'p620 7'])


def native_load(n):
    """existing-customer load per snapshot and bus (MW): static + time-varying p_set of loads not on a DC bus"""
    ld = n.loads[~n.loads.bus.astype(str).str.startswith('DC_')]
    p = pd.DataFrame(0.0, index=n.snapshots, columns=ld.index)
    tv = n.loads_t.p_set.reindex(columns=ld.index)
    for c in ld.index:
        p[c] = tv[c].values if (c in n.loads_t.p_set and tv[c].notna().all()) else float(ld.p_set[c])
    return p.T.groupby(ld.bus).sum().T


def evaluate(n, gate=None):
    g = dict(DEFAULTS, **(gate or {}))
    w = n.snapshot_weightings.generators
    per = n.snapshots.get_level_values(0)
    lam = n.generators.index[n.generators.carrier == 'load_shed']
    shed = n.generators_t.p.reindex(columns=lam).fillna(0.0)
    shed_bus = shed.T.groupby(n.generators.bus[lam]).sum().T if len(lam) else pd.DataFrame(index=n.snapshots)
    load_bus = native_load(n)
    rows, fw = [], []
    for y in sorted(set(per)):
        sl = per == y
        wy = w[sl]
        L = load_bus[sl].sum(axis=1)
        S = shed_bus[sl].sum(axis=1) if shed_bus.shape[1] else pd.Series(0.0, index=L.index)
        e = float((S * wy).sum()); a = float((L * wy).sum()); pk = float(L.max()); ms = float(S.max())
        rows.append(dict(year=int(y), EENS_MWh=e, native_load_MWh=a, eens_share=e / a if a > 0 else float('nan'),
                         native_peak_MW=pk, max_snapshot_shed_MW=ms, max_shed_to_peak=ms / pk if pk > 0 else float('nan'),
                         snapshots=int(sl.sum()), snapshots_with_shed=int((S > 1e-3).sum()), raw_shed_MW_sum=float(S.sum()),
                         eens_ok=bool(a > 0 and e / a <= g['eens_share_max']), peak_ok=bool(pk > 0 and ms / pk <= g['max_shed_to_peak_max'])))
        fwb = [b for b in g['far_west_buses'] if b in shed_bus.columns]
        fwl = [b for b in g['far_west_buses'] if b in load_bus.columns]
        fs = shed_bus.loc[sl, fwb].sum(axis=1) if fwb else pd.Series(0.0, index=L.index)
        fl = load_bus.loc[sl, fwl].sum(axis=1) if fwl else pd.Series(0.0, index=L.index)
        fw.append(dict(year=int(y), far_west_EENS_MWh=float((fs * wy).sum()), far_west_load_MWh=float((fl * wy).sum()),
                       far_west_max_shed_MW=float(fs.max()), far_west_peak_MW=float(fl.max()), share_of_system_EENS=float((fs * wy).sum()) / e if e > 0 else 0.0))
    df = pd.DataFrame(rows)
    ok = bool(len(df)) and bool(df.eens_ok.all()) and bool(df.peak_ok.all())
    return dict(PASS=ok, verdict='S0_SCIENCE_PASS' if ok else 'S0_SCIENCE_FAIL', thresholds=dict(eens_share_max=g['eens_share_max'],
                max_shed_to_peak_max=g['max_shed_to_peak_max'], basis='research proxy fixed before the solve; not an ERCOT rule'),
                far_west_buses=g['far_west_buses'], by_year=df.to_dict('records'), far_west=fw,
                total_EENS_MWh=float(df.EENS_MWh.sum()) if len(df) else 0.0,
                worst_eens_share=float(df.eens_share.max()) if len(df) else float('nan'),
                worst_max_shed_to_peak=float(df.max_shed_to_peak.max()) if len(df) else float('nan'))
