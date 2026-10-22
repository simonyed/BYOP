#!/usr/bin/env python3
"""Post-v1.6 package v1.1 (A0): write current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json (no solver).
    python byop/build/build_post_v16_manifest.py
The manifest pins the SHA-256 of every A1 code file, every A1 input, the normalised A1 config and the v1.6 baseline. The
post-v1.6 gate (byop/model/post_v16_gate.py) compares them at solve time; the researcher approves a commit that contains this
manifest. Re-run after any change to the listed files (the static tests fail otherwise).
"""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402
import post_v16_gate as G  # noqa: E402

ROOT = WF.parent
CFG = WF / 'config/config.byop_post_v16_a1.yaml'
CODE = ['workflow/byop/model/post_v16_gate.py', 'workflow/byop/model/post_v16_headroom.py', 'workflow/byop/model/byop_paths.py',
        'workflow/byop/run/post_v16_a1.py', 'workflow/byop/run/run_post_v16.sh']
INPUTS = ['workflow/byop/inputs/post_v16/derived/ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv',
          'workflow/byop/inputs/post_v16/derived/PRE_REGISTERED_STRESS_EVENTS.csv',
          'workflow/byop/inputs/post_v16/POST_V16_RESERVE_PARAMETERS.csv',
          'workflow/byop/inputs/dc/MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv',
          'workflow/byop/inputs/poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv',
          'workflow/byop/inputs/poi/GREAL_POI_E0_SCHEDULE.csv',
          'workflow/byop/inputs/dc/state_pue_2022_2050.csv',
          'workflow/byop/inputs/dc/MAINLINE_INHERITED_RAMP_2025.csv',
          'workflow/results/BYOP/baseline_2025_tamu_v16/COUNTY_TO_BUS_SHARES.csv',
          'current_work_pckg/_completed/BYOP_Post_v1.6_Execution_v1.1_A0/BYOP_Post_v1.6_Execution_v1.1/CURRENT_EXECUTION_WORK_PACKAGE_v1.1.md']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    c = G.load(CFG)
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    return dict(
        status='PRE_RUN_MANIFEST_A1 (A0 output; NOT an approval)', work_package='BYOP_Post_v1.6_Execution_v1.1', stage='A1',
        stages=c['stages'], max_lp_calls=c['max_lp_calls'], max_retries=c['max_retries'],
        config='workflow/config/config.byop_post_v16_a1.yaml', config_sha256_normalised=G.config_sha(CFG),
        baseline=dict(path=c['baseline']['path'], sha256=c['baseline']['sha256'], location='L2 only (.nc not in git)'),
        code_sha256={p: sha(ROOT / p) for p in CODE}, inputs_sha256={p: sha(ROOT / p) for p in INPUTS},
        head_when_built=head, note='approve the commit that CONTAINS this file; the gate requires approved_git_sha == HEAD')


def main():
    m = build()
    out = ROOT / 'current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json'
    out.write_text(json.dumps(m, indent=1), encoding='utf-8')
    print(out, len(m['code_sha256']), len(m['inputs_sha256']))


if __name__ == '__main__':
    main()
