# EXECUTION_REPORT_FOR_PUBLISHER — BYOP ERCOT 仿真架构重构 v1.0（含 P0 修正）

- 报告日期：2026-10-21（UTC 08:30）
- 依据：
  - `BYOP_ERCOT_Rearchitecture_Work_Package_v1.0_2026-10-20.md` 第 9 节
  - `BYOP_ERCOT_RUN_DECISION_AND_CORRECTION_PLAN_2026-10-20.md`
  - `BYOP_ERCOT_P0_RESEARCHER_DECISIONS_2026-10-20.md` 第 5 节
- 正式结果：`workflow/results/BYOP/rearch_p0/`，汇总表在 `_collected/`。
- 诊断结果：`workflow/results/BYOP/rearch/`，均标记为 `BASELINE_DIAGNOSTIC`。
- 本报告的结果来自**静态多期 LP（2026–2031 年，每年抽样 2 周，3 小时分辨率）**。没有运行 2036–2050 年的长期模拟。

## 1. 总体状态：**PARTIAL**

| 部分 | 状态 | 说明 |
|---|---|---|
| WP-A 输电骨干 | **完成** | TAMU 64 节点电气骨干网；修复了 PyPSA-USA 删除区内线路和跨区容量重复计算两个缺陷；2025 基准；网络映射审计 |
| WP-B POI 与纯电网 COD | **完成（以设备和审批假设为主导）** | 四层可交付能力；联合可交付；严格最早可交付基准 `S1_EARLIEST`；延迟归因 |
| WP-C 企业 BYOP | **大部分完成** | 四种供电模式枚举；基于联合报价的速度优先决策；公共阶段一致性；气源三级证据；单元测试。**合同路径（C）未实现**；“关闭瓶颈后不再采用 BYOP”的对照实验未做 |
| WP-D 2026–2050 跨年控制器 | **未开始** | `v240_path` 年度控制器尚未接入新架构 |
| P0-1 / P0-2 / D1–D3 | **完成并验收** | Step 1–6 全部完成；Step 5 小算例验收通过；Step 6 正式重算 3 个算例共 42 个求解，全部最优 |

## 2. 代码与环境

- **仓库**：<https://github.com/simonyed/BYOP>（分支 `byop` → 远端 `main`），上游基线为 `20b71907`。
- **正式算例实际使用的代码**（manifest 在进程启动时计算哈希）：
  - `R2_GK`、`R2_GU`：提交 `9c3a5626`
  - `R2_GW`：提交 `ac0f1f2e`。与 `9c3a5626` 的区别只在竞争负荷的计价；G-W 没有竞争负荷，所以对结果没有影响。
  - `S5_GK`：`40af7bc5`
- **新增文件**：
  - 模型 `workflow/byop/model/rearch_mech.py`
  - 构建器 `workflow/byop/build/build_2025_baseline_tamu.py`
  - 汇总 `workflow/byop/post/collect_rearch.py`
  - 运行脚本 `workflow/byop/run/run_rearch.sh`
  - 单元测试 `workflow/byop/tests/test_rearch_units.py`、`test_p0_units.py`
  - 配置 `workflow/config/config.byop_ercot_tamu.yaml`
  - 输入 `workflow/byop/inputs/poi/*`、`inputs/grid/TPIT_FARWEST_EVIDENCE_LEDGER.csv`、`COMMITTED_BASE_ASSETS.csv`
  - 文档 `README_REARCHITECTURE.md`、`workflow/byop/docs/*`、`current_work_pckg/*`
- **修改文件**（对旧模型兼容）：
  - `workflow/scripts/prepare_network.py`：WIND-01 增加按 reeds_zone 回退
  - `workflow/byop/model/v240_mech.py`：账本中排除 `dc_curtail`/`dc_interrupt`；空 Link 表保护
  - `.gitignore`
- **未修改**：7 区模型、县级模型、v250 的配置与代码路径。
- **环境**：L2 lambda-2（i9-10920X，12 个物理核心，251 GB 内存）；pypsa 1.3.0、linopy 0.9.1、gurobipy 11.0.3；barrier、Crossover=0；正式算例 3 路并行、每路 8 线程。
- **运行命令**：`bash byop/run/run_rearch.sh r2`（R2_GK/GU 因 RA-D2f 修订由 `/tmp/launch_r2b.sh` 重启，参数相同）。
- **求解时间**：R2 每个情景 12–56 分钟；R2_GW 约 5.2 小时（00:15–05:28），R2_GK 约 5.9 小时、R2_GU 约 7.2 小时（00:31 启动，06:27 / 07:44 结束）。

## 3. 既有成果的保留与变化

- 7 区和县级配置与代码路径没有改动，旧结果全部保留。
- 第一轮新架构算例（`DEV_GU`、`R1_GW`、`R1_GK`）保留在 `results/BYOP/rearch/`，标记为 `BASELINE_DIAGNOSTIC`。
- 与第一轮诊断结果相比，P0 修正后的变化：
  - ABI 在 G-K 中不再出现 S1 服务降为 0 的情况；
  - 企业电网报价改用物理最早可交付量；
  - S0 的背景负荷切负荷由 0.76–1.82 TWh 降到 0.04–0.51 TWh；
  - ABI 的 BYOP 由 426–455 MW 降到 188–392 MW。
- 差异来源属于**物理机制和数值定义的修正**，不是数据变化。

## 4. 数据准备情况

| 数据 | 位置 | 来源与日期 | 覆盖 | 缺失与替代 |
|---|---|---|---|---|
| TAMU 合成网络 | `resources/BYOP_ERCOT_TAMU/`（L2；`.nc` 不进 git） | PyPSA-USA / BE-TAMU | ERCOT 1,250 个变电站 → 64 簇 | 合成网络，不对应真实变电站 |
| 2025 机组与负荷 | `results/BYOP/baseline_2025_tamu/`（审计表在 git） | ReEDS eb75a6bc；ERCOT Native Load 2025 | 488.2 TWh，与 ERCOT 一致 | 2025 可送达性校准 4,994 MVA（B 级证据） |
| POI 场址 | `inputs/poi/POI_REGISTER.csv` | 公司公告、ERCOT Batch Zero、Oncor 2026Q2（SRC-03..10） | 3 个代表性场址 | 设备容量和工期为研究假设区间（低/基准/高），不是认证值 |
| TPIT 证据台账 | `inputs/grid/TPIT_FARWEST_EVIDENCE_LEDGER.csv`（sha256 见清单） | ERCOT TPIT 2026-07-13；ERCOT 董事会 2026-02 第 13 项 | 330 条记录 | 主情景只纳入 DWB Stage 2（+1,000 MW，ERCOT 估计） |
| S0 最小增容校准 | `rearch_s0repair/S0CAL_minuplift_2026_2031/S0_CALIBRATION.csv`（sha256 74044bb3…） | 本研究 | 7 条线，571 MW | 第一次尝试为了经济性买了 11 GW，已作废存档 |
| 证据登记表 | `inputs/poi/SOURCE_EVIDENCE_REGISTER.csv` | SRC-01..20 | — | — |

## 5. 科学机制逐项验收

| 机制 | 状态 | 证据 |
|---|---|---|
| M1 速度—技术选择 | **已实现，单元测试通过；ERCOT 算例中定性成立** | 三个场址在 S2 中都选择了 GF；SOFC（0.5 年工期）在 2027 年先投运，RICE（2 年）随后跟进；ABI 的 BYOP 规模随电网设置变化（188/392/377 MW）。见 `_collected/S2_MODES_R2_*.csv` |
| M2 私人 BYOP 与公共扩张的关系 | **已实现，短期信号已出现，未做现实校准** | G-U 中 S2 比 S1 少建输电增容 5,334 MW；三种设置下陆上风电少 1.7–3.5 GW，8 小时储能多 1.1–2.5 GW。见第 7 节 |
| M3 长期锁定、冗余与复用 | **未实现**（只看到早期信号） | DFW 复用的机组发电量为 0、只承担可靠容量；PEC 的 RICE 在 2031 年接网后利用率降到约 0。没有 2050 年路径 |
| M4 私人与社会成本偏离 | **已实现，单元测试通过；ERCOT 算例中存在显著偏离** | 服务量相同时，S2 比 S3 多 1.5 / 2.7 / 2.8 十亿美元（G-W/G-K/G-U） |

## 6. Gate 结果

| Gate | 检查 | 标准 | 实测 | 结果 |
|---|---|---|---|---|
| G0 | 代码与输入审计 | 记录 SHA，旧文件不被覆盖 | 已完成；发现并修复 manifest 记录代码版本的缺陷 | **PASS** |
| G1 | 新骨干网与 S0 | 无孤岛；守恒；S0 可求解且无无法解释的切负荷 | 63 母线单一连通分量；负荷守恒；S0 最优。G-W 剩余 39 GWh 为经济性切负荷（已解释）；G-K/G-U 的 S0 另有 0.51/0.45 TWh 背景切负荷加 0.36/0.44 TWh 竞争负荷削减，属于程式化竞争负荷造成的压力 | **PASS（有保留）** |
| G2 | S1 接入 | 联合可交付；最早 COD 可追溯；单调性 | S1_EARLIEST 三种设置一致（G-U ≥ G-K）；max-min 没有零锁死；投运容量不下降；归因可追溯 | **PASS** |
| G3 | S2 机制 | 强/弱瓶颈对照；内生 BYOP；工期敏感；WLPUN 与气源闸门检验 | 内生 BYOP 出现；WLPUN、孤岛、PCLR、MDQ 单元测试通过；S2 一致性通过。**工期敏感性和关闭瓶颈对照未在 ERCOT 算例中运行** | **PARTIAL** |
| G4 | 长期 S0–S3 | 年度状态账本、2050 资产 | 未运行 | **NOT RUN** |

**P0 验收（Step 5 和 R2）**：

| 检查 | R2_GW | R2_GK | R2_GU |
|---|---|---|---|
| 纯 LP、全部最优 | PASS | PASS | PASS |
| 投运容量不下降 | PASS | PASS | PASS |
| 中断不超过上限 | PASS | PASS | PASS |
| 不损害既有用户（最大越限 0.001 MW） | PASS | PASS | PASS |
| S1_zero = S0 | PASS | PASS | PASS |
| S2_off = S1_ECON | PASS | PASS | PASS |
| S2 一致性 | PASS | PASS | PASS |
| max-min 求解最优 | PASS | PASS | PASS |
| POI 进口 ≤ 设备容量 | PASS | PASS | PASS |
| 设施能量平衡 | PASS | PASS | PASS |
| `no_load_shed` | FAIL（已解释，见 G1） | FAIL（同） | FAIL（同） |

- **中断价格**（`_collected/INTERRUPTION_PRICE_TABLE.csv`）：2026–2031 年为 565 / 576 / 587 / 599 / 610 / 620 USD/MWh，与研究者核算表一致。
- **非计划中断与 PCLR 分账**：`_collected/INTERRUPTION_vs_PCLR_ACCOUNTS.csv`。
- **max-min 验收**：`_collected/MAXMIN_LEXIMIN_ACCEPTANCE.csv`。

## 7. 核心结果摘要（正式结果，2026–2031 年）

### 7.1 服务量与最早全额供电年份

| 场址 | S1_EARLIEST（三种设置相同） | S1_ECON | S2 | S3 |
|---|---|---|---|---|
| ABI_TAY | 250 / 500 / 868 / 1,000 MW，2030 年起全额 | G-W 与之相同；G-K/G-U 在 2027–28 年只有 172/147 MW（经济性少供） | 2027 年起全额 | 2027 年起全额 |
| DFW_KAU | 0 / 173 / 174 / 1,000，2030 年起全额 | 相同 | 2027 年起全额 | 2028 年起全额 |
| PEC_REE | 2031 年前为 0，2031 年起全额 | 相同 | 2027 年起全额 | 2027 年部分（109–213 MW），2028 年起全额 |

- **延迟归因**（以 S1_EARLIEST 为基准）：三种设置下全部来自 POI 设备，分别为 ABI 132、DFW 1,403、PEC 2,750 MW_IT·年；其中 DFW 有 173 与审批程序重叠。上游输电和系统充裕度的贡献为 0。
- 也就是说，S0 修复之后，在 1 GW 级请求规模下，**网络与系统充裕度不再推迟这三个场址的最早纯电网供电**。

### 7.2 BYOP（S2 选择的模式均为 GF）

| 场址 | G-W | G-K | G-U |
|---|---|---|---|
| DFW_KAU | SOFC 318 + RICE 305 + 复用机组 523 MW | 同左 | 同左 |
| ABI_TAY | RICE 188 MW | RICE 392 MW | RICE 377 MW |
| PEC_REE | SOFC 318 + RICE 1,079 MW | 同左 | 同左 |

### 7.3 成本与公共投资（社会口径现值，十亿美元，2026 年基准）

| 比较 | G-W | G-K | G-U |
|---|---:|---:|---:|
| S1_ECON − S0 真实资源成本 | +1.86 | +3.36 | +3.07 |
| S2 − S1_ECON | +3.80 | +3.69 | +4.01 |
| 其中 BYOP 资本支出 | +2.91 | +3.02 | +3.01 |
| **S2 − S3_mS2（服务量相同）** | **+1.49** | **+2.75** | **+2.79** |
| S1_ECON − S3_mS1（服务量相同） | +1.07 | +2.48 | +2.27 |
| S1_EARLIEST − S1_ECON（多服务 91 / 405 / 456 MW_IT·年） | +1.12 | +2.55 | +2.81 |

到 2031 年的公共新增装机存量（MW），按 S0 → S1_ECON → S2 → S3 排列：

| 设置 | 陆上风电 | 8 小时储能 | 输电增容 |
|---|---|---|---|
| G-W | 3,908 → 6,069 → 4,406 → 4,056 | 0 → 1,246 → 2,331 → 0 | — |
| G-K | 19,284 → 24,369 → 20,823 → 19,293 | 0 → 1,614 → 4,027 → 3 | — |
| G-U | 20,012 → 24,796 → 21,768 → 20,112 | 0 → 1,404 → 3,942 → 1 | 28,511 → 32,138 → 26,805 → 26,548 |

- **私人与社会偏离的来源**：
  - 开发商少建自备电源（RICE 1.57–1.78 GW），多依赖电网进口；协调规划者则建 RICE 2.5–2.8 GW。
  - 开发商只按节点电价（LMP）支付电量，不承担系统容量和可靠性成本（`--tariff energy`）。
  - 结果是公共系统被迫多建 2.3–4.0 GW 的 8 小时储能。
  - 这是“仅电量电价”下的外部性。在 `energy_erm` 电价下是否缩小，**尚未测试**。
- **背景负荷切负荷**：S2 低于 S0（例如 G-K 为 0.46 TWh，S0 为 0.51 TWh）。不得损害约束从未被突破。

## 8. 发现的缺陷与局限

| 类别 | 内容 |
|---|---|
| 研究假设局限 | ① 纯电网延迟几乎完全取决于 POI 设备和审批工期的假设（低/基准/高区间有出处，但不是 TSP 认证值），网络约束在当前请求规模下不起作用。② TAMU 是合成网络。③ 远西部负荷按 AEO 统一增长率，只有约 9.6 GW，而 ERCOT 预测 2028 年约 16 GW，因此真实的远西部压力被低估（RA-D3c）。④ 气源只有 L1 代理，没有 L0 核实的日用气量。⑤ ERM 是可靠性代理，不是 N-1 或动态稳定分析。⑥ 每年只抽样 2 周，3 小时分辨率。⑦ 中断上限 0.5%、PCLR 200 小时/年、服务价值 v 都是研究假设。 |
| 已修复的缺陷 | PyPSA-USA 删除 TAMU 区内线路；跨区容量重复计算；`.loc` 设置快照权重破坏多重索引（只出现在测试中）；manifest 在运行结束时计算代码哈希；POI 检查和能量平衡检查本身的缺陷；分层目标中残留的成本目标（单元测试发现）；不得损害约束与 ERM 修正冲突；两次被否决的校准或计价方案（11 GW 经济性增容；600 USD/MWh 竞争负荷），均已存档。 |
| 未解决 | C 合同路径未实现；`energy_erm` 电价对照未运行；BYOP 工期敏感性、关闭瓶颈对照（C6）、长期 M3 均未运行；G-K/G-U 的 S0 仍有竞争负荷造成的切负荷。 |

## 9. 下一阶段待办

| 优先级 | 对象 | 操作 | 验收标准 |
|---|---|---|---|
| P0 | 研究者决定 | ① 是否接受 POI 设备和审批工期的基准假设作为主情景；② RA-D2f 修订版和 RA-S0r 的处理；③ 远西部是否引入 ERCOT 负荷预测 | 写入决策日志 |
| P0 | 电价口径 | 用 `--tariff energy_erm` 重跑 R2 的 S2 和 S3_mS2（3 个设置） | 报告 M4 偏离对电价口径的敏感性 |
| P1 | C6 对照 | 在 `--case low`（设备和审批更快）以及放松 POI 约束（xPOI）下运行 S2 | 瓶颈消失后 BYOP 应显著减少 |
| P1 | BYOP 工期敏感性 | `--byop-case high` / `--gas-case high` | 速度优先解或第二阶段成本发生变化 |
| P1 | 更大请求或更多场址 | 引入 ERCOT 的大负荷队列规模，使网络约束起作用 | 归因中出现上游输电或系统充裕度的贡献 |
| P2 | WP-D | 把 TAMU + POI + S2 接入 `v240_path` 年度控制器（2036–2050 年及 2040/45/50 年节点） | 年度状态账本、资产到 2050 年的利用率与残值 |
| P2 | 合同路径 C | 交付路径 + 容量权利，防止重复出售 | 单元测试和 R2 对照 |

## 10. 交付清单

完整清单见 `current_work_pckg/RETURN_FILE_MANIFEST.md`（第 10 节为本轮 R2 文件），列出路径、用途、生成状态、GitHub 状态、算例 / run、大小和 SHA-256。主要文件：

- **报告**：`current_work_pckg/EXECUTION_REPORT_FOR_PUBLISHER.md`、`POST_RUN_DIAGNOSTIC_REPORT_FOR_PUBLISHER.md`、`P0_MODEL_CORRECTION_PROPOSAL.md`、`DECISION_LOG_REARCHITECTURE.md`、`INTERIM_PROGRESS_REPORT_2026-10-20.md`、`GITHUB_SYNC_EXECUTION_REPORT.md`
- **正式结果**：`workflow/results/BYOP/rearch_p0/R2_GW|R2_GK|R2_GU/`（`case_manifest.json`、`scenario_summary.csv`、`poi_ledger.csv`、`ledger.csv`、`S2_developer_modes.csv`、`S2_consistency.csv`、`lex_*.json`、`scenarios/*/`）
- **汇总**：`workflow/results/BYOP/rearch_p0/_collected/`（`POI_DELIVERABILITY_LEDGER`、`DELAY_ATTRIBUTION`、`ASSET_COMMITMENT_LEDGER`、`SCENARIO_COMPARISON`、`SCENARIO_DIFFERENCES`、`GATE_CHECKS`、`MAXMIN_LEXIMIN_ACCEPTANCE`、`INTERRUPTION_PRICE_TABLE`、`INTERRUPTION_vs_PCLR_ACCOUNTS`、图）
- **S0 修复**：`workflow/results/BYOP/rearch_s0repair/`
- **TPIT 台账与映射**：`workflow/byop/inputs/grid/TPIT_FARWEST_EVIDENCE_LEDGER.csv`、`COMMITTED_BASE_ASSETS.csv`
- **单元测试**：`workflow/byop/tests/`（14 项全部通过）
- 没有制作 `RETURN_PACKAGE.zip`：全部小文件已在 GitHub；`.nc` 网络文件和大日志保留在 L2，路径与哈希见清单第 8 节。

---

## 总结：当前 ERCOT 仿真能否可信地回答以下三个问题？

- **电网为什么延迟？——Partial。**
  延迟已经可以追溯，并且可以逐项归因：在严格最早可交付基准下，三种电网设置的纯电网延迟 100% 来自 POI 设备，DFW 另有审批程序重叠（`_collected/DELAY_ATTRIBUTION.csv`）。但这些延迟由有出处的工期假设决定；修复 S0 之后，网络和系统充裕度在 1 GW 级请求下没有起约束作用。因此“延迟来自哪一层”的结论依赖假设，网络瓶颈机制尚未被检验出来。
- **BYOP 为什么发生？——Partial。**
  三个场址在 S2 中都按速度优先内生选择了 GF：BYOP 投运早于电网可交付年份，2027 年起全额供电，SOFC 先投、RICE 跟进；ABI 的 BYOP 规模随电网设置变化（188 / 392 / 377 MW，`_collected/S2_MODES_R2_*.csv`）。但“瓶颈消失后不再采用 BYOP”的对照，以及工期敏感性，还没有在 ERCOT 算例中验证。
- **公共电网如何长期改变？——No。**
  只得到 2026–2031 年的短期信号：BYOP 减少了 1.7–3.5 GW 陆上风电和 G-U 中 5.3 GW 的输电增容，但仅电量电价下公共系统多建了 1.1–2.5 GW 储能，服务量相同时的社会成本偏离为 1.5–2.8 十亿美元。2036–2050 年的资产锁定和复用（M3）没有运行，无法回答长期问题。
