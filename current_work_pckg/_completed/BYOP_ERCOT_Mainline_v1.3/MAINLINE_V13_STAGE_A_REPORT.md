# MAINLINE_V13_STAGE_A_REPORT：BYOP ERCOT Mainline v1.3 Stage A 执行报告

- 报告日期：2026-10-21
- 依据：`BYOP_ERCOT_Mainline_Work_Package_v1.3_2026-10-21.md` §8 Stage A（A0–A6）
- 本轮只准备数据和修改代码，**没有运行任何 LP 求解器**。所有与求解结果相关的项目都标为 `PENDING_RUN_GATE`。

## 1. 完成与未完成

| 步骤 | 状态 | 内容 |
|---|---|---|
| A0 基线 | **完成** | 读取了最新 HEAD `be2c6904`（与工作包起草时一致）、`论文顶层设计.md`、参数证据基线、v1.0 决策日志和报告、Epoch 文件<br>新建功能分支 `mainline-v13-stageA`；没有删除任何历史或已有结果<br>上一个工作包（重构 v1.0）的原文和全部 10 份汇报用 `git mv` 移入 `current_work_pckg/_completed/BYOP_ERCOT_Rearchitecture_Work_Package_v1.0/`，L2 同步移动 |
| A1 需求 | **完成** | 8 个母线的 Epoch 接口；D11 存量爬坡对账（460.73 MW 继承 + 105.22 MW 新增 = 2026 年 565.95 MW）；D12 聚合 POI；旧的 3 个场址需求不再叠加；`regional_dc` 和竞争排队负荷关闭；统一企业 LP 接口（`developer_joint`） |
| A2 电网 | **完成（含代理值）** | 建立 G-REAL 证据台账：<br>• 背景负荷对账（AEO2023，不叠加 ERCOT 大负荷预测）<br>• 已承诺工程（DWB2、765 kV 通道）与扩建候选（有成本、有工期）<br>• 8 个 POI（设备行带日期）<br>• 3 个压力日进入 Firm 约束<br>没有为制造指定的拥堵去调参数或跑 LP |
| A3 资源 | **完成** | 本地 `D:\ReEDS2`（eb75a6bc）可以读取，**不是** `MISSING_LOCAL_REEDS2`：<br>• reV 风电和光伏 reference 供给曲线 → 63 个 ERCOT TAMU 母线的剩余潜力（扣除现有和已承诺装机）<br>• 逐时出力沿用 PyPSA-USA<br>• 可复用（R）资产池为空（ReEDS 只有按机龄推算的退役，不能作为证据） |
| A4 模型 | **完成** | 按批准年份分批的 COD；v1.3 技术参数和逐年气价；正常调度与 Firm 信用分开；BESS 用 SOC 建模；现场风光有上限；Fast SOFC = 0；四种供电模式求解后归类；S2 单一开发商 speed-first；S2 与 S3 物理选项相同；运行门控<br>无求解器静态测试和结构测试全部通过（第 3 节） |
| A5 GitHub | **完成**（见 `MAINLINE_V13_RETURN_MANIFEST.md`） | 推送功能分支，**没有合并到 `main`**<br>本机没有 `gh` CLI，PR 需要研究者在 GitHub 上点击创建，链接见 Return Manifest<br>L2 的文件和分支指针与本地一致 |
| A6 强制停止 | **已停止** | `RUN_AUTHORIZATION: NOT_APPROVED`；Stage B 没有执行 |

**没有做的**（v1.3 §9 范围外，或属于 Stage B）：

- 正式求解：S0–S3、ERM / S0 校准、smoke LP
- 2032–2050 年
- 敏感性矩阵
- 合同 C 的交付市场
- 全 AC / N−1
- 天然气管网 LP

## 2. 修改的文件

**模型**（只在 `--mainline` 下生效，v1.0 / v2.4.0 路径不变）：

- `workflow/byop/model/rearch_mech.py`，约 +500 行：
  - `configure_mainline`、`ml_base_build`（压力日）、`add_inherited_ramp`
  - `ml_public_potential` 和 `ml_space`（ReEDS2 共享上限与现场上限）
  - `add_byop_cohorts`（按批准年份分批；正常调度与 Firm 信用分开；BESS 用 SOC）
  - `ml_gas_delta`（逐年气价）
  - POI 升级按批准年份分批；PCLR 优先在压力时段触发
  - `label_mode`、`developer_joint` / `developer_joint_build`
  - `mainline_gate` / `_require_gate`
  - `poi_ledger` 的 B8 / B10 字段
  - `main()` 的 `--mainline` / `--config` 参数
- `workflow/byop/model/v240_mech.py`，约 +70 行：
  - `gas_price`、`approval_cohorts`、`firm_frac`、`byop_params_v13`
  - 常量 `V13_ID`、`NONFIRM_BYOP`、`SOFC_FAST_ELIGIBLE_MW`
  - `serve_cap` 中的 Firm 资格（只计全年在运；风光不计）
  - 台账：燃料按逐年价格计；现场 BESS 计入能量平衡；记录批准年份

**新增程序**：

- `workflow/byop/build/build_mainline_inputs.py`
- `workflow/byop/build/build_reeds2_potential.py`
- `workflow/byop/build/build_mainline_manifest.py`
- `workflow/byop/post/collect_mainline.py`（E3 结果表和 3 张机制图）
- `workflow/byop/run/run_mainline.sh`（唯一运行入口）
- `workflow/config/config.byop_ercot_mainline.yaml`（唯一配置与门控）
- `workflow/byop/tests/test_mainline_v13.py`、`structural_mainline_v13.py`

**新增输入**（逐项来源见 `MAINLINE_V13_DATA_REGISTER.csv`）：

- `inputs/dc/MAINLINE_{RESEARCH_COHORTS_TAMU64, INHERITED_RAMP_2025, AIDC_RECONCILIATION, BUS_SITE_POI_MAP}.csv`
- `inputs/poi/GREAL_{POI_ASSUMPTIONS, POI_E0_SCHEDULE, R_ASSET_POOL}.csv`
- `inputs/grid/GREAL_{GRID_PROJECTS, BACKGROUND_LOAD_RECONCILIATION, NETWORK_EVIDENCE}.csv`、`GREAL_PHYSICAL_MECHANISM_NOTE.md`
- `inputs/grid/{ERCOT_WIND_SOLAR_POTENTIAL, REEDS2_TO_TAMU64, REEDS2_SOURCE_INVENTORY}.csv`、`REEDS2_IMPORT_NOTE.md`
- `inputs/tech/MAINLINE_V13_{TECH_DEFAULTS, GAS_PRICES_2026_2031}.csv`

**文档**：`workflow/byop/README.md`、`workflow/byop/inputs/README.md`、`current_work_pckg/README.md`，以及第 5 节列出的报告。

## 3. 无求解器测试（`SOLVER_EXECUTIONS: 0`）

| 测试 | 结果 |
|---|---|
| 静态测试 `test_mainline_v13.py`（v1.3 §7 E2 的 12 项 QA 全覆盖） | L2：**21 / 21 通过**（`results/BYOP/mainline/static_tests.log`；含审计 P0-1..5 / P1 新增的 5 项）<br>本地（没有 pypsa）：6 项纯输入测试通过，其余跳过 |
| 结构测试 `structural_mainline_v13.py`：构建 G-REAL 的 S0 / S1_EARLIEST / S3 / S2 开发商四个 linopy 模型，只检查、不求解 | L2：**43 / 43 通过**（含审计新增的 QA-P0-4、QA-P0-5）<br>3 次求解调用被拦截，`solver_executions = 0`<br>文件：`results/BYOP/mainline/_structural/STRUCTURAL_CHECKS.csv`、`STRUCTURAL_REPORT.json` |
| 运行门控 | `rearch_mech.py --mainline` 以退出码 3 拒绝，在构建任何网络之前（`results/BYOP/mainline/_gate_test/RUN_GATE.json`） |
| 汇总程序冒烟测试（合成数据） | 7 个表和 3 张图全部生成 |

结构测试中的关键事实（属于模型输入的结构，不是求解结果）：

- **压力日**：基准年时间序列（2025 ERCOT 负荷 + PyPSA-USA 风光出力）中的 9 月 15 日（West 风电最低、高负荷）、7 月 31 日（净负荷最高）、2 月 19 日（冬季峰值）。
  - 网络时间戳沿用 PyPSA-USA 的 2030 年标签。
  - 3 天共 24 个时段，都不在原来的抽样周内，所以作为新时段加入；每期权重合计 8,760 小时。
- **燃气**：76 台燃气机组按逐年价格重新定价。
- **COD**：
  - RICE 最早 COD：L1 气源 2028 年，L2 气源 2029 年；
  - SOFC 标准型最早 2029 年；
  - POI 升级最早 2029 年；
  - 2029 年批准的 RICE 在 2029 / 2030 年不能出力。
- **出力与 Firm**：RICE 正常时段可用率 1.0，压力时段 0.8（= 1/1.25）；`serve_cap` 只计燃气 BYOP 的 Firm 信用，不计风光。
- **其他**：光伏夜间出力为 0；BESS 为 4 小时、往返效率 0.85、按期循环 SOC。
- **模型规模**：S3 有 4.39 M 变量、7.56 M 约束；S2 开发商模型有 0.13 M 变量。
- **整数变量**：四个模型均为 0。

## 3a. 独立审计后的修订（2026-10-21）

研究者方的独立审计（`BYOP_Mainline_v1.3_StageA_Independent_Audit_2026-10-21.md`，被审计 HEAD `efca9d0a`）提出 P0-1 至 P0-5，已全部修复；P1-1 至 P1-7 已披露并补充核验字段。逐项说明见 `MAINLINE_V13_AUDIT_RESPONSE.md`。修订提交：`85fa823d8e3e5034aea4774bdc3a8db63e858ab8`。

## 4. 阻塞项与需要研究者处理的事项

- **没有阻止审计的阻塞项**。
- 9 项 `REVIEW_REQUIRED`（ML13-01..09），每项都附推荐方案，见 `MAINLINE_V13_DECISION_LOG.md`。影响最大的三项：
  - ML13-01：已有园区的 POI 设备容量代理值；
  - ML13-02：Shackelford 是接网还是离网；
  - ML13-05：Abilene 现场既有燃机是否录入。
- **PR 尚未创建**：本机没有 `gh` CLI。研究者在 GitHub 上用 Return Manifest 中的链接创建即可，不需要合并。
- **Stage B 需要研究者操作**：在 `config.byop_ercot_mainline.yaml` 中写入 `run_authorization: APPROVED` 和审计过的 `approved_git_sha`。之后依次执行 `bash byop/run/run_mainline.sh gate`、`step0`、`run`。

## 5. 报告文件

- `MAINLINE_V13_PRE_RUN_AUDIT.md`
- `MAINLINE_V13_PARAMETER_CROSSWALK.md`
- `MAINLINE_V13_DATA_REGISTER.csv`
- `MAINLINE_V13_DECISION_LOG.md`
- `MAINLINE_V13_PRE_RUN_MANIFEST.json`
- `MAINLINE_V13_RETURN_MANIFEST.md`
- `MAINLINE_V13_TECH_DEFAULTS.csv`、`MAINLINE_V13_GAS_PRICES_2026_2031.csv`（工作包附件，已导入 `workflow/byop/inputs/tech/`）

```text
STAGE_A_STATUS: READY_FOR_RESEARCHER_AUDIT
RUN_AUTHORIZATION: NOT_APPROVED
SOLVER_EXECUTIONS: 0
GITHUB_HEAD: 85fa823d8e3e5034aea4774bdc3a8db63e858ab8 (branch mainline-v13-stageA; audit P0 fixes; first Stage A code commit edc5ed8c09eed4920693e1e9eef2a6545c30018f)
NEXT_STEP: RESEARCHER_REVIEW_REQUIRED
```
