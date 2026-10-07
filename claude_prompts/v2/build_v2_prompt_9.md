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

### Q1 (Task 1) — confirm the publish + backup plan

Everything below is staged and hashed but **nothing has been sent**. The
working agreement requires each publish/backup step be confirmed.

**(a) S3 → `s3://pab/v2/`** (226 MB, from the workstation). `s3://pab/v2/` is
currently **empty**; `s3://pab/v1/pab.db` exists and is byte-identical to the
frozen workstation copy (`09de0a6d…f978273` — Task 2's check already passes on
the workstation side).

| object | bytes | sha256 |
|---|---|---|
| `v2/pab.db` | 217,325,568 | `7d44e1f3c5a3385ca64af893b0b88661962a7910a8064abb7a297afc0b78bdaf` |
| `v2/matchup_summary.csv` | 6,102,869 | `6622a78cf3061a17bfafa908443c60c428512168ab235eb474e3ad26070f0f74` |
| `v2/matchup_summary.parquet` | 2,645,441 | `4754e2372f4d35918c7f060ea4287f44a89329a01045d24f2f2e6b5fe9c0627c` |

The tables were regenerated on the workstation from the authoritative
`v2/pab.db` (15,971 rows, `pab_version` all `2.0` — the version filter added
in Prompt 8 Task 1 is doing its job here). I will re-download each from the
public URL and re-check sha256 after upload, and check the existing object
before overwriting (the two-machines/one-key lesson).

**Which credential should the S3 push use?** `HOWTO.md` §7b says "the standard
boto3 chain". `~/.aws/credentials` has `default`, `mskelm`, `benpritikin`,
`ceph-s3-large-files`, `swot-user` — none named for `pab`, and I will not
guess which has write access to the public bucket. The `rclone` remote
`nautilus_s3` **does** have working Ceph credentials configured. Options:

- **(i)** `rclone copyto` via the `nautilus_s3` remote (credentials already
  known-good; bypasses `NautilusS3Backend`);
- **(ii)** `NautilusS3Backend` with a named profile — tell me which;
- **(iii)** `NautilusS3Backend` with `AWS_ACCESS_KEY_ID`/`SECRET` exported by
  you into the session.

I'd suggest **(ii) or (iii)**, so the documented code path is the one that
actually publishes — but I need the profile name.

**(b) Off-site backup → `AIOcean:PAB/`** (a Google shared drive, not S3).
`AIOcean:PAB/` currently holds only the v1-era `fit_chains/` and `site/`; there
is **no `v2/` prefix**, so the Prompt 7 optional chains backup was never run.

| item | size | source | how |
|---|---|---|---|
| `pab_v2_2026-10-07.db` | 217 MB | workstation | `rclone copyto`, direct |
| `v2/site/` | 1.1 MB | workstation | `rclone copy`, direct |
| `v2/fit_chains/` | ~18 GB | **PVC only** | needs an in-cluster job |
| `v2/figures/` | ~1 GB (17,361 files) | **PVC only** | needs an in-cluster job |

The chains and figures exist **only on the Nautilus PVC** (the workstation
`fit_chains/` is empty), and PVCs are not backed up — so this is the step that
actually protects 35 h of compute. It needs the 1.0 pattern: a temporary
AIOcean-only secret in the cluster, a `rclone copy` job, secret deleted after.
That means putting a Google Drive credential into the cluster, so I want it
confirmed explicitly and separately from (a).

**Answer (a):**

**Answer (b):**

### Q2 (Task 2) — `wave_max` is 700, not 720

Task 2's gate list says every BING fit should have `wave_max=720`. The actual
run has **`wave_max=700.0`** on all 15,971 2.0 fits — and v1 is also 400–700,
so the window never changed between versions. This is the same discrepancy
found in Prompt 8 Task 2 (the brief's "720 nm" item), and it is the *run* that
is right: Prompt 3 found Rrs(719) negative or noise-dominated on 44 % of a
diagnostic sample, so the red edge was deliberately excluded.

Unless you say otherwise I will verify `wave_max=700.0` and record the
deviation from the brief rather than failing the gate.

**Answer:**

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
