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
MAINLINE_MATCHED_SERVICE_COST.csv    S2_final vs S3_mS2 (same service, strict expected-key check) social real resource cost
                                     expected keys = research buses x model years of the case's own input record (legacy: 8 x 6 = 48)
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
LEGACY_BUSES = ['p600 0', 'p610 2', 'p630 2', 'p630 4', 'p630 5', 'p630 6', 'p630 9', 'p650 0']   # epoch8_legacy research buses
LEGACY_YEARS = list(range(2026, 2032))
N_KEYS = len(LEGACY_BUSES) * len(LEGACY_YEARS)      # 48: legacy eight-bus compatibility only, never the generic pass rule


def _r(out, nm):
    f = out / nm
    return pd.read_csv(f) if f.exists() and f.stat().st_size > 2 else pd.DataFrame()


def _formal(df):
    """drop raw S2 iteration rows (S2, S2_it2, ...): formal tables carry only S2_final"""
    if not len(df) or 'scenario' not in df:
        return df
    return df[~df.scenario.astype(str).str.match(RAW_S2)]


def expected_service_keys(man):
    """AIDC geospatial v1: the EXPECTED M4 key set = research buses x model years taken from the case's model-input record
    (case_manifest mainline.research_buses / model_years, else the SITES table and cfg start..end), never from the S2 or
    S3_mS2 output (a bus missing on both sides must not pass). A manifest without either record = the legacy 8 x 2026-2031."""
    ml = (man or {}).get('mainline') or {}
    buses = ml.get('research_buses') or sorted((man or {}).get('sites') or {})
    basis = 'mainline.research_buses' if ml.get('research_buses') else ('case_manifest.sites' if buses else 'legacy eight Epoch buses')
    buses = buses or LEGACY_BUSES
    yrs = ml.get('model_years')
    if not yrs:
        cfg = (man or {}).get('cfg') or {}
        yrs = list(range(int(cfg['start']), int(cfg['end']) + 1)) if 'start' in cfg and 'end' in cfg else LEGACY_YEARS
    return {(str(b_), int(y_)) for b_ in buses for y_ in yrs}, basis


def matched_service_check(poil, expected=None, tol=0.5):
    """M4 validity of S2_final vs S3_mS2: each side's key set equals the EXPECTED set exactly (no missing, no extra key),
    each key unique, no missing / non-numeric value, max |gap| <= tol MW IT. Valid only when every item holds.
    expected = set of (bus, year) from expected_service_keys(case_manifest); None = legacy 8 x 2026-2031."""
    expected = set(expected) if expected is not None else {(b_, y_) for b_ in LEGACY_BUSES for y_ in LEGACY_YEARS}
    out = dict(matched_service_expected_keys_present=False, matched_service_expected_key_count=len(expected),
               matched_service_observed_key_count=0, matched_service_S3_mS2_observed_key_count=0,
               matched_service_48_keys_present=False if len(expected) == N_KEYS else None,
               matched_service_keys_unique=False, matched_service_no_missing=False,
               matched_service_max_abs_gap_IT_MW=float('nan'), matched_service_valid=False)
    if not len(poil):
        return out
    a = poil[poil.scenario == 'S2_final'][['site', 'year', 'served_IT_MW']]
    b = poil[poil.scenario == 'S3_mS2'][['site', 'year', 'served_IT_MW']]
    ka = [(str(s_), int(y_)) for s_, y_ in zip(a.site, a.year)]
    kb = [(str(s_), int(y_)) for s_, y_ in zip(b.site, b.year)]
    out['matched_service_observed_key_count'] = len(set(ka))
    out['matched_service_S3_mS2_observed_key_count'] = len(set(kb))
    out['matched_service_keys_unique'] = len(ka) == len(set(ka)) and len(kb) == len(set(kb))
    out['matched_service_expected_keys_present'] = set(ka) == expected and set(kb) == expected
    if len(expected) == N_KEYS:          # legacy eight-bus field kept for comparability (None for other geographies)
        out['matched_service_48_keys_present'] = out['matched_service_expected_keys_present']
    va = pd.to_numeric(a.served_IT_MW, errors='coerce')
    vb = pd.to_numeric(b.served_IT_MW, errors='coerce')
    out['matched_service_no_missing'] = bool(len(a) and len(b) and va.notna().all() and vb.notna().all())
    if out['matched_service_keys_unique'] and out['matched_service_expected_keys_present'] and out['matched_service_no_missing']:
        ia = pd.MultiIndex.from_tuples(ka, names=['site', 'year'])
        ib = pd.MultiIndex.from_tuples(kb, names=['site', 'year'])
        g = (pd.Series(va.values, index=ia) - pd.Series(vb.values, index=ib)).abs()
        out['matched_service_max_abs_gap_IT_MW'] = float(g.max())
        out['matched_service_valid'] = bool(g.max() <= tol)
    return out


def _isok(v):
    return isinstance(v, (bool, np.bool_)) and bool(v)


def cost_book_decomposition(summ):
    """Stage B2.5-C: split the summary books without changing their definitions. social_real_resource_cost_USD of the
    model = public capex (incl. POI upgrades) + BYOP capex + system operating (incl. BYOP fuel) + load_shed_PV (existing-
    customer unserved energy at VOLL), so it is NOT a pure physical spending figure. Rows per scenario with identity
    residuals; transfers (energy payments to the grid, tax credits) are listed and never added to social cost."""
    if not len(summ):
        return pd.DataFrame()
    g = lambda r, c: float(r[c]) if c in r and r[c] == r[c] else 0.0
    rows = []
    for sc, r in summ.iterrows():
        phys = g(r, 'social_real_resource_cost_USD') - g(r, 'load_shed_PV_USD')
        parts = g(r, 'public_resource_capex_PV_USD') + g(r, 'byop_resource_capex_PV_USD') + g(r, 'system_operating_PV_USD')
        rows.append(dict(
            scenario=sc, physical_resource_spending_proxy_PV_USD=phys, existing_customer_unserved_loss_PV_USD=g(r, 'load_shed_PV_USD'),
            social_welfare_cost_before_dc_delay_PV_USD=phys + g(r, 'load_shed_PV_USD'),
            public_resource_capex_PV_USD=g(r, 'public_resource_capex_PV_USD'), poi_upgrade_resource_capex_PV_USD=g(r, 'poi_upgrade_resource_capex_PV_USD'),
            byop_resource_capex_PV_USD=g(r, 'byop_resource_capex_PV_USD'), system_operating_PV_USD=g(r, 'system_operating_PV_USD'),
            byop_fuel_PV_USD_included_in_operating=g(r, 'byop_fuel_PV_USD'),
            social_delay_loss_PV_USD=g(r, 'social_delay_loss_PV_USD'), curtailment_loss_PV_USD=g(r, 'curtailment_loss_PV_USD'),
            interruption_loss_PV_USD=g(r, 'interruption_loss_PV_USD'), social_total_USD=g(r, 'social_total_USD'),
            transfer_energy_payment_PV_USD_not_added=g(r, 'transfer_energy_PV_social_USD'), tax_credit_PV_USD_not_added=g(r, 'tax_credit_PV_USD'),
            identity_physical_residual_USD=phys - parts,
            identity_total_residual_USD=g(r, 'social_total_USD') - (g(r, 'social_real_resource_cost_USD') + g(r, 'social_delay_loss_PV_USD')
                                                                  + g(r, 'curtailment_loss_PV_USD') + g(r, 'interruption_loss_PV_USD')
                                                                  + g(r, 'competing_queue_loss_PV_USD')),
            label_note='physical_resource_spending_proxy = social_real_resource_cost - load_shed_PV (existing ledger); not a true_resource_cost rename'))
    out = pd.DataFrame(rows)
    tol = 1e-6 * out.social_total_USD.abs().clip(lower=1.0) + 1.0
    out['identity_check'] = np.where((out.identity_physical_residual_USD.abs() <= tol) & (out.identity_total_residual_USD.abs() <= tol), 'PASS', 'FAIL')
    return out


TECH_REQUIRED = ['true_LP', 'all_optimal', 'no_harm_existing_customers', 'served_le_requested', 'online_IT_monotone',
                 'dc_energy_balance', 'poi_flow_le_equipment', 'no_service_before_grid_or_byop', 'lex_presolve_optimal']
TECH_REQUIRED_CORE = ['s2_converged', 's2_public_delivers_developer_plan', 'matched_service_valid']


def science_layers(chk, phase, flags):
    """Stage B2.5-D status layers (the legacy SCIENTIFIC_USE is kept unchanged next to them):
    TECHNICAL_GATE   all required physical / numerical checks of the phase are explicitly True (missing = FAIL)
    METHOD_FLAGS     method risks that do not invalidate the LP (ERM first-year headroom, S0 reliability, pending exports)
    EXPLORATORY_USE  PERMITTED_WITH_METHOD_FLAGS / PERMITTED when the technical gate passes, else BLOCKED
    FINAL_SCIENTIFIC_USE  PENDING_METHOD_VALIDATION while method flags are on; never ALLOWED automatically"""
    req = list(TECH_REQUIRED) + (list(TECH_REQUIRED_CORE) if phase == 'CORE' else [])
    miss = [k for k in req if not _isok(chk.get(k))]
    if phase == 'INCOMPLETE':
        miss.append('incomplete_scenario_set')
    tech = 'PASS' if not miss else 'FAIL: ' + ', '.join(miss)
    on = [k for k, v in flags.items() if v not in (None, False, 'OFF')]
    expl = 'BLOCKED' if miss else ('PERMITTED_WITH_METHOD_FLAGS' if on else 'PERMITTED')
    final = 'BLOCKED' if miss else ('PENDING_METHOD_VALIDATION' if on else 'PENDING_RESEARCHER_REVIEW')
    return dict(TECHNICAL_GATE=tech, METHOD_FLAGS=';'.join(f'{k}={flags[k]}' for k in flags), EXPLORATORY_USE=expl,
                FINAL_SCIENTIFIC_USE=final, SCIENTIFIC_USE_LEGACY_MAPPING='SCIENTIFIC_USE keeps the B0 rule (any False check -> BLOCKED)')


def _weights(index, stress_days):
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


def method_flags(out, man, duals, poil):
    """data-driven method flags: ERM binding in the first period with research service below request; S0 reliability
    screen (total > 1000 MWh, bus peak > 10 MW, inherited ramp > 1 MWh / yr); S0CAL line-flow export present or not"""
    fl = {}
    e = duals[duals.constraint.astype(str).str.startswith('ERM')] if len(duals) else pd.DataFrame()
    y0 = min(poil.year) if len(poil) else None
    first = e[(e.year == y0) & (e.binding == True)] if len(e) and y0 is not None else pd.DataFrame()
    s1 = poil[(poil.scenario == 'S1_EARLIEST') & (poil.year == y0)] if len(poil) else pd.DataFrame()
    short = float((s1.requested_IT_MW - s1.served_IT_MW).clip(lower=0).sum()) if len(s1) else 0.0
    fl['ERM_FIRST_YEAR_METHOD_FLAG'] = f'ON ({short:.2f} MW_IT {y0} short, ERM binding)' if len(first) and short > 0.5 else 'OFF'
    fz = out / 'S0_shed_by_snapshot_frozen.csv.gz'
    stress = ((man.get('mainline') or {}).get('stress') or {}).get('days') or []
    if fz.exists() and stress:
        f = pd.read_csv(fz, index_col=[0, 1], parse_dates=[1])
        en = f.mul(_weights(f.index, stress), axis=0).groupby(level=0).sum()
        inh = [c for c in en.columns if c.endswith(' inherited_ramp_unserved')]
        tot, peak = float(en.values.sum()), float(f.max().max())
        inh_y = float(en[inh].sum(axis=1).max()) if inh else 0.0
        on = tot > 1000.0 or peak > 10.0 or inh_y > 1.0
        fl['S0_RELIABILITY_REVIEW_REQUIRED'] = f'ON (total {tot:.1f} MWh, bus peak {peak:.1f} MW, inherited max {inh_y:.2f} MWh/yr)' if on else 'OFF'
    else:
        fl['S0_RELIABILITY_REVIEW_REQUIRED'] = 'NOT_EVALUATED (no frozen S0 shed or stress days)'
    fl['S0CAL_LINE_FLOWS'] = 'EXPORTED' if (out / 'STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv').exists() else 'PENDING_DIAGNOSTIC_EXPORT'
    return fl


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
    # ---- M4 matched service: S2_final vs S3_mS2, strict expected-key check (research buses x model years)
    exp_keys, exp_basis = expected_service_keys(man)
    mchk = matched_service_check(poil, exp_keys) if phase == 'CORE' else {}
    if mchk:
        mchk['matched_service_expected_key_basis'] = exp_basis
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
    # Stage B2.5: S0CAL flow export (written per scenario by rearch_mech), cost books, layered status
    fl_parts = [f for f in sorted(out.glob('scenarios/*/s0cal_line_flows.csv')) if f.stat().st_size > 2]   # post-v1.6: no S0CAL -> empty (newline-only) files
    if fl_parts:
        w(pd.concat([pd.read_csv(f) for f in fl_parts], ignore_index=True), 'STAGE_B3_S0CAL_LINE_FLOW_UTILISATION.csv')
    cb = cost_book_decomposition(summ)
    if len(cb):
        w(cb, 'MAINLINE_COST_BOOK_DECOMPOSITION.csv')
        chk['cost_book_identities'] = bool((cb.identity_check == 'PASS').all())
    for sc_, sv_ in (man.get('solves') or {}).items():
        if isinstance(sv_, dict) and 'lex_audit_all_satisfied' in sv_ and sc_ == 'S1_EARLIEST':
            chk['lex_audit_all_satisfied'] = sv_['lex_audit_all_satisfied']
    flags = method_flags(out, man, duals, poil)
    chk.update(science_layers(chk, phase, flags))
    w(pd.DataFrame([dict(check=k, result=v) for k, v in chk.items()]), 'MAINLINE_GATE_CHECKS.csv')
    try:
        figures(out, poil, dev, led, files)
    except Exception as e:     # figures never block the tables
        files.append(f'FIGURES_FAILED: {e}')
    (out / 'MAINLINE_CASE_MANIFEST.json').write_text(json.dumps(dict(manifest=man, phase=phase, s2_selection=sel,
                                                                   scientific_use=chk['SCIENTIFIC_USE'], checks=chk,
                                                                   technical_gate=chk.get('TECHNICAL_GATE'), exploratory_use=chk.get('EXPLORATORY_USE'),
                                                                   final_scientific_use=chk.get('FINAL_SCIENTIFIC_USE'), method_flags=chk.get('METHOD_FLAGS'),
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
