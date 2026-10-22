# DC_SITING_PNNL_DESIGN_NOTE: spreading 2026+ AIDC growth over more buses

- Date: 2026-10-22 (New York time)
- Branch: `mainline-v13-stageA`
- Status: **DESIGN – AWAITING RESEARCHER DECISION**. The model does not read the new files yet, and no solver was run.

## 1. Researcher request

1. The 2025 stock keeps using the Epoch AI data.
2. For new demand in 2026 and later, the yearly total stays the same, but it is spread over more buses.
3. Candidate buses come from three sources:
   - the buses where Epoch AI sites connect;
   - the buses near existing data centers in the PNNL IM3 atlas;
   - the buses near the new sites PNNL projects under `higher_growth`, in all five market-gravity scenarios.

## 2. Data and where it is stored

| Content | Location |
|---|---|
| Original PNNL data (two folders, moved from the Desktop, SHA-256 checked, `SHA256SUMS.txt`) | `work_pkgs/BYOP_ERCOT_DC_Siting_PNNL/raw/` (local only) |
| Preprocessing script and log | `work_pkgs/BYOP_ERCOT_DC_Siting_PNNL/build_pnnl_tamu_candidates.py` / `.log` |
| Atlas sites in Texas, each mapped to a bus | `workflow/byop/inputs/dc/PNNL_ATLAS_TX_SITES_TAMU64.csv` |
| Projected new sites in Texas, by market-gravity scenario, each mapped to a bus | `workflow/byop/inputs/dc/PNNL_PROJECTED_HIGHER_TX_TAMU64.csv` |
| Per-bus summary of all three sources | `workflow/byop/inputs/dc/PNNL_CANDIDATE_BUS_SUMMARY.csv` |
| Source, license and hashes | `workflow/byop/inputs/dc/PNNL_PROVENANCE.json` |

About the two PNNL datasets:

- **Atlas v2026.02.09** (existing data centers):
  - Derived from OpenStreetMap; license ODbL 1.0.
  - Gives centroid locations only, with no MW. Area in square feet is given for buildings and campuses.
- **Projected v1.1** (new data centers):
  - Model output of CERF-DC: new sites through 2035, 36 MW IT each, with no year of entry. License CC-BY-4.0.
  - Citation: Mongird et al. (2026), doi:10.57931/3020186.
  - `higher_growth` means data-center electricity demand grows 15 % per year from 2023, following EPRI (2024).

The mapping rule is the same one used for the Epoch sites:
1. A site is in ERCOT if its Census county is in ERCOT.
2. The site goes to the nearest ERCOT TAMU substation, and from there to that substation's 64s cluster bus.
3. If another cluster's substation is less than 2 km farther away, the site is flagged as a boundary tie.

## 3. Mapping results

| Item | Number |
|---|---|
| Atlas sites in Texas (one row per id) | 127, all in ERCOT |
| Projected Texas sites, summed over 5 scenarios | 1,350, of which 1,258 are in ERCOT. The 92 outside ERCOT are mostly in Jefferson / Orange (MISO) and Potter / Gray (SPP). |
| Buses with an Epoch site | 8 (the current mainline) |
| Buses with an atlas site | 21 |
| Buses with a projected site | 26 |
| **Union of all candidate buses** | **37**, or 36 after removing crypto-mining sites (see below) |

Two features of the data matter for the choice of weights:

- **Projected sites depend strongly on market gravity.**
  - At 0 % gravity (location cost only), sites spread over 20 buses, mostly in the West (p62) and the Coast (p67).
  - At 25–100 % gravity, about 9.7 GW falls on only 6 buses: DFW (p630 3, p630 10, p630 8), San Antonio (p650 0), Austin (p640 1), plus a small amount on p650 7.
  - Averaging the 5 gravity scenarios is therefore effectively weighted toward the 25–100 % case.
- **The four largest atlas sites by area are crypto miners**, not AI data centers:
  - Riot Corsicana (p630 0) and Riot Rockdale (p630 5);
  - MARA in Hood County (p630 12);
  - IONIC Cedarvale (p620 0).
  - I recommend dropping them from the candidate weights. The sensitivity cases can put them back.

## 4. Proposed allocation (to be confirmed)

### 4.1 What stays unchanged

- **2025 stock**:
  - The time-weighted 2025 average stays inside the background load.
  - The D11 inherited ramp of 460.73 MW IT stays on its 5 original Epoch buses in 2026.
  - The Epoch E0 equipment rows (`GREAL_POI_E0_SCHEDULE.csv`) stay as POI equipment on their original buses.
- **Totals**: each year's research increment stays at `ERCOT_DC_TOTALS − D11`, which is 4,567.9 MW IT in total for mid over 2026–2035. The low and high scenarios follow the same rule.

### 4.2 Spatial weights

The share of bus b is a weighted mix of three normalized shares:

`w_b = αE·E_b + αA·A_b + αP·P_b`

- `E_b`: the bus's share of the Epoch queue (late-2025 ramp plus increments after 2025).
- `A_b`: the bus's share of atlas site counts, crypto miners excluded. Site count is used because area is dominated by a few very large campuses.
- `P_b`: the bus's share of projected higher-growth IT MW, averaged over the 5 market-gravity scenarios.

Two further rules apply:
- **Threshold**: drop non-Epoch buses whose share is below 2 % (about 90 MW of new demand in mid by 2035), and renormalize. All 8 Epoch buses are always kept.
- **Timing**: in each year y, bus b gets `w_b × dT(y)`. The yearly sum therefore equals the approved total exactly.

Comparison for mid, 2026–2035 new research demand (MW IT):

| Bus | W1 equal thirds (1/3, 1/3, 1/3) | W2 Epoch-heavy (½, ¼, ¼) | W3 PNNL only (0, ½, ½) | Current (8 Epoch buses) |
|---|---:|---:|---:|---:|
| p650 0 San Antonio | 808 | 655 | 1,159 | 188 |
| p630 3 DFW | 791 | 590 | 1,244 | 0 |
| p610 2 Abilene | 578 | 861 | 0 | 1,568 |
| p630 4 Shackelford | 558 | 822 | 21 | 1,649 |
| p630 8 DFW | 321 | 239 | 504 | 0 |
| p630 10 DFW | 315 | 235 | 495 | 0 |
| p640 1 Austin | 284 | 212 | 447 | 0 |
| p630 2 Red Oak | 252 | 225 | 319 | 100 |
| p600 0 Helios | 206 | 306 | 0 | 622 |
| p630 9 Denton | 189 | 221 | 127 | 264 |
| p650 7 San Antonio | 100 | 0 | 157 | 0 |
| p630 6 Midlothian | 94 | 100 | 85 | 121 |
| p630 5 Temple | 71 | 102 | 8 | 56 |
| **Number of buses** | **13** | **12** | **13** | **8** |
| Share of the 3 largest buses | 48 % | 51 % | 64 % | 80 % |

**I recommend W1.** It keeps the real Epoch projects in the West at Abilene and Shackelford, and it puts the PNNL weight on load centers such as DFW, San Antonio and Austin. No single source dominates.

## 5. Effects on the model and the run (if approved)

1. **New buses (non-Epoch)**:
   - E0 = 0.
   - POI upgrade, procedure, PCLR, gas lateral (L2 PROXY) and onsite-renewable parameters use the same PROXY rules as the current aggregated POIs. No new values are invented.
   - Every such parameter is marked `PROXY (PNNL candidate bus)`.
2. **Code changes**:
   - `build_mainline_inputs.py`: allocate by the weights above, rewrite `MAINLINE_RESEARCH_COHORTS_TAMU64.csv`, and add the new buses to `GREAL_POI_ASSUMPTIONS.csv`.
   - The model code assumes 8 buses in several places (`NAMES`, the 48-key matched-service check, tests). These change to the actual number of buses, for example 13 × 6 = 78 keys.
3. **Larger model**: research buses go from 8 to about 13. The S2 developer LP and S1 offers grow with them, and the run time is expected to grow about 1.3–1.6 times. This is an estimate.
4. **B3-E results**: they become the "8 Epoch buses" comparison version. A new geography needs:
   - its own case-id;
   - a rebuilt pre-run manifest;
   - re-approval of the SHA by the researcher before it can run.

## 6. Decisions needed from the researcher

1. Weights: W1 / W2 / W3, or custom α values.
2. Should the 2 % threshold apply, with all Epoch buses always kept?
3. Should crypto miners be dropped from the atlas weights?
4. Should the `higher_growth` projection average all 5 market-gravity scenarios, or use one of them (for example 50 %)?
5. Interpretation of "existing stock allocated in proportion": I read it as keeping the 2025 stock at its Epoch buses, in proportion to Epoch. If you instead want the 2025 stock to be reallocated by the PNNL atlas, please say so. That would change the background load, because the TAMU baseline already contains the 2025 load.
