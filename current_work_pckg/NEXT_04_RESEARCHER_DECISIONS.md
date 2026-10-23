# NEXT_04_RESEARCHER_DECISIONS: recommended vs explicitly approved

As of 2026-10-22, 22:10 EDT, **no decision below has been explicitly approved by the researcher.** None of the recommendations authorises a run.

| Decision | Package recommendation | Researcher's explicit decision | Run authorisation? |
|---|---|---|---|
| **G1 / A1** | Approve LP-R → LP-N at `802c9d9414514641fd2b088b45ec7ea945be18a4`: at most 2 calls, 0 retries, logs kept on failure | **Not given** (`run_authorization: NOT_APPROVED`, `approved_by: null`) | Yes, once given (config-only commit) |
| **G2** | Review the A1 result; if A1 is BLOCKED, a written physical interpretation or exception before A2 | Not given (A1 has not run) | No |
| **D2: Bexar `p650 0`** | Keep gas evidence at L2; no MDQ or contract is assumed | Not given | No |
| **D4: storage** | Accept `stores` = 3 h, start/end reserve SOC, and FIX-08 energy-neutral segments (representative approximation, stated) | Not given | No |
| **D5: DWB/PBRP** | Common exogenous committed assets; absolute cost ledger outside the objective. DWB 371 M$ (2019 USD, SOURCED); PBRP 3,020 M$ per path (2024 USD, PROXY); unpaid shares are assumptions | Not given | No |
| **D6: no-harm** | S1 shed ≤ S0 shed per unit × snapshot + 0.001 MW; acceptance 0.002 MW; strict SHA, no fill | Not given | No |
| **G3 / D7 / A2** | After A1 review **and** merge plus revalidation on unified `main`: approve the **new merged SHA**; 2 scenario attempts / 3 top-level calls (S0_COST → S1_SPEED_HIERARCHY → S1_COST), 0 retries; explicit Gurobi call counting (no global monkey-patch claim) | **Not given**; not yet requestable (merge not started) | Yes, once given |
| A3 (S2/S3) | Handoff only | Not requested | — |

When you decide, the executor records your words verbatim here and in the config commit. `approved_by` is never filled in by the executor.
