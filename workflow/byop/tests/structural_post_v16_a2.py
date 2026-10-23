#!/usr/bin/env python3
"""NEXT-01 A2-STATIC structural test: builds the post-v1.6 S0 and S1_EARLIEST multi-period models (v1.6 baseline, dynamic_pnnl_v1
16 buses, TECH_COMP_2, 3 GW operating reserve instead of the legacy ERM, no ERM-02 / S0CAL, RE+BESS firm certificate in serve_cap)
and inspects them. NO SOLVER IS CALLED: linopy.Model.solve and gurobipy.Model.optimize raise before anything reaches a solver.
Run on L2 from the A2 worktree workflow/:
    python -W ignore byop/tests/structural_post_v16_a2.py --out results/BYOP/post_v16_a2_static/_structural
"""
from __future__ import annotations

import argparse, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, 'byop/model')
import linopy  # noqa: E402
import pypsa  # noqa: E402
import rearch_mech as R  # noqa: E402
import post_v16_mainline as PM  # noqa: E402
import byop_paths as BP  # noqa: E402

M, w2, V, STATE = R.M, R.w2, R.V, R.STATE
SOLVER_CALLS = []


class StopBeforeSolve(Exception):
    pass


def _no_solve(self, *a, **k):
    SOLVER_CALLS.append('refused')
    raise StopBeforeSolve()


linopy.Model.solve = _no_solve
try:
    import gurobipy
    gurobipy.Model.optimize = _no_solve
except Exception:
    pass
CHK = []
CFG_PATH = 'config/config.byop_ercot_mainline_geo_dynamic_v1_baseline_v16.yaml'


def check(qa, name, ok, detail=''):
    CHK.append(dict(qa=qa, check=name, result='PASS' if ok else 'FAIL', detail=str(detail)[:400]))
    print(f"[{'PASS' if ok else 'FAIL'}] {qa} {name} {detail if not ok else ''}")


def build_model(tag, scen, **kw):
    n, mult = M.build(CONFIG, scen, 2.8e6, **kw)
    try:
        M.solve(CONFIG, tag, OUT, n)
    except StopBeforeSolve:
        pass
    return n, n.model


def labels(v):
    return set(np.asarray(v.labels.values).ravel()) - {-1}


def next02_audits(tag, n, m):
    """NEXT-02 A2-FIX-01..05 structural evidence on the built model (no solver)"""
    obj = PM.objective_coefficients(m)
    ay = dict(STATE.get('approval_year', {}))
    pa = PM.expansion_pair_audit(n, m, corridors=STATE.get('corridors'), approval_year=ay, obj=obj)
    pa.insert(0, 'scenario', tag); pa.to_csv(OUT / f'EXPANSION_PAIR_AUDIT_{tag}.csv', index=False)
    check('QA-PAIR', f'{tag}: every AC_exp fwd / rev pair tied by M2-line_sym (rev-only and fwd-only rejected), fwd priced once, corridor cap',
          len(pa) > 0 and bool(pa.PASS.all()), dict(pairs=len(pa), fail=int((~pa.PASS.astype(bool)).sum()) if len(pa) else None))
    ca = PM.committed_links_audit(n, m)
    ca.insert(0, 'scenario', tag); ca.to_csv(OUT / f'COMMITTED_LINKS_AUDIT_{tag}.csv', index=False)
    check('QA-PAIR', f'{tag}: committed DWB / PBRP links fixed, cost-free in the LP, outside every expansion row', len(ca) >= 2 and bool(ca.PASS.all()), len(ca))
    co = PM.cod_activity_audit(n, m, approval_year=ay, obj=obj)
    co.insert(0, 'scenario', tag); co.to_csv(OUT / f'COD_ACTIVITY_AUDIT_{tag}.csv', index=False)
    check('QA-COD', f'{tag}: every public candidate inactive before its build year, priced in the objective, approval <= build',
          len(co) > 0 and bool(co.PASS.all()), dict(n=len(co), fail=int((~co.PASS.astype(bool)).sum())))
    ce = co[(co.approval_year == 2027) & (co.build_year == 2029)]
    check('QA-COD', f'{tag}: counter-example 2027 order / 2029 COD exists and is unavailable in 2027-28 (same rule in S0 and S1)',
          len(ce) > 0 and not ce.active_before_build.any(), dict(n=len(ce), example=ce.name.iloc[0] if len(ce) else None))
    sw = n.snapshot_weightings
    check('QA-SOC', f'{tag}: storage SOC advances by the elapsed 3 h (stores weighting) while objective / generators keep the sample weight',
          np.allclose(sw.stores.values, M.SNAP_HOURS) and float(sw.generators.sum()) > 8000, dict(stores=sorted(set(np.round(sw.stores, 3)))[:3], gen_sum=float(sw.generators.sum())))
    cons = set(m.constraints)
    ok_start = 'PV16M-res_su_energy_start' in cons
    if ok_start:
        e = m.constraints['PV16M-res_su_energy_start'].lhs
        v_ = set(np.asarray(e.vars.values).ravel()) - {-1}
        ok_start = bool(v_ & labels(m['StorageUnit-p_dispatch'])) and bool(v_ & labels(m['StorageUnit-p_store'])) and bool(v_ & labels(m['StorageUnit-state_of_charge']))
    check('QA-SOC', f'{tag}: reserve energy also bounded at the START of each snapshot (dispatch SOC + same-snapshot flows, no shadow SOC)', ok_start)
    check('QA-RES', f'{tag}: reserve rows tie thermal r to online capacity - dispatch, ramp and min-load on the same online variable',
          {'PV16M-res_thermal_head', 'PV16M-res_ramp', 'PV16M-online_min', 'PV16M-online_max_p'} <= cons)
    # NEXT-03 A2-FIX-08: sampled segments, PyPSA's SOC chain across the gaps, and the segment-neutrality rows that cut it
    sm = PM.segment_map(n, stress_ts=sorted(STATE.get('stress_ts') or []))
    sm.insert(0, 'scenario', tag); sm.to_csv(OUT / f'A2_SOC_SEGMENT_MAP_{tag}.csv', index=False)
    info = STATE.get('pv16m_soc_segments') or {}
    sns = n.snapshots
    seg = PM.soc_segments(sns)
    b = seg[seg.segment != seg.segment.shift()].iloc[1:]                       # first snapshot of every segment after the first
    b = b[[int(seg.period.iloc[int(q) - 1]) == int(pr) for q, pr in zip(b.pos, b.period)]] if len(b) else b   # within-period gaps only
    linked = 0
    if len(b) and len(n.storage_units):
        x = n.storage_units.index[0]
        soc_l = m['StorageUnit-state_of_charge']
        eb = m.constraints['StorageUnit-energy_balance'].lhs
        for _, r in b.iterrows():
            prev_lab = int(soc_l.sel(name=x, snapshot=sns[int(r.pos) - 1]).labels.values)
            linked += int(prev_lab in set(np.asarray(eb.sel(name=x, snapshot=sns[int(r.pos)]).vars.values).ravel()))
    check('QA-SOCSEG', f'{tag}: PyPSA chains SOC across every within-period time gap (risk confirmed on the real model)',
          len(b) > 0 and linked == len(b), dict(gaps=len(b), linked=linked))
    act = n.components['StorageUnit'].get_activity_mask(sns)
    expected = int(sum(int((act.loc[sns[d.pos.iloc[0]]] & act.loc[sns[d.pos.iloc[-1]]]).sum()) for _, d in seg.groupby('segment')))
    check('QA-SOCSEG', f'{tag}: one segment-neutrality row per active StorageUnit x segment (no binaries)',
          info.get('rows') == expected and info.get('segments') == seg.segment.nunique() and int(len(m.binaries) + len(m.integers)) == 0,
          dict(rows=info.get('rows'), expected=expected, segments=info.get('segments')))
    check('QA-SOCSEG', f'{tag}: segments never span a time gap or a period; stress events kept contiguous',
          bool((seg.groupby('segment').period.nunique() == 1).all()) and bool((seg.groupby('segment').timestep.apply(
              lambda t: (t.diff().dropna() == pd.Timedelta(hours=3)).all())).all()))
    nh = PM.no_harm_qa(n, m, tag)
    nh.to_csv(OUT / f'NATIVE_LOAD_NO_HARM_QA_{tag}.csv', index=False)
    if tag == 'S1_EARLIEST':
        ls = nh[nh.carrier == 'load_shed']
        check('QA-NOHARM', 'S1_EARLIEST: every existing-customer shed unit (native + inherited ramp) in the D24 no-harm row',
              len(ls) == 1 and int(ls.units.iloc[0]) == int(ls.in_no_harm_row.iloc[0]) > 0, ls.to_dict('records'))
        check('QA-NOHARM', 'S1_EARLIEST: no study-AIDC unserved / interruption unit inside the no-harm row',
              int(nh[nh.carrier != 'load_shed'].in_no_harm_row.sum()) == 0)
    if tag in ('S0', 'S1_EARLIEST'):
        check('QA-F5', f'{tag}: no RE+BESS firm certificate rows (A2-FIX-05: S0 / S1 do not rely on BYOP RE+BESS firm)',
              not [x for x in m.variables if x.startswith('A2-F_cert_')])


def main():
    global CONFIG, OUT
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    R.BASE_TAMU = BP.BASE_TAMU_V16
    siting = R.ml_select_siting(CFG_PATH)
    R.ML.update(on=True, stress_days=3, stress_line_derate=1.0, gate=dict(approved=False, reasons=['A2_STATIC_STRUCTURAL_TEST']))
    R.GCFG.update(setting='G-REAL', competing=0.0, regional_dc='off', case='base', gas_case='base', relax=[], s2_modes=R.MODES,
                  interrupt_cap=0.005, no_harm=True, base_assets='main', s0_calibrate=False, s0_cal_file=None)
    M.CFG.update(periods='annual', start=2026, end=2031, cost_basis='repaired', public_subsidy='without', tariff='energy', reuse='on',
                 reuse_case='base', frac_cod=True, flex=False, poi_lead=0, byop_case='base', public_case='base', byop_techs=list(R.ML_TECHS),
                 sample_weeks=26, bg_growth=0.0, line_exp=True, erm15=False, threads=4, v=2.8e6, v_private=None, smoke=False, dem_scale=1.0)
    M.CFG['tech_version'] = R.ml_tech_version(CFG_PATH)
    PM.POST_V16['on'] = True
    w2.POST_V16_NO_ERM['on'] = True
    R.configure_mainline(OUT)
    M.build = R.build_rearch; M.extra = R.extra_rearch
    w2.store_ERM_duals = V.store_erm_duals_tx; V.GCFG.update(erm_scope='tx')
    w2.PREP = str(R.BASE_TAMU); w2.PUE = pd.read_csv(w2.PUE_CSV)
    CONFIG = pypsa.Network(str(R.BASE_TAMU)).meta
    STATE['erm_cal'] = None
    sites = sorted(R.SITES)
    check('QA-BASE', 'v1.6 baseline file and SHA', Path(R.BASE_TAMU).resolve() == BP.BASE_TAMU_V16.resolve() and M.sha(R.BASE_TAMU) == BP.BASE_TAMU_V16_SHA256)
    check('QA-VERSION', 'TECH_COMP_2 selected by the post-v1.6 config; siting dynamic_pnnl_v1', M.CFG['tech_version'] == 'TECH_COMP_2' and siting['variant'] == 'dynamic_pnnl_v1', siting['variant'])
    check('QA-SPACE', '16 research buses (no hard-coded 8 / 17)', len(sites) == 16, len(sites))
    check('QA-FIPS', 'site county FIPS attached (8 known, 8 UNKNOWN_CONSERVATIVE)', sum(bool(R.SITES[s].get('county_fips')) for s in sites) == 8)
    res = {}
    for tag, scen, kw in (('S0', 'S0', {}), ('S1_EARLIEST', 'S', {}), ('S3', 'S', dict(byop=list(R.ML_TECHS), reuse_dedicated=True))):
        STATE['firm_strict'] = True; STATE['lex'] = None
        STATE.pop('v2_pool_candidates', None); STATE.pop('byop_cod', None); STATE.pop('pv16m_re_firm', None)
        if tag == 'S1_EARLIEST':      # NEXT-02: a SYNTHETIC zero S0 shed reference, only so the D24 no-harm row is built and inspected
            n0_ = res['S0']['n']
            sc0 = n0_.generators.index[n0_.generators.carrier == 'load_shed']
            STATE['shed_S0'] = pd.DataFrame(0.0, index=n0_.snapshots, columns=sc0)
        n, m = build_model(tag, scen, **kw)
        if tag == 'S1_EARLIEST':
            STATE['shed_S0'] = None
        if tag == 'S3':
            res[tag] = dict(n=n, m=m, byop_cod=dict(STATE.get('byop_cod', {})), re_firm=list(STATE.get('pv16m_re_firm') or []))
        names = list(m.variables); cons = list(m.constraints)
        res.setdefault(tag, dict(n=n, m=m))
        check('QA-NOERM', f'{tag}: no legacy ERM row / shadow storage / ERM-02 margin', not [c for c in cons if 'ERM' in c] and not [v for v in names if v.endswith('_RESERVES') or 'erm_margin' in v],
              [c for c in cons if 'ERM' in c][:3])
        check('QA-LP', f'{tag}: continuous LP (no integer / binary)', int(len(m.binaries) + len(m.integers)) == 0)
        req = m.constraints['PV16M-reserve_req'] if 'PV16M-reserve_req' in cons else None
        check('QA-RES', f'{tag}: 3,000 MW reserve row in every snapshot', req is not None and np.allclose(req.rhs.values, 3000.0) and req.rhs.size == len(n.snapshots),
              None if req is None else req.rhs.size)
        if 'PV16M-res_su_energy' in cons:
            e = m.constraints['PV16M-res_su_energy'].lhs
            v_ = set(e.vars.values.ravel()) - {-1}
            check('QA-RES', f'{tag}: storage reserve energy uses the dispatch SOC (no shadow SOC)', v_ <= labels(m['StorageUnit-state_of_charge']) | labels(m['PV16M-res_su']) and bool(v_ & labels(m['StorageUnit-state_of_charge'])))
        el = list(m['PV16M-res_thermal'].coords['name'].values)
        check('QA-RES', f'{tag}: reserve-eligible units exclude DC-bus BYOP and load_shed', not any(str(n.generators.bus[x]).startswith('DC_') or n.generators.carrier[x] == 'load_shed' for x in el), len(el))
        check('QA-RES', f'{tag}: extendable public thermal candidates carry reserve via p_nom (online_cap_ext)', 'PV16M-online_cap_ext' in cons)
        led = PM.public_expansion_ledger(n, M.periods(), m=m)
        led.assign(scenario=tag).to_csv(OUT / f'PUBLIC_EXPANSION_LEDGER_{tag}.csv', index=False)
        check('QA-PUBLIC', f'{tag}: no free endogenous public expansion; S0CAL absent; every rev priced via a verified fwd equality',
              not led.status.isin(['FREE_FORBIDDEN', 'S0CAL_FORBIDDEN', 'PAIR_UNVERIFIED']).any(), led.status.value_counts().to_dict())
        next02_audits(tag, n, m)
        check('QA-PUBLIC', f'{tag}: committed TPIT / PBRP links listed as sunk common assets', (led.status.str.startswith('COMMITTED')).sum() >= 2, int(led.status.str.startswith('COMMITTED').sum()))
        res[tag]['ledger'] = led
    n0, n1, m1 = res['S0']['n'], res['S1_EARLIEST']['n'], res['S1_EARLIEST']['m']
    f0, f1 = PM.public_inputs_fingerprint(n0), PM.public_inputs_fingerprint(n1)
    same_parts = {k: f0[k]['sha256'] == f1[k]['sha256'] for k in f0}
    (OUT / 'S0_S1_IDENTICAL_PUBLIC_INPUTS.json').write_text(json.dumps(dict(
        rule='S0 and S1_EARLIEST share every non-DC-bus component, profile, line, native / inherited load, weighting and cost; '
             'only the study-AIDC rows at DC_ buses (and their POI links) differ', S0=f0, S1_EARLIEST=f1, identical=same_parts,
        all_identical=all(same_parts.values()), committed_assets=sorted(n0.links.index[n0.links.carrier.isin(['AC_base_committed', 'AC_committed'])]),
        reserve=STATE.get('pv16m_reserve'), committed_cost_ledger=PM.committed_cost_ledger('base').to_dict('records')), indent=1, default=str))
    check('QA-S0S1', 'NEXT-02: S0 / S1_EARLIEST public inputs identical (hash per component table)', all(same_parts.values()),
          [k for k, v in same_parts.items() if not v])
    # S0 vs S1 common initial assets (non-DC)
    def common(n):
        g = n.generators[~n.generators.bus.astype(str).str.startswith('DC_') & (n.generators.carrier != 'load_shed')]
        return g[['bus', 'carrier', 'p_nom', 'p_nom_extendable', 'capital_cost', 'build_year']].sort_index()
    a0, a1 = common(n0), common(n1)
    same = a0.index.equals(a1.index) and np.allclose(a0.p_nom.values, a1.p_nom.values) and np.allclose(a0.capital_cost.values, a1.capital_cost.values)
    check('QA-S0S1', 'S0 and S1 share the same public generators / candidates / costs (only AIDC rows differ)', same, (len(a0), len(a1)))
    check('QA-S0S1', 'S0 and S1 share lines and committed links', n0.lines.index.equals(n1.lines.index) and
          set(n0.links.index[n0.links.carrier.isin(['AC_base_committed', 'AC_committed'])]) == set(n1.links.index[n1.links.carrier.isin(['AC_base_committed', 'AC_committed'])]))
    # POI phasing per site / year in S1 (not a joint lambda = 0)
    poi = [c for c in m1.constraints if c.startswith('POI-eq_')]
    rhs = {c: float(np.asarray(m1.constraints[c].rhs.values).ravel().max()) for c in poi}
    per_site_2026 = {d['zone']: rhs.get(f"POI-eq_{d['S']}") for d in STATE['dc'] if d['period'] == 2026}
    check('QA-POI', 'S1 POI equipment phased per site and year (some sites > 0 in 2026, others 0)',
          any((v or 0) > 0 for v in per_site_2026.values()) and any((v or 0) == 0 for v in per_site_2026.values()), per_site_2026)
    # TECH_COMP_2 candidates, supply pools and RE+BESS firm certificate: S3 (S2 uses the same physical builder, cost basis differs)
    n3, m3 = res['S3']['n'], res['S3']['m']
    g3 = n3.generators
    byop = g3.index[g3.carrier.str.startswith('byop_')]
    aud = {k: v for k, v in res['S3']['byop_cod'].items() if v.get('tech_version') == 'TECH_COMP_2'}
    check('QA-S1', 'S1_EARLIEST is Grid-Only (no BYOP candidates)', not n1.generators.carrier.str.startswith('byop_').any())
    check('QA-TECH2', 'S3: BYOP candidates built from TECH_COMP_2 with permit / COD audit', len(aud) > 0 and all(v['permit_audit'] is not None for v in aud.values() if v['carrier'] in ('RICE', 'SOFC_NG', 'OCGT_aero')), len(aud))
    check('QA-TECH2', 'S3: CONTROLLED_ENV candidates for RICE / aero only', any(' CTRL ' in x for x in byop) and not any('SOFC_NG CTRL' in x for x in byop))
    check('QA-TECH2', 'S3: every BYOP candidate has a positive capital cost and a COD-consistent build year',
          (g3.capital_cost[byop] > 0).all() and all(M.first_period(v['cod']) == v['build'] for v in aud.values()))
    pools = [c for c in m3.constraints if c.startswith('V2-supply_pool_')]
    check('QA-SUPPLY', 'S3: common supply-pool rows V2-supply_pool_<tech>_<year> present (2026-2031 only)', len(pools) > 0 and all(int(c[-4:]) <= 2031 for c in pools), pools[:8])
    rf = res['S3']['re_firm']
    fvars = [v for v in m3.variables if v.startswith('A2-F_cert_')]
    in_cap = 0
    for d in STATE['dc']:                                   # STATE['dc'] is the S3 build here
        fv, nm = f"A2-F_cert_{d['zone']}_{d['period']}", f"M2-serve_cap_{d['S']}"
        if fv in m3.variables and nm in m3.constraints:
            in_cap += int(bool(labels(m3[fv]) & set(np.asarray(m3.constraints[nm].lhs.vars.values).ravel())))
    check('QA-REFIRM', 'S3: RE+BESS firm certificate variables built and entered into serve_cap', len(fvars) > 0 and in_cap == len(fvars), (len(fvars), in_cap))
    check('QA-REFIRM', 'S3: certificate SOC boundary rows on the dispatch SOC', any(c.startswith('A2-F_soc_start_') for c in m3.constraints))
    check('QA-NOERM', 'S3: no legacy ERM / shadow SOC', not [c for c in m3.constraints if 'ERM' in c] and not [x for x in m3.variables if x.endswith('_RESERVES')])
    check('QA-LP', 'no solver was called (only intercepted model calls)', all(c == 'refused' for c in SOLVER_CALLS), SOLVER_CALLS)
    rf = res['S3']['re_firm']
    rep = dict(stage='A2_STATIC_STRUCTURAL', solver_executions=0, solver_calls_intercepted=len(SOLVER_CALLS), siting=siting['variant'], research_buses=sites,
               n_checks=len(CHK), n_pass=sum(c['result'] == 'PASS' for c in CHK), n_fail=sum(c['result'] == 'FAIL' for c in CHK),
               n_vars={k: int(v['m'].nvars) for k, v in res.items()}, n_cons={k: int(v['m'].ncons) for k, v in res.items()},
               reserve=STATE.get('pv16m_reserve'), re_firm_rows=rf[:20], re_firm_count=len(rf), seconds=round(time.time() - t0, 1),
               base_sha256=M.sha(R.BASE_TAMU), tech_version=M.CFG['tech_version'])
    pd.DataFrame(CHK).to_csv(OUT / 'A2_STRUCTURAL_CHECKS.csv', index=False)
    (OUT / 'A2_STRUCTURAL_REPORT.json').write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: v for k, v in rep.items() if k not in ('re_firm_rows',)}, indent=1, default=str))


if __name__ == '__main__':
    main()
