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

3. **Provenance + identity.** **The schema half is already done** —
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

4. **Fitted-physics everywhere.** `_fit_diagnostics` (χ²/AIC/BIC) and
   `pab/plotting/fit_fig.py` dispatch on `rt_backend`: robust →
   `calc_Rrs_from_models_robust(..., geom=, Bp=)` with the geometry read
   back from the DB; Gordon → unchanged. `pab.parallel.init_worker` pins
   XLA's CPU threads (`XLA_FLAGS=--xla_cpu_multi_thread_eigen=false
   intra_op_parallelism_threads=1`) next to the BLAS caps. Tests (the fit
   figure for a robust fit uses the robust reconstruction — assert via a
   mocked `calc_Rrs_from_models_robust`). Log.

5. **Real end-to-end check (workstation).** On a **scratch copy** of
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

6. **Update.** Based on what you have done, update the prompt doc
   `build_v2_prompt_4.md`, as needed. Log.
   *(Added 2026-09-15, mirroring the Task 5 JXP added to
   `build_v2_prompt_1.md`, so each prompt hands its findings to the next.
   Delete it if that is not the intent.)*

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
