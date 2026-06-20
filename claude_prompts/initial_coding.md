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


## Stage 0

### Tasks

1.  Read the context files. Proceed with the coding.  Begin with Stage 0.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

### Q&A

## Stage 1

1.  Read the context files. Proceed with the coding.  Begin with Stage 1.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

## Stage 2

1.  Read the context files, especially the design document and the coding plan. Proceed with Stage 2.  If you have any questions, write them in the Q&A section below.  Log your work in the Logs section below.

2.  I should have requested from the start that you also create an Implemntation file to record your work.  Please do so now.  Call it `docs/design/PAB_implementation.md`.

### Q&A

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
