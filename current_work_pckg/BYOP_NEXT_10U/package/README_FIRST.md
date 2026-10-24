# BYOP NEXT-10U 无人值守主线工作包（2026-10-24）

**研究目标：**“用真实数据定义系统起点，用工程规律定义未来可行域，用优化模型决定未来建设路径”。修复统一三年 POI 代理造成的伪速度优势，建立公共工程**经济因果与实际付款**分离的三本账，在 ERCOT 2026–2031 最小主线上尽可能完成 S0 → S1 → S2 → S3 → S3_mS2。

**唯一权威仓库：** https://github.com/simonyed/BYOP 的 `main`（起草时检查 HEAD `8e1cf95f`；启动前重新 fetch 核验，严禁 reset 用户改动）。2025 v1.7L 有损基准已经 ADOPTED，SHA `f9aa87aea496f7c07ea4aca0439a703e7eaa90d08cb66c5bc6f149ea60eeefb6`。旧 NEXT-09 的 S0/S1 保持 NOT_APPROVED、零求解器调用，**不能直接复用旧批准**。新模型一律使用新命名 config/out_dir/manifest 与独立 ledger。

## 目录 / 复制说明（重要）

本 ZIP **不含**原始工程包的 `raw/`、`processed/`。将原 ZIP `BYOP_Engineering_Data_Package_v1.0_2026-10-23.zip` 内的同名原始文件夹及其**完整内容、子目录**复制为：

```
BYOP_NEXT_10U_Engineering_POI_Cost_Autonomous/
├── README_FIRST.md
├── docs/                       # 执行、数据、算法、成本、法规、验收
├── legal/                      # 法规来源索引；不含全文大文件
├── scripts/                    # 复制后预检/自检
├── engineering_data/
│   ├── raw/                    # ← 原工程包 raw/ 整个目录的内容
│   ├── processed/              # ← 原工程包 processed/ 整个目录的内容
│   └── reference/              # ← 可选：原工程包的小文件说明/manifest/config/scripts，不是必需
├── templates/
├── manifest/
└── results_interface/
```

请勿产生 `engineering_data/raw/raw`、`engineering_data/processed/processed`、`engineering_data/BYOP_Engineering_Data_Package_v1.0_2026-10-23/raw` 等多层嵌套。原包若已有子目录，保持其相对路径不变。

复制后在本包根目录运行：
`python scripts/preflight_external_data.py --data-dir engineering_data --out-dir manifest/local_preflight`
生成清单和缺失提示；**不会将原始数据上传 GitHub，也不会修改它们**。

此包不是原工程包的全量复制。原始原件及证据链先使用你本地解压的数据；原包其他小文件/README/manifest 可选复制到 `engineering_data/reference/`；**建议**特别复制原包中 `engineering_baseline.json` 所在的 `config/` 轻量目录（若不在 processed 内）、来源/哈希 manifest 和 `scripts/validate_package.py`，保持它们在 `reference/` 中原有相对路径，由执行方复查，不重复下载。若没有提供，仅标注缺失证据，不得自动用伪造值替代。

## 文件阅读顺序

1. `docs/00_EXECUTION_AUTHORITY_AND_SEQUENCE.md`：本轮用户直接授权、算例顺序、计算预算和无人值守恢复规则。
2. `docs/01_ENGINEERING_DATA_AND_POI.md`：原工程包真实表格的载入、工程可行域和消除固定 3 年代理。
3. `docs/02_COST_CAUSATION_AND_PAYMENT.md`：资产成本因果、CIAC/担保、开发商与用户负担账。
4. `docs/03_VALIDATION_AND_ACCEPTANCE.md`：门禁、S0 科学验收、S1/S2/S3 比较与停止条件。
5. `docs/04_RUNTIME_HANDOFF_AND_DELIVERABLES.md`：远程计算部署、提交与回报格式。
6. `legal/LEGAL_EVIDENCE.md`：2026-10-24 政策状态与来源，须区分正式规则与提案。

## 当前包明确不做
- 不重新下载 TPIT/EIA/ATB/NEMA 数百 MB，raw/processed 不复制回 GitHub。
- 不修改 2025 v1.7L 原始 NetCDF，不覆盖 NEXT-08/08b/09 旧 ledger。
- 不用预设 2/3/4 年的无证统一工期替代 3 年作为“新事实”。
- 不把系统升级担保本金或整条公共网线成本默认为开发商已付款，也不把 CIAC 收入再加作社会成本。
- 不运行 2026–2050 全期限大型规划，不做几十组 Low/Mid/High 随机敏感度；先 2026–2031 四主情景。
