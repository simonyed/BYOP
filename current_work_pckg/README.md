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
