#!/usr/bin/env python3
"""NEXT-07 W3.2 item 3: build (never solve) the NEXT-06 full-year 2026 S0 diagnostic model - formal 3 GW reserve, 2026 only, every
3 h snapshot (sample_weeks 0) - and report its real size (nvars / ncons / nnz), build time and peak memory. linopy.Model.solve and
gurobipy.Model.optimize raise before anything reaches a solver. Run on L2 from workflow/:
    python -W ignore byop/tests/structural_n07_fullyear_size.py --out results/BYOP/next07_s0_reserve_probe/_fullyear_size
"""
from __future__ import annotations

import argparse, json, time
from pathlib import Path

import numpy as np

import structural_n07_reserve_probe as S


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    config, siting = S.setup(out)
    S.M.CFG.update(start=2026, end=2026, sample_weeks=None)          # the NEXT-06 diagnostic run_args (2026, sample_weeks 0)
    n, info = S.build_s0(config, out, None)
    m = n.model
    nnz = int(sum(int((np.asarray(m.constraints[k].vars.values) != -1).sum()) for k in m.constraints))
    req = m.constraints['PV16M-reserve_req']
    rep = dict(work_package='BYOP_NEXT_07', step='W3.2 full-year size', solver_executions=0, solver_calls_intercepted=len(S.SOLVER_CALLS),
               snapshots=int(len(n.snapshots)), weight_sum_h=float(n.snapshot_weightings.generators.sum()),
               stores_weight_h=sorted(set(np.round(n.snapshot_weightings.stores.values, 6))), nvars=int(m.nvars), ncons=int(m.ncons), nnz=nnz,
               reserve_req_rhs=sorted(set(np.round(np.asarray(req.rhs.values).ravel(), 6))), soc_segment_rows=sum(k.startswith('A2F08-seg_soc_') for k in m.constraints),
               build_seconds=round(time.time() - t0, 1), peak_rss_GB=round(S.rss_gb(), 2),
               formal_s0_reference=dict(nvars=2660074, ncons=7107710, nnz=35171029, solve_seconds=2281.2, barrier_factor_GB=4.5, threads=10))
    rep['size_ratio_vs_formal_s0'] = dict(nvars=rep['nvars'] / 2660074, nnz=nnz / 35171029)
    (out / 'W3_FULLYEAR_MODEL_SIZE.json').write_text(json.dumps(rep, indent=1), encoding='utf-8')
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
