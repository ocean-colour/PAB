PAB matchup results
===================


PACE ↔ BGC-Argo matchups: satellite vs. in-situ backscatter (``b_bp``) and chlorophyll, retrieved with BING. Built from ``pab_version`` ``2.0.1`` on 2026-10-20.

**PAB** validates ocean-colour retrievals from NASA's **PACE/OCI** satellite against in-situ profiles from autonomous **BGC-Argo** floats. For each float profile we find the closest-in-space-and-time PACE scene, extract the remote-sensing reflectance (``Rrs``) at the float, retrieve the inherent optical properties with **BING**, and compare the satellite-derived particulate backscatter ``b_bp`` and chlorophyll against the float's mixed-layer values. The headline numbers below summarise that comparison; the :doc:`comparisons <comparisons>` and :doc:`figures <figures>` give the per-matchup detail, and the :doc:`Methods <methods>` page explains how to read them.

Coverage
--------

- **Profiles ingested:** 59620
- **Matchups:** 15976
- **Floats:** 912
- **BING fits:** 15,971 (15,920 at 2.0, 51 re-fitted at 2.0.1)
- **Median separation:** 0.804 km
- **Median Δtime:** 10.2 h

Headline comparison (b_bp 700 nm)
---------------------------------

- n = 15274; median sat/float ratio = 1.14; Spearman ρ = 0.414; log10 bias = -0.0146, RMS = 0.493. 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded — see the :doc:`Methods <methods>` page.

Chlorophyll
-----------

- n = 15154; median sat/float ratio = 0.945; Spearman ρ = 0.741.

BING vs NASA GIOP (b_bp)
------------------------

- n = 15964; median NASA(700 nm)/BING(700 nm) ratio = 0.938; Spearman ρ = 0.889; 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded. NASA's ``b_bp`` is shifted from 442 nm to 700 nm with its own per-pixel slope — see the :doc:`comparisons <comparisons>` and :doc:`Methods <methods>` pages for the formula and its caveat.

1.0 vs 2.0 (elastic vs inelastic)
---------------------------------

The same 14,604 matchups and the same pixels, retrieved with the elastic (1.0) and inelastic (2.0) forward model — what the re-analysis changed:

- **b_bp(700 nm)** — median 2.0/1.0 ratio = 0.749 (n = 14,604; 0 failed retrievals (0.00 %, ``b_bp`` > 1 m⁻¹) excluded)

- **chlorophyll** — median 2.0/1.0 ratio = 1.17 (n = 14,604)

The :doc:`Comparisons <comparisons>` page has the scatters, the full statistics, and what exactly differs between the two configurations.

Explore the results
-------------------

- :doc:`Comparisons <comparisons>` — interactive ``b_bp`` & Chl scatters and the matchup map.
- :doc:`Figures <figures>` — per-matchup fit, PACE scene, and Argo Q&A thumbnails.
- :doc:`Aggregate results <aggregates>` — binned statistics + a matchup quality table.
- :doc:`Methods <methods>` — how the analysis works and how to read these numbers.
- :doc:`Downloads <downloads>` — the summary tables (CSV/Parquet).
