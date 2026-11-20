PAB matchup results
===================


PACE ↔ BGC-Argo matchups: satellite vs. in-situ backscatter (``b_bp``) and chlorophyll, retrieved with BING. Built from ``pab_version`` ``2.1`` on 2026-11-18.

**PAB** validates ocean-colour retrievals from NASA's **PACE/OCI** satellite against in-situ profiles from autonomous **BGC-Argo** floats. For each float profile we find the closest-in-space-and-time PACE scene, extract the remote-sensing reflectance (``Rrs``) at the float, retrieve the inherent optical properties with **BING**, and compare the satellite-derived particulate backscatter ``b_bp`` and chlorophyll against the float's mixed-layer values. The headline numbers below summarise that comparison; the :doc:`comparisons <comparisons>` and :doc:`figures <figures>` give the per-matchup detail, and the :doc:`Methods <methods>` page explains how to read them.

Coverage
--------

- **Profiles ingested:** 59620
- **Matchups:** 15976
- **Floats:** 912
- **BING fits:** 15,971 (``pab_version`` 2.1)
- **Median separation:** 0.804 km
- **Median Δtime:** 10.2 h

Headline comparison (b_bp 700 nm)
---------------------------------

- n = 15274; median sat/float ratio = 1.33; Spearman ρ = 0.465; log10 bias = 0.0671, RMS = 0.461. 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded — see the :doc:`Methods <methods>` page.

Chlorophyll
-----------

- n = 15154; median sat/float ratio = 0.926; Spearman ρ = 0.759.

BING vs NASA GIOP (b_bp)
------------------------

- n = 15964; median NASA(700 nm)/BING(700 nm) ratio = 0.778; Spearman ρ = 0.927; 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded. NASA's ``b_bp`` is shifted from 442 nm to 700 nm with its own per-pixel slope — see the :doc:`comparisons <comparisons>` and :doc:`Methods <methods>` pages for the formula and its caveat.

1.0 vs 2.1 (elastic vs inelastic)
---------------------------------

The same 14,604 matchups and the same pixels, retrieved with the elastic (1.0) and inelastic (2.1) forward model — what the re-analysis changed:

- **b_bp(700 nm)** — median 2.1/1.0 ratio = 0.877 (n = 14,604; 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded)

- **chlorophyll** — median 2.1/1.0 ratio = 1.14 (n = 14,604)

The :doc:`Comparisons <comparisons>` page has the scatters, the full statistics, and what exactly differs between the two configurations.

What changed in 2.1
-------------------

2.1 evaluates the forward model at the normalized geometry the PACE ``Rrs`` is distributed at (sun at zenith, nadir view) instead of the observed angles 2.0 used; over the 15,971 fits paired on matchup and pixel, the median ``b_bp`` (700 nm) ratio of 2.1 to 2.0 (2.0.1 where re-fitted) is **1.17**, rising with the solar zenith angle — see `geometry_rerun.md <https://github.com/ocean-colour/PAB/blob/main/versions/v2.1/geometry_rerun.md>`__ and the :doc:`Methods <methods>` page.

Explore the results
-------------------

- :doc:`Comparisons <comparisons>` — interactive ``b_bp`` & Chl scatters and the matchup map.
- :doc:`Figures <figures>` — per-matchup fit, PACE scene, and Argo Q&A thumbnails.
- :doc:`Aggregate results <aggregates>` — binned statistics + a matchup quality table.
- :doc:`Methods <methods>` — how the analysis works and how to read these numbers.
- :doc:`Downloads <downloads>` — the summary tables (CSV/Parquet).
