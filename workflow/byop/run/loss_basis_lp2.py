#!/usr/bin/env python3
"""NEXT-07 W6 (2026-10-23): re-validate the 2025 v1.6 fixed-asset LP2 on the LOSSY basis chosen by the researcher for S0-S3
(transmission_losses = 2, PyPSA tangents, exactly as the mainline). Separate from the consumed v1.6 runner / ledger, which stay
untouched; the lossless LP1 / LP2 results and the NEXT-07 probes are never overwritten. Run on L2 from workflow/:
    python byop/run/loss_basis_lp2.py --build                      # both stage models built, checked and summarised, NO solve
    python byop/run/loss_basis_lp2.py --stage LP2_LOSSY_ASIS       # GATED (config.byop_loss_basis_lp2.yaml), 1 call, 0 retries
    python byop/run/loss_basis_lp2.py --stage LP2_LOSSY_R_PARALLEL # GATED; only after a LOSSY_ASIS that solved optimal and FAILED
                                                                    # the v1.6 acceptance (EENS / max gap) - a candidate repair
Stages (identical C1 fixed-asset rules, inputs, solver options and acceptance tolerances as the v1.6 LP2):
  LP2_LOSSY_ASIS        baseline_2025_tamu_prepared.nc as is (X1: s_nom uplifted on 18 lines, x / r pre-calibration)
  LP2_LOSSY_R_PARALLEL  the same, but r ONLY of the 18 calibration-uplifted lines scaled by raw / prepared s_nom (the builder's own
                        parallel-circuit convention, build_2025_baseline_tamu.py, applied to the resistance only; x unchanged = the
                        researcher-approved X1 flow split; no capacity added anywhere)
No line capacity is changed in either stage. Every call: gate -> STARTED row -> solve -> outputs -> DONE / ERROR row (no retry)."""
from __future__ import annotations

import argparse, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

WF = Path(__file__).resolve().parents[2]
ROOT = WF.parent
sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/build')); sys.path.insert(0, str(WF / 'byop/run'))
import baseline_v16_calibration as V16  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402
import post_v16_gate as G  # noqa: E402

CFG = WF / 'config/config.byop_loss_basis_lp2.yaml'
STAGES = ['LP2_LOSSY_ASIS', 'LP2_LOSSY_R_PARALLEL']
LOG_COLS = ['attempt_id', 'stage', 'state', 'started_utc', 'finished_utc', 'status', 'termination', 'seconds', 'acceptance_pass', 'note']


def load(cfg_path=CFG):
    return yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))['post_v16']


def out_dir(c):
    return WF / c['out_dir']


def ledger(c):
    p = out_dir(c) / 'LOSS_BASIS_LP2_SOLVE_LOG.csv'
    return p, (pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame(columns=LOG_COLS))


def git(*a):
    return subprocess.run(['git', '-C', str(ROOT), *a], capture_output=True, text=True)


def check(stage, cfg_path=CFG, git_fn=git):
    """fail-closed gate; never touches a solver"""
    c = load(cfg_path)
    r = []
    if str(c.get('run_authorization')) != 'APPROVED':
        r.append(f"run_authorization={c.get('run_authorization')}")
    if not c.get('approved_by'):
        r.append('approved_by missing')
    head = git_fn('rev-parse', 'HEAD').stdout.strip()
    asha = str(c.get('approved_git_sha') or '')
    if not asha:
        r.append('approved_git_sha missing')
    elif not head.startswith(asha):
        if git_fn('merge-base', '--is-ancestor', asha, 'HEAD').returncode != 0:
            r.append(f'approved_git_sha {asha} is not HEAD or an ancestor of it')
        else:
            since = set(git_fn('diff', '--name-only', asha, 'HEAD', '--', *G.CLEAN_PATHS).stdout.split()) - {'workflow/config/config.byop_loss_basis_lp2.yaml'}
            if since:
                r.append(f'code / config / inputs changed since the approved commit: {sorted(since)[:5]}')
    dirty = git_fn('diff', '--ignore-cr-at-eol', '--name-only', 'HEAD', '--', *G.CLEAN_PATHS).stdout.split() + \
        git_fn('ls-files', '--others', '--exclude-standard', '--', *G.CLEAN_PATHS).stdout.split()
    if dirty:
        r.append(f'worktree not clean for code / config / inputs: {dirty[:5]}')
    src = ROOT / c['authorization_source']
    if not src.exists() or A2G.file_shas(src)['lf'] != c['authorization_source_sha256']:
        r.append('authorization source missing or changed')
    man_p = ROOT / c['manifest']
    if not man_p.exists():
        r.append(f"manifest missing: {c['manifest']}")
    else:
        man = json.loads(man_p.read_text(encoding='utf-8'))
        r += A2G.manifest_mismatches(man, ROOT)
        if man.get('config_sha256_normalised') != G.config_sha(cfg_path):
            r.append('config differs from the manifest (normalised SHA)')
    base = ROOT / c['baseline']['path']
    if not base.exists() or A2G.file_shas(base)['raw'] != c['baseline']['sha256']:
        r.append('v1.6 prepared baseline missing or SHA differs')
    if stage not in STAGES or stage not in c['stages']:
        r.append(f'stage {stage} not in {c["stages"]}')
    _, lg = ledger(c)
    if (lg.stage == stage).any():
        r.append(f'{stage} already has a logged call (zero retries)')
    if len(lg) >= int(c['max_lp_calls']):
        r.append('LP budget used')
    if stage == STAGES[1]:
        a = lg[lg.stage == STAGES[0]]
        if not ((a.state == 'DONE') & (a.termination == 'optimal') & (a.acceptance_pass == 'False')).any():
            r.append('LP2_LOSSY_R_PARALLEL only after an optimal LP2_LOSSY_ASIS that FAILED the v1.6 acceptance')
    return dict(approved=not r, reasons=r, head=head, approved_git_sha=asha or None, stage=stage)


def r_parallel(n, raw):
    """r of the calibration-uplifted lines x raw / prepared s_nom (x and s_nom unchanged); returns the change table"""
    up = n.lines.s_nom - raw.lines.s_nom.reindex(n.lines.index)
    idx = up.index[up > 0.5]
    ratio = (raw.lines.s_nom.reindex(idx) / n.lines.s_nom[idx])
    t = pd.DataFrame(dict(r_before=n.lines.r[idx], s_nom_raw=raw.lines.s_nom.reindex(idx), s_nom_prepared=n.lines.s_nom[idx], scale=ratio))
    n.lines.loc[idx, 'r'] = n.lines.r[idx] * ratio
    t['r_after'] = n.lines.r[idx]
    t['x_unchanged'] = True
    return t


def build(stage, c):
    import pypsa
    v, _ = V16.load_cfg()
    d16 = V16.out_dir(v)
    n, info = V16.prepare_fixed(v, d16 / 'baseline_2025_tamu_prepared.nc')
    rtab = None
    if stage == STAGES[1]:
        raw = pypsa.Network(str(d16 / 'baseline_2025_tamu_raw_uncalibrated.nc'))
        rtab = r_parallel(n, raw)
    n.optimize.create_model(transmission_losses=int(c['transmission_losses']))
    return n, info, rtab, v


def run(stage, threads):
    c = load()
    g = check(stage)
    if not g['approved']:
        print(json.dumps(dict(LOSS_BASIS_GATE='REFUSED', **g), indent=1)); raise SystemExit(3)
    n, info, rtab, v = build(stage, c)
    from c1_fixed_asset_diagnostics import assert_no_build_variables
    var_names = assert_no_build_variables(n)
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
    ok = st == 'ok' and term == 'optimal'
    od = out_dir(c) / stage; od.mkdir(parents=True, exist_ok=True)
    try:
        m, acc, ev, bl, gen, shed = V16.metrics_lp2(n, v)
        loss = n.model.solution['Line-loss'].to_pandas() if 'Line-loss' in n.model.variables else None
        if loss is not None and isinstance(loss.index, pd.MultiIndex):
            loss.index = loss.index.get_level_values(-1)
        w = n.snapshot_weightings.generators
        losses = dict(total_loss_MWh=float(loss.mul(w.values, axis=0).sum().sum()) if loss is not None else None,
                      loss_share_of_load=float(loss.mul(w.values, axis=0).sum().sum() / v['acceptance']['annual_energy_MWh']) if loss is not None else None,
                      top_lines_MWh={k: float(x) for k, x in loss.mul(w.values, axis=0).sum().sort_values(ascending=False).head(15).items()} if loss is not None else None)
        passed = ok and acc['eens_pass'] and acc['max_gap_pass']
        qa = dict(stage=stage, status=st, termination=term, seconds=round(sec, 1), threads=int(threads), solver_options=opts,
                  transmission_losses=int(c['transmission_losses']), prepare=info, n_vars=int(n.model.nvars), n_cons=int(n.model.ncons),
                  linopy_variables=var_names, metrics=m, acceptance=acc, losses=losses, acceptance_pass=bool(passed),
                  r_parallel_changes=None if rtab is None else rtab.round(6).reset_index().to_dict('records'),
                  baseline_sha256=c['baseline']['sha256'], gate=g, label='LOSS_BASIS_REVALIDATION (2025 fixed assets); not a scenario result')
        (od / 'LOSS_BASIS_LP2_QA.json').write_text(json.dumps(qa, indent=1, default=str), encoding='utf-8')
        ev.to_csv(od / 'shedding_events.csv', index=False); bl.to_csv(od / 'lines.csv', index=False); gen.to_csv(od / 'generation_by_carrier.csv', index=False)
        shed.to_csv(od / 'shed_by_bus.csv.gz'); n.lines_t.p0.round(2).to_csv(od / 'line_flow_p0.csv.gz')
        if loss is not None:
            loss.round(3).to_csv(od / 'line_loss.csv.gz')
        if rtab is not None:
            rtab.to_csv(od / 'R_PARALLEL_CHANGES.csv')
        finish(state='DONE', status=st, termination=term, seconds=round(sec, 1), acceptance_pass=passed)
        print(json.dumps({k: x for k, x in qa.items() if k not in ('linopy_variables', 'r_parallel_changes')}, indent=1, default=str))
    except BaseException as e:
        finish(state='ERROR', status=st, termination=term, seconds=round(sec, 1), note=f'post-solve: {e.__class__.__name__}: {e}'[:300])
        raise
    if not ok:
        raise SystemExit(f'{stage} {st} {term}: BLOCKED (outputs kept, no retry)')


def build_only(threads):
    """both stage models, no solver: sizes, loss rows, r changes, identity of everything else"""
    import linopy
    calls = []
    linopy.Model.solve = lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(RuntimeError('no solver in --build'))
    c = load()
    rep = dict(step='W6 lossy LP2 static build', solver_calls=0, gate={s: check(s) for s in STAGES})
    for s in STAGES:
        n, info, rtab, v = build(s, c)
        m = n.model
        rep[s] = dict(n_vars=int(m.nvars), n_cons=int(m.ncons), has_line_loss='Line-loss' in m.variables,
                      loss_rows=sorted(k for k in m.constraints if k.startswith('Line-loss')), committable=int(n.generators.committable.sum()),
                      lines=int(len(n.lines)), line_capacity_MW=float((n.lines.s_nom * n.lines.s_max_pu).sum()), r_sum_ohm=float(n.lines.r.sum()),
                      x_sum_ohm=float(n.lines.x.sum()), prepare=info,
                      r_changes=None if rtab is None else rtab.round(4).reset_index().to_dict('records'))
    a, b = rep[STAGES[0]], rep[STAGES[1]]
    rep['checks'] = dict(both_have_losses=a['has_line_loss'] and b['has_line_loss'], same_size=(a['n_vars'], a['n_cons']) == (b['n_vars'], b['n_cons']),
                         no_capacity_change=abs(a['line_capacity_MW'] - b['line_capacity_MW']) < 1e-6, x_unchanged=abs(a['x_sum_ohm'] - b['x_sum_ohm']) < 1e-9,
                         r_changed_only_on_uplifted=b['r_changes'] is not None and len(b['r_changes']) == 18, no_committable=a['committable'] == 0,
                         no_solver_called=not calls)
    od = out_dir(c); od.mkdir(parents=True, exist_ok=True)
    (od / 'W6_LOSSY_LP2_BUILD.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: x for k, x in rep.items() if k not in STAGES}, indent=1, default=str))
    print(json.dumps({s: {k: x for k, x in rep[s].items() if k not in ('r_changes', 'prepare')} for s in STAGES}, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true'); ap.add_argument('--stage', choices=STAGES)
    ap.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 16)))
    a = ap.parse_args()
    if a.build:
        build_only(a.threads)
    elif a.stage:
        run(a.stage, a.threads)
    else:
        ap.error('--build or --stage')


if __name__ == '__main__':
    main()
