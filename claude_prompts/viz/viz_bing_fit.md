# Viz tool to fuss with a BING fit

## Goal

This doc will be used to develop a tool to inspect a BING fit and
fuss with its parameters.
In the context of PAB

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

- The newest BING family is the default (2.1 today), with a `version=` argument everywhere. Cheap old-vs-new views are side by side, and NASA-GIOP is an overlay on the `b_bp` views. v1 is read only on request. **Future versions (e.g. 3.0) must work unchanged**: no version string is hard-coded; all version logic goes through `pab.metrics.compare` (`version_family`, `newest_bing_version`, `overlay_patch`). |
- The tools are interactive Bokeh apps (bokeh 3.9.1 is in `ocean14`; `panel`, `holoviews` and Jupyter are **not**). 
- `pab/viz/` is the exploration layer. It reuses `pab/plotting`, `pab/metrics`, `pab/fit` and `pab/argo`, does not modify them, and never feeds the report pipeline. 
- Read-only tools; the Working agreements are rewritten to match. 
- **One Bokeh server app**, a tab per view, so a pick in one view opens another. Bound to `localhost` by default. 
- Built on the workstation, **also run on JXP's laptop**, and **launched from the command line** (not through VS Code). 

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

## Code

- When possible reuse existing code in the PAB package.
- Python only for now.  
- Place import commands at the top of the file.

If you need to run Python, use the `ocean14` conda environment.


- "Python only" in practice: Bokeh layouts are built in Python, and
  interactivity goes through Python callbacks (a Bokeh server, I-Q7). No
  hand-written `CustomJS` unless JXP asks for it.
- "Imports at the top": `bokeh` and `argopy` are imported at module top in
  `pab/viz/`. This is unlike `pab/report/interactive.py`, which imports
  bokeh lazily. That is fine because `pab.viz` is never imported by the
  pipeline (I-Q4), and `pab/viz/__init__.py` stays empty, so
  `import pab` stays light.

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


## Prompts

### Design

1. We are going to build a Bokeh tool that will show a BING fit for a given matchup
(specified by `wmo` and `cycle_ID`).  The left panel will mimic the PACE fit that is generated by the Bokeh code in `pab/viz/bokeh_argo_pace.py`.  The right panel will show the absorption and scattering spectra for the fit as generated by the code in `pab/viz/fits.py`.
It will be called from the command line with the `wmo` and `cycle_ID` as required arguments.
Before creating the figure, discuss it with me in the `Q&A/Design` section below.
It should be straightforward for the user to modify any of the BING parameters, starting
from the best fit values.
After modifiation, we will not show the 90% confidence intervals for the model,
only the new model.  We should leave the orignial model in orange and draw the new
model in blue in the left panel.  We will show the modified absorption and scattering spectra 
in the right panel in another line-style.
Use Opus 5.5.  Log your work in Logs.

2. I have answered the first round of questions in the `Q&A/Design` section.  Please review my answers
and continue the discussion.  Do not generate the code yet.
Use Opus 5.5.  Log your work.

### Implement

1. I have answered the next round of questions in the `Q&A/Design` section.  Please review my answers
and proceed to write the code.
If any issues come up, discuss them with me in the `Q&A/Implement` section below.
Use Opus 5.5.  Log your work.

2. Please read my answers in the `Q&A/Implement` section below
and make the necessary changes.
If any issues come up, discuss them with me in the `Q&A/Implement` section below.
Use Opus 5.5.  Log your work.

3. I have answered questions BF-I8 and BF-I9 in the `Q&A/Implement` section.  Please review my answers
and edit the code accordingly.  
If any issues come up, discuss them with me in the `Q&A/Implement` section below.
Use Opus 5.5.  Log your work.


## Q&A

### Implement

*Round 1 (2026-11-23), from Implement prompt #1. The tool is built and
tested. Below: how to run it, what was built, and the issues that came up.
Each issue has my recommendation. The code already follows it, so answer
only if you want a change.*

#### Run it

```bash
export PAB_DATA_DIR=/home/xavier/Oceanography/data/Color/PAB
/home/xavier/miniconda3/envs/ocean14/bin/python -m pab.viz.bing_fit --wmo 2902882 --cycle 96 --show
#   [--version 2.0] [--matchup-id …] [--db …] [--data-dir …] [--port 5007]
# or, after `pip install -e . --no-deps` (BF-I6; done in ocean14 on the workstation):
pab-bing-fit --wmo 2902882 --cycle 96 --show
```

Start-up selects the fit, builds the models, reconstructs the posterior and
warms the JIT. This takes ~8–10 s on the workstation, and then the server
binds to `localhost:5007`. One fit per server; restart for another (BF-Q15).
A missing matchup, fit or chain file is reported and the tool exits with
code 2 (BF-Q17).

#### What was built

| File | What |
|---|---|
| `pab/viz/bing_fit.py` (new) | `BingFitView` (the figures, sources, widgets and callbacks), `select_fit`, a server-free `make_bing_fit`, `prepare` (builds the fit's models once per server), `make_document`, `main` |
| `pab/viz/fits.py` | `ForwardModel` (models built once; `evaluate(params)` → `Evaluation`: `Rrs`, IOPs, χ², derived quantities, emulator out-of-domain lines), `ParamSpec`, `domain_messages` |
| `pab/viz/bokeh_argo_pace.py` | Panel builders moved out of `ArgoPaceView` (BF-Q9): `rrs_figures`, `rrs_glyphs`, `set_rrs_scale`, `resid_figure`, `iop_figure` (+ `IOP_STYLES`), `autorange_rrs`, `autorange_iops`, `table_html`, `header_html`; `load_selection(matchup_id=)`. No visual change; its tests pass unchanged |
| `pab/viz/data.py` | `matchup_for(matchup_id=)`, `matchup_ids_for` |
| `pab/viz/server.py` (new) | Launch helpers shared with `pab-viz` (`--db`, `--data-dir`, localhost / `--allow-remote`, logging, `serve`) |
| `pab/viz/__main__.py` | Now uses `server.py`; same options and messages |
| `pab/tests/test_viz_bing_fit.py` (new) | 12 tests: slider ranges, start state, bands after edit / reset / on demand, auto-range, widgets (slider, number box: widen, out-of-prior, non-number), domain notes, self-check, async stale-result drop, lookup errors, CLI, and a **real-data** test (skipped without the v2 DB) |

Every model computation reuses pipeline code. The forward model is
`run.reconstruct_rrs`. The derived quantities come from
`run.extract_quantities`, given the single vector as a 2-step, 1-walker
chain. χ² uses the `run._fit_diagnostics` formula. Checks: on a real 2.1
fit, χ² at the posterior medians equals `fits.chisq` (to 1e-7), and `Adg`,
`Aph`, `B_p`, Chl equal `fit_results`. All 575 tests pass, `ruff` is clean,
and a live server session on `7902116_30` rendered correctly.

#### Issues

**BF-I1: Most fits are already outside the emulator's `B_p` domain.** I
used `bing.evaluate.robust_domain_check` to surface the emulator's
`DomainWarning` (BF-Q14), because the jitted forward model never emits it
(the check skips traced inputs). The emulator is trained on **`B_p` ∈
[0.01026, 0.018]**, while the fit prior is [0.004, 0.05]. Of the 15,971
2.1 fits, the posterior-median `B_p` is **below that range for 4,248 and
above it for 7,435 (73 % in all)**. Example: `2902882_96`, median `B_p`
0.032. A warning shown for every fit would be noise, so:
- **Done (recommended).** Features already out of range at the posterior
  medians get a **grey standing line** ("The fit itself (posterior
  medians) is outside the emulator's training range: …"). The **amber
  warning** appears only when an edit pushes a *new* feature out of range
  (e.g. `eta_bb` after raising `B_p`).
- This is the "robust `DomainWarning` on the `B_p` breach for most fits" in
  the Working agreements, now with a number. It probably matters beyond this
  tool (2.1 `b_bp` is retrieved where the emulator is extrapolating in
  `B_p`), and may deserve a line in the 2.1 write-up.

>A. Ok, your change is fine.

**BF-I2: Auto-range on edit (a change from the design).** In Design I said
edits would not re-range, to keep a zoom. In the first render, raising
`Bnw` by 0.3 dex pushed the blue `Rrs` and the dotted `b_bp` off the axes,
which hid the curve being adjusted. **Done:** an "auto-range on edit"
checkbox, **on** by default. Untick it to keep a zoom while editing; load
and "Reset to fit" always re-range.

>A. This is good

**BF-I3: "modified" vs "fit" at the start.** The fit column shows the
stored **posterior medians of each quantity**. The modified column shows
each quantity computed **at the median parameter vector**. They agree
exactly for the parameters (`Adg`, `Sdg`, `Aph`, `β`, `B_p`, Chl). For
derived spectral values they differ slightly, e.g. `b_bp(440)` 1.21e-3 vs
1.22e-3 on `2902882_96`. This is the BF-Q1 caveat, and is expected.
Nothing to do unless you want a footnote under the table.

>A. This is fine; no footnote

**BF-I4: A doc comment in `pab/fit/models.py`** (near the top, on
`CEILING_FIELDS`) says `Adg`/`Aph` are "log10 amplitudes at 440 nm". In
BING's `ExpBricaud`, `Adg` is the amplitude at **400 nm** (`a_dg(λ) = Adg
exp(−Sdg(λ − 400))`); `Aph` is at 440 nm. The editor labels them
`a_dg(400)` and `a_ph(440)`. I did not touch `pab/fit` (outside the viz
layer). Fix the comment?

>A. Yes, fix the comment

**BF-I5: Commit `db84de4` is partial.** You committed while I was working
(12:25). The commit contains `bing_fit.py`, `server.py`, `__main__.py` and
the test file, but **not** the `bokeh_argo_pace.py`, `data.py` and
`fits.py` changes they import (`header_html`, `ForwardModel`,
`matchup_ids_for`, …). On its own, `db84de4` does not import. The working
tree is complete and green. The five files in `git status` (`M`) are the
rest.

>A. I will handle the git commands

**BF-I6: A console script?** `pab-viz` is in `setup.py`
(`console_scripts`). Add `pab-bing-fit = pab.viz.bing_fit:main`
(recommended; needs `pip install -e .` again on both machines)? I left
`setup.py` alone.

>A. Yes, add the console script

**BF-I7: Notes on the design as built** (no answer needed):
- Thread safety: one `ForwardModel` is shared by every browser session,
  with a lock around `evaluate`. The lock also covers
  `warnings.catch_warnings`, which is process-global. Each session opens its
  own read-only store.
- The first JAX evaluation compiles (~5 s); `prepare` does it before
  serving. After that an evaluation takes ~35 ms, including the un-jitted
  domain check.
- The NASA-GIOP mark on the IOP panel is hidden at start; click its legend
  entry to show it.

>A. Ok, good.

#### Actions on the round-1 answers (2026-11-23)

- **BF-I1, BF-I2, BF-I3, BF-I7:** accepted as built; no change (no
  footnote, per BF-I3).
- **BF-I4:** fixed in both places in `pab/fit/models.py`: the
  `CEILING_FIELDS` comment and the `FitConfig` docstring (`bbp600_max,
  adg_max, aph_max`). Both now say `Adg` is the amplitude at the **400 nm**
  pivot and `Aph` at 440 nm, citing `bing/models/anw.py`. This changes
  comments only; no other code in `pab/` made the 440 nm claim.
- **BF-I5:** git left to JXP. The uncommitted set is now
  `claude_prompts/viz/viz_bing_fit.md`, `pab/fit/models.py`,
  `pab/tests/test_viz_bing_fit.py`, `pab/viz/{bing_fit,bokeh_argo_pace,data,fits}.py`
  and `setup.py`.
- **BF-I6:** `pab-bing-fit = pab.viz.bing_fit:main` is added to
  `setup.py`'s `console_scripts`. I reinstalled `ocean14` on the
  workstation with `pip install -e . --no-deps`, and `pab-bing-fit --help`
  works. **The laptop needs the same reinstall** after you pull.

#### Round 2 (2026-11-23), from Implement prompt #2

Your revised Design answers are now in the code:

| Q | Revised answer | Change |
|---|---|---|
| BF-Q2 / BF-Q3 | Fit space; no sliders (too coarse); a number box and ±10 % of the current value | Sliders removed. Each row is now **[label] [−10 %] [box] [+10 %] [↺] [physical value]** |
| BF-Q4 | Update on Enter in a box or on a ±10 % click | As built: the box's `value` callback fires on Enter (and on leaving the box), and each button click re-evaluates |
| BF-Q5 | **B**: keep the original bands | The orange `Rrs` band and the IOP bands **stay visible throughout**; only the modified model has no band. The "show fit bands" checkbox and the legend workaround (BF-I2) are gone, since nothing hides any more |

Checked: 30 viz tests pass (12 in `test_viz_bing_fit.py`, rewritten for
the buttons) and `ruff` is clean. Real `ButtonClick` events on `7902116_30`
gave exactly ×1.331 on `Bnw` after three "+10 %" clicks and ×0.9 on `β`
after one "−10 %"; ↺ restored the value. A headless-Chrome render shows
the bands kept under the edited curves.

**BF-I8: What "±10 % of the current value" means for a log10 parameter.**
For `Adg`, `Aph` and `Bnw` the box holds log10 of the value. Taking 10 % of
*that number* would be meaningless: for log10 `Adg` = −2.0, "+10 %" would
give −2.2, a **37 % decrease** in `Adg`, and the step would grow with
|log10|. So I scale the **physical** value:
- **Done (recommended).** "+10 %" multiplies the physical value by 1.1
  (+0.041 dex in fit space); "−10 %" multiplies it by 0.9 (−0.046 dex). For
  the linear parameters (`Sdg`, `β`, `B_p`) this is simply ×1.1 / ×0.9.
- **B.** Step the fit-space number itself by ±10 % (not recommended, as above).
- A different step size is one constant (`STEP_FRACTION`); a per-row step
  box would also be easy if you want one.

>A. Agreed, scale the physical value not the log10

**BF-I9: Edge cases of the steps** (no answer needed unless you disagree):
- A step that would leave the prior is **clipped to the bound**. Another
  step at the bound is refused with a note. `B_p` near its 0.004 floor is
  the likely case.
- A linear parameter at exactly 0 cannot be stepped by a percentage (`β`'s
  prior starts at 0). Type a value instead. No 2.1 posterior median is
  exactly 0, so this only arises if 0 is typed.

>A. No, do not clip to the bound.  The user can adopt any value.

#### Round 3 (2026-11-23), from Implement prompt #3

| Q | Answer | Change |
|---|---|---|
| BF-I8 | Scale the physical value, not the log10 | Kept as built (`step_value`: ×1.1 / ×0.9 of the physical value) |
| BF-I9 | No clipping; the user can adopt any value | Steps are **not clipped**, and the number box **accepts any finite value**. I applied "any value" to the box as well as the buttons; before, it refused values outside the prior. A value outside the prior gets a **note** ("`Adg` = 3 is outside its prior [−6, 1] (allowed; the fit never sampled there)"), not a refusal, and the note clears when the value is back inside. Only non-numbers and NaN/inf are refused. |

Also fixed while here:
- Because any value can now be typed, the forward model might fail. A
  failed evaluation now gives a note ("Evaluation failed (…). The plot shows
  the last successful evaluation."), and the next good evaluation clears it.
  Before, the note stayed for the rest of the session, and the synchronous
  (no-server) path raised instead.
- A "Refused …" note now clears as soon as a valid entry is made, even one
  that does not change the value.

Checked: 32 viz tests pass (two new: values outside the prior are accepted
with a note, and a failed evaluation gives a note that clears), and `ruff`
is clean. On the real fit `7902116_30` I evaluated five out-of-prior
values. All gave finite `Rrs`; the prior note fired every time, and the
emulator-domain note fired where it applies:

| edit | χ²<sub>red</sub> | emulator note |
|---|---:|---|
| `B_p` = 0.002 (prior floor 0.004) | 572 | `B_p` out of range |
| `B_p` = −0.01 | 28 | `B_p` out of range |
| log10 `Bnw` = −0.5 (ceiling −1) | 2.6e5 | `log10_u`, `eta_bb` out of range |
| log10 `Adg` = 1.5 (ceiling 1) | 244 | none |
| `β` = −0.5 (floor 0) | 1.85 | none |

**BF-I10: Physically impossible values still plot.** A negative `B_p` (or
a negative `Sdg`, or `β` < 0) is not just outside the prior: it has no
physical meaning. Yet the forward model returns a finite curve, e.g.
`B_p` = −0.01 gives χ² = 28, *better* than the legal `B_p` = 0.002. The
current notes say "outside its prior" and, for `B_p`, "outside the
emulator's training range", but do not say "non-physical". Options:
- **A (recommended).** Keep accepting any value (your BF-I9), but word the
  note more strongly for a **negative linear parameter** (`Sdg`, `β`,
  `B_p`): "non-physical: `B_p` < 0", in the amber warning style.
- **B.** Refuse negative linear parameters (a narrow exception to BF-I9).
- **C.** Leave as is.

**Your answers:**


### Design

*Round 1 (2026-11-23), from Design prompt #1. No code yet. Recommendations
are marked; I will build to them unless you say otherwise.*

#### What I checked first

- **Cost of one forward call.** I rebuilt a 2.1 fit's models at its own
  geometry (`_config_from_row` → `build_models` → `init_other_bits` →
  `set_inelastic_Ed`), then evaluated one parameter vector through
  `run.reconstruct_rrs` (robust_hybrid, Raman + Chl-fl, free `B_p`). It took
  about **0.08 s** per call on the workstation. Building the models is the
  slow step (the 2–8 s of `reconstruct`), and it happens once per fit. Live
  updates while a parameter is changed are therefore feasible.
- **The parameters** (`param_names` in every NPZ, model pair `ExpBPow`):

  | name | space in the chain | prior (2.1) | physical meaning |
  |---|---|---|---|
  | `Adg` | log10 | log-uniform [10⁻⁶, 10¹] | `a_dg` amplitude (m⁻¹) |
  | `Sdg` | linear | uniform [0.01, 0.02] | `a_dg` slope (nm⁻¹) |
  | `Aph` | log10 | log-uniform [10⁻⁶, 10¹] | `a_ph` amplitude (m⁻¹) |
  | `Bnw` | log10 | log-uniform [10⁻⁶, 10⁻¹] | `b_bp(600)` (m⁻¹) |
  | `beta` | linear | uniform [0, 2] | `b_bp` power-law slope |
  | `Bp` | linear | (fit_Bp prior; floor 0.004) | backscattering ratio for the robust phase function |

  Parameter names and spaces are read from the NPZ and the model objects,
  not hard-coded, so another model pair or a 3.0 fit would still work.
- **Reuse.** `ArgoPaceView` builds the PACE panel (`_rrs_glyphs`, the
  linear/log toggle, the residual strip) and the IOP panel inside one
  `__init__`. `fits.reconstruct` gives the posterior bands, but it does not
  keep the models, so it cannot evaluate new parameters.

#### Proposed layout

```
 header: WMO · cycle · date · lat/lon · BING <version> · χ²_red (fit) · χ²_red (modified)
 ┌───────────── left: PACE Rrs ─────────────┐ ┌──────── right: IOPs ────────┐
 │ [linear | log10]                         │ │ a_nw, a_dg, a_ph (left axis)│
 │ obs ± σ (black)                          │ │ b_bp (right axis)           │
 │ BING fit: orange median (+ band until    │ │ fit: solid, 5–95 % band     │
 │           the first edit)                │ │ modified: dotted, no band   │
 │ modified: blue line                      │ │                             │
 ├──────────────────────────────────────────┤ └─────────────────────────────┘
 │ residual strip /σ: orange fit, blue mod  │
 └──────────────────────────────────────────┘
 parameter controls: one row per parameter
   name | slider | number box | fit median [5–95 %] | physical value
   [Reset to fit]
```

#### Questions

**BF-Q1: What is the "best fit" starting point?**
- **A (recommended).** The **posterior median of each parameter**, from the
  post-burn chain, which matches the stored `fit_results` values. Caveat:
  the Rrs computed at the median parameters is *not* the same curve as the
  orange line, which is the per-band median over the posterior samples.
  The two are usually close but not identical. At load time I would draw
  the blue curve at the starting parameters, so you see this difference
  before you edit anything, and report the χ² of both.
- **B.** The **lowest-χ² sample** in the thinned chain. This is closer to a
  true best fit, but the NPZ stores no `log_prob`, so I would compute χ²
  over the samples (~1 s, once per fit).
- **C.** Re-run the LM warm-start. No, this is slow and is not stored.

>A. Yes, go with A

**BF-Q2: Which space do the controls work in?**
- **A (recommended).** The **fit space** (log10 for `Adg`, `Aph`, `Bnw`;
  linear for `Sdg`, `beta`, `Bp`). This matches the sampler, and a log
  slider is the natural way to move an amplitude. Each row also shows the
  physical value (e.g. `Adg = 5.7e-3 m⁻¹`).
- **B.** Physical units for everything.

>A. Yes, use the fit space.  I am worried that a slide may be too coarse to adjust
the parameters.  I would prefer to have a number box for each parameter and
the ability to increase/decrease the parameter by +/- 10% of the current value.

**BF-Q3: Slider ranges.** The log priors span 7 dex, which makes a slider
useless for fine work.
- **A (recommended).** Each slider spans the **posterior 5–95 % widened ×3
  about the median** (at least ±0.5 dex for the log parameters), clipped to
  the prior. A number box next to each slider accepts any value inside the
  prior, and typing a value outside the slider range widens the slider.
- **B.** The full prior range for every slider.

>A. See above.  We will avoid sliders for now

**BF-Q4: When does the model update?**
- **A (recommended).** **Live**, on slider release (`value_throttled`) and
  on Enter in a number box. Each call takes ~0.1 s and runs in the thread
  pool, with the same stale-result token as `app.py`.
- **B.** An explicit "Apply" button.

>A. On Enter in a number box, or if the +/- 10% button is clicked.

**BF-Q5: What happens to the bands after the first edit?** You wrote that
after a modification the 90 % CI is not shown, only the new model, with the
original in orange.
- **A (recommended).** Before any edit: orange median + 5–95 % band, and the
  blue start curve from BF-Q1. After the first edit: the **orange band is
  hidden** and the orange median stays. The blue line is the modified model,
  and the IOP bands are hidden in the same way. "Reset to fit" brings the
  bands back. A checkbox can still show the bands on demand.
- **B.** The orange band stays visible throughout, and only the modified
  model has no band.

>A. I wish to try B. Keep the orignial bands

**BF-Q6: Line styles in the right panel.** The fit keeps the
`bokeh_argo_pace` colours (`a_nw` black, `a_dg` brown, `a_ph` green,
`b_bp` purple dashed on the right axis).
- **A (recommended).** The modified curves use the same colours,
  **dotted**, with `b_bp` **dot-dash** so it stays distinct from its
  dashed fit line. The legend has "fit" and "modified" entries, and
  click-to-hide works as it does now.
- **B.** All modified curves in blue (matching the left panel), told apart
  by dash pattern only.

>A. Use your recommended approach.

**BF-Q7: Is anything besides the six parameters editable?** The forward
model also depends on settings that were fixed in the fit: Raman on/off,
Chl-fl on/off, `phi_c`, and the geometry (0, 0, 0 for 2.1). It also
depends on the input `Chl`, which is used for the fluorescence.
- **A (recommended).** **Only the six fitted parameters** for now. The fixed
  settings are shown read-only in a small "forward model" line. Toggles for
  Raman, Chl-fl and `phi_c` would be a cheap follow-up, but changing them
  rebuilds the models (~seconds).
- **B.** Expose those settings now as well.

>A. Only the six parameters for now, recommendation A

**BF-Q8: Launch and how it relates to `pab-viz`.** The prompt asks for a
command-line call with `wmo` and `cycle` as required arguments.
- **A (recommended).** A **standalone server**:
  `python -m pab.viz.bing_fit --wmo 1901614 --cycle 24 [--db …] [--version …] [--port 5007] [--show]`.
  It reuses `__main__`'s DB, data-dir, localhost and `--allow-remote`
  handling, which I would factor into shared helpers. The view itself is a
  class (`BingFitView`) with a server-free `make_bing_fit(...)`, so it can
  later become a `pab-viz` tab, e.g. an "Edit fit" button on the Argo+PACE
  tab. There is no Argo fetch and no network.
- **B.** Only a new tab in `pab-viz`, with `--wmo/--cycle` passed through.

>A. It should be a standalone server; use recommendation A

**BF-Q9: How much to reuse from `bokeh_argo_pace.py`?**
- **A (recommended).** Lift the PACE-panel and IOP-panel builders out of
  `ArgoPaceView.__init__` into module-level functions that both views call,
  with no visual change to Argo+PACE (its tests must still pass). Add a
  small `fits.ForwardModel` that builds the models once per fit
  (`fit_fig`'s `_config_from_row` / `_geometry_from_row` + `build_models`)
  and exposes `evaluate(params) → (Rrs, {anw, adg, aph, bbp})`.
  `reconstruct_rrs` stays the only forward-model dispatch.
- **B.** Copy the glyph code into the new module and leave
  `bokeh_argo_pace.py` untouched.

>A. Use your recommended approach.

**BF-Q10: Keeping a modified parameter set.** The tools are read-only.
- **A (recommended).** No file writes. A "parameters" box shows the current
  vector (fit space and physical units) as copyable text, and Bokeh's
  `save` tool exports a PNG.
- **B.** An `--out-dir` option and a button that writes the parameters
  (JSON) plus the figure (HTML/PNG) there.

>A. Use A

**BF-Q11: Which fit, for which (wmo, cycle)?** I would use the same rule as
Argo+PACE (`data.matchup_for` + `data.bing_fit`): the first matchup and the
best-ranked pixel of the newest family, with `--version` to pick another
family. If a profile has several matchups, a `--matchup-id` override would
choose one. Recommended as stated; tell me if you want something else.

**Your answers:**

>A. Use your recommendation

#### Round 1 decisions

| Q | Decision |
|---|---|
| BF-Q1 | Start from the **posterior median of each parameter**. The blue curve is drawn there at load, and the header shows χ² for both curves. |
| BF-Q2 | Controls work in **fit space** (log10 `Adg`/`Aph`/`Bnw`; linear `Sdg`/`beta`/`Bp`), with the physical value shown next to each. |
| BF-Q3 | Each slider spans the **posterior 5–95 % widened ×3** (at least ±0.5 dex for log parameters), clipped to the prior. A number box accepts any value inside the prior and widens the slider when needed. |
| BF-Q4 | **Live** update on slider release / Enter, in the thread pool with a stale-result token. |
| BF-Q5 | After the first edit the orange band and the IOP bands are **hidden**; the orange median stays. "Reset to fit" restores the bands, and a checkbox shows them on demand. |
| BF-Q6 | Modified IOPs use the fit's colours, **dotted**, with `b_bp` **dot-dash**. |
| BF-Q7 | **Only the six fitted parameters** are editable. Fixed forward-model settings are shown read-only. |
| BF-Q8 | A standalone server, `python -m pab.viz.bing_fit --wmo … --cycle …`, built on a server-free `make_bing_fit(...)` so it can become a `pab-viz` tab later. |
| BF-Q9 | Move the PACE and IOP panel builders out of `ArgoPaceView` into shared functions, with no visual change, and add a `fits.ForwardModel`. |
| BF-Q10 | No file writes. A copyable parameter box, plus Bokeh's PNG `save` tool. |
| BF-Q11 | Fit selection: `data.matchup_for` + `data.bing_fit` (newest family, best-ranked pixel), with `--version` and `--matchup-id` overrides. |

#### Round 2 (2026-11-23)

*What I verified after your answers, then six follow-ups. Recommendations
are marked.*

**Checks behind round 1:**
- **BF-Q1 has a built-in self-check.** The stored `fits.chisq` is the reduced
  χ² **at the posterior-median parameters** (`run._fit_diagnostics`: drop
  `analysis_burn` = 7,000 of the 10,000 steps, take the median per
  parameter, k = 6 including `B_p`, dof = n − k). I recomputed it for 3
  random 2.1 fits, and it matched the stored value to ~1e-6 relative. The
  blue start curve is exactly the model that χ² was computed on. Its χ² must
  equal `fits.chisq`, and the header will show a warning if it does not
  (e.g. if the wrong geometry or config was rebuilt). This also becomes a
  test.
- **The `B_p` prior** is uniform, linear, **[0.004, 0.05]**
  (`bing.rt.defs.BP_PRIOR_PMIN/PMAX`). This fills the gap in the round-1
  table. The "floor pile-up" in the 2.1 headline is fits at 0.004.
- **The posterior** behind the medians and bands is the last 3,000 steps × 16
  walkers (thinned), not 9,000, because `analysis_burn` = 7,000. I will use
  the same `thin_burn_chains` call, so the slider ranges (BF-Q3) and the
  table match the stored `value_lo/hi`.
- **`Chl` is not a parameter.** The NPZ's `Chl` (the Argo ML `chla`, e.g.
  0.49 mg m⁻³) only **seeds the Bricaud `a_ph` spectral shape** and the
  fluorescence. The retrieved Chl is `run.chl_from_aph(Aph)` =
  `10**Aph / a*_ph(440)`. So changing `Aph` changes the retrieved Chl but
  **not** the `a_ph` shape. Per BF-Q7 the seed is shown read-only in the
  forward-model line ("`a_ph` shape seeded by Chl = 0.49 (Argo)").

**BF-Q12: A table of derived quantities, fit vs modified?** The sliders show
the six parameters. The numbers people compare against Argo are derived from
them.
- **A (recommended).** A table under the controls with three columns:
  **fit median [5–95 %]**, **modified**, and **Argo (ML)**. Rows:
  `b_bp(700)`, `b_bp(440)`, `β`, `a_nw(440)`, `a_dg(440)`, `S_dg`, Chl
  (from `Aph`), `B_p`, χ²_red. The "modified" column is recomputed on each
  update. The Argo column is filled from `mld_summary` (`bbp700` ± std,
  `chla`), with no network. Rows, labels and formatting are shared with
  `ArgoPaceView.show_table`.
- **B.** No table; parameter rows only.

>A. Ok, that is fine.  But note that Argo is secondary in this tool.

**BF-Q13: An Argo reference on the IOP panel?** Comparing `b_bp(700)` with
the float is the most likely reason to adjust a fit.
- **A (recommended).** Mark the Argo ML `bbp700` ± std at 700 nm on the
  `b_bp` (right) axis: a blue marker with an error bar, toggled from the
  legend, read from `mld_summary`, with no fetch. NASA-GIOP `b_bp(700)` gets
  the same treatment as an off-by-default toggle, as on Argo+PACE.
- **B.** No reference marks.

>A. This is a good suggestion.  Do so.

**BF-Q14: Emulator out-of-domain warnings.** `robust_hybrid` emits a
`DomainWarning` naming each input outside its training range (e.g. `B_p`,
the `b_b/(a+b_b)` ratio). None fired at the median parameters of the fits I
tried, but a large edit can push the model off-domain. There the emulator is
unreliable, so the blue curve could mislead.
- **A (recommended).** Capture the warning on each evaluation
  (`warnings.catch_warnings(record=True)`, which also covers the
  `PYTHONWARNINGS` rule) and show an **amber note under the plots** naming
  each feature and the fraction of values out of range. The note clears when
  the model is back in range. The curve is still drawn.
- **B.** Suppress the warnings, as `fits.reconstruct` does.

>A. Use your recommended approach.

**BF-Q15: In-page choice of fit.** The CLI fixes `wmo`/`cycle` (and
optionally `--version` / `--matchup-id`).
- **A (recommended).** The page shows **one fit**, with no selectors. To
  look at another profile you restart the tool or change the URL
  (`?wmo=…&cycle=…`, as `pab-viz` supports). The `pab-viz` tab (BF-Q8)
  can add selectors later.
- **B.** Add the `pab-viz` version / WMO / cycle selectors now.

>A. Agreed, I will restart the tool.

**BF-Q16: Several parameters moving together.** The posterior has strong
correlations (`Adg`–`Sdg`, `Bnw`–`beta`–`B_p`). If one is moved alone, the
others no longer fit, which is often the point of the tool but can also
mislead.
- **A (recommended).** Nothing automatic for now; each slider moves only its
  own parameter. Two buttons help: "Reset to fit" (all parameters) and a
  small "↺" per row (one parameter). A "re-fit the others with this one
  held" step (a short LM) would be a natural later feature. It would
  write nothing, but adds ~seconds per click.
- **B.** Add the held-parameter LM re-fit now.

>A. Agreed, nothing automatic for now.

**BF-Q17: Defaults and environment.** The default port is **5007** (so it can
run beside `pab-viz` on 5006), the server binds to localhost only, and
`--show` opens a browser. The laptop needs the same as `pab-viz`: the fit's
`_v<ver>.npz` under `<data-dir>/fit_chains/`, plus `bing`, `robust` and
`jax`. The tool reports a missing chain file at start-up and exits non-zero,
because it cannot do anything without one. Agree?

>A. I agree

**Build plan once these are answered** (for reference, not a question):
1. Refactor `bokeh_argo_pace.py` into panel builders, with the existing
   Argo+PACE tests unchanged and green.
2. Add `fits.ForwardModel` (build once; `evaluate(params)`; `chisq`;
   recorded domain warnings) plus tests. The tests run on a real 2.1 fit
   when chains are present, else they are skipped; the χ² self-check
   reproduces `fits.chisq`.
3. Add `pab/viz/bing_fit.py` (`BingFitView`, `make_bing_fit`, and the
   server `main`, reusing `__main__`'s argument handling) plus tests
   `pab/tests/test_viz_bing_fit.py`: glyphs/sources present, bands hidden
   after an edit, reset restores them. Run `ruff`.
4. A manual run on a good fit and a bad fit (`7902116_30`, `2902882_96`
   from the AWOC2026 figures).

**Your answers:**

>A. See above

## Logs

### 2026-11-23 (Design prompt 1: BING-fit editor design posed as BF-Q1 to BF-Q11; no code)

Read `pab/viz/bokeh_argo_pace.py` (the PACE panel to mimic: linear/log
toggle, obs ± σ, orange median + 5–95 % band, residual strip in σ; and the
IOP panel: `a_nw`/`a_dg`/`a_ph` on the left axis, `b_bp` dashed on the right
axis), `pab/viz/fits.py` (`reconstruct` caches posterior bands but drops the
models), `pab/plotting/fit_fig.py` (`reconstruct_posterior`: the
model-building recipe) and `pab/viz/__main__.py` (the CLI and server
pattern).

What I learned:
- A single-vector forward call at a 2.1 fit's own geometry
  (robust_hybrid, Raman + Chl-fl, free `B_p`) costs **~0.08 s** once the
  models are built. Live editing is practical; building the models is the
  only slow step, and it happens once per fit.
- The chains hold `[Adg, Sdg, Aph, Bnw, beta, Bp]`, with `Adg`/`Aph`/`Bnw`
  in log10 and `Sdg`/`beta`/`Bp` linear. The 2.1 priors are: `Adg`/`Aph`
  log-uniform [−6, 1], `Bnw` [−6, −1] (the `bbp600 ≤ 0.1` ceiling), `Sdg`
  [0.01, 0.02], `beta` [0, 2]. Sliders cannot span these priors usefully,
  hence BF-Q3.
- The Rrs at the posterior-median parameters is not the posterior-median Rrs
  curve (BF-Q1). The tool should make this visible rather than hide it.
- `bokeh_argo_pace.py` builds its panels inline. Reusing them cleanly needs a
  small refactor into builder functions (BF-Q9).

Posed BF-Q1 to BF-Q11 (starting point, control space, slider ranges, update
trigger, band behaviour after an edit, right-panel line styles, extra
editable settings, launch, reuse, keeping results, fit selection) in
Q&A/Design. Waiting for answers before writing code.
### 2026-11-23 (Design prompt 2: round-1 answers (all "A") folded in; checks run; BF-Q12 to BF-Q17 posed; no code)

JXP accepted every round-1 recommendation. I added a decision table
(BF-Q1 to BF-Q11) to Q&A/Design.

Checks run (read-only, `ocean14`, `PAB_DATA_DIR=…/v2`):
- **The stored χ² reproduces.** `run._fit_diagnostics` (the reduced χ² at
  the posterior-median parameters, burn = `analysis_burn` = 7,000, k = 6,
  dof = n − k), rerun on 3 random 2.1 fits from their chains and rebuilt
  models, matches `fits.chisq` to ~1e-6 relative. The BF-Q1 blue start
  curve therefore has an exact self-check. No `DomainWarning` fired at the
  median parameters.
- The `B_p` prior is linear uniform [0.004, 0.05]
  (`bing.rt.defs.BP_PRIOR_PMIN/PMAX`).
- The posterior is the last 3,000 of 10,000 steps (`analysis_burn` = 7,000),
  not 9,000.
- The NPZ `Chl` is the **seed** of the Bricaud `a_ph` shape (and of the
  fluorescence), not a parameter. The retrieved Chl is
  `run.chl_from_aph(Aph)`. Editing `Aph` changes the retrieved Chl, not the
  `a_ph` shape.
- `robust.rt.hybrid.DomainWarning` messages list each out-of-range feature
  with its fraction and worst value, so they can be shown to the user
  (BF-Q14).

Posed BF-Q12 (a fit / modified / Argo table), BF-Q13 (Argo and GIOP
`b_bp(700)` marks on the IOP panel), BF-Q14 (show emulator domain warnings),
BF-Q15 (no in-page selectors), BF-Q16 (no coupled-parameter re-fit yet) and
BF-Q17 (port 5007, environment, missing chains = exit). I added a 4-step
build plan. No code written.

### 2026-11-23 (Implement prompt 1: BING-fit editor built, tested and run; BF-I1 to BF-I7 posed)

Round-2 answers were all "A" (with "Argo is secondary": the Argo column is
last and greyed, and the Argo mark is a single point at 700 nm). Built:
- **Refactor (BF-Q9).** `bokeh_argo_pace.py`'s Rrs / residual / IOP panels,
  autoranges, table and header became module-level builders. Its 18
  existing tests pass unchanged. A first refactor script failed safely: an
  end marker also matched an indented comment, so the slice was empty and
  nothing was written. The fix was to anchor the markers on line starts.
- **`fits.ForwardModel`.** Models are built once (~3 s); `evaluate` takes
  ~35 ms (the first call compiles, ~5 s). It reuses
  `run.reconstruct_rrs`, the `_fit_diagnostics` χ², and
  `run.extract_quantities` on a 2-step × 1-walker chain, so the modified
  quantities are computed by pipeline code.
- **`bing_fit.py`** (view, server-free builder, CLI/server on 5007) and
  **`server.py`** (launch helpers now shared with `pab-viz`).
- 12 new tests. The full suite passes: 575 passed, 1 skipped (the real-data
  test, when `PAB_DATA_DIR` is unset; it passes when set). `ruff` is clean.

Learned:
- The jitted robust forward model **never** raises `DomainWarning` (the
  check skips JAX tracers). `bing.evaluate.robust_domain_check` is the
  un-jitted complement, and it is what surfaces the warning.
- The hybrid emulator's trained `B_p` range is [0.01026, 0.018] against a
  prior of [0.004, 0.05]. **73 % of 2.1 fits (4,248 below, 7,435 above)**
  sit outside it at their posterior median. Hence the grey (fit itself) vs
  amber (new, from an edit) split of the domain notes (BF-I1).
- Not re-ranging on edits (Design) hid the edited curves, so I added an
  "auto-range on edit" checkbox, on by default (BF-I2).
- Visual check: headless Chrome screenshots of a static export (no
  selenium in `ocean14`) after a +0.3 dex `Bnw` edit on `7902116_30`. They
  showed the off-axis curves and a greyed IOP legend (the hidden bands were
  attached to the fit's legend items). Both are fixed and re-checked. A
  live `bokeh.client` session against the server built the full document.
- `db84de4` (JXP, mid-session) is a partial snapshot of this work (BF-I5).
- `pab/fit/models.py` describes `Adg` as an amplitude at 440 nm; BING's
  pivot is 400 nm (BF-I4, not changed).

### 2026-11-23 (Implement prompt 2: sliders replaced by number boxes + ±10 % buttons; fit bands kept; BF-I8, BF-I9 posed)

JXP revised the Design answers: BF-Q2 / BF-Q3 (no sliders; a number box and
±10 % of the current value), BF-Q4 (update on Enter or a ±10 % click), and
BF-Q5 = **B** (keep the original bands). BF-I7 was acknowledged; BF-I1 to
BF-I6 have no answers yet.

Changes in `pab/viz/bing_fit.py`:
- The `Slider` widgets and `slider_range` are gone. Each parameter row is now
  label / "−10 %" / number box / "+10 %" / ↺ / physical value.
  `step_value` scales the **physical** value by 1 ± `STEP_FRACTION` (0.1),
  which is ±log10(1 ± 0.1) dex for a log parameter, clipped to the prior.
  `step_param` adds a note when a step is refused at a bound.
- The fit's bands are always visible. The `show fit bands` checkbox,
  `_update_bands` and the IOP-legend band stripping are removed.
- Module docstring updated.

Tests: `test_viz_bing_fit.py` rewritten for the buttons (step arithmetic,
clipping, zero, bound note, bands kept through edits). 30 viz tests pass and
`ruff` is clean. A real-fit check (`7902116_30`) fired Bokeh `ButtonClick`
events on the buttons: three "+10 %" on `Bnw` gave ×1.331 exactly, "−10 %"
on `β` gave ×0.9, and ↺ restored the value. A headless-Chrome render
confirmed the layout and that the bands are kept.

Learned: "±10 % of the current value" is ambiguous for a parameter held as
log10. Stepping the log10 number itself would invert the direction for
negative logs and make the step depend on magnitude, so the step acts on the
physical value (BF-I8, open for JXP to confirm).

### 2026-11-23 (Round-1 Implement answers acted on: models.py comment fixed, `pab-bing-fit` console script added)

JXP answered BF-I1 to BF-I7. BF-I1 to BF-I3 and BF-I7 were accepted as built,
and BF-I5 (git) stays with JXP. Acted on:
- BF-I4: `pab/fit/models.py` had "`Adg`/`Aph` at 440 nm" twice (the
  `CEILING_FIELDS` comment and the `FitConfig` docstring). Both now give
  `Adg` at its 400 nm pivot and `Aph` at 440 nm. Comments only; `ruff`
  is clean.
- BF-I6: `pab-bing-fit` is in `setup.py` `console_scripts`. I reinstalled
  `ocean14` on the workstation (`pip install -e . --no-deps`, so nothing
  else changed), and `pab-bing-fit --help` runs. The laptop needs the same
  reinstall.
BF-I8 (±10 % acts on the physical value) and BF-I9 (step edge cases), from
Implement round 2, are still open.

### 2026-11-23 (Implement prompt 3: BF-I8 confirmed; BF-I9 = no clipping, any value accepted; BF-I10 posed)

JXP confirmed BF-I8 (±10 % scales the physical value), and for BF-I9 said
not to clip: the user can adopt any value. Changes in `pab/viz/bing_fit.py`:
- `step_value` no longer clips to the prior. `set_param` accepts any
  finite value, from the box or the buttons; only non-numbers and NaN/inf
  are refused.
- `_prior_notes` gives one note per parameter currently outside its prior.
  The notes are derived from the parameters, so they clear on their own.
- Evaluation is shared by the server and no-server paths (`_evaluate`). A
  failure becomes a transient note (`_error`) that the next success clears,
  and the plot keeps the last good curve. Before, the failure note stayed
  for the session, and the no-server path raised.
- A "Refused" note clears on any valid entry, even an unchanged one.

Tests: `test_viz_bing_fit.py` was updated (no clipping, inf refused) and
gained two tests (values outside the prior accepted with a note; a failed
evaluation gives a note that clears). 32 viz tests pass; `ruff` is clean.

Learned (real fit `7902116_30`): the forward model returns finite `Rrs`
for every out-of-prior value tried, including the impossible `B_p` = −0.01,
which scores χ² = 28 against 572 for the legal `B_p` = 0.002. Nothing
crashes, but non-physical inputs look valid on the plot. This is BF-I10,
recommending a stronger amber "non-physical" note rather than a refusal,
which keeps BF-I9.
