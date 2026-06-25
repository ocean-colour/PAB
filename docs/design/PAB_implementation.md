# PAB Implementation Record

**Version:** 0.6.2
**Date:** 2026-06-25
**Authors:** JXP and Claude

**Status:** living document — updated as each stage is implemented.
**Companions:** implements [`PAB_design.md`](PAB_design.md) (design, *what/why*)
following [`PAB_coding_plan.md`](PAB_coding_plan.md) (plan, *how/when*). This
document records *what was actually built*: the modules, their public API, the
implementation decisions taken, and the test/doc coverage per stage.
**Versioning convention** (same as the design doc): minor bump for substantive
changes (0.1 → 0.2), extra decimal for small edits (0.1.1); update the Date on
every bump.

> This complements the chronological work log in
> [`claude_prompts/initial_coding.md`](../../claude_prompts/initial_coding.md)
> (the "Logs" section). The log is dated narrative; this document is the
> structured, current-state reference for the package as implemented.

---

## 1. Status at a glance

| Stage | Title | Status | Package surface |
|---|---|---|---|
| 0 | Scaffolding & infrastructure | ✅ done | `pab`, `pab.config`, subpackage stubs, CI, docs skeleton |
| 1 | Database layer | ✅ done | `pab.db.schema`, `pab.db.store` |
| 2 | BGC-Argo ingestion & mixed-layer summary | ✅ done | `pab.argo.{mld,summary,fetch,qa}` |
| 3 | PACE access & spectrum extraction | ✅ done | `pab.pace.{flags,extract,cloud,discover,l1b}` |
| 4 | Matchup engine | ✅ done | `pab.matchup.engine` |
| 5 | BING fitting wrapper | ✅ done | `pab.fit.{models,run,artifacts}` |
| 6 | Metrics & figures | ✅ done | `pab.metrics.compare`, `pab.plotting.{fit_fig,scene,population}` |
| 7 | Reporting | ✅ done | `pab.report.{aggregate,rst,interactive,publish}` |
| 8 | End-to-end pipeline & CLI | ⬜ pending | `pab.pipeline` (stub) |
| 9 | Extensibility & options | ⬜ future | — |

**Environment notes.** Workstation Python is 3.14.5 (plan floor 3.12);
`bing`, `ocpy`, `remote_sensing`, `argopy`, `earthaccess`, `gsw`, `pandas`,
`pyarrow` are all installed locally. CI runs two jobs: a **test** job that
installs a lean dependency set (numpy/scipy/pandas/pyarrow/xarray/gsw/matplotlib
+ pytest) and the package with `--no-deps`, and a **docs** job that builds with
`-W`. The test suite is fully offline (no network/S3); tests touching the
heavy/optional deps use `pytest.importorskip`.

**Verification (current).** `pytest` → 107 tests: 105 passed + 2 skipped when the
BING Loisel aph-basis data file is absent (the `b_bp`-recovery and fit-figure
smoke skip, e.g. on lean CI / when the data mount is down), 107 passed when it is
present; `ruff check pab` and `ruff format --check pab` → clean; `sphinx-build
-W` → build succeeded.

---

## 2. Stage 0 — Scaffolding & infrastructure

**Modules**

- `pab/__init__.py` — re-exports `pab_version` as `__version__`.
- `pab/config.py` —
  - `pab_version = "0.0.dev0"` (provenance stamp; distinct from the packaging
    version in `setup.py`).
  - `ROOT` / `DATA_DIR` paths, env-overridable via `PAB_ROOT` / `PAB_DATA_DIR`
    (`DATA_DIR` keeps large data out of the repo).
  - `package_versions()` → dict of versions for `pab`, `bing`, `ocpy`,
    `argopy`, `remote_sensing`, `earthaccess`, `numpy`, `scipy`, `xarray`;
    reports `"not installed"` instead of raising.
- Subpackage stubs `pab.{db,argo,pace,matchup,fit,metrics,plotting,report}` and
  `pab/pipeline.py`, each documenting its future role and stage.

**Infrastructure**

- `pytest.ini` (collect from `pab/tests`), `ruff.toml` (E/F/I/W/UP/B; black
  line length 88; `py312` target).
- `docs/` Sphinx site: `conf.py` (napoleon, myst-parser, sphinxcontrib-mermaid,
  `autodoc_mock_imports` for the heavy optional deps, `suppress_warnings` for
  the design docs' repo-relative links), `index.rst`, `dev_setup.rst`.
- `.github/workflows/ci.yml` (pytest + `-W` docs build on push/PR);
  `.readthedocs.yaml`.
- `requirements.txt` is the single source of dependencies; the special-source
  packages (`bing`, `ocpy`, `remote_sensing`) remain commented (installed
  separately) so `pip install -r` never fails.

**Tests** — `pab/tests/test_smoke.py`: import smoke over every subpackage,
`pab_version` presence/type, `package_versions()` shape.

**Docs page** — `dev_setup.rst` (install, test, docs build, working agreements,
CI).

**Notebook** — `docs/nb/00_getting_started.ipynb` (import, `pab_version`, config
paths, `package_versions()`).

---

## 3. Stage 1 — Database layer (the storage seam)

SQLite on the standard-library `sqlite3` (no ORM), behind a thin swappable
access layer so the backend can later change without touching analysis code.

### 3.1 Schema (`pab/db/schema.py`)

Eight tables in four groups (units & keys in `docs/db_schema.rst`):

- **floats / profiles** — `floats(wmo PK)`; `profiles(profile_id PK,
  UNIQUE(wmo,cycle), FK wmo)`.
- **mixed-layer summary** — `mld_summary(profile_id PK/FK)` 1:1 with a profile:
  `mld`, `mld_method`, `bbp700(+_std)`, `chla(+_std)`, `psal`, `temp`,
  `n_points`, `created`, `pab_version`.
- **matchup index** — `granules(granule_id PK)`; `matchups(matchup_id PK,
  UNIQUE(profile_id,granule_id))`; `matchup_pixels(pixel_id PK,
  UNIQUE(matchup_id,ix,iy))`.
- **namespaced fits** — `fits(fit_id PK)` (config + provenance + on-disk
  artifact paths) and `fit_results(fit_id,quantity PK)` in **long** format.

Supporting machinery: `SCHEMA_VERSION` (stored in `PRAGMA user_version`),
`UPSERT_KEYS` (natural key per table — the pure-Python source of truth the store
upserts on), `TABLE_NAMES`, `create_all()`, `get_version()`, and `migrate()` with
a forward-migration `MIGRATIONS` registry (empty at v1; mechanism in place).

### 3.2 Access layer (`pab/db/store.py`)

`Store` class — `Store.open(path, create=True)` (sets `foreign_keys=ON`, `Row`
factory; context-manager). Methods: `insert`, idempotent `upsert`/`upsert_many`
(`INSERT … ON CONFLICT(<key>) DO UPDATE`/`DO NOTHING`), `query`/`query_df`/
`table_df`/`count`, `execute`, `export_csv` (stdlib `csv`, no pandas dep),
`export_parquet` (pandas/pyarrow), and `fit_results_wide()`.

### 3.3 Key decision — long `fit_results` vs wide columns

The design describes namespaced result **columns** (`BING_ExpBPow_bbp`, a
parallel `BING_GIOP_bbp`, `NASA_L2IOP_bbp`). PAB stores these in a **long**
table (`fit_id, quantity, value, value_lo, value_hi, unit`): a new model pair
adds *rows*, not `ALTER TABLE` columns, keeping the schema stable as the model
library grows. `Store.fit_results_wide()` pivots to the wide, namespaced view
(`<quantity>` + `<quantity>_lo`/`_hi`, indexed by `fit_id`) at the export/report
boundary — so the design's naming is honoured where it matters.

**Tests** — `pab/tests/test_db.py`: schema version/tables, create idempotency,
insert→query round trip, idempotent upsert by matchup ID, non-key updates,
missing-key/unknown-table errors, FK + UNIQUE enforcement, CSV export equals
query, Parquet round trip, long→wide pivot.

**Docs page** — `db_schema.rst`.

**Notebook** — `docs/nb/01_database_layer.ipynb` (create → upsert → query →
export, idempotency, long→wide fit-results pivot).

---

## 4. Stage 2 — BGC-Argo ingestion & mixed-layer summary

The BGC-Argo side of the pipeline, following the Bisson et al. (2019) recipe.
Science functions take plain arrays (offline-testable); argopy is a thin,
lazily-imported seam (network only at `.load()`).

### 4.1 MLD (`pab/argo/mld.py`)

de Boyer Montégut density-threshold criterion.

- `mixed_layer_depth(pres, sig0, ref_depth=10, threshold=0.03)` — **pure NumPy**:
  shallowest depth below the reference where `SIG0` exceeds the reference-depth
  value by the threshold. Sorts shallow→deep; returns `nan` if the profile does
  not reach the reference depth or never crosses the threshold.
- `density_sigma0(pres, psal, temp, lon, lat)` — `SIG0` via TEOS-10 (`gsw`:
  `SA_from_SP → CT_from_t → sigma0`), the same computation as argopy's
  `ds.argo.teos10(['SIG0'])`.
- `mixed_layer_depth_from_ts(...)` — chains the two.
- Constants `MLD_METHOD="deBoyerMontegut_0.03"`, `REF_DEPTH`, `THRESHOLD`.

### 4.2 Summary (`pab/argo/summary.py`)

- `moving_median(values, window=3)` / `despike(...)` — NaN-aware centered moving
  median (3-pt de-spike of bubble spikes); rejects even windows.
- `iqr_inlier_mask(values, k=1.5, log=True)` — log-space 1.5×IQR outlier mask
  (Bisson); keeps all finite values when too few points to estimate quartiles.
- `mixed_layer_mean(pres, values, mld, despike_values, iqr_filter)` →
  `(mean, std, n)` over `pres <= mld`.
- `summarize_profile(pres, bbp700, chla, psal, temp, lon, lat, sig0, …)` →
  the `mld_summary` fields (no `profile_id`). Derives `SIG0` from T/S when not
  supplied (requires `lon`/`lat`).
- `persist_summary(store, wmo, cycle, summary, …)` — idempotent upsert of
  `floats` → `profiles` → `mld_summary`; stamps `created` + `pab_version`;
  returns `profile_id`.

### 4.3 Fetch (`pab/argo/fetch.py`)

`build_fetcher()` (BGC `DataFetcher`: `ds='bgc'`; default `src='gdac'` — the GDAC
netCDF read, more reliable than the flaky BGC ERDDAP, with `erddap` still
selectable; recent real-time profiles need `mode='expert'`; configurable
`params`/`measured`/`mode`), `fetch_region/float/profile()`, `filter_quality()`
(`filter_qc(QC_list=[1,2])` + optional research mode), and `iter_profiles()`
(`point2profile()` → per-profile metadata + variable arrays — the bridge into
`summarize_profile`). `DEFAULT_PARAMS`, `DEFAULT_QC` constants.

### 4.4 Q&A (`pab/argo/qa.py`)

`plot_profile()` / `save_profile_qa()` — `BBP700`/`CHLA` vs pressure with the
de-spiked overlay and MLD line. Matplotlib backend left unforced (auto-selects
Agg when headless), so importing `pab.argo` does not impose a backend on
interactive users.

**Tests** — `pab/tests/test_argo.py` (17): MLD known-answer + custom threshold +
nan/too-shallow/unsorted edge cases + T/S-path agreement; de-spike removes an
injected spike but preserves a real step; even-window rejected; mixed-layer mean
correctness + nan-MLD; IQR outlier drop; `summarize_profile` end-to-end;
lon/lat-required guard; summary row persisted + idempotent re-persist;
`build_fetcher` returns a BGC `DataFetcher` (no network); Q&A PNG produced.

**Docs page** — `argo_ingestion.rst` (pipeline overview + MLD method note citing
de Boyer Montégut 2004 and Bisson 2019).

**Notebook** — `docs/nb/02_argo_mld_summary.ipynb` (MLD, de-spike, whole-profile
summary, DB persistence, Q&A plot; optional `RUN_LIVE` argopy fetch).

**Open coverage gap.** The argopy `fetch` wrappers are network-bound, so the
offline suite tests only construction; `iter_profiles` and `fetch_*` get real
coverage once Stage 4 wires a tiny BGC fixture.

---

## 5. Stage 3 — PACE access & spectrum extraction

The satellite side: cloud-first granule access and nearest-unflagged-pixel
`Rrs` extraction. The screening and extraction work on plain arrays / xarray
(offline-testable against a synthetic granule); discovery and the S3 read are
lazily-imported, network-bound seams (mocked / construction-only in tests).

### 5.1 Flags (`pab/pace/flags.py`)

Self-contained `l2_flags` decoding (NumPy only). `L2_FLAG_BITS` (canonical
SeaDAS/OB.DAAC bit positions, matching `remote_sensing.netcdf.oc.L2_FLAGS`),
`STANDARD_OCEAN_MASK` (the design's screen), `flag_value()`, `decode()`,
`is_set()`, `flagged_mask()` (True = bad), `good_mask()` (True = unflagged).

### 5.2 Extraction (`pab/pace/extract.py`)

`haversine_km()` (vectorized great-circle distance), `nearest_valid_pixels()`
(the ~10 nearest *unflagged* pixels with ix/iy/lat/lon/distance/rank/flag),
`extract_spectrum()` → `(wave, Rrs, Rrs_unc)` at a pixel,
`extract_matchup_spectra()` (nearest pixels with spectra attached — the Stage 4
input), and `pace_noise_vector()` (wraps `ocpy.satellites.pace.gen_noise_vector`).

### 5.3 Cloud access (`pab/pace/cloud.py`)

The swappable backend producing a **canonical granule dataset** (dims
`(x, y, wl)`: `Rrs`, `Rrs_unc`; 2-D `latitude`/`longitude`; `wavelength`;
`l2_flags`). `to_granule_ds()` (attach ocpy's separate `l2_flags`), `open_local()`
(ocpy reader, dev/debug), `open_s3()` (lazy in-region read via `earthaccess.open`
→ a single `read_datatree()`/`xr.open_datatree`, including `FLH` when present),
and `open_granule(source, backend=, opener=)` dispatching
`auto`/`s3`/`local` (with `opendap` reserved → `NotImplementedError`). The
`opener` parameter is the test seam that mocks the cloud.

### 5.4 Discovery (`pab/pace/discover.py`)

`search_granules()` (`earthaccess.search_data` by short name / bbox / temporal /
cloud-cover), `granule_table()` (via
`remote_sensing.download.earthaccess.build_granule_table`), and
`persist_granules()` (idempotent upsert into the `granules` table; maps the
real `build_granule_table` columns `id`/`polygon`/`time`/`CC`/`url` onto the
schema, with schema-native names accepted as a fallback).

### 5.5 L1B hook (`pab/pace/l1b.py`)

Documented future path: `rrs_from_l1b()` raises `NotImplementedError`; provenance
tags `RRS_SOURCE_L2` (`"L2_AOP"`) vs `RRS_SOURCE_PREFIX` (`"PAB_L1B"`). Either Rrs
source feeds the same downstream fit.

### 5.6 Key decision — canonical granule dataset

Both the cloud and local readers normalise to one in-memory layout, so the
nearest-pixel extraction is *source-agnostic* — only the data source (lazy S3 vs
local file vs, later, OPeNDAP) differs. `open_granule`'s `backend`/`opener`
seam selects the source and makes the cloud read trivially mockable offline. PAB
starts with lazy-S3 (reusing the ocpy/remote_sensing readers) and leaves OPeNDAP
as a slot-in backend.

**Tests** — `pab/tests/test_pace.py` (16): flag value/decode/`is_set` and
flagged/good masks vs known bits; haversine ≈111 km/deg; nearest-pixel selection;
nearest **skips a flagged** pixel; spectrum values; matchup-spectra attachment;
all-flagged → empty; `to_granule_ds`; `open_granule` via injected opener +
opendap/unknown-backend errors; idempotent `persist_granules`; noise vector
length; L1B stub raises.

**Docs page** — `pace_access.rst` (pipeline, canonical dataset, lazy-S3 vs
OPeNDAP trade-off, the `l2_flags` screen, the L2-vs-L1B Rrs source).

**Notebook** — `docs/nb/03_pace_access.ipynb` (flag decoding, synthetic granule,
nearest-unflagged extraction; optional `RUN_LIVE` earthaccess discovery).

**Open coverage gap.** `discover.search_granules`/`granule_table` and
`cloud.open_s3` are network/S3-bound; the offline suite covers the extraction,
flags, persistence, and the `open_granule` abstraction (mocked), with the live
path exercised in the notebook.

---

## 5b. Stage 4 — Matchup engine

The first stage where the Argo and PACE halves meet: for each qualifying
profile (one with a mixed-layer summary) it finds the best PACE granule in
space + time, extracts the ~10 nearest **unflagged** `Rrs` spectra, and writes
the record linking **float ↔ granule ↔ pixels**. Geometry/time logic is pure
functions; granules arrive via the `open_granule` seam (synthetic in tests, no
network).

### 5b.1 Engine (`pab/matchup/engine.py`)

- `MatchupConfig` (frozen) — the tunable criteria: `dtime_max_hours` (default
  24 h → tighten to ~3 h), `n_spectra` (default 10), `max_distance_km` (default
  5 km), `mask_flags` (the standard ocean screen).
- `make_matchup_id(wmo, cycle, granule_id)` → `"{wmo}_{cycle}_{granule_id}"`
  (deterministic; re-runs upsert).
- `parse_time` / `time_offset_hours` — robust ISO-8601 parsing (trailing `Z`,
  naive→UTC, `datetime`/`datetime64`) and the `|Δt|`-in-hours offset.
- `find_matchup(profile, candidates, *, opener, config)` — temporal pre-filter,
  then for each candidate open the granule and select nearest unflagged pixels;
  reject if none valid or the nearest pixel is beyond `max_distance_km`. Picks
  the best by **(distance, dtime, −n_spectra, granule_id)** and returns a
  `Matchup` (or `None`).
- `write_matchup(store, matchup, *, created)` — upserts the `matchups` row
  (stamped `pab_version`/`created`) and **replaces** its `matchup_pixels`
  (delete-then-insert) so re-runs leave no stale/duplicate rows.
- `qualifying_profiles(store)` (profiles ⨝ mld_summary) and
  `candidate_granules(store, profile_time, dtime_max_hours)` (temporal
  pre-filter over the `granules` table).
- `build_matchups(store, *, opener, config, replace, created)` — the driver;
  returns `{"written", "skipped", "unmatched"}`, idempotent/resumable by
  `matchup_id`.

### 5b.2 Key decisions

- **Spatial test = nearest-pixel distance gate**, not polygon-in-footprint. The
  engine opens each temporally-near granule and accepts it only if the nearest
  *unflagged* pixel lies within `max_distance_km`. This reuses the Stage 3
  extraction unchanged and needs no WKT/shapely; a footprint bbox pre-filter is
  a future optimization (noted in `docs/matchup.rst`). Tie-break leads with
  distance because Bisson et al. find skill degrades where `Rrs` variability is
  high.
- **No schema change.** The Stage 1 `matchups`/`matchup_pixels` tables already
  fit; `SCHEMA_VERSION` stays at 1. Only unflagged pixels are selected, so
  `matchup_pixels.flagged` is always 0 (recorded for schema fidelity).
- **Spectra not stored.** `matchup_pixels` records *which* pixels were chosen
  (ix/iy + geometry); the `Rrs(λ)` arrays are re-read from the granule at fit
  time (Stage 5).

**Tests** — `pab/tests/test_matchup.py` (12): `matchup_id` format; time-offset
parsing (arg-order/`Z`); closest-granule selection; **time-window edge** (just
inside vs. just outside); distance-gate rejection of a far footprint;
**flagged-nearest-pixel exclusion**; all-flagged → `None`; persisted links with
correct FKs/`n_spectra`/`distance_km`/`dtime_hours` + **idempotent re-run** (no
dupes); unmatched when out of window; **missing-position guard** (`find_matchup`
raises, `build_matchups` skips → unmatched); `write_matchup` requires
`profile_id`. The cloud layer is mocked via injected `opener=` synthetic
granules.

**Docs page** — `matchup.rst` (criteria, selection/tie-break rule, `matchup_id`
scheme, float↔granule↔pixels linkage, source-agnostic testing; autodoc of
`pab.matchup.engine`).

**Notebook** — `docs/nb/04_matchup.ipynb` (synthetic granule → seed profile +
granule → `build_matchups` → selected pixels & records → idempotent re-run →
flagged-pixel exclusion; optional `RUN_LIVE` real float↔PACE matchup).

**Dev data.** `data/dev_profiles.csv` — the fixed 10-profile development set (2
JXP-confirmed PACE-matchup seeds + 8 random PACE-era cycles across two floats /
biomes), with `data/README.md`. The argopy `fetch`/`iter_profiles` and
`discover`/`open_s3` seams remain network-bound (exercised in the notebook's
`RUN_LIVE` path), so the offline suite still covers them only via construction /
mocks.

---

## 5c. Stage 5 — BING fitting wrapper

Fits the matchup `Rrs` spectra with `bing` and stores the retrieved IOPs (above
all non-water backscatter `b_bp`, the BGC-Argo matchup observable) with full
posterior uncertainties. `bing`/`emcee` are a lazily-imported seam; the
array-level science is pure and offline-tested.

### 5c.1 Models (`pab/fit/models.py`)

- `FitConfig` (frozen) — `model_pair` (default `"ExpBPow"`), `satellite`,
  `nsteps=10000`, `nburn=1000`, `wave_min/max=400/700`, `variable_Gordon=False`,
  `include_Raman=False`, `analysis_burn=7000`, `perc=(5,95)`.
- `build_models(config, wave)` → `(p, rt_dict, models)` via
  `bing.parameters.standard.<combo>` + `rt.defs.rt_dict_from_p` +
  `models.utils.init` + `priors.set_standard_priors`. `BING_COMBO` maps the PAB
  label to the bing factory (`ExpBPow → expb_pow`).

### 5c.2 Run (`pab/fit/run.py`)

- Pure helpers: `make_fit_id` (`"{matchup_id}_{ix}_{iy}_{model_pair}"`),
  `prepare_spectrum` (window + `varRrs` from `Rrs_unc**2`, 2% floor),
  `extract_quantities` (posterior → median + credible band for each free
  parameter, linearised out of log space, plus derived `bbp`/`anw`/`adg` at
  440/700 nm).
- `fit_spectrum(wave, Rrs, Rrs_unc, *, Chl, Y, config)` — LM warm-start
  (`chisq_fit.fit`, falls back to the initial guess) → MCMC (`inference.fit_one`,
  keeping the sampler for the acceptance fraction) → `FitSpectrumResult` (chains,
  quantities, reduced `chisq`/`aic`/`bic`, `accept_frac`, `success`). The `Chl`
  only **seeds** the Bricaud `a_ph` shape — the fit *retrieves* Chl from the
  posterior `Aph` (`chl_from_aph`: `Chl = 10**Aph / 0.05582`), emitted as the
  `chl` quantity.
- `fit_matchup(store, matchup_id, …)` — re-reads the pixel `Rrs` from the granule
  (via `pace.cloud`/`pace.extract`), passes the float's mixed-layer `chla` as
  `Chl` (guarded by `finite_or_none`, since a NaN `chla` would poison
  `set_aph`), fits, writes chains + rows. `build_fits(store, …)` runs the nearest
  pixel of every matchup, idempotent/resumable by `fit_id`, and records a matchup
  that fails to fit under `"failed"` rather than aborting the batch.

### 5c.3 Artifacts (`pab/fit/artifacts.py`)

- `save_chains`/`load_chains` — NPZ keyed by `fit_id` under
  `PAB_DATA_DIR/fit_chains/` (chains stay out of the DB; `fits.chains_path`
  points to them).
- `persist_fit(...)` — upserts the `fits` row (config + diagnostics +
  provenance: `pab_version`, `created`, `pkg_versions`) and the namespaced
  `fit_results` rows (`BING_<model_pair>_<quantity>`); replaces a fit's prior
  quantities (delete-then-insert) so re-runs leave no stale rows.

### 5c.4 Key decisions

- **`b_bp` via the bb_nw model**, not `reconstruct_from_chains` (which returns
  *total* a/bb and burns 7000 steps): PAB evaluates `models[1].eval_bbnw` on the
  posterior bb-params, so it gets the non-water backscatter directly and
  controls the analysis burn (falling back to `nsteps // 2` for short chains —
  this is what makes a toy-size MCMC testable).
- **No schema change** — the Stage 1 `fits`/`fit_results` tables already fit;
  `SCHEMA_VERSION` stays at 1. Quantities are namespaced so a second model pair
  adds rows, not columns.
- **Lighter MCMC than BING's research default** (`nsteps=10000`) — documented in
  `fitting.rst`.

**Tests** — `pab/tests/test_fit.py` (10): `make_fit_id`; `finite_or_none` (the
NaN-`chla` guard); `chl_from_aph` (Chl = 10**Aph / 0.05582); `prepare_spectrum` window/variance/empty-window; `persist_fit`
links + namespaced quantities + idempotent re-run; `build_fits` records a failed
matchup without aborting the batch; `save_chains`/`load_chains` round trip; and a
**known-answer recovery** (synthetic noise-free `Rrs` via `calc_Rrs`, short MCMC,
`importorskip("bing"/"emcee")`) checking `b_bp(700)` within tolerance — it
`skip`s when BING's external Loisel aph-basis data file is unavailable.

**Docs page** — `fitting.rst` (pipeline, the `BING_<model_pair>_<quantity>`
schema, MCMC settings, provenance/artifacts, matchup linkage; autodoc of
`pab.fit.*`).

**Notebook** — `docs/nb/06_fit.ipynb` (synthetic spectrum → LM→MCMC → posterior
`b_bp` + fit figure → persisted `fits`/`fit_results`; optional `RUN_LIVE`
real-matchup fit). Executed offline-safe at toy MCMC size.

---

## 5d. Stage 6 — Metrics & figures

Turns the per-matchup BING fits into the satellite-vs-Argo `b_bp` comparison (and
a Chl comparison via a satellite OC4 source) and the figures that make matchups
and the population inspectable. Metric math is pure; granule reads and the `bing`
reconstruction are mockable/lazy seams.

### 5d.1 Metrics (`pab/metrics/compare.py`)

- `log_comparison(sat, insitu)` — **quantity-agnostic, pure**: finite/positive
  pairs only; returns `n`, median ratio + IQR, Spearman ρ, log-space bias, and
  RMS/MAD of `log10(sat/insitu)`. Serves `b_bp`, Chl, and BING-vs-NASA alike.
- `gather_matchups(store, model_pair="ExpBPow")` — one row per matched fit:
  satellite `BING_*_bbp700` and `BING_*_chl` (both BING-retrieved, + bounds),
  Argo `bbp700`/`chla`, `chisq`, position, time. `compare(df, sat_col,
  insitu_col)` runs the metric on two columns (so `bbp_bing`-vs-`bbp_argo` and
  `chl_bing`-vs-`chla_argo` use the same code).
- `add_strata(df)` — `season` (month) + `region` (latitude band); the `Rrs`
  spatial-variability axis is deferred (the box `Rrs` spread isn't persisted).
- `add_oc_chl(df, store, opener=)` — an **OC4** band-ratio Chl
  (`ocpy.chl.band_ratios.oc4` on the matchup pixel `Rrs`), an optional independent
  cross-check on the BING-retrieved `chl_bing`.

### 5d.2 Figures (`pab/plotting/`)

- `scene.py` — `scene_quicklook(ds, lat, lon, …)` / `scene_from_store(...)`:
  default **false-color RGB composite** (`false_color_rgba`: `Rrs` at three
  wavelengths → R/G/B, **shared-scale** brightness + gamma so natural ocean
  colour is preserved, not per-channel stretched), with a single-band `mode="band"`
  view; the float is marked, analyzed pixels circled, and the `l2_flags` mask
  greyed. Pure NumPy/Matplotlib + `pab.pace.flags`;
  `locate_float_pixel` is a tested pure helper.
- `population.py` — `comparison_scatter(df, sat, insitu)` (log-log + 1:1 +
  median-ratio lines, annotated with the metrics) and `matchup_map(df)`.
- `fit_fig.py` — `fit_figure(store, fit_id)`: reconstructs the fit from its
  chains NPZ (`artifacts.load_chains` + `build_models`) and shows observed-vs-
  model `Rrs` and the retrieved `b_bp(λ)` band; PAB's own ~100 KB two-panel
  figure (the `bing.plotting`/`plot-bing-fit` *concept*, not its code).

### 5d.3 Key decisions

- **Metrics computed on demand**, not persisted: cheap to recompute from
  `fit_results`/`mld_summary`, so no `metrics` table and **no schema change**
  (`SCHEMA_VERSION` stays 1); aggregate presentation belongs to Stage 7.
- **Chl is retrieved, not input.** The `ExpBPow` fit *seeds* `a_ph` with the Argo
  `Chl` but recovers Chl from the posterior `Aph` (`Chl = 10**Aph / 0.05582`),
  emitted as `BING_*_chl` — so the Chl comparison (`chl_bing` vs Argo `chla`) is
  a genuine retrieval-vs-in-situ test, parallel to `b_bp`. An OC4 band-ratio Chl
  is an optional independent cross-check.
- **Wavelength offset** handled by comparing at 700 nm (BING reports `b_bp(700)`
  directly); the NASA-baseline 442 nm comparison is flagged as approximate.
- **`gather_matchups` filters `fits` by `model_pair`** (`AND f.model_pair = ?`),
  so a second model pair (or other fits) on the same matchup yields one row, not
  duplicates.
- **NASA L2 IOP baseline is deferred** (not ingested). BING-vs-Argo (`b_bp`,
  Chl) is implemented; BING-vs-NASA awaits an `ocpy.pace.io.load_iop_l2` ingest
  that populates `NASA_L2IOP_*` — a thin lazy seam the quantity-agnostic metric
  slots into. Documented in `metrics.rst`.

**Tests** — `pab/tests/test_metrics.py` (11): `log_comparison` known-values +
NaN/nonpositive handling; `season_of`/`region_of`; `gather_matchups` + `compare`
(bbp + chl) + `add_strata` on a seeded DB; **`gather_matchups` filters by
`model_pair`** (a 2nd-pair fit doesn't duplicate the row); `add_oc_chl` via an
injected granule;
`locate_float_pixel`; `false_color_rgba` (normalised RGBA + greyed flags); the
scene (RGB + single-band) and population figures render within the ~100 KB
budget; and a `bing`-guarded fit-figure smoke (skips when the Loisel data is
absent).

**Docs page** — `metrics.rst` (the three estimates, metric definitions,
wavelength offset, figures + budget, stratification; autodoc of `pab.metrics.*` /
`pab.plotting.*`).

**Notebook** — `docs/nb/07_metrics.ipynb` (log-space metrics, stratified median
ratios, the satellite-vs-float scatter, and a scene quick-look on a synthetic
population; optional `RUN_LIVE`). Executed offline-safe.

---

## 5e. Stage 7 — Reporting

Turns the SQLite store + per-matchup artifacts into community products: a static
site of **aggregate** pages, standalone **Bokeh** interactive figures, downloads
+ a manifest, and a citable snapshot. The build runs **end-to-end offline** —
the object-store / Zenodo uploads are stubbed and config-gated. `healpy`/`bokeh`
are lazily-imported seams; the aggregation math and manifest are pure.

### 5e.1 Aggregation (`pab/report/aggregate.py`)

- `aggregate_by(df, by, …)` — per-bin `log_comparison` over region/season (and
  `magnitude_bins`). Pure pandas.
- `nside_for_cell_size` (wraps `remote_sensing.healpix.utils`), `assign_healpix`
  (`healpy.ang2pix` lonlat), and `aggregate_healpix(df, …)` — per-HEALPix-cell
  stats with cell-centre `lon`/`lat` (lon wrapped to [-180, 180]). Equal-area,
  resolution-tunable, scales independently of matchup count.

### 5e.2 `.rst` generation (`pab/report/rst.py`)

- `rst_table` (static `list-table`), `summary_page`/`aggregates_page`/
  `methods_page`/`index_page`, and `build_site(store, outdir)` — writes the
  **fixed** `PAGE_STEMS` set **plus a Sphinx `conf.py`** (a self-contained,
  buildable reporting site, separate from the dev docs:
  `sphinx-build <outdir> <outdir>/_build`). The binned tables are **sortable**
  Bokeh `DataTable` embeds when `bokeh` is present (`aggregates_page(sortable=)`),
  falling back to a static `list-table`. **No per-matchup page** is ever emitted.

### 5e.3 Interactive (`pab/report/interactive.py`)

- `comparison_scatter` (log-log sat-vs-float + 1:1 line, hover, optional
  tap→artifact URL, `output_backend="webgl"`), `matchup_map`, `stats_table` (a
  **sortable** `DataTable`), and `embed`/`raw_html` (`bokeh.embed.components` →
  standalone script+div for a `.. raw:: html` block; no Bokeh server).

### 5e.4 Publish (`pab/report/publish.py`)

- `export_tables` (summary CSV/Parquet; the raw SQLite file is **not** a
  published download), `file_checksum` (SHA-256), `build_manifest` (one row per
  per-matchup artifact: `matchup_id`→URL+checksum, stamped `pab_version`), and
  `publish_release` (exports + manifest + stub "uploads", writes `manifest.json`
  with `pkg_versions`). `LocalStubBackend` copies to the filesystem (no network);
  `NautilusS3Backend`/`ZenodoBackend` are explicit `NotImplementedError` stubs
  (deferred, config-gated).

### 5e.5 Key decisions

- **Aggregate pages only** — `build_site` returns the fixed `PAGE_STEMS` (+ a
  `conf.py`) regardless of matchup count; a test asserts no per-matchup
  explosion, and another **builds the generated site** with `sphinx-build`.
- **Sortable tables** — the binned tables are Bokeh `DataTable` embeds (sortable
  on a static page); a static `list-table` is the no-`bokeh` fallback.
- **Publish stubbed** — interfaces implemented against the filesystem so the
  build is fully offline; real Nautilus S3 / Zenodo uploads are deferred behind a
  later config gate.
- **No schema change** — reporting reads the existing store + `fits.chains_path`/
  `figure_path`; metrics stay computed on demand.

**Tests** — `pab/tests/test_report.py` (14): `aggregate_by` region bins;
`magnitude_bins`; `aggregate_healpix` (cell assignment + centres,
`importorskip("healpy")`); `build_site` emits exactly `PAGE_STEMS` (+ `conf.py`,
no per-matchup page) + summary content + the static `list-table` fallback;
**sortable `DataTable` embed** when bokeh present; **`build_site` degrades
gracefully without `healpy`/`bokeh`** (HEALPix table omitted with a note — the
lean-CI regression); the **generated site builds** under `sphinx-build`;
`stats_table` columns are sortable; `rst_table` rendering;
Bokeh `comparison_scatter`/`embed`; `export_tables` round-trip; `build_manifest`
id↔URL+checksum+`pab_version` and `LocalStubBackend` copies-not-network;
`publish_release` writes the manifest; the real S3/Zenodo backends raise
`NotImplementedError`.

**Docs page** — `reporting.rst` (aggregate-not-per-matchup rationale, HEALPix,
interactive embed, downloads/manifest, stubbed publish + config gate, how to
publish a release; autodoc of `pab.report.*`).

**Notebook** — `docs/nb/08_reporting.ipynb` (region/season + HEALPix aggregates,
an aggregate `.rst` page, a standalone Bokeh embed, and a download manifest with
stubbed local publishing on a synthetic store). Executed offline-safe.

---

## 6. Cross-cutting conventions (as implemented)

- **Provenance** — every results-bearing row carries `pab_version` + `created`;
  `pab.config.package_versions()` supplies the environment snapshot for fit
  records (Stage 5 will store it in `fits.pkg_versions`).
- **Idempotency** — all writes go through `Store.upsert*`, keyed by each table's
  natural key, so stages are re-runnable/resumable.
- **Testing** — pure-array science functions are unit-tested offline with known
  answers; heavy/network seams are imported lazily and mocked or construction-
  only in tests. Target: every stage ships code + tests + a docs page.
- **Lint/format** — `ruff` (checks + format) clean; Google-style docstrings.
- **Notebooks** — each stage ships an explanatory notebook in `docs/nb/`
  (per the coding plan); built and executed offline-safe so they carry outputs,
  with any live-data section guarded behind a `RUN_LIVE` flag. They are
  **rendered into the Sphinx/RTD site** via `myst-nb` (`nb_execution_mode =
  "off"`, so the build uses the committed outputs) and reachable from a
  *Notebooks* toctree and from the relevant stage pages.
- **Units** — m / m⁻¹ / sr⁻¹ / mg m⁻³ / PSU / °C / nm / km / hours; ISO-8601
  timestamps. (Full table in `docs/db_schema.rst`.)

---

## 7. Module index (current)

```
pab/
  config.py            ✅ pab_version, paths, package_versions
  db/
    schema.py          ✅ DDL, SCHEMA_VERSION, UPSERT_KEYS, migrate
    store.py           ✅ Store: upsert/query/export/fit_results_wide
  argo/
    mld.py             ✅ de Boyer Montégut MLD (pure + TEOS-10)
    summary.py         ✅ despike, IQR, mixed-layer mean, summarize, persist
    fetch.py           ✅ argopy seam (build_fetcher, fetch_*, iter_profiles)
    qa.py              ✅ profile Q&A plots
  pace/
    flags.py           ✅ l2_flags decode + standard ocean mask
    extract.py         ✅ nearest-unflagged pixel + Rrs spectra + noise vector
    cloud.py           ✅ canonical granule ds; lazy-S3 / local backends
    discover.py        ✅ earthaccess discovery + granule table + persist
    l1b.py             ✅ documented L1B->Rrs hook (future)
  matchup/
    engine.py          ✅ space+time match, pixel selection, record writing
  fit/
    models.py          ✅ FitConfig + BING model-pair/prior build seam
    run.py             ✅ LM→MCMC fit, quantity extraction, matchup drivers
    artifacts.py       ✅ NPZ chains + fits/fit_results persistence
  metrics/
    compare.py         ✅ log-space metrics, gatherers, strata, OC4 Chl
  plotting/
    fit_fig.py         ✅ per-matchup fit figure (reconstructed from chains)
    scene.py           ✅ per-matchup scene quick-look (float + pixels + flags)
    population.py      ✅ sat-vs-float scatter, matchup map
  report/
    aggregate.py       ✅ region/season + HEALPix aggregation
    rst.py             ✅ aggregate .rst pages (no per-matchup pages)
    interactive.py     ✅ standalone Bokeh scatter/map (embed)
    publish.py         ✅ exports + download manifest + stubbed backends
  pipeline.py          ⬜ Stage 8
  tests/               test_smoke, test_db, test_argo, test_pace, test_matchup, test_fit, test_metrics, test_report
```

---

*Living document; updated at the close of each stage.*
