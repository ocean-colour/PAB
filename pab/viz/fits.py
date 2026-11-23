"""Fit-level computations for the viz tools (no plotting, no DB writes).

Wraps :func:`pab.plotting.fit_fig.reconstruct_posterior`, which rebuilds a
stored BING fit from its chain NPZ at the fit's own geometry, and adds what a
viewer needs beyond it: the per-band measurement σ, residuals, the non-water
IOP spectra (``a_nw``, ``a_dg``, ``a_ph``, ``b_bp``) with their 5–95 % bands,
and posterior quantities that are not stored (``a_dg(440)``).

:class:`ForwardModel` (the BING-fit editor, ``claude_prompts/viz/viz_bing_fit.md``)
keeps a fit's models built so that one parameter vector can be evaluated in
~0.1 s: model ``Rrs``, the IOP spectra, χ² and the derived quantities, each
computed by the pipeline's own code (:func:`pab.fit.run.reconstruct_rrs`,
:func:`pab.fit.run.extract_quantities`).
"""

from __future__ import annotations

import re
import threading
import warnings
from collections import OrderedDict
from dataclasses import dataclass, field

import bing.evaluate as ev
import bing.fitting.chisq_fit  # noqa: F401 - see below
import bing.models.utils  # noqa: F401
import bing.parameters.standard  # noqa: F401
import bing.priors.priors  # noqa: F401
import bing.rt.defs  # noqa: F401
import bing.rt.geometry  # noqa: F401
import numpy as np
import robust.rt.ed  # noqa: F401
from bing.models import utils as model_utils
from bing.rt import defs as rt_defs
from robust.rt.hybrid import DomainWarning

# Imported here, on the main thread, because reconstruct_posterior imports them
# lazily and two worker threads importing the same module at once deadlock
# (_ModuleLock; seen with argopy on the first pab-viz run).
import pab.fit.models  # noqa: F401
import pab.fit.run  # noqa: F401
from pab.fit import artifacts, run
from pab.fit.models import build_models, model_param_names
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
    #: ``{name: (median, 5 %, 95 %)}`` per band for ``anw``, ``adg``, ``aph``
    #: and ``bbp`` (m⁻¹); a model without a separable ``a_dg`` lacks
    #: ``adg``/``aph``. Empty when not reconstructed.
    iops: dict = field(default_factory=dict)

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
            post = fit_fig.reconstruct_posterior(store, fit_id, iops=True)
        npz = artifacts.load_chains(fit_id)
        adg440 = _posterior_adg440(store, fit_id, npz)
    finally:
        store.close()
    med, lo, hi = post["rrs"]
    curves = FitCurves(
        fit_id=fit_id,
        wave=np.asarray(post["wave"], dtype=float),
        rrs_obs=np.asarray(post["obs"], dtype=float),
        sigma=np.sqrt(np.asarray(npz["varRrs"], dtype=float)),
        rrs_med=np.asarray(med, dtype=float),
        rrs_lo=np.asarray(lo, dtype=float),
        rrs_hi=np.asarray(hi, dtype=float),
        adg440=adg440,
        iops={k: tuple(np.asarray(a, dtype=float).ravel() for a in post[k])
              for k in ("anw", "adg", "aph", "bbp") if post.get(k) is not None},
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


# -- the editor's forward model (BF-Q1 to BF-Q4, BF-Q12, BF-Q14) ---------------
#: One out-of-domain feature in a ``robust`` ``DomainWarning`` message.
_DOMAIN_PART = re.compile(
    r"(?P<feature>\S+) (?P<frac>[\d.]+%) of values outside \[(?P<lo>[^,\]]+), "
    r"(?P<hi>[^\]]+)\], worst (?P<worst>\S+)")


def domain_messages(message: str) -> list[str]:
    """Short ``"B_p: 100.0% outside [0.005, 0.03] (worst 0.004)"`` lines from a
    ``DomainWarning`` text (the whole text when it has an unknown form)."""
    parts = [f"{m['feature']}: {m['frac']} outside [{m['lo']}, {m['hi']}] "
             f"(worst {m['worst']})" for m in _DOMAIN_PART.finditer(message)]
    return parts or [message]


@dataclass(frozen=True)
class ParamSpec:
    """One free parameter, all values in **fit space** (log10 where the prior
    is log-uniform)."""

    name: str
    is_log: bool
    prior_lo: float
    prior_hi: float
    median: float
    lo: float  # posterior percentiles (config.perc, 5 / 95 %)
    hi: float

    def physical(self, value: float) -> float:
        """``value`` out of fit space (``10**value`` for a log parameter)."""
        return float(10.0 ** value) if self.is_log else float(value)

    def in_prior(self, value: float) -> bool:
        return bool(np.isfinite(value) and self.prior_lo <= value <= self.prior_hi)


@dataclass(frozen=True)
class Evaluation:
    """The forward model at one parameter vector."""

    params: np.ndarray
    rrs: np.ndarray
    #: ``{"anw", "bbp"}`` and, for a separable model, ``"adg"``, ``"aph"`` (m⁻¹).
    iops: dict
    #: Reduced χ², exactly as :func:`pab.fit.run._fit_diagnostics` scores a fit.
    chisq: float
    #: Bare quantity names (``bbp700``, ``chl``, ``Adg``, …) → value, from
    #: :func:`pab.fit.run.extract_quantities`, plus ``adg440``.
    quantities: dict
    #: Out-of-domain lines of any ``DomainWarning`` the evaluation raised.
    domain: tuple = ()


class ForwardModel:
    """A stored BING fit with its models built once, to evaluate edited
    parameter vectors (the BING-fit editor).

    The models are rebuilt as :func:`pab.plotting.fit_fig.reconstruct_posterior`
    does (config from the ``fits`` row, geometry from its ``geom_mode``, the
    NPZ ``Chl`` as the ``a_ph`` shape seed, the inelastic ``Ed``), so the
    evaluation at the posterior-median vector reproduces the stored
    ``fits.chisq``. :meth:`evaluate` is serialised by a lock: the models and
    the warning filters are shared by every session of the server.
    """

    def __init__(self, store, fit_id: str):
        row = store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))
        if not row:
            raise ValueError(f"no fit {fit_id!r}")
        row = row[0]
        npz = artifacts.load_chains(fit_id)
        self.fit_id = fit_id
        self.row = dict(row)
        self.config = fit_fig._config_from_row(row)
        self.geom = fit_fig._geometry_from_row(store, row, self.config)
        self.wave = np.asarray(npz["wave"], dtype=float)
        self.rrs_obs = np.asarray(npz["Rrs"], dtype=float)
        self.var = np.asarray(npz["varRrs"], dtype=float)
        self.chl_seed = float(npz["Chl"]) if np.isfinite(npz["Chl"]) else None
        _, self.rt_dict, self.models = build_models(self.config, self.wave, geom=self.geom)
        model_utils.init_other_bits(
            self.models, Chl=None if self.chl_seed is None else np.array([self.chl_seed]),
            Y=None, Rrs=self.rrs_obs)
        run.set_inelastic_Ed(self.models, self.geom, self.rt_dict)
        self.fit_bp = bool(self.rt_dict.get("fit_Bp", False))

        names = model_param_names(self.models)
        is_log = run._is_log_param(self.models)
        low, high = run._prior_bounds(self.models)
        if self.fit_bp:
            names = [*names, "Bp"]
            is_log = [*is_log, False]
            low = np.append(low, rt_defs.BP_PRIOR_PMIN)
            high = np.append(high, rt_defs.BP_PRIOR_PMAX)
        stored = [str(n) for n in npz["param_names"]]
        if stored != names:
            raise ValueError(f"{fit_id}: chain parameters {stored} != model {names}")
        chains = np.asarray(npz["chains"], dtype=float)
        burn = self.config.analysis_burn
        if chains.shape[0] <= burn:
            burn = chains.shape[0] // 2
        flat = ev.thin_burn_chains(chains, burn=burn)
        med = np.median(flat, axis=0)
        plo, phi = np.percentile(flat, list(self.config.perc), axis=0)
        self.specs = [
            ParamSpec(n, bool(lg), float(a), float(b), float(m), float(lo), float(hi))
            for n, lg, a, b, m, lo, hi in zip(names, is_log, low, high, med, plo, phi, strict=True)
        ]
        self._lock = threading.Lock()

    @classmethod
    def from_db(cls, db_path, fit_id: str) -> ForwardModel:
        """Build from ``db_path`` with a store of its own (closed afterwards)."""
        store = data.open_store(db_path)
        try:
            return cls(store, fit_id)
        finally:
            store.close()

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.specs]

    @property
    def start(self) -> np.ndarray:
        """The posterior median per parameter (BF-Q1), in fit space."""
        return np.array([s.median for s in self.specs])

    @property
    def stored_chisq(self) -> float:
        v = self.row.get("chisq")
        return float("nan") if v is None else float(v)

    def settings(self) -> dict:
        """The fixed forward-model settings (shown read-only, BF-Q7)."""
        g = self.geom
        return {
            "rt_backend": self.rt_dict.get("rt_backend", "gordon"),
            "Raman": bool(self.rt_dict.get("include_Raman", False)),
            "Chl-fl": bool(self.rt_dict.get("include_Chl_fl", False)),
            "CDOM-fl": bool(self.rt_dict.get("include_CDOM_fl", False)),
            "phi_c": self.rt_dict.get("phi_C"),
            "geometry": None if g is None else (float(g.theta_s), float(g.theta_v),
                                                float(g.dphi)),
            "geom_mode": self.row.get("geom_mode") or "observed",
            "chl_seed": self.chl_seed,
            "wave": (float(self.wave.min()), float(self.wave.max()), int(self.wave.size)),
        }

    def chisq(self, rrs) -> float:
        """Reduced χ² of ``rrs`` against the observed spectrum (k = all
        parameters, ``B_p`` included), as in :func:`run._fit_diagnostics`."""
        n, k = self.rrs_obs.size, len(self.specs)
        return float(np.sum((np.asarray(rrs) - self.rrs_obs) ** 2 / self.var)
                     / max(n - k, 1))

    def evaluate(self, params) -> Evaluation:
        """Model ``Rrs``, IOPs, χ² and derived quantities at ``params`` (fit space)."""
        p = np.asarray(params, dtype=float).ravel()
        if p.size != len(self.specs):
            raise ValueError(f"expected {len(self.specs)} parameters, got {p.size}")
        na = self.models[0].nparam
        a, bb, bp = run._split_flat(p[None, :], na, self.rt_dict)
        domain: list[str] = []
        with self._lock, warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("ignore")
            warnings.simplefilter("always", DomainWarning)
            bp_val = None if bp is None else float(bp[0])
            rrs = np.asarray(run.reconstruct_rrs(
                self.models, a, bb, self.rt_dict, geom=self.geom, Bp=bp_val),
                dtype=float).ravel()
            if self.rt_dict.get("rt_backend", "gordon") != "gordon":
                # The jitted forward model is silent out of domain by
                # construction (the check skips traced inputs); BING's
                # un-jitted complement lets the DomainWarning fire (BF-Q14).
                ev.robust_domain_check(self.models[0], a, self.models[1], bb,
                                       self.rt_dict, geom=self.geom, Bp=bp_val)
            anw_model = self.models[0]
            iops = {}
            if getattr(anw_model, "has_a_dg", False):
                adg, aph = anw_model.eval_anw(a, retsub_comps=True, wave=self.wave)
                iops["adg"] = np.asarray(adg, dtype=float).ravel()
                iops["aph"] = np.asarray(aph, dtype=float).ravel()
                iops["anw"] = iops["adg"] + iops["aph"]
            else:
                iops["anw"] = np.asarray(anw_model.eval_anw(a, wave=self.wave),
                                         dtype=float).ravel()
            iops["bbp"] = np.asarray(self.models[1].eval_bbnw(bb, wave=self.wave),
                                     dtype=float).ravel()
            # one vector as a 2-step, 1-walker chain: burn 1 leaves it alone
            chain = np.repeat(p[None, None, :], 2, axis=0)
            qs = {q["quantity"]: q["value"] for q in run.extract_quantities(
                self.models, chain, self.rt_dict, config=self.config)}
        for w in caught:
            if issubclass(w.category, DomainWarning):
                domain.extend(domain_messages(str(w.message)))
        if "Adg" in self.names:
            qs["adg440"] = float(adg_at(p[None, :], self.names)[0])
        return Evaluation(params=p, rrs=rrs, iops=iops, chisq=self.chisq(rrs),
                          quantities=qs, domain=tuple(dict.fromkeys(domain)))
