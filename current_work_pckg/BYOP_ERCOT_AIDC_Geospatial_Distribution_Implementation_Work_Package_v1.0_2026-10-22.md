# BYOP ERCOT：2026–2035 数据中心新增负荷的多母线空间分配实施工作包 v1.0

**发布日期：2026-10-22**  
**适用分支：`mainline-v13-stageA`**  
**编制所依据的最新已核查提交：`b3cb9c32fb9b623ef7f8385095fba844572bfa0b`**  
**性质：代码实施 + 无求解器验证；须在《2025 ERCOT 官方锚定校准与 B3 机制审计工作包 v1.1》的 C0–C5 求解及模型校准之前完成。**  
**授权状态：NOT_APPROVED；本包不授权任何正式 LP / Gurobi 求解。**

## 0. 给执行方的立即指令

在当前 `mainline-v13-stageA` 分支上实施一个**新的、可切换的 2026–2035 研究新增 AIDC 容量空间分配版本**：2025 既有负荷和 D11 继承负荷保持原样；2026 研究新增需求按现有 Epoch 母线分布；从 2027 年起将预测、非已确认场址的研究新增容量按 Epoch + PNNL Existing Atlas + PNNL CERF-DC Higher Growth 的**逐年动态权重**分配给更多 TAMU64 母线；每个 `scenario × year` 的 ERCOT 新增 IT MW 必须守恒。建立新母线的证据分级 POI、燃气与现场风光输入，修正硬编码的 8 母线/48 服务键假设。新旧空间版本并存；**只进行静态数据测试、单元测试、无求解器网络结构检查与 DRY/gate 拒绝检查**。最后将代码、配置、数据、测试和审计报告推送 GitHub，明确停止等待研究者审核。

不得为获得 BYOP 提速或消除切负荷而修改历史发电、输电、ERM、2025 基线、S0CAL、VOLL、技术 CAPEX、建设周期或既有研究结果。不得运行 `step0`、`pilot_s01`、`pilot_core[_b3e]`、`run`、`attribution`、C1–C5 或任何会实际启动优化器的命令。

---

## 1. 已有进展与为什么先做本包

### 1.1 GitHub 现状（执行前必须再次确认 HEAD）

- `ee422ff1e95a6f4f9dd12965fa1d76adb04ef1b8`：旧八母线 B3-E，五个情景全部 optimal，S1 延期 312.75 MW IT·年、S2_final 延期 173.17 MW IT·年、BYOP 新建约 312.5 MW aero OCGT；S2_final 与 S3_mS2 在 48 个母线—年份上完全匹配，社会总成本差约 +2.28 百万美元。存在 2026 ERM 方法性零裕度、S0 背景切负荷、S0CAL 线路表示等方法警告。**这是冻结的原始空间对照，不允许覆盖。**
- `b3cb9c32fb9b623ef7f8385095fba844572bfa0b`：引入 PNNL Atlas、PNNL higher-growth 五种 market-gravity 预测、映射结果和 `DC_SITING_PNNL_DESIGN_NOTE.md`；**仅准备数据，模型仍从八个 Epoch 母线输入读取**。
- `workflow/config/config.byop_ercot_mainline.yaml`：`run_authorization: NOT_APPROVED`、`approved_git_sha: null`；本包结束仍必须如此。
- 官方锚定校准 v1.1 的 C0–C5 仍是单独工作包；其执行应读取本包完成并核验的新地理输入，但**不能混淆“地理分配引起的效果”和“官方事实校准引起的效果”**。

### 1.2 本包的科学目的

已知和在建的超大型 AIDC 集中在少数 Epoch 项目；直接将 ERCOT 全部 2026+ 预测增长继续分配给它们，会过度夸大这些站点的相对负荷和 BYOP 决策影响。PNNL 的现有园区及长期潜在场址可以提供新的空间证据。但 PNNL projected **不是已获接入许可的项目队列，也没有逐设施 COD 年份**，因此只用于**预测增量位置的先验**，不能直接形成 Firm 接入权或事实上的 2026 年建成时间。

实现目标是“更合理地分散预测增长、保留历史事实、明确未知权利”，而**不是强制确保某一母线数目、BYOP 技术采用率或延迟量**。

---

## 2. 输入数据和权威依据（不重新构造已有数据）

### 2.1 本仓库已可读取的文件

| 输入 | 路径（前缀 `workflow/`） | 作用 / 禁止误用 |
|---|---|---|
| ERCOT 研究需求规模 | `byop/inputs/dc/ERCOT_DC_TOTALS_2026_2035.csv` | 三种需求情景每年 `new_IT_MW`；**总量唯一锚点**，不得使用 PNNL 预测 MW 替换年度总量 |
| 当前 Epoch 新增研究需求 | `byop/inputs/dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv` | 既有八母线的时间分布；区分 `IT_MW`（研究新增）与 `inherited_ramp_IT_MW` |
| 2025 D11 继承爬坡 | `byop/inputs/dc/MAINLINE_INHERITED_RAMP_2025.csv` | 5 母线累计 **460.73 MW IT**，2026 起作为所有情景共有背景负荷，不参与新址重新分配 |
| 2025 Epoch 站点证据 | `byop/inputs/dc/EPOCH_TX_SITES_TAMU64.csv`、`EPOCH_TX_TIMELINE_EVIDENCE.csv` | 2025 时间加权均值约 **140.27 MW IT**已包含在原生基线负荷中，不另加；区分真实日期与未来估计 |
| PNNL 既有 Atlas | `byop/inputs/dc/PNNL_ATLAS_TX_SITES_TAMU64.csv` | ERCOT 映射记录 127 条；原始 OSM 定位/面积并非独立设施 IT MW；有潜在矿场和同园区重复 |
| PNNL 未来场址 | `byop/inputs/dc/PNNL_PROJECTED_HIGHER_TX_TAMU64.csv` | 五种互斥 market-gravity 场景的地点（截至 2035）；单条设施模型规模通常 36 MW IT；**不提供各场址逐年投运信息** |
| 已汇总母线位置证据 | `byop/inputs/dc/PNNL_CANDIDATE_BUS_SUMMARY.csv` | `src_epoch/src_atlas/src_projected` 和 `proj_higher_g{0,25,50,75,100}_IT_MW`；目前候选 37 个 |
| 数据版本与原始哈希 | `byop/inputs/dc/PNNL_PROVENANCE.json` | 验证数据版本、许可证、县界/母线映射规则 |
| 现有 POI 证据 | `byop/inputs/poi/GREAL_POI_ASSUMPTIONS.csv`、`GREAL_POI_E0_SCHEDULE.csv` | 原八母线的接入证据，保留历史批准设备和工期来源 |
| 母线可再生资源 | `byop/inputs/grid/ERCOT_WIND_SOLAR_POTENTIAL.csv` | 增加母线后仍必须共用 ReEDS2 资源池 |

源代码目录：`workflow/byop/build/`、`workflow/byop/model/`、`workflow/byop/post/`、`workflow/byop/tests/`；上一轮 B3 报告：`current_work_pckg/STAGE_B3_MAINLINE_RESULTS_REPORT.md`。

### 2.2 PNNL 官方来源（报告中逐条保留 URL / 版本 / 许可证）

1. Existing Atlas v2026.02.09：<https://data.msdlive.org/records/p147s-4h760>；DOI <https://doi.org/10.57931/3017294>；OSM 派生、ODbL 1.0。官方说明不同 `point/building/campus` 图层可能重叠，县界跨越的对象可能多行、存在遗漏及误识别。
2. Projected Locations v1.1：<https://data.msdlive.org/records/r0cga-34g05>；DOI <https://doi.org/10.57931/3020186>；CC BY 4.0。CERF-DC 预测 2035 年前的新场址；higher-growth 采用 EPRI 2024 参考的 **15%/年**用电增长（从 2023 年起），market-gravity 的 0%/100% 分别为区位成本/市场邻近性完全主导。它们是**互斥的模拟假设，不是独立观测或发生概率**；未纳入专有电网容量合同，因此不能从该数据推断 POI Firm 权利。
3. 原始预处理脚本据现有说明在本地 `work_pkgs/BYOP_ERCOT_DC_Siting_PNNL/build_pnnl_tamu_candidates.py`，GitHub 未跟踪该本地目录。**执行时必须将复现脚本、必要的不受限辅助映射及依赖列表纳入仓库（例如 `workflow/byop/build/build_pnnl_tamu_candidates.py`），不要只依赖原作者 L2 私有绝对路径。** 若原始数据体积较大不适合 Git 跟踪，保留下载说明、SHA256SUMS 和标准预处理产物。

---

## 3. 已确认的方法选择：默认代码参数，不再向研究者反复询问

### 3.1 2025 历史状态不变（最高优先级）

- 保留 Epoch 每个真实场址的 2025 年末 IT 容量与所在 TAMU 母线；**不按 PNNL 重新分配已存在的数据中心**。
- 2025 时间加权已有负荷约 140.27 MW IT 仍包含在基准网络原生负荷中；**不得再次叠加**。
- D11 五母线 `inherited_ramp_IT_MW` 总计 460.73 MW IT 保持路径、站点、供电处理、no-harm 属性不变；它是历史已投运设备的年内爬坡，**不是可再分配的 2026 新建申请**。
- 原 `E0` 设备认证/批准行以及有依据的真实资产 COD 不因未来需求权重变化自动移动、增大或改签给另一母线。

### 3.2 保留真实确定的 2026+ 场址，但须有逐项证据

每一条原 Epoch `2026+` 容量必须先生成一个 **confirmed/projected 分类台账**：`LOCKED_VERIFIED`（有独立、可追溯的已投运/在建/已正式承诺 IT 容量、地址和时间证据）或 `FORECAST_REALLOCATABLE`（未证实、仅为时序/比例推断）。

**不能因为 Epoch 报告包含项目名称、预测 IT MW、或某母线存在 E0 设备，就将其预测增量全量自动标记 `LOCKED_VERIFIED`。** E0 是设备/接入权证据，与确切的新增研究 IT 容量不是同一数据。没有足够证据时标记预测，按下述权重重新分配；必须公开列出具体筛选规则与人工复核的记录。

冻结的容量按原母线和原年份保留，其余每年预测剩余 `R_{sc,y}` 才被重新分配：

```
T_sc,y = ERCOT_DC_TOTALS[sc,y].new_IT_MW
H_sc,y = 460.73 MW (仅 2026；其他年份为 0；以现有 CSV 精确合计为准)
F_sc,y = Σ locked verified new research IT MW of scenario sc in year y
R_sc,y = T_sc,y - H_sc,y - F_sc,y  (must be >= 0)
NEW_sc,y,b = LOCKED_sc,y,b + R_sc,y * w_sc,y,b
Σ_b NEW_sc,y,b + H_sc,y = T_sc,y
```

**第一版采用审慎规则**：2026 年全部研究新增（中情景约 105.2211 MW IT）保持原 Epoch 分布；因此 2026 即便没有足以锁定项目的证据，也不应改变该年的母线分配。对于 2027+ 项目，仅锁定逐条验证的真实容量；剩余按动态权重分布。若实际锁定量超过年度总量，标记 `BLOCKED_DATA_CONFLICT` 并停止，绝不能自动裁减真实项目或修改 ERCOT 年总量。

### 3.3 三种空间依据归一化

对每个 `scenario sc`、`year y`、母线 `b`：

- `E_sc,y,b`：原始 Epoch **该情景该年的研究新增** IT MW（扣除 D11 后）的母线份额，归一化到合计 1；2026 年可直接继承原行。若存在已锁定项目，预测残差的 `E` 可沿用原始年度份额，但应在台账中显式指出这是模型先验而不是额外保证。
- `A_b`：PNNL Atlas 中去重、剔除明确加密货币矿场后、各母线的**独立站点数量份额**。不以园区建筑面积当作 IT MW。
- `P_b`：由 **PNNL higher-growth** 两种空间机制组成，先各自在 ERCOT 内归一化：

  `P_b = 0.25 * P_b(g0) + 0.75 * P_b(g50)`

  `g0` 为区位成本主导，`g50` 为兼顾成本/市场的预测。上述 25%/75% **是研究者可追溯的情景参数，不是 PNNL 发生概率**；不对 g0/25/50/75/100 五份数据直接等权求平均，因为 g25–g100 在 ERCOT 基本重复。

混合权重基准：

| 年份 | Epoch α_y | Atlas β_y | PNNL projected γ_y | 设计解释 |
|---|---:|---:|---:|---|
| 2026 | **1.00** | **0.00** | **0.00** | 不搬迁近年已识别项目的研究新增容量 |
| 2027–2028 | **0.70** | **0.15** | **0.15** | 近期以 Epoch 为主，适度扩展 |
| 2029–2031 | **0.45** | **0.20** | **0.35** | 中期更多考虑实际园区集聚与新的候选区位 |
| 2032–2035 | **0.30** | **0.20** | **0.50** | 远期以 PNNL 地理预测为重要先验 |

```
raw_sc,y,b = α_y * E_sc,y,b + β_y * A_b + γ_y * P_b
w_sc,y,b = raw_sc,y,b / Σ_{j in B_allowed} raw_sc,y,j
NEW_sc,y,b = LOCKED_sc,y,b + R_sc,y * w_sc,y,b
```

所有权重先对各来源各自归一化，之后才混合；小母线过滤后再次归一化。实现中必须支持 `--weights-config` 参数/版本化 YAML，不要把权重数字散落在代码里。程序运行必须确定性、无随机性、无需 LP。

### 3.4 候选母线：36 MW IT 累计阈值 + 八个 Epoch 保护

- 候选原始并集：8 Epoch + 21 Atlas + 26 PNNL projected => 当前合并 37 个唯一母线；先移除因纯矿场记录才入选、且无其他 Epoch/非矿场 Atlas/PNNL projected 证据的母线。若一个母线另有非矿场证据，**只排除矿场记录而非整个母线**。
- 第一版候选筛选基于 2026–2035 **`mid` 情景的长周期参考分布**：`E_b^decade` (原始 Epoch 2026–2035 总研究增量份额)、`A_b`、`P_b`，以三源等权构造独立于年度动态权重的**候选资格参考分布**：`q_b=(E_b^decade+A_b+P_b)/3`。
- 保留 `q_b * (mid 情景 2026–2035 总研究 IT 增量) >= 36 MW IT` 的非 Epoch 母线，同时**保留全部 8 个 Epoch 母线**。36 MW 是与 PNNL 典型模型设施规模相当的选择阈值，不是并网门槛；不要把它强制当作每年最小负荷、真实承诺设备规模或发电机单机容量。
- 当前提交数据下，执行前的**参考性预期**约 17 个母线（不是为凑数量而校准的硬通过条件）；正式数量必须由程序、去重记录和数据文件确定，若有差异在审计报告解释。
- 每年采用相同候选集合；按情景/年度计算动态 `w_sc,y,b`，允许某些母线某年度分配为 0，且在 2026 年大部分新母线必须为 0。不可用均匀分配来强迫每个母线有负荷。

### 3.5 必须实施的地理风险和源数据去重

Atlas 当前 127 条映射不能直接被宣称为 127 个独立供电设施：

1. 用 `id`、`type`、`operator`、`name`、经纬度、可获取的 campus/building 空间重叠信息去重；记录原记录数、明确重复数、疑似重复但无法证明的记录数。不同建筑同园区可独立记录，但不得既把完整园区又把重叠单楼当两份独立数据中心权重；**不确定时标注并提供 raw-vs-dedup 权重对比，不能静默删除**。
2. 单独列出并从**Atlas 基准权重**排除 Riot Corsicana、Riot Rockdale、MARA（Hood）、IONIC Cedarvale 四类矿场记录（以已核对的 OSM `id` 与名称双重判断）；不能把 Epoch/PNNL 其他独立证据也一起删除。
3. `bus_boundary_tie=True` 或到最近 TAMU substation 距离异常的记录进入 `SPATIAL_MAPPING_REVIEW.csv`，包含原 bus、备选 bus、距离差、来源；不得因地址靠近某母线就声称已有 POI 合同。
4. 保留并列展示 g0、g50、五场景等权平均三个 `P` 方案及 q_b 分布，主方案必须使用 `g0/g50 = 0.25/0.75`；其余仅生成无求解器的输入侧对照，不执行正式情景。
5. PNNL 的 `weighted_siting_score` 是 CERF 模型内部选址打分，**不是概率**；不得与 Projected IT MW 在归一化时重复加权。Projected `higher_growth` 的 15% 增长率也**不得再次乘入** ERCOT 年度研究总量。

---

## 4. 精确的数据对账和不可变基准

### 4.1 第一版必须复现的锚点

- 2025 平均 Epoch IT 存量：约 **140.27 MW IT**，已经在背景负荷中。
- 2025 年末减 2025 时间加权平均形成的 D11：**460.73 MW IT**；作为 2026 起共有继承负荷。
- ERCOT 2026 `mid` 审批/规划新需求：`565.9509634982 MW IT`；研究新增部分应约 **105.2209634982 MW IT**（按原始精度与当前四舍五入对账）。
- 2026–2035 `mid` 研究新增合计约 **4,567.903 MW IT**；原始 `ERCOT_DC_TOTALS` 的 2026–2035 累计值为 `5,028.6326899004 MW IT`，两者差额正是 D11 460.73 MW。
- 对 **low / mid / high 每一年**都守恒，不只验证 2031、2035 两个终点。
- 同一情景 `cumulative(y)=Σ_{k≤y} NEW_{sc,k}`；全情景使用按年一致的 PUE 数据和 2025/2026 背景负荷拆分。

**精度规则**：以上文本的简写展示不得代替原 CSV 浮点数；内部计算用 double precision，输出至少六位有效小数；数据守恒建议绝对误差 `<1e-4 MW` 每 `scenario×year`，如果历史四舍五入导致更大误差，必须以官方获批 ERCOT 总量为真值，对**重新分配的残差**作确定性末项修正并在 `ROUNDING_RECONCILIATION.csv` 记录，不允许改 D11。

### 4.2 锁定与预测的显示方式

为每个新项目/母线—年份保留四类不可混淆字段：

```
stock_2025_avg_IT_MW_in_background
inherited_end2025_ramp_IT_MW
verified_2026plus_increment_IT_MW
forecast_reallocated_increment_IT_MW
```

总量以 `new_research_IT_MW = verified_increment + forecast_increment` 计算；`inherited` 只加入系统背景，不进入新申请的 S1/S2 研究队列。不能因为模型在 `poi_cohorts.csv` 中只读取 `IT_MW` 就把历史继承负荷也写到该列。

---

## 5. 新母线的 POI、燃气、风光输入：先证据、再代理

新增母线会改变接入权利，因此此部分必须与“空间权重”单独审计。**不要因为某母线存在 PNNL Atlas 数据中心，就假定新研究申请已经取得经过认证的未占用 Firm MW。** 既有园区实际消耗的容量也不能重复用于新研究增长。

### 5.1 原有 Epoch 八母线

- `GREAL_POI_E0_SCHEDULE.csv` 所有有依据的 E0 行保持原 bus/MW/COD/preapproved/evidence/status 不变。
- `GREAL_POI_ASSUMPTIONS.csv` 的既有厂址资源/设备/燃气证据保留；随新研究需求改变的**衍生量**（例如 `research_IT_MW_2026_2031_mid`、`research_facility_MW_2031_mid`、PCLR 0.3×需求和 onsite RE 1×需求）可重算，但必须分别记录 `OLD`/`NEW` 和计算公式；绝不因为需求减少自动删去已承诺 E0 设备。
- 若某母线原有 `L1` 级燃气有已证实现场基础设施，也不能直接把此权限送给同母线其他独立场址；当前按一个母线聚合 POI 的机制是假设，需保留证据标签和边界，不默认为“任意新负荷可共用权利”。

### 5.2 新增非 Epoch 母线

为每个新母线生成记录，优先使用 PNNL 匹配点/网络母线坐标的可追溯映射，不可填充 Epoch 假场址或虚构已批准项目。

- `E0_total_MW=0`、不添加 `preapproved=True` 的研究 E0 行：其含义**仅是没有证据证明新研究申请拥有可供使用的已批准独立设备额度**，绝不能声称该母线的现实既有 POI 容量为零。
- 不凭空补造 `Firm` 进口权、PCLR 合同，也不能默认把 Atlas 既有数据中心的合同转给研究新需求。
- 如无独立证明，POI Upgrade/程序 `base` 初值沿用 v1.3 的**透明统一代理**：升级工期 3 年（low 2、高 5）、程序最早 2028（low 2027.5、高 2029）、升级成本 160 USD/kW（low 80、高 300）、场址升级容量上限 2,000 MW；全部标记 `PROXY_PNNL_NEW_SITE`。由于每个新母线给 2 GW 的潜在升级额度可能明显过宽，报告须计算这些合计许可代理上限，并与预测需求比较；不自行调节上限以得到期望结果，交下一阶段正式校准和敏感性决定。
- PCLR 的 proxy `0.3 × 2031 中情景该母线研究累计设施 MW` 可按旧逻辑生成，但注明只是**条件接入上界的研究代理**、并非现有批准资格；在计划开展科学结论前应单列敏感性。
- `gas_evidence_level=L2`（除非能找到母线/场址级独立证据）；暂保留对应燃气侧建设期 3 年、100 USD/kW、MDQ proxy 100,000 MMBtu/day，标注每项 PROXY，**绝不因为 PNNL 点接近既有燃气机组就自动当 L1**。
- `onsite_renewable_cap_MW = 1.0 × 2031 中情景累计设施负荷 MW` 可沿用旧代理，并同时受该母线 ReEDS2 风/光剩余资源约束；不能把 PNNL Projected 的校园面积当成已经核实的可建风光面积。
- 对于新母线 2027 年有正增长但 `E0=0`、程序最早 2028 的情形，报告必须明确标为 `POI_PROXY_MAY_DRIVE_DELAY`。这可能是**代理规则造成的延期**，不是现实 ERCOT 拒绝接入的证据。
- 真实 `ERCOT` 公共电网资产、研究负荷新母线、G-REAL 网络和 BYOP 专用 DC bus 必须严格对应同一个 TAMU64 AC parent bus；不新造公共母线，不允许跨 ERCOT ERCOT 以外区域。

### 5.3 POI 风险对照表（本阶段只生成表）

要求输出每个新母线：`candidate_source(s), map_confidence, atlas_independent_sites, projected_g0/g50_MW, year_first_forecast_MW, existing_ERCOT_POI_evidence, E0_new_request_MW, earliest_grid_COD_base, U_lead_base, U_max_MW, PCLR_MW, gas_level, gas_lateral_lead_base, renewable_cap_MW, evidence_class, risk_flags`。单独识别有 Atlas 但无 E0 证据、仅 projected 无 Atlas、加密矿场以及地理边界模糊的站点。

---

## 6. 代码实现：具体文件和改动建议

### 6.1 一定保留可比较的旧八母线算例

**禁止覆盖或重算下面任何现有内容**：

```
workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1/
current_work_pckg/STAGE_B3_MAINLINE_RESULTS_REPORT.md
workflow/byop/inputs/dc/MAINLINE_INHERITED_RAMP_2025.csv
workflow/byop/inputs/poi/GREAL_POI_E0_SCHEDULE.csv
workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc
```

建议采用两套可切换输入（在正式新基准获得批准前，不覆盖原八母线输入文件）：

```
workflow/byop/inputs/dc/MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv
workflow/byop/inputs/dc/MAINLINE_AIDC_RECONCILIATION_GEO_DYNAMIC_V1.csv
workflow/byop/inputs/dc/MAINLINE_SITING_WEIGHTS_GEO_DYNAMIC_V1.csv
workflow/byop/inputs/poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv
workflow/byop/inputs/dc/MAINLINE_SITE_CLASSIFICATION_GEO_DYNAMIC_V1.csv
workflow/byop/inputs/dc/MAINLINE_CANDIDATE_BUS_ELIGIBILITY_GEO_DYNAMIC_V1.csv
workflow/byop/inputs/dc/MAINLINE_NEW_BUS_POI_RISK_GEO_DYNAMIC_V1.csv
```

将上述命名作为默认建议，允许执行方调整，但结果报告必须给出新旧路径对照。原八母线 `MAINLINE_RESEARCH_COHORTS_TAMU64.csv` 和 POI 仍保持历史版本，不允许将它们作为“临时结果”覆盖。新版本采用 `siting_variant: dynamic_pnnl_v1`；默认不指定/显式 `epoch8_legacy` 时走原数据，以便 B3 原结果仍可复现。

### 6.2 输入构造器

1. 新建 `workflow/byop/build/build_dynamic_siting_inputs.py` 和版本化 YAML `workflow/byop/inputs/dc/MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml`，**不得依靠单独手工编辑几十行 CSV**；所有派生 CSV 由确定性脚本重建。
2. 从 `ERCOT_DC_TOTALS_2026_2035.csv` 按 `low/mid/high × 2026–2035` 取得年度总量；从 D11 扣除继承负荷；读取原始 Epoch research cohorts 的**研究新增**时间分布计算 `E_sc,y,b`；清理 PNNL Atlas、计算 `A_b`；PNNL g0/g50 分别归一化得到 `P_b`。
3. 按 3.2 的证据准则输出 verified/forecast 分类台账；实际锁定的 2026+ 容量只使用人工/可追溯证据，不基于 E0 自动臆断。
4. 使用 3.4 定义的单一候选集合，再用每年动态权重和该年的 forecast residual 分配；处理正常的零负荷年份/母线、标明请求年份。统一形成 `scenario, request_year, region_id, IT_MW` 的 v1.3 兼容 CSV，另存来源分解列。
5. 根据 2031 中情景累计新研究容量重算每个保留母线的派生 POI/PCLR/RE 参数；原八母线历史 E0 不动，新增母线 POI 按 5.2。对所有字段记录来源 `VERIFIED/DERIVED/PROXY/UNKNOWN`。
6. 重建输入对账与站点映射（`MAINLINE_BUS_SITE_POI_MAP` 如旧版只记 Epoch 历史，应继续作为历史站点表，另加 `NEW_RESEARCH_BUS_POI_MAP`；禁止把 PNNL 新建模拟点当 Epoch 真实场址写入已存在站点表）。
7. **重点避免运行旧 `build_mainline_inputs.py` 的副作用**：该脚本会重写 D11、E0、原 Epoch POI、背景对账等多个文件；本包优先新增独立构造器或进行安全模式拆分，确保运行新的构造器后，历史不可变文件的 SHA256 一致。

### 6.3 模型输入切换

- `workflow/byop/model/rearch_mech.py` 中 `ML_COH`、`ML_POI` 目前是顶层静态路径；实现新配置的读取切换，**必须在 `configure_mainline()` 和 `mainline_gate()` 的相关文件哈希确认前完成**，并让新 `ML_INPUTS`、实际输入 SHA 记录与选中的版本完全一致。
- `mainline_gate()` 仍然为所有 LP 严格门控；必要时在 `build_mainline_manifest.py` 列入本包新增输入、构造代码及其哈希。**不要修改门控从 `NOT_APPROVED` 到 `APPROVED`，也不要重用旧哈希 manifest 伪装通过**。
- 保持 `rearch_mech.py` 的公开网络/技术/工期/ERM/TPIT/S0CAL 等数学模型不变，仅改变对应研究 `SITES` 和 cohort/POI 输入。更新注释/help 中“8 Epoch buses”为“legacy eight buses / configurable research buses”，不应修改最优性定义或运行参数。
- 在 config 提供 `mainline.siting_variant` 及新输入路径，可在无求解器测试中展示所选 17 个母线及研究 IT 对账；不要让输入切换依赖某个开发者的本地 Windows 盘符或私人原始数据路径。

### 6.4 所有固定 8 母线 / 48 键假设都要修复

必须显式检查至少：

```
workflow/byop/post/collect_mainline.py
workflow/byop/post/stage_b3_tables.py
workflow/byop/tests/test_mainline_v13.py
workflow/byop/tests/structural_mainline_v13.py
workflow/byop/model/rearch_mech.py
```

尤其 `collect_mainline.py` 目前存在 `N_KEYS = 48` 和 `matched_service_48_keys_present`。将匹配验收改成**从实际批准的研究母线集合 × 当前模拟年份集合建立精确期望键集合**，同时验证两情景各自无重复、无缺失、无额外键、完整 numeric、服务量一致。**严禁从 S2 自身观测键集合推导“期望集合”，否则双方同时漏掉一个母线可能被错误判 PASS。**

对于 2026–2031 和 17 母线，理论期望键数为 **102**，不是固定 48；若有资格母线即使某年请求为零，也应拥有对应该母线—年份的显式 0 服务记录，或在模型合同中定义确切的有效键规则并测试。

- 新字段建议 `matched_service_expected_keys_present`, `matched_service_expected_key_count`, `matched_service_observed_key_count`；旧字段 `matched_service_48_keys_present` 可保留为 legacy 八母线输出兼容（不能用于 17 母线通用通过判断）。
- 结构测试 `ONE developer network for all 8 buses`、`len(gpur)==48` 等改成按实际 `N_B × N_Y` 检查，同时保留八母线旧案例回归。
- `stage_b3_tables.py` 中 `NAMES` 当前只含 8 站点；新增母线名称由映射表驱动，不能全部显示 `NaN`，也不能把新预测母线命名成真实已建园区。
- 不改变 2026 年 Speed-First 的字典序含义，不降低 no-harm 的完整性要求；新地理版本的 LP 可行性、最优性在本包**不求解，也不得声称已验证**。

---

## 7. 运行和质量验收：**本包明确不调用求解器**

### 7.1 推荐命令（具体 CLI 由执行方实现并在 README 中记录）

在 L2 或具有依赖的相同环境、`pypsa-usa/workflow` 根目录：

```bash
# 仓库/分支与未提交文件审查；确保无正在进行的旧求解器进程
 git status --short
 git rev-parse HEAD
 git branch --show-current

# 新的确定性地理输入构造器；不得写回 legacy 文件
python byop/build/build_dynamic_siting_inputs.py \
  --config byop/inputs/dc/MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml \
  --variant dynamic_pnnl_v1

# 纯静态/输入测试，必须同时覆盖 legacy 和 dynamic variant
python -m pytest -q byop/tests/test_mainline_v13.py
python -m pytest -q byop/tests/test_dynamic_siting.py

# 允许结构化创建网络 / 变量和约束，但不得 optimize / solve / Gurobi；需明确记录跳过优化
python -W ignore byop/tests/structural_mainline_v13.py --out results/BYOP/mainline/_structural_geo_dynamic_v1

# 原正式运行的门控必须仍然拒绝任何求解器调用
bash byop/run/run_mainline.sh gate
DRY=1 bash byop/run/run_mainline.sh pilot_core_b3e
```

说明：最后两条只进行门控检查和 DRY 命令组装，**不能**运行未加 DRY 的 `pilot_core_b3e`；如 runner 需要读取新 config，应额外完成该版 config 的 gate 拒绝测试。结构测试若意外调用优化器，应立即终止并记为违反执行范围。

### 7.2 必须通过的 QA 核对表

| QA ID | 通过条件 | 失败处理 |
|---|---|---|
| GEO-01 | 2025 历史站点与负荷 SHA 不变，D11 五母线和 460.73 MW IT 不变 | STOP |
| GEO-02 | 对 3 情景 × 10 年，`Σ_b new_research + D11 == ERCOT_DC_TOTALS.new_IT_MW`，逐年绝对误差 `<1e-4 MW` | STOP |
| GEO-03 | 2026 所有研究新增长地点/容量与原 Epoch 一致（容忍数值舍入），新母线 2026 新增长为零 | STOP |
| GEO-04 | 2027–2035 只有 forecast residual 被重新分配，`LOCKED_VERIFIED` bus/year/MW 不变，未证实内容未被暗中锁定 | STOP |
| GEO-05 | `low/mid/high` 都支持，年度权重归一、非负、无 NaN、每母线符合候选集合；P0/P50 源各自归一 | STOP |
| GEO-06 | 站点来源、ODbL 和 CC BY 版本、矿场排除、去重、边界母线映射可追溯 | STOP |
| GEO-07 | 新增母线存在 POI row，`E0=0` 明确为“没有可证明的新研究权利”，没有新增假 `preapproved` | STOP |
| GEO-08 | 原八母线 E0 原始行、燃气 L1 证据及 2025 已建资产的 SHA 不变；衍生 POI 改变有逐项 delta | STOP |
| GEO-09 | 动态 M4 期望键由研究母线×模型年份生成，故意删 1 键/重复 1 键/增加多余键/错值/两边共同漏键均无法 PASS | STOP |
| GEO-10 | 新母线开发商单一联合模型、所有 BTM 技术、POI、资源共用和燃气 MDQ 约束可构建，且**没有求解调用** | STOP |
| GEO-11 | legacy8 输入与旧检查仍能跑通，新版输入不覆盖旧结果或旧路径 | STOP |
| GEO-12 | 门控 `approved:false` 且未修改批准 SHA；无 S0、S1、S2、S3、B4 求解与新正式结果文件 | STOP |
| GEO-13 | 新配置/新输入文件 SHA 和所选 variant 明确写入更新后的待批准 manifest | STOP |
| GEO-14 | 同一环境重复构造输入两次，除单独日志时间戳外导出 CSV / 静态配置 SHA 相同 | STOP |

关键**输入侧事实检查**：原八母线累计新增 Top3 约占 80%；执行本建议的动态模式，用 36 MW 阈值，候选母线参考约 **17** 个，Top3 累计份额参考约 **50%**。这些只是用于发现明显输入 bug 的诊断值，**不得**通过调权重来强行命中；正式验收依据 GEO-01–14，而不是 17/50% 数字。

### 7.3 最小测试覆盖要求

1. 原八母线回归：8 × 6 = 48 正确期望键，原始历史文件不变。
2. 新增动态模式：保留集合（预期约 17）× 2026–2031 = 动态期望键；低/中/高及 2026–2035 逐年守恒。
3. 原始 Epoch 每年部分母线为零、2026 Shackelford 研究新增长为零的边界测试。
4. PNNL 某情景全为 0、候选母线无 Atlas、某个已核实项目占去当年绝大部分容量、锁定量超过年度总量、负权重、缺失 lat/lon、候选母线不在 ERCOT 时都能正确处理或 fail closed。
5. PNNL Atlas 去重和剔除矿场的可复现性；关闭某单独证据源时可以形成不同测试对照但不会偷偷更改基准。
6. 新母线 `E0=0` 与 `procedural_COD` 的警告表已生成；没有将 PNNL `market_gravity` 得分或 15% 增长率再次乘入 `IT_MW`。
7. 运行门控仍拒绝未授权；没有将 `TECHNICAL_GATE` 或 `FINAL_SCIENTIFIC_USE` 伪造为 PASS。

---

## 8. 交付物与 GitHub 提交规范

执行方必须在分支 `mainline-v13-stageA` 当前最新提交基础上作新 commit，不得强推、不应改 `main`，若有人同时更新仓库先停止并重新对比 HEAD。每次成功提交后回传**实际 SHA**。

建议交付到 `current_work_pckg/`：

```
AIDC_GEO_DYNAMIC_V1_IMPLEMENTATION_REPORT.md
AIDC_GEO_DYNAMIC_V1_DATA_PROVENANCE_AND_FILTERS.md
AIDC_GEO_DYNAMIC_V1_LEGACY_VS_DYNAMIC_AUDIT.md
AIDC_GEO_DYNAMIC_V1_POI_GAS_RISK_REGISTER.csv
AIDC_GEO_DYNAMIC_V1_QA_RESULTS.csv
AIDC_GEO_DYNAMIC_V1_PRE_RUN_MANIFEST.json  # NOT_APPROVED / SOLVER_EXECUTIONS=0
AIDC_GEO_DYNAMIC_V1_RETURN_MANIFEST.md
```

同时交付生成代码、配置、静态输入、匹配测试和对应原始数据复现指引。代码中不存在仅开发者本地可用的磁盘路径，或至少有路径缺失时自动使用仓库已经生成并校验哈希的中间文件的可运行方式。

报告中**强制**包括：

- GitHub 父 SHA、新 SHA、变更文件列表、是否有任何求解器调用（必须为 0）。
- 源数据版本和哈希；37 候选来源并集、Atlas raw/dedup/矿场数、实际候选数及解释。
- `low/mid/high` 的逐年 `ERCOT approval = D11 + locked + forecast` 对账（30 行）和逐母线/逐年权重与容量矩阵。
- 八母线旧版 vs 动态版母线容量图表/表（按 2026、2028、2031、2035；同时报告 2026–2035 累计）。
- POI/E0、燃气 L1/L2、程序最早 COD、PCLR、现场风光等新旧差异；特别列出新增无已批准研究 E0 的母线。
- 旧八母线回归和新动态版 M4 键匹配的通过/失败测试、结构测试数量与结果、门控拒绝日志。
- 更新后的新基准 C0–C5 数据依赖说明：**2025 官方锚定校准优先固定事实，未来新增按本包的可切换地理输入；以后仅在另行批准的求解中使用新版本。**

回报本会话的固定格式：

```text
AIDC_GEO_PARENT_SHA: ...
AIDC_GEO_CODE_SHA: ...
AIDC_GEO_BRANCH: mainline-v13-stageA
AIDC_GEO_STATUS: IMPLEMENTED_NO_SOLVER / BLOCKED
AIDC_GEO_SOLVER_EXECUTIONS: 0
AIDC_GEO_2025_STOCK_UNCHANGED: PASS/FAIL
AIDC_GEO_D11_UNCHANGED: PASS/FAIL
AIDC_GEO_ANNUAL_RECONCILIATION: PASS/FAIL (30/30)
AIDC_GEO_SELECTED_BUSES_MID: <integer>
AIDC_GEO_TOP3_SHARE_MID_2026_2035: <percent>
AIDC_GEO_2026_EPOCH_UNCHANGED: PASS/FAIL
AIDC_GEO_NEW_BUS_E0_POLICY: <summary + caution>
AIDC_GEO_M4_DYNAMIC_EXPECTED_KEYS_2026_2031: <integer>
AIDC_GEO_LEGACY_TESTS: <pass/fail count>
AIDC_GEO_DYNAMIC_TESTS: <pass/fail count>
AIDC_GEO_STRUCTURAL: <pass/fail count; no solver>
AIDC_GEO_RUN_GATE: REFUSED (approved=false)
AIDC_GEO_INPUT_MANIFEST: <path/sha256>
AIDC_GEO_REPORT: <GitHub path>
NEXT_STEP: STOP_FOR_RESEARCHER_REVIEW_BEFORE_2025_C0_AND_ANY_NEW_SOLVE
```

**严禁**只发出“完成 17 个母线”的状态而不交付实际 CSV、测试和版本哈希。

---

## 9. 与官方锚定校准 v1.1 的后续衔接（本包禁止直接执行）

执行完成后，建议下一步序列为：

1. **研究者审查本次无求解器的动态空间输入**：各年守恒、历史继承、Atlas/Projected 筛选和新增 POI 证据风险，批准用于后续的空间分布版本（这不自动等于批准求解）。
2. **官方锚定校准 C0**：使用真实 ERCOT 2025 发电资产、负荷与规划可靠容量锚点核对历史系统；**无求解器**，新地理预测并不改变 2025 事实锚点。
3. **独立审计 C1/C2/C3**：获新审批后，检查安全边界、S0CAL 的正反向同时潮流及净潮流、ERM 首年方法问题，得到与历史事实一致的新基准。不能为了再现 139.58 MW·年提速而调整裕度。
4. **重新验证 S0/S1，再考虑 S2/S3**：对比 old8+oldbaseline、newgeo+oldbaseline、newgeo+newcalibration 的差异。每次实验更改**一个识别维度**，不要同时修改地理、POI 认证、Firm/Conditional Firm 规则和可靠性参数，然后把结果差解释为“空间差异”。
5. **B4/长期路径依赖**：在新基准与空间分配经过批准并获得真实机制结果后，再行授权。

本包不允许执行方擅自打开 ERM、VOLL、S0CAL、公共发电投资、工作负荷或历史基准相关参数；如发现新地理输入导致安全性问题，先生成解释和待批准修正建议。

---

## 10. 执行优先级与停止条件

**顺序：数据源与源记录 QA → 原八母线不可变对照 → verified/projected 分类 → 36 MW 候选集合 → 动态权重与年度守恒 → 新母线 POI/燃气/RE 参数 → 动态模型输入切换 → 48-key 通用化 → 静态/结构/gate QA → GitHub 交付 → STOP。**

必须停止并联系研究者的情况：
- 年度总量与 D11/已锁定增长互相矛盾；
- 需要修改 2025 背景负荷、历史机组/输电或原 E0 资产才能让新地理输入通过测试；
- 发现新候选母线实际上在 ERCOT 以外、映射的原始县界与 network busmap 不一致而无法可靠修正；
- 必须引入新的有物理含义的 POI 规模、审批年份、燃气 L1 批准额度或 Firm 资格来避免延期；
- 代码必须绕开审批门控或启动真实优化才能完成本包；
- 复现的 2025 历史负荷及源文件 SHA 与已保存 B3 输入不同，且无法解释；
- 任何同一文件的同步冲突或用户在执行期向分支推送新的 model/input 修改。

**完成定义**：版本化动态地理输入及配套代码已经进入仓库，已验证 2025 历史不变、每年总量不变、多个母线增加、无求解器门控仍拒绝；所有代码与 CSV 可复现、原八母线 B3 完整保留，已停止等待研究者审批。不存在“已验证新地理 LP 求解成功”之类未经执行的结论。
