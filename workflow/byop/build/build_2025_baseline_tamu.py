#!/usr/bin/env python3
"""Rearchitecture WP-A: 2025 actual ERCOT baseline on the TAMU/BE electrical backbone (config.byop_ercot_tamu.yaml).

Same data rules as build_2025_baseline_county.py (ReEDS eb75a6bc fleet, ERCOT Native Load 2025), re-targeted to the
clustered TAMU network (AC Lines with impedances, DC power flow), and with the electrical mapping made explicit:
  fleet   : ReEDS generator DB, T_PCA == ERCO, active 2025 = OP/SB, StartYear <= 2025 < RetireYear (summer MW);
            committed = U/V/TS at StartYear. Unit (T_LAT, T_LONG) -> nearest ERCOT TAMU substation (elec_s.nc)
            -> cluster bus (busmap_s_<clusters>.csv). No county/zone re-hanging.
  load    : Native_Load_2025 by 8 weather zones -> ERCOT counties (ReEDS county_state_lpf within the weather zone, as
            DATA-07c) -> substations inside the county polygon (by TAMU load_weight; county without substation: nearest
            substation to its centroid) -> cluster bus. Sum == ERCOT 2025 native load (asserted).
  lines   : interface rule (--interface-rule):
              reeds_sum  (default) cross-reeds_zone lines between a zone pair share the ReEDS NARIS reeds_zone
                         interface (max(MW_f0, MW_r0) / s_max_pu) in proportion to their TAMU member-line ratings;
                         PyPSA-USA's calibrate_tamu_transmission_capacity gives EVERY crossing line the full interface
                         value (k crossing lines -> k x interface), which is audited here and not used.
              tamu_raw   sum of the TAMU member-line thermal ratings (linemap) for every line
              pypsa_usa  as delivered by cluster_network (k x interface on crossing lines; audit/sensitivity only)
            Intra-zone lines keep the TAMU aggregate rating in every rule.
  2025    : deliverability calibration LP (same rule as calibrate_itl_lp.py, D250-20): the 2025 fleet must serve 2025
            load in every 3 h step; minimum line uplift priced at UPLIFT_COST, shedding at SHED_COST. Every uplift is
            logged (evidence B, derivation B2025_CALIBRATION_LP), it is not a TPIT project and earns no expansion cost.
  boundary: p48 (SPP panhandle, non-ERCOT) is dropped; buses outside the main AC component are diagnosed and dropped
            with their assets re-hung; there are no import generators or DC ties (no implicit unlimited supply).
Outputs (results/BYOP/baseline_2025_tamu/): baseline_2025_tamu_prepared.nc, NETWORK_MAPPING_AUDIT.csv (bus, line,
asset rows), INTERFACE_AUDIT.csv, LINE_LEDGER.csv, BUS_LEDGER.csv, TAMU_2025_CALIBRATION_LP.csv, baseline_2025_tamu_audit.json,
network_map.png.
Run (L2, from pypsa-usa/workflow, venv active):
    python byop/build/build_2025_baseline_tamu.py --clusters 64s
"""
import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
import byop_paths as BP  # noqa: E402

REEDS = BP.REEDS
NATIVE_LOAD = BP.NATIVE_LOAD
RES = Path('resources/BYOP_ERCOT_TAMU')
ITL_ZONE = Path('repo_data/ReEDS_Constraints/transmission/transmission_capacity_init_AC_ba_NARIS2024.csv')
WZ_STATIONS = {'COAST': (29.98, -95.34), 'EAST': (32.35, -95.40), 'FWEST': (31.94, -102.19), 'NORTH': (33.98, -98.49),
               'NCENT': (32.90, -97.04), 'SOUTH': (27.77, -97.50), 'SCENT': (30.19, -97.67), 'WEST': (32.41, -99.68)}
ZONES7 = ['p60', 'p61', 'p62', 'p63', 'p64', 'p65', 'p67']
GAS = 3.19
TECH_MAP = {'gas-cc': 'CCGT', 'gas-ct': 'OCGT', 'o-g-s': 'gas_steam', 'coaloldscr': 'coal', 'coal-new': 'coal',
            'coaloldunscr': 'coal', 'nuclear': 'nuclear', 'upv': 'solar', 'pvb_pv': 'solar', 'wind-ons': 'onwind',
            'battery_li': 'battery', 'hydEND': 'hydro', 'hydED': 'hydro', 'biopower': 'biomass',
            'lfill-gas': 'biomass', 'pumped-hydro': 'battery'}
THERMAL_FUEL = {'CCGT': 'gas', 'OCGT': 'gas', 'gas_steam': 'gas', 'coal': 'coal', 'nuclear': 'nuclear', 'biomass': 'bio'}
UPLIFT_COST = 2e6     # USD/MW (calibrate_itl_lp.py rule: bought only to avoid > 2 MWh shedding per MW)
SHED_COST = 1e6       # USD/MWh


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def interface_table():
    t = pd.read_csv(ITL_ZONE)
    t['MW'] = np.maximum(t.MW_f0, t.MW_r0)
    d = {}
    for r in t.itertuples():
        d[tuple(sorted([r.r, r.rr]))] = dict(interface=r.interface, MW_f0=r.MW_f0, MW_r0=r.MW_r0, MW=r.MW)
    return d


def calibrate_2025(raw_nc, threads):
    """minimum line uplift so the 2025 fleet serves 2025 load (re-read from the raw nc: Network.copy() of a
    multi-index network loses the time-series index names in pypsa 1.3; returns uplift per line, residual shed)"""
    c = pypsa.Network(raw_nc)
    g = c.generators
    c.remove('Generator', g.index[g.p_nom_extendable | (g.build_year > 2025)])
    s = c.storage_units
    c.remove('StorageUnit', s.index[s.p_nom_extendable | (s.build_year > 2025)])
    for df in (c.generators, c.storage_units, c.lines):
        df['lifetime'] = np.inf; df['build_year'] = 0
    if len(c.global_constraints):
        c.remove('GlobalConstraint', c.global_constraints.index)
    if 'load_shed' not in c.carriers.index:
        c.add('Carrier', 'load_shed')
    buses = sorted(set(c.loads.bus))
    c.add('Generator', [f'{b} shed' for b in buses], bus=buses, carrier='load_shed', p_nom=1e5, marginal_cost=SHED_COST)
    c.lines['s_nom_min'] = c.lines.s_nom
    c.lines['s_nom_extendable'] = True
    c.lines['s_nom_max'] = np.inf
    c.lines['capital_cost'] = UPLIFT_COST
    c.optimize(solver_name='gurobi', solver_options=dict(Method=2, Crossover=0, Threads=int(threads), BarConvTol=1e-8,
                                                         NumericFocus=2))
    up = (c.lines.s_nom_opt - c.lines.s_nom).clip(lower=0.0)
    shed = float(c.generators_t.p[[f'{b} shed' for b in buses]].mul(c.snapshot_weightings.generators, axis=0).sum().sum())
    return up, shed, str(c.model.termination_condition)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clusters', default='64s')
    ap.add_argument('--interface-rule', default='reeds_sum', choices=['reeds_sum', 'tamu_raw', 'pypsa_usa'])
    ap.add_argument('--threads', default='16')
    ap.add_argument('--no-calibration', action='store_true')
    ap.add_argument('--out-dir', default=None)
    a = ap.parse_args()
    out = Path(a.out_dir) if a.out_dir else BP.RESULTS / 'baseline_2025_tamu'
    out.mkdir(parents=True, exist_ok=True)
    cl = a.clusters
    prep_fn = RES / f'networks/texas/elec_s_c{cl}_ec_lv1.0_REM-ERM-3h_E.nc'
    subs_fn = RES / 'networks/texas/elec_s.nc'
    busmap_fn = RES / f'busmaps/texas/busmap_s_{cl}.csv'
    prep = pypsa.Network(prep_fn)
    subs = pypsa.Network(subs_fn)
    busmap = pd.read_csv(busmap_fn, index_col=0).iloc[:, 0]
    busmap.index = busmap.index.astype(str)
    n = pypsa.Network(prep_fn)   # not prep.copy(): see calibrate_2025
    audit_rows = []

    # ---------------- lines: re-aggregate from the connected substation network ----------------
    # PyPSA-USA calibrate_tamu_transmission_capacity() removes every clustered line whose zone pair is not a ReEDS
    # interface, i.e. ALL intra-zone lines (64s: 57 lines left, 24 islands although elec_s.nc is one component).
    # The inter-cluster lines are therefore rebuilt here from elec_s.nc with the same busmap (PyPSA line aggregation:
    # parallel s_nom sum, equivalent x), and the interface rule is applied to the cross-zone ones only.
    from pypsa.clustering.spatial import get_clustering_from_busmap
    import networkx as nx
    pre = n.lines.copy()
    hvac = float((pre.capital_cost / pre.length).median())         # USD/MW-km-yr (HVAC overhead annuity of the run)
    smax0 = float(pre.s_max_pu.median())
    sbm = pd.Series(busmap.reindex(subs.buses.index.astype(str)).values, index=subs.buses.index)
    assert sbm.notna().all(), 'busmap does not cover elec_s.nc'
    bstr = {c: 'first' for c in subs.buses.columns if c not in ('x', 'y')}   # only lines are used from this clustering
    clu = get_clustering_from_busmap(subs, sbm, line_length_factor=1.0, bus_strategies=bstr)
    cl_lines = clu.n.lines.copy()
    cl_linemap = clu.linemap.astype(str)
    cl_linemap.index = cl_linemap.index.astype(str)
    n.remove('Line', n.lines.index)
    keep_cols = ['bus0', 'bus1', 's_nom', 'x', 'r', 'b', 'g', 'length', 'v_nom', 'num_parallel']
    cl_lines = cl_lines[[c for c in keep_cols if c in cl_lines.columns]].copy()
    cl_lines['capital_cost'] = cl_lines.length * hvac
    cl_lines['s_max_pu'] = smax0
    cl_lines['carrier'] = 'AC'
    cl_lines['build_year'] = 2025
    cl_lines['lifetime'] = 60
    cl_lines.index = [f'TL{i}' for i in cl_lines.index]
    cl_linemap = 'TL' + cl_linemap
    n.add('Line', cl_lines.index, **{c: cl_lines[c].values for c in cl_lines.columns})

    # ---------------- boundary: drop non-ERCOT p48 and stray components ----------------
    zone = n.buses.reeds_zone
    p48 = list(n.buses.index[zone == 'p48'])
    tie = n.lines[n.lines.bus0.isin(p48) ^ n.lines.bus1.isin(p48)]
    island = dict(pypsa_usa_lines_after_calibration=len(pre), rebuilt_lines=len(cl_lines),
                  dropped_non_ercot_buses=p48, removed_tie_lines_MVA={k: float(v) for k, v in tie.s_nom.items()})
    for c in ['Generator', 'Load', 'StorageUnit', 'Store']:
        df = n.static(c)
        if not df.empty:
            n.remove(c, df.index[df.bus.isin(p48)])
    n.remove('Line', n.lines.index[n.lines.bus0.isin(p48) | n.lines.bus1.isin(p48)])
    n.remove('Bus', p48)
    G = nx.Graph(); G.add_nodes_from(n.buses.index)
    G.add_edges_from(zip(n.lines.bus0, n.lines.bus1))
    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    stray = [b for c_ in comps[1:] for b in c_]
    island['components'] = [len(c_) for c_ in comps]
    if stray:
        for c in ['Generator', 'Load', 'StorageUnit', 'Store']:
            df = n.static(c)
            if not df.empty:
                n.remove(c, df.index[df.bus.isin(stray)])
        n.remove('Line', n.lines.index[n.lines.bus0.isin(stray) | n.lines.bus1.isin(stray)])
        n.remove('Bus', stray)
        island['dropped_stray_buses'] = stray
    assert len(n.links[n.links.carrier.isin(['AC', 'DC'])]) == 0, 'unexpected AC/DC links (implicit transfer path)'
    cbus = list(n.buses.index[n.buses.carrier == 'AC'])

    # ---------------- substations (ERCOT, kept clusters) ----------------
    sb = subs.buses.copy()
    sb.index = sb.index.astype(str)
    sb['cluster'] = sb.index.map(busmap)
    sb = sb[sb.cluster.isin(cbus)].copy()
    for r in sb.itertuples():
        audit_rows.append(dict(kind='bus', source_id=r.Index, source_kV=float(r.v_nom), lon=r.x, lat=r.y,
                               reeds_zone=r.reeds_zone, cluster_bus=r.cluster, rating_or_MW=float(r.load_weight),
                               rule='busmap_s (modularity, inside reeds_zone)'))

    def nearest_sub(lon, lat):
        return ((sb.x - lon) ** 2 + (sb.y - lat) ** 2).idxmin()

    # ---------------- interface rule ----------------
    sl = subs.lines.copy(); sl.index = sl.index.astype(str)
    sl['cluster_line'] = sl.index.map(cl_linemap)
    sl = sl[sl.cluster_line.isin(n.lines.index)]
    nmem = sl.groupby('cluster_line').size()
    pz = {}          # PyPSA-USA calibrated rating per zone pair (one value per crossing line = full interface)
    for r in pre.itertuples():
        z0, z1 = prep.buses.reeds_zone.get(r.bus0), prep.buses.reeds_zone.get(r.bus1)
        if z0 != z1:
            pz[tuple(sorted([z0, z1]))] = float(r.s_nom)
    itf = interface_table()
    smax = n.lines.s_max_pu
    L = n.lines.copy()
    L['zone0'] = L.bus0.map(n.buses.reeds_zone); L['zone1'] = L.bus1.map(n.buses.reeds_zone)
    L['pair'] = [tuple(sorted([a_, b_])) for a_, b_ in zip(L.zone0, L.zone1)]
    L['cross_zone'] = L.zone0 != L.zone1
    L['tamu_raw_s_nom'] = L.s_nom
    L['n_member_lines'] = [int(nmem.get(i, 0)) for i in L.index]
    L['pypsa_usa_s_nom'] = [pz.get(p, np.nan) if c else np.nan for p, c in zip(L.pair, L.cross_zone)]
    L['reeds_interface_MW'] = [itf.get(p, {}).get('MW', np.nan) if c else np.nan for p, c in zip(L.pair, L.cross_zone)]
    L['reeds_interface'] = [itf.get(p, {}).get('interface', '') if c else '' for p, c in zip(L.pair, L.cross_zone)]
    share = L.tamu_raw_s_nom / L.groupby('pair').tamu_raw_s_nom.transform('sum')
    L['reeds_sum_s_nom'] = np.where(L.cross_zone & L.reeds_interface_MW.notna(), L.reeds_interface_MW / smax * share,
                                    L.tamu_raw_s_nom)
    rule_col = {'reeds_sum': 'reeds_sum_s_nom', 'tamu_raw': 'tamu_raw_s_nom', 'pypsa_usa': 'pypsa_usa_s_nom'}[a.interface_rule]
    newcap = L[rule_col].fillna(L.tamu_raw_s_nom)
    ratio = newcap / L.s_nom.replace(0, np.nan)
    # parallel-circuit scaling (same convention as calibrate_tamu_transmission_capacity): x, r ~ 1/capacity
    n.lines.loc[L.index, 'x'] = n.lines.x / ratio.fillna(1.0)
    n.lines.loc[L.index, 'r'] = n.lines.r / ratio.fillna(1.0)
    n.lines.loc[L.index, 's_nom'] = newcap.values
    for i, r in sl.iterrows():
        audit_rows.append(dict(kind='line_member', source_id=i, source_kV=float(r.v_nom) if 'v_nom' in r else np.nan,
                               cluster_line=r.cluster_line, rating_or_MW=float(r.s_nom), rule='pypsa line aggregation (busmap_s)'))
    itf_rows = []
    for p, grp in L[L.cross_zone].groupby('pair'):
        ok = grp.reeds_interface_MW.notna().all()
        itf_rows.append(dict(zone_pair='||'.join(p), reeds_interface=grp.reeds_interface.iloc[0],
                             reeds_MW_max_dir=grp.reeds_interface_MW.iloc[0], n_crossing_lines=len(grp),
                             tamu_raw_sum_MW=float((grp.tamu_raw_s_nom * grp.s_max_pu).sum()),
                             pypsa_usa_per_line_MW=float(grp.pypsa_usa_s_nom.iloc[0] * grp.s_max_pu.iloc[0]) if grp.pypsa_usa_s_nom.notna().any() else np.nan,
                             pypsa_usa_overcount_factor=float(len(grp)) if ok else np.nan,
                             applied_sum_MW=float((newcap[grp.index] * grp.s_max_pu).sum()), rule=a.interface_rule))
    itf_df = pd.DataFrame(itf_rows)
    itf_df.to_csv(out / 'INTERFACE_AUDIT.csv', index=False)

    # ---------------- counties -> substations ----------------
    # attributes from the ReEDS TIGER 2022 table (.dbf only), polygons from PyPSA-USA's Census cartographic counties
    att = gpd.read_file(REEDS / 'shapefiles/cache/tl_2022_us_county/tl_2022_us_county.dbf', ignore_geometry=True)
    att = att[att.STATEFP == '48']
    geo = gpd.read_file('data/counties/cb_2020_us_county_500k.shp')[['GEOID', 'geometry']].to_crs(4326)
    shp = geo.merge(att, on='GEOID', how='inner')
    shp['lat'] = shp.INTPTLAT.astype(float); shp['lon'] = shp.INTPTLON.astype(float)
    pts = gpd.GeoDataFrame(sb[['load_weight', 'cluster']], geometry=gpd.points_from_xy(sb.x, sb.y), crs=4326)
    j = gpd.sjoin(pts, shp[['GEOID', 'geometry']], how='left', predicate='within')
    sb['county'] = j.GEOID.groupby(level=0).first().reindex(sb.index)
    c2z = pd.read_csv(REEDS / 'zones/z134/county2zone.csv')
    c2z['GEOID'] = c2z.FIPS.astype(str).str.replace('p', '').str.zfill(5)
    shp['r'] = shp.GEOID.map(c2z.set_index('GEOID').r)
    lpf = pd.read_csv(REEDS / 'disaggregation/county_state_lpf.csv')
    lpf['GEOID'] = lpf.FIPS.astype(str).str.replace('p', '').str.zfill(5)
    shp['lpf'] = shp.GEOID.map(lpf.set_index('GEOID').value).fillna(0.0)
    erc = shp[shp.r.isin(ZONES7) | shp.GEOID.isin(sb.county.dropna())].copy()
    st_xy = pd.DataFrame(WZ_STATIONS, index=['lat', 'lon']).T
    erc['wz'] = [((st_xy.lat - la) ** 2 + (st_xy.lon - lo) ** 2).idxmin() for la, lo in zip(erc.lat, erc.lon)]
    # county -> cluster-bus shares (substations in the county weighted by TAMU load_weight; none -> nearest substation)
    cshare = []
    for r in erc.itertuples():
        s_in = sb[sb.county == r.GEOID]
        if len(s_in) and s_in.load_weight.sum() > 0:
            w = s_in.groupby('cluster').load_weight.sum(); w = w / w.sum(); rule = 'substations_in_county'
        elif len(s_in):
            w = s_in.groupby('cluster').size().astype(float); w = w / w.sum(); rule = 'substations_in_county_equal'
        else:
            w = pd.Series({sb.cluster[nearest_sub(r.lon, r.lat)]: 1.0}); rule = 'nearest_substation'
        for b_, s_ in w.items():
            cshare.append(dict(GEOID=r.GEOID, NAME=r.NAME, r=r.r, wz=r.wz, lpf=r.lpf, cluster_bus=b_, share=float(s_), rule=rule))
    cshare = pd.DataFrame(cshare)
    cshare.to_csv(out / 'COUNTY_TO_BUS_SHARES.csv', index=False)

    # ---------------- fleet ----------------
    db = pd.read_csv(REEDS / 'capacity_exogenous/ReEDS_generator_database_final_EIA-NEMS.csv', low_memory=False)
    db = db[db.T_PCA.astype(str).str.strip() == 'ERCO'].copy()
    db['carrier'] = db.tech.map(TECH_MAP)
    unmapped_tech = sorted(db[db.carrier.isna()].tech.unique())
    db = db[db.carrier.notna()].copy()
    db['sub'] = [nearest_sub(lo, la) for lo, la in zip(db.T_LONG, db.T_LAT)]
    db['zone'] = db['sub'].map(sb.cluster)
    db['sub_dist_deg'] = [float(np.hypot(sb.x[s_] - lo, sb.y[s_] - la)) for s_, lo, la in zip(db['sub'], db.T_LONG, db.T_LAT)]
    st = db.status.str[:4]
    db['sy'] = db.StartYear
    active = db[st.isin(['(OP)', '(SB)']) & (db.StartYear <= 2025) & (db.RetireYear > 2025)].copy()
    committed = db[st.isin(['(U) ', '(V) ', '(TS)'])].copy()
    active['retire_bucket'] = np.where(active.RetireYear <= 2035, active.RetireYear, 2100)
    for r in pd.concat([active.assign(set='active2025'), committed.assign(set='committed')]).itertuples():
        audit_rows.append(dict(kind='asset', source_id=str(getattr(r, 'T_PLANTID', '')) + ':' + str(r.tech), lon=r.T_LONG, lat=r.T_LAT,
                               substation=r.sub, cluster_bus=r.zone, rating_or_MW=float(r.summer_power_capacity_MW),
                               carrier=r.carrier, rule=f'{r.set}: nearest TAMU substation ({r.sub_dist_deg:.3f} deg)'))
    agg = lambda df, keys: df.groupby(keys).apply(lambda g_: pd.Series(dict(
        MW=g_.summer_power_capacity_MW.sum(), MWh=g_.energy_capacity_MWh.fillna(0).sum(),
        heat_rate=np.average(g_.HeatRate.fillna(0), weights=g_.summer_power_capacity_MW) if g_.HeatRate.notna().any() else np.nan,
        vom=np.average(g_.T_VOM.fillna(0), weights=g_.summer_power_capacity_MW), units=len(g_))), include_groups=False).reset_index()
    fleet = agg(active, ['zone', 'carrier', 'retire_bucket'])
    pipe = agg(committed, ['zone', 'carrier', 'StartYear'])
    fleet.to_csv(out / 'ercot_fleet_2025_tamu.csv', index=False)
    pipe.to_csv(out / 'ercot_committed_pipeline_tamu.csv', index=False)

    # ---------------- load ----------------
    nl = pd.read_excel(NATIVE_LOAD)
    assert len(nl) == 8760
    split = cshare.assign(w=cshare.lpf * cshare.share).groupby(['wz', 'cluster_bus']).w.sum()
    split = split / split.groupby(level=0).transform('sum')
    hourly = pd.DataFrame(0.0, index=range(8760), columns=sorted(set(cshare.cluster_bus)))
    for (wz, bb), sh in split.items():
        hourly[bb] += nl[wz].values * sh
    assert abs(hourly.values.sum() - nl.ERCOT.sum()) < 1e-6 * nl.ERCOT.sum()
    h3 = hourly.groupby(np.arange(8760) // 3).mean()
    h3.index = prep.snapshots
    h3.to_csv(out / 'ercot_load_2025_3h_by_bus.csv.gz')

    # ---------------- network rebuild (as build_2025_baseline_county.py) ----------------
    g = n.generators

    def fuel_price(carrier):
        rows = g[(g.carrier == carrier) & (g.p_nom > 0)]
        return float(np.average(rows.marginal_cost, weights=rows.p_nom)) if len(rows) else None
    mc_ref = {c: fuel_price(c) for c in ['coal', 'nuclear', 'biomass', 'hydro']}
    ex_g = g.index[g.bus.isin(cbus) & (g.p_nom > 0) & ~g.p_nom_extendable]
    templ = g.loc[g.index[g.bus.isin(cbus) & (g.p_nom > 0)]].copy()
    templ_all = g[g.bus.isin(cbus)].copy()
    prof = prep.generators_t.p_max_pu.copy()
    n.remove('Generator', ex_g)
    su = n.storage_units
    n.remove('StorageUnit', su.index[su.bus.isin(cbus) & (su.p_nom > 0) & ~su.p_nom_extendable])
    if 'gas_steam' not in n.carriers.index:
        n.add('Carrier', 'gas_steam', co2_emissions=float(n.carriers.co2_emissions.get('OCGT', 0.18)))
    added, tmpl_rule = [], []

    def template(bus, carrier):
        c = 'OCGT' if carrier == 'gas_steam' else carrier
        for pool in (templ, templ_all):
            t = pool[(pool.bus == bus) & (pool.carrier == c)]
            if carrier in ('solar', 'onwind', 'hydro'):
                t = t[t.index.isin(prof.columns)]
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
    ld = n.loads
    n.remove('Load', ld.index[ld.bus.isin(cbus)])
    for bb in h3.columns:
        n.add('Load', f'{bb} load 2025', bus=bb, p_set=h3[bb], carrier='AC')

    # time-series frames copied from prep lose their 'snapshot' index name (pypsa 1.3 then cannot select them)
    for lst in ['generators', 'loads', 'storage_units', 'stores', 'links', 'lines', 'buses']:
        for attr, d in getattr(n, lst + '_t').items():
            if isinstance(d, pd.DataFrame) and len(d) == len(n.snapshots):
                d.index = n.snapshots
    # ---------------- 2025 deliverability calibration ----------------
    n.lines['build_year'] = 2025
    n.export_to_netcdf(out / 'baseline_2025_tamu_raw_uncalibrated.nc')
    uplift, shed_left, term = (pd.Series(0.0, index=n.lines.index), None, 'NOT_RUN') if a.no_calibration else \
        calibrate_2025(out / 'baseline_2025_tamu_raw_uncalibrated.nc', a.threads)
    cal = pd.DataFrame(dict(line=uplift.index, bus0=n.lines.bus0[uplift.index].values, bus1=n.lines.bus1[uplift.index].values,
                            existing_MVA=n.lines.s_nom[uplift.index].values, added_MVA=uplift.values))
    cal = cal[cal.added_MVA > 0.5].copy()
    cal['evidence_level'] = 'B'; cal['derivation'] = 'B2025_CALIBRATION_LP (min uplift, full-year 2025 dispatch, KVL)'
    cal.to_csv(out / 'TAMU_2025_CALIBRATION_LP.csv', index=False)
    for r in cal.itertuples():
        ratio = (r.existing_MVA + r.added_MVA) / r.existing_MVA
        n.lines.loc[r.line, ['s_nom', 'x', 'r']] = [r.existing_MVA + r.added_MVA, n.lines.x[r.line] / ratio, n.lines.r[r.line] / ratio]
    L['calibration_uplift_MVA'] = uplift.reindex(L.index).fillna(0.0)
    L['final_s_nom'] = n.lines.s_nom.reindex(L.index)
    L['final_transfer_MW'] = L.final_s_nom * n.lines.s_max_pu.reindex(L.index)
    L['interface_rule'] = a.interface_rule
    L[['bus0', 'bus1', 'zone0', 'zone1', 'cross_zone', 'reeds_interface', 'reeds_interface_MW', 'n_member_lines',
       'tamu_raw_s_nom', 'pypsa_usa_s_nom', 'reeds_sum_s_nom', 'calibration_uplift_MVA', 'final_s_nom', 's_max_pu',
       'final_transfer_MW', 'x', 'length', 'capital_cost', 'interface_rule']].to_csv(out / 'LINE_LEDGER.csv')
    for i, r in L.iterrows():
        audit_rows.append(dict(kind='line', source_id=i, cluster_line=i, bus0=r.bus0, bus1=r.bus1, rating_or_MW=float(r.final_transfer_MW),
                               rule=f'{a.interface_rule}; members {r.n_member_lines}; raw {r.tamu_raw_s_nom:.0f}; pypsa_usa {r.pypsa_usa_s_nom:.0f}; uplift {r.calibration_uplift_MVA:.0f}'))
    pd.DataFrame(audit_rows).to_csv(out / 'NETWORK_MAPPING_AUDIT.csv', index=False)

    # ---------------- bus ledger, checks, map ----------------
    gx = n.generators[~n.generators.p_nom_extendable & (n.generators.build_year <= 2025)]
    sx = n.storage_units[~n.storage_units.p_nom_extendable & (n.storage_units.build_year <= 2025)]
    peak = n.loads_t.p_set.T.groupby(n.loads.bus).sum().T.max()
    BL = pd.DataFrame(index=cbus)
    BL['reeds_zone'] = n.buses.reeds_zone; BL['x'] = n.buses.x; BL['y'] = n.buses.y
    BL['n_substations'] = sb.groupby('cluster').size().reindex(cbus).fillna(0).astype(int)
    BL['peak_load_2025_MW'] = peak.reindex(cbus).fillna(0.0)
    BL['energy_2025_TWh'] = (n.loads_t.p_set.T.groupby(n.loads.bus).sum().T.mul(n.snapshot_weightings.generators, axis=0).sum() / 1e6).reindex(cbus).fillna(0.0)
    for car in sorted(gx.carrier.unique()):
        BL[f'MW_{car}'] = gx[gx.carrier == car].groupby('bus').p_nom.sum().reindex(cbus).fillna(0.0)
    BL['MW_battery'] = sx.groupby('bus').p_nom.sum().reindex(cbus).fillna(0.0)
    BL['line_transfer_MW_sum'] = pd.concat([n.lines.groupby('bus0').s_nom.sum(), n.lines.groupby('bus1').s_nom.sum()]).groupby(level=0).sum().reindex(cbus).fillna(0.0)
    BL['counties'] = cshare.groupby('cluster_bus').NAME.apply(lambda s_: ';'.join(sorted(set(s_)))).reindex(cbus)
    BL.to_csv(out / 'BUS_LEDGER.csv')
    ren = n.generators.index[n.generators.carrier.isin(['solar', 'onwind'])]
    miss = ren.difference(n.generators_t.p_max_pu.columns)
    assert len(miss) == 0, f'renewable generators without availability profile: {list(miss)[:10]}'
    assert (n.lines.s_nom > 0).all(), 'non-positive line rating'
    dup = n.lines.groupby([n.lines[['bus0', 'bus1']].min(axis=1), n.lines[['bus0', 'bus1']].max(axis=1)]).size()
    try:
        import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 8))
        for r in n.lines.itertuples():
            ax.plot([n.buses.x[r.bus0], n.buses.x[r.bus1]], [n.buses.y[r.bus0], n.buses.y[r.bus1]], '-', lw=0.4 + r.s_nom / 3000,
                    color='tab:red' if n.buses.reeds_zone[r.bus0] != n.buses.reeds_zone[r.bus1] else 'tab:gray', alpha=0.7)
        sc = ax.scatter(BL.x, BL.y, s=8 + BL.peak_load_2025_MW / 60, c=pd.factorize(BL.reeds_zone)[0], cmap='tab10', zorder=3)
        for b_, r in BL.iterrows():
            ax.annotate(b_, (r.x, r.y), fontsize=5)
        ax.set_title(f'TAMU ERCOT {cl} backbone (red = cross reeds_zone, width ~ rating); size ~ 2025 peak load')
        fig.savefig(out / 'network_map.png', dpi=160, bbox_inches='tight')
    except Exception as e:  # plotting is a convenience, the ledgers are the audit
        print('map failed', e)
    n.meta = dict(prep.meta, baseline=f'Rearchitecture WP-A 2025 actual ERCOT (ReEDS) on TAMU {cl} backbone ({a.interface_rule})')
    out_nc = out / 'baseline_2025_tamu_prepared.nc'
    n.export_to_netcdf(out_nc)
    pd.DataFrame(tmpl_rule).to_csv(out / 'tamu_template_rules.csv', index=False)
    sw = n.snapshot_weightings.generators
    audit = dict(
        status='BASELINE_2025_TAMU_BUILT', clusters=cl, interface_rule=a.interface_rule, reeds_commit='eb75a6bc664297492b38a40782df294666269971',
        prep=str(prep_fn), prep_sha256=sha(prep_fn), subs_sha256=sha(subs_fn), busmap_sha256=sha(busmap_fn),
        native_load_sha256=sha(NATIVE_LOAD), island=island, n_buses=len(cbus), n_lines=len(n.lines),
        n_substations_ercot=int(len(sb)), duplicate_corridors=int((dup > 1).sum()), negative_ratings=int((n.lines.s_nom <= 0).sum()),
        n_links_AC_DC=int(n.links.carrier.isin(['AC', 'DC']).sum()), import_generators=0,
        buses_by_zone=pd.Series(n.buses.reeds_zone).value_counts().to_dict(),
        fleet_2025_MW_by_carrier=fleet.groupby('carrier').MW.sum().round(1).to_dict(), fleet_2025_MW_total=round(float(fleet.MW.sum()), 1),
        committed_MW_by_year=pipe.groupby('StartYear').MW.sum().round(1).to_dict(),
        fleet_MW_far_from_substation=float(active[active.sub_dist_deg > 0.5].summer_power_capacity_MW.sum()),
        template_rule_MW=pd.DataFrame(tmpl_rule).groupby('rule').MW.sum().round(1).to_dict() if tmpl_rule else {},
        unmapped_reeds_techs=unmapped_tech,
        load=dict(ercot_native_2025_TWh=float(nl.ERCOT.sum() / 1e6), model_TWh=float((h3.sum(axis=1) * sw.values).sum() / 1e6),
                  peak_MW_3h=float(h3.sum(axis=1).max()), counties=int(cshare.GEOID.nunique()),
                  county_rule_counts=cshare.drop_duplicates('GEOID').rule.value_counts().to_dict()),
        interfaces=itf_df.to_dict(orient='records'),
        calibration=dict(termination=term, residual_shed_MWh=shed_left, n_lines=len(cal), total_uplift_MVA=round(float(cal.added_MVA.sum()), 1)),
        output=str(out_nc), output_sha256=sha(out_nc))
    (out / 'baseline_2025_tamu_audit.json').write_text(json.dumps(audit, indent=2, default=str))
    print(json.dumps({k: audit[k] for k in audit if k != 'interfaces'}, indent=1, default=str))
    print(itf_df.to_string())


if __name__ == '__main__':
    main()
