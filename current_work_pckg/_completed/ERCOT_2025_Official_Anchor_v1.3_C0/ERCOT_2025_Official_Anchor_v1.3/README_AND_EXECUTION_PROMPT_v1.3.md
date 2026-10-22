# ERCOT 2025 官方锚定校准：已采集证据、口径裁定与代码实施补充 v1.3

日期：2026-10-22（America/New_York）

核查仓库：simonyed/BYOP，分支 mainline-v13-stageA；本次读取 HEAD 为 `7a7eb2683a1d91840060616ecb31b76623223ed7`。本包未修改或推送该仓库，未运行优化器。

## 1. 本包解决什么问题

研究边界：只加强 2025 年及以前的事实与模型初始状态；2026 年及以后项目容量、预测年份、动态选址、POI 代理和技术曲线冲突均不在本轮处理。

研究方负责资料采集、来源评价和统计口径；执行方负责读入已提供的数据、核对本地台账、修改代码、形成可复算对账和调试。本包已附官方原件、提取表和离线脚本，不要求执行方重新开展开放式资料搜索。

这是可独立使用的证据与实施补充，不声称重新取得或逐条修订了此前未在当前附件中提供的 v1.1/v1.2 全文。与旧指令冲突时，本包对本轮 C0 的范围、资料分工和统计口径优先；历史结果保留。

## 2. 已完成的资料工作

本包 raw/ 已实际下载：

| 原件 | 具体用途 | 本次处理 |
|---|---|---|
| Native_Load_2025.zip / xlsx | 8 天气区、全年逐时原生负荷 | 已核验 SHA，复算全年、峰值和 3h 聚合 |
| ERCOT_2025_Annual_Report.pdf | 2025 宽口径容量快照及统计说明 | PDF 第 8 页（印刷页 6）已图像核验 |
| Capacity_December2025.xlsx | 2025 年 12 月五类容量趋势 | 已提取 2025 行及 operational/其他分类 |
| Capacity_November2025.xlsx | 11 月快照交叉参照 | 已下载，避免把 11 月当年末 |
| CDR_December2025.xlsx | 资源状态、机组标识、容量定义 | 已提取 1,772 条带数值记录，保留状态，不作为可直接投运清单 |
| IntGenbyFuel2025.xlsx | 分燃料实际发电量 | 已提取月度与年度 GWh、保留 WSL 符号 |
| MORA_August2025.xlsx | 供电风险时段与可用容量口径 | 已下载；是当时预测，不是全年实测 |
| ERCOT_Constraints_Needs_2025.pdf | 已观察拥塞、未来规划与限制 | 已核读；已观察期是 2024-10 至 2025-09 |
| ERCOT_Monthly_December2025.pdf | 补充交叉参照 | 已下载；标题月份不等于回顾数据月份，不作年末容量主源 |

各原件 URL、SHA-256 和用途见 SOURCE_MANIFEST.json。repo_snapshot/ 为已读取的代码和小型输入快照，仅作审计参考，执行方应在真实仓库完成修改，不用快照覆盖当前源码。

## 3. 已经可以确定的校准结论

### 3.1 负荷原始数据已经对上，不需要换源

本次下载的 xlsx SHA：`23664b0cddb047692f6cac26a4300e987c6309795395d394bf2dc223f37b53aa`，与仓库 baseline_2025_tamu_audit.json 完全相同。

| 指标 | 本次复算 | 裁定 |
|---|---:|---|
| 原始行数 | 8,760 | 通过完整性检查 |
| 全年原生负荷 | 488.233578542299 TWh | 保留为主负荷基准 |
| 原始逐小时最大值 | 83,679.001697 MW | 2025-08-18，Hour Ending 18:00 |
| 连续每 3 行均值的最大值 | 83,403.652115 MW | 复现仓库聚合方式 |
| 年报夏季峰值 | 83,707 MW | 单独保留，不强制替换 Native Load 峰值 |
| 年报与 Native Load 峰值差 | 27.998303 MW | 约 0.0335%；不能简单归因于 3h 聚合 |

重要修正：此前只比较年报 83.71 GW 与模型 3h 的 83.40 GW，遗漏了 Native Load 本身的 1h 峰值 83.679 GW。现在必须拆开“原始来源/修订差异”和“时间聚合差异”。没有证据说明为何相差 28 MW，暂不臆测为某一确定因素，也不为匹配峰值乘上全局倍率。

原始时间包含 `11/02/2025 02:00 DST` 与 `24:00`。附带 1h CSV 同时保留原始 HE 标签、源行号和行序号；model_sequence_start 只是复现仓库的连续模型坐标，不是 UTC 转换。不得无声删除 DST 行或重复计算 24:00。

### 3.2 29.8534 GW 差额不是可直接补建的缺口

年报容量基于 Installed Capacity Ratings；仓库主要来自 ReEDS 的夏季 MW，且状态和覆盖范围不同。年报还包含私人网络、部分配电侧和部分不可用/季节性资源，因此下表只作口径差异诊断。

| 类别 | 年报 2025 铭牌 MW | 当前模型 MW | 表观差额 MW |
|---|---:|---:|---:|
| Thermal | 89,507 | 72,455.3 | 17,051.7 |
| Wind | 40,719 | 40,028.8 | 690.2 |
| Solar | 37,443 | 29,262.7 | 8,180.3 |
| Storage | 16,656 | 12,768.4 | 3,887.6 |
| Hydro | 579 | 535.4 | 43.6 |
| 合计 | 184,904 | 155,050.6 | 29,853.4 |

核电提供了明确示例：CDR 四台机组 Installed Capacity 合计 5,268 MW，2026 夏季能力合计 4,973.2 MW，而模型为 4,980 MW。这里的 288 MW 表观铭牌差距主要不能被解释成漏了机组。2026 夏季列仅用于证明两种额定口径的不同，不作为 2025 实测能力。

12 月趋势表的 2025 行：Wind operational 40,718.75 MW；Solar operational 37,442.74 MW；Gas-CC operational 44,100.609 MW；Gas-Other operational 24,523.63 MW；Battery operational 16,645.90 MW。储能图表累计为 16,655.86 MW，另有 Small Generator 9.96 MW；未明确其状态之前，不自动把这 9.96 MW加到 operational。

需要执行方完成的工作是“源台账到组件的容量定义桥接与状态对账”，不能把 Thermal 差额全部加给 CCGT，也不能用 184.904/155.0506 给全网容量同比放大。

### 3.3 已取得机组清单，但不能把全表相加作为 2025 可用容量

CDR Unit Details 同时含 OPER、OPER-SYN、EXT-OUT、MOTH-SEA、MOTH-IND、PLAN、RMR 等状态，还有 DGR、SODG、SWGR、DC-TIE 等属性。本包输出全表与分状态汇总，明确标记 audit_only_not_model_ready。

`IN-SERVICE DATE <= 2025-12-31` 单独不足以确定可服务容量；还需结合状态、私人网络自用负荷和可切换容量。特别是：

- 排除 PLAN 系列和 indefinitely mothballed 的条目进入历史已运行集合；不能因数值列非空而纳入。
- OPER-SYN 不等于已全面商业运行；名义容量不等于可交付能力。
- 不能将私人网络铭牌容量全部作为公共电网 Firm 资源，也不能把 DC-TIE 容量伪装为本地发电。
- 当前 CDR 在 2025 年 12 月发布，不能单独保证覆盖 12 月 31 日最终状态；需保留与 12 月趋势表的快照差异。无直接证据的残差先解释和标记，不造机组、不填零假装完成。

### 3.4 可以增加分燃料运行验证，但不能机械闭合不同统计边界

Fuel Mix 的 Summary 已给出 GWh，附表可直接用于月度和年度比较。年度 Total 为 488,072.550688 GWh，与 Native Load 的差为 -161.027854 GWh（约 -0.033%）。原件含负数 Wholesale Storage Load（WSL）。

此处只报告差额；本次未证明其全部成因。不得人为调整负荷或发电量让两表相等。不要把 Summary 已经是 GWh 的能量再次乘 0.25；细分 15 分钟原始记录需另按其单位处理。

### 3.5 输电需要区分两个既有校准层

当前 2025 TAMU 审计记录 18 条线路、合计 4,993.9 MVA 的合成增容，仍有 102.2047 MWh 残余切负荷。此前 Stage B1 另外报告从 2026 起的 9 条线路、1,095.6 MW 共同基线修复。它们不是同一个账本，也不能把 MW、MVA 未换算就相加。

本次已提供 2025 校准逐线路表。2025 官方约束报告提供了历史拥塞的地理校验，但没有证明某个 TL 编号对应真实线路的真实热限额。对合成网络应保留代理身份，不能仅因为固定资产 LP 可行就宣称“已复现真实 ERCOT 全网”。

## 4. 新发现的历史 AIDC 证据边界

本轮未审查 2026+ 预测交付冲突。以下内容仅评价“截至 2025 年末是否已经运行”的证据质量。

| 场址 | 当前 2025 年末 IT MW | 已核读证据 | 本轮裁定 |
|---|---:|---|---|
| Abilene Stargate | 211 | Crusoe 2025-09-30 确认园区一期已运行；Epoch 211 MW 和细分日期仍含推断 | 运行状态有一手支撑；精确 IT 容量与分期日期仍属估计 |
| CoreWeave Denton | 67 | 仓库时间线引公司 billable MW；本次核读 Q1 公司公告为 8 MW 预计在 5 月交付，不能当作公告时已经完成 | billable/energized/IT/实际负荷须分别记录；不把计划措辞升级为事实 |
| Meta Temple | 152 | Epoch 2025-12-09 明示 best estimate；Meta 2026-07-22 才正式公告 serving traffic | 2025 年投运未经一手资料确认；不能认定绝对未用电，也不能标 VERIFIED |
| Google Red Oak | 77 | Epoch 依据建筑、设备及停车场影像推断 | 估计，非电表或已核实投运记录 |
| Microsoft SAT40 | 75 | 当前时间线为施工/设备影像判断 | 估计，保留现值但降级证据类别 |
| Microsoft SAT14 | 19 | 当前时间线为冷却设备、变电站及施工影像判断 | 估计，保留现值但降级证据类别 |

现行继承爬坡为 460.73 MW IT；其中 Temple 为 142.42 MW IT。不能继续把所有条目描述为已核实的历史投运事实。

处理建议：本轮默认保留既有数值和旧结果，新增逐字段证据类别、证据日期、观测日期、是否推断以及措辞原因；把该爬坡标成“从历史容量估计推导的负荷代理”。不由执行方自行将 Temple 改零、重排到未来或改动已批准年度预测。若后续需要修订历史数值，应由研究方另发带数值的修订表，而不是让执行方猜测。

原生负荷已经含 2025 年实际用电：核对账本时不可再把这六个场址的全部容量乘 PUE 叠加到 488.233579 TWh。设备容量与实际电力需求之间也需遵守现有工作负荷参数，不能因为标成 IT MW 就默认是恒定实测负荷。

## 5. 给执行方的直接执行 Prompt

你负责本地 BYOP 代码与程序调试。请以本包提供的官方原件、derived/ 和研究裁定为输入，实施 C0 的离线数据对账与代码接入。不要重新进行开放式资料采集；遇到证据不足，返回具体未匹配机组/字段与容量差额供研究方处理，同时继续不依赖该证据的任务。

### 任务 A：接入本包并复算

1. 记录真实 checkout SHA；若不同于本包 SHA，比较相关源码差异，不回退仓库。
2. 在 workflow/data/byop/ercot_official_anchor_2025/ 放官方原件和 manifest；建立数据路径配置，消除依赖个人 D:/ 路径。大型原件按仓库既定数据管理规则处理，manifest 和派生小表可跟踪。
3. 运行本包 rebuild_evidence.py，重现 VERIFIED_METRICS.json。它只读表、输出对账，不导入 PyPSA 或调用优化器。
4. 把已确认指标接入 `byop_paths.py` 和独立 audit builder；不改变动态 16 母线分布或 low/mid/high 总量。

### 任务 B：完成本地台账桥接

1. 利用本地已有 ReEDS generator DB 的机组记录与 CDR 的 UNIT CODE、名称、县、燃料、状态匹配，输出 matches、ambiguous、unmatched；先规范名称，再按县/燃料/容量候选辅助，不能只按最近距离确认身份。
2. 给每条模型资产记录源机组 ID、夏季 MW、名义 MW（若有证据）、纳入状态及日期。未知诊断字段允许明确的 unknown 状态，但不能传入模型数值矩阵；模型维持当前数值，不用占位符替代。
3. 输出分技术、状态、县的定义桥接：额定口径差、范围差、快照差、实际疑似漏项、尚未解释残差。没有证据不能把残差自动归给某项。
4. 优先核对 Solar、Battery 的 2025 已投运但仍落在 committed pipeline 的条目；这里只判断截至 2025 的归属，不重构未来预测。确认重复或跨账本的记录后，先生成更改建议表，不无声改历史资产。
5. 依据本包第 4 节给历史 AIDC 及 460.73 MW 继承负荷增加证据分类。保持数值，验证 2025 avg、end、inherited=end-avg 的代数一致性和母线不变。别把“字符串 estimate_wording=False”作为自动 verified 的充要条件。

### 任务 C：输出两套时间口径与历史负荷账本

1. 保留原始 HE 标签和源行号；复现 row-order 3h 均值和权重 3，8,760h/2,920 时段、年电量守恒。
2. 审计 2025 实际建模需求：Native Load、另加历史 AIDC、移除/重挂 AIDC、负荷缩放、储能充电分别计账；每时段母线合计必须可解释。不得直接再加一份 2025 数据中心存量。
3. 若现有代码已完全满足，只输出证据，不为改代码而改代码。记录未来继承爬坡加载位置，不审计未来交付冲突，也不更改未来情景。

### 任务 D：隔离合成输电修复，准备后续 C1

1. 为 raw synthetic、2025 calibration uplift、后续 S0 common uplift 分账；核验最终 s_nom 的组成，避免同一增容加载两次。
2. 从已提供 `TAMU_2025_CALIBRATION_LP.csv` 导出逐线原容量/增容/最终容量、单位和证据类别；不能将总额转换成实际 TPIT 已投运工程。
3. 给将来固定资产诊断准备配置，但本轮不执行。特别注意 `build_2025_baseline_tamu.py` 默认调用 calibrate_2025；C0 必须显式 no-calibration 或在新 audit-only 入口彻底阻断求解调用。
4. 后续若开展 C1，应区分 2025 年内运行回放和 2025 年末资产状态，年末装机不能默认为全年都可用。本轮保留日期元数据即可。

### 本轮边界与验收

- 本轮只做 C0 离线对账、代码接入与必要的纯数据/结构测试；solver executions 必须为 0。沿用之前尚未开启的运行门控，不申请新的正式 B3 运行。
- 不改 ERM、VOLL、技术成本、未来 POI 年份、天然气条件、选址权重或年度增量。
- 不用宽口径 184.904 GW 作为硬性拟合目标；物理可用容量、Firm 权利和铭牌容量分别处理。
- 输出 `C0_INPUT_RECONCILIATION.md`、`C0_GENERATOR_MATCH.csv`、`C0_CAPACITY_BRIDGE.csv`、`C0_LOAD_ACCOUNTING.csv`、`C0_HISTORICAL_AIDC_EVIDENCE.csv`、`C0_UPLIFT_LEDGER.csv`、`C0_QA.json`。
- 有限而必要的测试：源 SHA；负荷年电量/峰值；DST/24:00 行保留；3h 守恒；历史负荷不重复；机组不一对多重复计容；PLAN 不误入历史运行；校准增容不重复；历史 AIDC 证据标签；无求解调用。
- 回报 SHA、修改文件、关键指标、匹配覆盖率（按 MW 与条数）、未解释残差、测试结果和 solver executions。不要把“脚本跑通”写成“真实 ERCOT 校准已完成”。

## 6. 仍不能由本次资料直接决定的内容

尚未完成：ReEDS 原始逐机组数据库到官方记录的一一映射（原始 DB 在执行方本地）、63 母线历史负荷的真实空间分配、合成线路与真实线路热限额的完全对应、六个 AIDC 的 2025 实际逐时电表负荷。

本包已把“继续网上找资料”和“使用本地数据运行确定性匹配”分开：前者由研究方继续负责，后者就是执行方应做的代码任务。本包足以推进 C0，但不应宣称这些剩余问题已被解决。

## 7. 来源

- ERCOT Hourly Load Archives：https://www.ercot.com/gridinfo/load/load_hist
- 年报：https://www.ercot.com/files/docs/2026/03/19/2025-ERCOT-Annual-Report-Final-Single-Pages-March-19-2026.pdf
- 12 月容量趋势：https://www.ercot.com/files/docs/2026/01/08/Capacity-Changes-by-Fuel-Type-Charts_December_2025.xlsx
- CDR：https://www.ercot.com/files/docs/2025/12/19/CapacityDemandandReservesReport_December2025.xlsx
- Fuel Mix：https://www.ercot.com/files/docs/2025/02/07/IntGenbyFuel2025.xlsx
- 资源充裕度说明与归档：https://www.ercot.com/gridinfo/resource/2025
- 约束报告：https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf
- Crusoe 一期上线：https://www.crusoe.ai/resources/newsroom/crusoe-announces-flagship-abilene-data-center-is-live
- Meta 上线公告：https://datacenters.atmeta.com/2026/07/temple-we-are-online/
- Epoch Temple：https://epoch.ai/data/ai-data-centers/directory/meta-temple
- Epoch Red Oak：https://epoch.ai/data/ai-data-centers/directory/google-red-oak
- Core Scientific Q1：https://investors.corescientific.com/news-events/press-releases/detail/115/core-scientific-announces-fiscal-first-quarter-2025-results

官方原件保留原始来源；提取数值与本包解释分开。部分 2025 历史资料在 2026 发布，可用于回顾校验，但不自动进入 2025 研究决策者的信息集。
