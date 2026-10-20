#!/usr/bin/env bash
# v2.5.0 control group (doc RUN-0): legacy 7-zone v2.4.0 code, unchanged, at the P1 settings (2026-2031, 2 weeks/yr, POI lead 0)
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
O=/datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/p1_ctrl7; mkdir -p $O
V=/datasets/prgm/BYOP_impact/pypsa-usa/workflow/byop/model/v240_mech.py
python -W ignore $V --case-id CTRL7_CAL --out $O/CAL --calibrate --start 2026 --end 2031 --sample-weeks 26 --threads 4 > $O/CAL.log 2>&1 && echo CAL_OK
python -W ignore $V --case-id CTRL7_S1 --out $O/S1 --start 2026 --end 2031 --sample-weeks 26 --threads 4 --erm-cal $O/CAL/erm02_calibration.json --scenarios S0 S1 S3 S2 > $O/S1.log 2>&1 && echo S1_OK
