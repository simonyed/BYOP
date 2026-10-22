# ENVIRONMENT_MECHANISM_LIMITATIONS: emissions → permit → COD → service (NEXT-01 A3-STATIC, zero solver calls)

**Code:** branch `work/a2-postv16-static`:
- `byop/model/byop_delivery_and_permit.py`: `cod`, `delivery_timeline`
- `byop/post/a3_static_mechanism.py`

**Outputs:**
- `PERMIT_GAS_EVIDENCE_PRIORITY.csv`
- `PERMIT_TO_COD_CAUSAL_AUDIT_VNEXT.csv`
- `PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv`

## 1. What the static evidence shows

- **Main evidence (128 rows: 16 research buses × technologies × permit paths, order year 2026):**
  - The permit-attributable COD delay is 0 in every row.
  - The shift of the first full Firm year caused by the permit is also 0 in every row.
  - Gas readiness binds on the 14 L2 buses (3-year proxy lateral). Gas or equipment / installation binds on the 2 L1 buses (1-year lateral).
  - These are **research proxies**. The result is not a Texas finding that low emissions are useless. It says that, with the present site / gas evidence and equipment lead times, **the permit is not on the critical path**.
- **The one hypothetical counterfactual** (separately labelled `HYPOTHETICAL_MECHANISM_DEMONSTRATION`; Bexar ozone county, reliable gas in 0.5 or 1 year; never a model input):
  - **RICE:** COD 2027.50 → **2027.75** because of the permit (+0.25 y). The first full Firm year is **2028 either way** (shift 0), so reliable service is unchanged; only the partial-year energy in 2027 falls from 0.50 to 0.25 of the year.
  - **OCGT_aero:** COD 2028.00 → **2028.25** (+0.25 y). The first full Firm year moves **2028 → 2029** (shift +1 year), so the permit costs a full year of reliable service.
  - **SOFC_NG:** COD 2027.00 either way, first full Firm year 2027. Its shorter research-proxy permit (0.60 y in an ozone county) is not critical.
  - **Reading:** under fast gas, the lower-emission technology's permit advantage matters through two links. First, the permit becomes the critical milestone. Second, the delay crosses a calendar-year boundary, which changes the first full-year Firm credit.

## 2. Partial-year delivery rule (`PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv`, 42/42 consistent)

- `first_energizable_time = COD_real`.
- Energy in year y = clip(y + 1 − COD_real, 0, 1) × 8760 h. This equals the model's `v240_mech.avail_frac` with fractional COD.
- Full-year Firm is granted only if the whole year is after COD (`firm_frac` with `firm_full_year`).
- `delivered_IT_MW_year_firm` counts only full years; `delivered_IT_MW_year_energy_equiv` reports the partial-year energy.
- Examples: COD 2027.50 and 2027.75 both give first full Firm year 2028; 2027.25 gives no 2027 Firm.

## 3. Gas-delivery evidence of the four ozone-county research buses (`PERMIT_GAS_EVIDENCE_PRIORITY.csv`)

| Bus | Site / county | Evidence found this round | Decision |
|---|---|---|---|
| p630 2 | Google Red Oak / Ellis 48139 | no on-site or firm gas found; Google's Texas power = renewable PPAs | KEEP L2 |
| p630 6 | Google Midlothian / Ellis 48139 | none; Google's gas project is in Armstrong County (Goodnight), not here | KEEP L2 |
| p630 9 | CoreWeave Denton / Denton 48121 | site next to the 225 MW Denton Energy Center; **proximity only**, not a supply right | KEEP L2 |
| p650 0 | Vantage TX1 / Microsoft SAT / Bexar 48029 | Vantage West-San-Antonio campuses report 405–423 MW behind-the-meter VoltaGrid gas generation under TCEQ minor-source permits, contested in a federal Clean Air Act suit (alleged source splitting); match to the Epoch site not verified; no public MDQ / firm contract | KEEP L2. **Researcher decision:** possible L1 if the campus is confirmed as the research site and a firm supply is documented |

- The p650 0 evidence is also a **permit-risk** fact. The minor-source route is contested, and a state pause of data-center permits was reported (date to verify). A permit path can therefore fail or stall, not just take a fixed time. The current model has fixed proxy leads only; this is stated, not modelled.

## 4. What is not modelled or is only a proxy

- **Permit leads:** these are the v2.0 research proxies (`RELATIVE_RISK_RESEARCH_PROXY_NOT_LEGAL_DETERMINATION`), not TCEQ review times. There is no continuous NOx → lead function, and CONTROLLED_ENV does not shorten the lead.
- **Preconstruction:** construction release = permit lead unless there is evidence of legal parallel construction (no such evidence here).
- **Electrical readiness:** 0.5-year proxy (package example).
- **Gas laterals:** L2 3 years / L1 1 year (repository POI table). Proximity to a gas plant or pipeline does not change the level.
- **Site FIPS:** 8 of 16 research buses have no real site FIPS (`UNKNOWN_CONSERVATIVE` = ozone-class lead).
- **No monetisation:** no environmental tax, emission cap or damage cost. CO₂ / NOx are a ledger and permit evidence only. Water and noise are qualitative, with no value filled in.
- **Not a paper result:** none of this is an optimisation result. The future A2 / A3 dynamic runs must show whether the mechanism changes S2 technology choice.

Sources (web, 2026-10-22):
- [TPR: groups threaten lawsuit](https://www.tpr.org/environment/2026-07-28/environmental-groups-threaten-lawsuit-over-west-side-san-antonio-data-centers)
- [DCD: Vantage / VoltaGrid lawsuit](https://www.datacenterdynamics.com/en/news/vantage-voltagrid-face-lawsuit-concerning-natural-gas-powered-off-grid-data-centers-in-san-antonio-texas/)
- [News4SA: groups sue](https://news4sanantonio.com/news/local/environmental-groups-sue-developers-of-two-sa-data-centers-over-air-pollution-permits)
- [Law360](https://www.law360.com/articles/2528350)
- [DCD: Google Red Oak](https://datacenterdynamics.com/en/news/google-announces-plans-for-red-oak-data-center-campus-in-texas)
- [Cleanview: Midlothian](https://www.cleanview.co/data-centers/texas/3698/midlothian---building-1)
- [TechCrunch 2026-03-17](https://techcrunch.com/2026/03/17/googles-data-center-power-playbook-comes-into-focus/)
- [DCD: CoreWeave Denton](https://www.datacenterdynamics.com/en/news/coreweave-deploys-16000-gpus-at-delayed-data-center-in-denton-texas/)
- [AI datacenters list (Denton Energy Center)](https://glennklockwood.com/garden/AI-datacenters)
