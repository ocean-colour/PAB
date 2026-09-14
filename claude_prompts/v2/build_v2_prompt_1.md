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

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
