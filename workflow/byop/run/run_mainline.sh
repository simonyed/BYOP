#!/usr/bin/env bash
# BYOP ERCOT Mainline v1.3 - the single run entry (L2, from pypsa-usa/workflow).
#   bash byop/run/run_mainline.sh tests     no-solver static tests (Stage A; always allowed)
#   bash byop/run/run_mainline.sh struct    no-solver structural build of S1 / S2-joint / S3 LP models (Stage A; allowed)
#   bash byop/run/run_mainline.sh gate      print the E1 run-gate verdict
#   bash byop/run/run_mainline.sh step0     Stage B step 0: ERM-02 B calibration + S0 min-uplift calibration (GATED)
#   bash byop/run/run_mainline.sh run       Stage B: S0, S1_EARLIEST, S3, S2 (+ attribution) on G-REAL / mid (GATED)
# Every optimizer call checks config/config.byop_ercot_mainline.yaml (run_authorization, approved_git_sha) and the
# pre-run manifest; without APPROVED the model exits with code 3 before building anything.
set -u
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
CFG=config/config.byop_ercot_mainline.yaml
OUT=$W/results/BYOP/mainline
cd $W; mkdir -p $OUT
CASE=MAINLINE_V13_GREAL_MID
COMMON="--mainline --config $CFG --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-6}"
run() {   # name, args...
  local name=$1; shift
  mkdir -p $OUT/$name/code && cp $W/byop/model/*.py $OUT/$name/code/
  echo "$(date -u +%FT%TZ) start $name"
  python -W ignore $W/byop/model/rearch_mech.py --case-id $name --out $OUT/$name $COMMON "$@" > $OUT/$name.log 2>&1
  local rc=$?
  echo "$(date -u +%FT%TZ) end $name exit $rc"
  return $rc
}
case "${1:-}" in
  tests)  python -m pytest -q byop/tests/test_mainline_v13.py 2>&1 | tee $OUT/static_tests.log ;;
  struct) python -W ignore byop/tests/structural_mainline_v13.py --out $OUT/_structural 2>&1 | tee $OUT/structural_tests.log ;;
  gate)   python -c "import sys; sys.path.insert(0,'byop/model'); import rearch_mech as R, json; print(json.dumps(R.mainline_gate('$CFG'), indent=1))" ;;
  step0)  run ${CASE}_ERMCAL --calibrate &&
          run ${CASE}_S0CAL --erm-cal $OUT/${CASE}_ERMCAL/erm02_calibration.json --s0-calibrate --scenarios S0 ;;
  run)    run $CASE --erm-cal $OUT/${CASE}_ERMCAL/erm02_calibration.json --s0-cal-file $OUT/${CASE}_S0CAL/S0_CALIBRATION.csv --attribution ;;
  *)      echo "usage: $0 tests|struct|gate|step0|run"; exit 1 ;;
esac
