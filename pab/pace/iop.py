"""NASA PACE L2 IOP (GIOP) access & nearest-pixel extraction.

The NASA-baseline comparison PAB compares BING against (design *Comparison &
metrics*, "BING vs. NASA L2 IOP"). NASA/OB.DAAC distributes exactly **one**
operational PACE L2 IOP suite — ``PACE_OCI_L2_IOP``, produced with the
**GIOP** algorithm (default configuration) — there is no PACE GSM product
(confirmed via a live CMR sweep; see ``claude_prompts/pace_giop_gsm.md`` for
the full research record and decision log).

This module locates the IOP granule co-temporal with an already-matched AOP
granule (same overpass, adjacent filename tag), reads it
(``ocpy.pace.io.load_iop_l2``), and extracts NASA's scalar-at-442 nm IOP
quantities at the pixel already used for the BING fit — matched by **lat/lon,
not by array index**, since the two products' pixel grids are not assumed to
align 1:1 pixel-for-pixel.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: NASA's PACE OCI L2 IOP product short name — the only IOP suite NASA
#: distributes for PACE (GIOP-based; no GSM product exists).
IOP_SHORT_NAME = "PACE_OCI_L2_IOP"

#: Reference wavelength (nm) NASA's scalar L2 IOP fields (``bbp_442``,
#: ``adg_442``, ...) are reported at.
IOP_REF_WAVE = 442.0

#: Filename tags swapped to map an AOP granule id/URL to its co-temporal IOP
#: granule — both suites share a filename for the same overpass except this
#: tag (e.g. ``PACE_OCI.20260309T153836.L2.OC_AOP.V3_2.nc`` ->
#: ``PACE_OCI.20260309T153836.L2.OC_IOP.V3_2.nc``). Verified against a live
#: CMR lookup for a real granule (see the 2026-09-08 Task 3 log entry in
#: ``claude_prompts/pace_giop_gsm.md``).
_AOP_TAG = "L2.OC_AOP."
_IOP_TAG = "L2.OC_IOP."


def iop_source_for_aop(aop_source: str) -> str:
    """Map an AOP granule id/URL to its co-temporal IOP granule id/URL.

    Args:
        aop_source: An AOP granule id or download URL (contains ``L2.OC_AOP.``).

    Returns:
        The corresponding IOP granule id/URL.

    Raises:
        ValueError: if ``aop_source`` does not look like an AOP granule.
    """
    s = str(aop_source)
    if _AOP_TAG not in s:
        raise ValueError(f"not an AOP granule id/URL: {aop_source!r}")
    return s.replace(_AOP_TAG, _IOP_TAG)


def open_iop_local(fn: str):
    """Open a local PACE L2 IOP granule file (dev/debug path, like
    :func:`pab.pace.cloud.open_local` for the AOP product).

    ``ocpy.pace.io.load_iop_l2`` already returns an ``xarray.Dataset`` (dims
    ``x, y, wl``: ``a``, ``bb``, ``aph``, plus scalar ``adg_442``/``adg_s``/
    ``bbp_442``/``bbp_unc_442``/``bbp_s``) with ``latitude``/``longitude``/
    ``wavelength`` coords, so this just attaches ``l2_flags`` the same way
    :func:`pab.pace.cloud.to_granule_ds` does for the AOP reader.
    """
    from ocpy.pace import io as _io

    from pab.pace.cloud import to_granule_ds

    ds, l2_flags = _io.load_iop_l2(fn)
    return to_granule_ds(ds, l2_flags)


def nearest_pixel(ds, target_lat: float, target_lon: float) -> tuple[int, int, float]:
    """Nearest pixel (by great-circle distance, **no** flag filtering).

    Unlike :func:`pab.pace.extract.nearest_valid_pixels`, this does not screen
    by ``l2_flags`` — the goal is the *exact* physical location already
    selected for the BING fit (via the AOP granule's own nearest-pixel
    search), not an independently-chosen "nearest good" pixel on the IOP
    grid, which could silently land on a different pixel than BING used.

    Args:
        ds: A dataset with 2-D ``latitude``/``longitude`` (e.g. from
            :func:`open_iop_local`).
        target_lat: Target latitude (deg) — the matchup pixel's recorded
            latitude.
        target_lon: Target longitude (deg).

    Returns:
        ``(ix, iy, distance_km)`` of the nearest pixel.
    """
    from pab.pace.extract import haversine_km

    lats = np.asarray(ds["latitude"].values, dtype=float)
    lons = np.asarray(ds["longitude"].values, dtype=float)
    dist = haversine_km(lats, lons, target_lat, target_lon)
    ix, iy = np.unravel_index(int(np.nanargmin(dist)), dist.shape)
    return int(ix), int(iy), float(dist[ix, iy])


def nearest_wavelength_index(wave, target: float = IOP_REF_WAVE) -> int:
    """Index of the ``wave`` entry nearest ``target`` nm."""
    return int(np.argmin(np.abs(np.asarray(wave, dtype=float) - target)))


def extract_iop_quantities(ds, ix: int, iy: int) -> list[dict[str, Any]]:
    """NASA's IOP quantities at pixel ``(ix, iy)`` (bare quantity names).

    Returns a list of ``{"quantity", "value", "value_lo", "value_hi", "unit"}``
    dicts in the same shape :func:`pab.fit.run.extract_quantities` returns for
    BING, so both feed the same ``fit_results`` persistence path.

    ``bbp_442`` carries a **symmetric** credible interval derived from NASA's
    own ``bbp_unc_442`` (a single uncertainty number, unlike BING's asymmetric
    posterior percentiles). ``adg_442``/``aph_442`` have no per-pixel
    uncertainty in the fields ``ocpy.pace.io.load_iop_l2`` currently exposes —
    NASA's file also carries ``aph_unc_442``/``adg_unc_442``, which the
    ``ocpy`` loader does not read (a known gap, not fixed here) — so their
    ``value_lo``/``value_hi`` are ``None``.
    """

    def _val(name: str) -> float | None:
        v = float(ds[name].isel(x=ix, y=iy).values)
        return v if np.isfinite(v) else None

    bbp = _val("bbp_442")
    bbp_unc = _val("bbp_unc_442")

    out: list[dict[str, Any]] = []

    def _add(quantity: str, value, unc, unit: str) -> None:
        lo = None if (value is None or unc is None) else value - unc
        hi = None if (value is None or unc is None) else value + unc
        out.append(
            {
                "quantity": quantity,
                "value": value,
                "value_lo": lo,
                "value_hi": hi,
                "unit": unit,
            }
        )

    _add("bbp_442", bbp, bbp_unc, "m^-1")
    _add("bbp_unc_442", bbp_unc, None, "m^-1")
    _add("bbp_s", _val("bbp_s"), None, "")
    _add("adg_442", _val("adg_442"), None, "m^-1")
    _add("adg_s", _val("adg_s"), None, "nm^-1")

    wave = np.asarray(ds["wavelength"].values, dtype=float)
    widx = nearest_wavelength_index(wave)
    aph_val = float(ds["aph"].isel(x=ix, y=iy, wl=widx).values)
    _add("aph_442", aph_val if np.isfinite(aph_val) else None, None, "m^-1")

    return out
