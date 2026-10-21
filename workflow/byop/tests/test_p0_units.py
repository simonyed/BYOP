"""Unit tests for the P0 corrections (researcher decisions 2026-10-20: P0-1, P0-2, D1, D2).

Run on L2 (Gurobi) from pypsa-usa/workflow:
    python -m pytest -q byop/tests/test_p0_units.py
Developer-stage tests reuse the synthetic one-site world of test_rearch_units.py; public-side tests build a tiny
two-bus network (A: cheap generation, B: background load + POI sites) joined by one thermally limited line.
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
TS = pd.date_range('2030-01-01', periods=56, freq='3h')
OPTS = dict(Method=2, Crossover=0, BarConvTol=1e-8, OutputFlag=0, Threads=2)


def reset(tmp_path, cohorts):
    M.CFG.update(periods='annual', start=YEARS[0], end=YEARS[-1], cost_basis='repaired', frac_cod=True, byop_case='base',
                 byop_techs=['RICE', 'SOFC_NG'], threads=2, v=2.8e6, v_private=None, dem_scale=1.0, tariff='energy',
                 poi_lead=0, sample_weeks=None, decision_year=2026)
    w2.PUE = pd.read_csv(w2.PUE_CSV)
    pd.DataFrame(cohorts).to_csv(tmp_path / 'coh.csv', index=False)
    s1r.COHORTS = tmp_path / 'coh.csv'
    R.SITES.clear()
    R.GCFG.update(relax=[], s2_modes=R.MODES, interrupt_cap=0.005, no_harm=True)
    for k in ['offer', 'triggers', 'modes', 'dc', 'byop_cod', 'reuse', 'reuse_s1', 'corridors', 'poi_up', 'lex', 'lex_log',
              'shed_S0', 'no_harm_now', 'firm_strict', 'interrupt_price', 'cond_public']:
        M.STATE.pop(k, None)
    M.STATE['erm'] = False


def site(name, bus, E0=1000.0, cod0=2026.0, pre=True, proc=2026.0):
    R.SITES[name] = dict(site=name, bus=bus, lat=31.0, lon=-100.0, E0=E0, cod0=cod0, preapproved=pre, U_max=0.0, U_lead=4.0,
                         U_cost=1.6e5, proc=proc, pclr=0.0, pclr_off=0.0, gas_level='L1', mdq=2.5e5, lat_lead=0.0,
                         lat_cost=0.0, profile='X', confidence='TEST')


def snapshots_net():
    n = pypsa.Network()
    n.set_snapshots(pd.MultiIndex.from_product([YEARS, TS], names=['period', 'timestep']))
    n.investment_periods = YEARS
    n.snapshot_weightings = n.snapshot_weightings * 0.0 + 3.0 * 52   # not .loc[:, :] = (breaks the MultiIndex with pandas 3)
    n.investment_period_weightings.loc[:, 'years'] = 1.0
    n.investment_period_weightings.loc[:, 'objective'] = [M.w_social(p) for p in YEARS]
    return n


def tiny(line_mw=300.0, bg=100.0, option_mw=0.0):
    """A --line--> B; cheap generation at A only; background load and shed at B; optional extendable Link A->B"""
    n = snapshots_net()
    for b in ['A', 'B']:
        n.add('Bus', b, x=0.0, y=0.0)
    for c in ['gas', 'load_shed', 'AC_exp']:
        n.add('Carrier', c, co2_emissions=0.0)
    n.add('Generator', 'A gas', bus='A', carrier='gas', p_nom=5000.0, marginal_cost=20.0, build_year=2025, lifetime=100)
    n.add('Link', 'AB', bus0='A', bus1='B', p_nom=line_mw, p_min_pu=-1.0, build_year=2025, lifetime=100)   # single corridor: KVL irrelevant
    n.add('Load', 'B bg', bus='B', p_set=bg)
    n.add('Generator', 'B load_shed', bus='B', carrier='load_shed', p_nom=1e5, marginal_cost=M.SHED_COST, build_year=2025, lifetime=100)
    if option_mw > 0:
        n.add('Link', 'AB_exp', bus0='A', bus1='B', carrier='AC_exp', p_nom_extendable=True, p_nom_max=option_mw, capital_cost=1e4,
              build_year=2026, lifetime=60)
    M.ZONES = ['A', 'B']
    return n


def solve_public(n, lex=False, strict=False, s_fixed=None):
    M.STATE['firm_strict'] = strict
    dem = M.study_new_demand()
    R.add_dc_poi(n, dem, 2.8e6, np.ones(56), s_fixed=s_fixed)
    M.STATE['lex'] = dict(tag='test') if lex else None
    n.optimize(solver_name='gurobi', solver_options=OPTS, extra_functionality=R.extra_rearch, multi_investment_periods=True)
    M.STATE['lex'] = None; M.STATE['firm_strict'] = False
    return {(d['zone'], d['period']): float(n.generators.p_nom_opt[d['S']]) for d in M.STATE['dc']}


def two_sites(tmp_path, it=200.0):
    reset(tmp_path, [dict(cohort_id='a', scenario='mid', request_year=2026, st='TX', region_id='S_A', IT_MW=it),
                     dict(cohort_id='b', scenario='mid', request_year=2026, st='TX', region_id='S_B', IT_MW=it)])
    site('S_A', 'B'); site('S_B', 'B')


# ------------------------------------------------------------------------------------------------ developer side
@pytest.fixture
def one_site(tmp_path):
    reset(tmp_path, [dict(cohort_id='T1', scenario='mid', request_year=2026, st='TX', region_id='T', IT_MW=100.0)])
    site('T', 'B', E0=0.0, cod0=None, pre=False)
    return snapshots_net()


def test_value_consistency(one_site):
    """a full-year interruption of 1 MW_IT costs exactly the annual service value v"""
    M.STATE['offer'] = {('T', p): dict(firm=200.0, cond=0.0) for p in YEARS}
    price = pd.Series(40.0, index=one_site.snapshots)
    R.private_mode({}, one_site, 2.8e6, np.ones(56), 'T', 'GO_F', False, price, price)
    for (s_, p), d in M.STATE['interrupt_price'].items():
        assert abs(d['c_interrupt_USD_MWh'] * d['e_unit_MWh_per_MW_IT'] - d['v']) < 1e-6 * d['v']
        assert 300 < d['c_interrupt_USD_MWh'] < 1500        # same order as the researcher check table (565-620 USD/MWh)


def test_online_monotone_and_interrupt_cap(one_site):
    """offer collapses in 2028: online IT may not fall; interruption stays within 0.5 % of planned energy"""
    off = {2026: 200.0, 2027: 200.0, 2028: 0.0, 2029: 200.0}
    M.STATE['offer'] = {('T', p): dict(firm=off[p], cond=0.0) for p in YEARS}
    price = pd.Series(40.0, index=one_site.snapshots)
    r = R.private_mode({}, one_site, 2.8e6, np.ones(56), 'T', 'GO_F', False, price, price)
    S = [r['S'][p] for p in YEARS]
    assert all(b >= a - 1e-3 for a, b in zip(S[:-1], S[1:])), S
    n = r['_n']
    for d in M.STATE['dc']:
        if d.get('intr'):
            sl = n.snapshots.get_level_values(0) == d['period']
            e = float((n.generators_t.p[d['intr']][sl] * n.snapshot_weightings.generators[sl]).sum())
            assert e <= 0.005 * d['e_unit'] * float(n.generators.p_nom_opt[d['S']]) * (1 + 1e-5) + 1e-3
    assert S[0] < 1e-3 and S[1] < 1e-3        # cannot stay online through 2028 -> not commissioned before 2029


# ------------------------------------------------------------------------------------------------ public side
def test_no_harm_existing_customers(tmp_path):
    """S0 already sheds 50 MW (bg 350 > line 300); with the no-harm bound the DC sites cannot take load from it"""
    two_sites(tmp_path, it=100.0)
    n0 = tiny(line_mw=300.0, bg=350.0)
    n0.optimize(solver_name='gurobi', solver_options=OPTS, multi_investment_periods=True)
    sh0 = n0.generators_t.p[['B load_shed']].copy()          # frozen per generator (D2.4)
    M.STATE['shed_S0'] = sh0
    n1 = tiny(line_mw=300.0, bg=350.0)
    M.STATE['no_harm_now'] = True
    S = solve_public(n1)
    M.STATE['no_harm_now'] = False
    assert float((n1.generators_t.p['B load_shed'] - sh0['B load_shed']).max()) <= 0.001 + 1e-6
    assert sum(S.values()) < 1e-2


def test_earliest_ge_econ_and_maxmin(tmp_path):
    """two sites behind one 300 MW line (bg 100): strict earliest total >= economic total; max-min splits equally"""
    two_sites(tmp_path)
    e = solve_public(tiny(), lex=True, strict=True)
    lex = M.STATE['lex_log']
    assert lex['optimal']
    R.GCFG['interrupt_cap'] = 0.0          # same feasible domain as the strict Firm base (no unplanned interruption)
    c = solve_public(tiny())
    for y in YEARS:
        te = e[('S_A', y)] + e[('S_B', y)]; tc = c[('S_A', y)] + c[('S_B', y)]
        assert te >= tc - 1e-2, (y, te, tc)
        assert abs(e[('S_A', y)] - e[('S_B', y)]) < 0.5, (y, e)          # both eligible with equal R -> equal shares
        assert te < 400.0                                                  # the shared line is the binding limit
    assert any(l['stage'] == 'A2' for l in lex['levels'])


def test_earliest_monotone_in_options(tmp_path):
    """adding an expansion option never lowers the strict earliest deliverable IT"""
    two_sites(tmp_path)
    base = solve_public(tiny(), lex=True, strict=True)
    opt = solve_public(tiny(option_mw=200.0), lex=True, strict=True)
    for y in YEARS:
        assert opt[('S_A', y)] + opt[('S_B', y)] >= base[('S_A', y)] + base[('S_B', y)] - 1e-2


def test_ineligible_site_does_not_lock_maxmin(tmp_path):
    """a site without POI equipment (R = 0) is excluded from the min-share, so the other site is not forced to 0"""
    two_sites(tmp_path)
    R.SITES['S_B'].update(E0=0.0, cod0=None, preapproved=False)
    e = solve_public(tiny(), lex=True, strict=True)
    for y in YEARS:
        assert e[('S_B', y)] < 1e-3
        assert e[('S_A', y)] > 50.0


def test_regional_dc_background_load(tmp_path):
    """opt-in regional cohorts: cumulative IT x PUE per bus, only the selected basis / scenario, own load_shed generator"""
    reset(tmp_path, [])
    pd.DataFrame([dict(scenario='mid', request_year=2026, region_id='A', IT_MW=100.0, parent_zone='z', spatial_basis='existing_stock'),
                  dict(scenario='mid', request_year=2028, region_id='A', IT_MW=50.0, parent_zone='z', spatial_basis='existing_stock'),
                  dict(scenario='mid', request_year=2027, region_id='B', IT_MW=80.0, parent_zone='z', spatial_basis='existing_stock'),
                  dict(scenario='high', request_year=2026, region_id='B', IT_MW=999.0, parent_zone='z', spatial_basis='existing_stock'),
                  dict(scenario='mid', request_year=2026, region_id='B', IT_MW=777.0, parent_zone='z', spatial_basis='other_basis')]
                 ).to_csv(tmp_path / 'reg.csv', index=False)
    n = snapshots_net()
    for b in ['A', 'B']:
        n.add('Bus', b, x=0.0, y=0.0)
    old = R.REGIONAL_COHORTS
    try:
        R.REGIONAL_COHORTS = tmp_path / 'reg.csv'
        R.GCFG.update(regional_dc='off')
        R.add_regional_dc(n)
        assert 'A regional_dc' not in n.loads.index
        R.GCFG.update(regional_dc='existing_stock', regional_dc_scenario='mid')
        R.add_regional_dc(n)
    finally:
        R.REGIONAL_COHORTS = old
        R.GCFG.update(regional_dc='off')
    pue = {p: float(w2.PUE[(w2.PUE.st == 'TX') & (w2.PUE.year == p)].pue.iloc[0]) for p in YEARS}
    ps = n.loads_t.p_set
    for p in YEARS:
        assert np.isclose(ps.loc[p, 'A regional_dc'].iloc[0], (100.0 + (50.0 if p >= 2028 else 0.0)) * pue[p])
        assert np.isclose(ps.loc[p, 'B regional_dc'].iloc[0], (80.0 if p >= 2027 else 0.0) * pue[p])
    g = n.generators.loc[['A regional_dc_unserved', 'B regional_dc_unserved']]
    assert (g.carrier == 'load_shed').all() and (g.marginal_cost == M.SHED_COST).all()
    assert M.STATE['regional_dc']['IT_MW_total'] == 230.0
