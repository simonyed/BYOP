"""Calibration close-out v1.6 checks. Pure-input tests run anywhere; network tests need pypsa; result tests need the v1.6 run.
    python -m pytest -q byop/tests/test_baseline_v16.py        (from pypsa-usa/workflow)"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

WF = Path(__file__).resolve().parents[2]
BY = WF / 'byop'
for p in ('model', 'build', 'post', 'run'):
    sys.path.insert(0, str(BY / p))
import byop_paths as BP  # noqa: E402
import baseline_v16_assets as A16  # noqa: E402

OUT = BP.BASE_TAMU_V16_DIR
DEC = pd.read_csv(BP.CALIB_V16_INPUTS / 'ASSET_DECISIONS.csv', encoding='utf-8-sig')
CAPS = pd.read_csv(BP.CALIB_V16_EVIDENCE / 'SWITCHABLE_2025_MONTHLY_AVAILABILITY.csv', encoding='utf-8-sig')
need_db = pytest.mark.skipif(not BP.REEDS_GENDB.exists(), reason='ReEDS generator database not on this machine')
need_qa = pytest.mark.skipif(not (OUT / 'BASELINE_V16_FIXED_ASSET_QA.json').exists(), reason='v1.6 LP2 not run / synced')


def ercot_db():
    db = pd.read_csv(BP.REEDS_GENDB, low_memory=False)
    db = db[db.T_PCA.astype(str).str.strip() == 'ERCO']
    return db[db.tech.map(A16.TECH_MAP).notna()].copy()


# ------------------------------------------------------------------ assets
@need_db
def test_overrides_move_exactly_the_decided_records():
    db = ercot_db()
    after, au = A16.apply_overrides(db, DEC)
    s = au.groupby('item').agg(b=('set_before', 'first'), a=('set_after', 'first'), mw=('summer_MW', 'sum'))
    assert s.loc['Gaia solar'].tolist() == ['active2025', 'committed', 152.7]
    for it, mw in (('Pyron wind', 249.0), ('Danish Fields Storage', 150.0), ('Myrtle Storage', 150.0)):
        assert s.loc[it].tolist() == ['not_in_model', 'active2025', mw]
    for it in ('Sequoia phase 1', 'Fagus', 'Buzios / Roaring Springs', 'Big Star solar', 'La Casa', 'Long Point', 'Kiamichi', 'Tenaska Gateway'):
        assert s.loc[it, 'b'] == s.loc[it, 'a'] == 'active2025'
    assert au[au.item.str.contains('Storage')].energy_MWh.tolist() == [225.0, 225.0]      # MWh and duration kept
    fd = A16.fleet_delta(db, after)
    act = fd[fd.model_set == 'active2025']
    assert round(act.before_MW.sum(), 1) == 155050.6 and round(act.after_MW.sum(), 1) == 155446.9
    d = act.set_index('carrier').delta_MW
    assert round(d['onwind'], 1) == 249.0 and round(d['battery'], 1) == 300.0 and round(d['solar'], 1) == -152.7
    assert after['Unique ID'].is_unique                                                    # no duplicated record


@need_db
def test_override_validation_rejects_wrong_capacity_or_tech():
    db = ercot_db()
    bad = DEC.copy(); bad.loc[bad.item == 'Pyron wind', 'physical_summer_MW'] = 300
    with pytest.raises(ValueError, match='summer MW'):
        A16.apply_overrides(db, bad)
    bad = DEC.copy(); bad.loc[bad.item == 'Pyron wind', 'reeds_unique_id'] = '21245'        # a battery under a wind decision
    bad.loc[bad.item == 'Pyron wind', 'physical_summer_MW'] = 150
    with pytest.raises(ValueError, match='technology'):
        A16.apply_overrides(db, bad)


def test_month_mapping_follows_source_rows():
    h = pd.read_csv(BP.ANCHOR2025_DERIVED / 'ERCOT_NATIVE_LOAD_2025_1H.csv', usecols=['Hour Ending'])
    m = A16.month_of_3h_steps(h)
    assert len(m) == 2920 and m[0] == 1 and m[-1] == 12 and (np.diff(m) >= 0).all()
    days = pd.Series(m).value_counts().sort_index() * 3 / 24
    assert days.tolist() == [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def test_switchable_caps_match_package_and_p_max_pu():
    c = A16.switchable_caps(CAPS, {'Kiamichi': 1224.0, 'Tenaska Gateway': 826.0})
    assert c.loc[[1, 6, 8, 12], 'Kiamichi'].tolist() == [1215, 609, 609, 1215]
    assert c.loc[[1, 6, 8, 12], 'Tenaska Gateway'].tolist() == [729, 709, 556, 551]
    pm = A16.p_max_pu_series(c['Kiamichi'], np.array([1, 8, 12]), 1224.0)
    assert np.allclose(pm * 1224.0, [1215, 609, 1215]) and (pm <= 1).all()


# ------------------------------------------------------------------ ERM credit uses the same cap once
def test_erm_credit_of_capped_plant_is_p_nom_times_p_max_pu():
    pypsa = pytest.importorskip('pypsa')
    sys.path.insert(0, str(WF / 'scripts'))
    reserves = pytest.importorskip('opts.reserves')
    n = pypsa.Network()
    n.set_snapshots(pd.date_range('2025-01-01', periods=4, freq='3h'))
    n.add('Bus', 'b0'); n.add('Carrier', ['gas', 'AC'])
    cap = np.array([1215, 1215, 609, 609]) / 1224.0
    n.add('Generator', 'kiamichi', bus='b0', carrier='gas', p_nom=1224.0, p_max_pu=pd.Series(cap, index=n.snapshots), marginal_cost=10)
    n.add('Generator', 'new', bus='b0', carrier='gas', p_nom_extendable=True, capital_cost=1.0, marginal_cost=20)
    n.add('Load', 'l0', bus='b0', p_set=1000.0)
    n.optimize.create_model()
    reserves.define_erm_nodal_balance_constraints(n, n.snapshots, 0.15, 'TX', n.buses)
    rhs = n.model.constraints['GlobalConstraint-TX_ERM'].rhs.values.ravel()
    assert np.allclose(rhs, 1000.0 * 1.15 - np.array([1215, 1215, 609, 609]))              # credit = cap, counted once
    assert np.allclose(n.get_switchable_as_dense('Generator', 'p_max_pu')['kiamichi'].values * 1224.0, [1215, 1215, 609, 609])


# ------------------------------------------------------------------ save rule (X1) and reload identity
def test_s_nom_only_save_survives_reload(tmp_path):
    pypsa = pytest.importorskip('pypsa')
    B = pytest.importorskip('build_2025_baseline_tamu')
    n = pypsa.Network(); n.set_snapshots(pd.date_range('2025-01-01', periods=2, freq='3h'))
    n.add('Bus', ['a', 'b', 'c'])
    n.add('Line', ['L1', 'L2'], bus0=['a', 'b'], bus1=['b', 'c'], s_nom=[100.0, 200.0], x=[0.1, 0.2], r=[0.01, 0.02])
    raw = tmp_path / 'raw.nc'; n.export_to_netcdf(raw)
    cal = pd.DataFrame(dict(line=['L1', 'L2'], existing_MVA=[100.0, 200.0], added_MVA=[50.0, 0.2]))   # 0.2 MVA < display cut
    B.apply_uplift(n, cal, True)
    fin = tmp_path / 'fin.nc'; n.export_to_netcdf(fin)
    r, f = pypsa.Network(str(raw)), pypsa.Network(str(fin))
    assert np.array_equal(r.lines.x.values, f.lines.x.values) and np.array_equal(r.lines.r.values, f.lines.r.values)
    assert np.allclose(f.lines.s_nom.values, [150.0, 200.2])                                 # the small uplift stays in the network
    m = pypsa.Network(str(raw)); B.apply_uplift(m, cal, False)                               # legacy rule kept for reproduction only
    assert np.isclose(m.lines.x['L1'], 0.1 / 1.5)


# ------------------------------------------------------------------ PRM official reproduction (pure inputs)
def test_official_prm_reproduced_from_components():
    import v16_prm_bridge as P
    comp = pd.read_csv(BP.CALIB_V16_EVIDENCE / 'CDR_2025_RESOURCE_DEMAND_COMPONENTS.csv', encoding='utf-8-sig')
    prm = pd.read_csv(BP.CALIB_V16_EVIDENCE / 'CDR_2025_PRM_REFERENCE.csv', encoding='utf-8-sig')
    rows = P.official(comp, prm)
    r = {x['risk_period']: x for x in rows if x['category'] == 'PRM_RECOMPUTED'}
    assert abs(r['peak_load']['prm'] - 0.1889893040346796) < 1e-12 and abs(r['peak_net_load']['prm'] - 0.10471809939209706) < 1e-12
    cats = {x['category'] for x in rows if x.get('excel_row') in P.ROWCAT}
    assert {'thermal', 'switchable', 'storage', 'private_use_networks', 'dc_ties', 'rmr', 'wind_coastal', 'solar_farwest'} <= cats
    assert P.RISK == {'peak_load': 'summer_afternoon', 'peak_net_load': 'summer_evening'}


def test_bess_elcc_interpolates_by_duration():
    import v16_prm_bridge as P
    e = pd.read_csv(BP.CALIB_V16_EVIDENCE / 'CDR_2025_ELCC_REFERENCE.csv', encoding='utf-8-sig')
    f = P.bess_elcc(e, 'summer_afternoon', np.array([1.0, 1.5, 2.0, 20.0]))
    one = e[(e.resource_type == 'BESS - 1.0 hr') & (e.risk_period == 'summer_afternoon')].capacity_credit.iloc[0]
    two = e[(e.resource_type == 'BESS - 2.0 hr') & (e.risk_period == 'summer_afternoon')].capacity_credit.iloc[0]
    assert np.isclose(f[0], one) and np.isclose(f[1], (one + two) / 2) and f[3] <= 1.0


# ------------------------------------------------------------------ config / gates
def test_config_budget_and_formal_gates_unchanged():
    c = yaml.safe_load((WF / 'config/config.byop_baseline_v16_calibration.yaml').read_text())['v16']
    assert c['max_lp_calls'] == 2 and c['max_retries'] == 0
    assert list(c['stages']) == ['LP1_MIN_THERMAL_UPLIFT', 'LP2_RELOADED_FIXED_ASSET']
    assert c['acceptance']['eens_over_annual_energy_max'] == 1e-5 and c['acceptance']['max_gap_over_official_peak_max'] == 1e-3
    assert c['solver_options']['Crossover'] == 1
    for p in (WF / 'config').glob('config.byop_ercot_mainline*.yaml'):
        assert yaml.safe_load(p.read_text())['mainline']['run_authorization'] == 'NOT_APPROVED'


# ------------------------------------------------------------------ results (after the run)
@need_qa
def test_fixed_asset_qa_identity_and_calls():
    q = json.loads((OUT / 'BASELINE_V16_FIXED_ASSET_QA.json').read_text())
    assert q['reloaded_from_disk'] and q['identity']['xr_identical_to_raw_uncalibrated'] and q['identity']['s_nom_equals_LP1_solution']
    assert q['identity']['switchable_caps_present']
    assert not [v for v in q['linopy_variables'] if v.endswith(('-p_nom', '-s_nom', '-e_nom'))]
    lg = pd.read_csv(OUT / 'BASELINE_V16_SOLVE_LOG.csv')
    assert len(lg) <= 2 and lg.stage.is_unique and (lg.attempt == 1).all()
    assert q['termination'] == 'optimal' and q['lp1']['termination'] == 'optimal'
