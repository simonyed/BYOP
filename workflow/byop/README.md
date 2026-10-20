# BYOP project code inside PyPSA-USA

Data-center "Bring Your Own Power" (BYOP) mechanism models for ERCOT, built on this PyPSA-USA checkout
(upstream `20b71907` + RAMP-01 / WIND-01 patches, branch `byop`, GitHub `simonyed/BYOP`).

Rule (2026-10-20): every program that is executed lives here; work packages (guidance documents, preprocessing and
data-collection scripts, their own logs) stay local in `D:\BYOP_impact\work_pkgs`. L2 runs only this folder.

## Layout

| Path | Content | git |
|---|---|---|
| `byop/model/` | `v250_mech.py` (ERCOT county GCE + gas gate + S2-SF, current), `v240_mech.py` (static S0–S3 LP), `v240_path.py` (annual controller), `wp2_ercot_s0_s1.py` / `wp2_ercot_s1_real.py` (ERM-DC constraint, solve wrapper, DC task model), `byop_paths.py` (all locations) | tracked |
| `byop/build/` | `build_2025_baseline_county.py`, `calibrate_itl_lp.py`, `county_deliverability_diag.py`, `county_audits.py` | tracked |
| `byop/post/` | `collect_p1.py` | tracked |
| `byop/run/` | L2 run scripts: `run_rebuild_v6.sh`, `run_p1.sh`, `run_p1b.sh`, `run_ctrl7.sh` | tracked |
| `byop/inputs/` | runtime inputs = key parameters (TECH-01, PUE, task mix, inference trace, cohorts, AEO2023 growth, TPIT map); provenance in `inputs/README.md` | tracked |
| `config/config.byop_*.yaml`, `config/byop_*.csv` | Snakemake configs (7-zone legacy, ERCOT county) and WIND-01 factors | tracked (`.gitignore` rule) |
| `data/byop/` | raw public data for the builders (ReEDS eb75a6bc inputs, ERCOT Native Load 2025) | ignored |
| `results/BYOP/` | baselines (`baseline_2025_7zone`, `baseline_2025_county`), calibrations, case outputs (`p1`, `p1_ctrl7`, ...) incl. per-case logs | ignored (small files synced L2 → local) |
| `logs/byop/` | PyPSA-USA build/solve logs of the BYOP networks (7s/8s, county) | ignored (synced) |

## Running (L2, from `pypsa-usa/workflow`)

```bash
source /datasets/cds/env.sh; source /datasets/prgm/pypsa-usa/.venv/bin/activate
cd /datasets/prgm/BYOP_impact/pypsa-usa/workflow
snakemake -c 16 --configfile config/config.byop_ercot_county.yaml -- resources/BYOP_ERCOT_County/networks/texas/elec_s_c192s_ec_lv1.0_REM-ERM-3h_E.nc
bash byop/run/run_rebuild_v6.sh        # county baseline -> ITL calibration -> ERM calibration -> P1 -> P1b
python byop/model/v250_mech.py --grid G-R --case-id X --out results/BYOP/X --erm-cal results/BYOP/p1/ERM_CAL/erm02_calibration.json ...
python byop/post/collect_p1.py results/BYOP/p1
```

Model decisions and results are documented in the local work package
`work_pkgs/BYOP_ERCOT_County_v2.5.0` (`decisions/DECISION_LOG.md`, `docs/`).
