#!/usr/bin/env python3
"""Post-v1.6 execution package v1.1 (2026-10-22), A0: SHA-256 QA of the staged research files (no solver, no data change).
    python byop/build/post_v16_stage_qa.py [--rebuild-dir <scratch copy where build_research_data.py was re-run>]
Staging (kept apart from every earlier input so nothing is confused):
  raw/      -> workflow/data/byop/post_v16_execution_v11/raw/   (local + L2, not git; official files unchanged)
  derived/  -> workflow/byop/inputs/post_v16/derived/           (tracked)
  documents -> current_work_pckg/BYOP_Post_v1.6_Execution_v1.1/ (tracked)
Every file is checked against ORIGINAL_RESEARCH_FILES_SHA256.json (53 files of the research ZIP) and the raw files also against
SOURCE_REGISTRY.csv. With --rebuild-dir the derived files re-built by the package's own build_research_data.py are compared.
Writes workflow/byop/inputs/post_v16/STAGING_SHA_QA.json.
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path

import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def staged_path(rel):
    if rel.startswith('raw/'):
        return BP.POST_V16_RAW / rel[4:]
    if rel.startswith('derived/'):
        return BP.POST_V16_DERIVED / rel[8:]
    return BP.POST_V16_PACKAGE / rel


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rebuild-dir', default=None)
    a = ap.parse_args()
    man = json.loads((BP.POST_V16_PACKAGE / 'ORIGINAL_RESEARCH_FILES_SHA256.json').read_text(encoding='utf-8'))
    rows = []
    for f in man['files']:
        rel = f['path']
        p = staged_path(rel)
        if rel == 'README.md':                       # the v0.1 README is kept under its archived name
            p = BP.POST_V16_PACKAGE / f['archived_path']
        ok = p.exists() and sha(p) == f['sha256']
        rows.append(dict(path=rel, staged=p.relative_to(WF.parent).as_posix() if p.exists() else str(p), expected=f['sha256'],
                         actual=sha(p) if p.exists() else None, size_ok=p.exists() and p.stat().st_size == f['size_bytes'], ok=ok))
    reg = pd.read_csv(BP.POST_V16_PACKAGE / 'SOURCE_REGISTRY.csv', encoding='utf-8-sig')
    reg_rows = []
    for r in reg[reg.archive_included.astype(str) == 'True'].itertuples():
        p = staged_path(r.file)
        reg_rows.append(dict(file=r.file, ok=p.exists() and sha(p) == r.sha256))
    rebuild = None
    if a.rebuild_dir:
        import gzip
        d = Path(a.rebuild_dir) / 'derived'

        def text(p):          # a rebuild on Windows writes CRLF; compare the content with line endings normalised
            b = Path(p).read_bytes()
            return (gzip.decompress(b) if str(p).endswith('.gz') else b).replace(b'\r\n', b'\n')
        cmp = []
        for x in man['files']:
            if x['path'].startswith('derived/'):
                q = d / x['path'][8:]
                cmp.append(dict(file=x['path'], byte_identical=q.exists() and sha(q) == x['sha256'],
                                text_identical_after_eol=q.exists() and text(q) == text(staged_path(x['path']))))
        rebuild = dict(dir='scratch copy of raw/ + build_research_data.py (originals untouched)', compared=len(cmp),
                       byte_identical=sum(c['byte_identical'] for c in cmp), text_identical_after_eol=sum(c['text_identical_after_eol'] for c in cmp),
                       differing=[c['file'] for c in cmp if not c['text_identical_after_eol']])
    out = dict(status='PASS' if all(r['ok'] for r in rows) and all(r['ok'] for r in reg_rows) else 'FAIL', solver_calls=0,
               files=len(rows), files_ok=sum(r['ok'] for r in rows), raw_registry_checked=len(reg_rows),
               raw_registry_ok=sum(r['ok'] for r in reg_rows), failures=[r for r in rows if not r['ok']] + [r for r in reg_rows if not r['ok']],
               rebuild=rebuild, staging=dict(raw=BP.POST_V16_RAW.relative_to(WF.parent).as_posix(), derived=BP.POST_V16_DERIVED.relative_to(WF.parent).as_posix(),
                                             package=BP.POST_V16_PACKAGE.relative_to(WF.parent).as_posix()), rows=rows)
    (BP.POST_V16_INPUTS / 'STAGING_SHA_QA.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
    if out['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
