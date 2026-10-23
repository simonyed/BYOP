# W5P_APPROVAL_REQUEST: NEXT-07 lossless S0 confirming probe (one LP)

**Status: NOT_APPROVED. Prepared only. No solver has been called for it.**

## What is being asked

| Item | Value |
|---|---|
| Approvable code SHA | **`bf61d873b1e2e1d0df9befd70d3b41896df967d6`** (`mainline-v13-stageA` = L2 HEAD = GitHub) |
| Config | `workflow/config/config.byop_post_v16_n07_lossless_probe.yaml` (fields now `NOT_APPROVED / null / null`) |
| Manifest | `current_work_pckg/BYOP_NEXT_07/N07_LOSSLESS_PROBE_PRE_RUN_MANIFEST.json` (L2-built at `8567700b`; 151 code + 110 input files, 0 mismatches; no gated file changed since) |
| Scope | S0 only, 2026–2031, `--sample-weeks 26` (the same 2 weeks + B7 stress days as the formal S0), v1.6 baseline `a623fb6d…747d16`, no-harm on |
| The one change | `transmission_losses` **2 → 0** in the solve options. Applied per solve to a copy of the solve config (`rearch_mech.pv16_solve_config`); the baseline meta is never modified. |
| Kept formal | 3,000 MW reserve with online-capacity / min-load / headroom / ramp / BESS energy rows, segment-neutral SOC, `linearized_unit_commitment` (baseline meta), committed DWB/PBRP, COD-lagged paid expansion, sampling, VOLL, costs |
| Budget | **1 scenario attempt / 1 top-level call (`S0_COST`), 0 retries**. Own ledgers in `workflow/results/BYOP/next07_s0_lossless_probe/`. |
| Label | `DIAGNOSTIC_LOSSLESS_NOT_THE_FORMAL_LOSS_BASIS`. Never a formal S0, and no no-harm reference is written. It does not choose the study's loss basis. |
| Command (L2, `workflow/`) | `bash byop/run/run_post_v16_a2.sh n07l_gate`, then `THREADS=<T> bash byop/run/run_post_v16_a2.sh n07l_lossless_probe` |

## Evidence that it is the intended experiment (0 solver calls)

`W5P_MODEL_EQUALS_EXCEPT_LOSSES.json` and `W5P_CONSTRAINT_DIFF.csv` record three S0 models built in one L2 process with the solver intercepted. The build order was REF (formal), then PROBE, then REF2 (formal again).

**REF vs PROBE: verdict `W5P_STATIC_PASS`.**
- **Removed:** the `Line-loss` variable and the constraint groups `Line-loss_upper` and `Line-loss_tangents-{1,2}-{±1}`.
- **Rows that held loss terms** (`Bus-nodal_balance`, `Bus-meshed-30-nodal_balance`, `Line-fix-s-upper/lower`): identical after those terms are removed.
- **Everything else identical:** all other variables (coordinates, bounds), all other rows (signs, RHS and canonical terms), the objective and the network inputs.
- **Comparison method:** removing a variable shifts linopy labels, so terms are compared by (variable name, position).
- **The 3,000 MW reserve row** is present and identical in both.
- **REF2 == REF:** 0 differences.

**Size:**

| Model | Variables | Constraints | Nonzeros |
|---|---:|---:|---:|
| PROBE | 2,527,882 | 6,446,750 | 33,452,533 |
| Formal S0 | 2,660,074 | 7,107,710 | 35,171,029 |

The formal S0 solved in 2,281 s (10 threads); the reserve probe in 877 s (16 threads).

**Guards (tested):**
- **Registry:** exactly two diagnostics exist, reserve RHS and transmission losses. Each is valid only in its own config file, with its value, its out_dir, run arguments 2026–2031 / 26 weeks / [S0] and a budget of 1 / 1.
- **Refusals:** the A2 and A3 gates refuse anything else, and the formal A2 and NEXT-06 configs carry no diagnostic.

**Tests:** L2 full suite at this code: **297 passed / 0 failed** (8 new tests).

**Expected L2 load:** the machine was at load 2.3 / 24 cores with 243 GB free at 13:19 EDT. Planned: 16 threads, about 15–40 min, under 15 GB.

## Pre-registered reading (fixed before the solve)

The metric is the 2026 Far West nightly weighted shed. The comparison is against the formal S0 (47,297.9 MWh) on the same snapshot index.

| Lossless probe result | Reading |
|---|---|
| Reduction ≥ 80 % | **Loss basis confirmed** as the main cause. The researcher then chooses one loss basis for calibration and S0–S3; a paired S0/S1 rerun follows on that basis, separately approved. |
| 20–80 % | Losses are a major but not the only cause. The persisted flows / injections rank the rest (e.g. the TL21 / p620 0 supply difference). |
| < 20 % | Losses are not the main cause. The remaining mesh-injection difference is examined read-only. |
| Infeasible / warning / acceptance failure | `DIAGNOSTIC_BLOCKED`: evidence kept, no retry. |

## Proposed approval sentence (send in chat)

> I approve the NEXT-07 lossless S0 probe at approved_git_sha bf61d873b1e2e1d0df9befd70d3b41896df967d6: S0 only, 2026–2031, 26 sample weeks, 3 GW reserve, transmission_losses 0, at most 1 S0_COST optimizer call, 0 retries; approved_by: <your identifier>.

## Note: the A3 manifest is now stale

`A3_PRE_RUN_MANIFEST.json` was built at `4edf7bac`. This preparation changed gated A3-path code (`rearch_mech.py`, `post_v16_mainline.py`, `post_v16_a2_gate.py`, `run_post_v16_a2.sh`). The A3 gate would report SHA mismatches until the manifest is rebuilt. A3 is locked anyway (no approval, S0 verdict unresolved), and the rebuild belongs with any future A3 request.
