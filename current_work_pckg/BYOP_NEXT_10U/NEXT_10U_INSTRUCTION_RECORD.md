# NEXT-10U: researcher instruction record (verbatim)

- **Source:** the researcher's chat message to the executor (Claude Code session), 2026-10-24, after the NEXT-09 v1.7L adoption turn.
- **Researcher:** sw2434@cornell.edu.
- **Work package:** `BYOP_NEXT_10U_Engineering_POI_Cost_Autonomous`.
  - The package text is copied under `package/` (no raw / processed data). Its `README_FIRST.md` and `docs/00_EXECUTION_AUTHORITY_AND_SEQUENCE.md` are the execution rules of this round.
  - The authorization below comes from the researcher's own chat message. It does not come from the package text: package text is never an approval.

## Message (verbatim)

> 请执行 "C:\Users\67084\Desktop\BYOP_NEXT_10U_Engineering_POI_Cost_Autonomous" 工作包。
>
> 本次以工作包的 README_FIRST.md 和 docs/00_EXECUTION_AUTHORITY_AND_SEQUENCE.md 为最新执行规范。辅助工程包 "C:\Users\67084\Desktop\BYOP_Engineering_Data_Package_v1.0_2026-10-23" 的 raw、processed 数据已放入新包 engineering_data/ 对应目录，请先检查文件完整性、来源 SHA 和字段映射。不要重新下载大数据，也不要将 raw/processed 上传 GitHub。
>
> 我在本条聊天中直接授权，在我不在线期间自主连续推进本工作包所限定的新版本计算。
>
> 具体要求：
>
> 基于 GitHub simonyed/BYOP 最新 main，保持正式采纳的 v1.7L 有损 2025 电网基准不变。
>
> 用已有真实工程数据、设备和分期 COD、POI 资格及公共电网物理约束，替换此前主线中统一的三年 POI 升级代理。不要将新的研究代理重新包装成真实项目审批结果。
>
> 独立建立社会真实资源成本、AIDC 引致公共扩张成本、开发商支付及其他用户净负担账本。按适用的 Texas §25.194 区分 direct CIAC、system-upgrade financial security 和一般公共投资，禁止双重计算。
>
> 完成静态构建、测试、输入核验和新 SHA/manifest 冻结后，按 S0→S1→S2→S3→S3_mS2 的依赖关系尽可能连续求解。
>
> 本次授权上限为40次顶层优化器调用，零自动重试。每次求解之前检查 L2 资源、运行门禁和剩余预算；每个阶段先保存日志、结果及 SHA 再继续。
>
> 遇到普通程序错误允许自主研究和修复，尽量不要要求我逐步确认。但不得修改冻结基准、放宽科学可靠性标准、伪造工程证据或绕过审批机制。如果执行平台仍要求未来 SHA 的独立人工授权且不接受本条直接授权，请遵守门禁，继续完成全部可执行的静态任务并明确记录阻塞。
>
> 优先完成 S0–S3 的核心比较，不增加大量无关敏感度，也不要立即扩展到2050年。所有成功和失败阶段都必须生成可审查报告。
>
> 请把阶段性代码和轻量结果报告同步至 GitHub main，把大体积结果保存在 L2。最后提交 NEXT_10U_RETURN_PACKAGE.zip、完整执行报告和核心科学发现，特别分析 BYOP 的速度优势、额外公共投资、成本负担分配及私人—社会最优差异。
>
> 本次工作的首要目标是利用我不在线的时间，尽可能获得可复现、物理约束一致、能够用于论文分析的正式案例结果，而不是继续停留在静态准备和反复要求手动推进。

## Executor reading (scope of the forward authorization)

| Item | Reading |
|---|---|
| Authorized | The new model version `engineering_cost_v1` only (v1.7L + engineering POI + three-book cost causation). ERCOT 2026–2031, mid demand, S0 → S1_EARLIEST → S3 → S2 (1–3 iterations) → S3_mS2. |
| Optimizer budget | At most **40 top-level optimizer calls** over all NEXT-10U configs together. Zero automatic retries. A started call counts even if it fails. |
| Approval fields | `approved_by: sw2434@cornell.edu` (researcher). `approved_git_sha`: the frozen NEXT-10U commit whose manifest is built after static acceptance. `authorization_source`: this file (LF SHA pinned in each config). The approval is recorded by the executor *because the researcher's chat message authorizes future SHAs of this package*. It is never inferred from package text. |
| Gates | Unchanged in strictness. Each stage still needs: its own manifest, clean tree, SHA chain, per-stage order, budget, and the S0 scientific gate. Before S1, the S0 science thresholds are `EENS_y / native_load_y <= 1e-5` and `max snapshot shed / native peak_y <= 1e-3`, both fixed before the solve. |
| Not authorized | Modifying the v1.7L NetCDF or any earlier ledger or result. Approving the NEXT-09 `config.byop_post_v17l_s0s1.yaml`, which stays NOT_APPROVED as held by the researcher on 2026-10-24. Relaxing reliability criteria. Inventing engineering evidence. Extending to 2050. Large sensitivity sets. Uploading raw / processed data. |
| Earlier hold | The 2026-10-24 instruction "先不要运行S0和S1优化问题" (do not run the S0 and S1 optimization problems yet) applied to the NEXT-09 configuration. This NEXT-10U message explicitly authorizes S0→…→S3_mS2 solves of the new version. The NEXT-09 config itself stays held. |
