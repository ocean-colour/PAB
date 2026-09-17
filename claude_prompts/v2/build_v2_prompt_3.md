# Build v2 — Prompt 3: the 2.0 fit (RoB emulator, Raman + Chl fluorescence, free B_p)

## Goals

Make PAB's `fit` stage run BING with `rt_backend='robust_hybrid'`,
`include_Raman=True`, `include_Chl_fl=True`, `include_CDOM_fl=False`,
`wave_max=720`, a **free `B_p`**, per-pixel geometry from Prompt 2, and full
provenance — and prove it end-to-end on real cached matchups against the
1.0 configuration (`run_full_inelastic.md` Plan §2, §3 a/b/d/e/g/k; Q4, R2,
R4).

## Claude

### Skills

- **`run-bing-fit`** (the per-spectrum fit; its *RT backend selection*
  section), **`inelastic-rrs`** (in the BING repo: `bing/.claude/skills/`),
  **`diagnose-mcmc`** / **`debug-priors`** if the 6-parameter fit misbehaves.

### Working agreements

As in `build_v2_prompt_1.md`; **`v1/pab.db` frozen**; all fitting in this
prompt goes to a **scratch copy** of `v2/pab.db` (the real `v2/pab.db`
receives fits only from the Nautilus run). `pab_version` becomes `"2.0"`
here — bump it first so every row this prompt writes is stamped correctly.

**Settled in Prompts 1–2 — no longer open:**

- **`ocean14` is the only env**; Python 3.14.6, full stack, `xarray` pinned
  2025.9.0 by argopy. Test baseline is **287 passed, 1 skipped**
  (the skip is the env-gated live L1B test; run it with `PAB_LIVE_L1B=1`).
- `v1/pab.db` frozen at sha256 `09de0a6d…f978273`, **schema v4**, `a-w`.
  Any read of it needs `Store.open(..., create=False)` — a default open now
  tries to migrate v4 → v5 and dies with
  `attempt to write a readonly database`.
- `v2/pab.db` is at **schema v5** already (see Context).
- `ruff check pab/` has **8 pre-existing errors** in
  `pab/argo/check_argo_coverage.py`. Not yours.

## Context

- Plan §2 and §3 (a, b, d, e, g, k) of `claude_prompts/v2/run_full_inelastic.md`.
- BING (`/mnt/tank/Oceanography/python/bing`, `bf56f6d`):
  `bing/rt/defs.py` (`rt_dict_from_p`, `validate_rt_dict`, `BP_PRIOR_PMIN/
  PMAX = 0.004/0.05`), `bing/rt/geometry.py` (`ObsGeometry`),
  `bing/fitting/inference.py` (`log_prob` peels `params[-1]` as `B_p` when
  `fit_Bp`; `init_mcmc` → `ndim = 6`, walkers `max(16, 2·ndim)` = 16;
  `fit_one` takes a 5-tuple `(Rrs, varRrs, p0, idx, geom)`),
  `bing/fitting/chisq_fit.py` (same 5-tuple; bounds must include `B_p`),
  `bing/evaluate.py` (`calc_Rrs_from_models_robust(..., geom=, Bp=)`),
  `docs/radiative_transfer.rst` (backend table, throughput: `robust_hybrid`
  5.7k vs `gordon` 38.9k `log_prob`/s).
- PAB: `pab/fit/models.py` (`FitConfig`, `build_models`), `pab/fit/run.py`
  (`_initial_guess`, `_prior_bounds`, `_is_log_param`, `extract_quantities`
  — **splits the chain by `nparam_a` and must peel the trailing `B_p`
  first**, `_fit_diagnostics` and `pab/plotting/fit_fig.py` — **both call
  the Gordon `calc_Rrs_from_models` directly**), `pab/fit/artifacts.py`
  (`persist_fit`, `make_fit_id`), `pab/config.py` (`pab_version`,
  `package_versions`), `pab/parallel.py` (`init_worker`).
- `robust` (`/mnt/tank/Oceanography/python/retrieve-or-bust`, `dfab27c`).

### What Prompts 1–2 already delivered (2026-09-15)

- **Schema v5 is done — including this prompt's `fits` columns.** Prompt 2
  Task 1 carried *both* halves of v5 in one `_v4_to_v5` migration, because a
  migration step only runs on a database still at its starting version: once
  `v2/pab.db` was stamped `user_version = 5`, a later edit to `_v4_to_v5`
  would never have been applied to it. So `fits` **already has**
  `rt_backend` TEXT, `include_raman` / `include_chl_fl` / `include_cdom_fl` /
  `fit_bp` INTEGER (0/1), `phi_c` REAL — all NULL on the 14,609 legacy rows —
  and `wave_max` was confirmed to pre-exist. **Task 3 has no migration to
  write**; it wires `FitConfig` → `persist_fit` into columns that exist.
  (Recorded as Q1 in `build_v2_prompt_2.md`; the escape hatch if you want it
  undone is a `_v5_to_v6`, not an edit.)
- **`matchup_pixels` carries the geometry**: `theta_s`, `theta_v`, `dphi`
  (REAL, **degrees**) and `geom_source` TEXT (`'L1B_V3'`). `dphi` is
  `sensor_azimuth − solar_azimuth` **wrapped to (−180, 180]** —
  `pab.pace.l1b.wrap_dphi` is the canonical implementation; do not re-derive
  it, the reflex `((x+180) % 360) − 180` gives the wrong half-open end.
- **New modules to reuse, not re-invent:** `pab/pace/l1b.py`
  (`l1b_source_for_aop`, `read_geolocation`, `open_l1b_geolocation`,
  `pixel_geometry`, `wrap_dphi`, `GridMismatchError`, `GEOM_SOURCE`) and
  `pab/matchup/geometry.py` (`build_geometry`, `pixels_needing_geometry`,
  `geometry_for_granule`).
- **`geometry` is now a pipeline stage between `match` and `fit`**:
  `ingest → discover → match → geometry → fit → figure → report`.
  `--stage geometry` works; `STAGES` is at `pab/pipeline.py:35`.
- **Measured geometry ranges** on 200 real pixels (Prompt 2 Task 4), useful
  as `ObsGeometry` sanity bounds: `theta_s` 16.1–42.8°, `theta_v`
  22.1–59.7°, `dphi` −103.9–81.9°.

### Three things that will bite this prompt

1. **The real `v2/pab.db` has *no* geometry yet — 0 of 146,100 pixels.**
   Prompt 2 Task 4 validated the stage on a *pruned scratch copy*, which was
   then deleted. So Task 5's scratch copy starts with `theta_s IS NULL`
   everywhere and you must run **`--stage geometry` on it first**, or every
   fit will be skipped by Task 2's "no geometry → `failed`" rule. Budget
   ~9 s/granule serial (see the timings in `build_v2_prompt_2.md`).
2. **`package_versions()["pab"]` reads the *installed distribution* version,
   not `pab.config.pab_version`.** Bumping `setup.py` to `'2.0'` does nothing
   until `pip install -e . --no-deps` is re-run — until then every 2.0 fit's
   `pkg_versions` JSON records `pab: 1.1`. Verified: `config.pab_version`,
   the dist version and `setup.py` are three separate strings that currently
   all happen to read `1.1`. Bump all of them, then reinstall, then check
   `package_versions()`.
3. **Chains do not land in `v2/fit_chains/` unless you point `PAB_DATA_DIR`
   there.** `pab.fit.artifacts.chains_path()` is
   `Path(DATA_DIR) / "fit_chains" / f"{fit_id}.npz"` — the *root* of
   `PAB_DATA_DIR`. With the shell default (`…/Color/PAB`) chains go to
   `…/Color/PAB/fit_chains/`, mixed in with v1's and with whatever the test
   suite leaves there, whatever `--db` says. Set
   `PAB_DATA_DIR=…/Color/PAB/v2` for a run that writes chains.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below
6. Execute the 6th task in Tasks below
7. Execute the 7th task in Tasks below

## Tasks

1. **Config + version.** `pab_version` → `"2.0"` (`pab/config.py`,
   `setup.py`) — then **`pip install -e . --no-deps` again** and confirm
   `package_versions()["pab"] == "2.0"`; it reads the installed dist
   metadata, not `config.pab_version`, so without the reinstall every 2.0
   fit's provenance JSON silently records `pab: 1.1` (Context, bite #2). `FitConfig` gains `rt_backend="robust_hybrid"`,
   `include_Chl_fl=True`, `include_CDOM_fl=False`, `phi_C=0.02`,
   `fit_Bp=True`, `Bp_value=0.01`; `include_Raman` default → `True`;
   `wave_max` default → `720.0`. Keep a documented **`FitConfig.v1()`**
   classmethod (Gordon, elastic, 700 nm, `fit_Bp=False`) so the 1.0
   configuration stays reproducible for comparisons. `build_models` forwards
   the new fields to `standard.expb_pow`; `validate_rt_dict` runs at setup.
   Tests. Log.

2. **Free `B_p` + geometry plumbing** (`pab/fit/run.py`). `fit_spectrum`
   takes `geom: ObsGeometry | None` and, when `fit_Bp`, appends `B_p` to the
   initial guess (`Bp_value`), bounds (`[0.004, 0.05]`, **linear**), and
   names (`"Bp"`); passes the 5-tuple to `chisq_fit.fit` and `fit_one`.
   `extract_quantities` peels `flat[:, -1]` as `B_p` before the `a`/`bb`
   split, emits `Bp` (median + 5–95 %, unit `""`), and passes `Bp` medians
   where the robust forward model needs them. `_gather_fit_input` reads
   `theta_s`/`theta_v`/`dphi` from `matchup_pixels` (they exist — schema v5,
   degrees, `dphi` already wrapped to (−180, 180] by the `geometry` stage, so
   **do not re-wrap**); a pixel **without geometry is skipped and recorded
   under `"failed"` with a clear reason** (R3 — never a computed fallback).
   Test that path explicitly: on a store with geometry filled it must fit, on
   one without it must record every pixel as failed and open nothing. Tests with a toy robust fit
   (`importorskip("robust")`): chain has 6 columns, `Bp` inside its prior,
   `bbp700` recovered on a synthetic spectrum generated by the same backend.
   Log.

3. **Improve RoB.** Please read my answers to Q1.  Then proceed to do the training needed for RoB.  Use Fable if you can.  Log your work.

4. **Provenance + identity.** **The schema half is already done** —
   Prompt 2 Task 1's `_v4_to_v5` added `fits.rt_backend`, `include_raman`,
   `include_chl_fl`, `include_cdom_fl`, `phi_c`, `fit_bp` (NULL on the 14,609
   legacy rows) and confirmed `wave_max` pre-existed. `v2/pab.db` is already
   at `user_version = 5`. **Write no migration**; if a column is genuinely
   missing it needs a `_v5_to_v6`, not an edit to `_v4_to_v5` (that step will
   never re-run on an already-stamped file). What is left here:
   `make_fit_id` →
   `{matchup_id}_{ix}_{iy}_{model_pair}_v{pab_version}` (a test pins that
   the 1.0 format is *not* produced for 2.0). `package_versions()` adds
   `robust` and a `git_sha` map for `PAB`, `bing`, `ocpy`, `remote_sensing`,
   `retrieve-or-bust` (read via `git rev-parse` at import time with a
   `"unknown"` fallback so the container, which has no `.git`, can be fed
   the SHAs through an env var/label instead — design the seam).
   `persist_fit` writes the new columns. Tests. Log.

5. **Fitted-physics everywhere.** `_fit_diagnostics` (χ²/AIC/BIC) and
   `pab/plotting/fit_fig.py` dispatch on `rt_backend`: robust →
   `calc_Rrs_from_models_robust(..., geom=, Bp=)` with the geometry read
   back from the DB; Gordon → unchanged. `pab.parallel.init_worker` pins
   XLA's CPU threads (`XLA_FLAGS=--xla_cpu_multi_thread_eigen=false
   intra_op_parallelism_threads=1`) next to the BLAS caps. Tests (the fit
   figure for a robust fit uses the robust reconstruction — assert via a
   mocked `calc_Rrs_from_models_robust`). Log.

6. **Real end-to-end check (workstation).** On a **scratch copy** of
   `v2/pab.db` (make it with `pab.db.split_version.copy_database`), **first
   run `--stage geometry`** — the real `v2/pab.db` has geometry on *none* of
   its 146,100 pixels, so a fresh copy has none either (Context, bite #1).
   The validated local set is the **10 pilot `V3_2` granules → 20 matchups /
   200 pixels**, not 3 — all 200 filled cleanly in Prompt 2 Task 4 at
   ~9 s/granule serial (~90 s for the ten), so bound the copy to those
   matchups first (prune it; the CLI still has no `--matchup` filter).
   Fitting all 200 pixels may be more than you want — say which subset you
   used. Then fit under **`FitConfig()` (2.0)** and
   **`FitConfig.v1()`**, serially and with `--jobs 2` (spawned workers →
   JAX JIT in a worker is exercised). Report per matchup: s/fit for each
   config, `bbp700`, `Bp`, `chl`, χ², acceptance; the 2.0/1.0 `bbp700`
   ratio; and the `Rrs_unc(719)/Rrs(719)` value (R4 red-edge check). Confirm
   the persisted rows carry `pab_version="2.0"`, the v5 columns, the
   version-aware `fit_id`, chains under `$PAB_DATA_DIR/v2/fit_chains/`
   — which requires **`PAB_DATA_DIR=…/Color/PAB/v2` for the run**, since
   `chains_path()` keys off the root of `PAB_DATA_DIR`, not the `--db` path
   (Context, bite #3) — and that the v1 DB sha is still
   `09de0a6d…f978273`. Write it up under
   **Reports**; update `docs/fitting.rst` and `HOWTO.md` (the 2.0 defaults,
   `FitConfig.v1()`). Log.

7. **Update.** Based on what you have done, update the prompt doc
   `build_v2_prompt_4.md`, as needed. Log.
   *(Added 2026-09-15, mirroring the Task 5 JXP added to
   `build_v2_prompt_1.md`, so each prompt hands its findings to the next.
   Delete it if that is not the intent.)*

## Q&A

### Q1 (Task 2, 2026-09-15) — `robust_hybrid`'s emulator is **out of its training domain on every real pixel** — confirm the backend choice

Not a blocker for the code, which runs; a question about whether
`rt_backend='robust_hybrid'` (Plan Q4/R2) is the right choice for **this**
dataset. `robust` itself raises a `DomainWarning` on every forward call and
suggests `mode='ztt'`.

The emulator's training domain (`robust.rt.emulator.load_default().domain`)
versus the geometry actually measured on 200 real matchup pixels in
Prompt 2 Task 4:

| axis | trained | our data | |
|---|---|---|---|
| `cos_theta_s` | [0.5, 1] → 0–60° | 16.1–42.8° | **inside** |
| `cos_theta_v` | **[1, 1]** → nadir only | 22.1–59.7° | **OUTSIDE, all pixels** |
| `cos_dphi` | **[1, 1]** → 0° only | −103.9–81.9° | **OUTSIDE, all pixels** |
| `B_p` | [0.01026, 0.01800] | prior [0.004, 0.05] | only **17 %** of the prior is inside |
| wavelength | [350, 750] nm | 400–720 nm | inside |

So the **learned correction that distinguishes `robust_hybrid` from
`robust_ztt` is being extrapolated on 100 % of pixels**, on two axes it never
saw vary, and over a `B_p` range it mostly never saw. `robust`'s own wording:
*"the emulator is being evaluated outside its training range, where M3
measured its accuracy to be unreliable and occasionally worse than the
analytic backbone … Consider mode='ztt'."*

**Options:**

1. **Switch to `rt_backend='robust_ztt'`** — the analytic ZTT forward model
   with no emulator, so no training domain to leave. Loses the learned
   correction, which was the point of `hybrid`, but the correction is not
   valid here anyway. One-line change to `FitConfig`.
2. **Keep `robust_hybrid`** and accept documented extrapolation — defensible
   only if someone has checked the emulator degrades gracefully off-nadir.
   Nothing in `robust`'s docs suggests that has been measured.
3. **Fit both** on the 20-matchup local set (Task 5) and compare `bbp700`
   before committing the 11,494-granule run.

*My recommendation: option 3 now — Task 5 already fits two configurations, so
adding a third arm is cheap — then most likely option 1 for the full run.*
Task 5 is the right place to settle it, but the plan's §2 and the `FitConfig`
default may need changing, which is why it is raised here rather than there.

**Awaiting JXP.** The code is backend-agnostic either way: `rt_backend` is a
`FitConfig` field, so switching is one line plus a re-run.

>A. Yes, let's use option 3.  We will accept B_p lying outside its training range. I am adding a new task to the list.

### Q2 (Task 6, 2026-09-17) — `wave_max = 720` pulls in a band that is **negative or noise-dominated on 40 % of matchups** — confirm R4

The R4 red-edge check on all 20 local matchups, at the 719 nm band the 2.0
window newly includes:

| | count | |
|---|---:|---|
| `Rrs(719)` **negative** | **6 / 20** | −1.5e−4 … −3.2e−4 sr⁻¹ |
| `Rrs(719)` positive but `unc > signal` | 2 / 20 | ratios 1.95 and 3.85 |
| **unusable either way** | **8 / 20 = 40 %** | |
| usable | 12 / 20 | median `unc/Rrs` = **0.30** |

Even the *good* band carries ~30 % relative uncertainty — the best case here is
a noisy point, not a constraint.

**And it shows up in the fits.** Splitting the 20 matchups by red-edge quality:

| group | n | χ² 2.0 | χ² 1.0 | 2.0/1.0 |
|---|---:|---:|---:|---:|
| 719 nm usable | 12 | 0.48 | 0.39 | **1.24×** |
| 719 nm negative / noise-dominated | 8 | 1.12 | 0.61 | **1.84×** |

The four worst 2.0 χ² in the whole set — 2.38, 2.36, 2.05, 1.37 — are **exactly
the four matchups with the most negative `Rrs(719)`**. The 2.0 fit is being
asked to reproduce a negative reflectance, and the χ² degradation is
concentrated there rather than spread across the set.

**Options:**

1. **Keep `wave_max = 720`** and accept it. The inelastic terms (Chl
   fluorescence peaks ~685 nm) are the reason for going red, and a noisy band
   is still information when it is weighted by its variance — which
   `prepare_spectrum` does. But a *negative* `Rrs` is not noise around a small
   positive value the model can reach; the model is non-negative by
   construction, so those points can only ever contribute a floor of
   mismatch.
2. **Drop back to `wave_max = 700`** for 2.0. Keeps the inelastic physics
   (fluorescence peak is inside 700) and removes the pathological band.
   Loses the red shoulder the 720 window was chosen for.
3. **Keep 720 but screen the band per matchup** — drop non-positive `Rrs`
   points in `prepare_spectrum` (it already drops NaNs), so a matchup with a
   good red edge keeps it and one with a negative 719 nm simply fits 400–710.
   Costs a few lines and makes the window adaptive rather than global.

*My recommendation: option 3.* It is the only one that does not throw away
good data or keep bad data, and the existing NaN-dropping in
`prepare_spectrum` is the natural place. Worth noting a non-positive `Rrs` is
unphysical at **any** wavelength, so this arguably belongs there regardless of
the 720 decision — I checked, and no band below 700 nm is non-positive in
these 20, so it would be a no-op for 1.0.

**Awaiting JXP.** Nothing is blocked: the 2.0 fits all completed, and this is
about whether they should have been asked to fit that band.

## Reports

### Task 1 — the 2.0 configuration (2026-09-15): **done**

**Version.** `pab_version` `"1.1"` → `"2.0"` in `pab/config.py` and
`setup.py`, then `pip install -e . --no-deps`. Both now agree:

```
config.pab_version      : 2.0
package_versions()[pab] : 2.0
```

The reinstall mattered exactly as Context bite #2 predicted — without it the
dist metadata would still have read `1.1` and every 2.0 fit's `pkg_versions`
JSON would have recorded the wrong version. There is now a test
(`test_pab_version_is_2_0`) asserting **both** strings, with a failure message
naming the reinstall, so the two cannot drift again.

**`FitConfig`** — defaults are now the 2.0 configuration, with
**`FitConfig.v1()`** as the frozen 1.0 one:

| field | 2.0 (default) | `FitConfig.v1()` |
|---|---|---|
| `rt_backend` | `'robust_hybrid'` | `'gordon'` |
| `include_Raman` | `True` | `False` |
| `include_Chl_fl` | `True` | `False` |
| `include_CDOM_fl` | `False` | `False` |
| `fit_Bp` | `True` | `False` |
| `phi_C` | `0.02` | `0.02` |
| `Bp_value` | `0.01` | `0.01` |
| `wave_max` | **720.0** | 700.0 |
| `wave_min`, `model_pair` | 400.0, `ExpBPow` | same |

`v1()` takes `**overrides` so a test can shorten the chain without losing the
RT settings that are the point of it.

**`build_models`** forwards all six RT fields to `standard.expb_pow`. Verified
how that works rather than assuming: `expb_pow(**kwargs)` merges into
`p_ntuple.gen`, whose namedtuple is built from `params.keys()`, so extra
keywords **become fields on `p`** — and `rt_dict_from_p` reads them back with
`getattr(p, key, <default>)`. The round trip produces
`{'rt_backend': 'robust_hybrid', 'fit_Bp': True, 'Bp_value': 0.01,
'include_Raman': True, 'include_Chl_fl': True, 'include_CDOM_fl': False,
'phi_C': 0.02}`.

**`validate_rt_dict` now runs once at setup**, at the end of `build_models`.
It needed a signature change: `build_models(config, wave, *, geom=None,
validate=True)`. `validate_rt_dict` **raises** when a robust backend gets
`geom=None` — it refuses to let `theta_s` be silently defaulted — so the
geometry has to reach it, which is the Task 2 plumbing. That is R3 enforced at
the earliest possible point rather than at the first forward-model call.

Also confirmed: **`ROBUST_HYBRID_WAVE_MIN/MAX = 350/750`**, so the new
`wave_max = 720` is comfortably inside the emulator's training range. A test
pins that relationship against BING's constants rather than the literal 720,
so a future narrowing of the emulator range fails loudly here.

**Tests: 298 passed, 1 skipped** (was 287). 11 new, and three existing ones
adjusted — see below.

**Three existing tests broke, all for the right reason, all fixed honestly:**

1. `test_prepare_spectrum_window_and_variance` — the default window moved to
   400–720, so 720 nm is now *in*. Rather than just bumping the expectation, it
   now asserts **both** windows: 2.0 keeps 720, and `FitConfig.v1()` still
   stops at 700. The published window can no longer move unnoticed.
2. `test_fit_spectrum_recovers_bbp` — pinned to `FitConfig.v1()` and
   documented as *the regression guard on the published Gordon path*. It is a
   5-parameter, Gordon-synthesised test; the 6-parameter robust equivalent is
   Task 2's, and it needs an `ObsGeometry` the Gordon path has no concept of.
3. `test_fit_figure_smoke` — same, because `pab/plotting/fit_fig.py`
   reconstructs a `FitConfig` from the stored row and then calls the **elastic
   Gordon** `calc_Rrs_from_models` directly. That reconstruction is now
   explicitly `FitConfig.v1(...)`, with a comment pointing at Task 4, which
   replaces it with a dispatch on `row["rt_backend"]`. Pinning it is truthful
   about what the function does today; leaving it on the 2.0 defaults would
   have claimed a robust reconstruction it does not perform.


### Task 2 — free `B_p` + geometry plumbing (2026-09-15): **done**

`pab/fit/run.py` now carries per-pixel geometry end to end and samples `B_p`
as a sixth, trailing, linear parameter.

**New/changed API**

| | |
|---|---|
| `requires_geometry(config)` | True for every backend but `'gordon'` |
| `obs_geometry(theta_s, theta_v, dphi)` | → `ObsGeometry` or `None`; **does not re-wrap `dphi`** |
| `_split_flat(flat, nparam_a, rt_dict)` | peels the trailing `B_p` **before** the a/bb split |
| `set_inelastic_Ed(models, geom, rt_dict)` | attaches Ed for Raman + fluorescence (see below) |
| `fit_spectrum(..., geom=None)` | forwards geom to `build_models`, appends `B_p` to guess/bounds/names, passes the **5-tuple** to `chisq_fit.fit` and `fit_one`, and passes `rt_dict` to `init_mcmc` |
| `_fit_diagnostics(..., geom=None)` | peels the median `B_p`; `k` counts it |
| `_gather_fit_input` | returns `theta_s`/`theta_v`/`dphi` off `matchup_pixels` |
| `_fit_only(..., geom=None)` | picklable; `ObsGeometry` is a dataclass so it reaches workers |

**R3 enforced, and it opens nothing.** `build_fits` screens a geometry-less
pixel out **before** the granule open, logs the reason, and records the
`fit_id` under `"failed"`; `fit_matchup` raises a `ValueError` naming the
`geometry` stage. A test asserts the opener is called **zero** times in that
case, and a companion test asserts the same store *with* geometry does reach
the granule. `FitConfig.v1()` (Gordon) is unaffected — it has no geometry
concept, so a NULL pixel fits fine, and there is a test for that too.

**Tests: 315 passed, 1 skipped** (was 298). The toy robust fit
(`importorskip("robust")`) confirms the three things the task asked for: the
chain has **6 columns**, `param_names[-1] == "Bp"`, the posterior `Bp` sits
inside `[BP_PRIOR_PMIN, BP_PRIOR_PMAX]`, and `bbp700` is recovered from a
spectrum synthesised by the **same** robust backend.

#### Two things that were not in the task and had to be fixed

**1. The 2.0 configuration could not run at all without wiring `Ed`.** BING's
inelastic kernels need a downwelling-irradiance spectrum and `init_other_bits`
does **not** provide one; the caller must. Two separate hooks, with two
different failure modes:

- `set_raman_Ed(wave_Ed, Ed)` — missing, Raman silently falls back to a flat
  ratio of 1. BING measures that at **~+60 % increment error at 490 nm**
  against the L23 HydroLight pairs. A *silent* wrong answer.
- `init_Chl_fluorescence(Ed=...)` — missing, `a_model.Ed_ex` stays `None` and
  the kernel dies with `IndexError: too many indices for array: array is
  0-dimensional`. That is what the first run of the new test hit.

`set_inelastic_Ed` now supplies both from `robust`'s packaged Loisel+23 table
interpolated at the pixel's `theta_s` — Plan §2 item 3's "accept the packaged
`Ed`" made concrete. Verified the table spans **350–750 nm at 5 nm**, which
covers the 400–720 fit window *and* the Raman excitation grid (~50 nm blueward
of the emission edge, so a 400 nm edge needs ~352 nm). There is a test pinning
that coverage against `FitConfig().wave_max`.

**2. `robust_hybrid` is extrapolating on every real pixel — see Q1.** Raised
as a question rather than decided: the emulator was trained at nadir view and
zero relative azimuth only, and our pixels run to `theta_v` 59.7°.


### Task 3 — Improve RoB (2026-09-15): **done — it was an inference bug, not a training gap**

**Headline: `robust_hybrid` was applying a silent −22 % flat bias to `Rrs` at
real PACE geometry. Fixed in `robust`, with regression tests. No retraining was
needed, and none would have helped.**

#### What was actually wrong

`cos_theta_v` and `cos_dphi` are **constant in L23** (nadir view, zero
azimuth), so their stored training `std` is the `_STD_FLOOR = 1e-8` guard.
`Emulator._standardise` divided by it, so a 54.6° sensor zenith became

```
(cos 54.6° − 1.0) / 1e-8  =  −4.2e7
```

which saturates every `tanh` in the network. Measured, on the packaged
emulator with a real L23 IOP state:

| geometry | δ(λ) min | max | mean |
|---|---:|---:|---:|
| nadir (trained) | −0.0590 | +0.0342 | −0.0104 |
| `theta_v`=22.1°, `dphi`=0 | **+0.0455** | **+0.0455** | +0.0455 |
| `theta_v`=59.7°, `dphi`=0 | **+0.0455** | **+0.0455** | +0.0455 |
| `theta_v`=54.6°, `dphi`=81.3° **(real pixel)** | **−0.2189** | **−0.2189** | −0.2189 |

At nadir the correction is spectrally structured. Off-nadir it **collapses to
one constant across all 81 wavelengths** — and 22.1° and 59.7° return the
*identical* value, which is the signature of full saturation, not of a model
responding to view angle. At the real pixel that is a **−21.9 % multiplicative
error on `Rrs` at every wavelength**, applied silently to every 2.0 fit.

This is the exact pathology `emulator.py`'s own `_STD_FLOOR` comment describes
having hit once before ("saturated every tanh, and collapsed the correction to
a flat +0.046 at all 81 wavelengths"). The **domain check** was fixed then; the
**standardisation** was not.

#### The fix

`robust/rt/emulator.py::Emulator._standardise` — a feature that was constant
over the training split now standardises to exactly `0` instead of being
divided by the guard:

```python
z = (x - self.mean) / self.std
return jnp.where(self.std > _STD_FLOOR, z, 0.0)
```

Zero is the only defensible value: the network never saw the feature vary, so
it has no information about it. The correct behaviour is to apply the
correction it *did* learn, not an arbitrary extrapolation. **The analytic ZTT
backbone still carries the real geometry dependence** — only the learned
residual is held geometry-blind.

Verified after the fix:

| geometry | δ range | max abs diff vs nadir |
|---|---|---:|
| `theta_v` 22.1° / 59.7° / 54.6°+81.3° / 59.7°−103.9° | −0.0590 … +0.0342 | **0.00e+00** |
| `theta_s` 0° → 30° → 60° (a *trained* axis) | mean −0.049 → −0.010 → +0.053 | 0.083 |

So off-nadir now reuses the trained, wavelength-varying correction, while the
genuinely trained solar-zenith axis still moves it. The M5 seam is intact: once
off-nadir data exists, that feature's `std` exceeds the floor and it activates
automatically, with no interface or weights change.

#### Why no retraining

I ran the real training anyway to check the fix costs nothing at nadir
(`design/py/train_emulator.py --dry-run`, 9960 samples, 147 s):

| | rRMS |
|---|---:|
| hybrid, train | **0.30 %** |
| hybrid, held-out scenes | **0.30 %** |
| hybrid, held-out scenes @60° | 0.32 % |
| ZTT alone | 5.95 % |
| Gordon | 7.21 % |

Unchanged from the shipped weights, as expected — a constant feature
contributes `x − mean = 0` during training too, so training never saw the bug.
**Retraining fixes nothing here and would only churn a committed binary
artifact** (a fresh random draw with the same 0.30 %), so the shipped weights
are left alone.

This also settles the backend question underlying Q1 in PAB's favour: the
correction is worth **20×** (0.30 % vs 5.95 %) at nadir, so `robust_hybrid` is
worth keeping now that it is not corrupted — rather than falling back to
`robust_ztt`.

#### What genuine off-nadir training would require, and why it is blocked

Training the emulator to actually *know* about view angle needs off-nadir
truth, and **there is none on this machine**. I checked the source data rather
than assuming: `$OS_COLOR/Loisel2023/Hydrolight*.nc` have dims
`(IOP_Scenario: 3320, Lambda: 81)` and carry `Rrs`, `Lw`, `Lu_0+` — **no
view-angle dimension at all**, no radiance distribution. L23 is nadir-only by
construction. That is precisely what the design's **M5** is
("*future; detailed once M4 results are in*", "M5's HydroLight runs"), and it
needs new radiative-transfer simulations, not a training run.

So the honest position is: the emulator is now **geometry-blind by explicit
assumption** rather than **geometry-corrupted by numerical accident**, and the
`DomainWarning` still fires to say the correction is unvalidated off-nadir.

#### Files changed (in `retrieve-or-bust`, for JXP to commit)

- `robust/rt/emulator.py` — the `_standardise` fix + a docstring recording the
  measured collapse and the reasoning.
- `robust/tests/test_emulator.py` — three regression tests: constant features
  standardise to zero **and** `delta` stays spectrally structured off-nadir; a
  trained feature (`cos_theta_s`) still moves the correction; off-nadir is
  **still reported** out of domain (silencing the corruption must not silence
  the warning).

**Tests: `robust` 535 passed, 5 skipped** (was 532); **PAB 315 passed,
1 skipped** — unchanged.

#### One thing for Task 6 to handle

The `DomainWarning` now fires once per forward call on every pixel and is
correct but noisy at 146,100 fits. Note also that `on_out_of_domain="ztt"`
(robust's other policy) would be **degenerate** here: since the geometry
features are recorded as trained over `[1, 1]`, every pixel counts as out of
domain, so that policy zeroes the correction everywhere and is equivalent to
plain `robust_ztt`. The production run should suppress the warning explicitly
rather than reach for that policy expecting selective fallback.


### Task 4 — provenance + identity (2026-09-15): **done**

No migration written — schema v5 already carries the six `fits` RT columns
(Prompt 2 Task 1), confirmed at `user_version = 5`.

**Version-aware `fit_id`.** `make_fit_id(matchup_id, ix, iy, model_pair,
version=None)` →
`{matchup_id}_{ix}_{iy}_{model_pair}_v{pab_version}`, e.g.
`7902226_5_G1_3_4_ExpBPow_v2.0`. `version=` overrides for tests and for
reconstructing a historical id. Three tests, including the one the task asked
for — **the unsuffixed 1.0 format is never produced under 2.0** — with the
reason recorded in the test: `build_fits` skips a matchup whose `fit_id` is
already stored, so a colliding id would make a 2.0 run skip every matchup that
already has a 1.0 fit, and `--replace` would overwrite the published rows
instead of adding to them.

**`package_versions()`** gained `robust` and a nested `git_sha` map:

```json
{"pab": "2.0", "bing": "0.0.dev0", "ocpy": "0.1.dev0", "argopy": "1.4.0",
 "remote_sensing": "0.0.dev0", "earthaccess": "0.18.0", "robust": "0.0.dev0",
 "numpy": "2.5.2", "scipy": "1.18.0", "xarray": "2025.9.0",
 "git_sha": {"PAB": "736d8f6", "bing": "bf56f6d", "ocpy": "c3132a6",
             "remote_sensing": "2b85c65", "retrieve-or-bust": "5ca740d"}}
```

All five SHAs resolve on the workstation. Two details worth recording:

- **`robust` is distributed as `retrieve-or-bust`** —
  `importlib.metadata.version("robust")` raises `PackageNotFoundError`. A
  `_DISTRIBUTION_NAMES` alias maps it, and the entry is keyed under the
  **import** name, which is what appears in tracebacks and in `rt_backend`.
- **The git SHAs are the point, not a nicety.** Four of the five repos are
  editable installs permanently reporting `0.0.dev0`, so the version string
  identifies nothing. After Task 3's change to `robust`, "which `robust`?" is a
  question a 2.0 fit has to be able to answer.

**The container seam.** Resolution order per repo is `PAB_GIT_SHAS` (a JSON
object, e.g. from an image label the entrypoint exports) **then**
`git rev-parse --short HEAD` in the installed source tree, with
`"unknown"` as the floor. The env var **wins** over git, so a deliberately
stamped image is never second-guessed by a stray `.git` copied into it.
`_git_sha` cannot raise or hang: missing `.git`, missing `git` binary, bad
repo, all become `"unknown"`, and the subprocess has a 10 s timeout —
provenance capture must never fail a fit. Malformed JSON in the env var is
ignored rather than fatal (tested).

One deliberate deviation from the task text: the SHAs are read **once per
process** via `functools.cache` rather than literally at import. `import pab`
spawning five subprocesses would be a poor trade for an identical result, and
`find_spec` is used instead of importing the packages so a provenance lookup
never drags in `jax` or `argopy`.

**`persist_fit` writes the v5 columns** — `rt_backend`, `include_raman`,
`include_chl_fl`, `include_cdom_fl`, `phi_c`, `fit_bp` — from the `FitConfig`.
Two tests assert a 2.0 row and a `FitConfig.v1()` row land distinctly
(`robust_hybrid`/1/1/0/1 vs `gordon`/0/0/0/0, `wave_max` 720 vs 700).

**`docs`/report.** `provenance_block` would have rendered the nested map as a
dict repr inside the version column, so the SHAs now get their own
"Source revisions" table on the methods page. Sphinx still builds with **zero**
warnings.

**Tests: 325 passed, 1 skipped** (was 315). Eight new: the `robust` entry, the
`git_sha` map's shape, SHAs looking like short hashes, the env-var override,
malformed JSON tolerated, `"unknown"` for a non-repo, and the two `persist_fit`
configuration rows.


### Task 5 — fitted physics everywhere (2026-09-15): **done**

**One dispatch point.** `pab.fit.run.reconstruct_rrs(models, a_params,
bb_params, rt_dict, *, geom=None, Bp=None)` is now the only place PAB chooses a
forward model: `rt_backend == 'gordon'` → `calc_Rrs_from_models`, anything else
→ `calc_Rrs_from_models_robust(..., geom=, Bp=)`. A missing `rt_backend` (a
legacy 1.0 `rt_dict`) means Gordon. Both consumers go through it rather than
calling `bing.evaluate` themselves — reconstructing a robust fit with the
elastic relation produces perfectly plausible numbers that are simply not the
physics that was fitted, which is not a failure mode that announces itself.

**`_fit_diagnostics`** now scores a fit against its own physics. It already
peeled the median `B_p` (Task 2); it now forwards that and `geom` to the
dispatch, so χ²/AIC/BIC for a 2.0 fit are no longer a Gordon reconstruction of
a robust posterior.

**`pab/plotting/fit_fig.py`** reconstructs from the **stored** configuration
rather than a guess:

- `_config_from_row(row)` rebuilds the `FitConfig` from the schema-v5 columns.
  Built on `FitConfig.v1()` as the base, deliberately: a legacy 1.0 row has
  those columns NULL, and NULL must mean *the elastic Gordon fit it actually
  ran*, not the 2.0 defaults. Tested both ways.
- `_geometry_from_row(store, row)` reads `theta_s`/`theta_v`/`dphi` back from
  the fit's `matchup_pixels` row.
- The posterior is split with `_split_flat`, so the trailing free `B_p` is
  peeled before the a/bb split and passed to the robust forward model — without
  that the bb-model would receive an extra parameter.
- `set_inelastic_Ed` is called on the rebuilt models, so the figure's Raman and
  fluorescence terms match the fit's rather than silently falling back to a flat
  `Ed` ratio.

This replaces the `FitConfig.v1()` pin I put in during Task 1, which was
truthful about what the function did then and is now obsolete.

**XLA thread pinning.** `pab.parallel.init_worker` gained
`XLA_FLAGS=--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1`
alongside the BLAS caps, via a `_THREAD_CAPS` mapping, applied with
`setdefault` so a deliberate setting survives. It must be set before JAX
initialises its backend, which is exactly what a pool initialiser is for.

**A duplicate that would have defeated the whole point.** `pab/fit/run.py` had
its **own** `_worker_init` — a second copy of the BLAS caps — and it is the one
the **fit** pool uses, i.e. the only pool that actually runs JAX. Adding
`XLA_FLAGS` to `pab.parallel.init_worker` alone would have left the fit stage
uncapped while the shared helper looked correct. `run._worker_init` now
delegates to the shared one, and a test asserts they cannot drift again.

**Tests: 334 passed, 1 skipped** (was 325). Nine new: the three dispatch
branches (Gordon / robust-with-`geom`-and-`Bp` / legacy-defaults-to-Gordon,
each via a mocked `calc_Rrs_from_models_robust` as the task asks, asserting the
`geom` object identity and the `Bp` value reach it); `_config_from_row` for a
2.0 row and a NULL legacy row; `_geometry_from_row`; and three on the thread
caps, including that `run._worker_init` is the shared one and that a
deliberate `XLA_FLAGS` is respected.


### Task 6 — real end-to-end check (2026-09-17): **done — 60/60 fits, 0 failures**

**This is the first time 2.0 has fitted real data.** Three arms × 20 matchups,
every fit succeeded.

**Setup.** Scratch `v2` via `split_version.copy_database`, pruned to the 10
pilot `V3_2` granules → **20 matchups / 200 pixels**, schema v5.
`--stage geometry --jobs 8` filled **all 200 pixels, 0 failures, 28.6 s**.
`PAB_DATA_DIR` pointed at the *scratch* `v2/`, so the layout mirrors production
exactly (`$PAB_DATA_DIR/fit_chains/`) without writing into the real
`v2/fit_chains/`. `build_fits` fits the rank-1 pixel per matchup, so the subset
used is **all 20 matchups (20 fits per arm)**, not all 200 pixels.

**A third arm.** Per Q1 (JXP: option 3) I added `robust_ztt` alongside 2.0 and
`FitConfig.v1()`, to measure what the emulator correction is now worth after
Task 3's fix. Each arm ran serially in its own database — necessary, because
`make_fit_id` distinguishes *versions*, not *configurations*, so hybrid and
ztt at `pab_version = 2.0` produce identical ids.

#### Per-matchup results

| matchup | s/fit 2.0 | s/fit 1.0 | bbp700 2.0 | bbp700 1.0 | ratio | Bp | chl | χ² 2.0 | χ² 1.0 | acc 2.0 | acc 1.0 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1902370_80 | 194.5 | 37.8 | 0.001162 | 0.001335 | 0.871 | 0.0221 | 0.123 | 0.45 | 0.37 | 0.321 | 0.494 |
| 1902380_134 | 207.6 | 38.5 | 0.001821 | 0.001613 | 1.129 | 0.0216 | 0.073 | 1.12 | 0.72 | 0.346 | 0.446 |
| 1902381_134 | 197.1 | 37.3 | 0.000411 | 0.000530 | 0.776 | 0.0043 | 0.147 | 0.78 | 0.69 | 0.381 | 0.480 |
| 1902722_36 | 183.4 | 33.9 | 0.000851 | 0.001113 | 0.765 | 0.0280 | 0.143 | 0.42 | 0.32 | 0.350 | 0.483 |
| 2902912_68 | 185.1 | 36.3 | 0.000932 | 0.001233 | 0.756 | 0.0305 | 0.119 | 0.34 | 0.32 | 0.380 | 0.490 |
| 2902912_69 | 177.1 | 32.8 | 0.001070 | 0.001381 | 0.775 | 0.0317 | 0.115 | 0.38 | 0.34 | 0.385 | 0.478 |
| 2903451_85 | 207.8 | 36.5 | 0.001024 | 0.001410 | 0.726 | 0.0410 | 0.120 | 1.37 | 0.59 | 0.293 | 0.463 |
| 2903919_3 | 177.9 | 39.3 | 0.000413 | 0.000663 | 0.623 | 0.0055 | 0.139 | 0.82 | 0.58 | 0.358 | 0.474 |
| 2903919_4 | 166.1 | 46.3 | 0.000446 | 0.000692 | 0.644 | 0.0087 | 0.114 | 0.87 | 0.62 | 0.210 | 0.474 |
| 2903920_1 | 173.7 | 39.3 | 0.000654 | 0.000928 | 0.706 | 0.0325 | 0.124 | 2.05 | 1.02 | 0.319 | 0.458 |
| 2903920_2 | 194.4 | 33.4 | 0.000634 | 0.000911 | 0.696 | 0.0333 | 0.124 | 2.38 | 1.14 | 0.310 | 0.459 |
| 2903920_3 | 184.2 | 33.2 | 0.000634 | 0.000907 | 0.699 | 0.0367 | 0.122 | 2.36 | 1.14 | 0.339 | 0.457 |
| 3902343_37 | 173.9 | 37.4 | 0.001153 | 0.001272 | 0.906 | 0.0347 | 0.097 | 0.44 | 0.37 | 0.359 | 0.460 |
| 3902615_25 | 178.6 | 33.5 | 0.001395 | 0.001348 | 1.035 | 0.0202 | 0.085 | 0.89 | 0.54 | 0.326 | 0.455 |
| 5906343_162 | 187.2 | 33.9 | 0.000508 | 0.000660 | 0.770 | 0.0193 | 0.078 | 0.45 | 0.21 | 0.239 | 0.452 |
| 5906471_143 | 187.4 | 35.9 | 0.000614 | 0.000909 | 0.675 | 0.0057 | 0.129 | 0.54 | 0.44 | 0.291 | 0.497 |
| 5906476_142 | 175.9 | 38.1 | 0.001040 | 0.001342 | 0.775 | 0.0193 | 0.243 | 0.42 | 0.44 | 0.348 | 0.502 |
| 5906490_108 | 166.0 | 37.5 | 0.000782 | 0.001132 | 0.691 | 0.0346 | 0.064 | 0.51 | 0.41 | 0.333 | 0.461 |
| 5906521_119 | 159.7 | 34.1 | 0.000469 | 0.001016 | 0.462 | 0.0374 | 0.133 | 0.76 | 0.47 | 0.300 | 0.469 |
| 6904187_157 | 148.3 | 32.7 | 0.000541 | 0.000797 | 0.679 | 0.0193 | 0.185 | 0.26 | 0.24 | 0.288 | 0.463 |

#### Headline numbers

| | median | min | max |
|---|---:|---:|---:|
| **`bbp700` 2.0 / 1.0** | **0.741** | 0.462 | 1.129 |
| `bbp700` hybrid / ztt | 0.886 | 0.810 | 1.230 |
| `Bp` (prior 0.004–0.05) | 0.0250 | 0.0043 | 0.0410 |
| `Rrs_unc(719)/Rrs(719)` | 0.236 | −0.558 | 3.849 |
| s/fit 2.0 `robust_hybrid` | 181.0 | 148.3 | 207.8 |
| s/fit 2.0 `robust_ztt` | 178.2 | 151.5 | 204.9 |
| s/fit 1.0 `gordon` | 36.4 | 32.7 | 46.3 |
| χ² 2.0 / `robust_ztt` / 1.0 | 0.65 / 0.58 / 0.45 | | |

**The 2.0 fit retrieves ~26 % less `b_bp`(700) than 1.0** (median ratio 0.741),
systematically — 18 of 20 matchups are below 1.0. That is the single most
important number here, and it is far larger than the `Rrs` uncertainties.
Whether it is an improvement is the Prompt 4+ comparison against the float
`BBP700`; this task only establishes that the shift is large and consistent.

**The emulator correction is worth ~11 %** (`hybrid/ztt` median 0.886) and costs
essentially nothing in time (181 vs 178 s/fit). After Task 3's fix that is a
real, bounded contribution rather than the flat −22 % collapse it was applying
before — which is the empirical vindication of that fix.

**`B_p` is well determined but sits outside the emulator's trained range on
every fit.** `0/20` land inside `[0.01026, 0.018]`; JXP accepted that in Q1.
Worth recording: `3/20` press against the **lower prior bound** (0.0043,
0.0055, 0.0057 against a floor of 0.004), i.e. the data wants a smaller `B_p`
than the prior allows on those. Not acting on it, but it is the kind of
pile-up that should not go unnoticed.

**Cost.** 2.0 is **~5× slower** than 1.0 per fit (181 s vs 36 s). At 14,610
matchups that is ~735 core-hours for the 2.0 arm versus ~146 for 1.0 — the
number Prompt 5's Nautilus sizing needs. Note these s/fit were measured with
three arms running concurrently; the uncontended `--jobs 2` run came out at
~101 s/fit of wall per worker-pair, so the contended figures are conservative.

#### `--jobs 2` (spawned workers → JAX JIT in a worker)

`pab --db … --stage fit --jobs 2` on a 6-matchup copy: **6 written, 0 failed,
304 s**. JAX compiles per worker process without trouble. Results match the
serial arm to **0.1–1.6 %** (MCMC is unseeded, so that is sampling noise, not
a discrepancy).

#### Persistence checks — all 20/20

`pab_version='2.0'`, `rt_backend='robust_hybrid'`, `include_raman=1`,
`include_chl_fl=1`, `include_cdom_fl=0`, `fit_bp=1`, `phi_c=0.02`,
`wave_max=720.0`, `fit_id` ending `_v2.0`, `chains_path` non-null. The 20
`NASA_GIOP` baseline rows are untouched. Example id:

```
1902370_80_PACE_OCI.20251004T014456.L2.OC_AOP.V3_2.nc_292_979_ExpBPow_v2.0
```

**Chains**: 20 NPZ, 23 MB, in `$PAB_DATA_DIR/fit_chains/` — i.e. exactly where
pointing `PAB_DATA_DIR` at the version directory puts them (~1.15 MB/fit →
**~17 GB** for 14,610 matchups, close to v1's 18.09 GiB).

**Frozen data intact**: `v1/pab.db` sha256 still `09de0a6d…f978273`; the real
`v2/pab.db` still has **0** BING fits and **0** filled pixels; the real
`v2/fit_chains/` is still empty. All 60 fits stayed in scratch.

**Docs**: `docs/fitting.rst` gained an RT-configuration section (the 2.0 vs
`v1()` table, the free-`B_p` chain layout, the `Ed` requirement, the
reconstruction dispatch) and updated `fit_id`/provenance sections;
`HOWTO.md` gained the 2.0 defaults, the geometry prerequisite on the `fit`
stage row, and the chains-path warning. Sphinx clean; **334 tests pass**.

**One finding raised as Q2**: `wave_max = 720` pulls in a band that is negative
or noise-dominated on **40 %** of these matchups, and that is where the 2.0 χ²
degradation is concentrated.


### Task 7 — `build_v2_prompt_4.md` updated (2026-09-17): **done**

Everything added is checked against the repos and the store as they stand
today. Both source repos are now **committed** — PAB `eeda46f`,
retrieve-or-bust `e1f4289` ("off nadir") — so the SHAs in the doc are real.

**The one that would have cost the most: the image must be built from
`retrieve-or-bust` ≥ `e1f4289`.** An image staged from `5ca740d` or earlier
ships the emulator saturation bug, which applies a **flat −22 % bias to `Rrs`
at every off-nadir pixel with no error**. A container is exactly where that
would go unnoticed — there is no test suite in the image and the pod logs look
normal. So Task 1 now (a) says to check out that commit before staging and
(b) requires a **build guard that is a regression test, not an import check**:
one `robust_hybrid` forward call at off-nadir geometry asserting the
correction is spectrally varying rather than a flat constant. That guard fails
loudly on a stale `robust`.

**`robust`'s data files are runtime-critical and easy to rsync away.** Task 1's
original wording — "rsync `robust/` + `setup.py`, minus `.git`/notebooks/
reports" — is right in spirit, but the doc now names
`robust/rt/files/emulator_l23.npz` **and** `robust/rt/data/ed_l23.npz` as
must-keep. The second is the one that would surprise: PAB's
`set_inelastic_Ed` reads that `Ed` table on **every** 2.0 fit, because PACE L2
carries no `Ed`. Lose it and fluorescence raises `IndexError … 0-dimensional`
while Raman degrades silently. `context/` (16 MB) and `notebooks/` (3.3 MB)
are the things actually worth excluding from a 62 MB repo.

**Corrections and hard numbers added:**

- Task 1 cited "Prompt 3 Task 3's seam" — the SHA seam is Prompt 3 **Task 4**.
  JXP inserted "Improve RoB" as Task 3, shifting the numbering; noted inline so
  the next reader is not sent to the emulator task.
- The five `PAB_GIT_SHAS` keys are spelled out (the fifth is
  **`retrieve-or-bust`**, the repo name — not `robust`, the import name), with
  today's values and the env-wins-over-git precedence.
- Task 3 gained the actual staging target: sha256
  `ef552419…c127b735`, 120,635,392 B, **schema v5**, plus an in-pod
  `PRAGMA user_version = 5` check — a v4 copy would be fitted without the
  geometry columns and nobody would notice until the fits came back empty.
- Recorded that the staged DB has **0 of 146,100 pixels** with geometry, so
  that reads as expected rather than as a staging failure, and flagged the
  11,494-granule `geometry` budget as Prompt 5's problem.
- Task 4's gates went from "the fit succeeds" to the concrete v5 column values,
  the `_v2.0` id, 6-column chains, the `git_sha` map being non-`"unknown"`
  (the real check that the label reached the process), and **numeric sanity
  bands** from the 20 real fits — `bbp700` 1e−4–2e−3, `Bp` in [0.004, 0.05],
  χ² order-unity, acceptance 0.2–0.4.
- Noted that `geometry` in-pod is a **live CMR lookup + 1.8 GB L1B read per
  granule** — the one new external dependency 2.0 introduces, and something a
  Nautilus job needs credentials and egress for.
- Noted the thread caps are automatic now (`init_worker` sets `XLA_FLAGS`), and
  that the `DomainWarning` fires **once per forward call** and must be
  suppressed or the pod log is unusable — with the warning that
  `on_out_of_domain="ztt"` is not the fix, since it degenerates to plain
  `robust_ztt`.
- The measured cost table (2.0 ~5× 1.0; ~17 GB of chains) with an explicit
  caveat that the workstation s/fit was measured under contention, so Prompt 5
  should size from Task 4's in-pod number instead.

**Raised as Prompt 4 Q1: `wave_max` must be settled before the image is
built.** Prompt 3 Q2 is still open, and it is now on the critical path — if the
answer changes `FitConfig.wave_max` or adds a non-positive-band screen, the
change has to be in the code before `:2.0.0`, or the image is rebuilt and
re-pushed. The doc says to proceed with the current defaults if there is no
answer, but not to treat the image as final.

**Also added a Task 5 to Prompt 4** ("update `build_v2_prompt_5.md`"),
mirroring the pattern, flagged as removable.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-15 (Prompt 3 Task 1 — the 2.0 fit configuration)

`pab_version` is `2.0` (and the installed dist agrees), `FitConfig` defaults to
the inelastic robust configuration, `FitConfig.v1()` preserves the published
1.0 one, and `build_models` forwards the RT fields and validates the result
once at setup. 298 tests pass, docs clean, v1 sha unchanged.

What I learned / want to remember:

- **`validate_rt_dict` cannot run at setup without geometry**, and that is
  deliberate on BING's side: a robust backend with `geom=None` raises rather
  than defaulting `theta_s`. So "run `validate_rt_dict` at setup" forced
  `build_models` to grow a `geom` parameter, which in turn is why switching
  the defaults to robust immediately broke every call path that fits without
  geometry. That is the design working — the failure is loud and at setup, not
  a silently wrong forward model — but it means Tasks 1, 2 and 4 are coupled
  more tightly than the task list suggests.
- **BING's parameter namedtuple accepts arbitrary keywords.**
  `expb_pow(**kwargs)` → `p_ntuple.gen(**params)` builds the namedtuple from
  `params.keys()`, so passing `rt_backend=`/`fit_Bp=`/`Bp_value=` simply
  creates those fields, and `rt_dict_from_p` reads them with `getattr(p, key,
  default)`. Convenient, but it also means a **typo in a keyword is silently
  accepted** — it becomes a field nobody reads, and the RT dict quietly keeps
  its default. I verified the round trip explicitly instead of trusting the
  call, and the new `test_build_models_forwards_the_rt_fields` asserts every
  key, which is the only real protection against that failure mode.
- **Three failing tests were all correct failures**, and the temptation was to
  paper over them by loosening assertions. Two are genuinely 1.0-physics
  regression guards, so pinning them to `FitConfig.v1()` keeps exactly the
  coverage they had; the window test got *stronger* by asserting both windows
  rather than swapping 700 for 720. The third exposed something worth knowing:
  `fit_fig.py` reconstructs a config from the DB row but then calls the
  elastic Gordon forward model directly, so with 2.0 defaults it would have
  been building a robust `rt_dict` it never honours. Pinning it to `v1()` with
  a pointer to Task 4 makes the current behaviour honest instead of
  accidentally-correct.
- **`wave_max = 720` is safe** — `ROBUST_HYBRID_WAVE_MIN/MAX` are 350/750. I
  pinned the test against those constants rather than the literal, so if the
  emulator's training domain is ever narrowed the failure lands here rather
  than mid-run.
- The version bump is three strings in three places (`config.pab_version`,
  `setup.py`, the installed `.dist-info`) and only a reinstall reconciles the
  third. `test_pab_version_is_2_0` now asserts the pair with a message naming
  the fix, so the next bump cannot half-land.

### 2026-09-15 (Prompt 3 Task 2 — free B_p, geometry plumbing, and the Ed that was missing)

Geometry now flows from `matchup_pixels` through `_gather_fit_input` →
`_fit_only` → `fit_spectrum` → `build_models`/`fit_one`, and `B_p` is sampled
as a sixth trailing parameter. 315 tests pass. Two things came out of this that
the task did not anticipate.

**The 2.0 fit could not run at all.** The first execution of the new toy robust
test died with `IndexError: too many indices for array: array is
0-dimensional` inside BING's fluorescence kernel. The cause is that BING needs
an `Ed` spectrum for its inelastic terms and **wires none automatically** —
`init_other_bits` does not touch it, and the two processes need two *different*
calls: `set_raman_Ed` for the Raman ratio and `init_Chl_fluorescence` for the
excitation integral. PAB called neither. The fluorescence one crashes, which is
the lucky case; **the Raman one fails silently**, falling back to a flat
`Ed(λ')/Ed(λ) = 1` that BING itself measures at ~+60 % increment error at
490 nm. Had `include_Chl_fl` been False we would have shipped a quietly wrong
Raman correction across 146,100 pixels and had no signal at all. Plan §2 item 3
said "robust falls back to its packaged L23 Ed … Accept", which reads like
something that happens by itself; it is not — it is a call PAB has to make. Now
`set_inelastic_Ed` does, from `robust.rt.ed`'s packaged table at the pixel's
`theta_s`, and I checked the table covers 350–750 nm rather than assuming the
400–720 window was enough (it needs ~352 nm for the Raman excitation grid).

**`robust_hybrid`'s emulator is out of its training domain on 100 % of our
pixels.** `robust` emits a `DomainWarning` on every forward call; I read it
instead of filtering it out, then pulled the emulator's actual domain. Its
`cos_theta_v` and `cos_dphi` axes are both trained over **[1, 1]** — nadir
view, zero relative azimuth, never varied — while our measured pixels run
`theta_v` 22–60° and `dphi` −104 to +82°. Only 17 % of the free `B_p` prior is
inside the trained `B_p` range too. So the learned correction that is the
entire difference between `robust_hybrid` and `robust_ztt` is being
extrapolated everywhere, on axes it never saw move. Raised as Q1 with three
options rather than silently switching the default, because it questions a
locked plan decision (Q4/R2).

What I learned / want to remember:

- **Read the warnings the run emits, especially the ones from a dependency you
  did not write.** The `DomainWarning` was 15 lines of noise in a passing test;
  it is also the most consequential thing I found today. The instinct to filter
  warnings to see the failure would have buried it.
- **Two failure modes for the same missing input, and the loud one is the
  lucky one.** Fluorescence crashed; Raman would have degraded silently. When a
  library offers a "sensible fallback" for a physical input, check what the
  fallback costs — here it is documented in the very docstring of the setter
  nobody was calling.
- **`dphi` must not be re-wrapped.** `obs_geometry` passes it through
  unchanged with a test pinning `81.33`, `−103.92`, `180.0`, `−179.0`. The
  `geometry` stage already wrapped it; wrapping to (−180, 180] twice is
  idempotent for most values but the boundary case is not, and re-wrapping is
  the kind of thing that looks defensive and is actually a bug.
- **Turning on a gate breaks the fixtures that never needed it**, and that is
  a signal, not an annoyance: `test_build_fits_parallel_matches_serial` began
  failing with "no viewing geometry" the moment the R3 screen landed, which is
  precisely correct. I seeded the shared `_seed_matchup` helper with the real
  reference pixel's angles (and a `geometry=False` switch), so the fixtures now
  look like a store whose `geometry` stage has run — which is what every 2.0
  fit will face.
- `init_mcmc` needs `rt_dict` passed explicitly or `ndim` stays at 5 and the
  free `B_p` never gets a dimension. Easy to miss, since the call succeeds and
  simply samples the wrong thing.

### 2026-09-15 (Prompt 3 Task 3 — "improve RoB": found and fixed a silent −22 % bias)

JXP added this task after Q1. The answer turned out not to be training at all:
`robust_hybrid` had an **inference** bug that was corrupting every off-nadir
evaluation, and no amount of training would have touched it.

`cos_theta_v`/`cos_dphi` are constant in L23, so their stored `std` is the
`1e-8` guard. `_standardise` divided by it, turning a 54.6° sensor zenith into
a standardised −4.2e7, saturating every `tanh`. The measured consequence: at
nadir the correction runs −0.059…+0.034 across the band; at a real PACE pixel
it collapses to a **flat −0.219 at all 81 wavelengths** — a silent −22 %
multiplicative bias on `Rrs`. Two different view angles (22° and 60°) returned
byte-identical output, which is what convinced me it was saturation rather than
a model responding to geometry.

The fix is three lines: a feature that was constant in training standardises to
exactly 0, because the network has no information about it. Off-nadir then
reuses the trained correction (verified: max abs difference vs nadir is exactly
0.0), while `cos_theta_s` — genuinely varied in L23 — still moves the
correction across 0/30/60°. Three regression tests added in `robust`.

I ran the real training anyway and got 0.30 % rRMS train and held-out, matching
the shipped weights, and did **not** reship: a constant feature contributes
`x − mean = 0` during training too, so training never saw the bug, and a fresh
random draw would only churn a committed artifact.

What I learned / want to remember:

- **"Do the training" was the wrong frame, and checking the data settled it in
  ten minutes.** I opened `$OS_COLOR/Loisel2023/Hydrolight200.nc` instead of
  reasoning about it: dims `(IOP_Scenario, Lambda)`, no view-angle axis at all.
  There is no off-nadir truth on this machine, so the emulator *cannot* learn
  view geometry here — that is the design's own M5 and it needs new HydroLight
  runs. Had I started training something I would have burned hours producing a
  model with exactly as much view-angle information as the one we have.
- **A guard against division-by-zero became a silent corruption.**
  `max(std, 1e-8)` is the obvious way to avoid 0/0 on a constant feature, and
  it is right *inside* the training distribution where the numerator is also
  exactly 0. It is catastrophic outside it, because the tiny denominator
  amplifies any excursion by 1e8. The repo had already been bitten by this once
  and fixed the *domain check* — judging the excursion in the units the network
  sees — without fixing the standardisation that produced the number. Fixing
  the detector and not the fault is a very easy thing to do.
- **Identical outputs from different inputs is the cheapest saturation test
  there is.** `theta_v` 22° and 60° returning the same value to the last bit
  was more diagnostic than any magnitude check, and it is the assertion I put
  in the regression test.
- **The warning was right and the code was wrong.** `robust` told me on every
  single forward call that it was out of domain and suggested `mode='ztt'`.
  Following that advice (option 1 in Q1) would have "worked" — and thrown away
  a correction that is worth 20× at nadir (0.30 % vs 5.95 % rRMS) to dodge a
  three-line bug. Worth remembering when a dependency's own advice is to use
  the less capable path.
- The `DomainWarning` deliberately still fires: the correction is now
  geometry-**blind** by explicit assumption, which is defensible, rather than
  geometry-**corrupted**, which was not — but it is still unvalidated
  off-nadir, and that should keep being said until M5 data exists.

### 2026-09-15 (Prompt 3 Task 4 — version-aware fit ids and real provenance)

`make_fit_id` now carries `_v{pab_version}`, `package_versions()` reports
`robust` plus a git SHA per source repo, and `persist_fit` writes the six v5 RT
columns. 325 tests pass; docs clean.

What I learned / want to remember:

- **The version suffix is load-bearing, not decorative.** `build_fits` resumes
  by checking whether a `fit_id` is already in the store. Had 2.0 reproduced
  the 1.0 id, a 2.0 run over a store containing 1.0 fits would have reported
  every matchup as "skipped — already done" and written nothing, which looks
  exactly like a successful resume. `--replace` would have been worse: it would
  have overwritten the published 1.0 rows. I put that reasoning inside the test
  rather than in a comment, because the test is what a future reader will hit
  when they wonder why the id has a suffix.
- **`robust`'s import name and distribution name differ** (`retrieve-or-bust`),
  so the obvious `importlib.metadata.version("robust")` raises. I keyed the
  provenance entry under the *import* name — that is the name in `rt_backend`,
  in tracebacks, and in every conversation about it — and put the mapping in a
  documented alias dict rather than silently recording a name nobody uses.
- **Versions genuinely do not identify this stack.** Four of five repos are
  editable installs stuck at `0.0.dev0`. Before today that was a latent
  weakness; after Task 3 changed `robust`'s inference behaviour it is a real
  one, because "which `robust`?" now changes the numbers. The SHA map is the
  fix, and it is worth more than the version strings beside it.
- **Designing the container seam meant deciding precedence, and the
  non-obvious direction is right.** Env var **over** git: an image is stamped
  by its build with the SHAs it checked out, and if a `.git` happens to be
  copied in, it is likelier to be stale or irrelevant than authoritative. The
  other order would let an accident silently override a deliberate statement.
- **Provenance capture must not be able to fail the thing it describes.**
  `_git_sha` swallows every failure into `"unknown"` and bounds the subprocess
  at 10 s; malformed JSON in the env var is ignored, not raised. A fit that
  dies because it could not work out its own commit would be an absurd way to
  lose a 146,100-pixel run.
- A nested value in `package_versions()` quietly broke a *presentation*
  contract I would not have thought to check: `rst.py` builds a two-column
  DataFrame straight from the mapping, so `git_sha` would have rendered as a
  Python dict repr on the public methods page. Found it by rendering the block
  rather than trusting that the tests passing meant it looked right.

### 2026-09-15 (Prompt 3 Task 5 — one forward model, chosen from the stored row)

χ²/AIC/BIC and the fit figure now reconstruct with the backend the fit actually
used, read back out of the `fits` row and `matchup_pixels`. 334 tests pass,
docs clean.

What I learned / want to remember:

- **The duplicate `_worker_init` is the finding here.** `pab/fit/run.py` kept
  its own copy of the BLAS caps, independent of `pab.parallel.init_worker`.
  Adding `XLA_FLAGS` to the shared helper — which is what the task literally
  asked for — would have pinned XLA in `match`, `geometry` and `figure`, and
  **not** in `fit`: the one pool that runs JAX. The change would have looked
  complete, the tests would have passed, and 16 workers would each have spun up
  an ncores-wide XLA thread pool on Nautilus. I only caught it because I grepped
  for the callers of the function I had just edited instead of assuming the name
  was unique. Two copies of a "cap the threads" helper is precisely the kind of
  duplication that stays harmless until the day one of them grows a line.
- **NULL means "what it was", not "what we default to now".** `_config_from_row`
  builds on `FitConfig.v1()` rather than `FitConfig()`, because a 1.0 row's v5
  columns are NULL and the 2.0 defaults would claim Raman, fluorescence and a
  free `B_p` that row never had. Same shape of error as the `pab_version` note
  in `db_schema.rst`: a stored row describes the past, and the current defaults
  are not a safe stand-in for it.
- **Routing both consumers through one function was worth more than the
  dispatch itself.** The figure and the diagnostics had independently grown
  their own `calc_Rrs_from_models` call, and the figure's had also quietly
  skipped `set_inelastic_Ed` and the `B_p` peel. Centralising made those two
  omissions obvious; fixing them in two places separately, I would probably have
  fixed one.
- The `DomainWarning` is still emitted once per forward call and is now also
  emitted from the *figure* path. Still correct, still noisy — Task 6 should
  decide how the production run suppresses it.

### 2026-09-17 (Prompt 3 Task 6 — 2.0 fits real data for the first time)

Three arms × 20 real matchups, 60/60 fits succeeded. The headline: **2.0
retrieves ~26 % less b_bp(700) than 1.0**, systematically (median ratio 0.741,
18/20 below unity). Everything asked for verified — `pab_version`, the six v5
columns, the `_v2.0` id, chains in `$PAB_DATA_DIR/fit_chains/`, v1 sha
unchanged, production `v2` untouched.

What I learned / want to remember:

- **The red edge is the story of this run, and I only found it because R4 asked
  for one number.** `Rrs_unc(719)/Rrs(719)` was on the checklist as a sanity
  value; computing it showed `Rrs(719)` is **negative on 6 of 20 matchups** and
  swamped by its own uncertainty on 2 more — 40 % unusable. Then the χ² split
  fell out: the four worst 2.0 fits in the whole set are exactly the four most
  negative `Rrs(719)`, and the bad-red-edge group degrades 1.84× against 1.0
  while the good group degrades 1.24×. A single requested diagnostic turned
  into the explanation for the one number that looked wrong. Raised as Q2 with
  a recommendation to screen non-positive bands per matchup rather than move
  the global window.
- **Task 3's fix is now empirically justified, not just argued.** The emulator
  correction is worth a median 11 % on `bbp700` and costs 3 s/fit out of 181.
  Before the fix it was applying a flat −22 % to `Rrs`. "Worth 11 % when
  correct, −22 % when broken" is the kind of thing that is only visible once
  real fits exist.
- **Concurrency inflated my s/fit numbers and I nearly reported them as clean.**
  I ran the three arms simultaneously to save wall time, which is fine for the
  science but means every s/fit was measured under 3-way contention. The
  uncontended `--jobs 2` run came out ~45 % faster per fit. I labelled the
  figures rather than quietly presenting them as the cost model Prompt 5 will
  size Nautilus from — a projection built on contended timings would over-book
  the cluster.
- **`make_fit_id` distinguishes versions, not configurations**, so the three
  arms needed three databases: hybrid and ztt both stamp `_v2.0` and would
  have overwritten each other. Fine for the production run, which has one
  configuration, but it is a real constraint on any comparison study and it is
  now written into `docs/fitting.rst`.
- **`B_p` piles up on its lower prior bound for 3 of 20 matchups** (0.0043
  against a floor of 0.0040). Not acted on, but prior pile-up means the data
  wants something the prior forbids, and it is worth watching whether that
  fraction grows over 14,610.
- The background arms outlived the session that launched them and completed
  normally; the results were waiting in the scratch JSON. Worth knowing that a
  detached `nohup` run survives a session boundary here — and worth checking
  the output files rather than assuming a stopped watcher means lost work.

### 2026-09-17 (Prompt 3 Task 7 — handed three prompts' findings to `build_v2_prompt_4.md`)

Updated the containerisation prompt. Prompt 4 is where a mistake becomes
invisible — an image has no test suite and its logs look fine — so the edits
concentrate on turning "it built" into "it built the right thing".

What I learned / want to remember:

- **The highest-value edit was turning a build guard into a regression test.**
  The original asked for a guard that "imports `robust.rt`, runs one
  `robust_hybrid` forward call". That passes perfectly happily on the *broken*
  emulator — the saturated network returns a number, just a constant one. The
  guard now runs the forward call at off-nadir geometry and asserts the
  correction is spectrally varying. Same cost, and it is the difference between
  a check that confirms the import graph and one that confirms the physics.
  Generally: a smoke test that only asserts "no exception" cannot catch a bug
  whose symptom is a plausible wrong number.
- **Data files are the thing rsync excludes by accident.** Two `.npz` files
  totalling 8 KB decide whether every 2.0 fit works. They live under
  `robust/rt/files/` and `robust/rt/data/`, neither of which looks like
  "source", and the existing build script's exclude list is written as
  "everything except the package". Naming them explicitly in the prompt costs
  two lines and removes a failure that would only appear in-pod.
- **The task numbering drifted the moment JXP inserted a task**, and Prompt 4
  already pointed at the wrong one ("Prompt 3 Task 3's seam" now means the
  emulator work, not the SHA seam). Cross-references between prompt docs are
  fragile in exactly this way; I fixed the pointer and said why inline rather
  than silently renumbering.
- **I checked `git status` rather than assuming my changes were uncommitted.**
  They had been committed between sessions — `e1f4289` "off nadir" — which
  changed two of the five SHAs I was about to write into the doc. Had I copied
  the values from my earlier report, Prompt 4 would have baked a stale
  `retrieve-or-bust` SHA into the image label, and the provenance would have
  pointed at the commit *without* the emulator fix, which is precisely the
  thing the SHA exists to disambiguate.
- Carrying the open Q2 forward as Prompt 4 Q1 mattered more than it looked: it
  is a science question in Prompt 3, but in Prompt 4 it becomes a *sequencing*
  constraint, because the image freezes the configuration. Same question,
  different consequence, and worth restating in the place where the cost lands.
