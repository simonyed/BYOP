# BYOP 参数与证据统一基线（最终整合版 v1.0）

> **编制日期**：2026-10-20。**文档状态**：`CONSOLIDATED / IMPLEMENTATION SPECIFICATION / NOT AUTOMATICALLY MODEL-ADOPTED`。整合 v0.1–v0.4，并结合 2026-10-20 ERCOT County v2.5.0 进度审计。

## 0. 如何使用：这是一份唯一的参数规格书，不是已生效运行结果

1. **研究/建模决策**已冻结的部分（S0–S3、严格 S2 Speed-First、LP-only、2026–2050 时间线）按本文件执行；**数值参数**中仍有很多仅是“建议基准”，不得把“来源已核实”等同于“模型已采用”。
2. 下一位 Codex/Claude 应先读取真实仓库 `BYOP_ERCOT_County_v2.5.0` 中的 `tools_v250/v250_mech.py`、`work_package_v2/decisions/TECH-01_technologies_DRAFT.csv`、`model_settings/ERCOT_Model_Settings.md`，制作逐字段差异表，再提交有测试证据的修改；不要仅按本文标题“最终版”批量替换全部旧值。
3. **状态分两个正交轴**。证据：`SOURCE_FACT`（一手原始资料里的实际值）、`DERIVED`（有公式可重算）、`PROXY`（从其他工程移植）、`SCENARIO`（研究假设）、`UNKNOWN`（无证据）。代码：`IMPLEMENTED_TESTED` / `IMPLEMENTED_UNTESTED` / `PROPOSED` / `HOLD`。只可把源头事实标为“已证实”，不可自动标为“已实施”。
4. **成本口径**：`2025 USD`；`USD/kW_AC_net`、`USD/(kW_AC_net·yr)`、`USD/MWh_e`；燃气`USD_2025/MMBtu_HHV`；净发电 MW ≠ 机端 gross MW ≠ IT MW。新建 `CAPEX` 是真实发生的单次资源投资，不与全寿命资本年金重复计入。
5. 本文不是项目全生命周期实证数据的替代品。实际县级 firm 天然气余量、变电站/POI 送电能力、Aero/50SG/SOFC 同口径合同价格等，必须保留 `null` / `UNKNOWN` 并使用明确的敏感性情景。

### 0.1 四版合并与优先级

| 文档 | 被保留的独有成果 | 被后续证据替换或纠正的部分 |
|---|---|---|
| `v0.1` | 技术公平竞争原则、正常发电/容量信用解耦、Firm/Conditional Firm、N/R/C、资产残值、S0–S3 | SOFC 成本描述的 Table 3/4 区分、天然气 3.19 长期冻结、RICE/CCGT 证据不足 |
| `v0.2` | EIA 2026 全技术基准表、BESS 参数、LHV/HHV、WLPUN 流程、G−1 是概念而非统一法规 | RICE 仍暂用 8295/43/7 的“未校准中心”，后续 v0.3 得到 Liberty 净厂数据 |
| `v0.3` | Liberty 成本与 O&M、50SG 技术组、三座 CCGT 项目、被撤回 BESS、订单交付时序、Denton 和二手资产证据 | 当时长期气价仅方向性，后续 v0.4 补充 2025–2050 官方逐年价格 |
| `v0.4` | AEO2026 逐年气价、PUCT §25.194、Crusoe Longhorn 初审、Fermi 跨 RTO 对照、空气许可/气管资格 | 以本文件对齐 **P0-E v0.9 / v2.5.0** 的新证据和实际实施状态；v0.4 本身并未落实程序 |

**显式冲突处理**：

- `RICE 8295`（原值）→ 标准 50DF 的来源确认**8381**作为拟议工程设计锚；`8295`保留原模型复现与敏感性，`7507`只属 50SG 特定 LHV→HHV 机端推算。
- `RICE FOM 43 / VOM 7`（原 BTM 代理）与 Liberty `15 / 2.65`（公共电厂申报）**并存为不同成本边界**；不能挑低资本+低维护+高效率拼成不存在的完美机组。
- `CCGT 2000` 原建议在 v0.3 后变为项目全工程**2200 USD/kW 基准提案**，`2000`移为低档；EIA TRE `980`只用于结构对照。
- `SOFC $2650/kW`不是从 AEP `$2.65bn` 反推的可信造价；不可做主基准。`SOFC 0.5y`仅合资格的预采购快交付批次。
- `GAS $3.19/MMBtu`改为 AEO2026 WSC 逐年 2025 美元序列；旧值只保留复现实验。v0.1 对 2025 Texas `$3.06` 的简单热值换算，由 v0.3 使用 1.037 MMBtu/Mcf 更新为 **约 $3.03**，但不能替代 v0.4 WSC 全区域预测的 `2025 $3.295`。
- `N+1 冗余比 r=1.25`不能在所有时段令 `Dispatch ≤ K/r`；必须独立建立运行出力与故障后容量认证。
- 近县 GIS 管线、拟建规模、已批空气许可均**不能**自动生成可售的 firm MDQ、实际上电能力或 COD。

## 1. 不允许因参数更新而改变的研究架构

| 维度 | 冻结的决策与当前实际状态 |
|---|---|
| 比较情景 | `S0` 无增量 AIDC；`S1` Grid-only；`S2` 开发商 BYOP 与有限接网、严格 **最早可行服务优先→私人成本最小**；`S3` 相同物理可行域和信息条件下的社会协调成本最小；必须对比 `matched-service` |
| 分辨率 | 先 ERCOT **县级**真实拓扑，后本土 48 州且分区不跨州；早期 7 区只是回归/诊断，不得回退为论文主空间代表 |
| 近期求解器 | `PyPSA-USA` 与外部容量扩张/开发商 LP；用户上游保持 `RAMP-01 / WIND-01`，不能覆盖已验证修复；技术组合可 LP 外预筛/少量枚举，不引入整数电力规划主模型 |
| 时间 | 2026–2035 每年投资决策；2036–2050 **零新增 AIDC**，继续运行/退出/再利用/公共扩张，报告 2040/2045/2050；训练/推理比例及 PUE 2036 后继承 2035 |
| 负荷 | `MW_IT`×州/年 PUE→`MW_AC`，推理 wd/we 两类时段，训练日守恒可转移；避免容量/合同和购电结算里再次乘 PUE |
| 供电与资产 | 模式 `Grid-only / Grid-connected flexible / Islanded`；资源取得 `N`新建、`R1`延期退役、`R2`重启、`C`可交付专属合同/租赁彼此正交；`Bridge-to-grid`是跨年转换/租约退出，不另造第四类不兼容供电模型 |
| 私人/社会账 | S2 CAPEX、成本/合同现金流、接入担保机会成本；S3 真实资源成本＋外部性；保证金/转移支付非重复实体投资；分析寿命后出售、停机或跨系统复用的剩余价值 |
| 前瞻 | **3 年有限前瞻**（保留对未来需求的严格信息限制）；原论文文稿部分“五年”和按延期惩罚目标的文字不再作为主控制器指令 |

### 1.1 必须继承的最近一次“实际代码状态”（不是基线提案）

2026-10-20 `PROGRESS_REPORT_2026-10-20.md` 记录：`BYOP_ERCOT_County_v2.5.0` 已建立**185 个县母线、452 条县际走廊**；2025 县级基准 155.05 GW 机组与 488.23 TWh 负荷；既有 77.4GW 可再生机组时序丢失的 bug 已修复，旧 v1–v5 县级结果**已作废**。公共线路 G-R 限制在有 TPIT 项目记录的 111 条走廊，S2-SF 采用按年词典序 LP；`--gas-gate evidence` 与 `contract` 两种气源模式已写入 `tools_v250/v250_mech.py`。**但报告明确：TECH-01 的 RICE/SOFC 成本、工期、冗余系数尚未修改**。这里的“代码已写”不等于所有 v0.1–v0.4 参数修订已生效。

在 2026–2031、每年两个抽样周、Mid 负荷、`county_proxy_poi` 的筛查试验中，S1 已可按时满足四个 DC 县，S2/S3 均无 BYOP；**这是基线的真实诊断结果，不能通过人为关闭公共电网或刻意扭曲供货价“修复”成 BYOP 获胜**。下一步应优先寻找 POI/变电站层的真实限制和压力时段、做高需求压力测试。以上不构成长期论文结果已获现实校准。

## 2. 新建 N：统一参数主表

**表中价格为 2025 USD，净 AC。**“EIA”表示官方规划模型的参数，非当下 EPC 成交价；“主模型建议”仍需人工确认及代码差异审计。投资费用不要把公用工程、站点 BTM、供气支线/保费混在一个缺注解的列里。

| 技术/参数 ID | EIA AEO2026 对照（全国未调区；TRE 区） | 主模型建议/可用值 | 运维；HHV 净热耗；寿命 | COD/资格与证据等级 |
|---|---|---|---|---|
| `N-RICE-50DF` 标准新建发动机 | 2026 EIA 不单列新燃气 ICE | **BTM 2450 USD/kW** 暂保留 **PROXY**；Liberty 厂内净值 **2082**、含其输电工程 **2398** 仅为案例边界，均 **不能视为含新气管的现场交钥匙价** | 推荐分别比较 **FOM 15 / VOM 2.65**（Liberty 公共电厂申报）与**43 / 7**（原 BTM 保守）；净 HHV **8381** 拟用，**8295** 回归；寿命 25、30 两档 | **不可再固定 2 年**；订单+许可+气管+安装+调试；实际设备槽与本地资格；`PROXY/PROJECT_SOURCE` |
| `N-RICE-50SG` 高效大机 | 厂商 60Hz 机端约 50% LHV | **独立技术族**；同规格 complete EPC **UNKNOWN/null**，不得默认比标准 RICE 更便宜；如暂借 2450 则注明“同价研究假设” | 机端由 `7207 kJ/kWh_LHV` 且 LHV/HHV=0.91 推算约 **7507 Btu_HHV/kWh**；场址净值测 **7500/7800/8381**，不能把 7507 当净实测 | 德州 42 台/790MW：2026Q2 订单、2028 到货、**2029 年末计划 full COD**；`ORDERED≠COD` |
| `N-SOFC-STANDARD` | 10MW：**8287；7953**，3y | **7953 USD/kW** TRE 标准绿地起点，非 Bloom 成交价 | FOM **37.77**；VOM **0.72**；HHV **6469**；经济寿命 **15y**（电堆实际替换另核） | 标准参考 **3 年**，按项目实际路径门控；`EIA_ASSUMPTION` |
| `N-SOFC-FAST` | 与标准同物理化学技术，不独立增加厂商供给 | 需真实预购/已完成场址准备的 `fast_slot_MW`；实际 CAPEX、订金/快交付溢价 **UNKNOWN**，暂可借标准价仅做显式敏感性；`2650` 不可用于可信主情景 | 遵循该型号燃料与 O&M，考虑堆栈换新成本，**不把同一批 fast/standard 重复供应** | **0.25–0.5 年**仅 qualified preprocured；“55 天”只属于 Bloom–Oracle 一个成熟场址案例 |
| `N-AERO-35/50` 小型航改燃机 | 211MW 参考机群：**2275；2058**，2y | 开放 **LM2500XPRESS 35MW、PE6000 50MW** 设备组合；**2275**仅作规划代理，实际该模块 EPC **UNKNOWN** | EIA FOM **9.99**；VOM **5.97**；HHV **9447**；寿命约 30y 研究假设 | 两类确有厂家合同，非所有场址均有任意设备；分批供货、空气许可与气源筛选 |
| `N-OCGT-FRAME` 大型重型简循 | 419MW：**1158；1033**，2y | **仅 ≥实际可容纳设备包的合格大场址**做外部枚举/结构检验；1033 TRE 不代表 400MW 项目全套 BTM 交付价 | FOM **7.18**；VOM **4.17**；HHV **9142**；寿命须核同类合同 | 设备整机、gas/许可/电气筛选；不许把 419MW 随机拆成 3MW |
| `N-CCGT-LARGE` | 627MW：**1086；980**，3y | **2200 USD/kW 完整大型工程研究代理**；低 **2000**，高 **2500/2800**；由 KY/IN 三例 ~2144–2256 推断，**非 ERCOT BTM 成交价** | FOM **16.23**；VOM **3.49**；HHV **6226**；寿命约 30y | COD 中 **5y**，理想 **3y**，供货/许可以及大型土建压力 **7y**；须满足土地、水、气、电与最小模块 |
| `N-BESS-4H` | 150MW/4h：**1521；1500**，1y | 初轮 **1500 USD/kW, 4h**；Cane Run 未获批申请 **1938 USD/kW** 仅高价参照，不是已建工程 | FOM **41.84**、VOM **0**、往返效率 **0.85**、寿命 **15y** | 明确 `P_MW / E_MWh / SOC`；1y 为集中式参考，不能把 4h 自动当 24×7 firm |
| `N-PV-TRACKING` | 150MW：**1484；1342**，2y | 在合格土地/连接/小时出力下开放；**1342**仅集中式代理 | FOM **23.60**；VOM **0**；寿命/容量因子取 PyPSA-USA 项目级数据 | 太阳能逐时可用性与场址上限；不得用铭牌＝无条件 firm |
| `N-WIND-ONSHORE` | 200MW：**1712；1562**，3y | 在真实可利用风资源、地块和接入可行域下开放；**1562**仅集中式代理 | FOM **34.57**；VOM **0**；风廓线需继承修复后 County 时序 | 不能仅因为县内有风机就推断新 DC 所有本地风能可免费直连 |

### 2.1 两份真实成本证据必须保持原始范围

**Liberty Station 50DF，Kentucky PSC 2024-00310**：217.6MW gross / **214MW net**，总申请预算 **2024USD 500m** = **厂内 434.2m + 已列输电 65.8m**；因此 2024 年 USD/kW_net 为 2029 / 307 / 2336，按 CPI-U 2025/2024 = 321.943/313.689 作**一般物价调整**得 **2082 / 316 / 2398**。**新建供气支管未列入该总额**；不能把含输电的 2398 再按全额加一次公共线路升级。数据是 2024 申报、非竣工审计。[V01–V03]

**CCGT 项目工程案例**：Brown 12 645MW / $1.383bn ≈ **2144**；Mill Creek 6 645MW / $1.415bn ≈ **2194**；Cayuga 1476MW / $3.33bn ≈ **2256 USD/kW**。含部分气/电配套、分别有 net-summer 与 winter 额定口径，是选择 2200 作为工程研究代理的依据，而非保证所有 Texas 大机均该价。[V10–V12]

### 2.2 不得直接放入主参数表的误导性除法

- AEP SEC `$2.65bn` 对应“900MW option 的 substantial portion”，**未披露确切对应 MW**；`2650 USD/kW` 不是已证实 SOFC 价格。Cheyenne `$4bn/702MW≈5698 USD/kW` 仅是**整个项目（含计划碳捕集和其他工程）**比值，不是燃料电池 EPC；两笔披露不应相减构成真实成本分解。
- Cane Run `400MW/1600MWh/$775m` 是**已撤回的申请**，`1938 USD/kW`仅反映预计预算。
- ERCOT 15 台应急移动 aero `~$51m` 是一项期间**服务合同**，不是新机组设备 CAPEX；已有两座 768MW aero 电厂交易 `$768m` 是**二手资产成交价**，不是新建或通用残值系数。

## 3. GAS-01—03：燃气价格、热耗、可靠可交付性

### 3.1 逐年气价——替换单一 3.19，但并不制造真实站点报价

**首轮主参考：EIA AEO2026 Counterfactual Baseline Supplemental Table 3.7，West South Central 区（TX/OK/LA/AR）发电行业天然气购入价格，2025 年不变美元/MMBtu；**不是某个 ERCOT 县或开发商实际拿到的定价/firm gas 合同。第二列 Henry Hub 2025 real 用于替代路线，不能在 WSC 到站代理上再无证加普通 basis/variable distribution fee 而重复收费。2026–2050 是 EIA 预测，不是实签价格。[N01–N02]

| 年 | WSC ElectricPower：2025 USD/MMBtu（主） | Henry Hub：2025 USD/MMBtu（替代） |
|---:|---:|---:|
| 2025 | 3.295 | 3.467 |
| 2026 | **3.738** | 3.885 |
| 2027 | 3.513 | 3.620 |
| 2028 | 3.576 | 3.673 |
| 2029 | 3.768 | 3.843 |
| 2030 | **4.443** | 4.476 |
| 2031 | 4.857 | 4.853 |
| 2032 | 5.341 | 5.271 |
| 2033 | 5.265 | 5.235 |
| 2034 | 5.075 | 5.045 |
| 2035 | **5.082** | 5.049 |
| 2036 | 5.247 | 5.172 |
| 2037 | 5.365 | 5.276 |
| 2038 | 5.373 | 5.296 |
| 2039 | 5.386 | 5.310 |
| 2040 | **5.406** | 5.358 |
| 2041 | 5.421 | 5.378 |
| 2042 | 5.318 | 5.286 |
| 2043 | 5.179 | 5.141 |
| 2044 | 5.094 | 5.051 |
| 2045 | **5.035** | 4.997 |
| 2046 | 5.060 | 5.009 |
| 2047 | 4.958 | 4.898 |
| 2048 | 4.863 | 4.790 |
| 2049 | 4.770 | 4.697 |
| 2050 | **4.702** | 4.636 |

实现：单独输入 `gas_prices_2025usd.csv`（`year,scenario,region,price_2025usd_per_mmbtu,source_id,projection_vs_history`）；主 S2/S3 与 S0/S1 公共燃气设施均使用**同一**一致的气价曲线。2025/26/35/50 抽测数据重现本表；不允许一边使用名义 Henry Hub 另一边使用实际美元系统成本。若采用“Henry Hub + 站点基差 + 可变输送费”精细路径，必须以真实合同/开放价差数据证明，替换而**不是叠加在 WSC 主价格**之上；容量预约费、专属支管工程是额外不同成本项目。

**非首选/只能用于对照**：原代码固定 `3.19`；2025 Texas 发电行业历史平均 `$3.14/Mcf ÷ 1.037 MMBtu/Mcf ≈ $3.03/MMBtu`；EIA 2026-10 STEO 名义 HH 2026/27 `3.48/3.16`。各有地域、热值、价格基年和预测口径差异，不能无注释拼接时间序列。[V17–V20]

### 3.2 单位校验、价格与排放自动联动

设 `P_g` 单位 MW_AC_net，`HR_g` 是 Btu_HHV/kWh_AC_net：

```text
GasBurn_MMBtu_per_h = P_g_MW × HR_g_Btu_per_kWh / 1000
FuelCost_USD_per_MWhe = HR_g / 1000 × GasPrice_USD_per_MMBtu
DirectCO2_t_per_MWhe = HR_g / 1e6 × 53.06
  # EPA 53.06 kgCO2/MMBtu_HHV，仅直接 CO2，不含上游 methane

RICE 50DF: HR=8381 -> gas=8.381 MMBtu/MWh_e; CO2=0.4447 t/MWh_e
At WSC 2026 3.738: fuel=31.33 USD2025/MWh_e, plus VOM (separate)
At WSC 2035 5.082: fuel=42.60 USD2025/MWh_e, plus VOM (separate)
```

其他基准：SOFC `6469→0.343 t/MWh`、aero `9447→0.501`、CCGT `6226→0.330`；50SG `7507→0.398`是**机端理想气耗的有条件换算，不是同厂址实际净排放**。如采用机组 CO₂ 系数，必须从热耗实时派生，不得手工固定旧 `RICE 0.44` 导致热耗改了排放未变。风光/电池运营排放由充电能源/公共网排放继承；其制造生命周期排放另核，不能与直接烟囱 CO₂ 混为一项。

### 3.3 ERCOT County 可交付气源：数据层与两个气源情景

气源至少按以下**五个不同可验证字段**保存：

| 字段 | 必需证据；缺失时含义 | 能否直接提高 LP 的新建 firm 可发电容量？ |
|---|---|---|
| `gas_pipeline_geometry` | RRC GIS 有物理管线经过县/站点附近；`status_cd=I` 也可能是拟建 | **否** |
| `gas_tie_in_meter_ready_date` | 支管、计量表、降压与阀/压缩能力已完成/验收 | 单独不足 |
| `gas_plant_contract_right` | 具体持有人、供应/运输合同、有效起止日期与交割点 | 单独不足 |
| `firm_MDQ_MMBtu_per_day`（与小时/冬峰条件） | 明确到站**可新增签约**或已签 gas 量；共享走廊还需防多站双卖 | **需要**，但还要其他 gate |
| `gas_firm_delivery_ready_year` | 上述物理+合同权利同时成立且天然气可持续交付 | 合同和机组/环境/电气 gate 均成立后才可 |

**截至 P0-E v0.9**，Hill (48217)、Jones (48253)、Shackelford (48417)、Taylor (48441)、Wharton (48481) 的 `newly_contractable_firm_MDQ_MMBtu_day = null`，并非零。RRC 的 Abilene 2.0 `SYS_ID=691285`（24in / 拟14mi）、Abilene 3.0 `691286`（24in / 拟20.5mi）、BOLT `1200877`（24in / 2027-03-01 **计划**开工）及双 T4 证号 `05781/10370`可作为**资产级调查线索**，不是合同、首流、县级剩余容量。ABI-1 TCEQ 位置到三候选 GIS 线约 **0.7/1.8/2.2 km**，仅是未经完整 NAD27→WGS84 转换的定位检索近似，**不构成已接驳**。见 [P0E].

**当前 v2.5.0 已写入的两个情景**：

1. `--gas-gate evidence`：当新建 BYOP 缺少经过核实的 firm 输气权时，暂不将其视为已证的可交付选项。**这是一项“只认证有证据方案”的保守下界情景，绝不是断言这些县事实上没有天然气**；输出解释为 `DATA_NOT_VERIFIED`，不得记为物理能力 `0`。
2. `--gas-gate contract`：假定满足显式可签约情景的产能和工期，允许评估 speed-to-power 的潜在上界；必须另附 `contractability_fraction / pipeline_ready_year / firm_MDQ_scenario` 与成本并做敏感性，严禁在论文称为现实确证值。

**R1 既有厂延寿**不应被无条件跟随“新建 gas gate”关闭，但也**不能**因为历史上烧过气便推定未来可转售燃料权；检验原管线、供应合同转让/保供与公共系统容量权利归属。依县内有无已运行燃气机组作粗筛，**只能是弱代理**：没有机组不证明不能接气；有机组不证明还可新增 MDQ。

若存在经核实的共同气源走廊 `a`，LP 用 `Σ_{s∈a,g∈gas} GasBurn_s,g,t ≤ AvailableFirmFuel_a,t` 限制共享资源；站点逐日 MDQ 约束应为相应 24h 能量总和，并额外验证小时峰值、压力与极寒保供，不能仅把每日总量平均为任何小时都可用。**同一合同 MDQ 不得同时被两个数据中心/公用电厂重复预留。**

## 4. COD-01/02、供应槽位与环境许可——速度的真实工程来源

### 4.1 时间状态从“一个固定建设年数”变为项目证据事件链

```text
site_eligible(s, tech, y)
  = land_readiness AND equipment_slot AND air_authorization
    AND (gas_delivery_firm_ready if gas tech)
    AND electrical/POI_eligibility AND commissioning/safety qualification

earliest_legal_COD = earliest time when all prerequisites in the
  site-specific precedence DAG are complete.
  For independent parallel branches this is max(branch completion times);
  sequential predecessors must be scheduled, not all reduced to one max.

capacity_available(s,tech,y,t) <= purchased_cohort_capacity ×
     externally_verified_COD_availability_mask(y,t)
```

**一次采购仅有设备交货年份时不可判 COD**。支持分批调试、不同月送电、分期负荷上线；年度平均 `first_year_fraction` 只可用于能量与时段一致的近似，**不可作为无证的 firm 可靠容量认证**。

**一手工期锚**：Texas 42×50SG / 790MW 订单 2026Q2→2028 设备→2029 末计划 full COD；另 15×50SG / 282MW 2026Q3→2028 设备→2029 计划 full COD；Bloom–Oracle “55天”是准备成熟的一个现场部署例子；Brown 12 / Mill Creek 6 计划 2030/31 全厂 COD；Fermi 曾撤回/修订 2026 年底 1.1GW 初期预期。这些证明“供应槽位/许可/系统完工”多路径，却**不能**用个别事件拟合全国可统计的工期概率分布。见 [V05、V07、V16、V11、N04]。

供应分组字段：`supplier`、`equipment_family`、`order_cohort`、`reserved_MW`、`delivery_window`、`earliest_commissioning_date`、`site_power_ready`、`site_gas_ready`、`owner_and_transferability`。若缺 `slot_MW`，设 `null` 并只做 `0/limited/expanded` 透明情景；不能据厂家全球 backlog 推算特定 ERCOT 县的精确可交付 MW。

### 4.2 环境许可：已批、待批、运行分层

| ERCOT 内真实场址 | 最重要的许可事实 | 程序用法 |
|---|---|---|
| **Shackelford County ABI-1 / VoltaGrid**，`RN112247101` | **2025-07-17 最终许可 180842**：原计划 210 台、**709MW**、审查最多 197 台同时运行；新 `182467/PSDTX1692/GHGPSDTX266` **2026-09-18 为初步草案**，提出**同一站点总量 620 台、约 2582MW**，拟获终批后取代原许可。TCEQ 2026-09-18 记载该时点之前基线实际排放为零、尚未运行。[P0E] | `709 + 2582` 是重复计数；许可不能自动变成 COD 或 firm gas，草案不可当终批。两阶段以 `RN + permit_event_date` 去重 |
| **Taylor County Crusoe Longhorn** | 原阶段 **10 台/约 360.5MW** 2025 许可修订；扩大申请 `182126/PSDTX1688/GHGPSDTX263` 描述 **39 台/约 1330MW** 航改燃机（12 DT35、27 LM2500）；截至已有来源为初步/待核最终文件；申请中 NOx 530.85 **short tons/yr**、CO₂e 6,780,838.61 **short tons/yr** 是**排放潜势 PTE**，不是测量。[N03/P0E] | 厂址/版本分离；最高申报与最终批准/运营状态不互推；PTE 可作有证据的排放上限，运行排放由热耗调度计算 |
| **Carson County Fermi Matador** | 位于 **SPS/SPP，非 ERCOT**；2026-02-25 最终获约6GW气电空气许可；另5GW是后续申请；声称最高有条件 300,000MMBtu/day 气协议、7台移动 TM2500 在站址额定约132MW、计划200MW SPS 并网；完整 COD 未证。[N04–N05] | **仅跨 RTO 结构校验**，不得训练 ERCOT County 取气余量；`6GW permitted`不等于发电、气源或 POI 现货可用 |

**环境 LP 约束**：先在 LP 外按确切 `air_status`、合法装机、有效起止日期筛候选；LP 内对各污染物计算 `Σ_t emissions_pollutant ≤ permit_limit`（确保 **short ton → metric tonne** 严格换算），并按具体排污许可证而不是设备铭牌处理 `run_hours / emergency_only`。天然气 SOFC 不等于零 CO₂/零许可；NOx、噪声、耗水和社区压力应通过场址资格/真实成本/敏感性评估，而非笼统“SOFC 保证更快获批”。

**政策事件**：v0.4 记录 Texas 2026-09-21 州长要求 TCEQ 暂停某些数据中心许可签发至 ERCOT 审查完成。[N08] 该执行/解冻日**需持续核查**。`AIR_POLICY_PAUSE` 与 `AIR_POLICY_STANDARD` 分别作状态情景；不得把时间性行政指示外推为至 2050 年永久不批、也不能反向撤销此前已合法获批的许可。

## 5. FCF-01 / REG-01：正常出力、可靠容量与 ERCOT 接网责任

### 5.1 五种容量不能再被一个 `r` 或“网内净余量”代替

| 对象 | 严格物理/经济含义 | 正确约束 |
|---|---|---|
| `K_nameplate` 与 `K_net` | 设备铭牌与净 AC 额定；须辨 Gross/Net、温度降额 | `0 ≤ Dispatch_g,t ≤ K_net_g × availability_g,t`，正常出力不一律除以 1.25 |
| `CertifiedFirmCredit` | 设备事故后/保证交付资格，不等于当时正常调度上限 | LP 外已审的 G−1 设备组可 `K_survivable = Σ K_qualified − max(K_one_unit)`；储能须有 SOC/持续时长，天然气须有 firm delivery |
| `POI_ImportEligibility` | 站点实际获批/物理可进口上限，随完工/法律生效 | `grid_import_firm_t + grid_import_conditional_t ≤ POI_qualified_MW_t`，不能以 county 热力输电走廊容量替代站级 POI |
| `FirmContractMW` | 已付费/有资格的稳态取电权利，须有公共充裕度支持 | 联合 FCF 认证，扣减系统容量可用余量；公共可靠容量和同一 BYOP 信用不可双计 |
| `ConditionalFirmMW` | 条件触发可限制的进口 MW；不是“没有系统服务费的无限 firm” | 每个 T/G 触发场景下检验进口+自备+储能+允许中断负荷可服务 |

**G−1 是场址可靠性研究情景，而不是已发布的所有 ERCOT BYOP 一律 `r=1.25` 规范。** 例如 5×250MW 为了最坏损失一台可保 1000MW，比例 1.25；13×50MW 可保 600MW，比为 650/600≈1.083。两者在正常未故障时可以按调度各自出力至净可用上限。若 `r=0.95` 被定义为“冗余比”，应停止该无物理含义命名，转换为透明的 `firm_credit_scenario`。

对 `Conditional Firm`：研究定义应包含可触发的输电/发电紧张事件（T/G）、年度可中断 **MWh、小时、次数、最长连续小时**。数量/最大连续小时一般非凸，**不得在纯 LP 中虚构精确地实现**；可先用固定事件模式外部枚举与 LP 内能量/小时预算，求解后作数量与连续长度审计并剔除不合格方案。报告须明确哪些约束严格求解、哪些事后认证。

**必要的联合 FCF 单元测试**：同一公共机组售给 C 合同后其公共 ERM 容量信用扣减；同一 BYOP 设备同时供本站并向公共侧售电时权利总和不超标；同一公共电网 firm 进口不再被 Conditional Firm 无中断地重复使用；Islanded 的电压/频率控制、黑启动和事故保护在 LP 外资格审核，不能以结果 `grid_import=0` 自动视为真正离网可行。

### 5.2 ERCOT 2026 新大型负荷规则：必须分财务与物理账

根据 **2026-10-02 Texas Register 最终 adopted 16 TAC §25.194（2026-10-08 生效）**，ERCOT 合格新建/扩容大负荷主要以**单站总请求 ≥75MW** 及指定增容门槛触发；准确例外与旧项目过渡须依正文逐站检查，不能以 PNNL 统计点简单代表一个合法“site”。[N06]

| 输入/规则 | 已核证的官方量级（按适用条款） | 会计与优化含义 |
|---|---|---|
| `large_load_threshold_MW` | **75MW** 主门槛；另有扩增/豁免细则 | 仅作用于需要 ERCOT 并网审查的负荷项目；不得无差别套在完全离网站点 |
| `study_fee_usd2026` | **$100,000/适用项目**，未使用部分可返还 | S2 是支付/返还现金流；S3 仅实际使用的研究工作构成社会资源成本 |
| `intermediate_security_usd2026_per_MW_requested` | **$50,000 × 新增请求进口 MW**；2032 起周期调整 | **担保/信用占用**，不是不可退 `CAPEX`；私人只计担保费/资金机会成本、可能损失 |
| `significant_equipment_lead` | **18 个月或以上**长交期工程定义 | 后续担保与实际订购设备/服务风险衔接，按适用流程 |
| `CIAC_direct_connection_cost` | 直接连接工程建设分摊，**不可退** | 电气实体工程成本/产权和付费方分别建账；S3 不与 PyPSA grid CAPEX 双计 |
| `withdrawal_security_forfeit_rule` | 某些阶段退出可扣**20%** 等规则 | 根据触发条件与已承诺额度计算，**非任何延期都必损 20%** |
| `return_timing` | 送电、负荷履约里程碑后的分段返还 | S2 时间化流动性占用；禁止当作永久额外投资 |

代码中至少分别保留：

```text
requested_import_MW != studied_import_MW != certified_import_MW != energized_import_MW
private_cash_initial = refundable_security + nonrefundable_direct_CIAC + study_fee_paid
private_economic_cost = actual_study_resource_cost + financing_fee_on_security
                      + nonrefundable_direct_CIAC + conditional_forfeiture + ...
social_resource_cost  = physical_connection_build + real_study_work + ...
                      # no refundable escrow principal, no pure transfer double count
```

**注意**：大负荷信息征询（ERCOT 2026 Data Center Impact RFI）曾采用 **25MW** 信息收集门槛，**并非 §25.194 的 75MW 接入许可门槛**。[N07] §25.194 的费用规则**不能自动创造任何可用进口 MW**。

## 6. R/C/资产寿命：容量权利、再利用与搁浅风险

### 6.1 R1/R2 机组池的资格与“主基准”

原模型把 p63/p64/p65 由年龄推导的约 **4.0GW** ERCOT 燃气机组视为“可延寿池”，其 R1 一次性改造 **50/150/400 USD/kW**，维持性 CAPEX **10/15/25 USD/kW·年**，FOM **25/35/50 USD/kW·年**，延寿 **10y**、工期 **1y（高档 2y）**。这些均为**未核证的研究情景假设**；不得在缺机组状态、合同/产权、环境及燃气权利证据时当作真实可供开发商直接买入 4GW firm。[v0.1 §4，DEC-08、DEC-21]

**执行分层**：

1. `R1_existing_operating_extension`：已有机组尚在公共侧发电，是否可延迟退役？核 PlantID/GenID、ERCOT ResourceID、县、实际/计划退役时间、净可靠容量、所持气合同、交易资格。将容量转为 DC 专供，公共 `ERM` 同步扣减；区分“退休前重分配权利”和“原退休年后新增延寿期”。
2. `R2_retired_restart`：已经退役，检修重启、许可和关键装备差别大；**参数默认 null / 逐项目核验**，不能套用 R1 的 1y、150 USD/kW。
3. 没有证据时**关闭在“已核实可获得的主供给”范围**，但可作为明确的 `R1_4GW_stylized` 敏感性做机制检验。v2.5.0 暂从 DC 所在县内取可退休的燃气机组，是**严格空间过滤**，并不替代真实法律取得权核验。

所需底表：EIA-860/860M/923、ERCOT 发电机对照、资产产权/合同、已签退役或修复许可、可得气/电连接。Crane/TMI-1 重启属于专门核电案例，不能据其规模与资本费反推德州天然气机组平均重启成本。

### 6.2 C_qualified、临时租赁与跨年模式

合格合同的最小字段：`contract_id, source_asset_id, owner, physical_delivery_point, qualified_MW, COD, service_hours, firm/interruptible, end_year, capacity_fee, energy_fee, fuel_included, transferability, public_credit_reduction`。无本地送电与 firm import 权利的**财务型远程 PPA**可影响经济交易，却不得自动为 Islanded 或 POI 提供 24×7 可靠 MW。

资产产权和服务权分离：

| 路径 | 可以具有的资产/服务状态 | 防错重点 |
|---|---|---|
| `N` 新建 | 开发商所有、第三方持有但长期交付、分期安装 | 不得把拿到厂家订单当成资产投运 |
| `R` 复用 | 已有公共机组转专供、延寿、已退役重启 | 公私可用容量权利求和受原设备真实净容量限制 |
| `C` 合同/租赁 | `mobile_leased`、长协燃料电池服务、现有公用厂 firm 购电合同 | 合同费不是完整机组 CAPEX；租赁结束设备归属及可回收权属有别 |
| 模式转换 | `Islanded→Grid-connected flexible`、临时离网租赁撤出（Bridge-to-grid） | 需要真实 POI 建设/接网年，不因时间过去自动授予 firm 进口 |

### 6.3 LIFE-01：真实资本一次入账、到 2050 留残值

`private_discount_rate=7%`、`social_discount_rate=2%` 为原设研究假设，**须做相同折现率敏感性**，避免仅因折现差异得出 S2/S3 社会效率分歧。按年份处理：真实 CAPEX 在发生年支付；之后逐年 FOM、VOM、燃料费、合同费用、必要的 SOFC stack/BESS augmentation 等；可因租约退出、二手出售、获准并入公用系统再利用等终止或转换。投资不可逆不意味着设备必须盲目运行到 2050。

推荐在终点计算 `ResidualValue_2050` 但需区别：

- 已建成、有产权、可合法转让/继续使用的净可回收价值；
- 老化折旧后的剩余经济寿命和未来再利用所需新气/电连接、拆装/搬迁/许可成本；
- 已签但未建成设备订单的取消成本/不可退预付款，不等于拥有一台可交易的发电机；
- 2035 年后无**新 AIDC 需求增量**，不是已建负荷强制归零；可能形成超建或资产过剩须由调度、价格和退出决策**内生**决定。

`S2/S3` 统一保留公共电网扩建、燃料、电气改造的实体资源账；私人主体的租赁付款/网络收费与社会系统对应实体资产只计一次。可以先以 `reuse_fraction=0 / central / upper` 作外显研究情景，**不可把 768MW 二手 aero 每 kW 交易价机械当所有资产 salvage rate**。

## 7. 最小连续优化接口与两个目标的检验

### 7.1 LP 的物理集合

方案组合资格和真实模块台数由外部技术清单/少量合法方案枚举；给定合法组合 `k` 后，LP 用连续建设容量、调度、SOC、进口合同与公共扩建决策：

```text
For each scenario q in {S1,S2,S3}:
  load_AC(t) = IT_service_MW(t) × PUE(t)
  grid_import(t) + onsite_generation(t) + battery_discharge(t)
     = load_AC(t) + battery_charge(t) + net_export(t) + losses(t)
  dispatch_g(t) ≤ COD_active_g(t) × availability_g(t) × K_net_g
  gas_burn_g(t) = dispatch_g(t) × HR_g / 1000
  sum_shared_gas_use(t) ≤ certified_firm_gas_access(t)  [if evidenced]
  grid_import(t) ≤ certified_POI_right(t)
  conditional_interrupt_and_reserve_checks(t)
  battery_SOC(t) = SOC(t-1) + η_charge*charge(t) - discharge(t)/η_discharge
  public_ERM_and_joint_FCF_rights_no_double_allocation
```

若 `UNKNOWN` 的气/POI 实况使约束无法定标，**明确两个/多个条件可行域**，而非偷偷从公式去掉限制并称现实县级最优。

### 7.2 S2 / S3 的先后逻辑

**S2-SF 主目标（字典序）**：

1. 按年份优先最大化**按期实际可交付**的 IT 服务；冻结上一层最优交付集合（带严格数值容差及一致分期定义），不可用一个可任意调的“延迟罚价”替代。
2. 在相同最早服务结果中，最小化开发商真实私人折现成本（含资本、运维、合同、融资占用和适用监管支付）。若要研究选择偏好随 speed premium 改变的边界，另做 `S2-v` 对照，不混进主 S2。

**S3 主目标**：在和 S2 同一技术候选、可得设备槽、gas/air/POI、预见年限与服务资格下，最小化真实社会贴现成本及可说明的环境外部性；不得为 S3 额外赠送无限公共输电或免费现场气管。若 S3 选择的服务量与 S2 不同，需报告原始福利结果与**相同 IT 服务量**的 `S3_mS2` / matched-service 结果。对尚无足够证据的污染损害单价，以 `0/LOW/HIGH` 透明情景测试，而非冒充法定碳税。

**M1–M4 分析不变量**：M1 运营最早可用时间/实际交付 IT；M2 公共电力容量/线路与私有项目在空间和时序的替代或补充；M3 2035 以后停运/资产再用/2050 残值；M4 私人与社会目标的同物理机会集差异。**如果 S1 在现有诊断下零延迟，则这是可发表的模型边界信息，不能靠错误惩罚修造速度收益。**

## 8. 给 Codex/Claude 的逐项程序修改工作包（以 v2.5.0 为起点）

**总原则**：先只读、逐字段 diff、冻结旧可复现基准，再最小修复物理错误，再开展技术/价格的可控 A/B。保留原代码与用户变更，不执行破坏性重置。本文中 `proposed` 的字段名是**期望接口**，不是声称实际文件已有这些列。

| 优先级 | 任务 / 在真实代码中定位的入口 | 要改什么；建议交付 | 完成定义 |
|---|---|---|---|
| **P0-A** | `tools_v250/v250_mech.py`、`TECH-01_technologies_DRAFT.csv`、`ERCOT_Model_Settings.md`、`DECISION_LOG.md` | 逐项追踪参数 `RICE capex/FOM/VOM/heat`、SOFC fast、aero switch、CCGT、`r`、气价、POI、S2、残值，输出 `CODE_PARAMETER_CROSSWALK.md`：文档值→当前代码值→变量→目标/约束→当前实施状态/测试 | 在读取实际代码后列明“未修改的字段”；不能按本文推定代码现值 |
| **P0-B** | 从 `tools_v250/v250_mech.py` 的 `r/firm` 相关限制入手 | 正常调度容量和事故容量信用彻底分开；修复 `K/r` 常规出力误限；修正 IT×PUE 重乘和 `first_year_fraction` | 5×250 与 13×50 手算测试、正常出力可达额定、事故后保护负荷不超能力 |
| **P0-C** | `--gas-gate evidence/contract` 现存逻辑；P0E/P0F 表 | **保留已实施双闸门**；外加 `missing/zero/verified` 语义和 MDQ/合同/日气量共用约束；若数据不足在结果中显式打印 `CONTRACTABILITY_ASSUMPTION`，完成 `GAS_CONSTRAINT_AUDIT.md` | 所有未知 gas MDQ 仍为 null；0 仅由明示真实证据或情景选择产生；相邻 GIS 不导出无限供应 |
| **P0-D** | 保留现有 v2.5.0 S2-SF | 核对逐年词典序是否真正按已可交付服务排序；确认 S2 与 S3 可行域完全相同、同给三年前瞻，不因 gas-gate 情景不同混比；`S2-v` 只作敏感性 | 顺序 LP 最优值冻结、迟到负荷排序、matched-service 与私人/社会成本全部可重算 |
| **P1-A** | 新建 `parameters/`、`evidence/` 层（具体目录按仓库实际结构） | 做**唯一** `TECH-01_technologies_VERIFIED_DRAFT.csv`，含 §2 技术的原始参考、主模型代理、低高场景、source/status/price_basis、unit/gross_net；先保留旧运行配置并单独加 `scenario=legacy_tech` | 输出数据 schema；热耗、FOM、VOM、年化成本逐列校验，未证的 50SG EPC/null 不被默认变零 |
| **P1-B** | 新建 `data/derived/gas_prices_2025usd.csv` | 从 EIA **源 XLSX**重抽 2025–2050，并保留源 URL、Excel 工作表、行号、提取脚本与 SHA；按 §3 主参考/替代气价双列读取 | 26 年完整；2026/2030/2035/2050 主价 3.738/4.443/5.082/4.702；恢复旧 3.19 的单独对照运行 |
| **P1-C** | `COD / equipment cohorts` 工程接口 | 将 `2y_RICE / .5y_SOFC_fast / 2y_Aero` 固定普适 COD 替为按源证明的 order cohort、EPC/气网/空气/电气关键路径和分期 COD；外部非法设备包先筛除 | 2026 订 790MW/282MW 50SG 机组不允许 2028 全厂自动投运；55 天仅 fast-ready；无 gas rights 不可获 firm |
| **P1-D** | `BESS / PV / WIND` BYOP 新组合 | 将 4h BESS 的 `P_MW/E_MWh/SOC/RTE` 全部联立；加入当地 wind/PV 小时曲线、土地与连接容量；仅合资格可计 firm 信用 | 4h 电池不能放出第5小时额定电；充电电量与系统排放不双计；保持旧 WIND-01 时序修复 |
| **P1-E** | 合格 N/R/C、合同与资产状态 | R1 逐机组核验，R2 单独存空；加入 `C_qualified`、移动租赁及跨年模式转换，防公共机组被重复卖 firm；投资按真实年度 CAPEX 与 2050 残值计算 | 产权/容量权利双列、公共 ERM 扣减；不同类型成本不串表、不重复资本年金 |
| **P2-A** | ERCOT `§25.194` 接入责任 | 2026 规则触发门槛、study fee、可退 security、CIAC、退出费用及资金成本分别建账；保留政策版本与适用站点 | 对 100/500MW 请求安全保证金分别 5/25m；社会实体 CAPEX 不因单独“押金”而变化 |
| **P2-B** | `air/permitting` | 真实项目状态机：`APPLICATION / PRELIMINARY / APPROVED / INSTALLED / OPERATING`，版本替代，许可证污染物限额与年度运营时间；旧新项目去重 | ABI-1 **709 与 2582 不加和**，Longhorn 1330 pending 不自动运行；short tons 精确换算 |
| **P2-C** | `run / report / archive` | 同需求/同公共电网/同价格做 S0–S3 与分层 2×2/2×2×2 消融；输出 `PARAMETER_CHANGELOG.csv`、`ERCOT_TECH_SENSITIVITY_AUDIT.md`、完整源清单与测试日志 | 每个算例能指出参数版本、gas gate、COD 资格、POI、技术候选集、LP 状态、目标/交付/公共扩张、2050 资产余额 |

**执行顺序解释**：P0-A 到 P0-D 是**物理正确性与已有实现回归**；P1-A 到 P1-E 是**证据/技术/寿命基线落地**；P2 才是监管细账与研究情景出图。若修完 P0 后 S1 仍零延迟，先完成 P2-C 中的**站级 POI 瓶颈/压力负荷诊断**，而不是仅通过更改 EIA 成本使 RICE 获利。

### 8.1 参数表最小机器可读字段（不得省略元数据）

```yaml
schema_version: BYOP_EVIDENCE_BASELINE_v1.0_2026-10-20
model_target: BYOP_ERCOT_County_v2.5.0
price_basis: real_USD_2025
electric_capacity_basis: kW_AC_net
fuel_energy_basis: MMBtu_HHV
source_fact_does_not_imply_model_adopted: true
parameter_record_required_fields:
  - parameter_id
  - technology
  - parameter_name
  - numeric_value_or_null
  - physical_unit
  - geography_and_project_scale
  - price_year_and_included_scope
  - evidence_class            # SOURCE_FACT/DERIVED/PROXY/SCENARIO/UNKNOWN
  - source_id_and_url
  - project_status            # PERMIT/ORDER/INSTALLED/OPERATING etc.
  - model_scenario            # baseline/sensitivity/legacy/hold
  - code_path_and_variable
  - code_change_status       # IMPLEMENTED_TESTED/PROPOSED/HOLD
  - review_approval_status
  - retrieval_or_decision_date
example_records:
  rice_standard_50DF_capex_btm:
    numeric_value_or_null: 2450
    evidence_class: PROXY
    model_scenario: proposed_baseline
    project_status: NOT_AN_ACTUAL_EPC_QUOTE
  rice_high_eff_50SG_capex:
    numeric_value_or_null: null
    evidence_class: UNKNOWN
    model_scenario: hold_until_calibrated
  SOFC_standard_TRE_capex:
    numeric_value_or_null: 7953
    evidence_class: SOURCE_FACT
    model_scenario: proposed_reference
    source_id_and_url: E01
  free_firm_gas_MDQ_county:
    numeric_value_or_null: null
    evidence_class: UNKNOWN
    model_scenario: evidence_gate_or_contractability_sensitivity
  s2_speed_first:
    code_change_status: IMPLEMENTED_TESTED   # 已有进度报告表明 S2-SF 求解成功；须复检当前仓库
```

### 8.2 代码审计关键口径

- **缺失数值管理**：若数据 schema 中 `null` 代表未知，禁止以 `fillna(0)` 写成真实不可行/免费建设；同时不能 `fillna(infinity)` 让无限燃气、无限可预购 SOFC 成为隐含主参数。
- **购电费与工程费**：FIRM/CONDITIONAL 的服务价格如为研究影子容量价须写 `MODEL_PRICE`，不可写成真实 ERCOT 统一电价。新增气管/变压器公共实体投资和开发商付款不要双记社会资源。
- **采购规模**：LP 外合法机组包才可进入 LP。不能让 35MW aero 以 `0.14` 台实际投运；此约束允许离散方案**小集合外部枚举**，不要求改变 LP-only 主体。
- **资料核证等级**：项目 `APPROVED`、`CONTRACTED`、`IN_SERVICE` 由各自来源证明；许可批复、订单或工程计划从不自动生成能源系统可调度 MW。
- **现有源码保护**：检查并保留 PyPSA-USA upstream 以外的 `RAMP-01/WIND-01/WIND-01-C`；县级 77.4GW 时序失真 v1–v5 作废，不能再用于校准投资参数。

## 9. 强制 QA／回归测试与拒绝交付条件

以下测试应在简单手算小例子通过后逐步进入 ERCOT County。测试失败，**不能**把参数版本升级为“已通过”：

| QA ID | 最小输入/操作 | 必须结果 |
|---|---|---|
| `QA-01` | 比较 2025/2035 统一币值、净 MW / IT MW | 成本未混入名义价；`IT×PUE`只做一次；所有费用标明设备/BTM/POI/气线口径 |
| `QA-02` | 5 台×250MW，1000MW 受保护负荷，失去1台 | 事故认证1000MW；正常无故障总出力可在可用条件下达1250MW |
| `QA-03` | 13台×50MW，最坏失一台 | G−1认证600MW，比例≈1.083；`r=1.25`不作为无根据固定规范 |
| `QA-04` | 4h BESS，P=1MW/E=4MWh，完全放电后 | 无可再输出的“第5小时”1MW；RTE=0.85，SOC 守恒 |
| `QA-05` | 燃气净机组1MW、HR=8381，燃气价3.738 | 每小时8.381MMBtu、燃料成本31.33USD/MWh、直接CO₂ 0.445t/MWh |
| `QA-06` | WSC 26 年气价文件 | 无缺年、值非负、2026/2030/2035/2050=3.738/4.443/5.082/4.702 |
| `QA-07` | 选气源`null`、无证、无 RRC 交付点 | 报`UNKNOWN/DATA_NOT_VERIFIED`；evidence 情景关闭资格但**不写物理供给0**；contract 输出敏感性标签 |
| `QA-08` | RRC GIS 管线穿过县 + 计划 BOLT 2027 开工 | 不得自动获得 gas ready/首流/firm MDQ，不能让 pipeline `STATUS I`变 2026 合同 |
| `QA-09` | 同一 firm MDQ 被两个站点申请 | 共享约束阻止一份 gas rights 被消费两次，日/小时需求转换量纲一致 |
| `QA-10` | SOFC standard vs fast，无 fast slot | fast=0 资格，standard 仍候选；有预留时总量不得双算同一供应配额 |
| `QA-11` | 下单到货2028、现场2029联调的 RICE 50SG | 2028 不能生成“全厂已可运营”MW；如分期则只有文据允许的阶段有效 |
| `QA-12` | ABI-1旧批709MW，新申请总量2582MW未终批 | 不生成3291MW；未经实际 COD/firm 气权不得变可调度出力 |
| `QA-13` | Longhorn TCEQ 1330MW preliminary，Fermi 6GW许可 | 前者未终批、后者**非 ERCOT**；均不因许可/跨州公告进入 ERCOT 可用机组 |
| `QA-14` | ERCOT 请求进口100MW/500MW，规则适用 | 起始担保分别5m/25m，**只改变私人资金占用**而不创造 MW/社会实体 CAPEX |
| `QA-15` | 公共机组1GW，先公共 ERM 后有 200MW 合格专供合同 | 公共/专属权利合计 ≤1GW；公共系统对应可靠容量扣减 |
| `QA-16` | S2-SF 两个成本不同的合法路径 | 先选更早交付；在同一早 COD 集合中选私人成本更低；不同 S2-v 不改变主选择逻辑 |
| `QA-17` | S2/S3 的 gas/POI/COD/设备/信息参数导出哈希 | **同一物理候选集合**，仅目标和真实经济主体费用不同；matched service 单独核算 |
| `QA-18` | 已发生 CAPEX 及 2050 出售/剩余寿命 | 总资本只计一次，抵减合理净残值；不重复加全寿命年金，不把“2050截止”当全损 |
| `QA-19` | 县级 PyPSA-USA 2025 基准构网 | **185县、452走廊**与真实项目当前归档一致；既有风/光小时出力曲线全部保留，不能回归作废 v1–v5 |
| `QA-20` | 2026–2031 Mid、两个抽样周、同样 POI 的回归 | 当前 S1 零延迟、S2无BYOP 应可在相同冻结参数复现；更动后的差异须说明哪一个参数/物理约束导致 |

**验收否决项**：未经来源支持给每县统一 gas 供气上限；把 `SOFC $2650`、`R1 4GW`、`709+2582MW`、`gas GIS line length→firm MDQ`、`$50k/MW security→CAPEX`、`K/r→所有小时的发电上限` 任一项设为无注释基准；用抽样周“零延迟”或“BYOP=0”单独宣称论文机制被证实/证伪。

## 10. 决策汇总与下一轮人工确认点

下表是**截至 2026-10-20 的状态登记**。`SOURCE_VERIFIED` 只表示原始资料数值存在；需要用户正式同意、源代码通过测试，才能从 `PROPOSED` 改为`MODEL_ADOPTED`。

| 原版 ID / 主题 | 统一最终处理 | 源资料状态 | 代码/决策状态 |
|---|---|---|---|
| `DEC-01/02` SOFC 基准 | TRE 7953、EIA 标准3y；fast 0.25–0.5y 限已锁设备槽 | 官方 EIA 事实已核；fast 项目个例 | **数值 PROPOSED**，实际技术原值在 v2.5.0 未更改 |
| `DEC-03` 重型简循 | 419MW/1033 TRE 仅大站点资格的诊断技术 | EIA 事实确认 | **SCREENED_ONLY**，不无上限加入县级连续可任意拆分供给 |
| `DEC-04/11/12/13/14` RICE | Liberty 50DF：2082厂内/2398含输电；8381 HHV、15/2.65 低运营档；BTM 2450+43/7 暂代理；50SG 单独标未知 EPC | 申报和厂家资料已核；BTM 移植未核 | **PROPOSED**，先检查代码中当前 `8295` 与旧运营值 |
| `DEC-05/16` BESS | 4h、1500TRE、85%、15y、FOM41.84；1938 仅撤回方案敏感性 | EIA/NREL 有据，真实 BTM 溢价未知 | **PROPOSED**，先修 SOC 与功率/能量 |
| `DEC-06/17` SOFC 快速/低价 | `2650` **HOLD**；55天只个例，不能所有大型项目绿地速建 | SEC 无对应 MW，快部署事实为项目限定 | **HOLD** low cost，fast 能力严格限额 |
| `DEC-07 / CAP / FLEX` | 取消正常出力 `K/r`；分开 POI、Firm、Conditional、G−1、Joint FCF | ERCOT 规则和厂商设计有源，但部分服务是研究产品 | **PRIORITY DESIGN FIX**，不得以法规名义强加 r |
| `DEC-08` R1 4GW 延寿池 | 原参数单列研究假设；主供给需要真实 PlantID/GenID/权利核证 | 4GW 未验证 | **HOLD AS FACTUAL SUPPLY**，可做情景 |
| `DEC-09 / GAS-02` | 县级 firm gas MDQ 无资料保持 null；不可由气管/机组历史推算 | P0E 空缺已确认 | **双 gas gate 已在 v2.5.0 部分实现**；继续质量控制 |
| `DEC-10/18` Aero | 35/50MW 实际订单存在，主技术候选公平开放；项目 EPC 未证 | OEM 订货已证，真实站点单价未知 | **PROPOSED CANDIDATE**，须同真实气/许可/设备组约束 |
| `DEC-15` CCGT | 2200 完整大型工程代理，2000/2500/2800 敏感性；COD 3/5/7 年受证据门控 | 3 个公共项目预算已证；对 ERCOT BTM 外推是代理 | **PROPOSED** |
| `DEC-19 / GAS-01` | AEO2026 WSC 2025USD 逐年主轨迹、Henry Hub 替代；不得双加输气价差 | **26 年源序列已有原稿提取** | **PROPOSED NOT YET COPIED TO LIVE CODE** |
| `DEC-20` Direct CO₂ | HHV gas burn×EPA 53.06 自动计算 | 可重算 | **DESIGN FIX/TEST** |
| `DEC-21 / LIFE` | 25/30y RICE 研究寿命、S2/S3 不同折现率、真实资本加终值 | Liberty 30y 经济分析已证，残值未证 | **PROPOSED**；2050 残值不可删 |
| `DEC-22 / R/C` | 移动租赁、公共资产合同与开发商资产产权分开 | Denton/Life Cycle/Fermi 真实结构 | **PROPOSED**，不使用“拥有发电机”简写合约权利 |
| `REG-01` | ERCOT §25.194 75MW/100k/50k每MW（细则按最终文本），担保≠EPC | 2026 终规则已核 | **PROPOSED** |
| `ENV-01` | 许可状态/排放潜势与实际运行分开；ABI-1 版本互斥 | TCEQ 原件已核 | **部分数据 QA 已实现；LP 限额待实现** |
| `S2-SF / COUNTY-GRID` | 严格按年交付优先、县级网络，保留现有 bug 修复 | 2026-10-20 运行报告有 LP optimal | **IMPLEMENTED_TESTED (受报告覆盖范围限制)** |

**需用户决定的仅是“从研究代理变成正式主基准”**：

1. `TECH-P1`：首轮保持 RICE BTM 2450，但标准50DF热耗改8381，O&M 同时跑 15/2.65 与43/7 两档；是否接受作为竞争基准/双档？推荐 **接受双档，不将 Liberty 低运营费机械移植为唯一 DC 情景**。
2. `TECH-P2`：CCGT 完整工程代理基准 2200，并以 EIA 980 下界做对照；推荐 **接受有资格场址的 2200 基准**。
3. `TECH-P3`：SOFC standard 使用 7953/3y，fast 只限真实预采购条件，2650 不入主基准；推荐 **接受**。
4. `DATA-P1`：逐年 WSC 气价替代长期 3.19 作为研究中心；推荐 **接受，但与公开燃气合同替代报价严格区别**。
5. `GAS-P1`：论文重点展示“有证据 firm 情景下界 / 可签约情景上界”，不要让 evidence 缺数据的结果被写成“当地气源为零”；推荐 **双轨共报**。
6. `MODEL-P1`：如果零延迟基准持续，优先改善真实 POI/申请队列/变电站瓶颈的证据或做明示压力情景，而不靠故意拉长公共工期；推荐 **接受**。

## 11. 一手证据索引（核心可复核链接）

本目录只列影响本最终版的**核心一手来源**。原 v0.1 的 S01–S19、v0.2 的 E01–E13、v0.3 的 V01–V23、v0.4 的 N01–N08 完整表仍归档，文中标签沿用原编号。下列项目公告证明“订购/计划”而非“实际 COD/成交 EPC”。

| 本文标签 | 官方/原始资料 | 主要支持的字段 |
|---|---|---|
| `E01` | [EIA AEO2026 Electricity Market Module Assumptions Table 3/4](https://www.eia.gov/outlooks/aeo/assumptions/pdf/EMM_Assumptions.pdf) | SOFC、OCGT、CCGT、BESS、PV、风电、TRE/全国成本、工期、热耗与 O&M |
| `E08` | [NREL 2024 ATB – Utility Scale Battery](https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage) | BESS 85% RTE、15y、运维/电池衰减口径 |
| `V01` | [Kentucky PSC EKPC Liberty Scoping Report, Case 2024-00310](https://psc.ky.gov/pscecf/2024-00310/allyson%40hloky.com/09202024100053/Attachment_BY_-_1_%28To_be_filed_Redacted%29.pdf) | 500m 预算、供气支线不包含在厂/输电投资 |
| `V02` | [Kentucky PSC EKPC 正式 Data Response 2024-12](https://psc.ky.gov/pscecf/2024-00310/jessica.fitch-snedegar%40ekpc.coop/12062024065538/Mountain_Assocation_-_to_be_filed-bhk-ah.pdf) | 434.2+65.8、214MW net/217.6 gross、8381HHV、15/2.65、30y |
| `V03` | [BLS CPI-U 年均指数](https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm) | 2024/25 321.943/313.689，一般消费价换算，**非 EPC 指数** |
| `V05` | [Wärtsilä 2026-04 Texas 790MW/42×50SG](https://news.cision.com/wartsila-corporation/r/wartsila-continues-to-expand-its-data-center-footprint-with-new-790-mw-order-in-texas--the-next-data%2Cc4340470) | 下单2026、到货2028、计划全 COD 2029 |
| `V06` | [Wärtsilä 50SG 官方技术单页](https://www.wartsila.com/docs/default-source/energy-docs/technology-products/product-leaflets/wartsila-50sg.pdf) | 机端LHV 50%、7207kJ/kWh |
| `V07` | [Wärtsilä 2026-10 282MW/15×50SG](https://www.wartsila.com/sau/media/news/05-10-2026-wartsila-to-supply-282-mw-onsite-power-solution-for-a-u-s-data-center-as-ai-growth-intensifies-demand-for-reliable-power-3797450) | 设备槽、设备交付≠全场COD |
| `V09` | [GE Vernova–Crusoe LM2500XPRESS 29 台采购](https://www.gevernova.com/news/press-releases/ge-vernova-crusoe-announce-major-29-unit-aeroderivative-gas-turbine-deliver-ai-data-centers) | Aero 项目不是纸面选项；无成交全工程报价 |
| `V09a` | [PROENERGY–Crusoe 13×50MW PE6000](https://www.proenergyservices.com/2026/04/proenergy-to-deliver-major-generating-equipment-to-power-crusoe-ai-factories/) | 650MW 设备供货合同 |
| `V10` | [Indiana OUCC Cayuga CPCN](https://www.in.gov/oucc/electric/key-cases-by-utility/duke-energy-rates/cayuga-generating-station-cpcn) | 1476MW/$3.33bn 大型 CCGT 预算 |
| `V11` | [KY PSC Brown12 / MillCreek6 / CaneRun 联合申请](https://psc.ky.gov/pscecf/2025-00045/rick.lovekamp%40lge-ku.com/02282025010202/04-KU_LGE_Joint_Application_2025-00045.pdf) | CCGT 两座造价及 BESS 原申请预算 |
| `V12` | [LG&E/KU 2025-10 监管批准公告](https://investors.pplweb.com/2025-10-30-LG-E-and-KU-receive-approval-on-plans-to-meet-Kentuckys-growing-energy-needs) | CCGT 获批、Cane Run BESS **撤回** |
| `V14` | [City of Denton – Denton Energy Center](https://www.cityofdenton.com/335/Denton-Energy-Center-DEC) | 市有 225MW/12 发动机，2018 真正投运 |
| `V15` | [City of Denton–Core Scientific 2024 PPA/土地变更](https://www.cityofdenton.com/m/newsflash/Archive/Item/922?arcId=1599) | DC 计划2027 与公共网改造2029 不同步、所有权 |
| `V16` | [Bloom–Oracle 2026 合作公告](https://www.bloomenergy.com/news/bloom-energy-and-oracle-expand-strategic-partnership-to-deploy-up-to-2-8-gw-to-accelerate-ai-infrastructure-build-out/) | 55 天个案、1.2GW 已签、最高2.8GW 框架 |
| `V17` | [EIA Texas 发电用天然气历史购买价格](https://www.eia.gov/dnav/ng/hist/n3045tx3A.htm) | 2025 Texas 3.14 USD/Mcf，非新 DC 县合同 |
| `V18` | [EIA 天然气热值 FAQ](https://www.eia.gov/tools/Faqs/faq.php?id=45&t=5) | 2025 1.037 MMBtu/Mcf |
| `V21` | [ERCOT Life Cycle Power 应急机组合同公告](https://www.ercot.com/services/comm/mkt_notices/M-A060525-01) | 移动航改租赁/应急服务非新 EPC |
| `V23` | [EPA 天然气固定燃烧排放因子指南](https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=P101AWWT.TXT) | 53.06 kg CO₂/MMBtu HHV |
| `N01` | [EIA AEO2026 Table 13 XLSX](https://www.eia.gov/outlooks/aeo/excel/aeotab13.xlsx) | Henry Hub 2025 real 与 nominal 两个不同列 |
| `N02` | [EIA AEO2026 Supplemental Table 3.7 XLSX](https://www.eia.gov/outlooks/aeo/supplement/excel/suptab_3.7.xlsx) | **WSC 发电行业天然气价 2025–2050** |
| `N03` | [TCEQ Crusoe Longhorn 182126 初步决定摘要](https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_APD_SEARCH_GET_FILE&searchType=External&xAPDParent=8588007) | Taylor County、39 台/~1330MW 初审与 PTE |
| `N04` | [Fermi Form 10-K, US SEC 2026](https://www.sec.gov/Archives/edgar/data/2071778/000207177826000010/frmi-20251231.htm) | 非 ERCOT 的真实气网/移动租赁/POI 和规划变更 |
| `N06` | [Texas Register 2026-10-02，adopted §25.194](https://www.sos.state.tx.us/texreg/archive/October22026/Adopted%20Rules/16.ECONOMIC%20REGULATION.html) | 大负荷 75MW/100k/50k每MW/18个月/CIAC/退出责任 |
| `N07` | [ERCOT Data Center Impact RFI](https://www.ercot.com/about/legal/data-center-impact-rfi) | 25MW 是信息征询门槛 |
| `N08` | [Texas Governor 2026-09-21 TCEQ 函](https://gov.texas.gov/uploads/files/press/TCEQ_Data_Center.pdf) | 特定时期审批暂停要求，解冻进度需更新 |
| `P0E` | [TCEQ ABI-1 180842 正式批准函](https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_EXTERNAL_SEARCH_GET_FILE&Rendition=Web&dID=8983110)；[182467 初审替代总量](https://records.tceq.texas.gov/cs/idcplg?IdcService=TCEQ_APD_SEARCH_GET_FILE&searchType=External&xAPDParent=8647042)；[RRC T4 历史检索](https://www.rrc.texas.gov/pipeline-safety/permitting-and-mapping/permitting/how-to-search-for-t-4-permits/) | ABI-1 709已批/2582待批、不代表COD；GIS/T4证据与 firm gas 合同不同 |

## 12. 交付给下一位执行者的输出规范

下一阶段必须交回同一批次报告，保证本会话能审计“哪些是真做了、哪些仍是建议”：

1. `BYOP_PARAMETER_IMPLEMENTATION_REPORT.md`：逐个 DEC/参数的 **原值→最终采用值→技术/地点/年份→实际代码路径和行/函数→来源→测试结果→是否受用户批准**。
2. `TECH-01_technologies_VERIFIED_DRAFT.csv` 和 `gas_prices_2025usd.csv`；若获得真实气管/许可表，分成 `gas_contract_evidence.csv`、`site_permit_history.csv`，一律保留 `status/null/source_date`。
3. `CODE_PARAMETER_CROSSWALK.md` 和 `SCENARIO_INPUT_MANIFEST.json`：每个情景的脚本/配置、源文件 SHA-256、价格基年、物理 gate、S2 主目标、网架冻结版本。
4. `QA_TEST_REPORT.md`：第 9 节每个测试 `PASS/FAIL/NOT_RUN`，外加 LP 求解状态、目标差异、是否由非真实压力情景导致。
5. `ERCOT_TECH_SENSITIVITY_AUDIT.md`：S0–S3 和 matched-service，燃气 evidence/contract 两档，技术全开/fast 限额/aero 关闭诊断，以及 site POI 与更高需求的真实/假设区分。
6. `CONTROLLER_FINAL_WORK_REPORT.md` 和一个可重现的返回压缩包：包括更新后的本最终版 Markdown、代码 diff、上述数据、测试与未关闭问题；详细说明哪些大文件仍在用户本地仓库，不能假称整个 PyPSA-USA 数据集已被打包。

**最终移交结论**：现阶段最重要的“参数修订”不是改小 SOFC CAPEX 或强行增大 RICE 份额，而是确立**同口径技术参数 + 真实 COD/气源/POI 资格 + 公私社会成本不重计**的一致模型。v0.1–v0.4 的事实证据足以提供一个透明的初轮参数基线，但**不足以证明某个 ERCOT 县能够获得多少新增 firm 天然气或者某个数据中心真的可在某年 COD**。这两项必须在后续实证与敏感性中分开报告，才可能对 Nature Energy 的速度—路径依赖机制形成可信推断。

---

### 整合版本履历

| 版本 | 时间 | 主要贡献 | 当前作用 |
|---|---|---|---|
| v0.1 | 2026-10-19 | 原模型 N/R/F/C 的物理与会计审计 | 被本文件合并；不直接做代码指导 |
| v0.2 | 2026-10-19 | EIA 2026 原表、HHV/LHV、BESS、ERCOT WLPUN | 数值及来源在本文件保留 |
| v0.3 | 2026-10-19 | Liberty/CCGT/电源供应合同、RICE 校准、Denton | 以项目实例限定边界 |
| v0.4 | 2026-10-19 | 气价全轨迹、§25.194、Taylor/Fermi 与环保 | 后续新证据和当前实施状态以本文件更正 |
| **FINAL v1.0** | **2026-10-20** | **统一唯一参数台账、证据等级、实施差异、LP 物理接口、ERCOT County gas gate、测试/移交标准** | **指导后续代码修改的主 Markdown**；所有未批准数值仍按 PROPOSED 处理 |

