#!/usr/bin/env python3
"""NEXT-09 (2026-10-23): freeze the NEXT-08b LP1 v3 lossy candidate as the independent baseline version v1.7L (no solver).
Run on L2 from workflow/:
    python -W ignore byop/build/freeze_baseline_v17l.py
  1  source = results/BYOP/next08b_lp1_loss_upper_fix/baseline_2025_tamu_lossy_candidate.nc; its SHA must equal the v3 seal, the
     LP1-IT2 QA and the registry entry (config/config.byop_baseline_registry.yaml, v17l)
  2  byte copy to results/BYOP/baseline_2025_tamu_v17_lossy/baseline_2025_tamu_v17_lossy_prepared.nc (never overwritten: an existing
     file must already have the pinned SHA, otherwise STOP); the copy is re-hashed
  3  full component diff against v1.6 prepared.nc (meta, every static column, every time series): the only admissible differences are
     Line s_nom and Line r (LINE_DIFF_VS_V16.csv) and the free-text meta label `baseline`; x unchanged; meta transmission_losses 2
  4  the frozen v1.6 NetCDFs, the NEXT-08 / NEXT-08b candidates and the v3 ledger are re-hashed (unchanged)
Writes BASELINE_V17L_RECORD.json + LINE_DIFF_VS_V16.csv next to the copy. Adoption is NOT done here (registry, researcher only).
"""
from __future__ import annotations

import json, os, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

WF = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WF / 'byop/model'))
import baseline_registry as BR  # noqa: E402
import byop_paths as BP  # noqa: E402

ROOT = WF.parent
SRC_DIR = BP.RESULTS / 'next08b_lp1_loss_upper_fix'
SRC = SRC_DIR / 'baseline_2025_tamu_lossy_candidate.nc'
SEAL = ROOT / 'current_work_pckg/BYOP_NEXT_08B_LP1_TANGENT_FIX/LOSSY_LP1_V3_SEAL.json'
FROZEN = {'v16 prepared.nc': BP.BASE_TAMU_V16_DIR / 'baseline_2025_tamu_prepared.nc',
          'v16 raw_uncalibrated.nc': BP.BASE_TAMU_V16_DIR / 'baseline_2025_tamu_raw_uncalibrated.nc',
          'NEXT-08 v1 candidate.nc': BP.RESULTS / 'next08_lossy_lp1/baseline_2025_tamu_lossy_candidate.nc',
          'NEXT-08b v2 candidate.nc': BP.RESULTS / 'next08b_lp1_tangent_fix/baseline_2025_tamu_lossy_candidate.nc',
          'NEXT-08b v3 ledger': SRC_DIR / 'LOSSY_LP1_SOLVE_LOG.csv'}
ALLOWED = {('Line', 's_nom'), ('Line', 'r')}


def same(x, y):
    """element-wise equality that treats NaN == NaN and inf == inf (string fallback for objects)"""
    if pd.api.types.is_numeric_dtype(x) and pd.api.types.is_numeric_dtype(y):
        a, b = x.astype(float).values, y.astype(float).values
        return pd.Series((a == b) | (np.isnan(a) & np.isnan(b)) | np.isclose(a, b, rtol=1e-12, atol=0.0), index=x.index)
    return x.astype(str) == y.astype(str)


def network_diff(a, b):
    """every difference between two networks: (component, field, kind, n, examples)"""
    rows = []
    fa = {k: v for k, v in a.meta.items() if k != 'baseline'}
    fb = {k: v for k, v in b.meta.items() if k != 'baseline'}
    if json.dumps(fa, sort_keys=True, default=str) != json.dumps(fb, sort_keys=True, default=str):
        rows.append(dict(component='meta', field='*', kind='meta', n=1, examples='meta differs beyond the baseline label'))
    for k in sorted(set(a.meta) ^ set(b.meta)):
        rows.append(dict(component='meta', field=k, kind='meta_label' if k == 'baseline' else 'meta', n=1,
                         examples=f'{k} only in {"v16" if k in a.meta else "v17l"}: {str(a.meta.get(k, b.meta.get(k)))[:120]}'))
    if not a.snapshots.equals(b.snapshots) or not a.snapshot_weightings.equals(b.snapshot_weightings):
        rows.append(dict(component='snapshots', field='*', kind='index', n=1, examples='snapshots / weightings differ'))
    for c in a.iterate_components():
        sa, sb = c.static, b.static(c.name)
        if not sa.index.equals(sb.index):
            rows.append(dict(component=c.name, field='index', kind='index', n=abs(len(sa) - len(sb)), examples=sorted(set(sa.index) ^ set(sb.index))[:4]))
            continue
        for col in sorted(set(sa.columns) | set(sb.columns)):
            if col not in sa or col not in sb:
                rows.append(dict(component=c.name, field=col, kind='column', n=len(sa), examples='missing in one network')); continue
            bad = ~same(sa[col], sb[col])
            if bad.any():
                rows.append(dict(component=c.name, field=col, kind='static', n=int(bad.sum()), examples=list(sa.index[bad][:6])))
        for k, df in c.dynamic.items():
            db = b.dynamic(c.name)[k]
            if df.empty and db.empty:
                continue
            if not df.columns.equals(db.columns) or not df.index.equals(db.index):
                rows.append(dict(component=c.name, field=k, kind='series_shape', n=1, examples=sorted(set(df.columns) ^ set(db.columns))[:4])); continue
            x, y = df.values.astype(float), db.values.astype(float)
            bad = ~((x == y) | (np.isnan(x) & np.isnan(y)))
            if bad.any():
                rows.append(dict(component=c.name, field=k, kind='series', n=int(bad.sum()), examples=list(df.columns[bad.any(axis=0)][:4])))
    return rows


def main():
    import pypsa
    reg = BR.load()
    e = reg['baselines'][reg['candidate']]
    seal = json.loads(SEAL.read_text(encoding='utf-8'))
    it2 = json.loads((SRC_DIR / 'LP1_LOSSY_IT2/LOSSY_LP1_QA.json').read_text(encoding='utf-8'))
    lp2 = json.loads((SRC_DIR / 'LP2_LOSSY_CANDIDATE/LOSS_BASIS_LP2_QA.json').read_text(encoding='utf-8'))
    dst = ROOT / e['path']
    src_sha = BR._sha_raw(SRC)
    pins = dict(source=src_sha, seal=seal['candidate_sha256'], it2_qa=it2.get('candidate_sha256'), registry=e['sha256'], registry_module=BR.BASE_TAMU_V17L_SHA256)
    if len(set(pins.values())) != 1:
        raise SystemExit(f'STOP: candidate SHA pins disagree {pins}')
    if Path(dst).resolve() != BR.BASE_TAMU_V17L.resolve() or (ROOT / e['source']).resolve() != SRC.resolve():
        raise SystemExit('STOP: registry path / source disagree with baseline_registry constants')
    if not (lp2.get('acceptance_pass') is True and it2.get('r_converged') is True and it2['guards']['all_pass'] is True
            and it2['convergence'].get('lines_at_trust_floor') == []):
        raise SystemExit('STOP: the v3 chain did not pass (IT2 converged + guards + no floor line + LP2 acceptance)')
    frozen_before = {k: BR._sha_raw(p) for k, p in FROZEN.items()}
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if BR._sha_raw(dst) != src_sha:
            raise SystemExit(f'STOP: {dst} exists with a different SHA - never overwritten')
        copied = False
    else:
        tmp = dst.with_suffix('.nc.tmp')
        shutil.copyfile(SRC, tmp)
        with open(tmp, 'rb+') as f:
            os.fsync(f.fileno())
        os.replace(tmp, dst)
        copied = True
    dst_sha = BR._sha_raw(dst)
    a = pypsa.Network(str(BP.BASE_TAMU_V16))
    b = pypsa.Network(str(dst))
    diff = network_diff(a, b)
    unexpected = [r for r in diff if (r['component'], r['field']) not in ALLOWED and r['kind'] != 'meta_label']
    L = a.lines.index
    ld = pd.DataFrame(dict(s_nom_v16=a.lines.s_nom, s_nom_v17l=b.lines.s_nom.reindex(L), r_v16=a.lines.r, r_v17l=b.lines.r.reindex(L),
                           x_v16=a.lines.x, x_v17l=b.lines.x.reindex(L)))
    ld['s_nom_delta_MVA'] = ld.s_nom_v17l - ld.s_nom_v16
    ld['r_ratio'] = ld.r_v17l / ld.r_v16
    ld = ld[(ld.s_nom_delta_MVA.abs() > 1e-9) | ((ld.r_ratio - 1).abs() > 1e-12)].sort_values('s_nom_delta_MVA', ascending=False)
    ld.to_csv(dst.parent / 'LINE_DIFF_VS_V16.csv', float_format='%.10g')
    tl = b.meta.get('solving', {}).get('options', {}).get('transmission_losses')
    frozen_after = {k: BR._sha_raw(p) for k, p in FROZEN.items()}
    checks = dict(sha_pins_agree=True, copy_sha_equals_source=dst_sha == src_sha, v3_chain_passed=True,
                  only_line_s_nom_and_r_differ=not unexpected, x_unchanged=bool((ld.x_v16 == ld.x_v17l).all()) and not any(r['field'] == 'x' for r in diff),
                  meta_transmission_losses_2=tl == 2 and int(e['meta_transmission_losses']) == 2 and int(e['calibration_transmission_losses']) == 2,
                  frozen_files_unchanged=frozen_before == frozen_after, registry_not_adopted_by_this_script=not BR.adopted(reg))
    rec = dict(step='NEXT-09 v1.7L lossy 2025 baseline freeze (no solver)', version='v1.7L', status='FROZEN_PREPARED (adoption: registry, researcher only)',
               path=e['path'], sha256=dst_sha, source=e['source'], source_sha256=src_sha, copied_now=copied, solved_code_sha=e['solved_code_sha'],
               seal=e['seal'], seal_sha256=BR._sha_raw(SEAL), approval_commit=seal['approval_commit'],
               loss_basis=dict(calibration_transmission_losses=2, meta_transmission_losses=tl),
               lp1_it2=dict(r_converged=it2['r_converged'], max_rel_r_gap=it2['convergence']['max_rel_r_gap'], lines_at_trust_floor=it2['convergence']['lines_at_trust_floor'],
                            guards={k: it2['guards'][k] for k in ('G1', 'G2', 'G3', 'total_uplift_MVA', 'G1_limit_MVA')}),
               lp2_acceptance={k: lp2['acceptance'][k] for k in ('eens_MWh', 'max_gap_MW', 'eens_pass', 'max_gap_pass', 'shed_buses', 'max_gap_step')},
               lp2_losses_TWh=lp2['losses']['total_loss_MWh'] / 1e6,
               diff_vs_v16=dict(rows=diff, lines_changed=int(len(ld)), s_nom_delta_sum_MVA=float(ld.s_nom_delta_MVA.sum()), line_table='LINE_DIFF_VS_V16.csv'),
               frozen_sha256=frozen_after, checks=checks, built_utc=datetime.now(timezone.utc).isoformat(timespec='seconds'))
    rec['verdict'] = 'FREEZE_PASS' if all(checks.values()) else 'FREEZE_FAIL'
    (dst.parent / 'BASELINE_V17L_RECORD.json').write_text(json.dumps(rec, indent=1, default=str), encoding='utf-8', newline='\n')
    print(json.dumps(dict(verdict=rec['verdict'], sha256=dst_sha, copied_now=copied, checks=checks, diff=diff), indent=1, default=str))
    if rec['verdict'] != 'FREEZE_PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
