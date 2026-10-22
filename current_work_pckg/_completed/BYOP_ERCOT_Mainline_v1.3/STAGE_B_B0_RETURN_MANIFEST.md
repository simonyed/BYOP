# STAGE_B_B0_RETURN_MANIFEST：Stage B B0 交付清单

- 日期：2026-10-21
- `RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS: 0`

| 项目 | 值 |
|---|---|
| 仓库 / 分支 | <https://github.com/simonyed/BYOP/tree/mainline-v13-stageA>（**没有合并到 `main`**） |
| 审计起点 | `24c913b7a03257725c0bdc05afddd230724eeff1` |
| B0 代码修复提交（待研究者批准的 SHA） | `8636c08d4b9dd11e7624f6fb52f92c91cf439ad0` |
| PR 创建链接 | <https://github.com/simonyed/BYOP/compare/main...mainline-v13-stageA?expand=1> |
| L2 | `/datasets/prgm/BYOP_impact/pypsa-usa`：与本地逐字节一致，HEAD 指向同一提交 |

## 修改与新增的文件（tracked）

| 文件 | 内容 |
|---|---|
| `workflow/byop/model/rearch_mech.py` | `select_s2_final()`；`s2_selection` 写入 manifest；新增 `s2_converged` 检查 |
| `workflow/byop/post/collect_mainline.py` | 正式表只用 S2_final；诊断表单列；`matched_service_check()` 48 键严格匹配；缺失不算通过；PARTIAL_PILOT |
| `workflow/byop/run/run_mainline.sh` | 新增 `pilot_s01` / `pilot_core` / `attribution`；各阶段目录独立；`DRY=1` |
| `workflow/byop/tests/test_mainline_v13.py` | 新增 9 项 B0 测试（共 30 项） |
| `current_work_pckg/STAGE_B_B0_CODE_FIX_REPORT.md`、`STAGE_B_PRE_RUN_AUDIT.md`、本文件 | B0 交付物 |
| `current_work_pckg/MAINLINE_V13_PRE_RUN_MANIFEST.json` | 重建的代码和输入 SHA-256 |
| `current_work_pckg/MAINLINE_V13_DECISION_LOG.md`、`README.md` | 增加 Stage B 记录 |
| `current_work_pckg/BYOP_ERCOT_StageB_Pilot_Execution_Work_Package_v1.0_2026-10-21.md` | 工作包原文（研究者提供） |
| `workflow/results/BYOP/mainline/static_tests.log`、`structural_tests.log`、`gate_check.log`、`_structural/*` | 无求解器测试记录 |

## 只在 L2 上的文件（ignored / L2-only）

| 文件 | 状态 | SHA-256 |
|---|---|---|
| `workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc` | L2-only（`.nc` 被忽略） | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb` |

关于工作包归档：Stage B 是 v1.3 主线的后续阶段，工作包 §0 把 `MAINLINE_V13_*` 列为承接文件，所以这些文件**留在 `current_work_pckg/`，没有移入 `_completed/`**。主线工作结束后再一起归档。
