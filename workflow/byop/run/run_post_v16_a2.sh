#!/usr/bin/env bash
# BYOP-POST-V16-NEXT-02 A2 entry (L2, from the A2 checkout's workflow/). Independent of run_post_v16.sh (A1, SHA-pinned, unchanged).
#   bash byop/run/run_post_v16_a2.sh tests        A2 static unit tests (no solver)
#   bash byop/run/run_post_v16_a2.sh structural   build S0 / S1_EARLIEST / S3 + NEXT-02 audits, every solver call intercepted
#   bash byop/run/run_post_v16_a2.sh manifest     (re)write current_work_pckg/A2_PRE_RUN_MANIFEST.json (no solver)
#   bash byop/run/run_post_v16_a2.sh gate         print the A2 gate verdict for S0 and S1_EARLIEST (no build, no solver)
#   bash byop/run/run_post_v16_a2.sh n06_diag     NEXT-06 W2: ONE diagnostic S0 LP, 2026 full year - GATED by config.byop_post_v16_n06_diag.yaml
#   bash byop/run/run_post_v16_a2.sh n07_tests    NEXT-07 static tests (no solver)
#   bash byop/run/run_post_v16_a2.sh n07_static   NEXT-07 W1: build REF (3 GW) and PROBE (RHS 0) S0, constraint-by-constraint diff (no solver)
#   bash byop/run/run_post_v16_a2.sh n07_manifest / n07_gate
#   bash byop/run/run_post_v16_a2.sh n07_reserve_probe  NEXT-07 W2: ONE S0 LP with PV16M-reserve_req RHS 0 MW, 2026-2031, 26 weeks -
#                                                 GATED by config.byop_post_v16_n07_reserve_probe.yaml (1 call, 0 retries)
#   bash byop/run/run_post_v16_a2.sh n07l_static / n07l_manifest / n07l_gate   NEXT-07 W5 lossless probe: solver-free diff, manifest, gate
#   bash byop/run/run_post_v16_a2.sh n07l_lossless_probe  ONE S0 LP with transmission_losses 0 (else formal), 2026-2031, 26 weeks -
#                                                 GATED by config.byop_post_v16_n07_lossless_probe.yaml (1 call, 0 retries)
#   bash byop/run/run_post_v16_a2.sh lb_build / lb_manifest / lb_gate   NEXT-07 W6: lossy 2025 LP2 re-validation (static build, manifest, gate)
#   bash byop/run/run_post_v16_a2.sh lb_lp2_asis / lb_lp2_r_parallel     GATED by config.byop_loss_basis_lp2.yaml (1 call each, 0 retries)
#   bash byop/run/run_post_v16_a2.sh a3_manifest / a3_gate   NEXT-07 W4: A3 pre-run manifest / gate verdict (no solver)
#   bash byop/run/run_post_v16_a2.sh a3_e2e       NEXT-07 W4: zero-solver A3 end-to-end dry run (injected gate, scratch ledgers)
#   bash byop/run/run_post_v16_a2.sh s0s1         S0 then S1_EARLIEST - GATED (separate researcher approval of
#                                                 config/config.byop_post_v16_a2.yaml; 2 calls, 0 retries, STOP on any failure)
# DRY=1 prints the commands and runs nothing.
set -u
W=$(cd "$(dirname "$0")/../.." && pwd)
BASE=$W/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc
CFG=config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml
OUT=$W/results/BYOP/post_v16_a2/POST_V16_A2_S0S1
A2="python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --config $CFG --base $BASE --case-id POST_V16_A2_S0S1 --out $OUT --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-16} --scenarios S0 S1_EARLIEST"
run() {
  if [ -n "${DRY:-}" ]; then echo "CMD $*"; return 0; fi
  source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate; cd $W
  echo "$(date -u +%FT%TZ) start $*"; "$@"; local rc=$?; echo "$(date -u +%FT%TZ) end rc=$rc"; return $rc
}
case "${1:-}" in
  tests)      run python -m pytest -q byop/tests/test_a2_a3_static.py byop/tests/test_next02_a2_static.py ;;
  structural) run python -W ignore byop/tests/structural_post_v16_a2.py --out results/BYOP/post_v16_a2_static/_structural_next02 ;;
  manifest)   run python byop/build/build_post_v16_a2_manifest.py ;;
  gate)       run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps({s: G.check(s, '$BASE') for s in G.STAGES}, indent=1))" ;;
  s0s1)       run $A2 ;;
  n06_manifest) run python byop/build/build_post_v16_a2_manifest.py config/config.byop_post_v16_n06_diag.yaml ;;
  n06_gate)   run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps(G.check('S0', '$BASE', cfg_path='config/config.byop_post_v16_n06_diag.yaml'), indent=1))" ;;
  n06_diag)   run python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --a2-config config/config.byop_post_v16_n06_diag.yaml --config $CFG --base $BASE --case-id NEXT06_S0_DIAG_FULLYEAR_2026 --out $W/results/BYOP/next06_s0_diag_fullyear_2026 --start 2026 --end 2026 --sample-weeks 0 --threads ${THREADS:-16} --scenarios S0 ;;
  n07_tests)  run python -m pytest -q byop/tests/test_next07_reserve_probe.py ;;
  n07_static) run python -W ignore byop/tests/structural_n07_reserve_probe.py --out results/BYOP/next07_s0_reserve_probe/_static_w1 ;;
  n07_manifest) run python byop/build/build_post_v16_a2_manifest.py config/config.byop_post_v16_n07_reserve_probe.yaml ;;
  n07_gate)   run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps(G.check('S0', '$BASE', cfg_path='config/config.byop_post_v16_n07_reserve_probe.yaml'), indent=1))" ;;
  n07_reserve_probe) run python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --a2-config config/config.byop_post_v16_n07_reserve_probe.yaml --config $CFG --base $BASE --case-id NEXT07_S0_RESERVE_PROBE --out $W/results/BYOP/next07_s0_reserve_probe --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-16} --scenarios S0 ;;
  n07l_static) run python -W ignore byop/tests/structural_n07_lossless_probe.py --out results/BYOP/next07_s0_lossless_probe/_static ;;
  n07l_manifest) run python byop/build/build_post_v16_a2_manifest.py config/config.byop_post_v16_n07_lossless_probe.yaml ;;
  n07l_gate)  run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a2_gate as G; print(json.dumps(G.check('S0', '$BASE', cfg_path='config/config.byop_post_v16_n07_lossless_probe.yaml'), indent=1))" ;;
  n07l_lossless_probe) run python -W ignore $W/byop/model/rearch_mech.py --mainline --post-v16 --a2-config config/config.byop_post_v16_n07_lossless_probe.yaml --config $CFG --base $BASE --case-id NEXT07_S0_LOSSLESS_PROBE --out $W/results/BYOP/next07_s0_lossless_probe --start 2026 --end 2031 --sample-weeks 26 --threads ${THREADS:-16} --scenarios S0 ;;
  lb_build)   run python -W ignore byop/run/loss_basis_lp2.py --build ;;
  lb_manifest) run python byop/build/build_post_v16_a2_manifest.py config/config.byop_loss_basis_lp2.yaml ;;
  lb_gate)    run python -c "import sys, json; sys.path.insert(0, 'byop/run'); import loss_basis_lp2 as L; print(json.dumps({s: L.check(s) for s in L.STAGES}, indent=1))" ;;
  lb_lp2_asis) run python -W ignore byop/run/loss_basis_lp2.py --stage LP2_LOSSY_ASIS --threads ${THREADS:-16} ;;
  lb_lp2_r_parallel) run python -W ignore byop/run/loss_basis_lp2.py --stage LP2_LOSSY_R_PARALLEL --threads ${THREADS:-16} ;;
  a3_manifest) run python byop/build/build_post_v16_a2_manifest.py config/config.byop_post_v16_a3.yaml ;;
  a3_gate)    run python -c "import sys, json; sys.path.insert(0, 'byop/model'); import post_v16_a3_gate as G; print(json.dumps({s: G.check(s, '$BASE') for s in ['S0', 'S3']}, indent=1))" ;;
  a3_e2e)     PYTHONPATH=byop/tests run python -W ignore byop/tests/structural_n07_a3_e2e.py --out results/BYOP/next07_s0_reserve_probe/_a3_e2e ;;
  *)          echo "usage: $0 tests|structural|manifest|gate|s0s1|n06_manifest|n06_gate|n06_diag|n07_tests|n07_static|n07_manifest|n07_gate|n07_reserve_probe|n07l_static|n07l_manifest|n07l_gate|n07l_lossless_probe|lb_build|lb_manifest|lb_gate|lb_lp2_asis|lb_lp2_r_parallel|a3_manifest|a3_gate|a3_e2e"; exit 2 ;;
esac
