#!/usr/bin/env python3
"""BYOP calibration close-out v1.6: official 2025 PRM reproduction and same-scope model bridge (no solver, read-only network).
    python byop/post/v16_prm_bridge.py [--network results/BYOP/baseline_2025_tamu_v16/baseline_2025_tamu_prepared.nc]
Writes <v16 dir>/RELIABILITY_ANCHOR_BRIDGE.csv and PRM_BRIDGE_SUMMARY.json.

Rows (column row_type):
  OFFICIAL   every December 2024 Revised CDR (published 2025-02) summer component, unchanged, by category; PRM recomputed from
             numerator / denominator for the peak-load (18.899 %) and peak-net-load (10.472 %) risk periods.
  MODEL      the v1.6 2025 fleet (ReEDS + audited overrides, year-end 2025 physical MW) on the same scope: CDR ELCC of the matching
             risk period (peak_load -> summer_afternoon, peak_net_load -> summer_evening); storage by each unit's own duration
             (linear interpolation of the BESS 1-12 h rows); wind / solar by CDR region from the unit county (Coastal / Panhandle
             county rule; Far West / West = the builder's weather-zone assignment of the county); thermal at summer MW without
             the switchable plants; switchable at the v1.6 monthly cap of the risk-period month (counted once); hydro at the
             network hydro availability of the risk-period steps. DR / load resources, private-use networks, RMR, mothballed,
             DC ties: explicitly NOT MODELLED (0), never filled with virtual capacity.
  BRIDGE     official -> model step by step (category capacity difference, then load basis); PRM after each step on the
             official firm load, the last step on the model 2025 native peak. resolution says what each step is.
  ERM        the model's per-snapshot energy-backed ERM rows (15 % ERM, ERM-02 B period margins): a model deliverability
             constraint, NOT the official PRM and not calibrated to it.
The official numbers are a published 2025 FORECAST including eligible planned resources, not observed 2025 adequacy.
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/build'))
import byop_paths as BP  # noqa: E402
import baseline_v16_assets as A16  # noqa: E402

EV = BP.CALIB_V16_EVIDENCE
RISK = {'peak_load': 'summer_afternoon', 'peak_net_load': 'summer_evening'}
# CDR summer summary rows -> bridge category
ROWCAT = {24: 'thermal', 25: 'hydro', 26: 'switchable', 27: 'switchable', 28: 'mothballed', 29: 'private_use_networks',
          31: 'wind_coastal', 32: 'wind_panhandle', 33: 'wind_other', 34: 'solar_farwest', 35: 'solar_west', 36: 'solar_other',
          37: 'storage', 38: 'rmr', 39: 'pending_retirement', 42: 'dc_ties', 45: 'thermal', 47: 'wind_coastal', 48: 'wind_panhandle',
          49: 'wind_other', 50: 'solar_farwest', 51: 'solar_west', 52: 'solar_other', 53: 'storage', 54: 'pending_retirement'}
PLANNED_ROWS = set(range(45, 55))
SUBTOTAL_ROWS = {17: 'firm_load', 40: 'operational_total', 55: 'planned_total', 56: 'total_capacity', 58: 'reserve_margin', 19: 'memo_EE'}
LOAD_ROWS = range(8, 17)
ELCC_KEY = {'wind_coastal': 'Wind - Coastal', 'wind_panhandle': 'Wind - Panhandle', 'wind_other': 'Wind - Other',
            'solar_farwest': 'Solar - FarWest', 'solar_west': 'Solar - West', 'solar_other': 'Solar - Other'}
# ERCOT CDR wind regions by county (TX county FIPS); proxy membership lists, reported as such
COASTAL = {'48007', '48039', '48057', '48061', '48261', '48273', '48321', '48355', '48391', '48409', '48489'}   # Aransas Brazoria Calhoun Cameron Kenedy Kleberg Matagorda Nueces Refugio San Patricio Willacy
PANHANDLE = {'48011', '48045', '48065', '48069', '48075', '48087', '48111', '48117', '48129', '48179', '48191', '48195',
             '48205', '48211', '48233', '48295', '48341', '48357', '48359', '48369', '48375', '48381', '48393', '48421',
             '48437', '48483'}   # the 26 Texas Panhandle counties
NOT_MODELLED = {'mothballed', 'private_use_networks', 'rmr', 'pending_retirement', 'dc_ties'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def official(comp, prm):
    rows = []
    for rp in RISK:
        x = comp[(comp.season == 'Summer') & (comp.risk_period == rp)].set_index('excel_row')
        load = x.loc[list(LOAD_ROWS)]
        firm = float(load.value.sum())
        caps = x.loc[[r for r in x.index if r in ROWCAT]]
        num = float(caps.value.sum())
        p_ref = prm[prm.risk_period == rp].iloc[0]
        for r, v in x.iterrows():
            rows.append(dict(row_type='OFFICIAL', risk_period=rp, elcc_period=RISK[rp], excel_row=int(r), label=v.label,
                             category=ROWCAT.get(r, SUBTOTAL_ROWS.get(r, 'load_component' if r in LOAD_ROWS else 'other')),
                             resource_status='planned' if r in PLANNED_ROWS else ('operational' if r in ROWCAT else ''),
                             official_MW=float(v.value), source=f'{v.source_file} / {v.source_sheet} / {v.excel_column}{int(r)}'))
        q = dict(firm_load_from_components=firm, firm_load_cell=float(x.value[17]), credited_from_components=num,
                 credited_cell=float(x.value[56]), prm_recomputed=(num - firm) / firm, prm_cell=float(x.value[58]),
                 prm_reference=float(p_ref.prm_fraction))
        q['reproduced'] = bool(abs(q['prm_recomputed'] - q['prm_reference']) < 1e-9 and abs(firm - q['firm_load_cell']) < 1e-6
                               and abs(num - q['credited_cell']) < 1e-6)
        rows.append(dict(row_type='OFFICIAL', risk_period=rp, elcc_period=RISK[rp], category='PRM_RECOMPUTED', official_MW=num,
                         firm_load_MW=firm, prm=q['prm_recomputed'], note=json.dumps(q)))
        assert q['reproduced'], q
    return rows


def model_units(out):
    db = pd.read_csv(BP.REEDS_GENDB, low_memory=False)
    db = db[db.T_PCA.astype(str).str.strip() == 'ERCO']
    db = db[db.tech.map(A16.TECH_MAP).notna()].copy()
    dec = pd.read_csv(BP.CALIB_V16_INPUTS / 'ASSET_DECISIONS.csv', encoding='utf-8-sig')
    db, _ = A16.apply_overrides(db, dec)
    u = db[db.model_set == 'active2025'].copy()
    u['carrier'] = u.tech.map(A16.TECH_MAP)
    u['GEOID'] = u.FIPS.astype(str).str.replace('p', '').str.zfill(5)
    shares = out / 'COUNTY_TO_BUS_SHARES.csv'
    sh = pd.read_csv(shares if shares.exists() else BP.BASE_TAMU_DIR / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
    wz = sh.drop_duplicates('GEOID').set_index('GEOID').wz
    u['weather_zone'] = u.GEOID.map(wz).fillna('outside_ERCOT_county_table')
    sw = {int(x): r.item for r in dec[dec.action == A16.SWITCH].itertuples() for x in str(r.reeds_unique_id).split(';')}
    u['switchable_item'] = u['Unique ID'].map(sw)

    def cat(r):
        if isinstance(r.switchable_item, str):
            return 'switchable'
        if r.carrier in ('CCGT', 'OCGT', 'gas_steam', 'coal', 'nuclear', 'biomass'):
            return 'thermal'
        if r.carrier == 'hydro':
            return 'hydro'
        if r.carrier == 'battery':
            return 'storage'
        if r.carrier == 'onwind':
            return 'wind_coastal' if r.GEOID in COASTAL else 'wind_panhandle' if r.GEOID in PANHANDLE else 'wind_other'
        if r.carrier == 'solar':
            return 'solar_farwest' if r.weather_zone == 'FWEST' else 'solar_west' if r.weather_zone == 'WEST' else 'solar_other'
        return 'other'
    u['category'] = [cat(r) for r in u.itertuples()]
    return u


def bess_elcc(elcc, period, hours):
    b = elcc[elcc.resource_type.str.startswith('BESS') & (elcc.risk_period == period)].copy()
    b['h'] = b.resource_type.str.extract(r'([\d.]+) hr').astype(float)
    b = b.sort_values('h')
    return np.interp(np.clip(hours, b.h.min(), b.h.max()), b.h.values, b.capacity_credit.values)


def risk_steps(n, months):
    """model risk-period steps: the 3 h step of the peak load and of the peak net load (load - wind - solar availability)"""
    load = n.loads_t.p_set.sum(axis=1)
    g = n.generators
    pm = n.get_switchable_as_dense('Generator', 'p_max_pu')
    vre = [x for x in g.index[g.carrier.isin(['onwind', 'solar']) & ~g.p_nom_extendable & (g.build_year <= 2025)]]
    net = load - (pm[vre] * g.p_nom[vre]).sum(axis=1)
    out = {}
    for rp, ser in (('peak_load', load), ('peak_net_load', net)):
        k = int(np.argmax(ser.values))
        out[rp] = dict(step=k, snapshot=str(ser.index[k]), source_month_2025=int(months[k]), value_MW=float(ser.iloc[k]),
                       load_MW=float(load.iloc[k]))
    return out, load, pm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--network', default=str(BP.BASE_TAMU_V16_DIR / 'baseline_2025_tamu_prepared.nc'))
    ap.add_argument('--out-dir', default=str(BP.BASE_TAMU_V16_DIR))
    a = ap.parse_args()
    import pypsa
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    comp = pd.read_csv(EV / 'CDR_2025_RESOURCE_DEMAND_COMPONENTS.csv', encoding='utf-8-sig')
    prm = pd.read_csv(EV / 'CDR_2025_PRM_REFERENCE.csv', encoding='utf-8-sig')
    elcc = pd.read_csv(EV / 'CDR_2025_ELCC_REFERENCE.csv', encoding='utf-8-sig')
    rows = official(comp, prm)
    u = model_units(out)
    n = pypsa.Network(a.network)
    months = A16.month_of_3h_steps(pd.read_csv(BP.ANCHOR2025_DERIVED / 'ERCOT_NATIVE_LOAD_2025_1H.csv', usecols=['Hour Ending']))
    rs, load, pm = risk_steps(n, months)
    nl = pd.read_csv(BP.ANCHOR2025_DERIVED / 'ERCOT_NATIVE_LOAD_2025_1H.csv')
    capqa = pd.read_csv(out / 'SWITCHABLE_CAP_QA.csv') if (out / 'SWITCHABLE_CAP_QA.csv').exists() else None
    g = n.generators
    hyd = g.index[(g.carrier == 'hydro') & ~g.p_nom_extendable & (g.build_year <= 2025)]
    summary = dict(network=a.network, network_sha256=sha(a.network), risk_steps=rs, native_load_1h_peak_MW=float(nl.ERCOT.max()),
                   native_load_1h_peak_label=str(nl.loc[nl.ERCOT.idxmax(), 'Hour Ending']), native_load_3h_peak_MW=float(load.max()),
                   native_load_TWh=float(nl.ERCOT.sum() / 1e6))
    for rp, per in RISK.items():
        k, mon = rs[rp]['step'], rs[rp]['source_month_2025']
        off = pd.DataFrame([r for r in rows if r['row_type'] == 'OFFICIAL' and r['risk_period'] == rp and r.get('excel_row') in ROWCAT])
        off_cat = off.groupby('category').official_MW.sum()
        firm = [r for r in rows if r['row_type'] == 'OFFICIAL' and r['risk_period'] == rp and r['category'] == 'PRM_RECOMPUTED'][0]
        mrows = {}
        for c_, grp in u.groupby('category'):
            mw = float(grp.summer_power_capacity_MW.sum())
            if c_ == 'thermal':
                cr, basis = mw, 'summer MW x 1.0 (CDR installed summer-rated basis), switchable plants excluded'
            elif c_ == 'switchable':
                if capqa is None:
                    raise SystemExit('SWITCHABLE_CAP_QA.csv missing (run the v1.6 builder first)')
                cr = float(capqa[capqa.month == mon].applied_cap_MW.sum())
                basis = f'v1.6 monthly cap of source month {mon} (Kiamichi + Tenaska Gateway), counted once'
            elif c_ == 'hydro':
                cr = float((pm[hyd].iloc[k] * g.p_nom[hyd]).sum()); basis = f'network hydro p_nom x p_max_pu at the {rp} step'
            elif c_ == 'storage':
                h = (grp.energy_capacity_MWh.fillna(0) / grp.summer_power_capacity_MW).replace(0, 4.0).values
                f = bess_elcc(elcc, per, h)
                cr = float((f * grp.summer_power_capacity_MW.values).sum())
                basis = f'CDR BESS ELCC ({per}) by unit duration, interpolated; mean duration {np.average(h, weights=grp.summer_power_capacity_MW):.2f} h'
            elif c_ in ELCC_KEY:
                f = float(elcc[(elcc.resource_type == ELCC_KEY[c_]) & (elcc.risk_period == per)].capacity_credit.iloc[0])
                cr = mw * f; basis = f'CDR ELCC {ELCC_KEY[c_]} ({per}) = {f:.4f}'
            else:
                cr, basis = 0.0, 'not in the CDR categories'
            mrows[c_] = (mw, cr, basis)
        model_total = 0.0
        for c_ in sorted(set(off_cat.index) | set(mrows)):
            mw, cr, basis = mrows.get(c_, (0.0, 0.0, 'NOT MODELLED: no such resource in the model fleet (left at 0, no virtual capacity)'))
            model_total += cr
            implied = np.nan
            if c_ in ELCC_KEY:
                f = float(elcc[(elcc.resource_type == ELCC_KEY[c_]) & (elcc.risk_period == per)].capacity_credit.iloc[0])
                implied = float(off_cat.get(c_, 0.0)) / f if f > 0 else np.nan
            rows.append(dict(row_type='MODEL', risk_period=rp, elcc_period=per, category=c_, model_physical_MW=mw, model_credited_MW=cr,
                             official_MW=float(off_cat.get(c_, 0.0)), official_implied_installed_MW=implied,
                             delta_credited_MW=cr - float(off_cat.get(c_, 0.0)), basis=basis))
        rows.append(dict(row_type='MODEL', risk_period=rp, elcc_period=per, category='MODEL_CREDITED_TOTAL', model_credited_MW=model_total,
                         firm_load_MW=firm['firm_load_MW'], prm=(model_total - firm['firm_load_MW']) / firm['firm_load_MW'],
                         note='model credited capacity on the OFFICIAL firm load (same denominator)'))
        mpeak = rs[rp]['load_MW'] if rp == 'peak_load' else rs[rp]['load_MW']
        rows.append(dict(row_type='MODEL', risk_period=rp, elcc_period=per, category='MODEL_PRM_ON_NATIVE_LOAD', model_credited_MW=model_total,
                         firm_load_MW=mpeak, prm=(model_total - mpeak) / mpeak,
                         note=f'model credited capacity on the model 2025 native load at the {rp} step ({rs[rp]["snapshot"]}); native load is '
                              'ACTUAL weather / ACTUAL demand and is not confirmed to equal the CDR firm-load concept (load resources, ERS, '
                              'rooftop PV) - a scope comparison, not an adequacy shortfall'))
        # bridge: official -> model
        cum, step = firm['official_MW'], 0
        F = firm['firm_load_MW']
        rows.append(dict(row_type='BRIDGE', risk_period=rp, step=step, category='official', credited_MW=cum, firm_load_MW=F, prm=(cum - F) / F,
                         resolution='OFFICIAL_REPRODUCED'))
        res_of = dict(thermal='CAPACITY_BASIS_DIFFERENCE_UNRESOLVED (ReEDS summer MW of the year-end fleet vs CDR summer-rated incl. planned; PUN units may sit inside model thermal at gross MW)',
                      switchable='EXPLAINED_SCOPE (model: two switchable plants at the monthly MORA cap; CDR: all switchable units net of unavailable)',
                      hydro='EXPLAINED_SCOPE (CDR peak-average contribution vs model profile at the risk step)',
                      storage='ELCC_AND_FLEET_SCOPE (CDR operational + planned credited; model year-end 2025 units at their own-duration ELCC)')
        for c_ in sorted(set(off_cat.index) | set(mrows)):
            d = next(r for r in rows if r['row_type'] == 'MODEL' and r['risk_period'] == rp and r['category'] == c_)
            if abs(d['delta_credited_MW']) < 1e-9:
                continue
            step += 1; cum += d['delta_credited_MW']
            res = 'NOT_MODELLED' if c_ in NOT_MODELLED else res_of.get(c_, 'ELCC_AND_FLEET_SCOPE (CDR operational + planned at CDR ELCC vs model year-end 2025 installed at the same ELCC; difference = installed-MW scope)')
            rows.append(dict(row_type='BRIDGE', risk_period=rp, step=step, category=c_, delta_MW=d['delta_credited_MW'], credited_MW=cum,
                             firm_load_MW=F, prm=(cum - F) / F, resolution=res))
        step += 1
        rows.append(dict(row_type='BRIDGE', risk_period=rp, step=step, category='load_basis: official firm load -> model native load at the risk step',
                         delta_MW=mpeak - F, credited_MW=cum, firm_load_MW=mpeak, prm=(cum - mpeak) / mpeak,
                         resolution='LOAD_CONCEPT_NOT_CONFIRMED_EQUAL (forecast normal-weather firm load vs actual 2025 native load)'))
        br = [r for r in rows if r['row_type'] == 'BRIDGE' and r['risk_period'] == rp and r['step'] > 0 and 'delta_MW' in r and not r['category'].startswith('load_basis')]
        summary[rp] = dict(official_prm=firm['prm'], model_prm_official_load=(model_total - F) / F, model_prm_native_load=(model_total - mpeak) / mpeak,
                           official_credited_MW=firm['official_MW'], model_credited_MW=model_total, official_firm_load_MW=F, model_load_MW=mpeak,
                           not_modelled_MW=float(sum(-r['delta_MW'] for r in br if r['resolution'] == 'NOT_MODELLED')),
                           unexplained_MW=float(sum(r['delta_MW'] for r in br if 'UNRESOLVED' in r['resolution'])),
                           elcc_scope_MW=float(sum(r['delta_MW'] for r in br if r['resolution'].startswith('ELCC_AND_FLEET'))),
                           explained_scope_MW=float(sum(r['delta_MW'] for r in br if r['resolution'].startswith('EXPLAINED'))),
                           load_basis_MW=mpeak - F, closes=bool(abs(firm['official_MW'] + sum(r['delta_MW'] for r in br) - model_total) < 1e-6))
    # ERM rows: model constraints, not the official PRM
    rows.append(dict(row_type='ERM', category='ERM_15pct_per_snapshot', prm=0.15,
                     note='scripts/opts/reserves.py + wp2_ercot_s0_s1.ERM_MARGIN: per 3 h snapshot, sum over the TX region of storage / line '
                          'reserve terms + non-extendable p_nom x p_max_pu(t) >= demand(t) x 1.15; energy-backed deliverability row of S0-S3, '
                          'NOT the CDR PRM (no ELCC, no firm-load adjustments, per snapshot rather than at one forecast peak)'))
    rows.append(dict(row_type='ERM', category='ERM-02_B_period_margin',
                     note='v240_mech / rearch_mech --calibrate: per-period margin m_p <= 0.15 maximised on the existing + committed fleet; '
                          'future-period values are proxy margins, negative values are not an ERCOT-accepted planning standard; '
                          'not renamed as PRM and not tuned to 18.90 % / 10.47 %'))
    rows.append(dict(row_type='ERM', category='official_PRM_use_in_v1.6',
                     note='external validation anchor only (this table); the official PRM is NOT written into any snapshot ERM row, '
                          'ERM is not lowered / raised to match it; snapshot ERM is NOT calibrated to an official standard (not implemented)'))
    T = pd.DataFrame(rows)
    T.to_csv(out / 'RELIABILITY_ANCHOR_BRIDGE.csv', index=False, lineterminator='\n')
    u[['Unique ID', 'T_PNM', 'tech', 'carrier', 'category', 'GEOID', 'weather_zone', 'summer_power_capacity_MW', 'energy_capacity_MWh',
       'switchable_item']].to_csv(out / 'PRM_BRIDGE_UNIT_CATEGORIES.csv', index=False, lineterminator='\n')
    summary['inputs_sha256'] = {p.name: sha(p) for p in (EV / 'CDR_2025_RESOURCE_DEMAND_COMPONENTS.csv', EV / 'CDR_2025_PRM_REFERENCE.csv',
                                                          EV / 'CDR_2025_ELCC_REFERENCE.csv')}
    summary['script_sha256'] = sha(__file__)
    (out / 'PRM_BRIDGE_SUMMARY.json').write_text(json.dumps(summary, indent=1, default=str))
    print(json.dumps(summary, indent=1, default=str))


if __name__ == '__main__':
    main()
