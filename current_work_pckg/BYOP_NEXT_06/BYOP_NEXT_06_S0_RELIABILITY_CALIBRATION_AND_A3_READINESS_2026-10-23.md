# BYOP NEXT-06｜ERCOT S0 基准可靠性校准、S0/S1 复验与 A3 门禁准备

**版本**：v1.0｜2026-10-23（America/New_York）  
**交付对象**：Codex / Claude / 其他有 L2、GitHub、PyPSA-USA 项目访问权限的执行方  
**仓库**：https://github.com/simonyed/BYOP  
**开始基点（执行前须重新核实）**：GitHub 默认 `main`、`mainline-v13-stageA` 和 L2 均为 `e3544cd7`；本轮已求解代码冻结 SHA `cdfdea06146a6fe73df89cb410d6a88cb5fda306`。  
**论文依据**：`论文顶层设计.md`，四个主情景 S0 / S1 / S2 / S3，重点是 Speed-to-Power、公共扩张反馈、长期路径依赖和私人—社会协调差异。  
**唯一目标**：把 S0 从“优化器技术 PASS，但 2026 年可靠性异常尚未解释”推进到**有科学依据、可复现、可审计的公共电网反事实基准**；在此基础上确认 S1 是否需成对重跑，并准备 A3。不要另设复杂敏感度矩阵。

> **执行总令**：集中执行下列 **W1、W2、W3 三个工作**。优先投入精力解决 S0，不为达到某个事先希望的切负荷量而修改模型。充分使用已经求解出的数据，**W1 严格零优化器调用**。只有 W1 找到具体、可证实的修正理由，W2 才允许进入必要的重新求解审批/执行。W3 暂为静态建设，不得因还有历史夜间调用预算而提前启动 S2/S3。

---

## 0. 已验证的起点、冻结证据与不能误读的数值

### 0.1 已完成且禁止擅自重跑的原始算例

| 对象 | 当前事实 | 解释边界 |
|---|---|---|
| A1 LP-R | `ok/optimal/PASS`；`H_resource=2,587.772185 MW facility`，约 `2,253.37 MW IT` | 16 研究母线特定权重分布、固定资源、铜板输电的接入裕度，不是 ERCOT 实际公布的 headroom |
| A1 LP-N | 固定 2025 网络、零既有用户切负荷和 3 GW 备用下 **INFEASIBLE** | `H_network=NOT_AVAILABLE`，**绝对不是 0 MW**；不能直接由 LP-R 单个潮流解判定线路 IIS |
| S0 | `ok/optimal`、0 整数；技术门禁 PASS；缺供 `54,205.7791 MWh`（2026–2031 各年度加权量之和） | 其中 2026 年 `51,049.2775 MWh`，主要 p620 6 / p620 7；科学可靠性门禁待审查 |
| S1_EARLIEST | 技术 PASS；`54,007.7697 MWh` 既有用户缺供；相对 S0 保留 SHA 固定的逐单位/快照 no-harm | S1 的既有用户保护并不意味着 S0 本身已经可靠 |
| S1 速度缺口 | `590.7426 MW-IT-years / 11,425.9710 MW-IT-years`，集中 2026–2028 | 是 S2−S1 的速度改善基准，受 S0/S1 一致性及 POI/COD 假设限制 |
| S0/S1 调用 | 2 情景父尝试 / 3 顶层优化器调用；均已耗用、零重复 | 原结果、台账、SHA、日志不能清空或复用 |
| A3 | 未执行，0 调用；缺独立门禁、调用登记与完整 S2/S3 同可行域审计 | 不得把过去 A2 许可继承给 A3 |

**原始结果关键路径**：

- `current_work_pckg/OVERNIGHT_EXECUTION_REPORT.md`
- `current_work_pckg/S0_S1_MAINLINE_FINDINGS.md`
- `current_work_pckg/S0_S1_MAINLINE_COMPARISON.csv`
- `current_work_pckg/A1_RERUN_EXECUTION_REPORT.md`
- `current_work_pckg/S0_S1_EXECUTION_REPORT.md`
- `workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1/S0_RESULT.json`
- `workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1/S1_EARLIEST_RESULT.json`
- `workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1/S0_shed_by_snapshot_frozen.csv.gz`
- 同一输出目录下 `A2_SOLVE_LOG.csv`、`A2_OPTIMIZER_CALL_LOG.csv`、`S0_NO_HARM_REFERENCE.csv` 及原有汇总产物。

**数据持久化原则**：某些 `.nc` / `.csv.gz` 只存在于 L2，GitHub 找不到不代表不存在。执行方应在 L2 查验实际文件并记录路径、字节数和 SHA-256。不要因文件未跟踪就虚构新结果或重新求解。

### 0.2 特别重要：先核对历史 2025 基准之间的**口径差异**

过去报告中“原始 2025 校准只切负荷约 102–112 MWh”**不能直接成为 S0 校准的硬目标**。已有 `current_work_pckg/_completed/BYOP_C0_Repair_C1_Diagnostics_v1.4/C1_FIXED_ASSET_DIAGNOSTICS.md` 记载：

- 早期**可扩张线路的校准 LP**约 `102.2 MWh`；这是带有线路容量决策及高额缺供惩罚的校准问题；
- 早期 C1 使用**保存后的固定资产、固定线路网络**做 2025 全年 3 h 调度，曾得到 `72,905 MWh`；该报告还指出新增容量时可能改变了 18 条线路的 `x/r`，从而改变潮流分布；
- **早期 C1 与最新 v1.6 的网络版本也不应直接当成同一个文件**：C1 报告有 +4,993.9 MVA 的历史资产口径，而后续 v1.6 A1 验证记录的 uplift 为约 5,151.8 MVA。必须按实际基线文件、SHA、生成脚本及资产清单核对。

因此，本次必须把三种实验分开：`历史可扩张校准 LP`、`历史 C1 固定网络全年调度`、`最新 v1.6 固定网络 + 2026–2031 多年规划 S0`。分别核算模型拓扑/阻抗、机组、储能、负荷、时段、备用、缺供惩罚、投资和 COD，**不得以数值接近或相差多少作为唯一校准成功标准**。

### 0.3 严禁的“调好 S0”手段

不得：添加没有数据支撑的免费传输容量、重新打开 legacy `S0CAL`、暗降 3 GW 备用、删掉 2026 年短缺快照、把数据中心/Native Load 移到另一母线、虚构已有机组或气源、降低 VOLL 强迫模型不报告缺供、篡改 COD、移除已经同意的 SOC 约束，或者把 `no_load_shed=False` 偷改成 PASS。

**校准的含义是提高物理和证据一致性，不是让切负荷数字自动逼近零。**

---

# W1｜S0 异常缺供的只读归因与基准核对（最高优先级、0 optimizer calls）

## W1.1 冻结证据与数据对账

在执行时的统一主线记录 `git rev-parse HEAD`、求解代码 SHA、基线 `.nc` SHA、A2 manifest、两个求解父子台账及 `S0_RESULT.json`／`S1_RESULT.json`。原始 S0/S1 目录只读，建立本轮专用产出目录，例如：

`workflow/results/BYOP/next06_s0_diagnostic/`

用原始 S0 `S0_shed_by_snapshot_frozen.csv.gz`（68 列、816 行的期望结构应由 `S0_RESULT.json` 及索引实际核对）反算：

1. 按 model year × bus × 原始 3 h snapshot × sampled week / inserted stress event 输出**未加权 MW、物理持续小时、代表权重小时、加权 MWh**，并且精确对齐原始双层时间索引、压力事件名和源 2025 HE 标签；
2. 逐年和跨年加总，必须还原当前约 `54,205.7791 MWh`，2026 年约 `51,049.2775 MWh`；差异超过明确的数值舍入容差时 **DATA_QA_FAIL**，先修复统计程序，不改模型；
3. 特别核对 `p620 6` 的约 `32,052 MWh`、`p620 7` 约 `16,250 MWh` 是在怎样的少数快照产生，而非假设每小时都存在同等缺电；核对 2026 年的最大缺供 MW、发生快照数量、连续小时和对应负荷 MW；
4. 把原生 `native_background_unserved` 与 `inherited_ramp_unserved` 单独拆分：当前总量几乎全部为 Native Load，继承 ramp 贡献极小，不得把问题无证据地归咎于新增数据中心；
5. 只读复核 S0 与 S1 共用的基础负荷、线路、Committed 项目和压缩文件 SHA。保留 S0→S1 no-harm 文件和每列的 SHA 对照。

**特别检查代表性时段加权**：当前代码 `rearch_mech.py::ml_base_build` 对未额外插入的 sampled-week 快照把剩余全年小时均摊，而额外插入的压力快照通常权重为实际 `3 h`；储能 `stores` 步长为 `3 h`。对于每个模型年，报告：

- 各类快照数量、权重范围、权重和是否为 8760 h；
- sampled-week 中是否与 B7 压力事件重叠，是否有实际压力快照仍获得接近 **77.6 h** 的年度代表权重；
- 原始 3 h MWh 与加权年化 MWh 的区别；最大 10 个快照对总缺供的贡献率；
- 若少数离散缺供被较大代表权重放大，说明该权重能否代表 ERCOT 2025 一整年的类似时段频率，**不能只报告一个加权总量**。

**必交**：`W1_S0_SHED_BY_BUS_YEAR.csv`、`W1_S0_SHED_SNAPSHOT_WEIGHTS.csv`、`W1_S0_TOP_SHED_EVENTS.csv`、`W1_S0_RECONCILIATION.json`。

## W1.2 2025 基线谱系（lineage）和 apples-to-apples 核查

从最新 `.nc` 及其生成链，以及历史 C1/X1 文档与已保存结果出发，制作统一的 `W1_BASELINE_LINEAGE_AND_COMPARABILITY.csv`，至少比较：

- 2025/2026 年母线、线路、总线路容量、**每条关键线路的 `s_nom` / `s_max_pu` / `x` / `r`**；重点 p620 6/7 周边、历史 uplift 的 18 条线路及 A1 指示的 TL129、TL120、TL117、TL104、TL133；
- 资产 status、online year、retirement、发电/储能 MW、可用率、固定/可扩张状态、是否被重新导入；
- Native Load 的原始来源年份、母线映射和 2025→2026 继承方式；核对 `MAINLINE_INHERITED_RAMP_2025.csv` 有无重复计入，分清已有用户与本研究新增 AIDC；
- reserve / operating margin、SOC 边界、时间分辨率/采样和缺供 VOLL；
- 最关键：**历史可扩张 LP 的 102–112 MWh、历史 C1 固定网络的 72.9 GWh、最新 S0 2026 的 51.0 GWh是否分别有同样的可行域和时间/年度口径**。找不到完全可比参照时明确写 `NOT_COMPARABLE`，不得拟合一个低数值。

若存在同一条既有线路既提高容量又对 `x/r` 按比例缩放，而构建线路数量/电抗并无相应现实证据，应标为 `TOPOLOGY_OR_IMPEDANCE_REVIEW_REQUIRED`，而非当作物理上无可争议。**先用现有文件核查，必要的独立反事实仅在 W2 受控求解中使用。**

## W1.3 Far West 缺供的物理定位（不重新优化）

以 `p620 6/7` 为中心建立短缺瞬时“资产可交付台账”。从原 S0 结果、基线 PyPSA 网络、已保存扩张 ledger、COD/audit 和时段数据恢复以下事实：

1. 每个关键 bus 的 Native Load MW、保留机组/储能、实际可发 MW、进口方向线路、上下游邻接 bus；用实际潮流输出时才描述线路拥塞，**不能从 LP-R 非唯一潮流超限直接声称 LP-N IIS**；
2. 关键固定线路 `s_nom×s_max_pu`、`x/r`、是否同期有已承诺线路及公共扩建；每个工程的审批、2025 存量、COD 和当年可用快照；
3. `DWB_Stage_2` ISD 为 2026.49，PBRP-765-A/B 为 2031/2031.5（模型代理）；检查 2026 年以“全年可用”还是“全年不可用”近似半年度 COD，避免遗漏或提前交付；PBRP 不能被拿来无依据填补 2026 年；
4. 同母线及周边发电运行约束（p_max_pu、停役、燃气供应代理、机组输出/爬坡）；储能充放电与 reserve 是否在同一短缺时段限制可用电；
5. 2026 年没有新建公共资产可及早 COD，是**规划工期的真实结果**还是候选资产 build-year/activity mask 配置问题；核对被排除的已宣布/在建项目及其公开依据；
6. 尽可能从原 S0 输出定位线路流量；**若没有这些流量或 SOC，不得伪称已经证实具体流量约束**，仅给基于拓扑、容量、shed 和最优解其他导出量的有条件诊断。

**必交**：`W1_FAR_WEST_ASSET_DELIVERABILITY.csv`、`W1_FAR_WEST_BOTTLENECK_EVIDENCE.csv`、`W1_NATIVE_LOAD_MAPPING_QA.csv`、`W1_COMMITTED_PROJECT_COD_QA.csv`。

## W1.4 最小因果分类与证据等级

每项怀疑的主要原因给出**一条**可证伪的事实或检查方法，按以下类别登记，不重复罗列主观可能性：

| 原因类型 | 需要证明什么 | 允许的下一步 |
|---|---|---|
| **D：数据/拓扑错误** | 线路容量/阻抗、资产状态、负荷地理映射、双重计量、编码或单位确定有误 | 有证据则在 W2 修复同一公共输入；重新验证 A1 可比性 |
| **T：时段代表性错误或不可辩护的外推** | 少数周被过度赋权；重叠快照重复、时间权重错误或样本代表不足 | 修订采样/权重需预注册的年度代表性依据，不能为删除缺供时段选样 |
| **C：COD / committed 项目错误** | 已承诺工程被漏建、迟建、提前建或年度可用性错判 | 依据可查的资料修正承诺资产，保持所有 S 情景一致 |
| **P：物理上真实的过渡期缺电** | 数值、时空、资产与建设时滞都可解释，未检出 D/T/C 问题 | **保留并标注**；不可为了低 shed 加免费容量或掩盖；科学使用门禁另作决定 |
| **M：方法近似** | 3 GW 备用、储能段中性、无 UC、年度加权是否高估缺供 | 作为局限说明；只有证据证明方法本身错误才可修，不能临时改变既定备用规则 |
| **U：证据不足** | 缺少关键潮流/可用性/时序输出，无法认定 | 记录 `UNRESOLVED`，仅可申请 W2 极小诊断，不得假定“已校准” |

每条诊断必须标注 `SOURCED / MODEL_DIRECT / DERIVED / PROXY / UNRESOLVED`，注明来源路径、模型 commit、所用计算逻辑及可反驳证据。**W1 的终点不是写一份“可能是输电瓶颈”的报告，而是能对 2026 年 51 GWh 缺供做出定量分解和清晰的修正/保留决定。**

---

# W2｜只在有证据时修复 S0，必要时成对重跑 S0/S1

## W2.1 校准优先级和允许修改范围

**必须先出 W1 根因表，再决定是否重新优化。** 只允许以下顺序：

**优先级 1 — 输入/时序错误修复（有事实证据才改）**：

- 修正重复 Native Load、母线映射、机组实际可用状态、承诺输电线路日期/容量、已有线路的 `s_nom/x/r` 不一致及活动掩码；
- 修正确认为错误的时间权重计算、压力快照重叠/重复，或可由全年数据验证的代表样本权重；
- 对确定遗漏的**真实、已承诺**资产，可核对后纳入共同基准，保留成本、许可、建设期和 COD（绝不能视作免费新增候选）。

**优先级 2 — 经证明的方法实现错误**：

- 储能和备用在同一物理 SOC 上的数值/状态转移问题、年际资产 mask 错误、求解后统计错误；
- 对 v1.6 `x/r` 的处理若有构网逻辑缺陷，应根据电抗物理与保存前校准过程选择修复方式；不得任意降低线路阻抗以产生更大传输能力；
- 必须在可重复的结构测试中证明修复解决的是具体错误，且没有同时改动不相关的成本或需求。

**优先级 3 — 确认为真实约束的情形**：不修改 S0 只为消除缺供。把缺供作为合理的基准压力条件，但保持 `SCIENTIFIC_USE` 仍待独立方法审查；如无法给出可信解释，则维持 `SCIENTIFIC_BASELINE_BLOCKED`，不得用 `optimal` 替代。

**禁止修改**：削减原生负荷、放松 3 GW reserve、去掉 no-harm、降低 shed 惩罚以制造数值、添加无成本 `S0CAL`、人为缩短普通公用投资工期、只给 S0 一个特殊补救资产、为得到 BYOP 优势挑选 stress weeks。任何候选新公共资产必须有真实成本、真实 lead 和双向容量权利。

## W2.2 什么情况下需要新的求解调用？

| W1 结论 | W2 行动 | 求解额度 |
|---|---|---|
| 只是报告/统计误差，原始物理解无需改变 | 修订后处理、更新权重和成本报表的解释；不修改优化输入或已经使用的 shed 文件 | **0** |
| 发现事实支持的输入/拓扑/COD/采样修正，影响可行域或目标 | 建立**新的版本化 S0/S1 case**，先静态回归和门禁、再按新预算 `S0_COST → S1_SPEED_HIERARCHY → S1_COST` | **最多 3 个顶层调用 / 2 个情景尝试 / 0 重试** |
| 只有一项根因尚未分离，例如 `x/r` 缩放 vs 线路容量 | 仅在说明“旧产物无法推断”后，提出**一个**最小可证伪 2026 诊断 LP；不做多维灵敏度矩阵 | **最多 1 个额外诊断调用**，独立记账、独立审批；不得用其代替正式 S0/S1 |
| 已证实真实资源/网络缺口、无证据可修 | 不强行重跑；出具物理解释及代表性局限，研究者决定论文是否采用保守缺供基准 | **0** |
| 数据/SOC 证据不足且无合理修正 | 只读冻结，列出明确缺失证据与科学阻断项 | **0** |

**新预算不是 NEXT-05 夜间剩余 A3 额度**。本工作包是任务实施说明：新增正式优化调用必须有实际用户授权、独立的新代码 SHA/manifest、独立 gate 和已冻结的求解调用预算；不能单凭包含授权示例的 Markdown 文件自行冒充聊天审批。执行方可以无人值守完成 W1 与 W3 静态部分，并预先准备 W2 的测试与审批材料。若研究者已在本次实际对话中明确授权上述限制范围，可按原门禁记录并启动，不必反复请求相同批准。

## W2.3 成对重跑的硬性要求（若触发）

1. 在旧结果的只读快照之外新建 `case_id`、输出目录、配置、签名 manifest、父/子 ledger；先核对现有运行脚本和门禁是否支持新的输出路径。**不要直接运行旧的 `s0s1` 命令去消耗已用过的 A2 台账**。
2. S0 与 S1 **完全共用相同的修正后公共输入和时间轴**，只在既定 AIDC/POI/Speed-First 情景定义上不同；`S0_NO_HARM_REFERENCE.csv` 新版本必须 SHA 锁定，S1 的 no-harm 行从新 S0 引入、无缺项补填。
3. 全程保留 LP-only；S1 严格 2026→2031 lexicographic speed，再固定速度进行成本优化；不能退化为加权延迟罚函数。
4. 保留 3 GW 系统备用、SOC 段能量中性近似、起末 SOC 备用能源、付费公共扩张、DWB/PBRP 同一承诺、Firm/Conditional Firm 口径。若 W1 证明其中有实现错误，只修复已经明确识别的 bug 并留回归证据。
5. **运行中先保存解，再做 collector**：至少持久化每个情景的 `storage_units_t.state_of_charge`、`p_store`、`p_dispatch`，以单元×模型年×连续片段计算 `SOC_start`、`SOC_end`、`SOC_end_minus_start`、充放电能量、SOC slack；必要时存完整求解网络。输出与原结果的差别可追溯、不可通过结果后处理造新状态。
6. S0 单独执行并科学复验合格后才进入 S1；有真实 `DONE/optimal` 但科学异常未解决时，**不得把技术 PASS 当成论文基线 PASS**。S1 有两次不同顶层 optimizer 调用，全部计入预算；若 S1 的层级目标未锁定、baseline 文件 SHA 不匹配，则立刻停止。
7. 在新旧版本之间报告变化：S0 2026 年缺供（MWh、peak MW、bus-year）、2031 年公共资产、每年投资/COD、S1 年度请求/交付/延迟、S0/S1 各自的现有用户负荷保障、真实物理资源支出与总社会成本；不要只比一个年度缺供值。
8. 原版 S0/S1 运行代码 SHA `cdfdea06` 和结果保持**独立可复现**；修正版本用新的 SHA 和正式标签，不得将其回填旧求解日志或覆盖旧文件。

## W2.4 “S0 调好”必须具备的验收门槛

### 数据与物理层

- `W1` 缺供核算完整复现 54,205.7791 MWh（若原版）；新版本必须逐年、逐站点可追溯；
- 母线负荷、基线线路、机组和 DWB/PBRP 项目不遗漏不重复；线路的 `s_nom/x/r` 与资产物理表达一致；2026 年半年度 COD 的年度快照处理清楚写出；
- 权重和为 8760 h，stress-only 不能重复计价；保留真实 3 h 储能动态；
- S0 的 2026 年短缺若仍大于 `1000 MWh` 或单母线 peak 超过 `10 MW`，继续触发**强制科学审查**（沿用当前 collector 的方法标志阈值），**不能因为解释了其中一部分就改成 `SCIENTIFIC_USE=PASS`**；该阈值是复核触发条件，不是要求模型硬凑到其下；
- 如果短缺显著但有真实可靠性证据，报 `BASELINE_PHYSICAL_SCARCITY_DOCUMENTED`，说明与 Nature Energy 定量结论的解释风险；如果无证据则 `BASELINE_RELIABILITY_UNRESOLVED`。如由错误导致，只有更正输入和成对验收后才可解除该具体阻断。

### 求解与对比层（仅适用于新算例）

- `status=ok/optimal`、0 整数、节点平衡和备用按原 A2 容差、资产工期和有价扩张、不允许 free links、324 正反向扩张一致；
- S0/S1 公共输入完全匹配，S1 对同母线同快照的既有用户缺供不超过 S0 +0.001 MW（后验 0.002 MW），S1 Speed-First 目标在成本阶段全部保持；
- 固定代表性片段 SOC 起末的实际后验表必须存在；对 cyclic 和非 cyclic 资产**分别判断是否确实能量中性**，不能只检查 constraint count；
- `MAINLINE_GATE_CHECKS.csv` 应同时报告 `TECHNICAL_GATE`、`S0_RELIABILITY_REVIEW_REQUIRED`、`FINAL_SCIENTIFIC_USE`，科学使用状态不得因自动修复代码跳过审查；
- 新旧成本账必须注明 `social_real_resource_cost` **包含既有用户 VOLL 缺供损失**，不能冒充单纯的“真实资源投入”；单独报告 `physical_resource_spending_proxy = social_real_resource_cost − load_shed_PV`，而 `social_total` 另计 AIDC 延迟损失；POI 投资已计入 public capex，不得重复加；成本使用同一美元基年、折现和公共承诺外部成本附表。

### W2 决策分流

- **`S0_CALIBRATED_PASS`**：根因闭环、物理数据与时间权重有证据、可靠性足以支持论文解释；如仍有极小残余 shed，分清方法标志并提交研究者审查，不能默认论文-ready；
- **`S0_SCARCITY_VALIDATED_WITH_LIMITS`**：高缺供确认是实际可解释的物理约束，而非模型错误；明确是带可靠性限制的反事实。需另行判断是否适于私人—社会效率测算；
- **`S0_BASELINE_BLOCKED`**：关键信息缺失、错误未解决、时间外推无法辩护或成本/物理台账不可信。不运行依赖它的正式 S2/S3。

---

# W3｜A3 独立门禁与 S2/S3 最小主线静态准备（0 optimizer calls）

W3 可与 W1 的只读数据整理并行，但**科学结论以 W2 为先**。这一阶段只为后续避免再次因无门禁而停止，**不启动任何 S2/S3 优化器调用**。

1. 对真实程序中的全部调用点建表：`developer_joint` 的逐年 lex LP 及一次 private cost LP、`S2_PUBLIC_RESPONSE`、`S3_COORDINATED`、`S3_mS2` matched-service，以及所有可能的间接 `linopy/Gurobi` 路径。逐个区分**情景尝试、顶层调用、多目标内部目标级数**，禁止漏计或双重计数。
2. 实现独立 `A3` manifest、config、parent/child ledger、crash-safe `STARTED/DONE/ERROR`、严格 SHA、调用计划及额度拒绝测试。保留原 S0/S1 的已耗调用日志，不修改 A2 门禁以为 A3 留捷径；任何额外 optimizer 调用必须被门禁阻止。
3. S2 开发商严格“最早交付优先→在相同速度下私人成本最小”，并让 Grid-Only / Grid-Connected Flexible / Islanded 与 N/R/C 获取路径分开。S3 使用**同一物理资产、工期、气源、POI、备用和 SOC 可行集合**，改变的是协调优化目标。禁止把 S3 的灵活性变成放松物理标准。
4. S2 完成后必须有 `S2_final` 的收敛验证，公共响应可交付、服务速度一致；`S3_mS2` 真实 matched-service 用于比较资源效率，不能用更少负荷服务换取更低成本。
5. RE/BESS 的 48/72 h Firm 证书需要连续同一物理 SOC 的压力样本；当前 24 h B7 样本**不能**认证 72 h Firm，未验证资源不得预留全天候 firm 权利。若样本未扩展，采用明示的保守 firm credit，不为 S2 额外放松。
6. A3 必须能通过 solver-free failure injection：门禁缺失、重复 STARTED、SHA 改动、超额度、多目标内部调用计数、S0/S1 科学阻断、非收敛、缺 matched-service 等情形均被拒绝或正确标记。
7. 交付 **仅一个**可审查的 2026–2031 ERCOT 主线方案 `S3 → S2 developer/private → public response → S3_mS2`。不扩展全国、不跑长期 2050、不加入大量敏感性场景。历史 NEXT-05 的 A3 30 调用预算已用 0 次，但**本 W3 不自动解锁该额度**；正式 A3 解锁须在可信 S0 的物理审查通过后针对实际代码 SHA 独立登记。

**必交**：`W3_A3_SOLVER_CALL_PLAN.csv`、`W3_A3_GATE_VERDICT.json`、`W3_A3_STATIC_TEST_SUMMARY.json`、`W3_S2_S3_PHYSICAL_PARITY.csv`、`W3_A3_EXECUTION_READINESS.md`。

---

## 4. 执行流程、控制点和调用预算

```text
H0: 检查当前 main/L2/GitHub、运行锁、现有 ledger、原 S0/S1 SHA
  |
  v
W1: S0 原始 shed 数据/样本权重/2025 基线谱系/Far West 线路负荷 COD
    全部为只读，0 solver calls
  |
  +-- 根因 = 报表错误 → 只修后处理、保留旧解 → W2 科学验收 → W3
  |
  +-- 根因 = 可证实输入/拓扑/工期错误 → 修正公共共同输入和静态回归
  |      → 新 SHA/manifest + 新授权 → S0_COST
  |      → S0 科学/技术验收 PASS → S1_SPEED_HIERARCHY → S1_COST
  |      → 成对对比与 SOC 后验审计 → W3
  |
  +-- 根因 = 真实紧约束 → 保留物理缺供、明确可靠性限制
  |      → 研究者科学口径审查；W3 仅静态
  |
  +-- 根因仍无法核实 → 缺口证明/可选仅一项诊断 LP 的授权申请
         → W3 静态；不称正式科学结果
```

**预算**：W1=0；W2 若有严格证据支持的修正且获得独立批准，正式 S0/S1 共有 **2 情景尝试/3 顶层优化器调用、0 重试**；另有**最多 1 个事先确定问题的可选诊断 LP**，须独立批准；W3=0。总计本工作包预期 0 调用，条件下最多新增 4 调用。任何 `STARTED` 都计入消耗额度；不允许自动重复、大包式扫参或隐式 Gurobi 调用。

**人工介入点**仅保留三类真正研究决策：① 缺供到底保留还是事实校正无法达成唯一结论；② 影响物理可行域的新模型/数据以及其求解预算授权；③ 是否接受高缺供但物理可信的 S0 作为论文正式比较基准。执行方不必为原始报告整理、静态小修、测试和 A3 门禁代码反复申请确认。

## 5. 文件交付规范（必须持久化并同步到 GitHub）

在 `current_work_pckg/` 新建 `BYOP_NEXT_06/` 放置最终交付，并在本轮开始与每个里程碑记录 SHA。**最少交付**：

| 文件 | 必须包含 |
|---|---|
| `NEXT_06_EXECUTION_REPORT.md` | 分阶段状态、真实调用数、代码 SHA、校准决策、重要结论、停止原因 |
| `W1_S0_RELIABILITY_ROOT_CAUSE.md` | **本轮最重要报告**：54.2 GWh 的定量分解、2026 51 GWh 的母线/快照来源、物理证据、是否需修正、与历史 2025 口径差异 |
| `W1_S0_SHED_BY_BUS_YEAR.csv` | S0 各年、各 bus／负荷类别的加权/未加权 shed |
| `W1_S0_SHED_SNAPSHOT_WEIGHTS.csv` | 每个有 shed 的时间片的原始 MW、实际小时、代表小时和 MWh、周/压力归属 |
| `W1_S0_TOP_SHED_EVENTS.csv` | 最大事件、连续时间、权重放大与关键系统状态 |
| `W1_BASELINE_LINEAGE_AND_COMPARABILITY.csv` | 可扩张校准 LP、C1 固定 2025、v1.6 基线、2026 S0 的真实可比性 |
| `W1_FAR_WEST_ASSET_DELIVERABILITY.csv` | p620 6/7 周边的负荷/机组/线路/储能/承诺项目及其 COD/资格 |
| `W1_COMMITTED_PROJECT_COD_QA.csv` | DWB/PBRP 的 ISD、活动掩码、年度可用性与证据分类 |
| `W1_ROOT_CAUSE_DECISION_TABLE.csv` | D/T/C/P/M/U 根因、证据链接、能否独立证实、建议修正与计算代价 |
| `W2_S0_CALIBRATION_DECISION.md` | 只读保留/可证实修正/待补证据的明确路径及对 S1 的影响 |
| `W2_REVISED_S0_S1_EXECUTION_REPORT.md` | **只有正式重算时**才生成：新 SHA、父子 ledger、S0/S1 全部验收与新旧结果 |
| `W2_SOC_POSTSOLVE_AUDIT.csv` | **若发生新正式求解必交**，各 storage unit × 代表连续片段 SOC 起止差和实际能量收支 |
| `W3_A3_EXECUTION_READINESS.md` | 新门禁/manifest/父子预算、静态测试以及安全下一步；没有运行则明确写 0 次 |
| `NEXT_06_RESULTS_INDEX.json` | 每个关键文件的 sha256、模型版本、数据来源及缺失情况 |
| `NEXT_06_RETURN_PACKAGE.zip` | 包含报告/关键表/静态测试/验证结果，不强制重复打包大 `.nc`，但提供准确本机路径和 SHA |

原始 `OVERNIGHT_RETURN_PACKAGE.zip`、`S0_RESULT.json`、`S1_EARLIEST_RESULT.json` 和 ledger 都保留原样。新实验必在新目录。项目默认 `main` 为长期主线；仅用短期 worktree 处理修正，不制造两个持久研究主分支。

### 报告顶部的机器可读字段

```text
WORK_PACKAGE: BYOP_NEXT_06
SOURCE_MAIN_SHA: <核验的完整 SHA>
ORIGINAL_SOLVED_CODE_SHA: cdfdea06146a6fe73df89cb410d6a88cb5fda306
ORIGINAL_S0_STATUS: TECHNICAL_PASS / SCIENTIFIC_REVIEW_REQUIRED
ORIGINAL_S1_STATUS: TECHNICAL_PASS / EXPLORATORY_ONLY
ORIGINAL_S0_SHED_MWH_2026: 51049.2775
ORIGINAL_S0_SHED_MWH_ALL_YEARS_SUM: 54205.7791
W1: NOT_STARTED | PASS | INCOMPLETE | FAIL
W1_WEIGHT_AND_SHED_RECONCILIATION: PASS | FAIL
W1_BASELINE_LINEAGE: RECONCILED | NOT_COMPARABLE | UNRESOLVED
W1_ROOT_CAUSE: DATA | TIME | COMMITTED_COD | PHYSICAL | METHOD | UNRESOLVED
W2: NO_RERUN_NEEDED | STATIC_FIX_READY | RERUN_AUTH_PENDING | RERUN_PASS | RERUN_FAILED | BASELINE_BLOCKED
W2_NEW_SOLVER_CALLS: <integer>
S0_RELIABILITY_VERDICT: CALIBRATED_PASS | PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS | BLOCKED
S1_S0_COMPARABILITY: ORIGINAL_ONLY | REVISED_PAIR_VERIFIED | NOT_COMPARABLE
W3_A3_GATE: NOT_BUILT | STATIC_PASS | STATIC_FAIL
A3_SOLVER_CALLS_THIS_PACKAGE: 0
NEXT_SAFE_ACTION: <可复现的下一步>
```

## 6. 最后验收：如何衡量本工作包有没有真正推进研究？

**最低达标**：W1 用原始模型资料复算、分解并解释 2026 年主要缺供，查明是否有可校正的物理/数据/时段问题；明确比较为什么先前“111.8 MWh”不是自动应追逐的标杆；提供是否需要正式重跑的决策证据。仅汇报 `S0 54 GWh、可能是瓶颈` 不算通过。

**充分达标**：如有证据支持的修复，W2 对同一已登记修订模型成对重跑 S0/S1 并具备完整 SOC 后验审计；如确实无可校正错误，则不人为改小 shed，而以可信的物理与方法局限形成正式可审查的可靠性结论。W3 完成 A3 最小门禁静态准备而不挤占 S0 校准资源。

**研究目标不变**：下一步才在可信 S0/S1 之上，用 S2−S1 检验 BYOP 的 Speed-to-Power 和公共投资反馈，并用 S2−S3 matched-service 检验私人—社会效率；当前的 2026–2031 首轮结果不构成 2050 路径锁定结论。
