"""Fit-level computations for the viz tools (no plotting, no DB writes).

Wraps :func:`pab.plotting.fit_fig.reconstruct_fit`, which rebuilds a stored
BING fit from its chain NPZ at the fit's own geometry, and adds what a viewer
needs beyond it: the per-band measurement σ, residuals, and posterior
quantities that are not stored (``a_dg(440)``).
"""

from __future__ import annotations

import threading
import warnings
from collections import OrderedDict
from dataclasses import dataclass

import bing.evaluate as ev
import bing.fitting.chisq_fit  # noqa: F401 - see below
import bing.models.utils  # noqa: F401
import bing.parameters.standard  # noqa: F401
import bing.priors.priors  # noqa: F401
import bing.rt.defs  # noqa: F401
import bing.rt.geometry  # noqa: F401
import numpy as np
import robust.rt.ed  # noqa: F401

# Imported here, on the main thread, because reconstruct_fit imports them
# lazily and two worker threads importing the same module at once deadlock
# (_ModuleLock; seen with argopy on the first pab-viz run).
import pab.fit.models  # noqa: F401
import pab.fit.run  # noqa: F401
from pab.fit import artifacts
from pab.plotting import fit_fig
from pab.viz import data

#: Reconstructions kept in memory (each is a few kB; the cost is the 1–8 s).
CACHE_SIZE = 64

#: Wavelength at which the CDOM + detritus absorption is quoted (nm).
ADG_REF_WAVE = 440.0


@dataclass(frozen=True)
class FitCurves:
    """A reconstructed fit on its own wavelength grid (all arrays per band)."""

    fit_id: str
    wave: np.ndarray
    rrs_obs: np.ndarray
    sigma: np.ndarray
    rrs_med: np.ndarray
    rrs_lo: np.ndarray
    rrs_hi: np.ndarray
    adg440: tuple[float, float, float]

    @property
    def resid(self) -> np.ndarray:
        """``Rrs_obs − Rrs_model`` (sr⁻¹)."""
        return self.rrs_obs - self.rrs_med

    @property
    def resid_sigma(self) -> np.ndarray:
        """Residual in units of the measurement σ."""
        return self.resid / self.sigma

    @property
    def resid_pct(self) -> np.ndarray:
        """Residual relative to the model, in %."""
        return 100.0 * self.resid / self.rrs_med


_cache: OrderedDict[str, FitCurves] = OrderedDict()
_lock = threading.Lock()


def adg_at(flat: np.ndarray, names, wave: float = ADG_REF_WAVE, pivot: float = 400.0):
    """``a_dg(wave)`` per posterior sample from the ``ExpBricaud`` ``Adg``/``Sdg``.

    The chains carry ``log10(Adg)`` (amplitude at ``pivot`` = 400 nm) and a
    linear ``Sdg``; ``a_dg(λ) = Adg·exp(−Sdg(λ − 400))``.
    """
    names = [str(n) for n in names]
    adg = 10.0 ** flat[:, names.index("Adg")]
    sdg = flat[:, names.index("Sdg")]
    return adg * np.exp(-sdg * (wave - pivot))


def _posterior_adg440(store, fit_id: str, npz) -> tuple[float, float, float]:
    """Median and stored-CI percentiles of ``a_dg(440)`` from the chains."""
    row = store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))[0]
    config = fit_fig._config_from_row(row)
    chains = np.asarray(npz["chains"], dtype=float)
    burn = config.analysis_burn if chains.shape[0] > config.analysis_burn else chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)
    if "Adg" not in [str(n) for n in npz["param_names"]]:
        return (np.nan, np.nan, np.nan)
    samples = adg_at(flat, npz["param_names"])
    lo, med, hi = np.percentile(samples, [config.perc[0], 50.0, config.perc[1]])
    return (float(med), float(lo), float(hi))


def reconstruct(db_path, fit_id: str) -> FitCurves:
    """Rebuild ``fit_id`` (cached). Opens its **own** read-only store, so it is
    safe to call from a worker thread. Raises ``FileNotFoundError`` when the
    chain NPZ is absent."""
    with _lock:
        if fit_id in _cache:
            _cache.move_to_end(fit_id)
            return _cache[fit_id]
    if not data.has_chains(fit_id):
        raise FileNotFoundError(f"no chains for {fit_id} under {data.chains_file(fit_id).parent}")
    store = data.open_store(db_path)
    try:
        with warnings.catch_warnings():
            # robust's DomainWarning fires on the B_p breach for most fits.
            warnings.simplefilter("ignore")
            wave, obs, med, lo, hi, *_ = fit_fig.reconstruct_fit(store, fit_id)
        npz = artifacts.load_chains(fit_id)
        adg440 = _posterior_adg440(store, fit_id, npz)
    finally:
        store.close()
    curves = FitCurves(
        fit_id=fit_id,
        wave=np.asarray(wave, dtype=float),
        rrs_obs=np.asarray(obs, dtype=float),
        sigma=np.sqrt(np.asarray(npz["varRrs"], dtype=float)),
        rrs_med=np.asarray(med, dtype=float),
        rrs_lo=np.asarray(lo, dtype=float),
        rrs_hi=np.asarray(hi, dtype=float),
        adg440=adg440,
    )
    with _lock:
        _cache[fit_id] = curves
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return curves


def observed_spectrum(fit_id: str):
    """``(wave, Rrs, σ)`` straight from the chain NPZ, or ``None`` without it.

    Lets the panel show the data while the model is still reconstructing.
    """
    if not data.has_chains(fit_id):
        return None
    npz = artifacts.load_chains(fit_id)
    return (
        np.asarray(npz["wave"], dtype=float),
        np.asarray(npz["Rrs"], dtype=float),
        np.sqrt(np.asarray(npz["varRrs"], dtype=float)),
    )
