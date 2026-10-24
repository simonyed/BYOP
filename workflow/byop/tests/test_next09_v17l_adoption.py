"""NEXT-09 (2026-10-23): v1.7L baseline freeze / adoption registry / S0-S1 rerun gates. Static only (no solver)."""
from __future__ import annotations

import copy, hashlib, json, subprocess, sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import baseline_registry as BR  # noqa: E402
import byop_paths as BP  # noqa: E402
import post_v16_a2_gate as A2G  # noqa: E402
import post_v16_a3_gate as A3G  # noqa: E402

CFG17 = WF / 'config/config.byop_post_v17l_s0s1.yaml'
CFGA2 = WF / 'config/config.byop_post_v16_a2.yaml'
ML16 = WF / 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml'
ML17 = WF / 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v17l.yaml'
OK_GIT = lambda *a: SimpleNamespace(returncode=0, stdout='', stderr='')
NO_GIT = lambda *a: SimpleNamespace(returncode=1, stdout='', stderr='')


def reg():
    return copy.deepcopy(BR.load())


def adopt(r, **kw):
    r['adoption'].update(dict(adoption_status='ADOPTED', adopted_git_sha='0123456789abcdef', adopted_by='researcher'), **kw)
    return r


def fake_root(tmp_path, r):
    """a scratch root holding both registry baselines (fake bytes; the registry SHAs are set to them), the auth source and the record"""
    for k, e in r['baselines'].items():
        p = tmp_path / e['path']; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(f'fake {k}'.encode())
        e['sha256'] = hashlib.sha256(p.read_bytes()).hexdigest()
    src = tmp_path / r['authorization_source']; src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text('instruction\n', encoding='utf-8')
    r['authorization_source_sha256'] = hashlib.sha256(b'instruction\n').hexdigest()
    rec = tmp_path / r['baselines'][r['candidate']]['record']; rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text('{}', encoding='utf-8')
    return r


# ------------------------------------------------------------------------------------------------ registry
def test_registry_pins_match_paths_and_seal():
    r = BR.load()
    v16, v17 = r['baselines']['v16'], r['baselines']['v17l']
    assert r['previous_formal'] == 'v16' and r['candidate'] == 'v17l'
    # adopted by the researcher (config-only commit 7f4e27cb, 2026-10-24); formal = v1.7L with no adoption problems
    assert r['adoption'] == dict(adoption_status='ADOPTED', adopted_git_sha='c0b29f34709ed88229b42d7fd368ddd6370b5301',
                                 adopted_by='sw2434@cornell.edu')
    assert BR.formal(r)[0] == 'v17l' and BR.formal(r)[2] == []
    assert v16['sha256'] == BP.BASE_TAMU_V16_SHA256
    assert (WF.parent / v16['path']).resolve() == BP.BASE_TAMU_V16.resolve()
    assert (WF.parent / v17['path']).resolve() == BR.BASE_TAMU_V17L.resolve() and v17['sha256'] == BR.BASE_TAMU_V17L_SHA256
    seal = json.loads((WF.parent / v17['seal']).read_text(encoding='utf-8'))
    assert seal['candidate_sha256'] == v17['sha256'] and seal['solved_code_sha'] == v17['solved_code_sha']
    assert (v16['calibration_transmission_losses'], v16['meta_transmission_losses']) == (0, 2)
    assert (v17['calibration_transmission_losses'], v17['meta_transmission_losses']) == (2, 2)
    src = WF.parent / r['authorization_source']
    assert A2G.file_shas(src)['lf'] == r['authorization_source_sha256']


def test_formal_before_and_after_adoption(tmp_path):
    r = fake_root(tmp_path, reg())
    assert BR.formal(r, tmp_path, OK_GIT)[:1] == ('v16',)
    k, e, bad = BR.formal(adopt(copy.deepcopy(r)), tmp_path, OK_GIT)
    assert (k, bad) == ('v17l', []) and e['path'] == r['baselines']['v17l']['path']
    for field, val in (('adopted_by', None), ('adopted_git_sha', None), ('adopted_git_sha', 'abc')):
        k, e, bad = BR.formal(adopt(copy.deepcopy(r), **{field: val}), tmp_path, OK_GIT)
        assert k is None and e is None and bad                      # an incomplete ADOPTED record never falls back to v1.6
    assert BR.formal(adopt(copy.deepcopy(r)), tmp_path, NO_GIT)[2]    # adopted_git_sha not an ancestor of HEAD
    r2 = adopt(copy.deepcopy(r)); r2['authorization_source_sha256'] = '0' * 64
    assert any('authorization source' in x for x in BR.formal(r2, tmp_path, OK_GIT)[2])


def test_normalised_sha_ignores_only_adoption_fields(tmp_path):
    d = yaml.safe_load(BR.REGISTRY.read_text(encoding='utf-8'))
    p = tmp_path / 'r.yaml'
    p.write_text(yaml.safe_dump(d), encoding='utf-8'); h0 = BR.normalised_sha(p)
    assert h0 == BR.normalised_sha(BR.REGISTRY)
    d['baseline_registry']['adoption'].update(adoption_status='ADOPTED', adopted_git_sha='x' * 40, adopted_by='me')
    p.write_text(yaml.safe_dump(d), encoding='utf-8'); assert BR.normalised_sha(p) == h0
    d['baseline_registry']['baselines']['v17l']['sha256'] = '0' * 64
    p.write_text(yaml.safe_dump(d), encoding='utf-8'); assert BR.normalised_sha(p) != h0


def test_baseline_problems_fail_closed(tmp_path):
    r = fake_root(tmp_path, reg())
    pin = lambda k: dict(path=r['baselines'][k]['path'], sha256=r['baselines'][k]['sha256'])
    base = lambda k: str(tmp_path / r['baselines'][k]['path'])
    # before adoption: v1.7L refused (not ADOPTED); v1.6 refused for formal runs by the loss-basis rule only
    p17 = BR.baseline_problems(pin('v17l'), base('v17l'), r, tmp_path, OK_GIT)
    assert any('v17l is not the formal baseline (not ADOPTED)' in x for x in p17)
    p16 = BR.baseline_problems(pin('v16'), base('v16'), r, tmp_path, OK_GIT)
    assert len(p16) == 1 and 'loss-basis mismatch on v16' in p16[0]
    assert BR.baseline_problems(pin('v16'), base('v16'), r, tmp_path, OK_GIT, loss_basis=False) == []
    # after adoption: v1.7L clean, v1.6 superseded, wrong --base / wrong bytes / unregistered file refused
    a = adopt(copy.deepcopy(r))
    assert BR.baseline_problems(pin('v17l'), base('v17l'), a, tmp_path, OK_GIT) == []
    assert any('superseded' in x for x in BR.baseline_problems(pin('v16'), base('v16'), a, tmp_path, OK_GIT))
    assert any('is not the formal 2025 baseline v17l' in x for x in BR.baseline_problems(pin('v17l'), base('v16'), a, tmp_path, OK_GIT))
    assert any('no --base' in x for x in BR.baseline_problems(pin('v17l'), None, a, tmp_path, OK_GIT))
    assert any('unregistered' in x for x in BR.baseline_problems(dict(path='x.nc', sha256='0'), base('v17l'), a, tmp_path, OK_GIT))
    (tmp_path / r['baselines']['v17l']['path']).write_bytes(b'tampered')
    assert any('SHA differs' in x for x in BR.baseline_problems(pin('v17l'), base('v17l'), a, tmp_path, OK_GIT))


def test_meta_loss_basis(tmp_path):
    r = fake_root(tmp_path, reg())
    a = adopt(copy.deepcopy(r))
    meta = lambda tl: dict(solving=dict(options=dict(transmission_losses=tl)))
    assert BR.meta_loss_problems(meta(2), a, tmp_path, OK_GIT) == []
    assert BR.meta_loss_problems(meta(0), a, tmp_path, OK_GIT) and BR.meta_loss_problems({}, a, tmp_path, OK_GIT)


# ------------------------------------------------------------------------------------------------ configs and run entry
def test_s0s1_config_is_the_a2_config_on_v17l():
    a, b = A2G.load(CFGA2), A2G.load(CFG17)
    assert (b['run_authorization'], b['approved_git_sha'], b['approved_by']) == ('NOT_APPROVED', None, None)
    changed = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert changed == {'authorization_source', 'authorization_source_sha256', 'manifest', 'mainline_config', 'out_dir',
                       'baseline', 'loss_basis', 'design', 'acceptance'}
    assert {k for k in a['design'] if a['design'][k] != b['design'][k]} == {'no_harm'}
    assert {k for k in a['acceptance'] if a['acceptance'][k] != b['acceptance'][k]} == {'no_harm_reference'}
    for k in ('stage', 'stages', 'max_scenario_attempts', 'max_top_level_optimizer_calls', 'optimizer_call_plan', 'max_retries', 'solver'):
        assert a[k] == b[k]
    r = BR.load()['baselines']['v17l']
    assert b['baseline'] == dict(path=r['path'], sha256=r['sha256'])
    others = [A2G.load(p) for p in (WF / 'config').glob('config.byop_*.yaml') if p != CFG17 and 'post_v16' in yaml.safe_load(p.read_text(encoding='utf-8'))]
    assert all(o.get('out_dir') != b['out_dir'] and o.get('manifest') != b['manifest'] for o in others)    # never an old ledger / manifest
    assert 'BYOP_NEXT_09' in b['manifest'] and 'post_v16_a2' not in b['out_dir']


def test_mainline_config_v17l_differs_only_in_baseline_labels():
    a = yaml.safe_load(ML16.read_text(encoding='utf-8')); b = yaml.safe_load(ML17.read_text(encoding='utf-8'))
    assert b['inputs']['baseline'] == 'results/BYOP/baseline_2025_tamu_v17_lossy/baseline_2025_tamu_v17_lossy_prepared.nc'
    assert {k for k in a['inputs'] if a['inputs'][k] != b['inputs'][k]} == {'baseline'}
    assert {k for k in a['mainline'] if a['mainline'][k] != b['mainline'][k]} == {'case_id', 'stage'}
    assert set(a) == set(b)


def test_run_entry_v17l():
    s = (WF / 'byop/run/run_post_v16_a2.sh').read_text(encoding='utf-8')
    out = subprocess.run(['bash', str(WF / 'byop/run/run_post_v16_a2.sh'), 'v17l_s0s1'], capture_output=True, text=True, cwd=str(WF),
                         env={**__import__('os').environ, 'DRY': '1'}).stdout
    assert '--a2-config config/config.byop_post_v17l_s0s1.yaml' in out and '--config config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v17l.yaml' in out
    assert 'baseline_2025_tamu_v17_lossy/baseline_2025_tamu_v17_lossy_prepared.nc' in out and 'post_v17l_s0s1/POST_V17L_S0S1' in out
    assert '--scenarios S0 S1_EARLIEST' in out and '--no-harm off' not in out
    for k in ('v17l_freeze', 'v17l_registry', 'v17l_static', 'v17l_manifest', 'v17l_gate'):
        assert f'  {k})' in s


# ------------------------------------------------------------------------------------------------ gates
def test_s0s1_gate_refuses_until_approved():
    """v1.7L is ADOPTED; the S0 / S1 config is still NOT_APPROVED (researcher: do not run S0 / S1 yet)"""
    g = A2G.check('S0', str(BR.BASE_TAMU_V17L), cfg_path=CFG17)
    r = g['reasons']
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in r and 'approved_by missing' in r
    assert not any('formal' in x or 'loss-basis' in x for x in r)


def test_guard_refuses_v17l_until_approved(capsys):
    import rearch_mech as R
    a = SimpleNamespace(a2_config=str(CFG17), a3_config=None, base=str(BR.BASE_TAMU_V17L), mainline=True,
                        config='config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v17l.yaml', out=str(WF / 'results/BYOP/post_v17l_s0s1/POST_V17L_S0S1'),
                        no_harm='on', attribution=False, relax=[], scenarios=['S0', 'S1_EARLIEST'], start=2026, end=2031, sample_weeks=26,
                        calibrate=False, erm_cal=None, s0_calibrate=False, s0_cal_file=None)
    with pytest.raises(SystemExit) as e:
        R.post_v16_guard(a)
    o = capsys.readouterr().out
    assert e.value.code == 3 and 'not ADOPTED' not in o and 'run_authorization=NOT_APPROVED' in o


def test_old_configs_refused_after_adoption(monkeypatch, tmp_path):
    """once v1.7L is ADOPTED, every v1.6-pinned post-v1.6 config (A2, A3, probes) is superseded"""
    r = adopt(reg())
    monkeypatch.setattr(BR, 'adoption_problems', lambda *a, **k: [])
    for cfg in ('config.byop_post_v16_a2.yaml', 'config.byop_post_v16_a3.yaml', 'config.byop_post_v16_n07_lossless_probe.yaml'):
        c = A2G.load(WF / 'config' / cfg)
        p = BR.baseline_problems(c['baseline'], str(BP.BASE_TAMU_V16), r, loss_basis='diagnostic' not in c)
        assert any('superseded' in x for x in p), cfg


def test_s1_reference_binding(tmp_path):
    c = A2G.load(CFG17)
    lg = pd.DataFrame([dict(attempt_id='S0#1', stage='S0', state='DONE', base_sha256=BP.BASE_TAMU_V16_SHA256)])
    (tmp_path / 'S0_RESULT.json').write_text(json.dumps(dict(gate=dict(config=str(CFGA2)))), encoding='utf-8')
    bad = A2G.reference_binding_problems(tmp_path, lg, c, CFG17)
    assert any('solved on baseline a623fb6dd1bb' in x for x in bad) and any('written under config' in x for x in bad)
    lg.loc[0, 'base_sha256'] = c['baseline']['sha256']
    (tmp_path / 'S0_RESULT.json').write_text(json.dumps(dict(gate=dict(config=str(CFG17)))), encoding='utf-8')
    assert A2G.reference_binding_problems(tmp_path, lg, c, CFG17) == []


def test_a3_reference_must_be_on_the_config_baseline(tmp_path):
    """the v1.6 A2 S0 / S1 results (old no-harm reference) can never serve an A3 config on v1.7L"""
    c = A3G.load()
    old = A3G.reference_problems(c)                                   # the real v1.6 A2 reference: consistent with the v1.6 A3 config
    assert not any('was not solved on' in x for x in old)
    c17 = dict(c, baseline=dict(path=BR.load()['baselines']['v17l']['path'], sha256=BR.BASE_TAMU_V17L_SHA256))
    bad = A3G.reference_problems(c17)
    assert sum('was not solved on' in x for x in bad) == 2


def test_registry_adoption_only_change(tmp_path):
    m = tmp_path / 'm.json'
    m.write_text(json.dumps(dict(baseline_registry_normalised_sha256=BR.normalised_sha())), encoding='utf-8')
    assert A2G.registry_adoption_only_change(m) == {BR.REGISTRY_REL} and A2G.registry_manifest_problems(json.loads(m.read_text())) == []
    m.write_text(json.dumps(dict(baseline_registry_normalised_sha256='0' * 64)), encoding='utf-8')
    assert A2G.registry_adoption_only_change(m) == set() and A2G.registry_manifest_problems(json.loads(m.read_text()))
    assert A2G.registry_adoption_only_change(tmp_path / 'missing.json') == set()


def test_frozen_files_untouched_by_new_code():
    src = (WF / 'byop/build/freeze_baseline_v17l.py').read_text(encoding='utf-8')
    assert 'never overwritten' in src and 'to_netcdf' not in src and 'export_to_netcdf' not in src and "adoption_status'] =" not in src
    for p in ('byop/model/baseline_registry.py', 'byop/tests/structural_n09_v17l_swap.py'):
        s = (WF / p).read_text(encoding='utf-8')
        assert 'to_netcdf' not in s and '.solve(' not in s.replace('linopy.Model.solve', '')
