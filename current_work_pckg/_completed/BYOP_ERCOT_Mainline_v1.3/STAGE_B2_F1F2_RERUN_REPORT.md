# STAGE_B2_F1F2_RERUN_REPORT：B2-R（F1 + F2-b 修复后）Grid-Only 重运行报告

- 日期：2026-10-21（时间均为纽约时间 EDT）
- 依据：`BYOP_ERCOT_StageB_B2_F1F2_Repair_and_Rerun_Work_Package_v1.0_2026-10-21.md` §6、§7
- **状态：`B2_COMPLETED_WITH_FLAGS`**
  - S0 与 S1_EARLIEST 都求得最优解，所有硬性检查通过。
  - 但有两项需要研究者判断：S0 可靠性筛查超过阈值；2026 年 ERM 校准导致的方法性结果。
- 门控汇总：`SCIENTIFIC_USE = BLOCKED: no_load_shed`。
- **已停止**：B3 / B4 未启动。

## 1. 执行事实

| 项目 | 值 |
|---|---|
| 授权 | 研究者在对话中确认"代码修复可以通过，建议进入 B2-R……完成后无论成功或失败都应停止"。批准的修复提交为 `4fb58a450f43bab2b23e354601ea2d6b88b50ae9` |
| 运行时 HEAD | `a7b2e9ce`：与批准提交相比只改了配置里的授权项，`model/inputs/build/run` 没有改动<br>门控 `approved: true`，`reasons: []` |
| 命令 | `THREADS=20 bash byop/run/run_mainline.sh pilot_s01_fix`<br>case `MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1`（新目录）<br>`--scenarios S0 S1_EARLIEST`，没有 `--attribution` |
| 运行时间 | 2026-10-21 18:21:20 – 19:38:44 EDT（77 分钟），退出码 0 |
| 输入 | 基准 `.nc`：`19034285…cafadb`<br>B1 ERM：`7d0c02f1…807a19`<br>B1 S0CAL：`30bf497e…7454d5`<br>**9 条 S0CAL 线路、1,095.6 MW 已实际载入**（manifest `s0_calibration.n = 9`） |
| F2-b | 两个情景各有 68 台 `load_shed` 机组（含 5 台继承爬坡），罚价全部为 35,685，没有偏离的机组 |
| **S0** | **optimal**；1,552 s；4.09 M 变量；0 个整数变量 |
| **S1 字典序预求解** | **OPTIMAL**；12 个目标，1,122 s<br>实际参数：Method 2 / Crossover 0 / BarConvTol 1e-5 / FeasibilityTol 1e-3 / OptimalityTol 1e-4 / BarHomogeneous 1 / Threads 20<br>ConstrVio 2.3e-6 |
| **S1 成本阶段** | **optimal**；整个 S1 求解共 2,940 s；4.18 M 变量；0 个整数变量 |
| **结论** | B2 失败（`951ddb8b`）中的 INFEASIBLE 在统一参数后**没有再出现**，支持"参数口径不一致"的诊断，但这仍然不是 IIS 证明 |

## 2. 硬性验收（`STAGE_B2_AUDIT_CHECKLIST_F1F2.csv`、`MAINLINE_GATE_CHECKS.csv`）

| 结果 | 项目 |
|---|---|
| **全部 PASS** | S0 / S1 optimal；整数变量 0；门控；B1 哈希；9 条 S0CAL 已载入；48 个唯一键；延期 ≥ 0 且服务量 ≤ 申请量；在线 IT 单调；no-harm（S1 最大违反 0.001 MW，正好在约束允许的余量内）；数据中心能量平衡；POI 潮流 ≤ 设备；未接网不供电；字典序预求解 optimal；**Speed-First 各层在最终解上全部满足（47 行 A1 / A2，没有零锁定）** |
| **FAIL** | `no_load_shed`（S0 / S1 仍有背景切负荷）。因此 `SCIENTIFIC_USE = BLOCKED: no_load_shed`，而不是 `PARTIAL_PILOT` |
| **PENDING** | 4 条 AIDC 邻近 S0CAL 线路的潮流利用率：结果表不保存潮流，标为 `PENDING_DIAGNOSTIC_EXPORT` |

## 3. S0 背景可靠性（`STAGE_B2_S0_BACKGROUND_RELIABILITY_F1F2.csv`，与 B2 失败版本对照）

| 年份 | 原生负荷切除 MWh（B2-R / B2） | 全网最大单母线峰值 MW（B2-R / B2） | 继承爬坡 MWh（B2-R / B2） |
|---|---:|---:|---:|
| 2026 | 169 / 334 | 0.8 / 2.1 | 0.5 / 0.2 |
| 2027 | 1,923 / 4,536 | 14.9 / 79.0 | 0 / 0 |
| 2028 | 9,707 / 18,017 | 76.2 / 900.2 | 0 / 75.9 |
| 2029 | 75 / 9,845 | 1.0 / 965.7 | 0 / 0 |
| 2030–31 | 0 / 0 | 0 / 0 | 0 / 0 |
| **合计** | **11,874 / 32,733** | — | **0.49 / 76.1** |

各母线（B2-R）：

| 母线 | 原生切负荷 MWh（B2-R / B2） | 峰值 MW（B2-R / B2） |
|---|---:|---:|
| p630 13 | 6,969 / 11,771 | 73.9 / 83.8 |
| p630 14 | 1,750 / 3,821 | 22.2 / 30.6 |
| p600 1 | 1,621 / 3,625 | 19.4 / 25.1 |
| p670 8 | 732 / 744 | 5.0 / 5.1 |
| **p630 2（Red Oak）** | **417 / 9,100** | **76.2 / 965.7** |
| p620 1 | 141 / 140 | 29.4 / 29.1 |
| p630 10 | 0 / 1,491 | 0 / 273.8 |

- 切负荷合计下降 64%；Red Oak 的峰值从 966 MW 降到 76 MW；继承爬坡的切负荷几乎为 0（0.49 MWh，在 2026 年）。
- 2030 年起全部为 0。
- **按 §6.2 筛查（全期 > 1,000 MWh 或单母线峰值 > 10 MW）判为 `S0_RELIABILITY_REVIEW_REQUIRED`**。继承爬坡每年 ≤ 1 MWh，这一项通过。
- 切负荷集中在 2027–2028 年的 DFW 周边（p630 13 / 14 / 2）和 West（p600 1）。这两年线路扩建（最早 2030 年）和多数新增机组还不能投运。
- 按工作包要求，**没有继续提高 VOLL**。
- S0 的经济选择：新增 345 MW 4 小时储能、252 MW 8 小时储能、158 MW CCGT（B2 中为 0 / 0 / 708 MW）。

## 4. S1_EARLIEST：Grid-Only 交付与延期（`STAGE_B2_48_BUS_YEAR_GRID_ONLY_F1F2.csv`）

**延期合计 312.75 MW·年**；**2029 年起所有母线全额交付**。

| 母线 | 2026 | 2027 | 2028 | 首次投运年份 | 延期 MW·年 |
|---|---|---|---|---|---:|
| Helios（p600 0） | **11.3 延期** | 全额 | 全额 | 2027 | 11.3 |
| Abilene（p610 2） | **54.3 延期** | 全额 | **10.3 延期** | 2027 | 64.6 |
| Red Oak（p630 2） | **6.6 延期** | **50.8 延期** | 全额 | 2028 | 57.4 |
| Shackelford（p630 4） | 无需求 | 无需求 | **129.3 延期** | 2029 | 129.3 |
| Temple（p630 5） | **2.2 延期** | **17.2 延期** | 全额 | 2028 | 19.4 |
| Midlothian（p630 6） | **8.8 延期** | 全额 | 全额 | 2027 | 8.8 |
| Denton（p630 9） | **16.7 延期** | 全额 | 全额 | 2027 | 16.7 |
| TX1/SAT14（p650 0） | **5.2 延期** | 全额 | 全额 | 2027 | 5.2 |

（单位：MW IT。各年的申请量见 CSV。）

**各类延期的可观察证据（没有做单因素归因，因此不分摊比例）**：

| 延期 | 证据 | 可能的约束层 |
|---|---|---|
| **2026 年所有母线都为 0**（105.2 MW），包括有充足预批设备的 Helios（800 MW）、Abilene（956 MW）、Denton（226 MW） | 这些母线 2026 年的 POI 对偶值为 0、`serve_cap` 对偶值为 0，所以 POI 不是限制<br>**ERM 行只在 2026 年 binding**：S0 对偶值 1.2e7，S1 对偶值 4.3e8（是 S0 的 34 倍），2027 年以后不再 binding<br>所有电源都需要至少 1 年工期，2026 年无法新增任何 Firm 容量 | **RESOURCE_ADEQUACY**：这是**方法性结果**。ERM-02 B 把 2026 年的要求校准为现有和已承诺机组恰好能达到的 8.2%（B1），没有给新负荷留出余量，所以 2026 年任何新增 Firm 负荷都放不进去 |
| Red Oak、Temple：2027 年 | 设备都属于 `PLANNED_UNVERIFIED`，COD = max(Epoch 年份, 2028)<br>2026–2027 年 POI 设备为 0；`serve_cap` 对偶值 = −2.8e6（等于服务价值 v） | **PROCEDURE / POI_EQUIPMENT**：审计 P0-3 的分类直接带来的结果 |
| Shackelford：2028 年 | E0 = 0；POI 升级最早 2029 年（2026 年批准 + 3 年工期，且不早于 2028 年）<br>`serve_cap` 对偶值 = −2.8e6；2029 年起建成 1,476 MW 升级 | **POI_EQUIPMENT + PROCEDURE**（ML13-02） |
| Abilene：2028 年少 10.3 MW | POI 达到 955.6 MW 设备上限；POI 对偶值非零；升级最早 2029 年，2031 年前建成 544 MW | **POI_EQUIPMENT** |
| 上游输电 | 没有归因运行（`S1E_xUP` 未执行）；结果表没有导出线路潮流 | 不能判断 |

压力时段的认证 Firm 额度（`S1_GRID_OFFER.csv`）：2026 年所有母线都是 0；2027 年起与最大交付值基本一致。

## 5. S0 / S1 公共扩张（`STAGE_B2_S0_PUBLIC_EXPANSION_F1F2.csv`；不含 B1 S0CAL）

| 2031 年在运（MW） | S0（B2-R） | S1_EARLIEST（B2-R） | S1 − S0 | S0（B2 失败版本） |
|---|---:|---:|---:|---:|
| 线路扩建（AC_exp） | 35,181 | 36,195 | +1,014 | 34,758 |
| 陆上风电 | 25,747 | 28,152 | +2,405 | 25,101 |
| 光伏 | 6,215 | 7,953 | +1,738 | 6,174 |
| 4 小时 / 8 小时储能 | 345 / 252 | 530 / 1,231 | +185 / +979 | 0 / 0 |
| CCGT | 158 | 226 | +68 | 708 |

社会真实资源成本：S0 515.3 亿 USD，S1 537.7 亿 USD。不同罚价下的目标值不能直接相减来解释"资源节省"。

## 6. 科学判断

- **数值有效性**：已恢复。两个情景都是 optimal；字典序各层在最终解上全部满足；no-harm 满足。
- **M1（Grid-Only 延期）**：出现了**可信且可解释的**实质性延期，但规模有限：312.75 MW·年，只在 2026–2028 年。
  - 2027–2028 年的延期由 POI 设备和程序日期决定（Red Oak、Temple、Shackelford、Abilene），与输入设计一致。
  - **2026 年全部母线为 0，属于 ERM 校准方法造成的结果（零余量）**，不能解读为 ERCOT 的真实物理约束。Epoch 显示这些园区在 2026 年实际已投运。
- **S0 可靠性**：比 B2 大幅改善，但仍超过筛查阈值。

**是否进入 B3**：建议**先由研究者裁决**下面两项，再决定是否授权 B3。在此之前不运行任何求解器。

| # | 问题 | 选项 |
|---|---|---|
| 1 | 2026 年 ERM 零余量 | **A**：接受，把 2026 年标为方法性 RA 延期并如实报告。<br>**B**：另开一个敏感性 case，例如把 2026 年校准系数提高到不低于某个有依据的下限，或让 ERM 在第一年不约束新增 Firm 负荷（需要研究者给出依据并批准），不覆盖 B1 原文件。 |
| 2 | S0 剩余切负荷 11,874 MWh（2027–2028 年，DFW 与 West） | **A**：接受并在 B3 中把这部分列为既有可靠性背景（no-harm 冻结）。<br>**B**：按 §6.2 停在 B2，先分析 2027–2028 年的供需与工期。 |

```text
REPO: simonyed/BYOP
BRANCH: mainline-v13-stageA
FAILED_BASELINE_SHA: 951ddb8bd6bca575a78ecd3562c34e252c528f89
FIX_COMMIT_SHA: 4fb58a450f43bab2b23e354601ea2d6b88b50ae9
APPROVED_SHA: 4fb58a450f43bab2b23e354601ea2d6b88b50ae9
F1_TOLERANCE_CONSISTENCY: PASS (lex pre-solve OPTIMAL with the shared options)
F2_MAINLINE_VOLL: 35685 USD/MWh (Brattle 2024 1h planning proxy)
BASELINE_SHA_MATCH: PASS
B1_CALIBRATION_REUSED: YES
SOLVER_EXECUTIONS_BEFORE_APPROVAL: 0
B2_R_STATUS: OPTIMAL (B2_COMPLETED_WITH_FLAGS)
S0_BACKGROUND_SHED_MWh: 11874.5 (native 11874.0, inherited ramp 0.49)
S0_REDOAK_PEAK_SHED_MW: 76.2 (B2: 965.7)
S1_LEX_STATUS: OPTIMAL; 47/47 A1/A2 rows satisfied on the final solution
M1_VALIDITY: PARTIAL_PILOT (S0_RELIABILITY_REVIEW_REQUIRED; 2026 ERM zero-headroom flag)
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_REVIEW
```
