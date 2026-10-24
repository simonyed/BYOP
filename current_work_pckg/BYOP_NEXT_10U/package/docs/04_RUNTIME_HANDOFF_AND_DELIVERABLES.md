# 04｜L2 执行、结果交付与归档

1. 在机器上准备完整 clone/checkout `simonyed/BYOP` 最新 `main`；不要把此 ZIP 当作可直接运行的完整 PyPSA 仓库。该 ZIP 是执行说明 + 预检工具 + 规则表。原工程包 raw/processed 放在本 ZIP 的 engineering_data 子目录或通过只读的绝对数据根路径挂载。
2. 根目录运行 `python scripts/preflight_external_data.py --data-dir engineering_data --out-dir manifest/local_preflight`。对缺失仅查原数据包，工程源仅在原数据包和仓库指定来源已存在时读取，不再下载。
3. 原始/处理数据从工作包只读挂载进入 L2，如大型 L2 独立目录 `/datasets/prgm/BYOP_impact/engineering_external`；不要向 GitHub 推送原始或处理的大文件，不在仓库路径建立隐式 `raw/processed` copy。新代码输入 config 使用显式绝对根路径或环境变量 `BYOP_ENGINEERING_DATA_ROOT`，报告只保留逻辑相对路径+hash。
4. 新模型 config 建议 `workflow/config/config.byop_engineering_cost_v1.yaml`，科学场景输出 `workflow/results/BYOP/next10u_engineering_cost_v1/`，小报告同步到 `workflow/current_work_pckg/BYOP_NEXT_10U/` 或现有约定 current_work_pckg 路径，严禁覆盖旧 NEXT-09 output。
5. 每个代码阶段先提交后校验，静态验收和 manifest freeze 之后才能执行带许可的 LP。每次 solver 调用落盘 STARTED ledger 和 CPU/MEM/elapsed；任务恢复先读取 ledger 状态，不能因 watchdog 重复运行。
6. 旧原始 v1.7L 的 baseline NetCDF 为 L2-only，已 ADOPTED，使用现有正式 registry；不得重复上传或复制进 zip。

## 最终回传（必须交付，允许部分完成）
- `00_FINAL_EXECUTION_REPORT.md`：提交 SHA、当前基准、各阶段状态、调用次数、每个 STOP 原因、模型 QA、science QA。
- `01_DATA_INPUT_AUDIT.csv`, `02_POI_INPUT_MODEL_DIFF.csv`, `03_POI_EVENT_LEDGER.csv`, `04_EVIDENCE_GAPS.csv`。
- `05_PUBLIC_ASSET_LEDGER.csv`, `06_COST_CAUSATION_LEDGER.csv`, `07_PAYMENT_RISK_LEDGER.csv`, `08_COST_INCIDENT_MATRIX.csv`。
- `09_SCENARIO_SOLVE_LEDGER.csv`, `10_S0_SCIENCE_VERDICT.json`, `11_CASE_COMPARISONS.csv`, `12_MATCHED_SERVICE_VERDICT.json`。
- `13_MAINLINE_SCIENTIFIC_FINDINGS.md`：3 个主要对比 S1-S0/S2-S1/S2-S3 和尚未证实的结论，结果未跑则明确 NOT_RUN。
- `14_METHOD_LIMITATIONS.md`：空间聚合、POI 权利证据缺失、stage evidence 等级、拟合误差与政策状态。
- `15_NEXT_STEPS_AND_DECISIONS.md`：只列真正需要用户判断的 remaining blockers，不不断催促小审批。
- `NEXT_10U_RETURN_PACKAGE.zip`：只含上述轻量台账、报告、代码 diff、hash、回归/门禁摘要，不含 raw/processed、基准 NetCDF、求解器临时文件。

## 持续反馈机制
执行方应在每个可独立完成的里程碑提交 report 到 GitHub main，使用户醒来后直接看到已得到的结果；在中间的进度提示中不宣称任务能在 ChatGPT 本聊天后台执行。若平台配额中断，立即封存 state、关闭当前结果写入，下一次允许的会话只从 PASSED 阶段继续。
