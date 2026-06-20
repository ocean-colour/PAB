# PAB Implementation Record

**Version:** 0.2.0
**Date:** 2026-06-20
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
| 4 | Matchup engine | ⬜ pending | `pab.matchup.*` (stub) |
| 5 | BING fitting wrapper | ⬜ pending | `pab.fit.*` (stub) |
| 6 | Metrics & figures | ⬜ pending | `pab.metrics.*`, `pab.plotting.*` (stubs) |
| 7 | Reporting | ⬜ pending | `pab.report.*` (stub) |
| 8 | End-to-end pipeline & CLI | ⬜ pending | `pab.pipeline` (stub) |
| 9 | Extensibility & options | ⬜ future | — |

**Environment notes.** Workstation Python is 3.14.5 (plan floor 3.12);
`bing`, `ocpy`, `remote_sensing`, `argopy`, `earthaccess`, `gsw`, `pandas`,
`pyarrow` are all installed locally. CI installs the package + `pytest` and runs
a `-W` docs build; the test suite is fully offline (no network/S3).

**Verification (current).** `pytest` → 59 passed; `ruff check pab` and
`ruff format --check pab` → clean; `sphinx-build -W` → build succeeded.

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

`build_fetcher()` (BGC `DataFetcher`: `ds='bgc'`, `src='erddap'`, configurable
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
+ grouped netCDF), and `open_granule(source, backend=, opener=)` dispatching
`auto`/`s3`/`local` (with `opendap` reserved → `NotImplementedError`). The
`opener` parameter is the test seam that mocks the cloud.

### 5.4 Discovery (`pab/pace/discover.py`)

`search_granules()` (`earthaccess.search_data` by short name / bbox / temporal /
cloud-cover), `granule_table()` (via
`remote_sensing.download.earthaccess.build_granule_table`), and
`persist_granules()` (idempotent upsert into the `granules` table).

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
  with any live-data section guarded behind a `RUN_LIVE` flag.
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
  matchup/             ⬜ Stage 4
  fit/                 ⬜ Stage 5
  metrics/             ⬜ Stage 6
  plotting/            ⬜ Stage 6
  report/              ⬜ Stage 7
  pipeline.py          ⬜ Stage 8
  tests/               test_smoke, test_db, test_argo
```

---

*Living document; updated at the close of each stage.*
