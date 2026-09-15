# Build v2 — Prompt 2: per-pixel viewing geometry from PACE L1B (`geometry` stage)

## Goals

Give every matchup pixel the solar/sensor geometry the RoB backend requires
(`theta_s`, `theta_v`, `dphi`), read from the co-temporal **PACE L1B**
granule, stored on `matchup_pixels` (schema **v5**) and filled by a new
**parallel `geometry` stage** — so the `fit` stage never pays the L1B open
in its serial parent loop (`run_full_inelastic.md` Plan §2.1, §3 c; Q3 = A,
R3).

## Claude

### Skills

- **`batch-fit-argo`** — the workers-read / parent-writes pattern the new
  stage copies from `match`.

### Working agreements

As in `build_v2_prompt_1.md`: user's git; Python in `ocean14`; explicit
`--db`; **`v1/pab.db` frozen** (develop against `v2/pab.db` or a scratch
copy of it); log; use Fable if you can.

**Settled in Prompt 1 — no longer open:**

- **`ocean14` is ready and is the only env you need.** Python 3.14.6 with
  `pab` 1.1 editable, `argopy` 1.4.0, `erddapy` 3.2.1, `remote_sensing`,
  `robust`, `jax`, `bing`, `ocpy`, `earthaccess` 0.18.0, `healpy`, `bokeh`,
  and the Sphinx/myst docs deps. The `os_313` fallback is not needed.
- **Test baseline is now `230 passed, 0 failed`** (`pytest pab/tests`), not
  215 — Prompt 1 added `pab/tests/test_split_version.py` (15 tests). Regress
  against 230.
- **`xarray` is pinned to 2025.9.0** in `ocean14` (argopy 1.4.0 caps it).
  Checked for this prompt: `xr.open_datatree(..., engine="h5netcdf")` works
  on that version with `h5netcdf` 1.8.1, so the Context read below is
  reproducible here. Don't "upgrade xarray to get datatree" — that breaks
  argopy.
- `ruff check pab/` reports **8 pre-existing errors in
  `pab/argo/check_argo_coverage.py`**. They are not yours; leave them. Both
  files added in Prompt 1 are clean.

## Context

- Plan §2.1 (the verified L1B read) and §3 c/k of
  `claude_prompts/v2/run_full_inelastic.md`.
- **Verified facts (2026-09-14):** for `PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc`
  the CMR short name **`PACE_OCI_L1B_SCI`** returns the same-stamp
  `PACE_OCI.20250309T131631.L1B.V3.nc` (1.8 GB; **each granule is listed
  twice — dedupe by name**). `xr.open_datatree(earthaccess.open(...)[0],
  engine="h5netcdf")` → group `geolocation_data` with `solar_zenith`,
  `sensor_zenith`, `solar_azimuth`, `sensor_azimuth`, `latitude`,
  `longitude`, dims `(scans, pixels)` = `(1709, 1272)` — **identical grid to
  the L2**, lat/lon bit-identical at pixel `(868, 142)`; open + 4-value read
  7.6 s out-of-region. At that pixel `theta_s = 29.47°`, `theta_v = 54.58°`,
  `solar_azimuth = −19.75°`, `sensor_azimuth = 61.58°`.
- Precedents to mirror: `pab/pace/iop.py` (`iop_source_for_aop` name swap,
  flag-free nearest pixel, grid check) and `pab/matchup/engine.py` (the
  parallel `match` shape: `GranuleIndex`, `_open_with_timeout`, chunked
  pools, `_reclaim_pool`, `--jobs`).
- `pab/db/schema.py` (`MIGRATIONS`, `_v3_to_v4` as the template),
  `docs/db_schema.rst`.
- The cached granules in `/mnt/tank/Oceanography/data/PAB/pilot/granules/`
  (for local tests of the L2 side; the L1B read is a live network call).
  **Corrected 2026-09-14** — the doc said "the three cached V3.2 granules";
  there are in fact **85 files (42 `V3_2` + 43 `V3_1`)**, and **10 of the
  `V3_2` granules appear in `v2`'s matchups**, together covering
  **20 matchups / 200 pixels**. That is the local validation set for Task 4,
  and it is far better than three. Note the directory is under
  `…/data/PAB/`, **not** under `$PAB_DATA_DIR` (`…/data/Color/PAB/`) — it
  looks like a typo but is correct.

  | granule (`…L2.OC_AOP.V3_2.nc`) | matchups | pixels |
  |---|---:|---:|
  | `PACE_OCI.20241008T010831` | 2 | 20 |
  | `PACE_OCI.20250309T131631` | 1 | 10 |
  | `PACE_OCI.20250625T030832` | 6 | 60 |
  | `PACE_OCI.20250909T150111` | 2 | 20 |
  | `PACE_OCI.20250910T153613` | 2 | 20 |
  | `PACE_OCI.20251004T014456` | 1 | 10 |
  | `PACE_OCI.20251005T004636` | 2 | 20 |
  | `PACE_OCI.20251128T222318` | 1 | 10 |
  | `PACE_OCI.20251129T225813` | 1 | 10 |
  | `PACE_OCI.20260216T162141` | 2 | 20 |

  Conveniently, `PACE_OCI.20250309T131631` — the granule the verified-facts
  block above was measured on — **is** one of the ten, so Task 4 can check the
  stage's output against the known `theta_s = 29.47°` / `theta_v = 54.58°` at
  pixel `(868, 142)`.

- **The databases exist as of Prompt 1** (`build_v2_prompt_1.md` Tasks 2/3):
  - `$PAB_DATA_DIR/v1/pab.db` — **frozen**, `-r--r--r--`, sha256
    `09de0a6d…f978273`, 169,938,944 B, schema **v4**.
    `$PAB_DATA_DIR/full` is a symlink to `v1`.
  - `$PAB_DATA_DIR/v2/pab.db` — **the one you migrate and fill**,
    120,635,392 B, schema **v4**, writable. 881 floats / 54,031 profiles /
    67,435 granules / **14,610 matchups** / **146,100 `matchup_pixels`** /
    14,609 `NASA_GIOP` fits / 116,872 `fit_results`. No BING rows.
  - Verified for Task 3's sizing: those 14,610 matchups reference
    **11,494 distinct granules** — the figure in Task 3 is correct. All
    146,100 pixels have `flagged = 0`, so none can be skipped on that basis;
    plan on **146,100 pixels across 11,494 L1B opens**.
  - `$PAB_DATA_DIR/v2/fit_chains/` exists but is **empty and currently
    inert** — see the `PAB_DATA_DIR` warning under Tasks.

- **`pab/db/split_version.py`** (new in Prompt 1) is how you make the Task 4
  scratch copy: `split_version.copy_database(src, dst)` copies a store via the
  `sqlite3` online-backup API. Use it rather than `shutil.copy2`, which
  propagates the frozen `a-w` mode onto the copy.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below

## Tasks

### Before you start — four things Prompt 1 changed under you

1. **The schema bump breaks every default `Store.open()` on `v1/pab.db`.**
   `v1` is now `chmod a-w` at schema v4. The moment Task 1 sets
   `SCHEMA_VERSION = 5`, `Store.open(v1_path)` — which defaults to
   `create=True` and therefore tries to migrate — raises
   `OperationalError: attempt to write a readonly database`. Verified by
   simulating the bump. The freeze is doing its job (it fails loudly instead
   of mutating the release), but **every read of v1 must pass
   `create=False`**, or open the file read-only via
   `sqlite3.connect("file:…?mode=ro", uri=True)`. This bites the
   `--compare-db` work in a later prompt too; grep for bare `Store.open(` on
   anything v1-shaped before you finish.

2. **`v2/pab.db` is at schema v4 and is what you migrate.** A default
   `Store.open("$PAB_DATA_DIR/v2/pab.db")` will run `_v4_to_v5` in place.
   That is intended — but do it deliberately and log the before/after
   `PRAGMA user_version`, and remember 146,100 `matchup_pixels` rows gain
   four NULL columns.

3. **`PAB_DATA_DIR` is the *root*, not the version directory.**
   `pab.fit.artifacts.chains_path()` resolves to
   `$PAB_DATA_DIR/fit_chains/<fit_id>.npz`, so with the shell default
   (`PAB_DATA_DIR=…/Color/PAB`, which is a symlink-equivalent of
   `/mnt/tank/Oceanography/data/Color/PAB`) artifacts land in
   `…/Color/PAB/fit_chains/`, **not** `…/Color/PAB/v2/fit_chains/`, no matter
   which `--db` you pass. The `geometry` stage writes no chains so this does
   not bite Task 3 directly, but it will bite the fit prompts — and note the
   **test suite already writes into that shared root**, so don't be surprised
   by `.npz` files appearing there during `pytest`.

4. **Docs have moved on.** `HOWTO.md` gained **§5b "Versions"** (the
   `v1`/`v2` layout + the frozen-v1 rule) — Task 4's stage row goes in the
   §4 stage table, and the "geometry before fit" rule belongs beside it.
   `docs/db_schema.rst` gained a `pab_version` Conventions bullet, a
   Migrations paragraph distinguishing schema migration from version
   splitting, and an `automodule` for `pab.db.split_version`; Task 1's schema
   notes slot into the same Conventions/Tables structure. The docs currently
   build with **zero** Sphinx warnings — keep it that way.

### The tasks

1. **Schema v5 (pixels).** Add `matchup_pixels.theta_s`, `theta_v`, `dphi`
   (degrees, REAL, NULL on legacy rows) and `geom_source` (TEXT, e.g.
   `"L1B_V3"`), via a registered `_v4_to_v5` forward migration;
   `SCHEMA_VERSION = 5`; migration test; `docs/db_schema.rst` updated with
   units and the `dphi = sensor_azimuth − solar_azimuth` (wrapped to
   (−180, 180]) convention. (The `fits` v5 columns are added in Prompt 3 —
   the same migration function may carry both; coordinate.) Log.

2. **L1B reader** (`pab/pace/l1b.py`, replacing the current
   `NotImplementedError` stub's *module*, keeping `rrs_from_l1b` untouched —
   the file is 35 lines and also exports `RRS_SOURCE_PREFIX` and
   `RRS_SOURCE_L2`, both asserted by `pab/tests/test_pace.py:307-309`, so
   keep all three symbols):
   `l1b_source_for_aop(aop_granule_id_or_url)` (name-swap `L2.OC_AOP.V3_2`
   → `L1B.V3` **plus** a CMR lookup by `PACE_OCI_L1B_SCI` + the stamp's
   time window to obtain the real URL, deduped), `open_l1b_geolocation(source)`
   (lazy datatree, `geolocation_data` only, bounded by the same
   `_open_with_timeout`), and `pixel_geometry(ds, ix, iy, *, lat, lon,
   tol_deg=0.01)` → `(theta_s, theta_v, dphi)` after a **grid check**
   against the stored pixel lat/lon (raise on mismatch — never silently
   assume alignment). Offline tests with a synthetic geolocation dataset;
   one live test guarded by an env flag reproducing the numbers above. Log.

3. **The `geometry` stage.** Add `"geometry"` to `pab.pipeline.STAGES`
   (`pab/pipeline.py:35`, currently
   `("ingest", "discover", "match", "fit", "figure", "report")`)
   **between `match` and `fit`** (default run order), implemented like
   `match`: gather all `matchup_pixels` rows with `theta_s IS NULL` grouped
   by granule (one L1B open per granule — **confirmed against `v2`:
   11,494 distinct granules carry the 14,610 matchups / 146,100 pixels**, and
   no pixel is `flagged`, so none can be skipped), workers open + read all
   that granule's pixels, parent writes; `--jobs`; idempotent (skips filled pixels; `--replace` refills);
   per-granule failures logged and counted, never aborting the stage; a
   `"failed"` list in the summary. `--stage geometry` on the CLI; `dry-run`
   lists it. Tests: serial + parallel (module-level stub opener) agree;
   resume does zero opens; a grid-check failure is recorded, not raised.
   Log.

4. **Local validation.** On a scratch copy of `v2/pab.db` (make it with
   `pab.db.split_version.copy_database`, **not** `shutil.copy2`), run
   `--stage geometry` for the matchups whose granules are cached locally —
   the **10 pilot `V3_2` granules that appear in `v2`, covering 20 matchups /
   200 pixels** (table in Context), their L1Bs fetched live and lazily.
   Confirm the rows are filled, `geom_source` set, values physically sensible
   (`0 ≤ theta_s < 90`, `0 ≤ theta_v ≲ 60`), and re-running skips them.
   **Additionally, check the known-answer case:** granule
   `PACE_OCI.20250309T131631` at pixel `(868, 142)` must give
   `theta_s = 29.47°`, `theta_v = 54.58°`, and
   `dphi = 61.58 − (−19.75) = 81.33°` — that is a real regression anchor, not
   just a sanity range. Measure s/granule for the projection in Prompt 5.
   Report in **Reports**; `HOWTO.md` gains the stage row (§4 table) + the
   "geometry before fit" rule. Log.

5. **Update.** Based on what you have done, update the prompt doc
   `build_v2_prompt_3.md`, as needed. Log.
   *(Added 2026-09-14 to mirror the Task 5 JXP added to
   `build_v2_prompt_1.md`, so each prompt hands its findings to the next.
   Delete it if that is not the intent.)*

## Q&A

### Q1 (Task 1, 2026-09-14) — v5 carries the `fits` columns too, not just the pixels — **decided, flag if wrong**

Task 1 says the `fits` v5 columns land in Prompt 3 and that "the same
migration function may carry both; coordinate." **I carried both**, so
`_v4_to_v5` adds all ten columns now.

The reason is a trap, not a preference. A migration step only runs on a
database still at its *starting* version. Had Task 1 shipped
`SCHEMA_VERSION = 5` with only the four pixel columns and migrated
`v2/pab.db`, that file would be stamped `user_version = 5` — and Prompt 3
extending `_v4_to_v5` would then **never apply** its six `fits` columns to it.
The step is skipped, silently, because the database already claims to be v5.
The failure would surface much later as a missing-column error at fit time.

So v5 is defined once, completely. Column names and semantics are taken
verbatim from Plan §3 row e and `build_v2_prompt_3.md` Task 3:
`rt_backend`, `include_raman`, `include_chl_fl`, `include_cdom_fl`, `phi_c`,
`fit_bp`. **Prompt 3's Task 3 therefore has no migration to write** — the
columns exist; it wires `FitConfig` → `persist_fit` into them. Types are
`TEXT` / `INTEGER` (0/1) / `REAL` / `INTEGER` (0/1); SQLite affinity is loose,
so Prompt 3 can treat them as it likes.

If you would rather v5 had stayed pixels-only, the fix is to move the six
`fits` `ALTER`s into a new `_v5_to_v6` — but `v2/pab.db` is already at v5, so
that would need a version bump, not an edit.


## Reports

### Task 1 — schema v5 (2026-09-14): **done**

`SCHEMA_VERSION = 4 → 5`, with one registered forward migration `_v4_to_v5`
(`pab/db/schema.py`) adding **ten** columns, all NULL on legacy rows:

| table | columns | type |
|---|---|---|
| `matchup_pixels` | `theta_s`, `theta_v`, `dphi` | REAL, **degrees** |
| | `geom_source` | TEXT (e.g. `'L1B_V3'`) |
| `fits` | `rt_backend` | TEXT (`'gordon'` \| `'robust_hybrid'`) |
| | `include_raman`, `include_chl_fl`, `include_cdom_fl`, `fit_bp` | INTEGER 0/1 |
| | `phi_c` | REAL |

`wave_max` already existed — checked, not re-added. Both the `TABLES` DDL
(fresh databases) and the migration (existing ones) were updated, and a test
asserts the two agree.

**`$PAB_DATA_DIR/v2/pab.db` migrated in place**, deliberately:

```
BEFORE  user_version = 4   120,635,392 B
AFTER   user_version = 5   120,635,392 B
```

146,100 `matchup_pixels` rows now carry four NULL geometry columns (all
146,100 `theta_s IS NULL` — the whole backlog for the `geometry` stage);
14,609 `fits` rows carry six NULL RT columns. `integrity_check` → `ok`,
`foreign_key_check` → 0 violations, and every other table count unchanged
(881 / 54,031 / 54,031 / 67,435 / 14,610 / 116,872). The file did not grow —
SQLite `ALTER TABLE ADD COLUMN` is a metadata-only change.

**`v1/pab.db` untouched**: still `-r--r--r--` at `09de0a6d…f978273`, still
`user_version = 4`, re-checked after every step.

**Docs.** `docs/db_schema.rst`: the `matchup_pixels` entry now documents the
three angles with their ranges and the explicit
`dphi = sensor_azimuth − solar_azimuth` **wrapped to (−180, 180]** convention,
worked through on the reference pixel (`61.58 − (−19.75) = 81.33°`), plus why
geometry is per-pixel rather than per-fit; the `fits` entry documents the RT
block; the Migrations section now warns that a version must be defined
completely in one step. Sphinx builds with **zero warnings**.

**Tests: 236 passed, 0 failed** (was 230). Six new in `pab/tests/test_db.py`
— columns added on both paths, legacy rows survive with NULLs, idempotent
re-migrate, `create_all` and `_v4_to_v5` agree, a degrees round-trip, and a
read-only v4 database that must refuse to migrate. Two existing tests that
hard-pinned `== 4` now track `SCHEMA_VERSION`, as does one from Prompt 1.

**One regression found and fixed.** Acting on warning #1's "grep for bare
`Store.open(`": `pab/pipeline.py:1016` opened the store with the default
`create=True` for **`--emit-site`**, which is a purely read-only operation.
With v1 frozen at v4 and `SCHEMA_VERSION` now 5, regenerating the published
1.0 site (`pab --db $PAB_DATA_DIR/full/pab.db --emit-site …`) would have
failed with `attempt to write a readonly database`. Changed to
`create=False` and **verified end-to-end against the real frozen v1** — all 8
site sources emitted, v1's sha256 unchanged. The main run path (line 1030)
keeps `create=True`; it legitimately creates the database.


### Task 2 — L1B geometry reader (2026-09-15): **done**

`pab/pace/l1b.py` rewritten (35 → ~300 lines). **All three stub symbols kept**
— `RRS_SOURCE_PREFIX`, `RRS_SOURCE_L2`, `rrs_from_l1b` (still
`NotImplementedError`) — so `pab/tests/test_pace.py:307-309` passes unchanged.

| function | what it does |
|---|---|
| `granule_stamp(src)` | `…20250309T131631…` out of an AOP id/URL |
| `l1b_name_for_aop(src)` | pure name swap → `PACE_OCI.<stamp>.L1B.V3.nc` |
| `l1b_source_for_aop(src, *, search=None)` | + CMR lookup by `PACE_OCI_L1B_SCI` over a ±1 min window → the real download URL, deduped |
| `read_geolocation(src)` | lazy `open_datatree`, `geolocation_data` only, dims renamed `(scans, pixels)` → `(x, y)` |
| `open_l1b_geolocation(src, *, timeout_s, opener)` | the above, bounded |
| `pixel_geometry(ds, ix, iy, *, lat, lon, tol_deg=0.01)` | → `(theta_s, theta_v, dphi)` after the grid check |
| `wrap_dphi(deg)` | wrap to **(−180, 180]** |
| `GridMismatchError` | raised when the grid check fails |

**Live test passes against the real granule** (`PAB_LIVE_L1B=1`, 12.8 s
end-to-end: CMR → open → read). It resolves `PACE_OCI.20250309T131631` to its
L1B URL, confirms the grid is `(1709, 1272)`, and reproduces every verified
number at pixel `(868, 142)` to 0.01°: **`theta_s = 29.47°`,
`theta_v = 54.58°`, `dphi = 81.33°`**. It is skipped by default.

**Tests: 267 passed, 1 skipped** (was 236). 31 new in `pab/tests/test_l1b.py`,
offline against a synthetic `geolocation_data` dataset — name swap (including
that AOP `V3_1` *and* `V3_2` both map to L1B `V3`), stamp parsing, non-AOP
inputs rejected, CMR dedupe and window bounds, the right granule picked out of
a multi-result window, a malformed CMR result skipped rather than fatal, eight
`wrap_dphi` cases, dim renaming, a granule missing the group, the opener seam,
the timeout actually firing, and five grid-check cases.

Two details worth recording:

- **The `dphi` convention is only unambiguous if you state the half-open end.**
  The usual `((x + 180) % 360) − 180` yields **[−180, 180)**, i.e. the wrong
  end for the documented **(−180, 180]**. `wrap_dphi` uses
  `180 − ((180 − x) % 360)`, so `−180 → +180`, and there is a test for it.
- **The grid check is longitude-wrap aware.** A naive `abs(lon_a − lon_b)`
  makes `179.99` and `−179.99` look 359.98° apart and would reject every
  antimeridian pixel. `_lon_delta` reuses `wrap_dphi`; tested.

**One shared change outside the module.** `pab.matchup.engine._open_with_timeout`
gained an optional `open_fn` so a caller can bound a *different* read with the
same SIGALRM guard, instead of `l1b` re-implementing it. Default behaviour is
untouched (`cloud.open_granule`), and the existing callers —
`engine:426` and `pab/fit/run.py:46` — are unchanged; `test_matchup.py` passes.


### Task 3 — the `geometry` stage (2026-09-15): **done**

New module **`pab/matchup/geometry.py`**, wired into the pipeline as a
first-class stage **between `match` and `fit`**:

```
ingest → discover → match → geometry → fit → figure → report
```

`--stage geometry` and the dry-run listing both come free — the CLI's
`choices=STAGES` and `run()`'s plan are derived from the tuple, so only
`pab/pipeline.py:35` and `_STAGE_FUNCS` needed editing.

**Shape** (mirrors `match`): the parent reads the work list and performs
**every** DB write; workers only open granules and read values, so there is one
SQLite writer and no lock contention.

| function | role |
|---|---|
| `pixels_needing_geometry(store, *, replace)` | the work list — `theta_s IS NULL`, joined to the granule `source` (`data_url` else `granule_id`), ordered by granule |
| `group_by_granule(rows)` | the 146,100 → 11,494 collapse |
| `open_geolocation(source, *, opener, timeout_s)` | AOP source → CMR → L1B → lazy geolocation; `opener` short-circuits both for tests |
| `geometry_for_granule(source, pixels, ...)` | **module-level, picklable** — runs in the worker, returns `(filled, mismatched)` |
| `build_geometry(store, ...)` | the stage: gather, fan out, write, summarise |

**Summary shape** — `failed` is granule-level, `mismatched` is pixel-level, and
neither aborts the stage:

```python
{"written": [pixel_id...], "skipped": [pixel_id...],
 "failed": [granule_id...], "mismatched": [(pixel_id, reason)...]}
```

**Idempotent.** Pixels with `theta_s` set are filtered out *before* any granule
is opened, so a resumed run does **zero** opens — there is a test asserting
exactly that, and another asserting a partial resume opens only the one granule
its missing pixel belongs to. `--replace` refills.

**Tests: 287 passed, 1 skipped** (was 267). 20 new in
`pab/tests/test_geometry.py`, offline:

- stage ordering, dry-run listing, `--stage geometry` parsing, and a run
  through the real `run()` seam-forwarding
- one open per **granule**, not per pixel (6 pixels / 2 granules → 2 opens)
- the right angles land, `dphi` wrapped, `geom_source` stamped
- resume does zero opens; partial resume opens exactly one granule; `--replace`
- **grid-check failure recorded, not raised** — the bad pixel is listed in
  `mismatched` and left NULL while its granule's other five pixels still fill
- non-finite angles recorded the same way
- one unreadable granule counted in `failed` without costing the other's pixels;
  all-granules-failing still returns a summary
- **serial and parallel agree** — same written set, same DB rows
- an unpicklable (closure) opener falls back to serial rather than failing
  every granule

The parallel test is real, not nominal: the stub opener is **module-level**, and
a `test_stub_opener_is_picklable` guard asserts that precondition. A closure
there would have made `picklable()` route to the serial path and the "parallel"
test would have silently tested nothing.

One design note: each worker bounds its **own** open via the SIGALRM guard in
`l1b.open_l1b_geolocation` (a worker's main thread *is* a main thread, so
`signal.alarm` works there). That is why this stage does not need `match`'s
chunk-and-kill stall machinery — the per-granule timeout is enforced where the
wedge would happen.


### Task 4 — local validation against live L1B (2026-09-15): **done, with one caveat**

Scratch copy made with `split_version.copy_database` (not `shutil.copy2`),
then pruned **in the scratch copy** to the 10 pilot `V3_2` granules — the
pipeline CLI has no `--matchup`/`--granule` filter yet, so pruning is how the
work list gets bounded. It landed exactly on the Context table's numbers:
**10 granules / 20 matchups / 200 pixels**, schema v5, 200 pixels with
`theta_s IS NULL`.

**Result: all 200 pixels filled, `geom_source = 'L1B_V3'` on every one, zero
range violations.**

| check | result |
|---|---|
| pixels filled (all four columns) | **200 / 200** |
| `geom_source` | `L1B_V3` (single distinct value) |
| `0 ≤ theta_s < 90` | **0 violations** — observed 16.13°–42.79° |
| `0 ≤ theta_v ≲ 60` | **0 violations** — observed 22.05°–59.66° |
| `-180 < dphi ≤ 180` | **0 violations** — observed −103.92°–81.92° |

Per-granule spreads are tight and physically coherent (e.g.
`20250309T131631`: `theta_s` 27.73–27.79, `theta_v` 59.45–59.56 across its 10
adjacent pixels; `20250625T030832`, whose 60 pixels span a much wider swath
range, spreads `theta_v` 22.05–52.11).

**Known-answer check: exact match**, run through the stage's own code path
(`geometry.open_geolocation` → `l1b.pixel_geometry`), not the unit test:

| | expected | got |
|---|---|---|
| `theta_s` | 29.47° | **29.47°** |
| `theta_v` | 54.58° | **54.58°** |
| `dphi` | 81.33° | **81.33°** |

at pixel `(868, 142)` of `PACE_OCI.20250309T131631` (lat/lon −32.34044,
−7.55775). **Note:** that pixel is *not* one of the matchup's own ten — the
matchup sits at `(1017–1022, 95–96)`, where the stage recorded `theta_v`
59.45–59.56 and `dphi` 81.90–81.92. The reference pixel was simply the one the
planning verification probed, so the anchor has to be checked explicitly
against that `(ix, iy)` rather than read out of the filled rows.

**Resume verified twice over.** A second run reported
`geometry: 60 pixels over 1 granules (140 pixels already filled)` — one open,
15.9 s — and a final run with everything filled reported
`nothing to do (200 pixels already filled)` in **1.0 s with zero opens**.

**Caveat — one granule failed transiently, twice.**
`PACE_OCI.20250625T030832` failed at the granule level on two serial runs
(recorded in `failed`, stage completed normally, other 140 pixels written) and
succeeded on every subsequent run, in isolation, and at `--jobs 4/8/16`. Its
L1B is structurally identical to the reference granule's (same six groups,
`latitude`/`longitude` present as *coords*, `(1709, 1272)`), and its CMR
resolve takes 1.7 s. So this is **network flakiness, not a data or code
defect** — and it is exactly the case the design handles: recorded, not
raised, and picked up by the next run because those pixels stayed NULL.

**Timings** (10 granules / 200 pixels, out-of-region, wall clock):

| jobs | wall | notes |
|---:|---:|---|
| 1 | **87.2 s** | good conditions → **8.7 s/granule**, 0 failures |
| 1 | 375–377 s | degraded window, 1 transient failure (twice) |
| 4 | 29.1 s | |
| 8 | 23.2 / 22.9 s | |
| 16 | 21.8 s | no gain — only 10 granules to spread |

**Projection for Prompt 5, stated honestly:** at ≥8 jobs the 10-granule sample
is floor-limited by one granule's latency plus ~4 s of startup, so it measures
*latency*, not throughput. The defensible number is the **serial 8.7 s/granule**
under good conditions. Scaling that across 11,494 granules:

| jobs | ideal-scaling estimate |
|---:|---|
| 1 | ~28 h |
| 8 | ~3.5 h |
| 16 | ~1.7 h |

with a **4× penalty** if the degraded window (37.5 s/granule serial) is
representative — i.e. 8 jobs could be anywhere from ~3.5 h to ~15 h. **Prompt 5
should re-measure on a few hundred granules**, which is the smallest slice that
actually measures parallel scaling rather than single-granule latency.

**`HOWTO.md`** gained the `geometry` row in the §4 stage table and a
**"`geometry` runs before `fit`, and that order matters"** rule covering why
the read is not folded into `fit`, the idempotency contract, and the
`failed`/`mismatched` distinction.

One cosmetic annoyance worth knowing: closing an L1B dataset emits
`Exception ignored while calling deallocator … TypeError: bad operand type for
unary ~: 'NoneType'` from `h5netcdf`/`h5py` during GC. It is uncatchable (it
happens in a finaliser), harmless, and does not affect results.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-14 (Prompt 2 Task 1 — schema v5: per-pixel geometry + RT provenance)

Bumped `SCHEMA_VERSION` to 5 with a single `_v4_to_v5` forward migration, and
applied it to `$PAB_DATA_DIR/v2/pab.db` (v4 → v5, 146,100 pixels × 4 new NULL
columns, 14,609 fits × 6). `v1/pab.db` verified untouched at every step.

The one real decision was **scope**: Task 1 offered to leave the `fits`
columns to Prompt 3. I put all ten in v5 instead, because splitting them is a
trap rather than a choice. `migrate()` looks up `MIGRATIONS[current]` and only
runs the step if the file is still at the starting version — so once
`v2/pab.db` is stamped `user_version = 5` by a pixels-only step, Prompt 3
adding `ALTER`s to the *same* `_v4_to_v5` function changes nothing for that
file. It is skipped, silently, and the missing columns surface much later as
an error at fit time. Recorded as Q1 with the escape hatch (a `_v5_to_v6`) if
JXP disagrees.

What I learned / want to remember:

- **"Extend the existing migration later" is never safe once any file has
  been migrated.** This is the general lesson, not just a v5 one: a version
  number is a claim about completeness, so a version must be defined in full
  before anything is stamped with it. I put that warning into
  `docs/db_schema.rst`'s Migrations section, since the next person to add a
  column will hit exactly this.
- **The freeze + the schema bump produced a real regression, and the grep
  found it.** `pab/pipeline.py:1016` opened the store with default
  `create=True` for `--emit-site`, which only ever reads. That was harmless
  while `SCHEMA_VERSION` was 4 (migrate is a no-op at the current version) and
  became a hard failure the moment it went to 5: regenerating the *published*
  1.0 site off `full/pab.db` would have died with `attempt to write a readonly
  database`. Fixed to `create=False` and checked against the real v1, not a
  fixture — all 8 site sources emitted, sha256 unchanged. Worth noting the
  bug was pre-existing and merely *latent*; the freeze exposed it. Warning #1
  in this doc was written from a simulation and turned out to under-state the
  blast radius: it is not only future `--compare-db` code, it was already
  shipped CLI behaviour.
- `ALTER TABLE ADD COLUMN` on a 120 MB SQLite file is metadata-only and
  instant — the file size did not change by a byte across ten columns and
  160,709 affected rows. No `VACUUM` or rewrite needed.
- Two existing tests pinned `SCHEMA_VERSION == 4` literally, and so did one I
  wrote in Prompt 1 (`test_seed_is_schema_v4`). All three now compare against
  `schema.SCHEMA_VERSION`. Pinning the literal makes every future bump a
  multi-file edit for no benefit — the tests that *should* pin a literal are
  the ones asserting a specific migration's behaviour, not "the store is
  current".
- Added `test_fresh_v5_database_matches_the_migrated_one`, which compares
  `create_all`'s DDL against the migration's result. The classic schema bug is
  adding a column to one path and not the other, so new databases and migrated
  ones diverge; that test makes it impossible to land.

### 2026-09-15 (Prompt 2 Task 2 — the L1B geometry reader)

Replaced the `pab/pace/l1b.py` stub with a real reader: AOP → L1B name swap,
CMR resolution to a download URL, a lazy `geolocation_data` open, and
`pixel_geometry` returning `(theta_s, theta_v, dphi)` behind a grid check. The
three stub symbols survive, so nothing that imported them breaks.

The part I care most about is that this is **verified against the real
granule, not just against my own fixtures**. The live test (env-gated,
`PAB_LIVE_L1B=1`) does the whole chain — CMR lookup, open, read — and
reproduces `theta_s = 29.47°`, `theta_v = 54.58°`, `dphi = 81.33°` at pixel
(868, 142) of `PACE_OCI.20250309T131631` to 0.01°, with the grid confirmed as
(1709, 1272). 12.8 s end-to-end. Offline, 31 tests cover the same code against
a synthetic geolocation dataset.

What I learned / want to remember:

- **"Wrapped to (−180, 180]" is a real specification, and the reflex
  implementation gets it wrong.** `((x + 180) % 360) − 180` produces
  **[−180, 180)** — the other end is open. For the documented range the form
  is `180 − ((180 − x) % 360)`, under which `−180` maps to `+180`. It only
  matters for exactly-antipodal azimuth pairs, which is precisely the kind of
  once-in-14,610 case that would be written off as noise later.
- **The same wrap is needed for the grid check itself.** My first cut compared
  longitudes with `abs(a − b)`, which reports 359.98° for two pixels 0.02°
  apart across the antimeridian — every such pixel would have raised
  `GridMismatchError` and been logged as a failure. The Pacific floats would
  have hit this. `_lon_delta` reuses `wrap_dphi`; there is a test pinning it.
- **The L1B filename drops the AOP's minor version.**
  `…L2.OC_AOP.V3_2.nc` → `…L1B.V3.nc`, not `…L1B.V3_2.nc`. Both `V3_1` and
  `V3_2` AOP granules map to the same `V3` L1B, which matters because the
  pilot directory holds both and the v2 matchups reference only `V3_2`.
- **The name swap alone is not enough, unlike the IOP case.** `iop.py` can get
  away with a pure string swap because AOP and IOP sit at the same DAAC path;
  the L1B collection does not, so the URL genuinely requires the CMR lookup.
  That is why `l1b_source_for_aop` takes a `search` seam — otherwise every
  test of it would need the network.
- Confirmed the documented CMR quirk first-hand: **each L1B granule is listed
  twice**. `_dedupe_by_name` keys by filename, which both deduplicates and is
  what the caller matches on.
- Rather than copy the SIGALRM guard, I gave
  `engine._open_with_timeout` an optional `open_fn`. It is a three-line change
  with the default path untouched, and it keeps one implementation of the
  "interrupt a read wedged in a C-level lock" trick — which the comments there
  say was hard-won against real 40-minute wedges.

### 2026-09-15 (Prompt 2 Task 3 — the `geometry` pipeline stage)

Added `pab/matchup/geometry.py` and made `geometry` a real stage between
`match` and `fit`. 20 new tests, 287 passing overall, docs still clean.

The stage exists to group by **granule**: 146,100 pixels sit on 11,494
distinct granules, so grouping turns 146,100 potential 1.8 GB opens into
11,494 — and keeping it out of `fit` means that cost is fanned out rather than
paid in `fit`'s serial parent loop.

What I learned / want to remember:

- **The stage wiring was almost free, by design.** `--stage`'s `choices=STAGES`
  and `run()`'s `plan = [s for s in STAGES if ...]` are both derived from the
  one tuple, so inserting `"geometry"` into `STAGES` and `_STAGE_FUNCS` gave
  the CLI flag, the dry-run listing, and the run order together. Worth noting
  for the next stage someone adds: don't hand-edit the CLI.
- **A "parallel" test with a closure opener tests nothing.** `build_matchups`
  established the contract that an unpicklable opener silently falls back to
  serial — which means a parallel test written with a lambda would pass while
  exercising only the serial path. I made the stub opener module-level and
  added `test_stub_opener_is_picklable` to pin the precondition, so the day
  someone refactors it into a fixture closure, that guard fails rather than the
  coverage quietly evaporating.
- **Failure granularity matters here and is easy to get wrong.** A granule
  either opens or it doesn't (that's `failed`, one entry per granule), but a
  *pixel* can fail its grid check while its nine siblings are fine (that's
  `mismatched`, per pixel). My first instinct was one `failed` list; that would
  have thrown away nine good pixels every time one had a bad stored position,
  and it would have made "did the granule fail, or one pixel?" unanswerable
  from the summary. The per-pixel `try` is inside `geometry_for_granule`, so
  the bad pixel is skipped and left NULL — a later `--replace` or a fixed
  position retries it.
- **This stage doesn't need `match`'s stall machinery.** `match` wraps work in
  chunks with a fresh pool and kills a chunk that goes quiet, because its
  granule reads could wedge with no timeout available. Here each worker bounds
  its own open with the SIGALRM guard inside `l1b.open_l1b_geolocation` —
  `signal.alarm` is main-thread-only, and a worker process's main thread
  qualifies. The bound is enforced at the point of the wedge, so the pool
  cannot sit dead. Simpler, and strictly better placed.
- `COALESCE(g.data_url, m.granule_id) AS source` reuses the convention
  `GranuleIndex` already established, so the stage matches what `match`
  actually opened rather than inventing its own source resolution. There is a
  test that a `data_url` overrides the id.

### 2026-09-15 (Prompt 2 Task 4 — validated the `geometry` stage against live PACE L1B)

Ran the stage end-to-end through the real CLI on a pruned scratch copy of
`v2/pab.db`, against **live** L1B reads. All 200 pixels of the 10 pilot
granules filled, `geom_source` stamped, every value physically sensible, and
the known-answer anchor reproduced exactly (29.47 / 54.58 / 81.33).

What I learned / want to remember:

- **The reference pixel is not in the matchup.** `(868, 142)` was the pixel the
  planning verification happened to probe; the matchup for that granule holds
  `(1017–1022, 95–96)`. So the "known-answer check" cannot be done by reading
  the filled rows — it has to target that `(ix, iy)` explicitly. I nearly
  reported the matchup's own `theta_v` 59.45 as a mismatch against the expected
  54.58 before noticing they are different pixels of the same granule. The
  values are mutually consistent (`dphi` 81.90 vs 81.33, `theta_v` varying with
  cross-track position), which is itself a decent sanity signal.
- **A granule failed twice, then stopped failing — and chasing it was worth
  it.** `PACE_OCI.20250625T030832` failed at the granule level on two serial
  runs. I did not write it off: I checked its CMR resolve (1.7 s, fine), opened
  its L1B directly (9.4 s, fine), compared its group structure against the
  reference granule (identical — six groups, `(1709, 1272)`), and re-ran its 60
  pixels through `geometry_for_granule` (60 filled, 0 mismatched). It is
  network flakiness. Worth the detour, because the alternative explanation —
  some granules genuinely lack geolocation — would have changed the design.
- **`latitude`/`longitude` are xarray *coords*, not `data_vars`.** My first
  diagnostic printed `list(ds.data_vars)` and showed no lat/lon, which looked
  exactly like "this granule has no geolocation" and sent me down the wrong
  path for a few minutes. `sorted(ds.variables)` is the honest listing. Worth
  remembering for any future "the variable is missing" moment with these files.
- **Small samples measure latency, not throughput.** At `--jobs 8` and `16` the
  10-granule run is floor-limited by one granule's latency plus interpreter
  startup — 23 s and 22 s are indistinguishable, and 16 workers for 10 granules
  is meaningless. I reported the serial per-granule figure (8.7 s) as the
  projection basis and flagged that Prompt 5 should re-measure on a few hundred
  granules. Quoting "23 s for 10 granules → 7 h for 11,494" would have been a
  number with no support behind it.
- **Out-of-region L1B latency varies by more than 4×**: the same 10 granules
  took 87 s and 375 s on different serial runs, half an hour apart. Any
  projection for the full run needs that spread attached to it, not a single
  point estimate.
- The pipeline CLI still has no `--matchup`/`--granule` filter (it is in
  HOWTO's "Planned enhancements"), so bounding a validation run means pruning a
  scratch copy. That worked fine, but it is the second time the missing filter
  has cost a workaround; worth implementing if a third comes up.
