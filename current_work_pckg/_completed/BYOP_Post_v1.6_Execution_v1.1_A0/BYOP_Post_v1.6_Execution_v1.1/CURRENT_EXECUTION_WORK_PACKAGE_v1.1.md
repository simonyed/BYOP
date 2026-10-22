# BYOP Post-v1.6：运行可靠性与联合接入裕度执行工作包 v1.1

日期：2026-10-22 | 依据：v1.6 校准结果 + 原 post-v1.6 research basis ZIP + `mainline-v13-stageA` 当前代码。

> **授权边界：仅 A0（零求解器调用）。** A1 的两次小 LP、A2 的 S0/S1、A3 的 S2/S3 均为后续待申请阶段。工作包规定“批准后怎么做”并不等于给予批准；不得绕过 E1 gate 或自行设置 APPROVED。所有执行阶段完成后都要交报告，且在有明确决策点时停止。

## 0. 科学目的及范围

论文要识别新增 AI 数据中心在公共电网接入不足条件下，由私人速度优先供电选择造成的公共扩张反馈与长期路径依赖（S0 无新增研究 AIDC、S1 Grid-Only、S2 自主 BYOP、S3 社会协调，以及 S3_mS2 matched-service）。本阶段不做多组敏感性、不优化技术参数来生成预期结论、不直接启动 2050 控制器。先在真实地理映射支持的 **TAMU ERCOT 合成 64-bus / 162-line** 网络与 16 个 dynamic_pnnl_v1 研究母线上建立可信的一致接入能力规则。保持连续 LP，不添加 MILP 或伪装成真实 ERCOT 行政并网承诺。

本包暂不改变 2026–2031 的研究 AIDC cohort、2025 inherited 460.73 MW IT ramp、PUE、POI 位置、BYOP 技术/成本/天然气代理及 S2 speed-first 规则。除明确列出的可靠性、传输及基线接线以外，不做其他功能扩张。

## 1. 输入冻结、版本和实验口径

### 1.1 已完成 v1.6，禁止重做
- 仓库 Git 分支 `mainline-v13-stageA`；审查时 HEAD：`0b417903c7704c00de609581646fed29723397cf`。代码 commit `85cd6ae596e0af10692a2ecf65a000ae78b32bf1`，报告 commit `0b417903...`；`current_work_pckg/CALIBRATION_CLOSEOUT_REPORT.md` 为权威校准报告。执行前重新验证 SHA 与分支，任何漂移先做代码差异审计。
- 2025 原始年度负荷 488.23358 TWh；2025 active fleet 155,446.9 MW，较旧版 +396.3 MW（风 +249、储 +300、光 −152.7）。Gaia 入 2026 committed；Kiamichi 和 Tenaska Gateway 各独立机组组、按 2025 月度 MORA 上限限制 dispatch 及 ERM credit 一次。
- v1.6 LP1：18 条线热限额 `s_nom` +5,151.8 MVA；固定未经校准的 `x/r`；LP2 重新读盘固定资产检查 exact optimal。LP2 EENS=111.79 MWh、最大缺口 27.19 MW，集中 p620 Far West；这些通过的是研究 proxy 容差，**不是零切负荷或 N-1**。
- 官方 2025 预测 PRM：18.8989% / 10.4718%，模型按相同官方 firm load 比较：14.90% / 7.37%；同口径差异逐类桥接完成，但 thermal +4,000.1 MW 差额未充分解释，DR/PUN/RMR/DC ties 等有遗漏。**禁止为命中官方 PRM 而调机组、负荷、ERM 或虚构资源；不得宣称该差额已经全部解释。**
- West Texas Export Interface 未再现官方向外拥塞（模型西部边界出向未 binding），其他官方约束有合成聚类/缺停机序列的可辨识边界。将此作为用于选址/线路机制的**区域有效性限制**，不再以无数据支持的 TL 升容进行拟合。若结果高度依赖西部接口，必须报告或阻断地理结论。
- 网络在 L2（不在 Git）：`workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`，预期 SHA256：
  `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`。
  仅当 hash、路径、bus/line 数量、机组 cap、x/r、s_nom 同 v1.6 manifest 相符才允许参与 A1。**不得以原 baseline_2025_tamu 旧路径回退。**

### 1.2 事实与假说分开
- 2025 主实验截面是**年底机组存量 + 全年 2025 负荷/模型资源曲线**的合成规模及供电压力测试，不是逐月 COD 的历史运营回放。模型已有 3h 天气/负荷标签可能落到 2030 年；原数据窗口按 **2025 source HE** 识别，不可直接视为一致的当地小时、UTC 或同气象年实绩。
- ZIP `derived/ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv` 8,760 行、`3H.csv` 2,920 行，`derived/PRE_REGISTERED_STRESS_EVENTS.csv` 等数据可用于事件选择/负荷验证，**观测风/光=实际产出（含弃电），不是未弃电 `p_max_pu` 或 nodal 真实潜力**。2023–2025 PG7-126-M 与 settlement/Native 数据存在已登记口径差异，不可静默混用。
- MORA 边际分位数只能定义有来源的确定性压力范围，不能合成联合概率或 LOLE。ELCC 只作官方信用/横向检验，不乘进逐小时资源可用出力并再扣一次。

## 2. 现有代码实况及必须解决的三个错配

1. `workflow/byop/model/rearch_mech.py` 的 `BASE_TAMU` 默认仍指向 `baseline_2025_tamu/...`；代码虽已有 CLI `--base`，`workflow/byop/run/run_mainline.sh` 的 `COMMON` 尚未传这个参数。v1.6 YAML 中 `inputs.baseline` 并**不会自动重定向**模型。新增运行入口必须显式传递且校验 L2 v1.6 路径及 SHA，禁止 fallback；批准前 DRY 必须显示完整 `--base`。
2. `run_mainline.sh step0` 仍会运行 `--calibrate` (ERM-02 B 自校准) 和 `--s0-calibrate` (2026 以后免费公共网络基线补强)；后续 `pilot_s01` 的 `$CAL` 继续传旧的 `--erm-cal` 与 `--s0-cal-file`。**新的研究主线应禁用这两种未来免费/内生要求；历史 2025 v1.6 `s_nom` 修复独立保留**。修改成新增、默认拒绝直接求解的 post-v1.6 入口，不能将旧 `step0` 改写成“已批”。旧入口保留供历史复现，不允许被误用为新主线。
3. 现有 E1 `mainline_gate` 读取 manifest 中 `code_sha256` / `inputs_sha256` 并检查部分 Git 文件；v1.6 prepared manifest 尚非具备完整 code/input SHA 的正式 pre-run manifest，其 `baseline.sha256` 未在入口检查。必须增强 gate：对 `--base` 实际使用文件算 SHA，校验配置文件、研究源数据、主要源代码/运行脚本、参数来源，核对 approved SHA / 工作树清洁，锁定 stage 和 solver budget。未经研究者批准的 LP 即便由新的脚本发起，也必须被拦截。

**其他需要代码审计，不可假定已经实现：** 旧每快照 15% energy-backed ERM 具体从哪个回调注入、储能 shadow-SOC 是否与调度 SOC 混合、旧 no-harm 的 S0 每母线每快照对齐、2026 committed TPIT 项目是外生预承诺还是本轮新投资（必须记录成本/建设周期）、既有 3h B7 stress 与新 1h 压力 LP 是否相互覆盖。写出精确函数/行号/约束名与去留表。

## 3. 下一阶段采用的物理可靠性规则（首选研究代理，不冒充官方认证）

### 3.1 备用要求的初始版本
- ERCOT 全系统 2025 联合裕度/连续压力示范：**运行上调备用 R=3,000 MW**，持续时间 **τ=1 h**，先作为研究代理测试零 AIDC 基线是否可行。来源边界见 `PARAMETER_CANDIDATES.csv`、官方 ERCOT ELCC Study 附录；这不是 ERCOT 硬性规划 PRM、不是 LOLE，也不能把所有未调度火电视为已在线备用。
- 为保持 A1 的模型对照一致，**2026–2031 先采用固定外生 3,000 MW**，不由当期系统最优可达到的最大 ERM 反推、也不随 AIDC 增长内生下调。4000 MW 仅保留为后续有界敏感性候选；**本阶段不执行**，不为了 BYOP 获益而批量扫描备用值。2050 长期轨迹如何外推属于下一阶段，暂不预先规定其为官方规则。
- 关闭未来主情景旧 `ERM-02 B` 最大裕度自标定；旧 15% snapshot ERM 不得再作为另一个同时约束的隐形安全门槛。若将其保留作诊断，必须从正式目标及可行性约束中清楚分离；新规则能否取代整个 Shadow-ERM 结构须由 A0 的约束清单及静态测试确认。

### 3.2 备用可交付性与 LP 正确性
- 为每个压力时点明确外生可用出力、允许提供备用的机组集合、爬坡/响应时限。机组 `0 <= r_g(t) <= max(0, p_nom*g_avail(t) - p_g(t))`，还须加逐时 ramp/eligible 上限；禁止把未必能启动的全体离线机组自动称为在线备用。无 UC 二元变量时，应给定透明的 eligible 假设与保守界。
- 储能的备用功率/持续时间与**同一调度 SOC** 耦合，按效率扣除 τ=1h 能量，并计入当前调度已占用的功率及能量；禁止独立 shadow SOC 重复使用电量、禁止同一储能为 Firm/AIDC/备用多次认领，既有 LP 充放电同时发生须记录并做 reserve-credit 审核。维持 LP，不能偷偷加入充/放互斥 MILP。
- `Σ eligible reserve >= 3000 MW` 是系统 aggregate reserve，仅有这行不代表网络可送达。资源-网络 LP 如称网络可交付，应有预定义备用部署/再调度的电网物理检查，或明确标为“**满足系统备用条件下的负荷网络可送达性**”，不能标成 N-1/可交付备用。如果 A0 无法在当前 LP 内合理实现同时部署，明确降级为后一种表述并列出缺口，不虚报。
- 现有不可中断用户优先满足，不能把模型中的 `load_shed`、未来未交付计算任务或合同中断作为运行备用资源。不同 scenario 统一备用、气网、POI、上行及时间窗口。Firm/Conditional Firm 权利仍需联合排重，Conditional 不能无条件算作 Firm。

## 4. 事件/时间与输入契约

基础压力事件按原 ZIP 已预登记且**不依赖 BYOP 结果**：
- 2025-08-18：夏季最大 Native Load HE18 与同日 HE21 的夏季最大观测残余负荷；**同一个 72h 窗，不重复算两组独立样本**。
- 2025-02-20 HE08：冬季峰值暨全年观测残余峰值；72h 窗。
- 2025-07-30 HE21：与夏季最大负荷事件窗口不重叠的高观测残余负荷事件；72h 窗，作为有限的留出检查（**非完全未参与 v1.6 年度基线拟合的样本**）。
- 高净负荷爬坡、低风高负荷两个数据窗口只作后续诊断，不自动增加求解。

A0 生成 `STRESS_SOURCE_VINTAGE_QA.json`：每小时源行/HE/DST、日期、模型 snapshot、区域负荷拆分、需求口径、风光“观测出力 vs 反事实可用率”来源、所有功率/能量单位、是否真实同气象年。任何重采样按能量守恒，无凭空补造春秋 DST 小时。

连续压力 LP 使用**1 h 原始连续源行**、物理连续储能 SOC；与旧年度 3h LP 分开做，不把 3h 代表时点的现有切负荷直接当作新的逐小时允许缺口。联合接入测试同一组时段在全部目标母线同时施加相同规模参数。既有客户的不服务量必须单独报告；出现可靠性代理导致的零新增需求不可行，返回 `BASELINE_PRESSURE_INFEASIBLE`，不归责于 AIDC、不补造应急资源。

## 5. A1 的联合接入能力计算：只有**两次**授权后小型 LP

先固定 **同一** v1.6 资产、2025 源时序、备用户池/3 GW 要求、SOC、保护现有负荷以及负荷增加的空间权重：

令 16 个研究 AIDC 母线的新增设施取电 MW 权重为 `w_b >= 0, Σw_b=1`，由 `dynamic_pnnl_v1` cohort 的 request / facility-power 需求直接构造，不把 IT MW 与设施取电 MW 混算。`h_b=λ w_b, λ>=0`；三个压力窗口的同一 `λ`、每窗口可分别调度，求最大的可共同承诺 `λ`。若全年 cohort 为 2026–2031 多年期，A1 使用明确的 2025 基线/第一阶段压力切片，不能冒充所有未来年度额度。

**LP-R `H_resource`**：在相同资源、可靠性、需求及 SOC 条件下，解除内部输电热限额/网络瓶颈（经审计的铜板系统或等价无阻塞连通模型），但不能移除系统机组可用率、总出力与备用、储能时序约束；所有母线仍共同决定一个 λ。不要错误地删除潮流线路但保留会令各 bus 孤立的节点平衡。

**LP-N `H_network`**：完全同一输入恢复固定 v1.6 网络的 DC 潮流与线路限额，没有新建电源/储能/网架、没有隐形 S0CAL、没有模型可变资产容量，求同样 λ。必须验收 `H_network <= H_resource + numerical_tol`；否则先查口径/松弛集是否不同。

不把每个 bus 单独算出的最大值相加，不通过 re-siting 改变固定 `w_b` 以人为放大能力，不用官方 PRM 比例直接分摊到母线。两个 LP 均须完整证明在 λ=0 时既有负荷与 3 GW 代理能够独立可行；若任一 LP 最终 infeasible，保存 IIS/约束残差/差异原因，停止，不第三次补救 LP。

**POI 为第三本账，但默认不再加第三个 LP**：用 `GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv`、`GREAL_POI_E0_SCHEDULE.csv`、COD/升级合格性及 firm/conditional 资格计算 `H_POI`，显式报告现有资格、未来升级可交付的区别。对固定权重可算 `λ_POI = min_{w_b>0}(eligible_POI_b/w_b)`（仅在权利均为独立确定上限且网络条件不变时适用）。零值可能由 POI 未获资格造成，不代表全系统无物理资源。若 POI 与升级/合同交付相互耦合，提交方案审批后再决定是否加联合 LP；本阶段不得虚称“3 次 LP 已全部授权”。

A1 的输出不叫“真实 ERCOT 可接入裕度”；叫“合成网络中指定 AIDC 分布和压力约束下的联合接入能力”。西部 export 未校验的局限必须标出，至少输出各目标 bus 的约束、对应 zone 与主要线路影子价/接近约束的小时。

## 6. 对未来公共扩张和情景主线的具体保护

**历史已修复 ≠ 未来免费扩张。**冻结 2025 v1.6 热限额及当年已存在资产；禁用旧 `ERM-02 B -> S0CAL` 流程所产生的“自适应免费补网”。2026+ 新线路/电厂需有显式投资成本、COD 及部署地；已承诺 TPIT/PBRP 必须登记来源、真正承诺时点、物理容量、可用年份与账本口径，不能把模型自身生成的救火线路写作 2025 沉没资产。S0–S3 对历史存量、公共管线、运行备用、背景负荷和研究 AIDC 申请使用同一个物理集。

A2 以后才恢复 S0/S1_EARLIEST，另保留原已实现的 `S1_ECON` 经济对照作为代码/结果检查，不因 Grid-Only 自己少交付就宣称 BYOP 带来的社会节省。A3 才恢复 S2 speed-first 与 S3/S3_mS2 的 matched-service；必须证明企业自主投资通过公共容量扩张、时滞、复用或冗余资产反作用于系统，不用大量旁支敏感性替代主线。2026–2050 持续控制器、2036 后零新增长期追踪不是 A0/A1 任务。

## 7. 具体阶段与可授予权限（顺序不可交换）

### A0：现在唯一可执行（零 LP 调用）
1. 核对 GitHub HEAD（审查时 `0b417903`）、工作目录、L2 的 `nc` SHA；无法访问 L2 只能交“未验证”说明，不猜测成功。打印旧 Git manifest 相对实际文件的 SHA 差异；旧 manifest 仍 `NOT_APPROVED`。
2. 读取 `CALIBRATION_CLOSEOUT_REPORT.md`、固定资产 QA、PRM bridge、线路 direction report；输出 `POST_V16_A0_RECONCILIATION.md`（逐条关掉 v1.6 需要关闭的事项，未关项只作说明）。将这份包的 `raw/`, `derived/` 放置在新的、不可混淆的 data staging 目录，校验来源 SHA。原始研究数据的 `build_research_data.py` 可选**本地重建或读入检查**，但不更改官方原文件。
3. 完成模型约束审计 `BASELINE_AND_RESERVE_CONSTRAINT_INVENTORY.csv`，对旧 shadow ERM/ERM-02、自适应 S0CAL、储能 SOC、no-harm、Firm/Conditional、POI、旧 3h stress、气网 MDQ、future TPIT 的位置、启用条件、权利重计风险标注。明确哪些删除、替换、保留为只读诊断；未通过此步不许修改可靠性方程。
4. 新建**隔离的 post-v1.6 配置和入口**（不可覆盖既有可复现旧情景）及 `--base` 贯通；在每个 solve 入口强制预期 `.nc` SHA 与输入/代码 manifest 校验并保持 E1 NOT_APPROVED。旧 `step0` 不能静默用于新版；新入口 `DRY=1` 应显示**不带** `--erm-cal`、`--s0-cal-file`、`--calibrate`、`--s0-calibrate` 的命令。防止旧代码在默认参数下把 15% ERM 作为隐形重复约束。
5. 构建新**1h 连续压力** LP 代码及上下限约束（保留 PyPSA/linopy LP），以及未来独立备用参数、两种 λ 目标、POI 分账函数；完全通过 mock/合成小网/变量约束检查而**不调用 Gurobi 或其他优化器**。单测至少覆盖可用率、热机 ramp、储能同一 SOC 供能、排重、零新负荷保护、16 bus 权重单位、铜板网络、线路约束恢复、动态选址不可变、source HE/DST、2025 基线 SHA、错误 base 拒绝、旧 step0 拒绝、未批准 solver 拒绝、旧回归。
6. 不执行优化。返回 `A0_IMPLEMENTATION_REPORT.md`，`A0_RETURN_PACKAGE.zip`，完整 commit SHA、文件清单/校验 hash、`git diff`、全部静态测试与警告、准确 DRY 运行命令、A1 **最多 2 次 LP** 的节点数/变量数预估及预期资源时间（只能估计供批示，不能说已运行）；等待研究者批准新的配置和 SHA。若做不到真实连续 LP 或正确备用排重，退回 `BLOCKED` 附具体函数/限制，不擅自降级主结论。

### A1：研究者单独批准后（预算最多 2 次 LP；0 自动重试）
按同一 SHA 依次运行 LP-R（系统资源铜板）和 LP-N（固定网络）；若前者不 exact optimal 或零 AIDC 不可行，停止，未获批准不得再尝试。输入/方法必须同 A0 冻结。输出 `JOINT_HEADROOM_RESOURCE_NETWORK.csv`（λ MW facility, λ MW IT 另列）、`HEADROOM_BY_BUS.csv`、`POI_ELIGIBILITY_LEDGER.csv`、`STRESS_DISPATCH_RESERVE_QA.csv`、`HEADROOM_SOLVE_LOG.csv`、`NETWORK_PRESSURE_DIAGNOSTICS.csv`、`A1_EXECUTION_REPORT.md`、manifest（包含所有版本、solver 状态及结果）。要求 exact optimal 与完整电/能量/约束残差、完整服从无切负荷保护，出错只报告 `BLOCKED`，无第 3 次。

### A2：另行批准，仅 S0/S1 主线
审查 A1 结果和目标母线空间真实性后，使用冻结新版共同物理条件执行 S0 + S1_EARLIEST 的最小对照；未来已承诺公共项目与新建计划分账，详细报告延期、既有用户切负荷、投资及 line/POI constraints；**不开展 attribution 多场景、不启动 S2/S3**。求解数/成本/时间计划须先独立审批。

### A3：另行批准，仅核心 S2/S3 比较
在 A2 正常且 Grid-Only 产生有物理原因的延迟后，执行 S2, S3, S3_mS2，在 same-service 基础上评价私人速度优先与社会协调的路径差异；不纳入大量 tech/price/gas/offgrid 无边界扫参。是否延伸 2035–2050 再议。

## 8. A0 判定条件（硬门槛）
- 基线实际 SHA、v1.6 asset caps、现有/ committed 集合及线路 x/r/s_nom 与报告一致（若 L2 不可达，标记 `BLOCKED_ON_L2_BASELINE`, 不申请 LP）。
- 新 CLI / YAML / gate 真正使用 v1.6，而不是只改 config 的 `inputs.baseline`；manifest 含 baseline 文件完整 SHA，inputs/code SHA；未批准求解保持禁止。
- 旧 ERM-02 / free S0CAL 不会通过旧脚本参数或默认配置悄然带入新主线，旧回归仍能在旧配置下运行。
- 1h 连续压力、3GW reserve、1h SOC、λ 固定 16bus shares、铜板+输电两模型只是新建**可生成**的线性模型，静态约束检查充分；任何 mock 求解器/solver 都不得在 A0 被调用。
- 所有结果表明确 MW facility / MW IT、model vs source date、reserve vs PRM vs ERM、modelled vs official、pre-2026 vs future capital commitments 及 unknown-data flags。
- `git diff`, tests, staged data QA, DRY, manifest, unresolved issues 和回包完备；状态 `READY_FOR_A1_APPROVAL` 或 `BLOCKED`，不能自称 S0/S1 ready。

## 9. A1 科学验收条件（只有 A1 批准后使用）
- 两 LP `status=ok` 且 `termination=optimal`；相同客观可行集除输电松弛以外；`0 <= H_network <= H_resource + tol` 且共同 AIDC 权重逐 bus 等式满足。禁止将“去掉网络约束”意外变为节点孤岛。
- 所有既有负荷享有相同的时序/备用保护，无新增服务时若失败则清楚归类基线/代理风险。不能容许主情景人为提高既有客户负荷切除；同时披露 v1.6 2025 3h 的 111.8MWh 与新 1h 基线不可直接比较。
- 有据可查的 3GW 系统备用户池、热机出力+备用容量信用唯一性、储能 SOC 真实能量和时长、无过多双计、所有不等式残差与关键时段曲线；若未实现备用网络部署，不声称应急备用可交付或可靠性认证。
- 受 v1.6 西部接口与 4GW thermal basis 不确定性的影响独立说明；不可把 A1 数字发布为真实 TX 母线官方 interconnection capacity。
- 一次次执行有 solver call 计数、日志、版本/校验；成功后只提出是否进入 A2 的具体申请，不自行跑 S0/S1。

## 10. 明确不得做
- 不更新历史官方源文件，不扩张或修改 2025 v1.6 thermal baseline 来取得更大 headroom；不得自称做了真实年度 2025 调度复制。
- 不用官方 PRM 18.9/10.5 作硬约束，不加虚构 DR/PUN 容量；不将 2025 MORA 分位数称为联合可靠性轨迹或用观测风光直接当潜在出力。
- 不做每 bus 独立 headroom 后求和；不把 15% ERM 与 3GW 新备用重复强制；不在未充分审计下无偿扩建 S0CAL。
- 不修改 `run_authorization`、不自动重试、不得提前跑 `step0` / `pilot_s01` / `pilot_core` / attribution / national / 2050。
- 不因新的 3GW 测试碰到零新增负荷 infeasible 就偷偷提高机组可用率、替换负荷、放松备用或引入未记录容量。

## 11. A0 固定回报模板
```text
EXECUTION_STATUS: READY_FOR_A1_APPROVAL | BLOCKED
BRANCH_AND_START_HEAD: ...
CODE_COMMIT_SHA: ...
V16_NC_PATH_AND_SHA_VERIFIED_ON_L2: ...
SOURCE_AND_DERIVED_DATA_SHA_QA: ...
BASELINE_2025_FROZEN_AND_LIMITATIONS: ...
ERM02_AND_S0CAL_LEGACY_DISABLE_AUDIT: ...
NEW_RESERVE_MODEL: 3000 MW, tau=1h, eligibility/ramp/SOC/network-claim definition
STRESS_VINTAGE_AND_DST_QA: ...
H_RESOURCE_VS_H_NETWORK_STATIC_FORMULATION: ...
POI_ELIGIBILITY_SCOPE: ...
SOLVER_CALLS: 0
TESTS_PASS_FAIL_SKIP: ...
DRY_COMMANDS_AND_EXPECTED_A1_SOLVE_BUDGET: ...
GATES_AND_UNRESOLVED_BLOCKERS: ...
DELIVERABLES_AND_SHAS: ...
NEXT_RESEARCHER_DECISION: approve or reject A1 after reading artifacts
```

## 12. 后续工作的原则

本阶段优化的目标是能解释反事实的**可接入能力与速度延迟机制**，而不是寻找让早期 BYOP 看起来获利的安全裕度。只有 A1 证明新规则有物理意义，并且 A2 证明 Grid-Only 的延迟不是建模错配，才值得开展长期路径依赖的 S2–S3 科学结果。任何未解释的网架/POI 空间局限需要随结论同报，而不能在方法段省略。
