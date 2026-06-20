BGC-Argo ingestion & mixed-layer summary
=========================================

PAB turns each qualifying BGC-Argo profile into a single **mixed-layer summary**
record — the in-situ truth for the PACE matchup. The pipeline follows the
Bisson et al. (2019) recipe (``docs/context.md`` §3) and is implemented in the
:mod:`pab.argo` subpackage.

Pipeline
--------

#. **Fetch** (:mod:`pab.argo.fetch`) — ``argopy.DataFetcher`` configured for
   biogeochemical data (``ds='bgc'``, ``src='erddap'``), selected by region,
   float, or profile, and narrowed with the BGC-only ``params`` / ``measured``
   keywords. argopy is imported lazily; network access happens only at
   ``.load()``.
#. **QC & data-mode filtering** — :func:`pab.argo.fetch.filter_quality` applies
   ``ds.argo.filter_qc(QC_list=[1, 2])`` and, in research mode,
   ``filter_researchmode`` (delayed-mode, QC=1 — best when MLD quality matters).
#. **Reshape** — :func:`pab.argo.fetch.iter_profiles` calls
   ``ds.argo.point2profile()`` and yields per-profile metadata + variable arrays.
#. **Summarize** (:mod:`pab.argo.summary`) — compute the MLD, de-spike
   ``BBP700``, optionally drop log-IQR outliers, and average within the mixed
   layer.
#. **Persist** — :func:`pab.argo.summary.persist_summary` upserts the
   ``floats`` / ``profiles`` / ``mld_summary`` rows (idempotent, keyed by
   ``wmo`` / ``(wmo, cycle)`` / ``profile_id``).
#. **Q&A** (:mod:`pab.argo.qa`) — diagnostic ``BBP700`` / ``CHLA`` vs pressure
   plots with the MLD marked.

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
(:func:`pab.argo.summary.mixed_layer_mean`). ``CHLA`` is averaged over the same
layer; ``PSAL`` and ``TEMP`` are recorded as mixed-layer means.

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
