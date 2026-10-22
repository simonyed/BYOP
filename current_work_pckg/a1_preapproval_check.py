#!/usr/bin/env python3
"""BYOP-POST-V16-NEXT-01 P0: A1 pre-approval check (read-only, NO solver). Run on L2 from pypsa-usa/workflow:
    python ../current_work_pckg/a1_preapproval_check.py
Kept in current_work_pckg/ (outside the A1 gate's code / config / input paths) so that it does not change the commit the
researcher may approve. Builds both A1 models via the existing runner's build() (create_model only) and re-checks: network,
snapshots, sizes, zero-shed rows, objective = -lambda, line-limit relation R vs N, 16-bus weights sum 1, gate, ledger, manifest,
baseline SHA, v2 technology source SHA, A0.2 return package readability. Writes A1_PREAPPROVAL_GATE.json next to this file.
"""
from __future__ import annotations

import hashlib, json, subprocess, sys, zipfile
from pathlib import Path

import numpy as np

WF = Path.cwd()
ROOT = WF.parent
sys.path.insert(0, str(WF / 'byop/model')); sys.path.insert(0, str(WF / 'byop/run'))
import byop_paths as BP  # noqa: E402
import post_v16_gate as G  # noqa: E402
import post_v16_a1 as A  # noqa: E402

sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import linopy
    calls = []
    linopy.Model.solve = lambda *a, **k: calls.append('refused') or (_ for _ in ()).throw(RuntimeError('solve refused in P0'))
    out = {}
    head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(ROOT), 'diff', '--ignore-cr-at-eol', '--name-only', 'HEAD', '--', *G.CLEAN_PATHS], capture_output=True, text=True).stdout.split()
    untracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--others', '--exclude-standard', '--', *G.CLEAN_PATHS], capture_output=True, text=True).stdout.split()
    out['git'] = dict(head=head, expected='802c9d9414514641fd2b088b45ec7ea945be18a4', head_ok=head == '802c9d9414514641fd2b088b45ec7ea945be18a4',
                      dirty_code_config_inputs=dirty, untracked_code_config_inputs=untracked)
    c = G.load(A.CFG)
    out['authorization'] = {k: c.get(k) for k in G.APPROVAL_FIELDS}
    man = json.loads((ROOT / c['manifest']).read_text())
    mism = [r for r, h in {**man['code_sha256'], **man['inputs_sha256']}.items() if not (ROOT / r).exists() or sha(ROOT / r) != h]
    out['manifest'] = dict(path=c['manifest'], sha256=sha(ROOT / c['manifest']), code_files=len(man['code_sha256']), input_files=len(man['inputs_sha256']),
                           mismatches=mism, config_normalised_ok=man['config_sha256_normalised'] == G.config_sha(A.CFG),
                           baseline_pin_ok=man['baseline']['sha256'] == c['baseline']['sha256'])
    base = BP.BASE_TAMU_V16
    out['baseline'] = dict(path=str(base.relative_to(ROOT)), sha256=sha(base), ok=sha(base) == BP.BASE_TAMU_V16_SHA256)
    import byop_tech_parameters_v2 as T2
    out['tech_v2_sources'] = dict(ok=T2.verify_sources(), files={f: sha(T2.SRC / f) for f in T2.SOURCE_SHA256})
    z = ROOT / 'current_work_pckg/A0_2_RETURN_PACKAGE.zip'
    with zipfile.ZipFile(z) as Z:
        out['a0_2_return_package'] = dict(sha256=sha(z), entries=len(Z.namelist()), testzip=Z.testzip() is None,
                                          has_file_list='FILE_LIST_SHA256.txt' in Z.namelist())
    for f in ('A0_2_INTEGRATION_REPORT.md', 'A0_1_REPAIR_REPORT.md', 'A2_TECH_READINESS_MATRIX.csv', 'POST_V16_A1_PRE_RUN_MANIFEST.json'):
        out.setdefault('a0_2_reports_readable', {})[f] = (ROOT / 'current_work_pckg' / f).stat().st_size > 0
    lg = A.LOG
    rows, prob = G.solve_log_rows(lg)
    out['ledger'] = dict(path=str(lg.relative_to(ROOT)), exists=lg.exists(), rows=0 if rows is None else len(rows), problem=prob,
                         consumed_calls=0 if rows is None else len(rows))
    out['gate'] = {k: G.check(A.CFG, A.STAGE[k], str(base), lg) for k in A.STAGE}
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
                            snapshots=s['snapshots'], components=s['components'], objective_only_lambda=set(ov[ov != -1]) == {lam},
                            zero_shed_rows=int(z_.lhs.sizes['snapshot'] * z_.lhs.sizes['name']), weights_n=int(len(w)), weights_sum=float(w.sum()),
                            line_limit_total_MVA=float((n.lines.s_nom * n.lines.s_max_pu).sum()), lambda_upper_MW=float(cfg['headroom']['lambda_upper_MW']),
                            reserve_MW=cfg['reserve']['requirement_MW'], windows=[x['id'] for x in info['windows']])
    models['line_limit_relation_R_ge_N'] = models['R']['line_limit_total_MVA'] >= models['N']['line_limit_total_MVA']
    models['identical_structure'] = models['R']['n_vars'] == models['N']['n_vars'] and models['R']['n_cons'] == models['N']['n_cons']
    out['dry'] = models
    out['solver_calls'] = len(calls)
    ok = (out['git']['head_ok'] and not dirty and not untracked and not mism and out['manifest']['config_normalised_ok'] and out['baseline']['ok']
          and out['ledger']['consumed_calls'] == 0 and all(v in (None, 'NOT_APPROVED') for v in out['authorization'].values())
          and all(models[k]['objective_only_lambda'] and models[k]['integer_vars'] == 0 and abs(models[k]['weights_sum'] - 1) < 1e-12 for k in ('R', 'N'))
          and models['line_limit_relation_R_ge_N'] and models['identical_structure'] and len(calls) == 0
          and all(set(g['reasons']) <= {'run_authorization=NOT_APPROVED', 'approved_by missing', 'approved_git_sha missing'} or
                  (k == 'N' and all(r.startswith(('run_authorization', 'approved_', 'LP_N_H_NETWORK needs a PASSED')) for r in g['reasons']))
                  for k, g in out['gate'].items()))
    out['P0_status'] = 'PASS_READY_FOR_A1_APPROVAL_REQUEST' if ok else 'BLOCKED'
    (ROOT / 'current_work_pckg/A1_PREAPPROVAL_GATE.json').write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ('git', 'authorization', 'manifest', 'baseline', 'ledger', 'P0_status', 'solver_calls')}, indent=1, default=str))
    print(json.dumps({k: v for k, v in models.items()}, indent=1, default=str))


if __name__ == '__main__':
    main()
