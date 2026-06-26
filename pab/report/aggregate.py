"""Aggregation for the reporting layer (Stage 7).

Flat region/season/magnitude bins and an equal-area **HEALPix** spatial binning
of the per-matchup comparison table (:func:`pab.metrics.compare.gather_matchups`).
Each bin's statistics come from the quantity-agnostic
:func:`pab.metrics.compare.log_comparison`, so backscatter and Chl aggregate the
same way. ``healpy`` (via ``remote_sensing.healpix``) is imported lazily — the
flat-bin path is pure pandas/NumPy and unit-tests offline.
"""

from __future__ import annotations

import numpy as np

from pab.metrics.compare import log_comparison

#: Default HEALPix cell size (deg) for the spatial aggregation.
DEFAULT_CELL_SIZE_DEG = 5.0


def aggregate_by(df, by, *, sat_col: str = "bbp_bing", insitu_col: str = "bbp_argo"):
    """Per-bin log-space comparison statistics.

    Args:
        df: A per-matchup frame (e.g. from ``gather_matchups`` + ``add_strata``).
        by: Column name or list of column names to group on (e.g. ``"region"``,
            ``["region", "season"]``).
        sat_col, insitu_col: The satellite and in-situ columns to compare.

    Returns:
        A :class:`pandas.DataFrame` — one row per bin with the ``by`` key(s) plus
        the :func:`~pab.metrics.compare.log_comparison` fields (``n``,
        ``median_ratio``, ``spearman``, ``log_bias``, …).
    """
    import pandas as pd

    by_list = [by] if isinstance(by, str) else list(by)
    rows = []
    for keys, g in df.groupby(by_list, dropna=False):
        keys_t = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(by_list, keys_t, strict=True))
        row.update(log_comparison(g[sat_col].to_numpy(), g[insitu_col].to_numpy()))
        rows.append(row)
    return pd.DataFrame(rows)


def magnitude_bins(values, edges=(1e-3, 3e-3), labels=("low", "mid", "high")):
    """Label values by magnitude using ``edges`` (len ``labels`` − 1 cut points)."""
    import pandas as pd

    bins = [-np.inf, *edges, np.inf]
    return pd.cut(np.asarray(values, dtype=float), bins=bins, labels=list(labels))


def nside_for_cell_size(cell_size_deg: float = DEFAULT_CELL_SIZE_DEG) -> int:
    """HEALPix ``nside`` for an approximate cell size (via ``remote_sensing``)."""
    from remote_sensing.healpix import utils as hp_utils

    nside, _ = hp_utils.get_nside_from_angular_size(cell_size_deg)
    return int(nside)


def assign_healpix(lat, lon, nside: int):
    """Assign ``(lat, lon)`` points to HEALPix cell indices (RING, ``healpy``)."""
    import healpy

    return healpy.ang2pix(
        nside, np.asarray(lon, dtype=float), np.asarray(lat, dtype=float), lonlat=True
    )


def aggregate_healpix(
    df,
    *,
    nside: int | None = None,
    cell_size_deg: float = DEFAULT_CELL_SIZE_DEG,
    sat_col: str = "bbp_bing",
    insitu_col: str = "bbp_argo",
    lat_col: str = "latitude",
    lon_col: str = "longitude",
):
    """Per-HEALPix-cell comparison statistics with cell-centre coordinates.

    Assigns each matchup to a HEALPix cell, then aggregates with
    :func:`~pab.metrics.compare.log_comparison` per cell.

    Returns:
        A :class:`pandas.DataFrame` — one row per occupied cell: ``hpix``,
        ``nside``, ``lon``/``lat`` (cell centre, lon wrapped to [-180, 180]), and
        the comparison stats.
    """
    import healpy
    import pandas as pd

    if nside is None:
        nside = nside_for_cell_size(cell_size_deg)
    cells = assign_healpix(df[lat_col], df[lon_col], nside)
    work = df.assign(_hpix=cells)
    rows = []
    for hpix, g in work.groupby("_hpix"):
        clon, clat = healpy.pix2ang(nside, int(hpix), lonlat=True)
        row = {
            "hpix": int(hpix),
            "nside": int(nside),
            "lon": float(((clon + 180.0) % 360.0) - 180.0),
            "lat": float(clat),
        }
        row.update(log_comparison(g[sat_col].to_numpy(), g[insitu_col].to_numpy()))
        rows.append(row)
    return pd.DataFrame(rows)
