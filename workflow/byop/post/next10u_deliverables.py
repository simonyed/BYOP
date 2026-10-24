#!/usr/bin/env python3
"""NEXT-10U return tables (pure post-processing, NO solver). Builds the lightweight deliverables 01-12 of the work package from the
solved NEXT-10U out_dirs (S0S1, A3), the three cost books (next10u_cost_books.py) and the H1 input audits; files that depend on a
stage that did not run are written with status NOT_RUN instead of being filled.
Run from workflow/:
    python byop/post/next10u_deliverables.py --s0s1 results/BYOP/next10u_engineering_cost_v1/S0S1 \
        [--a3 results/BYOP/next10u_engineering_cost_v1/A3] --out ../current_work_pckg/BYOP_NEXT_10U/RETURN
"""
from __future__ import annotations

import argparse, json, shutil, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import next10u_cost_books as CB  # noqa: E402

WF = HERE.parents[1]
PKG = WF.parent / 'current_work_pckg/BYOP_NEXT_10U'
TOL = 1e-2


def rd(p):
    p = Path(p)
    return pd.read_csv(p) if p.exists() and p.stat().st_size > 2 else pd.DataFrame()


def scen_dir(d, tag):
    if d is None:
        return None
    if tag == 'S2_final':
        sel = Path(d) / 'scenarios/S2_final/S2_SELECTION.json'
        if not sel.exists():
            return None
        tag = json.loads(sel.read_text())['selected_tag']
    ck = Path(d) / 'scenarios' / tag
    return ck if (ck / 'scenario_summary.csv').exists() else None


def delay_causes(poil, binding, inv, tag):
    """multi-cause classification of each unserved site-year (no single 'POI 3 years' label); several causes may hold together"""
    rows = []
    bset = set(binding[binding.binding].row) if len(binding) else set()
    for r in poil.itertuples():
        un = float(r.requested_IT_MW - r.served_IT_MW)
        eq = float(r.equipment_total_MW)
        need = float(r.requested_IT_MW * r.PUE)
        used = float(r.served_IT_MW * r.PUE)
        s, y = r.site, int(r.year)
        cands = inv[inv.site == s] if len(inv) else pd.DataFrame()
        reach = cands[(cands.firm_first_full_year <= y)] if len(cands) else cands
        causes = []
        if un > TOL:
            if eq < need - TOL:
                if not len(reach):
                    causes.append('NEW_DIRECT_UPGRADE_NOT_YET_AVAILABLE (equipment lead / first full firm year)')
                else:
                    if any(b.startswith(f'ENG-vis_{s}_') for b in bset):
                        causes.append('DISCLOSURE_CAP (undisclosed cohorts cannot be ordered)')
                    if any(b in (f'ENG-cum_site_{s}', f'ENG-cum_RIGHTED_{s}', f'ENG-cum_NEW_REQUEST_{s}') for b in bset):
                        causes.append('CUMULATIVE_SITE_OR_CLASS_CAP')
                    if not causes:
                        causes.append('NEW_DIRECT_UPGRADE_ECONOMIC_OR_LEAD (reachable candidate not built to need)')
                if float(r.equipment_fixed_MW) > 0:
                    causes.append('EXISTING_EQUIPMENT_FULLY_USED')
            if eq >= need - TOL or used < eq - TOL:
                causes.append('UPSTREAM_NETWORK_OR_RESOURCE_ADEQUACY (equipment slack but not delivered: KCL / reserve / no-harm / stress)')
        rows.append(dict(scenario=tag, site=s, year=y, requested_IT_MW=r.requested_IT_MW, served_IT_MW=r.served_IT_MW, unserved_IT_MW=un,
                         facility_need_MW=need, equipment_total_MW=eq, equipment_known_MW=r.equipment_fixed_MW, poi_upgrade_cum_MW=r.poi_upgrade_MW_cum,
                         equipment_used_MW=used, poi_eq_dual_abs=getattr(r, 'poi_eq_dual_abs', np.nan),
                         causes=' | '.join(causes) if causes else ('SERVED' if un <= TOL else 'UNCLASSIFIED')))
    return pd.DataFrame(rows)


def scenario_table(dirs):
    rows = []
    for tag, d in dirs.items():
        if d is None:
            continue
        s = pd.read_csv(d / 'scenario_summary.csv').iloc[0].to_dict()
        pl = rd(d / 'poi_ledger.csv')
        row = dict(scenario=tag, termination=s.get('termination'), objective=s.get('objective'), social_real_resource_cost_USD=s.get('social_real_resource_cost_USD'),
                   social_total_USD=s.get('social_total_USD'), private_total_USD=s.get('private_total_USD'),
                   public_resource_capex_PV_USD=s.get('public_resource_capex_PV_USD'), byop_resource_capex_PV_USD=s.get('byop_resource_capex_PV_USD'),
                   poi_upgrade_resource_capex_PV_USD=s.get('poi_upgrade_resource_capex_PV_USD'), system_operating_PV_USD=s.get('system_operating_PV_USD'),
                   load_shed_MWh=s.get('load_shed_MWh'), existing_shed_PV_USD=s.get('load_shed_PV_USD'), served_MW_IT_year=s.get('served_MW_IT_year'),
                   delay_MW_IT_year=s.get('delay_MW_IT_year'), requested_MW_IT_year=s.get('requested_MW_IT_year'),
                   social_delay_loss_PV_USD=s.get('social_delay_loss_PV_USD'), public_new_MW=s.get('public_new_MW'), byop_MW=s.get('byop_MW'),
                   poi_upgrade_MW=s.get('poi_upgrade_MW'), interruption_loss_PV_USD=s.get('interruption_loss_PV_USD'),
                   curtailment_loss_PV_USD=s.get('curtailment_loss_PV_USD'), no_harm_max_violation_MW=s.get('no_harm_max_violation_MW'),
                   solve_seconds=s.get('solve_seconds'))
        if len(pl):
            for y, g in pl.groupby('year'):
                row[f'served_IT_MW_{int(y)}'] = float(g.served_IT_MW.sum())
                row[f'unserved_IT_MW_{int(y)}'] = float(g.unserved_IT_MW.sum())
                row[f'byop_capacity_MW_{int(y)}'] = float(g.BYOP_capacity_MW.sum()) if 'BYOP_capacity_MW' in g else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def comparisons(tab):
    if not len(tab):
        return pd.DataFrame()
    t = tab.set_index('scenario')
    num = [c for c in t.columns if t[c].dtype.kind in 'fi']
    out = []
    for a, b, label in (('S1_EARLIEST', 'S0', 'S1-S0 (AIDC grid-only vs no new AIDC)'), ('S2_final', 'S1_EARLIEST', 'S2-S1 (BYOP developer vs grid-only)'),
                        ('S2_final', 'S3', 'S2-S3 (private vs social optimum; NOT matched service)'),
                        ('S2_final', 'S3_mS2', 'S2-S3_mS2 (private vs social at matched service)'), ('S3', 'S1_EARLIEST', 'S3-S1 (coordinated vs grid-only)')):
        if a in t.index and b in t.index:
            d = {c: float(t.loc[a, c]) - float(t.loc[b, c]) for c in num if pd.notna(t.loc[a, c]) and pd.notna(t.loc[b, c])}
            out.append(dict(comparison=label, a=a, b=b, **d))
        else:
            out.append(dict(comparison=label, a=a, b=b, status='NOT_RUN'))
    return pd.DataFrame(out)


def ledgers(d, prefix):
    if d is None:
        return pd.DataFrame(), pd.DataFrame()
    return rd(Path(d) / f'{prefix}_SOLVE_LOG.csv'), rd(Path(d) / f'{prefix}_OPTIMIZER_CALL_LOG.csv')


def build(s0s1, a3, out):
    o = Path(out); o.mkdir(parents=True, exist_ok=True)
    a3 = a3 if a3 and Path(a3).exists() else None
    dirs = {t: scen_dir(s0s1, t) for t in ('S0', 'S1_EARLIEST')}
    dirs.update({t: scen_dir(a3, t) for t in ('S3', 'S2_final', 'S3_mS2')})
    status = {t: ('SOLVED' if d is not None else 'NOT_RUN') for t, d in dirs.items()}
    # 01-04 inputs / POI
    pre = rd(PKG / 'preflight/INPUT_FILE_SHA256.csv')
    reg = rd(WF / 'byop/inputs/poi_eng/ENG_POI_SOURCE_REGISTER.csv')
    pre.assign(record='engineering package file (preflight)').to_csv(o / '01_DATA_INPUT_AUDIT.csv', index=False)
    reg.to_csv(o / '01b_MODEL_SOURCE_SHA_REGISTER.csv', index=False)
    shutil.copy2(PKG / 'H1/POI_INPUT_MODEL_DIFF.csv', o / '02_POI_INPUT_MODEL_DIFF.csv')
    ev = rd(PKG / 'H1/POI_ENGINEERING_EVENT_LEDGER.csv')
    inv_all = []
    for t, d in dirs.items():
        if d is not None and (d / 'eng_poi_investment.csv').exists():
            inv_all.append(rd(d / 'eng_poi_investment.csv'))
    inv_all = pd.concat(inv_all, ignore_index=True) if inv_all else pd.DataFrame()
    ev.to_csv(o / '03_POI_EVENT_LEDGER.csv', index=False)
    inv_all.to_csv(o / '03b_POI_INVESTMENT_LEDGER_SOLVED.csv', index=False)
    shutil.copy2(PKG / 'H1/EVIDENCE_GAPS.csv', o / '04_EVIDENCE_GAPS.csv')
    shutil.copy2(PKG / 'H1/COD_CAUSE_LEDGER.csv', o / '04b_COD_CAUSE_LEDGER.csv')
    # 05-08 books
    if dirs['S0'] is not None:
        bk = CB.build(s0s1, a3, o / 'books')
        bk['res'][bk['res'].asset_class.str.match('^[ABC]_')].to_csv(o / '05_PUBLIC_ASSET_LEDGER.csv', index=False)
        bk['com'].to_csv(o / '05b_PUBLIC_ASSET_LEDGER_COMMITTED_BACKGROUND.csv', index=False)
        bk['cau'].to_csv(o / '06_COST_CAUSATION_LEDGER.csv', index=False)
        bk['pay'].to_csv(o / '07_PAYMENT_RISK_LEDGER.csv', index=False)
        bk['inc'].to_csv(o / '08_COST_INCIDENT_MATRIX.csv', index=False)
        books_checks = bk['checks']
    else:
        books_checks = dict(status='NOT_RUN')
    # 09 solve ledger
    p2, c2 = ledgers(s0s1, 'A2'); p3, c3 = ledgers(a3, 'A3')
    sl = pd.concat([p2.assign(config='config.byop_next10u_s0s1.yaml', level='parent'), c2.assign(config='config.byop_next10u_s0s1.yaml', level='child'),
                    p3.assign(config='config.byop_next10u_a3.yaml', level='parent'), c3.assign(config='config.byop_next10u_a3.yaml', level='child')], ignore_index=True)
    sl.to_csv(o / '09_SCENARIO_SOLVE_LEDGER.csv', index=False)
    calls = int(len(c2) + len(c3))
    # 10 S0 science
    sv = Path(s0s1) / 'S0_SCIENCE_VERDICT.json'
    (o / '10_S0_SCIENCE_VERDICT.json').write_text(sv.read_text() if sv.exists() else json.dumps(dict(S0_SCIENCE_VERDICT='NOT_RUN')), encoding='utf-8')
    # 11 comparisons + delay causes
    tab = scenario_table(dirs)
    tab.to_csv(o / '11_SCENARIO_RESULTS.csv', index=False)
    comparisons(tab).to_csv(o / '11_CASE_COMPARISONS.csv', index=False)
    dc = []
    for t in ('S1_EARLIEST', 'S2_final', 'S3', 'S3_mS2'):
        d = dirs.get(t)
        if d is not None and (d / 'poi_ledger.csv').exists():
            dc.append(delay_causes(rd(d / 'poi_ledger.csv'), rd(d / 'eng_poi_binding.csv'), rd(d / 'eng_poi_investment.csv'), t))
    (pd.concat(dc, ignore_index=True) if dc else pd.DataFrame()).to_csv(o / '11b_DELAY_CAUSE_LEDGER.csv', index=False)
    # 12 matched service
    ms = Path(a3) / 'A3_RUN_SUMMARY.json' if a3 else None
    (o / '12_MATCHED_SERVICE_VERDICT.json').write_text(ms.read_text() if ms and ms.exists() else json.dumps(dict(status='NOT_RUN')), encoding='utf-8')
    summary = dict(stage_status=status, optimizer_calls_ledgered=calls, books_checks=books_checks, solver_calls_by_this_script=0)
    (o / 'DELIVERABLES_STATUS.json').write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--s0s1', required=True); ap.add_argument('--a3', default=None); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    print(json.dumps(build(a.s0s1, a.a3, a.out), indent=1, default=str))


if __name__ == '__main__':
    main()
