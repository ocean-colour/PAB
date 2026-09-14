# Running the full PAB pipeline with inelastic RT (v2.0)

## Goals

Re-run the BING analysis in Nautilus with 
   - Full inelastic treatment, but not CDOM fluorescence 
   - Using the new RoB RT emulator
Also, we wish to backfill the missing matchups from the original run.

## Claude

### Skills

The heavy stage is the per-matchup BING fit; these inform it:

- **`batch-fit-argo`** — the batch/parallel-fit + checkpointing pattern (BING
  `fit_batch` across cores). The full run's `fit` stage is the bottleneck; this is
  where parallelism matters.
- **`run-bing-fit`** — the per-spectrum fit the `fit` stage invokes.
- **`diagnose-mcmc`** / **`debug-priors`** — if fits fail to converge or chains
  stall at scale.

### Working agreements (unchanged from Stages 0–9)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Drive the existing `pab` CLI / stage functions; do
  not re-implement them or copy the one-off `bing/papers/biomass/Analysis` scripts.
- **Keep git small by construction.** Only the small aggregate site
  (`report_site/`) is committed; bulky per-matchup figures / MCMC chains belong in
  the object store (Nautilus S3, deferred — `HOWTO.md` §7b). The report galleries
  auto-suppress above `MAX_INLINE_FIGURES`, so the site stays bounded at ~10⁴
  matchups.

## Context

Read these before running — plus the **hard-won operational lessons** below.

- **Operator guide** — `HOWTO.md` (the CLI, the stages, idempotency/resume, the
  in-region vs `--download` granule-access section, and §7 publishing).
- **Design** — `docs/design/PAB_design.md` → *Semi-automation* (idempotent stage
  runner, single-matchup debug vs full batch, BING `fit_batch`) and *Provenance &
  versioning* (every result stamped with `pab_version`; re-running under a new
  version **adds** records, never silently overwrites).
- **Implementation record** — `docs/design/PAB_implementation.md` (current state,
  incl. the Stage 9 close-out: schema v3, headless plotting, report structure).
- **Prior run logs** — `claude_prompts/run_full_pipeline.md` (the first full run)
  and `claude_prompts/nautilus_prompts.md` (the Nautilus work) and 
  `claude_prompts/pace_giop_gsm.md` which includes the PACE GIOP and GSM matchups
  and a discussion of the backfill needs

**Operational lessons to honour (learned the hard way):**

1. **One canonical `$PAB_DATA_DIR` for the whole run.** A mismatch between shells
   (set vs unset) silently split state across two databases during Stage 9
   (matchups in one, Q&A figures in another). **Export `PAB_DATA_DIR` once** (or
   pass an explicit `--db` every time) and never mix.
2. **Granule access at scale.** Out-of-region, lazy S3/HTTPS reads are slow and can
   hang; use `--download` (pre-download to `--cache-dir`, ~0.5 GB/granule on disk)
   **or** run in-region on AWS `us-west-2` (the design target — fast S3, no local
   copy). Budget disk accordingly.
3. **The `fit` stage is the cost.** BING MCMC per matchup is expensive and
   **matchup-level parallelism is not yet implemented** (`HOWTO.md` → Planned
   enhancements). Serial fitting of ~10³–10⁴ matchups will be very slow — see the
   Q&A on parallelism before starting.
4. **Everything is idempotent & resumable.** Each stage skips completed work
   (keyed on profile / `matchup_id` / `fit_id`); safe to interrupt and resume.
   `--replace` re-does completed work; a `pab_version` bump adds a fresh record set.
5. **Matplotlib is headless (`Agg`).** The `ingest` Q&A plots and figure stage no
   longer crash alongside argopy threads (Stage 9 fix).
6. **Schema auto-migrates** to v3 (`qa_path`, `scene_path`) on `Store.open`.
7. **Argo Q&A** figures come from `ingest`'s live-fetch path; **PACE scenes** are
   recorded by the `figure` stage (a plain `--stage figure` backfills existing
   scene PNGs). Both surface in the report once recorded.

If you need to use Python, be sure to use the `ocean14` conda environment.  

## Prompts

1. Execute the 1st task in Tasks/Planning below
2. Execute the 2nd task in Tasks/Planning below
3. Execute the 3rd task in Tasks/Planning below

## Tasks

### Planning

1. Read all the files in the context.  We wish to develop a plan to re-run the BING analysis in Nautilus with the new RoB RT emulator.  We will also need to backfill the missing matchups from the original run.  Have a discussion with me on the plan for this work.  Ask me a series of questions in the Q&A section.  Use Fable if you can.  Log your work.

2. I have answered your first round of questions.  See my answers, update the Plan, and then ask me another round.  Use Fable if you can. Log your work.

3. I have answered your second round of questions.  See my answers and update the Plan.  Then generate a series of prompt docs named `build_v2_prompt_<number>.md` in the `claude_prompts/v2` directory.  Use Fable if you can. Log your work.

## Plan

*Drafted 2026-09-13 after reading the context set and checking the current
state read-only (production DB, BING/`robust` code, a cached PACE granule,
Nautilus, `s3://pab`, the live Argo index). **Revised 2026-09-14 after the
round-1 answers (Q1–Q12)** and two further verifications: the L1B geometry
read (Q3) and BING's free-`B_p` chain layout (Q4). Open decisions are in
**Q&A → Planning — round 2**; the plan assumes my recommendations there.*

### 0. Decisions locked in round 1

| Decision | Answer |
|---|---|
| Version stamp | **`pab_version = "2.0"`** |
| Fit identity | version-aware `fit_id` `{matchup}_{ix}_{iy}_{model_pair}_v2.0` + **schema v5** provenance columns |
| **v1.0 and v2.0 live in separate databases** | new — see §1 |
| Geometry | **A — read from the L1B granule** (verified below) |
| RT config | `robust_hybrid`, Raman on, Chl-fluorescence on (`phi_C = 0.02` fixed), CDOM-fl **off**, **`wave_max = 720`**, **`B_p` free** |
| Backfill | gaps **A + B + D**; gap C (the 36,683-profile `match` plateau) dropped |
| DB custody | single writer on the PVC during the run; workstation read-only meanwhile |
| Report | 2.0 headline + one **1.0-vs-2.0** comparison section |
| Bulk-artifact publish | deferred again |
| Dev env | `ocean14` (install `pab`, `argopy` there) |
| Provenance | git SHAs of `PAB`/`bing`/`ocpy`/`remote_sensing`/`retrieve-or-bust` in `pkg_versions` + image label (`bing` @ `bf56f6d`, `robust` @ `dfab27c`, both trees clean today) |
| MCMC | keep `nsteps=10000` / `nburn=1000`; walkers = `max(16, 2×ndim)` = 16 still at ndim 6 |
| Gate | 100-matchup leading slice, reviewed by JXP before the full send |

### 1. Two databases: `v1` (frozen) and `v2` (this run)

The v1.0 fits stay in their own database, untouched; everything this run
produces goes into a new one. Proposed layout (confirm in **R1**):

| | v1 (frozen) | v2 (this run) |
|---|---|---|
| workstation | `$PAB_DATA_DIR/v1/pab.db` — today's `full/pab.db`, renamed; `full/` kept as a symlink so old commands keep working | `$PAB_DATA_DIR/v2/pab.db` |
| PVC | `/data/v1/pab.db` (+ the existing `/data/fit_chains` → `/data/v1/fit_chains`) | `/data/v2/pab.db`, `/data/v2/fit_chains`, `/data/v2/pipeline` (`PAB_DATA_DIR=/data/v2`, so `pab.fit.artifacts` keys chains there with no code change) |
| S3 | `s3://pab/v1/pab.db` (copy of today's `full/pab.db`); the `full/` objects stay where they are — the published site's download links point at them | `s3://pab/v2/pab.db` + `v2/matchup_summary.*`; the v2 site's downloads page points at `v2/` |
| backup | already at `AIOcean:PAB/` | `AIOcean:PAB/pab_v2_<date>.db` (copy-not-sync, dated) |

**v2 starts as a copy of v1 minus the BING 1.0 fits:** `floats`,
`profiles`, `mld_summary`, `granules`, `matchups`, `matchup_pixels` and the
14,609 **NASA-GIOP** rows (`algorithm='NASA_GIOP'`, `1.1`) are carried over —
the NASA values are per-pixel product reads independent of BING's RT, and
the "BING vs NASA GIOP" comparison must work inside v2 — while the BING
`fits`/`fit_results` rows (and `chains_path` references) are dropped. The
copied rows keep their original `pab_version` stamps (`1.0` = when the
matchup was made); every row *created* by this run stamps `2.0`. The
backfilled profiles/matchups exist **only in v2** (v1 is frozen). The
1.0-vs-2.0 report section reads v1 through a new `--compare-db` option
(SQLite `ATTACH`, join on `matchup_id`+`pixel_id`). The version-aware
`fit_id` is kept even though the DBs are separate — it makes an accidental
cross-DB merge harmless.

### 2. The fit: what changes and what BING needs from PAB

**Production 1.0**: `ExpBricaud`+`Pow`, 400–700 nm, 5 free parameters,
elastic Gordon (`rt_backend='gordon'`), 10k steps / 16 walkers.

**2.0**: same model pair and priors; `rt_backend='robust_hybrid'` (the RoB
emulator, valid 350–750 nm); `include_Raman=True`; `include_Chl_fl=True`
(`phi_C=0.02` fixed, double-Gaussian emission); `include_CDOM_fl=False`;
**`wave_max=720`** (PACE `wavelength_3d` runs to 719 nm, so the 685 nm
fluorescence peak's red shoulder is now inside the window); **`fit_Bp=True`**
— `B_p` (particulate backscattering ratio) becomes a **6th free parameter**,
sampled linearly on BING's default prior [0.004, 0.05] and carried as the
*trailing* element of the parameter vector (`inference.log_prob` peels
`params[-1]`; `init_mcmc` sets `ndim = 6`, walkers stay 16). BING's side is
ready (`rt_dict_from_p` reads all of these off the parameter tuple).

BING requirements that fall on PAB:

1. **Geometry — verified, option A works.** For the cached production
   granule `PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc` a CMR search on
   `PACE_OCI_L1B_SCI` returns the same-stamp `…L1B.V3.nc` (1.8 GB; CMR
   lists each granule twice — dedupe by name). `xr.open_datatree` over
   `earthaccess.open` reads `geolocation_data/{solar_zenith, sensor_zenith,
   solar_azimuth, sensor_azimuth}` lazily: **same 1709×1272 grid, lat/lon
   identical at the matched pixel (868, 142)**, open + 4-value read
   **7.6 s out-of-region** (faster in-pod). At that pixel: `theta_s = 29.47°`
   (the scan-line `csol_z` says 31.26° — option C would be 1.8° off) and
   `theta_v = 54.58°` (a nadir assumption would be 55° off). `dphi` =
   `sensor_azimuth − solar_azimuth` (wrapped). Geometry is a **pixel**
   property, not a fit property → store it on `matchup_pixels`
   (**R3**).
2. **Fluorescence needs `a_ph`** — satisfied: PAB already seeds Chl from
   the float's mixed-layer `chla` (0.1 fallback) via `init_other_bits`.
3. **`Ed`** — none in PACE L2; `robust` falls back to its packaged L23 `Ed`
   interpolated in `theta_s` (documented default). Accept.

### 3. PAB code work (before anything runs at scale)

| # | Change | Where |
|---|---|---|
| a | `FitConfig` gains `rt_backend`, `include_Chl_fl`, `include_CDOM_fl` (False), `phi_C`, `fit_Bp`, `Bp_value`; `wave_max` default → 720 for 2.0; `build_models` forwards them to `standard.expb_pow`. | `pab/fit/models.py` |
| b | **Free `B_p` plumbing**: `_initial_guess` / `_prior_bounds` / `_is_log_param` / `model_param_names` gain the trailing `B_p` (linear, [0.004, 0.05], seed 0.01); `extract_quantities` must **peel `flat[:, -1]` before** splitting `a`/`bb` params (today it would hand `eval_bbnw` three columns) and emit `BING_ExpBPow_Bp`; `_fit_diagnostics` passes `Bp` to the robust forward model. | `pab/fit/run.py` |
| c | **Geometry**: schema v5 adds `matchup_pixels.{theta_s, theta_v, dphi, geom_source}`; new `pab.pace.l1b`-side reader (`l1b_source_for_aop` name-swap + CMR lookup, lazy `geolocation_data` read at `(ix, iy)`, grid check against the pixel's stored lat/lon — the same discipline as the NASA-GIOP join); a new **parallel `geometry` stage** (`--jobs`, workers read, parent writes — the `match` shape) that fills the columns for every pixel lacking them. Runs once over the 14,610 existing matchups and again after the backfill. Running it as its own stage keeps the ~4 s L1B open out of `fit`'s *serial* parent loop (17k × 4 s ≈ 19 h if done there). `fit` then just reads the three angles and builds `ObsGeometry`, passed as the 5th tuple element to `chisq_fit.fit` / `fit_one`. | `pab/db/schema.py`, `pab/pace/`, `pab/pipeline.py`, `pab/fit/run.py` |
| d | `_fit_diagnostics` and `pab.plotting.fit_fig` call the Gordon `calc_Rrs_from_models` directly → dispatch to `calc_Rrs_from_models_robust(..., geom=, Bp=)` for robust fits (χ²/AIC/BIC and the fit figure must use the fitted physics). `fit_fig` reads the angles back from the DB. | `pab/fit/run.py`, `pab/plotting/fit_fig.py` |
| e | **Provenance**: schema v5 adds `fits.{rt_backend, include_raman, include_chl_fl, include_cdom_fl, phi_c, fit_bp}`; version-aware `make_fit_id`; `pkg_versions` gains `robust` and the five git SHAs. | `pab/db/schema.py`, `pab/fit/{run,artifacts}.py`, `pab/config.py` |
| f | **Report/metrics**: `gather_matchups` selects by `model_pair` only → add `pab_version`; new `gather_version_pair(store_v2, v1_path)` for the comparison section; `--compare-db`; the downloads page's base URL → `…/pab/v2`. | `pab/metrics/compare.py`, `pab/report/rst.py`, `pab/pipeline.py` |
| g | **Workers**: pin XLA's CPU thread pool to 1 in `pab.parallel.init_worker` (JAX otherwise spawns its own pool per worker); per-process JIT ~0.2 s, plus one recompile per distinct `nwave` (bands dropped by `prepare_spectrum`). | `pab/parallel.py` |
| h | **DB-split tooling**: a small `pab.db.split_version` helper (or script) that builds `v2/pab.db` from `v1/pab.db` per §1 and verifies it (`foreign_key_check`, counts). | `pab/db/` |
| i | **Image `pab:2.0.0`**: add `retrieve-or-bust` (2.2 MB) + `jax`/`flax`/`optax`/`jaxtyping` to the staged build; `--label` the SHAs. | `Dockerfile`, `nautilus/build_image.sh` |
| j | **Env**: `pip install -e` PAB + `argopy==1.4.0`/`erddapy==3.2.1` into `ocean14` (Python 3.14 — fall back to `os_313` + `robust`/`jax` if `argopy` won't install). | — |
| k | Tests for a–h (toy-size robust fit under `importorskip("robust")`, B_p peel, geometry stage with an injected opener, schema v5 migration, split helper); `ruff` clean. | `pab/tests/` |

**Cost.** BING's benchmark: `robust_hybrid` 5.7k vs `gordon` 38.9k
`log_prob` calls/s (**6.9× slower**, elastic) before the Raman/fluorescence
kernels; 16 walkers × 11k steps = 176k calls/fit → **~1–2 min CPU/fit**
expected (measured in the slice). ~16.6k fits / 50 cores ≈ **6–12 h**.
Geometry stage: ~13.5k unique L1B opens (11,494 granules today + the
backfill) at ~4 s in-pod / 16 workers ≈ **1 h**. The DB-local Job wrapper
stays (the 1.0 fit stage was CephFS-bound). Fit pod memory: JAX adds a few
hundred MB per worker → request 100 Gi, not 64 Gi, at 50 workers.

### 4. Backfill (A + B + D; sized read-only 2026-09-13)

| Gap | Size | Fix | ≈ new matchups (28 %) |
|---|---|---|---|
| **A** — ingested, never had candidates (granules in the DB stop 2026-06-01; profiles run to 07-06) | **2,356** profiles | subset CSV from the DB → `discover --profiles-csv … --replace` → `match` | ~650 |
| **B** — new BGC profiles since the selection was cut | **4,981** / 686 floats (live `bgc-s` query, 2026-07-06 → 09-14; re-queried at run time so the window ends *that* day) | selection CSV → `ingest` → `discover` → `match` | ~1,400 |
| **D** — leftovers | ~475 never-ingested profiles of the original 54,506 (argopy transients); 1 unfit matchup | re-attempt `ingest`; the matchup fits naturally under 2.0 | ~130 |

→ **~+2,200 matchups, ~16.8k fits.** Then NASA-GIOP for the new matchups
only (`python -m pab.fit.nasa_giop --db v2/pab.db`, ~2.2k × 4 s ≈ 2.5 h,
~100 GB scratch cache), and `figure` for the 2.0 fit figures (+ scenes for
the new matchups only).

### 5. Sequence

0. **Code + env** (§3 a–k) on the workstation; fit 3–5 real matchups from
   the cached granules under 1.0 and 2.0 configs; unit + smoke tests.
1. **Split the DB** (`v1` frozen, `v2` built per §1); rename local dirs;
   copy `v1/pab.db` → `s3://pab/v1/`.
2. **Image `pab:2.0.0`**; in-pod `validate_job` smoke (5 profiles → 1 fit
   with geometry + 2.0 config).
3. **Stage `v2/pab.db` on the PVC** (`/data/v2/`); rename `/data/fit_chains`
   → `/data/v1/fit_chains`; `/data/full/` → `/data/v1/`.
4. **Backfill** in-pod: `ingest` (B + D) → `discover` (A + B; `--replace`
   for A) → `match` (`--jobs 16`).
5. **`geometry` stage** in-pod over every pixel (`--jobs 16`, ~1 h).
6. **Leading slice** (100 matchups, `fit` 2.0): s/fit, χ²/acceptance vs 1.0,
   `bbp700(2.0)/bbp700(1.0)`, `B_p` posterior spread, robust-backend errors.
   **JXP reviews before step 7.** (Also, diagnostic only: the same 100 with
   `B_p` fixed, to attribute the shift — **R2**.)
7. **Full `fit` 2.0** (DB-local wrapper, `--jobs 50`, 100 Gi).
8. DB back to the workstation → **NASA-GIOP** for the new matchups.
9. **`figure`** (2.0 fit figures; scenes for new matchups) → **`report`** →
   `--emit-site report_site --compare-db v1/pab.db --downloads-base-url
   …/pab/v2`; publish `v2/pab.db` + tables → `s3://pab/v2/`; backup →
   `AIOcean:PAB/`; user pushes `report_site/` for RTD.
10. **Verify & close out**: every 2.0 row stamped; v1 DB byte-identical to
    its 2026-09-11 sha; integrity; docs (`HOWTO.md`, `PAB_implementation.md`,
    `db_schema.rst`, `PAB_design.md` provenance section for the two-DB
    convention); run report.

## Q&A

### Planning

*Answer inline under each **Your answer:**. Each carries my recommendation;
the Plan above assumes it.*

**Q1 — `pab_version` for this run.** This changes the forward-model
physics (RoB emulator + Raman + Chl fluorescence), so retrieved `b_bp`/`a_ph`
will differ materially from 1.0 — a re-analysis, not a backfill. Bump to
**`"2.0"`** (major: different physics, side-by-side with 1.0 by design), or
`"1.2"` (next minor after the NASA-GIOP `1.1`)?
*(My recommendation: `2.0`.)*

**Your answer:** 2.0

**Q2 — Keeping 1.0 and 2.0 fits side by side (identity + schema).** Today
`fit_id = {matchup_id}_{ix}_{iy}_{model_pair}` and the `fits` table has no
column for the RT backend or inelastic flags. Unchanged, a 2.0 `fit` run
skips every matchup (same `fit_id` already present), and `--replace` would
overwrite the 1.0 rows. Proposal: (i) new fits get a **version-aware id**,
`{matchup_id}_{ix}_{iy}_{model_pair}_v{pab_version}` (1.0 ids stay as
stored — the done-check then correctly sees nothing done for 2.0), and (ii)
**schema v5** adds `fits.rt_backend`, `fits.include_raman`,
`fits.include_chl_fl`, `fits.include_cdom_fl`, `fits.phi_c`, and the fitted
pixel's `theta_s`/`theta_v`/`dphi`, all NULL on legacy rows (a forward
migration, like v2–v4). The alternative — a new `model_pair` label such as
`ExpBPow_RoBi` — avoids the migration but misdescribes the model pair
(unchanged) and leaks RT config into a namespace meant for IOP models.
OK with (i)+(ii)?
*(My recommendation: yes.)*

**Your answer:** (i) I wish to keep the v1.0 fits as a separate database.  I think the version-aware ID is also good;  (ii) yes, this is good

**Q3 — Where does the viewing/illumination geometry come from?** The L2
AOP granule has no per-pixel angles (verified). Options:
- **A — Read the L1B granule.** `PACE_OCI.<stamp>.L1B.V3.nc` (named in the
  L2's `history`) carries `geolocation_data/{solar_zenith, sensor_zenith,
  solar_azimuth, sensor_azimuth}` per pixel; one lazy in-region read at
  `(ix, iy)` per matchup (~4 s in-pod, KB transferred) gives exact
  `theta_s`, `theta_v`, `dphi`. Needs the L1B granule to be
  `earthaccess`-searchable/openable alongside the AOP one (to verify).
- **B — Compute.** `theta_s` from pixel lat/lon + scan time (standard solar
  ephemeris; sub-degree accurate); `theta_v` from the pixel's cross-track
  index (OCI scans ±56.5°, 1,272 pixels → view zenith up to ~60° at the
  swath edge); `dphi` from solar azimuth vs the scan direction. No extra
  I/O; a few degrees of approximation in `theta_v`/`dphi`.
- **C — Minimal.** `theta_s = csol_z` of the pixel's scan line (already in
  the L2 file), nadir viewing assumed. Cheapest; wrong `theta_v` at the
  swath edges, where the emulator correction is presumably largest.
Whichever we pick is recorded on the fit row (Q2) so it can be revisited.
*(My recommendation: **A** if the L1B open works in-pod, else **B**; never C
for a production run.)*

**Your answer:** A

**Q4 — Confirm the RT configuration.** `rt_backend='robust_hybrid'` (not
`robust_ztt`; the 400–700 nm window is inside the emulator's 350–750 nm
domain); `include_Raman=True`; `include_Chl_fl=True` with BING's fixed
`phi_C=0.02` and the double-Gaussian emission; `include_CDOM_fl=False`;
`B_p` **held fixed** at BING's default 0.01 (`fit_Bp=False`) so 2.0 has the
same free parameters as 1.0 and the comparison isolates the RT change.
Two things to consider changing: (a) **extend `wave_max`** from 700 to
~715–720 nm (PACE bands run to 719) so the fluorescence emission's red wing
is actually constrained — 700 nm cuts the 685 nm peak's shoulder; (b) free
`B_p` (a new capability; adds a 6th parameter and a degeneracy with `Bnw`).
*(My recommendation: the config as stated, with **(a) yes, `wave_max=720`**
and **(b) no** — keep `B_p` fixed for this run.)*

**Your answer:** (a) yes, `wave_max=720` and (b) let B_p be free

**Q5 — Backfill scope.** Gaps **A** (2,356 profiles, re-discover + match),
**B** (4,981 new profiles, full chain) and **D** (475 ingest retries) are
cheap and clearly wanted. Gap **C** — re-running `match` over the 36,683
never-matched profiles — is ~3 days of pod time for an expected <1 % yield.
Proposal: run the DB-only `coverage_check.py` and a CMR sweep for newer
PACE reprocessing first; re-pass **C** only if either says the candidate
pool has changed. Also: should **B**'s window end at "today at run time"
(so we pick up everything to the run date), and do we extend the mission
window permanently (every future run backfills to `today`)?
*(My recommendation: A+B+D now; C conditional on the two checks; B to run
date; yes, "end = today" as the standing rule.)*

**Your answer:** A+B+D

**Q6 — DB custody for the run.** Upload the canonical merged
`$PAB_DATA_DIR/full/pab.db` to the PVC (replacing the stale `/data/full/
pab.db`), do **all** run writes there (one writer), and bring it back to the
workstation + S3 at the end; the workstation copy is read-only meanwhile.
Anything on your laptop (`cdom_chl`) still unpublished that would collide?
*(My recommendation: yes to the custody rule; please confirm the laptop is
in sync with S3 as of 2026-09-11.)*

**Your answer:** yes on your plan, but note my desire to keep the v1.0 and v2.0 fits as separate databases.

**Q7 — Report presentation.** Make **2.0 the headline** everywhere (summary,
aggregates, Chl, NASA-GIOP comparison), and add a **"1.0 vs 2.0"** section
(same-pixel `b_bp700`/`a_ph`/Chl scatter + `log_comparison` stats — a direct
measurement of what the RT change did), with 1.0 otherwise retired from the
site? Or keep both versions fully rendered (doubles the page set)?
*(My recommendation: 2.0 headline + one comparison section.)*

**Your answer:** 2.0 headline + one comparison section.

**Q8 — Chains and the bulk-artifact publish.** 2.0 adds ~17k chains
(~1.3 MB each, ~20 GB) beside the 1.0 set on the PVC (500 Gi, ample). Keep
deferring the bulk publish to `s3://pab` (the standing §7b follow-on), or
fold it into this run's publish step now that there are two versions?
*(My recommendation: defer again — keep this run focused.)*

**Your answer:** Defer again

**Q9 — Development environment.** You asked for `ocean14`; it has
`robust`+`jax` but not `pab`/`argopy`, while `os_313` (where the PAB suite
runs) lacks `robust`/`jax`. May I `pip install -e` PAB plus
`argopy==1.4.0`/`erddapy==3.2.1` into `ocean14` (Python 3.14 — a
compatibility risk for `argopy`), or install `retrieve-or-bust` + `jax`
into `os_313` instead? The container image is unaffected either way.
*(My recommendation: `ocean14` first; fall back to `os_313` if `argopy`
won't install on 3.14.)*

**Your answer:** Yes, use `ocean14` and install what you need.

**Q10 — Code provenance for the image.** The image builds from the local
working trees of `PAB`, `bing`, `ocpy`, `remote_sensing` and now
`retrieve-or-bust`. `bing` is at `bf56f6d` (post-`rob_rt`), `robust` at
`dfab27c`; both report `0.0.dev0` as a version, so `pkg_versions` cannot
distinguish builds. OK to record each package's **git SHA** in
`pkg_versions` (and in the image label), and should I ask you to commit
any uncommitted `bing`/`robust` work before the build so the SHAs are
meaningful?
*(My recommendation: yes to both.)*

**Your answer:** yes to both.

**Q11 — MCMC length.** Keep `nsteps=10000`/`nburn=1000`/16 walkers (the 1.0
settings) despite the ~7× costlier likelihood? Projected 6–12 h of fit on
50 cores — affordable. Halving `nsteps` would save hours but make the
1.0-vs-2.0 comparison confound RT physics with chain length.
*(My recommendation: keep.)*

**Your answer:** Keep.

**Q12 — The go/no-go gate.** Before the full send: a ~100-matchup leading
slice in-pod (the same pattern as the NASA-GIOP run) reporting measured
s/fit, χ²/acceptance distributions vs 1.0, the `bbp700(2.0)/bbp700(1.0)`
ratio distribution, and any robust-backend errors (out-of-domain
wavelengths, missing geometry). Proposed pause triggers: median s/fit
> 4 min, failure rate > 2 %, or a systematic `b_bp` shift you consider
implausible. Agree, and do you want to look at the slice before I proceed?
*(My recommendation: yes, and yes — the physics change deserves a look.)*

**Your answer:** yes, and yes — the physics change deserves a look.


### Planning — round 2

*Answers to Q1–Q12 read and folded into the Plan (2026-09-14). Answer inline
under **Your answer:**; each carries my recommendation.*

**R1 — The two-database layout (your Q2/Q6 answer).** Please confirm §1 of
the Plan: (a) `v1/` = today's `full/pab.db` frozen (local rename with a
`full/` symlink; a copy to `s3://pab/v1/pab.db`; the `full/` S3 objects left
in place because the live site links them); (b) `v2/pab.db` starts as a copy
of v1 **minus the BING 1.0 `fits`/`fit_results`**, keeping profiles,
summaries, granules, matchups, pixels **and the 14,609 NASA-GIOP rows** (so
the NASA comparison works inside v2 without cross-DB joins); (c) the
backfilled profiles/matchups go into v2 only — v1 stays frozen and does not
receive 1.0 fits for the new matchups (so the 1.0-vs-2.0 section covers the
14,609 shared matchups); (d) on the PVC, `/data/fit_chains` → `/data/v1/
fit_chains` and `/data/full/` → `/data/v1/`, with `PAB_DATA_DIR=/data/v2`
for the run. Alternative for (b): copy v1 *including* the 1.0 fits, so v2 is
a superset and the comparison needs no `ATTACH` — but then "separate
databases" is only a fork, and the 1.0 rows would be duplicated in two
places.
*(My recommendation: (a)–(d) as written.)*

**Your answer:** I agree, use your Recommendations.

**R2 — Free `B_p`: prior and attribution.** (a) Keep BING's default linear
uniform prior **[0.004, 0.05]** on `B_p`, seed 0.01? (b) Report it as
`BING_ExpBPow_Bp` (median + 5–95 %) like the other free parameters. (c) With
`B_p` free *and* new RT physics *and* a wider window, the 1.0-vs-2.0
difference has three causes. Proposal: in the leading slice only, also fit
the same 100 matchups with `B_p` fixed at 0.01 (diagnostic, chains to
scratch, not persisted) so we can say how much of the `b_bp` shift is the
extra parameter versus the emulator + inelastic terms. Worth the ~2 extra
hours?
*(My recommendation: (a) yes, (b) yes, (c) yes.)*

**Your answer:** I agree, use your Recommendations

**R3 — Geometry as a pixel property + a `geometry` stage.** The L1B read
works (Plan §2.1). Proposal: store `theta_s`/`theta_v`/`dphi`/`geom_source`
on **`matchup_pixels`** (schema v5) rather than on `fits`, and fill them in a
new **parallel `geometry` stage** (workers open the L1B lazily, parent
writes) run once over all pixels before `fit` — keeping the ~4 s L1B open
out of `fit`'s serial parent loop (which would otherwise add ~19 h). Two
policies to set: (i) if a pixel has **no geometry** at fit time (L1B missing
from CMR, or the grid check fails), **skip the fit and record it as failed**
(strict — `theta_s` must never be assumed) rather than falling back to a
computed solar zenith; (ii) the grid check requires the L1B lat/lon at
`(ix, iy)` to match the stored pixel position to < 0.01° (they were
bit-identical in the test), else the pixel is flagged and skipped.
*(My recommendation: pixels table + stage; strict (i); (ii) as stated.)*

**Your answer:** I agree, use your Recommendations.

**R4 — `wave_max = 720` and the red edge.** PACE's last `wavelength_3d`
bands are 713 and 719 nm; 719 nm sits on the edge of the 720–730 nm water-
vapour feature, and `Rrs_unc` there is larger than at 700 nm. Two options:
(a) 720 as answered — BING weights each band by `Rrs_unc`, so a noisier
edge band down-weights itself; (b) 715 — drops that one band. I'd check the
slice's `Rrs_unc(719)/Rrs(719)` distribution and the per-band residuals
before deciding to drop it.
*(My recommendation: (a) 720, with the slice check.)*

**Your answer:** I agree, use your Recommendations.

**R5 — Backfill B's window and the standing rule.** Q5 left this open: I
will re-query the Argo index **at run time** so gap B runs to that day
(4,981 profiles as of 2026-09-14; ~55 more per day). Should "end = today at
run time" become the standing rule for every future backfill (recorded in
`PAB_design.md`)?
*(My recommendation: yes.)*

**Your answer:** yes

**R6 — NASA-GIOP for the ~2,200 new matchups.** The driver downloads whole
IOP granules (~47 MB each) to a cache and needs the DB local. Run it on the
**workstation after the fit stage** (v2 DB back from the PVC; ~2.5 h,
~100 GB scratch, deleted after), stamped `1.1` like the existing NASA rows
(same product, same code)? Or in-pod?
*(My recommendation: workstation, after; keep the `1.1` stamp.)*

**Your answer:** I agree, use your Recommendations.

**R7 — `figure` scope for 2.0.** Re-render the **fit figures** for all
~16.8k 2.0 fits (they encode the fitted physics; ~9 h at 16 workers) and
**scenes only for the new matchups** (scenes don't depend on the fit)?
Skipping fit figures entirely would save the 9 h but leave the report's
per-matchup gallery/tap-through pointing at 1.0 figures.
*(My recommendation: as stated.)*

**Your answer:** No need to remake the existing scenes.  Let's point to v1.0 for those

**R8 — Getting the site live.** `full-inelastic` is 94 commits ahead of
`develop` and 121 ahead of `main`; the `pab-report` RTD project builds
`develop`/`latest(main)`, so the NASA-GIOP (1.1) report from the previous
prompt doc is **still not live** either. When 2.0's `report_site/` is ready,
will you merge to `develop` (or activate the branch on the RTD dashboard)?
Nothing for me to do here beyond regenerating the site — just flagging that
two reports are now queued behind that merge.
*(My recommendation: merge `full-inelastic` → `develop` at the close-out.)*

**Your answer:** Yes, I will merge to `develop` at the close-out.

**R9 — Order of work for the next prompt.** Unless you say otherwise, the
next task starts §3 in this order: (j) env → (a, b, e) fit config + `B_p` +
provenance → (c) geometry schema/stage → (d) diagnostics/figure dispatch →
(h) DB split → (f) report → (g) workers → (i) image → (k) tests throughout,
with a workstation fit of the cached matchups under 2.0 as the first
end-to-end check. Anything you want reordered or pulled forward (e.g. the
DB split first, so v1 is frozen before any code touches a DB)?
*(My recommendation: as listed, but **do the DB split first** — it is the
one irreversible-looking step and it protects v1 from everything after.)*

**Your answer:** I agree, use your Recommendations.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-13 (Planning Task 1 — read the context; drafted the Plan + twelve Q&A questions)

Read the full context set (`HOWTO.md`, `PAB_design.md`,
`PAB_implementation.md`, and the `run_full_pipeline.md` /
`nautilus_prompts.md` / `pace_giop_gsm.md` logs), then verified the current
state rather than trusting the docs: read-only queries on the production
`$PAB_DATA_DIR/full/pab.db` (schema v4; 54,031 profiles / 67,435 granules /
14,610 matchups; `fits` = 14,609 BING `1.0` + 14,609 NASA-GIOP `1.1`), the
BING `rob_rt` integration (`bing/rt/defs.py`, `evaluate.py`, the fitters,
`docs/radiative_transfer.rst`, the `inelastic-rrs` skill), a cached PACE
V3.2 granule, the Nautilus namespace/PVC, `s3://pab/full/`, and a live
`bgc-s` Argo index query.

**Findings that shape the plan (all new relative to the prompt doc):**

- **BING needs geometry PAB doesn't have.** The robust backends refuse to
  fit without `ObsGeometry.theta_s`; the PACE L2 AOP product carries **no
  per-pixel solar/sensor angles** (`l2prod = Rrs Rrs_unc aot_865 angstrom
  avw nflh`; only a per-scan-line `csol_z`). Geometry must come from the
  L1B granule, be computed from lat/lon/time + scan index, or be
  approximated — posed as Q3.
- **Identity collision.** `fit_id` doesn't encode the version or RT config,
  so a 2.0 `fit` run would skip every matchup (or `--replace` would destroy
  the 1.0 rows). Proposed version-aware ids + schema v5 provenance columns
  (Q2). Also: `_fit_diagnostics` and `fit_fig` call the Gordon forward model
  directly and must dispatch to the robust one.
- **Cost.** BING's own benchmark puts `robust_hybrid` at 0.146× Gordon's
  `log_prob` rate (5.7k vs 38.9k calls/s) before the inelastic kernels →
  ~1–2 min CPU/fit, ~6–12 h for ~16.6k fits on 50 cores. Affordable; the
  1.0 fit stage was CephFS-bound anyway, so the DB-local Job wrapper stays.
  JAX's per-worker XLA thread pool needs pinning in `init_worker`.
- **Backfill is four populations, not one.** Granules in the DB stop at
  2026-06-01 while profiles run to 07-06 → **2,356** profiles never had
  candidates (re-discover with `--replace`); **4,981** new BGC profiles
  (686 floats) since the selection was cut (live index count today);
  **36,683** never-matched in-window profiles (the August `match` plateau —
  mostly unmatchable, a re-pass is ~3 days for <1 %); plus ~475 never-
  ingested and 1 unfit matchup. Expect ~+2,000–2,500 matchups.
- **DB custody.** The canonical DB is the workstation/S3 merged copy; the
  PVC's `/data/full/pab.db` is stale (pre-`cdom_chl`, pre-NASA) and must be
  replaced before any Nautilus stage writes.
- **Environments.** No conda env has the full stack: `ocean14` has
  `robust`+`jax` but not `pab`/`argopy`; `os_313` the reverse. The image
  needs `retrieve-or-bust` + `jax`/`flax`/`optax`/`jaxtyping` added.

Wrote the **Plan** (config delta, the eight PAB code changes, cost, the
sized backfill table, DB custody, an 8-step sequence) and **Q1–Q12** under
Q&A → Planning, each with a recommendation: version `2.0`; version-aware
`fit_id` + schema v5; geometry from L1B (else computed); `robust_hybrid` +
Raman + Chl-fl, CDOM-fl off, `B_p` fixed, extend `wave_max` to 720 nm;
backfill A+B+D now and C only if a coverage/CMR check says the pool changed;
DB custody on the PVC during the run; 2.0 as the report headline with a
1.0-vs-2.0 section; defer the bulk-artifact publish; develop in `ocean14`;
record git SHAs in `pkg_versions`; keep the MCMC length; a 100-matchup
leading slice as the gate. No code changed; nothing written outside this
doc. Ran directly on Fable 5.1 (no delegation needed — the work was
reading and synthesis).

### 2026-09-14 (Planning Task 2 — folded in Q1–Q12; verified L1B geometry + free-B_p layout; revised Plan; posted R1–R9)

Read the twelve answers. Three of them change the shape of the run rather
than just a knob: **v1.0 and v2.0 fits live in separate databases**
(Q2/Q6), **`B_p` is a free parameter** (Q4b), and geometry comes from the
**L1B granule** (Q3 = A). Everything else landed on the recommendation
(2.0; version-aware `fit_id` + schema v5; `robust_hybrid` + Raman + Chl-fl,
CDOM-fl off; `wave_max=720`; backfill A+B+D only; 2.0 headline + one
comparison section; defer the bulk publish; `ocean14`; SHAs in
`pkg_versions`; keep the MCMC length; a reviewed 100-matchup slice).

**Verified before revising (read-only):**

- **L1B geometry works.** For the cached production granule
  `PACE_OCI.20250309T131631.L2.OC_AOP.V3_2.nc`, a CMR search on
  `PACE_OCI_L1B_SCI` returns the same-stamp `…L1B.V3.nc` (1.8 GB; each
  granule listed twice — dedupe by name). Lazy `open_datatree` over
  `earthaccess.open` reads `geolocation_data/{solar_zenith, sensor_zenith,
  solar_azimuth, sensor_azimuth}` in 7.6 s out-of-region; the grid is the
  same 1709×1272 and lat/lon are **identical** at the matched pixel
  (868, 142). The real angles there — `theta_s` 29.47°, `theta_v` 54.58° —
  show why the cheap options were rejected: the scan-line `csol_z` is 1.8°
  off and a nadir assumption would be 55° off.
- **Free `B_p` is a trailing parameter** in BING's vector (`log_prob` peels
  `params[-1]`; `ndim` 5 → 6; walkers stay at 16). PAB's
  `extract_quantities` splits the flattened chain into `a`/`bb` params by
  `nparam_a` and would hand `eval_bbnw` a stray column — the peel must be
  added, along with `B_p` in the initial guess / bounds / names.
- **Branch state**: `full-inelastic` is 94 commits ahead of `develop` and
  121 ahead of `main`; `bing` (`bf56f6d`) and `retrieve-or-bust`
  (`dfab27c`) working trees are clean, so SHAs are meaningful as-is. 11,494
  distinct granules carry the 14,610 matchups (sizes the geometry stage).

**Plan revisions:** a new §0 table of locked decisions; a new §1 describing
the two-database layout (`v1/` frozen incl. a copy to `s3://pab/v1/`; `v2/`
= v1 minus the BING 1.0 fits, keeping the NASA-GIOP rows; backfill into v2
only; `--compare-db` for the 1.0-vs-2.0 section; version-aware ids kept as
a merge guard); §2 rewritten around the verified L1B path and the 6-param
fit; §3 gains the `B_p` plumbing, a **parallel `geometry` stage** writing
`theta_s/theta_v/dphi/geom_source` onto `matchup_pixels` (keeping the ~4 s
L1B open out of `fit`'s serial parent loop — ~19 h otherwise), the DB-split
helper, `--compare-db`, and a 100 Gi memory note for JAX workers; §4 drops
gap C; §5 is now a 10-step sequence with the DB split first and JXP's slice
review as the explicit gate.

**Round 2 (R1–R9)** asks to confirm the two-DB layout and contents, the
`B_p` prior + a diagnostic B_p-fixed slice for attribution, geometry on the
pixels table with strict skip-if-missing, keeping 720 nm with a red-edge
check, "end = today" as the standing backfill rule, NASA-GIOP on the
workstation after the fit, figure scope, the RTD merge that two reports now
wait on, and the order of the code work (recommendation: DB split first).
No code changed; the one network action was the read-only L1B check. Ran
directly on Fable 5.1.
