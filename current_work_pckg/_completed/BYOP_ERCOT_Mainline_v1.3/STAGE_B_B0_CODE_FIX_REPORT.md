# STAGE_B_B0_CODE_FIX_REPORT：Stage B B0 代码修复报告

- 日期：2026-10-21
- 依据：`BYOP_ERCOT_StageB_Pilot_Execution_Work_Package_v1.0_2026-10-21.md` §3、§4、§5 B0、§7.1
- 审计起点：`24c913b7`；分支 `mainline-v13-stageA`
- **`RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS: 0`**。B0 只修改代码和测试，没有运行任何 LP

## 1. S2 最终迭代与 M4 的一致性（§3）

### 1.1 `S2_final` 的统一定义

- 本轮选择**新名称 `S2_final`**（§3.2 中二选一的第一种），在所有正式汇总中统一使用，不与 `S2` 混用。
- `S2_final` = S2 迭代循环中**最后一轮**（收敛时是第一个通过交付性核验的那一轮；最多 3 轮仍未收敛时是第 3 轮）。
  - 这一轮的公共电网**实际交付量**就是 `saved['S2_service']`，也就是 `S3_mS2` 固定的 8 × 6 母线—年度 IT。
- **实现**：`rearch_mech.select_s2_final()`。
  - 把所选轮次（`S2` / `S2_it2` / `S2_it3`）的汇总、账本、服务表、POI 账本、POI 升级账本和对偶表，复制一份并标为 `S2_final`，同时加 `S2_selected_iteration` 列。
  - 原迭代标签全部保留，作为诊断证据。
  - 另写 `scenarios/S2_final/S2_SELECTION.json`。
  - `case_manifest.json` 新增 `s2_selection`（`selected_iteration`、`selected_tag`、`formal_label`、`converged`）。
  - `checks` 新增 `s2_converged`。
- **没有改变**：任何优化约束、技术数据、经济目标、迭代次数上限（3）和收敛容差（`max(0.5, 1e-3 × 计划量)`）。

### 1.2 后处理（`collect_mainline.py`）

| 要求 | 实现 |
|---|---|
| 正式表全部来自同一轮 | 正式表只包含 `S0`、`S1_EARLIEST`、`S3`、`S2_final`、`S3_mS2`（以及可选的 `S1E_x*` 归因情景），涉及：`MAINLINE_SCENARIO_SUMMARY`、`BUS_DELIVERY_AND_DELAY`、`PUBLIC_INVESTMENT_DELTA`、`ASSET_COMMITMENT_LEDGER`、对偶值 |
| 开发商表 | `MAINLINE_S2_MODES_TECH.csv` 只取 `iteration == selected_iteration` |
| 中间迭代 | 原始 `S2` / `S2_itN` 只进入 `MAINLINE_DIAGNOSTIC_S2_ITERATIONS.csv`、`MAINLINE_DIAGNOSTIC_S2_DEVELOPER_ALL_ITERATIONS.csv`，**不参与任何加总** |
| 48 键匹配 | `matched_service_check()`：<br>• 母线 × 年份的键集合完全一致；<br>• 每个键唯一；<br>• 两边各 48 个键；<br>• 没有缺失或非数值；<br>• 最大绝对差 ≤ 0.5 MW IT。<br>任一项失败时 `gap_status = INVALID_DIAGNOSTIC_ONLY`，诊断值保留 |
| 门控检查 | `MAINLINE_GATE_CHECKS.csv` 和 `MAINLINE_CASE_MANIFEST.json` 新增：`selected_S2_iteration`、`s2_converged`、`matched_service_48_keys_present`、`matched_service_keys_unique`、`matched_service_no_missing`、`matched_service_max_abs_gap_IT_MW`、`matched_service_valid`、`phase`、`SCIENTIFIC_USE` |
| 缺失不算通过 | 必需检查值为 `None` / `NaN` 时，一律记为未通过：<br>• 所有阶段：`true_LP`、`all_optimal`、`no_harm_existing_customers`、`served_le_requested`、`online_IT_monotone`<br>• CORE 阶段另加：`s2_converged`、`s2_public_delivers_developer_plan`、`matched_service_valid`、`dc_energy_balance`<br>其他检查只要为 False，也会使 `SCIENTIFIC_USE` 为 `BLOCKED` |
| 只有 S0 / S1 的试运行 | 标记 `phase = PARTIAL_PILOT`，`SCIENTIFIC_USE = PARTIAL_PILOT（不得据此得出 M2 / M4 结论）` |

## 2. 分步运行入口（§4）

在 `workflow/byop/run/run_mainline.sh` 中新增以下入口。所有入口复用同一个 `rearch_mech.py --mainline`、同一 G-REAL、ReEDS2、mid 需求和技术参数，只在情景选择、归因开关和 case-id 上不同。

| 命令 | 情景 | `--attribution` | 输出目录 |
|---|---|---|---|
| `pilot_s01` | `S0 S1_EARLIEST` | 不带 | `…_PILOT_S01` |
| `pilot_core` | 配置中的全部五个（S0、S1_EARLIEST、S3、S2 → S2_final、S3_mS2） | 不带 | `…_PILOT_CORE` |
| `attribution`（可选，后置） | `S0 S1_EARLIEST` + xPOI / xUP / xRA / xPROC / xALL | 带 | `…_ATTRIBUTION` |
| `run`（保留） | 配置的全部情景 + 归因 | 带 | `MAINLINE_V13_GREAL_MID` |

- **各阶段目录独立**：如果目标目录已有完成的 `case_manifest.json`，`run()` 拒绝运行（返回 4），避免覆盖。
- **`DRY=1`**：只打印组装好的命令、不运行，供不调用求解器的命令组装测试使用。

## 3. 合成两轮 S2 对照（测试 `test_b0_two_iterations_select_last`）

| 项目 | 第 1 轮 `S2`（只出现在诊断表） | 第 2 轮 `S2_it2` = **`S2_final`** | 正式表中的取值 |
|---|---:|---:|---:|
| 每个母线 × 年份的交付 IT | 10 MW | 20 MW | 20 MW（48 个键） |
| 社会真实资源成本 | 1.0e9 | 2.0e9 | 2.0e9 |
| 公共新增 MW | 100 | 200 | 200（**没有**和第 1 轮相加） |
| 开发商表 | iteration 1 | iteration 2 | 48 行，全部为 iteration 2 |
| `S3_mS2` 匹配 | — | 与第 2 轮逐键一致 | `gap_status = VALID`，最大差 0 |

**`BLOCKED` 用例**（全部按预期拦截）：

- 缺少 1 个键 → `matched_service_48_keys_present`
- 出现重复键 → `matched_service_keys_unique`
- 偏差 0.6 MW → `matched_service_valid`
- 3 轮仍未收敛 → `s2_converged`
- 必需检查缺失（None）→ 也拦截

**一轮用例**：`S2_final` 与 `S2` 逐项相同，结果为 `ALLOWED`。

**仅 S0 / S1 用例**：结果为 `PARTIAL_PILOT`。

## 4. 无求解器测试（L2，2026-10-21）

| 测试 | 结果 |
|---|---|
| 静态测试 `test_mainline_v13.py` | **30 / 30 通过**（原有 21 项 + B0 新增 9 项：两轮选择、一轮不变、4 个 BLOCKED 用例、缺失不算通过、PARTIAL_PILOT、DRY 命令组装） |
| 结构测试 `structural_mainline_v13.py` | **43 / 43 通过**；`solver_executions = 0`，3 次求解调用被拦截；4 个模型整数变量均为 0 |
| 运行门控 `run_mainline.sh gate` | `approved: false`（`run_authorization = NOT_APPROVED`，`approved_git_sha = null`） |
| 本地（没有 pypsa） | 7 项通过，其余跳过 |

QA-PARAM / QA-COD / QA-FIRM / QA-SPACE / QA-LP 全部保持通过。

```text
B0_STATUS: COMPLETE
RUN_AUTHORIZATION: NOT_APPROVED
SOLVER_EXECUTIONS: 0
NEXT_STEP: RESEARCHER_APPROVAL_OF_SHA 8636c08d4b9dd11e7624f6fb52f92c91cf439ad0 REQUIRED BEFORE step0
```
