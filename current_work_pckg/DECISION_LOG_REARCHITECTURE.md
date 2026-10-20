# DECISION_LOG — BYOP ERCOT 仿真架构重构 v1.0（2026-10-20）

状态取值：**已确认**（研究者此前确认、本轮沿用）｜**执行者假设·待确认**（本轮由执行者依据公开资料设定，需研究者批准）｜**已实施·诊断**（仅作诊断/敏感性）。
所有数值的出处编号（SRC-xx）见 `SOURCE_EVIDENCE_REGISTER.csv`（同时位于仓库 `workflow/byop/inputs/poi/`）。

## A. 空间 / 网络（WP-A）

| 编号 | 决策 | 理由 | 来源 | 可替换参数 / 位置 | 状态 |
|---|---|---|---|---|---|
| RA-A01 | 新空间方案 = PyPSA-USA 原生 BE/TAMU 合成节点网（`transmission_network: tamu`），独立配置 `config.byop_ercot_tamu.yaml`、run name `BYOP_ERCOT_TAMU`；7 区与县级配置不动 | 工作包 A1 主路线；不覆盖旧算例 | SRC-20 | `workflow/config/config.byop_ercot_tamu.yaml` | 执行者假设·待确认 |
| RA-A02 | `simpl: ""`（资源层 = TAMU 变电站级，1,250 站），`clusters: 64s`，`cluster_network.algorithm: modularity`（按电气连通性的贪心模块度聚类，在每个 ReEDS 区内部进行） | A2.2：按电气连接而非县界；64 在 40–80 试探区间内 | SRC-20 | clusters / algorithm | 执行者假设·待确认 |
| RA-A03 | `focus_weights` 固定各区节点数：p48 1、p60 5、p61 5、p62 8、p63 16、p64 8、p65 10、p67 11 | 首次 60s 试算按负荷分配时 p60/p61/p62（West/Far West/Permian）各只得 1 个节点，无法表达 Abilene、Permian 接入瓶颈 | 试算日志 `logs/byop/rearch_tamu_build/build_c60s.log` | focus_weights | 执行者假设·待确认 |
| RA-A04 | **修复 PyPSA-USA 缺陷**：`cluster_network.calibrate_tamu_transmission_capacity()` 把所有不在 ReEDS 接口表中的线路删除——即**全部区内线路**；64s 网络只剩 57 条线、24 个孤岛（而 `elec_s.nc` 为单一连通分量）。基准构建器用同一 busmap 从 `elec_s.nc` 重新聚合聚类间线路（PyPSA 线路聚合：并联 s_nom 相加、等效电抗） | A3：不得出现意外孤岛；否则区内瓶颈与 POI 上游送达性根本无法表达 | 连通性诊断（本报告 TEST 节） | `byop/build/build_2025_baseline_tamu.py` | 已实施（缺陷修复，建议上游报告） |
| RA-A05 | 跨区线路额定值规则 `reeds_sum`：同一 ReEDS 区对之间的所有跨区聚合线路按其 TAMU 原始额定值比例**分摊**该接口容量 max(MW_f0, MW_r0)/s_max_pu。PyPSA-USA 原逻辑给**每一条**跨区线路整套接口容量（k 条线 → k 倍接口，审计表中最高 13 倍） | 防止接口容量重复计算（A2.5 只允许接口级校准） | SRC-19；`INTERFACE_AUDIT.csv` | `--interface-rule reeds_sum / tamu_raw / pypsa_usa` | 执行者假设·待确认 |
| RA-A06 | 电气边界：删除 p48（SPP 狭长地带，非 ERCOT）及其联络线；不在主连通分量中的母线诊断后删除、资产重挂；无进口发电机、无 DC 联络 | A2.4 禁止隐含无限供电 | — | 构建器 | 已实施 |
| RA-A07 | 2025 基准沿用县级规则（ReEDS eb75a6bc 机组库 + ERCOT 2025 Native Load），但映射改为：机组经纬度 → 最近 ERCOT TAMU 变电站 → 聚类母线；负荷：气象区 → 县（ReEDS lpf）→ 县内变电站（TAMU load_weight）→ 聚类母线 | 资产按电气位置而非县界挂接 | — | `NETWORK_MAPPING_AUDIT.csv` | 执行者假设·待确认 |
| RA-A08 | 2025 可送达性校准 LP（同 D250-20 规则，但为 KVL 直流潮流）：线路最小增容 2e6 USD/MW，切负荷 1e6 USD/MWh；每一处增容记录为 B 级证据、非 TPIT 项目、不计扩张成本 | 2025 年实际负荷已被满足；缺口是合成网络数据缺陷 | — | `TAMU_2025_CALIBRATION_LP.csv` | 已确认（沿用 D250-20 规则） |
| RA-A09 | 走廊加强（仅 G-U）：每条 TAMU 走廊每期一对可控增量 Link（对称、上限 = 现有传输额定 100%，LINE-01），工期 TPIT 4 年（D250-06），成本 = 该线 PyPSA-USA 年化成本/MW。增量部分**不满足 KVL**（可控近似） | 多期 LP 中线路不能逐期增容；保持连续 LP | D250-06 | `--line-lead` | 执行者假设·待确认 |
| RA-A10 | PBRP 765-kV 两条进口通道（Bell County East–Big Hill–Sand Lake、Howard–Solstice）在 G-U 中作为已承诺固定 Link，2.4 GW/条（SIL 代理），ISD 2031.0 / 2031.5（低 2030.5/2031.0，高 2032/2033） | PUCT 已批准；ISD 未正式公布 | SRC-01、SRC-02 | `inputs/poi/GRID_PROJECTS.csv` | 执行者假设·待确认 |

## B. POI 与公共供电资格（WP-B）

| 编号 | 决策 | 理由 | 来源 | 参数 | 状态 |
|---|---|---|---|---|---|
| RA-B01 | 首轮 3 个代表性 POI：DFW_KAU（Kaufman 县，Prometheus–ENGIE 共址）、ABI_TAY（Abilene/Taylor 县，Lancium/Crusoe）、PEC_REE（Pecos/Reeves 县，Prometheus–Istmo）；均核实位于 ERCOT | 工作包 §7 首轮最小实验；C5 三个真实案例 | SRC-04…09 | `inputs/poi/POI_REGISTER.csv` | 执行者假设·待确认 |
| RA-B02 | 三个 POI 使用**相同**的程式化请求：2027 年 250、2028 年 +250、2029 年 +500 MW IT（累计 1 GW IT ≈ 1.3 GW 设施），非项目预测 | §7：同样的服务请求，只比较电网约束差异 | — | `inputs/poi/POI_REQUESTS.csv` | 执行者假设·待确认 |
| RA-B03 | POI 设备层：E0（现有可用进口设备）+ 连续 POI 升级 U（容量变量，无潮流；工期、成本按场址）。DFW E0 = 200 MW（未预批，需等程序日期）、ABI E0 = 1,000 MW（2026.5，已在建/已安排）、PEC E0 = 0（**确认无公开接入容量**，开发商计划孤岛运行，不是“未知”） | B1/B2.1 | SRC-04、08、09 | 登记表列 import_equipment_* | 执行者假设·待确认 |
| RA-B04 | POI 升级成本/工期：DFW、ABI 80/160/300 USD/kW、3/4/5 年；PEC 150/250/400 USD/kW、4/5/7 年 | Oncor 2026Q2：约 44 GW 合格大负荷、>70 亿美元、2026–2034 施工窗口 → 约 160 USD/kW；远西部线路更长 | SRC-10 | 登记表 poi_upgrade_* | 执行者假设·待确认 |
| RA-B05 | 程序层（Batch Zero）：新分配（U、未预批 E0、PCLR）最早 2028.0（低 2027.5、高 2029.0） | ERCOT：2026-08 分类、2027 春分配、2027 秋最终输电规划 | SRC-03 | earliest_grid_COD_* | 执行者假设·待确认 |
| RA-B06 | 上游送达性**内生**：POI 潮流是母线负荷，受 64 节点 KVL 网络与所有场址共同约束（联合 FCF，不存在可被重复分配的逐项目 headroom 数字） | B2.2、B2 联合检查 | — | — | 已实施 |
| RA-B07 | 充裕度层：Firm POI 潮流以 (1+ERM) 进入 TX ERM 行（ERM-DC-01 B）；Conditional 潮流不进入 | B2.3；结果标注为“压力代理”，非 ERCOT 正式稳定性审查 | 已确认 ERM-DC-01 B、ERM-02 B | — | 已确认（沿用） |
| RA-B08 | 延迟归因：S1 逐项放松 xPOI（设备无限）、xUP（所有线路 ×10）、xRA（公用电源/储能工期 0）、xPROC（程序日期 = 2026.0），以及全部放松 xALL；残差记为 combined/uncertain | B3/B4 | — | `--attribution` | 已实施·诊断 |
| RA-B09 | 设置：G-W 弱电网（现网，无走廊扩张）、G-K 受限（G-W + 每个 POI 母线一个**同等规模的竞争排队大负荷**，在所有情景中均存在，程式化）、G-U 升级（G-K + 走廊加强 + PBRP 765 kV） | §7 weak / constrained / upgrade；竞争负荷依据 ERCOT 约 474 GW 大负荷队列（SRC-13） | SRC-13 | `--setting`、`--competing` | 执行者假设·待确认 |

## C. 企业决策、模式与气源（WP-C）

| 编号 | 决策 | 理由 | 来源 | 参数 | 状态 |
|---|---|---|---|---|---|
| RA-C01 | S2 模式在 LP 外枚举：GO_F 仅电网 Firm、GO_C 电网 Firm + PCLR 式条件供电（可中断）、GF 并网灵活（WLPUN/BYOG：进口 ≤ 认证上限 + 自有 N/R）、IS 孤岛（零进口）。Bridge-to-Grid 由 GF 的逐年进口上限变化自然表示 | C1、C2；顶层设计“合法转换路径在 LP 外枚举” | SRC-14 | `--s2-modes` | 执行者假设·待确认 |
| RA-C02 | 事前电网报价来自**联合 S1 LP**：每场址每年可送达 Firm 进口 = S1 中实际可送达的最大 Firm 潮流；价格 = S1 父母线 LMP（energy_erm 时加容量附加）。取代旧 S2 中“按需求量无限购电” | C3.1 | — | `S1_GRID_OFFER.csv` | 已实施 |
| RA-C03 | 每个模式：逐年最大化已投运 IT（最早年份优先），固定后最小化私人成本；模式间先比服务轨迹再比成本，成本相差 < 1e-5 视为相同，取较简单模式 | C3.2、S2-SF 已确认定义 | 已确认 D-01 S2-SF | — | 已确认（沿用）+ 执行者细化 |
| RA-C04 | 公共 S2 LP 固定 BYOP K、R 与进口权利（Firm/Conditional 上限 = 企业计划用量），服务量以企业计划为上限；若公共 LP 不能交付计划服务 → 用公共实际送达量重新报价、重解企业阶段，最多 3 次，记录不一致 | C3.3/C3.4 | — | `--s2-iter`；`S2_consistency.csv` | 执行者假设·待确认 |
| RA-C05 | PCLR 条件供电：上限 500 MW/场址，自程序日期起可用；在事前触发时段（S1 父母线最高价时段）必须为 0，可用削减替代；削减预算 200 h/年（低 50、高 550），单次最长连续 12 h；削减按损失算力价值计（v/8760/PUE），计入社会总损失而非资源成本 | C2；ERCOT 尚无采纳的削减小时上限 | SRC-12 | `--pclr-hours`、`--pclr-max-consec-h` | 执行者假设·待确认 |
| RA-C06 | 气源三级证据：三个场址均为 L1（有管线/在建支线/机组许可，但无已核实的可交付 MDQ）。L1：日用气上限代理 250,000 MMBtu/d、支线工期 DFW/ABI 1 年、PEC 0.5 年，支线成本 DFW 60、ABI/PEC 30 USD/kW；L2（未知）：100,000 MMBtu/d、3 年、100 USD/kW；L0 必须有核实 MDQ。燃气 BYOP COD = max(设备工期, 支线工期) | C4：不再用“无证据=关闭”或“可签约=无限” | SRC-16、17、18 | 登记表 gas_* | 执行者假设·待确认 |
| RA-C07 | 合同路径 C **本轮未实施**（需要交付路径 + 防重复出售的容量权利，未在本轮完成） | 工作量与 Gate 顺序；不以价格折扣冒充 C | — | — | 未实施（下一阶段 P1） |
| RA-C08 | R（复用）资产：POI 父母线上的 ReEDS 到龄燃气机组，每台只分配给一个最近场址；R_pub + R_dc ≤ 机组 MW | 防止 N/R 重复使用 | 沿用 E05 | — | 已确认（沿用，成本仍为 PROVISIONAL） |

## D. 长期（WP-D）

| 编号 | 决策 | 状态 |
|---|---|---|
| RA-D01 | 本轮未把 TAMU + POI + S2 接入 `v240_path.py` 年度 approve-and-commit 控制器；所有结果为 2026–2031 静态多期 LP（筛查分辨率：每年 2 个抽样周，3 h）。2036–2050、2040/45/50 里程碑、SOFC 2026.5 首年、2040–2044 退役衔接、终值处理均**未在新架构中运行** | 未实施（下一阶段 P0/P1） |
