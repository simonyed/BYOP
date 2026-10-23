# OVERNIGHT_AUTHORIZATION_RECORD (BYOP NEXT-05 v2)

**Researcher's approval in chat (2026-10-22/23, verbatim; the message arrived truncated):**

> "I approve unattended execution per NEXT-05 v2: A1 rerun1 at 07c881a4c643a800dfc55257716671e2791a48ab (<=1 LP-R + <=1 LP-N, 0 retries); then, if its gates pass, merge A2 and run S0 + S1_EARLIEST on the revalidated merged SHA (<=2 attempts / <=3 top-level calls, 0 retries); then the A3 pilot (<=30 cal"

**Notes:**
- An earlier attempt to record this approval from the package text alone was refused by the permission system; nothing was changed then.
- `approved_by: sw2434@cornell.edu` is the identifier the researcher stated explicitly in chat for A1 (NEXT-04).
- The A3 clause is truncated. It is applied with the package's own conditions: at most 30 top-level calls, 0 retries, only if S0 and S1 both PASS and an independent A3 gate / ledger exists.
- The executor (Claude) makes the config-only commits on this approval. Each stage still needs its own gate PASS.

| Stage | Approved code SHA | Scope / budget | Config-only commit | Status |
|---|---|---|---|---|
| A1 historical (NEXT-04) | `802c9d94…` | LP-R → LP-N | `f6dc3151` | LP_R_H_RESOURCE#1: solver ok/optimal, **output_failed / pass=False**, consumed 1 (kept unchanged) |
| A1 rerun1 | `07c881a4c643a800dfc55257716671e2791a48ab` | ≤ 1 LP-R + ≤ 1 LP-N, 0 retries (historical total ≤ 3) | `e4bfbe7f` (closed in `cdfdea06`) | done: LP-R PASS, LP-N infeasible (network side) → G2 A1_FIXED_NETWORK_EXCEPTION |
| A2 S0/S1 | `cdfdea06146a6fe73df89cb410d6a88cb5fda306` (merged, revalidated: 248/0, 75/75) | ≤ 2 attempts / ≤ 3 top-level calls, 0 retries | see git log | in progress |
| A3 pilot | — | ≤ 30 top-level calls, conditional | — | pending |
