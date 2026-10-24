"""NEXT-09 (2026-10-23): the formal 2025 baseline of the post-v1.6 S0-S3 line, read from config/config.byop_baseline_registry.yaml.

Every formal post-v1.6 entry (rearch_mech post_v16_guard / a3_guard, post_v16_a2_gate.check, post_v16_a3_gate.check) asks this
module which baseline is formal and refuses a run on any other file:
  * formal = the registry `candidate` (v1.7L, the NEXT-08b v3 lossy candidate, frozen byte for byte) only when the researcher has
    set adoption_status ADOPTED with adopted_by and adopted_git_sha (an ancestor of HEAD) in a config-only commit; otherwise the
    `previous_formal` entry (v1.6). An ADOPTED record with a missing field is a refusal, never a silent fallback to v1.6.
  * the config of the run must pin exactly the formal entry (path and SHA-256), --base must be that file and its bytes must hash
    to the pinned SHA.
  * loss basis: the baseline was calibrated with `calibration_transmission_losses` and the post-v1.6 solve uses the baseline
    meta value `meta_transmission_losses`; a formal S0-S3 run needs both equal (NEXT-07 W5: v1.6 is lossless-calibrated but the
    mainline solves lossy, so v1.6 fails this rule - by design).
The registry is pinned in the S0 / S1 / A3 manifests by normalised_sha() (the three adoption fields blanked), so adopting changes
no pinned hash; a change of any other registry field invalidates the manifests. Nothing here touches a solver.
"""
from __future__ import annotations

import hashlib, json, subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]            # pypsa-usa
WF = ROOT / 'workflow'
REGISTRY = WF / 'config/config.byop_baseline_registry.yaml'
REGISTRY_REL = 'workflow/config/config.byop_baseline_registry.yaml'
ADOPTION_FIELDS = ('adoption_status', 'adopted_git_sha', 'adopted_by')
# v1.7L lossy 2025 baseline = byte copy of the NEXT-08b LP1 v3 candidate (byop/build/freeze_baseline_v17l.py); kept here, not in
# byop_paths.py, so the closed A1 manifest (which pins byop_paths.py) stays current
BASE_TAMU_V17L_DIR = WF / 'results/BYOP/baseline_2025_tamu_v17_lossy'
BASE_TAMU_V17L = BASE_TAMU_V17L_DIR / 'baseline_2025_tamu_v17_lossy_prepared.nc'
BASE_TAMU_V17L_SHA256 = 'f9aa87aea496f7c07ea4aca0439a703e7eaa90d08cb66c5bc6f149ea60eeefb6'   # NEXT-08b v3 seal (LOSSY_LP1_V3_SEAL.json)


def _git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True)


def _sha_raw(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _sha_lf(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def load(path=REGISTRY):
    return yaml.safe_load(Path(path).read_text(encoding='utf-8'))['baseline_registry']


def normalised_sha(path=REGISTRY):
    """SHA-256 of the registry with the three adoption fields blanked (adopting does not change the pinned hash)"""
    d = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    for k in ADOPTION_FIELDS:
        d['baseline_registry']['adoption'][k] = None
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


def adopted(reg):
    return str((reg.get('adoption') or {}).get('adoption_status')) == 'ADOPTED'


def adoption_problems(reg, root=ROOT, git_fn=_git):
    """reasons an ADOPTED record is not valid (empty when NOT_ADOPTED: nothing to check)"""
    a = reg.get('adoption') or {}
    if not adopted(reg):
        return []
    bad = []
    if not a.get('adopted_by'):
        bad.append('baseline adoption: adopted_by missing')
    sha = str(a.get('adopted_git_sha') or '')
    if len(sha) < 8:
        bad.append('baseline adoption: adopted_git_sha missing or too short')
    elif git_fn('merge-base', '--is-ancestor', sha, 'HEAD').returncode != 0:
        bad.append(f'baseline adoption: adopted_git_sha {sha} is not HEAD or an ancestor of it')
    src = root / str(reg.get('authorization_source') or '')
    if not src.is_file() or _sha_lf(src) != reg.get('authorization_source_sha256'):
        bad.append('baseline adoption: authorization source missing or changed')
    cand = reg['baselines'][reg['candidate']]
    rec = root / str(cand.get('record') or '')
    if not rec.is_file():
        bad.append(f"baseline adoption: freeze record missing ({cand.get('record')})")
    return bad


def formal(reg=None, root=ROOT, git_fn=_git):
    """(id, entry, problems): the formal baseline; problems non-empty means no formal baseline (fail closed)"""
    reg = load() if reg is None else reg
    if adopted(reg):
        bad = adoption_problems(reg, root, git_fn)
        k = reg['candidate']
        return (None if bad else k), (None if bad else reg['baselines'][k]), bad
    k = reg['previous_formal']
    return k, reg['baselines'][k], []


def baseline_problems(cfg_baseline, base_path, reg=None, root=ROOT, git_fn=_git, loss_basis=True):
    """reasons a run that pins cfg_baseline ({path, sha256}) with --base base_path is not on the formal baseline"""
    reg = load() if reg is None else reg
    k, e, bad = formal(reg, root, git_fn)
    if bad:
        return bad
    out = []
    pinned = dict(path=str((cfg_baseline or {}).get('path')), sha256=str((cfg_baseline or {}).get('sha256')))
    if pinned != dict(path=e['path'], sha256=e['sha256']):
        others = [x for x, v in reg['baselines'].items() if dict(path=v['path'], sha256=v['sha256']) == pinned]
        why = (f'{others[0]} is not the formal baseline' + (' (not ADOPTED)' if others[0] == reg['candidate'] else ' (superseded)')) if others \
            else 'unregistered baseline'
        out.append(f"config baseline {pinned['path']} is not the formal 2025 baseline {k} ({e['path']}): {why}")
    want = (root / e['path']).resolve()
    if not base_path:
        out.append('no --base given (no fallback)')
    elif Path(base_path).resolve() != want:
        out.append(f'--base {base_path} is not the formal 2025 baseline {k} ({e["path"]})')
    elif not want.is_file():
        out.append(f'formal baseline {k} missing on this machine: {e["path"]}')
    elif _sha_raw(want) != e['sha256']:
        out.append(f'formal baseline {k} SHA differs from the registry')
    if loss_basis and int(e['calibration_transmission_losses']) != int(e['meta_transmission_losses']):
        out.append(f"loss-basis mismatch on {k}: calibrated with transmission_losses {e['calibration_transmission_losses']}, solved with "
                   f"{e['meta_transmission_losses']} (NEXT-07 W5) - not a formal S0-S3 baseline")
    return out


def meta_loss_problems(meta, reg=None, root=ROOT, git_fn=_git):
    """the solve config read from the baseline meta must carry the registry's meta_transmission_losses"""
    k, e, bad = formal(load() if reg is None else reg, root, git_fn)
    if bad:
        return bad
    got = ((meta or {}).get('solving') or {}).get('options', {}).get('transmission_losses')
    return [] if got is not None and int(got) == int(e['meta_transmission_losses']) else \
        [f"baseline meta transmission_losses {got} != registry {e['meta_transmission_losses']} ({k})"]


def summary(reg=None, root=ROOT, git_fn=_git):
    reg = load() if reg is None else reg
    k, e, bad = formal(reg, root, git_fn)
    return dict(formal=k, formal_path=(e or {}).get('path'), formal_sha256=(e or {}).get('sha256'), adoption=reg.get('adoption'),
                adoption_problems=bad, registry_normalised_sha256=normalised_sha())
