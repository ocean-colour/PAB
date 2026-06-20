"""Mixed-layer depth (MLD) via the de Boyer Montégut density-threshold method.

PAB follows the Bisson et al. (2019) recipe (``docs/context.md`` §3): the MLD is
the depth at which potential density ``SIG0`` first exceeds its near-surface
(10 m) value by 0.03 kg m\\ :sup:`-3` (de Boyer Montégut & Madec 2004).

The core :func:`mixed_layer_depth` works on plain arrays (pressure + potential
density) so it is unit-testable offline with a synthetic profile. The
convenience :func:`density_sigma0` / :func:`mixed_layer_depth_from_ts` derive
``SIG0`` from salinity/temperature with ``gsw`` (TEOS-10), mirroring argopy's
``ds.argo.teos10([..., 'SIG0'])`` — the path the design specifies.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

#: Method tag recorded in the ``mld_summary.mld_method`` column.
MLD_METHOD = "deBoyerMontegut_0.03"

#: Default reference depth (m / dbar) for the surface density.
REF_DEPTH = 10.0

#: Default density threshold (kg m^-3).
THRESHOLD = 0.03


def mixed_layer_depth(
    pres: ArrayLike,
    sig0: ArrayLike,
    *,
    ref_depth: float = REF_DEPTH,
    threshold: float = THRESHOLD,
) -> float:
    """Compute the MLD from pressure and potential density.

    The MLD is the shallowest depth (below the reference depth) where the
    potential density exceeds the reference-depth density by ``threshold``.

    Args:
        pres: Pressure / depth (dbar ≈ m), any order; NaNs allowed.
        sig0: Potential density anomaly ``SIG0`` (kg m\\ :sup:`-3`), aligned
            with ``pres``.
        ref_depth: Reference depth for the surface density (default 10 m).
        threshold: Density increase defining the MLD (default 0.03 kg m⁻³).

    Returns:
        The MLD in the same units as ``pres``, or ``nan`` if the profile does
        not reach the reference depth or never crosses the threshold.
    """
    pres = np.asarray(pres, dtype=float)
    sig0 = np.asarray(sig0, dtype=float)
    good = np.isfinite(pres) & np.isfinite(sig0)
    pres, sig0 = pres[good], sig0[good]
    if pres.size == 0:
        return float("nan")

    # Sort shallow -> deep.
    order = np.argsort(pres)
    pres, sig0 = pres[order], sig0[order]

    # Need data spanning the reference depth (a sample at or below it).
    if pres.min() > ref_depth or not np.any(pres >= ref_depth):
        return float("nan")

    i_ref = int(np.argmin(np.abs(pres - ref_depth)))
    ref_density = sig0[i_ref]

    below = np.arange(i_ref, pres.size)
    exceed = below[sig0[below] > ref_density + threshold]
    if exceed.size == 0:
        return float("nan")
    return float(pres[exceed[0]])


def density_sigma0(
    pres: ArrayLike,
    psal: ArrayLike,
    temp: ArrayLike,
    lon: float,
    lat: float,
) -> np.ndarray:
    """Potential density anomaly ``SIG0`` (kg m⁻³) from in-situ T/S via TEOS-10.

    Uses ``gsw``: practical salinity → absolute salinity → conservative
    temperature → ``sigma0``. This is the same computation argopy performs in
    ``ds.argo.teos10(['SIG0'])``.

    Args:
        pres: Pressure (dbar).
        psal: Practical salinity (PSU).
        temp: In-situ temperature (°C).
        lon: Profile longitude (deg).
        lat: Profile latitude (deg).

    Returns:
        ``SIG0`` aligned with the inputs.
    """
    import gsw

    pres = np.asarray(pres, dtype=float)
    psal = np.asarray(psal, dtype=float)
    temp = np.asarray(temp, dtype=float)
    sa = gsw.SA_from_SP(psal, pres, lon, lat)
    ct = gsw.CT_from_t(sa, temp, pres)
    return gsw.sigma0(sa, ct)


def mixed_layer_depth_from_ts(
    pres: ArrayLike,
    psal: ArrayLike,
    temp: ArrayLike,
    lon: float,
    lat: float,
    *,
    ref_depth: float = REF_DEPTH,
    threshold: float = THRESHOLD,
) -> float:
    """MLD from in-situ T/S: derive ``SIG0`` then apply :func:`mixed_layer_depth`."""
    sig0 = density_sigma0(pres, psal, temp, lon, lat)
    return mixed_layer_depth(pres, sig0, ref_depth=ref_depth, threshold=threshold)
