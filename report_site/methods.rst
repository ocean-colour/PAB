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

Retrieval configuration (2.0) & the two databases
-------------------------------------------------

**What changed in 2.0.** The 1.0 fits used the *elastic* Gordon radiative-transfer model: ``Rrs`` is produced by absorption and elastic scattering alone. 2.0 re-fits the same spectra with an **inelastic** forward model:

- **Radiative-transfer backend** — ``robust_hybrid`` (a neural-network emulator of a full RT solution) replaces the analytic ``gordon`` parameterisation.
- **Raman scattering** — water molecules re-emit absorbed blue light at longer wavelengths; included.
- **Chlorophyll fluorescence** — the ~685 nm phytoplankton emission line, at quantum yield ``phi_C = 0.02``; included.
- **CDOM fluorescence** — available in the model but **off** in this run, so none of the results below include it.
- **Free ``B_p``** — the backscatter phase-function parameter, held fixed in 1.0, is a sixth fitted parameter in 2.0 with a uniform prior over ``[0.004, 0.05]``.

The **fit window is unchanged** at 400–700 nm. The red edge (713/719 nm, where Raman and fluorescence are strongest) was evaluated and deliberately left out: on a 97-matchup diagnostic sample Rrs(719) is negative or noise-dominated on **44 %** of matchups, so including it would feed the inelastic terms mostly noise.

**``pab_version`` semantics.** Every row carries the version of the *analysis* that produced it, not of the code that wrote it. ``1.0`` is the elastic BING retrieval of the v1 release; ``2.0`` is the inelastic re-analysis in this one; ``1.1`` marks the NASA-GIOP ingests, which are the **same NASA product read by the same code** in both releases and so are deliberately *not* re-stamped ``2.0`` — a re-stamp would imply a re-analysis that did not happen.

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
- **BING vs NASA GIOP.** The *Comparisons* page includes NASA's own retrieval as a baseline: the operational ``PACE_OCI_L2_IOP`` product (**GIOP** algorithm, default configuration; Werdell et al. 2013), read at the **same pixel** used for each BING fit. NASA reports ``b_bp`` at **442 nm**, BING at **700 nm**; the comparison is deliberately **not** spectrally adjusted, and every figure/stat is labelled accordingly. **GSM is absent by NASA product availability, not by choice:** NASA does not operationally distribute a GSM (Garver-Siegel-Maritorena) Level-2 product for PACE — GIOP is the only distributed L2 IOP suite — so no GSM comparison is possible without reprocessing from Level-1B. The NASA-GIOP records carry ``pab_version = "1.1"`` (they were added alongside the existing ``1.0`` BING fits; the BING results are unchanged).
- **Provenance.** Every record is stamped with a ``pab_version``; the landing page shows the version and build date for this site. Per-matchup MCMC chains and figures are published as downloads (see the release manifest), keyed by matchup id.

References
----------

- Prochaska & Frouin (2025), *BING* — Bayesian inference of IOPs from remote-sensing reflectance with the Gordon model.
- Bisson et al. (2019) — satellite/in-situ ocean-colour matchup protocol and uncertainty assessment.

Provenance
----------


Built from ``pab_version`` ``2.0`` on 2026-10-05. Installed package versions:

.. list-table::
   :header-rows: 1

   * - package
     - version
   * - pab
     - 2.0
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
     - 920ab22
   * - bing
     - bf56f6d
   * - ocpy
     - 8d6396a
   * - remote_sensing
     - 2b85c65
   * - retrieve-or-bust
     - e1f4289
