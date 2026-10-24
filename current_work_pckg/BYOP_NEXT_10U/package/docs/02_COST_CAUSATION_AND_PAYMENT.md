# 02｜公共资源增量与付款主体严格分账

## 研究目标
避免旧模型隐含的“公共电网为 AIDC 扩张，所有支出默认由其他电力用户支付”这一未证假设。须分开识别：
1. **工程建设与运营真实资源成本**（谁出钱不改变物理支出）；
2. **大型负荷在反事实下引致的净公共系统扩张**（经济学归因）；
3. **现行合同/费率/监管确立的现金支付和风险承担**（法律/财务归属），不得把第2项直接当作第3项。

## 资产四类
A `DC_DIRECT_INTERCONNECTION`：专属变压器、bay、radial interconnection、直接接入设施；核实 §25.192 的直接接入成本定义后按适用协议计 CIAC。
B `GRID_UPSTREAM_SYSTEM_UPGRADE`：网络加固和共同输电项目；批次升级可能有 financial security，但未知法定最终支付不得设 DC=100%。
C `GRID_GENERAL_EXPANSION`：公共发电、储能、可共用输电；通过 S1-S0 等净变化归因，绝不自动视为 CIAC。
D `BACKGROUND_COMMITTED`：2025 已存在/已承诺的 DWB Stage 2 与 PBRP 765 工程等；共同背景下不记为本研究新增 DC 的全部工程支出。

## 三本账 & reconciliation
- `RESOURCE_COST_LEDGER`: `asset_id,year,scenario,capex_2025USD,opex_2025USD,real_reliability_cost,emission_externality_cost,real_resource_PV,beneficiary_evidence`。
- `COST_CAUSATION_LEDGER`: `asset_id,site_or_group,scenario,s0_MW,s1_MW,s2_MW,s3_MW,added_MW,avoided_MW,shifted_COD,delta_resource_PV,attribution_method,confidence`。
- `PAYMENT_RISK_LEDGER`: `asset_id,site_id,applicable_rule,study_fee_paid,study_fee_refund,CIAC_paid,system_upgrade_security_posted,security_kind,security_returned,security_forfeited,security_financing_cost,network_service_charge,unrecovered_cost,payer,beneficiary,contract_evidence,status`。

**不重不漏：**资产真实 CAPEX 只在资源成本算一次；CIAC/payment 是从开发商到账务接收方的 transfer（若费用支付用于工程购买，则不得再在社会成本加一次付款本身）；financial security 保证金本金若可退是受限现金/信用，不是不可返还资本开支；实际融资成本、罚没、未回收成本另计；若罚没拨给电网抵减费率，不得同时计整个担保本金和已抵减额为双重社会支出。

**AIDC 增量净资源**：同一工程ID/建设COD/公共设施型号匹配时，`ΔCpublic(S1) = Cpublic(S1)-Cpublic(S0)`；单个 S1 成本不等于 AIDC 诱发的增量，不得把 S0 已建设或基线 sunk 的资产重复收费。替代投资可能使某类公共资产减少；账本允许负的净增量。对 S2/S3 同理比较，并提供按资产/年/区域的新增、避免、提前、延期项。

### 德州制度的准确应用（2026-10-24）
- Texas SB6 2025 / PUCT 16 TAC §25.194 在 October 2, 2026 Texas Register 正式 adopted，适用 ERCOT 特定 ≥75 MW **单站点**的大负荷及部分共址/扩容情形；须核查有效日和既有合同/已送电过渡条款。
- Intermediate agreement: 实际要求 **$100,000 study fee，未使用余额退回**；通常 `$50,000/MW × requested/incremental MW` financial security。学习新的五年通胀调整时间规则，不向 2026 初始所有项目追溯同一正式义务。
- SLLIA: financial security 通常为 `max($50,000/MW × contracted peak MW, allocated system-upgrade cost)`；**是担保，不是系统升级已经由客户不可退还支付的费用**。直接接入设施采用不可退还 CIAC（具体范围依 §25.192 定义、相关规则与实际协议）。
- 2026-07 关于 12CP、§25.193 minimum billing demand 和 §25.252 的 Texas Register 页面为 PROPOSED。没有经过官方最终 adopted 验证，不得假设强制 20 年合同 100% 容量收费。
- FERC June 2026 six RTO/ISO show-cause orders 是改革程序和政策方向，**不将其作为 ERCOT 已生效费率**。
- 对尚不明确的B/C类工程付款：标记 `payer_status = UNRESOLVED_LEGAL_ALLOCATOR`，输出经济归因但不要虚构最后法定付款。

## S2/S3 决策一致性
- S2 已知非退还 CIAC + 实际收费及资金占用**成本**进入 private cost 的第二层；仍严格 speed-first。不会因为只变开发商付款、而不变资金约束/审批条件，就自动改善第一层最快交付。
- S3 的 objective 含实际工程 CAPEX/OPEX、真实环境与可靠性外部性，**不再加 CIAC/security 作为额外资源耗费**；S2/S3 共享相同工程、POI、工期和其他物理可行集。
- 在没有证明流动性/资格约束的情况下，针对所有已计算优化结果可以零求解器比较“现行已核实支付 vs 假设改为多付”的现金负担，但这种会计反事实不能声称改变最优速度/COD。

## 输出与守恒测试
输出 `PUBLIC_ASSET_LEDGER.csv`, `AIDC_INCREMENTAL_PUBLIC_COST.csv`, `COST_INCIDENT_MATRIX.csv`, `COST_CAUSATION_LEDGER.csv`, `PAYMENT_RISK_LEDGER.csv`, `S0_S1_PUBLIC_DELTA.csv`。

负面检查：原样生成/融资费/退还/社会成本不同；同一 asset 不跨 A/B/C/D 重复；任何 `unresolved` 上游工程不得凭模型假设自动全由 developer 支付；年度资源成本 PV 在不同付款分配下不改变，除非物理优化决策真的改变。保障金 $50,000/MW 的量纲为美元/兆瓦，而不是 USD/kW，也不是 $50,000/kW。
