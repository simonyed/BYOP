#!/usr/bin/env python3
"""NEXT-08 A4: lossy 2025 LP1 calibration -> candidate baseline -> fixed-asset lossy LP2 check (transmission_losses = 2, the
S0-S3 basis). Separate from the consumed v1.6 runner / ledger and from the NEXT-07 W6 lossy LP2 runner; nothing frozen is
overwritten (the candidate is a NEW NetCDF in results/BYOP/next08_lossy_lp1/). Run on L2 from workflow/:
    python byop/run/loss_basis_lp1.py --build                          # LP1 (iteration 1) and LP2 models built + checked, NO solve
    python byop/run/loss_basis_lp1.py --stage LP1_LOSSY_IT1            # GATED (config.byop_lossy_lp1.yaml)
    python byop/run/loss_basis_lp1.py --stage LP1_LOSSY_IT2            # GATED; only if IT1 is optimal and NOT r-converged
    python byop/run/loss_basis_lp1.py --stage LP2_LOSSY_CANDIDATE      # GATED; only after an optimal, r-converged LP1 whose
                                                                        # pre-registered expansion guards all pass
LP1 = the v1.6 LP1 (build_2025_baseline_tamu.calibrate_2025) on the same raw network, fleet, load, objective and prices
(UPLIFT_COST 2e6 USD per MVA of s_nom, SHED_COST 1e6 USD/MWh, every line extendable from its raw s_nom), with ONLY these changes:
  1  transmission_losses = 2 (PyPSA tangents; rating row |s| + loss <= s_max_pu s_nom)
  2  s_nom_max = CAP_FACTOR x v1.6 prepared s_nom (finite: required by the PyPSA loss formulation, whose tangents sit at 1/2 and 1 x
     s_max_pu s_nom_max - i.e. exactly at the v1.6 rating - and the per-line over-expansion guard)
  3  r = r_raw x s_nom_raw / s_ref (equivalent parallel-circuit resistance proxy, fixed inside each LP): s_ref = v1.6 prepared s_nom in
     iteration 1, the iteration-1 solution in iteration 2. x stays raw (researcher-approved X1 flow split). Never r x s_nom in one LP.
Convergence after an LP1: max over lines |r_used / r_implied(s_opt) - 1| <= R_TOL (r_implied = r_raw s_raw / s_opt) or the line's
|s_opt - s_ref| <= S_TOL_MVA. Not converged after IT2 -> STOP (no LP2). Guards (on the converged LP1, before any LP2):
  G1 total uplift over raw <= G1_FACTOR x v1.6 total uplift; G2 no line at its s_nom_max; G3 uplift on lines NOT uplifted in v1.6 <=
  G3_MAX_MVA in total (each such line > 50 MVA is listed for evidence review). LP2 acceptance = the unchanged v1.6 tolerances."""
from __future__ import annotations

import argparse, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/build')); sys.path.insert(0, str(WF / 'byop/run'))
import baseline_v16_calibration as V16  # noqa: E402
import loss_basis_lp2 as LB  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402
import post_v16_gate as G  # noqa: E402

CFG = WF / 'config/config.byop_lossy_lp1.yaml'
STAGES = ['LP1_LOSSY_IT1', 'LP1_LOSSY_IT2', 'LP2_LOSSY_CANDIDATE']
LOG_COLS = ['attempt_id', 'stage', 'state', 'started_utc', 'finished_utc', 'status', 'termination', 'seconds', 'r_converged', 'guards_pass',
            'acceptance_pass', 'note']
UPLIFT_COST, SHED_COST = 2e6, 1e6          # build_2025_baseline_tamu.py (unchanged v1.6 calibration prices)
CANDIDATE_NC = 'baseline_2025_tamu_lossy_candidate.nc'


def load(cfg_path=CFG):
    return yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))['post_v16']


def out_dir(c):
    return WF / c['out_dir']


def ledger(c):
    p = out_dir(c) / 'LOSSY_LP1_SOLVE_LOG.csv'
    return p, (pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame(columns=LOG_COLS))


def v16_files():
    v, _ = V16.load_cfg()
    d = V16.out_dir(v)
    return v, d / 'baseline_2025_tamu_raw_uncalibrated.nc', d / 'baseline_2025_tamu_prepared.nc'


# ------------------------------------------------------------------------------------------------ gate
def check(stage, cfg_path=CFG, git_fn=LB.git):
    """fail-closed; never touches a solver. Reuses the W6 approval / SHA / manifest checks, then this chain's stage rules."""
    c = load(cfg_path)
    r, head, asha = LB.common_checks(c, cfg_path, git_fn)          # approval, SHA, clean tree, source, manifest, v1.6 baseline
    rb = ROOT / c['raw_baseline']['path']
    if not rb.exists() or A2G.file_shas(rb)['raw'] != c['raw_baseline']['sha256']:
        r.append('v1.6 raw (pre-calibration) baseline missing or SHA differs')
    if stage not in STAGES or stage not in c['stages']:
        r.append(f'stage {stage} not in {c["stages"]}')
    _, lg = ledger(c)
    if (lg.stage == stage).any():
        r.append(f'{stage} already has a logged call (zero retries)')
    if len(lg) >= int(c['max_lp_calls']):
        r.append('LP budget used')
    done = lambda s: lg[(lg.stage == s) & (lg.state == 'DONE') & (lg.termination == 'optimal')]
    if stage == 'LP1_LOSSY_IT2':
        if not (done('LP1_LOSSY_IT1').r_converged == 'False').any():
            r.append('LP1_LOSSY_IT2 only after an optimal LP1_LOSSY_IT1 that is NOT r-converged')
    if stage == 'LP2_LOSSY_CANDIDATE':
        last = pd.concat([done('LP1_LOSSY_IT1'), done('LP1_LOSSY_IT2')])
        ok = last[(last.r_converged == 'True') & (last.guards_pass == 'True')]
        if ok.empty:
            r.append('LP2_LOSSY_CANDIDATE only after an optimal, r-converged LP1 whose expansion guards all pass')
        if not (out_dir(c) / CANDIDATE_NC).exists():
            r.append(f'candidate network {CANDIDATE_NC} missing')
    return dict(approved=not r, reasons=r, head=head, approved_git_sha=asha or None, stage=stage)


# ------------------------------------------------------------------------------------------------ model pieces (pure)
def r_proxy(r_raw, s_raw, s_ref):
    """equivalent parallel-circuit resistance proxy: r scales with raw / reference capacity (never above raw)"""
    return r_raw * (s_raw / s_ref).clip(upper=1.0)


def prepare_lp1(raw_nc, s_ref, cap_factor, s_prep):
    """the v1.6 LP1 network (calibrate_2025 statement by statement) + the lossy-basis changes 2 and 3 of the module docstring"""
    import pypsa
    c = pypsa.Network(str(raw_nc))
    g = c.generators
    c.remove('Generator', g.index[g.p_nom_extendable | (g.build_year > 2025)])
    s = c.storage_units
    c.remove('StorageUnit', s.index[s.p_nom_extendable | (s.build_year > 2025)])
    for df in (c.generators, c.storage_units, c.lines):
        df['lifetime'] = np.inf; df['build_year'] = 0
    if len(c.global_constraints):
        c.remove('GlobalConstraint', c.global_constraints.index)
    if 'load_shed' not in c.carriers.index:
        c.add('Carrier', 'load_shed')
    buses = sorted(set(c.loads.bus))
    c.add('Generator', [f'{b} shed' for b in buses], bus=buses, carrier='load_shed', p_nom=1e5, marginal_cost=SHED_COST)
    s_raw = c.lines.s_nom.copy(); r_raw = c.lines.r.copy()
    c.lines['s_nom_min'] = c.lines.s_nom
    c.lines['s_nom_extendable'] = True
    c.lines['s_nom_max'] = cap_factor * s_prep.reindex(c.lines.index)
    c.lines['capital_cost'] = UPLIFT_COST
    c.lines['r'] = r_proxy(r_raw, s_raw, s_ref.reindex(c.lines.index))
    return c, dict(s_raw=s_raw, r_raw=r_raw, buses=buses)


def convergence(s_opt, s_ref, s_raw, r_tol, s_tol):
    r_used = (s_raw / s_ref).clip(upper=1.0); r_impl = (s_raw / s_opt).clip(upper=1.0)
    rel = (r_used / r_impl - 1.0).abs()
    ok_line = (rel <= r_tol) | ((s_opt - s_ref).abs() <= s_tol)
    worst = rel[~ok_line].sort_values(ascending=False)
    return bool(ok_line.all()), dict(max_rel_r_gap=float(rel.max()), lines_not_converged=int((~ok_line).sum()),
                                     worst={k: round(float(v), 4) for k, v in worst.head(8).items()})


def guards(s_opt, s_raw, s_prep, s_max, g):
    up = (s_opt - s_raw).clip(lower=0.0); up16 = (s_prep - s_raw).clip(lower=0.0)
    v16_set = up16.index[up16 > 0.5]
    new = up[~up.index.isin(v16_set) & (up > 0.5)]
    at_cap = up.index[(s_max - s_opt) <= 1e-3 * s_max]
    res = dict(total_uplift_MVA=float(up.sum()), v16_total_uplift_MVA=float(up16.sum()), G1_limit_MVA=float(g['G1_factor'] * up16.sum()),
               G1=bool(up.sum() <= g['G1_factor'] * up16.sum() + 1e-6), lines_at_cap=list(at_cap), G2=len(at_cap) == 0,
               new_lines_uplift_MVA=float(new.sum()), new_lines=new.round(1).to_dict(), new_lines_over_50MVA=list(new.index[new > 50]),
               G3=bool(new.sum() <= g['G3_max_MVA'] + 1e-6), uplifted_lines=int((up > 0.5).sum()))
    res['all_pass'] = res['G1'] and res['G2'] and res['G3']
    return res


def candidate_network(raw_nc, s_final):
    """the candidate baseline: v1.6 raw network with s_nom = s_final and r = parallel proxy at s_final (x raw, nothing else changed)"""
    import pypsa
    n = pypsa.Network(str(raw_nc))
    s_raw, r_raw = n.lines.s_nom.copy(), n.lines.r.copy()
    sf = s_final.reindex(n.lines.index)
    n.lines['s_nom'] = np.maximum(sf, s_raw)
    n.lines['r'] = r_proxy(r_raw, s_raw, n.lines.s_nom)
    return n


def apply_reference_tangents(n, s_ref, cap):
    """NEXT-08b: PyPSA places the two loss tangents at 1/2 and 1 x s_max_pu x s_nom_max of each line. The model is created with
    s_nom_max = s_ref (the iteration's reference capacity), so the tangents are exactly the ones a fixed-capacity LP2 / S0-S3 model
    of that capacity uses; afterwards the capacity row (Line-ext-s_nom-upper) and the loss upper bound (Line-loss_upper) are reset
    to the guard cap, so the feasible capacity range is unchanged. Purely parameter changes of existing rows: the model stays an LP
    with the same size. Returns the per-line reference used."""
    m = n.model
    up = m.constraints['Line-ext-s_nom-upper']
    names = list(up.rhs.coords['name'].values)
    up.update(rhs=up.rhs.copy(data=np.asarray(cap.reindex(names).values, dtype=float)))
    import xarray as xr
    lu = m.constraints['Line-loss_upper']
    lnames = list(lu.rhs.coords['name'].values)
    scale = ((cap.reindex(lnames) / s_ref.reindex(lnames)) ** 2).values
    lu.update(rhs=lu.rhs * xr.DataArray(scale, coords={'name': lnames}, dims='name'))   # r (s_max_pu cap)^2 = r (s_max_pu s_ref)^2 x scale
    n.lines['s_nom_max'] = cap.reindex(n.lines.index)
    return s_ref.reindex(names)


def tangent_rows_vs_reference(n, s_ref, segments=2):
    """static proof: every Line-loss_tangents row of the built model has slope 2 r_pu p_k and offset -r_pu p_k^2 with
    p_k = k / segments x s_max_pu x s_ref (the fixed-capacity LP2 / S0-S3 rows of that capacity); returns max abs deviations"""
    m = n.model
    r_pu = n.lines.r / n.buses.v_nom.reindex(n.lines.bus0).values ** 2
    slabels = np.asarray(m.variables['Line-s'].labels.values).ravel()
    out = {}
    for k in range(1, segments + 1):
        for sign in (-1, 1):
            c = m.constraints[f'Line-loss_tangents-{k}-{sign}']
            names = list(c.rhs.coords['name'].values)
            pk = k / segments * n.lines.s_max_pu.reindex(names).values * s_ref.reindex(names).values
            rp = r_pu.reindex(names).values
            rhs = np.asarray(c.rhs.transpose(..., 'name').values, dtype=float)
            v = np.asarray(c.vars.transpose(..., 'name', '_term').values); co = np.asarray(c.coeffs.transpose(..., 'name', '_term').values, dtype=float)
            slope = np.where(np.isin(v, slabels), co, 0.0).sum(axis=-1)
            out[f'{k}{"+" if sign > 0 else "-"}'] = dict(offset_max_abs_dev=float(np.nanmax(np.abs(rhs - (-rp * pk ** 2)))),
                                                         slope_max_abs_dev=float(np.nanmax(np.abs(slope - sign * 2 * rp * pk))))
    return out


def build_lp1(stage, c):
    v, raw_nc, prep_nc = v16_files()
    import pypsa
    s_prep = pypsa.Network(str(prep_nc)).lines.s_nom
    if stage == 'LP1_LOSSY_IT1':
        s_ref = s_prep.copy()
    else:
        s_ref = pd.read_csv(out_dir(c) / 'LP1_LOSSY_IT1' / 'LP1_LINE_SOLUTION.csv', index_col=0).s_nom_opt
    n, info = build_lp1_from(raw_nc, s_prep, s_ref, c)
    return n, dict(info, raw_nc=raw_nc), v


def build_lp1_from(raw_nc, s_prep, s_ref, c):
    """the LP1 model from explicit inputs (used by build_lp1 and by the static tests on small networks)"""
    n, info = prepare_lp1(raw_nc, s_ref, float(c['cap_factor']), s_prep)
    tangent_ref = c.get('loss_tangent_reference', 'cap')          # v1 (NEXT-08): 'cap'; v2 (NEXT-08b): 's_ref'
    if tangent_ref == 's_ref':
        cap = n.lines.s_nom_max.copy()
        n.lines['s_nom_max'] = s_ref.reindex(n.lines.index)
        n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
        apply_reference_tangents(n, s_ref.reindex(n.lines.index), cap)
    elif tangent_ref == 'cap':
        n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
    else:
        raise ValueError(f'loss_tangent_reference {tangent_ref!r} not in (cap, s_ref)')
    return n, dict(info, s_ref=s_ref, s_prep=s_prep, tangent_reference=tangent_ref)


def build_lp2(stage, c):
    v, _, _ = v16_files()
    n, info = V16.prepare_fixed(v, out_dir(c) / CANDIDATE_NC)
    n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
    return n, info, None, v


# ------------------------------------------------------------------------------------------------ run
def run(stage, threads, cfg_path=CFG, gate_fn=None, lp1_build=None, lp2_build=None):
    c = load(cfg_path)
    g = (gate_fn or (lambda s_: check(s_, cfg_path)))(stage)
    if not g['approved']:
        print(json.dumps(dict(LOSSY_LP1_GATE='REFUSED', **g), indent=1)); raise SystemExit(3)
    if stage == 'LP2_LOSSY_CANDIDATE':
        # the W6 runner's run/postprocess with this chain's config, ledger and candidate network
        return LB.run(stage, threads, cfg_path=cfg_path, gate_fn=lambda s_: g, build_fn=lp2_build or build_lp2,
                      ledger_fn=lambda c_: ledger(c_), log_cols=LOG_COLS)
    n, info, v = (lp1_build or build_lp1)(stage, c)
    p, lg = ledger(c)
    aid = f'{stage}#1'
    row = {k: '' for k in LOG_COLS}; row.update(attempt_id=aid, stage=stage, state='STARTED', started_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    A2G._atomic_write(pd.concat([lg, pd.DataFrame([row])], ignore_index=True)[LOG_COLS], p)

    def finish(**kw):
        _, lg_ = ledger(c)
        i = lg_.index[lg_.attempt_id == aid][0]
        kw.setdefault('finished_utc', datetime.now(timezone.utc).isoformat(timespec='seconds'))
        for k, val in kw.items():
            lg_.loc[i, k] = str(val)
        A2G._atomic_write(lg_[LOG_COLS], p)
    opts = dict(v['solver_options'], Threads=int(threads))
    t = time.time()
    try:
        st, term = n.optimize.solve_model(solver_name=v['solver'], solver_options=opts)
    except BaseException as e:
        finish(state='ERROR', status='exception', seconds=round(time.time() - t, 1), note=f'{e.__class__.__name__}: {e}'[:300])
        raise
    sec = time.time() - t
    st, term = str(st), str(term)
    try:
        qa = postprocess_lp1(n, info, v, c, stage, st, term, sec, g, threads, out_dir(c) / stage)
        finish(state='DONE', status=st, termination=term, seconds=round(sec, 1), r_converged=qa['r_converged'], guards_pass=qa['guards']['all_pass'])
    except BaseException as e:
        finish(state='ERROR', status=st, termination=term, seconds=round(sec, 1), note=f'post-solve: {e.__class__.__name__}: {e}'[:300])
        raise
    if not (st == 'ok' and term == 'optimal'):
        raise SystemExit(f'{stage} {st} {term}: BLOCKED (outputs kept, no retry)')
    return qa


def postprocess_lp1(n, info, v, c, stage, st, term, sec, g, threads, od):
    ok = st == 'ok' and term == 'optimal'
    od.mkdir(parents=True, exist_ok=True)
    s_opt = n.lines.s_nom_opt.copy()
    bad = s_opt.index[~np.isfinite(s_opt) | (s_opt < info['s_raw'].reindex(s_opt.index) - 1e-6)] if ok else []
    if len(bad):                       # fail closed: never derive guards, r or a candidate from an invalid capacity solution
        raise ValueError(f'LP1 capacity solution invalid (non-finite or below raw s_nom) on {list(bad)[:5]}')
    pd.DataFrame(dict(s_nom_input=info['s_raw'], s_nom_opt=s_opt, s_ref=info['s_ref'], s_v16_prepared=info['s_prep'], s_nom_max=n.lines.s_nom_max,
                      r_raw=info['r_raw'], r_used=n.lines.r)).to_csv(od / 'LP1_LINE_SOLUTION.csv')
    sh = n.generators_t.p[[f'{b} shed' for b in info['buses']]].copy(); sh.columns = info['buses']
    acc, ev = V16.shed_stats(sh, n.snapshot_weightings.generators, v, stage)
    loss = LB.line_loss_frame(n)
    w = n.snapshot_weightings.generators
    conv, cinfo = convergence(s_opt, info['s_ref'], info['s_raw'], float(c['r_tol']), float(c['s_tol_MVA']))
    gd = guards(s_opt, info['s_raw'], info['s_prep'], n.lines.s_nom_max, c['guards'])
    up = (s_opt - info['s_raw']).clip(lower=0.0)
    qa = dict(stage=stage, status=st, termination=term, seconds=round(sec, 1), threads=int(threads), n_vars=int(n.model.nvars), n_cons=int(n.model.ncons),
              objective=float(n.objective) if ok else None, residual_shed=acc, r_converged=conv, convergence=cinfo, guards=gd,
              uplift_by_line_MVA={k: round(float(x), 2) for k, x in up[up > 0.5].sort_values(ascending=False).items()},
              total_loss_MWh=float(loss.mul(w.values, axis=0).sum().sum()) if loss is not None else None, gate=g,
              candidate_written=False, label='LOSSY LP1 CALIBRATION (2025 fixed fleet); not a scenario result')
    if ok and conv and gd['all_pass']:
        cand = candidate_network(info['raw_nc'], s_opt)
        cand.export_to_netcdf(str(out_dir(c) / CANDIDATE_NC))
        qa['candidate_written'] = True
        qa['candidate_sha256'] = A2G.file_shas(out_dir(c) / CANDIDATE_NC)['raw']
    (od / 'LOSSY_LP1_QA.json').write_text(json.dumps(qa, indent=1, default=str), encoding='utf-8')
    sh.to_csv(od / 'shed_by_bus.csv.gz'); ev.to_csv(od / 'shedding_events.csv', index=False)
    if loss is not None:
        loss.round(3).to_csv(od / 'line_loss.csv.gz')
    print(json.dumps({k: x for k, x in qa.items() if k != 'gate'}, indent=1, default=str))
    return qa


# ------------------------------------------------------------------------------------------------ static build
def build_only(threads, cfg_path=CFG):
    import linopy
    calls = []
    linopy.Model.solve = lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(RuntimeError('no solver in --build'))
    c = load(cfg_path)
    rep = dict(step='NEXT-08 lossy LP1 static build', config=str(cfg_path), tangent_reference=c.get('loss_tangent_reference', 'cap'),
               solver_calls=0, gate={s: check(s, cfg_path) for s in STAGES})
    n, info, v = build_lp1('LP1_LOSSY_IT1', c)
    m = n.model
    L = n.lines
    rep['LP1_LOSSY_IT1'] = dict(n_vars=int(m.nvars), n_cons=int(m.ncons), has_line_loss='Line-loss' in m.variables, has_line_s_nom='Line-s_nom' in m.variables,
                                loss_rows=sorted(k for k in m.constraints if k.startswith('Line-loss')), lines=int(len(L)),
                                all_lines_extendable=bool(L.s_nom_extendable.all()), s_nom_max_finite=bool(np.isfinite(L.s_nom_max).all()),
                                cap_over_v16_prepared=float((L.s_nom_max / info['s_prep'].reindex(L.index)).max()),
                                s_nom_min_equals_raw=bool(np.allclose(L.s_nom_min, info['s_raw'])), capital_cost_unique=sorted(set(L.capital_cost)),
                                x_equals_raw=None, r_scaled_lines=int((L.r < info['r_raw'] - 1e-12).sum()), r_sum_ohm=float(L.r.sum()),
                                generators=int(len(n.generators)), shed_units=int((n.generators.carrier == 'load_shed').sum()), storage_units=int(len(n.storage_units)),
                                snapshots=int(len(n.snapshots)), committable=int(n.generators.committable.sum()))
    import pypsa
    raw = pypsa.Network(str(info['raw_nc']))
    rep['LP1_LOSSY_IT1']['x_equals_raw'] = bool(np.array_equal(L.x.values, raw.lines.x.reindex(L.index).values))
    tref = info['s_ref'] if info.get('tangent_reference') == 's_ref' else L.s_nom_max
    dev = tangent_rows_vs_reference(n, tref.reindex(L.index))
    m_ = n.model
    cap_rhs = np.asarray(m_.constraints['Line-ext-s_nom-upper'].rhs.values, dtype=float)
    rep['LP1_LOSSY_IT1'].update(tangent_reference=info.get('tangent_reference'), tangent_rows_vs_reference=dev,
                                tangent_rows_match=all(d['offset_max_abs_dev'] < 1e-9 and d['slope_max_abs_dev'] < 1e-12 for d in dev.values()),
                                capacity_row_rhs_equals_cap=bool(np.allclose(cap_rhs, L.s_nom_max.reindex(list(m_.constraints['Line-ext-s_nom-upper'].rhs.coords['name'].values)).values)))
    del n
    cand = candidate_network(info['raw_nc'], info['s_prep'])           # the v1.6 capacities as a stand-in LP1 solution (no file written)
    rep['candidate_from_v16_capacities'] = dict(r_sum_ohm=float(cand.lines.r.sum()), s_nom_sum=float(cand.lines.s_nom.sum()),
                                                x_equals_raw=bool(np.array_equal(cand.lines.x.values, raw.lines.x.values)))
    a = rep['LP1_LOSSY_IT1']
    rep['checks'] = dict(loss_terms=a['has_line_loss'] and len(a['loss_rows']) == 5, capacity_variables=a['has_line_s_nom'],
                         finite_caps=a['s_nom_max_finite'], cap_factor_respected=abs(a['cap_over_v16_prepared'] - float(c['cap_factor'])) < 1e-9,
                         lp1_like_v16=a['all_lines_extendable'] and a['s_nom_min_equals_raw'] and a['capital_cost_unique'] == [UPLIFT_COST],
                         x_unchanged=a['x_equals_raw'], r_scaled_on_v16_uplifted_lines=a['r_scaled_lines'] == 18, no_committable=a['committable'] == 0,
                         tangent_rows_match_reference=a['tangent_rows_match'], capacity_row_is_guard_cap=a['capacity_row_rhs_equals_cap'],
                         no_solver_called=not calls)
    od = out_dir(c); od.mkdir(parents=True, exist_ok=True)
    (od / 'LOSSY_LP1_BUILD.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: x for k, x in rep.items() if k != 'gate'}, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true'); ap.add_argument('--stage', choices=STAGES)
    ap.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 20)))
    ap.add_argument('--config', default=str(CFG), help='gate config (default: the NEXT-08 v1 config; NEXT-08b: config.byop_lossy_lp1_v2.yaml)')
    a = ap.parse_args()
    cfgp = Path(a.config).resolve()
    if a.build:
        build_only(a.threads, cfgp)
    elif a.stage:
        run(a.stage, a.threads, cfg_path=cfgp)
    else:
        ap.error('--build or --stage')


if __name__ == '__main__':
    main()
