# current_work_pckg — 当前执行中的工作包及其汇报

存储规范（研究者 2026-10-20 设定）：

| 内容 | 位置 | 是否上传 GitHub / L2 |
|---|---|---|
| 当前要执行的工作包（研究者直接放入） | `pypsa-usa/current_work_pckg/` | 是 |
| 基于该工作包的汇报、决策日志、执行报告、同步报告等 | `pypsa-usa/current_work_pckg/` | 是 |
| 该工作包需要下载的原始数据、数据预处理脚本及其日志 | `D:\BYOP_impact\work_pkgs\<工作包对应文件夹>\` | **否**（仅本地） |
| 预处理后、模型实际读取的数据 | pypsa-usa 内的规定位置，如 `workflow/byop/inputs/<类别>/`，并附来源说明 | 是 |
| 被执行的程序与运行配置 | `workflow/byop/{model,build,post,run,tests}/`、`workflow/config/config.byop_*.yaml` | 是 |
| 运行结果与日志（小文件） | `workflow/results/BYOP/`、`workflow/logs/byop/` | 是（已排除 `.nc` 等大文件） |

跨工作包的项目级文档（论文顶层设计、参数证据基线）放在 `workflow/byop/docs/`。

## 当前工作包

**BYOP ERCOT 仿真架构重构 v1.0（2026-10-20）**；本地数据文件夹为 `work_pkgs/BYOP_ERCOT_Rearchitecture_Work_Package/`。

| 文件 | 内容 | 状态 |
|---|---|---|
| `BYOP_ERCOT_Rearchitecture_Work_Package_v1.0_2026-10-20.md` | 工作包原文 | 研究者提供 |
| `DECISION_LOG_REARCHITECTURE.md` | 空间、POI、气源、模式等决策及其状态 | 草稿，持续更新 |
| `GITHUB_SYNC_EXECUTION_REPORT.md` | GitHub 同步规则检查与完善报告 | 完成（2026-10-20） |
| `INTERIM_PROGRESS_REPORT_2026-10-20.md` | 中期进度：求解状态、S1 各场址服务量、DEV_GU（G-U）完整结果、发现的问题 | IN_PROGRESS（21:30 UTC 增补） |
| `EXECUTION_REPORT_FOR_PUBLISHER.md` | 工作包要求的执行情况报告 | 尚未编写，主要算例完成后写入本文件夹 |

参数来源登记表在 `workflow/byop/inputs/poi/SOURCE_EVIDENCE_REGISTER.csv`；运行说明在 `workflow/byop/README_REARCHITECTURE.md`。

## 新工作包到来时

1. 在 `work_pkgs/` 下为新工作包建立对应文件夹，原始数据和预处理脚本只放在那里。
2. 本文件夹中上一个工作包的全部文件（工作包原文及其汇报）移入 `current_work_pckg/_completed/<上一个工作包名>/`，git 保留完整历史，然后在此开始新的工作包。（研究者 2026-10-20 确认。）
