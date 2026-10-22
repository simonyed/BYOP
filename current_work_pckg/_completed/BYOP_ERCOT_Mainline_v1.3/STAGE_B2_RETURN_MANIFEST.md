# STAGE_B2_RETURN_MANIFEST：Stage B B2 交付清单

- 日期：2026-10-21
- 状态：`B2_BLOCKED_TECHNICAL` 与 `B2_BLOCKED_FOR_SCIENCE`
- 分支：`mainline-v13-stageA`（没有合并到 `main`）
- 运行时代码 HEAD：`af00b32a`；批准 SHA：`8636c08d`
- 本清单所在提交：见 GitHub 分支最新提交

## GitHub 上的文件（tracked）

| 文件 | 内容 |
|---|---|
| `current_work_pckg/BYOP_ERCOT_StageB_B2_GridOnly_Execution_Package_v1.0_2026-10-21.md` | 工作包原文 |
| `current_work_pckg/STAGE_B2_GRID_ONLY_REPORT.md`、本文件 | B2 报告与交付清单 |
| `workflow/byop/post/stage_b2_tables.py` | B2 专题表生成程序（纯后处理；兼容中途失败的算例） |
| `workflow/results/BYOP/mainline/STAGE_B_STAGE_AUDIT_B2.json` | 阶段审计：哈希、授权、每次求解的状态 |
| `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01/STAGE_B2_*.csv` | 6 个专题表：48 个母线—年份、S0 可靠性、S0 公共扩张、POI / 网络诊断、B1 对账、审计清单 |
| `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01/scenarios/S0/*` | S0 的检查点：`solve.json`、`scenario_summary.csv`、`ledger.csv`、`duals.csv`、`service.csv`、`poi_ledger.csv`、`poi_upgrade_ledger.csv` |
| 同一目录下的 `S0_shed_by_snapshot_frozen.csv.gz`、`shed_by_bus_S0.csv`、`prices_S0.csv.gz`、`solver_S0.log`、`rearch_solver.log`、`RUN_GATE.json`、`poi_cohorts.csv` | S0 冻结切负荷、价格、求解日志、门控记录 |
| `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01.excerpt.log`、`pilot_s01_driver.log` | 控制台日志摘录（含 traceback 和求解参数）、驱动日志 |

## 只在 L2 上的文件

| 文件 | 原因 | SHA-256 |
|---|---|---|
| `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01.log`（80 MB） | 体积超过同步上限 | `3231ca740bbbb4532d6e6d44725fb8ece52453c3c9726ca6332d24f53b28bb57` |
| `workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc` | `.nc` 文件被忽略 | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb` |

## 没有生成的文件（S1 没有求出解）

S1 没有求出解，算例在写最终结果表之前就停止了，所以没有：

- `case_manifest.json`、`MAINLINE_CASE_MANIFEST.json`、`MAINLINE_GATE_CHECKS.csv`
- `S1_GRID_OFFER.csv`、`PCLR_TRIGGERS.csv`、`shed_by_bus_S1_EARLIEST.csv`
- `scenarios/S1_EARLIEST/*`
