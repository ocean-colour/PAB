# Coding up PAB — Stage 5 (BING fitting wrapper)

## Goals

Implement **Stage 5** of the coding plan: the **BING fitting wrapper** that
takes the matchup `Rrs` spectra produced in Stage 4 and retrieves inherent
optical properties (IOPs) — above all **`b_bp`** — with full posterior
uncertainties, writing the fits to the DB and their MCMC chains to disk. This is
the stage where PAB's satellite half becomes directly comparable to the
BGC-Argo `bbp700` from Stage 2.

We continue to be guided by the design document `docs/design/PAB_design.md` and
the coding plan `docs/design/PAB_coding_plan.md`, and we record what we build in
`docs/design/PAB_implementation.md`.

## Claude

### Skills

Several installed skills target exactly this stage — use them as helpers (read
their guidance; don't blindly copy):

- `run-bing-fit` — the canonical end-to-end single-spectrum MCMC fit (configure
  models, set priors, LM warm-start, run emcee, reconstruct IOPs).
- `satellite-band-prep` — interpolate hyperspectral `Rrs` to PACE band centers
  and build the `varRrs` noise vector.
- `debug-priors` / `diagnose-mcmc` — triage `-inf` log-probs / stuck chains and
  judge convergence (autocorrelation, acceptance fraction, boundary pile-ups).
- `plot-bing-fit` — standardized three-panel `Rrs`/`a_nw`/`b_bnw` + corner
  figures (useful for the notebook and Stage 6).
- `fit-l23-spectrum` — fit a Loisel 2023 synthetic spectrum and compare to truth
  (a ready-made known-answer test source).
- `batch-fit-argo` — parallel batch fits via `inference.fit_batch` with
  checkpointing (the batch/idempotent pattern).
- `add-anw-model` / `add-bbnw-model` / `inelastic-rrs` — only if extending the
  model library or adding Raman/fluorescence (out of scope for the first pass).

### Working agreements (unchanged from Stages 0–4)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written; do **not** copy
  the one-off `bing/papers/biomass/Analysis` scripts (import/reuse their library
  functions instead).

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md`, especially *Fitting / IOP retrieval*
  and *Storage and retrieval* (the namespaced `fit_results` columns).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 5* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current
  state; update it at the close of this stage).
- **Distilled references** — `docs/context.md` §2 (BING: the Gordon forward
  model, the `bb/a` degeneracy, the IOP model table, MCMC/LM inference, AIC/BIC,
  and the finding that **`b_bp` is the most robustly retrieved quantity** — the
  reason it is the matchup observable) and §5 (PACE noise model).
- **BING package** — `bing.models.{anw,bbnw}` (parameterization classes +
  `init_model`), `bing.rt.rrs.calc_Rrs` (Gordon forward model), `bing.fitting.{
  chisq_fit (LM), inference (MCMC `fit_one`/`fit_batch`)}`, `bing.priors`. The
  `papers/biomass/Analysis/py/fitting.py` two-stage `expb_pow` LM→MCMC is the
  closest template (reuse its library calls, don't copy the script).
- **Existing PAB seams this stage builds on:**
  - `pab.db` — the `fits` and `fit_results` tables already exist
    (`fits.fit_id` PK encodes matchup+pixel+model+version; FKs to `matchups`/
    `matchup_pixels`; config + provenance + `chains_path`/`figure_path`;
    `fit_results` is **long** — `(fit_id, quantity, value, value_lo, value_hi,
    unit)` — pivoted to the wide namespaced columns by
    `Store.fit_results_wide()`). Write through `Store.upsert*` (idempotent).
  - `pab.matchup` — `matchups` / `matchup_pixels` are the fit inputs: which
    granule + which pixels.
  - `pab.pace.extract.extract_spectrum` / `pab.pace.cloud.open_granule` —
    re-read the pixel `Rrs(λ)` / `Rrs_unc(λ)` at fit time (spectra are **not**
    stored in `matchup_pixels`); `pab.pace.extract.pace_noise_vector` supplies
    `varRrs` when `Rrs_unc` is absent.
  - `pab.config.package_versions()` — the environment snapshot for
    `fits.pkg_versions`.

## Prompts

1. Read this doc and the context files. Execute the 1st task in the "Stage 5" section below.

2. Read this doc.  Execute the 1st task in the "Pull Request" section below.
3. Read this doc.  Execute the 2nd task in the "Pull Request" section below.

## Stage 5

### Tasks

1. Read this doc and the context files. Implement Stage 5 (below). If you have
   questions, write them in the Q&A section. If you have any requests, write them
   in the Requests section. Log your work in the Logs section.

### Q&A


## Pull Request

1. I have executed a Pull Request on GitHub for Stage 5.  Please review the Pull Request and post it to GitHub.

2. Make edits to the Repo to address the review comments.  If you have any questions, write them in the Q&A section below.  If you have any requests, write them in the Requests section below.

### Requests

**Addressed the PR #3 review (Claude, 2026-06-22).** Working-tree edits (not
committed — git is yours to push):

- **Fixed — NaN `chla` guard.** Extracted `run.finite_or_none()` and used it in
  `fit_matchup` so a non-finite mixed-layer `chla` falls back to `None` (→ the
  `fit_spectrum` default) instead of NaN-poisoning `set_aph`. New unit test.
- **Fixed — self-contained recovery test.** `test_fit_spectrum_recovers_bbp` now
  `pytest.skip`s on `FileNotFoundError` when BING's external Loisel aph-basis
  file is absent (as in this session), so the suite is green wherever
  bing-without-data is installed.
- **Fixed — batch resilience.** `build_fits` wraps each matchup in try/except,
  recording failures under a new `"failed"` bucket instead of aborting; new
  unit test (opener raises → `failed`, nothing written).
- **Clarified** that `fits.success` reflects the LM warm-start only (inline
  comment).
- **No change (documented):** `prepare_spectrum`'s `(2% of Rrs)**2` fallback
  (vs `pace_noise_vector`) — deliberate to avoid an `ocpy` import in the core;
  `fitting.rst` already states the 2% floor, and matchup pixels always carry
  `Rrs_unc`.

Suite: **80 passed, 1 skipped** (the data-dependent recovery test); `ruff` +
`sphinx -W` clean. Implementation record updated (test count 7→9, verification
line).

## Stage 5 — BING fitting wrapper

Here is some additional context.

### Scope

For each matchup (Stage 4), fit the selected PACE `Rrs` spectrum/spectra with
BING and persist the retrieved IOPs + uncertainties:

- **Model pair** — start with the workhorse **`ExpBricaud` + `Pow`** (`a_nw` =
  exponential CDOM/detritus + Bricaud phytoplankton; `b_b,nw` = power law),
  written so a second pair (e.g. GIOP-style constrained `k=5`, or a simpler
  `Cst`+`Pow`) slots in without schema churn (namespaced by `model_pair`).
- **Priors** — the BING default priors for the pair (log-uniform / uniform /
  Gaussian / ratio); they double as hard bounds. Record the `prior_set` label.
- **Inference** — **LM (`chisq_fit`) warm-start → MCMC (`emcee`)**. PAB default
  MCMC settings `nsteps≈10000`, `nburn≈1000`, `nwalkers=16` (configurable;
  lighter than BING's research default — document the choice). Likelihood is
  Gaussian in `Rrs` with `varRrs` from `Rrs_unc` (fallback: `pace_noise_vector`).
- **Band prep** — fit on the PACE band grid over a configured window (e.g.
  `wave_min`/`wave_max` ≈ 400–700 nm); interpolate/screen via
  `satellite-band-prep` conventions.
- **Outputs** — extract scalar IOPs as **posterior median + 5th/95th
  percentiles** into the long `fit_results` table under namespaced quantities
  (e.g. `BING_ExpBPow_bbp`, `…_bbp700`, `…_beta`/slope, `…_adg440`, `…_aph440`,
  `…_Sdg`, `…_Chl`). The **primary matchup observable is `b_bp` at 700 nm**
  (BGC-Argo's `BBP700`) — make sure it is retrieved/derivable for the Stage 6
  comparison. Record fit diagnostics on the `fits` row (`chisq`, `aic`, `bic`,
  `accept_frac`, `success`, `wave_min/max`).
- **Artifacts** — write the MCMC chains to an **NPZ on disk** under
  `PAB_DATA_DIR`, keyed by `fit_id`; store the path in `fits.chains_path` (chains
  are **not** in the DB). Stamp provenance: `pab_version`, `created`, and
  `pkg_versions` (JSON of `pab.config.package_versions()`).
- **Deterministic `fit_id`** — encode matchup + pixel + model + version (e.g.
  `"{matchup_id}_{ix}_{iy}_{model_pair}"`) so re-runs upsert idempotently.
- **Batch + idempotent + resumable** — fit many matchups (start with the nearest
  pixel per matchup; allow all ~10), skip/replace by `fit_id`; reuse BING
  `inference.fit_batch` where it helps.

Keep the heavy/optional dependency (`bing`) a **lazily-imported seam** so
`import pab.fit` works in the lean CI env, and keep the array-level science
(band prep, percentile extraction, `fit_id` construction) in **pure functions**
that unit-test offline.

### Deliverables

- `pab.fit.models` — configure the BING model pair + priors (the `ExpBricaud`
  +`Pow` setup; the seam for adding pairs).
- `pab.fit.run` — the LM→MCMC driver for one spectrum and the batch driver over
  matchups; percentile extraction into namespaced quantities.
- `pab.fit.artifacts` — NPZ chain read/write keyed by `fit_id`; provenance
  stamping; the `fits` + `fit_results` persistence helpers.
- Update `pab/fit/__init__.py` to export the public API.
- New rows in `fits` + `fit_results` via the DB layer (no schema change
  expected; if one is needed, bump `pab.db.schema.SCHEMA_VERSION` + add a
  migration).

### Tests (offline; `pytest`)

- **Known-answer recovery** — generate a synthetic `Rrs` from known IOPs with
  BING's own forward model (`calc_Rrs`), fit it (a **short** MCMC — tiny
  `nsteps`/`nwalkers` for speed), and check the retrieved `bbp`/slope within a
  tolerance. Guard the whole thing with `pytest.importorskip("bing")`.
- **Pure helpers** — `fit_id` construction; percentile→`(value, value_lo,
  value_hi)` extraction on a constructed chain array; band-prep interpolation on
  a known grid — all without `bing`.
- **Persistence + idempotency** — `fits` + `fit_results` rows written with
  correct FKs and namespaced quantities; provenance fields populated; the NPZ
  artifact written and its path stored; **idempotent re-run** produces no
  duplicates (and `fit_results_wide()` pivots as expected).
- Continue the project convention: pure functions checked with known values; the
  heavy `bing`/`emcee` path mocked or run at toy size; no network.

### Docs

- A **fitting page** (`docs/fitting.rst`): the LM→MCMC pipeline, the model-naming
  / namespaced-quantity schema (`BING_<model_pair>_<quantity>`), the MCMC
  settings and why, provenance + artifact layout, and how a fit links back to its
  matchup/pixel. Add it to the `index.rst` *Package* toctree and autodoc
  `pab.fit.*`.

### Notebook

- `docs/nb/06_fit.ipynb` — a worked example: build/obtain a spectrum, run the
  BING fit, show the posterior IOPs (`b_bp`, slope) with uncertainties and a
  fit/corner figure, and the written `fits`/`fit_results` rows. Offline-safe
  (synthetic spectrum, short MCMC, committed outputs); end with an optional
  `RUN_LIVE` section fitting a real Stage-4 matchup. Render via `myst-nb` and add
  to the *Notebooks* toctree.

### Definition of done (the Stage 0–4 standard)

- `pytest` green (new Stage 5 tests included); `ruff check pab` and
  `ruff format --check pab` clean; `sphinx-build -W` succeeds.
- Google-style docstrings on every public function; provenance stamped
  (`pab_version`, `created`, `pkg_versions`) on written records.
- `docs/design/PAB_implementation.md` updated: flip Stage 5 to ✅ in the status
  table, add a Stage 5 section (modules/API, key decisions, tests, docs,
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

### 2026-06-22 (Stage 5 — addressed PR #3 review comments)

Made working-tree edits addressing my PR #3 review (details in the Requests
section above):

- NaN-`chla` guard via a new `run.finite_or_none` helper used in `fit_matchup`.
- `test_fit_spectrum_recovers_bbp` now skips on `FileNotFoundError` when BING's
  Loisel aph-basis data file is missing (the env failure seen during the
  review).
- `build_fits` now records per-matchup failures under `"failed"` instead of
  aborting the batch.
- Clarified `success` = LM-warm-start-only; left the 2%-floor noise fallback as
  documented.
- Added two unit tests (`finite_or_none`, `build_fits` failed path). Suite **80
  passed, 1 skipped**; `ruff` + `sphinx -W` clean. Updated the implementation
  record (test count 7→9, verification line, run/fit notes).
- No commit/push (git is JXP's); the response diff lands on the PR once pushed.

### 2026-06-22 (Stage 5 — reviewed PR #3 and posted the review to GitHub)

Reviewed PR **#3 "Stage 5"** (`stage5` → `develop`, 11 files) and posted a
COMMENT review (https://github.com/ocean-colour/PAB/pull/3).

- **Due diligence:** `ruff` + `sphinx -W` clean; `pytest` → 78 passed, **1
  failure that is an environment data dependency, not a code defect** — BING's
  `ExpBricaud.set_aph` loads an external Loisel `Hydrolight400.nc` absent at its
  path this session (the same test passed last turn when the data was present).
- **Verdict:** solid; two should-fix items. (1) NaN `chla` poisons the fit —
  `summarize_profile` yields NaN (not None) when CHLA is missing, so it flows
  into `Chl` → `set_aph(NaN)`; guard for finite `chla` in `fit_matchup`.
  (2) Make `test_fit_spectrum_recovers_bbp` self-contained — skip on
  `FileNotFoundError` when the BING Loisel data file is unavailable. Plus minor
  notes (batch abort on one failure; `success` = LM-only; the 2%-floor vs
  `pace_noise_vector` doc mismatch).
- Posted via `gh pr review 3 --comment` as `profxj`; did not merge/commit (git
  is JXP's). These findings are the input to the next PR task (address review).

### 2026-06-21 (Stage 5 — implemented the BING fitting wrapper)

Implemented Stage 5: `pab.fit.{models,run,artifacts}`, fitting matchup `Rrs`
with BING (LM warm-start → emcee MCMC) and persisting IOPs + uncertainties.

What I built:

- **`models.py`** — `FitConfig` (frozen) + `build_models(config, wave)` wrapping
  `bing.parameters.standard.expb_pow` → `(p, rt_dict, models)` with standard
  priors. `BING_COMBO` maps the PAB label `ExpBPow` → the bing factory.
- **`run.py`** — pure helpers (`make_fit_id`, `prepare_spectrum`,
  `extract_quantities`) + `fit_spectrum` (band prep → LM → MCMC → posterior),
  and the matchup drivers `fit_matchup` / `build_fits` (re-read pixel `Rrs`,
  pass mixed-layer `chla` as `Chl`, idempotent by `fit_id`).
- **`artifacts.py`** — NPZ chains under `PAB_DATA_DIR/fit_chains/` + `persist_fit`
  (namespaced `BING_<model_pair>_<quantity>` rows; provenance incl.
  `pkg_versions`).
- **Tests** (`test_fit.py`, 7): pure helpers, persistence + idempotency, NPZ
  round-trip, and a known-answer `b_bp` recovery (`importorskip` bing/emcee,
  short MCMC). Suite **79 passed**; `ruff` + `sphinx -W` clean.
- **Docs** `fitting.rst` + **notebook** `06_fit.ipynb` (executed offline at toy
  MCMC size). Implementation record → Stage 5 ✅ (v0.4.0).

What I learned / decisions:

- **De-risked first.** Before writing PAB code I ran the canonical
  `run-bing-fit` pipeline on a synthetic PACE-band spectrum and confirmed the
  real API: `standard.expb_pow(..., variable_Gordon=False)`, `Chl` must be a
  numpy array for `set_aph`, `chisq_fit.fit → (ans, cov, idx)`,
  `fit_one(..., chains_only=...) → (sampler|chains, idx)`. Recovery of
  `b_bp(700)` was near-exact.
- **`b_bp` via `models[1].eval_bbnw`** (non-water) on the posterior bb-params —
  *not* `reconstruct_from_chains` (returns total a/bb and hard-burns 7000 steps).
  PAB controls the analysis burn (falls back to `nsteps//2`), which is what makes
  a toy-size MCMC testable.
- No schema change — the Stage 1 `fits`/`fit_results` tables already fit; long
  format keeps it stable as model pairs grow.

Open follow-ups for JXP (in the Q&A above): none blocking.
