#!/usr/bin/env python3
"""C0 tasks B-D (ERCOT 2025 official anchor v1.3, 2026-10-22): offline reconciliation of the 2025 model state with the
supplied official ERCOT evidence. Audit only: the model inputs and numbers are NOT changed; no optimizer is called (the
optional baseline-network read uses pypsa.Network only, never optimize / linopy).
    python byop/build/c0_anchor_audit.py [--check-nc]        (run c0_anchor_evidence.py first)

B  C0_GENERATOR_MATCH.csv      ReEDS generator DB (the model fleet source) <-> CDR Dec-2025 Unit Details: name-normalised plant
                               groups matched inside county + fuel family (exact key, then token similarity, one model group per
                               CDR group at most); MATCH_EXACT / MATCH_FUZZY / MATCH_FUZZY_OTHER_COUNTY / AMBIGUOUS / UNMATCHED / MODEL_ONLY
   C0_CAPACITY_BRIDGE.csv      per family and annual-report category: AR installed vs Dec trend operational vs CDR 2025 core vs
                               model summer MW, with an exact decomposition of CDR core - model (rating difference on matched groups,
                               cross-ledger pipeline, unmatched both sides) and the publication / snapshot residual left UNEXPLAINED
   C0_PIPELINE_RECLASS_SUGGESTIONS.csv  model committed (StartYear >= 2026) groups that the CDR lists operating by 2025 (and the
                               reverse); suggestions only, nothing applied
B5 C0_HISTORICAL_AIDC_EVIDENCE.csv  2025 Epoch AIDC stock / end-2025 / inherited ramp per site with evidence class (WP §4); values kept
C  C0_LOAD_ACCOUNTING.csv      1 h / 3 h time axis checks and every 2025 / 2026+ demand component with its code location
D  C0_UPLIFT_LEDGER.csv        per line: raw synthetic, interface rule, 2025 calibration uplift (MVA), final s_nom, later S0CAL (MW Links)
   C0_QA.json                  all checks (+ solver_executions = 0)
"""
from __future__ import annotations

import argparse, hashlib, json, re, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
import byop_paths as BP  # noqa: E402

DER, OUT = BP.ANCHOR2025_DERIVED, BP.C0_RESULTS
WP = BP.WORKFLOW.parent / 'current_work_pckg'
CUTOFF = pd.Timestamp('2025-12-31')
# identical to build_2025_baseline_tamu.TECH_MAP (asserted in the tests; that module imports pypsa, so it is not imported here)
TECH_MAP = {'gas-cc': 'CCGT', 'gas-ct': 'OCGT', 'o-g-s': 'gas_steam', 'coaloldscr': 'coal', 'coal-new': 'coal',
            'coaloldunscr': 'coal', 'nuclear': 'nuclear', 'upv': 'solar', 'pvb_pv': 'solar', 'wind-ons': 'onwind',
            'battery_li': 'battery', 'hydEND': 'hydro', 'hydED': 'hydro', 'biopower': 'biomass',
            'lfill-gas': 'biomass', 'pumped-hydro': 'battery'}
FAM_MODEL = {'CCGT': 'gas', 'OCGT': 'gas', 'gas_steam': 'gas', 'coal': 'coal', 'nuclear': 'nuclear', 'biomass': 'biomass',
             'onwind': 'wind', 'solar': 'solar', 'battery': 'storage', 'hydro': 'hydro'}
AR_CAT = {'gas': 'Thermal', 'coal': 'Thermal', 'nuclear': 'Thermal', 'biomass': 'Thermal', 'wind': 'Wind', 'solar': 'Solar',
          'storage': 'Storage', 'hydro': 'Hydro'}
AR_MW = {'Thermal': 89507, 'Wind': 40719, 'Solar': 37443, 'Storage': 16656, 'Hydro': 579}
TREND_FAM = {'Wind Chart': 'wind', 'Solar Chart': 'solar', 'Battery Chart': 'storage', 'Gas-Combined Cycle Chart': 'gas', 'Gas-Other Chart': 'gas'}
CORE = ('OPERATING', 'OPERATING_QUALIFIED')
STOP = set('''UNIT UNITS U CTG STG CT ST GT CC CCGT STEAM TURBINE TURBINES PLANT POWER ENERGY CENTER CENTRE STATION GENERATING
GENERATION GEN PROJECT FACILITY LLC LP INC CO COMPANY THE OF AND SOLAR WIND STORAGE BESS ESS BATTERY BATT PV SLR FARM PARK
HYBRID REPOWER REPOWERING PHASE PH BLOCK IC DIESEL HYDRO NUCLEAR COAL GAS ELECTRIC A B C D E'''.split())
ROMAN = {'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def norm_tokens(name):
    """plant-level name key: upper case, alphanumerics, drop technology / legal / phase words, unit numbers, roman numerals"""
    s = re.sub(r'[^A-Z0-9 ]', ' ', str(name).upper().replace('&', ' AND '))
    toks = []
    for t in s.split():
        t = re.sub(r'^(U|UNIT|CTG|STG|GT|ST|CC|BESS|ESS|PV|WT|IC)(\d+)$', '', t)
        if not t or t in STOP or t in ROMAN or any(ch.isdigit() for ch in t):     # unit / phase designators (1CT101, 2ST, PES1)
            continue
        toks.append(t)
    return tuple(toks)


def similarity(a, b):
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    j = len(a & b) / len(a | b)
    if a <= b or b <= a:                     # one plant name contained in the other ('CAPRICORN RIDGE' vs 'CAPRICORN RIDGE 4')
        j = max(j, 0.75)
    return j


def cdr_family(fuel):
    f = str(fuel)
    if f.startswith('SOLAR'):
        return 'solar'
    if f.startswith('WIND'):
        return 'wind'
    return {'GAS': 'gas', 'DIESEL': 'gas', 'COAL': 'coal', 'NUCLEAR': 'nuclear', 'BIOMASS': 'biomass', 'HYDRO': 'hydro',
            'STORAGE': 'storage', 'MWH': 'dc_tie'}.get(f, 'other')


def scope_bucket(status, attr):
    s, a = str(status), str(attr)
    if s.startswith('PLAN'):
        return 'PLANNED_NOT_2025'
    if s == 'MOTH-IND':
        return 'MOTHBALLED_INDEFINITE'
    if a == 'SWGR-UNA':
        return 'SWITCHABLE_UNAVAILABLE_ADJ'
    if a == 'SWGR-AVA':
        return 'SWITCHABLE_AVAILABLE'
    if a == 'DC-TIE':
        return 'DC_TIE'
    if 'SLF' in s or a == 'CONV-SLF':
        return 'PRIVATE_NETWORK'
    if a in ('CONV-DGR', 'CONV-SODG'):
        return 'DISTRIBUTION_DG'
    if s in ('OPER', 'RMR'):
        return 'OPERATING'
    if s in ('OPER-SYN', 'OPER-UNFC', 'OPER-UNR'):
        return 'OPERATING_QUALIFIED'
    if s in ('EXT-OUT', 'MOTH-SEA'):
        return 'OUTAGE_OR_SEASONAL'
    return 'OTHER'


# ------------------------------------------------------------------------------------------------ sources
def county_names():
    try:
        import geopandas as gpd
        c = gpd.read_file(BP.WORKFLOW / 'data/counties/cb_2020_us_county_500k.shp', ignore_geometry=True)
        c = c[c.STATEFP == '48']
        return dict(zip(c.GEOID.astype(str), c.NAME.str.upper())), 'Census cb_2020 county shapefile'
    except Exception:
        sh = pd.read_csv(BP.BASE_TAMU_DIR / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
        return dict(zip(sh.GEOID.str.zfill(5), sh.NAME.str.upper())), 'COUNTY_TO_BUS_SHARES (ERCOT counties only)'


def model_units():
    db = pd.read_csv(BP.REEDS_GENDB, low_memory=False)
    db = db[db.T_PCA.astype(str).str.strip() == 'ERCO'].copy()
    db['carrier'] = db.tech.map(TECH_MAP)
    db = db[db.carrier.notna()].copy()
    st = db.status.str[:4]
    db['model_set'] = np.where(st.isin(['(OP)', '(SB)']) & (db.StartYear <= 2025) & (db.RetireYear > 2025), 'active2025',
                               np.where(st.isin(['(U) ', '(V) ', '(TS)']), 'committed', 'not_in_model'))
    names, basis = county_names()
    db['GEOID'] = db.FIPS.astype(str).str.replace('p', '', regex=False).str.zfill(5)
    db['county'] = db.GEOID.map(names).fillna('UNKNOWN')
    db['family'] = db.carrier.map(FAM_MODEL)
    db['key'] = db.T_PNM.map(norm_tokens)
    db['gkey'] = list(zip(db.county, db.family, db.key))
    return db, basis


def cdr_units():
    u = pd.read_csv(DER / 'CDR_DEC2025_UNIT_REGISTER_AUDIT_ONLY.csv')
    u['family'] = u.FUEL.map(cdr_family)
    u['scope_bucket'] = [scope_bucket(s, a) for s, a in zip(u['CDR STATUS'], u['CDR RESOURCE ATTRIBUTE'])]
    d = pd.to_datetime(u['IN-SERVICE DATE'], errors='coerce')
    u['in_service_le_2025'] = np.where(d.isna(), 'UNKNOWN_DATE', np.where(d <= CUTOFF, 'YES', 'NO'))
    u['county'] = u.COUNTY.fillna('UNKNOWN').astype(str).str.upper().str.strip()
    u['key'] = u['UNIT NAME'].map(norm_tokens)
    u['gkey'] = list(zip(u.county, u.family, u.key))
    u['MW'] = u['INSTALLED CAPACITY (MW)'].astype(float)
    u['core_2025'] = u.scope_bucket.isin(CORE) & (u.in_service_le_2025 != 'NO')
    return u


# ------------------------------------------------------------------------------------------------ B: matching
def match(u, db):
    """group-level matching; returns {cdr gkey: (status, reeds gkey or None, score, note)}; each reeds group used once"""
    cg = u[~u.scope_bucket.isin(['SWITCHABLE_UNAVAILABLE_ADJ', 'DC_TIE'])].groupby('gkey').MW.sum()
    rg = db.groupby('gkey').summer_power_capacity_MW.sum()
    rkeys = set(rg.index)
    res, used = {}, set()
    for k in cg.index:                                                  # 1. exact county + family + plant key
        if k in rkeys and k[2]:
            res[k] = ('MATCH_EXACT', k, 1.0, '')
            used.add(k)
    by_cf = {}
    for k in rkeys:
        by_cf.setdefault((k[0], k[1]), []).append(k)
    cand = []
    for k in cg.index:                                                  # 2. token similarity inside county + family
        if k in res:
            continue
        sc = sorted(((similarity(k[2], r[2]), r) for r in by_cf.get((k[0], k[1]), []) if r not in used), reverse=True)
        sc = [x for x in sc if x[0] >= 0.5]
        if not sc:
            continue
        if len(sc) > 1 and sc[1][0] >= sc[0][0] - 0.1:
            res[k] = ('AMBIGUOUS', None, sc[0][0], '; '.join(' '.join(r[2]) for _, r in sc[:4]))
            continue
        cand.append((sc[0][0], k, sc[0][1]))
    for s_, k, r in sorted(cand, key=lambda x: (-x[0], str(x[1]))):
        if r in used:
            res[k] = ('AMBIGUOUS', None, s_, f'best model group already matched: {" ".join(r[2])}')
        else:
            res[k] = ('MATCH_FUZZY', r, s_, '')
            used.add(r)
    by_f = {}
    for k in rkeys:
        by_f.setdefault(k[1], []).append(k)
    for k in cg.index:                                                  # 3. other county (e.g. switchable / out-of-state FIPS), unique and >= 0.75
        if k in res or not k[2]:
            continue
        sc = sorted(((similarity(k[2], r[2]), r) for r in by_f.get(k[1], []) if r not in used and r[0] != k[0]), reverse=True)
        sc = [x for x in sc if x[0] >= 0.75]          # contained plant name (0.75) or better, unique
        if len(sc) == 1 or (len(sc) > 1 and sc[1][0] < sc[0][0] - 0.1):
            res[k] = ('MATCH_FUZZY_OTHER_COUNTY', sc[0][1], sc[0][0], f'model county {sc[0][1][0]}')
            used.add(sc[0][1])
        elif sc:
            res[k] = ('AMBIGUOUS', None, sc[0][0], 'other-county candidates: ' + '; '.join(f'{r[0]}:{" ".join(r[2])}' for _, r in sc[:4]))
    rem = [k for k in cg.index if k not in res]                        # 4. capacity-assisted CANDIDATE (not a confirmed identity)
    rem_r = [r for r in rkeys if r not in used]
    band = lambda c_, r_: rg[r_] > 0 and 0.8 <= cg[c_] / rg[r_] <= 1.25
    for k in rem:
        rc = [r for r in rem_r if r[:2] == k[:2] and band(k, r)]
        if len(rc) != 1:
            continue
        back = [c_ for c_ in rem if c_[:2] == k[:2] and band(c_, rc[0])]
        if back == [k] and rc[0] not in used:
            res[k] = ('CANDIDATE_COUNTY_FUEL_CAPACITY', rc[0], round(float(cg[k] / rg[rc[0]]), 3),
                      f'unique county + family + MW (0.8-1.25) pair, names differ: model {" ".join(rc[0][2])}; identity NOT confirmed')
            used.add(rc[0])
    for k in cg.index:
        res.setdefault(k, ('UNMATCHED', None, 0.0, 'no model group in county + family with similarity >= 0.5'))
    return res, used


def generator_match(u, db):
    res, used = match(u, db)
    agg = db.groupby('gkey').agg(model_unique_ids=('Unique ID', lambda s: ';'.join(map(str, s))),
                                 model_plant_ids=('T_PID', lambda s: ';'.join(sorted(set(map(str, s))))),
                                 model_plant_names=('T_PNM', lambda s: '; '.join(sorted(set(map(str, s))))),
                                 model_summer_MW_all=('summer_power_capacity_MW', 'sum'), model_nameplate_MW_all=('TC_NP', 'sum'),
                                 model_start_years=('StartYear', lambda s: ';'.join(map(str, sorted(set(s))))),
                                 model_sets=('model_set', lambda s: ';'.join(sorted(set(s)))))
    for ms in ('active2025', 'committed', 'not_in_model'):
        agg[f'model_{ms}_summer_MW'] = db[db.model_set == ms].groupby('gkey').summer_power_capacity_MW.sum()
    agg = agg.fillna({c: 0.0 for c in agg.columns if c.endswith('_MW')})
    num = [c for c in agg.columns if pd.api.types.is_numeric_dtype(agg[c])]
    cg = u.groupby('gkey').agg(group_cdr_core_2025_MW=('MW', lambda s: float(s[u.loc[s.index, 'core_2025']].sum())),
                               group_cdr_all_MW=('MW', 'sum'))
    rows = []
    for r in u.itertuples():
        st, rk, sc, note = res.get(r.gkey, ('NOT_MATCHED_BY_RULE', None, 0.0, 'switchable adjustment / DC tie: not a generating unit'))
        a = agg.loc[[rk]].iloc[0] if rk is not None and rk in agg.index else None
        rows.append(dict(side='CDR', match_status=st, match_score=round(sc, 3), match_note=note,
                         cdr_group_key='|'.join([r.county, r.family, ' '.join(r.key)]),
                         model_group_key='|'.join([rk[0], rk[1], ' '.join(rk[2])]) if rk else '',
                         cdr_unit_name=r._2, cdr_unit_code=r._4, cdr_inr=r._3, county=r.county, family=r.family, ar_category=AR_CAT.get(r.family, 'Other'),
                         cdr_status=r._7, cdr_attribute=r._8, scope_bucket=r.scope_bucket, in_service_date=r._11, in_service_le_2025=r.in_service_le_2025,
                         cdr_installed_MW=r.MW, cdr_core_2025=bool(r.core_2025), group_cdr_core_2025_MW=float(cg.group_cdr_core_2025_MW[r.gkey]),
                         **({k: a[k] for k in agg.columns} if a is not None else {k: (0.0 if k in num else '') for k in agg.columns})))
    for rk in sorted(set(agg.index) - used, key=str):
        a = agg.loc[[rk]].iloc[0]
        rows.append(dict(side='MODEL', match_status='MODEL_ONLY', match_score=0.0, match_note='no CDR group matched this model group',
                         cdr_group_key='', model_group_key='|'.join([rk[0], rk[1], ' '.join(rk[2])]), county=rk[0], family=rk[1],
                         ar_category=AR_CAT.get(rk[1], 'Other'), **{k: a[k] for k in agg.columns}))
    m = pd.DataFrame(rows)
    m['model_inclusion_status'] = np.where(m.model_active2025_summer_MW > 0, 'IN_2025_MODEL_FLEET',
                                           np.where(m.model_committed_summer_MW > 0, 'IN_MODEL_COMMITTED_PIPELINE',
                                                    np.where(m.model_summer_MW_all > 0, 'IN_DB_NOT_IN_MODEL', 'UNKNOWN_NOT_LINKED')))
    m['note_numeric_use'] = 'audit only: no field of this table enters the model matrices'
    return m, res, used, agg


def capacity_bridge(u, db, m, res, agg):
    """exact decomposition of CDR core 2025 - model active 2025 per family, then the publication residual per AR category"""
    trend = pd.read_csv(DER / 'CAPACITY_TREND_DEC2025_EXTRACT.csv')
    tr = trend.assign(family=trend.sheet.map(TREND_FAM)).groupby('family').operational_MW.sum()
    model = db[db.model_set == 'active2025'].groupby('family').summer_power_capacity_MW.sum()
    comp = {f: dict(rating_diff=0.0, pipeline_cross=0.0, matched_no_model=0.0, candidate_pairs=0.0, cdr_unmatched=0.0, model_unmatched=0.0,
                    model_matched_noncore=0.0)
            for f in FAM_MODEL.values()}
    core = u[u.core_2025].groupby('gkey').MW.sum()
    seen_r = set()
    for ck, (st, rk, _, _) in res.items():
        f = ck[1]
        if f not in comp:
            continue
        c = float(core.get(ck, 0.0))
        if rk is None:
            comp[f]['cdr_unmatched'] += c
            continue
        seen_r.add(rk)
        mm = float(agg.model_active2025_summer_MW.get(rk, 0.0)); kk = float(agg.model_committed_summer_MW.get(rk, 0.0))
        if st.startswith('CANDIDATE'):
            comp[f]['candidate_pairs'] += c - mm
        elif mm > 0 and c > 0:
            comp[f]['rating_diff'] += c - mm
        elif mm > 0:
            comp[f]['model_matched_noncore'] -= mm
        elif c > 0 and kk > 0:
            comp[f]['pipeline_cross'] += c
        elif c > 0:
            comp[f]['matched_no_model'] += c
    for rk in set(agg.index) - seen_r:
        f = rk[1]
        comp[f]['model_unmatched'] -= float(agg.model_active2025_summer_MW.get(rk, 0.0))
    scope = u.groupby(['family', 'scope_bucket']).MW.sum()
    rows, ok = [], True
    for f in sorted(comp):
        cdr_core = float(u[u.core_2025 & (u.family == f)].MW.sum())
        mod = float(model.get(f, 0.0))
        s = sum(comp[f].values())
        ok &= abs(cdr_core - mod - s) < 1e-6
        base = dict(family=f, ar_category=AR_CAT[f], unit='MW')
        rows.append(dict(base, component='model_active2025_summer_MW', MW=mod, basis='ReEDS DB active 2025 (OP/SB, Start<=2025<Retire), summer MW = model fleet'))
        rows.append(dict(base, component='cdr_core_2025_installed_MW', MW=cdr_core, basis='CDR OPER/RMR + OPER-SYN/UNFC/UNR, CONV(-TGR), in-service <= 2025-12-31 or unknown'))
        for k, txt in [('rating_diff', 'matched groups: CDR installed - model summer (rating definition + phase coverage inside the group)'),
                       ('pipeline_cross', 'CDR operating by 2025 but model holds the group only in the committed pipeline (B4 cross-ledger)'),
                       ('matched_no_model', 'matched group without model active / committed units (retired / out of service in the DB)'),
                       ('candidate_pairs', 'capacity-assisted county + family candidates (names differ): CDR core - model active; identity NOT confirmed'),
                       ('cdr_unmatched', 'CDR core MW without a matched model group: suspected omission OR unresolved name (not decided)'),
                       ('model_unmatched', 'model active MW without a matched CDR group (negative)'),
                       ('model_matched_noncore', 'model active MW whose CDR match is outside the 2025 core (PLAN / private / DG / outage) (negative)')]:
            rows.append(dict(base, component=f'decomp_{k}', MW=comp[f][k], basis=txt))
        rows.append(dict(base, component='identity_check_cdr_core_minus_model', MW=cdr_core - mod - s, basis='must be 0'))
        for b_ in ['OPERATING_QUALIFIED', 'PRIVATE_NETWORK', 'DISTRIBUTION_DG', 'SWITCHABLE_AVAILABLE', 'SWITCHABLE_UNAVAILABLE_ADJ',
                   'OUTAGE_OR_SEASONAL', 'MOTHBALLED_INDEFINITE', 'PLANNED_NOT_2025']:
            rows.append(dict(base, component=f'scope_info_{b_}', MW=float(scope.get((f, b_), 0.0)),
                             basis='CDR scope bucket (information; candidate explanation, NOT allocated to any residual)'))
        if f in tr:
            rows.append(dict(base, component='dec2025_trend_operational_MW', MW=float(tr[f]), basis='Capacity_December2025.xlsx 2025 operational'))
            rows.append(dict(base, component='trend_minus_cdr_core_MW', MW=float(tr[f]) - cdr_core, basis='snapshot / status definition between two ERCOT December publications: UNEXPLAINED'))
    fam_rows = pd.DataFrame(rows)
    cat_rows = []
    for cat, ar in AR_MW.items():
        fs = [f for f, c in AR_CAT.items() if c == cat]
        sel = fam_rows[fam_rows.family.isin(fs)]
        g = lambda c: float(sel[sel.component == c].MW.sum())
        mod, cdr = g('model_active2025_summer_MW'), g('cdr_core_2025_installed_MW')
        base = dict(family='ALL:' + '+'.join(fs), ar_category=cat, unit='MW')
        cat_rows += [dict(base, component='annual_report_installed_MW', MW=ar, basis='2025 ERCOT Annual Report p.6 (installed ratings, broad scope)'),
                     dict(base, component='model_active2025_summer_MW', MW=mod, basis='sum of families'),
                     dict(base, component='apparent_gap_AR_minus_model_MW', MW=ar - mod, basis='CAPACITY_DEFINITION_BRIDGE apparent gap'),
                     dict(base, component='cdr_core_minus_model_MW', MW=cdr - mod, basis='explained component by component in the family rows'),
                     dict(base, component='UNEXPLAINED_AR_minus_cdr_core_MW', MW=ar - cdr,
                          basis='publication scope / rating / snapshot residual; candidates: private-network, DG, switchable, outage, nameplate vs installed - NOT allocated')]
    out = pd.concat([pd.DataFrame(cat_rows), fam_rows], ignore_index=True)
    out['MW'] = out.MW.round(6) + 0.0                     # deterministic across machines (no -0.000000)
    return out, ok


def pipeline_suggestions(m):
    x = m[(m.side == 'CDR') & m.match_status.str.startswith('MATCH')]
    g = x.groupby(['cdr_group_key', 'model_group_key']).agg(
        cdr_units=('cdr_unit_name', lambda s: '; '.join(s)), cdr_core_2025_MW=('group_cdr_core_2025_MW', 'first'),
        cdr_statuses=('cdr_status', lambda s: ';'.join(sorted(set(map(str, s))))), cdr_in_service=('in_service_date', lambda s: ';'.join(sorted(set(map(str, s))))),
        model_active2025_MW=('model_active2025_summer_MW', 'first'), model_committed_MW=('model_committed_summer_MW', 'first'),
        model_start_years=('model_start_years', 'first'), family=('family', 'first')).reset_index()
    a = g[(g.cdr_core_2025_MW > 0) & (g.model_committed_MW > 0)].assign(
        direction='CDR_OPERATING_2025__MODEL_COMMITTED_PIPELINE',
        suggestion='candidate: move the matched committed units to the 2025 fleet (or confirm a later COD); NOT applied - researcher decision')
    b = g[(g.cdr_core_2025_MW == 0) & (g.model_active2025_MW > 0)].assign(
        direction='MODEL_ACTIVE_2025__CDR_NOT_CORE_2025', suggestion='check CDR status (PLAN / private / DG / outage) vs model active; NOT applied')
    s = pd.concat([a, b], ignore_index=True)
    s['priority'] = np.where(s.family.isin(['solar', 'storage']), 'HIGH (WP B4: solar / battery first)', 'NORMAL')
    return s.sort_values(['priority', 'family', 'cdr_core_2025_MW'], ascending=[True, True, False])


# ------------------------------------------------------------------------------------------------ B5: historical AIDC
AIDC_RULING = {   # WP §4 research ruling (2026-10-22); values unchanged, evidence class added
    'OpenAI Stargate Abilene': ('OPERATION_CONFIRMED_FIRST_HAND__IT_MW_ESTIMATED', 'Crusoe 2025-09-30 newsroom: phase 1 live',
                                'operation has first-hand support; exact IT MW and phase dates remain Epoch estimates'),
    'CoreWeave Denton TX': ('COMPANY_BILLABLE_MW__NOT_ENERGIZED_IT', 'Core Scientific Q1 2025 release: 8 MW expected in May (plan wording)',
                            'billable / energized / IT / actual load to be recorded separately; plan wording not upgraded to fact'),
    'Meta Temple': ('ESTIMATE__2025_OPERATION_NOT_CONFIRMED', 'Epoch 2025-12-09 best estimate; Meta announced serving traffic 2026-07-22',
                    'not VERIFIED for 2025; not asserted as zero load either'),
    'Google Red Oak': ('ESTIMATE__IMAGERY', 'Epoch imagery (building, equipment, parking)', 'estimate, no meter or verified energization record'),
    'Microsoft SAT40': ('ESTIMATE__IMAGERY_DOWNGRADED', 'Epoch construction / equipment imagery', 'value kept, evidence class downgraded'),
    'Microsoft SAT14': ('ESTIMATE__IMAGERY_DOWNGRADED', 'Epoch cooling equipment / substation / construction imagery', 'value kept, evidence class downgraded'),
}


def historical_aidc():
    st = pd.read_csv(BP.INPUTS / 'dc/EPOCH_TX_SITES_TAMU64.csv')
    tl = pd.read_csv(BP.INPUTS / 'dc/EPOCH_TX_TIMELINE_EVIDENCE.csv')
    tl['date'] = pd.to_datetime(tl.Date)
    ramp = pd.read_csv(BP.INPUTS / 'dc/MAINLINE_INHERITED_RAMP_2025.csv').set_index('bus')
    rows = []
    for r in st[st.ercot].itertuples():
        g = tl[(tl.site == r.site) & (tl.date <= CUTOFF)].sort_values('date')
        last = g.iloc[-1] if len(g) else None
        cls, ev, why = AIDC_RULING.get(r.site, ('NO_2025_CAPACITY' if r.IT_MW_2025 == 0 else 'UNCLASSIFIED', '', ''))
        rows.append(dict(site=r.site, bus=r.bus, IT_MW_2025_avg=r.IT_MW_2025_avg, IT_MW_2025_end=r.IT_MW_2025,
                         inherited_ramp_IT_MW=r.IT_carryover_2025_MW, algebra_end_minus_avg_ok=abs(r.IT_MW_2025 - r.IT_MW_2025_avg - r.IT_carryover_2025_MW) < 1e-6,
                         evidence_class=cls, evidence_source_and_date=ev, ruling_reason=why,
                         last_2025_timeline_date=str(last.Date) if last is not None else '', last_2025_timeline_IT_MW=float(last.IT_MW) if last is not None else 0.0,
                         last_2025_estimate_wording=bool(last.estimate_wording) if last is not None else None,
                         last_2025_observed_by_as_of=bool(last.observed_by_as_of) if last is not None else None,
                         inferred=cls.startswith('ESTIMATE') or 'ESTIMATED' in cls or cls.startswith('COMPANY'),
                         estimate_wording_rule='estimate_wording=False is NOT sufficient for VERIFIED (WP B5)',
                         treatment='2025 avg inside the 2025 native load (not re-added); inherited ramp = load proxy derived from a historical capacity estimate, added from 2026'))
    d = pd.DataFrame(rows)
    by_bus = d.groupby('bus').inherited_ramp_IT_MW.sum()
    d['bus_ramp_matches_MAINLINE_INHERITED_RAMP'] = d.bus.map(lambda b: abs(by_bus.get(b, 0) - (ramp.inherited_ramp_IT_MW.get(b, 0.0))) < 1e-6)
    d['ramp_label'] = np.where(d.inherited_ramp_IT_MW > 0, 'LOAD_PROXY_FROM_HISTORICAL_CAPACITY_ESTIMATE', '')
    return d, float(ramp.inherited_ramp_IT_MW.sum())


# ------------------------------------------------------------------------------------------------ C: load accounting
def load_accounting():
    h = pd.read_csv(DER / 'ERCOT_NATIVE_LOAD_2025_1H.csv')
    t3 = pd.read_csv(DER / 'ERCOT_NATIVE_LOAD_2025_3H.csv')
    bus = pd.read_csv(BP.BASE_TAMU_DIR / 'ercot_load_2025_3h_by_bus.csv.gz', index_col=[0, 1])
    lab = h['Hour Ending'].astype(str)
    E = float(h.ERCOT.sum())
    bus_sum = bus.sum(axis=1).values
    gf = pd.read_csv(BP.BG_LOAD_GROWTH)
    tx = gf[gf.state == 'TX'].set_index('year').factor_vs_2025
    ramp = pd.read_csv(BP.INPUTS / 'dc/MAINLINE_INHERITED_RAMP_2025.csv')
    rows = [
        dict(component='native_load_1h_rows', value=len(h), unit='rows', check=len(h) == 8760, location='inputs/anchor2025/ERCOT_NATIVE_LOAD_2025_1H.csv'),
        dict(component='native_load_DST_rows_kept', value=int(lab.str.contains('DST').sum()), unit='rows', check=int(lab.str.contains('DST').sum()) == 1,
             location='source_row_1based kept; the 02:00 DST repeat is not dropped'),
        dict(component='native_load_HE_24_00_rows_kept', value=int(lab.str.endswith('24:00').sum()), unit='rows', check=int(lab.str.endswith('24:00').sum()) == 365,
             location='HE 24:00 kept as the last hour of its day (not double-counted as the next day 00:00)'),
        dict(component='native_load_source_rows_unique_sequential', value=int(h.source_row_1based.is_monotonic_increasing and h.source_row_1based.is_unique),
             unit='bool', check=bool(h.source_row_1based.is_unique), location='row order = repository order'),
        dict(component='native_load_energy_MWh', value=E, unit='MWh', check=abs(E / 1e6 - 488.233578542299) < 1e-9, location='VERIFIED_METRICS energy_TWh'),
        dict(component='3h_periods_x_weight', value=len(t3) * 3, unit='h', check=len(t3) == 2920 and (t3.weight_hours == 3).all(), location='row-order 3 h means, weight 3'),
        dict(component='3h_energy_conservation_abs_MWh', value=abs(float(t3.ERCOT.sum()) * 3 - E), unit='MWh', check=abs(float(t3.ERCOT.sum()) * 3 - E) < 1e-3, location='sum(3h mean x 3) = 1 h energy'),
        dict(component='baseline_bus_load_energy_MWh', value=float(bus_sum.sum() * 3), unit='MWh', check=abs(float(bus_sum.sum() * 3) - E) < 1e-3 * 1e3,
             location='results/BYOP/baseline_2025_tamu/ercot_load_2025_3h_by_bus.csv.gz (weather zone -> county lpf -> substation -> bus)'),
        dict(component='baseline_bus_load_per_step_max_abs_error_MW', value=float(np.abs(bus_sum - t3.ERCOT.values).max()), unit='MW',
             check=float(np.abs(bus_sum - t3.ERCOT.values).max()) < 1e-3, location='each 3 h step: sum over buses = ERCOT 3 h native load'),
        dict(component='baseline_bus_count', value=bus.shape[1], unit='buses', check=bus.shape[1] > 0, location='historical load buses (spatial split is a model rule, not metered)'),
        dict(component='historical_AIDC_2025_avg_added_on_top', value=0.0, unit='MW', check=True,
             location='rearch_mech: no 2025 AIDC Load is added; the 2025 average (140.27 MW IT) is inside the native load'),
        dict(component='inherited_ramp_IT_MW_from_2026', value=float(ramp.inherited_ramp_IT_MW.sum()), unit='MW IT', check=abs(float(ramp.inherited_ramp_IT_MW.sum()) - 460.73) < 1e-6,
             location='rearch_mech.add_inherited_ramp (periods >= 2026, x PUE(period); never in a 2025 period)'),
        dict(component='background_load_scale_factor_2025', value=float(tx[2025]), unit='-', check=abs(float(tx[2025]) - 1.0) < 1e-12,
             location='v240_mech.build bg_traj (factor_vs_2025, TX); 2026+: ' + ', '.join(f'{y}:{tx[y]:.6f}' for y in range(2026, 2032))),
        dict(component='storage_charging_in_load', value=0.0, unit='MW', check=True,
             location='battery charging is a StorageUnit dispatch variable, not a Load; Fuel Mix WSL (negative) is a generation-side ledger item'),
        dict(component='research_AIDC_in_2025', value=0.0, unit='MW', check=True, location='research cohorts start 2026 (S0 has none at all)'),
        dict(component='regional_dc_and_competing_queue_mainline', value=0.0, unit='MW', check=True, location='mainline forces regional_dc=off, competing=0 (rearch_mech.main)'),
        dict(component='fuelmix_minus_native_GWh', value=float(json.loads((DER / 'VERIFIED_METRICS.json').read_text())['fuelmix_total_minus_native_GWh']),
             unit='GWh', check=True, location='reported only (-0.033 %); neither ledger is adjusted to close it'),
    ]
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ D: uplift ledger
def uplift_ledger(check_nc=False):
    L = pd.read_csv(BP.BASE_TAMU_DIR / 'LINE_LEDGER.csv')
    cal = pd.read_csv(BP.BASE_TAMU_DIR / 'TAMU_2025_CALIBRATION_LP.csv').set_index('line')
    s0 = pd.read_csv(BP.RESULTS / 'mainline/MAINLINE_V13_GREAL_MID_S0CAL/S0_CALIBRATION.csv').set_index('line')
    rule = L.interface_rule.iloc[0]
    rule_col = {'reeds_sum': 'reeds_sum_s_nom', 'tamu_raw': 'tamu_raw_s_nom', 'pypsa_usa': 'pypsa_usa_s_nom'}[rule]
    d = L[['name', 'bus0', 'bus1', 'zone0', 'zone1', 'cross_zone', 'n_member_lines', 'tamu_raw_s_nom', 'pypsa_usa_s_nom', rule_col,
           'calibration_uplift_MVA', 'final_s_nom', 's_max_pu', 'final_transfer_MW']].rename(columns={'name': 'line', rule_col: 'interface_rule_s_nom_MVA'})
    d['interface_rule'] = rule
    d['layer1_raw_synthetic_MVA'] = d.tamu_raw_s_nom
    d['layer2_2025_calibration_uplift_MVA'] = d.calibration_uplift_MVA
    d['calibration_LP_listed'] = d.line.isin(cal.index)
    d['calibration_LP_added_MVA'] = d.line.map(cal.added_MVA).fillna(0.0)
    d['final_identity_error_MVA'] = d.final_s_nom - (d.interface_rule_s_nom_MVA + d.calibration_uplift_MVA)
    d['layer3_S0CAL_2026plus_added_MW'] = d.line.map(s0.added_MW).fillna(0.0)
    d['layer3_S0CAL_existing_MVA_seen'] = d.line.map(s0.existing_MVA)
    d['S0CAL_existing_equals_final_s_nom'] = (d.layer3_S0CAL_existing_MVA_seen - d.final_s_nom).abs() < 1e-6
    d['layer3_form'] = np.where(d.layer3_S0CAL_2026plus_added_MW > 0.5, 'fixed Link pair AC_s0cal fwd / rev (MW, from 2026), line s_nom untouched', '')
    d['units'] = 'MVA (s_nom; transfer = s_nom x s_max_pu MW) | S0CAL in MW Link capacity'
    d['evidence_class'] = np.where(d.calibration_uplift_MVA > 0.5, 'B: synthetic 2025 calibration uplift (B2025_CALIBRATION_LP); NOT a TPIT project or a verified thermal limit',
                                   'synthetic TAMU / interface-rule rating (proxy identity)')
    nc_check = None
    if check_nc:
        nc_check = baseline_nc_check(d)
    return d, nc_check


def baseline_nc_check(d):
    """read-only: final line s_nom in the baseline network = ledger final_s_nom; no S0CAL link in the 2025 baseline"""
    p = BP.BASE_TAMU_DIR / 'baseline_2025_tamu_prepared.nc'
    if not p.exists():
        return dict(status='NOT_AVAILABLE_HERE', path=str(p))
    import pypsa                                                   # read only; no optimize / linopy call in this module
    n = pypsa.Network(str(p))
    s = n.lines.s_nom.reindex(d.line)
    err = float((s.values - d.final_s_nom.values).__abs__().max())
    return dict(status='CHECKED', path=str(p), sha256=sha(p), lines=len(n.lines), max_abs_s_nom_error_MVA=err,
                ac_s0cal_links_in_baseline=int((n.links.carrier == 'AC_s0cal').sum()), ok=err < 1e-6 and not (n.links.carrier == 'AC_s0cal').any())


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check-nc', action='store_true', help='read the L2 baseline .nc (no solve)')
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    db, cbasis = model_units()
    u = cdr_units()
    m, res, used, agg = generator_match(u, db)
    bridge, ident_ok = capacity_bridge(u, db, m, res, agg)
    sug = pipeline_suggestions(m)
    aidc, ramp_total = historical_aidc()
    la = load_accounting()
    up, ncc = uplift_ledger(a.check_nc)
    w = lambda df, nm: df.to_csv(OUT / nm, index=False, lineterminator='\n', float_format='%.6f')
    w(m, 'C0_GENERATOR_MATCH.csv'); w(bridge, 'C0_CAPACITY_BRIDGE.csv'); w(sug, 'C0_PIPELINE_RECLASS_SUGGESTIONS.csv')
    w(aidc, 'C0_HISTORICAL_AIDC_EVIDENCE.csv'); w(la, 'C0_LOAD_ACCOUNTING.csv'); w(up, 'C0_UPLIFT_LEDGER.csv')
    # coverage
    cdr = m[m.side == 'CDR']
    core = cdr[cdr.cdr_core_2025]
    mt = core.match_status.str.startswith('MATCH')
    act = db[db.model_set == 'active2025']
    conf = {r for st_, r, _, _ in res.values() if r is not None and st_.startswith('MATCH')}
    act_m = act.gkey.isin(conf)
    act_c = act.gkey.isin(used)
    cov = dict(cdr_core_units=int(len(core)), cdr_core_MW=float(core.cdr_installed_MW.sum()),
               cdr_core_matched_units=int(mt.sum()), cdr_core_matched_MW=float(core[mt].cdr_installed_MW.sum()),
               cdr_core_match_share_units=float(mt.mean()), cdr_core_match_share_MW=float(core[mt].cdr_installed_MW.sum() / core.cdr_installed_MW.sum()),
               cdr_core_ambiguous_MW=float(core[core.match_status == 'AMBIGUOUS'].cdr_installed_MW.sum()),
               cdr_core_candidate_MW=float(core[core.match_status.str.startswith('CANDIDATE')].cdr_installed_MW.sum()),
               cdr_core_matched_or_candidate_share_MW=float(core[mt | core.match_status.str.startswith('CANDIDATE')].cdr_installed_MW.sum() / core.cdr_installed_MW.sum()),
               cdr_core_unmatched_MW=float(core[core.match_status == 'UNMATCHED'].cdr_installed_MW.sum()),
               model_active_units=int(len(act)), model_active_MW=float(act.summer_power_capacity_MW.sum()),
               model_active_matched_units=int(act_m.sum()), model_active_matched_MW=float(act[act_m].summer_power_capacity_MW.sum()),
               model_active_match_share_MW=float(act[act_m].summer_power_capacity_MW.sum() / act.summer_power_capacity_MW.sum()),
               model_active_matched_or_candidate_share_MW=float(act[act_c].summer_power_capacity_MW.sum() / act.summer_power_capacity_MW.sum()),
               by_status=cdr.groupby('match_status').agg(units=('cdr_installed_MW', 'size'), MW=('cdr_installed_MW', 'sum')).round(3).to_dict('index'),
               county_name_basis=cbasis)
    fleet = json.loads((BP.BASE_TAMU_DIR / 'baseline_2025_tamu_audit.json').read_text())
    plan_in_hist = int(((cdr.scope_bucket == 'PLANNED_NOT_2025') & cdr.cdr_core_2025).sum())
    rk_multi = m[(m.side == 'CDR') & (m.model_group_key != '')].groupby('model_group_key').cdr_group_key.nunique()
    qa = dict(
        stage='C0 offline reconciliation (ERCOT 2025 official anchor v1.3)', solver_executions=0,
        source_sha_ok=json.loads((DER / 'EVIDENCE_REBUILD_CHECK.json').read_text()).get('all_equal'),
        verified_metrics=json.loads((DER / 'VERIFIED_METRICS.json').read_text()),
        load_checks_all_pass=bool(la.check.astype(bool).all()), load_checks={r.component: bool(r.check) for r in la.itertuples()},
        model_fleet_equals_audit=abs(float(act.summer_power_capacity_MW.sum()) - float(fleet['fleet_2025_MW_total'])) < 0.05,
        model_fleet_MW=float(act.summer_power_capacity_MW.sum()), audit_fleet_MW=float(fleet['fleet_2025_MW_total']),
        no_model_group_matched_twice=bool((rk_multi <= 1).all()), plan_units_in_2025_core=plan_in_hist,
        capacity_bridge_identity_ok=bool(ident_ok), coverage=cov,
        pipeline_reclass_suggestions=dict(rows=len(sug), cdr_operating_model_committed_MW=float(sug[sug.direction.str.startswith('CDR_OPERATING')].cdr_core_2025_MW.sum()),
                                          by_family={f'{k[0]}|{k[1]}': v for k, v in sug.groupby(['direction', 'family']).cdr_core_2025_MW.sum().round(1).items()} if len(sug) else {}),
        historical_aidc=dict(sites=len(aidc), algebra_ok=bool(aidc.algebra_end_minus_avg_ok.all()), bus_ramp_ok=bool(aidc.bus_ramp_matches_MAINLINE_INHERITED_RAMP.all()),
                             inherited_ramp_IT_MW=ramp_total, verified_count=int(aidc.evidence_class.str.startswith('VERIFIED').sum())),
        uplift=dict(calibration_2025_lines=int((up.calibration_uplift_MVA > 0.5).sum()), calibration_2025_MVA=float(up[up.calibration_uplift_MVA > 0.5].calibration_uplift_MVA.sum()),
                    residual_shed_MWh=fleet['calibration']['residual_shed_MWh'], ledger_matches_LP=bool((up[up.calibration_LP_listed].calibration_LP_added_MVA - up[up.calibration_LP_listed].calibration_uplift_MVA).abs().max() < 1e-6),
                    final_identity_max_err_MVA=float(up.final_identity_error_MVA.abs().max()), S0CAL_lines=int((up.layer3_S0CAL_2026plus_added_MW > 0.5).sum()),
                    S0CAL_MW=float(up[up.layer3_S0CAL_2026plus_added_MW > 0.5].layer3_S0CAL_2026plus_added_MW.sum()),
                    S0CAL_sees_final_2025_s_nom=bool(up.S0CAL_existing_equals_final_s_nom.all()), baseline_nc=ncc,
                    note='MVA (2025 line uplift, inside s_nom) and MW (S0CAL fixed Links from 2026) are separate layers; never summed'),
        outputs={p.name: sha(p) for p in sorted(OUT.glob('C0_*.csv'))})
    (OUT / 'C0_QA.json').write_bytes((json.dumps(qa, indent=1, default=str) + '\n').encode())
    print(json.dumps({k: qa[k] for k in ('solver_executions', 'source_sha_ok', 'load_checks_all_pass', 'model_fleet_equals_audit', 'no_model_group_matched_twice',
                                         'plan_units_in_2025_core', 'capacity_bridge_identity_ok', 'coverage', 'pipeline_reclass_suggestions', 'historical_aidc', 'uplift')},
                     indent=1, default=str))


if __name__ == '__main__':
    main()
