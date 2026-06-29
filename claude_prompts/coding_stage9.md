# Coding Stage 9 — richer Report: Chl plots, Q&A figures, and context

## Goals

The beta report (4 matchups) is live on Read the Docs. Stage 9 makes the
community Report **more complete and self-explanatory**: interactive Chl plots,
the Argo + PACE quality-assurance (Q&A) figures wired into the pipeline and the
site, and enough narrative that a first-time reader understands *what* was done
and *why* — without bloating git or breaking the no-per-matchup-pages rule.

## Claude

### Skills

Reporting/plotting glue over the existing modules:

- **`plot-bing-fit`** — standardized BING figure conventions (three-panel
  Rrs/a_nw/bb_nw, decomposed a_dg vs a_ph, corner plots) for any new per-matchup
  imagery.
- **`run-bing-fit`** / **`batch-fit-argo`** — only if a task needs to (re)produce
  fits to populate a richer figure; prefer reading the existing store.

### Working agreements (unchanged from Stages 0–8)

- **Git is handled by the user.** Do not run state-changing git commands
  (`add`/`commit`/`push`/branch/merge). Read-only inspection is fine.
- **Python only.** No MATLAB.
- **Reuse, don't reinvent.** Build on the installed `bing`, `ocpy`, `argopy`,
  `remote_sensing` packages and the PAB modules already written. Extend the
  existing stage functions / reporting seams; do **not** re-implement them or copy
  the one-off `bing/papers/biomass/Analysis` scripts.
- **Keep git small by construction.** Only the small aggregate site
  (`report_site/`: `.rst` + `conf.py` + slim `requirements.txt` + ~100 KB
  thumbnails) is committed; bulky per-matchup figures / MCMC chains belong in the
  object store (Nautilus S3, deferred — `HOWTO.md` §7b). New figures must respect
  the `MAX_INLINE_FIGURES` N-guard so the site stays bounded at ~10⁴ matchups.

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md` → *Reporting* (the three tiers: static
  aggregate pages, standalone Bokeh figures as the route to per-matchup detail,
  downloads + manifest) and *Provenance & versioning*.
- **Coding plan** — `docs/design/PAB_coding_plan.md` §Stage 2 (`pab.argo.qa`),
  §Stage 3 (`pab.pace.quality`/`flags` — granule quality assessment), §Stage 7
  (reporting).
- **Implementation record** — `docs/design/PAB_implementation.md` (current state;
  update it at the close of this stage).
- **Task 8 Report** — `claude_prompts/first_runs.md` (Reports → Task 8): the
  status of Chl, the Argo Q&A figures, and the PACE scene quick-looks.
- **Existing seams to extend (all implemented):**
  - `pab.report.rst` — `build_site`, `summary_page`, `aggregates_page`,
    `interactive_figures`, `figure_gallery`, `_gather_with_figures`, the
    `MAX_INLINE_FIGURES`/`FIGURE_URL_COL`/`html_static_path` mechanism.
  - `pab.report.interactive` — `comparison_scatter` (generic `sat_col`/`insitu_col`
    → reuse for Chl), `matchup_map`, `stats_table`, `embed`/`raw_html`.
  - `pab.report.aggregate` / `pab.metrics.compare` — `gather_matchups`
    (`chl_bing`, `chla_argo`), `add_oc_chl` (OC4 `chl_oc` cross-check, not yet
    wired), `log_comparison`, `add_strata`.
  - `pab.argo.qa` — `plot_profile` / `save_profile_qa` (BBP700+CHLA vs pressure,
    MLD marked); **not wired into `ingest`**, no default output dir.
  - `pab.plotting.scene` — `scene_from_store` (PACE scene quick-look PNG); the
    `figure` stage already writes `pipeline/figures/*_scene.png`, but the path is
    **not recorded in the DB** nor linked in the site.
  - `pab.pace.{quality,flags}` — per-granule / local-box flagged-pixel stats.
  - `pab.db.schema` — add columns (e.g. `matchups.scene_path`, a profile QA path)
    if persistence is needed; `pab.pipeline` — the stage runner + `--emit-site`.

## Prompts

1. Execute the first task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below
4. Execute the 4th task in Tasks below
5. Execute the 5th task in Tasks below

## Tasks

1. **Chl Bokeh plots in the online Report.** Add interactive chlorophyll figures
   to the reporting site, mirroring the existing `b_bp` scatter: a
   satellite-vs-in-situ Chl scatter (`chl_bing` vs Argo `chla`) via
   `interactive.comparison_scatter(df, sat_col="chl_bing", insitu_col="chla_argo",
   label="Chl")`, embedded on the summary page beside the `b_bp` scatter, reusing
   the existing hover / tap-to-open / N-guard. Wire the **OC4 band-ratio
   cross-check** (`compare.add_oc_chl` → `chl_oc`) into the gathered frame so the
   Chl comparison can show BING-Chl vs Argo-Chl *and* OC4-Chl (a second series or
   a small companion panel). Add/confirm Chl summary metrics. Add tests; rebuild
   `report_site` with `--emit-site` and verify the Chl figure renders. Log your
   work.

2. **Wire the Argo Q&A plots into the pipeline + Report.** Emit one
   `qa.save_profile_qa` figure per ingested profile (BBP700+CHLA vs pressure, MLD
   marked) — either inside `ingest` or as a dedicated step — writing to a stable
   location (e.g. `outdir/argo_qa/<wmo>_<cycle>.png`) and recording the path so the
   site can reference it (new DB column or a derivable path). Surface them in the
   Report as an N-guarded gallery / link (respecting the no-per-matchup-pages
   rule). Add a `--no-figures`-style guard if appropriate. Tests + rebuild +
   verify. Log your work.

3. **Wire the PACE "scene" Q&A figures into the Report.** The `figure` stage
   already produces `pipeline/figures/*_scene.png` (`plotting.scene`), but the path
   is not recorded nor linked. Persist the scene path (e.g. `matchups.scene_path`
   or alongside `fits.figure_path`) and surface each scene in the site next to its
   matchup (thumbnail and/or tap-to-open from the matchup map). Also consider a
   compact **granule-quality table** (percent flagged pixels in the local box, via
   `pab.pace.{quality,flags}`) so cloudy/glinty scenes are visible to the reader.
   Tests + rebuild + verify. Log your work.

4. **Flesh out the Report's narrative / context.** Expand the methods/landing
   pages so a first-time reader understands what was performed and why:
   - **Overview** — PACE (satellite ocean colour) ↔ BGC-Argo (in-situ floats)
     matchups, and the goal (validate satellite IOP/Chl against in-situ truth).
   - **Data** — PACE OCI L2 AOP `Rrs`; BGC-Argo `BBP700`/`CHLA` via argopy.
   - **Matchup protocol** — Bisson et al. (2019): unflagged pixel box near the
     float + tight time window.
   - **Retrieval** — BING (Prochaska & Frouin 2025): what `b_bp`, Chl, and the
     IOPs are; Chl retrieved from the posterior `Aph` (not an input).
   - **How to read the figures/tables** — the sat/float ratio, Spearman ρ, log10
     bias / RMS / MAD; what hover and tap do.
   - **Caveats & provenance** — dev sample size, out-of-region access, deferred
     BING-vs-NASA-L2-IOP, the `pab_version` stamp + build date, links to
     downloads. Cite BING and Bisson. Keep it concise and reader-facing (this is
     the community site, not the dev docs). Log your work.

5. **Other useful items (propose, confirm, then do).** Pick the high-value ones
   and put any open choices in Q&A first:
   - Link the **download manifest** (chains NPZ + figures, with checksums) from the
     Report so artifacts are reachable.
   - Add a **provenance/build footer** + a `package_versions()` table to the site.
   - A small **coverage/quality summary** (distance & Δtime distributions, flagged-
     pixel %) on the landing page.
   - De-duplicate figure handling between the `figure` stage and `_gather_with_
     figures` (one place that knows fit/scene/QA paths).
   - Update `HOWTO.md` and `docs/reporting.rst` for the new figures/sections, and
     update `docs/design/PAB_implementation.md` at the close of the stage.
   Log your work.

## Q&A

## Reports

### Stage 9

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs
