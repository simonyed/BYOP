# ReEDS2 → TAMU 64s：风电 / 光伏新增潜力（Mainline v1.3 WP-C）

状态：`DERIVED`，Stage A 已生成；尚未被任何求解使用（`SOLVER_EXECUTIONS: 0`）。

## 1. 读取了什么

- 来源：本地 `D:\ReEDS2`，只读，commit `eb75a6bc664297492b38a40782df294666269971`（2026-10-14）。
  - 整个 ReEDS2 没有复制进仓库，也没有复制到 L2。
  - 文件清单和 SHA-256 见 `REEDS2_SOURCE_INVENTORY.csv`。
- 用到的 ReEDS2 文件：

| ReEDS2 文件 | 内容 | 单位与处理 |
|---|---|---|
| `inputs/supply_curve/supplycurve_wind-ons-reference.csv` | reV 陆上风电供给曲线，reference 选址情景 | MW_AC |
| `inputs/supply_curve/supplycurve_upv-reference.csv` | reV 光伏供给曲线，reference 选址情景 | MW_DC，按 `ilr_utility = 1.34` 换算成 MW_AC |
| `inputs/supply_curve/interconnection_land.h5` | `sc_point_gid` 对应的经纬度和县 FIPS | — |
| `inputs/scalars.csv` | `ilr_utility = 1.34` | — |

- 逐时 cf 文件（`cf_wind-ons_reference.h5`，9.0 GB；`cf_upv_reference.h5`，5.9 GB）**没有使用**：
  - 模型继续用 PyPSA-USA 各母线的逐时风光可用率，与 2025 基准负荷属于同一气象年，这是 v1.3 §5 允许的做法。
  - ReEDS 的 cf 只在 `ERCOT_WIND_SOLAR_POTENTIAL.csv` 中按容量加权给出，作为对照。

## 2. 转换规则（`workflow/byop/build/build_reeds2_potential.py`）

1. **ERCOT 筛选**：资源点所在县必须出现在 2025 TAMU 基准的 ERCOT 县表 `COUNTY_TO_BUS_SHARES.csv` 中。
2. **母线映射**：资源点映射到该县所属 TAMU 母线中距离最近的一条，结果见 `REEDS2_TO_TAMU64.csv`（bus × 县）。
3. **扣除已利用量**：剩余可新增量 = max(0, ReEDS 潜力 − 2025 现有装机 − 2026 年起已承诺装机)。
   - 现有装机来自 `BUS_LEDGER.csv`，已承诺装机来自 `ercot_committed_pipeline_tamu.csv`。
4. **模型用法**：剩余可新增量是公共新建与**同母线**现场 BYOP 的**共享上限**，对全部建设期合计（约束 `ML-potential_{onwind,solar}_<bus>`）。
   - 公共候选机组的 `p_nom_max` 也同时截断到这个值。

## 3. 结果与局限

- ERCOT 全网剩余可新增量：风电约 834 GW_AC，光伏约 9,400 GW_AC。8 个 Epoch 母线上，风电 1.2–52.7 GW，光伏 24–602 GW。
- 这是**技术潜力**，比 AIDC 负荷大几个数量级。所以它防止的是"无限风光"，但限制不了站点自身。
- 站点层面另设**邻近土地代理上限**：`GREAL_POI_ASSUMPTIONS.csv` 中的 `onsite_renewable_cap_MW`，取各母线 2031 年研究设施 MW 的 1.0 倍，风电、光伏各自计算（约束 `ML-onsite_*`）。该值标为 `PROXY`，待审计。
- 未包含的内容：土地用途优化、道路或输电线寻址、ReEDS 的 spur-line 成本（`capital_adder_per_mw` 只做报告）。
- 可复用机组 / 退役辅助数据：没有从 ReEDS2 生成可复用（R）资产池。D14 要求 R 资产有可核实的状态和容量权利，而 ReEDS 只提供按机龄推算的退役年份，不能作为证据。因此 `GREAL_R_ASSET_POOL.csv` 为空。
