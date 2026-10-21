# MAINLINE_V13_DECISION_LOG：Mainline v1.3 决策日志

- 日期：2026-10-21
- 状态：`STAGE_A`
- 运行授权：`RUN_AUTHORIZATION: NOT_APPROVED`

## 1. 已批准的研究者决定（v1.3 §2）：全部 **CONFIRMED**，执行者不再重复询问

| ID | 内容 | 实现位置 | 状态 |
|---|---|---|---|
| ML-D01 / ML-D02 | 只用现有 PyPSA-USA / TAMU 64 节点底座；Epoch 空间分配；纯 LP | `rearch_mech.py --mainline` | **CONFIRMED** |
| **D11** 2025 存量爬坡 | 2025 年全年平均已在背景负荷中。<br>年末比均值高出的 **460.73 MW IT** 作为继承存量：<br>• 是所有情景（含 S0）的背景负荷，有单独的切负荷变量并受 no-harm 保护；<br>• 不是研究需求的 Firm 权利；<br>• 不额外加量，2026 年获批总量 565.95 MW = 460.73 继承 + 105.22 研究新增。 | `build_mainline_inputs.py`；`MAINLINE_AIDC_RECONCILIATION.csv`；`add_inherited_ramp()` | **CONFIRMED** |
| **D12** 每个母线一个聚合 POI | 8 个母线各有一个聚合 POI，带日期的设备行逐园区留痕（`GREAL_POI_E0_SCHEDULE.csv`）。<br>未知容量标为 `PROXY`，不会给无限进口。 | `configure_mainline()`、`eq_terms()` | **CONFIRMED** |
| **D13** S2 统一企业目标 | 一个联合开发商 LP：先逐年最大化 8 个母线已投运 IT 合计，再最小化私人成本。<br>无 max-min 公平层，无供电模式枚举。 | `developer_joint()` | **CONFIRMED** |
| **D14** SOFC Fast / 复用 | Fast SOFC 槽位为 0；可复用资产池为空（没有已核实资产）；气源用有界的 L1/L2 代理。 | `SOFC_FAST_ELIGIBLE_MW = 0`；`GREAL_R_ASSET_POOL.csv`；`MDQ_PROXY` | **CONFIRMED** |
| **D15** Aero OCGT | 开放 aero 作为主要燃气 BYOP 候选（2275 / 9.99 / 5.97 / 9447 / 2 年）。<br>大型 CCGT 不开放；容量为连续 MW（规划近似）。 | `ML_TECHS` | **CONFIRMED** |

## 2. 执行者在 Stage A 做出的实施选择（对研究目标影响小；在审计中可一并否决）

| ID | 选择 | 理由 |
|---|---|---|
| ML13-I01 | 在 `rearch_mech.py` 上加 `--mainline` 开关，不新建平行模型；v1.0 / v2.4.0 回归路径保持不变 | v1.3 §1："直接改造，避免新建平行模型"；"旧算例文件完整保留供回归" |
| ML13-I02 | 功能分支 `mainline-v13-stageA`，推送到 GitHub 并开 PR，不合并到 `main` | v1.3 A5："最好建 PR，不自动合并覆盖主分支"。本地 CLAUDE.md 的常规同步是推送到 `main`；本工作包的要求更具体，以本工作包为准 |
| ML13-I03 | ReEDS2 转换脚本放在 `workflow/byop/build/`，会提交到 GitHub；运行日志留在本地 `work_pkgs/BYOP_ERCOT_Mainline_v1.3/` | v1.3 §1 要求纳入"可复现的小型派生表、转换脚本、元数据与哈希"。与此前"预处理脚本只放 work_pkgs"的惯例不同，以本工作包为准 |
| ML13-I04 | 公共侧候选机组的成本和工期保持 PyPSA-USA ATB / TECH-01 UTILITY 口径 | v1.3 §D2.a：公共机组已有可信口径的参数不得被静默替换 |
| ML13-I05 | 压力日从 2025 气象和负荷年中选 3 个真实日，以自身 3 小时权重加入每期抽样 | B7：压力情形必须进入 Firm 约束；不用人为构造的极端值 |
| ML13-I06 | 现场风光继续使用 PyPSA-USA 的母线逐时出力；ReEDS2 只用于新增潜力上限 | v1.3 §5 允许复用现有时序；与 2025 负荷为同一气象年 |

## 3. 需要研究者审计的新问题（`REVIEW_REQUIRED`，每条附推荐方案）

| ID | 问题 | 推荐方案（已按此实现为默认值） | 不同选择的后果 |
|---|---|---|---|
| **ML13-01**（独立审计 P0-3 后修订） | 6 个已有园区（Google Red Oak / Midlothian、Meta Temple、Microsoft SAT14、Vantage TX1、CoreWeave Denton）的 POI 设备容量没有公开的认证数值 | **选项 A（新默认）**：按 Epoch 时间线逐步骤分类：<br>• 截至 2026-10-21 已观测投运的部分 → 预批（EXISTING_ENERGIZED）<br>• 未来或估计的步骤 → 不预批，COD = max(Epoch 年份, 2028)（PLANNED_UNVERIFIED，PROXY）<br>**选项 B**（v1.3 初版）：园区按 Epoch 最终规模，2026 年即预批 | 选项 A：Red Oak（2026–27 年最多 59 MW）和 Temple（最多 20 MW）可能出现由程序层主导的 S1 延期；其余母线不变<br>选项 B：有把未来资格提前之嫌（审计 P0-3） |
| **ML13-02** | Shackelford（Vantage Frontier）的电网方案有冲突：一说 Oncor 需要新建变电站（电网供电），一说由 VoltaGrid 建离网燃气微网 | E0 = 0，通过 POI 升级（工期 3 年，不早于程序日期 2028 → 最早 2029）；燃气按 L1 | 若改为离网 IS，就是把结果预设进了输入；若改为有 E0，Speed-to-Power 机制在该母线消失 |
| **ML13-03** | Helios 新增的 830 MW（2026 年 1 月获批，与 AEP Texas 签有服务协议）何时投运没有公开日期 | COD 按 2028.0 代理（新建变电站约 2 年） | 若取 2027，p600 0 更早不受 POI 约束；该母线 2031 年研究需求只有 365 MW IT，影响有限 |
| **ML13-04** | POI 升级参数：上限 2,000 MW，工期 2 / 3 / 5 年，成本 80 / 160 / 300 USD/kW，程序日期 2027.5 / 2028.0 / 2029.0（8 个母线统一） | 沿用 v1.0 `POI_REGISTER` 的区间（`RESEARCH_ASSUMPTION`）；主线用 base | low / high 情景只作为后续敏感性，本轮不运行矩阵 |
| **ML13-05** | Abilene 现场 aero 燃机（第三方报告引用的许可文件：约 360 MW；Crusoe 订购约 1 GW） | 不作为"已订货 / 已有"BYOP 录入（D11：不创造未证实的既有专属电源）；Abilene 的新增 BYOP 都按新建处理 | 若批准录入为已有设备（沉没成本、立即可用），S2 在 2026–2028 年的 Speed-to-Power 会明显提前；建议只有在研究者提供证据后才开放 |
| **ML13-06** | 现场风光的邻近土地上限 | 每种技术取 2031 年研究设施 MW 的 1.0 倍（`PROXY`）；母线级 ReEDS2 剩余潜力由公共侧和 BYOP 共享 | 若上限更大，GF / IS 模式中风光 + 储能组合的比重会上升 |
| **ML13-07** | 现有燃气机组的价格：2025 基准的 mc = HR × 3.19 + VOM | 所有燃气机组统一用 WSC 逐年价格重新定价（mc + HR × Δgas）；不改热耗和 VOM | 若现有机组保持 3.19，同一年公共侧与 BYOP 的燃气价格就不一致，违反 v1.3 §D2.b |
| **ML13-08** | PCLR（Conditional Firm）容量与触发方式 | 2031 年研究设施 MW 的 30%；200 小时/年、单次最长 12 小时；优先在压力时段触发，其次取 S1 电价最高的时段（`PROXY`） | 若 PCLR 设为 0，就只剩 GO_F / GF / IS 三种模式 |
| **ML13-10**（审计 P0-4） | 电网 Firm 报价的物理含义 | 两部分报价：压力时段 = S1 在压力时段与 8 个母线同时交付的最大值；非压力时段 = S1 的最大交付值。S2 公共 LP 交付不了开发商计划时 `SCIENTIFIC_USE = BLOCKED` | 若只用最大进口，可能高估压力时段的电网可交付量，从而低估 BYOP 的需要 |
| **ML13-11**（审计 P1-3） | 2031 年以后剩余年金的处理（`tv_share = 1.0`，隐含完整残值） | 保持不变，作为短期机制演示的明示约定；成本差需注明 | 若 `tv_share < 1`，早期投资的成本更高，BYOP 和公共投资都受影响；属于后续 M3 研究 |
| **ML13-09** | 运行规模与资源：v1.0 每个 3 场址算例要 5–7 小时；本轮是 8 个母线、6 种技术、5 次归因放松求解，预计显著更长 | 推荐 Stage B 顺序：step0（ERM 校准 + S0 最小增容校准）→ 正式运行（每个求解 6 线程）；如需提速，按 `--case-group` 把归因放松求解并行 | 不影响结论，只影响墙钟时间 |
