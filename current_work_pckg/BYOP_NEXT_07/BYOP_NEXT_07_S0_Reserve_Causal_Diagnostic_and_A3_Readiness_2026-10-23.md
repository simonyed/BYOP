# BYOP NEXT-07｜S0 备用约束归因、可靠性决策与 A3 最小就绪工作包

**版本**：v1.0 · 2026-10-23（America/New_York）  
**交付对象**：Codex / Claude / 具备 GitHub 和 L2 访问的执行方  
**仓库**：https://github.com/simonyed/BYOP  
**起始分支**：`main`；已核对 `main`、`mainline-v13-stageA` 均在 `bcd9844d`（执行前重新核对 HEAD）  
**原始正式 S0/S1 求解代码**：`cdfdea06146a6fe73df89cb410d6a88cb5fda306`（必须保留）  
**NEXT-06 预备诊断代码 SHA**：`e2daf9d3ecf7e69552c831ee60685a737dcbd9f5`（该 SHA 属于**2026 全年诊断**，不可直接用于本包新的备用对照求解）  
**基线文件固定 SHA-256**：`a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`  
**论文主线**：《论文顶层设计.md》；四情景 S0/S1/S2/S3；S0 必须是可信的公共电网反事实基准，之后才能研究 BYOP 的速度、扩张反馈与私人—社会偏离。

> **核心命令：最小化求解次数、最大化因果可解释性。** 不新增一般参数敏感度矩阵。本轮只有一组优先对照：原始 S0（3 GW 备用） vs **同一多年度 S0、仅系统备用需求右端置 0**。先完成原始结果数字更正与逐约束对等审计，再申请 **1 次**独立的 LP 求解授权；根据其结果决定是否需要执行已准备的昂贵全年诊断。A3 仅做必要的静态完工，不因还有调用预算而提前求解。

---

## 0. 冻结事实、研究边界与授权边界

### 0.1 绝不可覆盖的原始成果

- A1：LP-R `PASS`，`H_resource = 2587.772185 MW facility`；LP-N 因冻结线路限制不可行，`H_network = NOT_AVAILABLE`，不能记为 0。
- 正式 S0/S1：两情景均 LP `optimal` 且**技术验收** `PASS`；原始 S0 2026–2031 加权既有负荷缺供 `54205.7791 MWh`；其中原报告 2026 Native Load `51049.2775 MWh`。S1−S0 仍只属于探索性比较。
- 原始 S0/S1 顶层优化器调用已耗尽（`S0_COST` 1、`S1_SPEED_HIERARCHY` 1、`S1_COST` 1）；历史失败/成功账本均不得删除、重写或复用。
- NEXT-06 W1：S0 缺供集中在 2026 年 Far West 夜间，尤其 `p620 6` / `p620 7`；3 GW 备用与热机在线容量/最低出力耦合为高优先级**假说**，尚非已证实原因。
- NEXT-06 W2：全年 2026 诊断已预备但未授权，独立配置 `workflow/config/config.byop_post_v16_n06_diag.yaml`；当前仍 `NOT_APPROVED`，本工作包不得擅用旧 SHA 启动。
- NEXT-06 W3：A3 独立 gate / call plan 已通过静态测试，但 runtime 求解接线、保守 Firm 规则、S2 收敛和 S3 matched-service 的验收尚不完整；`S0_SCIENTIFIC_STATUS.json` 目前为 `BASELINE_RELIABILITY_UNRESOLVED`。

**原始冻结目录**：

- `workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1/`
- `workflow/results/BYOP/next06_s0_diagnostic/`
- `current_work_pckg/BYOP_NEXT_06/`
- `workflow/results/BYOP/POST_V16_A1_HEADROOM/`

原始 S0/S1 的求解与验收台账、`S0_NO_HARM_REFERENCE.csv`、`S0_shed_by_snapshot_frozen.csv.gz`、`S0_RESULT.json` 和 `S1_EARLIEST_RESULT.json` 均为只读证据。任何新的诊断应创建自己的输出目录、manifest、父子调用台账和 RESULT 文件。禁止把原 S0 结果标记为“失效并重算”来掩盖历史记录。

### 0.2 本包明确不做什么

- **不**把 2025 v1.6 LP2 的 `111.79 MWh` 当作 2026 S0 的拟合目标；二者的年份、备用及采样条件不同。
- **不**删除线路约束、SOC 分段约束、热机最低出力、公共扩建时滞、负荷或压力快照来制造一个易于优化的 S0。
- **不**把备用需求为 0 的诊断直接替换正式的 3 GW 备用 S0；本包的备用置零仅用于**机制归因**。
- **不**自动动用 NEXT-06 全年诊断预算，也不自动启动 S2/S3。
- **不**以“技术 PASS”替代“科学使用 PASS”；不将模型下的高 EENS 直接宣称为现实 ERCOT 缺供预测。

### 0.3 预算和审批

| 工作 | 本包允许的工作 | 新增实际优化器调用 | 放行方式 |
|---|---|---:|---|
| W0 | 确认状态、纠正 W1 统计表述 | **0** | 自动执行 |
| W1 | 备用约束单因素对照的编码、构建、逐约束静态验收 | **0** | 自动执行 |
| W2 | `S0_RESERVE_REQ_ZERO`：**一项诊断、1 次 S0 LP** | **最多 1** | **必须获取研究者对新冻结 SHA 与该次预算的聊天明确授权** |
| W3 | 解释结果并决定是否值得全年诊断或成对正式复验 | **0** | 自动执行分析；需研究者判断科学状态或新求解 |
| W4 | 补齐 A3 静态接线、保守 Firm 和验收测试 | **0** | 自动执行，不解 S2/S3 |

> **重要**：交付工作包本身不构成求解授权。必须由研究者在聊天中批准准确的代码 SHA、诊断范围、调用预算及标识后，执行方才能提交 config-only `APPROVED`。不得推断旧的 NEXT-05/06 授权可移植到新的可行域。若未取得授权，完成全部 W0/W1/W4 并提交 `W2_APPROVAL_REQUEST.md`，不得反复空转。

---

# W0｜NEXT-06 数据口径纠偏（零求解、优先级最高）

## W0.1 统一分母、时间权重与区域汇总

独立读取：

- `workflow/results/BYOP/next06_s0_diagnostic/W1_S0_RECONCILIATION.json`
- `workflow/results/BYOP/next06_s0_diagnostic/W1_S0_SHED_SNAPSHOT_WEIGHTS.csv`
- `workflow/results/BYOP/next06_s0_diagnostic/W1_S0_SHED_BY_BUS_YEAR.csv`
- 原始 `S0_shed_by_snapshot_frozen.csv.gz` 和 A2 SOC segment map。

明确且分开报告：

| 指标 | 已有近似值 | 正确解释 |
|---|---:|---|
| 跨年各年度加权缺供合计 | `54,205.7791 MWh` | 2026–2031 模型年值之和，**不是单年 EENS** |
| 2026 年既有 Native Load 缺供 | `51,049.2775 MWh` | 占跨年总量约 **94.2%**；该项不含极少的 inherited-ramp shed |
| 所有模型年份的 `SAMPLED_WEEK` 加权缺供 | `46,871.775 MWh` | 占跨年总量约 **86.5%**；这是采样周代表权重贡献，不是“94%” |
| 所有模型年份 `B7_STRESS_ONLY` 加权缺供 | `7,334.002 MWh` | 权重 3 h；与上项一起严格还原总量 |
| 2026 年保留快照按真实 3 h 相加的缺供 | `5,990.800 MWh` | 含 sampled-week **及** B7；不能整体再乘 25.857 |
| 采样周每 3 h 快照年度权重 | `77.5714 h` | 相对于实际 3 h 的权重比约 25.857；只适用该类快照 |

特别注意：`p620 6` 和 `p620 7` 的 2026 加权缺供约 31.2 GWh 与 16.25 GWh，**不能不分时段地说这两处所有缺供都发生于两周采样时段**；必须按 `bus × year × segment_kind` 再汇总验证，明确其中压力日的比例。W1 报告中“2026 / Far West / sampled week”三类不同分母的百分数需分别标注，若存在矛盾要更正。

新建不可覆盖原始表的 `W0_SHED_RECONCILIATION_CORRECTED.csv` 和 `W0_RECONCILIATION_VERDICT.json`，每个比率写明分子、分母、单位；全体求和残差绝对值应小于 0.05 MWh（允许原结果 1e-10 级数值噪音）。只更新本轮勘误说明或链接，不改写 NEXT-06 已签收的原始报告。

## W0.2 核对 S0 物理结果和先前代码版本

记录并 SHA-pin：

- 既有 S0/S1 结果 JSON 和两层求解日志；
- 基线 `.nc`、新旧代码 SHA、两类快照权重；
- 2025 LP2 与 2026 S0 的关键已知不同点：背景负荷增长 `1.009327`，备用规则、分段 SOC、已承诺资产 COD、跨年投资、时间采样。

在这里不把“LP2 2025 无缺供而 S0 2026 有缺供”直接归因于某一个新增约束；也不把缺少真实年资料的权重外推误认成客观错误。

**W0 验收**：`W0_DATA_QA=PASS`，记录数、精确加权总量、Native/inherited 划分与 `SAMPLED_WEEK`/`B7_STRESS_ONLY` 划分全部自洽。若 FAIL，仅修统计程序，W2 禁止启动。

---

# W1｜只改变备用需求右端的 S0 因果对照（零求解准备）

## W1.1 因果问题与严格的对照定义

**目标**：隔离 **3,000 MW 系统备用需求本身**对 S0 2026 Far West 夜间缺供的贡献，而不是同时删除热机运行限制或储能 SOC 规则。

| 维度 | 原始正式 S0 | NEXT-07 诊断 S0 |
|---|---|---|
| 时段及规划 | **2026–2031，sample_weeks = 26**，相同两周 + B7 压力日 | 完全相同 |
| 研究负荷与 S0 定义 | 无本研究新增 AIDC；有既有用户 / 已继承 ramp | 完全相同 |
| 现有发电、储能、线路 | 冻结 v1.6 基线 | 完全相同 |
| 天气、背景增长、PUE、燃气成本 | 正式 S0 共同输入 | 完全相同 |
| 已承诺资产、公共投资候选及 COD | DWB、PBRP、付费公共扩张 | 完全相同 |
| VOLL、求解目标、折现、投资年权重 | 原始 S0 | 完全相同 |
| `PV16M-online_cap` / 在线容量及热机最低出力 | **保留** | **保留** |
| 储能起止备用能量、段 SOC、物理储能步长 | **保留** | **保留** |
| `PV16M-reserve_req` | `total_reserve >= 3000 MW` | **仅改为 `total_reserve >= 0 MW`** |
| AIDC 供电模式、S1/S2/S3 | 不在本次诊断中 | 不变、不运行 |

`post_v16_mainline.py::add_operating_reserve(n, snapshots)` 当前除了 `PV16M-reserve_req` 外，还建立 `PV16M-online_cap`、`PV16M-online_min`、`PV16M-res_thermal_head`、`PV16M-res_ramp`、`PV16M-res_su_energy(_start)` 等约束。**严禁整个跳过 `add_operating_reserve`，严禁把 `POST_V16['on']` 关闭。** 只修改该诊断实例中 `PV16M-reserve_req` 的 RHS，亦可以通过该函数接受一个经 SHA-pinned 诊断配置的 `reserve_requirement_MW=0.0` 参数；默认正式路径必须仍为 3000.0。

解释范围：本实验识别 `reserve_req` **右端改变所产生的总均衡响应**（包括调度、价格、内生公共投资相应调整）；**不能**单独识别 online-min 约束的独立贡献，不能直接据此宣称系统最优备用容量应为 0 MW。

## W1.2 编码位置及变更保护

推荐新建独立配置，**不得修改或复用** NEXT-06 全年诊断配置：

- `workflow/config/config.byop_post_v16_n07_reserve_probe.yaml`
- `current_work_pckg/BYOP_NEXT_07/N07_RESERVE_PROBE_PRE_RUN_MANIFEST.json`
- `workflow/results/BYOP/next07_s0_reserve_probe/`
- 独立 gate/ledger 使用已有 A2 型门禁能力和 NEXT-06 的 `--a2-config` 接口；严格限定 `stage=A2`、`stages=[S0]`、一次情景尝试和 **一个 `S0_COST` 顶层调用**，零重试。
- 把唯一诊断选项作为该配置的显式字段（如 `diagnostic.reserve_requirement_MW: 0.0`、`diagnostic_kind: S0_RESERVE_REQ_RHS_ONLY`），在 `post_v16_guard` 及模型构建入口读取、校验；仅在匹配该专用诊断配置、独立输出目录和 SHA-pinned 代码时生效。**正式 A2、NEXT-06 full-year 和未来 A3 均不得继承诊断选项。**
- CLI run arguments 精确固定：`--start 2026 --end 2031 --sample-weeks 26 --scenarios S0`；`--config config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml`、`--base` 取 SHA 固定的 v1.6 文件，`--no-harm on`，不得启用 `--relax`、legacy ERM 或 S0CAL。
- `run_post_v16_a2.sh` 可新增 `n07_manifest / n07_gate / n07_reserve_probe / n07_tests` 四个**显式命令**；不能重写现有 `s0s1` 入口或默认 A2 路径。脚本选择新配置、专用输出目录与锁定的命令行参数。
- 与 `W1` 对照有关的变更保持在最少文件范围内：`post_v16_mainline.py`、`rearch_mech.py` 的诊断配置传递、新配置及必要测试/门禁；所有不相关代码应保持原始 SHA（尤其输入、基线、投运活动 mask、正式 S0/S1 物理规则）。

**一个必须主动排除的危险实现**：仅在源码中把全局 `POST_V16['reserve_MW'] = 0`，然后运行完忘记复位。这会污染下一场景、结构测试或 A3。改用每次模型创建时显式传参、局部作用域或 `try/finally` 复原；并用同进程连续构建“诊断 S0 → 默认 S0”确保默认 `PV16M-reserve_req` 始终是 3000 MW。

## W1.3 无求解器的“逐约束差异证明”

在 L2 构建如下两个**完全相同的 S0 模型**，拦截 `linopy.Model.solve`、`gurobipy.Model.optimize`，不得调用优化器：

1. **REF_BUILD**：从当前仓库冻结输入按原始正式路径重构 `S0`, 2026–2031, same snapshots, 3000 MW；
2. **PROBE_BUILD**：相同快照、对象和输入，仅启用 `reserve_requirement_MW=0.0`。

检查：

- 快照 MultiIndex、每年的 weight sums、`stores=3h`、发电/储能/线路/负荷参数、机组出力上限、线路 `x/r`、已承诺资产可用性、公共扩张 COST/COD、各类总成本系数**逐项相等**；
- 连续变量数、约束数、约束名称集合、所有非 reserve-requirement 行的表达式系数、上下界、RHS、变量上下界、目标函数常量/系数**相等**（浮点值用容差 1e-10；对稀疏矩阵按标签或 canonicalized 索引对齐而不是依赖遍历顺序）；
- `PV16M-reserve_req` 行数、系数、符号、坐标完全相同，**只有 RHS 由 3000 改为 0 MW**；
- `PV16M-online_cap`、`PV16M-online_min`、`PV16M-res_thermal_head`、`PV16M-res_ramp`、`PV16M-res_su_energy` 和 `..._start` 行都必须仍存在；`A2F08-seg_soc_` 分段行均存在；
- 默认/正常路径（包括 NEXT-06 全年诊断配置）在此更改后仍保持 3000 MW 备用 RHS。

将差异写入 `W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json` 与 `W1_CONSTRAINT_DIFF.csv`，期望**恰好一组约束的 RHS 数值变化**；如还有其他差异，进入 `BUILD_COMPARABILITY_FAIL`、停止并修复代码，**不启动 LP**。

建议最少测试：原始 S0 RHS 3000；探针 S0 RHS 0；诊断 flag 不能出现在正式 A2/A3；模拟多场景同进程后默认恢复；manifest/签名不匹配被门禁拒绝；调用前 STARTED 行原子落盘；非法第二次/重试被拒；无优化器 mock 路径仍可生成真实模型。对已知 S0 结构/成本的老回归都必须 PASS。

**W1 阶段目标**：`W1_STATIC_PASS`，且 `SOLVER_CALLS=0`；在此之前不得请求或执行求解授权。

---

# W2｜一项 3 GW 备用需求对照正式诊断 LP（研究者新授权后运行）

## W2.1 授权和启动门禁

当 W0/W1 验收全部 PASS 后，先冻结提交并同步 `main` / L2 / GitHub，生成确切 40 字符 `approved_git_sha` 与 `N07_RESERVE_PROBE_PRE_RUN_MANIFEST.json`，输出：

- `current_work_pckg/BYOP_NEXT_07/W2_APPROVAL_REQUEST.md`（必须给出**实际新 SHA**，不要使用上一轮的 `e2daf9d3`）；
- 新配置中的三字段仍 `NOT_APPROVED / null / null`；
- 门禁在 L2 只因审批三字段拒绝，且数据/manifest/独立台账均一致；
- 预构建的 vars/constraints 数量和内存估计，以及 L2 剩余 CPU/RAM/Gurobi 状态；
- 唯一授权范围：**S0、2026–2031 原始时段、0 MW reserve_req RHS、最多 1 `S0_COST` 优化器调用、零重试**。

研究者**在聊天中明确批准该新 SHA 和作用范围**后，才允许 config-only commit 设 `APPROVED`、准确的 SHA、研究者标识；再验证门禁通过并启动。未授权时继续 W4 的静态开发，不等待重复人工确认、不擅自批准。

## W2.2 求解和输出完整性

- `THREADS` 根据启动时 L2 负载实测选择，避免抢占其他作业；保留 Gurobi 参数的正式基准设置。
- 启动前向 `A2_SOLVE_LOG.csv` 写父 `STARTED`，顶层调用前向 `A2_OPTIMIZER_CALL_LOG.csv` 写唯一 `S0_COST STARTED`，结束写 DONE / ERROR；任何异常不得自动重试，不能擦除失败行。
- 使用 NEXT-06 已加入的 `post_v16_mainline.persist_solution`，在后处理前落盘并保存哈希：`storage_soc`、`storage_p_store`、`storage_p_dispatch`、`line_p0`、`link_p0`、`generator_p`、`bus_marginal_price` 和 `SOC_SEGMENT_POSTSOLVE_AUDIT.csv`。还应显式导出每快照的 **reserve shadow/slack / thermal online capacity / thermal reserve / BESS reserve、各关键发电机可用上界**，特别是 Far West 2026 晚间；导出应不改变 LP。若某项由 Linopy 解变量而非 PyPSA Network 提供，直接读取其 `.solution`，不可从合并坐标表误取。
- 逐项检查优化器 `ok/optimal`、功率平衡、无未计价免费公共扩张、公共线路 fwd/rev 容量相等、SOC 分段约束、0 整数、缺供/能源统计完整。`reserve_ok` 在本诊断中应与 **0 MW RHS** 核对，同时**明确标识 `DIAGNOSTIC_NONCOMPLIANT_WITH_FORMAL_3GW_REQUIREMENT`**，绝不能当作 3 GW 的正式验收。
- 禁止因结果读取失败而自动重跑：优先从已经保存的解文件重放后处理，保留历史调用行。
- 不自动收集“跨情景 S0/S1”比较结果，也不覆盖正式 `S0_RESULT.json`。

## W2.3 与原始 S0 的对照及判断

使用原始正式 S0 的 `S0_shed_by_snapshot_frozen.csv.gz` 与探针相同索引精确逐格比较；可将探针的加权缺供反算为同样的：year、bus、snapshot、sampled-week/stress-day、raw MWh、weighted MWh。

必交 `W2_RESERVE_CAUSAL_COMPARISON.csv`（至少含）：

- 2026 年原始总既有缺供 / native / inherited，探针对应值，差值及减少百分比；
- `p620 6`、`p620 7`、`p620 3`、`p610 4`、`p630 2` 的原始与探针：缺供 MW、加权 MWh、夜间缺供快照个数；
- 各 sampled-week/B7 应用时间权重后的缺供；
- 局部线路最大占用率、净进口、上游机组 dispatch 和在线容量、储能充放电 / SOC、旧与新 LMP；
- 公共新建 BESS、太阳能、风、燃气、输电容量及成本（全规划期、逐年），确认二者差异是内生响应而不是外生误差；
- 备用总量和 3 GW 要求违反量（在探针中仅诊断，不视为违法），判断原需求是否真的绑定于那些缺供快照。

**关键限制**：如果探针大幅降低缺供，只能证明“在原模型中，强制取得 3 GW 聚合备用的要求显著影响了最优调度/规划”。它**不能**单凭一项试算证明热机 minimum load 是唯一机制，也不能证明正式备用应削减。若探针缺供不降，不能反向证明 3 GW 备用对全网毫无影响，只能说无法解释目标 Far West 缺供。

#### 事前分类（不用结果反向调整标准）

| 探针发现 | 研究结论 | 下一步 |
|---|---|---|
| 2026 Far West 夜间缺供显著下降（例如降低 ≥80%） | `RESERVE_REQUIREMENT_LARGE_CONTRIBUTOR` | 分析拥塞、在线容量与储能证据；**仍不改变**正式 3 GW 规则；根据全年度代表性风险决定是否做全年诊断 |
| 下降有限（例如 <20%） | `RESERVE_REQUIREMENT_NOT_PRIMARY_IN_THIS_COUNTERFACTUAL` | 结合 per-line/thermal/SOC 解确认其他约束；不增加新的任意敏感度批次 |
| 20–80% 之间 | `MIXED_CAUSES` | 依据真实潮流与储能解排序贡献，不将混合影响强作单因素归因 |
| infeasible、solver warning、输出/验收失败 | `DIAGNOSTIC_BLOCKED` | 保存原始解和诊断，不重试、不调参、不扩大预算 |

上述 80/20% 仅用于**机制大小分类**，不是 S0 合格阈值、不是统计置信区间。要同时报告 MW、MWh 的绝对变化，且跨年加权总数不得与真实 3 h 电量混称。

---

# W3｜S0 科学状态决定：是否值得做 2026 全年诊断？

## W3.1 两个不同的疑问必须分离

- **M（机制）**：在两周 + B7 代表时段与 2026–2031 年相同外生世界里，备用需求是否造成 Far West 局部短缺？——W2 的 RHS-only 对照回答。
- **T（代表性）**：两个样本周的夜间短缺是否能代表全年 2026 运行状态？——不能由 W2 证明，必须有额外年度小时证据。

即使 W2 显示“去掉备用后缺供大减”，**T 仍然未解决**。不能因为搞清机制就把 51 GWh 加权值升级为可信的真实年度 EENS。

## W3.2 对全年诊断的成本—信息门禁

首先探索**不调用优化器**的年度代表性证据：原始 2025 全年 native load、天气负荷峰值、供需残差、局部净负荷夜间分布、两周抽样覆盖范围。若基于非优化数据不能判断短缺时数是否具代表性，则推荐保留 NEXT-06 已准备的 **2026 全年 S0 LP**，但满足以下要求后单独申请授权：

1. 不得沿用 NEXT-07 RHS=0 的诊断规则；全年模型保持正式 **3 GW 备用**；
2. NEXT-06 full-year 配置和 manifest 如因 NEXT-07 代码变更产生漂移，重新生成独立代码 SHA 并完成零求解的结构验收；
3. 全年求解模型实际构建，报告 `nvars/ncons/nnz`、矩阵内存及 L2 资源预算，不能仅引用估计的 9–10 M 变量；内存不足则 STOP、提交替代证据方案，不以未经证实的资源承诺启动；
4. 单独批准 **最多 1 次** S0 全年优化器调用（无重试），历史原始与 W2 的账本都应保持不可变；
5. 全年样本与代表性样本 **SOC 可行域不同**（连续全年 vs 离散 SOC 分段）、规划期不同（2026 单年 vs 2026–2031 联合），因此全年诊断给出“对应规则下的年度可靠性证据”，不是纯粹只改变 `weight_h` 的识别实验。报告必须登记这个重要的可比性限制。

若 W2 结果已足以确定某实现 bug，可依据证据提出**一项**最小修复，并在独立审批后成对重跑正式 S0/S1（2 父尝试、3 顶层调用，零重试），不得仅重跑 S0。没有证据支撑的情况则保留正式 S0 原值和科学使用限制。

## W3.3 S0 科学门禁不应自动解锁

建议 `S0_RELIABILITY_VERDICT` 合法状态：

- `BASELINE_RELIABILITY_UNRESOLVED`（默认，包含仅成功完成 W2、T 未解决的情况）；
- `METHOD_BUG_CONFIRMED_REPAIR_REQUIRED`（有确凿实现错误，需提出修复与成对重算方案）；
- `PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS`（已有足够年度频率证据、物理解释和审查，**研究者明确批准**）；
- `CALIBRATED_PASS`（经修正正式 S0/S1 并通过结构、数值、物理和年度代表性验收，**研究者明确批准**）。

不得因为诊断 LP `optimal`、原 S0/S1 `PASS` 或 2026 加权缺供量降低就自动将状态改为 `CALIBRATED_PASS`。如科学状态仍 unresolved，A3 求解 gate 必须锁定。

**W3 交付**：`W3_S0_SCIENTIFIC_DECISION.md`、`W3_S0_RELIABILITY_VERDICT_PROPOSAL.json`（此处状态仅 *PROPOSED*，不擅改被 A3 gate 读取的正式 `S0_SCIENTIFIC_STATUS.json`）、`W3_FULLYEAR_DECISION_TABLE.csv`。

---

# W4｜A3 必要的静态完成工作（严格 0 次优化器调用）

本工作与 W0/W1 可以平行准备，但**必须在单独工作树/分支**（如 `work/next07-a3-static`）中进行。**W2 诊断 SHA 和 manifest 冻结以后，W4 的代码/配置绝不得合入或同步到 L2 的 W2 求解工作树**；待 W2 完成、封存 ledger 和求解版本后再合并 W4，并重跑相应静态回归及 manifest 校验。不得因并行开发导致审批 SHA 漂移，也不得未授权触发任何求解。

### W4.1 按已核对代码补齐 A3 的调用保护

已有：

- `workflow/byop/model/post_v16_a3_gate.py`
- `workflow/config/config.byop_post_v16_a3.yaml`
- `current_work_pckg/BYOP_NEXT_06/W3_A3_SOLVER_CALL_PLAN.csv`

正式计划最多 **29 次顶层调用**（配置上界 30）：S0/S1 再求解 3，S3 一次，S2 每轮最多 8（共最多 3 轮），S3_mS2 一次。三轮 S2 仅在前一轮未收敛时执行；不得为了用完调用预算而继续迭代。

要求在不改变物理假设的前提下：

1. 将 S0/S1、`S3_COST`、S2 每轮 6 个 `S2_DEV_LEX`、1 个 `S2_DEV_COST`、1 个 `S2_PUBLIC` 及 `S3_MS2_COST` 的顶层求解统一接入 A3 **子台账 `child_start` → 实际调用 → `child_finish`**。对 `gurobipy.Model.optimize` 采用调用现场显式 instrumentation，不能假定 patch C 扩展接口可可靠拦截；
2. A3 门禁先于模型构建/求解；任何非法额外 `linopy.Model.solve`、重复阶段、超过 per-kind / total budget 的调用都拒绝；异常退出保留 STARTED / ERROR 证据，不能覆盖；
3. 复算 S0/S1 时需验证与正式基准相同模型/数据及无害性参考；如 S0 校准结果发生正式调整，则需要经批准的**新 S0/S1 基准**，不能声称恢复了旧 `S0_NO_HARM_REFERENCE.csv`；
4. S2 每轮进行“开发商计划容量 ≤ 公共系统可交付容量”审计，达标自动收敛退出；到最大轮数仍失败则 `S2_NOT_CONVERGED`，不得汇报 S2 最优；
5. S3_mS2 必须施加匹配 S2 已交付服务轨迹的约束，并在解后按母线×年、总 IT MW-year 与时间分布核对，未匹配不得报告 `S2−S3` 社会效率差异。

### W4.2 保守 RE+BESS Firm 规则与物理一致性

- S2 与 S3 都使用**同一**技术、气源、许可、COD、N/R/C 获取、POI、公共扩张、3 GW 备用、SOC 和 no-harm 可行域；不得只在某一场景放松。
- 在连续 **48/72 h** 同 SOC、低风/低光、无重复容量信用的认证尚未建立前，**BYOP 专用 RE+BESS 不给予全年 Firm 容量信用**；仍可按物理可交付性产生非 Firm 电量，不等于禁用可再生能源或储能设备。与公共系统已有的备用及储能容量权利必须严格区分，避免双重预留。
- 将保守规则同时落到实际开发商 LP / S3 社会 LP 的约束，不只写在配置说明。建立有反例的无求解器测试：RE+BESS 虚报 Firm 额度必被拒绝，RICE 等合格 Firm 的约束按既定规则保留，且 S2/S3 一致。
- 若实现 48/72 h 连续片段会改变代表性时间系统或 SOC 结构，则在独立工作包中提交采样变更及审批，NEXT-07 不执行。

### W4.3 明确验收边界

在当前 S0 科学状态为 `BASELINE_RELIABILITY_UNRESOLVED` 时，A3 应维持 `NOT_APPROVED / STATIC_READY_BUT_BLOCKED`。即使静态代码完成也**不得在本包解 S2/S3**。每次更改 A3 求解相关代码必须重建 manifest，旧 SHA 不再适用。

静态回归应覆盖：

- 旧 A2 求解预算已用完时绝不能重新消耗；
- 未授权、缺 manifest、SHA drift、原始 S0 状态未核定时 fail-closed；
- 前一轮收敛自动跳过 S2 可选迭代；
- 没收敛不进入 matched-service 效率报告；
- 模拟解对 S2/S3 共用物理约束，以及 RE+BESS 无完整 firm 认证不得占用完整 Firm 容量；
- 完整统计原有 256 项 NEXT-06 回归 + 新增测试，报告真实通过/失败/跳过数。

---

# 5. 总体执行顺序与三类停机条件

```text
H0 原仓库状态、证据与预算锁定
  ↓
W0 统计口径修正（0 solve）
  ↓
W1 备用 RHS 0 诊断模型搭建、逐约束比对（0 solve）
  ├─ STATIC_FAIL：修复本包范围内的程序问题；不运行诊断
  └─ STATIC_PASS：同步代码并生成 W2 审批请求
          ↓（研究者明确批准新 SHA）
W2 原始 3 GW S0 vs RHS 0 S0，新增仅 1 次 S0 LP
  ├─ infeasible/异常/验收失败：保留诊断，零重试；停止该支路
  └─ optimal + diagnostic acceptance：生成因果差分
          ↓
W3 给出 S0 科学状态建议、是否需要 2026 全年诊断、是否需要 S0/S1 成对重算
          ↓
W4 A3 求解路径静态完工（0 solve，独立工作树可并行）
          ↓
提交全部文件与下一步唯一决策建议；不自动开启全年诊断或 A3
```

**必须立即停止对应求解支路的情况**：

1. 基线 SHA / manifest / 受保护代码 / 输入发生漂移，W0 数值总量不能重现，或者 W1 发现 RHS 之外的非预期约束差异；
2. 执行设备 CPU/RAM/磁盘或 Gurobi license 不能安全满足模型，已存在冲突进程；
3. 求解器非 `ok/optimal`、输出验收失败、证据无法保存、调用预算触顶。严禁自动重试、解除安全门禁或清零账本。

**允许不等待批准继续的工作**：W0 静态数据 QA、W1 静态编码测试、W4 静态运行时接线/反例测试、报告和最终打包。审批未到不等于执行整个工作包失败；不要再次只生成 `NOT_APPROVED` 审批报告而不完成能做的工作。

---

# 6. 强制交付和报告回传协议

统一输出根目录：`current_work_pckg/BYOP_NEXT_07/`；计算诊断：`workflow/results/BYOP/next07_s0_reserve_probe/`。下列必需文件需有明确字段，若某环节因审批未到未执行则保留 `NOT_RUN` 并解释。

| 文件 | 最小要求 |
|---|---|
| `NEXT_07_EXECUTION_REPORT.md` | 顶部固定状态区、准确开始/结束 SHA、各阶段 PASS/FAIL/NOT_RUN，全部调用及分支状态 |
| `W0_SHED_RECONCILIATION_CORRECTED.csv` | bus/year/segment_kind 两维分拆、原始 3h 与加权 MWh、分母解释 |
| `W0_RECONCILIATION_VERDICT.json` | 各表与原始 S0 精确对账、QA 结论 |
| `W1_MODEL_EQUALS_EXCEPT_RESERVE_RHS.json` | 两模型变量/行/成本/RHS 对齐检查的完整结论 |
| `W1_CONSTRAINT_DIFF.csv` | 所有不同约束/变量/目标的清单（期望 RHS 唯一变化） |
| `N07_RESERVE_PROBE_PRE_RUN_MANIFEST.json` | 新代码与基线 SHA，诊断配置标准化 hash、预算、签名文本 |
| `W2_APPROVAL_REQUEST.md` | 最终正确 40 字符提交 SHA、研究者批准语句建议、准确预算、门禁意见 |
| `W2_RESERVE_CAUSAL_COMPARISON.csv` | 若批准已运行，按母线/年/采样类别比较缺供、成本、扩张、潮流与 SOC |
| `W2_RESERVE_CAUSAL_VERDICT.md` | 如已求解，解释右端 3000→0 的物理机制边界及差异 |
| `W3_S0_SCIENTIFIC_DECISION.md` | M 与 T 分开结论；需要的唯一后续科学决策 |
| `W3_FULLYEAR_DECISION_TABLE.csv` | 若需全年诊断，必要性、模型规模/内存预检、不同可行域限制 |
| `W4_A3_STATIC_READINESS.md` | 门禁+全部开发商/社会优化器调用接线、firm 屏蔽、S2 收敛 / matched-service 审计、剩余 GAP |
| `NEXT_07_RESULTS_INDEX.json` | 每个路径 / SHA / Git commit / 学术使用级别 / 求解次数 |
| `NEXT_07_RETURN_PACKAGE.zip` | 汇总本轮报告、表格、配置、清单、测试日志、轻量可读证据（大体量解文件只需 SHA + L2 路径，不必上传 GB 数据） |

### 固定报告状态块（必须置于执行报告最上方）

```text
WORK_PACKAGE: BYOP_NEXT_07
SOURCE_MAIN_SHA: bcd9844d (recheck before start)
START_HEAD: <actual full git SHA>
END_HEAD: <actual full git SHA>
ORIGINAL_S0_S1_CODE_SHA: cdfdea06146a6fe73df89cb410d6a88cb5fda306
W0_DATA_QA: PASS | FAIL | NOT_RUN
W1_RESERVE_RHS_ONLY_STATIC: PASS | FAIL | NOT_RUN
W2_NEW_SOLVER_CALLS: 0 | 1
W2_AUTHORIZATION: NOT_APPROVED | APPROVED
W2_SOLVER_AND_ACCEPTANCE: NOT_RUN | PASS | FAIL | INFEASIBLE
W2_RHS_CHANGED_ONLY: YES | NO | NOT_TESTED
W3_S0_RELIABILITY_VERDICT: BASELINE_RELIABILITY_UNRESOLVED | METHOD_BUG_CONFIRMED_REPAIR_REQUIRED | PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS | CALIBRATED_PASS
W3_FULL_YEAR_DIAGNOSTIC: NOT_AUTHORIZED | RECOMMENDED | NOT_NEEDED
W4_A3_RUNTIME_STATIC: PASS | PARTIAL | FAIL | NOT_RUN
A3_SOLVER_CALLS: 0
ORIGINAL_A2_LEDGERS_UNCHANGED: YES | NO
NEXT_DECISION_REQUIRED: <one concise action>
```

### 最终交付要求

1. 所有代码、配置、manifest、报告与非大体量文件同步 GitHub；**仅在 W2 求解版本已经完成或确定不会运行后**，才将 W4 静态开发分支合并回 `main`。完成交付时 `main` 与 L2 保持一致，列出真正用来求解的代码 SHA，不以最后报告提交 SHA 冒充冻结求解版本。
2. 不得只有日志与 PASS 结论；必须有可复核的数字、来源路径、对照模型检查、求解台账以及下一步建议。
3. 原始 S0/S1 研究结果始终保留；即使 RHS=0 使缺供大降，也不能直接把它改写成正式 S0。
4. 本轮重点是**回答一个具体因果问题**，不是把研究偏离到一般可靠性参数敏感度。尽快为四主情景 S0/S1/S2/S3 的可信比较创造条件。

---

## 研究者审核时只需要看的三项

1. **W0 是否彻底纠正 94% / 86.5% / ×25.86 的分母及采样权重解释？**
2. **W1 两个 S0 LP 是否真只差 `PV16M-reserve_req` 的 RHS？W2 实际缺供、潮流、SOC 和扩张对照为何变化？**
3. **S0 是否还需要年度代表性证明？A3 是否达到静态就绪、但在研究者批准科学基准前不误启动？**

**完成判据**：交付可审计的备用需求机制诊断（或明确阻断原因）、可信的 S0 下一步决定及 A3 静态就绪报告；无多余算例、无模型假设偷换、无虚假 PASS。
