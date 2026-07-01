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
of pages — a landing/summary page (coverage counts + the headline sat-vs-float
``b_bp`` and Chl metrics), a binned-results page, and a methods page — plus a
**Sphinx ``conf.py``**, so the output directory is a **self-contained, buildable
reporting site, separate from the developer docs** (build with ``sphinx-build
<outdir> <outdir>/_build``). Per-matchup detail is reached on demand through the
interactive figures, not pre-rendered. The binned-results tables are **sortable**
Bokeh ``DataTable`` embeds when ``bokeh`` is available, falling back to static
reStructuredText ``list-table`` (:func:`pab.report.rst.rst_table`) otherwise.

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

Beyond the interactive plots, :mod:`pab.report.rst` surfaces the quality-assurance
imagery and provenance the pipeline now records:

* **Per-matchup fit figures**, **PACE scene quick-looks**
  (:func:`~pab.report.rst.scene_gallery`, from ``matchups.scene_path``), and
  **Argo profile Q&A** plots (:func:`~pab.report.rst.argo_qa_gallery`, from
  ``mld_summary.qa_path``) — each an **N-guarded** thumbnail gallery
  (:data:`~pab.report.rst.MAX_INLINE_FIGURES`) served from ``_static/`` via the
  shared :func:`~pab.report.rst._stage_static` copier.
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
(chains NPZ, figure) with ``matchup_id`` → URL + SHA-256 checksum, stamped with
``pab_version``.

The bulky artifacts live in the **NSF/Nautilus S3** object store and snapshots go
to **Zenodo**, but those uploads are **deferred and config-gated**. This stage
ships the *interfaces* with a filesystem stub
(:class:`~pab.report.publish.LocalStubBackend`), so
:func:`~pab.report.publish.publish_release` runs the whole build locally (exports
+ manifest + stub "uploads", no network). :class:`~pab.report.publish.NautilusS3Backend`
and :class:`~pab.report.publish.ZenodoBackend` are explicit ``NotImplementedError``
stubs until activated.

How to publish a release
------------------------

The build is keyed to ``pab_version`` (so a site reflects a known analysis
version). The current cadence is a **manual** run::

    from pab.db import Store
    from pab.report import rst, publish

    store = Store.open("pab.db")
    rst.build_site(store, "report_site")          # the aggregate .rst pages
    publish.publish_release(store, "release")      # exports + manifest (local stub)

Once the object-store/Zenodo credentials are wired (a later, config-gated
switch), pass an activated backend to :func:`~pab.report.publish.publish_release`
to push artifacts and record their real URLs in the manifest. Building the
community Sphinx site from the generated ``.rst`` and pushing to readthedocs /
Zenodo is the remaining deferred step.

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
