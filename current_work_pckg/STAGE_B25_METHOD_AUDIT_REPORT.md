# STAGE_B25_METHOD_AUDIT_REPORT：Stage B2.5 方法审计报告（无求解器）

- 日期：2026-10-21（纽约时间）
- 依据：`BYOP_ERCOT_StageB25_B3_Exploratory_Work_Package_v1.0_2026-10-21.md` §2
- 事实基线：`3b044c1c038bf42946a6b445f157f08e5efa079c`（B2-R）
- **`RUN_AUTHORIZATION: NOT_APPROVED`；`SOLVER_EXECUTIONS_B25: 0`**
- 只读取了 B2-R 的表格，没有改写任何 B2-R 发布的文件。
- 新输出位于 `workflow/results/BYOP/mainline/B25_METHOD_AUDIT/`，由 `workflow/byop/post/stage_b25_audit.py` 生成。

## A. 2026 年 ERM 零新增裕度（`STAGE_B25_ERM_2026_METHOD_AUDIT.csv`）

**事实**（B2-R，S1_EARLIEST，2026 年）：

| 母线 | 申请 IT MW | 服务 IT MW | 当年可用的预批设备 MW | `serve_cap` 对偶 | POI 是否 binding | 解读 |
|---|---:|---:|---:|---:|---|---|
| Helios | 11.34 | 0 | 800.0 | 0 | 否 | ERM-02 B 首年零裕度：设备充足且 POI 不 binding，ERM 行 binding |
| Abilene | 54.29 | 0 | 955.6 | 0 | 否 | 同上 |
| Midlothian | 8.85 | 0 | 79.8 | 0 | 否 | 同上 |
| Denton | 16.75 | 0 | 225.6 | 0 | 否 | 同上 |
| TX1/SAT14 | 5.15 | 0 | 69.4 | 0 | 否 | 同上 |
| Red Oak | 6.61 | 0 | 0 | −2.8e6 | 否 | **可能有多重约束**：没有预批设备（计划设备不早于 2028 年），ERM 行同时 binding |
| Temple | 2.23 | 0 | 0 | −2.8e6 | 否 | 同上 |
| Shackelford | 0 | 0 | 0 | 0 | — | 2026 年没有需求 |

- **ERM 对偶值**：ERM 是全得州一行约束，每个母线上的对偶值相同（S1 为 6.76e6）。**无法可靠地把它分解到单个母线**，表中保留的是这一共同数值，没有做分解。
- **ERM 是否 binding**：S0 和 S1 都只在 2026 年 binding；2027 年以后都不 binding。
- **延期的三种口径**（只是按年份描述，**不是**放松 ERM 后重新求解得到的因果分解）：

| 口径 | MW·年 |
|---|---:|
| `total_delay_MW_IT_year` | 312.7528 |
| `method_flagged_2026_delay_MW_IT_year` | 105.2211 |
| `post_2026_delay_MW_IT_year` | 207.5317 |

**推断**：
- 对有预批设备的 5 个母线，2026 年的首要约束很可能是 ERM-02 B 的首年零裕度：2026 年的要求等于现有和已承诺机组能达到的 8.196%，而 2026 年无法新增任何 Firm 容量。
- 对 POI 设备为 0 的 2 个母线，可能存在多重约束，不能归为单一原因。

**局限与研究影响**：
- 这是模型内部的校准代理，没有被验证为 ERCOT 的真实 2026 年接网容量界限。
- 它也可能通过 S1 价格和电网报价（2026 年认证 Firm 额度为 0），影响 S2 企业的自供选择和之后的投资。即使 BYOP 最早在 2028 年投运，也不能说这一异常对多期动态完全没有影响。
- 本轮没有求解任何反事实；不能在模型之外通过"减掉 2026 年"来构造修复。

## B. S0 / S1 背景切负荷与 no-harm（`STAGE_B25_S0_S1_SHED_EXPOSURE.csv`、`STAGE_B25_RELIABILITY_FLAGS.csv`）

- **计算方法**：用 S0 的逐时段冻结切负荷（`S0_shed_by_snapshot_frozen.csv.gz`）乘以抽样权重得到 MWh：压力时段每个 3 小时；其余抽样时段平分 8,760 小时中剩下的部分。峰值单位为 MW，与 MWh 分开列出。
- **S1**：B2-R 只保存了按母线 × 年份的 MWh（`shed_by_bus_S1_EARLIEST.csv`）。S1 的逐时段切负荷和峰值标为 `DATA_NOT_SAVED`；继承爬坡在 S1 中按母线的值也没有保存（汇总为 0.503 MWh）。
- **S1 − S0 = −1,977.76 MWh**（S0 为 11,874.50，S1 为 9,896.74）。这只是两个结果的比较，**不是 BYOP 带来的改善**：B2-R 里还没有 S2。

可靠性筛查（沿用 B2-R 标准）：

| 项目 | 实际值 | 阈值 | 结果 |
|---|---:|---:|---|
| S0 六年总切负荷 | 11,874.50 MWh | ≤ 1,000 | **FAIL** |
| 任一母线峰值 | 76.17 MW（Red Oak，2028） | ≤ 10 | **FAIL** |
| 继承爬坡任一年 | 0.494 MWh | ≤ 1 | PASS |
| **S0_RELIABILITY_REVIEW_REQUIRED** | — | — | **ON** |
| no-harm（S1 ≤ S0 + 0.001 MW，逐机组逐时段，由模型检查） | 最大违反 0.001 MW | 0.001 | **PASS**（正好在允许余量边缘） |

**2028 年时段重合**（只有 S0）：
- 2028 年共 136 个时段，Red Oak 有 2 个时段切负荷，p630 13 有 2 个，p630 14 有 1 个。
- 三个母线在同一时段同时切负荷的情况为 0；任一母线切负荷的时段共 4 个，其中 2 个在压力日。
- 上游线路潮流在 B2-R 没有保存（`DATA_NOT_SAVED`），**不推算拥堵比例**。

## C. 成本账本拆分（`STAGE_B25_COST_BOOK_DECOMPOSITION.csv`）

**已核实的账本恒等式**（代码与数据一致）：

```text
social_real_resource_cost_USD = public capex（含 POI 升级） + BYOP capex + system_operating（含 BYOP 燃料） + load_shed_PV
social_total_USD              = social_real_resource_cost + delay loss + curtailment loss + interruption loss (+ 竞争排队损失)
```

能量购电支付和税抵免是转移支付，不计入社会成本。按此分别列出：

| 项目（亿 USD，PV） | S0 | S1_EARLIEST |
|---|---:|---:|
| 实物资源支出代理（`physical_resource_spending_proxy`）= social_real − load_shed | 511.17 | 534.27 |
| 既有用户未服务损失（`load_shed_PV`，按 VOLL 35,685） | 4.09 | 3.40 |
| 研究 AIDC 延迟损失 | 0 | 8.57 |
| 社会总成本 | 515.26 | 546.24 |
| 能量购电转移（不计入） | 0 | 24.11 |
| 恒等式残差 | ≈ 0（PASS） | 0（PASS） |

- `physical_resource_spending_proxy` 只表示"按现有账本扣除 VOLL 后的资源支出代理"，不是重新命名的"真实资源成本"。
- 新函数 `collect_mainline.cost_book_decomposition()` 在 B3 中会对 S2_final、S3、S3_mS2 使用同一结构。

## D. 科学使用状态分层（`collect_mainline.science_layers()`）

| 状态 | 规则 | 按 B2-R 数据重新评估的结果 |
|---|---|---|
| `SCIENTIFIC_USE`（旧列，**含义不变**） | 任何 False 都导致 BLOCKED | `BLOCKED: no_load_shed`（B2-R 原文件不改写） |
| `TECHNICAL_GATE` | 当前阶段必需的物理和数值检查都**显式为 True**（缺失即 FAIL）。<br>B2 阶段：LP、optimal、no-harm、服务量 ≤ 申请量、单调性、能量平衡、POI ≤ 设备、未接网不供电、字典序预求解。<br>CORE 阶段另加：S2 收敛、S2 交付开发商计划、48 键匹配 | PASS |
| `METHOD_FLAGS` | 根据数据判断：首年 ERM（ERM binding 且有服务缺口）、S0 可靠性筛查、S0CAL 潮流是否已导出 | ERM 首年 ON；S0 可靠性 ON；S0CAL 潮流 PENDING |
| `EXPLORATORY_USE` | 技术门控通过时为 `PERMITTED_WITH_METHOD_FLAGS`，否则 `BLOCKED` | PERMITTED_WITH_METHOD_FLAGS |
| `FINAL_SCIENTIFIC_USE` | 有方法标志时为 `PENDING_METHOD_VALIDATION`；**从不自动变成 ALLOWED** | PENDING_METHOD_VALIDATION |

`no_load_shed = False` 保持原样可见。这一项不在技术门控里，但通过 `S0_RELIABILITY_REVIEW_REQUIRED` 体现。

## E. 输出诊断（只增加导出，不改模型）

每个主线情景求解成功后，`ml_export_flows()` 会写出以下文件：

| 文件（`scenarios/<情景>/` 下） | 内容 |
|---|---|
| `s0cal_line_flows.csv` | 9 条 S0CAL Link 的利用率：校准 MW、正反向最大潮流（分开报告，不相加）、最大利用率、按权重计的满载小时、是否与 AIDC 母线相邻 |
| `shed_by_snapshot.csv.gz` | 非 S0 情景的逐时段既有用户切负荷 |
| `line_flows_2028_dfw.csv.gz`（含额定值表） | 2028 年 p630 2 / 13 / 14 相连 TAMU 线路的潮流 |

- 汇总程序会把各情景的 S0CAL 潮流合并为 `STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv`。
- 这些导出没有改动约束、目标、变量或求解顺序；B2-R 缺失的潮流**不通过重跑旧算例来补**。

## F. B3 运行建议

- 技术上可以进入 B3-E：`pilot_core_b3e`，新目录 `MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1`，情景为 S0、S1_EARLIEST、S3、S2（→ S2_final）、S3_mS2，不做归因。
- 结论必须带上这两个方法标志：2026 ERM 和 S0 可靠性。
- 预计用时：单进程 20 线程。S0 加 S1 约 75 分钟，S3 约 30–60 分钟；S2 为开发商 LP（每年一次字典序求解加一次成本求解）加公共复核，最多 3 轮；最后是 S3_mS2。总计约 3–6 小时。
