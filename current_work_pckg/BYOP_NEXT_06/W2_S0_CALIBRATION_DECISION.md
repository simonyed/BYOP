# W2_S0_CALIBRATION_DECISION (NEXT-06), 2026-10-23

**W2 = `RERUN_AUTH_PENDING`. 0 new solver calls.** Original S0/S1 (`cdfdea06`) results and ledgers are unchanged.

## 1. Decision from W1

W1 found **no data, topology or COD error** to correct (classes D and C rejected or minor; `W1_S0_RELIABILITY_ROOT_CAUSE.md`). Under the package rules (§W2.1, priorities 1–2) **there is no evidence-based input fix**, so a formal S0/S1 rerun is **not** justified now.

What remains is an **UNRESOLVED** question with two parts:

| Part | What is unknown | Why it matters |
|---|---|---|
| T (magnitude) | Is the 2026 nightly Far West shortage real across the whole 2026 year? 94 % of the 54.2 GWh is two sampled weeks ×25.86. | It decides whether S0's 2026 reliability is a sampling extrapolation or a genuine baseline scarcity. |
| M (cause) | Which post-v1.6 rule lowers night-time deliverability into the p610 4 / p620 6 / p620 7 pocket relative to the v1.6 LP2 check? Candidates: 3 GW non-locational reserve with min-load coupling, segment SOC, 2026 fleet, DWB link. | It decides whether a method change is warranted (only with evidence of an implementation error; the reserve rule itself is a researcher decision). |

## 2. Proposed single diagnostic LP (package §W2.2 row 3: at most 1, separately approved)

| Item | Value |
|---|---|
| Question | 2026 annual existing-customer shed under the **unchanged A2 rules** when every 3 h snapshot of the year is solved (no sampling): answers T directly. The persisted flows, SOC and dispatch then let M be attributed read-only (which lines and units bind at night). |
| Model | S0, model year 2026 only, 2,920 × 3 h snapshots, weight 3 h (sum 8,760 h), stores 3 h, one SOC segment per year. Same code, inputs, reserve, committed assets and expansion rules. No 2026 candidate is reachable at the pocket anyway. |
| Not a replacement | This is a diagnostic only. It does not replace `POST_V16_A2_S0S1` or change S0/S1. |
| Config / gate | `workflow/config/config.byop_post_v16_n06_diag.yaml` (NOT_APPROVED). Own manifest `current_work_pckg/BYOP_NEXT_06/N06_DIAG_PRE_RUN_MANIFEST.json`; own ledgers in `results/BYOP/next06_s0_diag_fullyear_2026/`. **Budget 1 scenario attempt / 1 top-level call (S0_COST), 0 retries.** Run arguments pinned (`--start 2026 --end 2026 --sample-weeks 0 --scenarios S0`); the guard refuses any drift. |
| Command (L2 `workflow/`) | `bash byop/run/run_post_v16_a2.sh n06_gate`, then `THREADS=<T> bash byop/run/run_post_v16_a2.sh n06_diag` |
| Persisted before acceptance | `solution/S0/{storage_soc, storage_p_store, storage_p_dispatch, line_p0, link_p0, generator_p, bus_marginal_price}.csv.gz` + `SOC_SEGMENT_POSTSOLVE_AUDIT.csv` (new, tested) |
| Size / cost | About 21 × one S0 period: roughly 9–10 M variables, ~25 M constraints (estimate, not measured). Memory perhaps 80–150 GB of L2's 244 GB; barrier time likely several hours. No promise. |
| Cheaper alternative (if you prefer) | The same 2026 sampled weeks with the 3 GW reserve switched off (~0.45 M variables, minutes). It isolates only the reserve part of M, not T. |

**Authorisation needed (in chat):** approve the diagnostic at the code SHA I will name after the final sync (config-only commit of the three fields on `config.byop_post_v16_n06_diag.yaml`). The A2 approval (S0/S1) was closed after use and does not carry over.

## 3. What happens after the diagnostic (decision rules, fixed in advance)

| Diagnostic outcome | Verdict | Next |
|---|---|---|
| Full-year 2026 shed ≪ 51 GWh (e.g. < 5 GWh) and concentrated in few events | **T confirmed:** two-week sampling over-extrapolates the nightly pocket deficit. | Propose a pre-registered sampling or weight fix with representativeness evidence. That is a model change, so a new paired S0/S1 run with separate approval (2 attempts / 3 calls). |
| Full-year 2026 shed of similar magnitude, nightly, Far West pocket | **Physical scarcity under the A2 rules is real** for 2026 (`PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS`, if you accept the rules), or a method question (M) if the flows show the reserve coupling drives it. | Researcher decision on the reserve rule; no input change |
| Diagnostic infeasible / not optimal | Classified, no retry | Stop |

## 4. Cost-book clarification (package W2.4), original run

| PV 2026–2031 | S0 | S1_EARLIEST | S1 − S0 |
|---|---:|---:|---:|
| `social_real_resource_cost` (**includes** existing-customer VOLL shed loss) | 52,747.4 M$ | 54,460.4 M$ | +1,713.1 M$ |
| Existing-customer shed loss (`load_shed_PV`) | 1,931.3 M$ | 1,924.5 M$ | −6.8 M$ |
| **`physical_resource_spending_proxy` = social_real − load_shed_PV** | **50,816.0 M$** | **52,535.9 M$** | **+1,719.9 M$** |
| AIDC delay loss (in `social_total` only) | 0 | 1,609.5 M$ | +1,609.5 M$ |

- POI upgrade cost (26.4 M$) is already inside public capex; not added again.
- Committed DWB/PBRP costs stay in their separate ledger (2019 USD and 2024 USD proxies).
- The S1 − S0 resource difference is almost unaffected by the shed (−6.8 M$), because S1 inherits S0's shed by construction (no-harm).

## 5. Status

- `S0_RELIABILITY_VERDICT = BASELINE_RELIABILITY_UNRESOLVED` (`S0_SCIENTIFIC_STATUS.json`). This blocks A3 through the A3 gate prerequisite.
- `S1_S0_COMPARABILITY = ORIGINAL_ONLY`: the S1 − S0 differential is usable with the stated caveat; absolute S0 reliability is not.
