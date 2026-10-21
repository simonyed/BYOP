#!/usr/bin/env python3
"""Mainline v1.3 E3 result tables and the three mechanism figures from one solved mainline case directory
(written by rearch_mech.py --mainline; called at the end of the run, or by hand):
    python byop/post/collect_mainline.py results/BYOP/mainline/<case>

MAINLINE_SCENARIO_SUMMARY.csv        scenario_summary.csv (social / private books, service, LP status)
MAINLINE_BUS_DELIVERY_AND_DELAY.csv  bus x year x scenario: request, delivered IT, B10 bridge fields, B8 delay layers
                                     (poi_limit_MW, upstream_limit_or_binding, resource_adequacy_binding,
                                     procedure_ready_year, earliest_grid_COD); attribution runs S1E_x* when present
MAINLINE_S2_MODES_TECH.csv           S2 joint developer: ex-post mode label, firm / conditional rights, technology x COD
MAINLINE_PUBLIC_INVESTMENT_DELTA.csv public new MW by carrier x year, S1/S2/S3 minus S0
MAINLINE_ASSET_COMMITMENT_LEDGER.csv every built asset: approval year, build period, COD, MW, social / private annuity
MAINLINE_MATCHED_SERVICE_COST.csv    S2_final vs S3_mS2 (same service, strict 48-key check) social real resource cost
Stage B B0: every formal table uses S2_final = the selected (last) S2 iteration; raw S2 / S2_itN rows go to
MAINLINE_DIAGNOSTIC_* only and are never summed; a missing required check is not a pass (SCIENTIFIC_USE BLOCKED);
a run with only S0 / S1_EARLIEST is PARTIAL_PILOT.
MAINLINE_GATE_CHECKS.csv             case_manifest checks (LP-only, optimal, no-harm, energy balance, S2 consistency)
MAINLINE_CASE_MANIFEST.json          the case manifest plus the produced file list
Status words: a field the solved tables cannot give stays NaN with a status column, never a guessed number.
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd


RAW_S2 = r'^S2(_it\d+)?$'                  # raw S2 iterations: diagnostic only (Stage B B0)
FORMAL = ['S0', 'S1_EARLIEST', 'S3', 'S2_final', 'S3_mS2']
CORE = set(FORMAL)
PILOT_S01 = {'S0', 'S1_EARLIEST'}
N_KEYS = 48                                # 8 Epoch buses x 2026-2031


def _r(out, nm):
    f = out / nm
    return pd.read_csv(f) if f.exists() and f.stat().st_size > 2 else pd.DataFrame()


def _formal(df):
    """drop raw S2 iteration rows (S2, S2_it2, ...): formal tables carry only S2_final"""
    if not len(df) or 'scenario' not in df:
        return df
    return df[~df.scenario.astype(str).str.match(RAW_S2)]


def matched_service_check(poil, n_keys=N_KEYS, tol=0.5):
    """M4 validity of S2_final vs S3_mS2: identical bus x year key sets, each key unique, n_keys keys on both sides,
    no missing / non-numeric value, max |gap| <= tol MW IT. Valid only when every item holds."""
    out = dict(matched_service_48_keys_present=False, matched_service_keys_unique=False, matched_service_no_missing=False,
               matched_service_max_abs_gap_IT_MW=float('nan'), matched_service_valid=False)
    if not len(poil):
        return out
    a = poil[poil.scenario == 'S2_final'][['site', 'year', 'served_IT_MW']]
    b = poil[poil.scenario == 'S3_mS2'][['site', 'year', 'served_IT_MW']]
    ka, kb = list(zip(a.site, a.year)), list(zip(b.site, b.year))
    out['matched_service_keys_unique'] = len(ka) == len(set(ka)) and len(kb) == len(set(kb))
    out['matched_service_48_keys_present'] = len(set(ka)) == n_keys and set(ka) == set(kb)
    va = pd.to_numeric(a.served_IT_MW, errors='coerce')
    vb = pd.to_numeric(b.served_IT_MW, errors='coerce')
    out['matched_service_no_missing'] = bool(len(a) and len(b) and va.notna().all() and vb.notna().all())
    if out['matched_service_keys_unique'] and out['matched_service_48_keys_present'] and out['matched_service_no_missing']:
        g = (a.assign(v=va.values).set_index(['site', 'year']).v - b.assign(v=vb.values).set_index(['site', 'year']).v).abs()
        out['matched_service_max_abs_gap_IT_MW'] = float(g.max())
        out['matched_service_valid'] = bool(g.max() <= tol)
    return out


def _isok(v):
    return isinstance(v, (bool, np.bool_)) and bool(v)


def collect(out):
    out = Path(out)
    summ_all, poil_all, dev_all, led_all = _r(out, 'scenario_summary.csv'), _r(out, 'poi_ledger.csv'), _r(out, 'S2_developer_modes.csv'), _r(out, 'ledger.csv')
    duals = _formal(_r(out, 'duals.csv'))
    man = json.loads((out / 'case_manifest.json').read_text()) if (out / 'case_manifest.json').exists() else {}
    sel = man.get('s2_selection') or {}
    it = sel.get('selected_iteration')
    summ, poil, led = _formal(summ_all), _formal(poil_all), _formal(led_all)
    dev = dev_all[dev_all.iteration == it] if (len(dev_all) and it is not None and 'iteration' in dev_all) else dev_all.iloc[0:0]
    files = []

    def w(df, nm):
        df = df.copy()
        df['S2_selected_iteration'] = it
        df.to_csv(out / nm, index=False)
        files.append(nm)
    present = set(summ.scenario) if len(summ) else set()
    phase = 'CORE' if CORE <= present else ('PARTIAL_PILOT' if PILOT_S01 <= present else 'INCOMPLETE')
    w(summ, 'MAINLINE_SCENARIO_SUMMARY.csv')
    diag = summ_all[summ_all.scenario.astype(str).str.match(RAW_S2)] if len(summ_all) else summ_all
    if len(diag):
        w(diag, 'MAINLINE_DIAGNOSTIC_S2_ITERATIONS.csv')
    if len(dev_all):
        w(dev_all, 'MAINLINE_DIAGNOSTIC_S2_DEVELOPER_ALL_ITERATIONS.csv')
    # ---- delivery and delay layers (B8 / B10)
    if len(poil):
        d = poil.copy()
        d['poi_limit_MW'] = d.equipment_total_MW
        d['poi_binding'] = (d.total_import_peak_MW >= 0.999 * d.equipment_total_MW - 1e-2) & (d.unserved_IT_MW > 1e-3)
        erm = duals[duals.constraint.astype(str).str.startswith('ERM')] if len(duals) else pd.DataFrame()
        if len(erm):
            eb = erm.groupby(['scenario', 'year']).binding.any().rename('resource_adequacy_binding')
            d = d.join(eb, on=['scenario', 'year'])
        else:
            d['resource_adequacy_binding'] = np.nan
        base = d[d.scenario == 'S1_EARLIEST'].set_index(['site', 'year']).served_IT_MW
        for tag, col in (('S1E_xUP', 'upstream_limit_or_binding'), ('S1E_xPOI', 'poi_relax_gain_IT_MW'),
                         ('S1E_xRA', 'adequacy_relax_gain_IT_MW'), ('S1E_xPROC', 'procedure_relax_gain_IT_MW'), ('S1E_xALL', 'all_relax_gain_IT_MW')):
            x = d[d.scenario == tag].set_index(['site', 'year']).served_IT_MW
            gain = (x - base).rename(col) if len(x) and len(base) else None
            if gain is not None:
                d = d.join(gain, on=['site', 'year'])
            else:
                d[col] = np.nan
        if 'upstream_limit_or_binding' in d:
            d['upstream_limit_or_binding'] = np.where(d.upstream_limit_or_binding.isna(), 'PENDING_ATTRIBUTION_RUN',
                                                      np.where(d.upstream_limit_or_binding > 1e-3, 'BINDING', 'NOT_BINDING'))
        d['delivered_IT_MW'] = d.served_IT_MW
        d['delay_IT_MW'] = d.requested_IT_MW - d.served_IT_MW
        d['delay_attribution_rule'] = 'layers reported separately (no additive split); binding from dual / single-factor relaxation'
        w(d, 'MAINLINE_BUS_DELIVERY_AND_DELAY.csv')
    if len(dev):
        w(dev, 'MAINLINE_S2_MODES_TECH.csv')
    # ---- public investment delta (formal scenarios only: no raw S2 iteration is summed)
    if len(led):
        pub = led[(led.resource_path == 'public')]
        t = pub.groupby(['scenario', 'carrier', 'year']).capacity_MW.sum().unstack('scenario').fillna(0.0)
        if 'S0' in t:
            for c in [c for c in t.columns if c != 'S0']:
                t[f'{c}_minus_S0'] = t[c] - t['S0']
        if {'S2_final', 'S1_EARLIEST'} <= set(t.columns):
            t['S2_final_minus_S1_EARLIEST'] = t['S2_final'] - t['S1_EARLIEST']
        w(t.reset_index(), 'MAINLINE_PUBLIC_INVESTMENT_DELTA.csv')
        cols = [c for c in ['scenario', 'asset_id', 'component', 'carrier', 'asset_boundary', 'resource_path', 'zone', 'commit_year',
                            'build_period', 'year', 'capacity_MW', 'social_annuity_USD_per_MW_yr', 'private_annuity_USD_per_MW_yr',
                            'resource_capex_PV_USD', 'private_capex_PV_USD', 'dispatch_MWh_per_yr'] if c in led]
        a = led[cols].rename(columns={'commit_year': 'approval_year'})
        # direct CO2 from the same fuel burn as the cost (EPA 53.06 kg/MMBtu_HHV; v1.3 D2: no separately fixed t/MWh)
        inp = Path(__file__).resolve().parents[1] / 'inputs/tech'
        v13 = pd.read_csv(inp / 'MAINLINE_V13_TECH_DEFAULTS.csv').set_index('technology').heat_rate_BtuHHV_per_kWh_e
        t1 = pd.read_csv(inp / 'TECH-01_technologies_DRAFT.csv')
        hr = {'byop_RICE': v13['RICE_50DF'], 'byop_SOFC_NG': v13['SOFC_NG_STANDARD'], 'byop_OCGT_aero': v13['OCGT_AERO']}
        hr.update({c: float(t1[(t1.carrier == c) & (t1.boundary == 'UTILITY')].heat_rate_Btu_kWh.iloc[0]) for c in ('CCGT', 'OCGT')})
        if 'dispatch_MWh_per_yr' in a:
            a['direct_CO2_t_per_yr'] = a.carrier.map(hr) / 1e6 * 53.06 * a.dispatch_MWh_per_yr.fillna(0.0)
        cod = _r(out, 'byop_cod.csv')
        if len(cod) and 'byop_name' in cod:
            a = a.merge(cod[['byop_name', 'cod']].drop_duplicates('byop_name').rename(columns={'byop_name': 'asset_id', 'cod': 'COD'}),
                        on='asset_id', how='left')
        if 'COD' not in a:
            a['COD'] = np.nan
        # audit P1-6: public candidates are indexed by their COD period (approval = COD - lead, static perfect foresight)
        a['cod_basis'] = np.where(a.COD.notna(), 'approval cohort (BYOP / POI upgrade): COD = approval year + lead',
                                  'public candidate: COD = build period; approval_year = build period - lead (static plan, not an annual commitment)')
        a['COD'] = a.COD.fillna(a.build_period)
        w(a, 'MAINLINE_ASSET_COMMITMENT_LEDGER.csv')
    # ---- M4 matched service: S2_final vs S3_mS2, strict 48-key check
    mchk = matched_service_check(poil) if phase == 'CORE' else {}
    if {'S2_final', 'S3_mS2'} <= present:
        s = summ.set_index('scenario')
        valid = mchk.get('matched_service_valid') is True
        w(pd.DataFrame([dict(compare='S2_final vs S3_mS2 (same service trajectory)', **mchk,
                             S2_final_social_real_USD=s.social_real_resource_cost_USD['S2_final'],
                             S3_mS2_social_real_USD=s.social_real_resource_cost_USD['S3_mS2'],
                             gap_USD=s.social_real_resource_cost_USD['S2_final'] - s.social_real_resource_cost_USD['S3_mS2'],
                             gap_status='VALID' if valid else 'INVALID_DIAGNOSTIC_ONLY',
                             rule='private payments to the grid are transfers: not added to the social real resource cost')]),
          'MAINLINE_MATCHED_SERVICE_COST.csv')
    chk = dict(man.get('checks') or {})
    chk.update(mchk)
    chk['selected_S2_iteration'] = it
    chk['s2_converged'] = sel.get('converged') if sel else None
    cons = _r(out, 'S2_consistency.csv')
    if len(cons) and it is not None:     # audit P0-4: the selected S2 iteration delivers the developer plan
        last = cons[cons.iteration == it]
        chk['s2_public_delivers_developer_plan'] = bool(len(last) and (last.gap_IT_MW <= np.maximum(0.5, 1e-3 * last.planned_IT_MW)).all())
    # Stage B B0: a required check that is missing (None / NaN) is NOT a pass
    required = ['true_LP', 'all_optimal', 'no_harm_existing_customers', 'served_le_requested', 'online_IT_monotone']
    if phase == 'CORE':
        required += ['s2_converged', 's2_public_delivers_developer_plan', 'matched_service_valid', 'dc_energy_balance']
    failed = [k for k in required if not _isok(chk.get(k))]
    failed += [k for k, v in chk.items() if k not in required and isinstance(v, (bool, np.bool_)) and not bool(v)]
    chk['phase'] = phase
    if phase == 'INCOMPLETE':
        chk['SCIENTIFIC_USE'] = 'BLOCKED: incomplete scenario set'
    elif failed:
        chk['SCIENTIFIC_USE'] = 'BLOCKED: ' + ', '.join(sorted(set(failed)))
    else:
        chk['SCIENTIFIC_USE'] = 'ALLOWED' if phase == 'CORE' else 'PARTIAL_PILOT (S0 / S1 only: no M2 / M4 conclusion)'
    w(pd.DataFrame([dict(check=k, result=v) for k, v in chk.items()]), 'MAINLINE_GATE_CHECKS.csv')
    try:
        figures(out, poil, dev, led, files)
    except Exception as e:     # figures never block the tables
        files.append(f'FIGURES_FAILED: {e}')
    (out / 'MAINLINE_CASE_MANIFEST.json').write_text(json.dumps(dict(manifest=man, phase=phase, s2_selection=sel,
                                                                   scientific_use=chk['SCIENTIFIC_USE'], checks=chk,
                                                                   produced=files), indent=1, default=str))
    return files


def figures(out, poil, dev, led, files):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if len(poil):
        sites = sorted(poil.site.unique())
        fig, axs = plt.subplots(2, 4, figsize=(16, 7), sharex=True)
        for ax, s in zip(axs.ravel(), sites):
            x = poil[poil.site == s]
            for sc, st in (('S1_EARLIEST', '--'), ('S2_final', '-'), ('S3', ':')):
                y = x[x.scenario == sc].sort_values('year')
                if len(y):
                    ax.plot(y.year, y.served_IT_MW, st, label=sc)
            r = x[x.scenario == x.scenario.iloc[0]].sort_values('year')
            ax.plot(r.year, r.requested_IT_MW, 'k-', lw=0.8, label='request')
            ax.set_title(s, fontsize=9)
        axs[0, 0].legend(fontsize=7)
        fig.suptitle('Speed-to-power: requested vs delivered IT MW (grid-only S1, developer S2, coordinated S3)')
        fig.savefig(out / 'speed_to_power_delivery.png', dpi=130); plt.close(fig); files.append('speed_to_power_delivery.png')
    if len(dev):
        k = dev.groupby(['site', 'year', 'mode']).BYOP_capacity_MW.sum().reset_index()
        fig, ax = plt.subplots(figsize=(12, 5))
        for i, s in enumerate(sorted(k.site.unique())):
            y = k[k.site == s]
            ax.scatter(y.year + i * 0.08, [i] * len(y), s=10 + y.BYOP_capacity_MW / 5, label=s)
            for r in y.itertuples():
                ax.annotate(r.mode, (r.year + i * 0.08, i), fontsize=6)
        ax.set_yticks(range(k.site.nunique())); ax.set_yticklabels(sorted(k.site.unique()))
        ax.set_title('S2 joint developer: ex-post supply mode and own capacity (marker size = BYOP MW)')
        fig.savefig(out / 'byop_modes_technology_stack.png', dpi=130); plt.close(fig); files.append('byop_modes_technology_stack.png')
    if len(led):
        pub = led[led.resource_path == 'public'].groupby(['scenario', 'year']).capacity_MW.sum().unstack('scenario')
        fig, ax = plt.subplots(figsize=(9, 5))
        pub.plot(ax=ax, marker='o')
        ax.set_ylabel('public new MW in operation'); ax.set_title('Public investment feedback across S0-S3')
        fig.savefig(out / 'public_grid_investment_feedback.png', dpi=130); plt.close(fig); files.append('public_grid_investment_feedback.png')


if __name__ == '__main__':
    print(collect(sys.argv[1]))
