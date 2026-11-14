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

### Task 1 — the full 2.0 fit (2026-10-02/03): **done — 15,779 fits, every close-out gate passes**

Launched 01:18 UTC 2026-10-02 on `:2.0.5` (PAB `69efcd4`), `--jobs 50`, 100 Gi,
DB-local wrapper. `V2_FIT_DONE` 12:56 UTC 2026-10-03 — **~35 h**.

#### Close-out gates — all pass

```
counts: matchups 15,976 | fits 30,388 | 2.0 fits 15,779 | NASA 14,609

2.0 fits                     15,779
all pab_version='2.0'        15,779
NASA rows (must be 14,609)   14,609     <- untouched
duplicate fit_ids                 0
v5 columns unfilled               0     <- must be 0
chains                       15,779 files, 19 GB
```

The chain count equals the fit count exactly, and 19 GB lands on the ~19 GB
projection. **15,779 of 15,872 attempted = 99.4 %.**

#### Sweeps: the tail is 100 % transient except the 5 permanent refusals

`fit` is idempotent on `fit_id`, so a re-run attempts only what is missing.

| pass | 2.0 fits | recovered | remaining |
|---|---:|---:|---:|
| main run | 15,779 | — | 197 |
| sweep 1 | 15,967 | **+188** | 9 |
| sweep 2 | **15,971** | **+4** | **5** |

**15,971 of 15,976 = 99.97 %.** The only irreducible failures are the **5
matchups with no viewing geometry** — the Q16 five, whose AOP granules have no
co-temporal L1B in CMR — correctly refused by R3 with a clear message rather
than fitted on an assumed solar angle.

**Every granule-open failure was transient: 192 of 192 eventually succeeded.**
After sweep 1 the 4 survivors came from just *two* granules
(`PACE_OCI.20250713T121339` failing a group of 3, and
`PACE_OCI.20260505T024912`), and having failed twice I suspected they were
permanently unavailable. They opened on the third attempt. Worth recording
because the opposite inference — "failed twice, therefore permanent" — is what
the geometry sweeps *did* establish for the missing-L1B cases, and the
distinction is the error class, not the repeat count: `FileNotFoundError` from
CMR is permanent, a granule-open timeout is not.

#### Failures in the main run: 197 (1.24 %), under the 2 % trigger

| cause | count |
|---|---:|
| `open_granule failed` | 168 log lines (~191 fits — one failure fails a whole group) |
| `no viewing geometry` | **5** — the expected R3 refusals (Prompt 5 Q16) |
| `extract_spectrum failed` | 1 |
| worker / persist | **0** |

The dominant cause is transient granule opens, the same class the Prompt 5
sweeps recovered. Zero worker or persist failures across 15,779 fits is the
reassuring number — the MCMC itself never failed.

#### Cost: my sizing was wrong, and the reason is worth keeping

| estimate | basis | value |
|---|---|---:|
| Prompt 6 gate | 164 s/fit at **32** workers | 14.7 h |
| after 200 fits | 303 s/fit marginal | 26.7 h |
| **actual** | | **~35 h** |

The rate degraded steadily through the run:

```
fits   elapsed h   marginal s/fit wall   median   cgroup   parent
 2050       3.9          7.00             496     42.8     20.4
 6050      11.7          7.07             495     42.9     20.4
10050      20.4          7.72             508     43.2     20.5
14050      31.2          9.92             523     43.3     20.5
15650      35.4          9.59             526     43.3     20.5
```

**The root error: I assumed per-fit cost is independent of worker count.** The
slice measured **165 s/fit of worker time at 32 workers**; this run averaged
roughly **410 s/fit at 50**. More workers bought substantially less than
proportionally more throughput — memory bandwidth and cache contention, most
likely, since the MCMC is CPU-bound and the box was CPU-saturated (49-53 cores
of a 50-core request throughout).

**For Prompt 8 sizing: `--jobs 50` was probably the wrong call.** At 165 s/fit,
32 workers would give 15,872 × 165 / 32 ≈ 22.7 h — *better* than the 35 h this
took, on fewer resources. The 50-worker configuration was chosen from Plan §3
and never validated; the slice had measured only 32.

A second contributor is that the rate also degraded *within* the 50-worker
configuration (7.0 → 9.6 s/fit, ~37 % slower by the end) with memory flat, so
contention alone does not explain all of it. Worth a look before the next long
fit run, but not worth re-running this one.

#### `max_tasks_per_child`: settled — `fit` does **not** need it (closes Prompt 6 Q1c)

```
fits        cgroup GB   parent GB   kids
 2,050        42.8        20.4      51
15,650        43.3        20.5      51
```

**Flat across 15,650 fits — ~315 per worker.** `geometry` needed ~950 per worker
to reach 64 Gi and OOM-restarted 12 times; `fit` is stable at 43 GB of a 100 Gi
limit for 35 h. So the guard that was essential for `geometry` is unnecessary
here, and copying it would have re-paid the ~8-11 min JAX compile for nothing.

This is the question the Prompt 6 slice explicitly could **not** answer (~3 fits
per worker, where the failure mode needs hundreds). It is now answered from a
run that actually exercises the regime, which is why it was worth deferring
rather than guessing.

**A correction made mid-run:** at 6,250 fits I flagged the parent growing
~2.3 MB/fit and projected ~87 GB at completion. That extrapolation was drawn
from two points during startup accumulation. The parent plateaued at 20.4 GB
and never moved again. Same error shape as the earlier ones in this project —
a trend read off too few points — caught within 30 minutes this time.

#### Instrumentation: the logging added in Prompt 6 earned its place, with one flaw

`fit: first result after 493.7 s (worker spawn + JAX compile)` separated
startup from per-fit cost exactly as intended, and `mem_breakdown()` on every
progress line is what settled `max_tasks_per_child`.

**The flaw:** the `median s/fit` figure starts its timer when a fit is
*submitted* to the pool, not when a worker picks it up. With ~100 futures in
flight the queue wait is included, so the median reads 490-526 s against a true
per-fit cost nearer 410 s, and it drifts upward as the queue deepens. The
**marginal wall rate** is the trustworthy number. Worth fixing before the next
run: time from first execution, not from submission.


### Task 2 — DB return (2026-10-03): **done — byte-identical, verified three ways**

`/data/v2/pab.db` returned to `$PAB_DATA_DIR/v2/pab.db`.

| check | result |
|---|---|
| sha256 both ends | `eb9a341aa6561fbef2169496997428c55e8700351fd30b33dc610969e2253542` — **match** |
| size | 207,638,528 B both ends |
| `PRAGMA integrity_check` | ok |
| contents | 15,971 2.0 fits, 14,609 NASA rows, 15,976 matchups, 159,710 pixels with geometry |

**Transfer it compressed.** The first attempt — `kubectl cp` of the raw 207 MB
in one stream — died at 36.9 MB on a dropped link and left a `pab.db` that
sqlite reports as `database disk image is malformed`. `kubectl cp` has no
resume, so a drop at any point costs the whole transfer. `gzip -c` in-pod gives
**40.3 MB (5.1x)** which transferred in **3.7 s**, and `gzip -t` adds an
integrity check independent of the sha.

I removed the truncated file rather than leave it: a corrupt database at the
canonical path is worse than no database.

**The destination was checked before overwriting.** There was already a
`v2/pab.db` there — the 2026-09-14 pre-backfill seed (14,610 matchups, 0 2.0
fits). Strictly superseded, but renamed to `pab_pre_backfill_2026-09-14.db`
rather than overwritten.

**`HOWTO.md` updated** with which copy is authoritative: the workstation copy is
now live and writable, and **the PVC copy is stale from here on** — it does not
have the NASA-GIOP rows Task 3 wrote locally. Chains stay on the PVC (15,971
files, 19 GB). All ten run logs copied to `$PAB_DATA_DIR/v2/logs/`.


### Task 3 — NASA-GIOP for the backfilled matchups (2026-10-03/04): **done — 1,367 rows; one defect found and fixed**

```
nasa-giop done: written 1,367, skipped 14,604, failed 0
                in 5,161 s (3.78 s/matchup)
```

#### Close-out

| | |
|---|---:|
| matchups | 15,976 |
| BING 2.0 fits | 15,971 — all `pab_version='2.0'` |
| NASA_GIOP rows | **15,976** — all `pab_version='1.1'` |
| matchups with a BING fit but no NASA row | **0** |
| duplicate `fit_id` | 0 |
| `PRAGMA integrity_check` | ok |
| **gate: NASA pixel ≠ BING pixel** | **0 of 1,367** — every distance 0.0000 km |
| cache | 41 GB / 1,020 granules, deleted after verifying the values are in `fit_results` (127,808 rows) |

**The counts differ from my prediction (1,362 / 14,609) and the reason is
benign:** the **5 geometry-less matchups** have NASA rows from v1 but no BING
fit, so they are excluded from the driver's `algorithm='BING'` join and counted
as neither written nor skipped. 14,604 + 1,367 = 15,971 = the BING fit count,
and all 15,976 matchups end up with a NASA row.

#### The defect: 1,367 rows stamped with the *pipeline* version

The new rows came out as `pab_version='2.0'`. Task 3 states they must be
**`1.1`** — "same product, same code — R6".

**Root cause:** `nasa_giop.py` passed `pab_version=config.pab_version`, the
*pipeline* version, and had no flag to override it. That global read `1.1`
during the v1 run and `2.0` now, so an unchanged product was relabelled purely
because PAB's own version had moved.

**Why it matters:** the database would have held one NASA-GIOP product under
**two version labels**, making "select the NASA-GIOP baseline" ambiguous for
anyone downstream — the kind of metadata inconsistency that stays invisible
until somebody trusts it.

**Corrected:** the 1,367 rows updated to `1.1` (snapshot
`pab_pre_nasagiop_20261003.db` taken before the run; BING fits verified
untouched at 15,971 × `2.0`; integrity `ok`).

**Fixed in code so it cannot recur:** `PRODUCT_VERSION = "1.1"` as a module
constant with the reasoning attached, a `--pab-version` flag defaulting to it,
and the driver now passes `args.pab_version`. **3 new tests**
(`test_nasa_giop_version.py`), verified load-bearing — restoring
`config.pab_version` makes one fail.

#### The existing test was pinning the bug

`test_main_runs_and_resumes` asserted

```python
assert row["pab_version"] == config.pab_version
```

which is the defect written down as a requirement. It passed for the whole v1
run only because `config.pab_version` *was* `1.1` then — accidentally correct.
Once PAB moved to 2.0 it began asserting the wrong behaviour, and it would have
**failed anyone who fixed the bug**. Corrected to pin `PRODUCT_VERSION`.

Worth recording as a class of problem: a test that compares two values which
*happen* to be equal is indistinguishable from one that checks the right thing,
until they diverge. The new test asserts `PRODUCT_VERSION != pab_version`
explicitly, so it fails loudly if they ever converge again and it silently
stops testing anything.

Suite **361 passed, 1 skipped**.


### Task 4 — R4 red-edge diagnostics (2026-10-04): **done — excluding the red edge was right, confirmed at 5x the sample**

Deferred from Prompt 6 Q2b. Run on the Prompt 6 slice's 100 matchups; 97 read
successfully, 3 failed as clean `TimeoutError`s.

**Observed** `Rrs` and `Rrs_unc` only — no model reconstruction. 713 and 719 nm
are **outside** the 400-700 fit window, so a "residual" there would extrapolate
the model beyond where it was fitted, which measures the extrapolation rather
than the data. The question R4 actually asks — *was excluding the red edge
right?* — is answered by the observations alone.

| band | median `Rrs` | median `unc/Rrs` | negative | `unc` > signal | **unusable** |
|---|---:|---:|---:|---:|---:|
| 685 nm (inside window) | 2.62e-04 | 0.40 | 0/97 | 2/97 | **2 %** |
| 713 nm (outside) | 1.74e-04 | 0.33 | 3/97 | 8/97 | **11 %** |
| **719 nm (outside)** | 7.20e-05 | 0.34 | **29/97 (30 %)** | 14/96 | **44 %** |

**Prompt 3 measured 40 % unusable at 719 nm on 20 matchups** (6 negative, 2
noise-dominated), and that is what moved `wave_max` from 720 to 700. At 97
matchups: **44 % unusable, with the negative fraction reproducing exactly at
30 %.** The small-sample figure held — unlike Prompt 3's chi-squared and `B_p`
edge-pinning numbers, which did not survive the larger sample. Parameter-level
and data-quality measurements generalised from n=20; goodness-of-fit summaries
did not.

**685 nm is clean at 2 % unusable**, so this is specifically a red-edge problem,
not a gradual degradation toward longer wavelengths. The fit window excludes
exactly the bands that needed excluding and keeps the ones that did not.

**Conclusion: `wave_max = 700` is correct and the decision is now supported by
~5x the evidence it was originally made on.**

#### Two mistakes of mine in getting here

1. **The first attempt wedged indefinitely.** I called `cloud.open_granule`
   directly, without the `_open_with_timeout` SIGALRM guard that `match` and
   `fit` both use — the guard exists precisely because `fsspec`/`aiohttp` have
   no read timeout on this path. It hung on one granule for 30 min. Rerun with
   `timeout_s=90`: the 3 failures came back as clean `TimeoutError`s instead.
2. **It produced a 0-byte log for those 30 minutes**, because I let Python
   block-buffer stdout. I had written in the Task 1 report that "a 15-23 h run
   that logs nothing is undiagnosable while it runs", and then built the same
   flaw into my own script twenty minutes later. Fixed with `-u` and
   `flush=True`.

Script kept at `nautilus/r4_diagnostics.py`; per-matchup values in
`$PAB_DATA_DIR/v2/logs/r4_diagnostics.csv`.


## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-10-03 (Prompt 7 Task 1 — full 2.0 fit: 15,779 fits in ~35 h; sizing lesson and a settled question)

The full send completed: **15,779 2.0 fits**, 99.4 % of the 15,872 attempted,
every close-out gate passing — all stamped `pab_version='2.0'`, NASA's 14,609
rows untouched, no duplicate `fit_id`, no unfilled v5 columns, 15,779 chains at
19 GB (exactly the projection).

**197 failures (1.24 %)**, under the trigger, and overwhelmingly transient
granule opens. **Zero worker or persist failures across 15,779 MCMC runs** —
the fit machinery itself never failed once, which is the number I would have
been most worried about going in.

**My cost estimate was wrong by 2.4×, and the reason matters for Prompt 8.** The
Prompt 6 gate measured 164 s/fit at **32** workers and I projected 14.7 h at 50.
Actual: ~35 h, i.e. roughly **410 s/fit at 50 workers**. I had assumed per-fit
cost is independent of worker count; it is not. More workers bought far less
than proportionally more throughput on a CPU-saturated box. At the measured
32-worker rate, `--jobs 32` would have finished in ~22.7 h — **faster than 50
workers, on fewer resources**. The 50 came from Plan §3 and was never validated
against a measurement; the only measurement in hand was at 32.

**`max_tasks_per_child` is settled, and the answer is no.** Memory was flat for
35 h — cgroup 42.8 → 43.3 GB, parent 20.4 → 20.5, workers steady — across
~315 fits per worker. `geometry` needed ~950 per worker to OOM; `fit` never
approaches it. Copying geometry's fix would have re-paid an 8-11 min JAX
compile repeatedly for no benefit. This is exactly the question the Prompt 6
slice could not answer at ~3 fits per worker, and deferring it to a run that
exercises the regime was the right call.

**One mid-run correction.** At 6,250 fits I flagged the parent growing
~2.3 MB/fit and projected ~87 GB at completion against a 100 Gi limit. Wrong:
that was startup accumulation seen from two points, and it plateaued
immediately after. Same error shape as several earlier in this project —
reading a trend off too few samples — but caught and corrected within half an
hour rather than left standing.

**The Prompt 6 logging earned its place and showed one flaw.** Separating
startup (`first result after 493.7 s`) from per-fit cost worked, and
`mem_breakdown()` on every progress line is what settled the pool question.
But the `median s/fit` timer starts at *submission*, not execution, so with
~100 futures in flight it includes queue wait — reading 490-526 s against a
true ~410 s and drifting upward as the queue deepens. The marginal wall rate is
the number to trust. Fix before the next run: time from first execution.

**Next:** sweep the 197 failures (idempotent — a resume retries only those),
then Task 2's database return.

### 2026-10-03 (Prompt 7 Task 1 sweeps — 15,971 / 15,976 = 99.97 %; the tail is fully explained)

Two resume sweeps closed the failure tail. `fit` skips completed `fit_id`s, so
each pass attempted only what was missing: 192, then 9.

```
main run  15,779        197 failed
sweep 1   15,967  +188    9 remaining
sweep 2   15,971    +4    5 remaining
```

**Every one of the 192 granule-open failures eventually succeeded.** The only
irreducible failures are the **5 with no viewing geometry** — the Q16 five,
refused by R3 rather than fitted on an assumed solar angle, which is the
behaviour JXP chose in answer (1).

**I called the last four wrong, and the reason is worth keeping.** After sweep 1
the survivors came from just two granules, each failing its whole group. Having
failed in the main run *and* in sweep 1, I said that if sweep 2 recovered
nothing they were "genuinely unavailable rather than transient". Sweep 2
recovered all four. The inference I was reaching for — "failed twice, therefore
permanent" — is the one the *geometry* sweeps established, but there the
failures were `FileNotFoundError` from CMR, which is a statement about what
exists. A granule-open timeout is a statement about one moment's network. **The
discriminator is the error class, not the repeat count**, and I had been
treating repeat count as the evidence.

### 2026-10-03 (Prompt 7 Task 2 — DB return: verified byte-identical, after one failed attempt)

`/data/v2/pab.db` is back on the workstation and verified at three levels: the
**sha256 matches byte-for-byte**
(`eb9a341aa6561fbef2169496997428c55e8700351fd30b33dc610969e2253542`,
207,638,528 B), `PRAGMA integrity_check` returns `ok`, and the contents are what
Task 1 produced — 15,971 2.0 fits, 14,609 NASA rows, 15,976 matchups, 159,710
pixels with geometry.

**The first attempt failed and left a corrupt file at the canonical path.**
`kubectl cp` of the 207 MB database in a single stream has no resume; the link
dropped at 36.9 MB and what remained was a `pab.db` that sqlite reports as
`database disk image is malformed`. I removed it — a corrupt file where the
real one belongs is worse than no file.

**The fix was to compress first**: `gzip -c` in-pod gives 40.3 MB (5.1x), which
transferred in **3.7 s** against the minute the uncompressed attempt burned
before timing out. Smaller exposure, and `gzip -t` adds an integrity check
independent of the sha. Recorded in `HOWTO.md` so the next person does not
repeat the slow way.

**Checked the destination before overwriting it.** There was already a
`v2/pab.db` on the workstation — the 2026-09-14 pre-backfill seed, 14,610
matchups and 0 2.0 fits. Strictly superseded, but I renamed it to
`pab_pre_backfill_2026-09-14.db` rather than overwrite. It costs 120 MB and
removes any question about what was lost.

**`HOWTO.md` updated** with which copy is authoritative: the workstation copy is
now live and writable, and **the PVC copy is stale from here on** — it will not
see the NASA-GIOP rows Task 3 writes locally. The chains stay on the PVC (15,971
files, 19 GB); only the database came back. All ten run logs copied to
`$PAB_DATA_DIR/v2/logs/`.

### 2026-10-04 (Prompt 7 Task 3 — NASA-GIOP: 1,367 rows, and a version-stamp defect that a test was protecting)

1,367 NASA-GIOP rows ingested in 86 min at 3.78 s/matchup, 0 failures. Every
matchup with a BING fit now has a NASA row, and the **0.0000 km gate held on all
1,367** — the NASA pixel is the BING pixel in every case, which is the one
correctness check this task really turns on. 41 GB cache deleted after
confirming the values are in `fit_results`.

**The counts were not what I predicted** (1,367/14,604 against 1,362/14,609) and
chasing the difference was worthwhile: the 5 geometry-less matchups carry NASA
rows from v1 but have no BING fit, so the driver's `algorithm='BING'` join
excludes them entirely — neither written nor skipped. The arithmetic closes
exactly once that is understood.

**The defect: 1,367 rows stamped `2.0` instead of `1.1`.** The driver passed
`pab_version=config.pab_version` — the *pipeline* version — with no way to
override it. That global was `1.1` during the v1 run and `2.0` now, so an
unchanged product got relabelled because PAB's version had moved underneath it.
Left alone the database would have carried one NASA-GIOP product under two
labels, and "select the NASA-GIOP baseline" would have been ambiguous. Task 3
states plainly that these should be `1.1` ("same product, same code — R6"), so
I corrected the rows and fixed the code: `PRODUCT_VERSION = "1.1"`, a
`--pab-version` flag defaulting to it, 3 tests verified load-bearing.

**The part worth remembering is that a test was holding the bug in place.**
`test_main_runs_and_resumes` asserted
`row["pab_version"] == config.pab_version`. That is the defect written down as
a requirement. It passed for the entire v1 run because the two values happened
to be equal then — so it looked like a check and was actually a tautology. The
moment PAB moved to 2.0 it started asserting the wrong thing, and it would have
failed anyone who fixed the bug rather than alerting them to it.

A test comparing two values that *happen* to coincide is indistinguishable from
a real check until they diverge. The replacement asserts
`PRODUCT_VERSION != pab_version` explicitly, so if they ever converge again the
test says so instead of quietly ceasing to test anything.

Suite **361 passed, 1 skipped**.

### 2026-10-04 (Prompt 7 Task 4 — R4: the red edge is as bad as Prompt 3 said, at 5x the sample)

Ran the deferred R4 diagnostics on the Prompt 6 slice's 100 matchups; 97 read,
3 timed out cleanly.

**The result vindicates `wave_max = 700` with more evidence than the original
decision had.** Prompt 3 measured 40 % unusable at 719 nm on 20 matchups (6
negative, 2 noise-dominated) and that is why JXP moved the window. At 97
matchups: **44 % unusable, negative on exactly 30 %** — the same number.
713 nm is 11 % unusable; **685 nm, inside the window, is 2 %**. So the problem
is the red edge specifically, not a gradual decline toward longer wavelengths,
and the fit window excludes precisely the bands that needed excluding.

**Worth noting which Prompt 3 numbers generalised and which did not.** The
red-edge data-quality figure held almost exactly (40 % → 44 %), as did
`bbp700` 2.0/1.0 (0.741 → 0.7375) and acceptance. What did *not* hold were the
goodness-of-fit summaries — chi-squared flipped from 2.0 being worse to
marginally better, and `B_p` prior-edge pinning fell from 15 % to 2 %. At n=20,
measurements *of the data* were reliable and measurements *of how well the
model fits it* were not.

**I measured observations only, not residuals**, and that was a deliberate
choice: 713/719 are outside the 400-700 fit window, so a "residual" there
measures how the model extrapolates rather than whether the band is usable. The
question R4 asks is the latter.

**Two self-inflicted problems getting there, both from ignoring lessons already
in this codebase.** The first attempt called `cloud.open_granule` without the
`_open_with_timeout` SIGALRM guard that `match` and `fit` use — the guard
exists *because* fsspec/aiohttp have no read timeout — and it wedged on one
granule for 30 minutes. It also produced a **0-byte log** for that entire time
because I let Python block-buffer stdout, twenty minutes after writing in the
Task 1 report that a long run which logs nothing is undiagnosable. Both fixed:
`timeout_s=90` turned the hangs into clean `TimeoutError`s, and `-u` plus
`flush=True` made progress visible.

I also hit the `pgrep -f` self-match trap again while trying to confirm the
wedged process was dead — the pattern matches the checking shell's own command
line. `ps -eo pid=,args= | grep "[r]4_..."` is the form that does not lie.
