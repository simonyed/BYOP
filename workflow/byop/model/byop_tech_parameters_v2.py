"""TECH_COMP_2 (BYOP technology package v2.0, 2026-10-22) - read-only parameter adapter (A0.2 P2, no solver).

Source: the four ORIGINAL files of the researcher's v2.0 ZIP, copied byte-identical to workflow/byop/inputs/tech_calibrated_v2/
(SHA-256 pinned below and checked on every load; the legacy MAINLINE_V13_TECH_DEFAULTS.csv is untouched and stays the default).
Six technologies RICE, OCGT_aero, SOFC_NG, WIND, PV, BESS. Units: CAPEX 2025 USD / kW net AC (installed, no tax credits, EPC
included once), FOM USD / kW-yr (SOFC FOM includes service + stack reserve: no extra stack annuity), VOM USD / MWh, heat rate
Btu_HHV / kWh. Fuel: MMBtu / MWh = HR / 1000; fuel cost = HR / 1000 x gas(year, WSC HHV 2025$) + VOM; PyPSA efficiency =
3412.14 / HR (no LHV conversion). Private annuity at 7 % WACC, social at 2 %, FOM counted once per year. NOx control
(CONTROLLED_ENV) adds its CAPEX / FOM only on that pre-enumerated path; it does not change the permit lead.
"""
from __future__ import annotations

import hashlib, json, math
from pathlib import Path

import pandas as pd

import byop_paths as BP

VERSION = 'TECH_COMP_2'
SRC = BP.INPUTS / 'tech_calibrated_v2'
SOURCE_SHA256 = {
    'BYOP_TECH_PARAMETER_BASELINE_V2.json': '10bd868ba50929379be23b63d72626d8d528a1b358ce6b5a63a516e5771327c7',
    'BYOP_TECH_PARAMETERS_V2.csv': '3956cdd25f25087dd74f0f6c959cf21bafb6eec1fd61ad295c0b91bbb9dcf26c',
    'BYOP_SUPPLY_POOL_PROXY_V2.csv': '181af58f60dec3a87e2a812ab235debd79b5ca58db23fdbb2f949a5e3c0ce988',
    'BYOP_COUNTY_OZONE_RULES_2026.csv': '8bfc4de5dd864e0107b8e1482c3d4193e31c43dad18aab81343910fd667def24',
}
GAS_PRICES = BP.INPUTS / 'tech/MAINLINE_V13_GAS_PRICES_2026_2031.csv'
TECHS = ['RICE', 'OCGT_aero', 'SOFC_NG', 'WIND', 'PV', 'BESS']
GAS_TECHS = ['RICE', 'OCGT_aero', 'SOFC_NG']
PATHS = ('DEFAULT_ENV', 'CONTROLLED_ENV')
NUMERIC = ['capex_2025USD_per_kW', 'capex_low', 'capex_high', 'fom_USD_per_kWyr', 'vom_USD_per_MWh', 'heat_rate_HHV_Btu_per_kWh',
           'equipment_order_to_arrival_years', 'site_install_commission_years', 'civil_ready_from_order_years', 'lifetime_years',
           'NOx_kg_per_MWh_uncontrolled_proxy', 'NOx_kg_per_MWh_controlled_proxy', 'NOx_control_extra_CAPEX_USD_per_kW',
           'NOx_control_extra_FOM_USD_per_kWyr', 'CO2_t_per_MWh']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify_sources(src=SRC):
    bad = {f: sha(src / f) for f, h in SOURCE_SHA256.items() if not (src / f).exists() or sha(src / f) != h}
    if bad:
        raise ValueError(f'TECH_COMP_2 source SHA mismatch (files must be the original bytes): {sorted(bad)}')
    return True


def load(src=SRC):
    """JSON baseline (the formal source) + CSV cross-check; raises on any SHA / value / missing-field problem"""
    verify_sources(src)
    j = json.loads((src / 'BYOP_TECH_PARAMETER_BASELINE_V2.json').read_text(encoding='utf-8'))
    assert j['version'] == 'TECH_COMP_2_2026-10-22'
    T = {t['tech']: t for t in j['technologies']}
    assert sorted(T) == sorted(TECHS), sorted(T)
    csv = pd.read_csv(src / 'BYOP_TECH_PARAMETERS_V2.csv').set_index('tech')
    for t in TECHS:
        for k in NUMERIC:
            v = T[t].get(k)
            if v is None:
                raise ValueError(f'{t}.{k} missing in the JSON (no silent 0)')
            if abs(float(csv.loc[t, k]) - float(v)) > 1e-9:
                raise ValueError(f'{t}.{k}: CSV {csv.loc[t, k]} != JSON {v}')
    return j, T


def crf(r, n):
    return r / (1 - (1 + r) ** -n)


def gas_price(year):
    g = pd.read_csv(GAS_PRICES).set_index('year').gas_price_2025USD_per_MMBtu_HHV
    if int(year) not in g.index:
        raise ValueError(f'no WSC gas price for {year} (2026-2031 only; 2032+ not authorised)')
    return float(g[int(year)])


def fixed_costs(t, path='DEFAULT_ENV', T=None):
    """USD / kW-yr: private (7 %) and social (2 %) annuity of CAPEX + FOM once; CONTROLLED_ENV adds the NOx-control CAPEX / FOM"""
    T = T or load()[1]
    x = T[t]
    assert path in PATHS
    ctrl = path == 'CONTROLLED_ENV' and t in ('RICE', 'OCGT_aero')
    capex = float(x['capex_2025USD_per_kW']) + (float(x['NOx_control_extra_CAPEX_USD_per_kW']) if ctrl else 0.0)
    fom = float(x['fom_USD_per_kWyr']) + (float(x['NOx_control_extra_FOM_USD_per_kWyr']) if ctrl else 0.0)
    life = float(x['lifetime_years'])
    return dict(tech=t, path=path, capex_USD_per_kW=capex, fom_USD_per_kWyr=fom, life_y=life,
                private_annual_USD_per_kWyr=capex * crf(0.07, life) + fom, social_annual_USD_per_kWyr=capex * crf(0.02, life) + fom)


def fuel(t, year, T=None):
    """HHV fuel use / cost; non-gas technologies return zeros (no fuel), never a silent default heat rate"""
    T = T or load()[1]
    x = T[t]
    hr = float(x['heat_rate_HHV_Btu_per_kWh'])
    vom = float(x['vom_USD_per_MWh'])
    if t not in GAS_TECHS:
        assert hr == 0
        return dict(tech=t, year=year, MMBtu_per_MWh=0.0, gas_USD_per_MMBtu=None, fuel_cost_USD_per_MWh=vom, efficiency=1.0)
    g = gas_price(year)
    return dict(tech=t, year=year, MMBtu_per_MWh=hr / 1000.0, gas_USD_per_MMBtu=g, fuel_cost_USD_per_MWh=hr / 1000.0 * g + vom,
                efficiency=3412.14 / hr, CO2_t_per_MWh=float(x['CO2_t_per_MWh']))


def nox_rate(t, path, T=None):
    T = T or load()[1]
    x = T[t]
    return float(x['NOx_kg_per_MWh_controlled_proxy'] if path == 'CONTROLLED_ENV' else x['NOx_kg_per_MWh_uncontrolled_proxy'])


def byop_params_v2(carrier, actor, CFG, path='DEFAULT_ENV', T=None, gas_ref=None):
    """same keys as v240_mech.byop_params (per MW, USD) so the existing cohort builder can read TECH_COMP_2 when the config
    selects it; 'lead' = equipment arrival + installation (the site / permit / gas COD comes from byop_delivery_and_permit);
    mc uses the reference gas price GAS so that rearch_mech.ml_gas_delta re-prices it to the WSC year price as for v1.3"""
    T = T or load()[1]
    x = T[carrier]
    fc = fixed_costs(carrier, path, T)
    rate = CFG['private_wacc'] if (actor == 'private' or CFG.get('cost_basis') == 'legacy') else CFG['social_r']
    life = float(x['lifetime_years'])
    cap = fc['capex_USD_per_kW'] * 1000.0
    fom = fc['fom_USD_per_kWyr'] * 1000.0
    hr = float(x['heat_rate_HHV_Btu_per_kWh'])
    vom = float(x['vom_USD_per_MWh'])
    g = CFG.get('gas_ref', 3.19) if gas_ref is None else gas_ref
    red = float('inf') if x.get('firm_redundancy_factor') is None else float(x['firm_redundancy_factor'])
    lead = float(x['equipment_order_to_arrival_years']) + float(x['site_install_commission_years'])
    return dict(carrier=carrier, case=VERSION, path=path, overnight_per_MW=cap, fom=fom, life=life, annual=cap * crf(rate, life) + fom, rate=rate,
                annual_social=cap * crf(CFG['social_r'], life) + fom, annual_private=cap * crf(CFG['private_wacc'], life) + fom,
                mc=hr / 1000.0 * g + vom, hr=hr, vom=vom, r=red, lead=lead, evidence=str(x.get('evidence')),
                max_hours=float(x['storage_duration_hours']) if x.get('storage_duration_hours') else None,
                eta_rt=float(x['storage_round_trip_efficiency']) if x.get('storage_round_trip_efficiency') else None,
                nox_kg_per_MWh=nox_rate(carrier, path, T), co2_t_per_MWh=float(x['CO2_t_per_MWh']),
                equipment_lead=float(x['equipment_order_to_arrival_years']), install_lead=float(x['site_install_commission_years']),
                civil_lead=float(x['civil_ready_from_order_years']), module_MW=x.get('module_reference_MW'))
