# Build v2 — Prompt 9: publish, back up, verify, close out

## Goals

Publish the v2 database and tables, back everything up off-site, verify the
run end to end (including that v1 is byte-identical to its frozen state),
update the documentation, and write the 2.0 run report
(`run_full_inelastic.md` Plan §5 step 10; R8).

## Claude

### Skills

- None specific.

### Working agreements

As in `build_v2_prompt_1.md`. Every publish/backup step is confirmed with
the user; `rclone copy` (never `sync`); dated backup names; check the
published object **before** pushing (the two-machines/one-key lesson,
`HOWTO.md` §7b).

## Context

- Plan §1 (S3/backup layout), §5 step 10 of `claude_prompts/v2/run_full_inelastic.md`.
- `HOWTO.md` §7 (publishing; `NautilusS3Backend`; the merged-DB lesson),
  `docs/design/PAB_implementation.md` (§10/§11 as the model for a new §12),
  `docs/design/PAB_full_run_report.md` (the model for the v2 run report),
  `docs/design/PAB_design.md` (*Provenance & versioning* — add the two-DB
  convention and the "end = today" backfill rule, R5), `docs/db_schema.rst`
  (v5), `ToDo.md`.
- RTD: the `pab-report` project builds `develop`/`latest(main)`; JXP will
  merge `full-inelastic` → `develop` at close-out (R8). Verify
  `/en/develop/` afterwards.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below

## Tasks

1. **Publish + back up.** (a) `v2/pab.db` → `s3://pab/v2/pab.db` and the
   `report` stage's `matchup_summary.{csv,parquet}` → `s3://pab/v2/`
   (`NautilusS3Backend`; re-download + sha256 at the public URL); (b)
   `rclone copy` → `AIOcean:PAB/pab_v2_<date>.db` (+ the v2 chains and
   figures if not already done in Prompt 7, and the v2 `site/`); (c) tell
   the user `report_site/` + the `pab/` changes are ready to commit/push;
   after the `develop` merge, verify the live RTD page shows the 2.0
   headline and the 1.0-vs-2.0 section. Log what went where, with sizes and
   hashes.

2. **Verify.** v1: `v1/pab.db` sha256 == the frozen value (workstation and
   S3 `v1/`). v2: `PRAGMA integrity_check`, `foreign_key_check`; every BING
   `fits` row `pab_version='2.0'` with `rt_backend='robust_hybrid'`,
   `include_raman=1`, `include_chl_fl=1`, `include_cdom_fl=0`, `fit_bp=1`,
   `wave_max=720`; every pixel has geometry; NASA rows = 14,609 + the new
   ones; no duplicate `fit_id`; 11 quantities per BING fit (`…_Bp` added);
   spot-check 4 matchups end to end (chains → figure → page). Report the
   headline science numbers: sat-vs-float `bbp700` and Chl (2.0), 1.0-vs-2.0
   ratios, NASA-vs-2.0. Log.

3. **Docs + report.** `PAB_implementation.md` → new §12 (2.0 run: what
   changed, schema v5, the `geometry` stage, the two-DB layout, fixes made
   along the way); `HOWTO.md` (2.0 defaults, `geometry` stage, `v1/v2`
   paths on workstation/PVC/S3, `--compare-db`); `PAB_design.md`
   (provenance: separate DBs per major version, "end = today" backfill
   rule); `db_schema.rst` (v5); `ToDo.md`. Write
   `docs/design/PAB_v2_run_report.md` (counts, timings per stage, failure
   tails, the slice gate results, the 1.0-vs-2.0 attribution, follow-ups:
   bulk-artifact publish, Zenodo, gap C, CDOM fluorescence). Log.

## Q&A

### Q1 (Task 1) — confirm the publish + backup plan

Everything below is staged and hashed but **nothing has been sent**. The
working agreement requires each publish/backup step be confirmed.

**(a) S3 → `s3://pab/v2/`** (226 MB, from the workstation). `s3://pab/v2/` is
currently **empty**; `s3://pab/v1/pab.db` exists and is byte-identical to the
frozen workstation copy (`09de0a6d…f978273` — Task 2's check already passes on
the workstation side).

| object | bytes | sha256 |
|---|---|---|
| `v2/pab.db` | 217,325,568 | `7d44e1f3c5a3385ca64af893b0b88661962a7910a8064abb7a297afc0b78bdaf` |
| `v2/matchup_summary.csv` | 6,102,869 | `6622a78cf3061a17bfafa908443c60c428512168ab235eb474e3ad26070f0f74` |
| `v2/matchup_summary.parquet` | 2,645,441 | `4754e2372f4d35918c7f060ea4287f44a89329a01045d24f2f2e6b5fe9c0627c` |

The tables were regenerated on the workstation from the authoritative
`v2/pab.db` (15,971 rows, `pab_version` all `2.0` — the version filter added
in Prompt 8 Task 1 is doing its job here). I will re-download each from the
public URL and re-check sha256 after upload, and check the existing object
before overwriting (the two-machines/one-key lesson).

**Which credential should the S3 push use?** `HOWTO.md` §7b says "the standard
boto3 chain". `~/.aws/credentials` has `default`, `mskelm`, `benpritikin`,
`ceph-s3-large-files`, `swot-user` — none named for `pab`, and I will not
guess which has write access to the public bucket. The `rclone` remote
`nautilus_s3` **does** have working Ceph credentials configured. Options:

- **(i)** `rclone copyto` via the `nautilus_s3` remote (credentials already
  known-good; bypasses `NautilusS3Backend`);
- **(ii)** `NautilusS3Backend` with a named profile — tell me which;
- **(iii)** `NautilusS3Backend` with `AWS_ACCESS_KEY_ID`/`SECRET` exported by
  you into the session.

I'd suggest **(ii) or (iii)**, so the documented code path is the one that
actually publishes — but I need the profile name.


**(b) Off-site backup → `AIOcean:PAB/`** (a Google shared drive, not S3).
`AIOcean:PAB/` currently holds only the v1-era `fit_chains/` and `site/`; there
is **no `v2/` prefix**, so the Prompt 7 optional chains backup was never run.

| item | size | source | how |
|---|---|---|---|
| `pab_v2_2026-10-07.db` | 217 MB | workstation | `rclone copyto`, direct |
| `v2/site/` | 1.1 MB | workstation | `rclone copy`, direct |
| `v2/fit_chains/` | ~18 GB | **PVC only** | needs an in-cluster job |
| `v2/figures/` | ~1 GB (17,361 files) | **PVC only** | needs an in-cluster job |

The chains and figures exist **only on the Nautilus PVC** (the workstation
`fit_chains/` is empty), and PVCs are not backed up — so this is the step that
actually protects 35 h of compute. It needs the 1.0 pattern: a temporary
AIOcean-only secret in the cluster, a `rclone copy` job, secret deleted after.
That means putting a Google Drive credential into the cluster, so I want it
confirmed explicitly and separately from (a).

**Answer (a):** (ii) with `default`

**Answer (b):** Yes it is ok to add the Google Drive credential to the cluster, it is a temporary secret.

### Q2 (Task 2) — `wave_max` is 700, not 720

Task 2's gate list says every BING fit should have `wave_max=720`. The actual
run has **`wave_max=700.0`** on all 15,971 2.0 fits — and v1 is also 400–700,
so the window never changed between versions. This is the same discrepancy
found in Prompt 8 Task 2 (the brief's "720 nm" item), and it is the *run* that
is right: Prompt 3 found Rrs(719) negative or noise-dominated on 44 % of a
diagnostic sample, so the red edge was deliberately excluded.

Unless you say otherwise I will verify `wave_max=700.0` and record the
deviation from the brief rather than failing the gate.

**Answer:** Ok, verify `wave_max=700.0` and record the deviation from the brief rather than failing the gate.

### Q3 (Task 2) — repair the 14,586 dangling `scene_path` values?

Task 2's spot-check turned up that **14,586 of 15,976 `matchups.scene_path`
values point at `/data/full/pipeline/figures/`**, a PVC directory that no
longer exists — it was renamed `full` → `v1` during the version split and the
column was never updated. `chains_path` and `figure_path` are fine.

The files are intact at `/data/v1/pipeline/figures/`. I checked **all 14,586**
remapped paths in-pod: **0 missing**. The repair is one statement:

```sql
UPDATE matchups
   SET scene_path = replace(scene_path, '/data/full/', '/data/v1/')
 WHERE scene_path LIKE '/data/full/%';
```

I have **not** run it. It mutates the database Task 1 is about to publish, and
I would rather publish a correct one than fix it afterwards.

- **(a)** Repair now, re-verify, then publish the corrected DB in Task 1.
  (Recommended — the hashes in Q1 would change, and I would recompute them.)
- **(b)** Publish as-is and repair later.
- **(c)** Leave it: the paths describe where the v1 run wrote them, and the
  v1 PVC layout is itself historical.

I'd go with **(a)**. The column is provenance for a published dataset; 91 % of
it currently points at nothing, and it fails silently everywhere it is used.

**Answer:** (a)

## Reports

### Task 1 — publish + back up

Executed after the Q3 repair, so what is published is the **corrected**
database. Running order was deliberately repair → re-verify → publish.

**(a) Published to `s3://pab/v2/`** via `NautilusS3Backend(prefix="v2",
profile_name="default")` — the documented code path, per Q1(a). `s3://pab/v2/`
was confirmed **empty** immediately before pushing (the two-machines /
last-writer-wins lesson), so nothing was overwritten.

| object | bytes | sha256 | upload |
|---|---|---|---|
| `v2/pab.db` | 217,325,568 | `1e69f6eef09b85add89b04ac45d423d9d981fbd81b097d0856dab59687d8a3f8` | 3.4 s |
| `v2/matchup_summary.csv` | 6,102,869 | `6622a78cf3061a17bfafa908443c60c428512168ab235eb474e3ad26070f0f74` | 0.3 s |
| `v2/matchup_summary.parquet` | 2,645,441 | `4754e2372f4d35918c7f060ea4287f44a89329a01045d24f2f2e6b5fe9c0627c` | 0.3 s |

**Verified at the public URL**, not from a listing: each object re-downloaded
over plain HTTPS with no credentials — **HTTP 200 and sha256 identical** for
all three.

The DB hash differs from the one quoted in Q1 (`7d44e1f3…`) because that was
the pre-repair database. The summary tables are **byte-identical** before and
after the repair — `gather_matchups` does not select `scene_path` — which I
confirmed by regenerating and comparing rather than assuming.

**(b) Off-site backup → `AIOcean:PAB/`** (Google shared drive). `rclone copy`
throughout, never `sync`: the destination holds the 1.0 backups and `sync`
would delete whatever is not in the source.

From the workstation, complete:

| item | size | destination |
|---|---|---|
| v2 database | 217,325,568 | `AIOcean:PAB/pab_v2_2026-10-07.db` |
| reporting site | 1.1 MB | `AIOcean:PAB/v2/site/` (incl. the 4 new 2.0 figures) |

From the PVC, running as `nautilus/v2_backup_job.yaml` (new):

| item | size | files |
|---|---|---|
| `v2/fit_chains/` | **18.3 GB** | 15,971 |
| `v2/figures/` | 1,022 MB | 17,361 |

These exist **only** on the PVC — the workstation `fit_chains/` is empty and
Nautilus PVCs are not backed up, so until this job finishes 35 h of compute
has exactly one copy. The job's first act is to list the destination and print
it, so the 1.0 artifacts are visibly untouched; it finishes with a count
comparison and an `rclone check`.

**Credential handling.** The in-cluster secret `aiocean-rclone` carries an
**AIOcean-only** rclone config — the workstation's other three remotes
(`GDrive:`, `RoB:`, `nautilus_s3:`) are deliberately excluded rather than
shipping the whole config. It is temporary and is deleted as soon as the job
reports Completed.

**(c) Ready for JXP.** `report_site/` and the `pab/` changes are ready to
commit and push; after the `full-inelastic` → `develop` merge the live RTD
page needs checking for the 2.0 headline and the 1.0-vs-2.0 section. Note
GitHub had a **major Git Operations outage** on 2026-10-07 15:14 UTC which
rejected a push with an opaque `Internal Server Error`; unrelated to this work.


### Task 2 — verify

**Everything passes except one finding, which is real and fixable — see below.**

**v1 is byte-identical to its frozen state, across three independent copies:**

```
HOWTO frozen value     09de0a6d334dc02e73494b198567a37707e1942e5cfd1173c89822b35f978273
workstation v1         09de0a6d334dc02e73494b198567a37707e1942e5cfd1173c89822b35f978273
S3 v1/pab.db           09de0a6d334dc02e73494b198567a37707e1942e5cfd1173c89822b35f978273
```

169,938,944 bytes, `-r--r--r--`. The S3 copy was downloaded from the public
URL and hashed, not trusted from a listing.

**v2 gates — all pass:**

| gate | result |
|---|---|
| `PRAGMA integrity_check` | ok |
| `PRAGMA foreign_key_check` | 0 violations |
| `PRAGMA user_version` | 5 |
| all 15,971 BING fits `pab_version='2.0'` | pass |
| `rt_backend='robust_hybrid'` | pass |
| `include_raman=1`, `include_chl_fl=1`, `include_cdom_fl=0`, `fit_bp=1` | pass |
| `wave_min=400.0`, **`wave_max=700.0`** | pass (see Q2 — the brief said 720) |
| no BING fit on a pixel without geometry (R3) | pass |
| NASA rows | 15,976 = 14,609 + **1,367** new, all stamped `1.1` (R6) |
| no duplicate `fit_id` | pass |
| 11 quantities on **every** BING fit | pass (one distinct count: 11) |
| `BING_ExpBPow_Bp` present | pass (new in 2.0) |
| every BING fit has `chains_path` + `figure_path` | pass |
| every matchup has `scene_path` | pass |
| no NASA row has a figure | pass |

**The geometry gate as written in the brief does not hold, and should not.**
50 of 159,760 pixels have no `theta_s`/`theta_v`/`dphi`. They are not scattered:
they are **all 10 pixels of exactly 5 matchups**, and none of those 5 was
fitted. That is R3 working — a matchup with no L1B geometry is refused rather
than silently defaulted. The invariant worth asserting is the arithmetic:
**15,971 fits + 5 refused = 15,976 matchups**, which closes exactly. The gate
was rewritten to check that, plus that the gap is never *partial* within a
matchup (0 such).

**Spot-check, 4 matchups end to end.** All four: chains recorded, figure
recorded, scene recorded, 11 quantities, present in the published summary
table — **and the files verified to exist on the PVC**, which is what turned
up the finding below.

### Finding: 14,586 `scene_path` values are dangling pointers

Checking files rather than columns showed all four spot-checked scenes
pointing at `/data/full/pipeline/figures/…`, which **no longer exists**. The
PVC directory was renamed `full` → `v1` during the version split and the
`matchups.scene_path` column was never updated.

| `scene_path` prefix | count | resolves? |
|---|---|---|
| `/data/full/` (the v1 run) | **14,586** | **no — path renamed** |
| `/data/v2/` (this run) | 1,390 | yes |

`chains_path` and `figure_path` are unaffected — all 15,971 of each point at
`/data/v2/` and resolve.

**The files are not lost.** They are at `/data/v1/pipeline/figures/` (29,195
files). I checked **all 14,586** remapped paths in-pod: **0 missing**. The fix
is one unambiguous substitution, `/data/full/` → `/data/v1/`.

Nothing is visibly broken today — the scene gallery is suppressed at this
scale, and `_stage_static` tests `is_file()` and skips silently. That is
precisely why it survived: a 91 %-dangling column that degrades quietly. It
would surface the moment anyone renders the site at small N, publishes bulk
artifacts, or follows the provenance.

**Not fixed yet — it mutates the database that Task 1 is about to publish, so
it wants a word from JXP first (Q3).**

### Headline science numbers (2.0)

```
sat vs float                        n       ratio     rho   log bias    RMS
  bbp700  BING(2.0) / Argo       15274      1.148   0.415    +0.0103   0.645
  chl     BING(2.0) / Argo       15154      0.943   0.733    -0.0917   0.587
1.0 vs 2.0 (same matchup, same pixel)
  bbp700  2.0 / 1.0              14604      0.750   0.924    -0.1565   0.536
  chl     2.0 / 1.0              14604      1.165   0.704    +0.1912   0.644
NASA vs 2.0
  NASA bbp(442) / BING(700)      15964      2.154   0.874    +0.3594   0.648
```

NASA 442 nm vs BING 700 nm — the wavelengths differ by design; a ratio above 1
is expected from the blue-to-red decrease of particulate backscatter.

The result that matters, from Prompt 8 Task 4: against the floats 2.0 cuts the
``b_bp`` log bias from +0.169 to +0.010 and improves Chl on every axis, and the
apparent doubling of ``b_bp`` scatter is almost entirely the ultra-oligotrophic
tail (at Chl > 0.05 it is 0.337 → 0.383).

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
