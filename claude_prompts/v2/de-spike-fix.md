# Fix the Argo `BBP700` de-spike and re-derive the mixed-layer `b_bp`

## Goals

Fix the 3-point moving-median de-spike of `BBP700` so that it runs over the
**samples**, not over every pressure level. Then re-derive the mixed-layer
`b_bp(700)` statistics (`bbp700`, `bbp700_std`, `n_points`) for the matched
profiles, and measure what the fix does to the PACE vs Argo comparison.

Why. `summary.mixed_layer_mean(..., despike_values=True)` calls
`moving_median` on the full pressure column of the merged argopy profile.
Most BGC floats carry `BBP700` on only every 2nd or 3rd level of that column,
with NaN in between. Each 3-point window then holds one sample, so:

- the median is the sample itself: **nothing is de-spiked**;
- a window centred on an empty level takes its one neighbour's value, so each
  sample is **copied into the empty levels**. `n_points` is inflated, and the
  mean and std are weighted by the number of copies.

Source of the decision: `claude_prompts/viz_tools.md`, Q&A / Argo+PACE,
**AP-Q16 = A** (fix the ingest and re-derive, in a new version, via this doc)
and **AP-Q17 = A** (keep the de-spiked line and the log-IQR filter as they
are; Bisson et al.). The bug was found with the `pab-viz` Argo + PACE tool
(Argo+PACE prompt 4, 2026-11-19).

## Claude

### Skills

None of the BING skills apply: nothing here touches a fit.
**`batch-fit-argo`** is a useful reference for the parallel, checkpointed
loop pattern only.

### Working agreements

- **Git is handled by JXP.** Run no state-changing git commands. Read-only
  `git status` / `git diff` / `git log` are fine.
- **Python only.** Use the `ocean14` env via
  **`/home/xavier/miniconda3/envs/ocean14/bin/python`**.
- **Explicit `--db` every time**: `$PAB_DATA_DIR/v2/pab.db`.
- **`v1/pab.db` is frozen.** It is `chmod a-w`, sha `09de0a6d…f978273`.
  Open it only read-only.
- **Before any write to the live v2 DB:** make a dated, sha-verified copy
  (`v2/pab_pre_despike_<date>.db`). Record row counts and checksums of
  `mld_summary` (and of whatever table Task 3 writes) before and after.
- **No `fits` / `fit_results` row is touched.** BING reads only
  `mld_summary.chla` (`pab/fit/run.py`, the `set_aph` input), and Chl is a
  plain ML mean with no de-spike, so no re-fit is needed or wanted.
- **Safety run first, on a scratch DB copy**, before the live DB.
- **Stop for JXP's review** where the Tasks say so.
- Questions for JXP go in the **Q&A** section of this file, never chat-only.
- **Nothing is published** (Zenodo, web, PyPI) without JXP's explicit
  go-ahead in that step.

## Context

### The bug, measured (2026-11-19)

The data come from the `pab-viz` session: a live re-fetch of 60 random
matchups out of the 15,279 matched profiles with a stored ML `b_bp`.

| measure | result |
|---|---|
| profiles with NaN levels between `BBP700` samples | 55 / 60 |
| profiles with more than half of their gaps NaN | 33 / 60 |
| stored `n_points` > real samples in the ML | 46 / 60 (median ratio 1.6) |
| change in the ML mean when fixed: median / 90th pct / max | 0.5 % / 2.0 % / 6.8 % |
| profiles whose mean changes > 2 % | 7 / 60 |

Examples (wmo/cycle):

| profile | what it shows |
|---|---|
| 1902368/25 | 22 samples in the ML; stored n = 66; 17 kept after IQR |
| 4903848/69 | a 2-sample spike at 8–10 dbar, which the IQR filter correctly rejects |
| 6904187/157 | the largest mean shift of the 60 (6.8 %) |

The viz already implements the corrected recipe (`pab.viz.argo.despike_samples`
and `bbp_layers`) and shows both values side by side.

### Code seams (verified 2026-11-19)

| Where | What |
|---|---|
| `pab/argo/summary.py` `moving_median` | Correct as a filter. The bug is in **what it is given**. |
| `pab/argo/summary.py` `mixed_layer_mean` | Calls `moving_median(vals)` over the full column when `despike_values=True`. **The fix goes here**: de-spike `vals[finite]` only, scatter the result back, and leave NaN on the empty levels. |
| `pab/argo/summary.py` `summarize_profile` | `bbp700`, `bbp700_std`, `n_points` come from that call. Chl, CDOM, PSAL and TEMP use plain means (no de-spike), so they are **unaffected**. |
| `pab/argo/qa.py` `plot_profile` | The per-profile QA figure (`mld_summary.qa_path`) overlays `moving_median(values)` over the full column: **same bug**, display only. |
| `pab/viz/argo.py` | `despike_samples` (the corrected recipe) plus `ingest_*` (the old one). After the fix, it should call the shared function, and its "stored vs sample de-spike" note becomes a stored (old) vs re-fetch (new) comparison. |
| `pab/pipeline.py` `ingest` | Idempotent upsert into `mld_summary` keyed by `profile_id`. With `replace` it re-fetches everything, including the MLD and the metadata. |
| `pab/metrics/compare.py` `gather_matchups` | Joins `mld_summary` for `bbp_argo` / `chla_argo`: every comparison metric reads `ms.bbp700`. |
| `pab/matchup/plot_bbp700_vs_temp.py` | Uses `bbp700_std` for error bars. |
| `mld_summary` (live v2 DB) | 59,620 rows: `pab_version` 1.0 = 54,031, 2.0 = 5,589. 55,948 have a `bbp700`. **One row per profile** (PK `profile_id`), so old and new values cannot coexist as rows of this table (DS-Q1). |

### What does not change

- The MLD (`deBoyerMontegut_0.03`), the IQR filter (k = 1.5 in log space;
  AP-Q17 = A), and the Chl / CDOM / PSAL / TEMP means.
- Every BING and GIOP fit.

## Prompts

1. Read this file. JXP has answered the questions in Q&A / Round 1. Fold the
   answers into the Plan, then execute **Task 1**. Use Opus 5.5. Log your
   work.

## Plan

*Draft, 2026-11-19. It will be revised with JXP's Round 1 answers.*

### 1. Code (Task 1)

- **Fix `mixed_layer_mean`.** De-spike over the finite samples only.
  `n_points` then counts real samples. Keep the signature.
- Add a `despike_levels="samples"|"column"` switch (default `"samples"`) so
  the old recipe stays reproducible for the comparison in Task 4 and for
  tests. The name is up for DS-Q5.
- **Fix `qa.plot_profile`** the same way (draw the de-spiked samples, not the
  column).
- **Point `pab.viz.argo`** at the shared function and drop its private copy.
  Its note becomes "stored (column recipe) vs re-fetch (sample recipe)"
  until the DB is refreshed.
- **Tests:**
  - a gapped synthetic profile (every 2nd level NaN plus an isolated spike):
    the spike is removed and `n` equals the sample count;
  - a dense profile gives identical results under both recipes;
  - the existing `summary` tests pass unchanged.
- **The refresh driver** (DS-Q1, DS-Q2). For each selected profile:
  - re-fetch with ingest's argopy `src`/`mode`;
  - compute **both** recipes on the same fetch, so the de-spike effect is
    separated from any GDAC reprocessing since ingest (DS-Q4);
  - write the result to the DS-Q1 target.
- **Resumable and parallel:**
  - fetch in workers and keep one SQLite writer, the `_ingest_concurrent`
    pattern;
  - log per-profile failures;
  - add a `--dry-run` flag and a `--limit` flag.

### 2. Safety run (Task 2)

- Run on a scratch copy of the live DB with `--limit 50`.
- Check:
  - the schema change, if DS-Q1 needs one;
  - the "column" recipe on the re-fetch reproduces the stored `bbp700` and
    `n_points` (except where the GDAC changed);
  - the "samples" recipe matches `pab-viz` on the AP examples.
- Time per profile, to size Task 3.

### 3. The refresh (Task 3)

- Dated copy and checksums, then the run on the DS-Q2 selection and the
  DS-Q6 machine.
- Expected cost: ~1–6 s per profile fetch. 15,279 profiles serial is
  ~1 day; with 8 workers it is a few hours.

### 4. Impact (Task 4)

- **Distribution of the change** (new − old) in `bbp700`, `bbp700_std` and
  `n_points`. Separately, the GDAC-drift component (stored vs column recipe
  on the re-fetch).
- **The PACE vs Argo `b_bp(700)` metrics** (`compare.py`: bias, median ratio,
  scatter, r) for 2.1, under old and new Argo values.
- A short write-up, plus figures in `versions/<v>/` (DS-Q3). Re-render the
  QA figures for the matched profiles if DS-Q7 says so.

### 5. Close-out (Task 5)

- HOWTO and `docs/` notes on the recipe change.
- The report regenerated if DS-Q3 calls for a version bump.
- Anything published only with JXP's go-ahead.

## Tasks

### Task 1: code, tests, local check

§1. Full suite and `ruff` clean. Confirm on 3–5 live profiles that the
"column" recipe reproduces the stored values exactly.

### Task 2: safety run (STOP for review)

§2. Report timings, reproduction rate, and the first look at new − old.

### Task 3: the refresh

§3. Dated copy first; counts and checksums before and after.

### Task 4: impact and write-up

§4.

### Task 5: close-out

§5. Each outward-facing step is confirmed with JXP.

## Q&A

### Round 1 (2026-11-19)

*Answer inline under each **Your answer:**. Where I have a recommendation it
is marked.*

**DS-Q1. Where do the corrected values go?**

`mld_summary` is one row per profile, so old and new cannot both be rows of
it. Options:

- **A** *(recommended)*. A new table `argo_bbp_ml`:
  - key `(profile_id, recipe)`, with `recipe` ∈ {`column`, `samples`};
  - columns `bbp700`, `bbp700_std`, `n_points`, `n_samples_ml`,
    `gdac_fetched` (timestamp) and `pab_version`;
  - a schema migration (v6 → v7);
  - `gather_matchups` gains a `bbp_recipe` argument (default `samples` once
    the table is filled).

  Old and new sit side by side, and `mld_summary` stays exactly as ingested
  for provenance.
- **B**. Overwrite `mld_summary.bbp700` / `bbp700_std` / `n_points` in place
  (after the dated copy), and stamp `pab_version`. Simplest, but the old
  values survive only in the backup copy.
- **C**. Add columns to `mld_summary` (`bbp700_samples`, …).

**Your answer:**

**DS-Q2. Which profiles?**

- **A** *(recommended)*. The 15,279 matched profiles with a stored ML `b_bp`:
  everything a PACE comparison uses.
- **B**. All 55,948 profiles with a `bbp700`: ~3.7× the fetch time, for
  profiles with no PACE match.

**Your answer:**

**DS-Q3. Version label.**

The BING fits do not change; only the Argo side of the comparison does.

- **A** *(recommended)*. Stamp the new rows `pab_version = "2.2"` and make
  2.2 the next report version: "2.1 fits, sample de-spike".
- **B**. A patch label, `"2.1.1"`, in the `compare` overlay sense. But the
  overlay is built for `fits`, not for Argo rows.
- **C**. No version bump: record the recipe only.

**Your answer:**

**DS-Q4. GDAC drift.**

The re-fetch gets today's GDAC files, and some profiles have been reprocessed
since ingest.

- **A** *(recommended)*. Compute both recipes on the same re-fetch, and
  report the de-spike effect (samples vs column, same data) apart from the
  drift (column re-fetch vs stored). The MLD is recomputed from the re-fetch
  too; where it moves by more than 1 m, flag the profile rather than silently
  change the ML.
- **B**. Use the re-fetch as is and do not separate the two effects.

**Your answer:**

**DS-Q5. Keep the old recipe in code?**

- **A** *(recommended)*. Yes, as `despike_levels="column"`, documented as
  "the pre-2.2 bug, kept for reproducibility". The default is `"samples"`.
- **B**. No: remove it. The old values live in the DB (DS-Q1 A) or the
  backup.

**Your answer:**

**DS-Q6. Where to run Task 3?**

The job is network- and fetch-bound, with no MCMC.

- **A** *(recommended)*. The workstation, with ~8 fetch workers, overnight.
- **B**. Nautilus, like the v2.1 re-fit (more image and PVC overhead for a
  light job).

**Your answer:**

**DS-Q7. The per-profile QA figures** (`mld_summary.qa_path`).

- **A** *(recommended)*. Fix `qa.py` now, and re-render the figures only for
  the matched profiles during Task 3 (same fetch).
- **B**. Fix the code only. Old figures stay until a future full re-ingest.

**Your answer:**

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-11-19 (Prompt doc written from viz_tools AP-Q16 = A; seven questions posed)

With Claude Opus 5.5, from `claude_prompts/viz_tools.md` Argo+PACE prompt 5.

The doc records:
- the bug and the 60-matchup measurement;
- the code seams, verified today:
  - `mixed_layer_mean` is where the fix goes;
  - `qa.plot_profile` has the same display bug;
  - BING reads only `mld_summary.chla`, so no re-fit is needed;
  - `mld_summary` is one row per profile: 59,620 rows, 55,948 with a
    `bbp700`, 15,279 of them matched;
- a five-task plan with a stop after the safety run.

Round 1 (DS-Q1 to DS-Q7) is posed. No code was changed and no DB was
touched.
