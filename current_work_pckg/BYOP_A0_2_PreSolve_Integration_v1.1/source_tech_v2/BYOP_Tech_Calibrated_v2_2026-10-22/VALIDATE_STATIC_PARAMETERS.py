from pathlib import Path
import json,csv,math
D=Path(__file__).resolve().parent
x=json.loads((D/'BYOP_TECH_PARAMETER_BASELINE_V2.json').read_text(encoding='utf-8'))
assert x['scope_control']['no_authorized_global_solver']
assert len(x['technologies'])==6
names={t['tech'] for t in x['technologies']}
assert names=={'RICE','OCGT_aero','SOFC_NG','WIND','PV','BESS'}
for t in x['technologies']:
    assert t['capex_low']<=t['capex_2025USD_per_kW']<=t['capex_high']
    assert t['equipment_order_to_arrival_years']>0 and t['site_install_commission_years']>0
    assert t['lifetime_years']>0
    if t['tech'] in {'RICE','OCGT_aero','SOFC_NG'}:
        assert 1.0<t['firm_redundancy_factor']<1.5
        assert abs(t['CO2_t_per_MWh']-t['heat_rate_HHV_Btu_per_kWh']*53.06/1e6)<1e-5
assert all(v==0 for v in x['schedule']['confirmed_fast_reserved_2026_MW'].values())
for yidx,y in enumerate(x['supply']['year']):
    assert 2026<=y<=2031
    for k,seq in x['supply']['reference_ERCOT_market_access_MW_by_tech'].items():assert seq[yidx]>0
assert len(x['permit']['values_years_from_order'])==4
with (D/'BYOP_COUNTY_OZONE_RULES_2026.csv').open(newline='',encoding='utf-8') as f:
    rows=list(csv.DictReader(f));assert all(len(r['county_fips'])==5 for r in rows)
print('PASS: 6 technologies, bounds, 2026-2031 annual supply, 2026 reserved 0, county FIPS, CO2 units, non-solver authorization')
