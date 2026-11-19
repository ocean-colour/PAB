"""On-demand BGC-Argo profiles for the viz tools (memory-only cache, I-Q8).

A profile is re-fetched **exactly as the ingest stage fetched it** (argopy
``src``/``mode`` from :class:`pab.pipeline.PipelineConfig`, no QC-flag
filter) so that the mixed-layer statistics recomputed here reproduce
``mld_summary``. The drawn mean and MLD still come from the store (AP-Q13);
the recomputation only flags a GDAC reprocessing since ingest.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

import argopy  # noqa: F401 - imported on the main thread, never first in a worker
import numpy as np

from pab.argo import fetch, summary
from pab.pipeline import PipelineConfig

#: Relative difference between the stored and re-fetched ML mean that
#: triggers the visible note (AP-Q13).
REPRODUCE_TOL = 0.02

#: Profiles kept in memory for the server's lifetime.
CACHE_SIZE = 128

#: Variables read from the fetched profile (as :func:`fetch.iter_profiles`,
#: plus the BBP700 QC flags for the hover).
_VARS = ("PRES", "BBP700", "BBP700_QC", "CHLA", "CHLA_ADJUSTED", "CDOM", "PSAL", "TEMP")


@dataclass(frozen=True)
class ArgoProfile:
    """One fetched profile's arrays (aligned on ``PRES``) and metadata."""

    wmo: int
    cycle: int
    latitude: float
    longitude: float
    variables: dict = field(repr=False)

    @property
    def pres(self) -> np.ndarray:
        return self.variables["PRES"]

    @property
    def bbp(self) -> np.ndarray:
        return self.variables.get("BBP700", np.full(self.pres.shape, np.nan))

    @property
    def bbp_qc(self) -> np.ndarray:
        return self.variables.get("BBP700_QC", np.full(self.pres.shape, np.nan))


@dataclass(frozen=True)
class BbpLayers:
    """What the Argo panel draws, all aligned with ``pres``.

    ``despiked`` is the 3-point moving median over the **BBP700 samples
    only** (NaN on the pressure levels without a sample): consecutive samples
    are the neighbours, whatever the empty CTD levels between them.
    ``in_ml`` marks samples at ``pres ≤ mld``; ``kept`` the subset the log-IQR
    filter keeps; ``dropped`` = in ML but rejected. ``mean``/``std``/``n`` are
    over ``kept``.

    ``ingest_*`` are the same statistics the way the ingest stage computed
    them (:func:`summary.mixed_layer_mean`, i.e. what ``mld_summary``
    holds). It runs the median over the full pressure column, so on a profile
    whose BBP700 sits on every 2nd/3rd level each window holds one sample:
    nothing is de-spiked, and each sample is copied into the empty levels
    beside it, which inflates ``n`` and weights the mean (AP-Q16).
    """

    pres: np.ndarray
    raw: np.ndarray
    qc: np.ndarray
    despiked: np.ndarray
    in_ml: np.ndarray
    kept: np.ndarray
    dropped: np.ndarray
    mean: float
    std: float
    n: int
    ingest_mean: float = float("nan")
    ingest_std: float = float("nan")
    ingest_n: int = 0

    @property
    def n_samples_ml(self) -> int:
        """BBP700 samples at ``pres ≤ mld`` (before the IQR filter)."""
        return int(self.in_ml.sum())

    @property
    def ingest_differs(self) -> bool:
        """Whether the ingest recipe gives a different ``n`` or mean (> tol)."""
        if self.ingest_n != self.n:
            return True
        return not reproduces(self.ingest_mean, self.mean)


def despike_samples(pres, bbp) -> np.ndarray:
    """3-point moving median over the finite samples of ``bbp`` only.

    Returns an array aligned with ``bbp``: the de-spiked value at each sample,
    NaN on the levels with no sample.
    """
    pres = np.atleast_1d(np.asarray(pres, dtype=float))
    bbp = np.atleast_1d(np.asarray(bbp, dtype=float))
    out = np.full(bbp.shape, np.nan)
    ok = np.isfinite(bbp) & np.isfinite(pres)
    if ok.any():
        out[ok] = summary.moving_median(bbp[ok])
    return out


def bbp_layers(pres, bbp, mld, qc=None) -> BbpLayers:
    """Split a ``BBP700`` profile at ``mld``: de-spike, IQR filter, ML mean."""
    pres = np.atleast_1d(np.asarray(pres, dtype=float))
    raw = np.atleast_1d(np.asarray(bbp, dtype=float))
    qc = np.full(pres.shape, np.nan) if qc is None else np.asarray(qc, dtype=float)
    if raw.shape != pres.shape:
        raw = np.full(pres.shape, np.nan)
    despiked = despike_samples(pres, raw)
    has_mld = mld is not None and np.isfinite(mld)
    if not has_mld:
        in_ml = np.zeros(pres.shape, dtype=bool)
    else:
        in_ml = np.isfinite(pres) & (pres <= mld) & np.isfinite(despiked)
    kept = in_ml.copy()
    if in_ml.any():
        kept &= summary.iqr_inlier_mask(np.where(in_ml, despiked, np.nan))
    dropped = in_ml & ~kept
    sel = despiked[kept]
    mean = float(np.mean(sel)) if sel.size else float("nan")
    std = float(np.std(sel)) if sel.size else float("nan")
    if has_mld:
        im, isd, inn = summary.mixed_layer_mean(pres, raw, mld, despike_values=True,
                                                iqr_filter=True)
    else:
        im, isd, inn = float("nan"), float("nan"), 0
    return BbpLayers(pres, raw, qc, despiked, in_ml, kept, dropped, mean, std, int(sel.size),
                     im, isd, int(inn))


def recompute_summary(profile: ArgoProfile) -> dict:
    """The ``mld_summary`` fields from a re-fetch, with the ingest arguments."""
    v = profile.variables
    return summary.summarize_profile(
        v["PRES"],
        bbp700=v.get("BBP700"),
        chla=v.get("CHLA"),
        chla_adjusted=v.get("CHLA_ADJUSTED"),
        cdom=v.get("CDOM"),
        psal=v.get("PSAL"),
        temp=v.get("TEMP"),
        lon=profile.longitude,
        lat=profile.latitude,
    )


def reproduces(stored: float | None, recomputed: float, tol: float = REPRODUCE_TOL) -> bool:
    """Whether the re-fetched ML mean matches the stored one within ``tol``."""
    if stored is None or not np.isfinite(stored) or not np.isfinite(recomputed):
        return stored is None or not np.isfinite(stored)
    return abs(recomputed - stored) <= tol * abs(stored)


def _from_dataset(ds) -> ArgoProfile:
    """Reshape an argopy point dataset to the first profile's arrays."""
    prof = ds.argo.point2profile()
    one = prof.isel(N_PROF=0)
    variables = {
        v: np.asarray(one[v].values, dtype=float) for v in _VARS if v in one
    }
    return ArgoProfile(
        wmo=int(one["PLATFORM_NUMBER"].values),
        cycle=int(one["CYCLE_NUMBER"].values),
        latitude=float(one["LATITUDE"].values),
        longitude=float(one["LONGITUDE"].values),
        variables=variables,
    )


@functools.lru_cache(maxsize=CACHE_SIZE)
def fetch_argo_profile(wmo: int, cycle: int) -> ArgoProfile:
    """Fetch profile ``(wmo, cycle)`` over the network (memory-cached).

    Raises whatever argopy raises when the GDAC cannot be reached; the caller
    shows it as a message.
    """
    cfg = PipelineConfig()
    ds = fetch.fetch_profile(int(wmo), int(cycle), src=cfg.argo_src, mode=cfg.argo_mode)
    return _from_dataset(ds)
