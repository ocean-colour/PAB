# Chl-a/CDOM Matchup Analysis & Report

## Goals

Build the Chl-a deep-dive figure set and GitHub-facing report agreed in
`claude_prompts/chl_cdom_matchups.md` (Q1–Q8), plus the qualitative/correlative
CDOM comparison (C1–C4) — both now stratified by the DAC/provenance and
adjusted-vs-raw Chl fields populated by the implementation pass. This is the
"second pass" quantification JXP referred to in Q10.

**Precondition:** `claude_prompts/chl_cdom_prompt_1.md` must be complete and
verified — schema v4, CDOM + `_ADJUSTED` + data-mode fields populated, and
`floats.project_name`/`data_center` filled for all 881 floats. Check its
Reports/Logs sections before starting; if the pass is incomplete, stop and say
so rather than working around it.

## Claude

### Skills

None specific — this is analysis/plotting over the existing `pab.db` and
`pab.metrics`/`pab.matchup` seams. No BING fitting is redone.

### Working agreements

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine. JXP will
  push the reports himself.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Mirror the bbp700 analysis scripts and write-up
  in `pab/matchup/`; build the analysis dataframe with
  `pab.metrics.compare.gather_matchups()` + `add_strata()`; absorb/generalize
  the existing rough `pab/matchup/plot_chl_matchup_scatter.py` (fix its
  hardcoded `/Users/alliejames/...` defaults) rather than writing a parallel
  script.
- **Internal figures, GitHub report.** Scripts and markdown write-ups live in
  `pab/matchup/` (a new `pab/matchup/chl/` subfolder), outside the `pab`
  package and NOT published to Read the Docs. The deliverable report goes to
  `reports/PAB/`.
- **CDOM stays qualitative/correlative (C3).** No 1:1 line, no claimed bias
  percentage. Scatter plots and rank correlation are fine. Every CDOM figure
  carries the explicit caveat that Argo CDOM is a fluorescence proxy (ppb
  QSDE) while BING's `Adg` is a *combined* CDOM + detrital absorption
  coefficient (m⁻¹) — do not invent a ppb→absorption conversion.
- **Decisions are already made** (Q1–Q11, C1–C5 in
  `claude_prompts/chl_cdom_matchups.md`). Do not reopen them; raise anything
  genuinely blocking in Q&A below instead of guessing.
- **`pab.db` is local** at `$PAB_DATA_DIR/pab.db` (post-pass, schema v4). Do
  not re-download from S3.

## Context

Read these before running:

- `claude_prompts/chl_cdom_matchups.md` — the full agreed plan: the Plan
  section (figure set, scientific framing, the Sea-Bird CDOM caveat, the
  Chl-correction provenance investigation) and the answered Q&A (Q1–Q11,
  C1–C5).
- `claude_prompts/chl_cdom_prompt_1.md` — the implementation pass this doc
  depends on; its Reports section carries the `CDOM_ADJUSTED` spot-check
  result and the re-ingestion verification numbers.
- `docs/design/PAB_design.md` (v0.5) and `docs/design/PAB_coding_plan.md`
  (v0.2, Stage 10) — the design record for what the pass added.
- `pab/matchup/pace_argo_bbp700_bias_analysis.md` and
  `pab/matchup/pace_argo_bbp700_global_maps.md` — the figure-set precedent to
  mirror: 1:1 log-log scatter, relative-difference histogram, static
  (cartopy/Mollweide) + interactive (Bokeh) global maps, and
  relative-difference vs Δt/distance/MLD/season/basin panels.
- `pab/matchup/plot_chl_matchup_scatter.py` — the rough existing script to
  absorb/generalize.
- `pab/metrics/compare.py` — `gather_matchups`, `add_strata` (and the joins
  for `distance_km`, `dtime_hours`, MLD).

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below

## Tasks

1. **Build the Chl-a figure set.** In a new `pab/matchup/chl/` subfolder,
   reproduce the bbp700 figure set for Chl at N ≈ 14.6k per the agreed plan in
   `chl_cdom_matchups.md`: 1:1 log-log scatter (`chl_bing` vs `chla_argo`),
   relative-difference histogram, static + interactive global maps, and
   stratified panels (Δt, distance, MLD, season, basin), plus the
   chl-specific diagnostics the plan calls for. Add the two comparisons this
   pass made possible: (a) adjusted vs raw Argo Chl (`chla_adjusted` vs
   `chla`, and its effect on the PACE-vs-Argo bias), and (b) stratification by
   DAC/`data_center` (AOML vs the rest). Standalone scripts, internal (not
   RTD). Log your work; raise blocking questions in Q&A rather than guessing.

2. **Build the CDOM figure set.** Qualitative/correlative only, per C1–C4:
   scatter plots of Argo CDOM (raw and adjusted) vs `BING_ExpBPow_Adg`
   *without* 1:1 lines, rank correlation (e.g., Spearman ρ), and
   regional/seasonal pattern panels. Every figure carries the combined-quantity
   caveat (fluorescence ppb QSDE vs combined CDOM+detrital absorption in m⁻¹).
   Note the smaller N (CDOM fleet coverage is ~46% of CHLA's — take what
   there is, per C4). Fold in the Sea-Bird calibration context from the
   `CDOM_ADJUSTED` spot-check reported in `chl_cdom_prompt_1.md`. Log your
   work; raise blocking questions in Q&A rather than guessing.

3. **Draft the Chl-a report.** Write `reports/PAB/pab_chl_matchups_report.md`
   (per Q5), mirroring the structure of the internal bbp700 write-up:
   establish the bias signature first, then test candidate mechanisms — do
   not assume the bbp700 depth-mismatch story carries over. Give the
   in-situ-reference caveats (raw vs adjusted Chl; the correction-provenance
   gap) prominent placement in the interpretation section, not a footnote.
   Include the DAC stratification results. JXP will review and push the report
   himself. Log your work.

4. **Draft the CDOM report.** Write up the CDOM comparison per C3 —
   qualitative/correlative, prominent combined-quantity and Sea-Bird
   calibration caveats. Its home is an open question (see Q&A below): do NOT
   assume a filename or that it is a standalone file — get the Q&A answer
   first, or draft it as a clearly-separable unit that can land either way and
   flag that in your report to JXP. Log your work.

5. **Record what was built.** Once both reports are drafted and reviewed with
   JXP, update `docs/design/PAB_implementation.md` to record what was actually
   built across both passes (the Stage 10 implementation from
   `chl_cdom_prompt_1.md` and this analysis) — per C5, this is the
   "go back and record" step, done last. Log your work.

## Q&A

**Q1 — CDOM report: its own file, or a section of the Chl-a report?**
Q5 pinned `reports/PAB/pab_chl_matchups_report.md` for the Chl-a deliverable,
but no filename was ever set for CDOM. Options: **(a)** a separate
`reports/PAB/pab_cdom_matchups_report.md` — cleaner, since the CDOM comparison
is qualitative-only with its own heavy caveats and much smaller N, and mixing
it into a quantitative bias report risks readers conflating the two; **(b)** a
section within the Chl-a report — one document to push, and the CDOM/detrital
aliasing story is already part of the Chl interpretation. My lean: (a). Which?

>A.

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
