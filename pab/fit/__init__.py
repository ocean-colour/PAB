"""BING fitting wrapper.

Configure the model pair (ExpBricaud + Pow) and priors, run the
LM warm-start -> MCMC pipeline, extract scalar IOPs + uncertainties into
namespaced columns, and write chains/provenance keyed by ID.

Public API::

    from pab.fit import FitConfig, fit_spectrum, fit_matchup, build_fits
    from pab.fit import models, run, artifacts

Implemented in Stage 5.
"""

from pab.fit import artifacts, models, run
from pab.fit.models import FitConfig, build_models
from pab.fit.run import (
    FitSpectrumResult,
    build_fits,
    chl_from_aph,
    extract_quantities,
    finite_or_none,
    fit_matchup,
    fit_spectrum,
    make_fit_id,
    prepare_spectrum,
)

__all__ = [
    "artifacts",
    "models",
    "run",
    "FitConfig",
    "FitSpectrumResult",
    "build_models",
    "build_fits",
    "chl_from_aph",
    "extract_quantities",
    "finite_or_none",
    "fit_matchup",
    "fit_spectrum",
    "make_fit_id",
    "prepare_spectrum",
]
