# RETURN_FILE_MANIFEST — 交付文件清单（2026-10-20）

依据 `BYOP_ERCOT_RUN_DECISION_AND_CORRECTION_PLAN_2026-10-20.md` 第 7.3 节编制。
- “GitHub 状态”指 `simonyed/BYOP` 的 `main` 分支。本清单与列出的文件在同一次提交中推送，提交 SHA 见回复。
- 可复现信息：代码版本以 git 提交和每个算例目录下的 `code/` 快照为准，输入哈希见各 `case_manifest.json`；本轮运行记录见 `workflow/results/BYOP/rearch/BASELINE_DIAGNOSTIC.md`。

## 1. 报告与研究者文件（`current_work_pckg/`）

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `current_work_pckg/BYOP_ERCOT_Rearchitecture_Work_Package_v1.0_2026-10-20.md` | 工作包原文（研究者） | 已生成 | 已同步 | — | 27.0 KB | 7cea22a55a18f8a5 |
| `current_work_pckg/BYOP_ERCOT_RUN_DECISION_AND_CORRECTION_PLAN_2026-10-20.md` | 研究者运行决策 | 已生成 | 已同步 | — | 17.0 KB | 98b0e3f0e642d1a9 |
| `current_work_pckg/BYOP_ERCOT_P0_RESEARCHER_DECISIONS_2026-10-20.md` | 研究者 P0 决策 | 已生成 | 已同步 | — | 14.7 KB | c33b6c5347d7e5a4 |
| `current_work_pckg/DECISION_LOG_REARCHITECTURE.md` | 决策日志（含 P0/D1–D3 落实） | 已生成 | 已同步 | — | 15.3 KB | cd13f44bee59be6e |
| `current_work_pckg/INTERIM_PROGRESS_REPORT_2026-10-20.md` | 中期进度报告 | 已生成 | 已同步 | — | 14.1 KB | 0f15cfc2f0679f5f |
| `current_work_pckg/P0_MODEL_CORRECTION_PROPOSAL.md` | P0 修正方案 | 已生成 | 已同步 | — | 13.1 KB | edda62a3fa046ca7 |
| `current_work_pckg/POST_RUN_DIAGNOSTIC_REPORT_FOR_PUBLISHER.md` | 本轮诊断报告 | 已生成 | 随本次提交同步 | — | 11.6 KB | 09485f232336730e |
| `current_work_pckg/GITHUB_SYNC_EXECUTION_REPORT.md` | GitHub 同步规则报告 | 已生成 | 已同步 | — | 15.4 KB | 1165c1199ad5f81a |
| `current_work_pckg/EXECUTION_REPORT_FOR_PUBLISHER.md` | 工作包最终执行报告（R2 完成后编写） | 未生成 | — | — | — | — |

## 2. 代码与配置

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `workflow/byop/model/rearch_mech.py` | 模型：TAMU + POI + S2 + P0 | 已生成 | 已同步 | — | 78.0 KB | 46d3becc88cf98bb |
| `workflow/byop/model/v240_mech.py` | 模型：S0–S3 LP 基础 | 已生成 | 已同步 | — | 63.9 KB | 7dc50ce788939ffd |
| `workflow/byop/model/v250_mech.py` | 模型：TX ERM 汇总 | 已生成 | 已同步 | — | 23.1 KB | 8809a2dcf5921bc4 |
| `workflow/byop/build/build_2025_baseline_tamu.py` | 2025 基准构建器 | 已生成 | 已同步 | — | 30.3 KB | a4059f84a2ff18de |
| `workflow/byop/post/collect_rearch.py` | 结果汇总 | 已生成 | 已同步 | — | 13.9 KB | 7cb5a936697900fe |
| `workflow/byop/run/run_rearch.sh` | 运行入口 | 已生成 | 已同步 | — | 4.2 KB | 27c4d4df290e7581 |
| `workflow/byop/tests/test_rearch_units.py` | 单元测试（WP-C，8 项） | 已生成 | 已同步 | — | 7.2 KB | f1b5b99ad111ef3b |
| `workflow/byop/tests/test_p0_units.py` | 单元测试（P0，6 项） | 已生成 | 已同步 | — | 8.6 KB | bc96d0e5ba2c4d73 |
| `workflow/config/config.byop_ercot_tamu.yaml` | TAMU 64 节点配置 | 已生成 | 已同步 | — | 2.2 KB | 3c2dda9b1a7229a6 |
| `workflow/scripts/prepare_network.py` | PyPSA-USA 补丁（WIND-01 回退） | 已生成 | 已同步 | — | 15.9 KB | 4c1173357f139c20 |
| `workflow/byop/README_REARCHITECTURE.md` | 运行说明 | 已生成 | 已同步 | — | 3.5 KB | 271b09dfaf8f2b89 |

## 3. 输入参数

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `workflow/byop/inputs/poi/POI_REGISTER.csv` | POI 登记表（四层可交付能力、气源证据） | 已生成 | 已同步 | — | 4.2 KB | d2f37909d559e165 |
| `workflow/byop/inputs/poi/POI_REQUESTS.csv` | 程式化请求 | 已生成 | 已同步 | — | 0.3 KB | 737d808551f9220e |
| `workflow/byop/inputs/poi/GRID_PROJECTS.csv` | PBRP 765 kV（G-U） | 已生成 | 已同步 | — | 0.9 KB | bb05fdc167688524 |
| `workflow/byop/inputs/poi/SOURCE_EVIDENCE_REGISTER.csv` | 证据登记表 SRC-01..20 | 已生成 | 已同步 | — | 9.0 KB | bfbc3c626eba98a9 |
| `workflow/byop/inputs/grid/TPIT_FARWEST_EVIDENCE_LEDGER.csv` | TPIT 远西部证据台账（D3 Step 1） | 已生成 | 已同步 | — | 141.8 KB | c632fd9ca02a3bb2 |
| `workflow/byop/inputs/grid/COMMITTED_BASE_ASSETS.csv` | 已承诺基准资产（主情景 / 敏感性） | 已生成 | 已同步 | — | 1.8 KB | a9aa717865910c65 |
| `workflow/byop/inputs/grid/TPIT_2026-07-13_project_register_v250.csv` | TPIT 原始登记（2026-07-13） | 已生成 | 已同步 | — | 967.3 KB | b7697cc9d57ed153 |

## 4. 网络与 2025 基准审计

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_audit.json` | 基准审计 | 已生成 | 已同步 | — | 6.2 KB | 993fb0f7bca72e58 |
| `workflow/results/BYOP/baseline_2025_tamu/NETWORK_MAPPING_AUDIT.csv` | 网络映射审计 | 已生成 | 已同步 | — | 371.9 KB | dffd4a67b15646ad |
| `workflow/results/BYOP/baseline_2025_tamu/INTERFACE_AUDIT.csv` | 接口审计 | 已生成 | 已同步 | — | 1.1 KB | b7b02c7f0244999d |
| `workflow/results/BYOP/baseline_2025_tamu/LINE_LEDGER.csv` | 线路台账 | 已生成 | 已同步 | — | 29.2 KB | f449ca89298db2de |
| `workflow/results/BYOP/baseline_2025_tamu/BUS_LEDGER.csv` | 母线台账 | 已生成 | 已同步 | — | 11.5 KB | 0a7cb15878a81ac5 |
| `workflow/results/BYOP/baseline_2025_tamu/TAMU_2025_CALIBRATION_LP.csv` | 2025 校准 | 已生成 | 已同步 | — | 2.1 KB | 44fbcf7941743cc4 |
| `workflow/results/BYOP/baseline_2025_tamu/COUNTY_TO_BUS_SHARES.csv` | 县→母线映射 | 已生成 | 已同步 | — | 20.4 KB | 6946ddd4fe03a885 |
| `workflow/results/BYOP/baseline_2025_tamu/network_map.png` | 网络图 | 已生成 | 已同步 | — | 261.9 KB | 59453188881a8457 |

## 5. 第一轮算例输出（BASELINE_DIAGNOSTIC）

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `workflow/results/BYOP/rearch/ERM_CAL_GW/erm02_calibration.json` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | ERM_CAL_GW / rearch_ERM_CAL_GW_20261020T162526Z | 1.0 KB | f4f83e4509daeba3 |
| `workflow/results/BYOP/rearch/ERM_CAL_GW/events.jsonl` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | ERM_CAL_GW / rearch_ERM_CAL_GW_20261020T162526Z | 0.4 KB | 40c0af81abae2beb |
| `workflow/results/BYOP/rearch/ERM_CAL_GK/erm02_calibration.json` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | ERM_CAL_GK / rearch_ERM_CAL_GK_20261020T162526Z | 1.0 KB | 9730fa054db22c7f |
| `workflow/results/BYOP/rearch/ERM_CAL_GK/events.jsonl` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | ERM_CAL_GK / rearch_ERM_CAL_GK_20261020T162526Z | 0.4 KB | e82dfb7eeb4e3dea |
| `workflow/results/BYOP/rearch/DEV_GU/case_manifest.json` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 8.7 KB | 5608f70fd81b388c |
| `workflow/results/BYOP/rearch/DEV_GU/scenario_summary.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 5.3 KB | 821dd2bee9faf52e |
| `workflow/results/BYOP/rearch/DEV_GU/service.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 31.1 KB | 8f1b166db7ecce76 |
| `workflow/results/BYOP/rearch/DEV_GU/ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 685.2 KB | 37317c0320cf8a8d |
| `workflow/results/BYOP/rearch/DEV_GU/poi_ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 22.4 KB | de3cd755433f07cc |
| `workflow/results/BYOP/rearch/DEV_GU/poi_upgrade_ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 3.3 KB | 13a4b704e1f01f27 |
| `workflow/results/BYOP/rearch/DEV_GU/S1_GRID_OFFER.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 1.0 KB | 14d640ddfc1f6017 |
| `workflow/results/BYOP/rearch/DEV_GU/S2_developer_modes.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 5.2 KB | 63940e7e25a3d449 |
| `workflow/results/BYOP/rearch/DEV_GU/S2_consistency.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 1.5 KB | bdd5c6319161cd77 |
| `workflow/results/BYOP/rearch/DEV_GU/events.jsonl` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 2.2 KB | d790a6e391a456c6 |
| `workflow/results/BYOP/rearch/DEV_GU/rearch_solver.log` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 276.1 KB | 3c0f11612f3513cf |
| `workflow/results/BYOP/rearch/DEV_GU/solver_S2.log` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | DEV_GU / rearch_DEV_GU_20261020T162802Z | 13.5 KB | f155d41825a45912 |
| `workflow/results/BYOP/rearch/R1_GW/case_manifest.json` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 9.4 KB | cb99e8643a9be24a |
| `workflow/results/BYOP/rearch/R1_GW/scenario_summary.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 7.6 KB | f53c5d7ac50b1ca4 |
| `workflow/results/BYOP/rearch/R1_GW/service.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 53.8 KB | b92b2d74e9e9c127 |
| `workflow/results/BYOP/rearch/R1_GW/ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 471.4 KB | 024974966a512667 |
| `workflow/results/BYOP/rearch/R1_GW/poi_ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 36.3 KB | a6b1d92bc3cabe3d |
| `workflow/results/BYOP/rearch/R1_GW/poi_upgrade_ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 5.4 KB | 093888ce81c3cd06 |
| `workflow/results/BYOP/rearch/R1_GW/S1_GRID_OFFER.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 0.9 KB | f3e32e5c3c9d8e18 |
| `workflow/results/BYOP/rearch/R1_GW/S2_developer_modes.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 5.2 KB | 4b45d44f92519bc9 |
| `workflow/results/BYOP/rearch/R1_GW/S2_consistency.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 1.5 KB | 6bda265da2eb6126 |
| `workflow/results/BYOP/rearch/R1_GW/events.jsonl` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 3.5 KB | 4c88b8da396ac4a7 |
| `workflow/results/BYOP/rearch/R1_GW/rearch_solver.log` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 104.1 KB | 8c1aa95ebd780696 |
| `workflow/results/BYOP/rearch/R1_GW/solver_S2.log` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GW / rearch_R1_GW_20261020T174558Z | 13.7 KB | 93adf1d9cab84274 |
| `workflow/results/BYOP/rearch/R1_GK/case_manifest.json` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 9.5 KB | d3e43cfcff2bb3b8 |
| `workflow/results/BYOP/rearch/R1_GK/scenario_summary.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 7.9 KB | a36d48e26edcf662 |
| `workflow/results/BYOP/rearch/R1_GK/service.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 56.0 KB | cf9f75840ac9eff2 |
| `workflow/results/BYOP/rearch/R1_GK/ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 657.6 KB | ddeaed258a4386a3 |
| `workflow/results/BYOP/rearch/R1_GK/poi_ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 37.1 KB | 709eb0dc485804ca |
| `workflow/results/BYOP/rearch/R1_GK/poi_upgrade_ledger.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 5.4 KB | 6e6bfd4fa683a399 |
| `workflow/results/BYOP/rearch/R1_GK/S1_GRID_OFFER.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 1.0 KB | 0dac11796f07a7e2 |
| `workflow/results/BYOP/rearch/R1_GK/S2_developer_modes.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 5.2 KB | ad79360190551819 |
| `workflow/results/BYOP/rearch/R1_GK/S2_consistency.csv` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 1.5 KB | b32e6dd14d586e16 |
| `workflow/results/BYOP/rearch/R1_GK/events.jsonl` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 3.5 KB | 4458f1778e1be3a4 |
| `workflow/results/BYOP/rearch/R1_GK/rearch_solver.log` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 104.1 KB | 553aedfc54d94910 |
| `workflow/results/BYOP/rearch/R1_GK/solver_S2.log` | 运行输出（BASELINE_DIAGNOSTIC） | 已生成 | 已同步 | R1_GK / rearch_R1_GK_20261020T174558Z | 17.0 KB | ca21df8203340ba2 |

## 6. 汇总表

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `workflow/results/BYOP/rearch/_collected/POI_DELIVERABILITY_LEDGER.csv` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 108.3 KB | 37e639fa242c0949 |
| `workflow/results/BYOP/rearch/_collected/DELAY_ATTRIBUTION.csv` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 6.4 KB | 0b72abcd29621301 |
| `workflow/results/BYOP/rearch/_collected/ASSET_COMMITMENT_LEDGER.csv` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 542.2 KB | 5f8bec8cc866bef7 |
| `workflow/results/BYOP/rearch/_collected/SCENARIO_COMPARISON.csv` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 15.2 KB | b85b00df1a511af5 |
| `workflow/results/BYOP/rearch/_collected/SCENARIO_DIFFERENCES.csv` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 2.0 KB | d69126c9c880ba51 |
| `workflow/results/BYOP/rearch/_collected/GATE_CHECKS.csv` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 3.3 KB | c68ee29cd2bf0cde |
| `workflow/results/BYOP/rearch/_collected/served_trajectories.png` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 231.5 KB | e46201d954f1c3c8 |
| `workflow/results/BYOP/rearch/_collected/delay_attribution.png` | 汇总表 / 图（BASELINE_DIAGNOSTIC） | 已生成 | 随本次提交同步 | — | 60.0 KB | bc587a47bfba2646 |

## 7. 运行记录、单元测试与 S0 修复

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `workflow/results/BYOP/rearch/BASELINE_DIAGNOSTIC.md` | 本轮运行记录与诊断标识 | 已生成 | 随本次提交同步 | — | 3.0 KB | ece0170804ba31e2 |
| `workflow/results/BYOP/rearch/unit_tests.log` | 单元测试日志（8 项通过） | 已生成 | 已同步 | — | 0.9 KB | 64048330f65d3b2c |
| `workflow/results/BYOP/rearch_s0repair/S0D_none/shed_by_bus_S0.csv` | S0 修复：无基准资产时的切负荷（G-W 2026–29） | 已生成 | 已同步 | — | 0.8 KB | 61e87c8b5acb9fb7 |
| `workflow/results/BYOP/rearch_s0repair/S0D_main/shed_by_bus_S0.csv` | S0 修复：加入 DWB Stage 2 后的切负荷 | 已生成 | 已同步 | — | 0.9 KB | d7de2310c393044a |
| `workflow/results/BYOP/rearch_s0repair/S0D_sens/shed_by_bus_S0.csv` | S0 修复：加入敏感性项目后的切负荷 | 已生成 | 已同步 | — | 0.9 KB | 16bdafa5b6301370 |
| `workflow/results/BYOP/rearch_s0repair/S0CAL_minuplift_2026_2031/S0_CALIBRATION.csv` | S0 最小增容校准（7 条线，571 MW） | 已生成 | 随本次提交同步 | — | 21.6 KB | 74044bb384909fe4 |
| `workflow/results/BYOP/rearch_s0repair/S0CAL_minuplift_2026_2031/case_manifest.json` | S0 校准 manifest | 已生成 | 随本次提交同步 | — | 6.7 KB | 9420b7b8ab543862 |
| `workflow/results/BYOP/rearch_s0repair/S0CAL_try1_REJECTED_economic_uplift/S0_CALIBRATION.csv` | 作废的第一次校准（11 GW，存档） | 已生成 | 已同步 | — | 21.8 KB | f9776d837337e529 |

## 8. 未同步到 GitHub 的大文件（保留在 L2，按既定的大文件管理规则）

| L2 路径（`/datasets/prgm/BYOP_impact/pypsa-usa/workflow/` 下） | 大小 | SHA-256（前 16 位） | 未同步原因 |
|---|---|---|---|
| `results/BYOP/rearch/DEV_GU.log` | 532.2 MB | 9d8dc614a952a919 | 控制台日志超过 5 MB（摘录 `*.excerpt.log` 已同步） |
| `results/BYOP/rearch/ERM_CAL_GK.log` | 43.2 MB | 266d25dbe12f8bbd | 控制台日志超过 5 MB（摘录 `*.excerpt.log` 已同步） |
| `results/BYOP/rearch/ERM_CAL_GW.log` | 43.2 MB | b994aa9cf539eee8 | 控制台日志超过 5 MB（摘录 `*.excerpt.log` 已同步） |
| `results/BYOP/rearch/G1_S0_GW.log` | 43.2 MB | 674dbf87967c8129 | 控制台日志超过 5 MB（摘录 `*.excerpt.log` 已同步） |
| `results/BYOP/rearch/R1_GK.log` | 573.7 MB | 825c9a72c041e8ae | 控制台日志超过 5 MB（摘录 `*.excerpt.log` 已同步） |
| `results/BYOP/rearch/R1_GW.log` | 573.7 MB | 76d72794613641d2 | 控制台日志超过 5 MB（摘录 `*.excerpt.log` 已同步） |
| `results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc` | 6.1 MB | 19034285be0aa9b9 | 网络文件（.nc 被忽略） |
| `results/BYOP/baseline_2025_tamu/baseline_2025_tamu_raw_uncalibrated.nc` | 6.1 MB | 7103e6e0966e7494 | 网络文件（.nc 被忽略） |
| `resources/BYOP_ERCOT_TAMU/networks/texas/elec_s_c64s_ec_lv1.0_REM-ERM-3h_E.nc` | 5.8 MB | 78ec376e6e9dc7df | 网络文件（.nc 被忽略） |
| 各算例目录下的 `code/` | — | 见 `BASELINE_DIAGNOSTIC.md` | 程序快照（被忽略；代码在 git 中，哈希已记录） |
| `workflow/data/byop/`（原始 ReEDS 与 ERCOT 负荷数据） | 8.5 MB | — | 原始数据，可能有使用限制（被忽略） |

## 9. 未生成的文件

- `results/BYOP/rearch/R1_GU/`：按研究者决定不运行（DEV_GU 不含延迟归因）。
- 非计划中断价格计算表与分账记录：已在第 10 节 `_collected/` 中生成。

## 10. P0 修正后的正式结果（`rearch_p0`，2026-10-21）

| 文件路径 | 用途 | 生成状态 | GitHub 状态 | 算例 / run | 大小 | SHA-256（前 16 位） |
|---|---|---|---|---|---|---|
| `current_work_pckg/EXECUTION_REPORT_FOR_PUBLISHER.md` | 工作包最终执行报告 | 已生成 | 随本次提交同步 | — | 16.5 KB | 6aa4d3343123bf0a |
| `workflow/results/BYOP/rearch_p0/S5_GK/case_manifest.json` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 13.2 KB | d9583b414ea65b07 |
| `workflow/results/BYOP/rearch_p0/S5_GK/scenario_summary.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 6.2 KB | d1c7004aab36c182 |
| `workflow/results/BYOP/rearch_p0/S5_GK/service.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 22.5 KB | d098173637a55cb0 |
| `workflow/results/BYOP/rearch_p0/S5_GK/ledger.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 192.7 KB | 9f636f017ac60801 |
| `workflow/results/BYOP/rearch_p0/S5_GK/poi_ledger.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 21.6 KB | d1f42e785902f92d |
| `workflow/results/BYOP/rearch_p0/S5_GK/poi_upgrade_ledger.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 0.0 KB | 01ba4719c80b6fe9 |
| `workflow/results/BYOP/rearch_p0/S5_GK/S1_GRID_OFFER.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 0.6 KB | 355ea132a33c15b8 |
| `workflow/results/BYOP/rearch_p0/S5_GK/S2_developer_modes.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 4.0 KB | fac26218fe0aa38f |
| `workflow/results/BYOP/rearch_p0/S5_GK/S2_consistency.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 0.9 KB | 5ad7b928f729fc8f |
| `workflow/results/BYOP/rearch_p0/S5_GK/lex_S1_EARLIEST.json` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 1.1 KB | edda2f601461dfdf |
| `workflow/results/BYOP/rearch_p0/S5_GK/S0_shed_by_snapshot_frozen.csv.gz` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 239.4 KB | 86a58c6bd4a38640 |
| `workflow/results/BYOP/rearch_p0/S5_GK/shed_by_bus_S0.csv` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 0.9 KB | b83c7be4b8116bc1 |
| `workflow/results/BYOP/rearch_p0/S5_GK/events.jsonl` | 验收算例输出 | 已生成 | 已同步 | S5_GK / rearch_S5_GK_20261020T231801Z | 2.5 KB | 5179383d1a25f058 |
| `workflow/results/BYOP/rearch_p0/R2_GW/case_manifest.json` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 30.7 KB | 8d6bb7dab6772436 |
| `workflow/results/BYOP/rearch_p0/R2_GW/scenario_summary.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 8.9 KB | 7f9b6e5b4dec7f58 |
| `workflow/results/BYOP/rearch_p0/R2_GW/service.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 60.5 KB | 77b08db9ac351d90 |
| `workflow/results/BYOP/rearch_p0/R2_GW/ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 480.6 KB | 40f6ee4a13c5fe73 |
| `workflow/results/BYOP/rearch_p0/R2_GW/poi_ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 55.9 KB | f7676d6b3b6053ef |
| `workflow/results/BYOP/rearch_p0/R2_GW/poi_upgrade_ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 6.5 KB | 7333f70b55b93b6f |
| `workflow/results/BYOP/rearch_p0/R2_GW/S1_GRID_OFFER.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 1.0 KB | 47ebafa6b55814d0 |
| `workflow/results/BYOP/rearch_p0/R2_GW/S2_developer_modes.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 5.2 KB | 18f2326c6b26adeb |
| `workflow/results/BYOP/rearch_p0/R2_GW/S2_consistency.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 1.5 KB | 834bd8475fbabc5c |
| `workflow/results/BYOP/rearch_p0/R2_GW/lex_S1_EARLIEST.json` | 正式结果 | 已生成 | 随本次提交同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 1.6 KB | a67a402e9c850eb7 |
| `workflow/results/BYOP/rearch_p0/R2_GW/S0_shed_by_snapshot_frozen.csv.gz` | 正式结果 | 已生成 | 已同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 264.2 KB | dc1559987a596297 |
| `workflow/results/BYOP/rearch_p0/R2_GW/shed_by_bus_S0.csv` | 正式结果 | 已生成 | 已同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 1.1 KB | 3cb12c5f894b5dd9 |
| `workflow/results/BYOP/rearch_p0/R2_GW/events.jsonl` | 正式结果 | 已生成 | 已同步 | R2_GW / rearch_R2_GW_20261021T001537Z | 3.7 KB | 68b9ce78e478a741 |
| `workflow/results/BYOP/rearch_p0/R2_GK/case_manifest.json` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 30.7 KB | a3428420a2c5c290 |
| `workflow/results/BYOP/rearch_p0/R2_GK/scenario_summary.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 10.0 KB | 1e878b661afeb024 |
| `workflow/results/BYOP/rearch_p0/R2_GK/service.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 59.4 KB | 83392ab806312cfb |
| `workflow/results/BYOP/rearch_p0/R2_GK/ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 577.4 KB | ec4591474d056723 |
| `workflow/results/BYOP/rearch_p0/R2_GK/poi_ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 55.5 KB | a08b29bc7f371293 |
| `workflow/results/BYOP/rearch_p0/R2_GK/poi_upgrade_ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 6.2 KB | adac078134e0388c |
| `workflow/results/BYOP/rearch_p0/R2_GK/S1_GRID_OFFER.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 1.0 KB | 340bbeca458c04e1 |
| `workflow/results/BYOP/rearch_p0/R2_GK/S2_developer_modes.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 5.2 KB | 77a2082b5b464c17 |
| `workflow/results/BYOP/rearch_p0/R2_GK/S2_consistency.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 1.5 KB | 8164fe3a9e9505d3 |
| `workflow/results/BYOP/rearch_p0/R2_GK/lex_S1_EARLIEST.json` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 1.6 KB | 94ac650a44b4fe64 |
| `workflow/results/BYOP/rearch_p0/R2_GK/S0_shed_by_snapshot_frozen.csv.gz` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 283.7 KB | 957bec85135e7b7d |
| `workflow/results/BYOP/rearch_p0/R2_GK/shed_by_bus_S0.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 1.3 KB | 1ceb08a2955af5cc |
| `workflow/results/BYOP/rearch_p0/R2_GK/events.jsonl` | 正式结果 | 已生成 | 随本次提交同步 | R2_GK / rearch_R2_GK_20261021T003139Z | 3.7 KB | d00f507632cbe070 |
| `workflow/results/BYOP/rearch_p0/R2_GU/case_manifest.json` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 31.4 KB | 8f89d5789edd20fc |
| `workflow/results/BYOP/rearch_p0/R2_GU/scenario_summary.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 9.8 KB | b3526341106d4666 |
| `workflow/results/BYOP/rearch_p0/R2_GU/service.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 59.6 KB | 2086527f1d3ba5ab |
| `workflow/results/BYOP/rearch_p0/R2_GU/ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 1039.2 KB | 06c5679e8fba1777 |
| `workflow/results/BYOP/rearch_p0/R2_GU/poi_ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 55.6 KB | e16d6470898b22be |
| `workflow/results/BYOP/rearch_p0/R2_GU/poi_upgrade_ledger.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 6.2 KB | 132a4943e46946f9 |
| `workflow/results/BYOP/rearch_p0/R2_GU/S1_GRID_OFFER.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 1.0 KB | cb4da7362a49a3a5 |
| `workflow/results/BYOP/rearch_p0/R2_GU/S2_developer_modes.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 5.2 KB | 6e04b3c1c2f29a00 |
| `workflow/results/BYOP/rearch_p0/R2_GU/S2_consistency.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 1.5 KB | 30abb75bdbf9f921 |
| `workflow/results/BYOP/rearch_p0/R2_GU/lex_S1_EARLIEST.json` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 1.6 KB | 53abda242affce8b |
| `workflow/results/BYOP/rearch_p0/R2_GU/S0_shed_by_snapshot_frozen.csv.gz` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 273.2 KB | 92f4b9993bac4840 |
| `workflow/results/BYOP/rearch_p0/R2_GU/shed_by_bus_S0.csv` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 1.2 KB | e05e5627f1bf8298 |
| `workflow/results/BYOP/rearch_p0/R2_GU/events.jsonl` | 正式结果 | 已生成 | 随本次提交同步 | R2_GU / rearch_R2_GU_20261021T003139Z | 3.7 KB | 889238d5448f7679 |
| `workflow/results/BYOP/rearch_p0/_collected/POI_DELIVERABILITY_LEDGER.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 205.5 KB | f5a81f5b6e191bc7 |
| `workflow/results/BYOP/rearch_p0/_collected/DELAY_ATTRIBUTION.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 9.9 KB | bf5bf4a5d28b9d5a |
| `workflow/results/BYOP/rearch_p0/_collected/ASSET_COMMITMENT_LEDGER.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 749.0 KB | 6bb96e7263dda8c0 |
| `workflow/results/BYOP/rearch_p0/_collected/SCENARIO_COMPARISON.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 21.8 KB | 6343a57ff20c6d59 |
| `workflow/results/BYOP/rearch_p0/_collected/SCENARIO_DIFFERENCES.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 2.8 KB | 8b0ed5d46141c843 |
| `workflow/results/BYOP/rearch_p0/_collected/GATE_CHECKS.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 5.5 KB | 533547d0effb1ade |
| `workflow/results/BYOP/rearch_p0/_collected/MAXMIN_LEXIMIN_ACCEPTANCE.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 6.8 KB | b44127c752e4169f |
| `workflow/results/BYOP/rearch_p0/_collected/INTERRUPTION_PRICE_TABLE.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 0.4 KB | bc65570332c22cf7 |
| `workflow/results/BYOP/rearch_p0/_collected/INTERRUPTION_vs_PCLR_ACCOUNTS.csv` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 1.0 KB | a9194c32a9b53d8d |
| `workflow/results/BYOP/rearch_p0/_collected/served_trajectories.png` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 235.8 KB | 1fb4ae401c40e9d4 |
| `workflow/results/BYOP/rearch_p0/_collected/delay_attribution.png` | 正式汇总表 / 图 | 已生成 | 随本次提交同步 | — | 68.9 KB | 24d57a8ed70c55a2 |

作废并存档的算例：`rearch_p0/R2_GK_ABORTED_competing600`、`R2_GU_ABORTED_competing600`（RA-D2f 原方案）；`rearch_s0repair/S0CAL_try1_REJECTED_economic_uplift`（第一次 S0 校准）。
