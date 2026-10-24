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
     (zero retries), the scenario-attempt budget (2) is not used up, and S1_EARLIEST needs a DONE / ok / optimal / pass S0 row
     plus an S0_RESULT.json with acceptance PASS and the SHA-pinned S0 no-harm reference on disk
  7  NEXT-03 A2-FIX-09: the optimizer-call ledger (A2_OPTIMIZER_CALL_LOG.csv) is readable and its top-level call budget (3) is
     not used up. Budgets are separate: max_scenario_attempts = 2 (S0, S1_EARLIEST: parent rows in A2_SOLVE_LOG.csv) and
     max_top_level_optimizer_calls = 3 (S0_COST, S1_SPEED_HIERARCHY, S1_COST: child rows, each STARTED before the call, each
     tied to its parent attempt). Gurobi's internal passes of the hierarchical multi-objective are audit metadata, not calls.
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
CHILD_COLS = ['call_id', 'parent_attempt_id', 'stage', 'kind', 'state', 'started_utc', 'finished_utc', 'status', 'termination',
              'n_vars', 'n_cons', 'n_objectives', 'seconds', 'note']
CALL_PLAN = {'S0': ['S0_COST'], 'S1_EARLIEST': ['S1_SPEED_HIERARCHY', 'S1_COST']}
NO_HARM_REF = 'S0_NO_HARM_REFERENCE.csv'
# armed only by rearch_mech's ledgered A2 wrapper; parent / stage are set for the duration of one scenario attempt
ACCT = dict(armed=False, parent=None, stage=None, log=None, child_log=None, max_top=None)
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


def child_log_path(cfg_path=CFG):
    return paths(cfg_path)[1] / 'A2_OPTIMIZER_CALL_LOG.csv'


def budgets(c):
    return int(c.get('max_scenario_attempts', c.get('max_lp_calls', 2))), int(c.get('max_top_level_optimizer_calls', 3))


def read_child_log(p):
    p = Path(p)
    if not p.exists():
        return pd.DataFrame(columns=CHILD_COLS), None
    try:
        cl = pd.read_csv(p, dtype=str, keep_default_na=False)
    except Exception as e:
        return None, f'optimizer-call ledger unreadable ({e.__class__.__name__}) - refused'
    miss = [k for k in ('call_id', 'parent_attempt_id', 'kind', 'state') if k not in cl.columns]
    return (None, f'optimizer-call ledger malformed (missing {miss}) - refused') if miss else (cl, None)


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
    try:                                     # NEXT-07: a `diagnostic` block is valid only in the exact reserve-probe config
        import post_v16_mainline as PM
        PM.diagnostic_spec(c, cfg_path)
    except ValueError as e:
        reasons.append(f'diagnostic config refused: {e}')
    head = git_fn('rev-parse', 'HEAD').stdout.strip()
    asha = str(c.get('approved_git_sha') or '')
    if not asha:
        reasons.append('approved_git_sha missing')
    elif len(asha) < 8:
        reasons.append(f'approved_git_sha {asha} too short')
    elif not head.startswith(asha):
        anc = git_fn('merge-base', '--is-ancestor', asha, 'HEAD').returncode == 0
        since = set(git_fn('diff', '--name-only', asha, 'HEAD', '--', *G.CLEAN_PATHS).stdout.split())
        cp, rp = Path(cfg_path).resolve(), Path(root).resolve()
        cfg_rel = cp.relative_to(rp).as_posix() if cp.is_relative_to(rp) else None
        since -= registry_adoption_only_change(root / c['manifest'])
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
        reasons += registry_manifest_problems(man)
    import baseline_registry as BR                      # NEXT-09: only the formal 2025 baseline (re-checked before every solve)
    reasons += [r for r in BR.baseline_problems(c.get('baseline'), base_path, root=root, git_fn=git_fn, loss_basis='diagnostic' not in c)
                if r not in reasons and not (r.startswith('no --base') and not base_path)]
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
        max_att, max_top = budgets(c)
        if len(lg) >= max_att:
            reasons.append('A2 scenario-attempt budget used')
        cl, prob2 = read_child_log(out / 'A2_OPTIMIZER_CALL_LOG.csv')
        if prob2:
            reasons.append(prob2)
        elif len(cl) >= max_top:
            reasons.append('A2 top-level optimizer-call budget used')
        if stage in STAGES and STAGES.index(stage) > 0:
            fails = G.prior_stage_pass(out, 'S0', lg)
            if fails:
                reasons.append('S1_EARLIEST needs a PASSED S0 first: ' + '; '.join(fails))
            reasons += no_harm_reference_problems(out)
            reasons += reference_binding_problems(out, lg, c, cfg_path)
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


# ------------------------------------------------------------------------------------------------ NEXT-03 A2-FIX-09 call ledger
def arm_accounting(cfg_path=CFG):
    c, out, log = paths(cfg_path)
    ACCT.update(armed=True, parent=None, stage=None, log=log, child_log=out / 'A2_OPTIMIZER_CALL_LOG.csv', max_top=budgets(c)[1])


def child_start(kind, **meta):
    """persist a STARTED child row BEFORE a top-level optimizer call; refuses (SystemExit) outside an armed parent attempt, for a kind
    not in the stage's plan, for a repeated kind of the same parent, or beyond the top-level budget"""
    if not ACCT['armed'] or not ACCT['parent']:
        raise SystemExit(f'POST_V16_A2: optimizer call {kind} outside a ledgered parent attempt refused')
    stage, parent = ACCT['stage'], ACCT['parent']
    lg = read_ledger(ACCT['log'])
    prow = lg[lg.attempt_id == parent]
    if len(prow) != 1 or prow.state.iloc[0] != 'STARTED':
        raise SystemExit(f'POST_V16_A2: parent {parent} is not a STARTED attempt - {kind} refused')
    if kind not in CALL_PLAN.get(stage, []):
        raise SystemExit(f'POST_V16_A2: {kind} is not in the call plan of {stage} {CALL_PLAN.get(stage)} - refused')
    cl, prob = read_child_log(ACCT['child_log'])
    if prob:
        raise SystemExit('POST_V16_A2: ' + prob)
    if ((cl.parent_attempt_id == parent) & (cl.kind == kind)).any():
        raise SystemExit(f'POST_V16_A2: {kind} already called for {parent} (zero retries) - refused')
    if len(cl) >= int(ACCT['max_top']):
        raise SystemExit('POST_V16_A2: top-level optimizer-call budget used - refused')
    row = {c_: '' for c_ in CHILD_COLS}
    row.update(call_id=f'{parent}/{kind}', parent_attempt_id=parent, stage=stage, kind=kind, state='STARTED',
               started_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), **{k: str(v) for k, v in meta.items()})
    _atomic_write(pd.concat([cl, pd.DataFrame([row])], ignore_index=True)[CHILD_COLS], ACCT['child_log'])
    return row['call_id']


def child_finish(call_id, **kw):
    cl, prob = read_child_log(ACCT['child_log'])
    assert prob is None, prob
    i = cl.index[cl.call_id == call_id]
    assert len(i) == 1, f'call {call_id} not in the optimizer-call ledger'
    kw.setdefault('finished_utc', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    for k, v in kw.items():
        cl.loc[i[0], k] = str(v)
    _atomic_write(cl[CHILD_COLS], ACCT['child_log'])


def close_open_children(parent, note):
    """mark every still-STARTED child of a failed parent as ERROR (rows are never deleted)"""
    cl, prob = read_child_log(ACCT['child_log'])
    if prob or cl is None:
        return
    for cid in cl.call_id[(cl.parent_attempt_id == parent) & (cl.state == 'STARTED')]:
        child_finish(cid, state='ERROR', note=note[:300])


def children_complete(parent, stage):
    """(ok, detail): exactly the planned kinds, each DONE / ok / optimal, and nothing else for this parent"""
    cl, prob = read_child_log(ACCT['child_log'])
    if prob:
        return False, prob
    mine = cl[cl.parent_attempt_id == parent]
    kinds = list(mine.kind)
    ok = sorted(kinds) == sorted(CALL_PLAN[stage]) and (mine.state == 'DONE').all() and (mine.status == 'ok').all() \
        and (mine.termination.str.lower() == 'optimal').all()
    return bool(ok), mine[['kind', 'state', 'status', 'termination', 'n_objectives']].to_dict('records')


# ------------------------------------------------------------------------------------------------ S0 no-harm reference (strict)
def write_no_harm_reference(n, out_dir):
    """S0 existing-customer shed per load_shed unit x snapshot, written once after S0 acceptance; returns its SHA record"""
    lam = n.generators.index[n.generators.carrier == 'load_shed']
    ref = n.generators_t.p.reindex(columns=lam)
    if ref.isna().any().any():
        raise ValueError('S0 shed has missing columns / values - no reference written')
    p = Path(out_dir) / NO_HARM_REF
    ref.to_csv(p, float_format='%.10g')
    return dict(file=NO_HARM_REF, sha256=file_shas(p)['raw'], columns=int(ref.shape[1]), rows=int(ref.shape[0]))


def read_no_harm_reference(out_dir):
    return pd.read_csv(Path(out_dir) / NO_HARM_REF, index_col=[0, 1], parse_dates=[1])


def no_harm_reference_problems(out_dir):
    out_dir = Path(out_dir)
    f, r = out_dir / NO_HARM_REF, out_dir / 'S0_RESULT.json'
    if not f.exists():
        return [f'S0 no-harm reference {NO_HARM_REF} missing']
    try:
        rec = json.loads(r.read_text(encoding='utf-8')).get('no_harm_reference') or {}
    except Exception:
        return ['S0_RESULT.json unreadable for the no-harm reference SHA']
    if rec.get('sha256') != file_shas(f)['raw']:
        return [f'S0 no-harm reference SHA differs from S0_RESULT.json ({rec.get("sha256")})']
    return []


def registry_adoption_only_change(man_p):
    """NEXT-09: {registry path} when the baseline registry differs from the manifest-pinned one only in its three adoption fields
    (so the researcher can adopt in the same config-only commit as the stage approval), else the empty set"""
    import baseline_registry as BR
    try:
        pinned = json.loads(Path(man_p).read_text(encoding='utf-8')).get('baseline_registry_normalised_sha256')
    except Exception:
        return set()
    return {BR.REGISTRY_REL} if pinned and pinned == BR.normalised_sha() else set()


def registry_manifest_problems(man):
    """a manifest that pins the registry must match it (normalised: adoption fields blanked)"""
    import baseline_registry as BR
    pinned = man.get('baseline_registry_normalised_sha256')
    if pinned is None:
        return []
    return [] if pinned == BR.normalised_sha() else ['baseline registry differs from the manifest (normalised SHA)']


def reference_binding_problems(out_dir, lg, c, cfg_path):
    """NEXT-09: the S0 reference S1 reads must be the S0 of THIS config, solved on THIS config's baseline (an old S0 reference copied
    in from another run, e.g. the v1.6 A2 one, is refused)"""
    bad = []
    s0 = lg[(lg.stage == 'S0') & (lg.state == 'DONE')]
    if len(s0) and str(s0.base_sha256.iloc[-1]) != str(c['baseline']['sha256']):
        bad.append(f"S0 reference solved on baseline {s0.base_sha256.iloc[-1][:12]}, not this config's {str(c['baseline']['sha256'])[:12]}")
    try:
        g = json.loads((Path(out_dir) / 'S0_RESULT.json').read_text(encoding='utf-8')).get('gate') or {}
    except Exception:
        return bad + ['S0_RESULT.json unreadable for the reference binding']
    if not g.get('config') or Path(g['config']).resolve() != Path(cfg_path).resolve():
        bad.append(f"S0_RESULT.json was written under config {g.get('config')}, not {cfg_path}")
    return bad


def no_harm_check(n, out_dir, tol=1e-3):
    """strict S1 comparison with the S0 reference: same load_shed units, same snapshots, no duplicates, SHA intact, and the D24
    row built from exactly reference + 0.001 MW; no fill of missing data"""
    import numpy as np
    chk, val = {}, {}
    probs = no_harm_reference_problems(out_dir)
    chk['no_harm_reference_sha_ok'] = not probs
    if probs:
        val['no_harm_reference'] = probs
        return chk, val
    ref = read_no_harm_reference(out_dir)
    lam = list(n.generators.index[n.generators.carrier == 'load_shed'])
    chk['no_harm_units_match'] = set(ref.columns) == set(lam) and not ref.columns.duplicated().any()
    idx_ok = (not ref.index.duplicated().any()) and len(ref.index) == len(n.snapshots) and \
        all((int(a[0]), pd.Timestamp(a[1])) == (int(b[0]), pd.Timestamp(b[1])) for a, b in zip(ref.index, n.snapshots))
    chk['no_harm_snapshots_match'] = bool(idx_ok)
    if not (chk['no_harm_units_match'] and idx_ok):
        val['no_harm'] = dict(missing_units=sorted(set(lam) - set(ref.columns))[:10], extra_units=sorted(set(ref.columns) - set(lam))[:10])
        return chk, val
    shed = n.generators_t.p[lam]
    excess = shed.values - ref[lam].values
    val['no_harm_max_excess_MW'] = float(excess.max()) if excess.size else 0.0
    chk['no_harm_ok'] = val['no_harm_max_excess_MW'] <= 0.001 + tol
    m = n.model
    if 'D24-no_harm_existing_customers' in m.constraints:
        rhs = m.constraints['D24-no_harm_existing_customers'].rhs.transpose('snapshot', 'name').sel(name=lam).values
        val['no_harm_row_vs_reference_max_abs'] = float(np.abs(rhs - (ref[lam].values + 0.001)).max())
        chk['no_harm_row_built_from_reference'] = val['no_harm_row_vs_reference_max_abs'] <= 1e-6
    else:
        chk['no_harm_row_built_from_reference'] = False
    return chk, val


def speed_levels_hold(levels, served_by_year, tol_abs=1e-3, tol_rel=1e-6):
    """S1_EARLIEST: every A1 (year total) level of the hierarchical pre-solve still holds in the final cost-stage solution"""
    rows = []
    for r in levels or []:
        if r.get('stage') != 'A1':
            continue
        got = float(served_by_year.get(int(r['year']), 0.0))
        need = float(r['value']) * (1 - tol_rel) - tol_abs
        rows.append(dict(year=int(r['year']), level=float(r['value']), served=got, ok=got >= need - tol_abs))
    return bool(rows) and all(x['ok'] for x in rows), rows


def acceptance(n, tag, res, shed_S0=None, tol_balance=1e-3, tol_reserve=1e-3, tol_noharm=1e-3, out_dir=None, science=None):
    """post-solve acceptance of one A2 scenario (pure: works on any solved network); every check must be True. NEXT-10U: with a
    config `s0_science_gate` block (science) the S0 also has to pass the scientific reliability gate (next10u_s0_science)"""
    import numpy as np
    m = n.model
    chk, val = {}, {}
    if tag == 'S0' and science is not None:
        import next10u_s0_science as SC
        sv = SC.evaluate(n, science)
        chk['s0_science_pass'] = sv['PASS']
        val['s0_science'] = sv
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
        if out_dir is not None:                            # NEXT-03: strict, file-based (SHA-pinned) reference; no fill
            c_, v_ = no_harm_check(n, out_dir, tol_noharm)
            chk.update(c_); val.update(v_)
        elif shed_S0 is None:
            chk['no_harm_ok'] = False; val['no_harm'] = 'S0 reference missing'
        else:
            ref = shed_S0.reindex(index=shed.index, columns=shed.columns)
            if ref.isna().any().any():
                chk['no_harm_ok'] = False; val['no_harm'] = 'S0 reference does not cover every unit / snapshot (no fill)'
            else:
                val['no_harm_max_excess_MW'] = float((shed - ref).max().max()) if shed.size else 0.0
                chk['no_harm_ok'] = val['no_harm_max_excess_MW'] <= 0.001 + tol_noharm
    if 'PV16M-res_su_energy' in m.constraints and not [x for x in m.constraints if x.startswith('A2F08-seg_soc_')] and len(n.storage_units):
        chk['soc_segment_rows_present'] = False             # NEXT-03 A2-FIX-08 must be in the solved model
    elif len(n.storage_units):
        chk['soc_segment_rows_present'] = True
    lk = n.links
    fwd = pd.Index([x for x in lk.index if lk.carrier[x] == 'AC_exp' and str(x).endswith('_fwd')])
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
