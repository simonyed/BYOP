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

**BYOP A0.2 v1.1: pre-solve model integration (A0.1 repair + TECH_COMP_2 + environment -> permit -> COD), 2026-10-22. Authorised scope: code / inputs / static tests only (zero solver calls).**

- Original package: `BYOP_A0_2_PreSolve_Integration_v1.1/` (EXECUTION_WORK_PACKAGE.md, ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md, original v2.0 ZIP + 9 files, tools, static examples; byte-identical); full local copy `work_pkgs/BYOP_A0_2_PreSolve_Integration_v1.1/`
- Technology inputs (byte-identical, SHA-pinned): `workflow/byop/inputs/tech_calibrated_v2/`
- Archived on 2026-10-22: post-v1.6 A0 and its reports -> `_completed/BYOP_Post_v1.6_Execution_v1.1_A0/`

| File | Content | Status |
|---|---|---|
| `A0_2_INTEGRATION_REPORT.md` | Decision + acceptance, fixed return block | READY_FOR_RESEARCHER_APPROVAL; 0 solver calls |
| `A0_1_REPAIR_REPORT.md` | FIX-01..04 evidence | PASS_STATIC |
| `TECH_V2_IMPLEMENTATION_AUDIT.md` | TECH_COMP_2 landing, v1.3 -> v2 differences | Done |
| `SOURCE_TO_PARAMETER_CROSSWALK.csv` | source -> loader -> state -> build / constraint -> ledger -> test | 147 rows |
| `TECH_COST_AND_COD_AUDIT.csv`, `PERMIT_TO_COD_CAUSAL_AUDIT.csv` | costs, COD milestones, permit attribution (ENV-01..10 + 16 buses) | DRY_NOT_SOLVED |
| `TECH_PERMIT_STATUS.csv` | 16 research buses: site FIPS / ozone class / flags | 8 known, 8 UNKNOWN_CONSERVATIVE |
| `TECH_SUPPLY_USAGE_STATIC_QA.csv`, `TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv`, `TECH_EMISSIONS_PROXY_STATIC_QA.csv`, `TECH_RE_BESS_FIRM_STATIC_QA.csv` | pools / rights, environment evidence, PTE / ledger, RE+BESS firm builder | DRY_NOT_SOLVED |
| `A2_TECH_READINESS_MATRIX.csv` | READY_STATIC / NOT_IMPLEMENTED / BLOCKED per module | Done |
| `A0_2_TEST_SUMMARY.json`, `A1_GATE_VERDICT.json`, `POST_V16_A1_PRE_RUN_MANIFEST.json` | L2 tests 196 passed; gate NOT_APPROVED; manifest (locked) | Done |
| `A0_2_RETURN_PACKAGE.zip` | Small files for local / L2 / GitHub reconciliation | Done |
