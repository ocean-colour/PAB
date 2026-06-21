"""BING model-pair + prior configuration (the fitting seam, Stage 5).

PAB fits PACE ``Rrs`` with `BING <https://github.com/ocean-colour/bing>`_. This
module holds the small, dependency-light configuration (:class:`FitConfig`) and
the one function that turns it into the BING objects a fit needs — the radiative
-transfer dict, the model pair, and its priors. ``bing`` is imported lazily
inside :func:`build_models` so ``import pab.fit`` works in the lean CI
environment (``bing`` is mocked / construction-only there).

The default pair is the workhorse **``ExpBricaud`` + ``Pow``** (exponential
CDOM/detritus + Bricaud phytoplankton absorption; power-law non-water
backscatter). A different pair slots in by adding to :data:`BING_COMBO` and
naming it via ``FitConfig.model_pair`` — results stay namespaced by that label
(``BING_<model_pair>_<quantity>``) so the DB schema never changes.
"""

from __future__ import annotations

from dataclasses import dataclass

#: PAB ``model_pair`` label → the ``bing.parameters.standard`` factory name.
BING_COMBO: dict[str, str] = {
    "ExpBPow": "expb_pow",  # ExpBricaud + Pow (the workhorse)
}


@dataclass(frozen=True)
class FitConfig:
    """Configuration for a BING fit.

    Attributes:
        model_pair: PAB label for the model pair (key of :data:`BING_COMBO`);
            also the namespace prefix for stored quantities.
        satellite: Sensor whose noise model BING uses (``'PACE'``).
        nsteps: MCMC production steps (after burn-in). Default 10000 — lighter
            than BING's research default but adequate for these retrievals; the
            posterior analysis drops :attr:`analysis_burn` of these.
        nburn: emcee burn-in steps (discarded by ``run_emcee`` before
            production).
        wave_min, wave_max: Fit window (nm); the spectrum is restricted to it.
        variable_Gordon: Use wavelength-dependent Gordon coefficients (PAB keeps
            the constant-coefficient default, ``False``).
        include_Raman: Include the Raman-scattering term (default ``False``).
        analysis_burn: Production steps dropped before computing posterior
            statistics (BING convention is 7000 for long chains; the
            reconstruction falls back to ``nsteps // 2`` when the chain is
            shorter, so short test runs still yield samples).
        perc: Lower/upper percentiles for the stored credible interval.
    """

    model_pair: str = "ExpBPow"
    satellite: str = "PACE"
    nsteps: int = 10000
    nburn: int = 1000
    wave_min: float = 400.0
    wave_max: float = 700.0
    variable_Gordon: bool = False
    include_Raman: bool = False
    analysis_burn: int = 7000
    perc: tuple[float, float] = (5.0, 95.0)


def build_models(config: FitConfig, wave):
    """Build the BING ``(p, rt_dict, models)`` for a fit on grid ``wave``.

    Constructs the standard parameter config for ``config.model_pair``, the
    radiative-transfer dict, the two model objects on the data wavelength grid,
    and attaches the standard priors. Does **not** call ``init_other_bits``
    (that needs ``Chl``/``Y``/``Rrs`` at fit time — see :func:`pab.fit.run`).

    Args:
        config: The fit configuration.
        wave: Wavelength grid (nm) the models are initialised on.

    Returns:
        ``(p, rt_dict, models)`` — the BING param ntuple, the RT config dict,
        and ``[anw_model, bbnw_model]``.

    Raises:
        KeyError: if ``config.model_pair`` is not in :data:`BING_COMBO`.
    """
    import numpy as np
    from bing.models import utils as model_utils
    from bing.parameters import standard
    from bing.priors import priors as bing_priors
    from bing.rt import defs as rt_defs

    if config.model_pair not in BING_COMBO:
        raise KeyError(
            f"unknown model_pair {config.model_pair!r}; known: {list(BING_COMBO)}"
        )
    gen = getattr(standard, BING_COMBO[config.model_pair])
    p = gen(
        satellite=config.satellite,
        nsteps=config.nsteps,
        nburn=config.nburn,
        variable_Gordon=config.variable_Gordon,
        include_Raman=config.include_Raman,
        wv_min=config.wave_min,
        wv_max=config.wave_max,
    )
    rt_dict = rt_defs.rt_dict_from_p(p)
    models = model_utils.init(p.model_names, np.asarray(wave, dtype=float))
    bing_priors.set_standard_priors(models, p)
    return p, rt_dict, models


def model_param_names(models) -> list[str]:
    """Flat list of free-parameter names across the model pair (anw then bbnw)."""
    return list(models[0].pnames) + list(models[1].pnames)
