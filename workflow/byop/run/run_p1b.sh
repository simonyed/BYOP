#!/usr/bin/env bash
# v2.5.0 P1b (D250-20/21): definitive v5 baseline (LP-calibrated 2025 ITLs) + CNY-05 county headroom diagnostic.
# Starts after run_p1.sh has printed ALL_DONE (no CPU contention). Two slots x 12 threads.
#   P1b_GR       main G-R case on v5 (S0 S1 S3 S2 S3_mS2), compare with P1_GR (v4)
#   P1b_GC_x2/x4/x8/x16 S1 on the committed grid with the DC request scaled x4 / x8 (STYLIZED headroom diagnostic)
set -u
source /datasets/cds/env.sh
source /datasets/prgm/pypsa-usa/.venv/bin/activate
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
OUT=$W/results/BYOP/p1
BASE=$W/results/BYOP/baseline_2025_county/baseline_2025_county_prepared.nc
CAL=$OUT/ERM_CAL/erm02_calibration.json
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
until grep -q ALL_DONE $OUT/run_p1.out 2>/dev/null; do sleep 60; done
[ -f "$BASE" ] || { echo "missing $BASE"; exit 1; }
COMMON="--start 2026 --end 2031 --sample-weeks 26 --erm-cal $CAL --threads ${THREADS:-12} --base $BASE"
run() {
  local name=$1; shift
  mkdir -p $OUT/$name/code && cp $W/byop/model/*.py $OUT/$name/code/
  echo "$(date -u +%FT%TZ) start $name"
  python -W ignore $W/byop/model/v250_mech.py --case-id $name --out $OUT/$name $COMMON "$@" > $OUT/$name.log 2>&1
  echo "$(date -u +%FT%TZ) end $name exit $?"
}
( run P1b_GC_x4 --grid G-C --dem-scale 4 --scenarios S1
  run P1b_GC_x16 --grid G-C --dem-scale 16 --scenarios S1 ) > $OUT/slotA_b.log 2>&1 &
( run P1b_GC_x8 --grid G-C --dem-scale 8 --scenarios S1
  run P1b_GC_x2 --grid G-C --dem-scale 2 --scenarios S1 ) > $OUT/slotB_b.log 2>&1 &
wait
echo "$(date -u +%FT%TZ) ALL_DONE_B"
