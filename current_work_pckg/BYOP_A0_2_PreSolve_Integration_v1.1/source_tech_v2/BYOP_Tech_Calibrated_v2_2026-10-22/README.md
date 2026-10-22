# Researcher-completed BYOP technology evidence, parameters and code-implementation package

This package was generated 2026-10-22 for `simonyed/BYOP`, source commit `d0a9bf85523b9630a0a6e811ec024653cd26c5ec`.

Main deliverable: **EXECUTION_WORK_PACKAGE.md**. No optimizer runs, GitHub writes or external system changes were performed by the researcher assistant.

- `BYOP_TECH_PARAMETER_BASELINE_V2.json`: parameter source of truth. The researcher has chosen explicit executable values. All speculative ERCOT quotas/permit times are labeled proxies, never regulatory or procurement facts.
- `BYOP_TECH_PARAMETERS_V2.csv`: six technology numerical settings for direct coding.
- `BYOP_SUPPLY_POOL_PROXY_V2.csv`: annual finite procurement **research proxies** for RICE, aero, SOFC.
- `BYOP_COUNTY_OZONE_RULES_2026.csv`: TCEQ county-level ozone classifications from public status pages.
- `SOURCE_REGISTER.json`: source URLs and IDs.
- `PARAMETER_UNIT_CHECKS.json`: computed cost and CO2 spot checks.

Start after Epoch+PNNL multibus static gate, before the 2025 historical baseline recertification. The implementation work is explicitly non-solver and non-GitHub-changing until the executor commits; no formal S0–S3 run is authorized by this package.
