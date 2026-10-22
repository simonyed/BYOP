#!/usr/bin/env python3
"""Mainline v1.3 WP-A / WP-B input tables (no solver; local or L2, from pypsa-usa/workflow):
    python byop/build/build_mainline_inputs.py

WP-A demand (D11, A1)
  dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv   research AIDC cohorts = ercot_cohorts_2026_2035_tamu64.csv minus the
                                            inherited late-2025 ramp (Epoch end-2025 IT - 2025 average IT per site),
                                            which the allocation queues first into the 2026 cohort (RA-DC-SPATIAL-05)
  dc/MAINLINE_INHERITED_RAMP_2025.csv       that ramp per bus: background facility load in EVERY scenario (S0-S3),
                                            never delayed by S2, never a POI Firm right for research demand
  dc/MAINLINE_AIDC_RECONCILIATION.csv       per scenario x year: approved total = inherited + research (exact), the
                                            2025 average stays inside the 2025 native load (not re-added)
  dc/MAINLINE_BUS_SITE_POI_MAP.csv          bus -> Epoch site -> POI evidence row (D12: one aggregated POI per bus)
WP-B G-REAL
  poi/GREAL_POI_ASSUMPTIONS.csv             one aggregated POI per Epoch bus (D12): upgrade path, procedure date,
                                            PCLR, gas evidence level; evidence class per field
  poi/GREAL_POI_E0_SCHEDULE.csv             existing / approved equipment available to research demand (facility MW)
  poi/GREAL_R_ASSET_POOL.csv                verified reusable units (D14: none verified -> empty, header only)
  grid/GREAL_GRID_PROJECTS.csv              committed / sensitivity / candidate transmission in G-REAL
  grid/GREAL_BACKGROUND_LOAD_RECONCILIATION.csv   2025 native load x AEO2023 TX factor; overlap with AIDC checked
  grid/GREAL_NETWORK_EVIDENCE.csv           network facts used by G-REAL with VERIFIED / DERIVED / PROXY / UNKNOWN
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
WF = HERE.parents[1]
INP = HERE.parent / 'inputs'
BASE = WF / 'results/BYOP/baseline_2025_tamu'
PUE = pd.read_csv(INP / 'dc/state_pue_2022_2050.csv')
pue = lambda y: float(PUE[(PUE.st == 'TX') & (PUE.year == y)].pue.iloc[0])

# --------------------------------------------------------------------------- POI evidence (D12), 2026-10-21 search
SRC = {
    'HELIOS': 'https://constructionreviewonline.com/news/galaxy-digital-secures-1-4b-to-fund-first-phase-of-helios-ai-data-center-in-texas/ ; '
              'https://blockspace.media/insight/galaxy-delivers-helios-to-coreweave/',
    'ABILENE': 'https://epoch.ai/publications/openai-stargate-where-the-us-sites-stand ; '
               'https://cleanview.co/reports/behind-the-meter-data-centers/full-report/stargate-abilene',
    'FRONTIER': 'https://wirelessestimator.com/articles/2025/digitalbridge-led-capital-fuels-vantages-new-25-billion-1-4-gw-frontier-data-center-in-texas/ ; '
                'https://cleanview.co/reports/behind-the-meter-data-centers/full-report/stargate-frontier',
    'DENTON': 'https://investors.corescientific.com/news-events/press-releases/detail/110/ ; '
              'https://epoch.ai/data/ai-data-centers/directory/coreweave-denton-tx',
    'EPOCH': 'https://epoch.ai/data/ai-data-centers (timeline; inputs/dc/EPOCH_TX_SITES_TAMU64.csv)',
    'BATCH0': 'ERCOT Batch Zero large-load process (SRC-03/10/12 in inputs/poi/SOURCE_EVIDENCE_REGISTER.csv)',
}
# E0: equipment / approved large-load capacity usable by RESEARCH demand (facility MW; the inherited stock's own use is
# subtracted). preapproved = no new Batch Zero allocation needed.
E0 = [
    # bus, site, MW, COD, preapproved, evidence_class, basis, source
    ('p600 0', 'Coreweave Helios', 800.0, 2026.0, True, 'VERIFIED_APPROVAL/PROXY_COD',
     'ERCOT-approved 800 MW (2024); first 133 MW delivered to CoreWeave 2026', SRC['HELIOS']),
    ('p600 0', 'Coreweave Helios', 830.0, 2028.0, True, 'VERIFIED_APPROVAL/PROXY_COD',
     'additional 830 MW approved Jan 2026 after LLIS, AEP Texas service agreement; COD = new station proxy (2 y)', SRC['HELIOS']),
    ('p610 2', 'OpenAI Stargate Abilene', None, 2026.0, True, 'VERIFIED_APPROVAL/DERIVED_MW',
     '1.2 GW approved ERCOT interconnection (Lancium) minus end-2025 stock facility MW', SRC['ABILENE']),
]
# Independent audit P0-3 (2026-10-21): campus equipment is no longer the Epoch final build-out at 2026. Each Epoch timeline
# step of an existing grid-served campus is classified from the dated timeline (raw Epoch data_center_timelines.csv,
# extracted to inputs/dc/EPOCH_TX_TIMELINE_EVIDENCE.csv):
#   EXISTING_ENERGIZED   observed operational on or before AS_OF (no estimate wording): physical service exists ->
#                        preapproved, earliest year = year of observed energization (year-level convention of the cohorts)
#   PLANNED_UNVERIFIED   future or estimated step without interconnection evidence -> NOT preapproved: earliest COD =
#                        max(Epoch estimated year, procedural earliest grid COD of the bus), bounded research proxy
# Verified ERCOT approvals (Helios, Abilene) stay as dated VERIFIED_APPROVAL rows above; Shackelford (ML13-02) and the
# Crusoe Abilene expansion have no grid evidence and use the POI-upgrade path only.
CAMPUS = ['Google Red Oak', 'Meta Temple', 'Google Midlothian', 'Vantage TX1', 'Microsoft SAT14', 'Microsoft SAT40', 'CoreWeave Denton TX']
AS_OF = pd.Timestamp('2026-10-21')
ESTIMATE = r'[Ee]stimat|projected|scheduled|[Bb]ased on the stated'     # imagery / earnings-call wording ('based on satellite imagery') = observed
import sys  # noqa: E402
sys.path.insert(0, str(HERE.parent / 'model'))
import byop_paths as BP  # noqa: E402
TIMELINE_RAW = BP.EPOCH_TIMELINE_RAW     # env BYOP_EPOCH_TIMELINE_RAW (C0: no personal drive path in code); unset = keep tracked extract
GAS = {   # bus: (level, lateral lead low/base/high y, lateral cost low/base/high USD/kW, note)
    'p610 2': ('L1', (0.5, 1.0, 2.0), (15, 30, 60), 'on-site aeroderivative turbines permitted at the Abilene campus (gas supply infrastructure exists; firm MDQ not public)'),
    'p630 4': ('L1', (0.5, 1.0, 2.0), (30, 60, 120), 'Vantage-VoltaGrid gas microgrid plan reported for Frontier (firm MDQ not public)'),
}
GAS_L2_NOTE = 'no public firm gas evidence for a large on-site plant: conservative bounded proxy (L2: lead 3 y, 100 USD/kW, MDQ 100,000 MMBtu/d)'


def main():
    sites = pd.read_csv(INP / 'dc/EPOCH_TX_SITES_TAMU64.csv')
    sites = sites[sites.ercot & sites.bus.notna()]
    coh = pd.read_csv(INP / 'dc/ercot_cohorts_2026_2035_tamu64.csv')
    tot = pd.read_csv(INP / 'dc/ERCOT_DC_TOTALS_2026_2035.csv')
    # ---------------- D11 inherited ramp
    ramp = sites.groupby('bus').agg(IT_MW_2025_avg=('IT_MW_2025_avg', 'sum'), IT_MW_2025_end=('IT_MW_2025', 'sum'),
                                    inherited_ramp_IT_MW=('IT_carryover_2025_MW', 'sum'),
                                    sites=('site', lambda s: '; '.join(s))).reset_index()
    ramp['facility_MW_2026'] = ramp.inherited_ramp_IT_MW * pue(2026)
    ramp['treatment'] = ('background facility load in all scenarios S0-S3 from 2026 (energized by end-2025 per Epoch timeline); '
                         'own shed variable protected by no-harm; not a POI Firm right for research demand')
    ramp['evidence_class'] = 'DERIVED (Epoch AI timeline end-2025 minus time-weighted 2025 average)'
    ramp = ramp[ramp.inherited_ramp_IT_MW > 0]
    ramp.to_csv(INP / 'dc/MAINLINE_INHERITED_RAMP_2025.csv', index=False, lineterminator=chr(10))
    # ---------------- research cohorts
    rc = coh.copy()
    rr = ramp.set_index('bus').inherited_ramp_IT_MW
    m26 = rc.request_year == 2026
    rc['inherited_ramp_IT_MW'] = np.where(m26, rc.region_id.map(rr).fillna(0.0), 0.0)
    rc['approved_cohort_IT_MW'] = rc.IT_MW
    rc['IT_MW'] = rc.approved_cohort_IT_MW - rc.inherited_ramp_IT_MW
    assert (rc.IT_MW >= -1e-6).all(), rc[rc.IT_MW < 0]
    rc['IT_MW'] = rc.IT_MW.clip(lower=0.0)
    rc['quality'] = 'RESEARCH_NEW_AIDC (approved total x Epoch geography minus D11 inherited ramp)'
    rc['status'] = 'MAINLINE v1.3 (D11)'
    rc.to_csv(INP / 'dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv', index=False, lineterminator=chr(10))
    # ---------------- reconciliation
    rec = []
    for (sc, y), g in rc.groupby(['scenario', 'request_year']):
        t = tot[(tot.scenario == sc) & (tot.year == y)].new_IT_MW.iloc[0]
        rec.append(dict(scenario=sc, year=y, approved_total_new_IT_MW=t, inherited_ramp_IT_MW=g.inherited_ramp_IT_MW.sum(),
                        research_new_IT_MW=g.IT_MW.sum(), sum_check_MW=g.inherited_ramp_IT_MW.sum() + g.IT_MW.sum() - t,
                        n_buses=g.region_id.nunique(), stock_2025_avg_IT_MW_in_background=float(sites.IT_MW_2025_avg.sum()),
                        old_three_test_POI_IT_MW=0.0, regional_dc_background_IT_MW=0.0, S0_research_IT_MW=0.0))
    rec = pd.DataFrame(rec)
    rec['research_cum_IT_MW'] = rec.groupby('scenario').research_new_IT_MW.cumsum()
    rec['check'] = np.where(rec.sum_check_MW.abs() < 1e-3, 'PASS', 'FAIL')
    rec.to_csv(INP / 'dc/MAINLINE_AIDC_RECONCILIATION.csv', index=False, lineterminator=chr(10))
    assert (rec.check == 'PASS').all()
    # ---------------- E0 schedule
    st = sites.set_index('site')
    stock_fac = lambda s: float(st.IT_MW_2025[s]) * pue(2025)
    e0 = []
    for bus, s, mw, cod, pre, ev, basis, src in E0:
        if mw is None and s == 'OpenAI Stargate Abilene':
            mw = 1200.0 - stock_fac(s)
        if mw is None and s == 'CoreWeave Denton TX':
            mw = 260.0 * pue(2026) - stock_fac(s)
        e0.append(dict(bus=bus, site=s, MW=round(mw, 1), COD=cod, preapproved=pre, evidence_class=ev, basis=basis, source=src))
    tl_f = INP / 'dc/EPOCH_TX_TIMELINE_EVIDENCE.csv'
    if TIMELINE_RAW is not None and TIMELINE_RAW.exists():      # refresh the small tracked extract from the local raw Epoch file
        t = pd.read_csv(TIMELINE_RAW)
        t = t[t['Data center'].isin(set(sites.site))].copy()
        t['date'] = pd.to_datetime(t.Date)
        t['status_text'] = t['Construction status'].astype(str).str.replace(r'\s+', ' ', regex=True).str.slice(0, 240)
        t['estimate_wording'] = t.status_text.str.contains(ESTIMATE, regex=True)
        t['observed_by_as_of'] = (t.date <= AS_OF) & ~t.estimate_wording
        t = t.rename(columns={'Data center': 'site', 'IT power (MW)': 'IT_MW', 'Power (MW)': 'power_MW'})
        t['raw_sha256'] = __import__('hashlib').sha256(TIMELINE_RAW.read_bytes()).hexdigest()
        t[['site', 'Date', 'IT_MW', 'power_MW', 'estimate_wording', 'observed_by_as_of', 'status_text', 'raw_sha256']].to_csv(tl_f, index=False, lineterminator=chr(10))
    tl = pd.read_csv(tl_f)
    tl['date'] = pd.to_datetime(tl.Date)
    for s in CAMPUS:
        r = st.loc[s]
        g = tl[tl.site == s].sort_values('date')
        prev = float(r.IT_MW_2025)                     # end-2025 stock (its own use is not research equipment)
        obs = g[g.observed_by_as_of]
        it_obs = max(prev, float(obs.IT_MW.max()) if len(obs) else prev)
        if it_obs > prev + 1e-6:
            d0 = obs[obs.IT_MW >= it_obs - 1e-6].date.min()
            e0.append(dict(bus=r.bus, site=s, MW=round((it_obs - prev) * pue(2026), 1), COD=float(max(2026, d0.year)), preapproved=True,
                           evidence_class='EXISTING_ENERGIZED (Epoch observed)', basis=f'Epoch timeline: {it_obs:.0f} MW IT operational by {d0.date()} '
                           f'minus end-2025 stock {prev:.0f} MW IT, x PUE 2026', source=SRC['EPOCH']))
            prev = it_obs
        for x in g[(~g.observed_by_as_of) & (g.IT_MW > prev + 1e-6)].itertuples():
            e0.append(dict(bus=r.bus, site=s, MW=round((x.IT_MW - prev) * pue(2026), 1), COD=float(max(2026, x.date.year)), preapproved=False,
                           evidence_class='PLANNED_UNVERIFIED (PROXY)', basis=f'Epoch {"estimate" if x.estimate_wording else "future step"} {x.IT_MW:.0f} MW IT on {x.date.date()}; '
                           'no interconnection evidence -> earliest COD = max(Epoch year, procedural earliest grid COD)', source=SRC['EPOCH']))
            prev = float(x.IT_MW)
    e0 = pd.DataFrame(e0)
    e0 = e0[e0.MW > 0.05].reset_index(drop=True)          # timeline rows without an IT increase carry no equipment
    e0.to_csv(INP / 'poi/GREAL_POI_E0_SCHEDULE.csv', index=False, lineterminator=chr(10))
    # ---------------- aggregated POI per bus (D12)
    mid = rc[(rc.scenario == 'mid') & (rc.request_year <= 2031)].groupby('region_id').IT_MW.sum()
    poi = []
    for bus, g in sites.groupby('bus'):
        lv, ll, lc, gn = GAS.get(bus, ('L2', (3.0, 3.0, 3.0), (100, 100, 100), GAS_L2_NOTE))
        fac31 = float(mid.get(bus, 0.0)) * pue(2031)
        poi.append(dict(
            site_id=bus, site_name=f'{bus} aggregated POI (' + '; '.join(g.site) + ')', bus=bus, lat=float(g.lat.mean()), lon=float(g.lon.mean()),
            epoch_sites='; '.join(g.site), research_IT_MW_2026_2031_mid=float(mid.get(bus, 0.0)), research_facility_MW_2031_mid=fac31,
            E0_total_MW=float(e0[e0.bus == bus].MW.sum()),
            poi_upgrade_max_MW=2000.0, poi_upgrade_lead_y_low=2.0, poi_upgrade_lead_y_base=3.0, poi_upgrade_lead_y_high=5.0,
            poi_upgrade_cost_USD_kW_low=80.0, poi_upgrade_cost_USD_kW_base=160.0, poi_upgrade_cost_USD_kW_high=300.0,
            earliest_grid_COD_low=2027.5, earliest_grid_COD_base=2028.0, earliest_grid_COD_high=2029.0,
            pclr_conditional_MW=round(0.3 * fac31, 1), pclr_conditional_COD_offset_y=0.0,
            gas_evidence_level=lv, gas_MDQ_MMBtu_d=np.nan,
            gas_lateral_lead_y_low=ll[0], gas_lateral_lead_y_base=ll[1], gas_lateral_lead_y_high=ll[2],
            gas_lateral_cost_USD_kW_low=lc[0], gas_lateral_cost_USD_kW_base=lc[1], gas_lateral_cost_USD_kW_high=lc[2],
            gas_note=gn,
            onsite_renewable_cap_MW=round(fac31, 1),
            ev_E0='see GREAL_POI_E0_SCHEDULE.csv', ev_upgrade='PROXY (new 345/138 kV large-load station; v1.0 POI_REGISTER range)',
            ev_procedure='PROXY (ERCOT Batch Zero: allocation 2027, energization >= 2028)', ev_pclr='PROXY (30 % of 2031 research facility MW)',
            ev_gas=f'{lv} PROXY', ev_onsite_renewable='PROXY (adjacent-land cap = 1.0 x 2031 research facility MW per technology; ReEDS bus cap shared with public)',
            confidence='C', run_status='PENDING_RESEARCHER_AUDIT', procedural_basis=SRC['BATCH0']))
    pd.DataFrame(poi).to_csv(INP / 'poi/GREAL_POI_ASSUMPTIONS.csv', index=False, lineterminator=chr(10))
    mp = sites[['site', 'owner', 'users', 'bus', 'county', 'lat', 'lon', 'geocode_precision', 'bus_alt', 'bus_boundary_tie',
                'IT_MW_2025_avg', 'IT_MW_2025', 'IT_carryover_2025_MW', 'IT_add_after_2025_MW', 'power_MW_final']].copy()
    mp['poi_id'] = mp.bus
    mp['poi_rule'] = 'D12: one aggregated POI per Epoch bus; site equipment rows in GREAL_POI_E0_SCHEDULE.csv are not shared rights of other campuses'
    mp['e0_rows'] = mp.site.map(e0.groupby('site').MW.sum()).fillna(0.0)
    mp['boundary_tie_note'] = np.where(mp.bus_boundary_tie, 'Shackelford tie p630 4 (10.6 km) vs p610 2 (10.8 km): nearest kept, flagged (not silently resolved)', '')
    mp.to_csv(INP / 'dc/MAINLINE_BUS_SITE_POI_MAP.csv', index=False, lineterminator=chr(10))
    pd.DataFrame(columns=['asset_id', 'bus', 'carrier', 'MW', 'unit_status', 'capacity_right', 'available_COD', 'evidence', 'source']).to_csv(
        INP / 'poi/GREAL_R_ASSET_POOL.csv', index=False, lineterminator=chr(10))
    # ---------------- grid projects
    gp = []
    for r in pd.read_csv(INP / 'grid/COMMITTED_BASE_ASSETS.csv').itertuples():
        gp.append(dict(project=r.asset_id, kind='committed TPIT increment (interface Link pair)', in_GREAL='COMMON_BASELINE' if r.case == 'MAIN' else 'NOT_IN_MAIN (sensitivity only)',
                       bus0=r.bus0, bus1=r.bus1, ISD=r.ISD, MW=r.MW, cost='sunk/committed (excluded from S differences)',
                       evidence_class='VERIFIED (ERCOT Feb-2026 board item 13)' if r.case == 'MAIN' else 'PROXY', source=r.source))
    for r in pd.read_csv(INP / 'poi/GRID_PROJECTS.csv').itertuples():
        gp.append(dict(project=r.project_id, kind='PUCT-approved 765 kV import path (Link pair)', in_GREAL='COMMON_BASELINE (ISD base, partial first year)',
                       bus0='nearest bus to from-point', bus1='nearest bus to to-point', ISD=r.ISD_base, MW=r.capacity_MW_base,
                       cost='sunk/committed', evidence_class='VERIFIED_STATUS/PROXY_MW_ISD', source=r.source_ids + '; ' + r.note))
    gp.append(dict(project='TAMU_corridor_reinforcement', kind='endogenous continuous reinforcement on every TAMU line (cap 100 % of rating)',
                   in_GREAL='CANDIDATE (priced, lead from TPIT 4 y base; approval cohorts, never free)', bus0='all', bus1='all', ISD='approval year + 4',
                   MW='<= existing rating', cost='PyPSA-USA line annuity (social r)', evidence_class='PROXY', source='D250-06 TPIT lead'))
    gp.append(dict(project='S0_CALIBRATION', kind='2025 deliverability repair of the synthetic network (min-uplift, background only)',
                   in_GREAL='COMMON_BASELINE (re-derived in Stage B step 0 with the G-REAL background incl. the inherited ramp)', bus0='7 lines', bus1='', ISD=2026,
                   MW='571 MW (v1.0) -> re-derived', cost='zero-cost calibration, evidence B, never triggered by research AIDC',
                   evidence_class='DERIVED', source='results/BYOP/rearch_s0repair/S0CAL_minuplift_2026_2031/S0_CALIBRATION.csv'))
    pd.DataFrame(gp).to_csv(INP / 'grid/GREAL_GRID_PROJECTS.csv', index=False, lineterminator=chr(10))
    # ---------------- background load reconciliation
    bl = pd.read_csv(BASE / 'BUS_LEDGER.csv', index_col=0)
    tr = pd.read_csv(INP / 'load/background_load_growth_states_AEO2023_reference.csv')
    tr = tr[tr.state == 'TX'].set_index('year').factor_vs_2025
    e25 = float(bl.energy_2025_TWh.sum()); p25 = float(bl.peak_load_2025_MW.sum())
    rows = []
    rmw = float(ramp.inherited_ramp_IT_MW.sum())
    for y in range(2026, 2032):
        f = float(tr.get(y, tr.iloc[-1]))
        rmid = rec[(rec.scenario == 'mid') & (rec.year <= y)].research_new_IT_MW.sum()
        rows.append(dict(year=y, native_load_2025_TWh=e25, AEO2023_TX_factor=f, background_TWh=e25 * f, background_peak_MW_noncoincident_bus_sum=p25 * f,
                         contains_2025_avg_epoch_IT_MW=float(sites.IT_MW_2025_avg.sum()), inherited_ramp_facility_MW=rmw * pue(y),
                         research_AIDC_cum_IT_MW_mid=rmid, research_AIDC_facility_MW_mid=rmid * pue(y),
                         overlap_rule='AEO2023 Reference growth carries no explicit large-load AIDC queue; ERCOT LTLF large-load officer letters are NOT added (they would double count the Epoch AIDC); no competing queued load at the AIDC buses',
                         evidence_class='DERIVED'))
    pd.DataFrame(rows).to_csv(INP / 'grid/GREAL_BACKGROUND_LOAD_RECONCILIATION.csv', index=False, lineterminator=chr(10))
    print(rec[rec.scenario == 'mid'].to_string())
    print(e0.to_string())


if __name__ == '__main__':
    main()
