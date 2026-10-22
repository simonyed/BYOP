"""Read-only source extraction for post-v1.6 research. No power-system solves.

Run with pandas/openpyxl: python build_research_data.py
Quarter-hour fuel entries are MWh; sum four intervals to get hourly MWh, which
numerically equals the average MW over that one-hour interval. DST source labels
are matched explicitly; no UTC interpretation is invented.
"""
from pathlib import Path
import calendar
import hashlib
import json
import math
import re
import pandas as pd

ROOT=Path(__file__).resolve().parent
RAW=ROOT/'raw'
OUT=ROOT/'derived'
OUT.mkdir(exist_ok=True)

def write(name, rows):
    d=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(OUT/name,index=False,encoding='utf-8-sig')
    return d

# Actual fuel generation. Native Load and fuel workbook both retain the repeated
# autumn HE02 as a second explicitly labelled DST hour.
observations=[]
daily_checks=[]
for month in range(1,13):
    sheet=calendar.month_abbr[month]
    d=pd.read_excel(RAW/'IntGenbyFuel2025.xlsx',sheet_name=sheet)
    for i,r in d.iterrows():
        if pd.isna(r['Date']) or str(r['Fuel']) not in ['Wind','Solar']:
            continue
        groups={}
        for col in d.columns[4:]:
            v=pd.to_numeric(r[col],errors='coerce')
            if pd.isna(v):continue
            label=str(col)
            match=re.match(r'(\d{1,2}):(\d{2})',label)
            assert match,label
            hh,mm=map(int,match.groups())
            he=24 if hh==0 and mm==0 else hh+(1 if mm>0 else 0)
            dst='DST' in label
            groups.setdefault((he,dst),[]).append(float(v))
        date=pd.Timestamp(r['Date']).strftime('%Y-%m-%d')
        total=sum(sum(v) for v in groups.values())
        error=abs(total-float(r['Total']))
        assert error<1e-3,(date,r['Fuel'],error)
        daily_checks.append({'date':date,'fuel':r['Fuel'],'interval_count':sum(map(len,groups.values())),
            'interval_sum_MWh':total,'published_total_MWh':r['Total'],'abs_error_MWh':error})
        for (he,dst),vs in groups.items():
            assert len(vs)==4,(date,he,dst,len(vs))
            observations.append({'date':date,'hour_ending':he,'source_extra_dst_hour':dst,
                'fuel':r['Fuel'],'actual_generation_MW':sum(vs),'source_sheet':sheet,
                'source_excel_row':i+2,'settlement_type':r['Settlement Type']})
obs=pd.DataFrame(observations)
key=['date','hour_ending','source_extra_dst_hour']
assert not obs.duplicated(key+['fuel']).any()
pivot=obs.pivot(index=key,columns='fuel',values='actual_generation_MW').reset_index()
pivot=pivot.rename(columns={'Wind':'wind_actual_MW','Solar':'solar_actual_MW'})
native=pd.read_excel(RAW/'Native_Load_2025.xlsx')
nrows=[]
for i,r in native.iterrows():
    label=str(r['Hour Ending'])
    match=re.match(r'(\d{2}/\d{2}/\d{4})\s+(\d{2}):00',label)
    assert match,label
    date=pd.to_datetime(match.group(1),format='%m/%d/%Y').strftime('%Y-%m-%d')
    nrows.append({'source_row_0based':i,'source_excel_row':i+2,'source_HE_label':label,
        'date':date,'hour_ending':int(match.group(2)),'source_extra_dst_hour':'DST' in label,
        'native_load_MW':float(r.ERCOT),**{f'load_{c}_MW':float(r[c]) for c in native.columns[1:-1]}})
hour=pd.DataFrame(nrows).merge(pivot,on=key,how='left',validate='one_to_one').sort_values('source_row_0based')
assert len(hour)==8760 and not hour.isna().any().any()
hour['observed_residual_load_MW']=hour.native_load_MW-hour.wind_actual_MW-hour.solar_actual_MW
hour['definition']='native load minus metered wind and solar; not uncurtailed potential net load'
write('ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv',hour)
write('FUEL_INTERVAL_DAILY_QA.csv',daily_checks)

# Match existing 3h model convention: sequential source rows, not a fabricated
# 2030 calendar or reindexed local day. Each group has exactly three source hours.
numeric=['native_load_MW','wind_actual_MW','solar_actual_MW','observed_residual_load_MW']
group=hour.source_row_0based//3
h3=hour.groupby(group)[numeric].mean().reset_index(names='model_3h_position_0based')
h3['source_row_start_0based']=h3.model_3h_position_0based*3
h3['source_row_end_0based']=h3.source_row_start_0based+2
h3['weight_hours']=3
write('ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_3H.csv',h3)
for c in numeric:assert abs(h3[c].sum()*3-hour[c].sum())<1e-6

# Pre-register five event families before seeing any BYOP result. Windows cover
# complete source days with one day before/after (typically 72h, DST 71/73h).
dates=pd.to_datetime(hour.date)
summer=dates.dt.month.isin([6,7,8,9])
winter=dates.dt.month.isin([1,2,12])
criteria=[('SUMMER_LOAD_PEAK','fit_reference_for_future_parameter_fit_only','native_load_MW',summer),
          ('SUMMER_OBSERVED_NET_PEAK','validation_window','observed_residual_load_MW',summer),
          ('WINTER_LOAD_PEAK','validation_window_not_whole_model_holdout','native_load_MW',winter)]
events=[]
for event,role,metric,mask in criteria:
    ix=hour.loc[mask,metric].idxmax()
    r=hour.loc[ix]
    center=pd.Timestamp(r.date)
    window=hour[(dates>=center-pd.Timedelta(days=1))&(dates<=center+pd.Timedelta(days=1))]
    events.append({'event_id':event,'role':role,'selection_metric':metric,'date':r.date,
        'source_HE_label':r.source_HE_label,'source_row_0based':r.source_row_0based,
        'native_load_MW':r.native_load_MW,'wind_actual_MW':r.wind_actual_MW,
        'solar_actual_MW':r.solar_actual_MW,'observed_residual_load_MW':r.observed_residual_load_MW,
        'window_source_row_start':int(window.source_row_0based.min()),
        'window_source_row_end':int(window.source_row_0based.max()),'window_hours':len(window)})
    write(f'WINDOW_{event}_1H.csv',window)
# Two extra diagnostics use observed residual-load ramp and a separate low-wind
# high-load day; they are candidates, not additional mandatory model solves.
hour['residual_ramp_1h_MW']=hour.observed_residual_load_MW.diff()
ix=hour.loc[summer,'residual_ramp_1h_MW'].idxmax()
r=hour.loc[ix]
events.append({'event_id':'SUMMER_UPWARD_NET_RAMP','role':'optional_diagnostic',
    'selection_metric':'observed_residual_ramp','date':r.date,'source_HE_label':r.source_HE_label,
    'source_row_0based':r.source_row_0based,'native_load_MW':r.native_load_MW,
    'wind_actual_MW':r.wind_actual_MW,'solar_actual_MW':r.solar_actual_MW,
    'observed_residual_load_MW':r.observed_residual_load_MW})
top=hour[summer & (hour.native_load_MW>=hour.loc[summer,'native_load_MW'].quantile(.9))]
r=top.loc[top.wind_actual_MW.idxmin()]
events.append({'event_id':'SUMMER_LOW_WIND_HIGH_LOAD','role':'optional_diagnostic',
    'selection_metric':'min observed wind among summer top-decile loads','date':r.date,
    'source_HE_label':r.source_HE_label,'source_row_0based':r.source_row_0based,
    'native_load_MW':r.native_load_MW,'wind_actual_MW':r.wind_actual_MW,
    'solar_actual_MW':r.solar_actual_MW,'observed_residual_load_MW':r.observed_residual_load_MW})
# The actual gross and net maxima may occur on the same day. Preserve both true
# maxima; add a pre-registered disjoint-day event rather than mislabel correlated
# hours as an independent validation sample. This holdout applies only to any
# future nuisance-parameter fit; v1.6 already uses full-year load for network fit.
load_peak_date=pd.Timestamp(events[0]['date'])
disjoint=summer & ((dates<load_peak_date-pd.Timedelta(days=2)) | (dates>load_peak_date+pd.Timedelta(days=2)))
ix=hour.loc[disjoint,'observed_residual_load_MW'].idxmax()
r=hour.loc[ix]
center=pd.Timestamp(r.date)
window=hour[(dates>=center-pd.Timedelta(days=1))&(dates<=center+pd.Timedelta(days=1))]
events.append({'event_id':'SUMMER_NET_PEAK_DISJOINT_DAY','role':'holdout_for_future_parameter_fit_only',
    'selection_metric':'max observed residual outside gross-peak +/-2 days',
    'date':r.date,'source_HE_label':r.source_HE_label,'source_row_0based':r.source_row_0based,
    'native_load_MW':r.native_load_MW,'wind_actual_MW':r.wind_actual_MW,
    'solar_actual_MW':r.solar_actual_MW,'observed_residual_load_MW':r.observed_residual_load_MW,
    'window_source_row_start':int(window.source_row_0based.min()),
    'window_source_row_end':int(window.source_row_0based.max()),'window_hours':len(window)})
write('WINDOW_SUMMER_NET_PEAK_DISJOINT_DAY_1H.csv',window)
if events[0]['date']==events[1]['date']:
    events[1]['role']='same_calendar_event_as_gross_peak_not_independent'
for event in events:
    if 'window_source_row_start' in event:continue
    center=pd.Timestamp(event['date'])
    window=hour[(dates>=center-pd.Timedelta(days=1))&(dates<=center+pd.Timedelta(days=1))]
    event.update(window_source_row_start=int(window.source_row_0based.min()),
        window_source_row_end=int(window.source_row_0based.max()),window_hours=len(window))
    write(f"WINDOW_{event['event_id']}_1H.csv",window)
ev=write('PRE_REGISTERED_STRESS_EVENTS.csv',events)
assert not ev.isna().any().any()

# Monthly published percentile marginals. These are not joint trajectories;
# never multiply their quantile probabilities or call a combined corner P90.
quantiles=[]
det=[]
for month in range(1,13):
    name=f'MORA_{calendar.month_name[month]}2025.xlsx'
    d=pd.read_excel(RAW/name,sheet_name='PRRM Percentile Results',header=None)
    measure=None
    measure_label=''
    hour_cols={}
    for i,r in d.iterrows():
        a=str(r.iloc[0]).strip()
        if 'Gross Demand by Hour' in a:measure='gross_demand'
        elif 'Solar Generation by Hour' in a:measure='solar_generation'
        elif 'Wind Generation by Hour' in a:measure='wind_generation'
        elif 'Unplanned Thermal Outages' in a:measure='unplanned_thermal_outages'
        if any(s in a for s in ['Gross Demand by Hour','Solar Generation by Hour','Wind Generation by Hour','Unplanned Thermal Outages']):
            measure_label=a
        if str(r.iloc[1]).strip()=='Percentiles':
            hour_cols={}
            for j in range(2,len(r)):
                v=pd.to_numeric(r.iloc[j],errors='coerce')
                if pd.notna(v) and float(v).is_integer() and 1<=v<=24:hour_cols[j]=int(v)
            continue
        raw_q=r.iloc[1]
        q=(pd.to_numeric(str(raw_q).rstrip('%'),errors='coerce')/100
           if isinstance(raw_q,str) and raw_q.endswith('%') else pd.to_numeric(raw_q,errors='coerce'))
        if measure is None or pd.isna(q) or not 0<=q<=1:continue
        if measure=='unplanned_thermal_outages':hour_cols={2:'DAILY'}
        for j,he in hour_cols.items():
            v=pd.to_numeric(r.iloc[j],errors='coerce')
            if pd.isna(v):continue
            quantiles.append({'month':month,'variable':measure,'quantile':q,'hour_ending':he,
                'MW':v,'variable_source_label':measure_label,
                'outage_component':('extreme_weather_increment' if 'Due to Extreme Weather' in measure_label and 'Not Due' not in measure_label
                    else 'non_extreme_weather' if 'Not Due to Extreme Weather' in measure_label else 'not_separated'),
                'source_file':name,'source_sheet':'PRRM Percentile Results',
                'source_excel_row':i+1,'source_excel_column_1based':j+1,
                'scope':'forecast marginal; not actual or joint weather trajectory'})
    d=pd.read_excel(RAW/name,sheet_name='Monthly Outlook',header=None)
    for i,r in d.iterrows():
        labels=[str(v).strip() for v in r if isinstance(v,str) and v.strip()]
        label=next((s for s in labels if len(s)<100),'')
        numbers=[float(v) for v in r if isinstance(v,(int,float)) and pd.notna(v)]
        if label and numbers:
            det.append({'month':month,'label':label,'value':numbers[-1],
                'source_file':name,'source_sheet':'Monthly Outlook','source_excel_row':i+1})
qs=write('MORA_2025_HOURLY_PERCENTILE_MARGINALS.csv',quantiles)
write('MORA_2025_DETERMINISTIC_SOURCE_VALUES.csv',det)
assert qs.month.nunique()==12
assert set(qs.variable)=={'gross_demand','solar_generation','wind_generation','unplanned_thermal_outages'}
outages=qs[qs.variable=='unplanned_thermal_outages']
write('MORA_2025_UNPLANNED_THERMAL_OUTAGE_QUANTILES.csv',outages)
assert len(outages)==143  # December publishes 11 extra weather-outage quantiles.

# Future ELCC reference is a separate vintage from historical 2025 credits.
d=pd.read_excel(RAW/'CDR_December2025.xlsx',sheet_name='ELCCs',header=None)
credits=[]
for i in range(5,len(d)):
    resource=str(d.iat[i,2]).strip()
    risk=str(d.iat[i,0]).strip()
    if not resource.startswith(('Wind -','Solar -','BESS -')):continue
    for j in range(4,len(d.columns)):
        v=pd.to_numeric(d.iat[i,j],errors='coerce')
        if pd.isna(v):continue
        credits.append({'year_label':str(d.iat[4,j]),'season':d.iat[3,j],
            'risk_period':risk,'hour_ending':int(d.iat[1 if risk.startswith('Peak Load') else 2,j]),
            'resource_type':resource,'published_cdr_capacity_credit':v,'excel_row':i+1,
            'excel_column_1based':j+1,'source_file':'CDR_December2025.xlsx',
            'scope':'published reporting coefficient at specified vintage/portfolio; not invariant under arbitrary new builds'})
write('CDR_FUTURE_ELCC_2026_2031_REFERENCE.csv',credits)

# Separate public annual operational series (PG7-126-M). It has its own load
# vintage/definition and DST hour labels; do not silently replace Native Load or
# merge by a naive timestamp. Metered generation / installed capacity is a
# realized output ratio, NOT an uncurtailed meteorological capacity factor.
multi=[]
multi_summary=[]
monthly_capacity=[]
for year in [2023,2024,2025]:
    name=f'ERCOT_{year}_Hourly_WindSolar_Output.xlsx'
    wind=pd.read_excel(RAW/name,sheet_name='Wind Data')
    solar=pd.read_excel(RAW/name,sheet_name='Solar Data')
    assert len(wind)==len(solar)==(8784 if year==2024 else 8760)
    assert wind.iloc[:,0].equals(solar.iloc[:,0])
    assert (wind['ERCOT.LOAD']-solar['ERCOT.LOAD']).abs().max()<1e-6
    x=pd.DataFrame({'source_year':year,'source_row_0based':range(len(wind)),
        'source_time_label':wind.iloc[:,0].astype(str),'source_date':wind['Date'].astype(str),
        'operational_load_MW':wind['ERCOT.LOAD'],'wind_metered_MW':wind['ERCOT.WIND.GEN'],
        'solar_metered_MW':solar['ERCOT.PVGR.GEN'],
        'wind_installed_MW':wind['Total Wind Installed, MW'],
        'solar_installed_MW':solar['Total Solar Installed, MW']})
    x['wind_realized_output_ratio']=x.wind_metered_MW/x.wind_installed_MW
    x['solar_realized_output_ratio']=x.solar_metered_MW/x.solar_installed_MW
    x['operational_residual_load_MW']=x.operational_load_MW-x.wind_metered_MW-x.solar_metered_MW
    assert not x.isna().any().any()
    multi.append(x)
    multi_summary.append({'year':year,'hours':len(x),
        'operational_load_peak_MW':x.operational_load_MW.max(),
        'wind_metered_TWh':x.wind_metered_MW.sum()/1e6,
        'solar_metered_TWh':x.solar_metered_MW.sum()/1e6,
        'installed_wind_start_MW':x.wind_installed_MW.iloc[0],
        'installed_wind_end_MW':x.wind_installed_MW.iloc[-1],
        'installed_solar_start_MW':x.solar_installed_MW.iloc[0],
        'installed_solar_end_MW':x.solar_installed_MW.iloc[-1]})
    months=(pd.to_datetime(wind.iloc[:,0])-pd.Timedelta(nanoseconds=1)).dt.month
    for mo,part in x.groupby(months):
        monthly_capacity.append({'year':year,'month':int(mo),'source_hours':len(part),
            'wind_installed_first_MW':part.wind_installed_MW.iloc[0],
            'wind_installed_last_MW':part.wind_installed_MW.iloc[-1],
            'solar_installed_first_MW':part.solar_installed_MW.iloc[0],
            'solar_installed_last_MW':part.solar_installed_MW.iloc[-1],
            'wind_mean_realized_output_ratio':part.wind_realized_output_ratio.mean(),
            'solar_mean_realized_output_ratio':part.solar_realized_output_ratio.mean(),
            'source_file':name})
pd.concat(multi).to_csv(OUT/'ERCOT_OPERATIONAL_WIND_SOLAR_2023_2025.csv.gz',index=False,compression='gzip')
write('OPERATIONAL_MULTIYEAR_SOURCE_SUMMARY.csv',multi_summary)
write('OPERATIONAL_MONTHLY_INSTALLED_CAPACITY.csv',monthly_capacity)
op=multi[-1]
comparison=pd.DataFrame({'source_row_0based':hour.source_row_0based,
    'native_HE_label':hour.source_HE_label,'operational_time_label':op.source_time_label,
    'native_load_MW':hour.native_load_MW,'operational_load_MW':op.operational_load_MW,
    'settled_wind_MW':hour.wind_actual_MW,'operational_wind_MW':op.wind_metered_MW,
    'settled_solar_MW':hour.solar_actual_MW,'operational_solar_MW':op.solar_metered_MW})
write('SOURCE_VINTAGE_COMPARISON_2025.csv',comparison)

qa={'status':'PASS','solver_calls':0,'hourly_rows':len(hour),'three_hour_rows':len(h3),
    'load_fuel_hour_keys_matched':8760,'daily_energy_QA_rows':len(daily_checks),
    'max_daily_fuel_MWh_abs_difference':max(r['abs_error_MWh'] for r in daily_checks),
    'native_load_TWh':float(hour.native_load_MW.sum()/1e6),
    'wind_actual_TWh':float(hour.wind_actual_MW.sum()/1e6),
    'solar_actual_TWh':float(hour.solar_actual_MW.sum()/1e6),
    'spring_transition_hours':int((hour.date=='2025-03-09').sum()),
    'autumn_transition_hours':int((hour.date=='2025-11-02').sum()),
    'mora_percentile_rows':len(qs),'mora_outage_quantile_rows':len(outages),
    'future_elcc_rows':len(credits),'supplemental_operational_years':[2023,2024,2025],
    'supplemental_operational_rows':sum(map(len,multi)),
    'operational_vs_native_load_MAE_MW':float(abs(op.operational_load_MW-hour.native_load_MW).mean()),
    'operational_vs_settled_wind_MAE_MW':float(abs(op.wind_metered_MW-hour.wind_actual_MW).mean()),
    'operational_vs_settled_solar_MAE_MW':float(abs(op.solar_metered_MW-hour.solar_actual_MW).mean()),
    'negative_actual_solar_hours':int((hour.solar_actual_MW<0).sum()),
    'negative_actual_wind_hours':int((hour.wind_actual_MW<0).sum()),
    'actual_generation_is_uncurtailed_availability':False,
    'UTC_conversion_claimed':False}
(OUT/'DATA_QA.json').write_text(json.dumps(qa,indent=2))
print(json.dumps(qa,indent=2))
print(ev[['event_id','date','source_HE_label','native_load_MW','observed_residual_load_MW']].to_string(index=False))
