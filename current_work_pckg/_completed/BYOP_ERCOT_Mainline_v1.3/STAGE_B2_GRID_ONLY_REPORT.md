# STAGE_B2_GRID_ONLY_REPORT：Stage B B2 Grid-Only 首轮执行报告

- 日期：2026-10-21
- 依据：`BYOP_ERCOT_StageB_B2_GridOnly_Execution_Package_v1.0_2026-10-21.md`
- **状态：`B2_BLOCKED_TECHNICAL` 与 `B2_BLOCKED_FOR_SCIENCE` 同时成立**
  - S0 已求得最优解；S1_EARLIEST 没有求出解。
  - S0 本身存在明显的既有用户切负荷。
- **停止于 B2**：没有调参，没有重跑，没有启动 B3 / B4。

## 1. 执行事实

| 项目 | 值 |
|---|---|
| 授权 | 研究者在对话中给出 B2 工作包并指示"根据……说明继续"（2026-10-21），按工作包 §0 视为 B2 `pilot_s01` 的授权记录。B3 / B4 未授权 |
| 代码 | HEAD `af00b32a7699344fd64b4129e02957dc3aeb4486`；批准 SHA `8636c08d4b9dd11e7624f6fb52f92c91cf439ad0`；两者之间 `workflow/byop/{model,inputs,build,run}` 没有改动 |
| 启动前核对（§4） | 门控：`approved: true`，`reasons: []`<br>`DRY=1` 命令：只含 `--scenarios S0 S1_EARLIEST`，有 `--erm-cal`、`--s0-cal-file`，没有 `--attribution`<br>运行目录原先不存在 |
| 输入哈希 | 基准 `.nc`：`19034285…cafadb`<br>B1 ERM JSON：`7d0c02f1…807a19`<br>B1 S0CAL CSV：`30bf497e…7454d5`<br>三者与 §2.1 一致 |
| 运行命令 | `THREADS=20 bash byop/run/run_mainline.sh pilot_s01`<br>单进程 20 线程：S0 → S1 是串行链，按 L2 运行规范安排 |
| 运行时间 | 2026-10-21 21:14:43Z – 21:43:42Z，进程退出码 **1** |
| 求解器 | Gurobi 11.0.3（gurobipy），pypsa 1.3.0，linopy 0.9.1 |
| **S0** | **optimal**，barrier 165 次迭代，1,410 秒（含建模共 1,523 秒）<br>4.09 M 变量、7.16 M 约束，**0 个整数变量**<br>目标值 5.0932e10 |
| **S1_EARLIEST** | **没有求出解**：`RuntimeError: P0-2 lexicographic pre-solve not optimal (Gurobi status 3)`，即导出的字典序模型被判定为 **INFEASIBLE**<br>7.31 M 行、4.18 M 列，0 个整数变量 |

## 2. S1_EARLIEST 失败的诊断（只依据日志，没有调用求解器）

| 证据 | S0 正式求解 | S1 字典序预求解（`lex_presolve`，用 `m.to_gurobipy()` 导出） |
|---|---|---|
| 求解参数 | Method 2（barrier），Crossover 0，BarConvTol 1e-5，**FeasibilityTol 1e-3**，OptimalityTol 1e-4，BarHomogeneous 1 | **只设置了 Threads = 20**，其余为 Gurobi 默认值：**FeasibilityTol 1e-6**，concurrent LP（单纯形与 barrier 并行） |
| 结果 | optimal；最终原始残差 2.4e-6 | 单纯形 149,019 次迭代后判定 "Infeasible model" |

**推断原因（数值口径不一致，而不是模型本身无解）**：

1. S1 的 no-harm 约束要求：每台既有用户切负荷机组在每个时段的切负荷 ≤ **冻结的 S0 切负荷 + 0.001 MW**。
2. 冻结的 S0 切负荷来自一个**容差 1e-3、没有 crossover 的 barrier 近似解**。no-harm 的余量 0.001 MW 恰好等于 S0 的可行性容差。
3. 字典序预求解改用默认的 1e-6 精确容差求解，于是 S0 近似解中 1e-6 到 1e-3 量级的残差，在 S1 中无法被 0.001 MW 余量吸收，模型被判定为不可行。
4. S1 的物理可行集是 S0 的超集：研究 AIDC 的服务量可以为 0，研究需求没有任何强制交付量。因此在一致容差下应当可行。

**局限**：没有做 IIS 不可行约束集分析，因为那需要调用求解器，本阶段未授权。所以以上是**有充分证据的推断，尚未经求解器证实**。

另外，`developer_joint()`（S2）的求解参数同样没有设置 FeasibilityTol，B3 会遇到同样的风险。

## 3. B1 → B2 对账（`STAGE_B2_B1_BASELINE_RECONCILIATION.csv`）

| 项目 | B1 校准运行（切负荷 1e8 USD/MWh，增容 1e7 USD/MW·年） | B2 正式 S0（切负荷 1e4 USD/MWh，S0CAL 作为固定资产） |
|---|---:|---:|
| 背景切负荷合计 | 5.4e-10 MWh | **32,808.6 MWh** |
| 其中原生负荷 | 5.2e-10 | 32,732.6 |
| 其中继承爬坡 | 2.0e-11 | **76.1** |
| 公共资本（PV） | 71.7 亿 USD | 61.4 亿 USD |
| 运行成本（PV） | 446.9 亿 USD | 444.7 亿 USD |
| 社会真实资源成本 | 518.6 亿 USD | 509.3 亿 USD |

ERM 年度系数：按 §2.2 原样使用，包括 2029–2031 年的负值，没有改动。

S0CAL：9 条线路、1,095.6 MW，其中 AIDC 邻近的 4 条共 665.9 MW；通过 `--s0-cal-file` 作为固定、零成本的 Link 载入。
- 实际载入条数要到算例结束时才写进 `case_manifest.json`，本次没有走到那一步，所以标为 `PENDING`。
- 这些 Link 的载体是 `AC_s0cal`、不可扩建，不会进入公共投资账本，没有被重复计为经济投资。

**更正 B1 报告**：B1 报告说"S1–S3 中既有用户的切负荷上限都是 0.001 MW"。这句话只适用于 B1 的校准运行。正式的 no-harm 基准来自本次经济 S0，其切负荷并不为 0（见 §4）。

## 4. 正式 S0 的背景供电可靠性（`STAGE_B2_S0_BACKGROUND_RELIABILITY.csv`）

切负荷集中在 **2026–2029 年**。2030 年起为 0：那时线路扩建（工期 4 年）和新增机组已经可以投运。

| 母线 | 2026 | 2027 | 2028 | 2029 | 峰值 MW |
|---|---:|---:|---:|---:|---:|
| **p630 2（Red Oak，AIDC 母线），原生负荷** | 6 | 252 | **4,838** | **4,004** | **965.7** |
| **p630 2，继承爬坡（Google Red Oak 存量）** | 0.2 | 0 | **75.9** | 0 | 25.3 |
| p630 13 | 84 | 2,134 | 6,955 | 2,598 | 83.8 |
| p630 14 | 39 | 744 | 2,377 | 662 | 30.6 |
| p600 1 | 136 | 467 | 1,947 | 1,075 | 25.1 |
| p620 6 | 0 | 158 | 1,784 | 6 | 9.3 |
| p630 10 | 0 | 0 | 0 | 1,491 | 273.8 |
| 其余 4 个母线 | — | — | — | — | ≤ 29 |

（单位：MWh/年；全网 6 年合计 32,808.6 MWh，其中 10,844 MWh 发生在 3 个压力日。）

**含义**：
- 按经济目标，2028–2029 年在 DFW 一带（含 Red Oak AIDC 母线）切掉既有负荷，比投资避免它更便宜：切负荷罚价 1e4 USD/MWh，而线路在 2030 年前无法投运。
- B1 的高罚价校准运行则在 2027–2028 年新建了 6.5 GW 的 8 小时储能来避免切负荷，所以那里切负荷为 0。
- 这一结果按工作包 §6.2 判为 **`B2_BLOCKED_FOR_SCIENCE`**：
  - Red Oak 母线在 S0 中最多有 966 MW 背景负荷未供电。
  - 冻结之后，这会成为该母线的 no-harm 允许量，同时与研究 AIDC 的接网判断混在一起。

## 5. 正式 S0 的公共扩张（`STAGE_B2_S0_PUBLIC_EXPANSION.csv`，不含 B1 S0CAL）

| 2031 年在运（MW） | B2 正式 S0 | B1 校准 S0 |
|---|---:|---:|
| 线路扩建（AC_exp，有成本） | 34,758 | 35,724 |
| 陆上风电 | 25,101 | 25,714 |
| 光伏 | 6,174 | 5,762 |
| CCGT | 708 | 0 |
| 8 小时 / 4 小时储能 | 0 / 0 | 1,514 / 56 |

逐年新增（MW）：

| 技术 | 2028 | 2029 | 2030 | 2031 |
|---|---:|---:|---:|---:|
| 线路扩建 | — | — | 30,387 | 4,370 |
| 陆上风电 | — | 6,694 | 12,165 | 6,242 |
| 光伏 | 2,572 | 1,372 | 0 | 2,230 |
| CCGT | — | — | — | 708 |

- 线路扩建最早在 2030 年出现（2026 年批准 + 4 年工期），这与 2026–2029 年的切负荷相互印证。
- 2031 年在运容量前 10 名走廊：LTL83（p630 4）2,959 MW、LTL133（p650 5）2,744 MW、LTL85（p630 5）1,500 MW 等，全部列于该表。
- 正式 S0 的扩张规模与 B1 校准运行同一数量级，**没有出现异常的扩张**。

## 6. 48 个母线—年份表与瓶颈证据

- `STAGE_B2_48_BUS_YEAR_GRID_ONLY.csv` 保留全部 **48 个唯一键**：
  - 申请量来自研究队列（mid，累计 IT MW）；
  - 服务量和延期标为 `NOT_AVAILABLE (S1_EARLIEST not solved)`。
  - **没有用猜测值填补空白**。
- `STAGE_B2_POI_NETWORK_DIAGNOSTICS.csv` 只列出输入层面的事实：
  - 预批与计划未核实的设备容量、程序日期、AIDC 邻近的 S0CAL 线路；
  - POI 对偶值、走廊拥堵、ERM binding：S1 没有求解，全部为 `NOT_RECORDED`；
  - 线路潮流利用率：结果表没有保存潮流，标为 `PENDING_DIAGNOSTIC_EXPORT`。
- **M1 的结论**：本轮**无法判断** Grid-Only 是否延期。没有做任何归因。

## 7. 审计清单（`STAGE_B2_AUDIT_CHECKLIST.csv`）

| 结果 | 项目 |
|---|---|
| **PASS** | S0 optimal；整数变量为 0；门控批准；B1 文件哈希一致；48 个唯一键 |
| **FAIL** | S1_EARLIEST optimal；字典序预求解；正式 S0 背景切负荷约为 0；SCIENTIFIC_USE = PARTIAL_PILOT（汇总程序没有执行到） |
| **PENDING** | S0CAL 实际载入条数；no-harm 违反量；能量平衡；单调性；POI ≤ 设备；AIDC 邻近线路利用率 |
| **NOT_APPLICABLE** | 延期非负检查（S1 无解）；单因素归因（B4 未授权） |

## 8. 最小修复建议与决定请求（最多两项；均未实施）

| # | 修复 | 性质 | 改动范围 | 影响 |
|---|---|---|---|---|
| **F1（必需）** | 让 `lex_presolve()` 和 `developer_joint()` 使用与正式求解相同的 Gurobi 参数：Method 2、Crossover 0、BarConvTol 1e-5、FeasibilityTol 1e-3、OptimalityTol 1e-4、BarHomogeneous 1 | **修复程序错误**：数值口径一致性，不改变模型 | `rearch_mech.py`：在 `gm.setParam` 和 `opts` 处约 6 行；另加不调用求解器的测试，核对参数一致 | 不修复的话，S1 / S2 很可能都无法求解 |
| **F2（科学，二选一）** | **F2-a**：保持切负荷罚价 1e4，接受经济 S0 的切负荷作为 no-harm 基准，如实披露 Red Oak 2028–2029 年的背景缺电<br>**F2-b**：把正式情景中既有用户切负荷的罚价改为代码中已用于报告的 ERCOT VOLL 35,685 USD/MWh（Brattle 2024，D2.5），让 S0 自己选择储能或其他方式避免切负荷 | F2-b 是**研究假设的改变**，需要研究者批准 | F2-b：一个常量（`M.SHED_COST` 或 mainline 专用参数） | F2-a：Red Oak 的 M1 结果会混入"背景已缺电"的问题<br>F2-b：S0 会多投资；B1 的 S0CAL 不需要重跑（校准本来就用 1e8） |

**推荐**：F1 + F2-b。

- 修复后，需要研究者批准新的代码 SHA，再重跑 `pilot_s01`（单进程约 20 线程，预计 S0 约 25 分钟加 S1 字典序求解）。
- 在此之前，**不运行任何求解器**。

```text
B2_STATUS: B2_BLOCKED_TECHNICAL + B2_BLOCKED_FOR_SCIENCE
SOLVER_EXECUTIONS (B2): 2 (S0 optimal; S1_EARLIEST lexicographic pre-solve INFEASIBLE)
SCIENTIFIC_USE: BLOCKED
NEXT_STEP: RESEARCHER_DECISION on F1 (required) and F2-a / F2-b, then approval of the fix SHA before re-running pilot_s01
```
