# AIDC_GEO_DYNAMIC_V1_LEGACY_VS_DYNAMIC_AUDIT: legacy 8-bus siting vs dynamic siting (input side)

- Date: 2026-10-22 (New York time)
- No solver was run. This file compares only the **input-side** research demand. It contains no LP results.
- Data:
  - `workflow/results/BYOP/mainline/AIDC_GEO_DYNAMIC_V1_AUDIT/LEGACY_VS_DYNAMIC_BY_BUS.csv`, `LEGACY_VS_DYNAMIC_SUMMARY.csv`, produced by `byop/post/geo_dynamic_v1_tables.py`;
  - `workflow/byop/inputs/dc/MAINLINE_SITING_WEIGHTS_GEO_DYNAMIC_V1.csv`: weights and allocation for every scenario × year × bus, 3 × 10 × 16 = 480 rows.

## 1. Overall comparison

| Scenario | Buses with growth: legacy → dynamic | Top-3 share: legacy → dynamic | Research addition 2026–2035 (MW IT) |
|---|---|---|---|
| low | 8 → 16 | 80.0 % → 50.5 % | 2,886.14 (both) |
| **mid** | **8 → 16** | **84.0 % → 48.3 %** | **4,567.903** (both) |
| high | 8 → 16 | 82.9 % → 47.0 % | 6,286.21 (both) |

- Legacy and dynamic totals differ only by the 4-decimal rounding error in the legacy file: −1.4e-4 MW for mid and low, −4.5e-5 MW for high.
- In the dynamic files every year equals `ERCOT_DC_TOTALS − D11` exactly (`ROUNDING_RECONCILIATION_GEO_DYNAMIC_V1.csv`).
- The work package's reference value for the top-3 share was "about 50 %" (§7.2). It was used only as a diagnostic, and no weight was tuned to hit it.

## 2. Bus by bus, mid scenario (MW IT of new research demand in that year; cumulative = total over the period)

| Bus | Type | 2026 legacy / dynamic | 2028 | 2031 | 2035 | Cumulative 2026–2031 | **Cumulative 2026–2035** |
|---|---|---|---|---|---|---|---|
| p610 2 Abilene | Epoch | 54.3 / 54.3 | 421.9 / 295.3 | 0 / 0 | 41.0 / 12.3 | 1,304.0 / 812.8 | **1,567.9 / 892.0** |
| p630 4 Shackelford | Epoch | 0 / 0 | 129.3 / 91.6 | 404.4 / 183.1 | 38.7 / 11.9 | 1,285.5 / 617.1 | **1,648.8 / 728.4** |
| p650 0 San Antonio (TX1/SAT14/SAT40) | Epoch | 5.2 / 5.2 | 50.0 / 83.6 | 0 / 61.9 | 5.0 / 19.8 | 156.0 / 417.4 | **188.3 / 587.6** |
| p630 3 (DFW) | PNNL new | 0 / 0 | 0 / 48.0 | 0 / 73.7 | 0 / 22.4 | 0 / 360.8 | **0 / 557.3** |
| p600 0 Helios | Epoch | 11.3 / 11.3 | 44.9 / 44.9 | 108.9 / 49.0 | 14.6 / 4.4 | 365.2 / 236.9 | **621.8 / 313.9** |
| p630 10 (DFW) | PNNL new | 0 / 0 | 0 / 19.5 | 0 / 34.6 | 0 / 11.3 | 0 / 164.3 | **0 / 263.1** |
| p630 9 Denton | Epoch | 16.7 / 16.7 | 72.5 / 75.1 | 0 / 4.6 | 7.7 / 3.4 | 215.0 / 230.6 | **264.3 / 254.7** |
| p630 8 (DFW) | PNNL new | 0 / 0 | 0 / 21.8 | 0 / 30.3 | 0 / 8.7 | 0 / 152.1 | **0 / 228.5** |
| p640 1 (Austin) | PNNL new | 0 / 0 | 0 / 19.1 | 0 / 24.4 | 0 / 6.7 | 0 / 125.1 | **0 / 183.5** |
| p630 2 Red Oak | Epoch | 6.6 / 6.6 | 26.2 / 33.8 | 0 / 16.2 | 3.5 / 4.8 | 77.0 / 143.6 | **99.5 / 183.0** |
| p670 1 (Coast) | PNNL new | 0 / 0 | 0 / 7.3 | 0 / 13.4 | 0 / 4.4 | 0 / 63.1 | **0 / 101.6** |
| p630 6 Midlothian | Epoch | 8.8 / 8.8 | 35.0 / 26.7 | 0 / 2.3 | 2.8 / 1.4 | 103.0 / 87.3 | **121.3 / 97.4** |
| p670 4 (Coast) | PNNL new | 0 / 0 | 0 / 5.6 | 0 / 7.6 | 0 / 2.2 | 0 / 38.4 | **0 / 57.4** |
| p670 0 (Coast) | PNNL new | 0 / 0 | 0 / 4.6 | 0 / 5.8 | 0 / 1.6 | 0 / 30.0 | **0 / 43.8** |
| p650 7 (San Antonio) | PNNL new | 0 / 0 | 0 / 4.8 | 0 / 5.2 | 0 / 1.3 | 0 / 27.8 | **0 / 38.8** |
| p630 5 Temple | Epoch | 2.2 / 2.2 | 8.8 / 6.8 | 0 / 1.2 | 4.7 / 1.8 | 26.0 / 24.5 | **55.9 / 36.9** |
| **Total** | | 105.22 / 105.22 | 788.63 / 788.63 | 513.38 / 513.38 | 118.00 / 118.00 | 3,531.7 / 3,531.7 | **4,567.90 / 4,567.90** |

The display name of a PNNL new bus only gives its approximate area. These buses are **candidate locations for research demand**, not existing campuses or approved projects.

## 3. What changes and what stays the same

- **2026 unchanged (GEO-03)**:
  - All 2026 research growth keeps the original Epoch layout. The only difference is −1.4e-4 MW at p610 2 from legacy rounding, which is logged.
  - In 2026 all 8 new buses are 0, and Shackelford stays 0.
- **2027 onward**:
  - Locked growth is the 387 MW IT already observed in operation at Denton, Helios, SAT14 and Vantage. It keeps its original bus and year.
  - In mid this is 222.07 MW in 2027 and 131.69 MW in 2028. The 33.24 MW of 2026 was already covered by the 2026 layout.
  - The forecast remainder is spread with the yearly weights α/β/γ (§3.3): 0.70/0.15/0.15 → 0.45/0.20/0.35 → 0.30/0.20/0.50.
- **Strongest effect**: forecast growth at the large western Epoch projects shrinks. Abilene, Shackelford and Helios fall from 3,838 MW to 1,934 MW for 2026–2035.
  - In the legacy siting this growth was **forecast**: Shackelford, the Crusoe expansion, Helios Phase II/III and Abilene buildings 5–8 all carry only TDLR or company estimated dates.
  - Under this package's rule they are not locked. If the researcher judges them sufficiently confirmed, they can be added to `locked_verified` in the YAML; the builder then keeps them at their original bus and year.
- **New buses**: the 8 PNNL new buses together receive **1,474 MW** (mid 2026–2035): DFW p630 3/8/10, San Antonio p650 7, Austin p640 1 and Coast p670 0/1/4. From 2027 they draw demand from the Atlas and Projected weights.
- **Epoch buses gaining demand**: three Epoch buses near load centres also grow, because Atlas sites are dense there: San Antonio p650 0 (+399 MW), Red Oak p630 2 (+83 MW) and Denton p630 9 (roughly flat).

## 4. Reading the result

- This change moves location only. Annual totals, D11, the 2025 stock and all historical files are unchanged (GEO-01/02, SHA-checked).
- Whatever is later observed in an LP comparison (delay, BYOP, public investment) has to separate the geography effect from the POI-proxy effect. All 8 new buses use E0 = 0 with an earliest COD of 2028 (`POI_PROXY_MAY_DRIVE_DELAY`), while their first forecast demand arrives in 2027. A 2027 delay at those buses would be caused by the proxy, not observed as an ERCOT refusal.
- Per §9, the next solve comparison should change one dimension at a time: old8 + old baseline → newgeo + old baseline → newgeo + new calibration.
