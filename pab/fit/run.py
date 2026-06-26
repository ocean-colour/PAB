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

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pab.fit import artifacts as _artifacts
from pab.fit.models import FitConfig, build_models, model_param_names

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


def make_fit_id(matchup_id: str, ix: int, iy: int, model_pair: str) -> str:
    """Deterministic fit id: ``"{matchup_id}_{ix}_{iy}_{model_pair}"``."""
    return f"{matchup_id}_{int(ix)}_{int(iy)}_{model_pair}"


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

    # free parameters (linearised where the prior was log10)
    for k, name in enumerate(names):
        samples = 10.0 ** flat[:, k] if is_log[k] else flat[:, k]
        _add(name, samples, "")

    # derived IOP scalars at the reference wavelengths
    a_params, bb_params = flat[:, :nparam_a], flat[:, nparam_a:]
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
        config: Fit configuration; defaults to :class:`FitConfig`.

    Returns:
        A :class:`FitSpectrumResult`.
    """
    config = config or FitConfig()
    from bing.fitting import chisq_fit
    from bing.fitting import inference as bing_inf
    from bing.models import utils as model_utils

    wave_w, Rrs_w, varRrs_w = prepare_spectrum(wave, Rrs, Rrs_unc, config=config)
    p, rt_dict, models = build_models(config, wave_w)

    chl_val = Chl if Chl is not None else (0.1 if models[0].uses_Chl else None)
    chl_arr = None if chl_val is None else np.array([chl_val], dtype=float)
    y_arr = None if Y is None else np.array([Y], dtype=float)
    model_utils.init_other_bits(models, Chl=chl_arr, Y=y_arr, Rrs=Rrs_w)

    # initial guess + Levenberg-Marquardt warm-start (fall back to the guess)
    low, high = _prior_bounds(models)
    p0 = np.clip(_initial_guess(models, Rrs_w), low, high)
    try:
        p_best, _cov, _ = chisq_fit.fit(
            (Rrs_w, varRrs_w, p0, 0), models, rt_dict, bounds=(low, high)
        )
        success = True
    except (RuntimeError, ValueError):
        p_best, success = p0, False

    # MCMC refinement (keep the sampler for the acceptance fraction)
    pdict = bing_inf.init_mcmc(models, nsteps=config.nsteps, nburn=config.nburn)
    pdict["Chl"] = np.array([chl_val if chl_val is not None else 0.0])
    pdict["Y"] = np.array([Y if Y is not None else 0.0])
    sampler, _ = bing_inf.fit_one(
        (Rrs_w, varRrs_w, p_best, 0),
        models=models,
        pdict=pdict,
        chains_only=False,
        rt_dict=rt_dict,
    )
    chains = np.asarray(sampler.get_chain(), dtype=float)
    accept_frac = float(np.mean(sampler.acceptance_fraction))

    quantities = extract_quantities(models, chains, rt_dict, config=config)
    chisq, aic, bic = _fit_diagnostics(models, chains, rt_dict, Rrs_w, varRrs_w, config)

    return FitSpectrumResult(
        chains=chains,
        wave=wave_w,
        Rrs=Rrs_w,
        varRrs=varRrs_w,
        param_names=model_param_names(models),
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


def _fit_diagnostics(models, chains, rt_dict, Rrs, varRrs, config):
    """Reduced chi-squared, AIC, BIC at the posterior-median parameters."""
    import bing.evaluate as ev

    burn = config.analysis_burn
    if chains.shape[0] <= burn:
        burn = chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)
    med = np.median(flat, axis=0)
    nparam_a = models[0].nparam
    pred = np.squeeze(
        ev.calc_Rrs_from_models(
            models[0], med[:nparam_a], models[1], med[nparam_a:], rt_dict
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
        ValueError: if the matchup, pixel, or granule URL is missing.
    """
    from pab.pace import cloud
    from pab.pace import extract as _extract

    config = config or FitConfig()
    m = store.query("SELECT * FROM matchups WHERE matchup_id = ?", (matchup_id,))
    if not m:
        raise ValueError(f"no matchup {matchup_id!r}")
    m = m[0]
    px = store.query(
        "SELECT * FROM matchup_pixels WHERE matchup_id = ? AND rank = ?",
        (matchup_id, rank),
    )
    if not px:
        raise ValueError(f"matchup {matchup_id!r} has no pixel with rank {rank}")
    px = px[0]
    gran = store.query(
        "SELECT data_url FROM granules WHERE granule_id = ?", (m["granule_id"],)
    )
    source = gran[0]["data_url"] if gran and gran[0]["data_url"] else m["granule_id"]
    chla = store.query(
        "SELECT chla FROM mld_summary WHERE profile_id = ?", (m["profile_id"],)
    )
    # require a *finite* chla (NaN would poison set_aph -> a NaN fit)
    chl = finite_or_none(chla[0]["chla"]) if chla else None

    ds = cloud.open_granule(source, opener=opener)
    wave, rrs, unc = _extract.extract_spectrum(ds, int(px["ix"]), int(px["iy"]))
    result = fit_spectrum(wave, rrs, unc, Chl=chl, config=config)
    if not persist:
        return result

    fit_id = make_fit_id(matchup_id, px["ix"], px["iy"], config.model_pair)
    path = _artifacts.save_chains(fit_id, result)
    _artifacts.persist_fit(
        store,
        fit_id=fit_id,
        matchup_id=matchup_id,
        pixel_id=px["pixel_id"],
        result=result,
        config=config,
        rrs_source="L2_AOP",
        chains_path=str(path),
        created=created,
    )
    return fit_id


def build_fits(
    store,
    *,
    config: FitConfig | None = None,
    opener=None,
    replace: bool = False,
    created: str | None = None,
) -> dict[str, list[str]]:
    """Fit the nearest pixel of every matchup and persist (idempotent).

    Skips a fit already present (by ``fit_id``) unless ``replace=True``. A
    single matchup that fails to fit (e.g. its granule cannot be opened, or the
    fit diverges) is recorded under ``"failed"`` and does **not** abort the
    batch — so a re-run resumes the rest.

    Returns:
        ``{"written": [...], "skipped": [...], "failed": [...]}`` of fit ids.
    """
    config = config or FitConfig()
    written: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []
    for m in store.query("SELECT matchup_id FROM matchups ORDER BY matchup_id"):
        mid = m["matchup_id"]
        px = store.query(
            "SELECT ix, iy FROM matchup_pixels WHERE matchup_id = ? AND rank = 1",
            (mid,),
        )
        if not px:
            continue
        fit_id = make_fit_id(mid, px[0]["ix"], px[0]["iy"], config.model_pair)
        if (
            store.query("SELECT 1 FROM fits WHERE fit_id = ?", (fit_id,))
            and not replace
        ):
            skipped.append(fit_id)
            continue
        try:
            fit_matchup(store, mid, config=config, opener=opener, created=created)
            written.append(fit_id)
        except Exception:  # noqa: BLE001 — one bad matchup must not abort the batch
            failed.append(fit_id)
    return {"written": written, "skipped": skipped, "failed": failed}
