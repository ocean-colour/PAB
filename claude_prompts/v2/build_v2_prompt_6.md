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


### Q2 (Tasks 2/3, 2026-10-01) — confirm the `B_p` attribution launch; plus two gaps I am not papering over

Tasks 1 and 2 are done and written up. Both Q12 pause triggers are clear
(**1 % failures**, **164 s/fit**) and `bbp700` 2.0/1.0 reproduces Prompt 3
almost exactly (**0.7375** against 0.741). The new result is that the shift is
**swath-edge dependent**: 0.577 at `theta_v ≥ 55` against ~0.78 elsewhere.

#### (a) Launch the `B_p` attribution run?

`nautilus/v2_bp_attribution_job.yaml` + `nautilus/v2_bp_attribution.py` are
written and validated.

| | |
|---|---|
| image | `:2.0.4` (PAB `2da2e09`) — manifest asserted against the verified image |
| config | `FitConfig(fit_Bp=False)`, `Bp_value=0.01`, otherwise 2.0 |
| selection | the same 100 matchups, `/data/v2/slice_100.csv` |
| database | **scratch copy** at `/scratch/pab_bpfix.db` |
| chains | `PAB_DATA_DIR=/scratch` → `/scratch/fit_chains`, **not** v2's |
| writes to the PVC | one new file, `/data/v2/bp_attribution.csv`, plus a log |
| est. | ~25 min (164 s/fit × 100 ÷ 32 + ~11 min JAX compile); 2 h deadline |

**Why the scratch copy is not optional, concretely.** `make_fit_id` is
`{matchup}_{ix}_{iy}_{model_pair}_v{version}` and does **not** encode
`fit_Bp`. So a B_p-fixed fit has the *same* fit_id as the free-B_p fit already
stored: without `replace=True` every matchup is skipped as "already done", and
**with** `replace=True` against the real store it would overwrite the 99 real
2.0 fits with diagnostic ones. On a scratch copy that is harmless. The script
refuses to start unless `SCRATCH_DB` is under `/scratch` and `PAB_DATA_DIR` is
not `/data/v2`, and the job re-checks v2's fit counts afterwards.

*My recommendation: yes.* It is the last measurement the go/no-go gate needs,
and it answers a question the slice raised rather than confirming something
already known — Task 2 found `B_p` has **no** `theta_v` dependence (medians
0.0218–0.0263 across the four bands), which suggests the swath-edge `bbp700`
shift is the emulator rather than `B_p` absorbing geometry. This run tests that
directly instead of leaving it as an inference.

#### (b) R4 band residuals — deferred, not estimated

Task 2 asks for per-band residuals at 685 / 713 / 719 nm and
`Rrs_unc(719)/Rrs(719)`. These need the observed granule spectra plus a
reconstructed fit, i.e. another granule-reading pass over 100 matchups — the
slice job did not retain the spectra. They are also now a diagnostic on a band
**outside** the 400–700 fit window, so they cannot be a fit residual in any
case.

**Question:** worth a separate ~20 min job, or skip for the gate? *My
recommendation: skip for the gate and fold it into Prompt 7 if wanted.* Prompt 3
already did this check on 20 matchups and it is what moved `wave_max` to 700;
re-measuring a band we deliberately excluded is unlikely to change a go/no-go
decision, and I would rather say that than produce the number for completeness.

#### (c) `build_fits` logs nothing — recommend fixing before the full send

`build_fits` emits **no progress and no per-fit timing**. Consequences:

- Task 2's requested "s/fit median, p90" is not directly answerable. I
  reconstructed the figures from `created` timestamps, which is why I can
  separate the 11.4 min compile from the 164 s/fit steady state at all.
- A **15–23 h** full send would log nothing between start and finish. Every
  other long stage has `PROGRESS_EVERY` (`match`, `geometry`, `discover`), and
  the value of that was proven repeatedly in Prompt 5 — progress staleness is
  how I caught the geometry pre-OOM thrash.

*My recommendation: add `PROGRESS_EVERY` logging plus per-fit elapsed time to
`build_fits` before Prompt 7.* Small, matches the other stages, and the full
send is exactly the run where you cannot afford to be blind. I have not done it
because it is outside Task 3's scope and would need another image.

>A. (a) yes; (b) skip and fold into Prompt 7; (c) add logging and per-fit timing to `build_fits` before Prompt 7.


## Reports

### Task 1 — slice selection + mechanism (2026-09-30/10-01): **done — 99/100 fits in 21 min**

#### The slice

Eligibility needed correcting mid-task. **The v1 BING fits are not in the v2
store** — it carries only the 14,609 `NASA_GIOP` 1.1 fits; the 14,609 `BING`
1.0 fits exist solely in the frozen `v1/pab.db`. My first query tested
`rt_backend IS NULL`, which the NASA_GIOP rows satisfy, and returned a
*plausible* 14,604. The real pool, joined against the frozen database, is
**14,573**. A wrong query giving a believable answer is the hard kind to catch.

100 matchups, fixed seed 20260930 (reproducible), staged to
`/data/v2/slice_100.csv`, md5 `61e04c7bbb33acbcdc04bdb18ed348ff`:

| stratum | |
|---|---|
| `theta_v` | 25 / 25 / 25 / 25 across <30, 30–45, 45–55, **≥55 (swath edge)** |
| basin | Pacific 32, Atlantic 19, Indian 17, Southern 16, N-high 16 |
| season | MAM 28, DJF 24, JJA 24, SON 24 |
| range | `theta_v` 22.1–**60.0**, 9 pixels ≥58°; `theta_s` 5.1–72.7 |

The swath edge is over-weighted on purpose (25 % of the slice against ~11 % of
the pool). That decision paid off — see Task 2.

#### The mechanism

Mirrored Prompt 5 Q5's `match` seam rather than inventing one:
`PipelineConfig.matchup_ids()` → `set[str] | None`, forwarded by
`pipeline.fit()`, filtered in `build_fits(selection=...)` **before any granule
is opened**. `--matchup ID` repeatable (as `pab.fit.nasa_giop` already had)
plus `--matchups-csv` for the bulk form. **8 tests**; suite **356 passed, 1
skipped**. `HOWTO.md`'s selection row corrected — it has been wrong twice, and
the fix is that `fit` selects by *matchup*, not profile.

#### The launch, and an error of mine worth recording

The pre-launch check refused `:2.0.3`:

```
image :2.0.3 baked PAB : 99c37ef      git HEAD : 2da2e09
build_fits accepts selection : False
```

So: commit `2da2e09` → build `:2.0.4` → push → launch. The push then failed
with `denied`, which took a diagnosis: the stored credential was
`gitlab+deploy-token-1383`, the deploy token for a **different project**
(`profx/keck-etcs`). GitLab deploy tokens are per-project, so it read fine and
could never write to `profx/pab`. A new project-scoped token (`pab-push`, 1384)
fixed it. Worth knowing because the symptom — pulls work, pushes denied — looks
like a registry problem rather than a credential-scope one.

**Then I launched a manifest still pointing at `:2.0.3`.** I had verified the
*image* exhaustively and never checked that the *manifest referenced it*. The
job ran for 12 s and died:

```
pab: error: unrecognized arguments: --matchups-csv /data/v2/slice_100.csv
```

Two lessons, and the second matters more:

1. **"Is the image right?" is not "does the manifest point at the right
   image?"** The Prompt 5 Task 4 failure was the latter and I had built a check
   for the former. A manifest-level assertion is now part of the sequence.
2. **The blast radius was luck.** Here the flag was *new*, so argparse rejected
   it and the job failed loudly. In Prompt 5 Task 4 the flag (`--profiles-csv`)
   already existed in the stale image, was silently ignored, and the job did
   the unrestricted thing. The difference between a hard failure and a silent
   wrong answer was purely whether the flag name already existed — not
   anything I did.

Database verified unchanged after the abort (14,609 fits). Relaunched on
`:2.0.4`; gate passed: `fit: selection restricts to 100 of the store's
matchups`.

---

### Task 2 — measuring the slice (2026-10-01): **both pause triggers clear; the swath-edge signal is the new result**

99 of 100 fits, 21 min wall, `robust_hybrid` / `fit_Bp` / `phi_C=0.02` /
400–700 nm / 10 000 steps / 16 walkers. 99 chains, **116.0 MB** (the ~115 MB
estimate was almost exact).

#### Cost — and why the obvious number is wrong

```
stage start -> first fit persisted   11.4 min   worker spawn + JAX compile, zero fits
first -> last fit                     8.5 min   all 99
steady state                        164 s/fit   worker time
naive total-wall / fits             385 s/fit
```

**164 s/fit, comfortably under Q12's 240 s trigger.** The naive aggregate is
**385 s/fit and would have tripped it** — inflated by an 11.4-minute one-time
compile amortised over only ~3 fits per worker. In the full send each worker
does ~320 fits and that cost disappears. Reporting the aggregate alone would
have produced a false *pause*.

**A gap this exposed:** `build_fits` logs **no per-fit timing and no progress
at all**. The "median, p90" this task asks for is not directly answerable; the
figures above are reconstructed from `created` timestamps. A 15–23 h full send
that logs nothing is also undiagnosable while it runs. Recommend adding
progress + per-fit timing before Prompt 7.

**Failures: 1 of 100 (1 %)**, under the 2 % trigger — `open_granule failed`
on `PACE_OCI.20260521T150812`, the same transient class as the geometry
timeouts, recoverable on a re-run.

**Projection (15,976 matchups):**

| workers | steady state | chains |
|---:|---:|---:|
| 32 | **22.9 h** | ~19 GB |
| 50 | **14.7 h** | ~19 GB |

#### Physics — 2.0 vs the same matchups' v1 BING fits

| | 2.0 | 1.0 |
|---|---:|---:|
| χ² median | **0.404** | 0.428 |
| acceptance median | **0.340** | 0.451 |

χ² is slightly **better** under 2.0, and acceptance drops as expected for six
parameters against five (Prompt 3 measured ~0.33 / ~0.47 — reproduced). Note
Prompt 3 reported χ² 0.65 / 0.45, i.e. 2.0 *worse*; at 5× the sample 2.0 is
marginally better. The 20-matchup χ² comparison did not generalise.

**`bbp700` 2.0 / 1.0 — the headline:**

```
median 0.7375      (Prompt 3, n=20: 0.741 — reproduced almost exactly)
96/99 below 1.0    (Prompt 3: 18/20)
p10 0.454   p90 0.927
```

**The new result is the swath-edge dependence:**

| `theta_v` band | median `bbp700` 2.0/1.0 |
|---|---:|
| <30° | 0.794 |
| 30–45° | 0.757 |
| 45–55° | 0.782 |
| **≥55° (swath edge)** | **0.577** |

At the swath edge the 2.0 backscatter is **~42 % below 1.0**, against ~21 %
elsewhere. That is exactly where the off-nadir emulator correction should bite
hardest, and it is only visible because the slice deliberately over-weighted
`theta_v ≥ 55`. A proportionally-sampled slice would have had ~11 of these
instead of 25 and the effect would have been far weaker.

Other parameters: `bbp440` 0.683, `anw440` 1.157.

**`chl` 2.0 / 1.0 — median 1.229, but read the tail carefully.** `p95` is 87
and the max is 371, which looks alarming until you look at what drives it:

```
ratio   chl_2.0   chl_1.0
370.9    0.282     0.0008
297.2    0.304     0.0010
283.1    0.556     0.0020
```

The extremes come from the **1.0** fit collapsing chl to ~0.001–0.002 mg/m³ —
an order of magnitude below anything physical in the open ocean — not from 2.0
misbehaving; the 2.0 values are entirely plausible. 7 of 99 are affected. So
this is evidence of 1.0 failing on those seven rather than a 2.0 problem, and
the honest summary is "chl ~23 % higher, with seven cases where the 1.0 fit was
not usable".

**`B_p` posterior (free, prior 0.004–0.05):**

```
median 0.0234   (Prompt 3, n=20: 0.0250)   68 % width median 0.0324
pinned LOW  (<=0.0045): 2/99  (2 %)
pinned HIGH (>=0.0495): 0/99  (0 %)
```

Prompt 3 flagged pinning to the lower bound on **~15 %** (3 of 20) and asked
whether that fraction grows. **It does not — it falls to 2 %.** The small-sample
figure was pessimistic. `B_p` shows no systematic `theta_v` dependence
(medians 0.0218 / 0.0260 / 0.0234 / 0.0263 across the four bands), which is
reassuring: the swath-edge `bbp700` shift is therefore **not** `B_p` absorbing
the geometry — Task 3's `fit_Bp=False` run tests that directly.

#### Not measured: R4 band residuals

Per-band residuals at 685 / 713 / 719 nm and `Rrs_unc(719)/Rrs(719)` need the
observed granule spectra and a reconstructed fit, i.e. another granule-reading
pass. They are now a diagnostic on a band **outside** the 400–700 fit window,
so they cannot be a fit residual. Deferred rather than guessed — see Q2.


### Task 3 — attribution + the go/no-go gate (2026-10-02): **GO**

#### Attribution: the `bbp700` shift is the emulator, not the free `B_p`

Refit the same 100 matchups with `fit_Bp=False` (`Bp_value=0.01`), otherwise
2.0, on a scratch copy. **100 written, 0 failed** — including the one matchup
whose granule open failed in the slice, confirming that failure was transient.
`v2` verified untouched afterwards (14,708 fits / 99 2.0 fits, unchanged).

| `bbp700` ratio | median | p10 | p90 |
|---|---:|---:|---:|
| free `B_p` / 1.0 — the 2.0 fit | **0.7375** | 0.454 | 0.927 |
| **fixed `B_p` / 1.0 — emulator + inelastic only** | **0.7363** | 0.439 | 0.942 |
| free / fixed — what the free `B_p` adds | **1.0050** | 0.972 | 1.069 |

**Freeing `B_p` moves `bbp700` by 0.5 %.** Essentially the whole ~26 %
reduction comes from the emulator + inelastic terms.

By `theta_v` band:

| band | free/1.0 | fixed/1.0 |
|---|---:|---:|
| <30° | 0.794 | 0.792 |
| 30–45° | 0.757 | 0.753 |
| 45–55° | 0.782 | 0.748 |
| **≥55° (swath edge)** | **0.577** | **0.560** |

The swath-edge effect is **entirely** the emulator — fixing `B_p` makes it
marginally *stronger*. This confirms by direct measurement what Task 2 could
only infer from `B_p` having no `theta_v` dependence (medians 0.0218–0.0263
across the four bands).

**A question this raises, which is JXP's to answer (Q3).** The free `B_p` is
the 6th parameter. It costs acceptance (0.340 against 1.0's 0.451) and it
contributes **0.5 %** to the headline quantity. That does not make it wrong —
it may matter for honest posterior widths or for other parameters — but
"we freed `B_p` and `b_bp` fell 26 %" would be the wrong story, and it is the
story the Prompt 3 numbers invited.

#### The gate, against Q12's three triggers

| trigger | threshold | measured | |
|---|---|---|---|
| median s/fit | > 4 min (240 s) | **164 s** | **clear** |
| failure rate | > 2 % | **1 %** (1 of 100, transient granule open; succeeded on the attribution re-run) | **clear** |
| a `b_bp` shift JXP considers implausible | judgement | **0.7375**, reproducing Prompt 3's 0.741 at 5× the sample | **JXP's call** |

The s/fit figure needs its caveat stated once more because it is the one that
could have gone the other way: **total wall ÷ fits = 385 s/fit**, which breaches
the trigger. The true steady-state cost is 164 s; the difference is an 11.4 min
one-time JAX compile amortised over ~3 fits per worker. In the full send
(~320 fits/worker) it disappears. Reporting the aggregate would have produced a
*pause* recommendation on an artefact of slice size.

#### Supporting evidence

- **χ² is slightly better under 2.0** (0.404 vs 0.428). Prompt 3 had 2.0 *worse*
  (0.65 vs 0.45) on 20 matchups; that did not generalise.
- **Acceptance reproduced exactly** (0.340 vs 0.451) — six parameters vs five.
- **`B_p` prior-edge pinning fell from 15 % (3/20) to 2 % (2/99)**, and never
  pins high. The small-sample concern was pessimistic.
- **`chl` 2.0/1.0 median 1.229**, with a tail to 371× caused by the **1.0** fit
  collapsing chl to ~0.001–0.002 mg/m³ on 7 of 99 — physically impossible —
  while the 2.0 values (0.28–0.56) are plausible. Evidence of 1.0 failing on
  those seven, not of a 2.0 defect.
- **96/99 matchups have `bbp700` below 1.0**, against 18/20 in Prompt 3.

#### Recommendation: **GO**

Two of three triggers are measured clear with margin, and the third reproduces
a number already in hand rather than discovering a new one. The physics is
coherent: the reduction scales with `theta_v` exactly as an off-nadir
correction should, and the attribution shows it is the emulator rather than an
extra free parameter soaking up signal.

**Full send:** 15,976 matchups, **14.7 h at 50 workers** (22.9 h at 32),
~19 GB of chains.

**Three things to carry into Prompt 7**, none of which block the go:

1. **`fit`'s pool still has no `max_tasks_per_child`** (Q1c). The slice could
   not settle it — ~3 fits per worker, where `geometry` needed ~950 to OOM —
   and memory climbed 0.3 → 20.0 GB without plateauing in 21 min. The geometry
   fix does **not** transfer naively: recycling a worker re-pays the JAX
   compile, which the slice measured at 11.4 min per pool. Size it from the
   full send's own trace, now that `build_fits` reports memory (see 2).
2. **`build_fits` now logs progress, per-fit median and memory** (Q2c, done) —
   with startup reported separately so the 385-vs-164 confusion cannot recur.
   This needs an image newer than `:2.0.4` to take effect.
3. **R4 band residuals** (685 / 713 / 719 nm, `Rrs_unc(719)/Rrs(719)`) deferred
   per Q2b, to fold into Prompt 7 if wanted.


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

### 2026-10-01 (Prompt 6 Tasks 1–2 — slice fitted, 99/100; both pause triggers clear; the swath edge is the finding)

Built and ran the leading slice, then measured it. Both Q12 triggers are clear
and the physics reproduces Prompt 3 closely — with one genuinely new result.

**The number that nearly produced a false alarm.** Dividing total wall by fits
gives **385 s/fit**, over Q12's 240 s pause trigger. The steady-state cost is
**164 s/fit**: the stage spent **11.4 min** spawning workers and compiling JAX
before persisting a single fit, then did all 99 in 8.5 min. With ~3 fits per
worker that one-time compile dominates; in the full send (~320 fits/worker) it
vanishes. Had I reported the aggregate I would have recommended *pause* on an
artefact of slice size.

**`bbp700` 2.0/1.0 median 0.7375**, against Prompt 3's 0.741 on 20 matchups —
reproduced almost exactly at 5× the sample, 96/99 below 1.0.

**The new result is that the shift is swath-edge dependent:** 0.577 at
`theta_v >= 55` against ~0.78 elsewhere, i.e. **~42 % below 1.0 at the edge
versus ~21 % in the middle**. That is precisely where the off-nadir emulator
correction should matter most, and it is only visible because the slice
deliberately over-weighted the swath edge (25 % of the slice against ~11 % of
the pool). A proportional sample would have had ~11 such matchups instead of 25
and the effect would have been much weaker. The stratification choice in Task 1
is what made this measurable.

**Two small-sample figures from Prompt 3 did not hold**, and both moved in the
reassuring direction:

- `B_p` pinning to its lower prior bound: **15 % (3/20) → 2 % (2/99)**.
- χ²: Prompt 3 had 2.0 *worse* (0.65 vs 0.45); here 2.0 is marginally **better**
  (0.404 vs 0.428).

Acceptance reproduced exactly (0.340 vs 0.451, six parameters against five).

**A scary-looking number that is the opposite of what it seems.** `chl` 2.0/1.0
has p95 = 87 and max = 371. The cause is the **1.0** fit collapsing chl to
~0.001–0.002 mg/m³ on 7 of 99 — an order of magnitude below anything physical —
while the 2.0 values (0.28–0.56) are entirely plausible. Reported as "chl ~23 %
higher, with seven cases where the 1.0 fit was not usable", because "371× higher"
would have read as a 2.0 defect.

**`B_p` shows no `theta_v` dependence** (medians 0.0218–0.0263 across the four
bands), so the swath-edge `bbp700` shift is not `B_p` quietly absorbing the
geometry. Task 3's `fit_Bp=False` run tests that directly.

**Two gaps recorded rather than papered over.** `build_fits` logs no per-fit
timing and no progress at all, so the "median, p90" this task asks for is not
directly answerable — I reconstructed it from `created` timestamps, and a
15–23 h full send that logs nothing would be undiagnosable while running. And
the R4 band residuals need another granule-reading pass, so they are deferred
(Q2) rather than estimated.

**An error of mine worth keeping.** After verifying the image exhaustively I
launched a manifest that still pointed at the *old* one. "Is the image right?"
is not "does the manifest point at the right image?" — and the latter is what
bit Prompt 5 Task 4. It failed loudly here only because the flag was new, so
argparse rejected it; in Prompt 5 the flag already existed and was silently
ignored, which is why that run did the unrestricted thing. The difference
between a crash and a silent wrong answer was luck, not care. A manifest-level
assertion is now in the pre-launch sequence.

**Also diagnosed:** the registry push failure was a **per-project** GitLab
deploy token — `gitlab+deploy-token-1383` belongs to `profx/keck-etcs`, so it
could read `profx/pab` but never write it. Symptom (pulls fine, pushes denied)
points at the registry; cause is credential scope.

### 2026-10-02 (Prompt 6 Task 3 — attribution: the shift is the emulator, not the free B_p; gate says GO)

Refit the slice's 100 matchups with `fit_Bp=False` on a scratch copy. **100
written, 0 failed** — including the matchup whose granule open failed in the
slice, which settles that failure as transient. The guard worked: `v2` verified
untouched at 14,708 fits / 99 2.0 fits.

**The result is cleaner than I expected.** Fixing `B_p` at 0.01 gives
`bbp700`/1.0 = **0.7363** against the free-`B_p` **0.7375** — the free
parameter moves the headline quantity by **0.5 %**. At the swath edge, fixing
`B_p` gives **0.560** against 0.577, i.e. slightly *more* shift. So the entire
`theta_v` dependence is the emulator, and none of it is `B_p` absorbing
geometry. Task 2 inferred this from `B_p` showing no `theta_v` dependence; this
measures it.

**Worth stating plainly because the Prompt 3 framing invited the opposite
reading:** "we freed `B_p` and `b_bp` fell 26 %" would be wrong. The free `B_p`
costs a parameter and acceptance (0.340 vs 0.451) and contributes 0.5 % to
`bbp700`. That is not an argument against keeping it — posterior honesty is a
reason on its own — but it is an argument against describing it as the cause.
Raised as Q3.

**Gate: GO.** Two of three Q12 triggers measured clear with margin (164 s/fit
against 240; 1 % failures against 2 %), and the third reproduces Prompt 3's
0.741 rather than discovering anything new.

**The trigger that nearly went the other way, recorded once more because it is
the single most important measurement lesson of this prompt:** total wall ÷
fits = **385 s/fit**, which breaches the 240 s trigger. The real steady-state
cost is **164 s/fit**. The gap is an 11.4 min one-time JAX compile spread over
~3 fits per worker, which vanishes at ~320 fits/worker in the full send. The
aggregate was not a wrong calculation — it was the right calculation of the
wrong quantity, and it would have produced a *pause* on an artefact of how
small the slice is. `build_fits` now reports startup separately for exactly
this reason.

**Several Prompt 3 small-sample figures did not survive 5× the sample**, all in
the reassuring direction: `B_p` edge-pinning 15 % → 2 %; χ² went from 2.0 being
worse (0.65/0.45) to marginally better (0.404/0.428). The ones that *did* hold
were the two central physics numbers — `bbp700` 0.741 → 0.7375 and acceptance
~0.33/~0.47 → 0.340/0.451. Encouraging: the parameter estimates were stable at
n=20 and the goodness-of-fit summaries were not.

**Carried into Prompt 7, not blocking:** `fit`'s pool still lacks
`max_tasks_per_child` and the slice cannot settle it (~3 fits/worker vs the
~950 geometry needed to OOM), with memory climbing 0.3 → 20.0 GB without
plateauing; the new `build_fits` logging needs an image past `:2.0.4`; and the
R4 band residuals are deferred per Q2b.

### 2026-10-02 (Prompt 6 Task 4 — `build_v2_prompt_7.md` updated from the gate)

Updated Prompt 7 with what the gate established, and corrected two things in it
that were already stale.

**Corrected:** it specified image `:2.0.0`, which Prompt 6's own working
agreements list as the one image that must never be used (its `figure` stage
fails for every 2.0 fit). Now `:2.0.4` or later. And its cost basis pointed at
Plan §3's ~16.8 k matchups; the store holds **15,976**, of which **99 already
have a 2.0 fit** (the slice, idempotently skipped) and **5 have no geometry and
will be refused by R3** per Prompt 5 Q16. So **~15,872** fits to attempt.

**Added:** the measured 164 s/fit with an explicit warning not to quote
total-wall ÷ fits (385 s/fit, which breaches the pause trigger); the attribution
result; the two pre-launch checks, both of which have now caught a real error;
and the `max_tasks_per_child` decision framed as "size it from this run's own
trace" rather than "copy geometry's value" — because recycling a worker re-pays
an 11 min JAX compile, so the fix that was right for geometry could be actively
harmful here.

**Added as Task 4:** the R4 band diagnostics deferred from Q2b, with the
framing that matters — 713/719 nm are *outside* the fit window, so the question
is whether excluding the red edge was right, not whether the fits are good
there. Suggested running it on the slice's 100 rather than all ~16 k, since it
needs a granule-reading pass.
