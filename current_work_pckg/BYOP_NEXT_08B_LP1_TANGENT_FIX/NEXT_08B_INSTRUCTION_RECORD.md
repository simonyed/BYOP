# NEXT_08B_INSTRUCTION_RECORD (2026-10-23)

The researcher's instruction, given in chat after `LOSSY_LP1_RESULTS.md` (NEXT-08), recorded verbatim. It is pinned (LF SHA-256) as the authorisation source of `config.byop_lossy_lp1_v2.yaml`. It authorises preparation only: **no optimizer call**. Any solve needs an explicit chat approval naming the SHA and budget.

> 同意准备下一版 2025 有损 LP1 四切线修复，但暂不授权实际优化求解。
> 请先完成以下检查：
>
> 1. 将 LP1 的损耗近似改为四切线，LP2 和正式 S0–S3 继续保持两切线，确保整体仍是 LP。
> 2. 不要直接宣称四切线必然使 LP1 的损耗不小于 LP2。由于 LP1 切点由固定的 s_nom_max 决定，而 LP2 切点由候选网络实际容量决定，二者未必完全重合。
> 3. 使用已保存的 NEXT-08 候选网络，对所有线路构建不调用求解器的损耗函数比较：在相同电阻、相同潮流下，分别计算 LP1 四切线和 LP2 两切线的损耗包络，报告最大差异、可能仍低估的线路及代表性运行区间。重点检查 p610 1、p630 14 附近的瓶颈线路。
> 4. 若四切线仍存在不可忽略的低估，请提出一种与 LP2 两切线更严格一致、但仍保持 LP 的实现方式，例如采用固定参考容量设置相同切点，并在外层容量迭代中更新参考值。优先选择最少改动、可验证且不需要额外求解批次的实现。
> 5. 检查候选网络的 r_used 与 r_final 差异，避免把电阻迭代误差全部归因于损耗切线。
> 6. 原 NEXT-08 三次调用台账、候选 NetCDF、审批 SHA 和旧结果全部保持不变。新版本使用独立输出目录、manifest、代码 SHA 和求解预算。
> 7. 保持 G1–G3 扩容保护以及原 LP2 可靠性标准不变。先完成真实模型静态构建、损耗包络检查、回归测试和报告，再提交新的求解审批申请。
>
> 研究目标是消除 LP1 与 LP2 的损耗近似偏差，而不是通过不断增加切线、扩容或放宽可靠性标准来强行使校准通过。
> 请尽快完成这轮最小修复，避免引入新的敏感度分析，并将结果同步到 GitHub main。
