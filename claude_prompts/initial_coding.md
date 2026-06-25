# Coding up PAB - First Major Pass

## Goals

We will now perform the first major pass of coding up PAB.  We will use the design document `docs/design/PAB_design.md` and the coding plan `docs/design/PAB_coding_plan.md` to guide our work.

## Claude

### Skills

Consider using the skills in .claude/skills/

## Context

Examine the following files that may help generating the design:

- The code and files in the BING Repository: https://github.com/ocean-colour/BING.  In particular all of the files in the papers/biomass folder.
- The BING paper: docs/PDFs/bing.pdf
- The Bisson et al. papers in docs/PDFs/
- The argopy documentation: https://argopy.readthedocs.io/en/stable/
- Documentation on the PACE website for:
  - the granules (Level 2 products) and
  - how to process their data in the cloud
  - any APIs to extract individual spectra instead of full granules (might also need to be done in the Cloud)
- The context.md file in this repository: docs/context.md
- The coding plan document: docs/design/PAB_coding_plan.md
- The design document: docs/design/PAB_design.md

## Prompts

### Stages

1. Read this doc. Execute the 1st task in the Stage 0 section below.
2. Read this doc. Execute the 1st task in the Stage 1 section below.

3. Read this doc. Execute the 1st task in the Stage 2 section below.
4. Read this doc. Execute the 2nd task in the Stage 2 section below.
5. Read this doc. Execute the 3rd task in the Stage 2 section below.

6. Read this doc. Execute the 1st task in the Stage 3 section below.

7. Read this doc. Execute the 1st task in the Pull Request section.
8. Read this doc. Execute the 2nd task in the Pull Request section.
9. Read this doc. Execute the 3rd task in the Pull Request section.
10. Read this doc. Execute the 4th task in the Pull Request section.
11. Read this doc. Execute the 5th task in the Pull Request section.

12. Read this doc. Execute the 1st task in the Stage 4 section below.

## Stage 0

### Tasks

1.  Read the context files. Proceed with the coding.  Begin with Stage 0.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

### Q&A

## Stage 1

1.  Read the context files. Proceed with the coding.  Begin with Stage 1.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

## Stage 2

1.  Read the context files, especially the design document and the coding plan. Proceed with Stage 2.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

2.  I should have requested from the start that you also create an Implemntation file to record your work.  Please do so now.  Call it `docs/design/PAB_implementation.md`.

3. I have updated the coding plan to request Jupyter Notebooks to be created for each stage.  Please create them now.  Put them in `docs/nb`.

### Q&A

## Stage 3

1.  Read the context files, especially the design document and the coding plan. Proceed with Stage 2.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

### Q&A

## Stage 4

1. Based on this doc, generate a prompt doc for Stage 4.  Please:

    - Call it `claude_prompts/coding_stage4.md`.
    - Log your work


## Pull Request

1. I have decided to issue a PR at this point.  And I have.  It is this one:

https://github.com/ocean-colour/PAB/pull/1

Please review it and transmit your comments onto GitHub.

2. Check the comments on the PR and make any necessary edits.  And:

   - If you have any additional questions, write them in the Q&A section below.
   - Report the specific changes you made to the PR in the Report section below.
   - Log your work in the Logs section below.

3. I wish to expose this package on readthedocs.io.  Please:

   - Create the files needed to build the documentation on readthedocs.io.
   - If you need to add new dependencies, please add them to the requirements.txt file.
   - I will do the plumbing on readthedocs.io.

4. Nice docs.  You can see them here at https://pab.readthedocs.io/en/design/argo_ingestion.html. Please:

   - Have links to the Argo notebooks from the Argo ingestion page (https://pab.readthedocs.io/en/design/argo_ingestion.html)


5. Do a pass on all of the code, design documents and documentation to ensure that it is all in sync.  I will then finish the PR.


### Report

Acted on the PR #1 review comments. Changes made (local; pending your push to
`design`):

1. **`pab/pace/discover.py` — fixed the `cloud_cover` bug.** `persist_granules`
   now maps the *real* `remote_sensing.build_granule_table` columns
   (`id`/`polygon`/`time`/`CC`/`url`) onto the schema, with the schema-native
   names accepted as a fallback. Added a `_first()` helper that picks the first
   non-`None` value (so a valid `CC == 0.0` is preserved, not dropped by an
   `or`-chain).
2. **`pab/tests/test_pace.py` — corrected the test.** It now uses the real
   `build_granule_table` column names and asserts `cloud_cover` is captured
   (including 0%), `time → time_start`, and `url → data_url`; added a second
   test that the schema-native-column fallback path still works. (The old test
   passed only because it shared the code's wrong column assumptions.)
3. **`pab/pace/cloud.py` — hardened the S3 read.** Replaced the triple
   `xr.open_dataset(fileobj, group=…)` with a single
   `xr.open_datatree(source, engine="h5netcdf", mask_and_scale=True)` (renamed
   `_read_datatree` → public `read_datatree`), and included `FLH`/`nflh` when
   present so the S3 and local backends produce the same canonical dataset.
4. **`.github/workflows/ci.yml` — lean test job.** The pytest job now installs
   `numpy scipy pandas pyarrow xarray gsw matplotlib pytest` + `pip install -e .
   --no-deps` instead of the full `requirements.txt`, so it no longer pulls
   argopy/earthaccess/bokeh/healpy; optional-dep tests `importorskip` and skip.
5. **`setup.py` — removed deprecated keys** (`use_2to3`,
   `setup_requires=['pytest-runner']`, `tests_require`).
6. **`pab/db/schema.py` — typing nit:** `MIGRATIONS` now typed
   `dict[int, Callable[[sqlite3.Connection], None]]`.
7. **xarray exact pin** — already resolved by you (unpinned in
   `requirements.txt`); replied to the thread.

Posted resolution replies on all five GitHub review threads. Verification after
the edits: `pytest` → **60 passed**; `ruff check`/`format` → clean;
`sphinx-build -W` → succeeded; `python setup.py --version` → `0.0.dev0` (parses
without the removed keys). Implementation record bumped to **v0.2.1**.

### Q&A

- **Notebook outputs:** I left the committed notebooks with their executed
  outputs (worked-example style). If you'd prefer them output-stripped to keep
  diffs/repo smaller, say so and I'll strip them (or add an `nbstripout` hook).
- **`requirements.txt` as single source vs. lean CI:** the CI test job now
  installs an explicit lean subset rather than deriving it from
  `requirements.txt`. If you'd rather formalize this, I can add an
  `extras_require={'test': [...]}` to `setup.py` and have CI use
  `pip install -e .[test]`. Left as-is for now to avoid changing the packaging
  model mid-PR.
- **Read the Docs slug (task #3):** I assumed the RTD project slug is `pab`, so
  the README badge/link point at `https://pab.readthedocs.io`. If you register a
  different slug on readthedocs.io, update the two URLs in `README.md`
  accordingly. Also: RTD installs the *full* `requirements.txt`; since only
  numpy/xarray/matplotlib are imported at module load (everything heavier is
  mocked in `conf.py`), I can switch RTD to a lean `docs/requirements.txt` if
  you'd prefer faster/sturdier builds — left on the single-source path for now
  per your instruction to keep deps in `requirements.txt`.

## Logging

The "Logs" section will record Claude's work.  Please use the following format:

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>

...

## Logs

### 2026-06-19 (Stage 0 — scaffolding & infrastructure)

Read the context files (`docs/design/PAB_design.md` v0.3.1,
`docs/design/PAB_coding_plan.md` v0.1.1, `docs/context.md`) and executed
**Stage 0** of the coding plan: package skeleton, config + `pab_version`, test
harness, Sphinx docs skeleton, dependency pinning, and CI.

Delivered:

- **Package skeleton** matching the §2 module map — importable subpackage
  stubs `pab.{db,argo,pace,matchup,fit,metrics,plotting,report}` (each an
  `__init__.py` docstring naming its future role and the stage that fills it in)
  plus `pab/pipeline.py`. `find_packages()` now discovers all 10 subpackages.
- **`pab/config.py`** exposing `pab_version = "0.0.dev0"` (distinct from the
  packaging version in `setup.py`), `ROOT`/`DATA_DIR` paths (env-overridable
  via `PAB_ROOT`/`PAB_DATA_DIR`), and `package_versions()` for provenance — it
  reports versions for pab/bing/ocpy/argopy/remote_sensing/earthaccess/
  numpy/scipy/xarray and degrades to `"not installed"` rather than raising.
  `pab/__init__.py` re-exports `pab_version` as `__version__`.
- **Tests** (`pab/tests/test_smoke.py`): parametrized import smoke test over all
  subpackages, `pab_version` presence/type, and `package_versions()` shape.
  `pytest.ini` collects from `pab/tests`. 13 tests pass.
- **Docs** (`docs/conf.py`, `index.rst`, `dev_setup.rst`): Sphinx site reusing
  the existing `docs/` tree, with napoleon (Google docstrings), myst-parser
  (renders the Markdown design/context docs), and sphinxcontrib-mermaid (the
  design's mermaid diagrams). `autodoc_mock_imports` and `suppress_warnings`
  keep the build green without the heavy optional deps. Builds clean under
  `sphinx-build -W`.
- **Dependency pinning**: added sphinx/sphinx-rtd-theme/myst-parser/
  sphinxcontrib-mermaid and ruff to `requirements.txt` (still the single source
  of deps; the special-source packages bing/ocpy/remote_sensing stay as
  comments). Added `ruff.toml`.
- **CI**: `.github/workflows/ci.yml` runs pytest and a `-W` docs build on every
  push/PR; `.readthedocs.yaml` for the RTD build.

Verification: `pytest` → 13 passed; `sphinx-build -W` → build succeeded;
`ruff check pab` and `ruff format --check pab` → clean.

What I learned: the workstation already has bing/ocpy/remote_sensing/argopy/
earthaccess installed, so later stages can import them directly — but CI and the
Stage 0 smoke test deliberately do **not** require them (CI installs only the
package + pytest; the docs build mocks them). Python here is 3.14.5 (plan
floor is 3.12). No questions for the Q&A section — Stage 0 scope was
unambiguous.

### 2026-06-19 (Stage 1 — database layer / the storage seam)

Executed **Stage 1** of the coding plan: the SQLite schema, a thin access API,
CSV/Parquet export, and a forward-migration mechanism — all on the standard
library `sqlite3` (no ORM), per the plan.

Delivered:

- **`pab/db/schema.py`** — DDL for the four entity groups the design calls for:
  `floats`/`profiles`, `mld_summary` (1:1 per-profile mixed-layer summary),
  the matchup index (`granules`, `matchups`, `matchup_pixels`), and the
  namespaced fit results (`fits` + `fit_results`). Plus `SCHEMA_VERSION`
  (stored in `PRAGMA user_version`), an `UPSERT_KEYS` map (natural key per
  table), `create_all()`, `get_version()`, and a `migrate()` that initialises a
  fresh DB and steps an existing one forward through a `MIGRATIONS` registry
  (empty for v1; mechanism in place).
- **`pab/db/store.py`** — a `Store` class (context-manager, `Store.open(path)`
  with `foreign_keys=ON` and `Row` factory) exposing `insert`, idempotent
  `upsert`/`upsert_many` (INSERT … ON CONFLICT keyed by the table's natural
  key), `query`/`query_df`/`table_df`/`count`, `export_csv` (stdlib `csv`, no
  pandas dep) and `export_parquet` (pandas/pyarrow), and `fit_results_wide()`
  which pivots the long `fit_results` rows into wide namespaced columns
  (`BING_ExpBPow_bbp` + `_lo`/`_hi`). `pab/db/__init__.py` re-exports
  `Store` and `schema`.
- **Tests** (`pab/tests/test_db.py`, 13 new): schema version + table presence,
  create idempotency, insert→query round trip, idempotent upsert keyed by
  matchup ID (no duplicate; updates in place), non-key updates, missing-key /
  unknown-table errors, FK enforcement, UNIQUE enforcement, CSV export equals
  query, Parquet round trip, and the long→wide fit-results pivot. **26 tests
  pass overall.**
- **Docs** — `docs/db_schema.rst` (schema reference: every table with columns,
  units, keys, FKs; the migrations approach; autodoc of `Store`/`schema`),
  added to the index toctree. `requirements.txt` gains `pyarrow` for Parquet.

Verification: `pytest` → 26 passed; `ruff check`/`format` → clean;
`sphinx-build -W` → build succeeded.

Design decision worth recording: I stored the fit IOP results in a **long**
`fit_results` table (`fit_id, quantity, value, value_lo, value_hi, unit`) rather
than wide per-model columns. The design describes namespaced columns
(`BING_ExpBPow_bbp`, a parallel `BING_GIOP_bbp`, etc.); long format delivers the
same namespacing while keeping the table schema stable as model pairs are added
(new pair → new rows, not `ALTER TABLE`). `Store.fit_results_wide()` reconstructs
the wide, namespaced view for export/reporting — so the design's column naming is
honoured at the export boundary. No questions for Q&A.

### 2026-06-20 (Stage 2 — BGC-Argo ingestion & mixed-layer summary)

Executed **Stage 2**: the BGC-Argo side of the pipeline — argopy fetch, QC
filtering, MLD, de-spike, mixed-layer averages, DB persistence, and Q&A plots.
The science functions operate on plain arrays so they unit-test offline (no
network); the argopy fetch is a thin, lazily-imported seam.

Delivered (`pab.argo`):

- **`mld.py`** — de Boyer Montégut density-threshold MLD. `mixed_layer_depth()`
  is pure NumPy (shallowest depth below a 10 m reference where `SIG0` exceeds
  the reference value by 0.03 kg m⁻³; handles unsorted/NaN/too-shallow/
  unresolved → `nan`). `density_sigma0()` derives `SIG0` from T/S via TEOS-10
  (`gsw`, matching argopy's `teos10`), and `mixed_layer_depth_from_ts()` chains
  them. Constants `MLD_METHOD="deBoyerMontegut_0.03"`, `REF_DEPTH`, `THRESHOLD`.
- **`summary.py`** — `moving_median()`/`despike()` (3-pt moving median),
  `iqr_inlier_mask()` (log-space 1.5×IQR outlier removal), `mixed_layer_mean()`
  (mean/std/n within `pres <= mld`, optional de-spike + IQR), `summarize_profile()`
  (assembles the `mld_summary` fields), and `persist_summary()` (idempotent
  upsert of `floats`/`profiles`/`mld_summary`, stamps `created`+`pab_version`,
  returns `profile_id`).
- **`fetch.py`** — `build_fetcher()` (BGC `DataFetcher`, `ds='bgc'`,
  `src='erddap'`), `fetch_region/float/profile()`, `filter_quality()` (QC +
  research mode), and `iter_profiles()` (point2profile → per-profile metadata +
  arrays, the bridge to `summarize_profile`). argopy imported lazily.
- **`qa.py`** — `plot_profile()`/`save_profile_qa()`: `BBP700`/`CHLA` vs
  pressure with the de-spiked overlay and MLD line.

Tests (`pab/tests/test_argo.py`, 17 new — **43 pass overall**): MLD known-answer
+ custom-threshold + nan edge cases + unsorted/NaN handling + T/S-path
agreement; de-spike removes an injected spike but preserves a real step;
even-window rejected; mixed-layer mean correctness + nan-MLD; IQR drops an
outlier; `summarize_profile` end-to-end (MLD=40, spike de-spiked, correct
n_points/means); lon/lat-required guard; **summary row persisted** + idempotent
re-persist; `build_fetcher` returns a BGC `DataFetcher` (no network); Q&A PNG
produced.

Docs: `docs/argo_ingestion.rst` (pipeline overview, MLD method note citing de
Boyer Montégut 2004 + Bisson 2019, de-spike/average note, autodoc of all four
modules), added to the index toctree.

Verification: `pytest` → 43 passed; `ruff check`/`format` → clean;
`sphinx-build -W` → build succeeded.

Notes / learnings: argopy exposes no public MLD accessor — its internal
`utils/optical_modeling.py::MLD_Func` confirms the same gsw `SA_from_SP →
CT_from_t → sigma0` recipe and the 0.03 kg m⁻³ threshold I implemented. I kept
the matplotlib backend unforced (qa.py imports `pyplot` without `use("Agg")`):
Matplotlib auto-selects Agg when headless, so importing `pab.argo` no longer
drags a forced backend onto interactive users. The fetch wrappers are
network-bound and therefore not exercised in the offline suite (only construction
is tested) — they'll get real coverage once Stage 4 wires a tiny fixture. No
questions for Q&A.

### 2026-06-20 (Implementation record document)

Per the new Stage 2 task #2, created
[`docs/design/PAB_implementation.md`](../docs/design/PAB_implementation.md) — a
living **implementation record** that complements the design doc (*what/why*)
and coding plan (*how/when*) by documenting *what was actually built*. v0.1.0
covers Stages 0–2: a status-at-a-glance table, per-stage module/API breakdowns,
the implementation decisions taken (e.g. the long `fit_results` table, the
unforced matplotlib backend), test/doc coverage per stage, cross-cutting
conventions as implemented, and a current module index. Distinct from this Logs
section: the log is dated narrative, the implementation doc is the structured
current-state reference, to be updated at the close of each stage. Added it to
the docs `Design` toctree; `sphinx-build -W` stays green.

### 2026-06-20 (Per-stage explanatory notebooks)

Per the new Stage 2 task #3 (the coding plan now requests Jupyter notebooks per
stage), created explanatory notebooks in `docs/nb/` for the three implemented
stages:

- **`00_getting_started.ipynb`** (Stage 0) — package import, `pab_version`,
  config paths (`ROOT`/`DATA_DIR`), `package_versions()`, and the subpackage
  map.
- **`01_database_layer.ipynb`** (Stage 1) — `Store` create → upsert → query →
  export (CSV/Parquet), idempotency, and the long→wide namespaced fit-results
  pivot, on an in-memory DB.
- **`02_argo_mld_summary.ipynb`** (Stage 2) — MLD (de Boyer Montégut, both the
  pure-density and T/S paths), `BBP700` 3-pt de-spike (with plot), whole-profile
  `summarize_profile`, DB persistence, and a `qa.plot_profile` figure; ends with
  an **optional `RUN_LIVE`** section that pulls a real profile via argopy.

Built them programmatically with `nbformat` (valid nbformat-4 JSON), then
executed each with `jupyter nbconvert --execute --inplace` so they carry their
outputs and are verified runnable — all three execute end-to-end **offline**
(0 error outputs; the Stage 2 live-data cell is guarded by `RUN_LIVE = False`).
Updated `docs/nb/README.md` (available vs planned list + re-run command) and
recorded the notebooks in `PAB_implementation.md` (now v0.1.1).

Build note: a stray `docs/nb/README.md` (a `.md` picked up by myst-parser) had
started tripping the `-W` "not in any toctree" check, so I added `nb` to
`exclude_patterns` in `docs/conf.py` — the notebooks are standalone runnable
deliverables, not yet rendered into the Sphinx site (that would need
`myst-nb`/`nbsphinx`, neither installed; rendering is an optional future step
per the plan). `sphinx-build -W` is green again; `pytest` → 43 passed
(no code changed). No questions for Q&A.

### 2026-06-20 (Stage 3 — PACE access & spectrum extraction)

Executed **Stage 3**: the satellite side — cloud-first granule access and
nearest-unflagged-pixel `Rrs` extraction. Screening/extraction are
array/xarray-only (offline-testable against a synthetic granule); discovery and
the S3 read are lazily-imported, network-bound seams.

Delivered (`pab.pace`):

- **`flags.py`** — self-contained `l2_flags` decoding: `L2_FLAG_BITS` (canonical
  SeaDAS/OB.DAAC positions, matching `remote_sensing.netcdf.oc.L2_FLAGS`),
  `STANDARD_OCEAN_MASK` (design screen), `flag_value`/`decode`/`is_set`/
  `flagged_mask`/`good_mask`.
- **`extract.py`** — `haversine_km`, `nearest_valid_pixels` (~10 nearest
  *unflagged* pixels w/ ix/iy/lat/lon/distance/rank/flag), `extract_spectrum`,
  `extract_matchup_spectra` (pixels + spectra; the Stage 4 input), and
  `pace_noise_vector` (wraps `ocpy.satellites.pace.gen_noise_vector`).
- **`cloud.py`** — the swappable backend producing a **canonical granule ds**
  (dims `(x,y,wl)`: Rrs/Rrs_unc; 2-D lat/lon; wavelength; l2_flags):
  `to_granule_ds`, `open_local` (ocpy), `open_s3` (lazy in-region via
  `earthaccess.open` + grouped netCDF), and `open_granule(source, backend, opener)`
  dispatching auto/s3/local (opendap reserved → NotImplementedError). The
  `opener` arg is the test seam that mocks the cloud.
- **`discover.py`** — `search_granules` (earthaccess CMR), `granule_table`
  (remote_sensing `build_granule_table`), `persist_granules` (idempotent upsert
  into `granules`).
- **`l1b.py`** — documented future hook: `rrs_from_l1b` raises; provenance tags
  `L2_AOP` vs `PAB_L1B`.

Tests (`pab/tests/test_pace.py`, 16 — **59 pass overall**): flag value/decode/
masks vs known bits; haversine ≈111 km/deg; nearest-pixel selection; nearest
**skips a flagged** pixel; spectrum values; matchup-spectra attachment;
all-flagged→empty; `to_granule_ds`; `open_granule` via injected opener +
opendap/unknown-backend errors; idempotent `persist_granules`; noise-vector
length; L1B stub raises.

Docs: `docs/pace_access.rst` (pipeline, canonical dataset, **lazy-S3 (a) vs
OPeNDAP (b)** trade-off, the `l2_flags` screen, L2-vs-L1B Rrs source), in the
toctree. Notebook: `docs/nb/03_pace_access.ipynb` (offline flag/extraction demos
+ optional `RUN_LIVE` earthaccess discovery; executed, 0 errors). Implementation
record bumped to **v0.2.0** (Stage 3 section + module index + status).

Verification: `pytest` → 59 passed; `ruff check`/`format` → clean;
`sphinx-build -W` → build succeeded.

Key decision: both readers normalise to one **canonical granule dataset**, so
nearest-pixel extraction is source-agnostic — only the data source differs
(lazy-S3 / local / future OPeNDAP). `open_granule`'s `opener` seam makes the
cloud read trivially mockable, which is how the suite stays offline. I reused
ocpy's L2 dataset shape (dims `x,y,wl`; lat/lon coords; separate `l2_flags`) and
implemented `flags` self-contained (mirroring `remote_sensing` bit positions) so
the QC is testable without importing remote_sensing. No questions for Q&A.

### 2026-06-20 (Reviewed PR #1 and posted comments to GitHub)

Per the Pull Request task, reviewed
[PR #1](https://github.com/ocean-colour/PAB/pull/1) ("Design, planning and
Stages 0–3"; design → main) and posted a single COMMENT review with a summary
body + 5 inline comments
([review](https://github.com/ocean-colour/PAB/pull/1#pullrequestreview-4537885027)).
Confirmed the PR head (`origin/design` @ "stage 3") matches local HEAD, so the
review covers all Stage 0–3 code as merged.

Findings (verified before posting, not taken on faith):

- **Correctness bug** — `pace.discover.persist_granules` drops `cloud_cover`.
  Read the actual `remote_sensing.build_granule_table` source: it emits columns
  `id` / `polygon` / `time` / **`CC`** / `url`, but the mapping looks for
  `cloud_cover`, so it's always stored `NULL`. The unit test passed only because
  it used a hand-built frame with the wrong column names — the test encodes the
  same wrong assumption as the code. (This is the headline finding; I'll fix it
  in Stage 4 when matchup wires real discovery, unless asked sooner.)
- **Robustness** — `cloud._read_datatree` opens the same file object 3× (risky
  on the untested lazy-S3 path) and omits `FLH` that `open_local` includes
  (backend-dependent canonical ds).
- **CI/packaging** — the `test` job `pip install -e .` pulls the whole heavy
  stack (healpy/bokeh/argopy/…) though the offline suite needs far less
  (suggest `extras_require[test]`); only `xarray` is pinned exactly while the
  rest float; `setup.py` keeps deprecated `use_2to3`/`pytest-runner`/
  `tests_require` (setuptools 81 here ignores them).
- **Minor** — notebooks committed with embedded outputs; the `export_csv`
  table-vs-SQL `' ' in arg` heuristic; `MIGRATIONS` typed with `"callable"`.

Verified locally: `setuptools.__version__ == 81.0.0`; read `build_granule_table`
to confirm its real column names. The review was framed as COMMENT (not
REQUEST_CHANGES) since these are my own commits and the user is driving merge
decisions. No questions for Q&A.

### 2026-06-20 (Addressed PR #1 review comments)

Per Pull Request task #2, re-read the PR #1 comment threads and made the edits.
The user had already resolved the xarray-pin comment (unpinned `xarray` in
`requirements.txt`, replied "modified"); I actioned the remaining five.

Edits (local, pending the user's push to `design`):

- **Correctness fix** — `pace.discover.persist_granules` now maps the real
  `build_granule_table` columns (`id`/`polygon`/`time`/`CC`/`url`) → schema,
  with schema-native fallbacks, via a `_first()` helper that preserves
  falsy-but-valid `CC == 0.0`. Corrected `test_pace.py` to use the real column
  names (it previously shared the bug's wrong assumption) and added a
  fallback-path test → suite now **60 passed**.
- **Robustness** — `pace.cloud` S3 read switched to a single
  `xr.open_datatree(engine="h5netcdf")` (was three opens of one handle) and now
  includes `FLH`; `_read_datatree` → public `read_datatree`.
- **CI** — pytest job installs a lean dep set + `pip install -e . --no-deps`
  (no more argopy/bokeh/healpy for unit tests).
- **Packaging** — dropped deprecated `setup.py` keys (`use_2to3`,
  `pytest-runner`, `tests_require`).
- **Nit** — `schema.MIGRATIONS` typed with `collections.abc.Callable`.

Posted resolution replies on all five GitHub review threads. Filled the doc's
Report + Q&A sections; bumped the implementation record to v0.2.1 (verification
line → 60 passed; discovery note updated). Verification: `pytest` → 60 passed;
`ruff` → clean; `sphinx-build -W` → succeeded; `setup.py --version` parses.

Two items raised in Q&A for JXP (non-blocking): whether to strip notebook
outputs, and whether to formalize the lean CI deps as an `extras_require[test]`.

### 2026-06-20 (Read the Docs setup)

Per Pull Request task #3 (expose on readthedocs.io), finalized the RTD build
files. The core file — `.readthedocs.yaml` — already existed from Stage 0; I
verified and hardened it, and made the docs discoverable:

- **`.readthedocs.yaml`** — RTD v2 config: `build` ubuntu-24.04 / Python 3.12;
  `sphinx.configuration: docs/conf.py`; installs the package (`path: .`) +
  `requirements.txt`. Documented why `fail_on_warning: false` (CI's `-W` is the
  strict gate; keep RTD lenient so a stray env warning doesn't block
  publication) and that the heavy sci deps are mocked in `conf.py`.
- **`README.md`** — added CI + Read the Docs badges and a **Documentation**
  section linking to `https://pab.readthedocs.io` plus local build instructions.

No new dependencies were required: the Sphinx stack (sphinx, sphinx-rtd-theme,
myst-parser, sphinxcontrib-mermaid) has been in `requirements.txt` since Stage 0,
so nothing was added.

What I checked: across `pab/` the only **module-load** third-party imports are
`numpy`, `xarray`, and `matplotlib`; every heavier package (gsw, argopy,
earthaccess, ocpy, bing, remote_sensing, healpy, bokeh) is imported lazily or
listed in `autodoc_mock_imports` — so the RTD autodoc build is light and robust.
`sphinx-build -W` → build succeeded (exit 0). The user does the readthedocs.io
plumbing. Q&A: flagged the assumed RTD slug (`pab`) and offered a lean
`docs/requirements.txt` alternative if they want faster RTD builds.

### 2026-06-20 (Render notebooks into the docs + link from the Argo page)

Per Pull Request task #4 (link the Argo notebooks from the Argo ingestion page),
I rendered the notebooks **into** the Sphinx/RTD site so the links resolve
on-site rather than 404-ing (the notebooks were previously excluded from the
build). Integrated `myst-nb`:

- **`requirements.txt`** — added `myst-nb`.
- **`docs/conf.py`** — load `myst_nb` instead of `myst_parser` (myst-nb bundles
  it; loading both conflicts); register `.ipynb` (and `.md`) → `myst-nb`; set
  `nb_execution_mode = "off"` so the build uses the **committed** outputs (no
  re-execution, so the `RUN_LIVE` network cells stay dormant). Un-excluded
  `docs/nb/` from the source, excluding only `nb/README.md` (a repo-facing
  index, not a docs page).
- **`docs/index.rst`** — added a *Notebooks* toctree listing all four notebooks
  (so they get pages and no orphan warning under `-W`).
- **`docs/argo_ingestion.rst`** — added a "Worked-example notebooks" admonition
  near the top with `:doc:` links to ``nb/02_argo_mld_summary`` (the Argo MLD/
  summary notebook) and ``nb/00_getting_started``.
- **`.github/workflows/ci.yml`** — added `myst-nb` to the docs-job install line.
- **`PAB_implementation.md`** → v0.2.2 (Notebooks note updated: now rendered via
  myst-nb).

Verified: `sphinx-build -W` → build succeeded (exit 0); the notebook HTML pages
(`nb/00..03.html`) are generated and `argo_ingestion.html` links resolve to
`nb/02_argo_mld_summary.html` and `nb/00_getting_started.html`; matplotlib
outputs render from the stored cells. `pytest` → 60 passed (no code changed).
The page the user cited (`/en/design/argo_ingestion.html`) will show the links
on the next RTD build of the `design` branch. No questions for Q&A.

### 2026-06-20 (Sync pass over code + design docs + documentation)

Per Pull Request task #5, audited the whole tree for drift before the PR is
finished. Found and fixed three real inconsistencies introduced by the recent
PR-review and notebook-rendering edits:

1. **`docs/dev_setup.rst`** — the docs-build install line omitted `myst-nb`
   (added in task #4). Added it and a note that notebooks render from committed
   outputs (`nb_execution_mode = "off"`).
2. **`docs/design/PAB_implementation.md` (→ v0.2.3)** — the "Environment notes"
   still said *"CI installs the package + pytest"*; updated to describe the
   actual two-job CI (lean **test** job with `--no-deps` + a `-W` **docs** job).
3. **Same doc, §5.3** — the `open_s3()` description said *"+ grouped netCDF"*;
   updated to the current single `read_datatree()`/`xr.open_datatree` read that
   also includes `FLH`.

Checked and found **consistent** (no change needed): the coding-plan `pace`
module list matches `pab/pace/` (`cloud/discover/extract/flags/l1b`); every
`automodule`/`autoclass` target in the `.rst` pages resolves (the `-W` build is
green); the implementation-doc module index and status table match the files on
disk; no stray `TODO`/`FIXME`; the only `NotImplementedError`s are the
intentional L1B hook and the reserved OPeNDAP backend; the Stage 4–8
subpackages are still stubs, matching their "pending" status.

**One observation (left for JXP, not edited):** `CLAUDE.md` still points to
`claude_prompts/start_up.md` as *the* work log, but the Stage 0–3 logs live in
`claude_prompts/initial_coding.md` (per this doc's own per-task instruction).
Both prompt docs carry a Logs section; if you want CLAUDE.md to generalize the
log location, say so and I'll update it (it's your instruction file, so I left
it untouched).

Final verification: `pytest` → **60 passed**; `ruff check`/`format` → clean;
`sphinx-build -W` → succeeded (exit 0). Everything is in sync and ready for you
to finish the PR.

### 2026-06-20 (Generated the Stage 4 prompt doc)

Per Stage 4 task #1, wrote `claude_prompts/coding_stage4.md` — a standalone
prompt doc for the **matchup engine**, modeled on the structure of
`initial_coding.md` (Goals / Claude / Context / Prompts / Stage section with
Tasks + Q&A / Logging / Logs). It expanded the one-line stub already in the repo.

The doc captures, for Stage 4:
- **Scope** distilled from the coding plan §4 and the design's *Matchup* section
  + Bisson recipe (5×5 unflagged pixel box, configurable `dtime` window, nearest
  valid granule selection, deterministic `matchup_id`, idempotent/resumable
  writes).
- **The seams it builds on** — `pab.db` (`matchups`/`matchup_pixels` already in
  the schema), `pab.pace.cloud.open_granule` (with the `opener=` test seam),
  `pab.pace.extract.*`, `pab.pace.discover` (granule candidates), and `pab.argo`
  (qualifying profiles).
- **Deliverables / offline tests / docs page / notebook**, plus an explicit
  **"definition of done"** encoding the Stage 0–3 standard (green
  pytest/ruff/`sphinx-build -W`; Google docstrings; provenance stamps; update
  `PAB_implementation.md` + bump its version; per-stage notebook rendered via
  myst-nb; log the work).
- Working agreements restated (git handled by the user; Python only; reuse not
  reinvent).

No code or package files changed; this task only authored the prompt doc.
Logged here per the instruction. No questions for Q&A.

### 2026-06-22 (Stages 4–6 built; corrected the Chl/Aph misconception)

Stages 4 (matchup engine), 5 (BING fitting wrapper), and 6 (metrics & figures)
were implemented, reviewed (PRs #2/#3), and logged in detail in their per-stage
docs (`claude_prompts/coding_stage{4,5,6}.md`); the implementation record is at
v0.5.1 and the suite is **89 passed, 2 skipped** (the two tests needing BING's
Loisel data file skip when it is absent), `ruff` + `sphinx-build -W` clean.

This entry records the most recent step — JXP's Stage 6 Task 2 correction. I had
wrongly treated `Chl` as a fixed **input** to the `ExpBPow` fit. In fact `Aph` is
a free parameter and BING **retrieves** Chl from it (`Chl = 10**Aph / 0.05582`
for the Bricaud family); the input `Chl` only *seeds* the `a_ph` shape. Fixes:

- `pab/fit` — added `chl_from_aph()` + `BRICAUD_APH440`; `extract_quantities`
  now emits a BING-retrieved **`chl`** quantity; reworded the `Chl`-as-input
  docstrings to "seed".
- `pab/metrics` — `gather_matchups` surfaces `chl_bing` (`BING_*_chl`) so the
  **BING Chl vs Argo `chla`** comparison runs through the same quantity-agnostic
  `log_comparison` as `b_bp`; `add_oc_chl` (OC4 band ratio) is reframed as an
  optional independent cross-check.
- Docs corrected: `PAB_design.md` (v0.4.1, *Comparison & metrics*),
  `fitting.rst`, `metrics.rst`, the impl record (v0.5.1), and the
  `07_metrics` notebook (now shows a Chl scatter beside `b_bp`).

What I learned: the model takes `Chl` only to set the Bricaud `a*_ph(λ)` shape;
the fitted amplitude `Aph` then determines the retrieved Chl — so a Chl matchup
is a genuine retrieval-vs-in-situ test, parallel to backscatter.

### 2026-06-23 (Reviewed Stage 6 PR #4 and posted the review to GitHub)

Reviewed PR #4 "Stage 6" (`stage-6` → `develop`, 20 files) and posted a COMMENT
review (https://github.com/ocean-colour/PAB/pull/4) as `profxj`. Due diligence:
`pytest` 89 passed / 2 skipped, `ruff` + `sphinx -W` clean. Verdict: solid, two
scope notes — (1) the NASA L2 IOP baseline (BING-vs-NASA) isn't implemented and
should be marked deferred; (2) `gather_matchups` should filter `fits` by
`model_pair` before a second pair is added (else duplicate/NULL matchup rows).
No merge/commit (git is JXP's). Full detail in `coding_stage6.md`.

### 2026-06-23 (Stage 6 — false-color RGB scene quick-look)

Per JXP's Stage 6 Task 3, upgraded the scene QA view from a single channel to a
**false-color RGB composite**: `pab/plotting/scene.py` gains `false_color_rgba`
(Rrs at ~645/555/470 nm → R/G/B, percentile-stretched, flagged pixels greyed) and
`scene_quicklook` now defaults to `mode="rgb"` (with `mode="band"` retained). The
RGB is drawn via `pcolormesh(...).set_facecolor(rgba)` so the float/pixel overlay
stays exact on the swath mesh. Tests +1 (`false_color_rgba`) and the scene smoke
now covers both modes → **90 passed, 2 skipped**; `ruff` + `sphinx -W` clean.
Docs updated: `PAB_design.md` (v0.4.2), `metrics.rst`, impl record (v0.5.2), and
the `07_metrics` notebook. Detail in `coding_stage6.md`.

### 2026-06-23 (Stage 6 — fixed the blank RGB scene in the notebook)

JXP saw nothing for the scene in `07_metrics.ipynb`. Root cause: the demo
granule was spatially **uniform** (`np.tile`), so the false-color composite —
with the old `Rrs/max` stretch — saturated every channel to 1.0 (pure white). My
earlier "renders RGB" log was true (a PNG was present) but the image was
effectively blank. Fixed by (1) switching `_stretch` to a **2–98% percentile
window** per channel (restores contrast; flat → neutral grey, not white) and
(2) rebuilding the notebook's scene with a **spatially varying** granule (gradient
+ greening + a flagged cloud edge). Scene cell now emits a ~20 KB colour PNG.
**90 passed, 2 skipped**; `ruff` + `sphinx -W` clean. Detail in `coding_stage6.md`.

### 2026-06-23 (Stage 6 — false-color composite on real PACE data, notebook 05)

Added a false-color RGB composite of the **real matched PACE granule** to the
live dig-in notebook `docs/nb/05_matchup_7902226_4.ipynb` (float 7902226 / cycle
5) — the first use of the composite on real PACE data (it had only run on
synthetic granules; a repo grep found no other real-PACE RGB). The cell reuses
the already-open `gds`, crops to a ~25×25-pixel window around the float (full OCI
granules are too large to composite whole), remaps the matchup-pixel indices into
the crop, and calls `scene.scene_quicklook`. Committed without outputs (no
Earthdata Login here to execute it); notebook stays excluded from the Sphinx
build, so nothing else is affected. Detail in `coding_stage6.md`.

### 2026-06-23 (Stage 6 — validated the composite on real PACE data; shared-scale fix)

A `~/.netrc` does exist (earthaccess authenticates), so I ran the composite on
**real PACE OCI data** for 7902226/5. Two fixes resulted: (1) `false_color_rgba`
now scales the three channels by a **shared brightness reference** (+gamma)
instead of per-channel percentile stretch — the latter turned a near-uniform
gyre crop into rainbow speckle; the shared scale gives a natural deep-blue ocean
scene (verified by viewing the rendered PNG on granule `…20250219T155847`, where
the float's nearest unflagged pixel is 0.41 km). (2) Fixed an `IndexError` in the
notebook-05 crop (center on the matchup-pixel centroid + clip, not
`locate_float_pixel`). Also learned the closest-*in-time* granule (51% cloud)
doesn't cover the float — the Stage-4 spatial gate correctly prefers the covering
one. Suite **92 passed** (the BING-data tests run now that the Loisel file is
present). Docs bumped: design v0.4.3, impl v0.5.3. Detail in `coding_stage6.md`.

### 2026-06-24 (Stage 6 — addressed PR #4 review comments)

Two findings from my PR #4 review: (1) `gather_matchups` now filters `fits` by
`model_pair` (`AND f.model_pair = ?`) so a second model pair on a matchup can't
duplicate the row (new test); (2) the **NASA L2 IOP baseline** is now explicitly
documented as **deferred** (metrics.rst note + impl §5d) rather than
implied-done — BING-vs-Argo (`b_bp`, Chl) is implemented, BING-vs-NASA awaits an
`ocpy.pace.io.load_iop_l2` ingest. Suite 93 tests (91 + 2 BING-data skips today);
`ruff` + `sphinx -W` clean. impl v0.5.4. No commit (git is JXP's).

### 2026-06-24 (Generated the Stage 7 prompt doc)

Wrote `claude_prompts/coding_stage7.md` (Reporting), modeled on the earlier
stage prompt docs and grounded in coding-plan §7 + the design's Reporting
section: aggregate `.rst` pages (no per-matchup pages) + sortable tables,
standalone Bokeh map/scatter (hover→values, click→artifact-by-id), HEALPix
aggregation via `remote_sensing.healpix`, downloads + manifest, Zenodo snapshot,
and **publish backends stubbed** (local mocks, config-gated). Deliverables
`pab.report.{rst,aggregate,interactive,publish}`, offline tests, `reporting.rst`,
and `08_reporting.ipynb`. Doc only — no code changed.

### 2026-06-24 (Stage 7 — implemented the reporting layer)

Built `pab.report.{aggregate,rst,interactive,publish}`: region/season + HEALPix
aggregation (reusing `remote_sensing.healpix` + `healpy.ang2pix`), programmatic
aggregate `.rst` pages (a **fixed** page set — no per-matchup pages), standalone
Bokeh scatter/map (`bokeh.embed`), and exports + a download manifest
(id→URL+checksum, `pab_version`) with **stubbed** Nautilus-S3/Zenodo backends
(filesystem `LocalStubBackend`; real ones `NotImplementedError`, config-gated).
Tests `test_report.py` (10); `docs/reporting.rst` + `08_reporting.ipynb`. Suite
**103** (101 + 2 BING-data skips when the mount is down); `ruff` + `sphinx -W`
clean. Stage 7 ✅, impl v0.6.0. Notebook bokeh cell uses `embed()` (not
`show()`) so myst-nb has no unknown-mime warnings. No commit (git is JXP's).

### 2026-06-25 (Reviewed Stage 7 PR #5 and posted the review to GitHub)

Reviewed PR #5 "stage 7" (`stage-7` → `develop`, 13 files) and posted a COMMENT
review as `profxj`. Due diligence: `pytest` 103 passed, `ruff` + `sphinx -W`
clean. Verdict: solid; two scope items to flag as partial — (1) the "sortable"
stats tables are static `list-table`s (need a Bokeh `DataTable` or a deferred
note); (2) no separate Sphinx reporting target yet (`build_site` writes `.rst`
sources only). Plus minor notes (inline interactive data vs a once-exported
lookup table; BING-vs-NASA still pending). No merge/commit. Detail in
`coding_stage7.md`.

### 2026-06-25 (Stage 7 — addressed PR #5 review comments)

Both should-fix findings fixed: (1) the binned stats tables are now **sortable**
Bokeh `DataTable` embeds (`interactive.stats_table`; static `list-table`
fallback), and (2) `build_site` writes a Sphinx `conf.py` so the generated dir is
a **buildable** reporting site (a test runs `sphinx-build` on it). Tests +3 (13
in `test_report.py`); suite **106** (104 + 2 BING-data skips); `ruff` +
`sphinx -W` clean; impl v0.6.1. No commit (git is JXP's).

### 2026-06-25 (Stage 7 — fixed the failing CI tests)

The 2 GitHub failures were the same test (`test_build_site_fixed_pages_no_per_matchup`)
failing in both pytest check-runs: in CI's **lean** env (no `healpy`/
`remote_sensing`), `aggregates_page` always called `aggregate_healpix` →
uncaught `ModuleNotFoundError`. Fixed by making the HEALPix table best-effort
(`try/except ImportError` → a graceful note; flat region/season bins remain the
default). Verified by blocking the `healpy`/`remote_sensing` imports and running
`build_site`, plus a regression test. Suite **107** (105 + 2 BING-data skips);
`ruff` + `sphinx -W` clean; impl v0.6.2. No commit.
