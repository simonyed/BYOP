"""Post-v1.6 run gate (execution package v1.1, A0 2026-10-22). Every post-v1.6 optimizer entry calls check() BEFORE building
anything and refuses unless ALL of the following hold (each failure is one reason string):
  1  run_authorization == APPROVED and approved_by set (only the researcher edits these fields)
  2  approved_git_sha == HEAD (>= 8-char prefix), or an ancestor of HEAD with nothing changed since under code / config /
     inputs except the A1 config itself (the approval commit); the worktree is clean for code / config / inputs
     (content diff against HEAD ignoring CR at EOL, and no untracked file; byte identity comes from the manifest SHAs)
  3  the work-package text equals its pinned SHA-256 (config authorization_source_sha256)
  4  the pre-run manifest exists and every code / input SHA-256 and the normalised config SHA-256 match it
  5  the network file actually passed (--base) is the configured v1.6 path, exists, and its SHA-256 equals the pinned
     v1.6 SHA in the config AND in the manifest (no fallback to the pre-v1.6 baseline_2025_tamu)
  6  the stage is in the authorised list, the order is respected (LP-N only after LP-R PASSED: DONE / ok / optimal / pass in the
     ledger AND an LP-R RESULT.json with acceptance PASS), the stage has no earlier ledger row in ANY state (STARTED counts:
     zero retries), the ledger is readable, and the LP budget is not used up (A0.1 FIX-02 / FIX-03)
check() never touches a solver; deny() raises SystemExit(3) with the reasons.
"""
from __future__ import annotations

import hashlib, json, subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]            # pypsa-usa
APPROVAL_FIELDS = ('run_authorization', 'approved_git_sha', 'approved_by')
CLEAN_PATHS = ['workflow/byop/model', 'workflow/byop/build', 'workflow/byop/run', 'workflow/byop/post', 'workflow/byop/inputs',
               'workflow/config', 'workflow/scripts']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(cfg_path):
    return yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))['post_v16']


def config_sha(cfg_path):
    """SHA-256 of the config with the three approval fields normalised (so approving does not change the pinned hash)"""
    d = yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))
    for k in APPROVAL_FIELDS:
        d['post_v16'][k] = None
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True)


LEDGER_REQUIRED = ('attempt_id', 'stage', 'attempt', 'state', 'status', 'termination', 'pass')


def solve_log_rows(log_path):
    """the A1 call ledger (A0.1 FIX-03); returns (DataFrame, problem) - an unreadable / malformed ledger is a refusal, never 'empty'"""
    import pandas as pd
    p = Path(log_path)
    if not p.exists():
        return pd.DataFrame(columns=list(LEDGER_REQUIRED)), None
    try:
        lg = pd.read_csv(p, dtype=str, keep_default_na=False)
    except Exception as e:
        return None, f'call ledger unreadable ({e.__class__.__name__}) - counted as consumed, refused'
    miss = [k for k in LEDGER_REQUIRED if k not in lg.columns]
    if miss:
        return None, f'call ledger malformed (missing {miss}) - refused'
    return lg, None


def prior_stage_pass(log_dir, prev, lg):
    """A0.1 FIX-02: the previous stage must have a DONE ledger row with ok / optimal / pass AND a RESULT.json whose acceptance
    PASS is true with every check true (log status alone is not enough); returns the list of failures"""
    bad = []
    rows = lg[lg.stage == prev]
    if not len(rows):
        return [f'{prev} has no ledger row']
    r = rows.iloc[-1]
    if not (r.state == 'DONE' and r.status == 'ok' and r.termination == 'optimal' and str(r['pass']) == 'True'):
        bad.append(f'{prev} ledger row is not DONE / ok / optimal / pass ({r.state}, {r.status}, {r.termination}, pass={r["pass"]})')
    f = Path(log_dir) / f'{prev}_RESULT.json'
    if not f.exists():
        return bad + [f'{prev}_RESULT.json missing']
    try:
        res = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        return bad + [f'{prev}_RESULT.json unreadable']
    acc = res.get('acceptance') or {}
    if acc.get('PASS') is not True or not acc.get('checks') or not all(v is True for v in acc['checks'].values()):
        bad.append(f'{prev}_RESULT.json acceptance is not PASS: {acc.get("checks")}')
    return bad


def check(cfg_path, stage, base_path, log_path, root=ROOT, git_fn=git):
    c = load(cfg_path)
    reasons = []
    if str(c.get('run_authorization')) != 'APPROVED':
        reasons.append(f"run_authorization={c.get('run_authorization')}")
    if not c.get('approved_by'):
        reasons.append('approved_by missing')
    head = git_fn('rev-parse', 'HEAD').stdout.strip()
    asha = str(c.get('approved_git_sha') or '')
    if not asha:
        reasons.append('approved_git_sha missing')
    elif len(asha) < 8:
        reasons.append(f'approved_git_sha {asha} too short')
    elif not head.startswith(asha):
        # the approval itself is a later commit of the A1 config only: the approved commit must be an ancestor of HEAD and
        # nothing under code / config / inputs may differ since, except the A1 config (whose normalised SHA is checked below)
        anc = git_fn('merge-base', '--is-ancestor', asha, 'HEAD').returncode == 0
        since = set(git_fn('diff', '--name-only', asha, 'HEAD', '--', *CLEAN_PATHS).stdout.split())
        cfg_rel = Path(cfg_path).resolve().relative_to(Path(root).resolve()).as_posix() if Path(cfg_path).resolve().is_relative_to(Path(root).resolve()) else None
        if not anc:
            reasons.append(f'approved_git_sha {asha} is not HEAD {head} or an ancestor of it')
        elif since - {cfg_rel}:
            reasons.append(f'code / config / inputs changed since the approved commit: {sorted(since - {cfg_rel})[:5]}')
    # content changes against HEAD (CR-at-EOL ignored: the L2 checkout shows CRLF-only differences as modified) + untracked files
    changed = git_fn('diff', '--ignore-cr-at-eol', '--name-only', 'HEAD', '--', *CLEAN_PATHS).stdout.split()
    untracked = git_fn('ls-files', '--others', '--exclude-standard', '--', *CLEAN_PATHS).stdout.split()
    dirty = '\n'.join(changed + untracked)
    if dirty:
        reasons.append(f'worktree not clean for code / config / inputs: {dirty.splitlines()[:5]}')
    src = root / c['authorization_source']
    if not src.exists() or sha(src) != c['authorization_source_sha256']:
        reasons.append('authorization source missing or changed')
    man_p = root / c['manifest']
    man = None
    if not man_p.exists():
        reasons.append(f'manifest missing: {c["manifest"]}')
    else:
        man = json.loads(man_p.read_text(encoding='utf-8'))
        for rel, h in {**man.get('code_sha256', {}), **man.get('inputs_sha256', {})}.items():
            f = root / rel
            if not f.exists() or sha(f) != h:
                reasons.append(f'sha256 mismatch: {rel}')
        if man.get('config_sha256_normalised') != config_sha(cfg_path):
            reasons.append('config differs from the manifest (normalised SHA)')
    # 5 the baseline actually used
    want = (root / c['baseline']['path']).resolve()
    got = Path(base_path).resolve() if base_path else None
    if got is None:
        reasons.append('no --base given (no fallback)')
    elif got != want:
        reasons.append(f'--base {base_path} is not the v1.6 baseline {c["baseline"]["path"]}')
    elif not got.exists():
        reasons.append(f'v1.6 baseline missing on this machine: {base_path} (BLOCKED_ON_L2_BASELINE)')
    else:
        h = sha(got)
        if h != c['baseline']['sha256']:
            reasons.append(f'baseline SHA {h} != pinned {c["baseline"]["sha256"]}')
        if man is not None and man.get('baseline', {}).get('sha256') != c['baseline']['sha256']:
            reasons.append('manifest baseline SHA differs from the config')
    # 6 stage, order, retries, budget
    stages = list(c['stages'])
    if stage not in stages:
        reasons.append(f'stage {stage} not authorised ({stages})')
    lg, prob = solve_log_rows(log_path)
    if prob:
        reasons.append(prob)
    else:
        if (lg.stage == stage).any():                 # STARTED / ERROR / DONE all consume the stage (zero retries)
            st_ = sorted(set(lg[lg.stage == stage].state))
            reasons.append(f'{stage} already has a logged call {st_} (zero retries)')
        if len(lg) >= int(c['max_lp_calls']):
            reasons.append('LP budget used')
        if stage in stages and stages.index(stage) > 0:
            prev = stages[stages.index(stage) - 1]
            fails = prior_stage_pass(Path(log_path).parent, prev, lg)
            if fails:
                reasons.append(f'{stage} needs a PASSED {prev} first: ' + '; '.join(fails))
    return dict(approved=not reasons, reasons=reasons, head=head, approved_git_sha=asha or None, stage=stage,
                base=str(base_path), config=str(cfg_path))


def deny(g):
    if not g['approved']:
        raise SystemExit('POST_V16_RUN_GATE REFUSED: ' + json.dumps(g['reasons']))
