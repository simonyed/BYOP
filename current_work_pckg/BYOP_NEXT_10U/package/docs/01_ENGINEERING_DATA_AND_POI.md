# 01｜工程包复用 + 项目级 POI 可行域（WP0–WP1）

## 证据包说明（真实本地原包，执行前需核验）
原会话数据 ZIP 名 `BYOP_Engineering_Data_Package_v1.0_2026-10-23.zip`（先前约 261 MB）。包含 TPIT 2026-07 项目 2,127 行，2020–2026 工程追踪面板约 25,838 行/4,286 条追踪；17 个 EIA-860M 版本、TX 机组面板约 57,479 行；ATB 2025、NEMA/Batch Zero/电网资料；站点、项目和需求候选表。本工作包不包含这些大文件；原包处理结果的数字不是每站官方接入容量事实。

首选 `engineering_data/processed/` 中查找如下**准确文件名**（原包实际子路径可能不同，不假定目录层次；预检脚本会递归定位，若有多个同名版本，应按原包 manifest SHA 或最新已核验版本定版）：

| 表 | 已知内容与用途 | 重要限制 |
|---|---|---|
| `poi_e0_evidence_classified.csv` | 原 E0 12 条权利事实/代理分类 | 不是已送电设备清单 |
| `poi_equipment_proxy_schedule.csv` | 已可使用设备、分批 COD 保守代理 | 不把获批额定 MW 视为设备已经完成 |
| `poi_site_release_parameters.csv` | 16 研究站点各类 capacity/evidence | 聚合研究母线≠同一真实客户 |
| `poi_engineering_parameters.csv` | LOCAL/GRID_DEPENDENT 工期及成本分组 | 研究建议，不是每站确认 COD |
| `poi_demand_visibility.csv` | 2026–2035 共 160 tranche；公告/需求年份 | 不能提前下单未披露 cohort |
| `poi_investment_candidates.csv` | 320 条 site/type/year 候选，包括不可用上限0 | 不能每年重复分配总容量上限 |
| `engineering_baseline.json` | 研究假设、已知工程与政策说明 | 不自动覆盖正式 v1.7L |

其余工程证据先从 raw/processed 递归映射：TPIT snapshots、TPIT history summary、TPIT-to-bus crosswalk、EIA-860M 面板、公共工程成本、Epoch/PNNL 站点证据及参数台账；绝不因文件名不同就重复下载。

## 站点真实项目与合成母线的区分
- 保留 `site_id, owner, campus_id, bus, request_id, cohort_id, request_MW_IT, facility_MW, evidence_id, document_date, agreement_status, equipment_status, approval_MW, qualified_firm_MW, first_service_date, earliest_COD, expected_COD, stage`。16 研究母线最后才聚合。
- Helios: 800/830 MW 可作为批准证据，已交付 200 MW gross /133 MW IT 可作为已交付下界，不可宣称批准的 1,630 MW 已全部送电。2026.50 作为保守代理，与已批准权利层分开。
- Abilene: 955.6 MW 的原值为批准容量减背景需求的代理，不能自动认为所有设备已就绪、也不能判定完全不能送电。
- PNNL 新站点的 E0=0 表示未观察到权利证据，不是实际设备零。`UNKNOWN` 与 `MODEL_DISABLED_UNVERIFIED` 字段必须分开。

## 工程日程与权利等级
E0：证实已送电、可分配权利；E1：证实批准、已承诺分期；E2：需要直接接入设备；E3：还需要上游网络/资源充分；E4：仅公告或模型预测，无正式权利。单个项目可以同时具有 E2、E3 需求；不可把 E4 直接当作 E0。

事件 ledger 至少区分 `application/site_control`, `study`, `transformer_order`, `substation_bay`, `ROW/permit`, `construction`, `utility_COD`, `grid_ready`, `gas_ready`, `environment_permit`。设备 COD = 必要部件的最晚完成日，项目可分期激活，**不得把所有部件工期简单求和**。资格的 2026+ 最新规则按适用时间及祖父条款标注，2025/2026 年初已存在的项目不得一律追溯套新程序审批。

TPIT 首次观测时间不是工程开工、EIA Planned 首次出现不是物理起建；不能从观察滞后直接拟合 1–2 年设备交期。`GRID_DEPENDENT_POI` 表示必须经过网状潮流/公共系统验证，**不表示每个 POI MW 自动等于 1 MW 新输电线**。

## 数学实现（LP-only）
给定研究站点 s、工程类型 k、承诺年 q 的增量设备 `U[s,k,q] >= 0`、工程可用系数 `a[s,k,q,y]`、已知设备可用 `E_known[s,y]`：

`E[s,y] = E_known[s,y] + sum_{k,q} a[s,k,q,y] U[s,k,q]`。

需追加的约束：
- 各类候选跨批次上限 `sum_q U[s,k,q] <= Umax[s,k]`，以及全部活动设备上限 `E[s,y] <= Emax[s,y]`（真实已承诺资产与候选去重）。
- 已披露需求上限：`sum_{k,q<=Q} U[s,k,q] <= sum_{cohort announced <= Q} facility_MW[cohort]`；已有设备、已承诺工程按真实台账排除避免再投资。
- `0 <= firm + conditional <= E[s,y]`，物理电网进口≤设备≤分配权利，同时满足电力平衡/损耗/网络瓶颈/备用/中断预算，防双重 credit。
- 同一真实共享物理工程 `sum_s allocated[s,g,y] <= capacity[g,y]`；目前不确定的共享关系不能通过猜测复制容量；研究母线代理只在标注时采用。
- 各工程候选的 COP/COD 日期在 LP 前由可信事件/类型确定，少量互斥合法选择 LP 外枚举，内部 LP 连续；不声称全局 MILP 最优。

## 现有程序接口
`workflow/byop/model/rearch_mech.py` 的 `configure_mainline, add_dc POIup, eq_terms, independent_it` 和 `workflow/byop/build/build_mainline_inputs.py` 是最小修改入口；`post_v16_mainline.py` 的 3 GW 备用、SOC 分段、firm 认证仅复用不改写。

**强制负面检查：**在新工程 config 下禁止读取 `GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv` 的 `poi_upgrade_lead_y_base=3`, `poi_upgrade_max_MW=2000`, `earliest_grid_COD_base=2028`。旧分支留作独立 `legacy_proxy` 复现。不能把原包 `GRID_DEPENDENT` 研究推荐 4 年同样无证统一套所有16母线；有证工程分期优先，无证候选应明确对机制识别不确定性。

## 验收
输出 `FIELD_TO_MODEL_MAP.csv`, `POI_ENGINEERING_EVENT_LEDGER.csv`, `POI_RIGHTS_AND_CAPACITY_AUDIT.csv`, `POI_INVESTMENT_LEDGER.csv`, `COD_CAUSE_LEDGER.csv`，每笔来源 SHA/证据级别/真实还是代理。小例至少覆盖：E0!=equipment、15年接入阶段继承、未到 COD、同站多 cohort、跨 q 不重购、风光不能替代 firm、conditional 中断预算、未披露需求不允许提前工程下单、未审核 TPIT 不自动创建线容量。
