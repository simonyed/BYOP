"""Reproduce v1.6 source extracts. No model loading, network mutation or solves.

Run: python rebuild_evidence.py (pandas/openpyxl). Paths are relative to this file.
Source values are intentionally kept separate from recommended model decisions.
"""
from pathlib import Path
import calendar
import hashlib
import json
import shutil
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'raw'
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=True)
PLANTS = {55501: 'Kiamichi', 55132: 'Tenaska Gateway', 68200: 'Sequoia 1',
          67123: 'Fagus', 68458: 'Buzios / Roaring Springs', 64202: 'Big Star',
          66919: 'La Casa', 66342: 'Gaia', 68998: 'Long Point', 56981: 'Pyron',
          66916: 'Danish Fields Storage', 66913: 'Myrtle Storage'}
PREFIXES = {'KMCHI_': (55501, 'Kiamichi', 1224.0),
            'TGCCS_': (55132, 'Tenaska Gateway', 826.0)}

def emit(name, rows):
    df = pd.DataFrame(rows)
    df.to_csv(OUT / name, index=False, encoding='utf-8-sig')
    return df

def number(v):
    return pd.to_numeric(pd.Series([v]), errors='coerce').iloc[0]

# Annual final EIA records; merely being on Operable does not prove OP.
annual = RAW / '3_1_Generator_Y2025.xlsx'
eia_rows = []
for sheet in ['Operable', 'Proposed', 'Retired and Canceled']:
    df = pd.read_excel(annual, sheet_name=sheet, header=1)
    for i, r in df[df['Plant Code'].isin(PLANTS)].iterrows():
        eia_rows.append({'plant_id': int(r['Plant Code']), 'item': PLANTS[int(r['Plant Code'])],
            'generator_id': r['Generator ID'], 'sheet': sheet, 'excel_row': int(i + 3),
            'plant_name': r['Plant Name'], 'county': r['County'], 'state': r['State'],
            'technology': r['Technology'], 'status': str(r['Status']).strip(),
            'nameplate_MW': number(r['Nameplate Capacity (MW)']),
            'summer_MW': number(r['Summer Capacity (MW)']),
            'operating_year': r.get('Operating Year'), 'operating_month': r.get('Operating Month'),
            'source_file': annual.name})
eia = emit('EIA860_2025_PRIORITY_PLANTS.csv', eia_rows)

# Monthly MORA headers have trailing formatting columns in March: capacity is J,
# never simply the final column. Values are prospective monthly capacities.
units, monthly, storage = [], [], []
for month in range(1, 13):
    path = RAW / f'MORA_{calendar.month_name[month]}2025.xlsx'
    df = pd.read_excel(path, sheet_name='Resource Details', header=None)
    assert 'UNIT CODE' in str(df.iat[1, 3])
    assert 'CAPACITY' in str(df.iat[1, 8])
    code = df.iloc[:, 3].fillna('').astype(str).str.strip()
    for prefix, (pid, item, physical) in PREFIXES.items():
        group = df[code.str.startswith(prefix)]
        assert len(group) >= (10 if pid == 55501 else 5), (path, prefix)
        vals = pd.to_numeric(group.iloc[:, 9], errors='coerce')
        # An August/September spacer row may have no capacity. It is never an asset.
        positive = vals[vals > 0].sum()
        negative = vals[vals < 0].sum()
        assert positive > 0 and negative <= 0
        net = positive + negative
        monthly.append({'year': 2025, 'month': month, 'plant_id': pid, 'item': item,
            'mora_positive_seasonal_MW': positive, 'mora_unavailable_adjustment_MW': negative,
            'mora_net_ercot_MW': net, 'model_physical_summer_MW': physical,
            'recommended_aggregate_dispatch_cap_MW': min(physical, net),
            'source_file': path.name, 'source_sheet': 'Resource Details',
            'interpretation': 'monthly planning availability envelope; not actual hourly outages'})
        for i, r in group.iterrows():
            if pd.isna(number(r.iloc[9])):
                continue
            units.append({'year': 2025, 'month': month, 'plant_id': pid,
                'ercot_unit_code': r.iloc[3], 'unit_name': r.iloc[1],
                'installed_rating_MW': number(r.iloc[8]), 'month_capacity_MW': number(r.iloc[9]),
                'excel_row': i + 1, 'source_file': path.name})
    for i, r in df[code.str.startswith(('DAN_BESS', 'MYR_BES'))].iterrows():
        storage.append({'month': month, 'ercot_unit_code': r.iloc[3], 'unit_name': r.iloc[1],
            'county': r.iloc[4], 'installed_MW': number(r.iloc[8]),
            'mora_seasonal_MW': number(r.iloc[9]), 'source_file': path.name,
            'excel_row': i + 1})
mon = emit('SWITCHABLE_2025_MONTHLY_AVAILABILITY.csv', monthly)
emit('SWITCHABLE_2025_SOURCE_ROWS.csv', units)
emit('STORAGE_2025_ERCOT_SOURCE_ROWS.csv', storage)
assert len(mon) == 24 and not mon.isna().any().any()
assert mon.query('month == 8').set_index('plant_id').mora_net_ercot_MW.to_dict() == {55501: 609, 55132: 556}

# CDR official forecast comparison references: preserve forecast vs observed scope.
cdr24 = RAW / 'CDR_December2024_Revised.xlsx'
refs, components = [], []
for sheet in ['Summer Summary', 'Winter Summary']:
    df = pd.read_excel(cdr24, sheet_name=sheet, header=None)
    for col, risk in [(3, 'peak_load'), (4, 'peak_net_load')]:
        for i, r in df.iterrows():
            labels = ' | '.join(str(x).strip() for x in r.iloc[:3] if pd.notna(x))
            value = number(r.iloc[col])
            if labels and pd.notna(value):
                components.append({'season': sheet.split()[0], 'risk_period': risk,
                    'excel_row': i+1, 'label': labels, 'value': value,
                    'source_file': cdr24.name, 'source_sheet': sheet,
                    'excel_column': 'D' if col == 3 else 'E'})
        if sheet == 'Summer Summary':
            firm, cap, margin = (float(df.iat[i, col]) for i in [16, 55, 57])
            assert abs((cap-firm)/firm - margin) < 1e-12
            refs.append({'year': 2025, 'season': 'summer', 'risk_period': risk,
                'forecast_normal_load_MW': df.iat[7, col], 'firm_load_MW': firm,
                'credited_capacity_MW': cap, 'prm_fraction': margin,
                'source_file': cdr24.name, 'denominator_cell': ('D17' if col == 3 else 'E17'),
                'numerator_cell': ('D56' if col == 3 else 'E56'),
                'prm_cell': ('D58' if col == 3 else 'E58'),
                'scope': 'published Feb 2025 forecast including eligible planned resources; not observed 2025'})
emit('CDR_2025_PRM_REFERENCE.csv', refs)
emit('CDR_2025_RESOURCE_DEMAND_COMPONENTS.csv', components)

elcc = pd.read_excel(cdr24, sheet_name='ELCCs', header=None)
elcc_rows=[]
for i in range(24, len(elcc)):
    label = str(elcc.iat[i, 0]).strip()
    if not label.startswith(('Wind -', 'Solar -', 'BESS', 'Energy Storage')):
        continue
    for col, risk in [(1, 'winter_morning'), (2, 'winter_evening'),
                      (3, 'summer_afternoon'), (4, 'summer_evening')]:
        val=number(elcc.iat[i, col])
        if pd.notna(val):
            elcc_rows.append({'reference_year': 2025, 'resource_type': label,
                'risk_period': risk, 'capacity_credit': val, 'excel_row': i+1,
                'excel_column': chr(65+col), 'source_file': cdr24.name})
credits=emit('CDR_2025_ELCC_REFERENCE.csv', elcc_rows)
assert len(credits) >= 24 and credits.capacity_credit.between(0,1).all()

# Future seasonal switchable schedules are separate from 2025 history.
cdr25=RAW / 'CDR_December2025.xlsx'
d=pd.read_excel(cdr25, sheet_name='Unit Details', header=2)
rows=[]
for prefix,(pid,item,physical) in PREFIXES.items():
    group=d[d['UNIT CODE'].fillna('').astype(str).str.startswith(prefix)]
    for col in [2026,2027,2028,2029,2030,'2026/2027','2027/2028','2028/2029','2029/2030','2030/2031']:
        vals=pd.to_numeric(group[col], errors='coerce')
        pos,neg=vals[vals>0].sum(),vals[vals<0].sum()
        rows.append({'plant_id':pid,'item':item,'season_label':str(col),
            'positive_seasonal_MW':pos,'unavailable_adjustment_MW':neg,
            'net_ercot_MW':pos+neg,'source_file':cdr25.name,'source_sheet':'Unit Details',
            'scope':'prospective seasonal ERCOT availability; not physical asset deletion'})
emit('SWITCHABLE_CDR_2026_2031_SEASONAL.csv',rows)

manifest=[]
url_mora=json.loads((ROOT/'mora_source_urls.json').read_text())
urls={
 '3_1_Generator_Y2025.xlsx':'https://www.eia.gov/electricity/data/eia860/xls/eia8602025.zip',
 'CDR_December2024_Revised.xlsx':'https://www.ercot.com/files/docs/2025/02/12/CapacityDemandandReservesReport_December2024.xlsx',
 'CDR_December2025.xlsx':'https://www.ercot.com/files/docs/2025/12/19/CapacityDemandandReservesReport_December2025.xlsx',
 'ERCOT_Constraints_Needs_2025.pdf':'https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf',
}
urls.update({f'MORA_{m}2025.xlsx':u for m,u in url_mora.items()})
for name,url in urls.items():
    path=RAW/name
    manifest.append({'file':str(path.relative_to(ROOT)), 'bytes':path.stat().st_size,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'official_url':url,
        'note':'annual generator workbook extracted without edits from EIA ZIP' if name.startswith('3_1') else ''})
(ROOT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
(OUT/'EXTRACT_QA.json').write_text(json.dumps({'monthly_plant_rows':len(mon),
    'eia_priority_rows':len(eia),'elcc_rows':len(credits),'official_prm_formula_checks':'PASS',
    'august_2025_net_MW':{'Kiamichi':609,'Gateway':556},'solver_calls':0},indent=2))
print(json.dumps({'status':'PASS','output_csvs':len(list(OUT.glob('*.csv'))),
    'monthly_rows':len(mon),'eia_rows':len(eia),'elcc_rows':len(credits),'solver_calls':0}))
