# BYOP ERCOT Mainline v1.3 — Stage A 独立代码审计

**审计时间：** 2026-10-21  
**GitHub：** https://github.com/simonyed/BYOP/tree/mainline-v13-stageA  
**被审计 HEAD：** `efca9d0a9bf4e5777fc5db4c0a92b9b46b604dd0`  
**相对 main 基线：** `be2c6904cb203822c9f5a36e57bf10ebaf6d159e`；领先 2 个提交。  
**依据：** `current_work_pckg/BYOP_ERCOT_Mainline_Work_Package_v1.3_2026-10-21.md`、`workflow/byop/docs/论文顶层设计.md`。  
**审计范围：** GitHub 上可读的源代码、CSV、配置、报告与结构检查记录。不能访问 L2 的未跟踪 `.nc` 及 Windows `D:\ReEDS2` 原始文件；**没有重跑 Linopy 建模或 Gurobi 求解**。

## 一、结论

**Stage A 主体完成，但建议维持 `RUN_AUTHORIZATION: NOT_APPROVED`；先对 5 个问题进行小规模修复/审计，再批准 Stage B。** 目前静态/结构日志里的 16/16、41/41 是执行方的测试结果，并非最优性、经济性或数值正确性的证明。

**已落实的核心：** Epoch AI 8 个母线需求作为正式研究 cohort（与旧 3 个 POI 需求不叠加）；D11 继承爬坡与新增需求互斥；单一联合开发商 LP；G-REAL 网络、三组压力时段；纯连续 LP；新技术和 gas CSV；BYOP 与 POI 逐审批年份 COD；本地 ReEDS2 导出风光潜力；未获批的求解器阻断与 GitHub 交付。以上源代码和文档确实存在，不能因以下问题否定 Stage A 工作。

## 二、运行前建议必须修复/确认（P0）

### P0-1. 继承爬坡负荷切负荷没有完整进入社会成本账本

- `workflow/byop/model/rearch_mech.py` 的 `add_inherited_ramp()` 将 460.73 MW IT 的继承爬坡建为背景 `Load` + `carrier='load_shed'` 的专用切负荷机组；`extra_rearch()` 的 no-harm 限制已涵盖所有 `load_shed`，这点正确。
- 但是 `workflow/byop/model/v240_mech.py` 的 `ledgers()` 计算 `shed` 使用 `n.generators_t.p[[f'{z} load_shed' for z in ZONES]]`，只计通常的各母线背景切负荷，**不包括** `p610 2 inherited_ramp_unserved` 等继承负荷切除。因此 `scenario_summary` 的 `load_shed_MWh`、`load_shed_PV_USD` 以及基于它们的 `social_real_resource_cost_USD`、`existing_customer_shed_loss_VOLL_PV_USD` 漏计这部分潜在损失。
- **建议：** 在 mainline 路径按 carrier=`load_shed` 汇总并分别列出 `native_background_unserved` 与 `inherited_ramp_unserved`；避免因审计输出漏计而把基准系统显得比实际更可靠。增加不调用求解器的合成账本测试，核对两类切负荷会计一致。

### P0-2. 必需的 M4 同服务量对比目前不会随正式主命令执行

- `workflow/config/config.byop_ercot_mainline.yaml` 只配置 `[S0, S1_EARLIEST, S3, S2]`；`workflow/byop/run/run_mainline.sh` 没有为正式运行添加 `--scenarios ... S3_mS2`。
- `workflow/byop/model/rearch_mech.py` 只在 `'S3_mS2' in a.scenarios` 条件满足时运行同服务协调规划；`workflow/byop/post/collect_mainline.py` 也只在有该情景时生成 `MAINLINE_MATCHED_SERVICE_COST.csv`。
- **建议：** 主运行显式包含 `S3_mS2`（仅增加一个既有的 LP 检查情景，而非敏感性矩阵）；确保同一需求、同一物理候选、同一服务轨迹、资源费用口径一致后才计算 S2–S3 社会效率差异。四个 S0–S3 仍是论文主情景。

### P0-3. 六个 POI 的 E0 代理值可能把未来工程资格错误提前到 2026

- `workflow/byop/inputs/poi/GREAL_POI_E0_SCHEDULE.csv` 将 Google Red Oak、Temple、Midlothian、Vantage、Microsoft SAT14、Denton 等多项设备能力直接赋为 `preapproved=True, COD=2026`，部分数值来自 Epoch **最终规划设施容量减 2025 年末存量**，未必是经认证的当前 POI 进口权利。
- `workflow/byop/model/rearch_mech.py` 的 `eq_terms()` 把这些行直接累加并形成可用设备容量，进而使这些母线不经历相应的 POI 升级和程序时滞。它尤其影响 M1 的延期空间分布，不是仅影响估算精度的无害代理。
- **建议：** 逐行复核 `E0` 为“物理现有/已认证进口权利”还是“未来规划负荷规模”。不能以 Epoch 最终 MW 自动证明 2026 的 Firm 进口；未知部分可以保留一个**有界且明确的研究代理**，分开已有、经核实承诺及拟建/未知，并给最早可用年。最小修复不需增加园区级 POI 或审批状态机。
- 用户需审计的 ML13-01/02/03/04/05 主要围绕此项；不得为产生 BYOP 优势而一律将 E0 改为 0。

### P0-4. Firm 电网报价应核实“最大发电潮流”不等于“经压力时段认证的 Firm 进口资格”

- `rearch_mech.py::s1_offer()` 使用 `max(S1 实际 POI 进口流量)` 形成每场址每年的 `offer_firm_MW`。这是已求解 S1 调度下的最高实际进口，而非自动等价于**所有必要压力时段可共同承诺的 Firm 进口上限**。
- `developer_joint()` 将其用于企业模型，后由 S2 公共 LP 复核，最多三轮反馈。该机制已比无限网购好，但仍需要检查是否在初始阶段过度或不足报价，是否出现 `S2_consistency.csv` 未收敛，以及共享公共可靠容量是否被两阶段分别承诺。
- **建议：** 保持 LP，不新建市场模型；用 S1 的联合应力小时和 POI/ERM 约束明确 Firm 额度的物理含义，检查同一年 8 母线的同步供电义务。至少让 Stage B 检查 `S2_consistent=True`、并在不收敛时拒绝科学结论，不能仅从各年实际进口最大值宣称获得真实 Firm 合同。

### P0-5. S0 校准可能未包含继承爬坡负荷的高可靠性要求

- `rearch_mech.py::build_rearch()` 中 `add_s0_calibration(n, scen)` **先于** `add_inherited_ramp(n)` 调用。
- S0 最小增容校准会把当时已有的 `load_shed` 惩罚提高到 `S0CAL_SHED=1e8 USD/MWh`，以消除合成网络的背景缺口；但稍后新加的 `*_inherited_ramp_unserved` 仍用 `M.SHED_COST=1e4`，可能被模型在校准中廉价切除。这与报告所称“包含 2025 年末继承爬坡的共同 S0 校准”**不一致**，且叠加 P0-1 的损失汇总漏计，会低估基线问题。
- **建议：** 确保校准专用的高切负荷惩罚覆盖 native background **和** inherited ramp 的所有 `load_shed`；可调整构建顺序或仅在校准模式更新新增机组的成本，无需改变正式运行的 VOLL 参数。增加不调用求解器的模型构建检查，断言 S0 校准下全部背景切负荷机组处罚一致。

## 三、需如实披露但可在 Stage B 结合求解验证（P1）

1. **物理瓶颈是否真的导致延期仍未验证。** G-REAL 已有 KVL、ERM、POI、压力快照，但全部只构建未优化。原远西部证据不宜套用全部 8 个 Epoch bus；既有 `p630 4` 与 `p610 2` 的 POI 数据代理可能主导速度收益。需要按 Stage B 结果报告 POI/上游/ERM/程序层的实际约束活跃与单因素放松收益，不能仅据“约束存在”宣称机制成立。
2. **当前压力日是真实气象日，但不是完整 N−1 或合同 Firm 认证。** `stress_line_derate=1.0` 表示线路降额关闭；燃气现场机组在压力快照统一 `1/r` 是研究代理而非逐设备事故计算。维持 LP 可以，但报告中要披露。
3. **短期成本采用窗口内年金并隐含完整残值。** `v240_mech.py::tv_factor()` 的默认参数 `tv_share_byop=tv_share_public=1.0`，未将 2031 以后的剩余年金作为负担；这对“短期速度机制示范”可作为明示约定，但不能据此声称证明长期搁浅或 M3。S2/S3 的成本差应注明此假设；后续长期扩展时再处理真实资本承诺和残值。
4. **“风光技术潜力”不是“数据中心旁可立即安装容量”。** ReEDS2 对 ERCOT 得出约 834 GW 风和 9,400 GW 光的技术潜力，站点层的上限来自 `onsite_renewable_cap_MW = 1×2031研究设施MW` 研究代理。不能把它当真实场址土地或接入额度；不需要此时开展 GIS 站点规划。
5. **PCLR 时数仅为离散样本/触发近似。** `select_triggers()` 用采样快照数量来近似 200h，且先选压力时段；未来需要在 Stage B 以加权全年小时核验实际中断总时数及连续性，不宣称已经满足全部正式 ERCOT 中断产品规则。
6. **COD 修复的覆盖范围需归档。** BYOP 和 POI 升级采用审批 cohort 并有直接检查；公共线和发电候选采用按“COD 年份”建立候选、用 lead 反推批准年，静态完美前瞻近似应在资产表中显式记录，避免解释为年度实际承诺。重点确认 `ASSET_COMMITMENT_LEDGER` 的 `approval_year`、`COD` 对公共资产正确。
7. **8-bus 聚合 POI 共享资格是简化。** `eq_terms()` 允许母线级设备容量求和，并不能保证同 bus 多园区合同间独立分配。符合当前“不增加园区级博弈”的原则，但必须标记为电气聚合代理。

## 四、已通过的 Stage A 项目（根据可读代码与执行记录）

| 工作包 | 状态 | 实质证据 |
|---|---|---|
| AIDC 8-bus + D11 防重计 | 已实施并有输入对账 | 2026 mid 已批准 565.951 MW = 460.730 MW 继承 + 105.221 MW 研究新增；S0 无研究新增，旧三 POI 不叠加。 |
| 一个联合 S2 开发商 | 结构完成，未求解 | `developer_joint_build()` 构造一个包含 8 个 DC bus 的 Linopy 模型；按年度字典序容量后最小私人成本，无 S2 max-min。 |
| G-REAL / B7 压力 | 结构完成，binding 待跑 | 3 个压力日 × 每年 24 快照；KVL 与 ERM 已存在。 |
| BYOP 六种主技术及 COD | 已实施并过测试 | 新 TECH/GAS CSV、RICE 热耗8381、SOFC 标准 3y、Aero、BESS SOC、ReEDS2 风光上限、按批准年份分批。 |
| 严格 LP | 已做结构检查 | 四模型 0 integer；报告 S0 4.07M / S1 4.15M / S3 4.39M / S2 开发商 0.13M 变量。 |
| Stage A 先 GitHub、后批准 | 已落实 | `mainline_gate()` 及配置 `run_authorization: NOT_APPROVED`；分支未合并主分支，未跑正式优化。 |
| Stage B 输出 | 已写后处理程序，未由真实解验证 | 单母线交付、BYOP 供电方式、资产台账、公共扩张等表；matched-service 因 P0-2 的情景缺失目前不触发。 |

## 五、建议下一轮给 Claude/Codex 的最小修订指令

1. 在同一个 `mainline-v13-stageA` 分支**只修 P0-1～P0-5**；优先修客观程序错误 P0-1、P0-2，再对 E0 与 Firm 报价出最小证据及验收补丁。
2. 不新增 MILP、园区间竞争、气网 LP、完整 N−1、长期情景矩阵；不为制造非零 BYOP 而故意改变线路容量。
3. 将新增测试写进 `test_mainline_v13.py` / `structural_mainline_v13.py`；仍**不得调用 LP 求解器**。修订现有 Stage A 审计、决策表、输入和 manifest，并推送到 GitHub。
4. 继续保持 `RUN_AUTHORIZATION: NOT_APPROVED`。研究者完成第二次审计前**不执行 `run_mainline.sh step0` 或 `run`**。
5. 本文件是独立代码审查结果，**未修改 GitHub，也未授权计算**。

