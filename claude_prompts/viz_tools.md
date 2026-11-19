# Viz tools for PAB

## Goals

This doc will be used to develop visualization tools for PAB.
These will include tools to inspect the BGC-Argo profiles and Rrs fits. 
We will also have tools to explore the bbp and other products for
the matchups.

## Claude

### Skills

- **`batch-fit-argo`**: the parallel-fit and checkpointing pattern.
- **`run-bing-fit`**, **`inelastic-rrs`**: the per-spectrum fit and the
  `rt_dict` inelastic flags.
- **`diagnose-mcmc`**, **`debug-priors`**: if anything changes in chain
  behaviour at the new geometry.

### Working agreements

- **Git is handled by JXP.** Run no state-changing git commands. JXP creates
  the working branch before Task 1. Read-only `git status` / `git diff` /
  `git log` are fine.
- **Python only.** Use the `ocean14` env, and call
  **`/home/xavier/miniconda3/envs/ocean14/bin/python`** directly, because
  `conda activate ocean14` in Claude's shell still resolves `python` to
  `os_313`.
- **These are read-only tools** (I-Q6). Every DB is opened read-only,
  `Store.open("file:<path>?mode=ro", create=False)` or a `mode=ro`
  `sqlite3` URI, never a plain `Store.open(path)`, which would create and
  migrate. Chain NPZs, figures and gallery files are only read. Tools write
  only HTML/PNG exports, and only to an explicit output directory or the
  scratchpad. No tool writes to `$PAB_DATA_DIR`. Fetched Argo profiles
  are cached in memory only (I-Q8).
- **Explicit DB path every time**, default `$PAB_DATA_DIR/v2/pab.db`; no
  default may resolve to `v1/pab.db`.
- **`v1/pab.db` is frozen.** It is `chmod a-w`, sha `09de0a6d…f978273`.
  Open it read-only, and only when a view asks for 1.0.
- **Chains resolve through `PAB_DATA_DIR`.** Set
  `PAB_DATA_DIR=$PAB_DATA_DIR/v2` before importing `pab` in any process
  that loads chains (`load_chains`, `reconstruct_fit`). The stored
  `chains_path` values are PVC paths.
- `PYTHONWARNINGS=ignore` (or a `warnings` filter inside the tool) when
  reconstructing robust fits: the forward model emits robust's
  `DomainWarning` on the `B_p` breach for most fits.
- **Confirm outward-facing steps with JXP** before running them: anything
  published, and any server bound to a non-localhost interface. The app
  binds to `localhost` by default (I-Q7).
- **Questions go in the Q&A section of this file**, never chat-only.

## Context

*Updated 2026-11-19 (Init prompt 1) for the finished v2.1 run. Every number
below was re-measured read-only on the live DB that day.*

Read:

- `HOWTO.md`: §3 (the CLI: `--matchups-csv`, `--replay-chains`,
  `--figure-version`, `--emit-site`), §5 (outputs), §5b (the v1/v2 layout,
  the frozen-v1 rule, where chains land, S3 keys) and §5c (2.1; its status
  line is stale at 2026-11-14, see "Open items" below).
- `claude_prompts/v2/run_full_inelastic.md`: the v2 plan (two-DB layout,
  provenance rules, gate pattern).
- `claude_prompts/v2/build_v2_1_rerun.md`: the v2.1 re-fit plan and its
  logs (Tasks 1–4 done). The single best record of what 2.1 is.
- `versions/v2.1/geometry_rerun.md`: the 2.1 science write-up (§2–3 the
  200-matchup slice and fixed-`B_p` arm; §5 the full population; §6 the
  paper note).
- `claude_prompts/v2/report_improvements.md`: Outliers O5–O9 (the 2.0.1
  re-fit, the replay seam, the patch overlay, the site build/publish).
- `versions/v2/ztt_slice.md`: the emulator domain and why the hybrid was
  never valid off-nadir.

### Decisions (Q&A / Init, 2026-11-19)

| # | Decision |
|---|---|
| I-Q1 = A | The newest BING family is the default (2.1 today), with a `version=` argument everywhere. Cheap old-vs-new views are side by side, and NASA-GIOP is an overlay on the `b_bp` views. v1 is read only on request. **Future versions (e.g. 3.0) must work unchanged**: no version string is hard-coded; all version logic goes through `pab.metrics.compare` (`version_family`, `newest_bing_version`, `overlay_patch`). |
| I-Q2 = Bokeh, interactive | The tools are interactive Bokeh apps (bokeh 3.9.1 is in `ocean14`; `panel`, `holoviews` and Jupyter are **not**). The run mode is I-Q7. |
| I-Q3 = A, on demand | Argo profiles are fetched on demand through `pab.argo.fetch.fetch_profile`. Whether to keep them on disk is I-Q8. |
| I-Q4 = agree | `pab/viz/` is the exploration layer. It reuses `pab/plotting`, `pab/metrics`, `pab/fit` and `pab/argo`, does not modify them, and never feeds the report pipeline. |
| I-Q5 | Deferred: JXP picks the views one prompt at a time. The candidates stay listed under "Code". |
| I-Q6 = yes | Read-only tools; the Working agreements are rewritten to match. |
| I-Q7 = A | **One Bokeh server app**, a tab per view, so a pick in one view opens another. Bound to `localhost` by default. |
| I-Q8 = A | Fetched Argo profiles live in an **in-process LRU cache** for the server's lifetime; nothing is written to disk. |
| I-Q9 | Built on the workstation, **also run on JXP's laptop**, and **launched from the command line** (not through VS Code). |
| I-Q10 | The laptop has a working `pab` env (bing, robust) and **a local copy of the data**, so `pab-viz` runs locally there as on the workstation. The tunnel stays documented as an option, and the capability check stays (it costs nothing and covers a partial copy). |

### What v2.1 is

Every v2 BING matchup re-fitted with the forward model at the geometry the
PACE L2 AOP `Rrs` is normalized to, **(θ_s, θ_v, Δφ) = (0, 0, 0)**, with the
inelastic `Ed` at θ_s = 0. The spectrum is **replayed** from each pixel's
2.0 chain NPZ, so 2.0 → 2.1 differs only in geometry. Everything else is the
2.0.1 config: `robust_hybrid`, Raman + Chl-fl on (CDOM-fl off),
`phi_c = 0.02`, 400–700 nm (136 bands), 10k steps / 1k burn / 16 walkers,
free `B_p`, prior ceilings `bbp600 ≤ 0.1, adg ≤ 10, aph ≤ 10`,
`on_out_of_domain = "warn"`. Run on Nautilus 2026-11-16/17 (image
`pab:2.1.0`, SHAs PAB `1f4b770`, bing `9acbe53`): **15,971 / 15,971 written,
0 failed**, ~300 s/fit/worker. The 5 matchups without a 2.0 fit are left
out (listed in the rerun doc's 2026-11-16 log).

Headline 2.1 / 2.0 (or 2.0.1 for the 51 re-fits), median, n = 15,971:
`b_bp(700)` **×1.168** [16–84 %: 0.94, 1.50], `b_bp(440)` ×1.19, Chl/`A_ph`
×0.979, `A_dg` ×0.915, `B_p` ×0.797, `beta` ×1.034, χ² ×0.984. The driver is
θ_s (0.96 at ≤20° → 1.44 at >50°), modulated by θ_v. 382 ratios lie outside
[1/3, 3], all clear water. `B_p` floor (0.004) pile-up 854 → 1,767.
Sat/float `b_bp` median 1.14 → **1.34**. LM `success = 0` on 86 fits (kept).

### Outputs (the data a viz tool reads)

All paths are under `$PAB_DATA_DIR` = `/home/xavier/Oceanography/data/Color/PAB`.

**The live v2 DB** `v2/pab.db`: schema **v6**, 302,505,984 B, sha256
`d0c286bf…8cc5` (after the 2.1 figure paths were written, 2026-11-18). It
is the only DB with 2.1 rows; S3 and AIOcean still hold the 2.0.1-era
`9503015b…` (Task 5 of the rerun is not done). Open it read-only for viz
(`sqlite3.connect("file:…?mode=ro", uri=True)`). `Store.open()` defaults to
`create=True` and runs `migrate`, which is a no-op on v6, but read-only
is the safe habit.

| table | rows | what a viz tool wants from it |
|---|---:|---|
| `floats` | 912 | `wmo`, project, data center |
| `profiles` | 59,620 | `profile_id` (an **integer** row id, e.g. 1038), `wmo`, `cycle`, lat/lon, time, `data_mode` |
| `mld_summary` | 59,620 | per-profile mixed-layer **summaries only**: `mld`, `bbp700`(±std), `chla`(±std), `chla_adjusted`, `cdom`, `psal`, `temp`, the per-variable data modes, `qa_path` (a PVC path) |
| `granules` | 72,803 | PACE L2 AOP granule ids/times/footprints (all V3_2) |
| `matchups` | 15,976 | `matchup_id` (`<wmo>_<cycle>_<granule file>`), `profile_id`, `distance_km`, `dtime_hours`, `scene_path` (a PVC path) |
| `matchup_pixels` | 159,760 | 10 pixels per matchup: `ix, iy`, lat/lon, `rank`, `flagged`, L1B `theta_s/theta_v/dphi` (QA metadata only under 2.1; 50 pixels NULL) |
| `fits` | 47,969 | one row per fit; see the version breakdown below |
| `fit_results` | 511,724 | long format: (`fit_id`, `quantity`, `value`, `value_lo`, `value_hi`, `unit`) |

`fits` by version:

| algorithm | `pab_version` | `geom_mode` | n | LM success |
|---|---|---|---:|---:|
| BING | 2.0 | NULL (= observed) | 15,971 | 15,827 |
| BING | 2.0.1 | NULL (= observed) | 51 | 50 |
| BING | **2.1** | `normalized` | **15,971** | 15,885 |
| NASA_GIOP | 1.1 | NULL | 15,976 | 15,976 |

- 2.1 `fit_id` = `<matchup_id>_<ix>_<iy>_ExpBPow_v2.1`.
  `rrs_source = L2_AOP:replay:<2.0 fit_id>`, so each 2.1 row names the 2.0
  fit it pairs with.
- Provenance columns on every BING row: `rt_backend`, `include_raman`,
  `include_chl_fl`, `include_cdom_fl`, `phi_c`, `fit_bp`, `geom_mode`,
  `prior_set`, `nsteps/nburn/nwalkers`, `wave_min/max`, `pkg_versions`
  (JSON with git SHAs), and `chisq/aic/bic/accept_frac/success`.
- BING `fit_results` quantities (prefix `BING_ExpBPow_`): `Adg`, `Sdg`, `Aph`,
  `Bnw`, `beta`, `Bp` (the free parameters), `anw440`, `anw700`, `bbp440`,
  **`bbp700`** (m⁻¹), `chl` (mg m⁻³) and `n_neg_blue` (bands). `value_lo/hi`
  are the credible bounds.
- NASA_GIOP quantities: `adg_442`, `adg_s`, `aph_442`, `bbp_442`, `bbp_s`
  and their `_unc_442`. Convert to 700 nm with `compare.giop_bbp_to_700`.

**Chains** `v2/fit_chains/`: 31,993 NPZs, 37 GB (15,971 `_v2.0` + 51
`_v2.0.1` + 15,971 `_v2.1`). Each holds `chains` (10000, 16, 6) float32,
`wave`/`Rrs`/`varRrs` (136,), `param_names` = `[Adg, Sdg, Aph, Bnw, beta,
Bp]` and `Chl`. A 2.1 NPZ's `Rrs` is bit-identical to its 2.0 NPZ's.
**Gotcha:** `fits.chains_path` stores the PVC path
(`/data/v2/fit_chains/…`). `pab.fit.artifacts.load_chains(fit_id)` resolves
by `$PAB_DATA_DIR/fit_chains/<fit_id>.npz`, so a viz session must set
`PAB_DATA_DIR=$PAB_DATA_DIR/v2` before importing `pab`, or resolve by
basename.

**Fit figures** `v2/pipeline/figures/`: 15,971 `<fit_id>_v2.1_fit.png` +
51 2.0.1 ones (0.9 GB). `fits.figure_path` on the 2.1 rows holds these
**workstation** paths. The 2.0 fit figures are on the PVC / AIOcean only.
`pab.plotting.fit_fig.reconstruct_fit(store, fit_id)` rebuilds
(wave, obs `Rrs`, model `Rrs` median/5/95 %, `b_bp(λ)` median/5/95 %) from a
chain NPZ at the row's own geometry (`geom_mode`), which makes it the
natural engine for an interactive Rrs-fit inspector (~2–8 s per fit).

**Scenes and Argo QA plots** are mostly **not** on the workstation:
`matchups.scene_path` and `mld_summary.qa_path` are PVC paths. Local
copies: `gallery/v1_scenes/`, `gallery/v2_figures/`, `gallery/argo_qa/`
(only the report's gallery picks) and `gallery/v2_argo_qa/` (the 5,453-file
v2 backfill set). HOWTO §7a's `--figure-root` remaps PVC → local.

**No Argo profile arrays are stored anywhere in PAB.** Only the
mixed-layer summaries (`mld_summary`) and the QA PNGs are. A profile viewer
must re-fetch through `pab.argo.fetch.fetch_profile(wmo, cycle)` (argopy,
network) or add a local cache.

**Analysis products** in `versions/v2.1/` (all read-only derivatives of the
DB):
- `full_table.csv`: **one row per matchup, 2.1 paired with its reference**
  (2.0 or 2.0.1): ids, θ_s/θ_v/Δφ, basin, float `bbp`/Chl, and ref/2.1
  `bbp700`, `bbp440`, `Aph`, Chl, `Adg`, `Sdg`, `beta`, `Bp`, χ², acceptance,
  success, plus `bbp700_ratio`. The quickest input for population
  2.0-vs-2.1 views. Built by `analyze_full.py` → also `full_summary.json`,
  `fig_full_ratios.png`.
- The slice: `slice_200.csv`, `slice_table.csv`, `slice_summary.json`,
  `fig_slice_ratios.png`; the arm: `bp_arm_50.csv`, `arm_table.csv`,
  `fig_bp_arm.png` (`analyze_slice.py`). Slice DBs and chains are in
  `$PAB_DATA_DIR/v2.1_slice/{main,arm_norm,arm_obs}/`.
- Integrity records: `preflight.py` (snapshot/verify), `preflight_snapshot.json`,
  `postrun_verify.json`, `prefigure_snapshot.json`, `postfigure_verify.json`.

**Report site** `report_site/` (RTD): rebuilt locally 2026-11-18 with 2.1
as the headline and a 1.0-vs-2.1 comparison (n = 14,604), but not yet
committed/pushed. Population plotting helpers live in
`pab/plotting/population.py` (`density_scatter`, `ratio_vs_level`,
`ratio_level_bins`, `matchup_map`, `healpix_map`, `value_histogram`) and the
standalone Bokeh pieces in `pab/report/interactive.py`. Matchup
frames come from `pab.metrics.compare.gather_matchups(store)` (newest family
with the patch overlay), `gather_version_pair(store, v1_path)` and
`gather_nasa_giop(store)`.

### Code seams for viz (verified 2026-11-19)

| What | Where | Note |
|---|---|---|
| New package | `pab/viz/__init__.py` | empty, staged by JXP |
| Read-only store | `pab/db/store.py:47` `Store.open(path, *, create=True)` | pass a `file:…?mode=ro` URI **and** `create=False` (`uri=True` is already set) |
| Version resolution | `pab/metrics/compare.py:235` `newest_bing_version`, `:249` `is_patch_version`, `:254` `base_version`, `:302` `resolve_versions` | the generic old-vs-new pairing pattern is in `geometry_shift_summary` (`:621`): previous base family with its patches overlaid, joined on `matchup_id` + `pixel_id` |
| Existing Bokeh | `pab/report/interactive.py` | standalone (`bokeh.embed`) scatter/map/table builders with hover and tap-to-URL; reuse their styling and column conventions |
| Fit reconstruction | `pab/plotting/fit_fig.py:96` `reconstruct_fit`, `:156` `fit_figure` | geometry from `geom_mode` via `_geometry_from_row` (`:68`) |
| Chain I/O | `pab/fit/artifacts.py:28` `chains_path`, `:53` `load_chains` | keyed on `PAB_DATA_DIR` |
| Replayed spectrum | `pab/fit/replay.py:60` `load_spectrum`, `:84` `spectrum_from_chains` | wave/Rrs/varRrs from an NPZ |
| Version logic | `pab/metrics/compare.py:260` `version_family`, `:329` `overlay_patch`, `:621` `geometry_shift_summary` | the newest family is `("2.1", [])` |
| Matchup frames | `pab/metrics/compare.py:678` `gather_matchups`, `:765` `gather_version_pair`, `:871` `gather_nasa_giop` | |
| Population plots | `pab/plotting/population.py` | see above |
| Scene quick-look | `pab/plotting/scene.py:89` `scene_quicklook`, `:177` `scene_from_store` | needs the granule (download) |
| Argo profile plot | `pab/argo/qa.py:28` `plot_profile`; fetch in `pab/argo/fetch.py:94` | needs a network fetch |
| Fit-time geometry (2.1) | `pab/fit/run.py:264` `fit_geometry`, `:252` `normalized_geometry` | (0, 0, 0) under `"normalized"` |

### Open items carried from the v2.1 run

- **Task 5 is not done**: S3 `v2/pab.db` and `matchup_summary.*`, the
  dated AIOcean backup, the RTD push and HOWTO §5c close-out are all
  pending. Until then the public DB has no 2.1 rows.
- `papers/bbp/bias_discussion_draft.md` bias numbers are 2.0/2.0.1 and need
  a refresh from 2.1 (a separate paper prompt).

## Code

- When possible reuse existing code in the PAB package.
- Python only for now.  
- Place import commands at the top of the file.

If you need to run Python, use the `ocean14` conda environment.

*The plan below was added 2026-11-19 (Init prompt 2); nothing written yet.
The views themselves come one prompt at a time (I-Q5).*

- "Python only" in practice: Bokeh layouts are built in Python, and
  interactivity goes through Python callbacks (a Bokeh server, I-Q7). No
  hand-written `CustomJS` unless JXP asks for it.
- "Imports at the top": `bokeh` and `argopy` are imported at module top in
  `pab/viz/`. This is unlike `pab/report/interactive.py`, which imports
  bokeh lazily. That is fine because `pab.viz` is never imported by the
  pipeline (I-Q4), and `pab/viz/__init__.py` stays empty, so
  `import pab` stays light.

### Status (2026-11-19)

**Built: the Argo + PACE tab** (Argo+PACE prompt 3). Modules:

| File | What it holds |
|---|---|
| `pab/viz/data.py` | read-only `open_store`, `set_data_dir`, `has_chains`; families (`version_families`, `family_label`); `wmos_with_matchups`, `cycles_for_wmo`, `matchup_for`, `bing_fit` (overlaid, best rank), `giop_fit` |
| `pab/viz/fits.py` | `reconstruct(db_path, fit_id)` → `FitCurves` (LRU 64, own store per call), `observed_spectrum`, `adg_at` (`a_dg(440)` per sample) |
| `pab/viz/argo.py` | `fetch_argo_profile` (LRU 128, ingest's src/mode), `despike_samples` (3-pt median over the BBP700 samples only, AP-Q16), `bbp_layers` (de-spike / in-ML / IQR-kept / dropped, plus the `ingest_*` statistics as stored), `recompute_summary`, `reproduces` |
| `pab/viz/bokeh_argo_pace.py` | `ArgoPaceView` (figures, sources, `show_*`), `load_selection`, `profile_notes`, server-free `make_argo_pace` |
| `pab/viz/app.py` | `ArgoPaceTab` (controls, URL args, background jobs with a stale-token guard), `make_document` |
| `pab/viz/__main__.py` | the `pab-viz` launcher and its capability report |
| `pab/tests/test_viz_argo_pace.py` | 11 tests, no network |

`setup.py` registers `pab-viz`. Launch notes are in HOWTO §5d.

**Gotcha:** two worker threads importing the same module for the first time
deadlock (`_ModuleLock`; seen with argopy). So `argopy` and every module
that `reconstruct_fit` imports lazily are imported at module top in
`argo.py` / `fits.py`, i.e. on the main thread. A new tool that adds
background work must do the same.

### Layout of `pab/viz/`

| Module | Role |
|---|---|
| `data.py` | The read-only data layer and **the only module that touches the DB or files**. `open_store(path)` (read-only URI, `create=False`); `fit_row(store, fit_id)`; `fit_results(store, fit_id)` (wide dict of value/lo/hi); `paired_fits(store, fit_id)` (the same matchup + pixel in the previous base family, patches overlaid, so it is generic in version); `matchup_frame(store, version=None)` wrapping `compare.gather_matchups`; `pixels(store, matchup_id)`; `profile_summary(store, profile_id)`; `chains(fit_id)` via `artifacts.load_chains`, guarded on `PAB_DATA_DIR`. |
| `fits.py` | The fit-level computations, no plotting: wraps `fit_fig.reconstruct_fit` and adds what it lacks (`a_nw(λ)` bands, residuals in σ units, the flat posterior for a corner plot), with an in-process LRU cache because a reconstruction costs ~2–8 s. |
| `argo.py` | The on-demand profile fetch (I-Q3) and its cache (I-Q8): returns per-variable arrays against pressure, reusing `fetch.filter_quality` / `iter_profiles` and `summary` for the MLD. |
| `bokeh_*.py` | One module per view, each a `make_<view>(…) -> bokeh layout` builder that is testable without a server. The Bokeh callbacks call into `data`/`fits`/`argo` only. |
| `app.py` | Builds the Bokeh `Document`: the tabs, the shared selection state (current `version`, `fit_id`, `matchup_id`), and the cross-tab navigation. |
| `__main__.py` | The command-line launcher (I-Q7, I-Q9); see "Launch" below. |

### Launch (I-Q7, I-Q9)

- Run from any shell: `python -m pab.viz --db <path>`, plus a console
  script **`pab-viz`** registered in `setup.py` beside `pab` (a one-line
  `entry_points` change, then `pip install -e . --no-deps`).
- `__main__` starts the server **programmatically**
  (`bokeh.server.server.Server` with a `FunctionHandler` around
  `app.make_document`), so there is no `bokeh serve <dir>` layout and no
  dependence on the cwd.
- Flags: `--db` (required; opened read-only), `--data-dir` (the root that
  holds `fit_chains/`, default `$PAB_DATA_DIR/v2`; it sets `PAB_DATA_DIR`
  before `pab` is imported), `--version` (default: the newest family),
  `--port` (default 5006), `--host` (default `localhost`; anything else
  asks for confirmation, per the Working agreements), `--show` (open the
  browser) and `--model-pair` (default `ExpBPow`).
- **Capability check at start-up**, because a laptop may hold less data than
  the workstation. The app logs what it found and enables views to match:
  the DB (required); chains under `--data-dir` (needed by the fit
  inspector's reconstruction; without them it falls back to the stored
  `fit_results` and the fit PNG if present); `robust`/`bing` importable
  (needed to reconstruct); network for argopy (needed for profiles). A
  missing piece disables the affected panel with a message rather than
  crashing the app.
- Launch instructions go in `HOWTO.md` (a new "Viz tools" section) once
  the first view exists. They cover the workstation, the laptop (I-Q10),
  and the SSH tunnel `ssh -N -L 5006:localhost:5006 <workstation>`.

### Rules for the code

- **Version-generic.** No `"2.0"`/`"2.1"` literals outside tests. "Newest"
  and "previous" come from `compare`. The old-vs-new pairing keys on
  `matchup_id` + `pixel_id`, not on `rrs_source`, so it works for a future
  3.0 that does not replay.
- **Model-pair aware.** Quantity names are built as
  `f"BING_{model_pair}_{q}"` (default `ExpBPow`), as in `compare`.
- **Reuse before writing.** Bins, ratios and gates come from
  `pab/plotting/population.py` and `compare` (`gate_bbp`,
  `giop_bbp_to_700`, `add_strata`), so the viz numbers match the report's.
- **Thread safety.** Bokeh server callbacks may run off the main thread.
  The data layer opens its own connection per session (or uses
  `check_same_thread=False` on a read-only connection), never a module
  global. Slow work (reconstruction, Argo fetch) runs in a thread pool and
  updates the document through `doc.add_next_tick_callback`, so the page
  stays responsive and shows a "loading" state.
- **Portable paths.** No workstation path is hard-coded. Stored PVC or
  workstation paths (`chains_path`, `figure_path`, `scene_path`, `qa_path`)
  are resolved by basename against `--data-dir` and the known gallery
  folders, and a miss is reported, not raised.
- **Tests** in `pab/tests/test_viz_*.py`: the data layer on a tiny
  in-memory store (as the existing tests do), and each builder returning a
  layout with the expected glyphs and sources. No network: the Argo fetch
  is mocked. `ruff` clean.

### Candidate views (from I-Q5, order to be set by JXP)

1. Rrs-fit inspector (one fit; old vs new version overlaid).
2. Matchup card (float profile, ten pixels, NASA-GIOP, geometry).
3. Population explorer (sat vs float, version ratios against geometry /
   basin / season / `B_p` / χ², and pick → views 1 and 2).

## Prompts

### Init

1. Read this file and the context described above. Then update the Context section to account
   for the latest (v2.1) run, in particular details on the various outputs.
   If you have any questions, put them in the Q&A/Init section. 
   Use Opus 5.5. Log your work.

2. I have answered the questions in the Q&A/Init section.  Please review my answers and modify the 
Context and Code sections accordingly.
   If you have any additional questions, put them in the Q&A/Init section.
   Use Opus 5.5. Log your work.

3. I have answered the next round of questions in the Q&A/Init section.  
Please review my answers and modify the Context and Code sections accordingly.
I will then proceed to work on the first tool with new Prompts.
   Use Opus 5.5. Log your work.

### Argo+PACE

1. I wish to start with a tool that shows the Argo profile of bbp
and the fit to PACE Rrs for the matchup.  Using 2 panels of one Bokeh layout.
The input will tbe the `wmo` and `profile_id` for the Argo profile.  

The Argo panel should show:
   - The individual bbp measurements to depth
   - An indication of the MLD (dashed, horizontal line)
   - The y-axis should run from surface to 2x the MLD
   - The measured bbp for the profile and its error should be indicated

The PACE panel should show:
   - The PACE Rrs values with error versus wavelength
   - The BING fit for the matchup and its uncertainty
   - The estimated values for bbp700 (amplitude and slope), Chl and CDOM

Consider the above and ask me a set of questions in Q&A/Argo+PACE before
proceeding to generate the code.
Use Opus 5.5. Log your work.

2. I have answered the questions in the Q&A/Argo+PACE section.  Please review my answers 
and ask additional questions if needed.  Do not generate the code yet.
Use Opus 5.5. Log your work.

3. I have answered the next round of questions in the Q&A/Argo+PACE section.  
Please review my answers and proceed to generate the code.
Then let me know how to launch the tool and give me a few `wmo` and `cycle` values to test.
Use Opus 5.5. Log your work.

4. This an excellent first iteration.  Here are modifications to make:
    - Have the Rrs figure have the y-axis always start at 0 (or below)
    - Include a dashed, dark-gray line at Rrs=0
    - Remove the CDOM row from the Table
    - In some cases, the "de-spiked" median line appears to follow each data point, not a 3-pt median. 
      Please explore.  Also, it doesn't appear the IQR-rejected points are being ignored.

Use Opus 5.5. Log your work.

5. Thanks for the modifications and the discussion of the de-spike issue.  Please read
my answers to AP-Q16 and Q17 and respond accordingly.
I will then test the new code further.
Use Opus 5.5. Log your work.

## Q&A

### Argo+PACE

*Round 1 (2026-11-19). Answer inline under each **Your answer:**.
Recommendations are marked; I will build to them where you leave a
question blank.*

Facts these questions rest on (measured read-only on the live v2 DB):
- Every matchup profile has **exactly one matchup**. Every matchup has
  **one 2.1 BING fit**, always on the **rank-1** (nearest, unflagged) pixel
  of its ten. So a profile picks a single fit with no further choice.
- `profiles.profile_id` is an **integer row id** (e.g. 1038), not
  `<wmo>_<cycle>`. `matchup_id` starts with `<wmo>_<cycle>_`.
- MLD (`deBoyerMontegut_0.03`) on matchup profiles: 10–684 m, mean 45 m;
  **91 have no MLD**.
- `mld_summary.bbp700` is the mixed-layer mean of the **de-spiked**
  (3-point moving median), **log-IQR-filtered** `BBP700` at `PRES ≤ MLD`.
  `bbp700_std` is the **standard deviation** of those samples (not the
  error of the mean); n ≈ 50 on average. **697** matchup profiles have
  `bbp700_std` NULL.
- Ingest fetched with argopy `src="gdac"`, `mode="expert"` and applied **no
  QC-flag filter** (`filter_quality` is not called).
- BING `ExpBPow`: `b_bp(λ) = Bnw·(600/λ)^β`, so the amplitude is at
  **600 nm**, and the stored `bbp700` is derived from (Bnw, β).
  `a_dg(λ) = Adg·exp(−Sdg(λ−400))` is CDOM **plus detritus**, amplitude at
  **400 nm**. Stored credible intervals are **5–95 %**.
- Observed `Rrs` errors are `sqrt(varRrs)` from the chain NPZ: the PACE
  `Rrs_unc` where finite, else a 2 % floor. 136 bands, 400–699 nm.

**AP-Q1: The input.** You wrote "`wmo` and `profile_id`". The DB's
`profile_id` is an integer row id, so with the WMO it is redundant.
- **A (recommended).** **`wmo` + `cycle`**, the natural Argo identity. The
  app has a WMO box/dropdown and then a cycle dropdown limited to that
  float's matchup cycles. The URL takes `?wmo=…&cycle=…` and the CLI takes
  `--wmo/--cycle`, so a profile opens directly. A `profile_id` or a
  `matchup_id` is also accepted.
- **B.** `wmo` + the integer `profile_id`, literally.

**Your answer:** Agreed, use `cycle` and not `profile_id`.

**AP-Q2: Which `bbp` points on the Argo panel?**
- **A (recommended).** Re-fetch exactly as ingest did (gdac, expert, no
  QC filter), so the plotted mean reproduces `mld_summary.bbp700`. Show:
  - every raw `BBP700` sample as light points;
  - the de-spiked profile as a line;
  - the in-ML samples that the IQR filter dropped, marked differently
    (they explain the mean).

  Hover gives pressure, value and QC flag.
- **B.** Raw points only.
- **C.** Apply a QC filter (e.g. flags 1, 2, 5, 8), which may no longer
  match the stored mean.

**Your answer:**  Go with `A`

**AP-Q3: How to show the measured `bbp` and its error.**
- **A (recommended).** A vertical line at `mld_summary.bbp700` from the
  surface to the MLD, with a shaded **±1 std** band (`bbp700_std`). The
  legend states n and that the band is the ML scatter. With a NULL std the
  line is drawn without a band, and a note says so.
- **B.** The same, but the band is the error of the mean (std/√n), which
  is ~7× narrower.

Also: should the **PACE `bbp700`** (BING median and 5–95 %) be drawn on
the Argo panel as a marker/band near the surface, so the comparison is on
one axis? *(Recommended: yes. Together with AP-Q7, NASA-GIOP the same
way.)*

**Your answer:** Go with `A` and, yes, include the PACE bbp700 value too

**AP-Q4: Axes of the Argo panel.**
- y: pressure (dbar ≈ m), increasing downward, 0 → 2×MLD as you asked.
  For the **91 profiles without an MLD**: no dashed line, and y runs
  0 → 200 m (or 0 → the deepest sample if shallower)? *(Recommended.)*
- x: **linear** `bbp700` (m⁻¹), auto-ranged on the samples inside the y
  window, so a deep spike does not flatten the plot? Or log x?
  *(Recommended: linear.)*

**Your answer:** Use your recommendations

**AP-Q5: The `Rrs` panel and the uncertainty.**
- Observed `Rrs` with ±`sqrt(varRrs)` error bars. The BING model median
  with its **5–95 %** band from `reconstruct_fit` (needs the chain NPZ and
  bing/robust; ~2–8 s, run in the background with a "loading" state).
  *(Recommended.)*
- Two panels exactly, as you asked, so no residual sub-panel for now?
  *(Recommended: none now; easy to add later.)*
- Your laptop "local copy": does it include the **2.1 chains** (~18 GB)?
  Without them the fit curve cannot be drawn and the panel shows only the
  observed `Rrs` and the stored values (AP-Q6). The PNG fallback is not
  used, since the plot is native Bokeh.

**Your answer:** Do recreate the median with a "loading" state.  
Do show a Residuals.  The laptop will include the 2.1 chains.

**AP-Q6: Which estimated values, and how shown?** BING has no separate
"`bbp700` amplitude": the amplitude `Bnw` is at **600 nm**. It also has no
pure CDOM: `a_dg` is CDOM + detritus.
- **A (recommended).** A small table under the `Rrs` plot (a Bokeh `Div`),
  median [5–95 %], with an Argo column where one exists:

  | quantity | PACE (BING) | Argo (ML mean) |
  |---|---|---|
  | `b_bp(700)` (m⁻¹) | stored `bbp700` | `bbp700` ± std |
  | `β` (`b_bp` slope) | stored `beta` | — |
  | `Bnw` = `b_bp(600)` | stored `Bnw` | — |
  | Chl (mg m⁻³) | stored `chl` | `chla` (and `chla_adjusted` if present) |
  | `a_dg(440)` (m⁻¹) | computed per posterior sample from `Adg`, `Sdg` | — |
  | `S_dg` (nm⁻¹) | stored `Sdg` | — |
  | Argo CDOM | — | `cdom` raw ppb, labelled *uncorrected* |

  The CDOM amplitude is quoted at **440 nm** (the usual convention). The
  stored amplitude is at 400 nm and can be shown instead.
- **B.** Only the four you named (`bbp700`, `β`, Chl, CDOM), PACE only.

**Your answer:**  Create the Recommended table.

**AP-Q7: Versions and NASA-GIOP on this tool.** Following I-Q1:
- A version selector, defaulting to the newest (2.1).
- An "overlay previous version" checkbox, **off** by default: it draws the
  2.0 model `Rrs` dashed and adds a 2.0 column to the table. It needs the
  2.0 chain.
- NASA-GIOP `b_bp(700)` (from `bbp_442` and `bbp_s` via
  `giop_bbp_to_700`) as a toggle on the Argo panel and as a table row.

*(Recommended: all three.)*

**Your answer:** Do have a version selector.  Do not overlay the 2.0 model.  Do include NASA-GIOP,
as a toggle 

**AP-Q8: Header.** A one-line header above the two panels: WMO/cycle,
date, lat/lon, `distance_km`, `Δt` (h), the version, LM `success`, χ²_red,
and the pixel's θ_s/θ_v (metadata). *(Recommended.)* Anything to add or
drop?

**Your answer:** Include everything except the pixel's θ_s/θ_v

**AP-Q9: Delivery.** This becomes the **first tab** of the `pab-viz`
server app (Code / Launch), built by a server-free
`make_argo_pace(store, wmo, cycle, …)` that the tests can exercise. Also:
a "save as HTML" export of the current view (static, to an explicit
path)? *(Recommended: the tab now, the export later.)*

**Your answer:** Follow your Recommendation

#### Round 1 resolved (2026-11-19)

| Q | Decision |
|---|---|
| AP-Q1 | Input is **`wmo` + `cycle`** (838 floats with matchups, 1–232 matchup cycles each). |
| AP-Q2 | A: re-fetch as ingest did; raw points, the de-spiked line, the IQR-dropped in-ML samples marked; hover with P, value, QC. |
| AP-Q3 | A: Argo ML mean line 0→MLD with a ±1 std band, **plus the PACE `bbp700`** on the same panel. |
| AP-Q4 | As recommended: 0→2×MLD; with no MLD, 0→200 m (or the deepest sample) and no dashed line; linear x, auto-ranged on the visible samples. |
| AP-Q5 | Model median and 5–95 % band reconstructed with a "loading" state; **a residuals display is added**; the laptop will have the 2.1 chains. |
| AP-Q6 | The recommended table (`b_bp(700)`, `β`, `Bnw`(600), Chl, `a_dg(440)`, `S_dg`, Argo CDOM uncorrected). |
| AP-Q7 | A version selector, yes; **no** overlay of the previous version's model; **NASA-GIOP as a toggle**. |
| AP-Q8 | Header: WMO/cycle, date, lat/lon, `distance_km`, Δt, version, LM `success`, χ²_red. **No θ_s/θ_v.** |
| AP-Q9 | The first tab of `pab-viz`, from a server-free `make_argo_pace(…)`; HTML export later. |

#### Round 2 (2026-11-19)

*Follow-ups from round 1. Recommendations are marked; I will build to
them where you leave a question blank.*

**AP-Q10: Where do the residuals go?** The layout was two panels.
- **A (recommended).** A short strip **under the `Rrs` plot**, sharing its
  x-axis (pan and zoom are linked), still inside the PACE panel. It plots
  `(Rrs_obs − Rrs_model)/σ` per band, with σ = `sqrt(varRrs)`, a zero line
  and ±1 guides. Hover also gives the residual in sr⁻¹ and in %.
- **B.** The same strip in **relative %** `(obs − model)/model`.
- **C.** A third, separate panel.

**Your answer:** Agree with `A`

**AP-Q11: What does the version selector offer?** The DB holds 2.0,
2.0.1 (a patch on 51 of the 2.0 fits) and 2.1, and later 3.0.
- **A (recommended).** One entry per **family**: "2.1" and "2.0 (+2.0.1)".
  The 2.0 entry overlays the patch through `compare.overlay_patch`, as the
  report does, so a runaway 2.0 fit shows its 2.0.1 replacement and is
  labelled so. Future families appear automatically. The newest is the
  default.
- **B.** Every raw `pab_version` as its own entry.

Also: the 2.0 family's **chains** (~19 GB) are on the workstation, and you
said the laptop will have the 2.1 chains. Without 2.0 chains on the
laptop, picking 2.0 there shows the stored values and the observed `Rrs`,
with the curve marked unavailable (the capability check). Is that fine,
or will the laptop carry the 2.0 chains too?

**Your answer:** Do `A`, and it is fine if the laptop does not have the 2.0 chains.

**AP-Q12: How is the PACE `bbp700` drawn on the Argo panel?** PACE
senses roughly the first optical depth, not a point.
- **A (recommended).** A **vertical band** in a second colour over the
  same 0→MLD span as the Argo mean: the median line with the 5–95 %
  shading. The two then compare directly by eye, and the legend names
  both.
- **B.** A single marker at the surface (y = 0) with a horizontal 5–95 %
  error bar.

The NASA-GIOP toggle (AP-Q7) then draws GIOP `b_bp(700)` the same way,
dashed. Its ± comes from `bbp_unc_442` scaled to 700 nm with the GIOP
slope, with no slope error, which is stated in the hover. In the table it
is one extra row, shown only while the toggle is on. *(Recommended.)*

**Your answer:** Do `A` and your recommendation for NASA-GIOP

**AP-Q13: If the re-fetched profile does not reproduce the stored mean.**
GDAC files get reprocessed (delayed mode, new QC) after ingest, so a
re-fetch today can differ from what the matchup used.
- **A (recommended).** Plot the re-fetched samples, but take the drawn
  Argo mean and std, and the table's Argo column, from **`mld_summary`**
  (the values the matchup used). The ML mean is recomputed from the
  re-fetch, and if it differs by more than 2 % a visible note gives both
  numbers. The MLD line likewise comes from `mld_summary`.
- **B.** Recompute everything from the re-fetch and ignore the stored
  values.

**Your answer:**  Good point; go with the Recommendation

**AP-Q14: Layout.**
- **A (recommended).** The header across the top. The Argo panel on the
  **left** (narrower, tall, depth down), and the PACE panel on the
  **right** (`Rrs` + residual strip, then the values table under it).
  The controls (WMO, cycle, version, GIOP toggle) are in a row above the
  header.
- **B.** Stacked vertically (better on a narrow laptop screen).

**Your answer:** Let us try your recommendation.  We may have to tinker further to improve the layout.

**AP-Q15: Failure cases.** These are shown as messages in the affected
panel, never as a crash:
- the Argo fetch fails (no network, GDAC down), so the Argo panel shows
  only the stored ML mean and the MLD;
- no BBP700 samples in the profile;
- the chain file is missing for the selected version;
- the fit has LM `success = 0`: it is drawn as usual, with a warning
  badge in the header;
- χ²_red is extreme (2.1 has a max of 231): no special handling beyond
  the header value.

*(Recommended as listed.)* Anything to add?

**Your answer:** Agree with the Recommended list. Nothing to add for now

#### Round 2 resolved (2026-11-19)

All six took the recommendation: the residual strip in σ units under `Rrs`
(AP-Q10); one selector entry per family with the patch overlay, and no 2.0
chains on the laptop (AP-Q11); the PACE and GIOP `b_bp(700)` drawn as bands
over 0→MLD (AP-Q12); the drawn Argo values from `mld_summary`, with a note
when a re-fetch differs by > 2 % (AP-Q13); Argo left, PACE right (AP-Q14,
"may tinker"); the failure cases as messages (AP-Q15). **Built 2026-11-19**,
see Code / Status.

#### Round 3 (2026-11-19, from prompt 4)

**AP-Q16. The ingest de-spike does not de-spike gapped profiles. Fix it
upstream?**

Prompt 4 asked why the "de-spiked" line sometimes follows every point. The
cause is in the ingest code, not the viz.

- **The bug.** `summary.mixed_layer_mean(..., despike_values=True)` runs
  `moving_median` over the whole pressure column. Many floats sample `BBP700`
  on only every 2nd or 3rd level of the merged profile, with NaN in
  between. Each 3-point window then holds a single sample, so:
  - the "median" is the sample itself, and **nothing is de-spiked**;
  - the window centred on an empty level takes its one neighbour's value, so
    every sample is **copied into the empty levels**. `n_points` is inflated
    and the mean is weighted (each sample counts once per copy).
- **Example.** 1902368/25 stores n = 66 from 22 real samples in the ML; 17
  are left after the IQR filter.
- **How common** (60 random matchups, live re-fetch):

  | measure | result |
  |---|---|
  | profiles with any NaN gaps between `BBP700` samples | 55 / 60 |
  | profiles with more than half of the gaps NaN | 33 / 60 |
  | stored `n_points` > real samples in the ML | 46 / 60 (median ratio 1.6) |
  | change in the ML mean when fixed: median / 90th pct / max | 0.5 % / 2.0 % / 6.8 % |
  | profiles whose mean changes > 2 % | 7 / 60 |

  So the means move little, but `n_points`, `bbp700_std` and the de-spiking
  itself are wrong on most profiles.
- **What the viz does now.** The drawn values stay the stored ones (AP-Q13).
  - The panel de-spikes sample to sample (`argo.despike_samples`).
  - When the stored `n` or mean differs, it adds a dotted "ML mean, sample
    de-spike" line, a second line in the table, and a note.
  - The GDAC-reprocessing check still compares like with like (ingest
    recipe vs stored).

Options:
- **A** *(recommended)*. Fix `mixed_layer_mean` / `summarize_profile` to
  de-spike over the finite samples only, and re-derive `mld_summary` in a
  new version. That means re-fetching the profiles: no BING re-fit, and
  `v1/pab.db` and v2.1 are untouched. This is a pipeline task with DB writes,
  so it belongs in its own prompt doc, not here.
- **B**. Leave the ingest as is. The viz keeps showing both values.
- **C**. Leave the ingest, but have the viz draw the corrected mean as the
  main Argo band (the stored value becomes the secondary one).

**Your answer:** I agree with `A`.  Generate a new prompt doc `claude_prompts/v2/de-spike-fix.md`
that I will execute at some point.

**AP-Q17. The rejected samples, and how strict the IQR filter is.**

Prompt 4 also said the IQR-rejected points did not seem to be ignored. I
checked: they are excluded from the mean, both in the ingest and here. A
test pins this, and the `n` in the table counts only kept samples.

Two things make them *look* included:
- The black de-spiked line still runs through them, because it is the whole
  de-spiked profile.
- Before the fix above, a spike was never de-spiked. It stayed on the line,
  sometimes marked with a red ×, sometimes not.

With the fix, isolated spikes disappear from the line. What gets rejected
now are runs of ≥ 2 high samples, which a 3-point median cannot remove
(e.g. 4903848/69 at 8–10 dbar).

One more observation: on a very tight ML profile, the 1.5 × IQR filter in
log space rejects samples that are close to the mean. On 1902368/25 it
rejects 5 of 22, all within ~15 % of the mean.

Options:
- **A** *(recommended)*. Keep the line as is and keep the filter
  (Bisson et al.).
- **B**. Break the de-spiked line at the rejected samples, so it shows only
  what is averaged.
- **C**. Also revisit the filter (e.g. a floor on the IQR) as part of the
  AP-Q16 re-derivation.

**Your answer:**  Agreed, go with `A`

#### Round 3 resolved (2026-11-19)

- **AP-Q16 = A.** The ingest fix and the `mld_summary` re-derivation are
  planned in `claude_prompts/v2/de-spike-fix.md`, with Round 1 there (DS-Q1 to
  DS-Q7). Until that runs, the viz keeps drawing the stored values, and shows
  the sample de-spike as the dotted line, a second table line and a note.
- **AP-Q17 = A.** No change: the de-spiked line runs through the whole
  profile, and the log-IQR filter stays as it is.

### Init

*Answer inline under each **Your answer:**. Where I have a recommendation it
is marked.*

**I-Q1: Which data versions should the tools cover?** The live v2 DB holds
2.0, 2.0.1, 2.1 and NASA-GIOP 1.1, and v1 (1.0) sits frozen beside it.
- **A (recommended).** 2.1 by default (the newest family through
  `version_family`), with a `version=` argument everywhere. Add
  side-by-side 2.0-vs-2.1 views where they are cheap: the chains and
  `full_table.csv` make the pairing trivial. NASA-GIOP shown as an overlay
  on the `b_bp` views. v1 is read only when asked, and always read-only.
- **B.** 2.1 only.

**Your answer:** Use A.  It is likely that there will be future versions of the DB as well, e.g. v3.0

**I-Q2: Output medium.** What form should the tools take?
- **A (recommended).** Python functions in `pab/viz/` that return
  matplotlib figures, for notebooks and scripts. Each takes a read-only
  store (or a DB path) plus a `fit_id` / `matchup_id` / `profile_id`. Thin
  CLI wrappers come later, if wanted.
- **B.** Interactive (Bokeh, as in `pab/report/interactive.py`, or a
  panel/dash app) for browsing many matchups.
- **C.** Both, with A first.

**Your answer:**  I wish for these tools to be interactive.  Let us use Bokeh

**I-Q3: Argo profiles are not stored locally.** PAB keeps only the
mixed-layer summaries (`mld_summary`) and the QA PNGs (most on the PVC or
AIOcean; 5,453 v2 ones in `gallery/v2_argo_qa/`). To inspect the profiles
themselves (`BBP700`, `CHLA`, `CDOM`, T/S against pressure, with the MLD and
the PACE value marked):
- **A (recommended).** Fetch on demand with `pab.argo.fetch.fetch_profile`
  and cache each profile as a small NetCDF under
  `$PAB_DATA_DIR/v2/argo_profiles/` (that is a new directory, so it writes
  data, but never the DB). Only the 15,976 matchup profiles are in scope.
- **B.** Bulk-fetch all matchup profiles once (network-heavy; argopy at
  ~1 s/profile with 12 processes, so ~5 h).
- **C.** Show only the existing QA PNGs and the `mld_summary` numbers.

**Your answer:** Let us try fetch on demand for now.

**I-Q4: Where do the tools live relative to `pab/plotting/`?**
`pab/plotting/` already holds `fit_fig.reconstruct_fit` and the population
plots used by the report. My proposal: `pab/viz/` is the exploration layer.
It imports and reuses `pab/plotting` and `pab/metrics`, does not modify
them, and never feeds the report pipeline. Agree, or should the two merge?

**Your answer:**  I agree.  Reuse code where possible.

**I-Q5: Which views first?** My proposed first set, in priority order:
1. **Rrs-fit inspector** for one fit: observed `Rrs` ± σ, model median and
   band, residuals, the `b_bp(λ)` / `a_nw(λ)` posteriors, a corner plot of
   the six parameters, with 2.0 and 2.1 overlaid on the same spectrum.
2. **Matchup card**: the float profile (I-Q3), the PACE `b_bp(700)` and Chl
   from all ten pixels, NASA-GIOP, and the geometry, on one page.
3. **Population explorer** for `b_bp` and the other products: sat vs float,
   2.1/2.0 ratios against θ_s / θ_v / basin / season / `B_p` / χ², and a
   filter-and-pick that returns `fit_id`s to feed views 1 and 2.

Add, drop or reorder?

**Your answer:**  I will answer this with individual prompts

**I-Q6: Doc housekeeping.** The Working agreements were copied from the
rerun doc. Two of them are about fitting (the `PAB_DATA_DIR` for chain
writes, `PYTHONWARNINGS` for fit runs). Viz work should only *read*. Shall
I add "viz tools open every DB read-only and write only figures under a
scratch or an explicit output dir", and trim the fit-only items?
*(My recommendation: yes.)*

**Your answer:** Yes, that is correct.  These are read-only tools.

### Init, round 2 (2026-11-19)

**I-Q7: How does a Bokeh tool run?** This decides the architecture.
Views 1–3 all need Python on interaction: a reconstruction (2–8 s) or a
network fetch when a fit or matchup is picked. Standalone HTML with
`CustomJS` cannot do that.
- **A (recommended). A Bokeh server app**, `bokeh serve` on the
  workstation, bound to **localhost**, viewed through the VS Code port
  forward or an SSH tunnel (`ssh -L 5006:localhost:5006 …`). One app with
  a tab per view, so a pick in the population explorer opens the fit or
  matchup view. Launched with something like
  `python -m pab.viz --db $PAB_DATA_DIR/v2/pab.db`. It needs no new
  package.
- **B. Static HTML per object.** A command writes a self-contained HTML
  for a given `fit_id` / `matchup_id`: pan, zoom, hover and toggles, but
  no navigation between objects. Easy to share or attach; precomputed only.
- **C. Both.** A first, with B as an "export this view" button.

**Your answer:**  I agree, use A

**I-Q8: Do fetched Argo profiles stay on disk?** "On demand" (I-Q3) still
leaves a choice, and the read-only rule (I-Q6) bears on it.
- **A (recommended). Memory only**: an in-process LRU cache for the
  server's lifetime. Strictly read-only. A re-fetch costs ~1–6 s per
  profile after a restart.
- **B. An opt-in disk cache**: `--argo-cache DIR` (off by default), one
  small NetCDF per profile, never under `$PAB_DATA_DIR` unless you name it.
- **C. An always-on disk cache** at `$PAB_DATA_DIR/v2/argo_profiles/`. That
  makes it the one place the tools write data.

**Your answer:** Let us try memory only for now.

**I-Q9: Which machine views it?** Do you view from the workstation itself
(VS Code forwards `localhost:5006` automatically), or from a laptop? That
decides only the launch instructions in HOWTO. *(No recommendation needed;
A works either way.)*

**Your answer:** I am going to build it on my workstation but run it on my laptop too.
I wish to be able to launch from the command line, not VS Code.

### Init, round 3 (2026-11-19)

**I-Q10: On the laptop, where does the app run, and with which data?**
The full data is the 302 MB v2 DB plus 37 GB of chains (18 GB for 2.1
alone), and the fit reconstruction also needs `bing`, `robust` and the
`ocean14` stack (JAX).
- **A (recommended). Both modes, one code path.**
  1. *Tunnel*: the server runs on the workstation and the laptop views it
     through `ssh -N -L 5006:localhost:5006 <workstation>`. No data or
     environment on the laptop, and every view works.
  2. *Local*: `pab-viz` runs on the laptop with the DB copied there (the
     public `s3://pab/v2/pab.db` once rerun Task 5 publishes 2.1, or an
     rsync until then) and chains optional. Without chains the fit
     inspector shows the stored posterior summaries and the fit PNG, and
     the start-up capability check reports this.
- **B. Local only**, with a full copy of the DB and the 2.1 chains on the
  laptop (~18 GB) and the full stack installed.
- **C. Tunnel only.**

Also: does the laptop already have a working `pab` env (bing, robust,
JAX)? If not, the local mode is DB-only until it does.

**Your answer:**  The laptop has a working `pab` environment and I will have a local copy

## Logs

### 2026-11-19 (Init prompt 1: Context updated for the finished v2.1 run; six questions posed)

With Claude Opus 5.5. Read this file, `claude_prompts/v2/build_v2_1_rerun.md`
in full (Plan, Q&A, and the logs through Task 4), and HOWTO §3 and §5–5c.
The Context list pointed at `built_v2_1_rerun.md`. The file is
`build_v2_1_rerun.md`, and the list now says so. Then I checked the current
state **read-only**: the DB through a `mode=ro` URI; only `ls`, `du` and
`sha256sum` on the files. No code, DB or data was changed.

**Context rewritten** (the old "code seams" table was the 2.1 fit's; it
is replaced by a viz-oriented one):
- *What v2.1 is*: config, the run, and the headline ratios (from the rerun
  log, cross-checked against the live counts).
- *Outputs*: the live v2 DB (schema 6, sha `d0c286bf…`) with row counts
  per table and the columns a viz tool needs; the `fits` breakdown by
  version and `geom_mode`; the BING and NASA `fit_results` quantity names;
  the chain NPZ layout (`chains` (10000, 16, 6), params `Adg, Sdg, Aph,
  Bnw, beta, Bp`, 136 bands, 400–699 nm); figures, scenes and QA plots with
  where each actually lives; and the `versions/v2.1/` analysis products.
- *Code seams for viz* with line numbers verified today.
- *Open items*: rerun Task 5 (publish) is not done, so S3 still has no 2.1.

**What I learned that matters for viz:**
- `fits.chains_path` holds PVC paths. `load_chains` resolves through
  `PAB_DATA_DIR`, so a viz session needs `PAB_DATA_DIR=…/PAB/v2`.
- 2.1 fit figures are local, with workstation `figure_path`s. The 2.0 ones
  and almost all scenes and QA plots are not.
- No Argo profile arrays are stored anywhere: only `mld_summary` and PNGs.
  A profile viewer needs a fetch, hence I-Q3.
- `versions/v2.1/full_table.csv` already pairs every 2.1 fit with its 2.0
  or 2.0.1 reference, which makes it a ready-made population input.
- `n_neg_blue` is present on the 2.1 rows too, and 50 pixels have NULL
  angles (irrelevant to 2.1 fits, relevant to geometry plots).

Questions I-Q1 to I-Q6 are in Q&A / Init.
### 2026-11-19 (Init prompt 2: JXP's answers folded in; Working agreements, Context and a new Code section; I-Q7 to I-Q9 posed)

With Claude Opus 5.5. No code, DB or data touched.

**Answers folded in.**
- **I-Q1 = A**, plus "future versions such as 3.0". This became a code rule:
  no version literals, all resolution through `compare`, and old-vs-new
  pairing on `matchup_id` + `pixel_id`. `geometry_shift_summary` already
  does that pairing generically and is the pattern to reuse. Pairing on
  `rrs_source` would have tied the tools to replay-based versions.
- **I-Q2 = Bokeh, interactive.** Checked `ocean14`: bokeh 3.9.1, tornado
  and corner are present; panel, holoviews, Jupyter and ipywidgets are
  not. Without Jupyter, a `bokeh serve` app is the natural interactive
  mode. Raised as I-Q7, because static HTML cannot run a reconstruction or
  a fetch on click.
- **I-Q3 = on demand.** Disk caching would be the only write the tools
  make, which conflicts with I-Q6, so it is I-Q8 (recommended: memory only).
- **I-Q4 = agree.** `pab/viz/` reuses and does not modify.
- **I-Q5 deferred** by JXP to individual prompts; the three candidates are
  kept in Code.
- **I-Q6 = yes.** Working agreements rewritten. The fit-only items are
  replaced by the read-only rule (`Store.open("file:…?mode=ro",
  create=False)`, checked at `pab/db/store.py:47`), the `PAB_DATA_DIR`
  rule for loading chains, and the `DomainWarning` note for
  reconstructions. S3/AIOcean/Nautilus are dropped from the confirm list,
  and a non-localhost server bind is added.

**Context:** a "Decisions" table; three code-seam rows (read-only
`Store.open`, the version helpers, `report/interactive.py`).

**Code section:** JXP's existing rules (reuse, Python only, imports at the
top, `ocean14`) kept at its head, with notes on how they apply to Bokeh
(callbacks in Python, not `CustomJS`; top-level `bokeh`/`argopy` imports are
fine because nothing in the pipeline imports `pab.viz`). Below them: the `pab/viz/` layout (`data`,
`fits`, `argo`, one `bokeh_*` builder per view, an app entry point), the
rules (version-generic, model-pair aware, reuse first, per-session
connections for thread safety, tests without network) and the candidate
views.

New questions: I-Q7 (Bokeh server vs static HTML), I-Q8 (Argo cache),
I-Q9 (which machine views the app).

### 2026-11-19 (Init prompt 3: round-2 answers folded in; launch design added; I-Q10 posed)

With Claude Opus 5.5. No code, DB or data touched.

- **I-Q7 = A** (Bokeh server, a tab per view, localhost), **I-Q8 = A**
  (memory-only Argo cache) and **I-Q9** (built on the workstation, also run
  on the laptop, launched from the command line) were added to the
  Decisions table. The Working agreements now state the memory-only cache
  and the localhost default.
- **Code / Layout:** the open `app/ or __main__` row became `app.py` (the
  document, tabs, shared selection state) and `__main__.py` (the launcher).
- **Code / Launch (new):** `python -m pab.viz` and a `pab-viz` console
  script (`setup.py` currently registers only `pab = pab.pipeline:main`).
  A programmatic `bokeh.server.server.Server`, so the launch works from
  any shell and cwd, which is what "command line, not VS Code" needs. The
  flags; a start-up capability check (DB, chains, `bing`/`robust`,
  network) that disables panels rather than crashing, because the laptop
  may hold only the DB; and HOWTO launch notes, including the SSH tunnel.
- **Code / Rules:** slow work runs off the event loop with
  `add_next_tick_callback`; stored paths are resolved by basename, never
  hard-coded, so the same code runs on both machines.
- **I-Q10** asks how the laptop gets its data: a tunnel, a local copy, or
  both (recommended: both, one code path). It also asks whether the laptop
  has the bing/robust stack. The first tool's prompt can start without
  the answer, since the capability check covers both cases.

### 2026-11-19 (Argo+PACE prompt 1: design questions AP-Q1 to AP-Q9 posed; I-Q10 folded in)

With Claude Opus 5.5. No code written, as the prompt asked. Read-only
checks on the live v2 DB, plus code reads in `pab/argo/{fetch,summary}.py`,
`pab/pipeline.py` (the ingest fetch), `pab/fit/run.py` and
`pab/fit/models.py` (the CI percentiles and `varRrs`), and bing
`bbNWPow` / `aNWExpBricaud`.

- **I-Q10** (the laptop has the env and a local copy) was added to the
  Decisions table.
- **A Context error is corrected:** `profiles.profile_id` is an integer row
  id, not `<wmo>_<cycle>`. `matchup_id` is the one that starts
  `<wmo>_<cycle>_`. This drives AP-Q1.
- **Facts gathered for the tool** (recorded at the top of Q&A / Argo+PACE):
  - one matchup per profile and one 2.1 fit per matchup, always the
    rank-1 pixel;
  - MLD range 10–684 m, with 91 matchup profiles lacking one;
  - the stored Argo `bbp700` is a de-spiked, IQR-filtered ML mean, and its
    `_std` is the sample scatter, NULL for 697;
  - ingest used gdac/expert with no QC filter, so a re-fetch can reproduce
    the stored mean exactly;
  - the `Pow` amplitude is at 600 nm, so "bbp700 amplitude" needs
    defining;
  - `a_dg` is CDOM + detritus at 400 nm;
  - the CIs are 5–95 %;
  - the `Rrs` error is the PACE `Rrs_unc` or a 2 % floor.
- **Questions AP-Q1 to AP-Q9:** input identity (wmo + cycle), which `bbp`
  points, the measured-value error band, the axes and the no-MLD case,
  the `Rrs` uncertainty and whether the laptop has the chains, the value
  table (`Bnw` at 600 nm vs `bbp700`, `a_dg(440)` as "CDOM"), the
  versions and NASA-GIOP overlays, the header, and delivery as the first
  `pab-viz` tab.

### 2026-11-19 (Argo+PACE prompt 2: round-1 answers reviewed; AP-Q10 to AP-Q15 posed; no code)

With Claude Opus 5.5. As the prompt asked, no code was written.

- Folded JXP's AP-Q1 to AP-Q9 answers into a "Round 1 resolved" table in
  Q&A / Argo+PACE. The departures from my recommendations: the
  residuals are **added** (AP-Q5); the previous-version model is **not**
  overlaid, though the version selector stays (AP-Q7); θ_s/θ_v are
  **dropped** from the header (AP-Q8).
- Read-only checks: 838 floats have matchups, with 1–232 matchup cycles
  each, so the WMO input should be an autocomplete, not a plain dropdown.
  The stored `fits.chisq` is the **reduced** χ² (`run.py:434`, `:815`),
  so the header can call it χ²_red; on 2.1 it spans 0.007–232, mean 0.59.
- **Round 2 questions:**
  - AP-Q10: residual placement and units;
  - AP-Q11: what the version selector lists (families with the patch
    overlay), and whether the laptop also has the 2.0 chains;
  - AP-Q12: how the PACE and the GIOP `bbp700` are drawn on the depth
    panel;
  - AP-Q13: stored against re-fetched Argo values when the GDAC has
    reprocessed;
  - AP-Q14: layout;
  - AP-Q15: failure cases.

### 2026-11-19 (Argo+PACE prompt 3: round-2 answers folded in; the Argo + PACE tab built, tested and run)

With Claude Opus 5.5. All six round-2 answers took the recommendation
(recorded under "Round 2 resolved").

**Code** (`pab/viz/`, see Code / Status for the module table):
- **Read-only throughout.** The DB is opened via a `mode=ro` URI with no
  migrate, and the test checks that a `DELETE` raises. Chains are only read.
  Argo profiles live in an in-memory LRU only.
- **Version-generic.** Families come from `compare` (`version_families` →
  `["2.1", "2.0"]`, labels `"2.0 (+2.0.1)"`), and `bing_fit` overlays the
  patch rows with `compare.overlay_patch`. Nothing hard-codes "2.1".
- **Reuse.** The fit is `fit_fig.reconstruct_fit` and `_config_from_row`;
  the Argo statistics are `summary.moving_median`, `iqr_inlier_mask` and
  `summarize_profile` with ingest's arguments; the GIOP shift is
  `compare.giop_bbp_to_700`.
- `pab.config.DATA_DIR` is bound when `pab` is imported, which happens
  before `python -m pab.viz` runs. `set_data_dir` therefore rebinds it in
  `pab.config` and `pab.fit.artifacts`, for reads only.
- The server is programmatic (`bokeh.server.server.Server` +
  `FunctionHandler`), so the launch works from any shell. Slow jobs run in
  a 4-thread pool and return through `doc.add_next_tick_callback`; a
  per-session token drops stale results.
- `setup.py` gained `pab-viz = pab.viz.__main__:main`. The editable install
  in `ocean14` was refreshed (`pip install -e . --no-deps`).

**Verification.**
- `pab/tests/test_viz_argo_pace.py`: **10 passed**. Full suite **555
  passed, 1 skipped** (was 545); `ruff check pab` is clean.
- A live re-fetch of 1902368/25 reproduced the stored ML mean exactly
  (0.0017238 m⁻¹, n = 66). `a_dg(440)` from the chains (0.569) is
  consistent with the stored `Adg(400)` 1.23 and `Sdg` 0.0195.
- The real server was driven with headless Chrome over CDP:
  - typical (4902680/6);
  - deep MLD 494 m (1902304/156, with IQR-rejected samples marked);
  - no MLD (7901106/233);
  - LM failure (1902347/214, red badge);
  - the 2.0-family switch on a patched profile (1902498/12: header
    "BING 2.0.1 (patch)", reconstruction re-run) with the GIOP toggle on.

  Logged timings: Argo fetch ~5.8 s; reconstruction 4.6–5.2 s cold and
  1.3–1.6 s warm.
- **Bug found and fixed** on the first live run: the Argo fetch failed
  with `_DeadlockError` on `argopy.xarray`, because two workers were
  importing at once. Fixed by importing on the main thread (Code / Status
  / Gotcha). Re-verified with concurrent fetch and reconstruction.
- Also fixed: launcher log lines were block-buffered when piped (now line
  buffered); crowded axis tick labels (now 1 decimal).

**Docs:** HOWTO §5d (launch, flags, capability report, tunnel). Nothing was
published, and no DB or data file was written.

### 2026-11-19 (Argo+PACE prompt 4: Rrs axis and zero line, CDOM row removed; the ingest de-spike bug found; AP-Q16/17 posed)

With Claude Opus 5.5.

**Requested changes** (`pab/viz/bokeh_argo_pace.py`):
- **`Rrs` y-axis** now starts at 0, or below 0 when the data or the bands go
  negative. It is recomputed whenever the observed spectrum or the model
  arrives (`_autorange_rrs`).
- **Dashed dark-gray (`#444`) line at `Rrs` = 0.**
- **CDOM row removed** from the table.

**De-spike investigation.** The "de-spiked line follows every point" report
is a real bug, and it lives in the ingest code
(`summary.mixed_layer_mean` → `moving_median` over the full pressure
column).
- With `BBP700` on every 2nd/3rd level of the merged profile, each window
  holds one sample. Nothing is de-spiked, and samples are copied into the
  empty levels, which inflates `n_points`.
- Survey of 60 random matchups:
  - 55 have gaps between samples;
  - 46 have an inflated `n_points` (median ×1.6);
  - the ML mean changes by 0.5 % (median), 2.0 % (90th pct) and 6.8 % (max).
- Details and options are in Q&A / AP-Q16. The rejected-points question is
  AP-Q17.

**Viz-side fix**, which leaves the stored values alone:
- `argo.despike_samples` takes the 3-pt median over the samples only.
- `BbpLayers` carries the `ingest_*` statistics (what `mld_summary` holds)
  next to the corrected ones.
- When the two differ, the view shows a dotted "ML mean, sample de-spike"
  line, a second line under the Argo `b_bp(700)` in the table, and a note.

No ingest code was changed and no DB was written; that is AP-Q16.

**Verification.**
- New test `test_gapped_profile_is_despiked_sample_to_sample`. The panel test
  also checks the `Rrs` floor, the zero line and that the CDOM row is gone.
- Viz tests: 11 passed. Full suite: **556 passed, 1 skipped**. `ruff` is
  clean.
- Live server, headless Chrome:
  - 1902368/25 (negative `Rrs` in the blue, zero line visible; stored n=66,
    corrected n=17);
  - 4903848/69 (a 2-sample spike rejected);
  - 4902680/6.

### 2026-11-19 (Argo+PACE prompt 5: AP-Q16/17 answered; de-spike-fix prompt doc written)

With Claude Opus 5.5. Both answers took the recommendation (see Q&A "Round 3
resolved").

**AP-Q16 = A.** I wrote `claude_prompts/v2/de-spike-fix.md`, which JXP
will execute later. It has:
- the bug and the 60-matchup survey;
- the code seams, verified today:
  - the fix goes in `summary.mixed_layer_mean`;
  - `qa.plot_profile` has the same display bug;
  - `pab.viz.argo` should then call the shared function;
- a five-task plan: code; safety run (stop for review); refresh; impact on
  the PACE vs Argo metrics; close-out;
- Round 1 questions DS-Q1 to DS-Q7: where the new values live
  (`mld_summary` is one row per profile), which profiles, the version label,
  GDAC drift, keeping the old recipe, where to run, and the QA figures.

Checked while writing it:
- BING reads only `mld_summary.chla`, which has no de-spike, so **no re-fit
  is needed**;
- `mld_summary` holds 59,620 rows (55,948 with a `bbp700`; 15,279 matched).

**AP-Q17 = A.** No code change.

No code was changed in this prompt and no DB was touched. The prompt-4 viz
changes are what JXP will test next.
