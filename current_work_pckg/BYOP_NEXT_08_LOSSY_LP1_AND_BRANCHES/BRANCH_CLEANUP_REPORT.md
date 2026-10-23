# BRANCH_CLEANUP_REPORT (NEXT-08 B), 2026-10-23 (New York)

**Result: GitHub `simonyed/BYOP` now has exactly one branch, `main`.** Every retired branch head is preserved as an `archive/branch-*` tag. Solved-code milestones are tagged `byop/*`.

Three local or L2 branch references remain. They are checked out in git worktrees, and removing those worktrees was **refused by the executor's permission classifier** (irreversible local deletion). They are kept until you decide (§5). No commit, result, ledger, approval SHA or input file was deleted or changed.

Full listings: `BRANCHES_BEFORE.txt`, `BRANCHES_AFTER.txt`.

## 1. Checks performed (before any deletion)

| Check | Result |
|---|---|
| `git fetch --all --prune`; HEADs and ancestry | Every BYOP branch (GitHub and local) is an **ancestor of `byop/main`** with **0 commits not in main**: `mainline-v13-stageA` (= main), `work/a2-postv16-static` (−67), `work/next07-a3-static` (GitHub `79134c9f`, local `caa428ab`), local `integrate/next05` `8e4ad312`, local `byop` `be2c6904` (−118) |
| Worktrees | **Local:** `.worktrees/a2` (work/a2-postv16-static; only ignored `__pycache__`), `.worktrees/merge` (integrate/next05; clean). **L2:** `.worktrees/a2` (work/a2-postv16-static), 64 untracked + 71 ignored files; byte-compared with the main L2 checkout (below). |
| L2 worktree content | Every untracked or ignored file has an identical copy in the main L2 checkout, except 4 five-byte `.done` markers (copied to `workflow/results/BYOP/post_v16_a2_static/`, `cp -n`, verified) and 1 symlink. **Nothing unique would be lost.** |
| Running tasks | None on L2 (no `rearch_mech` / `loss_basis` / `baseline_v16` / pytest processes; load ~2) |
| Uncommitted changes | None in any worktree |
| PRs | 0 open PRs (`api.github.com/repos/simonyed/BYOP/pulls?state=open`) |
| Default branch / protection | default `main`; no branch protected |
| Automation | `work_pkgs/_tools/sync_pypsa_usa.sh` pushes the *current* branch (`byop` → GitHub `main`); nothing hard-codes the retired names. `workflow/byop/inputs/calibration_v16/DECISION_POLICY.yaml` contains `branch: mainline-v13-stageA` as a verbatim historical record of the v1.6 package. It is read by no code and pinned in existing manifests, so it is **left unchanged**. |
| Research content merged | Ancestry proves every commit of every retired branch is in `main` (no cherry-pick needed) |

## 2. Tags created (annotated, pushed to GitHub; verified ancestors of main)

| Tag | Commit | Meaning |
|---|---|---|
| `byop/a1-rerun1-solved-code` | `07c881a4` | A1 rerun1 solved code |
| `byop/a2-s0s1-solved-code` | `cdfdea06` | formal S0 + S1_EARLIEST solved code |
| `byop/next07-reserve-probe-solved-code` | `5df4dda7` | NEXT-07 W2 |
| `byop/next07-lossless-probe-solved-code` | `bf61d873` | NEXT-07 W5P |
| `byop/next07-lossy-lp2-solved-code` | `c93cca5d` | NEXT-07 W6 |
| `byop/next07-end` | `327b46ea` | main before NEXT-08 |
| `archive/branch-mainline-v13-stageA` | `327b46ea` | retired head |
| `archive/branch-work-a2-postv16-static` | `39a74ff5` | retired head |
| `archive/branch-work-next07-a3-static` | `79134c9f` | retired head (GitHub) |
| `archive/branch-work-next07-a3-static-local` | `caa428ab` | retired head (local) |
| `archive/branch-integrate-next05` | `8e4ad312` | local branch head (kept, §5) |

The upstream PyPSA-USA `v0.x` tags were **not** pushed to BYOP.

## 3. Actions taken

1. **Local working branch.** Moved to `byop`, fast-forwarded from `be2c6904` to `327b46ea` (`git update-ref` with old-value check, then `git switch`; same commit, no working-file change).
2. **Sync tool fix.** It read the branch with `git rev-parse --abbrev-ref HEAD`, which returns `heads/byop` because the branch and the remote share the name `byop`. That would have pushed to a GitHub branch literally named `heads/byop`. It now uses `git symbolic-ref HEAD`.
3. **First sync on the new layout:** local `byop` = GitHub `main` = L2 HEAD `525d3539`. L2 moved to branch `byop` without touching its working files.
4. **GitHub branches deleted:** `git push byop --delete mainline-v13-stageA work/a2-postv16-static work/next07-a3-static`, after the tags existed on GitHub.
5. **Local branches deleted** with `git branch -d` (refuses unmerged): `mainline-v13-stageA`, `work/next07-a3-static`. **L2:** `mainline-v13-stageA`.
6. **Branch policy rewritten.** `pypsa-usa/CLAUDE.md` (the old "work against `origin/develop`" upstream text) now says: `origin/main` of simonyed/BYOP is the only baseline; `work/<task>` branches come from `main`, merge back, then are deleted; milestones are tags; never rewrite approved SHAs. The local `D:\BYOP_impact\CLAUDE.md` §2 was updated the same way (local only; it holds credentials).

**Not used:** `git reset --hard`, `git clean`, any force push or history rewrite.

## 4. State after cleanup

| Where | Branches |
|---|---|
| GitHub | `main` only (`525d3539` at cleanup time; later commits of this package on top) |
| Local | `byop` (tracks `byop/main`), `master` (tracks the upstream `origin/master`; PyPSA-USA reference, never pushed to BYOP), `integrate/next05`, `work/a2-postv16-static` (both checked out in worktrees) |
| L2 | `byop` (HEAD), `master`, `work/a2-postv16-static` (checked out in the L2 worktree) |

## 5. Kept, and why: one decision needed from you

| Item | Why kept | Safe removal (when you allow it) |
|---|---|---|
| local `.worktrees/a2` + branch `work/a2-postv16-static` | worktree removal refused by the permission classifier | `git worktree remove .worktrees/a2` (only ignored `__pycache__` inside), then `git branch -d work/a2-postv16-static` |
| local `.worktrees/merge` + branch `integrate/next05` | same | `git worktree remove .worktrees/merge` (clean), then `git branch -d integrate/next05` |
| L2 `.worktrees/a2` + branch `work/a2-postv16-static` | same; 418 MB of files duplicated in the main checkout | move the directory to `/datasets/prgm/BYOP_impact/_archive_20261020/worktree_a2_20261023` (non-destructive), `git worktree prune`, `git branch -d work/a2-postv16-static` |

None of these blocks task A; all their commits are in `main` and tagged.
