# S0_S1_EXECUTION_REPORT: S0 PASS, S1_EARLIEST PASS (2026-10-23 EDT)

| Item | Value |
|---|---|
| Code | `cdfdea06146a6fe73df89cb410d6a88cb5fda306` (merged mainline); A2 approval config-only commit on top; gate approved |
| Command (L2 main checkout `workflow/`) | `THREADS=10 bash byop/run/run_post_v16_a2.sh s0s1` |
| Output | `workflow/results/BYOP/post_v16_a2/POST_V16_A2_S0S1/` |
| Parent ledger `A2_SOLVE_LOG.csv` | `S0#1` DONE / ok / optimal / pass (2,355 s); `S1_EARLIEST#1` DONE / ok / optimal / pass (10,450 s) |
| Child ledger `A2_OPTIMIZER_CALL_LOG.csv` | `S0_COST` (2,660,074 × 7,107,710; 2,281 s); `S1_SPEED_HIERARCHY` (2,712,544 × 7,296,111; **12 objectives**; 7,433 s); `S1_COST` (2,712,538 × 7,296,112; 2,859 s). All DONE / ok / optimal. **3 top-level calls**, none extra or missing. |

## Acceptance

| Check | S0 | S1_EARLIEST |
|---|---|---|
| ok / optimal / 0 integers | ✓ | ✓ |
| Nodal balance residual (max) | 4.5e-6 MW | 8.2e-7 MW |
| 3 GW reserve, minimum slack | +9.0e-5 MW | +3.6e-6 MW |
| Reserve energy (start and end SOC), minimum slack | −1.9e-8 MWh | −5.9e-8 MWh |
| FIX-08 segment rows in the solved model | ✓ | ✓ |
| fwd = rev expansion (max \|diff\|) / free public links built | 0 / 0 MW | 0 / 0 MW |
| Child calls complete | ✓ | ✓ |
| No-harm: reference SHA, units, snapshots, D24 row = reference + 0.001 (3e-8) | — (writes the reference) | ✓ (max excess 0.0010000 MW; limit 0.002) |
| Lexicographic hierarchy optimal; speed levels hold in the cost stage | — | ✓ |
| Collector TECHNICAL_GATE (post-process) | PASS | PASS |

Results and interpretation: `S0_S1_MAINLINE_FINDINGS.md` and `S0_S1_MAINLINE_COMPARISON.csv`. The S0 existing-customer shed (54,206 MWh, 94 % in 2026, Far West) is flagged for review.
