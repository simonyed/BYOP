#!/usr/bin/env bash
# BYOP ERCOT Mainline v1.3 - the single run entry (L2, from pypsa-usa/workflow).
#   bash byop/run/run_mainline.sh tests        no-solver static tests (always allowed)
#   bash byop/run/run_mainline.sh struct       no-solver structural build of S0 / S1 / S3 / S2-joint LP models (allowed)
#   bash byop/run/run_mainline.sh gate         print the E1 run-gate verdict (no solver)
#   bash byop/run/run_mainline.sh step0        Stage B B1: ERM-02 B calibration + S0 min-uplift calibration (GATED)
#   bash byop/run/run_mainline.sh pilot_s01    Stage B B2: S0 + S1_EARLIEST only, no attribution (GATED)
#   bash byop/run/run_mainline.sh pilot_s01_fix  Stage B B2-R (after F1 + F2-b): S0 + S1_EARLIEST in a NEW case dir (GATED)
#   bash byop/run/run_mainline.sh pilot_core_b3e  Stage B3-E exploratory: S0 S1_EARLIEST S3 S2(->S2_final) S3_mS2, new case dir, no attribution (GATED)
#   bash byop/run/run_mainline.sh pilot_core   Stage B B3: config scenarios S0 S1_EARLIEST S3 S2(->S2_final) S3_mS2, no attribution (GATED)
#   bash byop/run/run_mainline.sh attribution  Stage B B4 (optional): S0 + S1_EARLIEST + xPOI / xUP / xRA / xPROC / xALL (GATED)
#   bash byop/run/run_mainline.sh run          full case: config scenarios + attribution (GATED)
# Every optimizer call checks config/config.byop_ercot_mainline.yaml (run_authorization, approved_git_sha) and the
# pre-run manifest; without APPROVED the model exits with code 3 before building anything.
# Each stage writes its own case directory (case-id suffix) so no stage overwrites another stage's tables.
# DRY=1 prints the assembled commands and runs nothing (no-solver command-assembly test).
set -u
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
CFG=${CFG:-config/config.byop_ercot_mainline.yaml}   # AIDC geospatial v1: CFG=config/config.byop_ercot_mainline_geo_dynamic_v1.yaml
OUT=$W/results/BYOP/mainline
if [ -z "${DRY:-}" ]; then
  source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
  cd $W; mkdir -p $OUT
fi
CASE=$(awk '/^  case_id:/{print $2; exit}' "$CFG")    # case-id from the config (legacy: MAINLINE_V13_GREAL_MID)
CALCASE=${CALCASE:-MAINLINE_V13_GREAL_MID}            # B1 common-baseline calibration (S0 has no research AIDC; shared by siting variants)
COMMON="--mainline --config $CFG --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-6}"
CAL="--erm-cal $OUT/${CALCASE}_ERMCAL/erm02_calibration.json --s0-cal-file $OUT/${CALCASE}_S0CAL/S0_CALIBRATION.csv"
run() {   # name, args...
  local name=$1; shift
  if [ -n "${DRY:-}" ]; then
    echo "CMD python -W ignore $W/byop/model/rearch_mech.py --case-id $name --out $OUT/$name $COMMON $*"
    return 0
  fi
  if [ -e "$OUT/$name/case_manifest.json" ]; then
    echo "refusing: $OUT/$name already holds a finished case (choose a new stage / case-id)"; return 4
  fi
  if [ -d "$OUT/$name" ] && [ -n "$(ls -A $OUT/$name 2>/dev/null)" ]; then     # Stage B2.5-F: any partial data -> manual check
    echo "refusing: $OUT/$name already contains files (partial run?) - check it by hand before re-running"; return 5
  fi
  mkdir -p $OUT/$name/code && cp $W/byop/model/*.py $OUT/$name/code/
  echo "$(date -u +%FT%TZ) start $name"
  python -W ignore $W/byop/model/rearch_mech.py --case-id $name --out $OUT/$name $COMMON "$@" > $OUT/$name.log 2>&1
  local rc=$?
  echo "$(date -u +%FT%TZ) end $name exit $rc"
  return $rc
}
case "${1:-}" in   # post-v1.6 (package v1.1): this legacy entry never runs a post-v1.6 config (use byop/run/run_post_v16.sh)
  step0|pilot_s01|pilot_s01_fix|pilot_core|pilot_core_b3e|attribution|run)
    case "$CFG" in *post_v16*|*baseline_v16*) echo "refusing: $CFG is a post-v1.6 config; legacy $1 (ERM-02 B / S0CAL / no --base) is for historical reproduction only - use byop/run/run_post_v16.sh"; exit 6 ;; esac ;;
esac
case "${1:-}" in
  tests)       python -m pytest -q byop/tests/test_mainline_v13.py 2>&1 | tee $OUT/static_tests.log ;;
  tests_geo)   python -m pytest -q byop/tests/test_dynamic_siting.py 2>&1 | tee $OUT/static_tests_geo_dynamic_v1.log ;;
  struct)      python -W ignore byop/tests/structural_mainline_v13.py --out $OUT/_structural 2>&1 | tee $OUT/structural_tests.log ;;
  gate)        python -c "import sys; sys.path.insert(0,'byop/model'); import rearch_mech as R, json; s = R.ml_select_siting('$CFG'); print(json.dumps(dict(siting=s, **R.mainline_gate('$CFG')), indent=1))" ;;
  step0)       run ${CALCASE}_ERMCAL --calibrate &&
               run ${CALCASE}_S0CAL --erm-cal $OUT/${CALCASE}_ERMCAL/erm02_calibration.json --s0-calibrate --scenarios S0 ;;
  pilot_s01)   run ${CASE}_PILOT_S01 $CAL --scenarios S0 S1_EARLIEST ;;
  pilot_s01_fix) run ${CASE}_PILOT_S01_F1F2_V1 $CAL --scenarios S0 S1_EARLIEST ;;
  pilot_core)  run ${CASE}_PILOT_CORE $CAL ;;
  pilot_core_b3e) run ${CASE}_B3_EXPLORATORY_V1 $CAL --scenarios S0 S1_EARLIEST S3 S2 S3_mS2 ;;
  attribution) run ${CASE}_ATTRIBUTION $CAL --scenarios S0 S1_EARLIEST --attribution ;;
  run)         run $CASE $CAL --attribution ;;
  *)           echo "usage: $0 tests|tests_geo|struct|gate|step0|pilot_s01|pilot_s01_fix|pilot_core|pilot_core_b3e|attribution|run"; exit 1 ;;
esac
