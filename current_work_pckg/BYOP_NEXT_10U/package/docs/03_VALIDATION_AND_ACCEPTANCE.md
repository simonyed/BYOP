# 03｜强制 Gate、S0 科学可靠性和正式结果口径

## G0 数据（0求解）
- external engineering_data/raw 与 /processed 可定位；所有 `required` 7 个表唯一匹配，或有证据冲突时 fail-closed；原始数据 SHA/bytes/schema 归档，避免读取 CSV 错版本。
- 披露证据中的 `unknown`, `proxy`, `official approved`, `energized` 必须区分；无空字符串转零，预测不能冒充获批容量。
- 覆盖 16 sites / 160 tranches / 320 candidates 是原包历史数目，若实际版本不同必须输出有来源的差异说明而不是强行补齐。

## G1 LP 结构（0求解）
- 整体仍连续 LP (0 integer)，2025 v1.7L SHA 固定，2025 网络不重校准。
- S0 不含研究新增 AIDC；S1/S2/S3 采用同一新增AIDC需求/站点/可见工程/物理容量/工期/成本来源。
- 新 S1 不能读取 3y proxy/2000MW/site/统一 COD；除项目自身有明确新工程证据或可辨研究代理；两者分级报告。
- 设备、公共网络、Firm、Conditional、gas、环境许可、逐时SOC不能交叉混用或重复认证。
- 财务真实资源成本/转移/担保三种费用在模型建构和后处理严格分离；与旧 public cost 不发生重复计费。

## G2 求解与验收：S0 （一调用）
- Gurobi optimal；KCL、3GW 备用、storage segment SOC、线路对称投资、已付费扩张、一年内资产 COD 均符合已有技术 QA。
- **额外科学 gate（用户此前明确要求避免旧 S0 TECHNICAL PASS 却产生异常缺供）：**输出每模型年既有用户 weighted EENS / 当年 background load，最大瞬时切负荷 / 当年 peak，Far West pocket 逐年汇总及 raw vs weighted snapshots。建议在模型求解前锁定 conservatively `EENS_y / annual_native_load_y <= 1e-5` 和 `max_snapshot_native_shed / native_peak_y <= 1e-3`；阈值属于本研究代理，不可称 ERCOT 法规。两条件均通过才进入 S1；若样本采样产生超阈值需要核查，但不能静默放宽。把实际 S0 科学 gate 判定封存。
- 旧 v1.6 S0 的跨期 ~54 GWh 缺供**不得用作新 S1 no-harm reference**；必须以同一新物理设定的 S0 解生成 SHA 和逐时逐母线保护参考。

## G3 S1 （两调用）
- 在 S0 科学+技术 pass 后运行；S1 speed hierarchy 与 cost stage 应同时持有相同服务优先级和 no-harm 约束。
- 交付量/延迟需要拆为 `(existing equipment, verified POI right, new direct upgrade, upstream network, electricity/resource adequacy, firm/conditional qualification, administrative process)` 的**多原因**诊断；不是不加区分归因给“POI 3 years”。
- 输出 S1-S0 的新增公共工程、公共工程被避免项、额外成本和电价成本，不将一个共同背景工程全价算 AIDC 诱发。

## G4 S2 S3 (A3 ≤30调用，已启动即计数)
- S2 开发商 cost 和 public electricity system consistency、备用、双重容量信用、Gas MDQ 与环境许可均通过；至少完成一个收敛或明确失败。
- S2 的 speed-first 锁定到成本末阶段；S3 使用社会真实资源成本与相同候选集合；不能将客户 CIAC 再加进社会目标。
- S3_mS2 严格匹配最终提供服务数量/时间，只有 matched service 科学验收通过才允许发布 S2-S3 效率差。
- 比较输出必须注明 `model_version, engine_data_hash, v17l_sha, legal_status, cost_basis, solver_ledger_id`。

## G5 财务/科学发布审查（0 solver）
- 跨期资产现金流严格守恒；先统计 `resource_cost`, `developer_cash_cost`, `other_ratepayer_net_cost`, `unallocated_fraction`，不把未知分摊硬凑成整额。
- 明确 `ratepayer burden` ≠ `public resource CAPEX`，公共/开发商之间的转移不会造成资源重复计数。固定解上变付款比例，真实资源成本必须严格不变。
- 旧/新物理设定不同则旧 S0/S1 不可直接用于 formal S1-S0；旧三年代理只做机制偏差诊断，不能做新版本正式对照。
- 不用单一工程代理带来更早交付的结果包装成 ERCOT 官方承诺 COD；这项研究面向机制，不是站点许可证预测。

## 预注册 STOP
- 任何基准SHA/数据源SHA不符、真实站点容量重复、Firm/Conditional重复、公共工程未知无足够证据却变已批准、成本不守恒 → STOP solver, continue static QA。
- 某阶段求解不可行/不最优、许可耗尽、科学S0 gate失败、S2物理/服务不收敛→ 不自动跳到非依赖结果、无重试，最大限度形成质量诊断和局部已验证结果。
- 用户若明确禁止进一步运行则立即停止本任务所有**尚未开始**的调用，不中断已开始的调用以免丢失封存证据（除非用户另有明确指令）。
