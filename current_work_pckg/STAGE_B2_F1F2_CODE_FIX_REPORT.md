# STAGE_B2_F1F2_CODE_FIX_REPORT：B2 失败修复（F1 + F2-b）代码报告

- 日期：2026-10-21
- 依据：`BYOP_ERCOT_StageB_B2_F1F2_Repair_and_Rerun_Work_Package_v1.0_2026-10-21.md` Phase F（§5）
- 失败基线：`951ddb8bd6bca575a78ecd3562c34e252c528f89`
- 修复提交：`__FIX_SHA__`
- 本轮只修改代码和测试。**没有运行任何求解器**，没有执行 B2-R。

## 0. F0 基线检查

- 分支 `mainline-v13-stageA`：开始修改时，本地、GitHub 和 L2 都在 `951ddb8b`。
- L2 上没有正在运行的本项目算例。
- 失败证据都没有改动：
  - `STAGE_B2_GRID_ONLY_REPORT.md`
  - `STAGE_B2_RETURN_MANIFEST.md`
  - `STAGE_B_STAGE_AUDIT_B2.json`
  - `MAINLINE_V13_GREAL_MID_PILOT_S01/` 目录（含 `scenarios/S0/*`）
  - `MAINLINE_V13_GREAL_MID_PILOT_S01.excerpt.log`
- 修复后的运行写入新目录 `MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1`；`run()` 拒绝覆盖已有 `case_manifest.json` 的目录。

## 1. F1：统一所有主线求解路径的 Gurobi 参数

| 位置（`workflow/byop/model/rearch_mech.py`） | 修改前 | 修改后 |
|---|---|---|
| 新常量 `MAINLINE_GUROBI_LP_OPTIONS`（第 91 行） | — | `Method=2, Crossover=0, BarConvTol=1e-5, FeasibilityTol=1e-3, OptimalityTol=1e-4, BarHomogeneous=1`，与正式求解的配置相同；结构测试 `QA-F1` 逐项比对 `config.solving.solver_options` |
| `gurobi_apply_options()`（第 1034 行） | — | 在导出的 gurobipy 模型上设置这 6 项和 Threads，并用 `getParamInfo` **读回 Gurobi 实际采用的值** |
| `lex_presolve()`（第 1061 行） | 只设置 `Threads`；其余为默认值（FeasibilityTol 1e-6，concurrent LP） | 在 `gm.optimize()` **之前**调用 `gurobi_apply_options`。<br>在 `lex_<tag>.json` 中记录：实际参数、status 及其名称、`ConstrVio` / `BoundVio` / `ObjVal`、12 个目标各自的 `ObjNVal`、行列数、整数变量数。<br>**先写文件，再抛出不可行错误**，失败时诊断信息不会丢失 |
| `developer_joint()`（S2，第 1358 行） | `Method=2, Crossover=0, BarConvTol=1e-7`，没有 FeasibilityTol 和 OptimalityTol | `ml_dev_solver_options()` = 同一组参数 + `OutputFlag=0` + Threads |
| `lex_audit()`（第 1125 行）和 `go()` | — | Speed-First 字典序层级在**最终（成本阶段）解**上重新核验：<br>• A1：总量 ≥ T\*(1−1e-6) − 1e-3<br>• A2：每个合格母线 S ≥ z\*R(1−1e-6) − 1e-3<br>• 带 `LEXIMIN_ZERO_LOCK` 的层级不施加约束，并显式标出<br>结果写入 `lex_audit_<tag>.csv` 和 `res['lex_audit_all_satisfied']` |
| `private_mode()` | 不变 | 主线不调用（mainline 使用 `developer_joint`），保持原样 |

- 不可行的原因**仍是待验证的假说**。如果 F1 之后 S1 仍不可行，按工作包 §2.3 的顺序诊断；需要计算 IIS 时，另行申请求解授权。
- 没有放宽 no-harm 的 0.001 MW 余量，也没有提高 FeasibilityTol。
- 仍是连续 LP，不引入整数变量。

## 2. F2-b：主线既有用户的切负荷罚价改为 35,685 USD/MWh

| 项目 | 修改前 | 修改后 | 证据 / 适用范围 |
|---|---|---|---|
| 主线罚价：原生背景负荷和继承爬坡的 `load_shed` | 10,000 | **35,685 USD/MWh**；`configure_mainline()` 第 112 行，在创建任何负荷切除机组之前设置 `M.SHED_COST` | Brattle（2024）*Value of Lost Load Study for the ERCOT Region*，Table 17，ERCOT 全系统 1 小时停电 VOLL（2024 美元，没有做通胀换算），作为 3 小时快照的规划层可靠性权重 |
| 非主线（v240 / v1.0 / 7 区） | 10,000 | **不变**（`v240_mech.SHED_COST = 1e4`） | 测试 `test_f2_mainline_voll_only` |
| B1 校准常量 `S0CAL_SHED` / `S0CAL_COST` | 1e8 / 1e7 | **不变**；不重跑 ERM / S0CAL | 同上测试 |
| 研究 AIDC 未交付、PCLR 计划中断、非计划中断 | 价值 v / 失算力价格 `c_interrupt` | **不变** | 这些项目使用不同的价格，不受 `SHED_COST` 影响 |
| 账本 | — | `load_shed_PV_USD`（v240）和 `ml_shed_accounting()`（继承爬坡）使用同一个 `M.SHED_COST`；`existing_customer_shed_loss_VOLL_PV_USD` 只作为报告列，不加进社会成本 | 合成测试 `test_f2_shed_books_once` |
| 运行记录 | — | case manifest `mainline.voll`：VOLL、来源、年份、时长口径、实际使用的 `SHED_COST`；每个情景的 `res['F2_load_shed_mc']`：最小值、最大值、继承爬坡机组数、不等于 VOLL 的机组数 | — |

## 3. 运行组织与门控

- 新入口 `pilot_s01_fix`：
  - case-id `MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1`
  - `--scenarios S0 S1_EARLIEST`
  - 使用原 B1 的 ERM 和 S0CAL 文件
  - 没有 `--attribution`
- 配置已复位：`run_authorization: NOT_APPROVED`，`approved_git_sha: null`。
- 即使把旧 SHA `8636c08d` 写回配置，门控也会拒绝：自那之后 `workflow/byop/model` 和 `run` 已有改动，manifest 哈希也已更新。
- B3 / B4 没有取得任何授权。

## 4. 无求解器测试（L2）

| 测试 | 结果 |
|---|---|
| 静态测试 `test_mainline_v13.py` | **39 / 39 通过**（原有 30 项 + 9 项新测试） |
| 新测试覆盖的内容 | • 用伪造 Gurobi 模型核对字典序模型的参数，确认在 optimize 之前设置<br>• 开发商 LP 的参数<br>• 失败时先写日志再报错<br>• `lex_audit` 的 A1 / A2 / 零锁定判断<br>• 主线 VOLL 只在主线生效，B1 常量不变<br>• 切负荷账本不重复计算，VOLL 报告列不加入社会成本<br>• `pilot_s01_fix` 的 DRY 命令<br>• 门控在 `NOT_APPROVED` 下拒绝<br>• B1 输入哈希不变 |
| 结构测试 `structural_mainline_v13.py` | **45 / 45 通过**（新增 QA-F1、QA-F2）；`solver_executions = 0`，3 次求解调用被拦截 |
| QA-F1 | `MAINLINE_GUROBI_LP_OPTIONS` 与 `gurobi-default` 配置逐项一致（Gurobi 参数名不区分大小写；配置中写作 `method` / `crossover`） |
| QA-F2 | 主线 S0 的 6 台 `load_shed` 机组（含 5 台继承爬坡）全部为 35,685 USD/MWh；S0 校准构建时全部为 1e8 |
| 门控 | `approved: false`，原因：`run_authorization=NOT_APPROVED`、`approved_git_sha` 缺失、4 个文件的 SHA-256 不一致 |
| DRY | 命令只含 `--scenarios S0 S1_EARLIEST`，输出到 `…_PILOT_S01_F1F2_V1`，使用原 B1 的 ERM / S0CAL，没有 `--attribution` |

**披露**：正式求解还设置了 `ScaleFlag 1, Seed 123, AggFill 0, PreDual 0, GURO_PAR_BARDENSETHRESH 200`。这 5 项不在工作包规定的 6 项之内，没有加到字典序模型和开发商 LP 中。它们不影响可行性和最优性容差。

```text
FIX_STATUS: COMPLETE
RUN_AUTHORIZATION: NOT_APPROVED
SOLVER_EXECUTIONS_SINCE_FIX: 0
NEXT_STEP: RESEARCHER_APPROVAL_OF_NEW_CODE_SHA_REQUIRED (__FIX_SHA__), then B2-R pilot_s01_fix only
```
