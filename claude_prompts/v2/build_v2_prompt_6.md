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

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
