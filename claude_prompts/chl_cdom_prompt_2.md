# Chl-a/CDOM Matchup Analysis & Report

## Goals

Build the Chl-a deep-dive figure set and GitHub-facing report agreed in
`claude_prompts/chl_cdom_matchups.md` (Q1–Q8), plus the qualitative/correlative
CDOM comparison (C1–C4) — both now stratified by the DAC/provenance and
adjusted-vs-raw Chl fields populated by the implementation pass. This is the
"second pass" quantification JXP referred to in Q10.

**Precondition:** `claude_prompts/chl_cdom_prompt_1.md` is complete and
verified (status: COMPLETE as of 2026-09-07) — schema v4, CDOM + `_ADJUSTED` +
data-mode fields populated, and `floats.project_name`/`data_center` filled for
873/881 floats (the remaining 8 had every profile fail to re-fetch; fully
reconciled in that doc's Task 4 report — not a defect). Check its Reports/Logs
sections before starting; if something there looks incomplete beyond what's
already explained, stop and say so rather than working around it.

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

### Task 1 — Chl-a figure set: built, verified against `pab.db`

**Where it lives.** New `pab/matchup/chl/` subfolder (per Q4): a shared loader
`data.py` (`load_chl_matchups()` — wraps `gather_matchups()` + `add_strata()`
plus the joins this pass's new fields need: `matchups.distance_km`/`dtime_hours`,
`mld_summary.mld`/`chla_adjusted`/`cdom`/`chla_data_mode`, `floats.data_center`/
`project_name`, `granules.cloud_cover`, and `fit_results` for
`BING_ExpBPow_Adg`), eight figure scripts, and `run_all.py` (the single
command reproducing the full set and printing the headline numbers below).
`plot_chl_matchup_scatter.py` was absorbed per Q6 (hardcoded
`/Users/alliejames/...` paths replaced with `pab.config.DATA_DIR`, rebuilt on
the shared loader for the full N rather than the flat parquet) and removed
from its old flat location — `pab/matchup/chl/plot_chl_scatter.py` is now the
one scatter script, not a parallel copy.

**Data.** `$PAB_DATA_DIR/pab.db` (already local, schema v4, matching the
141,156,352-byte / row-count numbers verified in `chl_cdom_prompt_1.md`'s
Task 6 — no re-download needed). 14,609 matchups carry a BING `ExpBPow` fit;
**9,814 are valid** (finite, positive `chl_bing`/`chla_argo`, |rel_diff| ≤ 1.5
— the same outlier screen the bbp700 precedent used). The ~4.8k dropped
matchups are matchups without a usable Argo Chl-a value at all (NaN/negative),
not a code issue.

**18 figures generated**, all spot-checked visually before accepting:
`chl_pace_vs_argo_scatter.png`, `chl_reldiff_histogram.png`,
`chl_global_map.png` (+ `chl_global_map.html`, Bokeh, internal-only per Q8),
`chl_reldiff_vs_dtime.png`, `chl_reldiff_vs_dist.png`, `chl_reldiff_vs_mld.png`,
`chl_reldiff_seasonal.png`, `chl_reldiff_by_basin.png`,
`chl_reldiff_quality_subset.png`, `chl_reldiff_by_data_mode.png`,
`chl_reldiff_vs_magnitude.png`, `chl_bias_vs_bbp_bias.png`,
`chl_reldiff_vs_adg.png`, `chl_raw_vs_adjusted_argo.png`,
`chl_bias_raw_vs_adjusted.png`, `chl_reldiff_by_dac_aoml.png`,
`chl_reldiff_by_dac_all.png`.

**Headline bias signature — confirmed different from bbp700, as the plan
anticipated (do not assume the depth-mismatch story carries over):**

| | bbp700 (run1k, n=264) | Chl-a (full run, n=9,814) |
|---|---|---|
| % PACE > Argo | 84% | **58%** |
| median rel_diff | +0.35 | **+0.13** |
| Spearman ρ (log-log) | — | 0.78 |

Chl-a shows a real but much weaker/noisier positive bias than bbp700 — a
different failure mode, not the same story at lower amplitude. The scatter
(`chl_pace_vs_argo_scatter.png`) shows PACE systematically low relative to
Argo below the 1:1 line at low Argo Chl-a (~<0.05 mg/m³) and systematically
high above it — a *sign flip with concentration*, not a uniform offset;
`chl_reldiff_vs_magnitude.png` makes this explicit via octile-bin medians.
This concentration-dependence, on its own, already rules out a single
constant multiplicative bias as the whole story — worth leading with in the
Task 3 report rather than the single headline number.

**New diagnostics/comparisons this pass's fields make possible — several
produced non-trivial results worth flagging now, before report drafting:**

- **CDOM/detrital-confound probe (`chl_reldiff_vs_adg.png`):** Spearman
  ρ = **-0.24** between Chl rel-diff and the fitted `BING_ExpBPow_Adg`
  amplitude — a real, if modest, *negative* correlation. Higher fitted
  CDOM+detrital absorption goes with *lower* (more negative) Chl bias, i.e.
  in the octile medians the bias crosses from positive to negative as `Adg`
  rises. This is consistent with (not proof of) the Bricaud-aliasing
  hypothesis in the Plan: some of what BING assigns to `Aph` (→ Chl) in
  low-CDOM water may instead be misattributed to `Adg` in high-CDOM water,
  suppressing the Chl retrieval there.
- **bbp700-bias correlation (`chl_bias_vs_bbp_bias.png`):** ρ = 0.09 —
  essentially uncorrelated. The two BING retrieval biases are **not** a
  shared-cause artifact; whatever drives the bbp700 depth-mismatch bias is
  largely independent of whatever drives the Chl bias.
- **DAC stratification (`chl_reldiff_by_dac_aoml.png`/`_all.png`) — the new
  `floats.data_center` field (Q1(b)):** AOML median **+0.06** (n=5,894) vs.
  all-other-DACs median **+0.25** (n=3,856) — a real, sizeable gap. AOML is
  612/881 floats and dominates this matchup set, so this is not a small-n
  artifact; a genuine calibration/QC-convention difference between AOML and
  the rest of the fleet is a live candidate worth naming in Task 3.
- **Adjusted-vs-raw Argo Chl (`chl_raw_vs_adjusted_argo.png`/
  `chl_bias_raw_vs_adjusted.png`) — the new `chla_adjusted` field, answering
  Q10's deferred second-pass quantification:** median adjusted/raw ratio on
  the reference values themselves, and — more importantly for the bias
  question — **switching the reference to `chla_adjusted` roughly
  quadruples the apparent bias**: median rel_diff goes from **+0.13** (raw,
  same n=9,168) to **+0.58** (adjusted). This is a substantial, unexpected
  finding: the delayed-mode/adjustment correction (largely an NPQ
  correction, per the earlier provenance investigation) pulls Argo Chl-a
  *down*, which — holding the PACE retrieval fixed — makes PACE look
  considerably higher relative to the "corrected" reference. This is
  first-order material for Task 3's interpretation section, parallel in
  weight to the in-situ-reference caveat already flagged in the Plan; it
  does **not** mean bbp700-style depth mismatch is ruled in or out, since NPQ
  affects Chl fluorescence-based measurement specifically, not bbp700.
- **Argo data-mode panel (`chl_reldiff_by_data_mode.png`, per Q11) — now a
  real, populated field** (`chla_data_mode`, not the coarse whole-profile
  `data_mode` that Q11's off-thread correction found to be NULL fleet-wide):
  real-time n=371 (med +0.10), real-time-adjusted n=9,154 (med +0.13),
  delayed-mode n=65 (med +0.31). The delayed-mode subset is small (n=65,
  <1% of the sample) and its higher median should be reported with that
  caveat, not as a confirmed trend.
- **Quality-filtered subset (`chl_reldiff_quality_subset.png`,** cloud cover
  < 50%, BING χ²ᵣ < 1.2): distribution shifts only slightly versus the full
  sample — data-quality filtering is not doing much work here, unlike the
  bbp700 clean-subset finding where the bias *strengthened*.

**No blocking questions raised.** Everything needed (schema v4 fields, DAC
provenance, `pab.db` already local and current) was already in place per
`chl_cdom_prompt_1.md`'s COMPLETE status. `ruff check`/`ruff format --check`
clean on all new files; full suite `pytest pab/tests/` → 192 passed, no
regressions (the new subfolder is standalone scripts, not covered by the
package test suite, per the Working agreements — none of this pass's changes
touch `pab/` package code).

### Task 2 — CDOM figure set: built, verified against `pab.db`

**Where it lives.** New `pab/matchup/cdom/` subfolder (sibling to
`pab/matchup/chl/`, no existing decision pinned this location but it mirrors
the established one-subfolder-per-topic convention and Q1's already-chosen
separate-report-file structure). `data.py` re-exports
`pab.matchup.chl.data.load_chl_matchups()` rather than re-deriving the same
joins — the CDOM population is a strict subset of the same matchup table
(same `cdom`/`cdom_std`/`cdom_data_mode`/`adg_bing` columns Task 1's loader
already carries) — and adds only what's CDOM-specific: `valid_cdom()` and the
two caveat-text constants (`QUANTITY_CAVEAT` per C3, `SEABIRD_CAVEAT` for the
5.62x RAF context). Four figure scripts (`plot_cdom_scatter.py`,
`plot_cdom_regional.py`, `plot_cdom_seasonal.py`, `plot_cdom_map.py`) plus
`run_all.py`.

**Scope note — "raw and adjusted" in the task text vs. what's actually in
`pab.db`.** The task asked for scatter plots of "Argo CDOM (raw and
adjusted)." No `cdom_adjusted` column exists anywhere in the schema: per
`chl_cdom_prompt_1.md`'s Task 1 spot-check, GDAC's `CDOM_ADJUSTED` is empty
fleet-wide (confirmed again here — every one of the 7,083 valid rows has
`cdom_data_mode = 'R'`, zero `'A'`/`'D'`), and per that doc's Q1, JXP
explicitly chose to ingest raw `cdom` only, deferring any Sea-Bird correction
until after a BGC-Argo consult. There is nothing for an "adjusted" panel to
show yet — this isn't a new decision to raise in Q&A, it's the direct,
already-documented consequence of an answer already on record. Every figure
here is raw-only, with `SEABIRD_CAVEAT` stamped on the map noting the ~5.6x
RAF is not applied. Not raised as a blocking question.

**Data.** 7,083 of 14,609 matchups (48.5%) have both a valid raw `cdom` and a
positive fitted `adg_bing` — matches the ~46-48% fleet-coverage expectation
from `pab/argo/BGC_Argo_Coverage_Report.md` and Task 1's report. Basin split:
Atlantic 3,123 / Pacific 2,608 / Indian 808 / Southern 544. Season split:
MAM 2,263 / JJA 1,646 / DJF 1,614 / SON 1,560.

**4 figures generated** (all visually spot-checked; one layout bug found and
fixed — see below): `cdom_vs_adg_scatter.png` (overall log-log scatter, no
1:1 line, Spearman ρ + caveat box), `cdom_vs_adg_by_basin.png` /
`cdom_vs_adg_seasonal.png` (small-multiples, one panel per basin/season, each
with its own ρ), `cdom_global_map.png` (descriptive Mollweide map colored by
raw CDOM magnitude only — not a PACE comparison, since C3 rules out a bias
metric for CDOM).

**Bug found and fixed during review:** the first `cdom_global_map.png` render
had the `SEABIRD_CAVEAT` text (placed via `fig.text` at a fixed figure-fraction
y-coordinate) visually overlapping the horizontal colorbar's own label —
readable-but-ugly, not silently wrong data, but still fixed before accepting:
switched to `cbar.ax.text(...)` anchored to the colorbar's own axes
coordinates, which stays clear of the label regardless of layout. Re-rendered
and re-inspected — clean now. `ruff check`/`ruff format --check` clean after;
full suite `pytest pab/tests/` → 192 passed, no regressions.

**Headline finding — essentially no rank correlation, at any stratification:**

| | n | Spearman ρ |
|---|---|---|
| Overall | 7,083 | **-0.03** (p=0.014 — significant only because of the large n; the effect size is negligible) |
| Atlantic | 3,123 | -0.06 |
| Pacific | 2,608 | **+0.19** |
| Indian | 808 | +0.06 |
| Southern | 544 | -0.09 |
| DJF/MAM/JJA/SON | 1,560-2,263 | -0.03 to -0.06 (SON: +0.01) |

This is a genuine, somewhat surprising result: unlike the Chl-a `Adg`
diagnostic in Task 1 (ρ=-0.24 against the *Chl bias*), here **CDOM itself
barely tracks the fitted combined CDOM+detrital amplitude at all**, globally
or in any basin/season slice — the one partial exception is the Pacific
(ρ=+0.19, still weak). Candidate explanations for Task 4's report to weigh
(not resolved here, per C3's qualitative-only scope): the "combined" nature
of `Adg` (detrital absorption may dominate over the dissolved CDOM signal in
much of the ocean, per JXP's own C3 answer anticipating detritus is
"generally much smaller" — this result is at least not a clean confirmation
of that expectation); the ppb-QSDE-vs-m⁻¹ unit mismatch itself defeating even
rank agreement if the underlying relationship is strongly nonlinear or
threshold-like; or CDOM sensor noise/calibration issues (real-time-only data,
no delayed-mode QC ever applied to any BGC-Argo CDOM record, per Task 1's
fleet-wide finding) swamping a real but weak signal. No basin or season shows
a materially different story — the near-zero correlation is not a regional
or seasonal artifact.

**No blocking questions raised.** Everything needed (schema v4 CDOM fields,
the Task 1 spot-check result) was already in place. `chl_cdom_prompt_1.md`
Task 1's Sea-Bird/RAF-5.62 context is folded in via `SEABIRD_CAVEAT` on the
map figure, per the task's instruction.

### Task 3 — Chl-a report drafted: `reports/PAB/pab_chl_matchups_report.md`

**Structure.** Mirrors `pace_argo_bbp700_bias_analysis.md` (header block,
Summary, Data, per-figure sections with file/image/key-observations,
Interpretation, How to Reproduce, Notes), scaled to this pass's 16 figures
(13 sections, some pairing 2 related files). Per the task, the bias signature
is established first (Figures 1-2) before any candidate mechanism is tested
(Figures 5-14), and the concentration-dependence (Figure 3) is treated as the
headline result rather than the single median number.

**In-situ-reference caveats given prominent placement, per the task's
explicit instruction — not a footnote.** The Summary's second paragraph and
Interpretation point 2 lead with: switching the reference from raw to
`chla_adjusted` Argo Chl-a moves the median bias from +0.13 to +0.58 (n=9,168,
Figure 13) — a bigger swing than any other stratification in the report — and
the correction-provenance gap (no `SCIENTIFIC_CALIB_*` ingested, so neither
raw nor adjusted is an unambiguous ground truth) is stated as an open,
unresolved question the pipeline should address before quoting a tighter bias
number publicly. DAC stratification (Figure 14, AOML +0.06 vs. other-DACs
+0.25) is included and explicitly tied to the same reference-uncertainty
theme (delayed-mode processing is DAC-run, not centralized).

**New synthesis beyond what Task 1's Reports entry already stated** (pulled
together only while writing the report, not previously logged): the MLD trend
(Figure 6, octile medians +0.38 at shallow MLD to -0.55 at the deepest) and
the Southern Ocean's outlier basin median (-0.53, n=1,028, Figure 8) are most
parsimoniously explained as the *same* concentration-dependence effect
(Figure 3) showing through two different stratifications — the Southern
Ocean combines low surface Chl-a with unusually deep mixed layers, both of
which independently push rel_diff negative — rather than as two additional,
independent mechanisms. Framed this explicitly in Interpretation point 4
rather than letting the MLD and basin figures read as separate findings.

**Quality-filter finding corrected from Task 1's looser phrasing.** Task 1's
Reports section described the quality-filtered subset as shifting "only
slightly" versus the full sample; computing the actual medians for the report
(not done precisely in Task 1) found +0.13 -> +0.22 (n=2,023) — a real,
if more modest than bbp700's (+0.35 -> +0.49), strengthening in the same
direction. Corrected in the report itself (Figure 9); not worth a retroactive
edit to Task 1's already-logged entry, since the qualitative conclusion
(quality filtering does not explain away the positive tail) is unchanged.

**Numbers verified freshly, not copied from memory.** Re-ran the full
computation (median/percent-positive/log-bias/median-ratio for the scatter;
exact quality-subset, geometry-octile, DAC, and data-mode medians) directly
against the live `pab.db` before writing, rather than trusting Task 1/2's
already-logged approximate figures — all matched to the precision already
reported, with the quality-subset exception above.

**Image paths verified, not assumed.** The report lives in `reports/PAB/`
while its figures stay in `pab/matchup/chl/` (per the project's
internal-figures/GitHub-report split) — checked all 17 relative image links
(`../../pab/matchup/chl/*.png`) resolve to real files before finishing, since
a broken relative path is the kind of error that survives a visual read of
the markdown source undetected.

**JXP will review and push.** Per the task and this doc's working
agreements, no git command was run; the file was written directly and is
ready for review.

### Task 4 — CDOM report drafted: `reports/PAB/pab_cdom_matchups_report.md` (location provisional — Q1 still unanswered)

**Q1 re-examined and found genuinely unanswered, not just unconfirmed.**
Every other answered question in this doc and in `chl_cdom_matchups.md`
carries actual text after `>A.` (e.g. `>A. (b) fold it in.`). Q1's field
reads only `>A.` with nothing after it — no letter chosen. Task 1's and
Task 2's log entries had described Q1 as "answered... option (a)," which on
this closer look was an overread of a blank field, not a real answer — worth
correcting now since this task's outcome actually depends on it (Task 4's
own instructions anticipated exactly this: "do NOT assume a filename... get
the Q&A answer first, or draft it as a clearly-separable unit that can land
either way"). Did not retroactively edit Task 1/2's log text (historical
record of what was believed at the time), but flagged the correction here
and did not repeat the earlier overread.

**Followed the task's explicit fallback rather than re-assuming (a).**
Drafted `reports/PAB/pab_cdom_matchups_report.md` as a complete,
self-contained document (its own title/header block/sections) with a note at
the very top stating plainly: this is provisional, Q1 is unresolved, the
stated lean in the original question was (a) which is why it lives at this
path for now, and the entire document (minus that note) can be pasted as a
new section into `pab_chl_matchups_report.md` if JXP prefers (b) instead —
no rewrite needed either way. This satisfies the task's "flag that in your
report to JXP" instruction directly in the deliverable, not just in this log.

**Content.** Structured like the Chl-a report but shorter, matching C3's
narrower qualitative/correlative scope: a "why qualitative only" section
up front carrying both required caveats prominently (the ppb-QSDE-vs-m⁻¹
combined-quantity mismatch, and the Sea-Bird RAF-5.62/real-time-only context
from `chl_cdom_prompt_1.md`'s Task 1 spot-check), then Summary, Data, the
four Task 2 figures with observations, Interpretation, How to Reproduce,
Notes. Numbers pulled directly from Task 2's already-verified Reports section
(ρ=-0.03 overall; basin range -0.09 to +0.19; season range -0.06 to +0.01;
n=7,083/48.5%; 100% `cdom_data_mode='R'`) — no new computation needed since
Task 2 already established these precisely.

**One methodological point added that Task 2's log did not state:** Spearman
ρ is invariant under any monotonic increasing transform, so the still-pending
Sea-Bird RAF (a uniform ×5.62 multiplication) would not change any of the
reported correlations if that is the whole correction. Flagged this
explicitly in the Summary and Interpretation so JXP knows this report's
qualitative finding (no meaningful CDOM/`Adg` correlation) does not
necessarily need re-doing once the correction pass happens — only if the
eventual correction turns out to be non-uniform (e.g. the second,
currently-unpublished sensor-reference bias) would it need revisiting.

**Image paths verified** (same pattern as Task 3: report in `reports/PAB/`,
figures in `pab/matchup/cdom/`) — all 4 relative links checked against the
filesystem, not just read visually.

**JXP will review and push; also needs to answer Q1** so this document's
final home is settled — flagged both in the doc itself and here.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-07 (corrected the precondition's DAC-provenance claim)

While reviewing `chl_cdom_prompt_1.md` post-completion (that doc's Task 7), a
Fable-assisted review flagged that this doc's precondition said DAC provenance
was "filled for all 881 floats" — but `chl_cdom_prompt_1.md`'s own Task 4
report establishes the verified reality is **873/881** (8 floats had every
profile fail to re-fetch; fully reconciled there, cross-checked against the
external GDAC index — not a defect). A literal reading of the old text would
have wrongly suggested the implementation pass was incomplete. Corrected the
precondition to state 873/881 with a pointer to the reconciliation, and to
stamp the pass as COMPLETE (matching `chl_cdom_prompt_1.md`'s own new status
note). No analysis started; this is a one-line factual correction only.

### 2026-09-07 (Task 1 — built and ran the Chl-a figure set; verified against `pab.db`)

Checked the Q&A section first: Q1 (CDOM report filename) was answered
(`>A.` — option (a), a separate `reports/PAB/pab_cdom_matchups_report.md`),
relevant to Task 4 later, not this task. No other open questions.

Read the full context set (`chl_cdom_matchups.md`'s Plan + Q1–Q11/C1–C5,
`chl_cdom_prompt_1.md`'s Reports/Logs confirming schema v4 and the verified
row counts, `pace_argo_bbp700_bias_analysis.md`/`_global_maps.md`/
`pace_argo_analysis_figures.md` for the exact bbp700 figure-set precedent —
including finding the actual basin-assignment rule and the seasonal/MLD/basin
plotting code lived inline in `pace_argo_analysis_figures.md`, not in a
standalone script as the task text implied — and `pab/metrics/compare.py` for
`gather_matchups`/`add_strata`). Confirmed `$PAB_DATA_DIR/pab.db` was already
local and current (141,156,352 B, matching `chl_cdom_prompt_1.md`'s Task 6
published checksum-verified size — no re-download needed) and inspected the
live schema/`fit_results` quantities directly (confirmed `BING_ExpBPow_Adg`
exists, `floats.data_center`/`mld_summary.cdom`/`chla_adjusted` are populated
per the prior pass's numbers) before writing any code.

Built `pab/matchup/chl/`: a shared `data.py` loader (`load_chl_matchups()`)
joining `gather_matchups()` + `add_strata()` with the geometry
(`distance_km`/`dtime_hours`), MLD, DAC/provenance
(`floats.data_center`/`project_name`), per-parameter data-mode
(`chla_data_mode`), adjusted-Chl (`chla_adjusted`), CDOM, granule
`cloud_cover`, and fitted `Adg` amplitude fields — reused by every figure
script rather than each re-deriving its own joins (unlike the bbp700
precedent, which had each script query independently; a deliberate small
improvement, not scope creep, since ~10 figures here all need the same
joins). Absorbed `plot_chl_matchup_scatter.py` per Q6 into
`pab/matchup/chl/plot_chl_scatter.py` (hardcoded `/Users/alliejames/...`
paths replaced with `pab.config.DATA_DIR`, rebuilt on the shared loader for
the full N instead of the flat parquet) and deleted the old flat-level
script — it is fully superseded, not left as a parallel copy. Wrote seven
more figure scripts (histogram; static+interactive maps; Δt/distance/MLD/
season/basin stratification; quality/data-mode stratification; the three
chl-specific diagnostics — vs. magnitude, vs. bbp700 bias, vs. `Adg`; the two
new comparisons this pass's fields enable — adjusted-vs-raw Argo Chl, and DAC
stratification) plus `run_all.py` to reproduce the whole set in one command
and print the headline numbers.

Ran the full set against the real `pab.db` (`python -m
pab.matchup.chl.run_all` from the repo root — had to run as a module, not a
bare script path, since `pab` is not pip-installed in `ocean14` and a
bare-script run only puts the script's own directory on `sys.path`). All 18
figures generated cleanly; visually inspected the scatter, histogram, global
map, and every diagnostic/comparison figure before accepting any of them (not
just checking exit codes). `ruff check --fix` + `ruff format` cleaned up
import-order/formatting nits (8 auto-fixed, 0 remaining); re-ran the full set
after reformatting to confirm the numbers didn't move. Full suite `pytest
pab/tests/` → 192 passed, no regressions (expected — this pass touches no
`pab` package code, only new standalone scripts).

Headline finding: **Chl-a's bias signature is real but materially different
from bbp700's**, confirming the Plan's caution not to assume the depth-mismatch
story carries over — 58% PACE>Argo / median +0.13 (n=9,814) vs. bbp700's 84%/
+0.35, and critically the bias **flips sign with Chl-a magnitude** (positive
at high concentration, negative at low), which alone rules out a single
constant-offset explanation. The new fields produced several results
substantial enough to flag now rather than wait for Task 3: a modest negative
correlation (ρ=-0.24) between the bias and the fitted CDOM/detrital amplitude
(consistent with, not proof of, the Bricaud-aliasing hypothesis); essentially
zero correlation with the bbp700 bias (ρ=0.09 — the two retrieval biases are
not a shared-cause artifact); a sizeable AOML-vs-other-DACs gap (+0.06 vs.
+0.25 median); and the most consequential one — switching the Argo reference
from raw to `chla_adjusted` (the delayed-mode/NPQ-corrected field) roughly
quadruples the apparent bias (+0.13 → +0.58 median, same n), a first-order
result for Task 3's interpretation section. Full details, numbers, and all 18
figure filenames are in the new Reports section above. No blocking questions
arose — everything needed was already in place per `chl_cdom_prompt_1.md`'s
COMPLETE status. Did not start Task 2 (CDOM figures), per "execute the 1st
task" — continuing only once instructed.

### 2026-09-07 (Task 2 — built and ran the CDOM figure set; found the "adjusted" wrinkle; fixed a map-layout bug)

Re-checked the Q&A section first, per instruction: Q1 is still just `>A.`
with no new text since Task 1's log entry recorded it — no new answer to
account for.

Built `pab/matchup/cdom/`, reusing `pab.matchup.chl.data.load_chl_matchups()`
rather than writing a second loader — the CDOM matchup population is the
exact same joined table already carrying `cdom`/`cdom_std`/`cdom_data_mode`/
`adg_bing`, just filtered differently, so a separate query set would have been
pure duplication. Added `valid_cdom()` and two caveat-text constants
(`QUANTITY_CAVEAT` for C3's fluorescence-vs-absorption-coefficient distinction,
`SEABIRD_CAVEAT` for the RAF-5.62 context) plus an `add_caveat_box()` helper so
every figure carries the required caveat without repeating boilerplate.

Hit a real scope wrinkle immediately: the task text asks for "Argo CDOM (raw
and adjusted)" scatter plots, but no `cdom_adjusted` column exists in the
schema at all — confirmed directly against the live DB (100% of the 7,083
valid CDOM/Adg matchups show `cdom_data_mode = 'R'`, matching
`chl_cdom_prompt_1.md`'s Task 1 fleet-wide spot-check that GDAC's
`CDOM_ADJUSTED` is empty everywhere, and that doc's Q1 where JXP explicitly
chose "just ingest cdom" pending a BGC-Argo consult on the correction).
Judged this was not a new blocking question — the answer already exists on
record in a sibling doc — so proceeded with raw-only figures and documented
the wrinkle plainly in this doc's Reports section rather than silently
dropping half the task's ask or inventing a correction of my own (which would
have directly contradicted JXP's explicit "not yet" on `chl_cdom_prompt_1.md`
Q1).

Wrote four figure scripts (overall scatter; by-basin and by-season
small-multiples panels; a descriptive global map colored by raw CDOM
magnitude, explicitly not a bias map per C3) plus `run_all.py`. Ran the full
set against the real `pab.db` (`python -m pab.matchup.cdom.run_all`) and
visually inspected every figure before accepting. Found one real bug on
inspection: `cdom_global_map.png`'s Sea-Bird caveat text, placed via a fixed
`fig.text` figure-fraction coordinate, visually overlapped the horizontal
colorbar's own label. Fixed by anchoring the text to the colorbar's own axes
(`cbar.ax.text(...)`) instead of the whole figure, which stays clear of the
label regardless of how the layout shifts; re-rendered and re-inspected to
confirm the fix, not just to assume it worked. `ruff check --fix` + `ruff
format` cleaned up formatting; full suite `pytest pab/tests/` → 192 passed, no
regressions.

Headline finding: CDOM shows **essentially no rank correlation with the
fitted `Adg` amplitude**, overall (ρ=-0.03, n=7,083 — statistically
significant only because of the large n, not practically meaningful) or in
any basin/season slice (Pacific the mild exception at ρ=+0.19; everything
else within ±0.09 of zero). This is notably weaker than the Chl-a-bias-vs-Adg
correlation found in Task 1 (ρ=-0.24) — a different, and on its face more
surprising, result: the two BING-fitted quantities that supposedly share a
physical basis with CDOM (the Chl retrieval's bias, and `Adg` itself) relate
to actual in-situ CDOM quite differently. Documented several candidate
explanations for Task 4 to weigh (detrital dominance in the "combined" `Adg`
term, unit-mismatch nonlinearity, or CDOM's real-time-only/never-QC'd data
stream) without resolving which — that's out of scope for a qualitative
comparison pass. Full numbers and figure filenames are in the new Reports
section above. No blocking questions raised. Did not start Task 3 (Chl-a
report drafting), per "execute the 2nd task" — continuing only once
instructed.

### 2026-09-07 (Task 3 — drafted `reports/PAB/pab_chl_matchups_report.md`)

Re-checked the Q&A section first: Q1 unchanged (still just `>A.`) — no new
answer, and not relevant to this task anyway (it's about the CDOM report's
home, Task 4's concern).

Before writing, re-ran the full set of headline statistics directly against
the live `pab.db` rather than relying on Task 1/2's already-logged numbers
from memory — confirmed all matched to the precision previously reported,
except the data-quality-subset median, which Task 1 had only described
qualitatively ("shifts only slightly"); computing it precisely for the report
found +0.13 → +0.22 (n=2,023), a real strengthening in the same direction as
bbp700's clean-subset finding (+0.35 → +0.49), just more modest — corrected
in the report's Figure 9 section rather than leaving the vaguer framing
stand uncorrected in a document JXP will actually read.

Drafted `reports/PAB/pab_chl_matchups_report.md` mirroring
`pace_argo_bbp700_bias_analysis.md`'s structure (header block, Summary, Data,
16 figures across 14 sections, Interpretation, How to Reproduce, Notes), per
Q5's filename. Followed the task's explicit sequencing instruction —
established the bias signature first (headline histogram/scatter, Figures
1-2) before testing candidate mechanisms (Figures 5-14) — and did not assume
the bbp700 depth-mismatch story carries over; instead let the data argue for
it or against it (Interpretation point 4: the Chl/bbp700 biases are
essentially uncorrelated, ρ=0.09, and the Chl MLD trend is better explained as
a concentration-dependence proxy than an independent depth effect, unlike
bbp700's flat MLD relationship).

Gave the two in-situ-reference caveats (raw-vs-adjusted Chl; the
correction-provenance gap) the prominent placement the task asked for —
second paragraph of the Summary and the lead point of the Interpretation,
not a footnote — since the adjusted-reference swing (+0.13 → +0.58) is
larger than every other stratification in the report combined. Included the
DAC stratification (Figure 14) as asked, and explicitly tied it to the same
reference-uncertainty theme rather than presenting it as an unrelated finding
(delayed-mode processing is DAC-run, not centralized, so cross-DAC bias
differences and reference-choice uncertainty are plausibly the same
underlying issue).

Synthesized two connections across figures that no single prior Task 1/2 log
entry had stated: the MLD trend (Figure 6) and the Southern Ocean's outlier
basin median (Figure 8, -0.53) both plausibly reduce to the same
concentration-dependence effect (Figure 3) — deep MLD and the Southern Ocean
both co-locate with low-Chl-a water in this matchup population — rather than
being two additional independent mechanisms. Framed this explicitly so the
report doesn't read as a list of disconnected stratification results.

Verified every one of the 17 relative image links
(`../../pab/matchup/chl/*.png`, since the report lives in `reports/PAB/` while
figures stay in `pab/matchup/chl/`) resolves to a real file with a direct
filesystem check, rather than trusting the markdown source looked right by
eye. No code changed. Per the working agreements, did not run any git
command — the file is written and ready for JXP's review/push. Did not start
Task 4 (CDOM report), per "execute the 3rd task" — continuing only once
instructed.

### 2026-09-07 (Task 4 — drafted `reports/PAB/pab_cdom_matchups_report.md`; found Q1 was never actually answered)

Re-checked the Q&A section first, as instructed, and this time it mattered:
Q1's field is `>A.` with no letter after it — literally blank, unlike every
other answered question in this document (all of which have real text after
`>A.`). Task 1's and Task 2's log entries had both described Q1 as "answered
(option a)," which in retrospect was reading too much into an empty
placeholder. This task's own text anticipated exactly this possibility
("do NOT assume a filename... draft it as a clearly-separable unit that can
land either way and flag that in your report to JXP"), so rather than
silently repeating the earlier assumption, treated Q1 as genuinely open.

Drafted `reports/PAB/pab_cdom_matchups_report.md` as a fully self-contained
document — its own title, header block, and section structure — with an
explicit note at the top stating the location is provisional pending JXP's
answer to Q1, naming the stated lean (a, a separate file) as the reason it
lives at this path for now, and stating plainly that the whole document
(minus that note) can be pasted into the Chl-a report as a new section if
JXP prefers (b), with no rewrite needed either way. This puts the flag where
the task asked for it — in the deliverable itself, not just buried in this
log.

Content followed C3's narrower qualitative/correlative scope: a leading
section restating both required caveats (the ppb-QSDE-vs-m⁻¹ unit mismatch,
and the Sea-Bird RAF-5.62/real-time-only calibration context), then the same
Summary/Data/Figures/Interpretation/Reproduce/Notes shape as the Chl-a
report, sized down to the four Task 2 figures. Reused Task 2's already-
verified numbers directly (overall ρ=-0.03; per-basin -0.09 to +0.19;
per-season -0.06 to +0.01; n=7,083 of 14,609, 48.5%) rather than
recomputing, since Task 2's Reports section already established them
precisely against the live DB.

Added one point not previously logged: Spearman ρ is invariant under a
uniform multiplicative rescaling, so the still-pending Sea-Bird RAF
correction (×5.62 on every raw value) — if that turns out to be the whole
correction — would not change any correlation number in this report.
Flagged this explicitly so JXP doesn't read this report as needing an
automatic re-run once the correction lands; only a *non-uniform* correction
(e.g. the second, still-unpublished sensor-reference bias) would require
revisiting the conclusion.

Verified all 4 relative image links (`../../pab/matchup/cdom/*.png`) resolve
against the filesystem before finishing. No code changed. Per the working
agreements, ran no git command — the file is written and ready for JXP's
review. Two things now genuinely need JXP's input before Task 5: reviewing
both reports, and answering Q1 so this document's final home is settled.
Did not start Task 5 (recording what was built in `PAB_implementation.md`),
per "execute the 4th task" and per Task 5's own gate ("once both reports are
drafted and reviewed with JXP") — continuing only once instructed.