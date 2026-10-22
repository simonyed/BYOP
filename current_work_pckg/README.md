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
| `CALIBRATION_CLOSEOUT_REPORT.md` | Close-out report incl. the fixed return (§9) | **COMPLETE_WITH_STATED_LIMITATIONS**; code `85cd6ae5`; 2 LPs, 0 retries |
| `BASELINE_V16_INPUT_DIFF.csv`, `ASSET_OVERRIDE_AUDIT.csv`, `SWITCHABLE_CAP_QA.csv` | Anchor 1: asset decisions, fleet bridge by unit / carrier / bus, monthly switchable caps | Done |
| `RELIABILITY_ANCHOR_BRIDGE.csv` | Anchor 2: official PRM reproduced, same-scope model rows, bridge, ERM rows | Done (4,000 MW thermal basis unresolved) |
| `TRANSMISSION_EXTERNAL_VALIDATION.csv` | Anchor 3: official constraints vs LP2 | Done (West export not reproduced) |
| `BASELINE_V16_FIXED_ASSET_QA.json`, `BASELINE_V16_SOLVE_LOG.csv` | LP2 reloaded fixed-asset QA; solve log | PASS |
| `S0_S1_BASELINE_V16_PREPARED_MANIFEST.json` | Prepared S0 / S1 on the v1.6 baseline (config `config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml`) | NOT RUN, NOT_APPROVED |
| `V16_CLOSEOUT_SUMMARY.json` | Collector summary and deliverable SHA-256 | Done |

New v1.6 common baseline (L2 only): `workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`, SHA-256 `a623fb6d…747d16`.
