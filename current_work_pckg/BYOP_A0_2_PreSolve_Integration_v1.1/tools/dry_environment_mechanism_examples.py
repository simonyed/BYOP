#!/usr/bin/env python3
"""Deterministic, no solver. Show technology emissions->permit proxy critical path->COD.
Illustrative only, not predictions of approval or project COD. Do not edit inputs.
"""
from pathlib import Path
import json, csv
R=Path(__file__).resolve().parents[1]
D=R/'source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22'
b=json.loads((D/'BYOP_TECH_PARAMETER_BASELINE_V2.json').read_text())
T={x['tech']:x for x in b['technologies']}
P=b['permit']['values_years_from_order']
EX=[('SOFC_ordinary','SOFC_NG','ATTAINMENT_OR_UNCLASSIFIED',.5,'DEFAULT_ENV'),
    ('SOFC_ozone','SOFC_NG','OZONE_NONATTAINMENT_2015',.5,'DEFAULT_ENV'),
    ('SOFC_gas_L2','SOFC_NG','OZONE_NONATTAINMENT_2015',3,'DEFAULT_ENV'),
    ('RICE_ordinary','RICE','ATTAINMENT_OR_UNCLASSIFIED',.5,'DEFAULT_ENV'),
    ('RICE_ozone','RICE','OZONE_NONATTAINMENT_2015',.5,'DEFAULT_ENV'),
    ('RICE_ozone_gas_L2','RICE','OZONE_NONATTAINMENT_2015',3,'DEFAULT_ENV'),
    ('RICE_ozone_controlled','RICE','OZONE_NONATTAINMENT_2015',.5,'CONTROLLED_ENV'),
    ('AERO_ordinary','OCGT_aero','ATTAINMENT_OR_UNCLASSIFIED',.5,'DEFAULT_ENV'),
    ('AERO_ozone','OCGT_aero','OZONE_NONATTAINMENT_2015',.5,'DEFAULT_ENV')]
res=[]
for label,t,cat,gas,path in EX:
 x=T[t]; q=2026; lead=P[cat][t]
 equip=q+x['equipment_order_to_arrival_years']; civil=q+x['civil_ready_from_order_years']
 permit=q+lead; gas_ready=q+gas; electrical=q+.5
 # conservative: construction before air permit is NOT assumed legally available
 installed=max(equip,civil,permit)+x['site_install_commission_years']
 cod=max(installed,permit,gas_ready,electrical)
 cod_without=max(max(equip,civil,q)+x['site_install_commission_years'],gas_ready,electrical)
 rate=x['NOx_kg_per_MWh_controlled_proxy'] if path=='CONTROLLED_ENV' else x['NOx_kg_per_MWh_uncontrolled_proxy']
 site_MW=100.0
 pte=site_MW*8760*rate/907.18474
 res.append({'case':label,'status':'STATIC_ILLUSTRATION_NOT_SOLVED','tech':t,'ozone_class':cat,'permit_path':path,
            'source_emissions_class':'RESEARCH_PROXY' if t!='SOFC_NG' else 'OEM_DATASHEET_VALUE',
            'order_year':q,'site_capacity_MW_for_PTE':site_MW,'NOx_kg_MWh':rate,'NOx_PTE_screen_short_tpy':round(pte,5),
            'permit_years_PROXY':lead,'equipment_ready':equip,'permit_ready':permit,'gas_ready':gas_ready,
            'COD_real':cod,'COD_without_permit_noncompliant_counterfactual':cod_without,
            'net_environment_permit_COD_delay_y':round(cod-cod_without,6),'first_full_firm_year':int(cod) if cod==int(cod) else int(cod)+1,
            'note':'illustration, permit default precedes construction, no actual site permits'})
R.joinpath('static_examples').mkdir(exist_ok=True)
fp=R/'static_examples/STATIC_PERMIT_COD_EXAMPLES.csv'
with fp.open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(res[0]));w.writeheader();w.writerows(res)
N={x['case']:x for x in res}
assert N['SOFC_ordinary']['COD_real']==N['SOFC_ozone']['COD_real']==2027
assert N['SOFC_gas_L2']['COD_real']==2029
assert N['RICE_ordinary']['COD_real']==2027.5
assert N['RICE_ozone']['COD_real']==2027.75
assert N['RICE_ozone_gas_L2']['COD_real']==2029
assert N['RICE_ozone_controlled']['COD_real']==N['RICE_ozone']['COD_real']
assert N['RICE_ozone_controlled']['NOx_PTE_screen_short_tpy']<N['RICE_ozone']['NOx_PTE_screen_short_tpy']
assert N['AERO_ordinary']['COD_real']==2028
assert N['AERO_ozone']['COD_real']==2028.25
print(json.dumps({'status':'STATIC_ENV_MEDIATION_PASS','solver_calls':0,'cases':len(res),'output':str(fp),'summary':{k:(v['COD_real'],v['net_environment_permit_COD_delay_y']) for k,v in N.items()}},ensure_ascii=False,indent=2))
