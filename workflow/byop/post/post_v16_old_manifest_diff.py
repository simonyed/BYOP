#!/usr/bin/env python3
"""Post-v1.6 package v1.1, A0 step 1: SHA-256 drift of the earlier (still NOT_APPROVED) pre-run manifests against the files
now in the repository (no solver). Writes workflow/results/BYOP/POST_V16_A1_HEADROOM/OLD_MANIFEST_SHA_DIFF.json."""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

MANIFESTS = ['current_work_pckg/_completed/BYOP_ERCOT_AIDC_Geospatial_Distribution_v1.0/AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json',
             'current_work_pckg/_completed/BYOP_Calibration_Closeout_v1.6/S0_S1_BASELINE_V16_PREPARED_MANIFEST.json']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    out = {}
    for m in MANIFESTS:
        p = ROOT / m
        if not p.exists():
            out[m] = dict(status='MISSING'); continue
        j = json.loads(p.read_text(encoding='utf-8'))
        pins = {**j.get('code_sha256', {}), **j.get('inputs_sha256', {})}
        rows = []
        for rel, h in pins.items():
            f = ROOT / rel if (ROOT / rel).exists() else WF / rel
            now = sha(f) if f.exists() else None
            rows.append(dict(file=rel, pinned=h, now=now, status='MATCH' if now == h else ('MISSING_HERE' if now is None else 'CHANGED')))
        base = j.get('baseline_network') or j.get('baseline') or {}
        out[m] = dict(entries=len(rows), match=sum(r['status'] == 'MATCH' for r in rows), changed=[r for r in rows if r['status'] == 'CHANGED'],
                      missing_here=[r['file'] for r in rows if r['status'] == 'MISSING_HERE'], baseline=base,
                      gate_state='NOT_APPROVED (unchanged); drift only makes the old gate stricter')
    d = BP.POST_V16_RESULTS; d.mkdir(parents=True, exist_ok=True)
    (d / 'OLD_MANIFEST_SHA_DIFF.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: dict(entries=v.get('entries'), match=v.get('match'), changed=[c['file'] for c in v.get('changed', [])],
                              missing_here=v.get('missing_here')) for k, v in out.items()}, indent=1))


if __name__ == '__main__':
    main()
