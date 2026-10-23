"""NEXT-02 A2-FIX-07: the post-v1.6 A2 (S0 + S1_EARLIEST) run gate, independent of the A1 gate (own config, manifest, ledger,
budget; it never reads the A1 approval fields). rearch_mech.py --post-v16 calls check() BEFORE building anything and again
before every solver call, and refuses (SystemExit 3) unless ALL hold:
  1  config.byop_post_v16_a2.yaml: run_authorization == APPROVED and approved_by set (only the researcher edits these)
  2  approved_git_sha == HEAD, or an ancestor of HEAD with nothing changed since under code / config / inputs except this config;
     the worktree is clean for code / config / inputs
  3  the work-package text equals its pinned SHA-256 (authorization_source_sha256)
  4  A2_PRE_RUN_MANIFEST.json exists; every code / input file matches it (A2-FIX-06: tracked text files by the LF-normalised
     SHA AND a raw SHA equal to either the pinned LF or the pinned CRLF encoding; untracked data by the raw SHA only); the
     normalised config SHA matches
  5  --base is the v1.6 baseline with the pinned SHA (config and manifest)
  6  the requested scenarios are exactly a prefix of [S0, S1_EARLIEST]; the stage has no earlier ledger row in ANY state
     (zero retries), the budget (2) is not used up, and S1_EARLIEST needs a DONE / ok / optimal / pass S0 row plus an
     S0_RESULT.json with acceptance PASS and the frozen S0 shed reference on disk
check() never touches a solver.
"""
from __future__ import annotations

import hashlib, json, os, tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import post_v16_gate as G

ROOT = G.ROOT
WF = ROOT / 'workflow'
CFG = WF / 'config/config.byop_post_v16_a2.yaml'
STAGES = ['S0', 'S1_EARLIEST']
LOG_COLS = ['attempt_id', 'stage', 'attempt', 'state', 'started_utc', 'finished_utc', 'status', 'termination', 'failure_class',
            'pass', 'seconds', 'manifest_sha256', 'base_sha256', 'note']
sha_bytes = lambda b: hashlib.sha256(b).hexdigest()


def lf(b):
    return b.replace(b'\r\n', b'\n')


def crlf(b):
    return lf(b).replace(b'\n', b'\r\n')


def file_shas(p):
    """raw / LF-normalised / CRLF-encoded SHA-256 of one file (A2-FIX-06 evidence layers)"""
    b = Path(p).read_bytes()
    return dict(raw=sha_bytes(b), lf=sha_bytes(lf(b)), crlf=sha_bytes(crlf(b)))


def load(cfg_path=CFG):
    return G.load(cfg_path)


def paths(cfg_path=CFG):
    c = load(cfg_path)
    out = WF / c['out_dir']
    return c, out, out / 'A2_SOLVE_LOG.csv'


def manifest_mismatches(man, root=ROOT):
    """tracked text: LF content must equal the pinned LF SHA and the raw bytes must be one of the two pinned encodings;
    raw data (text: false): raw bytes only"""
    bad = []
    for rel, rec in {**man.get('code', {}), **man.get('inputs', {})}.items():
        f = root / rel
        if not f.exists():
            bad.append(f'missing: {rel}')
            continue
        s = file_shas(f)
        if rec.get('text'):
            if s['lf'] != rec['lf'] or s['raw'] not in (rec['lf'], rec['crlf']):
                bad.append(f'sha256 mismatch: {rel}')
        elif s['raw'] != rec['raw']:
            bad.append(f'sha256 mismatch (raw): {rel}')
    return bad


def check(stage, base_path, scenarios=None, cfg_path=CFG, root=ROOT, git_fn=G.git):
    c, out, log = paths(cfg_path)
    reasons = []
    if str(c.get('run_authorization')) != 'APPROVED':
        reasons.append(f"run_authorization={c.get('run_authorization')}")
    if not c.get('approved_by'):
        reasons.append('approved_by missing')
    if c.get('stage') != 'A2':
        reasons.append(f"config stage {c.get('stage')} is not A2 (an A1 approval never carries over)")
    head = git_fn('rev-parse', 'HEAD').stdout.strip()
    asha = str(c.get('approved_git_sha') or '')
    if not asha:
        reasons.append('approved_git_sha missing')
    elif len(asha) < 8:
        reasons.append(f'approved_git_sha {asha} too short')
    elif not head.startswith(asha):
        anc = git_fn('merge-base', '--is-ancestor', asha, 'HEAD').returncode == 0
        since = set(git_fn('diff', '--name-only', asha, 'HEAD', '--', *G.CLEAN_PATHS).stdout.split())
        cfg_rel = Path(cfg_path).resolve().relative_to(Path(root).resolve()).as_posix()
        if not anc:
            reasons.append(f'approved_git_sha {asha} is not HEAD {head} or an ancestor of it')
        elif since - {cfg_rel}:
            reasons.append(f'code / config / inputs changed since the approved commit: {sorted(since - {cfg_rel})[:5]}')
    changed = git_fn('diff', '--ignore-cr-at-eol', '--name-only', 'HEAD', '--', *G.CLEAN_PATHS).stdout.split()
    untracked = git_fn('ls-files', '--others', '--exclude-standard', '--', *G.CLEAN_PATHS).stdout.split()
    if changed or untracked:
        reasons.append(f'worktree not clean for code / config / inputs: {(changed + untracked)[:5]}')
    src = root / c['authorization_source']
    if not src.exists() or file_shas(src)['lf'] != c['authorization_source_sha256']:      # LF content (checkout-EOL independent)
        reasons.append('authorization source missing or changed')
    man_p = root / c['manifest']
    man = None
    if not man_p.exists():
        reasons.append(f"manifest missing: {c['manifest']}")
    else:
        man = json.loads(man_p.read_text(encoding='utf-8'))
        reasons += manifest_mismatches(man, root)
        if man.get('config_sha256_normalised') != G.config_sha(cfg_path):
            reasons.append('config differs from the manifest (normalised SHA)')
    want = (root / c['baseline']['path']).resolve()
    got = Path(base_path).resolve() if base_path else None
    if got is None:
        reasons.append('no --base given (no fallback)')
    elif got != want:
        reasons.append(f"--base {base_path} is not the v1.6 baseline {c['baseline']['path']}")
    elif not got.exists():
        reasons.append(f'v1.6 baseline missing on this machine: {base_path}')
    else:
        h = file_shas(got)['raw']
        if h != c['baseline']['sha256']:
            reasons.append(f"baseline SHA {h} != pinned {c['baseline']['sha256']}")
        if man is not None and man.get('baseline', {}).get('sha256') != c['baseline']['sha256']:
            reasons.append('manifest baseline SHA differs from the config')
    if scenarios is not None and list(scenarios) != STAGES[:len(scenarios)]:
        reasons.append(f'scenarios {list(scenarios)} are not a prefix of {STAGES} (S2 / S3 / sensitivities are not part of A2)')
    if stage not in STAGES or stage not in c['stages']:
        reasons.append(f'stage {stage} not authorised ({c["stages"]})')
    lg, prob = G.solve_log_rows(log)
    if prob:
        reasons.append(prob)
    else:
        if (lg.stage == stage).any():
            reasons.append(f'{stage} already has a logged call {sorted(set(lg[lg.stage == stage].state))} (zero retries)')
        if len(lg) >= int(c['max_lp_calls']):
            reasons.append('A2 LP budget used')
        if stage in STAGES and STAGES.index(stage) > 0:
            fails = G.prior_stage_pass(out, 'S0', lg)
            if fails:
                reasons.append('S1_EARLIEST needs a PASSED S0 first: ' + '; '.join(fails))
            if not (out / 'S0_shed_by_snapshot_frozen.csv.gz').exists():
                reasons.append('S0 no-harm reference S0_shed_by_snapshot_frozen.csv.gz missing')
    return dict(approved=not reasons, reasons=reasons, head=head, approved_git_sha=asha or None, stage=stage, base=str(base_path),
                config=str(cfg_path), ledger=str(log))


def _atomic_write(df, p):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix='.tmp')
    with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
        df.to_csv(f, index=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)


def read_ledger(p):
    p = Path(p)
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame(columns=LOG_COLS)


def start_attempt(log, stage, manifest_sha, base_sha):
    """persisted STARTED row BEFORE the solver is called; it consumes the stage even if the process dies"""
    lg = read_ledger(log)
    k = int((lg.stage == stage).sum()) + 1
    row = {c: '' for c in LOG_COLS}
    row.update(attempt_id=f'{stage}#{k}', stage=stage, attempt=k, state='STARTED', manifest_sha256=manifest_sha, base_sha256=base_sha,
               started_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    _atomic_write(pd.concat([lg, pd.DataFrame([row])], ignore_index=True)[LOG_COLS], log)
    return row['attempt_id']


def finish_attempt(log, attempt_id, **kw):
    lg = read_ledger(log)
    i = lg.index[lg.attempt_id == attempt_id]
    assert len(i) == 1, f'attempt {attempt_id} not in the ledger'
    kw.setdefault('finished_utc', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    for k, v in kw.items():
        lg.loc[i[0], k] = str(v)
    _atomic_write(lg[LOG_COLS], log)


def acceptance(n, tag, res, shed_S0=None, tol_balance=1e-3, tol_reserve=1e-3, tol_noharm=1e-3):
    """post-solve acceptance of one A2 scenario (pure: works on any solved network); every check must be True"""
    import numpy as np
    m = n.model
    chk, val = {}, {}
    chk['status_ok'] = res.get('status', 'ok') == 'ok'
    chk['termination_optimal'] = str(res.get('termination')) == 'optimal'
    chk['no_integer_vars'] = int(res.get('integer_vars', 0)) == 0
    try:                                                   # nodal balance residual from the solved rows
        c = m.constraints['Bus-nodal_balance']
        resid = np.abs(np.asarray((c.lhs.solution - c.rhs).values, dtype=float))
        val['balance_residual_MW_max'] = float(np.nanmax(resid))
        chk['balance_residual_ok'] = val['balance_residual_MW_max'] <= tol_balance
    except Exception as e:
        val['balance_residual_error'] = repr(e); chk['balance_residual_ok'] = False
    try:
        req = m.constraints['PV16M-reserve_req']
        slack = np.asarray((req.lhs.solution - req.rhs).values, dtype=float)
        val['reserve_slack_MW_min'] = float(np.nanmin(slack))
        chk['reserve_ok'] = val['reserve_slack_MW_min'] >= -tol_reserve
    except Exception as e:
        val['reserve_error'] = repr(e); chk['reserve_ok'] = False
    try:
        socs = [x for x in m.constraints if x.startswith('PV16M-res_su_energy')]
        worst = min(float(np.nanmin(-np.asarray((m.constraints[x].lhs.solution - m.constraints[x].rhs).values, dtype=float))) for x in socs)
        val['reserve_soc_slack_MWh_min'] = worst
        chk['reserve_soc_ok'] = len(socs) == 2 and worst >= -tol_reserve
    except Exception as e:
        val['reserve_soc_error'] = repr(e); chk['reserve_soc_ok'] = False
    lam = n.generators.index[n.generators.carrier == 'load_shed']
    shed = n.generators_t.p.reindex(columns=lam).fillna(0.0)
    val['existing_shed_MWh'] = float(shed.mul(n.snapshot_weightings.generators, axis=0).sum().sum())
    if tag != 'S0':
        if shed_S0 is None:
            chk['no_harm_ok'] = False; val['no_harm'] = 'S0 reference missing'
        else:
            ref = shed_S0.reindex(index=shed.index, columns=shed.columns).fillna(0.0)
            val['no_harm_max_excess_MW'] = float((shed - ref).max().max()) if shed.size else 0.0
            chk['no_harm_ok'] = val['no_harm_max_excess_MW'] <= 0.001 + tol_noharm
    lk = n.links
    fwd = lk.index[(lk.carrier == 'AC_exp') & lk.index.str.endswith('_fwd')]
    if len(fwd):
        rev = fwd.str.replace('_fwd$', '_rev', regex=True)
        d = (lk.p_nom_opt[fwd].values - lk.p_nom_opt[rev].values)
        val['expansion_pair_max_abs_diff_MW'] = float(np.abs(d).max())
        chk['expansion_pairs_equal'] = val['expansion_pair_max_abs_diff_MW'] <= 1e-3
        free = lk.index[lk.p_nom_extendable & (lk.capital_cost <= 0) & ~lk.index.str.endswith('_rev')
                        & ~lk.bus0.astype(str).str.startswith('DC_') & ~lk.bus1.astype(str).str.startswith('DC_')]
        val['free_public_links_built_MW'] = float(lk.p_nom_opt[free].sum()) if len(free) else 0.0
        chk['no_free_public_expansion'] = val['free_public_links_built_MW'] <= 1e-3
    return dict(PASS=all(chk.values()), checks=chk, values=val)
