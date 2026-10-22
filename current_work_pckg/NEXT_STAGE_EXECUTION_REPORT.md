# NEXT_STAGE_EXECUTION_REPORT: BYOP-POST-V16-NEXT-01 (2026-10-22, New York time)

```text
REPO_AND_BRANCH: https://github.com/simonyed/BYOP  mainline-v13-stageA (A1 checkout, reports) + work/a2-postv16-static (A2 / A3 static code, separate branch, not merged)
START_GIT_SHA: 802c9d9414514641fd2b088b45ec7ea945be18a4
FINAL_GIT_SHA: mainline-v13-stageA = the commit containing this report (P0 report commit ac4eeeb8 before it); work/a2-postv16-static = ba73e600aa260b8f09ee9bd0d0084a98431c98d1
A0_2_ACCEPTANCE: PASS (A1_PREAPPROVAL_GATE.json: HEAD 802c9d94 clean for code / config / inputs; A1 manifest 5 code + 10 input SHAs and normalised config match; v1.6 .nc SHA matches on L2; TECH_COMP_2 sources verified; A0_2_RETURN_PACKAGE.zip 36 entries readable with file list; DRY LP-R / LP-N 373,249 vars / 967,980 cons / 0 integers, objective -lambda, 27,216 zero-shed rows, 16 weights sum 1, R limits >= N limits)
A1_RESEARCHER_AUTHORIZATION: NOT_APPROVED (no approver; no config commit)
A1_LP_R: NOT_RUN
A1_LP_N: NOT_RUN
A1_FINAL_STATUS: NOT_RUN
A1_SOLVER_CALLS_ACTUAL: 0
A1_CALL_LEDGER_SHA256: NO_LEDGER (HEADROOM_SOLVE_LOG.csv absent; 0 of 2 calls consumed)
V16_BASELINE_SHA256: a623fb6dd1bbcde444e089667f6e5a612ff5a8067f7afe5907ea218585747d16
H_RESOURCE_FACILITY_MW: NOT_AVAILABLE until accepted LP-R result
H_NETWORK_FACILITY_MW: NOT_AVAILABLE until accepted LP-N result
A2_STATIC_STATUS: PASS_STATIC (structural S0 / S1_EARLIEST / S3 40/40 PASS, 0 solver executions; 8 unit tests; branch regressions 202 passed / 2 EOL-artefact failures, see A2_STATIC_INTEGRATION_REPORT.md)
A2_SOLVER_CALLS_ACTUAL: 0
A3_STATIC_STATUS: PASS_STATIC (permit / gas evidence priority, causal audit vNext 128 main rows + 1 hypothetical block, partial-year QA 42/42)
A3_SOLVER_CALLS_ACTUAL: 0
POST_V16_ERM02_S0CAL: DISABLED
A2_A3_GATES: NOT_APPROVED (rearch_mech.py --post-v16 still exits 3)
OPEN_LIMITATIONS_AND_RESEARCHER_DECISIONS: (1) approve or not A1 at 802c9d94 (config-only commit: run_authorization / approved_git_sha / approved_by); (2) p650 0 Bexar gas evidence: Vantage campuses run ~405-423 MW behind-the-meter gas under contested TCEQ minor-source permits - keep L2 or reclassify (L1) once the site match and a firm supply are documented; (3) line-ending portability: A1 manifest / staging SHAs pin CRLF bytes of the main checkouts, a fresh LF clone fails them (content identical) - fix requires changing gated A1 code; (4) A2: 3 h -> 1 h reserve mapping, DWB Stage 2 / PBRP sunk treatment, no-harm reference vs hard zero, A2 manifest + gate + budget before removing exit 3; (5) RE / BESS certificate limited to 24 h B7 stress days in the main LP, single weather year; (6) 8/16 sites UNKNOWN_CONSERVATIVE; permit leads, supply pools, electrical readiness remain research proxies; (7) L2 shared load ~18 at check time - A1 threads chosen at launch from uptime
```

## 1. P0 (W0): A0.2 acceptance and frozen A1 inputs

`A1_PREAPPROVAL_CHECK.md` gives the full table; the raw result is `A1_PREAPPROVAL_GATE.json`. The check script is `current_work_pckg/a1_preapproval_check.py`; it is placed outside the gated paths so that the approvable commit stays `802c9d94`.

- **Verdict:** P0 passes. The gate refuses only on the three approval fields, and for LP-N additionally because LP-R has not passed.
- **Kept as is:** the windows, Native Load 2025, the model-weather-year renewable profiles, thermal availability (no MORA outages) and the reserve proxy.
- **Interpretation boundaries in the record:**
  - the 460.73 MW IT inherited ramp may overlap Native Load 2025;
  - the v1.6 111.8 MWh/yr 3 h shed uses a different basis from A1.

## 2. A1 (W1): not authorised, not run

`A1_EXECUTION_REPORT.md` = NOT_RUN. No headroom number exists.

## 3. A2-STATIC (W2), on branch `work/a2-postv16-static`

Details in `A2_STATIC_INTEGRATION_REPORT.md` and `A2_READINESS_MATRIX.csv`.

- **Reserve:** the 3 GW / 1 h operating reserve is in the multi-period LP, covering existing and public-candidate thermal and grid storage on the dispatch SOC.
- **Legacy ERM:** off on the post-v1.6 path only.
- **Public expansion:** priced (1,818 rows, 0 free, 0 S0CAL). The 6 committed DWB / PBRP links are sunk common assets.
- **S0 vs S1:** identical public assets.
- **S1 POI:** phased per site.
- **RE + BESS firm certificate:** 96 rows in `serve_cap` on the dispatch SOC.
- **S3:** TECH_COMP_2 candidates with COD audit and supply-pool rows.
- **Structural checks:** 40/40, with no solver executed.
- **Solving:** formal solving stays refused (exit 3).

## 4. A3-STATIC (W3)

Details in `ENVIRONMENT_MECHANISM_LIMITATIONS.md`, `PERMIT_GAS_EVIDENCE_PRIORITY.csv`, `PERMIT_TO_COD_CAUSAL_AUDIT_VNEXT.csv` and `PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv`.

- **Main evidence:** the permit-attributable COD delay is 0 and the shift of the first full Firm year is 0 at all 16 buses.
- **Hypothetical** (Bexar ozone county + fast reliable gas, labelled and separated):
  - aero: +0.25 y COD **and** +1 Firm year;
  - RICE: +0.25 y COD, Firm year unchanged;
  - SOFC: no permit effect.
- **Partial years:** the delivery rule equals the model rule (energy counted, no full-year Firm credit).
- **Ozone-county gas evidence:** all four buses keep L2. p650 0 is flagged for your decision.

## 5. Deliverables

All in `current_work_pckg/`; SHA-256 values are in `FILE_LIST_SHA256.txt` inside the zip.

| File | Status |
|---|---|
| `NEXT_STAGE_EXECUTION_REPORT.md` | this file |
| `A1_PREAPPROVAL_CHECK.md`, `A1_PREAPPROVAL_GATE.json`, `a1_preapproval_check.py` | P0 PASS |
| `A1_EXECUTION_REPORT.md` | NOT_RUN |
| `A2_STATIC_INTEGRATION_REPORT.md`, `A2_READINESS_MATRIX.csv` | PASS_STATIC |
| `PERMIT_GAS_EVIDENCE_PRIORITY.csv`, `PERMIT_TO_COD_CAUSAL_AUDIT_VNEXT.csv`, `PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv`, `ENVIRONMENT_MECHANISM_LIMITATIONS.md` | PASS_STATIC |
| `NEXT_STAGE_RETURN_PACKAGE.zip` | SHA manifest, the git diff 802c9d94..ba73e600 (branch code), static logs; no solve logs (none exist) |
