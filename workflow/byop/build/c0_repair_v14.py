#!/usr/bin/env python3
"""C0 repair (BYOP C0 repair / C1 diagnostics prompt v1.4, 2026-10-22, stage A): phase-level reconciliation, switchable
ledger and match confidence on top of the unchanged C0 v1.3 audit (c0_anchor_audit.py, whose outputs in
results/BYOP/C0_ANCHOR_2025 stay as the v1.3 snapshot). Audit only - no model number changes, no optimizer.
    python byop/build/c0_repair_v14.py

What v1.3 got wrong (A1): pipeline_suggestions() flagged a whole plant group whenever the CDR had ANY 2025 core MW and the
model ANY committed MW, so a historical phase already in the model fleet plus a separate future phase (Callisto I / II,
Tidwell Prairie 1 / 2, Padua 1 / 2-3) looked like one asset held in the wrong ledger. Here the plant-name group is only the
candidate search space; identity is decided per PHASE:
  CDR phase   = units of the group with the same in-service year and the same history class (HIST: in service <= 2025 or
                no date, not PLAN / MOTH-IND; FUTURE otherwise); SWGR-UNA adjustment rows and DC ties are not phases
  model phase = ReEDS units of the group with the same StartYear and model set (active2025 / committed / not_in_model)
  pairing     = |year difference| <= 1 and CDR MW / model MW in [0.8, 1.25], greedy by year gap then MW gap, one-to-one
  actions     = NONE_HISTORICAL_PHASE_COVERED / REVIEW_RECLASS_CANDIDATE (CDR commercial OPER/RMR phase paired with a model
                phase outside the 2025 fleet) / STATUS_QUALIFIED_REVIEW (same, but OPER-SYN or other qualified status: not
                upgraded) / MIXED_PHASE_REVIEW / UNRESOLVED_PHASE / UNRESOLVED_CANDIDATE_IDENTITY (name or capacity
                candidate only) ; future phases: NONE_FUTURE_CONSISTENT / STATUS_CONFLICT_REVIEW / NONE_FUTURE_NOT_PAIRED
Outputs (results/BYOP/C0_REPAIR_V14/): C0_PHASE_RECONCILIATION.csv, C0_RECLASS_REVISED.csv, C0_SWITCHABLE_LEDGER.csv,
C0_MATCH_CONFIDENCE.csv, C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv, C0_CAPACITY_BRIDGE_V14.csv, C0_REPAIR_BEFORE_AFTER.csv,
C0_REPAIR_QA.json
"""
from __future__ import annotations

import hashlib, importlib.util, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'model'))
import byop_paths as BP  # noqa: E402

spec = importlib.util.spec_from_file_location('c0_anchor_audit', HERE / 'c0_anchor_audit.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
OUT, OLD = BP.C0_REPAIR_RESULTS, BP.C0_RESULTS
CDR_PUBLISHED = '2025-12-19'          # CapacityDemandandReservesReport_December2025.xlsx (SOURCE_MANIFEST URL date)
COMMERCIAL = {'OPER', 'RMR'}
YEAR_TOL, RATIO_LO, RATIO_HI = 1, 0.8, 1.25
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def status_class(s):
    s = str(s)
    if s in COMMERCIAL:
        return 'COMMERCIAL_OPER'
    if s.startswith('OPER-SYN'):
        return 'SYNCHRONIZED_NOT_COMMERCIAL'
    if s.startswith('OPER'):
        return 'OPER_QUALIFIED_OTHER'
    if s in ('EXT-OUT', 'MOTH-SEA'):
        return 'OUTAGE_OR_SEASONAL'
    if s == 'MOTH-IND':
        return 'MOTHBALLED_INDEFINITE'
    if s.startswith('PLAN'):
        return 'PLANNED'
    return 'OTHER'


def cdr_frame():
    u = A.cdr_units()
    d = pd.to_datetime(u['IN-SERVICE DATE'], errors='coerce')
    u['in_service_year'] = d.dt.year
    u['date_class'] = np.where(d.isna(), 'NO_DATE', np.where(d <= A.CUTOFF, 'IN_SERVICE_LE_2025', 'FUTURE_DATE'))
    u['status_class'] = u['CDR STATUS'].map(status_class)
    u['phase_class'] = np.where((u.date_class != 'FUTURE_DATE') & ~u.status_class.isin(['PLANNED', 'MOTHBALLED_INDEFINITE']), 'HIST', 'FUTURE')
    u['is_adjustment_row'] = u.scope_bucket.eq('SWITCHABLE_UNAVAILABLE_ADJ') | u.scope_bucket.eq('DC_TIE')
    u['cdr_published'] = CDR_PUBLISHED
    return u


def phases_of(units, side):
    if side == 'CDR':
        x = units[~units.is_adjustment_row]
        g = x.groupby([x.phase_class, x.in_service_year.fillna(-1).astype(int)], dropna=False)
        return [dict(side='CDR', phase_class=k[0], year=None if k[1] < 0 else int(k[1]), MW=float(v.MW.sum()), idx=list(v.index),
                     statuses=sorted(set(v['CDR STATUS'].astype(str))), status_classes=sorted(set(v.status_class))) for k, v in g]
    g = units.groupby('StartYear')                      # one phase per start year (a year may mix ReEDS statuses, e.g. OP + TS)
    return [dict(side='MODEL', model_set=';'.join(sorted(set(v.model_set))), year=int(k), MW=float(v.summer_power_capacity_MW.sum()),
                 nameplate=float(v.TC_NP.fillna(0).sum()), idx=list(v.index)) for k, v in g]


def pair_phases(cp, mp):
    """one-to-one greedy pairing by (year gap, |log MW ratio|); returns {cdr i: model j}"""
    cand = []
    for i, c in enumerate(cp):
        for j, m in enumerate(mp):
            if c['year'] is None or m['MW'] <= 0 or c['MW'] <= 0:
                continue
            dy = abs(c['year'] - m['year']); r = c['MW'] / m['MW']
            if dy <= YEAR_TOL and RATIO_LO <= r <= RATIO_HI:
                cand.append((dy, abs(np.log(r)), i, j))
    out, ui, uj = {}, set(), set()
    for _, _, i, j in sorted(cand):
        if i not in ui and j not in uj:
            out[i] = j; ui.add(i); uj.add(j)
    return out


def noncore_reason(cdr_units):
    """why a model-active phase found no CDR historical phase: dominant CDR bucket of the matched group"""
    if not len(cdr_units):
        return 'NO_CDR_UNITS'
    if (cdr_units.phase_class == 'FUTURE').all():
        return 'SAME_NAME_FUTURE_RECORD_ONLY (repower / expansion?): old model unit identity unresolved'
    nb = cdr_units[cdr_units.phase_class == 'HIST']
    core = nb[nb.core_2025]
    if len(core):
        return 'PHASE_UNPAIRED_WITH_CDR_HISTORICAL (year / MW differ: capacity basis or phase split)'
    b = nb.groupby('scope_bucket').MW.sum().abs().sort_values(ascending=False)
    lab = {'DISTRIBUTION_DG': 'DGR_SODG_DISTRIBUTION', 'PRIVATE_NETWORK': 'PRIVATE_NETWORK', 'OUTAGE_OR_SEASONAL': 'OUTAGE_OR_SEASONAL',
           'SWITCHABLE_AVAILABLE': 'SWITCHABLE_RESOURCE', 'MOTHBALLED_INDEFINITE': 'MOTHBALLED'}
    return lab.get(b.index[0], 'STATUS_CONFLICT_REVIEW') if len(b) else 'STATUS_CONFLICT_REVIEW'


def reconcile(u, db, res):
    rows = []
    gu, gm = u.groupby('gkey').groups, db.groupby('gkey').groups
    for ck, (st, rk, sc, note) in sorted(res.items(), key=lambda x: str(x[0])):
        cu = u.loc[gu[ck]]
        mu = db.loc[gm[rk]] if rk is not None and rk in gm else db.iloc[0:0]
        cp, mp = phases_of(cu, 'CDR'), phases_of(mu, 'MODEL')
        pr = pair_phases(cp, mp) if rk is not None else {}
        name_tier = {'MATCH_EXACT': 'NAME_EXACT_SAME_COUNTY', 'MATCH_FUZZY': 'NAME_FUZZY_SAME_COUNTY',
                     'MATCH_FUZZY_OTHER_COUNTY': 'NAME_OTHER_COUNTY', 'CANDIDATE_COUNTY_FUEL_CAPACITY': 'CAPACITY_CANDIDATE'}.get(st, st)
        confirmed_name = st.startswith('MATCH')
        multi = len(cp) + len(mp) > 2 or any(c['phase_class'] == 'FUTURE' for c in cp)
        # aggregate pass: old multi-unit plants whose unit years differ between the ERCOT and EIA records - the remaining HIST
        # phases of both sides are compared as one block (covers history only; never produces a reclass candidate)
        agg_c = [i for i, c in enumerate(cp) if i not in pr and c['phase_class'] == 'HIST']
        agg_m = [j for j, m_ in enumerate(mp) if j not in pr.values() and m_['model_set'] == 'active2025']
        agg_ok = bool(confirmed_name and agg_c and agg_m and
                      RATIO_LO <= sum(cp[i]['MW'] for i in agg_c) / max(sum(mp[j]['MW'] for j in agg_m), 1e-9) <= RATIO_HI)
        paired_m = set(pr.values()) | (set(agg_m) if agg_ok else set())
        for i, c in enumerate(cp):
            j = pr.get(i)
            m = mp[j] if j is not None else None
            if m is None and agg_ok and i in agg_c:
                first = i == agg_c[0]                 # the aggregate block's model units are listed once (on its first CDR phase)
                m = dict(model_set='active2025', year=None, MW=sum(mp[k]['MW'] for k in agg_m) if first else 0.0,
                         nameplate=sum(mp[k]['nameplate'] for k in agg_m) if first else 0.0,
                         idx=[x for k in agg_m for x in mp[k]['idx']] if first else [], aggregate=True)
            if c['phase_class'] == 'HIST':
                if not confirmed_name:
                    act = 'UNRESOLVED_CANDIDATE_IDENTITY'
                elif m is None:
                    act = 'MIXED_PHASE_REVIEW' if multi else 'UNRESOLVED_PHASE'
                elif m['model_set'] == 'active2025':
                    act = 'NONE_HISTORICAL_PHASE_COVERED' + ('_AGGREGATE' if m.get('aggregate') else '')
                elif 'active2025' in m['model_set']:
                    act = 'NONE_HISTORICAL_PHASE_COVERED_PARTLY'      # paired start year holds active and non-active units
                elif set(c['status_classes']) == {'COMMERCIAL_OPER'}:
                    act = 'REVIEW_RECLASS_CANDIDATE'
                else:
                    act = 'STATUS_QUALIFIED_REVIEW'
            else:
                act = 'NONE_FUTURE_NOT_PAIRED' if m is None else ('NONE_FUTURE_CONSISTENT' if 'active2025' not in m['model_set'] else 'STATUS_CONFLICT_REVIEW')
            x = cu.loc[c['idx']]
            mx = db.loc[m['idx']] if m is not None else db.iloc[0:0]
            rows.append(dict(
                side='CDR_PHASE', cdr_group_key='|'.join([ck[0], ck[1], ' '.join(ck[2])]), model_group_key='|'.join([rk[0], rk[1], ' '.join(rk[2])]) if rk else '',
                family=ck[1], identity_match=name_tier if m is not None or not confirmed_name else f'{name_tier}+PHASE_UNPAIRED',
                phase_match=('HIST_AGGREGATE_PAIRED' if m.get('aggregate') else 'PHASE_PAIRED') if m is not None else 'PHASE_UNPAIRED',
                phase_class=c['phase_class'], phase_year=c['year'],
                historical_status=';'.join(c['status_classes']), cdr_statuses=';'.join(c['statuses']),
                date_classes=';'.join(sorted(set(x.date_class))), cdr_published=CDR_PUBLISHED,
                capacity_basis='CDR installed MW vs ReEDS summer MW (nameplate given) - different ratings, MW gap is not new capacity',
                reclass_action=act, cdr_MW=c['MW'], model_set=m['model_set'] if m else '', model_start_year=m['year'] if m else None,
                model_summer_MW=m['MW'] if m else 0.0, model_nameplate_MW=m['nameplate'] if m else 0.0,
                cdr_unit_names='; '.join(x['UNIT NAME'].astype(str)), cdr_unit_codes='; '.join(x['UNIT CODE'].fillna('').astype(str)),
                cdr_source_rows='; '.join(x.source_excel_row.astype(str)),
                cdr_inr='; '.join(sorted(set(x['INTERCONNECTION REQUEST  NUMBER (INR)'].dropna().astype(str)))),
                cdr_in_service='; '.join(sorted(set(x['IN-SERVICE DATE'].dropna().astype(str)))),
                eia_plant_ids='; '.join(sorted(set(mx.T_PID.astype(str)))), reeds_unique_ids='; '.join(mx['Unique ID'].astype(str)),
                reeds_status='; '.join(sorted(set(mx.status.astype(str)))), name_match_note=note))
        for j, m in enumerate(mp):
            if j in paired_m:
                continue
            mx = db.loc[m['idx']]
            reason = noncore_reason(cu) if m['model_set'] == 'active2025' else ''
            rows.append(dict(side='MODEL_PHASE_UNPAIRED', cdr_group_key='|'.join([ck[0], ck[1], ' '.join(ck[2])]),
                             model_group_key='|'.join([rk[0], rk[1], ' '.join(rk[2])]), family=ck[1], identity_match=f'{name_tier}+PHASE_UNPAIRED',
                             phase_match='PHASE_UNPAIRED', phase_class='MODEL_' + m['model_set'], phase_year=m['year'], historical_status='',
                             capacity_basis='ReEDS summer MW', reclass_action='MODEL_ACTIVE_NO_CDR_HISTORICAL_PHASE' if m['model_set'] == 'active2025' else 'NONE_MODEL_NON_ACTIVE',
                             noncore_reason=reason, cdr_MW=0.0, model_set=m['model_set'], model_start_year=m['year'], model_summer_MW=m['MW'],
                             model_nameplate_MW=m['nameplate'], eia_plant_ids='; '.join(sorted(set(mx.T_PID.astype(str)))),
                             reeds_unique_ids='; '.join(mx['Unique ID'].astype(str)), reeds_status='; '.join(sorted(set(mx.status.astype(str)))),
                             model_plant_names='; '.join(sorted(set(mx.T_PNM.astype(str)))), name_match_note=note))
    ph = pd.DataFrame(rows)
    return ph


def switchable_ledger(u, res, db):
    s = u[u['CDR RESOURCE ATTRIBUTE'].isin(['SWGR-AVA', 'SWGR-UNA'])].copy()
    s['row_type'] = np.where(s['CDR RESOURCE ATTRIBUTE'] == 'SWGR-AVA', 'PHYSICAL_UNIT', 'UNAVAILABLE_ADJUSTMENT')
    s['base_code'] = s['UNIT CODE'].astype(str).str.replace(r'_UNAVAIL$', '', regex=True)
    s['station_key'] = s.key.map(' '.join)
    phys = set(s[s.row_type == 'PHYSICAL_UNIT'].base_code)
    s['adjustment_paired_with_physical'] = np.where(s.row_type == 'UNAVAILABLE_ADJUSTMENT', s.base_code.isin(phys), None)
    adj_by = s[s.row_type == 'UNAVAILABLE_ADJUSTMENT'].groupby('base_code').MW.sum()
    s['unit_unavailable_adj_MW'] = np.where(s.row_type == 'PHYSICAL_UNIT', s.base_code.map(adj_by).fillna(0.0), np.nan)
    s['unit_net_MW'] = np.where(s.row_type == 'PHYSICAL_UNIT', s.MW + s.unit_unavailable_adj_MW, np.nan)
    agg = db.groupby('gkey').agg(model_summer=('summer_power_capacity_MW', 'sum'), model_active=('summer_power_capacity_MW', lambda v: float(v[db.loc[v.index, 'model_set'] == 'active2025'].sum())),
                                 model_names=('T_PNM', lambda v: '; '.join(sorted(set(v)))))
    st = []
    for k, g in s.groupby('station_key'):
        phy, adj = g[g.row_type == 'PHYSICAL_UNIT'], g[g.row_type == 'UNAVAILABLE_ADJUSTMENT']
        gk = phy.gkey.iloc[0] if len(phy) else adj.gkey.iloc[0]
        stt, rk, _, _ = res.get(gk, ('NOT_MATCHED', None, 0, ''))
        st.append(dict(station=k, county=g.county.iloc[0], physical_units=len(phy), physical_MW=float(phy.MW.sum()),
                       unavailable_adjustment_rows=len(adj), unavailable_adjustment_MW=float(adj.MW.sum()),
                       snapshot_net_MW=float(phy.MW.sum() + adj.MW.sum()),
                       adjustments_unpaired=int((~adj.base_code.isin(phys)).sum()),
                       model_match_status=stt, model_group=' '.join(rk[2]) + f' ({rk[0]})' if rk else '',
                       model_active2025_summer_MW=float(agg.model_active.get(rk, 0.0)) if rk else 0.0,
                       model_plant_names=agg.model_names.get(rk, '') if rk else '',
                       comparability='physical = installed MW of SWGR-AVA rows; adjustment = SWGR-UNA rows (negative, unavailable to ERCOT at the snapshot), '
                                     'paired once by base UNIT CODE; net is an audit figure only - not a reliability certification and not a model replacement value'))
    return s, pd.DataFrame(st).sort_values('physical_MW', ascending=False)


def match_confidence(u, db, ph, res):
    """coverage by identity tier, units and MW, with explicit denominators"""
    cdr = ph[ph.side == 'CDR_PHASE']
    uh = u[u.core_2025 & ~u.is_adjustment_row].copy()
    tier = {}
    for r in cdr.itertuples():
        for nm in str(r.cdr_unit_names).split('; '):
            pass
    # unit -> phase tier (by group key + year + class)
    key = lambda gk, cls, yr: (gk, cls, -1 if yr is None or (isinstance(yr, float) and np.isnan(yr)) else int(yr))
    pmap = {key(r.cdr_group_key, r.phase_class, r.phase_year): (r.identity_match, r.phase_match) for r in cdr.itertuples()}
    suffix = {'PHASE_PAIRED': '+PHASE_PAIRED', 'HIST_AGGREGATE_PAIRED': '+HIST_AGGREGATE_PAIRED'}
    uh['gk_s'] = ['|'.join([g[0], g[1], ' '.join(g[2])]) for g in uh.gkey]
    uh['tier'] = [pmap.get(key(g, c, y), ('UNRESOLVED', 'PHASE_UNPAIRED'))[0] for g, c, y in zip(uh.gk_s, uh.phase_class, uh.in_service_year)]
    uh['phase'] = [pmap.get(key(g, c, y), ('UNRESOLVED', 'PHASE_UNPAIRED'))[1] for g, c, y in zip(uh.gk_s, uh.phase_class, uh.in_service_year)]
    uh['tier_full'] = [t if ('PHASE_UNPAIRED' in t or t in ('AMBIGUOUS', 'UNMATCHED', 'UNRESOLVED')) else t + suffix.get(p_, '') for t, p_ in zip(uh.tier, uh.phase)]
    rows = []
    for denom, sel in (('CDR core 2025 incl. qualified (OPER/RMR + OPER-SYN/UNFC/UNR), installed MW', uh),
                       ('CDR core 2025 commercial only (OPER/RMR), installed MW', uh[uh.status_class == 'COMMERCIAL_OPER'])):
        tot_n, tot_mw = len(sel), float(sel.MW.sum())
        for t, g in sel.groupby('tier_full'):
            rows.append(dict(side='CDR', denominator=denom, identity_tier=t, units=len(g), MW=float(g.MW.sum()), share_units=len(g) / tot_n, share_MW=float(g.MW.sum()) / tot_mw))
        rows.append(dict(side='CDR', denominator=denom, identity_tier='ID_CONFIRMED (ERCOT UNIT CODE <-> EIA ID crosswalk)', units=0, MW=0.0, share_units=0.0, share_MW=0.0,
                         note='no crosswalk available: no unit is ID-confirmed; name tiers are candidates of decreasing strength'))
    act = db[db.model_set == 'active2025'].copy()
    paired_ids = set()
    for r in cdr[cdr.phase_match.isin(['PHASE_PAIRED', 'HIST_AGGREGATE_PAIRED']) & cdr.model_set.str.contains('active2025')].itertuples():
        paired_ids |= set(str(r.reeds_unique_ids).split('; '))
    tier_of = {}
    for r in cdr[cdr.phase_match.isin(['PHASE_PAIRED', 'HIST_AGGREGATE_PAIRED'])].itertuples():
        for i in str(r.reeds_unique_ids).split('; '):
            tier_of[i] = r.identity_match + ('+PHASE_PAIRED' if r.phase_match == 'PHASE_PAIRED' else '+HIST_AGGREGATE_PAIRED')
    act['tier'] = [tier_of.get(str(i), 'UNPAIRED_OR_UNMATCHED') for i in act['Unique ID']]
    tot = float(act.summer_power_capacity_MW.sum())
    for t, g in act.groupby('tier'):
        rows.append(dict(side='MODEL', denominator='model active 2025 (ReEDS OP/SB, Start<=2025<Retire), summer MW', identity_tier=t, units=len(g),
                         MW=float(g.summer_power_capacity_MW.sum()), share_units=len(g) / len(act), share_MW=float(g.summer_power_capacity_MW.sum()) / tot))
    return pd.DataFrame(rows), uh


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    db, cbasis = A.model_units()
    u = cdr_frame()
    m, res, used, agg = A.generator_match(u, db)
    ph = reconcile(u, db, res)
    sw_rows, sw = switchable_ledger(u, res, db)
    conf, uh = match_confidence(u, db, ph, res)
    # revised reclassification: the old v1.3 suggestion set, phase by phase
    old = pd.read_csv(OLD / 'C0_PIPELINE_RECLASS_SUGGESTIONS.csv')
    old_set = old[old.direction.str.startswith('CDR_OPERATING')]
    cdr = ph[ph.side == 'CDR_PHASE']
    rv = cdr[cdr.cdr_group_key.isin(old_set.cdr_group_key) & (cdr.phase_class == 'HIST')].copy()
    rv['old_v13_group_cdr_core_2025_MW'] = rv.cdr_group_key.map(old_set.set_index('cdr_group_key').cdr_core_2025_MW)
    rv['old_v13_label'] = 'v1.3 park-level rule: CDR core > 0 and model committed > 0 (to be reviewed; not a confirmed omission)'
    rv['set'] = 'OLD_V13_SUGGESTION_SET'
    new_cand = cdr[cdr.reclass_action.isin(['REVIEW_RECLASS_CANDIDATE'])].copy()
    new_cand['set'] = 'V14_PHASE_LEVEL_CANDIDATES'
    revised = pd.concat([rv, new_cand], ignore_index=True)
    # model active without CDR historical phase (the v1.3 ~6.37 GW "model active, CDR non-core")
    nc = ph[(ph.side == 'MODEL_PHASE_UNPAIRED') & (ph.model_set == 'active2025')]
    ncb = nc.groupby(['noncore_reason', 'family']).agg(phases=('model_summer_MW', 'size'), model_summer_MW=('model_summer_MW', 'sum')).reset_index()
    ncb['note'] = 'flags for review, not deletions'
    # bridge with corrected labels (arithmetic unchanged)
    bridge, ident = A.capacity_bridge(u, db, m, res, agg)
    bridge = bridge.replace({'component': {'decomp_rating_diff': 'decomp_matched_group_capacity_diff',
                                           'decomp_pipeline_cross': 'decomp_park_level_pipeline_overlap'}})
    bridge.loc[bridge.component == 'decomp_matched_group_capacity_diff', 'basis'] = (
        'matched name groups: CDR installed - model summer; MIXES rating basis (installed vs summer) AND phase coverage differences; '
        'not attributable to rating alone without unit / phase evidence')
    bridge.loc[bridge.component == 'decomp_park_level_pipeline_overlap', 'basis'] = (
        'park-level overlap of CDR 2025 core (incl. OPER-SYN) and model committed MW - NOT a reclass finding; see C0_PHASE_RECONCILIATION')
    bridge['note_v14'] = 'identity closure proves ledger arithmetic only, not unit identity or the cause of differences'
    # before / after
    v13 = json.loads((OLD / 'C0_QA.json').read_text())
    acts = rv.groupby('reclass_action').cdr_MW.sum()
    kiam = sw[sw.station.str.contains('KIAMICHI')].iloc[0]
    ba = [dict(metric='old_v13_cdr_operating_model_committed_MW', v13=v13['pipeline_reclass_suggestions']['cdr_operating_model_committed_MW'],
               v14=float(old_set.cdr_core_2025_MW.sum()), note='v1.4 name: total flagged by the old park-level rule (to be reviewed)')]
    for a_, v in acts.items():
        ba.append(dict(metric=f'old_set_phase_MW__{a_}', v13=None, v14=float(v), note='HIST phases of the old suggestion groups, by v1.4 action'))
    ba += [dict(metric='v14_REVIEW_RECLASS_CANDIDATE_MW_all_groups', v13=None, v14=float(new_cand.cdr_MW.sum()), note='commercial OPER/RMR phase paired with a model phase outside the 2025 fleet'),
           dict(metric='v14_REVIEW_RECLASS_CANDIDATE_phases', v13=None, v14=int(len(new_cand)), note=''),
           dict(metric='cdr_core_name_matched_MW_share', v13=v13['coverage']['cdr_core_match_share_MW'], v14=float(conf[(conf.side == 'CDR') & conf.denominator.str.contains('incl') & conf.identity_tier.str.startswith('NAME') & conf.identity_tier.str.endswith('PHASE_PAIRED')].share_MW.sum()),
                note='v1.3 = name-group match; v1.4 = name match AND phase pairing (still not ID-confirmed)'),
           dict(metric='kiamichi_physical_MW', v13=None, v14=float(kiam.physical_MW), note='SWGR-AVA rows'),
           dict(metric='kiamichi_unavailable_adjustment_MW', v13=None, v14=float(kiam.unavailable_adjustment_MW), note='SWGR-UNA rows'),
           dict(metric='kiamichi_snapshot_net_MW', v13=None, v14=float(kiam.snapshot_net_MW), note='audit net only'),
           dict(metric='kiamichi_model_active2025_summer_MW', v13=None, v14=float(kiam.model_active2025_summer_MW), note='model value unchanged'),
           dict(metric='model_active_without_cdr_historical_phase_MW', v13=float(v13['coverage']['model_active_MW'] - 0) and None, v14=float(nc.model_summer_MW.sum()),
                note='broken down by reason in C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv (v1.3: ~6.37 GW model-matched-noncore at group level)')]
    w = lambda df, nm: df.to_csv(OUT / nm, index=False, lineterminator='\n', float_format='%.6f')
    w(ph, 'C0_PHASE_RECONCILIATION.csv'); w(revised, 'C0_RECLASS_REVISED.csv'); w(sw, 'C0_SWITCHABLE_LEDGER.csv')
    w(sw_rows.drop(columns=['gkey', 'key']), 'C0_SWITCHABLE_UNIT_ROWS.csv'); w(conf, 'C0_MATCH_CONFIDENCE.csv')
    w(ncb, 'C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv'); w(bridge, 'C0_CAPACITY_BRIDGE_V14.csv'); w(pd.DataFrame(ba), 'C0_REPAIR_BEFORE_AFTER.csv')
    real = {}
    for k in ('CALLISTO', 'TIDWELL', 'PADUA'):
        x = cdr[cdr.cdr_group_key.str.contains(k)]
        real[k] = dict(phases=x[['phase_class', 'phase_year', 'cdr_MW', 'model_set', 'model_summer_MW', 'reclass_action']].to_dict('records'))
    qa = dict(stage='C0 repair v1.4 (stage A)', solver_executions=0, v13_snapshot_untouched_sha256={p.name: sha(p) for p in sorted(OLD.glob('C0_*'))},
              phase_rows=len(ph), real_cases=real,
              no_reclass_for_real_cases=all(not any(p['reclass_action'] in ('REVIEW_RECLASS_CANDIDATE', 'STATUS_QUALIFIED_REVIEW') and p['phase_class'] == 'FUTURE' for p in v['phases']) for v in real.values()),
              old_total_MW=float(old_set.cdr_core_2025_MW.sum()), old_set_by_action={k: float(v) for k, v in acts.items()},
              v14_review_reclass_candidates_MW=float(new_cand.cdr_MW.sum()),
              switchable=dict(stations=len(sw), physical_MW=float(sw.physical_MW.sum()), adjustment_MW=float(sw.unavailable_adjustment_MW.sum()),
                              unpaired_adjustments=int(sw.adjustments_unpaired.sum()), kiamichi=kiam[['physical_MW', 'unavailable_adjustment_MW', 'snapshot_net_MW', 'model_active2025_summer_MW']].to_dict()),
              id_confirmed_units=0, capacity_bridge_identity_ok=bool(ident),
              noncore_breakdown_MW=ncb.groupby('noncore_reason').model_summer_MW.sum().round(1).to_dict(),
              outputs={p.name: sha(p) for p in sorted(OUT.glob('C0_*.csv'))})
    (OUT / 'C0_REPAIR_QA.json').write_bytes((json.dumps(qa, indent=1, default=str) + '\n').encode())
    print(json.dumps({k: qa[k] for k in ('real_cases', 'no_reclass_for_real_cases', 'old_total_MW', 'old_set_by_action', 'v14_review_reclass_candidates_MW', 'switchable', 'noncore_breakdown_MW')}, indent=1, default=str))
    print(conf[conf.denominator.str.contains('incl') | (conf.side == 'MODEL')][['side', 'identity_tier', 'units', 'MW', 'share_MW']].round(4).to_string())


if __name__ == '__main__':
    main()
