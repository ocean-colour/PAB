# Matchups for floats with Hyperspectral sensors

## Goals

We are going to examine the matchups in the PAB database with hyperspectral sensors.

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

Yui Takeshita (MBARI) has shared with me that these are the float IDs that have hyperspectral sensors:

1902578
1902601
1902637
1902685
1902695
2903985
2904029
4903658
4903660
4903739
4903740
4903774
4903847
4903848
5906995
5907146
5907218
6903124
6903706
6990503
6990514
6990684
6990685
7901133
7902260


## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below


## Tasks

1. Read all the files in the context. We are going to check to see if any of our matchtups in `$OS_COLOR/PAB/pab.db` have hyperspectral sensors.  If you have any questions about this, please ask in the Q&A section below.  Use Opus 5.  Log your work.

2. Read my answers to the Q&A below and respond to them.  If you have any additional questions, please ask in the Q&A section below.  Use Opus 5.  Log your work.

## Q&A

*(JXP — questions from the 2026-09-10 run of Task 1. No answers yet.)*

**Q1 — Backfill the un-matched tail?** The full run's `match` stage stopped at
`profile_id = 52341`; profiles **52342–54031 (1,690, 3.1 % of the selection)
were never matched at all** (see the log entry below). One hyperspectral float,
**7902260**, lost 94 of its 95 profiles to this gap and is the *only* reason it
shows zero matchups — PACE swaths do cover 88 of those 95 profiles within ±24 h.
Do you want me to run `pab --stage match` over that tail (optionally
hyper-floats-first) to close the gap? Note this affects the whole dataset, not
just the hyperspectral subset (~460 expected missing matchups overall at the
27 % rate), so it also touches the published `pab_version = 1.0` numbers.

>A. This is a pretty big deal, if you are right.  Please generate a separate prompt doc named `backfill_unmatched.md` to first verify this needs to be done and then do it.  I will execute that separately.

> **Claude:** Agreed on the framing — "if you are right" is the right posture, so
> the doc is built as a **falsification exercise first**, with a hard gate.
> Written: [`claude_prompts/backfill_unmatched.md`](backfill_unmatched.md).
> Task 1 there is verification only and ends in "report and stop"; Tasks 3–5
> (the actual re-run) are explicitly conditional on it. It names the leading
> **alternative** explanation I could not settle from the DB alone — that the
> tail profiles were inserted by a *later* ingest-retry pass and so were simply
> absent when `match` ran (`profile_id` is `AUTOINCREMENT`, and float 7902260
> holds id 948 *and* ids 53278–53391, which fits that story) — and identifies
> the artefact that decides it: the `counts:` lines in `/data/full/run.log` on
> the Nautilus PVC, which record the `profiles` count immediately before the
> `match` stage. Either way the remedy is the same run, but the diagnosis and
> the guard differ, so it gets settled before anything is changed.
>
> Two things I firmed up while writing it, both strengthening the case: using
> the real `candidate_granules()`/`MatchupConfig` (±24 h, ≤ 5 km, 1° pad) rather
> than my own geometry, **1,524 of the 1,666** positioned tail profiles have
> candidate granules and **0** matched, against 29.9 % on the 48,780
> candidate-bearing profiles below the cut; and the tail is not a peculiar
> sub-population — 42 floats, latitude −66 to +77, all three basins,
> 2024-05 → 2026-07. Chance is ~10⁻¹³⁰. Expected yield ~**250–460** new
> matchups (best estimate ~300), of which ~25–30 are hyperspectral.

**Q2 — Refresh the selection?** The selection CSV was frozen 2026-07-06. The
`bgc-s` index today offers **1,972** in-window BBP700/CHLA profiles for these
floats vs the **1,775** in `pab.db` — ~197 new profiles (194 of them dated after
2026-07-06). Ingest+discover+match those too, or leave the dataset as-is?

>A. Leave the end date as is.

> **Claude:** Understood — the selection window stays frozen at 2026-07-06 and
> the ~197 newer profiles stay out. Worth noting this is *consistent* with the
> Q1 backfill rather than in tension with it: every profile in the un-matched
> tail is already inside the frozen selection (times 2024-05-08 → 2026-07-05),
> so completing `match` adds no profiles and moves no end date.

**Q3 — Is the WMO list the definition of "hyperspectral"?** `pab.db` carries no
sensor inventory (`floats` has only `wmo`/`project_name`/`data_center`), so I
identified hyperspectral matchups purely by Yui's 25 WMOs. Should I add a
`floats.hyperspectral` flag (or a sensor column) to the schema so this is
queryable and provenanced, rather than living in a prompt file?

>A. No, let's not do that for now.

> **Claude:** Fine — no schema change. This doc's 25-WMO list stays the sole
> definition of "hyperspectral", so any query has to carry the list explicitly;
> I'll keep referring back here rather than encoding it anywhere in `pab`.

**Q4 — What is the follow-on analysis?** Do you want the 555 hyperspectral
matchups written out as their own table/CSV and a dedicated report (à la the
Chl-a/CDOM reports), or is Task 2 going to specify something different?

>A. I will discuss with Yui and get back to you.

> **Claude:** Holding. Nothing written out yet — the 555 matchups are queryable
> from `pab.db` with the WMO list whenever the scope is settled. Two things that
> would help that conversation are in Q5/Q6 below.

**Q5 — Which hyperspectral instrument, and what comparison does Yui want?**
This shapes the whole analysis and I don't want to guess. All 21 floats present
are Coriolis (DAC `IF`) on REFINE / ITINERIS / APERO / GMMC — programmes that
typically fly **hyperspectral downwelling-irradiance radiometers** (e.g. TriOS
RAMSES), not hyperspectral `Rrs`. If that's what these carry, the interesting
comparison is float-derived apparent optical properties (or `Kd(λ)` / `Ed(λ)`
→ `Rrs(λ)`) against **PACE `Rrs(λ)` directly** — a genuinely different
experiment from what PAB currently stores, which is BING IOPs fitted to the
PACE spectra plus in-situ `bbp700`/`chla`. Note the current DB holds **no float
radiometry at all**: ingestion pulls `BBP700`/`CHLA`/`CDOM`/`PSAL`/`TEMP`/`PRES`
only, so `DOWN_IRRADIANCE*`/`DOWNWELLING_PAR` would need a new ingestion pass
(the `bgc-s` index shows several of these floats do carry
`DOWN_IRRADIANCE380/412/443/490/555`). Is that the direction, or is the ask
simply "how do our existing IOP retrievals do on the subset of floats that
happen to have hyperspectral sensors"? The second needs no new ingestion; the
first is a Stage-11-sized piece of work.

**Q6 — Should the follow-on analysis wait for the backfill?** If Q1's backfill
runs, 7902260 goes from 0 to ~25–30 matchups and the subset total from 555 to
~585 (~5 %). Small, but it would mean re-doing any figures/tables produced
before it. My lean: **settle `backfill_unmatched.md` Task 1 first** (a few
hours of verification, no re-run), then decide — if the truncation is confirmed,
run the backfill before any hyperspectral report; if it's refuted, start the
analysis immediately on the 555. Sound right, or would you rather I start on
whatever Yui asks for and accept re-doing it later?

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-10 (Task 1 — inventoried the hyperspectral-float matchups in `pab.db`)

Checked Yui Takeshita's 25 hyperspectral-sensor float WMOs against the
production store `$OS_COLOR/PAB/pab.db` (schema v4, `pab_version = 1.0`;
881 floats / 54,031 profiles / 14,610 matchups / 14,609 fits).

**Answer: yes — 555 matchups on 20 of the 25 floats,** 3.8 % of all matchups,
every one of them with a successful BING fit.

| | listed | in `floats` | with profiles | with matchups |
|---|---|---|---|---|
| hyperspectral floats | 25 | 21 | 21 | **20** |
| profiles / matchups / fits | — | — | 1,775 | **555 / 555** |

Per-float matchup counts (top): 4903847 **75**, 1902685 **54**, 5907146 **46**,
6990684 **41**, 4903848 **40**, 4903660 **34**, 6990685 **34**, 4903739 **33**,
6990503 **31**, 6990514 **29**, 7901133 **22**, 4903658 **19**, 1902637 **17**,
1902601 **16**, 1902695 **15**, 5906995 **14**, 2904029 **12**, 4903740 **10**,
5907218 **8**, 2903985 **5**, 7902260 **0**. All 21 floats present are
DAC = **IF** (Coriolis), across the REFINE / ITINERIS / APERO / GMMC-ESA /
GMMC-ARGO-DOME projects.

**Quality — the hyperspectral subset is slightly *better* than the population.**
Mean separation **1.24 km** (all matchups 1.45), mean Δtime **9.78 h** (10.81),
`n_spectra` = 10.0 on every matchup, **555/555 fits `success = 1`** with mean
reduced χ² **0.558** and mean MCMC acceptance 0.413. All ten
`BING_ExpBPow_*` quantities are present on all 555. In-situ coverage:
`bbp700`/`chla`/`mld` 555/555, `chla_adjusted` 497, `cdom` **241** (43 % — the
CDOM-carrying subset is the limiting factor for any CDOM work here); Argo data
mode is `A` (adjusted) on 497 and blank on 58.

**Why 5 of the 25 floats contribute nothing — all five explained, four benignly.**
Checked each against `argopy.ArgoIndex(index_file="bgc-s")` (406,804 rows), i.e.
the same source the full run's selection rule used (in-window profiles whose
`parameters` contain `BBP700` or `CHLA`; window opens 2024-03-05, the earliest
`PACE_OCI_L2_AOP` granule):

- **1902578** — index ends 2023-03-31. **6903124** — ends 2021-06-23.
  **6903706** — ends 2022-04-07. All three died before PACE data begins, so no
  in-window profiles exist. Correctly absent.
- **4903774** — alive (index runs to 2026-09-09, 156 in-window profiles) but
  only **5** of its 181 index rows carry `BBP700`/`CHLA`, and all five are 2023
  cycles (1–4 and 13). Every in-window cycle lists only
  `PRES TEMP PSAL DOXY`, so it fails the selection filter. Correctly absent —
  its bio-optics simply aren't in the synthetic index for the PACE era.
- **7902260** — **not benign; a real gap in the full run.** ITINERIS float in
  the Ionian Sea (39.3 N, 17.7 E), 95 profiles ingested 2025-05→2026-07, all
  with `bbp700`, `chla` and `mld` — and **zero** matchups, while its
  Mediterranean neighbour 4903847 converts at 55 %. A point-in-polygon check of
  its positions against the 67,435 stored granule footprints (±24 h) shows
  **88 of 95 profiles are genuinely covered by a PACE swath**, and
  `GranuleIndex.load()` pools granules globally, so the candidates were there.

**Root cause of 7902260's zero — the `match` stage never reached it.** Tracing
`matchups.created` (2026-08-06 → 08-14) against `profile_id` shows match walked
the `profiles` table in `profile_id` order and **stopped at 52341**. Match rate
by `profile_id` bin is a flat ~27 % for 19 of 20 bins and **5.8 %** in the last
one; resolved at 200-profile granularity it is 17–21 % up to ~52341 and then
**exactly 0 % for all 1,690 profiles from 52342 to 54031**. 94 of 7902260's 95
profile_ids sit above 52000, mostly past the cut — so its zero is an artefact of
where the run stopped, not of the float or the swath geometry. 28 floats with
≥20 profiles have zero matchups; the biggest ones (7902203, 7902260, 7902195,
7902334, …) cluster in that same tail. Every *other* hyperspectral float was
fully processed (`n_unprocessed = 0`), so the 555 figure is otherwise complete —
but it is a **floor**: at the subset's own 33 % rate the tail would add ~31 more
hyperspectral matchups, and ~460 across the whole dataset.

**What I learned.** (1) The headline "54,031 profiles → 14,610 matchups" hides a
3.1 % truncation at the end of the profile table; the full-run report's 27 %
match rate is right for what was processed but the denominator should have been
52,341, not 54,031. A per-profile "match attempted" marker would have made this
visible — right now the only way to see it is that the *derivative* of matchups
w.r.t. `profile_id` goes to zero, which is exactly the kind of thing a summary
count can't show. (2) `granules.time_end` is **empty for every row** — an
initially-plausible coverage diagnostic (`t0 <= t+24h AND t1 >= t-24h`) silently
returns zero candidates for every profile in the database. Use `time_start`
only. (3) The DB has no sensor inventory, so "hyperspectral" is not queryable
from `pab.db` alone — it lives only in this prompt file (see Q3).

**No code or data changed** — read-only queries plus one `ArgoIndex` load.
Questions for JXP are in the Q&A section above.

### 2026-09-10 (Task 2 — answered the Q&A and wrote `backfill_unmatched.md`)

Read JXP's four answers, responded inline under each, and produced the artefact
Q1-A asked for: **`claude_prompts/backfill_unmatched.md`** — a standalone prompt
doc that verifies the `match`-stage truncation before fixing it, for JXP to
execute separately.

**Answers taken as given.** Q2 — selection end date stays frozen at 2026-07-06
(the ~197 newer `bgc-s` profiles stay out; no conflict with the backfill, since
every un-matched tail profile is already inside the frozen selection). Q3 — no
`floats.hyperspectral` schema column; the 25-WMO list stays in this doc as the
sole definition. Q4 — follow-on analysis on hold pending Yui; asked two
questions (Q5/Q6) that should help that conversation.

**The doc is built as a falsification exercise, not a work order.** JXP's "if
you are right" is the correct posture, so Task 1 is a gate that ends in "report
and stop", and Tasks 3–7 are explicitly conditional. It states the claim as a
table of testable facts and names four competing hypotheses, with the tests that
discriminate them:

- **H1** the stage stopped early (preemption / `backoffLimit` / stall-guard
  kills on the final chunks, unnoticed because the total landed near the Job's
  own predicted "~14,100 matchups, 28 % of 50,292").
- **H2 — the leading alternative, and one I could not settle from the DB.**
  The tail may have been inserted by a *later* ingest-retry pass, so `match`
  never saw it and behaved correctly. `profiles.profile_id` is `AUTOINCREMENT`
  and the run had ~0.9–2.2 % transient argopy failures, which would put retried
  profiles at exactly these high ids; float 7902260 holding `profile_id` **948
  and** 53278–53391 fits that story precisely. The remedy is the same run either
  way, but the diagnosis, the docs correction, and the Task-7 guard differ.
  The decisive artefact is `/data/full/run.log` on the Nautilus PVC — it prints
  a `counts:` line before each stage, so the pre-`match` `profiles` count says
  directly whether the tail existed then. `mld_summary.created` cannot answer
  this: the 2026-09 re-ingest overwrote it.
- **H3** the granule pool grew after `match` (looks excluded — 67,435 then and
  now — but confirm, don't assume).
- **H4** measurement error in yesterday's analysis (re-derive with the real
  `pab` API rather than ad-hoc SQL/geometry).

**Evidence strengthened while writing it.** Re-ran the coverage test through the
production code path (`GranuleIndex` + `candidate_granules` + real
`MatchupConfig`: ±24 h, ≤ 5 km, 10 spectra, 1° footprint pad) instead of my own
polygon code: **1,524 of the 1,666** positioned+summarised tail profiles have
candidate granules and **0** matched, versus **14,608 / 48,780 = 29.9 %** on the
candidate-bearing profiles below the cut. Total candidate-bearing = 50,304,
which reproduces the 50,292 quoted in `nautilus/full_match_job.yaml` — so the
Job's own input estimate *already included* the tail, evidence for H1 over H2.
The cut is sharp: last matched id **52,341**, then exactly zero across
1,690 profiles in 50-profile bins to 54,031. The tail spans 42 floats,
latitude −66 → +77, all three basins (Atlantic 924 / Indian 434 / Pacific 308),
2024-05-08 → 2026-07-05 — so no regional, seasonal or single-float artefact can
explain it, and 0/1,524 against the local ~18 % rate is ~10⁻¹³⁰. Expected yield
**~250–460** new matchups (best estimate ~300), ~25–30 of them hyperspectral.

**Operational constraints the doc had to pin down, all found by reading the
code and the Job specs rather than assuming:**

1. **`match` has no profile-subset targeting.** `build_matchups(store, *, opener,
   config, replace, created, jobs)` takes no selection, and
   `qualifying_profiles()` is a bare `ORDER BY p.profile_id` over every
   summarised profile — which is *also* why an early stop produces a clean
   `profile_id` cut. Task 3 mirrors the `PipelineConfig.selection_keys()`
   pattern `discover` already got in Task 15/16 (and which `HOWTO.md` still
   lists as the unimplemented "single-matchup targeting" enhancement). Fallback
   with no code change: a plain `--stage match` re-run is safe and resumable
   because matched profiles are skipped before any granule is opened — but it
   re-attempts all ~35,700 candidate-bearing-unmatched profiles, ~2.5–3 days of
   cluster time versus ~3 h targeted.
2. **`fit` needs granule access too.** I initially assumed the stored spectra
   would let `fit` run offline; they don't. `matchup_pixels` holds only
   `ix`/`iy`/lat/lon/`distance_km`/`rank`/`flagged` — **no Rrs** — and
   `_gather_fit_input` returns the granule `data_url` for the fitter to read
   from. So match → fit → figure all have to run where the granules are cheap.
3. **The workstation can't host this.** Out-of-region granule opens are
   140–160 s each and `--download` costs ~0.5 GB per granule — order 1 TB for
   this tail. Nautilus (namespace `sea-meets-the-stars`, `pab-data` PVC,
   16 workers / 100 Gi, `MALLOC_ARENA_MAX=2`, `ulimit -n 65536`) is the only
   sane venue; the doc requires confirming the PVC/secrets still exist before
   planning around them.
4. **The authoritative DB is local, not on Nautilus.** `$OS_COLOR/PAB/pab.db`
   (2026-09-05, schema v4) carries the Chl-a/CDOM backfill; the PVC copy
   predates it. The doc makes "push the authoritative DB to the run site, never
   merge two SQLite files, keep a checksummed pre-run copy" a working
   agreement, since getting that backwards would silently lose Stage 10's work.
5. **The 18 GB of `fit_chains` are not local** (2 `.npz` files here) — they're
   on the PVC and in `AIOcean:PAB/`.

**Beyond the re-run, two things the doc insists on.** (a) The docs correction is
worth doing **even if the backfill is declined** (raised as its Q2):
`PAB_full_run_report.md` quotes a 27 % match rate on 54,031 profiles, but the
honest denominator for what was attempted is 52,341 / 48,780 candidate-bearing.
(b) Task 7 adds the guard that would have caught this: `match` should report
`attempted/skipped/unmatched/written` against the size of its qualifying set and
fail loudly when they don't reconcile. The deeper root cause is a schema gap —
"attempted and found nothing" and "never attempted" are **indistinguishable** in
`pab.db`, which is precisely why a 3.1 % truncation survived a full
verification-and-close-out pass. Summary counts can't show it; only the
derivative of matchups w.r.t. `profile_id` can.

**What I learned.** The truncation hid because the delivered total (14,610)
landed inside the Job header's own prediction (~14,100, 28 % of 50,292) — the
run agreed with its forecast while being 3.1 % short of its input, so every
aggregate check passed. A prediction being met is not evidence a loop completed;
only reconciling processed-count against input-count is. Also: `nautilus/` and
the Job YAML headers turned out to be the highest-value context in the repo for
this question — `full_match_job.yaml`'s header supplied the 50,292 figure that
distinguishes H1 from H2, and `coverage_check.py` already existed to answer the
candidate-coverage question I had been re-deriving by hand.

**Files changed:** `claude_prompts/backfill_unmatched.md` (new, 319 lines);
`claude_prompts/hyper_matchups.md` (Q1–Q4 responses, new Q5/Q6, this entry).
No package code, no data, no git operations.
