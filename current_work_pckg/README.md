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

**BYOP ERCOT Mainline v1.3 — 物理并网瓶颈、Speed-to-Power 与公共投资响应（2026-10-21）**

- 本轮状态：`STAGE_A_IMPLEMENTATION_ONLY`，`RUN_AUTHORIZATION: NOT_APPROVED`
- 本地数据文件夹：`work_pkgs/BYOP_ERCOT_Mainline_v1.3/`
- 上一个工作包（重构 v1.0）及其全部汇报已移入 `_completed/BYOP_ERCOT_Rearchitecture_Work_Package_v1.0/`

| 文件 | 内容 | 状态 |
|---|---|---|
| `BYOP_ERCOT_Mainline_Work_Package_v1.3_2026-10-21.md` | 工作包原文 | 研究者提供 |
| `MAINLINE_V13_TECH_DEFAULTS.csv`、`MAINLINE_V13_GAS_PRICES_2026_2031.csv` | 工作包附表；逐字节复制到 `workflow/byop/inputs/tech/` 作为模型输入 | 研究者提供 |
| `MAINLINE_V13_STAGE_A_REPORT.md` | Stage A 执行报告：完成项、修改文件、无求解器测试、阻塞项 | 完成 |
| `MAINLINE_V13_PRE_RUN_AUDIT.md` | 运行前审计，以及是否推荐正式运行 | 完成 |
| `MAINLINE_V13_PARAMETER_CROSSWALK.md` | 旧参数 → 证据 → v1.3 值 → 代码字段 | 完成 |
| `MAINLINE_V13_DATA_REGISTER.csv` | 数据来源、版本、单位、转换脚本、哈希 | 完成 |
| `MAINLINE_V13_DECISION_LOG.md` | D11–D15 均为 CONFIRMED；新问题 ML13-01..09 标为 REVIEW_REQUIRED | 待研究者审计 |
| `MAINLINE_V13_PRE_RUN_MANIFEST.json` | 代码和输入的 SHA-256、拟运行命令、运行环境；运行门控会核对 | `NOT_APPROVED` |
| `BYOP_Mainline_v1.3_StageA_Independent_Audit_2026-10-21.md` | 研究者方的 Stage A 独立审计（P0-1..5、P1-1..7） | 研究者提供 |
| `MAINLINE_V13_AUDIT_RESPONSE.md` | 对独立审计的逐项回应与修复 | 完成 |
| `MAINLINE_V13_RETURN_MANIFEST.md` | GitHub 文件清单、本地大文件、提交 SHA、下一阶段所需文件 | 完成 |

运行说明见 `workflow/byop/README.md` 的 Mainline v1.3 一节。

## 新工作包到来时

1. 在 `work_pkgs/` 下为新工作包建立对应文件夹，原始数据和预处理脚本只放在那里。
2. 本文件夹中上一个工作包的全部文件（工作包原文及其汇报）移入 `current_work_pckg/_completed/<上一个工作包名>/`，git 保留完整历史，然后在此开始新的工作包。（研究者 2026-10-20 确认。）
