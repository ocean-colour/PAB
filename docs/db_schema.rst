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
* ``pab_version`` records when a **row** was created, **not** which database
  file it currently lives in. The two diverge as soon as a version database is
  built by copying another (:mod:`pab.db.split_version`): the v2 store carries
  ``matchups`` stamped ``1.0`` and the NASA-GIOP ``fits``/``fit_results``
  stamped ``1.1``, because those records were made during the v1 run and were
  carried over unchanged; only rows *created* by the v2 run stamp ``2.0``. So
  do not infer a database's version from the stamps inside it — a single file
  legitimately holds several. Likewise a ``pab_version`` bump does not imply a
  re-analysis: the 2026-09-05/06 chl-a/CDOM provenance backfill deliberately
  stayed at ``1.0`` (see ``HOWTO.md`` §7b).

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
    ``rank`` (1 = nearest), ``flagged``, and — **v5** — the per-pixel viewing
    geometry: ``theta_s``, ``theta_v``, ``dphi`` (all **degrees**) and
    ``geom_source``.

    The geometry is read from the co-temporal **PACE L1B** granule
    (``geolocation_data``), which shares the L2's ``(scans, pixels)`` grid, and
    is filled by the ``geometry`` pipeline stage; ``geom_source`` records where
    it came from (e.g. ``'L1B_V3'``). It is stored per **pixel**, not per fit,
    because it is a property of the observation rather than of the model fitted
    to it — so it is read once and reused by every fit of that pixel.

    * ``theta_s`` — solar zenith angle, degrees, ``0 ≤ theta_s < 90`` for a
      daylight observation (L1B ``solar_zenith``).
    * ``theta_v`` — sensor (viewing) zenith angle, degrees, ``0`` at nadir
      (L1B ``sensor_zenith``).
    * ``dphi`` — **relative** azimuth, degrees, defined as
      ``sensor_azimuth − solar_azimuth`` **wrapped to (−180, 180]**. For the
      reference pixel ``(868, 142)`` of
      ``PACE_OCI.20250309T131631``: ``sensor_azimuth = 61.58°``,
      ``solar_azimuth = −19.75°``, hence ``dphi = 81.33°``.

    NULL on rows created before v5.

``fits``
    One row per fitted spectrum, with configuration + provenance. **PK**
    ``fit_id``; **FK**\ s to ``matchups`` and ``matchup_pixels``. Columns:
    ``algorithm`` (``BING`` for MCMC fits; ``NASA_GIOP`` for the NASA L2 IOP
    baseline ingest — a *parallel* row per matchup at the same pixel, with the
    BING/MCMC-specific columns NULL and its own ``pab_version``),
    ``model_pair``, ``anw_model``, ``bbnw_model``,
    ``rrs_source`` (``L2_AOP`` vs ``PAB_L1B:<algo/version>``), ``prior_set``,
    ``nsteps``, ``nburn``, ``nwalkers``, ``wave_min``/``wave_max``, ``chisq``,
    ``aic``, ``bic``, ``accept_frac``, ``success``, ``chains_path``,
    ``figure_path``, ``pkg_versions`` (JSON), ``pab_version``, ``created``.

    **v5** adds the radiative-transfer configuration, which is what
    distinguishes a 2.0 fit from a 1.0 one (the ``model_pair`` is unchanged
    between them): ``rt_backend`` (``'gordon'`` for the elastic 1.0 fits,
    ``'robust_hybrid'`` for the inelastic 2.0 ones), the inelastic switches
    ``include_raman`` / ``include_chl_fl`` / ``include_cdom_fl`` (0/1),
    ``phi_c`` (chlorophyll-fluorescence quantum yield), and ``fit_bp`` (0/1 —
    whether :math:`B_p` was a free parameter). NULL on rows created before v5.

``fit_results``
    The scalar IOP results in **long format**. **PK** ``(fit_id, quantity)``;
    **FK** ``fit_id`` → ``fits``. Columns: ``quantity`` (the namespaced name,
    e.g. ``BING_ExpBPow_bbp``), ``value`` (posterior median), ``value_lo`` /
    ``value_hi`` (5th/95th percentiles), ``unit``.

    Long format keeps the table stable as model pairs are added: a second pair
    (``BING_GIOP_bbp``) or the NASA baseline writes new rows, not new columns.
    The NASA baseline is now real: ``NASA_GIOP_*`` rows (``NASA_GIOP_bbp_442``,
    ``NASA_GIOP_adg_442``, ``NASA_GIOP_aph_442``, their ``*_unc_442``
    uncertainties and the ``bbp_s``/``adg_s`` spectral slopes) attach to the
    parallel ``NASA_GIOP`` fit row.
    :meth:`pab.db.store.Store.fit_results_wide` pivots
    this into the wide, namespaced columns used for export and reporting.

Migrations
----------

The schema version lives in ``PRAGMA user_version``.
:func:`pab.db.schema.migrate` initialises a fresh (version-0) database via
:func:`pab.db.schema.create_all` and steps an existing one forward through the
:data:`pab.db.schema.MIGRATIONS` registry. Stage 1 ships only the initial
schema (version 1); later DDL changes register a forward step and bump
``SCHEMA_VERSION``.

A migration step only ever runs on a database still at its *starting*
version, so each version must be defined **completely** in one step: adding a
column to ``_v4_to_v5`` after some file has already been stamped
``user_version = 5`` will never apply it to that file, silently. This is why
v5 carries both the ``matchup_pixels`` geometry and the ``fits`` RT columns in
a single migration.

Splitting a release into a new version database is a separate concern from
schema migration and lives in :mod:`pab.db.split_version`: it copies a store
and drops one algorithm's ``fits``/``fit_results``, leaving the schema version
untouched (``VACUUM`` preserves ``PRAGMA user_version``). See ``HOWTO.md``
§5b for the ``v1``/``v2`` layout and the frozen-v1 rule.

Access API
----------

.. autoclass:: pab.db.store.Store
   :members:
   :member-order: bysource

.. automodule:: pab.db.schema
   :members: SCHEMA_VERSION, create_all, migrate, get_version

.. automodule:: pab.db.split_version
   :members: split_version, verify, copy_database, drop_algorithm, table_counts, sha256
