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
- **BING vs NASA L2 IOPs.** A direct comparison against NASA's own L2 IOP product is planned but **not yet included**.
- **Provenance.** Every record is stamped with a ``pab_version``; the landing page shows the version and build date for this site. Per-matchup MCMC chains and figures are published as downloads (see the release manifest), keyed by matchup id.

References
----------

- Prochaska & Frouin (2025), *BING* — Bayesian inference of IOPs from remote-sensing reflectance with the Gordon model.
- Bisson et al. (2019) — satellite/in-situ ocean-colour matchup protocol and uncertainty assessment.

Provenance
----------


Built from ``pab_version`` ``0.0.dev0`` on 2026-07-01. Installed package versions:

.. list-table::
   :header-rows: 1

   * - package
     - version
   * - pab
     - 0.0.dev0
   * - bing
     - not installed
   * - ocpy
     - not installed
   * - argopy
     - not installed
   * - remote_sensing
     - not installed
   * - earthaccess
     - not installed
   * - numpy
     - 2.2.5
   * - scipy
     - 1.15.2
   * - xarray
     - 2025.3.1
