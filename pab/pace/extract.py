"""Nearest-unflagged-pixel ``Rrs`` spectrum extraction from a PACE granule.

Operates on the canonical in-memory granule dataset produced by
:mod:`pab.pace.cloud` (dims ``(x, y, wl)``: ``Rrs``, ``Rrs_unc``; 2-D
``latitude``/``longitude``; ``l2_flags``; ``wavelength``). The nearest-pixel
logic is identical whether the data came from the cloud (lazy S3) or a local
file — only the source differs (design *Loading* / *Cloud access*).

The functions here are NumPy/xarray-only so they unit-test offline against a
small synthetic granule; no network is involved.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from pab.pace import flags as _flags

#: Mean Earth radius (km) for the haversine distance.
EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lat1: ArrayLike, lon1: ArrayLike, lat2: float, lon2: float
) -> np.ndarray:
    """Great-circle distance (km) from each ``(lat1, lon1)`` to ``(lat2, lon2)``."""
    lat1 = np.radians(np.asarray(lat1, dtype=float))
    lon1 = np.radians(np.asarray(lon1, dtype=float))
    lat2r = np.radians(lat2)
    lon2r = np.radians(lon2)
    dlat = lat1 - lat2r
    dlon = lon1 - lon2r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def nearest_valid_pixels(
    ds,
    target_lat: float,
    target_lon: float,
    *,
    n: int = 10,
    mask_flags=_flags.STANDARD_OCEAN_MASK,
) -> list[dict[str, Any]]:
    """Return the ``n`` nearest **unflagged** pixels to a target location.

    Args:
        ds: A canonical granule dataset (see module docstring).
        target_lat: Target latitude (deg).
        target_lon: Target longitude (deg).
        n: Maximum number of pixels to return.
        mask_flags: ``l2_flags`` names that reject a pixel.

    Returns:
        Up to ``n`` dicts (nearest first), each with ``ix``, ``iy``,
        ``latitude``, ``longitude``, ``distance_km``, ``rank`` (1 = nearest),
        and ``flag`` (the raw ``l2_flags`` value).
    """
    lats = np.asarray(ds["latitude"].values, dtype=float)
    lons = np.asarray(ds["longitude"].values, dtype=float)
    l2 = np.asarray(ds["l2_flags"].values)
    dist = haversine_km(lats, lons, target_lat, target_lon)

    good = _flags.good_mask(l2, mask_flags) & np.isfinite(dist)
    ix_g, iy_g = np.where(good)
    if ix_g.size == 0:
        return []
    order = np.argsort(dist[ix_g, iy_g])[:n]
    out: list[dict[str, Any]] = []
    for rank, k in enumerate(order, start=1):
        ix, iy = int(ix_g[k]), int(iy_g[k])
        out.append(
            {
                "ix": ix,
                "iy": iy,
                "latitude": float(lats[ix, iy]),
                "longitude": float(lons[ix, iy]),
                "distance_km": float(dist[ix, iy]),
                "rank": rank,
                "flag": int(l2[ix, iy]),
            }
        )
    return out


def extract_spectrum(ds, ix: int, iy: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return ``(wavelength, Rrs, Rrs_unc)`` at pixel ``(ix, iy)``."""
    wave = np.asarray(ds["wavelength"].values, dtype=float)
    rrs = np.asarray(ds["Rrs"].isel(x=ix, y=iy).values, dtype=float)
    unc = np.asarray(ds["Rrs_unc"].isel(x=ix, y=iy).values, dtype=float)
    return wave, rrs, unc


def extract_matchup_spectra(
    ds,
    target_lat: float,
    target_lon: float,
    *,
    n: int = 10,
    mask_flags=_flags.STANDARD_OCEAN_MASK,
) -> list[dict[str, Any]]:
    """Nearest ``n`` unflagged pixels with their spectra attached.

    Combines :func:`nearest_valid_pixels` and :func:`extract_spectrum`; each
    returned dict adds ``wavelength``, ``Rrs``, and ``Rrs_unc`` arrays to the
    pixel record. This is the per-granule input the matchup engine (Stage 4)
    pairs with a float's mixed-layer summary.
    """
    pixels = nearest_valid_pixels(
        ds, target_lat, target_lon, n=n, mask_flags=mask_flags
    )
    for px in pixels:
        wave, rrs, unc = extract_spectrum(ds, px["ix"], px["iy"])
        px["wavelength"] = wave
        px["Rrs"] = rrs
        px["Rrs_unc"] = unc
    return pixels


def pace_noise_vector(wave: ArrayLike, *, include_sampling: bool = False) -> np.ndarray:
    """PACE measurement-noise vector for fitting (wraps ``ocpy``).

    Delegates to ``ocpy.satellites.pace.gen_noise_vector(wave)`` — the
    per-band noise the BING fit uses when an ``Rrs_unc`` is not supplied.
    ``ocpy`` is imported lazily.

    Args:
        wave: Wavelengths (nm).
        include_sampling: Passed through to ``gen_noise_vector``.

    Returns:
        The noise vector aligned with ``wave``.
    """
    from ocpy.satellites import pace as _ocpy_pace

    return _ocpy_pace.gen_noise_vector(
        np.asarray(wave, dtype=float), include_sampling=include_sampling
    )
