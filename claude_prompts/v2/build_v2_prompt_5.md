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

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
