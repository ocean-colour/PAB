# Running the full PAB pipeline

## Goals

The beta report (4 matchups, dev set) is live on Read the Docs and the reporting
layer is complete (Stage 9). Now run PAB **at scale** — the full BGC-Argo profile
selection through **ingest → discover → match → fit → figure → report** — and
publish the resulting community report. Do it **safely and resumably**: one
canonical data directory, idempotent stages, a version-stamped release.

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
- **Prior run log** — `claude_prompts/first_runs.md` (the dev-set run: the CMR
  500, the eager-cube fix, the `--download` path) and `claude_prompts/coding_stage9.md`.

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

## Prompts

1. Execute the first task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below
6. Execute the 6th task in Tasks below
7. Execute the 7th task in Tasks below

## Tasks

1. **Pin the run configuration (answer the Q&A first).** Record, for this
   production run: the single canonical `$PAB_DATA_DIR` and `--db`; where it runs
   (in-region `us-west-2` vs off-cloud `--download` + `--cache-dir`); the
   `pab_version` for the release; and the profile-selection source. Confirm with
   `pab --dry-run` (and `--download` echo) that the plan and paths are right.
   Log the pinned config.

2. **Assemble the full profile selection.** Produce the production `--profiles-csv`
   (the full BGC-Argo set per the Q&A scope), replacing the 10-row dev CSV.
   Sanity-check the count, the WMO/cycle coverage, and the lat/lon/time spread
   before committing to a multi-hour run. Log the selection size + provenance.

3. **Pilot on a subset first.** Before the full run, execute the whole pipeline on
   a **small representative slice** (e.g. one region or a ~50-profile sample) end to
   end — ingest → … → report — to shake out rate limits, disk, fit time, and the
   published report at non-trivial N. Extrapolate the cost. Log the pilot metrics.

4. **Ingest + discover.** Run `pab --stage ingest` (argopy fetch, MLD summaries,
   Argo Q&A figures) then `--stage discover` (CMR granule search). Expect argopy
   slowness / CMR transient 500s; both stages are resumable, so re-run to continue.
   Log counts (`profiles`, `granules`) and any failures.

5. **Match + fit (the heavy stages).** Run `--stage match` (with `--download` if
   off-cloud) to build matchups, then `--stage fit`. For the fit stage use the
   parallel/batch approach decided in Q&A (or chunk + resume serially). Monitor
   convergence on a sample (`diagnose-mcmc`). Log matchups written, fits
   written/failed, and wall-clock.

6. **Figure + report + publish.** Run `--stage figure` then `--stage report`;
   `pab --emit-site report_site`; preview locally (`sphinx-build`), then commit
   `report_site/` and push so RTD rebuilds. Confirm the summary coverage counts,
   the scatters/map, and that the galleries N-guard sensibly at scale. Decide
   bulky-artifact hosting (see Q&A). Log the published counts + the RTD build.

7. **Verify & close out.** Spot-check a handful of matchups (distance/Δt, fit
   quality, scene), confirm every record carries the release `pab_version`, update
   `docs/design/PAB_implementation.md` if anything changed, and write a run report
   (coverage, timings, failures, follow-ups). Log your work.

## Q&A

**Q1 — Scope of the full run?** The dev set is 10 profiles / 2 floats. What defines
"full"? (e.g. *all* BGC-Argo floats with `BBP700`+`CHLA` over a time window; a set
of regions; a specific float list; a date range aligned to PACE's mission, launched
2024.) This decides N (matchups, disk, fit time) and everything downstream.

**Q2 — Where do we run it?** In-region on AWS `us-west-2` (fast S3, the design
target — recommended at scale) or off-cloud on the workstation with `--download`
(reliable but ~0.5 GB/granule on disk and slower)? At ~10³⁺ granules the disk +
time cost of off-cloud may be prohibitive.

**Q3 — Fit parallelism?** Matchup-level parallel fitting is **not implemented** yet.
For a big run, do we (a) implement parallel `fit_batch` across cores first
(recommended; the `batch-fit-argo` pattern), (b) run serially and accept the wall
clock, or (c) chunk with `--replace`-free resumes? (a) is likely required to finish
in reasonable time.

**Q4 — `pab_version` for the release?** Bump from `0.0.dev0` to a tagged release
version (e.g. `1.0`) so the production records are provenance-distinct from the dev
runs? (Design: a new version adds records rather than overwriting.)

**Q5 — Bulky-artifact hosting.** A full run produces many MCMC-chain NPZs and
figures. Nautilus S3 is still deferred (`HOWTO.md` §7b). Do we (a) keep them local
and publish only the report + summary tables now, or (b) activate the Nautilus S3
backend first so the report can link the artifacts by URL?

## Reports

### Full run

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
