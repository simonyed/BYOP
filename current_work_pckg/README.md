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

**BYOP ERCOT: C0 audit repair and C1 fixed-asset diagnostics, execution prompt v1.4 (2026-10-22)**

- Original text: `BYOP_C0_Repair_C1_Diagnostics_Execution_Prompt_v1.4_2026-10-22.md` (provided by the researcher in this folder)
- Stage A: C0 repair (phase / switchable / match confidence), solver executions 0. Stage B: limited C1 fixed-asset dispatch LPs (at most 6) under a separate C1 config; formal run gates stay NOT_APPROVED. Stage C: report, commit, stop.
- Archived on 2026-10-22: the C0 v1.3 package (official anchor evidence package attachments + all C0 v1.3 reports, kept as the v1.3 snapshot) is in `_completed/ERCOT_2025_Official_Anchor_v1.3_C0/`; the official raw files stay in `workflow/data/byop/ercot_official_anchor_2025/`
- `.gitignore`: the LaTeX rule `*.[1-9]` had hidden folders whose names end in a version number (the v1.3 package attachments were never on GitHub); `current_work_pckg/**` is now always tracked

| File | Content | Status |
|---|---|---|
| `BYOP_C0_Repair_C1_Diagnostics_Execution_Prompt_v1.4_2026-10-22.md` | Original work package | Provided by the researcher |
| `C0_REPAIR_REPORT.md` + `C0_PHASE_RECONCILIATION.csv`, `C0_RECLASS_REVISED.csv`, `C0_SWITCHABLE_LEDGER.csv`, `C0_MATCH_CONFIDENCE.csv`, `C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv`, `C0_REPAIR_BEFORE_AFTER.csv`, `C0_REPAIR_QA.json` | Stage A: C0 phase / switchable / confidence repair (v1.3 snapshot kept) | Done (10/10 tests) |
| `BYOP_C1_Continuation_Addendum_v1.4.1_2026-10-22.md` | Researcher continuation addendum (0 new solves) | Provided by the researcher |
| `C1_FIXED_ASSET_DIAGNOSTICS.md` + `C1_CASE_MANIFEST.csv`, `C1_METRICS.csv`, `C1_SHEDDING_EVENTS.csv`, `C1_BINDING_LINES.csv`, `C1_GENERATION_BY_FUEL.csv`, `C1_QA.json`, `C1_SOLVE_LOG.csv`, `C1_MAIN_RESULTS.png`, `C1_CALIBRATION_VS_C1_SETUP.csv`, `C1_UPLIFT_LINE_CHECK.csv`, `C1_SHED_EVENTS_LABELLED.csv` | Stage B: C1 fixed-asset diagnostics (4 cases, 8 calls incl. 4 retries; continuation: collector / acceptance fix, read-only explanation) | Done; causes of the 72.9 GWh and of the storage overlap NOT isolated (proposals only) |

Not done (by design): asset revisions, re-calibration, C1-X1 / storage two-stage check, max-net-load window (MISSING_INPUT), S0-S3 / B3.
