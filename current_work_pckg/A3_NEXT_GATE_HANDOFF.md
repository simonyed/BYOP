# A3_NEXT_GATE_HANDOFF (NEXT-03 W4): handoff only, `A3 = NOT_APPROVED`, 0 solver calls

Nothing for S2/S3 has been requested or run. This note says what the next request must contain. It builds on `A3_READINESS_HANDOFF.md` (NEXT-02).

## Preconditions

S0 and S1_EARLIEST must both be PASS and reviewed by you. If either fails, the next step is failure attribution plus a baseline-recovery proposal, not A3.

## Minimum checklist for the A3 request

1. **S2 Speed-First stays strictly lexicographic.**
   - First: maximise deliverable, qualified DC service and earliest COD. Then: minimise private cost at that speed. No large-weight penalty.
   - The supply modes (GRID_ONLY / GRID_FLEX / ISLANDED) stay separate from the N/R/C sourcing rights.
   - An empty R (reuse) pool stays empty.
   - The S2 developer LPs (`private_mode`, `developer_joint_build`) call linopy/Gurobi directly. Under the A2 lock these calls are refused as unplanned, so A3 needs its own call plan (parent / child kinds and budget) and instrumentation, in the A2-FIX-09 pattern.
2. **S3 and S2 share one physical feasible set:**
   - technology, gas, permit → COD, manufacturing pools and POI;
   - public assets (DWB/PBRP);
   - SOC segment neutrality (A2-FIX-08) and start/end reserve SOC;
   - the 3 GW reserve;
   - the no-harm rule.
   Objectives differ only between the private cash-flow view and the social resource-cost view. Both are booked separately.
3. **RE + BESS firm.** Certify 48 / 72 h continuous low-wind / low-solar stress on the same dispatch SOC, with a double-reservation check per resource.
   - The current main LP certificate covers 24 h B7 days only.
   - Uncertified dedicated RE/BESS gets no full-year firm credit.
   - **Note:** under segment neutrality a stress segment cannot borrow energy from other segments. A 48/72 h certificate therefore needs contiguous 48/72 h stress segments in the sample (a sampling change that needs your approval).
4. **Environment chain.** NOx / permit eligibility → permit on the critical path → real COD → delivered service. No made-up emission tax.
   - At all 16 buses the permit adds no delay under the L2 gas proxy.
   - The fast-gas ozone-county counterfactual is a mechanism check only.
5. **Comparisons.** S2−S1 and S2−S3 with matched service.
   - Long horizon: 2032–2035 adds AIDC; 2036–2050 has no new study demand (lock-in, reuse, utilisation).
   - This comes only after the four ERCOT scenarios close. No 2050 claims from 2026–2031.
