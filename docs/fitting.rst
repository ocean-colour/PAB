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
toy size still yield samples. ``variable_Gordon`` stays off (the
constant-coefficient Gordon coefficients).

Radiative-transfer configuration: 2.0 vs 1.0
--------------------------------------------

As of ``pab_version = "2.0"`` the :class:`~pab.fit.models.FitConfig` **defaults
are the inelastic configuration**, and the published 1.0 configuration is kept
as the named constructor :meth:`~pab.fit.models.FitConfig.v1` so comparisons
cannot drift from it by accident.

.. list-table::
   :header-rows: 1

   * - field
     - 2.0 (default)
     - ``FitConfig.v1()``
   * - ``rt_backend``
     - ``'robust_hybrid'``
     - ``'gordon'``
   * - ``include_Raman``
     - ``True``
     - ``False``
   * - ``include_Chl_fl``
     - ``True``
     - ``False``
   * - ``include_CDOM_fl``
     - ``False``
     - ``False``
   * - ``fit_Bp``
     - ``True``
     - ``False``
   * - ``phi_C`` / ``Bp_value``
     - 0.02 / 0.01
     - 0.02 / 0.01
   * - ``wave_max``
     - **720 nm**
     - 700 nm

``rt_backend`` selects the forward model that turns ``(a, bb)`` into ``Rrs``:
``'gordon'`` is BING's own elastic Gordon (1988) relation; ``'robust_hybrid'``
is retrieve-or-bust's analytic ZTT model plus a learned emulator correction,
valid over 350–750 nm — which is why ``wave_max = 720`` is safe. Every backend
except ``'gordon'`` **requires per-pixel geometry**: ``theta_s`` is never
silently defaulted, so a fit whose pixel has no ``theta_s``/``theta_v``/``dphi``
is refused before the granule is even opened, and recorded under ``"failed"``.
Run the ``geometry`` stage first (see ``HOWTO.md`` §4).

**Free** ``B_p``. Under ``fit_Bp`` the sampled vector gains a **trailing**
``B_p`` dimension — ``[a_params…, bb_params…, B_p]``, ``ndim = 6`` for
``ExpBPow`` — sampled **linearly** over ``[0.004, 0.05]``. It is reported as the
``Bp`` quantity. Anything splitting a posterior must peel that trailing column
*before* the ``a``/``bb`` split (:func:`pab.fit.run._split_flat`).

**Downwelling irradiance.** BING's Raman and fluorescence kernels need
``Ed(λ)`` and PACE L2 carries none, so
:func:`pab.fit.run.set_inelastic_Ed` supplies ``robust``'s packaged Loisel+23
spectrum interpolated at the pixel's solar zenith (350–750 nm, covering both the
fit window and the Raman excitation grid). This is not optional: without it
Raman silently falls back to a flat ``Ed(λ')/Ed(λ) = 1`` (~+60 % increment error
at 490 nm) and chlorophyll fluorescence raises ``IndexError`` on a 0-d
``Ed_ex``.

**Reconstruction must match the fit.** :func:`pab.fit.run.reconstruct_rrs` is
the single dispatch point — χ²/AIC/BIC and the fit figure both use it, so a
robust fit is scored and drawn with ``calc_Rrs_from_models_robust`` rather than
the elastic relation.

Provenance & artifacts
----------------------

Every ``fits`` row carries ``pab_version``, ``created``, and ``pkg_versions``
(a JSON snapshot from :func:`pab.config.package_versions`), plus the fit
diagnostics (reduced ``chisq``, ``aic``, ``bic``, ``accept_frac``, ``success``)
and the configuration (``anw_model``/``bbnw_model``/``prior_set``/``nsteps``/…).
Schema v5 adds the RT configuration itself — ``rt_backend``, ``include_raman``,
``include_chl_fl``, ``include_cdom_fl``, ``phi_c``, ``fit_bp`` — which is what
distinguishes a 2.0 row from a 1.0 one, since ``model_pair`` is identical
between them.

``pkg_versions`` also carries a ``git_sha`` map for ``PAB``, ``bing``, ``ocpy``,
``remote_sensing`` and ``retrieve-or-bust``. Four of those are editable installs
permanently reporting ``0.0.dev0``, so the **commit** is the only thing that
identifies the code a fit ran under. In a container (no ``.git``) the build
supplies them through the ``PAB_GIT_SHAS`` environment variable as a JSON
object, which takes precedence over anything ``git`` reports.

The bulky MCMC chains are **not** in the DB — they are written to
``PAB_DATA_DIR/fit_chains/<fit_id>.npz`` and referenced by ``fits.chains_path``.
Note that path keys off the **root** of ``PAB_DATA_DIR``, not off ``--db``: to
put a v2 run's chains in ``…/PAB/v2/fit_chains/`` you must set
``PAB_DATA_DIR=…/PAB/v2``.

How a fit links back to its matchup
-----------------------------------

A fit's deterministic id is
``"{matchup_id}_{ix}_{iy}_{model_pair}_v{pab_version}"``
(:func:`pab.fit.run.make_fit_id`). The **version suffix** is load-bearing:
``build_fits`` resumes by skipping any ``fit_id`` already in the store, so
without it a 2.0 run over a store holding 1.0 fits would skip every matchup as
"already done", and ``--replace`` would overwrite the published 1.0 rows instead
of adding to them. Ids written under 1.0 keep their original, unsuffixed form.
Note the suffix distinguishes *versions*, not *configurations*: two
configurations run at the same ``pab_version`` (e.g. a ``robust_ztt``
comparison arm) collide, and belong in separate databases.

The ``fits`` row carries ``matchup_id`` +
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
