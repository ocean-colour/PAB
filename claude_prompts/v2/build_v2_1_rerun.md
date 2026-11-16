# Build v2.1: re-fit with the nadir/zenith-normalized geometry

## Goals

Re-fit every v2 BING matchup with the forward model evaluated at the geometry
that the PACE L2 AOP `Rrs` is **actually normalized to**:
**(θ_s, θ_v, Δφ) = (0, 0, 0)**, with the inelastic (Raman and Chl
fluorescence) `Ed` taken at θ_s = 0. The result is stamped
**`pab_version = "2.1"`**.

Why. NASA's l2gen runs with `brdf_opt = 7` (Morel f/Q plus Fresnel on the
sensor and solar paths), so the distributed `Rrs` is an exact-normalized
reflectance for a zenith sun and a nadir view. v2.0 and v2.0.1 instead passed
each pixel's *observed* L1B angles to `robust_hybrid`. Measured on 300 real v2
pixel geometries, the forward model then predicts a median of about 5–10 %
more `Rrs` for the same IOPs. The 5–95 % range is roughly 0.93–1.29, and the
error is correlated with geometry. The expected result of the fix is
`b_bp(700)` higher by about 5–10 % on median, plus the removal of a ±15 %
geometry-driven scatter. A side benefit: (0, 0, 0) lies **inside** the
emulator's trained domain (`cos_theta_s ∈ [0.5, 1]`,
`cos_theta_v = cos_dphi = 1`), so the "hybrid applied off-nadir, never
validated" caveat goes away.

Source of the decision: `papers/bbp/prompts/analysis.md`, under Q&A /
Viewing angle (findings 1–5; JXP's answers Q1 = fit at (0, 0, 0), Q2 =
θ_s = 0 for the inelastic terms) and Q&A / Raman correction. The second
established that the AOP `Rrs` is **not** Raman-corrected, so keeping BING's
Raman term on is correct.

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
- **Explicit `--db` every time**: `$PAB_DATA_DIR/v2/pab.db`. Set
  **`PAB_DATA_DIR=$PAB_DATA_DIR/v2`** for any command that writes chains, or
  they land in the root `fit_chains/` (lesson from Prompt 1).
- **`v1/pab.db` is frozen.** It is `chmod a-w`, sha `09de0a6d…f978273`.
  Open it only read-only (`create=False` or a read-only URI `ATTACH`).
- **Never modify the 2.0 or 2.0.1 rows.** 2.1 adds new rows (`fit_id …_v2.1`)
  under the design's provenance rule. Before any write to the live v2 DB,
  make a dated, sha-verified copy (the O6 discipline:
  `v2/pab_pre_v21_<date>.db`), and record row counts and checksums of the
  2.0 and 2.0.1 `fits` / `fit_results` before and after.
- **Safety run first, on a scratch DB copy.** Do a `--dry-run`, then a
  2-matchup real fit, before touching the live DB (the O6 pattern).
- **Confirm outward-facing steps with JXP** before running them: S3 uploads,
  `AIOcean` backups, Nautilus jobs, and anything published.
- `PYTHONWARNINGS=ignore` for fit runs (robust's `DomainWarning` spam). At
  (0, 0, 0) the view-geometry breach disappears, but the `B_p` breach remains
  on most fits.
- **Questions go in the Q&A section of this file**, never chat-only.

## Context

Read before Task 1:

- `papers/bbp/prompts/analysis.md`: Q&A / Viewing angle and Q&A / Raman
  correction, the physics and the evidence.
- `HOWTO.md`: §3 (the fit stage, `--matchups-csv`, `--replay-chains`) and
  §5b (how the 2.0.1 re-fit was run and published).
- `claude_prompts/v2/run_full_inelastic.md`: the v2 plan (two-DB layout,
  provenance rules, gate pattern).
- `claude_prompts/v2/report_improvements.md`: Outliers O5–O9, covering the
  2.0.1 configuration, the replay seam, the patch overlay, and the site
  rebuild and publish. 2.1 reuses most of that machinery.
- `versions/v2/high_bbp_outliers.md`, Appendix C: the replay re-fit as
  actually executed (commands, timings, checks).
- `versions/v2/ztt_slice.md`: the emulator domain and why the hybrid was
  never valid off-nadir.

### Code seams (verified 2026-11-14)

| What | Where | Note |
|---|---|---|
| Fit-time geometry | `pab/fit/run.py:212` `obs_geometry(theta_s, theta_v, dphi)` | builds `ObsGeometry` from the stored L1B angles |
| Gathered angles | `pab/fit/run.py:~782` (`_gather_fit_input`), `:~797` `_geometry_or_none` | reads `matchup_pixels.theta_s/theta_v/dphi` |
| Strict no-geometry skip (R3) | `pab/fit/run.py:~1011` | `requires_geometry(config)` is true for every robust backend |
| Inelastic `Ed` | `pab/fit/run.py:234` `set_inelastic_Ed(models, geom, rt_dict)` → `robust.rt.ed.Ed(geom.theta_s, …)` | L23 anchors 0/30/60°, so **θ_s = 0 is an anchor and needs no interpolation** |
| Diagnostics | `pab/fit/run.py:700` `_fit_diagnostics(…, geom=)` | χ²/AIC/BIC with the robust forward model |
| Figure reconstruction | `pab/plotting/fit_fig.py:62` `_geometry_from_row` → `obs_geometry` | **reads the pixel angles back**, so it must learn the fit's geometry mode or 2.1 figures will be drawn at the wrong geometry |
| Config | `pab/fit/models.py` `FitConfig` (+ `.v1()`, `.v2_0()`) | 2.0.1 ceilings are the current defaults |
| Replay | `pab/fit/replay.py` `spectrum_from_chains(root, version="2.0")` | bit-identical 2.0 input spectrum, no granule opened |
| Patch overlay | `pab/metrics/compare.py` `version_family` / `overlay_patch` | `"2.1"` is a **base** version, not a patch: the newest family becomes `("2.1", [])` |
| Version stamp | `pab/config.py` `pab_version = "2.0.1"`; `setup.py` `2.0.1` | |

### Measured facts this prompt starts from

- **v2 DB** (`$PAB_DATA_DIR/v2/pab.db`, schema v5): 15,976 matchups;
  **15,971 BING 2.0** fits (15,827 LM `success`), **51 BING 2.0.1**
  re-fits, 15,976 NASA_GIOP 1.1. All AOP granules are **V3_2**, which is
  after NASA's fix of the cross-scan BRDF azimuth bug (V3 release notes).
  Five matchups have no 2.0 fit, and 50 pixels have no geometry.
- **Chains**: `$PAB_DATA_DIR/v2/fit_chains/` holds all **15,971 `_v2.0.npz`**
  and **51 `_v2.0.1.npz`** files (19 GB). Every 2.0 fit is replayable on the
  workstation.
- **2.0 fit config**: 400–700 nm, 10k steps / 1k burn / 16 walkers, free
  `B_p` [0.004, 0.05], `phi_C = 0.02`, Raman + Chl-fl on, CDOM-fl off.
- **Cost**: the 2.0.1 replay ran at a **median 198 s CPU/fit** on the
  workstation (`--jobs 8`, O6). The workstation has **24 cores and 755 GB
  RAM**. 15,971 × ~200–250 s ÷ 20 workers ≈ **45–55 h** wall time.
- **Expected direction** (analysis.md, Viewing-angle finding 3; ZTT and
  hybrid, synthetic IOPs): `Rrs(obs)/Rrs(0,0,0)` has a median of 1.06–1.12
  at 440 nm and 1.03–1.10 at 700 nm, so **expect `bbp700(2.1)/bbp700(2.0)`
  ≈ 1.05–1.10 on median**, rising with θ_v and θ_s. A ratio *below* 1 on
  median would mean something other than geometry is acting. Stop and look.
- Test baseline at 2.0.1: **494 passed, 1 skipped**; `ruff check pab` clean.

## Prompts

1. Read this file. JXP has answered the questions in Q&A / Round 1. Fold the
   answers into the Plan, then execute **Task 1**. 
   Use Opus 5.5. Log your work.
1. Read my answer to T1-Q1 and modify the plan accordingly.
   Use Opus 5.5. Log your work.
1. Execute **Task 2** (the slice and the gate). Stop for JXP's review. Use
   Opus 5.5. Log your work.
1. JXP has reviewed the slice. Execute **Task 3** (the full re-fit). Use
   Opus 5.5. Log your work.
1. Execute **Task 4** (figures, report, write-up). Use Opus 5.5. Log your
   work.
1. Execute **Task 5** (publish, backup, close-out). Use Opus 5.5. Log your
   work.

## Plan

*Drafted 2026-11-14; revised the same day with JXP's Round 1 answers. Every
answer took the recommendation except **V6 = B: the full re-fit runs on
Nautilus**, because the workstation's cores are needed by other projects.
§3, §4 and §6 and Tasks 2–5 are rewritten for that. Decisions in force:
V1 = A (live v2 DB, new `_v2.1` rows), V2 = replay, V3 = the 15,971 with a
2.0 NPZ (the 5 without are listed in the write-up), V4 = `fits.geom_mode`,
V5 = no R3 refusal under `"normalized"`, V6 = **Nautilus**, V7 = (a)–(c),
V8 = A, V9 = re-render all fit figures, V10 = in place under `v2/`,
V11 = keep `"warn"`, V12 = as stated.*

### 1. What changes, and what does not

| | 2.0.1 (current) | **2.1** |
|---|---|---|
| Forward-model geometry | observed L1B (θ_s, θ_v, Δφ) per pixel | **(0, 0, 0)** for every pixel |
| Inelastic `Ed` | L23 `Ed(θ_s observed)` | **L23 `Ed(0°)`** |
| Spectrum | 2.0 granule read (2.0.1: replayed) | **replayed from the 2.0 chain NPZ** (V2) |
| Priors | ceilings 0.1 / 10 / 10 m⁻¹ | same (the 2.0.1 default) |
| Backend / inelastic / window / MCMC | `robust_hybrid`, Raman + Chl-fl, 400–700, 10k/1k/16, free `B_p` | **unchanged** |
| `on_out_of_domain` | `"warn"` | `"warn"` (V11) |
| L1B angles on `matchup_pixels` | used by the fit | **kept as metadata and QA** (glint, θ_v cuts), not used by the fit |

So 2.0.1 → 2.1 differs by the geometry and its `Ed`, and by nothing else.
The 15,920 non-runaway fits also pick up the ceilings, but O6 showed that
the ceilings never bind a physical posterior.

### 2. Code (Task 1)

| # | Change | Where |
|---|---|---|
| a | `FitConfig.geometry_mode: str = "normalized"`, with values `"observed"` / `"normalized"`. `FitConfig.v2_0()` and `FitConfig.v1()` pin `"observed"` (v1 is moot under Gordon). Add **`FitConfig.v2_0_1()`** (ceilings + `"observed"`) so every published release has a frozen constructor. | `pab/fit/models.py` |
| b | A single resolver, `fit_geometry(config, theta_s, theta_v, dphi)`. It returns `ObsGeometry(0, 0, 0)` under `"normalized"` and `obs_geometry(...)` under `"observed"`. Use it in `_geometry_or_none`, the fit path, `_fit_diagnostics`, and `set_inelastic_Ed` (automatic, since that reads `geom.theta_s`). | `pab/fit/run.py` |
| c | **Provenance, schema v6**: `fits.geom_mode TEXT`. `'observed'` / `'normalized'`; NULL on legacy rows means observed for robust fits (the forward migration pattern of v2–v5). `_config_from_row` reads it back. (V4) | `pab/db/schema.py`, `pab/fit/run.py` |
| d | **Reconstruction**: `fit_fig._geometry_from_row` and `reconstruct_fit` dispatch on the row's `geom_mode`, so a 2.1 figure is drawn at (0, 0, 0) and a 2.0 figure is still drawn at its observed angles. | `pab/plotting/fit_fig.py` |
| e | **R3 under `"normalized"`** (V5): the geometry is fixed by the product definition, so a pixel without L1B angles is **not** refused. `requires_geometry` splits into "the backend needs an `ObsGeometry`" (still true) and "the pixel needs L1B angles" (only under `"observed"`). | `pab/fit/run.py` |
| f | `pab_version = "2.1"` with a docstring entry; `setup.py` → `2.1.0`. `make_fit_id` already appends `_v2.1`. | `pab/config.py`, `setup.py` |
| g | **Report**: confirm that `version_family` makes 2.1 the headline on the v2 DB, `("2.1", [])`, and that `--compare-db v1` now yields a 1.0-vs-2.1 section. Fix any hard-coded "2.0" wording the rebuild exposes. Optional per V8: a 2.0-vs-2.1 comparison. | `pab/metrics/compare.py`, `pab/report/rst.py` |
| h | **Tests**: the resolver (normalized → (0,0,0); observed → passthrough); `Ed` called at 0°; the v6 migration on a v5 copy; `geom_mode` round-trip into `reconstruct_fit`; the frozen constructors; the normalized-mode fit of a pixel with NULL angles is not refused; a toy robust fit under `importorskip("robust")`. `ruff` clean. | `pab/tests/` |
| i | Docs: `HOWTO.md` (§3 fit defaults; a new §5c on the 2.1 re-fit), `docs/` schema page (v6 column), and a note in BING's `robust_hybrid` docstring that PAB now evaluates it at nadir (the old off-nadir caveat is moot for PAB). | docs |

**End-of-task check** (no DB writes): re-fit ~5 cached matchups
under `FitConfig()` (2.1) and `FitConfig.v2_0_1()` on a scratch DB, and
confirm three things: the 2.1 forward model is called with (0, 0, 0); the
2.0.1 config reproduces the stored 2.0.1/2.0 posteriors to MCMC noise; and
the `bbp700` ratio has the expected sign.

### 3. The gate (Task 2): a geometry-stratified slice, on Nautilus

- **Selection** (V7): **200 matchups**, stratified 50 per θ_v band (<25°,
  25–35°, 35–45°, >45°) and spread across basins and seasons. Include the
  50 of `ztt_slice` (re-used for comparability) and ~10 of the 51 2.0.1
  re-fits. Write the selection to `versions/v2.1/slice_200.csv`.
- **Image.** Build `pab:2.1.0` from the Task 1 tree with
  `nautilus/build_image.sh` (`TAG=2.1.0`), with `PAB_GIT_SHAS` baked in and
  checked against the commit JXP makes. Confirm with JXP before `--push`.
  The slice is the image's first real use, so the image is validated before
  the 2-day run depends on it.
- **Run** on Nautilus (V6 = B), DB-local in the pod: a **scratch copy** of
  the v2 DB (`/data/v2.1_slice/pab.db`, never `/data/v2/pab.db`),
  `--matchups-csv slice_200.csv`, `--replay-chains /data/v2/fit_chains`,
  `PAB_DATA_DIR=/data/v2.1_slice` (so slice chains never mix with the
  production ones), `--jobs 50`, `PYTHONWARNINGS=ignore`. The job spec is
  `nautilus/v21_slice_job.yaml`, modelled on `v2_fit_slice_job.yaml`. Measure
  s/fit from the `fit progress` lines, never from total wall time (the
  ~11 min one-time JAX compile per pool). Pull the slice DB back to the
  workstation for the analysis.
- **The fixed-`B_p` arm** (T1-Q1 = add it). It tells a geometry effect on
  `b_bp` apart from a free `B_p` absorbing it.
  - *Selection*: **50 of the 200**, `versions/v2.1/bp_arm_50.csv`, 12–13
    per θ_v band, spread in θ_s. Prefer `ztt_slice` members, take only
    `success = 1` 2.0 fits, and **exclude the 2.0.1 re-fits**, whose
    pathological spectra and floor-pinned `B_p` would confound the
    comparison.
  - *Two passes on the same 50*, both on the replayed 2.0 spectrum, both
    with `fit_Bp=False` and **`Bp_value = 0.014`**. 0.014 is the value
    analysis.md Viewing-angle finding 3 computed its 1.05–1.10 prediction
    at (T1-Q1 proposed 0.012; 0.014 makes the arm directly comparable) and
    lies inside the emulator's trained `B_p` range [0.0103, 0.018].
    - **arm-N**: `FitConfig(fit_Bp=False, Bp_value=0.014)`, i.e. normalized.
    - **arm-O**: `FitConfig.v2_0_1(fit_Bp=False, Bp_value=0.014)`, i.e.
      observed.
    The pair differs by the geometry only.
  - *Mechanics*: arm-N, arm-O and the main slice would all mint the same
    `…_v2.1` `fit_id`, so each pass gets its **own DB copy and its own
    `PAB_DATA_DIR`** (chains would otherwise overwrite each other by
    filename): `/data/v2.1_slice/{main,arm_norm,arm_obs}/`.
    `fits.geom_mode` and `fits.fit_bp` tell the rows apart. The `pab` CLI
    exposes no `FitConfig` fields, and the production CLI stays as it is,
    so the arm runs through a small driver,
    **`nautilus/v21_bp_arm.py`** (`--db`, `--matchups-csv`,
    `--replay-chains`, `--geometry-mode`, `--bp`, `--jobs`). It sets
    `PAB_DATA_DIR` before importing `pab` and calls `run.build_fits(…,
    selection=, spectra=spectrum_from_chains(…))`, the same path as the CLI.
  - *Cost*: 100 five-parameter fits. The two arm passes run concurrently
    in the slice pod after the main pass, `--jobs 25` each, about one
    round of fits plus the ~11 min JAX compile per pool, so **≈ 1 pod-hour**
    on top of the slice.
- **Before the pod**: a local safety run on the workstation: a `--dry-run`;
  2 matchups with `--jobs 2` through the CLI on a scratch copy; and the same
  2 matchups through `v21_bp_arm.py` in both geometry modes, each on its own
  scratch copy. Check `geom_mode` / `fit_bp` / `Bp` on the written rows.
  That is the only local compute.
- **Report** in `versions/v2.1/geometry_rerun.md` (new):
  - The `bbp700(2.1)/bbp700(2.0 or 2.0.1)` distribution, overall and per
    θ_v band, against θ_s, and against the analysis.md prediction.
  - The same for `a_ph(440)`, Chl, `A_dg` and `B_p`. **`B_p(2.1)` against
    `B_p(2.0)` per θ_v band is a first-class gate quantity** (T1-Q1),
    including the fraction at each prior bound in both versions.
  - **The fixed-`B_p` arm**:
    - `R_fix = bbp700(arm-N)/bbp700(arm-O)`, overall, per θ_v band and
      against θ_s / θ_v.
    - Compared with the analysis.md 1.05–1.10, and **per pixel** with the
      forward-model prediction `Rrs₇₀₀(observed)/Rrs₇₀₀(0,0,0)` evaluated at
      that pixel's arm-O posterior-median IOPs and `B_p = 0.014`. This costs
      no fit, and the predicted-against-measured scatter is the direct test.
    - Beside it, `R_free = bbp700(2.1)/bbp700(2.0)` and the `B_p` shift on
      the **same 50** from the main slice, plus χ²_red fixed against free.
    - Read together they give one of three outcomes:
      - **(a) compensation**: `R_fix` ≈ prediction, `R_free` ≈ 1, `B_p`
        falls. The geometry effect is real but goes into `B_p`.
      - **(b) the prediction does not survive a fit**: `R_fix` ≈ 1. Another
        parameter (`A_dg`, `β`) absorbs it, or the red-band linearity
        argument fails. Look further before Task 3.
      - **(c) noise**: `R_fix` ≈ `R_free` ≈ prediction. The Task 1 n = 5 was
        MCMC noise.
    - Each outcome gets its own recommendation in Round 2. (a) in particular
      raises the question of whether 2.1 should still fit `B_p` free.
  - χ²_red and acceptance against 2.0.
  - The `DomainWarning` breach mix (the view features should be gone).
  - LM `success` rate and failures.
  - Against the float, a quick look at whether δ = (PACE − Argo)/PACE moves
    as predicted.
- **Pause triggers** (V7): median `bbp700` ratio outside **[0.98, 1.20]**;
  failure rate > 2 %; median s/fit > 300 s; or any χ² or acceptance change
  JXP finds implausible. **Stop for JXP's review in every case.** The arm adds
  no numeric trigger. Its outcome (a)/(b)/(c) is read alongside the
  `bbp700` trigger: a main-slice median below 0.98 under outcome (a) is
  explained, under (b) it is not.

### 4. The full re-fit (Task 3), on Nautilus

- Where (V6 = B): **Nautilus**, job `nautilus/v21_fit_job.yaml` (from
  `v2_fit_job.yaml`): image `pab:2.1.0` (the one the slice validated),
  50 CPU / 100 Gi, `--jobs 50`, DB-local in `emptyDir` with the 2-minute
  `sqlite3.backup()` checkpoint back to CephFS (never `backup()` onto
  CephFS), `PAB_DATA_DIR=/data/v2` so the 2.1 chains land beside the 2.0
  ones in `/data/v2/fit_chains/`, `--replay-chains /data/v2/fit_chains`,
  `PYTHONWARNINGS=ignore`, `MALLOC_ARENA_MAX=2`, `backoffLimit` for
  preemption. 15,971 × ~200 s ÷ 50 ≈ **18 h** of fitting, plus the compile.
- **Staging.** The PVC copy of the v2 DB must be the **live** one: push the
  workstation `v2/pab.db` (after the dated copy, below) to `/data/v2/pab.db`
  and check the sha on both sides. Check that `/data/v2/fit_chains/` still
  holds all 15,971 `_v2.0.npz` (and the 51 `_v2.0.1.npz`); any missing NPZ
  is staged from the workstation first.
- **Custody.** While the pod runs, the PVC DB is the master: **no writes to
  the workstation v2 DB** until it is brought back. After the run: pull the
  DB back (sha on both sides), and rsync the ~15,971 new `_v2.1.npz` chains
  (~18 GB) into `$PAB_DATA_DIR/v2/fit_chains/`, verifying the count.
- Selection: the **15,971 matchups with a 2.0 NPZ** (V3), via
  `--matchups-csv versions/v2.1/refit_all.csv`. This guards against a
  silent all-matchup run.
- Idempotent and resumable (keyed on the `_v2.1` `fit_id`). A crash
  resumes where it left off.
- Before: a dated DB copy (`v2/pab_pre_v21_<date>.db`, sha-verified),
  counts and checksums of the 2.0 and 2.0.1 `fits` / `fit_results`. After
  (on the workstation, on the returned DB): 2.0 and 2.0.1 rows
  byte-identical; `integrity_check`; schema v6; 15,971 rows at 2.1 (minus
  failures, listed), all `geom_mode = 'normalized'`.

### 5. Figures, report, write-up (Task 4)

- `--stage figure --figure-version 2.1` for every 2.1 fit (V9), on
  **Nautilus** as well (the chains are there; ~9 h at 16 workers on the
  workstation was the old estimate, so a pod is the better fit here too),
  with the figures `rclone copy`'d back as in 2.0.1. Scenes are untouched;
  the v1 scene paths still apply.
- Rebuild `report_site/` with 2.1 as the headline and
  `--compare-db $PAB_DATA_DIR/v1/pab.db`.
- Finish `versions/v2.1/geometry_rerun.md` with the full-population numbers.
  Flag for the paper that the bias numbers in
  `papers/bbp/bias_discussion_draft.md` were computed on 2.0 or 2.0.1 and
  must be refreshed from 2.1 (that refresh is a separate paper prompt, not
  this doc).

### 6. Publish and close-out (Task 5); each step confirmed with JXP

- `s3://pab/v2/pab.db` and `v2/matchup_summary.*` updated in place (V10).
  The DB is the same file with more rows.
- Dated backup to `AIOcean:PAB/pab_v2_<date>.db`.
- Verify that the v1 sha is unchanged.
- JXP pushes `report_site/` (RTD).
- Close-out log entries here and in HOWTO §5c.

*(V6 = B made Nautilus the primary path; the old fallback paragraph is folded
into §3 and §4.)*

## Tasks

### Task 1: code, tests, local check

Implement Plan §2 a–i in the order f → a → b → e → c → d → g → h → i. Run
`pytest pab/tests -q` and `ruff check pab`, and report the new baseline. Then
do the §2 end-of-task check on a **scratch** DB copy with
`PAB_DATA_DIR` set to scratch. Report the measured `bbp700` ratios for those
matchups. No writes to the live v2 DB.

### Task 2: the slice and the gate (STOP for review)

Build `versions/v2.1/slice_200.csv` and `versions/v2.1/bp_arm_50.csv` per
Plan §3. Write `nautilus/v21_bp_arm.py` (with a unit test of its config
construction). Do the local safety run: a dry run, 2 matchups through the
CLI, and the same 2 through the arm driver in both modes, each on its own
scratch copy. Write `nautilus/v21_slice_job.yaml`: the main pass, then
arm-N and arm-O concurrently, each on its own DB copy and `PAB_DATA_DIR`
under `/data/v2.1_slice/`. Build `pab:2.1.0` and, **after JXP confirms**,
push it and apply the slice job (`--replay-chains /data/v2/fit_chains`).
Pull the three slice DBs back. Write the §3 report, arm included, into
`versions/v2.1/geometry_rerun.md` with figures in `versions/v2.1/`. Put the
go/no-go recommendation, the arm outcome (a)/(b)/(c) and any new questions
in Q&A / Round 2. **Do not start Task 3.**

### Task 3: the full re-fit (Nautilus)

After JXP's go: on the workstation, the pre-flight (counts, checksums of
the 2.0 / 2.0.1 rows, `integrity_check`) and the dated, sha-verified copy
`v2/pab_pre_v21_<date>.db`. Then, each step confirmed with JXP: stage the
live DB to `/data/v2/pab.db` (sha both sides), verify the 2.0 NPZs on the
PVC, apply `nautilus/v21_fit_job.yaml` with
`--matchups-csv versions/v2.1/refit_all.csv`. Monitor the progress lines
(s/fit, failures, `mem_breakdown`). When it finishes: pull the DB back (sha),
rsync the `_v2.1` chains, then verify on the workstation per Plan §4 and
list any failures with their reasons. Re-try failures once (a second apply
resumes on `fit_id`), and leave the rest listed for JXP.

### Task 4: figures, report, write-up

Plan §5. Render the 2.1 fit figures on Nautilus (confirm with JXP before
applying) and bring them back. Rebuild the site locally and check it renders
(summary headline reads 2.1; the comparison section is 1.0 vs 2.1; the 2.1
fit figures link correctly; the V8 = A sentence + link to
`geometry_rerun.md` on the summary page; any remaining hard-coded 2.0
narrative is revised). Complete `versions/v2.1/geometry_rerun.md`.

### Task 5: publish, backup, close-out

Plan §6, each outward step confirmed with JXP first. Update `HOWTO.md` §5c
and `docs/`, and log.

## Q&A

### Round 1

*Answer inline under each **Your answer:**. Each question carries my
recommendation, and the Plan assumes it.*

**V1: Which database holds the 2.1 fits?**
- **A (recommended).** The live **v2 DB**, as new rows (`fit_id …_v2.1`),
  exactly as 2.0.1 was added. It has the same matchups, pixels and NASA-GIOP
  rows, and the report's `version_family` then picks 2.1 as the headline
  with no new plumbing. 2.0 and 2.0.1 stay untouched beside it.
- **B.** A new `v2.1/pab.db` split from v2 (a third DB, a new S3 prefix,
  and `--compare-db` plumbing for 2.0-vs-2.1).

**Your answer:** Use A.

**V2: Spectrum source.** Replay each pixel's spectrum from its **2.0 chain
NPZ** (`--replay-chains`, the 2.0.1 seam), so 2.0 → 2.1 differs only by
geometry. The alternative is to re-read the granules, which picks up any
NASA reprocessing since the 2.0 run, costs ~25 GB+ of downloads, and
confounds the comparison. *(My recommendation: replay.)*

**Your answer:** Replay

**V3: Scope.** Re-fit the **15,971 matchups that have a 2.0 fit**. The 51
runaways are included: they replay their 2.0 spectrum under the 2.1 config,
which keeps the ceilings, so they do not run away again. The **5 matchups
with no 2.0 fit** have no NPZ to replay. Under `"normalized"` geometry they
*could* be fitted from the granule, since L1B angles are no longer needed,
but that means a granule download and a mixed `rrs_source`. Leave them out
of 2.1? *(My recommendation: leave them out and list them in the write-up.)*

**Your answer:** Leave them out and list them in the write-up.

**V4: Provenance of the geometry.** Add **`fits.geom_mode`** (schema v6;
`'observed'` / `'normalized'`; NULL on legacy rows means observed). Without
it, the only record that a fit used (0, 0, 0) is the version number, and
`reconstruct_fit` / `fit_fig` would have to infer physics from a version
string. The alternative is to imply it from `pab_version >= 2.1`, with no
migration. *(My recommendation: the explicit column.)*

**Your answer:** Agreed, add the column.

**V5: R3 (strict "no geometry → no fit") under the normalized mode.** R3
existed so that θ_s was never *assumed*. Under `"normalized"`, the geometry
is fixed by NASA's product definition, not assumed. Proposal: in
`"normalized"` mode a pixel without L1B angles is **not** refused. The
`geometry` stage keeps running for new matchups, as QA metadata. In
`"observed"` mode, R3 stays exactly as it is. *(My recommendation: yes. It
doesn't affect this run, where every replayed pixel has angles, but it
matters for future granule fits.)*

**Your answer:** Yes, I agree

**V6: Where does the full re-fit run?**
- **A (recommended).** The **workstation**: 24 cores, `--jobs 20`, ~45–55 h,
  in the background with a tee'd log. No image rebuild, no PVC staging, no
  DB round-trip; the chains and DB are already local.
- **B.** **Nautilus**: ~50 workers, ~20 h of fitting, plus a `pab:2.1.0`
  image build, DB staging, the DB-local wrapper, and bringing the DB and
  ~18 GB of new chains back.

**Your answer:**  I am using this workstation for a number of other projects
that need many of those procesors.  Let's use Nautilus.  Rewrite the Tasks
accordingly.

**V7: The gate.**
- (a) A **200-matchup** slice stratified by θ_v band (50 each), including the
  `ztt_slice` 50 and ~10 of the 2.0.1 re-fits.
- (b) Pause triggers: median `bbp700(2.1)/bbp700(2.0)` outside
  **[0.98, 1.20]**; failures > 2 %; median s/fit > 300 s; or any χ² or
  acceptance change you find implausible.
- (c) You review before Task 3 in every case.

*(My recommendation: (a)–(c) as written.)*

**Your answer:** Ok, go with (a)-(c)

**V8: Report presentation.** On the v2 DB, 2.1 becomes the site's headline
automatically, and the existing comparison section becomes **1.0 vs 2.1**
via `--compare-db`.
- **A (recommended).** The 2.0-vs-2.1 change is documented in
  `versions/v2.1/geometry_rerun.md`, with one sentence and a link on the
  report's summary page. No new report code.
- **B.** A second comparison section in the report (2.0 vs 2.1, same DB),
  which needs a version-pair gatherer inside one store.
- **C.** Swap the comparison section to 2.0 vs 2.1 and drop 1.0 vs 2.x.

**Your answer:** Use A.

**V9: Figures.** Re-render the **fit figures for all ~15,971 2.1 fits**.
They encode the fitted physics, and the gallery and tap-through would
otherwise show 2.0 fits. The earlier estimate was ~9 h at 16 workers. Scenes
stay as they are, still the v1 ones per R7. *(My recommendation: yes.)*

**Your answer:** Yes, I agree

**V10: Publishing.** Update `s3://pab/v2/pab.db` and `v2/matchup_summary.*`
**in place** (the same DB, with 2.1 rows added), plus a dated `AIOcean`
backup and the RTD site rebuild. The alternative is a new `s3://pab/v2.1/`
prefix. *(My recommendation: in place under `v2/`, consistent with V1 = A
and with how 2.0.1 was published.)*

**Your answer:** Ok, in place is fine

**V11: `on_out_of_domain`.** At (0, 0, 0) the view-geometry breach that
made `"ztt"` mean "pure ZTT everywhere" (O8) disappears. The `B_p` breach
remains: 86 % of 2.0 posterior medians lie outside the emulator's trained
`B_p` range [0.0103, 0.018]. Keep **`"warn"`**, i.e. the hybrid everywhere,
as in 2.0 (Q&A/Outliers 12 = A), so 2.0 → 2.1 isolates the geometry. The
alternative is to revisit the policy now. *(My recommendation: keep
`"warn"`. Retraining the emulator over the `B_p` prior range is the real fix
and belongs to the RoB repo.)*

**Your answer:** Keep "warn"

**V12: Version naming.** Use `pab_version = "2.1"` (fit ids `…_v2.1`),
package `2.1.0`, and add `FitConfig.v2_0_1()` as a frozen constructor
alongside `.v1()` / `.v2_0()`. It is a minor bump, not a patch, because the
physics changes for every fit, so it is a new **base** version and not an
overlay on 2.0. *(My recommendation: as stated.)*

**Your answer:** Agreed, as stated.

### Round 1b (from the Task 1 check, 2026-11-14)

**T1-Q1: the free `B_p` absorbs part of the geometry change.** In the Task 1
check (5 matchups, θ_v 22–53°; `versions/v2.1/task1_check.json`) the 2.1
`bbp700` against the same-spectrum 2.0.1 re-run is ×0.99, ×1.26, ×0.85,
×0.85, ×0.99 (median **0.99**). The prediction is 1.05–1.10. `B_p`, though,
moves in the same direction on 4 of 5: from 0.016–0.023 to **0.012–0.015**,
which is inside the emulator's trained range [0.0103, 0.018]. The fifth
(the 2.0.1 re-fit, `B_p` at the 0.004 floor) goes the other way, to 0.020.
χ²_red is slightly worse under 2.1 on 3 of 5 (0.87→0.94, 0.45→0.63,
0.37→0.45). `B_p` sets the angular shape (f/Q), so with `B_p` free the fit
can trade the geometry term against `B_p` instead of against `b_bp`. The
analysis.md prediction was made at fixed IOPs and fixed `B_p`. Five fits are
MCMC-noise-dominated and settle nothing, but this is exactly what the
"ratio < 1, stop and look" trigger is for. Proposal for Task 2: report
`B_p(2.1)` against `B_p(2.0)` per θ_v band as a first-class gate quantity,
and add a **50-matchup fixed-`B_p` arm** (`fit_Bp=False`,
`Bp_value = 0.012`, both geometries; about 100 extra fits) to separate
geometry from `B_p` compensation. The alternative is to read the 200-fit
slice as planned and decide afterwards. *(My recommendation: add the arm. It
costs ~1 pod-hour and is the only way to tell the two effects apart.)*

**Your answer:** Ok, add the arm.

*Folded into Plan §3 and Task 2 (2026-11-14). The fixed value is 0.014, not
0.012: 0.014 is the value the analysis.md prediction used, so the arm tests
it directly. It is still inside the emulator range.*

### Round 2a (Task 2, before the pod; 2026-11-14)

Everything local for Task 2 is done and passed: the selections, the arm
driver, the safety run, the job spec and the analysis script (see the log).
The next three steps are outward-facing, so they need your go.

**T2-Q1: commit the bing docstring, then build and push `pab:2.1.0`?**
`nautilus/build_image.sh` stages the **working trees** but bakes the
**HEAD** SHAs into `PAB_GIT_SHAS`. PAB HEAD is `6563a65`. The PAB working
tree differs only in non-runtime files (`versions/v2.1/analyze_slice.py`,
which is new, and a ruff import-order fix in `task1_check.py`). **bing** has
the uncommitted Task 1 docstring edit in `bing/rt/defs.py`. It is
docstring-only, but an image built now would carry it under the SHA
`bf56f6d`. Proposal: you commit bing (and, optionally, the two PAB files),
then I run `TAG=2.1.0 bash nautilus/build_image.sh --push`. Note that the
script also retags and pushes **`:latest`**. Every job spec pins an
explicit tag, so nothing should move with it. The Dockerfile's
self-check now asserts `pab 2.1.0`, `geometry_mode = 'normalized'`,
schema 6, `fit_geometry(…) == (0, 0, 0)`, and the arm driver present in the
image.

**Your answer:**  I have committed the bing docstring.  Do build and push pab:2.1.0

**T2-Q2: apply `nautilus/v21_slice_job.yaml`?** It is one pod, 50 CPU and
100 Gi, with an 8 h deadline against an expected ~1.5 h. It runs the main
200 (`--jobs 50`), then arm-N and arm-O concurrently (`--jobs 25` each).
Each pass gets its own copy of `/data/v2/pab.db` (only `cp`'d; its sha is
logged before and after) and writes only under `/data/v2.1_slice/`.
`/data/v2/fit_chains` is read for the replay, and the job logs how many of
the 200 NPZs are present before it fits. One thing to check in the log: the
PVC `/data/v2/pab.db` sha against the workstation's `9503015b…`. If the PVC
copy predates the 2.0.1 re-fit, the slice is still valid, because pixels and
2.0 spectra are unchanged and the 2.0 / 2.0.1 reference values are read from
the workstation DB in the analysis. I will flag any mismatch either way.

**Your answer:** Yes, I confirm you can apply that job

### Round 2 (the slice gate; 2026-11-15)

The full write-up is `versions/v2.1/geometry_rerun.md`. In short:
- 200/200 fitted, 0 failed, 244 s/fit.
- Median `bbp700` ratio **1.212**, just over the 1.20 trigger. Reweighted
  to the population's θ_s it is 1.14.
- The arm says the geometry effect is real and predicted per pixel
  (ρ = 0.86). `b_bp` responds with elasticity ≈ 2 to the `Rrs` change.
- The free `B_p` adds +6 % rather than compensating. Task 1's 0.99 was a
  low-θ_s sample.

**R2-Q1: go for Task 3?** The plain `bbp700` median trips the 1.20 bound
by 0.012. It is explained by θ_s over-sampling in the slice, by an
elasticity of about 2 that the bound assumed was 1, and by +6 % from the
free `B_p`. Population-reweighted it is 1.14–1.15. Every other trigger is
clear, and the view and θ_s domain breaches are gone. *(My recommendation:
go. For the record, the corrected expectation for the full population is
≈ 1.14 median, and a full-run median outside ~[1.05, 1.25] should stop the
close-out for a look.)*

**Your answer:**

**R2-Q2: keep `B_p` free in 2.1?**
- With `B_p` free, 2.1 drops `B_p` (median 0.024 → 0.020). The count at the
  0.004 floor goes from 9 to 23 of 200, and `b_bp` comes out +6 % above the
  fixed-`B_p` result. χ² is the same either way.
- **A (recommended).** Keep it free, as planned. 2.1 then changes the
  geometry and nothing else, and the floor pile-up and the +6 % are
  reported in the write-up and on the Methods page.
- **B.** Fix `B_p` (e.g. 0.014) for 2.1. That is a second physics change
  in the same release, and it makes 2.0 → 2.1 no longer a geometry-only
  comparison.

**Your answer:**

**R2-Q3: for the paper (no action in this doc).** 2.1 moves PACE `b_bp(700)`
up by ~14 % on the population and widens the PACE > Argo offset: δ median
+0.07 → +0.23 on the slice. analysis.md's "bias low by 5–10 %" becomes
"bias low by ~15–20 %, mostly from θ_s". Noted here so the bbp-paper prompt
picks it up from the Task 4 numbers. *(Nothing to answer unless you want it
handled differently.)*

**Your answer:**

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-11-14 (Prompt doc written: the v2.1 normalized-geometry re-fit planned; twelve questions posed)

Written from `papers/bbp/prompts/analysis.md` RT prompt 3, with Claude Opus
5.5. Read JXP's answers in Q&A / Raman correction and Q&A / Viewing angle:
fit at (0, 0, 0) under the name v2.1; θ_s = 0 for the inelastic terms; the
Raman term stays on, because the AOP `Rrs` is not Raman-corrected; no 2×2
test. Checked the current state read-only. The v2 DB is schema v5 with
15,971 BING 2.0 fits, 51 BING 2.0.1 fits, 15,976 NASA_GIOP 1.1 fits, and
all-V3_2 granules. All 15,971 + 51 chain NPZs are local (19 GB), so the
whole re-fit can replay on the workstation without a granule. The
production window is 400–700 nm (not 720). Five matchups have no 2.0 fit.
The workstation has 24 cores and 755 GB. The L23 `Ed` table anchors at
0/30/60°, so θ_s = 0 needs no interpolation. Traced the code seams where
geometry enters: `obs_geometry` in the fit, `_fit_diagnostics`,
`set_inelastic_Ed`, `fit_fig._geometry_from_row` / `reconstruct_fit`, and
the R3 skip. The figure reconstruction is the easy one to miss: it reads the
pixel's angles back, so it needs the fit's geometry mode. Checked that `2.1`
is a base version under `compare.version_family`, so it becomes the report
headline on the v2 DB without new code. Wrote Goals, Context (code seams,
measured facts, the expected 1.05–1.10 `bbp700` ratio), a Plan (code a–i,
gate, full run, report, publish), five Tasks with a hard stop after the
slice, and questions V1–V12. No code or DB changes.

### 2026-11-14 (Prompt 1: Round 1 folded in, Tasks rewritten for Nautilus; Task 1 code, tests and local check done)

**Plan.** Folded JXP's Round 1 answers into the Plan header. All took the
recommendation except V6 = B. Rewrote Plan §3, §4 and §6 and Tasks 2–5 for
Nautilus: the slice runs in a pod too, and doubles as the first use of the
`pab:2.1.0` image. The workstation does only a dry run and a 2-matchup
safety run. Staging and custody are spelled out: the PVC DB is the master
while the pod runs, with a sha on both sides and the `_v2.1` chains rsync'd
back. Figures also go to a pod.

**Code (Plan §2 a–i, in the order f→a→b→e→c→d→g→h→i).**
- f: `pab_version = "2.1"` with a docstring entry; `setup.py` 2.1.0. The
  editable install was refreshed (`pip install -e . --no-deps`), because
  `package_versions()` reads the dist metadata.
- a: `FitConfig.geometry_mode`, default `"normalized"`, validated in
  `__post_init__`; constants `GEOM_OBSERVED` / `GEOM_NORMALIZED`. New frozen
  `FitConfig.v2_0_1()` (ceilings + observed). `v2_0()` and `v1()` pin
  observed. `v2_0_1() == FitConfig(geometry_mode="observed")` exactly.
- b: `run.fit_geometry(config, θs, θv, Δφ)` is the one resolver:
  normalized → `normalized_geometry()` = `ObsGeometry(0, 0, 0)`; observed →
  `obs_geometry`; Gordon → None. `_geometry_or_none(inp, config)` uses it in
  `fit_matchup`, the serial and the parallel `build_fits` paths. `Ed` and
  diagnostics follow automatically, because they take the same `geom`.
  `fit_spectrum` also guards itself: under normalized, `geom=None` becomes
  (0, 0, 0), and a non-zero geom **raises** rather than being silently
  overridden.
- e: `requires_geometry` (the backend needs an ObsGeometry) is split from
  the new `requires_pixel_angles` (true only for robust + observed). R3 in
  `build_fits` keys on the latter (V5).
- c: schema **v6** `fits.geom_mode` (`_v5_to_v6`); `persist_fit` stamps it.
  `_config_from_row` reads it back, and NULL means observed.
- d: `fit_fig._geometry_from_row(store, row, config)` dispatches through
  `fit_geometry`, so a 2.1 figure is drawn at (0, 0, 0) and a 2.0 one at
  the pixel angles. `reconstruct_fit` no longer gates on
  `requires_geometry` itself.
- g: `version_family` gives `("2.1", [])` on a 2.0+2.0.1+2.1 store, and
  `gather_version_pair` pairs 1.0 with 2.1 (both tested). Added
  `rst._v2_label(df)` (the newer arm's base version, from the frame's own
  `version_v2`). The 1.0-vs-2.x headings, ratio labels, axis labels and
  captions now say 2.1 when the data are 2.1. Left for Task 4: the
  narrative paragraphs ("What changed in 2.0", Methods "Retrieval
  configuration (2.0)", the runaway-failure note, which has nothing to say
  on a 2.1 base, and hard-coded numbers such as "~0.02 in the clearest
  water"). They need the full-population 2.1 numbers.
- h: new `pab/tests/test_geometry_mode.py` (24 tests): the constructors,
  the resolver, the normalized fit refusing an observed geom, (0, 0, 0)
  reaching `build_models` and `set_inelastic_Ed`, `robust.rt.ed.Ed` called
  at exactly 0°, the diagnostics geometry, a NULL-angle pixel fitted under
  normalized (`build_fits` and `fit_matchup`), observed vs normalized on
  the same stored angles, the v5→v6 migration (legacy rows NULL,
  idempotent), the `geom_mode` stamp, `_config_from_row` / `_geometry_from_row`,
  `reconstruct_fit` at the row geometry (parametrized: normalized / NULL /
  observed), the 2.1 headline and the 1.0-vs-2.1 labels, and a real toy
  robust fit at (0, 0, 0) that recovers `bbp700`. Updated 10 existing tests:
  the R3 tests now pin `FitConfig.v2_0_1()`; version strings changed to
  2.1; the v5 asserts moved to `SCHEMA_VERSION`.
- i: HOWTO §4 (fit row, "2.1 changes the geometry and nothing else") and a
  new §5c (in progress, with the v5→v6 migrate-on-open warning); `docs/db_schema.rst`
  (v6); `docs/fitting.rst`; BING `bing/rt/defs.py` `robust_hybrid` docstring
  (trained at nadir; PAB evaluates at (0, 0, 0) from 2.1). The BING edit is
  in the **bing** repo, for JXP to commit.

**New baseline: 537 passed, 1 skipped** (was 494 + 1 at 2.0.1; this
includes tests added since). `ruff check pab` is clean.

**Gotcha for Task 3.** `Store.open()` defaults to `create=True`, which runs
`migrate`. The first 2.1-code open of the v2 DB therefore adds the
`geom_mode` column (a schema write). Take the dated copy before any 2.1 code
touches the live file. In this task the live DB was only `cp`'d. Its sha is
unchanged (`9503015b…`) and it is still `user_version = 5`.

**End-of-task check** (scratch copy of the v2 DB, `PAB_DATA_DIR` = scratch,
no persistence; `versions/v2.1/task1_check.{py,json}`). Five matchups:
θ_v 22, 33, 45, 48 and 53°, the last a 2.0.1 re-fit. Each was fitted
under `FitConfig()` and `FitConfig.v2_0_1()` on the replayed 2.0 spectrum,
10 workers, ~140–155 s CPU/fit. `ObsGeometry.to_robust` was patched in each
worker to record every geometry the forward model received.
1. **Geometry: confirmed.** Every 2.1 forward call saw exactly
   (0, 0, 0). Every 2.0.1 call saw the pixel's own angles.
2. **Reproduction: yes, to MCMC noise.** The 2.0.1 re-run against the
   stored value gives `bbp700` ×0.994, ×1.036, ×1.034, ×1.123 and ×1.217
   (the last against the stored 2.0.1; 0.00136 against a 5–95 % of
   [0.00091, 0.00134]). Chl ×0.68–1.02; one Chl is at the 1e-3 floor with a
   CI spanning three decades. χ² and acceptance are within a few
   hundredths.
3. **Sign: not as predicted, on n = 5.** `bbp700(2.1)/bbp700(2.0.1 re-run)`
   = 0.99, 1.26, 0.85, 0.85, 0.99 (median 0.99; against the stored values,
   median 0.98). `B_p` dropped to 0.012–0.015 on 4 of 5. Free `B_p` looks
   able to absorb the geometry term. Raised as **T1-Q1** in Q&A / Round 1b,
   with a proposed fixed-`B_p` arm for the Task 2 slice. Nothing else was
   changed because of it.

### 2026-11-14 (Prompt 2: T1-Q1 answered, so the fixed-`B_p` arm is added to the Task 2 gate)

JXP answered T1-Q1: add the arm. Folded it into Plan §3 and Task 2. No code
and no DB touched.

- **Design.** 50 of the 200 slice matchups (`versions/v2.1/bp_arm_50.csv`):
  12–13 per θ_v band, spread in θ_s, `ztt_slice` members preferred,
  `success = 1` only, the 2.0.1 re-fits excluded. Each is fitted twice on
  the replayed 2.0 spectrum with `fit_Bp=False`: arm-N
  (`FitConfig(fit_Bp=False, Bp_value=0.014)`) and arm-O
  (`FitConfig.v2_0_1(fit_Bp=False, Bp_value=0.014)`). The two differ only
  in geometry.
- **`Bp_value = 0.014`, not the 0.012 I proposed.** Rereading analysis.md
  Viewing-angle finding 3 showed that its 1.05–1.10 prediction was computed
  at `B_p = 0.014`. Fixing the arm at the same value makes `R_fix` a direct
  test of that number, and 0.014 is inside the emulator's trained range
  [0.0103, 0.018].
- **Mechanics.** All three passes (main, arm-N, arm-O) would mint the same
  `…_v2.1` `fit_id`, and the chain NPZs are named by `fit_id`. So each pass
  gets its own DB copy and `PAB_DATA_DIR` under
  `/data/v2.1_slice/{main,arm_norm,arm_obs}/`. The `pab` CLI has no
  `FitConfig` flags, and the production CLI is left alone, so the arm runs
  through a new driver `nautilus/v21_bp_arm.py` (written in Task 2). It
  goes through the same `run.build_fits(…, selection=, spectra=)` path as
  the CLI. The local safety run now also exercises the driver in both
  modes.
- **Analysis added to the §3 report.**
  - `R_fix` overall, per band and against θ_s / θ_v.
  - A per-pixel test against the forward-model ratio
    `Rrs₇₀₀(obs)/Rrs₇₀₀(0,0,0)` at each pixel's arm-O IOPs and
    `B_p = 0.014`. It needs no fits.
  - `R_free` and the `B_p` shift on the same 50.
  - `B_p(2.1)` against `B_p(2.0)` per band (with the bound fractions) as a
    first-class gate quantity.
  - The three readings to report: (a) compensation, (b) the prediction
    does not survive a fit, (c) noise.
- **Gate.** No new numeric trigger. The arm outcome is read alongside the
  `bbp700` [0.98, 1.20] trigger, and every case still stops for review.
- **Cost.** About one extra pod-hour: the two arm passes run concurrently
  in the slice pod at `--jobs 25` each, after the main pass.

### 2026-11-14 (Prompt 3, Task 2 part 1: selections, arm driver, safety run, job spec, analysis script; stopped before the image push and the pod)

**Selections** (`versions/v2.1/make_slice.py`, seed 2110, read-only on the v2
DB).
- `slice_200.csv`: 50 per θ_v band; round-robin over basin × season cells
  within each band; 10 of the 51 2.0.1 re-fits forced in. Basins: Arctic 17,
  Atlantic 31, Baltic 32, Indian 31, Med 29, Pacific 31, Southern 29.
  Seasons 45–53 each. θ_s 6.5–74.6°.
- `bp_arm_50.csv`: 13/13/12/12 per band, `success = 1`, no re-fits, evenly
  spaced in θ_s.
- Lat/lon come from the pixel, falling back to the profile, because some
  profile rows have NULL coordinates.
- The selection is **basin-balanced, not population-proportional**: the
  Baltic and the Med are over-weighted. So the analysis also reports a
  band × basin **population-weighted** median `bbp700` ratio beside the
  plain one.
- **Deviation from Plan §3:** the 50 `ztt_slice` ordinary fits could not be
  included. Their 300-fit sample list and the run's `specs.json` lived in
  `/tmp` and were lost when the workstation rebooted (it is on a new kernel).
  The seeded draw above replaces them.

**Arm driver** `nautilus/v21_bp_arm.py`. `arm_config(mode, bp)` builds
`FitConfig(fit_Bp=False, Bp_value=bp)` or
`FitConfig.v2_0_1(fit_Bp=False, Bp_value=bp)`. The driver sets
`PAB_DATA_DIR` before importing `pab` (and checks that it took), then calls
`run.build_fits(…, selection=, spectra=spectrum_from_chains(…))`. Tests in
`pab/tests/test_v21_bp_arm.py` (4) include "the two configs differ only in
`geometry_mode`".

**Local safety run** (scratch, 3 DB copies, 2 matchups from the arm set: θ_v
24° and 50°). Dry runs printed the right plan and configs. Real runs: CLI
main pass `--jobs 2` and both arm passes `--jobs 2`, concurrently,
~3 min each including the ~3 min compile. **All 2/2 written, 0 failed**.
Each copy migrated to **schema 6**. The 2.1 rows had `geom_mode` normalized,
or normalized and observed for the arms, `fit_bp` 1/0/0, and
`rrs_source` replay. The 2.0, 2.0.1 and 1.1 rows were intact with
`geom_mode` NULL. Chains landed only in each pass's own
`PAB_DATA_DIR/fit_chains`; production `fit_chains` holds 0 `_v2.1` files.
The live DB sha is unchanged (`9503015b…`).

**Analysis script** `versions/v2.1/analyze_slice.py` (written now, exercised
on the safety outputs).
- Slice: ratios for `bbp700`, Aph, Chl, Adg and `B_p` overall, per band and
  per θ_s bin, plus the population-weighted median. `B_p` quantiles, bound
  fractions and emulator-domain counts for both versions. χ² and acceptance;
  LM success and failures; float δ.
- Arm: `R_fix`, `R_free`, the per-pixel forward prediction
  `Rrs700(obs)/Rrs700(0,0,0)` at the arm-O posterior median with
  `B_p = 0.014`, and their rank correlation.
- Domain-breach mix at the posterior medians (2.0 observed against 2.1
  normalized).
- Figures `fig_slice_ratios.png` and `fig_bp_arm.png`.
- The two safety pixels already show the machinery working, n = 2, no
  conclusions:
  - the **view breaches (`cos_theta_v`, `cos_dphi`) vanish under 2.1** (2/2
    → 0/2) and only the `B_p` breach remains;
  - the **per-pixel predicted ratio is below 1 for both** (0.96 at θs 15°/θv
    24°; 0.87 at θs 6°/θv 50°), and `R_fix` follows it (0.93 and 0.71).
- So the analysis.md "1.05–1.10 on median" is a population median over
  pixels whose individual prediction can sit either side of 1. A small-θ_s,
  large-θ_v pixel is predicted *below* 1. The per-pixel prediction, not the
  population number, is the right yardstick for `R_fix`. The slice will show
  where the population median lands.

**Docker.** The Dockerfile self-check still asserted `pab == '2.0'`, which
would have failed the 2.1.0 build. It now asserts 2.1.0, normalized
geometry, schema 6, `fit_geometry → (0, 0, 0)` and that the driver is in the
image. JXP committed it in `6563a65`.

**Job spec** `nautilus/v21_slice_job.yaml`. Three passes, DB-local in
`/scratch`, checkpointed every 2 min to `/data/v2.1_slice/<pass>/pab.db`. The
source DB sha is logged before and after, and the replay NPZs are counted.
Arm PIDs are waited on explicitly. The YAML parses and the embedded script
passes `bash -n`.

**Baseline: 541 passed, 1 skipped**; ruff is clean (`pab`, the driver,
`versions/v2.1/`).

**Stopped** for T2-Q1 (commit bing, then build and push `pab:2.1.0`) and
T2-Q2 (apply the slice job) in Q&A / Round 2a. The rest of Task 2 (run,
pull back, `geometry_rerun.md`, Round 2) follows your answers.

### 2026-11-15 (Prompt 3, Task 2 part 2: image pushed, slice + arm run on Nautilus, gate report written; stopped for review)

JXP committed bing (`9acbe53`) and confirmed T2-Q1 and T2-Q2.

**Image.** `TAG=2.1.0 bash nautilus/build_image.sh --push`. SHAs PAB
`1f4b770`, bing `9acbe53`, ocpy `5261256`, remote_sensing `2b85c65`,
retrieve-or-bust `78d7de7`. The Dockerfile self-check printed `PAB 2.1 OK
robust_hybrid normalized schema 6`, and the smoke test passed (provenance,
stage order). `:2.1.0` and `:latest` pushed.

**Slice pod** `pab-v21-slice`, 2026-11-15 01:27–02:03 UTC.
- The log shows `pab_version 2.1 / pkg 2.1.0 / schema 6` and the baked SHAs.
  The selection shas were logged, and replay NPZs were 200/200 present.
- Main: first result after 302 s; **200/200 written, 0 failed** by 01:50.
- Arms (concurrent, `--jobs 25`): **50/50 + 50/50, 0 failed** by 02:02.
- Every DB is schema 6, with the expected
  `(2.1, normalized|observed, fit_bp)` rows. Memory was flat at ~26 GB.
- **The PVC `/data/v2/pab.db` sha is `7d44e1f3…`, not the workstation's
  `9503015b…`.** It holds no 2.0.1 rows, i.e. it is a pre-2.0.1 copy. The
  sha was unchanged before and after the pod, so it was only read. It does
  not affect the slice, because the references are read from the
  workstation DB and rows are keyed on matchup/ix/iy. It confirms that
  Task 3 must stage the live DB onto the PVC first.
- The progress-line "median s/fit" (331–736) counts queue time inside the
  2×jobs in-flight window. The real cost, from the `created` stamps, is
  **244 s/fit** steady state at 50 workers (arms ~205 s all-in).

**Pull-back.** A throw-away read-only pod (`pab-v21-pull`, deleted after)
streamed `tar czf` → `$PAB_DATA_DIR/v2.1_slice/`. The three DB shas match the
PVC (main `3e87b214…`, arm_norm `7201fc17…`, arm_obs `74eb1370…`), and all
300 chain NPZs load with finite chains. (The local du is about half the PVC
du, from ZFS compression. A stray `--exclude` warning from tar was harmless,
and the shas prove it.)

**Analysis** (`analyze_slice.py`, plus a `--figures-only` mode with the ratio
panels clipped to [1/3, 3] so the 9 clear-water extremes stop flattening the
plots). Full numbers are in `versions/v2.1/geometry_rerun.md`:
- **`bbp700` ratio median 1.212** [1.00, 1.51]. Population-reweighted:
  1.139 by θ_s, 1.149 by θ_v band × basin.
- **The driver is θ_s**: 0.96 (<20°) → 1.07 → 1.18 → 1.30 → 1.39 (≥50°).
  The θ_v bands are flat. The slice's median θ_s is 41.8° against the
  population's 31.4°.
- A_ph / Chl ×1.00; A_dg ×0.92; `B_p` ×0.84 (0.024 → 0.020).
- `B_p` floor pile-up 9 → 23; in the emulator `B_p` range 28 → 49.
- χ² ×0.97; acceptance −0.007; LM success 197/200 (three kept);
  0 failures.
- Domain breaches at the posterior median: view 190 → **0**, `cos_theta_s`
  33 → **0**, `B_p` 162 → 140.
- Float δ median +0.07 → +0.23.
- **Arm: outcome (c), not (a).**
  - `R_fix` 1.154 against a per-pixel predicted `Rrs` ratio of 1.067,
    Spearman 0.86. **Elasticity d ln `b_bp` / d ln `Rrs` ≈ 2.1** (Theil–Sen).
    The fixed inelastic and `b_bw` share of red `Rrs` makes `b_bp` move
    about twice the `Rrs` change; analysis.md had assumed 1.
  - `R_free`/`R_fix` = 1.06: the free `B_p` drop *adds* to `b_bp`, at
    equal χ².
  - 1.067^2.1 × 1.06 ≈ 1.21 reproduces the slice median.
  - Task 1's 0.99 (n = 5) is explained: those pixels had θ_s 17–33°.
- 9 / 200 extreme ratios (0.09–32): all are clear-water fits with a 2.0
  `b_bp(700)` of 5e-6 to 5e-4. The big ones move toward the float. They
  do not move the medians.

**Pause trigger:** the plain median (1.212) is 0.012 over the 1.20 bound.
Every other trigger is clear. The recommendation is **go** (R2-Q1), with the
explanation and a corrected full-population expectation of ≈1.14. R2-Q2
asks whether to keep `B_p` free (recommended: yes). R2-Q3 is a note for the
paper. **Task 3 not started.** Expected Task 3 cost: ≈ 21.6 h at 50
workers.

