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

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below

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
   `full_ingest_job.yaml`; image `:2.0.0`; `--db /data/v2/pab.db
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
   `--stage geometry --jobs 16` over the whole v2 DB (~13.5k unique L1B
   opens: 11,494 existing granules + the backfill's). Gates: every
   `matchup_pixels` row has `theta_s`; failures listed with causes (an L1B
   missing from CMR, grid-check failures) and a sweep re-run; `theta_v`
   distribution spans 0–~60°. Log s/granule and wall-clock; **update the
   fit-cost projection** in Plan §3 from Prompt 4's in-pod s/fit.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
