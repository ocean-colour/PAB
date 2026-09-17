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

5. **Geometry for every pixel.** `nautilus/v2_geometry_job.yaml`:
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

**Method note.** Gap B was rebuilt from the live `bgc-s` index (408,062 rows,
loaded in 5 s), token-filtered on `parameters` for `BBP700`/`CHLA` (194,884),
asc/desc-deduped to one row per `(wmo, cycle)` (189,080), cut to
`date > 2026-07-06` (5,206), then deduped against the 54,031 profiles already
in the store (5,187). Gap A is "ingested, no matchup, `time > 2026-06-01`" —
2,409, against the plan's 2,356; the difference is definitional (no *matchup*
versus no *candidate granule*) and A is re-`discover`ed with `--replace`
regardless.


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
