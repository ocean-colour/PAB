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

## Q&A

### Q1 (Task 2, 2026-09-14) — confirm the S3 upload of `v1/pab.db` — **awaiting JXP**

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
