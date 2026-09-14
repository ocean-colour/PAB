# Running the full PAB pipeline

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

## Prompts

1. Execute the 1st task in Tasks/Planning below

## Tasks

### Planning

1. Read all the files in the context.  We wish to develop a plan to re-run the BING analysis in Nautilus with the new RoB RT emulator.  We will also need to backfill the missing matchups from the original run.  Have a discussion with me on the plan for this work.  Ask me a series of questions in the Q&A section.  Use Fable if you can.  Log your work.

## Q&A

### Planning

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs