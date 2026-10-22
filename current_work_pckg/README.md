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

**BYOP: C1-X1 network comparison and storage degeneracy validation, work package v1.5 (2026-10-22)**

- Original text: `BYOP_C1_X1_Storage_Validation_Work_Package_v1.5_2026-10-22.md` (provided by the researcher)
- Scope: two annual 3 h LP stages only (X1 = calibrated capacity + raw x / r on the 18 uplift lines; then storage-throughput minimisation on X1 with the economic cost and total shed held within tolerance); own config + solve log; formal gates stay NOT_APPROVED; no asset change
- Archived on 2026-10-22: the v1.4 package (C0 repair / C1 diagnostics) + continuation addendum v1.4.1 and all their reports are in `_completed/BYOP_C0_Repair_C1_Diagnostics_v1.4/`

| File | Content | Status |
|---|---|---|
| `BYOP_C1_X1_Storage_Validation_Work_Package_v1.5_2026-10-22.md` | Original work package | Provided by the researcher |
| `C1_X1_STORAGE_VALIDATION_REPORT.md` | Report: X1 impedance comparison, storage two-stage check, evidence requests, network-representation proposal | Done (stop for researcher review) |
| `C1_X1_LINE_INPUT_AUDIT.csv`, `C1_X1_STAGE_COMPARISON.csv`, `C1_X1_STORAGE_BY_UNIT.csv`, `C1_X1_SHED_BY_BUS_MONTH.csv`, `C1_X1_LINE_COMPARISON.csv`, `C1_X1_SHED_EVENTS_LABELLED.csv`, `C1_X1_QA.json`, `C1_X1_SOLVE_LOG.csv` | 2 effective LP stages, 0 retries, both exactly optimal | Done |
| `C0_PRIORITY_ASSET_EVIDENCE_REQUESTS.csv` | 32 asset items for researcher rulings (existing values kept) | Waiting for researcher |

Not done (by design): network representation change, asset revisions, re-calibration, S0-S3 / B3.
