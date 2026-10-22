# STAGE_B3_RETURN_MANIFEST：B3-E 交付清单

- 日期：2026-10-22（纽约时间）
- 分支：`mainline-v13-stageA`（没有合并到 `main`）
- 批准 SHA：`01e761dabab25cce514c10abb1824936410e3f87`；运行时 HEAD：`8073d0e4`
- 本清单所在提交：见 GitHub 分支最新提交
- 运行后已把 `run_authorization` 复位为 `NOT_APPROVED`（单次运行已经完成）
- B4 执行次数：0

## GitHub 上的文件（tracked）

`workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1/` 下的文件：

| 类别 | 文件 |
|---|---|
| 正式汇总表 | `MAINLINE_SCENARIO_SUMMARY.csv`、`MAINLINE_BUS_DELIVERY_AND_DELAY.csv`、`MAINLINE_S2_MODES_TECH.csv`、`MAINLINE_PUBLIC_INVESTMENT_DELTA.csv`、`MAINLINE_ASSET_COMMITMENT_LEDGER.csv`、`MAINLINE_MATCHED_SERVICE_COST.csv`、`MAINLINE_COST_BOOK_DECOMPOSITION.csv`、`MAINLINE_GATE_CHECKS.csv`、`MAINLINE_CASE_MANIFEST.json` |
| S2 诊断 | `MAINLINE_DIAGNOSTIC_S2_ITERATIONS.csv`、`MAINLINE_DIAGNOSTIC_S2_DEVELOPER_ALL_ITERATIONS.csv` |
| B3 机制表 | `STAGE_B3_M1_SPEED_DELIVERY_BY_SITE_YEAR.csv`、`STAGE_B3_M2_PUBLIC_EXPANSION_BY_CARRIER_YEAR.csv`、`STAGE_B3_M2_ASSET_COMMITMENT_AND_COD.csv`、`STAGE_B3_M4_COST_COMPONENTS.csv`、`STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv`、`STAGE_B3_CHECKS_AND_METHOD_FLAGS.csv`、`STAGE_B3_EXPLORATORY_AUDIT.json` |
| 原始产物 | `case_manifest.json`、`S1_GRID_OFFER.csv`、`S2_developer_modes.csv`、`S2_consistency.csv`、`PCLR_TRIGGERS.csv`、`lex_S1_EARLIEST.json`、`lex_audit_S1_EARLIEST.csv`、`ledger.csv`、`poi_ledger.csv`、`service.csv`、`duals.csv`、`byop_cod.csv`、`shed_by_bus_*.csv`、`S0_shed_by_snapshot_frozen.csv.gz`、`prices_*.csv.gz`、`solver_*.log`、三张机制图 |
| 各情景检查点 | `scenarios/{S0,S1_EARLIEST,S3,S2,S3_mS2}/*`（含 `s0cal_line_flows.csv`、`shed_by_snapshot.csv.gz`、`line_flows_2028_dfw*.csv*`）<br>`scenarios/S2_final/S2_SELECTION.json`：S2_final 的正式行在各汇总表中，以 `scenario = S2_final` 标识 |

其他文件：

- 上一级目录：`MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1.excerpt.log`、`pilot_core_b3e_driver.log`
- `current_work_pckg/STAGE_B3_MAINLINE_RESULTS_REPORT.md`、本文件
- `workflow/byop/post/stage_b3_tables.py`

## 只在 L2 上的文件

| 文件 | 大小 | SHA-256 |
|---|---:|---|
| `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1.log` | 427 MB | `bac61d03c36e748e16cc8d76d9c058e8ec7627cb44c1757aa4f7470b76093720` |
| `workflow/results/BYOP/baseline_2025_tamu/baseline_2025_tamu_prepared.nc` | — | `19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb` |

如果有体积超过 5 MB 的结果文件，同步工具不会把它拉回本地，所以它们只在 L2 上；整个结果目录在 L2 上共 8.7 MB。
