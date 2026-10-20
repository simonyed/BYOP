
# BYOP ERCOT — P0 模型修正研究者确认意见

**日期：** 2026-10-20  
**状态：** APPROVED FOR IMPLEMENTATION  
**适用工作包：** `current_work_pckg/`  
**关联文件：** `P0_MODEL_CORRECTION_PROPOSAL.md`

## 0. 总体决定

批准 P0-1、P0-2 的总体修正方向，并确认以下三项决策：

| 决策 | 确认方案 |
|---|---|
| D1：同一年度多场址容量分配 | 先保护既有权利和接入资格，再采用 Max–Min；必要时使用迭代 Leximin |
| D2：中断成本及既有用户保护 | 根据年度服务价值和实际设施用电量动态计算中断价格；实施逐母线、逐时段的既有用户保护 |
| D3：I-4 远西部 S0 缺供 | 先补齐有可靠投运依据的 TPIT 输电项目，再针对剩余失配开展有证据支持的校准 |

全部修改保持连续线性规划（LP-only），不得引入整数变量。

本文件属于研究者确认的实施原则，不代表代码已完成修改或验收。

---

## 1. D1：同一年度多场址容量分配

### 1.1 确认原则

采用：

**Speed-First → 有资格约束的 Max–Min → 成本最小化**

不采用简单的“请求年份 + 场址编号”作为全部容量的排队规则。

执行顺序：

1. 优先保护现有用户、已投运容量以及具有明确依据的既有接入权利。
2. 核实各场址当年的审批状态、POI 设备容量、建设周期及物理接入资格。
3. 在同一资格层级、竞争同一共享可交付容量的场址之间实行 Max–Min 分配。
4. 固定最早服务结果及分配结果后，再最小化公共系统真实资源成本。

ERCOT 2026 年批准的 Batch Zero 采用符合资格的大负荷联合研究和容量分配机制，但 Max–Min 是本项目选择的透明数学实现，不应将其描述为 ERCOT 已正式规定的算法。

### 1.2 修正现有 A2 约束

现有提案：

`IT_online[s,y] >= z * D[s,y]`

不能无条件用于全部场址。

应先计算：

`R[s,y] = min(D[s,y], C_independent[s,y])`

其中：

- `D[s,y]`：场址累计申请 IT 容量。
- `C_independent[s,y]`：在审批、设备、建设 COD 和单场址物理条件下，当年独立可交付的 IT 容量。
- `R[s,y]`：当年能够参与共享容量分配的合格需求。

仅对 `R[s,y] > 0` 的合格场址施加：

`IT_online[s,y] >= z * R[s,y]`

对于因独立物理瓶颈而不可获得正容量的场址，必要时使用迭代 Leximin，避免最低比例被零锁死。

例如，PEC 在当前接入设备设定下，2031 年以前没有可用 POI 设备，因此不应在此前年度限制 ABI 和 DFW 之间的公平性分配。

### 1.3 验收标准

- 按年份优先最大化各场址总投运 IT 容量。
- 年度总投运量不低于相同可行域下的 S1_ECON。
- 不要求每个场址逐项不低于 S1_ECON，因为公平分配允许改变个体份额。
- 联合分配不得超过网络、POI 和公共可靠容量约束。
- 不得重复预留公共供电容量。
- 对联合 Firm 报价实施 Joint FCF 验证。
- 无接入资格的场址不得影响其他场址的最低满足比例。
- 已投运容量在无取消需求时跨年不下降。

---

## 2. D2：运行中断价格与既有用户保护

### 2.1 非计划中断价格

当前模型设置年度 IT 服务价值：

`v = 2,800,000 USD/(MW_IT·year)`

该值是研究假设，不是 ERCOT 官方公布的数据中心停电损失价格。

非计划中断价格应与这一年度价值保持一致：

`c_interrupt[s,y] = v / E_unit[s,y]`

其中：

`E_unit[s,y] = sum_t(weight[t] * facility_load_per_MW_IT[s,t])`

单位：

- `E_unit`：MWh/(MW_IT·year)
- `c_interrupt`：USD/MWh

根据当前仓库中的年度训练/推理利用率、空闲功耗比例、得州 PUE 和推理负荷曲线，得到近似校核值：

| 年份 | 年度设施用电量 MWh/MW_IT | 中断成本 USD/MWh |
|---|---:|---:|
| 2026 | 4,954 | 565 |
| 2027 | 4,861 | 576 |
| 2028 | 4,771 | 587 |
| 2029 | 4,678 | 599 |
| 2030 | 4,594 | 610 |
| 2031 | 4,513 | 620 |

正式实施时必须采用实际运行快照权重重新计算。

**确认：**

- 首选逐年动态价格。
- 如果程序必须使用统一参数，主情景采用 **600 USD/MWh**。
- 敏感性分析采用 **300 和 1,200 USD/MWh**。
- 暂不批准没有进一步计算依据的 460 USD/MWh。

### 2.2 PCLR 与非计划中断必须分开

区分：

1. `dc_curtail`：Conditional Firm/PCLR 合同允许的中断。
2. `dc_interrupt`：原计划供电未能实现造成的非计划中断。

两类中断分别计价、分别记录，不允许重复统计。

现有代码中，PCLR 使用 `v/(8760*PUE)`，其价格约为 278 USD/MWh，与当前真实设施用电量口径不同。

执行方须统一损失价值计算口径，或者为合同补偿价格较低提供独立依据。

### 2.3 防止虚假提前投运

不得允许模型通过“名义上 IT 容量已投运，但大部分时段实际中断”的方式虚增 Speed-to-Power 成果。

确认以下规则：

- `S1_GRID_EARLIEST` 的严格 Firm 基准不允许非计划中断。
- S2/S3 的非计划中断建议设置年度计划设施电量 **0.5%** 的上限。
- 0.5% 属于研究假设，不是 ERCOT 法定标准。
- 另测试 0% 和 2% 的敏感性。
- 合同中断与非计划中断的总量不能超过各快照真实的设施需求。
- COD 和实际交付指标须区分“已投运容量”与“实际获得服务的任务量”。

必须增加价值一致性测试：

当某单位 IT 容量在全年全部计划运行时段均发生中断时，其累计中断损失应与对应年度的服务价值相抵。

同时核查贴现因子、快照权重和单位转换。

### 2.4 既有用户保护

批准逐母线、逐时段的硬约束：

`background_shed[scenario,b,t] <= background_shed[S0_repaired,b,t] + 0.001 MW`

要求：

1. 首先按照 D3 修复 S0。
2. 使用修复后的 S0 作为唯一的既有用户切负荷基准。
3. 所有新增 AIDC 情景统一执行。
4. 使用相同的背景需求、天气、基准资产和时间快照。
5. 若不能同时满足新数据中心需求及既有用户保护，应优先采取新增负荷合同削减、自备供电或延迟投运，不允许通过增加既有用户切负荷获取容量。

上述约束是本研究采用的保护性原则，不能直接声称 ERCOT 对所有新旧负荷均具有这一统一的法定切负荷优先规则。

### 2.5 背景负荷缺供价格

现有：

`SHED_COST = 10,000 USD/MWh`

保留作为优化模型的紧急缺供惩罚。

但应区分优化惩罚与实际社会损失。

Brattle 为 ERCOT 开展的 2024 年 VOLL 调查估算，一小时无预警停电的全 ERCOT 平均损失约为：

`35,685 USD/MWh (2024 USD)`

该值用于社会损失核算或敏感性分析，不直接混同于当前 10,000 USD/MWh 的优化惩罚。

结果分别报告：

- 真实资源成本
- PCLR 合同中断成本
- AIDC 非计划中断损失
- 既有用户缺供损失
- 总社会成本

---

## 3. D3：远西部 2026–2029 年 S0 缺供（I-4）

### 3.1 确认处理顺序

采用：

**已承诺 TPIT 工程补全 → S0 重算 → 剩余失配识别 → 证据约束下的定向校准**

不允许仅为消除 S0 切负荷而无依据地统一增加线路容量。

### 3.2 现实依据

ERCOT 2026 年 2 月月报指出：

- Far West Texas 在关键工况下的可靠负荷服务能力约为 9,500 MW。
- Delaware Basin Stage 2 计划于 2026 年 6 月增加约 1,000 MW 送电能力。
- 下一轮主要进口容量改善预计要到 2029 年年底。

因此，西得州确实存在真实的近期输电瓶颈。

模型中的 1.82 TWh S0 缺供不应直接视为真实运行结果，但也不能不加分析地全部校准为零。

### 3.3 TPIT 项目筛选

执行方首先读取最新 TPIT，建立项目证据台账。

至少记录：

- TPIT Project ID
- 工程名称
- 输电服务提供商（TSP）
- 项目状态
- 电压等级
- 线路或变电站端点
- 额定容量及改造内容
- 预计/实际投运日期
- 信息更新时间
- 数据来源链接
- 映射至合成网络的母线及线路
- 是否已经存在于 2025 基准网络中

重点核查：

| 预计年份 | 相关工程 |
|---|---|
| 2026 | Bearkat–North McCamey–Sand Lake 345 kV |
| 2026 | Pecos County Transmission Improvement |
| 2027 | Silverleaf/Cowpen 345/138 kV |
| 2027 | West Texas Synchronous Condenser |
| 2028 | West Texas Infrastructure Project |
| 2029 | Delaware Basin Stage 5 |
| 2031 | Permian Basin 765 kV Import Paths |

特别注意：

1. TPIT 列名或计划投运日期不等于项目已经实际建成。
2. 主情景只纳入有可靠建设状态及 COD 依据的工程。
3. 状态不确定的规划工程纳入敏感性情景。
4. 同步调相机不能直接视为增加有功输电容量的线路。
5. **2031 年 765 kV 工程不能提前纳入 2026–2029 年。**
6. 必须核查原始网络是否已包含有关资产，避免重复计算。

### 3.4 对所有情景保持一致

有可靠承诺的历史输电工程应作为所有 S0/S1/S2/S3 共享的外生基准资产。

统一采用：

- 相同项目清单
- 相同投运日期
- 相同线路和变电站参数
- 相同基准资产投资口径

其费用应记录在共同基准资产账本，而不是误算为数据中心 BYOP 触发的新增内生公共投资。

不同 G-W/G-K/G-U 情景的内生输电投资权限仍按照工作包规定保持区别。

### 3.5 重新运行 S0

补齐工程后，逐年输出：

- 各母线切负荷量
- 各年切负荷总量
- 高边际电价时段
- 受限输电线路
- 相关接口的潮流及余量
- 各区域背景用电需求
- 公共发电及储能可用容量
- 真实投运工程对缺供量的改善

只有在上述分析仍存在无法解释的缺供时，才能进行定向校准。

校准须优先检查：

1. 合成网络是否缺失真实输电通道。
2. 线路额定值是否显著偏低。
3. 州级背景负荷增长是否被错误分配到远西部。
4. 机组退役、新增发电和储能 COD 是否合理。
5. 是否属于 ERCOT 已报告的真实局部瓶颈。

所有校准均需记录修改前后参数、依据及缺供改善幅度。

### 3.6 S0 验收原则

正常基准工况中，不应存在无法解释的大规模、持续性背景供电不足。

对有真实资料支持的局部可靠性风险，可以保留非零缺供，但必须明确记录来源和规模。

修复完成后：

- 输出最终 S0 基准网络。
- 冻结 `S0_repaired` 的逐母线、逐时段切负荷结果。
- 将其用于 D2 的既有用户保护约束。
- 报告 I-4 原有 1.82 TWh 缺供在每一步修复后的变化。

---

## 4. 实施顺序

请按以下顺序执行，不要直接启动全部主情景重算。

### Step 1 — TPIT 基准资产审查

完成真实工程筛选、状态核验、COD 核验和网络映射。

### Step 2 — 修复 S0

补齐有依据的工程，重新运行 2026–2029 年 S0，分析残余缺供，必要时开展定向校准。

### Step 3 — P0-1 修复

实现：

- 已投运 IT 容量跨年连续
- 合同中断与非计划中断分离
- 动态中断损失计算
- 既有用户保护约束
- 实际服务量与 COD 区分

### Step 4 — P0-2 修复

实现：

- 严格 `S1_GRID_EARLIEST`
- 有资格门槛的 Max–Min/Leximin
- 联合物理可交付性认证
- 与 `S1_ECON` 区分
- 以严格最早可交付结果生成 S2 电网报价

### Step 5 — 小规模验收

在缩小的 ERCOT 多年度模型上确认：

- 保持连续 LP
- 所有测试场景正常求解
- 年度 IT 已投运容量不无故下降
- 中断损失与服务价值一致
- 已投运不等于可以无限制中断
- 新增 AIDC 不增加既有用户切负荷
- 多场址不重复获得共享容量
- 未获接入资格场址不影响 Max–Min
- Firm/Conditional Firm 容量认证一致
- S1 严格最早可交付不受成本目标扭曲

### Step 6 — ERCOT 正式重算

验收通过后，重算 G-W、G-K、G-U 的主要场景。

此前 R1 和 DEV 的计算结果仅保留为：

`BASELINE_DIAGNOSTIC`

不得直接用作正式论文结论。

---

## 5. 执行方最终交付要求

本阶段完成后，必须提交：

1. 更新后的 `DECISION_LOG_REARCHITECTURE.md`
2. TPIT 项目和数据来源证据台账
3. TPIT 与合成网络的映射记录
4. 修复前后 S0 缺供比较
5. 非计划中断价格计算表
6. PCLR 与非计划中断分账记录
7. Max–Min/Leximin 分配验收结果
8. 新增和更新的单元测试
9. 小 ERCOT 算例的测试结果
10. 正式情景结果及主要差异分析
11. `EXECUTION_REPORT_FOR_PUBLISHER.md`

最终报告必须明确说明：

- 哪些工作已经完成
- 哪些工作尚未完成
- 修改了哪些代码
- 各项决策如何落实
- 是否通过验收
- 哪些参数仍属于研究假设
- 下一阶段需要研究者决定的问题

不能仅报告“求解成功”。

---

## 6. 主要参考来源

### ERCOT 大负荷接入

ERCOT (2026), PUCT Approves ERCOT's Batch Zero Process:

https://www.ercot.com/news/release/06182026-puct-approves-ercots

ERCOT (2026), Batch Zero Update, September:

https://www.ercot.com/files/docs/2026/09/11/14-Batch-Zero-Update.pdf

### 西得州可送达能力与输电工程

ERCOT (2026), ERCOT Monthly — February:

https://www.ercot.com/files/docs/2026/03/17/ERCOT-Monthly-February-2026-FINAL.pdf

ERCOT (2025), Report on Existing and Potential Electric System Constraints and Needs:

https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf

ERCOT (2026), Planning Guide, Section 6.4:

https://www.ercot.com/files/docs/2026/05/29/June-1-2026-Plannng-Guide.pdf

### 中断损失

The Brattle Group (2024), Value of Lost Load Study for the ERCOT Region:

https://www.brattle.com/wp-content/uploads/2024/09/Value-of-Lost-Load-Study-for-the-ERCOT-Region.pdf

### 本项目程序与输入数据

- `current_work_pckg/P0_MODEL_CORRECTION_PROPOSAL.md`
- `current_work_pckg/INTERIM_PROGRESS_REPORT_2026-10-20.md`
- `workflow/byop/model/rearch_mech.py`
- `workflow/byop/model/v240_mech.py`
- `workflow/byop/inputs/dc/yearly_task_parameters_2022_2050.csv`
- `workflow/byop/inputs/dc/hourly_inference_trace.csv`
- `workflow/byop/inputs/dc/state_pue_2022_2050.csv`

**最终研究原则：** 保留真实的物理接入限制，维持严格的 Speed-to-Power 决策与 LP 可求解性。所有新增约束和参数均应服务于识别 BYOP 的短期加速效应、长期公共投资替代效应及社会效率偏离，而不能通过人为设定预先制造结论。
