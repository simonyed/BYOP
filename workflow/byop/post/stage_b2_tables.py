#!/usr/bin/env python3
"""Stage B B2 (Grid-Only pilot) audit tables from the solved pilot_s01 case (pure post-processing, no solver):
    python byop/post/stage_b2_tables.py results/BYOP/mainline/MAINLINE_V13_GREAL_MID_PILOT_S01 \
        --b1-erm results/BYOP/mainline/MAINLINE_V13_GREAL_MID_ERMCAL --b1-s0cal results/BYOP/mainline/MAINLINE_V13_GREAL_MID_S0CAL

STAGE_B2_48_BUS_YEAR_GRID_ONLY.csv        8 Epoch buses x 2026-2031 S1_EARLIEST service, delay, POI and offer fields
STAGE_B2_S0_BACKGROUND_RELIABILITY.csv    formal S0 native / inherited-ramp shed per bus x year (from the frozen S0 shed)
STAGE_B2_S0_PUBLIC_EXPANSION.csv          public new capacity in operation and added per year (S0, S1_EARLIEST); B1 S0CAL excluded
STAGE_B2_POI_NETWORK_DIAGNOSTICS.csv      per bus: equipment rows, upgrades, POI dual, adjacent corridor congestion, ERM binding
STAGE_B2_B1_BASELINE_RECONCILIATION.csv   B1 file hashes, 9 S0CAL lines loaded, B1 calibration S0 vs B2 economic S0
STAGE_B2_AUDIT_CHECKLIST.csv              hard / scientific checks with PASS / FAIL / PENDING / NOT_APPLICABLE and evidence
Fields that the solved tables cannot give are written as NOT_RECORDED / PENDING_DIAGNOSTIC_EXPORT, never guessed.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
INP = HERE.parent / 'inputs'
BUSES = ['p600 0', 'p610 2', 'p630 2', 'p630 4', 'p630 5', 'p630 6', 'p630 9', 'p650 0']
NAMES = {'p600 0': 'Helios', 'p610 2': 'Abilene', 'p630 2': 'Red Oak', 'p630 4': 'Shackelford', 'p630 5': 'Temple',
         'p630 6': 'Midlothian', 'p630 9': 'Denton', 'p650 0': 'TX1/SAT14'}
YEARS = list(range(2026, 2032))
CAL_AIDC = {'TL73', 'TL63', 'TL3', 'TL26'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else 'MISSING'


def rd(d, nm, **kw):
    f = Path(d) / nm
    return pd.read_csv(f, **kw) if f.exists() and f.stat().st_size > 2 else pd.DataFrame()


def snapshot_weights(index, stress_days):
    """sample weights of ml_base_build: stress snapshots 3 h, other sampled snapshots share the rest of 8760 h"""
    ts = pd.DatetimeIndex(index.get_level_values(-1))
    per = index.get_level_values(0)
    st = ts.normalize().isin(pd.DatetimeIndex([d['day'] for d in stress_days]))
    w = pd.Series(0.0, index=index)
    for p in sorted(set(per)):
        m = per == p
        n_st, n_b = int((m & st).sum()), int((m & ~st).sum())
        w[m & st] = 3.0
        w[m & ~st] = (8760.0 - 3.0 * n_st) / max(n_b, 1)
    return w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('case'); ap.add_argument('--b1-erm', required=True); ap.add_argument('--b1-s0cal', required=True)
    a = ap.parse_args()
    C = Path(a.case)
    failed_run = not (C / 'case_manifest.json').exists()
    if failed_run:       # the case stopped before its final tables: use the per-scenario checkpoints that were written
        b1m = json.loads((Path(a.b1_s0cal) / 'case_manifest.json').read_text())
        gate = json.loads((C / 'RUN_GATE.json').read_text()) if (C / 'RUN_GATE.json').exists() else {}
        solves = {}
        for sj in sorted((C / 'scenarios').glob('*/solve.json')):
            solves[sj.parent.name] = json.loads(sj.read_text()).get('solve', {})
        man = dict(mainline=dict(stress=b1m['mainline']['stress'], gate=gate), checks={}, solves=solves,
                   baseline_sha256=None, s0_calibration=None, erm_cal=None)
        def cat(nm):
            fs = [pd.read_csv(f) for f in sorted((C / 'scenarios').glob(f'*/{nm}')) if f.stat().st_size > 2]
            return pd.concat(fs, ignore_index=True) if fs else pd.DataFrame()
        summ, poil, led, duals, upl = cat('scenario_summary.csv'), cat('poi_ledger.csv'), cat('ledger.csv'), cat('duals.csv'), cat('poi_upgrade_ledger.csv')
        summ = summ.set_index('scenario') if len(summ) else summ
        offer = pd.DataFrame()
    else:
        man = json.loads((C / 'case_manifest.json').read_text())
        summ = rd(C, 'scenario_summary.csv').set_index('scenario')
        poil, led, duals = rd(C, 'poi_ledger.csv'), rd(C, 'ledger.csv'), rd(C, 'duals.csv')
        upl, offer = rd(C, 'poi_upgrade_ledger.csv'), rd(C, 'S1_GRID_OFFER.csv')
    poi_a = pd.read_csv(INP / 'poi/GREAL_POI_ASSUMPTIONS.csv').set_index('bus')
    e0 = pd.read_csv(INP / 'poi/GREAL_POI_E0_SCHEDULE.csv')
    stress = (man.get('mainline') or {}).get('stress', {}).get('days', [])
    out = []

    def w(df, nm):
        df.to_csv(C / nm, index=False)
        out.append(nm)
    # ------------------------------------------------------------------ 1. 48 bus-year table
    s1 = poil[poil.scenario == 'S1_EARLIEST'].copy() if len(poil) else pd.DataFrame(columns=['site', 'year'])
    req = pd.read_csv(INP / 'dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv')
    req = req[req.scenario == 'mid']
    of = offer.rename(columns={'site': 'site'}).set_index(['site', 'year']) if len(offer) else pd.DataFrame()
    rows = []
    for b in BUSES:
        for y in YEARS:
            r = s1[(s1.site == b) & (s1.year == y)]
            if len(r) != 1 and failed_run:
                rq = float(req[(req.region_id == b) & (req.request_year <= y)].IT_MW.sum())
                rows.append(dict(site=b, name=NAMES[b], year=y, requested_IT_MW=rq, served_IT_MW=np.nan, delay_IT_MW=np.nan,
                                 status='NOT_AVAILABLE (S1_EARLIEST not solved: lexicographic pre-solve infeasible)',
                                 source='requested from MAINLINE_RESEARCH_COHORTS_TAMU64.csv (mid, cumulative); service NOT RUN'))
                continue
            if len(r) != 1:
                rows.append(dict(site=b, name=NAMES[b], year=y, status='MISSING_KEY' if len(r) == 0 else 'DUPLICATE_KEY'))
                continue
            r = r.iloc[0]
            o = of.loc[(b, y)] if len(of) and (b, y) in of.index else None
            rows.append(dict(
                site=b, name=NAMES[b], year=y, requested_IT_MW=r.requested_IT_MW, served_IT_MW=r.served_IT_MW,
                delay_IT_MW=r.requested_IT_MW - r.served_IT_MW, IT_energized_MW=r.get('IT_energized_MW', np.nan), PUE=r.PUE,
                equipment_total_MW=r.equipment_total_MW, equipment_fixed_MW=r.equipment_fixed_MW, poi_upgrade_MW_cum=r.poi_upgrade_MW_cum,
                certified_import_MW=r.get('certified_import_MW', np.nan), total_import_peak_MW=r.total_import_peak_MW,
                firm_import_MWh=r.firm_import_MWh, grid_import_MWh=r.get('grid_import_MWh', np.nan),
                facility_demand_MW_at_full_service=r.requested_IT_MW * r.PUE,
                procedure_ready_year=r.get('procedure_ready_year', np.nan), earliest_grid_COD=r.get('earliest_grid_COD', np.nan),
                poi_eq_dual_abs=r.get('poi_eq_dual_abs', np.nan),
                offer_firm_MW=o['offer_firm_MW'] if o is not None else np.nan,
                offer_firm_stress_certified_MW=o['offer_firm_stress_certified_MW'] if o is not None and 'offer_firm_stress_certified_MW' in o else np.nan,
                offer_cond_MW=o['offer_cond_MW'] if o is not None else np.nan,
                status='ZERO_REQUEST' if r.requested_IT_MW <= 1e-6 else ('SERVED' if r.requested_IT_MW - r.served_IT_MW <= 0.5 else 'DELAYED'),
                units='IT MW for requested/served/delay; facility MW (= IT x PUE) for equipment / import / offer',
                source='poi_ledger.csv (S1_EARLIEST) + S1_GRID_OFFER.csv'))
    t48 = pd.DataFrame(rows)
    for c_ in ['served_IT_MW', 'delay_IT_MW', 'poi_eq_dual_abs', 'total_import_peak_MW', 'equipment_total_MW']:
        if c_ not in t48:
            t48[c_] = np.nan
    w(t48, 'STAGE_B2_48_BUS_YEAR_GRID_ONLY.csv')
    # ------------------------------------------------------------------ 2. S0 background reliability (formal economic S0)
    fz = C / 'S0_shed_by_snapshot_frozen.csv.gz'
    rel = []
    if fz.exists():
        f = pd.read_csv(fz, index_col=[0, 1], parse_dates=[1])
        wt = snapshot_weights(f.index, stress)
        e = f.mul(wt, axis=0).groupby(level=0).sum()
        for col in e.columns:
            kind = 'inherited_ramp' if col.endswith(' inherited_ramp_unserved') else ('native_background' if col.endswith(' load_shed') else 'other')
            bus = col.replace(' inherited_ramp_unserved', '').replace(' load_shed', '')
            for y in e.index:
                rel.append(dict(bus=bus, year=int(y), kind=kind, shed_MWh=float(e.loc[y, col]), peak_shed_MW=float(f[col][f.index.get_level_values(0) == y].max())))
    rel = pd.DataFrame(rel)
    if len(rel):
        tot = rel.groupby(['year', 'kind']).agg(shed_MWh=('shed_MWh', 'sum'), peak_shed_MW=('peak_shed_MW', 'max')).reset_index().assign(bus='ALL_ERCOT')
        rel = pd.concat([tot, rel[rel.shed_MWh > 1e-6]], ignore_index=True)
        rel['source'] = 'S0_shed_by_snapshot_frozen.csv.gz x sample weights (stress 3 h; base share of 8760 h)'
    w(rel, 'STAGE_B2_S0_BACKGROUND_RELIABILITY.csv')
    # ------------------------------------------------------------------ 3. public expansion (S0, S1_EARLIEST), B1 S0CAL excluded
    pub = led[led.resource_path == 'public'].copy() if len(led) else pd.DataFrame()
    exp = []
    if len(pub):
        for (sc, car, y), g in pub.groupby(['scenario', 'carrier', 'year']):
            exp.append(dict(scenario=sc, carrier=car, year=int(y), in_operation_MW=float(g.capacity_MW.sum()),
                            added_this_year_MW=float(g[g.build_period == y].capacity_MW.sum()),
                            resource_capex_PV_USD=float(g.resource_capex_PV_USD.sum())))
        exp = pd.DataFrame(exp)
        ac = pub[(pub.carrier == 'AC_exp') & (pub.year == 2031)].groupby(['scenario', 'asset_id', 'zone']).capacity_MW.sum().reset_index()
        ac['corridor'] = ac.asset_id.str.replace(r'_exp\d+_fwd$', '', regex=True)
        top = ac.groupby(['scenario', 'corridor', 'zone']).capacity_MW.sum().reset_index().sort_values(['scenario', 'capacity_MW'], ascending=[True, False])
        top = top.groupby('scenario').head(10).rename(columns={'capacity_MW': 'in_operation_MW'}).assign(carrier='AC_exp_TOP10_CORRIDOR', year=2031)
        exp = pd.concat([exp, top], ignore_index=True)
        exp['note'] = 'endogenous priced public investment; B1 S0CAL uplift (fixed, cost-free, carrier AC_s0cal) is NOT included'
    w(pd.DataFrame(exp), 'STAGE_B2_S0_PUBLIC_EXPANSION.csv')
    # ------------------------------------------------------------------ 4. POI / network diagnostics
    corr = duals[duals.constraint == 'corridor_congestion'] if len(duals) else pd.DataFrame()
    ermd = duals[duals.constraint.astype(str).str.startswith('ERM')] if len(duals) else pd.DataFrame()
    cal = pd.read_csv(Path(a.b1_s0cal) / 'S0_CALIBRATION.csv')
    cal = cal[cal.added_MW > 0.5]
    diag = []
    for b in BUSES:
        x = t48[t48.site == b]
        ee = e0[e0.bus == b]
        cz = corr[(corr.scenario == 'S1_EARLIEST') & corr.zone.astype(str).str.contains(b.split()[0], regex=False)] if len(corr) else pd.DataFrame()
        u = upl[(upl.scenario == 'S1_EARLIEST') & (upl.zone == b)] if len(upl) else pd.DataFrame()
        diag.append(dict(
            site=b, name=NAMES[b], E0_preapproved_MW=float(ee[ee.preapproved].MW.sum()), E0_planned_unverified_MW=float(ee[~ee.preapproved].MW.sum()),
            E0_rows='; '.join(f"{r.site}:{r.MW:.0f}MW@{r.COD:.0f}{'' if r.preapproved else ' (planned, >= proc)'}" for r in ee.itertuples()),
            procedure_ready_year=float(poi_a.loc[b, 'earliest_grid_COD_base']), poi_upgrade_lead_y=float(poi_a.loc[b, 'poi_upgrade_lead_y_base']),
            poi_upgrades_built_MW_2031=float(u[u.year == 2031].capacity_MW.sum()) if len(u) else 0.0,
            poi_upgrade_first_year=int(u.build_period.min()) if len(u) else None,
            delay_MW_IT_years=float(x.delay_IT_MW.clip(lower=0).sum()), peak_delay_IT_MW=float(x.delay_IT_MW.max()),
            first_year_served=int(x[x.served_IT_MW > 0.5].year.min()) if (x.served_IT_MW > 0.5).any() else None,
            years_poi_eq_dual_nonzero=','.join(str(int(y)) for y in x[x.poi_eq_dual_abs > 1e-3].year) or 'none',
            years_poi_at_limit=','.join(str(int(r.year)) for r in x.itertuples() if r.delay_IT_MW > 0.5 and r.total_import_peak_MW >= 0.999 * r.equipment_total_MW - 1e-2) or 'none',
            adjacent_corridor_binding_years=','.join(sorted({str(int(y)) for y in cz[cz.binding == True].year})) if len(cz) else 'NOT_RECORDED',
            erm_binding_years=','.join(sorted({str(int(y)) for y in ermd[(ermd.scenario == 'S1_EARLIEST') & (ermd.binding == True)].year})) if len(ermd) else 'NOT_RECORDED',
            s0cal_lines_at_bus=';'.join(f"{r.line}:{r.added_MW:.0f}MW" for r in cal.itertuples() if b in (r.bus0, r.bus1)) or 'none',
            s0cal_line_flow_utilisation='PENDING_DIAGNOSTIC_EXPORT (line flows are not written by the solved case tables)',
            attribution='NOT_RUN (B4): bindings listed are observations, not shares of the delay'))
    w(pd.DataFrame(diag), 'STAGE_B2_POI_NETWORK_DIAGNOSTICS.csv')
    # ------------------------------------------------------------------ 5. B1 reconciliation
    b1e = json.loads((Path(a.b1_erm) / 'erm02_calibration.json').read_text())
    b1s = rd(a.b1_s0cal, 'scenario_summary.csv').set_index('scenario')
    s0c = man.get('s0_calibration') or {}
    rec = [dict(item='B1 ERM JSON sha256', B1=sha(Path(a.b1_erm) / 'erm02_calibration.json'), B2='used via --erm-cal',
                expected='7d0c02f1245ebba31d26cb303cd154600e0a6626853d7d2c2910a1a268807a19'),
           dict(item='B1 S0_CALIBRATION.csv sha256', B1=sha(Path(a.b1_s0cal) / 'S0_CALIBRATION.csv'), B2=s0c.get('sha256'),
                expected='30bf497ef009f3e120d43f7d6c2995fe0b7d82ffce9d1df2b5629131397454d5'),
           dict(item='baseline .nc sha256', B1='19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb', B2=man.get('baseline_sha256'),
                expected='19034285be0aa9b9906ab5b0e03778f3a16e7c1c39e97ac97b368d9097cafadb'),
           dict(item='S0CAL lines loaded (added_MW > 0.5)', B1=int(len(cal)), B2=s0c.get('n'), expected=9),
           dict(item='S0CAL MW loaded (sum of all rows incl. < 0.5 MW rows)', B1=round(float(pd.read_csv(Path(a.b1_s0cal) / 'S0_CALIBRATION.csv').added_MW.sum()), 4),
                B2=s0c.get('MW'), expected='1095.6 (rows > 0.5 MW); tiny rows not loaded'),
           dict(item='S0CAL MW at AIDC-adjacent lines (TL73, TL63, TL3, TL26)', B1=round(float(cal[cal.line.isin(CAL_AIDC)].added_MW.sum()), 4), B2='same fixed links', expected=665.8688)]
    for y, v in b1e['margin_by_period'].items():
        rec.append(dict(item=f'ERM margin {y}', B1=v, B2=(man.get('erm_cal') or {}).get(str(y), (man.get('erm_cal') or {}).get(int(y))), expected='identical'))
    for k in ['load_shed_MWh', 'native_background_unserved_MWh', 'inherited_ramp_unserved_MWh', 'public_resource_capex_PV_USD',
              'system_operating_PV_USD', 'social_real_resource_cost_USD', 'public_new_MW']:
        rec.append(dict(item=f'S0 {k}', B1=b1s.loc['S0', k] if 'S0' in b1s.index and k in b1s else None,
                        B2=summ.loc['S0', k] if 'S0' in summ.index and k in summ else None,
                        expected='B1 = calibration run (shed 1e8, uplift 1e7); B2 = economic S0 (shed 1e4, S0CAL fixed): may differ'))
    w(pd.DataFrame(rec), 'STAGE_B2_B1_BASELINE_RECONCILIATION.csv')
    # ------------------------------------------------------------------ 6. audit checklist
    chk = man.get('checks', {})
    solves = man.get('solves', {})
    ok = lambda v: 'PASS' if v is True else ('FAIL' if v is False else 'PENDING')
    keys = list(zip(t48.site, t48.year))
    if failed_run:
        b2gate = man['mainline'].get('gate', {})
        s0c = dict(n=None, note='case stopped before the manifest; S0CAL application is logged in S0 solve only')
    items = [
        ('HARD', 'S0 optimal', ok(solves.get('S0', {}).get('termination') == 'optimal'), 'case_manifest.json solves.S0'),
        ('HARD', 'S1_EARLIEST optimal', 'FAIL' if failed_run and 'S1_EARLIEST' not in solves else ok(solves.get('S1_EARLIEST', {}).get('termination') == 'optimal'),
         'RuntimeError: P0-2 lexicographic pre-solve not optimal (Gurobi status 3 = INFEASIBLE)' if failed_run else 'case_manifest.json solves.S1_EARLIEST'),
        ('HARD', 'integer / binary variables = 0', ok(all(v.get('integer_vars') == 0 for v in solves.values())) if failed_run and solves else ok(chk.get('true_LP')),
         'scenarios/*/solve.json integer_vars' if failed_run else 'checks.true_LP'),
        ('HARD', 'gate approved, approved SHA 8636c08d', ok((man.get('mainline') or {}).get('gate', {}).get('approved')), 'RUN_GATE.json'),
        ('HARD', 'B1 inputs hashes match', ok(all(r['B1'] == r['expected'] for r in rec[:2]) and (failed_run or man.get('baseline_sha256') == rec[2]['expected'])),
         'B1 file hashes in STAGE_B2_B1_BASELINE_RECONCILIATION.csv' + ('; baseline .nc hash checked in the pre-run sha256sum (B2 report section 1)' if failed_run else '')),
        ('HARD', '9 S0CAL lines loaded', 'PENDING' if failed_run else ok(s0c.get('n') == 9),
         '--s0-cal-file passed on the command line; load count is written to case_manifest.json only at case end (not reached)' if failed_run else 'case_manifest.json s0_calibration'),
        ('HARD', '48 unique bus-year keys', ok(len(keys) == 48 and len(set(keys)) == 48 and 'status' in t48 and not t48.status.isin(['MISSING_KEY', 'DUPLICATE_KEY']).any()), 'STAGE_B2_48_BUS_YEAR_GRID_ONLY.csv'),
        ('HARD', 'delay >= 0 and served <= requested', 'NOT_APPLICABLE' if t48.delay_IT_MW.isna().all() else ok(bool((t48.delay_IT_MW >= -1e-3).all())),
         'S1_EARLIEST not solved' if t48.delay_IT_MW.isna().all() else 'STAGE_B2_48_BUS_YEAR_GRID_ONLY.csv'),
        ('HARD', 'online IT monotone', ok(chk.get('online_IT_monotone')), 'checks.online_IT_monotone'),
        ('HARD', 'no-harm existing customers (S1 <= S0 + 0.001 MW)', ok(chk.get('no_harm_existing_customers')), f"scenario_summary no_harm_max_violation_MW = {summ.loc['S1_EARLIEST'].get('no_harm_max_violation_MW') if 'S1_EARLIEST' in summ.index else 'NA'}"),
        ('HARD', 'DC energy balance', ok(chk.get('dc_energy_balance')), 'checks.dc_energy_balance'),
        ('HARD', 'POI flow <= equipment', ok(chk.get('poi_flow_le_equipment')), 'checks.poi_flow_le_equipment'),
        ('HARD', 'no service before grid', ok(chk.get('no_service_before_grid_or_byop')), 'checks.no_service_before_grid_or_byop'),
        ('HARD', 'lexicographic pre-solve optimal (S1_EARLIEST)', 'FAIL' if failed_run and 'S1_EARLIEST' not in solves else ok(chk.get('lex_presolve_optimal')),
         'Gurobi status 3 (INFEASIBLE) in the exported lexicographic model' if failed_run else 'lex_S1_EARLIEST.json'),
        ('SCIENCE', 'formal S0 background shed ~ 0', 'PASS' if len(rel) and float(rel[rel.bus == 'ALL_ERCOT'].shed_MWh.sum()) < 1.0 else ('FAIL' if len(rel) else 'PENDING'), 'STAGE_B2_S0_BACKGROUND_RELIABILITY.csv'),
        ('SCIENCE', 'SCIENTIFIC_USE = PARTIAL_PILOT (expected for B2)', 'FAIL' if failed_run else ('PASS' if str(rd(C, 'MAINLINE_GATE_CHECKS.csv').set_index('check').result.get('SCIENTIFIC_USE', '')).startswith('PARTIAL_PILOT') else 'FAIL'),
         'collector not reached (run stopped)' if failed_run else 'MAINLINE_GATE_CHECKS.csv'),
        ('SCIENCE', 'line-flow utilisation of the 4 AIDC-adjacent S0CAL lines', 'PENDING', 'PENDING_DIAGNOSTIC_EXPORT: flows not saved'),
        ('SCIENCE', 'single-factor attribution of delays', 'NOT_APPLICABLE', 'B4 not authorised'),
    ]
    w(pd.DataFrame(items, columns=['level', 'check', 'result', 'evidence']), 'STAGE_B2_AUDIT_CHECKLIST.csv')
    print(json.dumps(dict(written=out), indent=1))


if __name__ == '__main__':
    main()
