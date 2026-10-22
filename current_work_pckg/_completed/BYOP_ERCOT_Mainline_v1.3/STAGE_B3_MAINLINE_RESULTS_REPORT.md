# STAGE_B3_MAINLINE_RESULTS_REPORT：B3-E 探索性主线结果报告

- 日期：2026-10-22（时间均为纽约时间 EDT）
- 依据：`BYOP_ERCOT_StageB25_B3_Exploratory_Work_Package_v1.0_2026-10-21.md` §3、§4.2（本报告即该工作包要求的 `STAGE_B3_EXPLORATORY_RESULTS_REPORT.md`；按研究者指示使用此文件名）
- 算例：`MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1`；结果目录 `workflow/results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1/`
- **状态**：
  - `TECHNICAL_GATE = PASS`
  - `EXPLORATORY_USE = PERMITTED_WITH_METHOD_FLAGS`
  - `FINAL_SCIENTIFIC_USE = PENDING_METHOD_VALIDATION`
  - 旧列 `SCIENTIFIC_USE = BLOCKED: no_load_shed`，按规则保留原值
- 以下结论都是**探索性**的，带有 2026 年 ERM 和 S0 可靠性两个方法标志。
- **B3 结束后已停止**；B4 执行次数为 0。

## 0. 执行事实

| 项目 | 值 |
|---|---|
| 授权 | 研究者在对话中批准："批准 01e761da 的单次 pilot_core_b3e 运行……B3 结束后停止"。运行后配置已复位为 `NOT_APPROVED` |
| 代码 | 批准 SHA：`01e761dabab25cce514c10abb1824936410e3f87`<br>运行时 HEAD：`8073d0e4`，与批准提交相比只改了配置里的授权项<br>门控 `approved: true` |
| 命令 | `THREADS=20 bash byop/run/run_mainline.sh pilot_core_b3e`<br>`--scenarios S0 S1_EARLIEST S3 S2 S3_mS2`，没有 `--attribution` |
| 运行时间 | 2026-10-21 21:13:04 – 2026-10-22 00:27:07（3 小时 14 分），退出码 0 |
| 输入 | 基准 `.nc` `19034285…`；B1 ERM `7d0c02f1…`；B1 S0CAL `30bf497e…`（9 条线路、1,095.6 MW，已载入）；VOLL 35,685 |

求解结果（全部 optimal，整数变量都为 0）：

| 情景 | 用时 | 变量数 | 说明 |
|---|---:|---:|---|
| S0 | 1,591 s | 4.09 M | 目标值与 B2-R 相差 2.8e-10（相对），**可复现** |
| S1_EARLIEST | 3,036 s | 4.18 M | 字典序 12 层 OPTIMAL；47 / 47 层在最终解上满足；目标值与 B2-R 相差 9e-8 |
| S3 | 2,148 s | 4.42 M | — |
| S2（第 1 轮） | 1,939 s | 4.42 M | **第 1 轮即收敛**：48 个母线—年份都没有低于开发商计划，`S2_final = S2（iteration 1）` |
| S3_mS2 | 2,046 s | 4.42 M | — |

- 开发商 LP（字典序 6 层 + 成本阶段）：optimal，整数变量 0。
- 硬性检查**全部通过**：能量平衡、在线 IT 单调、no-harm（最大违反 0.001 MW，在允许余量内）、POI ≤ 设备、未接网不供电、中断在上限内、开发商 LP、S2 收敛、字典序、成本恒等式。
- **M4 匹配**：48 个键齐全且唯一，没有缺失值，**最大服务差 0.0 MW**。

## 1. M1：延期能否重现？S2_final 让哪些母线、哪些年份提前投运？

**S1 的 312.75 MW·年延期完全重现**（与 B2-R 逐键一致）。

| 情景 | 延期 MW·年 |
|---|---:|
| S1_EARLIEST | **312.75** |
| **S2_final** | **173.17**（比 S1 少 139.58） |
| S3（自由服务量） | 76.80 |
| S3_mS2（服务量 = S2_final） | 173.17 |

S2_final 相对 S1 的提速**只发生在 2028 年的两个母线**：

| 母线 | 年份 | S1 延期 | S2_final 延期 | 提速原因 |
|---|---|---:|---:|---|
| **Shackelford（p630 4）** | 2028 | 129.26 | 0 | 2026 年批准、2028 年投运的 **186.4 MW Aero OCGT** 以**孤岛（IS）**方式全额供电。2029 年起转为并网灵活（GF）：电网接网升级投运后，BYOP 发电量从 2028 年的 617 GWh 降到 86–124 GWh/年，即 **Bridge-to-Grid** |
| **Abilene（p610 2）** | 2028 | 10.32 | 0 | 2028 年投运的 **126.1 MW Aero OCGT**，与 955.6 MW POI 设备一起供电（GF）；每年 84–104 GWh |

**没有提速的部分**：

- **2026 年（105.22 MW，所有母线）**：带 `ERM_2026_METHOD_FLAG`。所有 BYOP 技术最早 2027–2029 年投运（燃气 L1 和 aero 最早 2028 年），而 S1 给开发商的 2026 年 Firm 报价为 0，所以 S2 在 2026 年不可能提速。**这不能说明 BYOP 没有价值**，它是由工期和 2026 年 ERM 零裕度共同决定的。
- **Red Oak、Temple（2027 年，共 68.0 MW）**：两地的燃气为 L2 证据等级，aero 和 RICE 最早 2029 年投运，SOFC 也最早 2029 年，所以 2027 年没有可用的 BYOP。2028 年起这两个母线由电网全额供电（GO_C）。
- **其余 4 个母线**：2027 年起电网全额供电。S2 中为 GO_F（2027 年）和 GO_C（2028 年起）。

**S3 与 S2_final 的差（96.37 MW·年）全部在 2026 年**：

| 情景 | 2026 年是否供电 | 原因 |
|---|---|---|
| S3 | 给有设备的 5 个母线供电 96.3 MW（Firm 进口） | 使用 0.5% 的非计划中断预算和少量 PCLR 削减，越过 ERM 最紧的时段 |
| S1_EARLIEST | 不供电 | 严格 Firm 基线，不允许中断 |
| S2 | 不供电 | 继承 S1 给出的 0 报价 |

这是**规则不对称**：S2 的报价来自严格 Firm 的 S1；S3 直接面对电网，并可以使用中断预算。叠加 2026 年 ERM 的方法标志，这一差异**不能当作私人与社会效率的差别**。

## 2. 开发商选择了什么 BYOP？是否符合各项限制？（`STAGE_B3_M2_ASSET_COMMITMENT_AND_COD.csv`、`MAINLINE_S2_MODES_TECH.csv`）

| 资产 | 技术 | 批准年份 | COD | MW | 检查 |
|---|---|---:|---:|---:|---|
| `DC_p630 4 BYOP OCGT_aero q2026` | Aero OCGT | 2026 | 2028.0 | 186.37 | 工期 2 年；燃气 L1（支线 1 年，与工期并行）；2028 年之前不出力；压力时段只按 1/r 计 Firm |
| `DC_p610 2 BYOP OCGT_aero q2026` | Aero OCGT | 2026 | 2028.0 | 126.14 | 同上 |

- 开发商**没有选择** RICE、SOFC、风电、光伏或 BESS。
- 按 v1.3 参数，aero 的造价（2,275 USD/kW）和工期（2 年）在可行的燃气技术中最有利。SOFC 工期 3 年，赶不上 2028 年；RICE 造价 2,450、FOM 更高。
- 风电、光伏、BESS 没有 Firm 信用，无法单独满足 Speed-First 的服务要求。
- **供电模式**（求解后归类，不是 LP 中的离散变量）：
  - 2027 年：GO_F 为主；
  - 2028–2031 年：6 个母线 GO_C，Abilene GF；Shackelford 2028 年 IS，之后 GF。
- S3_mS2 的选择几乎相同：Abilene 135.9 MW、Shackelford 186.4 MW 的 aero。

## 3. M2：公共投资的变化（`STAGE_B3_M2_PUBLIC_EXPANSION_BY_CARRIER_YEAR.csv`；不含 S0CAL 和 BYOP）

2031 年在运的公共新增容量（MW）：

| 技术 | S0 | S1_EARLIEST | S2_final | S3_mS2 | S1 − S0 | **S2_final − S1** | S3_mS2 − S2_final |
|---|---:|---:|---:|---:|---:|---:|---:|
| 线路扩建 AC_exp | 35,181 | 36,195 | 36,572 | 36,657 | +1,014 | **+377** | +85 |
| 陆上风电 | 25,747 | 28,152 | 28,362 | 28,342 | +2,405 | **+210** | −19 |
| 光伏 | 6,215 | 7,953 | 7,653 | 7,674 | +1,738 | **−300** | +21 |
| 4 小时储能 | 345 | 530 | 0 | 0 | +185 | **−530** | 0 |
| 8 小时储能 | 252 | 1,231 | 611 | 609 | +979 | **−620** | −2 |
| CCGT | 158 | 226 | 0 | 0 | +68 | **−226** | 0 |
| POI 升级（累计） | 0 | 2,020 | 1,770 | 1,763 | +2,020 | −250 | −8 |

**解读**（只针对 2026–2031 年的观察窗口）：

- 新增 AIDC（S1 − S0）带来更多风电、光伏、储能、CCGT、线路和 POI 升级。
- 开发商自建 312 MW aero 之后（S2_final − S1）：
  - **公共的可靠容量类投资被替代**：储能 −1,150 MW、CCGT −226 MW、光伏 −300 MW、POI 升级 −250 MW；
  - 线路扩建 +377 MW、风电 +210 MW 小幅增加；
  - 按母线看，减少最多的是 p630 8、p610 2（Abilene）、p630 13、p630 2，增加最多的是 p640 2、p600 3、p630 4。
- 公共资本（PV）：S1 86.1 亿 → S2_final 75.2 亿 USD（−10.9 亿）；BYOP 资本 1.30 亿 USD。
- 两个情景的服务轨迹不同，所以这不是同服务量下的比较。
- **不对 2031 年以后的搁浅或路径依赖下结论**（M3）。

## 4. M4：同服务量下 S2_final 与 S3_mS2 的成本差（`STAGE_B3_M4_COST_COMPONENTS.csv`、`MAINLINE_MATCHED_SERVICE_COST.csv`）

48 个键严格匹配，最大服务差 0.0 MW IT，所以 `gap_status = VALID`。

| 项目（USD，PV） | S2_final | S3_mS2 | **S2_final − S3_mS2** |
|---|---:|---:|---:|
| 实物资源支出代理（扣除 VOLL） | 52,794.0 M | 52,793.6 M | **+0.40 M** |
| ↳ 公共资本（含 POI 升级） | 7,516.8 M | 7,512.3 M | +4.52 M |
| ↳ BYOP 资本 | 130.2 M | 134.2 M | −4.05 M |
| ↳ 系统运行（含 BYOP 燃料） | 45,147.1 M | 45,147.2 M | −0.07 M |
| 既有用户未服务损失（VOLL） | 350.1 M | 348.4 M | **+1.76 M** |
| 研究 AIDC 延迟损失 | 481.2 M | 481.2 M | 0（服务量相同） |
| 削减与中断损失 | 56.8 M | 56.7 M | +0.12 M |
| **社会总成本** | 53,682.1 M | 53,679.8 M | **+2.28 M（+0.004%）** |
| 购电转移支付（不计入社会成本） | 1,452.8 M | 1,108.7 M | — |

**结论**：在相同的 IT 交付轨迹下，统一开发商的 BYOP 与公共投资组合，与社会协调方案**几乎没有效率差别**：社会总成本只高 228 万美元。原因是两者选择了几乎相同的 aero 组合和公共投资。

按工作包，这是有效的发现，不需要非零的效率损失。它的前提是：
- 本模型中开发商的私人激励（7% WACC、按 S1 电价购电）与社会目标的差异有限；
- 可选技术和工期在两边相同。

## 5. 背景可靠性与 S0CAL 线路

**既有用户切负荷（MWh，6 年合计）**：

| S0 | S1_EARLIEST | S3 | S2_final | S3_mS2 |
|---:|---:|---:|---:|---:|
| 11,874.5 | 9,896.7 | 10,044.7 | 10,187.1 | 10,135.9 |

- 继承爬坡的切负荷在各情景都约 0.48 MWh。
- 所有情景的 no-harm 都满足（最大违反 0.001 MW）。
- `S0_RELIABILITY_REVIEW_REQUIRED` 仍为 **ON**（总量 11,874.5 MWh，单母线峰值 75.1 MW）。

**AIDC 邻近的 4 条 S0CAL 线路**（`STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv`）：

| 线路 | 连接 | 校准增容 MW |
|---|---|---:|
| TL73 | Red Oak – Temple | 260 |
| TL63 | Red Oak | 228 |
| TL3 | Helios | 147 |
| TL26 | Abilene | 31 |

- 4 条线路在**所有情景（包括 S0）**中都满载：最大利用率 1.0，按权重计约 7,400–8,400 满载小时 / 年。
- 也就是说，这些免费校准增容在 S0 中已被背景负荷和继承爬坡用满，**没有为研究 AIDC 留出多余的送电能力**。研究需求的接网没有因为它们而被"放宽"。
- 线路潮流只导出了 2028 年 DFW 的诊断表（`scenarios/*/line_flows_2028_dfw.csv.gz`），本报告没有据此推算拥堵分摊。

## 6. 机制判断（探索性）

| 机制 | 本轮结果 | 条件 |
|---|---|---|
| **M1** | **部分支持**：BYOP 在 Shackelford 和 Abilene 的 2028 年带来 139.6 MW·年的提速，正好对应 POI / 程序层的瓶颈；孤岛 → 并网的过渡清晰可见 | 2026 年的延期与 ERM 方法标志相关，BYOP 工期也无法赶上 2026 年；Red Oak / Temple 2027 年受燃气证据等级限制 |
| **M2** | **支持（窗口内）**：BYOP 替代了公共的可靠容量类投资（储能 −1.15 GW、CCGT −0.23 GW、POI 升级 −0.25 GW），线路和风电略增 | 只看 2026–2031 年；S1 与 S2 的服务量不同，所以不是同服务量比较 |
| **M4** | **几乎没有效率差**（+0.004%），在严格的同服务量匹配下成立 | 依赖当前的私人参数和统一可行集 |
| **M3** | 未评估 | 只保存了资产承诺和 COD 台账 |

## 7. 回报（工作包 §6）

```text
B3_APPROVED_CODE_SHA: 01e761dabab25cce514c10abb1824936410e3f87
B3_EXECUTION_GIT_HEAD: 8073d0e472217f04596d6c73a3f881a2930a0983
B3_GATE: APPROVED
B3_CASE_ID: MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1
B3_SCENARIOS_COMPLETED: S0, S1_EARLIEST, S3, S2 (-> S2_final, iteration 1), S3_mS2
B3_LP_INTEGER_VARIABLES: 0
B3_SOLVER_STATUS_BY_SCENARIO: S0 optimal; S1_EARLIEST optimal (lex OPTIMAL, 47/47); S3 optimal; S2 optimal; S3_mS2 optimal
B3_S1_DELAY_MW_IT_YEAR: 312.7528
B3_S2_FINAL_DELAY_MW_IT_YEAR: 173.1727
B3_S2_FINAL_SELECTED_ITERATION: 1
B3_S2_PUBLIC_CONVERGED: TRUE
B3_M2_PUBLIC_DELTA: see STAGE_B3_M2_PUBLIC_EXPANSION_BY_CARRIER_YEAR.csv (S2_final-S1 2031: storage -1150 MW, CCGT -226, solar -300, POI upgrade -250, AC_exp +377, wind +210)
B3_M4_48_KEYS_MATCHED: PASS (max gap 0.0 MW IT)
B3_M4_COST_COMPONENTS_VALID: PASS (identities PASS; S2_final - S3_mS2 social total +2.28 M USD)
B3_ERM_2026_METHOD_FLAG: ON
B3_S0_RELIABILITY_FLAG: ON (S0 11874.5 MWh > 1000; bus peak 75.1 MW > 10; inherited 0.48 MWh/yr <= 1)
B3_TECHNICAL_GATE: PASS
B3_EXPLORATORY_USE: PERMITTED_WITH_METHOD_FLAGS
B3_FINAL_SCIENTIFIC_USE: PENDING_METHOD_VALIDATION
B4_EXECUTIONS: 0
NEXT_STEP: STOP_AND_RETURN_FOR_RESEARCHER_RESULTS_AUDIT
```

**下一步可能需要研究者审计的问题**（建议，均未执行）：
1. 2026 年 ERM 的反事实敏感性。
2. S1 严格 Firm 报价与 S3 可中断接入之间的规则不对称。
3. Red Oak / Temple 燃气证据等级对 BYOP 可行性的影响。
4. S0 在 2027–2028 年的剩余切负荷。
