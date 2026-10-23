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

POST_V16 = dict(on=False, reserve_MW=3000.0, tau_h=1.0, window_min=10.0, re_firm=True, stores_elapsed_h=True, soc_segments=True)
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


# NEXT-07 W1: the ONLY admissible diagnostic of the reserve rule - the RHS of PV16M-reserve_req set to 0 MW in one SHA-pinned
# config (own out_dir / ledger / manifest / run_args, 1 S0_COST call); every other row of add_operating_reserve is kept.
# The value is passed per model build (never written into POST_V16), so the formal A2 / NEXT-06 / A3 paths stay at 3,000 MW.
RESERVE_PROBE = dict(config_name='config.byop_post_v16_n07_reserve_probe.yaml', kind='S0_RESERVE_REQ_RHS_ONLY', reserve_requirement_MW=0.0,
                     stages=['S0'], out_dir='results/BYOP/next07_s0_reserve_probe',
                     run_args={'start': 2026, 'end': 2031, 'sample_weeks': 26, 'scenarios': ['S0']},
                     label='DIAGNOSTIC_NONCOMPLIANT_WITH_FORMAL_3GW_REQUIREMENT')


def diagnostic_reserve_rhs(c, cfg_path):
    """reserve RHS (MW) a gate config asks for: None (formal 3,000 MW) when it has no `diagnostic` block; 0.0 only for the exact
    NEXT-07 probe config (name, kind, value, S0 only, own out_dir, pinned run_args, budget 1 / 1); anything else -> ValueError"""
    d = c.get('diagnostic')
    if d is None:
        return None
    from pathlib import Path as _P
    rp, bad = RESERVE_PROBE, []
    if _P(cfg_path).name != rp['config_name']:
        bad.append(f"diagnostic block only allowed in {rp['config_name']}")
    if not isinstance(d, dict) or set(d) != {'kind', 'reserve_requirement_MW'} or d.get('kind') != rp['kind']:
        bad.append(f'diagnostic must be exactly kind={rp["kind"]} + reserve_requirement_MW')
    elif float(d['reserve_requirement_MW']) != rp['reserve_requirement_MW']:
        bad.append(f"diagnostic reserve_requirement_MW {d['reserve_requirement_MW']} != {rp['reserve_requirement_MW']}")
    if list(c.get('stages') or []) != rp['stages'] or c.get('out_dir') != rp['out_dir'] or (c.get('run_args') or {}) != rp['run_args']:
        bad.append('diagnostic config must pin stages [S0], its own out_dir and run_args 2026-2031 / 26 weeks / [S0]')
    if int(c.get('max_scenario_attempts', 0)) != 1 or int(c.get('max_top_level_optimizer_calls', 0)) != 1 or c.get('optimizer_call_plan') != {'S0': ['S0_COST']}:
        bad.append('diagnostic config budget must be 1 attempt / 1 S0_COST call')
    if bad:
        raise ValueError('; '.join(bad))
    return float(d['reserve_requirement_MW'])


def add_operating_reserve(n, snapshots, reserve_MW=None):
    """reserve_MW: RHS of PV16M-reserve_req; None = the formal POST_V16['reserve_MW'] (3,000 MW). Only the NEXT-07 probe passes 0.0
    (see diagnostic_reserve_rhs); all other rows are identical for any value."""
    import xarray as xr
    rhs = float(POST_V16['reserve_MW'] if reserve_MW is None else reserve_MW)
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
        # NEXT-02 A2-FIX-03: the same energy backing at the START of the 3 h interval. PyPSA's own balance gives
        #   (1 - l)^w soc_prev = soc_t - w (eff_s p_store - p_dispatch / eff_d) - w inflow + w spill      (w = stores weighting)
        # so the decayed start SOC is an exact affine expression of the dispatch variables (no shadow SOC, no assumption on
        # the previous-snapshot / cyclic rule); it is <= soc_prev, hence conservative. Dispatch is constant within the
        # snapshot, so the SOC path is monotone between the two endpoints and both rows bound the whole interval.
        soc_start, info_start = interval_start_soc(n, snapshots, S)
        m.add_constraints(rs * (POST_V16['tau_h'] / effd) - soc_start <= 0, name='PV16M-res_su_energy_start')
        total = total + rs.sum('name')
    m.add_constraints(total >= rhs, name='PV16M-reserve_req')
    return dict(eligible_thermal=len(E), eligible_thermal_ext=len(ext), storage=len(S), soc_interval_start=info_start if S else None,
                reserve_req_rhs_MW=rhs)


def interval_start_soc(n, snapshots, S):
    """NEXT-02 A2-FIX-03: (1 - standing_loss)^w x SOC at the start of each snapshot, as a linopy expression of the dispatch
    variables of the same model (see add_operating_reserve)"""
    m = n.model
    su = n.storage_units
    w = n.snapshot_weightings.stores.loc[snapshots]
    frame = lambda f: pd.DataFrame({x: f(x) for x in S}, index=snapshots).rename_axis(columns='name')
    soc = m['StorageUnit-state_of_charge'].sel(name=S, snapshot=snapshots)
    ws = _like(soc, frame(lambda x: w.values * float(su.efficiency_store[x])))
    wd = _like(soc, frame(lambda x: w.values / float(su.efficiency_dispatch[x])))
    e = soc - ws * m['StorageUnit-p_store'].sel(name=S, snapshot=snapshots) + wd * m['StorageUnit-p_dispatch'].sel(name=S, snapshot=snapshots)
    # natural inflow is a constant: subtracted exactly; spill (>= 0) is left out, which only lowers the bound (conservative)
    inflow = n.get_switchable_as_dense('StorageUnit', 'inflow', snapshots, inds=S).reindex(columns=S).fillna(0.0)
    with_inflow = [x for x in S if float(inflow[x].abs().sum()) > 0]
    if with_inflow:
        e = e - _like(soc, frame(lambda x: w.values * inflow[x].values))
    return e, dict(storage=len(S), with_inflow=len(with_inflow), weight_h=sorted(set(np.round(w.values, 6)))[:5],
                   spill_term='omitted (conservative)')


FIRM_RULES = (None, 'CONSERVATIVE_FIRM_SCREENING')


def add_re_bess_firm_certificate(n, snapshots, dc_rows, stress_mask_fn, firm_rule=None):
    """dc_rows: STATE['dc'] entries (zone, period, S, pue); adds RF certificate rows and the F / PUE term in M2-serve_cap.
    NEXT-07 W4.2 firm_rule='CONSERVATIVE_FIRM_SCREENING' (A3, S2 and S3 alike, set once per run): the certificate rows are still
    built (audit), but F has upper bound 0 - dedicated BYOP RE + BESS earns NO full-year firm IT credit until a 48 / 72 h contiguous
    same-SOC certificate exists (not implemented; a sampling change is a separate decision). Wind / PV / BESS keep dispatching
    (energy, non-firm service); qualified firm terms of M2-serve_cap (RICE, SOFC, aero, firm import) are unchanged."""
    if firm_rule not in FIRM_RULES:
        raise ValueError(f'firm_rule {firm_rule!r} not implemented (allowed: {FIRM_RULES})')
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
        F = m.add_variables(lower=0.0, upper=0.0 if firm_rule == 'CONSERVATIVE_FIRM_SCREENING' else np.inf, name=f'A2-F_cert_{s}_{p}')
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
        made.append(dict(site=s, period=p, re_units=len(re), bess_units=len(ba), stress_snapshots=len(sns),
                         firm_rule=firm_rule or 'LEGACY_24H_CERTIFICATE', firm_credit_allowed=firm_rule != 'CONSERVATIVE_FIRM_SCREENING'))
    return made


def public_expansion_ledger(n, periods, first_period_fn=None, m=None):
    """NEXT-02 A2-FIX-01: a zero-cost '_rev' link counts as priced ONLY when the model m holds an equality row tying its
    capacity to its positively priced '_fwd' twin (see expansion_pair_audit); without m (or without the row) it is
    PAIR_UNVERIFIED / FREE_FORBIDDEN, never ENDOGENOUS_PRICED by name alone"""
    pairs = expansion_pair_audit(n, m).set_index('rev') if m is not None else None
    rows = []
    for comp, df in (('Generator', n.generators), ('StorageUnit', n.storage_units), ('Link', n.links)):
        for name, r in df[df.p_nom_extendable].iterrows():
            bus = r.bus if comp != 'Link' else r.bus0
            if str(bus).startswith('DC_') or str(r.carrier).startswith('byop_') or 'POI' in str(r.carrier) or 'load_shed' in str(r.carrier):
                continue
            paired_rev = comp == 'Link' and str(name).endswith('_rev') and f"{str(name)[:-4]}_fwd" in n.links.index
            bound = bool(pairs is not None and paired_rev and name in pairs.index and pairs.loc[name, 'PASS'])
            if float(r.capital_cost) > 0:
                status = 'ENDOGENOUS_PRICED'
            elif paired_rev:
                status = 'ENDOGENOUS_PRICED_VIA_FWD_EQUALITY' if bound else ('PAIR_UNVERIFIED' if m is None else 'FREE_FORBIDDEN')
            else:
                status = 'FREE_FORBIDDEN'
            rows.append(dict(component=comp, name=name, carrier=r.carrier, bus=bus, build_year=r.build_year, lifetime=r.lifetime,
                             capital_cost=float(r.capital_cost), p_nom_max=float(r.p_nom_max), paired_reverse=paired_rev,
                             pair_equality_verified=bound if paired_rev else None, priced=status.startswith('ENDOGENOUS_PRICED'), status=status))
    for name, r in n.links[n.links.carrier.isin(['AC_base_committed', 'AC_committed'])].iterrows():
        rows.append(dict(component='Link', name=name, carrier=r.carrier, bus=r.bus0, build_year=r.build_year, lifetime=r.lifetime,
                         capital_cost=float(r.capital_cost), p_nom_max=float(r.p_nom), paired_reverse=False, priced=None,
                         status='COMMITTED_SUNK_COMMON_ASSET (exogenous source; same in S0-S3)'))
    for name, r in n.links[n.links.carrier == 'AC_s0cal'].iterrows():
        rows.append(dict(component='Link', name=name, carrier=r.carrier, bus=r.bus0, build_year=r.build_year, lifetime=r.lifetime,
                         capital_cost=float(r.capital_cost), p_nom_max=float(r.p_nom), paired_reverse=False, priced=False, status='S0CAL_FORBIDDEN'))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ NEXT-02 static audits (no solver)
COMMITTED_COSTS = BP.INPUTS / 'grid/COMMITTED_PUBLIC_ASSET_COSTS.csv'


def _label(var, name):
    return int(np.asarray(var.sel(name=name).labels.values).ravel()[0])


def _row(m, cname):
    """(coefficient by variable label, sign, rhs) of a scalar linopy constraint"""
    c = m.constraints[cname]
    v = np.asarray(c.lhs.vars.values).ravel(); co = np.asarray(c.lhs.coeffs.values).ravel()
    keep = v != -1
    return pd.Series(co[keep]).groupby(v[keep]).sum(), str(np.asarray(c.sign.values).ravel()[0]), float(np.asarray(c.rhs.values).ravel()[0])


def objective_coefficients(m):
    e = m.objective.expression if hasattr(m.objective, 'expression') else m.objective
    v = np.asarray(e.vars.values).ravel(); co = np.asarray(e.coeffs.values).ravel()
    keep = v != -1
    return pd.Series(co[keep]).groupby(v[keep]).sum()


def _holds(d, sign, rhs, x, tol=1e-6):
    lhs = sum(float(d.get(k, 0.0)) * val for k, val in x.items())
    return abs(lhs - rhs) <= tol if sign == '=' else (lhs <= rhs + tol if sign == '<=' else lhs >= rhs - tol)


def expansion_pair_audit(n, m, corridors=None, approval_year=None, obj=None, probe_MW=100.0):
    """NEXT-02 A2-FIX-01: for every endogenous AC_exp '<corridor>_exp<p>_fwd' / '_rev' pair check, on the built model, that
    (a) an equality row M2-line_sym_<fwd> ties p_nom_rev to p_nom_fwd (+1 / -1, rhs 0), so a reverse-only build is infeasible,
    (b) only the fwd side is priced (objective coefficient > 0 on fwd, 0 on rev): one positive investment per MW of two-way capacity,
    (c) both sides share build year / lifetime / p_nom_max, and the corridor row M2-line_cap_<corridor> caps the cumulative fwd
        builds over all periods by the corridor limit"""
    lk = n.links
    fwd = [x for x in lk.index[(lk.carrier == 'AC_exp') & lk.p_nom_extendable] if str(x).endswith('_fwd')]
    if m is None or not fwd:
        return pd.DataFrame(columns=['fwd', 'rev', 'PASS'])
    lp = m['Link-p_nom']
    obj = objective_coefficients(m) if obj is None else obj
    corr = {c['corridor']: c for c in (corridors or [])}
    caps = {c[len('M2-line_cap_'):]: c for c in m.constraints if c.startswith('M2-line_cap_')}
    approval_year = approval_year or {}
    rows = []
    for f in fwd:
        r = f[:-4] + '_rev'
        base, per = f.rsplit('_exp', 1)
        per = int(per[:-4])
        lf = _label(lp, f)
        lr = _label(lp, r) if r in lk.index and bool(lk.p_nom_extendable.get(r, False)) else None
        sym = f'M2-line_sym_{f}'
        rec = dict(fwd=f, rev=r, corridor=base, period=per, build_year_fwd=int(lk.build_year[f]),
                   build_year_rev=int(lk.build_year[r]) if r in lk.index else None, approval_year=approval_year.get(f),
                   capital_cost_fwd=float(lk.capital_cost[f]), capital_cost_rev=float(lk.capital_cost[r]) if r in lk.index else None,
                   obj_coef_fwd=float(obj.get(lf, 0.0)), obj_coef_rev=float(obj.get(lr, 0.0)) if lr is not None else None,
                   p_nom_max_fwd=float(lk.p_nom_max[f]), p_nom_max_rev=float(lk.p_nom_max[r]) if r in lk.index else None,
                   sym_row=sym if sym in m.constraints else None, corridor_cap_MW=None)
        ok_sym = rej = acc = False
        if rec['sym_row'] and lr is not None:
            d, sign, rhs = _row(m, sym)
            ok_sym = sign == '=' and abs(rhs) < 1e-12 and set(d.index) == {lf, lr} and abs(d[lf] + d[lr]) < 1e-12 and abs(abs(d[lf]) - 1) < 1e-12
            rej = not _holds(d, sign, rhs, {lf: 0.0, lr: probe_MW}) and not _holds(d, sign, rhs, {lf: probe_MW, lr: 0.0})
            acc = _holds(d, sign, rhs, {lf: probe_MW, lr: probe_MW})
        cap_ok = False
        if base in caps:
            d, sign, rhs = _row(m, caps[base])
            cap_ok = sign == '<=' and lf in d.index and abs(d[lf] - 1) < 1e-12 and lr not in d.index
            rec['corridor_cap_MW'] = rhs
            if base in corr:
                cap_ok = cap_ok and abs(rhs - corr[base]['cap_MW']) < 1e-6
        rec.update(sym_coeffs_ok=ok_sym, reverse_only_rejected=rej, equal_build_accepted=acc, corridor_cap_row_ok=cap_ok,
                   investment_once_USD_per_MW=rec['obj_coef_fwd'])
        rec['same_build_life_cap'] = bool(r in lk.index and rec['build_year_rev'] == rec['build_year_fwd']
                                          and float(lk.lifetime[f]) == float(lk.lifetime[r]) and rec['p_nom_max_rev'] == rec['p_nom_max_fwd'])
        rec['PASS'] = bool(ok_sym and rej and acc and cap_ok and rec['same_build_life_cap'] and rec['capital_cost_fwd'] > 0
                           and rec['obj_coef_fwd'] > 0 and rec['capital_cost_rev'] == 0 and rec['obj_coef_rev'] == 0
                           and (rec['approval_year'] is None or rec['approval_year'] < rec['build_year_fwd']))
        rows.append(rec)
    return pd.DataFrame(rows)


def committed_links_audit(n, m):
    """fixed committed TPIT / PBRP links: never extendable, never in a line_sym / line_cap row (no double counting with AC_exp)"""
    lk = n.links
    com = lk.index[lk.carrier.isin(['AC_base_committed', 'AC_committed'])]
    in_rows = set()
    if m is not None:
        for c in m.constraints:
            if c.startswith(('M2-line_sym_', 'M2-line_cap_')):
                in_rows |= {x for x in com if x in c}
    return pd.DataFrame([dict(name=x, carrier=lk.carrier[x], bus0=lk.bus0[x], bus1=lk.bus1[x], p_nom_MW=float(lk.p_nom[x]),
                              build_year=int(lk.build_year[x]), extendable=bool(lk.p_nom_extendable[x]), capital_cost=float(lk.capital_cost[x]),
                              max_avail=float(n.links_t.p_max_pu[x].max()) if x in n.links_t.p_max_pu else 1.0,
                              in_expansion_rows=x in in_rows,
                              PASS=bool((not lk.p_nom_extendable[x]) and x not in in_rows and float(lk.capital_cost[x]) == 0.0)) for x in com])


def _public_candidates(n):
    out = []
    for comp, df in (('Generator', n.generators), ('StorageUnit', n.storage_units), ('Link', n.links)):
        bus = df.bus if comp != 'Link' else df.bus0
        sel = df.p_nom_extendable & ~bus.astype(str).str.startswith('DC_') & ~df.carrier.astype(str).str.startswith('byop_') \
            & ~df.carrier.astype(str).str.contains('POI|load_shed', regex=True)
        out += [(comp, x) for x in df.index[sel]]
    return out


def cod_activity_audit(n, m, approval_year=None, obj=None):
    """NEXT-02 A2-FIX-02: approval -> build -> COD -> dispatch for every endogenous public candidate on the built model:
    approval year < build year (= COD period), no availability before the build year (PyPSA activity mask; the dispatch
    variable is masked or capacity-free there), positive capital cost in the objective"""
    approval_year = approval_year or {}
    obj = objective_coefficients(m) if obj is None else obj
    per = np.asarray(n.snapshots.get_level_values(0))
    disp = {'Generator': 'Generator-p', 'StorageUnit': 'StorageUnit-p_dispatch', 'Link': 'Link-p'}
    rows = []
    amask = {c: n.components[c].get_activity_mask(n.snapshots) for c in disp}
    for comp, x in _public_candidates(n):
        df = n.components[comp].static
        by, life = int(df.build_year[x]), float(df.lifetime[x])
        act = np.asarray(amask[comp][x].values, dtype=bool)
        before = per < by
        lab = np.asarray(m[disp[comp]].sel(name=x).labels.values).ravel()
        masked_before = bool((lab[before] == -1).all()) if before.any() else None
        lab_pn = _label(m[f'{comp}-p_nom'], x)
        ay = approval_year.get(x)
        first_act = int(per[act][0]) if act.any() else None
        oc = float(obj.get(lab_pn, 0.0))
        twin = x[:-4] + '_fwd' if comp == 'Link' and str(x).endswith('_rev') and x[:-4] + '_fwd' in n.links.index else None
        if twin is not None:        # zero-cost reverse side: priced through its fwd twin (equality checked in expansion_pair_audit)
            ay = approval_year.get(twin, ay)
        priced = (float(df.capital_cost[x]) > 0 and oc > 0) if twin is None else (float(n.links.capital_cost[twin]) > 0
                                                                                   and float(obj.get(_label(m['Link-p_nom'], twin), 0.0)) > 0)
        rows.append(dict(component=comp, name=x, carrier=df.carrier[x], build_year=by, lifetime=life, approval_year=ay,
                         lead_years=(by - ay) if ay is not None else None, snapshots_before_build=int(before.sum()),
                         active_before_build=bool(act[before].any()) if before.any() else False,
                         dispatch_var_masked_before_build=masked_before, first_active_period=first_act,
                         capital_cost=float(df.capital_cost[x]), obj_coef_p_nom=oc, priced_via=twin or 'self',
                         PASS=bool(not (act[before].any() if before.any() else False) and priced
                                   and (ay is None or ay <= by) and first_act in (None, by))))
    return pd.DataFrame(rows)


def committed_cost_ledger(case='base'):
    """NEXT-02 A2-FIX-02 (3): absolute committed DWB / PBRP costs, OUTSIDE the LP objective (identical in S0-S3, so they cancel
    in every scenario difference); split into spend assumed before end-2025 (sunk) and the commitment still to be paid"""
    c = pd.read_csv(COMMITTED_COSTS)
    tot, rem = c[f'total_cost_MUSD_{case}'].astype(float), c[f'remaining_share_after_2025_{case}'].astype(float)
    out = c[['asset_id', 'model_links', 'family', 'ISD_model', 'cost_year_basis', 'evidence_class', 'source']].copy()
    out['case'] = case
    out['total_cost_MUSD'] = tot
    out['sunk_by_2025_MUSD'] = tot * (1 - rem)
    out['unpaid_commitment_after_2025_MUSD'] = tot * rem
    out['in_objective'] = c.in_objective.astype(str).str.lower().eq('true')
    out['scenario_difference_treatment'] = 'identical in S0-S3: cancels in S1-S0 / S2-S1 / S2-S3'
    out['absolute_accounting'] = 'reported separately from the LP objective (ratepayer-funded public transmission)'
    return out


def frame_sha(df):
    import hashlib
    return hashlib.sha256(pd.util.hash_pandas_object(df.reset_index(), index=False).values.tobytes()).hexdigest()


def public_inputs_fingerprint(n):
    """everything S0 and S1 must share (non-DC buses / components, weights, costs); DC-bus rows and study-AIDC loads excluded"""
    nd = lambda b: ~b.astype(str).str.startswith('DC_')
    g, su, lk, ld = n.generators, n.storage_units, n.links, n.loads
    gcols = ['bus', 'carrier', 'p_nom', 'p_nom_extendable', 'p_nom_max', 'capital_cost', 'marginal_cost', 'build_year', 'lifetime', 'efficiency']
    scols = ['bus', 'carrier', 'p_nom', 'p_nom_extendable', 'p_nom_max', 'capital_cost', 'marginal_cost', 'build_year', 'lifetime', 'max_hours',
             'efficiency_store', 'efficiency_dispatch']
    lcols = ['bus0', 'bus1', 'carrier', 'p_nom', 'p_nom_extendable', 'p_nom_max', 'capital_cost', 'build_year', 'lifetime', 'efficiency']
    gl = g[nd(g.bus)]
    ll = lk[nd(lk.bus0) & nd(lk.bus1)]
    lo = ld[nd(ld.bus)]
    parts = dict(
        generators=gl[gcols].sort_index(),
        generators_p_max_pu=n.generators_t.p_max_pu.reindex(columns=sorted(set(gl.index) & set(n.generators_t.p_max_pu.columns))),
        storage_units=su[nd(su.bus)][scols].sort_index(),
        links=ll[lcols].sort_index(),
        links_p_max_pu=n.links_t.p_max_pu.reindex(columns=sorted(set(ll.index) & set(n.links_t.p_max_pu.columns))),
        lines=n.lines[['bus0', 'bus1', 's_nom', 's_max_pu', 'x', 'r']].sort_index(),
        loads_static=lo[['bus', 'carrier']].sort_index(),
        loads_p_set=n.loads_t.p_set.reindex(columns=sorted(set(lo.index) & set(n.loads_t.p_set.columns))),
        snapshot_weightings=n.snapshot_weightings,
        investment_period_weightings=n.investment_period_weightings)
    return {k: dict(sha256=frame_sha(v), rows=int(len(v)), cols=int(v.shape[1])) for k, v in parts.items()}


def no_harm_qa(n, m, tag):
    """NEXT-02 A2-FIX-04: existing-customer shed units (carrier load_shed: native background + inherited ramp) vs the study-AIDC
    unserved / interruption units, and the D24 no-harm row (S1: shed <= S0 shed + 0.001 MW per unit x snapshot)"""
    g = n.generators
    nh = m.constraints['D24-no_harm_existing_customers'] if 'D24-no_harm_existing_customers' in m.constraints else None
    nh_names = set(nh.lhs.coords['name'].values) if nh is not None else set()
    rows = []
    for car in sorted(set(g.carrier.astype(str))):
        if car == 'load_shed' or car.startswith('dc_') or any(k in car for k in ('unserved', 'interrupt', 'curtail')):
            idx = g.index[g.carrier == car]
            rows.append(dict(scenario=tag, carrier=car, units=len(idx),
                             role='EXISTING_CUSTOMER_SHED (no-harm protected)' if car == 'load_shed' else 'STUDY_AIDC_UNSERVED_OR_INTERRUPTION (not existing customers)',
                             inherited_ramp_units=int(pd.Index(idx).str.endswith(' inherited_ramp_unserved').sum()),
                             native_bus_units=int(len(idx) - pd.Index(idx).str.endswith(' inherited_ramp_unserved').sum()),
                             in_no_harm_row=int(len(set(idx) & nh_names)), no_harm_row_present=nh is not None,
                             no_harm_tolerance_MW=0.001 if nh is not None else None,
                             marginal_cost_min=float(g.marginal_cost[idx].min()) if len(idx) else None,
                             marginal_cost_max=float(g.marginal_cost[idx].max()) if len(idx) else None))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ NEXT-03 A2-FIX-08: SOC segments
def soc_segments(snapshots, step_h=3.0):
    """contiguous segments of the retained snapshots: a new segment starts at every period start and at every time gap
    != step_h (sampled weeks and stress days are separate segments; a multi-day contiguous stress event stays ONE segment)"""
    per = np.asarray(snapshots.get_level_values(0)) if isinstance(snapshots, pd.MultiIndex) else np.zeros(len(snapshots), dtype=int)
    ts = pd.DatetimeIndex(snapshots.get_level_values(-1) if isinstance(snapshots, pd.MultiIndex) else snapshots)
    rows, seg = [], -1
    for i in range(len(snapshots)):
        gap = None if i == 0 or per[i] != per[i - 1] else (ts[i] - ts[i - 1]) / pd.Timedelta(hours=1)
        if gap is None or abs(gap - step_h) > 1e-9:
            seg += 1
        rows.append(dict(pos=i, period=int(per[i]), timestep=ts[i], gap_h_before=gap, segment=seg))
    df = pd.DataFrame(rows)
    df['segment_in_period'] = df.groupby('period').segment.rank(method='dense').astype(int)
    return df


def segment_map(n, snapshots=None, stress_ts=None):
    """A2_SOC_SEGMENT_MAP rows: one per (period, segment)"""
    sns = n.snapshots if snapshots is None else snapshots
    d = soc_segments(sns)
    w = n.snapshot_weightings.loc[sns]
    d['w_generators_h'] = w.generators.values; d['w_stores_h'] = w.stores.values; d['w_objective_h'] = w.objective.values
    st = set(pd.Timestamp(x) for x in (stress_ts or []))
    d['stress'] = d.timestep.map(lambda t: pd.Timestamp(t) in st)
    g = d.groupby(['period', 'segment', 'segment_in_period'])
    out = g.agg(start=('timestep', 'min'), end=('timestep', 'max'), snapshots=('pos', 'size'), gap_h_before=('gap_h_before', 'first'),
                w_generators_h=('w_generators_h', 'mean'), w_stores_h=('w_stores_h', 'mean'), stress_snapshots=('stress', 'sum')).reset_index()
    out['kind'] = np.where(out.stress_snapshots == out.snapshots, 'B7_STRESS_ONLY',
                           np.where(out.stress_snapshots > 0, 'SAMPLED_WEEK_WITH_STRESS', 'SAMPLED_WEEK'))
    return out


def add_segment_soc_neutrality(n, snapshots):
    """NEXT-03 A2-FIX-08: PyPSA chains the state of charge through the retained snapshots in order, so separate sampled weeks /
    stress days (and, for horizon-cyclic units, investment periods) are linked as if adjacent. For every StorageUnit and every
    contiguous segment k:   SOC(last snapshot of k)  >=  SOC_prev(k)
    where SOC_prev(k) is the state PyPSA's own energy balance uses at the first snapshot of k (read from the
    StorageUnit-energy_balance row: the other SOC variable in that row; the initial-SOC constant when there is none). With the
    cyclic chain every segment is then energy neutral (sum of non-negative increments around the cycle = 0): no net energy is
    carried across a time gap or a period, while the 3 h dynamics inside a segment (incl. a multi-day stress event) are kept.
    Linear, no binaries, no new variables."""
    m = n.model
    su = n.storage_units
    if su.empty or 'StorageUnit-energy_balance' not in m.constraints:
        return dict(storage=0, segments=0, rows=0)
    seg = soc_segments(snapshots)
    soc = m['StorageUnit-state_of_charge']
    soc_lab = soc.labels.sel(snapshot=snapshots)
    names = list(soc_lab.coords['name'].values)
    lab = soc_lab.transpose('snapshot', 'name').values                        # snapshot x name
    own = {int(v): (i, j) for i, row in enumerate(lab) for j, v in enumerate(row) if v != -1}
    eb = m.constraints['StorageUnit-energy_balance'].lhs
    ebv = eb.vars.transpose('snapshot', 'name', '_term').sel(snapshot=snapshots, name=names).values
    rows = 0
    made = []
    for k, d in seg.groupby('segment'):
        first, last = int(d.pos.iloc[0]), int(d.pos.iloc[-1])
        groups = {}
        for j, nm in enumerate(names):
            if lab[first, j] == -1 or lab[last, j] == -1:
                continue                                                      # inactive unit in this period
            prev = [own[int(v)] for v in ebv[first, j] if v != -1 and int(v) in own and int(v) != lab[first, j]]
            key = prev[0][0] if prev else None                                 # snapshot position of the predecessor SOC
            groups.setdefault(key, []).append(nm)
        for key, nms in groups.items():
            last_soc = soc.sel(name=nms, snapshot=snapshots[last])
            if key is None:
                init = xr_const(nms, [float(su.state_of_charge_initial[x]) for x in nms])      # PyPSA: absolute MWh
                m.add_constraints(last_soc >= init, name=f'A2F08-seg_soc_{k}_init')
            else:
                m.add_constraints(last_soc - soc.sel(name=nms, snapshot=snapshots[key]) >= 0, name=f'A2F08-seg_soc_{k}_{key}')
            rows += len(nms)
            made.append(dict(segment=int(k), period=int(d.period.iloc[0]), first=str(snapshots[first]), last=str(snapshots[last]),
                             predecessor=str(snapshots[key]) if key is not None else 'INITIAL_CONSTANT', units=len(nms)))
    return dict(storage=len(names), segments=int(seg.segment.nunique()), rows=rows, groups=made)


def xr_const(names, vals):
    import xarray as xr
    return xr.DataArray(np.asarray(vals, dtype=float), coords={'name': names}, dims='name')


# ------------------------------------------------------------------------------------------------ NEXT-06: persist the solved state
def soc_segment_postsolve_audit(n):
    """per StorageUnit x period x contiguous segment: SOC carried in (exact from PyPSA's balance at the first snapshot, standing
    loss as in the model), SOC at the end, end - start, charge / discharge energy (w = stores weighting), and the cyclic flags.
    Energy neutrality is reported from the numbers, not from the constraint count."""
    su = n.storage_units
    if su.empty or n.storage_units_t.state_of_charge.empty:
        return pd.DataFrame()
    seg = soc_segments(n.snapshots)
    soc = n.storage_units_t.state_of_charge
    ps = n.storage_units_t.p_store.reindex(columns=soc.columns).fillna(0.0)
    pdp = n.storage_units_t.p_dispatch.reindex(columns=soc.columns).fillna(0.0)
    w = n.snapshot_weightings.stores
    act = n.components['StorageUnit'].get_activity_mask(n.snapshots)
    rows = []
    for k, d in seg.groupby('segment'):
        sns = n.snapshots[d.pos.values]
        f, l = sns[0], sns[-1]
        for u in soc.columns:
            if not (bool(act.at[f, u]) and bool(act.at[l, u])):
                continue
            effs, effd = float(su.efficiency_store[u]), float(su.efficiency_dispatch[u])
            ws = w.loc[sns]
            ch = float((ps.loc[sns, u] * ws).sum()); dis = float((pdp.loc[sns, u] * ws).sum())
            start = float(soc.at[f, u] - w.at[f] * (effs * ps.at[f, u] - pdp.at[f, u] / effd))     # decayed carried-in SOC (loss 0 here)
            end = float(soc.at[l, u])
            rows.append(dict(unit=u, bus=su.bus[u], carrier=su.carrier[u], period=int(d.period.iloc[0]), segment=int(k), first=str(f[1]), last=str(l[1]),
                             snapshots=len(sns), SOC_start_MWh=start, SOC_end_MWh=end, SOC_end_minus_start_MWh=end - start,
                             charge_MWh_in=ch, discharge_MWh_out=dis, p_nom_opt=float(su.p_nom_opt[u]) if 'p_nom_opt' in su else float(su.p_nom[u]),
                             cyclic=bool(su.cyclic_state_of_charge[u]), cyclic_per_period=bool(su.cyclic_state_of_charge_per_period[u]),
                             extendable=bool(su.p_nom_extendable[u]), build_year=int(su.build_year[u])))
    a = pd.DataFrame(rows)
    if len(a):
        a['neutral_within_1e-3_MWh'] = a.SOC_end_minus_start_MWh.abs() <= 1e-3
        a['end_ge_start'] = a.SOC_end_minus_start_MWh >= -1e-3
    return a


def persist_solution(n, d):
    """write the solved state needed for post-solve audits (before any acceptance / collection step). Returns file -> SHA-256."""
    import hashlib
    from pathlib import Path
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    out = {}
    frames = dict(storage_soc=n.storage_units_t.state_of_charge, storage_p_store=n.storage_units_t.p_store,
                  storage_p_dispatch=n.storage_units_t.p_dispatch, line_p0=n.lines_t.p0, link_p0=n.links_t.p0,
                  generator_p=n.generators_t.p, bus_marginal_price=n.buses_t.marginal_price, snapshot_weightings=n.snapshot_weightings)
    for k, df in frames.items():
        if df is None or df.empty:
            continue
        f = d / f'{k}.csv.gz'
        df.to_csv(f, float_format='%.6g')
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    a = soc_segment_postsolve_audit(n)
    if len(a):
        f = d / 'SOC_SEGMENT_POSTSOLVE_AUDIT.csv'
        a.to_csv(f, index=False)
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    for k, df in reserve_solution_frames(n).items():       # NEXT-07 W2.2: reserve state straight from the linopy solution
        if isinstance(df, str):
            out[f'{k}.error'] = df
            continue
        f = d / f'{k}.csv.gz'
        df.to_csv(f, float_format='%.6g')
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def reserve_solution_frames(n, formal_MW=None):
    """NEXT-07 W2.2: per snapshot reserve total / RHS / dual / thermal and BESS reserve / thermal online capacity / shortfall versus the
    formal 3,000 MW, and per unit online capacity, thermal reserve, BESS reserve and available thermal capacity (p_max_pu x p_nom_opt x
    activity). Read from the linopy variables' .solution (never from merged coordinate tables); a frame that cannot be read is
    returned as an error string. Reads only - the LP is not touched."""
    formal = float(POST_V16['reserve_MW'] if formal_MW is None else formal_MW)
    m = getattr(n, 'model', None)
    out = {}
    if m is None or 'PV16M-reserve_req' not in m.constraints:
        return out
    tab = lambda v: v.solution.transpose('snapshot', 'name').to_pandas()
    try:
        req = m.constraints['PV16M-reserve_req']
        idx = n.snapshots
        tot = pd.Series(np.asarray(req.lhs.solution.values, dtype=float).ravel(), index=idx)
        rhs = pd.Series(np.asarray(req.rhs.values, dtype=float).ravel(), index=idx)
        try:
            dual = pd.Series(np.asarray(req.dual.values, dtype=float).ravel(), index=idx)
        except Exception:
            dual = pd.Series(np.nan, index=idx)
        rt = tab(m['PV16M-res_thermal']); oc = tab(m['PV16M-online_cap'])
        rs = tab(m['PV16M-res_su']) if 'PV16M-res_su' in m.variables else pd.DataFrame(index=idx)
        E = list(oc.columns)
        gp = n.generators_t.p.reindex(columns=E).reindex(idx)
        act = n.components['Generator'].get_activity_mask(idx)[E].astype(float)
        avail = n.get_switchable_as_dense('Generator', 'p_max_pu', idx, inds=E) * act * n.generators.p_nom_opt.reindex(E)
        out['reserve_by_snapshot'] = pd.DataFrame(dict(
            reserve_total_MW=tot, reserve_req_rhs_MW=rhs, reserve_req_dual=dual, thermal_reserve_MW=rt.sum(axis=1).values,
            bess_reserve_MW=rs.sum(axis=1).values if rs.shape[1] else 0.0, thermal_online_cap_MW=oc.sum(axis=1).values,
            thermal_p_MW=gp.sum(axis=1).values, thermal_available_MW=avail.sum(axis=1).values,
            shortfall_vs_formal_MW=(formal - tot).clip(lower=0.0), formal_requirement_MW=formal), index=idx)
        out.update(thermal_online_cap=oc, thermal_reserve=rt, thermal_available_cap=avail)
        if rs.shape[1]:
            out['bess_reserve'] = rs
    except Exception as e:
        out['reserve_by_snapshot'] = f'{e.__class__.__name__}: {e}'[:300]
    return out
