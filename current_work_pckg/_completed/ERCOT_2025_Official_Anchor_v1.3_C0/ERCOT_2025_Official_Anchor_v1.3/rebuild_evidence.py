#!/usr/bin/env python3
"""Offline extraction of supplied official ERCOT 2025 evidence; does not alter BYOP or solve LPs.
Requires Python 3, pandas, openpyxl. Run: python rebuild_evidence.py
"""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
OUT = ROOT / 'derived'
OUT.mkdir(exist_ok=True)
def csv(d, name):
    d.to_csv(OUT / name, index=False, float_format='%.10f')

native = pd.read_excel(RAW / 'Native_Load_2025.xlsx')
assert len(native) == 8760
assert native.iloc[:, 1:].notna().all().all()
source_sha = hashlib.sha256((RAW / 'Native_Load_2025.xlsx').read_bytes()).hexdigest()
assert source_sha == '23664b0cddb047692f6cac26a4300e987c6309795395d394bf2dc223f37b53aa'
zones = native.columns[1:9]
assert (native[zones].sum(axis=1) - native.ERCOT).abs().max() < 0.00001
hourly = native.copy()
hourly.insert(0, 'source_row_1based', np.arange(2, len(native) + 2))
hourly.insert(1, 'sequence_hour_1based', np.arange(1, 8761))
hourly.insert(2, 'model_sequence_start', pd.date_range('2025-01-01', periods=8760, freq='h'))
# model_sequence_start is a synthetic continuous alignment, NOT a conversion to UTC.
csv(hourly, 'ERCOT_NATIVE_LOAD_2025_1H.csv')
three = native.iloc[:, 1:].groupby(np.arange(8760) // 3).mean()
three.insert(0, 'model_sequence_start', pd.date_range('2025-01-01', periods=2920, freq='3h'))
three.insert(1, 'weight_hours', 3)
csv(three.reset_index(drop=True), 'ERCOT_NATIVE_LOAD_2025_3H.csv')
peak = native.loc[native.ERCOT.idxmax()]
metrics = dict(source_xlsx_sha256=source_sha, source_hash_matches_repository=True,
    rows=len(native), energy_TWh=float(native.ERCOT.sum()/1e6), peak_1h_MW=float(peak.ERCOT),
    peak_1h_source_label=str(peak.iloc[0]), peak_3h_MW=float(three.ERCOT.max()),
    zone_sum_max_abs_error_MW=float((native[zones].sum(axis=1)-native.ERCOT).abs().max()),
    official_annual_report_peak_MW=83707, annual_report_minus_native_peak_MW=float(83707-peak.ERCOT),
    source_DST_labels=native.loc[native.iloc[:,0].str.contains('DST'), native.columns[0]].tolist(),
    time_axis_policy='Preserve original HE strings; row-order alignment reproduces repository; synthetic timestamps are not UTC.')
assert abs(three.ERCOT.sum()*3-native.ERCOT.sum()) < 0.001
day = native.iloc[:,0].str.slice(0,10)
monthly = native.assign(month=day.str.slice(0,2)).groupby('month')[list(zones)+['ERCOT']].sum()/1e6
csv(monthly.reset_index(), 'LOAD_MONTHLY_TWH.csv')
daily = native.assign(date=day).groupby('date',sort=False).ERCOT.agg(['max','sum'])
daily['month'] = daily.index.str.slice(0,2).astype(int)
selected=[]
for label,mask in [('summer_peak',daily.month.isin([6,7,8,9])),('winter_peak',daily.month.isin([1,2,12]))]:
    for dt,row in daily[mask].nlargest(3,'max').iterrows():
        selected.append(dict(date=dt,selection=label,peak_MW=row['max'],energy_MWh=row['sum'],use='candidate for later validation; not solved'))
csv(pd.DataFrame(selected),'HISTORICAL_DEMAND_STRESS_DAYS.csv')

audit=json.loads((ROOT/'repo_snapshot/baseline_2025_tamu_audit.json').read_text())
fleet=audit['fleet_2025_MW_by_carrier']
model={'Thermal':sum(fleet[k] for k in ['CCGT','OCGT','gas_steam','coal','nuclear','biomass']),
       'Wind':fleet['onwind'],'Solar':fleet['solar'],'Storage':fleet['battery'],'Hydro':fleet['hydro']}
official={'Thermal':89507,'Wind':40719,'Solar':37443,'Storage':16656,'Hydro':579}
rows=[dict(category=k,official_annual_report_installed_MW=official[k],model_summer_based_MW=model[k],
           apparent_gap_MW=official[k]-model[k],interpretation='Different ratings, coverage and statuses; not an instruction to add capacity') for k in official]
rows.append(dict(category='Total',official_annual_report_installed_MW=184904,model_summer_based_MW=audit['fleet_2025_MW_total'],
    apparent_gap_MW=184904-audit['fleet_2025_MW_total'],interpretation='Cross-definition diagnostic only'))
csv(pd.DataFrame(rows),'CAPACITY_DEFINITION_BRIDGE.csv')

trend=[]
for sheet in pd.ExcelFile(RAW/'Capacity_December2025.xlsx').sheet_names:
    t=pd.read_excel(RAW/'Capacity_December2025.xlsx',sheet_name=sheet,header=None)
    ix=t.index[t.iloc[:,0].astype(str).eq('2025')]
    assert len(ix)==1
    i=ix[0];r=t.loc[i]
    trend.append(dict(sheet=sheet,excel_row=int(i+1),year=2025,chart_cumulative_MW=float(r.iloc[1]),
       operational_MW=float(r.iloc[2]),IA_FS_MW=float(r.iloc[3]),IA_no_FS_MW=float(r.iloc[4]),
       other_planned_MW=float(r.iloc[5]),small_generator_MW=float(r.iloc[6]),
       source='Capacity_December2025.xlsx; snapshot December 2025, published January 2026'))
csv(pd.DataFrame(trend),'CAPACITY_TREND_DEC2025_EXTRACT.csv')

units=pd.read_excel(RAW/'CDR_December2025.xlsx',sheet_name='Unit Details',header=2)
units.columns=[str(c).replace('\n',' ').strip() for c in units.columns]
units=units.iloc[:,:11].copy()
units.insert(0,'source_excel_row',np.arange(4,len(units)+4))
units['INSTALLED CAPACITY (MW)']=pd.to_numeric(units['INSTALLED CAPACITY (MW)'],errors='coerce')
units=units[units['INSTALLED CAPACITY (MW)'].notna()]
units['diagnostic_status_bucket']=units['CDR STATUS'].map(lambda s: 'PLANNED_EXCLUDE_FROM_2025' if str(s).startswith('PLAN') else 'INDEFINITE_MOTHBALLED_EXCLUDE' if s=='MOTH-IND' else 'REQUIRES_STATUS_AND_CUTOFF_MATCH')
units['audit_only_not_model_ready']=True
csv(units,'CDR_DEC2025_UNIT_REGISTER_AUDIT_ONLY.csv')
status=units.groupby(['CDR STATUS','CDR RESOURCE ATTRIBUTE','FUEL'],dropna=False)['INSTALLED CAPACITY (MW)'].agg(['count','sum']).reset_index()
csv(status,'CDR_UNIT_STATUS_FUEL_SUMMARY.csv')
nuclear=units[units.FUEL.eq('NUCLEAR')]
full=pd.read_excel(RAW/'CDR_December2025.xlsx',sheet_name='Unit Details',header=2)
metrics['nuclear_CDR_installed_MW']=float(nuclear['INSTALLED CAPACITY (MW)'].sum())
metrics['nuclear_CDR_summer2026_MW']=float(pd.to_numeric(full.loc[full.FUEL.eq('NUCLEAR'),2026]).sum())
metrics['model_nuclear_summer_based_MW']=fleet['nuclear']

fuel=pd.read_excel(RAW/'IntGenbyFuel2025.xlsx',sheet_name='Summary',header=None)
fuelrows=[]
for i in range(8,19):
    r=fuel.iloc[i]
    for j in range(1,14):
        fuelrows.append(dict(fuel=r.iloc[0],period='annual' if j==13 else f'2025-{j:02d}',GWh=float(r.iloc[j]),
          source_cell=f'Summary!{chr(65+j)}{i+1}',basis='Published energy, GWh; includes negative WSL; do not multiply by 0.25'))
csv(pd.DataFrame(fuelrows),'FUEL_MIX_2025_GWH.csv')
metrics['fuelmix_total_GWh']=float(fuel.iloc[18,13])
metrics['fuelmix_total_minus_native_GWh']=metrics['fuelmix_total_GWh']-metrics['energy_TWh']*1000
(OUT/'VERIFIED_METRICS.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(metrics,indent=2,ensure_ascii=False))
