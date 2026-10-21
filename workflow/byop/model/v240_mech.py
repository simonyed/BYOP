#!/usr/bin/env python3
"""v2.4.0 ERCOT mechanism model: static multi-period S0-S3 LP with the E01-E05 repairs (continuous LP only).

Derived from work_package_v2/tools/m2_public_response.py (v2.3.0, VALID M2/M4 runs); the diff is kept in
patches_v240/. Run from pypsa-usa/workflow with the PyPSA-USA venv (L2):
    python byop/model/v240_mech.py --case-id X --out results/BYOP/<case> [options]

Switches (each experiment changes one of them against a named BASE):
  --periods annual|2y       E02: annual investment periods start..end (fractional first-year COD for BYOP / reuse)
                            vs the v2.3.0 2-year periods 2028/2030/2032 (old first_period folding)
  --cost-basis legacy|repaired
        legacy   (v2.3.0): public candidates at PyPSA-USA ATB Moderate-Market annuity (wacc_real 4.4-5.4 %, incl.
                 27 % ITC on solar/battery and discounted PTC on onwind); BYOP at private WACC 7 % in every
                 scenario (also S3); years undiscounted.
        repaired (E01): every decision-maker except the developer sees SOCIAL resource cost: raw overnight CAPEX
                 re-annualised at r_s (2 %) over the same economic life + FOM, tax credits removed (or kept with
                 --public-subsidy with, sensitivity); objective years discounted at r_s; the S2 developer uses 7 %
                 annuity, 7 % year weights and pays the grid at LMP (+ capacity adder under --tariff energy_erm).
  --tariff energy|energy_erm  E04: S2 developer grid price = S1 LMP, or LMP + (1+ERM) x ERM dual (cost reflective)
  --reuse off|on            E05: continuous life-extension R of ReEDS-retiring gas units in the DC zones; one right
                            per unit: R_pub (zone bus, public ERM credit) + R_dc (dedicated, DC bus) <= unit MW
  --bg-growth g, --no-line-exp, --poi-lead L, --erm15   E03 physical / administrative bottleneck switches
Scenarios: S0, S1, S1_zero (D=0 check), S3, S3_mS1 (S3 with S fixed to S1), S2 (developer LP -> fixed K -> public
LP), S2_off (K=0 check), S3_mS2 (S3 with S fixed to S2 service: matched-service efficiency gap).
Outputs per case dir: ledger.csv (two books per asset), scenario_summary.csv, service.csv, builds.csv, duals.csv,
prices_<scen>.csv.gz, case_manifest.json, events.jsonl, solver_<scen>.log
"""
from __future__ import annotations

import argparse, copy, hashlib, json, logging, math, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

HERE = Path(__file__).resolve().parent
V2T = HERE                      # restructure 2026-10-20: wp2_* live next to this file (pypsa-usa/workflow/byop/model)
sys.path.insert(0, str(V2T))
import byop_paths as BP  # noqa: E402
import wp2_ercot_s0_s1 as w2  # noqa: E402
import wp2_ercot_s1_real as s1r  # noqa: E402

BASE = BP.BASE_7ZONE
TECH = BP.TECH
ZONES = ['p60', 'p61', 'p62', 'p63', 'p64', 'p65', 'p67']
DC_ZONES = ['p63', 'p64', 'p65']
GAS = 3.19
PRIVATE_WACC = 0.07
SOCIAL_R = 0.02
BYOP_LIFE = {'RICE': 25, 'SOFC_NG': 15, 'OCGT_aero': 30, 'CCGT': 30, 'WIND': 30, 'PV': 30, 'BESS': 15}   # WIND / PV: PyPSA-USA candidate life (set in rearch configure)
IDLE = s1r.IDLE
SHED_COST = 1e4
SNAP_HOURS = 3.0
LINE_LEADS = {'low': 3, 'base': 4, 'high': 6}
PUBLIC = {'solar': ('solar', 'Generator'), 'onwind': ('onwind', 'Generator'), 'OCGT': ('OCGT', 'Generator'),
          'CCGT': ('CCGT', 'Generator'), '4hr_battery_storage': ('battery_4h', 'StorageUnit'),
          '8hr_battery_storage': ('battery_8h', 'StorageUnit')}
# PyPSA-USA cost build (costs_2030.csv, ATB 2024 Moderate / Market; add_extra_components.apply_itc/apply_ptc):
# capital_cost = (annualised_capex(wacc_real, life) * location + FOM) * (1 - 0.9 * ITC); onwind mc -= discounted PTC
ATB_WACC = {'solar': 0.044, 'onwind': 0.052, 'OCGT': 0.054, 'CCGT': 0.054, '4hr_battery_storage': 0.044,
            '8hr_battery_storage': 0.044}
ATB_FOM = {'solar': 17991.0, 'onwind': 29264.0, 'OCGT': 25000.0, 'CCGT': 31800.0, '4hr_battery_storage': 32504.0,
           '8hr_battery_storage': 57073.0}            # USD/MW-yr (opex_fixed_per_kw x 1000)
ITC = {'solar': 0.27, '4hr_battery_storage': 0.27, '8hr_battery_storage': 0.27}   # 0.9 x 30 % (monetisation 10 %)
# R (E05): life extension of a ReEDS-retiring unit. PROVISIONAL bounds (RESEARCH_ASSUMPTION, PENDING_SITE_EVIDENCE):
# one-off refurbishment USD/kW over the extension life + sustaining capex + FOM (USD/kW-yr). Anchors: EIA/S&L 2019
# "Generating Unit Annual Capital and Life Extension Costs" (gas/oil steam annual capex by size tier; total O&M
# ~10-70 2017$/kW-yr), coal regression 16.5+0.126*age $/kW-yr as an ageing analogue. Not unit-specific.
REUSE = {'low': dict(refurb=50.0, sustain=10.0, fom=25.0, lead=1.0),
         'base': dict(refurb=150.0, sustain=15.0, fom=35.0, lead=1.0),
         'high': dict(refurb=400.0, sustain=25.0, fom=50.0, lead=2.0)}
REUSE_LIFE = 10
REUSE_R = 1.25            # redundancy for a dedicated reused unit (same as RICE base; RESEARCH_ASSUMPTION)
REUSE_CARRIERS = ['gas_steam', 'CCGT', 'OCGT']
logger = logging.getLogger('v240')

BG_TRAJ_DEFAULT = BP.BG_LOAD_GROWTH   # LOAD-GROWTH-03 (AEO2023 Reference only)
ZONE_STATE = {z: 'TX' for z in ['p48', 'p60', 'p61', 'p62', 'p63', 'p64', 'p65', 'p67']}   # national: zone -> owning state
CFG = dict(bg_traj=str(BG_TRAJ_DEFAULT), tv_share_byop=1.0, tv_share_public=1.0, periods='annual', start=2026, end=2033, decision_year=2026, years=1, cost_basis='repaired',
           public_subsidy='without', tariff='energy', reuse='on', reuse_case='base', frac_cod=True, flex=True,
           poi_lead=0, byop_case='base', public_case='base', byop_techs=['RICE', 'SOFC_NG'], sample_weeks=4,
           bg_growth=0.0, line_exp=True, erm15=False, threads=4, social_r=SOCIAL_R, private_wacc=PRIVATE_WACC,
           v=2.8e6, v_private=None, dem_scale=1.0, smoke=False,
           # Mainline v1.3 switches (default off = v2.4.0 / rearch v1.0 behaviour, kept for regression):
           gas_by_year=None,        # {year: USD/MMBtu HHV, 2025$} (D2.b); None = flat GAS
           tech_v13=None,           # path of MAINLINE_V13_TECH_DEFAULTS.csv for the DC_BTM techs (D2.a); None = TECH-01
           firm_full_year=False)    # D1: firm credit only for capacity in operation the whole year (energy keeps fractions)
STATE = {}
# Mainline v1.3 D2.a: model carrier <- v1.3 technology id; firm redundancy r (failure-case firm credit 1/r) is not in the
# v1.3 table and stays the TECH-01 base value (transparent reliability proxy); WIND / PV / BESS carry no firm credit
V13_ID = {'RICE': 'RICE_50DF', 'SOFC_NG': 'SOFC_NG_STANDARD', 'OCGT_aero': 'OCGT_AERO', 'WIND': 'WIND_ONSHORE',
          'PV': 'PV_TRACKING', 'BESS': 'BESS_4H'}
NONFIRM_BYOP = {'WIND', 'PV', 'BESS'}
SOFC_FAST_ELIGIBLE_MW = 0.0      # D14: no verified pre-procured fast SOFC slot -> the fast SOFC technology is not offered


def gas_price(p=None):
    """USD/MMBtu (HHV, 2025$) in year p: v1.3 AEO2026 WSC series when set, else the flat v2.4.0 GAS"""
    g = CFG.get('gas_by_year')
    if not g or p is None:
        return GAS
    return float(g.get(int(p), g[max(k for k in g if k <= p)] if any(k <= p for k in g) else g[min(g)]))


def approval_cohorts(lead, floor=None, q0=None):
    """D1 investment cohorts: approval year q = decision_year .. last period, COD(q) = max(q + lead, floor);
    returns [(q, cod, build_period)] with one entry per distinct COD inside the window (earliest approval kept).
    A 2-year asset approved in 2029 has COD 2031: it cannot dispatch in 2029 / 2030."""
    out, seen = [], set()
    for q in range(int(q0 if q0 is not None else CFG['decision_year']), periods()[-1] + 1):
        cod = q + float(lead)
        if floor is not None:
            cod = max(cod, float(floor))
        bp = first_period(cod)
        if bp is None or round(cod, 6) in seen:
            continue
        seen.add(round(cod, 6))
        out.append((q, cod, bp))
    return out


def firm_frac(build_period, cod, p):
    """D1 firm qualification: 1 only if the asset operates the whole year p (partial years give energy, not firm)"""
    f = avail_frac(build_period, cod, p)
    return f if not CFG.get('firm_full_year') else (1.0 if f >= 1.0 - 1e-9 else 0.0)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def crf(r, n):
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def tech():
    return pd.read_csv(TECH)


def periods():
    if CFG.get('period_list'):
        return list(CFG['period_list'])
    if CFG['periods'] == '2y':
        return [2028, 2030, 2032]
    return list(range(CFG['start'], CFG['end'] + 1))


def years():
    return 2 if CFG['periods'] == '2y' else 1


def years_p(p):
    """years represented by period p (milestone periods 2040/2045/2050 carry 5 years each)"""
    return float(CFG.get('period_years', {}).get(p, years()))


def df(p, r):
    """discount factor to the decision year (start of year convention)"""
    return (1 + r) ** -(p - CFG['decision_year'])


def w_social(p):
    return years_p(p) * (1.0 if CFG['cost_basis'] == 'legacy' else df(p, CFG['social_r']))


def w_private(p):
    return years_p(p) * (1.0 if CFG['cost_basis'] == 'legacy' else df(p, CFG['private_wacc']))


def first_period(cod):
    """first period whose year can host an asset with (possibly fractional) COD; annual: floor(COD) when
    fractional COD is on (partial first-year availability), else ceil(COD); 2y: old M2 folding"""
    P = periods()
    if CFG['periods'] == '2y':
        return min([p for p in P if p >= cod], default=None)
    y = math.floor(cod + 1e-9) if CFG['frac_cod'] else math.ceil(cod - 1e-9)
    return min([p for p in P if p >= y], default=None)


def avail_frac(build_period, cod, p):
    """share of year p an asset built (committed) for period build_period with COD cod is available"""
    if p < build_period:
        return 0.0
    if CFG['periods'] == '2y' or not CFG['frac_cod']:
        return 1.0
    return float(np.clip(p + 1 - max(cod, build_period), 0.0, 1.0))


def tv_factor(build_period, life, kind, actor='social'):
    """E02 explicit end-of-window residual value. The LP pays capital_cost in every active in-window period (annuity
    method => implicit residual value = PV of the remaining annuities, share theta = 1). With theta < 1 the remaining
    out-of-window annuities are charged at (1 - theta) inside the window: capital_cost is scaled by
    k = 1 + (1 - theta) * R / A, A = sum of in-window objective weights of active periods, R = discounted years beyond
    the window up to end of life. kind: 'byop' (dedicated assets) or 'public'."""
    theta = CFG.get('tv_share_byop' if kind == 'byop' else 'tv_share_public', 1.0)
    if theta >= 1.0 or CFG['periods'] == '2y':
        return 1.0
    P = periods(); end = P[-1]
    w = w_private if actor == 'private' else w_social
    r = CFG['private_wacc'] if (actor == 'private' or CFG['cost_basis'] == 'legacy') else CFG['social_r']
    A = sum(w(p) for p in P if build_period <= p < build_period + life)
    R = sum(df(y, r) for y in range(end + 1, int(build_period + life)))
    return 1.0 + (1.0 - theta) * R / A if A > 0 else 1.0


# ------------------------------------------------------------------------------------------------ cost bases
def public_costs(car, cc_net, life, mc_net):
    """returns dict(decision cc, decision mc, social cc (unsubsidised, r_s), subsidy cc, ptc mc) per MW-yr"""
    itc = ITC.get(car, 0.0)
    fom = ATB_FOM[car]
    unsub = cc_net / (1 - itc)
    capex_ann = unsub - fom
    overnight = capex_ann / crf(ATB_WACC[car], life)
    ptc = 0.0
    if car == 'onwind':
        eff = 0.9 * 27.5
        r = ATB_WACC[car]
        ptc = round(eff * (1 - (1 + r) ** -10) / r * crf(r, life), 2)
    soc = overnight * crf(CFG['social_r'], life) + fom
    out = dict(overnight_per_MW=overnight, fom=fom, itc=itc, ptc=ptc, cc_market_sub=cc_net, mc_market_sub=mc_net,
               cc_social=soc, mc_social=mc_net + ptc, cc_social_sub=soc * (1 - itc), mc_social_sub=mc_net)
    if CFG['cost_basis'] == 'legacy':
        out.update(cc_dec=cc_net, mc_dec=mc_net)
    elif CFG['public_subsidy'] == 'with':
        out.update(cc_dec=out['cc_social_sub'], mc_dec=out['mc_social_sub'])
    else:
        out.update(cc_dec=soc, mc_dec=mc_net + ptc)
    return out


def byop_params_v13(carrier, actor):
    """D2.a: v1.3 default table (2025$, CAPEX USD/kW net AC, FOM USD/kW-yr, VOM USD/MWh, HR Btu_HHV/kWh, lead y);
    firm redundancy r from TECH-01 base for the gas techs (failure-case firm credit only, never normal dispatch)"""
    t = pd.read_csv(CFG['tech_v13']).set_index('technology')
    r = t.loc[V13_ID[carrier]]
    cap = float(r.capex_2025USD_per_kW_netAC) * 1000
    fom = float(r.fom_2025USD_per_kW_year) * 1000
    life = BYOP_LIFE[carrier]
    rate = CFG['private_wacc'] if (actor == 'private' or CFG['cost_basis'] == 'legacy') else CFG['social_r']
    hr = float(r.heat_rate_BtuHHV_per_kWh_e) if r.heat_rate_BtuHHV_per_kWh_e == r.heat_rate_BtuHHV_per_kWh_e else 0.0
    vom = float(r.vom_2025USD_per_MWh_e)
    if carrier in NONFIRM_BYOP:
        red = float('inf')
    else:
        t1 = tech()
        red = float(t1[(t1.carrier == carrier) & (t1.boundary == 'DC_BTM')].iloc[0][f"redundancy_factor_{CFG['byop_case']}"])
    lead = float(r.reference_lead_years)
    return dict(carrier=carrier, case='v13', overnight_per_MW=cap, fom=fom, life=life, annual=cap * crf(rate, life) + fom, rate=rate,
                annual_social=cap * crf(CFG['social_r'], life) + fom, annual_private=cap * crf(CFG['private_wacc'], life) + fom,
                mc=hr / 1000 * GAS + vom, hr=hr, vom=vom, r=red, lead=lead, cod=CFG['decision_year'] + lead,
                first_period=first_period(CFG['decision_year'] + lead), evidence=str(r.evidence_class),
                max_hours=float(r.storage_duration_h) if r.storage_duration_h == r.storage_duration_h else None,
                eta_rt=float(r.storage_roundtrip_efficiency) if r.storage_roundtrip_efficiency == r.storage_roundtrip_efficiency else None)


def byop_params(carrier, actor):
    """actor: 'social' (S3 / social ledger) or 'private' (S2 developer / private ledger)"""
    if CFG.get('tech_v13'):
        return byop_params_v13(carrier, actor)
    r = tech()
    r = r[(r.carrier == carrier) & (r.boundary == 'DC_BTM')].iloc[0]
    k = CFG['byop_case']
    cap = float(r[f'capital_USD_kW_{k}']) * 1000
    fom = float(r.fom_USD_kWyr) * 1000
    life = BYOP_LIFE[carrier]
    rate = CFG['private_wacc'] if (actor == 'private' or CFG['cost_basis'] == 'legacy') else CFG['social_r']
    annual = cap * crf(rate, life) + fom
    mc = float(r.heat_rate_Btu_kWh) / 1000 * GAS + float(r.variable_USD_MWh)
    lead = float(r[f'lead_years_{k}'])
    cod = CFG['decision_year'] + lead
    return dict(carrier=carrier, case=k, overnight_per_MW=cap, fom=fom, life=life, annual=annual, rate=rate,
                annual_social=cap * crf(CFG['social_r'], life) + fom, annual_private=cap * crf(CFG['private_wacc'], life) + fom,
                mc=mc, r=float(r[f'redundancy_factor_{k}']), lead=lead, cod=cod, first_period=first_period(cod))


def reuse_params(actor):
    c = REUSE[CFG['reuse_case']]
    if actor == 'private':
        rate = CFG['private_wacc']
    elif actor == 'legacy':           # public utility extension under the v2.3.0 market basis (ATB gas wacc_real)
        rate = ATB_WACC['CCGT']
    else:
        rate = CFG['social_r'] if CFG['cost_basis'] == 'repaired' else CFG['private_wacc']
    ann = lambda r_: (c['refurb'] * crf(r_, REUSE_LIFE) + c['sustain'] + c['fom']) * 1000
    return dict(annual=ann(rate), rate=rate, annual_social=ann(CFG['social_r']), annual_private=ann(CFG['private_wacc']), **c)


# ------------------------------------------------------------------------------------------------ network
def to_multiperiod(n):
    P = periods()
    ts = n.snapshots.get_level_values('timestep')
    new = pd.MultiIndex.from_product([P, ts], names=['period', 'timestep'])
    saved = {}
    for lst in ['generators', 'loads', 'storage_units', 'links', 'buses', 'stores', 'lines']:
        for attr, d in getattr(n, lst + '_t').items():
            if isinstance(d, pd.DataFrame) and not d.empty:
                saved[(lst, attr)] = d.copy()
    sw = n.snapshot_weightings.copy()
    n.set_snapshots(new)
    n.investment_periods = P
    for (c, attr), d in saved.items():
        getattr(n, c + '_t')[attr] = pd.DataFrame(np.tile(d.values, (len(P), 1)), index=new, columns=d.columns)
    n.snapshot_weightings = pd.DataFrame(np.tile(sw.values, (len(P), 1)), index=new, columns=sw.columns)
    n.investment_period_weightings.loc[:, 'years'] = [years_p(p) for p in P]
    n.investment_period_weightings.loc[:, 'objective'] = [w_social(p) for p in P]
    return n


def tile(series_one_year):
    return np.tile(np.asarray(series_one_year), len(periods()))


def add_public_candidates(n, templ_g, templ_s, prof):
    t = tech().set_index(['carrier', 'boundary'])
    offered, costrows = [], []
    P = periods()
    for z in ZONES:
        for car, (tc, comp) in PUBLIC.items():
            row = t.loc[(tc, 'UTILITY' if comp == 'Generator' else 'UTILITY_AND_DC_BTM')]
            lead = float(row[f"lead_years_{CFG['public_case']}"])
            p0 = first_period(CFG['decision_year'] + lead)
            tg = templ_g if comp == 'Generator' else templ_s
            cand = tg[(tg.bus == z) & (tg.carrier == car)]
            for _, t0 in cand.iterrows():
                if car in ('CCGT', 'OCGT'):
                    mc_net = float(row.heat_rate_Btu_kWh) / 1000 * GAS + float(row.variable_USD_MWh)
                else:
                    mc_net = float(t0.marginal_cost)
                pc = public_costs(car, float(t0.capital_cost), float(t0.lifetime), mc_net)
                for p in P:
                    if p0 is None or p < p0:
                        continue
                    name = f'{z} {car} pub{p}' if len(cand) == 1 else f'{t0.name} pub{p}'
                    if comp == 'Generator':
                        kw = dict(bus=z, carrier=car, p_nom=0.0, p_nom_extendable=True, p_nom_max=float(t0.p_nom_max),
                                  capital_cost=pc['cc_dec'] * tv_factor(p, float(t0.lifetime), 'public'), marginal_cost=pc['mc_dec'],
                                  build_year=p, lifetime=float(t0.lifetime))
                        if car in ('CCGT', 'OCGT'):
                            kw.update(efficiency=float(row.efficiency), p_max_pu=1.0)
                        n.add('Generator', name, **kw)
                        if t0.name in prof:
                            n.generators_t.p_max_pu[name] = tile(prof[t0.name])
                    else:
                        n.add('StorageUnit', name, bus=z, carrier=car, p_nom=0.0, p_nom_extendable=True,
                              capital_cost=pc['cc_dec'] * tv_factor(p, float(t0.lifetime), 'public'), max_hours=float(t0.max_hours),
                              efficiency_store=float(t0.efficiency_store), efficiency_dispatch=float(t0.efficiency_dispatch),
                              cyclic_state_of_charge=True, build_year=p, lifetime=float(t0.lifetime),
                              marginal_cost=float(t0.marginal_cost))
                    offered.append(dict(zone=z, carrier=car, period=p, first_period=p0, lead=lead,
                                        earliest_COD=CFG['decision_year'] + lead))
                    costrows.append(dict(name=name, component=comp, zone=z, carrier=car, build_year=p,
                                         life=float(t0.lifetime), **pc))
    STATE['public_cost_table'] = pd.DataFrame(costrows)
    return offered


def add_line_expansion(n):
    lead = LINE_LEADS[CFG['public_case']]
    p0 = first_period(CFG['decision_year'] + lead)
    corridors = []
    fwd = n.links[(n.links.carrier == 'AC') & n.links.index.str.endswith('_fwd')]
    for name, l in fwd.iterrows():
        rev = name.replace('_fwd', '_rev')
        cap = 0.5 * (float(l.p_nom) + float(n.links.p_nom.get(rev, l.p_nom)))
        if not CFG['line_exp']:
            cap = 0.0
        base = name[:-4]
        for p in periods():
            if p0 is None or p < p0:
                continue
            n.add('Link', f'{base}_exp{p}_fwd', bus0=l.bus0, bus1=l.bus1, carrier='AC_exp', p_nom=0.0,
                  p_nom_extendable=True, p_nom_max=cap, capital_cost=float(l.capital_cost), efficiency=float(l.efficiency),
                  build_year=p, lifetime=60, length=float(l.length))
            n.add('Link', f'{base}_exp{p}_rev', bus0=l.bus1, bus1=l.bus0, carrier='AC_exp', p_nom=0.0,
                  p_nom_extendable=True, p_nom_max=cap, capital_cost=0.0, efficiency=float(l.efficiency),
                  build_year=p, lifetime=60, length=float(l.length))
        corridors.append(dict(corridor=base, cap_MW=cap, capital_cost_per_MW_yr=float(l.capital_cost), first_period=p0,
                              bus0=l.bus0, bus1=l.bus1, existing_MW=float(l.p_nom)))
    if 'AC_exp' not in n.carriers.index:
        n.add('Carrier', 'AC_exp', co2_emissions=0.0)
    STATE['corridors'] = corridors
    return corridors


def study_new_demand(scale=None):
    scale = CFG['dem_scale'] if scale is None else scale
    if s1r.COHORTS is None:
        raise SystemExit('DC cohorts not set: the PNNL-based 7-zone / county cohorts were deleted (RA-DC-SPATIAL-04); '
                         'use rearch_mech.py (POI cohorts, --regional-dc epoch_hybrid) or provide a new spatial basis')
    coh = pd.read_csv(s1r.COHORTS)
    coh = coh[coh.scenario == 'mid']
    rows = []
    Y = years()
    for z in sorted(coh.region_id.unique()):
        c = coh[coh.region_id == z]
        canc = CFG.get('cancel')   # {'from_request_year': y0, 'share': s, 'effective_year': y1} (labelled scenario)
        for p in periods():
            it = c.IT_MW.copy()
            if canc and p >= canc['effective_year']:
                it = it.where(c.request_year < canc['from_request_year'], it * (1 - canc['share']))
            D = float((it * np.clip((p + Y - c.request_year) / Y, 0, 1)).sum()) * scale
            G = float((it * np.clip((p + Y - (c.request_year + CFG['poi_lead'])) / Y, 0, 1)).sum()) * scale
            rows.append(dict(zone=z, period=p, D_IT_MW=D, G_IT_MW=G))
    return pd.DataFrame(rows)


def reuse_pool(n):
    """ReEDS-retiring gas units in the DC zones whose retirement falls inside the horizon (age-based, not announced)."""
    g = n.generators
    x = g[~g.p_nom_extendable & g.bus.isin(DC_ZONES) & g.carrier.isin(REUSE_CARRIERS)]
    x = x[(x.build_year + x.lifetime) <= periods()[-1]]
    rows = []
    for name, r in x.iterrows():
        rows.append(dict(asset_id=name, zone=r.bus, carrier=r.carrier, MW=float(r.p_nom), retire_year=int(r.build_year + r.lifetime),
                         marginal_cost=float(r.marginal_cost), efficiency=float(r.efficiency),
                         p_max_pu=float(r.p_max_pu) if np.isfinite(r.p_max_pu) else 1.0,
                         source='ReEDS age-based RetireYear (baseline_2025 fleet), PENDING_SITE_EVIDENCE'))
    return pd.DataFrame(rows)


def add_reuse(n, dedicated, rfixed=None):
    """R_pub (public) and optionally R_dc (dedicated) continuous life-extension candidates; rights constraint added in
    extra(). rfixed: {asset_id: MW} fixed dedicated R from the S2 developer stage."""
    pool = reuse_pool(n)
    STATE['reuse'] = []
    if pool.empty:
        return pool
    for c in ['reuse_pub', 'byop_R']:
        if c not in n.carriers.index:
            n.add('Carrier', c, co2_emissions=0.0)
    rp_pub = reuse_params('social' if CFG['cost_basis'] == 'repaired' else 'legacy')
    rp_dc = reuse_params('social')
    for r in pool.itertuples():
        cod = max(r.retire_year, CFG['decision_year'] + rp_pub['lead'])
        bp = first_period(cod)
        if bp is None:
            continue
        pub = f'{r.asset_id} Rpub'
        n.add('Generator', pub, bus=r.zone, carrier='reuse_pub', p_nom_extendable=True, p_nom_max=r.MW,
              capital_cost=rp_pub['annual'], marginal_cost=r.marginal_cost, efficiency=r.efficiency, p_max_pu=r.p_max_pu,
              build_year=bp, lifetime=REUSE_LIFE)
        ent = dict(asset_id=r.asset_id, zone=r.zone, MW=r.MW, retire_year=r.retire_year, COD=cod, build_period=bp,
                   pub=pub, dc=None, carrier=r.carrier)
        if dedicated or rfixed is not None:
            dcn = f'DC_{r.zone} BYOP R {r.asset_id}'
            kw = dict(bus=f'DC_{r.zone}', carrier='byop_R', capital_cost=rp_dc['annual'], marginal_cost=r.marginal_cost,
                      p_max_pu=1.0 / REUSE_R, build_year=bp, lifetime=REUSE_LIFE)
            if rfixed is not None:
                kw.update(p_nom=rfixed.get(r.asset_id, 0.0), p_nom_extendable=False)
            else:
                kw.update(p_nom_extendable=True, p_nom_max=r.MW)
            if f'DC_{r.zone}' in n.buses.index:
                n.add('Generator', dcn, **kw)
                ent['dc'] = dcn
        STATE['reuse'].append(ent)
    return pool


def add_dc(n, dem, v, mult, byop=None, byop_fixed=None, price=None, s_fixed=None, actor='social'):
    """DC facility per zone (as v2.3.0 M2) with fractional-COD BYOP and actor-specific cost basis.
    byop_fixed: {(zone, carrier, period): MW}; price: {zone: Series USD/MWh} -> grid is a price taker supply."""
    pue_t = w2.PUE
    par_t = pd.read_csv(s1r.TASK).set_index('year')
    for c in ['POI', 'compute_IT', 'AIDC_training', 'grid_purchase']:
        if c not in n.carriers.index:
            n.add('Carrier', c, co2_emissions=0.0)
    STATE['dc'] = []
    m1 = np.asarray(mult)
    Y = years()
    for z in sorted(dem.zone.unique()):
        dc = f'DC_{z}'
        if dc not in n.buses.index:
            zb = n.buses.loc[z] if z in n.buses.index else None
            n.add('Bus', dc, carrier='AC', x=0 if zb is None else zb.x, y=0 if zb is None else zb.y,
                  country='DC', reeds_zone='DC', reeds_state='DC', interconnect='dc_facility', nerc_reg='DC')
        for r in dem[dem.zone == z].itertuples():
            p = r.period
            pue = float(pue_t[(pue_t.st == 'TX') & (pue_t.year == min(p, 2035))].pue.iloc[0])
            par = par_t.loc[min(p, 2035)]
            inf_pu = float(par.infer_share * par.infer_util)
            fixed_pu = pue * (IDLE + (1 - IDLE) * inf_pu * m1)
            head = np.clip(1 - inf_pu * m1, 0, None)
            sname = f'{dc} S{p}'
            ppu = pd.Series(0.0, index=n.snapshots)
            ppu.loc[p] = fixed_pu
            n.add('Generator', sname, bus=dc, carrier='compute_IT', sign=-1, p_nom_extendable=True, p_nom_min=0.0,
                  p_nom_max=r.D_IT_MW, capital_cost=-v, marginal_cost=0.0, build_year=p, lifetime=Y)
            n.generators_t.p_max_pu[sname] = ppu.values
            n.generators_t.p_min_pu[sname] = ppu.values
            if s_fixed is not None:
                n.generators.loc[sname, ['p_nom_min', 'p_nom_max']] = min(s_fixed.get((z, p), 0.0), r.D_IT_MW)
            tname = f'{dc} train{p}'
            hpu = pd.Series(0.0, index=n.snapshots); hpu.loc[p] = head
            n.add('Generator', tname, bus=dc, carrier='AIDC_training', sign=-1, p_nom_extendable=True,
                  capital_cost=0.0, marginal_cost=0.0, build_year=p, lifetime=Y)
            n.generators_t.p_max_pu[tname] = hpu.values
            daily = pue * (1 - IDLE) * 24 * float(par.train_share * par.train_util)
            ent = dict(zone=z, period=p, S=sname, T=tname, pue=pue, daily=daily, D=r.D_IT_MW, G=r.G_IT_MW, firm=None, nf=None)
            STATE['dc'].append(ent)
            # FLEX-01 flexible interconnection: grid draw = firm part (charged (1+ERM) in the zone ERM row, ERM-DC-01 B)
            # + non-firm part (not in any ERM row) that must be backed at every snapshot by dedicated firm capacity
            # (extra(): p_nonfirm + sum p_byop <= sum f K / r). Only where the developer has dedicated supply (S2/S3).
            flex = CFG.get('flex') and (byop or byop_fixed is not None)
            if price is None:
                n.add('Link', f'POI {z} {p}', bus0=z, bus1=dc, carrier='POI', p_nom=pue * r.G_IT_MW, efficiency=1.0,
                      p_nom_extendable=False, build_year=p, lifetime=Y, marginal_cost=0.0, capital_cost=0.0)
                ent['firm'] = ('Link', f'POI {z} {p}')
                if flex:
                    if 'POI_nonfirm' not in n.carriers.index:
                        n.add('Carrier', 'POI_nonfirm', co2_emissions=0.0)
                    n.add('Link', f'POInf {z} {p}', bus0=z, bus1=dc, carrier='POI_nonfirm', p_nom=pue * r.G_IT_MW, efficiency=1.0,
                          p_nom_extendable=False, build_year=p, lifetime=Y, marginal_cost=0.0, capital_cost=0.0)
                    ent['nf'] = ('Link', f'POInf {z} {p}')
            else:
                gname = f'{dc} grid{p}'
                n.add('Generator', gname, bus=dc, carrier='grid_purchase', p_nom=pue * r.G_IT_MW,
                      p_nom_extendable=False, build_year=p, lifetime=Y, marginal_cost=0.0)
                n.generators_t.marginal_cost[gname] = price[z].values
                ent['firm'] = ('Generator', gname)
                if flex:   # developer stage: non-firm grid energy at the energy price only (no capacity adder)
                    if 'grid_nonfirm' not in n.carriers.index:
                        n.add('Carrier', 'grid_nonfirm', co2_emissions=0.0)
                    nfn = f'{dc} gridnf{p}'
                    n.add('Generator', nfn, bus=dc, carrier='grid_nonfirm', p_nom=pue * r.G_IT_MW,
                          p_nom_extendable=False, build_year=p, lifetime=Y, marginal_cost=0.0)
                    n.generators_t.marginal_cost[nfn] = STATE.get('lmp_energy', price)[z].values
                    ent['nf'] = ('Generator', nfn)
            for car in (byop or []):
                bp = byop_params(car, actor)
                if bp['first_period'] is None or p < bp['first_period']:
                    continue
                bname = f'{dc} BYOP {car} {p}'
                if f'byop_{car}' not in n.carriers.index:
                    n.add('Carrier', f'byop_{car}', co2_emissions=0.0)
                ppu_b = pd.Series(0.0, index=n.snapshots)
                for q in periods():
                    ppu_b.loc[q] = avail_frac(p, bp['cod'], q) / bp['r'] if q >= p else 0.0
                kw = dict(bus=dc, carrier=f'byop_{car}', capital_cost=bp['annual'] * tv_factor(p, BYOP_LIFE[car], 'byop', actor), marginal_cost=bp['mc'],
                          build_year=p, lifetime=BYOP_LIFE[car])
                if byop_fixed is not None:
                    kw.update(p_nom=byop_fixed.get((z, car, p), 0.0), p_nom_extendable=False)
                else:
                    kw.update(p_nom_extendable=True, p_nom_max=pue * r.D_IT_MW * bp['r'] * 2.0)
                n.add('Generator', bname, **kw)
                n.generators_t.p_max_pu[bname] = ppu_b.values
                STATE.setdefault('byop_cod', {})[bname] = dict(cod=bp['cod'], build=p, r=bp['r'], carrier=car, zone=z)


def extra(n, snapshots):
    m = n.model
    if STATE.get('erm'):
        w2.extra_functionality_erm_dc(n, snapshots)
        for reg in w2.ERM_REGIONS:
            name = f'GlobalConstraint-{reg}_ERM'
            if name not in m.constraints:
                continue
            c = m.constraints[name]
            shed = n.generators[n.generators.carrier == 'load_shed']
            add = xr.DataArray([float(shed.p_nom[shed.bus == b].sum()) for b in c.rhs.coords['Bus'].values],
                               coords={'Bus': c.rhs.coords['Bus'].values}, dims='Bus')
            lhs, rhs, mask = c.lhs, c.rhs + add, c.mask
            m.remove_constraints(name)
            m.add_constraints(lhs, '>=', rhs, name=name, mask=mask)
            cal = STATE.get('erm_cal')
            if cal is not None:
                c = m.constraints[name]
                buses = list(c.rhs.coords['Bus'].values)
                dem = (n.loads_t.p_set.T.groupby(n.loads.bus).sum().T).reindex(index=n.snapshots, columns=buses, fill_value=0.0)
                dims = c.rhs.dims
                da = lambda d_: c.rhs.copy(data=d_.values if dims[0] == 'snapshot' else d_.values.T)
                lhs, rhs, mask = c.lhs, c.rhs, c.mask
                per = n.snapshots.get_level_values(0)
                if cal == 'solve':
                    mv = m.add_variables(lower=-1.0, upper=w2.ERM_MARGIN, coords=[pd.Index(periods(), name='erm_period')],
                                         name='M2-erm_margin')
                    for p in periods():
                        Dp = dem.where(pd.Series(per == p, index=n.snapshots), 0.0, axis=0)
                        lhs = lhs - mv.sel(erm_period=p) * da(Dp)
                    rhs = rhs - w2.ERM_MARGIN * da(dem)
                    m.objective = m.objective.expression - 1e12 * mv.sum()
                else:
                    red = pd.Series([w2.ERM_MARGIN - cal.get(p, w2.ERM_MARGIN) for p in per], index=n.snapshots)
                    rhs = rhs - da(dem.mul(red, axis=0))
                m.remove_constraints(name)
                m.add_constraints(lhs, '>=', rhs, name=name, mask=mask)
    pnom = m['Generator-p_nom']
    gb = n.generators
    for d in STATE.get('dc', []):
        S = pnom.sel(name=d['S']); T = pnom.sel(name=d['T'])
        m.add_constraints(T - d['pue'] * (1 - IDLE) * S == 0, name=f"M2-train_cap_{d['T']}")
        sns = snapshots[snapshots.get_level_values(0) == d['period']]
        days = pd.Index(sns.get_level_values(1).normalize(), name='day')
        p = m['Generator-p'].sel(name=d['T'], snapshot=sns)
        wt = xr.DataArray(np.full(len(sns), SNAP_HOURS), coords={'snapshot': sns}, dims='snapshot')
        expr = (p * wt).groupby(xr.DataArray(days.values, coords={'snapshot': sns}, dims='snapshot', name='day')).sum()
        m.add_constraints(expr - d['daily'] * S == 0, name=f"M2-train_daily_{d['T']}")
        # served IT <= grid-ready IT (POI COD) + dedicated firm capacity in IT terms (fractional first-year COD)
        q = d['period']
        byop = gb.index[(gb.carrier.str.startswith('byop_')) & (gb.bus == f"DC_{d['zone']}")
                        & (gb.build_year <= q) & (gb.build_year + gb.lifetime > q)]
        coefs = {}
        for b in byop:
            info = STATE.get('byop_cod', {}).get(b)
            if gb.carrier[b][5:] in NONFIRM_BYOP:   # v1.3: wind / PV carry no firm credit (BESS is a StorageUnit)
                coefs[b] = 0.0
                continue
            if info is not None:
                f_ = firm_frac(info['build'], info['cod'], q); rr = info['r']
            else:   # reuse R or ledger asset
                f_ = 1.0; rr = REUSE_R if gb.carrier[b] == 'byop_R' else float(STATE.get('ledger_r', {}).get(b, 1.25))
            coefs[b] = f_ / (rr * d['pue'])
        ext = [b for b in byop if gb.p_nom_extendable[b] and coefs[b] > 0]
        fixed_firm = sum(float(gb.p_nom[b]) * coefs[b] for b in byop if not gb.p_nom_extendable[b])
        lhs = S
        if ext:
            coef = xr.DataArray([coefs[b] for b in ext], coords={'name': ext}, dims='name')
            lhs = S - (pnom.sel(name=ext) * coef).sum('name')
        m.add_constraints(lhs <= d['G'] + fixed_firm, name=f"M2-serve_cap_{d['S']}")
        if d.get('nf'):
            kind, nfname = d['nf']
            fkind, fname = d['firm']
            psel = lambda k, nm: m[f'{k}-p'].sel(name=nm, snapshot=sns)
            # total connection capacity shared by firm and non-firm draw
            m.add_constraints(psel(fkind, fname) + psel(kind, nfname) <= d['pue'] * d['G'], name=f"FLEX-conn_{d['S']}")
            # non-firm draw + dedicated output <= dedicated firm capacity (snapshot-wise)
            act = [b for b in byop if coefs.get(b, 0) > 0]
            lhs_nf = psel(kind, nfname)
            if act:
                lhs_nf = lhs_nf + m['Generator-p'].sel(name=act, snapshot=sns).sum('name')
            ext_a = [b for b in act if gb.p_nom_extendable[b]]
            fix_cap = sum(float(gb.p_nom[b]) * coefs[b] * d['pue'] for b in act if not gb.p_nom_extendable[b])
            if ext_a:
                capx = (pnom.sel(name=ext_a) * xr.DataArray([coefs[b] * d['pue'] for b in ext_a], coords={'name': ext_a}, dims='name')).sum('name')
                m.add_constraints(lhs_nf - capx <= fix_cap, name=f"FLEX-backing_{d['S']}")
            else:
                m.add_constraints(lhs_nf <= fix_cap, name=f"FLEX-backing_{d['S']}")
    # E05 rights: one physical unit, public extension + dedicated extension <= unit MW (never sold twice)
    for e in STATE.get('reuse', []):
        terms_ext = [x for x in [e['pub'], e['dc']] if x and x in gb.index and gb.p_nom_extendable[x]]
        fixed = sum(float(gb.p_nom[x]) for x in [e['pub'], e['dc']] if x and x in gb.index and not gb.p_nom_extendable[x])
        if terms_ext:
            m.add_constraints(pnom.sel(name=terms_ext).sum('name') <= e['MW'] - fixed, name=f"V240-reuse_right_{e['asset_id']}")
    if 'Link-p_nom' in m.variables and STATE.get('corridors'):
        lp = m['Link-p_nom']
        ext = set(n.links.index[n.links.p_nom_extendable])
        for c in STATE['corridors']:
            f = [f"{c['corridor']}_exp{p}_fwd" for p in periods() if f"{c['corridor']}_exp{p}_fwd" in ext]
            for name in f:
                m.add_constraints(lp.sel(name=name) - lp.sel(name=name.replace('_fwd', '_rev')) == 0, name=f'M2-line_sym_{name}')
            if f:
                m.add_constraints(lp.sel(name=f).sum('name') <= c['cap_MW'], name=f"M2-line_cap_{c['corridor']}")


def base_build(config):
    n = w2.base_network(config)
    if CFG['smoke']:
        n.set_snapshots(n.snapshots[:56])
    elif CFG['sample_weeks']:
        k = CFG['sample_weeks']; full = len(n.snapshots); sw0 = n.snapshot_weightings.copy()
        keep = [i for i in range(full) if (i // 56) % k == 0 and (i // 56) < full // 56]
        n.set_snapshots(n.snapshots[keep])
        n.snapshot_weightings = sw0.iloc[keep] * (full / len(keep))
    return n


def build(config, scen, v, byop=None, byop_fixed=None, s_fixed=None, reuse_dedicated=False, rfixed=None, dem_scale=None):
    n = base_build(config)
    g, su = n.generators, n.storage_units
    prof = {k: n.generators_t.p_max_pu[k].values[:len(n.snapshots)] for k in g.index if k in n.generators_t.p_max_pu}
    templ_g = g[g.p_nom_extendable & g.bus.isin(ZONES)].copy()
    templ_s = su[su.p_nom_extendable & su.bus.isin(ZONES)].copy()
    ex_links = n.links.index[~n.links.p_nom_extendable & n.links.carrier.isin(['AC', 'DC'])]
    n.links.loc[ex_links, 'build_year'] = 2025
    n.remove('Generator', templ_g.index)
    n.remove('StorageUnit', templ_s.index)
    mult = s1r.three_hour_multipliers(n).values
    n = to_multiperiod(n)
    if CFG.get('bg_traj') and CFG['bg_traj'] != 'none':   # LOAD-GROWTH-03: 2025 shape x annual state factor
        tr = pd.read_csv(CFG['bg_traj'])          # long format: state, year, factor_vs_2025 (48 states)
        per = n.snapshots.get_level_values(0)
        STATE['bg_factor_by_period'] = {}
        for st in sorted({ZONE_STATE[z] for z in ZONES}):
            fac_y = tr[tr.state == st].set_index('year').factor_vs_2025
            if fac_y.empty:
                raise SystemExit(f'bg_traj: no factors for state {st}')
            fac = np.array([float(fac_y.get(p, fac_y.iloc[-1])) for p in per])
            zl = n.loads.index[n.loads.bus.isin([z for z in ZONES if ZONE_STATE[z] == st])]
            n.loads_t.p_set.loc[:, zl] = n.loads_t.p_set.loc[:, zl].mul(fac, axis=0)
            STATE['bg_factor_by_period'][st] = {int(p): float(fac_y.get(p, fac_y.iloc[-1])) for p in periods()}
    if CFG['bg_growth']:
        per = n.snapshots.get_level_values(0)
        fac = np.array([(1 + CFG['bg_growth']) ** (p - 2025) for p in per])
        zl = n.loads.index[n.loads.bus.isin(ZONES)]
        n.loads_t.p_set.loc[:, zl] = n.loads_t.p_set.loc[:, zl].mul(fac, axis=0)
    for z in ZONES:
        n.add('Generator', f'{z} load_shed', bus=z, carrier='load_shed', p_nom=1e5, marginal_cost=SHED_COST,
              build_year=2025, lifetime=100)
    if 'load_shed' not in n.carriers.index:
        n.add('Carrier', 'load_shed', co2_emissions=0.0)
    STATE['offered'] = add_public_candidates(n, templ_g, templ_s, prof)
    add_line_expansion(n)
    STATE['dc'] = []; STATE['byop_cod'] = {}; STATE['reuse'] = []
    if scen != 'S0':
        dem = study_new_demand(scale=dem_scale)
        add_dc(n, dem, v, mult, byop=byop, byop_fixed=byop_fixed, s_fixed=s_fixed)
    if CFG['reuse'] == 'on':
        add_reuse(n, dedicated=reuse_dedicated and scen != 'S0', rfixed=rfixed if scen != 'S0' else None)
    return n, mult


def solve(config, tag, out, n):
    STATE['erm'] = True
    cfg = copy.deepcopy(config)
    for k_, o_ in cfg['solving'].get('solver_options', {}).items():
        if isinstance(o_, dict):
            o_['threads'] = CFG['threads']
    w2.sn.extra_functionality = extra
    return w2.solve(n, cfg, tag, out, erm_dc_mode='B')


# ------------------------------------------------------------------------------------------------ S2 developer
def private_stage(config, s1_net, v_priv, mult, reuse_on):
    """S2: per-zone developer LP on S1 zonal price (energy LMP, + capacity adder under energy_erm), private 7 %
    annuity and 7 % year weights; returns fixed BYOP K and dedicated R."""
    dem = study_new_demand()
    sw = s1_net.snapshot_weightings.generators
    ow = pd.Series([float(s1_net.investment_period_weightings.objective[p]) for p in s1_net.snapshots.get_level_values(0)],
                   index=s1_net.snapshots)
    K, R, out = {}, {}, []
    erm_p = s1_net.buses_t.get('erm_price')
    for z in sorted(dem.zone.unique()):
        n = pypsa.Network()
        n.set_snapshots(s1_net.snapshots)
        n.investment_periods = periods()
        n.snapshot_weightings = s1_net.snapshot_weightings.copy()
        n.investment_period_weightings = s1_net.investment_period_weightings.copy()
        n.investment_period_weightings.loc[:, 'objective'] = [w_private(p) for p in periods()]
        lmp = s1_net.buses_t.marginal_price[z].astype(float)
        adder = pd.Series(0.0, index=s1_net.snapshots)
        if CFG['tariff'] == 'energy_erm' and erm_p is not None and z in erm_p:
            mu = erm_p[z].astype(float).fillna(0.0)
            adder = (1 + w2.ERM_MARGIN) * mu.abs() / (sw * ow)
        price = {z: lmp + adder}
        STATE['lmp_energy'] = {z: lmp}
        add_dc(n, dem[dem.zone == z], v_priv, mult, byop=CFG['byop_techs'], price=price, actor='private')
        rs = []
        if reuse_on:
            for e in STATE.get('reuse_s1', []):
                if e['zone'] != z:
                    continue
                rp = reuse_params('private')
                dcn = f'DC_{z} BYOP R {e["asset_id"]}'
                if 'byop_R' not in n.carriers.index:
                    n.add('Carrier', 'byop_R', co2_emissions=0.0)
                n.add('Generator', dcn, bus=f'DC_{z}', carrier='byop_R', p_nom_extendable=True, p_nom_max=e['MW'],
                      capital_cost=rp['annual'], marginal_cost=e['mc'], p_max_pu=1.0 / REUSE_R,
                      build_year=e['build_period'], lifetime=REUSE_LIFE)
                rs.append((e['asset_id'], dcn))
        STATE['erm'] = False
        sv_reuse = STATE.get('reuse', []); STATE['reuse'] = []
        n.optimize(solver_name='gurobi', solver_options=dict(Method=2, Crossover=0, BarConvTol=1e-6, OutputFlag=0,
                   Threads=CFG['threads']), extra_functionality=extra, multi_investment_periods=True)
        STATE['reuse'] = sv_reuse
        STATE['erm'] = True
        for b in n.generators.index[n.generators.carrier.str.startswith('byop_') & (n.generators.carrier != 'byop_R')]:
            car = n.generators.carrier[b][5:]
            K[(z, car, int(n.generators.build_year[b]))] = float(n.generators.p_nom_opt[b])
        for aid, dcn in rs:
            R[aid] = float(n.generators.p_nom_opt[dcn])
        S = {int(n.generators.build_year[s]): float(n.generators.p_nom_opt[s]) for s in n.generators.index[n.generators.carrier == 'compute_IT']}
        w = n.snapshot_weightings.generators
        gp = n.generators.index[n.generators.carrier == 'grid_purchase']
        pay_e = sum(float((n.generators_t.p[gn] * lmp.values * w).groupby(level=0).sum().mul(pd.Series({p: w_private(p) for p in periods()})).sum()) for gn in gp)
        pay_c = sum(float((n.generators_t.p[gn] * adder.values * w).groupby(level=0).sum().mul(pd.Series({p: w_private(p) for p in periods()})).sum()) for gn in gp)
        out.append(dict(zone=z, private_objective=float(n.objective), termination=str(n.model.termination_condition),
                        integer_vars=int(len(n.model.binaries) + len(n.model.integers)), S=S,
                        K={f'{c}_{p}': K[(zz, c, p)] for (zz, c, p) in K if zz == z}, R={a: R[a] for a, _ in rs},
                        mean_lmp=float(lmp.mean()), mean_adder=float(adder.mean()),
                        planned_grid_energy_payment_PV_private=pay_e, planned_capacity_payment_PV_private=pay_c))
    return K, R, out


# ------------------------------------------------------------------------------------------------ ledgers
def ledgers(n, tag, v, case_id, run_id, byop_fixed_scen=False):
    """Two books per asset + system aggregates. social = unsubsidised resource cost at r_s; private = developer."""
    P = periods(); Y = years()
    w = n.snapshot_weightings.generators
    per = n.snapshots.get_level_values(0)
    g, su, l = n.generators, n.storage_units, n.links
    lmp = n.buses_t.marginal_price
    pct = STATE.get('public_cost_table', pd.DataFrame()).set_index('name') if len(STATE.get('public_cost_table', [])) else None
    # tax credits are in the network costs only when the decision basis kept them (legacy, or --public-subsidy with)
    sub_in_net = CFG['cost_basis'] == 'legacy' or CFG['public_subsidy'] == 'with'
    rows = []
    active = lambda by, life, p: by <= p < by + life
    ws = {p: years_p(p) * df(p, CFG['social_r']) for p in P}   # social ledger always discounted at r_s
    wp = {p: years_p(p) * df(p, CFG['private_wacc']) for p in P}
    gen_e = n.generators_t.p.mul(w, axis=0).groupby(level=0).sum()   # MWh per year by period
    for comp, d, cap in [('Generator', g, 'p_nom_opt'), ('StorageUnit', su, 'p_nom_opt'), ('Link', l, 'p_nom_opt')]:
        sel = d[(d.p_nom_extendable | d.carrier.str.startswith('byop_')) & ~d.carrier.isin(['compute_IT', 'AIDC_training'])]
        if comp == 'Link':
            sel = sel[sel.index.astype(str).str.endswith('_fwd') & (sel.carrier == 'AC_exp')]   # astype: empty Link table (no links in G-W)
        for name, r in sel.iterrows():
            MW = float(r[cap])
            if MW < 0.5:
                continue
            by, life = int(r.build_year), float(r.lifetime)
            act = [p for p in P if active(by, life, p)]
            car = r.carrier
            if car.startswith('byop_') and car != 'byop_R':
                bp_s = byop_params(car[5:], 'social'); bp_p = byop_params(car[5:], 'private')
                soc_ann, priv_ann, boundary, path = bp_s['annual_social'], bp_p['annual_private'], 'DC_BTM', 'N'
                overnight = bp_s['overnight_per_MW']; sub = 0.0; ptc = 0.0
            elif car == 'byop_R' or car == 'reuse_pub':
                rp = reuse_params('social')
                soc_ann, priv_ann = rp['annual_social'], rp['annual_private']
                boundary = 'DC_BTM_R' if car == 'byop_R' else 'UTILITY_R'; path = 'R'
                overnight = rp['refurb'] * 1000; sub = 0.0; ptc = 0.0
            elif comp == 'Link':
                soc_ann = priv_ann = float(r.capital_cost); boundary = 'UTILITY_LINE'; path = 'public'
                overnight = float('nan'); sub = 0.0; ptc = 0.0
            else:
                pc = pct.loc[name] if pct is not None and name in pct.index else None
                soc_ann = float(pc.cc_social) if pc is not None else float(r.capital_cost)
                priv_ann = float(pc.cc_market_sub) if pc is not None else float(r.capital_cost)
                sub = float(pc.cc_social - pc.cc_social_sub) if (pc is not None and sub_in_net) else 0.0
                ptc = float(pc.ptc) if (pc is not None and sub_in_net) else 0.0
                overnight = float(pc.overnight_per_MW) if pc is not None else float('nan')
                boundary = 'UTILITY'; path = 'public'
            energy = {p: float(gen_e[name].get(p, 0.0)) if comp == 'Generator' and name in gen_e else None for p in P}
            mc_p = {}
            if comp == 'Generator' and name in n.generators_t.marginal_cost and name in n.generators_t.p:   # v1.3 yearly gas price
                pe = n.generators_t.p[name].mul(w)
                mc_p = ((pe * n.generators_t.marginal_cost[name]).groupby(level=0).sum() / pe.groupby(level=0).sum().replace(0.0, np.nan)).to_dict()
            for p in act:
                e = energy.get(p) or 0.0
                mc_res = (float(mc_p[p]) if p in mc_p and mc_p[p] == mc_p[p] else float(r.marginal_cost)) + ptc if comp == 'Generator' else 0.0
                rows.append(dict(run_id=run_id, case_id=case_id, scenario=tag, asset_id=name, component=comp, carrier=car,
                                 asset_boundary=boundary, resource_path=path, zone=r.get('bus', r.get('bus0')),
                                 commit_year=STATE.get('approval_year', {}).get(name, CFG['decision_year']), build_period=by, year=p, capacity_MW=MW,
                                 overnight_capex_USD_per_MW=overnight,
                                 social_annuity_USD_per_MW_yr=soc_ann, private_annuity_USD_per_MW_yr=priv_ann,
                                 resource_capex_PV_USD=soc_ann * MW * ws[p], private_capex_PV_USD=priv_ann * MW * wp[p],
                                 dispatch_MWh_per_yr=e if comp == 'Generator' else None,
                                 resource_vom_fuel_PV_USD=mc_res * e * ws[p],
                                 subsidy_tax_credit_PV_USD=(sub * MW + ptc * e) * ws[p],
                                 cf=(e / (MW * 8760)) if comp == 'Generator' and MW > 0 else None,
                                 private_WACC=CFG['private_wacc'], social_discount=CFG['social_r'],
                                 currency_year='2025$ (TECH-01) / ATB2024$ (public)', present_value_year=CFG['decision_year'],
                                 time_basis=f"{CFG['periods']} sample_weeks={CFG['sample_weeks']}",
                                 evidence_grade='RAW_SOLVER_VERIFIED', validity='VALID_IF_RUN_OPTIMAL'))
    led = pd.DataFrame(rows)
    # system operating cost (all generators, existing included) at resource marginal cost, social PV
    mc = n.get_switchable_as_dense('Generator', 'marginal_cost')
    ptc_adj = pd.Series(0.0, index=g.index)
    if pct is not None and sub_in_net:
        for name in g.index.intersection(pct.index):
            ptc_adj[name] = float(pct.ptc[name])
    is_op = ~g.carrier.isin(['compute_IT', 'AIDC_training', 'load_shed', 'grid_purchase', 'dc_curtail', 'dc_interrupt'])   # dc_curtail: lost compute, not a resource (rearch PCLR)
    opcost_t = (n.generators_t.p.loc[:, is_op] * (mc.loc[:, is_op] + ptc_adj[is_op])).mul(w, axis=0).groupby(level=0).sum().sum(axis=1)
    shed = n.generators_t.p[[f'{z} load_shed' for z in ZONES]].mul(w, axis=0).groupby(level=0).sum().sum(axis=1)
    svc = []
    for d in STATE.get('dc', []):
        S = float(g.p_nom_opt[d['S']]); p = d['period']
        sl = per == p
        poi = f"POI {d['zone']} {p}"; poinf = f"POInf {d['zone']} {p}"
        poi_e = float((n.links_t.p0[poi][sl] * w[sl]).sum()) if poi in n.links_t.p0 else 0.0
        nf_e = float((n.links_t.p0[poinf][sl] * w[sl]).sum()) if poinf in n.links_t.p0 else 0.0
        pay = sum(float((n.links_t.p0[x][sl] * lmp[d['zone']][sl] * w[sl]).sum()) for x in (poi, poinf) if x in n.links_t.p0)
        nf_peak = float(n.links_t.p0[poinf][sl].max()) if poinf in n.links_t.p0 else 0.0
        poi_e_firm = poi_e
        poi_e = poi_e + nf_e
        byop_e = sum(float((n.generators_t.p[b][sl] * w[sl]).sum()) for b in g.index
                     if g.carrier[b].startswith('byop_') and g.bus[b] == f"DC_{d['zone']}")
        byop_e += sum(float((n.storage_units_t.p[b][sl] * w[sl]).sum()) for b in su.index      # v1.3 on-site BESS (net)
                      if su.carrier[b].startswith('byop_') and su.bus[b] == f"DC_{d['zone']}" and b in n.storage_units_t.p)
        fac_e = float(((n.generators_t.p[d['S']][sl] + n.generators_t.p[d['T']][sl]) * w[sl]).sum())
        svc.append(dict(run_id=run_id, case_id=case_id, scenario=tag, zone=d['zone'], year=p, requested_MW_IT=d['D'],
                        grid_ready_MW_IT=d['G'], served_MW_IT=S, unserved_MW_IT=d['D'] - S, served_MW_IT_year=S * years_p(p),
                        delay_MW_IT_year=(d['D'] - S) * years_p(p), poi_MWh_per_yr=poi_e, poi_firm_MWh_per_yr=poi_e_firm,
                        poi_nonfirm_MWh_per_yr=nf_e, poi_nonfirm_peak_MW=nf_peak, byop_MWh_per_yr=byop_e,
                        facility_load_MWh_per_yr=fac_e, energy_balance_resid_MWh=fac_e - poi_e - byop_e,
                        grid_payment_USD_per_yr=pay, pue=d['pue'],
                        social_delay_loss_PV_USD=v * (d['D'] - S) * ws[p],
                        private_delay_loss_PV_USD=(CFG['v_private'] or v) * (d['D'] - S) * wp[p],
                        transfer_energy_PV_social_USD=pay * ws[p], transfer_energy_PV_private_USD=pay * wp[p]))
    svc = pd.DataFrame(svc)
    S_ = lambda col: float(svc[col].sum()) if len(svc) else 0.0
    L_ = lambda col, mask=None: float(led[col][mask].sum()) if len(led) and mask is not None else (float(led[col].sum()) if len(led) else 0.0)
    if len(led):
        pub_m = led.resource_path.eq('public') | led.asset_boundary.eq('UTILITY_R')
        byo_m = led.asset_boundary.isin(['DC_BTM', 'DC_BTM_R'])
    else:
        pub_m = byo_m = None
    op = float(sum(opcost_t.get(p, 0.0) * ws[p] for p in P))
    byop_fuel = L_('resource_vom_fuel_PV_USD', byo_m) if byo_m is not None else 0.0
    summ = dict(run_id=run_id, case_id=case_id, scenario=tag, v_social=v, v_private=CFG['v_private'] or v,
                public_resource_capex_PV_USD=L_('resource_capex_PV_USD', pub_m) if pub_m is not None else 0.0,
                byop_resource_capex_PV_USD=L_('resource_capex_PV_USD', byo_m) if byo_m is not None else 0.0,
                byop_private_capex_PV_USD=L_('private_capex_PV_USD', byo_m) if byo_m is not None else 0.0,
                system_operating_PV_USD=op, byop_fuel_PV_USD=byop_fuel,
                load_shed_MWh=float(shed.sum()), load_shed_PV_USD=float(sum(shed.get(p, 0.0) * SHED_COST * ws[p] for p in P)),
                social_delay_loss_PV_USD=S_('social_delay_loss_PV_USD'),
                served_MW_IT_year=S_('served_MW_IT_year'), delay_MW_IT_year=S_('delay_MW_IT_year'),
                requested_MW_IT_year=S_('served_MW_IT_year') + S_('delay_MW_IT_year'),
                transfer_energy_PV_social_USD=S_('transfer_energy_PV_social_USD'),
                tax_credit_PV_USD=L_('subsidy_tax_credit_PV_USD'),
                public_new_MW=json.dumps(led[pub_m & led.year.eq(P[-1])].groupby('carrier').capacity_MW.sum().round(1).to_dict()) if pub_m is not None else '{}',
                byop_MW=json.dumps(led[byo_m & led.year.eq(P[-1])].groupby('carrier').capacity_MW.sum().round(1).to_dict()) if byo_m is not None else '{}',
                objective=float(n.objective))
    summ['social_real_resource_cost_USD'] = (summ['public_resource_capex_PV_USD'] + summ['byop_resource_capex_PV_USD']
                                             + summ['system_operating_PV_USD'] + summ['load_shed_PV_USD'])
    summ['social_total_USD'] = summ['social_real_resource_cost_USD'] + summ['social_delay_loss_PV_USD']
    # private developer book (planned grid purchase at own-scenario LMP, BYOP at 7 %, private delay)
    summ['private_total_USD'] = (summ['byop_private_capex_PV_USD'] + float(
        sum(led[byo_m & led.year.eq(p)].resource_vom_fuel_PV_USD.sum() / ws[p] * wp[p] for p in P)) if byo_m is not None else 0.0) \
        + S_('transfer_energy_PV_private_USD') + S_('private_delay_loss_PV_USD')
    # objective-consistency residual (only meaningful when the solve objective is the social basis)
    const = (CFG['v_private'] if False else v) * float(sum((svc[svc.year == p].requested_MW_IT.sum()) * w_social(p) for p in P)) if len(svc) else 0.0
    summ['objective_plus_service_value'] = summ['objective'] + const
    return led, svc, summ


def duals(n, tag, case_id, run_id):
    rows = []
    m = n.model
    for d in STATE.get('dc', []):
        nm = f"M2-serve_cap_{d['S']}"
        if nm in m.constraints:
            try:
                mu = float(m.dual[nm].values)
            except Exception:
                mu = float('nan')
            rows.append(dict(run_id=run_id, case_id=case_id, scenario=tag, constraint='serve_cap(POI+firm)', zone=d['zone'],
                             year=d['period'], dual_raw=mu, dual_USD_per_MW_IT_yr=mu / w_social(d['period']) if mu == mu else None,
                             binding=bool(abs(mu) > 1e-3) if mu == mu else None))
    ep = n.buses_t.get('erm_price')
    if ep is not None and len(ep.columns):
        sw = n.snapshot_weightings.generators
        for p in periods():
            sl = n.snapshots.get_level_values(0) == p
            for z in ZONES:
                if z in ep:
                    mu = ep[z][sl].astype(float).fillna(0.0)
                    rows.append(dict(run_id=run_id, case_id=case_id, scenario=tag, constraint='ERM(TX row, zone bus)', zone=z,
                                     year=p, dual_raw=float(mu.abs().sum()),
                                     dual_USD_per_MW_IT_yr=float(mu.abs().sum()) / w_social(p),
                                     binding=bool(mu.abs().sum() > 1e-3), n_binding_snapshots=int((mu.abs() > 1e-6).sum())))
    for c in STATE.get('corridors', []):
        f = c['corridor'] + '_fwd'
        if f in n.links_t.p0:
            for p in periods():
                sl = n.snapshots.get_level_values(0) == p
                cap = float(n.links.p_nom_opt[f]) + sum(float(n.links.p_nom_opt.get(f"{c['corridor']}_exp{q}_fwd", 0.0)) for q in periods() if q <= p)
                flow = n.links_t.p0[f][sl].abs()
                rows.append(dict(run_id=run_id, case_id=case_id, scenario=tag, constraint='corridor_congestion', zone=c['corridor'],
                                 year=p, dual_raw=None, dual_USD_per_MW_IT_yr=None,
                                 binding=bool((flow >= float(n.links.p_nom_opt[f]) * 0.999).any()),
                                 n_binding_snapshots=int((flow >= float(n.links.p_nom_opt[f]) * 0.999).sum()), capacity_MW=cap))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case-id', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--periods', default='annual', choices=['annual', '2y'])
    ap.add_argument('--start', type=int, default=2026); ap.add_argument('--end', type=int, default=2033)
    ap.add_argument('--cost-basis', default='repaired', choices=['legacy', 'repaired'])
    ap.add_argument('--public-subsidy', default='without', choices=['with', 'without'])
    ap.add_argument('--tariff', default='energy', choices=['energy', 'energy_erm'])
    ap.add_argument('--no-flex', action='store_true', help='disable FLEX-01 flexible interconnection')
    ap.add_argument('--reuse', default='on', choices=['off', 'on']); ap.add_argument('--reuse-case', default='base', choices=['low', 'base', 'high'])
    ap.add_argument('--no-frac-cod', action='store_true')
    ap.add_argument('--poi-lead', type=int, default=0, help='GRID-01: 0 = increment is the grid-connection demand of its year (delay endogenous); >0 = v2.3.0 exogenous POI wait')
    ap.add_argument('--byop-case', default='base', choices=['low', 'base', 'high'])
    ap.add_argument('--public-case', default='base', choices=['low', 'base', 'high'])
    ap.add_argument('--byop-techs', nargs='*', default=None)
    ap.add_argument('--sample-weeks', type=int, default=4, help='0 = full year 3h')
    ap.add_argument('--bg-growth', type=float, default=0.0); ap.add_argument('--no-line-exp', action='store_true')
    ap.add_argument('--bg-traj', default=str(BG_TRAJ_DEFAULT), help="background annual load factor CSV (year,factor_vs_2025); 'none' = hold 2025 (pre LOAD-GROWTH-01)")
    ap.add_argument('--erm-cal', default=None); ap.add_argument('--erm15', action='store_true')
    ap.add_argument('--calibrate', action='store_true')
    ap.add_argument('--v', type=float, default=2.8e6); ap.add_argument('--v-private', type=float, default=None)
    ap.add_argument('--threads', type=int, default=4); ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--s1-from', default=None, help='case dir whose solved S1 prices (prices_S1.csv.gz) feed the S2 developer stage; '
                    'S1 is then built (same physical world) but not re-solved')
    ap.add_argument('--scenarios', nargs='*', default=['S0', 'S1', 'S1_zero', 'S3', 'S3_mS1', 'S2', 'S2_off', 'S3_mS2'])
    a = ap.parse_args()
    CFG.update(flex=not a.no_flex, bg_traj=a.bg_traj, periods=a.periods, start=a.start, end=a.end, cost_basis=a.cost_basis, public_subsidy=a.public_subsidy,
               tariff=a.tariff, reuse=a.reuse, reuse_case=a.reuse_case, frac_cod=not a.no_frac_cod, poi_lead=a.poi_lead,
               byop_case=a.byop_case, public_case=a.public_case, sample_weeks=a.sample_weeks or None, bg_growth=a.bg_growth,
               line_exp=not a.no_line_exp, erm15=a.erm15, threads=a.threads, v=a.v, v_private=a.v_private, smoke=a.smoke)
    if a.byop_techs:
        CFG['byop_techs'] = a.byop_techs
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(out / 'v240_solver.log', 'a', 'utf-8'), logging.StreamHandler()])
    run_id = f'v240_{a.case_id}_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    w2.PREP = str(BASE)
    w2.PUE = pd.read_csv(w2.PUE_CSV)
    config = pypsa.Network(BASE).meta
    v = a.v
    events = []

    def ev(event, status, msg, **kw):
        events.append(dict(timestamp_utc=datetime.now(timezone.utc).isoformat(), run_id=run_id, case_id=a.case_id,
                           event=event, status=status, message=msg, **kw))
        with open(out / 'events.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(events[-1], ensure_ascii=False, default=str) + '\n')

    if a.calibrate:   # ERM-02 B at this resolution / period set: existing + committed fleet only
        n, _ = build(config, 'S0', v)
        for c, d in [('Generator', n.generators), ('StorageUnit', n.storage_units), ('Link', n.links)]:
            d.loc[d.index[d.p_nom_extendable], 'p_nom_max'] = 0.0
        STATE['erm_cal'] = 'solve'
        res = solve(config, 'ERM02_calibration', out, n)
        mv = n.model.solution['M2-erm_margin'].to_series()
        cal = dict(decision='ERM-02 B', margin_by_period={int(k): float(x) for k, x in mv.items()}, termination=res['termination'],
                   cfg={k: CFG[k] for k in ['periods', 'start', 'end', 'sample_weeks', 'bg_growth', 'bg_traj']}, baseline_sha256=sha(BASE))
        (out / 'erm02_calibration.json').write_text(json.dumps(cal, indent=2))
        ev('erm_calibration', 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL', json.dumps(cal['margin_by_period']))
        return
    if a.erm_cal and not a.erm15:
        STATE['erm_cal'] = {int(k): float(x) for k, x in json.loads(Path(a.erm_cal).read_text())['margin_by_period'].items()}
    else:
        STATE['erm_cal'] = None
    reuse_on = CFG['reuse'] == 'on'
    LED, SVC, SUM, DUA, RES = [], [], [], [], {}
    priv_info = None
    saved = {}

    def go(tag, **kw):
        if tag not in a.scenarios:
            return None
        t0 = time.time()
        n, mult = build(config, tag if tag == 'S0' else 'S', v, **kw)
        res = solve(config, tag, out, n)
        led, svc, summ = ledgers(n, tag, v, a.case_id, run_id)
        summ.update(termination=res['termination'], integer_vars=res['integer_vars'], n_vars=res['n_vars'],
                    n_cons=res['n_cons'], solve_seconds=res['seconds'])
        LED.append(led); SVC.append(svc); SUM.append(summ); RES[tag] = res
        DUA.append(duals(n, tag, a.case_id, run_id))
        pr = n.buses_t.marginal_price[ZONES].copy()
        ep = n.buses_t.get('erm_price')
        if ep is not None:
            for z in DC_ZONES:
                if z in ep:
                    pr[f'erm_{z}'] = ep[z].astype(float)
        pr.to_csv(out / f'prices_{tag}.csv.gz')
        ev('optimization_solved', 'SOLVER_OPTIMAL' if res['termination'] == 'optimal' else 'FAIL',
           f"obj {res['objective']:.6e}; vars {res['n_vars']}; int {res['integer_vars']}; {time.time() - t0:.0f}s", scenario=tag)
        logger.info(f'{tag}: {json.dumps({k: v_ for k, v_ in summ.items() if not isinstance(v_, str)}, default=str)}')
        return n, mult

    byop = CFG['byop_techs']
    go('S0')
    if a.s1_from:   # S1 prices from an identical physical world (S1 does not depend on the tariff regime)
        n1, mult1 = build(config, 'S', v)
        pr = pd.read_csv(Path(a.s1_from) / 'prices_S1.csv.gz', index_col=[0, 1])
        if len(pr) != len(n1.snapshots):
            raise SystemExit('s1-from: snapshot mismatch')
        n1.buses_t.marginal_price = pd.DataFrame(pr[ZONES].values, index=n1.snapshots, columns=ZONES)
        n1.buses_t['erm_price'] = pd.DataFrame({z: pr[f'erm_{z}'].values for z in DC_ZONES if f'erm_{z}' in pr}, index=n1.snapshots)
        r1 = (n1, mult1)
        ev('s1_prices_reused', 'REUSED', f'S1 prices from {a.s1_from}')
    else:
        r1 = go('S1')
    if r1 is not None:
        if not a.s1_from:
            saved['S1_service'] = {(s.zone, s.year): s.served_MW_IT for s in SVC[-1].itertuples()}
        STATE['reuse_s1'] = [dict(asset_id=e['asset_id'], zone=e['zone'], MW=e['MW'], build_period=e['build_period'],
                                  mc=float(r1[0].generators.marginal_cost[e['pub']])) for e in STATE.get('reuse', [])]
    go('S1_zero', dem_scale=0.0)
    go('S3', byop=byop, reuse_dedicated=True)
    if r1 is not None and 'S1_service' in saved:
        go('S3_mS1', byop=byop, reuse_dedicated=True, s_fixed=saved['S1_service'])
    if r1 is not None and ({'S2', 'S2_off', 'S3_mS2'} & set(a.scenarios)):
        K, R, priv_info = private_stage(config, r1[0], CFG['v_private'] or v, r1[1], reuse_on)
        RES['S2_private'] = priv_info
        ev('s2_private_stage', 'SOLVER_OPTIMAL' if all(p_['termination'] == 'optimal' for p_ in priv_info) else 'FAIL',
           json.dumps({p_['zone']: p_['K'] for p_ in priv_info}))
        r2 = go('S2', byop=byop, byop_fixed=K, rfixed=R if reuse_on else None)
        if r2 is not None:
            saved['S2_service'] = {(s.zone, s.year): s.served_MW_IT for s in SVC[-1].itertuples()}
        go('S2_off', byop=byop, byop_fixed={k: 0.0 for k in K}, rfixed={k: 0.0 for k in R} if reuse_on else None)
        if r2 is not None:
            go('S3_mS2', byop=byop, reuse_dedicated=True, s_fixed=saved['S2_service'])
    led = pd.concat(LED, ignore_index=True) if LED else pd.DataFrame()
    svc = pd.concat(SVC, ignore_index=True) if SVC else pd.DataFrame()
    summ = pd.DataFrame(SUM)
    led.to_csv(out / 'ledger.csv', index=False); svc.to_csv(out / 'service.csv', index=False)
    summ.to_csv(out / 'scenario_summary.csv', index=False)
    (pd.concat(DUA, ignore_index=True) if DUA else pd.DataFrame()).to_csv(out / 'duals.csv', index=False)
    STATE.get('public_cost_table', pd.DataFrame()).drop_duplicates(['zone', 'carrier']).to_csv(out / 'public_cost_basis.csv', index=False)
    pd.DataFrame(STATE.get('offered', [])).to_csv(out / 'offered_candidates.csv', index=False)
    cs = summ.set_index('scenario') if len(summ) else pd.DataFrame()
    rel = lambda x, y: abs(cs.social_total_USD[x] - cs.social_total_USD[y]) / abs(cs.social_total_USD[y])
    checks = dict(
        true_LP=all(r['integer_vars'] == 0 for k, r in RES.items() if isinstance(r, dict)),
        all_optimal=all(r['termination'] == 'optimal' for k, r in RES.items() if isinstance(r, dict)),
        S1_zero_equals_S0=bool(rel('S1_zero', 'S0') < 1e-4) if {'S1_zero', 'S0'} <= set(cs.index) else None,
        S2_off_equals_S1=bool(rel('S2_off', 'S1') < 1e-4) if {'S2_off', 'S1'} <= set(cs.index) else None,
        no_load_shed=bool((summ.load_shed_MWh < 1.0).all()) if len(summ) else None,
        no_public_offer_before_COD=bool(all(o['period'] >= math.floor(o['earliest_COD']) for o in STATE.get('offered', []))),
        dc_energy_balance=bool(svc.energy_balance_resid_MWh.abs().max() < 1e-3 * max(1.0, svc.facility_load_MWh_per_yr.max())) if len(svc) else None,
        served_le_requested=bool((svc.unserved_MW_IT >= -1e-6).all()) if len(svc) else None,
        private_stage_LP=all(p_['integer_vars'] == 0 and p_['termination'] == 'optimal' for p_ in priv_info) if priv_info else None)
    man = dict(run_id=run_id, case_id=a.case_id, cfg=dict(CFG), argv=sys.argv, status='CASE_SOLVED' if all(x in (True, None) for x in checks.values()) else 'CASE_CHECK_FAIL',
               checks=checks, solves=RES, erm_cal=STATE.get('erm_cal'), baseline=str(BASE), baseline_sha256=sha(BASE),
               code_sha256={p.name: sha(p) for p in [Path(__file__), V2T / 'wp2_ercot_s0_s1.py', V2T / 'wp2_ercot_s1_real.py']},
               tech_sha256=sha(TECH), bg_traj=CFG['bg_traj'], bg_traj_sha256=sha(CFG['bg_traj']) if CFG['bg_traj'] != 'none' else None,
               bg_factor_by_period=STATE.get('bg_factor_by_period'), cohorts_sha256=sha(s1r.COHORTS), pypsa=pypsa.__version__,
               byop={t: {k_: byop_params(t, ac) for ac in ['social', 'private'] for k_ in [ac]} for t in CFG['byop_techs']},
               reuse_params=reuse_params('social') if reuse_on else None, reuse_pool=STATE.get('reuse', []),
               corridors=STATE.get('corridors'), study_new=study_new_demand().to_dict(orient='records'),
               timestamp_utc=datetime.now(timezone.utc).isoformat())
    (out / 'case_manifest.json').write_text(json.dumps(man, indent=2, default=str))
    print(json.dumps(dict(case=a.case_id, status=man['status'], checks=checks), indent=1, default=str))
    if len(summ):
        print(summ[['scenario', 'social_total_USD', 'social_real_resource_cost_USD', 'social_delay_loss_PV_USD',
                    'served_MW_IT_year', 'public_new_MW', 'byop_MW', 'termination']].to_string())


if __name__ == '__main__':
    main()
