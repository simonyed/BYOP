# A2_EOL_SHA_PORTABILITY_REPORT (NEXT-02 A2-FIX-06)

## 1. Root cause

- The repository stores text with LF.
- The Windows main checkout (`core.autocrlf=true`) has CRLF bytes, and so does the L2 main checkout, which is filled by the byte-copying sync tool.
- The A1 manifest (`POST_V16_A1_PRE_RUN_MANIFEST.json`) and `STAGING_SHA_QA.json` pin the **raw CRLF bytes**.
- A fresh `git worktree` / clone on L2 (`core.autocrlf=input`) gets LF bytes. Same content, different raw SHA.
- Hence NEXT-01's **202 passed / 2 failed** on the A2 branch:
  - `test_post_v16_a0.py::test_staging_sha_qa_pass`
  - `test_post_v16_a0.py::test_manifest_is_current`

### 1b. A second cause, found in NEXT-02: a corrupt binary in the repository

**The "EOL artefact" in `test_staging_sha_qa_pass` was not EOL only.**

- The root `.gitattributes` rule `workflow/byop/** text eol=lf` forces **text** conversion on binaries too.
- The staged `workflow/byop/inputs/post_v16/derived/ERCOT_OPERATIONAL_WIND_SOLAR_2023_2025.csv.gz` was therefore committed (since `453e846f`) with its CRLF byte pairs collapsed:
  - committed blob SHA `5cf7251e…`, `gzip -t` → **CRC error**;
  - correct bytes `66069818…` (pinned) are present in the local and L2 **main** checkouts;
  - the GitHub mirror, any fresh clone and the A2 worktree held the corrupt blob.
- It is the only tracked binary under the forced-text paths (`git ls-files --eol`).
- A1 does not read this file: it is not in the A1 manifest, and A1 uses `derived/ERCOT_2025_OBSERVED_LOAD_WIND_SOLAR_1H.csv`.
- The A1 gate's dirty check (`git diff --ignore-cr-at-eol`) does not flag it on the main checkouts.

**Fixed on the A2 branch (`33f158d5`):**
- `.gitattributes` binary exemption (`*.gz *.zip *.xlsx *.png *.pdf *.parquet *.nc -text`; later rules win);
- the correct bytes re-committed: blob `66069818…`, `gzip -t` OK on L2.

**On `mainline-v13-stageA` the corrupt blob stays until A1 is frozen.** Re-committing it there would change a gated input path after `802c9d94` and void the A1 approvability. The fix reaches the mainline when the audited A2 commits are merged after A1.

## 2. What changed (A2 branch only; A1 checkout, A1 gate and A1 manifest untouched)

| Layer | Treatment | Evidence level |
|---|---|---|
| Raw data that must not change (`.nc`, staged raw registry, baseline) | **Raw-byte SHA only**, unchanged | Byte identity |
| Versioned text pinned by the A1 manifest / staging QA (tests) | `pinned_text_ok`: the pinned SHA must equal the raw, LF-normalised or CRLF-encoded SHA, **and** the file must contain no lone CR | Content identity (LF↔CRLF is a bijection for files without lone CR, so any content change still fails) |
| New A2 manifest (`A2_PRE_RUN_MANIFEST.json`) | Each file is pinned with three layers (`raw`, `lf`, `crlf`) plus a `text` flag. Text must match the **LF** SHA, and its raw bytes must be one of the two pinned encodings. Binary or untracked data must match **raw** only (`post_v16_a2_gate.manifest_mismatches`). | Both layers recorded explicitly |
| A2 gate authorisation source (NEXT-02 package text) | Pinned on its LF content SHA `a6baf464…` | Content identity |

Not done:
- **No "skip SHA" fallback.** No exception is caught and ignored.
- **No text renormalisation.** The only `.gitattributes` change is the binary exemption (§1b) on the A2 branch. The mainline `.gitattributes` and the A1 main checkout are untouched until A1 is frozen.
- **The A1 gate (`post_v16_gate.check`) still compares raw bytes.** So A1 can only pass from the CRLF main checkout, which the read-only recheck confirmed. Making A1 itself EOL-portable means editing gated A1 code. That is decision **D3** and is scheduled for after A1 is frozen.

## 3. Tests

- `test_next02_a2_static.py::test_manifest_text_files_are_eol_portable_but_content_strict`:
  - CRLF pinned / LF checkout → accepted;
  - content change → refused;
  - a binary flag with an EOL change → refused.
- The two formerly failing A0 tests now use `pinned_text_ok`.
- Full branch regression and the fresh-checkout run: see `A2_REGRESSION_SUMMARY.json`.

## 4. Proposed post-A1 step (needs your D3 decision)

1. Add `.gitattributes` with `* text=auto eol=lf` for `workflow/byop/**` and `workflow/config/byop_*`.
2. Renormalise once.
3. Rebuild the A1 manifest with LF + raw layers in a versioned manifest v2.
4. Give `post_v16_gate` the same three-layer check.

The CRLF raw SHA history stays in the old manifests as evidence.
