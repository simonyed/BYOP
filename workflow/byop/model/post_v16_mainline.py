"""NEXT-01 A2-STATIC: post-v1.6 rules for the multi-period mainline (S0 / S1 first). BUILD ONLY - the mainline solve path stays
refused (rearch_mech.py --post-v16 exits 3) until a separate A2 manifest, budget and researcher approval exist.

A2-P1  operating reserve (replaces the legacy 15 % snapshot ERM, its shadow SOC, ERM-02 B and S0CAL on the new line):
         sum_{eligible grid thermal + hydro} r_g(t) + sum_{grid storage} r_s(t) >= R (3,000 MW) in EVERY snapshot of EVERY period
         thermal (existing and public candidates; LP online-capacity relaxation, no binaries):
             p <= c,  c <= p_nom x avail x active,  p >= pmin x c,  r <= c - p,  r <= rho x c          (p_nom a variable if extendable)
         storage: r <= p_nom - p_dispatch + p_store,  tau x r / eff_dispatch <= state_of_charge (the dispatch SOC; no *_RESERVES)
         3 h snapshots: the reserve MW is held through the whole 3 h snapshot (each of its 3 hours is a separate 1 h requirement
         with the same dispatch), the energy backing is tau = 1 h from the end-of-snapshot SOC; the 3 h weight applies to
         dispatch energy only (the reserve itself carries no energy) - a system aggregate requirement, not a deliverable
         ancillary-service product, not N-1 / LOLE. BYOP units at DC buses and load_shed are never reserve.
A2-P3  RE + BESS firm certificate per (research site, period) on the B7 stress snapshots (contiguous 3 h stress days):
             F(s,p) <= sum p(byop WIND, PV at DC_s) + sum (p_dispatch - p_store)(byop BESS at DC_s)        at every stress snapshot
             SOC (dispatch variable) at the start of each stress day <= 0.5 x max_hours x p_nom and at the end >= start
         F / PUE enters M2-serve_cap_<S> of the same (site, period) as dedicated firm IT capacity; wind / PV / BESS still
         dispatch normally (energy value) outside this certificate. ISLANDED certificate only (no grid-import term).
Public expansion ledger: every extendable public component must carry a positive capital cost and a build year >= its first
feasible period; committed TPIT / PBRP links are sunk common assets with their source; S0CAL links are forbidden.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import byop_paths as BP

POST_V16 = dict(on=False, reserve_MW=3000.0, tau_h=1.0, window_min=10.0, re_firm=True)
THERMAL = ['CCGT', 'OCGT', 'gas_steam', 'coal', 'biomass']


def reserve_params(case='base'):
    t = pd.read_csv(BP.POST_V16_INPUTS / 'POST_V16_RESERVE_PARAMETERS.csv')
    out = {}
    for car in THERMAL:
        ramp = float(t[(t.parameter == 'ramp_rate') & (t.carrier == car)][case].iloc[0]) / 100.0
        pmin = float(t[(t.parameter == 'min_stable_load') & (t.carrier == car)][case].iloc[0])
        out[car] = dict(pmin=pmin, rho=min(1.0 - pmin, ramp * POST_V16['window_min']))
    out['hydro'] = dict(pmin=0.0, rho=1.0)
    return out


def _like(var, df):
    """DataFrame (snapshot x name) -> DataArray with exactly the coordinates of the linopy variable selection var
    (avoids rebuilding the MultiIndex snapshot coordinate)"""
    lab = var.labels
    names = list(lab.coords['name'].values)
    vals = df.reindex(columns=names).values
    if lab.dims[0] != 'snapshot':
        vals = vals.T
    return lab.copy(data=vals.astype(float))


def _grid(index, bus):
    return [x for x in index if not str(bus[x]).startswith('DC_')]


def add_operating_reserve(n, snapshots):
    import xarray as xr
    m = n.model
    g = n.generators
    rp = reserve_params()
    E = [x for x in _grid(g.index, g.bus) if g.carrier[x] in rp]
    act = n.components['Generator'].get_activity_mask(snapshots)[E].astype(float)
    pmax = n.get_switchable_as_dense('Generator', 'p_max_pu', snapshots, inds=E) * act
    pmax.index.name = 'snapshot'; pmax.columns.name = 'name'
    ext = [x for x in E if g.p_nom_extendable[x]]
    fix = [x for x in E if not g.p_nom_extendable[x]]
    p = m['Generator-p'].sel(name=E, snapshot=snapshots)
    c = m.add_variables(lower=0.0, coords=p.coords, name='PV16M-online_cap')
    r = m.add_variables(lower=0.0, coords=p.coords, name='PV16M-res_thermal')
    pmin = xr.DataArray([rp[g.carrier[x]]['pmin'] for x in E], coords={'name': E}, dims='name')
    rho = xr.DataArray([rp[g.carrier[x]]['rho'] for x in E], coords={'name': E}, dims='name')
    if fix:
        ub = pmax[fix] * g.p_nom[fix]
        m.add_constraints(c.sel(name=fix) <= _like(c.sel(name=fix), ub), name='PV16M-online_cap_fixed')
    if ext:
        m.add_constraints(c.sel(name=ext) - _like(c.sel(name=ext), pmax[ext]) * m['Generator-p_nom'].sel(name=ext) <= 0, name='PV16M-online_cap_ext')
    m.add_constraints(p - c <= 0, name='PV16M-online_max_p')
    m.add_constraints(p - pmin * c >= 0, name='PV16M-online_min')
    m.add_constraints(r + p - c <= 0, name='PV16M-res_thermal_head')
    m.add_constraints(r - rho * c <= 0, name='PV16M-res_ramp')
    total = r.sum('name')
    su = n.storage_units
    S = _grid(su.index, su.bus)
    if S:
        rs = m.add_variables(lower=0.0, coords=m['StorageUnit-p_dispatch'].sel(name=S, snapshot=snapshots).coords, name='PV16M-res_su')
        sact = n.components['StorageUnit'].get_activity_mask(snapshots)[S].astype(float)
        sact.index.name = 'snapshot'; sact.columns.name = 'name'
        pd_ = m['StorageUnit-p_dispatch'].sel(name=S, snapshot=snapshots); ps_ = m['StorageUnit-p_store'].sel(name=S, snapshot=snapshots)
        sfix = [x for x in S if not su.p_nom_extendable[x]]; sext = [x for x in S if su.p_nom_extendable[x]]
        if sfix:
            m.add_constraints(rs.sel(name=sfix) + pd_.sel(name=sfix) - ps_.sel(name=sfix) <= _like(rs.sel(name=sfix), sact[sfix] * su.p_nom[sfix]), name='PV16M-res_su_power_fixed')
        if sext:
            m.add_constraints(rs.sel(name=sext) + pd_.sel(name=sext) - ps_.sel(name=sext) - _like(rs.sel(name=sext), sact[sext]) * m['StorageUnit-p_nom'].sel(name=sext) <= 0,
                              name='PV16M-res_su_power_ext')
        effd = xr.DataArray(su.efficiency_dispatch[S].values, coords={'name': S}, dims='name')
        m.add_constraints(rs * (POST_V16['tau_h'] / effd) - m['StorageUnit-state_of_charge'].sel(name=S, snapshot=snapshots) <= 0, name='PV16M-res_su_energy')
        total = total + rs.sum('name')
    m.add_constraints(total >= POST_V16['reserve_MW'], name='PV16M-reserve_req')
    return dict(eligible_thermal=len(E), eligible_thermal_ext=len(ext), storage=len(S))


def add_re_bess_firm_certificate(n, snapshots, dc_rows, stress_mask_fn):
    """dc_rows: STATE['dc'] entries (zone, period, S, pue); adds RF certificate rows and the F / PUE term in M2-serve_cap"""
    m = n.model
    g, su = n.generators, n.storage_units
    smask = stress_mask_fn(snapshots)
    per = snapshots.get_level_values(0)
    made = []
    for d in dc_rows:
        s, p = d['zone'], d['period']
        dc = f'DC_{s}'
        re = [x for x in g.index if g.bus[x] == dc and g.carrier[x] in ('byop_WIND', 'byop_PV') and g.build_year[x] <= p]
        ba = [x for x in su.index if su.bus[x] == dc and su.carrier[x] == 'byop_BESS' and su.build_year[x] <= p]
        sns = snapshots[(per == p) & smask]
        if not (re or ba) or not len(sns):
            continue
        F = m.add_variables(lower=0.0, name=f'A2-F_cert_{s}_{p}')
        supply = 0
        if re:
            supply = m['Generator-p'].sel(name=re, snapshot=sns).sum('name')
        if ba:
            net = (m['StorageUnit-p_dispatch'].sel(name=ba, snapshot=sns) - m['StorageUnit-p_store'].sel(name=ba, snapshot=sns)).sum('name')
            supply = net if isinstance(supply, int) else supply + net
            # stress-day SOC boundary on the dispatch SOC (islanded certificate: no free energy carried into the window)
            days = pd.Index(sns.get_level_values(1).normalize()).unique()
            for k, day in enumerate(days):
                ds = sns[pd.Index(sns.get_level_values(1).normalize()) == day]
                soc = m['StorageUnit-state_of_charge']
                for b in ba:
                    pn = m['StorageUnit-p_nom'].sel(name=b) if su.p_nom_extendable[b] else float(su.p_nom[b])
                    h = float(su.max_hours[b])
                    m.add_constraints(soc.sel(name=b, snapshot=ds[0]) - 0.5 * h * pn <= 0, name=f'A2-F_soc_start_{b}_{p}_{k}')
                    m.add_constraints(soc.sel(name=b, snapshot=ds[-1]) - soc.sel(name=b, snapshot=ds[0]) >= 0, name=f'A2-F_soc_end_{b}_{p}_{k}')
        m.add_constraints(F - supply <= 0, name=f'A2-F_cert_rows_{s}_{p}')
        nm = f"M2-serve_cap_{d['S']}"
        if nm in m.constraints:
            c_ = m.constraints[nm]
            lhs, rhs = c_.lhs - F * (1.0 / d['pue']), c_.rhs
            m.remove_constraints(nm)
            m.add_constraints(lhs <= rhs, name=nm)
        made.append(dict(site=s, period=p, re_units=len(re), bess_units=len(ba), stress_snapshots=len(sns)))
    return made


def public_expansion_ledger(n, periods, first_period_fn=None):
    rows = []
    for comp, df in (('Generator', n.generators), ('StorageUnit', n.storage_units), ('Link', n.links)):
        for name, r in df[df.p_nom_extendable].iterrows():
            bus = r.bus if comp != 'Link' else r.bus0
            if str(bus).startswith('DC_') or str(r.carrier).startswith('byop_') or 'POI' in str(r.carrier) or 'load_shed' in str(r.carrier):
                continue
            paired_rev = comp == 'Link' and str(name).endswith('_rev') and f"{str(name)[:-4]}_fwd" in n.links.index
            rows.append(dict(component=comp, name=name, carrier=r.carrier, bus=bus, build_year=r.build_year, lifetime=r.lifetime,
                             capital_cost=float(r.capital_cost), p_nom_max=float(r.p_nom_max), paired_reverse=paired_rev,
                             priced=float(r.capital_cost) > 0 or paired_rev, status='ENDOGENOUS_PRICED' if (float(r.capital_cost) > 0 or paired_rev) else 'FREE_FORBIDDEN'))
    for name, r in n.links[n.links.carrier.isin(['AC_base_committed', 'AC_committed'])].iterrows():
        rows.append(dict(component='Link', name=name, carrier=r.carrier, bus=r.bus0, build_year=r.build_year, lifetime=r.lifetime,
                         capital_cost=float(r.capital_cost), p_nom_max=float(r.p_nom), paired_reverse=False, priced=None,
                         status='COMMITTED_SUNK_COMMON_ASSET (exogenous source; same in S0-S3)'))
    for name, r in n.links[n.links.carrier == 'AC_s0cal'].iterrows():
        rows.append(dict(component='Link', name=name, carrier=r.carrier, bus=r.bus0, build_year=r.build_year, lifetime=r.lifetime,
                         capital_cost=float(r.capital_cost), p_nom_max=float(r.p_nom), paired_reverse=False, priced=False, status='S0CAL_FORBIDDEN'))
    return pd.DataFrame(rows)
