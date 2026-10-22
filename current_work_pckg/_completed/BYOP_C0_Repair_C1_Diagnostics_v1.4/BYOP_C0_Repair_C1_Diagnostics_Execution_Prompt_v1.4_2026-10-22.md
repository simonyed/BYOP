# BYOP ERCOT：C0 审计修正与 C1 固定资产诊断执行 Prompt v1.4

日期：2026-10-22（America/New_York）

用途：将下文直接交给负责代码修改和程序调试的 Codex / Claude 执行。本文件是下一轮建议执行指令；编制本文件时没有修改仓库或运行优化器。

## 直接执行指令

你负责 `simonyed/BYOP` 的代码修改、输入审计和程序调试。本轮先修正 C0 的资产识别与报告口径，再在独立目录开展限定范围的 C1 固定资产运行诊断。完成本文件规定的工作后提交代码和结果，不运行正式 S0/S1/S2/S3 或 B3，不自行开展历史装机重标定。

### 1. 起点、研究边界和资料分工

- 目标分支：`mainline-v13-stageA`。编制本文件时 HEAD 为 `53aa883c4b71cfbf16c6024cade3994894b2e195`，C0 主要代码提交为 `be31ab62904a29efba76d20c8b763682c061ec7e`。
- 开始时记录真实 checkout SHA、工作区状态和本轮差异；若 HEAD 已更新，先检查相关改动，不回退、不覆盖他人工作。
- 接受 C0 已完成的官方负荷复算、历史 AIDC 证据分类及输电增容分账；不重做已经通过的资料采集。
- 只加强截至 2025 年的事实、初始资产和固定资产运行表现。2026 年及以后的 AIDC 项目预测冲突、16 母线地理分配、权重、POI 日期、天然气代理与风电曲线缺口不在本轮修改范围。
- 保留 460.73 MW IT 继承负荷的原数值及原母线，继续标记为历史容量估计推导的负荷代理。2025 年不重复加入 AIDC 存量。
- 研究方负责开放式资料采集与统计口径裁定。执行方使用已提供的官方原件、派生表、本地 ReEDS DB 和既有网络；缺证据时返回具体机组 ID、字段、容量和需要核实的问题，不把整项任务退回成“请重新收集全部数据”。
- 不修改 ERM、VOLL、技术成本、未来负荷总量或正式情景参数来使结果好看。

### 2. 执行顺序与求解范围

阶段 A：C0 修正及回归测试，求解次数为 0。

阶段 B：阶段 A 的必要测试通过后，实施下述独立 C1 固定资产诊断。C1 可以运行本文件列出的运行调度 LP；正式情景运行门控继续保持 `NOT_APPROVED`。另设 C1 专用配置和检查，不通过修改全局门控来放行。

阶段 C：形成解释与后续资产修订建议，提交 GitHub，停止。不得据诊断结果自动新增、删除或迁移历史机组，也不得自动重跑 B3。

若仓库已有本文件未覆盖的强制运行限制，先完成全部无求解工作和可审核的 C1 配置，准确返回冲突条款；不能擅自绕过，也不因一项受阻而放弃其他独立任务。

## 阶段 A：修正 C0 审计逻辑

### A1. 修正园区与分期混合，撤回 2.97 GW 的确定性解释

检查 `workflow/byop/build/c0_anchor_audit.py` 的 `norm_tokens()`、`match()`、`generator_match()`、`pipeline_suggestions()` 和覆盖率统计。

当前 `pipeline_suggestions()` 只检查同一园区 `cdr_core_2025_MW > 0` 且 `model_committed_MW > 0`，会把历史一期与未来扩建误认为同一资产跨账本。以下记录必须成为实际数据回归案例：

| 园区 | CDR 历史容量 MW | 模型 active2025 MW | 模型 committed MW | 应有处理 |
|---|---:|---:|---:|---|
| Callisto | 203.0，一期 2024-08-15；二期另列 PLAN | 200 | 400 | 不能因为一期运行而迁移二期 |
| Tidwell Prairie | 204.0，2025-06-01；后续扩建另列 PLAN | 200 | 200 | 区分已覆盖历史容量与未来分期 |
| Padua | 51.1，2025-07-28；后续 Unit 2/3 为 PLAN | 50 | 200 | 不能把整个园区当成历史漏项 |

这三项历史容量共 458.1 MW 被计入原 2,971.68 MW 建议汇总；它们已经有相应模型历史容量，不能据此认定未来 committed 都应迁移。两边 MW 口径不同，不能把 203−200 等差额直接当新增资产。

修正要求：

1. 保留原始名称、项目分期、UNIT CODE、INR、EIA plant ID、ReEDS Unique ID 和日期。园区规范名只用于候选搜索，不能丢掉全部数字后直接确认机组身份。
2. 将 `identity_match`、`phase_match`、`historical_status`、`capacity_basis`、`reclass_action` 分开记录。名称相似不等于分期相同，运行状态不等于容量额定口径相同。
3. 园区内同时存在历史装机与未来扩建时，默认输出 `MIXED_PHASE_REVIEW`；只有取得同一机组/分期的证据，才可输出待研究方审核的迁移建议。
4. 只有名称或容量候选时使用 `CANDIDATE` / `UNRESOLVED`，保留现有模型数值。诊断字符串不得进入数值矩阵；不得填虚构的 MW、日期或机组 ID。
5. 原建议表中其余相关记录为 `OPER-SYN`。分开记录状态、发布日期和 in-service 日期，不能将其统一升级为已核实商业运行或全年可用容量。
6. 新报告将 2.97 GW 称为“旧园区级规则触发的待审查总量”，并另报修正后的分期级建议。不得仅减去 458.1 MW 后把余量全部认定为已确认漏项。

### A2. 正确核算可切换机组，保留调整行身份

官方提取表中 Kiamichi 的 SWGR-AVA 正数合计 1,400 MW，SWGR-UNA 调整合计 −885 MW，快照净额为 515 MW；模型为 1,224 MW 夏季口径。

1. 按基础 UNIT CODE、站点及调整记录配对，保留原始代码；可去掉 `_UNAVAIL` 等后缀生成辅助配对键，但不能覆盖原值。
2. 区分物理机组行和不可用调整行。负数调整不是新增负发电机组，也不能直接丢弃。
3. 单独输出物理容量、不可用调整、快照净额、模型夏季容量及可比性说明。防止重复扣减、重复计容和将净额再次扣减。
4. 同样检查其他可切换资源，不能简单把所有 SWGR 都排除或全部计入公共 Firm 资源。
5. 515 MW 只作为该表的审计净额，不自动作为可靠容量认证，也不直接替换模型的 1,224 MW。本轮不修改 Kiamichi 资产数值；C1 报告明确其可用状态尚待口径裁定。

### A3. 修正匹配置信度与容量差额解释

1. 把名称模糊匹配、跨县名称匹配与有明确 ID/别名证据的确认匹配分开。现有 81.0% 不能直接表述为逐机组身份已核实。
2. 继续按条数和 MW 报告覆盖率，明确分母、是否包括 qualified 状态及容量口径。
3. 容量桥接恒等式闭合只证明账本算术一致，不能证明机组身份和容量差额成因正确。`rating_diff` 改为说明其可能混合额定口径与分期覆盖差异，未经证据不能全部归为额定差。
4. 年报与 CDR core 的约 24.4 GW 残差保持未解释；不要写成已证明全部来自范围差异，也不要据此全网放大容量。
5. 对“模型 active、CDR 非 core”分开标记 DGR、私人网络、季节性、可切换、未来重整/扩建及真正状态冲突；不要将约 6.37 GW 全部标为应删除资产。特别注意未来 repower 记录可能与同站旧机组同名。

### A4. 必要测试与产物

新增真正能识别上述失败模式的测试：

- 同园区“历史一期已覆盖＋未来二期 PLAN”不能触发二期迁移；覆盖上表三个实际案例。
- OPER-SYN、缺日期及未来日期分别处理，不能自动认证为 2025 已商业运行。
- SWGR 物理行与负数调整只配对/扣减一次；Kiamichi 快照净额重现 515 MW，模型数值仍为 1,224 MW。
- 未确认跨县名称候选不升级为 ID 确认匹配；同站未来 repower 不吞掉旧机组身份。
- 历史负荷不重复、分期/机组不重复计容、输电增容不重复，以及旧版与动态选址回归仍通过。

保留旧 C0 结果作为 v1.3 快照，输出修订结果和 before/after 差异。推荐文件：

- `C0_REPAIR_REPORT.md`
- `C0_PHASE_RECONCILIATION.csv`
- `C0_SWITCHABLE_LEDGER.csv`
- `C0_MATCH_CONFIDENCE.csv`
- `C0_RECLASS_REVISED.csv`
- `C0_REPAIR_QA.json`

## 阶段 B：C1 固定资产运行诊断

### B1. 先建立可审计配置和两套网络

输入均使用同一份现有 2025 fleet、同一份负荷与出力数据，不应用阶段 A 的待审查资产变更。诊断中最多改变网络是否含既有 2025 合成增容。

| case_id | 网络容量 | 用途 |
|---|---|---|
| C1_NETWORK_BASE | 已有 `reeds_sum` / interface rule 容量，不含 2025 calibration uplift | 判断未加合成增容时的瓶颈 |
| C1_NETWORK_CALIBRATED | 同一网络加既有 18 条、合计约 4,993.9 MVA 的 2025 uplift | 判断旧增容缓解了什么问题 |

两者都排除 2026 起的 `AC_s0cal` Links、未来机组、未来负荷及所有新增建设变量。两者资产容量、需求和出力序列的非目标部分必须一致。

注意：`build_2025_baseline_tamu.py --no-calibration` 是跳过重新求校准 LP；它不等于从已经保存的网络里自动移除历史 uplift。必须逐线路核验两个 case 的容量组成，不得覆盖旧 prepared.nc。优先从现有网络和账本构造诊断副本，避免无关重建。

### B2. LP 物理边界

- 固定发电、储能、线路与 Link 的装机容量；所有扩容变量关闭，断言 `*_nom_extendable=False`，并检查实际优化变量中没有建设变量。
- 只允许运行调度、合法储能充放电及显式记录的诊断切负荷。禁止自动购入容量、放宽线路限制或绕过功率平衡。
- 使用现有燃料价格、运行成本、VOLL 和技术运行参数；两案完全一致。
- 保留能量守恒和储能效率，核验同时充放电及终端 SOC；年度两案使用相同的循环/边界规则，不能通过免费初始电量弥补缺口。
- 固定资产切负荷应原样报告，不自动进入增容校准，不把求解最优终止等同于无缺电。
- 该诊断验证运行供电与网络可送达性，不能单独认证 Firm 取电权、POI 资格、N−1 安全或概率资源充裕度。

### B3. 明确时间口径

先运行两套全年 3h 对照，使用 2,920 时段和权重 3。结果必须标为“既有模型 2025 fleet 的固定资产诊断”。

如已具有逐机组真实日期和可用状态，可以另形成按年内投运/退出日期裁剪的回放；没有这些证据时，不把当前静态 fleet 称为真实全年历史回放。也不能把年末资产默认全年运行，再据此声称复现历史。

随后仅选两个连续 72h 窗口做 1h 检查：原始负荷峰值附近、原始数据中最大净负荷附近。重叠则合并。后者必须用已存在且时间对齐的 1h 风光数据计算；拿不到时明确标记缺项，不以 3h 插值冒充实测 1h 曲线。

两个网络使用相同窗口、出力、负荷及储能边界。每个 72h 窗口前 24h 作为缓冲，后 48h 为主要评价区间；初始 SOC 使用有来源的年度结果衔接规则，并披露边界敏感性。不得给每个窗口任意满电。

如缺少真实 1h 出力或合法初始状态，只完成不依赖这些数据的诊断并返回明确字段，不扩大为新一轮资料搜索。

### B4. 求解范围和回报指标

基础两次年度 3h LP；最多两个窗口×两个网络的 1h LP。本轮最多 6 次正式诊断求解。失败调试重试另计，记录原因；若需要新增算例，先写明必要性，不自动扩展为情景扫描。

逐 case 报告：

- 求解状态、实际求解次数、运行时间及配置/输入 SHA；
- 切负荷 MWh、最大 MW、发生小时/时段、母线与连续缺口时长；
- 线路利用率、约束时段和重点拥塞走廊；
- 分燃料发电量、风光弃电、储能充放电和 SOC；
- 功率平衡残差、容量是否固定、既有 uplift 是否只加载一次；
- 两案差异及其能够支持的结论，不能支持的部分明确写出。

官方分燃料月度/年度数据可作运行结构参照，但先解释口径；不调整参数来机械拟合。不要把历史 102.2047 MWh 残余切负荷预设为新诊断必须复现的数值。

若仍有缺电，只根据输出定位容量、燃料/可用率、网络、时间对齐或储能边界问题。没有对照证据时写“尚无法区分”，不直接归因为电网物理短缺。后续可提出独立放松网络对照建议，本轮不额外求解。

推荐输出：`C1_FIXED_ASSET_DIAGNOSTICS.md`、`C1_CASE_MANIFEST.csv`、`C1_METRICS.csv`、`C1_SHEDDING_EVENTS.csv`、`C1_BINDING_LINES.csv`、`C1_GENERATION_BY_FUEL.csv`、`C1_QA.json`，以及配置、必要日志和主要结果图。

## 阶段 C：提交、下一步建议和停止条件

1. 小型代码、配置、审计表、报告和必要日志按仓库规则提交；大型 nc/原始文件保留既有数据管理方式，附 SHA 与可访问位置。不要把个人机器路径作为代码依赖。
2. 不覆盖旧 B3、v1.3 C0 或原 prepared.nc。对正式门控、未来预测和历史数值输出“未改变”检查。
3. 提交后报告真实 code SHA；先写代码提交，再以独立报告提交引用该 SHA，避免在同一提交里伪造自身 SHA。
4. 返回少量优先级明确的历史资产修订建议：确切受影响机组、证据、额定口径、预计影响、缺失材料。不要要求全量 24.4 GW 残差解释完或 100% 匹配后才承认诊断有效。
5. 资料需求回研究方；代码、测试和已经具备输入的诊断由执行方完成。不得把未获取的场址电表或真实线路全量参数作为全部工作的前提。
6. 完成本轮后停止。正式历史资产数值修改、重新校准、S0/S1/S2/S3 与 B3 重运行不属于本轮。

### 固定回报格式

```text
REPOSITORY_AND_BRANCH:
START_SHA:
CODE_SHA_AND_REPORT_SHA:
MODIFIED_FILES:
C0_PHASE_BUG_FIXED_AND_REAL_CASE_TESTS:
OLD_2971_68_MW_RECLASSIFICATION_EXPLAINED:
SWITCHABLE_LEDGER_AND_KIAMICHI_1400_MINUS_885:
MATCH_COVERAGE_BY_CONFIDENCE_UNITS_AND_MW:
C0_TEST_RESULTS:
C1_CASE_INPUT_SHA_AND_NETWORK_DIFFERENCE:
C1_TIME_BASIS_AND_SOC_POLICY:
C1_SOLVER_EXECUTIONS_AND_RETRIES:
C1_SHEDDING_AND_CONGESTION_COMPARISON:
C1_QA_AND_MISSING_INPUTS:
HISTORICAL_NUMERIC_ASSETS_CHANGED: NO
FUTURE_AIDC_INPUTS_CHANGED: NO
FORMAL_S0_S3_OR_B3_RUN: NO
EXISTING_FORMAL_RUN_GATES_CHANGED: NO
RESEARCHER_EVIDENCE_REQUESTS:
NEXT_RECOMMENDATION:
```

上述冒号字段由执行方用实际结果填写，它们是回报模板，不是可传入模型的数值输入。

## 审查依据

- [C0 执行报告](https://github.com/simonyed/BYOP/blob/53aa883c4b71cfbf16c6024cade3994894b2e195/current_work_pckg/C0_INPUT_RECONCILIATION.md)
- [C0 审计代码](https://github.com/simonyed/BYOP/blob/53aa883c4b71cfbf16c6024cade3994894b2e195/workflow/byop/build/c0_anchor_audit.py)
- [原分期调整建议](https://github.com/simonyed/BYOP/blob/53aa883c4b71cfbf16c6024cade3994894b2e195/current_work_pckg/C0_PIPELINE_RECLASS_SUGGESTIONS.csv)
- [CDR 官方记录提取表](https://github.com/simonyed/BYOP/blob/53aa883c4b71cfbf16c6024cade3994894b2e195/workflow/byop/inputs/anchor2025/CDR_DEC2025_UNIT_REGISTER_AUDIT_ONLY.csv)

本轮结论应服务于后续共同基线的可信度，不能提前解释成 BYOP 的提速收益或长期社会成本结果。
