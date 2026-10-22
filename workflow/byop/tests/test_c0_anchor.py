"""C0 ERCOT 2025 official anchor v1.3 (2026-10-22) - the limited, necessary tests of the work package (§5 acceptance).
No LP solver is called anywhere in this file. Run from pypsa-usa/workflow after the two builders:
    python byop/build/c0_anchor_evidence.py && python byop/build/c0_anchor_audit.py
    python -m pytest -q byop/tests/test_c0_anchor.py"""
from __future__ import annotations

import ast, hashlib, importlib.util, json, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WF = Path(__file__).resolve().parents[2]
BY = WF / 'byop'
sys.path.insert(0, str(BY / 'model'))
import byop_paths as BP  # noqa: E402

DER, OUT = BP.ANCHOR2025_DERIVED, BP.C0_RESULTS
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
QA = lambda: json.loads((OUT / 'C0_QA.json').read_text())


@pytest.fixture(scope='module')
def A():
    spec = importlib.util.spec_from_file_location('c0_anchor_audit', BY / 'build/c0_anchor_audit.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ source SHA
def test_source_sha_and_rebuild():
    man = json.loads(BP.ANCHOR2025_MANIFEST.read_text())
    if not BP.ANCHOR2025_RAW.exists():
        pytest.skip('official raw files not on this machine')
    for s in man['sources']:
        assert sha(BP.ANCHOR2025 / s['file']) == s['sha256'], s['file']
    chk = json.loads((DER / 'EVIDENCE_REBUILD_CHECK.json').read_text())
    assert chk['all_equal'] is True                                          # every derived table / metric = researcher's extract
    assert sha(BP.NATIVE_LOAD) == man['sources'][1]['sha256'] == '23664b0cddb047692f6cac26a4300e987c6309795395d394bf2dc223f37b53aa'


# ------------------------------------------------------------------------------------------------ load
def test_load_energy_and_peaks():
    v = json.loads((DER / 'VERIFIED_METRICS.json').read_text())
    assert v['rows'] == 8760 and abs(v['energy_TWh'] - 488.233578542299) < 1e-9
    assert abs(v['peak_1h_MW'] - 83679.001697) < 1e-6 and v['peak_1h_source_label'] == '08/18/2025 18:00'
    assert abs(v['peak_3h_MW'] - 83403.652115) < 1e-5 and abs(v['annual_report_minus_native_peak_MW'] - 27.998303) < 1e-6
    audit = json.loads((BP.BASE_TAMU_DIR / 'baseline_2025_tamu_audit.json').read_text())
    assert abs(audit['load']['peak_MW_3h'] - v['peak_3h_MW']) < 1e-3 and abs(audit['load']['ercot_native_2025_TWh'] - v['energy_TWh']) < 1e-9


def test_dst_and_24h_rows_kept_and_3h_conservation():
    h = pd.read_csv(DER / 'ERCOT_NATIVE_LOAD_2025_1H.csv')
    lab = h['Hour Ending'].astype(str)
    assert len(h) == 8760 and lab.str.contains('DST').sum() == 1 and lab.str.endswith('24:00').sum() == 365
    assert (np.diff(h.source_row_1based) == 1).all() and h.source_row_1based.iloc[0] == 2
    t = pd.read_csv(DER / 'ERCOT_NATIVE_LOAD_2025_3H.csv')
    assert len(t) == 2920 and (t.weight_hours == 3).all()
    assert abs(t.ERCOT.sum() * 3 - h.ERCOT.sum()) < 1e-3
    la = pd.read_csv(OUT / 'C0_LOAD_ACCOUNTING.csv')
    assert la.check.astype(bool).all(), la[~la.check.astype(bool)]


def test_historical_load_not_double_counted():
    src = (BY / 'model/rearch_mech.py').read_text(encoding='utf-8')
    la = pd.read_csv(OUT / 'C0_LOAD_ACCOUNTING.csv').set_index('component')
    assert la.value['historical_AIDC_2025_avg_added_on_top'] == 0 and la.value['background_load_scale_factor_2025'] == 1.0
    assert 'IT_MW_2025_avg' not in src                                        # no 2025 stock Load added by the model
    assert "f'{x.bus} inherited_ramp'" in src and abs(la.value['inherited_ramp_IT_MW_from_2026'] - 460.73) < 1e-6
    assert la.value['baseline_bus_load_per_step_max_abs_error_MW'] < 1e-3


# ------------------------------------------------------------------------------------------------ generator match / bridge
def test_tech_map_equals_baseline_builder(A):
    tree = ast.parse((BY / 'build/build_2025_baseline_tamu.py').read_text(encoding='utf-8'))
    tm = [n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'TECH_MAP'][0]
    assert ast.literal_eval(tm.value) == A.TECH_MAP


def test_no_unit_counted_twice():
    m = pd.read_csv(OUT / 'C0_GENERATOR_MATCH.csv')
    c = m[(m.side == 'CDR') & m.model_group_key.notna() & (m.model_group_key != '')]
    assert (c.groupby('model_group_key').cdr_group_key.nunique() <= 1).all()     # one model group <-> one CDR group
    ids = [i for s in m.drop_duplicates('model_group_key').model_unique_ids.dropna() for i in str(s).split(';') if i]
    assert len(ids) == len(set(ids))                                              # every ReEDS unit in exactly one group
    assert not (set(m[m.side == 'MODEL'].model_group_key) & set(c.model_group_key))
    assert QA()['no_model_group_matched_twice'] is True
    assert (m.note_numeric_use.str.startswith('audit only')).all()


def test_plan_never_in_2025_history(A):
    assert A.scope_bucket('PLAN', 'CONV') == 'PLANNED_NOT_2025' and A.scope_bucket('PLAN-SLF', 'CONV-SLF') == 'PLANNED_NOT_2025'
    assert A.scope_bucket('MOTH-IND', 'CONV') == 'MOTHBALLED_INDEFINITE' and A.scope_bucket('OPER-SYN', 'CONV') == 'OPERATING_QUALIFIED'
    assert A.scope_bucket('OPER', 'DC-TIE') == 'DC_TIE' and A.scope_bucket('OPER', 'CONV-SLF') == 'PRIVATE_NETWORK'
    m = pd.read_csv(OUT / 'C0_GENERATOR_MATCH.csv')
    c = m[m.side == 'CDR']
    assert not c[c.cdr_status.astype(str).str.startswith('PLAN')].cdr_core_2025.any()
    assert not c[c.in_service_le_2025 == 'NO'].cdr_core_2025.any()
    assert not c[c.scope_bucket.isin(['DC_TIE', 'PRIVATE_NETWORK', 'DISTRIBUTION_DG', 'SWITCHABLE_UNAVAILABLE_ADJ'])].cdr_core_2025.any()
    assert QA()['plan_units_in_2025_core'] == 0


def test_capacity_bridge_identity_and_no_scaling():
    b = pd.read_csv(OUT / 'C0_CAPACITY_BRIDGE.csv')
    idc = b[b.component == 'identity_check_cdr_core_minus_model']
    assert len(idc) == 8 and (idc.MW.abs() < 1e-6).all()
    ar = b[b.component == 'annual_report_installed_MW'].MW.sum()
    assert ar == 184904                                                           # broad AR total kept as a diagnostic only
    mod = b[(b.component == 'model_active2025_summer_MW') & b.family.str.startswith('ALL:')].MW.sum()
    fleet = json.loads((BP.BASE_TAMU_DIR / 'baseline_2025_tamu_audit.json').read_text())['fleet_2025_MW_total']
    assert abs(mod - fleet) < 0.05                                                # model fleet unchanged (no 184.9 / 155.05 scaling)
    nuc = b[(b.family == 'nuclear') & (b.component == 'decomp_rating_diff')].MW.iloc[0]
    assert abs(nuc - (5268.0 - 4980.0)) < 1e-6                                    # the package's rating example
    assert b[b.component == 'UNEXPLAINED_AR_minus_cdr_core_MW'].basis.str.contains('NOT allocated').all()


def test_name_normalisation(A):
    assert A.norm_tokens('COMANCHE PEAK U1') == A.norm_tokens('Comanche Peak') == ('COMANCHE', 'PEAK')
    assert A.norm_tokens('FORNEY ENERGY CENTER CTG 11') == ('FORNEY',)
    assert A.norm_tokens('Capricorn Ridge Wind 4') == ('CAPRICORN', 'RIDGE')
    assert A.similarity(('CAPRICORN', 'RIDGE'), ('CAPRICORN', 'RIDGE', 'EAST')) >= 0.75 and A.similarity(('A1',), ('B2',)) == 0.0


# ------------------------------------------------------------------------------------------------ historical AIDC
def test_historical_aidc_labels_and_values():
    d = pd.read_csv(OUT / 'C0_HISTORICAL_AIDC_EVIDENCE.csv')
    st = pd.read_csv(BP.INPUTS / 'dc/EPOCH_TX_SITES_TAMU64.csv')
    st = st[st.ercot].set_index('site')
    for r in d.itertuples():                                                      # values unchanged
        assert r.IT_MW_2025_avg == st.IT_MW_2025_avg[r.site] and r.IT_MW_2025_end == st.IT_MW_2025[r.site] and r.bus == st.bus[r.site]
    assert d.algebra_end_minus_avg_ok.all() and d.bus_ramp_matches_MAINLINE_INHERITED_RAMP.all()
    assert abs(d.inherited_ramp_IT_MW.sum() - 460.73) < 1e-6
    six = {'OpenAI Stargate Abilene', 'CoreWeave Denton TX', 'Meta Temple', 'Google Red Oak', 'Microsoft SAT40', 'Microsoft SAT14'}
    assert six <= set(d[d.evidence_class != 'NO_2025_CAPACITY'].site)
    assert not d.evidence_class.str.startswith('VERIFIED').any()                  # nothing silently upgraded to verified
    assert d.set_index('site').evidence_class['Meta Temple'] == 'ESTIMATE__2025_OPERATION_NOT_CONFIRMED'
    assert d[d.inherited_ramp_IT_MW > 0].ramp_label.eq('LOAD_PROXY_FROM_HISTORICAL_CAPACITY_ESTIMATE').all()


# ------------------------------------------------------------------------------------------------ uplift
def test_uplift_layers_not_double():
    u = pd.read_csv(OUT / 'C0_UPLIFT_LEDGER.csv')
    assert (u.final_identity_error_MVA.abs() < 1e-3).all()                         # final = interface rule + 2025 uplift (once)
    cal = u[u.calibration_uplift_MVA > 0.5]
    assert len(cal) == 18 and abs(cal.calibration_uplift_MVA.sum() - 4993.9) < 0.1
    assert cal.calibration_LP_listed.all()
    s0 = u[u.layer3_S0CAL_2026plus_added_MW > 0.5]
    assert len(s0) == 9 and abs(s0.layer3_S0CAL_2026plus_added_MW.sum() - 1095.6) < 0.1
    assert u.S0CAL_existing_equals_final_s_nom.all()                             # S0CAL built on the final 2025 s_nom, as Links
    assert (s0.layer3_form.str.contains('Link')).all()
    q = QA()['uplift']
    if (q.get('baseline_nc') or {}).get('status') == 'CHECKED':
        assert q['baseline_nc']['ok'] is True


# ------------------------------------------------------------------------------------------------ no solver
def test_no_solver_call_in_c0_code():
    for f in ('build/c0_anchor_evidence.py', 'build/c0_anchor_audit.py'):
        tree = ast.parse((BY / f).read_text(encoding='utf-8'))
        mods = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        calls = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, 'id', '') for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not mods & {'linopy', 'gurobipy', 'build_2025_baseline_tamu', 'rearch_mech', 'v240_mech'}, (f, mods)
        assert not calls & {'optimize', 'solve', 'calibrate_2025', 'solve_model'}, (f, calls)
        if f.endswith('evidence.py'):
            assert 'pypsa' not in mods
    assert QA()['solver_executions'] == 0


def test_no_personal_drive_paths():
    for p in list((BY / 'build').glob('*.py')) + list((BY / 'model').glob('*.py')):
        assert 'D:/' not in p.read_text(encoding='utf-8') and 'D:\\\\' not in p.read_text(encoding='utf-8'), p.name
