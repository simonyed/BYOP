# A2_MERGE_AND_REVALIDATION_REPORT (NEXT-05 v2 H2), 2026-10-23 EDT. 0 solver calls.

## Merge

| Item | Value |
|---|---|
| Target | `mainline-v13-stageA` after the A1 rerun approval (`4fc1bd7c`) |
| Source | `work/a2-postv16-static` @ `39a74ff5` (code `81bd5743`, FIX-01..09) |
| Merge commit | `8e4ad312` (local integration branch `integrate/next05`, fast-forwarded into mainline after A1 finished) |
| Conflicts | None. `test_post_v16_a0.py` auto-merged and contains both the A2 EOL helpers and the A1 prior-ledger fixture. |
| A1 fix preserved | `post_v16_a1.py`, `post_v16_gate.py`, `test_post_v16_a1_writer.py`, `config.byop_post_v16_a1.yaml` are byte-identical to the mainline versions (blob check) |
| Binary `.csv.gz` | `.gitattributes` exempts `*.gz` and similar from text conversion. The merged blob is `66069818…`; on the L2 checkout `gzip -t` passes and the raw SHA matches. |
| Same-named reports | `A2_PRE_RUN_MANIFEST.json`, `A2_GATE_VERDICT.json`, `A2_REGRESSION_SUMMARY.json` were identical on both sides; the manifest was **regenerated** on the merged code (below) |
| A1 approval closed | After rerun1 the A1 config fields went back to `NOT_APPROVED` / `null` (commit `cdfdea06`). The approval history stays in `e4bfbe7f` and the ledgers. |

## Revalidation on the unified L2 checkout (`/datasets/prgm/BYOP_impact/pypsa-usa/workflow`)

| Check | Result |
|---|---|
| Structural QA (S0 / S1_EARLIEST / S3 built, every solver call intercepted) | **75 / 75 PASS** (`results/BYOP/post_v16_a2_static/_structural_merged/`) |
| Full regression at `8a32d74c` | 244 passed / 4 failed. All 4 asserted that the A1 config was still unapproved; fixed by closing the A1 approval (no test change). |
| Full regression after closing (`81735e73`) | **248 passed / 0 failed** (`H2_REGRESSION_2.log`) |
| A2 manifest | Rebuilt on L2 at `8a32d74c`: 149 code + 110 inputs, 0 mismatches. The A1 config is not part of it, so closing A1 leaves it valid. |
| A2 gate | LOCKED: refused only on `run_authorization` / `approved_by` / `approved_git_sha` (S1 also needs a PASSED S0 and its reference) |
| Retained capabilities | 3 h `stores`; FIX-08 SOC segments; FIX-09 parent/child call ledger; 324 fwd/rev pairs; 1,818 priced, COD-masked public candidates; S0 ≡ S1 public inputs; strict no-harm reference. All re-checked by the 75 structural checks. |

## main

GitHub `main` (`be2c6904`) is an ancestor of the unified mainline, so it can be fast-forwarded. This happens after the A2 solve, so the run's code SHA, `main` and L2 agree. The temporary branches are kept for now.

**Approved code SHA for A2:** `cdfdea06146a6fe73df89cb410d6a88cb5fda306`. It contains the merged code, the closed A1 config and the rebuilt A2 manifest. Later commits change only results and reports.
