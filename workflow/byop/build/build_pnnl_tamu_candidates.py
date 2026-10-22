#!/usr/bin/env python3
"""PNNL IM3 data-center locations -> ERCOT TAMU 64s buses (candidate-bus evidence for 2026+ research AIDC growth).

AIDC geospatial WP v1.0 §2.3 / §3.5. Raw data (not tracked; download from MSD-LIVE, check raw/SHA256SUMS.txt):
  <raw>/im3_open_source_data_center_atlas_v2026.02.09/   https://doi.org/10.57931/3017294  (ODbL 1.0, OSM-derived)
  <raw>/im3_projected_data_centers_v1.1/higher_growth/   https://doi.org/10.57931/3020186  (CC BY 4.0, CERF-DC, through 2035)
Mapping rule (same as the Epoch sites, build_epoch_tamu_allocation.py): ERCOT = Census county whose weather zone is ERCOT in
COUNTY_TO_BUS_SHARES.csv; bus = cluster bus of the nearest ERCOT TAMU substation; bus_alt = nearest substation of another
cluster, boundary tie when < 2 km farther; county_bus_consistent = the bus is one of the county's busmap buses.
Atlas source QA (§3.5):
  * explicit duplicate: a building / point that lies inside (>= 50 % of its area) another record's campus or building polygon
  * suspect same campus: polygons / points within 250 m of each other with the same non-empty operator (merged into one
    site_cluster, flagged, never silently deleted; raw / explicit-only / clustered counts all exported)
  * crypto mining: the four checked OSM records (id AND name) + a name/operator screen that only flags (review)
Outputs (byop/inputs/dc/): PNNL_ATLAS_TX_SITES_TAMU64.csv, PNNL_PROJECTED_HIGHER_TX_TAMU64.csv, PNNL_CANDIDATE_BUS_SUMMARY.csv,
PNNL_SPATIAL_MAPPING_REVIEW.csv, PNNL_PROVENANCE.json.
    python byop/build/build_pnnl_tamu_candidates.py --raw <dir with the two PNNL folders>
Without --raw (or when it is missing) nothing is rebuilt: the tracked outputs are checked against PNNL_PROVENANCE.json.
"""
from __future__ import annotations

import argparse, hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
OUT = WF / 'byop/inputs/dc'
BASE = WF / 'results/BYOP/baseline_2025_tamu'
COUNTIES = WF / 'data/counties/cb_2020_us_county_500k.shp'
ATLAS_DIR = 'im3_open_source_data_center_atlas_v2026.02.09'
PROJ_DIR = 'im3_projected_data_centers_v1.1/higher_growth'
ERCOT_WZ = ['COAST', 'EAST', 'FWEST', 'NORTH', 'NCENT', 'SOUTH', 'SCENT', 'WEST']
GRAVITY = [0, 25, 50, 75, 100]
SUSPECT_M = 250.0
FAR_KM = 15.0                      # nearest TAMU substation farther than this -> mapping review
# checked by OSM id AND name (2026-10-22): bitcoin mining, not AIDC
CRYPTO_CHECKED = {
    'Riot Corsiana': 'Riot Platforms Corsicana bitcoin mining facility (Navarro County)',
    'Riot Rockdale': 'Riot Platforms Rockdale (Whinstone) bitcoin mining facility (Milam County)',
    'MARA Data Center': 'Marathon Digital Holdings (MARA) bitcoin mining site, Granbury (Hood County)',
    'IONIC Digital Cedarvale': 'IONIC Digital Cedarvale bitcoin mining site (Ward County)',
}
CRYPTO_CLEARED = {'Texas Cryptologic Center': 'NSA Texas Cryptologic Center (San Antonio): government facility, name hit of the screen, not mining'}
CRYPTO_SCREEN = r'riot|marathon|\bmara\b|ionic digital|bitdeer|core scientific|cipher mining|terawulf|hut 8|cleanspark|bitcoin|crypto|mining'
OUTPUTS = ['PNNL_ATLAS_TX_SITES_TAMU64.csv', 'PNNL_PROJECTED_HIGHER_TX_TAMU64.csv', 'PNNL_CANDIDATE_BUS_SUMMARY.csv',
           'PNNL_SPATIAL_MAPPING_REVIEW.csv']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def network():
    import geopandas as gpd
    cty = gpd.read_file(COUNTIES).to_crs(4326)
    cty = cty[cty.STATEFP == '48'][['GEOID', 'NAME', 'geometry']]
    sh = pd.read_csv(BASE / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
    sh['GEOID'] = sh.GEOID.str.zfill(5)
    erc = set(sh[sh.wz.isin(ERCOT_WZ)].GEOID)
    cbus = sh.groupby('GEOID').cluster_bus.apply(set).to_dict()
    a = pd.read_csv(BASE / 'NETWORK_MAPPING_AUDIT.csv', low_memory=False)
    sub = a[a.kind == 'bus'][['lon', 'lat', 'reeds_zone', 'cluster_bus']].dropna().reset_index(drop=True)
    return cty, erc, cbus, sub


def locate(df, cty, erc, cbus, sub):
    """county (point in polygon), ERCOT flag, nearest-substation bus and distance, runner-up cluster, county/busmap check"""
    import geopandas as gpd
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lon, df.lat), crs=4326)
    j = gpd.sjoin(pts, cty, how='left', predicate='within').drop(columns='index_right')
    j = j[~j.index.duplicated()]
    out = pd.DataFrame(j.drop(columns='geometry')).rename(columns={'NAME': 'county'})
    out['ercot'] = out.GEOID.isin(erc)
    slo, sla, scb, szn = sub.lon.values, sub.lat.values, sub.cluster_bus.values, sub.reeds_zone.values
    rows = []
    for lo, la in zip(out.lon.values, out.lat.values):
        dd = np.hypot((slo - lo) * np.cos(np.radians(la)), sla - la) * 111.0
        i = int(dd.argmin())
        k = int(np.where(scb != scb[i], dd, np.inf).argmin())
        rows.append((scb[i], szn[i], dd[i], scb[k], dd[k]))
    b, z, d1, alt, d2 = map(np.array, zip(*rows))
    out['bus'] = np.where(out.ercot, b, '')
    out['zone'] = np.where(out.ercot, z, '')
    out['dist_to_substation_km'] = np.round(d1.astype(float), 2)
    out['bus_alt'] = np.where(out.ercot, alt, '')
    out['bus_alt_dist_km'] = np.round(d2.astype(float), 2)
    out['bus_boundary_tie'] = out.ercot & (d2.astype(float) - d1.astype(float) < 2.0)
    out['county_bus_consistent'] = [bool(e) and (bb in cbus.get(g, set())) for e, bb, g in zip(out.ercot, out.bus, out.GEOID)]
    return out


def atlas_qa(raw, at):
    """explicit duplicates (contained in another polygon), suspect same-campus clusters, crypto flags"""
    import geopandas as gpd
    f = raw / ATLAS_DIR / f'{ATLAS_DIR}.gpkg'
    g = pd.concat([gpd.read_file(f, layer=l)[['id', 'geometry']].assign(layer=l) for l in ('point', 'building', 'campus')], ignore_index=True)
    g['id'] = g['id'].astype(str)
    g = gpd.GeoDataFrame(g[g['id'].isin(set(at['id']))].drop_duplicates('id'), crs=4326).to_crs(5070).set_index('id')
    ids = list(at['id'])
    geom = g.geometry.reindex(ids)
    contained_in = {}
    for i in ids:
        gi = geom[i]
        if gi is None:
            continue
        for k in ids:
            if k == i or geom[k] is None or geom[k].geom_type == 'Point':
                continue
            gk = geom[k]
            if gi.geom_type == 'Point':
                hit = gk.contains(gi)
            else:
                hit = gk.area > gi.area and gi.intersection(gk).area >= 0.5 * gi.area
            if hit and (i not in contained_in or geom[contained_in[i]].area < gk.area):
                contained_in[i] = k                          # largest enclosing polygon
    # union-find: containment + same-operator proximity
    par = {i: i for i in ids}
    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for i, k in contained_in.items():
        par[find(i)] = find(k)
    op = at.set_index('id').operator.fillna('').str.strip().str.lower()
    suspect = set()
    for a_ in range(len(ids)):
        for b_ in range(a_ + 1, len(ids)):
            i, k = ids[a_], ids[b_]
            if not op[i] or op[i] != op[k] or geom[i] is None or geom[k] is None:
                continue
            if geom[i].distance(geom[k]) <= SUSPECT_M and find(i) != find(k):
                par[find(i)] = find(k); suspect |= {i, k}
    at = at.copy()
    at['contained_in_id'] = at['id'].map(contained_in).fillna('')
    at['site_cluster'] = [find(i) for i in at['id']]
    at['dup_class'] = np.where(at.contained_in_id != '', 'EXPLICIT_DUP_CONTAINED',
                               np.where(at['id'].isin(suspect), 'SUSPECT_SAME_CAMPUS', 'UNIQUE'))
    return at


def crypto(at):
    at = at.copy()
    nm = at.name.fillna('')
    checked = nm.isin(list(CRYPTO_CHECKED))
    screen = (nm + ' ' + at.operator.fillna('')).str.contains(CRYPTO_SCREEN, case=False, regex=True)
    cleared = nm.isin(list(CRYPTO_CLEARED))
    at['crypto_flag'] = np.where(checked, 'CRYPTO_CHECKED_EXCLUDED', np.where(cleared, 'CRYPTO_SCREEN_CLEARED', np.where(screen, 'CRYPTO_SCREEN_REVIEW', '')))
    at['crypto_basis'] = nm.map({**CRYPTO_CHECKED, **CRYPTO_CLEARED}).fillna('')
    return at


def build(raw):
    import geopandas as gpd
    cty, erc, cbus, sub = network()
    at = pd.read_csv(raw / ATLAS_DIR / f'{ATLAS_DIR}.csv', dtype={'id': str, 'state_id': str, 'county_id': str})
    tx = at[at.state_abb == 'TX']
    n_rows = len(tx)
    tx = tx.drop_duplicates('id').reset_index(drop=True)
    at = locate(tx[['id', 'operator', 'name', 'type', 'sqft', 'lon', 'lat']].copy(), cty, erc, cbus, sub)
    at = crypto(atlas_qa(raw, at))
    at = at.sort_values('id').reset_index(drop=True)
    at.to_csv(OUT / OUTPUTS[0], index=False, lineterminator='\n')
    pr = []
    for gw in GRAVITY:
        d = gpd.read_file(raw / PROJ_DIR / f'higher_growth_{gw}_market_gravity.geojson')
        d = d[d.region == 'texas'].copy()
        if d.crs is None:
            d = d.set_crs('ESRI:102003')
        c = d.geometry.centroid.to_crs(4326)
        pr.append(pd.DataFrame(dict(proj_id=d['id'].values, market_gravity_weight=gw, IT_MW=d.data_center_it_power_mw.values,
                                    weighted_siting_score=d.weighted_siting_score.values,
                                    normalized_locational_cost=d.normalized_locational_cost.values,
                                    normalized_gravity_score=d.normalized_gravity_score.values,
                                    lon=np.round(c.x.values, 6), lat=np.round(c.y.values, 6))))
    pr = locate(pd.concat(pr, ignore_index=True), cty, erc, cbus, sub)
    pr['growth_scenario'] = 'higher'
    pr = pr.sort_values(['market_gravity_weight', 'proj_id']).reset_index(drop=True)
    pr.to_csv(OUT / OUTPUTS[1], index=False, lineterminator='\n')
    # ---------------- per-bus summary (raw / explicit-dedup / clustered atlas counts)
    ep = pd.read_csv(OUT / 'EPOCH_TX_SITES_TAMU64.csv')
    ep = ep[ep.ercot & ep.bus.notna()]
    s = pd.DataFrame(index=pd.Index(sorted(sub.cluster_bus.unique()), name='bus'))
    s['zone'] = sub.groupby('cluster_bus').reeds_zone.first()
    s['epoch_sites'] = ep.groupby('bus').site.apply(lambda v: '; '.join(v))
    s['epoch_IT_MW_final'] = ep.groupby('bus').IT_MW_final.sum()
    ae = at[at.ercot]
    nc = ae[ae.crypto_flag != 'CRYPTO_CHECKED_EXCLUDED']
    s['atlas_n_sites'] = ae.groupby('bus').size()
    s['atlas_n_crypto_excluded'] = ae[ae.crypto_flag == 'CRYPTO_CHECKED_EXCLUDED'].groupby('bus').size()
    s['atlas_n_noncrypto_raw'] = nc.groupby('bus').size()
    s['atlas_n_noncrypto_explicit_dedup'] = nc[nc.dup_class != 'EXPLICIT_DUP_CONTAINED'].groupby('bus').size()
    s['atlas_n_noncrypto_clusters'] = nc.groupby('bus').site_cluster.nunique()
    s['atlas_sqft'] = ae.groupby('bus').sqft.sum()
    pe = pr[pr.ercot]
    for gw in GRAVITY:
        s[f'proj_higher_g{gw}_IT_MW'] = pe[pe.market_gravity_weight == gw].groupby('bus').IT_MW.sum()
    s = s.fillna({c: 0.0 for c in s.columns if c not in ('zone', 'epoch_sites')}).fillna({'epoch_sites': ''})
    pc = [f'proj_higher_g{gw}_IT_MW' for gw in GRAVITY]
    s['proj_higher_mean_IT_MW'] = s[pc].mean(axis=1)
    s['src_epoch'] = s.epoch_IT_MW_final > 0
    s['src_atlas'] = s.atlas_n_sites > 0
    s['src_atlas_noncrypto'] = s.atlas_n_noncrypto_raw > 0
    s['src_projected'] = s[pc].sum(axis=1) > 0
    s['candidate'] = s.src_epoch | s.src_atlas | s.src_projected
    s.reset_index().to_csv(OUT / OUTPUTS[2], index=False, lineterminator='\n')
    # ---------------- spatial mapping review (§3.5.3)
    rv = []
    for src, d in (('PNNL_ATLAS', at), ('PNNL_PROJECTED', pr)):
        d = d[d.ercot]
        m = d.bus_boundary_tie | (d.dist_to_substation_km > FAR_KM) | ~d.county_bus_consistent
        for r in d[m].itertuples():
            rv.append(dict(source=src, record_id=getattr(r, 'id', None) or f'g{r.market_gravity_weight}:{r.proj_id}', county=r.county,
                           lon=r.lon, lat=r.lat, bus=r.bus, bus_alt=r.bus_alt, dist_km=r.dist_to_substation_km, alt_dist_km=r.bus_alt_dist_km,
                           dist_gap_km=round(r.bus_alt_dist_km - r.dist_to_substation_km, 2), boundary_tie=bool(r.bus_boundary_tie),
                           far_from_substation=bool(r.dist_to_substation_km > FAR_KM), county_bus_consistent=bool(r.county_bus_consistent),
                           note='location evidence only; no POI contract implied'))
    ep_m = ep[ep.bus_boundary_tie.astype(bool)]
    for r in ep_m.itertuples():
        rv.append(dict(source='EPOCH', record_id=r.site, county=r.county, lon=r.lon, lat=r.lat, bus=r.bus, bus_alt=r.bus_alt,
                       dist_km=r.dist_to_substation_km, alt_dist_km=r.bus_alt_dist_km, dist_gap_km=round(r.bus_alt_dist_km - r.dist_to_substation_km, 2),
                       boundary_tie=True, far_from_substation=bool(r.dist_to_substation_km > FAR_KM), county_bus_consistent=None,
                       note='Epoch site: nearest kept (D12), flagged'))
    pd.DataFrame(rv).to_csv(OUT / OUTPUTS[3], index=False, lineterminator='\n')
    prov = dict(
        atlas=dict(dataset='IM3 Open Source Data Center Atlas v2026.02.09 (PNNL)', url='https://data.msdlive.org/records/p147s-4h760',
                   doi='https://doi.org/10.57931/3017294', licence='ODbL 1.0 (OpenStreetMap-derived)',
                   files={p.name: sha(p) for p in sorted((raw / ATLAS_DIR).iterdir()) if p.is_file()}),
        projected=dict(dataset='IM3 Projected US Data Center Locations v1.1 (PNNL, CERF-DC)', url='https://data.msdlive.org/records/r0cga-34g05',
                       doi='https://doi.org/10.57931/3020186', licence='CC BY 4.0',
                       citation='Mongird, K., Burleyson, C., Akdemir, K. Z., Vernon, C., & Rice, J. (2026). IM3 Projected US Data Center '
                                'Locations (v1.1) [Data set]. MSD-LIVE Data Repository. https://doi.org/10.57931/3020186',
                       horizon='new facilities through 2035, no per-facility year; higher growth = 15 %/yr data-center electricity growth from 2023 '
                               '(EPRI 2024); market-gravity weights are mutually exclusive simulation assumptions, not probabilities',
                       files={p.name: sha(p) for p in sorted((raw / PROJ_DIR).iterdir())}),
        network=dict(NETWORK_MAPPING_AUDIT=sha(BASE / 'NETWORK_MAPPING_AUDIT.csv'), COUNTY_TO_BUS_SHARES=sha(BASE / 'COUNTY_TO_BUS_SHARES.csv')),
        rule='county polygon -> ERCOT; nearest ERCOT TAMU substation -> 64s cluster bus (same as Epoch mapping)',
        atlas_qa=dict(suspect_same_campus_m=SUSPECT_M, crypto_checked=CRYPTO_CHECKED, crypto_screen=CRYPTO_SCREEN, far_from_substation_km=FAR_KM),
        counts=dict(atlas_TX_csv_rows=n_rows, atlas_TX_ids=len(at), atlas_ERCOT=int(at.ercot.sum()),
                    atlas_explicit_dup=int((at.dup_class == 'EXPLICIT_DUP_CONTAINED').sum()),
                    atlas_suspect_same_campus=int((at.dup_class == 'SUSPECT_SAME_CAMPUS').sum()),
                    atlas_site_clusters=int(at.site_cluster.nunique()),
                    atlas_crypto_checked=int((at.crypto_flag == 'CRYPTO_CHECKED_EXCLUDED').sum()),
                    atlas_crypto_screen_review=int((at.crypto_flag == 'CRYPTO_SCREEN_REVIEW').sum()),
                    projected_TX_rows=len(pr), projected_ERCOT_rows=int(pr.ercot.sum()),
                    candidate_buses=int(s.candidate.sum()), epoch_buses=int(s.src_epoch.sum()), atlas_buses=int(s.src_atlas.sum()),
                    atlas_noncrypto_buses=int(s.src_atlas_noncrypto.sum()), projected_buses=int(s.src_projected.sum()),
                    mapping_review_rows=len(rv)),
        outputs={o: sha(OUT / o) for o in OUTPUTS})
    (OUT / 'PNNL_PROVENANCE.json').write_bytes((json.dumps(prov, indent=1) + '\n').encode())
    return prov


def verify():
    prov = json.loads((OUT / 'PNNL_PROVENANCE.json').read_text())
    bad = {o: 'MISMATCH' for o, h in prov.get('outputs', {}).items() if not (OUT / o).exists() or sha(OUT / o) != h}
    return dict(mode='verify_tracked_outputs', ok=not bad, bad=bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', help='folder holding the two PNNL dataset folders (see raw/SHA256SUMS.txt)')
    a = ap.parse_args()
    raw = Path(a.raw) if a.raw else None
    if raw is None or not (raw / ATLAS_DIR).exists():
        r = verify()
        print(json.dumps(r, indent=1))
        sys.exit(0 if r['ok'] else 3)
    print(json.dumps(build(raw)['counts'], indent=1))


if __name__ == '__main__':
    main()
