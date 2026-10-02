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

**Settled by the Prompt 6 gate (2026-10-02) — recommendation GO:**

- **164 s/fit** steady state at 32 workers, against Q12's 240 s trigger.
  **Do not quote total-wall ÷ fits**: that gives 385 s/fit and breaches the
  trigger, because it folds in an ~11 min one-time JAX compile amortised over
  only ~3 fits per worker. At ~320 fits/worker here that cost vanishes.
  `build_fits` now logs startup separately for exactly this reason.
- **Failure rate 1 %** (1 of 100, a transient granule open that succeeded on
  the attribution re-run).
- **`bbp700` 2.0/1.0 = 0.7375**, reproducing Prompt 3's 0.741 at 5× the
  sample, 96/99 below 1.0; **0.577 at `theta_v >= 55`** against ~0.78
  elsewhere. The attribution run showed this is the **emulator**, not the free
  `B_p`: fixing `B_p` gives 0.7363, i.e. the free parameter moves `bbp700` by
  **0.5 %**.
- **Projection: 14.7 h at 50 workers** (22.9 h at 32), **~19 GB** of chains.

**Image: `:2.0.4` or later.** `:2.0.4` is PAB `2da2e09`. The `build_fits`
progress/timing logging landed *after* it, so this prompt needs a newer build
to get it — see Task 1.

**Two pre-launch checks, both of which have now caught a real error:**

1. Diff the image's baked `PAB` SHA against the commit carrying the change,
   **and** probe the behaviour. The SHA alone only says "older", which is true
   after every commit; the behavioural probe is what caught `:2.0.3` lacking
   the `--matchups-csv` seam.
2. **Assert the manifest points at the image you verified.** In Prompt 6 I
   verified `:2.0.4` exhaustively and then launched a manifest still naming
   `:2.0.3`. "Is the image right?" is not "does the manifest reference it?",
   and the latter is what cost Prompt 5 Task 4 a job launch.

## Context

- Plan §3 (cost), §5 of `claude_prompts/v2/run_full_inelastic.md`; the
  Prompt 6 **Reports** (measured s/fit). Plan §3's ~16.8 k is stale — the store
  holds **15,976** matchups, of which **99 already have a 2.0 fit** (the
  Prompt 6 slice, idempotently skipped) and **5 have no geometry and will be
  refused by R3** (Prompt 5 Q16, answer (1): skip them). So expect
  **~15,872** fits to attempt.
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
4. Execute the 4th task in Tasks below

## Tasks

1. **Full fit.** `nautilus/v2_fit_job.yaml` from `full_fit_job.yaml`
   (image **`:2.0.4` or later — never `:2.0.0`**, `PAB_DATA_DIR=/data/v2`,
   DB-local wrapper, chains → `/data/v2/fit_chains`, `--stage fit --jobs 50`,
   100 Gi, `backoffLimit 4`).

   **Build a fresh image first.** The `build_fits` progress + per-fit timing
   added after Q2c is not in `:2.0.4`, and a 15-23 h run that logs nothing is
   undiagnosable while it runs — which is precisely when diagnosis matters.
   Prompt 6's slice had to have its s/fit reconstructed from `created`
   timestamps afterwards.

   **Decide `max_tasks_per_child` from this run's own trace, not by copying.**
   `fit`'s pool still has none (Prompt 6 Q1c). `geometry` lacked the same guard
   and OOM-restarted 12 times; `match` has had it since the 1.0 run. But the
   geometry value (5) does **not** transfer: recycling a worker re-pays the JAX
   compile, measured at ~11 min per pool in the slice, so a low value could cost
   far more than it saves. The slice could not settle it either — ~3 fits per
   worker, where geometry needed ~950 to fail — though memory did climb
   0.3 → 20.0 GB in 21 min **without plateauing**. `build_fits` now logs
   `mem_breakdown()` on every progress line: watch it, and only then size the
   recycle interval (or confirm none is needed).
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

4. **R4 band diagnostics (deferred from Prompt 6, Q2b).** Per-band residuals
   around 685 nm and at 713/719 nm, plus `Rrs_unc(719)/Rrs(719)`, over a
   sample of the completed 2.0 fits. These need the observed granule spectra
   **and** a reconstructed fit (`pab.fit.run.reconstruct_rrs`), i.e. a
   granule-reading pass — the slice job did not retain the spectra, which is
   why it was deferred rather than estimated.

   Report it as a **diagnostic, not a fit residual**: 713/719 nm are outside
   the 400-700 fit window, which is where JXP moved `wave_max` after Prompt 3
   found `Rrs(719)` negative on 6 of 20 matchups and noise-dominated on 2 more.
   The question this answers is whether excluding the red edge was right, not
   whether the fits are good there. Cheapest honest version: run it on the
   Prompt 6 slice's 100 matchups rather than all ~16k.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
