# BYOP Post-v1.6 — A0.1 修复与 A1 授权前核查指令

版本：2026-10-22 | 面向分支：`simonyed/BYOP` / `mainline-v13-stageA`

## 0. 本轮研究决定及权限

- A0 阶段予以验收：代码提交 `453e846f`、`80e1835f`，报告提交 `946406d15f016bf6eb7dd37ae11d4ce99ead673d`。以执行时 GitHub 分支 HEAD 实际值再次核查，不覆盖他人新提交。
- 本文件**仅授权 A0.1 零求解器修复与测试**，不批准 LP-R、LP-N、S0–S3、旧 `step0` 或参数敏感性，也不允许修改任何运行授权字段。
- v1.6 2025 基线 `.nc` 继续冻结，SHA-256 `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`；不能调整 2025 机组容量、线路热限额、x/r 或既有负荷以求出好看的 headroom。
- 同意 A1 的**暂定研究代理参数**：统一上调备用 3000 MW，能量持续时间 1 h，响应 10 min；CCGT p_min 50%、爬坡 4%/min，OCGT 40%、10%/min，coal/gas_steam/biomass 40%、2%/min。hydro/battery 继续沿用 A0 类别设置，wind/solar/nuclear/负荷削减不计入备用。未建模 MORA 强迫停运分位数，不能声称 ERCOT 可靠性认证。参数不必修改现有 CSV；保留其 `PENDING` 证据分类，但增加研究者本轮“准许用于 A1 物理代理”的决定记录。
- 460.73 MW IT 的 end-2025 inherited ramp 暂按 A0 处理为 protected existing load；文档必须标注 Native Load 2025 对该年内上电负荷可能已经有部分覆盖，A1 不被定义为历史复盘或无偏净负荷预测。不得擅自从历史 Native Load 中减去猜测的 AIDC 数量。

## 1. 必须修复的代码逻辑（A0.1，不调用求解器）

### FIX-01：最大接入能力的严格目标及既有负荷保护

目前 `workflow/byop/model/post_v16_headroom.py` 通过 `EPS_COST * dispatch_cost + SHED_W * existing_shed - lambda` 的加权目标计算 headroom。该目标不能保证全体情形下最优 `lambda` 等于真实最大可行新增容量，且既有负荷损失只是罚项。

要求：A1 专门作为物理容量问题，**直接最大化 lambda**，不把能量费用当成可能改变最大容量的目标。将原有 `load_shed` 发电变量的出力明确固定为零（保留变量、强制零约束或删除都可；每个方案应保持可测试的既有负荷保护）。必须在 B0、BL 两类时段和 LP-R、LP-N 两个网络模型中都保证零切负荷。禁止为了恢复可行性而调低 3000 MW、改备用时长、免费增强 2025 网络或“容忍”额外客户损失。

若零切负荷硬约束造成模型 infeasible，则报告 `BASELINE_OR_STRESS_INFEASIBLE`，依据 LP-R/LP-N 所在阶段分辨资源侧与网络侧并停止；不得自动复跑或凭猜测说是 AIDC 导致。最大化目标无成本次级目标时，多解下的单次线路利用与发电调度只能称作 **optimal witness dispatch**，不能用于唯一拥塞归因或电价分析。

静态测试要求：校验 `m.objective` 的系数不再含可改变 lambda 最大值的成本或软弃供权衡；校验任何已有负荷削减变量上下界均为零或存在零出力硬约束；检查 `lambda` 仍为同一全局变量、权重仍为 16 母线标准化的固定负荷分布。不得将 `lambda` 改为可重选母线的单独变量。

### FIX-02：LP-R → LP-N 严格验收门禁及结果校验

当前 `workflow/byop/model/post_v16_gate.py` 仅要求上阶段求解 `status=ok`、`termination=optimal`，未要求 B0、BL 均通过零切负荷校验；`workflow/byop/run/post_v16_a1.py` 的 `combine()` 即使判断 `H_network > H_resource + tolerance` 仍只打印 `False`。

要求：LP-N 必须只在 LP-R `status=ok`、`termination=optimal`、**pass=true**、双方 B0/BL 零切负荷及全部 LP-R 验收检查成立之后才允许启动；后处理出错或结果文件缺失也必须拒绝。LP-N 完成后，应检查双方均 `PASS`、`lambda>=0`、`H_network<=H_resource+1e-3 MW`、守恒残差在预先明确的数值容差内，否则返回 `A1_BLOCKED`，不得报告成功。

要求保存 LP-R 验收报告 JSON，写入是否具有非空输出、缺失或非有限数值以及 `lambda` 是否意外触及 200000 MW 人工上界。任一异常停机后零重试。

静态测试：构造伪造日志/JSON，涵盖 `optimal + positive shed`、`optimal + missing result`、`optimal + no PASS`、`H_network > H_resource`、`nonoptimal`，均必须得到预期的拒绝或 `BLOCKED`，不调用优化器。

### FIX-03：预算日志必须在调用求解器前持久化

当前 `post_v16_a1.py` 在 `solve_model()` 返回后才记录一条运行，若进程在求解中断开，门禁不能识别已经使用的调用预算。

要求：优化器每次启动前原子写入 `HEADROOM_SOLVE_LOG.csv` 或等价稳定台账中的 `STARTED` 行（附 UTC 时间、stage、attempt、基线与代码 SHA）；写入并持久化成功后才允许调用求解器。正常返回后在同一 attempt 上补写结果和状态。异常退出、被杀死、遗留 `STARTED` 或损坏日志均视为已消费调用、不能自动重跑。禁止将日志行删除以绕过预算。阶段结果与台账必须一致。

静态测试：模拟 `solve_model` 抛异常及保留 `STARTED` 后重新进入，确认本阶段被拒绝；测试总预算两次和阶段顺序。不得在 A0.1 中调用真正求解器。

### FIX-04：失败后保留证据

`post_v16_a1.py` 应把状态、求解返回码、当前结果摘要及已经生成的可读诊断尽可能落盘，并区分 `solver_failed`、`output_failed`、`acceptance_failed`、`baseline_pressure_infeasible`。求解成功但后处理异常也不能算 `PASS`，更不能悄悄重新求解。若选择保存求解解或最小必要调度证据，应记录文件 SHA、生成范围、输出量大小，不强制保存巨大 NetCDF。

## 2. 解释边界——不要求现在增加新情景

1. A1 的 LP-R、LP-N 是**2025 冻结装机、2025 负荷、不同天气来源风光曲线**下的静态联合接入上限，不是 2026–2031 的逐年可接入能力，不可直接与 2029 有新增 POI 升级的账本拼接后称作真实 2029 headroom。
2. `H_POI=0`（2026–2028）是**16 个母线以同一个 lambda 固定比例联合增量**和若干母线零既有 POI 资格的数学结果，不能推断 ERCOT 全区没有任何可先行并网的数据中心。在 A2/S1 中应允许按站点具体资格、分期 COD 逐年交付，不得将共同 lambda=0 直接变成所有站点 zero service。
3. 储能备用已使用实际调度 SOC，优于旧 ERM shadow SOC；但 72 h 分段循环 SOC、LP 放松在线机组、未使用 MORA outage、系统合计备用而未验证备用投运后的网络输送，仍须保持公开局限。此阶段不是资源充裕度、LOLE、N-1 或 ECRS 资格认证。
4. 若 LP-N 即使 lambda=0 也不可行，不允许沿用旧 S0CAL 为此免费加线；应返回具体阻塞证据供研究者决定是否有物理修复依据。

## 3. A0.1 交付与停止条件

1. 只修改相关代码、测试和文档；不得变动 2025 baseline/既有用户负荷/POI 权利/天气窗口/技术容量；如仅修复 objective、gate、ledger，不需要重新整理原来的 53 个数据文件。
2. 在 L2 执行全部静态测试和 `--dry` 双模型结构检验，输出 `A0_1_REPAIR_REPORT.md`、`A0_1_TEST_SUMMARY.json`、`A1_GATE_VERDICT.json`、`A1_MANIFEST_REBUILT.json` 或对应 manifest，并提交 GitHub commit。明确 `solver_calls=0`。
3. 重新生成 manifest 所需 code SHA，保持 v1.6 baseline 与 inputs SHA；A1 授权字段仍是 `NOT_APPROVED`、`null`、`null`。若仅修改许可 config 的三项字段，normalised config SHA 应不变。
4. 报告必须含 `PRE_RUN_STATUS=READY_FOR_RESEARCHER_APPROVAL` 或 `BLOCKED`、修改提交 SHA、测试总数、0 solver 调用、三个 FIX 的静态验证与 LP-R/LP-N DRY 结构摘要。
5. **到此停止**。只有研究者在回看 A0.1 报告后，单独明确授权 A1、填写审核人与代码 SHA 并提交审批 config，执行方才可调用 LP-R。LP-R 通过全部验收后才可进行 LP-N（累计最多 2 次，0 重试）。

## 4. 执行时的建议提醒

不要因为 A1 最大容量为零或 LP-N infeasible 就反复调整参数。研究目的是可靠地区分冻结基线的系统物理上限、具体输电限制和 POI/COD 资格，不是事先假定一定能展示大幅 BYOP 提速效果。A1 结束才决定 A2 怎样把新备用和正确的未来付费扩张接入动态规划。
