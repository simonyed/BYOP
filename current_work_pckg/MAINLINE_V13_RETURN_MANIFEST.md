# MAINLINE_V13_RETURN_MANIFEST：Stage A 交付清单

- 日期：2026-10-21
- `RUN_AUTHORIZATION: NOT_APPROVED`，`SOLVER_EXECUTIONS: 0`

## 1. GitHub

| 项目 | 值 |
|---|---|
| 仓库 | <https://github.com/simonyed/BYOP> |
| 分支 | `mainline-v13-stageA`：<https://github.com/simonyed/BYOP/tree/mainline-v13-stageA> |
| Stage A 代码 / 输入 / 测试提交 | `edc5ed8c09eed4920693e1e9eef2a6545c30018f` |
| 报告补充提交 | `efca9d0a9bf4e5777fc5db4c0a92b9b46b604dd0` |
| 独立审计 P0 修复提交（代码 / 输入 / 测试 / 报告） | `85fa823d8e3e5034aea4774bdc3a8db63e858ab8` |
| 基线 | `main` = `be2c6904`（v1.3 起草时的 HEAD）；**没有合并到 `main`** |
| PR | 尚未创建（本机没有 `gh` CLI）。创建链接：<https://github.com/simonyed/BYOP/compare/main...mainline-v13-stageA?expand=1> |
| L2 | `/datasets/prgm/BYOP_impact/pypsa-usa`：工作文件与本地逐字节一致；HEAD 指向同一分支和提交（同步工具已改为支持功能分支） |

## 2. GitHub 上的文件

**工作包与报告**（`current_work_pckg/`）：

- 工作包原文 `BYOP_ERCOT_Mainline_Work_Package_v1.3_2026-10-21.md`
- 附件 `MAINLINE_V13_TECH_DEFAULTS.csv`、`MAINLINE_V13_GAS_PRICES_2026_2031.csv`
- 报告：`MAINLINE_V13_STAGE_A_REPORT.md`、`MAINLINE_V13_PRE_RUN_AUDIT.md`、`MAINLINE_V13_PARAMETER_CROSSWALK.md`、`MAINLINE_V13_DATA_REGISTER.csv`、`MAINLINE_V13_DECISION_LOG.md`、`MAINLINE_V13_PRE_RUN_MANIFEST.json`、本文件，以及 `README.md`
- 上一个工作包：`_completed/BYOP_ERCOT_Rearchitecture_Work_Package_v1.0/`（10 个文件，git 记为重命名，历史保留）

**程序**：

- `workflow/byop/model/rearch_mech.py`、`v240_mech.py`
- `workflow/byop/build/build_mainline_inputs.py`、`build_reeds2_potential.py`、`build_mainline_manifest.py`
- `workflow/byop/post/collect_mainline.py`
- `workflow/byop/run/run_mainline.sh`
- `workflow/byop/tests/test_mainline_v13.py`、`structural_mainline_v13.py`
- `workflow/config/config.byop_ercot_mainline.yaml`

**输入**（`workflow/byop/inputs/`）：

- `dc/MAINLINE_*.csv`（4 个）
- `poi/GREAL_*.csv`（3 个）
- `grid/GREAL_*.csv`（3 个）+ `GREAL_PHYSICAL_MECHANISM_NOTE.md`
- `grid/ERCOT_WIND_SOLAR_POTENTIAL.csv`、`REEDS2_TO_TAMU64.csv`、`REEDS2_SOURCE_INVENTORY.csv`、`REEDS2_IMPORT_NOTE.md`
- `tech/MAINLINE_V13_*.csv`（2 个）

**无求解器测试记录**（`workflow/results/BYOP/mainline/`）：

- `static_tests.log`、`structural_tests.log`、`gate_check.log`、`_gate_test.log`
- `_structural/STRUCTURAL_CHECKS.csv`、`_structural/STRUCTURAL_REPORT.json`、`_structural/structural_poi_ledger_S3_unsolved.csv`
- `_gate_test/RUN_GATE.json`

## 3. 不在 GitHub 上的文件

| 文件 | 位置 | 原因 | SHA-256 / 说明 |
|---|---|---|---|
| 2025 TAMU 基准网络 `baseline_2025_tamu_prepared.nc` | L2 `workflow/results/BYOP/baseline_2025_tamu/` | `.nc` 不进 git | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb`（已写入 pre-run manifest，运行门控会核对） |
| ReEDS2 原始供给曲线、站点表、逐时 cf | 本地 `D:\ReEDS2`（commit eb75a6bc） | 原始数据，只读 | 见 `inputs/grid/REEDS2_SOURCE_INVENTORY.csv` |
| 工作包 zip 原件 | 本地 `work_pkgs/BYOP_ERCOT_Mainline_v1.3/raw/` | 原始交付件 | 附件 CSV 与 zip 内文件逐字节一致（`QA-PARAM` 核对） |
| ReEDS2 转换日志 | 本地 `work_pkgs/BYOP_ERCOT_Mainline_v1.3/build_reeds2_potential.log` | 预处理日志 | — |
| Epoch AI 原始 zip | 本地 `work_pkgs/BYOP_ERCOT_Rearchitecture_Work_Package/epoch_ai/raw/` | 原始数据 | `c6e13b96…`（`EPOCH_TAMU64_PROVENANCE.json`） |

关于换行符：仓库的 `.gitattributes` 对 `workflow/byop/**` 规定 `eol=lf`，git 中存的是 LF 版本；manifest 的哈希按 L2 和本地的工作文件计算。从 GitHub 重新检出到其他机器时，CSV 附件的字节可能与这些哈希不同，但内容相同。

## 4. Stage B 需要的文件和操作

1. 研究者审计 `MAINLINE_V13_PRE_RUN_AUDIT.md`、`MAINLINE_V13_DECISION_LOG.md`（ML13-01..09）、`MAINLINE_V13_PARAMETER_CROSSWALK.md`。
2. 如需修改代理值，改 `build_mainline_inputs.py` 中对应的表并重新生成输入。然后重建 manifest：`python byop/build/build_mainline_manifest.py --baseline-sha256 <sha>`。
3. 在 `workflow/config/config.byop_ercot_mainline.yaml` 中写入 `run_authorization: APPROVED` 和 `approved_git_sha: <审计过的提交>`。
4. 在 L2 上执行：`bash byop/run/run_mainline.sh gate` → `step0` → `run`。结果写入 `results/BYOP/mainline/`，`collect_mainline.py` 自动生成 E3 表和 3 张图。
