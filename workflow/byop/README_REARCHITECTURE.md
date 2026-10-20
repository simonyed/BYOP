# BYOP ERCOT Rearchitecture v1.0 (2026-10-20) — run guide

Work package, decision log and reports: `current_work_pckg/` at the repository root (work package
`BYOP_ERCOT_Rearchitecture_Work_Package_v1.0_2026-10-20.md`). Parameter sources: `byop/inputs/poi/SOURCE_EVIDENCE_REGISTER.csv`.

The rearchitecture adds an electrical backbone, a POI deliverability layer and an S2 developer stage with an ex-ante
joint grid offer **on top of** the existing v2.4.0 LP (`v240_mech.py`) and the v2.5.0 TX-ERM aggregation
(`v250_mech.py`). Nothing of the 7-zone or county models is replaced; their configs and code paths are unchanged
(two backward-compatible edits: `scripts/prepare_network.py` WIND-01 falls back to the bus' reeds_zone factor when a
bus is not in the factor file; `v240_mech.ledgers` excludes the new `dc_curtail` carrier from operating cost).

## Environment (L2)

```bash
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate   # pypsa 1.3.0, linopy 0.9.1, gurobi 11
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
```

## Entry points

| Step | Command | Output |
|---|---|---|
| WP-A network | `snakemake -c 16 --configfile config/config.byop_ercot_tamu.yaml -- resources/BYOP_ERCOT_TAMU/networks/texas/elec_s_c64s_ec_lv1.0_REM-ERM-3h_E.nc` | `resources/BYOP_ERCOT_TAMU/` (log `logs/byop/rearch_tamu_build/`) |
| WP-A 2025 baseline | `python byop/build/build_2025_baseline_tamu.py --clusters 64s [--interface-rule reeds_sum\|tamu_raw\|pypsa_usa]` | `results/BYOP/baseline_2025_tamu/` (baseline nc, `NETWORK_MAPPING_AUDIT.csv`, `INTERFACE_AUDIT.csv`, `LINE_LEDGER.csv`, `BUS_LEDGER.csv`, `TAMU_2025_CALIBRATION_LP.csv`, audit json, `network_map.png`) |
| Unit tests (WP-C C6) | `bash byop/run/run_rearch.sh tests` | `results/BYOP/rearch/unit_tests.log` |
| ERM-02 B calibration | `bash byop/run/run_rearch.sh cal` | `results/BYOP/rearch/ERM_CAL_G{W,K}/erm02_calibration.json` |
| G1 (S0 on the backbone) | `bash byop/run/run_rearch.sh g1` | `results/BYOP/rearch/G1_S0_GW/` |
| G2/G3 matrix | `bash byop/run/run_rearch.sh matrix` | `results/BYOP/rearch/R1_G{W,K,U}/` |
| Sensitivities | `bash byop/run/run_rearch.sh sens` | `results/BYOP/rearch/R1_GU_*` |
| Collect | `python byop/post/collect_rearch.py results/BYOP/rearch` | `results/BYOP/rearch/_collected/` (POI_DELIVERABILITY_LEDGER, DELAY_ATTRIBUTION, ASSET_COMMITMENT_LEDGER, SCENARIO_COMPARISON, SCENARIO_DIFFERENCES, GATE_CHECKS, figures) |

## Model switches (`byop/model/rearch_mech.py`)

| Switch | Meaning |
|---|---|
| `--setting G-W / G-K / G-U` | weak (existing network) / constrained (+ equally sized competing queued load at each POI bus) / upgrade (+ corridor reinforcement, TPIT lead, + committed PBRP 765-kV paths) |
| `--attribution` | S1 delay attribution runs `S1_xPOI`, `S1_xUP`, `S1_xRA`, `S1_xPROC`, `S1_xALL` |
| `--case low/base/high` | POI equipment / upgrade / procedural / grid-project parameter case (register columns) |
| `--gas-case`, `--byop-case` | gas lateral and BYOP technology cases |
| `--s2-modes`, `--s2-iter` | enumerated supply modes (GO_F GO_C GF IS) and the offer-consistency iteration bound |
| `--pclr-hours`, `--pclr-max-consec-h` | conditional (PCLR-like) curtailment budget |

## Inputs (tracked)

`byop/inputs/poi/POI_REGISTER.csv` (sites, four deliverability layers, gas evidence),
`POI_REQUESTS.csv` (stylised identical request), `GRID_PROJECTS.csv` (PBRP 765 kV),
`SOURCE_EVIDENCE_REGISTER.csv` (SRC-xx). TAMU cluster buses are **synthetic**: they are not real substations, and no
model POI capacity is a certified ERCOT/TSP rating.
