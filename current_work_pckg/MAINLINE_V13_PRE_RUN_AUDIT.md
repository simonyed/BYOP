# MAINLINE_V13_PRE_RUN_AUDIT：运行前审计（需求 / POI / 物理瓶颈 / COD / BYOP / 纯 LP / S0–S3）

- 日期：2026-10-21
- 依据：`BYOP_ERCOT_Mainline_Work_Package_v1.3_2026-10-21.md` §8 Stage A
- 审计范围：Stage A 实现的代码、输入、无求解器测试
- **本审计不包含任何求解结果**（`SOLVER_EXECUTIONS: 0`）。所有"实际哪个约束 binding、BYOP 是否被选择"的问题都标为 `PENDING_RUN_GATE`。

## 1. 审计结论

| 项目 | 结论 | 依据 |
|---|---|---|
| 需求 | **通过** | 8 个母线 × 年份与获批的 mid 年度总量逐年一致（`MAINLINE_AIDC_RECONCILIATION.csv` 全部 PASS）。<br>• 2026 年：565.95 MW = 460.73 MW 继承爬坡 + 105.22 MW 研究新增；<br>• S0 研究需求为 0；<br>• 旧的 3 个测试 POI 需求为 0；<br>• `regional_dc` 强制关闭 |
| POI | **通过，但含代理值**（ML13-01..04） | 8 个聚合 POI，带日期的设备行逐行留证；未知容量标为 PROXY，没有无限进口 |
| 物理瓶颈 | **结构就绪** | POI、上游 KVL、ERM、程序 / COD 四层都有独立约束和诊断字段（结构测试 QA-DELAY-CAUSE）。<br>3 个真实压力日进入每期 Firm 约束（QA-STRESS-FIRM）。<br>binding 情况：`PENDING_RUN_GATE` |
| COD | **通过** | BYOP 和 POI 升级都按批准年份分批：2029 年批准的 2 年工期机组在 2029 / 2030 年不能出力（静态测试 + 结构测试）。<br>Firm 只计全年在运容量 |
| BYOP 技术与参数 | **通过** | 6 种主技术逐字段与 v1.3 附表一致（QA-PARAM）；2026–2031 逐年气价；Fast SOFC = 0；可复用资产池为空；正常调度与 Firm 信用分开 |
| 纯 LP | **通过** | 新代码没有整数或二元变量；S0、S1、S3、S2 开发商四个模型的 `integers + binaries = 0`（结构测试）；S2 不枚举模式，也没有 max-min 层 |
| S0–S3 一致性 | **通过（结构层面）** | S2 与 S3 读取同一组 BYOP 候选（6 种技术 × 按批准年份分批）、同一 POI、潜力、气源和 COD 规则。<br>S2 是"开发商联合 LP → 公共 LP 复核"；S3 是社会最优，物理机会集相同 |
| 运行门控 | **通过** | 未获批时正式入口以退出码 3 拒绝，在构建任何网络之前（L2 实测，`_gate_test/RUN_GATE.json`）；所有求解调用都经过 `_require_gate` |
| **是否推荐正式运行** | **推荐，条件是研究者先审计第 3 节所列代理值** | 见第 4 节运行建议 |

## 2. 无求解器测试

| 测试 | 结果 | 文件 |
|---|---|---|
| 静态测试 `test_mainline_v13.py`（QA-DC、COD、BESS、FIRM、SPACE、COST、LP、DELAY-CAUSE、STRESS-FIRM、GEOGRAPHY、BRIDGE、PARAM，共 16 项） | L2 上 **16/16 通过**；本地 6 项纯输入测试通过，其余因缺 pypsa 跳过 | `results/BYOP/mainline/static_tests.log` |
| 结构测试 `structural_mainline_v13.py`：真实 G-REAL 的 S0 / S1_EARLIEST / S3 / S2 开发商模型，只构建、不求解 | 见 Stage A 报告 §3 的最终计数；3 次求解调用均被拦截，`solver_executions = 0` | `results/BYOP/mainline/_structural/STRUCTURAL_CHECKS.csv`、`STRUCTURAL_REPORT.json` |
| 运行门控实测 | 退出码 3，`RUN_GATE: REFUSED`（未授权、缺批准 SHA、缺 manifest） | `results/BYOP/mainline/_gate_test/RUN_GATE.json` |
| 汇总程序冒烟测试（合成数据，本地） | 7 个表和 3 张图全部生成 | 草稿目录（未提交） |

模型规模（结构测试，2026–2031，每期 2 周 + 3 个压力日，3 小时分辨率）：

| 模型 | 变量 | 约束 |
|---|---:|---:|
| S0 | 4.07 M | 7.10 M |
| S1 | 4.15 M | 7.20 M |
| S3 | 4.39 M | 7.56 M |
| S2 开发商 | 0.13 M | 0.28 M |

## 3. 需要研究者确认的代理值（详见 `MAINLINE_V13_DECISION_LOG.md`）

1. **ML13-01**：6 个已有园区的 POI 设备容量按 Epoch 列出的建成规模代理。
2. **ML13-02**：Shackelford 的 E0 = 0，经升级最早 2029 年接网；燃气按 L1。
3. **ML13-03**：Helios 新增 830 MW 的 COD 取 2028。
4. **ML13-04**：POI 升级参数（2,000 MW / 3 年 / 160 USD/kW / 程序日期 2028）。
5. **ML13-05**：Abilene 现场既有燃机不录入。
6. **ML13-06**：现场风光上限 = 1.0 × 2031 年研究设施 MW。
7. **ML13-07**：现有燃气机组统一按逐年气价重新定价。
8. **ML13-08**：PCLR = 30%，200 小时 / 12 小时。

## 4. 对 Stage B 的预判与风险（不是结果）

- **最可能出现 Speed-to-Power 的母线**：Abilene（p610 2）和 Shackelford（p630 4）。这两个母线的研究需求超过已有或已批准的 POI 设备，升级不早于 2029 年。这是输入事实，不是求解结果。
- **其余 6 个母线**：设备不构成限制，是否延期取决于上游输电和 ERM。如果这两层都不 binding，S1 在这些母线可能没有延期，应如实报告。
- **BYOP 最早 COD**：
  - 燃气 BYOP 最早 2028 年（L1 气源）或 2029 年（L2 气源）；
  - SOFC 标准型最早 2029 年；
  - 光伏 2028 年，风电 2029 年；
  - BESS 2027 年（但没有 Firm 信用）。
  - 所以 2026–2027 年，任何情景都不可能靠 BYOP 加速，这是 v1.3 工期规则的直接结果。
- **程序日期主导风险**：若延期完全由 POI 程序日期（2028）和升级工期决定，按 v1.3 §4 如实报告，不调低线路容量。
- **运行时间**：v1.0 每个 3 场址算例要 5–7 小时。本轮模型约 4.4 M 变量，含 4 个主情景、5 次归因放松、S2 每年的字典序求解，预计显著更长（ML13-09）。

```text
STAGE_A_STATUS: READY_FOR_RESEARCHER_AUDIT
RUN_AUTHORIZATION: NOT_APPROVED
SOLVER_EXECUTIONS: 0
NEXT_STEP: RESEARCHER_REVIEW_REQUIRED
```
