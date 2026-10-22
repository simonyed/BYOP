#!/usr/bin/env python3
"""Post-v1.6 execution package v1.1: A1 joint AIDC headroom (LP-R H_resource, LP-N H_network), run on L2 from workflow/:
    python byop/run/post_v16_a1.py --dry                     # A0: build both models + structural checks + sizes, NO solver
    python byop/run/post_v16_a1.py --gate --lp R             # print the gate verdict only (no build, no solver)
    python byop/run/post_v16_a1.py --lp R --base <v1.6 nc>   # A1 (needs the researcher's approval in the config)
    python byop/run/post_v16_a1.py --lp N --base <v1.6 nc>   # A1, only after an optimal LP-R
Config: config/config.byop_post_v16_a1.yaml. Every --lp call goes through post_v16_gate.check() FIRST (before any network is
read); a refused gate exits 3. Zero automatic retries; every call is logged in HEADROOM_SOLVE_LOG.csv.
"""
from __future__ import annotations

import argparse, hashlib, json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import byop_paths as BP  # noqa: E402
import post_v16_gate as G  # noqa: E402

CFG = WF / 'config/config.byop_post_v16_a1.yaml'
OUT = BP.POST_V16_RESULTS
LOG = OUT / 'HEADROOM_SOLVE_LOG.csv'
STAGE = {'R': 'LP_R_H_RESOURCE', 'N': 'LP_N_H_NETWORK'}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def shares_csv():
    return BP.BASE_TAMU_V16_DIR / 'COUNTY_TO_BUS_SHARES.csv'


def build(mode, base):
    import post_v16_headroom as H
    cfg = H.load_cfg(CFG)
    n, info = H.build_network(cfg, mode, base, shares_csv())
    n.optimize.create_model()
    info['headroom'] = H.add_headroom(n, cfg, info)
    info['structure'] = H.structural_checks(n, info)
    return n, info, cfg


def log_call(stage, status, term, sec, note=''):
    lg = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame(columns=['timestamp_utc', 'stage', 'attempt', 'status', 'termination', 'seconds', 'note'])
    lg = pd.concat([lg, pd.DataFrame([dict(timestamp_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'), stage=stage,
                                           attempt=int((lg.stage == stage).sum()) + 1, status=status, termination=term,
                                           seconds=round(sec, 1), note=note)])], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    lg.to_csv(LOG, index=False, lineterminator='\n')


# ------------------------------------------------------------------------------------------------ outputs (pure pandas)
def solution_view(n, info):
    """everything the writers need, as pandas objects (so the writers are testable without a solver)"""
    m = n.model
    sol = m.solution
    g = n.generators
    return dict(lam=float(sol['PV16-lambda'].values), weights=pd.DataFrame(info['weights']).set_index('bus'), meta=info['meta'],
                p=n.generators_t.p.copy(), carrier=g.carrier.copy(), bus=g.bus.copy(), p_nom=g.p_nom.copy(),
                r_thermal=sol['PV16-res_thermal'].to_pandas(), online=sol['PV16-online_cap'].to_pandas(),
                r_su=sol['PV16-res_su'].to_pandas() if 'PV16-res_su' in sol else pd.DataFrame(),
                su_dispatch=n.storage_units_t.p_dispatch.copy(), su_store=n.storage_units_t.p_store.copy(),
                soc=n.storage_units_t.state_of_charge.copy(), su_pnom=n.storage_units.p_nom.copy(),
                su_effd=n.storage_units.efficiency_dispatch.copy(), p0=n.lines_t.p0.copy(),
                limit=(n.lines.s_nom * n.lines.s_max_pu).copy(), line_bus0=n.lines.bus0.copy(), line_bus1=n.lines.bus1.copy(),
                zone=n.buses.reeds_zone.copy() if 'reeds_zone' in n.buses else pd.Series(dtype=str),
                load=n.loads_t.p.T.groupby(n.loads.bus).sum().T if not n.loads_t.p.empty else n.loads_t.p_set.T.groupby(n.loads.bus).sum().T,
                duals_line=None, R=float(info['reserve_MW']), tau=float(info['tau_h']), mode=info['mode'])


def write_outputs(v, out, tag):
    """HEADROOM_BY_BUS, STRESS_DISPATCH_RESERVE_QA, NETWORK_PRESSURE_DIAGNOSTICS rows for one LP; returns summary dict"""
    meta = v['meta']
    w = v['weights']
    lam = v['lam']
    hb = w.assign(stage=tag, lambda_facility_MW=lam, h_facility_MW=lam * w.w, h_IT_MW=lam * w.w / w.PUE_TX_2031)
    hb.reset_index().to_csv(out / f'HEADROOM_BY_BUS_{tag}.csv', index=False, lineterminator='\n')
    shed_cols = [x for x in v['p'].columns if v['carrier'][x] == 'load_shed']
    shed = v['p'][shed_cols].sum(axis=1)
    rs = v['r_su'].sum(axis=1) if len(v['r_su']) else pd.Series(0.0, index=meta.index)
    rt = v['r_thermal'].sum(axis=1)
    simul = ((v['su_dispatch'] > 1e-3) & (v['su_store'] > 1e-3))
    rs_simul = (v['r_su'].where(simul, 0.0).sum(axis=1) if len(v['r_su']) else rs * 0)
    qa = pd.DataFrame(dict(stage=tag, block=meta.block.values, period=meta.period.values, source_row=meta.source_row.values,
                           reserve_requirement_MW=v['R'], reserve_thermal_MW=rt.values, reserve_storage_MW=rs.values,
                           reserve_total_MW=(rt + rs).values, reserve_slack_MW=(rt + rs - v['R']).values,
                           reserve_storage_in_simultaneous_charge_discharge_MW=rs_simul.values,
                           existing_shed_MW=shed.values, load_MW=v['load'].sum(axis=1).values,
                           timestep=meta.index.get_level_values(-1)), index=meta.index)
    # storage energy backing check (same SOC): tau x r / eff <= soc
    if len(v['r_su']):
        need = v['r_su'].mul(v['tau'] / v['su_effd'][v['r_su'].columns], axis=1)
        qa['storage_energy_backing_min_margin_MWh'] = (v['soc'][v['r_su'].columns] - need).min(axis=1).values
    qa.to_csv(out / f'STRESS_DISPATCH_RESERVE_QA_{tag}.csv', index=False, lineterminator='\n')
    load_ = v['p0'].abs().div(v['limit'], axis=1)
    near = (load_ >= 0.99)
    diag = pd.DataFrame(dict(stage=tag, line=v['limit'].index, bus0=v['line_bus0'].values, bus1=v['line_bus1'].values,
                             zone0=v['line_bus0'].map(v['zone']).values, zone1=v['line_bus1'].map(v['zone']).values,
                             limit_MW=v['limit'].values, hours_ge_99pct_BL=near[(meta.block == 'BL').values].sum().values,
                             hours_ge_99pct_B0=near[(meta.block == 'B0').values].sum().values, max_loading=load_.max().values))
    diag.sort_values('hours_ge_99pct_BL', ascending=False).to_csv(out / f'NETWORK_PRESSURE_DIAGNOSTICS_{tag}.csv', index=False, lineterminator='\n')
    return dict(lambda_facility_MW=lam, lambda_IT_MW=float((lam * w.w / w.PUE_TX_2031).sum()),
                existing_shed_MWh_B0=float(shed[(meta.block == 'B0').values].sum()), existing_shed_MWh_BL=float(shed[(meta.block == 'BL').values].sum()),
                reserve_min_slack_MW=float(qa.reserve_slack_MW.min()), reserve_storage_simultaneous_MW_max=float(qa.reserve_storage_in_simultaneous_charge_discharge_MW.max()),
                lines_near_limit_BL=int((diag.hours_ge_99pct_BL > 0).sum()))


def balance_residual(n):
    """max |generation + storage - load - line withdrawals| per bus and hour (MW)"""
    b = n.buses.index
    g, su, L = n.generators, n.storage_units, n.lines
    grp = lambda df, by: df.T.groupby(by).sum().T.reindex(columns=b, fill_value=0.0)
    inj = grp(n.generators_t.p, g.bus).add(grp(n.storage_units_t.p, su.bus), fill_value=0.0)
    inj = inj.sub(grp(n.loads_t.p, n.loads.bus), fill_value=0.0)
    inj = inj.sub(grp(n.lines_t.p0, L.bus0), fill_value=0.0).sub(grp(n.lines_t.p1, L.bus1), fill_value=0.0)
    return float(inj.abs().max().max())


def combine(out, tol):
    """JOINT_HEADROOM_RESOURCE_NETWORK.csv after both LPs; acceptance 0 <= H_network <= H_resource + tol"""
    r = {k: json.loads((out / f'{STAGE[k]}_RESULT.json').read_text()) for k in STAGE}
    rows = [dict(stage=r[k]['stage'], status=r[k]['status'], termination=r[k]['termination'],
                 lambda_facility_MW=r[k].get('lambda_facility_MW'), lambda_IT_MW=r[k].get('lambda_IT_MW'),
                 existing_shed_MWh_B0=r[k].get('existing_shed_MWh_B0'), existing_shed_MWh_BL=r[k].get('existing_shed_MWh_BL'),
                 reserve_min_slack_MW=r[k].get('reserve_min_slack_MW'), balance_residual_max_abs_MW=r[k].get('balance_residual_max_abs_MW'))
            for k in ('R', 'N')]
    hr, hn = rows[0]['lambda_facility_MW'], rows[1]['lambda_facility_MW']
    ok = hr is not None and hn is not None and 0 <= hn <= hr + tol
    for x in rows:
        x['H_network_le_H_resource_plus_tol'] = ok
        x['label'] = 'joint connection capability of the given AIDC distribution under the stated stress / reserve conditions on the synthetic network (NOT real ERCOT headroom)'
    pd.DataFrame(rows).to_csv(out / 'JOINT_HEADROOM_RESOURCE_NETWORK.csv', index=False, lineterminator='\n')
    return ok


# ------------------------------------------------------------------------------------------------ actions
def dry(base):
    import post_v16_headroom as H
    cfg = H.load_cfg(CFG)
    OUT.mkdir(parents=True, exist_ok=True)
    wins = H.windows(cfg)
    vq = H.stress_vintage_qa(cfg, wins)
    rep = dict(solver_calls=0, base=str(base), base_sha256=sha(base), gate={k: G.check(CFG, STAGE[k], base, LOG) for k in STAGE})
    import pypsa
    nb = pypsa.Network(str(base))
    rows = [r for w in wins for r in w['rows']]
    L, _ = H.hourly_bus_load(rows, shares_csv())
    grp = pd.Series(rows).groupby(np.array(rows) // 3).size()
    k3 = sorted(grp.index[grp == 3])                      # complete 3 h steps only (windows start mid-step)
    ps = nb.loads_t.p_set.T.groupby(nb.loads.bus).sum().T.iloc[k3]
    L3 = L.groupby(np.array(rows) // 3).mean().loc[k3].reindex(columns=ps.columns)
    vq['load_vs_v16_3h_p_set_max_abs_MW'] = float(np.abs(L3.values - ps.values).max())
    vq['load_vs_v16_3h_compared_complete_steps'] = len(k3)
    vq['v16_network'] = dict(buses=len(nb.buses), lines=len(nb.lines), sha256=rep['base_sha256'])
    (OUT / 'STRESS_SOURCE_VINTAGE_QA.json').write_text(json.dumps(vq, indent=1, default=str))
    for mode in ('R', 'N'):
        t = time.time()
        n, info, _ = build(mode, base)
        rep[mode] = dict(info['structure'], headroom=info['headroom'], build_seconds=round(time.time() - t, 1),
                         reserve=info['reserve'], line_limits=info['line_limits'])
    led, lam = H.poi_ledger()
    led.to_csv(OUT / 'POI_ELIGIBILITY_LEDGER_A0_PREVIEW.csv', index=False, lineterminator='\n')
    lam.to_csv(OUT / 'POI_LAMBDA_A0_PREVIEW.csv', index=False, lineterminator='\n')
    rep['poi_lambda_preview'] = lam.to_dict(orient='records')
    (OUT / 'A1_DRY_CHECK.json').write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: (v if k not in ('R', 'N') else {kk: vv for kk, vv in v.items() if kk not in ('variables', 'constraints')})
                      for k, v in rep.items() if k != 'poi_lambda_preview'}, indent=1, default=str))


def lp(mode, base, threads):
    g = G.check(CFG, STAGE[mode], base, LOG)            # BEFORE anything is read or built
    G.deny(g)
    n, info, cfg = build(mode, base)
    info.update(reserve_MW=cfg['reserve']['requirement_MW'], tau_h=cfg['reserve']['tau_h'])
    opts = dict(cfg['solver_options'], Threads=int(threads))
    t = time.time()
    try:
        st, term = n.optimize.solve_model(solver_name=cfg['solver'], solver_options=opts)
    except Exception as e:                                # logged, never retried
        log_call(STAGE[mode], 'error', repr(e)[:160], time.time() - t)
        raise
    sec = time.time() - t
    log_call(STAGE[mode], str(st), str(term), sec)
    tag = STAGE[mode]
    summ = dict(stage=tag, status=str(st), termination=str(term), seconds=round(sec, 1), solver_options=opts, gate=g,
                structure={k: v for k, v in info['structure'].items() if k not in ('variables', 'constraints')}, headroom=info['headroom'])
    if str(term) == 'optimal':
        summ.update(write_outputs(solution_view(n, info), OUT, tag))
        summ['balance_residual_max_abs_MW'] = balance_residual(n)
    (OUT / f'{tag}_RESULT.json').write_text(json.dumps(summ, indent=1, default=str))
    print(json.dumps(summ, indent=1, default=str))
    if not (str(st) == 'ok' and str(term) == 'optimal'):
        raise SystemExit(f'{tag}: {st} {term} -> BLOCKED (no retry)')
    if mode == 'N':
        ok = combine(OUT, float(cfg['acceptance']['h_network_le_h_resource_tol_MW']))
        print('H_network <= H_resource + tol:', ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--gate', action='store_true')
    ap.add_argument('--lp', choices=['R', 'N'])
    ap.add_argument('--base', default=str(BP.BASE_TAMU_V16))
    ap.add_argument('--threads', type=int, default=int(os.environ.get('THREADS', 16)))
    a = ap.parse_args()
    if a.gate:
        print(json.dumps(G.check(CFG, STAGE[a.lp or 'R'], a.base, LOG), indent=1))
    elif a.dry:
        dry(a.base)
    elif a.lp:
        lp(a.lp, a.base, a.threads)


if __name__ == '__main__':
    main()
