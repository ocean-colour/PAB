Metrics & figures
=================

Stage 6 turns the per-matchup BING fits (Stage 5) into the comparison PAB exists
to make — **satellite ``b_bp`` vs. BGC-Argo ``b_bp``** (and, with a satellite Chl
source, chlorophyll) — and the figures that make each matchup and the population
inspectable. Implemented in :mod:`pab.metrics` and :mod:`pab.plotting`.

The three backscatter estimates
-------------------------------

Each matchup carries up to three ``b_bp`` estimates, compared in **log space**
(following Bisson et al. 2019 and the BING ``papers/biomass`` analysis):

* **BING** — ``BING_ExpBPow_bbp700`` from ``fit_results`` (this analysis).
* **in-situ Argo** — ``mld_summary.bbp700`` (mixed-layer, de-spiked; Stage 2).
* **NASA L2 IOP** — the secondary baseline ``bbp_442``/``bbp_s`` under the
  ``NASA_L2IOP_*`` namespace (when ingested).

**Wavelength offset.** The Argo observable is ``b_bp(700)`` and BING reports
``b_bp`` at 700 nm directly (from the retrieved power-law slope), so the two are
compared at a common 700 nm. The NASA baseline is reported near 442 nm; comparing
it to 700 nm uses the retrieved/standard slope and is flagged as an
approximation.

Chlorophyll is compared the same way. **BING retrieves Chl** from the fitted
``Aph`` parameter (``Chl = 10**Aph / 0.05582`` for the Bricaud family — the input
``Chl`` only *seeds* the a*_ph shape, it is not a fixed input), stored as
``BING_ExpBPow_chl``; :func:`~pab.metrics.compare.gather_matchups` pulls it as
``chl_bing`` for comparison against the Argo ``chla``. An OC4 band-ratio Chl
(:func:`~pab.metrics.compare.add_oc_chl`) is available as an optional, independent
cross-check.

Metrics
-------

:func:`pab.metrics.compare.log_comparison` is **quantity-agnostic** — given paired
satellite & in-situ arrays (finite, positive) it returns:

* **median ratio** ``bbp_sat / bbp_float`` + IQR (Bisson found 0.77–1.66 across
  sensors/algorithms);
* **Spearman ρ** (rank-based, robust to the log-normal spread);
* **log-space bias** = mean of ``log10(sat/insitu)`` and **scatter** = RMS and
  MAD of that residual.

The per-fit reduced ``chisq`` (from ``fits``) rides along as a quality field. The
same function serves **BING-vs-NASA-L2-IOP** (two satellite columns) and the
**Chl** comparison.

Gathering & stratification
--------------------------

:func:`pab.metrics.compare.gather_matchups` joins
``matchups``/``profiles``/``mld_summary``/``fits``/``fit_results`` into one row
per matched fit (satellite + in-situ ``b_bp``, ``chla``, ``chisq``, position,
time). :func:`~pab.metrics.compare.add_strata` adds **season** (from the month)
and **region** (latitude band); the third Bisson axis — ``Rrs`` spatial
variability — needs the box ``Rrs`` spread, which is left for a later pass.
:func:`~pab.metrics.compare.add_oc_chl` attaches an **OC4** band-ratio Chl
(``ocpy.chl.band_ratios.oc4`` on the matchup pixel ``Rrs``) — a different
satellite Chl algorithm, an optional cross-check on the BING-retrieved
``chl_bing``.

Persistence — metrics are computed **on demand** from the stored fits/summaries
rather than written to a separate table: they are cheap to recompute, keep the
schema stable (no migration), and aggregate presentation belongs to the
reporting layer (Stage 7).

Figures (~100 KB budget)
------------------------

* **Per-matchup fit figure** (:func:`pab.plotting.fit_fig.fit_figure`) —
  reconstructs the fit from its chains NPZ and shows observed vs. model ``Rrs``
  (with the 5–95% band) and the retrieved ``b_bp(λ)`` band. PAB's own code,
  informed by ``bing.plotting`` / the ``plot-bing-fit`` skill *concept*, sized
  down (two panels, low DPI) from the ~1 MB biomass figures.
* **Per-matchup scene quick-look** (:func:`pab.plotting.scene.scene_quicklook`) —
  by default a **false-color RGB composite** (``Rrs`` at three wavelengths, R/G/B
  ≈ 645/555/470 nm, scaled by a shared brightness reference + gamma so the
  natural ocean colour is preserved; :func:`~pab.plotting.scene.false_color_rgba`),
  with a single-band view available (``mode="band"``). Either marks the Argo
  location, highlights the analyzed pixels, and greys the ``l2_flags`` mask.
* **Population figures** (:mod:`pab.plotting.population`) — the satellite-vs-float
  ``b_bp`` log-log scatter (1:1 + median-ratio lines) and a matchup map.

Offline-testable
----------------

The metric math is pure (known-value tested); the granule reads (scene, OC Chl)
go through the ``open_granule`` ``opener=`` seam (mocked in tests); figures
render under Matplotlib's Agg backend to files within the size budget; and the
``bing`` reconstruction for the fit figure is exercised only where ``bing`` + its
model data are present (skipped otherwise).

API reference
-------------

.. automodule:: pab.metrics.compare
   :members:

.. automodule:: pab.plotting.fit_fig
   :members:

.. automodule:: pab.plotting.scene
   :members:

.. automodule:: pab.plotting.population
   :members:
