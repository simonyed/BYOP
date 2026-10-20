#!/usr/bin/env bash
# v2.5.0 P1 county experiment matrix (doc sec.7.2 / 10.7; decisions D250-12/17/19). Run on L2:
#   bash run_p1.sh            (needs outputs/p1/ERM_CAL/erm02_calibration.json)
# D250-19: 2 sampled weeks per year (weeks 0 and 26 = winter / summer peak), 2026-2031, at most two cases at a time
# with 12 threads each. Slot A: P1_GR (main) then P1_GR_S2v. Slot B: P1_GC, P1_GI, then P1_GR_GE once P1_GR's S1
# prices exist (same physical world; S1 does not depend on the gas gate or the S2 rule).
#   P1_GC     S1 on the committed grid (existing NARIS + verified TPIT increments = none)        doc 10.7 (1)
#   P1_GR     main: G-R realistic expansion, gas contractable (sensitivity label), S2-SF          doc 10.7 (2)-(4)
#   P1_GI     G-I instant expansion upper bound (S1)
#   P1_GR_GE  G-R with the P0F evidence-only gas gate
#   P1_GR_S2v G-R, S2-v penalty rule (decision-rule control, D-01)
set -u
source /datasets/cds/env.sh
source /datasets/prgm/pypsa-usa/.venv/bin/activate
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
OUT=$W/results/BYOP/p1
CAL=$OUT/ERM_CAL/erm02_calibration.json
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
[ -f "$CAL" ] || { echo "missing $CAL"; exit 1; }
COMMON="--start 2026 --end 2031 --sample-weeks 26 --erm-cal $CAL --threads ${THREADS:-12}"
run() {   # name, args...  (foreground: slots are sequential inside)
  local name=$1; shift
  mkdir -p $OUT/$name/code && cp $W/byop/model/*.py $OUT/$name/code/
  echo "$(date -u +%FT%TZ) start $name"
  python -W ignore $W/byop/model/v250_mech.py --case-id $name --out $OUT/$name $COMMON "$@" > $OUT/$name.log 2>&1
  echo "$(date -u +%FT%TZ) end $name exit $?"
}
(
  run P1_GR --grid G-R --gas-gate contract --s2-rule sf --scenarios S0 S1 S3 S2 S3_mS2
  run P1_GR_S2v --grid G-R --gas-gate contract --s2-rule v --s1-from $OUT/P1_GR --scenarios S2
) > $OUT/slotA.log 2>&1 &
(
  run P1_GC --grid G-C --scenarios S1
  run P1_GI --grid G-I --scenarios S1
  until [ -f $OUT/P1_GR/prices_S1.csv.gz ]; do sleep 30; done
  run P1_GR_GE --grid G-R --gas-gate evidence --s2-rule sf --s1-from $OUT/P1_GR --scenarios S3 S2
) > $OUT/slotB.log 2>&1 &
wait
echo "$(date -u +%FT%TZ) ALL_DONE"
