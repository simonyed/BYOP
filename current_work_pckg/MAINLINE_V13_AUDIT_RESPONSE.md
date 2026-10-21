# MAINLINE_V13_AUDIT_RESPONSE：对独立审计的逐项回应

- 日期：2026-10-21
- 审计文件：`BYOP_Mainline_v1.3_StageA_Independent_Audit_2026-10-21.md`（被审计的 HEAD 是 `efca9d0a`）
- 本轮按审计第五节的要求，在同一分支 `mainline-v13-stageA` 上**只修 P0-1 至 P0-5**，P1 各项只做披露并补充核验字段。
- 没有新增 MILP、园区竞争、气网 LP、完整 N−1 或情景矩阵；没有为产生 BYOP 优势而修改线路容量或把 E0 一律设为 0。
- **`RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS: 0`**。没有执行 `step0` 和 `run`。

## 1. P0 修复

| ID | 审计指出的问题 | 修复 | 不调用求解器的验收 |
|---|---|---|---|
| **P0-1** | `v240.ledgers()` 只汇总 `<bus> load_shed`，继承爬坡的切负荷没有计入 `load_shed_*` 和社会成本 | 新增 `rearch_mech.ml_shed_accounting()`（只在 mainline 下生效）。<br>• 继承爬坡切负荷 `*_inherited_ramp_unserved` 按与背景负荷相同的 `SHED_COST` 计价，加入 `load_shed_MWh`、`load_shed_PV_USD`、`social_real_resource_cost_USD`、`social_total_USD`<br>• 单独报告 `native_background_unserved_*` 和 `inherited_ramp_unserved_*`<br>• 在 `existing_customer_shed_loss_*` 之前调用，所以这两项也包含继承爬坡 | 静态测试 `test_p0_1_inherited_ramp_shed_is_booked`：用合成账本（不建网络）验证两类切负荷各计一次，社会账本增加的金额正确 |
| **P0-2** | 正式运行不含 `S3_mS2`，M4 的同服务量比较不会生成 | 配置 `scenarios: [S0, S1_EARLIEST, S3, S2, S3_mS2]`。<br>• `main()` 在 mainline 下直接读取配置中的列表（`ml_config_scenarios()`），缺少 `S3_mS2` 时拒绝运行<br>• `collect_mainline.py` 先核对 S2 与 S3_mS2 每个母线 × 年份的服务量完全一致（`service_trajectory_identical`），再报告社会成本差 | `test_p0_2_matched_service_in_formal_run`；`run_mainline.sh run` 不再自行覆盖情景列表 |
| **P0-3** | 6 个园区的 E0 直接用 Epoch 最终规模减去 2025 年末存量，并设为 `preapproved, COD = 2026`，会把未来的设备资格提前到 2026 | 从 Epoch 原始时间线（`data_center_timelines.csv`，SHA-256 `fdd4b1c5…`，与 `EPOCH_TAMU64_PROVENANCE.json` 一致）提取小表 `inputs/dc/EPOCH_TX_TIMELINE_EVIDENCE.csv`，逐步骤分为三类：<br>• **EXISTING_ENERGIZED**：截至 2026-10-21 已观测投运（排除"estimated / projected / scheduled / based on the stated completion date"等估计措辞），视为预批，最早年份 = 观测投运年<br>• **VERIFIED_APPROVAL**：Helios（800 + 830 MW）、Abilene（1.2 GW），行不变<br>• **PLANNED_UNVERIFIED**：未来或估计的步骤，**不预批**，COD = max(Epoch 年份, 程序最早日期 2028)<br>Shackelford 与 Crusoe 扩建没有电网证据，仍只能走 POI 升级。Denton 不再用"260 MW 合同"代理，改为观测值 | 静态测试 `test_qa_cod_existing_vs_new`：三类都存在；只有前两类预批；EXISTING 不超过"观测投运 IT − 2025 年末存量" |
| **P0-4** | S1 的 `max(POI 进口)` 不等于压力时段认证的 Firm 资格 | `s1_offer()` 现在给出两部分：<br>• `firm`：S1 非压力时段已证明可交付的最大值<br>• `firm_stress`：S1 在 B7 压力时段**与其他 7 个母线同时、在同一 KVL / ERM 解中**实际交付的最大值<br>开发商的电网购电在压力时段不超过 `firm_stress`，其余时段不超过 `firm`。重新报价时两部分同步更新。<br>`collect_mainline.py` 新增 `s2_public_delivers_developer_plan`（S2 公共 LP 最后一轮是否交付了开发商计划）；任何检查为 False 时 `SCIENTIFIC_USE = BLOCKED`，不得据此得出科学结论 | `test_p0_4_stress_certified_offer`；结构测试 `QA-P0-4`：开发商模型中，压力时段的购电上限为认证比例（测试用 0.5），其余时段为 1.0 |
| **P0-5** | `add_s0_calibration()` 在 `add_inherited_ramp()` 之前运行，校准时继承爬坡切负荷仍按 1e4 计价 | `build_rearch()` 改为先 `add_inherited_ramp()`、后 `add_s0_calibration()`。S0 校准时，所有 `load_shed`（背景和继承爬坡）都按 `S0CAL_SHED = 1e8`。正式运行的 VOLL 不变 | `test_p0_5_inherited_ramp_before_s0_calibration`；结构测试 `QA-P0-5`：构建一个 S0 校准网络，断言全部切负荷机组（含 5 个继承爬坡）都按 1e8 计价 |

### P0-3 对输入的影响（只看设备层，尚未考虑 POI 升级；不是求解结果）

| 母线 | 修订前 E0（MW，全部预批 2026） | 修订后：预批 / 2028 起的计划 | 研究需求超出可用设备的缺口（MW，设施口径） |
|---|---:|---|---|
| p630 2 Red Oak | 95.8 | 0 / 89.1 | 2026 年 7.7、2027 年 58.7，2028 年起为 0 |
| p630 5 Temple | 54.9 | 0 / 30.1 | 2026 年 2.6、2027 年 19.8 |
| p630 6 Midlothian | 123.0 | 79.8 / 39.3 | 0 |
| p630 9 Denton | 223.1 | 225.6 / 23.1 | 0 |
| p650 0 San Antonio（TX1、SAT14） | 223.2 | 69.4 / 111.0 | 0 |
| p600 0 Helios、p610 2 Abilene | 不变（已核实批准） | — | Abilene 2029 年起约 500 MW，要靠升级补足 |
| p630 4 Shackelford | 0 | 0 | 2028 年 149 MW；2029 年起要靠升级补足 |

**含义**：Red Oak 和 Temple 在 2026–2027 年可能出现 S1 延期，这些延期**由程序层（PROCEDURE）主导**，Stage B 中应如实这样归类。如果研究者认为园区扩建应按 Epoch 日期获得接入，可在审计中选择旧做法（ML13-01 选项 B）。

## 2. P1：披露与补充核验字段

| ID | 处理 |
|---|---|
| P1-1 物理瓶颈尚未验证 | 同意。所有 binding 判断仍为 `PENDING_RUN_GATE`；Stage B 按 POI / 上游输电 / ERM / 程序四层的对偶值和单因素放松收益报告，不以"约束存在"为依据 |
| P1-2 压力日不等于 N−1 或合同 Firm 认证 | 已写入 `GREAL_PHYSICAL_MECHANISM_NOTE.md` §3；`stress_line_derate = 1.0`（关闭）；1/r 是研究代理 |
| P1-3 窗口内年金与完整残值 | `tv_share_byop = tv_share_public = 1.0`（隐含完整残值）。这是短期机制演示的约定，S2 / S3 的成本差需注明此假设，**不能据此证明 M3 或长期搁浅** |
| P1-4 技术潜力不等于站旁可装容量 | 已在 `REEDS2_IMPORT_NOTE.md` 中说明；现场上限 `onsite_renewable_cap_MW` 为研究代理（ML13-06） |
| P1-5 PCLR 只是抽样近似 | `poi_ledger` 新增 `pclr_trigger_hours_weighted`、`pclr_curtailed_hours_weighted`、`pclr_max_consecutive_sampled_h`，供 Stage B 按加权全年小时核对 200 小时 / 12 小时；不宣称满足正式 ERCOT 中断产品规则 |
| P1-6 COD 覆盖范围 | 公共发电和输电候选的 `approval_year`（= COD 期 − 工期）写入资产台账（`STATE['approval_year']` → `commit_year`）；`MAINLINE_ASSET_COMMITMENT_LEDGER.csv` 新增 `COD` 和 `cod_basis` 两列，注明这是静态完美前瞻近似，不是年度实际承诺 |
| P1-7 母线级聚合 POI | 已标为电气聚合代理（D12）；同一母线上的多个园区不独立分配合同 |

## 3. 测试结果（无求解器）

L2 静态测试 **21/21 通过**，结构测试 **43/43 通过**，`solver_executions = 0`（3 次求解调用被拦截）。修订提交：`__COMMIT_C__`。

```text
STAGE_A_STATUS: READY_FOR_RESEARCHER_AUDIT (second audit)
RUN_AUTHORIZATION: NOT_APPROVED
SOLVER_EXECUTIONS: 0
NEXT_STEP: RESEARCHER_REVIEW_REQUIRED
```
