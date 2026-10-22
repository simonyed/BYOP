# BYOP v1.6：完成共同基线校准，停止扩展诊断

日期：2026-10-22。核对仓库：`simonyed/BYOP`，分支 `mainline-v13-stageA`，最新 HEAD `55766e315539997bcf45a0ae3000f221211e2f6e`。

本包是根据 GitHub 最新代码、v1.5 结果以及新核查的 ERCOT/EIA 官方资料形成的执行指导和数据包。**本轮资料核查没有运行模型，也没有修改或推送仓库。以下模型调整由执行方在 L2 实施。**本包的决策是推进方案；不能把本文件的存在当作代码已经实现或校准已经完成。

## 1. 评审结论与本轮唯一目标

v1.5 已经完成了必要诊断，应进入校准收尾。采用 **X1：固定校准前阻抗，只增大热限额**，不采用最多五轮的容量—阻抗迭代。X1 中 72,905.1→112.58 MWh 的变化已足以决定保存方式；不用再追原校准 102.2 MWh 与 X1 的最后约 10 MWh 差异。

本轮目标是交付一个有来源、能复现、可被 S0–S3 共同引用的新版 2025 规模基线，并明确三个锚点的验证结果。新增年度 LP **最多两次，零自动重试**：资产调整后的最小热限额增容；保存并重新载入后的固定资产复验。储能诊断、全量机组编号交叉表、历史逐小时风光补齐均不再作为本轮前置任务。

这是研究基线的校准，不是 ERCOT 的可靠性认证。2025 年底机组规模配 2025 年负荷曲线仍是统一规模检验，不能称为逐月投产、逐小时停机均完整复现的历史回放。

## 2. GitHub 现状：哪些已完成，哪些尚未落地

| 项目 | 最新仓库证据 | 当前结论 |
|---|---|---|
| v1.5 两次 LP | runner `0c23f85f`，代码/结果 `7d699edf`，报告 `55766e31`；两次均精确 optimal，零重试 | 接受结果，不重跑诊断 |
| 网络保存方式 | `workflow/byop/build/build_2025_baseline_tamu.py` 仍在增容后把 x/r 除以容量比例；仅保存 >0.5 MVA 的增容 | 问题已验证，生产构建器尚未修复 |
| 正式共同基线 | 动态配置与 `rearch_mech.py` 仍引用旧 `baseline_2025_tamu_prepared.nc` | X1 尚未成为共同基线 |
| 2025 实际负荷 | Native Load 2025，488.23358 TWh；官方 1h 峰值 83,679.00 MW；3h 聚合峰值 83,403.65 MW | 保留，重新核对总量守恒即可 |
| 历史资产 | C0 已修正混期匹配；v1.5 的 32 项表仍保留原模型值 | 本包给出 12 项重点处理方案，不再全数等待外部裁定 |
| 官方可靠性锚点 | `wp2_ercot_s0_s1.py` 的 15% ERM；`reserves.py` 按所有快照构造需求×(1+ERM)；另有 ERM-02 内生裕度校准 | 不能称为已用官方季节性 PRM 校准 |
| 输电外部验证 | 已有 TPIT/Far West 未来工程与机制资料；未形成对 2025 官方历史拥塞清单的系统验证 | 用本包清单补一次有边界的对照 |
| 数据中心选址 | 动态配置仍为 `siting_variant: dynamic_pnnl_v1` | 保留动态选址与全部 AIDC 输入 |

## 3. 本包采用的资产处理方案

依据为 EIA **2025 年度最终表**的明确状态字段、ERCOT 2025 年 12 个月 MORA，以及 December 2025 CDR。年度最终 EIA 是对 2025 的回溯资料，不是 2025 年当时可见的信息；只能用于历史起点修订，不可把后见信息注入未来 AIDC 决策。

### 3.1 七个“状态冲突”：六个保留，一个移出历史

EIA 年度最终表确认以下六项为 OP 且 2025 年已运行：Sequoia 1 401.4 MW（12 月）、Fagus 331.6 MW（12 月）、Buzios/Roaring Springs 250 MW（10 月）、Big Star solar 200 MW（3 月）、La Casa 150 MW（12 月）、Long Point 120 MW（12 月）。**保留这六项，不因 December CDR 的未来商业批准日期将其全部删除。**Sequoia 第二期仍属于未来，不能并入第一期。

Gaia solar 152.7 MW 在年度最终 EIA 中仍为 Proposed，ERCOT MORA 的 Gaia 条目亦为零容量，年底转为 2026。将 ReEDS `Unique ID 20535` 从 2025 历史转入 2026 发电侧 committed pipeline，避免删除后漏入未来。不得据此修改任何 AIDC cohort。

### 3.2 三个改划候选

- Pyron wind：年度最终 EIA 已将 56981/1 列为 OP，249 MW summer；2025 MORA 也持续列出 Pyron 风电。激活原 ReEDS `10088` 记录，增加 249 MW 历史风电；不按 ERCOT 铭牌数放大，不顺便加入其他 Pyron 电池。
- Danish Fields Storage、Myrtle Storage：EIA 最终表仍为 Proposed/TS，与 ERCOT 冲突。但 ERCOT CDR 为 OPER，2025 MORA 多个月持续列出明确的 `DAN_BESS1/2`、`MYR_BES1/2`，各自季节容量合计 150 MW。**本研究的 ERCOT 历史接入状态以当地运营机构证据优先**：将原 ReEDS `21245`、`21242` 各 150 MW 从 2026 pipeline 移入 2025，保留原 MWh、时长、效率和县—bus 映射。
- 保留 EIA 冲突和项目级匹配置信度；这不等于取得官方 ERCOT–EIA 逐机编号对照。若源记录校验发现并非同一期，单独标为 unresolved，不允许新增一条重复容量来绕过。

预期物理容量净变化：风电 +249 MW、储能 +300 MW、光伏 −152.7 MW，合计 **+396.3 MW**。从旧总量 155,050.6 MW 出发应为约 155,446.9 MW；最终以修改前后逐记录清单求和为准。这不是向 ERCOT 广口径铭牌总量强行配平。

### 3.3 Kiamichi、Gateway：保留物理容量，分开限制 ERCOT 可用量

年度最终 EIA 的 summer 合计分别为 **1,224 MW、826 MW**，与现有物理容量一致，不删除机组。先前 1,400−885=515、937−937=0 使用的是另一容量列，不能全年套用。

本包已从 **全部 12 个月 MORA** 抽取正容量与 unavailable 负项，见 `evidence/SWITCHABLE_2025_MONTHLY_AVAILABILITY.csv`。例如：

| 2025 月份 | Kiamichi ERCOT 净可用 MW | Gateway ERCOT 净可用 MW |
|---|---:|---:|
| 1 | 1,215 | 729 |
| 6–7 | 609 | 709 |
| 8–9 | 609 | 556 |
| 12 | 1,215 | 551 |

这些是月度展望中的可用容量口径，**不是实际逐小时强迫停运记录**。本包将其作为有来源的月度运行上限代理，停止等待不可得的全年真实停机序列。

实施要求：

1. 在现有聚合前把两个电厂分出，生成独立的 plant group。不得把限制加到同 bus 所有燃气机组上，也不得猜测六台 Kiamichi 单机与 ERCOT 单元的一一配对。
2. 每月约束为 `sum(p_dispatch of plant) <= min(physical_summer_MW, MORA_net_MW)`；保留原有运行约束。可通过拆出的电厂组容量上界等价实现。
3. ERM 的既有容量信用也必须使用相同限制且只扣一次。仅加实际发电上界而让 ERM 继续按全厂满容量计信用不算完成；也不得对已扣除 switchable unavailable 的容量再次乘同一比例。
4. 模型坐标仍可能为 2030。用现有源行映射识别原始 2025 月份；不得按 2030 日历自行重新配齐或声称 UTC 对齐。
5. 本包另附 December 2025 CDR 的 2026–2031 季节可用表，供未来情景接续使用。该表不用于覆盖 2025 历史；超出覆盖期的延续必须标为假设，不冒充新预测。

## 4. 把原来的三个锚点落成可验收结果

### 锚点一：实际负荷与实际装机规模

负荷保持 Native Load 2025；按第 3 节落实目标资产修订和 switchable 可用限制，输出修改前后按机组、carrier、bus 的桥接表。对 OPER-SYN、商业批准、已运行、firm capacity credit 分栏，避免把不同概念当作同一个开关。

不新增全量机组匹配任务。不要求所有 ERCOT 资源编号均与 EIA 完成官方确认。未匹配项目只需列明已计入/未计入容量与理由；重点 12 项必须有动作和来源。

### 锚点二：官方规划备用裕度，先做同口径校验，不偷换成逐时 ERM

本包补入 **December 2024 Revised CDR（2025-02 发布）**，它覆盖 2025；May/December 2025 CDR 的主要夏季预测从 2026 起，不能冒作 2025 实绩。

| 2025 夏季风险时段 | 官方 Firm Load MW | 官方计信用资源 MW | 报告 PRM |
|---|---:|---:|---:|
| 负荷峰值时段 | 86,716.912 | 103,105.481 | 18.89893% |
| 净负荷峰值时段 | 82,963.969 | 91,651.798 | 10.47181% |

这些是包含预测负荷和合格规划资源的**报告情景结果**，不是两个应直接强制拟合的政策门槛，也不是 2025 实际备用率。网页上的历史 13.75% 参考值也不能未经口径论证替换 `ERM=15%`。

执行方用本包 ELCC 表和报告资源/需求分项，完成 `RELIABILITY_ANCHOR_BRIDGE.csv`：

1. **官方行**：逐字节来源不改，复算上述两个 PRM。分子区分 thermal、wind、solar、storage、switchable、private-use、RMR、外部联络、planned 等；分母保留屋顶光伏、响应负荷等调整。
2. **模型同口径行**：按修订 fleet 的原始县/资源分区映射，采用报告相应风险时段的 ELCC；储能按真实时长取值，必要时线性插值，不统一算 100%。thermal 和 switchable 的重叠信用必须消除。缺少的 DR、联络、PUN 项目显式为未建模，不能悄悄补入虚拟容量。
3. **差异桥**：依次量化预测 vs 实际负荷、规划资源 vs 年底已投运资源、容量口径、未建模 DR/联络/PUN、ELCC 分类等差异，给出调整后差额和未解释余量。Native Load 与 CDR Firm Load 未确认一致时，不可直接相减后宣布可靠性缺口。
4. **ERM 单独行**：报告现有逐快照 energy-backed ERM 及 ERM-02 的定义。它们用于模型内交付约束，不能重命名成官方 PRM。不得通过降低实际机组、伪造备用信用或调低未来负荷去追平该指标；未来 ERM-02 的负裕度也不等于官方已认可的规划标准。

本轮把官方 PRM 用作**基线的外部可靠性校验锚点**，不另起一个备用约束架构改造。验收必须区分“官方口径已复算并完成桥接”与“逐时 ERM 已被官方标准标定”；后者若未实现，必须明确写未实现。不得只贴官方数字就标记通过，也不得因指标不同无限调参。

如果桥接显示重要的真实资源遗漏，应在第一个 LP 之前一次性完成有证据的输入修订；没有证据的余量保留为模型限制。无法判断是否影响核心结论时返回具体阻断量与原因，不能写成完全通过。

### 锚点三：官方输电报告验证局部瓶颈

使用本包 `TRANSMISSION_EXTERNAL_CHECKLIST.csv`，对应官方 2025 Constraints and Needs 报告第 5 页。报告观察窗口是 **2024-10 至 2025-09**，不冒作全年 2025。

对最终固定资产输出做一次无求解后处理：列出模型主要拥塞区、跨区接口方向、满载小时和附近切负荷；与官方约束逐项标记“区域/方向一致”“方向不一致”“网架未分辨”“停运序列未建模”。

重点：West Texas **Export** Interface 是西部送出，不能因模型 Far West 有**进口**供电不足就声称验证成功。Longshore–Consavvy 345 kV 先核实是否有粗网走廊对应；多数 138 kV 约束不能强行匹配到合成聚类 TL 编号。无法分辨就报告边界，不逐条调线路去拟合历史拥塞租金。

## 5. 执行顺序与停止标准

### 阶段 A：一次完成无求解修改

1. 基于 HEAD 核对执行环境；如果 HEAD 已前进，先查看新增 diff，不回退他人提交。先归档 v1.5，保留所有输出与 solve log。
2. 将本包原始资料、来源 SHA、抽取脚本和决策表纳入版本控制的证据目录；不修改上游 ReEDS 源表，使用有审计记录的 targeted override。
3. 修改 `build_2025_baseline_tamu.py`：覆盖资产状态与分组；施加月度可用上限；修复最终保存步骤。**只写 s_nom，不再按 uplift 缩放 x/r**。`raw_uncalibrated.nc` 中校准前 x/r 是参照；它已经经过原有接口预处理，不要另行回退整个 TAMU 原始网架。
4. 增容小于 0.5 MVA 只可以在展示表过滤，不能在网络中丢弃。最终 s_nom 必须对应完整 LP 解；报告表注明展示阈值。
5. 先完成 PRM 桥接所需的输入口径分析。准备 `results/BYOP/baseline_2025_tamu_v16/` 新目录；旧结果不覆盖。代码和配置在求解前先提交。

### 阶段 B：两次 LP，完成后停止校准求解

**LP1：**按修订后的物理 fleet、可用上限、2025 负荷及固定校准前 x/r，重跑现有最小线路增容 LP。继续沿用现有目标函数和价格并记入 manifest，不以接近 102.2 MWh 作为目标。

**LP2：**从 LP1 保存出的新版 prepared.nc **重新读取**，固定全部容量，使用既有精确 optimal 配置做年度复验。校验保存后的 x/r 与 LP1 的输入一致、s_nom 与 LP1 解一致、月度可用限制仍在、无扩张变量。不得只验证内存网络。

两次均要求 `status == ok` 且 `termination == optimal`。本轮预先采用以下**研究代理容差**：年度 EENS/年电量 ≤1e−5（约 4.882 GWh）、最大缺口/官方小时峰值 ≤1e−3（约 83.68 MW）；它们不是 ERCOT 标准，不代表满足 LOLE/LOLH。报告完整 EENS、事件、最大缺口和位置，不把小于阈值描述为零切负荷。

若未通过，不追加第三次“试试看”的 LP。保留输出，区分全系统资源不足与局部传输不足，给出一个具体需处理的输入或约束原因并返回 `BLOCKED`。禁止循环修改 VOLL、负荷、ERM 或任意线容量直到数字好看。

### 阶段 C：后处理、回归与交付

- 完成负荷/资产桥接、PRM 桥接、输电对照；只使用本轮 LP 输出，不再重算储能二级目标。
- 测试覆盖保存再读回的一致性、资产不重复、两电厂可用上限在 dispatch/ERM 生效、源月份映射、PRM 分子分母分类。继续跑相关 C0/C1/动态选址回归；原历史结果保持原测试标准，新版资产差异用显式 v1.6 预期验证。
- 报告储能吞吐量与重叠即可，保留 v1.5 已证实的退化解释。不要继续证明 p630 14 的 98 GWh，也不要加 MILP。
- 更新 `GREAL_NETWORK_EVIDENCE.csv` 中旧“8 buses”等元数据，区分既有 Epoch 存量与 dynamic 研究 cohort，不把所有 8-bus 提及机械改成 16。保留未来 AIDC 数量、动态选址、inherited 460.73 MWIT、POI、gas、cost 和既有正式门控。
- 准备一份引用新版基线的后续 S0/S1 配置/manifest；这一步不执行 S0–S3 或打开正式门控。固定同一基线、同一可靠性定义和同一资产限制后，后续恢复顺序为 S0/S1，再 S2/S3。

## 6. 完成的定义与固定返回

只有代码已实现、保存后网络复验通过、三个锚点各自有实际比较输出，才能标记 `CALIBRATION_COMPLETE_WITH_STATED_LIMITATIONS`。本包附的数据与决策不能替代这些执行结果。若 PRM 仍只有 ERM=15% 的文字说明、没有容量信用和负荷差异桥，不得宣称三个锚点均完成。

交付至少包括：新版基线及 SHA（大文件留 L2 并记录路径）、`BASELINE_V16_INPUT_DIFF.csv`、`ASSET_OVERRIDE_AUDIT.csv`、`SWITCHABLE_CAP_QA.csv`、`RELIABILITY_ANCHOR_BRIDGE.csv`、`TRANSMISSION_EXTERNAL_VALIDATION.csv`、`BASELINE_V16_FIXED_ASSET_QA.json`、求解日志、`CALIBRATION_CLOSEOUT_REPORT.md`。代码提交在前，结果/报告提交在后。旧 v1.5 文件保持可追溯。

```text
START_SHA / CODE_SHA / REPORT_SHA:
CALIBRATION_STATUS: COMPLETE_WITH_STATED_LIMITATIONS | BLOCKED
NETWORK_REPRESENTATION: fixed_precalibration_xr_thermal_limit_proxy
SOURCE_AND_OVERRIDE_SHA:
PHYSICAL_FLEET_DELTA_BY_CARRIER_AND_PIPELINE_NO_DUPLICATION:
KIAMICHI_GATEWAY_DISPATCH_AND_ERM_CAP_CHECK:
LOAD_TOTAL_AND_1H_3H_PEAK:
OFFICIAL_PRM_REPRODUCED_PEAK_AND_NET_PEAK:
MODEL_PRM_SCOPE_BRIDGE_AND_UNEXPLAINED_MW:
ERM_VS_PRM_INTERPRETATION:
OFFICIAL_TRANSMISSION_MATCH_MISMATCH_UNRESOLVED:
LP_STAGES / ACTUAL_CALLS / RETRIES: <=2 / <=2 / 0
FINAL_FIXED_ASSET_EENS_MAX_GAP_EVENTS_AND_LOCATION:
FINAL_RELOADED_NETWORK_XR_CAPACITY_IDENTITY:
TESTS_AND_MATERIAL_LIMITATIONS:
NEW_BASELINE_PATH_AND_SHA:
S0_S1_CONFIG_READY / FORMAL_GATES_UNCHANGED:
```

## 7. 执行包内容与来源

- `DECISION_POLICY.yaml`、`ASSET_DECISIONS.csv`：本包明确采用的处理方案。
- `rebuild_evidence.py`：从原始官方文件重建证据 CSV，已本地运行通过，不读模型、不求解。
- `evidence/`：23 条重点 EIA 记录、24 条电厂月度上限、逐月原始行、两座储能原始行、官方 PRM/资源需求/ELCC、未来 switchable 季节表、输电清单。
- `raw/`：未经修改的 EIA 年度 generator 工作簿、两份 CDR、12 份 MORA、输电报告；`SOURCE_MANIFEST.json` 记录官方地址与 SHA-256。
- `repo_snapshot/`：核对时的关键 GitHub 文件，只作为审阅快照，不覆盖执行仓库。

核对链接：

- [GitHub v1.5 报告](https://github.com/simonyed/BYOP/blob/55766e315539997bcf45a0ae3000f221211e2f6e/current_work_pckg/C1_X1_STORAGE_VALIDATION_REPORT.md)
- [GitHub 基线构建器](https://github.com/simonyed/BYOP/blob/55766e315539997bcf45a0ae3000f221211e2f6e/workflow/byop/build/build_2025_baseline_tamu.py)
- [GitHub ERM 实现](https://github.com/simonyed/BYOP/blob/55766e315539997bcf45a0ae3000f221211e2f6e/workflow/scripts/opts/reserves.py)
- [EIA 年度详细数据](https://www.eia.gov/electricity/data/eia860/)
- [ERCOT 2025 资源充裕度资料](https://www.ercot.com/gridinfo/resource/2025)
- [ERCOT 2024 档案，含覆盖 2025 的修订 CDR](https://www.ercot.com/gridinfo/resource/2024)
- [ERCOT 2025 输电约束报告](https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf)
