#!/usr/bin/env python3
"""BYOP calibration close-out v1.6 (2026-10-22): the two annual LPs of the common 2025 baseline, run on L2 from workflow/:
    python byop/run/baseline_v16_calibration.py --dry      # build the v1.6 raw network + input tables, LP2 model + checks, NO solve
    python byop/run/baseline_v16_calibration.py --lp1      # builder v1.6 + minimum thermal uplift LP (writes the new baseline)
    python byop/run/baseline_v16_calibration.py --lp2      # reload the saved prepared.nc, fixed-asset annual LP, acceptance QA
Config: config/config.byop_baseline_v16_calibration.yaml (own authorisation; the formal mainline gate is untouched).

LP1 = build_2025_baseline_tamu.py main() (v1.6 defaults): revised fleet, monthly switchable caps, fixed pre-calibration x / r,
      unchanged uplift objective and prices; s_nom = full LP solution, x / r not scaled.
LP2 = the saved baseline_2025_tamu_prepared.nc re-read from disk; identity checks against LP1 (x / r == raw_uncalibrated.nc,
      s_nom == LP1 s_nom_opt, switchable p_max_pu present) BEFORE the solve; C1 fixed-asset rules (2025 fleet, every *_nom fixed
      and asserted on the linopy variables, global constraints dropped, annual cyclic storage, shed per load bus at VOLL).
Both must be status ok + termination optimal. Every call is logged in BASELINE_V16_SOLVE_LOG.csv; zero retries: a stage with
any logged attempt is refused, a failure returns BLOCKED with the outputs kept.
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
sys.path.insert(0, str(WF / 'byop/build'))
sys.path.insert(0, str(WF / 'byop/run'))
import byop_paths as BP  # noqa: E402

CFG_PATH = WF / 'config/config.byop_baseline_v16_calibration.yaml'
STAGES = ['LP1_MIN_THERMAL_UPLIFT', 'LP2_RELOADED_FIXED_ASSET']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_cfg():
    c = yaml.safe_load(CFG_PATH.read_text(encoding='utf-8'))['v16']
    src = WF.parent / c['authorization_source']
    reasons = []
    if c.get('authorization') != 'AUTHORIZED_BY_RESEARCHER_WORK_PACKAGE_V1_6':
        reasons.append('authorization string')
    if not src.exists() or sha(src) != c['authorization_source_sha256']:
        reasons.append('authorization source missing or changed')
    if list(c['stages']) != STAGES or int(c['max_retries']) != 0 or int(c['max_lp_calls']) != 2:
        reasons.append('stage list / budget differs from the package')
    return c, reasons


def out_dir(c):
    return WF / c['out_dir']


def solve_log(c):
    p = out_dir(c) / 'BASELINE_V16_SOLVE_LOG.csv'
    return p, (pd.read_csv(p) if p.exists() else pd.DataFrame(columns=['timestamp_utc', 'stage', 'attempt', 'counted_as', 'status',
                                                                       'termination', 'seconds', 'note']))


def gate(c, reasons, stage):
    if reasons:
        raise SystemExit(f'v1.6 gate REFUSED: {reasons}')
    _, lg = solve_log(c)
    if (lg.stage == stage).any():
        raise SystemExit(f'v1.6 gate REFUSED: {stage} already has a logged call (zero retries)')
    if len(lg) >= int(c['max_lp_calls']):
        raise SystemExit('v1.6 gate REFUSED: LP budget used')
    if stage == STAGES[1]:
        ok = lg[(lg.stage == STAGES[0]) & (lg.status == 'ok') & (lg.termination == 'optimal')]
        if ok.empty:
            raise SystemExit('v1.6 gate REFUSED: LP2 needs an optimal LP1')


def log_call(c, stage, status, term, sec, note=''):
    p, lg = solve_log(c)
    lg = pd.concat([lg, pd.DataFrame([dict(timestamp_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), stage=stage,
                                           attempt=int((lg.stage == stage).sum()) + 1, counted_as='effective', status=status,
                                           termination=term, seconds=round(sec, 1), note=note)])], ignore_index=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    lg.to_csv(p, index=False, lineterminator='\n')


def shed_stats(shed, w, c, label):
    """shed (snapshot x bus, MW), weights (h); acceptance vs the package proxy tolerances"""
    tot = shed.sum(axis=1)
    eens = float((tot * w.values).sum())
    a = c['acceptance']
    ev = []
    for b in shed.columns:
        x = shed[b].values > 1e-3
        i = 0
        while i < len(x):
            if x[i]:
                j = i
                while j + 1 < len(x) and x[j + 1]:
                    j += 1
                seg = shed[b].iloc[i:j + 1]
                ev.append(dict(stage=label, bus=b, start=str(seg.index[0][1] if isinstance(seg.index[0], tuple) else seg.index[0]),
                               steps=j - i + 1, duration_h=float(w.iloc[i:j + 1].sum()), energy_MWh=float((seg * w.iloc[i:j + 1].values).sum()),
                               peak_MW=float(seg.max())))
                i = j + 1
            else:
                i += 1
    k = int(np.argmax(tot.values)) if len(tot) else 0
    m = dict(eens_MWh=eens, eens_over_annual_energy=eens / a['annual_energy_MWh'], max_gap_MW=float(tot.max()),
             max_gap_over_official_peak=float(tot.max()) / a['official_hourly_peak_MW'], shed_steps=int((tot > 1e-3).sum()),
             shed_hours=float(w[tot.values > 1e-3].sum()), shed_buses=sorted(shed.columns[(shed.max() > 1e-3).values].tolist()),
             max_gap_step=str(shed.index[k]), max_gap_bus_split={b: float(v) for b, v in shed.iloc[k].items() if v > 1e-3},
             events=len(ev), thresholds=dict(eens_over_annual_energy_max=a['eens_over_annual_energy_max'],
                                             max_gap_over_official_peak_max=a['max_gap_over_official_peak_max']))
    m['eens_pass'] = m['eens_over_annual_energy'] <= a['eens_over_annual_energy_max']
    m['max_gap_pass'] = m['max_gap_over_official_peak'] <= a['max_gap_over_official_peak_max']
    m['description'] = 'research-proxy tolerance, not an ERCOT standard; below-threshold shed is NOT zero shed'
    return m, pd.DataFrame(ev)


# ------------------------------------------------------------------------------------------------ LP1
def builder_argv(c, threads, extra=()):
    return ['--clusters', c['clusters'], '--interface-rule', c['interface_rule'], '--threads', str(threads),
            '--out-dir', str(out_dir(c)), *extra]


def lp1(c, reasons, threads):
    gate(c, reasons, STAGES[0])
    import build_2025_baseline_tamu as B
    d = out_dir(c)
    if (d / 'baseline_2025_tamu_prepared.nc').exists():
        raise SystemExit(f'{d} already holds a prepared baseline (never overwritten)')
    det = {}
    t = time.time()
    try:
        audit = B.main(builder_argv(c, threads), lp_detail=det)
    except Exception as e:                                         # logged, never retried
        log_call(c, STAGES[0], det.get('status', 'error'), det.get('termination', repr(e)[:160]), det.get('seconds', time.time() - t),
                 'builder / LP1 exception')
        raise
    st, term = det.get('status'), det.get('termination')
    log_call(c, STAGES[0], st, term, det.get('seconds', 0.0), f'builder total {time.time() - t:.0f}s')
    m, ev = shed_stats(det['shed'], det['weights'], c, STAGES[0])
    pd.DataFrame(dict(s_nom_input=det['s_nom_input'], s_nom_opt=det['s_nom_opt'])).to_csv(d / 'LP1_LINE_SOLUTION.csv', lineterminator='\n')
    det['shed'].to_csv(d / 'LP1_shed_by_bus.csv.gz')
    ev.to_csv(d / 'LP1_shedding_events.csv', index=False, lineterminator='\n')
    rep = dict(stage=STAGES[0], status=st, termination=term, seconds=det.get('seconds'), objective_USD=det.get('objective'),
               solver_options=det.get('solver_options'), n_vars=det.get('n_vars'), n_cons=det.get('n_cons'),
               linopy_variables=det.get('linopy_variables'), shed=m, calibration=audit['calibration'],
               baseline=audit['output'], baseline_sha256=audit['output_sha256'], raw_uncalibrated_sha256=audit['raw_uncalibrated_sha256'],
               builder_sha256=sha(B.__file__), assets_module_sha256=sha(WF / 'byop/build/baseline_v16_assets.py'),
               config_sha256=sha(CFG_PATH), runner_sha256=sha(__file__))
    (d / 'LP1_METRICS.json').write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k != 'linopy_variables'}, indent=1, default=str))
    if not (st == 'ok' and term == 'optimal'):
        raise SystemExit(f'LP1 {st} {term}: BLOCKED (outputs kept, no retry)')


# ------------------------------------------------------------------------------------------------ LP2
def prepare_fixed(c, path):
    """C1 fixed-asset rules on the reloaded file (same as c1_fixed_asset_diagnostics.prepare)"""
    import pypsa
    n = pypsa.Network(str(path))
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
    n.add('Generator', [f'{b} V16 shed' for b in buses], bus=buses, carrier='load_shed', p_nom=1e5, marginal_cost=float(c['voll_USD_MWh']))
    assert not n.generators.p_nom_extendable.any() and not n.storage_units.p_nom_extendable.any()
    assert not n.lines.s_nom_extendable.any() and (len(n.links) == 0 or not n.links.p_nom_extendable.any())
    assert len(n.stores) == 0
    return n, dict(removed_global_constraints=gcs, generators=int(len(n.generators)), storage_units=int(len(n.storage_units)),
                   lines=int(len(n.lines)), storage_MW=round(float(n.storage_units.p_nom.sum()), 1),
                   fleet_MW_by_carrier={k: round(float(v), 1) for k, v in n.generators[n.generators.carrier != 'load_shed'].groupby('carrier').p_nom.sum().items()})


def identity_checks(c, lp1_solution=True):
    """saved network vs its references, read from disk: x / r == raw_uncalibrated, s_nom == LP1 s_nom_opt, caps present"""
    import pypsa
    d = out_dir(c)
    raw = pypsa.Network(str(d / 'baseline_2025_tamu_raw_uncalibrated.nc'))
    fin = pypsa.Network(str(d / 'baseline_2025_tamu_prepared.nc')) if lp1_solution else raw
    q = dict(lines_same_index=bool(raw.lines.index.equals(fin.lines.index)))
    q['x_max_abs_diff'] = float((fin.lines.x - raw.lines.x).abs().max())
    q['r_max_abs_diff'] = float((fin.lines.r - raw.lines.r).abs().max())
    q['xr_identical_to_raw_uncalibrated'] = bool(np.array_equal(fin.lines.x.values, raw.lines.x.values) and np.array_equal(fin.lines.r.values, raw.lines.r.values))
    if lp1_solution:
        sol = pd.read_csv(d / 'LP1_LINE_SOLUTION.csv', index_col=0)
        exp = np.maximum(sol.s_nom_opt, sol.s_nom_input).reindex(fin.lines.index)
        q['s_nom_max_abs_diff_vs_LP1_solution'] = float((fin.lines.s_nom - exp).abs().max())
        q['s_nom_equals_LP1_solution'] = bool(q['s_nom_max_abs_diff_vs_LP1_solution'] <= 1e-6)
        q['lines_uplifted'] = int((fin.lines.s_nom - raw.lines.s_nom > 0).sum())
        q['lines_uplifted_le_0p5MVA_kept_in_network'] = int(((fin.lines.s_nom - raw.lines.s_nom) > 0).sum() - ((fin.lines.s_nom - raw.lines.s_nom) > 0.5).sum())
        q['total_uplift_MVA'] = float((fin.lines.s_nom - raw.lines.s_nom).sum())
        q['s_nom_input_equals_raw'] = bool(np.allclose(sol.s_nom_input.reindex(raw.lines.index).values, raw.lines.s_nom.values))
    qa = pd.read_csv(d / 'SWITCHABLE_CAP_QA.csv')
    import baseline_v16_assets as A16
    months = A16.month_of_3h_steps(pd.read_csv(BP.ANCHOR2025_DERIVED / 'ERCOT_NATIVE_LOAD_2025_1H.csv', usecols=['Hour Ending']))
    caps = {}
    for gname, grp in qa.groupby('generator'):
        pm = fin.get_switchable_as_dense('Generator', 'p_max_pu')[gname].values
        pn = float(fin.generators.p_nom[gname])
        cap_t = grp.set_index('month').applied_cap_MW.reindex(months).values
        caps[gname] = dict(dispatch_bound_max_abs_diff_MW=float(np.abs(pm * pn - cap_t).max()),
                           erm_rhs_credit_max_abs_diff_MW=float(np.abs(pm * pn - cap_t).max()), p_nom=pn,
                           time_varying=bool(gname in fin.generators_t.p_max_pu.columns))
    q['switchable_caps'] = caps
    q['switchable_caps_present'] = bool(caps and all(v['time_varying'] and v['dispatch_bound_max_abs_diff_MW'] < 1e-6 for v in caps.values()))
    return q


def metrics_lp2(n, c):
    from c1_fixed_asset_diagnostics import metrics
    m, ev, bl, gen = metrics(n, STAGES[1], 'ANNUAL_3H')
    g = n.generators
    shed_c = g.index[g.carrier == 'load_shed']
    shed = n.generators_t.p[shed_c].copy(); shed.columns = g.bus[shed_c].values
    acc, ev2 = shed_stats(shed, n.snapshot_weightings.generators, c, STAGES[1])
    return m, acc, ev2, bl, gen, shed


def lp2(c, reasons, threads):
    gate(c, reasons, STAGES[1])
    d = out_dir(c)
    ident = identity_checks(c)
    if not (ident['xr_identical_to_raw_uncalibrated'] and ident['s_nom_equals_LP1_solution'] and ident['switchable_caps_present']):
        raise SystemExit(f'LP2 refused before the solve: identity check failed {ident}')
    path = d / 'baseline_2025_tamu_prepared.nc'
    n, info = prepare_fixed(c, path)
    n.optimize.create_model()
    from c1_fixed_asset_diagnostics import assert_no_build_variables
    var_names = assert_no_build_variables(n)
    opts = dict(c['solver_options'], Threads=int(threads))
    t = time.time()
    try:
        st, term = n.optimize.solve_model(solver_name=c['solver'], solver_options=opts)
    except Exception as e:
        log_call(c, STAGES[1], 'error', repr(e)[:160], time.time() - t)
        raise
    sec = time.time() - t
    st, term = str(st), str(term)
    log_call(c, STAGES[1], st, term, sec)
    ok = st == 'ok' and term == 'optimal'
    m, acc, ev, bl, gen, shed = metrics_lp2(n, c)
    lp1m = json.loads((d / 'LP1_METRICS.json').read_text())
    passed = ok and acc['eens_pass'] and acc['max_gap_pass'] and lp1m['termination'] == 'optimal'
    su = n.storage_units
    qa = dict(stage=STAGES[1], status=st, termination=term, seconds=round(sec, 1), solver_options=opts, threads=int(threads),
              network=str(path.relative_to(WF)), network_sha256=sha(path), reloaded_from_disk=True, identity=ident, prepare=info,
              linopy_variables=var_names, n_vars=int(n.model.nvars), n_cons=int(n.model.ncons), metrics=m, acceptance=acc,
              storage=dict(throughput_MWh=m['storage_dispatch_MWh'], charge_MWh=m['storage_charge_MWh'],
                           simultaneous_MWh=m['storage_simultaneous_MWh'], simultaneous_steps=m['storage_simultaneous_steps'],
                           note='v1.5 accepted: simultaneous charge/discharge is mostly LP degeneracy; no further storage objective'),
              lp1=dict(termination=lp1m['termination'], shed=lp1m['shed'], uplift=lp1m['calibration']),
              calls=dict(lp_stages=2, actual_calls=int(len(solve_log(c)[1])), retries=0),
              result='PASS' if passed else 'BLOCKED', config_sha256=sha(CFG_PATH), runner_sha256=sha(__file__))
    (d / 'BASELINE_V16_FIXED_ASSET_QA.json').write_text(json.dumps(qa, indent=1, default=str))
    ev.to_csv(d / 'LP2_shedding_events.csv', index=False, lineterminator='\n')
    bl.to_csv(d / 'LP2_lines.csv', index=False, lineterminator='\n')
    gen.to_csv(d / 'LP2_generation_by_carrier.csv', index=False, lineterminator='\n')
    shed.to_csv(d / 'LP2_shed_by_bus.csv.gz')
    n.lines_t.p0.round(2).to_csv(d / 'LP2_line_flow_p0.csv.gz')
    n.storage_units_t.state_of_charge.round(2).to_csv(d / 'LP2_storage_soc.csv.gz')
    sw = [x for x in n.generators.index if any(k in x for k in ('Kiamichi', 'Tenaska Gateway'))]
    n.generators_t.p[sw].round(3).to_csv(d / 'LP2_switchable_dispatch.csv.gz')
    print(json.dumps({k: v for k, v in qa.items() if k not in ('linopy_variables',)}, indent=1, default=str))
    if not ok:
        raise SystemExit(f'LP2 {st} {term}: BLOCKED (outputs kept, no retry)')


# ------------------------------------------------------------------------------------------------ dry
def dry(c, reasons, threads):
    """v1.6 builder up to the raw network (separate _dry directory), identity + caps checks, LP2-style model creation; no solve"""
    import build_2025_baseline_tamu as B
    dd = out_dir(c) / '_dry'
    r = B.main(['--clusters', c['clusters'], '--interface-rule', c['interface_rule'], '--threads', str(threads), '--out-dir', str(dd),
                '--stop-before-calibration'])
    cc = dict(c, out_dir=str((dd).relative_to(WF)))
    rep = dict(gate_reasons=reasons, raw=r, identity_raw=identity_checks(cc, lp1_solution=False))
    n, info = prepare_fixed(c, dd / 'baseline_2025_tamu_raw_uncalibrated.nc')
    n.optimize.create_model()
    from c1_fixed_asset_diagnostics import assert_no_build_variables
    rep.update(prepare=info, linopy_variables=assert_no_build_variables(n), n_vars=int(n.model.nvars), n_cons=int(n.model.ncons), solver_calls=0)
    (dd / 'V16_DRY_CHECK.json').write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps(rep, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--lp1', action='store_true'); ap.add_argument('--lp2', action='store_true')
    ap.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 16)))
    a = ap.parse_args()
    c, reasons = load_cfg()
    if a.dry:
        dry(c, reasons, a.threads)
    elif a.lp1:
        lp1(c, reasons, a.threads)
    elif a.lp2:
        lp2(c, reasons, a.threads)


if __name__ == '__main__':
    main()
