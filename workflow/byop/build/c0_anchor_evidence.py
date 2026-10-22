#!/usr/bin/env python3
"""C0 task A (ERCOT 2025 official anchor v1.3, 2026-10-22): rebuild the researcher's evidence extracts inside the repository.
Port of the package script rebuild_evidence.py (current_work_pckg/ERCOT_2025_Official_Anchor_v1.3/) with repository paths
(byop_paths) instead of the package folder. Reads tables only: no PyPSA import, no optimizer.
    python byop/build/c0_anchor_evidence.py
Inputs : data/byop/ercot_official_anchor_2025/raw/*  (SHA-256 checked against SOURCE_MANIFEST.json before use)
         results/BYOP/baseline_2025_tamu/baseline_2025_tamu_audit.json (the repository fleet, not the package snapshot)
Outputs: byop/inputs/anchor2025/  ERCOT_NATIVE_LOAD_2025_1H.csv, ERCOT_NATIVE_LOAD_2025_3H.csv, LOAD_MONTHLY_TWH.csv,
         HISTORICAL_DEMAND_STRESS_DAYS.csv, CAPACITY_DEFINITION_BRIDGE.csv, CAPACITY_TREND_DEC2025_EXTRACT.csv,
         CDR_DEC2025_UNIT_REGISTER_AUDIT_ONLY.csv, CDR_UNIT_STATUS_FUEL_SUMMARY.csv, FUEL_MIX_2025_GWH.csv,
         VERIFIED_METRICS.json, EVIDENCE_REBUILD_CHECK.json (value comparison with the researcher's derived tables)
Extraction rules are the package's, unchanged (same rows, cells, status buckets, 3 h row-order means, GWh as published).
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
import byop_paths as BP  # noqa: E402

RAW, OUT = BP.ANCHOR2025_RAW, BP.ANCHOR2025_DERIVED
PKG = BP.ANCHOR2025 / 'package_derived'          # researcher's derived tables (reference for the rebuild check)
NATIVE_SHA = '23664b0cddb047692f6cac26a4300e987c6309795395d394bf2dc223f37b53aa'
OFFICIAL = {'Thermal': 89507, 'Wind': 40719, 'Solar': 37443, 'Storage': 16656, 'Hydro': 579}
OFFICIAL_TOTAL, OFFICIAL_PEAK = 184904, 83707
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csv(d, name):
    d.to_csv(OUT / name, index=False, float_format='%.10f', lineterminator='\n')


def check_sources():
    man = json.loads(BP.ANCHOR2025_MANIFEST.read_text())
    bad = {s['file']: 'MISSING' if not (BP.ANCHOR2025 / s['file']).exists() else 'SHA_MISMATCH'
           for s in man['sources'] if not (BP.ANCHOR2025 / s['file']).exists() or sha(BP.ANCHOR2025 / s['file']) != s['sha256']}
    if bad:
        raise SystemExit(f'official source check failed: {bad}')
    return {s['file']: s['sha256'] for s in man['sources']}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = check_sources()
    native = pd.read_excel(RAW / 'Native_Load_2025.xlsx')
    assert len(native) == 8760
    assert native.iloc[:, 1:].notna().all().all()
    source_sha = sha(RAW / 'Native_Load_2025.xlsx')
    assert source_sha == NATIVE_SHA == sha(BP.NATIVE_LOAD), 'native load differs from the baseline builder input'
    zones = native.columns[1:9]
    assert (native[zones].sum(axis=1) - native.ERCOT).abs().max() < 0.00001
    hourly = native.copy()
    hourly.insert(0, 'source_row_1based', np.arange(2, len(native) + 2))
    hourly.insert(1, 'sequence_hour_1based', np.arange(1, 8761))
    hourly.insert(2, 'model_sequence_start', pd.date_range('2025-01-01', periods=8760, freq='h'))
    # model_sequence_start is a synthetic continuous alignment, NOT a conversion to UTC
    csv(hourly, 'ERCOT_NATIVE_LOAD_2025_1H.csv')
    three = native.iloc[:, 1:].groupby(np.arange(8760) // 3).mean()
    three.insert(0, 'model_sequence_start', pd.date_range('2025-01-01', periods=2920, freq='3h'))
    three.insert(1, 'weight_hours', 3)
    csv(three.reset_index(drop=True), 'ERCOT_NATIVE_LOAD_2025_3H.csv')
    peak = native.loc[native.ERCOT.idxmax()]
    metrics = dict(source_xlsx_sha256=source_sha, source_hash_matches_repository=True,
                   rows=len(native), energy_TWh=float(native.ERCOT.sum() / 1e6), peak_1h_MW=float(peak.ERCOT),
                   peak_1h_source_label=str(peak.iloc[0]), peak_3h_MW=float(three.ERCOT.max()),
                   zone_sum_max_abs_error_MW=float((native[zones].sum(axis=1) - native.ERCOT).abs().max()),
                   official_annual_report_peak_MW=OFFICIAL_PEAK, annual_report_minus_native_peak_MW=float(OFFICIAL_PEAK - peak.ERCOT),
                   source_DST_labels=native.loc[native.iloc[:, 0].str.contains('DST'), native.columns[0]].tolist(),
                   time_axis_policy='Preserve original HE strings; row-order alignment reproduces repository; synthetic timestamps are not UTC.')
    assert abs(three.ERCOT.sum() * 3 - native.ERCOT.sum()) < 0.001
    day = native.iloc[:, 0].str.slice(0, 10)
    monthly = native.assign(month=day.str.slice(0, 2)).groupby('month')[list(zones) + ['ERCOT']].sum() / 1e6
    csv(monthly.reset_index(), 'LOAD_MONTHLY_TWH.csv')
    daily = native.assign(date=day).groupby('date', sort=False).ERCOT.agg(['max', 'sum'])
    daily['month'] = daily.index.str.slice(0, 2).astype(int)
    selected = []
    for label, mask in [('summer_peak', daily.month.isin([6, 7, 8, 9])), ('winter_peak', daily.month.isin([1, 2, 12]))]:
        for dt, row in daily[mask].nlargest(3, 'max').iterrows():
            selected.append(dict(date=dt, selection=label, peak_MW=row['max'], energy_MWh=row['sum'], use='candidate for later validation; not solved'))
    csv(pd.DataFrame(selected), 'HISTORICAL_DEMAND_STRESS_DAYS.csv')
    audit = json.loads((BP.BASE_TAMU_DIR / 'baseline_2025_tamu_audit.json').read_text())
    fleet = audit['fleet_2025_MW_by_carrier']
    model = {'Thermal': sum(fleet[k] for k in ['CCGT', 'OCGT', 'gas_steam', 'coal', 'nuclear', 'biomass']),
             'Wind': fleet['onwind'], 'Solar': fleet['solar'], 'Storage': fleet['battery'], 'Hydro': fleet['hydro']}
    rows = [dict(category=k, official_annual_report_installed_MW=OFFICIAL[k], model_summer_based_MW=model[k], apparent_gap_MW=OFFICIAL[k] - model[k],
                 interpretation='Different ratings, coverage and statuses; not an instruction to add capacity') for k in OFFICIAL]
    rows.append(dict(category='Total', official_annual_report_installed_MW=OFFICIAL_TOTAL, model_summer_based_MW=audit['fleet_2025_MW_total'],
                     apparent_gap_MW=OFFICIAL_TOTAL - audit['fleet_2025_MW_total'], interpretation='Cross-definition diagnostic only'))
    csv(pd.DataFrame(rows), 'CAPACITY_DEFINITION_BRIDGE.csv')
    trend = []
    for sheet in pd.ExcelFile(RAW / 'Capacity_December2025.xlsx').sheet_names:
        t = pd.read_excel(RAW / 'Capacity_December2025.xlsx', sheet_name=sheet, header=None)
        ix = t.index[t.iloc[:, 0].astype(str).eq('2025')]
        assert len(ix) == 1
        i = ix[0]; r = t.loc[i]
        trend.append(dict(sheet=sheet, excel_row=int(i + 1), year=2025, chart_cumulative_MW=float(r.iloc[1]), operational_MW=float(r.iloc[2]),
                          IA_FS_MW=float(r.iloc[3]), IA_no_FS_MW=float(r.iloc[4]), other_planned_MW=float(r.iloc[5]), small_generator_MW=float(r.iloc[6]),
                          source='Capacity_December2025.xlsx; snapshot December 2025, published January 2026'))
    csv(pd.DataFrame(trend), 'CAPACITY_TREND_DEC2025_EXTRACT.csv')
    full = pd.read_excel(RAW / 'CDR_December2025.xlsx', sheet_name='Unit Details', header=2)
    units = full.copy()
    units.columns = [str(c).replace('\n', ' ').strip() for c in units.columns]
    units = units.iloc[:, :11].copy()
    units.insert(0, 'source_excel_row', np.arange(4, len(units) + 4))
    units['INSTALLED CAPACITY (MW)'] = pd.to_numeric(units['INSTALLED CAPACITY (MW)'], errors='coerce')
    units = units[units['INSTALLED CAPACITY (MW)'].notna()]
    units['diagnostic_status_bucket'] = units['CDR STATUS'].map(
        lambda s: 'PLANNED_EXCLUDE_FROM_2025' if str(s).startswith('PLAN') else 'INDEFINITE_MOTHBALLED_EXCLUDE' if s == 'MOTH-IND' else 'REQUIRES_STATUS_AND_CUTOFF_MATCH')
    units['audit_only_not_model_ready'] = True
    csv(units, 'CDR_DEC2025_UNIT_REGISTER_AUDIT_ONLY.csv')
    status = units.groupby(['CDR STATUS', 'CDR RESOURCE ATTRIBUTE', 'FUEL'], dropna=False)['INSTALLED CAPACITY (MW)'].agg(['count', 'sum']).reset_index()
    csv(status, 'CDR_UNIT_STATUS_FUEL_SUMMARY.csv')
    nuclear = units[units.FUEL.eq('NUCLEAR')]
    metrics['nuclear_CDR_installed_MW'] = float(nuclear['INSTALLED CAPACITY (MW)'].sum())
    metrics['nuclear_CDR_summer2026_MW'] = float(pd.to_numeric(full.loc[full.FUEL.eq('NUCLEAR'), 2026]).sum())
    metrics['model_nuclear_summer_based_MW'] = fleet['nuclear']
    fuel = pd.read_excel(RAW / 'IntGenbyFuel2025.xlsx', sheet_name='Summary', header=None)
    fuelrows = []
    for i in range(8, 19):
        r = fuel.iloc[i]
        for j in range(1, 14):
            fuelrows.append(dict(fuel=r.iloc[0], period='annual' if j == 13 else f'2025-{j:02d}', GWh=float(r.iloc[j]),
                                 source_cell=f'Summary!{chr(65 + j)}{i + 1}', basis='Published energy, GWh; includes negative WSL; do not multiply by 0.25'))
    csv(pd.DataFrame(fuelrows), 'FUEL_MIX_2025_GWH.csv')
    metrics['fuelmix_total_GWh'] = float(fuel.iloc[18, 13])
    metrics['fuelmix_total_minus_native_GWh'] = metrics['fuelmix_total_GWh'] - metrics['energy_TWh'] * 1000
    (OUT / 'VERIFIED_METRICS.json').write_bytes((json.dumps(metrics, indent=2, ensure_ascii=False) + '\n').encode())
    chk = compare_with_package(metrics)
    chk['official_sources_sha256'] = src
    chk['baseline_audit_sha256'] = sha(BP.BASE_TAMU_DIR / 'baseline_2025_tamu_audit.json')
    chk['outputs_sha256'] = {p.name: sha(p) for p in sorted(OUT.glob('*')) if p.name != 'EVIDENCE_REBUILD_CHECK.json'}
    (OUT / 'EVIDENCE_REBUILD_CHECK.json').write_bytes((json.dumps(chk, indent=1) + '\n').encode())
    print(json.dumps(dict(metrics=metrics, rebuild_check={k: v for k, v in chk.items() if k not in ('outputs_sha256', 'official_sources_sha256')}), indent=1))
    if not chk['all_equal']:
        raise SystemExit('rebuild differs from the researcher derived tables')


def compare_with_package(metrics):
    """value comparison (not byte: pandas versions format differently) of every derived table and metric"""
    if not PKG.exists():
        return dict(all_equal=None, note='package_derived not available here')
    res = {}
    for p in sorted(PKG.glob('*.csv')):
        a, b = pd.read_csv(p), pd.read_csv(OUT / p.name)
        ok = list(a.columns) == list(b.columns) and a.shape == b.shape
        if ok:
            for c in a.columns:
                if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
                    ok &= bool(np.allclose(a[c].values, b[c].values, rtol=0, atol=1e-6, equal_nan=True))
                else:
                    na = a[c].isna() & b[c].isna()                      # missing on both sides = equal
                    ok &= bool((na | (a[c].astype(str) == b[c].astype(str))).all())
        res[p.name] = ok
    pm = json.loads((PKG / 'VERIFIED_METRICS.json').read_text())
    mres = {k: (abs(v - metrics[k]) < 1e-6 if isinstance(v, float) else v == metrics[k]) for k, v in pm.items()}
    return dict(all_equal=all(res.values()) and all(mres.values()), tables=res, metrics=mres)


if __name__ == '__main__':
    main()
