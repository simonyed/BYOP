# NEXT-09 v1.7L baseline adoption preparation: researcher instruction (verbatim, 2026-10-23 23:05 EDT, chat)

同意准备 NEXT-08b v3 候选基准的正式采纳方案。请保留原 v1.6 和全部诊断结果，使用独立版本冻结新有损 NetCDF 及 SHA，核对所有 S0/S1/A3 的基准引用与求解门禁。采纳后优先准备 S0/S1 成对重跑，不得沿用旧 S0 的缺供参照和 A3 manifest。本次仅授权采纳准备，不授权新的优化器调用。

## Executor reading (no new scope)

| Item | Reading |
|---|---|
| Authorised now | **Preparation only:** freeze the NEXT-08b v3 candidate (`f9aa87ae…`) as an independent baseline version (v1.7L); audit every S0 / S1 / A3 baseline reference and gate; prepare the adoption record and the paired S0 / S1 rerun on v1.7L. |
| Not authorised | Any optimizer call; setting the baseline to ADOPTED; any S0 / S1 / A3 / S2 / S3 run. These need a separate chat approval. |
| Kept unchanged | v1.6 (`baseline_2025_tamu_v16/`, every NetCDF, report and ledger), every NEXT-06 / 07 / 08 / 08b diagnostic and result, every earlier approval SHA. |
| Must not be reused | The old S0 lost-load / no-harm reference (`post_v16_a2/POST_V16_A2_S0S1/S0_NO_HARM_REFERENCE.csv`, solved on v1.6) and the old A3 manifest (`BYOP_NEXT_07/A3_PRE_RUN_MANIFEST.json`). |
