# C0_REPAIR_REPORT: C0 audit corrections (prompt v1.4, stage A)

- Date: 2026-10-22 (New York time)
- Branch: `mainline-v13-stageA`. Start SHA `53aa883c`; archive commit `d2cf7d1c`; stage A + C1 runner code commit `1a8912f4`.
- Solver runs in stage A: **0**.
- No model value was changed. All C0 v1.3 outputs are kept unchanged as a snapshot (`results/BYOP/C0_ANCHOR_2025/`, SHAs checked by test), and the v1.3 reports are archived in `_completed/ERCOT_2025_Official_Anchor_v1.3_C0/`.
- Code: new module `byop/build/c0_repair_v14.py`. It reuses the v1.3 functions without modifying them, so the v1.3 results can still be reproduced. Results are in `workflow/results/BYOP/C0_REPAIR_V14/`, with copies in this folder.

## A1. The mixed-park-and-phase bug: fix and real-data cases

**Cause.** In v1.3, `pipeline_suggestions()` worked at plant-group level. A group was flagged whenever its CDR side had any 2025 core MW and its model side had any committed MW. A historical phase already in the model fleet plus a separate future expansion phase was therefore treated as "the same asset sitting in the wrong ledger".

**Fix.**
- The plant-name group (county + fuel family + normalized name) is now **only the candidate search space**.
- Identity is decided at **phase** level:
  - CDR phase = units with the same in-service year and the same historical/future class. SWGR-UNA adjustment rows and DC ties are not phases.
  - Model phase = ReEDS units with the same StartYear.
  - Phases pair only when the years are within ±1 and the MW ratio is between 0.8 and 1.25. Pairing is one-to-one and greedy.
  - Old multi-unit plants, where ERCOT and EIA unit years differ, get an extra aggregate pass over the remaining historical phases. This pass can only mark history as "covered"; it never produces a reclassification.
- The five fields `identity_match`, `phase_match`, `historical_status`, `capacity_basis` and `reclass_action` are recorded separately.
- All raw identifiers are kept: UNIT NAME, UNIT CODE, INR, CDR source row, in-service date, EIA plant ID, ReEDS Unique ID and status.

**The three real-data cases** (`test_real_mixed_phase_parks_do_not_migrate_future_phase`):

| Park | CDR historical phase | Paired model phase | Action | Future phase |
|---|---|---|---|---|
| Callisto | 2024: 203.0 MW (CLO_BESS1/2, OPER) | active2025, 2024: 200 MW | `NONE_HISTORICAL_PHASE_COVERED` | Callisto II 203.2 MW (PLAN 2026); model committed 400 MW, ratio out of band, so `NONE_FUTURE_NOT_PAIRED`; **not migrated** |
| Tidwell Prairie | 2025: 204.0 MW (OPER) | active2025, 2025: 200 MW | `NONE_HISTORICAL_PHASE_COVERED` | 2026: 203.6 vs committed 200, `NONE_FUTURE_CONSISTENT` |
| Padua | 2025: 51.1 MW (OPER) | active2025, 2025: 50 MW | `NONE_HISTORICAL_PHASE_COVERED` | 2026: 352.3 (Unit 2/3 PLAN) vs model 2026: 350 (OP + TS), `NONE_FUTURE_CONSISTENT` |

### What the old 2,971.68 MW really is

In v1.4 this number is called "**the total flagged by the old park-level rule, still to be reviewed**". Broken down by phase:

| v1.4 action | MW | Meaning |
|---|---:|---|
| `NONE_HISTORICAL_PHASE_COVERED` | **458.1** | Callisto + Tidwell + Padua history, already in the model 2025 fleet |
| `STATUS_QUALIFIED_REVIEW` | **2,513.6** | The rest is **all OPER-SYN** (synchronized, not commercial), with in-service dates 2025-09 to 2025-12-31. The model has these units as ReEDS TS (construction complete, not commercial) with StartYear 2026, so **the two ledgers agree that they were not in commercial operation in 2025**. They are not confirmed omissions and **were not upgraded**. |

The old 2,971.68 MW contains **no** confirmed 2025 omission.

### Phase-level reclassification candidates (new, for researcher review; 3 phases, 567.5 MW)

| Park | CDR | Model (ReEDS) | Issue |
|---|---|---|---|
| Pyron wind (Nolan) | OPER, 2008, 263.4 MW | 249 MW, StartYear 2009, status **(OA) out of service, expected to return** | Missing from the model 2025 fleet, but the CDR lists it as commercially operating |
| Danish Fields Storage (Wharton) | OPER, 2025-04-30, 152.9 MW | 150 MW, status **(OP)**, StartYear **2026** | Excluded from both the 2025 fleet and the pipeline because StartYear is after 2025 |
| Myrtle Storage (Brazoria) | OPER, 2025-02-28, 151.2 MW | 150 MW, (OP), StartYear 2026 | Same as above |

Other statuses that need review (not changed):
- `STATUS_CONFLICT_REVIEW`: 7 phases, **1,638 MW**. The model has these in the 2025 fleet (StartYear 2025), while the CDR gives a 2026 date or a PLAN / OPER-SYN status. Examples:
  - Sequoia solar: model 401 MW, CDR PLAN 2026-11-21;
  - Fagus (private network, SLF): 332 MW;
  - Buzios 250, Big Star 200, La Casa 150, Gaia 153, Long Point 120 MW.
  - The model's 2025 fleet may include these too early.
- `MIXED_PHASE_REVIEW`: 21 phases, 5,687 MW. There is a name match but phases cannot be paired one-to-one, for example W A Parish coal units, T H Wharton, Los Vientos.
- `UNRESOLVED_CANDIDATE_IDENTITY`: 32.5 GW. Only capacity candidates, ambiguous matches or no match exist; no reclassification is proposed.

## A2. Switchable resources (`C0_SWITCHABLE_LEDGER.csv`, `C0_SWITCHABLE_UNIT_ROWS.csv`)

Method:
- Physical unit rows (SWGR-AVA) and unavailable-adjustment rows (SWGR-UNA, negative values) are paired by base UNIT CODE (the `_UNAVAIL` suffix is removed only to build the key; original codes are kept).
- Each adjustment row is deducted exactly once (tested).
- No adjustment row is left unpaired.

| Station | Physical units / MW | Unavailable adjustment MW | Snapshot net MW | Model 2025 summer MW | Model match |
|---|---|---:|---:|---:|---|
| **Tenaska Kiamichi** (CDR county Fannin; model Pittsburg County, OK) | 6 / **1,400** | **−885** | **515** | **1,224** | name match, other county |
| Tenaska Frontier | 4 / 955 | 0 | 955 | 860 | name match, same county |
| Tenaska Gateway | 4 / 937 | −937 | 0 | 826 | name match, same county |
| Elk Station | 3 / 606 | −606 | 0 | 0 | not in model |
| Antelope | 3 / 168.1 | −168.1 | 0 | 0 | not in model |

The 515 MW is only an audit net for this table. It is not a reliability certification, and the model's 1,224 MW is **not replaced**. Kiamichi's availability status is **pending a definition ruling by the researcher**. Tenaska Gateway (826 MW in the model, net 0 in the CDR snapshot) needs the same ruling.

## A3. Match confidence and the capacity difference (`C0_MATCH_CONFIDENCE.csv`, `C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv`, `C0_CAPACITY_BRIDGE_V14.csv`)

- **ID_CONFIRMED (via an ERCOT UNIT CODE ↔ EIA ID crosswalk) = 0 units / 0 MW.** No crosswalk is available, so every match below is a name candidate of decreasing strength. **The 81.0 % reported in v1.3 must not be read as unit-by-unit verified identity.**
- **CDR side**, denominator = CDR 2025 core including qualified statuses (1,187 units / 160,494.6 MW):

  | Tier | MW share |
  |---|---:|
  | Exact name, same county, phase paired | 51.9 % (83,248 MW) |
  | Exact name, historical aggregate paired | 6.6 % |
  | Fuzzy name, same county, phase paired | 11.8 % |
  | Name match in another county, phase paired | 2.3 % |
  | Name match but phase not paired | 7.3 % |
  | Capacity candidates | 7.7 % |
  | Ambiguous | 1.1 % |
  | Unmatched | 10.2 % |

  With "commercial only (OPER/RMR)" as the denominator, the shares are close; see the table.
- **Model side**, denominator = model active 2025, 155,050.6 MW summer:

  | Tier | MW share |
  |---|---:|
  | Name match with phase or aggregate pairing | 74.3 % |
  | Capacity candidates | 5.6 % |
  | Unpaired or unmatched | 20.1 % |

- **Capacity bridge**: the identity closes (arithmetic consistency only). It proves neither unit identity nor the cause of any difference.
  - v1.3's `rating_diff` is renamed `decomp_matched_group_capacity_diff`; it mixes rating-definition differences with phase-coverage differences.
  - `pipeline_cross` is renamed `decomp_park_level_pipeline_overlap`; it is a park-level overlap, not a reclassification finding.
- **The ~24.4 GW gap between the annual report and the CDR core stays unexplained.** No capacity was scaled up.
- **Model-active capacity without a paired CDR historical phase** (v1.3's group-level ~6.37 GW "model active, CDR non-core") is now tagged by phase. These are **items to review, not deletions**:

  | Tag | MW | Meaning |
  |---|---:|---|
  | `PHASE_UNPAIRED_WITH_CDR_HISTORICAL` | 13,245 | The group has CDR historical units but years or MW cannot be paired (unit split or rating basis) |
  | `SAME_NAME_FUTURE_RECORD_ONLY` | 2,304 | The same-named CDR record is only a future repower or expansion; the old model unit's identity is unresolved, and the future record **does not absorb** the old unit |
  | `DGR_SODG_DISTRIBUTION` | 49 | Distribution-level generators |

## A4. Tests and outputs

- `test_c0_repair_v14.py` passes **10/10** locally. It covers:
  - the three real cases, parametrized;
  - the breakdown of the old 2,971.68 MW;
  - retained identifiers;
  - separate handling of OPER-SYN, missing dates and future dates;
  - SWGR pairing with each deduction made once, Kiamichi 1,400 / −885 / 515 / 1,224;
  - no upgrade of confidence tiers, with ID_CONFIRMED = 0;
  - a future repower not absorbing the old unit;
  - each phase and each CDR source row counted once;
  - the v1.3 snapshot SHAs unchanged.
- The CDR source lists Coleto Creek and J K Spruce U2 under both COAL and GAS. These are coal-to-gas conversions (the gas rows are dated 2027 / 2028), so they are kept as future records, are not counted twice in 2025, and are tested.
- `test_c0_anchor.py` (v1.3, 13 cases) still passes. The legacy-geography and dynamic-geography regression tests run on L2; see the C1 report.
- Output files:
  - `C0_PHASE_RECONCILIATION.csv`
  - `C0_RECLASS_REVISED.csv` (the old suggestion set, phase by phase, plus the v1.4 candidates)
  - `C0_SWITCHABLE_LEDGER.csv` / `C0_SWITCHABLE_UNIT_ROWS.csv`
  - `C0_MATCH_CONFIDENCE.csv`
  - `C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv`
  - `C0_CAPACITY_BRIDGE_V14.csv`
  - `C0_REPAIR_BEFORE_AFTER.csv`
  - `C0_REPAIR_QA.json`
