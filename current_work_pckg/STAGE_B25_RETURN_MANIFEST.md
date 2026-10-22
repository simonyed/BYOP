# STAGE_B25_RETURN_MANIFEST：B2.5 交付清单

- 日期：2026-10-21（纽约时间）
- 分支：`mainline-v13-stageA`（没有合并到 `main`）
- **B2.5 代码提交（待批准）：`__B25_SHA__`**
- `RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS_B25: 0`，B3 状态：`NOT_AUTHORIZED`

## GitHub 上的文件（tracked）

| 文件 | 内容 |
|---|---|
| `current_work_pckg/BYOP_ERCOT_StageB25_B3_Exploratory_Work_Package_v1.0_2026-10-21.md` | 工作包原文 |
| `current_work_pckg/STAGE_B25_METHOD_AUDIT_REPORT.md`、`STAGE_B25_CODE_AND_GATE_AUDIT.md`、本文件 | B2.5 交付物 |
| `current_work_pckg/MAINLINE_V13_PRE_RUN_MANIFEST.json` | 重建的哈希 |
| `workflow/results/BYOP/mainline/B25_METHOD_AUDIT/STAGE_B25_ERM_2026_METHOD_AUDIT.csv` | 2026 年 ERM 方法审计（48 个母线—年份键 + 3 行汇总口径） |
| `…/B25_METHOD_AUDIT/STAGE_B25_S0_S1_SHED_EXPOSURE.csv` | S0 / S1 切负荷对照与 2028 年时段重合 |
| `…/B25_METHOD_AUDIT/STAGE_B25_RELIABILITY_FLAGS.csv` | 可靠性筛查与方法标志 |
| `…/B25_METHOD_AUDIT/STAGE_B25_COST_BOOK_DECOMPOSITION.csv` | S0 / S1 成本账本拆分（恒等式 PASS） |
| `…/B25_METHOD_AUDIT/stage_b25_audit_L2.log` | 在 L2 上运行审计脚本的日志 |
| `workflow/byop/post/collect_mainline.py`、`stage_b25_audit.py`；`workflow/byop/model/rearch_mech.py`；`workflow/byop/run/run_mainline.sh`；`workflow/byop/tests/test_mainline_v13.py`；`workflow/config/config.byop_ercot_mainline.yaml` | 代码与配置 |
| `workflow/results/BYOP/mainline/static_tests_b25.log`、`structural_tests_b25.log`、`_structural_b25/*`、`gate_check_b25.log`、`dry_pilot_core_b3e.log` | 无求解器测试记录 |

B2-R 的所有已发布文件**都没有改写**。

## 只在 L2 上的文件

| 文件 | SHA-256 |
|---|---|
| `workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc` | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb` |
| B2-R 完整日志 `MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1.log`（163 MB） | 见 `STAGE_B2_F1F2_RERUN_AUDIT.json` |

## B3-E 获批后的执行顺序

1. 研究者批准 `__B25_SHA__`，在配置中写入 `APPROVED` 和该 SHA。
2. 依次执行：`gate`（必须 `approved: true`）→ `DRY=1 … pilot_core_b3e` → `THREADS=20 bash byop/run/run_mainline.sh pilot_core_b3e`。
3. 完成后**停止**，交付工作包 §4.2 的文件。
