# 环境低排放 → 环境许可 → 较早 COD：A0.2 v1.1 唯一机制实施规范

**优先级：** 与同级 `EXECUTION_WORK_PACKAGE.md` 一起执行；若原 2026-10-22 技术 v2.0 的旧顺序或环境文字与本文件冲突，以当前 A0/v1.6 冻结+本文件机制边界为准。**本轮完全禁止求解优化问题，所有示例是纯函数判定与静态单元测试。**

## A. 因果链条与研究意义

`technology/controls → pollutant emissions and site-wide potential-to-emit (PTE) → potentially applicable air authorization and review complexity (including ozone status) → project-specific permitted construction/commissioning milestone → effective COD → earliest full-year Firm IT service → developer speed-first preference`。

- 这不是 `CO₂ = 0 ⇒ no permit`，也不是 `低 NOx ⇒ 快 x 个月` 的事实性法律推断，而是**基于 TCEQ 许可类型事实与项目参数表的透明研究代理**。
- **本地 NOx/PTE** 的意义在于路径资格、控制设备与审查风险；CO₂ 只用于后处理吨数（可以展示社会与气候后果，但本轮不带价格进入目标）。水/噪声为非定量旁证，不推动 COD 数值。
- 许可代理主要来自原 v2.0 `BYOP_TECH_PARAMETER_BASELINE_V2.json` 的 `permit.values_years_from_order`：SOFC 一般 0.40/非达标 0.60 年，RICE 0.75/1.25，aero 1.00/1.75；WIND 0.75，PV 0.40，BESS 0.35（一般与非达标保持一样）。默认 `UNKNOWN_CONSERVATIVE` 取非达标值。
- 同一技术可以选择 `DEFAULT_ENV` 和 `CONTROLLED_ENV`（若证据与设施资格合法）。控制路径降低 NOx 但增加明确的 SCR CAPEX/FOM；**仅在原表中存在预先批准的许可时间差或额外官方证据时**才允许修改其审批工期，否则保持相同的对应县类别许可代理时间。不能用优化模型结果反过来“校准”许可工期。

## B. 资格门控先于优化决策

1. 输入是**真实研究场址** `site_id, county_fips, equipment_type (SI or dual-fuel unknown), tech, technology_path, permit_path, site_known_major_source_data, gas_evidence_level`，不允许仅凭聚合 TAMU bus 坐标宣称某县法规适用。`county_fips` 缺失则 `UNKNOWN_CONSERVATIVE`，带 flag；已知不在 19 FIPS 表则 `ATTAINMENT_OR_UNCLASSIFIED` 作为研究分类并保留非完全认证标记。
2. **NG-EGU 2025 许可路线只可能针对 spark-ignited pipeline natural gas engines** 且需审查其所有标准许可条件；gas turbines 不在适用范围；`RICE_50DF` 名称不足以证明 SI。TCEQ 标准许可不涵盖构成新的重大固定污染源或重大改建的项目，也不能代替其它适用许可。源：https://www.tceq.texas.gov/permitting/air/newsourcereview/combustion/ng-egu-sp 与其 2025-01-30 标准许可原文。
3. 风光储仍可能受到土地、消防、施工、接入等许可限制，其 CO₂/NOx 直接燃烧=0 **不是** COD=0 或免许可。
4. SOFC 很低的 NOx 只说明有潜在路径优势；从原证据不能证明任何一般性依法自动豁免，不能把 SOFC 赋予标准天然气发动机许可（除非有单独适用法规来源）。
5. 厂址内多个设备/处理路径按同一 `site_id` 聚合 PTE。`PTE_NOx_short_tpy = Σ K_MW × 8760h × rate_kg/MWh / 907.18474 kg/short ton`（注意 **分母为 907.18474 kg/短吨**，不是 907,184.74），并明确是忽略启停、不同污染物和操作细节的**非常粗略初筛**。如需要完整合法审查，应由以后独立的监管证据补足，不能将此筛查映射为 major source 真假结论。

## C. 时间规则：每种路径的关键里程碑

为避免把快许可误写成必然快投运，要求每项候选生成：

```text
q = order_year
permit_class = county_mapper(site_fips, original_BYOP_COUNTY_OZONE_RULES_2026.csv)
permit_lead = ORIGINAL_TECH_V2_JSON.permit.values_years_from_order[permit_class][tech]
permit_release = q + permitted_preconstruction_milestone_lead
permit_final_ready = q + permit_lead
supplier_ready = q + equipment_lead
site_civil_ready = q + civil_lead
installation_complete = max(supplier_ready, site_civil_ready, permit_release) + install_commission_lead
COD_real = max(installation_complete, permit_final_ready, gas_ready_if_applicable, electrical_ready)
first_full_firm_year = first year guaranteed for all relevant model snapshots after COD_real
```

- `permitted_preconstruction_milestone_lead` 是法规/审批规则决定的前置工期，不能把尚未颁布许可的项目默认当作已合法动工。若无数据证明环保许可可与安装施工并行，**固定默认 `permitted_preconstruction_milestone_lead = permit_lead`**；只有可追溯证据确认无需前置许可或可合法并行施工，才可使用较早的开工日期。该默认有明确数值，不得填 `NaN` 或留空。单纯 `max(设备,许可)` 并不总是足够。
- `COD_without_permit_constraints` 仅作归因审计的**不合法反事实**：去除上述 `permit_release` 和 `permit_final_ready`，其它输入逐个完全固定。它不是新可投建选项，也不是 LP 求解情景。
- `attributed_environment_permit_delay = max(0,COD_real-COD_without_permit_constraints)`；此值只有当许可产生**净关键路径约束**才大于 0。设备、天然气、土地与电力接入比许可更慢时应为 0。
- `COD_tech_A - COD_tech_B` 一般包含采购、工地、许可、燃气等多重差异，**不得全部归因环境**。若要看同一技术变更控制路径的效果，只能在相同站点与其余条件固定的 pure function pair 中展示，仍无额外 LP。

## D. 开放的许可资格、受控路径和代码执行要求

- `NOx_kg/MWh` 及 `CO2_t/MWh` 按原 CSV/JSON，2025 美元、额定 MW Net AC 边界不改变。
- SOFC `0.001 kg/MWh`，RICE 默认 `0.700`、受控 `0.0675`，aero 默认 `0.424`、受控 `0.085`；RICE 受控增量 CAPEX `$150/kW`+FOM `$5/kW·y`，aero 为 `$200/kW`+`$4/kW·y`。参数性质为原 v2.0 研究代理，不是 TCEQ 对实际机组的核定排放限值。
- `DEFAULT_ENV` 和 `CONTROLLED_ENV` 属于预枚举**受控技术路径**；选择前应判断气源、环保资格和同址总量限制，合同/制造产能不能两路径重复出售。**没有已明确映射的许可期限变化时，控制治理并不自动缩短 COD**。
- 后处理实测运行排放：`CO2_t = Σ MWh×CO2_t/MWh`；`NOx_kg = Σ MWh×NOx_kg/MWh`。`Carrier.co2_emissions=0` 是 PyPSA 数据结构兼容值时必须在审计注明，不意味着无排放。
- **不设置**运营期排放货币罚款、统一社会碳价、水税、噪声罚金或外部健康损失；真实污染治理设备成本可以进入投资/固定运维。未来如需污染物损害，应通过独立研究者授权而不是本轮执行方自主增加。

**随包纯函数示例：** `tools/dry_environment_mechanism_examples.py` 与 `static_examples/STATIC_PERMIT_COD_EXAMPLES.csv` 已用原 JSON 的许可与设备工期计算 9 条非求解示例，展示某些情况下许可延迟 = 0、RICE/aero 臭氧许可约 0.25 年的关键路径影响以及燃气三年造成的环境优势不显现。执行方须把这类证明真正连接到未来技术 COD loader，而不能把示例 CSV 直接冒充 S2/S3 最优解。

## E. 无求解器反例：必须全部 PASS

| Case | 输入条件 | 必须结果 |
|---|---|---|
| ENV-01 | 19 个源表 FIPS、2015/2008 布尔标志 | 原始 19 行唯一、类别 2015/2008_ONLY 正确；无 FIPS -> UNKNOWN_CONSERVATIVE |
| ENV-02 | `RICE_50DF` 只有技术代号，没有天然气 SI 证据 | 不自动授权 2025 NG-EGU 标准许可；aero 永不走该路线 |
| ENV-03 | 2026 下单、无气源/场址额外延迟，SOFC 一般许可 0.4y、设备 0.75+安装 0.25y | `COD_real=2027.0`；许可非关键，环境许可净延期为 0 |
| ENV-04 | 2026 下单 RICE，已证前置审批令施工不得先开始，非达标县许可 1.25y、设备需 1.0y、安装 0.5y | 不能将未取得前置许可的 0.25 年完全当作可并行施工；明确 COD 计算是否受其约束 |
| ENV-05 | 2026 下单 SOFC，燃气侧线三年才就绪 | `COD_real ≥ 2029.0`，SOFC 低排放**没有**提高投运速度 |
| ENV-06 | 同一路径 NOx 从 RICE 0.700 改到 0.0675，审批时长输入不变 | `NOx_PTE` 下降、额外 SCR 成本正确、`permit_lead` 与 `COD` 均不自动改变 |
| ENV-07 | 同站两条技术/排放路径汇总 | 厂址聚合 PTE；不允许两条互斥路径加总可用 Firm 或规避总量 |
| ENV-08 | 许可环节是瓶颈，其他全部输入冻结，改用**原表已允许的不同许可代理年限** | `COD_real` 应随许可能否及时就绪而变化，且 `attributed_environment_permit_delay>0`（不能只有 emissions ledger 的数字变） |
| ENV-09 | 风/PV/BESS 本地直接 CO₂/NOx=0 | 仍保留正数的场址/消防/工程许可时间，无自动 COD=0 |
| ENV-10 | 比较 SOFC 与 aero 默认模式，其他资源条件不同 | 报告全 COD 差及各 critical milestone，不得错误标记全差为环境 |

## F. 主交付物

- `PERMIT_TO_COD_CAUSAL_AUDIT.csv` — **A0.2 主要机制审计表**，严格区分实际有法规证据的资格 vs 研究代理工期，按技术×母线×候选许可路径提供纯函数示例。
- `TECH_PERMIT_STATUS.csv` — 19 个真实官方表内 FIPS、研究站点 FIPS 完备率、未知地点保守处理、许可途径与资格未确定 flags。
- `SOURCE_TO_PARAMETER_CROSSWALK.csv` — 明示 `source TECH_COMP_2 JSON/CSV → loader → tech/control-path constraints → permit_milestone → COD → served_IT` 的完整数据链。
- `TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv` — 有实测依据/代理/未知环境属性，至少 CO₂、NOx、水与噪声，并标明哪个属性可以影响 COD，哪个只作报告。
- `A0_2_INTEGRATION_REPORT.md` — 小节说明**许可路径在什么时候会/不会成为关键瓶颈**，并区分“低排放提供潜在许可加速”与“实际 COD 确实提前”；必须写出 ENV-03/05/06/08 的具体输出而非仅 PASS 字样。

**结束条件：** `REAL_SOLVER_EXECUTIONS=0`， A1/A2/A3 保持 `NOT_APPROVED`；本轮不得将上述机制转化为正式结果图或论文结论。
