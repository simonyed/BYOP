"""NEXT-07 W4.1: runtime accounting of the A3 pilot (S0 -> S1_EARLIEST -> S3 -> S2_IT1 [-> IT2 -> IT3] -> S3_mS2) through the
independent A3 gate (post_v16_a3_gate.py). Nothing here calls a solver; rearch_mech --a3-config routes every top-level optimizer
call through it:
    stage parent   begin(stage): A3 gate check (approval, SHA, manifest, S0 verdict prerequisite, order, budget) -> STARTED row
                   end(stage, ...): DONE / ERROR row; a failed stage stops the run (no retry)
    child call     linopy.Model.solve (cost stages, developer lex / cost LPs) and the explicit gurobipy hierarchy call of
                   lex_presolve: child_start (planned kind, per-kind count, total budget) BEFORE the call, child_finish after
    kinds          the caller announces a non-default kind with expect(kind) right before its solve (developer LPs, S1 hierarchy);
                   otherwise the stage's cost kind applies (S0_COST, S1_COST, S3_COST, S2_PUBLIC, S3_MS2_COST)
Pure audit helpers (no solver): A2 reproduction of the re-solved S0 / S1, S2 convergence, matched-service audit of S3_mS2 and
the rule that an S2 - S3 efficiency difference is reported only for a converged S2 with a matched S3_mS2.
"""
from __future__ import annotations

import json, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import post_v16_a2_gate as A2G
import post_v16_a3_gate as A3G

TAG_STAGE = {'S0': 'S0', 'S1_EARLIEST': 'S1_EARLIEST', 'S3': 'S3', 'S2': 'S2_IT1', 'S2_it2': 'S2_IT2', 'S2_it3': 'S2_IT3', 'S3_mS2': 'S3_mS2'}
COST_KIND = {'S0': 'S0_COST', 'S1_EARLIEST': 'S1_COST', 'S3': 'S3_COST', 'S2_IT1': 'S2_PUBLIC', 'S2_IT2': 'S2_PUBLIC', 'S2_IT3': 'S2_PUBLIC',
             'S3_mS2': 'S3_MS2_COST'}
A3_SCENARIOS = ['S0', 'S1_EARLIEST', 'S3', 'S2', 'S3_mS2']
ACCT = dict(armed=False, cfg=None, base=None, parent=None, stage=None, next_kind=None, gate_fn=None)


def arm(cfg_path, base, gate_fn=None):
    ACCT.update(armed=True, cfg=Path(cfg_path), base=base, parent=None, stage=None, next_kind=None,
                gate_fn=gate_fn or (lambda st: A3G.check(st, base, cfg_path=cfg_path)))


def disarm():
    ACCT.update(armed=False, cfg=None, base=None, parent=None, stage=None, next_kind=None, gate_fn=None)


def begin(stage):
    """A3 gate for this stage, then the persisted parent STARTED row (consumes the stage even if the process dies)"""
    if not ACCT['armed']:
        raise SystemExit(f'A3: stage {stage} outside an armed A3 run refused')
    if ACCT['parent']:
        raise SystemExit(f"A3: stage {stage} while {ACCT['parent']} is still open - refused")
    g = ACCT['gate_fn'](stage)
    if not g['approved']:
        raise SystemExit('POST_V16_A3_GATE REFUSED: ' + json.dumps(g['reasons']))
    c, out, log, child = A3G.paths(ACCT['cfg'])
    man_p = A3G.ROOT / c['manifest']
    aid = A2G.start_attempt(log, stage, A2G.file_shas(man_p)['raw'] if man_p.exists() else '', c['baseline']['sha256'])
    ACCT.update(parent=aid, stage=stage, next_kind=None)
    return aid, g


def end(state='DONE', **kw):
    c, out, log, child = A3G.paths(ACCT['cfg'])
    aid = ACCT['parent']
    if aid is None:
        return
    if state != 'DONE':
        close_open_children(aid, kw.get('note', state))
    A2G.finish_attempt(log, aid, state=state, **kw)
    ACCT.update(parent=None, stage=None, next_kind=None)


def expect(kind):
    """the next top-level optimizer call of the open stage is of this (planned) kind"""
    ACCT['next_kind'] = kind


def child_start(kind=None, **meta):
    if not ACCT['armed'] or not ACCT['parent']:
        raise SystemExit(f'POST_V16_A3: optimizer call {kind} outside a ledgered A3 stage refused')
    k = kind or ACCT.pop('next_kind', None) or COST_KIND[ACCT['stage']]
    ACCT['next_kind'] = None
    return A3G.child_start(ACCT['parent'], ACCT['stage'], k, cfg_path=ACCT['cfg'], **meta)


def child_finish(call_id, **kw):
    c, out, log, child = A3G.paths(ACCT['cfg'])
    cl, prob = A2G.read_child_log(child)
    assert prob is None, prob
    i = cl.index[cl.call_id == call_id]
    assert len(i) == 1, f'call {call_id} not in the A3 optimizer-call ledger'
    kw.setdefault('finished_utc', datetime.now(timezone.utc).isoformat(timespec='seconds'))
    for k, v in kw.items():
        cl.loc[i[0], k] = str(v)
    A2G._atomic_write(cl[A2G.CHILD_COLS], child)


def close_open_children(parent, note):
    c, out, log, child = A3G.paths(ACCT['cfg'])
    cl, prob = A2G.read_child_log(child)
    if prob or cl is None:
        return
    for cid in cl.call_id[(cl.parent_attempt_id == parent) & (cl.state == 'STARTED')]:
        child_finish(cid, state='ERROR', note=str(note)[:300])


@contextmanager
def ledgered_call(kind=None, **meta):
    cid = child_start(kind, **meta)
    t0 = time.time()
    try:
        yield cid
    except BaseException as e:
        child_finish(cid, state='ERROR', status='exception', seconds=round(time.time() - t0, 1), note=f'{e.__class__.__name__}: {e}'[:300])
        raise


def children_complete(parent, stage):
    """(ok, rows): every child of this parent DONE / ok / optimal, kinds within the plan counts, and the stage's cost (or public)
    kind present exactly once; developer lex LPs only in S2 stages"""
    c, out, log, child = A3G.paths(ACCT['cfg'])
    cl, prob = A2G.read_child_log(child)
    if prob:
        return False, prob
    mine = cl[cl.parent_attempt_id == parent]
    plan = A3G.plan_counts(c).get(stage, {})
    cnt = mine.kind.value_counts().to_dict()
    ok = bool(len(mine)) and all(k in plan and v <= plan[k] for k, v in cnt.items()) and cnt.get(COST_KIND[stage], 0) == 1 \
        and bool((mine.state == 'DONE').all()) and bool((mine.status == 'ok').all()) and bool((mine.termination == 'optimal').all())
    if stage.startswith('S2_IT'):
        ok = ok and cnt.get('S2_DEV_COST', 0) == 1 and cnt.get('S2_DEV_LEX', 0) >= 1
    if stage == 'S1_EARLIEST':
        ok = ok and cnt.get('S1_SPEED_HIERARCHY', 0) == 1
    return ok, mine[['call_id', 'kind', 'state', 'status', 'termination']].to_dict('records')


# ------------------------------------------------------------------------------------------------ audits (pure, no solver)
def a2_reproduction(stage, objective, existing_shed_MWh, shed_frame=None, ref_dir=None, tol_rel=1e-6, tol_shed_MWh=0.05):
    """the A3 re-solve of S0 / S1_EARLIEST must reproduce the accepted A2 result (same model / data): objective within tol_rel and
    the weighted existing-customer shed within tol_shed_MWh. For S0 the per unit x snapshot shed is compared with the SHA-pinned A2
    no-harm reference (reported; every later no-harm row is built from that formal reference, not from the re-solve)."""
    ref_dir = Path(ref_dir)
    f = ref_dir / f'{stage}_RESULT.json'
    rec = json.loads(f.read_text(encoding='utf-8'))
    obj0 = float(rec['result']['objective'])
    shed0 = float(rec['acceptance']['values']['existing_shed_MWh'])
    rel = abs(float(objective) - obj0) / max(1.0, abs(obj0))
    out = dict(stage=stage, a2_result=str(f), a2_objective=obj0, a3_objective=float(objective), objective_rel_diff=rel,
               a2_existing_shed_MWh=shed0, a3_existing_shed_MWh=float(existing_shed_MWh), shed_abs_diff_MWh=abs(float(existing_shed_MWh) - shed0))
    if stage == 'S0' and shed_frame is not None:
        ref = A2G.read_no_harm_reference(ref_dir)
        sf = shed_frame.reindex(index=ref.index, columns=ref.columns)
        out['per_cell_max_abs_diff_MW'] = float(np.nanmax(np.abs(sf.values - ref.values))) if sf.size else 0.0
        out['per_cell_covered'] = not bool(sf.isna().any().any())
    out['PASS'] = rel <= tol_rel and out['shed_abs_diff_MWh'] <= tol_shed_MWh and out.get('per_cell_covered', True)
    return out


def s2_gaps(dc_rows, planned, served):
    """per bus-year developer plan vs public delivery; bad = gap > max(0.5 MW, 1e-3 x plan) (the existing rearch_mech rule)"""
    rows, bad = [], []
    for d in dc_rows:
        k = (d['zone'], d['period'])
        plan, sp = float(planned[k]), float(served[k])
        rows.append(dict(site=k[0], year=k[1], planned_IT_MW=plan, public_served_IT_MW=sp, gap_IT_MW=plan - sp))
        if plan - sp > max(0.5, 1e-3 * plan):
            bad.append(d)
    return rows, bad


def s2_loop(iterate, max_iter):
    """run S2 iterations 1..max_iter; iterate(it) returns the list of site-years below plan; stop at the first consistent one.
    Returns (last iteration, converged). Optional iterations are never run after convergence (no budget filling)."""
    if not 1 <= int(max_iter) <= 3:
        raise ValueError('A3 allows 1-3 S2 iterations')
    it, bad = 0, ['not run']
    for it in range(1, int(max_iter) + 1):
        bad = iterate(it)
        if not bad:
            break
    return it, not bad


def matched_service_audit(target, served, tol_abs=0.5, tol_rel=1e-3):
    """S3_mS2 must deliver the S2_final public service: per bus x year IT MW, the total MW-year and the per-year distribution"""
    keys = sorted(set(target) | set(served))
    rows = [dict(site=k[0], year=k[1], S2_final_IT_MW=float(target.get(k, 0.0)), S3_mS2_IT_MW=float(served.get(k, 0.0))) for k in keys]
    df = pd.DataFrame(rows)
    if df.empty:
        return dict(PASS=False, reason='no service rows'), df
    df['diff_MW'] = df.S3_mS2_IT_MW - df.S2_final_IT_MW
    df['ok'] = df.diff_MW.abs() <= np.maximum(tol_abs, tol_rel * df.S2_final_IT_MW.abs())
    yr = df.groupby('year')[['S2_final_IT_MW', 'S3_mS2_IT_MW']].sum()
    yr_ok = bool(((yr.S3_mS2_IT_MW - yr.S2_final_IT_MW).abs() <= np.maximum(tol_abs, tol_rel * yr.S2_final_IT_MW.abs())).all())
    tot = dict(S2_final_MW_year=float(df.S2_final_IT_MW.sum()), S3_mS2_MW_year=float(df.S3_mS2_IT_MW.sum()))
    tot_ok = abs(tot['S3_mS2_MW_year'] - tot['S2_final_MW_year']) <= max(tol_abs, tol_rel * abs(tot['S2_final_MW_year']))
    return dict(PASS=bool(df.ok.all()) and yr_ok and tot_ok, bus_year_ok=bool(df.ok.all()), year_distribution_ok=yr_ok, total_ok=tot_ok,
                by_year=yr.reset_index().to_dict('records'), **tot), df


def efficiency_claim(s2_converged, matched):
    """an S2 - S3 social-efficiency difference may be reported only for a converged S2_final and a matched-service S3_mS2"""
    if not s2_converged:
        return 'BLOCKED_S2_NOT_CONVERGED'
    if not (matched or {}).get('PASS'):
        return 'BLOCKED_S3_MS2_NOT_MATCHED'
    return 'ALLOWED'
