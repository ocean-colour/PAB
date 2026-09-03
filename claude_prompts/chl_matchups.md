# Examining Chl-a Matchups

## Goals

We are going to examine the chl-a matchups for the PAB pipeline.  These have 
already been measured and are stored in the files in `s3://pab/full/`

## Context

Read these before running — plus the **hard-won operational lessons** below.

- **Operator guide** — `HOWTO.md` (the CLI, the stages, idempotency/resume, the
  in-region vs `--download` granule-access section, and §7 publishing).
- **Design** — `docs/design/PAB_design.md` → *Semi-automation* (idempotent stage
  runner, single-matchup debug vs full batch, BING `fit_batch`) and *Provenance &
  versioning* (every result stamped with `pab_version`; re-running under a new
  version **adds** records, never silently overwrites).
- **Implementation record** — `docs/design/PAB_implementation.md` (current state,
  incl. the Stage 9 close-out: schema v3, headless plotting, report structure).
- The logs in the prompt docs: `claude_prompts/first_runs.md`, `claude_prompts/nautilus_prompts.md`, `claude_prompts/run_full_pipeline.md`.


## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below

## Tasks

1. Read all the files in the context.  Also take a look at the files in the `s3://pab` bucket in `s3://pab/full/`.  We are going to do a deep dive into the chl-a matchups. We will want a set of figures similar to what we have done for bbp700.  But, those will remain internal for now, i.e. not published to RTD.  We will generate a report for GitHub.  Before doing so, please discuss with me the plan for this work.  Ask me a series of questions in the Q&A section.  Use Fable if you can.  Log your work.

2.  I have answered your questions; please review my answers.  And here is a new item. 
One of the important aspects of Chl-a from BGC-Argo is that they are now implementing a physiological correction based on satellite data.  Can you check to see whether we can tell if this correction is present in the PAB database?  Add any additional questions to the Q&A section.  Use Fable if you can.  Log your work.  Do not start the analysis or report yet.

3. 

## Plan

**Goal.** A chl-a deep-dive on the full-mission production run (`s3://pab/full/`, pab_version 1.0; 14,610 matchups / 881 floats), mirroring the internal bbp700 bias analysis. Figures and write-up stay internal (in-repo, not RTD); the deliverable is a GitHub-facing report. Note the RTD `summary` page already carries an aggregate Chl scatter — this work is the deeper diagnostic layer behind it.

**Scientific framing.** Unlike bbp700, `chl_bing` is a *retrieval* (`10**Aph / 0.05582` from the fitted phytoplankton amplitude), so this is a retrieval-vs-in-situ test with its own failure modes. The bbp700 depth-mismatch hypothesis does not automatically carry over; for Chl the leading confounders are different (e.g., CDOM/detrital absorption aliasing into the Bricaud phytoplankton term, especially at high latitudes / river-influenced regions). The analysis should establish the bias signature first, then test candidate mechanisms — not assume the bbp700 story.

### Investigation — Argo Chl-a correction provenance

**Short answer: no — the PAB database cannot currently tell us whether any Chl-a correction (satellite-based or otherwise) was applied to a given profile.** Three independent findings support this:

1. **The production run ingested raw, un-adjusted Chl by design.** `PipelineConfig.argo_mode` defaults to `"expert"` (`pab/pipeline.py`), and that is what the full-mission run used. Per `pab/argo/fetch.py`'s own docstring, `expert` mode returns "the measured parameters as-is" — the raw `CHLA` field — whereas `standard`/`research` mode prefer the delayed-mode/adjusted fields but return **zero data** for recent real-time profiles that have no adjusted fields yet, which is exactly why `expert` was chosen. Nothing in the codebase reads or stores `CHLA_ADJUSTED`, `CHLA_ADJUSTED_QC`, or `CHLA_ADJUSTED_ERROR` at all.
2. **This was flagged once before and never resolved.** `claude_prompts/coding_stage4.md` (2026-06-21) carries the caveat: *"`expert` mode returns raw (non-adjusted) `BBP700`/`CHLA`; for a recent real-time cycle that is the only data available, but CHLA in particular carries the usual real-time uncertainty (no delayed-mode factor-2 / NPQ correction yet)."* That is the only mention of the raw-vs-adjusted distinction (or "NPQ") anywhere in the repo — the default was never revisited.
3. **The schema carries no correction provenance.** The `profiles` table stores only a single coarse, whole-profile `data_mode` (Argo's R/A/D). It does not store the per-**parameter** `PARAMETER_DATA_MODE` that Argo files carry (CHLA and PSAL on the same profile can be in different modes), nor any of the `SCIENTIFIC_CALIB_COMMENT`/`_EQUATION`/`_COEFFICIENT` fields where a DAC documents exactly which adjustment algorithm and reference were applied. So even if the adjusted field had been ingested, there is no column that would let us determine, after the fact, which correction touched a given profile.

**Net:** `mld_summary.chla` — and therefore `chla_argo` in every matchup and report — is built from raw, uncorrected `CHLA`. Answering "is the satellite-based physiological correction present?" requires either (a) external Argo documentation establishing whether the correction in question is a delayed-mode-only procedure (in which case it plausibly affects some, but likely not most, of the 54,031 ingested profiles, since delayed-mode reprocessing lags real-time data by months to years), or (b) a code/re-ingestion change pulling `CHLA_ADJUSTED` plus its calibration metadata alongside the raw field for direct comparison.

**Why this matters for the deep-dive.** The Scientific framing above already flags one chl-specific confound on the *satellite* side (CDOM/detrital absorption aliasing into the Bricaud term). This is a second, independent confound on the *in-situ* side: if the floats' raw Chl carries a known, correctable calibration bias that PAB is not applying, part of any PACE-vs-Argo bias we report could be an artifact of the reference, not the retrieval. It belongs prominently in the report's interpretation section — parallel in stature to the bbp700 depth-mismatch caveat — not in a footnote. See Q9–Q11.

**Data source.** Pull `pab.db` (138 MB) locally and build a single analysis dataframe via `pab.metrics.compare.gather_matchups()` plus joins for `distance_km`, `dtime_hours`, MLD, and `add_strata()` (region/season). The flat `matchup_summary.parquet` lacks all of the geometry/stratification columns, so the DB is needed for most of the figure set anyway; the parquet remains useful for quick scatter/histogram sanity checks.

**Figure set (adapted from bbp700).** All at N ≈ 14.6k, which makes the stratified panels far more meaningful than at run1k's N = 273:

1. **1:1 log-log scatter** — `chl_bing` vs `chla_argo`, colored by relative difference; Spearman ρ, log-space bias/RMS, median ratio annotated. Absorb/generalize the existing `plot_chl_matchup_scatter.py` (fix its hardcoded `/Users/alliejames/...` defaults).
2. **Relative-difference histogram** — (PACE−Argo)/PACE, annotated with % positive and median (defining the headline bias statistic, parallel to bbp700's 84% / +0.35).
3. **Global maps** — static Mollweide (cartopy) + interactive Bokeh HTML, color = relative difference clipped ±1, RdBu_r. Bokeh should still be fine at 14.6k points; verify and thin/decimate only if needed.
4. **Rel-diff vs Δt and vs distance** — scatter + octile-bin medians, to rule matchup geometry in or out.
5. **Rel-diff vs MLD, by season, by basin** — direct analogs of the bbp700 stratification panels.
6. **Quality stratification** — bias in the highest-quality subset (fit chisq and/or granule quality), mirroring the bbp700 data-quality check.
7. **Chl-specific additions (proposed):** rel-diff vs Chl magnitude (retrieval bias is often concentration-dependent); rel-diff vs bbp700 rel-diff per matchup (are the two retrieval biases correlated, i.e., a shared cause?); optionally rel-diff vs fitted CDOM/detrital amplitude (`BING_ExpBPow_Adg`) — a direct probe of the CDOM-confound hypothesis at zero extra data cost.

**Doesn't carry over directly:** `plot_bbp700_vs_temp.py` (bbp–temperature covariation was a bbp-specific angle) — adapt as chl-vs-MLD-temperature only if an early look motivates it.

**OC4 cross-check.** `add_oc_chl()` exists but requires re-reading pixel Rrs from each matchup's PACE granule (network/S3 cost across ~14.6k matchups). Valuable as an independent band-ratio arbiter (does OC4 agree with Argo or with BING?), but proposed as a phase-2 item, possibly on a random subsample first — see Q&A.

**Where things live.** Standalone scripts + PNGs + markdown write-up, following the `pab/matchup/` convention (not part of the `pab` package report pipeline, not on RTD). Given the larger figure set, a subfolder `pab/matchup/chl/` is proposed to avoid crowding the flat directory — see Q&A.

**Deliverable.** A markdown report modeled on `pace_argo_bbp700_bias_analysis.md`: summary, per-figure key observations, an Interpretation section stating and testing hypotheses, and a How-to-Reproduce section. Delivery mechanism to GitHub needs clarification (git is handled by the user) — see Q&A.

**Sequence.**
1. Fetch `pab.db`; build the joined analysis dataframe (matchups + geometry + MLD + strata + fit quality).
2. Core figures: scatter, histogram, maps (items 1–3) → establish the headline bias numbers.
3. Stratification figures (items 4–6) + chl-specific diagnostics (item 7).
4. Draft the markdown report; iterate with JXP.
5. (Optional phase 2) OC4 cross-check on a subsample, expand if informative.

## Q&A

**Q1 — Data source: pull the full `pab.db` from S3, or work off the flat parquet export?**
The parquet is missing `distance_km`, `dtime_hours`, MLD, and region/season strata, so the geometry and stratification figures that mirror bbp700 need the DB regardless. My lean: download `pab.db` locally (138 MB, one-time) and build everything from `gather_matchups()` + joins, keeping the parquet only for quick checks. Any reason to prefer otherwise (e.g., you want the flat export itself extended so others can reproduce without the DB)?

>A. Yes, work from `pab.db`.  But, is there a good reason to have a local copy?  If not, just use the one in s3.
>
>**Claude (Task 2) →** SQLite has no remote/S3 read path — `Store.open()`/pandas
>need an actual file on local disk to query at all, so *some* local copy is
>unavoidable. The real choice is scratch vs. kept: (a) a throwaway download to a
>temp/scratch location, discarded once the figures are made, or (b) a copy kept
>under `$PAB_DATA_DIR`/`data/` so repeat sessions skip the re-pull. My lean:
>scratch by default — no reason to duplicate a 138 MB file that already lives
>durably on S3 (and is backed up to Google Drive). If you expect to iterate on
>this analysis across many sessions, say so and I'll keep it under the data dir
>instead.
>A. Ok, that's fine.  Let's have a local copy on my laptop.  Is there a way to do a check each time to see if the file is up to date with what is in s3?

**Q2 — OC4 cross-check: in scope for this pass?**
`add_oc_chl()` would give an independent band-ratio Chl to arbitrate BING-vs-Argo disagreements, but it requires re-reading pixel Rrs from PACE granules over the network for ~14.6k matchups. My lean: defer to phase 2, or run it on a random subsample (say ~1k matchups) first to see whether it's decisive before paying the full cost. Do you want it in the first report, subsampled, or out of scope?

>A. Defer to phase 2.

**Q3 — Figure scope: full bbp700 set 1:1, curated, or incremental?**
My lean: reproduce the full set minus the bbp-vs-temperature plot, plus the chl-specific additions (rel-diff vs Chl magnitude; chl-bias vs bbp-bias correlation; rel-diff vs fitted CDOM/detrital amplitude if available in fit_results). Alternatively we start with scatter + histogram + maps, look at the headline numbers, and let those steer which stratifications matter. Preference?

>A. Go with your lean.

**Q4 — Where should scripts/figures/report live?**
The bbp700 work sits flat in `pab/matchup/`. At this figure count I'd lean toward a subfolder, `pab/matchup/chl/`, to keep things navigable — but mirroring the flat convention exactly is fine if you prefer consistency. Which?

>A. Yes, generate a sub-folder.

**Q5 — What does "generate a report for GitHub" mean concretely?**
Since git is entirely yours, my lean: I produce a markdown report (modeled on `pace_argo_bbp700_bias_analysis.md`) in the repo, and you commit/push it yourself. Alternatives: a GitHub Issue or Discussion opened via `gh` (confirm that's in scope for me to run), or a PR description. Which delivery mechanism?

>A. Right, we want a markdown report that I will push to GitHub.  Name it `pab_chl_matchups_report.md` and put it in `reports/PAB`. 

**Q6 — The existing `plot_chl_matchup_scatter.py`: absorb or ignore?**
It's a solid starting point for the 1:1 scatter but has hardcoded `/Users/alliejames/...` defaults. My lean: generalize its paths/CLI and absorb it as the scatter script for this work (crediting the original in a comment), rather than writing a parallel script. OK, or should it be left untouched?

>A. Absorb it.

**Q7 — Any specific hypothesis you want prioritized?**
The obvious first question is whether Chl shows a bias with the same sign/ubiquity as bbp700 (PACE high in 84%, median +0.35) — which would hint at a shared cause — or something qualitatively different. If the latter, the CDOM/detrital-absorption confound on the Bricaud term is the natural chl-specific suspect (testable via the fitted CDOM amplitude and regional patterns). Is there a particular mechanism or regional behavior you already suspect and want the figure set designed around?

>A.  No, I have no specific hypothesis.

**Q8 — Interactive map delivery.**
Bokeh HTML at 14.6k points should render fine, but the HTML file will be a few MB and won't display inline on GitHub. Keep it as an internal artifact (opened locally) with only static PNGs in the report? That's my lean.

>A. Keep it as an internal artifact.

**Q9 — Which satellite-based physiological correction do you mean, specifically?**
I could not independently confirm the specific correction from the codebase or its history — the only related note in the repo is the generic Stage-4 caveat about raw `CHLA` lacking the delayed-mode/NPQ adjustments. Can you point me to it (a paper, a DAC processing note, or the Argo BGC recommendation document)? Without that, the most I can state in the report is the finding above — "PAB ingests raw, uncorrected Chl" — not whether or how this particular correction would move `chla_argo`.

>A.  I am going to ask my colleagues in BGC-Argo to provide me with the specific correction and reference.  

**Q10 — Raw-Chl caveat: disclose, or quantify?**
Given `expert` mode was chosen deliberately (the alternatives return zero data for recent real-time profiles), the options are: **(a)** treat this as an out-of-scope caveat, disclosed prominently in the deep-dive report's interpretation section alongside the CDOM confound; or **(b)** a follow-on task to re-ingest with `CHLA_ADJUSTED` + its calibration metadata (`PARAMETER_DATA_MODE`, `SCIENTIFIC_CALIB_*`) stored alongside the raw field, so we can actually quantify how much of the observed bias is attributable to the missing correction. To be clear, (b) is a real scope expansion — a schema change plus a partial re-run, not just another figure. My lean: (a) for this report, with (b) queued as its own task if the headline bias turns out large enough to make the reference calibration a live suspect. Which?

>A.  We are going to make another pass on Argo to add the adjusted Chl-a field.  So, we will do the quantification in the second pass.  

**Q11 — Cheap early signal: stratify the bias by profile-level `data_mode`?**
PAB does already store the coarse whole-profile R/A/D flag. It's a blunt instrument (per-parameter modes can differ), but breaking the headline bias stats out by it is free — no re-ingestion — and delayed-mode profiles get more thorough QC than the R stream even before any satellite-specific correction. If the bias differs visibly between R and D subsets, that's an early hint the reference calibration matters and would sharpen the Q10 decision. My lean: include it as one extra panel/table in the quality-stratification figure. OK?

>A.  Yes, include it as one extra panel/table in the quality-stratification figure.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-03 (Task 1 — read context, surveyed `s3://pab/full/`, drafted a plan + Q&A for the chl-a deep dive)

Read the four context docs (`HOWTO.md`, `PAB_design.md`, `PAB_implementation.md`, and the three prompt-doc logs) plus the full-mission production-run history in `run_full_pipeline.md`/`nautilus_prompts.md` (54,031 profiles → 14,610 matchups → 14,609 fits, `pab_version = "1.0"`, published to `s3://pab/full/`). Listed `s3://pab/full/`: `pab.db` (138 MB), `matchup_summary.csv`/`.parquet` (the flat `gather_matchups()` export — `matchup_id, wmo, cycle, latitude, longitude, time, fit_id, chisq, bbp_argo, chla_argo, bbp_bing(+lo/hi), chl_bing(+lo/hi)`; notably missing matchup geometry, MLD, and region/season strata, which live only in the DB).

Found the bbp700 precedent this task means by "similar figures": a set of standalone scripts + two markdown write-ups in `pab/matchup/` (not part of the `pab` package, not on RTD) — a 1:1 log-log scatter, a relative-difference histogram, static (cartopy/Mollweide) + interactive (Bokeh/CartoDB) global maps, and relative-difference-vs-Δt/distance/MLD/season/basin panels — done by a student collaborator off the smaller `run1k` set (273 matchups). Headline finding there: PACE bbp700 exceeds Argo in 84% of matchups (median +0.35), with the bias present at all magnitudes/geometries, leading to a depth-mismatch hypothesis. Also found an existing (uncommitted, on this branch) `pab/matchup/plot_chl_matchup_scatter.py` — a single chl_bing-vs-chla_argo scatter with hardcoded paths from a different user (`/Users/alliejames/...`) — a starting point, not the full dive.

Per the task, did not start the analysis. Instead used a **Fable** subagent to draft a plan and a set of clarifying questions (reviewed against the codebase before accepting — confirmed `BING_ExpBPow_Adg` exists among the 10 stored fit quantities, so the CDOM-confound question in Q7 is groundable), then wrote both into new **Plan** and **Q&A** sections of this file. The plan: build the analysis dataframe from `pab.db` (not the parquet, which lacks the geometry/strata columns needed for most of the bbp700-style figures), reproduce the bbp700 figure set at the full N≈14.6k (statistically much stronger than run1k's 273), add chl-specific diagnostics (bias vs Chl magnitude, correlation with the bbp700 bias, and a CDOM/detrital-amplitude probe), and defer the OC4 independent cross-check (needs re-reading PACE pixel Rrs over the network) to a later phase or a subsample. Eight open questions posed to JXP: DB vs. parquet as the source; OC4 in/out/subsampled; full vs. curated figure scope; where the code/figures should live (flat in `pab/matchup/` vs. a new `pab/matchup/chl/` subfolder); what "a report for GitHub" concretely means given git is user-only (a committed `.md`, a `gh`-opened Issue/Discussion, or a PR description); whether to absorb/generalize the existing scatter script; any hypothesis JXP wants prioritized; and whether the interactive Bokeh map should stay an internal-only artifact since it won't render inline on GitHub. Learned: the RTD report already carries an aggregate Chl scatter, so this task is explicitly the deeper, internal diagnostic layer behind that existing public one, not a duplicate of it. No code changed.

### 2026-09-03 (Task 2 — reviewed Q1–Q8 answers; investigated Argo Chl-a correction provenance; added Q9–Q11)

Reviewed JXP's answers to Q1–Q8 (DB as source; OC4 deferred to phase 2; full bbp700 figure set minus the temperature plot, plus chl-specific additions; a new `pab/matchup/chl/` subfolder; the deliverable is `reports/PAB/pab_chl_matchups_report.md`, pushed by JXP; absorb `plot_chl_matchup_scatter.py`; no specific hypothesis to prioritize; Bokeh map stays internal-only). Answered Q1's follow-up ("is there a good reason for a local copy?") directly under the answer: SQLite has no remote-read path, so some local copy is unavoidable to query it at all — recommended a throwaway scratch download by default over a kept copy, since the 138 MB file already lives durably on S3 and is backed up to Drive.

Investigated the new item — whether a physiological/satellite-based Chl-a correction that BGC-Argo is reportedly now implementing is visible in the PAB database. Traced the ingestion path (`pab/pipeline.py`, `pab/argo/fetch.py`, `pab/db/schema.py`) and found: (1) the full-mission production run used `PipelineConfig.argo_mode = "expert"` (the actual default), which per `fetch.py`'s own docstring returns Argo's **raw, un-adjusted** parameter values — `standard`/`research` mode would prefer the delayed-mode/adjusted fields but return zero data for recent real-time profiles, which is exactly why `expert` was chosen as the pipeline default; (2) this exact raw-vs-adjusted gap for Chl was already flagged once, in `claude_prompts/coding_stage4.md` (2026-06-21) — "no delayed-mode factor-2 / NPQ correction yet" — and never revisited; (3) a repo-wide search confirmed nothing reads or stores `CHLA_ADJUSTED`/`_QC`/`_ERROR`, and the schema's `profiles` table carries only one coarse whole-profile `data_mode` (R/A/D), not Argo's per-parameter `PARAMETER_DATA_MODE` or any `SCIENTIFIC_CALIB_*` provenance field. Conclusion: **no, the PAB database cannot currently tell us whether this (or any) Chl correction was applied** — `mld_summary.chla`/`chla_argo` is built from raw CHLA throughout, and there is no stored metadata that would let us check after the fact even if it weren't. Used a **Fable** subagent to draft the write-up from these verified facts (checked against the codebase before accepting — did not let it name or guess at a specific correction algorithm, since that wasn't independently confirmable), then added it as a new "Investigation" subsection under Plan → Scientific framing, flagging it as a second, independent confound (this one on the in-situ/Argo side) alongside the already-noted CDOM/Bricaud confound on the satellite side — material enough to belong in the eventual report's interpretation section, not a footnote.

Added three follow-up questions (Q9–Q11): asking JXP to point to the specific correction/reference they mean (not found in the codebase or its history); whether the raw-Chl gap should just be disclosed as a caveat in this report or trigger a separate follow-on task to re-ingest the adjusted field + calibration metadata for direct quantification (flagged as a real scope expansion, not another figure); and whether to add a free, no-re-ingestion-needed stratification of the bias by the existing coarse `data_mode` (R/A/D) as an early, cheap signal. Per the task, did not start the analysis or report. No code changed.
