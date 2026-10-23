"""NEXT-02 A2 static unit tests (zero solver: models are built, solutions are injected by hand, nothing is optimised)."""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))


@pytest.fixture(autouse=True)
def _no_solver(monkeypatch):
    linopy = pytest.importorskip('linopy')
    monkeypatch.setattr(linopy.Model, 'solve', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('solver call in a static test')))


def multiperiod(P=(2026, 2027, 2028, 2029, 2030, 2031), steps=2):
    pypsa = pytest.importorskip('pypsa')
    mi = pd.MultiIndex.from_product([list(P), pd.date_range('2030-01-01', periods=steps, freq='3h')], names=['period', 'timestep'])
    n = pypsa.Network(); n.set_snapshots(mi); n.investment_periods = list(P)
    n.snapshot_weightings.loc[:, :] = 3.0
    n.add('Bus', ['a', 'b']); n.add('Carrier', ['CCGT', 'OCGT', 'battery', 'AC_exp', 'load_shed'])
    n.add('Generator', 'a CCGT', bus='a', carrier='CCGT', p_nom=5000, marginal_cost=30, build_year=2025, lifetime=50)
    n.add('Generator', 'b OCGT pub2029', bus='b', carrier='OCGT', p_nom_extendable=True, capital_cost=1e5, marginal_cost=50,
          build_year=2029, lifetime=30)
    n.add('Generator', 'b load_shed', bus='b', carrier='load_shed', p_nom=1e5, marginal_cost=35685, build_year=2025, lifetime=100)
    n.add('StorageUnit', 'a bat', bus='a', carrier='battery', p_nom=500, max_hours=4, efficiency_dispatch=0.9, efficiency_store=0.95,
          build_year=2025, lifetime=20)
    n.add('Line', 'L', bus0='a', bus1='b', s_nom=1000, x=0.1)
    n.add('Load', 'l', bus='b', p_set=3000.0)
    return n


def add_pair(n, cc=2e4, p=2029):
    for suf, b0, b1, c_ in (('fwd', 'a', 'b', cc), ('rev', 'b', 'a', 0.0)):
        n.add('Link', f'LL_exp{p}_{suf}', bus0=b0, bus1=b1, carrier='AC_exp', p_nom_extendable=True, p_nom_max=1000.0, capital_cost=c_,
              build_year=p, lifetime=60, efficiency=1.0)


def add_corridor_rows(n, p=2029, cap=1000.0):
    """the exact rows v240_mech.extra adds for STATE['corridors'] (M2-line_sym / M2-line_cap)"""
    m = n.model
    lp = m['Link-p_nom']
    f = f'LL_exp{p}_fwd'
    m.add_constraints(lp.sel(name=f) - lp.sel(name=f.replace('_fwd', '_rev')) == 0, name=f'M2-line_sym_{f}')
    m.add_constraints(lp.sel(name=[f]).sum('name') <= cap, name='M2-line_cap_LL')


# ------------------------------------------------------------------------------------------------ A2-FIX-01
def test_pair_without_equality_is_free_and_flagged():
    import post_v16_mainline as PM
    n = multiperiod(); add_pair(n); n.optimize.create_model(multi_investment_periods=True)
    pa = PM.expansion_pair_audit(n, n.model, approval_year={'LL_exp2029_fwd': 2027})
    assert len(pa) == 1 and not pa.PASS.iloc[0] and not pa.reverse_only_rejected.iloc[0]
    led = PM.public_expansion_ledger(n, list(n.investment_periods), m=n.model)
    assert led.set_index('name').status['LL_exp2029_rev'] == 'FREE_FORBIDDEN'
    assert PM.public_expansion_ledger(n, list(n.investment_periods)).set_index('name').status['LL_exp2029_rev'] == 'PAIR_UNVERIFIED'


def test_pair_with_equality_rejects_reverse_only_and_pays_once():
    import post_v16_mainline as PM
    n = multiperiod(); add_pair(n); n.optimize.create_model(multi_investment_periods=True); add_corridor_rows(n)
    pa = PM.expansion_pair_audit(n, n.model, corridors=[dict(corridor='LL', cap_MW=1000.0)], approval_year={'LL_exp2029_fwd': 2027})
    r = pa.iloc[0]
    assert r.PASS and r.reverse_only_rejected and r.equal_build_accepted and r.corridor_cap_row_ok
    assert r.obj_coef_fwd > 0 and r.obj_coef_rev == 0          # one positive investment per MW of two-way capacity
    led = PM.public_expansion_ledger(n, list(n.investment_periods), m=n.model).set_index('name')
    assert led.status['LL_exp2029_rev'] == 'ENDOGENOUS_PRICED_VIA_FWD_EQUALITY'


def test_committed_links_are_fixed_and_outside_expansion_rows():
    import post_v16_mainline as PM
    n = multiperiod()
    for suf, b0, b1 in (('fwd', 'a', 'b'), ('rev', 'b', 'a')):
        n.add('Link', f'DWB_Stage_2_{suf}', bus0=b0, bus1=b1, carrier='AC_base_committed', p_nom=1000.0, build_year=2026, lifetime=60)
    add_pair(n); n.optimize.create_model(multi_investment_periods=True); add_corridor_rows(n)
    ca = PM.committed_links_audit(n, n.model)
    assert len(ca) == 2 and ca.PASS.all()


# ------------------------------------------------------------------------------------------------ A2-FIX-02
def test_counter_example_2027_order_2029_cod_unavailable_before():
    import post_v16_mainline as PM
    n = multiperiod(); add_pair(n); n.optimize.create_model(multi_investment_periods=True); add_corridor_rows(n)
    co = PM.cod_activity_audit(n, n.model, approval_year={'b OCGT pub2029': 2027, 'LL_exp2029_fwd': 2027}).set_index('name')
    r = co.loc['b OCGT pub2029']
    assert r.PASS and r.approval_year == 2027 and r.build_year == 2029 and r.first_active_period == 2029 and not r.active_before_build
    assert co.loc['LL_exp2029_rev'].priced_via == 'LL_exp2029_fwd' and co.loc['LL_exp2029_rev'].PASS


def test_committed_cost_ledger_splits_sunk_and_unpaid_outside_objective():
    import post_v16_mainline as PM
    c = PM.committed_cost_ledger('base')
    assert set(c.asset_id) == {'DWB_Stage_2', 'PBRP-765-A', 'PBRP-765-B'} and not c.in_objective.any()
    assert np.allclose(c.sunk_by_2025_MUSD + c.unpaid_commitment_after_2025_MUSD, c.total_cost_MUSD)
    assert (c.total_cost_MUSD > 0).all()


# ------------------------------------------------------------------------------------------------ A2-FIX-03
def test_reserve_energy_bounded_at_interval_start():
    import post_v16_mainline as PM
    n = multiperiod(); n.optimize.create_model(multi_investment_periods=True)
    PM.add_operating_reserve(n, n.snapshots)
    m = n.model
    c = m.constraints['PV16M-res_su_energy_start'].lhs
    sn = n.snapshots[3]
    row = c.sel(name='a bat', snapshot=sn)
    v, co = np.asarray(row.vars.values).ravel(), np.asarray(row.coeffs.values).ravel()
    lab = lambda var: int(m[var].sel(name='a bat', snapshot=sn).labels.values)
    d = pd.Series(co[v != -1]).groupby(v[v != -1]).sum()
    assert np.isclose(d[lab('StorageUnit-state_of_charge')], -1.0)        # constraint: tau r / eff - start <= 0
    assert np.isclose(d[lab('StorageUnit-p_store')], 3.0 * 0.95)            # start = soc - w eff_s p_store + w / eff_d p_dispatch
    assert np.isclose(d[lab('StorageUnit-p_dispatch')], -3.0 / 0.9)
    assert np.isclose(d[lab('PV16M-res_su')], 1.0 / 0.9)


def test_interval_start_soc_equals_previous_soc_on_a_hand_path():
    """inject a hand-made SOC path that satisfies PyPSA's own balance; the start expression must reproduce soc(t-1)"""
    import post_v16_mainline as PM
    n = multiperiod(P=(2026,), steps=4)
    n.storage_units.loc['a bat', 'cyclic_state_of_charge'] = False
    n.optimize.create_model(multi_investment_periods=True)
    m = n.model
    e, _ = PM.interval_start_soc(n, n.snapshots, ['a bat'])
    ps = np.array([100.0, 0.0, 0.0, 50.0]); pd_ = np.array([0.0, 200.0, 50.0, 0.0])
    soc = np.zeros(4); prev = 1500.0
    for i in range(4):
        soc[i] = prev + 3.0 * (0.95 * ps[i] - pd_[i] / 0.9); prev = soc[i]
    for name, vals in (('StorageUnit-state_of_charge', soc), ('StorageUnit-p_store', ps), ('StorageUnit-p_dispatch', pd_)):
        lab = m[name].labels
        full = np.zeros(lab.shape)
        idx = list(lab.coords['name'].values).index('a bat')
        if lab.dims[0] == 'snapshot':
            full[:, idx] = vals
        else:
            full[idx, :] = vals
        m.variables[name].solution = lab.copy(data=full)
    start = np.asarray(e.sel(name='a bat').solution.values).ravel()
    assert np.allclose(start, np.r_[1500.0, soc[:-1]])


# ------------------------------------------------------------------------------------------------ A2-FIX-06 / 07 gate
def _cfg(tmp_path, **over):
    c = yaml.safe_load((WF / 'config/config.byop_post_v16_a2.yaml').read_text(encoding='utf-8'))
    c['post_v16'].update(out_dir=str(tmp_path / 'out'), manifest=str(tmp_path / 'MANIFEST.json'), **over)
    p = tmp_path / 'cfg.yaml'
    p.write_text(yaml.safe_dump(c), encoding='utf-8')
    return p


def test_a2_gate_refuses_not_approved_and_never_inherits_a1(tmp_path):
    import post_v16_a2_gate as A2G
    g = A2G.check('S0', None, cfg_path=_cfg(tmp_path))
    assert not g['approved'] and 'run_authorization=NOT_APPROVED' in g['reasons'] and 'approved_by missing' in g['reasons']
    g = A2G.check('S0', None, cfg_path=_cfg(tmp_path, stage='A1', run_authorization='APPROVED', approved_by='x', approved_git_sha='0' * 40))
    assert any('is not A2' in r for r in g['reasons'])
    assert any('manifest missing' in r for r in g['reasons'])


def test_a2_gate_order_budget_and_started_rows(tmp_path):
    import post_v16_a2_gate as A2G
    cfg = _cfg(tmp_path)
    g = A2G.check('S1_EARLIEST', None, cfg_path=cfg)
    assert any('needs a PASSED S0' in r for r in g['reasons']) and any('no-harm reference' in r for r in g['reasons'])
    _, out, log = A2G.paths(cfg)
    aid = A2G.start_attempt(log, 'S0', 'm', 'b')                                   # STARTED persisted before a solver
    assert A2G.read_ledger(log).state.tolist() == ['STARTED']
    g = A2G.check('S0', None, cfg_path=cfg)
    assert any('already has a logged call' in r for r in g['reasons'])               # a crash still consumes the stage
    A2G.finish_attempt(log, aid, state='DONE', status='ok', termination='optimal', **{'pass': True})
    (out / 'S0_RESULT.json').write_text(json.dumps(dict(acceptance=dict(PASS=False, checks=dict(reserve_ok=False)))))
    g = A2G.check('S1_EARLIEST', None, cfg_path=cfg)
    assert any('acceptance is not PASS' in r for r in g['reasons'])
    g = A2G.check('S0', None, scenarios=['S0', 'S3'], cfg_path=cfg)
    assert any('not a prefix' in r for r in g['reasons'])


def test_manifest_text_files_are_eol_portable_but_content_strict(tmp_path):
    import post_v16_a2_gate as A2G
    f = tmp_path / 'x.py'
    f.write_bytes(b'a = 1\r\nb = 2\r\n')
    s = A2G.file_shas(f)
    man = dict(code={str(f): dict(text=True, **s)}, inputs={})
    assert A2G.manifest_mismatches(man, root=Path('/')) == []
    f.write_bytes(b'a = 1\nb = 2\n')                                   # same content, LF checkout
    assert A2G.manifest_mismatches(man, root=Path('/')) == []
    f.write_bytes(b'a = 1\nb = 3\n')                                   # content change -> refused
    assert A2G.manifest_mismatches(man, root=Path('/'))
    man['code'][str(f)]['text'] = False                                # binary / raw data: raw bytes only
    f.write_bytes(b'a = 1\r\nb = 2\r\n')
    assert A2G.manifest_mismatches(man, root=Path('/')) == []
    f.write_bytes(b'a = 1\nb = 2\n')
    assert A2G.manifest_mismatches(man, root=Path('/'))


def test_acceptance_on_injected_solution():
    """acceptance reads the solved rows: balance residual, missing reserve row -> FAIL, no-harm excess -> FAIL"""
    import post_v16_a2_gate as A2G
    pypsa = pytest.importorskip('pypsa')
    n = pypsa.Network(); n.set_snapshots(pd.date_range('2030-01-01', periods=2, freq='3h'))
    n.add('Bus', 'a'); n.add('Carrier', ['gas', 'load_shed'])
    n.add('Generator', 'g', bus='a', carrier='gas', p_nom=200)
    n.add('Generator', 'a load_shed', bus='a', carrier='load_shed', p_nom=1e3)
    n.add('Load', 'l', bus='a', p_set=100.0)
    n.optimize.create_model()
    m = n.model
    lab = m['Generator-p'].labels
    vals = np.zeros(lab.shape); i = list(lab.coords['name'].values).index('g'); vals[:, i] = 100.0
    m.variables['Generator-p'].solution = lab.copy(data=vals)
    n.generators_t.p = pd.DataFrame({'g': [100.0, 100.0], 'a load_shed': [0.0, 0.0]}, index=n.snapshots)
    acc = A2G.acceptance(n, 'S0', dict(status='ok', termination='optimal', integer_vars=0))
    assert acc['checks']['balance_residual_ok'] and acc['values']['balance_residual_MW_max'] == 0.0
    assert acc['checks']['reserve_ok'] is False and acc['PASS'] is False          # no reserve row -> never PASS
    vals[:, i] = 90.0
    m.variables['Generator-p'].solution = lab.copy(data=vals)
    assert not A2G.acceptance(n, 'S0', dict(status='ok', termination='optimal'))['checks']['balance_residual_ok']
    n.generators_t.p['a load_shed'] = [0.0, 5.0]
    ref = pd.DataFrame({'a load_shed': [0.0, 0.0]}, index=n.snapshots)
    acc = A2G.acceptance(n, 'S1_EARLIEST', dict(status='ok', termination='optimal'), shed_S0=ref)
    assert acc['checks']['no_harm_ok'] is False and acc['values']['no_harm_max_excess_MW'] == 5.0
