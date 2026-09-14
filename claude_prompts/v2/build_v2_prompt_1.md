# Build v2 — Prompt 1: freeze v1, build the v2 database, set up the environment

## Goals

Make the v1.0 production database **untouchable** before any v2 code exists,
create the **v2 database** it will be built from, and stand up the `ocean14`
environment with the full stack. This is the first step of the run because
it is the one that protects the published 1.0 results from everything after
(`run_full_inelastic.md` Plan §1, §5 step 1; R1/R9).

## Claude

### Skills

- **`batch-fit-argo`**, **`run-bing-fit`** — not needed here; listed for
  continuity with the series.

### Working agreements (the whole series)

- **Git is handled by the user.** No `add`/`commit`/`push`/branch/merge.
  Read-only inspection is fine.
- **Python only**, in the **`ocean14`** conda env (install what you need
  there — Q9).
- **Reuse, don't reinvent.** Drive the `pab` CLI / stage functions.
- **Explicit `--db` everywhere.** `$PAB_DATA_DIR=/mnt/tank/Oceanography/data/Color/PAB`;
  never let a default resolve a DB path (lesson #1).
- **`v1/pab.db` is frozen from this prompt onward.** No stage, script or
  test writes to it. Its sha256 (`09de0a6d…f978273`, 169,938,944 B) is the
  invariant checked at close-out.
- **Outward-facing actions** (S3 writes, Nautilus jobs, deletes/renames of
  production data) are confirmed with the user first.
- **Log your work** in this doc's Logs section. **Use Fable if you can.**

## Context

- The plan: `claude_prompts/v2/run_full_inelastic.md` — **Plan §0 (locked
  decisions), §1 (two databases), §3 h/j (split helper, env)**.
- `HOWTO.md` §7b (what is published where), `docs/db_schema.rst` (schema v4).
- `pab/db/schema.py`, `pab/db/store.py` (the access layer the helper must use).
- The DB today: `$PAB_DATA_DIR/full/pab.db` = `s3://pab/full/pab.db`
  (schema v4; 881 floats / 54,031 profiles / 67,435 granules / 14,610
  matchups / 146,100 pixels; `fits` = 14,609 BING `1.0` + 14,609 NASA-GIOP
  `1.1`; 262,962 `fit_results`). Sibling files in `full/`:
  `pab_merged_nasa_giop_2026-09-10.db`, `pab_pre_cdom_merge_2026-09-10.db`,
  two NASA-GIOP logs.

## Prompts

1. Execute the 1st task in Tasks below. Use Opus 5
2. Execute the 2nd task in Tasks below. Use Opus 5
3. Execute the 3rd task in Tasks below. Use Opus 5
4. Execute the 4th task in Tasks below. Use Opus 5
5. Execute the 5th task in Tasks below. Use Opus 5

## Tasks

1. **Environment.** In `ocean14`: `pip install -e` PAB (`--no-deps`, then
   the missing deps), `argopy==1.4.0`, `erddapy==3.2.1`; confirm `robust`,
   `jax`, `bing`, `ocpy`, `remote_sensing`, `earthaccess`, `healpy`, `bokeh`
   import; run `pytest pab/tests` and report the pass/skip/fail counts
   against the last recorded `os_313` baseline (213 passed + 2 jax-env
   failures). If `argopy` will not install on Python 3.14, stop and say so
   in Q&A (fallback: `os_313` + `retrieve-or-bust` + `jax`). Record the
   final `package_versions()` snapshot. Log.

2. **Freeze v1 (local).** `mv $PAB_DATA_DIR/full $PAB_DATA_DIR/v1` and
   `ln -s v1 $PAB_DATA_DIR/full` (old commands keep working); record the
   sha256 + size of `v1/pab.db`; `chmod a-w v1/pab.db`. Then copy it to
   **`s3://pab/v1/pab.db`** via `NautilusS3Backend` (creds from the
   `nautilus_s3` rclone remote as before; **confirm with the user before the
   upload**) and verify the public URL by re-download + sha256. Leave the
   `s3://pab/full/` objects untouched (the live site links them). Log.

3. **Build v2.** Write `pab/db/split_version.py` (module + `python -m`
   entry point; tests with a synthetic v4 store): copy `v1/pab.db` →
   `$PAB_DATA_DIR/v2/pab.db`, delete the BING `fits` rows
   (`algorithm='BING'`) and their `fit_results` (join on `fit_id`), keep the
   NASA-GIOP rows **and `matchups.scene_path`** (R7: the v2 site reuses the
   v1 scenes), `VACUUM`, then verify: `PRAGMA
   integrity_check`, `foreign_key_check`, counts (`fits` = 14,609 all
   `NASA_GIOP`; `fit_results` = 116,872 all `NASA_GIOP_*`; every other table
   equal to v1), and that `v1/pab.db`'s sha256 is unchanged. Create
   `$PAB_DATA_DIR/v2/fit_chains/` (empty). Log the counts.

4. **Docs.** `HOWTO.md`: a new "Versions" subsection describing the
   `v1/`/`v2/` layout (local, PVC, S3) and the frozen-v1 rule;
   `docs/db_schema.rst`: note that `pab_version` on copied rows reflects
   creation, not the DB's version. Update `claude_prompts/v2/
   run_full_inelastic.md` Plan §1 if anything about the layout changed in
   practice. Log.

5. **Update**.  Based on what you have done, update the prompt doc `build_v2_prompt_2.md`, as needed.  Use Opus 5. Log

## Q&A

### Q1 (Task 2, 2026-09-14) — confirm the S3 upload of `v1/pab.db` — **ANSWERED: yes**

The **local** freeze is done (`full/` → `v1/`, symlink, `chmod a-w`, sha256
verified unchanged). The remaining half is outward-facing, so it is held here
per the working agreement. Proposed, on your go-ahead:

- `NautilusS3Backend(bucket="pab", prefix="v1")` uploads
  `$PAB_DATA_DIR/v1/pab.db` (169,938,944 B) to a **new** key
  `s3://pab/v1/pab.db`; creds read from the `nautilus_s3` rclone remote.
- Nothing under `s3://pab/full/` is touched — the three live objects there
  (`pab.db`, `matchup_summary.csv`, `matchup_summary.parquet`) are what the
  site links, and `full/pab.db` is already byte-identical to the new `v1/`
  copy, so the site keeps working either way.
- Verified afterwards by anonymous re-download of
  `https://s3-west.nrp-nautilus.io/pab/v1/pab.db` + sha256 compare.
- No ACL work needed: the bucket policy is `PublicReadOnly` on
  `arn:aws:s3:::pab/*`, so the new prefix is public-read on arrival.
- `s3://pab/v1/` does not currently exist, so this only adds an object — it
  overwrites nothing.
>A. Yes, go ahead

Done — uploaded to `s3://pab/v1/pab.db` and verified by
anonymous re-download + sha256. See the Task 2 report below.


## Reports

### Task 1 — `ocean14` environment (2026-09-14): **ready**

`argopy` **does install on Python 3.14** — no fallback to `os_313` needed.
`aiohttp==3.12.15` (argopy's upper pin) has no cp314 wheel but builds cleanly
from sdist in this env.

**Test suite:** `pytest pab/tests` → **215 passed, 0 skipped, 0 failed** (35 s).
Against the recorded `os_313` baseline of *213 passed + 2 jax-env failures*
(215 collected), `ocean14` is **+2 passing / -2 failing**: the two jax tests now
run because `jax` is present here. No test regressed.

**`package_versions()` snapshot** (Python 3.14.6):

| package | version |
|---|---|
| pab | 1.1 (editable, `/mnt/tank/Oceanography/python/PAB`) |
| bing | 0.0.dev0 (editable, `../bing`) |
| ocpy | 0.1.dev0 (editable, `../ocpy`) |
| argopy | 1.4.0 |
| remote_sensing | 0.0.dev0 (editable, `../remote_sensing`) |
| earthaccess | 0.18.0 |
| numpy | 2.5.2 |
| scipy | 1.18.0 |
| xarray | 2025.9.0 |

Other tracked versions: `jax` 0.11.1, `robust` 0.0.dev0 (editable,
`../retrieve-or-bust`), `erddapy` 3.2.1, `healpy` 1.19.0, `bokeh` 3.9.1,
`pandas` 3.0.3, `matplotlib` 3.11.0, `netCDF4` 1.7.4, `sqlalchemy` 2.0.52,
`boto3` 1.43.40, `aiohttp` 3.12.15, `pytest` 9.1.1.

All 13 required imports succeed: `pab`, `argopy`, `erddapy`, `robust`, `jax`,
`bing`, `ocpy`, `remote_sensing`, `earthaccess`, `healpy`, `bokeh` (plus
`boto3`, `s3fs`, `sqlalchemy` needed by the S3 / docs paths).
`pab --help` resolves to `$CONDA_PREFIX/bin/pab`.

**Two side effects of installing argopy, both benign but recorded:**

1. `xarray` **2026.4.0 → 2025.9.0** (argopy 1.4.0 pins `xarray<=2025.9.0`).
   This is the same xarray the v1.0 results were produced with under `os_313`,
   so it moves *toward* the published stack, not away from it.
2. `aiohttp` **3.14.3 → 3.12.15** (argopy pins `aiohttp<=3.12.15`). This leaves
   a pip metadata conflict — `aiobotocore 3.9.0 requires aiohttp>=3.14.0`.
   It is metadata-only: `s3fs` and `boto3` both import and work, and PAB's S3
   path (`pab/report/publish.py`) uses **sync `boto3`**, never `aiobotocore`.
   Left as-is rather than pinning `aiobotocore` down, which would churn `s3fs`.


### Task 2 — v1 frozen, locally and on S3 (2026-09-14): **done**

**Local freeze.** `mv $PAB_DATA_DIR/full $PAB_DATA_DIR/v1` + `ln -s v1 full`;
`chmod a-w v1/pab.db` (now `-r--r--r--`).

| | |
|---|---|
| path | `/mnt/tank/Oceanography/data/Color/PAB/v1/pab.db` |
| sha256 | `09de0a6d334dc02e73494b198567a37707e1942e5cfd1173c89822b35f978273` |
| size | 169,938,944 B |
| schema | `PRAGMA user_version` = 4 |

The sha256 **matches the invariant** in the working agreements
(`09de0a6d…f978273`, 169,938,944 B) and is unchanged before the move, after the
move, and after the S3 round-trip. The DB was clean at move time — no `-wal` /
`-shm` files, no open handles.

The freeze was checked to actually bite, not just to be set: a `CREATE TABLE`
through the `full` symlink fails with `attempt to write a readonly database`,
while `mode=ro` opens read normally. Row counts through the symlink match the
expected v1 inventory exactly:

| table | rows |
|---|---|
| floats | 881 |
| profiles | 54,031 |
| mld_summary | 54,031 |
| granules | 67,435 |
| matchups | 14,610 |
| matchup_pixels | 146,100 |
| fits | 29,218 (14,609 `BING` `1.0` + 14,609 `NASA_GIOP` `1.1`) |
| fit_results | 262,962 |

Note the pixel table is named **`matchup_pixels`**, not `pixels`.

**S3 upload** (confirmed by JXP — Q1). `NautilusS3Backend(bucket="pab",
prefix="v1")`, creds from the `nautilus_s3` rclone remote, endpoint
`https://s3-west.nrp-nautilus.io`. Uploaded in 2.6 s to a **new** key:

- `https://s3-west.nrp-nautilus.io/pab/v1/pab.db`

**Verified by anonymous re-download** (no credentials): HTTP 200,
`content-length` 169,938,944, sha256 `09de0a6d…f978273` — identical to the
local frozen file. No ACL work was needed: the bucket carries a
`PublicReadOnly` policy on `arn:aws:s3:::pab/*`, so any new prefix is
public-read on arrival.

**`s3://pab/full/` left untouched**, as required — all three live objects still
HTTP 200 with their original modtimes:

| key | bytes | last-modified |
|---|---|---|
| `full/pab.db` | 169,938,944 | Fri, 11 Sep 2026 11:08:25 GMT |
| `full/matchup_summary.csv` | 5,449,551 | Wed, 26 Aug 2026 13:48:56 GMT |
| `full/matchup_summary.parquet` | 2,413,488 | Wed, 26 Aug 2026 13:48:56 GMT |
| `v1/pab.db` *(new)* | 169,938,944 | Mon, 14 Sep 2026 12:14:12 GMT |

`full/pab.db` and `v1/pab.db` share the etag
`190ca801f4af98dd803074cf837e24d3-21` — byte-identical, same multipart layout.


### Task 3 — v2 database built (2026-09-14): **done**

New module **`pab/db/split_version.py`** (+ **`pab/tests/test_split_version.py`**,
15 tests against a synthetic schema-v4 store on disk). Run:

```
python -m pab.db.split_version \
    --src $PAB_DATA_DIR/v1/pab.db --dst $PAB_DATA_DIR/v2/pab.db --fit-chains
```

`$PAB_DATA_DIR/v2/pab.db` — **120,635,392 B** (170 MB → 120.6 MB after
`VACUUM`), schema v4, writable. `$PAB_DATA_DIR/v2/fit_chains/` created, empty.

| table | v1 | v2 | |
|---|---:|---:|---|
| floats | 881 | 881 | = |
| profiles | 54,031 | 54,031 | = |
| mld_summary | 54,031 | 54,031 | = |
| granules | 67,435 | 67,435 | = |
| matchups | 14,610 | 14,610 | = |
| matchup_pixels | 146,100 | 146,100 | = |
| **fits** | 29,218 | **14,609** | −14,609 BING |
| **fit_results** | 262,962 | **116,872** | −146,090 BING |

Both targets in the task are hit exactly: `fits` = **14,609, all
`NASA_GIOP`** (all `pab_version` `1.1`); `fit_results` = **116,872, all
`NASA_GIOP_*`** (0 rows fail `LIKE 'NASA_GIOP_%'`; 8 distinct quantities).

Verification, all clean:

- `PRAGMA integrity_check` → `ok`
- `PRAGMA foreign_key_check` → 0 violations
- 0 orphan `fit_results`; 0 `fits` with a dangling `matchup_id`
- every non-fit table equal to v1 (table above)
- **`matchups.scene_path` kept** — 14,586 non-null, same as v1 (R7)
- `PRAGMA user_version` = 4 in both
- **`v1/pab.db` sha256 unchanged**: `09de0a6d…f978273`, still `-r--r--r--`

`pytest pab/tests` → **230 passed, 0 failed** (215 + 15 new).


### Task 4 — docs updated (2026-09-14): **done**

**`HOWTO.md` — new §5b "Versions — `v1/` (frozen) and `v2/`"** (between
Outputs and Notes & gotchas). Covers the frozen-v1 rule (sha256 invariant,
`chmod a-w`, read-only opens, explicit `--db`), the full three-way layout
table (workstation / Nautilus PVC / S3, plus backup), the public-URL and
bucket-policy facts, and how to build a version database with
`python -m pab.db.split_version`, with the v1→v2 count table. §7b gained a
short "Versioned layout" note recording `s3://pab/v1/pab.db` and pointing at
§5b, so "what is published where" is no longer stale.

**`docs/db_schema.rst`** — a new Conventions bullet stating that
`pab_version` records when a **row** was created, **not** which database file
it lives in, with the concrete v2 case (copied `matchups` stamped `1.0`,
NASA-GIOP fits `1.1`, only v2-created rows `2.0`) and the corollary: do not
infer a DB's version from the stamps inside it. It also links the existing
counter-example (the 2026-09-05/06 backfill deliberately stayed at `1.0`). The
Migrations section now distinguishes schema migration from *version splitting*
and points at `pab.db.split_version`, and the Access API section autodocs the
new module so those `:mod:` references resolve.

**`run_full_inelastic.md` Plan §1** — "Proposed layout (confirm in R1)" became
"confirmed in R1; the workstation and S3 rows were **built on 2026-09-14**…
the PVC row is still pending", plus an **"As built"** block with the real
numbers and three practical notes (below).

Verification: `python -m sphinx -b html docs` builds **clean, zero warnings**;
`pytest pab/tests` → **230 passed**; `ruff check` clean on both new files (the
8 remaining repo-wide errors are pre-existing in
`pab/argo/check_argo_coverage.py`, untouched here); `v1/pab.db` still
`-r--r--r--` at `09de0a6d…f978273`.

**One thing that did change in practice**, now documented in all three places:
`pab.fit.artifacts.chains_path()` resolves to **`$PAB_DATA_DIR/fit_chains/`** —
the *root* of `PAB_DATA_DIR`, not a per-version subdirectory. So the
`$PAB_DATA_DIR/v2/fit_chains/` created in Task 3 is **inert on the workstation**
unless `PAB_DATA_DIR` is itself pointed at `…/Color/PAB/v2`. The plan's PVC row
already gets this right (`PAB_DATA_DIR=/data/v2`); the workstation row did not
say it.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-14 (Task 1 — stood up the `ocean14` env with the full v2 stack)

Built out `ocean14` (Python 3.14.6) so the whole v2 run can happen in one
environment, resolving the split recorded earlier (`ocean14` had `robust`/`jax`
but no `pab`/`argopy`; `os_313` had `pab`/`argopy` but no `robust`/`jax`).

What was done:

- `pip install -e . --no-deps` for PAB → `pab 1.1` editable. Before this, `pab`
  only "imported" in `ocean14` because the CWD was the repo — it was never
  actually installed, and `pab` the console script did not exist. It does now.
- `pip install argopy==1.4.0 erddapy==3.2.1`. **The open question in the task —
  whether `argopy` installs on Python 3.14 — is answered: yes.** The only
  sdist-only dependency is `aiohttp==3.12.15` (argopy's upper pin, no cp314
  wheel published); it compiled its C extensions against 3.14 without a
  complaint and cached a `cp314` wheel. No fallback to `os_313` +
  `retrieve-or-bust` + `jax` is needed, so the series can stay in one env.
- `pip install -e ../remote_sensing --no-deps` (only local checkout; the same
  one `os_313` uses).
- Filled in the four `requirements.txt` docs deps that were missing:
  `sphinx-rtd-theme`, `myst-parser`, `myst-nb`, `sphinxcontrib-mermaid`. These
  pulled `sqlalchemy 2.0.52` in transitively via `jupyter-cache`, which also
  closes a gap I would have hit later.
- `pytest pab/tests` → **215 passed, 0 skipped, 0 failed**. The `os_313`
  baseline was 213 passed + 2 jax-env failures out of the same 215 collected,
  so `ocean14` is strictly better: the two jax tests pass here because `jax`
  0.11.1 is installed. Nothing regressed under the newer numpy/pandas.

What I learned / want to remember:

- Installing `argopy` is not free in this env: it **downgraded `xarray`
  2026.4.0 → 2025.9.0** and **`aiohttp` 3.14.3 → 3.12.15**. The xarray move is
  actually desirable — 2025.9.0 is what the published v1.0 numbers were
  computed against in `os_313` — but it is worth knowing that `ocean14` is no
  longer on the newest xarray, and that anything else in this env expecting
  2026.x is now on older code.
- The aiohttp downgrade leaves one unsatisfiable pip constraint:
  `aiobotocore 3.9.0 requires aiohttp>=3.14.0`. I deliberately did **not**
  chase it. It is metadata-only (both `s3fs` and `boto3` import and function),
  and PAB's only S3 code path, `pab/report/publish.py`, imports **sync
  `boto3`** lazily and never touches `aiobotocore`. Pinning `aiobotocore` back
  would drag `s3fs` around for no benefit. Task 2's S3 upload is therefore
  unaffected — but if a *future* async/fsspec S3 path ever appears, this is
  the first thing to check.
- `pandas` here is **3.0.3**, a major version ahead of `os_313`'s 2.2.3, and
  the suite still passes clean. Good signal, but any pandas-3 behaviour
  difference in the v2 stages will show up in `ocean14` and not in `os_313`.
- Reminder for the rest of the series: nothing in this task touched
  `$PAB_DATA_DIR`. `v1/pab.db` does not exist yet — the freeze is Task 2, and
  the DB is still at `full/pab.db`.

### 2026-09-14 (Task 2 — froze v1.0, locally and at a permanent S3 URL)

The published 1.0 dataset is now immutable and has its own versioned home, so
nothing built in the rest of the v2 series can disturb it.

Local side:

- `mv $PAB_DATA_DIR/full $PAB_DATA_DIR/v1` then `ln -s v1 $PAB_DATA_DIR/full`.
  The symlink means every existing command, script and `--db` path that says
  `full/pab.db` keeps resolving, so nothing had to be updated to match.
- `chmod a-w v1/pab.db` → `-r--r--r--`. The whole `full/` directory moved, so
  the two NASA-GIOP logs and the two sibling DBs
  (`pab_merged_nasa_giop_2026-09-10.db`, `pab_pre_cdom_merge_2026-09-10.db`)
  came along into `v1/` — only `pab.db` itself was write-protected.
- sha256 `09de0a6d…f978273` / 169,938,944 B, matching the invariant in the
  working agreements, and identical before the move, after the move, and after
  the S3 round-trip.

S3 side (confirmed with JXP first, per the outward-facing-actions agreement):

- `NautilusS3Backend(bucket="pab", prefix="v1")` with creds pulled out of the
  `nautilus_s3` rclone remote. 170 MB in 2.6 s → `s3://pab/v1/pab.db`.
- Verified the way the agreement wants it verified — an *anonymous* `curl` of
  `https://s3-west.nrp-nautilus.io/pab/v1/pab.db`, re-downloaded and sha256'd,
  matching the local file. Not just a successful PUT.
- `s3://pab/full/` untouched: all three objects still 200 with their original
  modtimes (11 Sep / 26 Aug). The live site keeps working off them.

What I learned / want to remember:

- **Verify the freeze, don't just set it.** `chmod a-w` is easy to believe in;
  I confirmed it by actually attempting `CREATE TABLE` through the symlink and
  getting `attempt to write a readonly database`. Worth doing because the
  symlink adds an indirection that could plausibly have been the thing you
  write through. It isn't — the mode on the target wins.
- The pixel table is **`matchup_pixels`**, not `pixels`. The prompt's context
  block says "146,100 pixels", which reads like a table name; it is not one. I
  tripped on this while inventorying and it will matter in Task 3's
  "every other table equal to v1" check.
- `full/pab.db` and the new `v1/pab.db` came out with the **same etag**
  (`190ca801f4af98dd803074cf837e24d3-21`, a 21-part multipart tag). boto3's
  multipart chunking is deterministic for a given file size, so the etag is a
  cheap byte-identity check between two S3 objects without downloading either
  — useful later for confirming `full/` and `v1/` have not diverged.
- No ACL handling was needed. The bucket has a `PublicReadOnly` policy scoped
  to `arn:aws:s3:::pab/*`, i.e. the whole bucket, so a brand-new prefix is
  world-readable the moment the object lands. `NautilusS3Backend.upload()`
  sets no ACL and does not need to.
- Note for Task 4's docs: `s3://pab` also still holds the old `run1k/` tree
  (`pab.db`, `fit_chains/`, `pipeline/` figures) from July. Not touched, but
  it is part of "what is published where" if that section gets rewritten.

### 2026-09-14 (Task 3 — built the v2 database with `pab/db/split_version.py`)

Wrote `pab/db/split_version.py` (module + `python -m` entry point) and
`pab/tests/test_split_version.py` (15 tests), then used it to create
`$PAB_DATA_DIR/v2/pab.db` from the frozen v1.

The module is copy → delete → `VACUUM` → verify, with the source opened
**read-only** throughout and its sha256 taken before the copy and re-checked at
the end, so a run proves it left the release alone rather than merely intending
to. `verify()` is a separate public function, so the copy can be re-checked at
any later date without rebuilding it.

Results — every number the task asked for landed exactly:

- `fits` 29,218 → **14,609**, all `NASA_GIOP` (`pab_version` `1.1`)
- `fit_results` 262,962 → **116,872**, all `NASA_GIOP_*`
- every other table bit-for-bit equal in count to v1
- `matchups.scene_path` 14,586 non-null, unchanged (R7)
- `integrity_check` ok, `foreign_key_check` clean, 0 orphans
- v1 sha256 `09de0a6d…f978273` unchanged
- 169,938,944 B → 120,635,392 B after `VACUUM`
- `v2/fit_chains/` created, empty

What I learned / want to remember:

- **`shutil.copy2` would have been a bug here.** It propagates mode, so
  copying the `chmod a-w` v1 file gives a read-only v2, and the very next
  statement — the `DELETE` — fails with `attempt to write a readonly
  database`. I used the `sqlite3` **online-backup API** (`src.backup(dst)`)
  instead: it creates the destination with normal permissions *and* takes a
  transactionally consistent snapshot. There is a regression test for exactly
  this (`test_copy_of_readonly_source_is_writable`), because it is the kind of
  thing that gets "simplified" back into a `copy2` later.
- Delete order matters and is not incidental: `fit_results` first, then
  `fits`. Done the other way round with `PRAGMA foreign_keys = ON` the parent
  delete trips the constraint. Both run inside one `with conn:` transaction.
- The dropped algorithm is a **parameter**, not a hard-coded `'BING'`, and
  there is a test that drops `NASA_GIOP` instead. Cheap to do, and it means
  the helper is reusable when a v3 line eventually needs the same surgery.
- `VACUUM` reclaimed 49.3 MB (29%). Worth doing — without it the freed pages
  stay in the file and the "v2 is smaller because it has fewer fits" story
  would not hold on disk.
- Verifying by quantity **prefix** (`substr` up to the first `_`) is coarse:
  `NASA_GIOP_bbp_442` counts under `NASA`. That is fine for proving no BING
  rows survive, but I also ran an explicit
  `WHERE quantity NOT LIKE 'NASA_GIOP_%'` → 0 check against the real DB, since
  the task's wording is specifically "all `NASA_GIOP_*`".
- `VACUUM` preserves `PRAGMA user_version` — confirmed v4 on both sides. Worth
  knowing, since it does *not* preserve everything (it rebuilds the file).

### 2026-09-14 (Task 4 — documented the v1/v2 layout and the pab_version caveat)

Wrote the versioning story into the three places that will be consulted later:
`HOWTO.md` (how to operate it), `docs/db_schema.rst` (how to read the stamps),
and the plan doc (what was actually built).

- **`HOWTO.md` §5b "Versions"**, a new subsection between Outputs and Notes &
  gotchas. The frozen-v1 rule stated as a rule with its enforcement (sha256
  invariant, `chmod a-w`, read-only URI opens, explicit `--db`, attach-don't-
  copy for comparisons); a workstation/PVC/S3/backup table; the public URL
  pattern and the `arn:aws:s3:::pab/*` bucket policy; and the
  `python -m pab.db.split_version` recipe with the v1→v2 counts. §7b got a
  pointer to it so the older "what is published where" text is not stale.
- **`docs/db_schema.rst`**: the `pab_version` caveat as a Conventions bullet,
  the Migrations section now separating schema migration from version
  splitting, and an `automodule` for `pab.db.split_version`.
- **`run_full_inelastic.md` Plan §1**: "Proposed" → confirmed/built, plus an
  "As built" block with the real numbers and the three notes below.

What I learned / want to remember:

- **The `v2/fit_chains/` directory Task 3 asked for is, on the workstation,
  inert.** `pab.fit.artifacts.chains_path()` is
  `Path(DATA_DIR) / "fit_chains" / f"{fit_id}.npz"` where `DATA_DIR` is
  `PAB_DATA_DIR` itself — the *root*, not a per-version subdir. With the
  `.bashrc` value `PAB_DATA_DIR=…/Color/PAB`, chains land in
  `…/Color/PAB/fit_chains/` no matter which `--db` is passed, so a v2 fit run
  on this box would scatter chains into the shared root and mix them with v1's
  unless `PAB_DATA_DIR` is deliberately set to `…/Color/PAB/v2`. The plan's PVC
  row already anticipated exactly this (`PAB_DATA_DIR=/data/v2`); the
  workstation row did not. Flagged in all three docs — this is the sort of
  thing that silently produces an unattributable pile of NPZs.
- Related and slightly alarming: the **test suite writes into that same root
  `…/Color/PAB/fit_chains/`**. Two `.npz` files there were rewritten during my
  `pytest` runs today. It does not threaten the freeze (nothing goes near
  `v1/pab.db`, which I re-verified after every run), but a test touching a
  production data directory at all is worth knowing about.
- `/home/xavier/Oceanography` is a **symlink to `/mnt/tank/Oceanography`**, so
  the `.bashrc` `PAB_DATA_DIR=/home/xavier/Oceanography/data/Color/PAB` and the
  prompt series' `/mnt/tank/Oceanography/data/Color/PAB` are the *same
  directory*. I checked this rather than assuming, because a genuine split
  there would have meant Tasks 2–3 froze and built in the wrong place.
- `VACUUM` preserves `PRAGMA user_version`, so a version split leaves the
  schema version alone — worth stating in the Migrations section, since
  "splitting a version" and "migrating a schema" are easy to conflate and only
  one of them touches `user_version`.
- The docs build is clean with **zero** warnings, and stays that way with the
  new `automodule`. Sphinx here is not in nitpick mode, so an unresolved
  `:mod:` reference would have failed silently — adding the `automodule` makes
  the two new cross-references actually resolve rather than just look right in
  the source.
