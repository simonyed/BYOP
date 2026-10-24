#!/usr/bin/env python3
"""NEXT-10U H1 (2026-10-24): engineering POI inputs of model version engineering_cost_v1 (no solver, no download).

Replaces the uniform POI proxy of GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv (poi_upgrade_lead_y_base = 3, poi_upgrade_max_MW =
2,000 per approval cohort, earliest_grid_COD_base = 2028) by project-level evidence layers, read from the verified engineering
data package (data/byop/engineering_v1, SHA-pinned below; raw / processed are never tracked in git):

  equipment   E0 / E1 known equipment with its own COD: poi_equipment_proxy_schedule.csv (delivered / operating lower bounds) plus
              Helios I Phase II (260 MW IT under construction since April 2026, data-hall deliveries from Q2 2027, Galaxy Q2 2026
              release). An approved capacity right is NOT equipment (poi_e0_evidence_classified.csv public_claim_kind).
  rights      approved capacity (Helios 1,630 MW, Abilene 955.6 MW residual) = the share of new equipment that needs no new study
              (class RIGHTED); everything else is a NEW_REQUEST that waits for a studied allocation (Batch Zero study years 2028-2032).
  candidates  U[s, class, q] >= 0, q = commitment year; COD = max(q + large-power-transformer lead, procedural floor of the class).
              Lead = NEMA 2026-10: 120-210 weeks for large power transformers (low / base / high = 120 / 165 / 210 weeks); the
              components run in parallel, the latest one sets the COD (never summed). LOCAL_POI_UPGRADE stays disabled (upper bound 0:
              no site-specific spare-bay / reuse evidence) - this is a policy, not an observation.
  caps        cumulative over q per class and per site (never one cap per commitment year), and the disclosure constraint
              sum_{class, q <= Q} U <= max(0, announced facility envelope by Q - known equipment).
Outputs: tracked model inputs in byop/inputs/poi_eng/ and the H1 audits in current_work_pckg/BYOP_NEXT_10U/H1/.
Run from pypsa-usa/workflow:  python byop/build/build_engineering_poi_v1.py [--check]
"""
from __future__ import annotations

import argparse, hashlib, json, math, sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
WF = HERE.parents[1]
ROOT = WF.parent
DATA = WF / 'data/byop/engineering_v1'
OUT = WF / 'byop/inputs/poi_eng'
AUD = ROOT / 'current_work_pckg/BYOP_NEXT_10U/H1'
OLD_POI = WF / 'byop/inputs/poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv'      # only the non-POI columns are carried (gas, PCLR, on-site RE)
COHORTS = WF / 'byop/inputs/dc/MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv'
MODEL_VERSION = 'engineering_cost_v1'

# verified against the engineering package FILE_SHA256.csv (65 / 65 raw + processed files byte-identical, NEXT-10U H0)
SOURCES = {
    'processed/poi_e0_evidence_classified.csv': '316bc3b83cec84df61c8b325ab2e5d28cbef0bd3659a2a94fd6805fa042beacb',
    'processed/poi_equipment_proxy_schedule.csv': '3945e8c47d435af54bd57b25cfcecdcf4101fe650caf5d09f2ba424af413edf8',
    'processed/poi_site_release_parameters.csv': '47ef8278b64049e94ba17ea4e20709c9d4381ba08d02d6d4afb364d0ac8b204b',
    'processed/poi_engineering_parameters.csv': 'db080871569ed6a6a9e55ed770977f45944b69c60cf9b1ecec391fe8443e7e15',
    'processed/poi_demand_visibility.csv': 'f90c9e4cae47c46ca8806d17969eed5fed5d3f4bd0f01fa8643d8eba7dc2788b',
    'processed/poi_investment_candidates.csv': '1f19bcd41fb47e0d932cc7508f9d903a4ccb3a1448ab61edc48eab9496e848ab',
    'reference/config/engineering_baseline.json': 'ead0f51c961bedae283e1c37b194df63f8f26e2969e5225e40d53492f56cc801',
    'raw/engineering/NEMA_2026_10.pdf': '9e6f755bff05a4b753fc3890b6daf31db4c6182b212cc3e5f41bf9b93c8ac4e5',
    'raw/ercot/Batch_Zero_Readiness_FAQs_V8.1.xlsx': 'f73b83879302766a9bdeadb991c8ae865bfcbd69d6b9e3dc0ae9ffcaa0565abb',
    'raw/ercot/BatchZero-Timeline-and-Communications.pptx': 'ce7d3784f5df886c3c3964541f727017fc2f38e538b7d3cca4cc622355cd6926',
    'raw/ercot/13-Far-West-Load-Growth-and-Transmission-Timing-Issues.pdf': '7eb9d4a530613466c7ddbb70fea13dee337bf16702283a2485896edb4ab20eb8',
    'raw/pages/GALAXY_Q2_2026.html': '54e180f2a3e2b3e5143d22cea45d556f172ad8bca6af269f856deb4dfd1ca2ba',
}
WEEKS_PER_YEAR = 365.25 / 7.0
TX_WEEKS = dict(low=120.0, base=165.0, high=210.0)      # NEMA 2026-10 p.2: "delays of 120 to 210 weeks for large transformers"
SWGR_WEEKS = dict(low=40.0, base=60.0, high=80.0)       # NEMA 2026-10 p.2: medium-voltage switchgear 40-80 weeks (parallel, not binding)
BATCH_ZERO_FLOOR = 2028.0     # ERCOT Batch Zero FAQ v8.1: the Batch Zero Interconnection Study studies / allocates 2028-2032 (LCP rows)
DECISION_YEAR, LAST_YEAR = 2026, 2031                   # mainline model window (commitment years beyond it cannot reach a period)
GRID_LIFE = 40
HELIOS_GROSS_PER_IT = 200.0 / 133.0                     # Phase I as delivered: 200 MW gross power / 133 MW critical IT (Galaxy Q2 2026)
HELIOS_P2_IT, HELIOS_P2_COD = 260.0, 2027.5             # Phase II 260 MW IT, deliveries "expected to begin in Q2 2027" -> end of Q2 proxy
CARRY = ['site_id', 'site_name', 'bus', 'lat', 'lon', 'research_IT_MW_2026_2031_mid', 'research_facility_MW_2031_mid', 'pclr_conditional_MW',
         'pclr_conditional_COD_offset_y', 'gas_evidence_level', 'gas_MDQ_MMBtu_d', 'gas_lateral_lead_y_low', 'gas_lateral_lead_y_base',
         'gas_lateral_lead_y_high', 'gas_lateral_cost_USD_kW_low', 'gas_lateral_cost_USD_kW_base', 'gas_lateral_cost_USD_kW_high', 'gas_note',
         'onsite_renewable_cap_MW', 'ev_pclr', 'ev_gas', 'ev_onsite_renewable', 'confidence', 'siting_variant', 'bus_class']
FORBIDDEN = ['poi_upgrade_max_MW', 'poi_upgrade_lead_y_low', 'poi_upgrade_lead_y_base', 'poi_upgrade_lead_y_high', 'poi_upgrade_cost_USD_kW_low',
             'poi_upgrade_cost_USD_kW_base', 'poi_upgrade_cost_USD_kW_high', 'earliest_grid_COD_low', 'earliest_grid_COD_base', 'earliest_grid_COD_high',
             'E0_total_MW', 'ev_E0', 'ev_upgrade', 'ev_procedure', 'procedural_basis', 'run_status']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def first_full_year(cod):
    return int(math.ceil(cod - 1e-9))


def verify_sources(data=DATA):
    bad = []
    for rel, h in SOURCES.items():
        p = data / rel
        if not p.is_file():
            bad.append(f'missing {rel}')
        elif sha(p) != h:
            bad.append(f'SHA differs {rel}')
    return bad


def build(data=DATA):
    bad = verify_sources(data)
    if bad:
        raise SystemExit('ENGINEERING_DATA FAIL-CLOSED: ' + '; '.join(bad))
    P = lambda f: pd.read_csv(data / 'processed' / f)
    e0, eqp, rel_, eng, vis, cand = (P('poi_e0_evidence_classified.csv'), P('poi_equipment_proxy_schedule.csv'), P('poi_site_release_parameters.csv'),
                                     P('poi_engineering_parameters.csv'), P('poi_demand_visibility.csv'), P('poi_investment_candidates.csv'))
    base_json = json.loads((data / 'reference/config/engineering_baseline.json').read_text(encoding='utf-8'))
    old = pd.read_csv(OLD_POI)
    coh = pd.read_csv(COHORTS)
    coh = coh[coh.scenario == 'mid']
    # ---------------------------------------------------------------- G0 input checks (fail closed)
    assert len(rel_) == 16 and rel_.site_id.is_unique, 'poi_site_release_parameters: 16 unique sites expected'
    assert len(vis) == 160 and len(cand) == 320, 'visibility 160 / candidates 320 rows expected (package history)'
    assert set(rel_.site_id) == set(old.site_id) == set(coh.region_id), 'site sets differ between engineering package, POI table and cohorts'
    j = pd.concat([coh.groupby(['region_id', 'request_year']).IT_MW.sum().rename_axis(['site_id', 'request_year']).rename('coh'),
                   vis.set_index(['site_id', 'request_year']).increment_it_mw.rename('vis')], axis=1)
    assert not j.isna().any().any() and float((j.coh - j.vis).abs().max()) < 1e-6, 'visibility increments differ from the model research cohorts'
    for c in ('existing_equipment_proxy_mw', 'approved_capacity_proxy_mw', 'site_equipment_cumulative_cap_mw', 'grid_route_cumulative_cap_mw'):
        assert rel_[c].notna().all() and (rel_[c] >= 0).all(), f'{c}: NaN or negative'
    assert (rel_.local_route_enabled == 0).all(), 'LOCAL route enabled somewhere without site evidence'
    g = eng.set_index('engineering_type')
    unit_cost = float(g.loc['GRID_DEPENDENT_POI', 'cost_base_2025USD_kW']) * 1000.0           # USD/MW
    unit_cost_low, unit_cost_high = (float(g.loc['GRID_DEPENDENT_POI', k]) * 1000.0 for k in ('cost_low_2025USD_kW', 'cost_high_2025USD_kW'))
    tx = {k: round(v / WEEKS_PER_YEAR, 4) for k, v in TX_WEEKS.items()}
    sw = {k: round(v / WEEKS_PER_YEAR, 4) for k, v in SWGR_WEEKS.items()}

    # ---------------------------------------------------------------- known equipment (E0 / E1)
    known = []
    for r in eqp.itertuples():
        known.append(dict(asset_id=r.asset_id, site_id=r.site_id, MW=float(r.equipment_mw), COD=float(r.cod_decimal),
                          firm_first_full_year=first_full_year(float(r.cod_decimal)),
                          evidence_level='E0', evidence_status=r.evidence_status, allocation_scope=r.allocation_scope,
                          source='processed/poi_equipment_proxy_schedule.csv', source_sha256=SOURCES['processed/poi_equipment_proxy_schedule.csv'],
                          real_or_proxy='OBSERVED_LOWER_BOUND' if 'DELIVERY' in r.evidence_status else 'INHERITED_OPERATING_LOAD_PROXY'))
    p2 = round(HELIOS_P2_IT * HELIOS_GROSS_PER_IT, 1)
    known.append(dict(asset_id='EQUIPMENT_E1_p600_0_HELIOS_I_PHASE_II', site_id='p600 0', MW=p2, COD=HELIOS_P2_COD,
                      firm_first_full_year=first_full_year(HELIOS_P2_COD), evidence_level='E1',
                      evidence_status='UNDER_CONSTRUCTION_SINCE_2026-04; DATA_HALL_DELIVERIES_EXPECTED_FROM_Q2_2027; WITHIN_HELIOS_I_800MW_APPROVAL',
                      allocation_scope='LEGACY_BUS_AGGREGATION_PROXY; REQUIRES_OWNER_MATCH_FOR_CAMPUS_SPECIFIC_CLAIMS',
                      source='raw/pages/GALAXY_Q2_2026.html', source_sha256=SOURCES['raw/pages/GALAXY_Q2_2026.html'],
                      real_or_proxy=f'DISCLOSED_SCHEDULE; MW = 260 MW IT x Phase I gross/IT ratio {HELIOS_GROSS_PER_IT:.4f}; COD = end of Q2 2027 (start of deliveries)'))
    known = pd.DataFrame(known)
    kn_site = known.groupby('site_id').MW.sum()
    # Helios I approval (800 MW) must hold the delivered Phase I and Phase II equipment
    assert kn_site.get('p600 0', 0.0) <= 800.0 + 1e-6, 'Helios known equipment exceeds the Helios I 800 MW approval'

    # ---------------------------------------------------------------- rights and cumulative caps
    sites, rights_rows, caps = [], [], {}
    for r in rel_.itertuples():
        s = r.site_id
        kn = float(kn_site.get(s, 0.0))
        site_cap = float(r.site_equipment_cumulative_cap_mw)           # max(approved right, research facility envelope)
        approved = float(r.approved_capacity_proxy_mw)
        new_total = max(0.0, site_cap - kn)                            # never re-buy known equipment
        righted = max(0.0, min(approved - kn, new_total))
        newreq = max(0.0, new_total - righted)
        caps[s] = dict(RIGHTED=round(righted, 4), NEW_REQUEST=round(newreq, 4), total=round(new_total, 4))
        e0s = e0[e0.bus == s]
        rights_rows.append(dict(site_id=s, bus=r.bus, approved_capacity_right_MW=approved,
                                approved_right_evidence=';'.join(sorted(set(e0s[e0s.public_claim_kind == 'APPROVED_RIGHT_NOT_EQUIPMENT'].evidence_id))) or 'NONE',
                                known_equipment_MW=kn, facility_envelope_MW=float(r.facility_capacity_envelope_mw), site_cumulative_cap_MW=site_cap,
                                new_equipment_cap_MW=new_total, cap_RIGHTED_MW=righted, cap_NEW_REQUEST_MW=newreq, cap_LOCAL_MW=0.0,
                                unknown_capacity_status=r.unknown_capacity_status, local_route_disabled_reason=r.local_route_disabled_reason,
                                shared_group_id=r.shared_group_id, shared_group_status=r.shared_group_status, cap_evidence=r.cap_evidence,
                                e0_rows_not_equipment=';'.join(e0s[e0s.public_claim_kind != 'OBSERVED_OPERATING_LOAD_PROXY'].evidence_id) or 'NONE'))
    rights = pd.DataFrame(rights_rows)

    # ---------------------------------------------------------------- disclosure (visibility) caps per commitment year Q
    vrows = []
    for s, gs in vis.groupby('site_id'):
        kn = float(kn_site.get(s, 0.0))
        for Q in range(DECISION_YEAR, LAST_YEAR + 1):
            ann = float(gs[gs.announcement_year <= Q].facility_envelope_mw.sum())
            vrows.append(dict(site_id=s, commitment_year=Q, announced_facility_MW_cum=ann, known_equipment_MW=kn,
                              visible_new_order_cap_MW=round(max(0.0, ann - kn), 4),
                              rule='sum_{class, q<=Q} U[s,class,q] <= max(0, announced facility envelope by Q - known equipment)',
                              announcement_rule='announcement_year = max(2026, request_year - 3) (package research assumption)'))
    visib = pd.DataFrame(vrows)

    # ---------------------------------------------------------------- candidates U[s, class, q] and COD causes
    crow, cod_rows = [], []
    for s in rel_.site_id:
        for cls in ('RIGHTED', 'NEW_REQUEST', 'LOCAL'):
            cap = caps[s].get(cls, 0.0) if cls != 'LOCAL' else 0.0
            for q in range(DECISION_YEAR, LAST_YEAR + 1):
                c_tx = q + tx['base']
                floor = BATCH_ZERO_FLOOR if cls == 'NEW_REQUEST' else None
                cod = max(c_tx, floor) if floor is not None else c_tx
                if cls == 'LOCAL':
                    cod = q + float(g.loc['LOCAL_POI_UPGRADE', 'lead_base_y'])
                in_window = math.floor(cod + 1e-9) <= LAST_YEAR
                enabled = cls != 'LOCAL' and cap > 1e-6 and in_window
                binding = ('PROCEDURE_BATCH_ZERO_FLOOR' if floor is not None and floor > c_tx + 1e-9 else 'EQUIPMENT_LARGE_POWER_TRANSFORMER')
                cid = f"ENG_{s.replace(' ', '_')}_{cls}_q{q}"
                crow.append(dict(candidate_id=cid, site_id=s, engineering_class=cls,
                                 engineering_type='LOCAL_POI_UPGRADE' if cls == 'LOCAL' else 'GRID_DEPENDENT_POI', commitment_year=q,
                                 lead_component_y=round(cod - q, 4), equipment_COD=round(cod, 4), firm_first_full_year=first_full_year(cod),
                                 procedural_floor=floor if floor is not None else '', class_cumulative_cap_MW=cap, enabled=int(enabled),
                                 disabled_reason='' if enabled else ('LOCAL_NO_SITE_SPARE_BAY_EVIDENCE (policy upper bound 0)' if cls == 'LOCAL' else
                                                                     ('COD_BEYOND_MODEL_WINDOW' if not in_window else 'ZERO_CAP')),
                                 unit_capex_2025USD_per_MW=unit_cost, unit_capex_low=unit_cost_low, unit_capex_high=unit_cost_high, lifetime_y=GRID_LIFE,
                                 cost_scope='POI_ONLY (direct interconnection facility; excludes public generation and upstream transmission)',
                                 asset_class='A_DC_DIRECT_INTERCONNECTION', cost_evidence=g.loc['GRID_DEPENDENT_POI', 'cost_evidence'],
                                 lead_evidence=('NEMA_2026_10 large power transformers 120-210 weeks (base 165 = midpoint, executor choice)' if cls != 'LOCAL'
                                                else g.loc['LOCAL_POI_UPGRADE', 'lead_evidence']),
                                 binding_cause=binding if cls != 'LOCAL' else 'DISABLED', model_version=MODEL_VERSION))
                if cls != 'LOCAL':
                    cod_rows.append(dict(candidate_id=cid, site_id=s, engineering_class=cls, commitment_year=q,
                                         transformer_COD_low=round(q + tx['low'], 4), transformer_COD_base=round(c_tx, 4), transformer_COD_high=round(q + tx['high'], 4),
                                         switchgear_COD_base=round(q + sw['base'], 4), procedural_floor=floor if floor is not None else '',
                                         study_component='NONE (approved right)' if cls == 'RIGHTED' else 'BATCH_ZERO_STUDIED_ALLOCATION (2028-2032)',
                                         equipment_COD=round(cod, 4), binding_cause=binding, combination_rule='max over parallel components (never summed)',
                                         firm_first_full_year=first_full_year(cod), in_model_window=int(in_window)))
    cands = pd.DataFrame(crow)
    codl = pd.DataFrame(cod_rows)
    lead = pd.DataFrame([
        dict(component_id='LARGE_POWER_TRANSFORMER', applies_to='RIGHTED, NEW_REQUEST', low_y=tx['low'], base_y=tx['base'], high_y=tx['high'],
             unit='years from commitment (order)', evidence='NEMA 2026-10: customers report 120-210 weeks for large transformers (substation power and GSU)',
             evidence_class='INDUSTRY_REPORTED_RANGE (not a site quote)', source='raw/engineering/NEMA_2026_10.pdf', source_sha256=SOURCES['raw/engineering/NEMA_2026_10.pdf'],
             modelled='base = 165 weeks (midpoint); low / high reported, not solved'),
        dict(component_id='MV_SWITCHGEAR', applies_to='RIGHTED, NEW_REQUEST', low_y=sw['low'], base_y=sw['base'], high_y=sw['high'], unit='years',
             evidence='NEMA 2026-10: medium-voltage switchgear 40-80 weeks', evidence_class='INDUSTRY_REPORTED_RANGE', source='raw/engineering/NEMA_2026_10.pdf',
             source_sha256=SOURCES['raw/engineering/NEMA_2026_10.pdf'], modelled='parallel component, never binding (shorter than the transformer)'),
        dict(component_id='BATCH_ZERO_STUDIED_ALLOCATION', applies_to='NEW_REQUEST', low_y=BATCH_ZERO_FLOOR, base_y=BATCH_ZERO_FLOOR, high_y=BATCH_ZERO_FLOOR,
             unit='earliest energization year (calendar)', evidence='ERCOT Batch Zero FAQ v8.1: the Batch Zero Interconnection Study studies years 2028-2032 (LCP rows start 2028)',
             evidence_class='ERCOT_PROCESS_DOCUMENT', source='raw/ercot/Batch_Zero_Readiness_FAQs_V8.1.xlsx', source_sha256=SOURCES['raw/ercot/Batch_Zero_Readiness_FAQs_V8.1.xlsx'],
             modelled='procedural floor of new studied allocations; later batches unpublished -> EVIDENCE_GAP, same floor (never binding: q + 2.30 y > 2028)'),
        dict(component_id='APPROVED_RIGHT_NO_STUDY', applies_to='RIGHTED', low_y=0, base_y=0, high_y=0, unit='years',
             evidence='legacy LLIS approvals (Helios 800 + 830 MW, Abilene 1.2 GW) = Batch Zero base load; no new study, equipment still required',
             evidence_class='APPROVAL_EVIDENCE (inherited E0 rows)', source='processed/poi_e0_evidence_classified.csv',
             source_sha256=SOURCES['processed/poi_e0_evidence_classified.csv'], modelled='no procedural floor; COD = commitment + transformer lead'),
        dict(component_id='LOCAL_POI_UPGRADE', applies_to='LOCAL', low_y=float(g.loc['LOCAL_POI_UPGRADE', 'lead_low_y']), base_y=float(g.loc['LOCAL_POI_UPGRADE', 'lead_base_y']),
             high_y=float(g.loc['LOCAL_POI_UPGRADE', 'lead_high_y']), unit='years', evidence=g.loc['LOCAL_POI_UPGRADE', 'lead_evidence'],
             evidence_class='RESEARCH_PROXY', source='processed/poi_engineering_parameters.csv', source_sha256=SOURCES['processed/poi_engineering_parameters.csv'],
             modelled='DISABLED (upper bound 0 at every site: no spare-bay / reuse evidence)'),
    ])
    # ---------------------------------------------------------------- site table for the model (no forbidden POI-proxy columns)
    st = old[CARRY].copy()
    st = st.merge(rights[['site_id', 'approved_capacity_right_MW', 'known_equipment_MW', 'site_cumulative_cap_MW', 'new_equipment_cap_MW',
                          'cap_RIGHTED_MW', 'cap_NEW_REQUEST_MW', 'unknown_capacity_status']], on='site_id', how='left')
    st['poi_unit_capex_2025USD_per_MW'] = unit_cost
    st['poi_lifetime_y'] = GRID_LIFE
    st['transformer_lead_y_base'] = tx['base']
    st['procedural_floor_new_request'] = BATCH_ZERO_FLOOR
    st['model_version'] = MODEL_VERSION
    st['carried_columns_source'] = f'{OLD_POI.name} (gas / PCLR / on-site RE only; POI proxy columns not read)'
    assert not (set(FORBIDDEN) & set(st.columns)), 'forbidden POI-proxy column in the engineering site table'
    # ---------------------------------------------------------------- audits
    fmap = pd.DataFrame([
        dict(source_table='poi_equipment_proxy_schedule.csv', source_field='equipment_mw / cod_decimal', model_object='SITES[s].E0rows (pre=True)', model_constraint='POI-eq (firm_frac: full years only)', note='equipment, not rights'),
        dict(source_table='GALAXY_Q2_2026.html', source_field='Phase II 260 MW IT, deliveries from Q2 2027', model_object='E1 known equipment p600 0', model_constraint='POI-eq', note='MW via Phase I gross/IT ratio'),
        dict(source_table='poi_site_release_parameters.csv', source_field='approved_capacity_proxy_mw', model_object='cap_RIGHTED', model_constraint='ENG-cum_RIGHTED', note='right residual after known equipment'),
        dict(source_table='poi_site_release_parameters.csv', source_field='site_equipment_cumulative_cap_mw', model_object='cap_total, cap_NEW_REQUEST', model_constraint='ENG-cum_site / ENG-cum_NEW_REQUEST', note='minus known equipment'),
        dict(source_table='poi_site_release_parameters.csv', source_field='local_route_enabled (0)', model_object='LOCAL candidates', model_constraint='not created (upper bound 0)', note='policy'),
        dict(source_table='poi_demand_visibility.csv', source_field='announcement_year, facility_envelope_mw', model_object='visible_new_order_cap_MW[s,Q]', model_constraint='ENG-vis', note='minus known equipment'),
        dict(source_table='poi_engineering_parameters.csv', source_field='cost_base_2025USD_kW (GRID_DEPENDENT)', model_object='POIup capital_cost', model_constraint='objective (resource cost, social r)', note='research proxy 160 USD/kW; class A direct interconnection'),
        dict(source_table='poi_engineering_parameters.csv', source_field='lead_base_y (4 y GRID_DEPENDENT)', model_object='NOT USED', model_constraint='-', note='replaced by the NEMA transformer component (doc 01: no unevidenced uniform 4 y)'),
        dict(source_table='poi_investment_candidates.csv', source_field='lead_y / equipment_cod / capacity_upper_mw', model_object='NOT USED (cross-check only)', model_constraint='-', note='uniform 4 y lead; rebuilt from components here'),
        dict(source_table='poi_e0_evidence_classified.csv', source_field='public_claim_kind', model_object='rights vs equipment split', model_constraint='-', note='APPROVED_RIGHT_NOT_EQUIPMENT never becomes equipment; UNVERIFIED_PLANNED dropped'),
        dict(source_table='Batch_Zero_Readiness_FAQs_V8.1.xlsx', source_field='study years 2028-2032', model_object='procedural_floor NEW_REQUEST', model_constraint='COD = max(q + lead, 2028)', note='non-binding in base'),
        dict(source_table='NEMA_2026_10.pdf', source_field='120-210 weeks large transformers', model_object='transformer_lead_y', model_constraint='COD = q + lead', note='base 165 weeks'),
        dict(source_table=OLD_POI.name, source_field=', '.join(c for c in CARRY if c.startswith(('gas_', 'pclr', 'onsite'))), model_object='gas lateral / MDQ / PCLR / on-site RE', model_constraint='unchanged', note='non-POI columns only'),
        dict(source_table=OLD_POI.name, source_field=', '.join(FORBIDDEN[:10]), model_object='NOT READ in engineering_cost_v1', model_constraint='-', note='legacy_proxy branch only'),
    ])
    events = []
    for r in rights.itertuples():
        s = r.site_id
        kn = known[known.site_id == s]
        hel = s == 'p600 0'
        for ev_, status, date, evid in [
            ('application/site_control', 'OBSERVED' if r.approved_capacity_right_MW > 0 else 'UNKNOWN', '', 'approved right' if r.approved_capacity_right_MW > 0 else 'no public request evidence (E4 forecast cohort)'),
            ('study', 'COMPLETED_LEGACY_LLIS' if r.approved_capacity_right_MW > 0 else 'MODELLED_BATCH_ZERO', '' if r.approved_capacity_right_MW > 0 else '2028-2032 window', 'E1 approval' if r.approved_capacity_right_MW > 0 else 'ERCOT Batch Zero FAQ v8.1'),
            ('transformer_order', 'MODELLED', 'commitment year q', 'NEMA 120-210 weeks'),
            ('substation_bay', 'UNKNOWN', '', 'no site-specific bay evidence (LOCAL disabled)'),
            ('ROW/permit', 'UNKNOWN', '', 'not in the package'),
            ('construction', 'OBSERVED' if hel else 'MODELLED_PARALLEL', '2026-04 (Helios Phase II)' if hel else '', 'Galaxy Q2 2026' if hel else 'parallel with equipment lead'),
            ('utility_COD', 'OBSERVED_LOWER_BOUND' if len(kn) else 'MODELLED', ';'.join(f'{a}@{c}' for a, c in zip(kn.asset_id, kn.COD)) if len(kn) else 'q + 3.16', 'equipment schedule' if len(kn) else 'transformer lead'),
            ('grid_ready', 'ENDOGENOUS', '', 'common KCL network, reserve and no-harm constraints of the LP (no headroom number)'),
            ('gas_ready', 'INHERITED', '', 'gas evidence level / lateral lead from the mainline POI table'),
            ('environment_permit', 'INHERITED', '', 'TECH_COMP permit-to-COD audit of the mainline (BYOP techs)')]:
            events.append(dict(site_id=s, event=ev_, status=status, date_or_rule=date, evidence=evid, model_version=MODEL_VERSION))
    events = pd.DataFrame(events)
    diff = []
    for r in old.itertuples():
        s = r.site_id
        diff.append(dict(site_id=s, old_poi_upgrade_lead_y=r.poi_upgrade_lead_y_base, old_poi_upgrade_max_MW_per_cohort=r.poi_upgrade_max_MW,
                         old_earliest_grid_COD=r.earliest_grid_COD_base, old_E0_MW=r.E0_total_MW, old_unit_cost_USD_kW=r.poi_upgrade_cost_USD_kW_base,
                         new_known_equipment_MW=float(kn_site.get(s, 0.0)), new_cap_RIGHTED_MW=caps[s]['RIGHTED'], new_cap_NEW_REQUEST_MW=caps[s]['NEW_REQUEST'],
                         new_cap_total_MW=caps[s]['total'], new_lead_y=tx['base'], new_first_candidate_COD=round(DECISION_YEAR + tx['base'], 4),
                         new_first_full_firm_year=first_full_year(DECISION_YEAR + tx['base']), new_unit_cost_USD_kW=unit_cost / 1000.0,
                         visible_new_order_cap_2026_MW=float(visib[(visib.site_id == s) & (visib.commitment_year == 2026)].visible_new_order_cap_MW.iloc[0]),
                         visible_new_order_cap_2031_MW=float(visib[(visib.site_id == s) & (visib.commitment_year == 2031)].visible_new_order_cap_MW.iloc[0])))
    diff = pd.DataFrame(diff)
    gaps = pd.DataFrame([
        dict(gap_id='GAP-01', item='remaining firm POI capacity per site (utility rating)', status='MISSING', consequence='site caps = research demand envelope / approved right, not a physical rating'),
        dict(gap_id='GAP-02', item='equipment order dates of approved rights (Helios 830 MW, Abilene)', status='MISSING', consequence='RIGHTED equipment modelled from the 2026 commitment year (conservative); true dates may be earlier'),
        dict(gap_id='GAP-03', item='Abilene equipment status beyond the approval', status='MISSING', consequence='no known equipment at p610 2 (approved right only)'),
        dict(gap_id='GAP-04', item='Helios Phase III timing and the 830 MW unleased approval', status='MISSING', consequence='right only (RIGHTED class); Phase II from disclosed schedule'),
        dict(gap_id='GAP-05', item='site-specific spare bay / reuse (LOCAL route)', status='MISSING', consequence='LOCAL disabled at all sites (policy upper bound 0)'),
        dict(gap_id='GAP-06', item='shared physical substations across research buses', status='MISSING', consequence='group = research bus; no cross-site sharing constraint'),
        dict(gap_id='GAP-07', item='POI unit cost calibration (utility quotes)', status='MISSING', consequence='160 USD/kW research proxy (80-300 range), MISO MTEP25 guide not obtained'),
        dict(gap_id='GAP-08', item='later Batch (after Batch Zero) study timing', status='MISSING', consequence='same 2028 floor (non-binding)'),
        dict(gap_id='GAP-09', item='owner / campus matching of research cohorts', status='MISSING', consequence='known equipment and rights allocated to bus cohorts = LEGACY_BUS_AGGREGATION_PROXY'),
        dict(gap_id='GAP-10', item='site transformer lead (site quotes)', status='MISSING', consequence='industry range 120-210 weeks; identical generic path at the 13 sites without own evidence (mechanism-identification uncertainty)'),
        dict(gap_id='GAP-11', item='allocated system-upgrade cost per request (SLLIA security basis)', status='MISSING', consequence='security = 50,000 USD/MW x contracted MW floor; allocated upgrade share UNRESOLVED'),
        dict(gap_id='GAP-12', item='12CP / minimum billing demand (25.193) and 25.252 tariff', status='PROPOSED_RULE (2026-07-24 TexReg)', consequence='not applied as a payment'),
    ])
    return dict(sites=st, known=known, candidates=cands, visibility=visib, lead=lead, rights=rights, cod=codl, fmap=fmap, events=events,
                diff=diff, gaps=gaps, baseline_json=base_json)


def write(res, out=OUT, aud=AUD):
    out.mkdir(parents=True, exist_ok=True); aud.mkdir(parents=True, exist_ok=True)
    files = {'ENG_POI_SITES.csv': res['sites'], 'ENG_POI_EQUIPMENT_KNOWN.csv': res['known'], 'ENG_POI_CANDIDATES.csv': res['candidates'],
             'ENG_POI_VISIBILITY.csv': res['visibility'], 'ENG_POI_LEAD_COMPONENTS.csv': res['lead']}
    for f, df in files.items():
        df.to_csv(out / f, index=False, lineterminator='\n')
    reg = pd.DataFrame([dict(source=k, sha256=v, root='data/byop/engineering_v1 (local + L2, never in git)') for k, v in SOURCES.items()])
    reg.to_csv(out / 'ENG_POI_SOURCE_REGISTER.csv', index=False, lineterminator='\n')
    for f, k in (('FIELD_TO_MODEL_MAP.csv', 'fmap'), ('POI_ENGINEERING_EVENT_LEDGER.csv', 'events'), ('POI_RIGHTS_AND_CAPACITY_AUDIT.csv', 'rights'),
                 ('POI_INVESTMENT_CANDIDATE_LEDGER.csv', 'candidates'), ('COD_CAUSE_LEDGER.csv', 'cod'), ('POI_INPUT_MODEL_DIFF.csv', 'diff'),
                 ('EVIDENCE_GAPS.csv', 'gaps')):
        res[k].to_csv(aud / f, index=False, lineterminator='\n')
    rec = dict(model_version=MODEL_VERSION, built_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), sources=SOURCES,
               outputs={f: sha(out / f) for f in list(files) + ['ENG_POI_SOURCE_REGISTER.csv']},
               counts=dict(sites=len(res['sites']), known_equipment_rows=len(res['known']), candidates=len(res['candidates']),
                           enabled_candidates=int(res['candidates'].enabled.sum()), visibility_rows=len(res['visibility'])),
               solver_calls=0)
    (aud / 'H1_BUILD_RECORD.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='rebuild in memory and compare with the tracked inputs (no write)')
    a = ap.parse_args()
    res = build()
    if a.check:
        bad = []
        for f, k in (('ENG_POI_SITES.csv', 'sites'), ('ENG_POI_EQUIPMENT_KNOWN.csv', 'known'), ('ENG_POI_CANDIDATES.csv', 'candidates'),
                     ('ENG_POI_VISIBILITY.csv', 'visibility'), ('ENG_POI_LEAD_COMPONENTS.csv', 'lead')):
            if res[k].to_csv(index=False, lineterminator='\n') != (OUT / f).read_text(encoding='utf-8'):
                bad.append(f)
        print(json.dumps(dict(check='PASS' if not bad else 'FAIL', differs=bad)))
        sys.exit(1 if bad else 0)
    print(json.dumps(write(res), indent=1))


if __name__ == '__main__':
    main()
