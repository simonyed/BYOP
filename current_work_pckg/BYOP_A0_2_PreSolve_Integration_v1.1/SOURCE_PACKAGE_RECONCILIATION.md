# SOURCE_PACKAGE_RECONCILIATION — 原技术工作包的真实字节及来源说明

- 原始上传文件：`BYOP_ERCOT_Technology_Calibrated_Execution_Package_v2.0_2026-10-22(1).zip`
- 完整 ZIP SHA-256：`527ff8ab95dbaaaab5c0d6c160d405b05eae7a941d7b73d1850f92e5601b241d`
- `zipfile.testzip()`: **PASS**；9 个实际文件（和 1 个目录项）原样解压；无路径穿越。
- 解包目录：`source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22/`。内容无需“修正”即可用于参数源。
- 版本：`TECH_COMP_2_2026-10-22`；原 JSON 记载旧起点 `d0a9bf85…`，但仅作为**历史参数基准**，不是当前 GitHub 执行基点；当前核查起点依 A0 commit `946406d1…`。
- 技术：RICE, OCGT_aero, SOFC_NG, WIND, PV, BESS，共 6 种；年度交付池：18 行（2026–2031 三技术）；原县级臭氧表：**19 行，19 唯一 county FIPS**，其中 2015 非达标 16 行、仅 2008 非达标 3 行；不是 A0.2 v1.0 所说的“缺失”。
- 源参数里许可时长为固定**研究代理**，不能作为实际 TCEQ 审批天数或法定豁免；环保变量优先作用在许可途径/COD，而非环境税。

| 源文件 | 大小（字节） | SHA-256 |
|---|---:|---|
| `BYOP_COUNTY_OZONE_RULES_2026.csv` | 2904 | `8bfc4de5dd864e0107b8e1482c3d4193e31c43dad18aab81343910fd667def24` |
| `BYOP_SUPPLY_POOL_PROXY_V2.csv` | 2038 | `181af58f60dec3a87e2a812ab235debd79b5ca58db23fdbb2f949a5e3c0ce988` |
| `BYOP_TECH_PARAMETERS_V2.csv` | 2186 | `3956cdd25f25087dd74f0f6c959cf21bafb6eec1fd61ad295c0b91bbb9dcf26c` |
| `BYOP_TECH_PARAMETER_BASELINE_V2.json` | 12069 | `10bd868ba50929379be23b63d72626d8d528a1b358ce6b5a63a516e5771327c7` |
| `EXECUTION_WORK_PACKAGE.md` | 25249 | `c9e5842da7272328510b38c6760afc8bac2ad696fc64ce242843755b270cd052` |
| `PARAMETER_UNIT_CHECKS.json` | 1071 | `8eb2d6f1aeb406285c5954e91116b89e7503913266e99f017159b3ea19f6e68a` |
| `README.md` | 1251 | `0266a61b6baead3ba7b6c0ecd404c20228fa58ee4c77b27ee5b81f562a6277cf` |
| `SOURCE_REGISTER.json` | 2916 | `415571a3ff431578d14cd0d64f7199ee8656b3faf8eb4508b029c53ad74c815e` |
| `VALIDATE_STATIC_PARAMETERS.py` | 1382 | `26c0f9525d864154acbf3ba65c0f2e3f9e0cd66e21788099d84e9e2ac1869eaa` |

**原始文件不作编辑。** `source_tech_v2/ORIGINAL_SOURCE_ZIP.zip` 是再次封装的原 ZIP 副本，与本文件列示整体 SHA 一致。静态一致性由 `tools/validate_original_sources.py` 及原 `VALIDATE_STATIC_PARAMETERS.py` 验证；整个过程没有优化求解器调用。
