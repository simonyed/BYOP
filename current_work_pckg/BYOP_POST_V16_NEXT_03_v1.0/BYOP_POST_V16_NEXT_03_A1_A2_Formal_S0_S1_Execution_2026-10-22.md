# BYOP ERCOT：NEXT-03 — A1 求解放行、A2 时序与日志闭环、S0/S1 正式仿真执行工作包

> **文档用途**：供 Codex、Claude 或其他具备仓库与 L2 环境的执行方逐项执行，完成静态修复、受控求解与结果返回。**本文不是研究者的求解授权**，不允许执行方以本文为依据自行填写 `approved_by`、修改 `run_authorization`、清除预算日志或发起 LP。
>
> **版本**：NEXT-03 v1.0，2026-10-22；**研究对象**：PyPSA-USA/ERCOT，2026–2031 年、16 个研究母线、mid 需求、LP-only；**论文主线**：《论文顶层设计.md》的 S0–S3 反事实，先取得 S0/S1，再研究 S2/S3 的 Speed-to-Power、私人—公共投资反馈和长期路径依赖。

## 0. 执行状态、代码基点与目标

**仓库**：`https://github.com/simonyed/BYOP`。

| 项目 | 2026-10-22 已核对状态 | 用途 |
|---|---|---|
| A1 主线 | `mainline-v13-stageA` @ `303eb35b`（执行时取完整 SHA） | 冻结后仅运行 A1；不可混入 A2 源码修改 |
| A1 可批准代码基点 | `802c9d9414514641fd2b088b45ec7ea945be18a4` | 审批配置的候选 `approved_git_sha`；是否仍满足祖先与受控路径 SHA，由现场 gate 重新验证 |
| A2 静态分支 | `work/a2-postv16-static` @ `fa93d257`（执行时取完整 SHA） | A2 最小修复、测试、申请 S0/S1；本轮不再新建一个阶段性远程 branch |
| 冻结 2025 基线 | `workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`，L2 本地 | SHA-256：`a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16` |
| 授权状态 | A1/A2/A3 均为 `NOT_APPROVED`；A1/A2 各零次正式求解 | **不因本文改变** |

以上为工作包起点，执行前必须重新核查 Git HEAD、clean worktree、受控文件 SHA、manifest、授权字段和两个求解账本，**禁止直接把文内 SHA 当作最新状态**。

**主要输入与审计证据**：
- `current_work_pckg/NEXT_02_EXECUTION_REPORT.md`
- `current_work_pckg/A1_FINAL_APPROVAL_REQUEST.md`、`A1_FINAL_RECHECK.json`
- `current_work_pckg/A2_PRE_SOLVE_RESEARCHER_DECISION.md`、`A2_GATE_VERDICT.json`、`A2_PRE_RUN_MANIFEST.json`
- `current_work_pckg/A2_RESERVE_SOC_TIME_QA.md`、`A2_EXPANSION_PAIR_AND_COST_AUDIT.md`
- `current_work_pckg/A2_EOL_SHA_PORTABILITY_REPORT.md`、`A3_READINESS_HANDOFF.md`
- 《论文顶层设计.md》；此前 NEXT-02 执行工作包。

### 0.1 本轮只做三件事

1. **A1**：准备最后一次只读审批检查；研究者明确批准后，依序运行 LP-R、LP-N，得到 `H_resource`/`H_network` 或可追溯的阻断原因。
2. **A2**：在现有 A2 分支完成两个**最后必要缺口**——不连续抽样时段的 SOC 边界审计/必要修复，以及 S1 分层求解实际调用日志和计数口径；保留已通过的 FIX-01～FIX-07。完成后按独立门禁申请 S0/S1 授权。
3. **S0/S1**：仅在研究者另行明确批准、A1 结论不妨碍物理解释且 A2 静态验收通过后，运行 S0 → S1_EARLIEST，并返回第一份正式主场景比较。

**不做**：全国范围、2026–2050 完整求解、新参数大规模搜集、Low/High 全景扫描、S2/S3 正式求解、环境排放价格或税的臆造、全面模型重写。报告不得把 2026–2031 的首轮结果外推为 2050 路径依赖结论。

### 0.2 强制停止/汇报点

- **H1**：A1 需要研究者的单独求解批准；无批准则只交付 A1 只读申请，不运行 LP。
- **H2**：A1 被阻断或失败后必须停止并上报，不擅自把不可行解释为零 headroom，也不自动授权 A2。
- **H3**：A2 必要时序与日志修复的静态测试完成，提交 A2 独立审批请求；**A1 的批准不能继承**。
- **H4**：S0 成功才能运行 S1；S1 完成后停止，未经额外授权不转入 A3。

## 1. 已验收事项：禁止重复造轮子

| 内容 | 最新证据 | 处理原则 |
|---|---|---|
| A1 模型 | LP-R 与 LP-N 各 373,249 variables、967,980 constraints、0 integer；432 个 1h snapshots；最大化 λ、既有负荷 hard-zero shed、3 GW 系统备用 | 不改物理输入、不重建基线；只读复核后申请批准 |
| A2 结构 | S0/S1/S3 的 66/66 项结构检查通过；L2 230/230 项回归通过；新克隆 228 pass、2 skip（本地基线不可得） | 作为静态通过，不等于已优化求解 |
| 输电正反向容量 | 324 个 AC_exp fwd/rev 对由既有 `M2-line_sym` / `M2-line_cap` 及 PyPSA 相关约束绑定，正向计价一次 | 保留 `expansion_pair_audit`，**不得重复设计第二套输电技术** |
| 1,818 个公共扩张候选 | 已检查计价、投运前不可用和 2027 下单/2029 COD 反例 | 保留审计，首次正式求解后复验实际扩张量、COD 和成本 |
| 共同已承诺输电 | DWB Stage 2 与 PBRP 两条路径（模型中 6 条方向 Link），所有情景共同外生、成本单独记账 | 不恢复免费 S0CAL，不把共同承诺成本直接归因于新增 AIDC |
| D24 no-harm | S1 约束覆盖 68 个既有用户/继承负荷切除设备，不含新增研究 AIDC 的未交付负荷 | 采用 S0 同设备、同 snapshot 作为基准（详见 D6） |
| v2 BYOP 技术 | 六技术、许可→COD、供货池、S2/S3 同物理候选 | 不重新校准；A3 再补连续 48/72h wind/PV/BESS Firm 认证 |
| 数据可移植性 | A2 分支已修复 LF/CRLF 验证；原 `.csv.gz` 在 GitHub 曾被 `.gitattributes` 当文本破坏，在 A2 分支修复 | A1 不读此文件；在 A1 冻结后同步正确二进制文件，保留 raw SHA 核验 |

## 2. W1 — A1 最后预检与有条件求解

**执行位置**：A1 冻结 L2 主 checkout；不得从 A2 worktree 直接执行 A1。

### W1.1 零求解预检

1. 运行 `git rev-parse HEAD`、`git status --porcelain`；确认受 A1 gate 管控的代码、配置、输入文件及 SHA 与 `POST_V16_A1_PRE_RUN_MANIFEST.json` 完全一致。报告类提交若在基点之后存在，按 gate 的祖先条件判断，不能自动改批准 SHA。
2. 验证基线 `.nc` 原始 SHA 为 `a623fb6d...747d16`，并核实授权来源文件、配置 normalized SHA。
3. 确认 `workflow/results/BYOP/POST_V16_A1_HEADROOM/HEADROOM_SOLVE_LOG.csv` 无历史调用；**任何 STARTED、错误或中断记录均计入预算，不得删除或改写**。
4. 检查 LP-R/LP-N 的：λ 目标无额外成本项、B0/BL 既有负荷零切除、16 母线权重和为 1、固定压力窗口、3GW 备用、线路放宽/冻结的唯一差异。
5. 执行无求解检查（从 L2 `workflow/` 目录）：

```bash
bash byop/run/run_post_v16.sh a1_dry
bash byop/run/run_post_v16.sh a1_gate
```

**预检不通过则 STOP**：仅返回失配文件和 SHA，不在这个阶段修改 A1 受控路径以强迫通过。

### W1.2 研究者单独批准（H1）

执行方填写并提交 `A1_FINAL_APPROVAL_REQUEST.md` 或其更新版，列出仓库完整 HEAD、基点、基线、manifest、账本、可用线程和两条求解命令。研究者**明确同意后**才允许对 `workflow/config/config.byop_post_v16_a1.yaml` 作 config-only 批准提交：

```yaml
post_v16:
  run_authorization: APPROVED
  approved_git_sha: 802c9d9414514641fd2b088b45ec7ea945be18a4
  approved_by: <研究者亲自明确提供的标识>
```

**以上只是批准后目标配置示例，并非本文件给出的批准。** 执行方不得推定或代填批准人。提交批准配置后再次检查门禁是否通过。

### W1.3 获批后执行（最多两次实际 solver 调用，零重试）

```bash
# 在 A1 冻结 L2 checkout 的 workflow/ 中；THREADS 由执行当时资源评估确定
THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_r
# LP_R_H_RESOURCE_RESULT.json acceptance PASS 且日志 DONE/ok/optimal/pass 后才可执行
THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_n
```

- LP-R 未 PASS：不运行 LP-N。
- B0 基线不可行：标记 `BASELINE_PRESSURE_INFEASIBLE_RESOURCE_SIDE` 或 `...NETWORK_SIDE`，不报告 headroom=0；不擅自放松零切负荷、3 GW 备用或免费增线。
- LP-N 非最优或验收未通过：标记 `A1_BLOCKED`，保留 LP-R 已通过的结果与完整失败诊断。
- 联合通过需 `0 ≤ H_network ≤ H_resource + 1e-3 MW`；节点平衡残差 ≤1e-3 MW、既有负荷切除为零、备用满足、λ 小于人为上限；每项缺失或非数值一律 FAIL。

**输出**：`A1_EXECUTION_REPORT.md`、两个阶段的 `*_RESULT.json`、`A1_RESULT.json`、`JOINT_HEADROOM_RESOURCE_NETWORK.csv`、带时间戳的 `HEADROOM_SOLVE_LOG.csv`、solver 原生日志、SHA/approval 清单及阻断原因。不得把资源/网络联合 headroom 称为 ERCOT 正式 POI 接入许可额度。

## 3. W2 — A2 仅修复真正阻挡 S0/S1 的两处缺口

**位置**：`work/a2-postv16-static` 现有 worktree，不另建长期分支；保留 A1 冻结 L2 checkout。起点 `fa93d257` 及其后新提交均须现场完整 SHA 审计。

### W2.1 重点 A：代表时段不连续引起的 SOC 跨段串联风险（新增 A2-FIX-08）

**已核实的旧问题**：`ml_base_build()` 将年度抽样的样本权重（约 77h）错误施加于 PyPSA `snapshot_weightings.stores`，现在仅在 post-v1.6 模式将 `stores=3h`，而 `generators/objective` 保留年度放大权重。**同意修正方向，禁止退回约 77h 作为实际 SOC 时间步长。**

**尚须静态核实的风险**：`sample_weeks:26` 并不生成完整连续年，而是抽取相距较远的代表周并额外并入 B7 压力日。将所有保留 snapshots 顺序连接、统一按 3h 更新 SOC，可能使不相邻的自然时间段之间隐式传输储能电量。这是需验证的**潜在风险**，不是当前已通过优化证实的错误。

执行方必须：

1. 在 `workflow/byop/model/rearch_mech.py::ml_base_build()` 及其随后 `to_multiperiod`、PyPSA StorageUnit 平衡约束中，输出每个投资年度的保留快照时间戳、相邻时间差、分段编号、年度权重与 `stores` 权重；确认抽样段（代表周和额外压力日）是否被视作连续 SOC 状态链。
2. 对普通电池/储能和可能具有季节特征的水电储能分别审计，不能用“把全部储能每日 SOC 清零”掩盖问题。
3. 若存在跨真实时间空隙的 SOC 继承，实施**最小 LP 线性修复**：在每个独立连续片段使用明确且有限的 SOC 起点/终点条件（如按片段设可审计的初始 SOC 上界、结束 SOC 不低于起点，或等价的既有 PyPSA 支持方式），阻止未认证的跨段净能量转移；保留片段内部的真实连续 3h 状态演化。对同一 B7 连续压力事件不允许每个 3h 快照单独重置 SOC。
4. 保留年能量/成本代表性权重，但在文档中明确：抽样加权后的储能调度是代表性近似，不能将片段内 SOC 直接解释为全年逐小时储能轨迹；检验分段边界不会意外跨年度重复初始化或相互影响。
5. 单元/结构测试至少覆盖：**连续 3h**、**相隔若干周的独立代表段**、**插入压力日**、**跨投资年度**，以及“4h 电池无法在连续多个低资源快照中凭空提供持续 Firm 能量”的反例。所有测试不得调用求解器。

若现有模型已经正确隔离分段：给出相应 PyPSA/linopy 状态方程和静态反例证明即可，**不要重复修改**。若静态难以证明或修复会改变 S0/S1 物理解释，停止并上报研究者，不要带风险直接正式求解。

**建议产物**：`A2_REPRESENTATIVE_PERIOD_SOC_BOUNDARY_AUDIT.md`、`A2_SOC_SEGMENT_MAP.csv`、`A2_SOC_BOUNDARY_TESTS.json`。

### W2.2 重点 B：S1 Speed-First 分层求解的真实调用和预算（新增 A2-FIX-09）

**已核对的调用链**：`rearch_mech.py::go()` → **A2 包装器** `post_v16_solve_wrapper`（先写父尝试 STARTED）→ PyPSA `w2.solve()` 建模 → `extra_rearch()` → `lex_presolve()` 中 `gurobipy.Model.optimize()` → PyPSA 成本阶段 `linopy.Model.solve()`。因此，不能声称 `lex_presolve()` 完全绕开 A2 父层门禁；**它处于已经记录 STARTED 的 S1 尝试之内**。

但当前“max_lp_calls=2”的含义不精确：

- 情景级尝试：S0 1 次，S1 1 次（各有父层 STARTED、独立验收）；
- 顶层优化器调用：预期至少 **3 次**——S0 成本 LP、S1 分层多目标 `gm.optimize()`、S1 最终成本 LP；
- Gurobi 分层多目标可能内部执行多轮目标优化；需记录目标层数及求解状态，不能声称恰好只有 3 次底层求解 pass。

实施要求：

1. 把配置和审批报告中的额度**明确分开**：`max_scenario_attempts=2`；`max_top_level_optimizer_calls=3`（仅在确认真实调用链与现有配置兼容后采用）；Gurobi 层级内部 passes 为**审计元数据**，不是额外可授权新情景。原 `max_lp_calls=2` 不得继续对用户呈现为“两次物理优化器调用”。
2. `A2_SOLVE_LOG.csv` 保留**父层** S0/S1 的不可覆盖、可恢复账本；新增 `A2_OPTIMIZER_CALL_LOG.csv` 或同等级的子调用记录，覆盖 `S0_COST`、`S1_SPEED_HIERARCHY`、`S1_COST`，含 `parent_attempt_id`、调用前持久化 `STARTED`、阶段返回码、优化状态、模型大小、目标层数和耗时。父层仍必须先于所有子调用记录。
3. 子求解异常、中断或非最优时父层应 FAIL/ERROR 并停止；任何已 STARTED 的父/子记录均不得删除，不自动重试；不得通过命令绕开父层/子层门禁。
4. 在当前 PyPSA/Gurobi 实际接口中，检查能否截获所有顶层 `.optimize()` 和 `.solve()`，尤其不得因 `gurobipy.Model` 扩展类型不能 monkey-patch，就误称已经有完整跨库拦截。使用**显式受控入口的代码打点**，不依赖易失败的全局 monkey patch 完成真实性审计。
5. 对 `S1_EARLIEST` 保持“逐年 Speed-First/公平比例 → 达到该速度水平后再最小化真实社会成本”的既定词典序；不换成一个随意设定的大权重惩罚目标。逐年速度层级若 Gurobi 返回最优，仍须检查最终阶段服务量是否满足锁定的速度目标（含已规定容差）。
6. 增加**强制失败注入**：分层预求解失败、分层成功但成本失败、父层 STARTED 后崩溃、第二次执行命令、账本数据损坏、跳过 S0 请求 S1；上述情况一律拒绝继续且保留日志。静态测试不调用真实 solver。

**建议产物**：`A2_SOLVER_ACCOUNTING_AUDIT.md`、`A2_OPTIMIZER_CALL_PLAN.json`、`A2_GATE_FAILURE_INJECTION_QA.json`。历史所有已发生 0 次正式调用，静态测试不应写入正式额度账本。

### W2.3 保留并复验的模型约束（不新增敏感性）

1. **系统备用**：3,000 MW、10 分钟响应、1h 储能备用支撑；同一调度 SOC 的**快照开始和结束**均受能量下界；既有热机与有工期公共候选按在线容量/出力余量计入；禁止 DC 自备资源或负荷切除重复提供系统备用；明示 3h 时段是 aggregate reserve screening proxy，非逐小时 N-1。
2. **输电正反向**：对全部 `AC_exp` `M2-line_sym`/`M2-line_cap`/实际成本变量进行原有 324 对台账复验，确认仅正向计费一次且没有免费反向容量；不要重写已经通过的约束。
3. **公共资产**：1,818 个候选计价并遵守 approval→COD；DWB Stage 2 与 PBRP 项目为共同已承诺外生资产。已收集的 DWB `371 M$`（2019 USD 口径）及 PBRP `3,020 M$/path`（由 2024 年总额分摊的研究代理）保留在**独立账簿**，必须附币值年份和来源，不得混称统一 2025 USD；尚未支付部分比例仅标为假设，不得当作已验证沉没成本。首次 S0/S1 的差额分析可以净去共同承诺成本，绝对社会成本报告须注明未完整核算的界限。
4. **既有用户保护**：采用 S0 **相同 `load_shed` 单元 × 相同 snapshot** 作为 S1 不可损害基准，允许求解数值容差 `+0.001 MW`（验收容差最高 `0.002 MW`）；不把新增研究 AIDC 的延迟/未交付误归类为既有用户切负荷。若 S0 结果与索引不匹配、存在重复/缺失列、冻结引用文件 SHA 不符，必须 FAIL，不能静默 `.fillna(0)` 后假装可比。
5. **S0/S1 相同世界**：公共候选、公共固定资产、年内 COD、气象/燃料成本、备用及价格规则一致，区别只在新增研究 AIDC 及相应供电服务；维持县气源等级 `p650 0=L2`，不根据邻近项目推断 firm MDQ。
6. **气象和风光储 Firm**：S0/S1 不使用专属 BYOP RE+BESS 证书，无需提前做 A3 的 48/72h 完整认证；不要把 S2/S3 尚缺的可靠性证书当作 S0/S1 阻断事项。

### W2.4 零求解综合验收

在 A2 worktree 执行原有 `tests`、`structural`、`manifest`、`gate` 入口与新增 FIX-08/FIX-09 测试；任何测试或脚本通过创建模型调用求解器均应 fail。现场复核 A2 原技术参数四源文件的 SHA、`.csv.gz` 二进制 gzip 完整性、A2 manifest 及基线 SHA。

**验收条件**：
- 66 项原有结构检查及原回归项目全部通过，新增 SOC 分段与求解计数失败注入项目全部通过；不得将新的失败以“环境不同”任意跳过。仅无 L2 原始基线的 fresh clone 可保留具原因的 skip。
- A2 实际授权字段仍 `NOT_APPROVED`；正式 A2 父子调用账本不存在或确认为零调用；所有受控源码、输入和 manifest SHA 一致。
- `rearch_mech --post-v16` 在未批准时仍 fail-closed，不能因为完成静态修复而自动解锁。
- S0/S1 真实规划模型**均为 LP，无整数变量**；不得因分段 SOC 引入二进制、循环无因果或无上界免费资源。

若不通过，只返回缺口报告，不请求用户批准有缺陷的模型。

## 4. 研究者决策表（申请，不是授权）

| 决策 | 推荐选择 | 在本轮工作中的含义 |
|---|---|---|
| **A1-APPROVAL** | 建议批准两次 LP-R / LP-N，仍需研究者明确说同意 | 使用冻结的 `802c9d94` 作为经现场验证的审批基点；两次物理调用，0 重试 |
| **D2：Bexar p650 0** | 继续 **L2** | 现有 Vantage/VoltaGrid 证据不等于研究场址 firm MDQ；保留证据等级与许可争议标签 |
| **D4：3h/1h 与 SOC** | 接受 `stores=3h` + 1h reserve 始/末端 SOC，且**先修复/证明不连续样本边界** | 不回退错误 77h SOC；不得把代表时段等同连续全年时序 |
| **D5：DWB / PBRP** | 各情景共同外生承诺资产；不同币值年份及未付比例独立披露 | 首轮主线看差额；绝对生命周期成本之后核对币值与付款分期 |
| **D6：no-harm** | 接受 S0 逐单元、逐 snapshot 上限 +0.001MW | S1 不能比 S0 更多损害既有客户（允验收公差） |
| **D7：A2 授权** | **原则支持，需 W2 全 PASS 且研究者再次明确批准** | S0/S1 两个情景尝试，预计三次顶层优化器调用，内部多目标 passes 留痕 |

研究者对某项不同意时，执行方根据否决原因出具**一个具体替代方案**及其与物理可行集合的差异，不自行发散为大量敏感性情景。

## 5. W3 — S0/S1 首次正式运行（仅单独获批后）

### W3.1 前置条件与审批

1. **A1 结论已提交研究者审阅**。若 A1_PASS，S0/S1 以同一冻结基础继续；若 A1_BLOCKED，先报告是否为固定 2025 基线/3GW 备用/压力窗口造成的不可行。**不能默认为 A1 失败也允许 A2**，需要研究者对可解释性作出明确裁定。
2. W2 所有零求解测试及实测 SHA 门禁通过，静态模型不再存在 SOC 跨段凭空能量或缺失子求解日志的阻断缺陷。
3. 执行方提交更新后的 `A2_PRE_SOLVE_RESEARCHER_DECISION.md`，列明：A2 **完整代码 commit SHA**、冻结 manifest、最小执行入口、`max_scenario_attempts=2`、`max_top_level_optimizer_calls=3`、多目标 passes 计数办法、上次测试结果、即将执行的 `THREADS` 和停止规则。
4. **研究者明确批准 A2 后**才允许 config-only 修改 `workflow/config/config.byop_post_v16_a2.yaml` 的 `run_authorization/approved_git_sha/approved_by`，并重新检查 A2 gate；不允许继承 A1 授权，不能由执行方代填批准者。要保留历史授权来源文件，不随意移动到 `_completed/` 导致 SHA 失配。

### W3.2 运行顺序与结果保存

在 A2 L2 worktree 的 `workflow/` 工作目录，根据已批准的 SHA 执行：

```bash
bash byop/run/run_post_v16_a2.sh gate
# 确认 S0 gate 通过后，使用批准的 THREADS 运行：
THREADS=<T> bash byop/run/run_post_v16_a2.sh s0s1
```

脚本允许**按序执行 S0 与 S1_EARLIEST**。但必须通过两层 STOP：

- **S0_PASS**：父尝试已落盘、最优、完整接受；现有用户 shed 与 S0 冻结参照文件的 snapshot/列/SHA 完整；备用始/末 SOC、公共投资、输电对称和节点平衡验收通过。否则**不运行 S1**。
- **S1_PASS**：S1 的分层预求解最优、年度速度目标在成本阶段仍满足；S1 相对冻结 S0 的 D24 no-harm 不越界；新 AIDC 供电服务和公共扩张可解释；无超预算优化器调用。否则 FAIL 并停止。

**严禁**：自动重试、清空任一父/子账本、换 solver 参数再次求解、恢复 ERM/S0CAL、修改 S0 以制造可行、在 S0/S1 未验收前运行 S2/S3。

### W3.3 论文主线最小结果集

结果至少可回答 **S1−S0**：“新 AIDC 需求在既定 POI 与公共建设时滞下，使电网何处何时新增哪些资产、哪些数据中心延期供电？”

| 产物 | 内容/口径 |
|---|---|
| `A2_SOLVE_LOG.csv` + `A2_OPTIMIZER_CALL_LOG.csv` | 2 个情景父尝试与实际顶层优化器子调用、真实状态/失败原因/时间；不得以无日志求解替代 |
| `S0_RESULT.json` / `S1_EARLIEST_RESULT.json` | Gate、最优性、残差、备用、SOC、扩张对称、no-harm、词典序速度目标验收 |
| `S0_S1_SCENARIO_SUMMARY.csv` | 固定资产、运营成本、公共扩张投资、储能/风光新增、S0/S1 已供电容量及年度主要输出 |
| `S0_S1_PUBLIC_EXPANSION_DIFF.csv` | 电源/储能/线路分投资年份、COD 年份和区域的新增容量、实际运行、成本差额；共同承诺外生资产单列 |
| `S0_S1_SERVICE_TIMELINE.csv` | 16 母线逐年需求、实际获供 IT 服务、首次可送电年、供电等待、未交付服务 IT-MW-year 与有权/无权部分 |
| `S0_S1_NATIVE_LOAD_NO_HARM.csv` | 每个既有 `load_shed` 单元/快照的 S0 基准、S1 实际、超限检查（按年汇总） |
| `S0_S1_RESERVE_SOC_QA.csv` | 3GW 总量、热机在线/响应代理、储能始末端 SOC 余量、代表时段边界检查 |
| `S0_S1_COST_RECONCILIATION.md` | 情景目标成本、外生承诺成本、币值年份和社会真实资源成本口径；禁止把未交付服务造成的低成本直接解释为效率增益 |
| `S0_S1_FIRST_RESULT_INTERPRETATION.md` | 实际结果和初步机制，注明 ERCOT 合成网络、气源/POI 代理、单天气年与抽样时序局限；对无法证明的结果明确写“不确定” |

不要求这次就得到 M2/M3/M4 全部科学结论：它们仍需要 S2/S3 与 2036–2050 路径分析。

## 6. W4 — A3 只做交接，不授权 S2/S3

交付 `A3_NEXT_GATE_HANDOFF.md`，只确认以下事项和下一份申请的最小清单：

1. S2 企业决策保留**严格 Speed-First → 私人成本第二层**；区分供电模式 GRID_ONLY/GRID_FLEX/ISLANDED 与 N/R/C 电源取得权利；复用 R 候选池为空时不可编造资产。
2. S3 与 S2 具有同一物理可行域、同一设施/天然气/许可/COD/制造池/POI/公共资产/SOC/备用约束；目标函数区分私人现金流与社会资源成本。
3. 48/72h 低风低光连续压力时段的 RE+BESS Firm 认证及独立资源不可重复容量预留（当前主 LP 仅 24h）必须在 A3 前核验；未经认证的专属再生能源/BESS 不得获得全年 firm 信用。
4. 环境链条为“NOx/污染控制与许可资格 → 许可关键路径 → 真实 COD → 已交付服务”，不单独虚构统一排放税。16 母线许可不引起延迟是当前 L2 气源代理下的结论，单独的快速气源反事实只用于机制测试。
5. S2−S1、S2−S3 必须报告**matched-service comparison**；2032–2035 继续新增 AIDC，2036–2050 无新增研究需求，长期资产锁定/复用/利用率在 ERCOT 四情景闭环后再扩展，禁止提前声称 2050 结果。

**不得自动申请或运行 A3**。若 S0/S1 失败，只做失败归因和基线恢复策略提案，不进入 A3。

## 7. 分支管理与复现约定（简化）

- **本轮不再为 A1/A2 的每个小修复创建远程阶段分支**：只保留已有 A1 冻结主线与 A2 临时开发分支，利用独立工作树隔离正在审批的代码。
- A1 完成并冻结求解结果以后，保留不可变 Git tag（例如 `ercot-a1-validated-20261022`，实际仅在 PASS 后创建），然后复核 A2 的变更再整合主干 `main`。没有经过审计的改动不能批量合并；尤其必须验证 `.gitattributes` 与 `.csv.gz` 的真实 raw SHA。
- S0/S1 首轮完成且经研究者审阅后，同样用 commit SHA、input manifest、solver ledger 和 Git tag 记录，而不长期保留大量 branch。
- `git status`、`git diff`、提交、推送应按执行环境和权限执行；避免在 L2 主 checkout 工作尚在求解时改变受控路径。不得 force push、擅自删历史分支或移动被授权 manifest 引用的文件。

## 8. 执行方最终交付规范

全部放在 `current_work_pckg/` 或约定的 `results/BYOP/`；非 Git 追踪的大文件保留在 L2，返回可下载的轻量结果/日志和校验清单。

**必须返回**：

1. `NEXT_03_EXECUTION_REPORT.md`：阶段结论、研究者已明确决定的事项、完整提交 SHA、L2 与 GitHub 同步情况、测试数、所有 LP 调用真实数量及失败/成功。
2. `A1_EXECUTION_REPORT.md`（如获授权并执行，否则保持 `NOT_RUN`）；A1 Gate/Result/日志。
3. `A2_REPRESENTATIVE_PERIOD_SOC_BOUNDARY_AUDIT.md`、`A2_SOLVER_ACCOUNTING_AUDIT.md`、新增单测与结构复验记录。
4. `A2_PRE_SOLVE_RESEARCHER_DECISION.md` 更新版、`A2_GATE_VERDICT.json` 更新版、A2 manifest/SHA 明细。
5. `S0_S1_EXECUTION_REPORT.md`（如获单独授权并执行，否则写 `NOT_RUN`）及第 5.3 节全部可获取的实际数据；若失败，保留拒绝/异常和部分完整结果。
6. `A3_NEXT_GATE_HANDOFF.md`（只交接，非授权）。
7. `NEXT_03_RETURN_PACKAGE.zip`：上述轻量文档/结果、`FILE_LIST_SHA256.txt`、相关 git diff/commit IDs、显式说明缺失的 L2-only 文件及原因。打包后执行完整性自检。

### 8.1 固定机器可读返回块（写入 `NEXT_03_EXECUTION_REPORT.md` 末尾）

```text
WORK_PACKAGE: BYOP-POST-V16-NEXT-03
A1_MAINLINE_START_SHA: <full-sha>
A1_MAINLINE_FINAL_SHA: <full-sha>
A2_BRANCH_START_SHA: <full-sha>
A2_BRANCH_FINAL_SHA: <full-sha>
BASELINE_SHA256: a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16
A1_RESEARCHER_APPROVAL: NOT_APPROVED | APPROVED
A1_GATE_STATUS: ...
A1_SOLVER_CALLS_ACTUAL: 0 | 1 | 2
A1_LP_R_STATUS: NOT_RUN | PASS | FAIL
A1_LP_N_STATUS: NOT_RUN | PASS | FAIL
H_RESOURCE_FACILITY_MW: NOT_AVAILABLE | <number>
H_NETWORK_FACILITY_MW: NOT_AVAILABLE | <number>
A2_SOC_SEGMENT_QA: PASS | FAIL | NOT_TESTED
A2_SUBCALL_ACCOUNTING_QA: PASS | FAIL | NOT_TESTED
A2_REGRESSION_PASS_FAIL_SKIP: ...
A2_STRUCTURAL_PASS_FAIL: ...
A2_RESEARCHER_APPROVAL: NOT_APPROVED | APPROVED
A2_SCENARIO_ATTEMPTS: 0 | 1 | 2
A2_TOP_LEVEL_OPTIMIZER_CALLS_ACTUAL: 0 | 1 | 2 | 3
A2_GUROBI_HIERARCHY_OBJECTIVE_COUNT: NOT_RUN | <number>
A2_S0_STATUS: NOT_RUN | PASS | FAIL
A2_S1_EARLIEST_STATUS: NOT_RUN | PASS | FAIL
A3_SOLVER_CALLS: 0
S0_S1_COMPARISON_STATUS: NOT_RUN | COMPLETE | BLOCKED
PROXY_LIMITS: single weather year; gas L2 3y; 8 sites UNKNOWN_CONSERVATIVE; sampled 3h; reserve aggregate LP proxy
OPEN_RESEARCHER_DECISIONS: ...
DELIVERABLES_AND_SHA256: ...
```

若实际状态不符合枚举，应保留真实状态及解释，不应强制改写为 PASS。所有已发生 solver 调用必须如实记录，不以“情景次数”替代优化器调用次数。

## 9. 执行方第一条指令

请先阅读本文件与 `current_work_pckg/NEXT_02_EXECUTION_REPORT.md`、`A1_FINAL_APPROVAL_REQUEST.md`、`A2_PRE_SOLVE_RESEARCHER_DECISION.md`、`A2_RESERVE_SOC_TIME_QA.md`，对本轮已完成项保持复用。**立即从 W1.1 只读复核和 W2.1/W2.2 零求解静态修复并行开始**：A1 checkout 不变，A2 只在现有工作树修改；先完成所需的静态 QA、报告与授权申请，所有未获研究者明确批准的 LP 必须保持 `NOT_RUN`。当需要研究者授权或作新事实判断时，交付完整申请并停止。后续在已授权的每个独立阶段完成当下允许的工作，绝不能因授权不足而谎报求解成功，也不要增加无关的敏感性案例。
