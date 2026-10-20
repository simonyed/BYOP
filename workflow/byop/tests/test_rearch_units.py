"""Unit tests for the rearchitecture developer stage (WP-C C6) on a synthetic one-site world.

Run on L2 (Gurobi) from pypsa-usa/workflow:
    python -m pytest -q byop/tests/test_rearch_units.py
Each test builds a developer LP (rearch_mech.private_mode) for one site, 2026-2029, one sampled week per year, and
checks one property: WLPUN import cap, Islanded zero import, Grid-Only without own supply, PCLR trigger-only
curtailment and zero conditional import at triggers, training daily conservation, BYOP COD / gas-lateral lead,
gas MDQ, and LP-only.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'model'))
import rearch_mech as R  # noqa: E402

M, w2, s1r = R.M, R.w2, R.s1r
YEARS = [2026, 2027, 2028, 2029]


@pytest.fixture(autouse=True)
def world(tmp_path):
    M.CFG.update(periods='annual', start=YEARS[0], end=YEARS[-1], cost_basis='repaired', frac_cod=True, byop_case='base',
                 byop_techs=['RICE', 'SOFC_NG'], threads=2, v=2.8e6, v_private=None, dem_scale=1.0, tariff='energy',
                 poi_lead=0, sample_weeks=None, decision_year=2026)
    w2.PUE = pd.read_csv(w2.PUE_CSV)
    pd.DataFrame([dict(cohort_id='T1', scenario='mid', request_year=2026, st='TX', region_id='T', IT_MW=100.0),
                  dict(cohort_id='T2', scenario='mid', request_year=2028, st='TX', region_id='T', IT_MW=100.0)]
                 ).to_csv(tmp_path / 'coh.csv', index=False)
    s1r.COHORTS = tmp_path / 'coh.csv'
    R.SITES.clear()
    R.SITES['T'] = dict(site='T', bus='B', lat=31.0, lon=-100.0, E0=0.0, cod0=None, preapproved=False, U_max=0.0, U_lead=4.0,
                        U_cost=1.6e5, proc=2028.0, pclr=150.0, pclr_off=0.0, gas_level='L1', mdq=2.5e5, lat_lead=0.0,
                        lat_cost=0.0, profile='X', confidence='TEST')
    R.GCFG.update(relax=[], s2_modes=R.MODES)
    for k in ['offer', 'triggers', 'modes', 'dc', 'byop_cod', 'reuse', 'reuse_s1', 'corridors', 'poi_up']:
        M.STATE.pop(k, None)
    M.STATE['erm'] = False
    # synthetic S1 network: snapshots / weights only (the developer LP never sees the grid)
    ts = pd.date_range('2030-01-01', periods=56, freq='3h')
    n = pypsa.Network()
    n.set_snapshots(pd.MultiIndex.from_product([YEARS, ts], names=['period', 'timestep']))
    n.investment_periods = YEARS
    n.snapshot_weightings = n.snapshot_weightings * 0.0 + 3.0 * 52   # not .loc[:, :] = (breaks the MultiIndex with pandas 3)
    n.investment_period_weightings.loc[:, 'years'] = 1.0
    n.investment_period_weightings.loc[:, 'objective'] = [M.w_social(p) for p in YEARS]
    yield n


def offer(firm, cond=0.0):
    M.STATE['offer'] = {('T', p): dict(firm=firm(p) if callable(firm) else firm, cond=cond) for p in YEARS}


def run(n, mode, trig=None):
    M.STATE['triggers'] = trig or {}
    price = pd.Series(40.0, index=n.snapshots)
    mult = np.ones(56)
    return R.private_mode({}, n, 2.8e6, mult, 'T', mode, False, price, price)


def facility_peak(res, p):
    n = res['_n']
    sl = n.snapshots.get_level_values(0) == p
    ld = n.generators.index[n.generators.carrier.isin(['compute_IT', 'AIDC_training'])]
    return float(n.generators_t.p[ld][sl].sum(axis=1).max())


def test_lp_only_and_optimal(world):
    offer(50.0)
    for mode in R.MODES:
        r = run(world, mode)
        assert r['integer_vars'] == 0
        assert r['termination'] == 'optimal', (mode, r['termination'])


def test_go_f_has_no_own_supply_and_respects_offer(world):
    offer(60.0)
    r = run(world, 'GO_F')
    n = r['_n']
    assert r['byop_MW'] == 0.0
    assert not n.generators.carrier.str.startswith('byop_').any()
    g = n.generators.index[n.generators.carrier == 'grid_purchase']
    assert float(n.generators_t.p[g].max().max()) <= 60.0 + 1e-4


def test_wlpun_import_cap(world):
    """GF: instantaneous grid import <= certified withdrawal limit; the rest from own supply"""
    offer(60.0)
    r = run(world, 'GF')
    n = r['_n']
    g = n.generators.index[n.generators.carrier.isin(['grid_purchase', 'grid_cond'])]
    imp = n.generators_t.p[g].sum(axis=1)
    assert float(imp.max()) <= 60.0 + 1e-4
    assert r['byop_MW'] > 1.0
    assert r['S'][2026] > 60.0 / 1.2      # serves more than the import cap alone could carry


def test_islanded_zero_import(world):
    offer(500.0, cond=100.0)
    r = run(world, 'IS')
    n = r['_n']
    g = n.generators.index[n.generators.carrier.isin(['grid_purchase', 'grid_cond'])]
    assert float(n.generators_t.p[g].abs().max().max() if len(g) else 0.0) < 1e-6
    assert all(v_ < 1e-6 for v_ in r['import_MWh'].values())
    assert r['S'][2029] > 1.0


def test_pclr_conditional_zero_at_triggers_and_curtail_only_there(world):
    offer(0.0, cond=150.0)
    sns = world.snapshots
    trig = {('T', p): list(sns[sns.get_level_values(0) == p][16:20]) for p in YEARS}
    r = run(world, 'GO_C', trig)
    n = r['_n']
    for p in YEARS:
        tset = set(trig[('T', p)])
        sl = sns[sns.get_level_values(0) == p]
        cn = f'DC_T gridc{p}'; cu = f'DC_T curt{p}'
        if cn in n.generators_t.p:
            at = n.generators_t.p.loc[[x for x in sl if x in tset], cn]
            assert float(at.abs().max()) < 1e-6
        if cu in n.generators_t.p:
            off = n.generators_t.p.loc[[x for x in sl if x not in tset], cu]
            assert float(off.abs().max()) < 1e-6
    assert sum(r['curtail_MWh'].values()) > 0.0


def test_training_daily_conservation(world):
    offer(500.0)
    r = run(world, 'GO_F')
    n = r['_n']
    for d in M.STATE['dc']:
        S = float(n.generators.p_nom_opt[d['S']])
        sl = n.snapshots[n.snapshots.get_level_values(0) == d['period']]
        e = (n.generators_t.p.loc[sl, d['T']] * M.SNAP_HOURS).groupby(sl.get_level_values(1).normalize()).sum()
        assert np.allclose(e.values, d['daily'] * S, rtol=1e-5, atol=1e-3)


def test_byop_cod_and_gas_lateral_lead(world):
    """no dedicated output before COD; a gas lateral lead of 2.5 y moves SOFC (0.5 y) and RICE (2 y) to 2028.5"""
    R.SITES['T']['lat_lead'] = 2.5
    offer(0.0)
    r = run(world, 'IS')
    n = r['_n']
    b = n.generators.index[n.generators.carrier.str.startswith('byop_')]
    assert (n.generators.build_year[b] >= 2028).all()
    out = n.generators_t.p[b]
    early = out[out.index.get_level_values(0) < 2028]
    assert float(early.abs().max().max()) < 1e-6
    assert r['S'][2026] < 1e-3 and r['S'][2027] < 1e-3
    for nm, info in M.STATE['byop_cod'].items():
        assert info['cod'] >= 2028.5 - 1e-9


def test_gas_mdq_binds(world):
    R.SITES['T']['mdq'] = 5000.0             # MMBtu/d ~ 25 MW of RICE at 8,295 Btu/kWh
    offer(0.0)
    r = run(world, 'IS')
    n = r['_n']
    t = M.tech().set_index(['carrier', 'boundary'])
    b = [x for x in n.generators.index if n.generators.carrier[x] in ('byop_RICE', 'byop_SOFC_NG')]
    hr = pd.Series({x: float(t.loc[(n.generators.carrier[x][5:], 'DC_BTM')].heat_rate_Btu_kWh) for x in b})
    fuel = (n.generators_t.p[b] * hr * M.SNAP_HOURS / 1000.0).sum(axis=1)
    day = fuel.groupby([fuel.index.get_level_values(0), fuel.index.get_level_values(1).normalize()]).sum()
    assert float(day.max()) <= 5000.0 * (1 + 1e-5)
    assert r['S'][2029] < 200.0 * 0.5        # the MDQ, not the request, limits the islanded service
