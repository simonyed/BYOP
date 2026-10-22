# BYOP ERCOT — Stage B2 失败修复与受控重运行工作包 v1.0

**日期：**2026-10-21  
**适用分支：**`simonyed/BYOP` — `mainline-v13-stageA`  
**审计基线：**`951ddb8bd6bca575a78ecd3562c34e252c528f89`  
**上游基准：**B1 `af00b32a7699344fd64b4129e02957dc3aeb4486`  
**目标：**以最少代码修改修复 B2 的 S1 字典序求解失败及 S0 既有用户大规模切负荷，得到可信的 S0/S1-EARLIEST 结果，并保留完整可复现的失败证据。  
**当前授权：**本文件**仅授权执行代码准备、无求解器测试及提交审计**；**不授权**自动重跑 B2 或启动 B3/B4。新代码 SHA 经研究者明确批准且门控通过后，才可执行本文件的 B2-R 阶段。执行方不得将本文件视为直接修改 `run_authorization` 的许可。

---

## 0. 执行摘要（请优先阅读）

本次只开展 **F1 + F2-b + B2-R** 三项，其他模型结构冻结。

1. **F1 — 数值一致性修复：**使 `lex_presolve()` 的独立 Gurobi 模型采用与 PyPSA/Linopy 正式求解一致的可行性/最优性容差和 barrier 设置；统一 S2 `developer_joint()` 的设置。补充可诊断的失败记录及严格 Speed-First 目标层级核查。**不能把当前 INFEASIBLE 直接认定为容差不一致的已证实结果。**
2. **F2-b — 有证据的可靠性参数修订：**ERCOT 主线正式经济运行的既有负荷切除罚价从 **10,000 USD/MWh** 调整为 **35,685 USD/MWh**，作为采用 Brattle（2024）ERCOT-wide、**1 小时停电** VOLL 的规划敏感参数；保证原生负荷和继承爬坡负荷采用同一价格，成本账本保持一致。**不保证 S0 切负荷一定降为零；若仍显著切负荷，应据实报告，不得继续盲目调参。**
3. **B2-R — 受控重运行：**在新的案例目录仅重新运行 `S0 + S1_EARLIEST`，不调用五项归因情景，不运行 S2/S3，不重跑 ERM/S0CAL。

**核心研究目标不变：**先以 TAMU64、Epoch 8-bus、2026–2031、G-REAL、mid、新增 AIDC 固定空间，检验 Grid-Only 是否存在可信、可解释的并网延期，才能进入 BYOP 的 S2/S3 对比。无论延期大小，都不能为获得预期 BYOP 效果而调节物理输入。

## 1. 已核实的失败事实与必须保留的证据

### 1.1 失败版本与指标

来源：提交 `951ddb8b` 下的 `current_work_pckg/STAGE_B2_GRID_ONLY_REPORT.md`、`workflow/results/BYOP/mainline/STAGE_B_STAGE_AUDIT_B2.json` 和运行日志。

| 项目 | 已有事实 | 解释 / 限制 |
|---|---:|---|
| B2 正式经济 S0 | `optimal`；4,094,602 变量、7,162,661 约束、0 整数 | 不是 S0CAL 的高罚价最小增容目标 |
| S0 既有负荷切除 | 32,808.6 MWh（32.81 GWh） | 原生 32,732.6 MWh，继承爬坡 76.1 MWh |
| Red Oak (`p630 2`) | 峰值 965.7 MW；2028–2029 最明显 | 背景既有用户可靠性问题，不能误作新 AIDC 的延期 |
| S1_EARLIEST | `lex_presolve()` 导出模型 Gurobi status 3 `INFEASIBLE` | 没有求出 S1 投运量及延期；“容差不匹配”仍属待验证假说 |
| 正式 S0/S1 主求解设置 | `Method=2`, `Crossover=0`, `BarConvTol=1e-5`, `FeasibilityTol=1e-3`, `OptimalityTol=1e-4`, `BarHomogeneous=1` | 线程数由运行命令设置 |
| S1 导出的字典序 Gurobi 模型 | 原版仅设置 `Threads`；其他为默认，`FeasibilityTol=1e-6` | 与正式求解器不同，且 no-harm 额外余量恰为 `0.001 MW` |
| B1 ERM | 2026–2031：8.20%、5.25%、2.56%、−0.59%、−1.95%、−4.17% | B2-R 不变 |
| B1 S0CAL | 9 条线路，1,095.6 MW；AIDC 邻近 4 条合计 665.9 MW | B2-R 不变，不删除、不中途折算 |

### 1.2 禁止覆盖的失败证据

不得删除、覆盖或修改以下已有诊断成果：

- `current_work_pckg/STAGE_B2_GRID_ONLY_REPORT.md`
- `current_work_pckg/STAGE_B2_RETURN_MANIFEST.md`
- `workflow/results/BYOP/mainline/STAGE_B_STAGE_AUDIT_B2.json`
- `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01/` 原失败目录及 `scenarios/S0/*`
- `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01.excerpt.log`

后续结果使用**新 case-id / 新目录**并记录与旧版的对比，不能重写失败日志后声称原版成功。

## 2. F1：统一 S1/S2 数值设置并保持纯 LP

### 2.1 修复文件与范围

优先修改：

- `workflow/byop/model/rearch_mech.py`：`lex_presolve()`、`developer_joint()`；若仍在主线可能调用 `private_mode()`，其相关参数也应同步一致，**但不要扩充或重新启用非主线的模式枚举**。
- `workflow/byop/tests/test_mainline_v13.py`：增加不调用求解器的配置与异常路径测试。
- 必要时少量修改日志或结果后处理，**不能**改变 IT 需求、POI、ERM、线路或 BYOP 技术数据。

正式目标参数作为单一明确定义，在两条主线求解路径共享：

```python
MAINLINE_GUROBI_LP_OPTIONS = dict(
    Method=2,
    Crossover=0,
    BarConvTol=1e-5,
    FeasibilityTol=1e-3,
    OptimalityTol=1e-4,
    BarHomogeneous=1,
)
# 每次求解再加入 Threads=<当前配置>, OutputFlag=<现有日志策略>
```

以上是目标行为的示意，按当前 Linopy/Gurobi API 正确接线；不要为了避免 import 循环或参数不生效而简单复制无用字典。

**必须同时满足：**

1. `lex_presolve()` 在 `gm.optimize()` **之前**显式设置这组参数，不能继续只设 `Threads`。
2. `developer_joint()` 的逐年 speed-first LP、成本 LP 使用同样的统一配置，修复目前独立使用 `BarConvTol=1e-7`、缺少 `FeasibilityTol` 和 `OptimalityTol` 的差异。
3. 记录每次求解的实际 Gurobi `getParamInfo` / 参数值、status、ObjVal（若有）、求解阶段、年份、模型行列数及最大原始约束违反量（若解可获取）。不能只写“调用已设置”。
4. Gurobi status 3 仍不可行时，先诊断同一导出模型**基础可行集**是否不可行；如果需要计算 IIS、feasRelax 或再求解，必须确认已获得对应**单独的诊断求解授权**，不得擅自放宽 `no-harm`、删除约束或提高 `FeasibilityTol`。
5. 现有模型应保持连续 LP，**整数和二进制变量为零**。禁止以“引入虚拟 binary 以解决多目标退化”替代 LP。

### 2.2 字典序最优层级的独立验证

`lex_presolve()` 当前依靠 Gurobi hierarchical multi-objective LP，每年 A1 最大化 IT 投运总量、A2 最大化符合资格的母线最低满足比例，随后把各层结果写回 Linopy 再做经济成本最小化。

重要限制：Gurobi **multi-objective LP** 的 `ObjNRelTol` 被忽略，`ObjNAbsTol` 控制变量 fixing 的 reduced-cost 阈值，**不是对目标值退化量的直接限制**。详见：<https://docs.gurobi.com/projects/optimizer/en/current/features/multiobjective.html>。

因此 F1 不要求立即重写全部 Speed-First 模型，但必须在 B2-R 中导出并校验：

- 所有 12 个层级的目标名（2026–2031 的 A1/A2）、原始目标值及最终 PyPSA 解中的对应目标值；
- 对每一 A1 年份，最终已投运 IT 总量与层级最优总量的差，须满足**现有显式下界** `T_y >= T*_y × (1−1e−6) − 1e−3 MW`，并保存绝对差和相对差；
- 对每一 A2 年份，按资格母线逐项检查 `S[s,y] >= z*_y R[s,y](1−1e−6) − 1e−3 MW`；存在 `LEXIMIN_ZERO_LOCK` 时保留显式标签、原因与后续影响；
- 如果目标层级结果有明显退化，即便 Gurobi 返回 optimal，也不能直接据此宣布“严格最早供电”通过；先报告，再决定是否改用**逐层顺序 LP + 显式目标下界**（仍然纯 LP）。

此项为结果可靠性验收，**不是**本轮预先全面改写求解体系的授权。

### 2.3 不可行时的诊断顺序（F1 后仍失败才执行）

1. 保留完整 Gurobi status 和数值参数，区分 `INFEASIBLE`、`INF_OR_UNBD`、数值失败与超时。
2. 对比“与 S0 完全相同的旧负荷约束 / S1 新增变量可设零”的结构是否真的构成可行超集。**不要事先断言 S1 必可行。**
3. 检查 `D24-no_harm_existing_customers`、POI、ERM、等式电力平衡、设备上限、时段与快照索引是否对齐。
4. 在得到求解授权后，必要时对导出模型计算 IIS；导出 IIS 中具有可读名称的约束及上/下界，优先判断是数值问题、数据错位还是物理矛盾。
5. 未确认原因前不设更宽容差、不修改已冻结的 ERM / POI / S0CAL，也不宣布“修复成功”。

## 3. F2-b：将正式既有负荷切除惩罚设为 35,685 USD/MWh

### 3.1 证据、适用范围与研究属性

证据：Brattle，*Value of Lost Load Study for the ERCOT Region*（2024），Table 17；ERCOT-wide 1 小时停电 **35,685（2024 USD/MWh）**，2 小时 21,326，4 小时 13,340，8 小时 10,435。来源：

- <https://www.brattle.com/wp-content/uploads/2024/09/Value-of-Lost-Load-Study-for-the-ERCOT-Region.pdf>
- <https://www.brattle.com/insights-events/publications/brattle-team-conducts-a-value-of-lost-load-study-for-the-ercot-region-in-a-new-report/>

**科学定位：**当前模型为 3 小时快照，35,685 **不是** 3 小时停电对应的实测 VOLL；它是以 ERCOT 一小时全系统结果作为**规划层可靠性权重**的有依据选择。报告必须记录 VOLL 为 2024 美元、其他模型费用的价格基年，不能谎称已经进行了未执行的通胀换算。本轮直接用数值 **35,685** 作为主线可靠性代理，并保留 10,000 旧情景作为敏感比较的已有证据。

### 3.2 代码实现边界

1. 只改变 **ERCOT v1.3 mainline** 正式 S0、S1、S2、S3 规划 LP 的既有用户（`load_shed`）切负荷边际成本，从 10,000 调整到 **35,685 USD/MWh**。
2. `v240_mech.py` 旧模型与非主线算例的 `SHED_COST=1e4` 不宜全局改动。优先在 `rearch_mech.py` 的 `--mainline` 配置完成后、创建任何负荷切除 Generator 之前，显式设置 `M.SHED_COST=35685.0`，并在 mainline 验证实际原生 `load_shed`、`inherited_ramp_unserved` 每个机组均采用该数值；如因导入方式使动态赋值不生效，应定位并修正，但不能悄悄遗漏某一类。
3. **保留 B1 S0CAL 校准**时使用的 `S0CAL_SHED=1e8 USD/MWh`、`S0CAL_COST=1e7 USD/MW·year`；不重跑 ERM、不重跑 S0CAL、不修改 `S0_CALIBRATION.csv`；新的 35,685 只影响正式经济优化及其账本。
4. 所有正式情景使用**同一个** 35,685，保持 S0/S1/S2/S3 可比；不得对 S0 和 S1 指定不同罚价。
5. 重新核查成本账本：`v240_mech.ledgers()` 的 `load_shed_PV_USD`、`rearch_mech.ml_shed_accounting()` 的继承负荷切除项、`social_total_USD`、`existing_customer_shed_loss_PV_USD` 和 `existing_customer_shed_loss_VOLL_PV_USD` 均要正确，**不得重复加总**。`existing_customer_shed_loss_VOLL_PV_USD` 是单独报告列，不得再加进目标或社会成本。
6. 对开发商合同违约、Conditional Firm 有计划中断、研究 AIDC 未交付的罚价保持原有逻辑，不可将 35,685 无差别传播到这些不同经济含义的项目。
7. 将 `F2_mainline_VOLL_USD_MWh=35685`、`VOLL_source_year=2024`、`VOLL_duration_basis=1h planning proxy` 写入运行日志和 case manifest；同时记录真实加载后的 Generator 边际成本最小值、最大值和异常个数。

**严禁：**为了将 Red Oak 切负荷逼近零而继续把 35,685 提到 100,000、1e8，或人为缩小线路、增大可用容量、减少背景需求。若 35,685 下仍有明显切负荷，那是应分析的物理/规划结果，而不是自动调参失败。

### 3.3 B2-R 需要额外报告的经济效果

在新的经济 S0 与旧 B2 S0 之间对比：

- 全系统、每年、每母线的原生/继承负荷切除 MWh，逐快照峰值 MW，尤其 Red Oak `p630 2`；
- 2028–2029 年 Red Oak 及周边母线的切负荷变化；
- 发电（风光、CCGT、OCGT）、储能、输电扩张的新增容量与 COD；
- 运行成本、公共资本成本和负荷损失（分别列出，不可把不同罚价下的**总目标值**差直接解释为“资源节省”）；
- 对 S1 冻结的 S0 no-harm 上限实际是多少，是否因 S0 可靠性不足而允许新负荷挤占既有客户。

## 4. 不变项与版本管控

| 资产/参数 | B2-R 处理方式 |
|---|---|
| `baseline_2025_tamu_prepared.nc` | 原 SHA-256 `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb`，不改 |
| B1 `erm02_calibration.json` | 原 SHA-256 `7d0c02f1245ebba31d26cb303cd154600e0a6626853d7d2c2910a1a268807a19`，**含负裕度**，不改 |
| B1 `S0_CALIBRATION.csv` | 原 SHA-256 `30bf497ef009f3e120d43f7d6c2995fe0b7d82ffce9d1df2b5629131397454d5`；9 条 / 1,095.6 MW，不改 |
| Epoch 八母线、mid 需求、2025 inherited ramp、PUE | 不改 |
| POI、程序日期、Firm/Conditional Firm、压力日 | 不改 |
| RICE / SOFC / Aero / 风光 / BESS 成本与工期 | 不改 |
| 可建设公共发电、储能、输电候选集和工期 | 不改 |
| `sample_weeks=26`、3 个压力日、2026–2031 | 不改 |
| S0/S1 no-harm 物理上限 `S0 + 0.001 MW` | **不改**；先解决一致求解容差，若仍不可行按 F1.3 诊断 |
| ERM 为负值 | **不改**；留给 B2 实际绑定状态或后续敏感性分析 |

原 `951ddb8b` 失败结果永久保留，新的变动仅体现在新的修复 SHA、运行配置和新案例目录。

## 5. Phase F：先只修改代码、测试与提交；禁止求解

### F0 — GitHub 基线 / 运行状态检查

- `git fetch`，确认待修改分支的 SHA 及相对 `951ddb8b` 的差异。
- 检查服务器上是否仍有相关算例在运行；不要中断无关进程。
- 保存旧结果目录的存在状态、mtime、必要文件哈希，确认本次执行不覆盖。
- 避免将 80 MB 以上日志或可能带有认证信息的本地文件加入仓库。

### F1 — 实施修改

按 §2–§3 最小改动；若共享 Gurobi options 的重构超出少量函数，应以保持现有接口/可解性为原则，不扩展功能。

### F2 — 无求解器回归测试（必须）

新增测试至少包括：

1. **参数一致性：**mock Gurobi model 记录所有 `setParam`，断言 `lex_presolve()` 的 6 项选项与正式求解器目标一致；检查 `developer_joint()` 使用相同配置。
2. **无 Solver 调用：**所有测试在真实优化入口之前返回，`SOLVER_EXECUTIONS=0`；若为了调试需要小 LP，属于求解器调用，必须在后续授权阶段执行。
3. **F2 口径：**运行构建级结构测试，验证普通背景负荷和 inherited-ramp `load_shed` 的 `marginal_cost` 都是 35,685；非 mainline 行为仍为 10,000。
4. **B1 CAL 保持：**assert `S0CAL_SHED==1e8`、`S0CAL_COST==1e7` 且三个 B1 基准输入 SHA 完全相同。
5. **成本账本：**用合成非零切负荷检验 `load_shed_MWh`、`load_shed_PV_USD`、`existing_customer_shed_loss_VOLL_PV_USD` 和社会总成本没有双重计数；同时覆盖 inherited-ramp。
6. **运行组织：**添加新的案例名入口（推荐 `pilot_s01_fix`）或新 case-id 参数，`DRY=1` 显示只调用 `S0 S1_EARLIEST`，输入仍指向**原 B1**的 ERM/S0CAL 文件，输出绝不覆盖 `MAINLINE_V13_GREAL_MID_PILOT_S01`。
7. **门控：**在 `NOT_APPROVED` 下，`pilot_s01_fix` / 诊断求解均被拒绝；B3/B4 不因本次修订自动取得授权。
8. **成果科学检查：**记录字典序每层次的独立目标值与最终解的差异；不能仅以 `optimal` 判断 Speed-First 正确。

测试失败时本轮立即停止，不启动求解器。所有参数修改必须有源码位置、变更前后值、证据和是否仅主线生效的记录。

### F3 — 首次交付及强制人工暂停

完成 F1/F2 测试后：

1. 推送修订至当前工作分支，不合并 `main`；更新必要的代码与输入 `MAINLINE_V13_PRE_RUN_MANIFEST.json`，重新核对 L2-only baseline 文件 SHA。
2. 将当前 `APPROVED` 权限复位为 `NOT_APPROVED`（或采用同等的显式阶段门控），并**禁止**因原旧 SHA 为祖先且通过旧门控而直接启动修复版。尤其要检查对当前门控来说变更过的运行脚本和模型文件已触发拒绝。
3. 提交以下文件：
   - `current_work_pckg/STAGE_B2_F1F2_CODE_FIX_REPORT.md`
   - `current_work_pckg/STAGE_B2_F1F2_PRE_RUN_AUDIT.md`
   - `current_work_pckg/STAGE_B2_F1F2_RETURN_MANIFEST.md`
   - 静态/结构/DRY 测试日志；单独的代码 SHA 和基准输入哈希表。
4. 报告必须以如下明确状态结束：

```text
FIX_STATUS: COMPLETE / BLOCKED
RUN_AUTHORIZATION: NOT_APPROVED
SOLVER_EXECUTIONS_SINCE_FIX: 0
NEXT_STEP: RESEARCHER_APPROVAL_OF_NEW_CODE_SHA_REQUIRED
```

**研究者未批准新的修复 SHA 之前，严禁执行下一节。**

## 6. Phase B2-R：研究者批准新的代码 SHA 后才可执行

### 6.1 启动门控与命令

只有研究者在独立对话/指令中明确批准**新的代码提交 SHA**及仅运行 B2-R 后，才允许执行。配置 `approved_git_sha` 指向经批准的修复 SHA，`run_authorization: APPROVED`，重新执行 `gate` 并确认 `approved: true`、输入哈希全匹配。

推荐入口（需要在修复阶段实现）——注意其输出目录是新的，**不是**覆盖旧 `pilot_s01`：

```bash
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow

# 无求解器检查
bash byop/run/run_mainline.sh gate
DRY=1 bash byop/run/run_mainline.sh pilot_s01_fix

# 此行仅在研究者明确批准新 SHA 后执行
THREADS=20 bash byop/run/run_mainline.sh pilot_s01_fix
```

其行为必须等价于：

```text
case_id=MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1
--mainline --start 2026 --end 2031 --sample-weeks 26
--erm-cal <原 B1 的 erm02_calibration.json>
--s0-cal-file <原 B1 的 S0_CALIBRATION.csv>
--scenarios S0 S1_EARLIEST
# 无 --attribution；无 S2、S3、S3_mS2
```

如果进程失败，要保留已求解场景 checkpoint 及日志；不应自动重试或跳过 S1。

### 6.2 运行结果与硬性验收

**求解与数值：**

- S0 与 S1_EARLIEST 均 `termination=optimal`；全部为连续 LP。
- S1 每一个 A1/A2 字典序目标的原始最优值、最终值和退化幅度均可审核；所有显式 Speed-First 目标下界在记录的可行性容差内满足。
- `no_harm_existing_customers`、`served_le_requested`、`online_IT_monotone`、`poi_flow_le_equipment`、`no_service_before_grid_or_byop`、`dc_energy_balance` 均检查通过；没有因 NULL/NaN 被误判 PASS。
- 8 母线 × 6 年共 48 个 `(site,year)` 记录均有效、唯一；负荷供电和延期不得伪造填充。
- `SCIENTIFIC_USE` 为有效的 `PARTIAL_PILOT` 类状态，而不是将 S0/S1 推断成 M2/M4 已验证。

**科学可靠性：**

- 显示 2026–2031 每年每个母线的 S0 `native`/`inherited` 未服务 MWh，及逐时最大 MW。
- **预设筛查阈值（研究验收代理、不是 ERCOT 规范）：**如果 S0 全期切负荷仍超过 **1,000 MWh**、任一母线峰值超过 **10 MW**、或 inherited-ramp 任一年切负荷超过 **1 MWh**，则标记 `S0_RELIABILITY_REVIEW_REQUIRED`，停止进一步科学结论并交研究者。低于这些阈值也须报告全部残余切负荷，不能直接声称精确为零。
- 特别对 Red Oak `p630 2` 输出 S0 切负荷峰值与累计值，同旧版的 965.7 MW / 32,808.6 MWh 全网总量对照。
- 报告 9 条 S0CAL Link 是否实际加载，特别是 AIDC 邻近四条的潮流利用率和对本地接网可用性的潜在影响。没有单因素归因时，只能称“可能限制/相关”，不能量化其因果贡献。
- 如果 S1 无延期，仍视为真实结果候选，检查 POI E0、程序日期、ERM 与上游瓶颈是否没有绑定；**不得**人为制造延期。

### 6.3 禁止自动推进

B2-R 结束或失败后均必须 **STOP**；不得自行重跑 ERM/S0CAL，改负 ERM，下调 POI，启动 B3 `pilot_core` 或 B4 `attribution`。

## 7. B2-R 最终交付包（必须同步 GitHub）

每一阶段至少提交：

| 文件 | 必需内容 |
|---|---|
| `STAGE_B2_F1F2_RERUN_REPORT.md` | 修复 SHA、B1 基准 SHA、运行参数、求解状态、失败对比、S0 可靠性、S1 延期主结果、是否准许进入 B3 的建议 |
| `STAGE_B2_F1F2_RERUN_AUDIT.json` | 求解状态、整数变量、模型规模、每层 lex 值、数值容差、负荷/能量平衡、no-harm、风险标志 |
| `STAGE_B2_48_BUS_YEAR_GRID_ONLY_F1F2.csv` | 48 键的 requested/served/delayed IT，含 POI 设备/时间、Firm 供电、经济 S0 的本地切负荷 |
| `STAGE_B2_S0_BACKGROUND_RELIABILITY_F1F2.csv` | 原生与继承切负荷，逐年总 MWh、快照峰值 MW、母线、旧版对照 |
| `STAGE_B2_S0_PUBLIC_EXPANSION_F1F2.csv` | 投资的发电/储能/输电容量、COD、资本/运行/切负荷账本，旧版对照 |
| `STAGE_B2_LEX_TOLERANCE_AUDIT.csv` | 每个 A1/A2 目标、各层与最终求解结果、最大违规、状态和实际设置 |
| `STAGE_B2_B1_INPUT_RECONCILIATION_F1F2.csv` | B1 ERM / S0CAL / baseline `.nc` 哈希、原 1,095.6 MW、B2 主线价格 |
| `STAGE_B2_F1F2_RETURN_MANIFEST.md` | 文件清单、缺失项原因、L2-only 大文件路径/哈希、最新 git SHA、停止状态 |

如某个输出在失败时无法生成，应创建 manifest 记录**确切缺失原因**，不能编造值或将空缺当 PASS。保留单独的场景检查点以便下一阶段继续审计。

## 8. 研究者决策点与异常处理矩阵

| 现象 | 执行方行动 | 是否可自行调参 |
|---|---|---|
| F1/F2 无求解器测试失败 | 提交失败日志与最小代码问题，暂停 | 仅修程序错误，无权求解 |
| 新 SHA 未批准 / gate 拒绝 | 停止，不运行任何 LP | 否 |
| S1 仍 INFEASIBLE | 保存状态，提出 IIS 最小诊断方案及所需授权 | 否；不可再放宽容差 |
| S1 optimal，但 Speed-First 分层目标明显退化 | 标记 `LEX_SCIENTIFIC_GATE_FAILED`，提交顺序 LP 备选设计 | 否；不得宣称 M1 结果可靠 |
| S0 仍有明显背景切负荷 | 按 §6.2 标记审查，拆分时空分布与公共扩张 | 否；不可再抬高 VOLL 逼零 |
| S0可靠、S1具备有效交付及延期结果 | 报告 M1 输入层机制，等待 B3 审核 | 否；不自动继续 |
| S1 没有明显延期 | 仍作为有效结果候选，核验瓶颈是否实际未绑定 | 否；不人为制造瓶颈 |

## 9. 执行方最终回报格式

```text
REPO: simonyed/BYOP
BRANCH: mainline-v13-stageA
FAILED_BASELINE_SHA: 951ddb8bd6bca575a78ecd3562c34e252c528f89
FIX_COMMIT_SHA: <执行方真实提交后填写>
APPROVED_SHA: <研究者明确批准后填写>
F1_TOLERANCE_CONSISTENCY: PASS / FAIL / NOT_TESTED
F2_MAINLINE_VOLL: 35685 USD/MWh (Brattle 2024 1h planning proxy)
BASELINE_SHA_MATCH: PASS / FAIL
B1_CALIBRATION_REUSED: YES / NO
SOLVER_EXECUTIONS_BEFORE_APPROVAL: 0
B2_R_STATUS: NOT_AUTHORIZED / OPTIMAL / FAILED / NOT_RUN
S0_BACKGROUND_SHED_MWh: <真实结果，未求解则 NOT_AVAILABLE>
S0_REDOAK_PEAK_SHED_MW: <真实结果，未求解则 NOT_AVAILABLE>
S1_LEX_STATUS: <真实结果，未求解则 NOT_AVAILABLE>
M1_VALIDITY: NOT_YET / PARTIAL_PILOT / BLOCKED
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_REVIEW
```

> **最终原则：**第一优先级是模型数值有效与已有负荷的真实可靠性；第二优先级是得到 S1 的 Grid-Only 供电延期。不要以 BYOP 后续必须更快、更便宜或延期必须非零，作为修改代码和物理参数的依据。任何新增修改均需审计、独立审批并可复现。
