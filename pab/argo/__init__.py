"""BGC-Argo ingestion and mixed-layer summary.

argopy fetch, QC filtering, mixed-layer depth (de Boyer Montégut), bbp
de-spiking, and per-profile mixed-layer averages, plus Q&A plots.

Public API::

    from pab.argo import fetch, mld, summary, qa

Implemented in Stage 2.
"""

from pab.argo import fetch, mld, qa, summary

__all__ = ["fetch", "mld", "qa", "summary"]
