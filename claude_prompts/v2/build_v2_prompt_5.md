# Build v2 — Prompt 5: backfill the missing matchups + geometry for every pixel (Nautilus)

## Goals

Bring the v2 database up to date: **A** the 2,356 profiles that never had
candidate granules, **B** every BGC profile since the selection was cut
(4,981 as of 2026-09-14; re-queried at run time), **D** the ~475
never-ingested profiles — then fill geometry for **every** matchup pixel so
`fit` can run (`run_full_inelastic.md` Plan §4, §5 steps 4–5; Q5, R5).
Expected: ~+2,200 matchups → ~16.8k in v2.

## Claude

### Skills

- **`batch-fit-argo`** — the checkpoint/resume discipline applies to every
  stage here.

### Working agreements

As in `build_v2_prompt_1.md`. Jobs write only to `/data/v2/pab.db`
(`PAB_DATA_DIR=/data/v2`). Shared-infrastructure manners: `--ingest-jobs ≤ 32`
(GDAC), `--discover-jobs 8` (CMR), `match --jobs 16` (memory-bound). Confirm
each Job launch with the user.

**Settled in Prompts 1–4 — no longer open:**

- **Use image `:2.0.1`, not `:2.0.0`.** `:2.0.0` shipped a `figure` stage that
  fails for *every* 2.0 fit (a `B_p` batch-shape bug, Prompt 4 Q4). `:2.0.1`
  fixes it. `:latest` also points at `:2.0.1`.
- Every 2.0 job needs **`PYTHONWARNINGS=ignore`**: `robust` emits a
  `DomainWarning` once per forward-model call — correct, but thousands of lines
  per fit, and it buried a real traceback in the Prompt 4 validation until it
  was suppressed.
- `pab_version` is `"2.0"`; `FitConfig` defaults are the inelastic
  configuration at **400–700 nm** (JXP moved `wave_max` back from 720 —
  Prompt 3 Q2).
- Test baseline **336 passed, 1 skipped**.
- Reusable patterns from Prompt 4: `nautilus/v2_validate_job.yaml` (env,
  secrets, mounts) and `nautilus/v2_validate_gates.py` — a ConfigMap-mounted
  gate script that **exits non-zero**, so a Job goes red instead of needing a
  human to read the log. Worth copying for each Job here.

## Context

- Plan §4 (the gap table) and §5 of `claude_prompts/v2/run_full_inelastic.md`.
- `claude_prompts/run_full_pipeline.md` Task 16 (why a subset re-`discover`
  needs `--profiles-csv` **and `--replace`**: the coverage-skip test would
  skip gap-A profiles again) and the 1k/full-run gates; `nautilus/
  rediscover_csv.py`, `nautilus/rediscover_job.yaml`, `nautilus/
  full_ingest_job.yaml`, `nautilus/full_match_job.yaml`, `nautilus/
  coverage_check.py`.
- Selection method (Task 3 of the first run): `argopy.ArgoIndex(index_file=
  'bgc-s')`, token-filter `parameters` for `BBP700` or `CHLA`, drop
  asc/desc duplicates; columns `wmo,cycle,date,latitude,longitude`.
  Original CSV: `/mnt/tank/Oceanography/data/PAB/full_profiles.csv`
  (54,506 rows; 54,031 ingested).
- Standing rule (R5): **the selection window ends "today at run time"**.
- Gap A query: profiles with `time > '2026-06-01'` and no granule covering
  them (the DB's granules stop 2026-06-01 — check CMR now for how far the
  `PACE_OCI_L2_AOP` forward stream reaches; if it still lags, gap A/B
  profiles newer than the stream can only be matched later).

### State as of 2026-09-17 (Prompts 1–4 delivered)

**The PVC is re-laid out and `/data/v2/pab.db` is staged and verified:**

| | |
|---|---|
| `/data/v2/pab.db` | sha256 `ef552419…c127b735`, 120,635,392 B, **schema v5** |
| contents | 881 floats / 54,031 profiles / 67,435 granules / **14,610 matchups** / **146,100 pixels** / 14,609 `NASA_GIOP` fits / 116,872 `fit_results` |
| **geometry** | **0 of 146,100 pixels filled** — Task 5 has the whole backlog |
| BING fits | 0 |
| `/data/v2/fit_chains`, `/data/v2/pipeline` | exist, empty |
| `/data/v1` | 45 G — the 1.0 run's outputs + 14,633 chains. **`/data/v1/pab.db` does not exist**: the stale DB that was at `/data/full/pab.db` is now `pab_stale_2026-08-20.db` |
| volume | 46 G of 500 G used, 455 G free |

The workstation copy of `v2/pab.db` is `chmod a-w` — **`/data/v2/pab.db` is the
single writer's copy** until Prompt 7.

**Measured in-pod cost (Prompt 4 Task 4, `:2.0.0`, `--jobs 4`, one matchup):**

| stage | in-pod | workstation |
|---|---:|---:|
| `geometry` | **47 s** / granule | ~9 s / granule |
| `fit` | **226 s** / fit | ~101 s (uncontended) / ~181 s (3-way contended) |

**Treat both as upper bounds, not rates.** Each is a *single* measurement
including pool startup, and the fit includes JAX's first compile. That is
precisely why Task 5's gate says to re-measure. Naive projections, so the
shape is visible:

- **geometry**, 11,494 existing granules (confirmed by query) + the backfill's
  → ~13.5 k opens. At 47 s ÷ 8 workers ≈ **22 h**; at the workstation's 9 s
  ≈ **4 h**. A 5× spread on a day-long job is worth resolving with a
  200-granule slice before committing.
- **fit**, ~16.8 k matchups at 226 s ÷ 16 workers ≈ **66 h**; at 101 s
  ≈ **29 h**. This is the number Task 5 is asked to feed back into Plan §3.

**Two things about the `geometry` stage this prompt should know:**

1. **It makes one CMR query per granule, uncached** —
   `l1b_source_for_aop` searches `PACE_OCI_L1B_SCI` for every granule, so
   ~13.5 k searches. At `--jobs 16` that is 16 concurrent CMR queries *plus* 16
   concurrent 1.8 GB L1B reads. The working agreements above already cap
   `--discover-jobs` at **8** for CMR etiquette; **the same cap belongs here**,
   and Task 5's `--jobs 16` should probably be `--jobs 8`. Flagging rather than
   silently changing the task.
2. **It is idempotent on `theta_s IS NULL` and resumes for free.** A run that
   dies part-way does zero network work for pixels already filled, a granule
   that fails transiently is recorded in `failed` (never raised) and picked up
   by the next run, and a per-pixel grid-check failure lands in `mismatched`
   without costing that granule's other pixels. The "sweep re-run" the gate
   asks for is simply running the stage again.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below
6. Execute the 6th task in Tasks below

## Tasks

1. **Selections (workstation, read-only on the DBs).** Build three CSVs
   under `$PAB_DATA_DIR/v2/`: `backfill_A.csv` (gap A from the v2 DB),
   `backfill_B.csv` (live index, `date > 2026-07-06` → today, dedupe
   against `profiles`), `backfill_D.csv` (original selection minus
   `profiles`). Report counts, float counts, lat/lon/time spread. Query
   CMR for the latest `PACE_OCI_L2_AOP` granule time and state how much of
   B is currently matchable. Stage the CSVs on the PVC (`/data/v2/`) — they
   exceed nothing, but ConfigMaps cap at 1 MiB, so use the PVC. Log.

2. **Ingest (B + D).** `nautilus/v2_ingest_job.yaml` (from
   `full_ingest_job.yaml`; image **`:2.0.1`**; `--db /data/v2/pab.db
   --profiles-csv /data/v2/backfill_BD.csv --stage ingest --ingest-jobs 32`).
   Gates: failure rate ≈ 2–3 % (argopy transients); one resume pass to
   sweep; the new `mld_summary` rows stamped `2.0`. Log counts + wall-clock.

   **Per JXP (Q1a/b):** ingest **all** of B (5,187) and **all** of D (475),
   not just the currently-matchable subsets.

   **New deliverable (Q1b):** after the resume pass, write the profiles that
   **failed ingest twice** to `/data/v2/ingest_failures.csv` (and copy it back
   to `$PAB_DATA_DIR/v2/`) — `wmo,cycle,date,latitude,longitude` plus a
   `reason` column with the argopy error. JXP will chase these with
   colleagues. Expect gap D to dominate it: 372 of D's 475 have no position,
   and historically only ~13.5 % of such profiles ever resolve. Distinguish
   in the `reason` whether argopy returned nothing at all versus returned a
   profile with no usable `BBP700`/`CHLA`, since those are different
   conversations to have.

3. **Discover (A + B).** `nautilus/v2_discover_job.yaml`: `--stage discover
   --profiles-csv /data/v2/backfill_AB.csv --replace --discover-jobs 8`.
   Gates: searches ≈ |A ∪ B| with ~0 failed; granule delta; then
   `coverage_check.py` on the v2 DB — candidates/profile for the backfill
   set ≈ the 5.67 CMR truth. Log.

4. **Match.** `nautilus/v2_match_job.yaml` (from `full_match_job.yaml`;
   16 workers / 100 Gi; `ulimit -n 65536`; `--stage match --jobs 16`).
   Only profiles without a matchup are processed; expect ~28 % of A+B+D.
   Gates: FDs bounded, stalls recovered, plateau reached. Report new
   matchups by gap, distance/Δt medians. Log.

5. **Geometry for every pixel.**  Begin by reading my answer to Q5 in the Q&A section below.  
   React to that before moving on to the rest of this task.
   `nautilus/v2_geometry_job.yaml`:
   `--stage geometry` over the whole v2 DB (**11,494** existing granules —
   confirmed by query — plus the backfill's, so ~13.5 k unique L1B opens).

   **Use `--jobs 8`, not 16.** This stage issues **one uncached CMR query per
   granule** on top of the L1B read, so `--jobs 16` means 16 concurrent CMR
   searches — against the same shared NASA infrastructure the working
   agreements already cap at `--discover-jobs 8`. Say so in the report if you
   deviate.

   **Measure before committing.** Run a **~200-granule slice first** and
   report s/granule from it. The two single-granule measurements in hand
   disagree 5× (47 s in-pod, ~9 s on the workstation), which is the difference
   between a 4-hour job and a 22-hour one; both are startup-dominated and
   neither is a rate.

   Gates: every `matchup_pixels` row has `theta_s`; `geom_source = 'L1B_V3'`;
   `theta_v` spans 0–~60°; `dphi` inside (−180, 180]; failures listed with
   causes (an L1B missing from CMR, grid-check failures) and a sweep re-run —
   which for this stage is simply running it again, since it is idempotent on
   `theta_s IS NULL` and does zero network work for filled pixels. Log
   s/granule and wall-clock; **update the fit-cost projection** in Plan §3
   using Prompt 4's in-pod **226 s/fit** (an upper bound: one fit including
   JAX's first compile) — ~16.8 k matchups ÷ 16 workers ≈ **66 h**, or ≈ 29 h
   at the workstation's 101 s/fit. Narrow it with the fit timing Prompt 6
   measures rather than leaving the range in the plan.

6. **Update.** Based on what you have done, update the prompt doc
   `build_v2_prompt_6.md`, as needed. Log.
   *(Added 2026-09-17, mirroring the Task 5 JXP added to
   `build_v2_prompt_1.md`. Delete it if that is not the intent.)*

## Q&A

### Q1 (Task 1, 2026-09-17) — the backfill yield is **~1,250 matchups, not ~2,200**; confirm how to handle the two causes

Task 1's selections are built and staged. Two measured facts cut the expected
yield roughly in half, and both need a decision before Tasks 2–4 run.

#### (i) PACE's forward stream ends **2026-08-01** — 6.5 weeks behind today

CMR, queried now: `PACE_OCI_L2_AOP` has 8,571 granules in
2026-06-01…2026-12-31, latest acquisition **2026-08-01T20:50:06Z**. The
Context anticipated this ("if it still lags, gap A/B profiles newer than the
stream can only be matched later"). It does lag:

| | profiles | matchable now (≤ 2026-08-01) | not yet |
|---|---:|---:|---:|
| **A** (2026-06-01…07-06) | 2,409 | **2,403** | 6 |
| **B** (2026-07-06…09-17) | 5,187 | **1,944** | **3,238** |

So **63 % of gap B cannot be matched yet**, no matter what we run.

**Question (a):** ingest all 5,187 of B anyway, or only the 1,944 that are
currently matchable? Ingesting all costs ~1.5 h of GDAC time for 3,238
profiles that cannot produce a matchup until PACE catches up — but they are
real BGC profiles, the ingest is the slow part, and a later `discover`/`match`
sweep would then pick them up for free.
*My recommendation: ingest all of B.* The profiles are the durable asset and
re-ingesting later costs the same; only `discover`/`match` should be
restricted to the matchable window (which they effectively self-restrict to
anyway, since no granules exist beyond it).

>A. Yes, ingest all of B.

#### (ii) Gap D is **78 % position-less**, and that predicts failure

Of D's 475 never-ingested profiles, **372 have no lat/lon** in the original
selection CSV. That is not incidental — it is close to the reason they were
never ingested. Evidence from the rows that *were* ingested: 807 original CSV
rows had a blank position, 435 of them ingested, and in a 200-row sample only
**27 (13.5 %)** ended up with a position from argopy. A profile with no
position is recorded by `match` as "no position to match against" and can
never yield a matchup.


**Question (b):** re-attempt ingest on all 475 of D, or only the 103 with
positions? *My recommendation: all 475* — ingest is cheap at this size, and
the 13.5 % that do recover a position are free matchups — but expect ~29 new
matchups from D, not the plan's ~130.

>A. Yes, re-attempt ingest on all 475 of D.  For those that fail again, provide a list in a separate file that I can try to hunt down with colleagues.

#### Revised expectation for Plan §4

| gap | matchable & positioned | × 28 % |
|---|---:|---:|
| A | 2,403 | ~673 |
| B | 1,944 | ~544 |
| D | 103 | ~29 |
| **total** | | **~1,246** |

against Plan §4's **~2,200**. That puts v2 at roughly **15.9 k matchups**, not
16.8 k — which also lowers the fit-cost projection Task 5 is asked to update.

**Question (c):** should Plan §4 be amended now with these numbers, or left
as-is until the jobs actually report?
*My recommendation: amend it* — the gap between 2,200 and 1,246 is large
enough that a later reader would otherwise treat the shortfall as a failure.

>A. Ok, amend it.

### Q2 (Task 2, 2026-09-17) — confirm launching `pab-v2-ingest` (first Job that writes to the v2 database)

`nautilus/v2_ingest_job.yaml` + `nautilus/v2_ingest_failures.py` are written
and validated; nothing has been launched. This is the **first Job that writes
to `/data/v2/pab.db`**, the single writer's copy, hence the confirmation.

| | |
|---|---|
| image | **`:2.0.1`** (`sha256:d586afb2…`) |
| selection | `/data/v2/backfill_BD.csv` — **5,662** profiles (B 5,187 + D 475, disjoint), per Q1a/b **all** of both |
| stages | `ingest` only, **two passes** (pass 2 is the resume sweep; ingest skips what is already stored) |
| flags | `--ingest-jobs 32` (the GDAC cap in the working agreements) |
| resources | 34 CPU / 48 Gi, `backoffLimit: 4` (preemption-tolerant, resumes from the DB) |
| est. wall | **~3.3 h** for pass 1 at the pilot's measured 2.1 s/profile, plus a short sweep |
| writes | `profiles` + `mld_summary` rows in `/data/v2/pab.db`; `/data/v2/ingest.log`; `/data/v2/ingest_failures.csv` |

**One trap found and removed.** `full_ingest_job.yaml` sets
`PYTHONPATH=/data/src`. That directory was **deleted** in the Prompt 4 PVC
re-layout, and I confirmed it is gone. Had it been copied across and the
directory still existed, it would have put a stale **1.0** package ahead of
the image's 2.0 one on `sys.path` — the job would have run the wrong code and
said nothing. The v2 job does not set `PYTHONPATH` at all.

**The failure list (Q1b)** is produced by a ConfigMap-mounted script after the
sweep, splitting failures into the two categories you will want to treat
differently:

- `no_profile_row` — argopy returned nothing for that `(wmo, cycle)`; the
  exception class is recovered from the run log where available.
- `no_mld_summary` — the profile *was* fetched but carried no usable
  `BBP700`/`CHLA`.

Each row also carries `has_position`, since 372 of D's 475 have none.
Dry-run against the current database gives the expected pre-ingest baseline:
all 475 of D as `no_profile_row`, 372 without a position.

**Question:** launch it?

*My recommendation: yes.* It is resumable, it only adds rows, and nothing
downstream can proceed without it. The one thing worth deciding now rather
than at 3 h in: if pass 1's failure rate comes back well above the expected
2–3 %, should I stop and report, or let pass 2 run regardless? *I suggest
letting pass 2 run* — it is cheap, it is the thing that distinguishes a
transient from a real failure, and the failure list is more useful after it.

>A. 1. yes; 2. let pass 2 run

**Launched 2026-09-18T05:50Z** as Job `pab-v2-ingest`. In-pod provenance
confirms the right image is running: `pab_version 2.0`,
`git_sha {"PAB":"8c7ab8a", …, "retrieve-or-bust":"e1f4289"}`. Baseline counts
before the run: 54,031 profiles / 54,031 `mld_summary` / 67,435 granules /
14,610 matchups / 14,609 fits.


### Q3 (Task 2, 2026-09-18) — ingest is running **5× slower than planned** (17 h, not 3.3 h). Let it run?

`pab-v2-ingest` is **healthy**: 650/5,662 profiles after 2 h, **0 failures**.
The problem is the rate.

| | |
|---|---|
| observed | **~11.0 s/profile**, flat across 2 h (12.4, 11.0, 11.0, 11.1, 10.8, 11.2, 10.9, 11.0, 11.3, 10.6, 10.3) |
| planned | 2.1 s/profile (the 1k pilot, 32 procs) |
| pass 1 projection | **~17.4 h total, ~15.4 h remaining** (finishes ~23:20Z) |
| failures | **0** |

**The workers are there but idle-waiting.** 36 python processes in the pod, so
the 32-process pool did start — but each sits at **~1.5 % CPU**, and the pod
draws **24 millicores** of its 34-core request. They are blocked on the
network, not parsing.

That directly contradicts what `_ingest_executor`'s docstring records from the
pilot: *"the fetch is not network-bound but bound by argopy's Python-side
parsing, so the GIL, not the servers, is the ceiling"* (serial 6.2 s → 12
threads 2.75 → 12 processes 0.97). Processes were the fix **because** the
bottleneck was local. Here the bottleneck is remote, so extra processes buy
nothing — and a dead-flat 11.0 s/profile over two hours is the signature of
**server-side rate limiting**, not of a slow or variable server.

**Options:**

1. **Let it run.** 15 h more, zero failures, fully resumable, and the
   selection only has to be ingested once.
2. **Kill and restart with fewer workers** (e.g. 8–16). If the GDAC is
   throttling per-connection this changes nothing; if it is penalising a
   32-connection burst it could help. Ingest is idempotent so the 650 already
   done are skipped — the restart costs minutes, not progress.
3. **Kill and restart against a different argopy source** (`erddap` rather
   than `gdac`). Larger change, unproven for this selection, and it would make
   these profiles' provenance differ from the 54,031 already in the store.

*My recommendation: option 1, let it run.* It is producing perfect output, the
cost is wall-clock on a machine that is otherwise idle, and options 2 and 3
are experiments whose payoff is speculative while option 1 is certain. 15 h is
tolerable for a one-off backfill, and Task 3 (discover) cannot start until
ingest finishes regardless.

**Worth fixing regardless of the answer:** the 2.1 s/profile figure in
`full_ingest_job.yaml`'s sizing comment and in `_ingest_executor`'s docstring
is now known not to generalise — the ceiling moved from local (GIL) to remote
(GDAC). I will record the measured 11 s/profile in the Task 2 report either
way, so the next sizing does not start from a number that no longer holds.

>A. let it run

Left running (option 1). Pass 1 ETA ~23:20Z 2026-09-18; pass 2 should be
quick, since it only retries what pass 1 missed and ingest skips what is
already stored.


### Q4 (Task 3, 2026-09-18) — confirm launching `pab-v2-discover`

`nautilus/v2_discover_job.yaml` is written and validated; the
`pab-v2-coverage` ConfigMap is created. Nothing launched.

| | |
|---|---|
| image | `:2.0.1` |
| selection | `/data/v2/backfill_AB.csv` — **7,596** profiles (A 2,409 + B 5,187) |
| flags | `--stage discover --replace --discover-jobs 8` |
| resources | 8 CPU / 24 Gi, `backoffLimit: 4` |
| est. wall | **~1.4 h** at the 2026-08 rediscover's 0.66 s/search — **unverified**, see below |
| writes | `granules` rows in `/data/v2/pab.db`; `/data/v2/discover.log` |

**`--replace` is doing real work here, not belt-and-braces.** `discover` skips
a profile when some already-stored granule covers it in space and time — and
that test is precisely what left gap A without its own search in the first
place. Without `--replace` the job would skip 2,409 of its 7,596 profiles,
report success, and leave gap A exactly as it was. The store now holds 67,435
granules (up from 2,734 when this trap was first hit), so the skip test is
*more* likely to fire, not less.

**Expect ~3,222 searches to return nothing.** PACE's forward stream ends
2026-08-01 (measured in Task 1), so those gap-B profiles are newer than any
available granule. That is not a failure, and it is not wasted: a profile with
no granules is never skipped by the coverage test, so they are re-searched for
free once PACE catches up.

**On the time estimate.** The comment says ~1.4 h from the 0.66 s/search the
2026-08 rediscover measured. After the ingest came in **5× slower** than its
pilot figure — because the bottleneck had moved from local to remote without
anything in the repo noticing — I would rather not repeat that. The job logs
progress every 50 searches; I will take the rate from the first few hundred
and report the real projection rather than defending the comment.

**Question:** launch it?

*My recommendation: yes.* It only adds `granules` rows, it is resumable, it
is a prerequisite for Task 4 (match), and at 8 threads it is within the CMR
etiquette cap the working agreements set.

>A. yes, launch it.  I will then /exit

**Launched 2026-09-19T04:22Z** as Job `pab-v2-discover`
(pod `pab-v2-discover-xbglm`).

**Rate measured from the job rather than assumed** (the thing I said I would
do): 100 searches in 109 s at 8 threads = **1.09 s/search**, against the
manifest comment's 0.66. So **~2.3 h**, not 1.4 — ~1.6× the August figure,
nowhere near the ingest's 5×. ETA **~06:38Z**. Yield so far 2.4 granules per
search.

Note `discover` reports **7,535** searches, not 7,596: the selection is
restricted to profiles that exist in the store, and 61 of the CSV's rows are
among Task 2's 73 ingest failures.


### Q5 (Task 4, 2026-09-20) — `match` does **not** honour `--profiles-csv`; it would re-attempt 36,966 known-negative profiles (~35 h vs ~6 h)

`nautilus/v2_match_job.yaml` is written and validated. Nothing launched. But
the task's premise — *"Only profiles without a matchup are processed; expect
~28 % of A+B+D"* — is half true, and the half that is wrong costs ~29 hours.

**`match` takes no profile selection.** `pipeline.match()` calls
`build_matchups(store, …)`, which sweeps `qualifying_profiles(store)` — every
profile with an `mld_summary`. Unlike `discover`, `config.selection_keys()` is
never consulted. The HOWTO does say this ("`match`/`fit`/`figure` always work
from the store"), but the task was written expecting the backfill only.

**What it would actually attempt:**

| | profiles |
|---|---:|
| with an `mld_summary` | 59,620 |
| already matched → skipped before any granule opens | 14,610 |
| **attempted** | **45,010** |

and of those attempted:

| | profiles | can a Task-3 granule help? |
|---|---:|---|
| time ≥ 2026-05-31 | **7,592** | **yes** — this is the backfill set |
| time < 2026-05-31 | **36,966** | **no** — see below |
| no position | 452 | no (cheap: no granule opened) |

**Why the 36,966 are known negatives.** Every granule Task 3 added starts
2026-06-01 or later (new granules by month: 2,537 in 06, 2,825 in 07, 92 in
08; the pre-existing 67,349 all ≤ 2026-06-01). The match window is ±24 h, so
only a profile from **2026-05-31** onward can possibly see one. The other
36,966 have a candidate pool **identical** to the 1.0 run that already
rejected them — they will open the same granules and fail the same way.

**Cost, from the 1.0 run's measured ~7 s/profile at 16 workers (42 h for
50,292):**

| | attempted | est. wall |
|---|---:|---:|
| as the task specifies | 45,010 | **~35 h** |
| restricted to ≥ 2026-05-31 | 7,592 | **~6 h** |

~82 % of the granule-opening effort would re-derive known-negative results.

**Options:**

1. **Run it as written** — ~35 h, no code change, and it is strictly complete:
   if any pre-June profile *does* benefit, it is caught.
2. **Teach `match` to honour a selection**, as `discover` already does. The
   machinery exists: `PipelineConfig.selection_keys()` returns
   `{(wmo, cycle)} | None`, `discover` consults it at `pipeline.py:473`, and
   `None` already means "no selection given, sweep everything". Passing it
   into `build_matchups` and filtering `qualifying_profiles` is a small,
   precedented change that also removes a documented asymmetry between the
   stages. Then run with `--profiles-csv /data/v2/backfill_AB.csv` (plus D),
   ~6 h.
3. **Run as written but accept it as a one-off**, and note the asymmetry for a
   later cleanup.

*My recommendation: option 2.* It saves ~29 h of cluster time on this run
alone, the change is a handful of lines against an existing, tested mechanism,
and `match` silently ignoring `--profiles-csv` while `discover` honours it is
a trap that will catch someone again. I would add a test pinning both
behaviours (selection given → restricted; absent → whole store).

**If you prefer option 1**, the manifest as written is ready to launch
unchanged — it is correct, just slow.

**A related caveat either way:** expect ~1,350 new matchups (Task 3's per-gap
table), **not** the ~15,406 total that `coverage_check.py`'s closing line
projects — that figure applies 28 % to every candidate-bearing profile,
including the ~40 k already attempted and rejected.

>A. Let's adopt your recommendation.

**Implemented 2026-09-21.** `build_matchups` gained an optional
`selection: set[tuple[int, int]] | None`, and `pipeline.match` now forwards
`config.selection_keys()` — the same mechanism `discover` has used since
2026-08. `None` still means "sweep the whole store", so a bare
`pab --stage match` is unchanged.

Four tests pin the behaviour: no selection sweeps every profile; a selection
restricts to it; an **empty** set means no profiles rather than all (the
`None`-vs-`set()` distinction that makes the default safe); and
`pipeline.match` actually forwards the keys. Suite **340 passed**.
`HOWTO.md`'s `--profiles-csv` row corrected — it stated that
`match`/`fit`/`figure` always work from the store.

**Verified against the real store**, not just in tests:

```
whole store with a summary : 59,620
selection matches          :  7,998
of those, not yet matched  :  7,998   <- what match will attempt
unrestricted would attempt : 45,010
```

**5.6× less work.** `backfill_ABD.csv` (8,071 rows, A+B+D deduped) built and
staged to `/data/v2/`, md5 verified.

### Q6 (Task 4, 2026-09-21) — confirm launching `pab-v2-match`

| | |
|---|---|
| image | `:2.0.1` |
| selection | `/data/v2/backfill_ABD.csv` → **7,998** profiles attempted |
| flags | `--stage match --jobs 16`, `ulimit -n 65536` |
| resources | 16 CPU / **100 Gi** — a memory constraint, not a speed choice: 32 workers on 80 Gi OOM-killed six times in the 1.0 run |
| est. wall | **~6 h** at the 1.0 run's measured ~7 s/profile |
| expect | **~1,350 new matchups** (14,610 → ~15,960) |
| writes | `matchups` + `matchup_pixels` in `/data/v2/pab.db`; `/data/v2/match.log` |

Protections carried over from the 1.0 run, all still active: per-granule
120 s read timeout, chunked pools with a 120 s stall guard, the resume
pre-filter (matched profiles skipped before any granule opens), and the
footprint pre-filter (~6 candidate opens/profile instead of ~291).

**Question:** launch it?

*My recommendation: yes.* This is the last prerequisite for Task 5 — geometry
needs the new `matchup_pixels` rows to exist, which is why Task 5 was not
runnable first.

>A. Let's adopt your recommendation.

### Q7 (Task 4, 2026-09-22) — **my error**: I launched match against an image that predates the fix. Blocked on a commit.

Launched `pab-v2-match` on your go-ahead, then **killed it after 5 minutes**.
It reported

```
match: 40414 profiles over 16 processes
```

— the unrestricted whole-store number (55,022 candidate-bearing − 14,610
matched), not the **7,998** the selection should have given. **No damage:
0 matchups were written and the database is byte-for-byte unchanged**
(14,610 matchups, 146,100 pixels, as before).

**Cause, confirmed rather than guessed.** `:2.0.1` was built on 2026-09-17
from PAB `8c7ab8a`. The `match` selection change is from **2026-09-21** — four
days later — and is still **uncommitted** in the working tree. Checked
directly in the image:

```
build_matchups accepts selection: False
```

So the running code could not possibly have honoured `--profiles-csv`. The
job's own provenance line printed `{"PAB":"8c7ab8a", …}` and I did not compare
it against the commit my change needed. That is the whole purpose of baking
the SHA in, and I walked past it.

**What is needed to unblock — a commit, which is yours to make.** The image
build rsyncs the *working tree*, so I could build from uncommitted code, but
the baked SHA would then name a commit that does not contain the change: the
precise provenance lie I avoided when building `:2.0.1` and flagged in that
task's log. I am not going to introduce it now.

Files carrying the change:

- `pab/matchup/engine.py` — `build_matchups(..., selection=None)`
- `pab/pipeline.py` — `match()` forwards `config.selection_keys()`
- `pab/tests/test_matchup.py` — four tests pinning both behaviours
- `HOWTO.md` — the `--profiles-csv` row corrected

Once committed:

1. rebuild as **`:2.0.2`** (~10 min; the guards re-run),
2. push `:2.0.2` + `:latest` (**needs your confirmation** — outward-facing),
3. relaunch `pab-v2-match` unchanged; the manifest already points at
   `backfill_ABD.csv`, only the `image:` tag changes.

**Question:** commit those four files, and confirm the `:2.0.2` push when I
get there?

*What I will do differently:* before launching any job that depends on a code
change, diff the image's baked `PAB` SHA against the commit that carries the
change — a one-command check that would have caught this before 16 cores were
scheduled.

>A. Let's adopt your recommendation.  


## Reports

### Task 1 — backfill selections (2026-09-17): **done, and the yield estimate halves**

Five CSVs built under `$PAB_DATA_DIR/v2/` and staged to `/data/v2/`, **all
five md5-verified** on the PVC. The DBs were only read (the workstation copy
is `chmod a-w` anyway).

| file | rows | floats | with position | matchable now | date span |
|---|---:|---:|---:|---:|---|
| `backfill_A.csv` | 2,409 | 655 | 2,403 | 2,403 | 2026-06-01 … 07-06 |
| `backfill_B.csv` | 5,187 | 691 | 5,082 | **1,944** | 2026-07-06 … 09-17 |
| `backfill_D.csv` | 475 | 29 | **103** | 103 | 2024-03-07 … 2026-06-21 |
| `backfill_BD.csv` *(Task 2 ingest)* | 5,662 | 702 | 5,185 | 2,047 | |
| `backfill_AB.csv` *(Task 3 discover)* | 7,596 | 708 | 7,485 | 4,347 | |

A, B and D are disjoint; the union is 8,071 profiles. Lat spans −66.7…78.8,
lon −179.8…180.0 — global, as expected.

**Against Plan §4's sizing:** A is 2,409 (planned 2,356), B is 5,187 (planned
4,981 as of 09-14 — re-queried today, per R5, so it grew as expected), D is
475 (planned ~475). The *counts* are close. The **yield** is not, for two
measured reasons — both raised as **Q1**:

1. **PACE's `PACE_OCI_L2_AOP` forward stream ends 2026-08-01**, 6.5 weeks
   behind today. 3,238 of B's 5,187 profiles (63 %) have no PACE data to match
   against yet.
2. **Gap D is 78 % position-less** — 372 of 475 have no lat/lon, and the
   evidence says a blank position predicts both ingest failure and no position
   after ingest (of 807 such rows originally, 435 ingested and only 13.5 % of
   a 200-sample recovered a position). A profile with no position can never
   produce a matchup.

Revised: **~1,246 new matchups**, not ~2,200 → v2 ends around **15.9 k**
matchups rather than 16.8 k. That also lowers the fit-cost projection Task 5
is asked to update.

**Q1 answered (JXP, 2026-09-17) and acted on:**

- **(a)** ingest **all** of B — recorded in Task 2.
- **(b)** re-attempt **all 475** of D, and write the profiles that fail a
  second time to a separate list for JXP to chase with colleagues — added to
  Task 2 as `/data/v2/ingest_failures.csv`, with a `reason` column that
  distinguishes "argopy returned nothing" from "returned a profile with no
  usable `BBP700`/`CHLA`".
- **(c)** **Plan §4 amended** in `run_full_inelastic.md` — the gap table now
  carries the measured counts, the with-position and matchable-now columns,
  and the revised **~1,250 matchups / ~15.9 k fits** (down from ~2,200 /
  16.8 k), with both causes and the decisions recorded inline.

**Method note.** Gap B was rebuilt from the live `bgc-s` index (408,062 rows,
loaded in 5 s), token-filtered on `parameters` for `BBP700`/`CHLA` (194,884),
asc/desc-deduped to one row per `(wmo, cycle)` (189,080), cut to
`date > 2026-07-06` (5,206), then deduped against the 54,031 profiles already
in the store (5,187). Gap A is "ingested, no matchup, `time > 2026-06-01`" —
2,409, against the plan's 2,356; the difference is definitional (no *matchup*
versus no *candidate granule*) and A is re-`discover`ed with `--replace`
regardless.


### Task 2 — backfill ingest of B + D (2026-09-18): **done — 5,589 / 5,662 (98.7 %)**

Job `pab-v2-ingest` on `:2.0.1`, launched 05:50Z, **Complete** at 22:10Z.
In-pod provenance confirmed the right image: `pab_version 2.0`,
`git_sha {"PAB":"8c7ab8a", …, "retrieve-or-bust":"e1f4289"}`.

| | profiles | `mld_summary` |
|---|---:|---:|
| before | 54,031 | 54,031 |
| after pass 1 | 59,617 | 59,617 |
| after pass 2 | **59,620** | **59,620** |
| **added** | **+5,589** | **+5,589** |

`mld_summary` tracks `profiles` exactly — every ingested profile produced a
summary. `granules`, `matchups` and `fits` unchanged, as expected for an
ingest-only job.

**Failure rate 1.3 %** — inside the 2–3 % gate, and better than it. Pass 1
missed 76; pass 2 retried exactly those 76 and recovered **3**, leaving **73**
genuine failures. That is the split the two-pass design exists to produce: 3
were argopy transients, 73 are real.

**`ingest_failures.csv`** (73 rows) written to `/data/v2/` and copied back to
`$PAB_DATA_DIR/v2/` for JXP. All 73 are `no_profile_row` — argopy returned
nothing at all for that `(wmo, cycle)`; **none** were `no_mld_summary`, so
nothing was fetched-but-unusable. Only **4 of the 73** lacked a position in
the selection CSV.

#### Two measured findings that correct earlier assumptions

**1. Gap D's position-less profiles were fine — I was wrong about them.**
In Q1 I predicted D would dominate the failure list, reasoning that 372 of its
475 profiles had no position and that historically only ~13.5 % of such
profiles ever acquire one. **368 of those 372 ingested, and all 368 gained a
position from argopy** — 99 %. The 13.5 % figure came from sampling rows
ingested in the *original* run, which had failed for their own reasons; it
said nothing about what a *fresh* fetch would return. Gap B's 105
position-less profiles split roughly as I expected (50 of 105 recovered), so
the error was specific to D. **Plan §4 has been corrected** — D is worth ~113
matchups, not ~29, and the revised total is **~1,338**, not ~1,246.

**2. Ingest ran 5× slower than the documented rate, and the bottleneck
moved.** ~**11.0 s/profile**, flat to within 10 % across 16 h (12.4, 11.0,
11.0, 11.1, 10.8, 11.2, 10.9, 11.0, 11.3, 10.6, 10.3 …), against the pilot's
2.1 s/profile. 36 python processes were confirmed running, so the 32-process
pool did start — but each sat at ~1.5 % CPU and the pod drew **24 millicores
of a 34-core request**. The workers were blocked on the GDAC, not parsing.

`_ingest_executor`'s docstring records the opposite from the pilot — *"the
fetch is not network-bound but bound by argopy's Python-side parsing, so the
GIL, not the servers, is the ceiling"* — which is why processes were chosen
over threads. Here the ceiling is remote, so extra processes buy nothing, and
a dead-flat rate over 5,662 fetches is the signature of rate limiting rather
than of a slow or variable server. **Both stale figures have been annotated**
(`pab/pipeline.py::_ingest_executor` and `nautilus/full_ingest_job.yaml`'s
sizing comment) so the next run is not sized from 2.1 s/profile.

Wall-clock: pass 1 **16 h 18 m**, pass 2 **1 m** (it only had 76 profiles to
retry — the idempotent skip working as designed). Tests still **336 passed**.

#### Where the store stands for Task 3

59,620 profiles, 454 still with a NULL position. Per-gap, after ingest:

| gap | selected | ingested | positioned | matchable (≤ 2026-08-01, no matchup) | ≈ ×28 % |
|---|---:|---:|---:|---:|---:|
| A | 2,409 | 2,409 | 2,403 | 2,403 | ~673 |
| B | 5,187 | 5,187 | 5,132 | 1,971 | ~552 |
| D | 475 | 402 | 402 | 402 | ~113 |
| **total** | 8,071 | **7,998** | 7,937 | **4,776** | **~1,338** |


### Task 3 — discover for gaps A + B (2026-09-19): **done — 0 failures, +5,368 granules**

Job `pab-v2-discover` on `:2.0.1`, 04:22:15Z → 05:25:48Z = **63 minutes**.

```
discover done: 13,863 granules from 7,535 searches (0 skipped, 0 failed)
```

| | before | after |
|---|---:|---:|
| granules | 67,435 | **72,803** *(+5,368 after dedupe)* |
| profiles / matchups / fits | 59,620 / 14,610 / 14,609 | unchanged, as expected |

**`--replace` did its job.** 7,535 searches ran and **0 were skipped** — with
the coverage test active and 67,435 granules already in the store, gap A's
2,409 profiles would otherwise have been skipped for the second time and the
job would have reported success having done nothing for a third of its input.

#### The gate: coverage check

```
granules indexed: 72,803
positioned profiles with a summary: 59,166
profiles with >=1 candidate: 55,022 / 59,166 (93.0%)
mean candidates/profile (capped at 10): 6.31
```

**6.31 candidates/profile against the gate's 5.67 CMR truth — passes.**
4,144 positioned profiles still have zero candidates and can never match.

#### One number in that output is misleading, and it matters for Task 4

`coverage_check.py` closes with *"match has up to 55,022 profiles to work
with; at the pilot's 28 % rate that projects to ~15,406 matchups"*. Against
the 14,610 already stored that implies only **~800** new — contradicting the
~1,338 this prompt has been working to.

The whole-store figure is the wrong instrument here: it applies 28 % to all
55,022 profiles that have candidates, including ~40 k that were **already
attempted** in the original run and failed the spatial/temporal gate. Those
will not suddenly match. So I measured the backfill profiles specifically,
using the same `GranuleIndex`/`candidate_granules` machinery `match` itself
uses:

| gap | selected | in store | positioned | no matchup yet | **≥1 candidate** | mean cand. | ≈ ×28 % |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 2,409 | 2,409 | 2,403 | 2,403 | **2,403** | 7.97 | ~673 |
| B | 5,187 | 5,187 | 5,132 | 5,132 | **2,021** | 3.16 | ~566 |
| D | 475 | 402 | 402 | 402 | **398** | 7.53 | ~111 |
| **total** | | | | | | | **~1,350** |

That lands on **~1,350**, confirming the ~1,338 estimate rather than the
~800. Gap B's 2,021-of-5,132 is exactly the PACE-stream limit measured in
Task 1 — the rest are newer than any available granule.

**Task 4 should expect ~1,350 new matchups**, and should read the per-gap
table above rather than `coverage_check.py`'s closing line.

#### Timing, and a correction to my own projection

I said I would take the rate from the job rather than the manifest comment,
and I did — but I took it **too early**. From the first 100 searches I
measured 1.09 s/search and projected **2.3 h**. The job finished in **63 min**
at **0.50 s/search**: the first hundred ran slow while the thread pool warmed,
and steady state was twice as fast. So my projection was 2.2× pessimistic in
the opposite direction to the ingest's. The manifest comment now carries the
measured 0.50 s/search **and** the warning that an early sample over-estimates.

#### The pod was cleaned up; the durable log was the only record

By the time I checked, `kubectl get jobs,pods` returned **no resources** — the
Job and pod had been removed from the namespace. Everything above was
recovered from `/data/v2/discover.log`, which the manifest tees to the PVC for
exactly this reason. Worth keeping in every long-running job: on this cluster
a completed Job's logs are not guaranteed to still be there when you look.


### Task 6 — `build_v2_prompt_6.md` updated (2026-09-22): **done**

Prompt 6 is the go/no-go gate, so the update concentrates on giving it numbers
it would otherwise have to rediscover, and on the traps that cost time here.

**The headline for that prompt: 2.0 has already been fitted on real data.**
Prompt 3 Task 6 ran 60 fits across three configurations with 0 failures, so the
slice is not first contact — it is first contact *in-pod at scale*. Carried
over: the **0.741** median `bbp700` 2.0/1.0 ratio (18 of 20 below unity), the
hybrid/ztt ratio of 0.886, χ² 0.65 vs 0.45, acceptance ~0.33 vs ~0.47, and
`Bp` medians. Prompt 6's Q12 trigger is *"a `b_bp` shift JXP considers
implausible"* — that shift is already measured, so the slice's job is to
confirm it holds across basins, not to discover it.

**Two of its tasks were pointed at questions already answered.** Task 2 asks
how often `Bp` pins to a prior edge: the workstation answer is *the lower*
edge, on 3 of 20. Task 2 also asks for residuals at 713/719 nm — but 719 is
now **outside** the fit window after Q2 moved `wave_max` to 700, so I flagged
that it is a diagnostic, not a fit residual, and recorded why the band was
dropped (negative on 6 of 20, noise-dominated on 2 more).

**Cost, with the pause trigger it bears on.** In-pod ~226 s/fit sits *just
under* Q12's 240 s pause trigger — and it is a single fit including JAX's
first compile. Flagged as an upper bound that one measurement cannot settle.

**Both rate lessons from this prompt, stated as a rule rather than numbers.**
Ingest was 5× slower than its pilot figure (remote bottleneck, not local);
discover was 2× faster than my own early projection (I sampled while the
thread pool warmed). The rule that went in: *take a rate from a few hundred
units in, never the first fifty, and never from a stale comment.*

**The traps, each with the command that catches it:**

- **Diff the image's baked SHA against the commit carrying your change**
  before launching — with the one-liner. This is Q7's lesson and the most
  expensive mistake of this prompt.
- Image `:2.0.1` or later, **never `:2.0.0`**; check whether `:2.0.2` exists.
- `PYTHONWARNINGS=ignore` on every 2.0 job.
- **Tee to the PVC** — Task 3's Job and pod were deleted before its results
  were read, and the tee'd log was the only record.
- `v1/pab.db` needs `create=False` (frozen at schema v4 against a current
  `SCHEMA_VERSION` of 5).
- Chains key off the **root** of `PAB_DATA_DIR`, not `--db`.

**On Task 1's "pick the least code" slicing mechanism**, I noted the precedent
this prompt set — Q5 added an explicit selection to `match` mirroring
`discover`'s — while being clear it is *not* a direct reuse, because `fit`
selects by matchup rather than profile. The closest existing pattern is
`pab.fit.nasa_giop`'s repeatable `--matchup ID`. Also flagged that `fit` still
does not honour `--profiles-csv`, and that `HOWTO.md`'s row listing which
stages take a selection **has now been wrong twice** — so whoever adds
targeting should fix it there too.

Also added a Task 4 (update `build_v2_prompt_7.md`), flagged as removable.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-17 (Prompt 5 Task 1 — backfill selections, and a halved yield estimate)

Built and staged the five backfill CSVs. The counts match Plan §4 closely; the
expected *yield* does not, and two measurements explain why.

What I learned / want to remember:

- **Ask what fraction of a selection can actually succeed, not just how big it
  is.** Gap B is 5,187 profiles — slightly *more* than planned, which looks
  like good news. But PACE's forward stream ends 2026-08-01, so 63 % of them
  have no satellite data to match against. The Context told me to check CMR
  for exactly this; it would have been easy to report "B = 5,187, on target"
  and let the shortfall surface later as an unexplained miss.
- **A blank column can be a diagnosis, not just missing data.** Gap D is 78 %
  position-less, and rather than assume that was harmless (ingest fetches
  position from argopy, after all) I checked the historical rows: of 807
  blank-position rows in the original selection, 435 ingested and only 13.5 %
  of a sample recovered a position. So the blank predicts the failure it looks
  like it should be independent of. D's realistic yield is ~29 matchups, not
  the planned ~130.
- **Re-deriving the estimate was the point of the task, not a by-product.**
  Plan §4's ~2,200 was sized read-only on 2026-09-13 from counts alone. With
  matchability and position folded in it is ~1,246. Both are honest; the
  difference is entirely in what the estimate conditions on. I raised amending
  the plan as Q1(c), because a later reader comparing 1,246 actual against
  2,200 planned would reasonably read it as something having gone wrong.
- Staged via `kubectl cp` and verified with md5 on both ends rather than
  trusting the copy — the same discipline as the database staging, and it cost
  one extra command for five files.
- The live `bgc-s` index loads in 5 s for 408 k rows, which makes re-querying
  the selection at run time (R5) genuinely cheap — worth knowing before anyone
  plans around a stale CSV.

### 2026-09-17 (Prompt 5 Task 1 follow-up — Q1 answered; Plan §4 amended)

Task 1's artifacts verified intact (five CSVs local **and** on the PVC, byte
sizes matching), then JXP's three Q1 answers actioned.

- **(a)/(b)** — ingest all of B and all of D. Recorded in Task 2, together
  with the new deliverable JXP asked for: a list of the profiles that fail
  ingest *twice*, for him to chase with colleagues. I specified a `reason`
  column that separates "argopy returned nothing" from "returned a profile
  with no usable `BBP700`/`CHLA`" — those are different conversations to have
  with a DAC, and lumping them would waste his time.
- **(c)** — `run_full_inelastic.md` Plan §4 amended: the gap table now carries
  measured counts alongside the original sizing, plus **with-position** and
  **matchable-now** columns and the revised **~1,250 matchups / ~15.9 k
  fits**. Both causes and both decisions are recorded inline.

What I learned / want to remember:

- **Amending the plan was worth more than noting the discrepancy in a
  report.** Plan §4 is what a later reader consults; leaving "~2,200" there
  and the correction three documents away guarantees the shortfall gets
  rediscovered as a problem. The amendment keeps the *original* sizing visible
  next to the measured one, so the difference reads as "the estimate got
  better conditioned", not "someone quietly changed the target".
- **The new columns are the actual content.** The gap table originally had one
  quantity — profile count — and that is precisely the number that did not
  predict the outcome. Adding "with position" and "matchable now" is what
  makes the revised yield derivable by the reader rather than asserted.

### 2026-09-18 (Prompt 5 Task 2 — backfill ingest: 5,589 profiles, and two corrected assumptions)

`pab-v2-ingest` ran 16 h 18 m and added **5,589 of 5,662** profiles (98.7 %),
with `mld_summary` tracking `profiles` exactly. 73 genuine failures written to
`ingest_failures.csv` for JXP. Plan §4 corrected; the stale ingest-rate
figures annotated in two places.

What I learned / want to remember:

- **I got gap D wrong, and the error is instructive.** I predicted D's 372
  position-less profiles would dominate the failure list, citing a measured
  13.5 % position-recovery rate. 99 % recovered. My evidence was a sample of
  rows ingested during the *original* run — profiles that had already failed
  in some way — so it measured the wrong population entirely. A blank field in
  a **stale** CSV says almost nothing about what a **fresh** fetch returns.
  Worse, I had written that 13.5 % into Plan §4 as justification for cutting
  D's yield from ~130 to ~29; it is now corrected in place, with the reasoning
  error stated, because a bare number swap would leave the next reader unable
  to judge which figure to trust.
- **The two-pass design earned its keep, in the small way it was meant to.**
  Pass 2 took 1 minute, retried exactly the 76 that pass 1 missed, and
  recovered 3. Without it, 76 would have gone onto JXP's chase list and 3 of
  them would have been wild goose chases. The value was not speed — it was
  making "transient" and "real" separable.
- **A flat rate is itself a diagnosis.** 11.0 s/profile varying by less than
  10 % across 5,662 fetches is not what a loaded or variable server looks
  like; it is what a rate limiter looks like. Combined with 24 millicores on a
  34-core request, that was enough to conclude the bottleneck had moved from
  local (GIL) to remote — the opposite of what the code's own docstring
  records from the pilot, and the reason 32 processes bought nothing.
- **Annotating the stale numbers mattered more than reporting them.** 2.1
  s/profile is written into a docstring that explains *why* processes were
  chosen over threads, and into a manifest's sizing comment. Both would have
  been reused. I left the original measurements intact and added what changed
  and how it was measured, rather than overwriting — the pilot's numbers were
  not wrong, they just stopped generalising.
- Checking `top pod` and the in-pod process list before drawing conclusions is
  now a habit worth keeping: "Running" told me nothing, 36 processes at 1.5 %
  CPU told me everything.

### 2026-09-20 (Prompt 5 Task 3 — discover: 0 failures, +5,368 granules, and two numbers worth distrusting)

`pab-v2-discover` ran 63 minutes, 7,535 searches, **0 failed**, granules
67,435 → 72,803. Coverage gate passes at 6.31 candidates/profile against the
5.67 CMR truth.

What I learned / want to remember:

- **I measured the rate too early and got it wrong in the other direction.**
  After the ingest came in 5× slower than its pilot figure, I promised to take
  discover's rate from the job rather than the comment. I did — from the first
  100 searches, which ran at 1.09 s/search while the thread pool warmed, and
  projected 2.3 h. Steady state was 0.50 s/search and it finished in 63 min.
  Being burned by an optimistic estimate made me trust a pessimistic early
  sample. The fix that went into the manifest is not a number but a method:
  take the rate a few hundred searches in, not from the first fifty.
- **`coverage_check.py`'s closing projection is the wrong instrument for a
  backfill.** It applies 28 % to every profile that has candidates — including
  ~40 k already attempted and rejected in the original run — so it implied
  ~800 new matchups against the ~1,338 this prompt expects. Rather than pick
  the number I preferred, I re-ran the *same* `GranuleIndex`/
  `candidate_granules` machinery restricted to the backfill profiles and got
  ~1,350. The script is not wrong; it answers "what is the store's ceiling",
  and I needed "what will match actually attempt". Worth writing into the Task
  4 expectations so nobody reconciles the two under time pressure.
- **Gap B's 2,021-of-5,132 with candidates is the PACE stream limit showing up
  independently.** Task 1 predicted 1,971 matchable from the stream-end date
  alone; the candidate count from the granule index says 2,021. Two unrelated
  routes to the same number is the best evidence either of them is right.
- **The Job and pod were gone when I looked**, and every number in this report
  came from `/data/v2/discover.log`. Teeing to the PVC was a habit copied from
  the 1.0 manifests; this is the run where it paid. Keep it in every job.
- `--replace` was load-bearing exactly as predicted: 7,535 searches, **0
  skipped**. Without it, gap A would have been silently skipped a second time
  and the job would still have exited 0.

### 2026-09-22 (Prompt 5 Task 6 — prompt 6 updated; and I launched match against a stale image)

Updated `build_v2_prompt_6.md` with the measured numbers and the traps. Before
that, acted on Q6 and launched `pab-v2-match` — which went wrong.

**The error.** The job reported `match: 40414 profiles over 16 processes`
instead of 7,998. I killed it after five minutes; **0 matchups were written
and the database is unchanged**. The cause was not the manifest, which was
correct: `:2.0.1` was built on 2026-09-17 from PAB `8c7ab8a`, and the
`match`-selection change is from 2026-09-21 and still uncommitted. I confirmed
it rather than inferred it — `build_matchups accepts selection: False` inside
the image.

What makes this worth writing down is that **the evidence was already in the
log I was reading**. The job prints its baked provenance as its first act,
precisely so a stale image is visible; it said `{"PAB":"8c7ab8a", …}` and I
read past it. I had also, four days earlier, deliberately checked the tree was
clean before building `:2.0.1` *because* an image whose SHA names a commit it
does not contain is a lie — and then failed to make the converse check, that
the commit I needed was in the image.

The rule now in Prompt 6's agreements is the one-command version:
`docker inspect --format '{{index .Config.Labels "…image.revision"}}'` against
`git log`, before any launch that depends on a recent change.

Other things worth remembering:

- **I will not build the image from uncommitted code to unblock myself.** The
  build rsyncs the working tree, so it would work — and the baked SHA would
  then name a commit without the change, which is exactly the failure mode I
  just spent a day being bitten by. The change needs a commit from JXP first;
  that is Q7.
- **Writing the update while the facts are fresh is worth more than writing it
  neatly.** Prompt 6 asks how often `Bp` pins to a prior edge and for
  residuals at 719 nm — one is already answered and the other is now outside
  the fit window. Neither would have been obvious to a reader starting from
  the prompt alone, and both would have produced confident, wrong work.
- The most useful thing I put in that doc is not a number but a rule about
  numbers: take a rate from a few hundred units in. This prompt got burned in
  both directions — 5× pessimistic on ingest, 2× optimistic on discover — and
  a rule generalises where either figure would mislead.
