#!/usr/bin/env python3
"""NEXT-02 A2-FIX-07: write current_work_pckg/A2_PRE_RUN_MANIFEST.json (no solver). Run from the A2 checkout's workflow/ on the
machine that will solve (L2):
    python byop/build/build_post_v16_a2_manifest.py
Pins every tracked file under workflow/byop/model, workflow/byop/run, workflow/scripts (code) and workflow/byop/inputs plus the
A2 mainline config (inputs) with three SHA-256 layers (A2-FIX-06): raw bytes on this checkout, LF-normalised content and its
CRLF encoding; text files are verified on the LF content (and raw must be one of the two encodings), binary / untracked data
on the raw bytes only. The A2 config is pinned by its normalised SHA (approval fields blanked), the baseline by its raw SHA.
"""
from __future__ import annotations

import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import post_v16_a2_gate as A2G  # noqa: E402
import post_v16_gate as G  # noqa: E402
import baseline_registry as BR  # noqa: E402

ROOT = WF.parent


def tracked(*paths):
    out = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--', *paths], capture_output=True, text=True).stdout
    return sorted(p for p in out.split('\0') if p)


def rec(rel):
    b = (ROOT / rel).read_bytes()
    s = A2G.file_shas(ROOT / rel)
    return dict(text=b'\0' not in b, **s)


def main():
    cfgp = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else A2G.CFG      # NEXT-06: any A2-type config (e.g. the W2 diagnostic)
    c = A2G.load(cfgp)
    code = [p for p in tracked('workflow/byop/model', 'workflow/byop/run', 'workflow/scripts') if p.endswith(('.py', '.sh'))]
    inputs = tracked('workflow/byop/inputs') + [f"workflow/{c['mainline_config']}"]
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    base = ROOT / c['baseline']['path']
    man = dict(status='A2_PRE_RUN_MANIFEST (NOT an approval)', work_package=c['authorization_source'],
               work_package_lf_sha256=c['authorization_source_sha256'], stage='A2', stages=c['stages'], max_scenario_attempts=A2G.budgets(c)[0], max_top_level_optimizer_calls=A2G.budgets(c)[1], optimizer_call_plan=c.get('optimizer_call_plan'),
               max_retries=c['max_retries'], config=Path(cfgp).resolve().relative_to(ROOT.resolve()).as_posix(),
               config_sha256_normalised=G.config_sha(cfgp),
               baseline=dict(path=c['baseline']['path'], sha256=A2G.file_shas(base)['raw'] if base.exists() else None),
               baseline_registry=BR.REGISTRY_REL, baseline_registry_normalised_sha256=BR.normalised_sha(),   # NEXT-09 (adoption fields blanked)
               formal_baseline_when_built=BR.summary()['formal'],
               code={p: rec(p) for p in code}, inputs={p: rec(p) for p in inputs},
               head_when_built=head, built_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
               note='verification: post_v16_a2_gate.manifest_mismatches; A1 manifest / gate untouched')
    if man['baseline']['sha256'] != c['baseline']['sha256']:
        raise SystemExit(f"baseline SHA {man['baseline']['sha256']} != pinned {c['baseline']['sha256']} - manifest not written")
    out = ROOT / c['manifest']
    out.write_text(json.dumps(man, indent=1), encoding='utf-8', newline='\n')
    print(json.dumps(dict(manifest=str(out.relative_to(ROOT)), code=len(code), inputs=len(inputs), head=head,
                          mismatches_now=A2G.manifest_mismatches(man)), indent=1))


if __name__ == '__main__':
    main()
