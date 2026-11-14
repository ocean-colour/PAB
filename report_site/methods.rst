Methods
=======


This page explains what PAB does and how to read the results. PAB pairs satellite ocean-colour observations with in-situ float profiles, retrieves the optical properties from the satellite spectrum, and compares them against the float — a like-for-like validation of the satellite product.

Data
----

- **Satellite — PACE/OCI Level-2 AOP.** NASA's PACE mission (Ocean Colour Instrument) hyperspectral remote-sensing reflectance ``Rrs(λ)``, accessed by ``earthaccess``. PAB reads only the pixels near each float.
- **In-situ — BGC-Argo.** Autonomous biogeochemical floats, fetched via ``argopy``. PAB de-spikes and averages ``BBP700`` (particulate backscatter at 700 nm) and ``CHLA`` (chlorophyll-a) within the mixed layer, and records the mixed-layer depth (MLD) and mean temperature/salinity.

Matchup protocol
----------------

Following **Bisson et al. (2019)**: for each float profile PAB takes a small box of **unflagged** PACE pixels centred on the float position and a **tight time window** between the profile and the overpass. A profile with no qualifying pixels (cloud, glint, or simply no coincident scene) yields no matchup — that is expected, not an error. The space/time separation and the number of valid spectra for each matchup are listed in the *Matchup quality* table on the *Aggregate results* page.

Retrieval (BING)
----------------

The satellite ``Rrs`` spectrum is fit with **BING** (Bayesian inference with Gordon coefficients; Prochaska & Frouin 2025), which returns the inherent optical properties with full posterior uncertainties:

- **``b_bp``** — non-water particulate backscatter (reported at 700 nm, to match the float ``BBP700``); the primary matchup observable.
- **Chlorophyll** — retrieved from the fitted phytoplankton absorption amplitude ``Aph`` (``Chl = 10**Aph / 0.05582``). The float ``CHLA`` only *seeds* the absorption shape; it is **not** a fixed input, so the BING Chl is a genuine retrieval compared against the in-situ value. An independent **OC4** band-ratio Chl is shown as a cross-check when available.

**Failed retrievals.** A BING ``b_bp`` (700 nm) above 1 m⁻¹ is not a measurement of seawater (the open ocean spans roughly 1e-4 to 1e-1 m⁻¹) but an optimiser failure: the fit ran to the prior ceiling on a spectrum with a depressed or negative blue ``Rrs``. Such fits are **excluded from every ``b_bp`` statistic and figure** on this site — the headline, the density panels, both maps, the aggregates and the NASA-GIOP and 1.0-vs-2.0 comparisons — and each caption says how many. In this release that is 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded. The chlorophyll of the same fits is not gated, the figure gallery shows one such fit on purpose, and the downloadable summary table keeps the raw values with a 0/1 ``bbp_bing_implausible`` column so a reader can apply or lift the gate. In this release the 51 such 2.0 fits were re-fitted under ``pab_version`` 2.0.1 with the priors capped at physical ceilings (``b_bp`` (600 nm) ≤ 0.1 m⁻¹, ``A_dg`` ≤ 10 m⁻¹, ``A_ph`` ≤ 10 m⁻¹; BING's 10⁻⁶ floors unchanged) on the same spectrum; 51 of the 51 re-fitted fits land below the gate and are the values this site shows (the 2.0 rows stay in the database and the downloadable table marks the patched rows), so the gate now excludes 0; the figure gallery shows the one with the largest 2.0 value, re-fitted; 11 of the re-fitted fits retrieve a chlorophyll below 0.01 mg m⁻³ (``A_ph`` at its floor) and are not gated. What went wrong and why is in `high_bbp_outliers.md <https://github.com/ocean-colour/PAB/blob/main/versions/v2/high_bbp_outliers.md>`__.

**Negative-blue QA count.** Every fit also records ``n_neg_blue``: the number of bands of the fitted spectrum with ``Rrs < 0`` between 400 and 450 nm (inclusive), stored as the ``BING_ExpBPow_n_neg_blue`` quantity and carried as the ``n_neg_blue`` column of the downloadable summary table. It is a flag, not a screen: a spectrum with a negative blue band is fitted exactly like any other. It is recorded because a depressed or negative blue ``Rrs`` is what the failed retrievals have in common, while a negative band *anywhere* in the window is ordinary (the red bands of clear-water spectra dip below zero). Fits made before the quantity existed were backfilled from the spectrum stored with their chains, so fit-time and backfilled counts are the same number. In this release 156 of 15,971 fitted spectra (0.98 %) have at least one negative band at 400–450 nm (``n_neg_blue`` ≥ 1).

**Forward-model domain.** The ``robust_hybrid`` backend is retrieve-or-bust's analytic ZTT model plus a learned emulator correction, run with its out-of-domain policy at the default ``on_out_of_domain="warn"`` (the correction is applied everywhere and a warning is raised, never an error). The packaged emulator was trained at **nadir view and zero relative azimuth**, while the pixels fitted here are viewed at θ_v 13–60° (15,971 of 15,971 off-nadir), so the correction is applied outside its trained geometry for every fit. The alternative ``"ztt"`` policy — drop the correction outside the trained domain — was tested on the failed retrievals and a sample of ordinary fits and **not adopted**: it does not remove the runaway basin, which belongs to the analytic model, and it shifts ordinary ``b_bp``. The emulator's trained ``B_p`` range is [0.01026, 0.018], against BING's free-``B_p`` prior over [0.004, 0.05] (unchanged in this release). In this release the fitted ``B_p`` (posterior median) lies outside that range for 13,772 of 15,971 fits (86 %; 2,715 below, 11,057 above), so the learned correction extrapolates in ``B_p`` for most fits. The test and the questions it raises for the forward model are in `ztt_slice.md <https://github.com/ocean-colour/PAB/blob/main/versions/v2/ztt_slice.md>`__.

Retrieval configuration (2.0) & the two databases
-------------------------------------------------

**What changed in 2.0.** The 1.0 fits used the *elastic* Gordon radiative-transfer model: ``Rrs`` is produced by absorption and elastic scattering alone. 2.0 re-fits the same spectra with an **inelastic** forward model:

- **Radiative-transfer backend** — ``robust_hybrid`` (a neural-network emulator of a full RT solution) replaces the analytic ``gordon`` parameterisation.
- **Raman scattering** — water molecules re-emit absorbed blue light at longer wavelengths; included.
- **Chlorophyll fluorescence** — the ~685 nm phytoplankton emission line, at quantum yield ``phi_C = 0.02``; included.
- **CDOM fluorescence** — available in the model but **off** in this run, so none of the results below include it.
- **Free ``B_p``** — the backscatter phase-function parameter, held fixed in 1.0, is a sixth fitted parameter in 2.0 with a uniform prior over ``[0.004, 0.05]``.

The **fit window is unchanged** at 400–700 nm. The red edge (713/719 nm, where Raman and fluorescence are strongest) was evaluated and deliberately left out: on a 97-matchup diagnostic sample Rrs(719) is negative or noise-dominated on **44 %** of matchups, so including it would feed the inelastic terms mostly noise.

**``pab_version`` semantics.** Every row carries the version of the *analysis* that produced it, not of the code that wrote it. ``1.0`` is the elastic BING retrieval of the v1 release; ``2.0`` is the inelastic re-analysis in this one; ``1.1`` marks the NASA-GIOP ingests, which are the **same NASA product read by the same code** in both releases and so are deliberately *not* re-stamped ``2.0`` — a re-stamp would imply a re-analysis that did not happen. ``2.0.1`` is a **patch** to 2.0 — the same data, physics and matchup set, with the prior ceilings capped and applied only to the fits that ran away — stored as new rows next to the 2.0 ones; on this site a 2.0.1 row **supersedes the 2.0 row of the same matchup and pixel** in every statistic, figure and table, the 2.0 row stays in the database, and the ``pab_version`` column of the downloadable tables says which rows are patched.

**Two databases.** The 1.0 fits are not in this release's database. They live in the **frozen v1 database**, which is held read-only (and at an older schema) so published results cannot be edited after the fact; the 1.0-vs-2.0 comparison attaches it read-only and joins on matchup **and pixel**, so each pair is two retrievals of one spectrum. Matchups fitted in only one of the two releases are absent from that comparison rather than being half-filled.

How to read the figures & metrics
---------------------------------

Each scatter plots the **satellite** value (y) against the **in-situ** float value (x) on log axes, with the **1:1 line** for reference; points on the line are perfect agreement. **Hover** a point to see its matchup id, float, and values; **tap** a point to open that matchup's BING fit figure. The headline and binned tables report, per group:

- **median sat/float ratio** — typical multiplicative bias (1.0 = no bias);
- **Spearman ρ** — rank correlation between satellite and float (1 = perfectly monotonic);
- **log10 bias / RMS / MAD** — mean / scatter / robust scatter of ``log10(satellite / in-situ)`` (0 = unbiased; smaller is tighter).

The **PACE scene quick-looks** show the false-colour scene around each float (red star) with the analyzed pixels (white circles), so cloudy or glinty scenes are obvious. The **Argo profile Q&A** plots show ``BBP700`` and ``CHLA`` vs pressure with the MLD marked, to sanity-check each in-situ summary.

Caveats & provenance
--------------------

- **Sample size.** This release may cover a small development set; treat the aggregate statistics accordingly.
- **Granule access.** Run out-of-region (outside AWS ``us-west-2``), PACE reads are slow; PAB pre-downloads granules for reliability. This affects *how* the data were read, not the results.
- **BING vs NASA GIOP.** The *Comparisons* page includes NASA's own retrieval as a baseline: the operational ``PACE_OCI_L2_IOP`` product (**GIOP** algorithm, default configuration; Werdell et al. 2013), read at the **same pixel** used for each BING fit. NASA reports ``b_bp`` at **442 nm**, BING at **700 nm**; for the comparison NASA's value is shifted to 700 nm with GIOP's own per-pixel power-law slope ``bbp_s``: ``b_bp(700) = b_bp(442) × (442/700)^bbp_s`` (bounds scaled by the same factor; nothing is written back to the database). GIOP bounds the slope at 2.0, and 14.6 % of the slopes sit at that ceiling in this release — such a slope is a pinned fit rather than a measurement, so those pixels' 700 nm values are the least constrained. **GSM is absent by NASA product availability, not by choice:** NASA does not operationally distribute a GSM (Garver-Siegel-Maritorena) Level-2 product for PACE — GIOP is the only distributed L2 IOP suite — so no GSM comparison is possible without reprocessing from Level-1B. The NASA-GIOP records carry ``pab_version = "1.1"`` (they were added alongside the existing ``1.0`` BING fits; the BING results are unchanged).
- **Provenance.** Every record is stamped with a ``pab_version``; the landing page shows the version and build date for this site. Per-matchup MCMC chains and figures are published as downloads (see the release manifest), keyed by matchup id.

References
----------

- Prochaska & Frouin (2025), *BING* — Bayesian inference of IOPs from remote-sensing reflectance with the Gordon model.
- Bisson et al. (2019) — satellite/in-situ ocean-colour matchup protocol and uncertainty assessment.

Provenance
----------


Built from ``pab_version`` ``2.0.1`` on 2026-10-20. Installed package versions:

.. list-table::
   :header-rows: 1

   * - package
     - version
   * - pab
     - 2.0.1
   * - bing
     - 0.0.dev0
   * - ocpy
     - 0.1.dev0
   * - argopy
     - 1.4.0
   * - remote_sensing
     - 0.0.dev0
   * - earthaccess
     - 0.18.0
   * - robust
     - 0.0.dev0
   * - numpy
     - 2.5.2
   * - scipy
     - 1.18.0
   * - xarray
     - 2025.9.0


Source revisions (the editable installs all report ``0.0.dev0``, so the commit is what identifies the code):

.. list-table::
   :header-rows: 1

   * - repository
     - commit
   * - PAB
     - 1dd8435
   * - bing
     - bf56f6d
   * - ocpy
     - 51a572c
   * - remote_sensing
     - 2b85c65
   * - retrieve-or-bust
     - e1f4289
