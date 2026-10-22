# BYOP ERCOT — Stage B2.5 方法审计与 B3 探索性主线验证工作包 v1.0

**日期：**2026-10-21  
**代码仓库：**`https://github.com/simonyed/BYOP`  
**目标分支：**`mainline-v13-stageA`  
**本轮事实基线：**`3b044c1c038bf42946a6b445f157f08e5efa079c`（B2-R 求解与报告已提交）  
**已通过审计的 F1/F2 修复：**`4fb58a450f43bab2b23e354601ea2d6b88b50ae9`  
**执行原则：**机制验证优先；真实输入可追溯；连续 LP；不根据结果预期调参；先 B2.5 无求解器准备，**停止接受研究者审核新 SHA**，再单独授权 B3 探索性运行。

> **授权边界（非常重要）**：本工作包交付后，执行方可进行 **B2.5 的数据读取、审计、必要的结果后处理与仅输出性代码修改、无求解器测试、GitHub 提交**；**不得自行将 `run_authorization` 改为 `APPROVED`，不得进行任何求解器调用或 B3 计算**。B2.5 完成、提交新的代码 SHA 并通过研究者复核后，研究者另行明确批准 **B3 探索性 `pilot_core` 单次运行**。B3 后必须暂停，不得自动运行 B4、敏感性情景、IIS 或重校准。

---

## 0. 核心任务与禁止事项

本工作包分两个阶段，**不可跳过批准节点**。

| 阶段 | 核心目的 | 运行权限 | 必须产出 |
|---|---|---|---|
| **B2.5** | 查清并标记 2026 ERM 零裕度及 S0 剩余切负荷；修正科学使用状态的分类；建立成本分账；补充未来求解时的输出诊断 | **无求解器** | B2.5 审计报告、CSV、测试、修订 commit、预运行 manifest；**STOP** |
| **B3-E** | 在冻结的物理参数下完成 S0、S1、S3、S2_final、S3_mS2 的**探索性**联合机制验证 | 仅当研究者**单独批准新 SHA**时允许 | M1/M2/M4 结果、资产/服务/成本比较、风险标记、求解报告、GitHub 回传；**STOP** |

**本轮明确不做：**

- 不重新执行 `step0`、ERM-02 B 或 S0CAL，也不覆盖 B1 文件。
- 不修改 ERM 年度校准值（包括 2029–2031 负值）、S0CAL 的 9 条线路 / 1,095.6 MW、2025 基准网架、AIDC 数据、POI 审批类别及日期、风光潜力、燃气 MDQ、各技术成本与工期。
- 不把 `SHED_COST` / VOLL 从 35,685 USD/MWh 再向上调整以逼近零切负荷。
- 不降低 POI 容量、不减少负荷、不放宽 Firm 或 no-harm 条件来制造 BYOP 的加速优势。
- 不增加 MILP、离散模式枚举、全国规模、2050 延伸或额外情景组合。
- 不把 B2-R 的 `SCIENTIFIC_USE=BLOCKED` 静默覆盖成 `ALLOWED`。

**目标机制：**M1（BYOP 是否缩短实际可解释的延期），M2（BYOP 如何改变公共投资），M4（在**同服务量**下企业与社会协调决策的社会成本差异）。**M3 长期路径依赖目前只保存资产承诺与 COD 台账，不作长期定论。**

---

## 1. 已核实的 B2-R 基线：不得被新的工作包改写

数据来源：`current_work_pckg/STAGE_B2_F1F2_RERUN_REPORT.md`，以及 `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01_F1F2_V1/` 内全部已提交表格。**下表为 B2-R 已发生的结果，不是对 B3 的预测。**

| 检查项 | B2-R 实际结果 | 必须保留的解释边界 |
|---|---:|---|
| S0 / S1_EARLIEST | 均 optimal，0 整数变量 | 数值求解通过；不等于所有科学假设得到验证 |
| 逐年 Speed-First A1/A2 检查 | 47/47 行通过 | S1 的目标层级在最终解满足显式下界 |
| S1 总延期 | **312.7528 MW_IT·year** | 不能直接将全部解释为 ERCOT 真实并网延迟 |
| 2026 年延期 | **105.22 MW_IT·year**，当年全部八母线新增 AIDC 服务为零 | 与 **ERM-02 B 校准零新增容量裕度**直接相关，标记 `ERM_2026_METHOD_FLAG` |
| 2027–2028 年延期 | **约 207.53 MW_IT·year**（即总量扣除 2026） | 仅是**排除 2026 年份后的描述性统计**，不是反事实重新求解的真实 ERM 贡献分解 |
| 2029 年及以后 | 8 个研究母线均能满足申请量 | 不意味着所有基础负荷均无供电风险 |
| S0 背景切负荷 | **11,874.50 MWh**（原生 11,874.01；继承爬坡 0.494） | 超过原 B2-R 可靠性筛查阈值；不得删去 |
| S1 背景切负荷 | **9,896.74 MWh** | 相对 S0 更低；逐快照/逐机组 `no-harm` 检查通过 |
| 最大局部切负荷 | **76.17 MW**（Red Oak，2028） | 全网 2028 年仍有较明显的供电缺口 |
| B1 S0CAL | **9 条、1,095.6237 MW**，AIDC 邻近 4 条 665.8688 MW | 作为共同校准资产进入所有情景，不算新增公共投资 |
| VOLL | **35,685 USD/MWh** | Brattle 2024 ERCOT 1h 全系统 VOLL，被用于 3h 模型快照的规划代理；不是“3h 实测 VOLL” |
| 现有综合后处理 | `SCIENTIFIC_USE=BLOCKED: no_load_shed` | 不能简单删除布尔值；需区分科学风险与可求解/可比较资格 |

**重点核查 B2-R 的来源文件**：

- `STAGE_B2_F1F2_RERUN_REPORT.md`
- `STAGE_B2_48_BUS_YEAR_GRID_ONLY_F1F2.csv`
- `STAGE_B2_S0_BACKGROUND_RELIABILITY_F1F2.csv`
- `STAGE_B2_POI_NETWORK_DIAGNOSTICS_F1F2.csv`
- `STAGE_B2_F1F2_RERUN_AUDIT.json`
- `MAINLINE_SCENARIO_SUMMARY.csv`
- `MAINLINE_GATE_CHECKS.csv`
- `lex_S1_EARLIEST.json`、`lex_audit_S1_EARLIEST.csv`

**冻结输入 SHA-256：**

```text
baseline_2025_tamu_prepared.nc  19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb
B1 erm02_calibration.json      7d0c02f1245ebba31d26cb303cd154600e0a6626853d7d2c2910a1a268807a19
B1 S0_CALIBRATION.csv         30bf497ef009f3e120d43f7d6c2995fe0b7d82ffce9d1df2b5629131397454d5
```

上述哈希必须在执行服务器重新核对。不可从 GitHub 文件名推测本地 `.nc` 已经存在。

---

## 2. B2.5 — 方法审计、后处理修订与准备（严格无求解器）

### B2.5-A：2026 年 ERM 零新增裕度审计

**研究判断：**原 `ERM-02 B` 在禁止新增资源的条件下，求出给定既有/承诺资源可达到的裕度，再将此值作为研究情景的最低 ERM 门槛。2026 年阈值约 **8.196%**，S0/S1 ERM 约束均 binding，并使 2026 年新增研究 AIDC 全部无法取得 Firm 服务。该值属于**模型内部校准代理**，尚未验证为 ERCOT 现实中的 2026 年并网容量界限。

执行内容：

1. 直接读取 B1 ERM JSON、B2-R 的 `duals.csv`、`lex_S1_EARLIEST.json`、`STAGE_B2_48_BUS_YEAR_GRID_ONLY_F1F2.csv`、`S1_GRID_OFFER.csv`；核对 2026 年各母线申请量、服务量、预批设备容量、POI / `serve_cap` 对偶及 ERM binding 状态。
2. 将全部延期列出两个**并列口径**：`total_delay_MW_IT_year=312.7528`、`post_2026_delay_MW_IT_year≈207.53`，同时列出 `method_flagged_2026_delay_MW_IT_year≈105.22`。注明后两者只作分年度描述，**不是**经过 ERM 反事实放松后算出的单因素因果贡献。
3. 不得把 2026 年的零服务量归因于 POI：对于当年有已批准设备容量的母线，应显示 ERCOT 容量代理可能是首要约束；对于 POI=0 的母线，允许存在多重约束，绝不能声称唯一原因。
4. 单独标注 2026 年 ERM 的研究影响：它可能影响 S1 价格、S2 企业自供选择与后期投资；即便 S2 最早 BYOP COD 晚于 2026，也不等于异常对多期动态结果完全无影响。
5. 不能通过在模型外从 S2 结果中“减掉 2026 年”来形成所谓修复后的反事实。若将来需要真正评估 2026 ERM 假设，应单独批准具有物理依据的 alternative-case，本轮不得求解。

**建议新输出：**`STAGE_B25_ERM_2026_METHOD_AUDIT.csv`，含 `year,site,requested_IT_MW,served_IT_MW,delay_IT_MW,E0_MW,ERM_binding,ERM_shadow_price,POI_binding,procedure_ready,method_flag,source,interpretation_limit`；如无法将全局 ERM 对偶可靠分解到母线，保留全局数值并说明不可分解，不作伪造。

### B2.5-B：S0 非零背景切负荷及 no-harm 审计

当前 S0 切负荷集中在 2027–2028 年，主要发生在 `p630 13`（约 6,969 MWh）、`p630 14`（约 1,750）、`p600 1`（约 1,621），Red Oak `p630 2` 原生负荷约 417 MWh。2025 继承的存量 AIDC 爬坡负荷合计切除仅 **0.494 MWh**。

执行内容：

1. 直接从 `S0_shed_by_snapshot_frozen.csv.gz`、`shed_by_bus_S0.csv`、`shed_by_bus_S1_EARLIEST.csv`、已保存的 scenario summaries 构造**母线 × 年度 × 原生/继承负荷**的切负荷台账；保留逐快照加权方法、权重单位、最大瞬时 MW，不将 MWh 与 MW 混用。
2. 确认旧 B2-R `no_harm_existing_customers` 为 true，最大违反量为约 `0.001 MW`（容许余量边缘）；按已有约束核对，而不是只根据 S1 全网切负荷更低就宣布逐点 no-harm 一定成立。
3. 计算 S0 和 S1 的背景切负荷差额（总量 S1−S0 约 **−1,977.76 MWh**）；说明此差值是**结果比较**，不是“BYOP 的改善”，因为 B2-R 还没有 S2。
4. 标记 `S0_RELIABILITY_REVIEW_REQUIRED`，沿用 B2-R 原筛查标准：**S0 六年总切负荷 >1,000 MWh、任一母线峰值 >10 MW 或继承爬坡任年 >1 MWh 则触发**。保留每项的实际 PASS/FAIL，不能因机制可继续分析而将其改写为 PASS。
5. 根据已有快照做 2028 年 Red Oak 与 `p630 13/14` 的时段重合表。**如果尚无线路潮流快照或 S1 逐快照切负荷，就标 `DATA_NOT_SAVED`，不能反推出上游拥堵比例。**

**建议新输出：**`STAGE_B25_S0_S1_SHED_EXPOSURE.csv`、`STAGE_B25_RELIABILITY_FLAGS.csv`。应包含源文件和不能直接观察的量。

### B2.5-C：成本账本必须拆分，不得误称“真实资源成本”

目前 `scenario_summary.csv` 中的 `social_real_resource_cost_USD` **实际包含 `load_shed_PV_USD`**；其字面名称容易误导读者将停电福利损失当成发电、储能、输电等实物资源投入。B3 的 M4 尤其必须避免这一点。

**建议仅新增派生汇总（不修改历史原列定义、不重算 S0/S1 优化目标）：**

```text
physical_resource_spending_proxy_PV_USD
    = social_real_resource_cost_USD - load_shed_PV_USD
existing_customer_unserved_loss_PV_USD
    = load_shed_PV_USD
social_welfare_cost_before_dc_delay_PV_USD
    = physical_resource_spending_proxy_PV_USD + existing_customer_unserved_loss_PV_USD
```

还应单列 `social_delay_loss_PV_USD`、`curtailment_loss_PV_USD`、`interruption_loss_PV_USD`、`social_total_USD`，以及真实费用与企业内部购电支付的**转移**项。对运营成本中燃料、可变运维是否已计入 BYOP 燃料，必须用现有账本恒等式核对，**避免二次加总**。

- `physical_resource_spending_proxy` 只能称为“按现有账本剔除 VOLL 后的资源支出代理”，若源代码中仍包含其他转移/损害项，应标注并进一步逐项拆开；不能未经核实直接改名为 `true_resource_cost`。
- S2_final 与 S3_mS2 允许分别展示 **资源支出差**、**既有用户停电损失差**、**计算服务损失差**和**社会总差**。对同服务量的判定只控制 IT 交付轨迹，不等于全部计算任务或供电可靠性结果完全一致。
- 不能把不同 VOLL 假设下的 S0 目标值变化称作资源节省；本 B3 保持一致的 35,685。

**建议新输出：**`STAGE_B25_COST_BOOK_DECOMPOSITION.csv` 与对应的合成单元测试。B2.5 可以只写出 S0/S1 两行；B3 求解后把 S2_final/S3/S3_mS2 添入同一结构。

### B2.5-D：重新设计科学使用状态，**不改变硬性失败事实**

当前 `workflow/byop/post/collect_mainline.py` 的 `required` 列表本身不要求 `no_load_shed`，但其后会把**任何额外的布尔 False**（包括 `no_load_shed=False`）计入 `failed`，最终把整个 B2-R 标为 `SCIENTIFIC_USE=BLOCKED: no_load_shed`。

**只修改后处理分类，不允许绕过真正的物理/数值失败。**建议保留：

1. **原始求解/校验字段**：`no_load_shed=False`、`no_harm_existing_customers=True`、`lex_presolve_optimal=True`、S2 收敛、48 键 matched-service 等原样呈现，完整保留历史文件，不就地改写。
2. **`TECHNICAL_GATE`**：要求当前阶段所有已请求情景 optimal、0 整数、相关物理/守恒/no-harm 约束、Speed-First A1/A2、S2 真实交付收敛（CORE 时）、48 键 matched service（CORE 时）等。缺失必需项必须 FAIL，不能以 `None` 视为通过。
3. **`METHOD_FLAGS`**：分别列出 `ERM_2026_METHOD_FLAG`、`S0_RELIABILITY_REVIEW_REQUIRED`、`S0CAL_LINE_FLOWS_PENDING_DIAGNOSTIC_EXPORT`。已完成导出时更新最后一项，但不改变其它两项事实。
4. **`EXPLORATORY_USE`**：当技术门控合格且不存在未解释的严重数据错误时，可以记 `PERMITTED_WITH_METHOD_FLAGS`，仅表示**可以审阅 M1/M2/M4 机制候选结果**；不是正式发表许可。
5. **`FINAL_SCIENTIFIC_USE`**：在 2026 ERM 与 S0 可靠性假设尚未独立验证/开展必要稳健性测试前，保持 `PENDING_METHOD_VALIDATION` 或 `NOT_YET_APPROVED`。不能把 `EXPLORATORY_USE` 复制成无保留 `ALLOWED`。
6. 为兼容现有下游工具，**保留 `SCIENTIFIC_USE` 旧列或给出显式映射**，并新增上述独立状态。禁止静默改变旧列语义或清除 `no_load_shed` 的原始 FAIL。

**验收**：合成测试包括「S0 非零 shed + no-harm PASS」应为探索性可分析、最终仍有方法学标记；「任何 LP infeasible」、「no-harm FAIL」、「48 键缺失」、「S2 不收敛」必须仍 BLOCKED；「字段缺失」不得自动 PASS。B2 阶段尚无 S2 / M4，则这些 CORE-only 字段应为 NOT_APPLICABLE，而不是伪造 PASS。

### B2.5-E：只增加求解**结果导出**，不改变物理模型

当前 B2-R 没保存 4 条 AIDC 邻近 S0CAL 线路实际流量，因此不能审计校准是否过度提供上游可送达能力。为使**后续 B3 的同一次求解**充分利用数据，允许新增最小输出性代码（不改变约束、目标、变量、参数、求解顺序）：

- 在场景 `go()` 的优化成功后，从 `n.links_t.p0` 保存 9 条固定 `AC_s0cal` 校准通道的双向流；重点是 `TL73`、`TL63`、`TL3`、`TL26`（实际资产名形如 `S0CAL_TL73_fwd/rev`）。
- 对每一场景、年份、线路输出 `calibrated_MW`、最大正反向潮流（MW）、`max(|flow_direction|)/calibrated_MW`、加权年内满载时数或满载快照占比、关联 AIDC 母线、snapshot/weight 口径。注意这是一对**平行可控 Link**，不得混同于原 AC `Line` 的电气潮流，也不得双向相加成虚假的净容量。
- 如可低成本导出 2028 年 `p630 2/13/14` 及对应原网络线路潮流，则额外生成 **仅诊断性** 快照表；但不得要求重跑旧 B2-R 来填补缺失。
- 输出宜落在独立 `scenarios/<scenario>/` 下或总目录的 `STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv`；完整逐快照表可以压缩存储，报告只需统计摘要与文件哈希。
- 保存 S0/S1 原生及继承切负荷快照指标的结果（如已有则复用），以便 B3 直接对照，无需重复事后推断。
- **如该纯导出改动显著增加内存/磁盘或侵入主求解逻辑，应只做轻量摘要，记录放弃原因，不据此阻止 B3 的核心求解。**

### B2.5-F：运行入口、测试及提交

执行方可对 `workflow/byop/run/run_mainline.sh` 作一个极小修改：新增**专用** `pilot_core_b3e`（或等价清楚命名的入口），例如：

```bash
# 只示意 case-id 和情景集合；实际复用仓库已有 COMMON/CAL/gate 及权限检查
pilot_core_b3e) run MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1 \
  $CAL --scenarios S0 S1_EARLIEST S3 S2 S3_mS2 ;;
```

- 必须独立新 case 目录，不能复用 `…_PILOT_S01_F1F2_V1` 或原 `…_PILOT_CORE`；当目标目录已有**任何非预期部分运行数据**时应停止人工核对，不得凭“还没有 case_manifest”就直接覆盖。
- 必须排除 `--attribution`、`step0`、`S1E_xPOI/UP/RA/PROC/ALL` 及其它未批准情景。
- 允许 `DRY=1` 无求解器命令核对；不得作为实际求解授权。
- 代码里原有配置 `mainline.stage` 的旧 `STAGE_A_IMPLEMENTATION_ONLY` 标签可做**非行为性**文档纠正，但不应以此为理由重构配置系统。
- 更新 `MAINLINE_V13_PRE_RUN_MANIFEST.json` 的**全部实际修改文件哈希**，特别是 `workflow/byop/post/collect_mainline.py`、`stage_b2_tables.py`（如果修改）、`rearch_mech.py`（若加导出）、`run_mainline.sh`、测试和配置。确认 `.nc`、ERM、S0CAL 输入 SHA 未变。
- 保留当前门控为 `NOT_APPROVED`，批准 SHA 为 null；验证 gate 必须 `approved: false`，无求解器测试至少覆盖输出口径、科学状态、算例目录保护、LP-only 和输入不变。

**B2.5 完成必须停止并向研究者交付：**

- `current_work_pckg/STAGE_B25_METHOD_AUDIT_REPORT.md`（事实、推断、局限、处理方式与 B3 运行建议）
- `current_work_pckg/STAGE_B25_CODE_AND_GATE_AUDIT.md`（修改的文件/函数、测试计数、无 solver、最新代码 SHA）
- `current_work_pckg/STAGE_B25_RETURN_MANIFEST.md`
- B2.5 新输出的四类 CSV、测试日志、gate 与 DRY 输出；必要时更新预运行 manifest。
- **必须回报 `RUN_AUTHORIZATION=NOT_APPROVED` 和 `SOLVER_EXECUTIONS_B25=0`，不得自称已批准 B3。**

---

## 3. Stage B3-E — 探索性核心情景计算（必须获得新 SHA 的单独授权）

### 3.1 前置批准与严格版本对账

仅在研究者审核 B2.5 报告、明确给出批准的 **B2.5 修订代码完整 SHA** 和执行范围后，允许执行方在运行配置中写入 `APPROVED`、`approved_git_sha`、`approved_by` 并提交授权记录。

建议在 L2 服务器执行的**示意命令**（仅获批后）：

```bash
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow

git rev-parse HEAD
bash byop/run/run_mainline.sh gate
DRY=1 bash byop/run/run_mainline.sh pilot_core_b3e

# 检查 approved: true、case-id、原 ERM/S0CAL 文件与输入哈希、无 attribution 后才可启动：
THREADS=20 bash byop/run/run_mainline.sh pilot_core_b3e
```

**求解授权必须显式覆盖 S0、S1_EARLIEST、S3、统一开发商 S2（有限轮公开电网复核）、S3_mS2；不包含 B4。** 若 L2 资源不足或任务正在运行，先停止新的启动，不抢占其它计算。批准仅适用于审核后的代码/输入状态；任何新行为性代码变动必须重新审批。

### 3.2 B3 的优化情景与结果边界

按现有 `rearch_mech.py` 调用顺序：

1. **S0**：不含研究新增 AIDC 的正式经济电网基准，重新输出 S0 背景切负荷及公共投资；注意相同输入重求解应与 B2-R 一致到可解释的数值误差。
2. **S1_EARLIEST**：统一严格 Grid-Only Speed-First 与公共系统最小成本，验证 2026 方法性 ERM 结果、2027–2028 延期和全部 47 行字典序检验。
3. **S3**：社会协调自由选择服务量及 BYOP/公共投资，保留实际服务量差异。
4. **S2**：一个覆盖全部 8 母线的开发商连续 LP，按最早投运再私人成本选择电源和合同；公共电网复核至给定迭代上限。最后一轮的正式标签为 **`S2_final`**；原始 `S2`/`S2_itN` 仅供诊断。
5. **S3_mS2**：在与 `S2_final` 相同的逐母线逐年度 IT 服务量约束下由社会协调重新优化，供 M4 matched-service 比较。

**不把 `S2_final` 当成另一条需要额外求解的情景**。没有复用资产资格、SOFC fast slot 或其他选项时，按原输入忠实给出结果，不为增加 BYOP 丰富性自行开放。

### 3.3 M1：供电速度与技术方案

至少检查：

- 8 母线 × 6 年的 `requested_IT_MW` / `served_IT_MW` / `delay_IT_MW`，包括 S1、S2_final、S3 和 S3_mS2。
- 每年累计在线 IT、六年 `delay_MW_IT_year`，S2_final−S1 的提速/延期减少量；对 2026 年**单独标记 ERM 方法性限制**，并另给 2027–2028 结果视图。
- S2 每母线 GO_F/GO_C/GF/IS（均为解后供电模式标签，不是 LP 的整数模式）、Firm/Conditional 容量权利、使用电量、自备电源技术/容量/建设批准年份/COD/发电量，以及未服务原因。
- 首期 BYOP 可投运日期与 2026 零 ERM headroom 的关系：不得称“2026 年 BYOP 未能提速”证明 BYOP 无价值，若大多数技术最早 2028 年 COD，应按年份分析。
- 若 S2 的服务量并未改善或甚至延迟更多，先检查报价、权利、工期、运营成本、可靠容量信用及 LP 目标；**不许仅因结果违背假说而调整参数。**

### 3.4 M2：公共电网扩张反馈

按 S0、S1_EARLIEST、S2_final、S3、S3_mS2 分别输出：

- 公共风电、光伏、CCGT/OCGT、储能、输电扩张与 POI 升级；按**技术 × 母线/走廊 × 年度投运**汇总，容量单位 MW、能源单位 MWh、成本单位 PV USD。
- S1−S0：新增 AIDC 的公共投资效应；S2_final−S1：开发商 BYOP 带来的公共系统投资反馈；S3_mS2−S2_final：同服务量协调调整。
- 区分 S0CAL 共用固定 Link（9 条，1,095.6 MW；**不是 S0/S1/S2 新投资**）、真实公共新建资产与数据中心自有 BYOP 资产，避免重复计数。
- 对提前/延期/替代/重复建设只在 **2026–2031** 观察窗内给出证据；目前不声称 2040/2050 年搁浅或路径依赖结论。

### 3.5 M4：社会成本及同服务量严格核验

最低质量要求：

1. `S2_final` 与 `S3_mS2` 的 **48 个唯一 site–year 键**必须完全相同，缺失/重复均 FAIL；每个键 `|served_IT_MW_gap| <= 0.5 MW IT`。
2. `S2_final` 必须与最终**公共电网实际交付**的开发商计划一致，`s2_converged=true`。不收敛时，不允许把成本差当作正式 M4；保留诊断并 STOP。
3. 严格比较 `physical_resource_spending_proxy_PV_USD`、`load_shed_PV_USD`、延迟损失、中断/削减损失以及社会总成本；**旧 `social_real_resource_cost_USD` 由于包含 VOLL 不得单独宣称为纯资源支出**。
4. 企业支付给电网的费用、税抵免/补贴等**转移支付**，不得与真实资源成本相加形成社会成本；检查账本恒等式。
5. S3 自由服务量与 S2 不同时，不得仅依据二者的总投资或总成本判定“私人效率偏离”；正式效率对比主要使用 `S2_final` vs `S3_mS2`。
6. 即便 matched-service 有效、成本差为 0 或为负，也必须按实际求解报告，不预设企业自主 BYOP 必然产生效率损失。

### 3.6 B3 质量门控与自动停止规则

| 类型 | 必须验证 | 处置 |
|---|---|---|
| **硬性有效性** | 5 个正式标签存在；各求解 optimal；整数/二进制变量 0；能量平衡、BESS SOC、燃气 MDQ、POI 设备/合同、压力快照、在线 IT 单调、no-harm、S1 Speed-First 均满足 | 任一失败 → `B3_BLOCKED_TECHNICAL`，不编写正式 M1/M2/M4 结论；不启动其它情景 |
| **S2 交付** | 选定迭代实际与开发商计划一致；最终 S2 结果无迭代错配；`s2_converged` 明确 TRUE | 失败或缺失 → `B3_BLOCKED_S2`；报告缺口和各轮情况，禁止宣称 M4 |
| **M4 匹配** | S2_final / S3_mS2 严格 48 键、无 NaN、最大服务差 <=0.5 MW IT，成本账本可对账 | 失败 → `B3_M4_INVALID`，仅发布诊断性数据 |
| **背景可靠性** | S0 非零切负荷完整列明、S1/S2/S3 no-harm；继承爬坡单列；2028 Red Oak 及周边状况审计 | 若 no-harm FAIL → 硬停止；若仅 S0 非零且 no-harm PASS → **保留 `S0_RELIABILITY_REVIEW_REQUIRED`，可做探索性比较，不得宣布最终科学验证完成** |
| **首年 ERM 方法风险** | 2026 服务与 ERM 对偶/约束状况、2027–2028 独立统计；禁止把 2026 binding 解释成实际 ERCOT 并网资格 | 保留 `ERM_2026_METHOD_FLAG`；探索性结论必须附条件，未来决定是否需要真实反事实敏感性 |
| **范围** | 不执行 B4 / 归因 / 全年 / 全国 / 2050 | 任何越权应立即停止并记录 |

**科学使用分层结果：**

- `TECHNICAL_GATE=PASS` 只说明模型在规定物理检查下有效。
- `EXPLORATORY_USE=PERMITTED_WITH_METHOD_FLAGS` 仅允许分析当前候选机制。
- `FINAL_SCIENTIFIC_USE=PENDING_METHOD_VALIDATION`，直到 ERM/S0 相关独立验证或敏感性工作另获批准后再裁决。
- 不能为了使 `SCIENTIFIC_USE=ALLOWED` 而删掉 `no_load_shed=False`；原始布尔字段与方法风险必须保持可见。

### 3.7 B3 计算完成后必须暂停

无论出现 BYOP 提速、没有提速、S2 与 S3 完全相同、求解器失败、S0 再现非零 shed，**都必须终止于 B3-E 并回报**。禁止自动开始 B4、修改 ERM/POI/VOLL、做 IIS、增加技术、扩大样本或覆盖历史结果。

---

## 4. 必需结果文件与 GitHub 交付清单

### 4.1 B2.5（第一批，无求解器）

放在版本明确的 `current_work_pckg/` 或 `workflow/results/BYOP/mainline/<B25_AUDIT_DIR>/`，不得覆盖 `B2-R` 已发布原表：

- `STAGE_B25_METHOD_AUDIT_REPORT.md`
- `STAGE_B25_ERM_2026_METHOD_AUDIT.csv`
- `STAGE_B25_S0_S1_SHED_EXPOSURE.csv`
- `STAGE_B25_RELIABILITY_FLAGS.csv`
- `STAGE_B25_COST_BOOK_DECOMPOSITION.csv`
- `STAGE_B25_CODE_AND_GATE_AUDIT.md`
- `STAGE_B25_RETURN_MANIFEST.md`
- `MAINLINE_V13_PRE_RUN_MANIFEST.json`（如有行为性/后处理性代码修订，更新全部相关哈希）
- 无求解器单元/结构测试、门控拒绝及 DRY 模拟命令日志。

`STAGE_B25_CODE_AND_GATE_AUDIT.md` 必须说明每个代码变更文件与函数、SHA、是否触及约束/目标/变量，以及 `SOLVER_EXECUTIONS=0` 证据。B2.5 返回时执行方**只能请求授权**，不得把“研究者之前说可以有条件进入 B3”视为直接求解许可。

### 4.2 B3-E（第二批，单独批准且运行后）

须保留现有 `collect_mainline.py` 的正式表：

- `MAINLINE_SCENARIO_SUMMARY.csv`
- `MAINLINE_BUS_DELIVERY_AND_DELAY.csv`
- `MAINLINE_S2_MODES_TECH.csv`
- `MAINLINE_PUBLIC_INVESTMENT_DELTA.csv`
- `MAINLINE_ASSET_COMMITMENT_LEDGER.csv`
- `MAINLINE_MATCHED_SERVICE_COST.csv`
- `MAINLINE_GATE_CHECKS.csv`、`MAINLINE_CASE_MANIFEST.json`
- `S1_GRID_OFFER.csv`、`S2_developer_modes.csv`、`S2_consistency.csv`、`S2_SELECTION.json`（如位于 `scenarios/S2_final/`，写明路径）
- `lex_S1_EARLIEST.json`、`lex_audit_S1_EARLIEST.csv`

此外新增/更新以下面向论文机制的表：

- `STAGE_B3_M1_SPEED_DELIVERY_BY_SITE_YEAR.csv`（含 2026 方法性标记）
- `STAGE_B3_M2_PUBLIC_EXPANSION_BY_CARRIER_YEAR.csv`
- `STAGE_B3_M2_ASSET_COMMITMENT_AND_COD.csv`
- `STAGE_B3_M4_COST_COMPONENTS.csv`（不把 VOLL 当作实物资源开支）
- `STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv`（如有求解后流量；无则明确标 PENDING）
- `STAGE_B3_CHECKS_AND_METHOD_FLAGS.csv`
- `STAGE_B3_EXPLORATORY_AUDIT.json`（调用记录、求解状态、时间、代码和输入哈希、S2 最终轮次、关键门控）
- `current_work_pckg/STAGE_B3_EXPLORATORY_RESULTS_REPORT.md`
- `current_work_pckg/STAGE_B3_RETURN_MANIFEST.md`

**B3 报告至少应回答四个具体问题：**

1. **B2-R 的 312.75 MW·year Grid-Only 延期在 B3 内能否重现？S2_final 对其中哪几座场址、哪几年提前投运？**
2. **开发商真正选择了哪些 BYOP 技术、容量和 COD？是否符合批准/施工/燃气及压力日限制？**
3. **这些选择改变了哪些公共发电、储能、输电及 POI 投资，相对 S1 和 S0 的差异是否有明确的资产台账依据？**
4. **在 48 键服务量配对后，S2_final 与 S3_mS2 在实物资源支出、背景停电损失及社会总成本上分别相差多少？**

任何不存在、损坏、过大或被 `.gitignore` 屏蔽的 L2 原始文件，应在 return manifest 中写明**准确服务器路径、大小、SHA-256 与 GitHub 可见的摘要文件**。没有结果不能填 0，必须注明 `NOT_AVAILABLE` 或 `NOT_RUN`。

---

## 5. 失败与异常时的处理原则

| 发现 | 允许执行方立即做的事 | 不允许的事 |
|---|---|---|
| B2.5 原始表格无法对账 | 停止代码准备、列出冲突来源和差额，交研究者 | 用猜测补齐缺项或改写旧结果 |
| 原始 2026 ERM binding 的判断与对偶不一致 | 先检查约束标签、单位、取值容差及年度索引；报告“证据不充分” | 任意改 ERM 系数或宣称因果归因 |
| B3 S0 切负荷仍高 | 如实标记，核查 S1/S2 no-harm 与时空重合；分列福利损失 | 提高 VOLL 或免费增容强行清零 |
| B3 S1 或 S2 LP infeasible | 保存 status、参数、诊断、最后成功场景检查点并 STOP | 自动跑 IIS、放宽 no-harm、忽略 infeasible |
| S2 不收敛 | 输出各轮 public-served 与计划差、合同权利、设备/工期/压力条件并 STOP | 直接将最后一轮命名为有效私人最优 |
| S3_mS2 与 S2_final 服务量不一致 | 标为 `M4_INVALID`、检查引用的 S2 最终轮次与 48 键 | 硬把不匹配成本差解释为社会效率 |
| B3 BYOP 不提速或成本差为零 | 按实际结果分析经济/物理原因 | 为获得期望机制调整工期、降 BYOP 成本或添加虚拟容量 |
| B3 的模型规模和内存过高 | 记录求解资源、提供减负建议，停止 | 未批准就更改时间采样、核心约束或求解方法 |

---

## 6. 两阶段向研究者回报的固定格式

### B2.5 回报（无需执行求解器）

```text
REPO: simonyed/BYOP
BRANCH: mainline-v13-stageA
B2_R_BASELINE_SHA: 3b044c1c038bf42946a6b445f157f08e5efa079c
B25_CODE_FIX_SHA: <实际完整 SHA>
B25_RUN_AUTHORIZATION: NOT_APPROVED
B25_SOLVER_EXECUTIONS: 0
B25_INPUT_HASHES_UNCHANGED: PASS / FAIL
ERM_2026_METHOD_FLAG: ON (105.22 MW_IT-year, descriptive)
S0_RELIABILITY_REVIEW_REQUIRED: ON (11874.50 MWh)
B2_R_NO_HARM: PASS / FAIL / UNVERIFIED
COST_DECOMPOSITION_CHECK: PASS / FAIL
SCIENCE_GATE_TESTS: <通过数量>/<总数>
DRY_B3_SCENARIOS: S0 S1_EARLIEST S3 S2 S3_mS2
B3_RUN_STATUS: NOT_AUTHORIZED
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_SHA_APPROVAL
```

### B3 回报（只有在研究者单独批准后）

```text
B3_APPROVED_CODE_SHA: <完整 SHA>
B3_EXECUTION_GIT_HEAD: <完整 SHA>
B3_GATE: APPROVED / REFUSED
B3_CASE_ID: MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1
B3_SCENARIOS_COMPLETED: <真实标签>
B3_LP_INTEGER_VARIABLES: 0 / nonzero
B3_SOLVER_STATUS_BY_SCENARIO: <每情景的真实结果>
B3_S1_DELAY_MW_IT_YEAR: <数值 / NOT_AVAILABLE>
B3_S2_FINAL_DELAY_MW_IT_YEAR: <数值 / NOT_AVAILABLE>
B3_S2_FINAL_SELECTED_ITERATION: <整数 / NOT_AVAILABLE>
B3_S2_PUBLIC_CONVERGED: TRUE / FALSE / NOT_AVAILABLE
B3_M2_PUBLIC_DELTA: <见对应 CSV>
B3_M4_48_KEYS_MATCHED: PASS / FAIL / NOT_AVAILABLE
B3_M4_COST_COMPONENTS_VALID: PASS / FAIL / NOT_AVAILABLE
B3_ERM_2026_METHOD_FLAG: ON / REVISED_BY_EVIDENCE
B3_S0_RELIABILITY_FLAG: ON / OFF (with threshold and real values)
B3_TECHNICAL_GATE: PASS / FAIL
B3_EXPLORATORY_USE: PERMITTED_WITH_METHOD_FLAGS / BLOCKED
B3_FINAL_SCIENTIFIC_USE: PENDING_METHOD_VALIDATION / BLOCKED
B4_EXECUTIONS: 0
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_RESULTS_AUDIT
```

**最终执行原则：**我们当前需要的是一个能回答 M1/M2/M4 的探索性 ERCOT 联合求解，而不是反复把 S0 和 2026 ERM 校准成“理想无风险电网”。然而，这不代表允许以探索性通过掩盖任何真正的求解失败、物理违反、项目资格不足或成本账本错误。保留方法学警告、进行严格结果对账，然后根据 B3 的真实发现决定是否值得做首年 ERM 反事实与背景可靠性敏感性，是当前最合适的推进顺序。
