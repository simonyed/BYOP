# NEXT-09: v1.7L lossy 2025 baseline, adoption plan and paired S0 / S1 rerun (preparation only)

**Status: PREPARED. Not adopted, not approved. 0 optimizer calls in NEXT-09.**
- **Instruction:** `NEXT_09_ADOPTION_INSTRUCTION_RECORD.md` (verbatim, 2026-10-23 23:05 EDT).
- **Approvable code SHA:** `__APPROVABLE_SHA__` (GitHub `main` = L2 `byop`; the commit that adds the S0 / S1 manifest).

## 1. The frozen baseline v1.7L

| Item | Value |
|---|---|
| File (L2 only; `.nc` is not in git) | `workflow/results/BYOP/baseline_2025_tamu_v17_lossy/baseline_2025_tamu_v17_lossy_prepared.nc` |
| SHA-256 | `f9aa87aea496f7c07ea4aca0439a703e7eaa90d08cb66c5bc6f149ea60eeefb6`. A byte copy of the NEXT-08b v3 candidate; its SHA equals the v3 seal, the LP1-IT2 QA and the registry. |
| Provenance | Solved code `d4fd5340`, approval `2c2c64a2`, results `76b1ca3a`, seal `LOSSY_LP1_V3_SEAL.json` |
| Loss basis | `transmission_losses 2` in the calibration (LP1 v3 and LP2) **and** in the S0–S3 solve (the baseline meta). The loss-basis mismatch found in NEXT-07 W5 is closed. |
| Difference from v1.6 | Only `Line.s_nom` and `Line.r`, on 21 lines (+723.2 MVA in total; per line in `LINE_DIFF_VS_V16.csv`). `x` is unchanged. Every other component, every time series, the snapshots and the weightings are identical. The free-text meta label `baseline` is absent, and no code reads it. |
| Record | `BASELINE_V17L_RECORD.json` (verdict `FREEZE_PASS`; it also re-hashes v1.6, the NEXT-08 / 08b candidates and the v3 ledger: all unchanged) |
| Kept unchanged | `baseline_2025_tamu_v16/` (every NetCDF, report and ledger), every NEXT-06 / 07 / 08 / 08b result and diagnostic, every earlier approval SHA |

## 2. Adoption mechanism (registry) and gates

`workflow/config/config.byop_baseline_registry.yaml` is read by `byop/model/baseline_registry.py`.

**Current state.**
- The registry is `NOT_ADOPTED`, so the formal baseline is still v1.6.
- v1.6 is refused for formal S0–S3 by the loss-basis rule (calibrated lossless, solved lossy).
- So **no formal S0–S3 run is possible today**.

**Adoption.**
- You set `adoption_status: ADOPTED`, `adopted_git_sha` and `adopted_by` in a config-only commit.
- After that, v1.7L is the only formal baseline, and every v1.6-pinned post-v1.6 config is refused as *superseded*.
- An ADOPTED record with a missing field, an `adopted_git_sha` that is not an ancestor of HEAD, a changed instruction record, or a missing freeze record is a refusal. It never silently falls back to v1.6.

**Checks added (fail-closed; each fires before anything is built and again before every solve):**

| Gate | New checks |
|---|---|
| `rearch_mech.post_v16_guard`, `a3_guard` | The hard-coded v1.6 path and SHA are replaced by a registry check:<br>• the config pins the formal baseline;<br>• `--base` is that file, with those bytes;<br>• the loss-basis rule holds;<br>• the baseline meta `transmission_losses` equals the registry value. |
| `post_v16_a2_gate.check` (S0 / S1) | Same registry check, plus **S1 reference binding**: the S0 that S1 reads must be the S0 of this config's ledger, solved on this config's baseline SHA, with `S0_RESULT.json` written under this config. The manifest pins the registry's normalised SHA. |
| `post_v16_a3_gate.check` (A3) | Registry check. The **reference ledger must have been solved on the A3 config's baseline**, and the **A3 manifest must have been built for that baseline**. |
| Approved-SHA rule | A change to the registry after the approved SHA is tolerated only if it touches nothing but the three adoption fields (normalised SHA unchanged). Adoption and the S0 / S1 approval can therefore be one config-only commit. |

**Never reused (your instruction):**
- **The old S0 lost-load / no-harm reference** (`post_v16_a2/POST_V16_A2_S0S1/S0_NO_HARM_REFERENCE.csv`, solved on v1.6). S1 reads only the S0 of its own new out_dir, and the reference binding refuses an S0 from another baseline or config (tested).
- **The old A3 manifest** (`BYOP_NEXT_07/A3_PRE_RUN_MANIFEST.json`). It is voided by the "manifest of another baseline" rule and by code changes since. A v1.6 A3 config is superseded after adoption, and a v1.7L A3 config cannot use the v1.6 A2 results as its reference (tested).

The full inventory of every config, script and gate that names a 2025 baseline, with its state before and after adoption, is in `BASELINE_REFERENCE_AUDIT.csv`.

## 3. Paired S0 / S1 rerun on v1.7L

| Item | Value |
|---|---|
| Config | `workflow/config/config.byop_post_v17l_s0s1.yaml` (`NOT_APPROVED / null / null`). It equals the consumed A2 config except: baseline, mainline config, out_dir, manifest, authorization source, and the no-harm reference wording. Same stage rules, call plan, budgets and acceptance. |
| Mainline config | `config.byop_ercot_mainline_geo_dynamic_v1_baseline_v17l.yaml`. Equals the v1.6 one except `case_id`, `inputs.baseline` and the stage label. Siting, AIDC, POI, gas, costs and VOLL are unchanged. |
| Output / ledgers | `workflow/results/BYOP/post_v17l_s0s1/POST_V17L_S0S1/`, with a new `A2_SOLVE_LOG.csv` and `A2_OPTIMIZER_CALL_LOG.csv`. The v1.6 A2 directory is never touched. |
| Manifest | `V17L_S0S1_PRE_RUN_MANIFEST.json`, L2-built at the approvable SHA. |
| Run order | `S0` (1 call: `S0_COST`). Then `S1_EARLIEST`, only after S0 PASSED with its own no-harm reference (2 calls: `S1_SPEED_HIERARCHY`, `S1_COST`). |
| Budget | ≤ 2 scenario attempts, **≤ 3 top-level optimizer calls, 0 retries**. STOP on any non-optimal result or failed acceptance. |
| Command (L2, `workflow/`) | `THREADS=<B> bash byop/run/run_post_v16_a2.sh v17l_s0s1`, with B measured at launch. On v1.6, S0 took 39 min and S1 2 h 54 min (NEXT-05). |
| Not covered | A3, S2, S3, attribution, sensitivities, any rerun. |

**Expected effect (not a result).** v1.7L adds 723 MVA on the 21 calibration lines and carries their losses consistently. The v1.6 S0 shed 54.2 GWh, 94 % in the 2026 Far West pocket. In the NEXT-07 W5 lossless probe it fell to 647 MWh, once the solve matched v1.6's lossless calibration. The rerun will show what remains on a consistent *lossy* basis.

## 4. Static validation (L2, 0 optimizer calls)

__SWAP_SECTION__

## 5. A3 after S0 / S1 (not prepared now)

A3 stays BLOCKED. Once the v1.7L S0 / S1 pass, A3 needs a new config on v1.7L:
- its `reference` must be the SHA-pinned v1.7L S0 / S1 files;
- a new S0 scientific verdict on v1.7L, replacing NEXT-06's v1.6 `S0_SCIENTIFIC_STATUS.json`;
- a new manifest;
- its own approval.

The NEXT-07 developer-reserve review remains open for A3.

## 6. Approval (one config-only commit can carry both; the registry and the S0 / S1 config only)

> I adopt v1.7L (f9aa87ae) as the formal lossy 2025 baseline and approve the NEXT-09 paired S0/S1 rerun on it at approved_git_sha __APPROVABLE_SHA__: S0 then S1_EARLIEST; at most 3 optimizer calls; 0 retries; no A3/S2/S3; approved_by: <your identifier>.

You can also adopt now and approve S0 / S1 later: the S0 / S1 gate refuses until its own three fields are set.
