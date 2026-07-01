PAB matchup results
===================


PACE ↔ BGC-Argo matchups: satellite vs. in-situ backscatter (``b_bp``) and chlorophyll, retrieved with BING. Built from ``pab_version`` ``0.0.dev0`` on 2026-07-01.

**PAB** validates ocean-colour retrievals from NASA's **PACE/OCI** satellite against in-situ profiles from autonomous **BGC-Argo** floats. For each float profile we find the closest-in-space-and-time PACE scene, extract the remote-sensing reflectance (``Rrs``) at the float, retrieve the inherent optical properties with **BING**, and compare the satellite-derived particulate backscatter ``b_bp`` and chlorophyll against the float's mixed-layer values. The headline numbers below summarise that comparison; the figures give the per-matchup detail and the *Methods* page explains how to read them.

Coverage
--------

- **Profiles ingested:** 10
- **Matchups:** 4
- **Floats:** 2
- **BING fits:** 4
- **Median separation:** 0.386 km
- **Median Δtime:** 8.27 h

Headline comparison (b_bp 700 nm)
---------------------------------

- n = 4; median sat/float ratio = 2.22; Spearman ρ = 0.4; log10 bias = 0.357, RMS = 0.365.

Chlorophyll
-----------

- n = 4; median sat/float ratio = 0.742; Spearman ρ = 0.6.
