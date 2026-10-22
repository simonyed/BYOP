"""TECH_COMP_2 delivery, permit and COD pure functions (A0.2 P3a / P3b, no solver).

Mechanism (ENVIRONMENT_SPEED_TO_POWER_IMPLEMENTATION.md): technology / controls -> emissions + site-wide NOx PTE screen ->
air-permit route eligibility (county ozone class from the ORIGINAL 19-FIPS table) -> research-proxy permit lead (original v2.0
JSON permit.values_years_from_order) -> construction release + final permit milestone -> COD_real -> first full Firm year.

    q = order year
    permit_lead          = TECH_V2.permit.values_years_from_order[county_class][tech]        (research proxy, not a TCEQ duration)
    preconstruction_lead = permit_lead unless traceable evidence says construction may legally start earlier (DEFAULT, never NaN)
    equipment_ready      = q + equipment_order_to_arrival_years ; civil_ready = q + civil_ready_from_order_years
    construction_release = q + preconstruction_lead
    installation_done    = max(equipment_ready, civil_ready, construction_release) + site_install_commission_years
    COD_real             = max(installation_done, q + permit_lead, gas_ready (gas techs), electrical_ready)
    COD_without_permit   = same with every permit milestone removed (NON-COMPLIANT attribution counterfactual, never an option)
    permit_attributable_COD_delay = max(0, COD_real - COD_without_permit)   (0 whenever the permit is not on the critical path)
    first_full_firm_year = ceil(COD_real) (an integer COD gives that year; 2027.25 -> 2028: partial years carry energy only)

CONTROLLED_ENV lowers NOx (and adds control CAPEX / FOM) but keeps the same permit lead (the source table grants no time
difference). The 2025 TCEQ NG-EGU standard permit can only apply to verified spark-ignited pipeline-gas engines; turbines never;
'RICE_50DF' by name does not qualify. Eligibility is reported, it does not shorten the proxy lead (no source value for that).
"""
from __future__ import annotations

import math

import pandas as pd

import byop_tech_parameters_v2 as T2

CLASSES = ['ATTAINMENT_OR_UNCLASSIFIED', 'OZONE_NONATTAINMENT_2015', 'OZONE_NONATTAINMENT_2008_ONLY', 'UNKNOWN_CONSERVATIVE']
ELECTRICAL_READY_LEAD_Y = 0.5      # research proxy of the package's static examples (on-site electrical / safety readiness)
GAS_LEAD_BY_LEVEL_FALLBACK = {'L2': 3.0}   # L2 unknown supply: conservative 3 y (rearch_mech.GAS_L2) when no site value is given


def ozone_table():
    t = pd.read_csv(T2.SRC / 'BYOP_COUNTY_OZONE_RULES_2026.csv', dtype={'county_fips': str})
    assert len(t) == 19 and t.county_fips.is_unique, 'original ozone table must have 19 unique FIPS'
    return t.set_index('county_fips')


def county_class(fips, table=None):
    """(class, flags) from the ORIGINAL table; missing FIPS -> UNKNOWN_CONSERVATIVE; known FIPS not listed -> research class
    ATTAINMENT_OR_UNCLASSIFIED with NOT_IN_LIST_NOT_FULL_LEGAL_VERIFICATION (never an all-pollutant attainment certificate)"""
    t = ozone_table() if table is None else table
    if fips is None or (isinstance(fips, float) and math.isnan(fips)) or str(fips).strip() in ('', 'nan', 'None'):
        return 'UNKNOWN_CONSERVATIVE', ['NO_SITE_FIPS']
    f = str(fips).split('.')[0].zfill(5)
    if f in t.index:
        r = t.loc[f]
        return str(r.classification_FOR_MODEL), [f'nonattainment_2015={int(r.nonattainment_2015_ozone)}', f'nonattainment_2008={int(r.nonattainment_2008_ozone)}',
                                                 str(r.evidence_class)]
    return 'ATTAINMENT_OR_UNCLASSIFIED', ['NOT_IN_LIST_NOT_FULL_LEGAL_VERIFICATION']


def permit_lead(tech, cls, J=None):
    J = J or T2.load()[0]
    v = J['permit']['values_years_from_order'][cls][tech]
    if v is None:
        raise ValueError(f'no permit proxy for {tech} / {cls}')
    return float(v)


def route_eligibility(tech, equipment_type=None, permit_path='DEFAULT_ENV'):
    """research screen of the special 2025 NG-EGU standard-permit route (eligibility only, no lead change)"""
    if tech == 'OCGT_aero':
        return 'NG_EGU_SP_NOT_APPLICABLE_TURBINE (case-by-case / turbine NSR authorisation)'
    if tech == 'RICE':
        if equipment_type == 'SI_PIPELINE_NG_VERIFIED':
            return 'NG_EGU_SP_POSSIBLE_PENDING_ALL_CONDITIONS (not a determination)'
        return 'NG_EGU_SP_NOT_ESTABLISHED (no verified spark-ignited pipeline-gas evidence; RICE_50DF name is not proof)'
    if tech == 'SOFC_NG':
        return 'NO_GENERAL_EXEMPTION_ESTABLISHED (low NOx = potential route advantage only; not the NG-EGU engine permit)'
    return 'NON_COMBUSTION (site / land / fire / construction permits still apply; lead > 0)'


def cod(tech, order_year, county_fips=None, permit_path='DEFAULT_ENV', gas_lead_years=None, gas_evidence=None,
        electrical_lead_years=ELECTRICAL_READY_LEAD_Y, preconstruction_lead_years=None, preconstruction_evidence=None,
        equipment_type=None, J=None, T=None):
    """all milestones of one candidate (pure function); returns a dict row of PERMIT_TO_COD_CAUSAL_AUDIT"""
    if J is None or T is None:
        J, T = T2.load()
    x = T[tech]
    q = float(order_year)
    cls, flags = county_class(county_fips)
    pl = permit_lead(tech, cls, J)
    pre = pl if preconstruction_lead_years is None else float(preconstruction_lead_years)
    if preconstruction_lead_years is not None and not preconstruction_evidence:
        raise ValueError('an earlier legal construction start needs traceable evidence (preconstruction_evidence)')
    eq = q + float(x['equipment_order_to_arrival_years'])
    civ = q + float(x['civil_ready_from_order_years'])
    inst = float(x['site_install_commission_years'])
    rel = q + pre
    fin = q + pl
    gas_tech = tech in T2.GAS_TECHS
    if gas_tech:
        if gas_lead_years is None:
            if gas_evidence not in GAS_LEAD_BY_LEVEL_FALLBACK:
                raise ValueError(f'{tech}: gas readiness needs the site lateral lead (evidence {gas_evidence}); no 0 / infinite default')
            gas_lead_years = GAS_LEAD_BY_LEVEL_FALLBACK[gas_evidence]
        gas_ready = q + float(gas_lead_years)
    else:
        gas_ready = None
    el = q + float(electrical_lead_years)
    installation_done = max(eq, civ, rel) + inst
    cands = dict(installation_done=installation_done, final_permit_ready=fin, electrical_ready=el)
    if gas_ready is not None:
        cands['gas_ready'] = gas_ready
    cod_real = max(cands.values())
    inst_wo = max(eq, civ, q) + inst
    wo = dict(installation_done=inst_wo, electrical_ready=el, **({'gas_ready': gas_ready} if gas_ready is not None else {}))
    cod_wo = max(wo.values())
    binding = [k for k, v in cands.items() if abs(v - cod_real) < 1e-9]
    if 'installation_done' in binding and abs(rel + inst - cod_real) < 1e-9 and rel >= max(eq, civ) - 1e-12 and rel > q:
        binding = binding + ['construction_release(permit)']
    ffy = int(math.ceil(cod_real - 1e-9))
    rate = T2.nox_rate(tech, permit_path, T) if gas_tech else 0.0
    return dict(tech=tech, order_year=q, county_fips=county_fips, ozone_class=cls, class_flags=';'.join(flags), permit_path=permit_path,
                permit_route_eligibility_status=route_eligibility(tech, equipment_type, permit_path), permit_lead_years_proxy=pl,
                preconstruction_lead_years=pre, preconstruction_basis='evidence: ' + str(preconstruction_evidence) if preconstruction_lead_years is not None else 'DEFAULT = permit lead (no evidence of legal parallel construction)',
                equipment_ready=eq, civil_ready=civ, preconstruction_release=rel, final_permit_ready=fin, gas_ready=gas_ready,
                electrical_ready=el, installation_done=installation_done, COD_without_permit_constraints=cod_wo, COD_real=cod_real,
                permit_attributable_COD_delay_years=round(max(0.0, cod_real - cod_wo), 9), COD_binding_milestone='+'.join(binding),
                first_full_firm_year=ffy, NOx_kg_per_MWh=rate, CO2_t_per_MWh=float(x['CO2_t_per_MWh']),
                proxy_evidence_class=str(J['permit']['source_status']), status='DRY_NOT_SOLVED')


def firm_full_year(cod_real, year):
    """full-year Firm credit only for years entirely after COD (2027.25 -> no Firm in 2027)"""
    return float(year) >= cod_real - 1e-9
