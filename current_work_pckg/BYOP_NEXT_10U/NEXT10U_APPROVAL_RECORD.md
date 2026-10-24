# NEXT-10U approval record (executor-recorded from the researcher's chat authorization)

| Item | Value |
|---|---|
| Authorization source | `NEXT_10U_INSTRUCTION_RECORD.md` (verbatim researcher chat message, 2026-10-24; LF SHA `d02c7fdf…`) |
| Scope authorized by the researcher | New model version `engineering_cost_v1`. S0 → S1 → S2 → S3 → S3_mS2. ≤ 40 top-level optimizer calls in total. 0 automatic retries. |
| Frozen code SHA (`approved_git_sha`) | `34a27ee6bb6e585c7b71c07571e133b48cd35807`. Code / config / inputs equal `47b5dd49`, where the S0/S1 manifest was built on L2. |
| Static acceptance at the freeze | Static build STATIC_PASS 29 / 29 (0 solver). Input rebuild check PASS. Full L2 suite 368 / 368. Manifest 156 code + 117 input files, 0 mismatches. |
| `approved_by` | `sw2434@cornell.edu` (the researcher). Recorded by the executor *only* because the researcher's own chat message authorizes future SHAs of this package. Package text never counts as an approval. |

## Stage 1: S0 / S1 (`config/config.byop_next10u_s0s1.yaml`)

- Approval commit: config-only (the three fields), approved_git_sha = the frozen SHA above.
- Budget: ≤ 3 top-level calls (S0_COST, S1_SPEED_HIERARCHY, S1_COST). 0 retries.
- S1 starts only after S0 passes **both** the technical acceptance and the S0 scientific gate. The gate is fixed before the solve:
  - EENS_y / native load_y ≤ 1e-5, in every year;
  - max snapshot shed_y / peak_y ≤ 1e-3, in every year.
- If the scientific gate fails, the run STOPs with no S1. The rest of the work turns to static root-cause analysis. Thresholds are never relaxed.

## Stage 2: A3 (`config/config.byop_next10u_a3.yaml`)

- Approved only after S0 / S1 pass. Before approval:
  - the reference SHAs (S0_RESULT.json, S1_EARLIEST_RESULT.json, S0_NO_HARM_REFERENCE.csv) are pinned in the config;
  - the A3 manifest is built.
- Then a config-only approval commit.
- Budget: ≤ 30 calls. Together with stage 1: ≤ 33 of the 40 authorized.
- Same thread count as stage 1, because the A3 re-solve of S0 / S1 must reproduce the stage-1 results.

## Not covered

- The NEXT-09 config `config.byop_post_v17l_s0s1.yaml` stays NOT_APPROVED (the researcher's hold of 2026-10-24).
- Its manifest is now stale by design, because NEXT-10U changed the code.
- No sensitivity runs. No 2032–2050 extension.
