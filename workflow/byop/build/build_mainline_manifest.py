#!/usr/bin/env python3
"""Mainline v1.3 pre-run manifest (E1): SHA-256 of every code file and input the mainline run reads, the proposed
commands and the environment; RUN_AUTHORIZATION stays NOT_APPROVED. The run gate (rearch_mech.mainline_gate) refuses
a run when any listed file differs. Run from pypsa-usa/workflow (local or L2):
    python byop/build/build_mainline_manifest.py [--baseline-sha256 <sha of the L2 baseline .nc>] [--variant dynamic_pnnl_v1]
AIDC geospatial v1 (2026-10-22): --variant dynamic_pnnl_v1 writes the separate pending manifest of the dynamic geography
(current_work_pckg/AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json) with its cohorts / POI / siting builder / config added; the
legacy eight-bus manifest stays where it is (epoch8_legacy, default).
"""
from __future__ import annotations

import argparse, hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CODE = ['workflow/byop/model/rearch_mech.py', 'workflow/byop/model/v240_mech.py', 'workflow/byop/model/v250_mech.py',
        'workflow/byop/model/wp2_ercot_s0_s1.py', 'workflow/byop/model/wp2_ercot_s1_real.py', 'workflow/byop/model/byop_paths.py',
        'workflow/byop/post/collect_mainline.py', 'workflow/byop/run/run_mainline.sh',
        'workflow/byop/build/build_mainline_inputs.py', 'workflow/byop/build/build_reeds2_potential.py',
        'workflow/byop/tests/test_mainline_v13.py', 'workflow/byop/tests/structural_mainline_v13.py',
        'workflow/scripts/solve_network.py', 'workflow/scripts/prepare_network.py']
INPUTS = ['dc/EPOCH_TX_TIMELINE_EVIDENCE.csv', 'dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv', 'dc/MAINLINE_INHERITED_RAMP_2025.csv', 'dc/MAINLINE_AIDC_RECONCILIATION.csv',
          'dc/MAINLINE_BUS_SITE_POI_MAP.csv', 'dc/ercot_cohorts_2026_2035_tamu64.csv', 'dc/ERCOT_DC_TOTALS_2026_2035.csv',
          'dc/EPOCH_TX_SITES_TAMU64.csv', 'dc/state_pue_2022_2050.csv', 'dc/yearly_task_parameters_2022_2050.csv', 'dc/hourly_inference_trace.csv',
          'poi/GREAL_POI_ASSUMPTIONS.csv', 'poi/GREAL_POI_E0_SCHEDULE.csv', 'poi/GREAL_R_ASSET_POOL.csv', 'poi/GRID_PROJECTS.csv',
          'grid/COMMITTED_BASE_ASSETS.csv', 'grid/ERCOT_WIND_SOLAR_POTENTIAL.csv', 'grid/GREAL_GRID_PROJECTS.csv',
          'grid/GREAL_BACKGROUND_LOAD_RECONCILIATION.csv', 'grid/GREAL_NETWORK_EVIDENCE.csv',
          'tech/MAINLINE_V13_TECH_DEFAULTS.csv', 'tech/MAINLINE_V13_GAS_PRICES_2026_2031.csv', 'tech/TECH-01_technologies_DRAFT.csv',
          'load/background_load_growth_states_AEO2023_reference.csv']
VARIANTS = {
    'epoch8_legacy': dict(name='MAINLINE_V13_PRE_RUN_MANIFEST', out='current_work_pckg/_completed/BYOP_ERCOT_Mainline_v1.3/MAINLINE_V13_PRE_RUN_MANIFEST.json',
                          config='workflow/config/config.byop_ercot_mainline.yaml', stage='STAGE_A_IMPLEMENTATION_ONLY', extra_code=[], extra_inputs=[]),
    'dynamic_pnnl_v1': dict(name='AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST', out='current_work_pckg/AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json',
                            config='workflow/config/config.byop_ercot_mainline_geo_dynamic_v1.yaml', stage='AIDC_GEO_DYNAMIC_V1_IMPLEMENTED_NO_SOLVER',
                            extra_code=['workflow/byop/build/build_dynamic_siting_inputs.py', 'workflow/byop/build/build_pnnl_tamu_candidates.py',
                                        'workflow/byop/tests/test_dynamic_siting.py', 'workflow/byop/post/stage_b3_tables.py'],
                            extra_inputs=['dc/MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml', 'dc/MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv',
                                          'dc/MAINLINE_AIDC_RECONCILIATION_GEO_DYNAMIC_V1.csv', 'dc/MAINLINE_SITING_WEIGHTS_GEO_DYNAMIC_V1.csv',
                                          'dc/MAINLINE_SITE_CLASSIFICATION_GEO_DYNAMIC_V1.csv', 'dc/MAINLINE_CANDIDATE_BUS_ELIGIBILITY_GEO_DYNAMIC_V1.csv',
                                          'dc/MAINLINE_NEW_BUS_POI_RISK_GEO_DYNAMIC_V1.csv', 'dc/MAINLINE_NEW_RESEARCH_BUS_POI_MAP_GEO_DYNAMIC_V1.csv',
                                          'dc/MAINLINE_SITING_P_VARIANTS_GEO_DYNAMIC_V1.csv', 'dc/ROUNDING_RECONCILIATION_GEO_DYNAMIC_V1.csv',
                                          'dc/MAINLINE_SITING_BUILD_MANIFEST_GEO_DYNAMIC_V1.json', 'dc/EPOCH_SITE_SERVICE_TAMU64.csv',
                                          'dc/PNNL_ATLAS_TX_SITES_TAMU64.csv', 'dc/PNNL_PROJECTED_HIGHER_TX_TAMU64.csv', 'dc/PNNL_CANDIDATE_BUS_SUMMARY.csv',
                                          'dc/PNNL_SPATIAL_MAPPING_REVIEW.csv', 'dc/PNNL_PROVENANCE.json',
                                          'poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv', 'poi/MAINLINE_POI_DERIVED_DELTA_GEO_DYNAMIC_V1.csv']),
}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--baseline-sha256', default=None)
    ap.add_argument('--variant', default='epoch8_legacy', choices=sorted(VARIANTS))
    a = ap.parse_args()
    V = VARIANTS[a.variant]
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True).stdout.strip()
    man = dict(
        manifest=V['name'], siting_variant=a.variant, created_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'),
        RUN_AUTHORIZATION='NOT_APPROVED', SOLVER_EXECUTIONS=0, stage=V['stage'],
        git=dict(branch=branch, parent_commit_when_hashed=head,
                 note='the files below are hashed from the working tree; the Stage A commit that contains them is in MAINLINE_V13_RETURN_MANIFEST.md'),
        code_sha256={p: sha(ROOT / p) for p in CODE + V['extra_code']},
        inputs_sha256={f'workflow/byop/inputs/{p}': sha(ROOT / 'workflow/byop/inputs' / p) for p in INPUTS + V['extra_inputs']},
        baseline_network=dict(path='workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc', location='L2 only (.nc not in git)',
                              sha256=a.baseline_sha256),
        config=f"{V['config']} (holds run_authorization / approved_git_sha; not hashed so that approval does not change the manifest)",
        environment=dict(host='L2 lambda-2', python_env='/datasets/prgm/pypsa-usa/.venv (source /datasets/cds/env.sh first)',
                         pypsa='1.3.0', linopy='0.9.1', gurobipy='11.0.3', solver='Gurobi barrier, Crossover 0'),
        proposed_commands=['cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow',
                           'bash byop/run/run_mainline.sh gate     # must print approved: true',
                           'bash byop/run/run_mainline.sh step0    # ERM-02 B calibration + S0 min-uplift calibration (G-REAL background)',
                           'bash byop/run/run_mainline.sh run      # S0, S1_EARLIEST (+ xPOI/xUP/xRA/xPROC/xALL), S3, S2 joint developer'],
        approval_procedure=['researcher sets mainline.run_authorization: APPROVED and mainline.approved_git_sha: <audited commit> in the config',
                            'no change under workflow/byop/{model,inputs,build,run} after that commit; all hashes above must match'])
    if a.baseline_sha256:
        man['inputs_sha256'][man['baseline_network']['path']] = a.baseline_sha256
    if a.variant != 'epoch8_legacy':
        man['proposed_commands'] = ['cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow',
                                    f"CFG={V['config'].removeprefix('workflow/')} bash byop/run/run_mainline.sh gate   # must print approved: true",
                                    'NOT PROPOSED IN THIS PACKAGE: any solve of the dynamic geography needs a new researcher approval (separate package)']
        out = ROOT / V['out']
        out.write_bytes((json.dumps(man, indent=1) + '\n').encode())
    else:
        out = ROOT / V['out']
        out.write_text(json.dumps(man, indent=1), encoding='utf-8')
    print(out, len(man['code_sha256']), len(man['inputs_sha256']))


if __name__ == '__main__':
    main()
