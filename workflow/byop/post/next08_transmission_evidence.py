#!/usr/bin/env python3
"""NEXT-08 A3 (read-only, NO solver): external engineering evidence for the 2025 calibration line uplift, from the official ERCOT
TPIT workbook (2026-07-13, byop/inputs/grid/TPIT_2026-07-13_project_register_v250.csv) mapped to TAMU-64 buses with the v1.6
county -> cluster-bus shares (dominant bus per county). Evidence is plausibility support, not a one-to-one line match:
  E1  a COMPLETED / In-Service >= 138 kV line project (new line, rebuild, upgrade) whose two end counties map to exactly the
      synthetic line's bus pair (in either direction)
  E2  completed >= 138 kV line work with one end at one of the line's buses (corridor / substation-area support)
  E3  only Planned / Under Construction / Future work on the bus pair (in service after 2025 - not 2025 evidence)
  E0  nothing: the uplift is a RESEARCH CALIBRATION PROXY (reported with its size and cost assumption)
Lines in scope: the 18 v1.6-uplifted lines, the Far West pocket lines and every line touching the 2025 lossy-LP2 shed buses.
Run from workflow/ (local or L2): python byop/post/next08_transmission_evidence.py
Writes current_work_pckg/BYOP_NEXT_08_LOSSY_LP1_AND_BRANCHES/A3_TRANSMISSION_EVIDENCE.csv / .json"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
B16 = WF / 'results/BYOP/baseline_2025_tamu_v16'
OUT = ROOT / 'current_work_pckg/BYOP_NEXT_08_LOSSY_LP1_AND_BRANCHES'
SHED_BUSES = ['p620 2', 'p620 3', 'p620 6', 'p620 7', 'p620 1', 'p610 4', 'p620 4', 'p630 2', 'p600 1', 'p600 2']
POCKET_LINES = ['TL35', 'TL36', 'TL43', 'TL44']
LINE_TYPES = ('new_line', 'rebuild', 'upgrade', 'line_upgrade', 'rebuild_upgrade', 'new_circuit')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    reg = pd.read_csv(WF / 'byop/inputs/grid/TPIT_2026-07-13_project_register_v250.csv', low_memory=False)
    c2b = pd.read_csv(B16 / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
    dom = c2b.sort_values('share', ascending=False).drop_duplicates('GEOID').set_index('GEOID').cluster_bus
    fips = lambda x: str(x).replace('p', '').split('.')[0] if isinstance(x, str) and x.startswith('p') else None
    reg['bus_from'] = reg.county_from_fips.map(lambda x: dom.get(fips(x)))
    reg['bus_to'] = reg.county_to_fips.map(lambda x: dom.get(fips(x)))
    reg['bus_to'] = reg.bus_to.fillna(reg.bus_from)
    reg['is_line'] = reg.asset_type.astype(str).str.contains('line|rebuild|upgrade|circuit', case=False, regex=True)
    reg['done'] = reg.source_category.eq('Completed') | reg.internal_status.eq('In-Service')
    reg['kv_ok'] = reg.service_kv >= 138
    led = pd.read_csv(B16 / 'LINE_LEDGER.csv').set_index('name')
    up = led.index[led.calibration_uplift_MVA > 0.5]
    touch = led.index[led.bus0.isin(SHED_BUSES) | led.bus1.isin(SHED_BUSES)]
    scope = sorted(set(up) | set(POCKET_LINES) | set(touch), key=lambda s: int(s[2:]))
    rows, detail = [], []
    for ln in scope:
        a, b = led.bus0[ln], led.bus1[ln]
        cand = reg[reg.is_line & reg.kv_ok]
        pair = cand[((cand.bus_from == a) & (cand.bus_to == b)) | ((cand.bus_from == b) & (cand.bus_to == a))]
        touch_ = cand[(cand.bus_from.isin([a, b]) | cand.bus_to.isin([a, b])) & ~cand.index.isin(pair.index)]
        p_done, t_done, p_later = pair[pair.done], touch_[touch_.done], pair[~pair.done & ~reg.loc[pair.index].source_category.eq('Cancelled')]
        cls = 'E1' if len(p_done) else ('E2' if len(t_done) else ('E3' if len(p_later) else 'E0'))
        rows.append(dict(line=ln, bus0=a, bus1=b, v16_uplift_MVA=float(led.calibration_uplift_MVA[ln]), final_s_nom_MVA=float(led.final_s_nom[ln]),
                         uplifted_in_v16=ln in up, pocket_line=ln in POCKET_LINES, touches_lossy_lp2_shed_bus=ln in touch, evidence_class=cls,
                         e1_completed_pair_projects=len(p_done), e1_kv=sorted(set(p_done.service_kv.astype(int))),
                         e1_new_circuit_miles=float(p_done.new_circuit_miles.fillna(0).sum()), e1_rebuild_miles=float(p_done.rebuild_upgrade_miles.fillna(0).sum()),
                         e2_completed_touching_projects=len(t_done), e3_later_pair_projects=len(p_later),
                         later_pair_years=sorted(set(p_later.projected_in_service_year.dropna().astype(int)))[:6],
                         examples='; '.join(f"{r.project_id} {str(r.project_title)[:60]} ({int(r.service_kv)} kV, {r.source_category})"
                                            for r in pd.concat([p_done, t_done.head(2), p_later.head(2)]).head(4).itertuples())))
        for kind, df in (('E1_pair_completed', p_done), ('E2_touch_completed', t_done), ('E3_pair_later', p_later)):
            for r in df.itertuples():
                detail.append(dict(line=ln, kind=kind, project_id=r.project_id, title=r.project_title, kv=r.service_kv, status=r.internal_status,
                                   category=r.source_category, in_service=r.actual_in_service_year if not pd.isna(r.actual_in_service_year) else r.projected_in_service_year,
                                   bus_from=r.bus_from, bus_to=r.bus_to, new_miles=r.new_circuit_miles, rebuild_miles=r.rebuild_upgrade_miles, owner=r.owner))
    T = pd.DataFrame(rows)
    T.to_csv(OUT / 'A3_TRANSMISSION_EVIDENCE.csv', index=False)
    pd.DataFrame(detail).to_csv(OUT / 'A3_TRANSMISSION_EVIDENCE_PROJECTS.csv', index=False)
    u = T[T.uplifted_in_v16]
    summ = dict(step='NEXT-08 A3 transmission evidence (read-only)', optimizer_calls=0, source='ERCOT TPIT 2026-07-13 workbook (byop/inputs/grid)',
                county_to_bus='v1.6 COUNTY_TO_BUS_SHARES (dominant cluster bus per county)', lines_in_scope=int(len(T)),
                uplifted_lines_by_class=u.evidence_class.value_counts().to_dict(),
                uplift_MVA_by_class={k: float(v) for k, v in u.groupby('evidence_class').v16_uplift_MVA.sum().items()},
                research_proxy_lines=u[u.evidence_class == 'E0'].line.tolist(), pocket_lines=T[T.pocket_line][['line', 'evidence_class', 'examples']].to_dict('records'),
                caveat='Synthetic TAMU-64 lines aggregate many real circuits; a class is plausibility support for a capacity increment in that corridor, '
                       'not a statement that the synthetic line equals a real line or that the uplifted MVA was built.')
    (OUT / 'A3_TRANSMISSION_EVIDENCE.json').write_text(json.dumps(summ, indent=1, default=str), encoding='utf-8')
    print(json.dumps(summ, indent=1, default=str))
    pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 90)
    print(T[['line', 'bus0', 'bus1', 'v16_uplift_MVA', 'evidence_class', 'e1_completed_pair_projects', 'e1_kv', 'e2_completed_touching_projects', 'e3_later_pair_projects', 'later_pair_years']].to_string())


if __name__ == '__main__':
    main()
