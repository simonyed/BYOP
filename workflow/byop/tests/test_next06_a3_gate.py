"""NEXT-06 W3: A3 gate static tests and solver-free failure injection (no solver, ledgers only in tmp directories)."""
from __future__ import annotations

import json, sys
from pathlib import Path

import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))


def cfg(tmp_path, verdict='CALIBRATED_PASS', **over):
    c = yaml.safe_load((WF / 'config/config.byop_post_v16_a3.yaml').read_text(encoding='utf-8'))
    st = tmp_path / 'S0_SCIENTIFIC_STATUS.json'
    st.write_text(json.dumps(dict(S0_RELIABILITY_VERDICT=verdict)))
    c['post_v16'].update(out_dir=str(tmp_path / 'out'), manifest=str(tmp_path / 'MANIFEST.json'),
                         prerequisites=[dict(file=str(st), field='S0_RELIABILITY_VERDICT', allowed=['CALIBRATED_PASS', 'PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS'])], **over)
    p = tmp_path / 'cfg.yaml'
    p.write_text(yaml.safe_dump(c), encoding='utf-8')
    return p


def test_real_config_locked_plan_fits_budget_and_blocks_on_s0():
    import post_v16_a3_gate as A3
    c = A3.load()
    assert c['run_authorization'] == 'NOT_APPROVED' and c['stage'] == 'A3' and c['approved_by'] is None
    assert A3.max_planned_calls(c) == 29 <= c['max_top_level_optimizer_calls'] == 30
    assert A3.plan_counts(c)['S2_IT1'] == {'S2_DEV_LEX': 6, 'S2_DEV_COST': 1, 'S2_PUBLIC': 1}
    g = A3.check('S3', None)
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons']
    assert any('S0_RELIABILITY_VERDICT' in r for r in g['reasons'])            # the unresolved S0 verdict blocks A3


def test_approval_from_other_stage_never_carries_over(tmp_path):
    import post_v16_a3_gate as A3
    g = A3.check('S0', None, cfg_path=cfg(tmp_path, stage='A2', run_authorization='APPROVED', approved_by='x', approved_git_sha='0' * 40))
    assert any('is not A3' in r for r in g['reasons']) and any('manifest missing' in r for r in g['reasons'])


def test_prerequisite_verdicts(tmp_path):
    import post_v16_a3_gate as A3
    assert any('S0_RELIABILITY_VERDICT' in r for r in A3.check('S0', None, cfg_path=cfg(tmp_path, verdict='BASELINE_RELIABILITY_UNRESOLVED'))['reasons'])
    ok = A3.check('S0', None, cfg_path=cfg(tmp_path, verdict='PHYSICAL_SCARCITY_VALIDATED_WITH_LIMITS'))['reasons']
    assert not any('S0_RELIABILITY_VERDICT' in r for r in ok)


def test_order_duplicate_and_corrupt_ledgers(tmp_path):
    import post_v16_a3_gate as A3
    import post_v16_a2_gate as A2G
    p = cfg(tmp_path)
    c, out, log, child = A3.paths(p)
    assert any('needs a PASSED S1_EARLIEST' in r for r in A3.check('S3', None, cfg_path=p)['reasons'])
    aid = A2G.start_attempt(log, 'S0', 'm', 'b')                                       # crash after STARTED
    assert any('already has a logged call' in r for r in A3.check('S0', None, cfg_path=p)['reasons'])
    A2G.finish_attempt(log, aid, state='DONE', status='ok', termination='optimal', **{'pass': True})
    a1 = A2G.start_attempt(log, 'S1_EARLIEST', 'm', 'b'); A2G.finish_attempt(log, a1, state='DONE', status='ok', termination='optimal', **{'pass': True})
    a3 = A2G.start_attempt(log, 'S3', 'm', 'b'); A2G.finish_attempt(log, a3, state='DONE', status='ok', termination='optimal', **{'pass': True})
    a4 = A2G.start_attempt(log, 'S2_IT1', 'm', 'b'); A2G.finish_attempt(log, a4, state='DONE', status='ok', termination='optimal', **{'pass': True})
    r = A3.check('S3_mS2', None, cfg_path=p)['reasons']
    assert not any('needs a PASSED' in x for x in r)                                    # S2_IT2 / IT3 optional
    child.parent.mkdir(parents=True, exist_ok=True); child.write_text('garbage\n1\n')
    assert any('optimizer-call ledger malformed' in x for x in A3.check('S3_mS2', None, cfg_path=p)['reasons'])


def test_child_calls_plan_counts_and_budget(tmp_path):
    import post_v16_a3_gate as A3
    import post_v16_a2_gate as A2G
    p = cfg(tmp_path, max_top_level_optimizer_calls=8)
    c, out, log, child = A3.paths(p)
    with pytest.raises(SystemExit):
        A3.child_start('S2_IT1#1', 'S2_IT1', 'S2_DEV_LEX', cfg_path=p)               # no STARTED parent
    aid = A2G.start_attempt(log, 'S2_IT1', 'm', 'b')
    with pytest.raises(SystemExit):
        A3.child_start(aid, 'S2_IT1', 'S3_COST', cfg_path=p)                        # not in this stage's plan
    for _ in range(6):
        A3.child_start(aid, 'S2_IT1', 'S2_DEV_LEX', cfg_path=p)
    with pytest.raises(SystemExit):
        A3.child_start(aid, 'S2_IT1', 'S2_DEV_LEX', cfg_path=p)                     # 7th lex level: beyond the plan count
    A3.child_start(aid, 'S2_IT1', 'S2_DEV_COST', cfg_path=p)
    A3.child_start(aid, 'S2_IT1', 'S2_PUBLIC', cfg_path=p)                          # 8 = total budget in this test config
    a2 = A2G.start_attempt(log, 'S3_mS2', 'm', 'b')
    with pytest.raises(SystemExit):
        A3.child_start(a2, 'S3_mS2', 'S3_MS2_COST', cfg_path=p)                     # total top-level budget used
