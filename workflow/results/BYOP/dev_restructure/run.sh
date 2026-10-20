#!/usr/bin/env bash
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow; O=/datasets/prgm/BYOP_impact/pypsa-usa/workflow/results/BYOP/dev_restructure
python -W ignore byop/model/v250_mech.py --grid G-R --case-id RS_COUNTY --out $O/county --smoke --start 2026 --end 2027 --erm-cal results/BYOP/p1/ERM_CAL/erm02_calibration.json --threads 8 --scenarios S1 > $O/county.log 2>&1; echo COUNTY_EXIT $?
python -W ignore byop/model/v240_mech.py --case-id RS_7ZONE --out $O/z7 --smoke --start 2026 --end 2027 --threads 8 --scenarios S1 > $O/z7.log 2>&1; echo Z7_EXIT $?
