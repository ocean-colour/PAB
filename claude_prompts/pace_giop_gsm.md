# Grabbing PACE GIOP and GSM matchups

## Goals

We have performed our own analysis of the PACE data with the BING algorithm.  For comparison, we would like to grab the GIOP and GSM outputs that are provided by the PACE team.  We would like to use these to compare our own results with the PACE team's results.

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
- The logs in the prompt docs: `claude_prompts/first_runs.md`, `claude_prompts/nautilus_prompts.md`, `claude_prompts/run_full_pipeline.md`.


## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below



### Tasks

1. Read all the files in the context.  Then scour the NASA PACE website for infomration on the GIOP and GSM products.  These will be provided as IOP outputs.  Before proceeding, have a discussion with me on the plan for this work.  Ask me a series of questions in the Q&A section.  Use Fable if you can.  Log your work.

2. I have answered your questions.  Read them and ask me any follow-up questions you may have.  Modify the plan as needed.  Log your work. Use Fable if you can.

3. Ok, read my answer to Q6, update the plan and then proceed to work on the dev suite of matchups.  Log your work. Use Fable if you can.

4. The test was a success.  Generate a set of prompts under the Full Run section below.  Log your work. Use Fable if you can.


### Full Run

The dev-set prototype validated the ingest end-to-end (see **Reports → Task 3**).
These prompts take it to production: close the known uncertainty gap *first* (so
the retrofit ingests everything in one pass, no backfill), retrofit every
BING-fit matchup onto the real production DB, wire the "BING vs NASA GIOP"
comparison into the published RTD report (Q5), publish, and close out.

**Numbers that size the run** (queried read-only from the production DB,
2026-09-08): 14,610 matchups, **14,609 with a BING fit** (the ingest
population), sharing **11,493 unique AOP granules** → 11,493 IOP-granule
downloads. At the prototype's ~42 MB/IOP granule that is **~0.5 TB** of cache
(9.5 TB currently free on `/mnt/tank` — fits comfortably; delete afterwards),
and at the prototype's ~3 s/matchup end-to-end, roughly **~12 h serial** — an
overnight run, so no parallelism is needed unless Full-Run task 2's measured
rate says otherwise.

**⚠️ One canonical DB (the run_full_pipeline lesson #1).** The
mission-production DB is at **`$PAB_DATA_DIR/full/pab.db`**
(= `/mnt/tank/Oceanography/data/Color/PAB/full/pab.db`; `/home/xavier/Oceanography`
is a symlink to `/mnt/tank/Oceanography`) — **not** `$PAB_DATA_DIR/pab.db`
(doesn't exist) and **not** `/mnt/tank/Oceanography/data/PAB/` (holds only the
old pilot DB). The Task 3 report's "`$PAB_DATA_DIR/pab.db`" reflected that
session's environment, not this one. Pass the explicit DB path everywhere;
never let a default resolve it. This is also the DB published at
`s3://pab/full/pab.db`, so publishing (task 5) must re-push it.

#### Full Run Prompts

1. Execute the 1st task in Full Run Tasks below
2. Execute the 2nd task in Full Run Tasks below
3. Execute the 3rd task in Full Run Tasks below
4. Execute the 4th task in Full Run Tasks below
5. Execute the 5th task in Full Run Tasks below
6. Execute the 6th task in Full Run Tasks below

#### Full Run Tasks

1. **Close the uncertainty gap before the retrofit.** NASA's IOP files carry
   `aph_unc_442`/`adg_unc_442`, but `ocpy.pace.io.load_iop_l2` doesn't read
   them, so the prototype's `adg_442`/`aph_442` landed with no per-pixel
   uncertainty (Reports → Task 3, "Known gap"). Fix the loader in the `ocpy`
   working tree (`/home/xavier/Oceanography/python/ocpy`) to read both fields,
   then extend `pab.pace.iop.extract_iop_quantities` to attach symmetric
   credible intervals to `adg_442`/`aph_442` the same way `bbp_442` already
   gets one from `bbp_unc_442` (degrading gracefully — no interval — when the
   loader/file lacks them, so old caches and tests still pass). Tests in both
   packages; `ruff` clean. Re-verify on one real granule (any of the three
   prototype matchups) that the uncertainties come through with plausible
   magnitudes. Doing this *now* means the 14,609-matchup retrofit ingests
   uncertainties in a single pass instead of needing a second sweep. Log your
   work. Use Fable if you can.

2. **Leading slice against the real production DB (count + rate first).** Wire
   a thin, resumable entry point for `pab.fit.nasa_giop.build_nasa_giop` — a
   `--stage`-style hook on the `pab` CLI or a small driver script, whichever is
   less code; it needs `--db`, `--cache-dir`, an optional matchup limit/subset,
   and file logging. Then run a **~100-matchup leading slice** against the
   *real* `$PAB_DATA_DIR/full/pab.db` (safe: idempotent, additive, stamped
   `pab_version = "1.1"` on parallel `fits` rows — the BING `1.0` records are
   untouched by design). Report: (a) measured s/matchup and MB/granule →
   re-project the full ~12 h / ~0.5 TB estimates; (b) the **pixel-distance
   distribution** — the prototype's 3/3 landed at 0.0000 km; if a non-trivial
   fraction of the slice lands > ~1.5 km (more than one pixel) from the BING
   pixel, **pause and investigate** before the full send; (c) failure count
   and causes. **Disk gate:** if the projected cache exceeds ~1 TB, decide
   (evict-as-you-go vs. proceed) before task 3. Log the measured rates + the
   projection. Use Fable if you can.

3. **Full retrofit — all 14,609 BING-fit matchups.** Run the ingest over the
   full population against `$PAB_DATA_DIR/full/pab.db` (the leading slice's
   ~100 skip via idempotency). Run it resumably in the background with output
   to a log file; it is safe to interrupt and resume (skip is keyed on
   `matchup_id`). Expect a small transient-failure tail (downloads over
   `earthaccess`); re-run to sweep failures until the failed list is stable,
   then report the irreducible failures with causes. **Close-out checks:**
   `fits` count for `algorithm = 'NASA_GIOP'` ≈ 14,609 minus irreducible
   failures, all stamped `pab_version = "1.1"`; BING row count and
   `pab_version = "1.0"` population unchanged; a final no-op re-run shows
   `written: []`, no duplicates; summarize the pixel-distance and
   `bbp_442`/`bbp700` ratio distributions as a sanity check. Then **delete the
   ~0.5 TB IOP granule cache**. Log counts, wall-clock, failure rates. Use
   Fable if you can.

4. **Wire the comparison into the RTD report.** Add the "BING vs NASA GIOP"
   comparison to the report layer (`pab.report.rst` + `pab.metrics.compare`),
   mirroring the existing satellite-vs-float `b_bp` treatment (Q5): scatter
   (interactive, like the existing Bokeh figures) + summary stats via the
   quantity-agnostic `log_comparison`, built on `gather_nasa_giop`. **Label
   the 442 nm-vs-700 nm `bbp` mismatch explicitly in the figure/table** (Q3 —
   no spectral adjustment), and add a short methods-page note documenting why
   GSM is absent (Q1: not an operationally-distributed PACE product — a NASA
   availability fact, not a PAB gap) plus the `pab_version = "1.1"` provenance
   of the NASA rows. Tests for the gatherer→page path; then regenerate the
   site sources (`pab --db "$PAB_DATA_DIR/full/pab.db" --emit-site report_site`)
   and preview with `sphinx-build` (HOWTO §7a). Do **not** commit — git is the
   user's. Log your work. Use Fable if you can.

5. **Publish.** Three artifacts, per HOWTO §7: (a) tell the user
   `report_site/` is ready to commit + push so RTD rebuilds (user does the git
   ops), and verify the RTD build once pushed; (b) re-upload the updated
   `pab.db` to **`s3://pab/full/pab.db`** via `NautilusS3Backend` (it now
   carries the NASA-GIOP rows; the currently-published copy predates them);
   (c) re-sync the backup to **`AIOcean:PAB/`** via rclone (Nautilus is not
   backed up). Confirm the public URL serves the new DB (size/hash). Log what
   was published where. Use Fable if you can.

6. **Verify & close out.** Spot-check a handful of matchups end-to-end (NASA
   values vs. the granule, sibling BING/NASA rows sharing `matchup_id` +
   `pixel_id`, report page rendering them correctly). Update
   `docs/design/PAB_implementation.md` (§5d.3 — "BING vs NASA L2 IOP" is now
   ingested + published), `HOWTO.md` (the NASA-GIOP ingest entry point and the
   `"1.1"` version note), and `docs/db_schema.rst` if it enumerates
   `algorithm`/quantity values. Write a short full-run report (counts,
   timings, failure tail, the pixel-distance result at scale, follow-ups —
   e.g. the deferred GSM decision). Log your work. Use Fable if you can.


## Plan

**Research finding that reshapes the scope (see full research summary in the
2026-09-08 Log entry): GSM is not an operationally-distributed PACE product.**
NASA/OB.DAAC provides exactly **one** L2 IOP suite for PACE OCI —
`PACE_OCI_L2_IOP` (currently v3.2) — produced with the **GIOP** algorithm
(default configuration, "GIOP-DC"; Werdell et al. 2013). A CMR sweep of every
`PACE_OCI_L2*` and `*GSM*` short name turns up no PACE GSM product at all —
GSM (Garver-Siegel-Maritorena) survives in NASA's operational chain only as an
alternate `l2gen` configuration (`iop_opt=2`) that is never run for standard
distribution, plus legacy **Level-4** GSM products for older sensors
(SeaWiFS/MODIS/MERIS) that don't apply here. So "grab the GIOP and GSM
outputs" as originally framed is really "grab GIOP (readily available) and
decide what, if anything, to do about GSM (not available without running
`l2gen`/OCSSW ourselves)."

**`PACE_OCI_L2_IOP` at a glance** (Provisional maturity, same
`us-west-2`/Earthdata-Cloud bucket as `PACE_OCI_L2_AOP`, `earthaccess`-searchable
identically):
- Wavelength-resolved `a`, `bb`, `aph`, `Kd` on a 19-band `wavelength_3d` axis
  (400–720 nm) — **not** the 172-band Rrs grid.
- Scalar-at-442-nm fields: `adg_442`, `bbp_442`, `adg_s`, `bbp_s`, `rrsdiff`,
  plus uncertainties `aph_unc_442`, `adg_unc_442`, `bbp_unc_442`. No
  wavelength-resolved adg/bbp arrays, no spectral uncertainties beyond 442 nm.
- Same 1 km / swath geometry and `l2_flags` masking as the AOP product PAB
  already reads.

**Where this lands in PAB.** The design doc already reserved this exact seam —
`ocpy.pace.io.load_iop_l2(fn)` as the loader, and a `NASA_L2IOP_*` namespace
parallel to `BING_ExpBPow_*` in `fit_results` — and `PAB_implementation.md`
(§5d.3) explicitly flags "BING vs NASA L2 IOP" as implemented-but-not-ingested,
pending exactly this ingest. So the shape of the work is: (1) for each existing
matchup's PACE AOP granule, locate/fetch the co-temporal `PACE_OCI_L2_IOP`
granule for the same overpass; (2) extract NASA's IOPs at the *same* pixel(s)
already used for the BING fit (reusing the nearest-pixel/flag-masking
machinery generically); (3) persist as namespaced `NASA_GIOP_*` rows in
`fit_results`, keyed to the existing `fit_id`; (4) extend
`pab.metrics.compare` with a NASA-GIOP gatherer/comparator (the quantity-agnostic
`log_comparison` already handles this — see `PAB_design.md` "BING vs. NASA L2
IOP" metric); (5) decide whether/how this surfaces in the RTD report.

Open questions on GSM handling, retrofit scope, storage/versioning, and
reporting are below — answer inline, then I'll proceed.

**Plan update (post Q1–Q5):** Scope is now **GIOP-only** — GSM is dropped
outright (Q1: A), with the product-availability limitation documented in the
report methods rather than treated as a PAB gap. Work proceeds on the **dev
set** (4 matchups) first; the full 14,610-matchup retrofit waits until the
prototype is validated end-to-end. One substantive change to step (3): the
`NASA_GIOP_*` rows will **not** attach to the existing BING `fit_id` — since
`fit_results` inherits all provenance (`pab_version`, `created`, `algorithm`)
from its parent `fits` row, reusing the BING fit would pin the NASA data to
the BING fit's `pab_version = "1.0"` instead of the new `"1.1"` (Q4). Instead,
each matchup/pixel gets a *parallel* `fits` row with `algorithm = 'NASA_GIOP'`
and its own `fit_id` (see Q6). The 442 nm-vs-700 nm `bbp` mismatch is deferred
to analysis (Q3), and the "BING vs NASA GIOP" scatter + summary stats go into
the published RTD report (Q5).

**Plan update (post Q6):** Q6 confirmed the **parallel-row** design — NASA-GIOP gets its own `fits` row (`algorithm='NASA_GIOP'`, BING/MCMC columns NULL) rather than piggybacking on the BING `fit_id`, so provenance is never silently misattributed. With all six questions settled, this turn moved from discussion to **implementation**: the ingest pipeline was built (`pab/pace/iop.py`, `pab/fit/nasa_giop.py`, `gather_nasa_giop`), `pab_version` bumped to `"1.1"`, and a three-matchup prototype ran end-to-end against real NASA Earthdata Cloud granules on a scratch copy of the production DB. See **Reports → Task 3** for the outcome — the headline result is that the IOP-granule nearest-pixel search landed at **0.0000 km** from the recorded BING-fit pixel on all three matchups. The full 14,610-matchup retrofit against the real `$PAB_DATA_DIR/pab.db` awaits go-ahead after review of that prototype.

## Q&A

**Q1 — GSM: how do we handle it, given it isn't a downloadable product?**
- **A — Drop GSM, GIOP only.** Simplest; document why in the report/methods
  page (a factual NASA-product-availability limitation, not a PAB gap).
- **B — Stand up OCSSW/`l2gen` and generate GSM ourselves** (`iop_opt=2`) for
  the matchup granules. A real undertaking: installing/configuring OCSSW,
  learning its L1B→L2 reprocessing invocation, and validating our GSM output
  against nothing NASA-published to check against. Substantially larger scope
  than this prompt doc as written.
- **C — Defer GSM as a explicit follow-up item**, proceed with GIOP now, revisit
  B later if there's real demand for it.

*(My recommendation: **C** — get the GIOP comparison working first since it's
the readily-available, design-anticipated piece; treat GSM as a separate,
scoped decision later rather than blocking on it now.)*

**Your answer:** Answer A, drop GSM

**Q2 — Retrofit scope.** Fetch/extract GIOP IOPs for the **full existing
production population** (14,610 matchups, `pab_version = "1.0"`, the Nautilus
mission run), or prototype first on the **dev set** (the 4 matchups currently
on the beta RTD site) before committing to the full retrofit?

*(My recommendation: dev set first — it's a new granule-join + extraction path
that's never been exercised, worth proving out on 4 before a full-population
run.)*

**Your answer:** Prototype first on the dev set

**Q3 — Storage & the 442 nm-vs-700 nm mismatch.** Store as namespaced
`fit_results` rows (`NASA_GIOP_bbp_442`, `NASA_GIOP_adg_442`,
`NASA_GIOP_aph_442`, `_unc` variants) linked to the existing `fit_id`, matching
the `NASA_L2IOP_*` scheme the design doc already reserved? And: NASA's GIOP
`bbp` is only reported at 442 nm while BING's headline `bbp` is at 700 nm — the
design doc already flags this as "approximate" when it's eventually compared
(`PAB_design.md`, *Comparison & metrics*). Confirm we keep that caveat
(labelled explicitly in any figure/table) rather than trying to spectrally
adjust one to match the other?

**Your answer:**  Yes.  And I will deal with the 442 nm vs 700 nm mismatch in the analysis later

**Q4 — `pab_version` for this addition.** This only *adds* new
`NASA_GIOP_*` quantities alongside the existing BING results — it doesn't
change any BING output — similar in spirit to the Stage 10 CDOM/provenance
backfill, which was a documented exception to "new version = new records."
Keep the same `pab_version = "1.0"` for this addition, or bump to a new
version since it's new science content (a new comparison), not a pure
provenance backfill?

*(My recommendation: bump — unlike the Stage 10 backfill this adds a genuinely
new retrieved-quantity comparison, not just missing metadata on existing
records, so it's more consistent with the project's normal versioning
convention.)*

**Your answer:** Bump to a new version.  I suggest "1.1"

**Q5 — Reporting.** Add a "BING vs NASA GIOP" comparison (scatter + summary
stats, mirroring the existing satellite-vs-float `b_bp` comparison) to the
published RTD report, or keep this as an internal/DB-only comparison for now
(queryable via `pab.metrics.compare`, not yet surfaced to the community site)?

**Your answer:**  Yes.  Add a "BING vs NASA GIOP" comparison (scatter + summary stats, mirroring the existing satellite-vs-float `b_bp` comparison) to the published RTD report

**Q6 — Storage mechanics: parallel `fits` row instead of reusing the BING `fit_id`.**
Q3 proposed linking the `NASA_GIOP_*` rows to the *existing* BING `fit_id`, but
that quietly breaks the Q4 versioning decision: `fit_results` has **no
provenance columns of its own** — every row inherits `pab_version` /
`created` / `algorithm` / `model_pair` from its parent `fits` row (see
`pab/db/schema.py`; `fits.pab_version` is `TEXT NOT NULL`). Attaching NASA
quantities to a BING fit would therefore stamp them with that fit's
`pab_version = "1.0"`, not the new `"1.1"` — a silent provenance
misattribution. Also worth noting: the GIOP values aren't a "fit" in the BING
sense at all (no MCMC, no chains, no warm-start) — they're NASA's own product
values read off the granule, so the BING/MCMC-specific `fits` columns
(`nsteps`, `nburn`, `chains_path`, ...) simply don't apply.

**The clean fix, zero schema migration:** write a *separate, parallel* `fits`
row per matchup/pixel — the same shape the design doc already sanctions for a
second model pair ("a second model pair would write parallel columns...
without colliding") — with `algorithm = 'NASA_GIOP'`, `model_pair = NULL`, the
MCMC columns NULL, its own `pab_version = "1.1"`, and a `fit_id` following the
existing convention with the model tag swapped:
`{matchup_id}_{ix}_{iy}_NASA_GIOP` (mirroring
`pab/fit/run.py::make_fit_id`'s `{matchup_id}_{ix}_{iy}_{model_pair}`). The
`NASA_GIOP_*` rows attach to that fit_id at the **same pixel** (ix, iy) as the
BING fit, so the two fits are siblings sharing `matchup_id` + `pixel_id` but
differing in `algorithm`/`fit_id`. This reuses `Store.upsert` and the
idempotency machinery unchanged, and `gather_matchups`'s existing
`algorithm`/`model_pair` filtering extends naturally to pull NASA rows in
alongside BING's.

*(My recommendation: adopt the parallel-`fits`-row approach — it's the only
option that honors the `"1.1"` version bump without a schema migration, and it
keeps NASA product values cleanly distinguishable from BING fits.)*

**Your answer:** Ok, that's fine.

## Reports

#### Task 3 — NASA-GIOP ingest implemented; dev-set prototype validated

**What was built.** Two new modules plus a metrics gatherer, with `pab_version` bumped `"1.0"` → `"1.1"` in `pab/config.py` (and `setup.py`, matching the 1.0 precedent):

- **`pab/pace/iop.py`** — NASA-GIOP granule access & extraction.
  - `iop_source_for_aop(aop_source)` maps an AOP granule id/URL to its co-temporal IOP granule by substituting the filename tag `L2.OC_AOP.` → `L2.OC_IOP.`. This substitution was **verified against a live CMR search**: for production matchup granule `PACE_OCI.20260309T153836.L2.OC_AOP.V3_2.nc`, `earthaccess.search_data(short_name="PACE_OCI_L2_IOP", temporal=...)` returned exactly `PACE_OCI.20260309T153836.L2.OC_IOP.V3_2.nc` at the identical timestamp — NASA's IOP and AOP suites share filenames per overpass except for that one tag.
  - `open_iop_local(fn)` opens a local IOP granule via `ocpy.pace.io.load_iop_l2` (already present in the installed `ocpy` — nothing had to be written there), wrapped the same way `pab.pace.cloud.open_local` wraps the AOP reader (attaches `l2_flags` via `to_granule_ds`).
  - `nearest_pixel(ds, target_lat, target_lon)` finds the nearest pixel by great-circle distance **without** `l2_flags` screening — deliberately unlike `pab.pace.extract.nearest_valid_pixels`. The goal is to land on the *exact* physical pixel already selected for the BING fit, not an independently-chosen "nearest good" pixel on the IOP grid that could silently be a different location.
  - `extract_iop_quantities(ds, ix, iy)` reads `bbp_442`, `bbp_unc_442`, `bbp_s`, `adg_442`, `adg_s` (direct scalar fields) plus `aph_442` picked from the spectral `aph` array at the band nearest 442 nm (no dedicated scalar-at-442 field exists for `aph`). `bbp_442` gets a symmetric credible interval (value ± `bbp_unc_442`). **Known gap:** NASA's file carries `aph_unc_442`/`adg_unc_442`, but `ocpy.pace.io.load_iop_l2` does not read them, so `adg_442`/`aph_442` land with no per-pixel uncertainty. Not fixed this task.
- **`pab/fit/nasa_giop.py`** — the ingest driver.
  - `make_nasa_giop_fit_id(matchup_id, ix, iy)` → `"{matchup_id}_{ix}_{iy}_NASA_GIOP"`, mirroring `pab.fit.run.make_fit_id` with the model tag swapped for the algorithm name (the Q6 design).
  - `persist_nasa_giop(...)` upserts the parallel `fits` row (`algorithm='NASA_GIOP'`, `model_pair=None`, BING/MCMC columns NULL, its own `pab_version`) and the namespaced `NASA_GIOP_*` `fit_results` rows — idempotent, delete-then-insert on re-run, matching `pab.fit.artifacts.persist_fit`.
  - `ingest_nasa_giop_matchup(...)` looks up the matchup's rank-1 pixel and AOP `data_url`, derives the IOP URL, downloads via `pab.pace.cloud.download_granule` (the same robust streaming path as the existing off-cloud `--download` mode, not a lazy S3 byte-range read), opens locally, nearest-pixel searches against the *recorded* matchup-pixel lat/lon, extracts, persists.
  - `build_nasa_giop(...)` mirrors `pab.fit.run.build_fits`'s idempotent/skip/failed-batch shape (one bad matchup doesn't abort the run), restricted to matchups with a completed `BING` fit, with an optional `matchup_ids` subset — the dev-set-first mechanism. Skip-tracking is keyed on `matchup_id`, not a precomputed `fit_id`, because the actual pixel indices aren't known until the IOP granule's own search runs; an early draft got this wrong (computed a candidate `fit_id` from the AOP pixel's `ix`/`iy` up front) and was corrected before any real run.
- **`pab/metrics/compare.py`** — `gather_nasa_giop(store, *, model_pair="ExpBPow")` joins BING `bbp700` against NASA `bbp_442`/`adg_442`/`aph_442`, one row per matchup with both fits. The docstring repeats the 442nm-vs-700nm caveat so downstream users of the frame see it, not just readers of this doc.
- Public-API exports updated in `pab/pace/__init__.py` and `pab/fit/__init__.py`.

**A real bug found and fixed.** `pab.pace.cloud.download_granule` never called `earthaccess.login()` in a fresh process — the exact bug fixed for `open_s3` back in `first_runs.md` Task 2 (`'NoneType' object has no attribute 'get'`), but the fix had only ever been applied to `open_s3`. Discovered by hitting it: the first real end-to-end prototype run failed with exactly that error on the very first granule download. Fixed with the same one-line guard (`_ensure_earthaccess_login(earthaccess)` before the download), already a private helper in the same file; a regression test was added.

**The dev-set prototype run (real data, real network).** The environment has changed since Q2 was answered: `$PAB_DATA_DIR/pab.db` now holds the full **14,610-matchup mission-production database** (Nautilus full run), not the original 4-matchup beta set. Rather than mutate the live production DB for a prototype, the ingest ran against a **scratch copy**, and the real DB was verified untouched afterward (same size, same mtime). This is a **deliberate interpretation** of "prototype on the dev set" given the changed environment — not something the user explicitly re-confirmed — and the eventual full retrofit must run against the real `$PAB_DATA_DIR/pab.db`, not a copy.

Three matchups from three different floats were ingested for real, hitting live NASA Earthdata Cloud (real CMR-derived URLs, real downloads — ~10 s wall total including login):

- `7902226_43_PACE_OCI.20260309T153836.L2.OC_AOP.V3_2.nc`
- `1902347_28_PACE_OCI.20250208T011041.L2.OC_AOP.V3_2.nc`
- `1902373_68_PACE_OCI.20260427T062154.L2.OC_AOP.V3_2.nc`

**All 3 succeeded end-to-end.** The single most important result: **the nearest-pixel search on each IOP granule landed at 0.0000 km from the exact BING-fit pixel's recorded lat/lon, for all 3 matchups** — empirical confirmation (for these granules) that PACE's AOP and IOP suites share the same pixel grid per overpass. The code does **not** assume this — it always runs a real distance search rather than blindly reusing the AOP `ix`/`iy` — but the result is reassuring evidence the grids align in practice.

**Sanity check on values.** Extracted `bbp_442` came out ~1.4–1.8× higher than BING's `bbp700` for the same matchup — consistent with backscatter's expected blue→red spectral decrease, and NASA's own `bbp_s` slope (~1.8–2.0 across the three) predicts almost exactly this ratio over the 442→700 nm gap. This is evidence the pipeline extracts real, physically plausible NASA data — not a validated scientific comparison (that remains future work, per Q3's deferral of the wavelength-mismatch handling).

**Idempotency verified.** Re-running `build_nasa_giop` on the same 3 ids gave `written: []`, `skipped: [all 3]`, `failed: []`; `fits` count for `algorithm='NASA_GIOP'` stayed at 3, no duplicates.

**Hygiene.** 13 new tests (`test_pace.py` iop + login-regression, new `test_nasa_giop.py` persistence/end-to-end-mocked/batch behavior, `test_metrics.py` for `gather_nasa_giop`); full suite **205 passed** (from 192 at Task 1). `ruff check`/`ruff format --check` clean on every touched file (one pre-existing `zip()` `strict=` warning in `pab/pace/cloud.py` predates this task). The ~127 MB of downloaded IOP granules and the scratch DB copy were deleted — nothing persistent left behind beyond the code/test changes. Per the working agreement, changes are on disk but not git-committed.

**Explicitly not done yet:**
- The full 14,610-matchup retrofit onto the real production DB — next step, pending go-ahead after this prototype is reviewed.
- Wiring `gather_nasa_giop` into the RTD report (`pab.report.rst`) as the published "BING vs NASA GIOP" page (Q5: yes, eventually); this turn built and validated only the gatherer.
- The `aph_unc_442`/`adg_unc_442` gap in the `ocpy` loader.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-08 (Task 1 — researched PACE GIOP/GSM availability; drafted Plan + Q&A)

Read all four context docs (`HOWTO.md`, `PAB_design.md`, `PAB_implementation.md`,
plus the `first_runs.md`/`nautilus_prompts.md`/`run_full_pipeline.md` prompt logs)
to ground the plan in what's already built: the design doc already reserves a
`PACE_OCI_L2_IOP` secondary-baseline loader (`ocpy.pace.io.load_iop_l2`) and a
`NASA_L2IOP_*` namespaced-quantity comparison against BING, and
`PAB_implementation.md` §5d.3 explicitly flags this ingest as the one deferred
piece of the metrics/figures stage (implemented machinery, no data).

Delegated the NASA-product research to a **Fable** subagent (per the task's "use
Fable if you can"), scoped to 6 questions: whether PACE distributes separate
GIOP/GSM product suites, exact CMR short names, variables/resolution, maturity,
algorithm references, and access path. Key finding, confirmed via direct CMR
sweeps (`PACE_OCI_L2*` and `*GSM*` short names) and the official OB.DAAC file-
structure doc: **NASA does not distribute a GSM product for PACE (or any current
sensor) at L2** — only one IOP suite exists, `PACE_OCI_L2_IOP` (v3.2), produced
with **GIOP** (default config). GSM survives only as an unused `l2gen` option
(`iop_opt=2`) and as heritage Level-4 products for older missions (SeaWiFS/MODIS/
MERIS). So "grab GIOP and GSM" as originally framed isn't fully available
as-stated — GIOP is a straightforward download (same `earthaccess`/`us-west-2`
path as the AOP product PAB already uses; 19-band wavelength-resolved a/bb/aph/Kd
plus scalar 442 nm adg/bbp/uncertainties, Provisional maturity); GSM would require
running NASA's `l2gen`/OCSSW ourselves from L1B, a materially larger undertaking.

Wrote the **Plan** section (GIOP product summary + where it lands in PAB: fetch
the co-temporal `PACE_OCI_L2_IOP` granule per existing matchup, extract at the
same pixel used for BING, persist as `NASA_GIOP_*` `fit_results` rows, extend
`pab.metrics.compare`, decide on reporting) and five **Q&A** questions covering:
(Q1) how to handle the GSM gap (recommended: defer it, proceed with GIOP only for
now); (Q2) retrofit scope — dev set first vs. the full 14,610-matchup production
population (recommended: dev set, to prove out the new granule-join path before a
full run); (Q3) storage naming + the 442 nm (NASA) vs 700 nm (BING) wavelength
mismatch, confirming the design's existing "flag as approximate" stance; (Q4)
whether this addition keeps `pab_version = "1.0"` or bumps to a new version
(recommended: bump, since unlike the Stage 10 CDOM backfill this is new science
content, not a provenance patch); (Q5) whether the comparison gets published to
the RTD report or stays DB-only for now. Awaiting answers before proceeding. No
code changed this task.

### 2026-09-08 (Task 2 — read Q1–Q5 answers; found a versioning bug in the plan, asked Q6)

Read the five answers: **Q1** A (drop GSM entirely); **Q2** dev-set prototype
first; **Q3** yes to both the `NASA_GIOP_*` naming and deferring the 442-vs-700
nm mismatch to later analysis; **Q4** bump `pab_version` to `"1.1"`; **Q5** yes,
publish "BING vs NASA GIOP" to the RTD report. Before updating the Plan,
checked the answers against the actual schema (`pab/db/schema.py`) rather than
taking the Q3-proposed storage scheme at face value, since Q4's version bump
interacts with it.

**Found a real problem with the Q3 plan as written.** `fit_results` (the long
table holding namespaced quantities) carries **no provenance columns of its
own** — every row is keyed to a `fit_id` and inherits `pab_version`/`created`/
`algorithm`/`model_pair` from its parent `fits` row (`fits.pab_version TEXT
NOT NULL`, confirmed by reading the schema directly). So attaching
`NASA_GIOP_*` rows to the *existing* BING `fit_id` — what Q3 as originally
posed implied — would silently stamp them with that fit's `pab_version =
"1.0"`, not the new `"1.1"` from Q4. Also, NASA's GIOP values aren't a "fit"
in the BING sense (no MCMC, no chains, no warm-start) — they're NASA's own
product values read off a granule — so the `fits` table's BING/MCMC-specific
columns (`nsteps`, `nburn`, `chains_path`, ...) don't apply to them either.

**Proposed fix (zero schema migration):** write a *separate, parallel* `fits`
row per matchup/pixel with `algorithm = 'NASA_GIOP'`, MCMC columns NULL, its
own `pab_version = "1.1"`, and `fit_id = "{matchup_id}_{ix}_{iy}_NASA_GIOP"`
(mirroring `pab/fit/run.py::make_fit_id`'s existing
`{matchup_id}_{ix}_{iy}_{model_pair}` scheme) — the same shape the design doc
already sanctions for a second model pair. The `NASA_GIOP_*` `fit_results`
rows attach to that new fit_id, at the same pixel already used for the BING
fit, so the two fit rows are siblings sharing `matchup_id`/`pixel_id` but
differing in `algorithm`/`fit_id`/`pab_version`. This reuses `Store.upsert`
and `gather_matchups`'s existing `algorithm`/`model_pair` filtering unchanged.

Delegated the actual prose drafting (Plan-update paragraph + the Q6 entry, in
the doc's established voice) to a **Fable** subagent, feeding it the verified
technical finding above so it had no schema details to guess at; reviewed its
output against the schema before inserting — accurate, no fabrication.
Appended the Plan-update paragraph to the end of the existing Plan section and
added **Q6** (with recommendation: adopt the parallel-`fits`-row approach)
to the Q&A. No other new questions were needed — Q1–Q5 covered the rest of the
open decisions cleanly. No code changed this task; awaiting the Q6 answer
before implementing.

### 2026-09-08 (Task 3 — implemented + prototyped the NASA-GIOP ingest)

Q6 was confirmed ("Ok, that's fine."), so this turn moved from discussion to
implementation. Bumped `pab_version` "1.0"→"1.1" (`pab/config.py`, `setup.py`).
Built two new modules: `pab/pace/iop.py` (NASA-GIOP granule access —
`iop_source_for_aop` maps an AOP granule to its co-temporal IOP granule by a
filename-tag swap, verified against a **live CMR search**; `open_iop_local`
wraps the already-installed `ocpy.pace.io.load_iop_l2`; `nearest_pixel` does a
flag-free great-circle search so it lands on the *exact* BING-fit pixel rather
than an independently-chosen "nearest good" one; `extract_iop_quantities`
reads `bbp_442`/`bbp_unc_442`/`bbp_s`/`adg_442`/`adg_s` plus a
nearest-442nm-band `aph_442`) and `pab/fit/nasa_giop.py` (the ingest driver —
`persist_nasa_giop` writes the Q6-agreed **parallel** `fits` row
(`algorithm='NASA_GIOP'`) + namespaced `fit_results`; `ingest_nasa_giop_matchup`
downloads the IOP granule via the existing robust `download_granule` path and
extracts; `build_nasa_giop` mirrors `build_fits`'s idempotent/skip/failed-batch
shape, restricted to matchups with a BING fit, with an optional `matchup_ids`
subset for dev-set-first prototyping). Caught and fixed a bug in my own first
draft of `build_nasa_giop`: it precomputed a skip-check `fit_id` from the AOP
pixel's `ix`/`iy` before the IOP granule's own pixel search ran, which uses
different indices — fixed by keying skip-tracking on `matchup_id` instead.
Extended `pab/metrics/compare.py` with `gather_nasa_giop` (BING `bbp700` vs
NASA `bbp_442`/`adg_442`/`aph_442`, carrying the 442-vs-700nm caveat in its
docstring). Added 13 tests across `test_pace.py`, a new `test_nasa_giop.py`,
and `test_metrics.py`; full suite went 192→205 passed, `ruff` clean.

Ran the actual prototype against real data. Found the environment had moved
on since Q2: `$PAB_DATA_DIR/pab.db` is now the full 14,610-matchup production
DB (the original small dev set no longer exists as a distinct artifact), so I
copied it to a scratch location and ran the ingest there rather than mutating
the live production DB — a judgment call, not something explicitly
re-confirmed with the user. Doing so immediately surfaced a real, unrelated
bug: `pab.pace.cloud.download_granule` never calls `earthaccess.login()` in a
fresh process — the identical bug already fixed for `open_s3` in
`first_runs.md` Task 2, but the fix was never ported to `download_granule`.
Applied the same one-line guard and added a regression test.

With that fixed, ingested 3 real matchups (three different floats) against
live NASA Earthdata Cloud — all 3 succeeded (~10 s wall total). The standout
result: the IOP granule's nearest-pixel search landed at **0.0000 km** from
the recorded BING-fit pixel on all three, empirically confirming (for these
granules) that PACE's AOP and IOP products share the same pixel grid per
overpass — reassuring, though the code never assumes this (it always searches
rather than reusing the AOP index blindly). Extracted `bbp_442` values were
~1.4–1.8× BING's `bbp700` for the same matchups, consistent with the expected
blue-to-red backscatter spectral decrease given NASA's own `bbp_s` slopes — a
physically-sane sanity check, not a validated comparison. Confirmed
idempotency (re-run: all 3 skipped, no duplicates) and confirmed the live
production DB was untouched (same size/mtime throughout). Deleted the ~127 MB
of scratch downloads and the scratch DB copy afterward. Full report + design
detail in the new **Reports → Task 3** section. Not done yet: the full
14,610-matchup retrofit (awaiting go-ahead), wiring the comparison into the
RTD report site, and the `aph_unc_442`/`adg_unc_442` gap in the `ocpy` loader.

### 2026-09-08 (Task 4 — wrote the Full Run prompt set)

The prototype was declared a success, so this task authored the production
prompt set under **Prompts → Full Run**: six tasks taking the NASA-GIOP work
from validated prototype to published comparison. Before writing them, ground
truth was gathered rather than assumed — the production DB was queried
read-only: **14,610 matchups, 14,609 with a BING fit** (the ingest
population), sharing **11,493 unique AOP granules**, all `pab_version = "1.0"`,
and **zero `NASA_GIOP` rows** (confirming the Task 3 scratch run left no trace
in production). That sizes the run concretely: ~11.5 k IOP downloads × ~42 MB
≈ **~0.5 TB** cache (9.5 TB free on `/mnt/tank`) and ~**12 h serial** at the
prototype's ~3 s/matchup — overnight-feasible with no new parallelism, subject
to a measured-rate check.

Locating the DB surfaced a trap now flagged prominently in the Full Run
preamble: the mission DB is at **`$PAB_DATA_DIR/full/pab.db`**
(`/mnt/tank/Oceanography/data/Color/PAB/full/pab.db`), *not*
`$PAB_DATA_DIR/pab.db` as the Task 3 report's wording implied (that session's
environment differed), and *not* `/mnt/tank/Oceanography/data/PAB/` (pilot DB
only) — exactly the split-state failure mode `run_full_pipeline.md`'s lesson
#1 warns about, so the prompts require an explicit DB path throughout.

The six tasks, with the reasoning behind the ordering: (1) **close the
`aph_unc_442`/`adg_unc_442` loader gap first** (in `ocpy` +
`extract_iop_quantities`) so the retrofit ingests uncertainties in one pass
instead of needing a 14.6 k-row backfill later; (2) **leading slice** —
~100 matchups against the *real* DB (safe: idempotent, additive, `"1.1"`-
stamped) behind a thin resumable CLI/driver entry point, with gates on
measured rate, the pixel-distance distribution (prototype: 0.0000 km — pause
if a non-trivial fraction lands > ~1.5 km), and projected disk; (3) **full
retrofit** of all 14,609, background + resumable, sweep the transient-failure
tail until stable, close-out count/idempotency/provenance checks, then delete
the ~0.5 TB cache; (4) **report wiring** — the Q5 "BING vs NASA GIOP" scatter
+ summary stats via `gather_nasa_giop`/`log_comparison`, the explicit
442-vs-700 nm label (Q3), a methods note on GSM's non-availability (Q1), then
`--emit-site` + sphinx preview, no commits; (5) **publish** — user pushes
`report_site/` for RTD, re-upload `pab.db` to `s3://pab/full/pab.db` (the
published copy predates the NASA rows), re-sync `AIOcean:PAB/`; (6) **verify &
close out** — spot-checks, `PAB_implementation.md` §5d.3 / `HOWTO.md` /
`db_schema.rst` updates, and a short full-run report. Each prompt carries the
doc's standing "Log your work. Use Fable if you can." (this task itself ran
directly on Fable 5 — no delegation needed). No code changed this task.

### 2026-09-09 (Full Run Task 1 — closed the aph/adg uncertainty gap; verified on a real granule)

Closed the known gap from the Task 3 prototype: NASA's IOP files carry
per-pixel `aph_unc_442`/`adg_unc_442`, but `ocpy.pace.io.load_iop_l2` never
read them, so `adg_442`/`aph_442` landed in `fit_results` with no credible
interval. Two-sided fix:

- **`ocpy` (in `/home/xavier/Oceanography/python/ocpy`):** `load_iop_l2` now
  reads `aph_unc_442`/`adg_unc_442` when the file carries them, tolerating
  their absence (older files) — the fields are added to the returned dataset
  conditionally, everything else unchanged. Added
  `ocpy/tests/test_pace_io.py` (the module previously had **no** tests):
  a synthetic group-structured L2 IOP netCDF written with `netCDF4`,
  exercised both with and without the unc fields.
- **`pab.pace.iop.extract_iop_quantities`:** `adg_442`/`aph_442` now get the
  same symmetric credible interval `bbp_442` always had (value ± unc), and
  the raw `adg_unc_442`/`aph_unc_442` land as their own namespaced rows —
  but **only when the dataset carries the fields**; otherwise behavior is
  exactly the pre-fix one (no interval, no unc rows), so nothing breaks under
  an old `ocpy`. The existing extraction test now pins that degradation path
  explicitly; a new test covers the uncertainties.

**Verified on a real granule** (the Task 3 prototype matchup `7902226_43`,
`PACE_OCI.20260309T153836.L2.OC_IOP.V3_2.nc`, freshly downloaded from
Earthdata Cloud): both unc fields present and read; nearest-pixel search
again landed **0.0000 km** from the recorded BING pixel; extracted
`adg_442 = 0.0033 ± 0.0002` (~6 % relative) and `aph_442 = 0.0066 ± 0.0007`
(~11 %) — plausible magnitudes, in family with `bbp_442`'s ~6 %. Scratch
download deleted afterwards.

**Hygiene.** pab suite: 204 passed + the 2 BING-dependent tests
(`test_fit_spectrum_recovers_bbp`, `test_fit_figure_smoke`) failing on
`ModuleNotFoundError: No module named 'jax'` — an environment difference in
this shell's conda env (`os_313` lacks jax), **not** a regression: neither
test touches the changed code. New ocpy tests: 2 passed. `ruff check` clean
on every touched file in both packages. Ran directly on Fable 5. Per the
working agreement, changes in both working trees are on disk, not committed —
note the `ocpy` change must be committed/installed wherever the Full Run
Task 3 retrofit runs, or the retrofit silently reverts to no-uncertainty
ingest (the graceful degradation cuts both ways).
