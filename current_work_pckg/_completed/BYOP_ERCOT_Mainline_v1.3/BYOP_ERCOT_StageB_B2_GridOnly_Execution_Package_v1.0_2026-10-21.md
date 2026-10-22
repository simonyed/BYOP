# BYOP ERCOT Mainline v1.3 — Stage B2 Grid-Only 首轮执行与独立审计工作包

**版本：** B2-WP v1.0  
**日期：** 2026-10-21  
**接收方：** Codex / Claude / L2 执行方  
**执行基线：** [`simonyed/BYOP`](https://github.com/simonyed/BYOP)，分支 `mainline-v13-stageA`；B1 完成提交 `af00b32a7699344fd64b4129e02957dc3aeb4486`  
**上游依据：** `current_work_pckg/STAGE_B1_CALIBRATION_REPORT.md`、`STAGE_B_PRE_RUN_AUDIT.md`、`BYOP_ERCOT_StageB_Pilot_Execution_Work_Package_v1.0_2026-10-21.md` 和《论文顶层设计.md》。

## 0. 给执行方的唯一指令

**接受 B1 的现有 ERM 及 S0 输电校准结果作为 B2 首轮的“冻结基线”，不做新的参数修正；按既有 `pilot_s01` 入口求解 S0 与 S1_EARLIEST，审查真实求解后的服务延期及其物理可解释性。完成后上传详尽报告和必要数据，并在 B2 停止，等待研究者判断是否进入 B3。**

本文件用于指导 **B2**，并不批准 S2/S3、B3 `pilot_core`、B4 `attribution` 或 `run` 全情景。**此前配置里的批准说明仅覆盖 B1 `step0`，不能因为门控程序技术上仍可通过，就视为已自动授权 B2。** 执行前需获得并记录研究者对当前 SHA、输入以及 B2 `pilot_s01` 的明确批准；研究者连同本文件明确下达“执行 B2”也可以作为批准记录。未经这一授权只允许进行无求解器检查。

## 1. 本阶段真正要回答的问题

B2 是论文机制 **M1（Grid-Only 的物理/程序延期基线）**的第一轮求解验证，不要求提前出现某种结果；M2（BYOP 对公共扩张的反馈）和 M4（企业—社会同服务量比较）属于 B3，不在此轮得出结论。

- 在共同电网 G-REAL、真实 Epoch AI 八个 TAMU 母线及 2026–2031 年新增需求下，**不采用 BYOP** 时，Grid-Only 能按要求投运多少 IT MW？哪些母线/年份存在服务延期？
- POI 设备取得与升级 COD、程序资格、上游网络可送达能力、资源充裕度约束在数学模型里是否真实作用于供电？不能把“存在约束”直接等同于“该约束已经导致延期”。
- B1 的共同校准资产会否过度提高 AIDC 附近的可送达能力？如果可能，记录证据，**先报告，暂不改网络**。
- 最终产生可以决定是否进入 B3 的可靠基准，以及针对实际瓶颈的下一步最小行动建议。

正式对象：`p600 0`（Helios）、`p610 2`（Abilene）、`p630 2`（Red Oak）、`p630 4`（Shackelford）、`p630 5`（Temple）、`p630 6`（Midlothian）、`p630 9`（Denton）、`p650 0`（TX1/SAT14）；2026–2031 共 **8 × 6 = 48 个母线—年份键**。正常零需求或尚未投运的年份也要保留键并注明状态。

## 2. B1 已确认结果：保留而不在 B2 前调参

### 2.1 B1 求解状态和基准文件

- ERM-02 B：`optimal`；S0 最小增容校准：`optimal`，均纯 LP。
- S0 最小增容校准背景切负荷近零（原生 `5.2×10⁻¹⁰` MWh、继承爬坡 `2.0×10⁻¹¹` MWh）。**这是高切负荷惩罚的“校准运行”结果，不等于正常经济目标下 B2 重新求解的 S0 也必然零切负荷。** B2 必须重新核验。
- 输电修正：9 条 TAMU 线路共 `1,095.6237013311218 MW`，经 `S0_CALIBRATION.csv` 作为所有情景共用、固定、零新增成本的**合成网络基准修正**；不是 AIDC 诱发的公共投资。
- B1 基准 `.nc` 文件 SHA-256：`19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb`。
- B1 ERM JSON SHA-256：`7d0c02f1245ebba31d26cb303cd154600e0a6626853d7d2c2910a1a268807a19`。
- B1 S0 校准 CSV SHA-256：`30bf497ef009f3e120d43f7d6c2995fe0b7d82ffce9d1df2b5629131397454d5`。

### 2.2 本阶段冻结的年度 ERM 校准值

| 年份 | 2026 | 2027 | 2028 | 2029 | 2030 | 2031 |
|---|---:|---:|---:|---:|---:|---:|
| `erm_margin` | 0.081961869 | 0.052523235 | 0.025608607 | −0.005940221 | −0.019528522 | −0.041745156 |

**方法学说明：** ERM 校准基于冻结现有与已承诺机组、禁止新建的反事实，六年共发生约 1,394,106 MWh 切负荷。它不是 ERCOT 官方可靠性标准；2029–2031 为负，若直接进入可扩张情景，资源充裕度的 Firm 要求可能偏宽松。**B2 主线先原样使用并透明标记。** 不设为 0%、不改成统一 15%、也不直接据此宣称 RA 约束一定无效。若真实结果指向这一问题，再提出有依据的 `max(0, calibrated_margin)` 对照，并作为**另立分支/新案例**的敏感性，不覆盖 B1 原始 JSON。

### 2.3 特别关注的 AIDC 相邻校准增容

| 线路 | 母线 | B1 增容 MW | 原线路 MVA | 审计重点 |
|---|---|---:|---:|---|
| TL73 | `p630 2`–`p630 5` | 259.7247 | 1,112.2 | Red Oak–Temple |
| TL63 | `p630 12`–`p630 2` | 228.0960 | 552.1 | Red Oak |
| TL3 | `p600 0`–`p600 1` | 147.2610 | 203.0 | Helios |
| TL26 | `p610 1`–`p610 2` | 30.7871 | 145.4 | Abilene |
| **合计** | 4 条 | **665.8688** | — | 约占校准增容 60.8% |

上述资产在所有情景共享，不构成 S1−S0 的差额投资；但它们可能弱化 Grid-Only 的瓶颈。**B2 只审计这种影响，不能任意取消其中任一条增容来制造延期**。另外 5 条线路仍应保留在总体基线对账中。

### 2.4 必须区分的三类输电容量

1. **已有和已承诺工程**（按原 COD 可用）；
2. **B1 S0CAL** `1,095.6 MW`（建模基线修正，所有情景相同、零新增资源投资）；
3. **正式 S0/S1 内生投资**（有成本、有建设周期，是可比较的公共投资）。

注意：B1 S0CAL 求解的报告中同时出现 `AC_exp` 约 `35.7 GW` 的公共内生扩张（2031 年在运）和新增风电约 `25.7 GW`，它们**不是** `1,095.6 MW` S0CAL。B2 应重新统计正式 S0/S1 的内生扩张，避免把“校准资产”“有成本的公共扩张”“容量累计口径”混为一谈；如正式 S0 规模异常须先分析。

## 3. 不允许为追逐预期结果而做的事情

- **不修改** ERM 的负值、不裁剪 S0CAL、不调低线路额定容量、不增加人为竞争排队负荷、不移动 Epoch 母线、不修改 POI E0 / 程序日期、不更改 RICE/SOFC/Aero/风光/储能技术参数、不扩展正式情景集。
- **不重跑**耗时较长的 B1 `step0`；除非发现校准文件损坏、哈希不符或者数学/单位实错，并经研究者批准。
- **不启动** B3 的 S2、S3、`S3_mS2`，也不运行 B4 `xPOI/xUP/xRA/xPROC/xALL`。
- **不将**已标记为计划或代理的 POI 容量描述成真实已签署接入合同；不把 Far West 约束强加给八个非 Far West 研究母线。
- **不以“BYOP 应当有优势”作为任何参数修正依据。** Grid-Only 没有明显延期也是可报告结果；先验证机制和输入，而不是修改到产生指定结果。

## 4. B2 启动前核对（强制，勿跳过）

**当前基线 HEAD（文档编制时）：** `af00b32a7699344fd64b4129e02957dc3aeb4486`。B0 模型修订提交为 `8636c08d4b9dd11e7624f6fb52f92c91cf439ad0`。如果执行时 HEAD 已变化，先列出变更，确认没有未经批准的 `workflow/byop/{model,inputs,build,run}` 改动；不得默默沿用旧审核结论。

L2 环境：`/datasets/prgm/BYOP_impact/pypsa-usa/workflow`；同一 Git 工作区相对目录为：

```
results/BYOP/mainline/MAINLINE_V13_GREAL_MID_ERMCAL/erm02_calibration.json
results/BYOP/mainline/MAINLINE_V13_GREAL_MID_S0CAL/S0_CALIBRATION.csv
results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc
```

建议先执行以下**不调用优化器**的检查（须在 L2 工作环境）：

```bash
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow

git rev-parse HEAD
git status --short
sha256sum results/BYOP/mainline/MAINLINE_V13_GREAL_MID_ERMCAL/erm02_calibration.json
sha256sum results/BYOP/mainline/MAINLINE_V13_GREAL_MID_S0CAL/S0_CALIBRATION.csv
sha256sum results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc

DRY=1 bash byop/run/run_mainline.sh pilot_s01
bash byop/run/run_mainline.sh gate
```

验收要求：哈希与 §2.1 一致；干运行只包含 `S0 S1_EARLIEST`、有 `--erm-cal` 和 `--s0-cal-file`，**没有** `--attribution`；Gate 实际输出 `approved: true` 且 `reasons=[]`。此外单独检查“**B2 执行授权**”在报告/指令/批准日志中明确存在，不能只看程序门控布尔值。

如 `results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01/` 已存在部分产物，先核查它是否属于此次运行；不能覆盖现有 `case_manifest.json`，也不能混用不同 SHA 的旧日志。若仅有失败的半成品，保全原目录和诊断记录后再在经批准的新 case-id 下运行；任何重命名/重跑都需记录来源与理由。

## 5. 唯一允许的正式求解命令

完成 §4 后，在本机已配置的 L2 shell 下调用：

```bash
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
bash byop/run/run_mainline.sh pilot_s01
```

脚本既定语义：`--mainline --start 2026 --end 2031 --sample-weeks 26 --scenarios S0 S1_EARLIEST`，统一 G-REAL / `mid`，先 S0 再 S1_EARLIEST，不做归因。运行目录应为：

```
workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01/
```

**重要：现有脚本会连续执行 S0 然后 S1，它不会在 S0 出现异常时自动中止再检查。** 因此 B2 结束后必须审计 S0，再决定是否科学接受 S1，不得仅凭进程退出码为 0 即推进 B3。若进程中出现 infeasible、numerical、崩溃或无法读入已冻结输入，应停止、保留失败产物并报告；不要未经批准直接调参或重跑大规模求解。

## 6. B2 科学与数据质量验收

### 6.1 计算是否有效（硬门槛）

- `S0` 与 `S1_EARLIEST` 都 `optimal`，整数/二元变量数为 0；核对 `case_manifest.json` 与 `scenarios/*/solve.json`。
- 输入 SHA、Git 修订、批准 SHA、基准 `.nc`、B1 ERM 和 S0CAL 哈希均可追溯；只变更输出文件不影响输入可复现性。
- S0 和 S1 计算结果符合电力平衡、每年样本权重、研究需求对账；注意 `MAINLINE_GATE_CHECKS.csv` 的 `SCIENTIFIC_USE=PARTIAL_PILOT` 是**设计上的正确状态**，不能误认为 `ALLOWED` 的完整 B3 结论。
- 48 个母线—年份键全部存在且唯一；需求/服务/延期关系满足 `delay_IT_MW = requested_IT_MW − served_IT_MW`（数值容差按源代码、单位一致），延期不得为负；年际在线 IT 的单调性遵循模型逻辑。
- no-harm：正式 S0 冻结下，各个已有用户、继承爬坡负荷在 S1 不应超出 S0 的允许切负荷上界（代码容差 `+0.001 MW`，审计报告中同时报告实际最大违反量）。

### 6.2 特别审计：B1 校准 S0 ≠ B2 经济 S0

B1 校准使用 **`1e8 USD/MWh` 切负荷惩罚**和 **`1e7 USD/MW-year` S0CAL 修正成本**；正式 S0/S1 使用正常的经济目标（基础切负荷惩罚 `1e4 USD/MWh`），并将 B1 校准增容作为固定共同网络资产。这可能导致公共投资组合、弃电/切负荷在 B2 与 B1 校准运行不完全相同。

因此必须独立输出 B2 的正式 `S0`：

1. 2026–2031 年逐年、逐母线的原生负荷和继承爬坡负荷切除 MWh（分别报告），不能用 B1 高惩罚求解的“零切负荷”直接填入。
2. 2031 年在运的公共线路/风电/光伏/储能容量，以及逐年新增投资；特别检查 `AC_exp`、边界口径、累计与非累计容量。必要时提供按母线及走廊的 Top 10 增容清单。
3. B1 的 S0CAL 9 条固定 Link 是否都被正确载入，额定 MW 是否等于原 CSV（应用代码只加载 `added_MW > 0.5` 的行）；是否被重复当作公共经济投资。
4. 若 B2 正式 S0 有明显既有用户切负荷、异常级别公共投资、重大可靠性或能量平衡偏差，**标记 `B2_BLOCKED_FOR_SCIENCE`**，停止进入 B3。先核对来源与成本/约束的建模问题；不得用“B1 是零切负荷”掩盖。

### 6.3 Grid-Only 的 48 行供电延期与约束审计

逐 `site × year` 建立可复现总表，至少包含：

`requested_IT_MW, served_IT_MW, delay_IT_MW, IT_energized_MW, PUE, equipment_total_MW, certified_import_MW, total_import_peak_MW, grid_import_MWh, poi_upgrade_MW_cum, procedure_ready_year, earliest_grid_COD, offer_firm_MW, offer_firm_stress_certified_MW, offer_cond_MW`。

字段仅在相关源表存在时按原定义填入；其他字段用 `NOT_RECORDED` / `NEEDS_DERIVATION` + 说明，**不得以猜测补空值或把 IT MW 当作设施 MW**。必须报告各母线的首次实际在线年份、累计 MW-yr 延期、峰值延期和是否被 E0 设备/升级 COD 限制。

- **POI / 程序：** 按 `GREAL_POI_E0_SCHEDULE.csv` 区分已观测投运、已批准、`PLANNED_UNVERIFIED`；给出 POI 已有设施 MW、投运年份和新增升级设施 MW。优先核查 Abilene、Shackelford、Red Oak、Temple；其他四个母线也不可省略。
- **上游输电：** 提取实际潮流、相关线路或接口拥堵与相应 dual/binding 证据。观察 TL73、TL63、TL3、TL26 等校准线路的峰值流量及利用率；若当前账本不能直接提取相关流量，明确标记 `PENDING_DIAGNOSTIC_EXPORT`，不要擅自重新求解。
- **资源充裕度：** 核对年度 ERM 行残差、dual、binding，说明负 ERM 如何进入要求；在没有可信证据时，不说“ERM 不 binding”也不说“已证实 RA 导致延期”。
- **条件 Firm：** S1_EARLIEST 主要用于生成统一电网报价，核查 `S1_GRID_OFFER.csv` 中普通与压力时段的 Firm 供电能力。不要把压力时段实际最高流量误称作 ERCOT 正式 Firm 认证。PCLR 的触发与预算仍按代码代理。
- **归因边界：** B2 没有运行放松实验，不能声称某种瓶颈贡献了 X% 延期、不能把不同约束的作用简单相加；只报可观察约束、其地理位置与可检验的解释。

### 6.4 零延期也是可能成立的结果

若八个母线多数年份没有延期，不自动判定为失败，也不修改参数。先审查：E0/未来计划容量是否被提前承认；POI 设备是否过宽；上游网络是否因 B1 S0CAL 或有成本 `AC_exp` 投资充足；负 ERM 是否明显宽松；`Firm` 与 `Conditional` 的资格是否正确。只有识别出真实错误或能提供独立依据的敏感性假说，才拟修改方案并提交研究者审批。**不要为了产生 BYOP Speed Premium 而改变数据。**

## 7. 交付给研究者的文件（强制）

### 7.1 L2 本地结果（不得只写“运行成功”）

在 `MAINLINE_V13_GREAL_MID_PILOT_S01/` 目录内保留并登记可核查路径：

- `case_manifest.json`、`MAINLINE_CASE_MANIFEST.json`、`MAINLINE_GATE_CHECKS.csv`、`events.jsonl`、`scenarios/S0/solve.json`、`scenarios/S1_EARLIEST/solve.json`。
- `scenario_summary.csv`、`service.csv`、`poi_ledger.csv`、`poi_upgrade_ledger.csv`、`ledger.csv`、`duals.csv`。
- `MAINLINE_SCENARIO_SUMMARY.csv`、`MAINLINE_BUS_DELIVERY_AND_DELAY.csv`、`MAINLINE_PUBLIC_INVESTMENT_DELTA.csv`（若后处理实际生成，按实记录）。
- `S1_GRID_OFFER.csv`、`PCLR_TRIGGERS.csv`、`S0_shed_by_snapshot_frozen.csv.gz`、`shed_by_bus_S0.csv`、`shed_by_bus_S1_EARLIEST.csv`（文件仅在生成时登记；缺失说明原因）。
- B2 完整运行日志、Gurobi 求解日志及错误/告警摘要；大型文件如受 Git LFS / `.gitignore` 限制，保留 L2 路径、哈希及可下载回传包，**不要伪称已在 GitHub 同步**。

### 7.2 新生成的专题结果表

1. `STAGE_B2_48_BUS_YEAR_GRID_ONLY.csv`：48 行母线—年份主表，含数据字段、单位、来源、状态标记。
2. `STAGE_B2_S0_BACKGROUND_RELIABILITY.csv`：每年全网与各母线原生/继承负荷切除；可另加诊断明细。
3. `STAGE_B2_S0_PUBLIC_EXPANSION.csv`：逐年公共发电/储能/线路新增容量与投资，**单独标明 B1 固定校准容量不计入公共新投资**。
4. `STAGE_B2_POI_NETWORK_DIAGNOSTICS.csv`：按母线/线路列示可得的 POI、上下游可送达与时间资格证据；归因尚不可得时需显式标记。
5. `STAGE_B2_B1_BASELINE_RECONCILIATION.csv`：与 B1 ERM/S0CAL 文件的哈希、9 条校准线路、1,095.6 MW、665.9 MW AIDC 邻近分布对账，以及 B1 校准 S0 vs B2 正式 S0 的可比较指标。
6. `STAGE_B2_AUDIT_CHECKLIST.csv`：每项硬检查/科学解释检查的 `PASS/FAIL/PENDING/NOT_APPLICABLE` 和证据路径。

除现有代码产物外，以上结果表可通过**纯后处理**形成；不要为了提取诊断而无授权改动模型或重跑优化。若必须额外导出未保存的逐时潮流，记录具体缺失内容与最小代码改动，交研究者裁决。

### 7.3 报告和 GitHub 回传（最重要）

生成 `current_work_pckg/STAGE_B2_GRID_ONLY_REPORT.md`，结构必须包含：

1. **执行事实：** 分支/代码 SHA、实际运行命令、输入文件 SHA、运行时间、两个求解终止状态、求解器版本、整数变量是否为 0。
2. **B1→B2 对账：** 负 ERM 原值、9 条 S0CAL 与载入情况、S0 正式目标下切负荷及经济扩张，特别解释可能出现的差异。
3. **48 个母线—年份结果：** 汇总统计、按母线年度服务/延期、首次实际投运年份；重点母线逐项解释。
4. **瓶颈证据及限制：** POI/PROC/UP/RA 中哪些有明确 binding 或其它证据、哪些只是候选解释；没有单因素归因时不做量化分摊。
5. **科学判断：** 当前 Grid-Only 是否出现可信的实质性延期？是否存在明显过度校准迹象？数据是否足够进入 B3？对正负结果都保持中立。
6. **异常、最小修订建议和决定请求：** 若 FAIL，只列最多 1–2 项最关键、有物理依据的修复；若 PASS，提出 B3 执行建议，但**不得自主启动**。
7. **Return manifest：** 生成 `STAGE_B2_RETURN_MANIFEST.md`，逐项列明 GitHub tracked 文件与 L2-only/ignored 的关键数据、准确路径、哈希和获取方式。

将报告、可纳入版本管理的轻量 CSV、摘要日志及 manifest 提交/推送同一功能分支；不要合并 `main`。不得提交超大求解日志、含敏感信息的服务器配置或未经允许的商业数据；以 L2 路径+SHA+回传压缩包作为补充。**提交完成后暂停，等待本会话审核。**

## 8. 分级验收与停止规则

| 状态 | 触发条件 | 下一步 |
|---|---|---|
| `B2_READY` | 授权、门控、源文件哈希均通过 | 只执行 `pilot_s01` |
| `B2_BLOCKED_TECHNICAL` | Gate 拒绝、输入不匹配、运行失败、非 optimal、数学或单位硬错误 | 保存诊断，停止；未经批准不调参重跑 |
| `B2_BLOCKED_FOR_SCIENCE` | 背景负荷不合理切除、no-harm 违规、S0 扩张/校准差异有不能解释的模型性缺陷、关键结果字段缺失到无法判断 | 不得进入 B3；提交原因与最小修复方案 |
| `B2_COMPLETED_WITH_FLAGS` | 两个求解 optimal、无硬错误，但负 ERM、局部过度校准、POI 代理资格等问题仍可能影响解释 | 如实报告、提供必要对照建议；等待研究者裁决 |
| `B2_ACCEPTED` | 48 键和供电延期对账通过、可靠性与经济扩张可解释、科学风险披露充分 | 可**建议** B3；**B3 须单独授权** |

不把“每个 AIDC 必须延期”或“某个约束必须 binding”列入 PASS 标准。`SCIENTIFIC_USE=PARTIAL_PILOT` 是 B2 预期结果状态；不能借此宣布 M2/M4 结论。

## 9. 本轮默认给执行方的简短版本

> 请以 GitHub `mainline-v13-stageA` 的 `af00b32a` 为本轮 B2 审计基线，并在记录 B2 明确授权后执行 `bash byop/run/run_mainline.sh pilot_s01`。保留 B1 原始年度 ERM（含 2029–2031 负值）及 9 条、1,095.6 MW 的 S0 最小增容校准，不修改任何物理参数，也不重跑 step0。先验证 B2 经济 S0 与 B1 校准 S0 的差异，重点核查背景切负荷和 `AC_exp` 内生扩张；再分析 8 母线×6 年 S1_EARLIEST 的接入量、延期与 POI/输电/ERM/程序证据。生成约定的 CSV、`STAGE_B2_GRID_ONLY_REPORT.md`、`STAGE_B2_RETURN_MANIFEST.md` 和数据哈希清单，推送 GitHub 后立即停止等待审核。未经研究者单独批准，不运行 B3/B4，不为制造 BYOP 优势调参。

---

**审批边界：** 本工作包是 B2 科学执行方案及交付标准；是否允许启动求解以研究者向执行方发出的明确 B2 指令和代码门控核验为准。文档本身不代表已在服务器上运行，也不说明任何 B2 实证结果已产生。
