BING fitting wrapper
====================

Stage 5 fits the matchup ``Rrs`` spectra (Stage 4) with
`BING <https://github.com/ocean-colour/bing>`_ and stores the retrieved IOPs —
above all **non-water backscatter ``b_bp``** — with full posterior
uncertainties. ``b_bp`` is BING's most robustly retrieved quantity (``docs/
context.md`` §2), which is exactly why it is the observable PAB compares against
the BGC-Argo ``BBP700``. Implemented in :mod:`pab.fit`.

Pipeline
--------

#. **Configure** (:mod:`pab.fit.models`) — :class:`~pab.fit.models.FitConfig`
   selects the model pair and MCMC settings;
   :func:`~pab.fit.models.build_models` turns it into the BING parameter ntuple,
   the radiative-transfer dict, the two model objects on the data wavelength
   grid, and their standard priors.
#. **Prepare** (:func:`pab.fit.run.prepare_spectrum`) — restrict the spectrum to
   the ``[wave_min, wave_max]`` window, drop non-finite samples, and build the
   noise variance ``varRrs`` (``Rrs_unc**2``; a 2% floor when uncertainty is
   absent).
#. **Fit** (:func:`pab.fit.run.fit_spectrum`) — a **Levenberg–Marquardt
   warm-start** (``chisq_fit``) followed by **emcee MCMC** (``inference``);
   the Bricaud ``a_ph`` shape is **seeded** with the float's mixed-layer ``chla``
   (the fit then *retrieves* Chl from the ``Aph`` parameter — see below).
#. **Extract** (:func:`pab.fit.run.extract_quantities`) — posterior median + a
   credible interval (5th/95th by default) for each free parameter and the
   derived IOP scalars (``bbp``/``anw``/``adg`` at 440 & 700 nm) and the
   BING-retrieved chlorophyll ``chl`` (``= 10**Aph / 0.05582`` for the Bricaud
   family — the input ``Chl`` only *seeds* the a*_ph shape).
#. **Persist** (:mod:`pab.fit.artifacts`) — write the chains to an NPZ keyed by
   ``fit_id`` and upsert the ``fits`` + ``fit_results`` rows.

Model pair & the namespaced-quantity schema
--------------------------------------------

The default pair is the workhorse **``ExpBricaud`` + ``Pow``** (``model_pair =
"ExpBPow"``): exponential CDOM/detritus + Bricaud phytoplankton absorption, and
a power-law non-water backscatter ``b_b,nw = B_nw·(λ/600)^{-β}``.

Retrieved scalars are stored **namespaced** as ``BING_<model_pair>_<quantity>``
in the long ``fit_results`` table — e.g. ``BING_ExpBPow_bbp700``,
``BING_ExpBPow_beta``, ``BING_ExpBPow_Bnw``, ``BING_ExpBPow_adg440``,
``BING_ExpBPow_chl``. A second
model pair (e.g. a GIOP-style ``k=5`` variant) adds **rows under a new prefix**
rather than columns, so the schema is stable; ``Store.fit_results_wide()`` pivots
to the wide, namespaced view at the export/report boundary. Free parameters are
stored **linearised** (out of the log10 space some priors use).

MCMC settings (and why)
-----------------------

PAB defaults to ``nsteps=10000``, ``nburn=1000``, ``nwalkers=max(16, 2·ndim)`` —
lighter than BING's research default but adequate for these retrievals. Posterior
statistics drop ``analysis_burn`` (7000) production steps; the reconstruction
falls back to ``nsteps // 2`` when a chain is shorter, so quick test/CI runs at
toy size still yield samples. ``variable_Gordon`` and ``include_Raman`` are off
by default (the constant-coefficient elastic Gordon model).

Provenance & artifacts
----------------------

Every ``fits`` row carries ``pab_version``, ``created``, and ``pkg_versions``
(a JSON snapshot from :func:`pab.config.package_versions`), plus the fit
diagnostics (reduced ``chisq``, ``aic``, ``bic``, ``accept_frac``, ``success``)
and the configuration (``anw_model``/``bbnw_model``/``prior_set``/``nsteps``/…).
The bulky MCMC chains are **not** in the DB — they are written to
``PAB_DATA_DIR/fit_chains/<fit_id>.npz`` and referenced by ``fits.chains_path``.

How a fit links back to its matchup
-----------------------------------

A fit's deterministic id is ``"{matchup_id}_{ix}_{iy}_{model_pair}"``
(:func:`pab.fit.run.make_fit_id`), and the ``fits`` row carries ``matchup_id`` +
``pixel_id`` FKs. :func:`pab.fit.run.fit_matchup` re-reads the pixel ``Rrs`` from
the granule (spectra are not stored in ``matchup_pixels``), fits it, and
persists; :func:`pab.fit.run.build_fits` runs the nearest pixel of every matchup,
idempotent/resumable by ``fit_id``.

Source-agnostic & offline-testable
-----------------------------------

``bing``/``emcee`` are imported lazily, so ``import pab.fit`` works in the lean
CI environment. The array-level helpers (``make_fit_id``, ``prepare_spectrum``,
``extract_quantities``) are pure and unit-tested with known values; the full
LM→MCMC path is exercised on a synthetic, noise-free spectrum at toy MCMC size
(``pytest.importorskip("bing")``) and checked for ``b_bp`` recovery.

API reference
-------------

.. automodule:: pab.fit.models
   :members:

.. automodule:: pab.fit.run
   :members:

.. automodule:: pab.fit.artifacts
   :members:
