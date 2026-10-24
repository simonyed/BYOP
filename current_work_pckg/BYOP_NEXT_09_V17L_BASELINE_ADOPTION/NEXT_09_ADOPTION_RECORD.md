# NEXT-09: v1.7L adoption record (S0 / S1 held)

**Status: v1.7L ADOPTED as the formal lossy 2025 baseline. The S0 / S1 rerun is NOT_APPROVED in the config (researcher hold). 0 optimizer calls.**

## 1. Researcher messages (chat, 2026-10-24, about 01:05 EDT; verbatim)

> I adopt v1.7L (f9aa87ae) as the formal lossy 2025 baseline and approve the NEXT-09 paired S0/S1 rerun on it at approved_git_sha c0b29f34709ed88229b42d7fd368ddd6370b5301: S0 then S1_EARLIEST; at most 3 optimizer calls; 0 retries; no A3/S2/S3; approved_by: sw2434@cornell.edu.

Followed, while the approval commit was being prepared, by:

> 先不要运行S0和S1优化问题 (do not run the S0 and S1 optimization problems yet)

## 2. Executor reading and actions

The second message takes precedence for anything that runs the solver. So:

| Item | Action |
|---|---|
| Baseline adoption | **Done.** Config-only commit `7f4e27cb` edits only the three adoption fields of `workflow/config/config.byop_baseline_registry.yaml`: `adoption_status: ADOPTED`, `adopted_git_sha: c0b29f34709ed88229b42d7fd368ddd6370b5301`, `adopted_by: sw2434@cornell.edu`. The registry normalised SHA is unchanged (`b7ab7c6f…`), so the S0 / S1 manifest stays current. |
| S0 / S1 approval fields | **Not set.** `config.byop_post_v17l_s0s1.yaml` stays `NOT_APPROVED / null / null`. The approval sentence above is recorded here. The fields are set in a config-only commit only after the researcher lifts the hold in chat. |
| Optimizer calls | **None.** Nothing was launched, and no L2 solve process was started. |
| Tests | `2d61c015` (tests only, outside `CLEAN_PATHS`) updates the three tests that read the live registry to its adopted state. |

Since `c0b29f34`, the only change in the gate's `CLEAN_PATHS` is the adoption-only registry edit, which the approved-SHA rule tolerates. So `c0b29f34` remains a valid approved SHA when the hold is lifted.

## 3. State after adoption (L2, static checks only, HEAD `2d61c015`)

| Check | Result |
|---|---|
| `baseline_registry.summary()` | formal = `v17l` (`f9aa87ae…`), adoption_problems = [] |
| S0 / S1 gate, v1.7L config (`v17l_gate`) | S0 is refused **only** on `run_authorization=NOT_APPROVED`, `approved_by missing` and `approved_git_sha missing`. S1 is refused on the same three fields plus its stage rule: no PASSED S0 in its own out_dir, and no own no-harm reference. |
| Old v1.6 A2 config | Refused: "v16 is not the formal baseline (superseded)", and `--base` is not the formal baseline. |
| v1.6 NetCDF, diagnostics, earlier ledgers and approvals | Unchanged (nothing written). |

## 4. To lift the hold

Make one config-only commit setting `run_authorization: APPROVED`, `approved_git_sha: c0b29f34709ed88229b42d7fd368ddd6370b5301` and `approved_by: sw2434@cornell.edu` in `config.byop_post_v17l_s0s1.yaml`. Then sync, measure L2 load, and run `THREADS=<B> bash byop/run/run_post_v16_a2.sh v17l_s0s1`: S0, then S1_EARLIEST; at most 3 optimizer calls; 0 retries; no A3 / S2 / S3.
