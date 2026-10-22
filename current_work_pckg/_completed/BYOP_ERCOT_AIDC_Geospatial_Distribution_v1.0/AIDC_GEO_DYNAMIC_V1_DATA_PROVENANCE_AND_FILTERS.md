# AIDC_GEO_DYNAMIC_V1_DATA_PROVENANCE_AND_FILTERS: data sources, mapping and filtering

- Date: 2026-10-22 (New York time)
- Scope: work package §2, §3.5, QA item GEO-06
- Solver runs: none. Everything here is deterministic data processing.

## 1. Data sources

| Dataset | Version / DOI / URL | License | Use |
|---|---|---|---|
| PNNL IM3 Open Source Data Center Atlas | v2026.02.09<br>DOI <https://doi.org/10.57931/3017294><br><https://data.msdlive.org/records/p147s-4h760> | ODbL 1.0 (derived from OpenStreetMap) | Locations of existing data centers. Gives no IT MW. We use the share of independent sites at each bus. |
| PNNL IM3 Projected US Data Center Locations | v1.1<br>DOI <https://doi.org/10.57931/3020186><br><https://data.msdlive.org/records/r0cga-34g05> | CC BY 4.0 | Site locations simulated by CERF-DC up to 2035, `higher_growth` scenario, 5 market-gravity variants. Each site is 36 MW IT and has no year of entry. Used only as a location prior. |
| Epoch AI Frontier Data Centers | 2026-10-21 (same as before; `EPOCH_TAMU64_PROVENANCE.json`) | CC BY 4.0 | 2025 stock, D11 ramp, verified/forecast ledger, E share |
| ERCOT research totals | `ERCOT_DC_TOTALS_2026_2035.csv` (unchanged) | Researcher input | The only anchor for annual totals |

Citation for the projected locations: Mongird, K., Burleyson, C., Akdemir, K. Z., Vernon, C., & Rice, J. (2026). *IM3 Projected US Data Center Locations (v1.1)*. MSD-LIVE. doi:10.57931/3020186.

Notes on the PNNL data:
- The five market-gravity scenarios are alternative simulation assumptions. They are not observations, and their weights are not probabilities.
- The data contain no grid capacity contracts, so they cannot support any inference about POI or firm rights.
- `weighted_siting_score` is an internal CERF scoring value. It is not used in any weight.
- The 15 % per year `higher_growth` rate is **not** applied to the ERCOT totals.

### 1.1 Where files are stored and how to reproduce them

| Content | Location |
|---|---|
| Original data: two folders, 26 files, `SHA256SUMS.txt` | `work_pkgs/BYOP_ERCOT_DC_Siting_PNNL/raw/`. Local only, not uploaded to GitHub, about 40 MB. Download from the two DOIs above, then check against `SHA256SUMS.txt`. |
| Preprocessing script, now in the repository | `workflow/byop/build/build_pnnl_tamu_candidates.py` |
| Processed outputs | `workflow/byop/inputs/dc/PNNL_ATLAS_TX_SITES_TAMU64.csv`, `PNNL_PROJECTED_HIGHER_TX_TAMU64.csv`, `PNNL_CANDIDATE_BUS_SUMMARY.csv`, `PNNL_SPATIAL_MAPPING_REVIEW.csv`, `PNNL_PROVENANCE.json` |

How to run the preprocessing script:
- With raw data: `--raw <directory>` rebuilds everything from the original files.
- Without `--raw`: the script only checks that the SHA-256 of the four tracked outputs matches `PNNL_PROVENANCE.json` (verify mode). L2 uses this mode and it passes.

Dependencies:
- geopandas 1.1.4 / pandas: only needed when rebuilding from raw.
- Census county boundaries `workflow/data/counties/cb_2020_us_county_500k.shp`: in the local and L2 `data/` directories, not in git.
- `results/BYOP/baseline_2025_tamu/NETWORK_MAPPING_AUDIT.csv` and `COUNTY_TO_BUS_SHARES.csv`: tracked in git.

## 2. Mapping rule (same as for Epoch sites)

1. ERCOT membership: the site's Census county lies in an ERCOT weather zone (according to `COUNTY_TO_BUS_SHARES.csv`).
2. Bus: the 64s cluster bus of the nearest ERCOT TAMU substation.
3. Checks:
   - `bus_alt` is the nearest substation that belongs to a different cluster. If it is less than 2 km farther away than the chosen one, the site is marked as a boundary tie.
   - `county_bus_consistent` says whether the chosen bus is one of the buses assigned to that county in the busmap.
   - A site more than 15 km from its nearest substation is marked as far from substation.
   - All flagged records go to `PNNL_SPATIAL_MAPPING_REVIEW.csv`.

| Source | Rows to review | Boundary tie | > 15 km | County/busmap inconsistent |
|---|---:|---:|---:|---:|
| PNNL Atlas | 17 | 16 | 1 | 0 |
| PNNL Projected (5 scenarios summed) | 171 | 154 | 5 | 28 |
| Epoch | 1 (Shackelford, already flagged in D12) | 1 | 0 | – |

- The 28 inconsistent records are all PNNL projected points that sit on county borders. The nearest-substation rule (the same one used for Epoch) is kept, and no record was moved by hand.
- None of these records leads to a non-ERCOT bus. All candidate buses are inside the ERCOT TAMU64 network (`check_ercot_buses`).
- Being mapped to a bus **does not mean** the site has a POI contract.

## 3. Counts

| Item | Count |
|---|---:|
| Atlas CSV rows in Texas (one id each) | 127, all in ERCOT. Layers: building 113, campus 10, point 4. |
| Explicit duplicates (a building or point lies inside another record's campus or building polygon, ≥ 50 % of its area) | 10 |
| Suspected same campus (same operator and ≤ 250 m apart) | 26, merged into one site cluster each and flagged. **Nothing was silently deleted.** |
| Site clusters (all / excluding crypto mining) | 99 / 95 |
| Crypto-mining records excluded (matched on both OSM id and name) | 4, see table below |
| Name-screen false positive | 1: "Texas Cryptologic Center" is the NSA facility in San Antonio, not a mine. Marked `CRYPTO_SCREEN_CLEARED` and kept. |
| Projected rows in Texas (5 scenarios summed) | 1,350. 1,258 are in ERCOT: g0 178/270; g25–g100 all 270/270. |
| Candidate buses (union) | **37**: 8 from Epoch, 21 from Atlas (17 excluding crypto), 26 from Projected |

The four excluded crypto-mining records:

| OSM id | Name | Bus | Basis |
|---|---|---|---|
| 01450422488 | Riot Corsiana | p630 0 | Riot Platforms Corsicana bitcoin mine |
| 01450418654 | Riot Rockdale | p630 5 | Riot Platforms Rockdale (Whinstone) bitcoin mine |
| 01301559332 | MARA Data Center | p630 12 | MARA, Granbury (Hood County) |
| 01455361421 | IONIC Digital Cedarvale | p620 0 | IONIC Digital, Ward County |

Only these records are dropped, not whole buses:
- p630 5 still has Epoch (Meta Temple) and Projected evidence.
- p630 0 and p620 0 still have Projected evidence.
- p630 12 is evidenced only by MARA, so it leaves the candidate set.

## 4. Three ways to count Atlas sites (input-side comparison only)

`results/BYOP/mainline/AIDC_GEO_DYNAMIC_V1_AUDIT/ATLAS_BASIS_SENSITIVITY.csv`

| Atlas counting basis | Eligible buses | Top-3 share, mid 2026–2035 |
|---|---:|---:|
| raw (crypto excluded, no deduplication) | 17 | 48.7 % |
| explicit_dedup (explicit duplicates removed) | 16 | 48.8 % |
| **noncrypto_clusters (main case)** | **16** | **48.3 %** |

- The work package expected "about 17" buses. That number matches the raw basis.
- The two bases differ only on **p630 7**. Its 3 raw Atlas records include an explicit duplicate. After merging they count as 2 independent sites, its q × total drops to 32.1 MW, below the 36 MW threshold, and the count becomes 16 buses.
- Among the excluded buses, p600 2 (projected sites only) is the closest to the threshold, at 34.2 MW.
- The basis is chosen by `atlas.count_basis` in the YAML. We did not change the threshold or the weights to reach 17.

## 5. Projected-site variants (input-side comparison only)

`.../P_VARIANT_SENSITIVITY.csv`. The main case is `P = 0.25·P(g0) + 0.75·P(g50)`. Each scenario is normalized within ERCOT before mixing.

| P variant | Eligible buses | Top-3 share, mid |
|---|---:|---:|
| **main (g0 25 %, g50 75 %)** | **16** | **48.3 %** |
| g0 only (location cost decides alone) | 24 | 43.8 % |
| g50 only | 15 | 49.2 % |
| equal-weight mean of the 5 scenarios | 16 | 48.6 % |

In ERCOT, g25–g100 put nearly identical sites on 6 DFW / San Antonio / Austin buses. The equal-weight mean is therefore effectively the g25–g100 result, which is why it was not chosen as the main case (§3.5.4).
