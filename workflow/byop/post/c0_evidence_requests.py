#!/usr/bin/env python3
"""WP v1.5 section 6: priority C0 asset evidence requests for the researcher (no solve, no asset change).
    python byop/post/c0_evidence_requests.py
Reads the C0 repair v1.4 outputs (results/BYOP/C0_REPAIR_V14/) and writes C0_PRIORITY_ASSET_EVIDENCE_REQUESTS.csv there:
one row per asset item with both sides' identifiers, status, dates, capacity units, the concrete conflict and the evidence
needed. Current treatment of every row: existing model values kept until a researcher ruling.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

R = BP.C0_REPAIR_RESULTS
KEEP = 'existing model values kept (no asset change before a researcher ruling)'


def main():
    ph = pd.read_csv(R / 'C0_PHASE_RECONCILIATION.csv')
    sw = pd.read_csv(R / 'C0_SWITCHABLE_LEDGER.csv')
    su = pd.read_csv(R / 'C0_SWITCHABLE_UNIT_ROWS.csv')
    cdr = ph[ph.side == 'CDR_PHASE']
    rows = []
    for st in ('TENASKA KIAMICHI', 'TENASKA GATEWAY'):
        s = sw[sw.station == st].iloc[0]
        u = su[su.station_key == st]
        grp = cdr[cdr.cdr_group_key.str.contains(st.split()[-1]) & cdr.model_set.fillna('').str.contains('active2025')]
        rows.append(dict(priority='HIGH', item=f'{st.title()} switchable resource', cdr_ids='; '.join(u['UNIT CODE'].astype(str)), cdr_rows='; '.join(u.source_excel_row.astype(str)),
                         model_ids='; '.join(grp.reeds_unique_ids.dropna().astype(str)) or s.model_group, eia_plant_ids='; '.join(grp.eia_plant_ids.dropna().astype(str)),
                         cdr_status=f'SWGR-AVA x{int(s.physical_units)} / SWGR-UNA x{int(s.unavailable_adjustment_rows)}', cdr_date='; '.join(sorted(set(u['IN-SERVICE DATE'].astype(str)))),
                         cdr_MW=f'physical {s.physical_MW} / unavailable adj {s.unavailable_adjustment_MW} / snapshot net {s.snapshot_net_MW} (installed MW)',
                         model_MW=f'{s.model_active2025_summer_MW} (ReEDS summer MW, full ERCOT capacity)', model_status='; '.join(grp.reeds_status.dropna().astype(str).unique()),
                         conflict='model counts the whole resource as ERCOT capacity; the CDR snapshot marks part (Kiamichi) / all (Gateway) unavailable to ERCOT',
                         evidence_needed='switchable status and ERCOT-available MW at 2025 year end and over 2025; comparable summer capability; whether SWGR-UNA reflects a contract / election that persists',
                         current_treatment=KEEP))
    for r in cdr[cdr.reclass_action == 'STATUS_CONFLICT_REVIEW'].sort_values('cdr_MW', ascending=False).itertuples():
        rows.append(dict(priority='HIGH', item=f'status conflict {r.cdr_group_key}', cdr_ids=r.cdr_unit_codes or r.cdr_unit_names, cdr_rows=r.cdr_source_rows,
                         model_ids=r.reeds_unique_ids, eia_plant_ids=r.eia_plant_ids, cdr_status=r.cdr_statuses, cdr_date=r.cdr_in_service,
                         cdr_MW=f'{r.cdr_MW} (installed MW, CDR phase {r.phase_year})', model_MW=f'{r.model_summer_MW} (ReEDS summer MW, StartYear {r.model_start_year})',
                         model_status=r.reeds_status, conflict='model fleet holds the unit active in 2025, CDR gives a 2026 date / PLAN / OPER-SYN (possibly a future phase, expansion or repower under the same name)',
                         evidence_needed='commercial operation date and 2025 operating status of the model unit; whether the CDR record is the same physical phase or a separate expansion',
                         current_treatment=KEEP))
    for r in cdr[cdr.reclass_action == 'REVIEW_RECLASS_CANDIDATE'].sort_values('cdr_MW', ascending=False).itertuples():
        rows.append(dict(priority='MEDIUM', item=f'reclass candidate {r.cdr_group_key}', cdr_ids=r.cdr_unit_codes or r.cdr_unit_names, cdr_rows=r.cdr_source_rows,
                         model_ids=r.reeds_unique_ids, eia_plant_ids=r.eia_plant_ids, cdr_status=r.cdr_statuses, cdr_date=r.cdr_in_service,
                         cdr_MW=f'{r.cdr_MW} (installed MW)', model_MW=f'{r.model_summer_MW} (ReEDS summer MW, StartYear {r.model_start_year}, set {r.model_set})',
                         model_status=r.reeds_status, conflict='CDR commercial operation by 2025, model unit outside the 2025 fleet (OA status or StartYear 2026)',
                         evidence_needed='identity confirmation (ERCOT unit code <-> EIA plant / unit), 2025 operating status, in-service date, capacity basis',
                         current_treatment=KEEP))
    um = cdr[cdr.identity_match.isin(['UNMATCHED', 'AMBIGUOUS']) & (cdr.phase_class == 'HIST')]
    top = um.groupby('cdr_group_key').agg(cdr_MW=('cdr_MW', 'sum'), ids=('cdr_unit_codes', lambda s: '; '.join(s.dropna().astype(str))),
                                          rows=('cdr_source_rows', lambda s: '; '.join(s.dropna().astype(str))), status=('cdr_statuses', 'first'),
                                          note=('name_match_note', 'first')).sort_values('cdr_MW', ascending=False).head(20)
    for k, r in top.iterrows():
        rows.append(dict(priority='ONGOING', item=f'ERCOT-EIA mapping {k}', cdr_ids=r.ids, cdr_rows=r.rows, model_ids='', eia_plant_ids='', cdr_status=r.status, cdr_date='',
                         cdr_MW=f'{r.cdr_MW} (installed MW)', model_MW='unresolved', model_status='', conflict=f'no confirmed model identity ({r.note})',
                         evidence_needed='ERCOT UNIT CODE -> EIA plant ID / generator ID (high-impact assets first; 100 % coverage not required)', current_treatment=KEEP))
    out = pd.DataFrame(rows)
    out.to_csv(R / 'C0_PRIORITY_ASSET_EVIDENCE_REQUESTS.csv', index=False, lineterminator='\n')
    print(out.groupby('priority').size().to_dict(), len(out))


if __name__ == '__main__':
    main()
