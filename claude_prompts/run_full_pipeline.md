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

0. Execute the 0th task in Tasks below
1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below
6. Execute the 6th task in Tasks below
7. Execute the 7th task in Tasks below
8. Execute the 8th task in Tasks below
9. Execute the 9th task in Tasks below

## Tasks

0. **Converse.** ✅ *done* — See my answers to the Q&A first; understand them and
   ask any additional questions before proceeding. Log your work.

1. **More conversation.** ✅ *done* — Confirm the Q6–Q9 answers and raise anything
   remaining before pinning the config. Log your work.

   *Decisions locked (Q1–Q9):* off-cloud `--download` on `/mnt/tank` (9.8 TB free);
   scope = all BGC floats with **`BBP700` or `CHLA`** over the PACE window (start =
   earliest `PACE_OCI_L2_AOP` granule, end = today);
   `$PAB_DATA_DIR=/mnt/tank/Oceanography/data/PAB` (fresh DB); `pab_version = 1.0`;
   implement parallel `fit_batch` first; keep artifacts local; **monitor disk, no
   eviction**.

2. **Pin the run configuration.** Create `$PAB_DATA_DIR=/mnt/tank/Oceanography/data/PAB`
   (fresh `pab.db`, distinct from the dev `…/Color/PAB`); bump `pab_version`
   `0.0.dev0` → **`1.0`** in `pab/config.py` (and `setup.py` for consistency);
   default to the off-cloud path (`--download`, `--cache-dir` under
   `$PAB_DATA_DIR/granules`). Confirm with `pab --dry-run --download` that the plan,
   `--db`, `--outdir`, and cache paths are right, and that the suite still passes
   after the version bump. Log the pinned config.

3. **Assemble the full profile selection (count first).** Determine the window
   start = the **earliest available `PACE_OCI_L2_AOP` granule** (query live via
   earthaccess), end = today. From the Argo **bgc index**
   (`argopy.ArgoIndex(index_file='bgc-s')`), select every in-window profile from any
   BGC float carrying **`BBP700` or `CHLA`**. **Report the count first** (floats,
   profiles) before any per-profile fetch. Write the production `--profiles-csv` and
   sanity-check WMO/cycle coverage + lat/lon/time spread. Log the selection size +
   provenance.

4. **Implement parallel `fit_batch` (per Q3).** Add matchup-level parallelism to the
   `fit` stage (the `batch-fit-argo` pattern; BING `fit_batch` across cores) with a
   cores/`--jobs` control; keep it idempotent/resumable (skip fits that already have
   a `fit_id`). Tests; confirm identical results to the serial path on the dev set.
   Do this **before** the pilot so the pilot measures parallel fit time. Log.

5. **Pilot on a subset.** Run the whole pipeline on a small representative slice
   (~50 profiles across regions/seasons) end to end — ingest → … → report — using
   the parallel fitter, to shake out rate limits, disk, fit time, and the published
   report at non-trivial N. **Extrapolate to the full N.** **Disk gate:** if
   projected granules exceed the ~19k ceiling (9.8 TB ÷ ~0.5 GB), pause and decide
   (more room on the 15 T volume, subsample, or revisit eviction) before the full
   send. Log the pilot metrics + extrapolation.

6. **Ingest + discover (full).** Run `pab --stage ingest` (argopy fetch, MLD
   summaries, Argo Q&A figures) then `--stage discover` (CMR granule search). Expect
   argopy slowness / transient CMR 500s; both stages resume on re-run. Log counts
   (`profiles`, `granules`) and any failures.

7. **Match + fit (the heavy stages).** Run `pab --stage match --download` to build
   matchups (**monitor disk; warn near ~9.8 TB; no eviction** per Q9), then
   `--stage fit` with the parallel fitter. Spot-check convergence (`diagnose-mcmc`).
   Log matchups written, fits written/failed, wall-clock, and peak disk.

8. **Figure + report + publish.** Run `--stage figure` then `--stage report`;
   `pab --emit-site report_site`; preview locally (`sphinx-build`), then commit
   `report_site/` and push so RTD rebuilds. Keep bulky artifacts **local** (Q5);
   publish the report + summary tables only. Confirm the summary coverage counts,
   the scatters/map, and that the galleries N-guard sensibly at scale. Log the
   published counts + the RTD build.

9. **Verify & close out.** Spot-check a handful of matchups (distance/Δt, fit
   quality, scene), confirm every record carries `pab_version = 1.0`, update
   `docs/design/PAB_implementation.md`, and write the full-run report (coverage,
   timings, failures, follow-ups — incl. the deferred Nautilus namespace/bucket
   TODO). Log your work.

## Q&A

**Q1 — Scope of the full run?** The dev set is 10 profiles / 2 floats. What defines
"full"? (e.g. *all* BGC-Argo floats with `BBP700`+`CHLA` over a time window; a set
of regions; a specific float list; a date range aligned to PACE's mission, launched
2024.) This decides N (matchups, disk, fit time) and everything downstream.
>A. Let us run on all BGC-Argo floats during the PACE mission.

**Q2 — Where do we run it?** In-region on AWS `us-west-2` (fast S3, the design
target — recommended at scale) or off-cloud on the workstation with `--download`
(reliable but ~0.5 GB/granule on disk and slower)? At ~10³⁺ granules the disk +
time cost of off-cloud may be prohibitive.
>A. I just cleared up >5Tb on my workstation. Let's use that.  Let me know if you need me to provide the path, but the parent is `/mnt/tank/Oceanography/data`.

**Q3 — Fit parallelism?** Matchup-level parallel fitting is **not implemented** yet.
For a big run, do we (a) implement parallel `fit_batch` across cores first
(recommended; the `batch-fit-argo` pattern), (b) run serially and accept the wall
clock, or (c) chunk with `--replace`-free resumes? (a) is likely required to finish
in reasonable time.
>A. Let's implement parallel `fit_batch` across cores first.

**Q4 — `pab_version` for the release?** Bump from `0.0.dev0` to a tagged release
version (e.g. `1.0`) so the production records are provenance-distinct from the dev
runs? (Design: a new version adds records rather than overwriting.)
>A. Let's bump from `0.0.dev0` to a tagged release version (e.g. `1.0`) so the production records are provenance-distinct from the dev runs.

**Q5 — Bulky-artifact hosting.** A full run produces many MCMC-chain NPZs and
figures. Nautilus S3 is still deferred (`HOWTO.md` §7b). Do we (a) keep them local
and publish only the report + summary tables now, or (b) activate the Nautilus S3
backend first so the report can link the artifacts by URL?
>A. Let's keep them local and publish only the report + summary tables now.  Remind me to create a new Namespace for this on Nautilus.  And its own s3 bucket.

---

**Follow-ups (Task 0 — Claude, awaiting answers before Task 1):**

**Q6 — PACE window start.** Pin the start to the **earliest available
`PACE_OCI_L2_AOP` granule** (queried live) with end = today, or a fixed date (e.g.
`2024-03-01`)? PACE launched 2024-02-08; OCI L2 ocean-color came slightly later.
*(Lean: earliest-available.)*

>A. Let's use the earliest available `PACE_OCI_L2_AOP` granule.

**Q7 — "All floats" filter.** Require **`BBP700`** (the primary `b_bp` observable),
using `CHLA` when present (i.e. skip floats with no backscatter)? And take **every**
in-window profile from each qualifying float (no subsampling / cap)?
*(Lean: require BBP700; all in-window profiles.)*
>A. We can use any float with either BBP700 or CHLA. 

**Q8 — Canonical data dir + version.** Use **`/mnt/tank/Oceanography/data/PAB`** as
the production `$PAB_DATA_DIR` (a **fresh** `pab.db`, distinct from the dev
`…/Color/PAB` DB), stamped `pab_version = 1.0`? *(Lean: yes.)*
>A. yes

**Q9 — Disk-bounding.** ~0.5 GB/granule × 5 TB ≈ a **~10k-granule ceiling**. Add
**cache eviction** (delete each granule once its matchups are extracted) so disk
stays bounded regardless of granule count, or just **monitor** and warn near 5 TB?
*(Lean: add eviction for an unbounded "all floats" run.)*
>A. Monitor and warn near 5 TB.

## Reports

### Full run

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-07-06 (Task 0 — reviewed the run decisions; raised follow-ups)

Read the user's Q&A answers and confirmed understanding: (1) scope = **all**
BGC-Argo floats over the PACE-mission window; (2) run **off-cloud** on the
workstation (>5 TB freed under `/mnt/tank/Oceanography/data`) via `--download`, not
in-region; (3) **implement parallel `fit_batch`** across cores before the fit stage;
(4) bump `pab_version` `0.0.dev0` → **`1.0`**; (5) keep chains/figures **local**,
publish report + summary tables only — with a standing reminder to **create a
Nautilus namespace + S3 bucket** later.

Flagged the scale reality: "all BGC floats with backscatter, 2024→now" is plausibly
tens of thousands of profiles and thousands of matched granules; at ~0.5 GB/granule
5 TB is a **~10k-granule ceiling**, and off-cloud reads are slow → a multi-day run.
This is why the Task-3 pilot must precede the full send.

Raised four follow-ups in the Q&A (Q6–Q9) before touching Task 1: PACE window start
(earliest-available vs fixed), the "all floats" filter (require `BBP700`? all
in-window profiles?), the canonical `$PAB_DATA_DIR`/version
(`/mnt/tank/Oceanography/data/PAB`, fresh DB, v1.0), and disk-bounding (add cache
eviction vs monitor). No code changed — conversational/planning step; awaiting
answers before pinning the config.

### 2026-07-06 (Task 1a — confirmed Q6–Q9 answers, verified ground truth)

User answered the follow-ups: Q6 **earliest-available `PACE_OCI_L2_AOP` granule**
as the window start (end = today); Q7 include any float with **`BBP700` *or*
`CHLA`** (broader than my lean — some floats will contribute only a Chl or only a
b_bp matchup, which the report already tolerates); Q8 **yes** —
`/mnt/tank/Oceanography/data/PAB`, fresh DB, `pab_version = 1.0`; Q9 **monitor &
warn**, no eviction.

Verified ground truth (read-only): `/mnt/tank` has **9.8 TB free** (roomier than
the 5 TB assumed → a ~19k-granule ceiling at ~0.5 GB each); `…/data/PAB` doesn't
exist yet (created at pin time); the version string lives only in `pab/config.py`
and `setup.py` — **no test pins `0.0.dev0`**, so the v1.0 bump is clean.

Two plan refinements (no decision needed): (a) in Task 2, get a **count** of
qualifying floats/profiles from the Argo bgc index *before* the expensive ingest;
(b) a **post-pilot disk gate** — if the granule-per-matchup rate extrapolates past
~19k granules, pause and decide (more room on the 15 T volume, subsample, or revisit
eviction) rather than overrun. Reminded the user to create the Nautilus namespace +
S3 bucket (Q5). No blocking questions remain; ready to pin the config. No code
changed.

### 2026-07-06 (Task list update — inserted the parallel-fit task, baked in decisions)

Tidied Prompts/Tasks now that the Q&A is resolved: marked tasks 0/1 (the two
converse steps) **done**; added a **new Task 4 — "Implement parallel `fit_batch`"**
(per Q3) *before* the pilot so the pilot measures parallel fit time; renumbered the
pilot → 5, ingest+discover → 6, match+fit → 7, figure+report+publish → 8,
verify → 9; extended the Prompts list to 0–9 to match. Baked the locked decisions
into the task text so each is self-contained: `$PAB_DATA_DIR=/mnt/tank/Oceanography/data/PAB`
+ fresh DB + `pab_version=1.0` (Task 2); earliest-`PACE_OCI_L2_AOP`-granule window +
`BBP700`-or-`CHLA` filter + count-first (Task 3); `--download` + monitor-disk /
no-eviction with a post-pilot disk gate (Tasks 5/7); keep-artifacts-local (Task 8).
No code changed — doc maintenance.

### 2026-07-06 (Task 2 — pinned the run configuration; bumped to v1.0)

Pinned the production config and verified it:

- **Data dir:** created `/mnt/tank/Oceanography/data/PAB` (+ `granules/` cache) —
  fresh, no `pab.db` yet, distinct from the dev `…/Color/PAB`.
- **Paths (dry-run confirmed):** `--db /mnt/tank/Oceanography/data/PAB/pab.db`,
  `--outdir …/pipeline`, `--cache-dir …/granules`, off-cloud `--download`, full
  stage order `ingest → … → report`.
- **Version bump:** `pab_version` `0.0.dev0` → **`1.0`** in `pab/config.py` and the
  packaging version in `setup.py`. Suite still green (**145 passed** in `os_313`).

Pinned invocation for the run:
`PAB_DATA_DIR=/mnt/tank/Oceanography/data/PAB pab --db $PAB_DATA_DIR/pab.db --download …`
(the explicit `--db` guards against the Stage-9 two-DB split).

Provenance nuance flagged to the user: the record **stamp** (`pab.config.pab_version`)
is `1.0`, but `package_versions()["pab"]` still reads `0.0.dev0` (installed dist
metadata) until `pip install -e . --no-deps` is re-run — do that before the run so
the Methods provenance table matches the stamp. Not blocking. Profiles CSV is Task 3.
Code changed: version bump only (config.py, setup.py).