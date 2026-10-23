# BYOP ERCOT — NEXT-04 执行工作包

**主题：A1 实际求解 → A2 分支整合与重新验收 → S0/S1 正式仿真**  
**文件版本：NEXT-04 v1.0｜2026-10-22（America/New_York）**  
**适用对象：Codex / Claude / 其他执行平台；PyPSA-USA + 自定义 BYOP LP**  
**研究依据：本项目 Sources 中《论文顶层设计.md》、NEXT-03 执行报告和 GitHub 现有代码**  
**仓库：** https://github.com/simonyed/BYOP  
**重要：本文件是执行规范和审批请求依据，**不是**任何 LP/优化器调用的研究者授权。**

---

## 0. 首要指令（执行方必须先读）

**下一阶段的重点是获取真实优化结果，不再启动 NEXT-05 式的大型静态开发循环。** NEXT-03 已完成以下工作：

- A1 接入裕度 LP-R/LP-N：静态构建及 SHA 门禁通过，**尚未运行**；
- A2 S0/S1：FIX-01～09 的静态集成已完成；75/75 结构检查通过，L2 回归 245 passed/0 failed，新克隆 243 passed/0 failed/2 skipped（仅依赖 L2 本地基线）；**尚未运行**；
- FIX-08：修复代表性周/压力日之间储能 SOC 非真实连续性，仍是 LP；
- FIX-09：区分 **2 次情景级尝试**与 **3 次顶层优化器调用**，添加父/子日志、速度层级复验及严格 S0 no-harm 文件指纹；
- `A1 = NOT_APPROVED`、`A2 = NOT_APPROVED`、`A3 = NOT_APPROVED`，目前全部正式求解调用为零。

**执行次序：**

```text
P0 只读确认当前状态
  ↓
G1 研究者明确批准 A1？──否→ 停止；提交简短 A1 审批状态报告
  │是
  ↓
P1 A1 LP-R → 验收 → LP-N → 验收 → 研究者审查 A1
  ↓
G2 A1 通过，或研究者对 A1 阻断给出明确书面处置？──否→ 停止
  │是
  ↓
P2 保存 A1 版本 → 合并 A2 → 整合 main → 重建 manifest/静态回归
  ↓
G3 研究者独立批准 A2 的统一代码 SHA 和预算？──否→ 停止
  │是
  ↓
P3 S0 成本 LP → 验收 → S1 Speed-First 分层 LP + 成本 LP → 验收
  ↓
P4 S1−S0 首批论文结果、失败归因或 S2/S3 交接（仍不运行 A3）
```

不得把上一轮提出的**建议批准**视为已经批准。**没有授权时，执行方不应再持续重复只读检查、打包、等待或开启新开发轮次。** 允许做本工作包规定的一次快速预检，随后停止并请求研究者决定。

---

## 1. 冻结版本、工作目录与分支现状

截至本工作包编制时的 GitHub 状态（执行当日重新核验，不得假定仍未变化）：

| 项目 | 当前标识及含义 |
|---|---|
| 仓库默认分支 | `main`（目前落后于研究主线；后续目标是唯一长期分支） |
| A1 研究主线 | `mainline-v13-stageA`，HEAD `1e637e6d`（完整 SHA 以 Git 读回为准） |
| A1 许可核验基点 | `802c9d9414514641fd2b088b45ec7ea945be18a4` |
| A2 临时开发分支 | `work/a2-postv16-static`，HEAD `39a74ff5f96acafc356d40978e33048768fce6a7` |
| A2 现有代码基点 | `81bd57438c7b002d6cfe455ec2b3f973f33ed12c`；**仅作为合并前的审查基点** |
| v1.6 基线 `.nc` SHA-256 | `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16` |
| A1 工作目录 | L2 主检出 `.../pypsa-usa/workflow/` |
| A2 工作目录（合并前） | L2 `.worktrees/a2/workflow/` |

**隔离原则：** A1 求解完毕前，禁止把 A2 的模型、输入、配置、`.gitattributes` 等受保护文件合并进 A1 检出目录。主线上报告文件的变化只有在 A1 门禁确认未触及受保护路径时才可接受。

**长期版本控制原则：** A1 完成后收敛为 `main` 一个长期开发分支；重要可复现版本保留 commit SHA 和 Git tag，不保留不断增多的阶段性长期分支。合并过程禁止强推（force push）和强制覆盖失败日志。

---

## 2. 研究者决策表（推荐处理，不自动授予求解权）

| 决策 | 本工作包推荐口径 | 是否独立构成运行授权 |
|---|---|---|
| **G1 / A1** | 在 A1 原冻结代码 `802c9d94...` 上，严格按 LP-R→LP-N，最多 2 次顶层 LP、零重试；失败保留日志 | **否。须研究者明确批准 A1** |
| **D2：Bexar `p650 0`** | 维持天然气证据等级 L2；未证实的 MDQ/专属合同不得转成确定供气资格 | 否 |
| **D4：储能** | 接受 `stores=3 h`、起止 SOC 备用约束、FIX-08 代表时段能量中性近似；报告其限制 | 否 |
| **D5：DWB/PBRP** | 所有场景共同的外生承诺资产；绝对成本独立台账、不进入差异化投资优化目标；分别标注 2019/2024 美元与代理份额 | 否 |
| **D6：既有用户保护** | S1 每台 `load_shed`、每快照 ≤ S0 同项 + 0.001 MW，后验容差 0.002 MW；严格 SHA 对照，不静默补缺 | 否 |
| **G3 / D7 / A2** | 仅在 A1 审查及合并后，批准重新验收的**统一代码版本**：最多 2 次情景尝试、3 次顶层优化器调用，零重试 | **否。须独立、明确批准 A2** |

研究者最终可以否决任一推荐；执行方需记录原意，不得自行代填 `approved_by`、自动改成 `APPROVED`，不得默认 A1 授权自动扩展为 A2/A3。

---

## 3. P0：一次性只读核查（零求解）

在 L2 A1 检出目录，仅执行必要核查：

1. `git status`、当前 HEAD、`git merge-base --is-ancestor 802c9d94 HEAD`；确认 A1 受保护路径无代码/输入/配置变化；
2. 验证 A1 manifest、基础网络 SHA、授权文档 SHA 和当前 `run_authorization` 字段；
3. 检查 `HEADROOM_SOLVE_LOG.csv` 是否仍为空；**如已有调用记录，停止并读取既有记录，不重跑**；
4. 如上次只读结果仍有效，允许复用 `A1_FINAL_RECHECK_NEXT03.json`，不必再次创建大规模模型；
5. 检查 A2 临时分支是否仍包含 FIX-08/09、75/75 结构检验、完整回归以及未解锁的独立门禁。

**P0 停止条件：** A1 仍无批准时，更新一页以内 `NEXT_04_APPROVAL_STATUS.md`（列出缺少的三个授权字段及所请求的 SHA），然后停止。不要以“为等待批准继续做更多调研”为由修改模型和增设敏感性案例。

---

## 4. P1：A1 两次正式裕度 LP（单独授权）

### 4.1 授权文件

只允许研究者明确同意后，以一个只改变以下授权字段的配置提交来放行：

`workflow/config/config.byop_post_v16_a1.yaml`

```yaml
post_v16:
  run_authorization: APPROVED
  approved_git_sha: 802c9d9414514641fd2b088b45ec7ea945be18a4
  approved_by: <由研究者明确提供的身份标识>
```

上述代码块仅是**批准后的配置形态示例**，不得提前提交。修改时保留原 YAML 其他键值，不重写整份配置。授权文件须完整经过现有 A1 SHA 门禁。

### 4.2 运行顺序

在 A1 主检出 `workflow/` 下：

```bash
# T 按启动时 L2 实际资源及用户/管理员限制确定；不得把静态建议的 T 当成实时可用资源
THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_r

# 仅在 LP-R 终止 optimal、所有验收 PASS、日志记录为 DONE/ok/optimal/pass 后：
THREADS=<T> bash byop/run/run_post_v16.sh a1_lp_n
```

A1 两个模型分别约 373,249 变量、967,980 约束、零整数；16 个研究站点权重和为 1；432 个 1 小时压力快照；固定 2025 网络及资源；系统 3 GW 备用；既有用户硬零切负荷；目标最大化比例增长 λ。LP-R 放松线路输送限制用于资源侧上界；LP-N 保留网络限制。

**最多 2 个求解调用、0 次重试。** `STARTED` 已写入即计入预算；进程异常或数值失败不得删除台账、放松约束后重算、移用 A2 门禁或默默更换基线。

### 4.3 必须验收

- `status=ok`、`termination=optimal`、零整数变量；
- 既有负荷切除为零，备用和节点功率平衡成立（节点残差 ≤ 1e-3 MW）；
- 资源与网络裕度均有限，`0 ≤ H_network ≤ H_resource + 1e-3 MW`（对于双结果都有效的情形）；
- 保存各压力片段约束的可行性、瓶颈和支持证据；
- 最大化 λ 的对偶变量/边际价格**不自动解释为真实电价或接入报价**；
- 若 LP-R 不可行，不运行 LP-N。若 LP-N 不可行，不将 `H_network` 填成 0。

### 4.4 A1 结束后强制研究者审查

| A1 结局 | 执行方动作 |
|---|---|
| LP-R、LP-N 都 PASS | 提交 `A1_EXECUTION_REPORT.md` 及裕度表，等待研究者确认；随后才能进入 P2 |
| LP-R 不可行 | 标记 `BASELINE_PRESSURE_INFEASIBLE_RESOURCE_SIDE`，保留诊断，立即停止 |
| LP-R PASS、LP-N 不可行 | 标记 `BASELINE_PRESSURE_INFEASIBLE_NETWORK_SIDE`，保留诊断，立即停止 |
| 时间限制、异常或数值问题 | 标记实际原因、保留子日志及求解额度使用记录，不重试 |

**注意：** A1 是固定资产、压力时段、严格零切负荷下的接入裕度筛查；A2 是允许真实成本和工期下公共扩张的多年规划。二者可行域不同。A1 不可行不必然意味着 S0/S1 不可行，但**未经研究者审查并书面认可具体物理解释，不得以此直接跳过 A1 结果进入 A2 求解**。

---

## 5. P2：合并 A2 并统一至 `main`（A1 后，A2 审批前）

**目标：结束向两条研究分支同时提交的过渡机制，今后在 `main` 维护唯一长期模型。**

### 5.1 合并前保留证据

1. 记录 A1 实际求解的完整 Git SHA、manifest SHA、基线 SHA、运行脚本和日志。A1 PASS 后可建立 `a1-headroom-v1` tag；若 A1 被正式终止，仅可建立清楚标记为诊断状态的 tag，不得伪称 PASS。
2. 以 `mainline-v13-stageA` 当前最终状态为合并目标，检查 A2 分支自共同祖先 `802c9d94...` 起的具体改动。
3. 以 A2 的 `81bd5743...` 作为**合并前代码来源**，不是合并后的永久批准 SHA；保留其测试证据。

### 5.2 处理 Git 合并与文件冲突

- 合并 `work/a2-postv16-static` 中 FIX-01～09 所涉及的 `workflow/byop/{model,build,run,tests,post,inputs}`、`workflow/config/`、`.gitattributes` 等必要内容；
- `current_work_pckg` 中双方同名的 `A2_GATE_VERDICT.json`、`A2_PRE_RUN_MANIFEST.json`、`A2_REGRESSION_SUMMARY.json` **不得简单取一边覆盖**；保留研究报告的较新内容，并由合并后的代码**重新生成**新的 manifest / gate verdict；
- 对修复的 `ERCOT_OPERATIONAL_WIND_SOLAR_2023_2025.csv.gz` 在合并检出中验证 gzip CRC/完整性及字节 SHA；`.gitattributes` 必须明确把二进制 `.gz` 排除出文本自动换行转换；
- A1 既有求解日志、报告、manifest 和对照文件不删除，不修改求解完成时的归因；
- 如 Git 遇到冲突，允许合并过程中修改并复验；**不得运行带冲突标记或未经测试的模型**；
- **不得**把含 A2 代码的提交倒灌到 A1 冻结运行目录后，再声称 A1 是用原 `802c9d94` 模型求得。

### 5.3 主分支整合

建议：先合并进 `mainline-v13-stageA`，经静态验收再让默认 `main` 快进到该统一版本，之后把该版本作为唯一长期开发分支；若 `main` 已出现独立新提交，先合并审查，**禁止 `git reset --hard` 覆盖或 `push --force`**。

合并完成后，才申请删除/关闭不再需要的 `work/a2-postv16-static` 和 `mainline-v13-stageA`；确认本地/L2/GitHub HEAD 一致、所有正式产物仍可访问后再清理分支。**不要为 A3 继续创建永久工作分支。**

### 5.4 重新验收（零求解）

合并后必须重新：

1. 读取完整 Git SHA，重建 A2 manifest（包含统一后新的代码和输入指纹），核对授权文档指纹与 v1.6 baseline；
2. 运行 A2 单测、全量回归、一次结构构建，并使**所有 solver 调用被拦截或禁止**；
3. 验证之前 75 项结构检查全部仍成立；L2 回归不允许失败，不能因合并导致 FIX-08/09 退化；
4. 验证 3 h SOC / 分段边界 / 324 对双向扩张 / 1,818 个公共候选 COD/成本 / 既有用户 no-harm / 求解子调用日志；
5. 验证 A2 `run_authorization` 仍为 `NOT_APPROVED`、2 次情景尝试和 3 次顶层调用预算、不同阶段零权限继承；
6. 生成新的 `A2_MERGED_PRE_RUN_MANIFEST.json` 或按照门禁现有固定路径替换并明确登记；**实际门禁必须引用真实生成且已核查的新 manifest**。

如果为了统一路径而改动了授权源文件或配置，必须更新其 SHA 并重新申请授权，禁止把旧 SHA 当作新版本批准。新批准记录只能针对**最终合并验收后的具体代码提交**，不可沿用 `81bd5743` 作为统一主线实际运行代码的准确标识（除非门禁和受保护文件内容确实严格保持不变并被验证）。

---

## 6. G3：A2 独立求解授权门槛

研究者收到合并报告后，再单独决定是否批准 S0/S1。

授权申请必须给出：

- 统一 `main` 的完整 **approved_git_sha**、A2 manifest 文件与 SHA、冻结 `.nc` SHA；
- D2/D4/D5/D6 的最终采用口径以及代表性时段近似局限；
- 上一阶段 A1 的结果和研究者审查意见，或对阻断原因的书面豁免；
- 明确预算：`max_scenario_attempts=2`，`max_top_level_optimizer_calls=3`，`max_retries=0`；
- 清晰的三步调用计划：`S0_COST` → `S1_SPEED_HIERARCHY` → `S1_COST`；
- 实际求解入口、输出目录、日志目录和不允许的额外情景；
- 确认 `gurobipy.Model.optimize()` 采用**显式计数**，不声称通过全局 monkey-patch 拦截。

仅研究者同意后，才允许按已有 A2 gate 约定，把 `workflow/config/config.byop_post_v16_a2.yaml` 中三个授权字段填为 `APPROVED`、新的最终代码 SHA 及研究者明确身份。配置修改须独立提交、受门禁检查。

**G3 未批准 = 立刻停止，不继续靠重复报告或新建分支推进。**

---

## 7. P3：正式 S0/S1 求解（不是敏感性分析）

### 7.1 唯一首轮情景设置

| 项目 | 第一轮设置 |
|---|---|
| 空间 | ERCOT/TAMU 主干网，16 个研究数据中心母线，不扩展全国模型 |
| 时间 | **2026–2031 年**逐年投资；此轮不得将结果外推为 2050 年路径依赖结论 |
| 需求 | 已冻结的中等 AIDC 增长路径，S0 不含新增研究需求，S1 为 Grid-Only 最早合格供电 |
| 时间采样 | 每年两段采样周＋三段压力日；3 h 快照；分段 SOC 能量中性 |
| 公共规划 | 同一套既有资产、DWB/PBRP 承诺、公共候选、成本与 COD；可扩张但不允许无成本 S0CAL |
| 备用和既有用户 | 3 GW 系统级 LP 筛查备用；S1 逐项受 S0 no-harm 指标约束 |
| 模型 | 纯 LP，不能改成 MILP；执行一次 S0、一次 S1（S1 内含两步优化器调用） |

严格禁止同时加跑 `S1_ECON`、`S1_zero`、归因拆解、气源敏感性、额外价格实验、S2/S3 或全国扩展，除非后来得到明确的新研究者指令。

### 7.2 正式入口

从经 G3 授权的统一主线 `workflow/` 检出：

```bash
bash byop/run/run_post_v16_a2.sh gate
THREADS=<T> bash byop/run/run_post_v16_a2.sh s0s1
```

`THREADS` 依据启动时实际可用的 CPU、内存和管理员限制决定；此前观察约 6 核只是历史负载条件下的建议值，不是固定许可。S0 和 S1 必须串行，S1 仅在 S0 后验通过、S0 SHA-pinned no-harm 文件齐全后启动。

### 7.3 S0 验收与结果冻结

S0 必须满足：

- `ok/optimal`、零整数、节点平衡残差 ≤ 1e-3 MW；
- 3 GW 备用、热机出力/爬坡、储能起止 SOC 备用及分段 SOC 约束的数值松弛均满足容差；
- 输电正反向投资容量差 ≤ 1e-3 MW、无免费公共扩张；
- 所有公共新资产真实 COD 前不可用，公共投资成本口径正确；
- 形成完整 S0 既有用户切负荷文件，**逐母线/快照/资源完全匹配，SHA 指纹写入 S0_RESULT.json**；
- 输出 `A2_SOLVE_LOG.csv` 父行和 `A2_OPTIMIZER_CALL_LOG.csv` 子行，其中 S0 对应 `S0_COST` 一次实际顶层调用。

**储能额外数值审计（强制）：** 从求解结果按储能单元 × 年份 × 分段导出 `SOC_start_MWh`、`SOC_end_MWh`、`SOC_end_minus_start_MWh`、充/放电能量、SOC 约束残差，区分周期型和非周期型资产：

- 在 FIX-08 当前的 `end ≥ start` 设计下，**不能仅凭不等式就推断对所有设备均严格 `end = start`**；
- 对形成闭合周期链的活动资产，须检验每段净 SOC 变化确实接近 0；
- 对非循环、跨年度建设/退役资产，须独立说明其初始 SOC 和跨段状态关联，不得声称未经证明的能量中性；
- 若出现显著跨段净能量转移，记录影响资产、年份、MWh 与造成偏差的实际约束，不准事后用“平均结果合理”替代检查；
- 只要求结果审核，不提前追加新的大规模储能敏感性分析。

若 S0 失败：停止，不运行 S1，也不默许备用下降、切负荷约束松弛或临时免费输电。

### 7.4 S1 验收

S1 同时满足 S0 的公共系统基本验收和：

- S1 是**严格的**逐年 Speed-First 交付层级，再固定速度目标最小化成本；禁止用单一超大延迟罚款替换字典序；
- `S1_SPEED_HIERARCHY` Gurobi 分层阶段为 optimal；最终 `S1_COST` 的交付 IT 逐年保持预求解中冻结的速度层级（误差按固定原门禁容差）；
- S0 的 `S0_NO_HARM_REFERENCE.csv` SHA 必须与 `S0_RESULT.json` 相符；S1 不允许缺失行、缺失列、重复时间索引或自动填补；
- S1 的 D24 约束 RHS 与 S0 参考 + 0.001 MW 一致，所有既有用户增加切负荷均不超过验收容差 0.002 MW；
- `S1_SPEED_HIERARCHY` 与 `S1_COST` 两个子调用均先写 `STARTED` 后求解，结束时留下各自 `DONE/ok/optimal` 状态；
- 总计两条情景尝试父记录、三条顶层优化器子记录。额外、重复或遗漏调用均为 FAIL；Gurobi 分层内部多目标阶段单独记为元数据，不冒充额外的顶层 API 调用。

若任一阶段失败：保留全部中间结果、门禁和原始求解日志，标记实际失败类别，不自动重跑；S1 的首轮 speed/cost 结果不得以未通过验收的值代替。

---

## 8. P4：首轮成果如何与论文主线相连

本轮不以“求解器 optimal”为研究完成标志。S0/S1 都 PASS 后，必须交付最小主线结果，而不是罗列多组算例。

**必需对照：S1 − S0（新增 AIDC 对公共电网及等待的影响）。**

| 指标族 | 应交付的最小结果 |
|---|---|
| 数据中心供电时间 | 按站点和年份：请求 IT MW、已合格投运 IT MW、未及时交付 IT MW、首次合格供电年度和服务总量 |
| 公共装机 | 按年度及技术：S0/S1 新增发电与储能 MW、绝对值及差值 |
| 公共输电 | 按走廊及 COD：新扩张 MW、建设批准与投运时间、投资成本与双向配对口径 |
| 系统费用 | 同一价格年份、同一折现口径下：真实资源成本、公共扩张成本、燃料/运行成本；单独列成本转移与罚损，避免双算 |
| 可靠性 | 原有用户的年切负荷、压力时段切负荷和 no-harm 最大超额；3 GW 备用、关键瓶颈 |
| 可信度 | A1 裕度结论是否支持出现的空间瓶颈；储能分段 SOC 审计和对模型近似的明确声明 |

尤其记录**S1 是否出现非零的供电等待和公共扩张反馈**。如果所有数据中心均立即投运、所有场址均无约束，则不能仅凭 optimal 宣称已检验 Speed-to-Power 机制，应报告这种基准结果并说明后续 S2/S3 的机制识别难度；未经指令不得暗改需求、负荷、工期或容量瓶颈以制造想要的效果。

**首轮正式结果分析的三个判断：**

1. S1 相比 S0 是否改变公共投资规模、技术、地理位置或 COD？
2. S1 中哪些 POI/资源/电网瓶颈使数据中心等待？规模与空间是否物理可信？
3. 这些真实基准是否足以支持下一步 S2−S1 的 BYOP 速度/公共扩张反馈和 S2−S3 的私人—社会效率差异研究？

本轮 **不能**声称 M2/M3/M4 已被证明；完整 S0–S3 比较、matched-service、2032–2050 长期路径以及不同地区的临界机制仍属于下一阶段。

---

## 9. A3 只做交接，不自动运行 S2/S3

S0/S1 通过并经研究者审查后，为下一轮保留一份简短 `A3_READY_CHECKLIST.md`：

1. S2 是开发商**先交付速度、后私人成本**的严格字典序决策；不能仅凭社会成本最小化代替，也不混同 Grid-Only/Grid-Flexible/Islanded 与 N/R/C 资产取得方式；
2. S2 与 S3 使用同一技术集合、天然气可交付代理、许可→COD、POI、公共资产、建设周期、备用与储能物理约束；目标和账单可不同，可行域不能任意放宽；
3. 48/72 小时连续低风低光下的风光储 Firm 认证，需要真正连续的应力片段、同一 SOC 以及不重复出售的容量权利；当前 24 小时测试不能直接宣称具备 72 小时 Firm。该采样修改须研究者另行决定；
4. S2/S3 各类开发商子 LP、公共 LP 与 matched-service LP 的调用预算需独立登记，不能继承 A2 的三次顶层调用授权；
5. 2026–2031 首轮结果不得推断 2036–2050 资产搁浅。正式长期阶段按顶层设计延伸至 2035 年新增需求与 2040/45/50 节点，2036 年以后研究新增 AIDC 需求为零；
6. 所有结论允许 BYOP 更好、更差或无显著影响；**不为制造显著差异调整底层数据**。

---

## 10. 必须返回的文件与验收格式

所有阶段都要能被本项目后续对话独立复核。必要交付（无需为未授权/未执行的计算伪造结果）：

| 文件 | 内容/什么时候产生 |
|---|---|
| `NEXT_04_EXECUTION_REPORT.md` | **必交**，P0/P1/P2/P3/P4 状态、版本 SHA、授权证据、实际优化器调用、验收及停止原因 |
| `NEXT_04_RESEARCHER_DECISIONS.md` | **必交**，列出 D2/D4/D5/D6/G1/G2/G3，区分“本工作包推荐”与“研究者已明确同意” |
| `A1_EXECUTION_REPORT.md` | A1 经授权运行后，返回 LP-R、LP-N、最优/不可行及可用裕度，不能用 `0` 填 `NOT_AVAILABLE` |
| `A1_HEADROOM_SUMMARY.csv` | 仅有效裕度结果存在时产生；压力时段与定义说明齐全 |
| `A2_MERGE_AND_REVALIDATION_REPORT.md` | A1 审查之后，记录冲突解决、统一 `main` SHA、重新生成的 manifest、回归结果以及两个临时分支处理状态 |
| `A2_PRE_SOLVE_RESEARCHER_DECISION.md` | 在**统一代码验收版本**上重新请求 A2 授权，显示 2 次情景/3 次顶层调用及全部输入哈希 |
| `S0_S1_EXECUTION_REPORT.md` | 经 A2 授权后报告 S0/S1 的状态、失败归因或有效优化结论 |
| `A2_SOLVE_LOG.csv` 与 `A2_OPTIMIZER_CALL_LOG.csv` | 父/子真实调用；STARTED 及终止状态原样保留 |
| `S0_NO_HARM_REFERENCE.csv`、`S0_RESULT.json` | S0 PASS 后形成；前者 SHA 记录在后者中 |
| `A2_SOC_SEGMENT_POSTSOLVE_AUDIT.csv` | S0 和 S1 真实解的逐资产×分段 SOC 边界数值核算 |
| `S0_S1_MAINLINE_COMPARISON.csv` | **仅双方 PASS 时**，交付论文主线对比结果 |
| `A3_READY_CHECKLIST.md` | 仅交接 S2/S3 的必要前置条件，不包含任何 S2/S3 求解 |
| `NEXT_04_RETURN_PACKAGE.zip` + `FILE_LIST_SHA256.txt` | 打包相关报告、关键 CSV、manifest、静态和求解日志；大体积 `.nc` 可只提供路径和 SHA，不必复制进 ZIP |

`NEXT_04_EXECUTION_REPORT.md` 顶部必须包含一个机器可读的状态摘要，例如：

```text
WORK_PACKAGE: BYOP-POST-V16-NEXT-04
A1_APPROVAL: NOT_APPROVED | APPROVED | REVOKED
A1_LP_R: NOT_RUN | PASS | INFEASIBLE | FAILED
A1_LP_N: NOT_RUN | PASS | INFEASIBLE | FAILED
A1_OPTIMIZER_CALLS_ACTUAL: <整数，不推测>
H_RESOURCE_MW: NOT_AVAILABLE | <实测值>
H_NETWORK_MW: NOT_AVAILABLE | <实测值>
A1_RESEARCHER_REVIEW: PENDING | ACCEPTED | EXCEPTION_APPROVED | REJECTED
A2_MERGE: NOT_STARTED | MERGED | BLOCKED
UNIFIED_MAIN_SHA: NOT_AVAILABLE | <完整 Git SHA>
A2_STATIC_REVALIDATION: NOT_RUN | PASS | FAIL
A2_APPROVAL: NOT_APPROVED | APPROVED | REVOKED
A2_SCENARIO_ATTEMPTS_ACTUAL: <整数>
A2_TOP_LEVEL_OPTIMIZER_CALLS_ACTUAL: <整数>
S0: NOT_RUN | PASS | INFEASIBLE | FAILED
S1_EARLIEST: NOT_RUN | PASS | INFEASIBLE | FAILED
S0_S1_COMPARISON: NOT_AVAILABLE | DELIVERED
A3_SOLVER_CALLS_ACTUAL: 0
RESEARCHER_DECISIONS_REMAINING: <具体名称>
```

不接受模糊表述“已执行 A2”却没有明确说明零求解、一次子求解或完整验收；也不接受将结构构建次数记为优化器调用。

---

## 11. 强制停止和禁止事项（研究者控制点）

1. 未收到**明确 A1 授权**：P0 后停止；不要自行把“建议批准”写成研究者批准。
2. A1 LP-R 不通过：不得运行 LP-N；A1 失败时不得自行决定越过 G2。
3. A1 仍需要复现：不要合并受保护 A2 代码进入 A1 检出目录。
4. 合并后 A2 未经过重新验收和新 SHA 审批：不得正式求解 S0/S1。
5. S0 不通过：不得运行 S1；S1 任一子调用失败或缺少日志：不得重试。
6. 禁止免费 S0CAL、偷加电网容量、放松 3 GW 备用、降低既有用户保护、偷偷扩大算例或换用未登记输入。
7. 禁止以覆盖日志、重新生成有利数据、静默更改停机状态方式制造 PASS。
8. 禁止未授权的 S2/S3、额外敏感性分析、全国仿真及 2050 结论。
9. 禁止为本工作包创建新的长期 GitHub branch；合并后尽量只保留 `main`。
10. **没有批准就停止，而不是反复重复 static-only 工作。**

---

## 12. 本工作包“完成”的真实含义

本文件有两种合法结束状态：

**A. 未得到运行授权：** P0 通过并提交准确的审批申请与现状，`A1/A2/S0/S1 = NOT_RUN`，停止。这是合规完成，但**不等于论文案例完成**。

**B. 获得相应独立授权并通过验收：** A1 真实结果及研究者审查完成，A2 代码合并并重新验收，S0/S1 两个正式场景及父/子求解台账全部 PASS，交付 S1−S0 对比与 A3 交接，**才算本轮研究主线实质完成**。

本研究最终目标仍是 Sources《论文顶层设计.md》的四情景比较：

- **S1−S0：** 新增数据中心对公共电网扩张的影响；
- **S2−S1：** 自主 BYOP 对首次供电速度和公共扩张反馈的影响；
- **S2−S3：** 开发商私人激励与社会协调最优之间的真实资源成本、服务交付及长期路径依赖差异（必须考虑 matched-service）。

**执行方下一步要交付的是“真实、可审核的 S0/S1 对照”，不是更多准备过程的报告。**
