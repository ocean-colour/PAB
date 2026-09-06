Database schema reference
=========================

PAB stores all *tabular, extracted* values in a single **SQLite** database — the
system of record (see the design's *Storage and retrieval* section). Bulky
artifacts (MCMC chains, figures) live in files keyed by ID; the database holds
only their on-disk paths.

The schema is defined in :mod:`pab.db.schema` and accessed through the thin
:class:`pab.db.store.Store` API. The current schema version is
:data:`pab.db.schema.SCHEMA_VERSION`, stamped into the file's
``PRAGMA user_version``.

Conventions
-----------

* Depths / MLD in metres (m); ``bbp700`` and IOPs in m⁻¹; ``Rrs`` in sr⁻¹;
  ``CHLA`` in mg m⁻³; ``CDOM`` in ppb QSDE (Quinine Sulfate Dihydrate
  Equivalent — a fluorescence proxy, **not** an absorption coefficient; see the
  CDOM caveat in the design doc's *Comparison & metrics*); ``PSAL`` in PSU;
  ``TEMP`` in °C; wavelengths in nm.
* Distances in km; time offsets in hours; timestamps as ISO-8601 text.
* Every results-bearing row carries a ``pab_version`` stamp for provenance.

Tables
------

``floats``
    BGC-Argo float identifiers. **PK** ``wmo``. Columns: ``project_name``,
    ``data_center``.

``profiles``
    One row per float profile. **PK** ``profile_id`` (autoincrement);
    **unique** ``(wmo, cycle)``; **FK** ``wmo`` → ``floats``. Columns:
    ``latitude``, ``longitude``, ``time``, ``data_mode``.

    .. note::
       ``data_mode`` is Argo's coarse, whole-profile R/A/D flag. **It is left
       ``NULL`` on real BGC fetches** — a bare ``DATA_MODE`` variable was not
       observed on any real BGC/GDAC dataset (as of argopy 1.4.0); BGC files
       instead carry a data mode **per BGC parameter** (see
       ``mld_summary.chla_data_mode`` / ``cdom_data_mode`` /
       ``bbp700_data_mode`` below), since ``CHLA`` and ``PSAL`` on the same
       profile can be in different modes. Use those, not this column, for any
       BGC-variable-specific mode stratification.

``mld_summary``
    Per-profile mixed-layer summary (1:1 with ``profiles``). **PK/FK**
    ``profile_id`` → ``profiles``. Columns: ``mld``, ``mld_method``,
    ``bbp700`` (+``_std``), ``chla`` (+``_std``), ``chla_adjusted``, ``cdom``
    (+``_std``), ``psal``, ``temp``, ``n_points``, ``chla_data_mode``,
    ``cdom_data_mode``, ``bbp700_data_mode``, ``created``, ``pab_version``.

    ``chla_adjusted`` — mixed-layer mean of Argo's ``CHLA_ADJUSTED`` (present
    for the ~97% of BGC profiles that have had real-time-adjusted or
    delayed-mode Chl-a processing); ``NULL`` where Argo has not yet adjusted
    that profile's Chl-a. ``cdom`` is the **raw** ``CDOM`` mixed-layer mean
    (ppb QSDE) — no adjusted/corrected counterpart is stored: as of schema v4,
    **no BGC-Argo float has ever had CDOM delayed-mode processed**
    (``cdom_data_mode`` is always ``'R'`` or ``NULL``, never ``'A'``/``'D'``),
    and a known Sea-Bird Scientific sensor calibration bias (pre-2023-01-13
    fluorometers, a confirmed ×5.62 factor on one part of it) has deliberately
    **not** been applied pending further consultation — see
    ``claude_prompts/chl_cdom_matchups.md``. The three ``*_data_mode`` columns
    are Argo's per-**parameter** mode (R/A/D) for that BGC variable — added
    because ``profiles.data_mode`` above is unpopulated for BGC data.

``granules``
    PACE granule index. **PK** ``granule_id`` (CMR concept-id / producer
    granule id). Columns: ``short_name``, ``time_start``, ``time_end``,
    ``footprint`` (WKT), ``cloud_cover``, ``data_url``.

``matchups``
    The profile ↔ granule matchup index. **PK** ``matchup_id`` (deterministic,
    encodes profile + granule); **unique** ``(profile_id, granule_id)``;
    **FK**\ s to ``profiles`` and ``granules``. Columns: ``distance_km``,
    ``dtime_hours``, ``n_spectra``, ``created``, ``pab_version``. This is the
    key the pipeline upserts on for idempotent, resumable runs.

``matchup_pixels``
    The ~10 selected ``Rrs`` pixels per matchup. **PK** ``pixel_id``;
    **unique** ``(matchup_id, ix, iy)``; **FK** ``matchup_id`` → ``matchups``.
    Columns: ``ix``, ``iy``, ``latitude``, ``longitude``, ``distance_km``,
    ``rank`` (1 = nearest), ``flagged``.

``fits``
    One row per fitted spectrum, with configuration + provenance. **PK**
    ``fit_id``; **FK**\ s to ``matchups`` and ``matchup_pixels``. Columns:
    ``algorithm``, ``model_pair``, ``anw_model``, ``bbnw_model``,
    ``rrs_source`` (``L2_AOP`` vs ``PAB_L1B:<algo/version>``), ``prior_set``,
    ``nsteps``, ``nburn``, ``nwalkers``, ``wave_min``/``wave_max``, ``chisq``,
    ``aic``, ``bic``, ``accept_frac``, ``success``, ``chains_path``,
    ``figure_path``, ``pkg_versions`` (JSON), ``pab_version``, ``created``.

``fit_results``
    The scalar IOP results in **long format**. **PK** ``(fit_id, quantity)``;
    **FK** ``fit_id`` → ``fits``. Columns: ``quantity`` (the namespaced name,
    e.g. ``BING_ExpBPow_bbp``), ``value`` (posterior median), ``value_lo`` /
    ``value_hi`` (5th/95th percentiles), ``unit``.

    Long format keeps the table stable as model pairs are added: a second pair
    (``BING_GIOP_bbp``) or the NASA baseline (``NASA_L2IOP_bbp``) writes new
    rows, not new columns. :meth:`pab.db.store.Store.fit_results_wide` pivots
    this into the wide, namespaced columns used for export and reporting.

Migrations
----------

The schema version lives in ``PRAGMA user_version``.
:func:`pab.db.schema.migrate` initialises a fresh (version-0) database via
:func:`pab.db.schema.create_all` and steps an existing one forward through the
:data:`pab.db.schema.MIGRATIONS` registry. Stage 1 ships only the initial
schema (version 1); later DDL changes register a forward step and bump
``SCHEMA_VERSION``.

Access API
----------

.. autoclass:: pab.db.store.Store
   :members:
   :member-order: bysource

.. automodule:: pab.db.schema
   :members: SCHEMA_VERSION, create_all, migrate, get_version
