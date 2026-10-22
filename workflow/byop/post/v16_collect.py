#!/usr/bin/env python3
"""BYOP calibration close-out v1.6: collect the deliverables into current_work_pckg/ (no solver).
    python byop/post/v16_collect.py          (local, after the L2 results are synced)
- re-keys the unit rows of BASELINE_V16_INPUT_DIFF.csv: the builder at code commit 85cd6ae5 wrote the pandas method repr of
  Series.item into the label column `key` of the unit rows (numbers unaffected); the label is rebuilt from
  ASSET_OVERRIDE_AUDIT.csv (same row order: one row per decided ReEDS Unique ID) and the repair is recorded in the file
  BASELINE_V16_INPUT_DIFF_REKEY.json
- copies the deliverables to current_work_pckg/ and writes V16_CLOSEOUT_SUMMARY.json (numbers for the report)
"""
from __future__ import annotations

import hashlib, json, shutil, sys
from pathlib import Path

import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

D = BP.BASE_TAMU_V16_DIR
CWP = WF.parent / 'current_work_pckg'
DELIVER = ['BASELINE_V16_INPUT_DIFF.csv', 'ASSET_OVERRIDE_AUDIT.csv', 'SWITCHABLE_CAP_QA.csv', 'RELIABILITY_ANCHOR_BRIDGE.csv',
           'TRANSMISSION_EXTERNAL_VALIDATION.csv', 'BASELINE_V16_FIXED_ASSET_QA.json', 'BASELINE_V16_SOLVE_LOG.csv']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rekey():
    p = D / 'BASELINE_V16_INPUT_DIFF.csv'
    d = pd.read_csv(p)
    u = d.level == 'unit'
    if not d.loc[u, 'key'].str.startswith('<bound method').any():
        return dict(rekeyed=False)
    au = pd.read_csv(D / 'ASSET_OVERRIDE_AUDIT.csv').drop_duplicates('reeds_unique_id')
    assert u.sum() == len(au)
    before = sha(p)
    d.loc[u, 'key'] = [f'{r.item} | ReEDS {r.reeds_unique_id}' for r in au.itertuples()]
    assert (d.loc[u, 'cluster_bus'].values == au.cluster_bus.values).all(), 'row order differs from the override audit'
    d.to_csv(p, index=False, lineterminator='\n')
    info = dict(rekeyed=True, rows=int(u.sum()), sha256_before=before, sha256_after=sha(p),
                reason='label column `key` of unit rows held the repr of pandas Series.item (builder 85cd6ae5); numbers unchanged; '
                       'fixed in the builder after the run; labels rebuilt from ASSET_OVERRIDE_AUDIT.csv (row order and cluster_bus checked)')
    (D / 'BASELINE_V16_INPUT_DIFF_REKEY.json').write_text(json.dumps(info, indent=1))
    return info


def main():
    info = dict(rekey=rekey())
    for f in DELIVER:
        if (D / f).exists():
            shutil.copy2(D / f, CWP / f)
    info['deliverables_sha256'] = {f: sha(CWP / f) for f in DELIVER if (CWP / f).exists()}
    for f in ('LP1_METRICS.json', 'PRM_BRIDGE_SUMMARY.json', 'WEST_EXPORT_INTERFACE.json', 'baseline_2025_tamu_audit.json'):
        if (D / f).exists():
            j = json.loads((D / f).read_text())
            info[f] = {k: v for k, v in j.items() if k not in ('linopy_variables', 'interfaces')}
    (CWP / 'V16_CLOSEOUT_SUMMARY.json').write_text(json.dumps(info, indent=1, default=str))
    print(json.dumps(info.get('rekey'), indent=1)); print(sorted(info['deliverables_sha256']))


if __name__ == '__main__':
    main()
