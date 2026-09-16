"""BING fit drivers (Stage 5).

The LM warm-start → MCMC pipeline for a single ``Rrs`` spectrum
(:func:`fit_spectrum`), the posterior → namespaced-quantity extraction
(:func:`extract_quantities`), and the matchup wiring that re-reads a Stage-4
pixel's spectrum, fits it, and persists the fit (:func:`fit_matchup`,
:func:`build_fits`).

The array-level helpers (:func:`make_fit_id`, :func:`prepare_spectrum`,
:func:`extract_quantities`) are pure and unit-tested offline; ``bing``/``emcee``
are imported lazily inside the fitting functions (mocked / run at toy size in
tests).
"""

from __future__ import annotations

import contextlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pab.config import pab_version as _pab_version
from pab.fit import artifacts as _artifacts
from pab.fit.models import FitConfig, build_models, model_param_names
from pab.matchup.engine import _close_quietly

_log = logging.getLogger("pab.fit")

#: Per-granule read timeout (seconds) for this stage's opens. A read that never
#: returned wedged `fit` for **8.6 h** on a real run — the open happens in the
#: parent here, so one bad granule stops everything, and neither fsspec nor HDF5
#: imposes a timeout of its own.
OPEN_TIMEOUT_S: float = 120.0


def _open_bounded(source, *, opener=None):
    """:func:`pab.pace.cloud.open_granule` with a hard timeout.

    Shares :func:`pab.matchup.engine._open_with_timeout` (SIGALRM-based, so it
    interrupts a thread parked in a C-level lock).
    """
    from pab.matchup.engine import _open_with_timeout

    return _open_with_timeout(source, opener=opener, timeout_s=OPEN_TIMEOUT_S)


@contextlib.contextmanager
def _quiet():
    """Silence a wrapped call's stdout/stderr.

    BING's ``run_emcee`` hard-codes emcee ``progress=True`` (tqdm bars) and prints
    status lines; across many parallel workers that floods the console. We can't
    pass a flag through ``fit_one``, so redirect both streams to ``os.devnull``
    around the MCMC call. Only *printed* output is dropped — exceptions still
    propagate, so failures remain diagnosable.
    """
    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            yield


#: Reference wavelengths (nm) at which derived IOP scalars are reported. 700 nm
#: is the BGC-Argo ``BBP700`` band — the primary matchup observable.
REF_WAVES: tuple[float, ...] = (440.0, 700.0)

#: Bricaud a*_ph(440) for Chl = 1 mg m^-3. For the Bricaud-family absorption
#: models, BING **retrieves** chlorophyll from the fitted ``Aph`` parameter as
#: ``Chl = 10**Aph / BRICAUD_APH440`` (see ``bing/models/anw.py``); the ``Chl``
#: passed in only **seeds** the a*_ph shape.
BRICAUD_APH440 = 0.05582

#: Absorption-model names whose fitted ``Aph`` maps to Chl via :data:`BRICAUD_APH440`.
_BRICAUD_ANW = ("ExpBricaud", "ExpBricaudFix")


def make_fit_id(
    matchup_id: str, ix: int, iy: int, model_pair: str, version: str | None = None
) -> str:
    """Deterministic, **version-aware** fit id.

    ``"{matchup_id}_{ix}_{iy}_{model_pair}_v{pab_version}"``.

    The version suffix is what lets 1.0 and 2.0 fits of the *same pixel*
    coexist. ``build_fits`` skips a matchup whose ``fit_id`` is already in the
    store, so without it a 2.0 run over a store holding 1.0 fits would skip
    every matchup as "already done" — and ``--replace`` would overwrite the 1.0
    rows rather than adding to them. The 1.0 ids already written stay exactly as
    they are; nothing rewrites them.

    Args:
        matchup_id: The matchup.
        ix, iy: Pixel indices.
        model_pair: e.g. ``"ExpBPow"``.
        version: Overrides :data:`pab.config.pab_version` (tests, and
            reconstructing a historical id).

    Returns:
        The fit id.
    """
    v = _pab_version if version is None else version
    return f"{matchup_id}_{int(ix)}_{int(iy)}_{model_pair}_v{v}"


def chl_from_aph(aph_log10):
    """BING's chlorophyll estimate from the fitted (log10) ``Aph`` parameter.

    ``Chl = 10**Aph / BRICAUD_APH440`` for the Bricaud-family absorption models
    (``bing/models/anw.py``). Returns an array matching ``aph_log10``.
    """
    return 10.0 ** np.asarray(aph_log10, dtype=float) / BRICAUD_APH440


def finite_or_none(value):
    """Return ``float(value)`` if it is a finite number, else ``None``.

    Guards the ``Chl`` path: ``summarize_profile`` yields **NaN** (not ``None``)
    when a profile has no ``CHLA``, and a NaN ``Chl`` would poison BING's
    ``set_aph`` into a NaN fit.
    """
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def prepare_spectrum(wave, Rrs, Rrs_unc=None, *, config: FitConfig | None = None):
    """Restrict a spectrum to the fit window and build the noise variance.

    Keeps finite ``Rrs`` samples within ``[wave_min, wave_max]`` and returns the
    measurement variance ``varRrs``: ``Rrs_unc**2`` where a finite uncertainty is
    supplied, else a ``(2% of Rrs)**2`` floor.

    Args:
        wave: Wavelengths (nm).
        Rrs: Remote-sensing reflectance (sr⁻¹).
        Rrs_unc: Per-band uncertainty (sr⁻¹), or ``None``.
        config: Fit configuration (for the window); defaults to
            :class:`FitConfig`.

    Returns:
        ``(wave, Rrs, varRrs)`` on the windowed grid.

    Raises:
        ValueError: if no finite samples fall within the window.
    """
    config = config or FitConfig()
    wave = np.asarray(wave, dtype=float)
    Rrs = np.asarray(Rrs, dtype=float)
    unc = None if Rrs_unc is None else np.asarray(Rrs_unc, dtype=float)

    keep = np.isfinite(wave) & np.isfinite(Rrs)
    keep &= (wave >= config.wave_min) & (wave <= config.wave_max)
    if not keep.any():
        raise ValueError("no finite Rrs samples within the fit window")

    wave_w, Rrs_w = wave[keep], Rrs[keep]
    if unc is not None and np.isfinite(unc[keep]).all() and np.all(unc[keep] > 0):
        var = unc[keep] ** 2
    else:
        var = (0.02 * np.abs(Rrs_w)) ** 2
    var = np.maximum(var, 1e-12)  # guard against zero variance
    return wave_w, Rrs_w, var


def _initial_guess(models, Rrs):
    """Crude per-model initial guess in fit space (log10 where the prior is log)."""
    p0_a = np.atleast_1d(models[0].init_guess(np.maximum(Rrs * 5.0, 1e-4)))
    p0_b = np.atleast_1d(models[1].init_guess(np.maximum(Rrs * 0.1, 1e-4)))
    p0 = np.concatenate([p0_a, p0_b])
    ii = 0
    for ss in (0, 1):
        for prior in models[ss].priors.priors:
            if prior.flavor.startswith("log"):
                p0[ii] = np.log10(max(p0[ii], 1e-6))
            ii += 1
    return p0


def _prior_bounds(models):
    low, high = [], []
    for prior in models[0].priors.priors + models[1].priors.priors:
        low.append(prior.pmin)
        high.append(prior.pmax)
    return np.array(low, dtype=float), np.array(high, dtype=float)


def _is_log_param(models) -> list[bool]:
    return [
        prior.flavor.startswith("log")
        for ss in (0, 1)
        for prior in models[ss].priors.priors
    ]


def requires_geometry(config: FitConfig) -> bool:
    """Whether ``config``'s RT backend needs per-pixel :class:`ObsGeometry`.

    Every backend except BING's own ``'gordon'`` does. ``theta_s`` is never
    silently defaulted (R3), so a fit without geometry must be refused rather
    than run on an assumed angle.
    """
    return config.rt_backend != "gordon"


def obs_geometry(theta_s, theta_v, dphi):
    """Build a ``bing.rt.geometry.ObsGeometry``, or ``None`` if ``theta_s`` is absent.

    ``theta_v``/``dphi`` fall back to ``ObsGeometry``'s nadir defaults, but
    ``theta_s`` has no default — without it there is no geometry at all.

    ``dphi`` is passed through **unchanged**: the ``geometry`` stage already
    wrapped it to (−180, 180] (:func:`pab.pace.l1b.wrap_dphi`), and wrapping a
    wrapped angle a second time is a silent way to move it.
    """
    from bing.rt.geometry import ObsGeometry

    if theta_s is None or not np.isfinite(float(theta_s)):
        return None
    kwargs = {"theta_s": float(theta_s)}
    if theta_v is not None and np.isfinite(float(theta_v)):
        kwargs["theta_v"] = float(theta_v)
    if dphi is not None and np.isfinite(float(dphi)):
        kwargs["dphi"] = float(dphi)
    return ObsGeometry(**kwargs)


def set_inelastic_Ed(models, geom, rt_dict) -> bool:
    """Attach a downwelling-irradiance spectrum for the inelastic terms.

    BING's Raman and fluorescence kernels need ``Ed(lambda)`` — Raman to form
    the true ``Ed(lambda')/Ed(lambda)`` ratio, chlorophyll fluorescence to
    weight the excitation integral. **PACE L2 carries no Ed**, so PAB supplies
    ``robust``'s packaged Loisel+23 spectrum interpolated at this pixel's
    solar zenith (``run_full_inelastic.md`` Plan §2 item 3). The table spans
    350–750 nm at 5 nm, which covers both the 400–720 nm fit window and the
    Raman excitation grid (~50 nm blueward of the emission edge).

    Two distinct hooks are needed, and BING wires neither automatically
    (``init_other_bits`` does not touch Ed):

    * ``set_raman_Ed(wave_Ed, Ed)`` — the Raman ratio. Without it BING
      silently falls back to a flat ratio of 1, which it measures at ~+60 %
      increment error at 490 nm against the L23 HydroLight pairs. It also
      stashes the raw pair that the **robust** backend reads to build its own
      Ed ratio.
    * ``init_Chl_fluorescence(Ed=...)`` — the excitation integral, with Ed on
      the **model** wavelength grid. Without it ``a_model.Ed_ex`` stays
      ``None`` and the fluorescence kernel raises
      ``IndexError: too many indices for array: array is 0-dimensional``.

    Args:
        models: ``[anw_model, bbnw_model]``.
        geom: ``ObsGeometry`` — ``theta_s`` selects the spectrum.
        rt_dict: The RT config; Ed is only needed by an inelastic process.

    Returns:
        True if an Ed spectrum was attached.
    """
    needs_raman = bool(rt_dict.get("include_Raman", False))
    needs_fl = bool(
        rt_dict.get("include_Chl_fl", False) or rt_dict.get("include_CDOM_fl", False)
    )
    if not (needs_raman or needs_fl) or geom is None:
        return False
    from robust.rt import ed as _robust_ed

    wave_ed, _table = _robust_ed.load_table()
    wave_ed = np.asarray(wave_ed, dtype=float)
    ed_vals = np.asarray(_robust_ed.Ed(float(geom.theta_s), wave_ed), dtype=float)
    if needs_raman:
        models[0].set_raman_Ed(wave_ed, ed_vals)
    if needs_fl:
        model_wave = np.asarray(models[0].wave, dtype=float)
        models[0].init_Chl_fluorescence(Ed=np.interp(model_wave, wave_ed, ed_vals))
    return True


def reconstruct_rrs(models, a_params, bb_params, rt_dict, *, geom=None, Bp=None):
    """Forward-model ``Rrs`` with whichever backend ``rt_dict`` selects.

    **The single place PAB chooses a forward model.** Reconstructing a robust
    fit with the elastic Gordon relation is a silent error — the numbers come
    out plausible, they are simply not the physics that was fitted — so both
    consumers (:func:`_fit_diagnostics` and :mod:`pab.plotting.fit_fig`)
    dispatch here rather than each calling ``bing.evaluate`` directly.

    Args:
        models: ``[anw_model, bbnw_model]``.
        a_params, bb_params: Parameters in the models' own fit space, already
            split by :func:`_split_flat` (any trailing ``B_p`` peeled off).
        rt_dict: The RT configuration; ``rt_backend`` selects the branch.
        geom: ``ObsGeometry`` — required by a robust backend.
        Bp: The ``B_p`` value(s) a robust forward model needs. Ignored by
            Gordon, which has no phase-function input.

    Returns:
        Model ``Rrs``, shape matching the parameter batch.
    """
    import bing.evaluate as ev

    if rt_dict.get("rt_backend", "gordon") == "gordon":
        return ev.calc_Rrs_from_models(
            models[0], a_params, models[1], bb_params, rt_dict
        )
    return ev.calc_Rrs_from_models_robust(
        models[0], a_params, models[1], bb_params, rt_dict, geom=geom, Bp=Bp
    )


def _split_flat(flat, nparam_a: int, rt_dict):
    """Split a posterior sample matrix into ``(a_params, bb_params, Bp)``.

    Under ``rt_dict['fit_Bp']`` the sampled vector is
    ``[a_params..., bb_params..., B_p]`` — the free ``B_p`` is a **trailing**
    column, so it must be peeled off *before* splitting at ``nparam_a``.
    Without the peel it would be handed to the bb-model as an extra parameter.

    Returns:
        ``(a_params, bb_params, Bp)`` where ``Bp`` is the trailing column or
        ``None`` when ``B_p`` is held fixed.
    """
    if rt_dict is not None and rt_dict.get("fit_Bp", False):
        return flat[:, :nparam_a], flat[:, nparam_a:-1], flat[:, -1]
    return flat[:, :nparam_a], flat[:, nparam_a:], None


@dataclass
class FitSpectrumResult:
    """In-memory result of :func:`fit_spectrum` (before persistence)."""

    chains: np.ndarray  # (nsteps, nwalkers, nparam)
    wave: np.ndarray
    Rrs: np.ndarray
    varRrs: np.ndarray
    param_names: list[str]
    quantities: list[dict[str, Any]]  # namespaced scalars (sans prefix)
    anw_model: str
    bbnw_model: str
    nwalkers: int
    chisq: float  # reduced chi-squared at the posterior-median parameters
    aic: float
    bic: float
    accept_frac: float
    success: bool  # whether the LM warm-start converged (MCMC always runs)
    Chl: float = field(default=float("nan"))


def extract_quantities(models, chains, rt_dict, *, config: FitConfig):
    """Posterior → list of namespaced-quantity dicts (median + credible band).

    Reports the free model parameters (linearised out of log space) plus derived
    IOP scalars at :data:`REF_WAVES`: ``bbp`` (non-water backscatter — the
    matchup observable), ``anw`` (non-water absorption), and ``adg`` when the
    absorption model exposes it.

    Returns:
        List of ``{"quantity", "value", "value_lo", "value_hi", "unit"}`` dicts
        (``quantity`` is the bare name; the ``BING_<model_pair>_`` prefix is
        applied at persistence).
    """
    import bing.evaluate as ev

    lo_p, hi_p = config.perc
    burn = config.analysis_burn
    if chains.shape[0] <= burn:
        burn = chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)  # (nsamples, nparam)

    names = model_param_names(models)
    is_log = _is_log_param(models)
    nparam_a = models[0].nparam
    fit_bp = bool(rt_dict is not None and rt_dict.get("fit_Bp", False))

    out: list[dict[str, Any]] = []

    def _add(quantity, samples, unit):
        med = float(np.median(samples))
        plo, phi = (float(x) for x in np.percentile(samples, [lo_p, hi_p]))
        out.append(
            {
                "quantity": quantity,
                "value": med,
                "value_lo": plo,
                "value_hi": phi,
                "unit": unit,
            }
        )

    # free model parameters (linearised where the prior was log10). `names`
    # covers the model parameters only, so this loop stops before the trailing
    # B_p column even when the chain carries one.
    for k, name in enumerate(names):
        samples = 10.0 ** flat[:, k] if is_log[k] else flat[:, k]
        _add(name, samples, "")

    # B_p is a trailing column, sampled linearly over [0.004, 0.05]; it is not
    # a model parameter, so it is reported separately and kept out of the split.
    a_params, bb_params, bp = _split_flat(flat, nparam_a, rt_dict)
    if fit_bp:
        _add("Bp", bp, "")

    # derived IOP scalars at the reference wavelengths
    wave = np.asarray(models[1].wave, dtype=float)
    bbnw = models[1].eval_bbnw(bb_params, wave=wave)  # (nsamples, nwave) m^-1
    anw = models[0].eval_anw(a_params)  # (nsamples, nwave) m^-1
    adg = models[0].eval_adg(a_params) if hasattr(models[0], "eval_adg") else None
    for w in REF_WAVES:
        j = int(np.argmin(np.abs(wave - w)))
        _add(f"bbp{int(round(w))}", bbnw[:, j], "m^-1")
        _add(f"anw{int(round(w))}", anw[:, j], "m^-1")
        if adg is not None:
            _add(f"adg{int(round(w))}", adg[:, j], "m^-1")

    # BING's retrieved chlorophyll from the fitted Aph (Bricaud-family anw).
    # Chl is *seeded* into the fit but recovered here from the posterior Aph.
    if models[0].name in _BRICAUD_ANW and "Aph" in names:
        _add("chl", chl_from_aph(flat[:, names.index("Aph")]), "mg m^-3")
    return out


def fit_spectrum(
    wave,
    Rrs,
    Rrs_unc=None,
    *,
    Chl: float | None = None,
    Y: float | None = None,
    geom=None,
    config: FitConfig | None = None,
) -> FitSpectrumResult:
    """Fit one ``Rrs`` spectrum: band prep → LM warm-start → MCMC → posterior.

    Args:
        wave: Wavelengths (nm).
        Rrs: Remote-sensing reflectance (sr⁻¹).
        Rrs_unc: Per-band uncertainty (sr⁻¹); a 2% floor is used when absent.
        Chl: Chlorophyll (mg m⁻³) that **seeds** the Bricaud ``a_ph`` shape
            (defaults to 0.1 when the absorption model needs a seed and none is
            supplied). It is not a fixed input — the fit retrieves Chl from the
            posterior ``Aph`` (reported as the ``chl`` quantity; see
            :func:`chl_from_aph`).
        Y: Backscattering slope for models that need it (unused by ``Pow``).
        geom: ``bing.rt.geometry.ObsGeometry`` for this pixel. **Required by
            every backend except ``'gordon'``** — ``build_models`` raises if a
            robust backend gets none, rather than assuming a solar angle (R3).
        config: Fit configuration; defaults to :class:`FitConfig`.

    Returns:
        A :class:`FitSpectrumResult`. Under ``config.fit_Bp`` the chains carry
        one extra trailing column (``B_p``) and ``param_names`` ends in
        ``"Bp"``.

    Raises:
        ValueError: if the RT configuration is illegal for this spectrum — in
            particular a robust backend with ``geom=None``.
    """
    config = config or FitConfig()
    from bing.fitting import chisq_fit
    from bing.fitting import inference as bing_inf
    from bing.models import utils as model_utils

    wave_w, Rrs_w, varRrs_w = prepare_spectrum(wave, Rrs, Rrs_unc, config=config)
    p, rt_dict, models = build_models(config, wave_w, geom=geom)
    fit_bp = bool(rt_dict.get("fit_Bp", False))

    chl_val = Chl if Chl is not None else (0.1 if models[0].uses_Chl else None)
    chl_arr = None if chl_val is None else np.array([chl_val], dtype=float)
    y_arr = None if Y is None else np.array([Y], dtype=float)
    model_utils.init_other_bits(models, Chl=chl_arr, Y=y_arr, Rrs=Rrs_w)
    set_inelastic_Ed(models, geom, rt_dict)

    # initial guess + Levenberg-Marquardt warm-start (fall back to the guess)
    low, high = _prior_bounds(models)
    p0 = np.clip(_initial_guess(models, Rrs_w), low, high)
    if fit_bp:
        # B_p is appended as a trailing, **linear-space** dimension over
        # [BP_PRIOR_PMIN, BP_PRIOR_PMAX]; BING's log_prob applies that prior
        # itself, but the LM warm-start needs the bound explicitly.
        from bing.rt import defs as _rt_defs

        p0 = np.append(p0, float(config.Bp_value))
        low = np.append(low, _rt_defs.BP_PRIOR_PMIN)
        high = np.append(high, _rt_defs.BP_PRIOR_PMAX)
        p0 = np.clip(p0, low, high)
    try:
        p_best, _cov, _ = chisq_fit.fit(
            (Rrs_w, varRrs_w, p0, 0, geom), models, rt_dict, bounds=(low, high)
        )
        success = True
    except (RuntimeError, ValueError):
        p_best, success = p0, False

    # MCMC refinement (keep the sampler for the acceptance fraction).
    # rt_dict must reach init_mcmc: it is what makes ndim (and the walker
    # count) account for the extra trailing B_p dimension.
    pdict = bing_inf.init_mcmc(
        models, nsteps=config.nsteps, nburn=config.nburn, rt_dict=rt_dict
    )
    pdict["Chl"] = np.array([chl_val if chl_val is not None else 0.0])
    pdict["Y"] = np.array([Y if Y is not None else 0.0])
    with _quiet():  # suppress BING's tqdm bars + status prints (see _quiet)
        sampler, _ = bing_inf.fit_one(
            (Rrs_w, varRrs_w, p_best, 0, geom),
            models=models,
            pdict=pdict,
            chains_only=False,
            rt_dict=rt_dict,
        )
    chains = np.asarray(sampler.get_chain(), dtype=float)
    accept_frac = float(np.mean(sampler.acceptance_fraction))

    quantities = extract_quantities(models, chains, rt_dict, config=config)
    chisq, aic, bic = _fit_diagnostics(
        models, chains, rt_dict, Rrs_w, varRrs_w, config, geom=geom
    )
    names = model_param_names(models)
    if fit_bp:
        names = [*names, "Bp"]

    return FitSpectrumResult(
        chains=chains,
        wave=wave_w,
        Rrs=Rrs_w,
        varRrs=varRrs_w,
        param_names=names,
        quantities=quantities,
        anw_model=models[0].name,
        bbnw_model=models[1].name,
        nwalkers=int(pdict["nwalkers"]),
        chisq=chisq,
        aic=aic,
        bic=bic,
        accept_frac=accept_frac,
        success=success,
        Chl=float(chl_val) if chl_val is not None else float("nan"),
    )


def _fit_diagnostics(models, chains, rt_dict, Rrs, varRrs, config, *, geom=None):
    """Reduced chi-squared, AIC, BIC at the posterior-median parameters.

    The reconstruction goes through :func:`reconstruct_rrs`, so a robust fit is
    scored against the physics it was actually fitted with — χ²/AIC/BIC from a
    Gordon reconstruction of a robust fit would be a quiet apples-to-oranges
    comparison. The median ``B_p`` is peeled and forwarded, and the parameter
    count ``k`` counts it.
    """
    import bing.evaluate as ev

    burn = config.analysis_burn
    if chains.shape[0] <= burn:
        burn = chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)
    med = np.median(flat, axis=0)
    nparam_a = models[0].nparam
    a_med, bb_med, bp_med = _split_flat(med[None, :], nparam_a, rt_dict)
    pred = np.squeeze(
        reconstruct_rrs(
            models,
            a_med[0],
            bb_med[0],
            rt_dict,
            geom=geom,
            Bp=None if bp_med is None else float(bp_med[0]),
        )
    )
    resid2 = np.sum((pred - Rrs) ** 2 / varRrs)
    n, k = Rrs.size, med.size
    dof = max(n - k, 1)
    chisq = float(resid2 / dof)
    aic = float(resid2 + 2 * k)
    bic = float(resid2 + k * np.log(n))
    return chisq, aic, bic


# -- matchup wiring ---------------------------------------------------------
def _gather_fit_input(store, matchup_id: str, config: FitConfig, rank: int = 1):
    """DB-only inputs for one matchup's fit (no granule I/O, no compute).

    Returns a dict ``{fit_id, matchup_id, pixel_id, source, ix, iy, chl,
    theta_s, theta_v, dphi}`` or ``None`` if the matchup has no pixel at
    ``rank`` (nothing to fit).

    The three angles come straight off ``matchup_pixels`` (schema v5, degrees,
    filled by the ``geometry`` stage) and are ``None`` on a pixel that stage
    has not reached. They are **not** re-wrapped: ``dphi`` is already in
    (−180, 180].
    """
    px = store.query(
        "SELECT * FROM matchup_pixels WHERE matchup_id = ? AND rank = ?",
        (matchup_id, rank),
    )
    if not px:
        return None
    px = px[0]
    m = store.query(
        "SELECT profile_id, granule_id FROM matchups WHERE matchup_id = ?",
        (matchup_id,),
    )
    if not m:
        return None
    m = m[0]
    gran = store.query(
        "SELECT data_url FROM granules WHERE granule_id = ?", (m["granule_id"],)
    )
    source = gran[0]["data_url"] if gran and gran[0]["data_url"] else m["granule_id"]
    chla = store.query(
        "SELECT chla FROM mld_summary WHERE profile_id = ?", (m["profile_id"],)
    )
    # require a *finite* chla (NaN would poison set_aph -> a NaN fit)
    chl = finite_or_none(chla[0]["chla"]) if chla else None
    return {
        "fit_id": make_fit_id(matchup_id, px["ix"], px["iy"], config.model_pair),
        "matchup_id": matchup_id,
        "pixel_id": px["pixel_id"],
        "source": source,
        "ix": int(px["ix"]),
        "iy": int(px["iy"]),
        "chl": chl,
        "theta_s": finite_or_none(px["theta_s"]),
        "theta_v": finite_or_none(px["theta_v"]),
        "dphi": finite_or_none(px["dphi"]),
    }


#: Why a matchup was refused before any granule was opened.
NO_GEOMETRY = (
    "no viewing geometry on the matchup pixel (matchup_pixels.theta_s is NULL) "
    "— run the `geometry` stage first; {backend} must not assume a solar angle"
)


def _geometry_or_none(inp):
    """``ObsGeometry`` for a gathered input, or ``None`` if it has no angles."""
    return obs_geometry(inp["theta_s"], inp["theta_v"], inp["dphi"])


def _fit_only(wave, Rrs, Rrs_unc, chl, config: FitConfig, geom=None):
    """Pure per-spectrum compute (no DB, no I/O) — the unit dispatched to workers.

    Module-level and picklable so it can run in a :class:`ProcessPoolExecutor`;
    ``ObsGeometry`` is a plain dataclass, so it pickles to the worker too.
    """
    return fit_spectrum(wave, Rrs, Rrs_unc, Chl=chl, geom=geom, config=config)


def _persist_result(store, inp: dict, result: FitSpectrumResult, config, created):
    """Write the chains NPZ + ``fits``/``fit_results`` for one completed fit."""
    path = _artifacts.save_chains(inp["fit_id"], result)
    _artifacts.persist_fit(
        store,
        fit_id=inp["fit_id"],
        matchup_id=inp["matchup_id"],
        pixel_id=inp["pixel_id"],
        result=result,
        config=config,
        rrs_source="L2_AOP",
        chains_path=str(path),
        created=created,
    )
    return inp["fit_id"]


def _worker_init():  # pragma: no cover - runs in worker processes
    """Cap a fit worker's thread pools — :func:`pab.parallel.init_worker`.

    This used to be a second, independent copy of the BLAS caps. It was not: it
    silently diverged the moment ``XLA_FLAGS`` was added to the shared helper,
    leaving the **fit** stage — the one pool that actually runs JAX — as the
    only one without the XLA cap. Delegating keeps one implementation.
    """
    from pab.parallel import init_worker

    init_worker()


def fit_matchup(
    store,
    matchup_id: str,
    *,
    config: FitConfig | None = None,
    opener=None,
    rank: int = 1,
    persist: bool = True,
    created: str | None = None,
):
    """Fit one matchup's pixel (default the nearest) and persist the fit.

    Re-reads the pixel ``Rrs`` from the granule (spectra are not stored in
    ``matchup_pixels``), **seeds** the Bricaud ``a_ph`` with the float's
    mixed-layer ``chla`` (the fit then retrieves Chl from ``Aph``), runs
    :func:`fit_spectrum`, writes the chains NPZ, and upserts the ``fits`` +
    ``fit_results`` rows.

    Args:
        store: An open :class:`pab.db.store.Store`.
        matchup_id: The matchup to fit.
        config: Fit configuration.
        opener: Optional granule opener (test seam; mocks the cloud).
        rank: Which pixel to fit (1 = nearest valid).
        persist: If False, fit only and return the result without writing.
        created: Timestamp to stamp on the written rows.

    Returns:
        The ``fit_id`` (when ``persist``) else the :class:`FitSpectrumResult`.

    Raises:
        ValueError: if the matchup, pixel, or granule URL is missing, or if the
            configured RT backend needs per-pixel geometry and the pixel has
            none (R3 — the granule is not even opened in that case).
    """
    from pab.pace import extract as _extract

    config = config or FitConfig()
    if not store.query("SELECT 1 FROM matchups WHERE matchup_id = ?", (matchup_id,)):
        raise ValueError(f"no matchup {matchup_id!r}")
    inp = _gather_fit_input(store, matchup_id, config, rank=rank)
    if inp is None:
        raise ValueError(f"matchup {matchup_id!r} has no pixel with rank {rank}")

    geom = _geometry_or_none(inp)
    if geom is None and requires_geometry(config):
        raise ValueError(
            f"{matchup_id!r}: " + NO_GEOMETRY.format(backend=config.rt_backend)
        )

    ds = _open_bounded(inp["source"], opener=opener)
    wave, rrs, unc = _extract.extract_spectrum(ds, inp["ix"], inp["iy"])
    result = _fit_only(wave, rrs, unc, inp["chl"], config, geom=geom)
    if not persist:
        return result
    return _persist_result(store, inp, result, config, created)


def build_fits(
    store,
    *,
    config: FitConfig | None = None,
    opener=None,
    replace: bool = False,
    created: str | None = None,
    jobs: int = 1,
) -> dict[str, list[str]]:
    """Fit the nearest pixel of every matchup and persist (idempotent, resumable).

    Skips a fit already present (by ``fit_id``) unless ``replace=True``. A single
    matchup that fails (granule unavailable, fit diverges) is recorded under
    ``"failed"`` and does **not** abort the batch, so a re-run resumes the rest.

    A matchup whose pixel has **no viewing geometry** is recorded under
    ``"failed"`` too, and is rejected *before* its granule is opened — the
    robust backends must not fit an assumed solar angle (R3). Running the
    ``geometry`` stage and re-running ``fit`` picks those up.

    ``jobs > 1`` fits matchups **in parallel across processes** (the heavy MCMC is
    CPU-bound): granules are opened and pixels extracted in the parent (one open
    per granule; the ``opener`` needn't be picklable), the pure per-spectrum fit
    (:func:`_fit_only`) runs in a :class:`ProcessPoolExecutor`, and all DB writes
    happen back in the parent (so there is no SQLite writer contention). Results
    are persisted as they complete, keeping the run resumable and memory bounded.

    Returns:
        ``{"written": [...], "skipped": [...], "failed": [...]}`` of fit ids.
    """
    config = config or FitConfig()
    written: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    # Existing fit_ids in one query rather than one per matchup (SQLite on CephFS
    # costs ~200 ms a round trip, so per-record checks dominate a resume).
    done_fits: set[str] = set()
    if not replace:
        done_fits = {r["fit_id"] for r in store.query("SELECT fit_id FROM fits")}

    need_geom = requires_geometry(config)
    inputs: list[dict] = []
    for m in store.query("SELECT matchup_id FROM matchups ORDER BY matchup_id"):
        inp = _gather_fit_input(store, m["matchup_id"], config)
        if inp is None:
            continue
        if inp["fit_id"] in done_fits:
            skipped.append(inp["fit_id"])
            continue
        # R3: a pixel with no geometry is refused **here**, before any granule
        # is opened — never fitted on an assumed solar angle.
        if need_geom and inp["theta_s"] is None:
            _log.warning(
                "fit skipped for %s: %s",
                inp["fit_id"],
                NO_GEOMETRY.format(backend=config.rt_backend),
            )
            failed.append(inp["fit_id"])
            continue
        inputs.append(inp)

    if jobs and jobs > 1 and inputs:
        _build_fits_parallel(
            store, inputs, config, opener, created, int(jobs), written, failed
        )
        return {"written": written, "skipped": skipped, "failed": failed}

    from pab.pace import extract as _extract

    for inp in inputs:
        try:
            ds = _open_bounded(inp["source"], opener=opener)
            try:
                wave, rrs, unc = _extract.extract_spectrum(ds, inp["ix"], inp["iy"])
            finally:
                _close_quietly(ds)
            result = _fit_only(
                wave, rrs, unc, inp["chl"], config, geom=_geometry_or_none(inp)
            )
            _persist_result(store, inp, result, config, created)
            written.append(inp["fit_id"])
        except Exception:  # noqa: BLE001 — one bad matchup must not abort the batch
            _log.exception("fit failed for %s", inp["fit_id"])
            failed.append(inp["fit_id"])
    return {"written": written, "skipped": skipped, "failed": failed}


def _build_fits_parallel(store, inputs, config, opener, created, jobs, written, failed):
    """Parallel fit backend (see :func:`build_fits`). Mutates ``written``/``failed``.

    Extraction + persistence stay in the parent; only :func:`_fit_only` is farmed
    out. In-flight futures are bounded (~2×``jobs``) so completed chains are drained
    and persisted promptly rather than piling up in memory.
    """
    import multiprocessing as mp
    from collections import defaultdict
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    from pab.pace import extract as _extract

    # 'spawn' avoids fork-in-a-multithreaded-parent deadlocks (Py3.13 warns on
    # fork here); workers re-import cleanly and `_fit_only` pickles by qualname.
    ctx = mp.get_context("spawn")

    by_source: dict[str, list[dict]] = defaultdict(list)
    for inp in inputs:
        by_source[inp["source"]].append(inp)

    fut_inp: dict = {}
    pending: set = set()

    def _collect(fut):
        inp = fut_inp.pop(fut)
        try:
            _persist_result(store, inp, fut.result(), config, created)
            written.append(inp["fit_id"])
        except Exception:  # noqa: BLE001
            _log.exception("fit failed for %s (worker/persist)", inp["fit_id"])
            failed.append(inp["fit_id"])

    with ProcessPoolExecutor(
        max_workers=jobs, mp_context=ctx, initializer=_worker_init
    ) as ex:
        for source, group in by_source.items():
            try:
                ds = _open_bounded(source, opener=opener)
            except Exception:  # noqa: BLE001 — a bad granule fails its whole group
                _log.exception(
                    "open_granule failed for %s (%d fits)", source, len(group)
                )
                failed.extend(inp["fit_id"] for inp in group)
                continue
            # One open per source shared across its group, then released: an
            # unclosed dataset keeps an fsspec handle plus its read-ahead cache,
            # which is what OOM-killed a 32-worker match pod inside 8 min.
            try:
                spectra = {}
                for inp in group:
                    try:
                        spectra[inp["fit_id"]] = _extract.extract_spectrum(
                            ds, inp["ix"], inp["iy"]
                        )
                    except Exception:  # noqa: BLE001
                        _log.exception("extract_spectrum failed for %s", inp["fit_id"])
                        failed.append(inp["fit_id"])
            finally:
                _close_quietly(ds)
            for inp in group:
                if inp["fit_id"] not in spectra:
                    continue
                wave, rrs, unc = spectra[inp["fit_id"]]
                fut = ex.submit(
                    _fit_only,
                    wave,
                    rrs,
                    unc,
                    inp["chl"],
                    config,
                    _geometry_or_none(inp),
                )
                fut_inp[fut] = inp
                pending.add(fut)
                while len(pending) >= 2 * jobs:
                    done, pending_ = wait(pending, return_when=FIRST_COMPLETED)
                    pending -= done
                    for f in done:
                        _collect(f)
        for f in list(pending):
            _collect(f)
