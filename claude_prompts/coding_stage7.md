# Coding up PAB — Stage 7 (Reporting)

## Goals

Implement **Stage 7** of the coding plan: the **reporting layer** that turns the
SQLite store of extracted values and the per-matchup fit artifacts (Stages 4–6)
into the community-facing products PAB exists to share — a **static readthedocs
site** of *aggregate* pages + sortable tables, **standalone Bokeh** interactive
map/scatter (the route to per-matchup detail), **downloads** (summary tables +
chains + figures), and a **citable snapshot** — with the external-service
backends (Nautilus/NSF S3, Zenodo) **stubbed** so the build runs end-to-end
offline. Per JXP this is *possibly the most important component of PAB*.

We continue to be guided by the design document `docs/design/PAB_design.md`
(especially the **Reporting** section) and the coding plan
`docs/design/PAB_coding_plan.md`, and we record what we build in
`docs/design/PAB_implementation.md`.

## Claude

### Skills

No BING fitting skills apply here; reporting is `.rst`/Bokeh/HEALPix glue over
the existing store and artifacts. Reuse, don't reinvent:

- **`remote_sensing.healpix`** (`rs_healpix`, `combine`, `utils`) — equal-area
  spatial binning for the HEALPix aggregation (an alternative to the flat
  region/season bins).
- **`pab.metrics.compare`** — `gather_matchups`, `log_comparison`, `add_strata`
  already produce the per-matchup table + binned statistics the pages display.
- **`pab.db.store.Store`** — `query_df`, `export_csv`, `export_parquet`,
  `fit_results_wide` are the export primitives.
- **`bokeh.embed`** (`components` / `json_item`) — standalone interactive figures
  for static hosting (no Bokeh server).

### Working agreements (unchanged from Stages 0–6)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written; do **not** copy
  the one-off `bing/papers/biomass/Analysis` scripts.

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md` → **Reporting** (the authoritative
  spec): the four products (static readthedocs `.rst`; standalone Bokeh;
  downloads; Zenodo snapshot), the **aggregate-not-per-matchup** constraint, the
  HEALPix aggregation, the Nautilus/NSF S3 object store + download manifest, and
  *Architecture & build* (build keyed to `pab_version`; fully static).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 7* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current state;
  update it at the close of this stage).
- **Existing PAB seams this stage builds on:**
  - `pab.db.store.Store` — the numbers: `query_df`/`table_df`,
    `fit_results_wide()`, `export_csv`/`export_parquet`. (The raw SQLite **file**
    is *not* a published download — only the table exports are.)
  - `pab.metrics.compare` — `gather_matchups` (per-matchup table), `add_strata`
    (season/region), `log_comparison` (population + per-bin stats).
  - `pab.fit.artifacts` + `fits.chains_path`/`figure_path` — the bulky per-matchup
    artifacts (chains NPZ, ~100 KB figures) the **download manifest** points to,
    keyed by matchup id + `pab_version`.
  - `pab.plotting.{fit_fig,scene,population}` — figures referenced by id from the
    interactive layer (rendered in Stage 6).
  - `pab.config` — `pab_version` (the build is keyed to it) and
    `package_versions()` (provenance in the manifest / release metadata).

## Prompts

1. Read this doc and the context files. Execute the 1st task in the "Stage 7"
   section below.
2. Read this doc.  Execute the 1st task in the "Pull Request" section below.
3. Read this doc.  Execute the 2nd task in the "Pull Request" section below.
4. Read this doc.  Execute the 3rd task in the "Pull Request" section below.

## Stage 7

### Tasks

1. Read this doc and the context files. Implement Stage 7 (below). If you have
   questions, write them in the Q&A section. If you have any requests, write them
   in the Requests section. Log your work in the Logs section.

### Q&A

(Write any questions for JXP here; he answers inline. Do not block on interactive
prompts.)

### Requests

**Addressed the PR #5 review (Claude, 2026-06-25).** Working-tree edits (not
committed — git is yours):

- **Fixed — sortable tables.** Added `interactive.stats_table` (a sortable Bokeh
  `DataTable`); `rst.aggregates_page(sortable=True)` now embeds sortable
  `DataTable`s (via `raw_html`), falling back to a static `list-table` when
  `bokeh` is unavailable. Tests: the `DataTable` is sortable; the embed is in the
  page; the static fallback still emits a `list-table`.
- **Fixed — separate Sphinx reporting target.** `build_site` now also writes a
  minimal `conf.py` (with the BokehJS CDN in `html_js_files` when bokeh is
  present), so the output dir is a **self-contained, buildable** reporting site
  (`sphinx-build <outdir> <outdir>/_build`). New test actually **builds the
  generated site** and checks `summary.html` is produced.
- **Minor (noted, not changed):** the interactive scatter still embeds the frame
  inline (fine at dev scale; the once-exported lookup table is a scale follow-up)
  and BING-vs-NASA remains deferred with Stage 6.

Suite **106** (104 + 2 BING-data skips when the mount is down); `ruff` +
`sphinx -W` clean. Docs (reporting.rst, impl §5e v0.6.1) updated.

## Pull Request

1. I have executed a Pull Request on GitHub for Stage 7. Please review the Pull
   Request and post it to GitHub.

2. Make edits to the Repo to address the review comments. If you have any
   questions, write them in the Q&A section below. If you have any requests,
   write them in the Requests section below.

3. There are 2 failing tests on GitHub.  Please fix them.  Log your work.

## Stage 7 — Reporting

Here is some additional context.

### Scope

Turn the store + artifacts into navigable, citable products — **build runs
end-to-end offline**, with external uploads stubbed:

- **Programmatic `.rst` generation** — a small **fixed set of aggregate pages**
  (landing/summary with headline `b_bp` (and Chl) sat-vs-float metrics; binned
  result pages; methods/algorithm pages citing BING + Bisson). **No per-matchup
  pages** (the ~10⁴-matchup page explosion JXP rules out) and no per-float pages;
  per-matchup detail is reached on demand via the interactive figures. Pages
  carry **sortable statistics tables** generated from the DB.
- **Aggregation** — population and **binned** views: by region, season, `b_bp`
  magnitude, and (where available) `Rrs` variability, **plus a HEALPix**
  equal-area spatial binning (via `remote_sensing.healpix`) feeding a map + a
  per-cell table. Flat region/season bins are the default; HEALPix is the
  alternative to evaluate alongside.
- **Standalone Bokeh** — a **map** of matchup locations and the
  **satellite-vs-float `b_bp`** (and BING-vs-NASA, once that baseline lands)
  scatter, embedded as static HTML/JSON (`bokeh.embed`, no server). **Hover** →
  each matchup's key values (IOPs + uncertainties, float context, distance/Δtime,
  `pab_version`); **click** → that matchup's figure/artifacts by id. The
  hover/lookup metadata is exported **once** to a compact table the figure loads;
  large scatter/maps use `output_backend="webgl"`.
- **Downloads + manifest** — export the **summary tables** (CSV/Parquet) and a
  **download manifest** (matchup id → URLs + checksums) tying the per-matchup
  **chains (NPZ)** and **figures** (in the object store) back to DB rows, keyed by
  `pab_version`. The raw SQLite file is **not** published.
- **Citable snapshot** — package the summary export + artifact manifest for a
  **Zenodo** DOI, pinned to a `pab_version`.
- **Publish backends — STUBBED.** Implement the publish *interfaces*
  (Nautilus/NSF S3 upload, Zenodo packaging) against **local mocks / the
  filesystem**, writing artifacts + manifests locally; **defer real uploads**
  behind a config gate (no live external calls in this stage, none in tests).

Keep network/object-store/Bokeh as **lazily-imported, mockable seams**; keep the
aggregation math and manifest construction in **pure functions** that unit-test
offline with known values.

### Deliverables

- `pab.report.rst` — templated `.rst` page generation from the store + metrics.
- `pab.report.aggregate` — region/season + `b_bp`-magnitude bins and the HEALPix
  binning (cell assignment + per-cell stats), returning tidy tables.
- `pab.report.interactive` — standalone Bokeh map/scatter + the hover/lookup
  metadata export (`bokeh.embed`).
- `pab.report.publish` — exports (CSV/Parquet/NPZ), the download manifest
  (ids→URLs+checksums + `pab_version`/provenance), and **stubbed** S3/Zenodo
  backends behind a config gate.
- Update `pab/report/__init__.py` to export the public API.
- A **separate Sphinx reporting target** (the community site) distinct from the
  developer docs; programmatically generated, fully static.

### Tests (offline; `pytest`)

- **`.rst` renders** — aggregate pages built from a seeded store contain the
  expected sections + a sortable stats table; **no per-matchup page** is emitted
  (assert the page count is the fixed aggregate set regardless of matchup count).
- **Aggregation correctness** — region/season/magnitude bins and **HEALPix cell
  assignment** on known coordinates give the expected cells/among-bin stats.
- **Bokeh embed produced** — `components`/`json_item` returns non-empty
  script+div (guard with `pytest.importorskip("bokeh")`).
- **Manifest consistency** — ids ↔ URLs one-to-one, checksums present,
  `pab_version` stamped; the **publish stub** writes locally and performs no
  network call (assert via the mock).
- **Exports** — CSV/Parquet round-trip (reuse `Store.export_*`).
- Continue the project convention: pure functions checked with known values;
  heavy/network seams mocked; no live S3/Zenodo/network.

### Docs

- A **reporting page** (`docs/reporting.rst`): the build pipeline (DB + artifact
  store → aggregate `.rst` + Bokeh → readthedocs; Zenodo snapshots), the
  aggregate-not-per-matchup rationale, the HEALPix aggregation, the
  downloads/manifest scheme, the **stubbed** publish backends + the config gate,
  and **how to publish a release** (keyed to `pab_version`). Add it to the
  `index.rst` *Package* toctree and autodoc `pab.report.*`.

### Notebook

- `docs/nb/08_reporting.ipynb` — a worked example on a **synthetic** store
  (offline): compute the binned + HEALPix aggregates, render an aggregate `.rst`
  snippet, produce a standalone Bokeh scatter, and write a download manifest +
  CSV/Parquet export — all without network. Built executed (offline-safe),
  rendered via `myst-nb`, added to the *Notebooks* toctree.

### Definition of done (the Stage 0–6 standard)

- `pytest` green (new Stage 7 tests included); `ruff check pab` and
  `ruff format --check pab` clean; `sphinx-build -W` succeeds.
- Google-style docstrings on every public function; provenance (`pab_version`,
  package versions) stamped on the manifest / release metadata.
- `docs/design/PAB_implementation.md` updated: flip Stage 7 to ✅ in the status
  table, add a Stage 7 section (modules/API, key decisions, tests, docs,
  notebook), update the module index and the verification line; bump its
  version/date.
- Work logged (see below).

### Q&A

(Write any questions for JXP here; he answers inline. Do not block on interactive
prompts.)

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-06-25 (Stage 7 — fixed the 2 failing CI tests)

The 2 GitHub failures were the **same** test failing in both pytest check-runs
(push + PR events): `test_build_site_fixed_pages_no_per_matchup` →
`ModuleNotFoundError: No module named 'healpy'`. Root cause — CI's **lean** env
has no `healpy`/`remote_sensing`, but my `aggregates_page` always called
`aggregate_healpix`, whose `import healpy` is uncaught.

Fix: made the HEALPix table in `aggregates_page` **best-effort** — wrap
`aggregate_healpix` in `try/except ImportError` and emit a "(HEALPix aggregation
requires healpy / remote_sensing)" note instead of crashing. The flat
region/season bins are the default and still render. (`ModuleNotFoundError`
subclasses `ImportError`, so the existing bokeh-fallback pattern is matched.)

Verified by actually blocking `healpy`/`remote_sensing` imports and running
`build_site` (degrades, no crash) and with a monkeypatched regression test
`test_build_site_without_healpy`. Suite **107** (105 + 2 BING-data skips); `ruff`
+ `sphinx -W` clean; impl v0.6.2. No commit (git is JXP's).

### 2026-06-25 (Stage 7 — addressed PR #5 review comments)

Implemented both should-fix findings (detail in Requests):

- **Sortable tables**: `interactive.stats_table` (sortable Bokeh `DataTable`) +
  `aggregates_page(sortable=True)` embedding them, with a static `list-table`
  fallback when bokeh is absent.
- **Separate Sphinx target**: `build_site` writes a `conf.py` (BokehJS CDN in
  `html_js_files`) so the output dir builds standalone; a new test runs
  `sphinx-build` on the generated site.
- Tests +3 (`test_report.py` → 13): sortable-when-bokeh, site-builds,
  stats_table-sortable. Suite **106** (104 + 2 BING-data skips when the mount is
  down); `ruff` + `sphinx -W` clean. Docs + impl (v0.6.1) updated. No commit.

### 2026-06-25 (Stage 7 — reviewed PR #5 and posted the review to GitHub)

Reviewed PR **#5 "stage 7"** (`stage-7` → `develop`, 13 files) and posted a
COMMENT review (https://github.com/ocean-colour/PAB/pull/5) as `profxj`.

- **Due diligence:** `pytest` 103 passed; `ruff` + `sphinx -W` clean.
- **Verdict:** solid core; two scope items partially delivered, flag explicitly.
  (1) **"Sortable" tables aren't sortable** — `rst_table` emits a static
  `list-table`; either a Bokeh `DataTable` or mark deferred. (2) **No separate
  Sphinx reporting target** — `build_site` writes `.rst` *sources*, but there's
  no `conf.py`/build for the community site; say sources-only / follow-up. Minor:
  interactive embeds the full df inline (vs the speced once-exported lookup
  table); BING-vs-NASA still pending; a `LocalStubBackend` key/url nit.
- Posted via `gh pr review 5 --comment`; no merge/commit (git is JXP's).

### 2026-06-24 (Stage 7 — implemented the reporting layer)

Implemented Stage 7: `pab.report.{aggregate,rst,interactive,publish}`.

- **`aggregate.py`** — `aggregate_by` (region/season bins via `log_comparison`),
  `magnitude_bins`, and HEALPix (`nside_for_cell_size` wrapping
  `remote_sensing.healpix`, `assign_healpix` via `healpy.ang2pix`,
  `aggregate_healpix` → per-cell stats + centres).
- **`rst.py`** — `rst_table` + `summary`/`aggregates`/`methods`/`index` pages and
  `build_site` writing the **fixed** `PAGE_STEMS` set to a dir outside the dev
  docs. **No per-matchup pages** (asserted in a test).
- **`interactive.py`** — standalone Bokeh `comparison_scatter` (log-log, hover,
  optional tap→artifact, webgl) + `matchup_map` + `embed`/`raw_html`.
- **`publish.py`** — `export_tables` (CSV/Parquet; not the raw DB), `build_manifest`
  (id→URL+SHA-256, `pab_version`), `publish_release` (exports + manifest + stub
  uploads + `manifest.json`); `LocalStubBackend` (filesystem, no network);
  `NautilusS3Backend`/`ZenodoBackend` = `NotImplementedError` stubs (deferred).
- **Tests** `test_report.py` (10): aggregation (region + HEALPix), no-per-matchup
  page count, rst_table, Bokeh embed, export round-trip, manifest consistency +
  stub-not-network, deferred-backends raise. Suite **103** (101 + 2 BING-data
  skips when the Loisel mount is down). `ruff` + `sphinx -W` clean.
- **Docs** `reporting.rst` + **notebook** `08_reporting.ipynb` (executed offline).
  Implementation record → Stage 7 ✅ (v0.6.0).

Key decisions / what I learned:

- **Tidy per-cell HEALPix table**, not a full-sky map: `healpy.ang2pix` for cell
  assignment + a pandas groupby gives a compact per-cell table (count, median
  ratio, centre lon/lat) that scales with *occupied* cells, not 12·nside².
- **Publish is stubbed end-to-end offline** (filesystem backend), with the real
  Nautilus S3 / Zenodo behind explicit `NotImplementedError` until a config gate
  activates them — exactly the plan's "implement the interfaces against stubs."
- **Bokeh in the docs notebook**: `output_notebook()/show()` emits
  `bokehjs_load/exec` mime types myst-nb can't render → `sphinx -W` warnings (and
  they wouldn't display statically anyway). Switched the cell to the
  `embed()` (components) path and report the script/div sizes — offline-safe and
  warning-free, and it's the path the site actually uses.
- Cleaned up the demo output dirs (`report_site`/`release`/`artifacts`) the
  notebook writes under `docs/nb/` so they aren't committed.
