# Coding up PAB — Stage 6 (Metrics & figures)

## Goals

Implement **Stage 6** of the coding plan: the **metrics & figures** layer that
turns the per-matchup BING fits (Stage 5) into the comparison PAB exists to make
— **satellite `b_bp` vs. BGC-Argo `b_bp`** and the same for **Chl-a** — and the figures that make each
matchup and the population inspectable. This is the analysis payoff: the three
backscatter estimates (BING, NASA L2 IOP baseline, in-situ Argo) are compared in
log space, stratified, and visualized.

We continue to be guided by the design document `docs/design/PAB_design.md` and
the coding plan `docs/design/PAB_coding_plan.md`, and we record what we build in
`docs/design/PAB_implementation.md`.

## Claude

### Skills

Helpers for this stage (read their guidance; don't blindly copy):

- `plot-bing-fit` — the standardized three-panel `Rrs`/`a_nw`/`b_bnw` fit figure
  and corner plot built from a fit's chains; the **concept** for the per-matchup
  fit figure (PAB writes its own ~100 KB version, not BING's ~1 MB one).
- `diagnose-mcmc` — corner-plot inspection and convergence cues for the fit
  figure / quality fields.
- `batch-fit-argo` — the batch/idempotent pattern, mirrored for figure
  generation over the matchup population.

### Working agreements (unchanged from Stages 0–5)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written; do **not** copy
  the one-off `bing/papers/biomass/Analysis` scripts (import/reuse their library
  functions, or follow BING's `bing.plotting` *concepts*, instead).

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md`, especially *Comparison & metrics* and
  *Figures & tables* (the three `b_bp` estimates; median ratio + IQR, Spearman ρ,
  log-space bias & RMS/MAD scatter, per-fit reduced χ²; the ~100 KB per-matchup
  fit figure and scene quick-look; population figures; stratify by region /
  season / `Rrs` spatial variability).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 6* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current state;
  update it at the close of this stage).
- **Distilled references** — `docs/context.md` §3 (Bisson: median sat/float `bbp`
  ratio 0.77–1.66; skill degrades where `Rrs` is spatially variable — hence the
  stratification) and §2 (why `b_bp` is the matchup observable).
- **Existing PAB seams this stage builds on:**
  - `pab.db` — read the per-matchup results: `fit_results` (the namespaced
    `BING_ExpBPow_bbp700` etc., via `Store.fit_results_wide()`), `fits` (reduced
    `chisq`/`aic`/`bic`/`accept_frac`, `chains_path`), `mld_summary` (the in-situ
    `bbp700`/`chla`), `matchups`/`matchup_pixels` (geometry + the granule).
  - `pab.fit.artifacts.load_chains` + `pab.fit.models.build_models` — reconstruct
    a fit's posterior for the per-matchup fit figure.
  - `pab.pace.cloud.open_granule` + `pab.pace.flags` + `pab.matchup` pixels — the
    scene quick-look (granule neighborhood, float marker, analyzed pixels, the
    `l2_flags` mask). Mockable via the `opener=` seam (no network in tests).
  - `pab.config` (`pab_version`, `DATA_DIR`) — provenance + where figures are
    written.
  - **NASA L2 IOP baseline (secondary)** — `ocpy.pace.io.load_iop_l2` yields
    `bbp_442`/`bbp_s`; carried under the `NASA_L2IOP_*` namespace. Treat its
    extraction as a thin, lazily-imported seam (like the cloud read); the metric
    functions themselves stay pure (operate on arrays the store provides).

## Prompts

1. Read this doc and the context files. Execute the 1st task in the "Stage 6" section below.
2. Read this doc.  Execute the 2nd task in the "Stage 6" section below.

3. Read this doc.  Execute the 1st task in the "Pull Request" section below.
4. Read this doc.  Execute the 3rd task in the "Stage 6" section below.
5. Read this doc.  Execute the 4th task in the "Stage 6" section below.
6. Read this doc.  Execute the 5th task in the "Stage 6" section below.

## Stage 6

### Tasks

1. Read this doc and the context files. Implement Stage 6 (below). If you have
   questions, write them in the Q&A section. If you have any requests, write them
   in the Requests section. Log your work in the Logs section.

2. We need to correct a misconception that you have about the `ExpBPow` model.  One of the free parameters is `Aph` and the model uses that to estimate `Chl`.  But `Chl` is **not** truly an input parameter.  We do input it to seed the model, and that is all.  If necessary modify the design docs to make this clear.  And modify your code for this Stage as well. Log your work.

3. I wish for the QA views of the PACE scenes to be more than a single channel.  I nice false-color image made from a few channels would be great.  Please modify the code to make this possible.  Also update the design docs as necessary. Log your work.

4. Your Logs state that you modified the 07_metrics notebook to render the RGB composite.  I just ran the Notebook and I don't see anything.  Please double check and update accordingly. Log your work.

5. Please add a false-color composites with real PACE data.  Add it to the 05_matchup_7902226_4.ipynb Notebook. Log your work.

### Q&A

**Q (Claude, 2026-06-22):** You added "and the same for Chl-a." Our `ExpBPow`
model takes `Chl` as an **input** (the Argo mixed-layer `chla`), so a "BING Chl"
would be circular. For the satellite Chl I defaulted to an **OC4 band ratio**
(`ocpy.chl.band_ratios.oc4`) computed on the matchup pixel `Rrs` — independent of
Argo. Is that the source you want, or would you prefer the **NASA L2 OC
`chlor_a`** product (a new ingest), or a BING `a_ph(440)`-derived Chl? The metric
layer is quantity-agnostic, so whichever you pick plugs straight in. — *JXP:*

**Corrected (Claude, 2026-06-22):** Per Task 2 — I had this wrong. `Chl` only
**seeds** the Bricaud `a_ph`; BING **retrieves** Chl from the fitted `Aph`
(`Chl = 10**Aph / 0.05582`). So the primary Chl comparison is now **BING `chl`
vs Argo `chla`** (parallel to `b_bp`): Stage 5 emits a `chl` quantity, and
`gather_matchups` surfaces `chl_bing`. The OC4 band-ratio Chl is kept as an
optional independent cross-check. Docs (design/fitting/metrics/impl) corrected.

### Requests

## Pull Request

1. I have executed a Pull Request on GitHub for Stage 6. Please review the Pull
   Request and post it to GitHub.

2. Make edits to the Repo to address the review comments. If you have any
   questions, write them in the Q&A section below. If you have any requests,
   write them in the Requests section below.

## Stage 6 — Metrics & figures

Here is some additional context.

### Scope

Compute the matchup comparison metrics and render the figures:

- **The three `b_bp` estimates per matchup** — **BING** (`BING_ExpBPow_bbp700`
  from `fit_results`), **in-situ Argo** (`mld_summary.bbp700`), and the
  **NASA L2 IOP** baseline (`bbp_442`/`bbp_s` → `NASA_L2IOP_bbp`, when
  available). Mind the **wavelength offset** (Argo `bbp(700)` vs the satellite
  band) noted by Bisson — document how it is handled (e.g. compare at 700 nm
  using the retrieved slope, or note the band difference).
- **Metrics** (pure functions on aligned arrays):
  - **Ratio** — `bbp_sat / bbp_float`, summarized by **median** + IQR.
  - **Rank correlation** — **Spearman** ρ.
  - **Log-space bias & scatter** — bias = mean of `log10(bbp_sat/bbp_float)`;
    scatter = RMS (and/or MAD) of that residual.
  - **Per-fit goodness of fit** — carry the reduced χ² from `fits` as a
    per-matchup quality field.
  - **BING vs. NASA L2 IOP** — the same statistics between the two satellite
    retrievals (separates algorithm differences from sat-vs-float differences).
  - **Stratification** — by region, season, and `Rrs` spatial variability.
- **Figures** (matplotlib, non-interactive/Agg; ~100 KB budget each):
  - **Per-matchup fit figure** — spectral fit + residuals (+ a compact corner),
    reconstructed from the fit's chains NPZ; PAB's own code informed by
    `bing.plotting`/`plot-bing-fit` *concepts*, sized down (lower DPI, optimized
    PNG, trimmed panels) vs the ~1 MB biomass figures.
  - **Per-matchup scene quick-look** — a granule-neighborhood `Rrs` (single-band)
    thumbnail with the **Argo location marked**, the **analyzed pixels
    highlighted**, and the `l2_flags` mask shown (flagged pixels greyed).
  - **Population figures** — satellite-vs-float `b_bp` log-log scatter (1:1 +
    median-ratio offset lines), BING-vs-NASA-L2-IOP comparison, a map, and metric
    distributions.

Keep the heavy/optional reads (`ocpy` for the NASA baseline; granule opens) a
**lazily-imported / mockable seam**, and keep the metric math in **pure functions
on arrays** so it unit-tests offline with known values.

### Deliverables

- `pab.metrics.compare` — the pure metric functions (ratio/median/IQR, Spearman,
  log bias & RMS/MAD), a per-matchup quality assembler, and a
  store→matchup-`bbp`-triples gatherer; stratification helpers.
- `pab.plotting.{fit_fig, scene, population}` — the three figure families.
- Update `pab/metrics/__init__.py` and `pab/plotting/__init__.py` to export the
  public API.
- **Persistence (decide & document):** the design says metrics are "written to
  the SQLite store for the reporting layer." If a small `metrics` table is
  warranted, **bump `pab.db.schema.SCHEMA_VERSION` and add a migration**;
  otherwise compute them on demand from `fit_results`/`mld_summary` at report
  time (Stage 7) and justify the choice.

### Tests (offline; `pytest`)

- **Metric known-values** — ratio/median/IQR, Spearman ρ, log-space bias & RMS/
  MAD on constructed arrays with hand-computed answers; NaN/empty handling.
- **Figure smoke** — fit + scene + population figures render to files **within
  the ~100 KB budget** (Agg backend; tmp paths); the **scene marks the correct
  float pixel** on a synthetic granule fixture (reuse the `pab.pace`/`pab.matchup`
  fixture pattern; inject the granule via `opener=`).
- **Gatherer** — the store→`bbp`-triples join returns the right rows/alignment on
  a seeded DB (matchup + fit_results + mld_summary).
- Continue the project convention: pure functions checked with known values;
  heavy/network seams mocked; matplotlib forced to Agg; no network/S3.

### Docs

- A **metrics & figures page** (`docs/metrics.rst`): the metric definitions
  (mirroring the design *Comparison & metrics*), the wavelength-offset handling,
  the figure families + size budget, and the stratification dimensions. Add it to
  the `index.rst` *Package* toctree and autodoc `pab.metrics.*` / `pab.plotting.*`.

### Notebook

- `docs/nb/07_metrics.ipynb` — a worked example on **synthetic** matchup results
  (offline): compute the metrics, render a fit figure, a scene quick-look, and a
  population scatter, and show the metric values. Built executed (offline-safe),
  rendered via `myst-nb`, added to the *Notebooks* toctree; optional `RUN_LIVE`
  section over real Stage-5 fits.

### Definition of done (the Stage 0–5 standard)

- `pytest` green (new Stage 6 tests included); `ruff check pab` and
  `ruff format --check pab` clean; `sphinx-build -W` succeeds.
- Google-style docstrings on every public function; provenance stamped where
  records are written.
- `docs/design/PAB_implementation.md` updated: flip Stage 6 to ✅ in the status
  table, add a Stage 6 section (modules/API, key decisions, tests, docs,
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

### 2026-06-23 (Stage 6 — validated the composite on real PACE data; shared-scale fix)

JXP pointed out a `~/.netrc` exists (my earlier "no Earthdata creds" was stale —
`earthaccess.login(strategy="netrc")` authenticates). So I actually ran the
composite on **real PACE data** for seed 7902226/5 and learned two things:

1. **Granule choice matters.** The closest-*in-time* granule (15:25 UTC, 51%
   cloud) doesn't cover the float — nearest *unflagged* pixel 81 km away → blank
   composite. The granule that covers the float is `…20250219T155847` (the one
   JR used): nearest unflagged pixel **0.41 km**, 10 valid pixels. The Stage 4
   matchup engine's spatial gate is what (correctly) rejects the bad one.
2. **Per-channel stretch made speckle.** On a near-uniform gyre crop the
   independent 2–98% per-channel stretch amplified retrieval noise into
   rainbow speckle and broke colour balance. Fixed `false_color_rgba` to scale
   all three channels by a **single shared brightness reference** (99th pct) +
   gamma — preserving the natural blue-dominant ocean colour. Re-rendered on the
   real granule: a clean deep-blue gyre scene with the float + 10 analyzed pixels
   correctly placed (verified by viewing the PNG).

Also fixed a **crop bug** in the notebook-05 cell: centering the crop on
`locate_float_pixel` (distance-nearest, can be a far/edge pixel) while remapping
the *unflagged* pixels produced negative indices → `IndexError`. The cell now
centers on the matchup-pixels' **centroid** and **clips** remapped indices to the
window (validated on real data).

- `pab/plotting/scene.py` — shared-scale `false_color_rgba` (removed the
  per-channel `_stretch`). `docs/nb/05_*` cell uses the robust crop.
- Docs updated (design v0.4.3, metrics.rst, impl v0.5.3, both notebook md cells)
  to say "shared brightness reference", not "per-channel percentile-stretched".
- Suite now **92 passed** (the two BING-data tests run + pass now that the Loisel
  aph-basis file is present this session; they `skip` when it's absent). `ruff` +
  `sphinx -W` clean.

Note: the real granule open took ~140–160 s (out-of-region HTTPS stream, not
in-region S3). The composite cell in notebook 05 is still committed without
outputs (it's part of the live RUN_LIVE-style flow); I validated it via a
standalone script rather than executing the whole notebook (its JR/PCA-NN cells
need their own data).

### 2026-06-23 (Stage 6 — false-color composite on real PACE data in notebook 05)

Task 5: added a **false-color RGB composite of the real matched PACE granule** to
`docs/nb/05_matchup_7902226_4.ipynb` (the live dig-in for float 7902226 / cycle
5). Inserted right after the existing granule-plot cell, reusing the already-open
`gds = cloud.open_granule(url)` and the matchup geometry:

- Crops the full OCI granule to a ~25×25-pixel window around the float's nearest
  pixel (`scene.locate_float_pixel`) — a full granule is far too large to
  composite whole — and **remaps the matchup-pixel indices into the crop**
  (`ix - x0`, `iy - y0`).
- Calls `pab.plotting.scene.scene_quicklook(sub, lat, lon, pixels=sub_pixels)`
  (default false-color, R/G/B ≈ 645/555/470 nm), float as a red star, analyzed
  pixels circled, flagged pixels greyed.

This is the **first use of the false-color composite on real PACE data** — until
now it had only been exercised on synthetic granules (a repo-wide grep found no
other real-PACE RGB example). I could **not execute it here** (no `~/.netrc` /
Earthdata Login), so the cell is committed without outputs, consistent with the
rest of notebook 05 (which is live end-to-end and excluded from the Sphinx
build). All code cells parse; `nbformat` validates; the notebook stays excluded
so `sphinx -W` is unaffected.

### 2026-06-23 (Stage 6 — fixed the blank RGB scene in the 07_metrics notebook)

Task 4: JXP ran `07_metrics.ipynb` and saw nothing for the scene. Root cause —
the notebook's synthetic granule was built with `np.tile`, i.e. **spatially
uniform**; my earlier RGB code *did* render (the committed cell had a PNG), but
a uniform scene + the old `Rrs/max` stretch makes every channel saturate to
**1.0 → pure white** (a blank-looking square). So my prior "renders RGB" log was
technically true but the image was effectively blank — my miss.

Two fixes:

- **`pab/plotting/scene.py`** — `_stretch` now uses a **low–high percentile
  window** (2–98%) per channel instead of `/max`. Ocean `Rrs` channels are all
  positive and similar in magnitude, so `/max` washes scenes out; the window
  restores contrast, and a genuinely flat channel maps to a neutral 0.5 (not
  white). (Verified: uniform → std 0; varying → std ≈ 0.29.)
- **`docs/nb/07_metrics.ipynb`** — rebuilt the scene cell with a **spatially
  varying** granule (N–S brightness gradient + E-ward greening + a flagged cloud
  edge), 7×7, so the composite shows real colour structure. The scene cell now
  emits a ~20 KB colour PNG (a blank white one is ~3–5 KB).

Verified **90 passed, 2 skipped**; `ruff` + `sphinx -W` clean. Lesson: a
figure-size/`has_png` check isn't enough — a uniform input can still "render"
blank; the demo data must have spatial contrast (and the stretch must use a
percentile window).

### 2026-06-23 (Stage 6 — false-color RGB scene quick-look)

Task 3: made the scene QA view a **false-color RGB composite** instead of a
single channel.

- `pab/plotting/scene.py` — added `false_color_rgba(ds, rgb_waves, mask_flags)`
  (Rrs at three wavelengths → R/G/B, each percentile-stretched + gamma; flagged
  pixels set to grey) and `RGB_WAVES = (645, 555, 470)`. `scene_quicklook` now
  defaults to `mode="rgb"` (drawn as a QuadMesh with per-cell `set_facecolor`, so
  the float/pixel overlay stays exact on the lat/lon mesh) and keeps a
  `mode="band"` single-band view with a colorbar.
- Tests: `test_false_color_rgba` (RGBA shape/normalisation + greyed flag) and an
  RGB+band figure-budget smoke. Suite **90 passed, 2 skipped**; `ruff` +
  `sphinx -W` clean.
- Docs: `PAB_design.md` *Figures & tables* (v0.4.2), `metrics.rst`, impl record
  §5d (v0.5.2), and the `07_metrics` notebook (scene cell now renders RGB).

What I learned: for an RGB image on the (curvilinear) swath lat/lon grid,
`pcolormesh(...).set_array(None)` + `set_facecolor(rgba)` keeps the exact mesh
geometry (so the float marker / pixel circles land correctly), where `imshow`
would have needed an approximate rectangular extent.

### 2026-06-23 (Stage 6 — reviewed PR #4 and posted the review to GitHub)

Reviewed PR **#4 "Stage 6"** (`stage-6` → `develop`, 20 files) and posted a
COMMENT review (https://github.com/ocean-colour/PAB/pull/4).

- **Due diligence:** `pytest` → 89 passed, 2 skipped (BING-data-dependent);
  `ruff` + `sphinx -W` clean.
- **Verdict:** solid; two scope notes. (1) **NASA L2 IOP baseline isn't
  implemented** — scope/schema mention BING-vs-NASA but nothing ingests
  `bbp_442`/`bbp_s`; the PR should mark it deferred (the metric layer is
  quantity-agnostic so it slots in later). (2) `gather_matchups` doesn't filter
  `fits` by `model_pair`, so a 2nd model pair / >1 fitted pixel would yield
  duplicate/NULL matchup rows — add `AND f.model_pair = ?` before the model
  library grows. Plus minor notes (deferred `Rrs`-variability strata; the
  hard-coded `0.05582` Bricaud constant).
- Posted via `gh pr review 4 --comment` as `profxj`; no merge/commit.

### 2026-06-22 (Stage 6 — corrected the Chl/Aph misconception)

Task 2: JXP corrected me — in `ExpBPow`, `Aph` is a free parameter and the model
**estimates Chl from it** (`Chl = 10**Aph / 0.05582`, `bing/models/anw.py`); the
input `Chl` only *seeds* the `a_ph` shape, it is not a fixed input. So BING
retrieves Chl, and the Chl comparison should be **BING Chl vs Argo chla**,
parallel to `b_bp` — not the OC4 workaround I'd defaulted to.

Changes (working tree):

- **Stage 5 `pab/fit`** — added `chl_from_aph()` + `BRICAUD_APH440`, and
  `extract_quantities` now emits a **`chl`** quantity (BING-retrieved) for the
  Bricaud family; reworded the `fit_spectrum`/`fit_matchup` docstrings
  (`Chl` *seeds*, not anchors/inputs). New pure test `test_chl_from_aph`.
- **Stage 6 `pab/metrics`** — `gather_matchups` now surfaces `chl_bing`
  (`BING_*_chl`); `compare(df, "chl_bing", "chla_argo")` is the Chl metric.
  `add_oc_chl` reframed as an **optional independent** OC4 cross-check (not the
  primary). Test asserts the `chl_bing` comparison.
- **Docs** — corrected `PAB_design.md` (Comparison & metrics: Chl is retrieved
  from `Aph`, seeded only; v0.4.1), `fitting.rst`, `metrics.rst`, and the impl
  record §5c/§5d (v0.5.1). The notebook `07_metrics` now shows a Chl scatter
  alongside `b_bp`.
- Verified: **89 passed, 2 skipped**; `ruff` + `sphinx -W` clean.

### 2026-06-22 (Stage 6 — implemented metrics & figures)

Implemented Stage 6: `pab.metrics.compare` + `pab.plotting.{fit_fig,scene,population}`.

What I built:

- **`metrics/compare.py`** — quantity-agnostic `log_comparison` (median ratio +
  IQR, Spearman ρ, log bias, RMS/MAD), `gather_matchups` (store → per-matchup
  frame), `compare`, `add_strata` (season/region), and `add_oc_chl` (satellite
  OC4 Chl via `ocpy.chl.band_ratios.oc4` on the matchup pixel Rrs).
- **`plotting/scene.py`** — `scene_quicklook`/`scene_from_store` (float marker +
  analyzed pixels + greyed `l2_flags`); pure, `locate_float_pixel` tested.
- **`plotting/population.py`** — `comparison_scatter` (log-log + 1:1 +
  median-ratio) and `matchup_map`.
- **`plotting/fit_fig.py`** — `fit_figure` reconstructing a fit from its chains
  NPZ + `build_models` (Rrs band + `b_bp(λ)` band).
- **Tests** (`test_metrics.py`, 9): metric known-values, gatherer/strata, OC Chl
  via injected granule, scene pixel-marking + figure budgets, population figures,
  and a `bing`-guarded fit-figure smoke. Suite **88 passed, 2 skipped**; `ruff` +
  `sphinx -W` clean.
- **Docs** `metrics.rst` + **notebook** `07_metrics.ipynb` (executed offline).
  Implementation record → Stage 6 ✅ (v0.5.0).

Key decisions / what I learned:

- **Chl source.** `ExpBPow` takes `Chl` as an *input* (the Argo value), so a
  "BING Chl" would be circular. I default the satellite Chl to an **OC4 band
  ratio** (`ocpy.chl.band_ratios.oc4`) on the matchup `Rrs` — independent of
  Argo. Raised a Q&A asking JXP to confirm vs NASA `chlor_a`. The metric layer is
  quantity-agnostic so the choice plugs in.
- **No schema change** — metrics are computed on demand from
  `fit_results`/`mld_summary` (cheap; aggregate presentation is Stage 7's job).
- **Wavelength offset** handled by comparing at 700 nm (BING reports `b_bp(700)`
  directly).
- The two `bing`-dependent tests (Stage 5 recovery + this fit-figure) skip when
  BING's external Loisel data file is absent (as in this env).
