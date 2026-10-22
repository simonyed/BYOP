# current_work_pckg: the current work package and its reports

Storage rules (set by the researcher on 2026-10-20):

| Content | Location | Uploaded to GitHub / L2? |
|---|---|---|
| The work package currently being executed (placed here by the researcher) | `pypsa-usa/current_work_pckg/` | Yes |
| Reports based on that package: decision log, execution report, sync report, etc. | `pypsa-usa/current_work_pckg/` | Yes |
| Raw data the package needs, plus preprocessing scripts and their logs | `D:\BYOP_impact\work_pkgs\<folder for the package>\` | **No** (local only) |
| Preprocessed data that the model actually reads | The designated place inside pypsa-usa, e.g. `workflow/byop/inputs/<category>/`, with a source note | Yes |
| Executed programs and run configuration | `workflow/byop/{model,build,post,run,tests}/`, `workflow/config/config.byop_*.yaml` | Yes |
| Run results and logs (small files only) | `workflow/results/BYOP/`, `workflow/logs/byop/` | Yes (`.nc` and other large files are excluded) |

Project-level documents that span work packages are in `workflow/byop/docs/`.

## Current work package

**BYOP post-v1.6 execution package v1.1: operating reliability and joint connection headroom (2026-10-22). Authorised scope: A0 only (zero solver calls).**

- Original package: `BYOP_Post_v1.6_Execution_v1.1/` (CURRENT_EXECUTION_WORK_PACKAGE_v1.1.md, decision register, research memo, registers, build_research_data.py; byte-identical)
- Staged data: `raw/` -> `workflow/data/byop/post_v16_execution_v11/raw/` (local + L2, not git); `derived/` -> `workflow/byop/inputs/post_v16/derived/` (tracked); SHA QA `workflow/byop/inputs/post_v16/STAGING_SHA_QA.json` (53/53, 20/20, rebuild 19/19 text-identical); full local copy `work_pkgs/BYOP_Post_v1.6_Execution_v1.1/`
- Archived on 2026-10-22: v1.6 calibration close-out and all its reports -> `_completed/BYOP_Calibration_Closeout_v1.6/`

| File | Content | Status |
|---|---|---|
| `BYOP_Post_v1.6_Execution_v1.1/` | Original work package | Provided by the researcher |
| `A0_IMPLEMENTATION_REPORT.md` | A0 report with the fixed return template | READY_FOR_A1_APPROVAL (no solver called) |
| `A0_RETURN_PACKAGE.zip` | Return package (reports, QA, manifests, diff, tests, hashes) | Done |
| `POST_V16_A0_RECONCILIATION.md` | v1.6 items closed / carried; HEAD / L2 SHA / staging / old-manifest checks | Done |
| `BASELINE_AND_RESERVE_CONSTRAINT_INVENTORY.csv` | Constraint audit (old ERM / ERM-02 / S0CAL / SOC / no-harm / POI / stress / gas / TPIT) with keep / replace / remove | Done |
| `POST_V16_A1_FORMULATION.md` | Static A1 formulation (1 h stress LP, 3 GW / 1 h reserve, lambda, copperplate vs network, POI book) | Done (not solved) |
| `POST_V16_A1_PRE_RUN_MANIFEST.json` | Pins code / inputs / config / v1.6 base for the A1 gate | NOT an approval |
