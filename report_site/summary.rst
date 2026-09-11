PAB matchup results
===================


PACE ↔ BGC-Argo matchups: satellite vs. in-situ backscatter (``b_bp``) and chlorophyll, retrieved with BING. Built from ``pab_version`` ``1.1`` on 2026-09-10.

**PAB** validates ocean-colour retrievals from NASA's **PACE/OCI** satellite against in-situ profiles from autonomous **BGC-Argo** floats. For each float profile we find the closest-in-space-and-time PACE scene, extract the remote-sensing reflectance (``Rrs``) at the float, retrieve the inherent optical properties with **BING**, and compare the satellite-derived particulate backscatter ``b_bp`` and chlorophyll against the float's mixed-layer values. The headline numbers below summarise that comparison; the :doc:`comparisons <comparisons>` and :doc:`figures <figures>` give the per-matchup detail, and the :doc:`Methods <methods>` page explains how to read them.

Coverage
--------

- **Profiles ingested:** 54031
- **Matchups:** 14610
- **Floats:** 881
- **BING fits:** 14609
- **Median separation:** 0.804 km
- **Median Δtime:** 10.2 h

Headline comparison (b_bp 700 nm)
---------------------------------

- n = 13970; median sat/float ratio = 1.56; Spearman ρ = 0.498; log10 bias = 0.169, RMS = 0.371.

Chlorophyll
-----------

- n = 13839; median sat/float ratio = 0.782; Spearman ρ = 0.523.

BING vs NASA GIOP (b_bp)
------------------------

- n = 14603; median NASA(442 nm)/BING(700 nm) ratio = 1.51; Spearman ρ = 0.866. **The wavelengths differ by design** — see the :doc:`comparisons <comparisons>` and :doc:`Methods <methods>` pages before reading this as a bias.

Explore the results
-------------------

- :doc:`Comparisons <comparisons>` — interactive ``b_bp`` & Chl scatters and the matchup map.
- :doc:`Figures <figures>` — per-matchup fit, PACE scene, and Argo Q&A thumbnails.
- :doc:`Aggregate results <aggregates>` — binned statistics + a matchup quality table.
- :doc:`Methods <methods>` — how the analysis works and how to read these numbers.
- :doc:`Downloads <downloads>` — the summary tables (CSV/Parquet).
