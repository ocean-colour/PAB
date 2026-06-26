Pipeline & CLI
==============

Stage 8 is the **end-to-end stage runner** that ties Stages 2–7 into one
resumable, config-driven pipeline — **ingest → discover → match → fit → figure →
report** — plus a ``pab`` command-line entry point. It adds **no new science**:
each stage is a thin wrapper over the module already built for it
(:mod:`pab.argo`, :mod:`pab.pace`, :mod:`pab.matchup`, :mod:`pab.fit`,
:mod:`pab.plotting`, :mod:`pab.report`), reading and writing the shared
:class:`pab.db.store.Store`. Implemented in :mod:`pab.pipeline`.

Stages
------

#. **ingest** — persist the selected BGC-Argo profiles + mixed-layer summaries
   (``pab.argo``; from ``data/dev_profiles.csv`` or an inline selection).
#. **discover** — search + persist the candidate PACE granules per profile
   (``pab.pace.discover``).
#. **match** — :func:`pab.matchup.engine.build_matchups`.
#. **fit** — :func:`pab.fit.run.build_fits` (LM → MCMC per matchup).
#. **figure** — per-matchup fit + scene PNGs (``pab.plotting``), recorded on
   ``fits.figure_path`` (best-effort per fit).
#. **report** — the aggregate site + the (stub-published) release
   (:func:`pab.report.rst.build_site`, :func:`pab.report.publish.publish_release`).

Idempotent & resumable
----------------------

Every stage **skips work already done**, using the store's natural keys (the
existing ``persist_*`` / ``build_*`` idempotency: a profile with an
``mld_summary``, a ``matchup_id``, a ``fit_id`` already present). So a re-run is a
fast no-op over completed work and **resumes** the rest; ``--replace`` re-does
finished work. Re-running under a **new ``pab_version``** adds records rather than
overwriting, enabling side-by-side comparison across algorithm/prior changes
(per the design's *Provenance & versioning*).

:func:`pab.pipeline.run` runs the requested stages in :data:`pab.pipeline.STAGES`
order and returns a per-stage summary (counts written/skipped/failed); a
``dry_run=True`` returns the planned stage order and touches nothing.

Injectable seams (offline-testable)
-----------------------------------

The network/heavy operations are passed in as seams, so the whole pipeline runs
offline on synthetic inputs while the orchestration stays pure:

* ``opener`` — the granule open (:func:`pab.pace.cloud.open_granule`; a synthetic
  granule in tests);
* ``fetcher`` — the argopy profile fetch (or inline ``summary`` dicts in the
  config);
* ``searcher`` — the earthaccess granule discovery (returns a granule table).

Single-matchup debugging vs. the full batch population both run through the same
``run`` call; the heavy fits use BING ``fit_batch`` across cores when enabled.

CLI
---

Installed as the ``pab`` console entry point (``setup.py`` → ``console_scripts``;
also ``python -m pab.pipeline``)::

    pab --help
    pab --dry-run                      # print the stage plan, touch nothing
    pab --stage match --stage fit      # run a subset, in order
    pab --replace                      # re-do completed work
    pab --db pab.db --outdir out/      # explicit store + output dir

``--profiles-csv`` overrides the profile selection; ``--no-figures`` skips the
figure stage. The build is keyed to ``pab_version`` so a run reflects a known
analysis version.

API reference
-------------

.. automodule:: pab.pipeline
   :members:
