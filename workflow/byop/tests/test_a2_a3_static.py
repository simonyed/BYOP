"""NEXT-01 A2-STATIC / A3-STATIC unit tests (zero solver; any real solve fails the test)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
for p in ('model', 'post'):
    sys.path.insert(0, str(WF / 'byop' / p))
import byop_delivery_and_permit as D  # noqa: E402


@pytest.fixture(autouse=True)
def no_solver(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('solver called in an A2 / A3 static test')
    try:
        import linopy
        monkeypatch.setattr(linopy.Model, 'solve', boom)
    except ImportError:
        pass
    yield


# ------------------------------------------------------------------------------------------------ A3: partial year vs firm year
def test_delivery_timeline_partial_year_energy_not_firm():
    t = {r['year']: r for r in D.delivery_timeline(2027.75, facility_MW=100.0, pue=1.1484)}
    assert t[2026]['energizable_fraction'] == 0 and t[2027]['energizable_fraction'] == 0.25
    assert abs(t[2027]['partial_year_service_MWh'] - 0.25 * 8760 * 100) < 1e-6 and not t[2027]['full_firm']
    assert t[2027]['delivered_IT_MW_year_firm'] == 0 and t[2028]['full_firm'] and abs(t[2028]['delivered_IT_MW_year_firm'] - 100 / 1.1484) < 1e-9
    assert t[2027]['first_full_firm_year'] == 2028 and t[2027]['first_energizable_time'] == 2027.75


def test_permit_delay_changes_firm_year_only_when_it_crosses_a_year_boundary():
    import math
    rice = D.cod('RICE', 2026, '48029', gas_lead_years=0.5)
    aero = D.cod('OCGT_aero', 2026, '48029', gas_lead_years=0.5)
    shift = lambda a: math.ceil(a['COD_real'] - 1e-9) - math.ceil(a['COD_without_permit_constraints'] - 1e-9)
    assert rice['permit_attributable_COD_delay_years'] == 0.25 and shift(rice) == 0          # 2027.5 -> 2027.75: still 2028 Firm
    assert aero['permit_attributable_COD_delay_years'] == 0.25 and shift(aero) == 1          # 2028.0 -> 2028.25: Firm 2028 -> 2029


def test_partial_year_rule_equals_model_rule():
    pytest.importorskip('pypsa')
    import a3_static_mechanism as A3
    q = A3.partial_year_qa()
    assert q.consistent.all() and len(q) == 42


def test_gas_evidence_priority_keeps_l2_without_firm_evidence():
    import a3_static_mechanism as A3
    import byop_tech_parameters_v2 as T2
    sites = pd.read_csv(T2.SRC / 'RESEARCH_SITE_COUNTY_FIPS_V2.csv', dtype={'county_fips': str}, keep_default_na=False)
    ev = A3.evidence_table(sites)
    assert list(ev.bus) == ['p630 2', 'p630 6', 'p630 9', 'p650 0'] and (ev.repo_gas_level == 'L2').all()
    assert not ev.model_input_changed.any() and ev.decision.str.startswith('KEEP_L2').all()


def test_hypothetical_block_is_separated():
    import a3_static_mechanism as A3
    import byop_tech_parameters_v2 as T2
    J, T = T2.load()
    sites = pd.read_csv(T2.SRC / 'RESEARCH_SITE_COUNTY_FIPS_V2.csv', dtype={'county_fips': str}, keep_default_na=False)
    au = A3.audit(sites, J, T)
    h = au[au.scenario_block == 'HYPOTHETICAL_COUNTERFACTUAL']
    assert len(h) == 10 and h.evidence_basis.str.startswith('HYPOTHETICAL_MECHANISM_DEMONSTRATION').all()
    m = au[au.scenario_block == 'MAIN_EVIDENCE']
    assert len(m) == 128 and (m.permit_attributable_COD_delay_years == 0).all()


# ------------------------------------------------------------------------------------------------ A2: multi-period reserve rows
def small_multiperiod():
    pypsa = pytest.importorskip('pypsa')
    P = [2026, 2027]
    mi = pd.MultiIndex.from_product([P, pd.date_range('2030-01-01', periods=2, freq='3h')], names=['period', 'timestep'])
    n = pypsa.Network(); n.set_snapshots(mi); n.investment_periods = P
    n.add('Bus', ['a', 'DC_x']); n.add('Carrier', ['CCGT', 'OCGT', 'nuclear', 'battery', 'byop_RICE', 'load_shed'])
    n.add('Generator', 'a CCGT', bus='a', carrier='CCGT', p_nom=5000, marginal_cost=30, build_year=2025, lifetime=50)
    n.add('Generator', 'a OCGT pub2027', bus='a', carrier='OCGT', p_nom_extendable=True, capital_cost=1e5, marginal_cost=50, build_year=2027, lifetime=30)
    n.add('Generator', 'a nuc', bus='a', carrier='nuclear', p_nom=1000, marginal_cost=10, build_year=2025, lifetime=50)
    n.add('Generator', 'DC_x BYOP RICE q2026', bus='DC_x', carrier='byop_RICE', p_nom_extendable=True, capital_cost=2e5, build_year=2027, lifetime=25)
    n.add('Generator', 'a load_shed', bus='a', carrier='load_shed', p_nom=1e5, marginal_cost=35685, build_year=2025, lifetime=100)
    n.add('StorageUnit', 'a bat', bus='a', carrier='battery', p_nom=500, max_hours=4, efficiency_dispatch=0.92, efficiency_store=0.92, build_year=2025, lifetime=20)
    n.add('Line', 'L', bus0='a', bus1='DC_x', s_nom=1000, x=0.1)
    n.add('Load', 'l', bus='a', p_set=3000.0)
    n.optimize.create_model()
    return n


def test_multiperiod_reserve_rows():
    import post_v16_mainline as PM
    n = small_multiperiod()
    info = PM.add_operating_reserve(n, n.snapshots)
    m = n.model
    names = set(m['PV16M-res_thermal'].coords['name'].values)
    assert names == {'a CCGT', 'a OCGT pub2027'} and info['eligible_thermal_ext'] == 1          # no nuclear / BYOP / load_shed
    assert np.allclose(m.constraints['PV16M-reserve_req'].rhs.values, 3000.0) and m.constraints['PV16M-reserve_req'].rhs.size == 4
    ext = m.constraints['PV16M-online_cap_ext'].lhs
    pn = int(m['Generator-p_nom'].sel(name='a OCGT pub2027').labels.values)
    co = ext.coeffs.values[ext.vars.values == pn]
    assert sorted(set(np.round(co, 9))) == [-1.0, 0.0] or set(np.round(co, 9)) <= {-1.0, 0.0}  # inactive in 2026 (coef 0), -avail in 2027
    e = m.constraints['PV16M-res_su_energy'].lhs
    soc = set(m['StorageUnit-state_of_charge'].labels.values.ravel())
    assert (set(e.vars.values.ravel()) - {-1}) & soc
    assert not [v for v in m.variables if v.endswith('_RESERVES')] and int(len(m.binaries) + len(m.integers)) == 0


def test_public_expansion_ledger_flags_free_lines():
    import post_v16_mainline as PM
    n = small_multiperiod()
    n.add('Link', 'X_exp2027_fwd', bus0='a', bus1='DC_x', p_nom_extendable=True, capital_cost=0.0, build_year=2027, carrier='AC_exp')
    n.add('Link', 'S0CAL_L_fwd', bus0='a', bus1='DC_x', p_nom=10, carrier='AC_s0cal', build_year=2026)
    led = PM.public_expansion_ledger(n, [2026, 2027])
    assert set(led.status) >= {'FREE_FORBIDDEN', 'S0CAL_FORBIDDEN', 'ENDOGENOUS_PRICED'}


def test_wp2_no_erm_switch_default_off():
    pytest.importorskip('pypsa')
    import wp2_ercot_s0_s1 as W
    assert W.POST_V16_NO_ERM == {'on': False}
