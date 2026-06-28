Methods
=======


PAB matches BGC-Argo mixed-layer summaries to PACE/OCI Level-2 ``Rrs`` and retrieves IOPs with **BING** (Bayesian inference with Gordon coefficients; Prochaska & Frouin 2025). The matchup protocol follows **Bisson et al. (2019)** — a small unflagged pixel box near the float and a tight time window. The matchup observable is non-water backscatter ``b_bp``; chlorophyll is retrieved from the fitted ``Aph``.
