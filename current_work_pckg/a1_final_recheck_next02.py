#!/usr/bin/env python3
"""BYOP-POST-V16-NEXT-02 W1 2.1: A1 final read-only recheck before the approval request (NO solver). Run on L2 in the A1 main
checkout, from pypsa-usa/workflow:
    python ../current_work_pckg/a1_final_recheck_next02.py
Kept in current_work_pckg/ (outside the A1 gate's code / config / input paths). Unlike the NEXT-01 P0 check it does NOT require
HEAD == 802c9d94: it requires 802c9d94 to be an ancestor of HEAD with nothing changed since under the gated paths (the same rule the
gate applies to an approval commit), and it re-hashes everything from this checkout (the old JSON is history only).
Writes A1_FINAL_RECHECK.json next to this file.
"""
from __future__ import annotations

import hashlib, json, subprocess, sys
from pathlib import Path

import numpy as np

WF = Path.cwd()
ROOT = WF.parent
sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/run'))
import byop_paths as BP  # noqa: E402
import post_v16_gate as G  # noqa: E402
import post_v16_a1 as A  # noqa: E402

APPROVABLE = '802c9d9414514641fd2b088b45ec7ea945be18a4'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
git = lambda *a: subprocess.run(['git', '-C', str(ROOT), *a], capture_output=True, text=True)


def main():
    import linopy
    calls = []
    linopy.Model.solve = lambda *a, **k: calls.append('refused') or (_ for _ in ()).throw(RuntimeError('solve refused in NEXT-02 recheck'))
    out = {}
    head = git('rev-parse', 'HEAD').stdout.strip()
    anc = git('merge-base', '--is-ancestor', APPROVABLE, 'HEAD').returncode == 0
    since_gated = git('diff', '--name-only', APPROVABLE, 'HEAD', '--', *G.CLEAN_PATHS).stdout.split()
    since_all = git('diff', '--name-only', APPROVABLE, 'HEAD').stdout.split()
    dirty = git('diff', '--ignore-cr-at-eol', '--name-only', 'HEAD', '--', *G.CLEAN_PATHS).stdout.split()
    untracked = git('ls-files', '--others', '--exclude-standard', '--', *G.CLEAN_PATHS).stdout.split()
    out['git'] = dict(head=head, approvable=APPROVABLE, approvable_is_ancestor=anc, changed_since_approvable_gated=since_gated,
                      changed_since_approvable_all=since_all, dirty_code_config_inputs=dirty, untracked_code_config_inputs=untracked,
                      log=git('log', '--format=%H %s', f'{APPROVABLE}..HEAD').stdout.splitlines())
    c = G.load(A.CFG)
    out['authorization'] = {k: c.get(k) for k in G.APPROVAL_FIELDS}
    src = ROOT / c['authorization_source']
    out['authorization_source'] = dict(path=c['authorization_source'], ok=src.exists() and sha(src) == c['authorization_source_sha256'])
    man = json.loads((ROOT / c['manifest']).read_text(encoding='utf-8'))
    files = {**man['code_sha256'], **man['inputs_sha256']}
    mism = [r for r, h in files.items() if not (ROOT / r).exists() or sha(ROOT / r) != h]
    out['manifest'] = dict(path=c['manifest'], sha256=sha(ROOT / c['manifest']), code_files=len(man['code_sha256']),
                           input_files=len(man['inputs_sha256']), mismatches=mism, files={r: sha(ROOT / r) for r in files if (ROOT / r).exists()},
                           config_normalised_sha=G.config_sha(A.CFG), config_normalised_ok=man['config_sha256_normalised'] == G.config_sha(A.CFG),
                           baseline_pin_ok=man['baseline']['sha256'] == c['baseline']['sha256'])
    base = BP.BASE_TAMU_V16
    out['baseline'] = dict(path=str(base.relative_to(ROOT)), sha256=sha(base), ok=sha(base) == BP.BASE_TAMU_V16_SHA256 == c['baseline']['sha256'])
    lg = A.LOG
    rows, prob = G.solve_log_rows(lg)
    out['ledger'] = dict(path=str(lg.relative_to(ROOT)), exists=lg.exists(), rows=0 if rows is None else len(rows), problem=prob,
                         sha256=sha(lg) if lg.exists() else None)
    out['gate'] = {k: G.check(A.CFG, A.STAGE[k], str(base), lg) for k in A.STAGE}
    out['frozen_design'] = dict(resolution_h=c['time']['resolution_h'], reserve_MW=c['reserve']['requirement_MW'], tau_h=c['reserve']['tau_h'],
                                blocks=c['headroom']['blocks'], objective=c['objective'], stages=c['stages'], max_lp_calls=c['max_lp_calls'],
                                max_retries=c['max_retries'], lambda_upper_MW=c['headroom']['lambda_upper_MW'], acceptance=c['acceptance'])
    models = {}
    for mode in ('R', 'N'):
        n, info, cfg = A.build(mode, base)
        m = n.model
        s = info['structure']
        lam = int(m['PV16-lambda'].labels.values)
        ov = np.asarray(m.objective.expression.vars.values if hasattr(m.objective, 'expression') else m.objective.vars.values).ravel()
        z_ = m.constraints['PV16-existing_shed_zero']
        w = np.array([x['w'] for x in info['weights']])
        models[mode] = dict(n_vars=s['n_vars'], n_cons=s['n_cons'], integer_vars=s['integer_vars'], buses=s['buses'], lines=s['lines'],
                            snapshots=s['snapshots'], objective_only_lambda=set(ov[ov != -1]) == {lam},
                            zero_shed_rows=int(z_.lhs.sizes['snapshot'] * z_.lhs.sizes['name']), weights_n=int(len(w)), weights_sum=float(w.sum()),
                            line_limit_total_MVA=float((n.lines.s_nom * n.lines.s_max_pu).sum()), reserve_MW=cfg['reserve']['requirement_MW'],
                            windows=[x['id'] for x in info['windows']])
    models['line_limit_relation_R_ge_N'] = models['R']['line_limit_total_MVA'] > models['N']['line_limit_total_MVA']
    models['identical_structure'] = models['R']['n_vars'] == models['N']['n_vars'] and models['R']['n_cons'] == models['N']['n_cons']
    out['dry'] = models
    out['solver_calls'] = len(calls)
    allowed = {'run_authorization=NOT_APPROVED', 'approved_by missing', 'approved_git_sha missing'}
    ok = (anc and not since_gated and not dirty and not untracked and not mism and out['manifest']['config_normalised_ok']
          and out['authorization_source']['ok'] and out['baseline']['ok'] and not lg.exists()
          and all(v in (None, 'NOT_APPROVED') for v in out['authorization'].values())
          and all(models[k]['objective_only_lambda'] and models[k]['integer_vars'] == 0 and abs(models[k]['weights_sum'] - 1) < 1e-12
                  and models[k]['snapshots'] == 432 and models[k]['reserve_MW'] == 3000 for k in ('R', 'N'))
          and models['line_limit_relation_R_ge_N'] and models['identical_structure'] and not calls
          and all(set(g['reasons']) <= allowed or (k == 'N' and all(r.startswith(('run_authorization', 'approved_', 'LP_N_H_NETWORK needs a PASSED'))
                                                                     for r in g['reasons'])) for k, g in out['gate'].items()))
    out['status'] = 'PASS_READY_FOR_A1_APPROVAL' if ok else 'BLOCKED'
    name = sys.argv[1] if len(sys.argv) > 1 else 'A1_FINAL_RECHECK.json'      # NEXT-03: A1_FINAL_RECHECK_NEXT03.json
    (ROOT / 'current_work_pckg' / name).write_text(json.dumps(out, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('git', 'authorization', 'authorization_source', 'baseline', 'ledger', 'status', 'solver_calls')},
                     indent=1, default=str))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'windows'}) for k, v in models.items()},
                     indent=1, default=str))
    print({k: g['reasons'] for k, g in out['gate'].items()})


if __name__ == '__main__':
    main()
