# PAB Coding Plan

**Version:** 0.2
**Date:** 2026-09-03
**Authors:** JXP and Claude

**Status:** living document — updated as the package is developed.
**Companion:** implements [`PAB_design.md`](PAB_design.md) (design v0.3.1). Where
the design doc says *what/why*, this plan says *how/when* (modules, stages,
tests, docs). **Versioning convention** (same as the design doc): minor bump for
substantive changes (0.1 → 0.2), extra decimal for small edits (0.1.1); update
the Date on every bump.

---

## 1. Guiding principles

- **Reuse, don't reinvent.** Build on the installable **BING**, **ocpy**,
  **argopy**, and **remote_sensing** packages. Do **not** import or adapt the
  one-off `bing/papers/biomass/Analysis` scripts — they are a scientific
  reference only; PAB implements fresh modules.
- **Python only.** No MATLAB. Figures and tooling are Python (matplotlib, Bokeh).
- **Cloud-first PACE.** Read PACE from the Earthdata Cloud (in-region AWS
  `us-west-2`); avoid full-granule downloads except for dev/debug.
- **One source of truth for numbers.** Extracted values live in a **SQLite**
  database behind a thin access layer; bulky artifacts (MCMC chains, figures)
  live in files keyed by ID. The storage layer is swappable.
- **Provenance + versioning.** Every fit records inputs, configuration, package
  versions, and a `pab_version` stamp.
- **Every stage ships code + tests + docs.** A stage is "done" only when its
  functionality is tested (pytest) and documented (docstrings + a docs page).
- **Idempotent, resumable pipeline.** Stages skip already-completed work and
  read/write through the database.

## 2. Proposed package layout

A first-cut module map (under [`pab/`](../../pab/)); names may evolve.

```
pab/
  __init__.py
  config.py            # paths, settings, pab_version, run config
  db/                  # SQLite schema + access layer (the storage seam)
    __init__.py
    schema.py          # table definitions
    store.py           # CRUD / query API; CSV/Parquet export
  argo/                # BGC-Argo ingestion & mixed-layer summary
    __init__.py
    fetch.py           # argopy DataFetcher / ArgoIndex wrappers
    mld.py             # de Boyer Montégut MLD (gsw / teos10)
    summary.py         # de-spike, mixed-layer bbp/Chl-a/T/S
    qa.py              # Q&A plots for profiles
  pace/                # PACE discovery, cloud access, extraction
    __init__.py
    discover.py        # earthaccess/CMR search; granule table
    cloud.py           # lazy S3 open (in-region); access abstraction
    extract.py         # nearest-unflagged-pixel Rrs spectra
    flags.py           # l2_flags mask
    l1b.py             # (future) PAB Rrs-from-L1B hook
  matchup/             # space + time matching
    __init__.py
    engine.py          # match floats <-> granules; select ~10 spectra
  fit/                 # BING wrapper
    __init__.py
    models.py          # model-pair config (ExpBricaud+Pow), priors, MCMC opts
    run.py             # LM warm-start -> MCMC -> extract values
    artifacts.py       # chains/figure files keyed by ID; provenance
  metrics/             # comparison metrics
    __init__.py
    compare.py         # ratio, Spearman, log bias/scatter, chi2
  plotting/            # figures
    __init__.py
    fit_fig.py         # per-matchup figure (~100 KB)
    population.py      # scatter/map/metric figures
  report/              # reporting layer
    __init__.py
    rst.py             # programmatic .rst generation
    interactive.py     # standalone Bokeh figures/tables
    aggregate.py       # region/season + HEALPix aggregation
    publish.py         # exports, Nautilus S3 upload + manifest, Zenodo packaging
  pipeline.py          # stage runner / CLI
  tests/               # pytest suite + small fixtures
```

## 3. Cross-cutting concerns (apply to every stage)

- **Testing.** `pytest`. Commit small fixtures — a trimmed BGC-Argo profile, a
  **small real PACE granule subset**, and a stored example BING fit — so the
  suite runs offline and in CI. **The PACE cloud-access layer is mocked in
  tests** (the granule fixture is read locally; no network/S3 in the suite). Unit
  tests for scientific functions (MLD, de-spike, flag decode, metrics) check
  known values.
- **Docs.** Google-style docstrings on every public function; a Sphinx site
  under `docs/` (the same `docs/` that already holds `design/`, `scripts/`,
  `figures/`). Each stage adds/updates a docs page. The reporting site
  (community-facing, Stage 7) is a distinct Sphinx target.
- **Explanatory notebooks.** While working through the stages, create **Jupyter
  notebooks in [`docs/nb/`](../nb/)** that describe and demonstrate any key
  method or analysis (e.g. MLD computation, nearest-pixel extraction, a BING fit,
  the metrics). These notebooks **may pull live data from the internet** (e.g.
  via `argopy` / `earthaccess`) — unlike the offline test suite — so they double
  as runnable worked examples. A notebook is a normal **per-stage deliverable**
  whenever a stage introduces a method worth illustrating, and notebooks can be
  rendered into the docs site (e.g. via `myst-nb`/`nbsphinx`).
- **Provenance/versioning.** `pab.config` exposes `pab_version` and captures
  package versions; the DB stores them per fit.
- **Database.** **SQLite** is the backend (per the design). The default access
  layer is the Python standard-library **`sqlite3`** module (no extra
  dependency); a heavier ORM (e.g. SQLAlchemy) is not adopted now but the thin
  `pab.db.store` API keeps that option open.
- **Standards/tooling.** Type hints where helpful; `ruff`/`black`-style
  formatting. `requirements.txt` is the **single source of dependencies**
  (Python **≥ 3.12**). Install sources differ by package: most deps are on
  **PyPI**; **`bing`** is being packaged for PyPI (use it once published);
  **`remote_sensing`** is installed from **GitHub**; **`ocpy`** likewise from
  GitHub/local checkout. Add `gsw`, `bokeh`, and HEALPix tooling as the stages
  that need them land.
- **CI.** **GitHub Actions** runs the `pytest` suite **and** a docs build on
  every push.

## 4. Development stages

Each stage lists **scope**, **deliverables**, **tests**, and **docs**. Stages
are ordered so each builds on the last; the database (Stage 1) is the backbone.

### Stage 0 — Scaffolding & infrastructure
- **Scope:** package skeleton, `config.py` (+ `pab_version`), test harness, docs
  scaffolding, dependency pinning, CI.
- **Deliverables:** importable `pab` subpackages (empty stubs), `pytest` runs, a
  buildable Sphinx skeleton, CI config.
- **Tests:** import smoke test; `pab_version` present.
- **Docs:** dev-setup / contributing page; docs build green.

### Stage 1 — Database layer (the storage seam)
- **Scope:** SQLite schema for floats/profiles, mixed-layer summaries, the
  matchup index, and namespaced fit results (`BING_ExpBPow_bbp`, …); thin access
  API; CSV/Parquet export.
- **Deliverables:** `pab.db.schema`, `pab.db.store` with create/insert/query/
  export; migrations approach.
- **Tests:** create-insert-query round trips; export equals query; schema
  constraints; idempotent upserts keyed by matchup ID.
- **Docs:** schema reference (tables, columns, units, keys).

### Stage 2 — BGC-Argo ingestion & mixed-layer summary
- **Scope:** argopy fetch (`ds='bgc'`, `src='erddap'`), QC filtering, **MLD** (de
  Boyer Montégut 0.03 kg m⁻³ via `gsw`/`teos10`), 3-pt de-spike, mixed-layer
  averages (`bbp`, `CHLA`, mean `PSAL`/`TEMP`); write summaries to the DB; Q&A
  plots.
- **Deliverables:** `pab.argo.{fetch,mld,summary,qa}`.
- **Tests:** MLD on a synthetic density profile (known answer); de-spike removes
  an injected spike; mixed-layer average correctness; summary row persisted.
- **Docs:** Argo ingestion page; MLD method note (cite Bisson/de Boyer Montégut).

### Stage 3 — PACE access & spectrum extraction
- **Scope:** granule discovery (`earthaccess` + `remote_sensing.download.
  earthaccess.build_granule_table`); cloud lazy-S3 open (in-region) behind an
  access abstraction; nearest-**unflagged**-pixel `Rrs(λ)`/`Rrs_unc` extraction;
  `l2_flags` mask; PACE noise vector (`ocpy.satellites.pace.gen_noise_vector`);
  **granule quality assessment** — percent flagged pixels (granule + local box),
  per-flag breakdown with the dominant flag, valid-pixel count near the float —
  written to the DB as granule-QC fields. L1B hook left as a documented stub.
- **Deliverables:** `pab.pace.{discover,cloud,extract,flags,quality}`
  (+ `l1b` stub).
- **Tests:** nearest-pixel selection and flag decoding on a tiny granule fixture;
  mask matches expected bits; flag-tally / percent-flagged on a known fixture;
  cloud layer mocked.
- **Docs:** PACE access page (cloud-first; (a) lazy-S3 vs (b) OPeNDAP trade-off;
  granule-QC fields).

### Stage 4 — Matchup engine
- **Scope:** space+time matching (small pixel box, time window), select the ~10
  nearest valid spectra per qualifying profile, write matchup records linking
  float ↔ granule ↔ pixels.
- **Deliverables:** `pab.matchup.engine`.
- **Tests:** matching on synthetic geometry/time (distance, window edges,
  flagged-pixel exclusion); record links persisted.
- **Docs:** matchup criteria page (box size, Δtime, selection rule).

### Stage 5 — BING fitting wrapper
- **Scope:** configure the `ExpBricaud`+`Pow` pair (prepared for more), priors,
  standard MCMC settings (`nsteps≈10000`, `nburn≈1000`, 16 walkers); LM
  warm-start → MCMC; extract scalar IOPs + uncertainties into namespaced columns;
  write chains (NPZ) keyed by ID; record provenance + `pab_version`; batch +
  idempotent.
- **Deliverables:** `pab.fit.{models,run,artifacts}`.
- **Tests:** fit a stored example spectrum fixture and check retrieved `bbp`/`β`
  against a tolerance; provenance fields populated; re-run is idempotent.
- **Docs:** fitting page (pipeline, model naming schema, provenance).

### Stage 6 — Metrics & figures
- **Scope:** comparison metrics (median sat/float ratio, Spearman ρ, log-space
  bias & RMS/MAD scatter, per-fit reduced χ²; BING vs NASA-L2-IOP); per-matchup
  fit figure (~100 KB target); **per-matchup scene quick-look PNG** (granule
  neighborhood thumbnail with the Argo location marked, the extracted/analyzed
  pixels highlighted, and the `l2_flags` mask shown); population figures
  (scatter/map/distributions).
- **Deliverables:** `pab.metrics.compare`, `pab.plotting.{fit_fig,scene,population}`.
- **Tests:** metric values on constructed arrays (known ratio/correlation/bias);
  fit + scene figure files produced and within size budget (smoke); scene marks
  the correct float pixel on a fixture.
- **Docs:** metrics definitions page (mirrors the design Analysis subsection);
  scene quick-look description.

### Stage 7 — Reporting
- **Scope:** programmatic `.rst` generation; small fixed set of **aggregate**
  pages + sortable tables (no per-matchup pages); **standalone Bokeh** map/scatter
  with hover→values and click→artifact-by-ID; **HEALPix** spatial aggregation
  (via `remote_sensing.healpix`) alongside region/season bins; exports
  (CSV/Parquet, NPZ); **Nautilus/NSF S3** upload + download manifest; **Zenodo**
  snapshot packaging.
- **External services (stubbed for now).** Credentials/endpoints for Nautilus/NSF
  S3 and Zenodo are available, but this stage **implements the publish interfaces
  against stubs/local mocks** and defers wiring real uploads until later — so the
  reporting build runs end-to-end (writing artifacts/manifests locally) without
  live external calls. Activation is a later, config-gated switch.
- **Deliverables:** `pab.report.{rst,interactive,aggregate,publish}` (publish
  backends stubbed); the readthedocs reporting target.
- **Tests:** rst renders; Bokeh embed produced; aggregation bins correct
  (HEALPix cell assignment on known coords); manifest IDs↔URLs consistent.
- **Docs:** reporting/build page; how to publish a release.

### Stage 8 — End-to-end pipeline & CLI
- **Scope:** the semi-automated stage runner tying Stages 2–7 together —
  idempotent, resumable, config-driven, single-matchup (debug) or full batch
  (parallel via BING `fit_batch`).
- **Deliverables:** `pab.pipeline` + CLI entry point.
- **Tests:** end-to-end run on a tiny fixture (1–2 floats, 1 granule) producing
  DB rows + artifacts + a minimal site.
- **Docs:** user guide / quickstart; pipeline stages and resume behavior.

### Stage 9 — Extensibility & options (future)
- **Scope:** loader registry for new in-situ/satellite sources; additional BING
  model pairs; the **L1B → Rrs** algorithm; optional server-backed interactivity.
- **Deliverables / tests / docs:** per sub-feature, as prioritized.

### Stage 10 — BGC-Argo provenance & CDOM ingestion (added 2026-09, v0.2)

Retroactive stage, in the spirit of Stage 9's post-hoc report close-out:
extends Stages 1–2 after the full-mission run, driven by the chl-a/CDOM
deep-dive planning in `claude_prompts/chl_cdom_matchups.md`. Two bugs/gaps
found while planning that deep-dive motivate it: (1) `floats.project_name`/
`data_center` and `profiles.data_mode` are columns that exist in the schema but
are **never populated** — `pab/argo/fetch.py::iter_profiles` doesn't extract
`PROJECT_NAME`/`DATA_CENTRE` at all, and `pab/pipeline.py::ingest()` doesn't
forward even the `DATA_MODE` it does extract to `persist_summary()` — so no
float in the full production run can currently be attributed to a processing
DAC (e.g. AOML); (2) `CDOM` isn't ingested at all, and Argo's real per-
**parameter** data-mode/adjustment metadata (`PARAMETER_DATA_MODE`,
`<PARAM>_ADJUSTED*`, `SCIENTIFIC_CALIB_*`) was never captured for any BGC
variable, only the coarse whole-profile `data_mode`.

- **Scope:**
  - **Spot-check first.** Before writing ingestion code, fetch one or two real
    profiles and determine empirically whether GDAC's `CDOM_ADJUSTED` already
    reflects the Sea-Bird Scientific calibration fix (RAF = 5.62 for sensors
    calibrated/serviced before 2023-01-13; see `PAB_design.md` v0.5) — this
    decides whether ingestion trusts `CDOM_ADJUSTED` as-is or must apply the
    RAF itself for pre-cutoff sensors lacking an adjusted value.
  - **DAC/project provenance.** Extract `PROJECT_NAME`/`DATA_CENTRE` per float
    in `iter_profiles`; thread `project_name`/`data_center` (already accepted
    by `summary.persist_summary`, just never supplied) through both `ingest()`
    call sites in `pipeline.py`. No schema change — `floats.project_name`/
    `data_center` already exist since Stage 1.
  - **CDOM ingestion.** Add `"CDOM"` to `pab/argo/fetch.py::DEFAULT_PARAMS`;
    compute its mixed-layer mean like `CHLA` (plain mean, no de-spike/IQR —
    Bisson's despike recipe is `BBP700`-specific).
  - **Per-parameter provenance.** Extract, per profile, the parameter-level
    data mode and `_ADJUSTED` value for `CHLA` and `CDOM` (and `BBP700` for
    consistency, if cheap); persist alongside the existing raw means.
  - **Schema migration v3 → v4** (`pab/db/schema.py`): add to `mld_summary` —
    `cdom`, `cdom_std`, `cdom_adjusted`, `chla_adjusted`, `chla_data_mode`,
    `cdom_data_mode` (names provisional; finalize during implementation,
    following the existing `_v2_to_v3`-style forward migration).
  - **Re-ingestion.** Per JXP (`claude_prompts/chl_cdom_matchups.md`, C1/C4):
    fold this into one combined pass rather than separate Chl- and CDOM-only
    re-runs; re-ingest the **existing 881 matched floats only** (no broadened
    float selection — C4: "we'll just take what there is").
- **Deliverables:** updated `pab.argo.{fetch,summary}`, `pab.pipeline.ingest`,
  `pab.db.schema` (v4 migration); a re-ingestion run over the 881 floats
  producing `CDOM`/adjusted/provenance-populated `mld_summary` rows.
- **Tests:** `PROJECT_NAME`/`DATA_CENTRE` extraction and threading (a
  synthetic-dataset fixture asserting `floats.data_center` round-trips, closing
  the exact gap this stage fixes); CDOM mixed-layer mean (known-answer, mirrors
  the existing `CHLA` test); v3→v4 migration idempotency; a re-ingestion smoke
  test confirming no previously-populated field regresses.
- **Docs:** update `db_schema.rst` for the new columns; update
  `docs/argo_ingestion.rst` for CDOM + the provenance fields; after the pass
  completes, update `PAB_implementation.md` with what was actually built (per
  JXP's C5 answer — plan first, implement, then record).

## 5. Suggested order & dependencies

```
Stage 0 ─► Stage 1 ─► Stage 2 ─┐
                     └► Stage 3 ─► Stage 4 ─► Stage 5 ─► Stage 6 ─► Stage 7 ─► Stage 8 ─► (Stage 9) ─► Stage 10
```

Stages 2 and 3 can proceed in parallel after the database (Stage 1) exists, since
the Argo and PACE sides are independent until the matchup (Stage 4). A thin
end-to-end "walking skeleton" (one float → one granule → one fit → one row → one
page) is worth standing up early (a minimal pass through Stages 1–8 on fixtures)
to de-risk the seams before scaling each stage out.

## 6. Milestones

- **M1 (Stages 0–1):** project + database usable.
- **M2 (Stages 2–4):** matchup records produced from real Argo + PACE.
- **M3 (Stages 5–6):** BING fits + metrics + figures in the DB.
- **M4 (Stage 7–8):** end-to-end pipeline + published readthedocs report.

---

*Living document; stages, names, and ordering will be refined as development
proceeds.*
