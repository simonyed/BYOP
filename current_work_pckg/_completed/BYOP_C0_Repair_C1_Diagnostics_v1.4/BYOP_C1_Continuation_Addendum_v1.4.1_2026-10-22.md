# BYOP C1 续跑调整说明与执行指令 v1.4.1

日期：2026-10-22（America/New_York）

适用仓库：`simonyed/BYOP`，分支 `mainline-v13-stageA`。

审查基点：`03536646721c59c255ac284a614af503c155cd53`。

## 1. 与原工作包的关系

本文件是《BYOP C0 Repair / C1 Diagnostics v1.4》的续跑补充说明，不替代原工作包，也不重新启动已经完成的阶段。在原执行会话、原 L2 环境中继续工作，复用现有输入和求解结果。

本轮目标是修复结果收集与验收、分析已有输出、完成报告和交付。**本轮新增求解次数必须为 0。**此条对原 v1.4 尚未使用的诊断额度具有优先效力；不能因为原上限为 6 个诊断算例，就自动继续使用剩余名额。

本文件只编制续跑指令，不代表本会话已经修改代码、运行测试或启动求解。

## 2. 当前已经完成的内容

| 项目 | 审查基点的状态 |
|---|---|
| C0 分期识别、可切换容量和匹配置信度修正 | 已完成；历史资产数值未变 |
| C0 修正测试 | 10/10 通过 |
| 原 C0、Legacy、动态选址回归 | 分别 13/13、50/50、32/32 通过 |
| C1 不同诊断算例 | 4 个：两个年度 3h、两个峰值窗口 |
| 实际求解调用 | 共 8 次：4 次初始调用＋4 次记录在案的重试 |
| 最终采用的四组结果 | 全部 optimal；早期尝试保留为 superseded |
| C1 测试 | 最新提交日志为 5 项通过、1 项失败 |
| 正式总结报告 | 待完成 |

执行返回中曾出现“6/6 通过”，随后执行方增加非空与标签检查，最新提交又出现失败。应以最新代码、日志和重新验证结果为准，不能沿用早先的通过表述。

## 3. 给执行方的续跑指令

继续原 v1.4 工作，先核对当前 checkout SHA。若仓库已前进，检查以下问题是否已修复，避免重复修改；不回退、不覆盖新成果。按 A—D 顺序完成，不启动任何新的 optimize / solve / calibration 调用。

### A. 修复 collector 和验收逻辑

#### A1. 统一标签，修复当前失败测试

位置：`workflow/byop/post/c1_collect.py`。

当前代码先用 `M` 创建 `met`，随后才规范 `M` 内的 `kind`；后续修改列表不会回写已经创建的 DataFrame。因此 `C1_METRICS.csv` 仍保留 `annual/window`，测试却按 `ANNUAL_3H/PEAK_WINDOW_1H` 筛选，得到空结果。

应在构建 DataFrame 前统一标签，或直接规范 DataFrame 列，并统一 manifest、metrics、events、binding lines、line comparison、fuel tables 和 QA 的命名。不能仅放宽测试，接受两套隐式混用的标签。

本轮预期四个结果键为：两种网络 `C1_NETWORK_BASE`、`C1_NETWORK_CALIBRATED`，各自对应 `ANNUAL_3H`、`PEAK_WINDOW_1H`。

新增或完善检查：

- manifest、metrics 的键集合精确等于预期四键，无缺失、无重复、无额外结果。
- fuel 与完整 line comparison 表必须非空，覆盖应有组合，关联后不能为空或出现关键字段缺失。
- binding / shedding 事件表允许某个算例确实没有事件；此时须与该算例指标一致，不得为了通过测试伪造事件，也不能把空表当作无条件通过。
- 同一指标在逐 case 输出、汇总表和 QA 中一致；被 superseded 的尝试不进入最终比较。

#### A2. 修复 optimal 判定

当前 `termination.str.contains('optimal')` 同时会匹配 `suboptimal`。改为精确检查状态：`status == 'ok'` 且 `termination == 'optimal'`。

同时检查结果键完整性，防止空表的 `.all()` 返回 True。增加至少三个反例：`suboptimal`、缺少一个算例、空结果，均不得通过。

本项是验收漏洞修正；当前四组最终结果确实为 optimal，不需要因此重新求解。

#### A3. 重新收集和测试

使用现有逐 case 文件重建汇总表、QA 和图；运行必要的无求解测试及受影响回归，保留日志。新 QA 区分“求解终止状态通过”“数据完整性通过”“物理解释仍有局限”，不能用一个 all_optimal 字段代表全部验收。

### B. 使用已有结果排查 72.9 GWh 与 102 MWh 的差异

先定位两个数字的来源、案例配置、目标函数、网络状态和统计时间范围。原校准 residual 与 C1 结果不是天然相同的实验，不能只因相差较大就认定某一代码错误。

逐项对照并提供文件/函数/字段证据：

| 对照项 | 必须核查的内容 |
|---|---|
| 输电容量与阻抗 | 原校准求解时的 s_nom、x、r；结果写入网络后是否按容量缩放；C1 实际读取的数值 |
| 切负荷成本与其他成本 | 原校准参数与 C1 的 VOLL 35,685 USD/MWh、线路增容成本、目标函数构成是否相同 |
| 资产与运行约束 | 机组集合、可用率、最小出力、储能初末边界及全局约束处理 |
| 时间与计量 | 快照、权重、切负荷阈值、MWh 汇总范围及单位 |

输出逐母线、月份或季节、最大事件和连续缺口的定位结果，优先关注 p620 系列及 p630 2。用已有聚合结果和可读取的已保存结果继续分析；不为了导出变量而重新求解。

结论按证据区分：

1. 已证实的输入/代码差异；
2. 有相关输出支持、但尚未隔离的机制；
3. 只有假说、仍需独立对照验证的原因。

“阻抗缩放导致 72.9 GWh”目前属于待验证假说，不能写成已证明结论。两套 C1 网络的差异涉及增容线路的容量及对应阻抗，不应描述为仅改变热限额。

若现有文件不足以归因，报告未确定的具体原因，并提出最小对照设计、所需变量和预计求解次数即可。本轮不执行该对照，也不要求为了完成报告而强行闭合因果解释。

### C. 核查储能同时充放电和时间标签

#### C1. 储能运行

已报告的同时充放电重叠能量较大：未校准年度约 9.04 TWh，校准年度约 4.78 TWh。先检查该指标是否按同一储能单元、同一时段的充放电交集计算，时间权重和单位是否正确。

从已有输入/输出定位：

- 哪些储能单元、母线、时段贡献最大，是否涉及不同储能技术；
- 充放电成本、风光成本是否实际为负，相关下界、弃电权限和效率如何设置；
- 是否存在必须消纳的能量或最小出力，以及储能损耗吸收能量的可能性；
- 已保存文件是否包含逐单元充放电、价格/对偶和 SOC；缺少什么变量，哪些推断因此不能成立。

“负风电价格导致异常”不能仅凭现象确认，应区分输入边际成本与求解得到的价格。若没有相关输出，明确证据不足。

核查循环 SOC 与窗口 SOC 边界时使用状态转移方程；首时段 SOC 是时段结束值，不能机械要求它等于末时段 SOC 就认定年度循环成立或失败。

本轮不修改成本、不引入 MILP、不重新求解。若怀疑多解退化，可提出保持原目标值在数值容差内、再最小化储能吞吐量的连续 LP 验证方案，但不执行，不提前认定这是唯一修复方式。

#### C2. 时间标签与 1h 证据边界

- 现有事件表显示的 2030 年是模型坐标。保留该坐标，同时按源行顺序关联原始 2025 Native Load 的 HE 标签和源行号；不要宣称已经转换为 UTC，也不要丢掉 DST / 24:00 标签。
- 当前峰值窗口使用逐小时负荷，但风光出力把每个 3h 值保持三小时。因此统一标为“小时负荷＋3h 保持风光出力的补充窗口”，不能作为完整 1h 压力验证通过的依据。
- 最大净负荷窗口保持 `MISSING_INPUT`，说明缺少与当前模型出力一致、时间对齐的 1h 风光数据。本轮不伪造曲线、不新增窗口、不开展开放式资料搜索。

### D. 完成报告、同步产物并提交

新增或完成 `C1_FIXED_ASSET_DIAGNOSTICS.md`，至少包含：

1. 实际完成内容、四个有效算例及八次调用记录；
2. 汇总标签、精确 optimal 判定和非空验收的修复；
3. 两套年度结果及峰值窗口结果，切负荷空间与时间定位；
4. 与原 102 MWh 的可证实差异、尚未解决的因果问题；
5. 储能重叠运行的证据、已知局限及最小验证建议；
6. 分燃料发电量对照，明确静态模型与真实全年统计边界不同，不机械拟合；
7. 真实 1h 数据、年内投运/停机日期等缺口；
8. 后续优先事项及是否需要额外对照；不得提前宣称历史基准已通过全面校准。

将本轮小型交付件及报告按仓库规则同步到 `current_work_pckg`，更新 README 的完成/未完成状态；历史结果和 superseded 尝试保留，不覆盖。代码提交和报告提交分开，报告引用实际 code SHA。

## 4. 本轮禁止扩大范围

- 不新增求解、不重跑已完成算例、不自动用完原剩余额度。
- 不自动将 567.5 MW 候选迁入历史资产，也不自动处理 1,638 MW 状态冲突。
- 不把 Kiamichi 的 515 MW 快照净额直接作为 Firm 容量，不自行删除 Tenaska Gateway。
- 不更改历史资产数值、460.73 MW IT 继承负荷、未来 AIDC 分布和总量、POI / 天然气 / 成本 / ERM / VOLL。
- 不改变正式运行门控，不启动 S0–S3 或 B3。

## 5. 完成标准与固定回报

本轮允许完成“代码与数据验收＋报告”，同时保留“机制尚未被独立对照验证”的结论。缺少因果验证不等于必须继续求解，也不能用测试通过替代物理有效性判断。

```text
START_SHA:
CODE_SHA:
REPORT_SHA:
COLLECTOR_LABEL_FIX:
EXACT_OPTIMAL_AND_NONEMPTY_TESTS:
C1_TESTS_AND_LOG_PATHS:
NEW_SOLVER_CALLS_THIS_CONTINUATION: 0
EXISTING_SOLVER_HISTORY: 4 distinct cases; 4 retries; 8 calls total
72_9_GWH_VS_102_MWH_CONFIRMED_DIFFERENCES:
CAUSES_STILL_UNPROVEN:
STORAGE_FINDINGS_AND_MISSING_OUTPUTS:
TIME_LABELS_AND_1H_LIMITATIONS:
DELIVERABLES_AND_README_UPDATED:
HISTORICAL_OR_FUTURE_NUMERIC_INPUTS_CHANGED: NO
FORMAL_RUN_GATES_CHANGED: NO
MINIMUM_NEXT_DIAGNOSTIC_PROPOSAL:
```

模板冒号字段由执行方填写实际结果；它们不是模型数值输入。

## 6. 审查依据

- [最新审查基点提交](https://github.com/simonyed/BYOP/commit/03536646721c59c255ac284a614af503c155cd53)
- [结果收集代码](https://github.com/simonyed/BYOP/blob/03536646721c59c255ac284a614af503c155cd53/workflow/byop/post/c1_collect.py)
- [C1 测试代码](https://github.com/simonyed/BYOP/blob/03536646721c59c255ac284a614af503c155cd53/workflow/byop/tests/test_c1_fixed_asset.py)
- [C1 最新测试日志](https://github.com/simonyed/BYOP/blob/03536646721c59c255ac284a614af503c155cd53/workflow/results/BYOP/C1_FIXED_ASSET_DIAG/_l2_run/test_c1_fixed_asset.log)
- [C1 运行指标](https://github.com/simonyed/BYOP/blob/03536646721c59c255ac284a614af503c155cd53/workflow/results/BYOP/C1_FIXED_ASSET_DIAG/C1_METRICS.csv)
