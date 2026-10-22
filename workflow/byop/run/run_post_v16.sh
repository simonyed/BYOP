#!/usr/bin/env bash
# BYOP post-v1.6 execution package v1.1 - the ONLY entry for the post-v1.6 main line (L2, from pypsa-usa/workflow).
# Isolated from byop/run/run_mainline.sh (legacy step0 / pilot / pilot_core stay for historical reproduction only).
#   bash byop/run/run_post_v16.sh tests      static tests (no solver)
#   bash byop/run/run_post_v16.sh a1_dry     A0: build LP-R / LP-N models + structural checks + sizes (NO solver)
#   bash byop/run/run_post_v16.sh a1_gate    print the post-v1.6 gate verdict for LP-R and LP-N (no build, no solver)
#   bash byop/run/run_post_v16.sh a1_lp_r    A1 LP-R (H_resource)  - GATED (researcher approval + SHA pins)
#   bash byop/run/run_post_v16.sh a1_lp_n    A1 LP-N (H_network)   - GATED, only after an optimal LP-R
#   bash byop/run/run_post_v16.sh a2_s0s1    A2 S0 + S1_EARLIEST on the v1.6 baseline - REFUSED (needs the A2 reserve-rule
#                                            implementation and a separate approval); shows the command shape only
# Every command passes --base <v1.6 prepared.nc> explicitly (SHA-checked by the gate; no fallback) and NONE passes the
# legacy --calibrate / --erm-cal / --s0-calibrate / --s0-cal-file (ERM-02 B and free S0CAL are not part of the new line).
# DRY=1 prints the assembled commands and runs nothing.
set -u
W=/datasets/prgm/BYOP_impact/pypsa-usa/workflow
BASE=$W/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc
A1CFG=config/config.byop_post_v16_a1.yaml
A2CFG=config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml
A1="python -W ignore $W/byop/run/post_v16_a1.py --base $BASE --threads ${THREADS:-16}"
A2="python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --config $A2CFG --base $BASE --case-id POST_V16_A2_S0S1 --out $W/results/BYOP/post_v16_a2/POST_V16_A2_S0S1 --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-16} --scenarios S0 S1_EARLIEST"
run() {
  if [ -n "${DRY:-}" ]; then echo "CMD $*"; return 0; fi
  source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate; cd $W
  echo "$(date -u +%FT%TZ) start $*"; "$@"; local rc=$?; echo "$(date -u +%FT%TZ) end rc=$rc"; return $rc
}
case "${1:-}" in
  tests)    run python -m pytest -q byop/tests/test_post_v16_a0.py ;;
  a1_dry)   run $A1 --dry ;;
  a1_gate)  run $A1 --gate --lp R && run $A1 --gate --lp N ;;
  a1_lp_r)  run $A1 --lp R ;;
  a1_lp_n)  run $A1 --lp N ;;
  a2_s0s1)  if [ -n "${DRY:-}" ]; then echo "CMD $A2"; else echo "refusing: A2 is not approved and the post-v1.6 reserve rule is not yet in the mainline (rearch_mech.py --post-v16 exits 3)"; exit 3; fi ;;
  *)        echo "usage: $0 tests|a1_dry|a1_gate|a1_lp_r|a1_lp_n|a2_s0s1"; exit 2 ;;
esac
