# W2_APPROVAL_REQUEST: NEXT-07 S0 reserve-requirement probe (one LP)

**Status: NOT_APPROVED.** No solver has been called in NEXT-07. This request covers exactly one optimizer call.

## What is being asked

| Item | Value |
|---|---|
| Approvable code SHA (40 chars) | **`5df4dda75efc4efb1796393c1131f93a8d801599`** (`main`-line branch `mainline-v13-stageA`, = L2 HEAD, = GitHub) |
| Config | `workflow/config/config.byop_post_v16_n07_reserve_probe.yaml` (fields now `NOT_APPROVED / null / null`) |
| Manifest | `current_work_pckg/BYOP_NEXT_07/N07_RESERVE_PROBE_PRE_RUN_MANIFEST.json` (L2-built at `a01b29b8`; 150 code + 110 input files, 0 mismatches; no code changed since) |
| Scope | S0 only, 2026–2031, `--sample-weeks 26` (the same 2 weeks + B7 stress days as the formal S0), v1.6 baseline `a623fb6d…747d16`, `--no-harm on` |
| The one change | `PV16M-reserve_req` RHS **3,000 → 0 MW**. Every other row is kept: online capacity, thermal min-load, reserve headroom and ramp, BESS reserve power and energy (end and start of snapshot), segment-neutral SOC, COD-lagged paid expansion, committed DWB/PBRP. |
| Budget | **1 scenario attempt / 1 top-level call (`S0_COST`), 0 retries**. Own ledgers in `workflow/results/BYOP/next07_s0_reserve_probe/`. |
| Label | Result carries `DIAGNOSTIC_NONCOMPLIANT_WITH_FORMAL_3GW_REQUIREMENT`. It never replaces `POST_V16_A2_S0S1`. No no-harm reference is written. |
| Command (L2, `workflow/`) | `bash byop/run/run_post_v16_a2.sh n07_gate`, then `THREADS=<T> bash byop/run/run_post_v16_a2.sh n07_reserve_probe` |

## Evidence that it is the intended experiment (W1, 0 solver calls)

`W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json` and `W1_CONSTRAINT_DIFF.csv` record three S0 models built in one L2 process with the solver intercepted. The build order was REF (formal), then PROBE, then REF2 (formal again).

- **REF vs PROBE: exactly one difference.** The 816 RHS values of `PV16M-reserve_req` change from 3000 to 0. Every other part is identical:
  - all 13 variable groups (labels and bounds);
  - all 1,015 constraint groups (coordinates, variable labels, coefficients, signs, RHS);
  - the objective;
  - every network input hash;
  - the snapshot weights (8,760 h per year).
- **REF2 == REF exactly** (0 differences). The probe leaves no state behind. `POST_V16['reserve_MW']` stays 3000.
- The formal A2 config and the NEXT-06 full-year config have no diagnostic. The A2 and A3 gates refuse a `diagnostic` block anywhere except this exact config.
- The guard pins the run arguments: `--end`, `--sample-weeks` and `--scenarios` cannot drift.
- **Size:** 2,660,074 variables, 7,107,710 constraints, 35,171,029 nonzeros. This is identical to the formal S0, which solved in 2,281 s (barrier, 10 threads, factor 4.5 GB).
- **Tests:** L2 full suite **272 passed / 0 failed**, including 16 new NEXT-07 tests.

## L2 at request time (2026-10-23 11:14 EDT)

- Load average 7.2.
- Other users' jobs: one 6-core `lmp` and long-running single-core processes.
- Memory: 243 GB available.
- `/datasets`: 494 GB free.
- Gurobi academic licence active through the venv.

Planned `THREADS`: measured at launch. The budget is B = 24 − other users' cores, capped at about 16. Expected wall time is about 40 min; peak memory about 15 GB.

## Proposed approval sentence (please send in chat)

> I approve the NEXT-07 W2 reserve probe at approved_git_sha 5df4dda75efc4efb1796393c1131f93a8d801599: S0 only, 2026–2031, 26 sample weeks, PV16M-reserve_req RHS 0 MW, at most 1 S0_COST optimizer call, 0 retries; approved_by: <your identifier>.

After that message, and not before, I will:
1. make a config-only commit of the three fields;
2. re-run the gate on L2 (it must pass);
3. launch once, monitored in the background;
4. on success, build `W2_RESERVE_CAUSAL_COMPARISON.csv` and the verdict using the pre-registered classes (≥ 80 % / 20–80 % / < 20 % reduction of the 2026 Far West nightly shed, or `DIAGNOSTIC_BLOCKED`).

Any failure is recorded and stops the branch. There is no retry.
