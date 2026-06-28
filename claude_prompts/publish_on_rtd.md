# Publishing PAB on readthedocs

## Goals

Get the report(s) on readthedocs

## Claude

### Skills

Reporting-style glue over the existing modules; a couple of fitting skills inform
the batch stage:

- **`batch-fit-argo`** — the batch/parallel-fit + checkpointing pattern (mirrors
  `pab.fit.build_fits` over the population; BING `fit_batch` across cores).
- **`run-bing-fit`** — the per-spectrum fit the batch stage invokes.

## Context

Read these before coding:

- **Design** — `docs/design/PAB_design.md` → *Semi-automation* (the stage runner:
  idempotent stages skipping completed work, store-in/store-out, single-matchup
  debug vs full batch, BING `fit_batch` for the heavy fits) and *Provenance &
  versioning* (every result stamped with `pab_version`; re-running under a new
  version produces a new record, not a silent overwrite).
- **Coding plan** — `docs/design/PAB_coding_plan.md` §4 *Stage 8* (scope,
  deliverables, tests, docs) and §3 *Cross-cutting concerns*.
- **Implementation record** — `docs/design/PAB_implementation.md` (current state;
  the per-stage seams the runner chains; update it at the close of this stage).
- **Existing PAB seams the runner chains (all already implemented):**
  - `pab.argo.{fetch,summary}` — fetch BGC profiles + persist mixed-layer
    summaries (`persist_summary`, idempotent). `data/dev_profiles.csv` is the dev
    selection.
  - `pab.pace.{discover,cloud}` — `search_granules`/`granule_table`/
    `persist_granules` (the candidate set) and `open_granule` (the `opener=` test
    seam).
  - `pab.matchup.build_matchups(store, opener=, …)` — space+time match → records
    (idempotent/resumable, returns `{written, skipped, unmatched}`).
  - `pab.fit.build_fits(store, opener=, …)` — LM→MCMC per matchup, chains NPZ +
    `fits`/`fit_results` (idempotent by `fit_id`, returns `{written, skipped,
    failed}`).
  - `pab.plotting.{fit_fig,scene}` — per-matchup figures (write to `fits.figure_path`).
  - `pab.report.{build_site,publish_release}` — the aggregate site + downloads.
  - `pab.db.store.Store` — the shared state every stage reads/writes; `pab.config`
    (`pab_version`, `DATA_DIR`, `package_versions`).

## Prompts

1. Execute the first task in Tasks below
2. Execute the 2nd task in Tasks below
3. Execute the 3rd task in Tasks below

## Tasks

1. Read this doc.  Write the summary you just provided on how to publish on RTD below in the Reports/RTD section.  If you have any questions, ask them in Q&A.  Log your work

2. Read my answers to your questions below.  Then write a plan for exposing the Reports on RTD in the Plan section below.  Log your work.

3. I like your plan.  Please proceed to code up Phase 1.  If you have any questions, put them in the Q&A section.  Log your work.

## Plan

**Decisions locked in (from Q&A):** two RTD projects (dev docs stay on the
existing `.readthedocs.yaml`; the community report gets its own); and the
committed footprint must stay **small and bounded regardless of matchup count** —
"no huge files in GitHub" is a hard constraint.

### Guiding principle — keep git small by construction

The report has three size classes; only the first ever goes in git:

| Content | Size at 10⁴ matchups | Goes in git? |
| --- | --- | --- |
| Aggregate `.rst` (summary/aggregates/methods/index) + `conf.py` | KB | **Yes** |
| Embedded Bokeh scatter/map (ColumnDataSource = one row/matchup) | ~1–5 MB | Yes for now; Phase 2 externalises at large N |
| Per-matchup figure thumbnails + MCMC chains | ~1 GB+ | **No** — Nautilus S3, site links out |

This is the design's tiered model already (`PAB_design.md`: bulky artifacts to the
object store, the site links to them by ID). So the "huge files" problem is solved
by *never committing the per-matchup figures/chains at scale* — they live on S3 and
the gallery/tap-to-open reference S3 URLs from the download manifest.

### Phase 1 — MVP for the current dev sample (do now; no S3 needed)

The dev run is 4 matchups → 4 thumbnails (~0.4 MB total) + tiny `.rst`. Small
enough to commit as-is.

1. **Add a generation step** so the site is reproducible without the ad-hoc
   snippet: a `pab` subcommand/flag (e.g. `pab report --emit <dir>`) or a Make
   target that calls `rst.build_site(store, dir)`. Emit to an in-repo
   **`report_site/`**.
2. **Add `.readthedocs.report.yaml`** (second config, *not* the existing one):
   - `sphinx.configuration: report_site/conf.py`
   - `python.install: [{method: pip, path: .}, {requirements: requirements.txt}]`
     so the generated `conf.py`'s BokehJS-CDN list resolves and `sphinx_rtd_theme`
     is present.
   - `fail_on_warning: false` (match the dev-docs config).
3. **Generate + commit `report_site/`** (user runs git). Footprint ~0.5 MB.
4. **Import the second RTD project** (web UI): readthedocs.org → *Import a
   Project* → connect GitHub → authorize `ocean-colour` → pick `PAB` → name it
   `pab-report` → **Settings → Advanced → "Path to configuration file"** =
   `.readthedocs.report.yaml`. The existing project keeps building the dev docs.
5. **Verify** the published site renders the aggregate pages, the interactive
   scatter/map (CDN JS over HTTPS), and the 4 thumbnails from
   `report_site/_static/figures/`.

### Phase 2 — scale-ready (when the full run + Nautilus S3 land)

Triggered when matchup count or figure volume would bloat git. Code changes in
`pab.report`:

1. **Figures by URL, not by file.** Add a `figure_base_url` (or manifest-driven)
   mode to `build_site`/`figure_gallery`/`interactive_figures`: the gallery and
   the scatter's tap-to-open reference the **S3 URLs from `publish.build_manifest`**
   instead of copying PNGs into `_static/figures/`. Then `report_site/` is `.rst`
   + `conf.py` + embedded Bokeh only — bounded at any matchup count. (The existing
   `MAX_INLINE_FIGURES` N-guard already suppresses the inline gallery at scale;
   this makes tap-to-open work without local files.)
2. **Externalise the Bokeh data at very large N.** Per the design's tier-2 note,
   above ~10⁴–10⁵ points load the hover/scatter data from a committed/served
   compact CSV/JSON (or Datashader) rather than inlining it in the page, so the
   embedded JSON stays small.
3. **Avoid history bloat from regeneration.** Publish the generated `report_site/`
   on a **dedicated branch** (e.g. `report-site`, refreshed as a rolling/orphan
   commit) and point the `pab-report` RTD project's default branch at it — keeps
   regenerated content out of `main`/`develop` history. (Optional now; nice once
   regeneration is frequent.)
4. **Wire publishing** — activate `NautilusS3Backend` (and Zenodo for DOI
   snapshots) in `publish_release`; this is the **deferred, config-gated** step
   (`HOWTO.md` §7) and is a prerequisite for step 1's S3 URLs.

### Out of scope / explicitly deferred

- Nautilus S3 + Zenodo backend activation (credentials, config) — deferred per
  `HOWTO.md` §7; only the local stub runs today.
- GitHub Pages — not the plan; GitHub is the *source*, RTD is the *host*.

### Open items to confirm before Phase 1 scaffolding

- **Generation entry point:** a `pab` subcommand vs a Make target vs a small
  script — preference? (Recommend a `pab report --emit <dir>` flag, since the
  pipeline already owns `build_site`.)
- **Branch placement now:** commit `report_site/` on `develop` for the MVP
  (simplest), and defer the dedicated `report-site` branch to Phase 2? (Recommend
  yes.)

## Q&A

**Q (Task 1): One RTD project or two?** The design separates the community
reporting site from the developer docs, so my recommendation is a **second RTD
project** (the existing `.readthedocs.yaml` keeps building the dev docs). The
simpler alternative is folding the report into the existing dev-docs toctree (one
project) — but that mixes community + developer/methods docs, against the design.
Confirm which you want before I scaffold.

A. Two

**Q (Task 1): Where should the generated site be committed?** I suggested an
in-repo path `report_site/`. OK, or prefer another name/location?

A.  Depends.  We can't push huge files to GitHub.  Given that, what do you recommend?

## Reports

### RTD

**Plan: readthedocs is the host; GitHub is the source — not either/or.** The
design names readthedocs the primary, fully-static channel
(`docs/design/PAB_design.md` *"Static site on readthedocs.io (.rst → Sphinx). The
primary channel"*) and it is milestone **M4** in the coding plan (*"published
readthedocs report"*). The three publishing channels play different roles:

- **GitHub** (`ocean-colour/PAB`) is the **source** RTD builds from — RTD watches
  the repo and rebuilds on push.
- **readthedocs** is the **host** that renders and serves the HTML.
- **Zenodo** (citable DOI snapshots) and **Nautilus/NSF S3** (bulk chains +
  figures) are the other two channels, but they are **deferred and must not be
  wired yet** (`HOWTO.md` §7). The RTD site itself is *not* deferred — it is M4.

GitHub Pages was never the plan: the rendered site goes on RTD, sourced from the
GitHub repo.

**Current wiring — two gaps to bridge:**

1. **`.readthedocs.yaml` already exists, but it builds the *developer* docs**, not
   the report. Its own comment says so (*"The community-facing reporting site
   (Stage 7) will be a separate Sphinx target; this config builds the
   developer/methods docs under docs/"*); it points at `docs/conf.py`.
2. **The generated report lives *outside* the repo.** `pab.report.rst.build_site`
   writes to `DATA_DIR/pipeline/site` (`DATA_DIR` is kept out of git by design).
   RTD builds from the repo, so it cannot see that directory, and it cannot
   regenerate it either (no SQLite store or matchup data in the build env).

**How to publish (recommended: a second RTD project off the same repo):**

1. **Generate the site into a repo path** (tiny — 4 `.rst` + `conf.py` + ~100 KB
   thumbnails):

   ```python
   from pab.db import Store
   from pab.report import rst
   with Store.open("…/pab.db") as s:
       rst.build_site(s, "report_site")   # a committed, in-repo path
   ```

   For the full ~10⁴-matchup run the bulky figures/chains go to Nautilus S3 and
   the site links out, so the committed footprint stays bounded — the design's
   tiered model.
2. **Commit `report_site/`** (git is the user's to run).
3. **Add a second config** `.readthedocs.report.yaml` with
   `sphinx.configuration: report_site/conf.py` and a `python.install` of the
   package (so the BokehJS CDN list baked into the generated `conf.py` resolves).
4. **On readthedocs.org:** *Import a Project* → connect GitHub → authorize the
   `ocean-colour` org → pick `PAB` → in the new project's **Settings → Advanced →
   "Path to configuration file"** set `.readthedocs.report.yaml`. Name it e.g.
   `pab-report`. The existing project keeps serving the dev docs from
   `.readthedocs.yaml`.

The embedded Bokeh figures load JS from `cdn.bokeh.org` over HTTPS (fine on RTD's
HTTPS hosting), and the `_static/figures/` thumbnails are served as static files,
so the figures render on RTD too.

**Alternative (one project):** fold the report pages into the existing dev-docs
toctree — simpler, but mixes the community site with developer/methods docs, which
the design explicitly separates. The two-project approach is recommended.

**Proposed scaffolding (pending the Q&A answers):** add `.readthedocs.report.yaml`
and a small `pab`/Make target that emits the site into `report_site/`, leaving the
`git add`/commit and the RTD web-UI import to the user.

## Logging

Append an entry to the **Logs** section of this file using the format:

```
### <Date> (Short summary of the work)

<Detailed description of the work and what you learned>
```

## Logs

### 2026-06-28 (Recorded the RTD publishing plan)

Read this doc and wrote the readthedocs publishing summary into Reports/RTD.
Confirmed from the design docs that **readthedocs is the planned host** (primary
static channel; coding-plan milestone M4 "published readthedocs report"), with
**GitHub `ocean-colour/PAB` as the source** RTD builds from — not an either/or —
and Zenodo + Nautilus S3 as the deferred channels (`HOWTO.md` §7). Identified the
two gaps to bridge: the existing `.readthedocs.yaml` builds the *developer* docs
(`docs/conf.py`), not the report, and `build_site` writes the generated site to
`DATA_DIR/pipeline/site` — outside the git repo and invisible to RTD's repo-based
build. Recommended path: generate the (small) aggregate site into an in-repo
`report_site/`, commit it, add a second `.readthedocs.report.yaml`
(`sphinx.configuration: report_site/conf.py`), and import it as a *second* RTD
project so the dev docs and the community report stay separate (the design's
intent). Raised two questions in Q&A (one vs two RTD projects; the in-repo path
name) before scaffolding. No code changed this task.

### 2026-06-28 (Wrote the RTD exposure plan)

Read the user's Q&A answers — **two RTD projects**, and **"we can't push huge
files to GitHub"** — and wrote the Plan section. The huge-files answer reframed
everything: the committed footprint must be **bounded by construction**, which is
exactly the design's tiered model. Split the report into three size classes and
ruled that only the aggregate `.rst` + `conf.py` (KB) ever lives in git; per-matchup
thumbnails + MCMC chains (~1 GB at 10⁴) go to Nautilus S3 with the site linking out;
the embedded Bokeh data is bounded now but externalised at very large N.

Plan is phased: **Phase 1** = MVP for the 4-matchup dev sample (~0.5 MB, commit
`report_site/` as-is) — add a generation step (`pab report --emit <dir>`), a second
`.readthedocs.report.yaml` pointing at `report_site/conf.py`, and import a
`pab-report` RTD project via the web UI. **Phase 2** (when the full run + S3 land) =
add a `figure_base_url`/manifest mode so the gallery + scatter tap-to-open reference
S3 URLs instead of copied PNGs (keeps git bounded at any N), externalise the Bokeh
data at very large N, and optionally publish the generated site on a dedicated
`report-site` branch to avoid history bloat. Left two entry-point questions open
(generation hook; branch placement) before scaffolding. No code changed this task.
