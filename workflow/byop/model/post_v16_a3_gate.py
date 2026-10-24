"""NEXT-06 W3: the A3 (S3 / S2 / S3_mS2 ERCOT pilot) run gate - independent of A1 / A2 (own config, manifest, parent + child ledgers,
budgets, call plan). Static only: nothing here calls a solver, and rearch_mech does not yet route A3 solves through it (runtime
wiring is listed in W3_A3_EXECUTION_READINESS.md). Refuses unless ALL hold:
  1  config.byop_post_v16_a3.yaml: run_authorization == APPROVED, approved_by set, stage == A3 (A1 / A2 approvals never carry over)
  2  approved_git_sha == HEAD or an ancestor with nothing changed since under code / config / inputs except this config; clean tree
  3  authorization source text equals its pinned LF SHA; manifest exists and matches (post_v16_a2_gate.manifest_mismatches)
  4  --base is the pinned v1.6 baseline
  5  prerequisites: every file in `prerequisites` exists and its JSON field equals the required value (e.g. the S0 scientific
     verdict must not be BLOCKED / UNRESOLVED) - an unresolved S0 baseline blocks A3
  6  parent ledger: the stage has no earlier row (zero retries), the scenario-attempt budget is not used up, stages in order
  7  child ledger: readable; every child kind is in the call plan and below its own count; the total top-level budget holds
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import post_v16_gate as G
import post_v16_a2_gate as A2G

ROOT, WF = A2G.ROOT, A2G.WF
CFG = WF / 'config/config.byop_post_v16_a3.yaml'
CHILD_COLS = A2G.CHILD_COLS


def load(cfg_path=CFG):
    return G.load(cfg_path)


def paths(cfg_path=CFG):
    c = load(cfg_path)
    out = WF / c['out_dir']
    return c, out, out / 'A3_SOLVE_LOG.csv', out / 'A3_OPTIMIZER_CALL_LOG.csv'


def plan_counts(c):
    """{stage: {kind: max_count}} from the config call plan"""
    return {st: {k: int(v) for k, v in kinds.items()} for st, kinds in (c.get('optimizer_call_plan') or {}).items()}


def prerequisite_problems(c, root=ROOT):
    bad = []
    for p in c.get('prerequisites') or []:
        f = root / p['file']
        if not f.exists():
            bad.append(f"prerequisite missing: {p['file']}"); continue
        try:
            v = json.loads(f.read_text(encoding='utf-8'))
            for k in p['field'].split('.'):
                v = v[k]
        except Exception:
            bad.append(f"prerequisite unreadable: {p['file']}:{p['field']}"); continue
        if v not in p['allowed']:
            bad.append(f"prerequisite {p['file']}:{p['field']} = {v} not in {p['allowed']}")
    return bad


def reference_problems(c, root=ROOT):
    """NEXT-07 W4.1: the accepted A2 S0 / S1_EARLIEST results the A3 re-solves must reproduce, SHA-pinned in the config"""
    r = c.get('reference') or {}
    if not r.get('dir') or not r.get('sha256'):
        return ['reference (accepted A2 S0 / S1 results) not pinned in the A3 config']
    bad = []
    for f, h in r['sha256'].items():
        p = root / 'workflow' / r['dir'] / f
        if not p.exists():
            bad.append(f'reference missing: {f}')
        elif A2G.file_shas(p)['raw'] != h and A2G.file_shas(p)['lf'] != h:
            bad.append(f'reference SHA differs: {f}')
    for f in ('S0_RESULT.json', 'S1_EARLIEST_RESULT.json', A2G.NO_HARM_REF):
        if f not in r['sha256']:
            bad.append(f'reference {f} not pinned')
    lg, prob = G.solve_log_rows(root / 'workflow' / r['dir'] / 'A2_SOLVE_LOG.csv')       # NEXT-09: reference on THIS baseline only
    if prob or lg is None or not len(lg):
        bad.append('reference ledger A2_SOLVE_LOG.csv missing or unreadable')
    else:
        for st in ('S0', 'S1_EARLIEST'):
            row = lg[(lg.stage == st) & (lg.state == 'DONE')]
            if not len(row) or str(row.base_sha256.iloc[-1]) != str(c['baseline']['sha256']):
                bad.append(f"reference {st} was not solved on this config's baseline {str(c['baseline']['sha256'])[:12]} "
                           f"(ledger: {row.base_sha256.iloc[-1][:12] if len(row) else 'none'})")
    return bad


def check(stage, base_path, cfg_path=CFG, root=ROOT, git_fn=G.git):
    c, out, log, child = paths(cfg_path)
    reasons = []
    if str(c.get('run_authorization')) != 'APPROVED':
        reasons.append(f"run_authorization={c.get('run_authorization')}")
    if not c.get('approved_by'):
        reasons.append('approved_by missing')
    if c.get('stage') != 'A3':
        reasons.append(f"config stage {c.get('stage')} is not A3 (A1 / A2 approvals never carry over)")
    if 'diagnostic' in c:                    # NEXT-07: diagnostic options (e.g. the reserve-RHS probe) never reach A3
        reasons.append('A3 config carries a diagnostic block - refused (formal rules only)')
    head = git_fn('rev-parse', 'HEAD').stdout.strip()
    asha = str(c.get('approved_git_sha') or '')
    if not asha:
        reasons.append('approved_git_sha missing')
    elif not head.startswith(asha):
        anc = git_fn('merge-base', '--is-ancestor', asha, 'HEAD').returncode == 0
        since = set(git_fn('diff', '--name-only', asha, 'HEAD', '--', *G.CLEAN_PATHS).stdout.split())
        cp, rp = Path(cfg_path).resolve(), Path(root).resolve()
        cfg_rel = cp.relative_to(rp).as_posix() if cp.is_relative_to(rp) else None
        since -= A2G.registry_adoption_only_change(root / c['manifest'])
        if not anc:
            reasons.append(f'approved_git_sha {asha} is not HEAD or an ancestor of it')
        elif since - {cfg_rel}:
            reasons.append(f'code / config / inputs changed since the approved commit: {sorted(since - {cfg_rel})[:5]}')
    dirty = git_fn('diff', '--ignore-cr-at-eol', '--name-only', 'HEAD', '--', *G.CLEAN_PATHS).stdout.split() + \
        git_fn('ls-files', '--others', '--exclude-standard', '--', *G.CLEAN_PATHS).stdout.split()
    if dirty:
        reasons.append(f'worktree not clean for code / config / inputs: {dirty[:5]}')
    src = root / c['authorization_source']
    if not src.exists() or A2G.file_shas(src)['lf'] != c['authorization_source_sha256']:
        reasons.append('authorization source missing or changed')
    man_p = root / c['manifest'] if not Path(c['manifest']).is_absolute() else Path(c['manifest'])
    if not man_p.exists():
        reasons.append(f"manifest missing: {c['manifest']}")
    else:
        man = json.loads(man_p.read_text(encoding='utf-8'))
        reasons += A2G.manifest_mismatches(man, root)
        if man.get('config_sha256_normalised') != G.config_sha(cfg_path):
            reasons.append('config differs from the manifest (normalised SHA)')
        if (man.get('baseline') or {}).get('sha256') != c['baseline']['sha256']:     # NEXT-09: a manifest of another baseline is void
            reasons.append('A3 manifest was built for another baseline - rebuild it')
        reasons += A2G.registry_manifest_problems(man)
    want = (root / c['baseline']['path']).resolve()
    if base_path is None or Path(base_path).resolve() != want or not want.exists() or A2G.file_shas(want)['raw'] != c['baseline']['sha256']:
        reasons.append('baseline missing / not the pinned v1.6 file')
    import baseline_registry as BR                      # NEXT-09: only the formal 2025 baseline
    reasons += [r for r in BR.baseline_problems(c.get('baseline'), base_path, root=root, git_fn=git_fn) if r not in reasons]
    reasons += prerequisite_problems(c, root)
    reasons += reference_problems(c, root)
    stages = list(c['stages'])
    if stage not in stages:
        reasons.append(f'stage {stage} not in the A3 plan {stages}')
    lg, prob = G.solve_log_rows(log)
    if prob:
        reasons.append(prob)
    else:
        if (lg.stage == stage).any():
            reasons.append(f'{stage} already has a logged call (zero retries)')
        if len(lg) >= int(c['max_scenario_attempts']):
            reasons.append('A3 scenario-attempt budget used')
        if stage in stages:
            for prev in stages[:stages.index(stage)]:
                if not ((lg.stage == prev) & (lg.state == 'DONE') & (lg['pass'] == 'True')).any() and prev not in (c.get('optional_stages') or []):
                    reasons.append(f'{stage} needs a PASSED {prev} first')
    cl, prob2 = A2G.read_child_log(child)
    if prob2:
        reasons.append(prob2)
    elif len(cl) >= int(c['max_top_level_optimizer_calls']):
        reasons.append('A3 top-level optimizer-call budget used')
    return dict(approved=not reasons, reasons=reasons, head=head, stage=stage, config=str(cfg_path), ledger=str(log), child_ledger=str(child))


def child_start(parent, stage, kind, cfg_path=CFG, **meta):
    """persist a STARTED child row BEFORE a top-level optimizer call; refuses an unplanned kind, a kind beyond its count, a parent that
    is not STARTED, or the total budget"""
    c, out, log, child = paths(cfg_path)
    lg = A2G.read_ledger(log)
    if not ((lg.attempt_id == parent) & (lg.state == 'STARTED')).any():
        raise SystemExit(f'A3: parent {parent} is not a STARTED attempt - {kind} refused')
    plan = plan_counts(c).get(stage, {})
    if kind not in plan:
        raise SystemExit(f'A3: {kind} not in the call plan of {stage} - refused')
    cl, prob = A2G.read_child_log(child)
    if prob:
        raise SystemExit('A3: ' + prob)
    used = int(((cl.parent_attempt_id == parent) & (cl.kind == kind)).sum())
    if used >= plan[kind]:
        raise SystemExit(f'A3: {kind} already used {used} / {plan[kind]} times for {parent} - refused')
    if len(cl) >= int(c['max_top_level_optimizer_calls']):
        raise SystemExit('A3: top-level optimizer-call budget used - refused')
    row = {k: '' for k in CHILD_COLS}
    row.update(call_id=f'{parent}/{kind}#{used + 1}', parent_attempt_id=parent, stage=stage, kind=kind, state='STARTED',
               started_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), **{k: str(v) for k, v in meta.items()})
    A2G._atomic_write(pd.concat([cl, pd.DataFrame([row])], ignore_index=True)[CHILD_COLS], child)
    return row['call_id']


def max_planned_calls(c):
    return sum(sum(k.values()) for k in plan_counts(c).values())
