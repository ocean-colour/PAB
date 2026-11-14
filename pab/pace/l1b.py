"""PACE Level-1B access: per-pixel viewing geometry (and a future Rrs hook).

Two distinct concerns share this module because they share a product.

**Viewing geometry (Stage: the ``geometry`` pipeline stage).** The inelastic
radiative-transfer backend needs the solar/sensor geometry at each fitted
pixel — ``theta_s``, ``theta_v`` and the relative azimuth ``dphi``. The L2 AOP
product does not carry it per pixel (only a coarse per-scan-line ``csol_z``,
which is ~1.8° off, and a nadir assumption for the sensor angle would be ~55°
off), so it is read from the co-temporal **L1B** granule's
``geolocation_data`` group. That grid is **identical** to the L2's
``(scans, pixels)``, verified lat/lon bit-identical at a reference pixel — but
:func:`pixel_geometry` re-checks it per read rather than trusting it, because
silently reading geometry from the wrong pixel is invisible downstream.

**PAB-derived Rrs (future).** The design treats the ``Rrs`` source as a
pluggable upstream stage: the BING fit consumes ``Rrs(λ)`` and its per-band
uncertainty whether they come from the **PACE L2 AOP** product (the default;
:mod:`pab.pace.cloud` / :mod:`pab.pace.extract`) or from a PAB in-house
**L1B → Rrs** algorithm. :func:`rrs_from_l1b` is the placeholder for that
second path and remains unimplemented.

Verified against ``PACE_OCI.20250309T131631`` (2026-09-14): the L1B granule is
1.8 GB, CMR lists each one **twice**, and an open plus a four-value read costs
~7.6 s out-of-region. At pixel ``(868, 142)``: ``theta_s = 29.47°``,
``theta_v = 54.58°``, ``solar_azimuth = −19.75°``, ``sensor_azimuth = 61.58°``
→ ``dphi = 81.33°``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import numpy as np

#: Provenance tag prefix for fits whose Rrs came from a PAB L1B algorithm.
RRS_SOURCE_PREFIX = "PAB_L1B"

#: Provenance tag for the default NASA L2 AOP Rrs source.
RRS_SOURCE_L2 = "L2_AOP"

#: CMR short name of the PACE OCI Level-1B science collection.
L1B_SHORT_NAME = "PACE_OCI_L1B_SCI"

#: netCDF group in an L1B granule holding the per-pixel geolocation + angles.
GEOLOCATION_GROUP = "geolocation_data"

#: Value written to ``matchup_pixels.geom_source`` for geometry from this path.
GEOM_SOURCE = "L1B_V3"

#: Angle variables read out of :data:`GEOLOCATION_GROUP`.
ANGLE_VARS = ("solar_zenith", "sensor_zenith", "solar_azimuth", "sensor_azimuth")

#: Default bound (seconds) on a single L1B open+read. These are 1.8 GB
#: granules read by HTTP byte-range out-of-region; ~7.6 s is typical, so this
#: is a stall guard, not a performance budget.
OPEN_TIMEOUT_S = 300.0

#: ``PACE_OCI.<stamp>.L2.OC_AOP.V3_<n>.nc`` — the AOP granule id/URL shape.
_AOP_RE = re.compile(
    r"(?P<mission>PACE_OCI)\.(?P<stamp>\d{8}T\d{6})\.L2\.OC_AOP\.V(?P<ver>\d+)_\d+\.nc"
)

#: Half-width of the CMR time window centred on the granule stamp. The L1B and
#: L2 share an overpass stamp exactly; a minute is ample and keeps the result
#: set to the handful of granules around it.
_CMR_WINDOW = timedelta(minutes=1)


class GridMismatchError(ValueError):
    """The L1B pixel's lat/lon does not match the stored matchup pixel's.

    Raised by :func:`pixel_geometry` rather than returning approximate angles:
    the L1B and L2 grids are expected to be identical, so a mismatch means the
    assumption has broken (a reprocessing, a different granule) and the
    geometry would be silently attributed to the wrong location.
    """


def granule_stamp(source: str) -> str:
    """Return the ``YYYYmmddTHHMMSS`` overpass stamp from a granule id/URL.

    Raises:
        ValueError: if ``source`` is not a recognisable PACE AOP granule.
    """
    m = _AOP_RE.search(str(source))
    if not m:
        raise ValueError(f"not a PACE L2 AOP granule id/URL: {source!r}")
    return m.group("stamp")


def l1b_name_for_aop(aop_source: str) -> str:
    """Map an AOP granule id/URL to its co-temporal **L1B filename**.

    Pure string swap, no network: ``PACE_OCI.<stamp>.L2.OC_AOP.V3_2.nc`` →
    ``PACE_OCI.<stamp>.L1B.V3.nc``. Note the L1B name keeps only the major
    version (``V3``), dropping the AOP's minor tag (``V3_2``).

    Raises:
        ValueError: if ``aop_source`` is not a recognisable AOP granule.
    """
    m = _AOP_RE.search(str(aop_source))
    if not m:
        raise ValueError(f"not a PACE L2 AOP granule id/URL: {aop_source!r}")
    return f"{m.group('mission')}.{m.group('stamp')}.L1B.V{m.group('ver')}.nc"


def _temporal_window(stamp: str) -> tuple[str, str]:
    """``(start, end)`` ISO strings bracketing ``stamp`` by :data:`_CMR_WINDOW`."""
    t = datetime.strptime(stamp, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return ((t - _CMR_WINDOW).strftime(fmt), (t + _CMR_WINDOW).strftime(fmt))


def _dedupe_by_name(results) -> dict[str, str]:
    """Map ``{granule filename: download URL}`` from CMR results.

    CMR lists each PACE L1B granule **twice** (verified 2026-09-14), so the
    raw result list must be deduplicated. Keying by filename does that and is
    what the caller matches on anyway.
    """
    out: dict[str, str] = {}
    for g in results:
        try:
            urls = g.data_links()
        except Exception:  # noqa: BLE001 — a malformed result must not abort
            continue
        for url in urls:
            name = str(url).rsplit("/", 1)[-1]
            out.setdefault(name, str(url))
    return out


def l1b_source_for_aop(aop_source: str, *, search=None) -> str:
    """Resolve an AOP granule to its co-temporal L1B **download URL**.

    The filename is derived by :func:`l1b_name_for_aop`, but the *URL* cannot
    be — the L1B collection lives under a different DAAC path — so this does a
    CMR lookup by :data:`L1B_SHORT_NAME` over a one-minute window around the
    overpass stamp and picks the entry whose filename matches.

    Args:
        aop_source: An AOP granule id or URL.
        search: Test seam — a callable ``(short_name=..., temporal=...)`` →
            results, defaulting to ``earthaccess.search_data``.

    Returns:
        The L1B granule's download URL.

    Raises:
        ValueError: if ``aop_source`` is not an AOP granule.
        FileNotFoundError: if CMR returns no granule with the expected name.
    """
    want = l1b_name_for_aop(aop_source)
    temporal = _temporal_window(granule_stamp(aop_source))

    if search is None:
        import earthaccess

        from pab.pace.cloud import _ensure_earthaccess_login

        _ensure_earthaccess_login(earthaccess)
        search = earthaccess.search_data

    by_name = _dedupe_by_name(search(short_name=L1B_SHORT_NAME, temporal=temporal))
    if want in by_name:
        return by_name[want]
    raise FileNotFoundError(
        f"no {L1B_SHORT_NAME} granule named {want!r} in CMR for {temporal[0]}"
        f"..{temporal[1]} (found: {sorted(by_name) or 'nothing'})"
    )


def read_geolocation(source):
    """Read an L1B granule's :data:`GEOLOCATION_GROUP` into a lazy dataset.

    Only the geolocation group is opened — the radiance cubes that make these
    granules 1.8 GB are never touched. Dimensions are renamed
    ``(scans, pixels)`` → ``(x, y)`` to match the canonical layout the rest of
    PAB indexes with (:func:`pab.pace.cloud.read_datatree`), so a caller can
    use the ``ix``/``iy`` it already stored.

    Args:
        source: A local path, or an open file-like object / URL that
            ``xarray`` can read with ``h5netcdf``.

    Returns:
        A lazy ``xarray.Dataset`` with ``latitude``/``longitude`` and the
        four :data:`ANGLE_VARS`, dims ``(x, y)``.
    """
    import xarray as xr

    if isinstance(source, str) and source.startswith(("s3://", "https://")):
        import earthaccess

        from pab.pace.cloud import _ensure_earthaccess_login

        _ensure_earthaccess_login(earthaccess)
        source = earthaccess.open([source])[0]

    dt = xr.open_datatree(source, engine="h5netcdf")
    if GEOLOCATION_GROUP not in dt.children:
        dt.close()
        raise KeyError(
            f"L1B granule has no {GEOLOCATION_GROUP!r} group "
            f"(groups: {sorted(dt.children)})"
        )
    ds = dt[GEOLOCATION_GROUP].ds
    renames = {d: n for d, n in (("scans", "x"), ("pixels", "y")) if d in ds.dims}
    return ds.rename(renames) if renames else ds


def open_l1b_geolocation(source, *, timeout_s: float = OPEN_TIMEOUT_S, opener=None):
    """:func:`read_geolocation` bounded by a timeout.

    Shares :func:`pab.matchup.engine._open_with_timeout` (SIGALRM-based, so it
    interrupts a read wedged in a C-level lock — ``fsspec``/``aiohttp`` offer
    no read timeout on this path).

    Args:
        source: Granule URL, path, or file-like object.
        timeout_s: Bound in seconds; ``<= 0`` disables the guard.
        opener: Test seam — ``source`` → geolocation dataset, bypassing the read.

    Returns:
        The lazy geolocation dataset.

    Raises:
        TimeoutError: if the open exceeds ``timeout_s``.
    """
    from pab.matchup.engine import _open_with_timeout

    read = opener if opener is not None else read_geolocation
    return _open_with_timeout(source, timeout_s=timeout_s, open_fn=read)


def wrap_dphi(deg: float) -> float:
    """Wrap a relative azimuth in degrees to the half-open range ``(-180, 180]``.

    ``-180`` maps to ``+180``; ``181`` to ``-179``.
    """
    return 180.0 - ((180.0 - float(deg)) % 360.0)


def _lon_delta(a: float, b: float) -> float:
    """Absolute longitude difference in degrees, across the antimeridian."""
    return abs(wrap_dphi(a - b))


def pixel_geometry(
    ds, ix: int, iy: int, *, lat: float, lon: float, tol_deg: float = 0.01
) -> tuple[float, float, float]:
    """Solar/sensor geometry at pixel ``(ix, iy)``, after checking the grid.

    Args:
        ds: A geolocation dataset from :func:`read_geolocation` (dims ``x``/``y``).
        ix: Along-track (scan) index, as stored on the matchup pixel.
        iy: Cross-track (pixel) index.
        lat: The matchup pixel's recorded latitude (deg) — the grid check.
        lon: Its recorded longitude (deg).
        tol_deg: Maximum accepted separation, per axis, in degrees.

    Returns:
        ``(theta_s, theta_v, dphi)`` in degrees, ``dphi`` wrapped to
        ``(-180, 180]``.

    Raises:
        GridMismatchError: if the L1B pixel's lat/lon differs from ``lat``/
            ``lon`` by more than ``tol_deg`` on either axis. The L1B and L2
            grids are identical in every granule checked, but this must never
            be assumed: reading the right index off the wrong grid yields
            plausible angles for the wrong place.
    """
    at = ds.isel(x=int(ix), y=int(iy))

    got_lat = float(at["latitude"].values)
    got_lon = float(at["longitude"].values)
    dlat = abs(got_lat - float(lat))
    dlon = _lon_delta(got_lon, float(lon))
    if not (dlat <= tol_deg and dlon <= tol_deg):
        raise GridMismatchError(
            f"L1B pixel ({ix}, {iy}) is at ({got_lat:.5f}, {got_lon:.5f}) but the "
            f"matchup pixel is at ({lat:.5f}, {lon:.5f}) — "
            f"dlat={dlat:.5f}°, dlon={dlon:.5f}° > tol {tol_deg}°"
        )

    vals = {name: float(at[name].values) for name in ANGLE_VARS}
    if not all(np.isfinite(v) for v in vals.values()):
        raise ValueError(f"non-finite L1B geometry at pixel ({ix}, {iy}): {vals}")

    dphi = wrap_dphi(vals["sensor_azimuth"] - vals["solar_azimuth"])
    return vals["solar_zenith"], vals["sensor_zenith"], dphi


def rrs_from_l1b(*args, **kwargs):
    """Derive ``Rrs``/``Rrs_unc`` from PACE L1B radiances (not yet implemented).

    Raises:
        NotImplementedError: always — this is a Stage 9 hook. See the module
            docstring for the intended contract.
    """
    raise NotImplementedError(
        "PAB L1B -> Rrs is a future capability (design 'Rrs source' section). "
        "The L2 AOP path (pab.pace.cloud/extract) is the current default."
    )
