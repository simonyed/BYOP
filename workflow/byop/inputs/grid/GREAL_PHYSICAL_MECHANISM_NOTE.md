# G-REAL：电网物理机制说明（Mainline v1.3 WP-B，B1–B10）

状态：Stage A 代码与数据已就绪。**哪类约束真正起作用（binding）、何时出现延期，均为 `PENDING_RUN_GATE`**，要等 Stage B 获准求解后才能判断。

## 1. G-REAL 是什么

G-REAL 是唯一的电网背景，S0–S3 四个情景完全共用：

- **电网**：TAMU 64s 电气骨干网（KVL 直流潮流），沿用 2025 年修复后的线路、机组和负荷映射。
- **背景负荷**：2025 年 ERCOT 原生负荷乘以 AEO2023 得州增长系数。
  - 这一负荷已含 Epoch 存量站点 2025 年的时间加权平均（140.27 MW IT）。
  - 另加 D11 的 2025 年末继承爬坡 460.73 MW IT，作为单独背景负荷。
- **已承诺输电工程**：DWB Stage 2，以及 PUCT 已批准的两条 765 kV 输入通道（ISD 2031 / 2031.5，投运首年按比例可用）。
- **内生扩建候选**：每条 TAMU 线路都可内生加强，有成本、按批准年份建模、工期 4 年，不会免费提前投运。

G-REAL 中**不包含**：

- v1.0 在每个 POI 母线上叠加的、与研究需求同等规模的程式化"竞争排队负荷"；
- `regional_dc` 背景 AIDC；
- 旧的 3 个测试 POI（DFW_KAU、ABI_TAY、PEC_REE）。

证据台账见 `GREAL_NETWORK_EVIDENCE.csv`、`GREAL_GRID_PROJECTS.csv`、`GREAL_BACKGROUND_LOAD_RECONCILIATION.csv` 和 `../poi/GREAL_POI_ASSUMPTIONS.csv`。

## 2. 新增研究 AIDC 取得 Firm 供电时受哪四层约束（B4、B8）

| 层 | 模型中的约束 | 如何记账与诊断 |
|---|---|---|
| `POI_EQUIPMENT` | 各母线一个聚合 POI，`firm + conditional ≤ EQ(s, p)`。<br>EQ = 已有或已批准设备行（`GREAL_POI_E0_SCHEDULE.csv`，带日期）+ 按批准年份分批的 POI 升级 U(s, q)。<br>升级 COD = max(q + 工期, 程序最早日期) | 约束 `POI-eq_*` 的对偶值（`poi_eq_dual_abs`）；设备上限 `poi_limit_MW`；单因素放松 `S1E_xPOI` |
| `UPSTREAM_TRANSMISSION` | POI 潮流是母线上的负荷，在同一个 KVL 网络中联合求解，8 个母线共享，不能重复预留 | 单因素放松 `S1E_xUP`（线路容量 ×10）；输电走廊拥堵记录 |
| `RESOURCE_ADEQUACY` | Firm POI 潮流以 (1+ERM) 计入得州 ERM 行；Conditional 不计入 | ERM 对偶值（`resource_adequacy_binding`）；单因素放松 `S1E_xRA` |
| `PROCEDURE / COD` | 新的接入分配（升级 U、未预批的设备、PCLR）不早于 Batch Zero 的最早日期；8 个母线用同一条规则 | `procedure_ready_year`、`earliest_grid_COD`；单因素放松 `S1E_xPROC` |

- 多个约束同时起作用时，**不把延期天数线性拆成相加的百分比**，而是分层报告哪些约束 binding。
- 对任何母线都没有硬编码"必须延期 X 年"。

## 3. B7：压力时段直接进入 Firm 约束

- **压力日选取**（`ml_stress_days()`）：从基准年时间序列（2025 ERCOT 负荷 + PyPSA-USA 风光出力，时间戳标为 2030）中选出 3 个真实日（3 小时分辨率）：
  1. 负荷最高的 30% 日子里，West / Panhandle 风电最低的一天；
  2. ERCOT 净负荷（负荷 − 风 − 光）最高的一天；
  3. 冬季（12–2 月）负荷最高的一天。
- **加入方式**：这 3 天被加进每个投资期的抽样周中。每个压力时段只代表它自己的 3 小时；其余抽样周的权重相应调整，使每期权重合计仍为 8,760 小时。
- **在压力时段内**：
  - AIDC 负荷照常存在，Firm 进口必须服务它，并同时满足 KVL、机组时序可用率、POI 上限和 ERM 行约束。
  - 燃气 BYOP 只能按故障情形下的 Firm 信用（1/r，且仅限全年在运的容量）出力。
  - 风电、光伏只有实际时序出力，没有 Firm 信用；BESS 受 SOC 约束。
- **PCLR 触发**：Conditional 合同的触发时段优先取压力时段，其次才取 S1 中电价最高的时段。
- **可选的接口降额**（`stress_line_derate`）：默认 1.0，即关闭。它是待审计的代理参数，不用来人为制造拥堵。
- 本轮不做全 N−1，也不引入整数变量。

## 4. B9：Far West 案例的空间适用性

- ERCOT 2026 年 2 月的 Far West 报告提供的是**机制证据**：低风、无光伏、接口受限。
- 8 个 Epoch 母线都不在 ReEDS 的 Far West 区（p62）。因此：
  - 报告中的区域可靠服务容量**没有**被写成任何线路或母线的上限；
  - DWB 和 765 kV 工程作为共同基准资产，只通过网络潮流影响 Epoch 母线。
- 旧的 Reeves / Pecos 测试 POI 不再携带任何研究负荷。
- 也不强求 8 个母线都出现拥堵。

## 5. B10：Bridge-to-Grid 可观察

- GF 模式下，跨年度调度和进口权利允许 BYOP 占比逐年下降、公共进口逐年上升。
- 每个母线、每年输出：`IT_energized_MW`、`grid_import_MWh`、`BYOP_gen_MWh`、`BYOP_capacity_MW`、`certified_import_MW`。
  - 输出位置：`poi_ledger.csv` 和 `MAINLINE_BUS_DELIVERY_AND_DELAY.csv`；S2 的开发商侧见 `MAINLINE_S2_MODES_TECH.csv`。
- 供电模式（GO_F、GO_C、GF、IS）在求解**之后**按物理结果归类，没有离散状态机。

## 6. 科学验收的预先风险提示（Stage B 时需要检查）

- 按 Stage A 的输入，**POI 设备层**的缺口集中在两个母线。在 G-REAL 下，两者都要等升级 COD，且不早于 2029 年：

| 母线 | 2031 年研究需求（IT） | 已有设备（设施 MW） | 缺口 |
|---|---|---|---|
| Abilene（p610 2） | 1,304 MW | 956 MW | 需要升级补足 |
| Shackelford（p630 4） | 1,286 MW | 0（无已证实的电网设备） | 全部依赖升级 |

- 独立审计 P0-3 之后，园区设备按 Epoch 时间线分为已观测投运和计划未核实（不早于 2028 年）两类。Red Oak（p630 2）和 Temple（p630 5）在 2026–2027 年有小缺口（最多 59 MW 和 20 MW），这部分延期属于**程序层**。
- 其余 4 个母线的已有或已批准设备不小于研究需求，是否延期取决于上游输电和资源充裕度。
- 如果 Stage B 的延期**完全由程序日期主导**，将如实报告，并重新检查网络和背景负荷。**不会通过降低线路容量来制造 BYOP 优势**（v1.3 B 科学验收条款）。
