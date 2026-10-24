# Texas 大型负荷成本责任：正式规则与提案（2026-10-24 检查）

**适用性不是按研究 bus 判断，而是按实际单一站点和当时合同/投运状态判断。** ERCOT 和 FERC/PJM 制度不能混用。

## 已通过、应进入当前法规账（带生效时点检查）
1. Texas SB 6 (2025) 形成 PURA §37.0561/§35.004 相关大型负荷责任背景；PUCT 16 TAC §25.194 于 2026-10-02 Texas Register 公布 adopted。适用客户包括特定尚未 energized 的单站 ≥75 MW 新接入/扩容，及规则规定共址条件；有既有合同、扩容和过渡例外，要逐笔检查。
2. Intermediate agreement 原文要求 **$100,000 study fee**，未使用部分通常退回；以及 `$50,000/MW × requested / incremental MW` 的 financial security；对须提前采购的 long-lead equipment 可能要追加担保。保证金不是全部已付公共建设资本支出。
3. SLLIA 阶段通常要求 `max($50,000/MW × contracted_peak_MW, allocated_system_upgrade_cost)` security；**不代表同等系统升级额已支付 CIAC**。符合定义的 direct interconnection costs 支付不可退还 CIAC，须按合同和 §25.192 定义确定，不将 B/C 网络扩张一律纳入。
4. 申请披露还包括 phased energization 月/年和容量、现场 backup/gas/permit，对“真实数据定义起点”很重要；不可把 Batch Zero 预计时间直接写成已获批 COD。

官方原文：https://www.sos.state.tx.us/texreg/archive/October22026/Adopted%20Rules/16.ECONOMIC%20REGULATION.html

## 尚未确认为正式生效规则的内容
2026-07-24 Texas Register 的 §25.192/§25.193（12CP / minimum billing demand）和 §25.252（大型负荷 tariff）为 `PROPOSED`；本包中不把“20 年最低计费=100%签约峰值”作为正式默认法定现金付款，除非执行时检索到了最终采用的公开官方文本，并记录 adopted_date / effective_date / exception。

官方提案：https://www.sos.state.tx.us/texreg/archive/July242026/Proposed%20Rules/16.ECONOMIC%20REGULATION.html

## 全国改革政策背景（不代表 ERCOT 法规）
FERC 2026-06 大型负荷六项 show-cause 命令强调升级透明度、成本回收协议、避免成本转嫁，但命令本身不会直接在 ERCOT 确立统一费率；后续提交期 2026-11 仍在进行。

官方背景：https://www.ferc.gov/cost-transparency-customer-protection

## 报表法条字段
`legal_id,jurisdiction,source_title,url,publication_date,checked_date,status(LAW|ADOPTED_RULE|PROPOSED_RULE|PRACTICE|MODEL_PROXY),applicability,grandfather_exception,amount_units,where_modeled,uncertainty`
