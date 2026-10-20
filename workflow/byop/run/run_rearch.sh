#!/usr/bin/env bash
# BYOP ERCOT Rearchitecture v1.0 (2026-10-20) gate runs on L2, from pypsa-usa/workflow:
#   bash byop/run/run_rearch.sh tests      unit tests (WP-C C6) on the synthetic one-site world
#   bash byop/run/run_rearch.sh cal        ERM-02 B calibration on the TAMU 64-bus baseline (G-W and G-K worlds)
#   bash byop/run/run_rearch.sh g1         G1: S0 on the new backbone (G-W)
#   bash byop/run/run_rearch.sh matrix     G2/G3: S0-S3 + S1 delay attribution for G-W / G-K / G-U (3 POIs)
#   bash byop/run/run_rearch.sh sens       G3 sensitivities on G-U (BYOP lead high, POI case low/high, no PCLR, gas L1 high)
#   bash byop/run/run_rearch.sh s5         P0 Step 5: small acceptance case (G-K, 2026-2029, P0 code, S0_repaired) -> rearch_p0/S5_GK
#   bash byop/run/run_rearch.sh r2         P0 Step 6: formal reruns R2_GW / R2_GK / R2_GU (P0 code, S0_repaired, attribution)
# R1_* / DEV_GU / G1 results are BASELINE_DIAGNOSTIC (pre-P0 code); P0 runs write to results/BYOP/rearch_p0/
# Screening resolution as P1: 2026-2031 annual periods, 2 sampled weeks per year (weeks 0 and 26), 3 h.
set -u
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
OUT=$W/results/BYOP/rearch
cd $W; mkdir -p $OUT
COMMON="--start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-8}"
run() {   # name, args...
  local name=$1; shift
  mkdir -p $OUT/$name/code && cp $W/byop/model/*.py $OUT/$name/code/
  echo "$(date -u +%FT%TZ) start $name"
  python -W ignore $W/byop/model/rearch_mech.py --case-id $name --out $OUT/$name $COMMON "$@" > $OUT/$name.log 2>&1
  echo "$(date -u +%FT%TZ) end $name exit $?"
}
case "${1:-}" in
  tests)  python -m pytest -q byop/tests/test_rearch_units.py byop/tests/test_p0_units.py 2>&1 | tee $OUT/unit_tests.log ;;
  cal)    run ERM_CAL_GW --setting G-W --calibrate &
          run ERM_CAL_GK --setting G-K --calibrate &
          wait ;;
  g1)     run G1_S0_GW --setting G-W --erm-cal $OUT/ERM_CAL_GW/erm02_calibration.json --scenarios S0 ;;
  matrix) run R1_GW --setting G-W --erm-cal $OUT/ERM_CAL_GW/erm02_calibration.json --attribution &
          run R1_GK --setting G-K --erm-cal $OUT/ERM_CAL_GK/erm02_calibration.json --attribution &
          run R1_GU --setting G-U --erm-cal $OUT/ERM_CAL_GK/erm02_calibration.json --attribution &
          wait ;;
  sens)   C=$OUT/ERM_CAL_GK/erm02_calibration.json
          run R1_GU_byopHigh --setting G-U --erm-cal $C --byop-case high --scenarios S0 S1 S2 S3 S3_mS2 &
          run R1_GU_poiLow --setting G-U --erm-cal $C --case low --scenarios S0 S1 S2 S3 S3_mS2 &
          run R1_GU_poiHigh --setting G-U --erm-cal $C --case high --scenarios S0 S1 S2 S3 S3_mS2 &
          wait
          run R1_GU_noPCLR --setting G-U --erm-cal $C --s2-modes GO_F GF IS --scenarios S0 S1 S2 S3_mS2 &
          run R1_GU_gasHigh --setting G-U --erm-cal $C --gas-case high --scenarios S0 S1 S2 S3 S3_mS2 &
          wait ;;
  s5|r2)  O2=$W/results/BYOP/rearch_p0; mkdir -p $O2
          CAL=${S0CAL:-$W/results/BYOP/rearch_s0repair/S0CAL_minuplift_2026_2031/S0_CALIBRATION.csv}
          P0="--base-assets main --s0-cal-file $CAL --interrupt-cap 0.005 --no-harm on"
          run2() { local name=$1; shift; mkdir -p $O2/$name/code && cp $W/byop/model/*.py $O2/$name/code/
                   echo "$(date -u +%FT%TZ) start $name"
                   python -W ignore $W/byop/model/rearch_mech.py --case-id $name --out $O2/$name --sample-weeks 26 "$@" > $O2/$name.log 2>&1
                   echo "$(date -u +%FT%TZ) end $name exit $?"; }
          if [ "$1" = s5 ]; then
            run2 S5_GK --setting G-K --erm-cal $OUT/ERM_CAL_GK/erm02_calibration.json --start 2026 --end 2029 --threads ${THREADS:-12} $P0
          else
            run2 R2_GW --setting G-W --erm-cal $OUT/ERM_CAL_GW/erm02_calibration.json --start 2026 --end 2031 --threads 8 --attribution $P0 &
            run2 R2_GK --setting G-K --erm-cal $OUT/ERM_CAL_GK/erm02_calibration.json --start 2026 --end 2031 --threads 8 --attribution $P0 &
            run2 R2_GU --setting G-U --erm-cal $OUT/ERM_CAL_GK/erm02_calibration.json --start 2026 --end 2031 --threads 8 --attribution $P0 &
            wait
          fi ;;
  *) echo "usage: $0 tests|cal|g1|matrix|sens|s5|r2"; exit 1 ;;
esac
echo "$(date -u +%FT%TZ) DONE ${1:-}"
