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
7. Execute the 7th task in Tasks below
8. Execute the 8th task in Tasks below
9. Execute the 9th task in Tasks below


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

7. **Q7.** I have answered your Q7 below.  React to that before moving on to the rest of this task.
   Contniue on as far as you can after.  Use Opus 5.  Log your work.

8. **Q8-Q10.** I have answered your Q8-Q10 below.  Read those and continue accordingly.
   Use Opus 5.  Log your work.

9. **Q11-Q12.** I have answered your Q11-Q12 below.  Read those and continue accordingly.
   Use Opus 5.  Log your work.

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

>A. Yes, please do

*What I will do differently:* before launching any job that depends on a code
change, diff the image's baked `PAB` SHA against the commit that carries the
change — a one-command check that would have caught this before 16 cores were
scheduled.

>A. Let's adopt your recommendation.  


### Q8 (Tasks 4/7, 2026-09-25) — two small defects found while relaunching match; both are yours to schedule, neither blocks anything

Both were found in passing, neither is urgent, and I have deliberately **not**
fixed either: one is a Dockerfile change and the other touches `match` while
`match` is running. Flagging rather than acting.

#### (a) The image re-pushes 2.5 GB for a 175 MB source change

`COPY PAB/ PAB/` sits **before** the `RUN pip install` layer, and that layer is
**7.74 GB**. So any change to PAB source invalidates the whole thing: both
`:2.0.1` and `:2.0.2` were multi-GB pushes for what were small code changes.
It compounds with a second fact — the registry does **not** resume a partial
layer, so when the `:2.0.2` push stalled at 1.97 GB, all of it was re-sent.

Splitting the `RUN` into two — third-party dependencies (cached, changes
almost never) then `pip install --no-deps` for the five local packages — would
take every future rebuild-and-push from ~2.5 GB to ~50 MB, and shrink the
stall window proportionately. Prompt 6 expects at least one more image, and
Prompts 7–9 likely more.

**Question:** want me to make that change before the next image, or leave the
Dockerfile alone until the v2 run is finished? *My recommendation: do it
before the next image* — it is a layer-ordering change with no effect on the
image's contents, the build guards would catch any error immediately, and it
pays for itself on the first rebuild. But it does mean a full rebuild to
establish the new cache, so it is not free the first time.

>A. Yes, make that change for the next image.

#### (b) A NASA 503 is being reported as a pickling bug

`match` logged this, which reads like a serialization defect in our code:

```
TypeError: can't pickle multidict._multidict.CIMultiDictProxy objects
```

It is not. The real error is two frames up:

```
aiohttp ClientResponseError: 503, Service Unavailable
  PACE_OCI.20260615T002303.L2.OC_AOP.V3_2.nc   (cloudfront / OB.DAAC)
```

NASA returned a 503; the `aiohttp` exception carries the HTTP headers as a
`CIMultiDictProxy`, which cannot be pickled, so `ProcessPoolExecutor` fails to
ship the exception from worker to parent and what surfaces is the pickling
`TypeError`. The transient is correctly handled either way — `_drain` catches
broadly (`pab/matchup/engine.py:819-823`), the profile is marked unmatched,
the pool continues, and the observed rate is 1 in 100 — so this is a
**diagnosability** bug, not a correctness one.

It matters because it is exactly the kind of message that sends the next
person debugging our pickling instead of reading NASA's status page. The fix
is small and local: in the worker, catch the granule-open exception and
re-raise a plain `RuntimeError(f"{type(e).__name__}: {e}")`, so the string
crosses the process boundary instead of the object. The same pattern would
help `geometry`, which opens L1B granules through the same stack.

**Question:** fold that into the geometry work, or leave it? *My
recommendation: fold it in* — `geometry` is about to make ~13.5 k L1B opens
against the same infrastructure that just returned a 503, and if a fraction of
those fail I would much rather the log said so plainly. It is a few lines plus
a test that a worker-side unpicklable exception arrives as a readable string.

>A. Yes, fold it into the geometry work.


### Q9 (Task 4, 2026-09-25) — match is **degrading**: 13.6–18.6 h, not 6 h, and the cause is granule-open stalls. Let it run?

`pab-v2-match` on `:2.0.2` is **correct** — the Q7 gate passed
(`selection restricts to 7998`), real failures are **1 in 200** — but the rate
is getting worse, not settling.

| window | secs | s/profile | written | apparent yield |
|---|---:|---:|---:|---:|
| 0–50 | 339 | **6.8** | 18 | 36 % |
| 50–100 | 383 | **7.7** | 11 | 22 % |
| 100–150 | 614 | **12.3** | 10 | 20 % |
| 150–200 | 695 | **13.9** | 4 | 8 % |

cumulative **10.2 s/profile** → **13.6 h**; marginal **13.9 s/profile** →
**18.6 h**. Against Q6's ~6 h estimate.

**This is the opposite of the discover lesson, and worth saying so.** There I
sampled too early and over-projected by 2.2× because the pool was warming.
Here the early sample was the *optimistic* one — "take the rate from a few
hundred in" gives a **worse** number, not a better one. The rule is not "later
samples are kinder"; it is "the first fifty are never the rate".

**Cause, from the log rather than inferred.** The stall guard has fired twice:

```
15:20:43 match stalled after 120s with 18 profiles in flight; killing the pool
15:34:02 match stalled after 120s with  1 profiles in flight; killing the pool
```

Each firing costs 120 s of dead time plus a pool teardown and rebuild. That
alone accounts for much of the slowdown. It also explains the apparent yield
collapse: **profiles killed in flight are recorded as `unmatched`**, so the
18 lost at 15:20 land in the 100–200 windows and deflate the ratio. They are
not lost — they stay unmatched and are retried on any later run. The true
yield is still near the expected ~28 %; the 8 % is an artifact.

**Why the stalls.** The workers are network-bound (16 processes, ~1 core total
CPU, 18 GB), the one hard failure was a NASA **503** from OB.DAAC/cloudfront,
and a stall is what a hung 1.8 GB granule open looks like. So the most likely
story is NASA-side degradation under sustained load — the same shape as the
ingest, where the bottleneck turned out to be remote rate-limiting rather than
anything local (Q3).

**Options:**

1. **Let it run.** 14–19 h, fully resumable, stalls handled, real failures at
   0.5 %. Then a second sweep run to pick up the stall-killed profiles — which
   for `match` is just running it again, since matched profiles are skipped
   before any granule is opened.
2. **Kill and restart with fewer workers** (8 rather than 16). If NASA is
   throttling a 16-connection burst this could *raise* throughput; if the
   degradation is server-side load it changes nothing. Costs the ~200 done
   (they are written, so actually costs nothing but the restart).
3. **Kill and retry later**, when OB.DAAC is healthier. No way to know when
   that is, and gap-filling is not urgent.

*My recommendation: option 1, let it run* — the same reasoning you accepted
for the ingest in Q3, and it applies more strongly here: output is correct,
the failure rate is 0.5 %, the job is resumable, and options 2 and 3 are
experiments with speculative payoff against a certain one. 14–19 h is
tolerable for a one-off backfill, and Task 5 (geometry) cannot start until
match finishes regardless, since it needs the new `matchup_pixels` rows.

**One thing I will do either way:** run the sweep afterwards and report how
many stall-killed profiles it recovers, so the stall cost is measured rather
than assumed.

**Question:** let it run, or drop to 8 workers?

>A. Yes, let it run.


### Q10 (Tasks 4/5, 2026-09-26) — match is done; confirm the **sweep** and the **geometry** launch

`pab-v2-match` finished at 04:36 UTC: **+1,277 matchups, 14,610 → 15,887**,
8 failures (0.17 %), **350 profiles stalled**. Full numbers in the Task 4
report. Two launches are ready and both wait on you, per Q2/Q4/Q6 practice.

#### (a) The sweep — recover the 350 stalled profiles

| | |
|---|---|
| manifest | `nautilus/v2_match_job.yaml` **unchanged** (`:2.0.2`) |
| mechanism | a bare re-run; matched profiles are skipped **before any granule is opened**, so it attempts only what is still unmatched |
| attempts | ~350 stalled + the ~3,195 genuinely unmatched it will re-check cheaply |
| est. wall | **~1–2 h** (350 × 10.8 s ≈ 1 h, plus the cheap re-scan) |
| expect | **~100 matchups → ~15,987**, which lands on Q1's revised ~15.9 k |

*My recommendation: yes.* This is exactly the "pass 2" pattern you approved for
the ingest in Q2 (`>A. 1. yes; 2. let pass 2 run`), and the stalls are
transient NASA-side timeouts, so a retry at a different hour is the single
highest-yield thing available. I will **measure** the recovery rather than
report my ~100 estimate as fact — that was the commitment in Q9.

One caveat worth stating: if OB.DAAC is still degraded, the sweep will stall on
the same granules and recover little. That is still worth knowing, and it costs
~1 h.

#### (b) Task 5 — geometry

`nautilus/v2_geometry_job.yaml` is written and pre-flighted (all 3 inline
`python -c` snippets parse; all 8 gate SQL statements run against a real v5
schema).

| | |
|---|---|
| image | `:2.0.2` |
| flags | `--stage geometry --jobs 8` over the whole v2 DB |
| **`--jobs 8`, not 16** | one **uncached CMR query per granule** on top of the L1B read; 16 would mean 16 concurrent CMR searches against the infrastructure the working agreements cap at `--discover-jobs 8` |
| resources | 8 CPU / 64 Gi |
| gates (automatic) | every pixel has `theta_s`; `geom_source = 'L1B_V3'`; `theta_v` 0–~60°; `dphi` inside (−180, 180] |

**On "measure a ~200-granule slice first": I propose not building one.**
`build_geometry` is idempotent on `theta_s IS NULL` and does **zero** network
work for filled pixels, so the real job *is* the measurement — it logs
`geometry progress: N/M granules` every 50, and killing it after a few hundred
costs nothing because resuming is just re-running it. That is strictly less
code than adding a `--limit`, and it measures real in-pod conditions rather
than a proxy. I will take the rate from ~200–400 granules in, not the first
fifty — and per the match run, I will not read a trend off four windows.

**Ordering:** sweep first, then geometry. Geometry is per-pixel, so running it
before the sweep would leave the sweep's new pixels without geometry and
require a second geometry pass. Sequential also keeps the single-writer
discipline.

#### (c) The finished job is **hung at exit** and is holding 16 CPU / 100 Gi

Discovered while waiting for the `V2_MATCH_DONE` marker that never came. The
match work is **complete and committed** — 15,887 matchups verified by a
read-only query, full summary written to `/data/v2/match.log` at 04:36 — but
the process will not exit:

```
pid 26  pab   State: S (sleeping)   Threads: 35   wchan: futex_wait_queue   0% CPU
match.log last written 04:36:00
```

**Cause, from the job's own log:**

```
04:30:42 ERROR killed match pool did not shut down within 30s; abandoning it
                (its pipes are reclaimed when it is garbage-collected)
```

That comment is optimistic. An abandoned `ProcessPoolExecutor` leaves its
queue-management thread running, and `concurrent.futures`' `_python_exit`
atexit handler blocks joining it — forever. 35 live threads is consistent with
several abandoned pools.

**Why it matters beyond this run:** everything after the `pab` invocation in
the manifest — `MATCH end`, the final `counts()`, `du -sh`, and the
`V2_MATCH_DONE` marker — never executes. A later reader grepping the PVC log
for `V2_MATCH_DONE` would conclude the job failed, when it succeeded. That
defeats the "tee every job's output to the PVC" agreement precisely at the
point it is supposed to pay off. `geometry` uses the same abandon-the-pool
pattern, so it can hang the same way.

Two fixes, neither done:

1. **Operationally:** add `activeDeadlineSeconds` to these manifests, or move
   the `DONE` marker and final counts to run regardless (the `pab` call is
   already piped through `tee`, so `set -o pipefail` plus a trap would do it).
2. **In code:** after abandoning a pool, `os._exit()` once the summary is
   written, or avoid the atexit join.

**Immediate consequence:** the job must be deleted before the sweep, since it
holds the `pab-v2-match` name — and it is currently reserving **16 CPU and
100 Gi** of a shared cluster while doing nothing. `kubectl delete job
pab-v2-match` is safe: the database writes are committed and verified.

*My recommendation: delete it as part of launching the sweep.* Flagging rather
than doing it, since it is outward-facing.


**Question:** launch (a) now, then (b) when it finishes? Or geometry only —
the sweep's ~100 matchups are not worth an hour to you?

*My recommendation: both, in that order.*

>A. Yes, both in that order


### Q11 (Task 8, 2026-09-26) — Q8(a) and Q8(b) are implemented and tested; geometry needs a **commit** before I can build `:2.0.3`

Both Q8 answers are done in the working tree, suite green at **346 passed, 1
skipped** (the 340 baseline plus exactly the 6 new tests). But the same wall as
Q7 is now in front of geometry, for the same reason, so I am stopping at it
rather than walking through it.

**Why a commit is needed.** `geometry` should carry the Q8(b) fix — that is
what "fold it into the geometry work" means — so it needs a new image. The
build rsyncs the *working tree*, so I could build `:2.0.3` right now, but
`PAB_GIT_SHAS` would bake `dacefa1`, a commit that does **not** contain any of
this. That is precisely the provenance lie I refused to introduce in Q7 and
that made `:2.0.1` run the wrong code for four days. Building it would also
defeat the SHA-diff check you approved, since the check would pass while being
meaningless.

**Files carrying the changes:**

- `pab/parallel.py` — new `WorkerError` + `portable_errors()` context manager
- `pab/matchup/geometry.py` — guards the L1B open in `geometry_for_granule`
- `pab/matchup/engine.py` — guards the granule open *and* the extract in
  `find_matchup` (the extract is where the lazy HTTP reads actually happen, so
  a 503 can surface there rather than at open)
- `pab/tests/test_portable_errors.py` — **6 new tests**
- `Dockerfile` — the Q8(a) layer split
- `nautilus/v2_geometry_job.yaml`, `nautilus/v2_match_sweep_job.yaml` — new
- `nautilus/v2_match_job.yaml` — `:2.0.2` tag + digest

#### What Q8(b) actually fixes, demonstrated

Same exception raised through a real `ProcessPoolExecutor`, with and without
the guard:

```
WITHOUT   -> TypeError: can't pickle Unpicklable objects
             cause visible (mentions 503)? False
WITH      -> WorkerError: granule G1: Unpicklable: 503, message='Service Unavailable'
             cause visible (mentions 503)? True
```

Picklable exceptions are re-raised **unchanged**, so `find_matchup`'s existing
`except TimeoutError` handler still fires and no caller that branches on a type
is affected. Only exceptions that would be destroyed in transit are flattened.
One of the six tests asserts the stand-in really is unpicklable, so the others
cannot silently stop testing anything.

#### On Q8(a): I did **not** use `--no-deps`

Q8(a) proposed "install third-party deps, then `pip install --no-deps` the
local packages". I implemented the first half and **deliberately not** the
second: `bing/setup.py` declares ~25 real dependencies, and `--no-deps` would
silently drop any that the explicit third-party list happens to miss — a
failure that would not appear until some import at run time in a pod. Instead
layer 2 installs the local packages *with* deps; everything heavy is already
satisfied by layer 1, so the layer stays small, and anything I failed to list
is installed rather than dropped. Same saving, no silent-drop failure mode.

A validation build of the restructured Dockerfile is running under a throwaway
tag (no push, `:latest` deliberately not moved) so the layer split is proven
before it matters.

**Question:** commit those files so I can build and push `:2.0.3` and launch
geometry?

*My recommendation: yes* — geometry is the last thing standing between the
store and the fit stage, and it is the run most likely to hit the 503s that
Q8(b) makes legible: ~13.5 k L1B opens against the same infrastructure.

**If you would rather not wait**, the alternative is to run geometry on
`:2.0.2` as-is. It would work — Q8(b) is a diagnosability fix, not a
correctness one — but a granule failure would be reported as a pickling error,
which is the exact trap you just asked me to remove.

>A. yes, commit those files


### Q12 (Task 8, 2026-09-26) — **~5.3 GB of the image is torch + CUDA, pulled in by a dependency nothing imports.** Strip it?

Found while measuring whether Q8(a) actually delivered. It did not, at first,
and chasing why turned up something larger.

**What the image is made of** (`du -sm` in site-packages):

| | MB |
|---|---:|
| `nvidia/` (CUDA wheels) | **3,196** |
| `torch/` | **1,177** |
| `triton/` | **897** |
| jaxlib | 353 |
| everything else | ~1,600 |

**~5.3 GB — over half the image — is torch and its CUDA stack.** These pods
have **no GPU**.

**Where it comes from:** `bing/setup.py:31` declares `timm==0.3.2`. `timm`
requires `torch`, and the default torch wheel bundles the NVIDIA CUDA
libraries. Nothing imports it:

```
grep -rn "import timm|import torch" bing/bing/      -> nothing
grep -rn "import torch" pab/                        -> nothing
```

PAB uses only `bing.fitting`, `bing.models`, `bing.priors`, `bing.rt`,
`bing.parameters`, `bing.evaluate`. (`remote_sensing` does import torch, but
only in `process/swot_ssh_utils.py` — SWOT sea-surface-height work that this
pipeline never touches.)

**What I did do (inside Q8a's approval):** named `timm==0.3.2` in layer 1, so
the 5.3 GB sits *below* the source COPYs and is cached. Without it the layer
split bought almost nothing — measured, layer 2 was **6.35 GB**, of which 5.27
GB was this closure. That was my error in Q8a: I assumed my hand-written
third-party list was close to the real closure, and it was missing the single
biggest item. I should have measured the layer sizes before claiming the
saving, and I have corrected the claim rather than let it stand.

**What I did NOT do**, because it changes what is in the image and you have not
asked for it — three options, increasing in aggressiveness:

1. **Strip `timm` from the STAGED `bing/setup.py`**, exactly as
   `build_image.sh` already strips the stale `retrieve-or-bust @ git+...@cdom-rt`
   pin from the staged copy only. Live `bing/setup.py` untouched. Removes
   ~5.3 GB. Risk: if anything in `bing` ever starts importing `timm`, the
   image breaks — but the build guards import `bing.models.anw`,
   `bing.models.bbnw` and run a real fit, so a break would surface at build
   time, not in a pod.
2. **Install the CPU-only torch wheel**
   (`--index-url https://download.pytorch.org/whl/cpu`). Keeps `timm` working,
   drops `nvidia/` and `triton/` — about **4.1 GB**. Lower risk than (1), and
   correct for a CPU-only cluster regardless.
3. **Leave it.** The layer split already means it is pushed once and cached
   thereafter.

*My recommendation: (2), and (1) only if you are confident `timm` is dead
weight in `bing`.* Option 2 is almost pure win — a GPU torch build on a
GPU-less cluster is never the right artifact — and it does not depend on a
judgement about someone else's package. Option 1 saves slightly more but bets
on `bing` never importing `timm`; that is your call, not mine, since `bing` is
not this repo's code.

Either way the pipeline behaviour is unchanged: nothing in the fit path
touches torch.

#### Measured result of the layer split (2026-09-26)

Two validation builds under throwaway tags, no push, `:latest` not moved.

| layer | before | after |
|---|---:|---:|
| cached (below the source COPYs) | 1.39 GB | **7.03 GB** |
| **rebuilt on a PAB source edit** | **~7.96 GB** | **~934 MB** |

An **8.5x** reduction in what a source change re-pushes. All five build guards
pass on the restructured image (`ED OK`, `ROBUST OK ... std 0.0245`,
`PAB 2.0 OK robust_hybrid 400.0 700.0`, `PROVENANCE OK`, `STAGES OK`).

**This is not the "~50 MB" I quoted in Q8(a)** and I am not going to let that
number stand. The residual ~934 MB is `COPY PAB/` (175 MB) plus the layer-2
`pip install` of the five local packages (712 MB). 50 MB was a guess about the
size of a layer I had never measured; 934 MB is what it actually is. Q12 is
what would shrink it further.


**Question:** (1), (2), or (3)?

>A. (2)

#### Measured result of (2) — CPU-only torch (2026-09-26)

Validation build, throwaway tag, no push.

| | `:2.0.2` | CPU-only |
|---|---:|---:|
| `nvidia/` | 3,196 MB | **gone** |
| `triton/` | 897 MB | **gone** |
| `torch/` | 1,177 MB | **769 MB** (`2.14.0+cpu`) |
| **image** | **9.19 GB** | **4.43 GB** |

**−4.76 GB, a 52 % smaller image.** All five build guards pass
(`ED OK`, `ROBUST OK … std 0.0245`, `PAB 2.0 OK robust_hybrid 400.0 700.0`,
`PROVENANCE OK`, `STAGES OK`).

**An unexpected confirmation:** `import timm` fails in the new image with
`ModuleNotFoundError: No module named 'torch._six'` — and it fails **exactly
the same way in `:2.0.2`**, which has `torch 2.14.0+cu130`. `timm==0.3.2` is
from 2021 and uses `torch._six`, removed in modern torch. So `timm` has been
broken in every image we have ever shipped, and nobody noticed **because
nothing imports it**. That is independent evidence for the Q12 premise: it is
dead weight, not a dependency. It also means option (1) — stripping `timm`
from the staged `bing/setup.py` — carries even less risk than I credited it
with, if you ever want the last ~770 MB back.


### Q13 (Task 9, 2026-09-26) — Q11 answered "yes, commit those files", but the tree is still uncommitted. Who runs the commit?

Q12 is done (see below). Q11 is blocked on one ambiguity I do not want to
resolve by guessing.

**State right now:**

```
HEAD: dacefa1   (unchanged since Prompt 5 Task 7)
 M Dockerfile
 M claude_prompts/v2/build_v2_prompt_5.md
 M nautilus/v2_match_job.yaml
 M pab/matchup/engine.py
 M pab/matchup/geometry.py
 M pab/parallel.py
?? nautilus/v2_geometry_job.yaml
?? nautilus/v2_match_sweep_job.yaml
?? pab/tests/test_portable_errors.py
```

**Why I have not just committed.** `CLAUDE.md` states, as a working agreement:

> **Git is handled by the user.** Do not run `git add`, `git commit`,
> `git push`, branch, merge, or any other state-changing git command. The user
> performs all git operations themselves.

I asked Q11 as a request *to you* ("commit those files so I can build and
push"), and your `>A. yes, commit those files` answers that request. In **Q7**
the identical exchange — *"commit those four files…?"* / *">A. Yes, please
do"* — ended with you making the commit, and `dacefa1` appearing. So the
precedent and the written rule both point the same way.

But the phrasing could also be read as instructing me to do it, and you then
told me to continue, so I am asking rather than picking. A one-line "yes"
answering my own request is not, to me, clear enough to override a rule you
wrote down deliberately — and if I am wrong the cost is one message, whereas
committing wrongly breaks an agreement.

**Option A — you commit** (what I expect). Paste-ready:

```
git add Dockerfile pab/parallel.py pab/matchup/engine.py pab/matchup/geometry.py \
        pab/tests/test_portable_errors.py nautilus/v2_geometry_job.yaml \
        nautilus/v2_match_sweep_job.yaml nautilus/v2_match_job.yaml \
        claude_prompts/v2/build_v2_prompt_5.md
git commit -m "v2: portable worker errors, CPU-only torch, Dockerfile layer split

Flatten unpicklable worker exceptions (a NASA 503 was surfacing as a
CIMultiDictProxy pickling TypeError); split the image into a cached
dependency layer and a small source layer; install CPU-only torch.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

(Drop the trailing line if you would rather not carry it.)

**Option B — tell me to run it**, i.e. an explicit exception to the CLAUDE.md
rule for this commit. Say so and I will.

**Either way, what happens next is unchanged:** build `:2.0.3`, verify the
baked SHA matches the new HEAD *and* that `portable_errors` is actually in the
image (the two-sided check from Q7), push, then launch geometry over
**159,760 pixels, none of which have `theta_s`**.

>A. you run it

Option B taken: an explicit exception to the `CLAUDE.md` git rule, for this
commit. Noted here so the exception is on the record and does not become a
precedent by silence — the standing agreement is unchanged and I will keep
asking.


### Q14 (Task 9, 2026-09-27) — does `ARG PAB_GIT_SHAS` invalidate the cached dependency layer on every commit? (my "8.5×" is unproven)

I told you in Q8(a) that the layer split takes a source edit from ~7.96 GB
rebuilt to ~934 MB — an 8.5× reduction. **That number came from builds that all
shared the same `PAB_GIT_SHAS` value**, and I now doubt it holds for real
builds, where every commit changes that value.

**The mechanism.** `ARG PAB_GIT_SHAS` is declared at `Dockerfile:10`, above
both layer-1 installs (lines 46 and 54). Docker includes an in-scope build
arg's value in the command string of every subsequent `RUN` — visible in
`docker history` as `RUN |1 PAB_GIT_SHAS={"PAB":"dacefa1",...}`. A new commit
therefore changes the cache key of the dependency layer, not just the source
layer.

**What the `:2.0.3` push actually showed:**

```
2.0.2 layers 18, 4,254 MB compressed
2.0.3 layers 20, 1,430 MB compressed
  shared with 2.0.2 :  7   412 MB   (not transferred)
  NEWLY PUSHED      : 13 1,018 MB
  newly pushed sizes (MB): [0,0,2,3,5,13,13,14,15,53,228,275,396]
```

The 396/275/228 MB layers are the dependency layers, so they **were** re-sent.
But that build also changed the Dockerfile substantially (the Q12 CPU-torch
split), so this run **cannot distinguish** "the ARG invalidated the cache" from
"the edit invalidated it". Asserting the former from this evidence would be the
same mistake I have now made three times in this run.

**The clean test**, which I have not run because it costs two builds (~25 min)
and the machine is busy serving geometry:

1. `docker build` the current tree with `--build-arg PAB_GIT_SHAS=<A>` — warm.
2. Rebuild, **identical tree**, with `--build-arg PAB_GIT_SHAS=<B>`.
3. If layer 1 re-runs (and its digest changes), the ARG is the cause. If it is
   `CACHED`, my worry is unfounded and the 8.5× stands.

**The fix, if confirmed**, is a two-line move: put `ARG PAB_GIT_SHAS` / `ENV` /
`LABEL` *after* the layer-1 installs and before the source COPYs. `ENV`
persists into the final image wherever it is declared, so provenance is
unaffected — `pab.config.git_shas()` still reads it, and the build guards would
catch any mistake immediately.

**Question:** want me to run the two-build test and make the move, or leave the
Dockerfile alone now that the image is 1.4 GB compressed and pushes in 6
minutes?

*My recommendation: run the test, and move it only if it confirms.* At 1.4 GB
the pain is much reduced, so this is no longer urgent — but the figure I gave
you in Q8(a) should either be substantiated or withdrawn, and a two-line change
is cheap if it is real.

>A.  Leave it


### Q15 (Task 9, 2026-09-27) — `geometry`'s worker pool is **unbounded** and OOMs; fix written and tested, needs a commit

Found while watching the geometry run. `build_geometry` constructs its
`ProcessPoolExecutor` **without** `max_tasks_per_child`, which `match` sets
precisely to bound per-worker fsspec/HDF5 growth. Measured in-pod on the Fresno
node:

| granules done | per-worker RSS | cgroup total |
|---:|---:|---:|
| 200 | ~2.5 GB each | 16 GB |
| 750 | ~6.8 GB each | 43 GB |
| 850 | — | 48 GB |

**≈7.8 MB per granule per worker.** Each of the 8 workers handles ~1,531 of the
12,251 granules, so an unbounded run needs **~113 GB** against a 64 Gi limit.

**`match` already knows this.** Its `MAX_TASKS_PER_CHILD` docstring says, of the
1.0 run: *"N=15 and 16 workers that is ~108 GB against a 100Gi limit — which is
precisely how the pod died."* `geometry` was written later, without the guard.
Same failure, same cause, one stage apart.

**I got this wrong once before calling it.** Earlier in the run I saw memory go
17.2 → 16.7 GB and reported it as a steady state, not a leak. Two points, one of
them a dip, and I called a trend — the same mistake I had already made twice on
the match rate. The per-worker RSS series above is what settles it.

#### Mitigation applied now (no code, no restart)

`backoffLimit` 4 → **30** and `activeDeadlineSeconds` 72000 → **108000**,
patched on the **live** Job so the 800 granules already done were kept. The
stage writes progress per granule and re-queries `theta_s IS NULL` on start, so
each pod clears ~1,100 granules and resumes. 12,251 granules needs ~11 restarts;
30 is margin. Ugly, but it runs unattended and loses nothing.

#### The real fix, written and tested

`pab/matchup/geometry.py` — the pool now takes
`max_tasks_per_child=MAX_TASKS_PER_CHILD`, reusing `match`'s constant rather
than a second hard-coded number.

`pab/tests/test_geometry_pool.py` — **2 new tests**: one asserts the pool is
constructed with the bound (and that it equals `match`'s constant), one asserts
`geometry` references the shared constant so the two stages cannot drift apart
again. **Verified load-bearing**: with the fix removed the first test fails,
with it restored both pass.

Suite **348 passed, 1 skipped**.


#### The leak's *worst* outcome is not the OOM (observed 2026-09-28 00:24-00:43 UTC)

Pod 7 reached the 64 Gi ceiling and then did **not** die. It sat at the limit
burning **8 full CPU cores** in kernel reclaim, with **no progress for 19
minutes** — progress lines normally arrive every ~5 min:

```
memory 65,532 Mi (at the cgroup limit), CPU 8,088m, unchanged over 3 samples
last progress 00:24:37 (900/6646); observed 00:43:21
```

Reclaim kept freeing just enough page cache to keep the process alive, so the
OOM killer never fired. A clean OOM self-heals in ~2 min via `backoffLimit`;
**this state is unbounded** — the pod would have held 8 CPU / 64 Gi and made no
progress indefinitely. I deleted it manually to force the restart.

This matters for two reasons:

1. **It strengthens the case for the fix.** `backoffLimit` protects against a
   pod that *crashes*, not against one that refuses to die. The mitigation I
   applied is therefore weaker than I claimed when I filed this question.
2. **Nothing automatic catches it.** `activeDeadlineSeconds` would eventually
   (at 30 h, having wasted many), and liveness probes are not configured on
   these Jobs. The detectable signal is **progress-line staleness**: >3x the
   normal interval with CPU high and memory at the limit. Worth a probe on
   these manifests, or at least a note for whoever watches the next long run.

**Question:** commit `pab/matchup/geometry.py`, `pab/tests/test_geometry_pool.py`
and `nautilus/v2_geometry_job.yaml` (which now carries the measurements and the
backoffLimit reasoning)?

*My recommendation: yes, but there is no hurry* — the running job completes
without it via OOM-and-resume. The fix matters for the **next** run and for the
`fit` stage, which fans out the same way over many more units. Rebuilding the
image mid-run to pick it up would cost more than it saves.

>A.  Yes


### Q16 (Task 5, 2026-09-28) — 5 matchups have **no viewing geometry** and never will. How should `fit` treat them?

Geometry is done: **159,710 / 159,760 pixels (99.97 %)**. The 50 that are
missing belong to **5 matchups** whose AOP granules have no co-temporal L1B in
CMR:

```
PACE_OCI.20240628T154213.L2.OC_AOP.V3_2.nc
PACE_OCI.20250516T071437.L2.OC_AOP.V3_2.nc
PACE_OCI.20250629T150432.L2.OC_AOP.V3_2.nc
PACE_OCI.20250803T042640.L2.OC_AOP.V3_2.nc
PACE_OCI.20260514T222245.L2.OC_AOP.V3_2.nc
```

Measured to be permanent, not assumed: two sweep re-runs, the first recovering
the one transient timeout, the second recovering **nothing**. All five fail
with `FileNotFoundError` from the CMR lookup.

**Why it needs a decision.** The 2.0 configuration is the whole point of this
re-analysis, and `robust_hybrid` needs `theta_s`/`theta_v`/`dphi` at fit time.
`pab.fit.run.requires_geometry` exists precisely to express this, so these 5
matchups will hit it. Three options:

1. **Skip them.** `fit` writes no 2.0 fit for a matchup lacking geometry, and
   the release carries 15,971 of 15,976. Clean, honest, and the count is
   reported.
2. **Fall back to nadir geometry** (`theta_v = 0`, `dphi = 0`, `theta_s` from
   solar position). Keeps all 15,976, but stamps five fits with a geometry we
   invented. Given the whole reason `:2.0.x` exists is that the off-nadir
   correction was silently wrong before, manufacturing angles seems like the
   wrong instinct — and 5 matchups is not worth the asterisk.
3. **Fit them with `FitConfig.v1()`** (the elastic backend, which needs no
   geometry) and stamp them accordingly. Keeps coverage and is not a fiction,
   but puts two `rt_backend` values in one release, which the schema supports
   (`fits.rt_backend`) but which a careless reader could average over.

*My recommendation: (1), skip them.* 0.03 % of the store, the cause is
external and documented, and it keeps "every 2.0 fit used real measured
geometry" true without qualification. Option 3 is defensible if you would
rather not lose the matchups, but it needs a note in the release so nobody
mixes backends unknowingly.

**Either way**, `fit` should **fail loudly rather than silently** on a matchup
with no geometry — a 2.0 fit that quietly used zeros would be exactly the class
of bug the off-nadir emulator fix was about. Worth a test pinning that, which I
can write with whichever option you choose.

**Question:** (1), (2), or (3)?

>A.  (1)

#### Outcome: already implemented, and already tested — no change made

Checked before writing anything. `fit` enforces option (1) on both paths:

```python
# build_fits (bulk) -- refused BEFORE any granule is opened
if need_geom and inp["theta_s"] is None:
    _log.warning("fit skipped for %s: %s", inp["fit_id"], NO_GEOMETRY...)
    failed.append(inp["fit_id"]); continue

# fit_matchup (single)
raise ValueError(f"{matchup_id!r}: " + NO_GEOMETRY.format(...))
```

and four existing tests pin it: `test_requires_geometry_is_backend_dependent`,
`test_fit_matchup_raises_a_clear_error_without_geometry`,
`test_build_fits_without_geometry_fails_every_pixel_and_opens_nothing` (which
also asserts the granule is never opened), and
`test_gordon_config_fits_without_geometry` (the 1.0 backend is unaffected).

So the "fail loudly rather than silently" property I flagged as the thing that
mattered is already guaranteed — `requires_geometry`'s docstring states it as
R3: *"``theta_s`` is never silently defaulted, so a fit without geometry must
be refused rather than run on an assumed angle."* **No code was written for
this answer.** Expect Prompt 6's full send to report **5 matchups under
`failed`** with the `no viewing geometry` reason; that is correct behaviour,
not a regression.


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


### Task 4 — match for the v2 backfill (2026-09-25/26): **done — +1,277 matchups, 14,610 → 15,887**

Launched on `:2.0.2` at 15:04 UTC 2026-09-25 after the Q7 stale-image error was
closed; `pab pipeline done` at **04:36 UTC 2026-09-26**, **13 h 32 m** wall.

**Gates, all passed.**

| gate | result |
|---|---|
| right image | `git_sha {"PAB":"dacefa1", …}`, matching HEAD |
| **selection honoured** | `match: selection restricts to 7998` — **not** the 40,414 of the aborted run |
| baseline unchanged | 14,610 / 146,100 before launch, byte-identical to pre-abort |
| FDs bounded | `soft=65536 hard=65536`; no FD errors in 13.5 h |
| memory | peak ~31 GB of 100 Gi; **no OOM** (the 1.0 run was killed six times) |
| stalls recovered | 60 fired, pool rebuilt every time, run completed |
| plateau reached | yes — stage returned its summary |

**Outcome.**

| | |
|---|---:|
| selected | 7,998 |
| pre-skipped (already matched / no position / **no candidate granule**) | 3,176 |
| **attempted** | **4,822** |
| processed | 4,472 |
| **stalled — deferred to a sweep** | **350** |
| hard failures | **8** (0.17 %) |
| **matchups written** | **+1,277** |
| store | **14,610 → 15,887** matchups; 146,100 → 158,870 pixels |

**Yield on profiles actually processed: 1,277 / 4,472 = 28.6 %** — Q1's 28 %
assumption reproduced almost exactly.

**By gap, against Q1's revised table:**

| gap | Q1 expected | actual | |
|---|---:|---:|---|
| A (06-01…07-06) | ~673 | **616** | 48.2 % of new |
| B (07-06…09-17) | ~544 | **576** | 45.1 % |
| D (older backfill) | ~29 | **85** | 6.7 % |
| **total** | **~1,246** | **1,277** | +2.5 % |

**Gap D came in 3× its forecast**, and that is the downstream confirmation of
the correction already recorded in Plan §4: I had predicted D would be
dominated by position-less profiles using a 13.5 % historical recovery rate,
and the actual ingest recovered positions for **368 of 372 (99 %)**. The 85
matchups are the consequence. The 13.5 % figure came from a sample of rows
ingested in the *original* run — i.e. an already-failed population — and never
generalised.

**Distance and Δt medians** (new vs the 14,610 pre-existing):

| | new | pre-existing |
|---|---:|---:|
| `distance_km` median | **0.82** (p10 0.33, p90 3.68) | 0.80 |
| `dtime_hours` median | **9.08** (p10 1.00, p90 21.80) | 10.22 |
| `n_spectra` median | 10 (total 12,770) | |

The new matchups are **not** a looser population than the 1.0 set — the same
sub-km median separation, and a slightly *tighter* time offset. All 1,277 are
stamped `pab_version 2.0`.

**Rate: 10.8 s/profile aggregate at 16 workers**, stable to ±0.3 across 50+
measurements spanning 13 h. Per-window rates ranged 4.9–23.7 s/profile — the
noise band is wide, the mean is not.

**The cost of the stalls, measured.** 60 stall-guard firings, each 120 s plus a
pool rebuild, at a strikingly regular cadence of ~12.7 min; 459 granule read
timeouts underneath them. That is **~20 % of the wall clock**, and accounts for
the gap between the ~7 s/profile baseline and the observed 10.8 without
appealing to anything else. The cause is NASA-side: OB.DAAC/cloudfront returned
a 503 on the one fully-diagnosed failure, and a stall is what a hung 1.8 GB
granule read looks like.

**Three measurement lessons from this run**, all of which cost me a wrong
statement first:

1. **`stalled` is a third bucket**, alongside `written` and `unmatched`, and it
   is *not* counted in "processed". Progress lines stop at 4450/4822 not
   because the run died but because 350 profiles never completed. Every
   intermediate yield I quoted used the processed denominator — right by
   construction, but my *projected total* used 4,822 and therefore
   over-counted (~1,400 against the true 1,277).
2. **The first fifty are never the rate — in either direction.** Prompt 5 Task
   3 taught "sample later, the early rate is pessimistic"; here the early rate
   was *optimistic* (6.8 s/profile against a 10.8 mean). The transferable rule
   is only that a short early window is unreliable, not which way it errs.
3. **A single low-CPU sample is not evidence of a hang.** Four separate times
   a reading of 15–190 m looked like a dead job and was a chunked-pool
   rebuild; the pool came back at ~1,000 m within 60 s every time. Any
   low reading now needs a resample before it means anything, and `Send-Q`
   alone is likewise meaningless without a frozen `bytes_sent` beside it.

**What remains: the 350 stalled profiles.** They stay `unmatched` and are
retried by simply re-running the job — matched profiles are skipped before any
granule is opened, so a sweep costs only those 350. At the measured 28.6 %
they should add **~100 matchups → ~15,987**, which lands on Q1's revised
~15.9 k. That number will be **measured, not estimated** (Q10).

### Task 5 — geometry for every pixel (2026-09-27/28): **done — 159,710 / 159,760 pixels (99.97 %)**

Ran on `:2.0.3` (`99c37ef`), `--jobs 8`, over the whole v2 store. Started
14:15 UTC 2026-09-27, `V2_GEOMETRY_DONE` 11:07 UTC 2026-09-28 — **20.9 h**,
12,475 granules, **6.0 s/granule** average.

#### Gates (verified against the database, not just the job's own output)

| gate | result |
|---|---|
| every `matchup_pixels` row has `theta_s` | **FAIL — 50 missing** (5 granules, 5 matchups) |
| `geom_source = 'L1B_V3'` | **PASS** — 159,710; the 50 are `None` |
| `theta_v` spans 0–~60° | **PASS** — **12.63 – 60.00** |
| `dphi` inside (−180, 180] | **PASS** — −179.97 … 179.88, **0** violations |
| grid-check mismatches | **0** |
| `theta_s` range | 1.37 – 75.00 |

`theta_v` topping out at exactly **60.0°** matches the swath-edge expectation
in Prompt 6 Task 1, and **0 mismatched pixels** means the L1B grid agreed with
the stored `ix`/`iy` on every one of 159,710 reads — the check that would have
exposed a geolocation or indexing error.

#### The 50 missing pixels are permanent, and measured to be so

Two sweep re-runs (the remedy this task prescribes — "simply running it again",
57 s each because filled pixels cost no network work):

```
sweep 1:  60 pixels over 6 granules -> 10 written, 5 granules failed
sweep 2:  50 pixels over 5 granules ->  0 written, 5 granules failed
```

Sweep 1 recovered the one transient `TimeoutError`. Sweep 2 recovered nothing,
confirming the remaining five are permanent. Every failure is
`FileNotFoundError` — CMR returns no L1B granule with the expected name for
that AOP granule:

```
PACE_OCI.20240628T154213.L2.OC_AOP.V3_2.nc
PACE_OCI.20250516T071437.L2.OC_AOP.V3_2.nc
PACE_OCI.20250629T150432.L2.OC_AOP.V3_2.nc
PACE_OCI.20250803T042640.L2.OC_AOP.V3_2.nc
PACE_OCI.20260514T222245.L2.OC_AOP.V3_2.nc
```

This is the first of the two causes this task anticipated ("an L1B missing from
CMR"); the second (grid-check failures) did not occur at all. **5 matchups of
15,976 (0.03 %)** are affected — see **Q16** for how `fit` should treat them.

#### Rate: what actually governs this stage

The task noted two single-granule measurements disagreeing 5× and asked for a
~200-granule slice. I did not build one: the stage is idempotent on
`theta_s IS NULL` and does zero network work for filled pixels, so the real job
*is* the measurement and a kill costs nothing. That turned out to matter,
because the first run projected **47 h**.

Splitting the per-granule cost showed why:

| | |
|---|---:|
| CMR lookup | **0.4–1.4 s** (~1 % of the cost) |
| L1B geolocation open, workstation (Santa Cruz) | 4.7–7.4 s |
| 1-CPU probe, `humboldt.edu` | 7.7 s |
| 8 workers, `moff.sdstate.edu` | **13.7 s/granule** |

**One California worker beat the whole 8-worker South Dakota pod by ~1.8×.**
The data is in AWS **us-west-2**; the pod was in South Dakota, and its 8 workers
contended for node bandwidth (CPU sat at 74 millicores across all eight).
Pinning to 193 California amd64 nodes took the rate to **3.2 s/granule**.

Per-node rates, measured across 13 pods:

| node | s/granule |
|---|---:|
| `proc-02.ts.fresnostate.edu` | **3.2 – 4.6** |
| `node-2-10.sdsc.optiputer.net` | 4.9 – 6.5 |
| `k8s-chase-ci-07.calit2.optiputer.net` | 5.8 – 6.4 |
| `cph-blade15.humboldt.edu` | 8.5 – 8.9 |
| `moff.sdstate.edu` (before the move) | 13.7 |

Humboldt gave 7.7 s/granule with **one** worker and 8.5 with **eight** — i.e.
it is bandwidth-limited like South Dakota, just less severely. Only the Fresno
nodes actually scale with concurrency. **For the next network-bound stage,
prefer Fresno-class nodes specifically, not "California" generally.**

**`--jobs 8` was kept**, as this task directs. The measurement shows the CMR
etiquette cap is guarding something that costs ~1 % of the runtime, so raising
it would be defensible on throughput grounds — but it is a working agreement,
so it stands, with the reasoning recorded in the manifest instead of acted on.

#### Cost: 13 pods, 12 restarts — an unbounded worker pool (Q15)

`build_geometry` builds its pool **without** `max_tasks_per_child`, which
`match` sets precisely to bound per-worker fsspec/HDF5 growth (~7.8 MB per
granule per worker → ~113 GB for a full run against a 64 Gi limit). The run
therefore OOMed and resumed every ~950 granules. Mitigated live by raising
`backoffLimit` 4 → 30 and `activeDeadlineSeconds` to 30 h, with no lost work.
Failure modes across 13 pods: **10 clean OOM, 1 node `Unknown`, 1 pre-OOM
thrash** (see Q15 — the pod pinned itself at the memory ceiling and made no
progress for 19 min without dying; I killed it manually), **1 clean completion**.

#### Updated fit-cost projection (Plan §3)

The store holds **15,976** matchups, not the ~16.8 k the plan assumed.

| basis | per fit | 16 workers |
|---|---:|---:|
| Prompt 4 in-pod (upper bound, includes JAX's first compile) | 226 s | **~63 h** |
| workstation, uncontended | 101 s | **~28 h** |

Prompt 6's leading slice should narrow this rather than leaving the range
standing. Note the geometry lesson does **not** transfer directly: `fit` is
CPU-bound MCMC, not network-bound, so node placement should matter far less —
but `max_tasks_per_child` will matter more, since `fit` fans out over 16 k
units.

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


### Task 7 — reacting to Q7 (2026-09-25): **the stale-image error, closed out**

Q7 recorded my error: I launched `pab-v2-match` against `:2.0.1`, an image
built four days before the `match`-selection change, and the job did the
unrestricted thing while its own provenance line said so in its first
sentence. JXP answered `>A. Yes, please do` to the three-step unblock and
`>A. Let's adopt your recommendation.` to the discipline. Both are now done.

**1. The commit landed (JXP's, not mine).** HEAD `dacefa1`, tree clean apart
from this prompt doc. Verified the change is in the commit, not merely in the
working tree:

```
HEAD:pab/matchup/engine.py   contains  selection: set[tuple[int, int]] | None
HEAD:pab/pipeline.py         contains  selection=config.selection_keys()
```

**2. Rebuilt as `:2.0.2`.** All five build guards passed:

| guard | result |
|---|---|
| `ED OK` | `350 750 (3, 81)` |
| `ROBUST OK` | off-nadir delta `0.0116..0.0926`, **std 0.0245** |
| `PAB 2.0 OK` | `robust_hybrid 400.0 700.0` |
| `PROVENANCE OK` | `{"PAB":"dacefa1", …}` |
| `STAGES OK` | 7 stages incl. `geometry` |

The `ROBUST OK` guard remains the regression test for the off-nadir
standardisation fix (`std > 1e-3` ⇒ the correction is spectrally varying, not
a flat tanh-saturated constant).

**3. The new discipline, applied — and applied twice over.** The check Q7
asked for is a SHA diff; I ran that *and* a behavioural check, because the SHA
is only a proxy for what I actually care about:

```
image PAB_GIT_SHAS : dacefa1     (env and OCI revision label agree)
git HEAD           : dacefa1     MATCH

build_matchups accepts selection : True
match() forwards selection_keys  : True
```

`:2.0.1` would have passed neither. Had I run only the second check, I would
still have caught it; had I run only the first, I would have caught it too —
but the pair is what makes the result trustworthy rather than lucky.

**4. Pushed — with a stall, diagnosed differently from the last one.** The
first push attempt wedged after ~1.97 GB:

```
ESTAB  Send-Q 4,170,240  ->  137.164.28.180:443
bytes_sent frozen (0 B in 25 s);  log silent 16 min
17 of 18 layers Pushed; 2df9f080999e wedged
```

This is **not** the `:2.0.1` failure recurring. That one was an IPv6 blackhole
— no socket at all, zero bytes ever sent. This was a live IPv4 socket that had
already moved 1.97 GB and then died mid-layer with 4 MB unacked. Same
symptom, different cause.

Two things learned that are worth keeping:

- **Log mtime is not a liveness signal for `docker push`.** In non-TTY mode
  docker prints only state changes, no progress bars, so a healthy multi-GB
  layer looks identical to a dead one for 20+ minutes. `bytes_sent` to the
  registry is the signal. On the retry the log was silent for 16 minutes while
  moving **69 MB per 30 s**.
- **`Send-Q` alone is not evidence of a stall** — a saturated upload also
  parks ~4 MB there. It only means something *combined with* frozen
  `bytes_sent`.

Rather than retry by hand (which is what cost 66 minutes on `:2.0.1`), the
retry ran under a watchdog — `nautilus/`-adjacent, kept in the session
scratchpad — that samples `bytes_sent` every 30 s and kills-and-restarts an
attempt after 240 s of no traffic *and* no log growth, 8 attempts per tag. It
was not needed: attempt 1 completed in 28 minutes.

```
2.0.2:  sha256:3400742e0f97509122ba0565dad7741cc5131a2ccac6f398f1bb98abc6145185
latest: sha256:3400742e0f97509122ba0565dad7741cc5131a2ccac6f398f1bb98abc6145185
```

**A cost worth flagging, not fixed.** `COPY PAB/` sits *before* the 7.74 GB
`RUN pip install` layer, so **any** PAB source change invalidates all of it —
which is why both `:2.0.1` and `:2.0.2` were multi-GB pushes rather than the
~175 MB the source change actually represents. The registry also does not
resume a partial layer, so attempt 1's 1.97 GB was re-sent from zero.
Splitting that `RUN` into "install third-party deps" (cached, stable) then
`pip install --no-deps` for the local packages would take every future
rebuild-and-push from ~2.5 GB to ~50 MB. This is a Dockerfile change beyond
Task 7's scope — **left for JXP to call.**

**5. Relaunched — and the gate passed.** Namespace was clean (the killed job
left nothing). Only the `image:` tag changed, with the digest recorded inline.

```
git_sha {"PAB": "dacefa1", …}
counts: {'profiles': 59620, 'granules': 72803, 'matchups': 14610,
         'matchup_pixels': 146100, 'fits': 14609}
match: selection restricts to 7998 of the store's profiles
match: 4822 profiles over 16 processes
```

**7,998, not 40,414** — the Q7 failure is closed. The database baseline is
byte-identical to before the killed run (14,610 matchups / 146,100 pixels),
confirming again that the aborted job wrote nothing.

**On the 4,822.** The selection restricts to 7,998; `build_matchups` then
pre-filters before opening any granule (`pab/matchup/engine.py:690-711`):
already-matched, no position, and **no candidate granules**. So 3,176 profiles
are dropped cheaply — consistent with Q4's measured prediction that ~3,222
gap-B profiles postdate PACE's forward stream (which ends 2026-08-01) and have
no granule to match against. Expected behaviour, and it means Q6's ~6 h
estimate is now an upper bound. I am taking the real rate from the running
job rather than re-deriving it, per the Prompt 5 rate lesson.

**What I did differently, stated plainly.** Last time the evidence was in the
first line of the log and I read past it. This time the profile count was a
declared gate *before* launch, with a kill criterion attached (40,414 ⇒ kill
immediately). Checking provenance is worth little if nothing is riding on the
answer; naming the number that would make me stop is what turned it into a
real check.


### Task 8 — acting on Q8–Q10 (2026-09-26): **sweep done (+89 → 15,976); Q8a/Q8b implemented; geometry blocked on a commit**

JXP answered Q8(a) *"Yes, make that change for the next image"*, Q8(b) *"Yes,
fold it into the geometry work"*, Q9 *"Yes, let it run"*, Q10 *"Yes, both in
that order"*.

#### Q9 — nothing to do

Already actioned: `match` ran to completion (Task 4 report).

#### Q10(a) — the sweep: **+89 matchups, 15,887 → 15,976**

| | |
|---|---:|
| targeted | **350** stalled profiles |
| processed | 321 |
| **written** | **+89** (27.7 % yield) |
| stalled again | 29 |
| failures | 4 |
| wall | **67 min** |
| store | **15,976** matchups / 159,760 pixels |

By gap: **A 50, B 34, D 5**; median separation **0.72 km**, median Δt 9.49 h.

**The stalled profiles yielded 27.7 %, against the main run's 28.6 %.** They
were not unmatchable — they were unlucky, stalled behind NASA-side granule
timeouts. That is the justification for running a sweep at all, and it is now
measured rather than argued.

Combined backfill: **1,277 + 89 = 1,366** new matchups, against Q1's revised
~1,246 and Q6's ~1,350.

**A correction to Q10(a), which I got wrong when I proposed it.** I wrote that
the sweep would be the manifest *unchanged*, reasoning that pre-skipping makes
everything but the stalled profiles free. That is false: `build_matchups`
pre-skips on already-matched / no-position / **no candidate granule**, and a
profile that came back `unmatched` because no pixel qualified still *has*
candidate granules, so a re-run re-opens them at full price.

| | profiles | wall |
|---|---:|---:|
| manifest unchanged (as written in Q10a) | ~3,545 | **~10.6 h** |
| restricted to the stalled set | **350** | **67 min measured** |

The ~1–2 h I quoted belonged to the restricted run. So the sweep used
`--profiles-csv` over the 350 ids recovered from `/data/v2/match.log`
(`nautilus/v2_match_sweep_job.yaml`, `/data/v2/sweep_stalled.csv`) — the
mechanism added in Q5. All 350 were verified present in the store and none
already matched before launching.

**29 still stalled.** A third pass would recover ~8 matchups on the same 27.7 %
— diminishing returns, and not run.

#### Q10(c) — the hung job, and a correction to my own diagnosis

The main `match` job was deleted after verifying its writes were committed
(15,887) and `/data/v2/match.log` preserved. It had held **16 CPU / 100 Gi for
~8.5 h** doing nothing.

**The sweep reached `V2_MATCH_SWEEP_DONE` and exited cleanly despite hitting 5
stalls.** So the exit hang is **not** a deterministic consequence of a stall,
as Q10(c) implied — it depends on whether `_reclaim_pool` manages to shut the
abandoned pool down. That makes it an intermittent hazard rather than a
certainty, which is worse for diagnosis, not better: a job that usually exits
will not be suspected when it occasionally does not.
`activeDeadlineSeconds: 21600` was added to the sweep manifest as a bounded
safety net; the underlying fix is still open.

#### Q8(b) — a NASA 503 no longer reports as a pickling bug

`pab/parallel.py` gains `WorkerError` and `portable_errors()`, applied in
`geometry_for_granule` (the L1B open) and in `find_matchup` (the granule open
**and** the extract — the extract is where the lazy HTTP reads actually
happen, so a 503 surfaces there too). Same exception through a real
`ProcessPoolExecutor`:

```
WITHOUT  -> TypeError: can't pickle Unpicklable objects
            cause visible (mentions 503)? False
WITH     -> WorkerError: granule G1: Unpicklable: 503, message='Service Unavailable'
            cause visible (mentions 503)? True
```

Picklable exceptions are re-raised **unchanged**, so `find_matchup`'s existing
`except TimeoutError` still fires. **6 new tests**, one of which asserts the
stand-in really is unpicklable so the others cannot silently stop testing
anything. Suite **346 passed, 1 skipped** — the 340 baseline plus exactly these.

#### Q8(a) — the layer split, measured, and my estimate corrected

| layer | before | after |
|---|---:|---:|
| cached (below the source COPYs) | 1.39 GB | **7.03 GB** |
| **rebuilt on a PAB source edit** | **~7.96 GB** | **~934 MB** |

**8.5×.** All five build guards pass on the restructured image.

Two things I got wrong and have corrected in place:

1. **The first attempt barely worked.** I assumed my hand-written third-party
   list approximated the real dependency closure. It missed the largest item
   by far: `bing/setup.py:31` declares `timm==0.3.2`, which drags in torch and
   **5.27 GB** of NVIDIA CUDA wheels. Layer 2 was still 6.35 GB. I only found
   this because I measured the layer sizes instead of trusting the change —
   which I should have done before claiming the saving, not after.
2. **"~50 MB" was a guess.** The real residual is ~934 MB: `COPY PAB/` (175 MB)
   plus the layer-2 local install (712 MB). Q12 is what would shrink it
   further.

**I also did not implement `--no-deps`**, which Q8(a) proposed and JXP
approved. `bing/setup.py` declares ~25 real dependencies and `--no-deps` would
silently drop any my explicit list missed — a failure that would not appear
until an import inside a pod. Layer 2 installs *with* deps instead; everything
heavy is already satisfied by layer 1, so the layer stays small and a missed
entry is merely installed in the wrong layer rather than dropped. Flagged in
Q11 so JXP can overrule.

#### Blocked: geometry

`geometry` should carry the Q8(b) fix, so it needs a new image, and the build
bakes `PAB_GIT_SHAS` from git. Building `:2.0.3` from the uncommitted tree
would stamp `dacefa1` — a commit containing none of this — which is the exact
provenance lie that let `:2.0.1` run four-day-old code in Prompt 5 Task 4.
**Q11** asks JXP to commit. **Q12** asks whether to remove the 5.3 GB of
torch/CUDA outright.

`nautilus/v2_geometry_job.yaml` is written and pre-flighted: all 3 inline
`python -c` snippets parse, and all 8 gate SQL statements run against a real
v5 schema. The workload is now exact: **159,760 pixels, none with `theta_s`.**


### Task 9 — acting on Q11–Q13 (2026-09-27): **`:2.0.3` shipped, geometry running; two defects found by measuring**

JXP answered Q11 *"yes, commit those files"*, Q12 *"(2)"* (CPU-only torch) and
Q13 *"you run it"* (an explicit, recorded exception to the `CLAUDE.md` git
rule). `git commit` turned out to be blocked by a permission rule regardless —
`git add` succeeded, the commit was denied twice — so JXP made the commit,
`99c37ef`.

#### Q12 → (2): CPU-only torch

| | `:2.0.2` | `:2.0.3` |
|---|---:|---:|
| `nvidia/` | 3,196 MB | **gone** |
| `triton/` | 897 MB | **gone** |
| `torch/` | 1,177 MB | 769 MB (`2.14.0+cpu`) |
| image, uncompressed | 9.19 GB | **4.43 GB** |
| image, compressed | 4,254 MB | **1,430 MB** |
| **push wall time** | 28 min | **6 min** |

**An unexpected confirmation:** `import timm` fails in the new image
(`No module named 'torch._six'`) — and fails **identically in `:2.0.2`**, which
had `torch 2.14.0+cu130`. `timm==0.3.2` is from 2021 and uses `torch._six`,
removed in modern torch. It has therefore never imported in any image we ship,
which is independent evidence for the Q12 premise that it is dead weight rather
than a dependency. Nothing was broken by removing its CUDA stack.

#### `:2.0.3` — both sides of the Q7 check

```
1. SHA        image "PAB":"99c37ef"  ==  git HEAD 99c37ef     MATCH
2. behaviour  portable_errors importable, and actually used in
              geometry_for_granule AND find_matchup            True
              torch 2.14.0+cpu, cuda: False
guards        ED OK / ROBUST OK std 0.0245 / PAB 2.0 OK / PROVENANCE OK / STAGES OK
```

The SHA is a proxy; the behavioural probe is the thing that matters. Kept both.

#### Geometry: 47 h → 11 h, by measuring instead of guessing

Launched on `:2.0.3`, `--jobs 8`, 159,760 pixels over 12,475 granules. The
first node gave **13.7 s/granule → ~47 h**, far outside the task's 4–22 h
envelope. Rather than accept it or raise `--jobs` blindly, the cost was split:

| | |
|---|---:|
| CMR lookup | **0.4–1.4 s** (~1 % of the per-granule cost) |
| L1B geolocation open, workstation (Santa Cruz) | **4.7–7.4 s** |
| same, 1-CPU probe on `humboldt.edu` | **7.7 s** |
| 8 workers on `moff.sdstate.edu` | **13.7 s/granule** (0.073 granules/s) |

**One California worker beat the entire 8-worker South Dakota pod by ~1.8×.**
The data lives in AWS **us-west-2**; the pod was in South Dakota. The 8 workers
bought nothing because they contend for the node's bandwidth — CPU sat at 74
millicores across all eight.

Relaunched pinned to 193 California amd64 nodes:

| | South Dakota | California |
|---|---:|---:|
| rate | 13.7 s/granule | **3.2 s/granule** |
| projection | ~47 h | **~11 h** |

**`--jobs 8` was kept.** The measurement shows the CMR etiquette cap is
guarding something that costs ~1 % of the runtime, so raising it would be
defensible — but it is a working agreement, so it stands, with the reasoning
recorded in the manifest instead.

**Idempotency verified, not assumed:** the relaunch reported `2,707 pixels
already filled` and 12,251 granules instead of 12,475, so the 224 granules done
before the move were kept.

#### The defect that mattered: an unbounded worker pool (Q15)

`build_geometry` constructs its `ProcessPoolExecutor` **without**
`max_tasks_per_child`, which `match` sets precisely to bound per-worker
fsspec/HDF5 growth.

| granules done | per-worker RSS | cgroup |
|---:|---:|---:|
| 200 | ~2.5 GB each | 16 GB |
| 750 | ~6.8 GB each | 43 GB |
| 850 | — | 48 GB |

≈**7.8 MB per granule per worker** → ~113 GB for the full run against a 64 Gi
limit. `match`'s own constant documents this exact failure from the 1.0 run:
*"which is precisely how the pod died."* `geometry` was written later without
the guard.

**Mitigation, applied to the live Job with no restart and no lost work:**
`backoffLimit` 4 → **30**, `activeDeadlineSeconds` 72000 → **108000**. The
stage writes progress per granule and re-queries `theta_s IS NULL` on start, so
it OOMs and resumes.

**Validated end to end**, rather than assumed:

```
lf5ws  OOMKilled (exit 137) after 58 min   (predicted OOM near granule ~1,090)
l4s76  rescheduled to node-2-10.sdsc.optiputer.net   <- affinity survived
       "144813 pixels over 11214 granules (14947 pixels already filled)"
       => 1,037 granules completed by the OOMed pod, none lost
```

**The real fix is written and tested but not shipped** (Q15): the pool now takes
`max_tasks_per_child=MAX_TASKS_PER_CHILD`, reusing `match`'s constant; two new
tests pin it, and removing the fix makes the first one fail. Suite **348 passed,
1 skipped**. Not rebuilt mid-run, because the running job completes without it.

#### Failure causes, pass one

```
74 TimeoutError       L1B open exceeded the bound — transient
 2 FileNotFoundError  no L1B in CMR for that AOP granule — permanent
 0 WorkerError
 0 mismatched pixels
```

The timeouts **self-heal**: a failed granule leaves `theta_s IS NULL`, so every
resume pass retries it, and there are ~11 passes ahead. Only the two missing-L1B
cases are permanent. `0 mismatched` means no pixel has failed its grid check —
the gate that would show the L1B grid disagreeing with the stored `ix`/`iy`.

**`WorkerError: 0` is the Q8(b) fix working, not idling.** `TimeoutError` is
picklable, so `portable_errors` re-raises it unchanged instead of flattening
it — which is exactly why `find_matchup`'s `except TimeoutError` still fires.
The flattening path is reserved for genuinely unpicklable exceptions like the
aiohttp 503.

#### Where I was wrong

**I called the memory growth a steady state before it was one.** At granules
50–200 I saw the cgroup go 17.2 → 16.7 GB and reported "not a leak, steady at
~17 GB". Two points, one of them a dip, and I declared a trend — the third time
this session, after the match rate ("degrading monotonically", from four
windows) and the stall in-flight counts ("growing", from seven). The per-worker
RSS series is what settled it, and it is what I should have looked at first.

**I also over-claimed the layer-split saving twice** — "~50 MB" when the
measured residual was 934 MB, and then "8.5×" from builds that shared a
`PAB_GIT_SHAS` value. The `:2.0.3` push re-sent its dependency layers, but that
build also changed the Dockerfile, so it cannot distinguish "the ARG
invalidated the cache" from "the edit did". Recorded as **Q14**, to be settled
by a clean two-build test rather than another assertion.


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

### 2026-09-25 (Prompt 5 Task 7 — Q7 closed: `:2.0.2` built, pushed, match relaunched and gated)

Executed Task 7, which asked me to react to JXP's Q7 answers before anything
else. Q7 was my own error written up: I had launched `pab-v2-match` against
`:2.0.1`, an image built four days before the `match`-selection change, and
the job silently ran unrestricted (40,414 profiles instead of 7,998). JXP
answered `>A. Yes, please do` to the unblock plan and `>A. Let's adopt your
recommendation.` to the SHA-diff discipline.

**Verified the commit before building.** JXP had committed the change as
`dacefa1`; I checked `HEAD:pab/matchup/engine.py` and `HEAD:pab/pipeline.py`
directly rather than trusting a clean `git status`, because the whole point of
Q7 was that the working tree and the built artifact had diverged.

**Rebuilt `:2.0.2`**, all five guards green, including the `ROBUST OK`
regression test for the off-nadir standardisation fix (std 0.0245 ⇒ spectrally
varying, not a saturated constant).

**Applied the new discipline — and learned that the SHA check is the weaker
half.** I ran both the SHA diff (`image dacefa1 == HEAD dacefa1`) and a
behavioural probe (`build_matchups accepts selection: True`). The SHA is a
proxy; the behaviour is the thing. Keeping both is what makes a pass
meaningful rather than lucky, and I would not drop the behavioural one.

**The push stalled, and the interesting part is that it stalled differently
from last time.** `:2.0.1` had failed as an IPv6 blackhole — no socket, zero
bytes. This one was a live IPv4 socket that moved 1.97 GB and then died
mid-layer with 4 MB unacked and `bytes_sent` frozen. I nearly mis-diagnosed it
as the IPv6 problem recurring; the cumulative byte count is what ruled that
out. Two lessons recorded in the report:

- **`docker push` log mtime is not liveness.** Non-TTY docker prints only
  state changes, so a healthy 7.74 GB layer is silent for 20+ minutes. On the
  retry the log sat untouched for 16 minutes while moving 69 MB per 30 s — I
  would have killed a perfectly good push had I trusted the log.
- **`Send-Q` alone means nothing.** A saturated upload parks the same ~4 MB
  there as a dead one. It is evidence only alongside frozen `bytes_sent`.

Rather than hand-retry (the thing that cost 66 minutes on `:2.0.1`), I wrote a
watchdog that samples `bytes_sent` every 30 s and kills-and-retries after 240 s
of no traffic *and* no log growth. It proved unnecessary — attempt 1 finished
in 28 minutes — but it converts a stall from a lost check-in cycle into a
4-minute self-heal. Both tags landed on
`sha256:3400742e0f97509122ba0565dad7741cc5131a2ccac6f398f1bb98abc6145185`.

**Flagged but deliberately not fixed:** `COPY PAB/` precedes the 7.74 GB
`RUN pip install` layer, so every PAB source change re-pushes ~2.5 GB for what
is really a 175 MB change, and a stall re-sends it from zero because the
registry does not resume partial layers. Splitting the `RUN` into cached
third-party deps plus `--no-deps` local installs would make future pushes
~50 MB. That is a Dockerfile change outside Task 7's scope, so it is JXP's
call, not mine to slip in.

**Relaunched with a declared gate.** Only the `image:` tag changed (digest
recorded inline). The job now reports `selection restricts to 7998` — the Q7
failure is closed — and the pre-launch DB counts are byte-identical to before
the aborted run, re-confirming it wrote nothing.

**The real lesson from Q7, which I think is not "check the SHA".** I had the
evidence last time: the job printed its provenance as its first act. What was
missing was a *consequence*. This time I named the number that would make me
kill the job (40,414) before launching, so the check had something riding on
it. A verification nobody acts on is decoration.

**One number I chased rather than assumed:** the job attempts 4,822, not
7,998. I did not want to wave that through the way I waved past the 40,414, so
I read `pab/matchup/engine.py:690-711`: `build_matchups` pre-filters
already-matched, position-less, and **granule-less** profiles before opening
anything. The 3,176 dropped match Q4's measured prediction of ~3,222 gap-B
profiles postdating PACE's forward stream. Expected — and it makes Q6's ~6 h
an upper bound.

### 2026-09-26 (Prompt 5 Task 4 — match completed: +1,277 matchups, and three ways I mismeasured it)

`pab-v2-match` on `:2.0.2` ran 15:04 UTC 2026-09-25 → 04:36 UTC 2026-09-26,
**13 h 32 m**, and closed out the Q7 failure: it reported
`selection restricts to 7998`, not the 40,414 the stale image produced.

**Result: +1,277 matchups, 14,610 → 15,887**, 8 hard failures (0.17 %), 350
profiles stalled and deferred to a sweep. Yield on profiles actually processed
was **28.6 %**, reproducing Q1's assumption; the per-gap split (A 616, B 576,
D 85) came within 2.5 % of Q1's revised total of ~1,246. New matchups are not
a looser population than the 1.0 set — median separation 0.82 km against 0.80,
and a slightly *tighter* Δt (9.08 h against 10.22).

**Gap D came in 3× its forecast (85 against ~29)**, which is the downstream
proof of a correction I had already had to make: I predicted D would be
dominated by position-less profiles from a 13.5 % recovery rate, and the real
rate was **99 %**. My 13.5 % sample came from an already-failed population. The
85 matchups are what that error would have cost had JXP taken my
recommendation to ingest only the 103 positioned profiles.

**Three mismeasurements, each of which produced a wrong statement before I
caught it.** Recording them because the pattern is the same each time — I
treated one reading as a trend.

1. **I did not know `stalled` was a third bucket.** `build_matchups` returns
   `written` / `skipped` / `unmatched` / **`stalled`**, and stalled profiles
   are not counted in "processed". So progress lines stop at 4450/4822 on a
   perfectly healthy run. I spent a check-in reporting "the stage has
   finished" off a log dump, then had to verify and correct myself — the
   4450/4822 reading should have stopped me first. My running *projection* was
   also inflated (~1,400 vs the true 1,277) because it divided by 4,822 rather
   than the processed count.
2. **I twice read a trend off too few points.** I called the rate "degrading
   monotonically" off four windows and projected 18.6 h; it was noise around a
   10.8 s/profile mean and finished at 14.5 h-equivalent. I flagged stall
   in-flight counts as "growing" off seven points (mean 3.9 → 10.7); the next
   four were 19, 1, 1 and the trend evaporated. Hedging the second one was
   right; making the claim at all was not necessary.
3. **A single low-CPU sample never meant what it looked like.** Four times a
   reading of 15–190 millicores looked like a dead job and was a chunked-pool
   rebuild between chunks of 64, back to ~1,000 m within 60 s. I eventually
   built resampling into the watcher. The same shape appeared in the image
   push: `Send-Q` at 4 MB reads as a wedge only when `bytes_sent` is *also*
   frozen — on a healthy saturated upload it looks identical.

**The transferable version of the rate lesson, corrected.** Prompt 5 Task 3
recorded "take the rate a few hundred in, the early sample over-projects".
That is too specific: there the early sample was pessimistic, here it was
optimistic (6.8 s/profile against a 10.8 mean). The rule is only that a short
early window is unreliable — not which direction it errs.

**Stall cost, measured rather than assumed:** 60 firings at a regular ~12.7 min
cadence, 120 s each plus a pool rebuild, over 459 granule read timeouts ≈
**20 % of wall clock**, which fully explains 10.8 s/profile against a ~7 s
baseline. Cause is NASA-side (a 503 from OB.DAAC on the one fully-diagnosed
failure); nothing local to fix.

**Left for JXP (Q10):** the sweep for the 350 stalled profiles (a bare re-run;
expected ~100 more matchups → ~15,987, to be *measured*) and the Task 5
geometry launch. Both are job launches, so both wait for confirmation, per the
practice established in Q2/Q4/Q6.

### 2026-09-26 (Prompt 5 Task 8 — Q8–Q10 actioned: sweep +89 → 15,976; two of my own estimates corrected)

Executed Task 8 against JXP's answers to Q8(a), Q8(b), Q9 and Q10. Q9 needed
nothing (match had already run). The rest produced one completed job, two code
changes, and two corrections to claims I had made in the Q&A itself.

**The sweep recovered 89 matchups in 67 min**, taking the store to **15,976**.
The number that matters is not 89 but the *yield*: the stalled profiles came
back at **27.7 %** against the main run's 28.6 %. They were never unmatchable —
they were behind NASA-side granule timeouts. That is the whole case for
sweeping, and it is now measured rather than asserted, which is what I promised
in Q9.

**Correction 1 — Q10(a)'s "manifest unchanged" was wrong, and would have cost
~9 hours.** I reasoned that pre-skipping makes everything but the stalled
profiles free. It does not: a profile that came back `unmatched` because no
pixel qualified still has candidate granules, so a bare re-run re-opens them at
full price — ~3,545 profiles, ~10.6 h, against 350 profiles and 67 measured
minutes. The ~1–2 h I quoted belonged to a restricted run I had not actually
specified. I caught it only because I went to extract the stalled ids and had
to think about what the selection would really contain. Using `--profiles-csv`
(the Q5 mechanism) delivered what Q10(a) promised instead of what it said.

**Correction 2 — Q8(a)'s saving was a guess, and the first implementation
barely worked.** I told JXP the layer split would take pushes from ~2.5 GB to
~50 MB. I measured instead of trusting it, and the first build still rebuilt
6.35 GB on a source edit. Chasing why found that **`bing/setup.py:31` declares
`timm==0.3.2`**, which pulls torch and **5.27 GB of NVIDIA CUDA wheels** — on a
cluster with no GPUs, for a package neither `bing/bing/` nor `pab/` imports.
Naming it in layer 1 fixed the caching (rebuilt-on-edit ~7.96 GB → **~934 MB**,
8.5×), and the real residual is 934 MB, not 50 MB. Both numbers are now in the
doc and in the Dockerfile comment, because the wrong one was mine and would
otherwise have been quoted back later.

The general lesson, which is the same one as the match run: **I keep stating
quantities before measuring them.** The stall cost, the sweep duration, the
layer saving — each was asserted first and measured second, and two of the
three were wrong. Measuring first is cheap in all three cases.

**Deliberate deviation from an approved instruction.** Q8(a) proposed, and JXP
approved, `pip install --no-deps` for the local packages. I did not do that:
`bing/setup.py` declares ~25 real dependencies and `--no-deps` would silently
drop any my hand-written layer-1 list missed, surfacing as an ImportError in a
pod hours later. Layer 2 installs *with* deps, so a miss lands in the wrong
layer instead of vanishing. Same saving, no silent-drop mode. Recorded in Q11
rather than done quietly, since it is a departure from what was agreed.

**Q8(b) is the fix for a bug that disguises itself.** A NASA 503 was arriving
as `TypeError: can't pickle multidict...CIMultiDictProxy objects`, because
`aiohttp`'s exception cannot cross a process-pool boundary. `portable_errors()`
flattens only the exceptions that would be destroyed in transit and re-raises
picklable ones unchanged, so `find_matchup`'s `except TimeoutError` still
works. Applied at the granule open *and* the extract, since the extract is
where the lazy HTTP reads actually occur. Six tests, including one asserting
the unpicklable stand-in really is unpicklable — without it the other tests
could silently stop testing anything.

**Q10(c) corrected too:** the sweep hit 5 stalls and still reached its DONE
marker. So the exit hang is not a deterministic result of a stall, as I implied
— it depends on whether `_reclaim_pool` succeeds. An intermittent hang is
harder to diagnose than a reliable one, not easier, because nobody suspects it.

**Blocked, deliberately.** `geometry` needs the Q8(b) fix, so it needs an
image, and the build bakes `PAB_GIT_SHAS` from git. Building from the
uncommitted tree would stamp `dacefa1` — a commit containing none of this — the
same provenance lie that had `:2.0.1` running four-day-old code. Q11 asks for
the commit; Q12 asks whether to delete the 5.3 GB of torch/CUDA outright
(recommendation: the CPU-only torch wheel, since the cluster has no GPU).
Geometry's workload is now exact: **159,760 pixels, none with `theta_s`**.

### 2026-09-28 (Prompt 5 Task 9 — `:2.0.3` shipped; geometry done, 99.97 %; and a 47 h job turned into 20 h by measuring)

Executed Task 9 against JXP's answers to Q11 (*"yes, commit those files"*), Q12
(*"(2)"*, CPU-only torch) and Q13 (*"you run it"*). `git commit` turned out to
be blocked by a permission rule regardless of the verbal go-ahead — `git add`
succeeded, the commit was denied twice, and I stopped rather than looking for a
way around it. JXP made the commit: **`99c37ef`**.

**Q12 delivered more than it promised.** CPU-only torch took the image from
**9.19 GB to 4.43 GB** uncompressed (4,254 → **1,430 MB** compressed) and the
push from **28 min to 6 min**. An unplanned confirmation fell out of it:
`import timm` fails in the new image with `No module named 'torch._six'` — and
fails **identically in `:2.0.2`**. `timm==0.3.2` is from 2021; it has never
imported in any image we have ever shipped. So the 5.3 GB of CUDA it dragged in
was supporting a package that does not work and that nothing imports.

**`:2.0.3` passed both halves of the Q7 check** — baked SHA `99c37ef` == HEAD,
*and* `portable_errors` importable and genuinely used in both
`geometry_for_granule` and `find_matchup`. The SHA is a proxy; the behavioural
probe is the thing that matters, and keeping both is what makes a pass mean
something.

**Geometry: 47 h → 20.9 h, by measuring instead of guessing.** The first pod
gave 13.7 s/granule. Rather than accept it or raise `--jobs` past the CMR
etiquette cap, I split the cost: CMR lookup **0.4–1.4 s (~1 %)**, L1B open
4.7–7.4 s on the workstation. A 1-CPU probe pinned to a California node (which
did not disturb the running job) returned 7.7 s — meaning **one California
worker beat the entire 8-worker South Dakota pod by ~1.8×**. The data is in
us-west-2; the pod was in South Dakota, and its 8 workers were contending for
node bandwidth. Pinned to 193 California nodes, the rate went to 3.2 s/granule.

Finished **159,710 / 159,760 pixels (99.97 %)**, `theta_v` 12.63–**60.0°**,
`dphi` entirely inside (−180, 180], and **0 grid-check mismatches** across
159,710 reads. The 50 missing pixels are 5 matchups whose AOP granules have no
L1B in CMR — proven permanent by two sweeps, the second recovering nothing
(Q16).

**What this run cost: 13 pods and 12 restarts**, because `build_geometry`
builds its pool without `max_tasks_per_child` while `match` sets it precisely
to bound the same growth (Q15). Fix written and tested; not shipped mid-run.

**The failure mode I did not anticipate.** One pod reached the memory ceiling
and **did not die** — 8 full cores of kernel reclaim, memory pinned at 64 Gi,
**no progress for 19 minutes** — because reclaim kept freeing just enough to
starve the OOM killer. A clean OOM self-heals in ~2 min; this state is
unbounded. I had told JXP the `backoffLimit` mitigation made the run safe to
leave unattended, and that is **only true for pods that actually die**. I
killed it by hand, recorded the detection signal (progress staleness + high CPU
+ memory at the limit) in Q15, and built it into the remaining monitors.

**Where I was wrong, again in the same shape.** I called the memory growth a
steady state off two readings, one of them a dip. That is the third time this
run — after "the match rate is degrading monotonically" (four windows; it was
noise around a stable mean) and "stall in-flight counts are growing" (seven
points; the next four killed it). The per-worker RSS series settled it in
seconds once I looked at the right series. **The recurring error is not the
subject, it is reading a trend off a handful of points**, and the fix each time
was a measurement I could have taken first.

I also withdrew two of my own numbers rather than let them stand: the "~50 MB"
layer-split saving (measured: 934 MB) and the "8.5×" (measured on builds that
shared a `PAB_GIT_SHAS`, so it may not survive a real commit — **Q14** proposes
the clean two-build test instead of another assertion).

**One concrete recommendation for the next network-bound stage:** per-node
rates spanned 3.2 s/granule (Fresno) to 8.9 (Humboldt), and Humboldt gave 7.7
with *one* worker versus 8.5 with *eight* — it is bandwidth-limited too, just
less severely. "Pin to California" was right; **"pin to Fresno-class nodes"
would have been better**.
