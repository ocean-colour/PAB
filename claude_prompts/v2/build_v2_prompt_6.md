# Build v2 — Prompt 6: the leading slice (go/no-go gate)

## Goals

Fit **100 matchups** under the 2.0 configuration in-pod, measure what the
full send will cost and what the physics change does, and stop for JXP's
review before committing ~16.8k fits (`run_full_inelastic.md` Plan §5
step 6; Q12, R2 c, R4).

## Claude

### Skills

- **`diagnose-mcmc`**, **`debug-priors`** — the first real look at
  6-parameter robust chains at scale.

### Working agreements

As in `build_v2_prompt_1.md`. The slice's 2.0 fits are **real** (they stay
in `/data/v2/pab.db`, idempotently skipped by the full run); the
`B_p`-fixed diagnostic fits go to a **scratch DB copy** and scratch chains,
never to v2. Job launches confirmed with the user.

**Settled in Prompts 1–5 — no longer open:**

- **Image: `:2.0.1` or later, never `:2.0.0`** (whose `figure` stage fails for
  every 2.0 fit). If Prompt 5's `match`-selection change has been committed
  and rebuilt, that is **`:2.0.2`** — check which tag is current before
  writing a manifest.
- **Before launching any job that depends on a recent code change, diff the
  image's baked `PAB` SHA against the commit carrying it.** Prompt 5 Task 4
  lost a job launch to exactly this: the manifest was right, the image was
  four days stale, and the job silently did the unrestricted thing.
  `docker inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' <image>`
  against `git log` is the whole check.
- Every 2.0 job needs **`PYTHONWARNINGS=ignore`** — `robust` emits a
  `DomainWarning` per forward-model call, thousands of lines per fit, and it
  buried a real traceback in the Prompt 4 validation.
- **Tee every job's output to the PVC.** Prompt 5 Task 3's Job and pod were
  gone from the namespace before the results were read; `/data/v2/discover.log`
  was the only surviving record.
- `pab_version` is `"2.0"`; `FitConfig` defaults are the inelastic
  configuration at **400–700 nm** (JXP moved `wave_max` back from 720 after
  the 719 nm band proved negative or noise-dominated on 40 % of matchups —
  Prompt 3 Q2). `FitConfig.v1()` is the frozen 1.0 configuration.
- Test baseline **340 passed, 1 skipped**.

## Context

- Plan §3 (cost), §5 step 6 of `claude_prompts/v2/run_full_inelastic.md`;
  the NASA-GIOP leading-slice pattern in `claude_prompts/pace_giop_gsm.md`
  (Full Run Task 2).
- `nautilus/full_fit_job.yaml` — the **DB-local wrapper** (copy the DB to
  `emptyDir`, run, checkpoint back by local backup + file copy every 2 min;
  never `sqlite3.backup()` onto CephFS). Reuse it; add a slice mechanism —
  the `fit` stage has no `--limit`; either add `--limit N` / `--matchup ID`
  (the long-planned single-matchup targeting) to the CLI, or stage a
  100-matchup selection via a SQL view/temporary table. Pick the least code.
- v1 numbers for the same matchups: `v1/pab.db` (frozen) — read-only
  `ATTACH`.
- Pause triggers agreed in Q12: median s/fit > 4 min; failure rate > 2 %;
  a `b_bp` shift JXP considers implausible.

### Measured facts this prompt should start from (Prompts 3–5)

**The 2.0 fit has already been run on real data** — Prompt 3 Task 6, 20 real
matchups on the workstation, 60/60 fits across three configurations, 0
failures. So the slice is not the first contact with 2.0; it is the first
*in-pod at scale*. What that run measured:

| | median | range |
|---|---:|---|
| **`bbp700` 2.0 / 1.0** | **0.741** | 0.462–1.129 (18 of 20 below 1.0) |
| `bbp700` hybrid / ztt | 0.886 | 0.810–1.230 |
| `Bp` (prior 0.004–0.05) | 0.0250 | 0.0043–0.0410 |
| χ² 2.0 / 1.0 | 0.65 / 0.45 | |
| acceptance 2.0 / 1.0 | ~0.33 / ~0.47 | six parameters vs five |

So **expect ~26 % less `b_bp`(700) than 1.0**, systematically. Against Q12's
"a `b_bp` shift JXP considers implausible" trigger, that is the number
already in hand — the slice's job is to confirm it holds at scale and across
basins, not to discover it.

**`B_p` pins to its lower prior bound on ~15 % of fits** (3 of 20 at
0.0043–0.0057 against a floor of 0.0040). Task 2 asks how often it pins to an
edge; the workstation answer is "the *lower* edge, on a sixth of fits". Worth
watching whether that fraction grows.

**Cost, measured in-pod** (Prompt 4 Task 4, `--jobs 4`, one fit): **~226
s/fit**, against ~101 s uncontended and ~181 s 3-way-contended on the
workstation. Treat 226 s as an **upper bound** — a single fit including JAX's
first compile. Against Q12's "median s/fit > 4 min = 240 s" pause trigger, the
in-pod figure sits *just under* it, so this measurement matters and one fit is
not enough to judge it on. **Chains are ~1.15 MB each** → ~17 GB for a full
send, ~115 MB for the slice.

**Two rate lessons, both learned the hard way in Prompt 5.** Ingest came in
**5× slower** than its pilot figure (11 s/profile against 2.1) because the
bottleneck had moved from local (GIL) to remote (GDAC rate-limiting) without
anything in the repo noticing. Discover came in **2× faster** than my own
early projection, because I sampled the first 100 searches while the thread
pool was still warming. **Take a rate from a few hundred units in, never from
the first fifty, and never from a stale comment.**

**The R4 red-edge check has already been done** (Prompt 3 Task 6) and is what
moved `wave_max` to 700: `Rrs(719)` was **negative on 6 of 20** matchups and
noise-dominated on 2 more — 40 % unusable — and the four worst 2.0 χ² in the
set were exactly the four most negative `Rrs(719)`. Task 2's "per-band
residuals at 713/719 nm plus `Rrs_unc(719)/Rrs(719)`" is now a check on a band
**outside** the fit window; report it as diagnostic, not as a fit residual.

**The v1 comparison needs `create=False`.** `v1/pab.db` is frozen at schema
**v4** and `chmod a-w`; the current `SCHEMA_VERSION` is 5, so a default
`Store.open` tries to migrate it and dies with `attempt to write a readonly
database`. Use `Store.open(..., create=False)` or a read-only URI `ATTACH`.

**Chains land in `$PAB_DATA_DIR/fit_chains/`** — the *root* of `PAB_DATA_DIR`,
not the `--db` directory. `PAB_DATA_DIR=/data/v2` is what puts them in
`/data/v2/fit_chains/`.

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below

## Tasks

1. **Slice selection + mechanism.** Choose 100 matchups stratified by
   basin/season/`theta_v` (include some swath-edge pixels) that have a v1
   fit; implement the slicing mechanism; `nautilus/v2_fit_slice_job.yaml`
   (image **`:2.0.1` or later — never `:2.0.0`**, DB-local wrapper,
   `PAB_DATA_DIR=/data/v2`, `--jobs 32`, 100 Gi). Run it. Log.

   **On the slicing mechanism**, "pick the least code" now has a precedent:
   Prompt 5 Q5 added an explicit-selection parameter to `match` mirroring the
   one `discover` already had, and `PipelineConfig.selection_keys()` +
   `--profiles-csv` is the established seam. `fit` is selected by *matchup*,
   not profile, so it is not a direct reuse — but `--matchup ID` (repeatable),
   which `pab.fit.nasa_giop` already implements as a CLI flag, is the closest
   existing pattern and avoids a SQL view. Note **`fit` does not yet honour
   `--profiles-csv`** either; if you add matchup targeting, say in `HOWTO.md`
   which stages now take a selection, because that row has been wrong twice.

   **Stratify on `theta_v` using real values**: the 200 pixels measured in
   Prompt 2 Task 4 spanned `theta_s` 16.1–42.8°, `theta_v` 22.1–59.7°,
   `dphi` −103.9–81.9°. "Swath-edge" means `theta_v` near 60°, and those
   pixels are where the emulator is furthest from its nadir-only training
   domain — so they are the most interesting, not merely the most extreme.

2. **Measure.** From the pod log + the v2 DB: s/fit (median, p90; and CPU
   time per fit), failure count + causes, χ² and acceptance-fraction
   distributions vs the same matchups' v1 fits, `bbp700(2.0)/bbp700(1.0)`
   and `chl(2.0)/chl(1.0)` distributions, `Bp` posterior medians and widths
   (how often it pins to a prior edge), per-band residuals around 685 nm
   and at 713/719 nm plus `Rrs_unc(719)/Rrs(719)` (R4). Project the full
   send (~16.8k fits, 50 workers) in hours and chain GB. Log.

3. **Attribution (diagnostic).** Fit the same 100 with `fit_Bp=False`
   (`Bp_value=0.01`), otherwise 2.0, on a scratch copy; report how much of
   the `bbp700` shift is the free `B_p` vs the emulator + inelastic terms.
   Write the whole gate under **Reports** with a clear **go / pause**
   recommendation against the Q12 triggers, and **stop — JXP reviews before
   Prompt 7.** Put any questions in Q&A. Log.

4. **Update.** Based on what you have done, update the prompt doc
   `build_v2_prompt_7.md`, as needed. Log.
   *(Added 2026-09-22, mirroring the Task 5 JXP added to
   `build_v2_prompt_1.md`. Delete it if that is not the intent.)*

## Q&A

### Q1 (Task 1, 2026-09-30) — slice is built and staged; needs a **commit + `:2.0.4`** before it can launch, and one open question about `fit`'s worker pool

Task 1 is done except "Run it", which is blocked the same way Prompt 5 Task 4
was — and the pre-launch check caught it rather than the job doing so.

#### The slice: 100 matchups, staged and verified

Eligibility, which needed correcting mid-task: **the v1 BING fits are not in
the v2 store.** `/data/v2/pab.db` carries only the 14,609 `NASA_GIOP` 1.1
fits; the 14,609 `BING` 1.0 fits live solely in the frozen `v1/pab.db`. My
first eligibility query matched `rt_backend IS NULL`, which the NASA_GIOP rows
satisfy, and reported "14,604 with a 1.0 fit" — a **false positive**. The real
join is against the frozen database, which is also what Task 2's comparison
will need.

```
pool: v2 matchups with a rank-1 pixel carrying geometry, no 2.0 fit : 14,604
        ...AND a successful BING 1.0 fit in frozen v1/pab.db        : 14,573
```

Selected 100 (fixed seed 20260930, so it is reproducible):

| stratum | |
|---|---|
| `theta_v` band | 25 / 25 / 25 / 25 across <30, 30–45, 45–55, **≥55 (swath edge)** |
| basin | Pacific 32, Atlantic 19, Indian 17, Southern 16, N-high 16 |
| season | MAM 28, DJF 24, JJA 24, SON 24 |
| `theta_v` | 22.1 – 45.3 – **60.0**; **9 pixels at ≥58°** |
| `theta_s` | 5.1 – 36.7 – 72.7 |

The swath edge is **over-weighted on purpose** — 25 % of the slice against
~11 % of the pool — per Task 1's note that those pixels are where the emulator
is furthest from its nadir-only training domain. Worth flagging that the real
`theta_s` span (5.1–72.7°) is much wider than the 200-pixel sample in Prompt 2
Task 4 suggested (16.1–42.8°), so the slice probes more geometry than that
figure implied.

Staged to `/data/v2/slice_100.csv`, md5 `61e04c7bbb33acbcdc04bdb18ed348ff`,
verified identical on the PVC.

#### The mechanism: `--matchup` / `--matchups-csv`, mirroring Q5

"Pick the least code" pointed at the `match` seam from Prompt 5 Q5, so `fit`
now has the same shape: `PipelineConfig.matchup_ids()` returns
`set[str] | None` (the `None`-vs-empty distinction that keeps a bare
`pab --stage fit` safe), `pipeline.fit()` forwards it, and
`build_fits(selection=...)` filters **before any granule is opened**.
`--matchup ID` is repeatable, mirroring `pab.fit.nasa_giop`; `--matchups-csv`
is its bulk form, because 100 ids on a command line makes an unreadable
manifest.

**8 new tests** (`pab/tests/test_fit_selection.py`), including one asserting
`fit()` actually forwards the selection — the Prompt 5 Task 4 failure was a
flag that existed and was ignored. Suite **356 passed, 1 skipped**.
`HOWTO.md`'s selection row updated (it has been wrong twice): `fit` now takes
a selection, but by **matchup**, not profile.

#### Why it cannot launch yet

```
image :2.0.3 baked PAB : 99c37ef      git HEAD : 7ecafff
build_fits accepts selection : False
PipelineConfig.matchup_ids   : False
```

`:2.0.3` predates the seam. Launching on it would have fitted **the whole
store — 15,976 matchups — instead of 100**, and reported success. That is
precisely the Prompt 5 Task 4 failure, and the **behavioural** probe is what
caught it: the SHA diff only said the image was older, not that the feature
was missing. Keeping both halves of that check earned its keep again.

So it needs: commit → build `:2.0.4` → push → launch.

**Question (a):** commit `pab/pipeline.py`, `pab/fit/run.py`,
`pab/tests/test_fit_selection.py`, `HOWTO.md`,
`nautilus/v2_fit_slice_job.yaml` (and the Dockerfile/doc caveats still
outstanding from Q14/Q16)? Then I build, push and launch.

**Question (b):** confirm the launch — `nautilus/v2_fit_slice_job.yaml`,
`:2.0.4`, `--jobs 32`, 100 Gi, DB-local wrapper, 12 h deadline. Expected
~1–2 h at the Prompt 4 in-pod upper bound of 226 s/fit (100 fits / 32 workers
≈ 4 rounds), ~115 MB of chains.

#### (c) `fit`'s worker pool has no `max_tasks_per_child` either — but the geometry fix does **not** transfer

`pab/fit/run.py:890` builds `ProcessPoolExecutor(max_workers=jobs,
mp_context=ctx, initializer=_worker_init)` — the same gap that cost `geometry`
12 OOM restarts (Q15). I have **not** applied the fix, for a reason worth
stating:

- **The slice cannot detect the problem.** 100 fits over 32 workers is ~3 fits
  per worker; `geometry` needed ~950 per worker before it hit 64 Gi.
- **The fix could be actively harmful here.** Recycling a worker every N tasks
  forces JAX to re-JIT the forward model in the fresh process. Prompt 4's
  226 s/fit is explicitly "including JAX's first compile", so
  `max_tasks_per_child=5` (the value `match` uses) could add that cost to
  **every fifth fit**. For `geometry` a respawn cost ~10–15 s of imports; for
  `fit` it could cost minutes.

So the slice job **samples cgroup memory every 60 s** into
`/data/v2/fit_slice.log`, and Task 2 will report the trend. If memory is flat
across ~3 fits/worker that is weak evidence either way, and the honest answer
for the full send is to size `max_tasks_per_child` from a longer run rather
than copy `match`'s 5. I would rather say that than assume the geometry lesson
generalises.

>A.


## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-30 (Prompt 6 Task 1 — slice selected and staged; mechanism added; launch blocked on a commit)

Built the 100-matchup leading slice, added the `fit`-stage selection seam, and
stopped at "Run it" because the pre-launch check refused the current image.

**A correction I had to make mid-task.** I assumed the v2 store carried the v1
fits, because it has 14,609 of them. It does not — those are **`NASA_GIOP`
1.1** fits; the **`BING` 1.0** fits exist only in the frozen `v1/pab.db`. My
eligibility query tested `rt_backend IS NULL`, which the NASA_GIOP rows
satisfy, so it reported "14,604 matchups with a 1.0 fit" — entirely false
positives. The real pool, joined against the frozen database, is **14,573**.
The number barely moved, which is exactly why the error was easy to miss: a
plausible answer from the wrong query. It also means Task 2's 1.0 comparison
genuinely needs the frozen DB, as the prompt's Context said.

**Selection:** 100 matchups, seed 20260930, stratified 25/25/25/25 across
`theta_v` bands with the **swath edge deliberately over-weighted** (25 % of the
slice against ~11 % of the pool), spanning 5 basins and all 4 seasons.
`theta_v` reaches the full 60.0°, and `theta_s` spans 5.1–72.7° — considerably
wider than the 16.1–42.8° the 200-pixel sample in Prompt 2 Task 4 suggested, so
the slice exercises more of the geometry space than that figure implied.

**Mechanism:** mirrored Prompt 5 Q5's `match` seam rather than inventing one —
`matchup_ids()` returning `set | None`, forwarded by `pipeline.fit()`, filtered
in `build_fits` before any granule opens. `--matchup` repeatable (as
`nasa_giop` already had) plus `--matchups-csv` for the bulk form. 8 tests,
suite **356 passed, 1 skipped**. `HOWTO.md`'s selection row corrected — it has
now been wrong twice, and the fix is to say `fit` selects by *matchup*, not
profile.

**The check earned its keep.** Before launching I ran the two-sided probe:

```
image :2.0.3 baked PAB : 99c37ef      git HEAD : 7ecafff
build_fits accepts selection : False
```

`:2.0.3` predates the seam, so the job would have fitted **all 15,976
matchups instead of 100** and reported success — the Prompt 5 Task 4 failure
exactly. Worth noting *which* half caught it: the SHA diff only said the image
was older, which is true after every commit and easy to wave through. The
**behavioural** probe said the feature was absent. I would not keep the SHA
check alone.

**Flagged, not fixed (Q1c):** `fit`'s pool also lacks `max_tasks_per_child`.
I did **not** copy the geometry fix across, because recycling a worker forces
JAX to re-JIT the forward model — Prompt 4's 226 s/fit is "including JAX's
first compile" — so `match`'s value of 5 could add that to every fifth fit.
And the slice cannot settle it either way: ~3 fits per worker, where geometry
needed ~950 to fail. The job samples cgroup memory every 60 s so Task 2 can
reason from a trace instead of from the assumption that the last stage's lesson
transfers.
