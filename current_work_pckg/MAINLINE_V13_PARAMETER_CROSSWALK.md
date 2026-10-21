# MAINLINE_V13_PARAMETER_CROSSWALK：旧代码参数 → 证据 → v1.3 拟采用值 → 代码字段

- 日期：2026-10-21
- 状态：`STAGE_A`，所有值为**拟运行默认值**，等待研究者运行前审计；`RUN_AUTHORIZATION: NOT_APPROVED`。
- 本表回答三个问题：
  1. 每个字段在旧代码中的值和覆盖路径是什么；
  2. v1.3 工作包附表的值和证据等级是什么；
  3. 现在由哪个代码字段读取。

"旧值"指 commit `be2c6904`（v1.3 起草时的 HEAD）中的值。旧值不会被静默替换：

- v1.3 的值只在 `--mainline` 下生效。打开方式是在 `v240_mech.CFG` 中设置 `tech_v13`、`gas_by_year`、`firm_full_year`。
- 不带 `--mainline` 时，旧的 v1.0 和 7 区回归路径完全按旧值运行。

## 1. 现场 BTM 技术（D2.a）

技术表读取路径：

- `workflow/byop/inputs/tech/MAINLINE_V13_TECH_DEFAULTS.csv` → `v240_mech.byop_params_v13()`。该文件与 `current_work_pckg/` 附件逐字节相同，测试 `QA-PARAM` 用 SHA-256 核对。
- 模型载体与 v1.3 技术 ID 的对应关系在 `V13_ID` 中：RICE→RICE_50DF，SOFC_NG→SOFC_NG_STANDARD，OCGT_aero→OCGT_AERO，WIND→WIND_ONSHORE，PV→PV_TRACKING，BESS→BESS_4H。

| 技术 | 字段 | 旧值（TECH-01 base / 旧代码） | v1.3 值 | 证据等级 | 代码字段 | 说明 |
|---|---|---:|---:|---|---|---|
| RICE 50DF | CAPEX USD/kW | 2450 | **2450** | PROXY | `capex_2025USD_per_kW_netAC` → `overnight_per_MW` | 不变 |
| | FOM USD/kW·年 | 43.0 | **43.00** | PROXY | `fom` | Liberty 申报的 15 / 2.65 只作对照 |
| | VOM USD/MWh | 7.0 | **7.00** | PROXY | `vom` | |
| | HHV 热耗 Btu/kWh | **8295** | **8381** | PROXY | `hr` → 机组 `efficiency = 3412.14/hr` | **改变**；8295 只留作回归 |
| | 工期 年 | 2 | **2**（代理） | PROXY | `reference_lead_years` → `approval_cohorts(lead)` | COD = 批准年 + max(2, 供气支线工期) |
| | 寿命 年 | 25 | 25 | PROXY | `BYOP_LIFE['RICE']` | |
| SOFC 标准 | CAPEX | 7953 | **7953** | SOURCE_FACT_PLAN（EIA TRE） | 同上 | 不是 Bloom 报价 |
| | FOM / VOM | 37.77 / 0.72 | 37.77 / 0.72 | SOURCE_FACT_PLAN | | |
| | 热耗 | 6469 | 6469 | SOURCE_FACT_PLAN | | |
| | 工期 | **0.5**（TECH-01 base；low 0.25） | **3** | SOURCE_FACT_PLAN | | **改变**：0.5 年只适用于已有合格预采购的快速 SOFC |
| | 寿命 | 15 | 15 | | | |
| SOFC Fast | 可用槽位 | 隐含：TECH-01 low 2650 USD/kW、0.25 年 | **0 MW** | D14 | `SOFC_FAST_ELIGIBLE_MW = 0.0`（不提供该技术） | 2650 不作参考值 |
| Aero OCGT | CAPEX / FOM / VOM / 热耗 / 工期 | 2275 / 9.99 / 5.97 / 9447 / 2 | 相同 | PROXY | 同上 | v1.0 默认不开放（`--byop-techs RICE SOFC_NG`）；v1.3 **开放**（D15） |
| | 寿命 | 30 | 30 | | | |
| 陆上风电（现场） | CAPEX / FOM / VOM | 无（v1.0 无现场风电） | 1562 / 34.57 / 0 | SOURCE_FACT_PLAN | `byop_WIND` | **新增**；用母线逐时出力；Firm 信用为 0 |
| | 工期 / 寿命 | — | 3 / 沿用 PyPSA-USA | | `BYOP_LIFE['WIND']` 取 PyPSA-USA 候选机组寿命 | 受 ReEDS2 共享上限和现场上限约束 |
| 跟踪光伏（现场） | CAPEX / FOM / VOM | 无 | 1342 / 23.60 / 0 | SOURCE_FACT_PLAN | `byop_PV` | **新增**；夜间出力为 0（结构测试已验证） |
| | 工期 / 寿命 | — | 2 / 沿用 PyPSA-USA | | | |
| 4h BESS（现场） | CAPEX / FOM | 公共侧 battery_4h：1500 / **32.50** | 1500 / **41.84** | SOURCE_FACT_PLAN | `byop_BESS` StorageUnit | **新增现场技术**；4 MWh/MW、η_rt 0.85、15 年、有 SOC；Firm 信用为 0 |
| 冗余系数 r（Firm 信用代理） | RICE / aero / SOFC | 1.25 / 1.25 / 1.10，**所有时段**出力都除以 r | 只在 B7 压力时段用 1/r；正常时段可用率为 1.0 | PROXY（TECH-01 base） | `np.where(smask, fm / r, av)`；`serve_cap` 用 `firm_frac / r` | **D2 修正**：正常调度与 Firm 信用分开 |
| 50SG RICE / 8h BESS / 大型 CCGT | — | TECH-01 中有 | 不开放 | — | 不在 `ML_TECHS` 中 | 保留为数据候选 |

> 公共侧候选机组（PyPSA-USA ATB 年金按社会贴现率重新年化，TECH-01 UTILITY 行的工期）**保持不变**。v1.3 §D2.a 要求：已有可信口径的公共机组参数，不得为了套用 BTM 表而被替换。

## 2. 燃气价格与热耗（D2.b）

| 字段 | 旧值 | v1.3 值 | 代码字段 |
|---|---|---|---|
| 燃气价格 USD/MMBtu（2025$，HHV） | `GAS = 3.19`，所有年份、所有机组相同（v240、v250、baseline 构建器） | WSC 发电用气价格：2026 **3.738**、2027 3.513、2028 3.576、2029 3.768、2030 **4.443**、2031 **4.857** | `CFG['gas_by_year']`（来自 `MAINLINE_V13_GAS_PRICES_2026_2031.csv`），`gas_price(p)` |
| 适用范围 | — | **全部燃气机组同一年同一价格**：现有机组、公共新建 CCGT/OCGT、复用机组、BYOP RICE/SOFC/aero | `ml_gas_delta()`：mc_t = mc(3.19) + HR × (gas_y − 3.19)，HR = 3412.14/η |
| 燃气可变成本 | 热耗/1000 × 3.19 + VOM | 热耗/1000 × gas_y + VOM（只算一次，不叠加输气费） | 例：RICE 2030 年 = 8.381 × 4.443 + 7 = 44.24 USD/MWh（`QA-COST` 测试） |
| 直接 CO₂ | TECH-01 `emission_t_MWh` 手工填写（RICE 0.44） | 从热耗推导：HR/1e6 × 53.06 t/MWh（RICE 0.445，SOFC 0.343，aero 0.501） | 模型中没有碳价约束；排放在结果报告中按同一燃气消耗推导，见 §5 |
| 现场燃气 MDQ | v1.0 场址 L0/L1/L2 | 各母线 `gas_evidence_level`：p610 2、p630 4 为 L1（250,000 MMBtu/日代理），其余 6 个为 L2（100,000 MMBtu/日，供气支线工期 3 年、100 USD/kW） | `SITES[s]['mdq']`，约束 `GAS-mdq_*` |

## 3. COD 与时间（D1）

| 资产 | 旧规则 | v1.3 规则 | 代码 |
|---|---|---|---|
| BYOP | COD = 2026 + 工期（固定决策年），按服务年份建变量 | 每个批准年 q 建一个变量，COD = q + max(技术工期, 供气支线工期)；COD 之前不能调度 | `add_byop_cohorts()`，`approval_cohorts()` |
| POI 升级 | COD = max(2026 + 工期, 程序日期)，所有建设期相同 | COD(q) = max(q + 工期, 程序日期) | `add_dc_poi` 中的 mainline 分支，名称 `POIup <bus> q<q>` |
| 公共发电与输电 | 首个建设期 = 2026 + 工期；第 p 期建设即该期全年可用 | 不变；等价于批准年 = p − 工期（公共侧工期都是整数年）；批准年写入台账 | `ml_public_candidates()` 中的 `approval_year` |
| 投运首年按比例可用 | 能量和 Firm 都按比例 | **能量**按比例；**Firm**（`serve_cap` 和 E0/U 设备）只计全年在运的容量 | `firm_frac()`，`CFG['firm_full_year']` |
| 已有 / 已批设备 vs 新建 | v1.0 每个场址一个 E0 | `GREAL_POI_E0_SCHEDULE.csv` 中逐行带日期的已有或已批设备（预批的不等 Batch Zero）；新建一律通过 U 或 BYOP 批准批次；可复用资产池为空 | `eq_terms()` |

## 4. 需求、POI、可复用机组

| 字段 | 旧值 | v1.3 值 | 代码 |
|---|---|---|---|
| 研究需求 | `POI_REQUESTS.csv`：3 个场址 × 程式化 1 GW | `MAINLINE_RESEARCH_COHORTS_TAMU64.csv`（mid）：8 个 Epoch 母线；2026 年扣除 460.73 MW 继承爬坡 | `configure_mainline()` |
| `regional_dc` | 可选的背景负荷 | 强制关闭 | `main()` |
| 竞争排队负荷 | G-K / G-U 下与研究需求等量 | 0 | `main()` |
| POI | `POI_REGISTER.csv`，3 个场址 | `GREAL_POI_ASSUMPTIONS.csv`：每个 Epoch 母线一个聚合 POI | |
| PCLR（Conditional） | 每个场址 500 MW；200 小时/年；单次最长 12 小时 | 2031 年研究设施 MW 的 30%；200 小时/年；单次最长 12 小时；优先在压力时段触发 | `pclr_cap`、`select_triggers` |
| 可复用机组 | ReEDS 按机龄推算的退役燃气机组 | 只用已核实资产池（空） | `reuse_pool_poi()` + `ML_RPOOL` |
| 现场风光上限 | — | 2031 年研究设施 MW 的 1.0 倍（每种技术）；与公共侧共享 ReEDS2 剩余潜力 | `ml_space()` |

## 5. 已知未改、需在审计中确认的项目

1. **燃料 CO₂**：模型没有排放约束，所以载体的 `co2_emissions` 不影响求解。v1.3 要求排放由燃气消耗推导，报告时按热耗 × 53.06 kg/MMBtu 计算。Stage A 没有改动载体排放系数，以避免影响旧的回归路径。
2. **工期是否仍"固定 2 年"**：参数基线 §2 指出 RICE "不可再固定 2 年"，但 v1.3 §D2.a 明确把 2 年作为研究代理起点。本实现按 v1.3 执行，并叠加供气支线工期、POI 程序日期等约束。
3. **Abilene 现场 aero 燃机（约 360 MW；数字来自第三方报告引用的许可文件，执行者没有核对许可原件）**：D11 不允许创造未证实的既有专属电源，因此没有作为"已订货 / 已有"BYOP 录入，列为 `REVIEW_REQUIRED`（决策日志 ML13-05）。
