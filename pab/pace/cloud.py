"""Cloud-first granule access behind a swappable backend.

PAB reads PACE granules from the **NASA Earthdata Cloud** (in-region AWS
``us-west-2``) without bulk-downloading, falling back to local files for
dev/debug. Both paths produce the same **canonical granule dataset** so the
nearest-pixel extraction (:mod:`pab.pace.extract`) is source-agnostic:

* dims ``(x, y, wl)``: ``Rrs``, ``Rrs_unc`` (+ ``FLH`` when present);
* 2-D coords ``latitude``/``longitude`` (``x, y``); ``wavelength`` (``wl``);
* a ``l2_flags`` data variable (``x, y``).

The design keeps two cloud read mechanisms open — (a) lazy ``xarray`` over S3
and (b) OPeNDAP server-side subsetting — selected here by ``backend``; (a) is
the default as it reuses the existing ``ocpy`` reader unchanged. The heavy
imports (``ocpy``, ``earthaccess``) are lazy, and the cloud read is mocked in
tests (no network/S3 in the suite).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
import xarray as xr


def to_granule_ds(ds: xr.Dataset, l2_flags) -> xr.Dataset:
    """Attach ``l2_flags`` to an ``ocpy`` L2 dataset → the canonical dataset.

    Args:
        ds: An ``ocpy.pace.io.load_oci_l2``-style dataset (dims ``x, y, wl``).
        l2_flags: The 2-D ``l2_flags`` array (``ocpy`` returns it separately).

    Returns:
        The same dataset with an integer ``l2_flags`` (``x, y``) variable.
    """
    out = ds.copy()
    out["l2_flags"] = (("x", "y"), np.asarray(l2_flags))
    return out


def open_local(fn: str) -> xr.Dataset:
    """Open a local PACE L2 AOP granule file via ``ocpy`` (dev/debug path)."""
    from ocpy.pace import io as _io

    ds, flags = _io.load_oci_l2(fn)
    return to_granule_ds(ds, flags)


def granule_cache_path(source: str, cache_dir: str | Path) -> Path:
    """Local cache path for a granule ``source`` (URL or path) under ``cache_dir``.

    Uses the granule file's basename so the same granule maps to a stable file
    regardless of run — PACE L2 basenames are unique
    (e.g. ``PACE_OCI.20250124T215746.L2.OC_AOP.V3_1.nc``).
    """
    name = Path(urlparse(str(source)).path).name or Path(str(source)).name
    return Path(cache_dir) / name


def download_granule(
    source: str, cache_dir: str | Path, *, replace: bool = False
) -> Path:
    """Download a granule to ``cache_dir`` and return its local path (idempotent).

    Uses ``earthaccess.download`` (a robust streaming HTTP download with the
    operator's Earthdata Login), which — unlike lazy ``fsspec`` byte-range reads —
    does **not** stall out-of-region. A granule already in the cache is reused
    unless ``replace``. This is the *pre-download* path for off-cloud dev runs;
    in-region S3 access (:func:`open_s3`) needs no local copy.

    Args:
        source: The granule URL (or local path, returned unchanged if it exists).
        cache_dir: Directory to hold the downloaded granule(s).
        replace: Re-download even if the cached file already exists.

    Returns:
        The local :class:`~pathlib.Path` of the granule file.
    """
    if not str(source).startswith(("http://", "https://", "s3://")):
        return Path(source)  # already a local path
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = granule_cache_path(source, cache_dir)
    if target.exists() and not replace:
        return target

    import earthaccess

    paths = earthaccess.download([str(source)], local_path=str(cache_dir))
    got = Path(paths[0])
    # earthaccess names the file by its basename, which is our cache path; guard
    # against a divergent name by trusting whatever it actually wrote.
    return got if got.exists() else target


def cached_opener(
    cache_dir: str | Path, *, download: bool = True
) -> Callable[[str], xr.Dataset]:
    """An ``opener`` that reads granules from a **local cache** (pre-download path).

    Returns a ``source -> canonical dataset`` callable suitable for
    :func:`pab.matchup.engine.build_matchups` / the pipeline ``opener`` seam. For
    a URL source it ensures the granule is in ``cache_dir`` (downloading on first
    use when ``download``) and then opens it with the reliable local reader
    (:func:`open_local`); a local-path source is opened directly. This is what
    makes the ``match`` stage dependable off-cloud — no out-of-region byte-range
    stalls (Q&A *Task 2*).

    Args:
        cache_dir: Directory holding (or to hold) the downloaded granules.
        download: If False, a missing cached granule raises instead of being
            fetched (use when the cache is expected to be pre-populated).
    """
    cache_dir = Path(cache_dir)

    def _open(source: str) -> xr.Dataset:
        if not str(source).startswith(("http://", "https://", "s3://")):
            return open_local(str(source))
        target = granule_cache_path(source, cache_dir)
        if not target.exists():
            if not download:
                raise FileNotFoundError(
                    f"granule not in cache and download=False: {target}"
                )
            target = download_granule(source, cache_dir)
        return open_local(str(target))

    return _open


def open_s3(url: str) -> xr.Dataset:
    """Open a PACE L2 AOP granule lazily from S3 (in-region ``us-west-2``).

    Uses ``earthaccess`` for temporary DAAC credentials + a file-like S3 object,
    then reads the netCDF group hierarchy into the canonical layout. Only the
    requested bytes transfer in-region, so a nearest-pixel read does not pull the
    full cube. Requires running in ``us-west-2`` with an Earthdata Login
    configured.
    """
    import earthaccess

    fileset = earthaccess.open([url])
    return read_datatree(fileset[0])


def read_datatree(source) -> xr.Dataset:
    """Read a PACE L2 granule's group hierarchy into the canonical dataset.

    Reads the whole group tree in a **single open** (``xr.open_datatree``) — the
    pattern in ``docs/context.md`` — rather than opening the source once per
    group, which is fragile for an already-opened S3/fsspec file handle.

    The ``Rrs``/``Rrs_unc`` cubes are kept **lazy**: the canonical dataset wraps
    the on-disk variables (renamed to ``(x, y, wl)``) without materialising them,
    so a nearest-pixel ``isel(...).values`` in :mod:`pab.pace.extract` fetches
    only the few HDF5 chunks covering that pixel rather than the full ~GB cube.
    This is what makes the cloud read affordable out-of-region (HTTP byte-range)
    and realises the "only the requested bytes transfer" design. The 2-D
    navigation / flag arrays are small and read whole by the nearest-pixel search.

    Args:
        source: A path, URL, or file-like object accepted by
            ``xr.open_datatree`` (``h5netcdf`` engine).

    Returns:
        The canonical granule dataset (includes ``FLH``/``nflh`` when present).
    """
    dt = xr.open_datatree(
        source, engine="h5netcdf", mask_and_scale=True, decode_timedelta=False
    )
    geo = dt["geophysical_data"].ds
    nav = dt["navigation_data"].ds
    sbp = dt["sensor_band_parameters"].ds

    def _canon(da, target_dims):
        """Lazy ``Variable`` with dims renamed to ``target_dims`` positionally.

        Renaming by position (not by source name) mirrors the original eager
        ``(dims, values)`` construction and is robust to PACE groups using
        different source dim names for the same axis (e.g. the spectral dim is
        ``wavelength_3d`` in ``geophysical_data`` but ``wavelength`` in
        ``sensor_band_parameters`` on some granules). ``.variable`` keeps the
        on-disk data lazy.
        """
        return da.rename(dict(zip(da.dims, target_dims))).variable

    data_vars = {
        "Rrs": _canon(geo["Rrs"], ("x", "y", "wl")),
        "Rrs_unc": _canon(geo["Rrs_unc"], ("x", "y", "wl")),
        "l2_flags": _canon(geo["l2_flags"], ("x", "y")),
    }
    # FLH is carried by the local (ocpy) reader too; include it when present so
    # both backends yield the same canonical dataset.
    if "nflh" in geo:
        data_vars["FLH"] = _canon(geo["nflh"], ("x", "y"))
    return xr.Dataset(
        data_vars,
        coords={
            "latitude": _canon(nav["latitude"], ("x", "y")),
            "longitude": _canon(nav["longitude"], ("x", "y")),
            "wavelength": _canon(sbp["wavelength_3d"], ("wl",)),
        },
    )


def open_granule(
    source: str,
    *,
    backend: str = "auto",
    opener: Callable[[str], xr.Dataset] | None = None,
) -> xr.Dataset:
    """Open a granule into the canonical dataset, dispatching on backend.

    Args:
        source: An S3 URL / Earthdata granule URL, or a local file path.
        backend: ``"s3"`` (lazy S3), ``"local"`` (file), or ``"auto"`` (decide
            from ``source``). ``"opendap"`` is reserved for the future
            server-side-subsetting backend.
        opener: Optional override taking ``source`` → canonical dataset.
            Primarily a test seam (inject a synthetic granule; mock the cloud).

    Returns:
        The canonical granule dataset.
    """
    if opener is not None:
        return opener(source)
    if backend == "auto":
        backend = "s3" if str(source).startswith(("s3://", "https://")) else "local"
    if backend == "s3":
        return open_s3(source)
    if backend == "local":
        return open_local(source)
    if backend == "opendap":
        raise NotImplementedError(
            "OPeNDAP backend is a documented future option (design Cloud access)."
        )
    raise ValueError(f"Unknown backend {backend!r}")
