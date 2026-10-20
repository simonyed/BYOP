#!/usr/bin/env python3
"""v2.5.0 ERCOT County / Grid-Connection-and-Expansion (GCE) / gas-gate layer on top of the v2.4.0 static S0-S3 LP.

Reuses v240_mech (same DC cohorts, PUE, task model, BYOP N/R/F equations, ERM-02 B, two-book ledgers, S2/S3 logic) and
changes ONLY (doc ERCOT_Grid_Bottlenecks v0.3 sec.10, P0F F4):
  topology   CNY-01/02  county ReEDS/NARIS transport network, 2025 county baseline (build_2025_baseline_county.py);
                        DC cohorts re-split to county buses (D250-05); POI = county_proxy_poi (no invented K_POI)
  --grid     CNY-04/7.2 G-C  committed only: existing NARIS county ITLs + verified TPIT increments (none pass the five
                             gates on 2026-10-20, D250-09) -> no ITL expansion
                        G-R  realistic (main): continuous reinforcement only on TPIT-eligible county corridors (a live
                             Future/Planned TPIT line/reconductor record between the two counties, D250-12), lead from
                             TPIT (D250-06: 3/4/5 y), cap = 100 % of existing corridor (LINE-01 bound kept, labelled)
                        G-RA realistic-all: as G-R on every NARIS corridor (= LINE-01 legacy rule, sensitivity)
                        G-I  instant: G-RA with lead 0 (non-physical upper bound; only speed differs)
  --gas-gate P0F F4     evidence  EVIDENCE_ONLY: new gas-fired BYOP (RICE/SOFC_NG/OCGT_aero/CCGT) needs a verified firm
                                  gas right at the site; none exists for any DC county (firm MDQ null) -> gate CLOSED,
                                  reported as closed-for-evidence, not as MDQ = 0. R (existing gas units) stays open.
                        contract  EXPLICIT_CONTRACTABILITY_SENSITIVITY: gas assumed contractable within the BYOP lead
                                  time (labelled assumption = v2.4.0 behaviour)
  --s2-rule  D-01       sf  S2-SF: developer stage is lexicographic: maximise served IT year by year (earliest first),
                            fix each year, then minimise private cost (sequential LPs, no big-M / penalty weights)
                        v   S2-v: v2.4.0 penalty rule (delay loss v in the private objective)
Run (L2, from pypsa-usa/workflow with the venv):
    python byop/model/v250_mech.py --case-id X --out results/BYOP/<case> [v240 options] --grid G-R ...
"""
from __future__ import annotations

import json, math, sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

HERE = Path(__file__).resolve().parent
V240 = HERE                     # restructure 2026-10-20: all model modules in pypsa-usa/workflow/byop/model
sys.path.insert(0, str(V240))
import v240_mech as M  # noqa: E402

w2, s1r = M.w2, M.s1r
import byop_paths as BP  # noqa: E402
BASE_COUNTY = BP.BASE_COUNTY
COHORTS_COUNTY = BP.COHORTS_COUNTY
TPIT_MAP = BP.TPIT_MAP
DC_COUNTIES = ['p48029', 'p48113', 'p48121', 'p48453']      # Bexar, Dallas, Denton, Travis (D250-05)
COUNTY_NAME = {'p48029': 'Bexar', 'p48113': 'Dallas', 'p48121': 'Denton', 'p48453': 'Travis'}
GAS_FIRED = {'RICE', 'SOFC_NG', 'OCGT_aero', 'CCGT'}
LINE_LEADS_TPIT = {'low': 3, 'base': 4, 'high': 5}          # D250-06
# P0E v0.9 firm-gas status per DC county: no verified firm MDQ / delivery point / transport right anywhere (the P0E
# five-county register is all null; the four DC counties were not surveyed) -> None = unknown, never 0 or unbounded.
FIRM_MDQ = {c: None for c in DC_COUNTIES}
GCFG = dict(grid='G-R', gas_gate='contract', s2_rule='sf', erm_scope='tx')
GSTATE = {}


def configure():
    """point the v2.4.0 module at the county world (module globals are read at call time)"""
    n0 = pypsa.Network(str(BASE_COUNTY))
    zones = sorted(b for b in n0.buses.index if str(b).startswith('p48') and len(str(b)) == 6)
    M.BASE = BASE_COUNTY
    M.ZONES = zones
    M.DC_ZONES = list(DC_COUNTIES)
    M.ZONE_STATE = {z: 'TX' for z in zones}
    M.LINE_LEADS = dict(LINE_LEADS_TPIT)
    w2.EXCLUDE_ZONES = []
    s1r.COHORTS = COHORTS_COUNTY
    GSTATE['zones'] = zones
    return n0


def tpit_corridors():
    """county pairs with a live (Future/Planned, not cancelled/completed) TPIT line or reconductor record"""
    a = pd.read_csv(TPIT_MAP)
    a = a[a.asset_type.isin(['new_line', 'reconductor']) & a.source_category.isin(['Future', 'Planned'])
          & a.county_from_fips.notna() & a.county_to_fips.notna() & (a.county_from_fips != a.county_to_fips)]
    pairs = {}
    for r in a.itertuples():
        k = tuple(sorted([r.county_from_fips, r.county_to_fips]))
        pairs.setdefault(k, []).append(str(r.project_id))
    return pairs


def add_public_candidates_bulk(n, templ_g, templ_s, prof):
    """v240 add_public_candidates with identical names / parameters, but added in one n.add call per component
    (185 counties x 6 techs x 6 periods: one-by-one inserts fragment the time-series frames and take tens of minutes)"""
    t = M.tech().set_index(['carrier', 'boundary'])
    offered, costrows, G, S, PMAX = [], [], [], [], {}
    P = M.periods()
    for z in M.ZONES:
        for car, (tc, comp) in M.PUBLIC.items():
            row = t.loc[(tc, 'UTILITY' if comp == 'Generator' else 'UTILITY_AND_DC_BTM')]
            lead = float(row[f"lead_years_{M.CFG['public_case']}"])
            p0 = M.first_period(M.CFG['decision_year'] + lead)
            tg = templ_g if comp == 'Generator' else templ_s
            cand = tg[(tg.bus == z) & (tg.carrier == car)]
            for _, t0 in cand.iterrows():
                mc_net = (float(row.heat_rate_Btu_kWh) / 1000 * M.GAS + float(row.variable_USD_MWh)) if car in ('CCGT', 'OCGT') \
                    else float(t0.marginal_cost)
                pc = M.public_costs(car, float(t0.capital_cost), float(t0.lifetime), mc_net)
                for p in P:
                    if p0 is None or p < p0:
                        continue
                    name = f'{z} {car} pub{p}' if len(cand) == 1 else f'{t0.name} pub{p}'
                    cc = pc['cc_dec'] * M.tv_factor(p, float(t0.lifetime), 'public')
                    if comp == 'Generator':
                        d = dict(name=name, bus=z, carrier=car, p_nom=0.0, p_nom_extendable=True, p_nom_max=float(t0.p_nom_max),
                                 capital_cost=cc, marginal_cost=pc['mc_dec'], build_year=p, lifetime=float(t0.lifetime),
                                 efficiency=float(row.efficiency) if car in ('CCGT', 'OCGT') else 1.0,   # v240: PyPSA defaults
                                 p_max_pu=1.0)
                        G.append(d)
                        if t0.name in prof:
                            PMAX[name] = M.tile(prof[t0.name])
                    else:
                        S.append(dict(name=name, bus=z, carrier=car, p_nom=0.0, p_nom_extendable=True, capital_cost=cc,
                                      max_hours=float(t0.max_hours), efficiency_store=float(t0.efficiency_store),
                                      efficiency_dispatch=float(t0.efficiency_dispatch), cyclic_state_of_charge=True,
                                      build_year=p, lifetime=float(t0.lifetime), marginal_cost=float(t0.marginal_cost)))
                    offered.append(dict(zone=z, carrier=car, period=p, first_period=p0, lead=lead,
                                        earliest_COD=M.CFG['decision_year'] + lead))
                    costrows.append(dict(name=name, component=comp, zone=z, carrier=car, build_year=p,
                                         life=float(t0.lifetime), **pc))
    if G:
        g = pd.DataFrame(G).set_index('name')
        n.add('Generator', g.index, **{c: g[c].values for c in g.columns})
        if PMAX:
            pm = pd.DataFrame(PMAX, index=n.snapshots)
            n.generators_t.p_max_pu = pd.concat([n.generators_t.p_max_pu, pm], axis=1)
    if S:
        s = pd.DataFrame(S).set_index('name')
        n.add('StorageUnit', s.index, **{c: s[c].values for c in s.columns})
    M.STATE['public_cost_table'] = pd.DataFrame(costrows)
    return offered


def add_line_expansion_gce(n):
    """CNY-04 replacement of v240 add_line_expansion (same Link pair + symmetry + cap constraints in M.extra)"""
    grid = GCFG['grid']
    if grid == 'G-C':
        M.STATE['corridors'] = []
        GSTATE['corridor_audit'] = dict(grid=grid, eligible=0, rule='no verified TPIT increment (D250-09); no generic expansion')
        return []
    lead = 0 if grid == 'G-I' else M.LINE_LEADS[M.CFG['public_case']]
    p0 = M.first_period(M.CFG['decision_year'] + lead)
    pairs = tpit_corridors() if grid == 'G-R' else None
    corridors, skipped, L = [], 0, []
    fwd = n.links[(n.links.carrier == 'AC') & n.links.index.str.endswith('_fwd')]
    for name, l in fwd.iterrows():
        key = tuple(sorted([l.bus0, l.bus1]))
        if pairs is not None and key not in pairs:
            skipped += 1
            continue
        rev = name.replace('_fwd', '_rev')
        cap = 0.5 * (float(l.p_nom) + float(n.links.p_nom.get(rev, l.p_nom)))
        if not M.CFG['line_exp']:
            cap = 0.0
        base = name[:-4]
        for p in M.periods():
            if p0 is None or p < p0:
                continue
            for suf, b0, b1, cc in (('fwd', l.bus0, l.bus1, float(l.capital_cost)), ('rev', l.bus1, l.bus0, 0.0)):
                L.append(dict(name=f'{base}_exp{p}_{suf}', bus0=b0, bus1=b1, carrier='AC_exp', p_nom=0.0, p_nom_extendable=True,
                              p_nom_max=cap, capital_cost=cc, efficiency=float(l.efficiency), build_year=p, lifetime=60,
                              length=float(l.length)))
        corridors.append(dict(corridor=base, cap_MW=cap, capital_cost_per_MW_yr=float(l.capital_cost), first_period=p0,
                              bus0=l.bus0, bus1=l.bus1, existing_MW=float(l.p_nom),
                              tpit_projects='|'.join(pairs[key]) if pairs is not None else 'ALL_CORRIDORS_SENSITIVITY'))
    if L:
        x = pd.DataFrame(L).set_index('name')
        n.add('Link', x.index, **{c: x[c].values for c in x.columns})
    if 'AC_exp' not in n.carriers.index:
        n.add('Carrier', 'AC_exp', co2_emissions=0.0)
    M.STATE['corridors'] = corridors
    GSTATE['corridor_audit'] = dict(grid=grid, lead_years=lead, first_period=p0, eligible=len(corridors), not_eligible=skipped,
                                    eligible_existing_MW=round(sum(c['existing_MW'] for c in corridors), 1))
    return corridors


def gas_gate(n):
    """P0F F4 gate matrix: close new gas-fired BYOP at sites without verified firm gas rights (evidence mode)"""
    rows = []
    g = n.generators
    for c in DC_COUNTIES:
        for car in M.CFG['byop_techs']:
            names = g.index[(g.carrier == f'byop_{car}') & (g.bus == f'DC_{c}')]
            gas = car in GAS_FIRED
            open_ = (not gas) or GCFG['gas_gate'] == 'contract' or FIRM_MDQ[c] is not None
            if not open_:
                ext = [x for x in names if g.p_nom_extendable[x]]
                n.generators.loc[ext, 'p_nom_max'] = 0.0
            rows.append(dict(county=c, county_name=COUNTY_NAME[c], tech=car, gas_fired=gas, gate_mode=GCFG['gas_gate'],
                             firm_mdq_mmbtu_day=FIRM_MDQ[c], firm_transport_right_verified=FIRM_MDQ[c] is not None,
                             gas_lateral_meter_verified=False, air_permit_gate='TECH-01 lead (generic site, no permit record)',
                             power_poi_gate='county_proxy_poi (K_POI unknown, not bounded)',
                             status='OPEN' if open_ else 'CLOSED_EVIDENCE_MISSING',
                             assumption='EXPLICIT_CONTRACTABILITY_SENSITIVITY' if (gas and GCFG['gas_gate'] == 'contract') else
                             ('EVIDENCE_ONLY' if gas else 'NOT_GAS'), n_assets=len(names)))
    GSTATE['gas_gate'] = rows
    return rows


_extra_v240 = M.extra


def extra_gce(n, snapshots):
    """v240 extra (ERM-DC-01 B, load-shed fix, ERM-02 B calibration, DC / FLEX / R / line constraints), then D250-15:
    --erm-scope tx sums the upstream nodal ERM rows (reserve balance per county bus with reserve flows bounded by ITLs)
    into ONE TX row per snapshot (doc CNY-03: keep the unified TX adequacy assessment; county deliverability is carried
    by the ITL-constrained energy balance). Reserve flow terms cancel up to link losses."""
    _extra_v240(n, snapshots)
    if GCFG.get('erm_scope', 'tx') != 'tx' or not M.STATE.get('erm'):
        return
    m = n.model
    name = 'GlobalConstraint-TX_ERM'
    if name not in m.constraints:
        return
    c = m.constraints[name]
    lhs, rhs, mask = c.lhs, c.rhs, c.mask
    if mask is not None:
        lhs = lhs.where(mask); rhs = rhs.where(mask, 0.0)
    L, R = lhs.sum('Bus'), rhs.sum('Bus')
    m.remove_constraints(name)
    m.add_constraints(L, '>=', R, name=name)
    pois = list(w2.DC_ERM.get('pois', []))
    chk = None
    if pois:   # structural check (replaces the per-bus check in w2.solve): POI flow enters the TX row with -(1+erm)
        lab = int(m['Link-p'].sel(name=pois[0][0]).labels.values.ravel()[0])
        row = m.constraints[name].lhs.isel(snapshot=0)
        co = row.coeffs.values[row.vars.values == lab]
        chk = float(co.sum()) if co.size else 0.0
    GSTATE['erm_tx'] = dict(scope='tx', n_bus_rows_summed=int(c.rhs.sizes.get('Bus', 0)), poi_coeff_snapshot0=chk)
    w2.DC_ERM['pois'] = []          # w2.solve's per-bus coefficient check does not apply to the aggregated row


def store_erm_duals_tx(n):
    """dual of the single TX ERM row per snapshot, broadcast to every TX bus (same layout as upstream erm_price)"""
    m = n.model
    if 'GlobalConstraint-TX_ERM' not in m.constraints:
        return
    d = m.dual['GlobalConstraint-TX_ERM']
    if 'Bus' in d.dims:
        return _store_up(n)
    s = d.to_series()
    s.index = n.snapshots
    buses = [b for b in n.buses.index if b in M.ZONES]
    n.buses_t['erm_price'] = pd.DataFrame({b: s.values for b in buses}, index=n.snapshots)


_store_up = w2.store_ERM_duals
_build_v240 = M.build


def build_gce(config, scen, v, **kw):
    """v240 build with the county corridor rule and the gas gate"""
    M.add_line_expansion = add_line_expansion_gce
    M.add_public_candidates = add_public_candidates_bulk
    n, mult = _build_v240(config, scen, v, **kw)
    ren = n.generators.index[n.generators.carrier.isin(['solar', 'onwind'])]
    miss = ren.difference(n.generators_t.p_max_pu.columns)
    assert len(miss) == 0, f'D250-22: solar/onwind without availability profile: {list(miss)[:10]}'
    gas_gate(n)
    return n, mult


# ------------------------------------------------------------------------------------------------ S2-SF developer stage
def private_stage_sf(config, s1_net, v_priv, mult, reuse_on):
    """S2-SF: per-county developer LP on the S1 county price, lexicographic speed-first then private cost."""
    if GCFG['s2_rule'] == 'v':
        return _private_v240(config, s1_net, v_priv, mult, reuse_on)
    dem = M.study_new_demand()
    K, R, out = {}, {}, []
    sw = s1_net.snapshot_weightings.generators
    ow = pd.Series([float(s1_net.investment_period_weightings.objective[p]) for p in s1_net.snapshots.get_level_values(0)],
                   index=s1_net.snapshots)
    erm_p = s1_net.buses_t.get('erm_price')
    opts = dict(Method=2, Crossover=0, BarConvTol=1e-6, OutputFlag=0, Threads=M.CFG['threads'])
    for z in sorted(dem.zone.unique()):
        n = pypsa.Network()
        n.set_snapshots(s1_net.snapshots)
        n.investment_periods = M.periods()
        n.snapshot_weightings = s1_net.snapshot_weightings.copy()
        n.investment_period_weightings = s1_net.investment_period_weightings.copy()
        n.investment_period_weightings.loc[:, 'objective'] = [M.w_private(p) for p in M.periods()]
        lmp = s1_net.buses_t.marginal_price[z].astype(float)
        adder = pd.Series(0.0, index=s1_net.snapshots)
        if M.CFG['tariff'] == 'energy_erm' and erm_p is not None and z in erm_p:
            adder = (1 + w2.ERM_MARGIN) * erm_p[z].astype(float).fillna(0.0).abs() / (sw * ow)
        M.STATE['lmp_energy'] = {z: lmp}
        M.add_dc(n, dem[dem.zone == z], v_priv, mult, byop=M.CFG['byop_techs'], price={z: lmp + adder}, actor='private')
        gas_gate(n)
        rs = []
        if reuse_on:
            for e in M.STATE.get('reuse_s1', []):
                if e['zone'] != z:
                    continue
                rp = M.reuse_params('private')
                dcn = f'DC_{z} BYOP R {e["asset_id"]}'
                if 'byop_R' not in n.carriers.index:
                    n.add('Carrier', 'byop_R', co2_emissions=0.0)
                n.add('Generator', dcn, bus=f'DC_{z}', carrier='byop_R', p_nom_extendable=True, p_nom_max=e['MW'],
                      capital_cost=rp['annual'], marginal_cost=e['mc'], p_max_pu=1.0 / M.REUSE_R,
                      build_year=e['build_period'], lifetime=M.REUSE_LIFE)
                rs.append((e['asset_id'], dcn))
        M.STATE['erm'] = False
        sv_reuse = M.STATE.get('reuse', []); M.STATE['reuse'] = []
        m = n.optimize.create_model(multi_investment_periods=True)
        M.extra(n, n.snapshots)
        cost_obj = m.objective.expression
        Snames = {int(n.generators.build_year[s]): s for s in n.generators.index[n.generators.carrier == 'compute_IT']}
        lex = {}
        for p in sorted(Snames):                          # stage A: earliest service first, year by year
            Sv = m['Generator-p_nom'].sel(name=Snames[p])
            m.objective = -1.0 * Sv
            st, tc = m.solve(solver_name='gurobi', **opts)
            s_star = float(m.solution['Generator-p_nom'].sel(name=Snames[p]))
            lex[p] = dict(S_max=s_star, termination=str(tc))
            m.add_constraints(Sv >= max(0.0, s_star * (1 - 1e-6) - 1e-4), name=f'S2SF-lex_{z}_{p}')
        m.objective = cost_obj                            # stage B: private cost at the fixed fastest trajectory
        n.optimize.solve_model(solver_name='gurobi', solver_options=opts)
        M.STATE['reuse'] = sv_reuse
        M.STATE['erm'] = True
        for b in n.generators.index[n.generators.carrier.str.startswith('byop_') & (n.generators.carrier != 'byop_R')]:
            K[(z, n.generators.carrier[b][5:], int(n.generators.build_year[b]))] = float(n.generators.p_nom_opt[b])
        for aid, dcn in rs:
            R[aid] = float(n.generators.p_nom_opt[dcn])
        S = {p: float(n.generators.p_nom_opt[s]) for p, s in Snames.items()}
        out.append(dict(zone=z, rule='S2-SF', private_objective=float(n.objective), termination=str(m.termination_condition),
                        integer_vars=int(len(m.binaries) + len(m.integers)), S=S, lexicographic=lex,
                        K={f'{c}_{p}': K[(zz, c, p)] for (zz, c, p) in K if zz == z}, R={a: R[a] for a, _ in rs},
                        mean_lmp=float(lmp.mean()), mean_adder=float(adder.mean())))
    return K, R, out


_private_v240 = M.private_stage


def gas_use(n):
    """fuel demand of the dispatched dedicated gas units (MMBtu): what a firm MDQ would have to cover (P0F F3 item 4)"""
    t = M.tech().set_index(['carrier', 'boundary'])
    g = n.generators
    rows = []
    for c in DC_COUNTIES:
        for b in g.index[(g.bus == f'DC_{c}') & g.carrier.str.startswith('byop_')]:
            car = g.carrier[b][5:]
            if car == 'R':
                hr = 3412.14 / float(g.efficiency[b]) if float(g.efficiency.get(b, 0) or 0) > 0 else np.nan
            elif car in GAS_FIRED:
                hr = float(t.loc[(car, 'DC_BTM')].heat_rate_Btu_kWh)
            else:
                continue
            p = n.generators_t.p[b] if b in n.generators_t.p else None
            if p is None or float(p.abs().max()) < 1e-3:   # solver noise (no real dedicated dispatch)
                continue
            per = n.snapshots.get_level_values(0); day = n.snapshots.get_level_values(1).normalize()
            mmbtu = p * M.SNAP_HOURS * hr / 1000.0           # MWh x Btu/kWh / 1000 = MMBtu
            daily = mmbtu.groupby([per, day]).sum()
            for yr, dd in daily.groupby(level=0):
                rows.append(dict(county=c, asset=b, carrier=car, year=int(yr), heat_rate_Btu_kWh=hr,
                                 peak_day_MMBtu=float(dd.max()), mean_day_MMBtu=float(dd.mean())))
    return pd.DataFrame(rows)


def main():
    import argparse
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--grid', default='G-R', choices=['G-C', 'G-R', 'G-RA', 'G-I'])
    ap.add_argument('--gas-gate', default='contract', choices=['evidence', 'contract'])
    ap.add_argument('--s2-rule', default='sf', choices=['sf', 'v'])
    ap.add_argument('--erm-scope', default='tx', choices=['tx', 'nodal'], help='D250-15: tx = one TX row; nodal = upstream per-county rows')
    ap.add_argument('--dem-scale', type=float, default=1.0, help='CNY-05 headroom diagnostic: scale of the Study-New DC request (labelled STYLIZED if != 1)')
    ap.add_argument('--base', default=None, help='county baseline nc (default outputs/baseline_2025_county/...)')
    a, rest = ap.parse_known_args()
    global BASE_COUNTY
    if a.base:
        BASE_COUNTY = Path(a.base)
    GCFG.update(grid=a.grid, gas_gate=a.gas_gate, s2_rule=a.s2_rule, erm_scope=a.erm_scope)
    configure()
    M.CFG['dem_scale'] = a.dem_scale      # v240 main() does not overwrite dem_scale
    GCFG['dem_scale'] = a.dem_scale
    M.build = build_gce
    M.private_stage = private_stage_sf
    M.extra = extra_gce
    w2.store_ERM_duals = store_erm_duals_tx
    sys.argv = [sys.argv[0]] + rest
    # wrap the v240 main: after it writes its outputs, add the GCE / gas audits next to them
    out = Path(rest[rest.index('--out') + 1])
    out.mkdir(parents=True, exist_ok=True)
    orig_solve = M.solve
    gas_tables = []

    def solve_and_audit(config, tag, out_, n):
        res = orig_solve(config, tag, out_, n)
        if tag not in ('ERM02_calibration',):
            gu = gas_use(n)
            if len(gu):
                gu.insert(0, 'scenario', tag); gas_tables.append(gu)
            for d in M.STATE.get('dc', []):
                d.setdefault('county_proxy_poi', True)
        return res
    M.solve = solve_and_audit
    try:
        M.main()
    finally:
        (out / 'gce_manifest.json').write_text(json.dumps(dict(
            gce=GCFG, corridor_audit=GSTATE.get('corridor_audit'), erm_tx=GSTATE.get('erm_tx'), dc_counties=COUNTY_NAME, firm_mdq=FIRM_MDQ,
            line_leads=M.LINE_LEADS, n_zones=len(GSTATE.get('zones', [])), base=str(BASE_COUNTY),
            base_sha256=M.sha(BASE_COUNTY), cohorts_sha256=M.sha(COHORTS_COUNTY), tpit_map_sha256=M.sha(TPIT_MAP),
            code_sha256={p.name: M.sha(p) for p in [Path(__file__), V240 / 'v240_mech.py']},
            poi='county_proxy_poi: K_POI unknown; POI link = PUE x G (G = D, GRID-01); not a certified POI'), indent=2, default=str))
        pd.DataFrame(GSTATE.get('gas_gate', [])).to_csv(out / 'F4_SCENARIO_GAS_GATE_MATRIX.csv', index=False)
        pd.DataFrame(M.STATE.get('corridors', [])).to_csv(out / 'gce_corridors.csv', index=False)
        if gas_tables:
            pd.concat(gas_tables).to_csv(out / 'byop_gas_use.csv', index=False)


if __name__ == '__main__':
    main()
