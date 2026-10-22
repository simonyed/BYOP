"""TECH_COMP_2 common manufacturing delivery pools and capacity-right ledger (A0.2 P3c, no solver).

Pool (RESEARCH_PROXY_NOT_VERIFIED_SPARE_OEM_CAPACITY, net AC MW by delivery year 2026-2031 for RICE / OCGT_aero / SOFC_NG):
    sum over sites, paths and order years with delivery_year == y of K[site, tech, q, path] <= pool[tech, y]
shared by all 16 research buses and both permit paths; one physical asset is counted once (an S2 asset kept in the later public
stage does not draw the pool again); S0-S3 are mutually exclusive worlds (no cross-scenario accumulation). Years after 2031 have
NO value: requesting one raises (no default infinite, zero or 2031 copy - needs a future authorisation). Wind / PV / BESS have no
national pool (site / bus potential applies). Verified pre-orders are 0 (no back-dated slots; SOFC fast path disabled).
Rights ledger (N new / R reuse / C contract): firm_right + contracted_right <= physical capacity per asset; one reliable MW is
never sold to the S2 contract, the public supply and a Firm certificate at the same time.
"""
from __future__ import annotations

import pandas as pd

import byop_tech_parameters_v2 as T2

POOL_TECHS = ['RICE', 'OCGT_aero', 'SOFC_NG']
YEARS = range(2026, 2032)


def pool_table(case='base'):
    t = pd.read_csv(T2.SRC / 'BYOP_SUPPLY_POOL_PROXY_V2.csv')
    col = {'base': 'ercot_available_MW_base_PROXY', 'low': 'low_MW', 'high': 'high_MW'}[case]
    assert len(t) == 18 and set(t.technology) == set(POOL_TECHS) and set(t.delivery_year) == set(YEARS)
    assert (t.reserved_verified_MW == 0).all(), 'verified pre-orders must be 0 (no evidence)'
    return t.set_index(['technology', 'delivery_year'])[col].astype(float)


def pool(tech, year, case='base'):
    if tech not in POOL_TECHS:
        return None                                   # no national pool (site potential applies)
    if int(year) not in YEARS:
        raise ValueError(f'no supply pool value for {tech} {year}: 2032+ needs a separate authorisation (no default)')
    return float(pool_table(case)[(tech, int(year))])


def usage_check(orders, case='base'):
    """orders: rows (site_id, tech, order_year, path, MW, delivery_year, asset_id) -> per tech-year usage vs pool; duplicate
    asset ids are counted once and flagged"""
    df = pd.DataFrame(orders)
    dup = df[df.duplicated('asset_id', keep='first')]
    use = df.drop_duplicates('asset_id').groupby(['tech', 'delivery_year']).MW.sum()
    rows = []
    for (t, y), mw in use.items():
        cap = pool(t, y, case)
        rows.append(dict(tech=t, delivery_year=int(y), used_MW=float(mw), pool_MW=cap, within_pool=cap is None or mw <= cap + 1e-9,
                         duplicate_assets_ignored=int((dup.tech == t).sum()), status='STATIC_QA_NOT_AN_INVESTMENT_RESULT'))
    return pd.DataFrame(rows)


def add_pool_constraints(n, m, candidates, case='base'):
    """linopy rows on an existing model (no solve): candidates = {generator name: (tech, delivery_year)}; one row per pool tech-year"""
    import xarray as xr  # noqa: F401
    pn = m['Generator-p_nom']
    ext = set(n.generators.index[n.generators.p_nom_extendable])
    by = {}
    for name, (t, y) in candidates.items():
        if t in POOL_TECHS and name in ext:
            by.setdefault((t, int(y)), []).append(name)
    made = []
    for (t, y), names in sorted(by.items()):
        cap = pool(t, y, case)
        m.add_constraints(pn.sel(name=names).sum('name') <= cap, name=f'V2-supply_pool_{t}_{y}')
        made.append(dict(tech=t, delivery_year=y, n_candidates=len(names), pool_MW=cap))
    return made


def rights_audit(assets):
    """assets: rows (asset_id, owner, site, kind N/R/C, physical_MW, firm_right_MW, contracted_right_MW, rights_source)"""
    df = pd.DataFrame(assets)
    df['oversold'] = df.firm_right_MW + df.contracted_right_MW > df.physical_MW + 1e-9
    df['missing_source'] = df.rights_source.isna() | (df.rights_source.astype(str).str.strip() == '')
    df['status'] = ['FAIL' if o or s else 'OK' for o, s in zip(df.oversold, df.missing_source)]
    return df
