Matchup engine & criteria
==========================

The matchup engine joins the two data halves built in Stages 2–3 — BGC-Argo
mixed-layer summaries (:mod:`pab.argo`) and PACE granules (:mod:`pab.pace`) —
into **matchup records**. For each qualifying profile it selects the single best
PACE granule and the ~10 nearest **unflagged** ``Rrs`` spectra around the float,
and writes the record linking **float ↔ granule ↔ pixels** through
:class:`pab.db.store.Store`. Implemented in :mod:`pab.matchup.engine`.

The criteria follow the Bisson et al. matchup recipe (``docs/context.md`` §3):
a small unflagged pixel box near the float and a tight time window.

Criteria
--------

A granule **qualifies** for a profile when both hold:

* **Temporal** — ``|profile_time − granule_time| ≤`` ``dtime_max_hours``
  (default **24 h**; the design's loose bound, tightened toward **~3 h** per
  Bisson et al. as data density allows). The offset is recorded as
  ``dtime_hours``.
* **Spatial** — the nearest unflagged pixel lies within ``max_distance_km``
  (default **5 km**) of the float, i.e. the footprint actually covers the float.
  The float-to-nearest-pixel great-circle distance is recorded as
  ``distance_km``.

Within a qualifying granule, the **~10 nearest unflagged pixels** are selected
with :func:`pab.pace.extract.extract_matchup_spectra` (10 ≈ the central part of
the 5×5 box Bisson et al. use). A pixel is *unflagged* when it passes the
standard ocean screen :data:`pab.pace.flags.STANDARD_OCEAN_MASK`; only unflagged
pixels are ever selected, so every stored pixel has ``flagged = 0``.

These knobs live on :class:`pab.matchup.engine.MatchupConfig`
(``dtime_max_hours``, ``n_spectra``, ``max_distance_km``, ``mask_flags``).

Selection / tie-break rule
--------------------------

When more than one granule qualifies, the engine picks the best by, in order:

#. smallest ``distance_km`` (closest in space — the primary criterion);
#. then smallest ``dtime_hours`` (closest in time);
#. then most spectra (``n_spectra``);
#. then lowest ``granule_id`` (a deterministic final tie-break).

The spatial criterion leads because Bisson et al. find skill degrades where
``Rrs`` spatial variability is high — proximity to the float matters most.

``matchup_id`` scheme
---------------------

Each record carries a deterministic id ``"{wmo}_{cycle}_{granule_id}"``
(:func:`pab.matchup.engine.make_matchup_id`). Because the id is a pure function
of the profile and the selected granule, re-running the engine on the same
inputs produces the same id, so writes **upsert** rather than duplicate. The
run is therefore idempotent and resumable: an already-written matchup is skipped
unless ``replace=True``.

How records link float ↔ granule ↔ pixels
-----------------------------------------

The engine writes through the Stage 1 schema (no DDL change):

* ``matchups`` — one row per matchup: ``matchup_id`` (PK), ``profile_id`` and
  ``granule_id`` (FKs into ``profiles`` / ``granules``), ``distance_km``,
  ``dtime_hours``, ``n_spectra``, and provenance (``pab_version``, ``created``).
* ``matchup_pixels`` — the selected pixels for that matchup: ``matchup_id`` (FK),
  ``ix``/``iy`` (granule pixel indices), ``latitude``/``longitude``,
  ``distance_km``, ``rank`` (1 = nearest), and ``flagged``. The pixels are
  *replaced* (delete-then-insert) on each write, so a re-run leaves no stale or
  duplicate rows.

The ``Rrs(λ)`` spectra themselves are not stored here — they are re-read from the
granule at fit time (Stage 5); ``matchup_pixels`` records *which* pixels were
chosen.

Source-agnostic & offline-testable
-----------------------------------

Granule datasets are obtained through the :func:`pab.pace.cloud.open_granule`
seam, so the engine never cares whether the data came from lazy S3, a local
file, or (in tests) a synthetic granule injected via ``opener=``. The geometry
and time logic are pure functions on values/arrays
(:func:`~pab.matchup.engine.time_offset_hours`,
:func:`~pab.matchup.engine.find_matchup`), checked offline against known
geometries — no network or S3 in the test suite.

Driver
------

:func:`pab.matchup.engine.build_matchups` ties it together: it walks the
qualifying profiles (:func:`~pab.matchup.engine.qualifying_profiles` — those with
a mixed-layer summary), gathers temporally-near granules
(:func:`~pab.matchup.engine.candidate_granules`), selects the best with
:func:`~pab.matchup.engine.find_matchup`, and persists it with
:func:`~pab.matchup.engine.write_matchup`. It returns the matchup ids written,
the ids skipped (already present), and the profiles left unmatched.

API reference
-------------

.. automodule:: pab.matchup.engine
   :members:
