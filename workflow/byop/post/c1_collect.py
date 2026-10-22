#!/usr/bin/env python3
"""C1 fixed-asset diagnostics: comparison tables, figure and QA from the solved case folders (no solve). Called by
    python byop/run/c1_fixed_asset_diagnostics.py --collect
Outputs (results/BYOP/C1_FIXED_ASSET_DIAG/): C1_CASE_MANIFEST.csv, C1_METRICS.csv, C1_SHEDDING_EVENTS.csv, C1_BINDING_LINES.csv,
C1_LINE_COMPARISON.csv, C1_GENERATION_BY_FUEL.csv, C1_QA.json, C1_MAIN_RESULTS.png
Fuel comparison with the official 2025 Fuel Mix is a structure reference only: settlement GWh of the real 2025 system vs a
3 h dispatch of the static year-end model fleet with model costs - nothing is fitted to it.
"""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

OUT = BP.C1_RESULTS
OFFICIAL_MAP = {'CCGT': 'Gas-CC', 'OCGT': 'Gas', 'gas_steam': 'Gas', 'coal': 'Coal', 'nuclear': 'Nuclear', 'onwind': 'Wind', 'solar': 'Solar',
                'hydro': 'Hydro', 'biomass': 'Biomass', 'load_shed': '(diagnostic shed)'}
KL = {'annual': 'ANNUAL_3H', 'window': 'PEAK_WINDOW_1H'}             # runner labels -> the one result vocabulary
EXPECTED_KEYS = {(c, k) for c in ('C1_NETWORK_BASE', 'C1_NETWORK_CALIBRATED') for k in ('ANNUAL_3H', 'PEAK_WINDOW_1H')}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def is_optimal(status, termination):
    """exact: 'suboptimal' must not pass (a substring test on 'optimal' would accept it)"""
    return str(status) == 'ok' and str(termination) == 'optimal'


def validate(man, met, ev, bl, gen, cmp_, fuel, tol_MWh=0.5):
    """layered acceptance (pure function, unit-tested with counterexamples):
    solver_termination  every final case ok + exactly optimal
    data_integrity      manifest / metrics keys == the 4 expected keys (no missing, duplicate or extra); fuel and line
                        comparison tables non-empty for every key; events / binding tables consistent with the metrics
                        (a case may have no event only if its metric says zero)"""
    out, prob = {}, []
    keys = lambda df: [tuple(x) for x in df[['case', 'kind']].values] if len(df) else []
    for nm, df in (('manifest', man), ('metrics', met)):
        k = keys(df)
        if set(k) != EXPECTED_KEYS or len(k) != len(set(k)):
            prob.append(f'{nm} keys {sorted(k)} != expected 4 keys')
    out['solver_termination_pass'] = bool(len(man) == 4 and all(is_optimal(s_, t_) for s_, t_ in zip(man.status, man.termination)) and not
                                          [p for p in prob if p.startswith('manifest')])
    for nm, df in (('fuel', fuel), ('line_comparison', cmp_)):
        if not len(df):
            prob.append(f'{nm} empty')
    if len(fuel) and set(keys(fuel)) != EXPECTED_KEYS:
        prob.append(f'fuel keys {sorted(set(keys(fuel)))}')
    if len(fuel) and fuel.model_GWh.isna().any():
        prob.append('fuel model_GWh missing')
    if len(cmp_):
        for c_ in ('C1_NETWORK_BASE', 'C1_NETWORK_CALIBRATED'):
            for col in (f'binding_hours_{c_}', f's_nom_MVA_{c_}', f'max_loading_{c_}'):
                if col not in cmp_ or cmp_[col].isna().any():
                    prob.append(f'line comparison {col} missing / NaN')
        if set(cmp_.kind) != {'ANNUAL_3H', 'PEAK_WINDOW_1H'}:
            prob.append(f'line comparison kinds {sorted(set(cmp_.kind))}')
    if len(met):
        for r in met.itertuples():
            e = ev[(ev.case == r.case) & (ev.kind == r.kind)] if len(ev) else ev
            esum = float(e.energy_MWh.sum()) if len(e) else 0.0
            if abs(esum - r.shed_MWh) > max(tol_MWh, 1e-6 * r.shed_MWh):
                prob.append(f'events {r.case} {r.kind}: {esum} vs metric {r.shed_MWh}')
            b = bl[(bl.case == r.case) & (bl.kind == r.kind)] if len(bl) else bl
            if not len(b):
                prob.append(f'lines table missing {r.case} {r.kind}')
            elif int((b.binding_hours > 0).sum()) != int(r.binding_lines):
                prob.append(f'binding lines {r.case} {r.kind}: {int((b.binding_hours > 0).sum())} vs metric {r.binding_lines}')
    out['data_integrity_pass'] = not prob
    out['problems'] = prob
    return out


def collect(c):
    dirs = sorted(p for p in OUT.glob('C1_NETWORK_*__*') if (p / 'metrics.json').exists() and '__attempt' not in p.name)
    earlier = sorted(p for p in OUT.glob('C1_NETWORK_*__*__attempt*') if (p / 'metrics.json').exists())
    M, EV, BL, GEN, MAN = [], [], [], [], []
    log = pd.read_csv(OUT / 'C1_SOLVE_LOG.csv')
    for d in dirs:
        m = json.loads((d / 'metrics.json').read_text())
        raw_kind = m['kind']
        m['kind'] = KL.get(raw_kind, raw_kind)
        assert m['kind'] == d.name.split('__')[1], (d.name, m['kind'])
        lg = log[(log.case == m['case']) & (log.kind == raw_kind)]
        MAN.append(dict(case=m['case'], kind=m['kind'], network=m['network']['network'], network_sha256=m['network']['network_sha256'],
                        config_sha256=m['config_sha256'], script_sha256=m['script_sha256'], status=m['status'], termination=m['termination'],
                        seconds=m['seconds'], threads=m['threads'], n_vars=m['n_vars'], n_cons=m['n_cons'],
                        diagnostic_solves=int((lg.counted_as == 'diagnostic').sum()), retries=int((lg.counted_as == 'retry').sum()),
                        retry_reasons='; '.join(lg[lg.counted_as == 'retry'].reason.astype(str)), snapshots=m['snapshots'],
                        evaluated_snapshots=m['evaluated_snapshots'], weight_h=m['weight_h'],
                        build_variables=','.join(v for v in m['linopy_variables'] if v.endswith('_nom')) or 'none',
                        window=json.dumps({k: v for k, v in (m.get('window') or {}).items() if k in ('peak_label', 'start_h', 'end_h', 'buffer_h', 'renewables', 'soc_boundary')}),
                        label=m['label']))
        M.append({k: v for k, v in m.items() if not isinstance(v, (dict, list))})
        for nm, L in (('shedding_events.csv', EV), ('lines.csv', BL), ('generation_by_carrier.csv', GEN)):
            f = d / nm
            if f.exists() and f.stat().st_size > 2:
                x = pd.read_csv(f)
                if len(x):
                    x['kind'] = x['kind'].replace(KL)
                    L.append(x)
    att = []
    for d in earlier:                                       # superseded attempts: kept, listed, never used in the comparison
        m = json.loads((d / 'metrics.json').read_text())
        att.append(dict(attempt_dir=d.name, case=m['case'], kind=d.name.split('__')[1], status=m['status'], termination=m['termination'],
                        seconds=m['seconds'], shed_MWh=m['shed_MWh'], shed_max_MW=m['shed_max_MW'], balance_residual_max_abs_MW=m['balance_residual_max_abs_MW'],
                        solver_options=json.dumps(m.get('solver_options', {})), note='superseded attempt (not optimal or upstream boundary changed)'))
    man, met = pd.DataFrame(MAN), pd.DataFrame(M)
    pd.DataFrame(att).to_csv(OUT / 'C1_SUPERSEDED_ATTEMPTS.csv', index=False, lineterminator=chr(10), float_format='%.6f')
    ev = pd.concat(EV, ignore_index=True) if EV else pd.DataFrame(columns=['case', 'kind', 'bus', 'start', 'end', 'duration_h', 'energy_MWh', 'peak_MW'])
    bl = pd.concat(BL, ignore_index=True)
    gen = pd.concat(GEN, ignore_index=True)
    w = lambda df, nm: df.to_csv(OUT / nm, index=False, lineterminator='\n', float_format='%.6f')
    w(man, 'C1_CASE_MANIFEST.csv'); w(met, 'C1_METRICS.csv'); w(ev, 'C1_SHEDDING_EVENTS.csv')
    w(bl[(bl.binding_hours > 0) | (bl.max_loading >= 0.95)].sort_values(['kind', 'case', 'binding_hours'], ascending=[True, True, False]), 'C1_BINDING_LINES.csv')
    cmp_ = bl.pivot_table(index=['kind', 'line', 'bus0', 'bus1'], columns='case', values=['binding_hours', 'max_loading', 's_nom_MVA']).reset_index()
    cmp_.columns = ['_'.join(x for x in col if x) if isinstance(col, tuple) else col for col in cmp_.columns]
    led = pd.read_csv(WF / c['uplift_ledger']).set_index('line')
    cmp_['uplift_line'] = cmp_.line.isin(led.index)
    w(cmp_, 'C1_LINE_COMPARISON.csv')
    off = pd.read_csv(BP.ANCHOR2025_DERIVED / 'FUEL_MIX_2025_GWH.csv')
    off = off[off.period == 'annual'].set_index('fuel').GWh
    gen['official_category'] = gen.carrier.map(OFFICIAL_MAP).fillna('Other/unmapped')
    g = gen.groupby(['kind', 'case', 'official_category']).MWh.sum().div(1e3).rename('model_GWh').reset_index()
    g['official_2025_GWh'] = np.where(g.kind.str.contains('ANNUAL'), g.official_category.map(off), np.nan)
    g['basis'] = 'official = 2025 settlement Fuel Mix (real system, incl. WSL / Other); model = 3 h dispatch of the static year-end fleet; reference only, not fitted'
    w(g, 'C1_GENERATION_BY_FUEL.csv')
    dry = json.loads((OUT / 'C1_DRY_CHECK.json').read_text()) if (OUT / 'C1_DRY_CHECK.json').exists() else {}
    gates = {p.name: ('NOT_APPROVED' in p.read_text(encoding='utf-8')) for p in (WF / 'config').glob('config.byop_ercot_mainline*.yaml')}
    ch = subprocess.run(['git', '-C', str(WF.parent), 'diff', '--name-only', 'd2cf7d1c', 'HEAD', '--', 'workflow/byop/inputs/dc', 'workflow/byop/inputs/poi',
                         'workflow/byop/inputs/grid', 'workflow/byop/inputs/tech', 'workflow/results/BYOP/baseline_2025_tamu'], capture_output=True, text=True).stdout.split()
    qa = dict(stage='C1 fixed-asset diagnostics (prompt v1.4)', cases=man[['case', 'kind', 'status', 'termination']].to_dict('records'),
              acceptance=validate(man, met, ev, bl, gen, cmp_, g),
              physical_interpretation_limits=[
                  'static year-end fleet, not a 2025 historical replay (no in-year commissioning / outage dates)',
                  'peak window = hourly load + renewables held at their 3 h value (not a full 1 h stress test); max-net-load window MISSING_INPUT',
                  'cause of CALIBRATED annual shed vs the 102.2 MWh calibration residual not isolated (see report)',
                  'large simultaneous storage charge / discharge in the LP solution: degeneracy / energy-sink mechanism not isolated',
                  'dispatch diagnostic only: no firm-right, POI, N-1 or probabilistic adequacy statement'],
              diagnostic_solves=int((log.counted_as == 'diagnostic').sum()), retries=int((log.counted_as == 'retry').sum()),
              solve_budget=int(c['max_diagnostic_solves']), no_build_variables=bool((man.build_variables == 'none').all()),
              balance_residual_max_abs_MW=float(met.balance_residual_max_abs_MW.max()),
              storage_simultaneous_charge_discharge_MWh={f'{r.case}|{r.kind}': r.storage_simultaneous_MWh for r in met.itertuples()},
              network_difference=dry.get('network_difference'), uplift_loaded_once=bool((dry.get('network_difference') or {}).get('equals_ledger')),
              ac_s0cal_links=0, max_net_load_window=c['windows']['max_net_load']['status'],
              missing_inputs=['time-aligned 1 h wind / solar for the model profiles (max-net-load window not run; peak window holds RE at its 3 h value)',
                              'unit-level 2025 in-service / outage dates (no in-year commissioning replay; static year-end fleet)',
                              'hydro inflow profile (hydro p_max_pu = 1 static)'],
              formal_gates_NOT_APPROVED=gates, historical_or_future_inputs_changed_since_d2cf7d1c=ch,
              outputs={p.name: sha(p) for p in sorted(OUT.glob('C1_*.csv'))})
    qa['solver_termination_pass'] = qa['acceptance']['solver_termination_pass']
    qa['data_integrity_pass'] = qa['acceptance']['data_integrity_pass']
    qa['shed_by_case'] = {f'{r.case}|{r.kind}': dict(shed_MWh=r.shed_MWh, shed_max_MW=r.shed_max_MW, shed_hours=r.shed_hours, shed_buses=r.shed_buses,
                                                        longest_shed_event_h=r.longest_shed_event_h) for r in met.itertuples()}
    (OUT / 'C1_QA.json').write_text(json.dumps(qa, indent=1, default=str))
    try:
        figure(met, cmp_)
    except Exception as e:                                       # the figure is optional; record why it is missing
        qa['figure_error'] = repr(e)
        (OUT / 'C1_QA.json').write_text(json.dumps(qa, indent=1, default=str))
    print(json.dumps({k: v for k, v in qa.items() if k != 'outputs'}, indent=1, default=str))


def figure(met, cmp_):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
    t = met.assign(lbl=met.case.str.replace('C1_NETWORK_', '') + '\n' + met.kind.str.replace('_', ' '))
    ax[0].bar(t.lbl, t.shed_MWh, color=['#888' if 'BASE' in x else '#2a6' for x in t.case])
    ax[0].set_ylabel('diagnostic load shed (MWh, evaluated period)'); ax[0].set_title('Fixed-asset shed by case')
    a = cmp_[cmp_.kind.str.contains('ANNUAL')].copy()
    a = a.sort_values('binding_hours_C1_NETWORK_BASE', ascending=False).head(15)
    x = np.arange(len(a))
    ax[1].bar(x - 0.2, a.binding_hours_C1_NETWORK_BASE, 0.4, label='BASE (no 2025 uplift)', color='#888')
    ax[1].bar(x + 0.2, a.binding_hours_C1_NETWORK_CALIBRATED, 0.4, label='CALIBRATED (+4,994 MVA on 18 lines)', color='#2a6')
    ax[1].set_xticks(x); ax[1].set_xticklabels([f"{l}{'*' if u else ''}" for l, u in zip(a.line, a.uplift_line)], rotation=60, fontsize=8)
    ax[1].set_ylabel('binding hours (annual, 3 h x 3)'); ax[1].set_title('Most binding lines, annual 3 h (* = uplift line)'); ax[1].legend(fontsize=8)
    fig.suptitle('C1: existing-model 2025 fleet fixed-asset diagnostic (static year-end fleet, not a historical replay)', fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / 'C1_MAIN_RESULTS.png', dpi=130)
