# A1_PREAPPROVAL_CHECK: P0 of BYOP-POST-V16-NEXT-01 (read-only, zero solver calls)

- Date: 2026-10-22 (New York time). Checked on L2 `/datasets/prgm/BYOP_impact/pypsa-usa/workflow`.
- Script: `current_work_pckg/a1_preapproval_check.py`. It sits outside the gate's code / config / input paths, so it does not change the approvable commit.
- Raw result: `A1_PREAPPROVAL_GATE.json`.
- **P0 status: `PASS_READY_FOR_A1_APPROVAL_REQUEST`. A1 is NOT approved and NOT run.**

| Item | Result |
|---|---|
| HEAD (local = GitHub = L2) | `802c9d9414514641fd2b088b45ec7ea945be18a4` = the package's verified HEAD |
| Uncommitted / untracked A1 code, config or inputs (CR-at-EOL ignored) | none / none |
| Authorization fields | `run_authorization: NOT_APPROVED`, `approved_git_sha: null`, `approved_by: null` |
| A1 manifest | `current_work_pckg/POST_V16_A1_PRE_RUN_MANIFEST.json` (SHA `d0f0b7f9…`): 5 code + 10 input SHAs, all match; normalised config SHA matches; baseline pin matches |
| v1.6 baseline on L2 | `a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16`, matches |
| TECH_COMP_2 sources | 4 SHA-pinned files verified (`verify_sources()` true) |
| A0.2 return package | `A0_2_RETURN_PACKAGE.zip` SHA `072f7437…`: 36 entries, zip test OK, contains `FILE_LIST_SHA256.txt`; A0.2 / A0.1 reports, readiness matrix and manifest readable |
| Call ledger `HEADROOM_SOLVE_LOG.csv` | **does not exist**: 0 STARTED / DONE / ERROR rows, 0 calls consumed |
| A1 gate LP-R | refused only for `run_authorization=NOT_APPROVED`, `approved_by missing`, `approved_git_sha missing` |
| A1 gate LP-N | the same, plus `needs a PASSED LP_R_H_RESOURCE first` |
| A2 / A3 | `NOT_APPROVED`; `rearch_mech.py --post-v16` still exits 3 |

## DRY re-check (`build()` = create_model only; `linopy.Model.solve` replaced by a refusal: 0 calls)

| | LP-R (H_resource) | LP-N (H_network) |
|---|---:|---:|
| Variables / constraints / integers | 373,249 / 967,980 / 0 | 373,249 / 967,980 / 0 |
| Buses / lines / snapshots / connected components | 63 / 162 / 432 / 1 | 63 / 162 / 432 / 1 |
| Objective only −λ | yes | yes |
| Hard zero-shed rows | 27,216 | 27,216 |
| Weights: buses / Σw | 16 / 1.0 | 16 / 1.0 |
| Σ line limit s_nom × s_max_pu (MVA) | 162,000,000 (1e6 per line) | 198,015.4 (v1.6) |
| Reserve / λ upper bound | 3,000 MW / 200,000 MW | 3,000 MW / 200,000 MW |
| Windows | 2025-08-17..19, 2025-02-19..21, 2025-07-29..31 (72 h each, B0 + BL) | same |

LP-R limits ≥ LP-N limits and both models have identical structure, as required for `H_network ≤ H_resource`.

## Interpretation boundaries carried into A1 (nothing changed to "make A1 feasible")

- **v1.6 shed:** the v1.6 fixed-asset LP2 residual shed (111.8 MWh/yr, 3 h, annual, VOLL-priced) uses a different basis from A1 (1 h windows, hard zero shed, 3 GW reserve). It neither implies that A1 is feasible nor that it is infeasible.
- **Inputs left untouched:** the windows, 2025 Native Load, the model-weather-year renewable profiles held 3 h, thermal availability (no MORA outages) and the reserve proxy.
- **Load overlap:** Native Load 2025 may already contain part of the 460.73 MW IT end-2025 inherited ramp. Native Load is not reduced.
- **Threads:** L2 load average was about 18 at check time (shared machine). If A1 is approved, the thread count is set from `uptime` at launch, not a fixed 20.

## Requested researcher decision (A1-APPROVAL)

If approved, the execution is:
1. **Approval commit:** a config-only commit changes exactly three fields in `workflow/config/config.byop_post_v16_a1.yaml`:
   - `run_authorization: APPROVED`
   - `approved_git_sha: 802c9d9414514641fd2b088b45ec7ea945be18a4`, or the SHA you name
   - `approved_by: <your identifier>`; the executor will not fill in your name
2. **LP-R:** `bash byop/run/run_post_v16.sh a1_lp_r`.
3. **LP-N:** `a1_lp_n`, only if `LP_R_H_RESOURCE_RESULT.json` has acceptance PASS and the ledger row is DONE / ok / optimal / pass.
4. **Budget:** at most 2 calls, 0 retries, then STOP and report.

The gate accepts an approved commit that is an ancestor of HEAD if nothing under code / config / inputs changed since, except the A1 config. The P0 report commit and the A2 / A3 static work (on a separate branch) do not change that.
