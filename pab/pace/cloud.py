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

    Args:
        source: A path, URL, or file-like object accepted by
            ``xr.open_datatree`` (``h5netcdf`` engine).

    Returns:
        The canonical granule dataset (includes ``FLH``/``nflh`` when present).
    """
    dt = xr.open_datatree(source, engine="h5netcdf", mask_and_scale=True)
    geo = dt["geophysical_data"].ds
    nav = dt["navigation_data"].ds
    sbp = dt["sensor_band_parameters"].ds
    dims = ("x", "y", "wl")
    data_vars = {
        "Rrs": (dims, geo["Rrs"].values),
        "Rrs_unc": (dims, geo["Rrs_unc"].values),
        "l2_flags": (("x", "y"), geo["l2_flags"].values),
    }
    # FLH is carried by the local (ocpy) reader too; include it when present so
    # both backends yield the same canonical dataset.
    if "nflh" in geo:
        data_vars["FLH"] = (("x", "y"), geo["nflh"].values)
    return xr.Dataset(
        data_vars,
        coords={
            "latitude": (("x", "y"), nav["latitude"].values),
            "longitude": (("x", "y"), nav["longitude"].values),
            "wavelength": ("wl", sbp["wavelength_3d"].values),
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
