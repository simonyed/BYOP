"""BYOP calibration close-out v1.6 (2026-10-22): asset decisions and switchable caps for the 2025 baseline, as pure functions
(no network, no solver) shared by build_2025_baseline_tamu.py, the PRM bridge and the tests.

Decisions (inputs/calibration_v16/ASSET_DECISIONS.csv, by ReEDS Unique ID; the ReEDS source table is never edited):
  KEEP_IN_2025_FLEET                                 must already be active 2025; no change (verified)
  MOVE_2025_FLEET_TO_2026_COMMITTED_PIPELINE         StartYear -> 2026, status -> '(TS) v1.6 override' (committed pipeline)
  ACTIVATE_EXISTING_2025_RECORD                      status -> '(OP) v1.6 override' (StartYear / RetireYear kept)
  MOVE_EXISTING_150_MW_RECORD_FROM_PIPELINE_TO_2025  StartYear -> 2025, status -> '(OP) v1.6 override' (MWh, duration kept)
  KEEP_PHYSICAL_AND_APPLY_MONTHLY_AGGREGATE_ERCOT_CAP plant kept at its physical summer MW, split out of the bus aggregation
                                                     and given p_max_pu(t) = min(physical, MORA net)_month / physical
Active 2025 = status OP / SB and StartYear <= 2025 < RetireYear; committed = U / V / TS (same rule as the builder).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TECH_MAP = {'gas-cc': 'CCGT', 'gas-ct': 'OCGT', 'o-g-s': 'gas_steam', 'coaloldscr': 'coal', 'coal-new': 'coal',
            'coaloldunscr': 'coal', 'nuclear': 'nuclear', 'upv': 'solar', 'pvb_pv': 'solar', 'wind-ons': 'onwind',
            'battery_li': 'battery', 'hydEND': 'hydro', 'hydED': 'hydro', 'biopower': 'biomass',
            'lfill-gas': 'biomass', 'pumped-hydro': 'battery'}
FAMILY = {'gas-cc': 'gas', 'gas-ct': 'gas', 'o-g-s': 'gas', 'upv': 'solar', 'pvb_pv': 'solar', 'wind-ons': 'wind',
          'battery_li': 'storage', 'pumped-hydro': 'storage'}
DECISION_FAMILY = {'Kiamichi': 'gas', 'Tenaska Gateway': 'gas', 'Pyron wind': 'wind', 'Danish Fields Storage': 'storage',
                   'Myrtle Storage': 'storage'}
SWITCH = 'KEEP_PHYSICAL_AND_APPLY_MONTHLY_AGGREGATE_ERCOT_CAP'


def model_set(status, start, retire):
    st = str(status)[:4]
    if st in ('(OP)', '(SB)') and start <= 2025 < retire:
        return 'active2025'
    if st in ('(U) ', '(V) ', '(TS)'):
        return 'committed'
    return 'not_in_model'


def classify(db):
    db = db.copy()
    db['model_set'] = [model_set(s, a, r) for s, a, r in zip(db.status, db.StartYear, db.RetireYear)]
    return db


def decision_ids(d):
    return {int(x): r.item for r in d.itertuples() for x in str(r.reeds_unique_id).split(';')}


def apply_overrides(db, decisions):
    """returns (db with overrides, audit rows); raises on any ID / technology / capacity mismatch"""
    db = classify(db).set_index('Unique ID', drop=False)
    before = db.copy()
    audit = []
    for r in decisions.itertuples():
        ids = [int(x) for x in str(r.reeds_unique_id).split(';')]
        missing = [i for i in ids if i not in db.index]
        if missing:
            raise ValueError(f'{r.item}: ReEDS Unique ID {missing} not in the ERCOT generator database')
        x = db.loc[ids]
        mw = float(x.summer_power_capacity_MW.sum())
        if abs(mw - float(r.physical_summer_MW)) > 0.05:
            raise ValueError(f'{r.item}: summer MW {mw} != decision {r.physical_summer_MW}')
        fam = DECISION_FAMILY.get(r.item, 'solar' if 'solar' in r.item.lower() or r.item in ('Sequoia phase 1', 'Fagus', 'Buzios / Roaring Springs',
                                                                                          'Long Point') else 'wind' if r.item == 'La Casa' else None)
        if fam and not set(x.tech.map(FAMILY)) <= {fam}:
            raise ValueError(f'{r.item}: technology {sorted(set(x.tech))} does not match {fam}')
        a = r.action
        for i in ids:
            if a == 'KEEP_IN_2025_FLEET' or a == SWITCH:
                if db.at[i, 'model_set'] != 'active2025':
                    raise ValueError(f'{r.item} {i}: expected active2025, found {db.at[i, "model_set"]}')
            elif a == 'MOVE_2025_FLEET_TO_2026_COMMITTED_PIPELINE':
                db.at[i, 'StartYear'] = 2026; db.at[i, 'status'] = '(TS) v1.6 override: moved to 2026 committed pipeline'
            elif a == 'ACTIVATE_EXISTING_2025_RECORD':
                db.at[i, 'status'] = '(OP) v1.6 override: activated for 2025'
            elif a == 'MOVE_EXISTING_150_MW_RECORD_FROM_PIPELINE_TO_2025':
                db.at[i, 'StartYear'] = 2025; db.at[i, 'status'] = '(OP) v1.6 override: in 2025 fleet (ERCOT CDR OPER + 2025 MORA)'
            else:
                raise ValueError(f'unknown action {a}')
    db = classify(db.reset_index(drop=True)).set_index('Unique ID', drop=False)
    for r in decisions.itertuples():
        for i in [int(x) for x in str(r.reeds_unique_id).split(';')]:
            b, n_ = before.loc[i], db.loc[i]
            audit.append(dict(item=r.item, action=r.action, reeds_unique_id=i, eia_plant_id=int(b.T_PID), plant_name=b.T_PNM, tech=b.tech,
                              summer_MW=float(b.summer_power_capacity_MW), energy_MWh=float(b.energy_capacity_MWh) if pd.notna(b.energy_capacity_MWh) else None,
                              status_before=b.status, status_after=n_.status, start_before=int(b.StartYear), start_after=int(n_.StartYear),
                              set_before=b.model_set, set_after=n_.model_set, source_basis=r.source_basis, limitation=r.remaining_limitation))
    for i in set(db.index) - set(decision_ids(decisions)):                  # nothing else moved
        assert db.at[i, 'model_set'] == before.at[i, 'model_set']
    return db.reset_index(drop=True), pd.DataFrame(audit)


def fleet_delta(db_before, db_after):
    """physical fleet change by carrier and set (MW), and a duplicate check (each Unique ID in exactly one set)"""
    a = classify(db_before).assign(carrier=lambda d: d.tech.map(TECH_MAP))
    b = db_after.assign(carrier=lambda d: d.tech.map(TECH_MAP))
    pa = a.groupby(['model_set', 'carrier']).summer_power_capacity_MW.sum()
    pb = b.groupby(['model_set', 'carrier']).summer_power_capacity_MW.sum()
    out = pd.DataFrame(dict(before_MW=pa, after_MW=pb)).fillna(0.0)
    out['delta_MW'] = out.after_MW - out.before_MW
    assert b['Unique ID'].is_unique
    return out.reset_index()


def month_of_3h_steps(native_1h):
    """2025 source month of each 3 h model step (row order: step k = source rows 3k..3k+2; month of the middle row)"""
    m = native_1h['Hour Ending'].astype(str).str.slice(0, 2).astype(int).values
    assert len(m) == 8760
    return m.reshape(2920, 3)[:, 1]


def switchable_caps(caps, plant_mw):
    """monthly aggregate cap per plant = min(physical summer MW, MORA net ERCOT MW); returns DataFrame month x item"""
    c = caps.pivot_table(index='month', columns='item', values='mora_net_ercot_MW')
    assert list(c.index) == list(range(1, 13)), 'need 12 months'
    out = pd.DataFrame({it: np.minimum(c[it].values, plant_mw[it]) for it in c.columns}, index=c.index)
    rec = caps.pivot_table(index='month', columns='item', values='recommended_aggregate_dispatch_cap_MW')
    assert np.allclose(out.values, rec[out.columns].values), 'cap != package recommended_aggregate_dispatch_cap_MW'
    return out


def p_max_pu_series(cap_month, months, p_nom):
    return np.array([cap_month[mm] for mm in months]) / float(p_nom)
