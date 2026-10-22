# 启动指令 — BYOP A0.2 v1.1，供 Codex / Claude

请在仓库 `simonyed/BYOP` 的 `mainline-v13-stageA` 分支实施本目录 `EXECUTION_WORK_PACKAGE.md`；同时必须读 `ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md`。

**与上一版不同：** 本包已经附有研究者重传的**原始技术 v2.0 ZIP 及全部 JSON/CSV**。工作开始先运行 `python tools/validate_original_sources.py`，再从 `source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22/` 将 4 个真实参数源文件拷入版本化运行输入。不要使用旧 A0.2 v1.0 重构值或重新猜县 FIPS。原 v2.0 旧阶段/代码 SHA 与新主线冲突时，新主线冻结基线与本版指令优先。

先确认 GitHub HEAD、A0 报告与冻结 v1.6 baseline SHA。按 P0→P1→P2→P3→P4→P5 执行：

1. 修 A0.1：A1 真正 max lambda、既有负荷零 shed 硬约束、LP-R 完整 PASS 后 LP-N 门禁、求解前 STARTED 消耗预算（不得求解）。
2. 显式技术版本 TECH_COMP_2，六技术成本/燃气/供货/实际技术到场工期，保留旧 v1.3。
3. **环境传导机制为首要指标**：技术排放及厂址聚合 PTE → TCEQ 许可路径资格/县级臭氧分类 → 不同许可工期代理 → 最终 COD；如果许可被燃气或设备工期覆盖，必须报告环境优点没有真正造成提前投运。治理后的低 NOx 不能在没有许可年限依据时自动加速。CO₂/NOx 附属台账，不加社会环境税或外部损害目标。
4. 供货容量权防重、风光储 24/48/72 h SOC/Firm 干构模、S2/S3 同物理约束与动态键审计。
5. 生成 `PERMIT_TO_COD_CAUSAL_AUDIT.csv`（附 ENV-03/05/06/08 数值示例）及工作包要求的其他产物，所有测试 zero solver，提交报告、完整 SHA，停机。

任何真实或模拟 `optimize`、Gurobi/HiGHS/linopy solve_model 调用均不授权，最终 `REAL_SOLVER_EXECUTIONS=0`，A1/A2/A3 仍 `NOT_APPROVED`。不得把 2025 固定电网机组或线路改成 v2 参数，也不得启动 ERM-02/S0CAL 或任何正式 S0-S3 算例。
