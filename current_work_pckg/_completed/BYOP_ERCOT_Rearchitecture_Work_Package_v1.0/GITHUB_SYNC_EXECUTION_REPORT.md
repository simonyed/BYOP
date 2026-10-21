# GITHUB_SYNC_EXECUTION_REPORT — BYOP GitHub 文件同步规则检查与完善

- 日期：2026-10-20（UTC 约 18:00–19:00）
- 仓库：<https://github.com/simonyed/BYOP>；本地分支 `byop` → 远端 `main`（SSH，用户 simonyed）
- 执行前 HEAD：`9cc88ee8`；本次内容提交：`504bd5f1`（已推送）；本报告与 `unit_tests.log` 在其后的一次提交中推送（SHA 见文末第 9 节）
- 存放位置：2026-10-20 按新存储规范从 `workflow/byop/docs/` 移到 `current_work_pckg/`（内容未改，文中 docs/ 路径指当时的位置）
- 范围：只改动 `.gitignore`、文档镜像、日志摘录和同步脚本，**不改数学模型、输入参数数值或正在运行的仿真**

## 1. 执行前 `.gitignore` 的问题

| # | 问题 | 后果 |
|---|---|---|
| P1 | 通用 Python 规则 `build/`（第 70 行）屏蔽了 `workflow/byop/build/` | 县级与 TAMU 基准构建器从未进入 GitHub。已由 `4c545d01` 加 `!workflow/byop/build/` 修复，本次复核有效 |
| P2 | `results/`、`logs/`、`data/`、`resources/`（第 29–36 行）整体屏蔽 | 结果、审计表、日志不可见。已由 `9cc88ee8` 为 `workflow/results/BYOP/` 和 `workflow/logs/byop/` 加放行规则 |
| P3 | **`9cc88ee8` 的 `!workflow/results/BYOP/**` 和 `!workflow/logs/byop/**` 是最后匹配的规则，会重新放行此前全局屏蔽的 `*.parquet *.gpkg *.tif *.tiff *.zip *.tar.gz *.pyc`**；当时只在其后补排除了 `.nc .pkl .pid code/` | 若这两个目录里出现 parquet、zip、tar.gz、tif 等文件，`git add -A` 会把它们一起提交（与 2026-09-17 那次 177 MB parquet 事故的机制相同）。执行前尚未发生 |
| P4 | `.venv/` 没有显式规则，只依赖 uv 在 `.venv` 内自带的 `*` 忽略 | 换一种方式创建虚拟环境时可能被提交 |
| P5 | `.gitignore` 无法按文件大小过滤 | 结果目录里出现 >10 MB 的 csv/log 时没有任何阻拦。实际情况：L2 上每个算例的控制台日志有 43–716 MB |
| P6 | 同步脚本先 `git add -A` 再提交，没有逐文件检查 | 与本次“只暂存确认过的文件”的要求不符 |

其他检查结果：`.git/info/exclude` 为空；没有全局 `core.excludesfile`；全仓库只有根目录一个 `.gitignore`。

## 2. 修改内容

| 文件 | 修改 |
|---|---|
| `.gitignore`（BYOP 段，第 326–363 行） | 1）保留两组精确放行规则：`!workflow/results/` → `workflow/results/*` → `!workflow/results/BYOP/**`，以及 `!workflow/logs/` → `workflow/logs/*` → `!workflow/logs/byop/**`。2）**在放行之后重新施加排除**（最后匹配生效）。`results/BYOP/**` 排除 `*.nc *.pkl *.parquet *.gpkg *.tif *.tiff *.zip *.tar.gz *.pid *.pyc __pycache__/ code/`；`logs/byop/**` 排除 `*.nc *.pkl *.parquet *.gpkg *.tif *.tiff *.zip *.tar.gz *.pid`。3）新增 `.venv/`。4）注释说明 >10 MB 文件由同步脚本把关。PyPSA-USA 原有规则一条未删 |
| `workflow/byop/docs/`（新建） | 研究文档的逐字节副本：`论文顶层设计.md`、`BYOP_ERCOT_Rearchitecture_Work_Package_v1.0_2026-10-20.md`、`BYOP_Parameter_Evidence_Baseline_FINAL_v1.0.md`、`DECISION_LOG_REARCHITECTURE.md`（草稿）；`README.md` 记录原件路径和 SHA-256；以及本报告 |
| `workflow/results/BYOP/rearch/*.excerpt.log`（新建） | 已结束的 `ERM_CAL_GW`、`ERM_CAL_GK`、`G1_S0_GW` 控制台日志的摘录（各 2–3 KB）：traceback、错误、终止状态、最后 60 行，并注明原文件大小和 SHA-256。原日志 43 MB，保留在 L2 |
| `work_pkgs/_tools/sync_pypsa_usa.sh`（本地工具，不在仓库内） | 1）`results/BYOP` 以 L2 为准：只拉回，不做逐字节比对，`--from-local` 不会覆盖运行中的算例。2）**提交前大小检查**：暂存区若有 >10 MB 文件，先撤销暂存再退出。3）只拉取 L2 上 <5 MB、非 `.nc`、非 `.pid` 的文件 |

**本次未修改**：`workflow/byop/model|build|run|tests|post|inputs` 下的任何程序和参数文件、`workflow/scripts/`、任何配置文件，以及正在运行的进程和运行脚本。

## 3. 已同步的目录与文件类别（`504bd5f1` 时 GitHub 上的状态）

| 目录 | 跟踪文件数 | 内容 |
|---|---:|---|
| `workflow/byop/model/` | 7 | `rearch_mech.py`、`v240_mech.py`、`v250_mech.py`、`v240_path.py`、`wp2_*`、`byop_paths.py` |
| `workflow/byop/build/` | 5 | 县级和 TAMU 基准构建器、ITL 校准、县级审计和诊断 |
| `workflow/byop/run/` | 5 | `run_rearch.sh` 及 v2.5.0 的运行脚本 |
| `workflow/byop/tests/` | 1 | `test_rearch_units.py` |
| `workflow/byop/post/` | 2 | `collect_rearch.py`、`collect_p1.py` |
| `workflow/byop/inputs/` | 13 | `poi/` 4、`tech/` 1、`dc/` 5、`grid/` 2、`load/` 1（另有 inputs/README.md） |
| `workflow/byop/README_REARCHITECTURE.md`、`README.md` | 2 | 运行说明 |
| `workflow/byop/docs/` | 5 + 本报告 | 研究文档镜像 |
| `workflow/config/config.byop_*.yaml`、`byop_*.csv` | 7 | 7s、8s、8s_gurobi、county、tamu 配置，以及两个风电修正系数文件 |
| `workflow/scripts/`（BYOP 补丁） | — | `cluster_network.py`（RAMP-01）、`prepare_network.py`（WIND-01 及本轮 reeds_zone 回退），作为上游文件一直被跟踪 |
| `workflow/results/BYOP/baseline_2025_tamu/` | 13 | 要求的 8 个审计文件全部已跟踪，另有 `build.log`、fleet、pipeline、负荷 `.csv.gz`、模板规则 |
| `workflow/results/BYOP/rearch/` | 52（加本报告提交为 53） | ERM 校准、G1、DEV_GU、R1_GW、R1_GK 的已有输出、日志摘录、`unit_tests.log` |
| `workflow/results/BYOP/`（旧结果） | 约 150 | `baseline_2025_7zone`、`baseline_2025_county`、`p1`、`p1_ctrl7`、`run0_freeze`、`dev_restructure` 中 <5 MB 的文件 |
| `workflow/logs/byop/` | 17 | 各次网络构建日志，含 `rearch_tamu_build/build_c60s.log` 和 `build_c64s.log` |

BYOP 相关跟踪文件合计 **261 个，24.25 MB**（`504bd5f1` 时）。

## 4. 新增跟踪文件数量与大小

| 提交 | 新增 | 修改 | 新增和修改内容合计 | 说明 |
|---|---:|---:|---:|---|
| `4c545d01` | 15 | 3 | 0.24 MB | 修复 build/ 屏蔽；rearch 代码、输入和配置 |
| `9cc88ee8` | 217 | 1 | 22.30 MB | 首次跟踪 results/BYOP 和 logs/byop |
| `504bd5f1`（本次） | 17 | 8 | 1.00 MB | `.gitignore` 加固、docs 镜像、日志摘录、运行中算例的新快照；最大单文件 0.37 MB（`R1_GK/prices_S1.csv.gz`） |
| 报告提交（本次） | 2 | 0 | <0.1 MB | `GITHUB_SYNC_EXECUTION_REPORT.md`、`unit_tests.log` |

提交前预览（`git add --dry-run -A`）为 25 个文件、1.00 MB，与实际提交一致。暂存时只列出了 `.gitignore`、`workflow/byop/docs`、`workflow/results/BYOP`、`workflow/logs/byop` 四个路径。

## 5. 被排除的大型文件类别

| 类别 | 位置与规模 | 处理 |
|---|---|---|
| 网络 `.nc`、`.pkl` | 基准网络（如 `baseline_2025_tamu_prepared.nc`）、`resources/*/networks` | 忽略；构建器、审计 json 中的 SHA-256 和配置可用于复现 |
| 每个算例的控制台日志 `<case>.log` | L2 上 14 个，6–716 MB（`p1/P1_GR.log` 716 MB、`rearch/DEV_GU.log` 332 MB、`R1_GW.log`/`R1_GK.log` 各 131 MB、ERM/G1 各 43 MB 等） | 不拉回、不提交；已结束的 rearch 算例改为提交摘录 `*.excerpt.log` |
| 每个算例的程序快照 `*/code/` | 每个算例目录一份 | 忽略；`case_manifest.json` 中有代码 SHA-256 |
| `workflow/data/` | 本地 11 GB，含 `data/byop` 8.5 MB 的 ReEDS 和 ERCOT 原始数据 | 忽略，未解除（可能有使用限制） |
| `workflow/resources/` | 392 MB | 忽略（可由配置重新生成） |
| 根目录 `workflow/*.zip` | 约 1.77 GB | 忽略 |
| `.venv/`、`.snakemake/`、`__pycache__`、`*.pyc` | 1.2 GB 等 | 忽略 |
| 密钥 `workflow/config/config.api.yaml` | — | 忽略（第 26 行），本次复核有效 |

**凭据扫描**：对 docs、byop、results/BYOP、logs/byop、BYOP 配置检查了 password、token、api_key、secret、私钥、GitHub/AWS 令牌格式、服务器 IP、L2 密码字样，均无命中。日志中出现 Gurobi 的 `Set parameter WLSSecret` 和 `WLSAccessID`，**只有参数名，没有值**。唯一打印出的值是学术许可证编号 `LicenseID 2559322`，属于标识号而非可直接使用的凭据；若希望隐去，需要改写已提交的日志和历史，本次未做。日志和 manifest 中含 L2 路径 `/datasets/prgm/...`，属于运行环境信息，予以保留。

**仓库中的其他大文件（非 BYOP，非本次引入）**：上游 PyPSA-USA 的 `workflow/repo_data/` 中有 5 个 >10 MB 的文件（3 个 psh `.gpkg` 各约 54 MB、NERC `.shp` 24 MB、county 距离成本 csv 23 MB），来自上游基线 `20b71907`。

## 6. 正反向忽略规则测试

方法：先对每条路径执行 `git check-ignore -v --no-index`（不存在的路径也可检验规则）；再在 `results/BYOP/rearch/_tmp_ignore_test/`、`R1_GW/code/` 和 `logs/byop/rearch_tamu_build/` 下创建真实临时文件，执行 `git add --dry-run -A`，结束后全部删除，并用 `git status` 确认没有残留。

**正向（应被跟踪）：22/22 PASS**
`byop/build/build_2025_baseline_tamu.py`，`byop/model/rearch_mech.py`，`byop/inputs/{poi,tech,dc,grid,load}/…`，`byop/run/run_rearch.sh`，`byop/tests/test_rearch_units.py`，`byop/post/collect_rearch.py`，`byop/README_REARCHITECTURE.md`，`byop/docs/论文顶层设计.md`，`config/config.byop_ercot_tamu.yaml`，`config/byop_onwind_cf_scaling.csv`，`results/BYOP/baseline_2025_tamu/{baseline_2025_tamu_audit.json, network_map.png}`，`results/BYOP/rearch/R1_GW/{scenario_summary.csv, case_manifest.json, solver_S1.log}`，`results/BYOP/rearch/_collected/GATE_CHECKS.csv`，`results/BYOP/rearch/unit_tests.log`，`logs/byop/rearch_tamu_build/build_c64s.log`

**反向（应被忽略）：21/21 PASS**（括号内为生效规则所在行）
`rearch/test.nc`（340）、`.parquet`（342）、`.pkl`（341）、`.zip`（346）、`.tar.gz`（347）、`.gpkg`（343）、`.tif`（344）、`.pid`（348）、`R1_GW/code/test.py`（351）、`R1_GW/__pycache__/x.pyc`（350）、`logs/byop/…/test.parquet`（354）、`config/config.api.yaml`（26）、`config/config.default.yaml`（18）、`data/byop/test.nc` 和 `data/byop/reeds_inputs/x.csv`（285）、`resources/BYOP_ERCOT_TAMU/…/elec_s.nc`（33）、`results/BYOP_ERCOT7s/x.csv`（333）、`byop/model/__pycache__/x.pyc`（72）、`.venv/x`（363）、`.snakemake/x` 和 `workflow/.snakemake/x`（4）

**真实文件测试**：`git add --dry-run` 只列出了两个探针文件（`positive_probe.csv`、`_tmp_probe.log`）；同目录下的 `.nc .parquet .pkl .zip .pid` 未被加入，`code/` 被报告为已忽略。临时文件已清理，`git status` 中 `_tmp` 的匹配数为 0。

## 7. 尚未生成、未同步或未完成的文件

| 期望文件 | 状态 |
|---|---|
| `rearch/R1_GW/`、`R1_GK/`：`case_manifest.json`、`scenario_summary.csv`、`service.csv`、`ledger.csv`、`poi_ledger.csv`、`poi_upgrade_ledger.csv`、`S2_developer_modes.csv`、`S2_consistency.csv` | **IN_PROGRESS**：算例结束时才写出。已有 `S1_GRID_OFFER.csv`、`PCLR_TRIGGERS.csv`、`events.jsonl`、`solver_S0/S1/S1_xPOI.log`、`rearch_solver.log`、`prices_*.csv.gz` |
| `rearch/DEV_GU/`：同上的最终表 | **IN_PROGRESS**。已有 S0、S1、S1_zero、S3 的日志和价格，以及 S1 报价和触发表 |
| `rearch/R1_GU/` | **未开始**。见第 8 节：DEV_GU 启动时**未带 `--attribution`**，不包含 S1 延迟归因，因此不能替代 R1_GU |
| `rearch/R1_GU_*/`（敏感性） | **未开始**（按研究者要求暂缓） |
| `rearch/_collected/`：`POI_DELIVERABILITY_LEDGER.csv`、`DELAY_ATTRIBUTION.csv`、`ASSET_COMMITMENT_LEDGER.csv`、`SCENARIO_COMPARISON.csv`、`SCENARIO_DIFFERENCES.csv`、`GATE_CHECKS.csv` | **未生成**：需要所有算例结束后运行 `collect_rearch.py` |
| `rearch/G1_S0_GW/case_manifest.json` | **不存在**。第一次运行在写账本时出错（G-W 设置没有 Link 导致空表，已在 `v240_mech.py:731` 修复）；重跑时，因 R1_GW 已包含同一个 S0 而被人为停止。注意：重跑覆盖了 `G1_S0_GW.log`，**第一次的 traceback 已不存在**，摘录反映的是被停止的重跑 |
| `rearch/unit_tests.log` | 本次由 `run_rearch.sh tests` 真实运行生成：8 passed，62.9 秒，在报告提交中推送 |
| `EXECUTION_REPORT_FOR_PUBLISHER.md`（重构工作包） | **尚未编写**，将在主要算例完成后编写，不做占位 |
| `MODEL_MODIFICATION_LOG.md` | **不存在同名文件**。模型改动记录在 `DECISION_LOG_REARCHITECTURE.md`、`README_REARCHITECTURE.md` 和提交历史中。v2.5.0 有 `ERCOT_COUNTY_MODEL_CHANGELOG.md`，但它属于另一个工作包，未纳入 |
| L2 上 >5 MB 的控制台日志（14 个） | 未同步（第 5 节） |
| `workflow/data/byop/` 原始数据 | 未同步（第 5 节） |

## 8. ERCOT 仿真运行状态（截至 2026-10-20 18:53 UTC，只报告，未干预）

| 算例 | 设置 | 已完成情景 | 运行时长 | manifest | traceback |
|---|---|---|---|---|---|
| DEV_GU | G-U（**无归因**） | S0、S1、S1_zero、S3；正在跑 S3_mS1 | 2:25 | 无 | 0 |
| R1_GW | G-W，含归因 | S0、S1；正在跑 S1_xPOI | 1:07 | 无 | 0 |
| R1_GK | G-K，含归因 | S0、S1；正在跑 S1_xPOI | 1:07 | 无 | 0 |
| ERM_CAL_GW / ERM_CAL_GK | 校准 | 完成，最优 | — | 不适用（输出 `erm02_calibration.json`） | 0 |

每个情景的求解约需 25–30 分钟。本次同步只修改了 `.gitignore`、`docs/` 和新增的摘录文件，没有停止、重启或修改任何运行中的进程和脚本。L2 上做了一件事：用 bundle 把 `byop` 分支指针移到 `504bd5f1`（`git reset` 默认模式，不改工作区文件）。L2 工作区目前显示的差异属于预期：运行中算例仍在写的文件（M）、>5 MB 日志（??），以及只存在于本地、L2 上不存在的 `baseline_2025_7zone/ercot_retirements_2026_2035.csv`（D，执行前已存在的差异）。

## 9. 提交与推送

- 内容提交 `504bd5f169f1be9f7cd0ce66b8485c51e3ae6a63`：已推送到 `simonyed/BYOP` 的 `main`，快进 `9cc88ee8..504bd5f1`，无强制推送，无冲突，未使用 LFS 或 `git add -f`。
- 本报告和 `unit_tests.log` 随后一次提交推送，SHA 见对话回复和 `git log`。

## 10. 遗留问题与后续建议

1. **R1_GU（含延迟归因）需要补跑**：DEV_GU 未开启 `--attribution`。建议在 DEV_GU 结束后补跑归因情景，即带 `--attribution --scenarios S1` 的 R1_GU；或在当前算例结束后完整运行 R1_GU。
2. **控制台日志太大**：求解器迭代行把每个算例日志撑到 100–700 MB。建议在 `run_rearch.sh` 中把 stdout 改成只记录 Python 日志和 traceback，迭代行留在已有的 `solver_*.log` 中；在此之前，每个算例结束后生成 `*.excerpt.log`。这需要改运行脚本，本次未做。
3. **运行中的结果是快照**：在 `case_manifest.json` 出现之前，GitHub 上的 rearch 输出都应视为 IN_PROGRESS，不能作为结论引用。
4. **文档镜像需要维护**：`workflow/byop/docs/` 是本地 work_pkgs 原件的副本，原件更新后需要重新复制并更新 README 中的 SHA-256。
5. **许可证编号**：若认为 Gurobi `LicenseID 2559322` 不宜公开，需要清理日志并重写历史，请研究者决定。
6. **上游大文件**：上游 `repo_data` 中有 5 个 >10 MB 文件，与 BYOP 无关，保持现状。
7. **本地与 L2 的一个已有差异**：`baseline_2025_7zone/ercot_retirements_2026_2035.csv` 只在本地存在，需确认它是否应存在于 L2。
