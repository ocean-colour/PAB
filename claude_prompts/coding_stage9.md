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
8. Execute the 8th task in Tasks below


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

3. **Debug.** I ran the `pab --stage ingest --replace` as per your direction.  It crashed.  The log is in the file `Oceanography/python/PAB/bugs/replace_crash.txt`.  Please examine and try to fix.  

4. **Wire the PACE "scene" Q&A figures into the Report.** The `figure` stage
   already produces `pipeline/figures/*_scene.png` (`plotting.scene`), but the path
   is not recorded nor linked. Persist the scene path (e.g. `matchups.scene_path`
   or alongside `fits.figure_path`) and surface each scene in the site next to its
   matchup (thumbnail and/or tap-to-open from the matchup map). Also consider a
   compact **granule-quality table** (percent flagged pixels in the local box, via
   `pab.pace.{quality,flags}`) so cloudy/glinty scenes are visible to the reader.
   Tests + rebuild + verify. Log your work.

5. **Flesh out the Report's narrative / context.** Expand the methods/landing
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

6. **Other useful items (propose, confirm, then do).** Pick the high-value ones
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

7. **More.**  Please add a nice description of what PAB is and so on for the front of the Reporting site on RTD.  You can draw from the other RTD docs.  Log your work.  You can do all of your work without asking me for permission.

8. **Reformat.**  This looks great, but the matchup results are a bit much.  Can we break them up into separate sub-web-pages?  Please do.  Log your work

## Q&A

**Note (Task 5 numbering):** the Tasks list has *two* entries numbered "5" — the
narrative/context task and an "Other useful items" task. I read prompt 5 as the
**narrative/context** task (the 5th task block in order) and executed that; the
"Other useful items" block is treated as a separate, later task. Flag if you meant
the other one.

**Q (Task 6 — download manifest links):** the other Task-6 items are done
(provenance block, coverage stats, figure-copy de-dup, docs). I held back the
**"link the download manifest from the Report"** item because it needs a decision:
the bulky artifacts (per-matchup MCMC chains, figures) are meant for the **Nautilus
S3** object store, which is **deferred/not wired** (`HOWTO.md` §7b), so there are no
public URLs to link yet. Options:

- **A (recommended, now):** add a **Downloads** section linking only the small,
  already-committed **summary tables** (`matchup_summary.csv`/`.parquet`, copied
  into `_static/downloads/`), and *describe* the chains/figures as
  object-store artifacts coming once S3 is live. Keeps git small.
- **B:** wait for S3 activation, then link the real manifest URLs (chains +
  figures + tables) with checksums. Fully deferred.
- **C:** also commit the per-matchup chains/figures into the repo and link them —
  **not recommended** (violates the keep-git-small rule at scale).

Which would you like? (My pick: **A** now, **B** later.)

**A (done).** Implemented option A — see the 2026-07-01 (Downloads) log entry.

## Reports

### Stage 9

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-06-29 (Task 1 — Chl Bokeh plots in the Report)

Added the interactive **chlorophyll** figure to the reporting site, beside the
existing `b_bp` scatter. Changes:

- `pab/report/interactive.py`: gave `comparison_scatter` an optional `extra_series`
  (`[(col, legend_label), …]`) that overlays additional satellite series against
  the same in-situ x-axis (used for OC4 Chl), labelling the primary glyph too so
  the sources are distinguishable; widened the 1:1-line span to cover overlays;
  added `chla_argo` + `chl_oc` to `HOVER_FIELDS`. Backward compatible — the `b_bp`
  call (no `extra_series`) is unchanged.
- `pab/report/rst.py`: `interactive_figures` now also emits a Chl scatter via a new
  `_chl_scatter` helper (`chl_bing` vs Argo `chla`, OC4 `chl_oc` overlaid when
  present), guarded to return `None` when there is no finite Chl pair. Threaded an
  `opener` seam through `build_site` → `_gather_with_figures`, which calls
  `compare.add_oc_chl` (best-effort, exception-guarded) to add `chl_oc` only when
  an opener is supplied.
- `pab/pipeline.py`: `report(store, config, *, opener=None)` (so `run` forwards the
  opener like other stages) passes it to `build_site`; the `--emit-site` path
  builds a `cached_opener` when `--download` is set, so the OC4 cross-check can be
  populated from the local granule cache without slow out-of-region reads.

Tests (`test_report.py`): `test_build_site_embeds_chl_scatter` (both scatters on
the landing page) and `test_comparison_scatter_oc4_overlay` (OC4 legend present);
**29 passed**. Rebuilt `report_site` via `--emit-site` and confirmed the Chl
scatter is embedded and renders in the built HTML (`satellite vs in-situ Chl`).

Key learning / decision: OC4 (`add_oc_chl`) re-reads each matchup's pixel `Rrs`
through a granule opener, so running it during the report build risks the same
out-of-region hang as the `match` stage. I made it **opt-in via the `opener`
seam** (network-free by default; `--emit-site --download` uses the local cache),
rather than always-on. The BING-Chl-vs-Argo scatter needs no network and is the
guaranteed deliverable; OC4 is an overlay that appears only once `chl_oc` is
populated. `ocpy` is not installed in this env, so the OC4 overlay is covered by a
synthetic-`chl_oc` unit test rather than a live rebuild. A cleaner future option is
to persist `chl_oc` (e.g. as a `fit_result` quantity) during a stage that already
holds the opener, so the report stays purely DB-driven.

### 2026-06-29 (Task 2 — Argo Q&A plots wired into pipeline + Report)

Wired the per-profile Argo Q&A figures (BBP700/CHLA vs pressure, MLD marked) end
to end. Key constraint discovered: `qa.plot_profile` needs the **full profile
arrays**, which exist only on the **live argopy fetch** path — the
precomputed-summary path (and the dev DB) carry scalars only. So QA generation
lives in `ingest`'s live branch, not as a post-hoc step over the DB.

Changes:
- **Schema** (`pab/db/schema.py`): added `mld_summary.qa_path TEXT`, bumped
  `SCHEMA_VERSION` 1→2, and registered `MIGRATIONS[1] = _v1_to_v2`
  (`ALTER TABLE … ADD COLUMN qa_path`). Verified on a copy of the real dev DB:
  migrates v1→v2 additively, all 10 profiles / 4 matchups intact, `qa_path` NULL.
- **ingest** (`pab/pipeline.py`): new `_emit_profile_qa(...)` — gated on
  `config.make_figures` (so `--no-figures` skips it), fully exception-guarded,
  renders to `config.out()/argo_qa/<wmo>_<cycle>.png` and records the path via
  `UPDATE mld_summary SET qa_path`. Called from the live-fetch branch with the
  in-hand `PRES`/`BBP700`/`CHLA` arrays + the summary MLD.
- **Report** (`pab/report/rst.py`): refactored the gallery into a shared
  `_thumbnail_gallery(items, …)` (N-guarded by `MAX_INLINE_FIGURES`); reused it for
  the existing `figure_gallery` and a new `argo_qa_gallery(store, outdir)` that
  copies each recorded `qa_path` into `_static/argo_qa/` and links it. `build_site`
  now appends the QA gallery to the summary page.

Tests: `test_db` migration adds `qa_path`; `test_pipeline` QA emit writes+records
and respects `--no-figures`; `test_report` QA gallery copies+links and is empty
without paths. **126 passed** (only the pre-existing, unrelated `earthaccess`
import test still fails). Rebuilt `report_site` — builds clean; the QA gallery is
correctly absent because the current dev DB predates QA wiring (`qa_path` all NULL).

Operator note for actually populating it: in the full env (with argopy), re-run
`pab --stage ingest --replace` to fetch profiles and emit/record QA figures, then
`pab --emit-site report_site` to copy them into the site and commit. Cannot be
demonstrated live here (argopy not installed); covered by unit tests with synthetic
arrays instead. HOWTO/docs updates deferred to Task 5.

### 2026-06-30 (Task 3 — fixed the `ingest --replace` core dump)

`pab --stage ingest --replace` crashed in the user's full env (`bugs/replace_crash.txt`).
The argopy lines were just warnings; the fatal part was an **interactive Matplotlib
(Tk) backend** crash: `RuntimeError: main thread is not in main loop` →
`Tcl_AsyncDelete: async handler deleted by the wrong thread` → `Aborted (core
dumped)`. Root cause: **no PAB plotting module set a non-interactive backend** —
they all just `import matplotlib.pyplot`, so the default (TkAgg on the user's
machine) was used. My Task-2 change made `ingest` render Q&A figures *while
argopy's worker threads run*, so Tk objects were torn down on the wrong thread and
aborted the process. (The `figure` stage hadn't tripped this because no argopy
threads run alongside it; `qa.py`'s docstring already *claimed* a non-interactive
backend but never enforced it.)

Fix (two layers): (1) `pab/__init__.py` sets `os.environ.setdefault("MPLBACKEND",
"Agg")` before Matplotlib is ever imported — a central headless default for the
whole package (also hardens `fit_fig`/`scene`/`population`); (2) `pab/argo/qa.py`
explicitly `matplotlib.use("Agg")` before importing pyplot — import-order-proof and
honouring its own docstring. Added `test_qa_uses_headless_backend` (asserts
`MPLBACKEND==Agg` and `matplotlib.get_backend()=="agg"`). Verified a fresh
`import pab` yields the Agg backend; **63 passed** in the argo/pipeline/report/db
suites. With Agg no Tk objects are created, so the teardown abort cannot recur.
The user can now re-run `pab --stage ingest --replace`.

Key learning: a library that renders figures in batch — and especially one that
plots alongside another library's threads (argopy) — must pin a non-interactive
backend; relying on the Matplotlib default is a latent core-dump waiting for the
first machine whose default is interactive.

### 2026-06-30 (Task 4 — PACE scene quick-looks + matchup-quality table)

Wired the PACE scene quick-looks into the Report and added a network-free
per-matchup quality table.

- **Schema** (`pab/db/schema.py`): added `matchups.scene_path TEXT`, bumped
  `SCHEMA_VERSION` 2→3, registered `MIGRATIONS[2] = _v2_to_v3`
  (`ALTER TABLE matchups ADD COLUMN scene_path`).
- **figure stage** (`pab/pipeline.py`): capture `scene_from_store`'s returned path
  and record it (`UPDATE matchups SET scene_path`). Plus a **cheap backfill** in
  the skip branch — a plain `pab --stage figure` (no `--replace`, no bing, no
  granule) records an already-on-disk `figures/<matchup_id>_scene.png` into a NULL
  `scene_path`, so existing runs surface scenes without re-rendering.
- **Report** (`pab/report/rst.py`): `scene_gallery(store, outdir)` (mirrors the
  QA/fit galleries — copies `scene_path` into `_static/scenes/`, N-guarded) and
  `matchup_quality_table(store)` (per-matchup wmo/cycle, distance_km, dtime_hours,
  n_spectra — straight from the DB). `build_site` appends the scene gallery to the
  summary page and the quality table to the aggregates page.

Tests: migration test now covers v1→v3 (qa_path + scene_path); added scene-gallery
(copy/empty), matchup-quality-table, and figure-stage scene backfill tests.
**131 passed** (only the pre-existing `earthaccess` test fails).

Verified end-to-end on the real `Color/PAB` DB (no bing/network): ran
`pab --stage figure` → backfilled all 4 `scene_path`s from existing PNGs;
`--emit-site report_site` → the summary now shows b_bp + Chl scatters, **4 PACE
scene quick-looks**, 4 fit thumbnails, and the aggregates page shows the matchup
quality table; `sphinx-build` clean.

Scope call: there is **no `pab.pace.quality` module** — only `flags.py`, whose
flagged-pixel-% over the local box needs a granule re-read (the same out-of-region
hazard as OC4). So I delivered the network-free distance/Δt/n_spectra table (the
scene quick-looks already make cloudy/glinty scenes visible to the reader), and
deferred a flagged-% column as a network-dependent follow-up.

State note (two-DB split from the prior turn persists): the rebuilt `report_site`
now has scenes + both scatters + quality table, but **Argo Q&A is absent** because
`Color/PAB`'s `qa_path` is empty (QA was generated against `data/pab.db`). The
clean full report still needs, in the full env: `export PAB_DATA_DIR=…/Color/PAB`
then `pab --stage ingest --replace` (populate qa_path) → `pab --stage figure`
(scene_path, already done) → `pab --emit-site report_site`. The regen self-heals
the orphaned `_static/argo_qa/*.png` (same `<wmo>_<cycle>.png` names).

### 2026-06-30 (Task 5 — fleshed out the Report narrative/context)

Expanded the community site so a first-time reader understands what was done and
why (the two "Task 5" entries — flagged in Q&A; executed the narrative one).

- `summary_page` (`pab/report/rst.py`): added an **Overview** paragraph after the
  provenance line — PAB validates PACE/OCI retrievals against BGC-Argo floats;
  the one-line pipeline (nearest scene → extract ``Rrs`` → BING → compare ``b_bp``
  & Chl); pointer to the figures and Methods. Kept the Coverage/headline metrics
  (and the `Matchups:`/`median sat/float ratio` strings the tests pin).
- `methods_page`: rewrote the one-paragraph stub into reader-facing sections —
  **Data** (PACE OCI L2 AOP ``Rrs`` via earthaccess; BGC-Argo ``BBP700``/``CHLA``
  via argopy), **Matchup protocol** (Bisson 2019: unflagged pixel box + tight time
  window; zero-matchup profiles are expected), **Retrieval (BING)** (what ``b_bp``,
  Chl and the IOPs are; Chl from posterior ``Aph``, not an input; OC4 cross-check),
  **How to read the figures & metrics** (1:1 line, hover/tap, median ratio /
  Spearman ρ / log10 bias·RMS·MAD), **Caveats & provenance** (sample size,
  out-of-region access, deferred NASA-IOP, `pab_version` + build-date stamp,
  downloads), and **References** (BING; Bisson 2019).

Both pages stay pure string builders. Tests: report suite **22 passed**; rebuilt
`report_site` and confirmed every new section renders and `sphinx-build` is clean.

Care taken: kept the project's own BING phrasing ("Bayesian inference with Gordon
coefficients") rather than inventing a backronym, and the ``Chl = 10**Aph /
0.05582`` relation matches the implementation — no fabricated DOIs/journal details
in the references (author/year only), since I couldn't verify them.

### 2026-07-01 (Task 6 — provenance, coverage, de-dup, docs)

Did the high-value "other useful items"; left one for a decision (Q&A).

- **Provenance block** (`pab/report/rst.py:provenance_block`): `pab_version` +
  build date + a `pab.config.package_versions()` table (static list-table — always
  renders), appended to the methods page by `build_site`.
- **Coverage stats**: `summary_page` now shows profiles ingested + **median
  separation (km)** and **median Δtime (h)** from the matchups (network-free).
- **De-dup (#4)**: extracted `_stage_static(src, outdir, subdir)` — the single
  copy-into-`_static` + URL helper now shared by `_gather_with_figures`,
  `scene_gallery`, and `argo_qa_gallery` (removed three near-identical loops).
- **Docs (#5)**: `docs/reporting.rst` (Chl/OC4 scatter, scene/QA galleries, quality
  table, provenance), `HOWTO.md` §5 Outputs (new site sections + `argo_qa/` +
  scene backfill), and a **Stage 9** close-out section in
  `docs/design/PAB_implementation.md` (headless fix, schema v3, Q&A wiring, report
  additions, `--emit-site`).

Tests: added provenance-block, methods-has-provenance, and summary-coverage-stats
cases; **134 passed** (only the pre-existing `earthaccess` test fails). Rebuilt
`report_site` and confirmed the Provenance block + coverage medians render and
`sphinx-build` is clean.

Held for a decision (Q&A): **linking the download manifest**. Bulky artifacts
(chains, figures) target the deferred Nautilus S3, so there are no public URLs yet;
proposed adding a Downloads section for the small summary tables now (option A) and
the full manifest once S3 is live (option B). Awaiting the user's pick before
implementing.

### 2026-07-01 (Task 6 — Downloads section, option A)

User picked **A**. Added `pab/report/rst.py:downloads_block(store, outdir)`: stages
the summary tables via `publish.export_tables` into `_static/downloads/`
(`matchup_summary.csv` always; `.parquet` best-effort) and links them with raw-HTML
relative anchors (no docutils link-resolution quirks); notes that the bulky
per-matchup chains/figures are object-store (Nautilus S3) artifacts keyed by
`matchup_id`, available once that backend is wired. `build_site` appends it to the
summary page. Best-effort (export failure never breaks the build).

Test `test_downloads_block_stages_tables` (CSV staged + linked + S3 note);
**135 passed** (only the pre-existing `earthaccess` test fails). Rebuilt
`report_site` — Downloads section renders, CSV + Parquet staged under
`_static/downloads/`, links resolve in the built HTML, `sphinx-build` clean with no
warnings. This closes the Stage 9 "other useful items"; the only remaining
real-world step is the DB reconciliation (`ingest --replace` with `$PAB_DATA_DIR`
set) so the published report also shows the Argo Q&A gallery.

### 2026-07-01 (Task 7 — front-page description of PAB)

Rewrote the reporting-site front page (`pab/report/rst.py:index_page`) from a bare
title+toctree into a reader-facing description of PAB, drawing phrasing from the
in-repo docs (`docs/index.rst`, `docs/design/PAB_design.md`, `docs/reporting.rst`):
a one-line what-it-is, a **Why** (satellite ocean-colour retrievals need in-situ
validation; BGC-Argo provides it), a numbered **What PAB does** (match → extract
``Rrs`` → BING → compare), and a **What's on this site** guide to the Summary /
Aggregate results / Methods pages plus the provenance/downloads note. Made the
toctree ``:hidden:`` so the prose reads cleanly while the pages stay linked (RTD
theme keeps them in the sidebar) — no orphan warnings.

Test `test_index_page_has_description_and_toctree`; **27** report tests pass.
Rebuilt `report_site` and confirmed the front page renders the title
("PAB — PACE ↔ BGC-Argo Matchups") and the Why / What PAB does / What's-on-this-site
sections, with `sphinx-build` clean (no warnings). No fabrication — all claims are
drawn from existing repo docs. This completes the Stage 9 task list.

### 2026-07-01 (Task 8 — split the results across topical sub-pages)

The summary page had grown long (overview + coverage + metrics + scatters + map +
three galleries + downloads). Split it into a **fixed set of topical pages** —
still no per-matchup page, so the ~10⁴ design constraint holds.

`PAGE_STEMS` grew from 4 → **7**: `index`, `summary`, `comparisons`, `figures`,
`aggregates`, `methods`, `downloads`. In `pab/report/rst.py`:

- **summary** is now concise (overview + coverage + headline `b_bp`/Chl metrics).
- **comparisons** (new `comparisons_page`) — the interactive `b_bp` + Chl scatters
  and the matchup map (moved off summary; `interactive_figures` lost its inner
  heading so the page owns the title).
- **figures** (new `figures_page`) — the per-matchup fit, PACE scene, and Argo
  Q&A thumbnail galleries.
- **downloads** — `downloads_block` promoted to `downloads_page` (top-level title).
- `aggregates`/`methods` unchanged (tables+quality / narrative+provenance).
- `index_page` toctree now lists all six content pages (hidden; sidebar nav) and
  its "What's on this site" guide matches the new structure.

Tests: `test_build_site_fixed_pages_no_per_matchup` auto-tracks `PAGE_STEMS`;
updated the two build-site assertions to read the **comparisons** (scatters) and
**figures** (gallery + copied PNG) pages, and renamed `downloads_block` →
`downloads_page`. **136 passed** (only the pre-existing `earthaccess` test fails).
Rebuilt `report_site` → 7 pages, summary carries no scatter, comparisons has both,
figures has the galleries, downloads has the tables; `sphinx-build` clean, no
orphan/toctree warnings. Updated `docs/reporting.rst` to describe the page set.
