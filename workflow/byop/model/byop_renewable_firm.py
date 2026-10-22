"""TECH_COMP_2 wind / PV / BESS Firm certification by continuous stress windows - MODEL CONSTRUCTION ONLY (A0.2 P4).
This module never calls a solver; a built model is not evidence that any site can serve 72 h.

For one site and year, over EVERY registered window (24 / 48 / 72 h of contiguous 1 h steps):
    0 <= p_wind[t] <= CF_wind[t] x K_wind ;  0 <= p_pv[t] <= CF_pv[t] x K_pv
    0 <= charge[t], discharge[t] <= K_bess ;  0 <= E[t] <= h x K_bess   (h = 4 h)
    E[t] = E[t-1] + sqrt(eta_rt) x charge[t] x dt - discharge[t] x dt / sqrt(eta_rt)   (eta_rt = 0.85; E[-1] = E_initial)
    E_initial <= 0.5 x h x K_bess ;  E_final >= E_initial
    F <= p_wind[t] + p_pv[t] + discharge[t] - charge[t] (+ grid_import[t] only in GRID_FLEX, which is then booked)   for all t
ONE SOC variable E per window (the dispatch SOC); no second / shadow SOC exists. ISLANDED has no grid import variable at all.
F is the certificate of THIS physical asset set (shared physical caps across contracts at the same site); ERCOT system ELCC is
an external reference only and is never assigned to a single islanded site. Weather: the existing PyPSA-USA / TAMU bus
profiles (flag REEDS_MULTIWX_PENDING_LOCAL_H5: single weather year until multi-year ReEDS H5 profiles are on L2).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

WINDOW_HOURS = (24, 48, 72)
MODES = ('ISLANDED', 'GRID_FLEX')


def firm_windows(event_rows_72):
    """24 h = the central day of a pre-registered 72 h event window, 48 h = central + following day, 72 h = the full window"""
    r = list(event_rows_72)
    assert len(r) == 72 and r == list(range(r[0], r[0] + 72))
    return {24: r[24:48], 48: r[24:72], 72: r}


def build_firm_model(cf_wind, cf_pv, windows, mode='ISLANDED', K=None, h=4.0, eta_rt=0.85, dt=1.0, grid_import_cap=0.0):
    """cf_wind / cf_pv: dict window_id -> array (per-unit availability per hour); windows: dict window_id -> hours.
    K: optional dict of fixed capacities (wind, pv, bess); otherwise they are variables. Returns (linopy Model, labels)"""
    import linopy
    import xarray as xr
    assert mode in MODES
    m = linopy.Model()
    cap = {}
    for k in ('wind', 'pv', 'bess'):
        if K is not None and k in K:
            cap[k] = float(K[k])
        else:
            cap[k] = m.add_variables(lower=0.0, name=f'RF-K_{k}')
    F = m.add_variables(lower=0.0, name='RF-F')
    se = math.sqrt(eta_rt)
    lab = dict(soc=[], firm_rows=[], windows=[])
    for wid, hours in windows.items():
        T = int(hours)
        cw = np.asarray(cf_wind[wid], dtype=float)
        cp = np.asarray(cf_pv[wid], dtype=float)
        assert len(cw) == len(cp) == T and (cw >= 0).all() and (cp >= 0).all()
        idx = pd.RangeIndex(T, name='t')
        pw = m.add_variables(lower=0.0, coords=[idx], name=f'RF-p_wind_{wid}')
        pp = m.add_variables(lower=0.0, coords=[idx], name=f'RF-p_pv_{wid}')
        ch = m.add_variables(lower=0.0, coords=[idx], name=f'RF-charge_{wid}')
        dis = m.add_variables(lower=0.0, coords=[idx], name=f'RF-discharge_{wid}')
        E = m.add_variables(lower=0.0, coords=[idx], name=f'RF-E_{wid}')
        E0 = m.add_variables(lower=0.0, name=f'RF-E_initial_{wid}')
        cwa = xr.DataArray(cw, coords=[idx]); cpa = xr.DataArray(cp, coords=[idx])
        m.add_constraints(pw - cwa * cap['wind'] <= 0, name=f'RF-wind_avail_{wid}')
        m.add_constraints(pp - cpa * cap['pv'] <= 0, name=f'RF-pv_avail_{wid}')
        m.add_constraints(ch - cap['bess'] <= 0, name=f'RF-charge_cap_{wid}')
        m.add_constraints(dis - cap['bess'] <= 0, name=f'RF-discharge_cap_{wid}')
        m.add_constraints(E - h * cap['bess'] <= 0, name=f'RF-E_cap_{wid}')
        # SOC chain: E[0] = E0 + ..., E[t] = E[t-1] + ...
        m.add_constraints(E.isel(t=0) - E0 - se * dt * ch.isel(t=0) + (dt / se) * dis.isel(t=0) == 0, name=f'RF-soc_first_{wid}')
        if T > 1:
            prev = E.shift(t=1).isel(t=slice(1, None))
            m.add_constraints(E.isel(t=slice(1, None)) - prev - se * dt * ch.isel(t=slice(1, None)) + (dt / se) * dis.isel(t=slice(1, None)) == 0,
                              name=f'RF-soc_{wid}')
        m.add_constraints(E0 - 0.5 * h * cap['bess'] <= 0, name=f'RF-E_initial_cap_{wid}')
        m.add_constraints(E.isel(t=T - 1) - E0 >= 0, name=f'RF-E_final_ge_initial_{wid}')
        supply = pw + pp + dis - ch
        if mode == 'GRID_FLEX':
            gi = m.add_variables(lower=0.0, upper=float(grid_import_cap), coords=[idx], name=f'RF-grid_import_{wid}')
            supply = supply + gi
        m.add_constraints(F - supply <= 0, name=f'RF-firm_{wid}')
        lab['soc'].append(f'RF-E_{wid}'); lab['firm_rows'].append(f'RF-firm_{wid}'); lab['windows'].append((wid, T))
    return m, lab


def firm_energy_upper_bound(cf_wind, cf_pv, windows, K, mode='ISLANDED', grid_import_cap=0.0):
    """solver-free upper bound: with E_final >= E_initial the window's net storage output is <= 0, so
    F <= min over windows of mean_t(CF_wind K_wind + CF_pv K_pv (+ import cap)); weak wind / sun -> 0, never an arbitrary value"""
    b = []
    for wid in windows:
        x = np.asarray(cf_wind[wid]) * K['wind'] + np.asarray(cf_pv[wid]) * K['pv'] + (grid_import_cap if mode == 'GRID_FLEX' else 0.0)
        b.append(float(x.mean()))
    return min(b)
