"""Post-v1.6 execution package v1.1 (A0 2026-10-22): 1 h continuous stress LP with a 3,000 MW / 1 h operating reserve and the
joint AIDC headroom lambda, built on the frozen v1.6 2025 baseline. This module only BUILDS models (PyPSA / linopy, LP, no
binaries); solving happens exclusively in byop/run/post_v16_a1.py behind byop/model/post_v16_gate.py.

Model (one LP per network mode; mode R = H_resource, mode N = H_network):
  snapshots   6 investment-period blocks x 72 hourly source rows: B0 (lambda = 0) and BL (lambda) for each pre-registered
              window; storage SOC cyclic inside each block (no free energy, no coupling across windows / blocks)
  assets      v1.6 2025 fleet only (extendable / build_year > 2025 removed), every *_nom fixed; switchable monthly caps via
              the v1.6 p_max_pu of the 3 h step containing the source row (dispatch and reserve use the same availability once)
  load        existing: Native Load 2025 1 h by weather zone -> bus (v1.6 builder rule) + the end-2025 inherited AIDC ramp
              (protected existing load); new: h_b = lambda x w_b at the 16 dynamic_pnnl_v1 buses in BL only
  reserve     sum_g r_g + sum_s r_s >= R (3,000 MW) every hour; thermal online-capacity relaxation (c_g):
                p <= c <= p_nom x avail, p >= pmin x c, r <= c - p, r <= rho x c   (rho = min(1 - pmin, ramp x window))
              storage: r <= p_nom - p_dispatch + p_store and tau x r / eff_dispatch <= state_of_charge (the dispatch SOC)
              wind / solar / nuclear / load shed / new AIDC load: no reserve
  objective   minimise eps x dispatch cost + SHED_W x existing-load shed - lambda (lexicographic by weights; see constants)
  networks    N: v1.6 lines, DC power flow (KVL) with the v1.6 limits; R: the same lines, KVL kept, every limit 1e6 MVA
              (connected network -> no binding transfer limit, no isolated bus)
The 15 % snapshot ERM, its shadow storage SOC, ERM-02 B and S0CAL are NOT part of this model (inventory INV-01..05).
"""
from __future__ import annotations

import hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import byop_paths as BP

EPS_COST = 1.0e-5          # dispatch cost weight: 216 h x 200 USD/MWh x eps = 0.43 per MW of lambda < 1 (lambda weight)
SHED_W = 1.0e3             # existing-load shed per MWh >> lambda per MW (one shed MWh can at most free ~1 MW of lambda)
LAMBDA_W = 1.0
COPPER_MVA = 1.0e6
THERMAL = ['CCGT', 'OCGT', 'gas_steam', 'coal', 'biomass']
WZ = ['COAST', 'EAST', 'FWEST', 'NORTH', 'NCENT', 'SOUTH', 'SCENT', 'WEST']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------------------------------------ inputs (no network)
def load_cfg(cfg_path):
    return yaml.safe_load(Path(cfg_path).read_text(encoding='utf-8'))['post_v16']


def windows(cfg):
    ev = pd.read_csv(BP.POST_V16_DERIVED / 'PRE_REGISTERED_STRESS_EVENTS.csv', encoding='utf-8-sig').set_index('event_id')
    out = []
    for w in cfg['windows']:
        e = ev.loc[w['events']]
        a, b = e.window_source_row_start.unique(), e.window_source_row_end.unique()
        assert len(a) == 1 and len(b) == 1, f"{w['id']}: events of one window must share the same 72 h rows"
        rows = list(range(int(a[0]), int(b[0]) + 1))
        assert len(rows) == int(e.window_hours.iloc[0]) == 72
        out.append(dict(id=w['id'], events=list(w['events']), rows=rows, role=w['role']))
    flat = [r for w in out for r in w['rows']]
    assert len(flat) == len(set(flat)), 'windows overlap'
    return out


def weights():
    """16 research buses: cumulative mid IT 2026-2031 x PUE TX 2031 (facility MW) -> w_b; checked against the POI table"""
    c = pd.read_csv(BP.INPUTS / 'dc/MAINLINE_RESEARCH_COHORTS_TAMU64_GEO_DYNAMIC_V1.csv')
    c = c[(c.scenario == 'mid') & c.request_year.between(2026, 2031)]
    pue = pd.read_csv(BP.PUE)
    p31 = float(pue[(pue.st == 'TX') & (pue.year == 2031)].pue.iloc[0])
    it = c.groupby('region_id').IT_MW.sum()
    fac = it * p31
    poi = pd.read_csv(BP.INPUTS / 'poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv').set_index('bus')
    assert np.allclose(fac.reindex(poi.index).values, poi.research_facility_MW_2031_mid.values, atol=1e-3), 'weights != POI table'
    w = pd.DataFrame(dict(IT_MW_2026_2031=it, PUE_TX_2031=p31, facility_MW_2031=fac))
    w['w'] = w.facility_MW_2031 / w.facility_MW_2031.sum()
    assert len(w) == 16 and abs(w.w.sum() - 1) < 1e-12 and (w.w > 0).all()
    return w


def reserve_params(cfg, case='base'):
    t = pd.read_csv(BP.WORKFLOW / cfg['reserve']['parameters'])
    win = float(cfg['reserve']['response_window_min'])
    out = {}
    for car in THERMAL:
        ramp = float(t[(t.parameter == 'ramp_rate') & (t.carrier == car)][case].iloc[0]) / 100.0
        pmin = float(t[(t.parameter == 'min_stable_load') & (t.carrier == car)][case].iloc[0])
        out[car] = dict(pmin=pmin, rho=min(1.0 - pmin, ramp * win), ramp_pct_min=ramp * 100, window_min=win)
    out['hydro'] = dict(pmin=0.0, rho=1.0, ramp_pct_min=None, window_min=win)
    return out


def bus_split(shares_csv):
    sh = pd.read_csv(shares_csv, dtype={'GEOID': str})
    split = sh.assign(w=sh.lpf * sh.share).groupby(['wz', 'cluster_bus']).w.sum()
    return split / split.groupby(level=0).transform('sum')


def hourly_bus_load(rows, shares_csv):
    """existing load by bus for the given 0-based source rows (v1.6 builder rule on the tracked 1 h weather-zone table)"""
    d = pd.read_csv(BP.POST_V16_DERIVED / 'ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv', encoding='utf-8-sig').set_index('source_row_0based')
    d = d.loc[rows]
    split = bus_split(shares_csv)
    buses = sorted(set(split.index.get_level_values(1)))
    L = pd.DataFrame(0.0, index=rows, columns=buses)
    for (wz, b), s in split.items():
        L[b] += d[f'load_{wz}_MW'].values * s
    assert np.allclose(L.sum(axis=1).values, d.native_load_MW.values, rtol=1e-9), 'bus load != native load'
    return L, d


def inherited_ramp():
    r = pd.read_csv(BP.INPUTS / 'dc/MAINLINE_INHERITED_RAMP_2025.csv')
    pue = pd.read_csv(BP.PUE)
    p25 = float(pue[(pue.st == 'TX') & (pue.year == 2025)].pue.iloc[0])
    return pd.Series(r.inherited_ramp_IT_MW.values * p25, index=r.bus.values), p25, float(r.inherited_ramp_IT_MW.sum())


def stress_vintage_qa(cfg, wins):
    """STRESS_SOURCE_VINTAGE_QA content: per hour source row / HE / DST / date / model 3 h step; units and source vintage"""
    d = pd.read_csv(BP.POST_V16_DERIVED / 'ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv', encoding='utf-8-sig').set_index('source_row_0based')
    rows = []
    for w in wins:
        x = d.loc[w['rows']]
        rows.append(dict(window=w['id'], events=w['events'], role=w['role'], source_rows=[w['rows'][0], w['rows'][-1]], hours=len(x),
                         first_HE=str(x.source_HE_label.iloc[0]), last_HE=str(x.source_HE_label.iloc[-1]),
                         dates=sorted(set(x.date)), dst_extra_hours=int(x.source_extra_dst_hour.astype(str).eq('True').sum()),
                         hour_ending_contiguous=bool((np.diff(x.index.values) == 1).all()),
                         model_3h_steps=[int(w['rows'][0] // 3), int(w['rows'][-1] // 3)],
                         native_load_peak_MW=float(x.native_load_MW.max()), native_load_MWh=float(x.native_load_MW.sum()),
                         observed_wind_MWh=float(x.wind_actual_MW.sum()), observed_solar_MWh=float(x.solar_actual_MW.sum())))
    return dict(windows=rows, solver_calls=0,
                load=dict(source='derived/ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv (Native Load 2025, 8 weather zones; = ERCOT Native_Load_2025.xlsx)',
                          unit='MW hourly average (= MWh per hour)', regional_split='weather zone -> bus: v1.6 COUNTY_TO_BUS_SHARES (lpf x substation share)',
                          demand_concept='ERCOT native load (actual 2025), not CDR firm load'),
                renewables=dict(model_input='v1.6 network p_max_pu (PyPSA-USA profiles) of the 3 h step containing each source row, held for 3 h',
                                observed_output='derived settlement wind / solar = ACTUAL OUTPUT incl. curtailment, used only for QA and event choice, NOT as p_max_pu',
                                same_weather_year=False, note='model profiles are not the 2025 weather; load and renewables are a cross-year stress combination'),
                time=dict(label='ERCOT source HE labels (Central prevailing time as published); no UTC conversion claimed; no DST hour fabricated',
                          resampling='none (1 h source rows); the 3 h step index is only used to pick p_max_pu',
                          model_snapshot='period = block x window (1..6), timestep = source date + HE hours (label only)'),
                thermal_availability='v1.6 template p_max_pu; MORA outage quantiles NOT applied (ex-ante marginals, not joint; not authorised)',
                power_energy_units='MW for power, MWh for energy, 1 h snapshots, weight 1')


# ------------------------------------------------------------------------------------------------ network
def snapshot_index(wins):
    per, ts, rows, block = [], [], [], []
    d = pd.read_csv(BP.POST_V16_DERIVED / 'ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv', encoding='utf-8-sig',
                    usecols=['source_row_0based', 'date', 'hour_ending']).set_index('source_row_0based')
    k = 0
    for blk in ('B0', 'BL'):
        for w in wins:
            k += 1
            for r in w['rows']:
                per.append(k); rows.append(r); block.append(blk)
                ts.append(pd.Timestamp(d.date[r]) + pd.Timedelta(hours=int(d.hour_ending[r])))
    mi = pd.MultiIndex.from_arrays([per, pd.DatetimeIndex(ts)], names=['period', 'timestep'])
    meta = pd.DataFrame(dict(period=per, block=block, source_row=rows, step3h=[r // 3 for r in rows]), index=mi)
    return mi, meta


def fix_fleet(n):
    """v1.6 2025 fleet only, every *_nom fixed, no links / global constraints, timeless assets"""
    g = n.generators
    n.remove('Generator', g.index[g.p_nom_extendable | (g.build_year > 2025)])
    s = n.storage_units
    n.remove('StorageUnit', s.index[s.p_nom_extendable | (s.build_year > 2025)])
    if len(n.links):
        n.remove('Link', n.links.index)
    if len(n.global_constraints):
        n.remove('GlobalConstraint', n.global_constraints.index)


def retime(n, mi, meta):
    """hourly blocks: every time series of the v1.6 network taken at the 3 h step that contains the source row"""
    dyn = {}
    for lst in ('generators', 'storage_units', 'lines'):
        for attr, df in getattr(n, lst + '_t').items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                dyn[(lst, attr)] = df.copy()
    n.remove('Load', n.loads.index)
    n.set_snapshots(mi)
    n.investment_periods = sorted(set(meta.period))
    n.snapshot_weightings.loc[:, :] = 1.0
    n.investment_period_weightings.loc[:, 'years'] = 1.0
    n.investment_period_weightings.loc[:, 'objective'] = 1.0
    for df in (n.generators, n.storage_units, n.lines):
        df['build_year'] = 0; df['lifetime'] = np.inf
    k3 = meta.step3h.values
    for (lst, attr), df in dyn.items():
        getattr(n, lst + '_t')[attr] = pd.DataFrame(df.values[k3], index=mi, columns=df.columns)


def apply_costs_and_storage(n):
    """eps-scaled dispatch costs (static and time-varying); storage cyclic inside every block"""
    n.generators['marginal_cost'] = n.generators.marginal_cost * EPS_COST
    if 'marginal_cost' in n.generators_t and not n.generators_t.marginal_cost.empty:
        n.generators_t.marginal_cost = n.generators_t.marginal_cost * EPS_COST
    n.storage_units['marginal_cost'] = 0.0
    n.storage_units['cyclic_state_of_charge'] = True
    n.storage_units['cyclic_state_of_charge_per_period'] = True


def add_loads(n, meta, Lt, ramp, w, lam_up):
    """existing load + inherited ramp (both blocks), shed per load bus (SHED_W), new AIDC load generators (0 in B0)"""
    mi = n.snapshots
    for b in Lt.columns:
        n.add('Load', f'{b} existing 2025', bus=b, p_set=Lt[b], carrier='AC')
    for b, mw in ramp.items():
        n.add('Load', f'{b} inherited_ramp', bus=b, p_set=pd.Series(mw, index=mi), carrier='AC')
    for car in ('load_shed', 'aidc_new'):
        if car not in n.carriers.index:
            n.add('Carrier', car)
    lb = sorted(set(n.loads.bus))
    n.add('Generator', [f'{b} PV16 existing shed' for b in lb], bus=lb, carrier='load_shed', p_nom=1e5, marginal_cost=SHED_W)
    is_bl = (meta.block == 'BL').values
    for b, r in w.iterrows():
        n.add('Generator', f'{b} PV16 new AIDC load', bus=b, carrier='aidc_new', p_nom=lam_up * r.w + 1.0, marginal_cost=0.0,
              p_min_pu=pd.Series(np.where(is_bl, -1.0, 0.0), index=mi), p_max_pu=pd.Series(0.0, index=mi))


def apply_mode(n, mode):
    """R: every line limit lifted to COPPER_MVA (lines and KVL kept: the network stays one connected component); N: v1.6"""
    assert mode in ('R', 'N')
    if mode == 'R':
        n.lines['s_nom'] = COPPER_MVA
        n.lines['s_max_pu'] = 1.0
        if 's_max_pu' in n.lines_t:
            n.lines_t.s_max_pu = n.lines_t.s_max_pu.iloc[:, :0]


def build_network(cfg, mode, base_path, shares_csv, case='base'):
    """mode 'R' (H_resource) or 'N' (H_network); returns (network, info). No solver."""
    import pypsa
    assert mode in ('R', 'N')
    n = pypsa.Network(str(base_path))
    fix_fleet(n)
    wins = windows(cfg)
    mi, meta = snapshot_index(wins)
    retime(n, mi, meta)
    apply_costs_and_storage(n)
    rows = [r for w in wins for r in w['rows']]
    L, _ = hourly_bus_load(rows, shares_csv)
    Lt = pd.DataFrame(L.loc[meta.source_row.values].values, index=mi, columns=L.columns)
    ramp, p25, ramp_it = inherited_ramp()
    w = weights()
    add_loads(n, meta, Lt, ramp, w, float(cfg['headroom']['lambda_upper_MW']))
    s_nom_v16 = n.lines.s_nom.copy()
    apply_mode(n, mode)
    info = dict(mode=mode, base=str(base_path), base_sha256=sha(base_path), windows=wins, snapshots=len(mi), blocks=6,
                weights=w.reset_index().rename(columns={'index': 'bus', 'region_id': 'bus'}).to_dict(orient='records'),
                inherited_ramp_facility_MW=float(ramp.sum()), inherited_ramp_IT_MW=ramp_it, pue_tx_2025=p25,
                existing_load_peak_MW=float(Lt.sum(axis=1).max()), line_limits='copperplate 1e6 MVA, KVL kept' if mode == 'R' else 'v1.6 s_nom x s_max_pu',
                s_nom_v16_total=float(s_nom_v16.sum()), reserve=reserve_params(cfg, case), meta=meta)
    return n, info


def add_headroom(n, cfg, info):
    """lambda, new-load equalities and the reserve rows on n.model (created by n.optimize.create_model)"""
    import xarray as xr
    m = n.model
    meta = info['meta']
    sns = n.snapshots
    w = pd.DataFrame(info['weights']).set_index('bus').w
    lam = m.add_variables(lower=0.0, upper=float(cfg['headroom']['lambda_upper_MW']), name='PV16-lambda')
    newg = [f'{b} PV16 new AIDC load' for b in w.index]
    bl = sns[(meta.block == 'BL').values]
    wda = xr.DataArray(w.values, coords={'name': newg}, dims='name')
    m.add_constraints(m['Generator-p'].sel(name=newg, snapshot=bl) + lam * wda == 0, name='PV16-newload')
    g = n.generators
    rp = info['reserve']
    E = [x for x in g.index if g.carrier[x] in rp]
    avail = n.get_switchable_as_dense('Generator', 'p_max_pu', inds=E) * g.p_nom[E]
    avail.index.name = 'snapshot'; avail.columns.name = 'name'
    pmin = xr.DataArray([rp[g.carrier[x]]['pmin'] for x in E], coords={'name': E}, dims='name')
    rho = xr.DataArray([rp[g.carrier[x]]['rho'] for x in E], coords={'name': E}, dims='name')
    c = m.add_variables(lower=0.0, upper=xr.DataArray(avail), name='PV16-online_cap')
    r = m.add_variables(lower=0.0, name='PV16-res_thermal', coords=c.coords)
    pg = m['Generator-p'].sel(name=E)
    m.add_constraints(pg - c <= 0, name='PV16-online_max_p')
    m.add_constraints(pg - pmin * c >= 0, name='PV16-online_min')
    m.add_constraints(r + pg - c <= 0, name='PV16-res_thermal_head')
    m.add_constraints(r - rho * c <= 0, name='PV16-res_ramp')
    su = n.storage_units
    S = list(su.index)
    tau = float(cfg['reserve']['tau_h'])
    total = r.sum('name')
    if S:
        pnom = xr.DataArray(su.p_nom[S].values, coords={'name': S}, dims='name')
        effd = xr.DataArray(su.efficiency_dispatch[S].values, coords={'name': S}, dims='name')
        rs = m.add_variables(lower=0.0, name='PV16-res_su', coords=m['StorageUnit-p_dispatch'].sel(name=S).coords)
        m.add_constraints(rs + m['StorageUnit-p_dispatch'].sel(name=S) - m['StorageUnit-p_store'].sel(name=S) <= pnom, name='PV16-res_su_power')
        m.add_constraints(rs * (tau / effd) - m['StorageUnit-state_of_charge'].sel(name=S) <= 0, name='PV16-res_su_energy')
        total = total + rs.sum('name')
    m.add_constraints(total >= float(cfg['reserve']['requirement_MW']), name='PV16-reserve_req')
    m.objective = m.objective.expression - LAMBDA_W * lam
    return dict(eligible_thermal=len(E), eligible_thermal_MW=float(g.p_nom[E].sum()), storage=len(S), storage_MW=float(su.p_nom[S].sum()))


def structural_checks(n, info):
    """no-solver checks of the created model; returns dict (asserts the hard ones)"""
    import networkx as nx
    m = n.model
    names = list(m.variables)
    bad = [v for v in names if v.endswith(('-p_nom', '-s_nom', '-e_nom')) or v.endswith('_RESERVES')]
    assert not bad, f'build / shadow variables present: {bad}'
    erm = [c for c in m.constraints if 'ERM' in c]
    assert not erm, f'old ERM rows present: {erm}'
    G = nx.Graph(); G.add_nodes_from(n.buses.index); G.add_edges_from(zip(n.lines.bus0, n.lines.bus1))
    comps = nx.number_connected_components(G)
    assert comps == 1, f'network has {comps} components (isolated buses)'
    meta = info['meta']
    newg = [x for x in n.generators.index if n.generators.carrier[x] == 'aidc_new']
    pmin = n.get_switchable_as_dense('Generator', 'p_min_pu', inds=newg)
    assert (pmin[(meta.block == 'B0').values] == 0).all().all(), 'new AIDC load not fixed to 0 in B0'
    c = m.constraints['PV16-newload']
    lam_label = int(m['PV16-lambda'].labels.values)
    co = c.lhs.coeffs.values; vv = c.lhs.vars.values
    lam_coef = sorted(set(np.round(co[vv == lam_label], 12)))
    w = sorted(np.round(pd.DataFrame(info['weights']).w.values, 12))
    assert lam_coef == sorted(set(w)), 'lambda coefficients != weights'
    soc_lab = set(m['StorageUnit-state_of_charge'].labels.values.ravel())
    e = m.constraints['PV16-res_su_energy'].lhs
    soc_in_res = set(e.vars.values.ravel()) - {-1} - set(m['PV16-res_su'].labels.values.ravel())
    assert soc_in_res <= soc_lab and soc_in_res, 'storage reserve energy row does not use the dispatch SOC'
    if info['mode'] == 'R':
        assert (n.lines.s_nom == COPPER_MVA).all()
    return dict(variables=names, constraints=sorted(m.constraints), n_vars=int(m.nvars), n_cons=int(m.ncons),
                components=comps, buses=len(n.buses), lines=len(n.lines), generators=len(n.generators), storage_units=len(n.storage_units),
                snapshots=len(n.snapshots), lambda_coefficients=len(lam_coef), integer_vars=int(len(m.binaries) + len(m.integers)))


# ------------------------------------------------------------------------------------------------ POI ledger (no LP)
def poi_ledger(years=range(2026, 2032), case='base', decision_year=2026):
    """H_POI book: per bus x year, firm-eligible equipment (E0 pre-approved / all E0 rows), + POI upgrade (earliest COD
    max(decision_year + lead, procedural COD)), conditional PCLR (never firm); lambda_POI = min_b cap_b / w_b"""
    w = weights().w
    poi = pd.read_csv(BP.INPUTS / 'poi/GREAL_POI_ASSUMPTIONS_GEO_DYNAMIC_V1.csv').set_index('bus')
    e0 = pd.read_csv(BP.INPUTS / 'poi/GREAL_POI_E0_SCHEDULE.csv')
    rows = []
    for b in w.index:
        p = poi.loc[b]
        proc = float(p[f'earliest_grid_COD_{case}'])
        up_cod = max(decision_year + float(p[f'poi_upgrade_lead_y_{case}']), proc)
        pclr_cod = proc + float(p.pclr_conditional_COD_offset_y)
        e = e0[e0.bus == b]
        for y in years:
            cod_eff = [(x.MW, x.COD if bool(x.preapproved) else max(x.COD, proc), bool(x.preapproved)) for x in e.itertuples()]
            firm_pre = sum(mw for mw, cd, pre in cod_eff if pre and cd <= y)
            firm_all = sum(mw for mw, cd, pre in cod_eff if cd <= y)
            up = float(p.poi_upgrade_max_MW) if up_cod <= y else 0.0
            cond = float(p.pclr_conditional_MW) if pclr_cod <= y else 0.0
            rows.append(dict(bus=b, year=y, w_b=float(w[b]), E0_firm_preapproved_MW=firm_pre, E0_firm_all_rows_MW=firm_all,
                             upgrade_MW=up, upgrade_earliest_COD=up_cod, firm_with_upgrade_MW=firm_all + up,
                             conditional_PCLR_MW=cond, conditional_COD=pclr_cod, procedural_COD=proc,
                             note='conditional is never firm; upgrade = eligible future delivery, not existing qualification'))
    L = pd.DataFrame(rows)
    lam = []
    for y, grp in L.groupby('year'):
        for col in ('E0_firm_preapproved_MW', 'E0_firm_all_rows_MW', 'firm_with_upgrade_MW'):
            ratio = grp[col] / grp.w_b
            k = ratio.idxmin()
            lam.append(dict(year=y, book=col, lambda_POI_facility_MW=float(ratio.min()), binding_bus=grp.bus[k],
                            zero_buses=int((grp[col] <= 0).sum()),
                            validity='only if the POI rights are independent fixed caps and the network is unchanged'))
    return L, pd.DataFrame(lam)
