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
     - 700 nm
     - 700 nm

``rt_backend`` selects the forward model that turns ``(a, bb)`` into ``Rrs``:
``'gordon'`` is BING's own elastic Gordon (1988) relation; ``'robust_hybrid'``
is retrieve-or-bust's analytic ZTT model plus a learned emulator correction,
valid over 350–750 nm, comfortably containing the 400–700 nm window.

.. note::

   2.0 briefly defaulted to ``wave_max = 720`` to reach the red shoulder for
   the inelastic terms. It was moved back to **700** after the first real
   fits: the PACE 719 nm band is unusable on a large fraction of matchups —
   ``Rrs(719)`` came back **negative on 6 of 20** local matchups and
   noise-dominated on 2 more, and the χ² degradation of 2.0 against 1.0 was
   concentrated entirely on those (1.84× versus 1.24× where the band was
   usable). The chlorophyll-fluorescence peak (~685 nm) is inside 700, so the
   inelastic physics is unaffected. **2.0 and 1.0 therefore fit the same
   band** — they differ by radiative transfer, not by window.

Every backend
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

Prior ceilings (2.0.1)
----------------------

BING's standard ``ExpBPow`` priors are log-uniform over [10⁻⁶, 10⁵] m⁻¹ for
``Adg``, ``Aph`` and ``Bnw`` (``Bnw`` is ``b_bp`` at the 600 nm pivot). On
spectra with a depressed or negative blue ``Rrs`` the Levenberg–Marquardt
warm-start can deliver the walkers to the ``Bnw`` ceiling, where
``b_b ≫ a`` and the reflectance saturates; the chains never leave it, and the
fit reports ``b_bp`` ≈ 10⁵ m⁻¹ (51 of the 15,971 2.0 fits —
``versions/v2/high_bbp_outliers.md``). From ``pab_version = "2.0.1"`` the
:class:`~pab.fit.models.FitConfig` defaults therefore carry **physical
ceilings**, ``bbp600_max = 0.1``, ``adg_max = 10.0``, ``aph_max = 10.0`` (m⁻¹;
``None`` = BING's 10⁵), applied in :func:`~pab.fit.models.build_models` as a
PAB-side override: the factory's own prior dicts are copied and only the
``pmax`` of those three parameters is set to ``log10(ceiling)`` — the floors,
the ``Sdg``/``beta`` priors and BING itself are untouched, and both the LM
bounds and BING's ``log_prob`` see the same ceiling. ``fits.prior_set`` records
it (:func:`~pab.fit.models.prior_set_label`:
``"bing_standard+ceiling:bbp600<=0.1,adg<=10,aph<=10"``, or ``"bing_standard"``
when all three are ``None``), and :func:`~pab.fit.models.ceilings_from_prior_set`
inverts the label so a figure rebuilt from a row cannot misdescribe its priors.
:meth:`~pab.fit.models.FitConfig.v2_0` is the frozen, unceilinged 2.0
configuration and :meth:`~pab.fit.models.FitConfig.v1` also sets the three to
``None`` — the published priors never change retroactively.

Two checks accompany the ceilings. :func:`pab.fit.run.chain_start_report`
reports the step-0 walker median of each capped parameter in dex below its
ceiling and ``started_below_wall`` (≥ 0.5 dex under the ceiling);
:func:`~pab.fit.run.fit_spectrum` logs a warning when it is false (never
fails) and :class:`~pab.fit.run.FitSpectrumResult` carries the dict. And the
**replay seam** — :func:`~pab.fit.run.build_fits` / :func:`~pab.fit.run.fit_matchup`
accept a ``spectra``/``spectrum`` provider and
:func:`pab.fit.replay.spectrum_from_chains` returns the ``wave``/``Rrs``/
``sqrt(varRrs)`` stored in the 2.0 fit's chain NPZ (CLI ``--replay-chains DIR``)
— lets a patch re-fit see **bit-identical** input, so 2.0 → 2.0.1 differs by
the prior and nothing else; such a fit is stamped
``rrs_source = "L2_AOP:replay:<2.0 fit_id>"``. On the 51 runaways the 2.0.1
re-fit started below the wall in every case, lowered χ² in every case
(median 8×), landed below the 1 m⁻¹ gate in every case and never within 5 %
of a ceiling; its rows sit next to the 2.0 ones and the report overlays them
(below).

Negative-blue QA count
----------------------

Every fit also records one QA quantity, ``n_neg_blue``
(:func:`pab.fit.run.rrs_qa_quantities`): the number of finite bands with
``Rrs < 0`` between 400 and 450 nm inclusive (:data:`pab.fit.run.BLUE_QA_BAND`),
computed on the **windowed** spectrum — exactly what the chain NPZ stores — so a
fit-time value and one backfilled from the NPZ agree by construction. It is
stored like any other quantity (``BING_ExpBPow_n_neg_blue``, ``value_lo =
value_hi = value``, unit ``bands``), it is a flag and never a refusal, and
``python -m pab.fit.rrs_qa_backfill --db … --chains-root DIR`` backfills it for
fits that predate it (resolving ``chains_path`` by basename; a real run
requires a sha-verified ``--backup-copy``, prints a fingerprint before and
after, and refuses to proceed if anything but the QA rows changed). In the v2
database 156 of 15,971 2.0 spectra (0.98 %) have at least one negative blue
band; 40 of the 51 runaways do.

Forward-model domain
--------------------

``robust_hybrid`` runs retrieve-or-bust's hybrid — the analytic ZTT backbone
plus a learned emulator correction — with the out-of-domain policy at robust's
default ``on_out_of_domain="warn"`` (BING never passes the argument; the
warning is silent under ``jit``). The packaged emulator was trained at **nadir
view and zero relative azimuth**, and every PACE pixel PAB fits is off-nadir
(θ_v 13–60°), so robust's domain check flags every sample of every fit; the
``"ztt"`` policy as shipped is therefore pure ZTT for the whole mission. It was
tested on the 51 runaways and 50 ordinary fits (``versions/v2/ztt_slice.md``)
and **not adopted**: it does not remove the runaway basin or the χ² wall (both
belong to the backbone's ``u → 1`` limit), it rescues 32 LM runaways while
creating 3, and it shifts ordinary ``b_bp``(700) by +0.05–0.10 dex with no χ²
gain (Q&A/Outliers 12 = A — no ``FitConfig`` field; the question is carried to
the bing/robust repos). Separately, the emulator's trained ``B_p`` range is
[0.0103, 0.018] while BING's free-``B_p`` prior is [0.004, 0.05] with the seed
at 0.01, so the fitted ``B_p`` lies **outside the trained range for ~86 % of v2
fits** and the hybrid extrapolates in ``B_p`` whatever the policy — stated on
the report's Methods page with the fraction computed from the database
(:func:`pab.metrics.compare.forward_model_domain_summary`, the range read from
``robust`` by :func:`~pab.metrics.compare.emulator_bp_domain`), not changed in
v2 (Q&A/Outliers 13 = A: a narrower prior would be a full re-fit, not a patch).

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
comparison arm) collide, and belong in separate databases. A **patch**
version (``2.0.1``: the 2.0 runaways re-fitted with the prior ceilings) shares
its base's database and matchup set — its fits are new ``…_v2.0.1`` rows next
to the untouched 2.0 rows, and the report overlays a patch row on the base row
of the same matchup **and pixel** (:func:`pab.metrics.compare.overlay_patch`).

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
