#!/usr/bin/env bash
# BYOP-POST-V16-NEXT-02 A2 entry (L2, from the A2 checkout's workflow/). Independent of run_post_v16.sh (A1, SHA-pinned, unchanged).
#   bash byop/run/run_post_v16_a2.sh tests        A2 static unit tests (no solver)
#   bash byop/run/run_post_v16_a2.sh structural   build S0 / S1_EARLIEST / S3 + NEXT-02 audits, every solver call intercepted
#   bash byop/run/run_post_v16_a2.sh manifest     (re)write current_work_pckg/A2_PRE_RUN_MANIFEST.json (no solver)
#   bash byop/run/run_post_v16_a2.sh gate         print the A2 gate verdict for S0 and S1_EARLIEST (no build, no solver)
#   bash byop/run/run_post_v16_a2.sh n06_diag     NEXT-06 W2: ONE diagnostic S0 LP, 2026 full year - GATED by config.byop_post_v16_n06_diag.yaml
#   bash byop/run/run_post_v16_a2.sh s0s1         S0 then S1_EARLIEST - GATED (separate researcher approval of
#                                                 config/config.byop_post_v16_a2.yaml; 2 calls, 0 retries, STOP on any failure)
# DRY=1 prints the commands and runs nothing.
set -u
W=$(cd "$(dirname "$0")/../.." && pwd)
BASE=$W/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc
CFG=config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml
OUT=$W/results/BYOP/post_v16_a2/POST_V16_A2_S0S1
A2="python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --config $CFG --base $BASE --case-id POST_V16_A2_S0S1 --out $OUT --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-16} --scenarios S0 S1_EARLIEST"
run() {
  if [ -n "${DRY:-}" ]; then echo "CMD $*"; return 0; fi
  source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate; cd $W
  echo "$(date -u +%FT%TZ) start $*"; "$@"; local rc=$?; echo "$(date -u +%FT%TZ) end rc=$rc"; return $rc
}
case "${1:-}" in
  tests)      run python -m pytest -q byop/tests/test_a2_a3_static.py byop/tests/test_next02_a2_static.py ;;
  structural) run python -W ignore byop/tests/structural_post_v16_a2.py --out results/BYOP/post_v16_a2_static/_structural_next02 ;;
  manifest)   run python byop/build/build_post_v16_a2_manifest.py ;;
  gate)       run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps({s: G.check(s, '$BASE') for s in G.STAGES}, indent=1))" ;;
  s0s1)       run $A2 ;;
  n06_manifest) run python byop/build/build_post_v16_a2_manifest.py config/config.byop_post_v16_n06_diag.yaml ;;
  n06_gate)   run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps(G.check('S0', '$BASE', cfg_path='config/config.byop_post_v16_n06_diag.yaml'), indent=1))" ;;
  n06_diag)   run python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --a2-config config/config.byop_post_v16_n06_diag.yaml --config $CFG --base $BASE --case-id NEXT06_S0_DIAG_FULLYEAR_2026 --out $W/results/BYOP/next06_s0_diag_fullyear_2026 --start 2026 --end 2026 --sample-weeks 0 --threads ${THREADS:-16} --scenarios S0 ;;
  *)          echo "usage: $0 tests|structural|manifest|gate|s0s1|n06_manifest|n06_gate|n06_diag"; exit 2 ;;
esac
