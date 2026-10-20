# BASELINE_DIAGNOSTIC — rearch 第一轮算例（P0 修正之前）

依据研究者指令 `current_work_pckg/BYOP_ERCOT_RUN_DECISION_AND_CORRECTION_PLAN_2026-10-20.md`，本目录中 P0 修正前的全部算例（`ERM_CAL_GW`、`ERM_CAL_GK`、`G1_S0_GW`、`DEV_GU`、`R1_GW`、`R1_GK` 及 `_collected/`）**统一标记为 `BASELINE_DIAGNOSTIC`**：

- 用途：模型集成测试与问题诊断。
- **不得作为论文正式结果引用。**
- 文件不删除、不覆盖。P0 修正后的新算例写入 `results/BYOP/rearch_p0/`。

## 运行记录

| 算例 | run_id | 启动 (UTC) | 结束 (UTC) | 实际运行的代码 | 设置 | 状态 |
|---|---|---|---|---|---|---|
| ERM_CAL_GW | rearch_ERM_CAL_GW_20261020T162526Z | 16:25 | 16:27 | `rearch_mech` = 提交 `4c545d01` 的版本（ea6918fe…）；`v240_mech` 为 d9d29e2b…，与 `4c545d01` 只差空 Link 表的账本修复（不影响模型），该版本未单独提交 | G-W 校准 | 最优；输出 `erm02_calibration.json` |
| ERM_CAL_GK | rearch_ERM_CAL_GK_20261020T162526Z | 16:25 | 16:27 | 同上 | G-K 校准 | 最优 |
| G1_S0_GW | — | 16:28 / 重跑 18:4x | — | `4c545d01` | G-W，仅 S0 | 第一次运行在写账本时出错（空 Link 表），已修复；重跑因 R1_GW 已包含同一个 S0 而被人为停止。**第一次运行的 traceback 已被重跑覆盖，无法找回** |
| DEV_GU | rearch_DEV_GU_20261020T162802Z | 16:28 | 21:0x | 手动启动，**没有 code 快照**；按启动时间推断代码与 ERM_CAL 相同 | G-U，**不含延迟归因** | 8 个情景全部最优；CASE_CHECK_FAIL（no_load_shed、poi_flow_le_equipment） |
| R1_GW | rearch_R1_GW_20261020T174558Z | 17:46 | ≈23:00 | `4c545d01`（code 快照 sha256：rearch ea6918fe…，v240 bcd964d8…） | G-W，含归因 | 13 个情景全部最优；CASE_CHECK_FAIL（同上） |
| R1_GK | rearch_R1_GK_20261020T174558Z | 17:46 | ≈23:00 | 同上 | G-K，含归因 | 同上 |

- **代码版本以每个算例目录下的 `code/` 快照为准**（在 L2 上，不进 git）。
- `case_manifest.json` 中的 `code_sha256` 是在**算例结束时**计算的，所以 R1 的 manifest 记录的是结束时磁盘上的文件（与 `40af7bc5` 一致），**不是实际运行的代码**。这一记录缺陷已修正：此后 manifest 改为在进程启动时计算哈希（`code_sha256_basis = 'hashed at process start'`）。
- **共同输入**（sha256 前 12 位）：
  - 基准网络 `baseline_2025_tamu_prepared.nc` 19034285be0a
  - POI_REGISTER d2f37909d559、POI_REQUESTS 737d808551f9、GRID_PROJECTS bb05fdc16768
  - TECH-01 127e5a97b517、PUE 28c4da910027、task 1206faa69dd9
- **环境**：L2 lambda-2（i9-10920X，12 个物理核心，251 GB 内存），pypsa 1.3.0、linopy 0.9.1、gurobipy 11.0.3。求解参数为 barrier、Crossover=0，每年抽样 2 周、3 小时分辨率。
- **启动命令**：见各 `case_manifest.json` 的 `argv`；R1 由 `/tmp/launch_r1.sh` 调用 `rearch_mech.py` 启动，参数为 `--setting G-W|G-K --attribution --start 2026 --end 2031 --sample-weeks 26 --threads 7`。
