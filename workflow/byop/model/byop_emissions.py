"""TECH_COMP_2 emissions: NOx PTE screen per site, operating CO2 / NOx ledger, control-path cost (A0.2 P3b, no solver).

PTE_NOx_short_tpy = sum over EVERY unit / path at the same site_id of K_MW x 8760 h x rate_kg_per_MWh / 907.18474 (kg per short
ton). A crude permit screen only (no start-up / shutdown, other pollutants or regulatory calculation): it never decides
major-source status, approval or exemption. Mutually exclusive paths of one site are aggregated, never split to dodge the PTE.
Operating ledger: CO2_t = sum MWh x CO2_t/MWh, NOx_kg = sum MWh x NOx_kg/MWh. Carrier.co2_emissions = 0 in the PyPSA BYOP
carriers is a data-structure value, NOT zero emissions - the ledger here is the reported quantity. No emission price, carbon
tax, cap or damage cost enters any objective in this package.
"""
from __future__ import annotations

import pandas as pd

import byop_tech_parameters_v2 as T2

KG_PER_SHORT_TON = 907.18474
HOURS = 8760.0


def pte_short_tpy(capacity_MW, nox_kg_per_MWh):
    return float(capacity_MW) * HOURS * float(nox_kg_per_MWh) / KG_PER_SHORT_TON


def site_pte(units, T=None):
    """units: rows (site_id, tech, path, capacity_MW); one PTE per site over all its units / paths"""
    T = T or T2.load()[1]
    df = pd.DataFrame(units)
    if df.empty:
        return pd.DataFrame(columns=['site_id', 'NOx_PTE_screen_short_tpy', 'units'])
    df['nox_kg_per_MWh'] = [T2.nox_rate(t, p, T) if t in T2.GAS_TECHS else 0.0 for t, p in zip(df.tech, df.path)]
    df['pte'] = [pte_short_tpy(k, r) for k, r in zip(df.capacity_MW, df.nox_kg_per_MWh)]
    g = df.groupby('site_id').agg(NOx_PTE_screen_short_tpy=('pte', 'sum'), units=('tech', 'size'),
                                  paths=('path', lambda s: ';'.join(sorted(set(s))))).reset_index()
    g['screen_note'] = 'crude NOx PTE screen (8760 h at the rated MW); not a major-source / approval determination'
    return g


def operating_ledger(dispatch_MWh, T=None):
    """dispatch_MWh: rows (tech, path, MWh) -> CO2 t and NOx kg (post-processing ledger, never an objective term)"""
    T = T or T2.load()[1]
    rows = []
    for r in pd.DataFrame(dispatch_MWh).itertuples():
        co2 = float(T[r.tech]['CO2_t_per_MWh'])
        nox = T2.nox_rate(r.tech, r.path, T) if r.tech in T2.GAS_TECHS else 0.0
        rows.append(dict(tech=r.tech, path=r.path, MWh=float(r.MWh), CO2_t=float(r.MWh) * co2, NOx_kg=float(r.MWh) * nox,
                         note='carrier co2_emissions = 0 is a PyPSA placeholder; this ledger is the emission quantity'))
    return pd.DataFrame(rows)


def control_cost_delta(tech, T=None):
    """extra resource cost of CONTROLLED_ENV vs DEFAULT_ENV (USD / kW and USD / kW-yr); 0 for SOFC and non-combustion"""
    a, b = T2.fixed_costs(tech, 'DEFAULT_ENV', T), T2.fixed_costs(tech, 'CONTROLLED_ENV', T)
    return dict(tech=tech, extra_capex_USD_per_kW=b['capex_USD_per_kW'] - a['capex_USD_per_kW'],
                extra_fom_USD_per_kWyr=b['fom_USD_per_kWyr'] - a['fom_USD_per_kWyr'],
                extra_private_annual_USD_per_kWyr=b['private_annual_USD_per_kWyr'] - a['private_annual_USD_per_kWyr'])
