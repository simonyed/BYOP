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

**ERCOT 2025 official anchor calibration: collected evidence, definition rulings and code implementation supplement v1.3 (2026-10-22) — C0 offline reconciliation**

- Original text and attachments (byte-identical): `ERCOT_2025_Official_Anchor_v1.3/` (README_AND_EXECUTION_PROMPT_v1.3.md, SOURCE_MANIFEST.json, CHECKSUMS.sha256, annual_capacity_page.png, researcher scripts rebuild_evidence.py / prepare_package.py)
- Official raw files (27 MB): `workflow/data/byop/ercot_official_anchor_2025/` (local + L2, not on GitHub; SHA in SOURCE_MANIFEST.json). Full local copy including `repo_snapshot/`: `work_pkgs/ERCOT_2025_Official_Anchor_v1.3/`
- Nature: C0 offline reconciliation + code wiring; solver executions = 0; run gates stay NOT_APPROVED
- Archived on 2026-10-22: the previous package (AIDC multi-bus siting v1.0) and all its reports are in `_completed/BYOP_ERCOT_AIDC_Geospatial_Distribution_v1.0/`; the dynamic-geography config and tests now point to the archived pending manifest

| File | Content | Status |
|---|---|---|
| `ERCOT_2025_Official_Anchor_v1.3/README_AND_EXECUTION_PROMPT_v1.3.md` | Original work package | Provided by the researcher |
| `C0_INPUT_RECONCILIATION.md` | C0 report: tasks A-D, coverage, bridge, unexplained residuals, items returned to the researcher, tests | Done |
| `C0_GENERATOR_MATCH.csv` | CDR Dec-2025 units <-> ReEDS model groups (match / candidate / ambiguous / unmatched / model-only) | Audit only |
| `C0_CAPACITY_BRIDGE.csv` | AR / Dec trend / CDR core / model, exact decomposition, unexplained residual | Done |
| `C0_PIPELINE_RECLASS_SUGGESTIONS.csv` | 2025-operating units held in the 2026 pipeline (and reverse) - suggestions, not applied | Researcher decision |
| `C0_LOAD_ACCOUNTING.csv` | time axis and demand components (17 checks) | All PASS |
| `C0_HISTORICAL_AIDC_EVIDENCE.csv` | evidence class of the 2025 AIDC stock and the 460.73 MW IT ramp (values unchanged) | Done |
| `C0_UPLIFT_LEDGER.csv` | synthetic / 2025 calibration (MVA) / S0CAL (MW) line layers | Done |
| `C0_QA.json` | all checks, coverage, solver_executions = 0 (L2 run incl. read-only .nc check) | Done |
