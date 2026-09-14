# Build v2 — Prompt 8: report layer for 2.0 (version-aware metrics, the 1.0-vs-2.0 section, figures, site)

## Goals

Make the report read the v2 database correctly, add the **"1.0 vs 2.0"**
comparison section fed from the frozen v1 database, render the 2.0 fit
figures (scenes reused from v1), and regenerate `report_site/`
(`run_full_inelastic.md` Plan §3 f, §5 step 9; Q7, R7).

## Claude

### Skills

- **`dataviz`** when adding the new comparison figure.

### Working agreements

As in `build_v2_prompt_1.md`. `v1/pab.db` is read **only** via
`ATTACH … AS v1` / a read-only `Store.open(create=False)`. The committed
`report_site/` stays small (thumbnail galleries auto-suppress above
`MAX_INLINE_FIGURES`; interactive Bokeh only below `MAX_INTERACTIVE_MATCHUPS`).

## Context

- Plan §3 f, §5 step 9 of `claude_prompts/v2/run_full_inelastic.md`.
- `pab/metrics/compare.py` (`gather_matchups` filters by `model_pair`
  **only**; `gather_nasa_giop`; `log_comparison`), `pab/report/rst.py`
  (`build_site`, `nasa_giop_section` — the template for a new section;
  `_NASA_BBP_CAVEAT` style for single-sourced wording; `downloads_page`;
  `provenance_block`; `methods_page`), `pab/pipeline.py` (`--emit-site`,
  `--downloads-base-url`), `pab/plotting/fit_fig.py` (robust dispatch from
  Prompt 3), `nautilus/full_figrep_job.yaml` (16 workers / 100 Gi;
  `figure` is memory-bound).
- R7: **fit figures re-rendered for all 2.0 fits; existing scenes reused
  from v1** — `matchups.scene_path` was carried into v2 by the split, so
  `figure` must not re-render a scene whose path exists; scenes are rendered
  only for the backfilled matchups.
- `HOWTO.md` §7a (regenerate + preview: `pab --db … --emit-site report_site`,
  `sphinx-build`).

## Prompts

1. Execute the 1st task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below

## Tasks

1. **Version-aware metrics.** `gather_matchups(store, model_pair=…,
   pab_version=None)` — default to the store's newest BING version and
   filter on it (a test: a store holding 1.0 and 2.0 fits for one matchup
   yields one row); `gather_version_pair(store_v2, v1_path)` → one row per
   matchup with both fits (`bbp700`, `chl`, `aph`, `Bp` where present, χ²),
   joined on `matchup_id` + `pixel_id` via `ATTACH`. The summary page's
   coverage counts must count 2.0 BING fits only. Tests. Log.

2. **"1.0 vs 2.0" section** on the Comparisons page (mirror
   `nasa_giop_section`): what changed (emulator, Raman, Chl fluorescence,
   720 nm, free `B_p`) stated once in a module-level constant; scatters
   `bbp700` / `chl` (2.0 vs 1.0, 1:1 + median-ratio lines; interactive
   below `MAX_INTERACTIVE_MATCHUPS`, static PNG above), `log_comparison`
   stats, a `B_p` posterior-median histogram; the methods page gains the
   2.0 configuration and the two-database provenance (`v1` frozen, `v2`
   this run, `pab_version` semantics); a summary-page headline block.
   `--compare-db PATH` on `--emit-site`; the section returns `""` when
   absent. Tests. Log.

3. **Figures on Nautilus.** `figure` stage: render **fit figures** for every
   BING 2.0 fit; render **scenes only where `scene_path` is NULL**
   (backfilled matchups) — add that guard + test. The chains live on the
   PVC, so this stage runs **in-pod**: upload the current workstation
   `v2/pab.db` to `/data/v2/pab.db` (sha both ends; the PVC copy is the
   writer for this one stage), run `nautilus/v2_figrep_job.yaml`
   (16 workers / 100 Gi, DB-local wrapper, `--stage figure` then
   `--stage report` on `/data/v2`), then copy the DB back and re-lock the
   PVC copy. Log counts (fit figures ≈ 2.0 fits; new scenes ≈ backfilled
   matchups) and wall-clock.

4. **Regenerate the site.** `pab --db $PAB_DATA_DIR/v2/pab.db --emit-site
   report_site --compare-db $PAB_DATA_DIR/v1/pab.db --downloads-base-url
   https://s3-west.nrp-nautilus.io/pab/v2`; `sphinx-build` preview; check:
   coverage counts (matchups ≈ 16.8k, BING fits = 2.0 count), the NASA
   comparison now against 2.0 `bbp700`, the new section, galleries
   suppressed at scale, site size. Do **not** commit. Log the headline
   numbers.

## Q&A

## Reports

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
