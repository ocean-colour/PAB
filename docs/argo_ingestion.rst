BGC-Argo ingestion & mixed-layer summary
=========================================

PAB turns each qualifying BGC-Argo profile into a single **mixed-layer summary**
record — the in-situ truth for the PACE matchup. The pipeline follows the
Bisson et al. (2019) recipe (``docs/context.md`` §3) and is implemented in the
:mod:`pab.argo` subpackage.

.. admonition:: Worked-example notebooks
   :class: tip

   - :doc:`nb/02_argo_mld_summary` — MLD (de Boyer Montégut), ``BBP700``
     de-spiking, the whole-profile summary, DB persistence, and a Q&A plot,
     ending with an optional live ``argopy`` fetch.
   - :doc:`nb/00_getting_started` — package basics (``pab_version``, config,
     provenance) if you are new to PAB.

Pipeline
--------

#. **Fetch** (:mod:`pab.argo.fetch`) — ``argopy.DataFetcher`` configured for
   biogeochemical data (``ds='bgc'``, ``src='gdac'`` — reads the GDAC netCDF
   directly, more reliable than the Ifremer BGC ERDDAP), selected by region,
   float, or profile, and narrowed with the BGC-only ``params`` / ``measured``
   keywords. ``DEFAULT_PARAMS`` requests ``CHLA``, ``BBP700``, ``CDOM``,
   ``PSAL``, ``TEMP``, ``PRES``. argopy is imported lazily; network access
   happens only at ``.load()``.
#. **QC & data-mode filtering** — :func:`pab.argo.fetch.filter_quality` applies
   ``ds.argo.filter_qc(QC_list=[1, 2])`` and, in research mode,
   ``filter_researchmode`` (delayed-mode, QC=1 — best when MLD quality matters).
#. **Reshape** — :func:`pab.argo.fetch.iter_profiles` calls
   ``ds.argo.point2profile()`` and yields per-profile metadata (including the
   processing DAC and per-BGC-parameter data modes — see *Provenance* below) +
   variable arrays (``PRES``, ``BBP700``, ``CHLA``, ``CHLA_ADJUSTED``,
   ``CDOM``, ``PSAL``, ``TEMP``).
#. **Summarize** (:mod:`pab.argo.summary`) — compute the MLD, de-spike
   ``BBP700``, optionally drop log-IQR outliers, and average within the mixed
   layer.
#. **Persist** — :func:`pab.argo.summary.persist_summary` upserts the
   ``floats`` / ``profiles`` / ``mld_summary`` rows (idempotent, keyed by
   ``wmo`` / ``(wmo, cycle)`` / ``profile_id``).
#. **Q&A** (:mod:`pab.argo.qa`) — diagnostic ``BBP700`` / ``CHLA`` vs pressure
   plots with the MLD marked.

Provenance: processing DAC & per-parameter data mode
-----------------------------------------------------

Each float's ``PROJECT_NAME`` / ``DATA_CENTRE`` (the processing DAC — e.g.
distinguishing AOML- from Coriolis-processed floats) are extracted per profile
and stored on ``floats``. Argo's whole-profile ``DATA_MODE`` is *not* a
meaningful signal for BGC data — a bare ``DATA_MODE`` variable was not observed
on any real BGC/GDAC fetch (as of argopy 1.4.0); BGC files instead carry a data
mode **per BGC parameter**, since e.g. ``CHLA`` and ``PSAL`` on the same
profile can be in different modes. ``iter_profiles`` extracts
``CHLA_DATA_MODE`` / ``CDOM_DATA_MODE`` / ``BBP700_DATA_MODE`` accordingly,
stored as ``mld_summary.chla_data_mode`` / ``cdom_data_mode`` /
``bbp700_data_mode``. Notably, **``cdom_data_mode`` is always ``'R'`` or
``NULL`` across the whole BGC-Argo fleet** — no float has ever had CDOM
delayed-mode or real-time-adjusted processing — while ``CHLA``/``BBP700`` are
predominantly ``'A'``/``'D'``.

Mixed-layer depth (MLD) — method note
-------------------------------------

PAB uses the **de Boyer Montégut density-threshold** criterion (de Boyer
Montégut et al. 2004), as adopted by **Bisson et al. (2019)** for BGC-Argo
``bbp`` matchups: the MLD is the shallowest depth below a 10 m reference at
which the potential density anomaly ``SIG0`` exceeds its reference-depth value
by **0.03 kg m⁻³**.

Potential density is computed with TEOS-10 (``gsw``: practical → absolute
salinity, in-situ → conservative temperature, then ``sigma0``), matching
argopy's ``ds.argo.teos10(['SIG0'])``. The criterion is implemented in pure
NumPy in :func:`pab.argo.mld.mixed_layer_depth` (so it unit-tests against a
synthetic profile with a known answer), with
:func:`pab.argo.mld.mixed_layer_depth_from_ts` providing the T/S → ``SIG0`` →
MLD convenience path. The method tag stored with each summary is
:data:`pab.argo.mld.MLD_METHOD` (``"deBoyerMontegut_0.03"``).

De-spiking and averaging
------------------------

Within the mixed layer PAB de-spikes ``BBP700`` with a **3-point moving median**
(:func:`pab.argo.summary.moving_median` / :func:`~pab.argo.summary.despike`) to
remove single-sample bubble spikes, optionally removes **log-space 1.5×IQR
outliers** (:func:`pab.argo.summary.iqr_inlier_mask`), then averages
(:func:`pab.argo.summary.mixed_layer_mean`). ``CHLA``, ``CHLA_ADJUSTED``, and
``CDOM`` all get the same **plain** mixed-layer mean as each other (no
de-spike/IQR filter — Bisson's recipe was derived for ``BBP700``
specifically); ``PSAL`` and ``TEMP`` are likewise recorded as mixed-layer
means.

References
----------

* de Boyer Montégut, C., et al. (2004), *J. Geophys. Res.* 109, C12003 — MLD
  climatology and the 0.03 kg m⁻³ density-threshold criterion.
* Bisson, K. M., et al. (2019), *Opt. Express* 27, 30191 — the BGC-Argo ``bbp``
  matchup recipe PAB follows.

API reference
-------------

.. automodule:: pab.argo.mld
   :members:

.. automodule:: pab.argo.summary
   :members:

.. automodule:: pab.argo.fetch
   :members:

.. automodule:: pab.argo.qa
   :members:
