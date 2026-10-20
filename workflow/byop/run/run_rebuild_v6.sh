#!/usr/bin/env bash
# v2.5.0 D250-22 rebuild after the static-renewable bug: raw baseline -> LP ITL calibration -> baseline v6
# -> TX ERM-02 B calibration -> P1 matrix (run_p1.sh) -> P1b (GC x4/x8 headroom; the v5-rerun case is dropped).
set -u
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
B=$W/results/BYOP/baseline_2025_county; mkdir -p $B $W/results/BYOP/p1
PREP=resources/BYOP_ERCOT_County/networks/texas/elec_s_c192s_ec_lv1.0_REM-ERM-3h_E.nc
step() { echo "$(date -u +%FT%TZ) $1"; }
step raw;  python -W ignore $W/byop/build/build_2025_baseline_county.py --prep $PREP > $B/build_raw.log 2>&1 || { step RAW_FAIL; exit 1; }
step lp;   python -W ignore $W/byop/build/calibrate_itl_lp.py $B/baseline_2025_county_raw_uncalibrated.nc $B/ITL_2025_CALIBRATION_LP.csv 22 > $B/cal_lp.log 2>&1 || { step LP_FAIL; exit 1; }
step v6;   python -W ignore $W/byop/build/build_2025_baseline_county.py --prep $PREP --itl-cal-lp $B/ITL_2025_CALIBRATION_LP.csv > $B/build_v6.log 2>&1 || { step V6_FAIL; exit 1; }
step erm;  O=$W/results/BYOP/p1/ERM_CAL; rm -rf $O; mkdir -p $O
python -W ignore $W/byop/model/v250_mech.py --grid G-R --case-id ERM_CAL --out $O --calibrate --start 2026 --end 2031 --sample-weeks 26 --threads 22 > $O.log 2>&1 || { step ERM_FAIL; exit 1; }
step p1;   bash $W/byop/run/run_p1.sh > $W/results/BYOP/p1/run_p1.out 2>&1
step p1b;  bash $W/byop/run/run_p1b.sh > $W/results/BYOP/p1/run_p1b.out 2>&1
step ALL_REBUILD_DONE
