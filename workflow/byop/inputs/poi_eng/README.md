# Engineering POI inputs (model version `engineering_cost_v1`, NEXT-10U, 2026-10-24)

- **Built by:** `byop/build/build_engineering_poi_v1.py` (no solver, no download). It reads the verified engineering data package in `workflow/data/byop/engineering_v1/`.
  - That package is held locally and on L2, never in git.
  - Its files are byte-identical to the package `FILE_SHA256.csv` (65 / 65).
  - Each source SHA-256 is pinned in the builder and in `ENG_POI_SOURCE_REGISTER.csv`.
- **Selected by:** `mainline.poi_model: engineering_cost_v1` (`config/config.byop_ercot_mainline_engineering_cost_v1.yaml`). The legacy POI table (`../poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv`) and its E0 schedule are then not model inputs.
  - Only the legacy table's gas / PCLR / on-site RE columns are carried into `ENG_POI_SITES.csv`.
  - Its uniform 3 y lead, 2,000 MW per approval cohort and 2028 earliest grid COD are never read.

| File | Content |
|---|---|
| `ENG_POI_SITES.csv` | 16 research buses: approved right, known equipment, site cumulative cap, class caps, carried gas / PCLR / on-site RE fields, unit cost, base transformer lead |
| `ENG_POI_EQUIPMENT_KNOWN.csv` | Known equipment with its own COD. E0: Helios 200 MW @ 2026.5 (delivered lower bound); operating-load proxies at p630 6, p630 9, p650 0. E1: Helios I Phase II 391 MW @ 2027.5 (under construction, Galaxy Q2 2026). |
| `ENG_POI_CANDIDATES.csv` | U[site, class, commitment year]: RIGHTED (inside an approved right), NEW_REQUEST, LOCAL (disabled). COD, first full firm year, class cap, unit cost, evidence. |
| `ENG_POI_VISIBILITY.csv` | Disclosure cap per site and commitment year Q = announced facility envelope by Q − known equipment |
| `ENG_POI_LEAD_COMPONENTS.csv` | Lead components and their evidence |
| `ENG_POI_SOURCE_REGISTER.csv` | Source file SHA-256 |

## Rules (evidence class in brackets)

1. **Equipment ≠ right.** An approved capacity right (Helios 1,630 MW, Abilene 955.6 MW) only removes the study step. Equipment counts only with its own COD.
   - [APPROVAL_EVIDENCE]
   - Epoch "planned, no interconnection evidence" rows are demand, not equipment.
2. **COD = max over parallel components, never summed.**
   - Large power transformer: 120–210 weeks [INDUSTRY_REPORTED_RANGE, NEMA 2026-10]. Base = 165 weeks = 3.16 y (midpoint; executor choice, low / high reported, not solved).
   - Medium-voltage switchgear: 40–80 weeks, parallel and never binding.
   - New studied allocations (NEW_REQUEST) cannot energize before 2028.0 [ERCOT Batch Zero FAQ v8.1: the study covers 2028–2032]. This floor never binds in the base case.
   - Commitment in year q gives COD q + 3.16. The first full firm year is ceil(COD) (firm only in full years).
3. **Cumulative caps.**
   - Per class: RIGHTED = approved right − known equipment; NEW_REQUEST = the rest of the site cap.
   - Per site: site cumulative cap − known equipment.
   - The per-link upper bound equals the class cap. The `ENG-cum_*` rows stop it being repeated over commitment years.
4. **Disclosure.** sum over classes and q ≤ Q of U ≤ announced facility envelope by Q − known equipment. Announcement = max(2026, request year − 3), a package research assumption.
5. **LOCAL_POI_UPGRADE disabled (upper bound 0).** There is no site-specific spare-bay or reuse evidence. This is a policy, not an observation.
6. **Cost.** 160 USD/kW (GRID_DEPENDENT base; range 80–300) [RESEARCH_PROXY, not a utility quote], 40 y life.
   - This is a direct interconnection facility (asset class A). Under 16 TAC 25.194 it is paid by the large load as a non-refundable CIAC.
   - Its resource cost enters the public LPs once, at the social rate. The S2 developer pays it as a CIAC transfer.

## Not claimed

- No real remaining firm POI rating per site (the caps are demand envelopes or approved rights).
- No utility-approved COD.
- No owner-matched cohort allocation (LEGACY_BUS_AGGREGATION_PROXY).
- No shared-substation groups.
- No calibrated POI cost.

All gaps are listed in `current_work_pckg/BYOP_NEXT_10U/H1/EVIDENCE_GAPS.csv`.
