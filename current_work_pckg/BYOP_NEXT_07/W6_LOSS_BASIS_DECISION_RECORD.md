# W6_LOSS_BASIS_DECISION_RECORD (NEXT-07), 2026-10-23

The researcher's decision, given in chat after `W5P_LOSSLESS_VERDICT.md`, recorded verbatim. It is pinned (LF SHA-256) as the authorisation source of `config.byop_loss_basis_lp2.yaml`. It is **not** an approval of any optimizer call: every call still needs the three config fields set in a config-only commit, after an explicit chat approval naming the SHA and budget.

> 确认采用有损输电作为正式 S0–S3 的统一建模口径。
>
> 请首先核查关键线路的电阻、损耗近似及单位换算，并使用现有固定资产重新验证 2025 年有损 LP2。只有确认需要且具备工程依据时，才修正 v1.6 校准。
>
> 不得以消除所有切负荷为目标随意增加输电容量，也不要覆盖既有无损和有损诊断结果。
>
> 本次先授权静态核查、模型构建及校准方案设计；新增优化器调用需单独列明预算和审批。目标是在完成必要的基准一致性修复后，尽快成对重跑 S0/S1，并进入 S2/S3 主线。

## Recorded consequences

- **Loss basis:** S0–S3 use `transmission_losses: 2`, the mainline value, with PyPSA tangents.
- **Authorised now:** static checks, model builds and the calibration design. Every new optimizer call is listed separately with its budget and approval.
- **Capacity:** no transmission capacity is added to remove shed.
- **Existing results:** the lossless and lossy diagnostic results already produced are kept unchanged.
