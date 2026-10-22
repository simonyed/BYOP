#!/usr/bin/env python3
"""AIDC geospatial distribution v1 (work package 2026-10-22): switchable research-AIDC siting `dynamic_pnnl_v1`.
Deterministic, no LP, no solver. Writes ONLY *_GEO_DYNAMIC_V1 files; the legacy eight-bus inputs (MAINLINE_RESEARCH_COHORTS_TAMU64,
GREAL_POI_ASSUMPTIONS, GREAL_POI_E0_SCHEDULE, MAINLINE_INHERITED_RAMP_2025, ...) are read and never written (SHA checked).
    python byop/build/build_dynamic_siting_inputs.py --config byop/inputs/dc/MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml --variant dynamic_pnnl_v1

Accounting per scenario sc and year y (§3.2):
    T = ERCOT_DC_TOTALS.new_IT_MW,  H = D11 inherited end-2025 ramp (2026 only),  F = LOCKED_VERIFIED research increment
    R = T - H - F >= 0  (else BLOCKED_DATA_CONFLICT),  NEW_b = LOCKED_b + R * w_b,  sum_b NEW_b + H = T
    2026: NEW_b = original Epoch research cohort (alpha = 1).
Weights (§3.3): w = normalise_B(alpha_y E_sc,y + beta_y A + gamma_y P), each source normalised first;
    E_sc,y,b = share of the original Epoch research cohort minus its locked part (forecast part) in (sc, y),
    A_b = PNNL Atlas independent-site share (crypto excluded, site clusters), P_b = 0.25 P(g0) + 0.75 P(g50).
    A source that is zero on the allowed set drops out and the remaining mixing weights are renormalised (logged).
Candidates (§3.4): q_b = (E_decade + A + P) / 3 (mid 2026-2035); keep all Epoch buses and non-Epoch buses with
    q_b x (mid research total) >= 36 MW IT; buses evidenced only by crypto-mining Atlas records are dropped.
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
WF = HERE.parents[1]
INP = WF / 'byop/inputs'
DC, POI = INP / 'dc', INP / 'poi'
BASE = WF / 'results/BYOP/baseline_2025_tamu'
SUF = 'GEO_DYNAMIC_V1'
LEGACY = [DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv', DC / 'MAINLINE_INHERITED_RAMP_2025.csv', DC / 'MAINLINE_AIDC_RECONCILIATION.csv',
          DC / 'MAINLINE_BUS_SITE_POI_MAP.csv', DC / 'EPOCH_TX_SITES_TAMU64.csv', DC / 'EPOCH_TX_TIMELINE_EVIDENCE.csv',
          DC / 'EPOCH_SITE_SERVICE_TAMU64.csv', DC / 'ERCOT_DC_TOTALS_2026_2035.csv', POI / 'GREAL_POI_ASSUMPTIONS.csv',
          POI / 'GREAL_POI_E0_SCHEDULE.csv', POI / 'GREAL_R_ASSET_POOL.csv']
PNNL = [DC / 'PNNL_ATLAS_TX_SITES_TAMU64.csv', DC / 'PNNL_PROJECTED_HIGHER_TX_TAMU64.csv', DC / 'PNNL_CANDIDATE_BUS_SUMMARY.csv',
        DC / 'PNNL_PROVENANCE.json']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
HIST_ROUND_MW = 1e-2      # max legacy 4-decimal rounding gap of the 2026 Epoch cohort row sum (8 buses x 5e-5), corrected + logged
PUE = pd.read_csv(DC / 'state_pue_2022_2050.csv')
pue = lambda y: float(PUE[(PUE.st == 'TX') & (PUE.year == y)].pue.iloc[0])


class DataConflict(RuntimeError):
    """BLOCKED_DATA_CONFLICT: stop, never trim real projects or change ERCOT totals"""


# ------------------------------------------------------------------------------------------------ pure helpers (unit-tested)
def normalise(s: pd.Series) -> pd.Series:
    """non-negative finite shares summing to 1; an all-zero source returns zeros (caller drops it)"""
    s = pd.Series(s, dtype=float)
    if s.isna().any() or not np.isfinite(s.values).all():
        raise ValueError(f'source has NaN / inf: {list(s.index[~np.isfinite(s.values)])}')
    if (s < 0).any():
        raise ValueError(f'negative source weight: {list(s.index[s < 0])}')
    t = s.sum()
    return s / t if t > 0 else s * 0.0


def mix_for_year(cfg, y):
    for r in cfg['mix_weights']:
        if int(r['from']) <= y <= int(r['to']):
            return dict(epoch=float(r['epoch']), atlas=float(r['atlas']), projected=float(r['projected']))
    raise ValueError(f'no mixing weights for {y}')


def mixed_weights(E, A, P, mix, allowed):
    """w_b = normalise_allowed(alpha E + beta A + gamma P); sources normalised on the allowed set first. Returns (w, used_mix)"""
    src = {'epoch': normalise(E.reindex(allowed).fillna(0.0)), 'atlas': normalise(A.reindex(allowed).fillna(0.0)),
           'projected': normalise(P.reindex(allowed).fillna(0.0))}
    used = {k: (v if src[k].sum() > 0 else 0.0) for k, v in mix.items()}
    tot = sum(used.values())
    if tot <= 0:
        raise ValueError('all spatial sources are zero on the allowed bus set')
    used = {k: v / tot for k, v in used.items()}
    raw = sum(used[k] * src[k] for k in src)
    return normalise(raw), used


def allocate(T, H, locked, w, tol=1e-4):
    """NEW_b = locked_b + R w_b, R = T - H - sum(locked). Raises DataConflict when the locked growth exceeds T - H."""
    locked = pd.Series(locked, dtype=float).reindex(w.index).fillna(0.0)
    if (locked < -1e-12).any():
        raise ValueError('negative locked growth')
    R = float(T) - float(H) - float(locked.sum())
    if R < -tol:
        raise DataConflict(f'BLOCKED_DATA_CONFLICT: locked {locked.sum():.6f} + inherited {H:.6f} > approved total {T:.6f}')
    R = max(R, 0.0)
    fc = R * w
    return locked, fc, R


def check_ercot_buses(buses, net):
    """every candidate must be an AC bus of the ERCOT TAMU64 network (ReEDS zones p60-p67); fail closed otherwise"""
    bad = [b for b in buses if b not in net.index or not str(net.reeds_zone.get(b, '')).startswith('p6')]
    if bad:
        raise DataConflict(f'candidate buses not in the ERCOT TAMU64 network: {bad}')


def queue_buckets(sites, years):
    """Epoch queue increments per (site, epoch_year) after end-2025 (same rule as build_epoch_tamu_allocation.py)"""
    q = []
    for r in sites.itertuples():
        prev = float(r.IT_MW_2025)
        for y in years:
            v = float(getattr(r, f'IT_MW_{y}'))
            if v > prev + 1e-9:
                q.append(dict(site=r.site, bus=r.bus, epoch_year=y, bucket_IT_MW=v - prev))
            prev = max(prev, v)
    return pd.DataFrame(q)


# ------------------------------------------------------------------------------------------------ sources
def epoch_tables(cfg):
    coh = pd.read_csv(DC / 'MAINLINE_RESEARCH_COHORTS_TAMU64.csv')
    sites = pd.read_csv(DC / 'EPOCH_TX_SITES_TAMU64.csv')
    sites = sites[sites.ercot & sites.bus.notna()]
    svc = pd.read_csv(DC / 'EPOCH_SITE_SERVICE_TAMU64.csv')
    return coh, sites, svc


def atlas_share(cfg):
    at = pd.read_csv(DC / 'PNNL_ATLAS_TX_SITES_TAMU64.csv', dtype={'id': str, 'site_cluster': str, 'contained_in_id': str})
    at = at[at.ercot]
    nc = at[at.crypto_flag.fillna('') != cfg['atlas']['exclude_crypto_flag']]
    root_bus = at.set_index('id').bus
    clusters = nc.drop_duplicates('site_cluster').assign(bus=lambda d: d.site_cluster.map(root_bus).fillna(d.bus))
    counts = pd.DataFrame(dict(
        atlas_raw_all=at.groupby('bus').size(),
        atlas_raw_noncrypto=nc.groupby('bus').size(),
        atlas_explicit_dedup_noncrypto=nc[nc.dup_class != 'EXPLICIT_DUP_CONTAINED'].groupby('bus').size(),
        atlas_clusters_noncrypto=clusters.groupby('bus').size(),
        atlas_crypto_excluded=at[at.crypto_flag.fillna('') == cfg['atlas']['exclude_crypto_flag']].groupby('bus').size())).fillna(0.0)
    basis = {'noncrypto_clusters': 'atlas_clusters_noncrypto', 'explicit_dedup': 'atlas_explicit_dedup_noncrypto', 'raw': 'atlas_raw_noncrypto'}
    return normalise(counts[basis[cfg['atlas']['count_basis']]]), counts


def projected_shares(cfg):
    pr = pd.read_csv(DC / 'PNNL_PROJECTED_HIGHER_TX_TAMU64.csv')
    pr = pr[pr.ercot]
    g = {gw: normalise(pr[pr.market_gravity_weight == gw].groupby('bus').IT_MW.sum()) for gw in sorted(pr.market_gravity_weight.unique())}
    allb = sorted(set().union(*[set(s.index) for s in g.values()]))
    g = {k: v.reindex(allb).fillna(0.0) for k, v in g.items()}
    mix = {int(k): float(v) for k, v in cfg['projected']['gravity_mix'].items()}
    P = normalise(sum(w_ * g[k] for k, w_ in mix.items()))
    variants = dict(main_g0_25_g50_75=P, g0_only=g[0], g50_only=g[50], g5_equal=normalise(sum(g.values())))
    return P, pd.DataFrame(variants), g


# ------------------------------------------------------------------------------------------------ build
def build(cfg, write=True):
    YRS, SCN = [int(y) for y in cfg['years']], list(cfg['scenarios'])
    tot = pd.read_csv(DC / 'ERCOT_DC_TOTALS_2026_2035.csv').set_index(['scenario', 'year']).new_IT_MW
    ramp = pd.read_csv(DC / 'MAINLINE_INHERITED_RAMP_2025.csv')
    H26 = float(ramp.inherited_ramp_IT_MW.sum())
    coh, sites, svc = epoch_tables(cfg)
    epoch_buses = sorted(sites.bus.unique())
    orig = coh.pivot_table(index=['scenario', 'request_year'], columns='region_id', values='IT_MW', aggfunc='sum').fillna(0.0)
    # ---------------- verified / forecast ledger (§3.2)
    q = queue_buckets(sites, YRS)
    lk = pd.DataFrame(cfg.get('locked_verified') or [], columns=['site', 'epoch_year', 'IT_MW', 'evidence'])
    q = q.merge(lk.rename(columns={'IT_MW': 'locked_IT_MW', 'evidence': 'lock_evidence'}), on=['site', 'epoch_year'], how='left')
    if len(lk) and len(q[q.locked_IT_MW.notna()]) != len(lk):
        raise DataConflict(f'locked_verified entries without an Epoch queue bucket: {lk.to_dict("records")}')
    if (q.locked_IT_MW.fillna(0.0) > q.bucket_IT_MW + 1e-9).any():
        raise DataConflict('locked IT exceeds the Epoch bucket: ' + str(q[q.locked_IT_MW > q.bucket_IT_MW].to_dict('records')))
    notes = {(r['site'], int(r['epoch_year'])): r['note'] for r in (cfg.get('forecast_review_notes') or [])}
    q['locked_IT_MW'] = q.locked_IT_MW.fillna(0.0)
    q['lock_share'] = q.locked_IT_MW / q.bucket_IT_MW
    q['classification'] = np.where(q.lock_share >= 1 - 1e-9, 'LOCKED_VERIFIED',
                                   np.where(q.lock_share > 0, 'PARTLY_LOCKED_VERIFIED', 'FORECAST_REALLOCATABLE'))
    q['evidence_or_review_note'] = [e if isinstance(e, str) else notes.get((s, int(y)), 'no reviewed operational observation by as_of: forecast prior')
                                    for e, s, y in zip(q.lock_evidence, q.site, q.epoch_year)]
    q['rule'] = ('LOCKED only with a reviewed Epoch timeline row dated <= as_of, no estimate wording, capacity reported operational with a '
                 'cited source / satellite observation (YAML locked_verified); E0 equipment or a project name alone never locks')
    # locked part served per (scenario, year, bus): served(site, bucket) x lock_share
    sv = svc.merge(q[['site', 'epoch_year', 'lock_share']], on=['site', 'epoch_year'], how='left').fillna({'lock_share': 0.0})
    sv['locked_served'] = sv.served_IT_MW * sv.lock_share
    LOCK = sv.groupby(['scenario', 'year', 'bus']).locked_served.sum()
    # ---------------- sources and candidate eligibility (§3.4)
    A, acounts = atlas_share(cfg)
    P, pvar, pg = projected_shares(cfg)
    summ = pd.read_csv(DC / 'PNNL_CANDIDATE_BUS_SUMMARY.csv').set_index('bus')
    ref = cfg['eligibility']['reference_scenario']
    dec = orig.loc[ref].sum()
    E_dec = normalise(dec)
    research_total_ref = float(orig.loc[ref].values.sum())
    union = sorted(set(E_dec.index[E_dec > 0]) | set(epoch_buses) | set(acounts.index[acounts.atlas_raw_all > 0]) | set(P.index[pvar.max(axis=1) > 0]))
    el = pd.DataFrame(index=pd.Index(union, name='bus'))
    el['zone'] = summ.zone.reindex(union)
    el['src_epoch'] = el.index.isin(epoch_buses)
    el['src_atlas_any'] = acounts.atlas_raw_all.reindex(union).fillna(0) > 0
    el['src_atlas_noncrypto'] = acounts.atlas_raw_noncrypto.reindex(union).fillna(0) > 0
    el['src_projected'] = pvar.max(axis=1).reindex(union).fillna(0) > 0
    el['crypto_only'] = el.src_atlas_any & ~el.src_atlas_noncrypto & ~el.src_epoch & ~el.src_projected
    for c in acounts.columns:
        el[c] = acounts[c].reindex(union).fillna(0.0)
    el['E_decade'] = E_dec.reindex(union).fillna(0.0)
    el['A'] = A.reindex(union).fillna(0.0)
    for c in pvar.columns:
        el[f'P_{c}'] = pvar[c].reindex(union).fillna(0.0)
    for k, v in pg.items():
        el[f'proj_higher_g{k}_share'] = v.reindex(union).fillna(0.0)
    el['q'] = (el.E_decade + el.A + el.P_main_g0_25_g50_75) / 3.0
    el['q_x_mid_research_total_IT_MW'] = el.q * research_total_ref
    thr = float(cfg['eligibility']['threshold_IT_MW'])
    el['eligible'] = (el.src_epoch & bool(cfg['eligibility']['keep_all_epoch_buses'])) | (~el.crypto_only & (el.q_x_mid_research_total_IT_MW >= thr))
    el['reason'] = np.where(el.src_epoch, 'Epoch bus (always kept)',
                            np.where(el.crypto_only, 'dropped: evidenced only by crypto-mining Atlas records',
                                     np.where(el.eligible, f'q x mid total >= {thr:g} MW IT', f'dropped: q x mid total < {thr:g} MW IT')))
    net = pd.read_csv(BASE / 'BUS_LEDGER.csv', index_col=0)
    check_ercot_buses(el.index, net)
    B = sorted(el.index[el.eligible])
    # ---------------- yearly dynamic weights and allocation
    W, REC, ROUND = [], [], []
    tol = float(cfg['reconciliation_tol_MW'])
    for sc in SCN:
        for y in YRS:
            T = float(tot[(sc, y)])
            H = H26 if y == YRS[0] else 0.0
            o = orig.loc[(sc, y)].reindex(B).fillna(0.0)
            if abs(float(orig.loc[(sc, y)].sum()) - float(o.sum())) > 1e-9:
                raise DataConflict(f'original Epoch research growth outside the candidate set in {sc} {y}')
            lockd = LOCK.reindex(pd.MultiIndex.from_product([[sc], [y], B])).fillna(0.0).droplevel([0, 1]) if y > YRS[0] else pd.Series(0.0, index=B)
            mix = mix_for_year(cfg, y)
            if y == YRS[0]:            # §3.2: 2026 research growth keeps the original Epoch layout
                lk26 = LOCK.reindex(pd.MultiIndex.from_product([[sc], [y], B])).fillna(0.0).droplevel([0, 1])
                if mix['epoch'] != 1.0:
                    raise ValueError('2026 must be alpha = 1 (original Epoch layout)')
                new = o.copy(); locked_y = lk26.clip(upper=o); fc = new - locked_y
                w = normalise(o); used = dict(epoch=1.0, atlas=0.0, projected=0.0); R = T - H - float(locked_y.sum())
                if abs(float(o.sum()) + H - T) > HIST_ROUND_MW:
                    raise DataConflict(f'2026 original research + D11 != approved total in {sc}: {o.sum() + H} vs {T}')
            else:
                Ef = (o - lockd).clip(lower=0.0)
                E = Ef if Ef.sum() > 0 else E_dec.reindex(B).fillna(0.0)
                w, used = mixed_weights(E, A, P, mix, B)
                locked_y, fc, R = allocate(T, H, lockd, w, tol)
                new = locked_y + fc
            gap = T - (float(new.sum()) + H)
            if abs(gap) > 1e-9:
                ROUND.append(dict(scenario=sc, year=y, gap_before_MW=gap))
                lim = HIST_ROUND_MW if y == YRS[0] else tol     # 2026 carries the 4-decimal rounding of the legacy cohort CSV
                if abs(gap) < lim and fc.sum() > 0:     # deterministic last-term correction on the largest forecast bus
                    b_ = fc.idxmax(); fc[b_] += gap; new[b_] += gap
                    ROUND[-1].update(corrected_bus=b_, gap_after_MW=T - (float(new.sum()) + H))
                elif abs(gap) >= lim:
                    raise DataConflict(f'allocation does not reproduce the approved total in {sc} {y}: gap {gap}')
            for b in B:
                W.append(dict(scenario=sc, year=y, bus=b, alpha=used['epoch'], beta=used['atlas'], gamma=used['projected'],
                              alpha_cfg=mix['epoch'], beta_cfg=mix['atlas'], gamma_cfg=mix['projected'],
                              E_share=float(normalise(o if y == YRS[0] else E).get(b, 0.0)), A_share=float(normalise(A.reindex(B).fillna(0.0)).get(b, 0.0)),
                              P_share=float(normalise(P.reindex(B).fillna(0.0)).get(b, 0.0)), w=float(w.get(b, 0.0)),
                              original_epoch_research_IT_MW=float(o[b]), verified_2026plus_increment_IT_MW=float(locked_y[b]),
                              forecast_reallocated_increment_IT_MW=float(fc[b]), new_research_IT_MW=float(new[b])))
            REC.append(dict(scenario=sc, year=y, ERCOT_approved_new_IT_MW=T, D11_inherited_IT_MW=H, locked_verified_IT_MW=float(locked_y.sum()),
                            forecast_residual_IT_MW=float(fc.sum()), new_research_IT_MW=float(new.sum()),
                            check_abs_error_MW=abs(T - (float(new.sum()) + H)), n_buses_positive=int((new > 1e-9).sum()),
                            stock_2025_avg_IT_MW_in_background=float(sites.IT_MW_2025_avg.sum())))
    W, REC = pd.DataFrame(W), pd.DataFrame(REC)
    REC['check'] = np.where(REC.check_abs_error_MW < tol, 'PASS', 'FAIL')
    if (REC.check != 'PASS').any():
        raise DataConflict('annual reconciliation failed')
    # ---------------- v1.3-compatible cohorts (every eligible bus x year, explicit zeros)
    zone = el.zone
    cz = W.copy()
    cz['cohort_id'] = 'TX_' + cz.scenario + '_' + cz.year.astype(str) + '_' + cz.bus.str.replace(' ', '')
    cz['st'] = 'TX'
    cz['parent_zone'] = cz.bus.map(zone)
    cz['spatial_basis'] = cfg['variant']
    cz['status'] = f"AIDC geospatial v1 ({cfg['variant']})"
    cz['quality'] = np.where(cz.year == YRS[0], 'RESEARCH_NEW_AIDC (2026: original Epoch layout minus D11)',
                             'RESEARCH_NEW_AIDC (locked verified + forecast residual x dynamic Epoch/PNNL weights)')
    cz['inherited_end2025_ramp_IT_MW_background'] = np.where(cz.year == YRS[0], cz.bus.map(ramp.set_index('bus').inherited_ramp_IT_MW).fillna(0.0), 0.0)
    cz['inherited_ramp_IT_MW'] = cz.inherited_end2025_ramp_IT_MW_background      # legacy column semantics (not in IT_MW)
    cz['stock_2025_avg_IT_MW_in_background'] = np.where(cz.year == YRS[0], cz.bus.map(ramp.set_index('bus').IT_MW_2025_avg).fillna(0.0), 0.0)
    cz = cz.rename(columns={'year': 'request_year', 'bus': 'region_id', 'new_research_IT_MW': 'IT_MW'})
    cz['approved_cohort_IT_MW'] = cz.IT_MW + cz.inherited_end2025_ramp_IT_MW_background
    coh_cols = ['cohort_id', 'scenario', 'request_year', 'st', 'region_id', 'IT_MW', 'parent_zone', 'spatial_basis', 'status', 'quality',
                'inherited_ramp_IT_MW', 'approved_cohort_IT_MW', 'verified_2026plus_increment_IT_MW', 'forecast_reallocated_increment_IT_MW',
                'original_epoch_research_IT_MW', 'inherited_end2025_ramp_IT_MW_background', 'stock_2025_avg_IT_MW_in_background']
    cz = cz[coh_cols].sort_values(['scenario', 'request_year', 'region_id']).reset_index(drop=True)
    # ---------------- POI (§5): the eight Epoch rows keep every evidence field; derived fields recomputed with OLD / NEW
    poi0 = pd.read_csv(POI / 'GREAL_POI_ASSUMPTIONS.csv')
    mid = cz[(cz.scenario == 'mid') & (cz.request_year <= 2031)].groupby('region_id').IT_MW.sum()
    fac = lambda b: float(mid.get(b, 0.0)) * pue(2031)
    np_ = cfg['new_bus_poi']
    rows, delta = [], []
    for r in poi0.itertuples(index=False):
        d = r._asdict()
        new_vals = dict(research_IT_MW_2026_2031_mid=float(mid.get(r.bus, 0.0)), research_facility_MW_2031_mid=fac(r.bus),
                        pclr_conditional_MW=round(np_['pclr_share_of_2031_facility_MW'] * fac(r.bus), 1),
                        onsite_renewable_cap_MW=round(np_['onsite_renewable_share_of_2031_facility_MW'] * fac(r.bus), 1))
        for k, v in new_vals.items():
            delta.append(dict(bus=r.bus, field=k, OLD=d[k], NEW=v, DELTA=v - float(d[k]),
                              formula={'research_IT_MW_2026_2031_mid': 'sum mid research IT 2026-2031 (dynamic cohorts)',
                                       'research_facility_MW_2031_mid': 'research_IT_MW_2026_2031_mid x PUE(TX, 2031)',
                                       'pclr_conditional_MW': '0.3 x research_facility_MW_2031_mid (PROXY)',
                                       'onsite_renewable_cap_MW': '1.0 x research_facility_MW_2031_mid (PROXY; ReEDS bus cap shared)'}[k]))
            d[k] = v
        d.update(siting_variant=cfg['variant'], bus_class='EPOCH_LEGACY (evidence fields unchanged; derived fields recomputed)')
        rows.append(d)
    k = list(poi0.columns)
    for b in [b for b in B if b not in set(poi0.bus)]:
        s_ = el.loc[b]
        srcs = '; '.join(x for x, f in (('PNNL_ATLAS', s_.src_atlas_noncrypto), ('PNNL_PROJECTED', s_.src_projected)) if f)
        d = {c: np.nan for c in k}
        d.update(site_id=b, site_name=f'{b} PNNL candidate research bus (no Epoch site; {srcs})', bus=b, lat=float(net.y[b]), lon=float(net.x[b]),
                 epoch_sites='', research_IT_MW_2026_2031_mid=float(mid.get(b, 0.0)), research_facility_MW_2031_mid=fac(b),
                 E0_total_MW=float(np_['E0_total_MW']), poi_upgrade_max_MW=float(np_['poi_upgrade_max_MW']),
                 pclr_conditional_MW=round(np_['pclr_share_of_2031_facility_MW'] * fac(b), 1), pclr_conditional_COD_offset_y=0.0,
                 gas_evidence_level=np_['gas_evidence_level'], gas_MDQ_MMBtu_d=np.nan,
                 gas_note='PROXY_PNNL_NEW_SITE: no bus / site gas evidence; L2 conservative bounded proxy (lead 3 y, 100 USD/kW, MDQ 100,000 MMBtu/d)',
                 onsite_renewable_cap_MW=round(np_['onsite_renewable_share_of_2031_facility_MW'] * fac(b), 1),
                 ev_E0='PROXY_PNNL_NEW_SITE: E0 = 0 means no evidence that NEW research demand holds approved spare equipment; NOT a statement that the real POI capacity is zero',
                 ev_upgrade='PROXY_PNNL_NEW_SITE (v1.3 uniform upgrade proxy)', ev_procedure='PROXY_PNNL_NEW_SITE (ERCOT Batch Zero: allocation 2027, energization >= 2028)',
                 ev_pclr='PROXY_PNNL_NEW_SITE (0.3 x 2031 research facility MW: research upper-bound proxy, not an existing eligibility)',
                 ev_gas='L2 PROXY_PNNL_NEW_SITE', ev_onsite_renewable='PROXY_PNNL_NEW_SITE (1.0 x 2031 research facility MW; ReEDS bus cap shared with public)',
                 confidence=np_['confidence'], run_status='PENDING_RESEARCHER_AUDIT', procedural_basis='ERCOT Batch Zero large-load process (SRC-03/10/12) - uniform proxy',
                 siting_variant=cfg['variant'], bus_class='PNNL_NEW_SITE')
        for c, v in (('poi_upgrade_lead_y', np_['poi_upgrade_lead_y']), ('poi_upgrade_cost_USD_kW', np_['poi_upgrade_cost_USD_kW']),
                     ('earliest_grid_COD', np_['earliest_grid_COD']), ('gas_lateral_lead_y', np_['gas_lateral_lead_y']),
                     ('gas_lateral_cost_USD_kW', np_['gas_lateral_cost_USD_kW'])):
            for case in ('low', 'base', 'high'):
                d[f'{c}_{case}'] = float(v[case])
        rows.append(d)
    poi = pd.DataFrame(rows)[k + ['siting_variant', 'bus_class']].sort_values('bus').reset_index(drop=True)
    # ---------------- POI / gas risk register (§5.3) and display map
    first = cz[(cz.scenario == 'mid') & (cz.IT_MW > 1e-9)].groupby('region_id').request_year.min()
    rv = pd.read_csv(DC / 'PNNL_SPATIAL_MAPPING_REVIEW.csv') if (DC / 'PNNL_SPATIAL_MAPPING_REVIEW.csv').exists() else pd.DataFrame(columns=['bus', 'boundary_tie'])
    risk = []
    for r in poi.itertuples():
        s_ = el.loc[r.bus]
        new_bus = r.bus_class == 'PNNL_NEW_SITE'
        fy = first.get(r.bus, np.nan)
        flags = []
        if new_bus and s_.src_atlas_noncrypto:
            flags.append('ATLAS_WITHOUT_E0_EVIDENCE')
        if new_bus and s_.src_projected and not s_.src_atlas_noncrypto:
            flags.append('PROJECTED_ONLY_NO_ATLAS')
        if s_.atlas_crypto_excluded > 0:
            flags.append('CRYPTO_RECORDS_EXCLUDED')
        if (rv.bus == r.bus).any() and rv[rv.bus == r.bus].boundary_tie.astype(bool).any():
            flags.append('BOUNDARY_TIE_RECORDS')
        if new_bus and fy == fy and fy < float(r.earliest_grid_COD_base):
            flags.append('POI_PROXY_MAY_DRIVE_DELAY')
        risk.append(dict(bus=r.bus, bus_class=r.bus_class, candidate_sources=';'.join(x for x, f in (('EPOCH', s_.src_epoch), ('ATLAS', s_.src_atlas_noncrypto),
                                                                                              ('PROJECTED', s_.src_projected)) if f),
                         map_confidence='EPOCH_GEOCODED' if s_.src_epoch else ('ATLAS_OSM_CENTROID' if s_.src_atlas_noncrypto else 'CERF_MODEL_CENTROID'),
                         atlas_independent_sites=float(s_.atlas_clusters_noncrypto), projected_g0_MW_share=float(s_.proj_higher_g0_share),
                         projected_g50_MW_share=float(s_.proj_higher_g50_share), year_first_forecast_MW_mid=fy,
                         existing_ERCOT_POI_evidence='see GREAL_POI_E0_SCHEDULE.csv (Epoch campus)' if not new_bus else 'none in repository',
                         E0_new_request_MW=float(r.E0_total_MW), earliest_grid_COD_base=float(r.earliest_grid_COD_base), U_lead_base=float(r.poi_upgrade_lead_y_base),
                         U_max_MW=float(r.poi_upgrade_max_MW), PCLR_MW=float(r.pclr_conditional_MW), gas_level=r.gas_evidence_level,
                         gas_lateral_lead_base=float(r.gas_lateral_lead_y_base), renewable_cap_MW=float(r.onsite_renewable_cap_MW),
                         research_IT_MW_2026_2031_mid=float(r.research_IT_MW_2026_2031_mid),
                         evidence_class='PROXY_PNNL_NEW_SITE' if new_bus else 'EPOCH_LEGACY', risk_flags=';'.join(flags)))
    risk = pd.DataFrame(risk)
    bmap = pd.DataFrame([dict(bus=r.bus, display_name=(r.site_name if r.bus_class == 'EPOCH_LEGACY' else f'{r.bus} (PNNL candidate; counties {";".join(str(net.counties[r.bus]).split(";")[:3])})'),
                              bus_class=r.bus_class, lat=r.lat, lon=r.lon,
                              coord_basis='Epoch site mean' if r.bus_class == 'EPOCH_LEGACY' else 'TAMU64 bus coordinate (BUS_LEDGER x / y)',
                              note='research load bus; NOT an existing campus or approved project' if r.bus_class != 'EPOCH_LEGACY' else 'Epoch historical sites')
                         for r in poi.itertuples()])
    # ---------------- P-variant comparison (input side only, mid 2026-2035)
    pc = []
    for vn in pvar.columns:
        tmp = []
        for y in YRS[1:]:
            o = orig.loc[('mid', y)].reindex(B).fillna(0.0)
            lockd = LOCK.reindex(pd.MultiIndex.from_product([['mid'], [y], B])).fillna(0.0).droplevel([0, 1])
            Ef = (o - lockd).clip(lower=0.0)
            w, _ = mixed_weights(Ef if Ef.sum() > 0 else E_dec.reindex(B).fillna(0.0), A, pvar[vn], mix_for_year(cfg, y), B)
            lk_, fc_, _ = allocate(float(tot[('mid', y)]), 0.0, lockd, w)
            tmp.append(lk_ + fc_)
        s26 = orig.loc[('mid', YRS[0])].reindex(B).fillna(0.0)
        tsum = sum(tmp) + s26
        for b in B:
            pc.append(dict(P_variant=vn, bus=b, mid_research_IT_MW_2026_2035=float(tsum[b]), share=float(tsum[b] / tsum.sum())))
    pc = pd.DataFrame(pc)
    out = {f'MAINLINE_RESEARCH_COHORTS_TAMU64_{SUF}.csv': (DC, cz), f'MAINLINE_AIDC_RECONCILIATION_{SUF}.csv': (DC, REC),
           f'MAINLINE_SITING_WEIGHTS_{SUF}.csv': (DC, W), f'GREAL_POI_ASSUMPTIONS_{SUF}.csv': (POI, poi),
           f'MAINLINE_SITE_CLASSIFICATION_{SUF}.csv': (DC, q.drop(columns=['lock_evidence'])),
           f'MAINLINE_CANDIDATE_BUS_ELIGIBILITY_{SUF}.csv': (DC, el.reset_index()), f'MAINLINE_NEW_BUS_POI_RISK_{SUF}.csv': (DC, risk),
           f'MAINLINE_NEW_RESEARCH_BUS_POI_MAP_{SUF}.csv': (DC, bmap), f'MAINLINE_POI_DERIVED_DELTA_{SUF}.csv': (POI, pd.DataFrame(delta)),
           f'MAINLINE_SITING_P_VARIANTS_{SUF}.csv': (DC, pc),
           f'ROUNDING_RECONCILIATION_{SUF}.csv': (DC, pd.DataFrame(ROUND, columns=['scenario', 'year', 'gap_before_MW', 'corrected_bus', 'gap_after_MW']))}
    res = dict(buses=B, n_buses=len(B), eligibility=el, cohorts=cz, rec=REC, weights=W, poi=poi, risk=risk, classification=q, pvar=pc, files={})
    if write:
        legacy_before = {str(p.relative_to(WF).as_posix()): sha(p) for p in LEGACY}
        for nm, (d, df) in out.items():
            p = d / nm
            df.to_csv(p, index=False, lineterminator='\n', float_format='%.9f')
            res['files'][str(p.relative_to(WF).as_posix())] = sha(p)
        legacy_after = {str(p.relative_to(WF).as_posix()): sha(p) for p in LEGACY}
        assert legacy_before == legacy_after, 'legacy input changed'
        man = dict(variant=cfg['variant'], config=str(Path(cfg['_path']).relative_to(WF).as_posix()), config_sha256=sha(cfg['_path']),
                   builder=str(Path(__file__).relative_to(WF).as_posix()), builder_sha256=sha(__file__),
                   legacy_inputs_sha256_unchanged=legacy_after, pnnl_inputs_sha256={str(p.relative_to(WF).as_posix()): sha(p) for p in PNNL},
                   outputs_sha256=res['files'], n_buses=len(B), buses=B, solver_executions=0)
        mp = DC / f'MAINLINE_SITING_BUILD_MANIFEST_{SUF}.json'
        mp.write_bytes((json.dumps(man, indent=1) + '\n').encode())
        res['manifest'] = str(mp.relative_to(WF).as_posix())
    return res


def load_cfg(path):
    cfg = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    cfg['_path'] = str(Path(path).resolve())
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=str(DC / 'MAINLINE_SITING_SCENARIO_DYNAMIC_V1.yaml'))
    ap.add_argument('--variant', default='dynamic_pnnl_v1')
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    if cfg['variant'] != a.variant:
        raise SystemExit(f"config variant {cfg['variant']} != --variant {a.variant}")
    r = build(cfg)
    mid = r['cohorts'][r['cohorts'].scenario == 'mid'].groupby('region_id').IT_MW.sum().sort_values(ascending=False)
    print(json.dumps(dict(variant=cfg['variant'], n_buses=r['n_buses'], buses=r['buses'],
                          reconciliation=f"{(r['rec'].check == 'PASS').sum()}/{len(r['rec'])} PASS",
                          top3_share_mid_2026_2035=round(float(mid.head(3).sum() / mid.sum()), 4),
                          mid_research_total=round(float(mid.sum()), 6), files=r['files']), indent=1))
    print(mid.round(2).to_string())


if __name__ == '__main__':
    main()
