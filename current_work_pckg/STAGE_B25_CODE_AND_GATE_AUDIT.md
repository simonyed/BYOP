# STAGE_B25_CODE_AND_GATE_AUDIT：B2.5 代码与门控审计

- 日期：2026-10-21（纽约时间）
- B2-R 基线：`3b044c1c038bf42946a6b445f157f08e5efa079c`
- **B2.5 代码提交（待批准）：`__B25_SHA__`**
- `RUN_AUTHORIZATION: NOT_APPROVED`；`approved_git_sha: null`；`SOLVER_EXECUTIONS_B25: 0`

## 1. 修改的文件与函数

| 文件 | 函数 / 位置 | 性质 | 是否改动约束、目标、变量 |
|---|---|---|---|
| `workflow/byop/post/collect_mainline.py` | 新增 `cost_book_decomposition()`、`science_layers()`、`method_flags()`、`_weights()`、`TECH_REQUIRED`、`TECH_REQUIRED_CORE`<br>`collect()` 新增：`MAINLINE_COST_BOOK_DECOMPOSITION.csv`、`STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv`（汇总各情景的潮流导出）、门控表新字段 `TECHNICAL_GATE` / `METHOD_FLAGS` / `EXPLORATORY_USE` / `FINAL_SCIENTIFIC_USE` / `cost_book_identities` / `lex_audit_all_satisfied` | 后处理 | 否。旧的 `SCIENTIFIC_USE` 计算位置和规则不变 |
| `workflow/byop/model/rearch_mech.py` | 新增 `s0cal_flow_summary()`、`ml_export_flows()`；`go()` 在求解**之后**调用 `ml_export_flows(n, tag, out)`（只在 mainline 下） | 只增加导出 | **否**：只读取 `n.links_t.p0`、`n.generators_t.p`、`n.lines_t.p0`；不访问 `n.model`，不调用 `add_constraints`（测试检查） |
| `workflow/byop/post/stage_b25_audit.py` | 新建：B2.5 的 4 个 CSV | 后处理 | 否 |
| `workflow/byop/run/run_mainline.sh` | 新增 `pilot_core_b3e`（`…_B3_EXPLORATORY_V1`，`--scenarios S0 S1_EARLIEST S3 S2 S3_mS2`，没有 `--attribution`）<br>`run()` 对**非空目录**一律拒绝（返回码 5，需人工核对） | 运行组织 | 否 |
| `workflow/config/config.byop_ercot_mainline.yaml` | 授权复位为 `NOT_APPROVED` / `null`；`stage` 标签改为 `STAGE_B25_METHOD_AUDIT`（只是说明文字，不影响行为） | 门控 | 否 |
| `workflow/byop/tests/test_mainline_v13.py` | 新增 B2.5 测试（11 个用例） | 测试 | — |
| `current_work_pckg/MAINLINE_V13_PRE_RUN_MANIFEST.json` | 按新代码重建所有代码和输入的哈希 | 清单 | — |

物理模型、ERM、S0CAL、VOLL、POI、技术参数、样本和时间窗口**都没有改动**。

## 2. 测试（L2，无求解器）

| 测试 | 结果 |
|---|---|
| 静态测试 `test_mainline_v13.py` | **50 / 50 通过**（`static_tests_b25.log`） |
| B2.5 新测试覆盖的内容 | • 成本账本恒等式 PASS / FAIL，VOLL 与实物支出分开，转移支付不计入<br>• 科学状态分层 7 个用例：S0 切负荷但 no-harm PASS → 可探索并带标志；不是 optimal、no-harm FAIL、字段缺失、48 键失败、S2 不收敛 → BLOCKED；CORE 全部通过 → PASS；最终科学使用从不自动变成 ALLOWED<br>• 合成算例上旧 `SCIENTIFIC_USE` 保持不变，同时有新状态层<br>• `s0cal_flow_summary` 合成测试：正反向不相加；`ml_export_flows` 不访问模型<br>• `pilot_core_b3e` DRY 命令与目录保护 |
| 结构测试 | **45 / 45 通过**（`_structural_b25/`）；`solver_executions = 0`，3 次求解调用被拦截 |
| 门控 | `approved: false`，原因：`run_authorization=NOT_APPROVED`、`approved_git_sha` 缺失、manifest 哈希不一致（`gate_check_b25.log`） |
| DRY `pilot_core_b3e` | 只含 `S0 S1_EARLIEST S3 S2 S3_mS2`，新目录，使用原 B1 的 ERM / S0CAL，没有 `--attribution`（`dry_pilot_core_b3e.log`） |
| 输入哈希 | 基准 `.nc` `19034285…`，ERM `7d0c02f1…`，S0CAL `30bf497e…`：都没有变化 |

## 3. 回报（工作包 §6）

```text
REPO: simonyed/BYOP
BRANCH: mainline-v13-stageA
B2_R_BASELINE_SHA: 3b044c1c038bf42946a6b445f157f08e5efa079c
B25_CODE_FIX_SHA: __B25_SHA__
B25_RUN_AUTHORIZATION: NOT_APPROVED
B25_SOLVER_EXECUTIONS: 0
B25_INPUT_HASHES_UNCHANGED: PASS
ERM_2026_METHOD_FLAG: ON (105.22 MW_IT-year, descriptive)
S0_RELIABILITY_REVIEW_REQUIRED: ON (11874.50 MWh)
B2_R_NO_HARM: PASS (max violation 0.001 MW = constraint slack)
COST_DECOMPOSITION_CHECK: PASS
SCIENCE_GATE_TESTS: 50/50 static (incl. 11 B2.5 cases), 45/45 structural
DRY_B3_SCENARIOS: S0 S1_EARLIEST S3 S2 S3_mS2
B3_RUN_STATUS: NOT_AUTHORIZED
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_SHA_APPROVAL
```
