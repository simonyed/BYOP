# BYOP v1.6 后续研究：附带数据的分阶段执行工作包 v1.1

**更新时间：2026-10-22；默认许可：仅 A0（不调用任何优化求解器）。**

该包在原 `BYOP_Post_v1.6_Calibration_Research_Basis_2026-10-22.zip` 基础上建立。原研究备忘录 `CALIBRATION_RESEARCH_MEMO_v0.1.md`、数据处理程序 `build_research_data.py`、`raw/`、`derived/`、官方来源及既有校验结果原样保留。新增的《CURRENT_EXECUTION_WORK_PACKAGE_v1.1.md》才是当前可执行指令，原备忘录的“等待 v1.6”表述不再作为最新状态。

## 执行者首先阅读（按序）
1. `CURRENT_EXECUTION_WORK_PACKAGE_v1.1.md`：执行范围、阶段、约束、结果和停止点；**A0 之外的优化均不授权**。
2. `POST_V16_DECISION_REGISTER.csv`：已关闭、保留局限、推荐新规则、仍待授权的决策。
3. `RESEARCH_TO_EXECUTION_CHANGELOG.md`：原资料包中哪些判断因 v1.6 和 GitHub 实况被更新。
4. `CALIBRATION_RESEARCH_MEMO_v0.1.md`：未经改写的完整方法与证据研究。
5. `SOURCE_REGISTRY.csv`、`DATA_GAPS_AND_OWNERSHIP.csv`、`derived/DATA_QA.json`：数据来源、缺口和校验记录。

## 研究分支及不可混淆的网络文件
- 仓库：`https://github.com/simonyed/BYOP`；研究分支：`mainline-v13-stageA`。
- 本次复核的 HEAD：`0b417903c7704c00de609581646fed29723397cf`（相对于原资料包记录的 `027431c2`，只增加 v1.6 代码及报告两次提交）。任何新的执行必须先重新检查当前 HEAD，发生漂移则先返回差异审计。
- 固定基线在执行环境 L2：`workflow/results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc`，完整 SHA256 见工作包；这个 `.nc` **没有放在 GitHub**，不可依据文件名假设它存在、也不可用旧基线代替。
- v1.6 验收结果：`COMPLETE_WITH_STATED_LIMITATIONS`，并非官方 ERCOT 可靠性认证。

## 当前停止点
A0 只允许 GitHub 代码审计、数据放置和校验、实现独立备用/联合裕度 LP 的代码及结构测试、更新门禁和文档、在新分支或新 commit 推送并返回报告；**严禁调用 Gurobi/PyPSA optimize/solver、改变 `run_authorization` 为 APPROVED、启动旧 `step0`、正式 S0/S1/S2/S3、B4、全国算例**。执行方交付 `A0_IMPLEMENTATION_REPORT.md` 和 `A0_RETURN_PACKAGE.zip`、提交 SHA、DRY 命令和 A1 两次 LP 的明示请求后停止。下一步须由研究者按 SHA 单独批准。

本包不预先保证 A1 的“运行备用 3 GW、1 h”代理一定可行；若零新增负荷不可行，应报告阻断原因，不可静默改备用、改实际负荷或免费增容。
