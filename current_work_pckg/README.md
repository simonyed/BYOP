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

**BYOP v1.6: calibration close-out of the common 2025 baseline (2026-10-22)**

- Original package: `BYOP_Calibration_Closeout_v1.6/` (main text, EXECUTOR_PROMPT, DECISION_POLICY.yaml, ASSET_DECISIONS.csv, SOURCE_MANIFEST.json, rebuild_evidence.py; byte-identical)
- Evidence CSVs (tracked): `workflow/byop/inputs/calibration_v16/evidence/`; official raw files (31 MB, local + L2, SHA checked 16/16): `workflow/data/byop/calibration_closeout_v16/raw/`; full local copy incl. repo_snapshot: `work_pkgs/BYOP_Calibration_Closeout_v1.6/`
- Scope: X1 network representation (fixed pre-calibration x / r, thermal-limit uplift only), 12 asset decisions, monthly switchable caps (dispatch + ERM credit once), at most 2 annual LPs (LP1 minimum uplift, LP2 reloaded fixed-asset check), zero retries; official PRM bridge and transmission check; formal gates stay NOT_APPROVED
- Archived on 2026-10-22: v1.5 (C1-X1 / storage validation) and all its reports are in `_completed/BYOP_C1_X1_Storage_Validation_v1.5/`

| File | Content | Status |
|---|---|---|
| `BYOP_Calibration_Closeout_v1.6/` | Original work package | Provided by the researcher |
