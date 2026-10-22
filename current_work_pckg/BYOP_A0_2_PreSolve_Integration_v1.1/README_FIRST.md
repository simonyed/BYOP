# BYOP A0.2 v1.1 — 阅读顺序和包内数据说明

**最先阅读：** `EXECUTION_WORK_PACKAGE.md`，随后 `ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md`、`EXECUTOR_START_HERE.md`。

本包将 A0.1 门禁修复与技术参数完善C 原 v2.0 技术经济/交付/环境参数合并；最大的模型更新是**排放特征→环境许可资格与工期→COD→Speed-to-Power**，而非独立的环境损害货币化目标。全部工作仍为 **0 次优化求解器调用**。

## 原始 v2.0 包已完整取得（区别于 A0.2 v1.0）

- `source_tech_v2/ORIGINAL_SOURCE_ZIP.zip`：研究者重新上传的完整 ZIP 原始字节。
- `source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22/`：从上述 ZIP 解包的完整 **9 个文件**，包括 4 个核心的 JSON/CSV 源文件、原执行文档、来源登记和原参数验证程序。
- `SOURCE_PACKAGE_RECONCILIATION.md`：逐文件 SHA-256 和关键源字段计数。
- `tools/validate_original_sources.py`：独立源数据比对脚本，**只用 Python 标准库，不调用优化求解器**。先运行 `python tools/validate_original_sources.py`。
- `tools/dry_environment_mechanism_examples.py` 与 `static_examples/STATIC_PERMIT_COD_EXAMPLES.csv`：原参数驱动的 9 个纯函数示例，用于说明许可是否为 COD 关键路径（**非仿真结果、无优化求解**）。

请直接从原始 JSON/CSV 复制至仓库 `workflow/byop/inputs/tech_calibrated_v2/`，并保留原始 SHA；**不再使用 A0.2 v1.0 的重建参考表**。已有旧 `MAINLINE_V13_TECH_DEFAULTS.csv` 不覆盖。原 v2.0 文档中要求重新进行 2025 基线校准、沿用旧 ERM-02/S0CAL 的部分过时，以本版总工作包为准。

`source_instructions/` 保留论文总设计及前轮 A0.1 修复要求。

## 明确授权边界

只实施代码、输入、纯函数、参数检验、dry-build 结构测试与 git 提交；A1 LP-R/LP-N、A2/S0-S1、A3/S2-S3 **均不得调用求解器**。所有 `run_authorization` 始终 `NOT_APPROVED`；最终报告同时分开披露 A1 和 A2/A3 是否 READY_STATIC（未运行并不等于真实可行）。
