# BYOP ERCOT：六技术参数定标及 LP 实施工作包 v2.0

**日期** 2026-10-22；**GitHub 基点** `simonyed/BYOP`, branch `mainline-v13-stageA`, commit `d0a9bf85523b9630a0a6e811ec024653cd26c5ec`。  
**必须执行在：** 已派发的 **Epoch+PNNL 多母线空间分配**正式落地并通过其静态验收之后；新的 **2025 ERCOT 官方锚定校准**正式大规模重跑之前。  
**授权：**仅允许参数文件集成、代码修改、隔离单元测试与非优化器静态审计。**正式 ERCOT S0/S1/S2/S3、B4、全国算例与官方历史基线改变均**未授权**。如需 Gurobi 小规模 LP 测试，执行方先准备 DRY 命令/验收计划、报告给研究者，再请求单次授权。

## A. 执行原则与交付边界

研究者已完成公开资料核查、技术参数取值、许可地理分区规则及设备供货代理额度设计。**不要求执行方继续搜索成本、施工工期、法规或供货市场资料，不允许以“缺乏数据”为由留下空参数或自行随意填写。**所有数值优先从本包 `BYOP_TECH_PARAMETER_BASELINE_V2.json`、`BYOP_TECH_PARAMETERS_V2.csv`、`BYOP_SUPPLY_POOL_PROXY_V2.csv`、`BYOP_COUNTY_OZONE_RULES_2026.csv` 读取。除代码实在无法访问的原始多年份气象 H5 文件之外，外部采集不是本工作包的工作内容。

保留三类证据层级：`OBSERVED`（厂商产品或官方规则中直接观测）、`INFERRED`（从其数值进行透明计算）、`RESEARCH_PROXY`（现实证据约束下的可执行基准数值）。本包没有声称研究代理是 ERCOT 已批复的采购容量、TCEQ 许可结果或者厂商个别订单报价。研究目的不是强制同时出现六种技术，而是让技术的**可交付性、可靠供电资格与长期成本**具备不同且合理的竞争条件。

### 与前后工作包的接口

1. 先验收并冻结新增母线输入（约 17 母线），包括新的 `GREAL_POI_ASSUMPTIONS`、逐年 IT 需求与动态 M4 服务量键集合；不允许沿用 `N_KEYS=48`、`len(SITES)==8` 等旧假设。
2. **2025 Epoch 存量、460.73 MW IT 继承负荷、既有公共电网设备和 S0CAL 原结果不动**；多母线后 2026–2035 low/mid/high 年总 IT 容量不动。
3. 本包新增独立技术参数版本，旧 v1.3 读取路径与已归档 B3-E 全部结果保持可复现；禁止覆盖旧 `MAINLINE_V13_TECH_DEFAULTS.csv` 原文件。
4. 新官方锚定校准继续独立处理 2025 基线、2026 ERM 与 S0CAL。新技术集不能在历史基准校准期间私自改变固定历史机组。
5. 不改动开发商 **Speed-First 再成本最小化**的目标顺序。S2 开发商与 S3 社会规划者的候选技术、物理资格、许可、制造池一致；区别仅在私人/社会目标和供电权限的已批准设置。

## B. 技术定量基准（全部 2025 年实值美元、净交流铭牌、未净扣税收抵免）

| 技术 `carrier` | CAPEX $/kW 基准 [下–上] | FOM $/kW·y | VOM $/MWh | HHV Btu/kWh | 采购至设备到场 y | 到场后安装调试 y | 年金寿命 y | `r` | 可靠性资格 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `RICE` | **2200** [1995–2750] | 43 | 7.00 | 8381 | **1.00** | **0.50** | 25 | 1.25 | 可调度 Firm，设备和燃气及许可限制 |
| `OCGT_aero` | **2550** [2275–3200] | 20 | 5.97 | 9447 | **1.50** | **0.50** | 30 | 1.25 | 可调度 Firm，同上 |
| `SOFC_NG` | **3900** [3200–5000] | **125** | 0.72 | 6469 | **0.75** | **0.25** | 15 | 1.10 | 可调度 Firm，同上 |
| `WIND` | 1562 [1408–1712] | 34.57 | 0 | — | 1.75 | 0.75 | 30 | N/A | 仅经风光储组合压力窗口认证 |
| `PV` | 1342 [1193–1484] | 23.60 | 0 | — | 0.75 | 0.50 | 30 | N/A | 同上 |
| `BESS` | 1500 [1451–1775] | 41.84 | 0 | — | 0.50 | 0.25 | 15 | N/A | 4 小时、往返效率 0.85、需 SOC 认证 |

**源与推断界限：**

- RICE 与 aero 的 *热耗率/VOM/寿命* 沿用原始 GitHub 技术台账，并非随意更改。RICE 基准 EPC 2200 较原 2450 降约 10%，为小型模块化设备的**可比工程范围内研究取值**；aero 2550 较原 2275 升约 12%，代表当前 OEM 排单与交付紧张后的**全包工程溢价代理**，不是设备商已公开的平均报价。GE 2026Q2 公开燃机订单/保留槽位合计 116 GW，但不等于航改燃机全部订单：`S08`。
- SOFC **$3900/kW** 是依据 2026 年商业资讯对完整项目约 $3000–4000/kW 的估算，并适当包含安装、场址平衡设备的高端基准；AEP 2026 年 $2.65bn 采购合同并非经核验的同口径 ERCOT installed CAPEX，因此仅用于交叉判断而不直接用 `2.65bn / 1GW` 替代。资料 `S04,S05`。**$125/kW·y** 是含运维服务及未来电堆更换准备金的**研究代理**，不得再与独立 stack replacement 年金重复收费；相较旧 $37.77/kW·y 的财务规划值，合理反映完整服务合同可能更贵但并非厂商公开报价。
- 2026 Bloom `Energy Server 6.5` 325kW 模块，天然气 12–18 psig，HHV 5811–7127 Btu/kWh，无正常工况水消耗，噪声 <65dBA@3m；选择处于合理范围的原模型 HHV 6469。其 SOFC 数据表给出 NOx **0.001 kg/MWh**、CO **0.005 kg/MWh**、VOC **0.004 kg/MWh**、CO2 308–378 kg/MWh；`S01`。设备快部署案例 **55 天**为 Oracle 特定已具备条件项目，不能误写为从零下单总工期 `S02`。
- RICE 常见模组约 4–20MW；aero 约 30–60MW；前者单机技术性最小稳定负荷约 10%、后者约 40%，型号和厂商资料的可行范围，不可直接作为整座多机机组的硬性 LP 下限 `S06,S07`。这两个模块规模仅用于**后验可施工性检查**，避免让 LP 的连续容量变量被错误解释为可以购买 0.0001 台机组。
- 按 7% 私人 WACC：年固定成本 RICE **$231.78/kW·y**、aero **$225.50/kW·y**，差约 $6.28；2028 年气价 $3.576/MMBtu 时 RICE 燃料加 VOM 比 aero 低约 $2.78/MWh。两者在参考条件下满负荷小时分界约 **2,260 h/y（~26% CF）**，至少不再被无条件固定成本支配；**这是数值筛查，不代表两个技术在实际 COD、许可、排放和规模上都相同**。
- SOFC 年固定成本约 **$553.2/kW·y**，高于 aero；2028 年天然气条件下边际发电成本约 $23.85/MWh，低于 aero 的约 $39.75/MWh。因此它是**快交付但固定服务费用较高**的真实竞争性路线，不是廉价万能电源。
- WIND/PV/BESS 暂保留现行 capex 和 FOM。没有项目专属建设成本资料时，不能用 ReEDS 全区 resource potential 当作直接可开工项目。

### COD 必须按并行里程碑计算

对于订货年 `q`、母线 `s`、技术 `k`、路径 `p`：

```
equipment_ready = q + equipment_delivery_lead[k,p]
site_civil_ready = q + civil_electrical_lead[s,k,p]
construction_released = max(q, permit_must_exist_before_construction[s,k,p])
installation_done = max(equipment_ready, site_civil_ready, construction_released) + install_commission_lead[k,p]
COD = max(installation_done, gas_ready_year[s,k,p],
          final_permit_approval_year[s,k,p], electrical_safety_ready_year[s,k,p])
```

若本地设计不区分初步许可与终局许可，则只能使用更保守的一条统一许可关键路径，不可通过错误的 `max(q+equipment, q+permit)` 假设一切项目建设自动和最终许可完全重叠。后续许可工期具体值详见参数 JSON。

**2025 年末已经存在的合同**：当前没有研究数据中心可核实的预留 SOFC/aero/RICE 设备槽位，因此 `verified_preordered_research_MW=0`；不要允许优化器在 2026 年后“倒签”2025 合同。SOFC `RESERVED_FAST` 路径不删代码，但基准额度 **0 MW**；可对确有证明的未来项目再解锁。新订单 `STANDARD` 按以上参考到货时长。

**年内 Firm**：旧模型 `firm_full_year=True` 意味着 2027.25 投运只在 2028 年取得全年 Firm 认证。本包**暂不擅自把部分年度输出算作 2027 整年 IT 服务**；必须输出 `equipment_ready`, `permit_ready`, `gas_ready`, `COD_real`, `first_full_firm_year`，并将有限的年内提前收益留待季度/年度服务审计。

## C. TCEQ 许可与场址环境：给定配置和规则

### C1. 具体县及法律事实

- `BYOP_COUNTY_OZONE_RULES_2026.csv` 已给出 TCEQ 官方列示的 DFW（9 县 2015 标准；10 县 2008 标准）、Houston-Galveston-Brazoria（6/8 县）、Bexar（2015）FIPS。模型使用真实 PNNL/Epoch 设施 FIPS 映射县 **不能拿 TAMU bus 的平均坐标替代实际所在县**；不在表中的县只可暂按 `ATTAINMENT_OR_UNCLASSIFIED` 的建模类别，不能宣称其所有污染物都达到正式认证。`S11,S12,S13`。
- **TCEQ 2025 年新天然气 EGU Standard Permit**：只对满足全部条件的**管道天然气火花点火式内燃机**可能适用；**不适用于燃机**。特别是代码名 `RICE_50DF` 可能对应双燃料概念，**没有核实发动机是管道天然气 Spark-Ignition 之前，不允许自动授予此许可资格**。许可的排放限制与是否构成 major source 须依项目判断 `S09,S10`。
- SOFC 当地污染物极低，并不自动免除德州建设许可。下表只是用于 LP 早期研究的**差异化审批风险年限代理**，非 TCEQ 承诺的审查时限；其确切代码应注明 `PERMIT_LEAD_PROXY`。

| 技术 | 其他/一般县许可时间 y | 2015/2008 臭氧不达标县时间 y | 真实许可适用限制 |
|---|---:|---:|---|
| SOFC | **0.40** | **0.60** | 污染物很低；不推定免许可 |
| RICE | **0.75** | **1.25** | 新 NG-EGU 简化途径仅对合法合格天然气 SI engines 可用 |
| aero | **1.00** | **1.75** | turbines 不能使用上述 2025 纯天然气 engine permit，按更保守构造路径 |
| WIND | 0.75 | 0.75 | 非空气许可主导；为场址/环境与施工许可时间代理 |
| PV | 0.40 | 0.40 | 场址环境/土地许可代理 |
| BESS | 0.35 | 0.35 | 消防安全及场址许可代理 |

尚无现场地址/县映射的母线使用 `UNKNOWN_CONSERVATIVE`，**不是 0 许可时间**。有效 `COD` 还受设备交期、天然气接入和电气工程制约；这些估计值**不应附加到公共电网 POI 法定并网日期**。

### C2. 能直接计算的排放参数

| 技术 | CO₂ t/MWh（HHV 天然气 × 53.06 kg/MMBtu） | NOx kg/MWh（供模型试验） | 证据/适用限定 |
|---|---:|---:|---|
| SOFC | **0.3433** | **0.001** | CO₂ 由 6469 Btu/kWh 计算；NOx 源于 Bloom 2026 设备数据表 |
| RICE | **0.4447** | 无后处理 **0.70 代理**；采用 SCR 的项目路径 **0.0675 代理** | NOx 值非州通行认证限额；SCR 仅在加计 CAPEX $150/kW、FOM $5/kW·y 时使用 |
| aero | **0.5013** | 干式低 NOx **0.424**（EPA AP-42 lean premix 推导）；另设 SCR **0.085 代理** | 使用 SCR 时加计 CAPEX $200/kW、FOM $4/kW·y，具体厂商控制技术需工程复核 |

计算示例 `NOx_aero = 0.099 lb/MMBtu × 9.447 MMBtu/MWh × 0.453592 kg/lb = 0.424 kg/MWh`。NOx 的本次取值仅用于方向性比较和 `PTE` 筛查，**不等于 TCEQ 认可的具体场址 PTE**；CO₂ 必须记入社会成本后处理，但不得无依据自动施加统一碳税。`S01,S16,S18`。

新增 `permit_path`：`DEFAULT_ENV` 与 `CONTROLLED_ENV`；`CONTROLLED_ENV` 容许更低 NOx 但必须支付额外成本，且在现场排放控制预算和供应资格中单独验收。**站点合并**的潜在最大年排放用 `Σ_tech [K_tech × 8760 × NOx_kg/MWh] / 907.185` 估算美制短吨/年，筛查规则和真实重大排放源法律门槛必须分离；不能让模型通过把同一场址拆成多个 permit_path 来逃避总量限制。

对不同许可路径给定的可选容量和 COD 必须在优化之前判定合法资格。**不得用非线性阈值或互斥条件伪装成 LP。** 无实际工程数据时，只使用上述固定代理路径，报告它是政策代理机制，不声称已取得许可证。

## D. 设备制造供货池：明确基准额度（单位 MW净AC/交付年）

厂商报告的全球产能或积压不等于分给 ERCOT 研究母线的剩余槽位。因此本包不假装知道真实市场可用量，但给出**有限且可复算的基准研究采购池**；执行方无需重新做供应商调查。

| 年度交付 | RICE | aero | SOFC |
|---:|---:|---:|---:|
| 2026 | 250 | 200 | 75 |
| 2027 | 300 | 225 | 150 |
| 2028 | 375 | 250 | 225 |
| 2029 | 450 | 300 | 300 |
| 2030 | 525 | 350 | 375 |
| 2031 | 600 | 400 | 450 |

上述数值全部标注 `RESEARCH_PROXY_NOT_VERIFIED_SPARE_OEM_CAPACITY`。建议核心配置不添加对 wind/PV/BESS 假设的全国供应上限，保留现有 ReEDS 母线潜力、现场占地和工期。供应池的主要价值是对三类快速天然气/燃料电池设备同时进行排队约束。Bloom 2026 SEC 所称 2 GW/年扩产是**企业全球工厂目标**，GE 116 GW 是**整个燃机产品 backlog+slot agreements**，均不可作本表的官方容量 `S03,S08`。

低/高供货可取基准 ×0.5 / ×2.0，仅作为后续要求的单因素机制验证，**本次不授权任何扩展求解**。检查跨母线、跨采购路径、跨下单年的总交付不超过同技术同年上限；S2 开发商容量承诺在公共 S2 LP 中是同一份设备，不得双倍占用制造池；不同 S0/S1/S2/S3 是互斥反事实而非需要消耗同一个现实生产库存的同时发生的世界。

合同预订：仅在 2026 年起的企业决策中预订未来槽位，并将定金与取消成本计入私人目标/资产账本。考虑 LP 的线性性，初版 `reserved_existing_MW=0`、`new_reservation_path=DISABLED`，标准年度交付池已足以体现有限采购；保留接口，但**不要假装有 2025 已预订的 SOFC 或 aero 容量**。若执行方发现现有模型没有供应池，可以直接实现 `Σ K[s,k,q,delivery_year=y] <= pool[k,y]`，不引入整数变量。

## E. 风光储：ReEDS 数据与连续压力窗口 Firm 认证

现有 `REEDS2_TO_TAMU64.csv` / `ERCOT_WIND_SOLAR_POTENTIAL.csv` 已从 `D:\ReEDS2` commit `eb75a6bc...` 构建风光资源点/县/母线聚合。`ReEDS2_IMPORT_NOTE.md` 记录原始 CF H5 在本地约 9.0+5.9 GB，仓库不含原始 H5。**执行方的任务是实现读取/映射代码，不是去收集或校核新的商业数据。**

### E1. 先保证资料与单位正确

- ReEDS 风光潜力母线映射、县重叠避免双重计算与原始 `sc_point_gid` 对应关系全部沿用现有 `build_reeds2_potential.py`；不能用一个按 ERCOT 总量平均的 CF 取代局部站点 CF。
- 若执行环境可访问本地只读 H5，直接读取并降维缓存 **每个候选母线×气象年×小时** 的加权 CF；以 `src_sha256, county_fips, resource_category, weather_year, bus, timezone, nameplate_AC, PV_ILR=1.34` 等元数据确保可重现。**不得向执行方要求重新下载 15GB 的数据才允许实现技术模块**；如果 H5 不在运行环境，先使用已经进入 PyPSA-USA 的同一基准气象年风光曲线及其压力窗口完成代码实现，状态标 `REEDS_MULTIWX_PENDING_LOCAL_H5`，而非断言已完成 ReEDS 多年验证。
- ReEDS 每个 PV 容量因子须先核对 H5 具体 DC/AC 的原始定义，不能无条件乘 1.34。

### E2. 可靠性认证 LP

将单一机组固定 `NONFIRM_BYOP={'WIND','PV','BESS'}` 改为：风光储**不单独宣称 Firm**，但其经过 SOC 的**组合应急可供电量**可以计入年度服务资格。设 `F[s,y]` 为经过认证的**组合稳定电力 MW**：

```
0 <= W_t <= CF_wind(s,t,weather)*Kwind
0 <= P_t <= CF_pv(s,t,weather)*Kpv
0 <= C_t,D_t <= Kbess
0 <= E_t <= 4 * Kbess
E_{t+1}=E_t+sqrt(.85)*C_t*dt-D_t*dt/sqrt(.85)
F[s,y] <= W_t + P_t + D_t - C_t  for every t in selected contiguous stress window
```

关键参数：连续 **24、48、72 小时**压力窗口；初始 SOC 不得高于容量的 **50%**，事件结束必须不少于初始 SOC（无事件净能量套利），若是 Islanded，**禁止隐含电网免费充电**。窗口之间不允许人为重置 SOC 再宣称能连续跨越 72h；每个天气/窗口均需要满足同一个 `F`，以获得保守的鲁棒认证。此证书不是 ERCOT 法规正式批准的容量，仍是研究可靠性代理。

压力时段须包括：夏季晚间净负荷峰、冬季晨/晚峰、连续弱风弱光。若只能使用现行 3h×26w snapshots，认证窗口须用**连续原始小时序列的额外辅助 LP**或完整连续事件约束，不能把抽样点直接拼接成伪连续 72h 时序。若现有年度 LP 将 72h 事件的储能充电重复计入年内常规 dispatch，要将预留服务资源从同一时间的公共能源套利中扣除，或显式合并进容量与能量方程。

`serve_cap` 的增量表达应为 `S_it <= (GridFirm_MW+ThermalFirm_MW+F_re_bess_MW)/PUE`，同时逐时能量平衡对同一风光储资源进行强制检验，避免再在 dispatch 中重复使用额外的“免费”Firm 电力。ERCOT 2025 官方报告晚间参考 ELCC：其他地区风电 **8.33%**、Panhandle 风电 **17.83%**、其他地区光伏 **5.51%**、西部光伏 **7.32%**、4h 储能 **54.85%**，仅供**系统级统计对照**，不得当作单站孤网 Firm 系数 `S14`。

**即使某站组合认证 `F=0`，风光/BESS 仍可在正常运行节省燃料、套利或为已认证电源配套。** 不能以发电技术没有单独 Firm 信用为理由将其整个发电能量排除。

## F. 精确代码变更位置与实施顺序

1. **版本化输入**：将 `BYOP_TECH_PARAMETER_BASELINE_V2.json` 等复制至 `workflow/byop/inputs/tech_calibrated_v2/`；增加 `parameter_version = TECH_COMP_2` 选择开关，默认保持 v1.3，严禁直接改写老参数表。供应源与环境县规则均以本包记录为唯一实现参数来源。
2. `workflow/byop/model/v240_mech.py`：改造 `byop_params_v13` 为版本参数表适配器；保持 `byop_params` 对 social/private 利率和燃料价格逻辑；加入单独服务费、必要的后处理资产退出余额字段；旧 `SOFC_FAST_ELIGIBLE_MW=0` 保持旧版本有效，新版本仅提供需合法供货权的 reserved path，初始 verified MW=0。
3. `workflow/byop/model/rearch_mech.py`: `configure_mainline`, `add_byop_cohorts`, `ml_space`, `GAS-mdq`、`ml_stress_days`, `M2-serve_cap` 的版本化路径。对 `SITES` 全部循环，不能硬编码 8 个母线；按实际母线 facility MW 约束建设资格，并复用现有 ReEDS 母线风光潜力限制。
4. 新建 `workflow/byop/model/byop_delivery_and_permit.py`（纯函数）：输入 `site_fips`、技术、订单年、气网证据、供应路径与环境类别；返回许可候选状态、供应池、有效 COD 与所有并行工期分解。没有真实 FIPS 则自动 UNKNOWN_CONSERVATIVE，留可审计 flag，但**不能未定义/NaN 或回退 0**。
5. 新建 `workflow/byop/model/byop_renewable_firm.py`：处理压力窗口连续时间索引、额外鲁棒 LP 行和 `Fcert`；**缺 H5 只可使用现有对齐风光形状，不可伪造历史年份**；测试同一电源在压力窗口和普通逐时 dispatch 无双重使用。
6. 新建 `workflow/byop/model/byop_supply_pools.py`：`calendar_y, tech, path, quantity` 联合交付池; 将 2026–2031 的数值原封不动读入；保留 2032–2035 扩展接口，但本轮只求解准备至 2031，不得擅自延长解期。
7. 修改 `workflow/byop/post/collect_mainline.py` 与 `stage_b3_tables.py`，输出 `TECH_COST_AND_COD_AUDIT.csv`, `TECH_CAPACITY_BY_SITE_YEAR.csv`, `TECH_SUPPLY_USAGE.csv`, `TECH_EMISSIONS_PROXY.csv`, `TECH_RE_BESS_FIRM_AUDIT.csv`, `TECH_PERMIT_STATUS.csv`; M4 matched-service 键改为动态 `(site,year)` 完整集合，并保存 `n_expected_keys`，旧 48-key 回归继续通过。
8. `build_mainline_manifest.py` 列入所有新增代码和输入 SHA，更新严格运行门控；默认 `run_authorization=NOT_APPROVED`。不允许复制旧 SHA 的批准状态取得新主程序的求解授权。

## G. 验收标准（任何 FAIL 均停）

1. **数据范围**：输入中的 2025 historical / inherited ramp 内容字节哈希不变；2026–2035 low/mid/high 逐年研究增量守恒，原多母线空间权重不变；候选 BUS 与 POI/天然气/FIPS 映射完整。
2. **版本回归**：旧 v1.3 技术参数、旧 8 母线的小型结构测试不受新技术代码影响；新配置在多母线下 6 技术均能够创建且仅有合法参赛对象，无“技术空缺自动变零工期”的隐式 fallback。
3. **COD**：小单元例子：(a) SOFC 设备 0.75y + 现场 0.25y、燃气 0.5y、许可 0.4y，2026 下单，名义 COD=2027；(b) 燃气 L2=3 年时同 SOFC COD 不能早于 2029；(c) 2027.25 COD 不能获得 2027 **全年** Firm 认证；(d) aero 标准设备 1.5 + 安装 0.5 不得 2027 全年 Firm；(e) 缺专属合同没有 `RESERVED_FAST` 的装机容量。
4. **成本**：RICE 固定约 $231.78/kW·y、aero $225.50、SOFC $553.2；包括运维/stack 代价只出现一次；base private=7% / social=2%；HHV 天然气系数与逐年气价一致；不重算新建专属电源为公共电网资本支出。
5. **环境**：本工作包 DFW、HGB、Bexar 县名名单与 FIPS 匹配；高风险县默认工期更长；`RICE_50DF` 未证明为天然气 SI 时不可自动获得 TCEQ 新标准许可；`Carrier.co2_emissions` 如果出于兼容必须保留 0，**不代表技术无排放**，必须单独输出 CO₂/NOx 台账。
6. **供货**：对应六年度供应池严格可读取、不过限；同一 MW 不因 S2 开发商承诺转交社会规划而重复使用；没有已核实 2025 预订额就不能在快速路径出现容量。
7. **风光储**：SOC 能量守恒（含效率）、连续 24/48/72h 约束在多日弱风弱光案例不能凭空供电；同个储能不能同时提供两个重复的完整 Firm 承诺；ELCC 不能当项目局部固定 Credit；带气象标签。
8. **数学**：线性 LP，无整数变量、二进制变量、线性化的产能容量约束不得出现乘积 `K*decision`; 数字尺度检查不导致求解不稳定（有意测试非求解器输入）。需生成一页“具体哪些机制造成不同技术竞争差异”的无需 LP 报表。
9. **审计**：保留旧 B3 中 S2 延期 173.17 MW IT·yr、312.5 MW aero、M4 差约 $2.28m **仅作旧版本参照**。新参数版本不要求再出现特定容量、特定技术或更高 speed benefit。

## H. 交付清单和执行终点

执行方必须 git push 后返还：

```
GIT_BRANCH, FINAL_GIT_SHA, PARENT_SHA
TECH_PARAMETERS_CODE_AND_INPUT_DIFF.md
SOURCE_TO_PARAMETER_CROSSWALK.csv
TECH_COST_AND_COD_AUDIT.csv
TECH_PERMIT_STATUS.csv
TECH_SUPPLY_USAGE.csv
TECH_RE_BESS_FIRM_AUDIT.csv
TECH_STATIC_TEST_REPORT.md
TECH_GATE_AND_MANIFEST_REPORT.md
TECH_UNRESOLVED_MODEL_LIMITATIONS.md
RUN_AUTHORIZATION=NOT_APPROVED
SOLVER_EXECUTIONS=0  # unless separately approved for SMALL isolated LP tests
```

**执行 STOP**：完成技术模型及静态/不运行求解器的检查后停止，不执行 Stage B3 全量重跑，不覆盖 B3 结果，不进入官方 2025 可靠性校准 C1 计算。研究者审核通过后才安排在同一新多母线与同一官方锚定电网下比较 `GEO_OLDTECH` 和 `GEO_NEWTECH`，避免把地理变化、历史校准与技术变化混在一起归因。

## I. 核查来源（研究者已提供，供留痕，不作为执行方搜集任务）

- `S01` Bloom Energy Server 6.5 (Feb 2026)：https://www.bloomenergy.com/wp-content/uploads/bloom-energy-server-datasheet-feb-2026.pdf
- `S02` Bloom Oracle 实绩与订单：https://www.bloomenergy.com/news/bloom-energy-and-oracle-expand-strategic-partnership-to-deploy-up-to-2.8-gw-to-accelerate-ai-infrastructure-build-out/
- `S03` Bloom SEC 2026 产能：https://www.sec.gov/Archives/edgar/data/1664703/000162828026024237/be-20260408.htm
- `S04` AEP Fuel Cell 合同：https://www.reuters.com/business/energy/american-electric-power-signs-265-billion-deal-fuel-cells-2026-01-08/
- `S05` Rabobank 2026 BYOP 对比：https://www.rabobank.com/knowledge/d011524694-the-sprint-data-centers-are-building-a-parallel-energy-system-in-the-us
- `S06–S07` Wärtsilä 技术比较：https://www.wartsila.com/energy/learn-more/technology-comparison-engines-vs-aeros/executive-summary
- `S08` GE Vernova 2026Q2：https://www.gevernova.com/news/articles/ge-vernova-releases-second-quarter-2026-financial-results
- `S09` TCEQ 新天然气 EGU Standard Permit：https://www.tceq.texas.gov/permitting/air/newsourcereview/combustion/ng-egu-sp
- `S10` TCEQ 燃机许可：https://www.tceq.texas.gov/permitting/air/guidance/newsourcereview/turbines/nsrauth_turb.html
- `S11/S12/S13` TCEQ DFW / Houston / Bexar 非达标县：https://www.tceq.texas.gov/airquality/sip/dfw/dfw-status/ ; https://www.tceq.texas.gov/airquality/sip/hgb/hgb-status ; https://www.tceq.texas.gov/airquality/sip/san/san-status
- `S14` ERCOT 2025 风光储 ELCC 报告：https://www.ercot.com/files/docs/2025/02/12/2024_ERCOT_ELCC_Study_Final_Report_Revised.pdf
- `S15` ReEDS 输入：https://reeds-model.github.io/ReEDS/inputs.html
- `S16–S18` EPA AP-42 与 GHG：https://www.epa.gov/air-emissions-factors-and-quantification/ap-42-fifth-edition-volume-i-chapter-3-stationary-0 ; https://www.epa.gov/climateleadership/ghg-emission-factors-hub
