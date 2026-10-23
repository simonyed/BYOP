#!/usr/bin/env python3
"""NEXT-07 W6 zero-solver end-to-end test of the lossy LP2 runner on the REAL models: both stages go through loss_basis_lp2.run with
the real build (v1.6 prepared baseline, C1 fixed-asset rules, transmission_losses 2), an injected approved gate and a scratch
config / ledger; linopy.Model.solve is replaced by tests/fake_solve.py and gurobipy.Model.optimize raises, so PyPSA's post-solve
path, the Line-loss reader, metrics, acceptance and every output file run on the real shapes without any solver.
Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n07_lossy_lp2_post.py --out results/BYOP/next07_loss_basis/_zero_solver_post
"""
from __future__ import annotations

import argparse, json, shutil, sys
from pathlib import Path

import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / 'run'))
import linopy  # noqa: E402
import fake_solve as F  # noqa: E402

linopy.Model.solve = F.fake_solve
try:
    import gurobipy
    gurobipy.Model.optimize = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('gurobipy optimize in a zero-solver test'))
except Exception:
    pass
import loss_basis_lp2 as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    raw = yaml.safe_load(L.CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str(out / 'scratch')
    cfgp = out / 'config.byop_loss_basis_lp2.ZERO_SOLVER.yaml'
    cfgp.write_text(yaml.safe_dump(raw), encoding='utf-8')
    rep = dict(step='W6 zero-solver end-to-end post-processing on the real lossy LP2 models', real_solver_calls=0, stages={})
    for st in L.STAGES:
        qa = L.run(st, 4, cfg_path=cfgp, gate_fn=lambda s: dict(approved=True, reasons=['ZERO_SOLVER_TEST_INJECTED_GATE']))
        od = out / 'scratch' / st
        files = sorted(p.name for p in od.iterdir())
        rep['stages'][st] = dict(files=files, n_vars=qa['n_vars'], n_cons=qa['n_cons'], total_loss_MWh=qa['losses']['total_loss_MWh'],
                                 eens_MWh=qa['acceptance']['eens_MWh'], key_lines=sorted(qa['key_lines']), r_changes=len(qa['r_parallel_changes'] or []),
                                 acceptance_pass_flag=qa['acceptance_pass'])
    lg = pd.read_csv(out / 'scratch' / 'LOSS_BASIS_LP2_SOLVE_LOG.csv', dtype=str, keep_default_na=False)
    need = {'LOSS_BASIS_LP2_QA.json', 'shedding_events.csv', 'lines.csv', 'generation_by_carrier.csv', 'shed_by_bus.csv.gz', 'line_flow_p0.csv.gz', 'line_loss.csv.gz'}
    s0, s1 = rep['stages'][L.STAGES[0]], rep['stages'][L.STAGES[1]]
    rep['checks'] = dict(
        fake_solve_called_once_per_stage=len(F.CALLS) == 2,
        all_outputs_written=need <= set(s0['files']) and need | {'R_PARALLEL_CHANGES.csv'} <= set(s1['files']),
        line_loss_read_on_real_shape=s0['total_loss_MWh'] is not None and s0['total_loss_MWh'] > 0,
        key_lines_reported=s0['key_lines'] == sorted(['TL12', 'TL13', 'TL15', 'TL21', 'TL35', 'TL36', 'TL43', 'TL44']),
        r_parallel_18_lines=s1['r_changes'] == 18 and s0['r_changes'] == 0,
        ledger_started_then_done=list(lg.state) == ['DONE', 'DONE'] and list(lg.termination) == ['optimal', 'optimal'],
        real_ledger_untouched=not (L.WF / L.load()['out_dir'] / 'LOSS_BASIS_LP2_SOLVE_LOG.csv').exists())
    rep['verdict'] = 'ZERO_SOLVER_POST_PASS' if all(rep['checks'].values()) else 'ZERO_SOLVER_POST_FAIL'
    rep['fake_solve_calls'] = F.CALLS
    (out / 'W6_ZERO_SOLVER_POST.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
