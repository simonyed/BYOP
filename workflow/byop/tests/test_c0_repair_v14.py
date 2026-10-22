"""C0 repair v1.4 (2026-10-22, stage A) tests - the failure modes of the v1.3 audit as real-data and synthetic cases.
No LP solver anywhere. Run from pypsa-usa/workflow after  python byop/build/c0_repair_v14.py :
    python -m pytest -q byop/tests/test_c0_repair_v14.py"""
from __future__ import annotations

import hashlib, importlib.util, json, sys
from pathlib import Path

import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
BY = WF / 'byop'
sys.path.insert(0, str(BY / 'model'))
import byop_paths as BP  # noqa: E402

OUT, OLD = BP.C0_REPAIR_RESULTS, BP.C0_RESULTS
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
PH = lambda: pd.read_csv(OUT / 'C0_PHASE_RECONCILIATION.csv')
QA = lambda: json.loads((OUT / 'C0_REPAIR_QA.json').read_text())


@pytest.fixture(scope='module')
def R():
    spec = importlib.util.spec_from_file_location('c0_repair_v14', BY / 'build/c0_repair_v14.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ A1 real cases
@pytest.mark.parametrize('park, hist_mw, hist_year', [('CALLISTO', 203.0, 2024), ('TIDWELL PRAIRIE', 204.0, 2025), ('PADUA GRID', 51.1, 2025)])
def test_real_mixed_phase_parks_do_not_migrate_future_phase(park, hist_mw, hist_year):
    c = PH()
    c = c[(c.side == 'CDR_PHASE') & c.cdr_group_key.str.contains(park)]
    h = c[c.phase_class == 'HIST']
    assert len(h) == 1 and abs(h.cdr_MW.iloc[0] - hist_mw) < 1e-6 and int(h.phase_year.iloc[0]) == hist_year
    assert h.reclass_action.iloc[0] == 'NONE_HISTORICAL_PHASE_COVERED' and h.model_set.iloc[0] == 'active2025'
    f = c[c.phase_class == 'FUTURE']
    assert len(f) == 1 and f.reclass_action.iloc[0] in ('NONE_FUTURE_CONSISTENT', 'NONE_FUTURE_NOT_PAIRED')
    assert not c.reclass_action.isin(['REVIEW_RECLASS_CANDIDATE', 'STATUS_QUALIFIED_REVIEW']).any()
    rv = pd.read_csv(OUT / 'C0_RECLASS_REVISED.csv')
    assert not ((rv.set == 'V14_PHASE_LEVEL_CANDIDATES') & rv.cdr_group_key.str.contains(park)).any()


def test_old_2971_total_explained_not_confirmed():
    q = QA()
    assert abs(q['old_total_MW'] - 2971.68) < 1e-6
    by = q['old_set_by_action']
    assert abs(by['NONE_HISTORICAL_PHASE_COVERED'] - 458.1) < 1e-6                  # Callisto + Tidwell + Padua history
    assert abs(sum(by.values()) - 2971.68) < 1e-6
    assert 'REVIEW_RECLASS_CANDIDATE' not in by                                      # nothing in the old set is a confirmed omission
    rv = pd.read_csv(OUT / 'C0_RECLASS_REVISED.csv')
    assert rv[rv.set == 'OLD_V13_SUGGESTION_SET'].old_v13_label.str.contains('to be reviewed').all()


def test_identifiers_and_separate_fields_kept():
    c = PH()
    for col in ('identity_match', 'phase_match', 'historical_status', 'capacity_basis', 'reclass_action', 'cdr_unit_names', 'cdr_unit_codes',
                'cdr_inr', 'eia_plant_ids', 'reeds_unique_ids', 'cdr_in_service', 'cdr_published'):
        assert col in c.columns
    cal = c[(c.side == 'CDR_PHASE') & c.cdr_group_key.str.contains('CALLISTO') & (c.phase_class == 'HIST')].iloc[0]
    assert 'CLO_BESS1' in cal.cdr_unit_codes and '66338' in str(cal.eia_plant_ids) and '20530' in str(cal.reeds_unique_ids)


# ------------------------------------------------------------------------------------------------ status / dates
def test_oper_syn_missing_and_future_dates_not_certified(R):
    assert R.status_class('OPER-SYN') == 'SYNCHRONIZED_NOT_COMMERCIAL' and R.status_class('OPER-SYN-SLF') == 'SYNCHRONIZED_NOT_COMMERCIAL'
    assert R.status_class('OPER') == 'COMMERCIAL_OPER' and R.status_class('PLAN') == 'PLANNED'
    c = PH()
    c = c[c.side == 'CDR_PHASE']
    rc = c[c.reclass_action == 'REVIEW_RECLASS_CANDIDATE']
    assert (rc.historical_status == 'COMMERCIAL_OPER').all() and (rc.date_classes == 'IN_SERVICE_LE_2025').all()
    syn = c[c.historical_status.str.contains('SYNCHRONIZED') & (c.phase_class == 'HIST') & c.model_set.fillna('').str.len().gt(0) & c.identity_match.str.startswith('NAME_')
            & ~c.model_set.fillna('').str.contains('active2025')]
    assert len(syn) and (syn.reclass_action == 'STATUS_QUALIFIED_REVIEW').all()      # Danish Fields / Roseland / ... solar
    assert c[c.phase_year.isna()].phase_match.ne('PHASE_PAIRED').all()             # no date -> never paired on year
    assert (c[c.phase_class == 'FUTURE'].reclass_action.str.startswith(('NONE_FUTURE', 'STATUS_CONFLICT'))).all()


# ------------------------------------------------------------------------------------------------ A2 switchable
def test_switchable_ledger_kiamichi():
    sw = pd.read_csv(OUT / 'C0_SWITCHABLE_LEDGER.csv')
    k = sw[sw.station.str.contains('KIAMICHI')].iloc[0]
    assert k.physical_MW == 1400.0 and k.unavailable_adjustment_MW == -885.0 and k.snapshot_net_MW == 515.0
    assert k.model_active2025_summer_MW == 1224.0                                    # model value unchanged
    assert (sw.adjustments_unpaired == 0).all()
    rows = pd.read_csv(OUT / 'C0_SWITCHABLE_UNIT_ROWS.csv')
    adj = rows[rows.row_type == 'UNAVAILABLE_ADJUSTMENT']
    assert (adj.MW < 0).all() and adj.adjustment_paired_with_physical.astype(bool).all()
    phys = rows[rows.row_type == 'PHYSICAL_UNIT']
    assert abs(phys.unit_unavailable_adj_MW.sum() - adj.MW.sum()) < 1e-9             # each adjustment deducted exactly once
    assert abs(phys.unit_net_MW.sum() - sw.snapshot_net_MW.sum()) < 1e-9
    assert not PH().cdr_unit_codes.fillna('').str.contains('_UNAVAIL').any()          # adjustment rows are never phases


# ------------------------------------------------------------------------------------------------ A3 confidence
def test_confidence_tiers_not_upgraded():
    cf = pd.read_csv(OUT / 'C0_MATCH_CONFIDENCE.csv')
    idc = cf[cf.identity_tier.str.startswith('ID_CONFIRMED')]
    assert (idc.units == 0).all() and (idc.MW == 0).all()
    assert not cf.identity_tier.str.contains('OTHER_COUNTY.*ID|CANDIDATE.*ID').any()
    c = PH()
    cand = c[(c.side == 'CDR_PHASE') & c.identity_match.str.startswith(('CAPACITY_CANDIDATE', 'AMBIGUOUS', 'UNMATCHED')) & (c.phase_class == 'HIST')]
    assert (cand.reclass_action == 'UNRESOLVED_CANDIDATE_IDENTITY').all()
    for d, g in cf[cf.side == 'CDR'].groupby('denominator'):
        assert abs(g.share_MW.sum() - 1.0) < 1e-4                                   # CSV written at 6 decimals
    b = pd.read_csv(OUT / 'C0_CAPACITY_BRIDGE_V14.csv')
    assert 'decomp_rating_diff' not in set(b.component) and b[b.component == 'decomp_matched_group_capacity_diff'].basis.str.contains('MIXES').all()


def test_same_site_future_repower_does_not_swallow_old_unit(R):
    cp = [dict(side='CDR', phase_class='FUTURE', year=2027, MW=200.0, idx=[], statuses=['PLAN'], status_classes=['PLANNED'])]
    mp = [dict(side='MODEL', model_set='active2025', year=2008, MW=200.0, nameplate=200.0, idx=[])]
    assert R.pair_phases(cp, mp) == {}
    cu = pd.DataFrame(dict(phase_class=['FUTURE'], core_2025=[False], scope_bucket=['PLANNED_NOT_2025'], MW=[200.0]))
    assert R.noncore_reason(cu).startswith('SAME_NAME_FUTURE_RECORD_ONLY')
    nc = pd.read_csv(OUT / 'C0_MODEL_ACTIVE_NONCORE_BREAKDOWN.csv')
    assert nc.note.eq('flags for review, not deletions').all()


# ------------------------------------------------------------------------------------------------ no double counting / snapshot
def test_units_counted_once_and_v13_snapshot_untouched():
    c = PH()
    ids = [i for s in c.reeds_unique_ids.dropna() for i in str(s).split('; ') if i]
    assert len(ids) == len(set(ids))                                                 # each ReEDS unit in at most one phase row
    rows = [i for s in c[c.side == 'CDR_PHASE'].cdr_source_rows.dropna() for i in str(s).split('; ') if i]
    assert len(rows) == len(set(rows))                                               # each CDR source row in exactly one phase
    u = pd.read_csv(BP.ANCHOR2025_DERIVED / 'CDR_DEC2025_UNIT_REGISTER_AUDIT_ONLY.csv')
    dup = u[u['UNIT CODE'].notna() & u['UNIT CODE'].duplicated(keep=False)]
    for code, g in dup.groupby('UNIT CODE'):                                         # only coal -> gas conversion records of one unit
        assert set(g.FUEL) == {'COAL', 'GAS'} and (pd.to_datetime(g[g.FUEL == 'GAS']['IN-SERVICE DATE']) > '2025-12-31').all(), code
    old = json.loads((OLD / 'C0_QA.json').read_text())['outputs']
    for nm, h in old.items():
        assert sha(OLD / nm) == h, nm                                                 # v1.3 outputs unchanged
    assert QA()['solver_executions'] == 0 and QA()['capacity_bridge_identity_ok'] is True
