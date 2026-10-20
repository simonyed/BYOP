#!/usr/bin/env python3
"""v2.5.0 CNY-02: 2025 actual ERCOT baseline on the county ReEDS/NARIS transport network.

Same data and rules as work_package_v2/tools/build_2025_baseline.py (DATA-07, 7 zones), re-targeted to county buses:
  fleet  : ReEDS generator DB (eb75a6bc), T_PCA == ERCO; active 2025 = OP/SB, StartYear <= 2025 < RetireYear (summer MW);
           committed = U/V/TS at StartYear. Bus = the unit's own county bus if that county is in the network, else the
           nearest network county bus by county centroid (logged, MW reported) -- no p48/p50 7-zone re-hanging.
  load   : ERCOT Native_Load_2025 by 8 weather zones -> ERCOT counties by ReEDS county_state_lpf within each weather
           zone (county -> weather zone by nearest reference station, as DATA-07c); counties without a bus give their
           share to the nearest county bus. Sum over buses == ERCOT 2025 native load (asserted).
  weather: county-bus renewable profiles of the prepared county network (GODEEEP 2030, WIND-01-C applied upstream).
  island : buses of reeds_zone p48 (SPP panhandle, an island in the 7-zone model) are dropped if not connected
           (SPATIAL-ERCOT-03 analogue, checked on the county links).
Run (L2, from pypsa-usa/workflow, venv active):
    python byop/build/build_2025_baseline_county.py --prep <county prepared nc>
"""
import argparse, hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import geopandas as gpd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
import byop_paths as BP  # noqa: E402
REEDS = BP.REEDS
OUT = BP.BASE_COUNTY.parent
NATIVE_LOAD = BP.NATIVE_LOAD
ZONES7 = ['p60', 'p61', 'p62', 'p63', 'p64', 'p65', 'p67']
WZ_STATIONS = {'COAST': (29.98, -95.34), 'EAST': (32.35, -95.40), 'FWEST': (31.94, -102.19), 'NORTH': (33.98, -98.49),
               'NCENT': (32.90, -97.04), 'SOUTH': (27.77, -97.50), 'SCENT': (30.19, -97.67), 'WEST': (32.41, -99.68)}
GAS = 3.19
TECH_MAP = {'gas-cc': 'CCGT', 'gas-ct': 'OCGT', 'o-g-s': 'gas_steam', 'coaloldscr': 'coal', 'coal-new': 'coal',
            'coaloldunscr': 'coal', 'nuclear': 'nuclear', 'upv': 'solar', 'pvb_pv': 'solar', 'wind-ons': 'onwind',
            'battery_li': 'battery', 'hydEND': 'hydro', 'hydED': 'hydro', 'biopower': 'biomass',
            'lfill-gas': 'biomass', 'pumped-hydro': 'battery'}
THERMAL_FUEL = {'CCGT': 'gas', 'OCGT': 'gas', 'gas_steam': 'gas', 'coal': 'coal', 'nuclear': 'nuclear', 'biomass': 'bio'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--prep', required=True)
    ap.add_argument('--itl-cal-lp', default=None, help='D250-20: CSV from calibrate_itl_lp.py (replaces the peak heuristic)')
    ap.add_argument('--out-dir', default=None, help='write here instead of outputs/baseline_2025_county (do not overwrite a baseline in use)')
    a = ap.parse_args()
    global OUT
    if a.out_dir:
        OUT = Path(a.out_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    prep = pypsa.Network(a.prep)
    n = prep.copy()
    b = n.buses
    # ---------------- island screen: p48 counties ----------------
    zone_of = b.reeds_zone if 'reeds_zone' in b else pd.Series('', index=b.index)
    p48 = list(b.index[zone_of == 'p48'])
    links = n.links
    touching = links.index[(links.bus0.isin(p48) & ~links.bus1.isin(p48)) | (links.bus1.isin(p48) & ~links.bus0.isin(p48))]
    island = {}
    # D250-10: p48 = SPP panhandle counties (non-ERCOT). In the county NARIS file they hang on one 9/13 MW ITL
    # (p48129||p48191); kept, they would strand 2.25 GW of ERCO wind. Drop them always (DATA-07d analogue): ERCO units
    # located there are re-hung to the nearest ERCOT county bus below and their counties get no ERCOT load.
    tie = {l: (float(links.p_nom[l])) for l in touching}
    if p48:
        for c in ['Generator', 'Load', 'StorageUnit', 'Store']:
            df = n.static(c)
            if not df.empty:
                n.remove(c, df.index[df.bus.isin(p48)])
        inner = links.index[links.bus0.isin(p48) & links.bus1.isin(p48)]
        n.remove('Link', inner)
        lines = n.lines.index[n.lines.bus0.isin(p48) | n.lines.bus1.isin(p48)]
        n.remove('Line', lines)
        n.remove('Bus', p48)
        n.remove('Link', [l for l in touching if l in n.links.index])
        island = dict(dropped_buses=p48, removed_tie_links_MW=tie, rule='D250-10: SPP p48 counties dropped; ERCO units re-hung to nearest ERCOT county bus')
    ac = n.buses.index[n.buses.carrier == 'AC']
    zbus = [x for x in ac if str(x).startswith('p48') and len(str(x)) == 6]   # county buses 'p48FFF'
    xy = n.buses.loc[zbus, ['x', 'y']]
    import networkx as nx
    G = nx.Graph(); G.add_nodes_from(zbus)
    acl = n.links[n.links.carrier == 'AC']
    G.add_edges_from([(u, v) for u, v, c in zip(acl.bus0, acl.bus1, acl.p_nom) if c > 0])
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    island['components'] = [len(c) for c in comps]
    island['small_components'] = [sorted(c) for c in comps[1:]]
    # D250-11: buses outside the main ITL component (unreachable on the county ITL graph) are diagnosed and their units /
    # load re-hung to the nearest main-component county bus (same rule as counties without a bus); nothing is deleted.
    stray = [b_ for c in comps[1:] for b_ in c]
    if stray:
        for c in ['Generator', 'Load', 'StorageUnit', 'Store']:
            df = n.static(c)
            if not df.empty:
                n.remove(c, df.index[df.bus.isin(stray)])
        n.remove('Link', n.links.index[n.links.bus0.isin(stray) | n.links.bus1.isin(stray)])
        n.remove('Bus', stray)
        zbus = [x for x in zbus if x not in stray]
        xy = n.buses.loc[zbus, ['x', 'y']]
        island['rehung_unreachable_buses'] = stray

    def nearest(lon, lat):
        return ((xy.x - lon) ** 2 + (xy.y - lat) ** 2).idxmin()

    # ---------------- counties ----------------
    cty = gpd.read_file(REEDS / 'shapefiles/cache/tl_2022_us_county/tl_2022_us_county.dbf', ignore_geometry=True)
    cty = cty[cty.STATEFP == '48'].copy()
    cty['bus'] = 'p' + cty.GEOID.astype(str)
    cty['lat'] = cty.INTPTLAT.astype(float); cty['lon'] = cty.INTPTLON.astype(float)
    c2z = pd.read_csv(REEDS / 'zones/z134/county2zone.csv')
    c2z['bus'] = 'p' + c2z.FIPS.astype(str).str.replace('p', '').str.zfill(5)
    cty['r'] = cty.bus.map(c2z.set_index('bus').r)
    lpf = pd.read_csv(REEDS / 'disaggregation/county_state_lpf.csv')
    lpf['bus'] = 'p' + lpf.FIPS.astype(str).str.replace('p', '').str.zfill(5)
    cty['lpf'] = cty.bus.map(lpf.set_index('bus').value).fillna(0.0)
    erc = cty[cty.bus.isin(zbus) | cty.r.isin(ZONES7) | (cty.GEOID == '48303')].copy()
    erc['net_bus'] = [bb if bb in zbus else nearest(lo, la) for bb, lo, la in zip(erc.bus, erc.lon, erc.lat)]
    erc['bus_rule'] = np.where(erc.bus.isin(zbus), 'own_county_bus', 'nearest_county_bus')

    # ---------------- fleet ----------------
    db = pd.read_csv(REEDS / 'capacity_exogenous/ReEDS_generator_database_final_EIA-NEMS.csv', low_memory=False)
    db = db[db.T_PCA.astype(str).str.strip() == 'ERCO'].copy()
    db['cbus'] = 'p' + db.FIPS.astype(str).str.replace('p', '').str.zfill(5)
    db['carrier'] = db.tech.map(TECH_MAP)
    unmapped_tech = sorted(db[db.carrier.isna()].tech.unique())
    db = db[db.carrier.notna()]
    db['zone'] = [c if c in zbus else nearest(lo, la) for c, lo, la in zip(db.cbus, db.T_LONG, db.T_LAT)]
    db['zone_rule'] = np.where(db.cbus.isin(zbus), 'own_county_bus', 'nearest_county_bus')
    st = db.status.str[:4]
    db['sy'] = db.StartYear
    active = db[st.isin(['(OP)', '(SB)']) & (db.StartYear <= 2025) & (db.RetireYear > 2025)].copy()
    committed = db[st.isin(['(U) ', '(V) ', '(TS)'])].copy()
    active['retire_bucket'] = np.where(active.RetireYear <= 2035, active.RetireYear, 2100)
    agg = lambda df, keys: df.groupby(keys).apply(lambda g: pd.Series(dict(
        MW=g.summer_power_capacity_MW.sum(), MWh=g.energy_capacity_MWh.fillna(0).sum(),
        heat_rate=np.average(g.HeatRate.fillna(0), weights=g.summer_power_capacity_MW) if g.HeatRate.notna().any() else np.nan,
        vom=np.average(g.T_VOM.fillna(0), weights=g.summer_power_capacity_MW), units=len(g),
        start_year=int(round(np.average(g.sy, weights=g.summer_power_capacity_MW))))), include_groups=False).reset_index()
    fleet = agg(active, ['zone', 'carrier', 'retire_bucket'])
    pipe = agg(committed, ['zone', 'carrier', 'StartYear'])
    fleet.to_csv(OUT / 'ercot_fleet_2025_county.csv', index=False)
    pipe.to_csv(OUT / 'ercot_committed_pipeline_county.csv', index=False)
    active[['T_PLANTID' if 'T_PLANTID' in active else 'tech', 'tech', 'carrier', 'cbus', 'zone', 'zone_rule',
            'summer_power_capacity_MW', 'StartYear', 'RetireYear']].to_csv(OUT / 'COUNTY_PLANT_MAPPING.csv', index=False)

    # ---------------- load ----------------
    nl = pd.read_excel(NATIVE_LOAD)
    assert len(nl) == 8760
    st_xy = pd.DataFrame(WZ_STATIONS, index=['lat', 'lon']).T
    erc['wz'] = [((st_xy.lat - la) ** 2 + (st_xy.lon - lo) ** 2).idxmin() for la, lo in zip(erc.lat, erc.lon)]
    split = erc.groupby(['wz', 'net_bus']).lpf.sum()
    split = split / split.groupby(level=0).transform('sum')
    hourly = pd.DataFrame(0.0, index=range(8760), columns=sorted(set(erc.net_bus)))
    for (wz, bb), sh in split.items():
        hourly[bb] += nl[wz].values * sh
    assert abs(hourly.values.sum() - nl.ERCOT.sum()) < 1e-6 * nl.ERCOT.sum()
    erc[['GEOID', 'NAME', 'r', 'wz', 'lpf', 'net_bus', 'bus_rule']].to_csv(OUT / 'COUNTY_LOAD_MAPPING.csv', index=False)
    h3 = hourly.groupby(np.arange(8760) // 3).mean()
    h3.index = prep.snapshots
    h3.to_csv(OUT / 'ercot_load_2025_3h_by_county.csv.gz')

    # ---------------- network rebuild ----------------
    g = n.generators
    def fuel_price(carrier):
        rows = g[(g.carrier == carrier) & (g.p_nom > 0)]
        return float(np.average(rows.marginal_cost, weights=rows.p_nom)) if len(rows) else None
    mc_ref = {c: fuel_price(c) for c in ['coal', 'nuclear', 'biomass', 'hydro']}
    ex_g = g.index[g.bus.isin(zbus) & (g.p_nom > 0)]
    templ = g.loc[ex_g].copy()
    templ_all = g[g.bus.isin(zbus)].copy()     # incl. extendable templates (renewable profiles per county)
    prof = prep.generators_t.p_max_pu.copy()   # D250-22: NOT a view of n (n.remove drops removed templates' columns in place)
    n.remove('Generator', ex_g)
    su = n.storage_units
    n.remove('StorageUnit', su.index[su.bus.isin(zbus) & (su.p_nom > 0)])
    if 'gas_steam' not in n.carriers.index:
        n.add('Carrier', 'gas_steam', co2_emissions=float(n.carriers.co2_emissions.get('OCGT', 0.18)))
    added, tmpl_rule = [], []

    def template(bus, carrier):
        c = 'OCGT' if carrier == 'gas_steam' else carrier
        for pool in (templ, templ_all):
            t = pool[(pool.bus == bus) & (pool.carrier == c)]
            if len(t):
                return t.iloc[0], 'same_bus'
        t = templ_all[templ_all.carrier == c]
        if carrier in ('solar', 'onwind', 'hydro'):
            t = t[t.index.isin(prof.columns)]
        bx, by = n.buses.x[bus], n.buses.y[bus]
        d = (n.buses.x[t.bus].values - bx) ** 2 + (n.buses.y[t.bus].values - by) ** 2
        return t.iloc[int(np.argmin(d))], 'nearest_bus'

    def add_rows(df, committed_flag):
        for r in df.itertuples():
            name = f"{r.zone} {r.carrier} 2025fleet r{r.retire_bucket}" if not committed_flag else f"{r.zone} {r.carrier} committed {r.StartYear}"
            build_year = 2025 if not committed_flag else int(r.StartYear)
            lifetime = (int(r.retire_bucket) - build_year) if (not committed_flag and r.retire_bucket < 2100) else 100
            if r.carrier == 'battery':
                hours = r.MWh / r.MW if r.MW > 0 and r.MWh > 0 else 4.0
                n.add('StorageUnit', name, bus=r.zone, carrier='battery', p_nom=r.MW, p_nom_extendable=False,
                      max_hours=hours, efficiency_store=0.92, efficiency_dispatch=0.92, cyclic_state_of_charge=True,
                      build_year=build_year, lifetime=lifetime, marginal_cost=0.0)
                added.append((name, 'StorageUnit', r.MW)); continue
            t0, rule = template(r.zone, r.carrier)
            tmpl_rule.append(dict(asset=name, MW=r.MW, template=t0.name, rule=rule))
            kw = dict(bus=r.zone, carrier=r.carrier, p_nom=r.MW, p_nom_extendable=False, build_year=build_year,
                      lifetime=lifetime, capital_cost=0.0)
            if r.carrier in ('solar', 'onwind', 'hydro'):
                src = prof[t0.name] if t0.name in prof.columns else None
                kw.update(marginal_cost=float(t0.marginal_cost), p_max_pu=src if src is not None else float(t0.p_max_pu))
            else:
                hr = r.heat_rate if r.heat_rate and not np.isnan(r.heat_rate) and r.heat_rate > 0 else None
                if THERMAL_FUEL[r.carrier] == 'gas' and hr:
                    mc = hr / 1000 * GAS + (r.vom or 0); eff = 3412.14 / hr
                else:
                    mc = mc_ref.get(r.carrier) or float(t0.marginal_cost); eff = float(t0.efficiency)
                kw.update(marginal_cost=mc, efficiency=eff, p_max_pu=float(t0.p_max_pu) if not np.isnan(t0.p_max_pu) else 1.0,
                          ramp_limit_up=float(t0.ramp_limit_up) if not np.isnan(t0.ramp_limit_up) else 1.0,
                          ramp_limit_down=float(t0.ramp_limit_down) if not np.isnan(t0.ramp_limit_down) else 1.0)
            n.add('Generator', name, **kw)
            added.append((name, 'Generator', r.MW))
    add_rows(fleet, False)
    add_rows(pipe, True)
    for _, t0 in templ[templ.carrier.isin(['CCGT', 'OCGT']) & templ.p_nom_extendable].iterrows():
        n.add('Generator', f'{t0.bus} {t0.carrier}_new', bus=t0.bus, carrier=t0.carrier, p_nom=0.0, p_nom_min=0.0,
              p_nom_extendable=True, capital_cost=float(t0.capital_cost), marginal_cost=float(t0.marginal_cost),
              efficiency=float(t0.efficiency), build_year=2030, lifetime=float(t0.lifetime), p_max_pu=1.0,
              ramp_limit_up=1.0, ramp_limit_down=1.0)
    ld = n.loads
    n.remove('Load', ld.index[ld.bus.isin(zbus)])
    for bb in h3.columns:
        n.add('Load', f'{bb} load 2025', bus=bb, p_set=h3[bb], carrier='AC')
    # D250-16: 2025 deliverability calibration. ERCOT served its 2025 native load, so a county whose 2025 peak exceeds
    # local dispatchable + battery capacity + NARIS import capability is a network-data gap (synthetic TAMU vintage /
    # re-hung county load, e.g. Lubbock -> Crosby; split ERCOT/MISO Montgomery), not a real 2025 shortage. The deficit is
    # added symmetrically to the county's largest existing corridor; every uplift is logged (evidence level B,
    # derivation 'B2025_CALIBRATION'), it is not a TPIT project and earns no expansion cost.
    FIRM = ['CCGT', 'OCGT', 'gas_steam', 'coal', 'nuclear', 'biomass', 'hydro']
    gx = n.generators[~n.generators.p_nom_extendable & (n.generators.build_year <= 2025)]
    sx = n.storage_units[~n.storage_units.p_nom_extendable & (n.storage_units.build_year <= 2025)]
    peak = n.loads_t.p_set.T.groupby(n.loads.bus).sum().T.max()
    local = gx[gx.carrier.isin(FIRM)].groupby('bus').p_nom.sum().add(sx.groupby('bus').p_nom.sum(), fill_value=0.0)
    acl = n.links[n.links.carrier == 'AC']
    imp = acl.groupby('bus1').p_nom.sum()
    n.export_to_netcdf(OUT / 'baseline_2025_county_raw_uncalibrated.nc')   # input of calibrate_itl_lp.py (D250-20)
    uplift = []
    if a.itl_cal_lp:
        cal = pd.read_csv(a.itl_cal_lp)
        for r in cal.itertuples():
            n.links.loc[r.link, 'p_nom'] += float(r.added_MW)
            uplift.append(dict(county_bus=r.bus1, from_bus=r.bus0, added_MW=float(r.added_MW), corridor=r.corridor,
                               direction=r.direction, existing_MW=float(r.existing_MW), evidence_level='B',
                               derivation='B2025_CALIBRATION_LP'))
    # D250-16b: the deficit is split over the county's inbound corridors in proportion to each neighbour's surplus
    # (local firm/battery + its own import capability - its peak - what it already passes on); a remainder that the
    # neighbours cannot cover becomes pass-through demand of the best-connected neighbour (cascade, max 50 rounds).
    need = {bb: float(peak.get(bb, 0.0)) for bb in zbus}
    passed = {bb: 0.0 for bb in zbus}
    for _ in range(0 if a.itl_cal_lp else 50):
        acl = n.links[n.links.carrier == 'AC']
        imp = acl.groupby('bus1').p_nom.sum()
        cover = lambda b_: float(local.get(b_, 0.0)) + float(imp.get(b_, 0.0))
        short = [(b_, need[b_] + passed[b_] - cover(b_)) for b_ in zbus if need[b_] + passed[b_] - cover(b_) > 1e-6]
        if not short:
            break
        for bb, deficit in short:
            inbound = acl[acl.bus1 == bb]
            if inbound.empty:
                raise SystemExit(f'D250-16: {bb} has no corridor')
            sur = pd.Series({f: max(0.0, cover(n.links.bus0[f]) - need[n.links.bus0[f]] - passed[n.links.bus0[f]])
                             for f in inbound.index})
            alloc = (sur / sur.sum() * min(deficit, sur.sum())) if sur.sum() > 0 else pd.Series(0.0, index=inbound.index)
            rest = deficit - float(alloc.sum())
            if rest > 1e-6:
                f_best = inbound.p_nom.idxmax()
                alloc[f_best] = alloc.get(f_best, 0.0) + rest
            for f, add in alloc.items():
                if add <= 1e-9:
                    continue
                r_ = f.replace('_fwd', '_rev') if f.endswith('_fwd') else f.replace('_rev', '_fwd')
                before = (float(n.links.p_nom[f]), float(n.links.p_nom.get(r_, np.nan)))
                n.links.loc[f, 'p_nom'] += add
                if r_ in n.links.index:
                    n.links.loc[r_, 'p_nom'] += add
                passed[n.links.bus0[f]] += add
                uplift.append(dict(county_bus=bb, from_bus=n.links.bus0[f], peak_MW=float(peak.get(bb, 0.0)),
                                   local_firm_battery_MW=float(local.get(bb, 0.0)), deficit_MW=deficit, added_MW=float(add),
                                   corridor=f[:-4], before_fwd_rev_MW=before, after_fwd_MW=float(n.links.p_nom[f]),
                                   evidence_level='B', derivation='B2025_CALIBRATION',
                                   counties_loaded_here=';'.join(erc[erc.net_bus == bb].NAME)))
    pd.DataFrame(uplift).to_csv(OUT / 'ITL_2025_CALIBRATION_UPLIFT.csv', index=False)
    ren = n.generators.index[n.generators.carrier.isin(['solar', 'onwind'])]
    miss = ren.difference(n.generators_t.p_max_pu.columns)
    assert len(miss) == 0, f'D250-22: renewable generators without availability profile: {list(miss)[:10]}'
    cfs = n.generators_t.p_max_pu[ren].mean()
    assert cfs.max() < 0.8, f'D250-22: implausible mean availability {cfs.max():.2f}'
    n.meta = dict(prep.meta, baseline='v2.5.0 CNY-02 2025 actual ERCOT (ReEDS) on county buses')
    out_nc = OUT / 'baseline_2025_county_prepared.nc'
    n.export_to_netcdf(out_nc)
    pd.DataFrame(tmpl_rule).to_csv(OUT / 'county_template_rules.csv', index=False)
    sw = n.snapshot_weightings.generators
    itl = n.links[n.links.carrier == 'AC']
    audit = dict(
        status='BASELINE_2025_COUNTY_BUILT', reeds_commit='eb75a6bc664297492b38a40782df294666269971',
        prep=a.prep, prep_sha256=sha(a.prep), inputs={p.name: sha(p) for p in REEDS.rglob('*') if p.is_file() and p.name != 'SHA256SUMS'},
        native_load_sha256=sha(NATIVE_LOAD), island=island,
        county_buses=len(zbus), ercot_counties=len(erc), counties_without_bus=int((erc.bus_rule != 'own_county_bus').sum()),
        load_buses=len(h3.columns), itl_links=len(itl), itl_MW_total_fwd=float(itl[itl.index.str.endswith('_fwd')].p_nom.sum()) if len(itl) else None,
        fleet_2025_MW_by_carrier=fleet.groupby('carrier').MW.sum().round(1).to_dict(),
        fleet_2025_MW_total=round(float(fleet.MW.sum()), 1),
        committed_MW_by_year=pipe.groupby('StartYear').MW.sum().round(1).to_dict(),
        fleet_MW_by_rule=active.groupby('zone_rule').summer_power_capacity_MW.sum().round(1).to_dict(),
        template_rule_MW=pd.DataFrame(tmpl_rule).groupby('rule').MW.sum().round(1).to_dict() if tmpl_rule else {},
        unmapped_reeds_techs=unmapped_tech,
        load=dict(ercot_native_2025_TWh=float(nl.ERCOT.sum() / 1e6), ercot_2025_TWh_model=float((h3.sum(axis=1) * sw.values).sum() / 1e6),
                  peak_MW_3h=float(h3.sum(axis=1).max()),
                  top10_county_share=(h3.sum() / h3.sum().sum()).sort_values(ascending=False).head(10).round(4).to_dict()),
        itl_2025_calibration=dict(n_rows=len(uplift), total_uplift_MW=round(sum(u['added_MW'] for u in uplift), 1), counties=sorted({u['county_bus'] for u in uplift})),
        output=str(out_nc), output_sha256=sha(out_nc))
    (OUT / 'baseline_2025_county_audit.json').write_text(json.dumps(audit, indent=2, default=str))
    print(json.dumps({k: audit[k] for k in audit if k not in ('inputs',)}, indent=1, default=str))


if __name__ == '__main__':
    main()
