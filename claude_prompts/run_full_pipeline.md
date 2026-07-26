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

5. **Suppress tqdm progress bars.** Suppress the tqdm progress bars in the BING fitter.  Log your work.

6. **Pilot on a subset.** Run the whole pipeline on a small representative slice
   (~50 profiles across regions/seasons) end to end — ingest → … → report — using
   the parallel fitter, to shake out rate limits, disk, fit time, and the published
   report at non-trivial N. **Extrapolate to the full N.** **Disk gate:** if
   projected granules exceed the ~19k ceiling (9.8 TB ÷ ~0.5 GB), pause and decide
   (more room on the 15 T volume, subsample, or revisit eviction) before the full
   send. Log the pilot metrics + extrapolation.

7. **Setup Nautilus**.  Given the projected size of the PACE granules, it is time to setup Nautilus.  Remind me of what you have done so far and what needs to be done.  Put this in the Q&A section below.  Log your work

8. **More Nautilus**.  Read my answers to N1-N3.  If you have more questions, ask them in the Q&A section below.  Log your work.

9. **Yet more Nautilus**.  Read my answers to N4-N6.  We will continue this conversation in the `nautilus_prompts.md` file.  Log your work.

10. **Nautilus run**.  We branched off for a while to work on running PAB on Nautilus.  You can see that work in the `nautilus_prompts.md` file.  Now we are back to continue with the full pipeline.  You had just created the `pipeline.py` and `pab/matchup/engine.py` files. Please examine those and guide me on how to proceed with a 1000 profile run.  If you have any questions, ask them in the Q&A section below.  Log your work.  Use Fable if you can.

11. **Ingest + discover (full).** Run `pab --stage ingest` (argopy fetch, MLD
   summaries, Argo Q&A figures) then `--stage discover` (CMR granule search). Expect
   argopy slowness / transient CMR 500s; both stages resume on re-run. Log counts
   (`profiles`, `granules`) and any failures.

12. **Match + fit (the heavy stages).** Run `pab --stage match --download` to build
   matchups (**monitor disk; warn near ~9.8 TB; no eviction** per Q9), then
   `--stage fit` with the parallel fitter. Spot-check convergence (`diagnose-mcmc`).
   Log matchups written, fits written/failed, wall-clock, and peak disk.

13. **Figure + report + publish.** Run `--stage figure` then `--stage report`;
   `pab --emit-site report_site`; preview locally (`sphinx-build`), then commit
   `report_site/` and push so RTD rebuilds. Keep bulky artifacts **local** (Q5);
   publish the report + summary tables only. Confirm the summary coverage counts,
   the scatters/map, and that the galleries N-guard sensibly at scale. Log the
   published counts + the RTD build.

14. **Verify & close out.** Spot-check a handful of matchups (distance/Δt, fit
   quality, scene), confirm every record carries `pab_version = 1.0`, update
   `docs/design/PAB_implementation.md`, and write the full-run report (coverage,
   timings, failures, follow-ups — incl. the deferred Nautilus namespace/bucket
   TODO). Log your work.

## Q&A

**Nautilus setup (Task 7) — status + what's left.**

*What's already done (more than I'd realised):*
- **Access is live.** This workstation has an active `kubectl` context **`nautilus`**,
  Nautilus S3 creds (`~/.aws/credentials` + `~/.config/rclone/rclone.conf`), and the
  endpoint **`ENDPOINT_URL=https://s3-west.nrp-nautilus.io`** — `aws --endpoint-url
  $ENDPOINT_URL s3 ls` works (9 buckets visible).
- **Code interfaces exist.** `pab.report.publish` already has the seam:
  `LocalStubBackend` (active), a `NautilusS3Backend` **stub** (`NotImplementedError`),
  and `publish_release(store, outdir, *, backend=…)` / `build_manifest` that upload
  each artifact via `backend.upload(local_path, key) -> url` and record URL +
  SHA-256 in `manifest.json`, stamped `pab_version`.
- **Design + docs** specify NSF/Nautilus S3 as the bulk-artifact store; `HOWTO.md`
  §7b marks it deferred. `ToDo.md` carries the "create namespace + S3 bucket" item.

*Not done yet:*
- **No PAB bucket** (none of the 9 existing buckets is PAB-related).
- **No PAB Kubernetes namespace** (only needed if we also *run compute* on Nautilus).
- `NautilusS3Backend.upload()` is unimplemented; `publish_release` isn't wired to it;
  manifest still carries local-stub URLs.

*To do:*
1. **(infra)** Create the bucket — `aws --endpoint-url $ENDPOINT_URL s3 mb s3://<name>`
   (needs a name + public-read-vs-private decision). Namespace only if compute-on-Nautilus.
2. **(code, me — once the bucket + name exist)** implement `NautilusS3Backend.upload()`
   (boto3, endpoint from `ENDPOINT_URL`, creds from `~/.aws`; **config-gated**, never
   hardcoded); wire `publish_release(backend=NautilusS3Backend(...))` behind a flag;
   put real `https://s3-west.nrp-nautilus.io/<bucket>/…` URLs in the manifest; add an
   offline-mocked test; update HOWTO §7b.

**⚠️ Important scoping — Nautilus ≠ AWS us-west-2.** Setting up Nautilus solves
**artifact hosting/distribution** (Q5: publish chains/figures) and gives us big S3
storage. It does **not** fix the **PACE-granule read** bottleneck (Q11): PACE L2
granules live on **NASA's AWS us-west-2**; reading them from Nautilus is
out-of-region (slow/hangs), and copying all 18.55 TB onto Nautilus is the same
infeasible transfer. So **Q11 (how to read granules: us-west-2 / subsample /
eviction) is still open and separate** from the Nautilus artifact store.

*Questions for you (answer inline):*
- **N1 — Nautilus scope?** Artifact hosting only (the design's role), or also **run
  compute + stage granules** on Nautilus? (Decides whether we need a K8s namespace +
  containerizing PAB, and whether it touches Q11.)
>A. Artifact hosting only.  We will just their storage for now.  Note, it is not backed-up so anything that we want to keep should also be copied to my Google Drive.  For that, we will use the Shared Drive named AIOcean and `rclone` to copy the files.
- **N2 — Bucket name + access?** e.g. `pab`, `pab-v1`, `ocean-color-pab`; and
  **public-read** (so the RTD report can link downloads directly) or **private**?
>A. pab.  Yes, public-read.  Let me know if you need help accessing it.  This command works for me: `aws --endpoint https://s3-west.nrp-nautilus.io s3 ls s3://pab`
- **N3 — Confirm Q11 still needs a separate answer** (B in-region / C subsample /
  D eviction) for the granule reads — Nautilus doesn't replace it.
>A.  We will put the files in Nautilus.  I don't think Q11 is relevant anymore.

**Follow-ups (Task 8 — from N1–N3).** Read the answers. **Infra is ready:**
`s3://pab` exists (empty) with a public policy; rclone remotes `nautilus_s3:`,
`AIOcean:` (Google shared-drive root: AAII, AI, MHW, SharedFiles, data, …) and
`GDrive:` are configured. Three things need your input:

- **N4 — the granule *read* path (Q11) is still open — Nautilus doesn't remove it.**
  N1 says Nautilus is **storage only, no compute**, and it holds our **outputs**.
  But to *produce* those outputs PAB must still **read pixels from 124,218 PACE
  *input* granules that live on NASA's AWS `us-west-2`** — that's the 18.55 TB.
  Where we store outputs doesn't change how we read inputs. Even "copy all granules
  into `s3://pab`" is the *same* 18.55 TB NASA→Nautilus transfer (then a read-back
  to the workstation, since compute stays local). So the read path still needs a
  choice: **B** reads in `us-west-2` (lazy S3, ~MB/pixel, no bulk transfer —
  recommended); **C** subsample the 882 floats; **D** download→extract→evict on the
  workstation (bounded disk, but the full 18.55 TB transits + ~weeks; needs a
  parallel `match`). Did you perhaps mean to stage the granules on `s3://pab` and
  read them lazily from there? (Works *only if compute runs near Nautilus* —
  otherwise it's the big transfer twice.) **Which read path?**

>A.  Ok, I am reconsidering my answer. It might be faster to process all of this in Nautilus.  Let's do a deeper dive on all of this in a separate prompt doc called `nautilus_prompts.md`.  Create that file and populate it in a similar fashion as this and the other prompt docs.  Log your work.

- **N5 — backup scope + target.** Nautilus isn't backed up → keepers go to
  `AIOcean:` via rclone. Back up **everything** (`pab.db`, `matchup_summary.*`,
  MCMC-chain NPZs, figures, `report_site/`) or just the **reproducible-from-DB
  keepers** (the `pab.db` + summary tables + report, skipping the bulky chains)?
  Target path `AIOcean:PAB/`?

>A.  I think we should back up everything.  Let me know if you need help accessing the AIOcean drive.  This command works for me: `rclone ls AIOcean:`

- **N6 — bucket policy is too open.** `s3://pab`'s policy grants `*` (anyone)
  **GetObject + PutObject + DeleteObject** — so anyone can overwrite/wipe the
  artifacts, not just read them. Tighten to **public `GetObject` only** (writes via
  your authenticated creds)? I can apply it.

>A.  Yes, please do.  

**Q11 — Discover-count is in: 124,218 unique granules = 18.55 TB (~2× the 9.8 TB
free). Off-cloud download is infeasible. How do we run the matchups?** Pick a path
(answer inline):

- **B — In-region AWS `us-west-2` + lazy S3.** The design target. `open_s3` reads
  only the ~MB pixel chunks per matchup — **no 18.55 TB download**, dramatically
  faster. Needs a `us-west-2` instance with the repo + `~/.netrc`. *(My
  recommendation.)*
- **C — Subsample the 882 floats** to a tractable set (e.g. 1 profile/float/month,
  a region, or top-N floats) so the download fits off-cloud. No longer "all
  floats", but stays on the workstation.
- **D — Eviction, off-cloud.** Delete each granule after extraction so disk stays
  bounded — but the full 18.55 TB still transits the network and match is serial
  (~weeks); would also need to parallelize `match`. Slowest.

>A. 

**Q10 — Post-pilot gate: how do we proceed with the full run?** The pilot shows the
full **off-cloud `--download`** run projects to **~8–41 TB and ~11–56 days** — match
(granule downloads), not the fit, is the bottleneck, and it's at/over the 9.8 TB
ceiling. Pick a path (answer inline):

- **A — Discover-first, then decide.** Run `discover` on all 54,506 profiles
  (~10 h, cheap CMR queries, resumable) to get the **true unique-granule count**
  (accounts for cross-profile sharing). Then compute exact disk/time and choose.
  De-risks before any download. *(My recommendation.)*
- **B — Switch to in-region `us-west-2` + lazy S3.** The design target: `open_s3`
  reads only the needed chunks, no multi-TB download, far faster. Needs a cloud
  instance (revisits Q2's off-cloud choice).
- **C — Subsample the selection.** Reduce scope to fit disk/time (e.g. one region,
  1 profile/float/month, or top-N floats). Off-cloud but no longer "all floats".
- **D — Cache eviction, stay off-cloud.** Delete each granule after its matchups
  are extracted (revisits Q9). Bounds disk to a small working set, but match still
  takes ~weeks.

>A. Proceed with Option A 

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

#### Pilot (Task 6) — 50 profiles, off-cloud `--download`, `--jobs 8`

**Two findings; the second is a go/no-go gate.**

**(1) Ingest bug — found & fixed.** Ingest crashed (`IndexError: … 0-dimensional`)
in `summary.moving_median` when a profile carried a **single** `BBP700`/`CHLA`
sample (0-d array → unsliceable), and — worse — the crash **aborted the whole
stage** (only 16 of 50 profiles ingested). Fixes: `moving_median` now `atleast_1d`s
its input; **`ingest` wraps each profile in try/except** and records failures under
`"failed"` (like `build_fits`) so one bad profile can't kill a 50k run. Tests added;
147→ suite green.

**(2) Disk/time gate — TRIPPED.** Per-stage timing (the 16 ingested profiles):

| stage | time | notes |
| --- | --- | --- |
| ingest | 112 s (crashed) | ~7 s/profile (argopy) |
| discover | 11 s | ~0.7 s/profile (CMR) |
| **match** | **1425 s** | **85 granules, 12 GB downloaded**, 4 matchups / 40 pixels |
| fit (×4, jobs=8) | 65 s | parallel fitter works, quiet |
| figure / report | 71 s / 55 s | — |

Key rates: **~5.3 candidate granules/profile**, **141 MB/granule**, **~17 s/granule**
(download+open+extract), **25 % match rate**. **Match (granule download) dominates —
not the fit**, off-cloud.

**Extrapolation to 54,506 profiles:** discover ≈ 10 h; ingest ≈ 4–5 days;
**match ≈ 289k granule-fetches ≈ 41 TB / ~56 days** at the pilot's (low-sharing)
rate — and even if cross-profile granule sharing cuts unique granules 5×, that is
**~8 TB / ~11 days**, at/over the **9.8 TB** ceiling. Fits ≈ 13.6k matchups ≈ hours
(not the bottleneck). **Conclusion: the full off-cloud `--download` run is
infeasible on disk and time as configured.** Paused at the gate for a decision
(revisit Q2 in-region / subsample / eviction / discover-first). See Logs.

#### Discover-count (Option A) — exact granule volume, no downloads

Ran the pipeline's per-profile CMR search over **all 54,506 profiles** (±0.4°,
±1 day, cloud 0–100), unioning granules by name and summing **CMR-reported sizes**
(no downloads). Threaded (8 workers), resumable; ~1.7 h wall.

| metric | value |
| --- | --- |
| profiles queried | 54,506 (944 CMR-failed, ~1.7% — contribute no candidates) |
| candidate refs (with dup) | 303,900 → **5.67 / profile** |
| **unique candidate granules** | **124,218** |
| **total download size** | **18.55 TB** (mean 157 MB/granule) |
| vs 9.8 TB ceiling | **189 % — ~2× over** |
| est. match time @ ~17 s/granule (serial) | **~24 days** |

**Verdict: off-cloud `--download` is out** — 18.55 TB is ~2× the free disk, and
even with eviction the full volume must transit the network (~days–weeks). The
design-target **in-region us-west-2 + lazy S3** avoids the 18.55 TB transfer
entirely (reads only the ~MB pixel chunks). Decision surfaced as Q11.

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

### 2026-07-06 (Task 3 — assembled the full profile selection, count first)

**Window start** (queried live via earthaccess): earliest `PACE_OCI_L2_AOP` granule
= **2024-03-05**; end = today. **Selection** from the Argo synthetic-profile index
(`ArgoIndex(index_file="bgc-s")`, 394,641 rows, loaded in ~6 s): every in-window
profile whose `parameters` list contains **`BBP700` or `CHLA`**.

**Count (reported before any per-profile fetch):** **55,305 profiles / 882 floats**;
after dropping 799 asc/desc `(wmo,cycle)` duplicates → **54,506 profiles** written.
Global coverage (lat −77.6→79, lon ±180; Pacific 23.8k / Atlantic 20.3k / Indian
10.2k); profiles/float min 1, median 62, max 398.

**Output:** `/mnt/tank/Oceanography/data/PAB/full_profiles.csv` (columns
`wmo,cycle,date,latitude,longitude`; kept in `$PAB_DATA_DIR`, out of git). No
existing "select-all-BGC" helper in `pab` (dev CSV was hand-picked), so this was a
one-off script over `ArgoIndex`; `search_params` doesn't exist in argopy 1.4, so I
token-filtered the `parameters` column in pandas.

Learning / flag: **54.5k profiles is a very large run** — ingest (argopy fetch each)
+ discover (CMR query each) alone is multi-day; matched granules feed the ~19k
disk ceiling. **Task 5 (pilot) must extrapolate before the full send**, and
subsampling the 882 floats is a live option if the projected cost/disk is
prohibitive. No package code changed (one-off selection script only).

### 2026-07-07 (Task 4 — implemented parallel `fit_batch`)

Added matchup-level parallelism to the `fit` stage. Design (in `pab/fit/run.py`):
split the old monolithic `fit_matchup` into `_gather_fit_input` (DB-only),
`_fit_only` (pure per-spectrum compute — module-level, picklable) and
`_persist_result` (DB writes). `build_fits(..., jobs=N)`:

- **Serial (`jobs=1`, default):** unchanged behaviour/results — existing tests pass
  untouched.
- **Parallel (`jobs>1`):** granules opened **once each** and pixels extracted in the
  **parent** (the `opener` needn't be picklable); `_fit_only` farmed to a
  `ProcessPoolExecutor`; **all DB writes back in the parent** → no SQLite writer
  contention. In-flight futures bounded at ~2×`jobs` and persisted as they complete
  → memory-bounded and **resumable** (already-persisted `fit_id`s skip on re-run).
- Uses the **`spawn`** start method (avoids the Py3.13 fork-in-a-multithreaded-parent
  deadlock warning) with a `_worker_init` that caps BLAS/OpenMP threads to 1 so N
  workers don't oversubscribe cores.

Wired `PipelineConfig.jobs` + `--jobs` CLI (default 1) → `build_fits`. Updated HOWTO
(new `--jobs` row; removed parallel fitting from "planned"). Tests:
`test_build_fits_parallel_matches_serial` (deterministic stub, 2 workers → same
fit_ids/rows as serial + idempotent re-run) and `test_cli_parser_jobs`; **147
passed**. De-risked the real path: ran the actual `fit_spectrum` in a **spawned**
worker via a guarded script — recovered bbp700 = 0.00346 (truth ≈ 0.00343), chisq
0.026 → bing imports and runs correctly under spawn.

Learnings / flags for the pilot (Task 5): (a) spawn re-imports `__main__`, so it must
be run via the guarded `pab` CLI / `python -m pab.pipeline` (a bare heredoc/`<stdin>`
breaks spawn — not a code bug); (b) BING's emcee prints tqdm progress bars per fit —
across many parallel workers this will be noisy on stderr; consider quieting it (a
BING `progress` flag) or redirecting worker stderr for the full run. Code changed:
`pab/fit/run.py`, `pab/pipeline.py`, tests, `HOWTO.md`.

### 2026-07-07 (Task 5 — suppressed BING's tqdm progress bars)

Followed up the Task-4 flag. BING's `run_emcee` hard-codes emcee `progress=True`
(tqdm bars) plus bare `print()`s (`idx=…`, "Running burn-in", "Running full
model") and exposes **no** flag through `fit_one`/`init_mcmc`. Rather than edit the
separate BING package (working agreement: build on it, don't re-implement), I
suppressed it **PAB-side**: a `_quiet()` context manager in `pab/fit/run.py` that
redirects stdout+stderr to `os.devnull`, wrapped around the single
`bing_inf.fit_one(...)` MCMC call in `fit_spectrum`. It drops only *printed* output
— exceptions still propagate (so a failed fit is still caught + recorded), and it
works in the serial path and in every spawned worker.

Tests: `test_quiet_suppresses_stdout_and_stderr` (prints inside are swallowed,
streams restored after); **148 passed**. Verified on the real path — re-ran the
spawned-worker fit smoke: output is now just the final result line (no bars, no
status prints), fit still correct (bbp700 = 0.00345, truth ≈ 0.00343). This clears
the console-noise blocker for the 54k-matchup run. Code changed: `pab/fit/run.py`,
`pab/tests/test_fit.py`.

### 2026-07-07 (Task 6 — pilot: fixed an ingest crash; disk/time gate tripped)

Ran the full pipeline over 50 representative profiles (isolated
`…/PAB/pilot/`, `--download --jobs 8`). Finished in ~29 min. See the Reports →
Pilot table for numbers.

**Finding 1 — ingest crash (fixed).** `summary.moving_median` did `x[lo:hi]` on a
0-d array (a profile with a single `BBP700`/`CHLA` sample) → `IndexError`, which
**aborted the entire ingest stage** (16/50 done). Fixed `moving_median` (`atleast_1d`)
and, more importantly, made `ingest` **per-profile resilient** (try/except →
`failed` list), so one bad profile can't kill a 50k run. Added
`test_moving_median_handles_scalar_profile` + `test_ingest_survives_a_bad_profile`;
37 passed in argo+pipeline (full suite green).

**Finding 2 — disk/time gate TRIPPED (needs a decision).** Off-cloud, **match
(granule download) is the bottleneck, not fit**: ~5.3 candidate granules/profile,
141 MB each, ~17 s each. Extrapolated to 54,506 profiles → ~289k granule-fetches ≈
**41 TB / ~56 days** at the pilot's low-sharing rate; even with 5× granule sharing,
~**8 TB / ~11 days** — at/over the 9.8 TB ceiling. The full off-cloud `--download`
run is **infeasible as configured**.

**Paused at the gate.** Options put to the user: (A) run `discover` on the full set
first (~10 h, cheap, resumable) to get the *true* unique-granule count before
committing; (B) switch to **in-region us-west-2 + lazy S3** (the design target — no
multi-TB download, far faster; revisits Q2); (C) subsample the 882 floats; (D) turn
on cache eviction (revisits Q9; bounds disk but match still ~weeks). Recommendation:
A to measure, expecting B or C. Awaiting the decision before the full send. Code
changed: `pab/argo/summary.py`, `pab/pipeline.py`, tests.

### 2026-07-09 (Q10=A — discover-count: 18.55 TB, off-cloud ruled out)

Per the user's **Q10 = Option A**, measured the exact candidate-granule volume
without downloading. A one-off threaded script (`discover_count.py`) ran the
pipeline's per-profile CMR search over all 54,506 profiles and summed CMR-reported
granule sizes; ~1.7 h, resumable, 8 workers, retry-on-transient (944/54,506 queries
failed after retries, ~1.7%, harmless).

**Result: 124,218 unique candidate granules = 18.55 TB** (157 MB/granule; 5.67
candidate refs/profile), i.e. **~2× the 9.8 TB free** and ~24 days of serial match.
So off-cloud `--download` for all 882 floats is **definitively infeasible** — even
with eviction the 18.55 TB must transit the network. Recommended pivot to the
design-target **in-region us-west-2 + lazy S3** (Q11-B), which skips the bulk
transfer entirely (reads ~MB/pixel). Surfaced the B/C/D choice as **Q11**; stopped
the 30-min status loop. No package code changed (analysis-only script).

### 2026-07-12 (Task 7 — Nautilus setup status)

Assessed the Nautilus state and wrote a status + plan into Q&A. Discovered the
workstation is **already connected**: active `kubectl` context `nautilus`, working
Nautilus S3 creds (`~/.aws/credentials`, rclone), endpoint
`ENDPOINT_URL=https://s3-west.nrp-nautilus.io`, and `aws s3 ls` lists 9 buckets —
**none PAB-related**. Code-side, the seam exists (`LocalStubBackend` active,
`NautilusS3Backend` a `NotImplementedError` stub, `publish_release`/`build_manifest`
ready for a real backend). So remaining work = (infra) create a PAB bucket [+ K8s
namespace only if running compute there]; (code) implement `NautilusS3Backend.upload`
(boto3 → endpoint, creds from `~/.aws`, config-gated), wire `publish_release`, put
real URLs in the manifest, offline-mocked test, HOWTO §7b.

Key point I flagged: **Nautilus ≠ AWS us-west-2.** Nautilus solves *artifact
hosting* (Q5) + storage, but **not** the PACE-granule read bottleneck (Q11) — those
granules are on NASA AWS us-west-2, and staging 18.55 TB onto Nautilus is the same
infeasible transfer. So Q11 (us-west-2 / subsample / eviction) stays open and
separate. Raised N1–N3 in Q&A (Nautilus scope? bucket name + public/private?
confirm Q11 separate?). Held off creating the bucket/namespace pending the name +
public-vs-private decision (outward-facing, my-to-propose-not-assume). No code
changed.

### 2026-07-13 (Task 8 — read N1–N3; raised N4–N6)

N1 = **Nautilus storage-only** (no compute); **not backed up → keepers rclone'd to
Google Shared Drive `AIOcean`**. N2 = bucket **`pab`, public-read**. N3 = "put files
in Nautilus, Q11 not relevant". Verified infra: **`s3://pab` exists (empty)**;
rclone remotes `nautilus_s3:`, `AIOcean:` (shared-drive root reachable), `GDrive:`
all configured.

Pushed back (respectfully) on N3: storing **outputs** on Nautilus doesn't remove the
need to **read** 124,218 PACE **input** granules (18.55 TB) from NASA AWS us-west-2
to compute the matchups; with compute staying local (N1), the read path is still
B/us-west-2 vs C/subsample vs D/evict — even staging granules on `s3://pab` is the
same big transfer. Raised as **N4** (which read path? — the real open decision).
Also **N5** (backup scope: everything vs reproducible-from-DB keepers; target
`AIOcean:PAB/`) and **N6 — security**: the `pab` policy grants `*` GetObject **+
PutObject + DeleteObject** (public write/delete, not just read) → offered to tighten
to public GetObject-only. Held off changing the policy / creating anything pending
answers. No code changed.

### 2026-07-13 (Task 9 — N4–N6 resolved; Nautilus pivot → new prompt doc)

Read N4–N6. **N6 done:** tightened the `s3://pab` bucket policy from public
Get+Put+Delete to **public `GetObject` only** (`aws s3api put-bucket-policy`;
verified) — writes/deletes now require authenticated creds. **N5 recorded:** back
up **everything** to `AIOcean:` (rclone) since Nautilus isn't backed up. **N4:** the
user is reconsidering — rather than storage-only, it may be **faster to run all the
compute on Nautilus** (co-locating the 18.55 TB reads + 124k fits with Ceph/S3), so
they asked for a dedicated deep-dive doc.

Created **`claude_prompts/nautilus_prompts.md`**, modelled on the other prompt docs
(Goals / Claude / Context / Prompts / Tasks / Q&A / Reports / Logs). It frames the
compute-on-Nautilus plan and pins the crux: **Nautilus nodes aren't in AWS
us-west-2**, so Task 1 must *measure* pod↔NASA-S3 lazy-read throughput before
choosing lazy-read vs a one-time 18.55 TB stage-to-Ceph. Tasks: measure →
containerize → namespace/secrets/storage → data+DB strategy → run stages as K8s
Jobs (fan-out, resumable) → publish to `s3://pab` + rclone to `AIOcean:` → verify.
Open questions M1–M5 (namespace/quota, registry, connectivity, stage-vs-subsample,
compute shape). The full-run conversation continues in that doc. Code changed: none
(applied the bucket-policy fix via aws-cli; authored the new prompt doc).