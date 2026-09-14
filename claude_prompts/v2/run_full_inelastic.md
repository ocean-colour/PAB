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

## Tasks

### Planning

1. Read all the files in the context.  We wish to develop a plan to re-run the BING analysis in Nautilus with the new RoB RT emulator.  We will also need to backfill the missing matchups from the original run.  Have a discussion with me on the plan for this work.  Ask me a series of questions in the Q&A section.  Use Fable if you can.  Log your work.

2. I have answered your first round of questions.  See my answers, update the Plan, and then ask me another round.  Use Fable if you can. Log your work.

## Plan

*Drafted 2026-09-13 after reading the context set (`HOWTO.md`, both design
docs, the three run logs) and checking the current state read-only: the
production DB, the BING/`robust` code, a cached PACE granule, the Nautilus
namespace, `s3://pab`, and the live Argo index. Numbers below are measured,
not recalled. Open decisions are in **Q&A → Planning**; the plan is written
against my recommendations there and will be revised once answered.*

### 1. What changes in the fit — and what BING needs from PAB

**Production `1.0` fit** (`pab/fit/models.py::FitConfig` →
`bing.parameters.standard.expb_pow`): `ExpBricaud`+`Pow`, 400–700 nm,
`nsteps=10000`/`nburn=1000`/16 walkers, and the **elastic Gordon** forward
model — `rt_dict['rt_backend']` defaults to `'gordon'`, `include_Raman=False`,
no fluorescence.

**Target `2.0` fit:** same model pair, priors and MCMC length, but
`rt_backend='robust_hybrid'` (the RoB emulator: ZTT analytic backbone + the
learned HydroLight-trained correction, valid 350–750 nm — our 400–700 nm
window sits inside), `include_Raman=True`, `include_Chl_fl=True`,
`include_CDOM_fl=False` (per the Goals). BING's `rt_dict_from_p` already
picks these up from the parameter tuple, and `p_ntuple.gen` accepts
arbitrary kwargs, so the BING side is ready (PR #29 `rob_rt` merged; the
project has adopted `robust`'s inelastic path — `bing/.claude/skills/
inelastic-rrs`). Three BING requirements fall on PAB:

1. **Geometry is mandatory.** A robust backend refuses to fit without an
   `ObsGeometry(theta_s, theta_v=0, dphi=0)` — `theta_s` is *never*
   defaulted (`bing.rt.defs.validate_rt_dict`). **PACE L2 AOP granules carry
   no per-pixel angles**: I inspected a cached V3.2 granule — `l2prod = Rrs
   Rrs_unc aot_865 angstrom avw nflh`; the only geometry is
   `scan_line_attributes/csol_z` (centre solar zenith per scan line) and
   `navigation_data/tilt`. PAB must source `theta_s` (and ideally
   `theta_v`/`dphi`) itself — see **Q3**.
2. **Fluorescence needs `a_ph`.** `include_Chl_fl` requires the Bricaud
   model to have `set_aph(Chl)` called; PAB already seeds Chl from the
   float's mixed-layer `chla` (0.1 fallback) via `init_other_bits`, so this
   works as-is. The quantum yield `phi_C` is a **fixed** 0.02 in BING (no
   free `phi_C` in the MCMC), emission shape `double_gaussian=True`.
3. **Downwelling irradiance.** With Raman on and no `Ed` supplied, `robust`
   falls back to its packaged L23 `Ed` spectra interpolated in `theta_s`
   (documented default). PACE L2 has `F0` but no `Ed`; accept the fallback.

### 2. PAB code work (before anything runs at scale)

| # | Change | Where |
|---|---|---|
| a | `FitConfig` gains `rt_backend`, `include_Chl_fl`, `include_CDOM_fl` (False), `phi_C`, `Bp_value`/`fit_Bp`; `build_models` forwards them to `standard.expb_pow`. | `pab/fit/models.py` |
| b | Geometry: derive per-pixel `ObsGeometry` for the fitted pixel (source per **Q3**); thread it as the 5th tuple element into `chisq_fit.fit` and `fit_one`; record it on the fit row. | `pab/pace/{cloud,extract}.py`, `pab/fit/run.py` |
| c | `_fit_diagnostics` and `pab.plotting.fit_fig` call `calc_Rrs_from_models` (Gordon) directly → dispatch to `calc_Rrs_from_models_robust(..., geom=)` when the backend is robust, else the χ²/AIC/BIC and the fit figures are computed with the *wrong* forward model. | `pab/fit/run.py`, `pab/plotting/fit_fig.py` |
| d | **Identity + provenance.** `fit_id = {matchup}_{ix}_{iy}_{model_pair}` is unchanged between 1.0 and 2.0, so `build_fits` would *skip every matchup* (or, with `--replace`, overwrite the 1.0 rows — exactly what the versioning convention forbids). Version-aware `fit_id` + new `fits` columns (`rt_backend`, inelastic flags, `phi_C`, `theta_s/theta_v/dphi`) → **schema v5**. See **Q2**. Add `robust` (+ git SHAs of `bing`/`robust`, which both report `0.0.dev0`) to `pkg_versions`. | `pab/db/schema.py`, `pab/fit/{run,artifacts}.py`, `pab/config.py` |
| e | Report/metrics select by `model_pair` today; they must select by `pab_version` (or config) so the site shows 2.0 and can compare 2.0 vs 1.0 — **Q7**. | `pab/metrics/compare.py`, `pab/report/rst.py` |
| f | Worker hygiene: JAX pays a ~0.2 s JIT per process (fine) but spawns its own XLA CPU thread pool → 50 workers × N threads oversubscribe the pod. Pin XLA to 1 thread in `pab.parallel.init_worker` (alongside the BLAS caps). Note `prepare_spectrum` drops non-finite bands, so `nwave` varies per pixel → one recompile per distinct shape (cheap). | `pab/parallel.py` |
| g | Environment/image: `retrieve-or-bust` (2.2 MB package) + `jax`/`flax`/`optax`/`jaxtyping` added to the staged build (`nautilus/build_image.sh`, `Dockerfile`); image tag `pab:2.0.0`. No conda env currently has everything: `ocean14` has `robust`+`jax` but not `pab`/`argopy`; `os_313` has `pab`/`argopy` but not `robust`/`jax` — **Q9**. | `Dockerfile`, `nautilus/build_image.sh` |
| h | Tests for a–f; a toy-size robust fit under `importorskip("robust")`; `ruff` clean. | `pab/tests/` |

**Cost.** BING's benchmark: `gordon` 38.9k `log_prob` calls/s vs
`robust_hybrid` 5.7k/s (**6.9× slower**, elastic); the Raman + fluorescence
kernels add on top. A fit is 16 walkers × 11,000 steps ≈ 176k calls → ~31 s
of forward model at hybrid-elastic rates, plausibly **1–2 min CPU/fit**
inelastic (to be measured in the leading slice, **Q12**). ~16.6k fits /
50 cores ≈ **6–12 h** — the 1.0 fit stage was CephFS-bound, not CPU-bound,
so the DB-local Job wrapper in `nautilus/full_fit_job.yaml` stays.

### 3. Backfilling the missing matchups (sized from the production DB, 2026-09-13)

Production: 881 floats / 54,031 profiles / 67,435 granules / 14,610 matchups
(14,609 BING fits, 1.0) + 14,609 NASA-GIOP rows (1.1). Profiles run to
2026-07-06 (the day the selection was cut) but **granules stop at
2026-06-01** — NASA's forward stream had not reached June when `discover`
ran. Four distinct gaps:

| Gap | Size (measured) | Fix | Expected new matchups (≈28 % match rate) |
|---|---|---|---|
| **A** — ingested but never had candidates (2026-06-02 → 07-06) | **2,356** profiles | `discover --profiles-csv <subset> --replace` (the coverage-skip test would otherwise skip them again) → `match` | ~650 |
| **B** — new profiles since the selection was cut | **4,981** profiles / 686 floats (live `bgc-s` index query today, BBP700-or-CHLA, 2026-07-06 → 09-14) | new selection CSV → `ingest` → `discover` → `match` | ~1,400 |
| **C** — the `match` plateau: positioned, in-window, never matched | **36,683** profiles (≤ 2026-06-01) | mostly genuinely unmatchable (no cloud-free coincident granule); includes the stall/timeout casualties (~1 wedged read per 86 profiles, then a 120 s skip). A full re-pass costs ~3 days of `match` and yielded <1 %/pass in August. Cheap first step: `nautilus/coverage_check.py` (DB-only) to count profiles with ≥1 candidate but no matchup, and a CMR check for newer PACE reprocessing (all 67,435 granules are V3.2). **Q5** | unknown, likely small |
| **D** — odds and ends | 399 profiles without a position (unmatchable); 1 matchup without a fit (`5906568_97…`); ~475 of the original 54,506 selection never ingested (argopy transients) | re-attempt ingest for the 475; the 1 fit re-runs naturally under 2.0 | ~130 |

Total ≈ **+2,000–2,500 matchups** → **~16.6–17.1k fits** under 2.0. The
NASA-GIOP baseline (`python -m pab.fit.nasa_giop`, idempotent, 4 s/matchup)
then needs ~2.5 h + ~90 GB of scratch cache for the new matchups only.

**DB placement matters (lesson #1).** The canonical DB is the workstation
`$PAB_DATA_DIR/full/pab.db` = the published `s3://pab/full/pab.db`
(sha-verified 2026-09-11, 169,938,944 B). The Nautilus PVC copy
`/data/full/pab.db` is **stale** (pre-`cdom_chl`, pre-NASA). Before any
Nautilus stage runs, the merged DB is uploaded to the PVC and becomes the
single writer's copy; the workstation copy is read-only until the run's DB
comes back. **Q6**.

### 4. Proposed sequence

0. **Code + local validation** (workstation): §2 a–h; fit 3–5 real
   matchups from cached granules under both configs; confirm the robust
   path, geometry, provenance columns, figure/diagnostic dispatch.
1. **Image `pab:2.0.0`** (+`robust`/`jax`), `nautilus/validate_job.yaml`
   smoke test in-pod (5 profiles → 1 fit) with the 2.0 config.
2. **Stage the canonical DB** on the PVC; **backfill** ingest (B + D) →
   discover (A + B, `--replace` for A) → match — existing Job manifests,
   lazy NASA-S3 reads, `--jobs 16` for match (memory-bound). All new
   `matchups`/`mld_summary` rows stamp 2.0.
3. **Leading slice** (~100 matchups, `fit` 2.0 in-pod): measure s/fit,
   χ² and acceptance distributions, `bbp700(2.0)/bbp700(1.0)` on the same
   pixels — the go/no-go gate (**Q12**).
4. **Full `fit` 2.0** over all ~16.6k matchups (DB-local wrapper,
   `--jobs 50`, chains under version-distinct ids; +~20 GB on the PVC).
5. **NASA-GIOP** for the new matchups (workstation driver, as before).
6. **figure → report → `--emit-site`**; site headline = 2.0 with a
   1.0-vs-2.0 comparison section (**Q7**); publish DB → `s3://pab/full/`,
   backup → `AIOcean:PAB/` (dated name), user pushes `report_site/` for RTD.
7. **Verify & close out**: provenance (every 2.0 row stamped; 1.0/1.1 rows
   byte-unchanged), integrity, docs (`HOWTO.md`, `PAB_implementation.md`,
   `db_schema.rst`), run report.

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
