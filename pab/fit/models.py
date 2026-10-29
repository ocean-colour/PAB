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

import math
from dataclasses import dataclass

#: PAB ``model_pair`` label → the ``bing.parameters.standard`` factory name.
BING_COMBO: dict[str, str] = {
    "ExpBPow": "expb_pow",  # ExpBricaud + Pow (the workhorse)
}

#: The ``prior_set`` stamp of BING's own ``expb_pow`` priors, untouched.
PRIOR_SET_STANDARD = "bing_standard"

#: Prefix of the ``prior_set`` stamp when PAB caps the ceilings (2.0.1).
PRIOR_SET_CEILING_PREFIX = PRIOR_SET_STANDARD + "+ceiling:"

#: ``FitConfig`` ceiling field → (``prior_set`` token, BING parameter name).
#: Order fixed: it is the order the tokens appear in the ``prior_set`` string.
#: ``Bnw`` is the Pow model's log10 amplitude **at its 600 nm pivot**
#: (``bing/models/bbnw.py``: ``bb_nw = 10**Bnw * (600/wave)**beta``), hence
#: ``bbp600``; ``Adg``/``Aph`` are ExpBricaud's log10 amplitudes at 440 nm.
CEILING_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("bbp600_max", "bbp600", "Bnw"),
    ("adg_max", "adg", "Adg"),
    ("aph_max", "aph", "Aph"),
)

#: ``log10`` upper bound of BING's standard log-uniform priors (10⁵ m⁻¹) —
#: what a ``None`` ceiling leaves in place.
BING_LOG_PMAX = 5.0


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
            **400–700 for both 1.0 and 2.0.** 2.0 briefly defaulted to 720 to
            reach the red shoulder, but the 719 nm PACE band is unusable on a
            large fraction of matchups — ``Rrs(719)`` came back *negative* on
            6 of 20 local matchups and noise-dominated on 2 more, and the
            resulting χ² degradation was concentrated entirely on those (JXP,
            ``build_v2_prompt_3.md`` Q2). The chlorophyll-fluorescence peak
            (~685 nm) is inside 700, so the inelastic physics is unaffected.
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
        bbp600_max, adg_max, aph_max: **Physical prior ceilings** (m⁻¹) on
            the Pow amplitude ``Bnw`` (= ``b_bp`` at the 600 nm pivot) and
            the ExpBricaud amplitudes ``Adg``/``Aph`` (at 440 nm). BING's
            ``expb_pow`` puts log-uniform [10⁻⁶, 10⁵] priors on all three;
            ``None`` keeps that 10⁵. The 2.0.1 defaults (0.1, 10, 10) exist
            because 51 of the 15,971 2.0 fits ran away to the 10⁵ wall
            (``versions/v2/high_bbp_outliers.md``): the LM warm-start
            delivered the walker ball to the ceiling and it never left,
            although a better physical basin existed in every re-fitted
            case. Applied by :func:`build_models` as a **PAB-side override**
            of the factory's prior dicts — BING itself is untouched — so both
            the LM bounds and the MCMC ``log_prob`` see the same ceiling.
            Recorded on every fit as ``fits.prior_set``
            (:func:`prior_set_label`). Q&A/Outliers 2 = A.

    The defaults are the **2.0.1** configuration — the 2.0 physics with the
    ceilings. :meth:`v2_0` returns the frozen, unceilinged 2.0 configuration
    and :meth:`v1` the frozen 1.0 one, so published results stay reproducible
    and version comparisons are a one-line change rather than remembered
    keywords.
    """

    model_pair: str = "ExpBPow"
    satellite: str = "PACE"
    nsteps: int = 10000
    nburn: int = 1000
    wave_min: float = 400.0
    wave_max: float = 700.0
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
    # --- physical prior ceilings (2.0.1); None = BING's 1e5 ---
    bbp600_max: float | None = 0.1
    adg_max: float | None = 10.0
    aph_max: float | None = 10.0

    #: The three ceiling fields set to ``None`` — BING's own priors, verbatim.
    _NO_CEILINGS = {"bbp600_max": None, "adg_max": None, "aph_max": None}

    @classmethod
    def v1(cls, **overrides) -> FitConfig:
        """The frozen **1.0** configuration: elastic Gordon, 400–700 nm, fixed B_p.

        This is what produced the published 1.0 fits
        (``$PAB_DATA_DIR/v1/pab.db``), kept as a named constructor so the
        comparison arm of the 2.0 analysis cannot drift from it by accident.
        The 1.0 fits ran on BING's unceilinged priors, so the three ceilings
        are ``None`` here — they must not change retroactively.

        Args:
            **overrides: Any field to change (e.g. ``nsteps=1000`` for a test);
                the RT settings below are the point of the classmethod, so
                overriding those defeats it.

        Returns:
            A :class:`FitConfig` with ``rt_backend='gordon'``,
            ``include_Raman=False``, ``include_Chl_fl=False``,
            ``include_CDOM_fl=False``, ``fit_Bp=False``, ``wave_max=700.0``
            and no prior ceilings.
        """
        v1 = {
            # Same as the 2.0 default since Q2 moved 2.0 back to 700; kept
            # explicit so v1() stays pinned if the default ever moves again.
            "wave_max": 700.0,
            "rt_backend": "gordon",
            "include_Raman": False,
            "include_Chl_fl": False,
            "include_CDOM_fl": False,
            "fit_Bp": False,
            **cls._NO_CEILINGS,
        }
        return cls(**{**v1, **overrides})

    @classmethod
    def v2_0(cls, **overrides) -> FitConfig:
        """The frozen **2.0** configuration: the 2.0.1 defaults *without* the
        prior ceilings (BING's log-uniform [10⁻⁶, 10⁵] on ``Adg``, ``Aph``,
        ``Bnw``).

        This is what produced the 15,971 2.0 fits in ``$PAB_DATA_DIR/v2/pab.db``
        (``prior_set = 'bing_standard'``). Kept as a named constructor for the
        same reason as :meth:`v1`: the O8 slice test and any 2.0-vs-2.0.1
        comparison must be able to name the old priors exactly.

        Args:
            **overrides: Any field to change; overriding a ceiling defeats it.
        """
        return cls(**{**cls._NO_CEILINGS, **overrides})


def prior_ceilings(config) -> dict[str, float | None]:
    """``{BING parameter name: ceiling in m⁻¹ or None}`` for the three capped
    parameters, read off ``config`` (``{"Bnw": 0.1, "Adg": 10.0, "Aph": 10.0}``
    for the 2.0.1 defaults).

    ``getattr`` with a ``None`` default, so a config object predating the
    ceilings (or a mock) reads as uncapped rather than raising.

    Raises:
        ValueError: if a ceiling is set but is not a positive finite number.
    """
    out: dict[str, float | None] = {}
    for field_name, _token, pname in CEILING_FIELDS:
        value = getattr(config, field_name, None)
        if value is not None:
            value = float(value)
            if not (math.isfinite(value) and value > 0.0):
                raise ValueError(
                    f"FitConfig.{field_name} must be a positive finite ceiling in "
                    f"m^-1 or None, got {value!r}"
                )
        out[pname] = value
    return out


def prior_set_label(config) -> str:
    """The ``fits.prior_set`` stamp for ``config``.

    ``"bing_standard"`` when all three ceilings are ``None`` (BING's priors,
    verbatim — every 1.0 and 2.0 fit), else
    ``"bing_standard+ceiling:bbp600<=0.1,adg<=10,aph<=10"`` listing only the
    ceilings that are set, in :data:`CEILING_FIELDS` order. **The one place**
    the text is built: :func:`build_models` caps the bounds from the same
    :func:`prior_ceilings` dict, so the stamp and the bounds cannot drift, and
    :func:`ceilings_from_prior_set` inverts it exactly.
    """
    ceilings = prior_ceilings(config)
    tokens = [
        f"{token}<={ceilings[pname]:g}"
        for _field, token, pname in CEILING_FIELDS
        if ceilings[pname] is not None
    ]
    if not tokens:
        return PRIOR_SET_STANDARD
    return PRIOR_SET_CEILING_PREFIX + ",".join(tokens)


def ceilings_from_prior_set(label: str | None) -> dict[str, float | None]:
    """Invert :func:`prior_set_label`: ``{FitConfig field: ceiling or None}``.

    ``None``, ``""`` and ``"bing_standard"`` (every stored 1.0/2.0 fit) give
    all-``None``; a ceiling label gives the ceilings it names, ``None`` for the
    rest. This is how :func:`pab.plotting.fit_fig._config_from_row` rebuilds a
    2.0.1 fit's configuration from its row.

    Raises:
        ValueError: for a label this module did not write.
    """
    fields = {field_name: None for field_name, _t, _p in CEILING_FIELDS}
    if not label or label == PRIOR_SET_STANDARD:
        return fields
    if not label.startswith(PRIOR_SET_CEILING_PREFIX):
        raise ValueError(f"unrecognised prior_set {label!r}")
    by_token = {token: field_name for field_name, token, _p in CEILING_FIELDS}
    for item in label[len(PRIOR_SET_CEILING_PREFIX):].split(","):
        token, sep, value = item.partition("<=")
        if not sep or token not in by_token:
            raise ValueError(f"unrecognised ceiling {item!r} in prior_set {label!r}")
        fields[by_token[token]] = float(value)
    return fields


def apply_prior_ceilings(p, models, config):
    """Return ``p`` with its ``apriors``/``bpriors`` capped at ``config``'s
    ceilings — **the PAB-side override** (BING's factory is not modified).

    The factory's prior dicts are copied one by one (``expb_pow`` builds its
    list as ``[dict(...)] * 3``, i.e. three references to *one* dict, so an
    in-place edit of index 0 would move index 2 as well) and only the ``pmax``
    of the capped parameters becomes ``log10(ceiling)``; flavors, ``pmin`` and
    every other prior (``Sdg``, ``beta``) are returned unchanged.
    ``set_standard_priors`` then takes ``p.apriors``/``p.bpriors`` verbatim,
    so the LM bounds (:func:`pab.fit.run._prior_bounds`) and BING's
    ``log_prob`` see the same ceiling.

    Args:
        p: The BING parameter namedtuple from the factory.
        models: ``[anw_model, bbnw_model]`` — their ``pnames`` locate the
            capped parameters, so the indices are never hard-coded.
        config: The :class:`FitConfig`.

    Returns:
        ``p`` itself when no ceiling is set, else ``p._replace(...)``.

    Raises:
        ValueError: if a ceiling is set for a parameter this model pair does
            not have, or lies at/below the prior's floor.
    """
    ceilings = {k: v for k, v in prior_ceilings(config).items() if v is not None}
    if not ceilings:
        return p
    new_lists = []
    for model, priors in zip(models, (p.apriors, p.bpriors), strict=True):
        copied = [dict(d) for d in priors]
        for pname, ceiling in ceilings.items():
            if pname not in model.pnames:
                continue
            k = list(model.pnames).index(pname)
            if not copied[k]["flavor"].startswith("log"):
                raise ValueError(
                    f"{pname} prior is {copied[k]['flavor']!r}, not log-uniform; "
                    "a ceiling in m^-1 does not apply"
                )
            pmax = math.log10(ceiling)
            if pmax <= copied[k]["pmin"]:
                raise ValueError(
                    f"ceiling {ceiling:g} m^-1 for {pname} is at or below the prior "
                    f"floor 10^{copied[k]['pmin']}"
                )
            copied[k]["pmax"] = pmax
        new_lists.append(copied)
    all_names = set(models[0].pnames) | set(models[1].pnames)
    missing = sorted(set(ceilings) - all_names)
    if missing:
        raise ValueError(
            f"ceiling(s) set for {missing} but model pair "
            f"{[m.name for m in models]} has no such parameter"
        )
    return p._replace(apriors=new_lists[0], bpriors=new_lists[1])


def build_models(config: FitConfig, wave, *, geom=None, validate: bool = True):
    """Build the BING ``(p, rt_dict, models)`` for a fit on grid ``wave``.

    Constructs the standard parameter config for ``config.model_pair``, the
    radiative-transfer dict, the two model objects on the data wavelength grid,
    and attaches the standard priors — capped at ``config``'s physical
    ceilings by :func:`apply_prior_ceilings` (2.0.1; a no-op for
    :meth:`FitConfig.v2_0` / :meth:`FitConfig.v1`). Does **not** call
    ``init_other_bits`` (that needs ``Chl``/``Y``/``Rrs`` at fit time — see
    :func:`pab.fit.run`).

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
    # 2.0.1: cap the factory's prior ceilings on the PAB side (a no-op when all
    # three are None); set_standard_priors takes p.apriors/p.bpriors verbatim.
    p = apply_prior_ceilings(p, models, config)
    bing_priors.set_standard_priors(models, p)
    if validate:
        rt_defs.validate_rt_dict(rt_dict, models=models, geom=geom)
    return p, rt_dict, models


def model_param_names(models) -> list[str]:
    """Flat list of free-parameter names across the model pair (anw then bbnw)."""
    return list(models[0].pnames) + list(models[1].pnames)
