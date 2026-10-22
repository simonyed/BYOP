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

**BYOP ERCOT: multi-bus spatial distribution of new data-center load, 2026–2035, implementation package v1.0 (2026-10-22)**

- Original text: `BYOP_ERCOT_AIDC_Geospatial_Distribution_Implementation_Work_Package_v1.0_2026-10-22.md`
  - SHA-256 `dd529f75…1f4b04`, byte-identical to the original placed by the researcher
- Nature: code implementation plus solver-free validation; `RUN_AUTHORIZATION: NOT_APPROVED`; no solver may be run
- Local data folder: `work_pkgs/BYOP_ERCOT_DC_Siting_PNNL/`
  - Raw PNNL data, with `raw/SHA256SUMS.txt`
- Archived on 2026-10-22: the previous package, Mainline v1.3, with Stage A, Stage B (B0–B3) and the PNNL siting design note. All of it is in `_completed/BYOP_ERCOT_Mainline_v1.3/`.
  - Files that the code reads were repointed to the archive path:
    - the gate manifest `MAINLINE_V13_PRE_RUN_MANIFEST.json`;
    - the tech and gas-price attachments that the tests check.

| File | Content | Status |
|---|---|---|
| `BYOP_ERCOT_AIDC_Geospatial_Distribution_Implementation_Work_Package_v1.0_2026-10-22.md` | Original work package | Provided by the researcher |
| `AIDC_GEO_DYNAMIC_V1_IMPLEMENTATION_REPORT.md` | Implementation report: what was done, ledger, results, POI risks, tests, C0–C5 dependencies | Done |
| `AIDC_GEO_DYNAMIC_V1_DATA_PROVENANCE_AND_FILTERS.md` | PNNL sources and licenses, mapping rules, deduplication, crypto-mining exclusion, basis comparisons | Done |
| `AIDC_GEO_DYNAMIC_V1_LEGACY_VS_DYNAMIC_AUDIT.md` | Legacy 8-bus vs dynamic 16-bus, by bus and year (input side) | Done |
| `AIDC_GEO_DYNAMIC_V1_POI_GAS_RISK_REGISTER.csv` | POI / gas / RE risks per research bus (§5.3) | Done |
| `AIDC_GEO_DYNAMIC_V1_QA_RESULTS.csv` | GEO-01 to GEO-14 | All PASS |
| `AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json` | Pending manifest of the dynamic geography | `NOT_APPROVED`, `SOLVER_EXECUTIONS=0` |
| `AIDC_GEO_DYNAMIC_V1_RETURN_MANIFEST.md` | GitHub SHA, file list, return in the fixed format | Done |
