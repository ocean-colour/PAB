# Backfill the un-matched tail of the full-mission run

## Goals

The full-mission run (`pab_version = 1.0`, 2026-08-20) reports
**54,031 profiles → 14,610 matchups**. Evidence gathered in
`claude_prompts/hyper_matchups.md` (Task 1, 2026-09-10) says the `match` stage
**stopped early**: it walked the `profiles` table in `profile_id` order and
produced its last matchup at `profile_id = 52341`, leaving
**1,690 profiles (3.1 % of the selection) never attempted** — of which
**1,524 have candidate PACE granules** and should have converted at the
population rate.

This doc has two halves, in order, and the second must not start until the
first is done:

1. **Verify** the claim — hard enough to *falsify* it. It is a claim that the
   published `1.0` dataset is incomplete, so the bar is high.
2. **If verified, fix it**: complete `match` (and the dependent `fit`/`figure`/
   `report` stages) over the un-attempted profiles, re-publish, and correct the
   affected numbers in the docs. Then add a guard so a stage can never again
   finish short of its input set without saying so.

> **Status (2026-09-10): NOT STARTED.** Written by Claude at JXP's request
> (`hyper_matchups.md` Q1-A). Task 1 is the verification gate — Tasks 3+ are
> conditional on it.

## Claude

### Skills

None specific. No BING model or prior changes — the `fit` stage is re-run only
to cover *new* matchups, with the **same** config the full run used.

### Working agreements

- **Git is handled by the user.** Do not run `git add`/`commit`/`push`/branch/
  merge. Read-only inspection (`git status`, `git diff`, `git log`) is fine.
- **Python only.** No MATLAB.
- **Verify before you change anything.** Task 1 is a gate. If the truncation
  does **not** hold up, stop, log what the real explanation is, and report —
  do not "fix" a non-problem.
- **The local DB is authoritative, and it is not the one on Nautilus.**
  `$OS_COLOR/PAB/pab.db` (schema v4, 2026-09-05) carries the Chl-a/CDOM
  provenance backfill; the Nautilus PVC copy at `/data/full/pab.db` predates it
  (2026-08-20, schema v3-era content). **Never merge two SQLite files.** Push
  the authoritative DB to wherever the run happens, run there, pull it back.
  Take a checksummed copy before any stage writes to it.
- **Reuse, don't reinvent.** The stage runner, idempotency guards, parallel
  pools and stall protections all exist and are battle-tested (`pab/pipeline.py`,
  `pab/matchup/engine.py`, `nautilus/full_match_job.yaml`). Extend the existing
  seams.
- **No re-analysis.** Matching criteria (`MatchupConfig`: ±24 h, ≤ 5 km,
  10 spectra, 1° footprint pad) and the BING fit config are **unchanged**. This
  is completion of an interrupted run, not a new run.
- Raise anything genuinely blocking in **Q&A** below rather than guessing.

## Context

Read these before running:

- `HOWTO.md` — the CLI and stages, idempotency/resume, the in-region vs
  `--download` granule-access section, and §7b (publishing + the `AIOcean:PAB/`
  backup convention).
- `docs/design/PAB_design.md` → *Semi-automation* and *Provenance & versioning*
  (the "a new `pab_version` **adds** records" rule, and the documented one-time
  exception the Chl-a/CDOM backfill took).
- `docs/design/PAB_full_run_report.md` — the numbers this doc may have to
  correct, especially §9 (timings and failure rates) and the headline table.
- `docs/design/PAB_implementation.md` §10 (the full run) and §11 (Stage 10).
- `claude_prompts/hyper_matchups.md` — the 2026-09-10 log entry is the origin of
  this doc.
- `claude_prompts/run_full_pipeline.md` — Tasks 15–19, especially the 2026-08-06
  entry (Task 17a: the time-first rule, the seven OOM kills, the 16-worker
  settling point) and the 2026-08-27 close-out.
- `nautilus/full_match_job.yaml` — the Job that actually ran `match`. Its header
  predicts "**~14,100 matchups (28 % of 50,292** candidate-bearing profiles)".
  Note the delivered 14,610 *does* land near that prediction — which is why the
  truncation was not noticed. That prediction is not evidence the run finished.
- `nautilus/coverage_check.py` — the existing "how many profiles have candidate
  granules" tool. It answers the question `match` will ask, from the store, with
  no CMR queries. Reuse it; don't rewrite it.
- `docs/nautilus/s3_PAB.md` — the S3 bucket and its (read-only public) policy.

### Environment notes

- The `pab` package is **not** importable from the default `python`. Use
  `/Users/xavier/miniforge3/envs/ocean14/bin/python` with
  `PYTHONPATH=/Users/xavier/Oceanography/python/PAB` (or `pip install -e .` into
  that env).
- `$OS_COLOR` and `$PAB_DATA_DIR` both resolve to
  `/Users/xavier/Oceanography/data/Color/PAB`'s parent layout — the DB is at
  `$OS_COLOR/PAB/pab.db`.
- The 18 GB of `fit_chains` from the full run are **not** local (only 2 `.npz`
  files are). They live on the Nautilus PVC and in `AIOcean:PAB/`.

## The claim to be tested

Stated precisely, so it can be refuted rather than confirmed by assumption.
All figures below are from the 2026-09-10 read of `$OS_COLOR/PAB/pab.db` and
are the starting point, not the answer:

| Fact | Value |
|---|---|
| Highest `profile_id` carrying a matchup | **52,341** |
| Profiles with `profile_id > 52341` | 1,690 (1,666 positioned + summarised) |
| …of those, with ≥ 1 candidate granule (`candidate_granules`, real `MatchupConfig`) | **1,524** |
| …of those, with a matchup | **0** |
| Candidate-bearing profiles at `profile_id ≤ 52341` | 48,780 → 14,608 matched = **29.9 %** |
| Candidate-bearing profiles overall | 50,304 (vs the Job's stated 50,292) |
| Local match rate in the 1,000 profiles *before* the cut | ~18 % |
| `matchups.created` span | 2026-08-06 → 2026-08-14 |
| `granules` count then and now | 67,435 (unchanged) |

`qualifying_profiles()` is `ORDER BY p.profile_id`, so an early stop shows up as
exactly this: a sharp cut in `profile_id`, not a scatter.

**Why chance is not a candidate explanation.** 0 matched out of 1,524
candidate-bearing profiles, against a local rate of ~18 % (population 29.9 %),
has probability ~`0.82^1524` ≈ 10⁻¹³⁰. And the tail is not a peculiar
sub-population: 1,666 profiles across **42 floats**, latitudes −66 to +77,
longitudes −179 to +180 (Atlantic 924 / Indian 434 / Pacific 308), times
2024-05-08 → 2026-07-05. No regional, seasonal, or single-float artefact can
produce it.

**The competing hypotheses that must be excluded** (Task 1's real job):

- **H1 — the stage stopped early.** The Job was preempted / hit `backoffLimit`
  / the final chunked pools were killed by the 120 s stall guard and never
  retried, and the operator moved on to `fit` because the total looked right.
- **H2 — those profiles were not in the store when `match` ran.** If the tail
  was inserted by a *later* ingest retry pass (the run had ~0.9–2.2 % transient
  argopy failures, and `profiles.profile_id` is `AUTOINCREMENT`, so retried
  profiles get high ids — which would neatly explain both the high ids and the
  zero matchups), then `match` behaved correctly and the fix is the same run but
  the *diagnosis*, the docs correction, and the guard in Task 7 are different.
  **This is the leading alternative and the one to settle first.** Note the
  suggestive pattern: float 7902260 holds `profile_id` 948 **and** 53278–53391,
  i.e. one profile from an early pass and 94 from a much later one.
- **H3 — the granule pool grew after `match` ran**, so the tail's candidates did
  not exist at match time. Test: `granules` is 67,435 now and
  `full_match_job.yaml` already calls the pool "the complete 67,435-granule
  pool", so this looks excluded — confirm it rather than assume it.
- **H4 — measurement error in the 2026-09-10 analysis.** Re-derive the numbers
  independently (see Task 1). One trap already found: `granules.time_end` is
  **empty on every row**, so the natural coverage predicate
  `t0 <= t+24h AND t1 >= t-24h` silently returns *zero* candidates for every
  profile in the database. Use `time_start` only, or better, call
  `pab.matchup.engine.candidate_granules` and let the real code answer.

## Prompts

1. Execute Task 1 (the verification gate) and report before going further.
2. Execute Tasks 2–7 — only if Task 1 confirms the gap and JXP has answered
   Q1–Q3 below.

## Tasks

1. **Verify (the gate). Try to break the claim, not to confirm it.**
   - Re-derive every row of *The claim to be tested* independently of the
     2026-09-10 queries: use `pab.db.Store` + `pab.matchup.engine`
     (`GranuleIndex`, `candidate_granules`, `MatchupConfig`,
     `qualifying_profiles`) and `nautilus/coverage_check.py`, not ad-hoc SQL and
     hand-rolled geometry. Split every count at `profile_id = 52341`.
   - **Settle H2 — was the tail in the store when `match` ran?** The decisive
     artefact is the run's own log, `/data/full/run.log` on the Nautilus PVC
     (also possibly in `AIOcean:PAB/`): it carries a `counts:` line before and
     after every stage. If the pre-`match` `profiles` count is 54,031 the tail
     was present (→ H1). If it is ~52,341 the tail arrived later (→ H2). Get
     that log. Secondary evidence: the ingest-stage logs and the `pab-full-*`
     Job histories; `mld_summary.created` is **useless here** — the 2026-09
     re-ingest overwrote it.
   - Exclude H3 (granule pool unchanged since match) and H4 (independent
     re-derivation agrees).
   - Confirm the cut is sharp: matched-profile counts in 50-profile bins from
     `profile_id` 51,000 to 54,031, and the identity of the last ~20 matched
     ids.
   - **Report and stop.** State which hypothesis holds, with the evidence, and
     how many matchups the backfill is expected to add (a range, from the local
     ~18 % and population 29.9 % rates — roughly **250–460**, best estimate
     ~300). Do not proceed to Task 3 until JXP has seen this and answered
     Q1–Q3. Log it.

2. **Decide and record the run plan** (needs Task 1's verdict + Q1–Q3).
   - Where it runs: **Nautilus**, almost certainly. The workstation is not
     viable for `match` — out-of-region granule opens are 140–160 s each and
     `--download` costs ~0.5 GB per granule (~1 TB for this tail). Note that
     `fit` **also** needs granule access: `_gather_fit_input` returns the
     granule `data_url` and the Rrs spectra are read from the granule at fit
     time (`matchup_pixels` stores only pixel indices, not spectra). So
     match → fit → figure all want to be in the same place the full run was.
   - **Confirm the Nautilus namespace (`sea-meets-the-stars`), the `pab-data`
     PVC, the image, and the `earthdata-netrc` / `prp-s3-credentials` secrets
     still exist** before planning around them. If the PVC is gone, that is a
     scope change — raise it, don't improvise.
   - **DB sync, carefully.** Push the authoritative local `pab.db` to the PVC
     (via `s3://pab/full/pab.db`, which already holds the same bytes — verify by
     sha256 rather than trusting the copy), so the run extends the *v4,
     CDOM-backfilled* DB and not the stale PVC one. Keep a checksummed
     pre-run copy off to the side. Never merge.
   - Budget from the full run's measured throughput (16 workers, ~6.9 s/profile
     wall-clock): `match` over ~1,690 profiles ≈ **3 h**; `fit` over ~300
     matchups ≈ **1 h**; `figure` ≈ **20 min** at `--jobs 16`; chains
     ≈ 1.24 MB × 300 ≈ **400 MB**. Confirm against the real numbers, don't
     inherit these.

3. **Give the `match` stage a profile-subset target** (the *recommended* route;
   see the fallback below).
   - `build_matchups()` currently has no selection parameter and
     `qualifying_profiles(store)` returns every summarised profile. `discover`
     already solved exactly this in Task 15/16 via
     `PipelineConfig.selection_keys()` — mirror that pattern rather than
     inventing a new one, keeping the "`None` means no selection given, so sweep
     the whole store" subtlety intact so a subset CSV can never silently narrow
     a production run. This is the **"single-matchup targeting"** enhancement
     already listed under *Planned enhancements* in `HOWTO.md`, so it has
     standing value beyond this backfill.
   - Tests: subset honoured; `None` still sweeps; idempotency and the parallel
     path unaffected. Update `HOWTO.md`'s `--profiles-csv` row and move the
     enhancement out of *Planned*.
   - **Fallback needing no code change:** a plain `pab --stage match --jobs 16`
     re-run. It skips already-matched profiles *before* any granule is opened,
     so it is safe and resumable — but it re-attempts all ~35,700
     candidate-bearing-but-unmatched profiles, ≈ **2.5–3 days** of cluster time
     instead of ~3 h. Take this route if Task 3 turns out to be more delicate
     than it looks; the science outcome is identical.

4. **Backfill `discover` for the tail first.** 142 of the 1,666 tail profiles
   have no candidate granule, and a profile is only skipped by `discover` if the
   store holds a granule covering *its own* position in its window — so some of
   those may simply never have been searched. Run
   `pab --stage discover --profiles-csv <tail.csv> --discover-jobs 8`
   (~1,690 CMR searches ≈ 6–10 min). Re-run `coverage_check.py` afterwards and
   log how many profiles gained candidates. Cheap, and it removes an
   "un-searched vs genuinely uncovered" ambiguity from the final numbers.

5. **Run `match` over the tail**, then `fit`, then `figure` — same config, same
   protections (per-granule 120 s read timeout, chunked pools + stall guard,
   `MALLOC_ARENA_MAX=2`, 16 workers / 100 Gi, `ulimit -n 65536`). Reuse
   `nautilus/full_match_job.yaml` as the template; add the new Job specs to
   `nautilus/`. After each stage, record counts, wall-clock, stall/failure
   counts, and the new-record deltas. Verify the new matchups look like the old
   ones (separation, Δtime, `n_spectra`, fit `chisq`, `success` rate) — a
   *different* distribution would mean something changed, and is worth stopping
   for.

6. **Re-publish, re-back-up, and correct the record.**
   - `pab --stage report`, then regenerate `report_site/` (`--emit-site`, with
     `--downloads-base-url`), remembering `MAX_INTERACTIVE_MATCHUPS = 2000`
     keeps the committed tree small.
   - Push `pab.db` + the summary tables to `s3://pab/full/` and verify the way
     the Chl-a/CDOM pass did: public HTTP 200, exact content-length, and a
     fresh round-trip **sha256** match — not a clean CLI exit. Then
     `rclone copy` to `AIOcean:PAB/`, including any new chains.
   - **Correct the numbers, and do this even if JXP declines the backfill**
     (see Q2): `docs/design/PAB_full_run_report.md` reports a 27 % match rate on
     54,031 profiles, but the honest denominator for what was actually attempted
     is 52,341 profiles / 48,780 candidate-bearing. Fix the headline table and
     §9, and add a short subsection recording the truncation and its remedy.
     Update `docs/design/PAB_implementation.md` (§10.6 close-out) and
     `HOWTO.md` §7b.
   - Note in `claude_prompts/hyper_matchups.md`'s log what the hyperspectral
     count became (7902260 should go from 0 to roughly 25–30 matchups; the
     subset total from 555 to ~585).

7. **Add the guard that would have caught this.** The truncation was invisible
   because the only signals were summary counts, and the totals looked
   plausible. Make the pipeline unable to finish short of its input set
   silently: have `match` report `attempted / skipped / unmatched / written`
   against the size of its qualifying set, and fail loudly (non-zero exit, or a
   clear terminal warning) when `attempted + skipped < len(qualifying)`. Do the
   same for any other stage where it is as cheap. Consider persisting a
   per-profile "match attempted" marker — right now "attempted and found
   nothing" and "never attempted" are indistinguishable in the schema, which is
   the actual root cause of a month-long blind spot. Tests, docs, log.

8. **Log every task** in the Logs section below, per the format in *Logging*.

## Q&A

**Q1 — Scope: the whole tail, or the hyperspectral floats only?** The full tail
is ~1,690 profiles / ~300 new matchups / ~3 h of Nautilus `match` time; the
hyperspectral share of it is one float (7902260, 94 profiles, ~25–30 matchups).
Doing the whole tail costs barely more than doing part of it and leaves the
dataset consistent, so my recommendation is **the whole tail**. Confirm?

**Q2 — What if you'd rather not re-run at all?** The docs correction in Task 6
(the match-rate denominator, and a written record of the truncation) is worth
doing **regardless** — it costs nothing and stops the wrong number propagating
into anything published. Should I do Task 6's doc corrections even if Tasks 3–5
are declined?

**Q3 — `pab_version`: stay at `1.0`, or bump?** These would be *new* rows
(matchups/fits that never existed), added under unchanged criteria and code —
which is completion of an interrupted run, not a re-analysis. Staying at `1.0`
matches the precedent set by the Chl-a/CDOM backfill (`chl_cdom_prompt_1.md`
Q2-A) and keeps one coherent `1.0` dataset; bumping to `1.1` would make DB
snapshots distinguishable by version string but split the dataset across two
versions for no scientific reason. My lean: **stay at `1.0`**, documented as a
second, deliberate exception. There is no duplication risk either way —
`build_matchups` skips by `profile_id` already present in `matchups`, not by
version. Your call, since it sets precedent.

**Q4 — Who owns the S3/Drive re-publish?** The Chl-a/CDOM pass had Claude do
the `aws s3 cp` + `rclone copy` with checksum verification. Same arrangement
here, or do you want to review the DB locally before anything overwrites
`s3://pab/full/pab.db`?

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
