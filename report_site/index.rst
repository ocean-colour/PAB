PAB — PACE ↔ BGC-Argo Matchups
==============================


**PAB** produces **matchup analyses between PACE (satellite ocean colour) and BGC-Argo (autonomous float) data**, and shares the results with the community.

Why
---

Satellite ocean-colour missions like NASA's **PACE** retrieve the ocean's inherent optical properties (IOPs) and chlorophyll from space — but those retrievals need validation against independent, in-situ measurements. **BGC-Argo** floats drift through the global ocean returning vertical profiles of exactly the quantities PACE estimates: particulate backscatter (``BBP700``) and chlorophyll (``CHLA``). PAB pairs the two — for every float profile it finds the coincident PACE scene, retrieves the IOPs from the satellite spectrum with **BING**, and compares them against the float. The result is a growing, reproducible record of how well the satellite agrees with the ocean.

What PAB does
-------------

For each BGC-Argo profile, PAB:

#. **Matches** it to the closest-in-space-and-time PACE/OCI Level-2 scene (following Bisson et al. 2019 — an unflagged pixel box and a tight time window);
#. **Extracts** the ~10 nearest remote-sensing reflectance (``Rrs``) spectra;
#. **Retrieves** the IOPs — non-water backscatter ``b_bp`` and chlorophyll — with **BING** (Bayesian inference with Gordon coefficients), with full posterior uncertainties;
#. **Compares** the satellite retrieval against the float's mixed-layer values.

What's on this site
-------------------

- :doc:`Summary <summary>` — dataset coverage and the headline satellite-vs-float ``b_bp`` and chlorophyll metrics.
- :doc:`Comparisons <comparisons>` — the interactive ``b_bp`` and chlorophyll scatter plots and the matchup map (hover for values, tap for the fit figure).
- :doc:`Figures <figures>` — per-matchup BING fit figures, PACE scene quick-looks, and the Argo profile Q&A plots.
- :doc:`Aggregate results <aggregates>` — population statistics binned by region and season (plus an equal-area HEALPix view) and a per-matchup quality table.
- :doc:`Methods <methods>` — the data, the matchup protocol, the BING retrieval, how to read the figures and metrics, caveats, provenance, and references.
- :doc:`Downloads <downloads>` — the exported summary tables (CSV/Parquet).

New here? Start with the :doc:`Summary <summary>`, then open the :doc:`Comparisons <comparisons>`. Every result is stamped with a ``pab_version`` for provenance.

.. toctree::
   :maxdepth: 1
   :hidden:

   summary
   comparisons
   figures
   aggregates
   methods
   downloads
