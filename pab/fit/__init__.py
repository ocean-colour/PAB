"""BING fitting wrapper, and the NASA-GIOP comparison-baseline ingest.

Configure the model pair (ExpBricaud + Pow) and priors, run the
LM warm-start -> MCMC pipeline, extract scalar IOPs + uncertainties into
namespaced columns, and write chains/provenance keyed by ID.

Public API::

    from pab.fit import FitConfig, fit_spectrum, fit_matchup, build_fits
    from pab.fit import models, run, artifacts, nasa_giop

Implemented in Stage 5; ``nasa_giop`` (the NASA-GIOP baseline; not a BING fit)
added in Stage 10b — see ``claude_prompts/pace_giop_gsm.md``.
"""

from pab.fit import artifacts, models, nasa_giop, replay, run
from pab.fit.models import FitConfig, build_models, prior_set_label
from pab.fit.nasa_giop import build_nasa_giop, ingest_nasa_giop_matchup
from pab.fit.replay import spectrum_from_chains
from pab.fit.run import (
    FitSpectrumResult,
    build_fits,
    chain_start_report,
    chl_from_aph,
    extract_quantities,
    finite_or_none,
    fit_matchup,
    fit_spectrum,
    make_fit_id,
    prepare_spectrum,
    rrs_qa_quantities,
)

__all__ = [
    "artifacts",
    "models",
    "nasa_giop",
    "replay",
    "run",
    "FitConfig",
    "FitSpectrumResult",
    "build_fits",
    "build_models",
    "build_nasa_giop",
    "chain_start_report",
    "chl_from_aph",
    "extract_quantities",
    "finite_or_none",
    "fit_matchup",
    "fit_spectrum",
    "ingest_nasa_giop_matchup",
    "make_fit_id",
    "prepare_spectrum",
    "prior_set_label",
    "rrs_qa_quantities",
    "spectrum_from_chains",
]
