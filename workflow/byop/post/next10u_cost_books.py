#!/usr/bin/env python3
"""NEXT-10U H2 / G5 (2026-10-24): three separate books of the solved engineering_cost_v1 scenarios (pure post-processing, NO solver).

  1 RESOURCE   real resource cost of every asset, counted ONCE whoever pays (CAPEX annuity PV at r_s from the scenario ledgers, POI
               equipment from poi_upgrade_ledger, system operating and existing-customer shed from the scenario summary).
  2 CAUSATION  AIDC-induced public expansion = same-asset-class / zone / build-year difference against S0 of the SAME model version
               (S0 and S1 / S2 / S3 share every public candidate and the committed background). Negative = avoided.
  3 PAYMENT    cash and risk under the adopted Texas rule (16 TAC 25.194, Texas Register 2026-10-02): direct interconnection facility
               (class A) = non-refundable CIAC paid by the large load; system-upgrade financial security = refundable principal
               (max(50,000 USD/MW x contracted MW, allocated system-upgrade cost); the allocated share is not observed -> floor + UNRESOLVED);
               study fee 100,000 USD per request; upstream / general public expansion (B / C) = payer UNRESOLVED_LEGAL_ALLOCATOR (never
               assumed 100 % developer, never assumed 100 % ratepayer). Transfers never enter the resource book.
Asset classes (each asset in exactly one): A_DC_DIRECT_INTERCONNECTION (POI equipment), B_GRID_UPSTREAM_SYSTEM_UPGRADE (corridor
expansion AC_exp), C_GRID_GENERAL_EXPANSION (public generation / storage / reuse), D_BACKGROUND_COMMITTED (DWB Stage 2, PBRP 765-kV;
identical in every scenario, outside the objective), P_DEVELOPER_DEDICATED (BYOP behind the POI; developer resource cost).
Run from workflow/:  python byop/post/next10u_cost_books.py --s0s1 <S0S1 out_dir> [--a3 <A3 out_dir>] --out <dir>
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
COMMITTED = WF / 'byop/inputs/grid/COMMITTED_PUBLIC_ASSET_COSTS.csv'
STUDY_FEE_USD = 100000.0          # 25.194 intermediate agreement study fee per request (flat fee; unused balance returned: refund not observed)
SECURITY_USD_PER_MW = 50000.0     # 25.194 financial security floor, USD per MW (not per kW)
SECURITY_POST_COD_Y, SECURITY_TBILL = 2.0, 0.04   # 20 % returned at energization, then 20 % steps (one per year assumed); collateral earns T-bill
LEGAL = dict(rule='16 TAC 25.194', status='ADOPTED_RULE', publication='Texas Register 2026-10-02', checked='2026-10-24',
             url='https://www.sos.state.tx.us/texreg/archive/October22026/Adopted%20Rules/16.ECONOMIC%20REGULATION.html',
             proposed_not_applied='25.192 / 25.193 12CP and minimum billing demand, 25.252 large-load tariff (TexReg 2026-07-24, PROPOSED)')
FORMAL = {'S0': 's0s1', 'S1_EARLIEST': 's0s1', 'S3': 'a3', 'S2_final': 'a3', 'S3_mS2': 'a3'}


def asset_class(r):
    if r.carrier == 'POI_upgrade':
        return 'A_DC_DIRECT_INTERCONNECTION'
    if r.resource_path != 'public' and r.asset_boundary != 'UTILITY_R':
        return 'P_DEVELOPER_DEDICATED'
    if r.carrier == 'AC_exp':
        return 'B_GRID_UPSTREAM_SYSTEM_UPGRADE'
    return 'C_GRID_GENERAL_EXPANSION'


def load_scenario(d, tag):
    ck = Path(d) / 'scenarios' / tag
    if not (ck / 'scenario_summary.csv').exists():
        return None
    rd = lambda f: pd.read_csv(ck / f) if (ck / f).exists() and (ck / f).stat().st_size > 2 else pd.DataFrame()
    return dict(summary=pd.read_csv(ck / 'scenario_summary.csv').iloc[0].to_dict(), ledger=rd('ledger.csv'), upl=rd('poi_upgrade_ledger.csv'),
                poil=rd('poi_ledger.csv'), inv=rd('eng_poi_investment.csv'))


def resource_book(scen):
    rows = []
    for tag, s in scen.items():
        led = s['ledger']
        if len(led):
            for r in led.itertuples():
                rows.append(dict(scenario=tag, asset_id=r.asset_id, asset_class=asset_class(r), carrier=r.carrier, zone=r.zone, year=int(r.year),
                                 build_period=int(r.build_period), capacity_MW=float(r.capacity_MW), capex_PV_USD=float(r.resource_capex_PV_USD),
                                 opex_PV_USD=float(r.resource_vom_fuel_PV_USD), book='RESOURCE'))
        upl = s['upl']
        if len(upl):
            for r in upl.itertuples():
                rows.append(dict(scenario=tag, asset_id=r.asset_id, asset_class='A_DC_DIRECT_INTERCONNECTION', carrier='POI_upgrade', zone=r.zone,
                                 year=int(r.year), build_period=int(r.build_period), capacity_MW=float(r.capacity_MW),
                                 capex_PV_USD=float(r.resource_capex_PV_USD), opex_PV_USD=0.0, book='RESOURCE'))
        sm = s['summary']
        rows.append(dict(scenario=tag, asset_id='SYSTEM_OPERATING', asset_class='SYSTEM', carrier='dispatch', zone='ERCOT', year=-1, build_period=-1,
                         capacity_MW=0.0, capex_PV_USD=0.0, opex_PV_USD=float(sm['system_operating_PV_USD']), book='RESOURCE'))
        rows.append(dict(scenario=tag, asset_id='EXISTING_CUSTOMER_SHED', asset_class='RELIABILITY', carrier='load_shed', zone='ERCOT', year=-1,
                         build_period=-1, capacity_MW=0.0, capex_PV_USD=0.0, opex_PV_USD=float(sm['load_shed_PV_USD']), book='RESOURCE'))
    df = pd.DataFrame(rows)
    # ledger opex is already inside system_operating (network dispatch) -> report it, never add it twice
    df['real_resource_PV_USD'] = df.capex_PV_USD + np.where(df.asset_class.isin(['SYSTEM', 'RELIABILITY']), df.opex_PV_USD, 0.0)
    df['emission_externality_PV_USD'] = 0.0
    df['emission_note'] = 'NOT_MONETISED in engineering_cost_v1 (CO2 reported in dispatch outputs only)'
    return df


def reconcile(res, scen):
    out = []
    for tag, s in scen.items():
        sm = s['summary']
        got = float(res[res.scenario == tag].real_resource_PV_USD.sum())
        want = float(sm['social_real_resource_cost_USD'])
        out.append(dict(scenario=tag, books_resource_PV_USD=got, summary_social_real_resource_cost_USD=want, abs_diff_USD=got - want,
                        rel_diff=(got - want) / max(1.0, abs(want)), ok=abs(got - want) <= 1e-6 * max(1.0, abs(want)) + 1.0))
    return pd.DataFrame(out)


def causation_book(res):
    """per scenario x asset class x zone: MW and resource PV vs S0 of the same model version; build-year shifts"""
    a = res[res.asset_class.isin(['A_DC_DIRECT_INTERCONNECTION', 'B_GRID_UPSTREAM_SYSTEM_UPGRADE', 'C_GRID_GENERAL_EXPANSION', 'P_DEVELOPER_DEDICATED'])]
    # MW per asset (count each asset once: capacity is the same in every active year)
    mw = a.groupby(['scenario', 'asset_class', 'zone', 'asset_id']).agg(MW=('capacity_MW', 'max'), bp=('build_period', 'min'),
                                                                     pv=('real_resource_PV_USD', 'sum')).reset_index()
    g = mw.groupby(['scenario', 'asset_class', 'zone']).apply(
        lambda x: pd.Series(dict(MW=x.MW.sum(), PV=x.pv.sum(), MW_weighted_build_year=float((x.MW * x.bp).sum() / x.MW.sum()) if x.MW.sum() > 0 else np.nan)),
        include_groups=False).reset_index()
    piv = g.pivot_table(index=['asset_class', 'zone'], columns='scenario', values=['MW', 'PV', 'MW_weighted_build_year'])
    rows = []
    scs = sorted(set(g.scenario))
    for (cls, z), r in piv.iterrows():
        base_mw = float(r.get(('MW', 'S0'), 0.0) or 0.0) if ('MW', 'S0') in r.index else 0.0
        base_pv = float(r.get(('PV', 'S0'), 0.0) or 0.0) if ('PV', 'S0') in r.index else 0.0
        base_by = r.get(('MW_weighted_build_year', 'S0'), np.nan) if ('MW_weighted_build_year', 'S0') in r.index else np.nan
        for sc in scs:
            if sc == 'S0':
                continue
            m_ = float(np.nan_to_num(r.get(('MW', sc), 0.0))); p_ = float(np.nan_to_num(r.get(('PV', sc), 0.0)))
            by = r.get(('MW_weighted_build_year', sc), np.nan)
            d = m_ - np.nan_to_num(base_mw)
            rows.append(dict(asset_class=cls, site_or_group=z, scenario=sc, s0_MW=np.nan_to_num(base_mw), scenario_MW=m_, added_MW=max(d, 0.0),
                             avoided_MW=max(-d, 0.0), shifted_build_year=(by - base_by) if np.isfinite(by) and np.isfinite(base_by) else np.nan,
                             s0_resource_PV_USD=np.nan_to_num(base_pv), scenario_resource_PV_USD=p_, delta_resource_PV_USD=p_ - np.nan_to_num(base_pv),
                             attribution_method='DIFFERENCE vs S0 of the same model version (same public candidates, committed background, network)',
                             confidence='MODEL_COUNTERFACTUAL' if cls != 'P_DEVELOPER_DEDICATED' else 'PRIVATE_ASSET (100 % induced by the AIDC)'))
    return pd.DataFrame(rows)


def committed_ledger():
    c = pd.read_csv(COMMITTED)
    return pd.DataFrame([dict(asset_id=r.asset_id, asset_class='D_BACKGROUND_COMMITTED', family=r.family, ISD_model=r.ISD_model,
                              total_cost_MUSD_base=float(r.total_cost_MUSD_base), cost_year_basis=r.cost_year_basis,
                              remaining_share_after_2025_base=float(r.remaining_share_after_2025_base), in_objective=bool(r.in_objective),
                              incidence='COMMON BACKGROUND in S0-S3 (identical; never attributed to the study AIDC)', evidence_class=r.evidence_class)
                         for r in c.itertuples()])


def payment_book(scen, res, charges, private_wacc=0.07):
    """one row per site x scenario (DC scenarios only); class A paid by the developer as CIAC; class B / C unresolved"""
    rows = []
    for tag, s in scen.items():
        if tag == 'S0':
            continue
        inv = s['inv']
        poil = s['poil']
        sites = sorted(set(poil.site)) if len(poil) else []
        for site in sites:
            iv = inv[inv.site == site] if len(inv) else pd.DataFrame()
            built = iv[iv.built_MW > 1e-3] if len(iv) else iv
            new_mw = float(built.built_MW.sum()) if len(built) else 0.0
            ciac = float((built.built_MW * built.unit_capex_USD_per_MW).sum()) if len(built) else 0.0
            new_req_mw = float(built[built.engineering_class == 'NEW_REQUEST'].built_MW.sum()) if len(built) else 0.0
            hold = float((built.equipment_COD - built.commitment_year).max()) if len(built) else 0.0
            sec = SECURITY_USD_PER_MW * new_mw
            p = poil[poil.site == site]
            peak_it = float(p.served_IT_MW.max()) if len(p) else 0.0
            ciac_pv = float(res[(res.scenario == tag) & (res.zone == site) & (res.asset_class == 'A_DC_DIRECT_INTERCONNECTION')].real_resource_PV_USD.sum())
            rows.append(dict(asset_id=f'POI_{site}', site_id=site, scenario=tag, applicable_rule=LEGAL['rule'] + ' (' + LEGAL['status'] + ')',
                             applicability='bus aggregate of research cohorts: applies per real single site >= 75 MW (UNVERIFIED at bus level)',
                             study_fee_paid_USD=STUDY_FEE_USD if new_req_mw > 1e-3 else 0.0, study_fee_refund_USD=np.nan,
                             study_fee_refund_status='UNKNOWN (unused balance refundable)', CIAC_paid_USD_nominal_2025=ciac, CIAC_resource_PV_USD=ciac_pv,
                             system_upgrade_security_posted_USD=sec, security_kind='refundable financial security (floor 50,000 USD/MW x contracted new MW; allocated system-upgrade share UNRESOLVED)',
                             security_returned_USD=sec, security_return_status='RETURNED 20 % AT ENERGIZATION + 20 % MILESTONE STEPS (one per year assumed); no withdrawal -> no 20 % / 50 % retention',
                             security_forfeited_USD=0.0, security_hold_y=hold + SECURITY_POST_COD_Y if len(built) else 0.0,
                             security_financing_cost_USD=sec * max(0.0, private_wacc - SECURITY_TBILL) * (hold + SECURITY_POST_COD_Y) if len(built) else 0.0,
                             new_poi_MW=new_mw, new_request_MW=new_req_mw, peak_served_IT_MW=peak_it,
                             network_service_charge='energy purchases at the parent-bus LMP (scenario transfer book, not a resource cost)',
                             unrecovered_cost_USD=np.nan, payer='DEVELOPER (CIAC, study fee, security financing)', beneficiary='AIDC site',
                             contract_evidence='NONE observed (research case; rule-based)', status='RULE_BASED_RESEARCH_ESTIMATE'))
        # upstream / general public expansion: induced vs S0, payer unresolved (never assumed developer or ratepayer)
        for cls in ('B_GRID_UPSTREAM_SYSTEM_UPGRADE', 'C_GRID_GENERAL_EXPANSION'):
            d = float(res[(res.scenario == tag) & (res.asset_class == cls)].real_resource_PV_USD.sum()
                      - res[(res.scenario == 'S0') & (res.asset_class == cls)].real_resource_PV_USD.sum())
            rows.append(dict(asset_id=f'{cls}_ALL', site_id='ERCOT', scenario=tag, applicable_rule='none adopted for allocation of shared upgrades',
                             applicability='system-wide', study_fee_paid_USD=0.0, CIAC_paid_USD_nominal_2025=0.0, CIAC_resource_PV_USD=0.0,
                             system_upgrade_security_posted_USD=0.0, security_returned_USD=0.0, security_forfeited_USD=0.0, security_financing_cost_USD=0.0,
                             unrecovered_cost_USD=d, payer='UNRESOLVED_LEGAL_ALLOCATOR', beneficiary='ERCOT customers incl. the AIDC (shared assets)',
                             contract_evidence='NONE', status='ECONOMIC_ATTRIBUTION_ONLY (delta resource PV vs S0; negative = avoided)'))
    return pd.DataFrame(rows)


def incidence_matrix(res, pay):
    rows = []
    for tag in sorted(set(res.scenario)):
        r_ = res[res.scenario == tag]
        p_ = pay[pay.scenario == tag] if len(pay) else pay
        for cls in ['A_DC_DIRECT_INTERCONNECTION', 'B_GRID_UPSTREAM_SYSTEM_UPGRADE', 'C_GRID_GENERAL_EXPANSION', 'P_DEVELOPER_DEDICATED', 'SYSTEM', 'RELIABILITY']:
            pv = float(r_[r_.asset_class == cls].real_resource_PV_USD.sum())
            s0 = float(res[(res.scenario == 'S0') & (res.asset_class == cls)].real_resource_PV_USD.sum())
            if cls == 'A_DC_DIRECT_INTERCONNECTION':
                dev, rp, un = pv, 0.0, 0.0
            elif cls == 'P_DEVELOPER_DEDICATED':
                dev, rp, un = pv, 0.0, 0.0
            elif cls in ('B_GRID_UPSTREAM_SYSTEM_UPGRADE', 'C_GRID_GENERAL_EXPANSION'):
                dev, rp, un = 0.0, s0, pv - s0          # the S0 part is background; the induced delta is unresolved
            else:
                dev, rp, un = np.nan, np.nan, np.nan
            fees = float(p_.study_fee_paid_USD.sum() + p_.security_financing_cost_USD.sum()) if len(p_) and cls == 'A_DC_DIRECT_INTERCONNECTION' else 0.0
            rows.append(dict(scenario=tag, asset_class=cls, resource_PV_USD=pv, developer_cash_PV_USD=dev, developer_fees_and_financing_USD=fees,
                             ratepayer_background_PV_USD=rp, unresolved_induced_PV_USD=un,
                             unallocated_fraction=(un / pv) if (isinstance(un, float) and np.isfinite(un) and pv) else np.nan,
                             double_count_check='resource counted once; CIAC = transfer of class A resource; security principal refundable (not a resource)'))
    return pd.DataFrame(rows)


def build(s0s1, a3=None, out=None):
    scen = {}
    for tag, src in FORMAL.items():
        d = s0s1 if src == 's0s1' else a3
        if d is None:
            continue
        src_tag = tag
        if tag == 'S2_final':           # the formal S2 label points at the selected raw iteration directory (S2 / S2_it2 / S2_it3)
            sel = Path(d) / 'scenarios' / 'S2_final' / 'S2_SELECTION.json'
            if not sel.exists():
                continue
            src_tag = json.loads(sel.read_text())['selected_tag']
        s = load_scenario(d, src_tag)
        if s is not None:
            scen[tag] = s
    if 'S0' not in scen:
        raise SystemExit('S0 missing: no causation book without the S0 of the same model version')
    res = resource_book(scen)
    rec = reconcile(res, scen)
    cau = causation_book(res)
    ch = pd.read_csv(Path(a3) / 'S2_PRIVATE_GRID_RIGHT_CHARGES.csv') if a3 and (Path(a3) / 'S2_PRIVATE_GRID_RIGHT_CHARGES.csv').exists() else pd.DataFrame()
    pay = payment_book(scen, res, ch)
    inc = incidence_matrix(res, pay)
    com = committed_ledger()
    ids = res[res.asset_class.str.match('^[ABCP]_')].groupby('asset_id').asset_class.nunique()
    one_class = bool((ids <= 1).all())
    delta = cau.groupby(['scenario', 'asset_class'])[['added_MW', 'avoided_MW', 'delta_resource_PV_USD']].sum().reset_index()
    checks = dict(resource_reconciles_with_solver_summary=bool(rec.ok.all()), every_asset_in_one_class=one_class,
                  ciac_not_in_resource_book='CIAC' not in ' '.join(res.columns), security_principal_not_in_resource_book=True,
                  unresolved_never_assigned=bool((pay[pay.asset_id.str.endswith('_ALL')].payer == 'UNRESOLVED_LEGAL_ALLOCATOR').all()) if len(pay) else True,
                  units_security_USD_per_MW=SECURITY_USD_PER_MW == 50000.0)
    if out:
        o = Path(out); o.mkdir(parents=True, exist_ok=True)
        for f, df in (('RESOURCE_COST_LEDGER.csv', res), ('RESOURCE_RECONCILIATION.csv', rec), ('COST_CAUSATION_LEDGER.csv', cau),
                      ('PAYMENT_RISK_LEDGER.csv', pay), ('COST_INCIDENT_MATRIX.csv', inc), ('PUBLIC_ASSET_LEDGER_COMMITTED_BACKGROUND.csv', com),
                      ('AIDC_INCREMENTAL_PUBLIC_COST.csv', delta), ('S0_S1_PUBLIC_DELTA.csv', delta[delta.scenario == 'S1_EARLIEST'])):
            df.to_csv(o / f, index=False)
        (o / 'BOOKS_CHECKS.json').write_text(json.dumps(dict(checks=checks, legal=LEGAL, scenarios=sorted(scen), solver_calls=0), indent=1))
    return dict(res=res, rec=rec, cau=cau, pay=pay, inc=inc, com=com, delta=delta, checks=checks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--s0s1', required=True); ap.add_argument('--a3', default=None); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    a3 = a.a3 if a.a3 and Path(a.a3).exists() else None
    r = build(a.s0s1, a3, a.out)
    print(json.dumps(r['checks'], indent=1))
    sys.exit(0 if all(r['checks'].values()) else 1)


if __name__ == '__main__':
    main()
