#!/usr/bin/env python3
"""NEXT-01 A3-STATIC (no solver): environment -> permit -> COD -> service mechanism, evidence-separated.
    python byop/post/a3_static_mechanism.py [--out <dir>]
Writes PERMIT_GAS_EVIDENCE_PRIORITY.csv, PERMIT_TO_COD_CAUSAL_AUDIT_VNEXT.csv, PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv.
Main-case rows use only the repository evidence (GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv gas levels: L2 3 y / L1 1 y);
exactly ONE hypothetical counterfactual block (ozone county + fast reliable gas) is written with evidence_basis =
HYPOTHETICAL_MECHANISM_DEMONSTRATION and never feeds a model input.
"""
from __future__ import annotations

import argparse, sys
from pathlib import Path

import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402
import byop_tech_parameters_v2 as T2  # noqa: E402
import byop_delivery_and_permit as D  # noqa: E402

OZONE_BUSES = ['p630 2', 'p630 6', 'p630 9', 'p650 0']
# gas-delivery evidence found in this round (web, 2026-10-22); none is verified firm gas / MDQ for the research site
EVIDENCE = {
    'p630 2': dict(site='Google Red Oak (Ellis 48139)', found='no public report of on-site / behind-the-meter gas generation; Google Texas power = renewable PPAs',
                   pipeline_proximity='not established', firm_gas_or_MDQ='none found', contract='none found', lateral_construction='unknown',
                   sources='cleanview.co Red Oak Building 1 / 2; datacenterdynamics.com Red Oak campus; w.media Google $1bn Texas'),
    'p630 6': dict(site='Google Midlothian (Ellis 48139)', found='no on-site gas generation found; Google gas project is in Armstrong County (Goodnight / Crusoe), not Midlothian',
                   pipeline_proximity='not established', firm_gas_or_MDQ='none found', contract='none found', lateral_construction='unknown',
                   sources='cleanview.co Midlothian Building 1; datacenterdynamics.com Google $1bn Dallas; techcrunch.com 2026-03-17'),
    'p630 9': dict(site='CoreWeave Denton (Denton 48121)', found='site adjacent to the 225 MW Denton Energy Center (gas RICE plant) - proximity only; no site gas supply / MDQ found',
                   pipeline_proximity='near an existing gas plant (not a supply right)', firm_gas_or_MDQ='none found', contract='none found', lateral_construction='unknown',
                   sources='glennklockwood.com AI datacenters list; datacenterdynamics.com CoreWeave Denton; tipranks.com Denton grid'),
    'p650 0': dict(site='Vantage TX1 / Microsoft SAT (Bexar 48029)', found='Vantage West San Antonio campuses (Rogers Rd / Omicron Dr) report 405-423 MW behind-the-meter VoltaGrid gas generation under TCEQ minor-source permits, contested in a federal Clean Air Act suit (alleged source splitting); match to the Epoch site TX1 not verified; no MDQ / firm contract public',
                   pipeline_proximity='gas supply evidently exists for the developer campuses', firm_gas_or_MDQ='not public', contract='VoltaGrid power supply (generation), gas contract not public',
                   lateral_construction='built / under construction (one campus operating, one under construction)',
                   sources='tpr.org 2026-07-28; datacenterdynamics.com Vantage VoltaGrid lawsuit; news4sanantonio.com; law360.com 2528350'),
}


def evidence_table(sites):
    rows = []
    for b in OZONE_BUSES:
        s = sites[sites.bus == b].iloc[0]
        e = EVIDENCE[b]
        decision = ('KEEP_L2 (candidate evidence for researcher review: possible L1 if the Vantage campus = research site and a firm supply is documented)'
                    if b == 'p650 0' else 'KEEP_L2 (no additional evidence)')
        rows.append(dict(bus=b, county_fips=s.county_fips, ozone_class=s.ozone_class, repo_gas_level=s.gas_evidence_level, repo_lateral_lead_y=s.gas_lateral_lead_y_base,
                         **e, decision=decision, model_input_changed=False,
                         permit_risk_note=('TCEQ minor-source permits contested (source-splitting allegation); reported state pause of data-center permits - '
                                           'permit path is a real risk, not only a duration' if b == 'p650 0' else '')))
    return pd.DataFrame(rows)


def audit(sites, J, T):
    rows = []
    for s in sites.itertuples():
        for t in T2.TECHS:
            for path in (T2.PATHS if t in ('RICE', 'OCGT_aero') else ('DEFAULT_ENV',)):
                a = D.cod(t, 2026, s.county_fips or None, path, gas_lead_years=float(s.gas_lateral_lead_y_base) if t in T2.GAS_TECHS else None, J=J, T=T)
                tl = {r['year']: r for r in D.delivery_timeline(a['COD_real'])}
                rows.append(dict(scenario_block='MAIN_EVIDENCE', evidence_basis=f'repository gas level {s.gas_evidence_level} ({s.gas_lateral_lead_y_base} y)',
                                 bus=s.bus, **{k: a[k] for k in ('tech', 'permit_path', 'ozone_class', 'permit_lead_years_proxy', 'equipment_ready', 'gas_ready',
                                                                 'preconstruction_release', 'final_permit_ready', 'COD_without_permit_constraints', 'COD_real',
                                                                 'permit_attributable_COD_delay_years', 'COD_binding_milestone', 'first_full_firm_year')},
                                 first_energizable_time=a['COD_real'],
                                 first_full_firm_year_without_permit=int(__import__('math').ceil(a['COD_without_permit_constraints'] - 1e-9)),
                                 permit_shift_of_first_full_firm_year=int(__import__('math').ceil(a['COD_real'] - 1e-9)) - int(__import__('math').ceil(a['COD_without_permit_constraints'] - 1e-9)), **{f'energy_fraction_{y}': tl[y]['energizable_fraction'] for y in tl},
                                 **{f'full_firm_{y}': tl[y]['full_firm'] for y in tl}, status='DRY_NOT_SOLVED'))
    # the ONE hypothetical counterfactual: ozone county + fast reliable gas (not evidence, not a model input)
    for lead in (0.5, 1.0):
        for t in T2.GAS_TECHS:
            for path in (T2.PATHS if t != 'SOFC_NG' else ('DEFAULT_ENV',)):
                a = D.cod(t, 2026, '48029', path, gas_lead_years=lead, J=J, T=T)
                tl = {r['year']: r for r in D.delivery_timeline(a['COD_real'])}
                rows.append(dict(scenario_block='HYPOTHETICAL_COUNTERFACTUAL', evidence_basis=f'HYPOTHETICAL_MECHANISM_DEMONSTRATION: Bexar ozone county + reliable gas in {lead} y',
                                 bus='p650 0 (hypothetical)', **{k: a[k] for k in ('tech', 'permit_path', 'ozone_class', 'permit_lead_years_proxy', 'equipment_ready', 'gas_ready',
                                                                                   'preconstruction_release', 'final_permit_ready', 'COD_without_permit_constraints', 'COD_real',
                                                                                   'permit_attributable_COD_delay_years', 'COD_binding_milestone', 'first_full_firm_year')},
                                 first_energizable_time=a['COD_real'],
                                 first_full_firm_year_without_permit=int(__import__('math').ceil(a['COD_without_permit_constraints'] - 1e-9)),
                                 permit_shift_of_first_full_firm_year=int(__import__('math').ceil(a['COD_real'] - 1e-9)) - int(__import__('math').ceil(a['COD_without_permit_constraints'] - 1e-9)), **{f'energy_fraction_{y}': tl[y]['energizable_fraction'] for y in tl},
                                 **{f'full_firm_{y}': tl[y]['full_firm'] for y in tl}, status='DRY_NOT_SOLVED (illustration only)'))
    return pd.DataFrame(rows)


def partial_year_qa():
    """pure delivery_timeline vs the model rules v240_mech.avail_frac / firm_frac (annual periods, fractional COD, full-year firm)"""
    import v240_mech as M
    saved = dict(M.CFG)
    M.CFG.update(periods='annual', start=2026, end=2031, frac_cod=True, firm_full_year=True)
    rows = []
    try:
        for cod in (2027.0, 2027.25, 2027.5, 2027.75, 2028.0, 2029.0, 2031.5):
            bp = M.first_period(cod)
            for r in D.delivery_timeline(cod, facility_MW=100.0, pue=1.1484):
                af = M.avail_frac(bp, cod, r['year']) if bp is not None else 0.0
                ff = M.firm_frac(bp, cod, r['year']) if bp is not None else 0.0
                rows.append(dict(COD_real=cod, build_period=bp, year=r['year'], pure_energy_fraction=r['energizable_fraction'], model_avail_frac=af,
                                 pure_full_firm=r['full_firm'], model_firm_frac=ff, partial_year_service_MWh_100MW=round(r['partial_year_service_MWh'], 3),
                                 delivered_IT_MW_year_firm=round(r['delivered_IT_MW_year_firm'], 6), delivered_IT_MW_year_energy_equiv=round(r['delivered_IT_MW_year_energy_equiv'], 6),
                                 consistent=abs(af - r['energizable_fraction']) < 1e-9 and (ff == 1.0) == r['full_firm'],
                                 note='partial years: energy counted, no full-year Firm credit'))
    finally:
        M.CFG.clear(); M.CFG.update(saved)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(WF.parent / 'current_work_pckg'))
    a = ap.parse_args()
    out = Path(a.out)
    J, T = T2.load()
    sites = pd.read_csv(T2.SRC / 'RESEARCH_SITE_COUNTY_FIPS_V2.csv', dtype={'county_fips': str}, keep_default_na=False)
    ev = evidence_table(sites)
    ev.to_csv(out / 'PERMIT_GAS_EVIDENCE_PRIORITY.csv', index=False, lineterminator='\n')
    au = audit(sites, J, T)
    au.to_csv(out / 'PERMIT_TO_COD_CAUSAL_AUDIT_VNEXT.csv', index=False, lineterminator='\n')
    q = partial_year_qa()
    q.to_csv(out / 'PARTIAL_YEAR_DELIVERY_CONSISTENCY_QA.csv', index=False, lineterminator='\n')
    m = au[au.scenario_block == 'MAIN_EVIDENCE']; h = au[au.scenario_block == 'HYPOTHETICAL_COUNTERFACTUAL']
    print('main rows', len(m), 'permit delay > 0:', int((m.permit_attributable_COD_delay_years > 0).sum()))
    print(h[['evidence_basis', 'tech', 'permit_path', 'COD_real', 'COD_without_permit_constraints', 'permit_attributable_COD_delay_years', 'first_full_firm_year', 'first_full_firm_year_without_permit', 'permit_shift_of_first_full_firm_year']].to_string())
    print('partial-year QA consistent:', bool(q.consistent.all()), len(q))


if __name__ == '__main__':
    main()
