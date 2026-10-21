#!/usr/bin/env python3
"""BYOP ERCOT Rearchitecture (work package v1.0, 2026-10-20): TAMU electrical backbone + POI deliverability layer +
S2 speed-first developer with an ex-ante joint grid offer, on top of the v2.4.0 static S0-S3 LP (continuous LP only).

Reuses v240_mech (cohort/PUE/task model, BYOP N/R equations, fractional COD, two-book ledgers, ERM-DC-01 B) and the
v250 TX-ERM aggregation; replaces only the parts the work package flags:
  world   WP-A  TAMU/BE 64-bus backbone (AC Lines, DC power flow), 2025 baseline build_2025_baseline_tamu.py
                (cross-zone lines share the ReEDS NARIS interface instead of PyPSA-USA's k x interface).
  POI     WP-B  one DC bus per representative POI site s (POI_REGISTER.csv), parent bus = nearest ERCOT TAMU
                substation -> busmap. Grid service at the POI has four separately audited layers:
                  1 equipment  EQ(s,p) = E0 x avail(cod0, p) [x proc] + sum_q U(s,q) x avail(cod_u, p)
                               U = continuous POI upgrade (Link capacity variable, no flow), lead + cost from register
                  2 upstream   the POI flow is a load on the parent bus of the KVL network (endogenous, joint for all
                               sites; no per-project headroom number that could be allocated twice)
                  3 adequacy   firm POI flow enters the TX ERM row with (1+ERM) (ERM-DC-01 B); conditional flow does not
                  4 procedure  new allocation (U, non-preapproved E0, PCLR) only after earliest_grid_COD (Batch Zero)
                firm flow <= EQ; firm + conditional <= EQ; conditional <= PCLR MW, zero at ex-ante trigger snapshots,
                where the load may be curtailed (budgeted hours, max consecutive duration) instead.
                Delay attribution (S1): one-at-a-time relaxations xPOI / xUP / xRA / xPROC and all-relaxed xALL.
  S2      WP-C  developer stage per site and supply mode, enumerated outside the LP:
                  GO_F  Grid-Only firm (the S1 offer)          GO_C  Grid-Only firm + PCLR conditional (curtailable)
                  GF    Grid-Connected Flexible (WLPUN/BYOG-like: import <= certified limit + own N/R supply)
                  IS    Islanded (zero import)
                The grid offer comes from the joint S1 grid-only LP (deliverable firm import per site-year, S1 parent
                bus LMP), never from an unlimited price-taker purchase. Each mode: lexicographic speed-first (max
                served IT year by year, earliest first) then min private cost; the mode with the faster trajectory,
                then lower cost, is chosen. Committed BYOP + import rights are fixed in the public S2 LP; a public
                solution that cannot deliver the planned service triggers a re-offer (bounded iterations, logged).
                Gas: evidence levels L0/L1/L2 with lateral lead (COD = max(tech lead, lateral lead)), lateral cost and
                daily MDQ (L0: verified value; L1: infrastructure proxy; L2: conservative) - never 0 / unbounded.
  grid    settings G-W weak (existing network, no corridor expansion) | G-K constrained (G-W + an equally sized
                competing queued large load at every POI parent bus) | G-U upgrade (G-K + corridor reinforcement with
                TPIT lead + committed PBRP 765-kV import paths at their ISD).
Run (L2, from pypsa-usa/workflow):
    python byop/model/rearch_mech.py --case-id X --out results/BYOP/rearch/X --setting G-U [--calibrate] ...
"""
from __future__ import annotations

import argparse, copy, json, logging, math, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import byop_paths as BP  # noqa: E402
import v240_mech as M  # noqa: E402
import v250_mech as V  # noqa: E402

w2, s1r = M.w2, M.s1r
logger = logging.getLogger('rearch')

BASE_TAMU = BP.RESULTS / 'baseline_2025_tamu/baseline_2025_tamu_prepared.nc'
POI_REG = BP.INPUTS / 'poi/POI_REGISTER.csv'
POI_REQ = BP.INPUTS / 'poi/POI_REQUESTS.csv'
GRID_PROJ = BP.INPUTS / 'poi/GRID_PROJECTS.csv'
BASE_ASSETS = BP.INPUTS / 'grid/COMMITTED_BASE_ASSETS.csv'   # D3: committed TPIT increments shared by all scenarios
SUBS = Path('resources/BYOP_ERCOT_TAMU/networks/texas/elec_s.nc')
GAS_FIRED = V.GAS_FIRED
MDQ_PROXY = {'L1': 250000.0, 'L2': 100000.0}       # MMBtu/d lateral sizing proxy when no verified MDQ (RESEARCH_ASSUMPTION)
GAS_L2 = dict(lead=3.0, cost=100.0)                # L2 unknown: conservative lateral lead (y) / cost (USD/kW)
UPGRADE_LIFE = 40
MODES = ['GO_F', 'GO_C', 'GF', 'IS']
GCFG = dict(regional_dc='off', regional_dc_scenario='mid', competing_voll=None, s0_calibrate=False, s0_cal_file=None, interrupt_cap=0.005, no_harm=True, base_assets='main', setting='G-U', relax=[], case='base', gas_case='base', pclr_hours=200.0, pclr_max_consec_h=12.0,
            s2_iter=3, competing=1.0, line_lead=None, offer_tol=1e-3, clusters='64s')
SITES: dict = {}
STATE = M.STATE

# ------------------------------------------------------------------------------------------------ Mainline v1.3
# --mainline: 8 Epoch TAMU buses as research AIDC (one aggregated POI per bus, D12), D11 inherited ramp as background,
# G-REAL (no competing queue, no regional_dc), v1.3 techs and yearly gas, approval-cohort COD (D1), stress snapshots in
# the firm LP (B7), one joint developer LP (D13), run gate (E1). Default off: v1.0 behaviour unchanged.
ML = dict(on=False, stress_days=3, stress_line_derate=1.0, gate=None)
ML_POI = BP.INPUTS / 'poi/GREAL_POI_ASSUMPTIONS.csv'
ML_E0 = BP.INPUTS / 'poi/GREAL_POI_E0_SCHEDULE.csv'
ML_RPOOL = BP.INPUTS / 'poi/GREAL_R_ASSET_POOL.csv'
ML_COH = BP.INPUTS / 'dc/MAINLINE_RESEARCH_COHORTS_TAMU64.csv'
ML_RAMP = BP.INPUTS / 'dc/MAINLINE_INHERITED_RAMP_2025.csv'
ML_POT = BP.INPUTS / 'grid/ERCOT_WIND_SOLAR_POTENTIAL.csv'
ML_TECH = BP.INPUTS / 'tech/MAINLINE_V13_TECH_DEFAULTS.csv'
ML_GASP = BP.INPUTS / 'tech/MAINLINE_V13_GAS_PRICES_2026_2031.csv'
ML_TECHS = ['RICE', 'SOFC_NG', 'OCGT_aero', 'WIND', 'PV', 'BESS']
ML_INPUTS = [ML_POI, ML_E0, ML_RPOOL, ML_COH, ML_RAMP, ML_POT, ML_TECH, ML_GASP]
GAS_CARRIERS = {'CCGT', 'OCGT', 'gas_steam', 'reuse_pub', 'byop_R'} | {f'byop_{c}' for c in GAS_FIRED}
RE_CAR = {'WIND': 'onwind', 'PV': 'solar'}


def configure_mainline(out):
    """WP-A: research AIDC = MAINLINE_RESEARCH_COHORTS (mid) on the 8 Epoch buses; the Epoch bus IS the parent bus
    (no re-siting); POI parameters from GREAL_POI_ASSUMPTIONS (case low/base/high) + E0 equipment rows"""
    n0 = pypsa.Network(str(BASE_TAMU))
    zones = sorted(b for b in n0.buses.index if n0.buses.carrier[b] == 'AC')
    M.BASE = BASE_TAMU
    M.ZONES = zones
    M.ZONE_STATE = {z: 'TX' for z in zones}
    M.LINE_LEADS = dict(V.LINE_LEADS_TPIT)
    w2.EXCLUDE_ZONES = []
    gp = pd.read_csv(ML_GASP)
    M.CFG.update(gas_by_year={int(r.year): float(r.gas_price_2025USD_per_MMBtu_HHV) for r in gp.itertuples()},
                 tech_v13=str(ML_TECH), firm_full_year=True)
    g0 = n0.generators[n0.generators.p_nom_extendable]
    for c, car in RE_CAR.items():          # D2.a: wind / PV life = verified PyPSA-USA candidate setting
        lt = g0.lifetime[g0.carrier == car]
        if len(lt):
            M.BYOP_LIFE[c] = float(lt.iloc[0])
    reg = pd.read_csv(ML_POI)
    e0 = pd.read_csv(ML_E0)
    k = GCFG['case']
    for r in reg.itertuples():
        assert r.bus in n0.buses.index, f'Epoch bus {r.bus} not in the TAMU network'
        lvl = r.gas_evidence_level
        mdq = float(r.gas_MDQ_MMBtu_d) if lvl == 'L0' else MDQ_PROXY.get(lvl, MDQ_PROXY['L2'])
        rows = [dict(MW=float(x.MW), cod=float(x.COD), pre=bool(x.preapproved), site=x.site) for x in e0[e0.bus == r.bus].itertuples()]
        SITES[r.site_id] = dict(
            site=r.site_id, name=r.site_name, bus=r.bus, substation=None, sub_dist_deg=0.0, parent_rule='EPOCH_TAMU64_BUS (D12)', lat=r.lat, lon=r.lon,
            E0=sum(x['MW'] for x in rows), cod0=min((x['cod'] for x in rows), default=None), preapproved=all(x['pre'] for x in rows) if rows else False,
            E0rows=rows, U_max=float(r.poi_upgrade_max_MW), U_lead=float(getattr(r, f'poi_upgrade_lead_y_{k}')),
            U_cost=float(getattr(r, f'poi_upgrade_cost_USD_kW_{k}')) * 1000, proc=float(getattr(r, f'earliest_grid_COD_{k}')),
            pclr=float(r.pclr_conditional_MW), pclr_off=float(r.pclr_conditional_COD_offset_y), gas_level=lvl, mdq=mdq,
            lat_lead=float(getattr(r, f"gas_lateral_lead_y_{GCFG['gas_case']}")), lat_cost=float(getattr(r, f"gas_lateral_cost_USD_kW_{GCFG['gas_case']}")) * 1000,
            onsite_re=float(r.onsite_renewable_cap_MW), profile='MAINLINE_RESEARCH_COHORT', confidence=r.confidence)
    coh = pd.read_csv(ML_COH)
    coh = coh[coh.scenario == 'mid'].copy()
    assert set(coh.region_id) <= set(SITES), 'research cohort bus without an aggregated POI'
    c2 = out / 'poi_cohorts.csv'
    coh[['cohort_id', 'scenario', 'request_year', 'st', 'region_id', 'IT_MW', 'quality']].to_csv(c2, index=False)
    s1r.COHORTS = c2
    M.DC_ZONES = list(SITES)
    pot = pd.read_csv(ML_POT)
    STATE['re_potential'] = {(r.bus, r.technology): float(r.remaining_new_MW_AC) for r in pot.itertuples()}
    return n0


def ml_gas_delta(n):
    """D2.b: one WSC gas price per year for every gas unit (existing fleet, public candidates, reuse, BYOP):
    mc_t = mc(GAS) + HR x (gas_y - GAS), HR = 3412.14 / efficiency (the baseline built mc = HR x GAS + VOM)"""
    g = n.generators
    sel = g.index[g.carrier.isin(GAS_CARRIERS) & (g.efficiency > 0.05)]
    if not len(sel) or not M.CFG.get('gas_by_year'):
        return
    per = n.snapshots.get_level_values(0)
    dp = np.array([M.gas_price(p) - M.GAS for p in per])
    hr = 3412.14 / g.efficiency[sel].values / 1000.0
    base = n.get_switchable_as_dense('Generator', 'marginal_cost')[sel].values
    mc = pd.DataFrame(base + np.outer(dp, hr), index=n.snapshots, columns=sel)
    keep = n.generators_t.marginal_cost.columns.difference(sel)
    n.generators_t.marginal_cost = pd.concat([n.generators_t.marginal_cost[keep], mc], axis=1)
    STATE['gas_repriced'] = dict(n=len(sel), by_year={int(p): M.gas_price(p) for p in M.periods()}, flat_reference=M.GAS)


def ml_stress_days(n):
    """B7: a few real stress days of the 2025 weather / load year (3-h snapshots), placed in every period's sample:
    (1) lowest West / Panhandle wind day among the 30 % highest-load days, (2) highest ERCOT net-load day
    (load - wind - solar), (3) highest winter (Dec-Feb) load day. Returns timestep labels."""
    ts = n.snapshots.get_level_values(-1) if isinstance(n.snapshots, pd.MultiIndex) else n.snapshots
    ts = pd.DatetimeIndex(ts)
    g = n.generators
    pm = n.generators_t.p_max_pu
    load = n.loads_t.p_set.sum(axis=1).values
    def cap_profile(car, zones=None):
        sel = [x for x in g.index[(g.carrier == car) & ~g.p_nom_extendable] if x in pm]
        if zones:
            sel = [x for x in sel if str(g.bus[x])[:3] in zones]
        if not sel:
            return np.zeros(len(ts))
        return (pm[sel].values * g.p_nom[sel].values).sum(axis=1)
    wind_w = cap_profile('onwind', ('p60', 'p61', 'p62'))
    net = load - cap_profile('onwind') - cap_profile('solar')
    day = ts.normalize()
    df = pd.DataFrame(dict(day=day, load=load, wind_w=wind_w, net=net)).groupby('day').agg(load=('load', 'mean'), wind_w=('wind_w', 'mean'), net=('net', 'max'))
    hi = df[df.load >= df.load.quantile(0.7)]
    picks = [('LOW_WEST_WIND_HIGH_LOAD', hi.wind_w.idxmin()), ('MAX_NET_LOAD', df.net.idxmax())]
    win = df[df.index.month.isin([12, 1, 2])]
    if len(win):
        picks.append(('WINTER_PEAK', win.load.idxmax()))
    out, seen = [], set()
    for kind, d_ in picks[:ML['stress_days']]:
        if d_ in seen:
            continue
        seen.add(d_)
        out.append(dict(kind=kind, day=str(d_.date()), mean_load_MW=float(df.load[d_]), mean_west_wind_MW=float(df.wind_w[d_]),
                        max_net_load_MW=float(df.net[d_])))
    STATE['stress_days'] = out
    return [t for t in ts if t.normalize() in seen]


def ml_base_build(config):
    """v240 base_build with the B7 stress days added to the week sample (each stress snapshot represents itself, 3 h;
    the sampled weeks carry the rest of the year so the weights still sum to 8760 h)"""
    n = w2.base_network(config)
    stress = set(ml_stress_days(n))
    full = len(n.snapshots); sw0 = n.snapshot_weightings.copy()
    k = M.CFG['sample_weeks']
    base = [i for i in range(full) if (i // 56) % k == 0 and (i // 56) < full // 56] if k else list(range(full))
    ts = pd.DatetimeIndex(n.snapshots.get_level_values(-1) if isinstance(n.snapshots, pd.MultiIndex) else n.snapshots)
    sidx = [i for i in range(full) if ts[i] in stress]
    extra = [i for i in sidx if i not in set(base)]
    keep = sorted(set(base) | set(extra))
    n.set_snapshots(n.snapshots[keep])
    hours = float(sw0.generators.sum())
    w = pd.Series(0.0, index=n.snapshots)
    ex = set(extra)
    for j, i in enumerate(keep):
        w.iloc[j] = M.SNAP_HOURS if i in ex else (hours - M.SNAP_HOURS * len(ex)) / len(base) / 1.0
    n.snapshot_weightings = pd.DataFrame({c: w.values for c in sw0.columns}, index=n.snapshots)
    STATE['stress_ts'] = {ts[i] for i in sidx}
    STATE['stress_sample'] = dict(days=STATE.get('stress_days'), snapshots=len(sidx), added_outside_sample=len(extra),
                                  weight_total_h=float(w.sum()))
    return n


def stress_mask(snapshots):
    """True at the B7 stress snapshots of every period"""
    st = STATE.get('stress_ts') or set()
    ts = snapshots.get_level_values(-1) if isinstance(snapshots, pd.MultiIndex) else snapshots
    return np.array([pd.Timestamp(t) in st for t in ts])


def add_inherited_ramp(n):
    """D11: late-2025 Epoch ramp (energized by end-2025) as background facility load in EVERY scenario (S0 too):
    flat cum. IT x PUE(period); own shed generator (carrier load_shed: no-harm protected, reported separately)"""
    r = pd.read_csv(ML_RAMP)
    per = n.snapshots.get_level_values(0)
    rows = []
    for x in r.itertuples():
        prof = np.array([x.inherited_ramp_IT_MW * float(w2.PUE[(w2.PUE.st == 'TX') & (w2.PUE.year == min(p, 2035))].pue.iloc[0]) for p in per])
        n.add('Load', f'{x.bus} inherited_ramp', bus=x.bus, carrier='AC', p_set=pd.Series(prof, index=n.snapshots))
        n.add('Generator', f'{x.bus} inherited_ramp_unserved', bus=x.bus, carrier='load_shed', p_nom=float(prof.max()) + 1.0,
              marginal_cost=M.SHED_COST, build_year=2025, lifetime=100)
        rows.append(dict(bus=x.bus, IT_MW=x.inherited_ramp_IT_MW, facility_MW_peak=float(prof.max())))
    STATE['inherited_ramp'] = dict(file=str(ML_RAMP), sha256=M.sha(ML_RAMP), buses=rows, IT_MW=float(r.inherited_ramp_IT_MW.sum()))


def ml_public_potential(n):
    """WP-C: public onwind / solar new-build per bus capped by the remaining ReEDS2 potential (shared with BYOP in
    ml_space); the aggregate over all build periods is enforced there"""
    g = n.generators
    for car in RE_CAR.values():
        for name in g.index[(g.carrier == car) & g.p_nom_extendable]:
            cap = STATE['re_potential'].get((g.bus[name], car))
            if cap is not None:
                n.generators.loc[name, 'p_nom_max'] = min(float(g.p_nom_max[name]), cap)


def ml_space(n, m):
    """QA-SPACE: (a) on-site BYOP wind / PV per site <= adjacent-land proxy; (b) public new-build + BYOP of the same
    technology at a bus (all build periods) <= remaining ReEDS2 potential (no double use, no unlimited site RE)"""
    if 'Generator-p_nom' not in m.variables:
        return
    pn = m['Generator-p_nom']
    g = n.generators
    ext = set(g.index[g.p_nom_extendable])
    for s, d in SITES.items():
        for c, car in RE_CAR.items():
            b = [x for x in g.index[(g.carrier == f'byop_{c}') & (g.bus == f'DC_{s}')] if x in ext]
            if b:
                m.add_constraints(pn.sel(name=b).sum('name') <= d['onsite_re'], name=f'ML-onsite_{c}_{s}')
    for (bus, car), cap in STATE.get('re_potential', {}).items():
        c = {v_: k_ for k_, v_ in RE_CAR.items()}[car]
        own = [x for s, d in SITES.items() if d['bus'] == bus for x in g.index[(g.carrier == f'byop_{c}') & (g.bus == f'DC_{s}')]]
        terms = [x for x in g.index[(g.carrier == car) & (g.bus == bus)] if x in ext] + [x for x in own if x in ext]
        fixed = float(g.p_nom[[x for x in own if x not in ext]].sum())     # S2 public LP: committed BYOP uses the cap first
        if terms:
            m.add_constraints(pn.sel(name=terms).sum('name') <= max(0.0, cap - fixed), name=f'ML-potential_{car}_{bus}')


def add_byop_cohorts(n, s, site, dmax_fac, byop, byop_fixed, actor):
    """D1 / D2: BYOP capacity variables by approval year q (COD(q) = q + lead; gas: max(tech lead, lateral lead) in
    parallel), normal dispatch at the real availability (gas: 1.0 after COD; wind / PV: bus profile), failure-case
    firm credit (1/r, full years only) at the B7 stress snapshots; BESS = StorageUnit with SOC (4 h, eta_rt 0.85)"""
    dc = f'DC_{s}'
    per = n.snapshots.get_level_values(0)
    smask = stress_mask(n.snapshots)
    for car in byop:
        bp = M.byop_params(car, actor)
        lead = bp['lead']
        lat_ann = 0.0
        if car in GAS_FIRED:
            lead = max(lead, site['lat_lead'])
            lat_ann = site['lat_cost'] * M.crf(bp['rate'], M.BYOP_LIFE[car])
        if f'byop_{car}' not in n.carriers.index:
            n.add('Carrier', f'byop_{car}', co2_emissions=0.0)
        for q, cod, b0 in M.approval_cohorts(lead):
            name = f'{dc} BYOP {car} q{q}'
            av = np.array([M.avail_frac(b0, cod, p) for p in per])
            fm = np.array([M.firm_frac(b0, cod, p) for p in per])
            cc = (bp['annual'] + lat_ann) * M.tv_factor(b0, M.BYOP_LIFE[car], 'byop', actor)
            fixed = byop_fixed.get((s, car, q), 0.0) if byop_fixed is not None else None
            STATE.setdefault('approval_year', {})[name] = q
            if car == 'BESS':
                eta = math.sqrt(bp['eta_rt'])
                kw = dict(bus=dc, carrier='byop_BESS', capital_cost=cc, max_hours=bp['max_hours'], efficiency_store=eta,
                          efficiency_dispatch=eta, cyclic_state_of_charge=True, cyclic_state_of_charge_per_period=True,
                          build_year=b0, lifetime=M.BYOP_LIFE[car], marginal_cost=0.0)
                kw.update(dict(p_nom=fixed, p_nom_extendable=False) if fixed is not None else dict(p_nom_extendable=True, p_nom_max=dmax_fac * 2.0))
                n.add('StorageUnit', name, **kw)
                n.storage_units_t.p_max_pu[name] = av
                n.storage_units_t.p_min_pu[name] = -av
            else:
                if car in RE_CAR:
                    prof = STATE['re_profile'].get((site['bus'], RE_CAR[car]))
                    assert prof is not None, f'no {RE_CAR[car]} availability profile at {site["bus"]}'
                    ppu = av * np.asarray(prof)
                    pmax = site['onsite_re']
                else:
                    ppu = np.where(smask, fm / bp['r'], av)       # failure-case firm credit only at stress snapshots
                    pmax = dmax_fac * bp['r'] * 2.0
                kw = dict(bus=dc, carrier=f'byop_{car}', capital_cost=cc, marginal_cost=bp['mc'], build_year=b0,
                          lifetime=M.BYOP_LIFE[car], efficiency=(3412.14 / bp['hr']) if bp.get('hr') else 1.0)
                kw.update(dict(p_nom=fixed, p_nom_extendable=False) if fixed is not None else dict(p_nom_extendable=True, p_nom_max=pmax))
                n.add('Generator', name, **kw)
                n.generators_t.p_max_pu[name] = ppu
            STATE.setdefault('byop_cod', {})[name] = dict(cod=cod, build=b0, approval_year=q, r=bp['r'], carrier=car, zone=s,
                                                          lateral_USD_per_MW_yr=lat_ann, lead_effective=lead, evidence=bp.get('evidence'))


# ------------------------------------------------------------------------------------------------ world setup
def nearest_parent(lat, lon, n0):
    """nearest ERCOT TAMU substation (elec_s.nc) mapped through busmap_s_<clusters>; fallback nearest cluster bus"""
    bm = Path(f"resources/BYOP_ERCOT_TAMU/busmaps/texas/busmap_s_{GCFG['clusters']}.csv")
    if SUBS.exists() and bm.exists():
        sb = pypsa.Network(str(SUBS)).buses
        sb.index = sb.index.astype(str)
        busmap = pd.read_csv(bm, index_col=0).iloc[:, 0]
        busmap.index = busmap.index.astype(str)
        sb['cluster'] = sb.index.map(busmap)
        sb = sb[sb.cluster.isin(n0.buses.index)]
        i = ((sb.x - lon) ** 2 + (sb.y - lat) ** 2).idxmin()
        return sb.cluster[i], i, float(np.hypot(sb.x[i] - lon, sb.y[i] - lat)), 'nearest_ERCOT_TAMU_substation'
    b = n0.buses[n0.buses.carrier == 'AC']
    i = ((b.x - lon) ** 2 + (b.y - lat) ** 2).idxmin()
    return i, None, float(np.hypot(b.x[i] - lon, b.y[i] - lat)), 'nearest_cluster_bus_FALLBACK'


def configure(out):
    n0 = pypsa.Network(str(BASE_TAMU))
    zones = sorted(b for b in n0.buses.index if n0.buses.carrier[b] == 'AC')
    M.BASE = BASE_TAMU
    M.ZONES = zones
    M.ZONE_STATE = {z: 'TX' for z in zones}
    M.LINE_LEADS = dict(V.LINE_LEADS_TPIT)
    w2.EXCLUDE_ZONES = []
    reg = pd.read_csv(POI_REG)
    req = pd.read_csv(POI_REQ)
    k = GCFG['case']
    rows = []
    for r in reg.itertuples():
        bus, sub, dist, rule = nearest_parent(r.lat, r.lon, n0)
        lvl = r.gas_evidence_level
        mdq = float(r.gas_MDQ_MMBtu_d) if lvl == 'L0' else MDQ_PROXY.get(lvl, MDQ_PROXY['L2'])
        lat_lead = GAS_L2['lead'] if lvl == 'L2' else float(getattr(r, f"gas_lateral_lead_y_{GCFG['gas_case']}"))
        lat_cost = GAS_L2['cost'] if lvl == 'L2' else float(getattr(r, f"gas_lateral_cost_USD_kW_{GCFG['gas_case']}"))
        SITES[r.site_id] = dict(
            site=r.site_id, name=r.site_name, bus=bus, substation=sub, sub_dist_deg=dist, parent_rule=rule, lat=r.lat, lon=r.lon,
            E0=float(r.import_equipment_limit_MW), cod0=float(r.import_equipment_COD) if r.import_equipment_COD == r.import_equipment_COD else None,
            preapproved=bool(r.import_equipment_preapproved), U_max=float(r.poi_upgrade_max_MW),
            U_lead=float(getattr(r, f'poi_upgrade_lead_y_{k}')), U_cost=float(getattr(r, f'poi_upgrade_cost_USD_kW_{k}')) * 1000,
            proc=float(getattr(r, f'earliest_grid_COD_{k}')), pclr=float(r.pclr_conditional_MW),
            pclr_off=float(r.pclr_conditional_COD_offset_y), gas_level=lvl, mdq=mdq, lat_lead=lat_lead, lat_cost=lat_cost * 1000,
            profile=r.request_profile, confidence=r.confidence)
        for q in req[req.request_profile == r.request_profile].itertuples():
            rows.append(dict(cohort_id=f'{r.site_id}_{q.request_year}', scenario='mid', request_year=int(q.request_year),
                             st='TX', region_id=r.site_id, IT_MW=float(q.IT_MW), quality='STUDY_REQUEST_STYLIZED'))
    relax = set(GCFG['relax'])
    for s in SITES.values():
        if 'PROC' in relax:
            s['proc'] = M.CFG['decision_year']
    coh = out / 'poi_cohorts.csv'
    pd.DataFrame(rows).to_csv(coh, index=False)
    s1r.COHORTS = coh
    M.DC_ZONES = list(SITES)
    return n0


def eq_terms(s, p):
    """(fixed equipment MW available to the study request in period p) and [(upgrade link, coefficient)]"""
    d = SITES[s]
    relax = set(GCFG['relax'])
    if 'POI' in relax:
        return float('inf'), []
    fixed = 0.0
    if d.get('E0rows') is not None:        # mainline: dated equipment rows of the aggregated POI (GREAL_POI_E0_SCHEDULE)
        for x in d['E0rows']:
            cod = x['cod'] if x['pre'] else max(x['cod'], d['proc'])
            bp = M.first_period(cod)
            fixed += x['MW'] * M.firm_frac(bp, cod, p) if bp is not None else 0.0
    elif d['E0'] > 0 and d['cod0'] is not None:
        cod = d['cod0'] if d['preapproved'] else max(d['cod0'], d['proc'])
        bp = M.first_period(cod)
        fixed = d['E0'] * M.avail_frac(bp, cod, p) if bp is not None else 0.0
    ups = [(nm, M.firm_frac(q, cod, p)) for nm, q, cod in STATE.get('poi_up', {}).get(s, []) if q <= p]
    return fixed, [(nm, c) for nm, c in ups if c > 0]


def pclr_cap(s, p):
    d = SITES[s]
    cod = d['proc'] + d['pclr_off']
    bp = M.first_period(cod)
    return d['pclr'] * M.avail_frac(bp, cod, p) if bp is not None else 0.0


# ------------------------------------------------------------------------------------------------ network hooks
def add_line_expansion_tamu(n):
    """G-U: continuous controllable reinforcement increments on every TAMU corridor (Link pair per period, symmetric,
    cap = 100 % of the existing transfer rating = LINE-01 bound), lead from TPIT (D250-06), cost from the line's
    PyPSA-USA annuity per MW. G-W / G-K: none. KVL holds for the existing lines; increments are controllable
    (approximation, labelled)."""
    if GCFG['setting'] not in ('G-U', 'G-REAL') or not M.CFG['line_exp']:
        M.STATE['corridors'] = []
        return []
    lead = GCFG['line_lead'] if GCFG['line_lead'] is not None else M.LINE_LEADS[M.CFG['public_case']]
    p0 = M.first_period(M.CFG['decision_year'] + lead)
    L, corr = [], []
    for name, l in n.lines.iterrows():
        cap = float(l.s_nom) * float(l.s_max_pu)
        base = f'L{name}'
        cc = float(l.capital_cost) / max(float(l.s_max_pu), 1e-6)     # per MW of transfer
        for p in M.periods():
            if p0 is None or p < p0:
                continue
            for suf, b0, b1, c_ in (('fwd', l.bus0, l.bus1, cc), ('rev', l.bus1, l.bus0, 0.0)):
                L.append(dict(name=f'{base}_exp{p}_{suf}', bus0=b0, bus1=b1, carrier='AC_exp', p_nom=0.0, p_nom_extendable=True,
                              p_nom_max=cap, capital_cost=c_, efficiency=1.0, build_year=p, lifetime=60, length=float(l.length)))
        corr.append(dict(corridor=base, cap_MW=cap, capital_cost_per_MW_yr=cc, first_period=p0, bus0=l.bus0, bus1=l.bus1,
                         existing_MW=cap, lead=lead))
    if L:
        x = pd.DataFrame(L).set_index('name')
        n.add('Link', x.index, **{c: x[c].values for c in x.columns})
    if 'AC_exp' not in n.carriers.index:
        n.add('Carrier', 'AC_exp', co2_emissions=0.0)
    M.STATE['corridors'] = corr
    return corr


def tech_ra_relaxed():
    t = _tech_orig()
    if 'RA' in set(GCFG['relax']):
        u = t.boundary.isin(['UTILITY', 'UTILITY_AND_DC_BTM'])
        for c in ['lead_years_low', 'lead_years_base', 'lead_years_high']:
            t.loc[u, c] = 0.0
    return t


_tech_orig = M.tech


def add_base_assets(n):
    """D3 (researcher 2026-10-20): committed TPIT transmission (COMMITTED_BASE_ASSETS.csv, built from the TPIT evidence
    ledger) as common baseline assets of EVERY setting and scenario: fixed controllable Link pair at the interface level,
    partial first-year availability from the ISD. 'main' = MAIN_COMMITTED only; 'sens' = + SENSITIVITY_PLANNED; 'none'."""
    mode = GCFG.get('base_assets', 'main')
    if mode == 'none' or not BASE_ASSETS.exists():
        STATE['base_assets'] = []
        return []
    a = pd.read_csv(BASE_ASSETS)
    a = a[a.case.isin(['MAIN'] if mode == 'main' else ['MAIN', 'SENSITIVITY'])]
    if 'AC_base_committed' not in n.carriers.index:
        n.add('Carrier', 'AC_base_committed', co2_emissions=0.0)
    out = []
    for r in a.itertuples():
        if r.bus0 not in n.buses.index or r.bus1 not in n.buses.index or not r.MW == r.MW:
            out.append(dict(asset=r.asset_id, status='SKIPPED_NOT_MAPPED_OR_NO_MW'))
            continue
        bp = M.first_period(float(r.ISD))
        if bp is None:
            out.append(dict(asset=r.asset_id, status='OUTSIDE_WINDOW'))
            continue
        avail = pd.Series(0.0, index=n.snapshots)
        for q in M.periods():
            avail.loc[q] = M.avail_frac(bp, float(r.ISD), q)
        for suf, x0, x1 in (('fwd', r.bus0, r.bus1), ('rev', r.bus1, r.bus0)):
            nm = f'{r.asset_id}_{suf}'
            n.add('Link', nm, bus0=x0, bus1=x1, carrier='AC_base_committed', p_nom=float(r.MW), p_nom_extendable=False,
                  build_year=bp, lifetime=60, efficiency=1.0, capital_cost=0.0)
            n.links_t.p_max_pu[nm] = avail.values
        out.append(dict(asset=r.asset_id, case=r.case, bus0=r.bus0, bus1=r.bus1, ISD=float(r.ISD), MW=float(r.MW), build_period=bp,
                        status='COMMON_BASELINE_ASSET', tpit=r.tpit_project_ids))
    STATE['base_assets'] = out
    return out


# D3 3.5 minimum-uplift rule: shedding is made prohibitive (1e8 USD/MWh) and the uplift far dearer than any dispatch saving
# (1e7 USD/MW-yr >> price spread x 8760 h), so the LP removes background shedding with the least uplift MW and never
# buys line capacity for economics (a first try at 2e4 USD/MW-yr bought 11 GW, mostly congestion relief - rejected)
S0CAL_COST = 1.0e7
S0CAL_SHED = 1.0e8


def add_s0_calibration(n, scen):
    """D3 3.5 targeted S0 calibration (researcher 2026-10-20), after the committed TPIT assets:
    calibrate  (S0 only, --s0-calibrate): one symmetric extendable uplift Link pair per TAMU line, built 2026, priced at
               S0CAL_COST so it is bought only where it removes > 2 MWh of background shedding per MW and year
    apply      (--s0-cal-file CSV): the resulting uplifts as fixed, cost-free common baseline assets of EVERY scenario
               (like the 2025 deliverability calibration: evidence level B, not an investment)"""
    if 'AC_s0cal' not in n.carriers.index:
        n.add('Carrier', 'AC_s0cal', co2_emissions=0.0)
    p0 = M.periods()[0]
    if GCFG.get('s0_calibrate') and scen == 'S0':
        L = []
        for name, l in n.lines.iterrows():
            for suf, b0, b1, cc in (('fwd', l.bus0, l.bus1, S0CAL_COST), ('rev', l.bus1, l.bus0, 0.0)):
                L.append(dict(name=f'S0CAL_{name}_{suf}', bus0=b0, bus1=b1, carrier='AC_s0cal', p_nom=0.0, p_nom_extendable=True,
                              capital_cost=cc, efficiency=1.0, build_year=p0, lifetime=60))
        x = pd.DataFrame(L).set_index('name')
        n.add('Link', x.index, **{c: x[c].values for c in x.columns})
        STATE['s0cal_pairs'] = [f'S0CAL_{name}' for name in n.lines.index]
        n.generators.loc[n.generators.carrier == 'load_shed', 'marginal_cost'] = S0CAL_SHED
    elif GCFG.get('s0_cal_file'):
        c = pd.read_csv(GCFG['s0_cal_file'])
        for r in c[c.added_MW > 0.5].itertuples():
            for suf, b0, b1 in (('fwd', r.bus0, r.bus1), ('rev', r.bus1, r.bus0)):
                n.add('Link', f'S0CAL_{r.line}_{suf}', bus0=b0, bus1=b1, carrier='AC_s0cal', p_nom=float(r.added_MW),
                      p_nom_extendable=False, efficiency=1.0, build_year=p0, lifetime=60, capital_cost=0.0)
        STATE['s0cal_applied'] = dict(file=str(GCFG['s0_cal_file']), sha256=M.sha(GCFG['s0_cal_file']), n=int((c.added_MW > 0.5).sum()),
                                      MW=float(c.added_MW.sum()))


def add_grid_projects(n):
    """G-U: committed PBRP 765-kV import paths (fixed Link pair, partial first-year availability from the ISD)"""
    if GCFG['setting'] not in ('G-U', 'G-REAL'):
        return []
    gp = pd.read_csv(GRID_PROJ)
    b = n.buses[n.buses.index.isin(M.ZONES)]
    near = lambda lo, la: ((b.x - lo) ** 2 + (b.y - la) ** 2).idxmin()
    out = []
    if 'AC_committed' not in n.carriers.index:
        n.add('Carrier', 'AC_committed', co2_emissions=0.0)
    for r in gp.itertuples():
        b0, b1 = near(r.from_lon, r.from_lat), near(r.to_lon, r.to_lat)
        isd = float(getattr(r, f"ISD_{GCFG['case']}")); cap = float(getattr(r, f"capacity_MW_{GCFG['case']}"))
        bp = M.first_period(isd)
        if bp is None or b0 == b1:
            out.append(dict(project=r.project_id, bus0=b0, bus1=b1, ISD=isd, MW=cap, status='OUTSIDE_WINDOW_OR_SAME_BUS'))
            continue
        avail = pd.Series(0.0, index=n.snapshots)
        for q in M.periods():
            avail.loc[q] = M.avail_frac(bp, isd, q)
        for suf, x0, x1 in (('fwd', b0, b1), ('rev', b1, b0)):
            nm = f'{r.project_id}_{suf}'
            n.add('Link', nm, bus0=x0, bus1=x1, carrier='AC_committed', p_nom=cap, p_nom_extendable=False, build_year=bp,
                  lifetime=60, efficiency=1.0, capital_cost=0.0)
            n.links_t.p_max_pu[nm] = avail.values
        out.append(dict(project=r.project_id, name=r.name, bus0=b0, bus1=b1, ISD=isd, MW=cap, build_period=bp,
                        status='COMMITTED_IN_MODEL', cost_treatment='sunk/committed in every scenario (excluded from S-differences)'))
    STATE['grid_projects'] = out
    return out


def add_competing_load(n):
    """G-K / G-U: an equally sized competing queued large load (flat, facility MW = cum. request IT x PUE x share) at
    every POI parent bus, present in ALL scenarios (it is background, not study AIDC). STYLIZED stress."""
    if GCFG['setting'] not in ('G-K', 'G-U') or not GCFG['competing']:
        return
    req = pd.read_csv(POI_REQ)
    pue_t = w2.PUE
    per = n.snapshots.get_level_values(0)
    for s, d in SITES.items():
        r = req[req.request_profile == d['profile']]
        prof = np.array([float(r[r.request_year <= p].IT_MW.sum()) * float(pue_t[(pue_t.st == 'TX') & (pue_t.year == min(p, 2035))].pue.iloc[0])
                         for p in per]) * GCFG['competing']
        n.add('Load', f'{s} competing_queue', bus=d['bus'], carrier='AC', p_set=pd.Series(prof, index=n.snapshots))
        # RA-D2f (revised 2026-10-21): the competing queue has its own curtailment variable, REPORTED separately from
        # background shedding, but priced like background shedding (SHED_COST) and protected per generator by the
        # no-harm bound: G-K / G-U must stay a physical stress (a first version at 600 USD/MWh curtailed 2.6 TWh in
        # S0 because curtailing was cheaper than supplying it - rejected). Carrier load_shed keeps the v240 ERM correction.
        n.add('Generator', f'{s} competing_unserved', bus=d['bus'], carrier='load_shed', p_nom=float(prof.max()) + 1.0,
              marginal_cost=GCFG['competing_voll'] or M.SHED_COST, build_year=2025, lifetime=100)
    STATE['competing'] = dict(share=GCFG['competing'], voll_USD_MWh=GCFG['competing_voll'] or M.SHED_COST,
                              rule='equal to the study request at each POI parent bus (STYLIZED); own curtailment at the new-load lost value')


REGIONAL_COHORTS = Path(__file__).resolve().parents[1] / 'inputs/dc/ercot_cohorts_2026_2035_tamu64.csv'


def add_regional_dc(n):
    """Opt-in (--regional-dc, default off): the approved ERCOT DC totals (DATA-01/03, low/mid/high) split over the 21 TAMU
    64s buses by Epoch AI geography (RA-DC-SPATIAL-03: totals = approved scenarios every year; Epoch sites served in date order,
    residual by Epoch increment share; ercot_cohorts_2026_2035_tamu64.csv) as flat BACKGROUND
    facility load (cum. IT MW of cohorts with request_year <= period x state PUE) in ALL scenarios. Not a study request:
    no POI equipment limit, no BYOP choice (aggregate-POI equipment assumption pending a researcher decision); added on
    top of the 3 representative POI requests (overlap rule pending). Own curtailment generator priced at SHED_COST,
    carrier load_shed, protected per generator by no-harm, reported separately."""
    if GCFG['regional_dc'] == 'off':
        return
    c = pd.read_csv(REGIONAL_COHORTS)
    c = c[(c.spatial_basis == GCFG['regional_dc']) & (c.scenario == GCFG['regional_dc_scenario'])]
    assert len(c), f"no regional cohorts for {GCFG['regional_dc']} / {GCFG['regional_dc_scenario']}"
    miss = set(c.region_id) - set(n.buses.index)
    assert not miss, f'regional cohort buses not in network: {sorted(miss)}'
    pue_t = w2.PUE
    per = n.snapshots.get_level_values(0)
    pue = {p: float(pue_t[(pue_t.st == 'TX') & (pue_t.year == min(p, 2035))].pue.iloc[0]) for p in sorted(set(per))}
    rows = []
    for b, g in c.groupby('region_id'):
        prof = np.array([float(g[g.request_year <= p].IT_MW.sum()) * pue[p] for p in per])
        if prof.max() <= 0:
            continue
        n.add('Load', f'{b} regional_dc', bus=b, carrier='AC', p_set=pd.Series(prof, index=n.snapshots))
        n.add('Generator', f'{b} regional_dc_unserved', bus=b, carrier='load_shed', p_nom=float(prof.max()) + 1.0,
              marginal_cost=M.SHED_COST, build_year=2025, lifetime=100)
        rows.append(dict(bus=b, zone=g.parent_zone.iloc[0], IT_MW_final=float(g.IT_MW.sum()), facility_MW_peak=float(prof.max())))
    STATE['regional_dc'] = dict(basis=GCFG['regional_dc'], scenario=GCFG['regional_dc_scenario'], file=str(REGIONAL_COHORTS),
                                sha256=M.sha(REGIONAL_COHORTS), buses=rows, IT_MW_total=float(c.IT_MW.sum()),
                                rule='background facility load, flat, cum. cohorts x PUE; not a study request (STYLIZED)')


def relax_upstream(n):
    if 'UP' in set(GCFG['relax']):
        n.lines['s_nom'] = n.lines.s_nom * 10.0
        STATE['relax_up'] = 'all TAMU line ratings x10'


def add_dc_poi(n, dem, v, mult, byop=None, byop_fixed=None, price=None, s_fixed=None, actor='social'):
    """v240 add_dc re-keyed by POI site: DC bus per site, POI links from the parent bus, POI upgrade capacity,
    PCLR conditional import with trigger-hour curtailment, per-site gas lateral lead / cost. price = developer stage."""
    pue_t = w2.PUE
    par_t = pd.read_csv(s1r.TASK).set_index('year')
    for c in ['POI', 'POI_cond', 'POI_upgrade', 'compute_IT', 'AIDC_training', 'grid_purchase', 'grid_cond', 'dc_curtail', 'dc_interrupt']:
        if c not in n.carriers.index:
            n.add('Carrier', c, co2_emissions=0.0)
    STATE['dc'] = []
    STATE.setdefault('poi_up', {})
    m1 = np.asarray(mult)
    Y = M.years()
    modes = STATE.get('modes', {})
    for s in sorted(dem.zone.unique()):
        site = SITES[s]
        dc = f'DC_{s}'
        mode = modes.get(s, 'PUBLIC')
        if dc not in n.buses.index:
            n.add('Bus', dc, carrier='AC', x=site['lon'], y=site['lat'], country='DC', reeds_zone='DC', reeds_state='DC',
                  interconnect='dc_facility', nerc_reg='DC')
        cond_on = (mode in ('GO_C', 'GF')) if price is not None else bool(STATE.get('cond_public', {}).get(s, False))
        # POI upgrade candidates (public LPs only; the developer receives an offer instead)
        if price is None and 'POI' not in set(GCFG['relax']) and site['U_max'] > 0 and s not in STATE['poi_up'] and ML['on']:
            # D1: POI upgrade approved in year q is energized at COD(q) = max(q + lead, procedural earliest grid COD)
            STATE['poi_up'][s] = []
            for qa, cod_u, q in M.approval_cohorts(site['U_lead'], floor=site['proc']):
                nm = f'POIup {s} q{qa}'
                cc = site['U_cost'] * M.crf(M.CFG['social_r'], UPGRADE_LIFE) * M.tv_factor(q, UPGRADE_LIFE, 'public')
                n.add('Link', nm, bus0=site['bus'], bus1=dc, carrier='POI_upgrade', p_nom_extendable=True, p_nom_max=site['U_max'],
                      capital_cost=cc, p_max_pu=0.0, p_min_pu=0.0, build_year=q, lifetime=UPGRADE_LIFE, efficiency=1.0)
                STATE['poi_up'][s].append((nm, q, cod_u))
                STATE.setdefault('approval_year', {})[nm] = qa
        elif price is None and 'POI' not in set(GCFG['relax']) and site['U_max'] > 0 and s not in STATE['poi_up']:
            cod_u = max(M.CFG['decision_year'] + site['U_lead'], site['proc'])
            q0 = M.first_period(cod_u)
            STATE['poi_up'][s] = []
            for q in M.periods():
                if q0 is None or q < q0:
                    continue
                nm = f'POIup {s} {q}'
                cc = site['U_cost'] * M.crf(M.CFG['social_r'], UPGRADE_LIFE) * M.tv_factor(q, UPGRADE_LIFE, 'public')
                n.add('Link', nm, bus0=site['bus'], bus1=dc, carrier='POI_upgrade', p_nom_extendable=True, p_nom_max=site['U_max'],
                      capital_cost=cc, p_max_pu=0.0, p_min_pu=0.0, build_year=q, lifetime=UPGRADE_LIFE, efficiency=1.0)
                STATE['poi_up'][s].append((nm, q, cod_u))
        elif price is None and s in STATE['poi_up']:
            for nm, q, cod_u in STATE['poi_up'][s]:
                if nm not in n.links.index:
                    cc = site['U_cost'] * M.crf(M.CFG['social_r'], UPGRADE_LIFE) * M.tv_factor(q, UPGRADE_LIFE, 'public')
                    n.add('Link', nm, bus0=site['bus'], bus1=dc, carrier='POI_upgrade', p_nom_extendable=True, p_nom_max=site['U_max'],
                          capital_cost=cc, p_max_pu=0.0, p_min_pu=0.0, build_year=q, lifetime=UPGRADE_LIFE, efficiency=1.0)
        for r in dem[dem.zone == s].itertuples():
            p = r.period
            pue = float(pue_t[(pue_t.st == 'TX') & (pue_t.year == min(p, 2035))].pue.iloc[0])
            par = par_t.loc[min(p, 2035)]
            inf_pu = float(par.infer_share * par.infer_util)
            fixed_pu = pue * (M.IDLE + (1 - M.IDLE) * inf_pu * m1)
            head = np.clip(1 - inf_pu * m1, 0, None)
            sname = f'{dc} S{p}'
            ppu = pd.Series(0.0, index=n.snapshots); ppu.loc[p] = fixed_pu
            n.add('Generator', sname, bus=dc, carrier='compute_IT', sign=-1, p_nom_extendable=True, p_nom_min=0.0,
                  p_nom_max=r.D_IT_MW, capital_cost=-v, marginal_cost=0.0, build_year=p, lifetime=Y)
            n.generators_t.p_max_pu[sname] = ppu.values
            n.generators_t.p_min_pu[sname] = ppu.values
            if s_fixed is not None:
                if STATE.get('s_upper_only'):
                    n.generators.loc[sname, 'p_nom_max'] = min(s_fixed.get((s, p), 0.0), r.D_IT_MW)
                else:
                    n.generators.loc[sname, ['p_nom_min', 'p_nom_max']] = min(s_fixed.get((s, p), 0.0), r.D_IT_MW)
            tname = f'{dc} train{p}'
            hpu = pd.Series(0.0, index=n.snapshots); hpu.loc[p] = head
            n.add('Generator', tname, bus=dc, carrier='AIDC_training', sign=-1, p_nom_extendable=True,
                  capital_cost=0.0, marginal_cost=0.0, build_year=p, lifetime=Y)
            n.generators_t.p_max_pu[tname] = hpu.values
            daily = pue * (1 - M.IDLE) * 24 * float(par.train_share * par.train_util)
            ent = dict(zone=s, bus=site['bus'], period=p, S=sname, T=tname, pue=pue, daily=daily, D=r.D_IT_MW, G=r.D_IT_MW,
                       firm=None, nf=None, cond=None, curt=None, mode=mode, actor=actor, private=price is not None)
            # D2: dynamic lost-compute price c = v / E_unit, E_unit = annual facility MWh per MW_IT (sampled snapshots
            # weighted to the year: inference/idle profile + daily training energy) -> a full-year interruption of 1 MW_IT
            # costs exactly v (value consistency with the service value of IT_online)
            w_ = n.snapshot_weightings.generators
            sl_ = np.asarray(n.snapshots.get_level_values(0) == p)
            e_unit = float((ppu.values[sl_] * w_.values[sl_]).sum()) + 365.0 * daily
            vv = (M.CFG['v_private'] or v) if price is not None else v
            c_int = vv / e_unit
            ent.update(e_unit=e_unit, c_interrupt=c_int, intr=None)
            STATE.setdefault('interrupt_price', {})[(s, p)] = dict(e_unit_MWh_per_MW_IT=e_unit, c_interrupt_USD_MWh=c_int, v=vv)
            if GCFG['interrupt_cap'] > 0 and not STATE.get('firm_strict'):
                iname = f'{dc} intr{p}'
                ipu = pd.Series(0.0, index=n.snapshots); ipu.loc[p] = 1.0
                n.add('Generator', iname, bus=dc, carrier='dc_interrupt', p_nom=pue * r.D_IT_MW * 1.5, p_nom_extendable=False,
                      build_year=p, lifetime=Y, marginal_cost=c_int)
                n.generators_t.p_max_pu[iname] = ipu.values
                ent['intr'] = iname
            trig = STATE.get('triggers', {}).get((s, p), [])
            tpu = pd.Series(0.0, index=n.snapshots)
            if trig:
                tpu.loc[trig] = 1.0
            if price is None:
                n.add('Link', f'POI {s} {p}', bus0=site['bus'], bus1=dc, carrier='POI', p_nom=pue * r.D_IT_MW * 1.5, efficiency=1.0,
                      p_nom_extendable=False, build_year=p, lifetime=Y, marginal_cost=0.0, capital_cost=0.0)
                ent['firm'] = ('Link', f'POI {s} {p}')
                if cond_on:
                    cn = f'POIc {s} {p}'
                    n.add('Link', cn, bus0=site['bus'], bus1=dc, carrier='POI_cond', p_nom=pue * r.D_IT_MW * 1.5, efficiency=1.0,
                          p_nom_extendable=False, build_year=p, lifetime=Y, marginal_cost=0.0, capital_cost=0.0)
                    n.links_t.p_max_pu[cn] = (1.0 - tpu).values
                    ent['cond'] = ('Link', cn)
            else:
                off = STATE['offer'].get((s, p), dict(firm=0.0, cond=0.0))
                firm_mw = 0.0 if mode == 'IS' else off['firm']
                cond_mw = off['cond'] if cond_on else 0.0
                gname = f'{dc} grid{p}'
                n.add('Generator', gname, bus=dc, carrier='grid_purchase', p_nom=firm_mw, p_nom_extendable=False,
                      build_year=p, lifetime=Y, marginal_cost=0.0)
                n.generators_t.marginal_cost[gname] = price[s].values
                ent['firm'] = ('Generator', gname)
                if cond_mw > 0:
                    cn = f'{dc} gridc{p}'
                    n.add('Generator', cn, bus=dc, carrier='grid_cond', p_nom=cond_mw, p_nom_extendable=False,
                          build_year=p, lifetime=Y, marginal_cost=0.0)
                    n.generators_t.marginal_cost[cn] = STATE['lmp_energy'][s].values
                    n.generators_t.p_max_pu[cn] = (1.0 - tpu).values
                    ent['cond'] = ('Generator', cn)
                ent['G'] = (firm_mw + cond_mw) / pue
            if cond_on and trig:      # PCLR curtailment: only at trigger snapshots (budgeted hours), lost-compute value
                cu = f'{dc} curt{p}'
                n.add('Generator', cu, bus=dc, carrier='dc_curtail', p_nom=pue * r.D_IT_MW * 1.5, p_nom_extendable=False,
                      build_year=p, lifetime=Y, marginal_cost=c_int)    # D2.2: same lost-compute basis as dc_interrupt
                n.generators_t.p_max_pu[cu] = tpu.values
                ent['curt'] = cu
            STATE['dc'].append(ent)
            if mode in ('GO_F', 'GO_C') or ML['on']:     # mainline: approval cohorts per site, below
                continue
            for car in (byop or []):
                bp = M.byop_params(car, actor)
                cod = bp['cod']
                lat_ann = 0.0
                if car in GAS_FIRED:
                    cod = max(cod, M.CFG['decision_year'] + site['lat_lead'])
                    rate = bp['rate']
                    lat_ann = site['lat_cost'] * M.crf(rate, M.BYOP_LIFE[car])
                fp = M.first_period(cod)
                if fp is None or p < fp:
                    continue
                bname = f'{dc} BYOP {car} {p}'
                if f'byop_{car}' not in n.carriers.index:
                    n.add('Carrier', f'byop_{car}', co2_emissions=0.0)
                ppu_b = pd.Series(0.0, index=n.snapshots)
                for q in M.periods():
                    ppu_b.loc[q] = M.avail_frac(p, cod, q) / bp['r'] if q >= p else 0.0
                kw = dict(bus=dc, carrier=f'byop_{car}', capital_cost=(bp['annual'] + lat_ann) * M.tv_factor(p, M.BYOP_LIFE[car], 'byop', actor),
                          marginal_cost=bp['mc'], build_year=p, lifetime=M.BYOP_LIFE[car])
                if byop_fixed is not None:
                    kw.update(p_nom=byop_fixed.get((s, car, p), 0.0), p_nom_extendable=False)
                else:
                    kw.update(p_nom_extendable=True, p_nom_max=pue * r.D_IT_MW * bp['r'] * 2.0)
                n.add('Generator', bname, **kw)
                n.generators_t.p_max_pu[bname] = ppu_b.values
                STATE.setdefault('byop_cod', {})[bname] = dict(cod=cod, build=p, r=bp['r'], carrier=car, zone=s,
                                                               lateral_USD_per_MW_yr=lat_ann)
        if ML['on'] and mode not in ('GO_F', 'GO_C') and byop:   # D1 approval cohorts of BYOP per site (all periods)
            ents = [e for e in STATE['dc'] if e['zone'] == s]
            dmax_fac = max(e['pue'] * e['D'] for e in ents) if ents else 0.0
            add_byop_cohorts(n, s, site, dmax_fac, byop, byop_fixed, actor)


def reuse_pool_poi(n):
    """ReEDS-retiring gas units at a POI parent bus (each unit assigned to ONE site: the nearest; never double-sold)"""
    g = n.generators
    buses = {d['bus'] for d in SITES.values()}
    x = g[~g.p_nom_extendable & g.bus.isin(buses) & g.carrier.isin(M.REUSE_CARRIERS)]
    x = x[(x.build_year + x.lifetime) <= M.periods()[-1]]
    if ML['on']:     # D14: only units in the verified R pool (location, status, capacity right, lead); empty = none
        x = x[x.index.astype(str).isin(set(pd.read_csv(ML_RPOOL).asset_id.astype(str)))]
    rows = []
    for name, r in x.iterrows():
        cand = [s for s, d in SITES.items() if d['bus'] == r.bus]
        s = min(cand, key=lambda s_: (n.buses.x[r.bus] - SITES[s_]['lon']) ** 2 + (n.buses.y[r.bus] - SITES[s_]['lat']) ** 2)
        rows.append(dict(asset_id=name, zone=s, bus=r.bus, carrier=r.carrier, MW=float(r.p_nom), retire_year=int(r.build_year + r.lifetime),
                         marginal_cost=float(r.marginal_cost), efficiency=float(r.efficiency),
                         p_max_pu=float(r.p_max_pu) if np.isfinite(r.p_max_pu) else 1.0,
                         source='ReEDS age-based RetireYear at the POI parent bus, PENDING_SITE_EVIDENCE'))
    return pd.DataFrame(rows)


def add_reuse_poi(n, dedicated, rfixed=None):
    """v240 add_reuse with the public extension at the parent bus and the dedicated one at the site DC bus"""
    pool = reuse_pool_poi(n)
    STATE['reuse'] = []
    if pool.empty:
        return pool
    for c in ['reuse_pub', 'byop_R']:
        if c not in n.carriers.index:
            n.add('Carrier', c, co2_emissions=0.0)
    rp_pub = M.reuse_params('social'); rp_dc = M.reuse_params('social')
    for r in pool.itertuples():
        cod = max(r.retire_year, M.CFG['decision_year'] + rp_pub['lead'])
        bp = M.first_period(cod)
        if bp is None:
            continue
        pub = f'{r.asset_id} Rpub'
        n.add('Generator', pub, bus=r.bus, carrier='reuse_pub', p_nom_extendable=True, p_nom_max=r.MW,
              capital_cost=rp_pub['annual'], marginal_cost=r.marginal_cost, efficiency=r.efficiency, p_max_pu=r.p_max_pu,
              build_year=bp, lifetime=M.REUSE_LIFE)
        ent = dict(asset_id=r.asset_id, zone=r.zone, MW=r.MW, retire_year=r.retire_year, COD=cod, build_period=bp,
                   pub=pub, dc=None, carrier=r.carrier)
        if (dedicated or rfixed is not None) and f'DC_{r.zone}' in n.buses.index:
            dcn = f'DC_{r.zone} BYOP R {r.asset_id}'
            kw = dict(bus=f'DC_{r.zone}', carrier='byop_R', capital_cost=rp_dc['annual'], marginal_cost=r.marginal_cost,
                      efficiency=r.efficiency, p_max_pu=1.0 / M.REUSE_R, build_year=bp, lifetime=M.REUSE_LIFE)
            kw.update(dict(p_nom=rfixed.get(r.asset_id, 0.0), p_nom_extendable=False) if rfixed is not None else
                      dict(p_nom_extendable=True, p_nom_max=r.MW))
            n.add('Generator', dcn, **kw)
            ent['dc'] = dcn
        STATE['reuse'].append(ent)
    return pool


_build_v240 = M.build


def ml_public_candidates(n, templ_g, templ_s, prof):
    """v250 bulk public candidates + record the bus wind / PV availability profile (the same PyPSA-USA profile is
    used for on-site BYOP wind / PV at that bus; WP-C keeps the PyPSA-USA weather year)"""
    off = V.add_public_candidates_bulk(n, templ_g, templ_s, prof)
    pm = n.generators_t.p_max_pu
    g = n.generators
    prof_ = {}
    for car in RE_CAR.values():
        for name in g.index[(g.carrier == car) & g.p_nom_extendable]:
            if name in pm and (g.bus[name], car) not in prof_:
                prof_[(g.bus[name], car)] = pm[name].values.copy()
    STATE['re_profile'] = prof_
    for o in off:
        o['approval_year'] = o['period'] - o['lead']           # D1: COD = approval + lead (integer public leads)
    return off


def build_rearch(config, scen, v, **kw):
    M.add_line_expansion = add_line_expansion_tamu
    M.add_public_candidates = ml_public_candidates if ML['on'] else V.add_public_candidates_bulk
    M.add_dc = add_dc_poi
    M.add_reuse = add_reuse_poi
    M.tech = tech_ra_relaxed
    if ML['on']:
        M.base_build = ml_base_build
        STATE['re_profile_pending'] = True
    STATE['poi_up'] = {}
    n, mult = _build_v240(config, scen, v, **kw)
    add_base_assets(n)
    add_s0_calibration(n, scen)
    add_grid_projects(n)
    STATE['no_harm_now'] = scen != 'S0' and GCFG['no_harm'] and STATE.get('shed_S0') is not None
    add_competing_load(n)
    add_regional_dc(n)
    if ML['on']:
        add_inherited_ramp(n)
        ml_public_potential(n)
        ml_gas_delta(n)
        if ML['stress_line_derate'] < 1.0:      # B7 optional interface derate at stress snapshots (PROXY, default off)
            sm = stress_mask(n.snapshots)
            n.lines_t.s_max_pu = pd.DataFrame(np.outer(np.where(sm, ML['stress_line_derate'], 1.0), n.lines.s_max_pu.values),
                                              index=n.snapshots, columns=n.lines.index)
    relax_upstream(n)
    ren = n.generators.index[n.generators.carrier.isin(['solar', 'onwind'])]
    miss = ren.difference(n.generators_t.p_max_pu.columns)
    assert len(miss) == 0, f'solar/onwind without availability profile: {list(miss)[:10]}'
    return n, mult


# ------------------------------------------------------------------------------------------------ constraints
def extra_rearch(n, snapshots):
    V.extra_gce(n, snapshots)        # v240 extra (ERM-DC B, DC task model, serve_cap, R rights, corridors) + TX ERM row
    m = n.model
    pnom = m['Generator-p_nom']
    gb = n.generators
    lnom = m['Link-p_nom'] if 'Link-p_nom' in m.variables else None
    rel = set(GCFG['relax'])
    for d in STATE.get('dc', []):
        p = d['period']
        sns = snapshots[snapshots.get_level_values(0) == p]
        nm = f"M2-serve_cap_{d['S']}"
        if not d['private']:
            fixed, ups = eq_terms(d['zone'], p)
            if math.isinf(fixed):
                fixed = d['pue'] * d['D'] * 1.5
            # equipment (+ PCLR uses the same equipment): firm + conditional flow <= EQ
            flow = m['Link-p'].sel(name=d['firm'][1], snapshot=sns)
            if d['cond']:
                flow = flow + m['Link-p'].sel(name=d['cond'][1], snapshot=sns)
                m.add_constraints(m['Link-p'].sel(name=d['cond'][1], snapshot=sns) <= pclr_cap(d['zone'], p), name=f"POI-pclr_{d['S']}")
            if ups and lnom is not None:
                ucap = sum(c_ * lnom.sel(name=u) for u, c_ in ups)
                m.add_constraints(flow - ucap <= fixed, name=f"POI-eq_{d['S']}")
            else:
                m.add_constraints(flow <= fixed, name=f"POI-eq_{d['S']}")
            # serve_cap rebuilt: S <= (EQ)/pue + dedicated firm capacity (IT terms)
            c = m.constraints[nm]
            lhs = c.lhs
            if ups and lnom is not None:
                lhs = lhs - sum((c_ / d['pue']) * lnom.sel(name=u) for u, c_ in ups)
            rhs_byop = float(c.rhs.values) - d['G']        # v240 rhs = G + fixed_firm
            m.remove_constraints(nm)
            m.add_constraints(lhs <= fixed / d['pue'] + rhs_byop, name=nm)
        # gas MDQ per site and day (dedicated gas units incl. reused gas steam/CT), MMBtu/d
        site = SITES[d['zone']]
        gas = [b for b in gb.index if gb.bus[b] == f"DC_{d['zone']}" and gb.carrier[b].startswith('byop_')
               and (gb.carrier[b][5:] in GAS_FIRED or gb.carrier[b] == 'byop_R')]
        if gas and site['mdq'] > 0:
            if ML['on']:     # v1.3 HHV heat rates (the unit efficiency is set from them in add_byop_cohorts)
                hr = xr.DataArray([3412.14 / max(float(gb.efficiency[b]), 0.2) for b in gas], coords={'name': gas}, dims='name')
            else:
                t = M.tech().set_index(['carrier', 'boundary'])
                hr = xr.DataArray([float(t.loc[(gb.carrier[b][5:], 'DC_BTM')].heat_rate_Btu_kWh) if gb.carrier[b] != 'byop_R'
                                   else 3412.14 / max(float(gb.efficiency[b]), 0.2) for b in gas], coords={'name': gas}, dims='name')
            pg = m['Generator-p'].sel(name=gas, snapshot=sns)
            days = xr.DataArray(sns.get_level_values(1).normalize().values, coords={'snapshot': sns}, dims='snapshot', name='day')
            fuel = (pg * hr * (M.SNAP_HOURS / 1000.0)).sum('name').groupby(days).sum()
            m.add_constraints(fuel <= site['mdq'], name=f"GAS-mdq_{d['S']}")
    gp_ = m['Generator-p']
    by_site = {}
    for d in STATE.get('dc', []):
        by_site.setdefault(d['zone'], []).append(d)
        sns = snapshots[snapshots.get_level_values(0) == d['period']]
        S = pnom.sel(name=d['S'])
        if d.get('intr'):     # D2.3: unplanned interruption <= cap x planned annual facility energy (0 in the strict Firm base)
            wt = xr.DataArray(n.snapshot_weightings.generators.loc[sns].values, coords={'snapshot': sns}, dims='snapshot')
            m.add_constraints((gp_.sel(name=d['intr'], snapshot=sns) * wt).sum('snapshot') - GCFG['interrupt_cap'] * d['e_unit'] * S <= 0,
                              name=f"P01-intr_cap_{d['S']}")
        outs = [x for x in (d.get('intr'), d.get('curt')) if x]
        if outs:              # D2.3: contractual + unplanned interruption <= actual facility demand in every snapshot
            load = gp_.sel(name=d['S'], snapshot=sns) + gp_.sel(name=d['T'], snapshot=sns)
            m.add_constraints(gp_.sel(name=outs, snapshot=sns).sum('name') - load <= 0, name=f"P01-intr_le_load_{d['S']}")
    for s_, lst in by_site.items():   # P0-1: online IT never falls unless the request itself is cancelled
        lst = sorted(lst, key=lambda d: d['period'])
        for a_, b_ in zip(lst[:-1], lst[1:]):
            drop = max(0.0, a_['D'] - b_['D'])
            m.add_constraints(pnom.sel(name=b_['S']) - pnom.sel(name=a_['S']) >= -drop, name=f"P01-online_monotone_{b_['S']}")
    g_sh = n.generators[n.generators.carrier == 'load_shed']    # background shed and competing-queue curtailment
    if STATE.get('no_harm_now') and len(g_sh) and 'Generator-p' in m.variables:   # D2.4 shed <= frozen S0 per generator (+0.001 MW)
        sh0 = STATE['shed_S0']
        g = g_sh
        ub = pd.DataFrame({gn: (sh0[gn].reindex(snapshots).fillna(0.0).values if gn in sh0 else np.zeros(len(snapshots))) + 0.001
                           for gn in g.index}, index=snapshots)
        ub.index.name = 'snapshot'; ub.columns.name = 'name'
        m.add_constraints(gp_.sel(name=list(g.index), snapshot=snapshots) <= xr.DataArray(ub), name='D24-no_harm_existing_customers')
        STATE['no_harm_applied'] = len(g)
    if GCFG.get('s0_calibrate') and STATE.get('s0cal_pairs') and 'Link-p_nom' in m.variables:
        lp_ = m['Link-p_nom']; ext_ = set(n.links.index[n.links.p_nom_extendable])
        for b in STATE['s0cal_pairs']:
            if f'{b}_fwd' in ext_:
                m.add_constraints(lp_.sel(name=f'{b}_fwd') - lp_.sel(name=f'{b}_rev') == 0, name=f'S0CAL-sym_{b}')
    if ML['on']:
        ml_space(n, m)
    if STATE.get('lex'):
        lex_presolve(n, m)


def independent_it(s, p, pue):
    """D1: C_independent[s,y] = IT deliverable by approval, POI equipment (E0 + full upgrade) and COD alone"""
    d = SITES[s]
    if 'POI' in set(GCFG['relax']):
        return float('inf')
    fixed, _ = eq_terms(s, p)
    ups = 0.0
    for nm, q, cod in STATE.get('poi_up', {}).get(s, []):
        if q <= p:
            ups = max(ups, d['U_max'] * M.avail_frac(q, cod, p))
    return (fixed + ups) / pue


def lex_presolve(n, m):
    """P0-2 / D1 strict Speed-First grid-only base (S1_GRID_EARLIEST), stages A1/A2 per year as a Gurobi hierarchical
    multi-objective on the exported model (continuous LP; each level is fixed with a 1e-6 relative tolerance):
      A1_y  max sum_s IT_online[s,y]                                   (earliest year = highest priority)
      A2_y  max z_y  s.t.  IT_online[s,y] >= z_y * R[s,y]  for eligible s (R = min(D, C_independent) > 0)
    The optimal levels T*_y and z*_y are then imposed on the linopy model, and PyPSA's own solve does stage B (min
    social resource cost). A2 is skipped when fewer than two sites are eligible. z*_y = 0 with T*_y > 0 is flagged
    LEXIMIN_ZERO_LOCK (the min-share level is then not imposed; reported, not hidden)."""
    import gurobipy as gp
    lex = STATE['lex']
    dc = STATE.get('dc', [])
    years = sorted({d['period'] for d in dc})
    gm = m.to_gurobipy()
    gm.setParam('Threads', M.CFG['threads'])
    lab = lambda nm: int(m['Generator-p_nom'].sel(name=nm).labels.values.ravel()[0])
    var = lambda nm: gm.getVarByName(f'x{lab(nm)}')
    objs, info = [], []
    for k, y in enumerate(years):
        ds = [d for d in dc if d['period'] == y]
        tot = gp.quicksum(var(d['S']) for d in ds)
        objs.append(('A1', y, tot, None))
        R = {d['zone']: min(d['D'], independent_it(d['zone'], y, d['pue'])) for d in ds}
        elig = [d for d in ds if R[d['zone']] > 1e-6]
        if len(elig) >= 2:
            z = gm.addVar(lb=0.0, ub=1.0, name=f'lexz_{y}')
            for d in elig:
                gm.addConstr(var(d['S']) - R[d['zone']] * z >= 0, name=f'lexshare_{d["zone"]}_{y}')
            objs.append(('A2', y, z, R))
        info.append(dict(year=y, R={s_: round(v_, 3) for s_, v_ in R.items()}, eligible=[d['zone'] for d in elig]))
    gm.setObjective(gp.LinExpr(), gp.GRB.MINIMIZE)      # drop the cost objective: the hierarchy holds only A1/A2 levels
    gm.NumObj = len(objs)
    for i, (kind, y, expr, _) in enumerate(objs):
        gm.setObjectiveN(expr, index=i, priority=10 * len(objs) - i, weight=-1.0, reltol=1e-6, abstol=1e-3, name=f'{kind}_{y}')
    gm.ModelSense = 1
    t0 = time.time()
    gm.optimize()
    ok = gm.Status == gp.GRB.OPTIMAL
    res = []
    for i, (kind, y, expr, R) in enumerate(objs):
        # level values read from the final hierarchical solution (every level is kept within its tolerance there)
        val = (float(expr.getValue()) if kind == 'A1' else float(expr.X)) if ok else float('nan')
        res.append(dict(stage=kind, year=y, value=val))
        ds = [d for d in dc if d['period'] == y]
        Ssum = sum(m['Generator-p_nom'].sel(name=d['S']) for d in ds)
        if kind == 'A1' and ok:
            m.add_constraints(Ssum >= val * (1 - 1e-6) - 1e-3, name=f'P02-A1_{y}')
        if kind == 'A2' and ok:
            if val < 1e-6 and any(r['stage'] == 'A1' and r['year'] == y and r['value'] > 1e-3 for r in res):
                res[-1]['flag'] = 'LEXIMIN_ZERO_LOCK'
                continue
            for d in ds:
                if R[d['zone']] > 1e-6:
                    m.add_constraints(m['Generator-p_nom'].sel(name=d['S']) >= val * R[d['zone']] * (1 - 1e-6) - 1e-3,
                                      name=f"P02-A2_{d['zone']}_{y}")
    lex.update(status=int(gm.Status), optimal=ok, seconds=round(time.time() - t0, 1), levels=res, eligibility=info)
    STATE['lex_log'] = lex
    if not ok:
        raise RuntimeError(f'P0-2 lexicographic pre-solve not optimal (Gurobi status {gm.Status})')


# ------------------------------------------------------------------------------------------------ S1 -> offer
def s1_offer(n1):
    """ex-ante grid offer per site-year from the solved joint S1 (grid-only) LP: firm = max firm POI flow actually
    deliverable, conditional = PCLR MW on the remaining equipment; price = parent-bus LMP (+ ERM adder)."""
    offer, rows = {}, []
    lp = n1.links_t.p0
    for d in STATE.get('dc', []):
        s, p = d['zone'], d['period']
        sl = n1.snapshots.get_level_values(0) == p
        f = d['firm'][1]
        firm = float(lp[f][sl].max()) if f in lp else 0.0
        firm = max(0.0, firm) * (1 + GCFG['offer_tol'])
        fixed, ups = eq_terms(s, p)
        eq = (fixed if not math.isinf(fixed) else d['pue'] * d['D'] * 1.5) + sum(c_ * float(n1.links.p_nom_opt[u]) for u, c_ in ups)
        cond = max(0.0, min(pclr_cap(s, p), eq - firm))
        offer[(s, p)] = dict(firm=firm, cond=cond)
        rows.append(dict(site=s, year=p, offer_firm_MW=firm, offer_cond_MW=cond, equipment_MW=eq, S1_served_MW_IT=float(n1.generators.p_nom_opt[d['S']])))
    return offer, pd.DataFrame(rows)


def select_triggers(n1):
    """ex-ante PCLR trigger snapshots per site-year: highest S1 parent-bus LMP snapshots, budget = pclr_hours scaled
    to the sampled share of the year, runs no longer than pclr_max_consec_h (greedy)"""
    trig = {}
    mp = n1.buses_t.marginal_price
    for d in STATE.get('dc', []):
        s, p = d['zone'], d['period']
        sns = n1.snapshots[n1.snapshots.get_level_values(0) == p]
        nsel = int(round(GCFG['pclr_hours'] / M.SNAP_HOURS * len(sns) / 2920.0))
        maxrun = max(1, int(GCFG['pclr_max_consec_h'] // M.SNAP_HOURS))
        pr = mp[d['bus']].loc[sns].sort_values(ascending=False)
        if ML['on']:      # D3: trigger tied to the defined system-stress snapshots first, then the highest S1 LMP
            sm = pd.Series(stress_mask(sns), index=sns)
            pr = pd.concat([pr[sm.reindex(pr.index).values], pr[~sm.reindex(pr.index).values]])
        pos = {sn: i for i, sn in enumerate(sns)}
        chosen = set()
        for sn in pr.index:
            if len(chosen) >= nsel:
                break
            i = pos[sn]
            left = 0
            while i - left - 1 >= 0 and sns[i - left - 1] in chosen:
                left += 1
            right = 0
            while i + right + 1 < len(sns) and sns[i + right + 1] in chosen:
                right += 1
            if left + right + 1 > maxrun:
                continue
            chosen.add(sn)
        trig[(s, p)] = sorted(chosen)
    return trig


# ------------------------------------------------------------------------------------------------ S2 developer
def private_mode(config, s1_net, v_priv, mult, site, mode, reuse_on, price, lmp):
    """one developer LP (site, supply mode): lexicographic speed-first, then private cost"""
    dem = M.study_new_demand()
    dem = dem[dem.zone == site]
    n = pypsa.Network()
    n.set_snapshots(s1_net.snapshots)
    n.investment_periods = M.periods()
    n.snapshot_weightings = s1_net.snapshot_weightings.copy()
    n.investment_period_weightings = s1_net.investment_period_weightings.copy()
    n.investment_period_weightings.loc[:, 'objective'] = [M.w_private(p) for p in M.periods()]
    STATE['modes'] = {site: mode}
    STATE['lmp_energy'] = {site: lmp}
    add_dc_poi(n, dem, v_priv, mult, byop=M.CFG['byop_techs'] if mode in ('GF', 'IS') else None, price={site: price}, actor='private')
    rs = []
    if reuse_on and mode in ('GF', 'IS'):
        for e in STATE.get('reuse_s1', []):
            if e['zone'] != site:
                continue
            rp = M.reuse_params('private')
            dcn = f'DC_{site} BYOP R {e["asset_id"]}'
            if 'byop_R' not in n.carriers.index:
                n.add('Carrier', 'byop_R', co2_emissions=0.0)
            n.add('Generator', dcn, bus=f'DC_{site}', carrier='byop_R', p_nom_extendable=True, p_nom_max=e['MW'],
                  capital_cost=rp['annual'], marginal_cost=e['mc'], p_max_pu=1.0 / M.REUSE_R, build_year=e['build_period'],
                  lifetime=M.REUSE_LIFE, efficiency=e.get('eff', 0.33))
            rs.append((e['asset_id'], dcn))
    M.STATE['erm'] = False
    sv_reuse = STATE.get('reuse', []); STATE['reuse'] = []
    sv_corr = STATE.get('corridors', []); STATE['corridors'] = []
    opts = dict(Method=2, Crossover=0, BarConvTol=1e-7, OutputFlag=0, Threads=M.CFG['threads'])
    m = n.optimize.create_model(multi_investment_periods=True)
    extra_rearch(n, n.snapshots)
    cost_obj = m.objective.expression
    Snames = {int(n.generators.build_year[x]): x for x in n.generators.index[n.generators.carrier == 'compute_IT']}
    lex = {}
    for p in sorted(Snames):
        Sv = m['Generator-p_nom'].sel(name=Snames[p])
        m.objective = -1.0 * Sv
        st, tc = m.solve(solver_name='gurobi', **opts)
        s_star = float(m.solution['Generator-p_nom'].sel(name=Snames[p])) if st == 'ok' else 0.0
        lex[p] = dict(S_max=s_star, termination=str(tc))
        m.add_constraints(Sv >= max(0.0, s_star * (1 - 1e-6) - 1e-4), name=f'S2SF-lex_{site}_{p}')
    m.objective = cost_obj
    n.optimize.solve_model(solver_name='gurobi', solver_options=opts)
    STATE['reuse'] = sv_reuse; STATE['corridors'] = sv_corr
    M.STATE['erm'] = True
    K = {(site, n.generators.carrier[b][5:], int(n.generators.build_year[b])): float(n.generators.p_nom_opt[b])
         for b in n.generators.index[n.generators.carrier.str.startswith('byop_') & (n.generators.carrier != 'byop_R')]}
    R = {aid: float(n.generators.p_nom_opt[dcn]) for aid, dcn in rs}
    S = {p: float(n.generators.p_nom_opt[x]) for p, x in Snames.items()}
    w = n.snapshot_weightings.generators
    per = n.snapshots.get_level_values(0)
    right_f, right_c, imp_e, curt_e = {}, {}, {}, {}
    for d in STATE['dc']:
        p = d['period']; sl = per == p
        gn = d['firm'][1]
        right_f[(site, p)] = float(n.generators_t.p[gn][sl].max()) if gn in n.generators_t.p else 0.0
        right_c[(site, p)] = float(n.generators_t.p[d['cond'][1]][sl].max()) if d['cond'] and d['cond'][1] in n.generators_t.p else 0.0
        imp_e[p] = float((n.generators_t.p[gn][sl] * w[sl]).sum()) + (float((n.generators_t.p[d['cond'][1]][sl] * w[sl]).sum()) if d['cond'] else 0.0)
        curt_e[p] = float((n.generators_t.p[d['curt']][sl] * w[sl]).sum()) if d['curt'] else 0.0
    return dict(site=site, mode=mode, private_objective=float(n.objective), termination=str(m.termination_condition),
                integer_vars=int(len(m.binaries) + len(m.integers)), S=S, lexicographic=lex, K=K, R=R,
                right_firm=right_f, right_cond=right_c, import_MWh=imp_e, curtail_MWh=curt_e,
                byop_MW=sum(K.values()) + sum(R.values()), _n=n)


def choose_mode(res):
    """lexicographic across modes: served IT trajectory (earliest year first, 0.1 MW tolerance), then private cost;
    costs within 1e-5 (relative) are a tie and the simpler mode wins (order GO_F, GO_C, GF, IS) - a GF solution that
    builds nothing is reported as the Grid-Only mode it equals"""
    years = sorted(res[0]['S'])
    ok = [r for r in res if r['termination'] == 'optimal'] or res
    srv = lambda r: tuple(-round(r['S'][p], 1) for p in years)
    best_srv = min(srv(r) for r in ok)
    cand = [r for r in ok if srv(r) == best_srv]
    cmin = min(r['private_objective'] for r in cand)
    tie = [r for r in cand if r['private_objective'] <= cmin + 1e-5 * max(1.0, abs(cmin))]
    return min(tie, key=lambda r: MODES.index(r['mode']))


def developer_stage(config, s1_net, v_priv, mult, reuse_on, iteration):
    sw = s1_net.snapshot_weightings.generators
    ow = pd.Series([float(s1_net.investment_period_weightings.objective[p]) for p in s1_net.snapshots.get_level_values(0)],
                   index=s1_net.snapshots)
    erm_p = s1_net.buses_t.get('erm_price')
    K, R, rights, out = {}, {}, {}, []
    for site, d in SITES.items():
        lmp = s1_net.buses_t.marginal_price[d['bus']].astype(float)
        adder = pd.Series(0.0, index=s1_net.snapshots)
        if M.CFG['tariff'] == 'energy_erm' and erm_p is not None and d['bus'] in erm_p:
            adder = (1 + w2.ERM_MARGIN) * erm_p[d['bus']].astype(float).fillna(0.0).abs() / (sw * ow)
        res = [private_mode(config, s1_net, v_priv, mult, site, mode, reuse_on, lmp + adder, lmp) for mode in GCFG['s2_modes']]
        best = choose_mode(res)
        K.update(best['K']); R.update(best['R'])
        for p in best['S']:
            rights[(site, p)] = dict(firm=best['right_firm'].get((site, p), 0.0), cond=best['right_cond'].get((site, p), 0.0),
                                     S=best['S'][p], mode=best['mode'])
        for r in res:
            out.append(dict(iteration=iteration, site=site, mode=r['mode'], chosen=r['mode'] == best['mode'],
                            private_objective=r['private_objective'], termination=r['termination'], integer_vars=r['integer_vars'],
                            S=json.dumps({int(k): round(v_, 3) for k, v_ in r['S'].items()}), byop_MW=r['byop_MW'],
                            K=json.dumps({f'{c}_{p}': round(v_, 3) for (_, c, p), v_ in r['K'].items() if v_ > 1e-3}),
                            R=json.dumps({a: round(v_, 3) for a, v_ in r['R'].items() if v_ > 1e-3}),
                            import_MWh=json.dumps({int(k): round(v_, 1) for k, v_ in r['import_MWh'].items()}),
                            curtail_MWh=json.dumps({int(k): round(v_, 1) for k, v_ in r['curtail_MWh'].items()}),
                            mean_lmp=float(lmp.mean()), mean_adder=float(adder.mean())))
    STATE['modes'] = {}
    return K, R, rights, out


def label_mode(S, firm_MWh, cond_MWh, byop_MW):
    """D3 ex-post supply-mode label of one site-year (no mode variable in the LP): IS = served with zero public import;
    GF = public import + own capacity; GO_C = import incl. conditional, no own capacity; GO_F = firm import only"""
    if S <= 1e-3:
        return 'NOT_SERVED'
    if firm_MWh + cond_MWh <= 1e-3:
        return 'IS'
    if byop_MW > 0.5:
        return 'GF'
    return 'GO_C' if cond_MWh > 1e-3 else 'GO_F'


def developer_joint(config, s1_net, v_priv, mult, reuse_on, iteration):
    """D13 / WP-A4: ONE developer LP for all 8 Epoch buses (common private objective, every bus keeps its own power
    balance, POI, gas MDQ, potential and COD; no on-site power moves between buses). Grid offer per bus-year = the
    jointly deliverable S1_EARLIEST firm import (+ PCLR conditional); price = S1 parent-bus LMP (+ ERM adder).
    Lexicographic speed-first: year by year (earliest first) max sum_s IT_online[s, y], fixed; then min private cost.
    No max-min fairness layer, no mode enumeration: GO_F / GO_C / GF / IS are labelled after the solve."""
    n, m, (sv_reuse, sv_corr) = developer_joint_build(s1_net, v_priv, mult)
    opts = dict(Method=2, Crossover=0, BarConvTol=1e-7, OutputFlag=0, Threads=M.CFG['threads'])
    cost_obj = m.objective.expression
    lex = {}
    for p in sorted({d['period'] for d in STATE['dc']}):
        Sv = m['Generator-p_nom'].sel(name=[d['S'] for d in STATE['dc'] if d['period'] == p]).sum('name')
        m.objective = -1.0 * Sv
        _require_gate('developer_joint lex')
        st, tc = m.solve(solver_name='gurobi', **opts)
        s_star = float(sum(float(m.solution['Generator-p_nom'].sel(name=d['S'])) for d in STATE['dc'] if d['period'] == p)) if st == 'ok' else 0.0
        lex[p] = dict(S_max_total=s_star, termination=str(tc))
        m.add_constraints(Sv >= max(0.0, s_star * (1 - 1e-6) - 1e-3), name=f'S2J-lex_{p}')
    m.objective = cost_obj
    _require_gate('developer_joint cost')
    n.optimize.solve_model(solver_name='gurobi', solver_options=opts)
    STATE['reuse'] = sv_reuse; STATE['corridors'] = sv_corr
    M.STATE['erm'] = True
    ay = STATE.get('approval_year', {})
    K = {}
    for comp, df_ in (('Generator', n.generators), ('StorageUnit', n.storage_units)):
        for b in df_.index[df_.carrier.str.startswith('byop_') & (df_.carrier != 'byop_R')]:
            info = STATE['byop_cod'][b]
            K[(info['zone'], info['carrier'], ay[b])] = float(df_.p_nom_opt[b])
    w = n.snapshot_weightings.generators
    per = n.snapshots.get_level_values(0)
    rights, out = {}, []
    for d in STATE['dc']:
        s, p = d['zone'], d['period']; sl = per == p
        gn = d['firm'][1]
        ff = n.generators_t.p[gn][sl] if gn in n.generators_t.p else pd.Series(0.0)
        cf = n.generators_t.p[d['cond'][1]][sl] if d['cond'] and d['cond'][1] in n.generators_t.p else pd.Series(0.0)
        S = float(n.generators.p_nom_opt[d['S']])
        bg = [b for b in n.generators.index if n.generators.bus[b] == f'DC_{s}' and n.generators.carrier[b].startswith('byop_')
              and int(n.generators.build_year[b]) <= p]
        bs = [b for b in n.storage_units.index if n.storage_units.bus[b] == f'DC_{s}' and int(n.storage_units.build_year[b]) <= p]
        bmw = float(n.generators.p_nom_opt[bg].sum()) + float(n.storage_units.p_nom_opt[bs].sum())
        bmwh = float(sum((n.generators_t.p[b][sl] * w[sl]).sum() for b in bg if b in n.generators_t.p))
        fe = float((ff * w[sl]).sum()) if len(ff) > 1 else 0.0
        ce = float((cf * w[sl]).sum()) if len(cf) > 1 else 0.0
        mode = label_mode(S, fe, ce, bmw)
        rights[(s, p)] = dict(firm=float(ff.max()) if len(ff) else 0.0, cond=float(cf.max()) if len(cf) else 0.0, S=S, mode=mode)
        out.append(dict(iteration=iteration, site=s, year=p, mode=mode, chosen=True, requested_IT_MW=d['D'], S=S,
                        offer_firm_MW=STATE['offer'].get((s, p), {}).get('firm', 0.0), offer_cond_MW=STATE['offer'].get((s, p), {}).get('cond', 0.0),
                        right_firm_MW=rights[(s, p)]['firm'], right_cond_MW=rights[(s, p)]['cond'], grid_import_MWh=fe + ce,
                        firm_import_MWh=fe, conditional_import_MWh=ce, BYOP_capacity_MW=bmw, BYOP_gen_MWh=bmwh,
                        K=json.dumps({f'{c}_q{q}': round(v_, 3) for (s_, c, q), v_ in K.items() if s_ == s and v_ > 1e-3}),
                        private_objective=float(n.objective), termination=str(m.termination_condition),
                        integer_vars=int(len(m.binaries) + len(m.integers)), lexicographic=json.dumps(lex)))
    STATE['modes'] = {}
    STATE['dev_net'] = n
    return K, {}, rights, out


def developer_joint_build(s1_net, v_priv, mult):
    """the joint developer network and its linopy model (no solve; also used by the Stage A structural test)"""
    dem = M.study_new_demand()
    n = pypsa.Network()
    n.set_snapshots(s1_net.snapshots)
    n.investment_periods = M.periods()
    n.snapshot_weightings = s1_net.snapshot_weightings.copy()
    n.investment_period_weightings = s1_net.investment_period_weightings.copy()
    n.investment_period_weightings.loc[:, 'objective'] = [M.w_private(p) for p in M.periods()]
    sw = s1_net.snapshot_weightings.generators
    ow = pd.Series([float(s1_net.investment_period_weightings.objective[p]) for p in s1_net.snapshots.get_level_values(0)], index=s1_net.snapshots)
    erm_p = s1_net.buses_t.get('erm_price')
    price, lmps = {}, {}
    for s, d in SITES.items():
        lmp = s1_net.buses_t.marginal_price[d['bus']].astype(float)
        adder = pd.Series(0.0, index=s1_net.snapshots)
        if M.CFG['tariff'] == 'energy_erm' and erm_p is not None and d['bus'] in erm_p:
            adder = (1 + w2.ERM_MARGIN) * erm_p[d['bus']].astype(float).fillna(0.0).abs() / (sw * ow)
        price[s], lmps[s] = lmp + adder, lmp
    STATE['modes'] = {s: 'GF' for s in SITES}
    STATE['lmp_energy'] = lmps
    add_dc_poi(n, dem, v_priv, mult, byop=M.CFG['byop_techs'], price=price, actor='private')
    ml_gas_delta(n)
    M.STATE['erm'] = False
    sv_reuse = STATE.get('reuse', []); STATE['reuse'] = []
    sv_corr = STATE.get('corridors', []); STATE['corridors'] = []
    m = n.optimize.create_model(multi_investment_periods=True)
    extra_rearch(n, n.snapshots)
    return n, m, (sv_reuse, sv_corr)


def _require_gate(where):
    """E1: in the mainline every optimizer call needs RUN_AUTHORIZATION=APPROVED (checked at start, re-checked here)"""
    if ML['on'] and not (ML.get('gate') or {}).get('approved'):
        raise SystemExit(f'RUN_GATE: solver call refused ({where}): RUN_AUTHORIZATION not APPROVED')


def mainline_gate(cfg_path):
    """E1 run gate: APPROVED + approved code commit is HEAD or an ancestor with no code / input change since + every
    code / input SHA-256 equal to MAINLINE_V13_PRE_RUN_MANIFEST.json. Returns dict(approved, reasons, ...)"""
    import subprocess, yaml
    cfg = yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))['mainline']
    root = Path(__file__).resolve().parents[3]
    reasons = []
    auth = str(cfg.get('run_authorization', 'NOT_APPROVED'))
    if auth != 'APPROVED':
        reasons.append(f'run_authorization={auth}')
    head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    sha = cfg.get('approved_git_sha')
    if not sha:
        reasons.append('approved_git_sha missing')
    else:
        anc = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', str(sha), 'HEAD']).returncode == 0
        chg = subprocess.run(['git', '-C', str(root), 'diff', '--name-only', str(sha), 'HEAD', '--', 'workflow/byop/model', 'workflow/byop/inputs',
                              'workflow/byop/build', 'workflow/byop/run'], capture_output=True, text=True).stdout.split()
        if not anc:
            reasons.append(f'approved_git_sha {sha} is not HEAD or an ancestor of HEAD {head}')
        if chg:
            reasons.append(f'code/input changed since the approved commit: {chg[:5]}')
    man_p = root / cfg.get('manifest', 'current_work_pckg/MAINLINE_V13_PRE_RUN_MANIFEST.json')
    if not man_p.exists():
        reasons.append(f'manifest missing: {man_p}')
    else:
        man = json.loads(man_p.read_text(encoding='utf-8'))
        for rel, h in {**man.get('code_sha256', {}), **man.get('inputs_sha256', {})}.items():
            f = root / rel
            if not f.exists() or M.sha(f) != h:
                reasons.append(f'sha256 mismatch: {rel}')
    return dict(approved=not reasons, reasons=reasons, head=head, approved_git_sha=sha, config=str(cfg_path))


def extra_rights(n, snapshots):
    """public S2 LP: the developer's committed import rights cap the firm / conditional POI flows"""
    extra_rearch(n, snapshots)
    m = n.model
    rights = STATE.get('rights')
    if not rights:
        return
    for d in STATE.get('dc', []):
        rt = rights.get((d['zone'], d['period']))
        if rt is None:
            continue
        sns = snapshots[snapshots.get_level_values(0) == d['period']]
        m.add_constraints(m['Link-p'].sel(name=d['firm'][1], snapshot=sns) <= rt['firm'] * (1 + 1e-6) + 1e-3, name=f"S2-right_firm_{d['S']}")
        if d['cond']:
            m.add_constraints(m['Link-p'].sel(name=d['cond'][1], snapshot=sns) <= rt['cond'] * (1 + 1e-6) + 1e-3, name=f"S2-right_cond_{d['S']}")


# ------------------------------------------------------------------------------------------------ ledgers / audits
def poi_ledger(n, tag, case_id):
    rows = []
    per = n.snapshots.get_level_values(0)
    w = n.snapshot_weightings.generators
    for d in STATE.get('dc', []):
        s, p = d['zone'], d['period']
        sl = per == p
        S = float(n.generators.p_nom_opt[d['S']])
        fixed, ups = eq_terms(s, p) if not d['private'] else (float('nan'), [])
        U = {u: float(n.links.p_nom_opt[u]) for u, _ in ups if u in n.links.index}
        eq = (fixed if not math.isinf(fixed) else float('inf')) + sum(c_ * U.get(u, 0.0) for u, c_ in ups)
        f = d['firm'][1]
        ff = n.links_t.p0[f][sl] if d['firm'][0] == 'Link' and f in n.links_t.p0 else pd.Series(0.0)
        cf = n.links_t.p0[d['cond'][1]][sl] if d['cond'] and d['cond'][0] == 'Link' and d['cond'][1] in n.links_t.p0 else pd.Series(0.0)
        cu = n.generators_t.p[d['curt']][sl] if d['curt'] and d['curt'] in n.generators_t.p else pd.Series(0.0)
        it_ = n.generators_t.p[d['intr']][sl] if d.get('intr') and d['intr'] in n.generators_t.p else pd.Series(0.0)
        it_e = float((it_ * w[sl]).sum()) if len(it_) > 1 else 0.0
        cu_e = float((cu * w[sl]).sum()) if len(cu) > 1 else 0.0
        byop = [b for b in n.generators.index if n.generators.bus[b] == f'DC_{s}' and n.generators.carrier[b].startswith('byop_')
                and int(n.generators.build_year[b]) <= p]
        bsu = [b for b in n.storage_units.index if n.storage_units.bus[b] == f'DC_{s}' and n.storage_units.carrier[b].startswith('byop_')
               and int(n.storage_units.build_year[b]) <= p]
        bgen = float(sum((n.generators_t.p[b][sl] * w[sl]).sum() for b in byop if b in n.generators_t.p))
        mu_eq = float('nan')
        try:
            mu_eq = float(abs(n.model.dual[f"POI-eq_{d['S']}"]).sum()) if f"POI-eq_{d['S']}" in n.model.constraints else float('nan')
        except Exception:
            pass
        ff_e = float((ff * w[sl]).sum()) if len(ff) > 1 else 0.0
        cf_e = float((cf * w[sl]).sum()) if len(cf) > 1 else 0.0
        bmw = (float(n.generators.p_nom_opt[byop].sum()) if byop else 0.0) + (float(n.storage_units.p_nom_opt[bsu].sum()) if bsu else 0.0)
        ml_extra = dict(IT_energized_MW=S, grid_import_MWh=ff_e + cf_e, BYOP_gen_MWh=bgen, BYOP_capacity_MW=bmw,
                        certified_import_MW=STATE.get('offer', {}).get((s, p), {}).get('firm', float('nan')),
                        poi_eq_dual_abs=mu_eq, mode_label=label_mode(S, ff_e, cf_e, bmw),
                        stress_snapshot_min_firm_MW=float(ff[stress_mask(ff.index)].min()) if len(ff) > 1 and stress_mask(ff.index).any() else float('nan'),
                        procedure_ready_year=SITES[s]['proc'],
                        earliest_grid_COD=min([x['cod'] if x['pre'] else max(x['cod'], SITES[s]['proc']) for x in SITES[s].get('E0rows') or []]
                                              + [c_ for _, _, c_ in STATE.get('poi_up', {}).get(s, [])[:1]], default=float('nan')))
        rows.append(dict(case_id=case_id, scenario=tag, site=s, parent_bus=d['bus'], year=p, requested_IT_MW=d['D'], served_IT_MW=S, **ml_extra,
                         unserved_IT_MW=d['D'] - S, PUE=d['pue'], equipment_fixed_MW=fixed, equipment_total_MW=eq,
                         poi_upgrade_MW_cum=sum(U.values()), firm_entitlement_used_MW=float(ff.max()) if len(ff) else 0.0,
                         conditional_peak_MW=float(cf.max()) if len(cf) else 0.0,
                         total_import_peak_MW=float((ff + cf.reindex(ff.index).fillna(0.0)).max()) if len(ff) > 1 else (float(ff.max()) if len(ff) else 0.0),
                         firm_import_MWh=float((ff * w[sl]).sum()) if len(ff) > 1 else 0.0,
                         conditional_import_MWh=float((cf * w[sl]).sum()) if len(cf) > 1 else 0.0,
                         curtailed_MWh=float((cu * w[sl]).sum()) if len(cu) > 1 else 0.0,
                         pclr_cap_MW=pclr_cap(s, p), byop_MW=float(n.generators.p_nom_opt[byop].sum()) if byop else 0.0,
                         earliest_grid_COD_procedural=SITES[s]['proc'], poi_upgrade_earliest_COD=max(M.CFG['decision_year'] + SITES[s]['U_lead'], SITES[s]['proc']),
                         confidence=SITES[s]['confidence'], mode=d['mode'], interrupt_MWh=it_e, e_unit=d.get('e_unit', np.nan),
                         c_interrupt_USD_MWh=d.get('c_interrupt', np.nan),
                         served_energy_equiv_IT_MW=S - (it_e + cu_e) / d['e_unit'] if d.get('e_unit') else S))
    return pd.DataFrame(rows)


def upgrade_ledger(n, tag, case_id):
    """resource cost of POI upgrades (public, social r_s) and committed grid projects (sunk, reported only)"""
    rows = []
    P = M.periods()
    ws = {p: M.years_p(p) * M.df(p, M.CFG['social_r']) for p in P}
    for s, lst in STATE.get('poi_up', {}).items():
        for nm, q, cod in lst:
            if nm not in n.links.index:
                continue
            MW = float(n.links.p_nom_opt[nm])
            if MW < 0.5:
                continue
            ann = SITES[s]['U_cost'] * M.crf(M.CFG['social_r'], UPGRADE_LIFE)
            for p in P:
                if p >= q:
                    rows.append(dict(case_id=case_id, scenario=tag, asset_id=nm, component='Link', carrier='POI_upgrade',
                                     asset_boundary='UTILITY_POI', resource_path='public', zone=s, build_period=q, COD=cod, year=p,
                                     capacity_MW=MW, social_annuity_USD_per_MW_yr=ann, resource_capex_PV_USD=ann * MW * ws[p]))
    return pd.DataFrame(rows)


def energy_resid(svc, poil):
    """facility energy - firm POI - own supply - conditional import - curtailment (MWh/yr per scenario x site x year)"""
    k = pd.MultiIndex.from_arrays([svc.scenario, svc.zone, svc.year])
    pl = poil.set_index(['scenario', 'site', 'year'])
    cond = pl.conditional_import_MWh.reindex(k).fillna(0.0).values
    cur = pl.curtailed_MWh.reindex(k).fillna(0.0).values
    intr = pl.interrupt_MWh.reindex(k).fillna(0.0).values if 'interrupt_MWh' in pl else 0.0
    return svc.facility_load_MWh_per_yr - svc.poi_MWh_per_yr - svc.byop_MWh_per_yr - cond - cur - intr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case-id', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--setting', default='G-U', choices=['G-W', 'G-K', 'G-U', 'G-REAL'])
    ap.add_argument('--mainline', action='store_true', help='Mainline v1.3 (8 Epoch buses, G-REAL, joint developer, run gate)')
    ap.add_argument('--config', default='config/config.byop_ercot_mainline.yaml', help='mainline run config with the run authorization')
    ap.add_argument('--stress-days', type=int, default=3); ap.add_argument('--stress-line-derate', type=float, default=1.0)
    ap.add_argument('--case', default='base', choices=['low', 'base', 'high'], help='POI / project parameter case')
    ap.add_argument('--gas-case', default='base', choices=['low', 'base', 'high'])
    ap.add_argument('--relax', nargs='*', default=[], help='S1 attribution relaxations: POI UP RA PROC')
    ap.add_argument('--attribution', action='store_true', help='also run S1_xPOI / S1_xUP / S1_xRA / S1_xPROC / S1_xALL')
    ap.add_argument('--competing', type=float, default=1.0)
    ap.add_argument('--regional-dc', default='off', choices=['off', 'epoch_hybrid'],
                    help='background ERCOT DC growth on TAMU64 buses, RA-DC-SPATIAL-03 (default off)')
    ap.add_argument('--regional-dc-scenario', default='mid', choices=['low', 'mid', 'high'])
    ap.add_argument('--competing-voll', type=float, default=None, help='curtailment price of the competing queued load (default = SHED_COST)')
    ap.add_argument('--s0-calibrate', action='store_true', help='D3 3.5: targeted S0 uplift calibration (S0 only); writes S0_CALIBRATION.csv')
    ap.add_argument('--s0-cal-file', default=None, help='D3 3.5: apply a S0_CALIBRATION.csv as cost-free common baseline assets')
    ap.add_argument('--base-assets', default='main', choices=['main', 'sens', 'none'], help='D3 committed TPIT baseline assets')
    ap.add_argument('--line-lead', type=float, default=None)
    ap.add_argument('--pclr-hours', type=float, default=200.0); ap.add_argument('--pclr-max-consec-h', type=float, default=12.0)
    ap.add_argument('--s2-modes', nargs='*', default=MODES); ap.add_argument('--s2-iter', type=int, default=3)
    ap.add_argument('--start', type=int, default=2026); ap.add_argument('--end', type=int, default=2031)
    ap.add_argument('--sample-weeks', type=int, default=26)
    ap.add_argument('--byop-case', default='base', choices=['low', 'base', 'high'])
    ap.add_argument('--byop-techs', nargs='*', default=['RICE', 'SOFC_NG'])
    ap.add_argument('--tariff', default='energy', choices=['energy', 'energy_erm'])
    ap.add_argument('--reuse', default='on', choices=['off', 'on'])
    ap.add_argument('--erm-cal', default=None); ap.add_argument('--calibrate', action='store_true')
    ap.add_argument('--v', type=float, default=2.8e6); ap.add_argument('--threads', type=int, default=8)
    ap.add_argument('--base', default=None)
    ap.add_argument('--case-group', default=None, help='logical case several parallel sub-runs belong to (default: case-id); '
                    'collect_rearch.py merges sub-runs of one group for attribution / differences')
    ap.add_argument('--scenarios', nargs='*', default=['S0', 'S1_EARLIEST', 'S1_ECON', 'S1_zero', 'S3', 'S3_mS1', 'S2', 'S2_off', 'S3_mS2'])
    ap.add_argument('--interrupt-cap', type=float, default=0.005, help='D2.3 unplanned interruption cap (share of planned annual facility MWh)')
    ap.add_argument('--no-harm', default='on', choices=['on', 'off'], help='D2.4 existing-customer shed <= frozen S0 per bus x snapshot')
    a = ap.parse_args()
    a.case_group = a.case_group or a.case_id
    if a.mainline:      # E1 run gate BEFORE anything is built or solved
        ML.update(on=True, stress_days=a.stress_days, stress_line_derate=a.stress_line_derate)
        ML['gate'] = mainline_gate(a.config)
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / 'RUN_GATE.json').write_text(json.dumps(ML['gate'], indent=1))
        if not ML['gate']['approved']:
            print(json.dumps(dict(RUN_GATE='REFUSED', **ML['gate']), indent=1))
            raise SystemExit(3)
        a.setting, a.competing, a.regional_dc = 'G-REAL', 0.0, 'off'
        if a.byop_techs == ['RICE', 'SOFC_NG']:
            a.byop_techs = list(ML_TECHS)
        if a.scenarios == ['S0', 'S1_EARLIEST', 'S1_ECON', 'S1_zero', 'S3', 'S3_mS1', 'S2', 'S2_off', 'S3_mS2']:
            a.scenarios = ['S0', 'S1_EARLIEST', 'S3', 'S2']
    global BASE_TAMU
    if a.base:
        BASE_TAMU = Path(a.base)
    GCFG.update(regional_dc=a.regional_dc, regional_dc_scenario=a.regional_dc_scenario, competing_voll=a.competing_voll, s0_calibrate=a.s0_calibrate, s0_cal_file=a.s0_cal_file, interrupt_cap=a.interrupt_cap, no_harm=a.no_harm == 'on', base_assets=a.base_assets, setting=a.setting, case=a.case, gas_case=a.gas_case, relax=list(a.relax), competing=a.competing,
                line_lead=a.line_lead, pclr_hours=a.pclr_hours, pclr_max_consec_h=a.pclr_max_consec_h, s2_modes=a.s2_modes,
                s2_iter=a.s2_iter)
    M.CFG.update(periods='annual', start=a.start, end=a.end, cost_basis='repaired', public_subsidy='without', tariff=a.tariff,
                 reuse=a.reuse, reuse_case='base', frac_cod=True, flex=False, poi_lead=0, byop_case=a.byop_case,
                 public_case='base', byop_techs=a.byop_techs, sample_weeks=a.sample_weeks or None, bg_growth=0.0,
                 line_exp=True, erm15=False, threads=a.threads, v=a.v, v_private=None, smoke=False, dem_scale=1.0)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(out / 'rearch_solver.log', 'a', 'utf-8'), logging.StreamHandler()])
    run_id = f'rearch_{a.case_id}_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    # provenance: hash the code AT START (a later edit of the files must not be attributed to this run)
    code_sha_start = {p.name: M.sha(p) for p in [Path(__file__), HERE / 'v240_mech.py', HERE / 'v250_mech.py',
                                                  HERE / 'wp2_ercot_s0_s1.py', HERE / 'wp2_ercot_s1_real.py']}
    configure_mainline(out) if ML['on'] else configure(out)
    M.build = build_rearch
    if ML['on']:
        _solve0 = M.solve
        def _gated_solve(*args_, **kw_):
            _require_gate('M.solve')
            return _solve0(*args_, **kw_)
        M.solve = _gated_solve
    M.extra = extra_rearch
    w2.store_ERM_duals = V.store_erm_duals_tx
    V.GCFG.update(erm_scope='tx')
    w2.PREP = str(BASE_TAMU)
    w2.PUE = pd.read_csv(w2.PUE_CSV)
    config = pypsa.Network(str(BASE_TAMU)).meta
    v = a.v
    events, RES, LED, SVC, SUM, DUA, POIL, UPL = [], {}, [], [], [], [], [], []

    def ev(event, status, msg, **kw):
        events.append(dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), run_id=run_id, case_id=a.case_id,
                           event=event, status=status, message=msg, **kw))
        with open(out / 'events.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(events[-1], ensure_ascii=False, default=str) + '\n')

    if a.calibrate:   # ERM-02 B on the TAMU world: existing + committed fleet only
        n, _ = M.build(config, 'S0', v)
        for c, d in [('Generator', n.generators), ('StorageUnit', n.storage_units), ('Link', n.links)]:
            d.loc[d.index[d.p_nom_extendable], 'p_nom_max'] = 0.0
        STATE['erm_cal'] = 'solve'
        res = M.solve(config, 'ERM02_calibration', out, n)
        mv = n.model.solution['M2-erm_margin'].to_series()
        shed = n.generators_t.p[[c for c in n.generators.index if c.endswith('load_shed')]].mul(n.snapshot_weightings.generators, axis=0).sum().sum()
        cal = dict(decision='ERM-02 B (TAMU)', margin_by_period={int(k): float(x) for k, x in mv.items()}, termination=res['termination'],
                   load_shed_MWh=float(shed), setting=GCFG, cfg={k: M.CFG[k] for k in ['periods', 'start', 'end', 'sample_weeks', 'bg_traj']},
                   baseline_sha256=M.sha(BASE_TAMU), seconds=res['seconds'], n_vars=res['n_vars'])
        (out / 'erm02_calibration.json').write_text(json.dumps(cal, indent=2, default=str))
        ev('erm_calibration', 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL', json.dumps(cal['margin_by_period']))
        print(json.dumps(cal, indent=1, default=str))
        return
    STATE['erm_cal'] = {int(k): float(x) for k, x in json.loads(Path(a.erm_cal).read_text())['margin_by_period'].items()} if a.erm_cal else None
    reuse_on = M.CFG['reuse'] == 'on'
    saved = {}

    def go(tag, relax=None, extra=None, lex=False, strict=False, **kw):
        GCFG['relax'] = list(relax or a.relax)
        STATE['firm_strict'] = strict                   # P0-2: strict Firm base has no unplanned interruption
        STATE['lex'] = dict(tag=tag) if lex else None   # P0-2: lexicographic A1/A2 pre-solve inside extra_rearch
        for s in SITES.values():           # PROC relaxation is a register override
            s['proc'] = M.CFG['decision_year'] if 'PROC' in GCFG['relax'] else s.setdefault('proc0', s['proc'])
        t0 = time.time()
        M.extra = extra or extra_rearch
        n, mult = M.build(config, tag if tag == 'S0' else 'S', v, **kw)
        res = M.solve(config, tag, out, n)
        M.extra = extra_rearch
        if lex:
            (out / f'lex_{tag}.json').write_text(json.dumps(STATE.get('lex_log'), indent=1, default=str))
            res['lex'] = STATE.get('lex_log')
        STATE['firm_strict'] = False; STATE['lex'] = None
        if tag == 'S0' and GCFG.get('s0_calibrate'):
            rows = []
            for b in STATE.get('s0cal_pairs', []):
                f_ = f'{b}_fwd'
                mw = float(n.links.p_nom_opt[f_]) if f_ in n.links.index else 0.0
                ln = b[len('S0CAL_'):]
                rows.append(dict(line=ln, bus0=n.lines.bus0[ln], bus1=n.lines.bus1[ln], existing_MVA=float(n.lines.s_nom[ln]),
                                 s_max_pu=float(n.lines.s_max_pu[ln]), added_MW=mw, evidence_level='B',
                                 derivation=f'S0_{M.periods()[0]}_{M.periods()[-1]}_CALIBRATION (min uplift: {S0CAL_COST:.0e} USD/MW-yr vs shed {S0CAL_SHED:.0e} USD/MWh)'))
            cal = pd.DataFrame(rows)
            cal.to_csv(out / 'S0_CALIBRATION.csv', index=False)
            ev('s0_calibration', 'DONE', f"{int((cal.added_MW > 0.5).sum())} lines, {cal.added_MW.sum():.0f} MW")
        if tag == 'S0':                                  # D2.4: frozen existing-customer shed of the (repaired) S0
            sc0 = n.generators.index[n.generators.carrier == 'load_shed']
            STATE['shed_S0'] = n.generators_t.p[sc0].copy()      # per generator: background shed + competing queue
            STATE['shed_S0'].to_csv(out / 'S0_shed_by_snapshot_frozen.csv.gz')
        for s, d in SITES.items():          # site price columns for the v240 service ledger
            n.buses_t.marginal_price[s] = n.buses_t.marginal_price[d['bus']]
        led, svc, summ = M.ledgers(n, tag, v, a.case_id, run_id)
        upl = upgrade_ledger(n, tag, a.case_id)
        add = float(upl.resource_capex_PV_USD.sum()) if len(upl) else 0.0
        summ['poi_upgrade_resource_capex_PV_USD'] = add
        summ['public_resource_capex_PV_USD'] += add
        summ['social_real_resource_cost_USD'] += add
        summ['social_total_USD'] += add
        ws = {p: M.years_p(p) * M.df(p, M.CFG['social_r']) for p in M.periods()}
        for car, col in (('dc_curtail', 'curtailment_loss_PV_USD'), ('dc_interrupt', 'interruption_loss_PV_USD')):
            cu = n.generators.index[n.generators.carrier == car]
            cl = 0.0
            if len(cu):
                e = n.generators_t.p[cu].mul(n.snapshot_weightings.generators, axis=0).groupby(level=0).sum()
                mc = n.generators.marginal_cost[cu]
                cl = float(sum((e.loc[p] * mc).sum() * ws[p] for p in e.index))
            summ[col] = cl            # PCLR contractual / unplanned interruption: lost compute value, not a resource cost
            summ['social_total_USD'] += cl
        cq = n.generators.index[n.generators.index.str.endswith(' competing_unserved')]
        if len(cq):
            e = n.generators_t.p[cq].mul(n.snapshot_weightings.generators, axis=0).groupby(level=0).sum()
            summ['competing_queue_unserved_MWh'] = float(e.sum().sum())
            summ['competing_queue_loss_PV_USD'] = float(sum(e.loc[p].sum() * (GCFG['competing_voll'] or M.SHED_COST) * ws[p] for p in e.index))
            summ['social_total_USD'] += summ['competing_queue_loss_PV_USD']
        rq = n.generators.index[n.generators.index.str.endswith(' regional_dc_unserved')]
        if len(rq):              # opt-in regional DC background (--regional-dc): reported separately
            summ['regional_dc_unserved_MWh'] = float(n.generators_t.p[rq].mul(n.snapshot_weightings.generators, axis=0).sum().sum())
        summ['existing_customer_shed_loss_PV_USD'] = summ['load_shed_PV_USD']      # D2.5: optimisation penalty basis 1e4 USD/MWh
        summ['existing_customer_shed_loss_VOLL_PV_USD'] = summ['load_shed_PV_USD'] / M.SHED_COST * 35685.0   # Brattle 2024 ERCOT VOLL
        if tag != 'S0' and STATE.get('shed_S0') is not None:
            sc1 = n.generators.index[n.generators.carrier == 'load_shed']
            p1 = n.generators_t.p[sc1]
            diff = p1 - STATE['shed_S0'].reindex(index=p1.index, columns=p1.columns).fillna(0.0)
            summ['no_harm_max_violation_MW'] = float(diff.max().max())
        pl = poi_ledger(n, tag, a.case_id) if tag != 'S0' else pd.DataFrame()
        summ.update(termination=res['termination'], integer_vars=res['integer_vars'], n_vars=res['n_vars'], n_cons=res['n_cons'],
                    solve_seconds=res['seconds'], relax='+'.join(GCFG['relax']) or 'none', setting=GCFG['setting'],
                    curtailed_MWh=float(pl.curtailed_MWh.sum()) if len(pl) else 0.0,
                    poi_upgrade_MW=float(pl.groupby('site').poi_upgrade_MW_cum.max().sum()) if len(pl) else 0.0)
        LED.append(led); SVC.append(svc); SUM.append(summ); RES[tag] = res; POIL.append(pl); UPL.append(upl)
        DUA.append(M.duals(n, tag, a.case_id, run_id))
        # per-scenario checkpoint: a scenario's tables are on disk as soon as it is solved, so a case can be split
        # over parallel processes (--case-group) or survive a later crash without losing finished solves
        ck = out / 'scenarios' / tag
        ck.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([summ]).to_csv(ck / 'scenario_summary.csv', index=False)
        for nm, df_ in (('ledger', led), ('service', svc), ('poi_ledger', pl), ('poi_upgrade_ledger', upl), ('duals', DUA[-1])):
            df_.to_csv(ck / f'{nm}.csv', index=False)
        (ck / 'solve.json').write_text(json.dumps(dict(case_id=a.case_id, case_group=a.case_group, run_id=run_id, scenario=tag,
                                                       relax=GCFG['relax'], setting=GCFG['setting'], solve=res,
                                                       timestamp_utc=datetime.now(timezone.utc).isoformat()), indent=1, default=str))
        pr = n.buses_t.marginal_price[[z for z in M.ZONES]].copy()
        pr.to_csv(out / f'prices_{tag}.csv.gz')
        # D3 diagnostics: background load shed per bus and year (MWh/yr, sampled snapshots weighted to the year)
        sc = n.generators.index[(n.generators.carrier == 'load_shed') & n.generators.index.str.endswith(' load_shed')]
        if len(sc):
            sh = n.generators_t.p[sc].mul(n.snapshot_weightings.generators, axis=0).groupby(level=0).sum()
            sh.columns = [n.generators.bus[c] for c in sh.columns]
            sh = sh.loc[:, sh.sum() > 1e-3].T
            sh.index.name = 'bus'
            sh.to_csv(out / f'shed_by_bus_{tag}.csv')
        ev('optimization_solved', 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL',
           f"obj {res['objective']:.6e}; vars {res['n_vars']}; int {res['integer_vars']}; {time.time() - t0:.0f}s", scenario=tag)
        return n, mult

    byop = M.CFG['byop_techs']
    if 'S0' in a.scenarios:
        go('S0')
    # P0-2: strict physical earliest grid-only base (offers, triggers, attribution) and the economic S1 (control)
    r1e = go('S1_EARLIEST', lex=True, strict=True) if 'S1_EARLIEST' in a.scenarios else None
    if r1e is not None:
        saved['S1E_service'] = {(d['zone'], d['period']): float(r1e[0].generators.p_nom_opt[d['S']]) for d in STATE['dc']}
    r1c = go('S1_ECON') if 'S1_ECON' in a.scenarios else None
    if r1c is not None:
        saved['S1_service'] = {(d['zone'], d['period']): float(r1c[0].generators.p_nom_opt[d['S']]) for d in STATE['dc']}
    r1 = r1e if r1e is not None else r1c
    if r1 is not None:
        n1 = r1[0]
        saved.setdefault('S1_service', saved.get('S1E_service'))
        STATE['reuse_s1'] = [dict(asset_id=e['asset_id'], zone=e['zone'], MW=e['MW'], build_period=e['build_period'],
                                  mc=float(n1.generators.marginal_cost[e['pub']]), eff=float(n1.generators.efficiency[e['pub']]))
                             for e in STATE.get('reuse', [])]
        STATE['triggers'] = select_triggers(n1)
        STATE['offer'], off = s1_offer(n1)
        off.to_csv(out / 'S1_GRID_OFFER.csv', index=False)
        pd.DataFrame([dict(site=s, year=p, n_trigger_snapshots=len(v_), first=str(v_[0]) if v_ else None)
                      for (s, p), v_ in STATE['triggers'].items()]).to_csv(out / 'PCLR_TRIGGERS.csv', index=False)
        n1_keep = n1
    if a.attribution and r1 is not None:   # attribution on the strict earliest base (P0-2)
        for rl in (['POI'], ['UP'], ['RA'], ['PROC'], ['POI', 'UP', 'RA', 'PROC']):
            go('S1E_x' + ('ALL' if len(rl) > 1 else rl[0]), relax=rl, lex=True, strict=True)
    if 'S1_zero' in a.scenarios:
        go('S1_zero', dem_scale=0.0)
    STATE['cond_public'] = {s: True for s in SITES}      # S3 / S2 public: PCLR conditional service allowed
    if 'S3' in a.scenarios:
        go('S3', byop=byop, reuse_dedicated=True)
    if r1 is not None and 'S3_mS1' in a.scenarios:
        go('S3_mS1', byop=byop, reuse_dedicated=True, s_fixed=saved['S1_service'])
    priv_log, consistency = [], []
    if r1 is not None and ({'S2', 'S3_mS2'} & set(a.scenarios)):
        STATE['cond_public'] = {s: True for s in SITES}
        for it in range(1, GCFG['s2_iter'] + 1):
            K, R, rights, plog = (developer_joint if ML['on'] else developer_stage)(config, n1_keep, M.CFG['v_private'] or v, r1[1], reuse_on, it)
            priv_log += plog
            STATE['rights'] = rights
            STATE['cond_public'] = {s: any(rt['cond'] > 1e-3 for (s_, _), rt in rights.items() if s_ == s) for s in SITES}
            STATE['s_upper_only'] = True
            s_dev = {k: rt['S'] for k, rt in rights.items()}
            r2 = go('S2' if it == 1 else f'S2_it{it}', extra=extra_rights, byop=byop, byop_fixed=K, rfixed=R if reuse_on else None, s_fixed=s_dev)
            STATE['s_upper_only'] = False
            STATE['rights'] = None
            n2 = r2[0]
            bad = []
            for d in STATE['dc']:
                sp = float(n2.generators.p_nom_opt[d['S']]); plan = s_dev[(d['zone'], d['period'])]
                consistency.append(dict(iteration=it, site=d['zone'], year=d['period'], planned_IT_MW=plan, public_served_IT_MW=sp,
                                        gap_IT_MW=plan - sp, mode=rights[(d['zone'], d['period'])]['mode'],
                                        right_firm_MW=rights[(d['zone'], d['period'])]['firm'], right_cond_MW=rights[(d['zone'], d['period'])]['cond']))
                if plan - sp > max(0.5, 1e-3 * plan):
                    bad.append(d)
            ev('s2_iteration', 'CONSISTENT' if not bad else 'INCONSISTENT', f'iteration {it}: {len(bad)} site-years below plan')
            if not bad:
                break
            for d in bad:      # re-offer: what the public LP actually delivered through the firm POI
                f = d['firm'][1]
                sl = n2.snapshots.get_level_values(0) == d['period']
                STATE['offer'][(d['zone'], d['period'])]['firm'] = max(0.0, float(n2.links_t.p0[f][sl].max())) if f in n2.links_t.p0 else 0.0
        saved['S2_service'] = {(d['zone'], d['period']): float(n2.generators.p_nom_opt[d['S']]) for d in STATE['dc']}
        saved['K'] = K
        if 'S2_off' in a.scenarios:
            STATE['cond_public'] = {s: False for s in SITES}
            go('S2_off', byop=byop, byop_fixed={k: 0.0 for k in K}, rfixed={k: 0.0 for k in R} if reuse_on else None)
        STATE['cond_public'] = {s: True for s in SITES}
        if 'S3_mS2' in a.scenarios:
            go('S3_mS2', byop=byop, reuse_dedicated=True, s_fixed=saved['S2_service'])
    led = pd.concat(LED, ignore_index=True) if LED else pd.DataFrame()
    svc = pd.concat(SVC, ignore_index=True) if SVC else pd.DataFrame()
    summ = pd.DataFrame(SUM)
    poil = pd.concat(POIL, ignore_index=True) if POIL else pd.DataFrame()
    upl = pd.concat(UPL, ignore_index=True) if UPL else pd.DataFrame()
    led.to_csv(out / 'ledger.csv', index=False); svc.to_csv(out / 'service.csv', index=False)
    summ.to_csv(out / 'scenario_summary.csv', index=False)
    poil.to_csv(out / 'poi_ledger.csv', index=False); upl.to_csv(out / 'poi_upgrade_ledger.csv', index=False)
    pd.DataFrame(priv_log).to_csv(out / 'S2_developer_modes.csv', index=False)
    pd.DataFrame(consistency).to_csv(out / 'S2_consistency.csv', index=False)
    (pd.concat(DUA, ignore_index=True) if DUA else pd.DataFrame()).to_csv(out / 'duals.csv', index=False)
    pd.DataFrame(STATE.get('grid_projects', [])).to_csv(out / 'grid_projects.csv', index=False)
    pd.DataFrame(STATE.get('corridors', [])).to_csv(out / 'corridors.csv', index=False)
    pd.DataFrame([dict(byop_name=k, **v_) for k, v_ in STATE.get('byop_cod', {}).items()]).to_csv(out / 'byop_cod.csv', index=False)
    cs = summ.set_index('scenario') if len(summ) else pd.DataFrame()
    rel = lambda x, y: abs(cs.social_total_USD[x] - cs.social_total_USD[y]) / abs(cs.social_total_USD[y])
    pl1 = poil[poil.scenario == ('S1_EARLIEST' if 'S1_EARLIEST' in set(poil.scenario) else 'S1')] if len(poil) else pd.DataFrame()
    mono = True
    if len(poil):
        for (sc_, s_), g_ in poil.sort_values('year').groupby(['scenario', 'site']):
            dd = g_.served_IT_MW.diff().fillna(0.0) + g_.requested_IT_MW.diff().clip(upper=0).fillna(0.0).abs()
            mono = mono and bool((dd >= -1e-3).all())
    checks = dict(
        true_LP=all(r['integer_vars'] == 0 for r in RES.values()),
        all_optimal=all(r['termination'] == 'optimal' for r in RES.values()),
        S1_zero_equals_S0=bool(rel('S1_zero', 'S0') < 1e-4) if {'S1_zero', 'S0'} <= set(cs.index) else None,
        no_load_shed=bool((summ.load_shed_MWh < 1.0).all()) if len(summ) else None,
        served_le_requested=bool((svc.unserved_MW_IT >= -1e-6).all()) if len(svc) else None,
        dc_energy_balance=bool((energy_resid(svc, poil).abs() <= 1e-3 * svc.facility_load_MWh_per_yr.clip(lower=1.0) + 1.0).all())
        if len(svc) and len(poil) else None,
        S2_off_equals_S1=bool(rel('S2_off', 'S1_ECON') < 1e-4) if {'S2_off', 'S1_ECON'} <= set(cs.index) else
        (bool(rel('S2_off', 'S1') < 1e-4) if {'S2_off', 'S1'} <= set(cs.index) else None),
        online_IT_monotone=mono if len(poil) else None,
        no_harm_existing_customers=bool((summ.get('no_harm_max_violation_MW', pd.Series(dtype=float)).fillna(0.0) <= 0.01).all()) if 'no_harm_max_violation_MW' in summ else None,
        interruption_within_cap=bool((poil.interrupt_MWh <= GCFG['interrupt_cap'] * poil.e_unit * poil.served_IT_MW * (1 + 1e-4) + 1.0).all()) if len(poil) and 'interrupt_MWh' in poil else None,
        lex_presolve_optimal=all(r.get('lex', {}).get('optimal', True) for r in RES.values() if isinstance(r, dict)),
        # simultaneous firm + conditional import (the LP limit is per snapshot; the sum of the two separate peaks is not)
        poi_flow_le_equipment=bool((poil.total_import_peak_MW <= poil.equipment_total_MW * (1 + 1e-5) + 1e-2).all()) if len(poil) else None,
        no_service_before_grid_or_byop=bool(((pl1.served_IT_MW * pl1.PUE) <= pl1.equipment_total_MW + 1e-2).all()) if len(pl1) else None,
        s2_consistent=bool(not consistency or all(c['gap_IT_MW'] <= max(0.5, 1e-3 * c['planned_IT_MW']) for c in consistency if c['iteration'] == max(x['iteration'] for x in consistency))),
        private_stage_LP=all(p_['integer_vars'] == 0 for p_ in priv_log) if priv_log else None)
    man = dict(run_id=run_id, case_id=a.case_id, case_group=a.case_group, gcfg=GCFG, cfg=dict(M.CFG), argv=sys.argv, checks=checks, solves=RES,
               status='CASE_SOLVED' if all(x in (True, None) for x in checks.values()) else 'CASE_CHECK_FAIL',
               sites={k: {kk: vv for kk, vv in s.items()} for k, s in SITES.items()}, erm_cal=STATE.get('erm_cal'),
               baseline=str(BASE_TAMU), baseline_sha256=M.sha(BASE_TAMU),
               inputs_sha256={p.name: M.sha(p) for p in ([POI_REG, POI_REQ, GRID_PROJ, M.TECH, BP.PUE, BP.TASK] + (ML_INPUTS if ML['on'] else []))},
               mainline=dict(gate=ML.get('gate'), stress=STATE.get('stress_sample'), inherited_ramp=STATE.get('inherited_ramp'),
                             gas=STATE.get('gas_repriced')) if ML['on'] else None,
               code_sha256=code_sha_start, code_sha256_basis='hashed at process start',
               interrupt_price={f'{k[0]}|{k[1]}': v_ for k, v_ in STATE.get('interrupt_price', {}).items()},
               s0_calibration=STATE.get('s0cal_applied'), base_assets=STATE.get('base_assets'), grid_projects=STATE.get('grid_projects'), competing=STATE.get('competing'), pypsa=pypsa.__version__,
               timestamp_utc=datetime.now(timezone.utc).isoformat())
    (out / 'case_manifest.json').write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(dict(case=a.case_id, status=man['status'], checks=checks), indent=1, default=str))
    if ML['on']:
        import importlib.util
        spec = importlib.util.spec_from_file_location('collect_mainline', HERE.parent / 'post/collect_mainline.py')
        cm = importlib.util.module_from_spec(spec); spec.loader.exec_module(cm)
        cm.collect(out)
    if len(summ):
        print(summ[[c for c in ['scenario', 'relax', 'social_total_USD', 'social_real_resource_cost_USD', 'served_MW_IT_year', 'delay_MW_IT_year',
                    'load_shed_MWh', 'interruption_loss_PV_USD', 'public_new_MW', 'byop_MW', 'poi_upgrade_MW', 'curtailed_MWh', 'termination',
                    'solve_seconds'] if c in summ]].to_string())


if __name__ == '__main__':
    main()
