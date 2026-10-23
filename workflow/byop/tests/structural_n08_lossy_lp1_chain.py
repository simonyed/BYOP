#!/usr/bin/env python3
"""NEXT-08 zero-solver end-to-end test of the lossy LP1 -> candidate -> LP2 chain on the REAL v1.6 networks: every stage goes through
loss_basis_lp1.run with the real builds and the REAL stage-order rules (only the approval / SHA / manifest reasons are dropped, the
config / ledger / candidate live in a scratch directory). linopy.Model.solve = tests/fake_solve.py (capacities at s_nom_min, i.e. no
uplift), gurobipy optimize raises. Expected: IT1 not r-converged (r from v1.6 capacities, 'solution' = raw) -> IT2 converged, guards
pass, candidate written (= raw capacities) -> LP2 on the candidate; all outputs and ledger rows present; frozen files untouched.
Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n08_lossy_lp1_chain.py --out results/BYOP/next08_lossy_lp1/_zero_solver_chain
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
import loss_basis_lp1 as L  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402

DROP = ('run_authorization', 'approved_by', 'approved_git_sha', 'worktree not clean', 'manifest', 'config differs', 'code / config')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    raw = yaml.safe_load(L.CFG.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str(out / 'scratch')
    cfgp = out / 'config.byop_lossy_lp1.ZERO_SOLVER.yaml'
    cfgp.write_text(yaml.safe_dump(raw), encoding='utf-8')
    c = L.load(cfgp)
    frozen = {k: A2G.file_shas(L.ROOT / c[k]['path'])['raw'] for k in ('baseline', 'raw_baseline')}

    def gate(stage):
        g = L.check(stage, cfg_path=cfgp)
        keep = [x for x in g['reasons'] if not x.startswith(DROP)]
        return dict(g, approved=not keep, reasons=keep, dropped_for_test=[x for x in g['reasons'] if x.startswith(DROP)])
    rep = dict(step='NEXT-08 zero-solver lossy LP1 chain on the real v1.6 networks', real_solver_calls=0, stages={}, gate_before={s: gate(s)['reasons'] for s in L.STAGES})
    for st in L.STAGES:
        q = L.run(st, 4, cfg_path=cfgp, gate_fn=gate)
        rep['stages'][st] = {k: q.get(k) for k in ('status', 'termination', 'n_vars', 'n_cons', 'r_converged', 'candidate_written', 'acceptance_pass')}
        rep['stages'][st]['files'] = sorted(p.name for p in (out / 'scratch' / st).iterdir())
        if st != 'LP2_LOSSY_CANDIDATE':
            rep['stages'][st].update(convergence=q['convergence'], guards={k: q['guards'][k] for k in ('G1', 'G2', 'G3', 'all_pass', 'total_uplift_MVA')})
    lg = pd.read_csv(out / 'scratch' / 'LOSSY_LP1_SOLVE_LOG.csv', dtype=str, keep_default_na=False)
    retry = gate('LP1_LOSSY_IT1')
    s1, s2, s3 = (rep['stages'][s] for s in L.STAGES)
    rep['checks'] = dict(
        fake_solve_three_calls=len(F.CALLS) == 3,
        it1_not_converged=s1['r_converged'] is False and not s1['candidate_written'],
        it2_converged_and_candidate=s2['r_converged'] is True and s2['candidate_written'] is True,
        candidate_file=(out / 'scratch' / L.CANDIDATE_NC).exists(),
        lp2_outputs={'LOSS_BASIS_LP2_QA.json', 'line_loss.csv.gz', 'shed_by_bus.csv.gz', 'line_flow_p0.csv.gz'} <= set(s3['files']),
        lp1_outputs={'LOSSY_LP1_QA.json', 'LP1_LINE_SOLUTION.csv', 'line_loss.csv.gz', 'shed_by_bus.csv.gz'} <= set(s1['files']),
        ledger=list(lg.stage) == L.STAGES and set(lg.state) == {'DONE'},
        zero_retries=not retry['approved'] and any('already has a logged call' in x for x in retry['reasons']),
        frozen_v16_files_unchanged={k: A2G.file_shas(L.ROOT / c[k]['path'])['raw'] for k in ('baseline', 'raw_baseline')} == frozen,
        real_ledger_untouched=not (L.WF / L.load()['out_dir'] / 'LOSSY_LP1_SOLVE_LOG.csv').exists())
    rep['verdict'] = 'ZERO_SOLVER_CHAIN_PASS' if all(rep['checks'].values()) else 'ZERO_SOLVER_CHAIN_FAIL'
    rep['fake_solve_calls'] = F.CALLS
    (out / 'NEXT08_ZERO_SOLVER_CHAIN.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps(rep, indent=1, default=str))


if __name__ == '__main__':
    main()
