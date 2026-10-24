#!/usr/bin/env bash
# BYOP NEXT-10U entry (L2, from pypsa-usa/workflow/): model version engineering_cost_v1 on the ADOPTED v1.7L lossy 2025 baseline.
#   bash byop/run/run_next10u.sh tests        NEXT-10U static unit tests (no solver)
#   bash byop/run/run_next10u.sh build_check  rebuild the engineering POI inputs in memory and compare with the tracked ones (no solver)
#   bash byop/run/run_next10u.sh static       build S0 / S1_EARLIEST / S3 with the engineering POI model, every solver call intercepted
#   bash byop/run/run_next10u.sh manifest / gate          S0 / S1 pre-run manifest and gate verdict (no solver)
#   bash byop/run/run_next10u.sh s0s1         S0 then S1_EARLIEST - GATED by config/config.byop_next10u_s0s1.yaml (<= 3 calls, 0 retries,
#                                             S0 technical + scientific gate before S1, STOP on any failure)
#   bash byop/run/run_next10u.sh a3_manifest / a3_gate    A3 pre-run manifest and gate verdict (no solver)
#   bash byop/run/run_next10u.sh a3           S0 -> S1_EARLIEST (re-solve, must reproduce) -> S3 -> S2 (1-3 iterations) -> S3_mS2 - GATED by
#                                             config/config.byop_next10u_a3.yaml (<= 30 calls, 0 retries, STOP on any failure)
#   bash byop/run/run_next10u.sh books <dir>  zero-solver three-book cost ledgers of a solved out_dir
# DRY=1 prints the commands and runs nothing. THREADS must be the same for s0s1 and a3 (the A3 re-solve must reproduce S0 / S1).
set -u
W=$(cd "$(dirname "$0")/../.." && pwd)
BASE=$W/results/BYOP/baseline_2025_tamu_v17_lossy/baseline_2025_tamu_v17_lossy_prepared.nc
CFG=config/config.byop_ercot_mainline_engineering_cost_v1.yaml
A2CFG=config/config.byop_next10u_s0s1.yaml
A3CFG=config/config.byop_next10u_a3.yaml
OUT=$W/results/BYOP/next10u_engineering_cost_v1/S0S1
OUT3=$W/results/BYOP/next10u_engineering_cost_v1/A3
COMMON="--mainline --post-v16 --config $CFG --base $BASE --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-16}"
run() {
  if [ -n "${DRY:-}" ]; then echo "CMD $*"; return 0; fi
  source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate; cd $W
  echo "$(date -u +%FT%TZ) start $*"; "$@"; local rc=$?; echo "$(date -u +%FT%TZ) end rc=$rc"; return $rc
}
case "${1:-}" in
  tests)       run python -m pytest -q byop/tests/test_next10u_engineering.py ;;
  build_check) run python byop/build/build_engineering_poi_v1.py --check ;;
  static)      run python -W ignore byop/tests/structural_n10u_engineering.py --out results/BYOP/next10u_engineering_cost_v1/_static ;;
  manifest)    run python byop/build/build_post_v16_a2_manifest.py $A2CFG ;;
  gate)        run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps({s: G.check(s, '$BASE', cfg_path='$A2CFG') for s in G.STAGES}, indent=1))" ;;
  s0s1)        run python -W ignore $W/byop/model/rearch_mech.py $COMMON --a2-config $A2CFG --case-id NEXT10U_S0S1 --out $OUT --scenarios S0 S1_EARLIEST ;;
  a3_manifest) run python byop/build/build_post_v16_a2_manifest.py $A3CFG ;;
  a3_gate)     run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a3_gate as G; print(json.dumps({s: G.check(s, '$BASE', cfg_path='$A3CFG') for s in ['S0', 'S3']}, indent=1))" ;;
  a3)          run python -W ignore $W/byop/model/rearch_mech.py $COMMON --a3-config $A3CFG --case-id NEXT10U_A3 --out $OUT3 --s2-iter 3 --scenarios S0 S1_EARLIEST S3 S2 S3_mS2 ;;
  books)       run python byop/post/next10u_cost_books.py --s0s1 $OUT --a3 $OUT3 --out ${2:-$W/results/BYOP/next10u_engineering_cost_v1/BOOKS} ;;
  *)           echo "usage: $0 tests|build_check|static|manifest|gate|s0s1|a3_manifest|a3_gate|a3|books"; exit 2 ;;
esac
