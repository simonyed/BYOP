# BYOP ERCOT — A0.2 正式求解前综合模型实施工作包 v1.1

**日期：**2026-10-22  
**目标：**把已通过的 A0、尚未执行的“BYOP技术参数完善C”v2.0，以及 A0.1 的三类缺陷修复合并为一个可执行的、版本隔离的 **Pre-Solve Model Integration** 任务，为下一步 A1（两个静态 LP）和后续 A2/A3（动态 S0–S3）提供一致的代码、参数、环境台账和验收门禁。  
**仓库：**`https://github.com/simonyed/BYOP`，分支 `mainline-v13-stageA`；制定本包时已核对 HEAD = `946406d15f016bf6eb7dd37ae11d4ce99ead673d`（A0 report）。执行时重新检查 HEAD；若有后续提交，先列差异并确认不会覆盖，不得用本包旧 SHA 强行重置。  
**已冻结 2025 基线（L2）：**`workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`，SHA-256：`a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`。  
**授权范围：**代码改动、将数值版技术参数接入版本化输入、纯函数与无求解器结构测试、审计表与 Git 提交。**严格禁止任何真实/模拟求解器 optimize/solve_model 调用**，禁止 LP-R、LP-N、S0/S1/S2/S3、旧 step0、B3/B4、全国运行、额外敏感性。GitHub 本身不得由本文件视为已获修改授权的运行结果；执行者需按本任务在自己的工作区实施并回报。  
**最后状态：**`SOLVER_CALLS=0`、`run_authorization=NOT_APPROVED`、`PRE_RUN_STATUS=READY_FOR_RESEARCHER_APPROVAL` 或 `BLOCKED`，**完成即停止等待研究者评审**。

---

## 0. 研究目标、当前事实与本包覆盖范围

论文目标是识别数据中心企业为 **Speed-to-Power** 投资 BYOP，如何反馈至未来公共网架扩张、资源复用和长期私人—社会效率差异；而不是证明某单一设备最便宜。保留 S0 无新增研究 AIDC、S1 Grid-Only、S2 Developer-Driven BYOP、S3 Coordinated Planning，以及 **S3_mS2 matched service**。尤其 S2/S3 **必须共享物理候选、设备池、场址与天然气/许可/COD/可交付约束**，只在决策目标、成本归属和已确定权利上不同。S2 仍为先按年份严格最大化投运 IT、再最小化私人成本，Speed Premium 事后评估；不改成任意较大“延期罚项”标量权重。

当前 GitHub A0 已经完成：冻结 v1.6 公共网基线；主线 A1 采用 2025 冻结 2025 机组、2025 实际小时负荷、16 个 `dynamic_pnnl_v1` 研究母线、统一 `lambda`、3×72h 压力窗口、系统 3,000MW / 1h / 10min 备用代理；A1 约 373,249 连续变量、940,764 约束（**仅 DRY 构模数字，并非已求解**）。旧逐快照 15% ERM 存在与调度 SOC 未绑定的 shadow storage，未来 ERM-02 B 可按现有机组倒推宽松余量，S0CAL 将未来加线视为免费共同资产；**三者只能留在历史回归，不能重新进入新主线。** A0 报告提交 `946406d1`，A0 code `453e846f`、`80e1835f`。A1 目前 `NOT_APPROVED`。v1.6 官方 PRM 差异还有约 4 GW 热机容量口径未解释，West Texas Export Interface 拥塞方向未复现；这些是局限，不通过新增容量或改线路硬拟合。

本包已**实物包含**研究者此次补传的原始 **`BYOP_ERCOT_Technology_Calibrated_Execution_Package_v2.0_2026-10-22(1).zip`**（位于 `source_tech_v2/ORIGINAL_SOURCE_ZIP.zip`，原件 SHA-256 写入 `SOURCE_PACKAGE_RECONCILIATION.md`），同时原样解压其 9 个文件于 `source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22/`。**这批原始 JSON/CSV 而非 A0.2 v1.0 重构参考表，是 TECH_COMP_2 的唯一正式数值来源。** 仍要以 A0/v1.6 的现行代码和授权决定覆盖原 v2.0 文档中的过时执行顺序。旧工作包以 `d0a9bf85` 为起点、假定空间分配及官方锚定校准尚未做完，还要求保留未来 S0CAL 的原逻辑；这些**必须由 A0/v1.6 的现行决定覆盖**。当前研究母线为 **16** 个（不是旧“约17”或 Epoch8），不能硬编码旧键数。2026–2031 是下一轮准备的短期模拟期；2032–2050 的长期参数及投运后追踪接口先保留，**本包不擅自运行或填造 2032+ 供应额**。

## 1. 唯一执行顺序与停止规则

1. **P0 — 安全检查与冻结（0 LP）**：记录执行时 HEAD / branch / dirty 状态；对照 `A0_IMPLEMENTATION_REPORT.md`、`POST_V16_A1_FORMULATION.md`、A1 gate / manifest；验证 v1.6 `.nc` 的真实 SHA；盘点旧技术表、参数读取链、排放输出、供货与 COD 变量。无需重做官方 2025 历史校准或下载原 53 文件。
2. **P1 — 完成 A0.1 原问题（0 LP）**：先修复 A1 objective、硬保护、门禁、写前日志与失败诊断（第 2 节）。A1 2025 静态模型的成本/机组/时段/权重不得受到后续 BYOP v2 参数改动影响。先提交单独代码 commit 与 DRY 摘要。
3. **P2 — 输入版本化与 BYOP 成本、燃料、工期（0 LP）**：实施 `TECH_COMP_2` 的输入适配器和 pure delivery/cost functions；旧 `MAINLINE_V13_TECH_DEFAULTS.csv` 不改。标出每个属性在 S2 与 S3 的读取地点，完成单元测试。
4. **P3 — 环境、许可、供货池与用气（0 LP）**：环境排放→TCEQ 许可路径与资格→审批代理工期→COD（详见专章；不以直接环境损害货币化为主）、共同制造交付池、县 FIPS、气源资格和费用；严禁虚构环境排放或放大 gas MDQ。
5. **P4 — 风光储的 Firm 资格及物理一致性（0 LP）**：完成 24/48/72h 连续压力 LP 的**模型构造**、SOC/能量/签约权利防重、单元和结构测试；不得真正求解该 LP。本项只供未来 A2/A3 使用；A1 模型本身保持独立。
6. **P5 — 集成、多母线与回归、收集交付（0 LP）**：对新主线 S0–S3 的技术/环境/供货路径进行 dry-build 或纯静态检查（尚未实现的 A2 正式 mainline 用 `NOT_READY` 明示，不能伪装已通过）；回归 v1.3、v1.6、A0/A0.1；更新所有受影响 SHA/manifest，全部 gate 仍锁定。提交报告与 manifest，停机。

**不得启动优化求解器，即使“只跑一个微型 LP 看是否可行”也不允许。** 如果模型无法在无求解情况下构建，报告 `BLOCKED_STATIC`, 保留证据而非放开 gate。现有 v1.6 基线及产物均不可修改。工作树/代码 SHA 有漂移则先比对并停止有冲突的部分，禁止强推或重建覆盖。

## 2. P1：原样保留 A0.1 的三项核心修复，补上必须的静态保障

唯一详细指令为本包 `source_instructions/BYOP_A0_1_A1_Gate_Repair_Decision_2026-10-22.md`；以下为不可省略的硬验收：

**FIX-01（物理上限）**：`workflow/byop/model/post_v16_headroom.py` A1 objective 从加权 `EPS_COST*Cdispatch + 1000*E_shed - lambda` 改成 **纯粹最大化唯一的共同 `lambda`**，保证 16 bus 原权重不变；所有旧负荷 shed 在 B0、BL、LP-R、LP-N **硬约束为零**（不能仅用高罚值）。检验 lambda 线性、上界 200,000 MW 未成为假上限；没有次级成本时运行后的调度仅是非唯一 `optimal witness`，不能用作经济拥塞归因。此处的 A1 不包含新建 BYOP 技术。

**FIX-02（验收与先后顺序）**：`post_v16_gate.py` 放行 LP-N 必须核 LP-R 的真实 `RESULT.json`、`PASS=true`、`status=ok`、`termination=optimal`、B0/BL 零切负荷、有限数值与平衡残差；日志最优不足以通行。LP-N `H_network > H_resource+1e-3 MW` 要报 `A1_BLOCKED` 而不只是打印 False；缺结果/NaN/人工容量上界/后处理异常也明确失败。务必区分 LP-R baseline infeasible 与 LP-N network infeasible，不能归于 AIDC。

**FIX-03（调用预算）**：`post_v16_a1.py` 在每次 `solve_model` **之前**原子落盘 `STARTED` 行并持久化（UTC、stage、attempt、code/base SHA）；终态回填同一行。遗留 `STARTED`、错误/崩溃和损坏日志视为一次已消费调用，零自动重试，累计最多两次；不得通过删日志绕过。使用 fake solver 或 monkeypatch 作**仅静态**故障注入，不实际调用优化器。异常分类 `solver_failed/output_failed/acceptance_failed/baseline_pressure_infeasible`。

**附加注意**：A1 还须显式阻断“备用在两类任务中重复充当功率”，验证储能 SOC 是真实调度变量、`tau*r/eta_d <= SOC`、`p_dispatch+p_reserve` 的功率约束；热机 LP 在线容量松弛并非现实 UC/ECRS 资格认证，网络备用是总量要求而非每条线路受扰后可送达认证。

A1 基准代理 **本轮允许用于后续 A1 探索**：R=3000MW，tau=1h，10min；CCGT（pmin=0.50,ramp=4%/min）、OCGT（0.40,10%/min）、coal/gas_steam/biomass（0.40,2%/min），hydro 和 battery 维持 A0 定义。未应用 MORA 未来强迫停运。2025 年末 460.73 MW IT ramp 维持为 protected existing load，但不能称为 2025 历史无重叠估计；不擅减 Native Load。这些**不意味着 A1 已获求解授权**。

## 3. P2：六技术 v2.0 数值基线、币值与成本核算

**唯一新版本标识：**`TECH_COMP_2`（原 JSON 中为 `TECH_COMP_2_2026-10-22`）。源数据已随本包完整提供：

`source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22/{BYOP_TECH_PARAMETER_BASELINE_V2.json,BYOP_TECH_PARAMETERS_V2.csv,BYOP_SUPPLY_POOL_PROXY_V2.csv,BYOP_COUNTY_OZONE_RULES_2026.csv,SOURCE_REGISTER.json,PARAMETER_UNIT_CHECKS.json,VALIDATE_STATIC_PARAMETERS.py,EXECUTION_WORK_PACKAGE.md,README.md}`。

执行方**必须按原始文件真实 SHA 校验后逐字节复制**四份主参数数据到 `workflow/byop/inputs/tech_calibrated_v2/`，不得依据 A0.2 v1.0 的临时 `inputs_reference` 重建，也不得与旧 `v1.3` 混表。原县级臭氧表**19 行、19 个不同 FIPS**，已取得原字节，必须完整使用。无法把研究场址映射到真实县 FIPS 时才使用 `UNKNOWN_CONSERVATIVE`（不能把没有 FIPS 的地点标成达标县）；已知 FIPS 不在原 19 县名录时，暂标 `ATTAINMENT_OR_UNCLASSIFIED` 研究类别并保留 `NOT_IN_LIST_NOT_FULL_LEGAL_VERIFICATION`，不得把这个代理当作所有污染物的达标认证。所有新派生表都需来源文件 SHA/字段映射。

| 技术 | CAPEX ($2025/kW净AC) | FOM ($/kW·y) | VOM ($/MWh) | HHV Btu/kWh | 设备到场 + 安装 (年) | 寿命 (年) | 原技术 firm r |
|:--|--:|--:|--:|--:|:--|--:|--:|
| RICE | 2,200 | 43 | 7.00 | 8,381 | 1.00+0.50 | 25 | 1.25 |
| OCGT_aero | 2,550 | 20 | 5.97 | 9,447 | 1.50+0.50 | 30 | 1.25 |
| SOFC_NG | 3,900 | 125 | 0.72 | 6,469 | 0.75+0.25 | 15 | 1.10 |
| WIND | 1,562 | 34.57 | 0 | 无燃料 | 1.75+0.75 | 30 | 不单独证 Firm |
| PV | 1,342 | 23.60 | 0 | 无燃料 | 0.75+0.50 | 30 | 同上 |
| BESS 4h | 1,500 | 41.84 | 0 | 无燃料 | 0.50+0.25 | 15 | SOC 组合认证 |

CAPEX 为 **2025 年真实美元、净交流容量、未扣税收抵免、建设安装的范围代理**；设备到场与安装阶段不能重复把已含的安装 EPC 另收一次。SOFC FOM `$125/kW·y` 已含服务与电堆更换准备金，不能再重复叠加 stack replacement 年金。`NOx CONTROLLED_ENV` 另加治理 CAPEX/FOM，属于**不同许可设备路径的增量**。RICE 原 `RICE_50DF` 与 `RICE` 的别名只用于参数检索，不能自动给 `RICE_50DF` NG-EGU spark-ignition 许可权利。

`v240_mech.py` 中 `byop_params_v13`/`byop_params` 与 `rearch_mech.py` 中 `ML_TECH`,`ML_TECHS`,`add_byop_cohorts`,`ml_space`,`GAS-mdq` 对齐，建议新增只读适配模块 `byop_tech_parameters_v2.py`。新路径必须由新 post-v1.6 配置显式选择 `TECH_COMP_2`，**旧配置默认 legacy-v13**，旧文件的字节不变。旧 v1.3 不能重新解释为 v2.0。公共发电成本输入不应因为修改 BYOP 技术表而变动。

- 资本成本社会与私人保持各自正确年金：私人 WACC 7%；社会 2%；FOM 每年只计一次；生命周期剩余价值在后续资产账本中独立记录，不将转移支付当作社会真实资源成本。私人基准年度总固定参考：RICE **231.78**、Aero **225.50**、SOFC **553.2** $/kW·y（7% 年金 + FOM，验收允许合理舍入）。
- 天然气费用采用 `workflow/byop/inputs/tech/MAINLINE_V13_GAS_PRICES_2026_2031.csv` 已有 **2026–2031 WSC 电力部门 HHV 2025$**：3.738、3.513、3.576、3.768、4.443、4.857 $/MMBtu，不能用单一常数 3.19 替代。严格 `fuel_MMBtu/MWh = heat_rate_HHV_Btu/kWh /1000`，`fuel_cost_USD/MWh = (HR/1000)*gas_price + VOM`；PyPSA efficiency = `3412.14/HR`。避免 LHV/HHV 双换算与单位千倍错误。
- 技术资金参数必须区分投资与运行权属、社会真实成本与企业财务支出、采购合同/复用资产专属权。S2、S3 新候选技术和工程资格 **相同**；仅成本评价和相应决策机制不同。
- 变量为连续容量，设备模块（如 RICE ~10 MW、Aero ~50 MW、SOFC ~0.325 MW）只做后验模块数可施工性报告，不用无依据 MILP；绝对禁止容量离散与连续约束误混。
- 本阶段**不改 A1 2025 固定存量运行成本与装机**：上述新技术只供 A2/A3 2026+ 自有供电选择的 DRY 模型准备。

## 4. P3a：许可和真实 COD 的严格分离

按原 v2.0 的并行关键路径，纯函数 `byop_delivery_and_permit.py` 接收 `(site_fips, technology, order_year, technology_path, gas_evidence, permit_path, electrical_ready, civil_ready, contract_entitlement)`，返回：

```text
equipment_ready = q + equipment_order_to_arrival_years
site_civil_ready = q + civil_ready_from_order_years
construction_released = max(q, required_preconstruction_permission_year)
installation_done = max(equipment_ready, site_civil_ready, construction_released) + install_commission_years
COD_real = max(installation_done, gas_ready_year_if_gas,
               final_permit_approval_year, electrical_safety_ready_year)
first_full_firm_year = first calendar/investment year whose full eligibility is guaranteed by COD_real
```

如果许可在动工前必须取得而资料不能证明可以并行，使用保守许可路径；禁止无证据假定全部许可与采购可以完全并行。`gas_ready` 只能由原 POI/gas L0/L1/L2 接入、侧管工期和共享 MDQ 认证确定；**县里有天然气机组不等于本站有 firm gas，县里没有天然气机组也不等于永不可能接气**。未知供气不得赋 0 工期或无限气量：保留 L2 现有保守代理（若原配置为 `GAS_L2.lead=3y`，保持该来源并审计）及有限 MDQ，不能未经资质判断自动给予 Firm。

**许可工期代理（年；为排放→许可→COD 的主因果传导参数，而非已验证审批时长）：**

| 技术 | 其他/一般县 | 臭氧非达标县 | FIPS 不确定时 |
|---|---:|---:|---:|
| SOFC_NG | 0.40 | 0.60 | 0.60 + `UNKNOWN_CONSERVATIVE` |
| RICE | 0.75 | 1.25 | 1.25 + `UNKNOWN_CONSERVATIVE` |
| OCGT_aero | 1.00 | 1.75 | 1.75 + `UNKNOWN_CONSERVATIVE` |
| WIND | 0.75 | 0.75 | 0.75 |
| PV | 0.40 | 0.40 | 0.40 |
| BESS | 0.35 | 0.35 | 0.35 |

本包已附原始 `BYOP_COUNTY_OZONE_RULES_2026.csv`（**19 个实际 FIPS**），必须据此映射 DFW、HGB、Bexar 的臭氧区域指定；不能拿 TAMU 母线几何中心代替站点 county FIPS，也不能因 `UNKNOWN_CONSERVATIVE` 即对现实县下法律结论。**2015 和 2008 臭氧标准双重状态**应保留两个原始布尔列，模型分类采用源文件 `classification_FOR_MODEL`，不按母线平均坐标推断。TCEQ 2025 NG-EGU Standard Permit 仅有可能适用于满足条件的**管道天然气 spark-ignition reciprocating engines**，不适用于 gas turbine；所有设备还须审查法规重大源及真实 permit 资格。`permit_path=DEFAULT_ENV/CONTROLLED_ENV` 为**预定义外部枚举路径**，不在 LP 内通过同站拆机绕过污染控制、许可时滞或合并场址排放。未获核实的 2025 预订合同 `verified_preordered_research_MW=0`，`SOFC RESERVED_FAST=0 MW`，防止倒签。

## 5. P3b：环境影响如何进入 Speed-to-Power（**以许可工期为主，不以环境惩罚成本为主**）

### 5.1 唯一优先研究机制

**环境特征（特别是本地空气污染物 NOx 和项目聚合潜在排放） → 许可可适用路径/申请复杂度/审批风险 → 许可准备就绪时间 → `COD_real` → 数据中心首次可交付服务年度 → S2 投资选择。**

- **NOx/控制技术/厂址合并 PTE** 用于申请路径筛查与技术间许可时间代理；**CO₂ 只用于运行排放审计**，不能把较低 CO₂ 或 NOx 直接线性换算为更短审批天数。选址县臭氧分类、设备类型、源规模与许可适用资格是必要中介。
- 采用**原 v2.0 JSON 的离散许可工期表**：`permit.values_years_from_order[class][tech]`，加以可审计的 `permit_path=DEFAULT_ENV | CONTROLLED_ENV`，并按已批准的资格规则选择。没有证据时不得根据 NOx 的具体连续数值制造新的 `permit_lead = a+b × emissions` 函数或自行声称通过评估。治理后较低 NOx 只有在**有相应的许可适用性映射及固定工期**时才可能改变 COD；否则仅改变治理成本/排放和可申报资格，不自动形成提速。
- **SOFC 相对于 RICE/aero** 的低 NOx 特性已体现在原表较短的研究许可代理；这不是 TCEQ 对 SOFC 的免许可承诺。特别注意：TCEQ 2025 NG-EGU Standard Permit 只可能适用于满足全部条款的管道天然气 spark-ignition engines，**不包括燃机**，亦不得在无资格事实时自动授予 `RICE_50DF`。详见本包 `ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md`，其中把资格门控和 COD 归因字段列为硬要求。
- **术语**：德州主要讨论 TCEQ 空气污染源建设许可 / New Source Review 路径；不把全部项目都笼统说成法定环境影响评价（NEPA EIS/EIA）。“排放较低 → 审批更容易”是**待模型验证的机制假说**，不等于法律上的自动批准或固定审查期限。

### 5.2 原始排放参数只服务于许可筛查、台账与既定控制路径

| 技术 | 运行 CO₂ t/MWh | 默认 NOx kg/MWh | 治理后 NOx kg/MWh | NOx 控制额外 CAPEX $/kW | 控制额外 FOM $/kW·y |
|---|---:|---:|---:|---:|---:|
| SOFC_NG | 0.34325 | 0.001 | 0.001 | 0 | 0 |
| RICE | 0.4447 | 0.700 | 0.0675 | 150 | 5 |
| OCGT_aero | 0.50126 | 0.424 | 0.085 | 200 | 4 |

其中 CO₂、NOx 的数据逐项直接读取源 CSV/JSON，不许从此表手工粘贴作为运行参数。运行排放按实际 `MWh × rate` 汇总；审批用潜在最大排放按 `Σ_{站内所有路径/机组} K_MW × 8760 h × NOx_kg/MWh / 907.18474 kg/short-ton` 形成 **NOx PTE 初筛（短吨/年）**。这只是筛查，不包含启动、停机、其它污染物和实际法规计算，也不能据此自动判定 major source、获批或豁免。

SOFC 低常规用水和噪声证据只列入 `TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv` 的环境优势解释；本轮没有同口径跨技术设施噪声/耗水数据，**不**制造额外许可年限折减，也不设置水价/噪声损害成本。风/光/储直接燃烧排放为零不等于无场地/土地/消防许可或生命周期影响。

**本轮不新增独立 CO₂/NOx 货币化社会损害目标、不增加碳税、排放总量优化上限或环境敏感性情景。** 保留真实 NOx 控制设备的额外 CAPEX/FOM，因为它属于实现许可路径所需的资源成本，而不是外部损害罚款。若已有经批准的全局环境约束，仅审计，未经研究者授权不改其值。具体流程/法律门控、关键路径与全部反例详见 `ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md`。

### 5.3 必须验证环境因素真正影响 COD，而不只是台账漂亮

新增一个 **`PERMIT_TO_COD_CAUSAL_AUDIT.csv`**（可参考本包 `tools/dry_environment_mechanism_examples.py` 和 `static_examples/STATIC_PERMIT_COD_EXAMPLES.csv` 的 9 个非求解示例）（本轮用纯函数和预注册小型例子生成 `DRY_NOT_SOLVED`），至少包括：`site_id`, `site_fips`, `tech`, `permit_path`, `NOx_kg_per_MWh`, `CO2_t_per_MWh`, `NOx_PTE_screen_short_tpy`, `ozone_class`, `permit_route_eligibility_status`, `permit_lead_years_proxy`, `equipment_ready`, `civil_ready`, `gas_ready`, `preconstruction_release`, `final_permit_ready`, `electrical_ready`, `COD_without_permit_constraints`, `COD_real`, `permit_attributable_COD_delay_years`, `COD_binding_milestone`, `first_full_firm_year`, `proxy_evidence_class`。

`COD_without_permit_constraints` 是**仅为隔离许可关键路径的非合规计算对照**：同一技术、同一站点、同一供气/供货等参数固定，仅松开环境许可时间，不进入真实投资可行集，更不是另一个正式优化情景。定义 `permit_attributable_COD_delay_years=max(0,COD_real-COD_without_permit_constraints)`，并记录**许可不在关键路径时，该增量必须为零**。对比 SOFC、RICE、aero 若其他约束（尤其气源 L2、设备交付）不同，不能把全部 COD 差归因于排放。

`CONTROLLED_ENV` 在通过有效合法资格判定之后可以有更低 NOx、额外治理成本；如源表未授权它更短的许可时间，默认保留原 `permit_lead`，不得自动创造速度优势。同场址所有技术/路径与排放源聚合，不能拆分 permit path 绕过 PTE。

---

## 6. P3c：供货池、资源路径、天然气权利

明确交付年 2026–2031 **净交流 MW** 的共同设备池：

| 交付年 | RICE | OCGT_aero | SOFC_NG |
|---:|---:|---:|---:|
| 2026 | 250 | 200 | 75 |
| 2027 | 300 | 225 | 150 |
| 2028 | 375 | 250 | 225 |
| 2029 | 450 | 300 | 300 |
| 2030 | 525 | 350 | 375 |
| 2031 | 600 | 400 | 450 |

这些都是 **`RESEARCH_PROXY_NOT_VERIFIED_SPARE_OEM_CAPACITY`**，不是制造商官方预留产能。形式上 `Σ_{s,q,path: delivery_year=y}K_{s,k,q,path} ≤ pool_{k,y}`，跨 16 母线、各路径、下单年共用；S2 企业投资在后续公共阶段是**同一资产**，不能重新占据/释放第二次额度；反事实情景是互斥世界，不应跨 S0–S3 叠加消耗。风/PV/BESS 不虚构全国限额，使用已有站点/母线风光潜力和现场资格。

**供应权与容量权分账**：N 新建、R 合格复用、C 合格容量合同分别登记 `asset_id`, `owner`, `site`, `physical_capacity`, `firm_right`, `contracted_right`, `generation_dispatch`, `year/availability`, `rights_source`; 同一可靠容量在 S2 合同、公共供给和 Firm 认证不得三次出售。空 `GREAL_R_ASSET_POOL.csv` = 没有合格 R 候选，不表示可凭空生成复用机组；`RESERVED_FAST` 在无真正预订证据时拒绝。天然气 `GAS-mdq` 是站点 **MMBtu/day HHV** 的供给上限，公共燃气机组与站点 BYOP 若共享同一已认证管线容量，不能把两份分配都当成独立 firm 权利。保持现有 L0/L1/L2 证据级别，并审计容量信用与逐日燃料消耗是否一致。

## 7. P4：风光储的能量价值与 Firm 认证（仅构模）

不能把 `NONFIRM_BYOP={'WIND','PV','BESS'}` 等同“不许使用风光储供能”。正常发电仍应节省燃料与成本；需要 Firm 时允许**风/PV/BESS 经连续压力窗口联合认证**得到一个经本模型定义的 `F_RE_BESS(site,year)`：

```text
0 ≤ p_wind[t] ≤ CF_wind[t] * K_wind
0 ≤ p_PV[t] ≤ CF_PV[t] * K_PV
0 ≤ charge[t], discharge[t] ≤ K_BESS
0 ≤ E[t] ≤ 4h * K_BESS
E[t+1] = E[t] + sqrt(0.85)*charge[t]*dt - discharge[t]*dt/sqrt(0.85)
F_RE_BESS ≤ p_wind[t] + p_PV[t] + discharge[t] - charge[t]   (ALL t in every registered 24/48/72h stress window)
E_initial ≤ 0.5 * 4h * K_BESS; E_final ≥ E_initial
```

上述为模型**构造规则**，不是保证某项目必有正 Firm。Islanded 禁止虚构公共电网充电；Grid-Connected Flexible 必须把 grid import 资格及后续真实供电时序计入，不能用同一台电池再生成独立的免费 Firm shadow SOC。容量证书与 dispatch 在相同应力时段共同受物理容量和能量限制，避免 BESS 储能分别当成正常负荷和事故备用双份能量。对同站不同组合/合同的 `F` 认证要共享物理资产上限；逐年服务资格与逐时能量平衡分别核查。

气象数据优先现有 ReEDS2/TAMU bus 映射；如果多气象年 CF H5 不在 L2，可使用已有 PyPSA-USA 对齐气象年的原有 CF **仅做干运行构模**并登记 `REEDS_MULTIWX_PENDING_LOCAL_H5`，不能补造某年的气象证据或把实测弃电出力当成自然潜力。无 H5 时不影响本包修复/代码结构验收，但 A2/A3 在论文解释中标为单气象年限制。ReEDS PV DC/AC 口径和 ILR=1.34 不得默认重复乘。系统 ELCC 数值只能作为外部报告对照，**不能直接赋给某单站孤网 Firm**。

本轮新建 `byop_renewable_firm.py` 可生成变量、约束、`F` 的单位与 `SOC` label 校验，但**禁止调用 linopy/Guorbi/HiGHS 等求解方法**，不得把这个 DRY 模型的存在写成“已证明 72h 可供电”。

## 8. 多母线、主情景与历史版本隔离

- 遍历现行 `SITES` 实际长度 **16**，不是硬编码 8/17。统一 `research_cohorts`、`POI`、`dynamic_pnnl_v1`、生效 PUE、继承 460.73 MW IT；L2 所有既有 2025 机组、线路与真实需求不变。缺 FIPS 的母线不是“推算 POI 位于相邻县”；必须记录真实 site-versus-bus 地理不确定性。
- A1 是 2025 **静态**固定存量的物理余量，v2 技术供 2026+ S2/S3，**不允许把 A1 的 `H_resource/H_network` 直接当作 2029 的即时可接入容量**。A0 发现 2026–2028 联合 POI 权利零，仅说明 16 bus 固定权重共同放大受一个零资格母线约束；S1 按站/按年份分期 COD，不得将区域全部研究负荷设为零。
- 新 A2 `rearch_mech.py --post-v16` 现有约束未就绪，exit 3 是有意门禁。A0.2 只做代码与结构准备，**不得通过删掉 exit 3 来假称 A2 READY**。在另一个授权阶段完成新运行备用、多年度付费公共扩张及权利一致性后才单独审查 A2。
- 2026 以后主规划公共发电/输电扩张必须有真实成本与工期，不能执行免费 S0CAL 或自动放松到 ERM-02 内生最大可满足裕度；旧输入保留归档可复现但不激活。
- `S3_mS2` 模型键随 16 母线和真实 (site,year) 全集合动态形成；不能硬编码过去 48 个键。S2/S3 的完整同服务对照仍是论文核心（M4）。
- 不调整背景负荷、研究 AIDC 数量、Firm/Conditional Firm 服务权与企业 speed-first 顺序来强制得到理想 BYOP 结果。

## 9. 修改目标与实施接口（按现有仓库逐项映射）

| 文件 / 模块 | 改动类型 | 本阶段验收 |
|---|---|---|
| `byop/model/post_v16_headroom.py` | A0.1 的 strict max λ、既有负荷硬保护 | 反例静态测试 |
| `byop/model/post_v16_gate.py`, `byop/run/post_v16_a1.py` | 先写 STARTED、LP-R PASS 才启动 LP-N、异常分级 | 故障注入无求解 |
| `byop/run/run_post_v16.sh`, `config/config.byop_post_v16_a1.yaml` | A1 现有 base SHA/不带 legacy flags 保持；A0.1 更新 manifest | DRY + 不授权 |
| `byop/inputs/tech_calibrated_v2/*`（新） | v2 版本化六技术、供货/许可/排放/证据 | 读取/单位/哈希校验 |
| `byop/model/byop_tech_parameters_v2.py`（建议新） | 参数适配、同一 gas price 年份、private/social 成本 | 6 tech 单元回归 |
| `byop/model/byop_delivery_and_permit.py`（新） | 并行 COD、**环境许可资格→审批工期→COD**、气源门控、FIPS/合同资格 | 19 FIPS、许可关键路径、真实 COD 反例 |
| `byop/model/byop_supply_pools.py`（新） | 交付年池、共用资产、N/R/C 权利审计 | 压力/跨年归集静态校验 |
| `byop/model/byop_emissions.py`（建议新） | CO₂/NOx/PTE 筛查、控制成本和证据；**与许可路径和 COD 接口相联** | 源 CSV、PTE 单位、资格审核、路径互斥 |
| `byop/model/byop_renewable_firm.py`（新） | 连续时间窗口、能量与 Firm 共同约束构模 | 无求解 SOC/变量复用校验 |
| `byop/model/v240_mech.py`, `byop/model/rearch_mech.py` | 添加 **显式 TECH_COMP_2 flag** 与参数/许可/供货结构接口；旧 v1.3 仍默认 | 旧/新均 DRY 可构建 |
| `byop/post/*` | TECH 成本/环境/供货/COD/Firm 审计及 M4 动态键 | 不制造求解产物 |
| `byop/build/build_post_v16_manifest.py` 与 A1 gate | 增量哈希与分阶段门禁，包含已冻结 baseline SHA | 全部求解仍拒绝 |

修改前逐项核对函数是否仍存在；若代码已有同等成熟组件，复用并标清而不重复实现。不得仅靠将 v2 值追加在 CSV 后面就标记模型集成 PASS；每个 v2 属性都需在 `SOURCE_TO_PARAMETER_CROSSWALK.csv` 中写出 `CSV key → loader → state → build / constraint / ledger → test`。

## 10. 必须通过的静态测试矩阵（全部 zero-solver）

| 测试组 | 具体测试、反例和停止条件 |
|---|---|
| `T-GATE` | A0.1 weighted objective 消失；hard zero shed；虚构 optimal+positive shed/缺结果/无 PASS/NaN/上下限反常应拒绝；先写 STARTED 崩溃不能重跑；预算 2 次 0 retries；错误 baseline SHA 报拒绝 |
| `T-VERSION` | legacy v1.3 参数表与 v2 分离；legacy 旧结果可按配置构模；16 bus 无 `len(SITES)==8`；所有数值有单位、来源、币值，空的关键参数不可静默变 0 |
| `T-COST` | RICE/Aero/SOFC 私人年固定成本 231.78/225.50/553.2；2028 燃料成本按 HHV；SOFC stack 只计一次；SCR 额外资本/固定费只在有证据 CONTROLLED 环境路径计入 |
| `T-COD` | 标准 SOFC 2026 下单在纯设备/安装条件下 2027 COD；L2 gas 3y 时不早于 2029；2027.25 COD 不得认定 2027 全年 Firm；SOFC_FAST 无可核预留时为 0；permit 高风险县不比一般县更快 |
| `T-ENV-COD` | **主验收**：原始 19 FIPS 源表、TCEQ NG-EGU 不适用于 turbine/未经核实 RICE_50DF；SOFC/RICE/aero 许可代理正确映射；NOx/PTE 归并、控制前后资格审查；许可在关键路径才令 COD 变化，设备/气源更慢则效应严格为 0；无许可事实不因低 NOx 自动获批或提前；`CONTROLLED_ENV` 不自动加速；零货币化环境罚款 |
| `T-SUPPLY` | 2026–2031 三技术 18 项限额精确一致；一资产不重复计供货；跨路径/母线不超限；未来没有 2032+ 值不默认无限、0 或复制 2031（需未来授权） |
| `T-RE_FIRM` | 4h BESS × MW，eta_rt=.85，真实 SOC label；弱风弱光可构造零 Firm 而非任意容量；窗首 SOC<=50%、窗末>=窗首，24/48/72h 时段连续；不得产生第二套 shadow SOC |
| `T-BASELINE` | L2 v1.6 `.nc` SHA、全部 2025 fleet、x/r、s_nom、Native Load / 460.73 MW IT、dynamic 16 weights 不变；旧 S0CAL/ERM 不进入 new path |
| `T-DELIVERABLE` | 仅构模的结构/尺寸/SHA/数学表达和审计表；测试内 monkeypatch 全部实际 `optimize/solve_model` 必须 fail；任何 fake 的结果文件明确 `DRY_NOT_SOLVED` |

### 验收之外的真实求解限制（必须在报告注明）

- A1 尚未经真实求解；不能因有 373k 变量的 DRY 结构就推断 feasible。LP-R 和 LP-N 最多 2 次且需另行批准。
- A2 后续必须实现多年度新备用、成本与工程工期的公共扩张和私有 BYOP，一次性的技术版本接入并不自动意味着 A2_READY。特别警惕旧主线继承了 15% ERM shadow SOC、未来 S0CAL 与 S1 事前电网出价限额。
- 本次可将技术 v2.0 代码完整 DRY 串入 S2/S3 配置，但若主线尚不支持，不得取消 `POST_V16_MAINLINE_NOT_READY` 保护；按 `TECH_INTEGRATED_STATIC_ONLY` 交付并列未来阻断量。
- 真正环境经济效率比较应在 matched service 与同一环境成本边界下完成；本轮只有运行排放和环境治理成本、许可时滞，未建立可被认为真实的健康损害、生命周期碳/水社会价格。

## 11. 交付目录、报告格式和提交门禁

在 `current_work_pckg/` 交付以下文档/表，并为新代码与参数生成版本化仓库目录，不改旧 2025 `.nc`：

```text
A0_2_INTEGRATION_REPORT.md             # 决策+验收, 唯一总控返回
A0_1_REPAIR_REPORT.md                 # A0.1 三 FIX 的独立证明
TECH_V2_IMPLEMENTATION_AUDIT.md      # 本包 v2 6 技术落地证据和原 v2 数值差异
SOURCE_TO_PARAMETER_CROSSWALK.csv     # 原始来源/数值/单位/loader/变量/约束/test/证据级别
TECH_COST_AND_COD_AUDIT.csv          # 数值通过纯函数生成, 状态 DRY_NOT_SOLVED
TECH_PERMIT_STATUS.csv               # site FIPS coverage, unknown conservative flags
TECH_SUPPLY_USAGE_STATIC_QA.csv      # 可用额度、权利映射, 非真实最优投资结果
TECH_ENVIRONMENT_EVIDENCE_LEDGER.csv # CO2/NOx、水噪证据；只服务许可代理/后处理
TECH_EMISSIONS_PROXY_STATIC_QA.csv   # 单位/项目合并 PTE 小例子, 非仿真排放
PERMIT_TO_COD_CAUSAL_AUDIT.csv        # 环境许可 -> COD 的主机制；许可非关键时效应为零
TECH_RE_BESS_FIRM_STATIC_QA.csv      # 构模/SOC/单站认证条件, 不写 solved Firm
A0_2_TEST_SUMMARY.json               # L2 pytest totals + dry structure + monkeypatch guard
POST_V16_A1_PRE_RUN_MANIFEST.json    # 最新哈希, locked
A1_GATE_VERDICT.json                 # NOT_APPROVED
A2_TECH_READINESS_MATRIX.csv         # 模块 READY_STATIC / NOT_IMPLEMENTED / BLOCKED
A0_2_RETURN_PACKAGE.zip             # 本地/L2/GitHub对账所需小文件; 不含大型原始数据
```

`A0_2_INTEGRATION_REPORT.md` 最后必须严格追加固定返回块：

```text
BRANCH / START_SHA / FINAL_CODE_SHA / FINAL_REPORT_SHA:
PRE_RUN_STATUS: READY_FOR_RESEARCHER_APPROVAL | BLOCKED
SOURCE_V2_PACKAGE_PRESENT: TRUE | FALSE ; NUMERIC_CROSSWALK_RESULT: ...
V16_BASELINE_SHA_VERIFIED: ...
A0_1_FIXES: FIX01=..., FIX02=..., FIX03=...
TECH_VERSION: TECH_COMP_2 ; LEGACY_V13_UNCHANGED: ...
TECH_V2_SIX_CARRIER_QA: ...
PERMIT_FIPS_COVERAGE_AND_UNKNOWN_CONSERVATIVE: ...
COD_AND_GAS_EVIDENCE_QA: ...
SUPPLY_POOL_2026_2031_QA: ...
DIRECT_EMISSIONS_NOX_AND_NONQUANTIFIED_ENV_QA: ...
PERMIT_TO_COD_CAUSAL_QA: ...  # 本包优先；需看许可关键路径与实际 COD 改变
RE_BESS_FIRM_STATIC_ONLY: ...
S2_S3_SAME_PHYSICAL_FEASIBLE_SET_STATIC_QA: ...
A1_GATE_LOCKED / A2_GATE_LOCKED / A3_GATE_LOCKED: ...
PYTEST_TOTAL_PASS_FAIL_SKIP_AND_L2_ENV: ...
REAL_SOLVER_EXECUTIONS: 0
LEGACY_ERM02_S0CAL_IN_POST_V16: DISABLED
DELIVERABLE_FILES_AND_SHA256: ...
UNRESOLVED_BLOCKERS_FOR_A1: ...
UNRESOLVED_BLOCKERS_FOR_A2_A3: ...
NEXT_RESEARCHER_DECISION: REVIEW_A0_2_THEN_SEPARATELY_APPROVE_A1
```

**核查关键原则：**出现单站缺少县级 FIPS、既有代码缺少新建技术的真实约束接点、气源权利无法区分时，必须透明记录 `UNKNOWN_CONSERVATIVE` / `NOT_IMPLEMENTED` / `BLOCKED`。不允许用空参数、零工期、无限 gas、虚构厂商定单、环境税或“全部 static tests pass”替代物理/许可有效性。

**执行 STOP：**提交 v2 技术与 A0.1 修复的代码、输入、报告、所有可审计文件后立即停止；`run_authorization: NOT_APPROVED` 不得改变。本轮**不批准实际 LP-R/LP-N**。研究者下轮单独审核后才能设定 A1 的 `APPROVED` 和 approved SHA（只能有该阶段合法配置修改）；LP-N 还须等待 LP-R 通过 PASS。A2/A3 再单独批准。

## 12. 现有资料与版本来源

1. `current_work_pckg/A0_IMPLEMENTATION_REPORT.md`、`BASELINE_AND_RESERVE_CONSTRAINT_INVENTORY.csv`、`POST_V16_A1_FORMULATION.md`、`POST_V16_A1_PRE_RUN_MANIFEST.json` (A0 commit `946406d1`).
2. 本包随附 `source_instructions/BYOP_A0_1_A1_Gate_Repair_Decision_2026-10-22.md` 和 `source_instructions/论文顶层设计.md`，以及本版新加的 `ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md`。
3. “BYOP技术参数完善C”最后形成的 **v2.0**：`BYOP_ERCOT_Technology_Calibrated_Execution_Package_v2.0_2026-10-22.zip`、`EXECUTION_WORK_PACKAGE.md`，原 ZIP 原样随附 `source_tech_v2/ORIGINAL_SOURCE_ZIP.zip`，解包文件全部包含，`BYOP_TECH_PARAMETER_BASELINE_V2.json`、`BYOP_TECH_PARAMETERS_V2.csv`、`BYOP_SUPPLY_POOL_PROXY_V2.csv`、`BYOP_COUNTY_OZONE_RULES_2026.csv` **均为原始字节**。`SOURCE_PACKAGE_RECONCILIATION.md` 存放对应 SHA；不再使用前版手工重编参考数值。
4. 旧参数已在 GitHub `workflow/byop/inputs/tech/MAINLINE_V13_TECH_DEFAULTS.csv`；WSC 天然气价格在 `MAINLINE_V13_GAS_PRICES_2026_2031.csv`；BYOP 技术候选链 `byop/model/v240_mech.py` 和 `byop/model/rearch_mech.py`。不得直接覆盖旧路径。
5. 官方说明/证据以 v2.0 原工作包给出的 Bloom 2026 Energy Server datasheet、TCEQ Air New Source Review (NG EGU SP、Turbine)、ERCOT ELCC、ReEDS、EPA AP-42/GHG 数据库为依据；本轮不授权执行方开放式新资料搜集。
