Reporting
=========

Stage 7 turns the SQLite store of extracted values and the per-matchup fit
artifacts (Stages 4–6) into the community-facing products PAB exists to share:
a **static readthedocs site** of *aggregate* pages + sortable tables, **standalone
Bokeh** interactive figures (the route to per-matchup detail), **downloads** plus
a manifest, and a **citable snapshot**. Implemented in :mod:`pab.report`; the
build runs **end-to-end offline** with the external-service backends stubbed.

Aggregate pages, not per-matchup pages
--------------------------------------

A hard design constraint: at ~10⁴ matchups PAB does **not** render one page per
matchup (nor per float). :func:`pab.report.rst.build_site` emits a **fixed set**
of topical pages (:data:`~pab.report.rst.PAGE_STEMS`) — an **index** (what PAB is),
a **summary** (coverage counts + headline sat-vs-float ``b_bp`` and Chl metrics), a
**comparisons** page (the interactive scatters + matchup map), a **figures** page
(the per-matchup fit / PACE scene / Argo Q&A thumbnail galleries), an
**aggregates** page (binned tables + a matchup-quality table), a **methods** page
(context + provenance), and a **downloads** page — plus a **Sphinx ``conf.py``**,
so the output directory is a **self-contained, buildable reporting site, separate
from the developer docs** (build with ``sphinx-build <outdir> <outdir>/_build``).
The results are split across these pages so none is overloaded, but the set is
still fixed — never one page per matchup. Per-matchup detail is reached on demand
through the interactive figures, not pre-rendered. The binned-results tables are
**sortable** Bokeh ``DataTable`` embeds when ``bokeh`` is available, falling back
to static reStructuredText ``list-table`` (:func:`pab.report.rst.rst_table`)
otherwise.

Aggregation
-----------

:mod:`pab.report.aggregate` bins the per-matchup comparison table
(:func:`pab.metrics.compare.gather_matchups`) and applies the quantity-agnostic
:func:`pab.metrics.compare.log_comparison` per bin:

* **Flat bins** — :func:`~pab.report.aggregate.aggregate_by` over ``region`` /
  ``season`` (and ``b_bp``-magnitude via
  :func:`~pab.report.aggregate.magnitude_bins`).
* **HEALPix** — :func:`~pab.report.aggregate.aggregate_healpix` assigns matchups
  to equal-area HEALPix cells (``healpy`` via ``remote_sensing.healpix``;
  :func:`~pab.report.aggregate.nside_for_cell_size` picks ``nside``) and returns a
  per-cell table with cell-centre ``lon``/``lat`` for the map. Equal-area and
  resolution-tunable, it scales independently of matchup count; the flat bins
  remain the default.

Interactive figures (standalone Bokeh)
--------------------------------------

:mod:`pab.report.interactive` builds the satellite-vs-float ``b_bp`` scatter
(:func:`~pab.report.interactive.comparison_scatter`) and the matchup map
(:func:`~pab.report.interactive.matchup_map`), embedded as **standalone**
HTML/JSON (:func:`~pab.report.interactive.embed` / ``bokeh.embed.components``) so
they work on static hosting with no Bokeh server. **Hover** shows each matchup's
values; an optional **tap** opens the matchup's artifact by URL — this is how the
site exposes per-matchup detail. Large scatter/maps use
``output_backend="webgl"``.

``comparison_scatter`` is quantity-agnostic (``sat_col``/``insitu_col``), so the
same function renders a **chlorophyll** scatter (``chl_bing`` vs Argo ``chla``)
alongside ``b_bp``; its ``extra_series`` overlays the independent **OC4**
band-ratio Chl (``chl_oc``) when a granule opener is supplied to
:func:`~pab.report.rst.build_site`.

Static figures at scale
-----------------------

Above :data:`~pab.report.rst.MAX_INTERACTIVE_MATCHUPS` (2,000) the Comparisons
page uses pre-rendered PNGs from :mod:`pab.plotting.population` instead of Bokeh
embeds — this is what the published 2.0 site (≈16,000 matchups) shows:

* :func:`~pab.plotting.population.density_scatter` — the ``b_bp``, chlorophyll,
  GIOP-vs-BING and 1.0-vs-2.0 panels. Log–log axes span the central 99 % of the
  pooled values; cells of a 50 × 50 2-D histogram holding
  ≥ :data:`~pab.plotting.population.DENSITY_MIN_COUNT` (5) matchups are filled
  on a sequential single-hue colormap (Blues / Greens / Purples) with a log
  count colorbar, and every matchup in a sparser cell is drawn as an individual
  dot in the same hue. The 1:1 line, the dashed median-ratio line and the
  ``n ρ bias RMS`` title are kept; matchups outside the axes are counted in
  the title (``[N off-scale]``) and **kept in the statistics**. Failed
  retrievals (``b_bp`` above the gate, below) are **not** in the statistics
  or on the panel — the caption counts them instead.
* :func:`~pab.plotting.population.matchup_map` and
  :func:`~pab.plotting.population.healpix_map` — a cartopy Robinson dot map
  (grey land, coastlines) and a HEALPix map of per-cell median
  ``log10(satellite / float b_bp)`` for cells with
  ≥ :data:`~pab.plotting.population.HEALPIX_MIN_COUNT` (5) matchups. Both use
  the same diverging scale, symmetric about 0 and clipped at a fixed
  ±:data:`~pab.plotting.population.LOG_RATIO_VMAX` (0.5 dex); the captions state
  how many matchups (or cells) saturate. Without cartopy, or without its cached
  Natural Earth shapefiles and no network, the maps fall back to plain axes
  with a warning (``projection=None`` forces that path in the tests).
* The NASA GIOP panel compares at **one wavelength**: NASA's 442 nm ``b_bp`` is
  shifted to 700 nm with its own per-pixel slope
  (:func:`pab.metrics.compare.giop_bbp_to_700`), derived in
  :func:`~pab.metrics.compare.gather_nasa_giop` and never persisted.

Failed retrievals and patch versions
------------------------------------

Two rules decide which BING values a page uses (``claude_prompts/v2/
report_improvements.md``, Q&A/Outliers 1 = B then C):

* **The ``b_bp`` gate.** A BING ``b_bp`` (700 nm) above
  :data:`pab.metrics.compare.BBP_IMPLAUSIBLE` (1 m⁻¹) is an optimiser failure,
  not a measurement (the 2.0 runaways all sit at 5–9 × 10⁴ m⁻¹, pressed against
  the ``Bnw`` prior ceiling; see ``versions/v2/high_bbp_outliers.md``).
  :func:`~pab.metrics.compare.gate_bbp` sets **only that column** to NaN where
  :func:`~pab.metrics.compare.implausible_bbp` is true, and every ``b_bp``
  statistic and figure — the summary headline, the density panel, both maps,
  the aggregates, the NASA-GIOP and 1.0-vs-2.0 sections — is computed from the
  gated frame, each caption carrying the computed "N failed retrievals (x.xx %,
  ``b_bp`` > 1 m⁻¹) excluded" clause (printed even at N = 0, so a page says the
  gate exists). The Chl of the same fits is **not** gated (Q&A/Outliers 6 = A),
  the gallery deliberately shows one such fit, and the exported tables keep the
  raw values with a 0/1 ``bbp_bing_implausible`` column. The *Methods* page
  explains the gate and the per-fit negative-blue QA count ``n_neg_blue``
  (:doc:`fitting`).
* **The patch overlay.** A patch version (``2.0.1``: the 2.0 runaways
  re-fitted with physical prior ceilings) shares its base's database and
  matchup set. :func:`pab.metrics.compare.version_family` names the newest
  base version plus its patches, and :func:`~pab.metrics.compare.overlay_patch`
  keeps, per matchup **and pixel** (and model pair), only the newest row — so
  :func:`~pab.metrics.compare.gather_matchups`,
  :func:`~pab.metrics.compare.gather_nasa_giop` and
  :func:`~pab.metrics.compare.gather_version_pair` show the 2.0.1 value where
  one exists and the 2.0 value elsewhere, never both and never neither. A patch
  on a different pixel supersedes nothing; base rows are never deleted. Every
  frame keeps its per-row ``pab_version``, and the matchup table also carries
  ``fit_id_superseded`` / ``bbp_bing_superseded`` so a reader can see what a
  patched row replaced. The summary page prints the per-version counts
  (:func:`~pab.metrics.compare.fit_version_counts`), the Comparisons page's
  retrieval-failure note is computed from
  :func:`~pab.metrics.compare.patch_refit_summary`, and an explicit
  ``pab_version`` (``--figure-version 2.0``) means exactly that version, with
  no overlay.

Beyond the interactive plots, :mod:`pab.report.rst` surfaces the quality-assurance
imagery and provenance the pipeline now records:

* **Per-matchup fit figures**, **PACE scene quick-looks**
  (:func:`~pab.report.rst.scene_gallery`, from ``matchups.scene_path``), and
  **Argo profile Q&A** plots (:func:`~pab.report.rst.argo_qa_gallery`, from
  ``mld_summary.qa_path``) — each an **N-guarded** thumbnail gallery
  (:data:`~pab.report.rst.MAX_INLINE_FIGURES`) served from ``_static/`` via the
  shared :func:`~pab.report.rst._stage_static` copier. Above the guard the
  galleries show a deterministic **representative** subset instead of nothing:
  :func:`~pab.report.rst.select_representative_fits` (the matchups nearest the
  5th/25th/50th/75th/95th percentiles of the sat/float ``b_bp`` ratio, the
  re-fitted runaway with the largest superseded 2.0 ``b_bp`` — shown with its
  patch-version figure and a "2.0 → 2.0.1 (float)" caption — or, with no patch
  version, the largest non-physical retrieval, and the clearest and most
  productive Chl terciles — ≤ 8, each captioned with why it was chosen),
  :func:`~pab.report.rst.select_representative_scenes` (one per latitude band),
  and the Argo Q&A plots behind the selected fits. Only those files are staged,
  downscaled to :data:`~pab.report.rst.GALLERY_MAX_SIDE` px. Because the
  database records the paths where the figures were rendered (in-pod), the
  ``pab --emit-site`` CLI takes a repeatable ``--figure-root OLD=NEW`` remap
  (:func:`~pab.report.rst.remap_figure_path`); a file still missing after the
  remap is dropped with one counted warning per gallery. Because the picks are
  "nearest a percentile", any change in the frame moves them, so
  :func:`~pab.report.rst.build_site` empties the three gallery folders
  (:data:`~pab.report.rst.GALLERY_SUBDIRS`) before staging — a committed site
  never carries a thumbnail from an earlier build that nothing links to.
* A **matchup-quality table** (:func:`~pab.report.rst.matchup_quality_table`:
  distance / Δtime / spectra count) on the aggregates page.
* A **provenance block** (:func:`~pab.report.rst.provenance_block`: ``pab_version``
  + build date + :func:`pab.config.package_versions` table) on the methods page.

Downloads, manifest & publishing
--------------------------------

:mod:`pab.report.publish` exports the **summary tables** (CSV/Parquet via
:func:`~pab.report.publish.export_tables`; the raw SQLite file is *not* a
published download) and builds a **download manifest**
(:func:`~pab.report.publish.build_manifest`) — one row per per-matchup artifact
(chains NPZ, figure) with ``matchup_id`` → URL + SHA-256 checksum. Each row
carries the **fit's own** ``pab_version`` (every version in the database is
listed) and a ``superseded_by`` field naming the patch re-fit that replaces it
on the site, if any (:func:`~pab.report.publish.superseded_fits`). The exported
tables carry the same ``pab_version`` and, for the matchup table, the
``_superseded`` columns, so a reader can tell patched rows apart.

The bulky artifacts live in the **NSF/Nautilus S3** object store and snapshots
would go to **Zenodo**. The stage ships a filesystem stub
(:class:`~pab.report.publish.LocalStubBackend`) so
:func:`~pab.report.publish.publish_release` runs the whole build locally (exports
+ manifest + stub "uploads", no network), and a **live**
:class:`~pab.report.publish.NautilusS3Backend` (path-style Ceph RGW, public-read
``s3://pab``; credentials from the standard boto3 chain) that has published the
v1 and v2 databases and the v2 summary tables — the procedure and the recorded
sizes/sha256 are in ``HOWTO.md`` §5b/§7b.
:class:`~pab.report.publish.ZenodoBackend` remains an explicit
``NotImplementedError`` stub.

How to publish a release
------------------------

The build is keyed to ``pab_version`` (so a site reflects a known analysis
version). The current cadence is a **manual** run::

    from pab.db import Store
    from pab.report import rst, publish

    store = Store.open("pab.db")
    rst.build_site(store, "report_site")          # the aggregate .rst pages
    publish.publish_release(store, "release")      # exports + manifest (local stub)

The production site is built with the ``pab --emit-site`` CLI (``--compare-db``
for the frozen v1 database, ``--downloads-base-url`` to link the tables on S3
instead of staging them, ``--figure-root`` to translate the pod paths stored in
the database; ``HOWTO.md`` §7a has the exact command) and committed as
``report_site/`` for Read the Docs. The summary tables are uploaded with
:class:`~pab.report.publish.NautilusS3Backend`; the bulk artifacts (chains and
figures) are backed up but not yet published through
:func:`~pab.report.publish.publish_release`, so the manifest still carries local
URLs, and Zenodo is the remaining deferred step.

API reference
-------------

.. automodule:: pab.report.aggregate
   :members:

.. automodule:: pab.report.rst
   :members:

.. automodule:: pab.report.interactive
   :members:

.. automodule:: pab.report.publish
   :members:
