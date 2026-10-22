#!/usr/bin/env python3
"""TECH_COMP_2 research-site county FIPS and permit status for the 16 dynamic_pnnl_v1 buses (A0.2 P3, no solver).
    python byop/build/build_tech_v2_site_permit.py
Rule (package 4 / ENV B): the FIPS is that of the REAL research site, never of the TAMU bus geometry or a PNNL candidate point.
  EPOCH_LEGACY bus  -> the county GEOID of its Epoch site(s) (inputs/dc/EPOCH_TX_SITES_TAMU64.csv, Epoch geocode); several
                       counties -> the most conservative ozone class among them (flag MULTI_COUNTY_CONSERVATIVE)
  PNNL_NEW_SITE bus -> no real site -> no FIPS -> UNKNOWN_CONSERVATIVE (flag NO_REAL_RESEARCH_SITE)
Writes inputs/tech_calibrated_v2/RESEARCH_SITE_COUNTY_FIPS_V2.csv (model input) and current_work_pckg/TECH_PERMIT_STATUS.csv.
"""
from __future__ import annotations

import hashlib, sys
from pathlib import Path

import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402
import byop_delivery_and_permit as D  # noqa: E402

POI = BP.INPUTS / 'poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv'
EPOCH = BP.INPUTS / 'dc/EPOCH_TX_SITES_TAMU64.csv'
ORDER = ['OZONE_NONATTAINMENT_2015', 'OZONE_NONATTAINMENT_2008_ONLY', 'UNKNOWN_CONSERVATIVE', 'ATTAINMENT_OR_UNCLASSIFIED']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    poi = pd.read_csv(POI)
    ep = pd.read_csv(EPOCH, dtype={'GEOID': str})
    t = D.ozone_table()
    rows = []
    for r in poi.itertuples():
        sites = ep[ep.bus == r.bus]
        if str(r.bus_class).startswith('EPOCH_LEGACY') and len(sites):
            fips = sorted(set(sites.GEOID.str.zfill(5)))
            cls = {f: D.county_class(f, t)[0] for f in fips}
            pick = sorted(fips, key=lambda f: ORDER.index(cls[f]))[0]
            flags = ['EPOCH_SITE_GEOCODE:' + ';'.join(sorted(set(sites.geocode_precision.astype(str))))]
            if len(fips) > 1:
                flags.append('MULTI_COUNTY_CONSERVATIVE')
            c, cf = D.county_class(pick, t)
            rows.append(dict(bus=r.bus, site_id=r.bus, research_site_basis='EPOCH_SITE', epoch_sites=';'.join(sites.site), counties=';'.join(sorted(set(sites.county))),
                             county_fips=pick, all_site_fips=';'.join(fips), ozone_class=c, flags=';'.join(flags + cf),
                             gas_evidence_level=r.gas_evidence_level, gas_lateral_lead_y_base=r.gas_lateral_lead_y_base,
                             fips_coverage='KNOWN_SITE_FIPS'))
        else:
            c, cf = D.county_class(None, t)
            rows.append(dict(bus=r.bus, site_id=r.bus, research_site_basis='NO_REAL_SITE (PNNL candidate bus)', epoch_sites='', counties='',
                             county_fips='', all_site_fips='', ozone_class=c, flags=';'.join(['NO_REAL_RESEARCH_SITE', 'BUS_GEOMETRY_NOT_USED'] + cf),
                             gas_evidence_level=r.gas_evidence_level, gas_lateral_lead_y_base=r.gas_lateral_lead_y_base,
                             fips_coverage='UNKNOWN_CONSERVATIVE'))
    df = pd.DataFrame(rows)
    assert len(df) == 16 and df.bus.is_unique
    for car in ('SOFC_NG', 'RICE', 'OCGT_aero', 'WIND', 'PV', 'BESS'):
        df[f'permit_lead_{car}_y'] = [D.permit_lead(car, c) for c in df.ozone_class]
    df['NG_EGU_SP_route_RICE'] = D.route_eligibility('RICE', None)
    df['NG_EGU_SP_route_OCGT_aero'] = D.route_eligibility('OCGT_aero', None)
    df['legal_status'] = 'RESEARCH_PROXY: area designation only; not a site permit determination'
    df['sources'] = f'POI {sha(POI)[:12]}; EPOCH {sha(EPOCH)[:12]}; OZONE {sha(D.T2.SRC / "BYOP_COUNTY_OZONE_RULES_2026.csv")[:12]}'
    return df


def main():
    df = build()
    df[['bus', 'site_id', 'research_site_basis', 'county_fips', 'all_site_fips', 'ozone_class', 'flags', 'gas_evidence_level',
        'gas_lateral_lead_y_base', 'fips_coverage', 'sources']].to_csv(D.T2.SRC / 'RESEARCH_SITE_COUNTY_FIPS_V2.csv', index=False, lineterminator='\n')
    df.to_csv(WF.parent / 'current_work_pckg/TECH_PERMIT_STATUS.csv', index=False, lineterminator='\n')
    print(df[['bus', 'counties', 'county_fips', 'ozone_class', 'fips_coverage']].to_string())


if __name__ == '__main__':
    main()
