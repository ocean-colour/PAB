# Build v2 — Prompt 9: publish, back up, verify, close out

## Goals

Publish the v2 database and tables, back everything up off-site, verify the
run end to end (including that v1 is byte-identical to its frozen state),
update the documentation, and write the 2.0 run report
(`run_full_inelastic.md` Plan §5 step 10; R8).

## Claude

### Skills

- None specific.

### Working agreements

As in `build_v2_prompt_1.md`. Every publish/backup step is confirmed with
the user; `rclone copy` (never `sync`); dated backup names; check the
published object **before** pushing (the two-machines/one-key lesson,
`HOWTO.md` §7b).

## Context

- Plan §1 (S3/backup layout), §5 step 10 of `claude_prompts/v2/run_full_inelastic.md`.
- `HOWTO.md` §7 (publishing; `NautilusS3Backend`; the merged-DB lesson),
  `docs/design/PAB_implementation.md` (§10/§11 as the model for a new §12),
  `docs/design/PAB_full_run_report.md` (the model for the v2 run report),
  `docs/design/PAB_design.md` (*Provenance & versioning* — add the two-DB
  convention and the "end = today" backfill rule, R5), `docs/db_schema.rst`
  (v5), `ToDo.md`.
- RTD: the `pab-report` project builds `develop`/`latest(main)`; JXP will
  merge `full-inelastic` → `develop` at close-out (R8). Verify
  `/en/develop/` afterwards.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below

## Tasks

1. **Publish + back up.** (a) `v2/pab.db` → `s3://pab/v2/pab.db` and the
   `report` stage's `matchup_summary.{csv,parquet}` → `s3://pab/v2/`
   (`NautilusS3Backend`; re-download + sha256 at the public URL); (b)
   `rclone copy` → `AIOcean:PAB/pab_v2_<date>.db` (+ the v2 chains and
   figures if not already done in Prompt 7, and the v2 `site/`); (c) tell
   the user `report_site/` + the `pab/` changes are ready to commit/push;
   after the `develop` merge, verify the live RTD page shows the 2.0
   headline and the 1.0-vs-2.0 section. Log what went where, with sizes and
   hashes.

2. **Verify.** v1: `v1/pab.db` sha256 == the frozen value (workstation and
   S3 `v1/`). v2: `PRAGMA integrity_check`, `foreign_key_check`; every BING
   `fits` row `pab_version='2.0'` with `rt_backend='robust_hybrid'`,
   `include_raman=1`, `include_chl_fl=1`, `include_cdom_fl=0`, `fit_bp=1`,
   `wave_max=720`; every pixel has geometry; NASA rows = 14,609 + the new
   ones; no duplicate `fit_id`; 11 quantities per BING fit (`…_Bp` added);
   spot-check 4 matchups end to end (chains → figure → page). Report the
   headline science numbers: sat-vs-float `bbp700` and Chl (2.0), 1.0-vs-2.0
   ratios, NASA-vs-2.0. Log.

3. **Docs + report.** `PAB_implementation.md` → new §12 (2.0 run: what
   changed, schema v5, the `geometry` stage, the two-DB layout, fixes made
   along the way); `HOWTO.md` (2.0 defaults, `geometry` stage, `v1/v2`
   paths on workstation/PVC/S3, `--compare-db`); `PAB_design.md`
   (provenance: separate DBs per major version, "end = today" backfill
   rule); `db_schema.rst` (v5); `ToDo.md`. Write
   `docs/design/PAB_v2_run_report.md` (counts, timings per stage, failure
   tails, the slice gate results, the 1.0-vs-2.0 attribution, follow-ups:
   bulk-artifact publish, Zenodo, gap C, CDOM fluorescence). Log.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
