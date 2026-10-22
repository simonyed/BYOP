#!/usr/bin/env python3
"""BYOP calibration close-out v1.6: official 2025 constraint report vs the final fixed-asset run (LP2), no solver.
    python byop/post/v16_transmission_validation.py        (L2, after --lp2; reads the v16 directory)
Writes TRANSMISSION_EXTERNAL_VALIDATION.csv, TRANSMISSION_MODEL_CONGESTION.csv, WEST_EXPORT_INTERFACE.json.

Official: inputs/calibration_v16/evidence/TRANSMISSION_EXTERNAL_CHECKLIST.csv (ERCOT 2025 Constraints and Needs report, p. 5,
observation window 2024-10 .. 2025-09, NOT calendar 2025). Model: 64-bus TAMU backbone, 3 h steps, fixed v1.6 assets, no outages.
West Texas Export Interface = signed flow OUT of the west ReEDS zones {p60, p61, p62} into the rest (p63-p67) on every crossing
line (positive = export); a Far West import / shortage is a different phenomenon and is never counted as a match. Clustered TL
ids carry no substation names, so a named 138 / 345 kV element is never matched to a TL by name.
Status vocabulary: REGION_DIRECTION_CONSISTENT | DIRECTION_INCONSISTENT | NETWORK_NOT_RESOLVED | OUTAGE_SEQUENCE_NOT_MODELLED.
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

WEST = {'p60', 'p61', 'p62'}
AREA = {'West': WEST, 'South': {'p65'}, 'Central': {'p64'}, 'North': {'p63'}, 'Houston': {'p67'}}
ROW_AREA = {'Koch Tap - Vealmoor': 'West', 'Hargrove - Twin Buttes': 'West', 'Odessa EHV Switch - Yarbrough Sub': 'West',
            'Knapp - Scurry Chevron': 'West', 'Polecat Creek Switch - Wrage Ranch Pod': 'West', 'Laredo VFT North - Las Cruces': 'South',
            'Bell County - Salado Switch': 'Central', 'Haine Drive - La Palma': 'South', 'Longshore Switch - Consavvy Switch': None,
            'West Texas Export Interface': 'West'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import pypsa
    d = BP.BASE_TAMU_V16_DIR
    n = pypsa.Network(str(d / 'baseline_2025_tamu_prepared.nc'))
    chk = pd.read_csv(BP.CALIB_V16_EVIDENCE / 'TRANSMISSION_EXTERNAL_CHECKLIST.csv', encoding='utf-8-sig')
    p0 = pd.read_csv(d / 'LP2_line_flow_p0.csv.gz', index_col=[0, 1])
    lines = pd.read_csv(d / 'LP2_lines.csv').set_index('line')
    shed = pd.read_csv(d / 'LP2_shed_by_bus.csv.gz', index_col=[0, 1])
    w = 3.0
    L = n.lines
    z = n.buses.reeds_zone
    lim = L.s_nom * L.s_max_pu
    z0, z1 = L.bus0.map(z), L.bus1.map(z)
    lines['zone0'] = z0; lines['zone1'] = z1
    # model congestion table: every line with binding steps, area and direction of the binding flow
    cong = []
    for l in L.index:
        f = p0[l]
        b_fwd = f >= 0.999 * lim[l]; b_rev = f <= -0.999 * lim[l]
        if not (b_fwd.any() or b_rev.any()):
            continue
        a0 = next((k for k, v in AREA.items() if z0[l] in v), z0[l]); a1 = next((k for k, v in AREA.items() if z1[l] in v), z1[l])
        cong.append(dict(line=l, bus0=L.bus0[l], bus1=L.bus1[l], zone0=z0[l], zone1=z1[l], area0=a0, area1=a1, limit_MW=float(lim[l]),
                         v_nom=float(L.v_nom[l]) if 'v_nom' in L else np.nan, binding_hours_bus0_to_bus1=float(b_fwd.sum() * w),
                         binding_hours_bus1_to_bus0=float(b_rev.sum() * w), binding_hours=float((b_fwd | b_rev).sum() * w),
                         cross_west_boundary=bool((z0[l] in WEST) != (z1[l] in WEST))))
    C = pd.DataFrame(cong).sort_values('binding_hours', ascending=False) if cong else pd.DataFrame(columns=['line', 'binding_hours'])
    # West Texas Export: signed flow out of WEST on every crossing line
    xl = L.index[(z0.isin(WEST)) != (z1.isin(WEST))]
    sign = pd.Series(np.where(z0[xl].isin(WEST), 1.0, -1.0), index=xl)
    exp = (p0[xl] * sign).sum(axis=1)
    bind_exp = pd.DataFrame({l: (p0[l] * sign[l] >= 0.999 * lim[l]) for l in xl})
    bind_imp = pd.DataFrame({l: (p0[l] * sign[l] <= -0.999 * lim[l]) for l in xl})
    west_buses = n.buses.index[z.isin(WEST)]
    shed_w = shed[[b for b in shed.columns if b in west_buses]].sum(axis=1)
    W = dict(crossing_lines=list(xl), crossing_limit_MW=float(lim[xl].sum()), export_mean_MW=float(exp.mean()), export_max_MW=float(exp.max()),
             export_min_MW=float(exp.min()), export_positive_share_of_hours=float((exp > 0).mean()),
             hours_any_crossing_line_binding_export=float(bind_exp.any(axis=1).sum() * w), hours_any_crossing_line_binding_import=float(bind_imp.any(axis=1).sum() * w),
             hours_export_ge_95pct_of_crossing_limit=float((exp >= 0.95 * lim[xl].sum()).sum() * w),
             west_shed_MWh=float(shed_w.sum() * w), west_shed_hours=float((shed_w > 1e-3).sum() * w),
             definition='positive = flow out of p60/p61/p62 into p63-p67 (signed per line, summed); model 3 h steps x 3 h')
    consistent = W['export_positive_share_of_hours'] > 0.5 and W['hours_any_crossing_line_binding_export'] > W['hours_any_crossing_line_binding_import']
    rows = []
    for r in chk.itertuples():
        area = ROW_AREA.get(r.official_constraint)
        a_c = C[(C.area0 == area) | (C.area1 == area)] if area and len(C) else C.iloc[0:0]
        ev = dict(model_area=area or '', model_binding_lines_in_area=int(len(a_c)),
                  model_binding_hours_in_area=float(a_c.binding_hours.sum()) if len(a_c) else 0.0,
                  model_top_lines_in_area=';'.join(f'{x.line}({x.zone0}-{x.zone1}):{x.binding_hours:.0f}h' for x in a_c.head(3).itertuples()) if len(a_c) else '')
        if r.official_constraint == 'West Texas Export Interface':
            st = 'REGION_DIRECTION_CONSISTENT' if consistent else 'DIRECTION_INCONSISTENT'
            why = (f"model West export: positive in {W['export_positive_share_of_hours']:.1%} of hours, mean {W['export_mean_MW']:.0f} MW; "
                   f"crossing lines binding in the export direction {W['hours_any_crossing_line_binding_export']:.0f} h vs import {W['hours_any_crossing_line_binding_import']:.0f} h; "
                   'Far West shed / import is not counted')
        elif r.official_constraint.startswith('Longshore'):
            st = 'NETWORK_NOT_RESOLVED'
            why = ('345 kV corridor: TAMU clustered lines carry no substation names and the package gives no coordinates for Longshore / '
                   'Consavvy; no TL is identified by name (coarse-corridor inclusion unverified)')
        elif str(r.resolution_status_before_executor_check).startswith('OUTAGE'):
            st = 'OUTAGE_SEQUENCE_NOT_MODELLED'
            why = 'outage-driven in the official report; the fixed-asset baseline has no outage sequence (area congestion shown only as context)'
        else:
            st = 'NETWORK_NOT_RESOLVED'
            why = (f'{r.voltage_kV:.0f} kV local element below the 64-bus resolution; area-level evidence only' if pd.notna(r.voltage_kV) else 'local element')
            if ev['model_binding_lines_in_area'] > 0:
                why += f"; model {area} area has {ev['model_binding_lines_in_area']} binding lines ({ev['model_binding_hours_in_area']:.0f} line-hours)"
        rows.append(dict(rank=r.rank, official_constraint=r.official_constraint, voltage_kV=r.voltage_kV,
                         congestion_rent_USD_million=r.congestion_rent_USD_million, observation_window=r.observation_window,
                         official_required_comparison=r.required_model_comparison, status=st, explanation=why, **ev,
                         model_window='calendar 2025 load / profile year, 3 h, fixed v1.6 assets, no outages'))
    V = pd.DataFrame(rows)
    V.to_csv(d / 'TRANSMISSION_EXTERNAL_VALIDATION.csv', index=False, lineterminator='\n')
    C.to_csv(d / 'TRANSMISSION_MODEL_CONGESTION.csv', index=False, lineterminator='\n')
    W.update(status_counts=V.status.value_counts().to_dict(), network_sha256=sha(d / 'baseline_2025_tamu_prepared.nc'), script_sha256=sha(__file__))
    (d / 'WEST_EXPORT_INTERFACE.json').write_text(json.dumps(W, indent=1, default=str))
    print(V[['rank', 'official_constraint', 'status']].to_string()); print(json.dumps({k: v for k, v in W.items() if k != 'crossing_lines'}, indent=1))


if __name__ == '__main__':
    main()
