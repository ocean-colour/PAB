# Database PR

## Goals

We are going to review and improve the PR on the `database` branch.

## Prompts

1. We have submitted a PR for the `database` branch.  Please review the PR and provide feedback on GitHub.  Use my `profxj` account to do so.  Use Fable if you can.  Log your work.
If you have any questions, ask them in the Q&A section below.

## Q&A

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-09-08 (Reviewed PR #10 `database` and posted feedback on GitHub)

**Task:** Review the open PR on the `database` branch (PR #10, "Database", author
`alliejames`) and post feedback to GitHub as `profxj`. The Q&A section of
`claude_prompts/database.md` was empty, so no user answers modified the task.

**What was done:**

- Confirmed `gh` was authenticated as `profxj` and that PR #10 had no prior
  reviews (only a `@cursor review` request that failed with an account
  mismatch). The PR is +2220/-0 across 25 files: 4 plotting scripts, 7 new
  markdown reports, 11 PNGs, 1 Bokeh HTML, `read_pab_db.py`, and a
  `start_up.md` log entry.
- Reviewed the diff against the existing codebase conventions
  (`pab/config.py`, `pab/db/schema.py`, `pab/metrics/compare.py`,
  `pab/pipeline.py`, `ruff.toml`, `setup.py`), then dispatched a **Fable**
  subagent to independently verify each concrete claim before posting. That
  verification pass corrected one of my claims and surfaced a bug I had
  missed.
- Posted the review with `gh pr review 10 --comment`.

**Principal findings (blocking first):**

1. **Committed results are not reproducible.** Only 3 of 11 figures have a
   generating script in the repo. Six scripts are cited by path in the docs
   but do not exist anywhere: `make_analysis_figures.py`,
   `plot_bbp_matchup_map_global.py`, `plot_bbp_matchup_map_bokeh_global.py`,
   and three under a `pab/modis/` package that was never added.
   `pace_argo_analysis_figures.md` pastes the plotting code into fenced
   markdown blocks, so the logic behind seven figures lives only as prose.
2. **Hardcoded `/Users/alliejames/Documents/summer 2026/...` defaults** in all
   four plotting scripts, despite `pab.config.DATA_DIR` (env-overridable)
   already being the project convention used by `pab/pipeline.py:888`.
3. **Runtime bugs:** `read_pab_db.py:33` selects `id, time` from `granules`,
   which has neither column (`granule_id`, `time_start`, `time_end`) — an
   uncaught `OperationalError` that kills the script mid-run;
   `plot_bbp700_vs_temp.py:71` indexes a two-entry `wmo_names` dict directly,
   so it `KeyError`s on any of the other 243 floats; the `LEFT JOIN matchups`
   in the same file duplicates points for multi-granule profiles.
4. **χ²ᵣ threshold appears as three different values in one file**
   (docstring 1.0, argparse 1.2, function signature 1.0), so calling
   `plot_clean_map()` programmatically silently fails to reproduce the
   committed figure and the "39 of 264" number.
5. **Scientific/metric points:** the relative difference is normalized by the
   *satellite* value, `(PACE − Argo)/PACE`, rather than the in-situ reference,
   which bounds the positive tail in [0,1) (hence the ±1 clipping on the
   global maps) and diverges from `pab.metrics.compare.log_comparison`.

**What I learned:**

- The docs **contradict each other on the headline conclusion**:
  `bias_analysis.md` and `global_maps.md` call depth-sampling mismatch the
  leading explanation for the +0.35 bias, while
  `pace_argo_analysis_figures.md` finds flat rel-diff-vs-MLD quintile medians
  and argues *against* it. Valid-matchup denominators also drift (264 vs 262
  vs 273 total). Flagged as the most interesting unresolved result in the PR.
- The `clean_subset.md` argument is the strongest part of the submission: the
  bias *grows* to +0.49 under the strict quality cuts, which is real evidence
  that the offset is physical rather than a retrieval artifact. Said so in the
  review — the problem is reproducibility, not the science.
- Verifying claims with a second model before posting was worth it: it caught
  that `read_pab_db.py` uses a *relative* path (not absolute, as I had
  written) and found the `granules` column bug independently.
