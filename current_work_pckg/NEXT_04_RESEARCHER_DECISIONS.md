# NEXT_04_RESEARCHER_DECISIONS: recommended vs explicitly approved

As of 2026-10-22, 22:45 EDT, **only G1 / A1 has been explicitly approved by the researcher.** Everything else is still a recommendation; G1 does not extend to A2 or A3.

| Decision | Package recommendation | Researcher's explicit decision | Run authorisation? |
|---|---|---|---|
| **G1 / A1** | Approve LP-R → LP-N at `802c9d9414514641fd2b088b45ec7ea945be18a4`: at most 2 calls, 0 retries, logs kept on failure | **APPROVED, 2026-10-22 ~22:45 EDT.** Researcher's words: "I approve A1 (LP-R then LP-N, max 2 calls, 0 retries) at approved_git_sha 802c9d9414514641fd2b088b45ec7ea945be18a4". `approved_by` was given explicitly in reply to the executor's question: `sw2434@cornell.edu`. Config-only commit `f6dc3151fe9228f0d162829ee3df4224d1eeced1`. | Yes (A1 only) |
| **G2** | A1 ran: LP-R ok/optimal (λ objective 2,587.77 MW, **unaccepted**) but BLOCKED by a post-solve output-reader defect (`A1_EXECUTION_REPORT.md`). **Recommend Option 1:** fix the reader only (LP unchanged), with a new A1 approval and an explicit new budget for one LP-R + one LP-N. Alternatives: Option 2 (written exception: A1 BLOCKED-tooling, proceed to the A2 merge) or Option 3 (stop). | **Pending** | Option 1 needs a new config-only approval |
| **D2: Bexar `p650 0`** | Keep gas evidence at L2; no MDQ or contract is assumed | Not given | No |
| **D4: storage** | Accept `stores` = 3 h, start/end reserve SOC, and FIX-08 energy-neutral segments (representative approximation, stated) | Not given | No |
| **D5: DWB/PBRP** | Common exogenous committed assets; absolute cost ledger outside the objective. DWB 371 M$ (2019 USD, SOURCED); PBRP 3,020 M$ per path (2024 USD, PROXY); unpaid shares are assumptions | Not given | No |
| **D6: no-harm** | S1 shed ≤ S0 shed per unit × snapshot + 0.001 MW; acceptance 0.002 MW; strict SHA, no fill | Not given | No |
| **G3 / D7 / A2** | After A1 review **and** merge plus revalidation on unified `main`: approve the **new merged SHA**; 2 scenario attempts / 3 top-level calls (S0_COST → S1_SPEED_HIERARCHY → S1_COST), 0 retries; explicit Gurobi call counting (no global monkey-patch claim) | **Not given**; not yet requestable (merge not started) | Yes, once given |
| A3 (S2/S3) | Handoff only | Not requested | — |

When you decide, the executor records your words verbatim here and in the config commit. `approved_by` is never filled in by the executor.
