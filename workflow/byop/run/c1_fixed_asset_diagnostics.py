#!/usr/bin/env python3
"""C1 fixed-asset dispatch diagnostics (BYOP C0 repair / C1 prompt v1.4, 2026-10-22, stage B), run on L2 from workflow/:
    python byop/run/c1_fixed_asset_diagnostics.py --dry                 # build + checks + create the linopy model, NO solve
    python byop/run/c1_fixed_asset_diagnostics.py --run annual --case C1_NETWORK_BASE
    python byop/run/c1_fixed_asset_diagnostics.py --run window --case C1_NETWORK_CALIBRATED   (needs the CALIBRATED annual SOC)
    python byop/run/c1_fixed_asset_diagnostics.py --collect             # comparison tables + C1_QA.json (no solve)
Config: config/config.byop_c1_fixed_asset_diag.yaml (its own authorisation, NOT the formal mainline gate, which is untouched).

Physical bounds: the existing-model 2025 fleet only (extendable components and build_year > 2025 removed), every *_nom fixed
(asserted on the components AND on the linopy variables: no *_nom variable may exist), no lines / links added or relaxed,
lv_limit global constraint dropped (no line is extendable), diagnostic shed generator per load bus at the mainline VOLL,
storage annual-cyclic (annual) / SOC fixed at both window ends from the CALIBRATED annual result (windows; same values for both
networks). Only the line capacities differ between the two cases (2025 calibration uplift, checked line by line).
This is a static year-end-fleet diagnostic: it is NOT a historical replay and it does not certify firm rights, POI
eligibility, N-1 security or probabilistic adequacy. Solves are counted in C1_SOLVE_LOG.csv (max 6 diagnostic solves;
failed attempts that are retried are logged as retries with their reason).
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

CFG_PATH = WF / 'config/config.byop_c1_fixed_asset_diag.yaml'
OUT = BP.C1_RESULTS
LOG = OUT / 'C1_SOLVE_LOG.csv'
CASES = ['C1_NETWORK_BASE', 'C1_NETWORK_CALIBRATED']
KINDS = {'annual': 'ANNUAL_3H', 'window': 'PEAK_WINDOW_1H'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ gate
def load_cfg():
    c = yaml.safe_load(CFG_PATH.read_text(encoding='utf-8'))['c1']
    src = WF.parent / c['authorization_source']
    reasons = []
    if c.get('authorization') != 'AUTHORIZED_BY_RESEARCHER_PROMPT_V1_4':
        reasons.append('authorization string')
    if not src.exists() or sha(src) != c['authorization_source_sha256']:
        reasons.append('authorization source missing or changed')
    if set(c['cases']) != set(CASES):
        reasons.append('case list differs from the prompt')
    return c, reasons


def solve_log():
    return pd.read_csv(LOG) if LOG.exists() else pd.DataFrame(columns=['timestamp_utc', 'case', 'kind', 'attempt', 'counted_as', 'reason', 'status', 'termination', 'seconds'])


def gate(c, reasons, case, kind, upstream=''):
    if reasons:
        raise SystemExit(f'C1 gate REFUSED: {reasons}')
    if case not in CASES or kind not in KINDS:
        raise SystemExit(f'C1 gate REFUSED: {case} / {kind} not in the authorised list')
    lg = solve_log()
    done = lg[(lg.status == 'ok') & (lg.termination == 'optimal')]          # only an optimal LP counts as solved
    if ((done.case == case) & (done.kind == kind)).any() and not upstream:
        raise SystemExit(f'C1 gate REFUSED: {case} {kind} already solved (no silent re-run; a changed upstream SOC boundary needs --upstream)')
    prev = lg[(lg.case == case) & (lg.kind == kind)]
    if len(prev):
        return 'retry', f'previous attempt {prev.iloc[-1].status}: {prev.iloc[-1].termination}' + (f'; {upstream}' if upstream else '')
    if int((lg.counted_as == 'diagnostic').sum()) >= int(c['max_diagnostic_solves']):
        raise SystemExit('C1 gate REFUSED: diagnostic solve budget used')
    return 'diagnostic', ''


def log_solve(case, kind, counted, reason, status, term, sec):
    lg = solve_log()
    lg = pd.concat([lg, pd.DataFrame([dict(timestamp_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), case=case, kind=kind,
                                           attempt=int(((lg.case == case) & (lg.kind == kind)).sum()) + 1, counted_as=counted, reason=reason,
                                           status=status, termination=term, seconds=round(sec, 1))])], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    lg.to_csv(LOG, index=False, lineterminator='\n')


# ------------------------------------------------------------------------------------------------ networks
def prepare(c, case):
    import pypsa
    p = WF / c['cases'][case]['network']
    n = pypsa.Network(str(p))
    g = n.generators
    n.remove('Generator', g.index[g.p_nom_extendable | (g.build_year > 2025)])
    s = n.storage_units
    n.remove('StorageUnit', s.index[s.p_nom_extendable | (s.build_year > 2025)])
    for df in (n.generators, n.storage_units, n.lines):
        df['lifetime'] = np.inf; df['build_year'] = 0
    gcs = list(n.global_constraints.index)
    if gcs:
        n.remove('GlobalConstraint', gcs)
    n.storage_units['cyclic_state_of_charge'] = True
    n.storage_units['cyclic_state_of_charge_per_period'] = False
    if 'load_shed' not in n.carriers.index:
        n.add('Carrier', 'load_shed')
    buses = sorted(set(n.loads.bus))
    n.add('Generator', [f'{b} C1 shed' for b in buses], bus=buses, carrier='load_shed', p_nom=1e5, marginal_cost=float(c['voll_USD_MWh']))
    info = dict(network=str(p.relative_to(WF)), network_sha256=sha(p), removed_global_constraints=gcs,
                generators=int(len(n.generators)), storage_units=int(len(n.storage_units)), lines=int(len(n.lines)), links=int(len(n.links)),
                fleet_MW_by_carrier={k: round(float(v), 1) for k, v in n.generators[n.generators.carrier != 'load_shed'].groupby('carrier').p_nom.sum().items()},
                storage_MW=round(float(n.storage_units.p_nom.sum()), 1))
    assert not n.generators.p_nom_extendable.any() and not n.storage_units.p_nom_extendable.any()
    assert not n.lines.s_nom_extendable.any() and (len(n.links) == 0 or not n.links.p_nom_extendable.any())
    assert len(n.stores) == 0 and not (n.links.carrier == 'AC_s0cal').any() if len(n.links) else True
    return n, info


def hourly_bus_load():
    """baseline builder rule: weather-zone native load -> county lpf x substation share -> cluster bus (3 h means = network load)"""
    sh = pd.read_csv(BP.BASE_TAMU_DIR / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
    split = sh.assign(w=sh.lpf * sh.share).groupby(['wz', 'cluster_bus']).w.sum()
    split = split / split.groupby(level=0).transform('sum')
    nl = pd.read_excel(BP.NATIVE_LOAD)
    hourly = pd.DataFrame(0.0, index=range(8760), columns=sorted(set(sh.cluster_bus)))
    for (wz, bb), s in split.items():
        hourly[bb] += nl[wz].values * s
    return hourly, nl


def window_bounds(c, nl):
    w = c['windows']['peak_load']
    peak = int(nl.ERCOT.idxmax())
    start = int(np.floor((peak - w['length_h'] / 2) / 3) * 3)
    return dict(peak_row=peak, peak_label=str(nl.iloc[peak, 0]), start_h=start, end_h=start + int(w['length_h']), buffer_h=int(w['buffer_h']))


def to_window(n, c, wb, hourly, soc_start, soc_end):
    L = wb['end_h'] - wb['start_h']
    old = n.snapshots
    t0 = old.get_level_values(1)[0] + pd.Timedelta(hours=wb['start_h'])
    ts = pd.MultiIndex.from_arrays([[old.get_level_values(0)[0]] * L, pd.date_range(t0, periods=L, freq='h')], names=old.names)
    idx3 = np.arange(wb['start_h'], wb['end_h']) // 3
    pmax = n.generators_t.p_max_pu.iloc[idx3].copy()
    lb = n.loads.bus
    load = pd.DataFrame({l: hourly[lb[l]].values[wb['start_h']:wb['end_h']] for l in n.loads.index})
    chk = float(np.abs(load.groupby(np.arange(L) // 3).mean().values - n.loads_t.p_set.iloc[wb['start_h'] // 3:wb['end_h'] // 3].values).max())
    n.set_snapshots(ts)
    n.snapshot_weightings.loc[:, :] = 1.0
    pmax.index = ts
    n.generators_t.p_max_pu = pmax
    load.index = ts
    n.loads_t.p_set = load
    su = n.storage_units.index
    n.storage_units['cyclic_state_of_charge'] = False
    n.storage_units['state_of_charge_initial'] = soc_start.reindex(su).fillna(0.0).values
    socset = pd.DataFrame(np.nan, index=ts, columns=su)
    socset.iloc[-1] = soc_end.reindex(su).fillna(0.0).values
    n.storage_units_t.state_of_charge_set = socset
    return dict(load_3h_mean_vs_network_max_abs_MW=chk, renewables='RE_HELD_AT_3H_VALUE (not a measured 1 h curve)')


def assert_no_build_variables(n):
    names = list(n.model.variables)
    bad = [v for v in names if v.endswith('-p_nom') or v.endswith('-s_nom') or v.endswith('-e_nom')]
    assert not bad, bad
    return names


# ------------------------------------------------------------------------------------------------ metrics
def metrics(n, case, kind, eval_from=0):
    w = n.snapshot_weightings.generators
    sl = slice(eval_from, None)
    g = n.generators
    shed_c = g.index[g.carrier == 'load_shed']
    P = n.generators_t.p
    shed = P[shed_c].iloc[sl]
    ws = w.iloc[sl]
    tot = shed.sum(axis=1)
    ev = []
    for col in shed_c:
        x = shed[col].values > 1e-3
        i = 0
        while i < len(x):
            if x[i]:
                j = i
                while j + 1 < len(x) and x[j + 1]:
                    j += 1
                seg = shed[col].iloc[i:j + 1]
                ev.append(dict(case=case, kind=kind, bus=g.bus[col], start=str(seg.index[0][1]), end=str(seg.index[-1][1]),
                               duration_h=float(ws.iloc[i:j + 1].sum()), energy_MWh=float((seg * ws.iloc[i:j + 1]).sum()), peak_MW=float(seg.max())))
                i = j + 1
            else:
                i += 1
    lines = n.lines
    lim = lines.s_nom * lines.s_max_pu
    p0 = n.lines_t.p0.iloc[sl]
    load_ = p0.abs() / lim
    bind = load_ >= 0.999
    bl = pd.DataFrame(dict(case=case, kind=kind, line=lines.index, bus0=lines.bus0, bus1=lines.bus1, s_nom_MVA=lines.s_nom, limit_MW=lim,
                           binding_hours=(bind.mul(ws, axis=0)).sum().values, max_loading=load_.max().values, mean_loading=load_.mean().values))
    gen = (P.iloc[sl].mul(ws, axis=0)).sum().groupby(g.carrier).sum()
    curt = {}
    for car in ('onwind', 'solar'):
        cc = [x for x in g.index[g.carrier == car] if x in n.generators_t.p_max_pu]
        av = n.generators_t.p_max_pu[cc].iloc[sl] * g.p_nom[cc]
        curt[car] = float(((av - P[cc].iloc[sl]).clip(lower=0).mul(ws, axis=0)).sum().sum())
    su = n.storage_units
    pdp, pst = n.storage_units_t.p_dispatch.iloc[sl], n.storage_units_t.p_store.iloc[sl]
    simul = (pdp > 1e-3) & (pst > 1e-3)
    soc = n.storage_units_t.state_of_charge
    # bus balance residual: generation + storage - load - line withdrawals at both ends
    inj = P.T.groupby(g.bus).sum().T.reindex(columns=n.buses.index, fill_value=0.0)
    inj = inj.add(n.storage_units_t.p.T.groupby(su.bus).sum().T.reindex(columns=n.buses.index, fill_value=0.0), fill_value=0.0)
    inj = inj.sub(n.loads_t.p.T.groupby(n.loads.bus).sum().T.reindex(columns=n.buses.index, fill_value=0.0), fill_value=0.0)
    inj = inj.sub(n.lines_t.p0.T.groupby(lines.bus0).sum().T.reindex(columns=n.buses.index, fill_value=0.0), fill_value=0.0)
    inj = inj.sub(n.lines_t.p1.T.groupby(lines.bus1).sum().T.reindex(columns=n.buses.index, fill_value=0.0), fill_value=0.0)
    m = dict(case=case, kind=kind, snapshots=int(len(n.snapshots)), evaluated_snapshots=int(len(ws)), weight_h=float(w.iloc[0]),
             objective_USD=float(n.objective), shed_MWh=float((tot * ws).sum()), shed_max_MW=float(tot.max()),
             shed_steps=int((tot > 1e-3).sum()), shed_hours=float(ws[tot > 1e-3].sum()), shed_buses=int((shed.max() > 1e-3).sum()),
             longest_shed_event_h=float(max([e['duration_h'] for e in ev], default=0.0)),
             binding_lines=int((bl.binding_hours > 0).sum()), line_binding_hours_total=float(bl.binding_hours.sum()),
             curtailment_wind_MWh=curt['onwind'], curtailment_solar_MWh=curt['solar'],
             storage_dispatch_MWh=float((pdp.mul(ws, axis=0)).sum().sum()), storage_charge_MWh=float((pst.mul(ws, axis=0)).sum().sum()),
             storage_simultaneous_steps=int(simul.any(axis=1).sum()), storage_simultaneous_MWh=float((np.minimum(pdp, pst).where(simul, 0).mul(ws, axis=0)).sum().sum()),
             soc_total_first_MWh=float(soc.iloc[0].sum()), soc_total_last_MWh=float(soc.iloc[-1].sum()),
             balance_residual_max_abs_MW=float(inj.abs().max().max()), load_MWh=float((n.loads_t.p.iloc[sl].sum(axis=1) * ws).sum()))
    return m, pd.DataFrame(ev), bl, gen.rename('MWh').reset_index().assign(case=case, kind=kind)


# ------------------------------------------------------------------------------------------------ actions
def solve(n, c, threads, opts):
    t = time.time()
    st, term = n.optimize(solver_name=c['solver'], solver_options=dict(opts, Threads=int(threads)))
    return st, str(term), time.time() - t


def run(c, reasons, case, kind, threads, retry=False, upstream=''):
    counted, why = gate(c, reasons, case, kind, upstream)
    if retry != (counted == 'retry'):
        raise SystemExit(f'C1: --retry {"given without" if retry else "missing for"} a previous attempt of {case} {kind}')
    opts = c['retry_solver_options'] if retry else c['solver_options']
    d = OUT / f'{case}__{KINDS[kind]}'
    if (d / 'metrics.json').exists():                       # keep every earlier attempt's outputs
        k = 1
        while (OUT / f'{d.name}__attempt{k}').exists():
            k += 1
        d.rename(OUT / f'{d.name}__attempt{k}')
    d.mkdir(parents=True, exist_ok=True)
    n, info = prepare(c, case)
    extra, eval_from = {}, 0
    if kind == 'window':
        hourly, nl = hourly_bus_load()
        wb = window_bounds(c, nl)
        soc = pd.read_csv(OUT / 'C1_NETWORK_CALIBRATED__ANNUAL_3H/storage_soc.csv.gz', index_col=[0, 1])
        k0, k1 = wb['start_h'] // 3 - 1, wb['end_h'] // 3 - 1
        extra = to_window(n, c, wb, hourly, soc.iloc[k0], soc.iloc[k1])
        extra.update(wb, soc_boundary='CALIBRATED annual SOC at the end of 3 h steps %d and %d (same values for both networks)' % (k0, k1))
        eval_from = wb['buffer_h']
    n.optimize.create_model()
    var_names = assert_no_build_variables(n)
    try:
        st, term, sec = solve(n, c, threads, opts)
    except Exception as e:                                   # logged, never silently retried
        log_solve(case, kind, counted, why, 'error', repr(e)[:200], 0.0)
        raise
    ok = st == 'ok' and term == 'optimal'
    log_solve(case, kind, counted, why, st, term, sec)
    m, ev, bl, gen = metrics(n, case, kind, eval_from)
    m.update(status=st, termination=term, seconds=round(sec, 1), counted_as=counted, solver_options=opts, linopy_variables=var_names,
             n_vars=int(n.model.nvars), n_cons=int(n.model.ncons), threads=int(threads), config_sha256=sha(CFG_PATH),
             script_sha256=sha(__file__), network=info, window=extra, label=c['label'])
    (d / 'metrics.json').write_text(json.dumps(m, indent=1, default=str))
    ev.to_csv(d / 'shedding_events.csv', index=False, lineterminator='\n')
    bl.to_csv(d / 'lines.csv', index=False, lineterminator='\n')
    gen.to_csv(d / 'generation_by_carrier.csv', index=False, lineterminator='\n')
    n.storage_units_t.state_of_charge.to_csv(d / 'storage_soc.csv.gz')
    print(json.dumps({k: v for k, v in m.items() if k not in ('linopy_variables', 'network', 'window')}, indent=1, default=str))
    if not ok:
        raise SystemExit(f'{case} {kind}: {st} {term} (outputs kept, NOT counted as solved)')


def dry(c, reasons, threads):
    """build both cases (annual + window with a placeholder SOC), check every bound and create the models - no solve"""
    rep = dict(gate_reasons=reasons)
    nets = {}
    for case in CASES:
        n, info = prepare(c, case)
        n.optimize.create_model()
        rep[case] = dict(info, linopy_variables=assert_no_build_variables(n), n_vars=int(n.model.nvars), n_cons=int(n.model.ncons))
        nets[case] = n
    a, b = nets['C1_NETWORK_BASE'], nets['C1_NETWORK_CALIBRATED']
    d = (b.lines.s_nom - a.lines.s_nom)
    led = pd.read_csv(WF / c['uplift_ledger']).set_index('line')
    same = {}
    for comp in ('generators', 'storage_units', 'loads', 'buses'):
        x, y = getattr(a, comp), getattr(b, comp)
        same[comp] = bool(x.index.equals(y.index) and all(np.allclose(x[k].fillna(0).values, y[k].fillna(0).values) for k in x.columns
                                                           if pd.api.types.is_numeric_dtype(x[k]) and k in y))
    same['loads_t'] = bool(np.allclose(a.loads_t.p_set.values, b.loads_t.p_set.values))
    same['p_max_pu'] = bool(np.allclose(a.generators_t.p_max_pu.values, b.generators_t.p_max_pu.values))
    same['line_s_max_pu_length'] = bool(all(np.allclose(a.lines[k].values, b.lines[k].values) for k in ('s_max_pu', 'length')))
    ratio = (b.lines.s_nom / a.lines.s_nom)
    xs = ~np.isclose(a.lines.x.values, b.lines.x.values)
    same['line_x_r_scaled_only_on_uplift_lines_by_s_ratio'] = bool(set(a.lines.index[xs]) == set(d.index[d.abs() > 1e-6]) and
                                                                   np.allclose((a.lines.x / b.lines.x).values, ratio.values) and np.allclose((a.lines.r / b.lines.r).values, ratio.values))
    rep['network_difference'] = dict(lines_changed=int((d.abs() > 1e-6).sum()), uplift_MVA=float(d.sum()),
                                     equals_ledger=bool(np.allclose(d[d.abs() > 1e-6].sort_index().values, led.added_MVA.reindex(d[d.abs() > 1e-6].index).sort_index().values, atol=1e-6)),
                                     all_else_identical=same)
    hourly, nl = hourly_bus_load()
    wb = window_bounds(c, nl)
    zero = pd.Series(0.0, index=b.storage_units.index)
    rep['window'] = dict(wb, **to_window(b, c, wb, hourly, zero, zero))
    b.optimize.create_model()
    rep['window']['linopy_variables'] = assert_no_build_variables(b)
    rep['window']['n_vars'] = int(b.model.nvars)
    rep['max_net_load_window'] = c['windows']['max_net_load']['status']
    rep['solver_calls'] = 0
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'C1_DRY_CHECK.json').write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k not in CASES}, indent=1, default=str))
    print({k: {kk: vv for kk, vv in rep[k].items() if kk in ('n_vars', 'n_cons', 'removed_global_constraints', 'storage_MW')} for k in CASES})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--run', choices=list(KINDS)); ap.add_argument('--case', choices=CASES)
    ap.add_argument('--collect', action='store_true')
    ap.add_argument('--retry', action='store_true', help='re-solve a case whose previous attempt was not optimal (retry_solver_options)')
    ap.add_argument('--upstream', default='', help='reason text when a window is retried because its SOC boundary changed')
    ap.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 8)))
    a = ap.parse_args()
    c, reasons = load_cfg()
    if a.dry:
        dry(c, reasons, a.threads)
    elif a.run:
        run(c, reasons, a.case, a.run, a.threads, a.retry, a.upstream)
    elif a.collect:
        import importlib.util
        spec = importlib.util.spec_from_file_location('c1_collect', WF / 'byop/post/c1_collect.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        m.collect(c)


if __name__ == '__main__':
    main()
