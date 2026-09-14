# Build v2 — Prompt 7: the full 2.0 fit, DB return, NASA-GIOP for the new matchups

## Goals

Fit every matchup in v2 under 2.0 on Nautilus, bring the database back to
the workstation, and add the NASA-GIOP baseline for the backfilled
matchups (`run_full_inelastic.md` Plan §5 steps 7–8; R6).

## Claude

### Skills

- **`batch-fit-argo`** (resume/checkpoint), **`diagnose-mcmc`** for
  stragglers.

### Working agreements

As in `build_v2_prompt_1.md`. Only proceed once JXP has signed off on the
Prompt 6 gate (record the sign-off date in the log). Job launch confirmed.

## Context

- Plan §3 (cost), §5 of `claude_prompts/v2/run_full_inelastic.md`; the
  Prompt 6 **Reports** (measured s/fit).
- `nautilus/full_fit_job.yaml` (DB-local wrapper; `--jobs 32`/64 Gi in 1.0 —
  raise memory to **100 Gi** for JAX workers, `--jobs 50` if the node
  schedules); the CephFS playbook in `claude_prompts/nautilus_prompts.md`
  (state `D` on `ceph_mdsc_wait_request` → force-delete, resume).
- NASA-GIOP driver: `python -m pab.fit.nasa_giop --db … --cache-dir …
  --log-file …` (`HOWTO.md` §4; idempotent by `matchup_id`; ~4 s/matchup;
  ~47 MB/IOP granule; restricted to matchups with a completed BING fit —
  check that filter still finds the **2.0** fits, i.e. it keys on
  `algorithm='BING'`, not on `pab_version`).

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below

## Tasks

1. **Full fit.** `nautilus/v2_fit_job.yaml` from `full_fit_job.yaml`
   (image `:2.0.0`, `PAB_DATA_DIR=/data/v2`, DB-local wrapper, chains →
   `/data/v2/fit_chains`, `--stage fit --jobs 50`, 100 Gi, `backoffLimit 4`).
   Monitor: fits/min, checkpoint markers, PVC usage, pod state. Sweep the
   failure tail with a resume until stable; list irreducible failures with
   causes. Close-out: `fits` count `algorithm='BING'` ≈ matchups − failures,
   all `pab_version='2.0'`, all with the v5 columns filled; NASA rows
   unchanged (14,609); no duplicate `fit_id`; chains GB. Log wall-clock.

2. **DB return.** Copy `/data/v2/pab.db` → workstation `$PAB_DATA_DIR/v2/
   pab.db` (sha both ends; the workstation copy becomes writable again —
   the PVC copy is now the stale one; say so in `HOWTO.md`). Also copy the
   run logs. Optionally start `rclone copy` of `/data/v2/fit_chains` →
   `AIOcean:PAB/v2/fit_chains/` in-cluster (the 1.0 pattern: temporary
   AIOcean-only secret, deleted after) — confirm first. Log.

3. **NASA-GIOP for the new matchups (workstation).** `python -m
   pab.fit.nasa_giop --db $PAB_DATA_DIR/v2/pab.db --cache-dir
   $PAB_DATA_DIR/v2/iop_granules --log-file …`; the 14,609 existing rows
   skip; ~2.2k written at ~4 s each, stamped `1.1` (same product, same
   code — R6). Gates: pixel distance 0.0000 km for all; sweep transients;
   delete the ~100 GB cache. Close-out counts. Log.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
