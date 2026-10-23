# BYOP ERCOT — NEXT-05 v2.0 无人值守连续执行工作包

**用途：** 接手 NEXT-04 的 A1 补救求解，从已验收的修复代码继续执行，随后自动推进 A2 合并、S0/S1 正式计算，以及条件满足时的 S2/S3 机制试算。  
**适用平台：** Codex、Claude 或获得该仓库、L2 和 PyPSA-USA/Gurobi 使用权限的执行代理。  
**仓库：** https://github.com/simonyed/BYOP  
**科学依据：** `论文顶层设计.md`；四个主情景 S0/S1/S2/S3；首轮仅 ERCOT 16 研究站点、2026–2031、中等增长。  
**版本日期：** 2026-10-22（美国东部时间）；**本版取代尚未交付执行的 NEXT-05 v1.0**。  
**最优先目标：** 在用户离线期间获得真实、经过独立验收的优化结果；不要再因为等待用户逐次确认而重复进行无产出的审批循环。

> **执行方立即读取：** 这是用户明确要求“从当前版本开始，无人值守持续运行”的**有限范围事前授权及执行指令**。执行方可以在现有权限与本文件门禁、预算范围内办理相应的独立授权配置提交；这**不是**允许绕过既有 SHA/manifest/求解器门禁、擅自改变研究假设、无限重试或伪造研究结果。**每个后续阶段必须自己满足客观放行条件，不能仅凭本文件就声称 PASS。**

---

## 0. 与 NEXT-05 v1.0 相比必须首先纠正的事实

上一版写成“A1 仍在等待第一次 LP-R”。**该状态已失效，严禁照 v1.0 从首次 LP-R 开始运行。**

### 0.1 GitHub 最新已核查状态（开始执行时再次从 L2、GitHub 验证）

| 对象 | 当前事实与约束 |
|---|---|
| A1 历史首次授权 | 配置提交 `f6dc3151fe9228f0d162829ee3df4224d1eeced1`；冻结代码源 `802c9d9414514641fd2b088b45ec7ea945be18a4` |
| **A1 首次 LP-R** | **优化器已完成 `ok/optimal`，但结果读取 `KeyError`，最终 `output_failed` / `pass=False`。** 历史已消耗 1 次 LP 调用，不得改写为 PASS |
| 首次 LP-R 仅供核查的目标值 | λ = **2,587.772185 MW facility**，约 2,253 MW IT；**未经验收，不能列为正式 `H_resource`** |
| A1 历史 LP-N | **NOT_RUN** |
| 原始历史日志 SHA | `HEADROOM_SOLVE_LOG.csv`: `05bd03c2fa629f7af0f1f767d9d9758bd5b156856c00f5d75ce06a5e7142e28d` |
| 原始历史结果 SHA | `LP_R_H_RESOURCE_RESULT.json`: `d80d6f9e11b3765699ddc052021c06742f26e0a2d288daeafc81ad8d0162bd27` |
| **A1 已通过静态验收的补救代码** | **`07c881a4c643a800dfc55257716671e2791a48ab`**；代码之后已有报告/日志提交（执行方称 HEAD `5380f0f5`，执行时重新确认） |
| A1 补救配置 | `workflow/config/config.byop_post_v16_a1.yaml` 中 `run_dir: rerun1`；`prior_ledgers` 固定旧两文件；目前新批准字段为 `NOT_APPROVED` / `null` |
| A1 修复内容 | 从各 Linopy 变量本身读取解；求解结束后**先保存网络及 PV16 解，再输出和验收**；使用独立 `rerun1` 台账 |
| A1 修复验收 | L2 214 passed、0 failed；其中注入解完整 writer 测试 3/3，`a1_dry` 结构仍为 373,249 变量 / 967,980 约束 / 0 整数，旧 LP 数学构造、10 份输入和 v1.6 基线未改变 |
| A1 基线 SHA | `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`；`.nc` 文件只在 L2 有完整副本 |
| A2 模型开发分支 | `work/a2-postv16-static`，HEAD `39a74ff5f96acafc356d40978e33048768fce6a7`，代码基点 `81bd57438c7b002d6cfe455ec2b3f973f33ed12c` |
| A2 静态能力 | FIX-01～09 已实现；先前 75/75 结构检查，L2 245/0 回归；**尚无正式 S0/S1 结果** |
| Git 分支 | 默认 `main` 尚落后；A1 主线 `mainline-v13-stageA` 与 A2 分支仍需在完成补救 A1 后合并 |

**真实状态优先级：** L2 进程及锁、真实求解父/子台账、正式结果和验收 JSON、实际文件 SHA、Git HEAD 和授权门禁，优先于历史 `NEXT_04_EXECUTION_REPORT.md`、`.done` 文件或模型记忆。不要将“GitHub 没有新结果”理解为“L2 没有正在执行的作业”。

### 0.2 本次无人值守授权的解释与边界

**研究者当前授权原文：**“我后面要睡觉了，基于当前进度，把之前 NEXT-05 工作包修改一下，授权从当前版本开始无人值守持续运行。”

据此，从上述**已核查的 A1 补救代码版本**继续，无须在接下来每个阶段人工在线重复批准。执行方可以在本文件**预先列明的阶段、代码验证、模型、计算额度、物理一致性和停止条件**下办理配置授权、提交、启动求解与连续交接。

- **A1 补救：** 明确批准 `07c881a4c643a800dfc55257716671e2791a48ab`，仅限独立 `rerun1` 内新增 **LP-R 最多 1 次 + LP-N 最多 1 次**，总新增上限 **2 次顶层优化器调用**、0 自动重试；历史第一次 LP-R **另外计入总历史次数**（若全部运行，历史累计最多 3 次）。
- **A2 正式 S0/S1：** 补救 A1 被正确验收或符合 §4 的可解释例外，并且 A2 合并、manifest 重建、回归和物理检查**全部通过**后，预先允许执行方对**合并后的真实代码 SHA**登记一份新的、**独立于 A1** 的 A2 授权配置；上限 **2 次情景级尝试、3 次顶层优化器调用**、0 自动重试（`S0_COST`、`S1_SPEED_HIERARCHY`、`S1_COST`）。
- **A3 有限机制试算：** **仅当 S0/S1 均 PASS**、可审计的 S2/S3 物理可行域一致且 A3 独立父/子日志门禁通过时，允许做 2026–2031、ERCOT、中等需求路径的 **S3、S2 开发商及公共响应、matched-service**，A3 顶层调用合计 **最多 30 次**、0 自动重试。绝不默认把 A2 的三次预算套用给 A3。
- **研究口径：** 在本授权限定范围内一并接受 D2、D4、D5、D6（见 §2）。**不批准**增加不相关敏感性、全国扩张、私改数据、改变可靠性标准、造假或未经认证的 48/72 h firm 承诺。
- **版本授权不可继承：** 各阶段需要独立 `approved_git_sha`、manifest、配置和完整门禁 PASS；执行方在授权-only 提交中填写已冻结代码 SHA，不得凭自身判断随意扩展许可到新代码或新场景。
- **研究者身份：** 仓库此前已由研究者明确登记 `approved_by: sw2434@cornell.edu`。此处只允许原样复用该已核实标识，新增 `authorization_basis: NEXT_05_v2_USER_ADVANCE_AUTHORIZATION` 的执行记录，不得声称是研究者亲自完成代码提交或签署其他身份文件。

**对执行方的直接指令：** 本文件本身及用户本次指令**就是上述范围的事前授权**，不需要再因研究者睡觉/离线而停止索要一次同范围的授权。但必须按现有配置和 gate 的实际要求执行独立、可追溯的批准提交，且任何硬门禁未通过不得调用求解器。

---

## 1. 资源管理、执行期限和不可重复的求解台账

1. **以成功获得科学结果为先。** 夜间优先级：A1 补救 → 合并 A2 → S0 → S1 → 必要 S2/S3 试算。不重复制作 NEXT-04 式静态批准报告、不启动新敏感度矩阵。
2. **不假定执行端一定持续在线。** 如果执行平台再次触发限额，先提交状态机、产物索引、代码 SHA、下一个可安全启动的步骤；下一次恢复时继续而非从头执行。若环境支持合规的后台任务/调度器，只有在其能在退出后持久保存调用状态和文件且不违反共享集群政策时才可使用；不得只在聊天中声称“仍在后台运行”。
3. **调用前记录。** 所有 LP 必须在优化器调用前原子写入 `STARTED`，包含研究阶段、调用类型、代码/数据 SHA、父尝试 ID、实际线程数和时间。任何 `STARTED`、`DONE`、`ERROR` 行均占额度；遇到挂起先查是否仍有进程，不自动二次调用。
4. **分阶段预算独立。** `rerun1` 2、A2 3、A3 30 次顶层优化器调用；A3 内分层 `m.solve` 实际次数均计算，Gurobi 一次多目标调用的内部目标阶段只作为其元数据；纯静态建模不是优化器调用。**不能跨阶段挪用额度**。
5. **共享计算资源。** L2 曾有 24 个逻辑核心，实际空闲不断变化。启动前检查 CPU、RAM、磁盘、Gurobi license 和其他用户负载，线程数在实际剩余资源内选取；大型 LP 串行执行，不允许并行挤占他人任务，不允许无监管无限提交队列作业。
6. **连续运行的停止点：** 客观门禁无法恢复、关键输入 SHA 异常、物理模型不兼容、预算耗尽、正在执行的求解状态不可判断、共享资源不足，以及本轮已完成 S0–S3 有限试算时，及时结束或安全暂停。不以形式上的某个小时数替代真实状态判定；若即将耗尽执行平台会话且没有持久化任务能力，不新启动不可追踪的大作业。

---

## 2. 本次一并确认的科学口径（不用凌晨逐条发问）

| 编号 | 采用的研究假设 | 必须披露的局限 |
|---|---|---|
| **D2** | Bexar `p650 0` 天然气可交付性按现有 L2 证据代理，不凭邻近机组自动认证可靠 MDQ/专属合同 | 气源与许可代理不等于真实供气合同 |
| **D4** | `stores=3 h`；同一运行 SOC 的备用起末能源约束；FIX-08 按真实连续片段划分的 SOC 边界近似 | 代表性时段不代表季节储能；求解后逐资产、逐片段验证净 SOC 差 |
| **D5** | DWB Stage 2、PBRP-765-A/B 是 S0–S3 共同外生承诺资产，历史绝对投资单列，不在场景差异中重复计价 | DWB 371 M USD 为 2019 币值；PBRP 每条 3,020 M USD 为 2024 币值代理；已付/未付份额为假设 |
| **D6** | S1 既有用户负荷切除 ≤ S0 同单元同快照 + 0.001 MW；验收容差 0.002 MW；S0 参考 SHA 强约束且不自动填补 | 这是严格 no-harm 规则，不等于 ERCOT 官方接入认证 |
| **A1** | 2025 冻结电网、432 个 1h 快照、3 GW 备用、既有负荷硬零切除、LP-R 放松线路限额 vs LP-N 保留网络限额 | 接入裕度只是研究模型筛查，不是实际 POI 分配；不得用 max-λ 的非唯一调度推导真实电价 |
| **A2** | ERCOT 16 站点、2026–2031 逐年、单一中等 AIDC 需求、3h 代表时段；S0/S1 使用完全一致公共资产和成本/COD 规则 | 不能将首轮结果解释为 2050 年的路径依赖 |

凡影响科学可比性的变更（需求增长、Firm 认证、备用、气源、公共扩张、主体最优化目标、成本币值）均不在本次授权中。工程层面可修复输出、测试、文件路径和日志，但如果新改动影响模型可行域，需据既定标准停止该结果的正式解释，不得硬凑 PASS。

---

## 3. H0 — 限额恢复后只执行一次真实状态盘点

执行端从 GitHub + L2 获取：

- 当前 `mainline-v13-stageA`、`work/a2-postv16-static`、`main` 的完整 SHA、工作树脏文件（区分真实修改与 CRLF-only 差异）、有没有并发任务；
- `workflow/config/config.byop_post_v16_a1.yaml` 的 `run_dir`、`prior_ledgers`、三项新授权字段；`POST_V16_A1_PRE_RUN_MANIFEST.json`；原两个不可变文件的 SHA；
- `POST_V16_A1_HEADROOM/rerun1/HEADROOM_SOLVE_LOG.csv` 和原目录历史台账；若发现 `rerun1` 已启动或 PASS，则只推进未执行的合法后续步骤；
- L2 的 `baseline_2025_tamu_prepared.nc` 的实际 SHA；A2 的现有父/子日志；shared L2 的 CPU/RAM/磁盘/Gurobi license。

写出 `OVERNIGHT_START_SNAPSHOT.json`，绝不推测 `rerun1` 未运行；若是 `STARTED` 但没写 DONE，先查真正在运行的优化器和检查点文件。

**立即执行条件：** 补救代码与 manifest、旧文件固定 SHA、基线、现有工作树均匹配，`rerun1` 的 LP-R 尚未消耗调用预算，则按本次预先批准办理 **A1 授权-only 配置提交**；然后验证真实 A1 gate PASS，**直接 H1 求解，不再请求研究者人工确认**。

---

## 4. H1 — A1 补救 LP-R/LP-N：新增两次调用、不可变旧历史

### 4.1 最小批准提交（用户本次已提前授权）

核对以下起点：

- 冻结代码 commit：`07c881a4c643a800dfc55257716671e2791a48ab`；若执行环境代码/输入与该 commit 不一致，必须查明差异，**不得自动把更新过的新代码 SHA 当作用户已批准**；
- 配置已有 `run_dir: rerun1`，且两份 `prior_ledgers` SHA 为 §0 的原值；
- `post_v16_headroom.py` 的 SHA 仍是 `f45940f7cf347c2d456194b8a9bb2cb19d5df9dfa0555e1809224ed6b4749e2`，10 份输入、基线、压力事件、负荷和备用参数均未改变；
- 旧历史台账必须原样保留，新台账文件必须不同于旧台账，`rerun1/` 不能无故复用旧结果。

在一次**仅修改授权字段**的 config-only commit 中设置：

```yaml
# workflow/config/config.byop_post_v16_a1.yaml 的 post_v16 部分
run_authorization: APPROVED
approved_git_sha: 07c881a4c643a800dfc55257716671e2791a48ab
approved_by: sw2434@cornell.edu
```

保留 YAML 其他全部字段。执行记录注明：`authorization_source = researcher user message requesting unattended continuation + NEXT-05 v2`；`approval_action = recorded_by_executor_under_advance_authorization`。不要伪称该提交是研究者亲手操作。只有提交后从 L2 验证 A1 `gate` 真实返回 `approved=true`，才可进入 LP-R。

### 4.2 唯一正式求解入口

L2 主检出 `.../pypsa-usa/workflow`（不是 A2 `.worktrees/a2/workflow`）：

```bash
THREADS=<根据当时 L2 实际空闲核数设定> bash byop/run/run_post_v16.sh a1_lp_r
# 仅当 rerun1 的 LP-R DONE / ok / optimal / acceptance.PASS == true:
THREADS=<根据当时 L2 实际空闲核数设定> bash byop/run/run_post_v16.sh a1_lp_n
```

**新增额度：** `rerun1` LP-R 一次，LP-N 一次；零自动重试，`rerun1` 当中途失败不能清除台账重开 `rerun2`。原始 `LP_R_H_RESOURCE#1` 永远保留为 `output_failed / False`；若两次补救都成功，**A1 历史总计 3 次真正 LP 调用**。

### 4.3 成功后必须保存并检查

- 首先保留求解后的 `.nc` 和 `PV16-*` 变量解文件及其实际 SHA，检查可读取性；这一步必须先于结果写入及 `acceptance()`；
- 3 GW 备用、同一 SOC 的储能备用能源、两块 B0/BL 的既有用户零切负荷、节点平衡残差 ≤ 1e−3 MW、λ 有限且低于 200,000 MW 上界、零整数变量、`ok/optimal`；
- **LP-R 若得到约 2,587.77 MW facility**，只可作为与前次未验收 objective 的一致性诊断；正式 `H_resource` 必须来自本次全部验收 PASS；如果重跑结果不同，优先核查模型指纹、求解选项和最优目标，不隐瞒差异；
- LP-N 只有 LP-R 完全 PASS 才执行；有效 `0 ≤ H_network ≤ H_resource + 1e−3 MW`；网络压力位置、两者差值需要附线路/站点证据；
- `.done` 文件不是合格计算证据；必须是新 `rerun1/HEADROOM_SOLVE_LOG.csv` 的 DONE/ok/optimal/pass，以及各 RESULT.json 的逐项验收 PASS，二者一致。

### 4.4 A1 出错后的**无额外求解器调用**挽救

如果 Gurobi 已 `optimal`、新的**已保存解检查点**存在，但 writer 或验收代码失败，允许执行方：

1. 保留 `rerun1` 的原始 `STARTED/DONE/ERROR` 行、失败原因、已保存解及 SHA；本次调用已消耗，禁止再提交同一 LP。
2. 在另一个**postprocess-only** 目录修复明确的读取/格式错误，执行不含 solver 的读取、重建报告与验收回归；把新审核结果标记 `POSTHOC_RECOVERED_FROM_SAVED_SOLUTION`，保留原台账失败记录和独立的补救验证记录。
3. 如果需要让 LP-N gate 接受该已保存解，必须通过**透明且有证据的只读校验或独立签名的恢复结果接口**来判定 LP-R 是否 PASS，不能直接篡改原台账的 `pass=False` 或绕过 gate。恢复入口只能使用同一解和完全相同的数学模型，不得第二次调用优化器。
4. 如果原门禁不支持这种恢复且需要改动求解门禁的关键安全逻辑，停止 LP-N；仍可推进不消耗求解器的 A2 合并预检，不应在夜间自行创建新的未授权 LP-R 预算。

如出现真正数值失败、优化状态未知、数据损坏或物理不可行，按实际分类；不重新运行失败的 stage、不把不可行写为接入裕度 0。

### 4.5 无人值守 G2 结果处置

| A1 补救结果 | 自动处置（必须留证） | 下一步 |
|---|---|---|
| LP-R、LP-N 均验收 PASS | `G2=ACCEPTED_FOR_ERCOT_PILOT`，冻结结果和 SHA | **继续 H2 合并和 H3** |
| LP-R 可行、LP-N 因严格冻结网络而**物理不可行且有明确诊断** | `G2=A1_FIXED_NETWORK_EXCEPTION`，不填 `H_network=0` | 可进入 H2、并**独立验证有成本公共扩张的 S0**；不假装 A1 PASS |
| LP-R 因固定资产/零原有切负荷/备用压力**物理不可行且能明确归因** | `G2=A1_STRICT_RESOURCE_EXCEPTION`，不填 `H_resource=0` | 同上，仅将 A1 当做限制明确的筛查，不作为正式裕度结果 |
| 输出代码异常但解可恢复、验收独立 PASS | `G2=A1_POSTHOC_VALIDATED`，附同解、双记录的完整审计；不得私改原失败行 | 仅在兼容的、真实 gate 放行且无需新 LP-R 时继续 LP-N；否则仅做 H2 静态准备 |
| 模型、数据或 gate 指纹异常；无法分类的数值/结果故障 | `G2=BLOCKED_UNVERIFIED` | 停止 A1/A2 正式求解；允许纯静态排查、保留完整断点 |

**特别说明：** A1 是冻结 2025 资产的压力筛查，S0 是允许付费公共扩张的多年 LP，它们可行域不同；只有明确的**物理不可行例外**允许不再等待研究者在线审查而转入 S0 独立测试。不能把 A1 工程故障等同于物理不可行豁免。

---

## 5. H2 — A1 已结束后合并 A2，并收敛至默认 `main`

**触发条件：** §4 G2 为双 PASS，或按明确物理诊断获上述例外；原 A1 补救记录已归档，不再修改已运行基线。任何未解决的 A1 读取故障仍可做静态合并预检，**但不意味着 A2 求解自动放行**。

1. 保存 A1 修复代码、批准提交、manifest、求解 `.nc`/结果/台账及全部 SHA；根据真实状态打 tag（失败不能冠名 PASS）。
2. 以 A1 实际主线为集成目标，审查 A2 旧分支 `39a74ff5…` 自共同祖先 `802c9d94…` 起的真实代码差异，将 FIX-01～09 和相关测试/配置/二进制校验规则合并，特别保留 **A1 修复后的 `post_v16_a1.py` / `post_v16_gate.py` / `test_post_v16_a1_writer.py` / `run_dir`**，不能被旧 A2 分支内容覆盖。
3. 历史同名的 `A2_PRE_RUN_MANIFEST.json`、`A2_GATE_VERDICT.json`、`A2_REGRESSION_SUMMARY.json` 不盲选一方：先另存旧证据，**再对合并后的代码重新生成**；检查 `.gz` 按 binary 跟踪、CRC 与字节哈希。
4. 合并后至少运行一次完整 L2 回归和 75 项结构 QA，并包含 A1 新 writer 回归（之前 214 测试）；确认新增的 3h `stores`、FIX-08 SOC 分段、FIX-09 调用计数、324 对输电双向配对、公共建设 COD、S0/S1 公共资产完全一致、no-harm 来源严格不缺值。**此阶段 0 优化器调用**。
5. 若 `main` 可 fast-forward，则同步；若有独立新提交则先审查差异后正常 merge。保留 remote commit 与 L2 SHA 一致，禁止强推、强制 reset、删除任何历史结果。临时分支夜间**不必删除**，后续开发仅在 `main` 上继续。
6. 输出 `A2_MERGE_AND_REVALIDATION_REPORT.md` 和新的 A2 manifest / code SHA。注意：旧 A2 代码 `81bd5743` **不再是合并后正确的正式批准 SHA**。

若仅有工程合并错误，可在**未实际运行 A2**前修复并重新静态验证、重新冻结 SHA；若发现物理可行域已经改变、需修改核心建模假设或测试无法通过，停止 A2 求解，保存具体失败和剩余合法进度，不以“模型大致可用”替代门禁。

---

## 6. H3 — 对统一代码独立放行 A2，连续求解 S0/S1

**严格前置：** G2 有可审计的放行结论、`main` 与 L2 的合并版 SHA 一致、A2 manifest 重新建立并匹配、静态回归及结构检查全 PASS、A2 正式父/子求解台账未消耗本阶段预算。

### 6.1 不经研究者再次在线交互的授权流程

1. 对最终**合并且未写新批准字段的代码完整 SHA**进行冻结并保存；在 `OVERNIGHT_AUTHORIZATION_RECORD.md` 写明：`stage=A2`，`basis=本用户对 NEXT-05 v2 的无人值守明确授权`，`approved_code_sha=<merged SHA>`，`scope=S0 + S1_EARLIEST only`，`budget=2 parent attempts/3 top-level calls`。
2. 再执行一次**config-only commit**，仅把 `workflow/config/config.byop_post_v16_a2.yaml` 的 `run_authorization` 设为 `APPROVED`、`approved_git_sha` 设为上述完整 SHA、`approved_by` 复制已确认标识。**这不是 A1 许可的自动继承**。
3. 重新调用 A2 自己的 gate，核对统一版 manifest、已记录授权源 SHA、基线 SHA、所有源码/输入内容及预算。若出现非批准字段不一致，先做审计、必要的静态修复及版本冻结，**不许直接绕过**；无法保持用户预先授权的范围则停止。

### 6.2 受控三次优化器调用

从统一 `main` 的 `workflow/` 目录进入实际脚本：

```bash
bash byop/run/run_post_v16_a2.sh gate
# 门禁允许 S0、父/子台账未调用过时：
THREADS=<实际可用安全值> bash byop/run/run_post_v16_a2.sh s0s1
```

调用序列严格为：`S0_COST` → 验收并 SHA 固定 S0 的 `S0_NO_HARM_REFERENCE.csv` → `S1_SPEED_HIERARCHY` → `S1_COST`。`S1` 两次子调用属于**同一个** S1 情景级父尝试，顶层合计 **3 次**。Gurobi 多目标内部层级不是新的顶层 API 调用，但要记录其目标数和状态。

**恢复条件：** 若仅 S0 已 PASS，S1 未 STARTED，必须经当前 gate 的实际合法断点入口启动只含 S1 的命令，且保持相同 base/outdir/case-id，不得重新执行会调用 S0 的 `s0s1`；不能为了绕开门禁另造新场景目录。

### 6.3 强制验收与真实结果

- S0、S1：`ok/optimal`、0 整数、节点平衡 ≤ 1e−3 MW、3 GW 备用、热机/储能备用与 SOC 起末约束、公共资产付费及 COD、324 对扩张线路正反向 MW 相等、不得无成本扩张；
- FIX-08：**解后**按资产 × 年 × 连续代表性片段计算 `SOC_start_MWh, SOC_end_MWh, SOC_end_minus_start_MWh` 和起末备用能源约束余量。仅在真循环链闭合时宣称每段能量中性；非循环/跨年投运设备分别说明，不只检查约束“存在”；
- S0：完整写出既有用户逐单元、逐快照 shed 文件和 SHA；S1：严格原样使用该文件，no-harm 限制 +0.001 MW、验收 0.002 MW；零缺失/重复，不填补；
- S1：先 Speed-First（按年度最高可交付服务并锁定各层级），再 Cost-Second；最终交付量保留所有锁定速度目标并由解后重新检查；
- 父/子调用日志正确、没有缺失或额外顶层调用；若结果保存或统计阶段出错，优先利用已保存模型解进行**postprocess-only** 恢复，不重跑优化器；
- S0/S1 双 PASS 后，立即生成 `S0_S1_MAINLINE_COMPARISON.csv` 和一页 `S0_S1_MAINLINE_FINDINGS.md`，明确新增 AIDC 对公共发电、储能、输电、COD、服务等待、实际资源成本与原有用户保护的影响；如无显著瓶颈也要如实报告。

**S0 失败不运行 S1。S1 hierarchy 失败不运行 S1 cost。** 任何不明 `STARTED` 不自动复跑，严禁私降备用、偷加容量、修改需求或解锁无成本 S0CAL。

---

## 7. H4 — 条件满足时继续 S2/S3，但保持物理可比性与 LP-only

**只在 S0 和 S1 双 PASS 且已冻结其输入/结果后开始，不将本次 A1/A2 授权当作无限 A3 权限。**

1. 先完成 A3 独立 gate/manifest/求解子调用登记与静态一致性测试。必须审计 `developer_joint` 的**每年 lex LP 和成本 LP**、公共扩张 LP、协调规划 LP 和 matched-service LP。不得直接沿用 A2 的 3 次调用计划，也不得让旧 `RUN_AUTHORIZATION` 单独解锁所有求解。
2. 开发商 S2：**先最大化逐年合格 IT 供电速度，再最小化私人成本**，保留各年度 lex 锁定，不用虚构大罚值替代字典序。Grid-Only/Grid-Flexible/Islanded 与 N/R/C 新建/复用/合同是两个不同维度，R 池空则不能凭空复用。
3. S3：与 S2 严格共享供电技术、天然气 MDQ/代理、许可→COD、公共 POI、DWB/PBRP、3 GW 备用、储能分段约束、no-harm、投入工期等物理集合；社会与私人成本的区别不能来自单方面放宽可靠性或供电条件。
4. **风光储 Firm 认证：** 当前只有 24 h 压力样本，不允许声称已完成连续 48/72 h full-year Firm。此次若要试算，对 S2/S3 **共同**把未经连续 48/72 h 验证的专用 RE+BESS 全年 Firm 信用保守设为 0（但保留其可用发电/储能能量、技术及成本），同时确认不会在另一权利路径重复记 Firm；标签 `CONSERVATIVE_FIRM_SCREENING`，不作为正式结论。若无法保证两侧一致，则只做 A3 静态交接、停止这些 LP。
5. 调用优先顺序：一次 `S3_COORDINATED`；之后最多三轮 `S2_DEVELOPER_JOINT`（2026–2031 通常每轮最多 6 年度 lex + 1 cost）及对应 `S2_PUBLIC_RESPONSE`；仅在 S2 符合交付要求时执行 `S3_MATCHED_S2`。用真实代码审计建模调用，**总 A3 顶层调用 ≤ 30**，每次 STARTED 前审查预算，0 重试。理论估计约 26 次不替代实际日志。
6. 若前一轮 S2 公共响应未收敛，记录 `S2_NOT_CONVERGED`；剩余预算和时间允许可进入下一轮，但**不得称为正式 S2 最优或有可信 S2−S3 差异**。必须在 matched-service 固定同等合格服务后，才比较两者真实社会成本；不得把少供电省钱误读为效率更高。
7. 本轮只有 ERCOT 2026–2031、小规模机制试算；不得自动开 2032–2050、全国 48 州、额外敏感性矩阵或声称 M3 长期搁浅已证实。长周期需求截至 2035、新增 2036 后为零、2040/45/50 节点是后续研究任务。

A3 必须有完全独立的 `A3_GATE_VERDICT.json`、manifest、父/子调用 ledger 和代码 SHA 授权记录；无法实现“额外调用被拒绝”和异常崩溃可恢复的最小机制，就不启动 A3 solver，但不影响 S0/S1 的成果交付。

---

## 8. 失败时自动推进的合法边界

| 阻断情形 | 可以做的事 | 不允许的事 |
|---|---|---|
| 历史 LP-R `output_failed` | 保存不可变日志并在 `rerun1` 按本次新授权补救求解 | 清空第一次 ledger、把旧未验收 λ 作为 H_resource |
| 补救 LP-R 已 optimal 但 writer 报错 | 在已保存解上独立 postprocess-only 修复/核验；不消耗新 LP | 自动运行 rerun2、改写旧 `pass=False` 记录 |
| A1 LP-R 或 LP-N 确定物理不可行 | 如 §4 有完整归因，写严格筛查例外；按不同可行域独立进入 S0 | 将 infeasible 当作 0 MW、放松既有负荷硬保护或备用 |
| A1 未知状态、SHA/授权不符 | 保留证据，做纯静态 A2 合并预检和阻断归因 | 用替代 SHA、伪造新授权、启动 A2 solver |
| 合并回归失败 | 修复明确的工程错误，重新静态验收并冻结版本 | 未通过完整门禁就正式求解 S0/S1 |
| S0 solver/验收失败 | 保存日志、查看 IIS/输出、可在解文件存在时做后处理恢复 | S0 未通过就运行 S1、重试、放宽物理约束 |
| S1 分层或成本阶段失败 | 保存对应每个子调用和独立结果 | 跳过速度目标、删除失败调用行、重算同一阶段 |
| S0/S1 PASS 但 A3 物理一致性不足 | 交付主线 S1−S0 结果及 A3 缺口清单 | 以 24h 样本冒充 72h Firm 或未经匹配宣称 S2/S3 社会效率差 |
| 平台限额或集群资源紧张 | 写 checkpoint、保存安全下一步与未消耗额度 | 暗中并行过量求解、无落盘保障的无限后台运行 |

**允许更正工程错误，不允许改变科学命题。** 特别是补救输出路径、恢复序列化与后处理，不应触动容量、工期、成本、需求、备用、技术资格或 solver 模型约束。

---

## 9. 无人值守运行状态、提交与报告（必须持久化）

最初创建并随里程碑更新 `current_work_pckg/`：

- `OVERNIGHT_AUTHORIZATION_RECORD.md`：逐阶段明确记录用户本次事前授权、历史 A1 首次失败与新批准的区别、每个实际代码 SHA、授权-only commit、预算、操作代理身份；
- `OVERNIGHT_CONTROLLER_STATE.json`：`phase, code_sha, run_id, baseline_sha, prior_failed_attempt, a1_rerun_parent_calls, a2_parent_calls, a2_child_calls, a3_child_calls, remaining_budget, current_process, checkpoint_sha, last_pass, blocker, next_safe_command`；
- `OVERNIGHT_EXECUTION_REPORT.md`：状态机里程碑、每项真实 solver 调用、完整验收、失败归因、下一条安全操作命令；
- `OVERNIGHT_RESULTS_INDEX.csv`：scenario / stage / code_sha / baseline_sha / manifest_sha / solver_status / acceptance / saved_solution_path / saved_solution_sha / result_path / comparability；
- `A1_RERUN_EXECUTION_REPORT.md`：**明确列出历史 LP-R #1 的失败**及 `rerun1` 新执行，不可把两者汇总成“LP-R 已运行一次”；
- 条件产生的 `A2_MERGE_AND_REVALIDATION_REPORT.md`、`S0_S1_EXECUTION_REPORT.md`、`A2_SOC_SEGMENT_POSTSOLVE_AUDIT.csv`、`A3_PILOT_EXECUTION_REPORT.md`、`S0_S1_MAINLINE_COMPARISON.csv`；
- `OVERNIGHT_RETURN_PACKAGE.zip` + `FILE_LIST_SHA256.txt`：只打包必要的文本、日志、摘要 CSV/JSON 和小文件；大型 `.nc`/solver 工程文件只列 L2 真路径、大小、SHA，不能为同步 ZIP 复制并覆盖原始结果。

报告开头固定状态块（值必须真实，不允许猜测）：

```text
WORK_PACKAGE: BYOP_NEXT_05_OVERNIGHT_v2
AUTHORIZATION_MODE: USER_ADVANCE_AUTHORIZATION_WITH_INDEPENDENT_GATES
A1_FIX_APPROVED_CODE_SHA: 07c881a4c643a800dfc55257716671e2791a48ab
A1_HISTORICAL_LP_R_1: SOLVER_OPTIMAL_OUTPUT_FAILED (consumed 1)
A1_HISTORICAL_CALLS: 1
A1_RERUN_LP_R: NOT_RUN | IN_PROGRESS | PASS | FAILED | INFEASIBLE
A1_RERUN_LP_N: NOT_RUN | IN_PROGRESS | PASS | FAILED | INFEASIBLE
A1_RERUN_CALLS_ACTUAL: <integer 0..2>
A1_RERUN_AUTH_CONFIG_COMMIT: <sha or NOT_AVAILABLE>
A1_H_RESOURCE_MW: NOT_AVAILABLE | <accepted value>
A1_H_NETWORK_MW: NOT_AVAILABLE | <accepted value>
A1_G2: ACCEPTED_FOR_ERCOT_PILOT | A1_STRICT_RESOURCE_EXCEPTION | A1_FIXED_NETWORK_EXCEPTION | BLOCKED_UNVERIFIED | NOT_EVALUATED
A2_MERGE: NOT_STARTED | PASS | BLOCKED
UNIFIED_MAIN_SHA: NOT_AVAILABLE | <full sha>
A2_AUTH_CONFIG_COMMIT: NOT_AVAILABLE | <sha>
A2_SCENARIO_ATTEMPTS: <integer>
A2_TOP_LEVEL_CALLS: <integer 0..3>
S0: NOT_RUN | IN_PROGRESS | PASS | FAILED | INFEASIBLE
S1_EARLIEST: NOT_RUN | IN_PROGRESS | PASS | FAILED | INFEASIBLE
S0_S1_COMPARISON: NOT_AVAILABLE | DELIVERED
A3_TOP_LEVEL_CALLS: <integer 0..30>
S2_S3_PILOT: NOT_STARTED | PARTIAL | COMPARABLE | BLOCKED
NEXT_SAFE_ACTION: <command / static task / STOP with reason>
```

### Git 同步与回滚政策

- A1 补救通过前保持 A1 主检出与 A2 worktree 分离，别将 A2 代码污染 `rerun1` 的冻结代码。
- 新模型代码、manifest、授权-only commit 分开提交；报告/日志 commit 不能静默修改受保护文件；推送后用实际 SHA 比较 L2、远程和本地。
- 不用 `git push --force` / `git reset --hard` 覆盖别人的新提交；合并冲突按真实文件解决，旧 evidence 在 Git 和 L2 中可取回。
- 不要求夜里立即清理老分支。**目标是最终 `main` 成为唯一长期研究分支**，中间阶段无需为审批单独创建更多永久分支。

---

## 10. 执行端“从这里直接开始”的简明控制流

```text
START / 执行额度恢复
  ↓
H0 重新核验 GitHub + L2 状态、进程、旧 LP-R 失败证据、rerun1 台账
  ↓
旧 LP-R #1 = output_failed (永久保留；不能当作结果)
  ↓
A1 补救代码 07c881a4 + 修复版 manifest + 旧证据 SHA 一致？
  ├─ 否 → 停止新增 A1 求解，执行只读定位并保存进度
  └─ 是 → 按用户本次预授权做 config-only approval (rerun1)
            ↓
         A1 gate PASS → LP-R #2 (首次补救 LP-R) → 实际验收
            ├─ PASS → LP-N #1 → 实际验收 → 自动 G2
            ├─ 可证明固定资源物理不可行 → G2 严格筛查例外
            └─ 工程失败/未核实 → 首选保存解无求解器恢复；否则停止 A2 正式求解
            ↓
H2 合并 A2 FIX-01～09，**保留 A1 修复版**，回归 + 75 结构 QA，统一 main
  ↓
H3 在合并后的真实 SHA 上单独登记 A2 授权，gate PASS
  ↓
S0_COST → S0 PASS → S1_SPEED_HIERARCHY → S1_COST → S1 PASS
  ↓
形成 S1−S0 正式对照，冻结结果/台账
  ↓
若物理一致、时间和预算允许：A3 独立门禁 → S3 → S2 联合开发商/公共响应 → S3_mS2
  ↓
持久化报告、调用账本、Git SHA、返回包；不因用户夜间离线而循环请求批准
```

**执行者的成功标准不是“做了更多静态检查”，而是：在不牺牲可信度、无重试造假、不破坏 L2 共享资源的前提下，取得最多数量的有效可审核 LP 结果。** 如果某阶段客观失败，保存真实诊断及下一阶段的安全静态准备，不能通过人为调整假设产生预定结论。
