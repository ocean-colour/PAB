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
        include_Raman: Include the Raman-scattering term. **Default ``True``
            as of 2.0** (it was ``False`` for the elastic 1.0 fits).
        rt_backend: Which forward model turns ``(a, bb)`` into ``Rrs`` — one
            of ``bing.rt.defs.RT_BACKENDS``. ``'robust_hybrid'`` (2.0) is
            retrieve-or-bust's analytic model plus a learned emulator
            correction, valid for 350–750 nm; ``'gordon'`` is BING's own
            elastic Gordon (1988) model, which 1.0 used.
        include_Chl_fl: Include chlorophyll fluorescence (2.0: ``True``).
        include_CDOM_fl: Include CDOM fluorescence (2.0: ``False`` — the
            Hawes kernel needs a pure-CDOM source term that BING can only
            approximate as ``cdom_fraction * a_dg``).
        phi_C: Chlorophyll-fluorescence quantum yield.
        fit_Bp: Sample ``B_p`` (the backscattering-ratio / phase-function
            parameter) as a **free** MCMC parameter rather than holding it at
            :attr:`Bp_value`. Robust backends only — ``fit_Bp=True`` with
            ``rt_backend='gordon'`` is rejected by ``validate_rt_dict``,
            since Gordon has no phase-function input. Sampled **linearly**
            over ``[BP_PRIOR_PMIN, BP_PRIOR_PMAX] = [0.004, 0.05]``.
        Bp_value: Fixed value for ``B_p`` when ``fit_Bp`` is False, and the
            walker-ball seed when it is True.
        analysis_burn: Production steps dropped before computing posterior
            statistics (BING convention is 7000 for long chains; the
            reconstruction falls back to ``nsteps // 2`` when the chain is
            shorter, so short test runs still yield samples).
        perc: Lower/upper percentiles for the stored credible interval.

    The defaults are the **2.0** configuration. :meth:`v1` returns the frozen
    1.0 one, so published results stay reproducible and 2.0-vs-1.0
    comparisons are a one-line change rather than six remembered keywords.
    """

    model_pair: str = "ExpBPow"
    satellite: str = "PACE"
    nsteps: int = 10000
    nburn: int = 1000
    wave_min: float = 400.0
    wave_max: float = 720.0
    variable_Gordon: bool = False
    include_Raman: bool = True
    # --- radiative transfer (2.0) ---
    rt_backend: str = "robust_hybrid"
    include_Chl_fl: bool = True
    include_CDOM_fl: bool = False
    phi_C: float = 0.02
    fit_Bp: bool = True
    Bp_value: float = 0.01
    analysis_burn: int = 7000
    perc: tuple[float, float] = (5.0, 95.0)

    @classmethod
    def v1(cls, **overrides) -> FitConfig:
        """The frozen **1.0** configuration: elastic Gordon, 400–700 nm, fixed B_p.

        This is what produced the published 1.0 fits
        (``$PAB_DATA_DIR/v1/pab.db``), kept as a named constructor so the
        comparison arm of the 2.0 analysis cannot drift from it by accident.

        Args:
            **overrides: Any field to change (e.g. ``nsteps=1000`` for a test);
                the RT settings below are the point of the classmethod, so
                overriding those defeats it.

        Returns:
            A :class:`FitConfig` with ``rt_backend='gordon'``,
            ``include_Raman=False``, ``include_Chl_fl=False``,
            ``include_CDOM_fl=False``, ``fit_Bp=False`` and
            ``wave_max=700.0``.
        """
        v1 = {
            "wave_max": 700.0,
            "rt_backend": "gordon",
            "include_Raman": False,
            "include_Chl_fl": False,
            "include_CDOM_fl": False,
            "fit_Bp": False,
        }
        return cls(**{**v1, **overrides})


def build_models(config: FitConfig, wave, *, geom=None, validate: bool = True):
    """Build the BING ``(p, rt_dict, models)`` for a fit on grid ``wave``.

    Constructs the standard parameter config for ``config.model_pair``, the
    radiative-transfer dict, the two model objects on the data wavelength grid,
    and attaches the standard priors. Does **not** call ``init_other_bits``
    (that needs ``Chl``/``Y``/``Rrs`` at fit time — see :func:`pab.fit.run`).

    The RT fields are forwarded to the BING factory as extra keywords, which
    ``p_ntuple.gen`` turns into fields on ``p``; ``rt_dict_from_p`` then reads
    them back with ``getattr(p, key, <default>)``, so a legacy ``p`` still
    yields a valid Gordon-backend dict.

    Args:
        config: The fit configuration.
        wave: Wavelength grid (nm) the models are initialised on.
        geom: ``bing.rt.geometry.ObsGeometry`` for this pixel. **Required by a
            robust backend** — ``validate_rt_dict`` refuses to let
            ``theta_s`` be silently defaulted (R3), so a robust
            ``config`` with ``geom=None`` raises here rather than fitting the
            wrong physics.
        validate: Run ``bing.rt.defs.validate_rt_dict`` once at setup. Leave
            it on; ``False`` exists for constructing models in contexts that
            legitimately have no geometry (e.g. inspecting priors).

    Returns:
        ``(p, rt_dict, models)`` — the BING param ntuple, the RT config dict,
        and ``[anw_model, bbnw_model]``.

    Raises:
        KeyError: if ``config.model_pair`` is not in :data:`BING_COMBO`.
        ValueError: if the RT configuration is illegal — an unknown backend,
            ``fit_Bp`` with Gordon, a robust backend without ``geom``, a
            ``robust_hybrid`` wavelength outside 350–750 nm, or an
            ``include_CDOM_fl`` combination the a-model cannot supply.
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
        rt_backend=config.rt_backend,
        include_Chl_fl=config.include_Chl_fl,
        include_CDOM_fl=config.include_CDOM_fl,
        phi_C=config.phi_C,
        fit_Bp=config.fit_Bp,
        Bp_value=config.Bp_value,
    )
    rt_dict = rt_defs.rt_dict_from_p(p)
    models = model_utils.init(p.model_names, np.asarray(wave, dtype=float))
    bing_priors.set_standard_priors(models, p)
    if validate:
        rt_defs.validate_rt_dict(rt_dict, models=models, geom=geom)
    return p, rt_dict, models


def model_param_names(models) -> list[str]:
    """Flat list of free-parameter names across the model pair (anw then bbnw)."""
    return list(models[0].pnames) + list(models[1].pnames)
