# STAGE_B_PRE_RUN_AUDIT：Stage B 运行前审计（B0 结束时）

- 日期：2026-10-21
- 分支：`mainline-v13-stageA`
- 待批准提交：`__COMMIT_B0__`
- **`RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS: 0`**

## 1. 状态

| 项目 | 结论 |
|---|---|
| S2 最终迭代与 M4 的一致性 | **已修复**：所有正式表统一使用 `S2_final`（所选的最后一轮）；`S3_mS2` 固定的是该轮实际交付的服务量；48 键严格匹配；中间迭代只进诊断表（`STAGE_B_B0_CODE_FIX_REPORT.md`） |
| 分步运行入口 | `pilot_s01`、`pilot_core`、`attribution`、`run`；各阶段输出目录独立；`DRY=1` 命令组装测试通过 |
| 纯 LP | 新代码没有整数或二元变量；4 个结构模型的 `integers + binaries = 0` |
| 运行门控 | 在 `NOT_APPROVED` 下拒绝运行（`approved: false`）；`step0` / `pilot_*` / `attribution` / `run` 都经过同一门控 |
| 物理模型、8 个母线、技术参数、目标函数 | **未改动** |

## 2. 代码与输入的 SHA-256

完整清单见 `MAINLINE_V13_PRE_RUN_MANIFEST.json`（随 B0 提交一起重建）。其中包括：

- 14 个代码文件；
- 25 个输入文件；
- L2 上未纳入 git 的基准网络 `baseline_2025_tamu_prepared.nc`，SHA-256 `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb`。

门控逐个文件核对这些哈希。

## 3. 仍需研究者确认的代理值（简表）

| ID | 内容 | 当前默认值 |
|---|---|---|
| ML13-01 | 园区 POI 设备容量 | 选项 A：按 Epoch 时间线，已观测投运的部分预批；计划未核实的部分不早于 2028 年 |
| ML13-02 | Shackelford 接网方式 | E0 = 0，经 POI 升级最早 2029 年接网；燃气 L1 |
| ML13-03 | Helios 新增 830 MW 的 COD | 2028 |
| ML13-04 | POI 升级参数 | 2,000 MW / 3 年 / 160 USD/kW / 程序日期 2028 |
| ML13-05 | Abilene 现场既有燃机 | 不录入 |
| ML13-06 | 现场风光上限 | 1.0 × 2031 年研究设施 MW |
| ML13-07 | 全部燃气机组按逐年气价 | 是 |
| ML13-08 | PCLR | 30%，200 小时 / 12 小时 |
| ML13-10 | 电网 Firm 报价 | 两部分：压力时段为认证值，非压力时段为最大交付值 |
| ML13-11 | 残值处理 | `tv_share = 1`（隐含完整残值） |

## 4. 获批后的执行顺序与自动停止规则（工作包 §4.2、§5）

1. 研究者在 `config.byop_ercot_mainline.yaml` 中写入 `run_authorization: APPROVED` 和 `approved_git_sha: <批准的提交>`。`bash byop/run/run_mainline.sh gate` 必须输出 `approved: true`，否则停止。
2. **B1 `step0`** → 生成 `STAGE_B1_CALIBRATION_REPORT.md` → **人工停止点**：研究者确认 S0 / ERM 基准合理之后，才能继续。
3. **B2 `pilot_s01`** → 生成 `STAGE_B2_GRID_ONLY_REPORT.md`。出现以下任一情况即自动停止、不进入 B3：
   - 任一 LP 不是 optimal；
   - 背景出现严重切负荷；
   - 能量平衡或单位异常。
4. **B3 `pilot_core`** → 生成 `STAGE_B3_MAINLINE_RESULTS_REPORT.md`。只有 `SCIENTIFIC_USE = ALLOWED` 时，才能得出 M1 / M2 / M4 结论。
5. **B4 `attribution`**：可选，只在 B3 有意义时运行。
