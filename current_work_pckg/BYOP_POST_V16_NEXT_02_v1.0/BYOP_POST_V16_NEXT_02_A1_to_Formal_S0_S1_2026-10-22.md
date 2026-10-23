# BYOP ERCOT：A1 正式求解与 S0/S1 主线仿真准入工作包（NEXT-02）

**版本**：2026-10-22 · NEXT-02 v1.0  
**交付对象**：Codex / Claude / 具备 GitHub、L2 与 PyPSA-USA 环境的执行方  
**仓库**：<https://github.com/simonyed/BYOP>  
**A1 冻结主线**：`mainline-v13-stageA`，已报告 HEAD `b2b2e48e`（执行时重新获取完整 SHA）  
**A1 已核验的可授权代码基点**：`802c9d9414514641fd2b088b45ec7ea945be18a4`  
**A2 静态开发分支**：`work/a2-postv16-static`，代码提交 `ba73e600aa260b8f09ee9bd0d0084a98431c98d1`  
**基线**：`workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`（L2），SHA-256 `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`  
**主要依据**：`current_work_pckg/NEXT_STAGE_EXECUTION_REPORT.md`、`A1_PREAPPROVAL_GATE.json`、`A2_STATIC_INTEGRATION_REPORT.md`、`A2_READINESS_MATRIX.csv`、`ENVIRONMENT_MECHANISM_LIMITATIONS.md`、`论文顶层设计.md`。

> **首要授权边界**：本 Markdown 是执行规范及求解申请说明，**本身不是研究者的求解授权**。目前 A1/A2/A3 仍为 `NOT_APPROVED`。执行方可以立即完成只读复核、可审计的代码修复与静态测试，但不得仅凭本文件填写 `approved_by`、把 `run_authorization` 改为 `APPROVED`、删除门禁、或开始任何正式 LP。**A1 的两次 LP 需要研究者明确批准；S0/S1 需另行批准；S2/S3 再另行批准。**

## 0. 本轮目的与研究范围

本轮不再重复 A0–A0.2 和 NEXT-01 已完成的参数收集、技术表建设及 40 项结构检查，而是将研究推进到《论文顶层设计.md》中的四个主反事实场景：

| 情景 | 含义 | 本轮位置 |
|---|---|---|
| **S0 — No New AIDC** | 保留既有负荷和存量数据中心，不增加研究期新增 AIDC | A2 首轮正式 LP |
| **S1 — Grid-Only** | 新增 AIDC 只依靠电网、受到分站 POI 与公共建设进度限制 | A2 首轮正式 LP |
| **S2 — Developer-Driven BYOP** | 开发商以最早投运/交付服务为优先，随后最小化私人成本 | 本轮仅接口审查，待 A3 授权 |
| **S3 — Coordinated Planning** | 相同物理资源集合下的社会协调规划 | 本轮仅接口审查，待 A3 授权 |

主要对比依然是 **S1−S0（AIDC 对公共扩张）、S2−S1（BYOP 速度与公共投资反馈）、S2−S3（私人—社会效率差异）**；最终需做 matched-service，且继续追踪 2036–2050 长期资产状态。本轮首个正式小案例限于 **ERCOT、16 个研究母线、2026–2031、mid 需求、单一冻结气象口径、LP-only**。不启动全国模型、Low/High 扫描、批量敏感性或长期 2050 扩展。

**本轮三个清晰终点**：

1. 完成 A1 两次 LP（如获独立授权），报告可靠的资源/网络容量结果或明确的物理不可行原因；
2. 修复和验收 A2 多年 S0/S1 的**必要**物理与经济约束，提交可运行的独立 gate，而非无条件打开旧主程序；
3. 获 S0/S1 的**单独**求解授权后，运行各一次 LP，形成第一份正式场景比较；完成之后停止，提交 S2/S3 准备情况及下一轮申请。

## 1. 当前进度与不可改变的事实

- NEXT-01 的 P0 已通过：A1 manifest、五个代码文件和十个输入文件的哈希、v1.6 `.nc` 哈希均已核对；两种 A1 模型各 **373,249 变量 / 967,980 约束 / 0 整数**；共同 16 母线权重和为 1；最大化 `λ`；既有负荷 hard zero shed。**A1 从未调用求解器，也没有 `H_resource/H_network` 结果**。
- A1 资源/网络 LP 仍需要 `run_authorization`、`approved_git_sha` 和 `approved_by`；A1 代码基点 `802c9d94` 后主线只提交了报表与审计，不应混入 A2 代码。
- A2 静态分支有 3 GW 系统备用、共 1,818 条可扩张候选台账、6 条双向已承诺公共 Link、16 站 × 6 年的风光储 Firm 构建；S0/S1/S3 静态测试 **40/40**，8 项新增单测通过，**零 solver**。
- A2 分支全量回归 **202 passed / 2 failed**；两处为不同 checkout 换行符导致的原始字节 SHA 不一致。尚未达到“所有回归通过”。
- `rearch_mech.py --post-v16` 仍以 `POST_V16_MAINLINE_NOT_READY`/exit 3 拒绝正式 A2 求解；这一失败关闭状态是设计要求，不得提前取消。
- 技术 v2 的环境作用主要是 **NOx/许可资格 → 许可工期 → 实际 COD → 可交付服务**，没有统一的环境税。现有 16 个母线的静态许可延迟均为 0：这是**L2 气源工期代理主导**的模型结论，而非 Texas 实际许可证件的因果识别。

## 2. W1 — A1 联合接入容量：审批后立即执行

### 2.1 审批前最后一次只读核查（无需 solver）

在 **A1 L2 主 checkout**、而非 A2 worktree 中执行：

1. 读取 `git rev-parse HEAD`、`git status --short`、`current_work_pckg/A1_PREAPPROVAL_GATE.json`；从该 checkout **重新**检验 manifest、冻结 `.nc`、授权来源、正规化配置及受控源码输入 SHA。旧 JSON 只能作历史证据，不得代替新核查。
2. 确认 A1 账本 `results/BYOP/POST_V16_A1_HEADROOM/HEADROOM_SOLVE_LOG.csv` 不存在旧 `STARTED/DONE/ERROR` 行；任一历史 solver 尝试计入预算，禁止清空账本。
3. 确认 1 小时 432 snapshots、B0+BL、三组事前指定压力窗口、3 GW/1h reserve、完整硬零 existing shed、`max λ` 目标、`LP-R` 线路放宽与 `LP-N` 冻结线路上限均不变。
4. 检查新的主线 HEAD 若非 `802c9d94`，只有报告/非受控路径变化；由当前 gate 证明祖先 SHA 可接受。**不能自动把最新 HEAD 当成被批准提交。**
5. 不修改原始 2025 网络、2025 Native Load、460.73 MW 既有 IT ramp、气象、可靠性代理来强迫求解可行。注意 v1.6 年度既有 111.8 MWh residual shed 与 A1 压力/备用口径不同，不能据此预判可行性。

安全入口（L2 的 `pypsa-usa/workflow/`）：

```bash
bash byop/run/run_post_v16.sh a1_dry     # create_model，不执行 solver
bash byop/run/run_post_v16.sh a1_gate    # 显示拒绝原因
```

### 2.2 **研究者独立授权节点 A1-APPROVAL**

执行方先提交 `A1_FINAL_APPROVAL_REQUEST.md`：实际主线完整 SHA、基线 SHA、manifest、空账本、两个命令、拟用线程数、错误停止规则。研究者同意后，**只允许**在 `workflow/config/config.byop_post_v16_a1.yaml` 修改以下三个字段并提交 config-only commit：

```yaml
post_v16:
  run_authorization: APPROVED
  approved_git_sha: 802c9d9414514641fd2b088b45ec7ea945be18a4
  approved_by: <研究者本人明确提供的批准标识>
```

本段是**获得授权以后**的目标配置示意，不准由执行方代填批准人或把其当作现成授权。若批准时基点、受控文件或账本发生漂移，则返回研究者重新审批。

### 2.3 正式求解次序（合计最多两次 solver，0 重试）

```bash
# L2：在冻结的 A1 checkout 上运行，线程数按执行前实际资源情况确定
THREADS=<批准的合理线程数> bash byop/run/run_post_v16.sh a1_lp_r
# 只有 LP_R_H_RESOURCE_RESULT.json 每项 acceptance PASS，且 ledger 为 DONE/ok/optimal/pass
THREADS=<批准的合理线程数> bash byop/run/run_post_v16.sh a1_lp_n
```

`STARTED` 行必须在 solver 前持久落盘；一旦中断、崩溃、不可行或未最优，**不重试、不删日志、不自动调整参数**。LP-R 失败时不运行 LP-N。LP-N 失败时停止，不报告 `H_network=0`。

每个阶段检查：`status=ok`、`termination=optimal`、零 existing shed、备用满足、节点平衡残差 ≤1e−3 MW、`λ` 有限且低于人工上界；联合结果需 `0≤H_network≤H_resource+1e−3 MW`。如 B0 既有系统不可行，分类为 `BASELINE_PRESSURE_INFEASIBLE_RESOURCE/NETWORK_SIDE`，**不得将其解释成 AIDC 零接入容量**。

### 2.4 A1 必要产物及暂停点

至少保存 `HEADROOM_SOLVE_LOG.csv`、`LP_R_H_RESOURCE_RESULT.json`、若有则 `LP_N_H_NETWORK_RESULT.json`、`A1_RESULT.json`、`JOINT_HEADROOM_RESOURCE_NETWORK.csv`、预注册压力时段和逐母线结果、失效诊断、solver 原生日志、授权配置与 SHA；报告 `H_resource`、`H_network`、差额、瓶颈时间和固定权重。

A1 的结果是 **固定 2025 电网与 16 母线比例增长下的联合可交付容量代理**，不是 ERCOT 官方逐站可并网审批。纯最大化 `λ` 的调度 witness 不唯一，不得将其 LMP/对偶变量当作已证明的经济价格。**完成 A1 后 STOP，汇报研究者；A1 批准绝不向 A2 传递。**

## 3. W2 — A2 分支的最小必要修复与 S0/S1 正式准入

**起点**：`work/a2-postv16-static` @ `ba73e600aa260b8f09ee9bd0d0084a98431c98d1`。先在独立 worktree 修改与测试，不改 A1 主 checkout；A1 结果冻结归档后再合并或挑选经过审计的提交。模型继续保持 LP-only。

### A2-FIX-01（**阻断级**）：检查双向扩张 Link 是否存在“反向免费建线”

源码 `workflow/byop/model/rearch_mech.py::add_line_expansion_tamu` 为每个走廊/投资年份生成 `_fwd` 和 `_rev` 两条可扩张 Link：`fwd` 正 capital_cost、`rev` 为 0。`post_v16_mainline.py::public_expansion_ledger` 将 `_rev` 在找到 `_fwd` 后直接标记为 `ENDOGENOUS_PRICED`。**这项台账分类本身不能保证两个方向共同支付成本或拥有相同建设容量。** 在已审阅的该模块中没有发现对 `AC_exp` 一般扩张对施加 `p_nom_fwd=p_nom_rev` 的相应行；需再次全仓库核查是否由其他回调添加，不能仅凭命名认定已绑定。

必须实施下列之一并证明数学上等价：

- **方案 A（推荐最小改动）**：对所有内生 `_fwd/_rev` 扩张 Link、每条走廊及批准年份加入 `p_nom_fwd == p_nom_rev`；仅一侧计价；双侧具有相同建设周期、COD、潜力上限、有效年、容量权利，年度累计新建容量不可超越已定走廊上限。
- **方案 B**：改为一个允许双向有符号流的 Link（如可审计的 `p_min_pu=-1` / `p_max_pu=1`）及单个正成本容量变量；必须验证它与原网络的潮流及耗损口径相容。

**验收**：尝试只扩建 `_rev` 而不扩建 `_fwd` 时结构约束必须拒绝；投入 ΔMW 双向容量必须发生一次、且非零的投资支出；测试既有固定双向 Link 与内生扩张不会相互抵消或重复计容。若发现此前已有共享容量约束，给出约束名、代码位置与测试证据即可，**不重复改写**。本项不通过不得授权 S0/S1。

### A2-FIX-02（阻断级）：公共扩张真实成本、建设周期与共同承诺资产的计量

1. 对新增发电、储能、输电分别核查 `approval_year/order_year → build_year → effective COD → dispatch availability`，禁止因跨年度容量复制而在实际 COD 前发电或传输；年内投运仅按已认证的可用比例参与。
2. 对 1,818 个候选的台账：不仅检查 `capital_cost>0` 或配对存在，还要检查正向计价的容量变量与实际获批新增容量一致，以及投资/年金/残值是否按模型目标正确计入。缺少明确来源的线路免费扩张不得存在。
3. 把 DWB Stage 2 与 PBRP 的**三项基础项目/六条方向 Link**建成所有 S0–S3 世界共同的外生已承诺条件。财务口径上不要把“2026/2031 尚未支付的承诺成本”等同“截至 2025 已经沉没的现金支出”：为**情景差额**可将共同承诺成本抵消，但**绝对社会成本、财政承担和资金流**须独立记账，对尚未支付的承诺支出有据可查。
4. 确认弃用 ERM-02、15% legacy ERM、shadow SOC 与 S0CAL；2025 冻结 `.nc` 不可重新生成替换；所有 S0/S1/S2/S3 的共同资产清单相同。

**验收**：`PUBLIC_EXPANSION_CAPACITY_RIGHTS_QA.csv`、`PUBLIC_EXPANSION_COST_COD_AUDIT.csv`；至少以一个 2027 订货、正工期、2029 COD 的项目为反例确认 2027/28 不可用，且 S0/S1 共用同样参数。静态测试不得调用 solver。

### A2-FIX-03：3 小时调度与 1 小时备用的物理映射及电池 SOC

保留已实现的每 3h 代表性快照 3 GW aggregate reserve、10 分钟可响应、1 小时能量支撑研究代理；不改成全国全年小时级模型。**但是必须确认储能 SOC 的时点定义**，包括在 3h 区间开始/结束 SOC 高低不同的情况下，现有 `r×1h/η≤snapshot SOC` 是否可能高估区间开始时的备用能力。若会高估，可增加基于同一实际 dispatch SOC 的**区间两端**线性约束或其他经验证的保守近似；不可创建影子储能状态。

热机 reserve 继续包括既有和公共候选，且不允许数据中心专属 BYOP 或切负荷直接提供公共备用；必须证明 `r≤online capacity−dispatch`、爬坡率/最小出力和可用状态协同成立。文档注明这是代表性 3h 规划近似，**并非所有 1h 内部转变均得到验证**。保留后续选定压力窗 1h 验证任务，不因此扩大本轮算例。

### A2-FIX-04：既有用户 no-harm、S0/S1 可比性与基准口径

首轮建议以 **S0 同一模型下的逐节点 × 逐快照 native load shed** 作为 S1 既有用户保护上限，采用一致 MW、3h 权重及很小数值容差；不直接强制 A2 每时段零切负荷，因为 S0 基准本身可能存在不可消除的短缺。S0 不得为了放宽 S1 约束而通过任意负荷切除或人为降低公共扩张获得更差参照；保留 S0 的社会真实成本最小化/服务处罚设置并做审计。

- 明确区分既有用户 shed、新增 AIDC 未交付、可协商的数据中心中断量；不能靠改称谓绕过 no-harm。
- S0、S1 完全共用天气、2025 固定网络、公共候选、建设周期、3GW 备用、TPIT/PBRP 承诺、投资价格和运行成本；差异仅是新增 AIDC 及其 POI/服务约束。
- S1 应按站点/年份的 POI 可投运条件得到实际可交付量，不能将 A1 统一固定权重结果或所有站点统一零资格硬编码到多年模型。
- S1 不得允许公共电网在未获建设许可/COD 的年份立即满足新增数据中心申请。

新增 `NATIVE_LOAD_NO_HARM_QA.csv`、`S0_S1_IDENTICAL_PUBLIC_INPUTS.json`；若 S0 本身不可行，停止求解授权流程，不准向 S1 伪造保护上限。

### A2-FIX-05：风光储 Firm 认证的范围标识，避免意外重复信用

目前 S3 的 96 个 `A2-F_cert` 已连接到服务上限，是结构进展。但主 LP 仅包含抽样的 **24 小时 B7** 压力片段，原 v2 文件的 **48/72 小时连续弱风弱光认证**尚未进入多年主模型。因此：

- **S0/S1 首轮不因这一项延迟**，因为它们不将 BYOP 风光储作为可靠供电主技术；
- **S2/S3 正式比较之前必须落实**同一物理储能状态和 48/72h 连续压力认证、边界 SOC、同资源双重预留检查，或由研究者批准一个公开限制明确的保守替代；
- GRID_FLEX 与 ISLANDED 计入的公共进口资格需分开，孤网认证不能得到免费网电；名牌风光/BESS 容量不等于独立 Firm；同一储能不能同时承诺多份互斥全额服务；
- 仅以现有单气象年做首轮，保留 `REEDS_MULTIWX_PENDING_LOCAL_H5`，不伪造多年极端气象。

### A2-FIX-06：跨平台 checkout 的 SHA 稳健性及全量回归

NEXT-01 的两个失败测试来自 CRLF/LF 换行符差异，但**目前 `202 passed / 2 failed` 不能记为全量 PASS**。A1 求解前避免触动已通过主 checkout 预检的门禁。A1 完成并冻结后再采取可移植措施：

- 对字节必须不变的原始数据继续验证**原始字节 SHA**；对 Git 可能进行换行转换的版本化文本，采用受控 `.gitattributes` 固定 EOL 并重建有版本标识的 manifest，或同时钉死原始/规范化字节哈希、校验内容严格一致。
- 禁止简化为“不比较 SHA”或捕获异常后忽略；标记原始 SHA 与正规化 SHA 各自的证据层级。
- 新 A2 分支的静态测试、完整回归与 fresh checkout 测试均必须通过；若无法修复，提交可复现的故障与受影响路径，并保持 A2 gate 锁定。

### A2-FIX-07：为 S0/S1 建立独立求解门禁（并行于 W2 静态开发，零 solver）

复用 A1 的 gate 模式，但独立命名和预算：

- `A2` config `run_authorization=NOT_APPROVED` / `approved_git_sha=null` / `approved_by=null`，独立 `A2_PRE_RUN_MANIFEST.json` 固定新分支最终代码/输入/基线 SHA；保持 `rearch_mech --post-v16` fail-closed，只有 gate 经批准通过才解除阻断，不能无条件去掉 `exit 3`；
- **预计申请** S0 一次 + S1_EARLIEST 一次，合计最多 2 次 LP、0 自动重试。当前 S0 约 2.66m 变量 / 6.53m 约束、S1 约 2.71m / 6.66m，具体大小重新静态构建记录；不得把预计求解时长当作保证；
- `STARTED` 在 solver 前原子写入，崩溃也消耗一次；S1 必须等待 S0 PASS、S0 no-harm 参考数据完整；严格处理 infeasible、unbounded、time-limit、非最优与输出损坏；
- 仅允许研究者批准 config-only commit 后启动，绝不能继承 A1 授权字段；
- 若 A1 结果 `A1_BLOCKED`，需先解释其是否妨碍构建可信 S0/S1 物理基准，由研究者再决定是否放行，不能直接忽略。

静态完成后的停点：提交 `A2_PRE_SOLVE_RESEARCHER_DECISION.md`，列出新增约束清单、强制失败测试、完整回归、正式两次 LP 命令、资源限制和剩余代理，**STOP 请求 A2 求解授权**。

## 4. W3 — S0/S1 一旦获批，正式进入论文主线仿真

**不授权即不可执行**。研究者批准 A2 后，严格顺序执行：

1. **S0（No New AIDC）**：同 2025 公共负荷和既有数据中心，2026–2031 公共发电/储能/输电内生扩张，3GW 备用，真实 COD 及所有承诺资产；按既定成本目标求解；验收 solver 最优、完整样本、公共扩张账本、既有负荷切除/备用/潮流/SOC/投资时滞及非零正成本审计。生成 S0 逐节点逐快照 native shed 参考（不能从其他旧版 S0CAL 结果抄）。
2. **S1（Grid-Only）**：在与 S0 同一公共可行域中加入分母线/年份新增 AIDC、POI 权利及合格网电交付；既有用户切负荷不得超越 S0 参考；同一 3GW 备用、无任何 BYOP 新建设备或伪造合同。报告未按期交付 IT、最早可通电年份、年度服务、公共扩张差额和系统成本变化。
3. **S1−S0**：按公共电网容量/总社会资源成本/新增数据中心实际服务/既有负荷可靠性对照；同时保留不同需求实现的服务量，不因 S1 延迟低成本而宣称其更优。

严格 STOP：S0 或 S1 求解状态非 `ok/optimal`、物理平衡残差超容差、备用违规、公共扩张存在零成本反向通道、S1 既有用户保护违规、分站 POI/COD 违规、输出缺失、账本不一致或超 solver 预算。无 Solver PASS 不得用占位符填入正式对照图表。完成两次 LP 后自动结束当前执行工作流，**不得连带启动 S2/S3**。

**首轮结果的最低指标（按 bus × year，另有全 ERCOT 汇总）**：

| 指标 | S0 | S1 | 用途 |
|---|---|---|---|
| AIDC 申请 IT、累计新增 IT、首次可投运/首次全年 Firm、实际交付 IT MW·year | 仅继承存量 | 新增及延迟 | S1−S0 的可交付性 |
| Public 新建各技术容量、各走廊 MW、COD、共用承诺与内生投资 | ✓ | ✓ | 公共扩张响应 |
| 真实资源成本（CAPEX 现值/年金、FOM、燃料/VOM、储能与线路）、公共成本与私人转移支付分账 | ✓ | ✓ | 避免成本口径混淆 |
| 既有用户 shed（MW / MWh，bus、时间）、系统 reserve 最低松弛、SOC QA | ✓ | ✓ | no-harm 和可靠性 |
| POI equipment / U upgrade / firm / conditional、各年可交付 MW | — | ✓ | 接网时间证据 |
| 未满足新增 IT MW·year、允许中断 vs 未交付 | — | ✓ | 速度基准 |

S0/S1 是**开始正式场景仿真**，不是研究主线的终点。若 S1 的公网投运并无延迟，需诚实报告并分析是否由真实 POI/资源条件造成，禁止人为扩大需求或压小现有容量来制造 BYOP 优势。

## 5. W4 — S2/S3 正式仿真前的最小衔接（仅准备，不求解）

待 S0/S1 结果可用后，下一轮只处理实现科学主线必须的接口：

1. **S2 Speed-First**：严格“优先最大化可交付、合格的数据中心服务/最早 COD，再在相同速度下最小化私人成本”，不得改成任意大权重的延期惩罚；网电报价/POI 权利不得从 S1 无约束搬运；N/R/C 电源取得路径与 Grid-Only/Grid-Flex/Islanded 供电模式分离；实际 R 候选池为空则保留为空，不虚构复用机组。
2. **S3 社会协调**：技术、工期、气源、permit、制造池、POI、已有公共资产和 no-harm 物理集合与 S2 对齐；真实社会资源成本与企业私有资金流分别入账。比较 S2−S1 和 S2−S3；如果服务量不同，必须执行 matched-service。
3. **长期路径依赖**：在正式四场景 ERCOT 小案例成立后，才扩展 2032–2035 的新增负荷及 2036–2050 零增量运行/资产利用、承诺锁定、重复扩张和低利用率；随后考虑全国。不可用当前 2026–2031 六年案例直接声称验证 2050 长期结果。
4. **环境—COD 链**：目前 16 站在 L2/L1 气源假设下许可延迟均为 0。Bexar `p650 0` 维持 L2，除非设施匹配、可靠气量与合同、侧线工期获得证据；实际排放低可能便利许可，但只有审批位于关键路径且改变实际交付服务时才产生速度收益。已登记的“臭氧非达标县 + 快速可靠气源”假设反事实仅作机制校验，不能混入基准输入。SOFC 低 NOx 不自动意味着免许可；NOx 控制设备未证实缩短时限时不能擅自赋予时限收益。
5. **Firm/Conditional Firm、RE+BESS**：实现符合合同承诺的证书、同一储能真实 SOC 与 48/72h 连续压力认证；与年度服务资格/部分年度交付逻辑相容，不能双重占用电网/BYOP 相同的可靠容量。

本轮只提交 `A3_READINESS_HANDOFF.md`，并保留 `A3=NOT_APPROVED`；未获研究者许可不得进行 S2/S3 的任何正式求解。

## 6. 人工决策登记（不得代替研究者决定）

| 决策编号 | 执行方建议（本工作包） | 何时需要研究者明确批准 | 默认未批准状态 |
|---|---|---|---|
| D1：A1 两 LP | 建议批准 `802c9d94` 所核验的主线代码；LP-R→LP-N，各 1 次，0 重试 | A1 实际 solver 前 | `NOT_APPROVED` |
| D2：Bexar `p650 0` 气源 | 继续 L2；已有现场燃气发电报道不是 firm MDQ/合同证据 | 证据足以正式改分级时 | `KEEP_L2` |
| D3：换行符 / SHA | A1 完成后修复跨 checkout 字节哈希；保留 fail-closed | 修改受控 A1/A2 gate 或 manifest 前 | 两次回归失败不可隐去 |
| D4：3h 调度 / 1h reserve | 接受研究筛查近似，先验证真实 SOC 起止端点 | A2 实际 solver 前 | 不授权 A2 |
| D5：DWB/PBRP | 作为各场景相同的**外生已承诺**基础资产；区别对待已沉没成本和未来支付成本 | A2 实际 solver 前 | 不自行改历史文件 |
| D6：native load no-harm | 推荐 S0 同节点/同时间切负荷为 S1 上限 | A2 实际 solver 前 | 静态实现可做，不能求解 |
| D7：A2 两 LP | S0 一次、S1 一次，0 重试；必须先修复 A2-FIX-01、建立独立门禁并全部静态验收 | A2 真实 solver 前（**另行**） | `NOT_APPROVED` |
| D8：A3 S2/S3 | 待 S0/S1 可信，完成 Firm 长压力窗口、企业/社会可比性及服务匹配 | A3 真实 solver 前（**另行**） | `NOT_APPROVED` |

## 7. 提交要求、验收清单与停止点

### 7.1 本工作包禁止事项

- 不改 2025 冻结基线、不恢复免费 S0CAL/ERM-02、不清空 solver ledger、不绕过哈希/授权门禁；
- 不为了出现正面的 BYOP 速度收益而改母线映射、气源等级、设备交期、线路上限、需求增长或审批时间；
- 不增加全国算例、十几组敏感性、统一环境税、未经证实的环境审批时间缩短；
- 不用旧 solver 日志冒充本轮最优结果；不将 A2 静态 `PASS_STATIC` 误写为 A2 正式 `PASS`；
- 不在 A1 主线运行期间合并 A2 的新代码；不得在一个自动脚本中串接 A1、A2、A3 的实际 solver。

### 7.2 新的必要交付物（`current_work_pckg/`，无新授权不得伪造结果）

```text
NEXT_02_EXECUTION_REPORT.md            # 最终总报告；含 git SHAs、技术判断、真实调用预算与研究者决策
A1_FINAL_APPROVAL_REQUEST.md           # 真实求解前提交给研究者；无授权不能启动
A1_EXECUTION_REPORT.md                 # LP 已获批并运行才有结果，否则继续 NOT_RUN
A1_RESULT.json / HEADROOM_SOLVE_LOG.csv # 可保留在真实 outputs 并提供精确相对路径/哈希
A2_EXPANSION_PAIR_AND_COST_AUDIT.md   # 记录 AC_exp fwd/rev 是否严格绑定，必须是 PASS
PUBLIC_EXPANSION_CAPACITY_RIGHTS_QA.csv
PUBLIC_EXPANSION_COST_COD_AUDIT.csv
A2_RESERVE_SOC_TIME_QA.md
A2_EOL_SHA_PORTABILITY_REPORT.md
A2_REGRESSION_SUMMARY.json            # 完整 pass/fail/skip；不消除失败计数
NATIVE_LOAD_NO_HARM_QA.csv
S0_S1_IDENTICAL_PUBLIC_INPUTS.json
A2_PRE_RUN_MANIFEST.json              # 仅在静态修复完成时创建
A2_GATE_VERDICT.json                  # 未获批准保持 LOCKED
A2_PRE_SOLVE_RESEARCHER_DECISION.md
S0_EXECUTION_REPORT.md / S1_EXECUTION_REPORT.md # 仅有真实授权、真实 solver 后产出
S0_S1_COMPARISON.csv                  # 仅两个均经过 PASS 后产出
A3_READINESS_HANDOFF.md               # 仅静态准备；不得宣称 S2/S3 已求解
NEXT_02_RETURN_PACKAGE.zip            # 报告、SHA256 清单、非巨型静态文件与求解证据(如获批)
```

执行方需在 `NEXT_02_EXECUTION_REPORT.md` 开头填写如下**状态块**，不能把未运行、不可行写为 0：

```text
START_MAINLINE_SHA:
START_A2_BRANCH_SHA:
FINAL_MAINLINE_SHA:
FINAL_A2_BRANCH_SHA:
V16_BASELINE_SHA256:
A1_RESEARCHER_APPROVAL: NOT_APPROVED / APPROVED (approval evidence)
A1_LP_R: NOT_RUN / PASS / FAILED / BLOCKED
A1_LP_N: NOT_RUN / PASS / FAILED / BLOCKED
A1_SOLVER_CALLS: integer 0..2
A1_RESULT: NOT_AVAILABLE / A1_PASS / A1_BLOCKED
H_RESOURCE_FACILITY_MW: NOT_AVAILABLE unless accepted LP-R
H_NETWORK_FACILITY_MW: NOT_AVAILABLE unless accepted LP-N
A2_EXPANSION_PAIR_INTEGRITY: PASS / FAIL / UNVERIFIED
A2_SOC_RESERVE_QA: PASS / FAIL / UNVERIFIED
A2_ALL_REGRESSIONS: PASSED / FAILED (full counts)
A2_STATIC_READINESS: PASS_STATIC / BLOCKED
A2_RESEARCHER_APPROVAL: NOT_APPROVED / APPROVED (separate evidence)
A2_S0: NOT_RUN / PASS / FAILED / BLOCKED
A2_S1: NOT_RUN / PASS / FAILED / BLOCKED
A2_SOLVER_CALLS: integer 0..2
A3_SOLVER_CALLS: 0
NEXT_DECISION: A1_APPROVAL / A1_BLOCKER_REVIEW / A2_APPROVAL / S0_S1_RESULTS_REVIEW
```

### 7.3 实施顺序与强制暂停

**T0 — 立即**：A1 只读预检、单独准备 A1 批准请求，同时独立分支静态检查 **A2-FIX-01 扩张双向容量/成本**。A1 运行权仍为 `NOT_APPROVED`。  
**T1 — 获 A1 书面/明确授权后**：LP-R→按通过门禁选择是否 LP-N；完成立即 STOP，回报真实 headroom 或不可行诊断。  
**T2 — A1 冻结后**：修复 A2-FIX-01～07、CRLF/LF 及全量回归；构建独立 A2 manifest/gate、申请仅 S0+S1 两次 LP。**STOP 等研究者 A2 批准。**  
**T3 — 获 A2 明确授权后**：正式运行 S0、再 S1；输出 S1−S0 第一组正式论文主线数据并 STOP。  
**T4 — 下一个研究工作包**：仅当结果显示物理与服务口径可靠，进入 S2/S3 的 Speed-to-Power—公共扩张反馈—长期路径依赖测试。

**最终强调**：结果应允许 BYOP 没有优势、许可不在关键路径、或短期 BYOP 减少公共投资；任何一种结果都不得用未授权的隐性参数调整去“纠正”。本次工作成功的标志是拿到可以审计的 **S0/S1 实际优化结果**，并建立 S2/S3 的可比实验边界，而不是通过增加更多研究代理或者算例数量来宣称完成。
