# STAGE_B2_F1F2_PRE_RUN_AUDIT：B2-R 运行前审计

- 日期：2026-10-21
- 待批准提交：`4fb58a450f43bab2b23e354601ea2d6b88b50ae9`
- 失败基线：`951ddb8b`
- **`RUN_AUTHORIZATION: NOT_APPROVED`；修复后求解次数：0**

## 1. 状态

| 项目 | 结论 |
|---|---|
| F1：数值参数一致 | **PASS**（测试项）：<br>• `lex_presolve()` 在 optimize 之前设置这 6 项，并读回实际值；<br>• `developer_joint()` 使用同一组参数；<br>• 与正式求解的 `gurobi-default` 配置逐项一致（结构测试 QA-F1，参数名不区分大小写）。<br>**这只验证了参数，不能证明 S1 一定可行。** |
| 剩余参数差异（披露） | 正式求解另外设置了 `ScaleFlag 1, Seed 123, AggFill 0, PreDual 0, GURO_PAR_BARDENSETHRESH 200`，字典序模型和开发商 LP 没有设置。按工作包，F1 只统一了规定的 6 项。这 5 项影响的是预处理和数值缩放，不影响可行性容差 |
| F2-b：主线 VOLL 35,685 | **PASS**：<br>• 主线 S0 的 6 台切负荷机组（含 5 台继承爬坡）全部为 35,685（结构测试 QA-F2）；<br>• 非主线仍为 10,000；<br>• B1 校准常量不变；<br>• 账本不重复计算 |
| 运行组织 | `pilot_s01_fix` → 新目录 `…_PILOT_S01_F1F2_V1`，只跑 `S0 S1_EARLIEST`，使用原 B1 的 ERM / S0CAL，没有 `--attribution` |
| 门控 | **拒绝**：`run_authorization=NOT_APPROVED`、`approved_git_sha` 为空、4 个文件的 SHA-256 与旧 manifest 不一致；修复提交后 manifest 将随新代码重建 |
| 纯 LP | 四个结构模型的整数变量均为 0 |

## 2. 冻结输入（与 B1 / B2 一致）

| 文件 | SHA-256 |
|---|---|
| `baseline_2025_tamu_prepared.nc`（L2-only） | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb` |
| B1 `erm02_calibration.json`（含负裕度） | `7d0c02f1245ebba31d26cb303cd154600e0a6626853d7d2c2910a1a268807a19` |
| B1 `S0_CALIBRATION.csv`（9 条线路、1,095.6 MW） | `30bf497ef009f3e120d43f7d6c2995fe0b7d82ffce9d1df2b5629131397454d5` |

## 3. 获批后的执行（工作包 §6）

1. 研究者批准 `4fb58a450f43bab2b23e354601ea2d6b88b50ae9` 之后，在配置中写入 `run_authorization: APPROVED` 和 `approved_git_sha: 4fb58a450f43bab2b23e354601ea2d6b88b50ae9`。
2. 依次执行：`gate`（必须 `approved: true`）→ `DRY=1 … pilot_s01_fix` → `THREADS=20 bash byop/run/run_mainline.sh pilot_s01_fix`。
3. 结束后，无论成功与否都**停止**，交付工作包 §7 的文件。

验收阈值（工作包 §6.2）：S0 全期切负荷 > 1,000 MWh、任一母线峰值 > 10 MW、或继承爬坡任一年 > 1 MWh 时，标记 `S0_RELIABILITY_REVIEW_REQUIRED`。

S1 如果仍然不可行，不放宽容差，而是提出 IIS 诊断方案并申请授权。
