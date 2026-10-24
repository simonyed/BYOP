# 14 · Method limitations (NEXT-10U, model version `engineering_cost_v1`)

## 1. Spatial aggregation

- **Research buses, not projects.** The 16 research buses are aggregates of a synthetic / calibrated TAMU-64 backbone (v1.7L), not the real ERCOT node-breaker network. Each bus carries forecast research cohorts (Epoch + PNNL dynamic siting). They are not owner-matched campuses.
- **Equipment and rights are bus proxies.** Known equipment and approved rights (Helios, Abilene) are allocated to all cohorts of their bus (`LEGACY_BUS_AGGREGATION_PROXY`). A real right belongs to one owner and may serve fewer cohorts.
- **No shared substations.** Shared physical substations across buses are not identified: one group per bus, no cross-site sharing constraint.

## 2. POI capacity and rights evidence

- **Caps are not ratings.** Site caps are the research facility envelope (research IT × max PUE) or the approved right, not a utility rating of the remaining firm POI capacity.
- **Abilene (p610 2):** an approved right without observed equipment, so no known equipment. RIGHTED equipment is modelled from a 2026 commitment. If the real equipment was ordered earlier (Batch Zero requires long-lead equipment ordered before 2026-07-10 for base load energizing in 2028+), grid service there could be earlier than modelled.
- **Helios (p600 0):**
  - Phase I 200 MW (Q2 2026) and Phase II 391 MW (from Q2 2027) come from the Galaxy disclosure. Phase II MW is converted with Phase I's gross / IT ratio.
  - Phase III and the 830 MW unleased approval are a right only.
- **Operating-load proxies.** The Epoch operating rows (p630 6, p630 9, p650 0) are inherited operating-load proxies, not spare capacity.
- **Planned Epoch rows dropped.** Planned Epoch rows without interconnection evidence (Red Oak, Temple, Midlothian, Vantage, Denton expansions) are demand, not equipment. In the legacy model they were equipment with a 2028 floor.

## 3. Lead times and stage evidence

- **Transformer lead.** One industry range (NEMA 2026-10: 120–210 weeks for large power transformers) sets the equipment lead at the 13 sites without their own evidence. The base is the 165-week midpoint, so the COD is the commitment year + 3.16. These sites therefore share one generic path, and site-level heterogeneity in grid timing comes only from known equipment, rights, caps and disclosure. Mechanism identification across those 13 sites is limited.
  - Low and high leads (2.30 y / 4.02 y) are documented, not solved (no sensitivity runs in this package).
- **Procedural floor.** The Batch Zero 2028 floor never binds in the base case. The timing of later batches is unpublished.
- **Full-year firm rule.** Firm service needs a full year after COD. A COD of 2029.16 gives firm service only from 2030; energy in the COD year is not credited as firm.
- **Disclosure assumption.** Announcement = max(2026, request year − 3) (package research assumption). This limits early orders but is not a non-anticipative rolling controller: the LP still sees future prices.

## 4. Costs and payments

- **POI unit cost** is 160 USD/kW (research proxy, range 80–300), not a utility quote. It is classified as a direct interconnection facility (class A, developer CIAC). Whether a utility would treat parts of a new station as a system upgrade is not observed.
- **§25.194 amounts** are taken from the adopted rule (Texas Register 2026-10-02): 50,000 USD/MW security; SLLIA security = max(that, allocated system-upgrade cost); flat study fee (100,000 USD) with unused amount returned; 20 % of security returned at energization, the rest in 20 % milestone steps.
  - Not observed: the allocated system-upgrade cost per request, the milestone timing (one step per year assumed) and the T-bill interest on cash collateral (4 % assumed). These only affect the size of the security financing cost.
  - Applicability is per real single site ≥ 75 MW and cannot be verified at bus level.
- **Shared upstream and general public expansion (classes B, C)** is attributed economically (difference against the S0 of the same model version). Its legal payer stays `UNRESOLVED_LEGAL_ALLOCATOR`. The 12CP / minimum-billing / large-load tariff rules (25.193 / 25.252) are PROPOSED and are not applied.
- **Emissions** are not monetised in the resource book (reported in dispatch outputs only).
- **Background costs.** The committed background (DWB Stage 2, PBRP 765 kV) is identical in all scenarios, outside the objective. Its cost is reported, never attributed to the AIDC.

## 5. Model and solve

- **Snapshots.** 26 sample weeks (weeks 0 and 26 of the 2025 weather / load year), 3-hour snapshots plus B7 stress days, one frozen weather year. Sampling may understate rare scarcity. The S0 scientific gate is evaluated on the same sample.
- **LP structure.** Continuous LP only. The S2 developer stage is speed-first lexicographic (year by year), then private cost, with the S1 grid offer fixed ex ante. S2 – S3 differences are reported only for a converged S2_final and a matched-service S3_mS2.
- **Firm rule.** CONSERVATIVE_FIRM_SCREENING in A3: dedicated RE + BESS earn no full-year firm IT credit.
- **Thresholds.** The S0 scientific thresholds (1e-5 EENS share, 1e-3 peak-shed share) are research proxies, not ERCOT reliability standards.

## 6. Policy status (checked 2026-10-24)

- §25.194 is ADOPTED.
- §25.192 / 25.193 (12CP, minimum billing) and §25.252 are PROPOSED (Texas Register 2026-07-24).
- The FERC June 2026 show-cause orders are policy direction outside ERCOT.
