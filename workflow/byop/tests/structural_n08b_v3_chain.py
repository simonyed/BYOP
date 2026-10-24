#!/usr/bin/env python3
"""NEXT-08b loss-upper fix: zero-solver end-to-end test of the LP1 v3 chain on the REAL v1.6 networks (config.byop_lossy_lp1_v3.yaml),
through loss_basis_lp1.run with the real builds and the REAL stage-order rules (only the approval / SHA / manifest reasons are dropped;
config / ledger / candidate in a scratch directory). gurobipy optimize raises; linopy.Model.solve is replaced by fake solves:
  (a) FIXED POINT: every capacity at S_ref (= v1.6 prepared in IT1) -> IT1 r-converged, no line on a floor, guards pass, candidate
      written -> IT2 refused (IT1 converged) -> LP2 on the candidate;
  (b) FLOOR: every capacity at its lower row (the trust floor max(raw, 0.75 S_ref)) -> IT1 not converged (lines on floors above raw)
      -> IT2 -> still on floors -> not converged -> LP2 refused (STOP).
Frozen v1.6 files and every earlier ledger are checked unchanged. Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n08b_v3_chain.py --out results/BYOP/next08b_lp1_loss_upper_fix/_zero_solver_chain
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
from test_next08b_loss_upper import fake_at  # noqa: E402

try:
    import gurobipy
    gurobipy.Model.optimize = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('gurobipy optimize in a zero-solver test'))
except Exception:
    pass
import loss_basis_lp1 as L  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402

DROP = ('run_authorization', 'approved_by', 'approved_git_sha', 'worktree not clean', 'manifest', 'config differs', 'code / config')
CFG3 = L.WF / 'config/config.byop_lossy_lp1_v3.yaml'
LEDGERS = ['results/BYOP/next08_lossy_lp1/LOSSY_LP1_SOLVE_LOG.csv', 'results/BYOP/next08b_lp1_tangent_fix/LOSSY_LP1_SOLVE_LOG.csv']


def scenario(out, tag, solve_lp1):
    raw = yaml.safe_load(CFG3.read_text(encoding='utf-8'))
    raw['post_v16']['out_dir'] = str(out / tag)
    cfgp = out / f'config.byop_lossy_lp1_v3.{tag}.ZERO_SOLVER.yaml'
    cfgp.write_text(yaml.safe_dump(raw), encoding='utf-8')

    def gate(stage):
        g = L.check(stage, cfg_path=cfgp)
        keep = [x for x in g['reasons'] if not x.startswith(DROP)]
        return dict(g, approved=not keep, reasons=keep, dropped_for_test=[x for x in g['reasons'] if x.startswith(DROP)])
    rep = dict(stages={})
    for st in L.STAGES:
        linopy.Model.solve = F.fake_solve if st == 'LP2_LOSSY_CANDIDATE' else solve_lp1
        g = gate(st)
        if not g['approved']:
            rep['stages'][st] = dict(refused=g['reasons'])
            continue
        q = L.run(st, 4, cfg_path=cfgp, gate_fn=lambda s_, g=g: g)
        d = {k: q.get(k) for k in ('status', 'termination', 'n_vars', 'n_cons', 'r_converged', 'candidate_written', 'acceptance_pass')}
        if st != 'LP2_LOSSY_CANDIDATE':
            d.update(convergence=q['convergence'], guards={k: q['guards'][k] for k in ('G1', 'G2', 'G3', 'all_pass', 'total_uplift_MVA')})
        d['files'] = sorted(p.name for p in (out / tag / st).iterdir())
        rep['stages'][st] = d
    p = out / tag / 'LOSSY_LP1_SOLVE_LOG.csv'
    rep['ledger'] = pd.read_csv(p, dtype=str, keep_default_na=False)[['stage', 'state', 'r_converged', 'guards_pass']].to_dict('records') if p.exists() else []
    return rep, cfgp


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    c = L.load(CFG3)
    frozen = {k: A2G.file_shas(L.ROOT / c[k]['path'])['raw'] for k in ('baseline', 'raw_baseline')}
    led = {p: A2G.file_shas(L.WF / p)['raw'] for p in LEDGERS}
    import pypsa
    s_prep = pypsa.Network(str(L.ROOT / c['baseline']['path'])).lines.s_nom
    ra, _ = scenario(out, 'a_fixed_point', fake_at(s_prep))
    rb, _ = scenario(out, 'b_trust_floor', F.fake_solve)
    A, B = ra['stages'], rb['stages']
    rep = dict(step='NEXT-08b LP1 v3 zero-solver chain on the real v1.6 networks', config=str(CFG3), real_solver_calls=0,
               a_fixed_point=ra, b_trust_floor=rb, fake_solve_calls=len(F.CALLS))
    rep['checks'] = dict(
        a_it1_converged_no_floor_candidate=A['LP1_LOSSY_IT1'].get('r_converged') is True and A['LP1_LOSSY_IT1']['convergence'].get('lines_at_trust_floor') == []
        and A['LP1_LOSSY_IT1'].get('candidate_written') is True and A['LP1_LOSSY_IT1']['guards']['all_pass'],
        a_it2_refused=any('LP1_LOSSY_IT2 only' in x for x in A['LP1_LOSSY_IT2'].get('refused', [])),
        a_lp2_ran=A['LP2_LOSSY_CANDIDATE'].get('termination') == 'optimal' and 'LOSS_BASIS_LP2_QA.json' in A['LP2_LOSSY_CANDIDATE'].get('files', []),
        a_candidate_file=(out / 'a_fixed_point' / L.CANDIDATE_NC).exists(),
        b_it1_floor_not_converged=B['LP1_LOSSY_IT1'].get('r_converged') is False and len(B['LP1_LOSSY_IT1']['convergence'].get('lines_at_trust_floor', [])) > 0,
        b_it2_not_converged_no_candidate=B['LP1_LOSSY_IT2'].get('r_converged') is False and B['LP1_LOSSY_IT2'].get('candidate_written') is False,
        b_lp2_refused=any('LP2_LOSSY_CANDIDATE only' in x for x in B['LP2_LOSSY_CANDIDATE'].get('refused', [])),
        b_no_candidate_file=not (out / 'b_trust_floor' / L.CANDIDATE_NC).exists(),
        lp1_files=all({'LOSSY_LP1_QA.json', 'LP1_LINE_SOLUTION.csv', 'line_loss.csv.gz'} <= set(x.get('files', [])) for x in (A['LP1_LOSSY_IT1'], B['LP1_LOSSY_IT1'], B['LP1_LOSSY_IT2'])),
        frozen_v16_files_unchanged={k: A2G.file_shas(L.ROOT / c[k]['path'])['raw'] for k in ('baseline', 'raw_baseline')} == frozen,
        earlier_ledgers_unchanged={p: A2G.file_shas(L.WF / p)['raw'] for p in LEDGERS} == led,
        real_v3_ledger_untouched=not (L.WF / c['out_dir'] / 'LOSSY_LP1_SOLVE_LOG.csv').exists())
    rep['verdict'] = 'ZERO_SOLVER_CHAIN_PASS' if all(rep['checks'].values()) else 'ZERO_SOLVER_CHAIN_FAIL'
    (out / 'NEXT08B_V3_ZERO_SOLVER_CHAIN.json').write_text(json.dumps(rep, indent=1, default=str), encoding='utf-8')
    print(json.dumps(dict(verdict=rep['verdict'], checks=rep['checks']), indent=1, default=str))


if __name__ == '__main__':
    main()
