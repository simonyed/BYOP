#!/usr/bin/env python3
"""Stage B3-E mechanism tables from the solved pilot_core_b3e case (pure post-processing, no solver):
    python byop/post/stage_b3_tables.py results/BYOP/mainline/MAINLINE_V13_GREAL_MID_B3_EXPLORATORY_V1

STAGE_B3_M1_SPEED_DELIVERY_BY_SITE_YEAR.csv     research buses x model years x {S1_EARLIEST, S2_final, S3, S3_mS2}: request / service / delay,
                                                S2_final - S1 acceleration, S2 mode label, BYOP MW, 2026 ERM method flag
STAGE_B3_M2_PUBLIC_EXPANSION_BY_CARRIER_YEAR.csv public new capacity in operation / added per scenario x carrier x zone x year
                                                and the deltas S1-S0, S2_final-S1, S3_mS2-S2_final (B1 S0CAL excluded)
STAGE_B3_M2_ASSET_COMMITMENT_AND_COD.csv        every built asset of the formal scenarios: approval year, build period, COD, MW
STAGE_B3_M4_COST_COMPONENTS.csv                 cost books per formal scenario + S2_final - S3_mS2 (VOLL kept apart from physical)
STAGE_B3_CHECKS_AND_METHOD_FLAGS.csv            gate checks and the B2.5 status layers
STAGE_B3_EXPLORATORY_AUDIT.json                 solves, sizes, hashes, S2 selection, key gates
Formal scenario set: S0, S1_EARLIEST, S3, S2_final, S3_mS2 (raw S2 / S2_itN only in the MAINLINE_DIAGNOSTIC_* tables).
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('collect_mainline', HERE / 'collect_mainline.py')
CM = importlib.util.module_from_spec(spec); spec.loader.exec_module(CM)
FORMAL = ['S0', 'S1_EARLIEST', 'S3', 'S2_final', 'S3_mS2']
NAMES = {'p600 0': 'Helios', 'p610 2': 'Abilene', 'p630 2': 'Red Oak', 'p630 4': 'Shackelford', 'p630 5': 'Temple',
         'p630 6': 'Midlothian', 'p630 9': 'Denton', 'p650 0': 'TX1/SAT14'}
BUS_MAP = HERE.parent / 'inputs/dc/MAINLINE_NEW_RESEARCH_BUS_POI_MAP_GEO_DYNAMIC_V1.csv'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else 'MISSING'


def bus_names(man):
    """display names: legacy Epoch names, then the AIDC geospatial bus map (PNNL candidate buses are labelled as candidate
    research buses, never as a built campus), then the case SITES name; never NaN"""
    nm = dict(NAMES)
    if BUS_MAP.exists():
        for r in pd.read_csv(BUS_MAP).itertuples():
            nm.setdefault(r.bus, r.display_name)
    for b, s in ((man or {}).get('sites') or {}).items():
        nm.setdefault(b, s.get('name') or b)
    return nm


def rd(C, nm):
    f = Path(C) / nm
    return pd.read_csv(f) if f.exists() and f.stat().st_size > 2 else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('case')
    a = ap.parse_args()
    C = Path(a.case)
    man = json.loads((C / 'case_manifest.json').read_text())
    sel = man.get('s2_selection') or {}
    it = sel.get('selected_iteration')
    poil, led, summ = rd(C, 'poi_ledger.csv'), rd(C, 'ledger.csv'), rd(C, 'scenario_summary.csv')
    dev = rd(C, 'S2_developer_modes.csv')
    out = []

    def w(df, nm):
        df.to_csv(C / nm, index=False); out.append(nm)
    # ------------------------------------------------------------------ M1
    keep = ['site', 'year', 'requested_IT_MW', 'served_IT_MW', 'grid_import_MWh', 'BYOP_gen_MWh', 'BYOP_capacity_MW', 'certified_import_MW', 'mode_label']
    m1 = []
    for sc in ['S1_EARLIEST', 'S2_final', 'S3', 'S3_mS2']:
        x = poil[poil.scenario == sc][[c for c in keep if c in poil]].copy()
        x.insert(0, 'scenario', sc)
        m1.append(x)
    m1 = pd.concat(m1, ignore_index=True)
    nmap = bus_names(man)
    m1['name'] = m1.site.map(lambda b: nmap.get(b, b))
    m1['delay_IT_MW'] = m1.requested_IT_MW - m1.served_IT_MW
    s1 = m1[m1.scenario == 'S1_EARLIEST'].set_index(['site', 'year']).served_IT_MW
    m1['served_minus_S1_IT_MW'] = m1.served_IT_MW - m1.set_index(['site', 'year']).index.map(s1).values
    m1['method_flag'] = np.where(m1.year == min(m1.year), 'ERM_2026_METHOD_FLAG (first-year zero ERM headroom)', '')
    if len(dev) and it is not None:
        d_ = dev[dev.iteration == it].set_index(['site', 'year'])
        for c in ('mode', 'K', 'right_firm_MW', 'right_cond_MW', 'offer_firm_MW'):
            if c in d_:
                m1.loc[m1.scenario == 'S2_final', f'S2_dev_{c}'] = m1[m1.scenario == 'S2_final'].set_index(['site', 'year']).index.map(d_[c]).values
    w(m1, 'STAGE_B3_M1_SPEED_DELIVERY_BY_SITE_YEAR.csv')
    # ------------------------------------------------------------------ M2 public expansion
    pub = led[(led.resource_path == 'public') & led.scenario.isin(FORMAL)].copy() if len(led) else pd.DataFrame()
    m2 = pub.groupby(['scenario', 'carrier', 'zone', 'year']).agg(in_operation_MW=('capacity_MW', 'sum'),
                                                                 resource_capex_PV_USD=('resource_capex_PV_USD', 'sum')).reset_index()
    add = pub[pub.build_period == pub.year].groupby(['scenario', 'carrier', 'zone', 'year']).capacity_MW.sum().rename('added_this_year_MW')
    m2 = m2.join(add, on=['scenario', 'carrier', 'zone', 'year']).fillna({'added_this_year_MW': 0.0})
    piv = m2.pivot_table(index=['carrier', 'zone', 'year'], columns='scenario', values='in_operation_MW', aggfunc='sum').fillna(0.0)
    for sc in FORMAL:
        if sc not in piv:
            piv[sc] = 0.0
    piv['S1_minus_S0_MW'] = piv['S1_EARLIEST'] - piv['S0']
    piv['S2_final_minus_S1_MW'] = piv['S2_final'] - piv['S1_EARLIEST']
    piv['S3_mS2_minus_S2_final_MW'] = piv['S3_mS2'] - piv['S2_final']
    piv['S3_minus_S2_final_MW'] = piv['S3'] - piv['S2_final']
    tot = piv.groupby(level=['carrier', 'year']).sum().reset_index().assign(zone='ALL_ERCOT')
    m2w = pd.concat([tot, piv.reset_index()], ignore_index=True)
    m2w['note'] = 'public endogenous assets only; B1 S0CAL (fixed, AC_s0cal) and BYOP excluded; MW in operation in the year'
    w(m2w, 'STAGE_B3_M2_PUBLIC_EXPANSION_BY_CARRIER_YEAR.csv')
    # ------------------------------------------------------------------ M2 asset commitments
    acl = rd(C, 'MAINLINE_ASSET_COMMITMENT_LEDGER.csv')
    if len(acl):
        acl = acl[acl.scenario.isin(FORMAL)]
        first = acl.sort_values('year').groupby(['scenario', 'asset_id']).first().reset_index()
        cols = [c for c in ['scenario', 'asset_id', 'carrier', 'asset_boundary', 'resource_path', 'zone', 'approval_year', 'build_period', 'COD', 'cod_basis',
                            'capacity_MW', 'social_annuity_USD_per_MW_yr', 'private_annuity_USD_per_MW_yr'] if c in first]
        w(first[cols], 'STAGE_B3_M2_ASSET_COMMITMENT_AND_COD.csv')
    # ------------------------------------------------------------------ M4 cost components
    s = summ[summ.scenario.isin(FORMAL)].set_index('scenario')
    cb = CM.cost_book_decomposition(s)
    ms = rd(C, 'MAINLINE_MATCHED_SERVICE_COST.csv')
    if {'S2_final', 'S3_mS2'} <= set(cb.scenario):
        a2, a3 = cb.set_index('scenario').loc['S2_final'], cb.set_index('scenario').loc['S3_mS2']
        num = [c for c in cb.columns if c.endswith('_USD') or c.endswith('_USD_not_added') or c.endswith('_in_operating')]
        diff = {c: float(a2[c]) - float(a3[c]) for c in num}
        diff.update(scenario='S2_final_minus_S3_mS2',
                    matched_service_valid=bool(ms.matched_service_valid.iloc[0]) if len(ms) and 'matched_service_valid' in ms else None,
                    matched_service_max_abs_gap_IT_MW=float(ms.matched_service_max_abs_gap_IT_MW.iloc[0]) if len(ms) and 'matched_service_max_abs_gap_IT_MW' in ms else None,
                    label_note='M4 efficiency gap on the identical served trajectory; VOLL (existing-customer loss) kept apart from physical spending')
        cb = pd.concat([cb, pd.DataFrame([diff])], ignore_index=True)
    w(cb, 'STAGE_B3_M4_COST_COMPONENTS.csv')
    # ------------------------------------------------------------------ checks + audit
    g = rd(C, 'MAINLINE_GATE_CHECKS.csv')
    w(g, 'STAGE_B3_CHECKS_AND_METHOD_FLAGS.csv')
    gd = dict(zip(g.check, g.result)) if len(g) else {}
    lex = json.loads((C / 'lex_S1_EARLIEST.json').read_text()) if (C / 'lex_S1_EARLIEST.json').exists() else {}
    cons = rd(C, 'S2_consistency.csv')
    aud = dict(stage='B3-E pilot_core_b3e', case=man.get('case_id'), approved_git_sha=(man.get('mainline') or {}).get('gate', {}).get('approved_git_sha'),
               execution_git_head=(man.get('mainline') or {}).get('gate', {}).get('head'), status=man.get('status'),
               solves={k: {kk: v.get(kk) for kk in ['termination', 'seconds', 'n_vars', 'n_cons', 'integer_vars', 'objective', 'lex_audit_all_satisfied']}
                       for k, v in (man.get('solves') or {}).items() if isinstance(v, dict)},
               s2_selection=sel, s2_iterations=sorted(cons.iteration.unique().tolist()) if len(cons) else [],
               lex=dict(status=lex.get('status_name'), seconds=lex.get('seconds'), violations=lex.get('violations')),
               inputs=dict(baseline_nc=man.get('baseline_sha256'), s0_calibration=man.get('s0_calibration'), erm=(man.get('mainline') or {}).get('voll')),
               gates={k: gd.get(k) for k in ['TECHNICAL_GATE', 'EXPLORATORY_USE', 'FINAL_SCIENTIFIC_USE', 'METHOD_FLAGS', 'SCIENTIFIC_USE', 'phase',
                                             'matched_service_valid', 'matched_service_max_abs_gap_IT_MW', 's2_converged', 'cost_book_identities']},
               delay_MW_IT_year={sc: float(m1[m1.scenario == sc].delay_IT_MW.clip(lower=0).sum()) for sc in m1.scenario.unique()},
               written=out, B4_EXECUTIONS=0)
    (C / 'STAGE_B3_EXPLORATORY_AUDIT.json').write_text(json.dumps(aud, indent=1, default=str))
    print(json.dumps(dict(written=out + ['STAGE_B3_EXPLORATORY_AUDIT.json'], delay=aud['delay_MW_IT_year'], gates=aud['gates']), indent=1, default=str))


if __name__ == '__main__':
    main()
