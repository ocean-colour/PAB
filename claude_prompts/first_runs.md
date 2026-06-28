# Running PAB for the first time

## Goals

Start our first runs of PAB

## Claude

### Skills

Reporting-style glue over the existing modules; a couple of fitting skills inform
the batch stage:

- **`batch-fit-argo`** — the batch/parallel-fit + checkpointing pattern (mirrors
  `pab.fit.build_fits` over the population; BING `fit_batch` across cores).
- **`run-bing-fit`** — the per-spectrum fit the batch stage invokes.

### Working agreements (unchanged from Stages 0–7)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written; do **not** copy
  the one-off `bing/papers/biomass/Analysis` scripts. Stage 8 should call the
  existing stage functions, not re-implement them.

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md` → *Semi-automation* (the stage runner:
  idempotent stages skipping completed work, store-in/store-out, single-matchup
  debug vs full batch, BING `fit_batch` for the heavy fits) and *Provenance &
  versioning* (every result stamped with `pab_version`; re-running under a new
  version produces a new record, not a silent overwrite).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 8* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current state;
  the per-stage seams the runner chains; update it at the close of this stage).
- **Existing PAB seams the runner chains (all already implemented):**
  - `pab.argo.{fetch,summary}` — fetch BGC profiles + persist mixed-layer
    summaries (`persist_summary`, idempotent). `data/dev_profiles.csv` is the dev
    selection.
  - `pab.pace.{discover,cloud}` — `search_granules`/`granule_table`/
    `persist_granules` (the candidate set) and `open_granule` (the `opener=` test
    seam).
  - `pab.matchup.build_matchups(store, opener=, …)` — space+time match → records
    (idempotent/resumable, returns `{written, skipped, unmatched}`).
  - `pab.fit.build_fits(store, opener=, …)` — LM→MCMC per matchup, chains NPZ +
    `fits`/`fit_results` (idempotent by `fit_id`, returns `{written, skipped,
    failed}`).
  - `pab.plotting.{fit_fig,scene}` — per-matchup figures (write to `fits.figure_path`).
  - `pab.report.{build_site,publish_release}` — the aggregate site + downloads.
  - `pab.db.store.Store` — the shared state every stage reads/writes; `pab.config`
    (`pab_version`, `DATA_DIR`, `package_versions`).

## Prompts

1. Execute the first task in Tasks below
2. Execute the 2nd task in Tasks below

4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below
6. Execute the 6th task in Tasks below
7. Execute the 7th task in Tasks below


## Tasks

1. I have tried to run `pab` for the first time with this command: "pab --db data/pab.db" as per the `HOWTO.md` doc.  It crashed out.  Please try it yourself and investigae.  Report on your findings below in the Report section.  If you have any questions, ask them in Q&A.  Log your work.

2.  It ran further this time.  Can you view `pab_error_00.md` and see what you can do?

3. Read my answer to the Q&A below and modify the code accordingly.  If you have any additional questions, put them in the Q&A.  Log your work.  

4. Can you check the `HOWTO.md` file?  I just tried running `pab --db data/pab.db` and it failed saying "FileNotFoundError: [Errno 2] No such file or directory: '/mnt/tank/Oceanography/python/PAB/data/dev_profiles.csv'".  I don't see why it is looking for that file.  My $PAB_DATA_DIR variable is set.

5. I ran the report.  How do I view it?  

6. I have now viewed the report.  There are no figures.  Was this as expected?  I am sure our design included figures in the Reports.  Please advise

7. This looks great now!  Remind me, were we planning to stage this on `readthedocs` or GitHub?  Either way, how do I do so?

### Q&A

(Task 1 — no blocking questions; see the recommendation in the Report.)

**Q (Task 2): How should we make PACE granule access reliable?**

The lazy-read fix works, but running the `match` stage **out-of-region from this
workstation** can hang indefinitely on a stalled HTTPS byte-range read (the
2h+/0% CPU wedge described in the Task 2 report). Pick a path (answer inline
below):

- **A — Add timeout + retry.** I add an aiohttp read-timeout and bounded retry
  around the cloud read so a stalled connection fails fast and retries instead of
  hanging. Mitigation only — out-of-region reads stay slow (~21 s/granule), but
  the stage completes instead of wedging. Smallest change; keeps the lazy-cloud
  design.
- **B — Pre-download granules.** I add a step that downloads the candidate
  granules to disk once, then `match` reads them via the existing fast/reliable
  `open_local` backend. Reliable off-cloud; costs disk + an explicit download
  step. Best for local dev on this workstation.
- **C — Run in-region (us-west-2).** You run the pipeline on an AWS instance in
  `us-west-2` so `open_s3` reads S3 directly (the original design target). Fastest
  and most reliable; requires cloud compute, no code change from me now.
- **D — Stop here.** Leave the two fixes as-is and decide the access strategy
  later.

My recommendation: **C** if you can run in-region, otherwise **B** for local dev
(optionally plus **A** as a safety net).

**Your answer:**  For the small sample run, let us pre-download the granules.  Otherwise use option C.


### Reports

#### Task 1 — `pab --db data/pab.db` crash investigation

**Verdict: not a PAB bug.** The crash was a *transient* HTTP 500 ("An Internal
Error has occurred.") returned by NASA's CMR granule-search service during the
`discover` stage. Re-running succeeds — the pipeline is fine.

**What happened.** Reproduced the crash on the first run. The traceback:

```
pab/pipeline.py:370 main → run(...)
pab/pipeline.py:313 run  → discover(store, config)
pab/pipeline.py:182 discover → disc.search_granules(...)
pab/pace/discover.py:44 → earthaccess.search_data(...)
earthaccess/search.py:444 hits() → raise RuntimeError(...)
requests.exceptions.HTTPError: 500 Server Error for url:
  https://cmr.earthdata.nasa.gov/search/granules.umm_json?short_name=PACE_OCI_L2_AOP
  &temporal[]=2025-01-24T13:01:02Z,2025-01-26T13:01:02Z
  &bounding_box=-137.1154,3.5475,-136.3154,4.3475&cloud_cover=0,100&page_size=0
RuntimeError: {"errors":["An Internal Error has occurred."]}
```

The `ingest` stage completed first; the failure is at the very next stage,
`discover`, on `earthaccess.search_data` → `query.hits()` (the `page_size=0`
count request).

**Confirmed transient.** Hitting the exact failing URL directly now returns
`200` (both `page_size=0` and `page_size=10`), with `CMR-Hits: 4` for that
profile. Re-running the stage cleanly succeeds:

```
$ pab --db data/pab.db --stage discover
  discover: {'granules_upserted': 38, 'skipped': []}
```

So the 4 candidate granules per profile resolve and 38 were upserted across the
dev set — the pipeline gets past the point of failure with no code change.

**Robustness gap (recommended fix).** `pab.pace.discover.search_granules` calls
`earthaccess.search_data` with no retry/backoff, and `earthaccess` does not
retry CMR 500s itself. A single transient CMR hiccup therefore aborts the entire
run. Suggest wrapping the CMR query in a small retry-with-backoff (e.g. 3–4
attempts, exponential sleep) so the common case — CMR being briefly flaky —
self-heals instead of crashing the operator's first run. (Discover is also the
only stage exercised live against an external service mid-pipeline, so it's the
natural place to harden.) Happy to implement this if you'd like.

#### Task 2 — `pab_error_00.md`: granule open pulled the whole cube over HTTP

**Verdict: a real PAB bug, now fixed.** With discover working, the run reached
the `match` stage and died opening a granule. The traceback bottoms out in an
`aiohttp.ClientResponseError` raised mid byte-range fetch
(`fsspec/http.py async_fetch_range → raise_for_status`) while reading
`geo["Rrs_unc"].values` in `pab/pace/cloud.py:read_datatree`.

**Root cause.** `read_datatree` built the canonical dataset by calling `.values`
on **every** variable — including the full `Rrs` and `Rrs_unc` cubes
(`1710 × 1272 × 172` int16, ~0.75 GB each). That eagerly downloads the entire
granule (~1.5 GB) over HTTP **before** the nearest-pixel extraction ever runs —
directly contradicting the module's own design promise ("only the requested
bytes transfer … a nearest-pixel read does not pull the full cube"). The
`extract` module is already lazy-friendly: `nearest_valid_pixels` only needs the
small 2-D lat/lon/flags, and `extract_spectrum` does `ds["Rrs"].isel(x,y).values`
for a *single* pixel. Eager `.values` in `read_datatree` defeated that.

Out-of-region (this workstation is not in `us-west-2`), `earthaccess.open`
returns HTTPS file handles, so pulling 1.5 GB via thousands of byte-range
requests either stalls for many minutes or trips a transient
`ClientResponseError` — which is exactly the logged crash. I reproduced the
precursor directly: `l2_flags` read in 5 s, then `Rrs.values` hung past the
timeout.

**Fix (implemented).** Made `read_datatree` lazy — it now wraps the on-disk
`Rrs`/`Rrs_unc` variables (renamed to `(x, y, wl)`) via `.variable` instead of
`.values`, so the cubes stay lazy and `extract`'s per-pixel `isel().values`
fetches only the ~5 HDF5 chunks (`(32, 256, 40)`) covering that pixel — a few MB
instead of ~1.5 GB. Also added `decode_timedelta=False` to silence a
`FutureWarning`. See `pab/pace/cloud.py`.

Running the full `match` stage then surfaced a **second** bug the eager code had
hidden: the dims are renamed **by position**, not by source name. PACE groups can
name the same axis differently — the spectral dim is `wavelength_3d` in
`geophysical_data` but `wavelength` in `sensor_band_parameters` on some granules
— so a single shared dim map crashed (`cannot rename 'wavelength'`). The original
`.values`/positional-`dims=` construction was immune to this; the lazy rewrite
must be too. The fix renames each variable using its own `dims` positionally
(`_canon(da, target_dims)`), exactly mirroring the old positional behaviour.

**Verified.**
- `pab/tests/test_pace.py` — 17 passed.
- Real granule, out-of-region HTTPS: single-pixel `Rrs` read ~3 s (was: full
  cube hang); `open_granule` ~21 s; `extract_matchup_spectra(n=3)` ~22 s,
  returning valid ocean `Rrs` (~0.0138 sr⁻¹) with finite `Rrs_unc` at 3.3 km.

**Caveats / follow-ups.**
- ⚠️ **Out-of-region HTTPS access can hang indefinitely — likely a blocker for
  running the real `match` stage from this workstation.** After the fix, a full
  `pab --stage match` run wedged for **2h+ at ~0% CPU with zero matchups
  written**. Diagnosis: the process was blocked on a futex
  (`wchan=futex_wait_queue`) inside `fsspec`'s sync-over-async wrapper, with a
  stalled HTTPS connection to the AWS data host (≈4 MB stuck in the socket
  recv-queue, a second connection in `CLOSE-WAIT`). `fsspec`/`aiohttp` is opened
  by `earthaccess` with **no read timeout**, so a single stalled byte-range read
  blocks forever. The lazy fix is necessary and correct (it removes the ~1.5 GB
  full-cube pull), but it does not by itself make out-of-region cloud reads
  *reliable*. **Recommended path forward (needs your call):**
  1. Run the pipeline **in-region on AWS `us-west-2`** so `open_s3` reads S3
     directly (the design target) — fastest and most reliable; or
  2. **Pre-download** the candidate granules once and use the `local` backend
     (`open_local`) — reliable off-cloud, at the cost of disk + an explicit
     download step; or
  3. Add an **aiohttp read timeout + bounded retry** around the cloud read so a
     stalled connection fails fast and is retried instead of hanging (mitigation,
     not a speed fix — and out-of-region it will still be slow).

  My recommendation: (1) if you can run in-region, else (2) for local dev. I held
  off implementing (2)/(3) pending your preference.
  **→ Resolved in Task 3:** you chose **pre-download (2)** for small sample runs,
  **in-region (1)** otherwise. Implemented as the `--download` flag (see the
  Task 3 report below).
- *Even when it does not hang, it is slow out-of-region.* The dominant cost is
  the ~21 s `xr.open_datatree` HDF5-header read over HTTP, paid once per granule
  open; the engine opens every time-qualifying candidate.
- A benign `Exception ignored in ... File.close` finalizer message from
  `h5netcdf`/`h5py` can appear at interpreter exit now that the file handle stays
  open for lazy reads. It is harmless (post-results, during GC) but cosmetic; we
  could close datasets explicitly in the matchup loop if we want it gone.

#### Task 3 — implemented option B (pre-download) + keep C (in-region)

Per your answer ("for the small sample run, pre-download; otherwise option C"),
added a reliable **off-cloud** granule-access path and left the in-region S3 path
(`open_s3`) as the default for `us-west-2`.

**What I added.**
- `pab/pace/cloud.py`:
  - `download_granule(source, cache_dir, *, replace=False)` — idempotent
    streaming download via `earthaccess.download` (the robust path; no fsspec
    byte-range stalls). A cached granule is reused; a local-path source is passed
    through untouched.
  - `granule_cache_path(source, cache_dir)` — stable cache path from the granule
    basename (PACE L2 basenames are unique).
  - `cached_opener(cache_dir, *, download=True)` — an `opener` (the existing
    `build_matchups`/pipeline seam) that ensures the granule is local, then reads
    it with the fast/reliable `open_local` (ocpy). `download=False` requires a
    pre-populated cache.
- `pab/pipeline.py`: new `PipelineConfig.download` / `cache_dir` (+ `cache()`),
  CLI `--download` / `--cache-dir`, and `run()` builds the cached opener when
  `--download` is set and no opener is injected (the test seam still wins). The
  opener flows to `match`/`fit`/`figure` via the existing seam.
- `HOWTO.md`: documented the flags and an "in-region vs `--download`" section.
- Tests: `pab/tests/test_pace.py` (cache path, idempotent skip, opener
  download-then-open, local passthrough, `download=False` raises) and
  `pab/tests/test_pipeline.py` (cache dir default/override; `run()` wires the
  cached opener when `download=True`). **35 passed.**

**Verified on real data (out-of-region).** `download_granule` fetched a real
granule in ~33 s; a second call was an instant cache hit; `cached_opener` →
`open_local` opened it in ~14 s with correct dims `(1710, 1272, 172)`; extraction
of 3 spectra took ~0.1 s (local — no network) and returned the same valid `Rrs`
(0.013794 …) as the lazy cloud read. Then ran `pab --db data/pab.db --stage match
--download` end-to-end: it **completed reliably with no hang** (vs the 2h+ wedge
before the fix), downloading all **38/38** candidate granules (~15 GB) and writing
**4 matchups / 40 pixels**:

| matchup | dist (km) | Δt (h) | n |
| --- | --- | --- | --- |
| 7902226/5  → PACE 20250219T155847 | 0.45 | 19.56 | 10 |
| 7902226/21 → PACE 20250730T153750 | 0.32 | 13.40 | 10 |
| 7902226/27 → PACE 20250928T162134 | 0.29 |  3.13 | 10 |
| 7902226/42 → PACE 20260226T154741 | 0.58 |  0.71 | 10 |

All four are sub-km with 10 spectra each — clean matchups for float **7902226**.

**Observation (not a bug, worth a look later):** all 5 profiles of float
**7902136** came back *unmatched* despite each having 4 candidate granules, as did
**7902226/51** (which had 0 candidates). For 7902136 the granules were downloaded
and opened fine, so the float simply fell outside every candidate footprint, or
its nearest pixels were flagged / beyond `max_distance_km`. Suggest a quick triage
of 7902136 (footprint vs float position, flag masking) before the full fit run.

Usage:

```bash
pab --db data/pab.db --download          # off-cloud: pre-download + local read
pab --db data/pab.db                      # in-region us-west-2: lazy S3 (default)
```

#### Task 6 — report had no figures: wired the interactive + per-matchup figures in

**Verdict: partly expected, partly a real gap (now fixed).** Two kinds of figure
were designed in:

- **Per-matchup fit/scene PNGs inline** — *deliberately absent*. The design's hard
  constraint (no per-matchup pages at ~10⁴ matchups) means these are reached on
  demand, not embedded. So not seeing them on their own pages was correct.
- **Interactive Bokeh figures (sat-vs-float `b_bp` scatter + matchup map)** —
  *genuinely missing*. `pab.report.interactive` implemented `comparison_scatter`
  and `matchup_map`, and `docs/reporting.rst` documented them as part of the site,
  but `build_site`/`aggregates_page` only ever embedded the stats `DataTable`s
  (`interactive.stats_table`). The promised figures were never wired into page
  generation.

**Fix (implemented in `pab/report/rst.py`).**
- `interactive_figures(df)` — embeds the `comparison_scatter` (hover + **tap a
  point to open that matchup's fit figure**) and `matchup_map` (coloured by the
  per-matchup sat/float ratio) on the **summary** landing page. Bokeh-guarded
  (returns `""` without bokeh), gated on the existing `sortable` switch.
- `figure_gallery(df)` — an **N-guarded** inline thumbnail strip of the
  per-matchup fit figures (clickable → full PNG), suppressed above
  `MAX_INLINE_FIGURES` (50) to honour the no-page-explosion rule; above the
  threshold detail comes via tap-to-open + the release-manifest downloads.
- `_gather_with_figures(store, outdir)` copies each `fits.figure_path` into
  `outdir/_static/figures/` and records a page-relative `figure_url`; `conf.py`
  now sets `html_static_path = ["_static"]` so one mechanism serves the inline
  gallery, the download links, and the scatter's tap-to-open.

**Verified.** `pab/tests/test_report.py` 15 passed (added two: figures embedded +
copied; gallery N-guard). Rebuilt the real site from `DATA_DIR/pab.db` (4
matchups): 4 fit PNGs copied to `_static/figures/`, scatter + map + gallery
embedded, `sphinx-build` succeeds, and `summary.html` references all four figures.
The fix flows through the pipeline automatically — `pab --stage report` calls
`build_site` with `sortable=True`.

> Note: only the **fit** figure is stored per matchup (`fits.figure_path`); the
> scene quick-looks in `pipeline/figures/*_scene.png` are produced but not yet
> recorded in the DB, so they aren't linked. Easy follow-up if we want them too.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-06-26 (Investigated first `pab` run crash)

Reproduced the crash from `pab --db data/pab.db`. The `ingest` stage completes,
then the `discover` stage dies on `earthaccess.search_data` →
`pab/pace/discover.py:44` → CMR `granules.umm_json` with HTTP 500 "An Internal
Error has occurred." — a server-side error from NASA's CMR, not a PAB bug.

Confirmed it is transient: `curl` of the exact failing URL now returns 200
(`CMR-Hits: 4` for that profile), and `pab --db data/pab.db --stage discover`
completes cleanly (`granules_upserted: 38`). Learned that PAB has no
retry/backoff around the network-bound CMR query and `earthaccess` doesn't retry
500s either, so any transient CMR hiccup aborts the whole pipeline — flagged
adding retry-with-backoff to `discover.search_granules` as a robustness fix.

### 2026-06-26 (Fixed eager full-cube granule read; found out-of-region hang)

Reviewed `error_logs/pab_error_00.md`: with discover working, the run reached the
`match` stage and crashed in `pab/pace/cloud.py:read_datatree` with an
`aiohttp.ClientResponseError` during a byte-range fetch of `Rrs_unc`. Root cause:
`read_datatree` called `.values` on the full `Rrs`/`Rrs_unc` cubes
(`1710×1272×172` int16, ~0.75 GB each), eagerly pulling the whole ~1.5 GB granule
over HTTP before the nearest-pixel extraction — the opposite of the module's
documented lazy design, which `pab/pace/extract.py` already relies on
(`isel(x,y).values` per pixel). Made `read_datatree` lazy: wrap the on-disk
variables via `.variable` (dims renamed to `(x,y,wl)`) instead of `.values`.
Verified out-of-region that a single-pixel `Rrs` read drops from a multi-minute
hang to ~3 s; chunks are `(32,256,40)` so one pixel needs ~5 chunks (~MB) vs ~1.5
GB. Added `decode_timedelta=False` to silence a FutureWarning.

Running the full `match` stage exposed a second latent bug: PACE groups can name
the spectral dim differently (`wavelength_3d` in `geophysical_data` vs
`wavelength` in `sensor_band_parameters`), so a shared dim-rename map crashed
(`cannot rename 'wavelength'`). The old `.values` path was immune because it
assigned dims positionally; reworked the lazy version to rename each variable by
its own `dims` positionally (`_canon`). `pab/tests/test_pace.py` stays green (17
passed).

Biggest learning: even after the fix, a full out-of-region `match` run **hung for
2h+ at ~0% CPU with no matchups**. The process was stuck in a futex inside
`fsspec`'s sync-over-async wrapper with a stalled HTTPS connection (≈4 MB unread
in the socket recv-q, another conn in CLOSE-WAIT). `earthaccess`/`fsspec` opens
the HTTP filesystem with no read timeout, so one stalled byte-range read blocks
forever. The lazy fix is necessary but not sufficient for reliable out-of-region
reads. Recommended to the user: run in-region (`us-west-2`) on S3, or
pre-download granules and use the `local` backend, optionally adding an aiohttp
read-timeout + retry. Awaiting their preference before implementing.

### 2026-06-27 (Implemented `--download` pre-download path for off-cloud runs)

User chose pre-download for small sample runs (in-region S3 otherwise). Added a
local-cache granule path that sidesteps the out-of-region fsspec hang entirely:
`pab/pace/cloud.py` gains `download_granule` (idempotent `earthaccess.download`
streaming fetch), `granule_cache_path`, and `cached_opener` (ensure-local then
`open_local`). Wired into `pab/pipeline.py` as `PipelineConfig.download`/
`cache_dir` + CLI `--download`/`--cache-dir`; `run()` builds the cached opener
when `--download` is set and no opener is injected, so it flows through the
existing `opener` seam to `match`/`fit`/`figure`. Documented in `HOWTO.md`.

Key learning: the reliable fix was not to harden the lazy byte-range read but to
swap transports — `earthaccess.download` (full-file streaming HTTP, threaded,
authenticated) is robust where `fsspec` random byte-range reads stall. Once
local, `open_local` (ocpy) reads are fast and network-free, so extraction drops
to ~0.1 s/granule. Cost is ~0.5 GB/granule on disk and a ~33 s one-time download
per granule. Tests: 35 passed across `test_pace.py` + `test_pipeline.py`.
Verified the real path end-to-end (download → cache hit → `open_local` →
extract). Full `pab --stage match --download` run completed cleanly with no hang:
38/38 granules downloaded (~15 GB), 4 matchups / 40 pixels written (all for float
7902226, sub-km, 10 spectra each); float 7902136's 5 profiles came back unmatched
(granules opened fine — float falls outside footprints or pixels flagged), worth
triaging before the fit run. Confirmed the union of candidates is all 38 granules
because each profile's ±24 h window picks a distinct, non-overlapping set.

### 2026-06-27 (Wired figures into the report site)

The reporting site is `.rst` + a Sphinx `conf.py` (not HTML); built it with
`sphinx-build` to view (Task 5). Then found Task 6's real gap: `build_site` only
embedded the stats `DataTable`s — the designed **interactive `b_bp` scatter** and
**matchup map** (`pab.report.interactive.comparison_scatter`/`matchup_map`,
already implemented and documented) were never called from page generation. The
inline per-matchup PNGs are *intentionally* absent (no-per-matchup-pages rule).

Fixed `pab/report/rst.py`: `interactive_figures()` embeds the scatter (hover +
tap-to-open the matchup's fit figure) and the ratio-coloured map on the summary
page; `figure_gallery()` adds an N-guarded (`MAX_INLINE_FIGURES=50`) inline
thumbnail strip; `_gather_with_figures()` copies `fits.figure_path` into
`_static/figures/` and `conf.py` gains `html_static_path = ["_static"]` so one
mechanism serves the gallery, downloads, and tap-to-open. Gated the Bokeh figures
on the existing `sortable` switch; the gallery needs no Bokeh.

Key learning: the interactive figures and the per-matchup PNGs are *different
deliverables* with opposite display rules — the scatter/map are the **per-matchup
detail surface** (so they belong embedded on a fixed page), while the PNGs are
**downloads reached via tap**, never their own pages. Serving the PNGs through
`html_static_path` (rather than RST `image`/`download` directives) gives a single
stable URL for inline `<img>`, the download link, and the Bokeh `OpenURL` tap.
Tests: `test_report.py` 15 passed (added figures-embedded-and-copied + gallery
N-guard); rebuilt the real 4-matchup site, `sphinx-build` clean, all 4 fit PNGs
linked. Only the fit figure is stored per matchup; `*_scene.png` quick-looks are
produced but not in the DB, so unlinked — a small follow-up.
