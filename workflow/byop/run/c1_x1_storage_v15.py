#!/usr/bin/env python3
"""C1-X1 network comparison + storage degeneracy validation (work package v1.5, 2026-10-22), run on L2 from workflow/:
    python byop/run/c1_x1_storage_v15.py --dry            # build X1, line audit, model + stage-2 expressions, NO solve
    python byop/run/c1_x1_storage_v15.py --run            # stage 1 (X1) then stage 2 on the same in-memory model
    python byop/run/c1_x1_storage_v15.py --stage2-retry   # only if stage 2 failed: rebuild stage 2 from saved F*, E* (stage 1 not re-solved)
Config: config/config.byop_c1_x1_storage_v15.yaml (own authorisation; formal gates untouched).
X1 = the v1.4 C1_NETWORK_CALIBRATED diagnostic network (same fleet, storage, VOLL, shed variables, global-constraint removal)
with x, r of the 18 uplift lines set back to the raw-network values by line ID; s_nom, s_max_pu, topology unchanged.
Stage 2 keeps every physical constraint and asset, adds F(x) <= F* + eps_F and E* - eps_E <= E(x) <= E* + eps_E (F = the
stage-1 objective expression, E = weighted total shed), and minimises sum_t w_t sum_s (p_store + p_dispatch). No cost change,
no binaries. Stage-1 bus prices (economic duals) and stage-2 duals are saved in separate folders / fields.
"""
from __future__ import annotations

import argparse, hashlib, importlib.util, json, platform, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402

CFG = WF / 'config/config.byop_c1_x1_storage_v15.yaml'
OUT = BP.RESULTS / 'C1_X1_STORAGE_V15'
LOG = OUT / 'C1_X1_SOLVE_LOG.csv'
S1, S2 = 'C1_X1_RAW_IMPEDANCE', 'C1_X1_MIN_STORAGE_THROUGHPUT'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('c1diag', WF / 'byop/run/c1_fixed_asset_diagnostics.py')
C1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(C1)


# ------------------------------------------------------------------------------------------------ gate / log
def load_cfg():
    c = yaml.safe_load(CFG.read_text(encoding='utf-8'))['c1x1']
    src = WF.parent / c['authorization_source']
    reasons = []
    if c.get('authorization') != 'AUTHORIZED_BY_RESEARCHER_WP_V1_5':
        reasons.append('authorization string')
    if not src.exists() or sha(src) != c['authorization_source_sha256']:
        reasons.append('authorization source missing or changed')
    base = yaml.safe_load((WF / c['base_config']).read_text(encoding='utf-8'))['c1']
    return c, base, reasons


def solve_log():
    return pd.read_csv(LOG) if LOG.exists() else pd.DataFrame(columns=['timestamp_utc', 'stage', 'attempt', 'counted_as', 'reason', 'status', 'termination', 'seconds'])


def gate(c, reasons, stage):
    if reasons:
        raise SystemExit(f'C1-X1 gate REFUSED: {reasons}')
    lg = solve_log()
    if ((lg.stage == stage) & (lg.status == 'ok') & (lg.termination == 'optimal')).any():
        raise SystemExit(f'C1-X1 gate REFUSED: {stage} already solved optimally (no silent re-run)')
    prev = lg[lg.stage == stage]
    return ('retry', f'previous attempt {prev.iloc[-1].status}: {prev.iloc[-1].termination}') if len(prev) else ('effective', '')


def log_solve(stage, counted, why, st, term, sec):
    lg = solve_log()
    lg = pd.concat([lg, pd.DataFrame([dict(timestamp_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), stage=stage,
                                           attempt=int((lg.stage == stage).sum()) + 1, counted_as=counted, reason=why, status=st,
                                           termination=term, seconds=round(sec, 1))])], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    lg.to_csv(LOG, index=False, lineterminator='\n')


# ------------------------------------------------------------------------------------------------ network
def build_x1(c, base):
    import pypsa
    n, info = C1.prepare(base, c['base_case'])
    cal_x, cal_r, cal_s = n.lines.x.copy(), n.lines.r.copy(), n.lines.s_nom.copy()
    raw = pypsa.Network(str(WF / c['raw_network']))
    led = pd.read_csv(WF / c['uplift_ledger']).set_index('line')
    assert set(led.index) <= set(raw.lines.index) and set(led.index) <= set(n.lines.index)
    n.lines.loc[led.index, 'x'] = raw.lines.x.reindex(led.index).values           # by stable line ID, not row order
    n.lines.loc[led.index, 'r'] = raw.lines.r.reindex(led.index).values
    a = pd.DataFrame(dict(bus0=n.lines.bus0, bus1=n.lines.bus1, s_nom_raw=raw.lines.s_nom.reindex(n.lines.index), s_nom_calibrated=cal_s,
                          s_nom_X1=n.lines.s_nom, s_max_pu=n.lines.s_max_pu, x_raw=raw.lines.x.reindex(n.lines.index), x_calibrated=cal_x,
                          x_X1=n.lines.x, r_raw=raw.lines.r.reindex(n.lines.index), r_calibrated=cal_r, r_X1=n.lines.r))
    a['uplift_line'] = a.index.isin(led.index)
    a['impedance_restored'] = ~np.isclose(a.x_X1, a.x_calibrated) | ~np.isclose(a.r_X1, a.r_calibrated)
    assert (a.s_nom_X1 == a.s_nom_calibrated).all(), 'X1 capacity must equal CALIBRATED exactly'
    assert set(a.index[a.impedance_restored]) == set(led.index), 'impedance change must be exactly the 18 uplift lines'
    assert np.allclose(a.loc[a.uplift_line, 'x_X1'], a.loc[a.uplift_line, 'x_raw']) and np.allclose(a.loc[~a.uplift_line, 'x_X1'], a.loc[~a.uplift_line, 'x_calibrated'])
    info.update(raw_network_sha256=sha(WF / c['raw_network']), uplift_ledger_sha256=sha(WF / c['uplift_ledger']), lines_restored=int(a.impedance_restored.sum()))
    return n, info, a


def wda(n, var):
    import xarray as xr
    w = n.snapshot_weightings.generators
    return xr.DataArray(w.values, coords={'snapshot': var.coords['snapshot']}, dims='snapshot')


def stage2_expressions(n):
    m = n.model
    gp = m['Generator-p']
    shed = list(n.generators.index[n.generators.carrier == 'load_shed'])
    w = wda(n, gp)
    E = (gp.sel(name=shed) * w).sum()
    T = ((m['StorageUnit-p_store'] + m['StorageUnit-p_dispatch']) * wda(n, m['StorageUnit-p_store'])).sum()
    return E, T, shed


def economic_cost(n):
    """F(x) recomputed from the network solution: sum_t w_t (sum_g mc_g p_g + sum_s mc_s p_dispatch_s) - the PyPSA operational
    objective of this fixed-asset model (no capital terms: nothing is extendable)"""
    w = n.snapshot_weightings.objective
    g = n.generators
    mc = n.get_switchable_as_dense('Generator', 'marginal_cost')
    gen = (n.generators_t.p * mc).mul(w, axis=0).sum()
    s = n.storage_units
    smc = n.get_switchable_as_dense('StorageUnit', 'marginal_cost')
    sto = (n.storage_units_t.p_dispatch * smc).mul(w, axis=0).sum().sum()
    by = gen.groupby(g.carrier).sum()
    return float(gen.sum() + sto), {k: float(v) for k, v in by.items()} | {'storage_dispatch_cost': float(sto)}


def shed_total(n, shed):
    return float(n.generators_t.p[shed].mul(n.snapshot_weightings.generators, axis=0).sum().sum())


# ------------------------------------------------------------------------------------------------ exports
def storage_state_residual(n):
    """per unit: SOC_t - [SOC_{t-1} (1-sl)^w + w (eta_s p_store - p_dispatch / eta_d)] with the cyclic SOC_{-1} = SOC_T"""
    s = n.storage_units
    w = n.snapshot_weightings.stores.values[:, None]
    soc = n.storage_units_t.state_of_charge[s.index].values
    prev = np.vstack([soc[-1:], soc[:-1]])
    sl = s.standing_loss.values[None, :]
    pred = prev * (1 - sl) ** w + w * (s.efficiency_store.values * n.storage_units_t.p_store[s.index].values
                                       - n.storage_units_t.p_dispatch[s.index].values / s.efficiency_dispatch.values)
    return pd.Series(np.abs(soc - pred).max(axis=0), index=s.index)


def export(n, d, stage, extra, thr):
    d.mkdir(parents=True, exist_ok=True)
    w = n.snapshot_weightings.generators
    s, g, L = n.storage_units, n.generators, n.lines
    gz = lambda df, nm: df.to_csv(d / nm, compression='gzip')
    gz(n.storage_units_t.p_store[s.index], 'storage_p_store.csv.gz')
    gz(n.storage_units_t.p_dispatch[s.index], 'storage_p_dispatch.csv.gz')
    gz(n.storage_units_t.state_of_charge[s.index], 'storage_soc.csv.gz')
    s[['bus', 'carrier', 'p_nom', 'max_hours', 'efficiency_store', 'efficiency_dispatch', 'standing_loss', 'cyclic_state_of_charge',
       'state_of_charge_initial', 'marginal_cost']].to_csv(d / 'storage_static.csv')
    gz(n.generators_t.p, 'generators_p.csv.gz')
    av = n.get_switchable_as_dense('Generator', 'p_max_pu') * g.p_nom
    gz(av, 'generators_available.csv.gz')
    g[['bus', 'carrier', 'p_nom', 'p_min_pu', 'p_max_pu', 'marginal_cost']].to_csv(d / 'generators_static.csv')
    gz(n.lines_t.p0, 'lines_p0.csv.gz'); gz(n.lines_t.p1, 'lines_p1.csv.gz')
    lim = L.s_nom * L.s_max_pu
    L.assign(limit_MW=lim)[['bus0', 'bus1', 's_nom', 's_max_pu', 'limit_MW', 'x', 'r']].to_csv(d / 'lines_static.csv')
    sat = (n.lines_t.p0.abs() / lim) >= 0.999
    gz(sat.astype(int), 'lines_saturated.csv.gz')
    shed = g.index[g.carrier == 'load_shed']
    gz(n.generators_t.p[shed].rename(columns=lambda c_: g.bus[c_]), 'shed_by_bus.csv.gz')
    price_nm = 'economic_marginal_price.csv.gz' if stage == S1 else 'stage2_nodal_balance_duals_NOT_economic_prices.csv.gz'
    if len(n.buses_t.marginal_price.columns):
        gz(n.buses_t.marginal_price, price_nm)
    pdp, pst = n.storage_units_t.p_dispatch[s.index], n.storage_units_t.p_store[s.index]
    ov = np.minimum(pdp, pst).where((pdp > thr) & (pst > thr), 0.0)
    loss = (pst.mul(s.efficiency_store, axis=1) - pst) * -1 + (pdp.div(s.efficiency_dispatch, axis=1) - pdp)
    unit = pd.DataFrame(dict(bus=s.bus, p_nom=s.p_nom, energy_cap_MWh=s.p_nom * s.max_hours,
                             charge_MWh=pst.mul(w, axis=0).sum(), dispatch_MWh=pdp.mul(w, axis=0).sum(),
                             throughput_MWh=(pst + pdp).mul(w, axis=0).sum(), overlap_MWh=ov.mul(w, axis=0).sum(),
                             overlap_steps=((pdp > thr) & (pst > thr)).sum(), conversion_loss_MWh=loss.mul(w, axis=0).sum(),
                             soc_first_end_MWh=n.storage_units_t.state_of_charge[s.index].iloc[0], soc_last_end_MWh=n.storage_units_t.state_of_charge[s.index].iloc[-1],
                             state_equation_max_abs_residual_MWh=storage_state_residual(n)))
    unit.to_csv(d / 'storage_by_unit.csv')
    m, ev, bl, gen = C1.metrics(n, stage, 'ANNUAL_3H', 0)
    ev.to_csv(d / 'shedding_events.csv', index=False); bl.to_csv(d / 'lines.csv', index=False); gen.to_csv(d / 'generation_by_carrier.csv', index=False)
    m.update(extra)
    m['storage_conversion_loss_MWh'] = float(unit.conversion_loss_MWh.sum())
    m['storage_throughput_MWh'] = float(unit.throughput_MWh.sum())
    m['storage_state_equation_max_abs_residual_MWh'] = float(unit.state_equation_max_abs_residual_MWh.max())
    m['price_file'] = price_nm if len(n.buses_t.marginal_price.columns) else 'NOT_AVAILABLE (no duals assigned)'
    (d / 'metrics.json').write_text(json.dumps(m, indent=1, default=str))
    return m


def env_info(c):
    import pypsa, linopy, gurobipy
    return dict(python=platform.python_version(), pypsa=pypsa.__version__, linopy=linopy.__version__, gurobipy='.'.join(map(str, gurobipy.gurobi.version())),
                config_sha256=sha(CFG), script_sha256=sha(__file__), base_runner_sha256=sha(WF / 'byop/run/c1_fixed_asset_diagnostics.py'),
                authorization_source_sha256=c['authorization_source_sha256'], host=platform.node())


# ------------------------------------------------------------------------------------------------ actions
def solve_stage(n, c, stage, threads, why_counted):
    counted, why = why_counted
    t = time.time()
    st, term = n.optimize.solve_model(solver_name=c['solver'], solver_options=dict(c['solver_options'], Threads=int(threads)))
    sec = time.time() - t
    log_solve(stage, counted, why, st, str(term), sec)
    return st, str(term), sec, counted


def add_stage2(n, c, F_expr, Fstar, Estar):
    m = n.model
    E, T, shed = stage2_expressions(n)
    eF = max(c['epsilon_F']['abs_USD'], c['epsilon_F']['rel'] * abs(Fstar))
    eE = max(c['epsilon_E']['abs_MWh'], c['epsilon_E']['rel'] * abs(Estar))
    m.add_constraints(F_expr <= Fstar + eF, name='X1S2-economic_cost_bound')
    m.add_constraints(E <= Estar + eE, name='X1S2-shed_upper')
    m.add_constraints(E >= max(0.0, Estar - eE), name='X1S2-shed_lower')
    m.add_objective(T, overwrite=True)
    return dict(epsilon_F_USD=eF, epsilon_E_MWh=eE, F_bound_USD=Fstar + eF, E_bounds_MWh=[max(0.0, Estar - eE), Estar + eE]), shed


def run(c, base, reasons, threads):
    g1 = gate(c, reasons, S1)
    n, info, audit = build_x1(c, base)
    OUT.mkdir(parents=True, exist_ok=True)
    audit.to_csv(OUT / 'C1_X1_LINE_INPUT_AUDIT.csv', lineterminator='\n', float_format='%.6f')
    n.optimize.create_model()
    C1.assert_no_build_variables(n)
    F_expr = n.model.objective.expression                     # the stage-1 economic objective, kept for stage 2
    t0 = datetime.now(timezone.utc).isoformat(timespec='seconds')
    st, term, sec, counted = solve_stage(n, c, S1, threads, g1)
    ok1 = st == 'ok' and term == 'optimal'
    Fstar = float(n.model.objective.value) if ok1 else None
    shed = list(n.generators.index[n.generators.carrier == 'load_shed'])
    Estar = shed_total(n, shed) if ok1 else None
    Fman, Fparts = economic_cost(n) if ok1 else (None, None)
    extra = dict(stage=S1, status=st, termination=term, seconds=round(sec, 1), counted_as=counted, start_utc=t0, network=info,
                 solver_options=c['solver_options'], env=env_info(c), F_star_USD=Fstar, F_recomputed_USD=Fman, F_components_USD=Fparts, E_star_MWh=Estar,
                 objective_expression='PyPSA operational objective of the fixed-asset model (linopy n.model.objective at stage 1)')
    m1 = export(n, OUT / 'stage1_X1', S1, extra, c['overlap_threshold_MW'])
    (OUT / 'stage1_objective.json').write_text(json.dumps(dict(F_star_USD=Fstar, E_star_MWh=Estar, F_recomputed_USD=Fman, F_components_USD=Fparts,
                                                               status=st, termination=term), indent=1))
    print(json.dumps({k: m1[k] for k in ('termination', 'shed_MWh', 'shed_max_MW', 'binding_lines', 'storage_simultaneous_MWh', 'balance_residual_max_abs_MW')}, indent=1))
    if not ok1:
        raise SystemExit(f'stage 1 {st} {term}: stage 2 NOT started')
    g2 = gate(c, reasons, S2)
    bounds, _ = add_stage2(n, c, F_expr, Fstar, Estar)
    t0 = datetime.now(timezone.utc).isoformat(timespec='seconds')
    st, term, sec, counted = solve_stage(n, c, S2, threads, g2)
    finish_stage2(n, c, st, term, sec, counted, t0, info, bounds, Fstar, Estar, shed, 'in-memory stage-1 model')


def finish_stage2(n, c, st, term, sec, counted, t0, info, bounds, Fstar, Estar, shed, how):
    ok = st == 'ok' and term == 'optimal'
    F2, F2parts = economic_cost(n)
    E2 = shed_total(n, shed)
    tol = 1e-6 * max(1.0, abs(Fstar))                       # solver feasibility slack on a 1e10 USD objective
    extra = dict(stage=S2, status=st, termination=term, seconds=round(sec, 1), counted_as=counted, start_utc=t0, network=info, built_from=how,
                 solver_options=c['solver_options'], env=env_info(c), F_star_USD=Fstar, E_star_MWh=Estar, **bounds,
                 F_stage2_recomputed_USD=F2, F_stage2_components_USD=F2parts, E_stage2_MWh=E2,
                 F_bound_ok=bool(F2 <= bounds['F_bound_USD'] + tol), E_bound_ok=bool(bounds['E_bounds_MWh'][0] - 1e-6 <= E2 <= bounds['E_bounds_MWh'][1] + 1e-6),
                 objective_expression='min sum_t w_t sum_s (p_store + p_dispatch); duals of this stage are NOT economic prices',
                 stage2_objective_value=float(n.model.objective.value) if ok else None)
    m2 = export(n, OUT / 'stage2_min_throughput', S2, extra, c['overlap_threshold_MW'])
    print(json.dumps({k: m2[k] for k in ('termination', 'shed_MWh', 'storage_simultaneous_MWh', 'storage_throughput_MWh', 'F_bound_ok', 'E_bound_ok')}, indent=1))
    if not ok:
        raise SystemExit(f'stage 2 {st} {term} (outputs kept, NOT accepted)')


def stage2_retry(c, base, reasons, threads):
    g2 = gate(c, reasons, S2)
    if g2[0] != 'retry':
        raise SystemExit('stage-2 retry needs a failed stage-2 attempt in the log')
    o = json.loads((OUT / 'stage1_objective.json').read_text())
    n, info, _ = build_x1(c, base)
    n.optimize.create_model()
    F_expr = n.model.objective.expression
    bounds, shed = add_stage2(n, c, F_expr, o['F_star_USD'], o['E_star_MWh'])
    t0 = datetime.now(timezone.utc).isoformat(timespec='seconds')
    st, term, sec, counted = solve_stage(n, c, S2, threads, g2)
    finish_stage2(n, c, st, term, sec, counted, t0, info, bounds, o['F_star_USD'], o['E_star_MWh'], shed, 'rebuilt from saved F*, E* (stage 1 not re-solved)')


def dry(c, base, reasons):
    n, info, audit = build_x1(c, base)
    n.optimize.create_model()
    var = C1.assert_no_build_variables(n)
    F_expr = n.model.objective.expression
    bounds, shed = add_stage2(n, c, F_expr, 1.0e10, 7.0e4)        # placeholders: structure check only
    rep = dict(gate_reasons=reasons, network=info, lines_restored=list(audit.index[audit.impedance_restored]),
               capacity_identical=bool((audit.s_nom_X1 == audit.s_nom_calibrated).all()), linopy_variables=var,
               stage2_constraints=[k for k in n.model.constraints if k.startswith('X1S2-')], stage2_objective_terms=int(n.model.objective.expression.nterm),
               shed_generators=len(shed), solver_calls=0, env=env_info(c))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'C1_X1_DRY_CHECK.json').write_text(json.dumps(rep, indent=1, default=str))
    audit.to_csv(OUT / 'C1_X1_LINE_INPUT_AUDIT.csv', lineterminator='\n', float_format='%.6f')
    print(json.dumps({k: v for k, v in rep.items() if k != 'network'}, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--dry', action='store_true'); g.add_argument('--run', action='store_true'); g.add_argument('--stage2-retry', action='store_true')
    ap.add_argument('--threads', type=int, default=20)
    a = ap.parse_args()
    c, base, reasons = load_cfg()
    if a.dry:
        dry(c, base, reasons)
    elif a.run:
        run(c, base, reasons, a.threads)
    else:
        stage2_retry(c, base, reasons, a.threads)


if __name__ == '__main__':
    main()
