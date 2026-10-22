#!/usr/bin/env python3
"""A0.2 v1.1 source ZIP and full original JSON/CSV provenance verification; no solvers."""
from pathlib import Path
import zipfile, hashlib, csv, json, math
R=Path(__file__).resolve().parents[1]
ZIP=R/'source_tech_v2/ORIGINAL_SOURCE_ZIP.zip'
D=R/'source_tech_v2/BYOP_Tech_Calibrated_v2_2026-10-22'
sha=lambda b: hashlib.sha256(b).hexdigest()
with zipfile.ZipFile(ZIP) as z:
    assert z.testzip() is None
    originals={Path(x).name:z.read(x) for x in z.namelist() if not x.endswith('/')}
assert len(originals)==9,originals.keys()
assert all((D/name).read_bytes()==b for name,b in originals.items())
base=json.loads((D/'BYOP_TECH_PARAMETER_BASELINE_V2.json').read_text(encoding='utf-8-sig'))
assert base['version']=='TECH_COMP_2_2026-10-22'
def table(n):
    with (D/n).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
tech=table('BYOP_TECH_PARAMETERS_V2.csv'); supply=table('BYOP_SUPPLY_POOL_PROXY_V2.csv'); oz=table('BYOP_COUNTY_OZONE_RULES_2026.csv')
assert {x['tech'] for x in tech}=={'RICE','OCGT_aero','SOFC_NG','WIND','PV','BESS'}
assert len(tech)==len(base['technologies'])==6
for row in tech:
    src=next(x for x in base['technologies'] if x['tech']==row['tech'])
    for key in ['capex_2025USD_per_kW','fom_USD_per_kWyr','vom_USD_per_MWh','heat_rate_HHV_Btu_per_kWh','equipment_order_to_arrival_years','site_install_commission_years','CO2_t_per_MWh']:
        assert math.isclose(float(row[key]),float(src[key]),rel_tol=0,abs_tol=0.0001),(row['tech'],key)
assert len(supply)==18 and {(int(x['delivery_year']),x['technology']) for x in supply}=={(y,t) for y in range(2026,2032) for t in ('RICE','OCGT_aero','SOFC_NG')}
for x in supply:
    t=x['technology'];y=int(x['delivery_year']); index=base['supply']['year'].index(y)
    assert float(x['ercot_available_MW_base_PROXY'])==float(base['supply']['reference_ERCOT_market_access_MW_by_tech'][t][index])
    assert float(x['reserved_verified_MW'])==0
assert len(oz)==19 and len(set(x['county_fips'] for x in oz))==19
for x in oz:
    fips=x['county_fips']; a=int(x['nonattainment_2015_ozone']); b=int(x['nonattainment_2008_ozone'])
    assert len(fips)==5 and fips.startswith('48')
    assert x['classification_FOR_MODEL']==('OZONE_NONATTAINMENT_2015' if a else 'OZONE_NONATTAINMENT_2008_ONLY' if b else 'ATTAINMENT_OR_UNCLASSIFIED')
    assert a or b
permit=base['permit']['values_years_from_order']
for cat in ('ATTAINMENT_OR_UNCLASSIFIED','OZONE_NONATTAINMENT_2015','OZONE_NONATTAINMENT_2008_ONLY','UNKNOWN_CONSERVATIVE'):
    assert set(permit[cat])=={x['tech'] for x in tech}
    assert all(permit[cat][t]>0 for t in permit[cat])
for t in ['SOFC_NG','RICE','OCGT_aero']:
    assert permit['UNKNOWN_CONSERVATIVE'][t]>=permit['ATTAINMENT_OR_UNCLASSIFIED'][t]
# environmental time critical examples reflect source values, no reliance on solver
cod=lambda q,equip,inst,permit,gas=0,elec=0: max(max(q+equip,q+permit)+inst,q+permit,q+gas,q+elec)
assert cod(2026,0.75,0.25,0.4,0.5)==2027.0
assert cod(2026,0.75,0.25,0.6,3.0)==2029.0
report={'status':'ORIGINAL_TECH_V2_SOURCE_QA_PASS','real_solver_calls':0,'source_zip_sha256':sha(ZIP.read_bytes()),'source_files':len(originals),'technologies':len(tech),'supply_rows':len(supply),'ozone_fips_rows':len(oz),'permit_classes':list(permit),'copied_source_byte_identical':True}
print(json.dumps(report,ensure_ascii=False,indent=2))
