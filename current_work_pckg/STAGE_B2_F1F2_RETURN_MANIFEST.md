# STAGE_B2_F1F2_RETURN_MANIFEST：Phase F 交付清单

- 日期：2026-10-21
- 分支：`mainline-v13-stageA`（没有合并到 `main`）
- 失败基线：`951ddb8bd6bca575a78ecd3562c34e252c528f89`
- **修复提交（待批准）**：`4fb58a450f43bab2b23e354601ea2d6b88b50ae9`
- `RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS_SINCE_FIX: 0`
- B2-R 状态：`NOT_AUTHORIZED`

## GitHub 上的文件（tracked）

| 文件 | 内容 |
|---|---|
| `current_work_pckg/BYOP_ERCOT_StageB_B2_F1F2_Repair_and_Rerun_Work_Package_v1.0_2026-10-21.md` | 工作包原文 |
| `current_work_pckg/STAGE_B2_F1F2_CODE_FIX_REPORT.md`、`STAGE_B2_F1F2_PRE_RUN_AUDIT.md`、本文件 | Phase F 交付物 |
| `current_work_pckg/MAINLINE_V13_PRE_RUN_MANIFEST.json` | 按修复代码重建的代码 / 输入 SHA-256（含 L2 基准 `.nc`） |
| `workflow/byop/model/rearch_mech.py` | F1：`MAINLINE_GUROBI_LP_OPTIONS`、`gurobi_apply_options`、`ml_dev_solver_options`、`lex_audit`；F2-b：`ML_VOLL` |
| `workflow/byop/run/run_mainline.sh` | `pilot_s01_fix` 入口 |
| `workflow/byop/tests/test_mainline_v13.py`、`structural_mainline_v13.py` | 新增 9 项静态测试；新增结构检查 QA-F1、QA-F2 |
| `workflow/config/config.byop_ercot_mainline.yaml` | 授权复位为 `NOT_APPROVED`，`approved_git_sha` 设为 `null` |
| `workflow/results/BYOP/mainline/static_tests_f1f2.log`、`structural_tests_f1f2.log`、`_structural_f1f2/*`、`gate_check_f1f2.log`、`dry_pilot_s01_fix.log` | 无求解器测试记录 |

## 保留未动的失败证据

- `STAGE_B2_GRID_ONLY_REPORT.md`
- `STAGE_B2_RETURN_MANIFEST.md`
- `STAGE_B_STAGE_AUDIT_B2.json`
- `MAINLINE_V13_GREAL_MID_PILOT_S01/`
- `MAINLINE_V13_GREAL_MID_PILOT_S01.excerpt.log`

## 只在 L2 上的文件

| 文件 | SHA-256 |
|---|---|
| `workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc` | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb` |
| `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01.log`（80 MB，失败运行的完整日志） | `3231ca740bbbb4532d6e6d44725fb8ece52453c3c9726ca6332d24f53b28bb57` |

## 回报格式（工作包 §9）

```text
REPO: simonyed/BYOP
BRANCH: mainline-v13-stageA
FAILED_BASELINE_SHA: 951ddb8bd6bca575a78ecd3562c34e252c528f89
FIX_COMMIT_SHA: 4fb58a450f43bab2b23e354601ea2d6b88b50ae9
APPROVED_SHA: NOT_YET
F1_TOLERANCE_CONSISTENCY: PASS (configuration tests; S1 feasibility NOT_TESTED until B2-R)
F2_MAINLINE_VOLL: 35685 USD/MWh (Brattle 2024 1h planning proxy)
BASELINE_SHA_MATCH: PASS
B1_CALIBRATION_REUSED: YES
SOLVER_EXECUTIONS_BEFORE_APPROVAL: 0
B2_R_STATUS: NOT_AUTHORIZED
S0_BACKGROUND_SHED_MWh: NOT_AVAILABLE
S0_REDOAK_PEAK_SHED_MW: NOT_AVAILABLE
S1_LEX_STATUS: NOT_AVAILABLE
M1_VALIDITY: NOT_YET
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_REVIEW
```
