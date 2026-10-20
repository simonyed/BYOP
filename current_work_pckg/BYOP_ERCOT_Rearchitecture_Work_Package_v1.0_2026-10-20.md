# BYOP ERCOT 仿真架构重构工作包 v1.0

> 面向 Codex / Claude / 其他具备仓库访问与求解环境的执行者  
> 编制日期：2026-10-20  
> 工作性质：已有 PyPSA-USA/BYOP 程序的针对性重构、校验与分阶段运行；不是另起炉灶，也不是要求一次完成全国模型  
> **强制最后一步：提交完整的执行情况报告与可追溯交付清单。**

## 0. 执行指令与优先级

请先阅读本工作包、仓库 `workflow/byop/README.md`、Source《论文顶层设计.md》，然后核查实际仓库 HEAD、最近执行报告、代码与数据。凡本工作包与论文顶层设计冲突，以论文顶层设计和研究者已确认的决策为准；凡本工作包中的代码路径、参数或功能描述与新 HEAD 冲突，应先记录差异并提出最小兼容方案。严禁仅依据文件名宣布某功能已经运行成功。

代码仓库：<https://github.com/simonyed/BYOP>  
本次方案审查所依据的代码基线（2026-10-20）：`6637d81102e5cde13fcd45fd105004ac6cd9e76d`。执行时必须记录实际 SHA，不自动重写既有成果。

**目标：**把当前 ERCOT 算例改造为“输电骨干与 POI 实际可交付能力 → 企业 Speed-First BYOP 决策 → 公共电网跨年投资反馈 → 2050 长期路径依赖”的可运行、可检验、LP-only 模型。优先证明论文机制，数值精度在有证据的范围内逐步校准。

**不得改变的研究约束：**

1. 保持 PyPSA-USA + Python/Linopy + 连续 LP。离散供电模式或转换路径可在 LP 外枚举；不因追求复杂真实性而默认改成 MILP。
2. 先合成/7 区回归测试，再建设一个小型真实地理 ERCOT 骨干样例，通过门槛后才运行更大 ERCOT；全国 48 州不在本工作包实施范围。
3. 保留 S0/S1/S2/S3 与 M1–M4 科学问题；论文重点是 M2 公共扩张反馈和 M3 长期路径依赖。
4. S2 维持既定的 **Speed-First（逐年严格优先最早交付服务）→ 私人成本最小化** 双阶段决策，Speed Premium 主指标事后核算。现有有限延迟损失 `v` 模型只做机制对照/敏感性，不得未经批准替换 S2 主定义。
5. S3 和 S2 使用相同物理可行集合、技术、工期、信息可用性及需求。S3 以社会真实资源成本（含适当环境外部性）衡量效率；必须输出 matched-service 对照，不能把少服务视为更高效率。
6. 2026–2035 每年有新增 AIDC 需求；2036–2050 无新增 AIDC，2035 年训练/推理/PUE 参数延续；2040/2045/2050 为补充规划与评价节点。公共规划可保留五年前瞻，企业可知具体申请的窗口按此前既定三年信息约束；只有当年批准的决策形成不可逆承诺。
7. 保留推理工作日/周末逐时曲线；训练只在日内移时且每日任务守恒；代表性 3 小时调度 + 必要时连续 1 小时应力检验。
8. 不因为一条事实缺失就将数值留空、写占位符或默认为零。若无法获取精确值，提供有出处、明确范围的研究假设与敏感性，区分“未知”“确认无容量”“不适用”。
9. 不删除旧模型、历史结果、原始数据和用户已有修改。新的空间方案独立配置，历史 7 区和 county 算例保留作回归/对照。

## 1. 论文问题与反事实设计

| 场景 | 定义 | 不可缺少的结果 |
|---|---|---|
| S0 No New AIDC | 保留既有数据中心及普通负荷，不增加本研究新增 AIDC | 无新增 AIDC 时的公共发电、储能、输电扩张轨迹 |
| S1 Grid-Only | 新 AIDC 只能获得具备物理可交付性和投运资格的公共电力；允许推迟 COD | 电网最早供电年份、未交付 IT、公共补建投资 |
| S2 Developer-Driven BYOP | 企业在事前可获得的电网容量/报价及工期下，先尽可能提前投运，再最小化私人成本；承诺固定后公共系统重新响应 | BYOP 技术与路径、交付速度、公共扩张变化 |
| S3 Coordinated Planning | 同样的需求、物理可行集合和真实工期下社会协调建设 | 实际社会资源成本及 S2–S3 效率偏离 |

主比较：S1−S0、S2−S1、S2−S3；另做 S3 在 S2 实际服务轨迹固定条件下的 matched-service comparison。主机制：M1 速度—技术选择，M2 私人 BYOP—公共扩张，M3 资产利用/冗余/再利用与长期锁定，M4 私人—社会成本与风险归属。

**成功的 ERCOT 模型不能仅证明 BYOP 电源能比电网快。**它必须让 S1 的真实瓶颈产生可解释的迟延，使 S2 的 BYOP 决策在相同瓶颈下内生发生，再引起 S0/S1/S2/S3 的公共投资路径差异。

## 2. 已有代码快照与需先核实的缺口

本工作包所依据的主要文件（执行者先阅读，而不是立刻替换）：

| 仓库位置 | 2026-10-20 观察到的功能 | 审核重点 |
|---|---|---|
| `workflow/byop/model/v250_mech.py` | 最新 county GCE、TPIT 走廊选择、gas gate、S2-SF | 缺失真实 POI 进口资格；县级网架仍非电气分区；S2 私人 LP 继承 S1 LMP，但购电资格未与真实可交付额度对齐 |
| `workflow/byop/model/v240_mech.py` | S0–S3 静态多期 LP，FLEX、N 类 BYOP、部分复用 R、双账本、服务配平 | S2 价格接受者与公共物理可行域的一致性；Firm/非 Firm 资格和重复预留；C 合同路径；按年份新增项目的真实投资起点与 COD |
| `workflow/byop/model/v240_path.py` | 年度 approve-and-commit 控制器、2036–2050 衔接 | 是否兼容新的 ERCOT 拓扑与 GCE；半年度 COD、2050 终值、退役和锁定 |
| `workflow/config/config.byop_ercot_county.yaml` | `reeds` + `county`，`192s`，来自 185 县节点基线 | 新建 TAMU 电气骨干配置，不覆盖此文件 |
| `workflow/byop/inputs/dc/ercot_cohorts_2026_2035_county.csv` | Dallas、Denton、Travis、Bexar 县级示例 | 真实位置核验，加入 Abilene、Reeves/Permian 等对照，不强制所有数据中心聚于四县 |
| `workflow/byop/inputs/grid/TPIT_TO_COUNTY_ASSET_MAP.csv` | TPIT 项目→县级输电走廊关联 | 改成项目→电气接口/候选线路的可验证映射，不能用县界代替实际连接 |
| `workflow/byop/inputs/tech/TECH-01_technologies_DRAFT.csv` | RICE/SOFC 等候选技术成本、效率和工期的草案 | 保留来源和区间，分清工程 COD 与外生申请审批 |

注意：县级模型曾涉及约 185 母线、452 走廊及 2,127 条 TPIT 项目记录。这些数字属于旧实现或数据台账，**不代表已通过真实 ERCOT POI 验证**。`v250` 默认 `gas_gate=contract`，`evidence` 模式又可能因资料缺失将全部新建燃气关停；二者均不能未经检验视为真实基准。

## 3. WP-A：ERCOT 物理输电骨干重构（第一个实施阶段）

### A1. 数据源与路线选择

主路线：使用 PyPSA-USA 原生 `tamu`/Breakthrough Energy 合成节点网络，按照电气连通性和关键输电接口进行有约束聚合，形成可运算的 ERCOT 骨干系统。试探 40–80 个保留关键走廊的输电节点，具体数量由网络完整性、运行时间和结果稳定性决定，不把这个数字当真实电网分区数。

关键参考：

- PyPSA-USA 空间配置：<https://pypsa-usa.readthedocs.io/en/latest/config-spatial.html>
- PyPSA-USA 输电数据：<https://pypsa-usa.readthedocs.io/en/latest/data-transmission.html>
- ERCOT 年度规划：<https://www.ercot.com/gridinfo/planning/>
- Texas 123-bus 345-kV backbone 公开检验案例：<https://rpglab.github.io/resources/TX-123BT/>
- Texas A&M 公共合成输电/气电测试系统：<https://electricgrids.engr.tamu.edu/electric-grid-test-cases/>

TX-123BT 可用于独立测试、拓扑与瓶颈校验，但不要在主模型已经基于 PyPSA-USA 后另建一套长期优化代码。TAMU/TX-123BT 都是**合成网络**，不可以把合成母线冒充真实变电站或声称真实项目接入容量已经得到认证。

### A2. 网络聚合原则

1. 主要保持 345/765 kV 输电骨干、跨区域进口路径和主要发电—负荷接口，必要时保留会限制数据中心接入的 138 kV 通道。765-kV 未投运项目按未来承诺/候选资产编码，不得加入 2025 存量。
2. 分区依据电气连接、关键割集/走廊以及瓶颈位置，不按县界拆分母线。县、城市、TSP、州、EIA 厂站作为节点属性与资源匹配标签。
3. 配置应支持不同资源分辨率和最终输电分辨率；保存 `busmap`、原始设备→聚合节点映射、容量加总和跨区线路。
4. 保留 ERCOT 电气边界。Texas 其他 ISO/非 ERCOT 区域不能因位于州内而被错误纳入；边界交换能力明确界定，禁止隐含无限供电。
5. 使用 ERCOT RTP、TPIT 和已公开的关键规划接口校验地理关系；真实 TPIT 工程与合成线路无法确认精确一一对应时，只允许区域接口级校准，记录不确定性。

### A3. 验收

- 7 区旧网络和 county 旧网络可复现，不被新配置覆盖。
- 新网络无意外孤岛、重复走廊、负容量、无穷边界进口；负荷、机组容量、资源可用性与上游基线的加总差异报告可审计。
- 至少生成网络图、节点/线路台账、不同空间尺度的比较表、主要受限输电接口列表。
- 小模型可完成 S0 基线 LP；不能只做网架绘制即标记通过。

## 4. WP-B：POI、公共供电资格与内生 Grid-Only COD（第二个实施阶段；最高科学优先级）

### B1. 新的 POI 层

为代表性数据中心场址 `s` 引入独立 POI，而不是把一县等同一个 POI。一个输电节点可接多个独立 POI，一个数据中心项目可按证据分期投运。每个 POI 保存：

`site_id, location, ercot_membership, parent_bus, request_year, requested_IT_MW, PUE, import_equipment_limit_MW, upstream_transfer_limit_MW, firm_entitlement_MW, conditional_entitlement_MW, connection_project, project_status, earliest_grid_COD, confidence, source_url`。

其中未知数据必须保留 `unknown` 证据状态，同时以明确、可计算的假设情景赋予数值；不能把 `unknown` 当作“无限”或“零”。

### B2. 公共电力可交付能力

分别建立并审计以下四层能力：

1. **POI 设施进口资格**：断路器、变压器、专用接入线路等约束；在证据不足时用合理功率区间和附加接入成本/工期代理。
2. **上游网络可送达性**：与其他现有/拟增负荷共同受制于输电接口、线路、变电站及实际投运工程；不能仅使用 LMP 判定供电可行。
3. **系统资源充裕度/可靠容量**：保留 TX 系统 ERM，辅以节点/接口压力约束与有限高峰/故障样本。LP 结果应标为 N-1/G-1 近似或压力代理，不能声称完成 ERCOT 正式动态稳定性审查。
4. **接入时间**：区分物理建设与采购工期、工程审批/核验/研究、排队/批量分配、其他行政原因。尤其不能把 2026 Batch Zero 的申请分类或审查停顿全部解释为“当地缺少物理装机”。

对多个同时申请的场址，必须做联合供电可行性检查，禁止逐项目独立计算的 `headroom` 在总量上重复分配。Firm 和 Conditional Firm 要有独立的服务可用性与容量权利记录。

### B3. 年度 COD 机制

对每个项目和年度，形成 `Grid-only` 的新增可交付 MW 和最早 COD；公共发电、输电、变电站或 POI 专属扩建只有在工程 COD 后才改变可用电网容量。保持 `decision_year`、`commit_year`、`construction_start`、`COD` 和 `retirement_year` 的语义区分，不因 PyPSA `build_year` 字段而把开工年错当投运年。

输出延迟归因：`POI equipment`、`upstream transmission`、`system resource adequacy`、`procedural/study`、`combined/uncertain`。S1 的低服务量必须能对应一项或多项已记录限制，而不是人为固定 `poi_lead=2/3/5`。

### B4. 完成标准

- 在至少一个紧约束和一个非紧约束真实地理代表场址，S1 交付时间有可解释差异。
- 关闭上游瓶颈时，Grid-Only 能提前交付；增加瓶颈时，交付不应不合理增加（允许其他受耦合约束引起的非单调效果，但需解释）。
- 多项目申请不得超过同一接口的物理服务/认证容量；已投运公共扩建应合理改变后续可用额度。
- 专门报告物理原因和行政/研究原因的贡献与可辨识程度。

## 5. WP-C：企业 BYOP 决策与 ERCOT 现实模式（第三个实施阶段）

### C1. 三种供电模式与三种资源取得路径分离

供电模式：`Grid-Only`、`Grid-Connected Flexible`、`Islanded`。桥接供电（Bridge-to-Grid）作为年份间从 Islanded/自供主导转为有进口资格的 Grid-Connected 的合法转换路径，不单独设第四种永久模式。

资源取得路径：`N` 新建，`R` 经核实可复用既有/退役资产，`C` 专属合同/合格供电权利。所有权、资源取得路径、接线位置及对公共电网可用的容量信用必须分别记账。合同 C 不应只改变经济价格，还必须有实际交付路径和防重复出售的容量权利。

### C2. ERCOT 模式映射与约束

- 对照 ERCOT `WLPUN/BYOG`，提供“有限电网进口 + 自有发电/储能”的配置。场址瞬时净取电 `0 <= grid_import[s,h] <= certified_withdrawal_limit[s,y]`，场内设备和储能按能量平衡提供剩余负荷。
- 对照可中断大型负荷（包括 PCLR 机制演变），提供适当的 Conditional 供电或负荷调减；设置事前确定的 T/G 高压与网络拥塞触发、年度 MWh/小时/次数/最长连续时长预算，避免无限免费中断。
- Islanded 不使用 ERCOT 公共电网进口，其可靠性由场址内设备/储能/可中断负荷承担；不要把 BYOP/BTM 与完全离网混为一谈。
- Firm/Conditional Firm 是研究中的服务权利抽象，须建立映射说明；不能直接说 ERCOT 正式提供与模型名称完全同义的两个商品。
- 共享公共可靠容量、POI 进口权和 BYOP 有效容量不得双重记账。BYOP 电厂的可用容量与上网出口信用也不可同时超额分配。

官方制度参考：<https://www.ercot.com/services/rq/large-load-integration>；<https://www.ercot.com/services/comm/mkt_notices/M-B062326-01>；<https://www.ercot.com/services/comm/mkt_notices/M-B062326-02>。

### C3. 私人 LP 与公共 LP 的一致性

现有 S2 私人阶段基本从 S1 取得 LMP，再允许 `grid_purchase` 使用与研究需求相关的购电容量。必须改成：

1. 由统一的 POI/联合 FCF 层生成事前可获得的网电进口报价、服务质量和逐年可交付上限。
2. 企业在相同容量、技术、气源、建设与施工约束下执行 **按年度先最大化已投运 IT，再最小化私人成本**；明确报告哪种瓶颈触发 BYOP。
3. 当年企业批准的合同、BYOP 资产和进口资格锁定；公共 LP 按实际承诺/可用公共供电重新决定后续新增发电、储能与输电。不得将企业阶段不可交付的“廉价网电”在公共阶段变成免费的无限来源。
4. 必要时使用有限次数报价—选择—再认证循环，但每一次仍是 LP；设置收敛/不一致诊断及最大迭代次数，不默默接受不一致的企业/公共解。
5. 输出最早投运服务路径、私人总成本、事后 Speed Premium、公共投资替代量和 BYOP 新增容量；不要把 Speed Premium 作为 S2 主目标中的任意大权重。

### C4. 设备及气源边界

主候选：RICE、SOFC、风、光、储能及证据充分的 R/C 路径；其它燃机技术可以继续作为补充敏感性而不喧宾夺主。技术工期包括设备采购、场址许可、燃料/电气接入；明确可先投运的部分容量和全年/半年度 COD 处理。可继续使用 `TECH-01` 数据，但要审计来源、2025 美元币值、运维、热耗率、冗余系数和极端短工期证据等级。

天然气约束用三级证据，不用“县内没有气电厂则天然气不可用”的硬规则：

| 类型 | 供气处理 |
|---|---|
| L0 Verified | 有项目级可交付容量/运输权、管线接点或已核实合同；按权利与时段限制燃料 |
| L1 Infrastructure Proxy | 有机组、管线或其他基础设施证据但缺增量可交付容量；加入可复现的连接工期/费用/容量界限与敏感性 |
| L2 Unknown | 未取得充分证据；不判定必然无气，使用审慎成本/工期上限情景，主结果必须标注不确定性 |

通过每日/峰值 MMBtu 消耗与已证实或假定 MDQ 做约束，显式计算燃气支线与合同完成时间。ERCOT 州内天然气瓶颈不能用 PyPSA-USA 州级天然气节点自动表示；不要求重做全面的天然气管网扩张 LP。

### C5. 真实案例校验（不是硬校准技术组合）

以真实项目观察支持不同机制，而不是强制模型复现它们宣称的准确电气接线：

1. Abilene / Taylor County：Crusoe–Microsoft 公告 900 MW 现场发电和储能，适合检验大规模自备电源和后期公共投资响应。<https://www.crusoe.ai/resources/newsroom/crusoe-announces-new-900-mw-ai-factory-campus-in-abilene-texas-to-support-microsoft-ai-infrastructure>
2. Dallas 周边：Prometheus–Conduit–ENGIE 的现场燃气/电池桥接与备份供电，适合检验临时自供转网、保留或再利用。<https://www.prometheushyperscale.com/news/prometheus-hyperscale-and-conduit-power-partnership>
3. Reeves County / Pecos：Prometheus–Istmo 计划分期 1.5/2.5 GW，自供电方案强调不等待电网升级，适合检验强接入瓶颈下的离网/有限进口选项。<https://www.prometheushyperscale.com/news/prometheus-hyperscale-and-istmo-energy-partner-to-develop-data-center-campus-in-west-texas>

先核查每个场址的 ERCOT 电气服务区成员资格、已有/规划装机、项目状态、阶段性 COD 与证据性质；公告值不等于已投运值，也不能从公司宣称的加速推算反事实延迟年数。可在有限代表性 POI 做机制校验，之后保持预测性新需求的外生州/区域分配，不把所有未来数据中心强放在三个案例场址。

### C6. 完成标准

- 至少一个瓶颈场址在 S2 中内生采用 BYOP，且关闭瓶颈后不再无理由采用相同的高成本 BYOP。
- 设备 lead 改变能够改变速度优先解或其经济第二阶段；不因 `build_year` 混淆允许在设备建设完工前发电。
- WLPUN 进口上限、Islanded 零进口、Conditional 中断预算、训练日守恒、储能 SOC、Firm 资源认证全部通过单元/集成测试。
- N、R、C 三路径不会因同一资产所有权/容量被重复使用；燃气 gate 不再因“缺证据”假造无限容量或直接归零。

## 6. WP-D：2026–2050 跨年扩张反馈与效率比较（第四个实施阶段）

### D1. 主控器

把最新 ERCOT 骨干 + POI + S2 决策纳入年度 approve-and-commit 控制器。每年只批准真实形成承诺的公共与专用投资，之后作为不可逆历史状态进入下一次有限前瞻 LP；区分申请、合同、许可、开工、投运、退出、退役。保持 2036–2039 的逐年资产状态推进与 2040/2045/2050 补充里程碑。

**特别修复历史审计指出的边界问题：**SOFC 2026.5 COD 的首年可用小时处理；2040–2044 退役与规划窗口衔接；窗口末端未偿回投资的合理残值或终值。所有年份的资本成本只记入一次社会与私人账本，合同付款不得被直接视为社会真实新增资源成本。

### D2. 可解释的输出

每年、每场址、每资产保存：`requested_IT`, `served_IT`, `unserved_IT`, `COD`, `grid_import`, `BYOP_MW`, `BYOP_MWh`, `public_generation_build`, `storage_build`, `transmission_build`, `upstream_bottleneck`, `gas_deliverability_status`, `asset_owner`, `asset_path`, `asset_status`, `private_cost`, `social_resource_cost`, `carbon/water_externality_if_used`, `sunk_cost`, `remaining_life`, `utilisation`, `reuse_value`, `cancellation`。

报告至少包括：

- M1：速度优先解对供电额度、BYOP lead、气源与合同可得性的响应；速度溢价事后核算。
- M2：相对 S1 的公共发电、储能、输电增减；识别替代投资与双重建设，区别 BYOP 新建和复用。
- M3：2035 后 BYOP 与公共资产的利用率、冗余 MW、总现值、提前退出和再利用。
- M4：S2 vs S3 的社会资源成本及服务量；同时输出 S3 matched to S2、S3 matched to S1 的服务匹配比较，公开解释无法精确匹配的部分。

禁止仅用优化目标值差异作为全部社会成本差异；现金转移、私人电价/合同账和社会资源成本必须分别记录。除非实际测试通过，不要宣称 M1–M4 已“实证发现”。

## 7. 实现顺序、停机检查与防止计算资源浪费

| Gate | 必须通过的测试 | 未通过时处理 |
|---|---|---|
| G0：代码与输入审计 | 记录 SHA、环境、既有结果可复现程度、无误覆盖旧文件 | 先修复或报告阻断，不开大规模算例 |
| G1：网架与 S0 | 新 ERCOT 小骨干网无异常孤岛、容量与需求守恒、S0 可求解 | 仅调试空间/数据，不引入 BYOP |
| G2：S1 接入 | 真实地理 POI、联合 headroom、可追溯 Grid-only COD，压力场景与单调性/守恒测试 | 不能进入 S2 论文主结果 |
| G3：S2 机制 | 强/弱瓶颈对照；至少一个内生 BYOP；技术 lead 敏感；WLPUN 与 gas gate 检验 | 修复企业—公共一致性，不能只调整惩罚系数制造结果 |
| G4：长期 S0–S3 | 年度状态账本、不可逆承诺、2050 资产结果、matched-service、社会成本账本全部有效 | 只能称阶段性结果，不得称完整论文实证 |

首轮最小实验建议：只选 2–3 个不同电网约束的代表性 POI；同样的 AIDC 服务请求及时间路径，在 `weak-grid / constrained-grid / grid-upgrade` 三种清晰物理设置中对比 S1/S2/S3。变量改变须有实际物理意义，禁止为了得到 BYOP 结果任意篡改真实网络数据。通过后扩大到 ERCOT 主系统。

## 8. 必须生成的交付文件

执行者可以根据实际代码组织方式调整文件名，但不得遗漏以下种类。**所有执行程序与运行配置保持在原 BYOP 仓库结构内**（以 `workflow/byop/`、`workflow/config/` 为优先）；数据来源与工作包可存放本地 `work_pkgs`；不得创建无人维护的第二套 BYOP 求解框架。

1. `README_REARCHITECTURE.md`：运行环境、入口命令、配置与结果目录说明。
2. `DECISION_LOG.md`：每一项空间、POI、气源和合同假设的决策编号、理由、来源、可替换参数、确认/未确认状态。
3. `SOURCE_EVIDENCE_REGISTER.csv`：原始资料网址、机构、获取日期、证据类型、适用地区、可信度；能获取的数值写实值，不能获取的给可运行的上下界假设与理由，不填裸占位符。
4. `NETWORK_MAPPING_AUDIT.csv`：原始 bus/line/asset→聚合节点/接口映射和总量守恒。
5. `POI_DELIVERABILITY_LEDGER.csv`：各项目、各年、各类网电服务权利、可交付容量、COD、瓶颈归因与证据等级。
6. `ASSET_COMMITMENT_LEDGER.csv`：公共/BYOP/合同 N/R/C 的投资年份、COD、权利、用途、退役与剩余价值。
7. `SCENARIO_COMPARISON.csv` 与图表：S0/S1/S2/S3 的服务量、公共与专用投资、速度、真实成本、长周期利用率及 matched-service 指标。
8. `TEST_AND_VALIDATION_REPORT.md`：各 Gate、单元测试、集成测试、LP 性质、容量守恒、失败案例和耗时。
9. **`EXECUTION_REPORT_FOR_PUBLISHER.md`：强制最后一步编制的完整执行情况报告。**
10. 如需跨电脑交接，附 `RETURN_PACKAGE.zip`，只打包小体积决策文档、关键输入/输出摘要、报告和 manifest；大规模网络 `.nc` 和日志可用可追溯路径/哈希代替，不能把未包含内容声称已交付。

## 9. 强制最后一步：编写并提交执行情况报告

**无论本工作包全部完成、部分完成、求解失败、缺数据、尚未得到正式结果，执行者都必须在结束前写出 `EXECUTION_REPORT_FOR_PUBLISHER.md`。这是完成工作包的必要条件，不是可选收尾。**

执行报告必须包含以下固定栏目：

1. **总体状态（PASS / PARTIAL / BLOCKED）**：本轮实际完成 A/B/C/D 哪些子任务；哪些未开始、哪些失败，不得把代码存在等同测试通过。
2. **代码与环境**：Git 仓库和 SHA、改动文件清单（新增/修改/未改）、依赖和求解器版本、具体运行命令、机器/线程和主要求解时间。
3. **既有成果保留与变化**：旧 7 区、county 模型是否仍可跑；与旧基线的定量差异，以及差异原因（数据、物理机制、数值错误）。
4. **数据准备情况**：数据文件目录、来源/获取日期、覆盖范围、数据缺失、用于替代的具体建议值及依据、每个重要文件的哈希或可核验位置。
5. **科学机制逐项验收**：M1–M4 分别填“未实现 / 已实现未校验 / 测试通过 / 现实校准支持”；写出对应情景、图表、关键数值与证据文件路径。
6. **Gate 结果表**：G0–G4 的测试名称、预期标准、实测值、PASS/FAIL/NOT RUN 与失败原因。绝不省略未运行测试。
7. **核心结果摘要**：每个 S0/S1/S2/S3 的服务量、最早 COD、BYOP MW、公共发电/储能/输电 MW、真实资源成本、资产利用/冗余；若无结果明确写“未计算”。
8. **发现的缺陷与局限**：真实 POI 缺证、TAMU 合成网络、气源代理、可靠性近似、模型退化/无界/不可行、结果对假设敏感之处；区分可修复 bug 与研究假设局限。
9. **下一阶段待办**：按 P0/P1/P2 排序，给出具体修改对象、可执行操作、验收标准及估计依赖；有需要研究者判断的重大事项要显式列出，不擅自改变既定研究目标。
10. **交付清单**：逐个列出可交接文件相对路径、文件大小、用途、SHA256/版本；如果有 `RETURN_PACKAGE.zip`，列出其中实际包含的内容与未包含的外部大文件。

报告末尾必须用一段中文总结：**“当前 ERCOT 仿真能否可信地回答：电网为什么延迟、BYOP 为什么发生、公共电网如何长期改变？”**分别给出 Yes / Partial / No 和一条最直接的证据；禁止使用未经结果支持的笼统“全部成功”表述。

最后，向研究者汇报时优先提供执行报告、测试报告、模型结构变化图和返回包路径。不要先进入全国模型，除非研究者在确认 ERCOT Gate G4 后另行授权。

---

### 附：执行者应首先打开的参考资料

- 本项目 Source：《论文顶层设计.md》（本工作包的科研目标上位文件）。
- 仓库 `workflow/byop/README.md`、`model/v250_mech.py`、`model/v240_mech.py`、`model/v240_path.py`、`model/byop_paths.py`。
- ERCOT 官方 Batch Zero 大型负荷资料：<https://www.ercot.com/services/rq/large-load-integration>。
- ERCOT 2025 RTP 与实际扩张计划：<https://www.ercot.com/gridinfo/planning/>。
- PyPSA-USA 分辨率/骨干选择：<https://pypsa-usa.readthedocs.io/en/latest/config-spatial.html>。
- Texas TX-123BT 数据与论文：<https://rpglab.github.io/resources/TX-123BT/>。

**版本控制注记：**v1.0 是研究工作包，不是已执行报告；所列示例数值、节点数和项目公告均需要执行阶段核验与记录证据等级。当前不授权在工作包之外作破坏性代码、数据或 Git 历史修改。
